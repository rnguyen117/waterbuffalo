"""Signals derived from the market itself.

These are the highest-value signals in the package, for a simple reason: they
do not require knowing anything about the teams. They read what informed
money has already done and what slow books have not yet done.

Ranked by how much they are actually worth:

1. **Stale line.** A soft book is offering a number the sharp market has left
   behind. Not a prediction -- an arbitrage against latency.
2. **Sharp/retail divergence.** Retail books shade toward the public side.
   The size of that gap is a direct measurement of where the recreational
   money is, and the unshaded side is where the price is honest.
3. **Steam.** Coordinated high-limit movement, valuable only at books that
   have not followed yet.
4. **Reverse line movement.** The line moving against the ticket count.
   Genuine but weaker than its reputation, and increasingly priced.
"""

from __future__ import annotations

from ..models import SignalContribution
from ..oddsmath import logit
from .base import SignalContext, book_lag_credit, clamp, points_to_logit


class StaleLineSignal:
    """A bettable book trailing the sharp consensus.

    Deliberately the strongest weight in the system, because it is the only
    signal whose premise is verifiable at the moment of the bet rather than
    after the game. If Pinnacle is -3.5 and a soft book is still on -2.5, the
    +1 point is real regardless of who wins.
    """

    name = "stale_line"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        movement = ctx.movement
        if movement is None or not getattr(movement, "stale_books", None):
            return []

        stale = dict(movement.stale_books)
        # Only the book we are actually betting counts. Another book being a
        # point off the market is interesting but it is not our edge.
        if ctx.book is not None:
            gap = stale.get(ctx.book)
            if gap is None:
                return []
            book = ctx.book
        else:
            book, gap = movement.stale_books[0]

        if gap < 0.5:
            return []

        adjustment = points_to_logit(gap, ctx.market_probability, ctx.sport)
        weight = clamp(0.95 * book_lag_credit(ctx.hours_to_start), 0.0, 1.0)
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=weight,
                rationale=(
                    f"{book} still posting a number {gap:+.1f} points off the sharp "
                    "consensus -- take the price before it moves"
                ),
                points=gap,
                source="line comparison",
            )
        ]


class RetailShadingSignal:
    """Exploit the gap between what sharp and retail books charge.

    Retail books do not price to be right, they price to balance action
    against a public that reliably takes favorites, overs, and popular teams.
    When retail sits meaningfully above the sharp number on one side, the
    other side is being sold at a discount to attract balancing money.

    This is the most direct encoding of "how Vegas thinks" in the package: it
    treats a book's price as a business decision about flow rather than as a
    forecast.
    """

    name = "retail_shading"

    def __init__(self, threshold: float = 0.04):
        self.threshold = threshold

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        fair = getattr(ctx, "fair_price", None)
        bias = getattr(fair, "retail_bias", None) if fair else None
        if bias is None:
            bias = (ctx.event.metadata or {}).get("retail_bias", {}).get(ctx.outcome)
        if bias is None or abs(bias) < self.threshold:
            return []

        # Negative bias means retail prices this outcome *below* the sharp
        # number: the unpopular side, sold cheap. That is the value side.
        adjustment = -bias * 0.5
        weight = clamp(min(abs(bias) / 0.15, 1.0) * 0.7, 0.0, 0.7)
        side = "unpopular" if bias < 0 else "public"
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=weight,
                rationale=(
                    f"retail books price this {abs(bias):.3f} log-odds "
                    f"{'below' if bias < 0 else 'above'} the sharp number -- "
                    f"this is the {side} side"
                ),
                source="sharp/retail split",
            )
        ]


