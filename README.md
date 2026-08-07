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

### Tracking

A SQLite ledger of every bet with the reasoning attached, closing line value
reporting, and calibration analysis that measures whether the probabilities are
honest and feeds a corrected `market_trust` back into the config.

**Read the CLV line before the profit line.** Over any realistic sample, profit
is mostly variance and CLV is mostly signal.

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
sharp-edge devig -110 -110        # inspect a market's true prices
sharp-edge ladder strikeouts 6.5 -115 -105   # derive a full alternate ladder
sharp-edge kelly 0.55 -110        # size a single bet
sharp-edge simulate --edge 0.02   # what a season actually looks like
sharp-edge settle 12 won --closing -130
sharp-edge clv                    # are you beating the close?
sharp-edge calibrate              # are your probabilities honest?
sharp-edge summary                # performance by book, league, market
```

`sharp-edge simulate` is worth running before you bet anything. At a 2% edge
over 540 bets, you finish profitable 64% of the time and see a 20% drawdown
along the way 47% of the time. That is what a *winning* approach feels like.

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
  pricing/          expected value, Kelly, portfolio, stat distributions
  risk/             bankroll management, correlation
  track/            ledger, closing line value, calibration
  backtest/         Monte Carlo simulation
  sources/          The Odds API, RSS news, demo generator
```

`docs/METHODOLOGY.md` explains the reasoning behind the numbers — where the
effect sizes come from, which are well supported, and which are weak enough
that they are carried at near-zero weight.

## Tests

```bash
pip install pytest && pytest
```

328 tests, no network required. They cover the math against known values
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
- **Public ticket data is a weak sample.** It covers a small, unrepresentative
  slice of the market, which is why signals derived from it are weighted low.
- **Correlations are structural, not estimated.** Estimating them from your own
  history needs more settled bets than anyone has.
- **Prop distribution shapes are empirical priors, not fitted per player.** The
  dispersion constants are league-typical. A knuckleballer or a
  bench player with erratic minutes will not match them.
- **Prop limits are small and prop accounts get limited fastest.** Books
  tolerate losing on sides far longer than on props, because prop losses
  identify you immediately.
- **This is not financial advice, and it is not a guarantee.** It is a
  disciplined framework for a negative-sum game where the house holds a
  structural advantage. Bet only what you can afford to lose. If gambling stops
  being something you control, stop: 1-800-GAMBLER.

Sports betting is legal in some jurisdictions and not others. Complying with
the law where you live is your responsibility.

## License

MIT.
