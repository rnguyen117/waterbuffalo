"""Tests for prop distributions, ladder pricing, public money, and ranking."""

import math

import pytest

from sharpedge.market.props import (
    PropMarket,
    PropQuote,
    analyze_ladder,
    anchor_probability,
    consensus_distribution,
    derived_ladder,
    find_line_disagreement,
    fit_ladder,
    implied_projection,
    is_playable,
    over_shading,
    prop_hold,
)
from sharpedge.market.public import PublicRead, contrarian_value, darling_score, read
from sharpedge.market.taxonomy import (
    markets_for,
    profile_for,
    props_for,
    softest_markets,
)
from sharpedge.models import MarketType, PublicBetting
from sharpedge.oddsmath import american_to_prob, prob_to_american
from sharpedge.pricing.distributions import (
    GammaDist,
    NegativeBinomialDist,
    NormalDist,
    PoissonDist,
    build,
    fit_to_market,
    model_for,
    push_probability,
    standard_ladder,
)


class TestDistributions:
    def test_poisson_sums_to_one(self):
        d = PoissonDist(mean=4.2)
        assert sum(d.pmf(k) for k in range(0, 40)) == pytest.approx(1.0, abs=1e-9)

    def test_poisson_mean_is_correct(self):
        d = PoissonDist(mean=4.2)
        assert sum(k * d.pmf(k) for k in range(0, 60)) == pytest.approx(4.2, abs=1e-6)

    def test_negbin_sums_to_one(self):
        d = NegativeBinomialDist(mean=6.0, dispersion=1.35)
        assert sum(d.pmf(k) for k in range(0, 80)) == pytest.approx(1.0, abs=1e-6)

    def test_negbin_mean_is_correct(self):
        d = NegativeBinomialDist(mean=6.0, dispersion=1.35)
        assert sum(k * d.pmf(k) for k in range(0, 200)) == pytest.approx(6.0, abs=1e-4)

    def test_negbin_has_fatter_tails_than_poisson(self):
        # The entire reason for using it: Poisson understates the tails, which
        # is where alternate lines live.
        nb = NegativeBinomialDist(mean=6.0, dispersion=1.4)
        po = PoissonDist(mean=6.0)
        assert nb.sf(11.5) > po.sf(11.5)
        assert nb.sf(1.5) < po.sf(1.5)

    def test_negbin_collapses_to_poisson_at_unit_dispersion(self):
        nb = NegativeBinomialDist(mean=5.0, dispersion=1.0)
        po = PoissonDist(mean=5.0)
        assert nb.sf(6.5) == pytest.approx(po.sf(6.5), abs=1e-3)

    def test_survival_is_monotonic(self):
        for dist in (
            PoissonDist(mean=5.0),
            NegativeBinomialDist(mean=5.0),
            NormalDist(mean=20.0, sd=6.0),
            GammaDist(mean=60.0, cv=0.6),
        ):
            values = [dist.sf(x) for x in range(0, 40)]
            assert all(a >= b for a, b in zip(values, values[1:]))

    def test_gamma_never_goes_negative(self):
        d = GammaDist(mean=45.0, cv=0.6)
        assert d.sf(0.0) == pytest.approx(1.0, abs=1e-6)
        assert 0.0 <= d.sf(300.0) < 0.01

    def test_gamma_is_right_skewed(self):
        # Median below the mean is the defining property, and it is why yardage
        # props are not normal.
        d = GammaDist(mean=60.0, cv=0.6)
        assert d.sf(60.0) < 0.5

    def test_normal_is_symmetric(self):
        d = NormalDist(mean=20.0, sd=5.0)
        assert d.sf(20.0) == pytest.approx(0.5, abs=1e-9)

    def test_stat_models_are_registered(self):
        assert model_for("strikeouts").family == "negbin"
        assert model_for("home_runs").family == "poisson"
        assert model_for("receiving_yards").family == "gamma"
        # Unknown stats fall back conservatively rather than crashing.
        assert model_for("nonsense_stat").family == "negbin"

    def test_build_dispatches_by_family(self):
        assert isinstance(build("strikeouts", 6.0), NegativeBinomialDist)
        assert isinstance(build("home_runs", 0.4), PoissonDist)
        assert isinstance(build("receiving_yards", 60.0), GammaDist)


