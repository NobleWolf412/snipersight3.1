"""Venue descriptors — the single place that knows what a market ALLOWS.

Before this module, `risk.ALLOW_SHORTS = False` was a global constant. That was
true of Coinbase spot and false of everything else, and it silently rejected 31%
of all validated setups (44 of 143) — every SHORT the playbook produced. A
venue capability is a property of the venue, not of the process.

Venue is derived from the symbol string, which is unambiguous across the two
venues we support and needs no schema change:
    BTC-USD   -> coinbase spot   (dash, USD quote)
    BTCUSDT   -> phemex perp     (no dash, USDT quote)
    PF_XBTUSD -> kraken perp     (PF_ prefix, USD quote)

Kraken's prefix is checked FIRST and is unambiguous: no other venue here mints a
symbol starting `PF_`. Note Kraken writes Bitcoin as XBT, so `PF_XBTUSD` and
`BTCUSDT` are the same underlying under two spellings — `universe._base_asset`
has to know that or the same coin enters the universe twice, which is the exact
double-exposure bug S33 caught between BTC-USD and BTCUSDT.

Adding a venue means adding a descriptor here plus an adapter module. Nothing
else in the engine should branch on venue by name.
"""
from dataclasses import dataclass
from decimal import Decimal

# Cost profiles live with the venue because they are venue facts. Historical
# reports must never silently rewrite these — introduce a new profile version
# instead of editing one in place.
VENUES_VERSION = "venues-v0.3-draft"
# v0.3: the REFERENCE contract — a per-symbol pointer to the deepest venue's
# candle series for analysis (operator ruling 2026-08-09), plus the `@`-key
# refusal in venue_for that keeps every money path off it. Venue descriptors
# themselves are unchanged, so nothing downstream moves.
# v0.2: Kraken Futures added (operator ruling 2026-07-30 — CFTC-regulated US
# perps settle the access question Phemex left open), and `margin_mode` is now
# DECLARED rather than implied. The liquidation model was always the isolated
# formula; it simply never said so, and an undeclared assumption under a gate
# that decides whether a stop is safe is the kind that surprises you once.


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
    #: ISOLATED or CROSS. Operator ruling 2026-07-30: **isolated**, and the
    #: reason is the whole point — under cross margin every position is backed
    #: by the entire account balance, so one bad trade can take all of it. Under
    #: isolated, a position can only lose the margin posted to it. The risk
    #: envelope in risk.py sizes by "distance to stop" and caps total open risk;
    #: cross margin would make both of those advisory, because the exchange
    #: could close a position at a loss far larger than the one that was risked.
    margin_mode: str = "ISOLATED"

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

KRAKEN_PERP = Venue(
    key="kraken-perp",
    kind="perp",
    # PF_ contracts are USD-quoted and multi-collateral.
    quote="USD",
    allow_shorts=True,
    # Same reasoning as Phemex: the venue permits far more, and we declare 10
    # deliberately. Size here is derived from RISK and leverage is the
    # CONSEQUENCE of the notional that risk implies; a high cap does not
    # increase edge, it only widens how badly a sizing mistake ends.
    max_leverage=Decimal("10"),
    # Kraken Futures retail taker/maker. Conservative: assumes no fee tier.
    maker_rate=Decimal("0.0002"),
    taker_rate=Decimal("0.0005"),
    slippage_atr=Decimal("0.05"),
    funding_settlements_per_day=24,      # hourly, unlike Phemex's 8-hourly
    cost_profile="kraken-perp-v1",
)

ALL = (COINBASE_SPOT, PHEMEX_PERP, KRAKEN_PERP)
_BY_KEY = {v.key: v for v in ALL}

#: Maintenance margin assumed by `liquidation_price`. Named rather than left as
#: an inline default because the order ticket now draws a liquidation line from
#: the same formula, and a second copy of this number in JavaScript is how the
#: UI and the engine come to disagree about where a position dies. Served to the
#: ticket by `/api/trade-config`; house convention 10, one authority per number.
#: 0.005 is the conservative first-tier figure — see `kraken.py`, which measured
#: it against the published tier table.
MAINTENANCE_MARGIN = Decimal("0.005")


def venue_for(symbol: str) -> Venue:
    """Which venue this symbol trades on. Raises on anything unrecognised —
    guessing a venue would mean guessing whether shorting is allowed."""
    if not symbol:
        raise ValueError("empty symbol")
    if "@" in symbol:
        # A REFERENCE-SERIES key (see REFERENCE below). Nothing trades on it,
        # so it has no venue — and this raise is the load-bearing half of the
        # design: sizing, liquidation, participation and fills all reach a
        # venue through this function, so a reference series is unreachable
        # from every path that touches money. The suffix rules below happen to
        # refuse these keys anyway; that is a coincidence of spelling, and
        # this check is the contract.
        raise ValueError(f"{symbol!r} is a reference-series key; it has no "
                         f"venue and nothing may be sized against it")
    if symbol.endswith("-USD"):
        return COINBASE_SPOT
    if symbol.startswith("PF_") and symbol.upper().endswith("USD"):
        return KRAKEN_PERP
    if "-" not in symbol and symbol.endswith("USDT"):
        return PHEMEX_PERP
    raise ValueError(f"cannot determine venue for symbol {symbol!r}")


