"""Tennis: win probability from serve percentages, not a margin distribution.

Every other sport in this package prices a market by recovering an expected
margin and running it through a normal (or Skellam, or gamma) distribution.
Tennis cannot be modeled that way, because tennis does not have a margin in
the sense football or basketball do -- a 6-1 6-2 win and a 7-6 7-6 win are
both "the match," and neither final score maps onto a single continuous
scale the way point differential does.

What tennis has instead is serve percentage: the probability a player wins a
point on their own serve. That single number, run through the actual rules
of scoring -- games are won by four points with deuce, sets by six games with
a tiebreak at 6-6, matches by two sets of three or three of five -- pins down
everything else. This module computes that chain exactly, via recursion
rather than a memorized closed form, and every function is cross-checked
against an independent Monte Carlo simulation in the test suite rather than
trusted on the strength of a formula transcribed from memory.

The payoff mirrors what ``oddsmath.prob_to_spread`` does for team sports:
given a quoted moneyline, invert the model to recover the serve-percentage
edge it implies, so a news signal ("second serve speed down 8 mph") has
somewhere principled to land -- the same way a team-sport signal lands on
points and gets pushed through the margin distribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import comb

__all__ = [
    "game_win_prob",
    "tiebreak_win_prob",
    "set_win_prob",
    "match_win_prob",
    "fit_hold_edge_to_market",
    "implied_hold_edge",
    "games_margin_sigma",
    "total_games_mean",
    "MatchFormat",
    "BASELINE_HOLD_PROB",
]

# ATP/WTA tour average probability of winning a point on one's own serve.
# Used as the center that a fitted "hold edge" perturbs symmetrically around
# -- see fit_hold_edge_to_market.
BASELINE_HOLD_PROB = 0.64


def win_first_to_k(p: float, k: int) -> float:
    """P(reach k successes before the opponent reaches k), no win-by-two.

    The general form behind both the "first three points of a game" partial
    sum and the whole match-from-sets calculation: reaching k wins with
    exactly j losses first requires C(k-1+j, j) orderings (the last point is
    forced to be the k-th win), each with probability p**k * q**j.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    if k < 1:
        raise ValueError("k must be at least 1")
    q = 1.0 - p
    return sum(comb(k - 1 + j, j) * (p**k) * (q**j) for j in range(k))