class TestFitting:
    def test_fit_recovers_the_projection(self):
        truth = build("strikeouts", 6.4)
        recovered = fit_to_market("strikeouts", 6.5, truth.sf(6.5))
        assert recovered.mean == pytest.approx(6.4, abs=0.05)

    def test_fit_works_across_the_ladder(self):
        truth = build("strikeouts", 6.4)
        for line in (4.5, 5.5, 7.5, 8.5):
            recovered = fit_to_market("strikeouts", line, truth.sf(line))
            assert recovered.mean == pytest.approx(6.4, abs=0.1)

    def test_fit_handles_continuous_stats(self):
        truth = build("receiving_yards", 62.0)
        recovered = fit_to_market("receiving_yards", 55.5, truth.sf(55.5))
        assert recovered.mean == pytest.approx(62.0, abs=1.0)

    def test_joint_fit_beats_a_single_anchor(self):
        # The joint fit is robust to the devig noise that wrecks a
        # single-point fit, which is the whole reason it exists.
        truth = build("strikeouts", 6.4)
        quotes = [
            PropQuote(
                "pinnacle", line,
                prob_to_american(min(truth.sf(line) * 1.075, 0.97)),
                prob_to_american(min((1 - truth.sf(line)) * 1.075, 0.97)),
            )
            for line in (4.5, 5.5, 6.5, 7.5, 8.5, 9.5)
        ]
        fitted = fit_ladder(quotes, "strikeouts")
        assert fitted is not None
        assert fitted.mean == pytest.approx(6.4, abs=0.25)

    def test_joint_fit_needs_two_points(self):
        assert fit_ladder([PropQuote("dk", 5.5, -110, -110)], "strikeouts") is None

    def test_standard_ladder_steps_correctly(self):
        assert standard_ladder(6.5, "strikeouts", 2) == [4.5, 5.5, 6.5, 7.5, 8.5]
        # Yardage ladders in larger increments.
        assert 10.0 in [
            b - a for a, b in zip(
                standard_ladder(75.5, "receiving_yards", 2),
                standard_ladder(75.5, "receiving_yards", 2)[1:],
            )
        ]

    def test_push_probability_on_whole_numbers(self):
        d = build("strikeouts", 6.0)
        assert push_probability(d, 6.0, "strikeouts") > 0.05
        assert push_probability(d, 6.5, "strikeouts") == 0.0
        # Continuous stats never push.
        assert push_probability(build("receiving_yards", 60.0), 60.0, "receiving_yards") == 0.0


def coherent_ladder(mean=6.4, hold=0.075, books=("pinnacle", "draftkings", "fanduel",
                                                 "betmgm", "caesars", "espnbet"),
                    lines=(4.5, 5.5, 6.5, 7.5, 8.5, 9.5), stat="strikeouts"):
    """A ladder priced correctly from one distribution at every rung."""
    truth = build(stat, mean)
    quotes = []
    for book in books:
        for line in lines:
            p = truth.sf(line)
            quotes.append(
                PropQuote(
                    book, line,
                    prob_to_american(min(max(p * (1 + hold), 0.02), 0.97)),
                    prob_to_american(min(max((1 - p) * (1 + hold), 0.02), 0.97)),
                )
            )
    return PropMarket("Test Player", stat, "mlb", "e1", quotes)


def linear_ladder(mean=6.4, anchor=6.5, slope=0.13):
    """A ladder whose alternates were generated by linear interpolation."""
    truth = build("strikeouts", mean)
    anchor_p = truth.sf(anchor)
    quotes = []
    for book in ("draftkings", "fanduel", "betmgm"):
        for line in (4.5, 5.5, 6.5, 7.5, 8.5, 9.5):
            p = min(max(anchor_p - (line - anchor) * slope, 0.02), 0.98)
            quotes.append(
                PropQuote(
                    book, line,
                    prob_to_american(min(max(p * 1.075, 0.02), 0.97)),
                    prob_to_american(min(max((1 - p) * 1.075, 0.02), 0.97)),
                )
            )
    return PropMarket("Linear Player", "strikeouts", "mlb", "e2", quotes)


