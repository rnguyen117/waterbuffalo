# sharp-edge

A sports betting expected-value engine. It reads prices from every book it can
reach, reconstructs what the sharp market actually believes, adjusts for news
and injuries the market has not finished pricing, and produces a staked card of
the day's best bets — or, frequently, no card at all.

```
==============================================================================
  DAILY CARD  -  2026-08-06 22:10 UTC
==============================================================================
  Bankroll $10,000   |   672 prices screened
  3 bets   |   $900 at risk (9.0% of bankroll)
  Expected profit $52.53 (+5.84% on turnover)

------------------------------------------------------------------------------
  TIER A  strong
------------------------------------------------------------------------------

  Philadelphia Eagles @ Houston Texans  [NFL]  Sun 09:39 UTC
  >> Houston Texans -0.5 (-100) @ bovada
     Stake $300  |  EV +8.72%  |  fair +102  |  model 54.4% vs market 50.0%
     - bovada still posting a number +1.5 points off the sharp consensus
     - Houston Texans: 49% of money on 59% of tickets
     - M. Carter (questionable, WR); net +0.6 pts, line has moved +0.0,
       +0.6 pts still unpriced
     - coming off a bye (+0.9 pts)
```

## Start here, because it changes what you expect

**You cannot out-predict Vegas, and this software does not try.**

The closing line at a high-limit book is the best publicly available forecast
of a sporting event. It is not one bookmaker's opinion — it is the number that
survived every sharp bettor in the world attacking it with real money for
days. Beating it consistently with a model you wrote is not a realistic goal,
and every product that claims to do so is selling picks.

So the strategy here is different, and it is the one that actually works:

1. **Reconstruct the sharp number precisely.** Strip vig correctly, weight
   books by how much their opinion is worth, and know how uncertain the
   answer is.
2. **Find the books that have not caught up to it.** A soft book still posting
   +7 when the market is at +6 is offering a point of free equity. This is
   latency arbitrage, not prediction, and it is where most of the realized
   profit comes from.
3. **Claim only what the market has not priced.** When news breaks, the line
   moves. The edge is the residual — the part of a real effect the market has
   not absorbed yet — never the whole effect.
4. **Size small enough to survive being wrong.** Fractional Kelly against
   uncertainty-adjusted probabilities, with hard caps on exposure.

Realistic outcomes: a disciplined operator doing this well earns low
single-digit ROI on turnover. A 3% ROI is a genuinely good result. If you find
yourself projecting 15%, something in the pipeline is lying to you, and this
package contains several deliberate mechanisms to stop that from happening.

## Install and run

Requires Python 3.11 or newer. The core has **no dependencies** — the math
should never be blocked on an install.

```bash
git clone <this-repo> && cd sharp-edge
pip install -e .

sharp-edge card              # today's card, using the built-in demo market
sharp-edge card -v           # with full reasoning for each bet
```

The demo generator simulates a realistic market — market makers pricing
tightly, retail books shading toward the public side, and a subset of soft
books deliberately left stale — so you can see the whole pipeline work before
connecting a real feed.

### Going live

```bash
sharp-edge init                          # writes a commented config
export ODDS_API_KEY=your_key_here        # from the-odds-api.com
```

Set `provider = "theoddsapi"` in the config, list the books you actually hold
funded accounts with under `[accounts]`, and run `sharp-edge -c sharp-edge.toml card`.

Recommending a price at a book you cannot bet is noise, so configure the
account list before trusting a card.

**What "live" actually covers, and what it does not.** Odds and lines are
always real once a key is set. Everything else is assembled from whatever
free source actually exists for it, and one input has none at all:

| Input | Source | Notes |
|---|---|---|
| Odds / lines | The Odds API | Real, always, given a key |
| Player props | The Odds API, per event | Priced per game, not bulk -- one extra paid API call per event. `sources.live_props_max_events` caps it. Off by setting `live_props = false` |
| Injuries | ESPN's public site API | Free, keyless, but unofficial and unversioned -- it is what espn.com itself runs on, not a published product, and could change shape without notice |
| Weather | National Weather Service | Free, official, US-only. Only wired for NFL -- the one sport here with outdoor venues where it matters |
| News | RSS, if you configure `news_feeds` | Empty otherwise |
| Player lineups | Inferred from news text | No structured feed exists; this only works at all when `news_feeds` is configured, and it's keyword matching ("will start," "scratched"), not a confirmed lineup |
| Public betting (tickets/handle) | **None** | Real-time ticket/handle splits are a paid product (Action Network and similar). Left empty rather than built against an unofficial scrape of someone else's consensus page |

