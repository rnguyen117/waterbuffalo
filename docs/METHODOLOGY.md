# Methodology

Where the numbers come from, how confident to be in each, and what the system
deliberately refuses to do. Read this before changing any constant.

The organizing principle: **effects are ranked by how verifiable they are**, not
by how large they are. A one-point stale line you can confirm before placing
the bet is worth more than a three-point handicapping opinion you cannot.

---

## 1. Why the closing line is the benchmark

Bookmakers do not primarily forecast games. They open near their own model,
then let money move them, and the closing number aggregates the information of
everyone who bet into it — including people with better models, better data,
and, sometimes, actual private information.

The empirical consequence is consistent across decades of published research
and every honest bettor's records: the no-vig closing line at a high-limit book
predicts outcomes better than any publicly available model. Systems that beat
the *opening* line are common; systems that beat the *close* are rare.

Two things follow, and they shape every design decision here.

**First, the market probability is the prior, and it is a strong one.** The
model is allowed to disagree, but it starts from the market and its
disagreement is shrunk. `market_trust = 0.60` means 40% of any disagreement
survives. That is not timidity — it is the correct weighting between a noisy
estimate and a very good prior.

**Second, closing line value is the scoreboard.** Whether a bet won is mostly
variance. Whether it beat the close is mostly skill, and it is measurable the
moment the game starts rather than after a thousand bets.

---

## 2. Removing the vig

A book posting -110/-110 quotes 52.38% on each side, summing to 104.76%. The
excess is the vig, and removing it recovers what the book believes. *How* you
remove it matters far more than most bettors realize.

| Method | Assumption | Where it fails |
|---|---|---|
| Multiplicative | Vig is proportional to probability | Overstates longshots |
| Additive | Vig is a flat probability tax | Too harsh on longshots; can go negative |
| Power | Common exponent, `Σ q^k = 1` | Better on the favorite-longshot bias |
| Shin | Book protects against a share `z` of insiders | Best match to settled closing lines |

On a symmetric market all four agree exactly. On a lopsided one they do not,
and the gap is large enough to flip a bet's sign:

```
$ sharp-edge devig -2000 1000
  multiplicative   0.9129  0.0871   ->    -1048    +1048
  additive         0.9307  0.0693   ->    -1344    +1344
  power            0.9433  0.0567   ->    -1663    +1663
  shin             0.9307  0.0693   ->    -1344    +1344
```

The longshot is 8.71% or 5.67% depending on which method you trust — a 54%
relative difference. At an offered price of +1000 (9.09% break-even),
multiplicative says *bet it* and power says *no*.

**This is the single most common way a betting screen fools itself.** Shin is
the default here, and `require_robust_devig` demands the edge clear zero under
all four methods. Most apparent longshot edges do not survive, which is the
point.

Shin's `z` is also reported on its own: it estimates the share of informed
money the book is defending against, and it rises with injury uncertainty and
thin liquidity. It is a decent proxy for how confident a book is in its number.

---

## 3. Weighting books

Books do not have equal opinions. `sharpness` (0–1) reflects independent
pricing, limit size, and how quickly informed money corrects the book.

| Tier | Books | Sharpness | Role |
|---|---|---|---|
| Market maker | Pinnacle, Circa | 0.95–1.00 | Set the number |
| Exchange | Betfair, ProphetX | 0.62–0.88 | Real two-sided liquidity |
| Retail sharp | DraftKings, FanDuel | 0.44–0.46 | Fast, huge volume, still shaded |
| Retail | BetMGM, Caesars | 0.26–0.32 | Slower to move |
| Soft | ESPN Bet, Fanatics, Bovada | 0.14–0.18 | Slowest — where edges live |

Consensus combines log-odds weighted by `sharpness × limit × recency`, with a
floor guaranteeing market makers at least 55% of total weight when present.
Without that floor, twenty retail books echoing each other outvote Pinnacle,
and the "consensus" becomes a measurement of what retail copied.

Limits are weighted logarithmically. A number a book will take $50,000 on has
been defended against everyone who wanted to attack it; a $500 limit has not
been tested.

**Recency matters more than it looks.** A six-hour-old price is a statement
about a different information set. It gets decayed out of the consensus (45
minute half-life) — while the stale price *itself* becomes an opportunity
elsewhere in the pipeline.

