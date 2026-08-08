"""Versioned public contracts shared by research, execution and the cockpit.

The fact store remains the source of history.  These immutable records are the
wire vocabulary around it: they stop paper, shadow, testnet, live and the UI
from inventing five subtly different meanings for one setup or order.

Prices and quantities stay Decimal until ``to_wire`` serialises them as exact
strings.  A browser may format those strings; it may not recalculate them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any


CONTRACT_VERSION = "contracts-v0.3-draft"


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class AutomationMode(StrEnum):
    OFF = "OFF"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class OpportunityState(StrEnum):
    WATCHING = "WATCHING"
    FORMING = "FORMING"
    READY = "READY"
    ORDER_WORKING = "ORDER_WORKING"
    POSITION_OPEN = "POSITION_OPEN"
    CLOSED = "CLOSED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class TopDownState(StrEnum):
    ALIGNED = "ALIGNED"
    CONDITIONAL = "CONDITIONAL"
    CONFLICT = "CONFLICT"
    BLOCKED = "BLOCKED"


class EvidenceStatus(StrEnum):
    RESEARCH = "RESEARCH"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    TESTNET = "TESTNET"
    LIVE_ELIGIBLE = "LIVE_ELIGIBLE"
    DISABLED = "DISABLED"


class OrderKind(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    NONE = "NONE"


class ControlOwner(StrEnum):
    BOT = "BOT"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


@dataclass(frozen=True)
class DecisionReason:
    code: str
    summary: str
    severity: str = "INFO"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketContextSnapshot:
    symbol: str
    timeframe: str
    as_of: int
    regime: str
    structure: str | None
    volatility: str | None
    liquidity_state: str | None
    data_status: str
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class TopDownDecision:
    state: TopDownState
    composite: str
    direction: str
    rungs: dict[str, str | None]
    reasons: tuple[DecisionReason, ...] = ()
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class FactorEvidence:
    factor: str
    cohort: str
    sample_size: int
    coverage: Decimal
    mean_r: Decimal | None
    uplift_r: Decimal | None
    ci_lo: Decimal | None
    ci_hi: Decimal | None
    q_value: Decimal | None
    stable: bool
    status: str
    warnings: tuple[str, ...] = ()
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class FactorGrade:
    score: Decimal | None
    grade: str
    confidence: str
    coverage: Decimal
    expected_edge_r: Decimal | None
    sample_size: int
    components: tuple[FactorEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    sizing_allowed: bool = False
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class TradeSetup:
    setup_id: str
    symbol: str
    venue: str
    timeframe: str
    horizon: str
    strategy: str
    direction: str
    regime: str | None
    confirmed_at: int
    expires_at: int | None
    entry: Decimal
    stop: Decimal
    targets: tuple[Decimal, ...]
    rr: Decimal
    invalidation: str
    top_down: TopDownDecision
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class EntryRecommendation:
    order_kind: OrderKind
    limit_price: Decimal | None
    may_convert_to_market: bool
    expires_at: int | None
    reasons: tuple[DecisionReason, ...]
    version: str = CONTRACT_VERSION
    entry_model: str | None = None
    maker_wait_bars: int | None = None


@dataclass(frozen=True)
class OpportunityCandidate:
    setup: TradeSetup
    state: OpportunityState
    eligible: bool
    quality_score: Decimal
    evidence: FactorGrade
    entry_recommendation: EntryRecommendation
    risk_decision: dict[str, Any] | None
    ranking_components: dict[str, Decimal]
    economics: dict[str, Any]
    primary_explanation: str
    strongest_counterargument: str
    reasons: tuple[DecisionReason, ...]
    legacy_rank: Decimal | None = None
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    setup_id: str
    mode: AutomationMode
    symbol: str
    direction: str
    order_kind: OrderKind
    quantity: Decimal
    entry: Decimal | None
    stop: Decimal
    targets: tuple[Decimal, ...]
    reduce_only: bool
    created_at: int
    playbook_version: str
    idempotency_key: str
    version: str = CONTRACT_VERSION
    timeframe: str | None = None
    expires_at: int | None = None
    entry_model: str | None = None
    maker_wait_bars: int | None = None


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    decision: str
    risk_usd: Decimal
    quantity: Decimal
    notional_usd: Decimal
    implied_leverage: Decimal
    reasons: tuple[DecisionReason, ...]
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ExecutionPlan:
    intent: OrderIntent
    risk: RiskDecision
    venue: str
    margin_mode: str
    position_mode: str
    protection_deadline_seconds: int = 5
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class BrokerOrder:
    broker_order_id: str | None
    client_order_id: str
    symbol: str
    status: str
    order_kind: OrderKind
    quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal | None
    reduce_only: bool
    updated_at: int
    average_fill_price: Decimal | None = None
    cumulative_fee: Decimal = Decimal(0)
    raw_code: str | None = None
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class BrokerExecution:
    execution_id: str
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str
    occurred_at: int
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class Fill:
    fill_id: str
    broker_order_id: str
    symbol: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    occurred_at: int
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class PositionSnapshot:
    position_id: str
    symbol: str
    direction: str
    quantity: Decimal
    entry: Decimal
    stop: Decimal | None
    unrealized_pnl: Decimal
    owner: ControlOwner
    reconciled: bool
    updated_at: int
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ExitDecision:
    position_id: str
    action: str
    quantity: Decimal
    order_kind: OrderKind
    reason: DecisionReason
    reduce_only: bool = True
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class AutomationStatus:
    mode: AutomationMode
    revision: int
    halted: bool
    live_submission_enabled: bool
    dispatch_allowed: bool
    promotion: dict[str, Any]
    reasons: tuple[DecisionReason, ...]
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class PromotionGate:
    key: str
    label: str
    passed: bool
    have: Any
    need: Any
    note: str
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class AchievementProgress:
    key: str
    label: str
    description: str
    progress: Decimal
    completed: bool
    completed_at: int | None
    category: str = "DISCIPLINE"
    version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class UIEvent:
    event_id: str
    severity: str
    title: str
    message: str
    occurred_at: int
    action: dict[str, str] | None = None
    requires_acknowledgement: bool = False
    version: str = CONTRACT_VERSION


def to_wire(value: Any) -> Any:
    """Convert contracts to JSON-safe values without losing decimal precision."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return to_wire(asdict(value))
    if isinstance(value, dict):
        return {str(k): to_wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_wire(v) for v in value]
    return value
