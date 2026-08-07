"""Configuration loading.

TOML via the standard library, so there is no dependency to install and the
config file is readable by a human at 6am. Every value has a defensible
default; the file only needs to carry what you disagree with.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

from .pricing.portfolio import PortfolioConstraints


@dataclass
class BankrollConfig:
    starting: float = 10_000.0
    kelly_multiplier: float = 0.25
    max_bet_fraction: float = 0.03
    min_stake: float = 5.0
    round_stakes_to: float = 1.0
    # Cut stake sizes automatically after a drawdown.
    drawdown_scaling: bool = True
    # Dollar value of one "unit", the way bettors actually talk about stakes
    # ("2.5 units on the under") rather than raw dollar figures that drift
    # with a fluctuating bankroll. This is a reporting convention layered on
    # top of the sizing math, not a different sizing model: every stake is
    # still the fractional-Kelly dollar amount computed against the current
    # bankroll, just also expressed in units for the record book. Leave unset
    # to use the standard convention of 1 unit = 1% of the starting bankroll.
    unit_size: float | None = None

    @property
    def effective_unit_size(self) -> float:
        return self.unit_size if self.unit_size else self.starting / 100.0

    def to_units(self, dollars: float) -> float:
        size = self.effective_unit_size
        return dollars / size if size > 0 else 0.0


@dataclass
class ModelConfig:
    devig_method: str = "shin"
    # How much to defer to the market. 0.6 means the model keeps 40% of its
    # disagreement. Raising this is the fastest way to make the system worse.
    market_trust: float = 0.60
    max_total_logit: float = 0.55
    consensus_half_life_min: float = 45.0
    min_books_for_consensus: int = 3
    # Confidence level for the pessimistic EV bound.
    ev_confidence: float = 0.75
    # Require the edge to survive every devig method.
    require_robust_devig: bool = True
    # Apply a winner's-curse haircut scaled to how many prices were screened.
    apply_selection_penalty: bool = True


@dataclass
class FilterConfig:
    min_ev: float = 0.01              # 1% EV floor on the point estimate
    min_ev_lower: float = 0.0         # must clear zero at the lower bound
    # Upper sanity bound. In a live, correctly-parsed market an edge beyond
    # this is not an opportunity -- it is a stale quote, a feed error, or a
    # market we have misidentified. Acting on it is how automated bettors fire
    # at prices that do not exist. Raise it only when you know why.
    max_ev: float = 0.35
    max_hold: float = 0.07            # skip markets juiced beyond this
    min_books: int = 3
    max_hours_to_start: float = 96.0
    min_hours_to_start: float = 0.0
    exclude_markets: list[str] = field(default_factory=list)
    exclude_leagues: list[str] = field(default_factory=list)
    # How many bets the daily card should contain. The engine ranks every
    # qualifying bet across every market and cuts to this number.
    card_size: int = 10
    # "value" (composite, default), "probability", "edge", "confidence", "kelly".
    # Ranking purely by probability selects heavy favorites with poor prices --
    # see docs/METHODOLOGY.md before changing this.
    rank_mode: str = "value"
    # Floor on win probability for a bet to make the card at all.
    min_probability: float = 0.0
    # Cap on how many bets from a single game may occupy the card.
    max_per_game: int = 2
    # Cap per market type. Hedges model risk rather than outcome risk: every
    # prop on a card shares the same distribution assumptions, so if that
    # machinery is wrong it is wrong on all of them at once.
    max_per_market_type: int = 6
    # Include player props and derivative markets in the scan.
    include_props: bool = True
    include_derivatives: bool = True


@dataclass
class SourceConfig:
    provider: str = "demo"            # "demo" | "theoddsapi"
    api_key: str = ""
    sports: list[str] = field(default_factory=lambda: ["nfl", "nba", "wnba", "mlb", "tennis"])
    regions: list[str] = field(default_factory=lambda: ["us", "us2", "eu"])
    markets: list[str] = field(default_factory=lambda: ["h2h", "spreads", "totals"])
    news_feeds: list[str] = field(default_factory=list)
    cache_ttl_seconds: int = 120


@dataclass
class GoalConfig:
    """Daily profit target, in units, with risk cut once it is banked.

    Scoped to the entire bankroll rather than per sport -- one goal, one
    risk dial, whatever mix of sports produced yesterday's number. See
    risk/goals.py for the recurrence this drives.
    """

    enabled: bool = True
    daily_goal_units: float = 3.0
    # Floor on how far size gets cut once the goal is fully banked. Kept
    # well above zero: a fully banked day still bets, just smaller, rather
    # than stopping outright -- stopping is what stop_loss_drawdown is for.
    min_risk_multiplier: float = 0.4


@dataclass
class AccountConfig:
    """Books you can actually bet at.

    Empty means all bettable books are considered, which is fine for
    exploration and useless for a real card.
    """

    books: list[str] = field(default_factory=list)
    limits: dict[str, float] = field(default_factory=dict)


@dataclass
class Config:
    bankroll: BankrollConfig = field(default_factory=BankrollConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    sources: SourceConfig = field(default_factory=SourceConfig)
    goals: GoalConfig = field(default_factory=GoalConfig)
    accounts: AccountConfig = field(default_factory=AccountConfig)
    portfolio: PortfolioConstraints = field(default_factory=PortfolioConstraints)
    data_dir: str = "data"

    @property
    def available_books(self) -> set[str] | None:
        return {b.lower() for b in self.accounts.books} if self.accounts.books else None


def load(path: str | Path | None = None) -> Config:
    """Load configuration, falling back to defaults for anything absent.

    The API key is read from the ``ODDS_API_KEY`` environment variable when
    it is not in the file, because keys do not belong in version control.
    """
    cfg = Config()
    if path is not None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"config file not found: {p}")
        with p.open("rb") as fh:
            raw = tomllib.load(fh)
        _apply(cfg, raw)

    if not cfg.sources.api_key:
        cfg.sources.api_key = os.environ.get("ODDS_API_KEY", "")

    return cfg


def _apply(target: Any, raw: dict) -> None:
    """Recursively overlay a parsed TOML dict onto a dataclass."""
    for f in fields(target):
        if f.name not in raw:
            continue
        value = raw[f.name]
        current = getattr(target, f.name)
        if is_dataclass(current) and isinstance(value, dict):
            _apply(current, value)
        else:
            setattr(target, f.name, value)


DEFAULT_CONFIG_TOML = '''\
# sharp-edge configuration
#
# Every value here has a sane default; delete anything you do not want to
# override. Start with the demo provider to see the pipeline run, then switch
# to a real odds feed once you have a key.

data_dir = "data"

[bankroll]
starting = 10000.0
# Fraction of full Kelly. 0.25 is the recommended ceiling for anyone who is
# not certain their probabilities are calibrated -- and if you were certain,
# you would not be.
kelly_multiplier = 0.25
max_bet_fraction = 0.03
min_stake = 5.0
round_stakes_to = 1.0
drawdown_scaling = true
# Dollar value of one unit, for reporting stakes the way bettors actually
# talk about them ("2.5u on the under"). Purely a display convention --
# sizing itself is still fractional Kelly against the bankroll. Leave
# commented to use the standard 1 unit = 1% of starting bankroll.
# unit_size = 100.0

[model]
devig_method = "shin"
# How far the model is allowed to disagree with the market. Lower is safer.
market_trust = 0.60
ev_confidence = 0.75
require_robust_devig = true
apply_selection_penalty = true
min_books_for_consensus = 3

[filters]
min_ev = 0.01
min_ev_lower = 0.0
max_hold = 0.07
min_books = 3
max_hours_to_start = 96.0

[sources]
provider = "demo"          # "demo" or "theoddsapi"
# api_key = ""             # or set ODDS_API_KEY in the environment
sports = ["nfl", "nba", "wnba", "mlb", "tennis"]
regions = ["us", "us2", "eu"]
markets = ["h2h", "spreads", "totals"]

[goals]
# Daily profit target in units. Once a day's profit clears this, the
# surplus banks and reduces tomorrow's effective goal, which scales down
# bet sizing -- see risk/goals.py. A losing day never increases size.
enabled = true
daily_goal_units = 3.0
min_risk_multiplier = 0.4

[accounts]
# Books you hold funded accounts with. Leave empty to consider all of them.
books = ["draftkings", "fanduel", "betmgm", "caesars", "espnbet", "circa"]

[portfolio]
max_total_exposure = 0.12
max_per_game = 0.05
max_per_bet = 0.03
max_bets = 15
risk_aversion = 1.0
'''


def write_default(path: str | Path) -> Path:
    """Write a commented starter config."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(DEFAULT_CONFIG_TOML)
    return p
