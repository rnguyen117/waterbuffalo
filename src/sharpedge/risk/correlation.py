"""Correlation between bets on the same slate.

The mistake this module prevents: treating a daily card of twelve bets as
twelve independent wagers when four of them are on the same game. Correlated
positions concentrate risk exactly where the model is most likely to be wrong
about a single game, and a card that looks diversified can carry the variance
of a position three times its apparent size.

Correlations here are structural rather than estimated, because estimating a
correlation matrix from a bettor's own history requires more settled bets
than anyone has. The values are conservative and the sign is always right,
which is what matters for sizing.
"""

from __future__ import annotations

from ..models import BetCandidate, MarketType

# Same-game correlations between market types. A team covering the spread and
# winning outright are nearly the same event for a favorite; a team total over
# and the game total over move together strongly.
SAME_GAME: dict[tuple[MarketType, MarketType], float] = {
    (MarketType.MONEYLINE, MarketType.SPREAD): 0.75,
    (MarketType.MONEYLINE, MarketType.TOTAL): 0.08,
    (MarketType.SPREAD, MarketType.TOTAL): 0.10,
    (MarketType.TOTAL, MarketType.TEAM_TOTAL): 0.62,
    (MarketType.SPREAD, MarketType.TEAM_TOTAL): 0.35,
    (MarketType.MONEYLINE, MarketType.TEAM_TOTAL): 0.40,
    (MarketType.TOTAL, MarketType.ALTERNATE_TOTAL): 0.90,
    (MarketType.SPREAD, MarketType.ALTERNATE_SPREAD): 0.90,
    (MarketType.TOTAL, MarketType.FIRST_HALF): 0.60,
    (MarketType.PLAYER_PROP, MarketType.TEAM_TOTAL): 0.30,
    (MarketType.PLAYER_PROP, MarketType.TOTAL): 0.18,
    (MarketType.PLAYER_PROP, MarketType.SPREAD): 0.15,
}

# Bets in the same league on the same day share exposure to league-wide
# effects: officiating emphasis, weather systems, scoring environment shifts.
# Small but not zero, and it adds up across a large card.
SAME_LEAGUE_SAME_DAY = 0.04

# Two bets on the same team across different games (a season-long and a
# single game, say) share team-quality risk.
SAME_TEAM_DIFFERENT_GAME = 0.25


def pair_correlation(a: BetCandidate, b: BetCandidate) -> float:
    """Estimated correlation between two candidate bets."""
    if a.key() == b.key():
        return 1.0

    if a.event.event_id == b.event.event_id:
        # Opposite sides of the same market are strongly negatively
        # correlated -- they cannot both win.
        if a.market_type == b.market_type and a.outcome != b.outcome:
            return -0.92
        if a.market_type == b.market_type and a.outcome == b.outcome:
            return 0.97  # same bet at different books or lines
        key = (a.market_type, b.market_type)
        rho = SAME_GAME.get(key)
        if rho is None:
            rho = SAME_GAME.get((b.market_type, a.market_type), 0.20)
        # Direction matters: two "overs" agree, an over and an under oppose.
        if _opposing_directions(a, b):
            return -rho
        return rho

    if a.event.league == b.event.league:
        same_day = a.event.start_time.date() == b.event.start_time.date()
        if _shares_team(a, b):
            return SAME_TEAM_DIFFERENT_GAME
        if same_day:
            return SAME_LEAGUE_SAME_DAY

    return 0.0


def _opposing_directions(a: BetCandidate, b: BetCandidate) -> bool:
    """Whether two bets point opposite ways on scoring or on a team."""
    a_out, b_out = a.outcome.lower(), b.outcome.lower()
    a_over = a_out.startswith("over")
    b_over = b_out.startswith("over")
    a_under = a_out.startswith("under")
    b_under = b_out.startswith("under")
    if (a_over and b_under) or (a_under and b_over):
        return True
    # Two team-based bets on opposite teams in the same game oppose.
    a_team = _team_of(a)
    b_team = _team_of(b)
    if a_team and b_team and a_team != b_team:
        return True
    return False


def _team_of(bet: BetCandidate) -> str | None:
    for team in (bet.event.home_team, bet.event.away_team):
        if team.lower() in bet.outcome.lower():
            return team
    return None


def _shares_team(a: BetCandidate, b: BetCandidate) -> bool:
    teams_a = {a.event.home_team, a.event.away_team}
    teams_b = {b.event.home_team, b.event.away_team}
    return bool(teams_a & teams_b)


def correlation_matrix(bets: list[BetCandidate]) -> list[list[float]]:
    """Full symmetric correlation matrix for a slate."""
    n = len(bets)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            rho = pair_correlation(bets[i], bets[j])
            matrix[i][j] = rho
            matrix[j][i] = rho
    return matrix


def portfolio_variance(
    stakes: list[float], variances: list[float], matrix: list[list[float]]
) -> float:
    """Variance of total slate profit given stakes and a correlation matrix."""
    n = len(stakes)
    total = 0.0
    for i in range(n):
        for j in range(n):
            total += (
                stakes[i]
                * stakes[j]
                * matrix[i][j]
                * (variances[i] ** 0.5)
                * (variances[j] ** 0.5)
            )
    return total


def bet_variance(probability: float, decimal_odds: float) -> float:
    """Variance of profit per unit staked on a binary bet."""
    b = decimal_odds - 1.0
    p = min(max(probability, 0.0), 1.0)
    mean = p * b - (1.0 - p)
    return p * (b - mean) ** 2 + (1.0 - p) * (-1.0 - mean) ** 2


def effective_bet_count(matrix: list[list[float]]) -> float:
    """How many genuinely independent bets a correlated slate amounts to.

    Twelve bets with heavy same-game overlap can be worth six independent
    ones. Reporting this keeps a card from looking more diversified than it
    is, which is the practical failure this whole module exists to prevent.
    """
    n = len(matrix)
    if n == 0:
        return 0.0
    total = sum(sum(abs(v) for v in row) for row in matrix)
    if total <= 0:
        return float(n)
    return (n * n) / total