That last row means the public-money signals (`HandleDivergenceSignal`,
part of `ReverseLineMovementSignal`) never fire on a live card today --
they are fully implemented and tested against the demo's simulated data,
just structurally starved of a real feed. If you have or can get a paid
public-betting data source, wiring it in is a matter of populating
`Inputs.public` the same way the injuries/weather sources below do.

**Sport coverage is whatever The Odds API lists, not whatever exists.**
`sources.sports` defaults to `nfl, nba, wnba, mlb, npb, tennis`. NPB
(Nippon Professional Baseball, Japan) is wired the same way MLB is, minus
player props -- The Odds API only publishes h2h/spreads/totals for
`baseball_npb`, no prop markets, so `PROP_MARKET_KEYS` deliberately has no
`npb` entry and `fetch_props` treats that as "nothing to fetch," not an
error. **KBO (Korean baseball) is not available from The Odds API at any
plan tier** -- checked directly against their `/v4/sports` catalog (79
sports, no KBO). Wiring it in would mean integrating a second data
provider, not a config change, and no free/legitimate KBO odds source is
known to exist.

**Credits are the real constraint, and they burn far faster than "one
request per pull."** The Odds API charges `regions x markets` per call,
not one credit per call. With the default 3 regions (`us, us2, eu`) and
player props priced per event (not bulk), a single `card` run against a
full slate can cost **400-500+ credits** -- almost the entire 500/month
free tier in one run, because props dominate the bill (bulk odds pulls are
cheap; per-event prop chunks, multiplied by regions, are not). Practical
levers, cheapest first: drop `regions` to `["us"]` (3x cheaper), lower
`live_props_max_events`, or set `live_props = false` entirely. Paid tiers
(checked live): 20K credits/mo for $30, 100K/mo for $59, 5M/mo for $119.
At ~500 credits/run, 20K/mo supports roughly 40 runs a month before the
props cap or region count need loosening further.

## Every market, not just sides

Moneylines, spreads, and totals are the *hardest* markets to beat, because
they get the most attention from everyone. The engine scans them, but the
edges concentrate elsewhere — and it prices the full menu accordingly:

| Market | Efficiency | Typical hold | Typical limit |
|---|---:|---:|---:|
| Point spread | 0.90 | 4.5% | $25,000 |
| Moneyline / total | 0.87–0.88 | 4.2–4.5% | $20–25,000 |
| First half / first five | 0.72–0.78 | 5.0% | $4–5,000 |
| Team totals | 0.68 | 5.5% | $2,500 |
| Alternate lines | 0.72 | 6.0% | $3,000 |
| Pitcher strikeouts | 0.66 | 7.5% | $2,500 |
| NBA points / rebounds / assists | 0.56–0.66 | 7.2–8.2% | $1,500–2,500 |
| Anytime touchdown | 0.54 | 11.5% | $1,000 |
| Tackles, steals, blocks | 0.42–0.46 | 9.5–11% | $250–500 |
| WNBA points / rebounds / assists | 0.44–0.52 | 9.0–9.8% | $500–750 |
| Tennis aces / double faults | 0.40–0.48 | 10.0–11.5% | $250–400 |

WNBA props are registered under their own `(sport, stat)` key, not folded
into the NBA's — the two share stat names ("points", "assists") but not a
profile. A lookup keyed on the stat alone would let whichever sport loads
last in the registry silently overwrite the other's efficiency and limit
numbers, which is exactly the kind of bug this system exists to prevent
elsewhere and very nearly reintroduced here.

### Tennis: a different kind of market entirely

Every other sport here prices a market by recovering an expected margin and
running it through a distribution — normal, Skellam, gamma. Tennis has no
margin in that sense: a 6-1 6-2 win and a 7-6 7-6 win are both "the match,"
and neither maps onto a continuous scale the way point differential does.

