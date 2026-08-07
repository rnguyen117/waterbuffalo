"""Command line interface.

    sharp-edge card                 build today's card
    sharp-edge card --json out.json write it somewhere
    sharp-edge init                 write a starter config
    sharp-edge clv                  how you are doing against the close
    sharp-edge calibrate            are the probabilities honest
    sharp-edge simulate             what a day or a season looks like
    sharp-edge devig -110 -110      inspect a market's true prices
    sharp-edge kelly ...            size a single bet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config as config_module
from . import pipeline, report
from .market.movement import LineHistory
from .models import BetStatus
from .oddsmath import american_to_prob, devig, hold, prob_to_american, shin_z


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sharp-edge",
        description="Sports betting expected-value engine.",
    )
    parser.add_argument("-c", "--config", help="path to a TOML config file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_card = sub.add_parser("card", help="build today's card")
    p_card.add_argument("--json", help="write the card as JSON to this path")
    p_card.add_argument("--markdown", help="write the card as Markdown to this path")
    p_card.add_argument("-v", "--verbose", action="store_true")
    p_card.add_argument("--log", action="store_true", help="record the bets in the ledger")
    p_card.add_argument("--bankroll", type=float, help="override the configured bankroll")
    p_card.add_argument(
        "--unit-size", type=float,
        help="dollar value of one unit, for display (default: 1%% of bankroll)",
    )
    p_card.add_argument(
        "--kelly-multiplier", type=float,
        help="override the configured fraction of full Kelly (e.g. 0.25)",
    )
    p_card.add_argument("--top", type=int, help="how many bets the card should contain (default 10)")
    p_card.add_argument(
        "--rank",
        choices=["value", "probability", "edge", "confidence", "kelly"],
        help="ranking mode. 'value' (default) balances edge, hit rate, evidence "
             "and verifiability; 'probability' sorts by raw win probability, which "
             "selects heavy favorites at poor prices -- see docs/METHODOLOGY.md",
    )
    p_card.add_argument(
        "--min-probability", type=float,
        help="only include bets winning at least this often (e.g. 0.5)",
    )
    p_card.add_argument("--no-props", action="store_true", help="skip player props")
    p_card.add_argument("--props-only", action="store_true", help="player props only")

    sub.add_parser("init", help="write a starter config file").add_argument(
        "path", nargs="?", default="sharp-edge.toml"
    )

    sub.add_parser("clv", help="closing line value report")
    sub.add_parser("calibrate", help="check whether the probabilities are honest")
    p_summary = sub.add_parser("summary", help="ledger performance summary")
    p_summary.add_argument("--json", help="write the scorecard as JSON to this path")

    p_sim = sub.add_parser("simulate", help="simulate a season at a given edge")
    p_sim.add_argument("--edge", type=float, default=0.02)
    p_sim.add_argument("--bets-per-day", type=int, default=3)
    p_sim.add_argument("--days", type=int, default=180)
    p_sim.add_argument("--kelly", type=float, default=0.01)

    p_devig = sub.add_parser("devig", help="remove vig from a set of prices")
    p_devig.add_argument("prices", nargs="+", type=float, help="American odds")

    p_kelly = sub.add_parser("kelly", help="size a single bet")
    p_kelly.add_argument("probability", type=float, help="your win probability, 0-1")
    p_kelly.add_argument("american", type=float, help="the price offered")
    p_kelly.add_argument("--bankroll", type=float, default=10_000.0)
    p_kelly.add_argument("--multiplier", type=float, default=0.25)
    p_kelly.add_argument(
        "--unit-size", type=float,
        help="dollar value of one unit, for display (default: 1%% of bankroll)",
    )

    p_ladder = sub.add_parser(
        "ladder", help="derive a full alternate-line ladder from one price"
    )
    p_ladder.add_argument("stat", help="e.g. strikeouts, points, receiving_yards")
    p_ladder.add_argument("line", type=float, help="the posted line")
    p_ladder.add_argument("over", type=float, help="over price, American")
    p_ladder.add_argument("under", type=float, help="under price, American")

    p_settle = sub.add_parser("settle", help="grade a bet in the ledger")
    p_settle.add_argument("bet_id", type=int)
    p_settle.add_argument("result", choices=["won", "lost", "pushed", "voided"])
    p_settle.add_argument("--closing", type=float, help="closing American odds, for CLV")

    args = parser.parse_args(argv)

    try:
        cfg = config_module.load(args.config) if args.config else config_module.Config()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    handlers = {
        "card": _cmd_card,
        "init": _cmd_init,
        "clv": _cmd_clv,
        "calibrate": _cmd_calibrate,
        "summary": _cmd_summary,
        "simulate": _cmd_simulate,
        "devig": _cmd_devig,
        "kelly": _cmd_kelly,
        "ladder": _cmd_ladder,
        "settle": _cmd_settle,
    }
    return handlers[args.command](args, cfg)


# ---------------------------------------------------------------------------


def _cmd_card(args, cfg) -> int:
    if args.bankroll:
        cfg.bankroll.starting = args.bankroll
    if args.unit_size:
        cfg.bankroll.unit_size = args.unit_size
    if args.kelly_multiplier is not None:
        cfg.bankroll.kelly_multiplier = args.kelly_multiplier
    if args.top:
        cfg.filters.card_size = args.top
    if args.rank:
        cfg.filters.rank_mode = args.rank
    if args.min_probability is not None:
        cfg.filters.min_probability = args.min_probability
    if args.no_props:
        cfg.filters.include_props = False
    if args.props_only:
        cfg.filters.exclude_markets = [
            m.value for m in __import__(
                "sharpedge.models", fromlist=["MarketType"]
            ).MarketType if not m.is_prop
        ]

    try:
        inputs = pipeline.fetch_inputs(cfg)
    except Exception as exc:
        print(f"error fetching data: {exc}", file=sys.stderr)
        return 1

    unit = cfg.bankroll.effective_unit_size
    from .track.ledger import Ledger

    ledger = Ledger(Path(cfg.data_dir) / "bets.db")
    try:
        scorecard = ledger.scorecard()
        daily_pnl = ledger.daily_pnl_units(unit)
    finally:
        ledger.close()

    goal_state = None
    if cfg.goals.enabled:
        from .risk.goals import state_from_history

        goal_state = state_from_history(
            daily_pnl, cfg.goals.daily_goal_units, cfg.goals.min_risk_multiplier
        )
        cfg.bankroll.kelly_multiplier *= goal_state.risk_multiplier
        if goal_state.risk_multiplier < 0.999:
            print(
                f"Goal tracking: {goal_state.banked_surplus:.2f}u banked, "
                f"sizing at {goal_state.risk_multiplier:.0%} of normal "
                f"({goal_state.effective_goal:.2f}u still needed today)\n"
            )

    history = LineHistory(Path(cfg.data_dir) / "lines.db")
    try:
        result = pipeline.run(inputs, cfg, history=history)
    finally:
        history.close()

    result.card_stats = dict(result.card_stats or {})
    result.card_stats["scorecard"] = scorecard
    if goal_state is not None:
        result.card_stats["goal"] = {
            "daily_goal_units": cfg.goals.daily_goal_units,
            "banked_surplus_units": round(goal_state.banked_surplus, 4),
            "effective_goal_units": round(goal_state.effective_goal, 4),
            "progress_fraction": round(goal_state.progress_fraction, 4),
            "risk_multiplier": round(goal_state.risk_multiplier, 4),
        }

    print(report.console(result, verbose=args.verbose, unit_size=unit))

    if args.json:
        Path(args.json).write_text(report.to_json(result, unit_size=unit))
        print(f"\nwrote JSON to {args.json}")
    if args.markdown:
        Path(args.markdown).write_text(report.markdown(result, unit_size=unit))
        print(f"wrote Markdown to {args.markdown}")

    if args.log and result.bets:
        from .track.ledger import Ledger

        ledger = Ledger(Path(cfg.data_dir) / "bets.db")
        ids = ledger.record_slate(result.bets)
        ledger.close()
        print(f"logged {len(ids)} bets to the ledger (ids {ids[0]}-{ids[-1]})")

    return 0


def _cmd_init(args, cfg) -> int:
    path = config_module.write_default(args.path)
    print(f"wrote {path}")
    print("Edit it, then run: sharp-edge -c", path, "card")
    return 0


def _cmd_clv(args, cfg) -> int:
    from .track import clv as clv_module
    from .track.ledger import Ledger

    ledger = Ledger(Path(cfg.data_dir) / "bets.db")
    try:
        rep = clv_module.analyze(ledger)
        summary = ledger.summary()
    finally:
        ledger.close()

    print(rep.summary)
    if rep.n:
        print(f"Projected long-run ROI from this CLV: {rep.projected_roi:+.2%}")
        print()
        print(clv_module.diagnose(rep, summary["roi"]))
        if rep.by_book:
            print("\nBy book:")
            for book, value in sorted(rep.by_book.items(), key=lambda kv: -kv[1]):
                print(f"  {book:<14} {value:+.2%}")
    return 0


def _cmd_calibrate(args, cfg) -> int:
    from .track import calibration
    from .track.ledger import Ledger

    ledger = Ledger(Path(cfg.data_dir) / "bets.db")
    try:
        rows = [r for r in ledger.settled() if r.status in ("won", "lost")]
    finally:
        ledger.close()

    if not rows:
        print("No settled bets yet. Grade some bets first with `sharp-edge settle`.")
        return 0

    predictions = [r.model_probability for r in rows]
    outcomes = [1 if r.status == "won" else 0 for r in rows]
    rep = calibration.analyze(predictions, outcomes)

    print(f"{rep.n} settled bets")
    print(f"Brier score       {rep.brier:.4f}   (0.25 = no skill)")
    print(f"Log loss          {rep.log_loss:.4f}")
    print(f"Calibration error {rep.expected_calibration_error:.4f}")
    print(f"Overconfidence    {rep.overconfidence:.2f}x")
    print(f"\n{rep.verdict}")

    if rep.bins:
        print("\nPredicted vs actual:")
        for b in rep.bins:
            print(f"  {b.label:<10} n={b.count:<5} predicted {b.predicted:.1%}  actual {b.actual:.1%}")

    suggested = calibration.suggested_market_trust(rep, cfg.model.market_trust)
    if abs(suggested - cfg.model.market_trust) > 0.01:
        print(f"\nSuggested market_trust: {suggested:.2f} (currently {cfg.model.market_trust:.2f})")
    return 0


def _cmd_summary(args, cfg) -> int:
    import json

    from .risk.goals import state_from_history
    from .track.ledger import Ledger

    unit = cfg.bankroll.effective_unit_size
    ledger = Ledger(Path(cfg.data_dir) / "bets.db")
    try:
        s = ledger.summary()
        by_book = ledger.by_dimension("book")
        scorecard = ledger.scorecard()
        daily_pnl = ledger.daily_pnl_units(unit)
    finally:
        ledger.close()

    goal_state = None
    if cfg.goals.enabled and daily_pnl:
        goal_state = state_from_history(
            daily_pnl, cfg.goals.daily_goal_units, cfg.goals.min_risk_multiplier
        )

    if args.json:
        payload = {
            "summary": s,
            "scorecard": scorecard,
            "by_book": by_book,
            "daily_pnl_units": daily_pnl,
            "goal": (
                {
                    "daily_goal_units": cfg.goals.daily_goal_units,
                    "banked_surplus_units": round(goal_state.banked_surplus, 4),
                    "effective_goal_units": round(goal_state.effective_goal, 4),
                    "progress_fraction": round(goal_state.progress_fraction, 4),
                    "risk_multiplier": round(goal_state.risk_multiplier, 4),
                }
                if goal_state is not None
                else None
            ),
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"wrote scorecard JSON to {args.json}")

    if not s["bets"]:
        print("No settled bets yet.")
        return 0

    print(f"Record     {scorecard['wins']}-{scorecard['losses']}  ({scorecard['win_rate']:.1%})")
    print(f"Bets       {s['bets']:,}")
    print(f"Staked     ${s['staked']:,.2f}")
    print(f"Profit     ${s['profit']:,.2f}")
    print(f"ROI        {s['roi']:+.2%}")
    print(f"Expected   ${s['expected_profit']:,.2f}   (what the model projected)")
    if s["clv_mean"] is not None:
        print(f"CLV        {s['clv_mean']:+.2%}, beat the close {s['beat_close_rate']:.0%} of the time")

    if goal_state is not None:
        print(
            f"\nGoal       {cfg.goals.daily_goal_units:g}u/day  |  "
            f"{goal_state.banked_surplus:.2f}u banked  |  "
            f"{goal_state.progress_fraction:.0%} of goal covered  |  "
            f"next sizing at {goal_state.risk_multiplier:.0%}"
        )

    if by_book:
        print("\nBy book:")
        for book, stats in sorted(by_book.items(), key=lambda kv: -kv[1]["profit"]):
            print(
                f"  {book:<14} {stats['bets']:>4} bets  "
                f"${stats['profit']:>9,.2f}  {stats['roi']:+.2%}"
            )
    return 0


def _cmd_simulate(args, cfg) -> int:
    from .backtest import simulate

    result = simulate.simulate_season(
        edge=args.edge,
        bets_per_day=args.bets_per_day,
        days=args.days,
        bankroll=cfg.bankroll.starting,
        kelly_fraction=args.kelly,
    )
    print(
        f"Simulating {args.days} days, {args.bets_per_day} bets/day, "
        f"{args.edge:.1%} edge, {args.kelly:.1%} of bankroll per bet:"
    )
    print()
    print(result.summary(cfg.bankroll.starting))
    print()
    ruin = simulate.risk_of_drawdown(
        args.edge, args.days * args.bets_per_day, args.kelly, threshold=0.20
    )
    print(f"Chance of seeing a 20% drawdown along the way: {ruin:.0%}")
    print(
        "\nA genuinely profitable approach still finishes negative a meaningful "
        "share of the time. Size for the bad path, not the median one."
    )
    return 0


def _cmd_devig(args, cfg) -> int:
    raw = [american_to_prob(a) for a in args.prices]
    print(f"Raw implied:  {' '.join(f'{p:.4f}' for p in raw)}")
    print(f"Overround:    {sum(raw) - 1:.4f}")
    print(f"Hold:         {hold(raw):.3%}")
    print(f"Shin z:       {shin_z(raw):.4f}   (implied insider share)")
    print()
    for method in ("multiplicative", "additive", "power", "shin"):
        fair = devig(raw, method=method)
        prices = "  ".join(f"{prob_to_american(p):+7.0f}" for p in fair)
        probs = "  ".join(f"{p:.4f}" for p in fair)
        print(f"  {method:<16} {probs}   ->  {prices}")
    print()
    print("Where the methods disagree most is where a naive screen invents edges.")
    return 0


def _cmd_kelly(args, cfg) -> int:
    from .pricing.ev import expected_value, break_even_probability
    from .pricing.kelly import kelly_fraction, risk_of_ruin

    p, a = args.probability, args.american
    if not 0 < p < 1:
        print("probability must be between 0 and 1", file=sys.stderr)
        return 1

    full = kelly_fraction(p, a)
    fractional = full * args.multiplier
    ev = expected_value(p, a)
    unit = args.unit_size if args.unit_size else args.bankroll / 100.0

    print(f"Price {a:+.0f}  |  break-even {break_even_probability(a):.2%}  |  your {p:.2%}")
    print(f"Edge          {p - break_even_probability(a):+.2%}")
    print(f"EV            {ev:+.2%} per unit staked")
    if full <= 0:
        print("\nNo edge here. Kelly says do not bet.")
        return 0
    full_stake = args.bankroll * full
    frac_stake = args.bankroll * fractional
    print(f"Full Kelly    {full:.2%} of bankroll  (${full_stake:,.0f}, {full_stake / unit:.2f}u)")
    print(
        f"At {args.multiplier:g}x       {fractional:.2%} of bankroll  "
        f"(${frac_stake:,.0f}, {frac_stake / unit:.2f}u)   <- use this"
    )
    print(f"\nRisk of a 50% drawdown at full Kelly: {risk_of_ruin(p, full):.1%}")
    print(f"                       at {args.multiplier:g} Kelly: {risk_of_ruin(p, fractional):.1%}")
    return 0


def _cmd_ladder(args, cfg) -> int:
    from .market.props import over_shading
    from .oddsmath import devig
    from .pricing.distributions import fit_to_market, model_for, standard_ladder

    raw = [american_to_prob(args.over), american_to_prob(args.under)]
    fair = devig(raw, method=cfg.model.devig_method)
    dist = fit_to_market(args.stat, args.line, fair[0])
    model = model_for(args.stat)

    print(f"{args.stat.replace('_', ' ')} {args.line:g}: {args.over:+.0f} / {args.under:+.0f}")
    print(f"Hold          {hold(raw):.2%}")
    print(f"Fair over     {fair[0]:.4f}  ({prob_to_american(fair[0]):+.0f})")
    print(f"Distribution  {model.family}" + (f", dispersion {model.parameter}" if model.family == "negbin" else ""))
    print(f"Implied projection: {dist.mean:.2f}")
    print()
    print("  line      fair over     fair under")
    for candidate in standard_ladder(args.line, args.stat):
        p = dist.sf(candidate)
        if not 0.02 < p < 0.98:
            continue
        marker = "  <- posted" if abs(candidate - args.line) < 1e-9 else ""
        print(f"  {candidate:>6g}   {prob_to_american(p):>+8.0f}      {prob_to_american(1-p):>+8.0f}{marker}")
    print()
    print(
        "Compare these against the book's own alternates. Where they disagree, "
        "the book disagrees with itself."
    )
    shading = over_shading(args.stat)
    if shading > 0.01:
        print(
            f"Note: overs on this stat carry roughly {shading:.3f} log-odds of "
            "public shading, so the honest over price is a little worse than shown."
        )
    return 0


def _cmd_settle(args, cfg) -> int:
    from .track.ledger import Ledger

    ledger = Ledger(Path(cfg.data_dir) / "bets.db")
    try:
        profit = ledger.settle(args.bet_id, BetStatus(args.result), args.closing)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        ledger.close()

    print(f"bet {args.bet_id} settled {args.result}: {profit:+,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
