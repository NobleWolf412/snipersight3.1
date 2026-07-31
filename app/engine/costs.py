"""Versioned execution-cost profiles shared by setup gating and simulation.

A cost profile is a VENUE fact, not a process constant. Until now this module
exported one DEFAULT_COST_PROFILE and every consumer charged it to every
symbol: Coinbase spot rates (0.40% maker / 0.60% taker) applied to a book that
is mostly Phemex USDT perps, whose real rates are 0.01% / 0.06%. That is a ~14x
over-charge on the round trip (1.00% vs 0.07%), and because the setup gate uses
the same profile to decide whether a trade clears its own costs, perp setups
were being rejected on Coinbase fees — the gate demanded a ~14x wider stop than
the venue actually justifies before a setup counted as economic.

Rates are read from venues.py and nowhere else (§6: one authority per number).
Profiles are immutable and versioned: a historical report must never silently
re-price, so a rate change means a NEW profile version, never an edit in place.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal

from . import store, venues


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


def _from_venue(venue: venues.Venue, fee_tier: str) -> CostProfile:
    """Derive a profile from its venue descriptor.

    Nothing here retypes a rate — the numbers, and the profile version string
    itself, come from venues.py. A profile that *cannot* drift from the venue it
    claims to price is the entire point of this function.
    """
    return CostProfile(
        version=venue.cost_profile,
        venue=venue.key,
        fee_tier=fee_tier,
        maker_rate=venue.maker_rate,
        taker_rate=venue.taker_rate,
        market_slippage_atr=venue.slippage_atr,
    )


# Conservative Coinbase retail default. Spelled out literally rather than
# derived, because exec facts already in the store reference this exact
# payload's manifest hash (d0dd32c4...) and deriving it would change the
# `venue` label from 'coinbase-advanced-spot' to the venue key — a different
# hash, silently invalidating the audit trail the hash exists to provide.
# _assert_venue_rates below keeps its NUMBERS honest instead.
DEFAULT_COST_PROFILE = CostProfile(
    version="coinbase-retail-v1",
    venue="coinbase-advanced-spot",
    fee_tier="lowest-volume-conservative",
    maker_rate=Decimal("0.0040"),
    taker_rate=Decimal("0.0060"),
    market_slippage_atr=Decimal("0.05"),
)

# Phemex USDT perps. Derived, so it can never disagree with venues.PHEMEX_PERP.
PHEMEX_PERP_COST_PROFILE = _from_venue(
    venues.PHEMEX_PERP, "retail-no-tier-conservative")


def _assert_venue_rates(profile: CostProfile, venue: venues.Venue) -> None:
    """Fail loudly when a hand-written profile disagrees with its venue.

    DEFAULT_COST_PROFILE cannot be derived (its hash is load-bearing), so the
    invariant is ENFORCED rather than sourced. Editing a rate in venues.py
    without minting a new profile version is exactly the mistake this catches,
    and it catches it at import rather than in a report nobody re-reads.
    """
    mine = (profile.maker_rate, profile.taker_rate, profile.market_slippage_atr)
    theirs = (venue.maker_rate, venue.taker_rate, venue.slippage_atr)
    if mine != theirs:
        raise AssertionError(
            f"cost profile {profile.version!r} disagrees with venue "
            f"{venue.key!r}: profile has maker={mine[0]} taker={mine[1]} "
            f"slip={mine[2]}, venue has maker={theirs[0]} taker={theirs[1]} "
            f"slip={theirs[2]}. Rates are venue facts (§6) — mint a NEW cost "
            f"profile version instead of editing one in place.")


_assert_venue_rates(DEFAULT_COST_PROFILE, venues.COINBASE_SPOT)

_BY_VERSION = {p.version: p
               for p in (DEFAULT_COST_PROFILE, PHEMEX_PERP_COST_PROFILE)}


def by_version(version: str) -> CostProfile:
    """Look up an immutable profile by its version string."""
    if version not in _BY_VERSION:
        raise ValueError(
            f"unknown cost profile {version!r} — known: "
            f"{', '.join(sorted(_BY_VERSION))}")
    return _BY_VERSION[version]


def profile_for(symbol: str) -> CostProfile:
    """The cost profile of the venue this symbol trades on.

    Raises (through venues.venue_for) on an unrecognised symbol. There is
    deliberately no default: charging some fallback venue's fees is precisely
    what produced the 14x perp over-charge, and a wrong fee is not a safer
    answer than a loud one.
    """
    return by_version(venues.venue_for(symbol).cost_profile)


def record(con, profile: CostProfile) -> str:
    return store.record_manifest(con, "cost_profile", profile.payload())


def estimated_round_trip_cost(entry: Decimal, atr: Decimal,
                              profile: CostProfile) -> Decimal:
    """Maker entry plus taker protective exit, including stressed slippage.

    `profile` is required. It used to default to DEFAULT_COST_PROFILE, which
    made charging the wrong venue the path of least resistance for every
    caller — the bug this module was rewritten to remove.
    """
    return (profile.maker_rate + profile.taker_rate) * entry + \
        profile.market_slippage_atr * atr
