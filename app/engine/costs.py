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


def record(con, profile: CostProfile = DEFAULT_COST_PROFILE) -> str:
    return store.record_manifest(con, "cost_profile", profile.payload())


def estimated_round_trip_cost(entry: Decimal, atr: Decimal,
                              profile: CostProfile = DEFAULT_COST_PROFILE) -> Decimal:
    """Maker entry plus taker protective exit, including stressed slippage."""
    return (profile.maker_rate + profile.taker_rate) * entry + \
        profile.market_slippage_atr * atr
