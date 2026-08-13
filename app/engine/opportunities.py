"""Server-owned opportunity lifecycle, ranking and entry recommendation.

This is a read model over existing append-only setup/risk/order/exec facts.  It
does not create a second strategy engine.  In particular, the browser receives
the state, score components, exact prices and reasons already reconciled here.
"""
from __future__ import annotations

import dataclasses
import json
import time
from decimal import Decimal, InvalidOperation

from . import execsim, registry, risk, setups, store, venues
from .contracts import (DecisionReason, EntryRecommendation, FactorGrade,
                        OpportunityCandidate, OpportunityState, OrderKind,
                        TopDownDecision, TopDownState, TradeSetup, to_wire)


OPPORTUNITY_VERSION = "opportunity-v0.5-draft"
# v0.5: cockpit copy translates risk codes into trader-readable decisions,
# unavailable setup-specific grades no longer masquerade as a reason to pass,
# and portfolio/expiry blocks no longer falsify the independent top-down state.
# v0.4: risk rejection outranks counterfactual simulator outcomes, and entry
# eligibility is reserved for a READY setup instead of including progress or
# already-active lifecycle states.
# v0.3: real custody overlays the paper lifecycle. The read model derived
# ORDER_WORKING / POSITION_OPEN / CLOSED from simulator facts only, so with a
# real testnet position open and no matching paper exec fact, /api/operations
# said "No setup currently meets entry rules. Scanning continues." — a false
# record on the one surface the operator trusts. Custody state's OWNER stays
# the outbox and managed_positions; this module reads it, exactly as it reads
# risk facts. A PAPER-only database produces byte-identical output.


