"""Rendering the daily card.

The report has one job: make it obvious what to bet, for how much, and why --
and make it equally obvious when the answer is "nothing". A card that
recommends fifteen bets every day is not finding fifteen edges, and a report
that never prints an empty slate is hiding something.

Console output uses plain ASCII so it survives any terminal. Markdown and
JSON are provided for anything downstream.
"""

from __future__ import annotations

import json
from datetime import datetime

from .models import Confidence, Opportunity, SlateResult

TIER_LABEL = {
    Confidence.A: "A  strong",
    Confidence.B: "B  solid",
    Confidence.C: "C  marginal",
}


def console(result: SlateResult, verbose: bool = False) -> str:
    """Human-readable card for a terminal."""
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add(f"  DAILY CARD  -  {result.generated_at:%Y-%m-%d %H:%M UTC}")
    add("=" * 78)
    add(f"  Bankroll ${result.bankroll:,.0f}   |   {result.considered:,} prices screened")

    if not result.bets:
        add("")
        add("  No bets today.")
        add("")
        add("  This is a normal and frequent outcome. Nothing in the slate cleared")
        add("  the expected-value floor once uncertainty and vig were accounted for.")
        add("  Forcing a bet on a day like this is how edges get given back.")
        if result.skipped and verbose:
            add("")
            add("  Skipped:")
            for name, reason in result.skipped[:12]:
                add(f"    - {name}: {reason}")
        add("=" * 78)
        return "\n".join(lines)

    add(
        f"  {len(result.bets)} bets   |   ${result.total_stake:,.0f} at risk "
        f"({result.total_stake / result.bankroll:.1%} of bankroll)"
    )
    add(
        f"  Expected profit ${result.expected_profit:,.2f} "
        f"({result.expected_roi:+.2%} on turnover)"
    )
    add("")

    for tier in (Confidence.A, Confidence.B, Confidence.C):
        tier_bets = result.by_confidence(tier)
        if not tier_bets:
            continue
        add("-" * 78)
        add(f"  TIER {TIER_LABEL[tier]}")
        add("-" * 78)
        for bet in tier_bets:
            add("")
            add(f"  {bet.event.name}  [{bet.event.league}]  {bet.event.start_time:%a %H:%M UTC}")
            add(f"  >> {bet.description}")
            add(
                f"     Stake ${bet.stake:,.0f}  |  EV {bet.ev_pct:+.2f}%  |  "
                f"fair {bet.fair.fair_american:+.0f}  |  model {bet.model_probability:.1%} "
                f"vs market {bet.implied:.1%}"
            )
            reasons = [
                c.rationale for c in bet.signals if abs(c.effective) > 1e-4
            ]
            for reason in reasons[:4]:
                add(f"     - {reason}")
            if verbose:
                for note in bet.notes:
                    add(f"       . {note}")

    if result.opportunities:
        add("")
        add("-" * 78)
        add("  STRUCTURAL OPPORTUNITIES  (no forecast required)")
        add("-" * 78)
        for opp in result.opportunities[:8]:
            add(f"  [{opp.kind}] {opp.event.name} {opp.market_type.value}")
            add(f"     {opp.description}")
            add(f"     {opp.profit_pct:+.2%}  -  {opp.note}")

    add("")
    add("=" * 78)
    add("  Sizing is fractional Kelly against uncertainty-adjusted probabilities.")
    add("  Track closing line value; it tells you whether this is working long")
    add("  before the profit column does.")
    add("=" * 78)
    return "\n".join(lines)


