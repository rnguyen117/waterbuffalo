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

The system is built to say "no bets today" and does so often. That is the
product working. A screen that finds fifteen edges every day has found zero.

## Commands

```bash
sharp-edge card [-v] [--json out.json] [--markdown card.md] [--log]
sharp-edge devig -110 -110        # inspect a market's true prices
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
  market/           book registry, consensus pricing, movement, line shopping
  signals/          injuries, news, weather, situational, market-derived
  pricing/          expected value, Kelly, portfolio construction
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

259 tests, no network required. They cover the math against known values
(-110 is 52.38%, three is the most common NFL margin, Kelly at p=0.6 and even
money is 0.2), and the behaviors that matter: the screen must find the stale
lines the demo generator plants, and it must never recommend both sides of a
market, exceed an exposure cap, or return a negative-EV bet.

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
- **This is not financial advice, and it is not a guarantee.** It is a
  disciplined framework for a negative-sum game where the house holds a
  structural advantage. Bet only what you can afford to lose. If gambling stops
  being something you control, stop: 1-800-GAMBLER.

Sports betting is legal in some jurisdictions and not others. Complying with
the law where you live is your responsibility.

## License

MIT.