class TestLadderAnalysis:
    def test_no_false_positives_on_a_coherent_ladder(self):
        # The single most important test in the prop pipeline. A book that
        # prices its whole ladder from one model must produce zero findings;
        # anything here is bias in our own math masquerading as an edge.
        found = analyze_ladder(coherent_ladder(), min_ev=0.02, correct_over_bias=False)
        assert found == []

    @pytest.mark.parametrize("hold", [0.04, 0.06, 0.08, 0.10, 0.12])
    def test_no_false_positives_at_any_hold(self, hold):
        found = analyze_ladder(
            coherent_ladder(hold=hold), min_ev=0.02, correct_over_bias=False
        )
        assert found == []

    @pytest.mark.parametrize("mean", [2.5, 4.0, 6.4, 9.0])
    def test_no_false_positives_at_any_projection(self, mean):
        # Ladder centered on the projection, as books actually post them.
        lines = tuple(
            round(mean) + offset + 0.5 for offset in (-3, -2, -1, 0, 1, 2)
            if round(mean) + offset + 0.5 > 0
        )
        found = analyze_ladder(
            coherent_ladder(mean=mean, lines=lines),
            min_ev=0.02,
            correct_over_bias=False,
        )
        assert found == []

    def test_extreme_tail_rungs_are_declined(self):
        # A 9.5 line against a 2.5 projection is unpriceable, and betting it
        # would be acting on pure extrapolation.
        found = analyze_ladder(
            coherent_ladder(mean=2.5, lines=(1.5, 2.5, 3.5, 9.5)),
            min_ev=0.02,
            correct_over_bias=False,
        )
        assert all(m.line != 9.5 for m in found)

    def test_catches_a_linearly_generated_ladder(self):
        found = analyze_ladder(linear_ladder(), min_ev=0.02, correct_over_bias=False)
        assert found, "failed to catch alternates generated by interpolation"

    def test_finds_the_tail_where_the_error_is_largest(self):
        found = analyze_ladder(linear_ladder(), min_ev=0.02, correct_over_bias=False)
        # The biggest error is furthest from the anchor.
        assert abs(found[0].line - 6.5) >= 2.0

    def test_a_book_with_too_few_rungs_is_skipped(self):
        prop = PropMarket(
            "Sparse", "strikeouts", "mlb", "e3",
            [PropQuote("dk", 5.5, -110, -110), PropQuote("dk", 6.5, +120, -140)],
        )
        assert analyze_ladder(prop, min_rungs=3) == []

    def test_consensus_distribution_recovers_the_market(self):
        fit = consensus_distribution(coherent_ladder(mean=6.4))
        assert fit is not None
        dist, sigma, n_books = fit
        assert dist.mean == pytest.approx(6.4, abs=0.3)
        assert n_books == 6
        assert sigma > 0

    def test_consensus_needs_enough_quotes(self):
        prop = PropMarket("Thin", "strikeouts", "mlb", "e4",
                          [PropQuote("dk", 5.5, -110, -110)])
        assert consensus_distribution(prop) is None

    def test_implied_projection_is_reported(self):
        assert implied_projection(coherent_ladder(mean=6.4)) == pytest.approx(6.4, abs=0.35)

    def test_derived_ladder_is_monotonic(self):
        ladder = derived_ladder(coherent_ladder())
        lines = sorted(ladder)
        overs = [american_to_prob(ladder[l][0]) for l in lines]
        # Higher lines are harder to go over.
        assert all(a >= b for a, b in zip(overs, overs[1:]))


