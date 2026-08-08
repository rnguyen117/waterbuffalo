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


def _near_miss_desc(nm) -> str:
    subject = f"{nm.subject} " if nm.subject else ""
    stat = f"{nm.stat.replace('_', ' ')} " if nm.stat else ""
    line = f" {nm.line:g}" if nm.line is not None else ""
    return f"{subject}{stat}{nm.outcome}{line} ({nm.american:+.0f})"


def console(result: SlateResult, verbose: bool = False, unit_size: float | None = None) -> str:
    """Human-readable card for a terminal.

    ``unit_size`` is the dollar value of one betting unit, purely for
    display -- stakes are always Kelly-correct dollar amounts against the
    bankroll, shown alongside their unit equivalent because that is how
    bettors actually track a card. Defaults to 1% of the bankroll, the
    standard convention, when not given.
    """
    unit = unit_size if unit_size else result.bankroll / 100.0
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add(f"  DAILY CARD  -  {result.generated_at:%Y-%m-%d %H:%M UTC}")
    add("=" * 78)
    add(
        f"  Bankroll ${result.bankroll:,.0f}   |   1 unit = ${unit:,.2f}   |   "
        f"{result.considered:,} prices screened"
    )

    if not result.bets:
        add("")
        add("  No bets today.")
        add("")
        add("  This is a normal and frequent outcome. Nothing in the slate cleared")
        add("  the expected-value floor once uncertainty and vig were accounted for.")
        add("  Forcing a bet on a day like this is how edges get given back.")
        if result.near_misses:
            add("")
            add("  Closest misses (not bets -- none of these cleared the floor):")
            for nm in result.near_misses[:8]:
                add(
                    f"    - {nm.event} [{nm.league}] {_near_miss_desc(nm)}: "
                    f"{nm.ev:+.2%} EV, {nm.shortfall:.2%} short of the "
                    f"{nm.min_ev:.2%} floor"
                )
        if result.skipped and verbose:
            add("")
            add("  Skipped:")
            for name, reason in result.skipped[:12]:
                add(f"    - {name}: {reason}")
        add("=" * 78)
        return "\n".join(lines)

    add(
        f"  {len(result.bets)} bets   |   ${result.total_stake:,.0f} "
        f"({result.total_stake / unit:.1f}u) at risk "
        f"({result.total_stake / result.bankroll:.1%} of bankroll)"
    )
    add(
        f"  Expected profit ${result.expected_profit:,.2f} "
        f"({result.expected_roi:+.2%} on turnover)"
    )

    stats = result.card_stats or {}
    if stats:
        record = stats.get("expected_record")
        if record:
            wins, losses = record
            add(
                f"  Expected record {wins:.1f}-{losses:.1f}   |   "
                f"average win probability {stats.get('mean_probability', 0):.1%}"
            )
        mix = stats.get("markets") or {}
        if mix:
            pretty = ", ".join(
                f"{count} {name.replace('_', ' ')}"
                for name, count in sorted(mix.items(), key=lambda kv: -kv[1])
            )
            add(f"  Market mix: {pretty}")
        backfilled = stats.get("backfilled") or 0
        if backfilled:
            add(
                f"  NOTE: {backfilled} of these were added by relaxing the "
                "diversification caps to reach the requested card size."
            )
            add(
                "        They are correlated with bets already on the card, or "
                "share their"
            )
            add(
                "        modeling assumptions. A shorter card would carry less "
                "hidden risk."
            )
        share = stats.get("verifiable_share")
        if share is not None:
            add(
                f"  {share:.0%} rest on a premise checkable before kickoff "
                "(stale line, ladder inconsistency, public shading)"
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
                f"     Stake ${bet.stake:,.0f} ({bet.stake / unit:.2f}u)  |  EV {bet.ev_pct:+.2f}%  |  "
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

    if result.near_misses:
        add("")
        add("-" * 78)
        add("  NEAR THE FLOOR  (not bets -- none of these cleared the EV floor)")
        add("-" * 78)
        for nm in result.near_misses[:8]:
            add(f"  {nm.event} [{nm.league}]  {_near_miss_desc(nm)}")
            add(
                f"     {nm.ev:+.2%} EV @ {nm.book}  -  {nm.shortfall:.2%} short "
                f"of the {nm.min_ev:.2%} floor"
            )

    if result.ranked:
        from .ranking import probability_of_winning_at_least

        staked = {id(b) for b in result.bets}
        scored = [s for s in result.ranked if id(s.bet) in staked]
        if scored:
            n = len(scored)
            add("")
            add("-" * 78)
            add("  WHAT A NORMAL NIGHT LOOKS LIKE")
            add("-" * 78)
            for k in (n // 2, int(n * 0.6) + 1, n - 1):
                if 0 < k <= n:
                    p = probability_of_winning_at_least(scored, k)
                    add(f"  {k}+ of {n} winning: {p:.0%}")
            add("")
            add("  Going 4-6 on a card like this is an ordinary outcome, not a")
            add("  broken model. Judge the process on closing line value.")

    add("")
    add("=" * 78)
    add("  Sizing is fractional Kelly against uncertainty-adjusted probabilities.")
    add("  Track closing line value; it tells you whether this is working long")
    add("  before the profit column does.")
    add("=" * 78)
    return "\n".join(lines)


def markdown(result: SlateResult, unit_size: float | None = None) -> str:
    """Markdown card, for a file, a commit, or a message."""
    unit = unit_size if unit_size else result.bankroll / 100.0
    lines: list[str] = []
    add = lines.append

    add(f"# Daily Card - {result.generated_at:%Y-%m-%d}")
    add("")
    add(
        f"**Bankroll** ${result.bankroll:,.0f} | **Unit** ${unit:,.2f} | "
        f"**Screened** {result.considered:,} prices | **Selected** {len(result.bets)}"
    )
    add("")

    if not result.bets:
        add("## No bets today")
        add("")
        add(
            "Nothing cleared the expected-value floor after uncertainty and vig. "
            "This happens often and is the system working as intended."
        )
        if result.near_misses:
            add("")
            add("### Closest misses")
            add("")
            add("Not bets -- none of these cleared the floor.")
            add("")
            for nm in result.near_misses[:10]:
                add(
                    f"- {nm.event} [{nm.league}] {_near_miss_desc(nm)} @ {nm.book}: "
                    f"{nm.ev:+.2%} EV, {nm.shortfall:.2%} short of the {nm.min_ev:.2%} floor"
                )
        return "\n".join(lines)

    add(
        f"**At risk** ${result.total_stake:,.0f} ({result.total_stake / unit:.1f}u, "
        f"{result.total_stake / result.bankroll:.1%}) "
        f"| **Expected profit** ${result.expected_profit:,.2f} ({result.expected_roi:+.2%})"
    )
    add("")
    add("| Tier | Game | Bet | Book | Stake | Units | EV | Model | Market |")
    add("|---|---|---|---|---:|---:|---:|---:|---:|")
    for bet in result.bets:
        add(
            f"| {bet.confidence.value} | {bet.event.name} | "
            f"{bet.outcome}{'' if bet.line is None else f' {bet.line:+g}'} "
            f"({bet.american:+.0f}) | {bet.book} | ${bet.stake:,.0f} | "
            f"{bet.stake / unit:.2f}u | "
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

    if result.near_misses:
        add("")
        add("## Near the floor")
        add("")
        add("Not bets -- none of these cleared the EV floor.")
        add("")
        for nm in result.near_misses[:10]:
            add(
                f"- {nm.event} [{nm.league}] {_near_miss_desc(nm)} @ {nm.book}: "
                f"{nm.ev:+.2%} EV, {nm.shortfall:.2%} short of the {nm.min_ev:.2%} floor"
            )

    return "\n".join(lines)


def to_json(result: SlateResult, unit_size: float | None = None) -> str:
    """Machine-readable card.

    Carries everything needed to recompute stakes and exposure client-side
    against a different bankroll, unit size, or Kelly multiplier -- this is
    the export the web dashboard's staking calculator reads.
    """
    unit = unit_size if unit_size else result.bankroll / 100.0
    payload = {
        "generated_at": result.generated_at.isoformat(),
        "bankroll": result.bankroll,
        "unit_size": unit,
        "prices_screened": result.considered,
        "total_stake": result.total_stake,
        "total_stake_units": round(result.total_stake / unit, 3) if unit else None,
        "expected_profit": result.expected_profit,
        "expected_roi": result.expected_roi,
        "card_stats": {
            k: (list(v) if isinstance(v, tuple) else v)
            for k, v in (result.card_stats or {}).items()
        },
        "bets": [
            {
                "event_id": b.event.event_id,
                "event": b.event.name,
                "league": b.event.league,
                "sport": b.event.sport,
                "start_time": b.event.start_time.isoformat(),
                "market": b.market_type.value,
                "subject": b.subject,
                "stat": b.stat,
                "outcome": b.outcome,
                "line": b.line,
                "book": b.book,
                "american": b.american,
                "decimal": round(b.decimal, 4),
                "stake": b.stake,
                "stake_units": round(b.stake / unit, 3) if unit else None,
                "kelly_fraction": round(b.kelly_fraction, 5),
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
        "near_misses": [
            {
                "event": nm.event,
                "league": nm.league,
                "sport": nm.sport,
                "market": nm.market,
                "subject": nm.subject,
                "stat": nm.stat,
                "outcome": nm.outcome,
                "line": nm.line,
                "book": nm.book,
                "american": nm.american,
                "ev": round(nm.ev, 5),
                "min_ev": round(nm.min_ev, 5),
                "shortfall": round(nm.shortfall, 5),
                "model_probability": round(nm.model_probability, 5),
                "market_probability": round(nm.market_probability, 5),
                "books_priced": nm.books_priced,
            }
            for nm in result.near_misses
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
