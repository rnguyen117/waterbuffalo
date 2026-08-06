"""Sportsbook registry: who sets the number and who copies it.

The single most important structural fact in sports betting is that books do
not have equal opinions. A handful of market makers price independently,
accept large stakes, and get moved by informed money. Everyone else watches
those numbers and follows, some quickly and some slowly.

That asymmetry is the business model of this entire package:

  * You learn the true probability from books with high ``sharpness``.
  * You place the bet at books with ``bettable=True`` and low sharpness,
    because those are the ones whose prices lag the truth.

A "+EV" bet at Pinnacle is almost always a modeling error. A +EV bet at a
slow book, measured against Pinnacle, is the actual product.
"""

from __future__ import annotations

from ..models import Book, BookTier

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
#
# sharpness is the weight the consensus estimator gives this book's no-vig
# price, on a 0..1 scale. It reflects independence of pricing, limit size, and
# how quickly the book is corrected by informed money -- not brand size.

BOOKS: dict[str, Book] = {
    # -- Market makers: they originate numbers ------------------------------
    "pinnacle": Book(
        key="pinnacle",
        name="Pinnacle",
        tier=BookTier.MARKET_MAKER,
        sharpness=1.00,
        max_limit=50_000,
        bettable=False,  # unavailable in most US states; used as the anchor
    ),
    "circa": Book(
        key="circa",
        name="Circa Sports",
        tier=BookTier.MARKET_MAKER,
        sharpness=0.95,
        max_limit=50_000,
        bettable=True,
    ),
    "bookmaker": Book(
        key="bookmaker",
        name="BookMaker",
        tier=BookTier.MARKET_MAKER,
        sharpness=0.72,
        max_limit=20_000,
        bettable=True,
    ),
    # -- Exchanges: two-sided liquidity, no house position ------------------
    "betfair": Book(
        key="betfair",
        name="Betfair Exchange",
        tier=BookTier.EXCHANGE,
        sharpness=0.88,
        max_limit=25_000,
        bettable=True,
    ),
    "prophetx": Book(
        key="prophetx",
        name="ProphetX",
        tier=BookTier.EXCHANGE,
        sharpness=0.62,
        max_limit=10_000,
        bettable=True,
    ),
    # -- Retail sharp: enormous volume, fast, but they shade the public side -
    "draftkings": Book(
        key="draftkings",
        name="DraftKings",
        tier=BookTier.RETAIL_SHARP,
        sharpness=0.46,
        max_limit=5_000,
        bettable=True,
    ),
    "fanduel": Book(
        key="fanduel",
        name="FanDuel",
        tier=BookTier.RETAIL_SHARP,
        sharpness=0.44,
        max_limit=5_000,
        bettable=True,
    ),
    "betmgm": Book(
        key="betmgm",
        name="BetMGM",
        tier=BookTier.RETAIL,
        sharpness=0.32,
        max_limit=3_000,
        bettable=True,
    ),
    "caesars": Book(
        key="caesars",
        name="Caesars",
        tier=BookTier.RETAIL,
        sharpness=0.30,
        max_limit=3_000,
        bettable=True,
    ),
    "betrivers": Book(
        key="betrivers",
        name="BetRivers",
        tier=BookTier.RETAIL,
        sharpness=0.26,
        max_limit=2_000,
        bettable=True,
    ),
    # -- Soft: slowest to move, smallest limits, best prices to attack ------
    "espnbet": Book(
        key="espnbet",
        name="ESPN Bet",
        tier=BookTier.SOFT,
        sharpness=0.18,
        max_limit=1_000,
        bettable=True,
    ),
    "fanatics": Book(
        key="fanatics",
        name="Fanatics",
        tier=BookTier.SOFT,
        sharpness=0.17,
        max_limit=1_000,
        bettable=True,
    ),
    "hardrock": Book(
        key="hardrock",
        name="Hard Rock Bet",
        tier=BookTier.SOFT,
        sharpness=0.16,
        max_limit=1_000,
        bettable=True,
    ),
    "bovada": Book(
        key="bovada",
        name="Bovada",
        tier=BookTier.SOFT,
        sharpness=0.14,
        max_limit=1_000,
        bettable=True,
    ),
}

# Default when a feed returns a book we have not profiled. Deliberately
# pessimistic: an unknown book gets little say in the consensus but is still
# somewhere you might find a stale price.
UNKNOWN_BOOK = Book(
    key="unknown",
    name="Unknown Book",
    tier=BookTier.SOFT,
    sharpness=0.12,
    max_limit=500,
    bettable=True,
)


def get_book(key: str) -> Book:
    """Look up a book, falling back to a conservative default."""
    normalized = key.lower().replace(" ", "").replace("_", "")
    if normalized in BOOKS:
        return BOOKS[normalized]
    for book_key, book in BOOKS.items():
        if normalized.startswith(book_key) or book_key.startswith(normalized):
            return book
    return Book(
        key=key,
        name=key.title(),
        tier=UNKNOWN_BOOK.tier,
        sharpness=UNKNOWN_BOOK.sharpness,
        max_limit=UNKNOWN_BOOK.max_limit,
        bettable=UNKNOWN_BOOK.bettable,
    )


def sharp_books() -> list[Book]:
    """Books whose prices we treat as evidence about the truth."""
    return [b for b in BOOKS.values() if b.is_sharp]


def bettable_books(available: set[str] | None = None) -> set[str]:
    """Books we can actually place bets at, optionally restricted by account.

    Pass the set of books you hold funded accounts with. Recommending a price
    at a book you cannot bet is noise, and it is the fastest way to make a
    daily card useless.
    """
    keys = {k for k, b in BOOKS.items() if b.bettable}
    if available is not None:
        keys &= {a.lower() for a in available}
    return keys


def limit_weight(book: Book) -> float:
    """Weight contribution from limit size, normalized to roughly 0..1.

    A number a book will take $50k on has been defended against everyone who
    wanted to attack it. A number with a $500 limit has not been tested.
    Logarithmic because the difference between $500 and $5,000 matters far
    more than between $25,000 and $50,000.
    """
    import math

    return min(math.log10(max(book.max_limit, 100.0)) / 5.0, 1.0)


def consensus_weight(book: Book) -> float:
    """Total weight a book gets when estimating the fair probability."""
    return book.sharpness * (0.5 + 0.5 * limit_weight(book))


def is_derivative(book_key: str) -> bool:
    """True if this book is known to copy another rather than price its own.

    Copies are not independent evidence. Counting six books that all mirror
    the same feed as six opinions is how a consensus gets falsely confident.
    """
    book = get_book(book_key)
    return book.follows is not None
