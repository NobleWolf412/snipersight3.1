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


CONTRACT_VERSION = "contracts-v0.5-draft"
# v0.5: an opportunity states WHICH EXECUTION DOMAIN its lifecycle came from,
# and carries an `attempt_id` for the occurrence rather than the zone. Before
# this the read model derived ORDER_WORKING / POSITION_OPEN / CLOSED from the
# research simulator's facts for every caller including the autotrader, so a
# setup the replay had already exited could never be READY. Measured
# 2026-09-11: all 37 risk-approved setups in the live baseline read CLOSED
# because the simulator had settled them, zero reached READY, and the paper
# book was empty in consequence. `domain` is what makes "absence of a record
# means this domain has not acted" expressible; without it the sentence has no
# subject.
# v0.4: a RiskDecision states its EQUITY BASIS — the account balance the size
# is a percentage of, and where that figure was read. Every dispatched size
# descends from the paper research book's replayed equity ($9,317 today);
# `dispatch_scale` converts the R (2% -> 0.25%) and nothing converts the
# ACCOUNT. On a $1,000 funded account the resulting order risks 2.3% per
# trade, and the 2R/4R envelope that is supposed to contain it lives entirely
# inside the paper replay. Recording the basis is what lets the dispatch gate
# refuse a real-money order sized against a book that is not the one paying.


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class AutomationMode(StrEnum):
    OFF = "OFF"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class ExecutionDomain(StrEnum):
    """Whose order records decide an opportunity's lifecycle.

    NOT the same axis as `AutomationMode`, and the difference is the whole
    reason this exists. A mode says what the dispatcher is allowed to do;
    a domain says whose account of an attempt you are reading. RESEARCH is a
    domain and never a mode — the replay simulates continuously whatever the
    dispatcher is set to. SHADOW is a mode and never a domain — it writes
    PAPER records. Collapsing the two is what let the simulator's exits
    decide whether the paper book could trade.

    The rule every reader here obeys: **absence of a record in a domain means
    that domain has not acted.** It is never a reason to consult another one.
    """

    RESEARCH = "RESEARCH"
    PAPER = "PAPER"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


def domain_for_mode(mode: AutomationMode) -> ExecutionDomain:
    """Whose records a dispatcher running in `mode` reads and writes.

    SHADOW maps to PAPER because that is literally what it writes — the
    coordinator mints a paper intent alongside every shadow one, so the paper
    outbox is where a SHADOW dispatcher's account of itself lives. OFF maps to
    PAPER for the same reason: an OFF dispatcher still queues the intent and
    records HELD_OFF against the paper book.

    RESEARCH is deliberately unreachable from any mode. The replay is not a
    dispatcher and no dispatcher may read its records as its own.
    """
    if mode in (AutomationMode.TESTNET, AutomationMode.LIVE):
        return ExecutionDomain(mode.value)
    return ExecutionDomain.PAPER


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
    #: The occurrence, where `setup_id` is only the zone. `setup_id` is
    #: `symbol|tf|strategy|zone_id|version` and the zone carries its own
    #: FORMATION time, so one zone touch re-derives under the same id at every
    #: engine bump — UNIQUE per attempt in practice today (833 VALIDATED facts,
    #: 833 distinct ids), but five ids for one touch across v0.13-v0.17, which
    #: brought a hand-closed position back as live exposure (manual.py, audit
    #: 2026-08-06). So this is built to MERGE: version-stripped zone plus the
    #: CONFIRMING bar, which describes the market and survives an engine bump.
    #: Required rather than defaulted — an identity that can silently go
    #: missing is worse than one that fails loudly at construction.
    attempt_id: str
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
    #: Which domain's records produced `state`. A reader that shows a state
    #: without showing this is the defect convention 9 forbids: two surfaces
    #: reporting different lifecycles for one setup, both correct, neither
    #: saying whose account it is reading.
    domain: str = ExecutionDomain.RESEARCH.value
    #: What the research replay believes happened to this setup, when the
    #: domain above is not RESEARCH. DISPLAY ONLY — it never reaches `state`
    #: and never reaches `eligible`. This is the field that lets a screen keep
    #: showing "the simulator closed this at +1.2R" while the paper domain
    #: correctly reports the same setup as READY.
    research_story: dict[str, Any] | None = None


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
    #: WHOSE money this size is a percentage of, and where that figure came
    #: from. Every size on this record is derived from the PAPER research
    #: book's replayed equity — `dispatch_scale` converts the R, not the
    #: account — so a TESTNET/LIVE order carries a percentage of an account
    #: it was never measured against. On a funded account smaller than the
    #: paper book that is silently oversize, and nothing on the wire said so.
    #: `equity_basis_source` is the guard's whole point: only "VENUE_BALANCE"
    #: means the number was read from the account the order will actually
    #: hit. See execution.Coordinator.dispatch.
    equity_basis_usd: Decimal | None = None
    equity_basis_source: str = "PAPER_REPLAY"
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