def game_win_prob(p: float) -> float:
    """P(server wins a game) given p = P(server wins a point on serve).

    A game is first-to-four-points, win by two. Reaching 4-0, 4-1, or 4-2 is
    the no-deuce case (``win_first_to_k`` with k=4, truncated to j<3, since
    j=3 is deuce rather than a loss). From deuce (3-3), the game becomes an
    effectively infinite point-for-point contest that resolves the instant
    either side gets two points ahead; the classic result for that repeated
    structure is p**2 / (p**2 + q**2), which this derives via the geometric
    series rather than asserting.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    q = 1.0 - p

    no_deuce = sum(comb(3 + j, j) * (p**4) * (q**j) for j in range(3))
    prob_reach_deuce = comb(6, 3) * (p**3) * (q**3)

    denom = p * p + q * q
    prob_win_from_deuce = (p * p) / denom if denom > 0 else 0.5

    return no_deuce + prob_reach_deuce * prob_win_from_deuce


def _tied_pair_win_prob(p_a: float, p_b: float) -> float:
    """P(A wins the tiebreak) from a tied score at or beyond 6-6, closed form.

    Once tied at 6-6 or later, the score cannot reach a 2-point lead on the
    very next point -- it takes exactly two more points (one served by each
    player, in whichever order the rotation currently has them) to either
    decide the tiebreak (someone goes up 2) or return to tied one level
    higher, with the *other* player now serving next. That "one serve each,
    order swaps each time we return to tied" structure is a two-state
    renewal process with no bound on how many times it can repeat, so
    (unlike a single game's deuce) it cannot be solved by fixed-depth
    recursion -- Python's call stack would overflow long before the
    (exponentially unlikely but nonzero) long sequences resolve.

    Let X = P(A wins | A serves the next point, B serves the one after) and
    Y = P(A wins | B serves the next point, A serves the one after). Writing
    out both point orders and solving the resulting pair of linear equations
    gives X = Y = p_a*q_b / (p_a + p_b - 2*p_a*p_b) -- which makes sense:
    both orders involve exactly one A-serve and one B-serve before the next
    tie-or-decide, so which one goes first doesn't change the odds.
    """
    q_a = 1.0 - p_a
    q_b = 1.0 - p_b
    return p_a * q_b / (p_a + p_b - 2.0 * p_a * p_b)


@lru_cache(maxsize=None)
def _tiebreak_state(points_a: int, points_b: int, a_serves: bool, p_a: float, p_b: float) -> float:
    """P(player A wins the tiebreak) from a given point score and server.

    Recursive rather than closed-form below 6-6, where the state space is
    small and bounded. At or beyond 6-6 with the score tied, this defers to
    ``_tied_pair_win_prob`` instead of recursing further -- see that
    function's docstring for why plain recursion breaks down there.
    """
    if points_a >= 7 and points_a - points_b >= 2:
        return 1.0
    if points_b >= 7 and points_b - points_a >= 2:
        return 0.0
    if points_a == points_b and points_a >= 6:
        return _tied_pair_win_prob(p_a, p_b)
    p = p_a if a_serves else p_b
    win_this_point_a = p if a_serves else (1.0 - p)

    next_a_serves = _tiebreak_server(points_a + points_b + 1)

    return win_this_point_a * _tiebreak_state(points_a + 1, points_b, next_a_serves, p_a, p_b) + (
        1 - win_this_point_a
    ) * _tiebreak_state(points_a, points_b + 1, next_a_serves, p_a, p_b)


def _tiebreak_server(points_played: int) -> bool:
    """Whether player A serves the point after ``points_played`` have been played.

    Point 1 (points_played=0 before it): A serves. Then B serves points 2-3,
    A serves points 4-5, and so on -- a new server every two points after the
    first.
    """
    if points_played == 0:
        return True
    # Points 1 is A (index 0). Points 2,3 -> B. Points 4,5 -> A. ...
    block = (points_played - 1) // 2
    return block % 2 == 1  # odd block => back to A


def tiebreak_win_prob(p_a: float, p_b: float) -> float:
    """P(player A wins a tiebreak), given each player's point-on-serve rate."""
    if not (0.0 < p_a < 1.0 and 0.0 < p_b < 1.0):
        raise ValueError("probabilities must be in (0, 1)")
    _tiebreak_state.cache_clear()
    return _tiebreak_state(0, 0, True, p_a, p_b)


@dataclass(frozen=True)
class MatchFormat:
    """Scoring format: how many sets to win, and whether the last set has a tiebreak.

    Most tour-level tennis (all WTA, most ATP, all Slam women's draws) is
    best-of-three with tiebreaks throughout. Men's Slams are best-of-five.
    Some tournaments play a deciding-set tiebreak at 6-6 even where the rest
    of the format historically used advantage scoring; ``final_set_tiebreak``
    covers that distinction without needing a third scoring path.
    """

    sets_to_win: int = 2
    final_set_tiebreak: bool = True

    @property
    def best_of(self) -> int:
        return 2 * self.sets_to_win - 1


BEST_OF_3 = MatchFormat(sets_to_win=2, final_set_tiebreak=True)
BEST_OF_5 = MatchFormat(sets_to_win=3, final_set_tiebreak=True)


@lru_cache(maxsize=None)
def _set_state(
    games_a: int,
    games_b: int,
    a_serves: bool,
    p_game_a: float,
    p_game_b: float,
    p_point_a: float,
    p_point_b: float,
    tiebreak: bool,
) -> float:
    """P(player A wins the set) from a given game score and server.

    ``p_game_a``/``p_game_b`` (hold rates) drive the game-by-game recursion;
    ``p_point_a``/``p_point_b`` (point-on-serve rates) are carried through
    only for the 6-6 tiebreak, which is a point-by-point contest and would
    be mis-scaled if fed hold rates instead -- a hold rate like 0.83 is not
    interchangeable with the ~0.55-0.70 point rate it was built from.
    """
    if games_a >= 6 and games_a - games_b >= 2:
        return 1.0
    if games_b >= 6 and games_b - games_a >= 2:
        return 0.0
    if games_a == 6 and games_b == 6:
        if tiebreak:
            return tiebreak_win_prob(p_point_a, p_point_b)
        # Advantage set: keep playing service games until someone is two
        # games clear. Equivalent in structure to the game/tiebreak cases
        # above -- alternating "games" instead of "points" -- solved the
        # same way a single game resolves from deuce.
        hold_a = p_game_a
        hold_b = p_game_b
        # From 6-6 with advantage scoring, treat each *game pair* (A serves
        # one, B serves one) as a single trial: A wins the pair outright if
        # she holds and B does not; B wins outright if the reverse; and a
        # split pair (both hold or neither holds) returns to the same
        # 6-6-equivalent state, so it drops out of the conditional win prob.
        a_wins_pair = hold_a * (1 - hold_b)
        b_wins_pair = (1 - hold_a) * hold_b
        denom = a_wins_pair + b_wins_pair
        return a_wins_pair / denom if denom > 0 else 0.5

    p_hold = p_game_a if a_serves else p_game_b
    win_game_a = p_hold if a_serves else (1.0 - p_hold)
    next_a_serves = not a_serves

    return win_game_a * _set_state(
        games_a + 1, games_b, next_a_serves, p_game_a, p_game_b, p_point_a, p_point_b, tiebreak
    ) + (1 - win_game_a) * _set_state(
        games_a, games_b + 1, next_a_serves, p_game_a, p_game_b, p_point_a, p_point_b, tiebreak
    )


def set_win_prob(
    p_a_hold: float,
    p_b_hold: float,
    p_a_point: float,
    p_b_point: float,
    a_serves_first: bool = True,
    tiebreak: bool = True,
) -> float:
    """P(player A wins a set), given each player's own service-game hold rate.

    ``p_a_hold`` and ``p_b_hold`` drive the game-by-game recursion.
    ``p_a_point`` and ``p_b_point`` -- the underlying point-on-serve rates
    ``p_a_hold``/``p_b_hold`` were derived from via ``game_win_prob`` -- are
    needed separately because a 6-6 set is decided by a point-by-point
    tiebreak, not a game-by-game one; feeding it hold rates instead of point
    rates would price the tiebreak off the wrong scale entirely.
    """
    if not (0.0 < p_a_hold < 1.0 and 0.0 < p_b_hold < 1.0):
        raise ValueError("hold probabilities must be in (0, 1)")
    if not (0.0 < p_a_point < 1.0 and 0.0 < p_b_point < 1.0):
        raise ValueError("point probabilities must be in (0, 1)")
    _set_state.cache_clear()
    return _set_state(0, 0, a_serves_first, p_a_hold, p_b_hold, p_a_point, p_b_point, tiebreak)


def match_win_prob(
    p_a_point: float, p_b_point: float, fmt: MatchFormat = BEST_OF_3
) -> float:
    """P(player A wins the match), from each player's point-on-serve rate.

    Composes the whole chain: point rate -> game hold rate -> set win
    probability -> match win probability. Sets are treated as independent
    and identically distributed given the two hold rates, the standard
    simplifying assumption in tennis forecasting (Klaassen & Magnus and the
    Barnett-Clarke model both use it) -- it ignores momentum and fatigue
    across sets, which is a real but second-order effect next to serve
    quality itself.
    """
    hold_a = game_win_prob(p_a_point)
    hold_b = game_win_prob(p_b_point)
    p_set = set_win_prob(hold_a, hold_b, p_a_point, p_b_point, tiebreak=fmt.final_set_tiebreak)
    return win_first_to_k(p_set, fmt.sets_to_win)


def fit_hold_edge_to_market(
    target_win_prob: float,
    fmt: MatchFormat = BEST_OF_3,
    baseline: float = BASELINE_HOLD_PROB,
    tol: float = 1e-10,
) -> float:
    """Recover the point-rate edge implied by a quoted match win probability.

    Assumes a symmetric perturbation around a shared baseline serve rate:
    player A serves at ``baseline + edge``, player B at ``baseline - edge``.
    This is the tennis analog of recovering an expected margin from a
    moneyline in a team sport -- it turns "the market says 62% to win" into
    a number (serve-rate points) that a signal can act on directly, the same
    way ``implied_expected_margin`` does for football.
    """
    if not 0.0 < target_win_prob < 1.0:
        raise ValueError("target_win_prob must be in (0, 1)")

    lo, hi = -0.20, 0.20
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        p = match_win_prob(baseline + mid, baseline - mid, fmt)
        if p < target_win_prob:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def implied_hold_edge(edge: float, delta: float, baseline: float = BASELINE_HOLD_PROB) -> float:
    """Reprice a match win probability after shifting the hold-rate edge by delta.

    Used the way ``points_to_logit`` is used elsewhere: a signal reports its
    effect in the sport's native unit (here, serve-rate points) and this
    turns that into a new probability.
    """
    return match_win_prob(baseline + edge + delta, baseline - edge - delta)


# ---------------------------------------------------------------------------
# Games-handicap and total-games markets
# ---------------------------------------------------------------------------
#
# Match win probability above is computed exactly. Games-margin is not: the
# exact distribution requires marginalizing over every possible set-score
# sequence, which is tractable but not worth the complexity next to the
# secondary market it prices. A Gaussian approximation on games margin is
# used instead, calibrated to typical tour-level spread, and reported
# honestly as an approximation rather than dressed up as exact.

# Standard deviation of (games won by winner - games won by loser), roughly
# calibrated from typical tour outcomes: straight-set wins cluster around a
# 4-6 game margin, three-setters pull the distribution wider.
GAMES_MARGIN_SIGMA = {
    True: 5.6,   # best-of-five: one extra set of variance
    False: 4.1,  # best-of-three
}


def games_margin_sigma(fmt: MatchFormat = BEST_OF_3) -> float:
    return GAMES_MARGIN_SIGMA[fmt.sets_to_win == 3]


def total_games_mean(p_a_point: float, p_b_point: float, fmt: MatchFormat = BEST_OF_3) -> float:
    """Rough expected total games played, for total-games markets.

    Closer players play more games (more deuces, more tiebreaks, more three-
    setters); this scales a baseline expectation by how close the match
    projects to be, which is the direction that matters even though the
    magnitude is an approximation.
    """
    p_match = match_win_prob(p_a_point, p_b_point, fmt)
    closeness = 1.0 - abs(p_match - 0.5) * 2.0  # 1.0 at a coin flip, 0 at a lock
    base = 21.5 if fmt.sets_to_win == 2 else 33.0
    return base + closeness * (3.0 if fmt.sets_to_win == 2 else 5.0)