What tennis has instead is **serve percentage** — the probability a player
wins a point on their own serve. `pricing/tennis.py` runs that single number
through the actual rules of scoring exactly, via recursion rather than a
memorized formula: point-win-rate → game-hold probability (the closed-form
deuce result, derived from a geometric series rather than asserted) →
set-win probability (game-by-game, with a proper 6-6 tiebreak) → match-win
probability (best-of-three or best-of-five, via exact combinatorics). A
quoted moneyline inverts back to a serve-rate edge the same way
`oddsmath.prob_to_spread` recovers an expected margin for a team sport, so a
news signal ("second serve speed down 8 mph") has somewhere principled to
land.

Every function is cross-checked against an independent Monte Carlo
simulation in `tests/test_tennis.py` rather than trusted on the strength of
a formula transcribed from memory — which caught two real bugs during
development: unbounded recursion in the win-by-two zone past 6-6 in a
tiebreak (fixed with a closed-form solution to that renewal process), and a
6-6 set tiebreak that was accidentally being priced off game-hold
probabilities (~70%) instead of the underlying point probabilities (~55–65%)
it needed.

The pattern is the whole strategy. A book defends its NFL side with six
figures and its best analysts; it posts a tackles prop at a $500 limit with a
model nobody reviews. Almost no sharp money corrects prop markets, so errors
there survive to settlement.

**The catch, stated plainly:** the softest markets carry the smallest limits.
An 11% edge on a $250 prop is $27. The engine tracks this explicitly and
ranks a 3% edge on a $5,000 market above an 11% edge you can only get $250
down on.

### Every bet inside every bet

The strongest prop edge does not require out-projecting anyone. Books post one
anchor line and generate the alternates off it with a crude multiplier, rather
than from the model that produced the anchor. So:

1. Take every price a book posts on a player-stat.
2. Fit a single distribution across all of them — negative binomial for
   overdispersed counts like strikeouts, Poisson for rare events, gamma for
   right-skewed yardage.
3. Any rung that deviates from the book's own fitted curve is the book
   **disagreeing with itself**, which is checkable before kickoff.

```
$ sharp-edge ladder strikeouts 6.5 -115 -105
Fair over     0.5113  (-105)
Distribution  negbin, dispersion 1.35
Implied projection: 6.87

  line      fair over     fair under
     4.5       -339          +339
     6.5       -105          +105  <- posted
     8.5       +266          -266
     9.5       +438          -438
```

A book pricing that ladder off a Poisson would offer **+538** on the 9.5 when
the correct number is **+438**. Poisson assumes variance equals the mean;
real strikeout counts run about 1.35× overdispersed, which fattens exactly the
tails alternates are sold on.

The safeguard that makes this trustworthy: **fed a correctly-priced ladder,
the engine returns zero findings** — at every hold level from 4% to 12% and
every projection. That is a test, not a claim (`test_no_false_positives_at_any_hold`).

### Where the public's money is

Books do not price to be right. They price to earn the hold against a public
with known preferences, and that shows up hardest where nobody corrects it:

- **Prop overs.** Roughly 88% of anytime-touchdown tickets and 72% of
  strikeout tickets take the over — people bet on a player to *do* something.
  Books shade accordingly, and with no sharp money to correct it the premium
  survives to settlement. This is the single largest systematic public-money
  effect on the board.
- **Handle versus tickets.** 30% of tickets carrying 65% of dollars means the
  average wager is four times larger on that side. This measures *who* is
  betting, not how many, and it is far more informative than a ticket count.
- **Public darlings.** Cowboys, Lakers, Yankees. Books shade their numbers
  because the money arrives regardless of price.
- **Ticket percentage alone.** Included, weighted lowest, and labeled as the
  weak signal it is — public data covers a small unrepresentative slice, and
  "fade the public" has been known long enough to be partly priced.

### One slate, one date

The card is today's games, full stop — not a blend of tonight's MLB and
next Sunday's NFL just because the NFL had nothing closer to fill the card
with. `filters.same_day_only` (on by default) drops any event that doesn't
fall on the same calendar day as every other event on the card. A sport
with nothing today simply contributes zero bets rather than reaching days
or weeks ahead.

"Day" is anchored to `filters.schedule_timezone` (US Eastern by default)
rather than UTC, because any prime-time game already crosses into the next
UTC date — a 1pm ET game and a 9pm ET game on the *same* Eastern calendar
day land on two different UTC dates (18:00 UTC vs. 02:00 UTC the next day),
which a raw UTC-date comparison would read as two different slates. Eastern
is the reference every American league schedules around, not a claim about
where games are played.