# ── Reference feeds: the deepest venue's SERIES, never a venue to trade ──
#
# A thin market's own candles under-describe it — BICO-USD trades $9M/day on
# Coinbase in bursts, with 24% of its hours empty, while Binance prints the
# same market at ~$1.5M/hour nearly continuously. Price levels are shared
# across venues (arbitrage keeps them within basis points), so the deep
# venue's series is PRICE-TRUE for analysis; its liquidity is NOT yours, so
# nothing about execution may read it. Averaging venues was explicitly
# rejected (operator, 2026-08-09): an averaged bar is a price nobody traded,
# and a second authority for "what is the price".
#
# The map is the per-symbol contract, same doctrine as the venue rules above:
# stated once, absent means absent (reference_for returns None — a valid
# state, not a guess). Values are (venue_key, native_symbol_on_that_venue) —
# the cross-venue symbol spelling lives HERE and nowhere else.
#
# Pilot membership, measured 2026-08-09: BICO-USD is the only ADMITTED symbol
# with material thinness (24.5% of 1H empty; every other admitted symbol is a
# Phemex perp at 0.0%). BTCUSDT joins as the liquid CONTROL: the basis fact
# stream over-represents liquid hours on thin symbols by construction (a
# bucket the thin venue served nothing for produces no fact), so grading it
# needs a series without that bias. IMU-USD (WARMING) was probed and is not
# listed on Binance.
REFERENCE = {
    "BICO-USD": ("binance-spot", "BICOUSDT"),
    "BTCUSDT": ("binance-spot", "BTCUSDT"),
}


def reference_for(symbol: str) -> tuple[str, str] | None:
    """(venue_key, native_symbol) of this symbol's reference feed, or None.
    None is the normal state and callers must treat it as 'no feed', never
    fall back to a guess."""
    return REFERENCE.get(symbol)


def ref_key(symbol: str) -> str:
    """The storage key the reference series lives under — 'BICOUSDT@binance-spot'.

    Self-describing on purpose: the part before '@' is the venue's own symbol
    spelling (what the adapter fetches), the part after is the `source` the
    candles are labelled with. A distinct key rather than a source-column
    distinction because candles are PRIMARY KEY (symbol, tf, open_ts) with
    INSERT OR REPLACE — under the trading symbol, a reference bar would
    silently REPLACE the execution venue's bar, and execsim would fill on
    prices nobody traded at the venue the book lives on."""
    ref = REFERENCE.get(symbol)
    if ref is None:
        raise ValueError(f"{symbol!r} has no reference feed")
    venue_key, native = ref
    return f"{native}@{venue_key}"


def is_reference_key(symbol: str) -> bool:
    return "@" in (symbol or "")


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
                      maintenance_margin: Decimal = MAINTENANCE_MARGIN,
                      margin_mode: str = "ISOLATED") -> Decimal | None:
    """Approximate liquidation price for a leveraged perp position, ISOLATED.

    `(1/leverage) - maintenance` is the isolated-margin formula: the price move
    that exhausts the margin posted to THIS position. That is what the code has
    always computed — it simply never declared which mode it was pricing, which
    is how an assumption becomes a surprise.

    Under CROSS margin the answer would be different and much worse to get
    wrong: liquidation is then a function of total account equity, so the
    distance depends on every other open position and on the balance, and one
    trade can consume the whole account. Isolated bounds a position's loss to
    its own margin, which is the only mode under which `risk.py`'s "2% per
    trade" means what it says.

    Operator ruling 2026-07-30: isolated. This function REFUSES to price cross
    rather than returning the isolated number under a cross label — a
    liquidation estimate that is wrong in the optimistic direction is worse than
    no estimate, because the stop-safety gate is built on top of it.

    Returns None at 1x — an unleveraged position cannot be liquidated by price.
    """
    if margin_mode != "ISOLATED":
        raise ValueError(
            f"liquidation_price models ISOLATED margin only; got {margin_mode!r}. "
            f"Cross-margin liquidation depends on total account equity and every "
            f"other open position, and returning the isolated number here would "
            f"understate the danger the stop-safety gate exists to catch.")
    if leverage is None or leverage <= 1:
        return None
    move = (Decimal("1") / leverage) - maintenance_margin
    if move <= 0:
        return entry                      # margin allowance exceeds the buffer
    return entry * (Decimal("1") - move) if direction == "LONG" \
        else entry * (Decimal("1") + move)


def stop_survives_liquidation(entry: Decimal, sl: Decimal, leverage: Decimal,
                              direction: str,
                              margin_mode: str = "ISOLATED") -> tuple[bool, Decimal | None]:
    """Would the stop trigger BEFORE liquidation?

    Ported intent from the prior project's liquidation gate. If liquidation sits
    between entry and the stop, the position is closed by the exchange at a loss
    larger than the one that was risked — the stop becomes decorative and the
    whole R-multiple accounting is fiction. Returns (ok, liquidation_price).
    """
    liq = liquidation_price(entry, leverage, direction,
                            margin_mode=margin_mode)
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
