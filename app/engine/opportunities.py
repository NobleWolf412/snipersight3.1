"""Server-owned opportunity lifecycle, ranking and entry recommendation.

This is a read model over existing append-only setup/risk/order/exec facts.  It
does not create a second strategy engine.  In particular, the browser receives
the state, score components, exact prices and reasons already reconciled here.
"""
from __future__ import annotations

import json
import time
from decimal import Decimal, InvalidOperation

from . import execsim, registry, risk, setups, store, venues
from .contracts import (DecisionReason, EntryRecommendation, FactorGrade,
                        OpportunityCandidate, OpportunityState, OrderKind,
                        TopDownDecision, TopDownState, TradeSetup, to_wire)


OPPORTUNITY_VERSION = "opportunity-v0.2-draft"


def _decimal(value, default="0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def top_down(payload: dict, *, hard_blocked: bool = False) -> TopDownDecision:
    block = payload.get("bias") or {}
    composite = str(block.get("composite") or "UNKNOWN")
    alignment = str(block.get("alignment") or "UNKNOWN")
    resolved = str(block.get("resolved") or "ALLOW")
    rungs = block.get("rungs") if isinstance(block.get("rungs"), dict) else {}
    reasons = []
    if hard_blocked or resolved == "BLOCK":
        state = TopDownState.BLOCKED
        reasons.append(DecisionReason(
            "TOP_DOWN_BLOCK", "The higher-timeframe policy blocks this entry.",
            "CRITICAL"))
    elif alignment == "WITH":
        state = TopDownState.ALIGNED
        reasons.append(DecisionReason(
            "TOP_DOWN_ALIGNED", "The higher-timeframe ladder supports the trade."))
    elif alignment in ("AGAINST", "MIXED"):
        state = TopDownState.CONFLICT
        reasons.append(DecisionReason(
            "TOP_DOWN_CONFLICT", "The higher-timeframe ladder conflicts with "
            "or disagrees about this direction.", "WARNING"))
    else:
        state = TopDownState.CONDITIONAL
        reasons.append(DecisionReason(
            "TOP_DOWN_CONDITIONAL", "The higher-timeframe ladder is flat or "
            "does not have enough confirmed information.", "WARNING"))
    return TopDownDecision(state=state, composite=composite,
                           direction=str(payload.get("direction") or "UNKNOWN"),
                           rungs=rungs, reasons=tuple(reasons),
                           version=OPPORTUNITY_VERSION)


def lifecycle(setup_state: str, risk_fact: dict | None = None,
              order: dict | None = None, execution: dict | None = None) -> OpportunityState:
    state = (setup_state or "").upper()
    if execution and execution.get("outcome") not in (None, "PENDING"):
        return OpportunityState.CLOSED
    event = str((order or {}).get("event") or "").upper()
    if event == "FILLED":
        return OpportunityState.POSITION_OPEN
    if event in ("PLACED", "PARTIALLY_FILLED", "UNTRIGGERED"):
        return OpportunityState.ORDER_WORKING
    if event in ("CANCELLED", "CANCELED"):
        return OpportunityState.CANCELLED
    if event == "MISSED":
        return OpportunityState.EXPIRED
    decision = str((risk_fact or {}).get("decision") or "").upper()
    if decision == "REJECTED":
        return OpportunityState.BLOCKED
    if state == "VALIDATED":
        return OpportunityState.READY
    if state in ("FORMING", "CONFIRMING"):
        return OpportunityState.FORMING
    if state == "CANCELLED":
        return OpportunityState.CANCELLED
    if state == "EXPIRED":
        return OpportunityState.EXPIRED
    if state == "REJECTED":
        return OpportunityState.REJECTED
    return OpportunityState.WATCHING


def recommend_entry(payload: dict, state: OpportunityState,
                    *, blocked: bool = False) -> EntryRecommendation:
    strategy = str(payload.get("strategy") or "").upper()
    entry = _decimal(payload.get("entry")) if payload.get("entry") is not None else None
    expires = payload.get("expires_at_ts") or payload.get("expires_at")
    if blocked or state in {OpportunityState.BLOCKED, OpportunityState.REJECTED,
                            OpportunityState.EXPIRED, OpportunityState.CANCELLED,
                            OpportunityState.CLOSED}:
        return EntryRecommendation(
            OrderKind.NONE, None, False, expires,
            (DecisionReason("NO_TRADE", "No order is permitted in the current state.",
                            "WARNING"),), OPPORTUNITY_VERSION)

    if strategy in {"BREAKOUT_RETEST", "LIQUIDITY_SWEEP_REVERSAL",
                    "COMPRESSION_RELEASE"} and state == OpportunityState.READY:
        return EntryRecommendation(
            OrderKind.MARKET, None, False, expires,
            (DecisionReason("TIME_SENSITIVE_TRIGGER",
                            "The confirmed trigger is time-sensitive; use market "
                            "only while cost and slippage checks remain valid."),),
            OPPORTUNITY_VERSION, entry_model="MARKET_NEXT_OPEN")

    may_cross = str(payload.get("entry_model") or setups.ENTRY_MODEL).upper() == "MAKER_THEN_MARKET"
    return EntryRecommendation(
        OrderKind.LIMIT, entry, may_cross, expires,
        (DecisionReason("STRUCTURE_LIMIT",
                        "Rest the entry at the structure-defined price instead "
                        "of chasing the market."),), OPPORTUNITY_VERSION,
        entry_model="MAKER_THEN_MARKET" if may_cross else "MAKER_PULLBACK",
        maker_wait_bars=setups.MAKER_WAIT_BARS)


def _quality(payload: dict, state: OpportunityState) -> tuple[Decimal, dict[str, Decimal]]:
    rr = max(Decimal(0), min(_decimal(payload.get("rr")), Decimal(3)))
    confluence = payload.get("confluence") if isinstance(payload.get("confluence"), dict) else {}
    measured = sum(1 for value in confluence.values() if value is not None)
    coverage = Decimal(min(measured, 10)) / Decimal(10)
    strength = max(Decimal(0), min(_decimal(payload.get("zone_strength")), Decimal(5)))
    urgency = Decimal(1) if state == OpportunityState.READY else (
        Decimal("0.5") if state == OpportunityState.FORMING else Decimal(0))
    parts = {
        "reward_to_risk": (rr / Decimal(3) * Decimal(40)).quantize(Decimal("0.01")),
        "structure_quality": (strength / Decimal(5) * Decimal(30)).quantize(Decimal("0.01")),
        "factor_coverage": (coverage * Decimal(20)).quantize(Decimal("0.01")),
        "trigger_urgency": (urgency * Decimal(10)).quantize(Decimal("0.01")),
        # Evidence edge deliberately contributes zero until a calibrated,
        # setup-specific FactorGrade exists. No legacy rank laundering.
        "evidence_edge": Decimal("0.00"),
    }
    return sum(parts.values(), Decimal(0)).quantize(Decimal("0.01")), parts


def _ungraded(payload: dict) -> FactorGrade:
    confluence = payload.get("confluence") if isinstance(payload.get("confluence"), dict) else {}
    measured = sum(1 for value in confluence.values() if value is not None)
    coverage = (Decimal(measured) / Decimal(max(1, len(confluence)))) if confluence else Decimal(0)
    return FactorGrade(
        score=None, grade="UNGRADED", confidence="INSUFFICIENT_EVIDENCE",
        coverage=coverage.quantize(Decimal("0.0001")), expected_edge_r=None,
        sample_size=0, components=(),
        warnings=("No setup-specific, out-of-sample factor calibration is available; "
                  "quality may rank this card but cannot increase its size.",),
        sizing_allowed=False, version=OPPORTUNITY_VERSION)


def candidate(payload: dict, *, risk_fact: dict | None = None,
              order: dict | None = None, execution: dict | None = None,
              now: int | None = None) -> OpportunityCandidate:
    state = lifecycle(payload.get("state", "WATCHING"), risk_fact, order, execution)
    expires_at = payload.get("expires_at_ts") or payload.get("expires_at")
    if now is not None and state in {
            OpportunityState.READY, OpportunityState.FORMING,
            OpportunityState.WATCHING}:
        try:
            if expires_at is None:
                # Every executable playbook owns an expiry. A legacy or damaged
                # setup without one can remain visible but cannot become risk.
                state = OpportunityState.BLOCKED
            elif int(expires_at) <= int(now):
                state = OpportunityState.EXPIRED
        except (TypeError, ValueError):
            # An unreadable expiry is unsafe for an entry decision.
            state = OpportunityState.BLOCKED
    hard_blocked = state in {OpportunityState.BLOCKED, OpportunityState.REJECTED}
    td = top_down(payload, hard_blocked=hard_blocked)
    alignment_blocked = td.state in {TopDownState.CONFLICT, TopDownState.BLOCKED}
    conditional_hold = td.state == TopDownState.CONDITIONAL
    if alignment_blocked and state in {OpportunityState.READY, OpportunityState.FORMING}:
        state = OpportunityState.BLOCKED
    quality, components = _quality(payload, state)
    strategy_name = str(payload.get("strategy") or "UNKNOWN").upper()
    reg = registry.for_engine_name(strategy_name)
    horizon = reg.horizon if reg else str(payload.get("horizon") or "unknown")
    targets = tuple(_decimal(x) for x in (payload.get("targets") or
                    ([payload.get("tp")] if payload.get("tp") is not None else [])))
    # Early setup-v0.17 facts omitted symbol/tf even though both remain part of
    # the canonical setup_id. Hydrate the server-owned read model here so every
    # browser sees one identity; never make each client parse it independently.
    setup_id = str(payload.get("setup_id") or "")
    identity = setup_id.split("|")
    symbol = str(payload.get("symbol") or (identity[0] if len(identity) > 1 else ""))
    timeframe = str(payload.get("tf") or (identity[1] if len(identity) > 1 else ""))
    try:
        venue = venues.venue_for(symbol).key
    except ValueError:
        venue = "UNKNOWN"
    setup = TradeSetup(
        setup_id=setup_id,
        symbol=symbol, venue=venue,
        timeframe=timeframe, horizon=horizon,
        strategy=strategy_name, direction=str(payload.get("direction") or ""),
        regime=payload.get("regime"),
        confirmed_at=int(payload.get("confirmed_at") or 0),
        expires_at=expires_at,
        entry=_decimal(payload.get("entry")), stop=_decimal(payload.get("sl")),
        targets=targets, rr=_decimal(payload.get("rr")),
        invalidation=str(payload.get("invalidation") or
                         "The structure-defined stop is the invalidation."),
        top_down=td, version=OPPORTUNITY_VERSION)
    reasons = list(td.reasons)
    if risk_fact and risk_fact.get("reasons"):
        reasons.extend(DecisionReason(str(code), str(code),
                                      "CRITICAL" if hard_blocked else "INFO")
                       for code in risk_fact["reasons"])
    eligible = state in {OpportunityState.READY, OpportunityState.FORMING,
                         OpportunityState.ORDER_WORKING,
                         OpportunityState.POSITION_OPEN} and not hard_blocked and \
               not alignment_blocked and not conditional_hold
    evidence = _ungraded(payload)
    primary = str(payload.get("why") or reasons[0].summary)
    if hard_blocked:
        counterargument = "The risk authority rejected this setup."
    elif td.state == TopDownState.CONFLICT:
        counterargument = "Higher-timeframe structure conflicts with this direction."
    elif evidence.warnings:
        counterargument = evidence.warnings[0]
    else:
        counterargument = "No material contraindication is recorded."
    economics = {
        "risk_usd": (risk_fact or {}).get("risk_usd"),
        "notional_usd": (risk_fact or {}).get("notional_usd"),
        "fee_r": payload.get("fee_r") or payload.get("estimated_fee_r"),
        "funding_r": payload.get("funding_r") or payload.get("estimated_funding_r"),
        "slippage_r": payload.get("slippage_r") or payload.get("estimated_slippage_r"),
        "total_cost_r": payload.get("costs_r") or payload.get("estimated_cost_r"),
        "distance_atr": payload.get("distance_atr") or payload.get("prox_atr"),
    }
    return OpportunityCandidate(
        setup=setup, state=state, eligible=eligible, quality_score=quality,
        evidence=evidence,
        entry_recommendation=recommend_entry(
            payload, state,
            blocked=hard_blocked or alignment_blocked or conditional_hold),
        risk_decision=risk_fact, ranking_components=components,
        economics=economics, primary_explanation=primary,
        strongest_counterargument=counterargument,
        reasons=tuple(reasons),
        legacy_rank=_decimal(payload.get("rank")) if payload.get("rank") is not None else None,
        version=OPPORTUNITY_VERSION)


_STATE_ORDER = {
    OpportunityState.POSITION_OPEN: 0,
    OpportunityState.ORDER_WORKING: 1,
    OpportunityState.READY: 2,
    OpportunityState.FORMING: 3,
    OpportunityState.WATCHING: 4,
    OpportunityState.BLOCKED: 5,
    OpportunityState.REJECTED: 6,
    OpportunityState.EXPIRED: 7,
    OpportunityState.CANCELLED: 8,
    OpportunityState.CLOSED: 9,
}


def rank(candidates: list[OpportunityCandidate]) -> list[OpportunityCandidate]:
    """Deterministic order; the legacy volume/confluence rank is not consulted."""
    return sorted(candidates, key=lambda c: (
        _STATE_ORDER[c.state], -c.quality_score,
        c.setup.expires_at if c.setup.expires_at is not None else 2**63,
        c.setup.symbol, c.setup.timeframe, c.setup.setup_id))


def _latest_by_setup(con, kind: str, version: str, since: int) -> dict[str, dict]:
    out = {}
    for confirmed_at, raw in con.execute(
            "SELECT confirmed_at,payload FROM facts WHERE kind=? AND algo_version=? "
            "AND confirmed_at>=? ORDER BY confirmed_at,id", (kind, version, since)):
        payload = json.loads(raw)
        sid = payload.get("setup_id")
        if sid:
            payload["confirmed_at"] = confirmed_at
            out[sid] = payload
    return out


def list_candidates(con, *, include_history: bool = True, now: int | None = None) -> list[dict]:
    observed_at = int(time.time()) if now is None else int(now)
    baseline = store.get_active_baseline(con)
    since = int(baseline["started_at"])
    setups_by_id = _latest_by_setup(con, "setup", setups.SETUP_VERSION, since)
    risk_by_id = _latest_by_setup(con, "risk", risk.RISK_VERSION, since)
    order_by_id = _latest_by_setup(con, "order", execsim.EXEC_VERSION, since)
    exec_by_id = _latest_by_setup(con, "exec", execsim.EXEC_VERSION, since)
    items = []
    for sid, payload in setups_by_id.items():
        payload.setdefault("setup_id", sid)
        item = candidate(payload, risk_fact=risk_by_id.get(sid),
                         order=order_by_id.get(sid), execution=exec_by_id.get(sid),
                         now=observed_at)
        if not include_history and item.state in {
                OpportunityState.CLOSED, OpportunityState.EXPIRED,
                OpportunityState.CANCELLED, OpportunityState.REJECTED}:
            continue
        items.append(item)
    return [to_wire(item) for item in rank(items)]


def summary(rows: list[dict]) -> dict:
    counts = {state.value: 0 for state in OpportunityState}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    actionable = counts["READY"] + counts["FORMING"]
    if counts["POSITION_OPEN"]:
        count = counts["POSITION_OPEN"]
        narrative = f"Managing {count} open position{'s' if count != 1 else ''}."
    elif counts["ORDER_WORKING"]:
        count = counts["ORDER_WORKING"]
        narrative = (f"{count} order{'s are' if count != 1 else ' is'} working; "
                     "protection remains monitored.")
    elif actionable:
        narrative = (f"{counts['READY']} ready and {counts['FORMING']} forming "
                     f"setup{'s' if actionable != 1 else ''} "
                     f"{'deserve' if actionable != 1 else 'deserves'} review.")
    else:
        narrative = "No setup currently meets entry rules. Scanning continues."
    return {"counts": counts, "actionable": actionable,
            "narrative": narrative, "version": OPPORTUNITY_VERSION}