```toml
[filters]
same_day_only = true
schedule_timezone = "America/New_York"
```

`max_hours_to_start` still applies underneath this as a secondary cap, so
turning `same_day_only` off falls back to the plain rolling window that was
the only behavior before this existed.

### The daily top 10

Every qualifying bet across every market is ranked and cut to a fixed card.

**One caveat worth reading before you set `--rank probability`.** The
highest-probability bet available on any day is a -3000 favorite at 96.8%. It
is also nearly the worst price on the board: you risk $30 to win $1, and one
loss erases thirty wins. Sorting by raw probability produces a card of heavy
chalk that loses money slowly and reliably — it is what every
parlay-of-favorites tout sells.

So the default composite balances five things: EV at its lower confidence
bound, hit probability (favoring the 45–70% band), evidence strength,
**verifiability** (a stale line is checkable now, a situational read is not),
and realizable size. Every mode is still selectable:

```bash
sharp-edge card --top 10                      # composite (default)
sharp-edge card --top 10 --rank probability   # literal highest win probability
sharp-edge card --top 10 --min-probability 0.5
sharp-edge card --props-only
```

The card reports its own expected record and the odds of a good night, because
a 4-6 evening on ten 55% bets is an ordinary outcome, not a broken model:

```
  Expected record 5.1-4.9   |   average win probability 50.5%
  Market mix: 9 player prop, 1 spread
  5+ of 10 winning: 64%      7+ of 10: 18%      9+ of 10: 1%
```

## What it does

### Market pricing

| Capability | Why it matters |
|---|---|
| Four devig methods (Shin, power, multiplicative, additive) | On a -2000/+1000 market they disagree by 3 percentage points on the longshot. That gap decides whether a bet is +EV, and most screens never check |
| Sharp-weighted consensus in log-odds | Pinnacle and Circa outweigh twenty retail books echoing each other |
| Dispersion as an error bar | When books disagree, the consensus deserves less trust and stakes shrink automatically |
| Sharp-versus-retail split | Measures how far retail has shaded toward the public side, which points directly at the value side |
| Line re-pricing across numbers | +2.5 and +1.5 are different bets; comparing their prices directly invents edges |
| Empirical key numbers | NFL margins spike hard at 3 and 7; a normal curve misprices every half point near them |

### Signals

Every signal reports its effect **and** how much the market has already priced,
so a headline that moved the line contributes nothing.

- **Stale lines** — a bettable book trailing the sharp number. Highest weight in
  the system, because its premise is verifiable *before* the game.
- **Retail shading** — books price to balance action against a public that
  reliably takes favorites, overs, and famous teams. That is a business decision,
  not a forecast, and it leaves the unpopular side cheap.
- **Injuries** — positional point values (an NFL quarterback is ~6.5 points, an
  MLB position player is ~0.1), converted to probability through the sport's
  margin distribution, minus whatever the line already absorbed.
- **Breaking news** — keyword classification of headlines, weighted by minutes
  since publication. Keyword-based on purpose: betting news is a small,
  formulaic vocabulary, and when the edge lasts minutes, speed beats nuance.
- **Steam and reverse line movement** — coordinated high-limit moves, and lines
  moving against the ticket count. Steam is only worth anything at a book that
  has not followed yet.
- **Handle versus tickets** — 35% of tickets carrying 60% of dollars means large
  wagers are on that side.
- **Weather** — wind, and effectively only wind. Below 10 mph it does nothing;
  above 20 it is worth multiple points off a total.
- **Rest, travel, altitude, schedule spots** — small, real, and mostly priced
  already, so weighted accordingly. Revenge narratives are included at near-zero
  weight because the evidence for them is near zero.

### Structural edges (no forecast required)

Arbitrage, middles, low-hold pairs, odds boosts, free-bet conversion, and
correlated parlay pricing. These are arithmetic on posted prices and are true
regardless of who wins.

### Staking and risk

Fractional Kelly (quarter by default), shrinkage toward the market scaled by
model confidence, and whole-slate optimization: mean-variance joint Kelly under
caps on total exposure, per game, per bet, and per book, with a structural
correlation matrix so four bets on one game are not treated as four independent
positions.