---

## 4. Converting points to probability

Signals are naturally measured in points ("their quarterback is out, that's
worth 6.5"). Prices are in probability. The bridge is the sport's margin
distribution.

| Sport | σ (margin) | Note |
|---|---|---|
| NFL | 13.2 | |
| NCAAF | 16.5 | Wider talent gaps |
| NBA | 11.5 | |
| NCAAB | 10.4 | |
| NHL | 1.9 goals | Prefer the Skellam path |
| MLB | 3.1 runs | Prefer the Skellam path |

This conversion is nonlinear, and the nonlinearity is the point: three points
moves a pick'em from 50% to 59%, but moves a 90% favorite only to 93.4%.
Losing a star from a heavy favorite moves the *spread* a lot and the *win
probability* barely at all. A fixed points-to-probability rate gets this
backwards and systematically overvalues news about favorites.

Low-scoring sports use a Skellam distribution (difference of two Poissons)
because a normal curve misses both the discreteness and the tails.

### Key numbers

Football margins are spiky. Roughly 14.7% of NFL games end with a 3-point
margin and 9.2% with 7, because of how scoring works. A normal curve badly
misprices the half point around those numbers, so an empirical margin table is
blended with the game-specific normal. This is what makes `half_point_value()`
correct, and it is why -3 and -3.5 are genuinely different bets rather than a
rounding difference.

---

## 5. Signal effect sizes

Every value below is a consensus estimate, not a fitted parameter. They are
starting points to calibrate against your own results.

### Injuries — the largest real effects

| Sport | Position | Points | Confidence |
|---|---|---|---|
| NFL | QB | 6.5 | High — largest single-player effect in sports |
| NFL | LT / EDGE / WR | 1.3–1.4 | Moderate |
| NFL | RB | 1.2 | Moderate — usually overvalued by the public |
| NBA | Superstar | 7.5 | High |
| NBA | Starter | 2.0 | Moderate |
| NHL | Goalie | 0.7 | High relative to skaters |
| NHL | Skater | 0.15–0.2 | Low — rarely moves a line |
| MLB | Starting pitcher | 0.6 | High |
| MLB | Position player | 0.1–0.15 | Very low |

Multiple absences sum with diminishing returns (0.82 decay per additional
player), because replacement level rises as usage redistributes.

**The residual is what matters.** If a quarterback is out and the line already
moved 6.5 points, the signal contributes *nothing* and says so explicitly in
the report. If the line moved 2 points, 4.5 remain unpriced. If it moved 9, the
market overreacted and the residual flips sign.

### Weather — one variable, and it is wind

| Wind | Points off the total |
|---|---|
| < 10 mph | 0.0 |
| 15 mph | 0.5 |
| 20 mph | 2.2 |
| 25 mph | 4.5 |
| 30 mph | 6.3 |

Football only. Cold weather is largely a myth once wind is controlled for
(≤1.4 points at extremes). Rain matters less than people expect because it
slows both offense and defense. Wind affects totals strongly and sides only
slightly.

### Situational — small, real, mostly priced

| Factor | Points | Weight | Evidence |
|---|---|---|---|
| NBA back-to-back | 1.1 | 0.55 | Strong |
| NBA third in four | 0.6 | 0.55 | Moderate |
| NFL off a bye | 0.9 | 0.55 | Moderate |
| NFL short week | 0.8 | 0.55 | Moderate |
| Altitude (Denver) | 0.6–0.75 | 0.45 | Moderate |
| Cross-country travel | 0.2–0.35 | 0.45 | Weak |
| Lookahead spot | 0.9 | 0.50 | Weak-moderate |
| Letdown spot | 0.7 | 0.40 | Weak |
| **Revenge game** | **0.3** | **0.10** | **Essentially none** |

Revenge is included at near-zero weight deliberately. It is a staple of tout
content and it does not hold up. Carrying it visibly at 0.10 is more useful
than omitting it, because it documents the judgment.

Nothing in this table exceeds 1.1 points. Anyone quoting three points for a
scheduling spot is selling something.

### Market-derived — the most valuable category

These require no knowledge of the teams at all.

| Signal | Weight | Why |
|---|---|---|
| Stale line | 0.95 | Verifiable *before* the bet settles |
| Retail shading | ≤0.70 | Directly measures where public money is |
| Steam (stale book available) | 0.60 | The move has not reached this book yet |
| Steam (market adjusted) | 0.15 | You are paying the new number |
| Handle divergence | ≤0.45 | Measures who is betting, not how many |
| Reverse line movement | 0.40 | Real but crowded, and ticket data is a weak sample |
| Opener drift | 0.35 | A brake — penalizes betting into a big move |

Stale lines carry the highest weight because their premise is checkable at the
moment of the bet. If Pinnacle is -3.5 and a soft book is on -2.5, that point
is real regardless of the outcome. Everything else is a probabilistic claim.

---

## 6. Staking

Full Kelly maximizes growth **given correct probabilities**. Yours are not
correct, and the error is asymmetric: overestimating your edge by 2× makes
Kelly stake 4× too much, and the growth penalty for overbetting is far steeper
than for underbetting.

- Half Kelly: ~75% of theoretical growth, ~50% of the variance.
- Quarter Kelly (default): less growth, ruin becomes a practical impossibility.

Before Kelly is applied, three haircuts run:

1. **Shrinkage toward the market**, scaled by book disagreement. Tight
   agreement means the market is confident and a disagreeing model should
   mostly defer. Wide dispersion is where an independent estimate is worth the
   most.
2. **A lower confidence bound on EV.** A 3% edge with a 4% standard error is
   not a 3% edge, it is a coin flip on whether an edge exists.
3. **A winner's-curse haircut.** Screening *n* prices and keeping the best
   guarantees the survivor carries favorable noise, growing as
   `sqrt(2 ln n)`. Screening 500 prices means the best one carries roughly 2.5
   standard errors of luck.

Then hard caps: 3% per bet, 5% per game, 8% per book, 12% per day. A
catastrophic day costs a tenth of the bankroll, which is survivable.

### The whole slate at once

Sizing bets individually is where good analysis becomes a bad bankroll. A
screen finding fifteen edges will happily stake 40% of a roll across correlated
positions on games kicking off within three hours of each other.

The optimizer maximizes `Σ fᵢμᵢ − ½λ·f'Σf` — the mean-variance approximation to
joint Kelly, tight at small fractions — via projected gradient ascent, subject
to every cap. Correlations are structural:

| Pair | ρ |
|---|---|
| Moneyline / spread, same team | 0.75 |
| Team total / game total | 0.62 |
| Opposite sides, same market | −0.92 |
| Same team, different game | 0.25 |
| Same league, same day | 0.04 |

`effective_bet_count()` reports how many genuinely independent bets a card
amounts to. Twelve bets with same-game overlap can be worth six.

---

## 7. What this deliberately does not do

**Predict game outcomes from box scores.** Any power rating you build is
already inside the closing line, and worse than it.

**Chase steam after the market moves.** Being on the right side at the new
number is worth nothing.

**Trust ticket percentages as gospel.** They cover a small, unrepresentative
slice of the market.

**Bet longshots on multiplicative devig alone.** The most reliable way to
generate fake edges.

**Recommend something every day.** An empty card is a valid, frequent output.

**Promise a number.** Realistic sustained ROI is low single digits. The
simulator exists partly to make that concrete:

```
$ sharp-edge simulate --edge 0.02 --bets-per-day 3 --days 180
Across 5,000 simulations: median $1,001 (+10.0%), profitable 64% of the time.
A bad day (5th percentile) is $-2,349 (-23.5%); a good one (95th) is $5,816.
Chance of seeing a 20% drawdown along the way: 47%
```

A genuine 2% edge over 540 bets loses money more than a third of the time. Size
for the bad path.

---

## 8. Closing the loop

The system corrects itself from its own record.

**Calibration.** A model saying 60% should win 60%. `overconfidence_factor()`
fits a single scaling constant on the log-odds; 1.3 means every claimed edge
should be cut by about a quarter, and `suggested_market_trust()` turns that
directly into a config change.

**CLV, in four quadrants:**

| CLV | Results | Read |
|---|---|---|
| + | + | Working. Change nothing |
| + | − | A real edge inside a bad run. Change nothing |
| − | + | **Dangerous.** Lucky, not good — the profit hides it |
| − | − | Not finding edges. Fall back to structural plays |

The third row is why CLV is tracked at all. A bettor with negative CLV and a
winning month will conclude they have an edge and increase stakes. The data
says otherwise, and it says so long before the P&L does.

---

## References

The approaches here draw on standard results in the field:

- Shin, H.S. (1993) — optimal betting odds against insider traders
- Levitt, S. (2004) — why sportsbooks price to exploit bettor bias rather than
  to balance action
- Kelly, J.L. (1956) — the growth-optimal criterion
- Wolfers & Zitzewitz (2004) — prediction markets as forecasts
- The extensive literature on closing line efficiency and the
  favorite-longshot bias

---

## 9. Props, derivatives, and market efficiency

Everything above concerns sides and totals. Those are the hardest markets in
sports betting, and a system restricted to them is competing where the
competition is strongest.

Market efficiency is not uniform, and the variation is structural rather than
random. It comes down to four things a book allocates unevenly:

1. **Analyst attention.** A pricing desk has a handful of people. They price
   the NFL sides by hand and let a model handle 4,000 player props.
2. **Limit size.** A number a book will take $25,000 on has been attacked by
   everyone who wanted to attack it. A $250 prop has not.
3. **Sharp participation.** Syndicates bet sides because that is where the
   capacity is. Almost nobody with an edge is grinding tackles props for $250
   a shot, so those errors are never corrected.
4. **Correction speed.** A side moves within seconds of news. The related
   props move in minutes, or when someone notices.

That gives the efficiency ladder encoded in `market/taxonomy.py`, and it drives
two behaviors: how far the model may disagree with the market (`market_trust`),
and how large an edge it must find before betting (`min_edge_required`).

**The counterweight is limits, and it is not small.** An 11% edge on a $250
prop is $27. A 3% edge on a $5,000 side is $150. The ranking scores realizable
size explicitly so the card does not fill with percentage edges that cannot be
converted into money.

### Distributions, and why the family matters

A prop is a threshold question about a distribution, so the family has to be
right:

| Family | Stats | Why |
|---|---|---|
| Negative binomial | strikeouts, receptions, rebounds, assists | Overdispersed: variance runs 1.2–1.4× the mean |
| Poisson | home runs, touchdowns, goals, steals | Genuinely rare and independent |
| Gamma | passing, rushing, receiving yards | Non-negative and right-skewed |
| Normal | NBA points, outs recorded | High-volume and near-symmetric |

Using Poisson where negative binomial belongs is the most common and most
expensive mistake, because Poisson forces variance to equal the mean and so
understates both tails. Alternate lines are tail bets, which is exactly where
that error is largest:

```
Projection 6.87 strikeouts, P(over 9.5):
  Poisson            15.67%   =  +538
  Negative binomial  18.58%   =  +438
```

A book generating alternates from a Poisson offers +538 on something worth
+438. That is a 6.6% edge with no forecasting involved.

### Fitting: jointly, never to a single anchor

The obvious approach — fit to the main line, extrapolate outward — is subtly
broken, and the failure is silent. Recovering one probability requires
removing vig, and no devig method is exactly right. A small anchor error
compounds as you move away from it:

```
Anchor devigged 1.3 points low at the 7.5 line
  -> fitted projection 6.29 instead of 6.40
  -> P(over 4.5) off by 1.2 points, three rungs out
  -> a phantom 10% "edge" on a correctly priced ladder
```

This was a real bug during development, caught by feeding the engine a ladder
priced perfectly from a single distribution and finding twelve mispricings
that did not exist.

Fitting jointly fixes it. Every rung is devigged the same way, and the
projection is chosen to minimize squared error in log-odds across all of them.
A systematic devig bias shifts every rung in the same direction and cancels
out of the residuals; what survives is genuine internal disagreement.

The regression test is permanent: **a coherently priced ladder must yield zero
findings**, at every hold from 4% to 12% and every projection.

### Guards specific to props

- **Tail floor (3%).** A fitted 0.3% probability is extrapolation, not
  estimation. Those rungs are declined rather than bet.
- **Distance haircut.** Confidence decays with distance from the ladder's
  center, and the adjustment is one-directional — it can only make a bet look
  worse, never better, so it cannot manufacture an edge.
- **Push credit.** Whole-number prop lines refund rather than lose. Pricing a
  push as a loss materially undervalues the over.
- **Maximum EV (35%).** In a live, correctly parsed market, an edge beyond
  this is a stale quote, a feed error, or a misidentified market. All three
  lose money; none is a bet.

### Public money, where it actually pays

Prop handle is overwhelmingly recreational, and recreational bettors bet overs
— they buy a player to *do* something. The ticket splits are extreme:

| Prop | Over share |
|---|---:|
| Anytime touchdown | 88% |
| Home run | 86% |
| Passing TDs | 78% |
| Points | 74% |
| Strikeouts | 72% |
| Goalie saves | 58% (the exception — unders are popular here) |

Books shade accordingly. The difference from sides is decisive: a shaded
spread gets corrected by sharp money within hours, while a shaded prop is
corrected by nobody and the premium survives to settlement.

The shading is applied **once**, in the signal layer. Applying it in both the
consensus and the signal was another real bug during development — it
double-counted and produced cards consisting entirely of unders.

### Prop-specific signals

**Usage redistribution** is the most valuable. When a starter sits, the side
moves in seconds and the teammates' props move slowly or not at all — yet
their true values have changed a great deal. Basketball has fixed minutes and
fixed shots; a 29%-usage player's absence redistributes to whoever shares his
role, roughly 42% of it to his position-mate.

Stats differ in how much they respond: assists move most (1.30×) because
playmaking concentrates, blocks and steals barely at all (0.30×).

**Blowout risk** is the counterweight nobody prices. Books set props off
season averages that include close games, but starters sit in the fourth
quarter of a 20-point game. The effect is asymmetric: a heavy favorite's stars
get pulled, while a heavy underdog's pass-catchers see *more* volume because
the team throws to catch up.

**Workload limits** are the clearest hard cap in the package. A pitcher who
will not go past the fifth inning has essentially no path to nine strikeouts,
yet his alternate overs are priced from an unconstrained distribution.

---

## 10. Ranking a fixed-size card

"The ten most probable bets" contains a trap worth naming.

**The highest-probability bet on any board is a -3000 favorite at 96.8%.** It
is also nearly the worst price available: risk $30 to win $1, and one loss
erases thirty wins. Sort by probability and you get chalk that loses money
slowly and reliably — the product every parlay-of-favorites tout sells.

Sorting purely by EV fails in the opposite direction, selecting the thinnest
and highest-variance markets, where a 12% edge is usually a modeling error.

The default composite weights five things:

| Component | Weight | Rationale |
|---|---:|---|
| Edge quality | 34% | EV at its lower confidence bound, compressed so outliers do not dominate |
| Hit probability | 22% | Shaped, not raw: full credit in the 45–70% band, penalties for heavy chalk and deep longshots |
| Evidence | 22% | Book count, market-maker participation, agreement |
| Verifiability | 14% | A stale line is checkable now; a situational read is not |
| Realizable size | 8% | An edge you can only get $250 down on is worth less |

Every mode remains selectable — `--rank probability` does exactly what it says
— so the trade-off is made with the numbers visible rather than hidden.

### Two kinds of diversification

`max_per_game` limits **outcome** correlation: four bets on one game is one
opinion expressed four times.

`max_per_market_type` limits **model** correlation, which is subtler and more
dangerous. Every prop on a card is priced through the same distribution
assumptions and the same ladder fit. If that machinery is wrong, it is wrong
on all of them at once, and the card's real variance far exceeds what its
correlation matrix suggests, because the errors share a cause. Spreading
across market types hedges the modeling, not just the games.

When filling a fixed card size requires relaxing these caps, the report says
so rather than padding silently.

### Setting expectations

The card reports its own expected record and the distribution of outcomes:

```
Expected record 5.1-4.9  |  average win probability 50.5%
5+ of 10 winning: 64%    7+ of 10: 18%    9+ of 10: 1%
```

Going 4-6 on ten 55% bets is an ordinary night. Publishing that in advance is
the difference between a bettor who abandons a working process during normal
variance and one who does not.