def markdown(result: SlateResult) -> str:
    """Markdown card, for a file, a commit, or a message."""
    lines: list[str] = []
    add = lines.append

    add(f"# Daily Card - {result.generated_at:%Y-%m-%d}")
    add("")
    add(
        f"**Bankroll** ${result.bankroll:,.0f} | **Screened** {result.considered:,} prices "
        f"| **Selected** {len(result.bets)}"
    )
    add("")

    if not result.bets:
        add("## No bets today")
        add("")
        add(
            "Nothing cleared the expected-value floor after uncertainty and vig. "
            "This happens often and is the system working as intended."
        )
        return "\n".join(lines)

    add(
        f"**At risk** ${result.total_stake:,.0f} ({result.total_stake / result.bankroll:.1%}) "
        f"| **Expected profit** ${result.expected_profit:,.2f} ({result.expected_roi:+.2%})"
    )
    add("")
    add("| Tier | Game | Bet | Book | Stake | EV | Model | Market |")
    add("|---|---|---|---|---:|---:|---:|---:|")
    for bet in result.bets:
        add(
            f"| {bet.confidence.value} | {bet.event.name} | "
            f"{bet.outcome}{'' if bet.line is None else f' {bet.line:+g}'} "
            f"({bet.american:+.0f}) | {bet.book} | ${bet.stake:,.0f} | "
            f"{bet.ev_pct:+.2f}% | {bet.model_probability:.1%} | {bet.implied:.1%} |"
        )

    add("")
    add("## Reasoning")
    for bet in result.bets:
        add("")
        add(f"### {bet.description}")
        add(f"*{bet.event.name}, {bet.event.start_time:%a %d %b %H:%M UTC}*")
        add("")
        for contribution in bet.signals:
            if abs(contribution.effective) <= 1e-4:
                continue
            add(f"- **{contribution.name}**: {contribution.rationale}")
        for note in bet.notes:
            add(f"- {note}")

    if result.opportunities:
        add("")
        add("## Structural opportunities")
        add("")
        for opp in result.opportunities[:10]:
            add(f"- **{opp.kind}** {opp.event.name}: {opp.description} ({opp.profit_pct:+.2%}) - {opp.note}")

    return "\n".join(lines)


def to_json(result: SlateResult) -> str:
    """Machine-readable card."""
    payload = {
        "generated_at": result.generated_at.isoformat(),
        "bankroll": result.bankroll,
        "prices_screened": result.considered,
        "total_stake": result.total_stake,
        "expected_profit": result.expected_profit,
        "expected_roi": result.expected_roi,
        "bets": [
            {
                "event_id": b.event.event_id,
                "event": b.event.name,
                "league": b.event.league,
                "start_time": b.event.start_time.isoformat(),
                "market": b.market_type.value,
                "outcome": b.outcome,
                "line": b.line,
                "book": b.book,
                "american": b.american,
                "decimal": round(b.decimal, 4),
                "stake": b.stake,
                "confidence": b.confidence.value,
                "ev": round(b.ev, 5),
                "model_probability": round(b.model_probability, 5),
                "market_probability": round(b.implied, 5),
                "fair_probability": round(b.fair.probability, 5),
                "sigma_logit": round(b.fair.sigma_logit, 5),
                "books_priced": b.fair.n_books,
                "signals": [
                    {
                        "name": c.name,
                        "weight": round(c.weight, 4),
                        "adjustment": round(c.logit_adjustment, 5),
                        "rationale": c.rationale,
                    }
                    for c in b.signals
                    if abs(c.effective) > 1e-6
                ],
                "notes": b.notes,
            }
            for b in result.bets
        ],
        "opportunities": [
            {
                "kind": o.kind,
                "event": o.event.name,
                "market": o.market_type.value,
                "legs": [
                    {"book": book, "outcome": outcome, "american": american, "line": line}
                    for book, outcome, american, line in o.legs
                ],
                "profit_pct": round(o.profit_pct, 5),
                "note": o.note,
            }
            for o in result.opportunities
        ],
        "skipped": [{"what": w, "why": r} for w, r in result.skipped],
    }
    return json.dumps(payload, indent=2)


def summary_line(result: SlateResult) -> str:
    """One-line status, for a notification or a log."""
    if not result.bets:
        return (
            f"{result.generated_at:%Y-%m-%d}: no bets "
            f"({result.considered:,} prices screened, none cleared the floor)"
        )
    return (
        f"{result.generated_at:%Y-%m-%d}: {len(result.bets)} bets, "
        f"${result.total_stake:,.0f} at risk, "
        f"${result.expected_profit:,.2f} expected ({result.expected_roi:+.2%})"
    )