**Goal-based risk reduction** (`risk/goals.py`) layers a second, slower dial
on top of that: set a daily profit goal in units. A day that clears it
*banks* the surplus, which reduces tomorrow's effective goal and scales
exposure down for the next card — continuously, not as a step function, and
floored at `min_risk_multiplier` (0.4 by default) so betting never stops
outright, which is what `stop_loss_drawdown` is already for.

```
banked_surplus_t  = max(banked_surplus_{t-1} + (profit_units_{t-1} - goal), 0)
effective_goal_t  = max(goal - banked_surplus_t, 0)
progress_fraction = 1 - effective_goal_t / goal
risk_multiplier   = 1 - progress_fraction * (1 - min_risk_multiplier)
```

The floor at zero on `banked_surplus` is the load-bearing line: a day that
misses the goal contributes a negative term that gets clamped away instead
of carried forward as "debt" that would justify betting bigger to catch up.
That asymmetry — surplus banks, deficits do not — is what keeps this from
turning into martingale/revenge-betting with extra steps. The state is
recomputed from the ledger's full settled history on every run
(`state_from_history`) rather than saved separately, so the number in front
of you is always reproducible from the ledger alone.

`risk_multiplier` scales the exposure caps themselves
(`max_total_exposure`, `max_per_bet`, `max_per_game`, `max_per_book`, and
`bankroll.max_bet_fraction`) — not `kelly_multiplier`. That distinction
matters: the portfolio optimizer re-solves the whole slate from the caps on
every run and in practice pushes every stake up to whatever those caps
allow, almost independent of `kelly_multiplier`, which turns out to mostly
just gate whether a thin-edge bet is eligible at all. An earlier version of
this scaled `kelly_multiplier` and, as a result, did not actually reduce
risk on a day it should have — caught by testing the claim directly rather
than trusting that the parameter with "risk" in its name was the one doing
the work.

It applies to the whole bankroll, not per sport: one goal, one risk dial,
whatever mix of NFL, NBA, WNBA, MLB, and tennis produced yesterday's number.
Configure it under `[goals]`:

```toml
[goals]
enabled = true
daily_goal_units = 3.0
min_risk_multiplier = 0.4
```

**Target-seeking** is the mirror image, for the opposite question: given
today's actual screened edges, what would it take to be *on pace* for the
goal? `auto_target = true` (or `sharp-edge card --target-profit 5`) has the
card search for the smallest exposure scale — always ≥ 1.0×, capped at
`max_target_scale` (1.5 by default) — that makes today's expected profit
meet the day's remaining goal (`effective_goal`, after any banked surplus).
It only ever scales *up* from the configured baseline, and only up to that
ceiling: doubling every exposure cap roughly quadruples the depth of a bad
run, so this stays deliberately closer to 1× than to 2×, and a day already
on pace at baseline sizing is left alone rather than shrunk to land exactly
on the goal. If even the ceiling falls short, the card says so plainly —
"today's screened edges support at most 2.1u, short of the 5.0u goal" —
because that is a real shortage of qualifying bets, not something more
exposure would fix, and the tool says so instead of quietly overbetting to
chase a number.

```bash
sharp-edge card --target-profit 5   # size up (bounded) to pursue 5u today
```

The two dials compose: risk reduction can shrink the effective baseline
below 1.0× first (a day already ahead of pace), and target-seeking then
searches upward *from that reduced baseline*, still bounded by the same
ceiling relative to the original configured caps — so being partly ahead of
the multi-day goal never licenses full-ceiling risk just because today's
specific number hasn't been hit yet.

### Tracking

A SQLite ledger of every bet with the reasoning attached, closing line value
reporting, and calibration analysis that measures whether the probabilities are
honest and feeds a corrected `market_trust` back into the config.

**Read the CLV line before the profit line.** Over any realistic sample, profit
is mostly variance and CLV is mostly signal.

`sharp-edge summary` also prints a **scorecard** — win/loss count and win
rate off graded bets specifically (`Ledger.scorecard()`), which is a
different question than `summary()`'s ROI-first view — and, when goal
tracking is enabled, the same goal-progress numbers the next card will size
against. `sharp-edge summary --json` exports the scorecard, the goal state,
and daily P&L by settlement day.

## How it avoids fooling itself

Most betting screens fail in the same handful of ways. Each is addressed
explicitly:

