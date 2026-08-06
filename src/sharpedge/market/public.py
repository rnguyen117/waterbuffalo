"""Public money: where it is, and what books do about it.

A sportsbook is not trying to predict games. It is trying to earn the hold on
a balanced book, and failing that, to be positioned against the side it thinks
is wrong. Both objectives make it price against the public rather than against
the truth, and that difference is measurable.

Four readings, in descending order of how much they are worth:

**1. Handle versus tickets.** The cleanest signal available. If a side has 30%
of tickets and 65% of dollars, the average wager on it is roughly four times
larger. Large wagers come disproportionately from accounts that win. This
measures *who* is betting, not how many, and it is far more informative than
the ticket count alone.

**2. Prop over-shading.** Prop handle is overwhelmingly recreational, and
recreational bettors bet overs -- they buy a player to do something. Books
shade prop overs accordingly, and because almost no sharp money corrects prop
markets, the shading survives to settlement. This is the largest systematic
public-money effect in the entire betting menu.

**3. Public darlings.** A handful of teams draw money regardless of price.
Books shade their numbers by a half point to a full point and are happy to
take the other side.

**4. Ticket percentage alone.** The weakest of the four and the most quoted.
Public ticket data covers a small, unrepresentative slice of the market, and
the "fade the public" rule has been widely known for long enough that much of
it is priced. Included, weighted low, and labeled as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import MarketType, PublicBetting

# Teams that draw disproportionate recreational money. Books shade their
# lines because the flow arrives regardless of the number.
PUBLIC_DARLINGS: dict[str, float] = {
    # NFL
    "Dallas Cowboys": 1.00,
    "Kansas City Chiefs": 0.95,
    "Green Bay Packers": 0.80,
    "Philadelphia Eagles": 0.75,
    "San Francisco 49ers": 0.70,
    "Pittsburgh Steelers": 0.70,
    "Buffalo Bills": 0.65,
    "Baltimore Ravens": 0.55,
    "Detroit Lions": 0.55,
    # NBA
    "Los Angeles Lakers": 1.00,
    "Golden State Warriors": 0.95,
    "Boston Celtics": 0.80,
    "New York Knicks": 0.70,
    "Milwaukee Bucks": 0.60,
    "Phoenix Suns": 0.55,
    # MLB
    "New York Yankees": 0.95,
    "Los Angeles Dodgers": 0.90,
    "Boston Red Sox": 0.75,
    "Chicago Cubs": 0.70,
}


@dataclass
class PublicRead:
    """What the money says about one side of one market."""

    outcome: str
    ticket_pct: float | None = None
    handle_pct: float | None = None
    darling_score: float = 0.0
    is_over: bool = False
    # Positive means this side is the one being shaded, so its price is worse
    # than it should be and the other side is where the value sits.
    shading_logit: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def divergence(self) -> float | None:
        """Handle share minus ticket share."""
        if self.ticket_pct is None or self.handle_pct is None:
            return None
        return self.handle_pct - self.ticket_pct

    @property
    def average_bet_ratio(self) -> float | None:
        """How large the average wager on this side is, relative to the other.

        A ratio of 3.0 means the typical bet on this side is three times the
        size of the typical bet against it.
        """
        if self.ticket_pct is None or self.handle_pct is None:
            return None
        if self.ticket_pct <= 0 or self.ticket_pct >= 1:
            return None
        mine = self.handle_pct / self.ticket_pct
        theirs = (1 - self.handle_pct) / (1 - self.ticket_pct)
        return mine / theirs if theirs > 0 else None

    @property
    def verdict(self) -> str:
        ratio = self.average_bet_ratio
        if ratio is None:
            return "no public data"
        if ratio > 1.6:
            return "sharp side -- large wagers concentrated here"
        if ratio < 0.65:
            return "public side -- small tickets, little real money"
        return "money and tickets are balanced"


def darling_score(team: str) -> float:
    """How much recreational money a team attracts, 0 to 1."""
    return PUBLIC_DARLINGS.get(team, 0.0)


def read(
    outcome: str,
    market_type: MarketType,
    public: PublicBetting | None,
    stat: str | None = None,
    is_home: bool = False,
    is_favorite: bool = False,
) -> PublicRead:
    """Assemble everything known about public money on one side."""
    is_over = outcome.lower().startswith("over")
    result = PublicRead(
        outcome=outcome,
        ticket_pct=public.ticket_pct if public else None,
        handle_pct=public.handle_pct if public else None,
        darling_score=darling_score(outcome),
        is_over=is_over,
    )

    shading = 0.0

    # 1. Prop overs carry the largest and most reliable shading.
    if market_type.is_prop and stat:
        from .props import over_shading

        magnitude = over_shading(stat)
        if is_over:
            shading += magnitude
            result.notes.append(
                f"prop overs on {stat.replace('_', ' ')} take roughly "
                f"{_over_share(stat):.0%} of tickets, and the price reflects it"
            )
        else:
            shading -= magnitude * 0.35
            result.notes.append(
                "prop unders are the unpopular side and are priced more honestly"
            )

    # 2. Game totals: the public bets overs there too, though far less
    # lopsidedly than on props, because sharp money does correct game totals.
    elif market_type in (MarketType.TOTAL, MarketType.FIRST_HALF_TOTAL, MarketType.TEAM_TOTAL):
        if is_over:
            shading += 0.022
            result.notes.append("the public leans over on game totals")

    # 3. Public darlings.
    if result.darling_score > 0.4:
        shading += 0.030 * result.darling_score
        result.notes.append(
            f"{outcome} is a heavily backed public team; its number carries a premium"
        )

    # 4. Ticket counts, weighted low on purpose.
    if public is not None and public.outcome == outcome:
        if public.ticket_pct > 0.70:
            shading += 0.018
            result.notes.append(
                f"{public.ticket_pct:.0%} of tickets are on this side"
            )
        divergence = public.divergence
        if divergence is not None:
            if divergence > 0.10:
                # Large money agrees: this is not really the public side.
                shading -= 0.035
                result.notes.append(
                    f"but {public.handle_pct:.0%} of the money is here too -- "
                    "large wagers, not small ones"
                )
            elif divergence < -0.10:
                shading += 0.030
                result.notes.append(
                    f"only {public.handle_pct:.0%} of the money on "
                    f"{public.ticket_pct:.0%} of tickets -- small-ticket money"
                )

    result.shading_logit = shading
    return result


def _over_share(stat: str) -> float:
    from .props import DEFAULT_OVER_SHARE, PROP_OVER_TICKET_SHARE

    return PROP_OVER_TICKET_SHARE.get(
        stat.lower().replace(" ", "_"), DEFAULT_OVER_SHARE
    )


def contrarian_value(read: PublicRead) -> float:
    """Log-odds of value on this side from public shading alone.

    Negative when this is the shaded side. Note the sign convention: shading
    makes a side *worse* to bet, so the value is the negative of it.
    """
    return -read.shading_logit


def fade_recommendation(read: PublicRead) -> str | None:
    """Plain-language read, when there is one worth stating."""
    if read.shading_logit > 0.05:
        return (
            f"heavily shaded side ({read.shading_logit:+.3f} log-odds of public "
            "premium) -- the other side is where the honest price is"
        )
    if read.shading_logit < -0.03:
        return "unpopular side; the price has no public premium built in"
    return None


def consensus_public(reports: list[PublicBetting]) -> PublicBetting | None:
    """Average several public-data sources into one read.

    Different providers report very different numbers for the same game
    because each sees only its own handle. Averaging is crude but better than
    trusting whichever one you happened to scrape.
    """
    if not reports:
        return None
    first = reports[0]
    return PublicBetting(
        event_id=first.event_id,
        market_type=first.market_type,
        outcome=first.outcome,
        ticket_pct=sum(r.ticket_pct for r in reports) / len(reports),
        handle_pct=sum(r.handle_pct for r in reports) / len(reports),
    )