class TestPropMarketMechanics:
    def test_anchor_is_the_most_posted_line(self):
        quotes = [PropQuote(b, 6.5, -110, -110) for b in ("dk", "fd", "mgm")]
        quotes.append(PropQuote("dk", 8.5, +200, -240))
        assert PropMarket("P", "strikeouts", "mlb", "e", quotes).anchor_line == 6.5

    def test_incomplete_quotes_are_ignored(self):
        q = PropQuote("dk", 6.5, over_american=-110)
        assert not q.complete
        assert q.fair_over() is None

    def test_devig_removes_the_hold(self):
        q = PropQuote("dk", 6.5, -110, -110)
        assert q.fair_over() == pytest.approx(0.5, abs=1e-6)
        assert q.hold() == pytest.approx(0.0455, abs=1e-3)

    def test_playability_rejects_thin_markets(self):
        prop = PropMarket("P", "strikeouts", "mlb", "e",
                          [PropQuote("dk", 6.5, -110, -110)])
        playable, reason = is_playable(prop, min_books=3)
        assert not playable
        assert "books" in reason

    def test_playability_rejects_rich_juice(self):
        prop = coherent_ladder(hold=0.25)
        playable, reason = is_playable(prop, max_hold=0.10)
        assert not playable
        assert "rich" in reason

    def test_line_disagreement_detected(self):
        quotes = [
            PropQuote("dk", 5.5, -110, -110),
            PropQuote("espnbet", 7.5, -110, -110),
        ]
        found = find_line_disagreement(PropMarket("P", "strikeouts", "mlb", "e", quotes))
        assert found is not None
        assert found.gap == pytest.approx(2.0)

    def test_no_disagreement_when_books_agree(self):
        quotes = [PropQuote(b, 6.5, -110, -110) for b in ("dk", "fd")]
        assert find_line_disagreement(PropMarket("P", "strikeouts", "mlb", "e", quotes)) is None

    def test_hold_is_measured(self):
        assert prop_hold(coherent_ladder(hold=0.08)) == pytest.approx(0.074, abs=0.01)


class TestPublicMoney:
    def test_over_shading_scales_with_ticket_share(self):
        # Anytime TD is the most lopsided prop; saves is the least.
        assert over_shading("anytime_td") > over_shading("strikeouts")
        assert over_shading("strikeouts") > over_shading("saves")

    def test_shading_is_always_non_negative(self):
        for stat in ("anytime_td", "points", "saves", "unknown_stat"):
            assert over_shading(stat) >= 0

    def test_prop_over_is_flagged_as_the_public_side(self):
        r = read("Over", MarketType.PLAYER_PROP, None, stat="anytime_td")
        assert r.shading_logit > 0
        assert contrarian_value(r) < 0

    def test_prop_under_is_the_unshaded_side(self):
        r = read("Under", MarketType.PLAYER_PROP, None, stat="anytime_td")
        assert r.shading_logit < 0
        assert contrarian_value(r) > 0

    def test_public_darlings_carry_a_premium(self):
        assert darling_score("Dallas Cowboys") > 0.5
        assert darling_score("Jacksonville Jaguars") == 0.0
        r = read("Dallas Cowboys", MarketType.SPREAD, None)
        assert r.shading_logit > 0

    def test_handle_divergence_flips_the_read(self):
        # Heavy tickets but heavy money too means it is not really the public
        # side, and the read should say so.
        small = PublicBetting("e", MarketType.SPREAD, "Team", 0.75, 0.45)
        big = PublicBetting("e", MarketType.SPREAD, "Team", 0.75, 0.90)
        assert read("Team", MarketType.SPREAD, small).shading_logit > \
               read("Team", MarketType.SPREAD, big).shading_logit

    def test_average_bet_ratio(self):
        r = read("Team", MarketType.SPREAD,
                 PublicBetting("e", MarketType.SPREAD, "Team", 0.30, 0.65))
        assert r.average_bet_ratio > 3.0
        assert "sharp side" in r.verdict

    def test_no_data_is_handled(self):
        r = read("Team", MarketType.SPREAD, None)
        assert r.average_bet_ratio is None
        assert r.verdict == "no public data"


