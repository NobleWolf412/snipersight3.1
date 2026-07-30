"""Venue descriptors — the single place that knows what a market ALLOWS.

Before this module, `risk.ALLOW_SHORTS = False` was a global constant. That was
true of Coinbase spot and false of everything else, and it silently rejected 31%
of all validated setups (44 of 143) — every SHORT the playbook produced. A
venue capability is a property of the venue, not of the process.

Venue is derived from the symbol string, which is unambiguous across the two
venues we support and needs no schema change:
    BTC-USD   -> coinbase spot   (dash, USD quote)
    BTCUSDT   -> phemex perp     (no dash, USDT quote)

Adding a venue means adding a descriptor here plus an adapter module. Nothing
else in the engine should branch on venue by name.
"""
from dataclasses import dataclass
from decimal import Decimal

# Cost profiles live with the venue because they are venue facts. Historical
# reports must never silently rewrite these — introduce a new profile version
# instead of editing one in place.
VENUES_VERSION = "venues-v0.1-draft"


@dataclass(frozen=True)
class Venue:
    key: str
    kind: str                       # 'spot' | 'perp'
    quote: str
    allow_shorts: bool
    max_leverage: Decimal
    maker_rate: Decimal
    taker_rate: Decimal
    slippage_atr: Decimal
    # Perps charge funding while a position is open. Spot does not.
    funding_settlements_per_day: int
    cost_profile: str

    @property
    def is_perp(self) -> bool:
        return self.kind == "perp"


COINBASE_SPOT = Venue(
    key="coinbase-spot",
    kind="spot",
    quote="USD",
    # Spot inventory shorting is unsupported: you cannot sell what you do not
    # hold. This is a venue fact, not a risk preference.
    allow_shorts=False,
    max_leverage=Decimal("1"),
    maker_rate=Decimal("0.0040"),
    taker_rate=Decimal("0.0060"),
    slippage_atr=Decimal("0.05"),
    funding_settlements_per_day=0,
    cost_profile="coinbase-retail-v1",
)

PHEMEX_PERP = Venue(
    key="phemex-perp",
    kind="perp",
    quote="USDT",
    allow_shorts=True,
    # The venue permits up to 100x. We declare 10 deliberately: position size
    # here is derived from RISK, and leverage is the CONSEQUENCE of the notional
    # that risk implies. A high cap does not increase edge, it only widens how
    # badly a sizing mistake ends. Raise it only with a version bump.
    max_leverage=Decimal("10"),
    # Phemex USDT-perp retail taker/maker. Conservative: assumes no fee tier.
    maker_rate=Decimal("0.0001"),
    taker_rate=Decimal("0.0006"),
    slippage_atr=Decimal("0.05"),
    funding_settlements_per_day=3,          # 8-hourly
    cost_profile="phemex-perp-v1",
)

ALL = (COINBASE_SPOT, PHEMEX_PERP)
_BY_KEY = {v.key: v for v in ALL}


def venue_for(symbol: str) -> Venue:
    """Which venue this symbol trades on. Raises on anything unrecognised —
    guessing a venue would mean guessing whether shorting is allowed."""
    if not symbol:
        raise ValueError("empty symbol")
    if symbol.endswith("-USD"):
        return COINBASE_SPOT
    if "-" not in symbol and symbol.endswith("USDT"):
        return PHEMEX_PERP
    raise ValueError(f"cannot determine venue for symbol {symbol!r}")


def by_key(key: str) -> Venue:
    if key not in _BY_KEY:
        raise ValueError(f"unknown venue {key!r}")
    return _BY_KEY[key]


def allow_shorts(symbol: str) -> bool:
    return venue_for(symbol).allow_shorts


def max_leverage(symbol: str) -> Decimal:
    return venue_for(symbol).max_leverage


def round_trip_cost_rate(symbol: str) -> Decimal:
    """Fee rate paid on notional for one full round trip (maker in, taker out)."""
    v = venue_for(symbol)
    return v.maker_rate + v.taker_rate


def liquidation_price(entry: Decimal, leverage: Decimal, direction: str,
                      maintenance_margin: Decimal = Decimal("0.005")) -> Decimal | None:
    """Approximate liquidation price for a leveraged perp position.

    Returns None at 1x — an unleveraged position cannot be liquidated by price.
    The maintenance-margin allowance makes this CONSERVATIVE (liquidation is
    modelled as nearer than the naive 1/leverage estimate), because the failure
    we must avoid is believing the stop is safe when it is not.
    """
    if leverage is None or leverage <= 1:
        return None
    move = (Decimal("1") / leverage) - maintenance_margin
    if move <= 0:
        return entry                      # margin allowance exceeds the buffer
    return entry * (Decimal("1") - move) if direction == "LONG" \
        else entry * (Decimal("1") + move)


def stop_survives_liquidation(entry: Decimal, sl: Decimal, leverage: Decimal,
                              direction: str) -> tuple[bool, Decimal | None]:
    """Would the stop trigger BEFORE liquidation?

    Ported intent from the prior project's liquidation gate. If liquidation sits
    between entry and the stop, the position is closed by the exchange at a loss
    larger than the one that was risked — the stop becomes decorative and the
    whole R-multiple accounting is fiction. Returns (ok, liquidation_price).
    """
    liq = liquidation_price(entry, leverage, direction)
    if liq is None:
        return True, None
    return (sl > liq, liq) if direction == "LONG" else (sl < liq, liq)


def funding_cost_rate(symbol: str, rate_per_settlement: Decimal,
                      holding_hours: Decimal) -> Decimal:
    """Funding paid on notional over a holding period. Zero on spot.

    Funding is charged repeatedly, not once. A perp held over a weekend pays
    every settlement, and on a tight target that can exceed the edge — the same
    arithmetic that made intraday spot uneconomic.
    """
    v = venue_for(symbol)
    if not v.funding_settlements_per_day:
        return Decimal("0")
    hours_per = Decimal(24) / v.funding_settlements_per_day
    settlements = holding_hours / hours_per
    return rate_per_settlement * settlements