class SteamSignal:
    """Coordinated high-limit movement.

    The critical detail is *where you are relative to the move*. Being on the
    steam side at a book that already moved is worthless -- you are paying
    the new number. Being on the steam side at a book that has not moved is
    the whole play, so the weight is tied to whether a stale book exists.
    """

    name = "steam"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        movement = ctx.movement
        if movement is None or not getattr(movement, "steam", False):
            return []
        direction = getattr(movement, "steam_direction", 0)
        if direction == 0:
            return []

        has_stale = bool(getattr(movement, "stale_books", None))
        points = 0.7 * direction
        weight = 0.6 if has_stale else 0.15

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=weight,
                rationale=(
                    "coordinated move across high-limit books "
                    + (
                        "and a slow book has not followed yet"
                        if has_stale
                        else "-- but the market has already adjusted, little left here"
                    )
                ),
                points=points,
                source="line movement",
            )
        ]


class ReverseLineMovementSignal:
    """The line moving against the majority of tickets.

    Real, but weaker and more crowded than its reputation. It is also easy to
    fake yourself out with: ticket percentages from public sites cover a
    small, unrepresentative slice of the market. Weighted accordingly.
    """

    name = "reverse_line_movement"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        movement = ctx.movement
        if movement is None or not getattr(movement, "reverse_line_movement", False):
            return []
        public = ctx.public
        if public is None:
            return []

        # RLM favors the side the public is *not* on.
        on_public_side = public.outcome == ctx.outcome
        points = -0.55 if on_public_side else 0.55
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=0.40,
                rationale=(
                    f"{public.ticket_pct:.0%} of tickets on {public.outcome} but the "
                    "line moved the other way -- respected money is opposing it"
                ),
                points=points,
                source="ticket counts",
            )
        ]


class HandleDivergenceSignal:
    """Large average bet size on one side.

    When a side has 35% of tickets and 60% of dollars, the average wager on
    it is roughly three times larger. Large wagers skew toward informed
    accounts, so this is a cleaner read than ticket counts alone -- it is
    measuring who is betting, not how many.
    """

    name = "handle_divergence"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        public = ctx.public
        if public is None:
            return []
        d = public.divergence
        if abs(d) < 0.08:
            return []

        aligned = public.outcome == ctx.outcome
        points = (0.5 if d > 0 else -0.5) * (1.0 if aligned else -1.0)
        weight = clamp(min(abs(d) / 0.30, 1.0) * 0.45, 0.0, 0.45)
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=weight,
                rationale=(
                    f"{public.outcome}: {public.handle_pct:.0%} of money on "
                    f"{public.ticket_pct:.0%} of tickets"
                ),
                points=points,
                source="handle split",
            )
        ]


class OpenerDriftSignal:
    """How far the number has traveled since it opened.

    Openers are soft -- they are posted at low limits precisely to be
    corrected. A line that has moved a long way has absorbed a lot of
    information, and betting *back* into a big move is usually betting
    against everyone who moved it. This signal mostly exists to penalize
    that, which makes it a brake rather than an accelerator.
    """

    name = "opener_drift"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if ctx.opening_line is None or ctx.current_line is None:
            return []
        move = ctx.current_line - ctx.opening_line
        if abs(move) < 1.0:
            return []

        # A line moving toward this outcome means money came in on it.
        # Taking the other side now means opposing that money.
        opposing = move > 0
        points = -0.3 * min(abs(move), 3.0) if opposing else 0.0
        if points == 0.0:
            return []

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=0.35,
                rationale=(
                    f"line has moved {move:+.1f} from the opener; taking this side "
                    "means betting against the money that moved it"
                ),
                points=points,
                source="line movement",
            )
        ]


class MarketDisagreementSignal:
    """Flag markets where books disagree unusually widely.

    Wide dispersion means someone is wrong, but it does not say who. It is
    reported with zero weight so it appears in the rationale and feeds the
    uncertainty used for staking, without pretending to have a direction.
    """

    name = "market_disagreement"

    def __init__(self, threshold: float = 0.12):
        self.threshold = threshold

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        fair = getattr(ctx, "fair_price", None)
        sigma = getattr(fair, "sigma_logit", None) if fair else None
        if sigma is None or sigma < self.threshold:
            return []
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=0.0,
                weight=0.0,
                rationale=(
                    f"books disagree unusually widely (sigma {sigma:.3f}) -- the "
                    "consensus is less reliable here, stake reduced"
                ),
                source="consensus dispersion",
            )
        ]