class TestTaxonomy:
    def test_core_markets_are_more_efficient_than_props(self):
        spread = profile_for(MarketType.SPREAD)
        prop = profile_for(MarketType.PLAYER_PROP, "tackles_assists")
        assert spread.efficiency > prop.efficiency
        assert spread.typical_limit > prop.typical_limit

    def test_softer_markets_demand_a_bigger_edge(self):
        spread = profile_for(MarketType.SPREAD)
        prop = profile_for(MarketType.PLAYER_PROP, "nba_steals")
        assert prop.min_edge_required >= spread.min_edge_required

    def test_market_trust_is_bounded(self):
        for mt in MarketType:
            assert 0.25 <= profile_for(mt).market_trust <= 0.90

    def test_unknown_markets_are_handled_conservatively(self):
        profile = profile_for(MarketType.MARGIN_BUCKET)
        assert profile.typical_hold > 0.09

    def test_sports_carry_their_own_menus(self):
        assert MarketType.FIRST_FIVE in markets_for("mlb")
        assert MarketType.FIRST_FIVE not in markets_for("nba")
        assert MarketType.PLAYER_PROP in markets_for("nfl")

    def test_props_are_registered_per_sport(self):
        stats = {p.stat for p in props_for("mlb")}
        assert "strikeouts" in stats
        assert {p.stat for p in props_for("nba")} & {"points", "rebounds", "assists"}

    def test_wnba_has_its_own_menu(self):
        assert MarketType.PLAYER_PROP in markets_for("wnba")
        assert MarketType.TEAM_TOTAL in markets_for("wnba")
        # Thinner real-world coverage than the NBA: no alternates, no quarters.
        assert MarketType.ALTERNATE_SPREAD not in markets_for("wnba")
        assert MarketType.FIRST_QUARTER not in markets_for("wnba")

    def test_wnba_props_are_registered(self):
        stats = {p.stat for p in props_for("wnba")}
        assert {"points", "rebounds", "assists"} <= stats

    def test_shared_stat_names_do_not_collide_across_sports(self):
        # The regression this whole taxonomy exists to prevent: WNBA and NBA
        # both have a "points" prop, and without a sport-aware lookup key,
        # whichever one loads last in the registry silently overwrites the
        # other for every caller in the codebase -- meaning every NBA points
        # prop would quietly inherit the WNBA's tighter limit and thinner
        # trust once WNBA support was added.
        nba = profile_for(MarketType.PLAYER_PROP, "points", sport="nba")
        wnba = profile_for(MarketType.PLAYER_PROP, "points", sport="wnba")
        assert nba.typical_limit != wnba.typical_limit
        assert nba.typical_limit > wnba.typical_limit
        assert nba.efficiency > wnba.efficiency

    def test_wnba_props_are_softer_than_nba(self):
        # Fewer books, fewer sharp bettors, smaller limits -- consistent with
        # every other thin market in the taxonomy.
        for stat in ("points", "rebounds", "assists"):
            nba = profile_for(MarketType.PLAYER_PROP, stat, sport="nba")
            wnba = profile_for(MarketType.PLAYER_PROP, stat, sport="wnba")
            assert wnba.typical_limit < nba.typical_limit
            assert wnba.min_edge_required >= nba.min_edge_required

    def test_softest_markets_are_ranked(self):
        softest = softest_markets(5)
        assert len(softest) == 5
        assert all(
            a.efficiency <= b.efficiency for a, b in zip(softest, softest[1:])
        )