| Failure | Defense |
|---|---|
| Devig method manufactures the edge | The bet must clear zero EV under *all four* methods |
| Point estimate ignores its own error | EV evaluated at a lower confidence bound, not the mean |
| Winner's curse from screening thousands of prices | Log-odds haircut scaling with `sqrt(2 ln n)` |
| An outlier price looks generous | Prices far off the market median are discounted, because a lone book is more often informed or stale than generous |
| Betting news the market already priced | Signals claim only the residual after observed line movement |
| Correlated bets sized as independent | Structural correlation matrix in the portfolio optimizer |
| Both sides of a market screening +EV | Both are dropped — the fair price is wrong, not the market |
| Comparing prices at different numbers | Each book's price re-priced at its own line first |
| Overbetting a real edge into ruin | Fractional Kelly, hard caps, drawdown scaling, stop-loss |
| Pooling a prop ladder into one price | Each rung priced separately from a jointly-fitted distribution |
| Extrapolating into an unpriceable tail | Rungs implying under 3% are declined outright |
| An "edge" that is really bad data | Anything above 35% EV is rejected as a stale quote or parse error |
| A card of ten props sharing one modeling assumption | Per-market-type caps, flagged when relaxed to fill the card |
| Books split on which side of a near-even line is "favorite" | Every book's quote translated onto a common reference line before averaging |

The system is built to say "no bets today" and does so often. That is the
product working. A screen that finds fifteen edges every day has found zero.

## Commands

```bash
sharp-edge card [-v] [--json out.json] [--markdown card.md] [--log]
sharp-edge card --unit-size 50 --kelly-multiplier 0.25   # stakes shown in $ and units
sharp-edge card --target-profit 5   # size up (bounded) to pursue 5u today
sharp-edge devig -110 -110        # inspect a market's true prices
sharp-edge ladder strikeouts 6.5 -115 -105   # derive a full alternate ladder
sharp-edge kelly 0.55 -110 --unit-size 50    # size a single bet, in $ and units
sharp-edge simulate --edge 0.02   # what a season actually looks like
sharp-edge settle 12 won --closing -130
sharp-edge clv                    # are you beating the close?
sharp-edge calibrate              # are your probabilities honest?
sharp-edge summary [--json out.json]   # scorecard, goal progress, performance by book
sharp-edge refresh-stats card.json     # re-sync a card export's scorecard/goal from
                                        # the ledger after settling bets -- no live pull
```

