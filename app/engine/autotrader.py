"""Turn eligible OpportunityCandidate records into the shared execution path.

This is deliberately small: strategies, top-down alignment, expiry, costs and
risk have already spoken.  It does not invent a trade or recalculate a number;
it translates the server-owned candidate and risk decision into immutable
OrderIntent/RiskDecision/ExecutionPlan records and asks the coordinator to
route them according to the active mode.
"""
from __future__ import annotations

import hashlib
import time
from decimal import Decimal

from . import automation, execution, opportunities
from .contracts import (AutomationMode, DecisionReason, ExecutionPlan,
                        OrderIntent, OrderKind, RiskDecision)


AUTOTRADER_VERSION = "autotrader-v0.4-draft"
# v0.4: quantity is scaled to the dispatch mode's R before an intent is
# minted. The risk fact sizes the PAPER research book (2% R, risk-v0.22); an
# order sent to TESTNET/LIVE must carry that mode's R (0.25%) or the first
# real order goes out 8x oversize. risk.dispatch_scale() owns the ratio —
# the number still has exactly one authority.


def _d(value, default="0") -> Decimal:
    return Decimal(str(default if value in (None, "") else value))


def build_plan(row: dict, mode: AutomationMode) -> ExecutionPlan:
    setup = row["setup"]
    risk = row.get("risk_decision") or {}
    if not row.get("eligible") or row.get("state") != "READY":
        raise ValueError("only an eligible READY opportunity can become an intent")
    if risk.get("decision") not in ("APPROVED", "REDUCED"):
        raise ValueError("risk authority did not approve this opportunity")
    recommendation = row.get("entry_recommendation") or {}
    kind = OrderKind(recommendation.get("order_kind") or "NONE")
    if kind == OrderKind.NONE:
        raise ValueError("entry selector recommends no order")
    # The risk fact sizes the paper research book; this order goes to `mode`.
    # Scale quantity and the dollar figures together so the plan stays
    # internally consistent (execution checks plan/intent quantity equality).
    from . import risk as _risk_engine
    scale = _risk_engine.dispatch_scale(mode)
    quantity = (_d(risk.get("units")) * scale).quantize(Decimal("0.00000001"))
    if quantity <= 0:
        raise ValueError("risk authority returned no positive quantity")
    entry = None if kind == OrderKind.MARKET else _d(
        recommendation.get("limit_price") or setup.get("entry"))
    key = execution.intent_key(
        setup["setup_id"], mode, kind.value, str(quantity),
        None if entry is None else str(entry))
    intent_id = "auto-" + hashlib.sha256(
        f"{AUTOTRADER_VERSION}|{key}".encode()).hexdigest()[:32]
    intent = OrderIntent(
        intent_id=intent_id, setup_id=setup["setup_id"], mode=mode,
        symbol=setup["symbol"], direction=setup["direction"],
        order_kind=kind, quantity=quantity, entry=entry,
        stop=_d(setup["stop"]),
        targets=tuple(_d(value) for value in setup.get("targets") or []),
        reduce_only=False, created_at=int(time.time()),
        playbook_version=setup.get("version") or AUTOTRADER_VERSION,
        idempotency_key=key, timeframe=setup.get("timeframe"),
        expires_at=setup.get("expires_at"),
        entry_model=recommendation.get("entry_model"),
        maker_wait_bars=recommendation.get("maker_wait_bars"))
    decision = RiskDecision(
        approved=True, decision=risk["decision"],
        risk_usd=(_d(risk.get("risk_usd")) * scale).quantize(Decimal("0.01")),
        quantity=quantity,
        notional_usd=(_d(risk.get("notional_usd")) * scale).quantize(Decimal("0.01")),
        # Leverage is notional/equity; at fixed equity it scales with the
        # notional. Left unscaled it records 8x the truth on every
        # TESTNET/LIVE plan — a durable wire record contradicting its own
        # risk_usd, and a trap for any future gate that reads it.
        implied_leverage=(_d(risk.get("implied_leverage")) * scale).quantize(Decimal("0.01")),
        reasons=tuple(DecisionReason(str(reason), str(reason))
                      for reason in risk.get("reasons") or ["WITHIN_LIMITS"]))
    return ExecutionPlan(
        intent=intent, risk=decision, venue=setup.get("venue") or "UNKNOWN",
        margin_mode="ISOLATED", position_mode="ONE_WAY",
        protection_deadline_seconds=5, version=AUTOTRADER_VERSION)


def run(con, *, broker=None, live_gate: dict | None = None) -> dict:
    operational = automation.operational_evidence(con)
    active = automation.status(con, live_gate=live_gate, operational=operational)
    rows = opportunities.list_candidates(con, include_history=False)
    coordinator = execution.Coordinator(broker)
    routed, refused = [], []
    for row in rows:
        if row.get("state") != "READY" or not row.get("eligible"):
            continue
        try:
            plan = build_plan(row, active.mode)
            routed.append({"setup_id": row["setup"]["setup_id"],
                           **coordinator.dispatch(
                               con, plan, live_gate=live_gate,
                               operational=operational)})
        except (ValueError, execution.DispatchRejected) as exc:
            refused.append({"setup_id": row["setup"]["setup_id"],
                            "reason": str(exc)})
    return {"mode": active.mode.value, "routed": routed, "refused": refused,
            "ready_seen": len(routed) + len(refused),
            "version": AUTOTRADER_VERSION}
