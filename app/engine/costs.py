"""Versioned execution-cost profiles shared by setup gating and simulation."""
from dataclasses import asdict, dataclass
from decimal import Decimal

from . import store


@dataclass(frozen=True)
class CostProfile:
    version: str
    venue: str
    fee_tier: str
    maker_rate: Decimal
    taker_rate: Decimal
    market_slippage_atr: Decimal

    def payload(self) -> dict:
        return {k: str(v) if isinstance(v, Decimal) else v
                for k, v in asdict(self).items()}


# Conservative Coinbase retail default. A deployment may introduce another
# immutable profile, but historical reports must never silently rewrite this.
DEFAULT_COST_PROFILE = CostProfile(
    version="coinbase-retail-v1",
    venue="coinbase-advanced-spot",
    fee_tier="lowest-volume-conservative",
    maker_rate=Decimal("0.0040"),
    taker_rate=Decimal("0.0060"),
    market_slippage_atr=Decimal("0.05"),
)

PHEMEX_PERP_COST_PROFILE = CostProfile(
    version="phemex-perp-v1",
    venue="phemex-perp",
    fee_tier="retail-no-tier-conservative",
    maker_rate=Decimal("0.0001"),
    taker_rate=Decimal("0.0006"),
    market_slippage_atr=Decimal("0.05"),
)

KRAKEN_PERP_COST_PROFILE = CostProfile(
    version="kraken-perp-v1",
    venue="kraken-perp",
    fee_tier="retail-no-tier-conservative",
    maker_rate=Decimal("0.0002"),
    taker_rate=Decimal("0.0005"),
    market_slippage_atr=Decimal("0.05"),
)

_BY_VENUE_KEY = {
    "coinbase-spot": DEFAULT_COST_PROFILE,
    "phemex-perp": PHEMEX_PERP_COST_PROFILE,
    "kraken-perp": KRAKEN_PERP_COST_PROFILE,
}

_BY_VERSION = {p.version: p for p in _BY_VENUE_KEY.values()}


def by_version(version: str) -> CostProfile:
    """The immutable profile a recorded fact refers to.

    Raises on an unknown version rather than substituting a live profile: an
    exec fact's `cost_manifest_hash` is its PROOF of what it was charged, and
    silently answering with today's rates would let a historical report be
    re-priced without anything saying so.
    """
    if version not in _BY_VERSION:
        raise ValueError(f"unknown cost profile version {version!r}")
    return _BY_VERSION[version]


def _assert_venue_rates(profile: CostProfile, venue) -> None:
    """One authority per number (§6): a profile must not restate a venue's rates.

    Profiles are immutable and versioned because facts reference them; venues
    carry the live capability table. They therefore duplicate three numbers, and
    duplication drifts. This runs at import so editing a rate in `venues.py`
    without minting a NEW profile version fails loudly at startup instead of
    quietly re-pricing history.
    """
    for attr, vattr in (("maker_rate", "maker_rate"),
                        ("taker_rate", "taker_rate"),
                        ("market_slippage_atr", "slippage_atr")):
        ours, theirs = getattr(profile, attr), getattr(venue, vattr)
        assert ours == theirs, (
            f"cost profile {profile.version} {attr}={ours} disagrees with venue "
            f"{venue.key} {vattr}={theirs} — mint a new profile version rather "
            f"than editing rates in place")


def _check_profiles_match_venues() -> None:
    from . import venues as _venues
    for v in _venues.ALL:
        _assert_venue_rates(by_version(v.cost_profile), v)


def profile_for(symbol: str | None) -> CostProfile:
    """The cost profile of the venue THIS symbol trades on.

    Fixed 2026-07-30. Both the setup economics gate and the execution simulator
    used the module-level Coinbase default unconditionally, and the traded
    universe has been 100% Phemex perps since S34. Measured consequence, on all
    232 recorded exec facts: one cost manifest, `coinbase-retail-v1`, charging a
    1.00% round trip against the venue's real 0.07% — a ~14x over-charge on the
    perp book.

    It mattered in both directions, and the gate direction matters more:
    `setups.MIN_RISK_COST_MULT` requires risk >= K x round-trip cost, so a 14x
    inflated cost demanded a ~14x wider stop before a setup was considered
    economic. That is a large share of the 675 UNECONOMIC_AFTER_COSTS
    rejections, and it also pushed surviving setups toward the wide stops and
    distant targets this version exists to fix.

    An unrecognised symbol RAISES. Falling back to a default profile is the
    original bug in miniature: it is exactly how every perp came to be priced at
    Coinbase rates without anything failing. A wrong fee is not a safer answer
    than a loud failure — it is the same wrong answer, only harder to find. Every
    symbol in the traded universe resolves (spot, Phemex and Kraken all do), so
    a raise here means a genuinely unknown instrument reached pricing.
    """
    from . import venues
    if not symbol:
        raise ValueError("cannot price an empty symbol")
    venue = venues.venue_for(symbol)          # raises on an unknown instrument
    if venue.key not in _BY_VENUE_KEY:
        raise ValueError(f"no cost profile registered for venue {venue.key!r}")
    return _BY_VENUE_KEY[venue.key]


def record(con, profile: CostProfile = DEFAULT_COST_PROFILE) -> str:
    return store.record_manifest(con, "cost_profile", profile.payload())


# Expected hold, in bars of the setup's own timeframe, used ONLY to price
# funding into the pre-trade economics gate. A model, not a measurement — but
# grounded: the recorded book's median holds are 7 (15m), 8 (1H), 6 (4H), 5 (1D)
# and 14 (1W). Ten is a round number above most of them, which errs toward
# charging MORE funding than the median trade will pay. Erring the other way
# would let a setup pass a gate it has not earned.
EXPECTED_HOLD_BARS = 10
DEFAULT_FUNDING_RATE = Decimal("0.0001")


def estimated_round_trip_cost(entry: Decimal, atr: Decimal,
                              profile: CostProfile,
                              *, symbol: str | None = None,
                              tf_seconds: int | None = None,
                              funding_rate: Decimal | None = None) -> Decimal:
    """Maker entry plus taker protective exit, stressed slippage, AND funding.

    Funding was missing here, and its absence had a direction: on a perp the
    holder pays it every settlement, so a gate that ignored it let multi-day
    swing setups through on economics they do not have. The redesign plan said
    so in as many words — "a multi-day swing long pays funding repeatedly, which
    changes whether a setup is economic" — and the gate never did it.

    Funding is priced only when the caller supplies `symbol` and `tf_seconds`,
    so no existing caller silently changes meaning. Spot venues declare zero
    settlements a day, so the term vanishes there by venue declaration rather
    than by a branch here.
    """
    cost = (profile.maker_rate + profile.taker_rate) * entry + \
        profile.market_slippage_atr * atr
    if symbol and tf_seconds:
        from . import venues
        rate = DEFAULT_FUNDING_RATE if funding_rate is None else funding_rate
        hours = Decimal(EXPECTED_HOLD_BARS * tf_seconds) / Decimal(3600)
        cost += venues.funding_cost_rate(symbol, rate, hours) * entry
    return cost


# Fail at import, not at the first mispriced trade.
_check_profiles_match_venues()