class TestRanking:
    """Ranking, and the probability-versus-value trade-off it encodes."""

    def _bets(self):
        from datetime import datetime, timedelta, timezone

        from sharpedge.models import BetCandidate, Confidence, Event, FairPrice, MarketType

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        out = []
        # (probability, price, books) -- a heavy favorite, a coin flip, a dog.
        specs = [
            ("chalk", 0.94, -1200, 10),
            ("coinflip", 0.56, -110, 10),
            ("dog", 0.24, +420, 4),
        ]
        for i, (name, prob, price, books) in enumerate(specs):
            event = Event(
                event_id=f"e{i}", sport="nfl", league="NFL",
                home_team=f"H{i}", away_team=f"A{i}",
                start_time=now + timedelta(hours=5),
            )
            out.append(
                BetCandidate(
                    event=event,
                    market_type=MarketType.SPREAD,
                    outcome=name,
                    book="draftkings",
                    american=price,
                    line=-3.0,
                    fair=FairPrice(name, prob, 0.05, books, 2),
                    model_probability=prob,
                    confidence=Confidence.B,
                    kelly_fraction=0.01,
                    conservative_probability=prob - 0.01,
                )
            )
        return out

    def test_probability_mode_picks_the_favorite(self):
        from sharpedge.ranking import RankMode, rank

        ranked = rank(self._bets(), mode=RankMode.PROBABILITY, top_n=3)
        assert ranked[0].bet.outcome == "chalk"

    def test_value_mode_penalizes_heavy_chalk(self):
        # The point of the composite: a 94% favorite at -1200 should not lead
        # a card just because it wins most often.
        from sharpedge.ranking import RankMode, rank

        ranked = rank(self._bets(), mode=RankMode.VALUE, top_n=3)
        assert ranked[0].bet.outcome != "chalk"

    def test_min_probability_filters(self):
        from sharpedge.ranking import RankMode, rank

        ranked = rank(self._bets(), mode=RankMode.VALUE, top_n=3, min_probability=0.5)
        assert all(s.hit_probability >= 0.5 for s in ranked)

    def test_card_size_is_respected(self):
        from sharpedge.ranking import rank

        assert len(rank(self._bets(), top_n=2)) == 2

    def test_max_per_game_limits_concentration(self):
        from datetime import datetime, timedelta, timezone

        from sharpedge.models import BetCandidate, Confidence, Event, FairPrice, MarketType
        from sharpedge.ranking import rank

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        event = Event(
            event_id="same", sport="nfl", league="NFL", home_team="H", away_team="A",
            start_time=now + timedelta(hours=5),
        )
        bets = [
            BetCandidate(
                event=event, market_type=mt, outcome=f"o{i}", book="dk",
                american=-110, line=-3.0,
                fair=FairPrice(f"o{i}", 0.56, 0.05, 8, 2),
                model_probability=0.56, confidence=Confidence.B,
                kelly_fraction=0.01, conservative_probability=0.55,
            )
            for i, mt in enumerate(
                [MarketType.SPREAD, MarketType.TOTAL, MarketType.MONEYLINE,
                 MarketType.TEAM_TOTAL]
            )
        ]
        ranked = rank(bets, top_n=4, max_per_game=2, diversify=True)
        # Backfill may top the card up, but the flag records that it happened.
        capped = [s for s in ranked if "backfilled" not in s.components]
        assert len(capped) <= 2

    def test_expected_record_matches_the_probabilities(self):
        from sharpedge.ranking import expected_record, rank

        ranked = rank(self._bets(), top_n=3)
        wins, losses = expected_record(ranked)
        assert wins + losses == pytest.approx(3.0)
        assert wins == pytest.approx(sum(s.hit_probability for s in ranked))

    def test_poisson_binomial_is_a_distribution(self):
        from sharpedge.ranking import probability_of_winning_at_least, rank

        ranked = rank(self._bets(), top_n=3)
        # P(at least 0) is certain; the sequence must be non-increasing.
        assert probability_of_winning_at_least(ranked, 0) == pytest.approx(1.0)
        values = [probability_of_winning_at_least(ranked, k) for k in range(4)]
        assert all(a >= b for a, b in zip(values, values[1:]))

    def test_summary_reports_the_market_mix(self):
        from sharpedge.ranking import rank, summarize_card

        stats = summarize_card(rank(self._bets(), top_n=3))
        assert stats["count"] == 3
        assert stats["markets"]["spread"] == 3
        assert 0 <= stats["mean_probability"] <= 1

    def test_empty_card_summarizes_safely(self):
        from sharpedge.ranking import summarize_card

        assert summarize_card([])["count"] == 0
