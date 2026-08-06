"""sharp-edge: a sports betting expected-value engine.

The thesis in one paragraph: you cannot out-predict a sharp closing line, so
do not try. Reconstruct it precisely, measure how uncertain it is, find the
books that have not caught up to it, and stake the result small enough to
survive being wrong. Everything in this package is in service of one of those
four steps.
"""

from .config import Config, load
from .models import (
    BetCandidate,
    Confidence,
    Event,
    Market,
    MarketType,
    Price,
    SlateResult,
)

__version__ = "0.1.0"

__all__ = [
    "Config",
    "load",
    "Event",
    "Market",
    "MarketType",
    "Price",
    "BetCandidate",
    "Confidence",
    "SlateResult",
    "__version__",
]