An exported card's `card_stats.scorecard` and `card_stats.goal` are a
snapshot from whenever `card --json` ran, not something that updates itself
as bets settle later. `refresh-stats` re-reads the local ledger and rewrites
just those two fields in place, so the [dashboard](#dashboard)'s Track
Record and Goal Progress panels reflect real settled results the next time
you reload that export -- without spending API quota to re-pull odds just
to refresh two numbers that live entirely in the ledger.

**Units** are a display convention, not a different sizing model: every
stake is still a fractional-Kelly dollar amount against the current
bankroll, shown alongside its unit equivalent because that's how bettors
actually talk about a card ("2.5u on the under"). `--unit-size` sets the
dollar value of one unit directly; leave it unset and one unit defaults to
1% of the bankroll, rebasing automatically as the bankroll changes.
`sharp-edge card --json` exports `unit_size`, `stake_units`, and
`kelly_fraction` per bet, which is what lets the [web dashboard](#dashboard)
recompute stakes at a different bankroll or unit size without rerunning the
Python pipeline.

`sharp-edge simulate` is worth running before you bet anything. At a 2% edge
over 540 bets, you finish profitable 64% of the time and see a 20% drawdown
along the way 47% of the time. That is what a *winning* approach feels like.

## Dashboard

`web/dashboard.html` is a self-contained staking calculator and card
explorer — open it directly in a browser, no server or build step. It ships
with an embedded sample card so it works immediately, and it reads a real
export from `sharp-edge card --json` if you paste or upload one.

Above the card sits a **track record and goal progress** panel, sourced
from `card_stats.scorecard` and `card_stats.goal` in the JSON export — the
same win/loss record and goal state `sharp-edge summary` prints, next to
each bet's event date and time. It hides itself gracefully on an older
export, or a fresh ledger with nothing settled yet.

Every control on the left recomputes the card live, client-side:

- **Bankroll, unit size, Kelly multiplier, exposure caps** — restaked
  through the exact same uncertainty-shrunk fractional-Kelly formula as
  `pricing/kelly.py`, cross-checked against the Python output to six decimal
  places before anything shipped. A single pass of the same per-bet /
  per-game / per-book / total-exposure caps from `pricing/portfolio.py`
  follows — not the full correlation-aware optimizer (that still only runs
  in the CLI), so treat these totals as a close approximation.
- **Sort and filter** (rank mode, minimum win probability, sport, market
  type) act on the bets already screened into the loaded card. They do not
  re-run the EV screen — changing what qualifies for a card at all still
  means adjusting `filters.*` and rerunning `sharp-edge card`.

It is a staking calculator and card viewer, not a rebuild of the pipeline in
JavaScript. That scope is deliberate: recomputing stakes from a screened
card's own numbers is arithmetic a browser can do exactly; regenerating
which bets qualify would mean re-implementing the signal engine, and a
second implementation that quietly drifts from the Python one is worse than
no second implementation.

## Layout

```
src/sharpedge/
  oddsmath.py       conversions, four devig methods, margin and Skellam models
  models.py         shared data types
  config.py         TOML configuration
  pipeline.py       the daily run, start to finish
  report.py         console, Markdown, and JSON output
  cli.py            command line interface
  ranking.py        daily top-N selection and the probability/value trade-off
  market/           book registry, consensus, movement, shopping, props,
                    public money, market taxonomy
  signals/          injuries, news, weather, situational, market-derived, props
  pricing/          expected value, Kelly, portfolio, stat distributions,
                    tennis (serve-percentage win probability)
  risk/             bankroll management, correlation, goal-based sizing
  track/            ledger, closing line value, calibration
  backtest/         Monte Carlo simulation
  sources/          The Odds API (odds, props), NWS (weather), ESPN
                    (injuries), RSS news, demo generator
web/
  dashboard.html    self-contained staking calculator and card explorer
```

`docs/METHODOLOGY.md` explains the reasoning behind the numbers — where the
effect sizes come from, which are well supported, and which are weak enough
that they are carried at near-zero weight.

## Tests

```bash
pip install pytest && pytest
```

465 tests, no network required. They cover the math against known values
(-110 is 52.38%, three is the most common NFL margin, Kelly at p=0.6 and even
money is 0.2), and the behaviors that matter: the screen must find the stale
lines the demo generator plants, and it must never recommend both sides of a
market, exceed an exposure cap, or return a negative-EV bet. The most
important one is negative: fed a coherently-priced prop ladder, the engine
must find **nothing**.

## Limits and honest caveats

- **Effect sizes are estimates.** Positional injury values and situational
  adjustments are consensus figures, not fitted parameters. Calibrate them
  against your own results.
- **Winning accounts get limited.** Sustained success at retail books leads to
  stake limits or closure. This is a business reality the software cannot solve.
- **Public ticket/handle data has no live source.** The signals that read it
  are weighted low by design even where the data exists, because it covers a
  small, unrepresentative slice of the market -- but as shipped, live mode
  has no feed for it at all (see the table under "Going live"), so those
  signals are inert on a live card, not just lightly weighted.
- **The injury source is unofficial.** ESPN's site API is not a published,
  versioned product; it is what espn.com itself happens to run on, and it
  can change shape or disappear without notice. Treat a sudden empty
  injuries list as "check whether ESPN changed something," not "no one is
  hurt today."
- **Correlations are structural, not estimated.** Estimating them from your own
  history needs more settled bets than anyone has.
- **Prop distribution shapes are empirical priors, not fitted per player.** The
  dispersion constants are league-typical. A knuckleballer or a
  bench player with erratic minutes will not match them.
- **Prop limits are small and prop accounts get limited fastest.** Books
  tolerate losing on sides far longer than on props, because prop losses
  identify you immediately.
- **The tennis model treats sets as independent, given each player's hold
  rate.** That is the standard simplifying assumption in tennis forecasting
  (Klaassen & Magnus, Barnett-Clarke), but it ignores momentum and fatigue
  across sets, which is a real, second-order effect.
- **This is not financial advice, and it is not a guarantee.** It is a
  disciplined framework for a negative-sum game where the house holds a
  structural advantage. Bet only what you can afford to lose. If gambling stops
  being something you control, stop: 1-800-GAMBLER.

Sports betting is legal in some jurisdictions and not others. Complying with
the law where you live is your responsibility.

## License

MIT.
