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
                        OrderIntent, OrderKind, RiskDecision, domain_for_mode)


AUTOTRADER_VERSION = "autotrader-v0.7-draft"
# v0.7: two wire corrections. `equity_basis_source` is read from the
# decision instead of hardcoded "PAPER_REPLAY" — true while the replay was
# the only risk authority, a lie once the paper ledger started sizing, and
# the dispatch gate trusts that field. And the idempotency key carries the
# ATTEMPT: without it a zone retested at the same size minted the previous
# attempt's key and read back its terminal state instead of routing.
# v0.6: the candidates are read in the ACTIVE MODE'S OWN DOMAIN. Until now
# this asked for the default read model, which derived lifecycle from the
# research replay — so a setup the simulator had already exited could not be
# READY and could not be dispatched. Measured 2026-09-11: every one of the 37
# risk-approved setups in the live baseline read CLOSED for that reason, none
# reached READY, and the paper book had never received an order. No sizing or
# routing rule changed here; this asks the right book.
# v0.5: the plan states the equity basis its size is a percentage of
# (contracts-v0.4). No arithmetic changed — `dispatch_scale` still converts
# the R and nothing converts the account — but the wire record now says
# which account was measured, which is what lets the dispatch gate refuse a
# LIVE order sized against the paper book.
# v0.4: quantity is scaled to the dispatch mode's R before an intent is
# minted. The risk fact sizes the PAPER research book (2% R, risk-v0.22); an
# order sent to TESTNET/LIVE must carry that mode's R (0.25%) or the first
# real order goes out 8x oversize. risk.dispatch_scale() owns the ratio —
# the number still has exactly one authority.


#: `pct_basis` on a risk decision -> the equity basis the wire records.
#: The replay writes "PAPER" meaning its own simulated book; the paper ledger
#: writes "PAPER_LEDGER". Neither is "VENUE_BALANCE", which is the only value
#: `execution.Coordinator.dispatch` accepts for a LIVE order — so this mapping
#: cannot accidentally unlock live routing, and an unrecognised basis falls
#: back to the most restrictive answer rather than the most permissive.
_EQUITY_BASIS = {"PAPER": "PAPER_REPLAY", "PAPER_LEDGER": "PAPER_LEDGER"}


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
    # The ATTEMPT, not just the zone. Without it a later retest of the same
    # zone at the same size mints the key of the previous attempt, reads back
    # that attempt's terminal state, and never routes.
    key = execution.intent_key(
        setup["setup_id"], mode, kind.value, str(quantity),
        None if entry is None else str(entry), setup.get("attempt_id"))
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
        # WHOSE account this size is a percentage of, read from the decision
        # rather than assumed. This said "PAPER_REPLAY" unconditionally, which
        # was true while the replay was the only risk authority and became a
        # lie the moment the paper ledger started sizing: the number came from
        # a real book and the wire kept naming the backtest. A provenance
        # field that does not track its own source is worse than none, because
        # the dispatch gate trusts it — see contracts.RiskDecision.
        equity_basis_usd=(_d(risk.get("equity_at"))
                          if risk.get("equity_at") is not None else None),
        equity_basis_source=_EQUITY_BASIS.get(
            str(risk.get("pct_basis") or ""), "PAPER_REPLAY"),
        reasons=tuple(DecisionReason(str(reason), str(reason))
                      for reason in risk.get("reasons") or ["WITHIN_LIMITS"]))
    return ExecutionPlan(
        intent=intent, risk=decision, venue=setup.get("venue") or "UNKNOWN",
        margin_mode="ISOLATED", position_mode="ONE_WAY",
        protection_deadline_seconds=5, version=AUTOTRADER_VERSION)


def run(con, *, broker=None, live_gate: dict | None = None) -> dict:
    operational = automation.operational_evidence(con)
    active = automation.status(con, live_gate=live_gate, operational=operational)
    rows = opportunities.list_candidates(
        con, domain=domain_for_mode(active.mode).value, include_history=False)
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
