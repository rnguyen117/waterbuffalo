"""RSS news ingestion.

A minimal RSS/Atom parser on the standard library, because the value of a
news feed here is latency and a heavyweight dependency chain does not help
with that.

Feed selection matters more than parsing does. Beat reporters break
availability news well before aggregators do, and the gap between a reporter's
post and a national feed picking it up is frequently longer than the window
in which a soft book's line is still stale. The default list below is
national coverage, which is a starting point rather than an edge -- a serious
setup follows the specific reporters covering the teams it bets.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from ..models import NewsItem
from .base import SourceError

DEFAULT_FEEDS: dict[str, str] = {
    "espn-nfl": "https://www.espn.com/espn/rss/nfl/news",
    "espn-nba": "https://www.espn.com/espn/rss/nba/news",
    "espn-mlb": "https://www.espn.com/espn/rss/mlb/news",
    "espn-nhl": "https://www.espn.com/espn/rss/nhl/news",
    "cbs-nfl": "https://www.cbssports.com/rss/headlines/nfl/",
    "cbs-nba": "https://www.cbssports.com/rss/headlines/nba/",
}


class RSSNewsSource:
    """Pull headlines from RSS feeds and normalize them."""

    name = "rss"

    def __init__(
        self,
        feeds: dict[str, str] | list[str] | None = None,
        timeout: float = 8.0,
        max_age_hours: float = 24.0,
    ):
        if feeds is None:
            self.feeds = dict(DEFAULT_FEEDS)
        elif isinstance(feeds, list):
            self.feeds = {url: url for url in feeds}
        else:
            self.feeds = dict(feeds)
        self.timeout = timeout
        self.max_age_hours = max_age_hours

    def fetch_news(self, since: datetime | None = None) -> list[NewsItem]:
        """Fetch every configured feed, skipping any that fail.

        One dead feed must not take down a morning run, so failures are
        swallowed per feed rather than raised.
        """
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError("RSS ingestion needs `requests`: pip install requests") from exc

        cutoff = since or datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)
        items: list[NewsItem] = []

        for source_name, url in self.feeds.items():
            try:
                response = requests.get(
                    url, timeout=self.timeout, headers={"User-Agent": "sharp-edge/1.0"}
                )
                if response.status_code >= 400:
                    continue
                items.extend(self._parse(response.content, source_name, cutoff))
            except Exception:
                continue

        items.sort(key=lambda i: i.published, reverse=True)
        return items

    def _parse(self, content: bytes, source: str, cutoff: datetime) -> list[NewsItem]:
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError:
            return []

        out: list[NewsItem] = []
        # RSS <item> and Atom <entry> both handled.
        nodes = root.iter("item")
        entries = list(nodes) or [
            e for e in root.iter() if e.tag.endswith("}entry") or e.tag == "entry"
        ]

        for node in entries:
            title = _text(node, "title")
            if not title:
                continue
            published = _published(node)
            if published < cutoff:
                continue
            out.append(
                NewsItem(
                    headline=_clean(title),
                    published=published,
                    source=source,
                    url=_text(node, "link"),
                    body=_clean(_text(node, "description") or ""),
                )
            )
        return out


def _text(node, tag: str) -> str:
    for child in node:
        if child.tag == tag or child.tag.endswith("}" + tag):
            if child.text:
                return child.text.strip()
            # Atom links carry the URL in an attribute.
            href = child.attrib.get("href")
            if href:
                return href
    return ""


def _published(node) -> datetime:
    for tag in ("pubDate", "published", "updated", "date"):
        raw = _text(node, tag)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.now(timezone.utc)


_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text).replace("&amp;", "&").replace("&#39;", "'").strip()