def _decimal(value, default="0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def top_down(payload: dict) -> TopDownDecision:
    block = payload.get("bias") or {}
    composite = str(block.get("composite") or "UNKNOWN")
    alignment = str(block.get("alignment") or "UNKNOWN")
    resolved = str(block.get("resolved") or "ALLOW")
    rungs = block.get("rungs") if isinstance(block.get("rungs"), dict) else {}
    reasons = []
    if resolved == "BLOCK":
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
    # Risk is the authority for whether a shadow order was ever allowed to
    # become exposure. execsim deliberately records counterfactual fills even
    # when risk rejects them; those facts remain evidence, not custody.
    decision = str((risk_fact or {}).get("decision") or "").upper()
    if decision == "REJECTED":
        return OpportunityState.BLOCKED
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
    if blocked or state != OpportunityState.READY:
        summary = {
            OpportunityState.FORMING: "The entry trigger has not confirmed yet.",
            OpportunityState.WATCHING: "The bot is watching this setup; there is no entry yet.",
            OpportunityState.BLOCKED: "This setup was skipped. No order will be placed.",
            OpportunityState.REJECTED: "This setup was skipped. No order will be placed.",
            OpportunityState.EXPIRED: "The entry window expired without a trade.",
            OpportunityState.CANCELLED: "The setup was cancelled before entry.",
            OpportunityState.ORDER_WORKING: "The entry order is already working.",
            OpportunityState.POSITION_OPEN: "The position is already open.",
            OpportunityState.CLOSED: "This trade has finished.",
        }.get(state, "No new order is allowed in the current state.")
        return EntryRecommendation(
            OrderKind.NONE, None, False, expires,
            (DecisionReason("NO_TRADE", summary,
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
        "setup_signal_coverage": (coverage * Decimal(20)).quantize(Decimal("0.01")),
        "trigger_urgency": (urgency * Decimal(10)).quantize(Decimal("0.01")),
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
        warnings=("No setup-specific performance grade is available yet.",),
        sizing_allowed=False, version=OPPORTUNITY_VERSION)


def _risk_reason_summary(code: str, symbol: str, decision: str = "REJECTED") -> str:
    """Translate an audit code without hiding it from the decision record."""
    raw = str(code or "")
    base, _, argument = raw.partition("(")
    argument = argument[:-1] if argument.endswith(")") else argument
    rejected = str(decision).upper() == "REJECTED"
    if base == "NOT_IN_POINT_IN_TIME_UNIVERSE":
        if symbol.startswith("PF_"):
            return ("Trade skipped — this is a research-only market, so the bot "
                    "records setups but does not fund them.")
        return (f"Trade skipped — {symbol or 'this market'} did not meet the bot's "
                "market-selection rules when the setup confirmed.")
    if base == "OPERATOR_HALT":
        return "Trade skipped — new entries were manually halted."
    if base == "DATA_HEALTH_BLOCKED":
        return "Trade skipped — the latest market-data safety check did not pass."
    if base == "DRAWDOWN_HALT":
        suffix = f" ({argument})" if argument else ""
        return f"Trade skipped — the account hit its drawdown safety limit{suffix}."
    if base == "STRATEGY_DISABLED":
        strategy = argument or "this"
        return f"Trade skipped — the {strategy} strategy was switched off."
    if base == "COOLDOWN":
        return (f"Trade skipped — {symbol or 'this market'} was still resting after "
                "a recent trade.")
    if base == "DAILY_LOSS_HALT":
        return "Trade skipped — the daily loss limit had already been reached."
    if base == "INVALID_STOP_DISTANCE":
        return "Trade skipped — the stop was too close to the entry to size safely."
    if base == "SHORT_UNSUPPORTED_COINBASE_SPOT":
        return "Trade skipped — this spot market does not support short positions."
    if base == "SCALE_IN_FORBIDDEN":
        return "Trade skipped — adding to an open position is disabled."
    if base == "PARENT_CLOSED":
        return "Trade skipped — the original position had already closed."
    if base == "CONCURRENT_LIMIT":
        return "Trade skipped — all available position slots were already in use."
    if base == "EXPOSURE_LIMIT":
        return ("Trade skipped — it did not fit within the remaining account risk budget."
                if rejected else
                "Position size was reduced to fit the remaining account risk budget.")
    if base == "LEVERAGE_CAP":
        suffix = f" ({argument})" if argument else ""
        return f"Position size was reduced to stay within the leverage limit{suffix}."
    if base == "STOP_BEYOND_LIQUIDATION":
        return "Trade skipped — the exchange could liquidate it before the stop was reached."
    if base == "BELOW_MIN_NOTIONAL":
        return "Trade skipped — the safe position size was below the exchange minimum."
    if base == "PARTICIPATION_CAP":
        return "Position size was reduced because the market was too thin for the full size."
    if base == "PARTICIPATION_TOO_THIN":
        return "Trade skipped — the market was too thin for a safely sized order."
    if base == "ZERO_RISK_SIZE":
        return "Trade skipped — the safety calculation produced no valid position size."
    if base == "WITHIN_LIMITS":
        return "All account safety checks passed."
    return ("Trade skipped — a safety rule blocked it. Open the decision trace for details."
            if rejected else
            "A safety check adjusted this trade. Open the decision trace for details.")


def candidate(payload: dict, *, risk_fact: dict | None = None,
              order: dict | None = None, execution: dict | None = None,
              now: int | None = None) -> OpportunityCandidate:
    state = lifecycle(payload.get("state", "WATCHING"), risk_fact, order, execution)
    risk_rejected = str((risk_fact or {}).get("decision") or "").upper() == "REJECTED"
    expiry_issue = None
    expires_at = payload.get("expires_at_ts") or payload.get("expires_at")
    if now is not None and state in {
            OpportunityState.READY, OpportunityState.FORMING,
            OpportunityState.WATCHING}:
        try:
            if expires_at is None:
                # Every executable playbook owns an expiry. A legacy or damaged
                # setup without one can remain visible but cannot become risk.
                state = OpportunityState.BLOCKED
                expiry_issue = "missing"
            elif int(expires_at) <= int(now):
                state = OpportunityState.EXPIRED
        except (TypeError, ValueError):
            # An unreadable expiry is unsafe for an entry decision.
            state = OpportunityState.BLOCKED
            expiry_issue = "unreadable"
    hard_blocked = state in {OpportunityState.BLOCKED, OpportunityState.REJECTED}
    # Portfolio, expiry and execution state must not rewrite the market read.
    # A setup can be top-down aligned and still be skipped for account reasons.
    td = top_down(payload)
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
    risk_reasons = []
    if risk_fact and risk_fact.get("reasons"):
        risk_reasons = [DecisionReason(
            str(code), _risk_reason_summary(
                code, symbol, str((risk_fact or {}).get("decision") or "")),
                                      "CRITICAL" if hard_blocked else "INFO")
                        for code in risk_fact["reasons"]]
        reasons.extend(risk_reasons)
    eligible = state == OpportunityState.READY and not hard_blocked and \
               not alignment_blocked and not conditional_hold
    evidence = _ungraded(payload)
    primary = str(payload.get("why") or reasons[0].summary)
    if risk_rejected:
        counterargument = (risk_reasons[0].summary if risk_reasons else
                           "Trade skipped — an account safety check blocked it.")
    elif expiry_issue == "missing":
        counterargument = ("The setup has no expiry, so the entry window cannot "
                           "be verified.")
    elif expiry_issue == "unreadable":
        counterargument = ("The setup expiry is unreadable, so the entry window "
                           "cannot be verified.")
    elif state == OpportunityState.EXPIRED:
        counterargument = "The entry window expired before a trade could be taken."
    elif state == OpportunityState.CANCELLED:
        counterargument = "The setup was cancelled before an entry was taken."
    elif state == OpportunityState.ORDER_WORKING:
        counterargument = "The entry order is already working; no second order is needed."
    elif state == OpportunityState.POSITION_OPEN:
        counterargument = "The position is already open and is being managed."
    elif state == OpportunityState.CLOSED:
        counterargument = "This trade has finished; review its result in the journal."
    elif hard_blocked:
        counterargument = "A hard safety rule blocks this setup."
    elif td.state == TopDownState.CONFLICT:
        counterargument = "Higher-timeframe structure conflicts with this direction."
    elif state in {OpportunityState.FORMING, OpportunityState.WATCHING}:
        counterargument = "The entry trigger has not confirmed yet."
    else:
        counterargument = "No safety issue is currently blocking this setup."
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


def _private_custody_by_setup(con) -> dict[str, tuple]:
    """Real-venue lifecycle state per setup_id, from the custody authority.

    Latest outbox row per setup (several intents can share a setup when the
    quantity changed), overlaid with the managed position keyed by intent_id.
    Only TESTNET/LIVE rows — paper stays with the simulator's account of
    itself. Missing tables mean no private path has ever run: empty overlay.
    """
    try:
        rows = con.execute(
            "SELECT o.setup_id, o.state, m.state, "
            "COALESCE(m.updated_at, o.updated_at) "
            "FROM execution_outbox o "
            "LEFT JOIN managed_positions m ON m.position_id = o.intent_id "
            "WHERE o.mode IN ('TESTNET','LIVE') "
            "ORDER BY o.updated_at, o.id").fetchall()
    except Exception:
        return {}
    overlay: dict[str, tuple] = {}
    for setup_id, outbox_state, custody_state, updated_at in rows:
        # last row per id wins. managed_positions speaks for the position
        # (OPEN / UNPROTECTED / EMERGENCY_CLOSE / CLOSED); the outbox speaks
        # for the order (SUBMITTING through LIFECYCLE_COMPLETE).
        if custody_state in ("OPEN", "UNPROTECTED", "EMERGENCY_CLOSE"):
            overlay[setup_id] = (OpportunityState.POSITION_OPEN, updated_at)
        elif custody_state == "CLOSED" or outbox_state in (
                "LIFECYCLE_COMPLETE", "CUSTODY_CLOSED"):
            overlay[setup_id] = (OpportunityState.CLOSED, updated_at)
        elif outbox_state in ("SUBMITTED", "PARTIALLY_FILLED", "SUBMITTING"):
            overlay[setup_id] = (OpportunityState.ORDER_WORKING, updated_at)
    return overlay


def list_candidates(con, *, include_history: bool = True, now: int | None = None) -> list[dict]:
    observed_at = int(time.time()) if now is None else int(now)
    baseline = store.get_active_baseline(con)
    since = int(baseline["started_at"])
    setups_by_id = _latest_by_setup(con, "setup", setups.SETUP_VERSION, since)
    risk_by_id = _latest_by_setup(con, "risk", risk.RISK_VERSION, since)
    order_by_id = _latest_by_setup(con, "order", execsim.EXEC_VERSION, since)
    exec_by_id = _latest_by_setup(con, "exec", execsim.EXEC_VERSION, since)
    custody = _private_custody_by_setup(con)
    items = []
    for sid, payload in setups_by_id.items():
        payload.setdefault("setup_id", sid)
        item = candidate(payload, risk_fact=risk_by_id.get(sid),
                         order=order_by_id.get(sid), execution=exec_by_id.get(sid),
                         now=observed_at)
        # Real custody outranks the simulator's story about the same setup:
        # a real order or position IS the lifecycle state, whatever the
        # paper book thinks. The overlay never touches READY, so the
        # autotrader's dispatch condition is unaffected.
        #
        # Except a TERMINAL overlay older than the setup fact itself.
        # setup_id embeds zone and version, so a persistent zone retested
        # weeks later re-validates under the SAME id — and an old completed
        # lifecycle stamping the fresh candidate CLOSED would hide a valid,
        # tradeable setup forever (audit 2026-08-08). A live order or open
        # position overlays unconditionally: it is a present-tense fact.
        if sid in custody:
            _cstate, _cts = custody[sid]
            if (_cstate != OpportunityState.CLOSED or
                    int(_cts or 0) >= int(payload.get("confirmed_at") or 0)):
                item = dataclasses.replace(
                    item, state=_cstate, eligible=False,
                    entry_recommendation=recommend_entry(payload, _cstate))
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
    actionable = counts["READY"]
    if counts["POSITION_OPEN"]:
        count = counts["POSITION_OPEN"]
        narrative = f"Managing {count} open position{'s' if count != 1 else ''}."
    elif counts["ORDER_WORKING"]:
        count = counts["ORDER_WORKING"]
        narrative = (f"{count} order{'s are' if count != 1 else ' is'} working; "
                     "protection remains monitored.")
    elif actionable:
        forming = counts["FORMING"]
        narrative = (f"{actionable} setup{'s are' if actionable != 1 else ' is'} ready"
                     + (f"; {forming} {'are' if forming != 1 else 'is'} still forming."
                        if forming else "."))
    elif counts["FORMING"]:
        forming = counts["FORMING"]
        narrative = (f"{forming} setup{'s are' if forming != 1 else ' is'} forming; "
                     "no entry is ready.")
    else:
        narrative = "No setup currently meets entry rules. Scanning continues."
    return {"counts": counts, "actionable": actionable,
            "narrative": narrative, "version": OPPORTUNITY_VERSION}
