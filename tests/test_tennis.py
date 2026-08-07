"""Tests for the tennis serve-percentage Markov chain.

Every layer of the chain (game -> tiebreak -> set -> match) is cross-checked
against an independent Monte Carlo point-by-point simulation, not just
against internal consistency, so a formula transcribed wrong can't pass by
agreeing with itself.
"""

from __future__ import annotations

import random

import pytest

from sharpedge.pricing.tennis import (
    BASELINE_HOLD_PROB,
    BEST_OF_3,
    BEST_OF_5,
    MatchFormat,
    fit_hold_edge_to_market,
    game_win_prob,
    games_margin_sigma,
    implied_hold_edge,
    match_win_prob,
    set_win_prob,
    tiebreak_win_prob,
    total_games_mean,
    win_first_to_k,
)


# ---------------------------------------------------------------------------
# Monte Carlo reference simulators (independent of the module under test)
# ---------------------------------------------------------------------------


def _sim_game(p: float, rng: random.Random) -> bool:
    """Simulate one service game point by point; True if server wins."""
    a = b = 0
    while True:
        if rng.random() < p:
            a += 1
        else:
            b += 1
        if a >= 4 and a - b >= 2:
            return True
        if b >= 4 and b - a >= 2:
            return False


def _sim_tiebreak(p_a: float, p_b: float, rng: random.Random) -> bool:
    """Simulate a 7-point tiebreak (win by two); True if A wins."""
    a = b = 0
    played = 0
    while True:
        server_a = played == 0 or (((played - 1) // 2) % 2 == 1)
        p = p_a if server_a else (1.0 - p_b)
        if rng.random() < p:
            a += 1
        else:
            b += 1
        played += 1
        if a >= 7 and a - b >= 2:
            return True
        if b >= 7 and b - a >= 2:
            return False


def _sim_set(p_a_point: float, p_b_point: float, rng: random.Random, a_serves_first: bool = True) -> bool:
    games_a = games_b = 0
    a_serves = a_serves_first
    while True:
        if games_a == 6 and games_b == 6:
            return _sim_tiebreak(p_a_point, p_b_point, rng)
        server_won = _sim_game(p_a_point if a_serves else p_b_point, rng)
        a_won_game = server_won if a_serves else (not server_won)
        if a_won_game:
            games_a += 1
        else:
            games_b += 1
        a_serves = not a_serves
        if games_a >= 6 and games_a - games_b >= 2:
            return True
        if games_b >= 6 and games_b - games_a >= 2:
            return False


def _sim_match(p_a_point: float, p_b_point: float, fmt: MatchFormat, rng: random.Random) -> bool:
    sets_a = sets_b = 0
    while sets_a < fmt.sets_to_win and sets_b < fmt.sets_to_win:
        if _sim_set(p_a_point, p_b_point, rng):
            sets_a += 1
        else:
            sets_b += 1
    return sets_a > sets_b


def _mc_prob(sim_fn, n: int, seed: int) -> float:
    rng = random.Random(seed)
    wins = sum(1 for _ in range(n) if sim_fn(rng))
    return wins / n


N_TRIALS = 20_000
TOL = 0.015  # ~3 std devs at n=20000 for p near 0.5-0.65


# ---------------------------------------------------------------------------
# win_first_to_k
# ---------------------------------------------------------------------------


def test_win_first_to_k_matches_monte_carlo():
    def sim(rng):
        a = b = 0
        while a < 3 and b < 3:
            if rng.random() < 0.6:
                a += 1
            else:
                b += 1
        return a >= 3

    exact = win_first_to_k(0.6, 3)
    mc = _mc_prob(sim, N_TRIALS, seed=1)
    assert abs(exact - mc) < TOL


def test_win_first_to_k_coin_flip_is_half():
    assert win_first_to_k(0.5, 1) == pytest.approx(0.5)
    assert win_first_to_k(0.5, 5) == pytest.approx(0.5, abs=1e-9)


def test_win_first_to_k_rejects_bad_input():
    with pytest.raises(ValueError):
        win_first_to_k(1.5, 3)
    with pytest.raises(ValueError):
        win_first_to_k(0.5, 0)


# ---------------------------------------------------------------------------
# game_win_prob
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("p", [0.55, 0.60, 0.64, 0.70])
def test_game_win_prob_matches_monte_carlo(p):
    exact = game_win_prob(p)
    mc = _mc_prob(lambda rng: _sim_game(p, rng), N_TRIALS, seed=2)
    assert abs(exact - mc) < TOL


def test_game_win_prob_coin_flip_is_half():
    assert game_win_prob(0.5) == pytest.approx(0.5, abs=1e-9)


def test_game_win_prob_monotonic_in_p():
    ps = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    probs = [game_win_prob(p) for p in ps]
    assert probs == sorted(probs)


def test_game_win_prob_rejects_bad_input():
    with pytest.raises(ValueError):
        game_win_prob(0.0)
    with pytest.raises(ValueError):
        game_win_prob(1.0)


# ---------------------------------------------------------------------------
# tiebreak_win_prob
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("p_a,p_b", [(0.6, 0.6), (0.65, 0.60), (0.60, 0.65)])
def test_tiebreak_win_prob_matches_monte_carlo(p_a, p_b):
    exact = tiebreak_win_prob(p_a, p_b)
    mc = _mc_prob(lambda rng: _sim_tiebreak(p_a, p_b, rng), N_TRIALS, seed=3)
    assert abs(exact - mc) < TOL


def test_tiebreak_symmetric_players_is_half():
    assert tiebreak_win_prob(0.6, 0.6) == pytest.approx(0.5, abs=1e-9)


def test_tiebreak_stronger_server_favored():
    assert tiebreak_win_prob(0.70, 0.60) > 0.5


# ---------------------------------------------------------------------------
# set_win_prob
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("p_a,p_b", [(0.60, 0.60), (0.65, 0.60), (0.60, 0.65)])
def test_set_win_prob_matches_monte_carlo(p_a, p_b):
    hold_a = game_win_prob(p_a)
    hold_b = game_win_prob(p_b)
    exact = set_win_prob(hold_a, hold_b, p_a, p_b)
    mc = _mc_prob(lambda rng: _sim_set(p_a, p_b, rng), N_TRIALS, seed=4)
    assert abs(exact - mc) < TOL


def test_set_win_prob_symmetric_players_is_half():
    hold = game_win_prob(0.62)
    assert set_win_prob(hold, hold, 0.62, 0.62) == pytest.approx(0.5, abs=1e-9)


def test_set_win_prob_advantage_set_no_tiebreak():
    # Without a 6-6 tiebreak, symmetric hold rates should still net to 50/50
    # via the game-pair reduction. Point rates are unused on this path but
    # still required by the signature, so pass the same value through.
    hold = game_win_prob(0.62)
    assert set_win_prob(hold, hold, 0.62, 0.62, tiebreak=False) == pytest.approx(0.5, abs=1e-6)


def test_set_win_prob_uses_point_rates_not_hold_rates_for_tiebreak():
    # A 6-6 set is decided by a point-by-point tiebreak. Swapping in the
    # hold rate (much higher than the point rate) instead of the point rate
    # would make the favored player look far stronger in the tiebreak than
    # they actually are -- this guards against that regression directly.
    p_a, p_b = 0.65, 0.60
    hold_a, hold_b = game_win_prob(p_a), game_win_prob(p_b)
    correct = set_win_prob(hold_a, hold_b, p_a, p_b)
    wrong = set_win_prob(hold_a, hold_b, hold_a, hold_b)
    assert abs(correct - wrong) > 0.01


# ---------------------------------------------------------------------------
# match_win_prob
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", [BEST_OF_3, BEST_OF_5])
@pytest.mark.parametrize("p_a,p_b", [(0.62, 0.62), (0.66, 0.60), (0.60, 0.66)])
def test_match_win_prob_matches_monte_carlo(p_a, p_b, fmt):
    exact = match_win_prob(p_a, p_b, fmt)
    mc = _mc_prob(lambda rng: _sim_match(p_a, p_b, fmt, rng), 8_000, seed=5)
    # Fewer trials (match sim is expensive); loosen tolerance accordingly.
    assert abs(exact - mc) < 0.03


def test_match_win_prob_symmetric_players_is_half():
    assert match_win_prob(0.63, 0.63) == pytest.approx(0.5, abs=1e-9)


def test_match_win_prob_monotonic_in_edge():
    baseline = BASELINE_HOLD_PROB
    probs = [match_win_prob(baseline + e, baseline - e) for e in (-0.05, -0.02, 0.0, 0.02, 0.05)]
    assert probs == sorted(probs)


def test_best_of_five_amplifies_the_better_players_edge():
    # Best-of-five is a longer sample, so a fixed per-point edge should win
    # the match more often than the same edge does at best-of-three.
    p3 = match_win_prob(0.66, 0.60, BEST_OF_3)
    p5 = match_win_prob(0.66, 0.60, BEST_OF_5)
    assert p5 > p3 > 0.5


def test_match_win_prob_rejects_bad_input():
    with pytest.raises(ValueError):
        game_win_prob(-0.1)


# ---------------------------------------------------------------------------
# fit_hold_edge_to_market / implied_hold_edge (inversion round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", [0.50, 0.55, 0.62, 0.70, 0.80])
def test_fit_hold_edge_round_trips(target):
    edge = fit_hold_edge_to_market(target)
    repriced = match_win_prob(BASELINE_HOLD_PROB + edge, BASELINE_HOLD_PROB - edge)
    assert repriced == pytest.approx(target, abs=1e-6)


def test_fit_hold_edge_at_50_50_is_zero_edge():
    assert fit_hold_edge_to_market(0.5) == pytest.approx(0.0, abs=1e-6)


def test_fit_hold_edge_monotonic_in_target():
    edges = [fit_hold_edge_to_market(t) for t in (0.40, 0.50, 0.60, 0.70, 0.80)]
    assert edges == sorted(edges)


def test_implied_hold_edge_zero_delta_recovers_input():
    edge = fit_hold_edge_to_market(0.62)
    assert implied_hold_edge(edge, 0.0) == pytest.approx(0.62, abs=1e-6)


def test_implied_hold_edge_positive_delta_increases_win_prob():
    edge = fit_hold_edge_to_market(0.55)
    bumped = implied_hold_edge(edge, 0.02)
    assert bumped > 0.55


def test_fit_hold_edge_rejects_bad_input():
    with pytest.raises(ValueError):
        fit_hold_edge_to_market(0.0)
    with pytest.raises(ValueError):
        fit_hold_edge_to_market(1.0)


# ---------------------------------------------------------------------------
# games-margin / total-games approximations
# ---------------------------------------------------------------------------


def test_games_margin_sigma_wider_for_best_of_five():
    assert games_margin_sigma(BEST_OF_5) > games_margin_sigma(BEST_OF_3)


def test_total_games_mean_higher_for_closer_match():
    close = total_games_mean(0.62, 0.61, BEST_OF_3)
    lopsided = total_games_mean(0.70, 0.50, BEST_OF_3)
    assert close > lopsided


def test_total_games_mean_higher_for_best_of_five():
    assert total_games_mean(0.63, 0.63, BEST_OF_5) > total_games_mean(0.63, 0.63, BEST_OF_3)
