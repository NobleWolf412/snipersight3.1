"""Server-owned opportunity lifecycle, ranking and entry recommendation.

This is a read model over existing append-only setup/risk/order/exec facts.  It
does not create a second strategy engine.  In particular, the browser receives
the state, score components, exact prices and reasons already reconciled here.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
import time
from decimal import Decimal, InvalidOperation

from . import bias, execsim, registry, risk, setups, store, venues
from .runlog import get_logger
from .contracts import (DecisionReason, EntryRecommendation, ExecutionDomain,
                        FactorGrade, OpportunityCandidate, OpportunityState,
                        OrderKind, TopDownDecision, TopDownState, TradeSetup,
                        to_wire)


OPPORTUNITY_VERSION = "opportunity-v0.8-draft"
# v0.8: lifecycle belongs to ONE execution domain, and the research simulator
# is no longer any domain's authority but its own.
#
# Until now `lifecycle()` took the replay's `order` and `exec` facts for every
# caller, so the simulator decided whether a setup could route. It reaches
# every setup first — `execsim.run` at live.py:629, before `risk.run` at :658
# — and stamps it POSITION_OPEN or CLOSED, and only a setup with no research
# record at all could be READY. Measured on the live store 2026-09-11, in the
# active baseline: 1035 setups, 189 risk-rejected, **40 claimed by the
# replay's own exits, and zero reaching READY**. All 37 risk-APPROVED setups
# were in those 40. `autotrader.run` dispatches READY only, so the paper book
# had never been offered a single setup and `paper_positions` was empty.
#
# The rule this version encodes, and the one a future edit must not quietly
# undo: **a domain's routing state comes from that domain's own records, and
# the absence of a record means that domain has not acted.** Never fall back
# to another domain. The research story survives as `research_story`, which
# is display and reaches neither `state` nor `eligible`.
#
# This is convention 7 ("evidence is recorded, not filtered on, until it has
# been graded") applied where it had not been: the replay is evidence, and it
# was filtering.
# v0.7: an engine position the OPERATOR closed by hand is CLOSED here too.
# /api/portfolio has joined `manual.overridden_setups` since the override
# existed; this read model never did, so after pressing Close on a mission
# card the exposure chip dropped the trade while Next Action kept saying
# "Manage X — a position is open" until the engine's own simulation reached
# an exit — days, on a 4H or 1D trade. Same version-stripped zone key and the
# same rule as the portfolio: a zone the operator closed stays closed for the
# life of the zone. CLOSED_EARLY only — an ADOPTED position is still open —
# and never over real custody.
# v0.6: the ladder has ONE policy authority, and it is the playbook's own
# recorded bias verdict — this module stops running a second, ungraded one.
# Until now `top_down()` blocked dispatch for everything short of a fully
# agreeing ladder: AGAINST and MIXED were CONFLICT, FLAT and UNKNOWN were
# CONDITIONAL, and all four zeroed `eligible`. That rule was never graded,
# contradicted the per-playbook measurement (`bias.py`, 2026-08-04: filtering
# the live book to WITH-only costs -0.109 R/trade), and scored a MISSING
# measurement as a bad one — the exact rule `bias.validate_policy` refuses at
# import time because it cost 1.02 R/trade when setups.py made the same
# mistake. It also made the testnet path rehearse a different book than the
# paper book the grades describe, which defeats the shadow comparison.
# Now: only a recorded `resolved == "BLOCK"` from the playbook's own
# BIAS_POLICY blocks. The four states remain as the honest DISPLAY of the
# ladder (aligned / conflict / conditional), and CONFLICT still supplies the
# strongest counterargument — it is advisory, not a gate. NOT armed here:
# any preference FOR against-ladder trades (the +0.2755 R bucket is n=126,
# P(>0) 94.5%, one cell of a 100-cell sweep, measured pre-drift) — that is
# an edge claim bias.py's own text refuses, not rehearsal fidelity.
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


def attempt_id_for(setup_id: str, payload: dict) -> str | None:
    """The identity of one ATTEMPT at a zone, or None before one exists.

    `setup_id` names the zone, not the occurrence: it is
    `symbol|tf|strategy|zone_id|version`, and `zone_id` carries the zone's own
    FORMATION bar (`zones.py`), so every later retest of a persistent zone
    re-derives the same id, and so does every engine generation. Both failure
    modes follow from that, and they point opposite ways:

    · **Over-splitting**, which has actually happened. One UNIUSDT 4H REVERSAL
      touch minted five ids across setup-v0.13 to v0.17 with byte-identical
      entry/sl/tp and one `confirmed_at`; a position the operator had closed
      came back as live exposure under the new tag (`manual.setup_zone_key`,
      2026-08-06).
    · **Under-splitting**, which has not. No `setup_id` has ever VALIDATED
      twice under one version (833 facts, 833 distinct ids, measured
      2026-09-11) — so the merge half of this key is evidenced and the split
      half is sound by construction and untested. Do not claim otherwise.

    So: the version-stripped zone plus the CONFIRMING bar. Both describe the
    market rather than the code, which is why they survive an engine bump.

    Returns None for a setup that has not confirmed. That is not a missing
    value to paper over — an unconfirmed setup is not yet an attempt, and the
    store agrees exactly: `confirmed_bar_ts` is present on every VALIDATED and
    EXPIRED fact and absent from every FORMING, CONFIRMING and CANCELLED one.
    """
    bar = payload.get("confirmed_bar_ts")
    if bar is None or not setup_id:
        return None
    from . import manual as _manual
    return f"{_manual.setup_zone_key(setup_id)}|{int(bar)}"


def top_down(payload: dict) -> TopDownDecision:
    """The ladder as a DISPLAY, and the playbook's verdict as the only gate.

    The reading (composite, rungs, alignment) is `bias.py`'s, recorded on the
    setup fact by the playbook that emitted it, alongside that playbook's own
    policy verdict in `resolved`. This function renders those; it decides
    nothing of its own. Only `resolved == "BLOCK"` — the playbook's armed
    BIAS_POLICY speaking — produces a blocking state. CONFLICT and
    CONDITIONAL survive as honest descriptions of the ladder and as the
    strongest counterargument, because a trader deserves to see "the daily
    disagrees" beside an entry; they no longer veto it. Re-deriving a policy
    here was a second authority over one number — convention 9's defect —
    and it was this module, not bias.py, that ended up scoring UNKNOWN as a
    weak AGAINST.
    """
    block = payload.get("bias") or {}
    composite = str(block.get("composite") or "UNKNOWN")
    alignment = str(block.get("alignment") or "UNKNOWN")
    resolved = str(block.get("resolved") or "ALLOW")
    rungs = block.get("rungs") if isinstance(block.get("rungs"), dict) else {}
    reasons = []
    # bias.blocked is the ONE place the verdict comparison lives — its
    # docstring exists precisely to forbid the inline `== "BLOCK"` this
    # line briefly carried (cold audit, 2026-08-31): if REQUIRE_EVIDENCE
    # ever grows a third outcome, this display must move with the gate in
    # setups.py rather than drift from it.
    if bias.blocked({"resolved": resolved}):
        state = TopDownState.BLOCKED
        reasons.append(DecisionReason(
            "TOP_DOWN_BLOCK", "This playbook's higher-timeframe policy "
            "blocks this entry.", "CRITICAL"))
    elif alignment == "WITH":
        state = TopDownState.ALIGNED
        reasons.append(DecisionReason(
            "TOP_DOWN_ALIGNED", "The higher-timeframe ladder supports the trade."))
    elif alignment in ("AGAINST", "MIXED"):
        state = TopDownState.CONFLICT
        reasons.append(DecisionReason(
            "TOP_DOWN_CONFLICT", "The higher-timeframe ladder conflicts with "
            "or disagrees about this direction. The playbook's measured "
            "policy allows the trade.", "WARNING"))
    else:
        state = TopDownState.CONDITIONAL
        reasons.append(DecisionReason(
            "TOP_DOWN_CONDITIONAL", "The higher-timeframe ladder is flat or "
            "has no confirmed reading. A missing measurement never blocks.",
            "INFO"))
    return TopDownDecision(state=state, composite=composite,
                           direction=str(payload.get("direction") or "UNKNOWN"),
                           rungs=rungs, reasons=tuple(reasons),
                           version=OPPORTUNITY_VERSION)


def lifecycle(setup_state: str, risk_fact: dict | None = None,
              record: OpportunityState | None = None) -> OpportunityState:
    """Where one setup stands, for ONE execution domain.

    `record` is that domain's own account of the attempt — what its orders and
    positions prove — or `None` when it holds no record. `None` means **this
    domain has not acted**; it is never permission to read another domain's
    history, which is precisely the defect v0.8 exists to remove.

    Risk still outranks a record, because risk is the authority on whether an
    attempt was ever allowed to become exposure. A domain that recorded a fill
    against a rejected decision is describing a bug, not a position.
    """
    state = (setup_state or "").upper()
    decision = str((risk_fact or {}).get("decision") or "").upper()
    if decision == "REJECTED":
        return OpportunityState.BLOCKED
    if record is not None:
        return record
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
    if base == "SAME_SIDE_HALT":
        side, _, n = argument.partition(",")
        word = {"LONG": "long", "SHORT": "short"}.get(side, "that side")
        return (f"Trade skipped — {n or 'enough'} {word} trades had already lost "
                f"today, so no more {word} entries until tomorrow.")
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
              record: OpportunityState | None = None,
              domain: str = ExecutionDomain.RESEARCH.value,
              research_story: dict | None = None,
              now: int | None = None) -> OpportunityCandidate:
    state = lifecycle(payload.get("state", "WATCHING"), risk_fact, record)
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
    #
    # Only the playbook's own recorded policy verdict blocks (BLOCKED, from
    # `resolved == "BLOCK"`). CONFLICT and CONDITIONAL are ladder DISPLAY
    # states — v0.5 treated them as a gate, which was a second ungraded HTF
    # authority and held every setup whose ladder was merely unmeasured.
    td = top_down(payload)
    alignment_blocked = td.state == TopDownState.BLOCKED
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
        attempt_id=attempt_id_for(setup_id, payload),
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
               not alignment_blocked
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
    elif alignment_blocked:
        counterargument = ("This playbook's own higher-timeframe policy "
                           "blocks this entry.")
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
            blocked=hard_blocked or alignment_blocked),
        risk_decision=risk_fact, ranking_components=components,
        economics=economics, primary_explanation=primary,
        strongest_counterargument=counterargument,
        reasons=tuple(reasons),
        legacy_rank=_decimal(payload.get("rank")) if payload.get("rank") is not None else None,
        version=OPPORTUNITY_VERSION,
        domain=str(domain),
        research_story=research_story)


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


#: The research simulator's order events, mapped to the lifecycle each one
#: proves. These describe the REPLAY and nothing else; `_research_records` is
#: the only reader, and only the RESEARCH domain consults it as state.
_RESEARCH_LIFECYCLE = {
    "FILLED": OpportunityState.POSITION_OPEN,
    "PLACED": OpportunityState.ORDER_WORKING,
    "PARTIALLY_FILLED": OpportunityState.ORDER_WORKING,
    "UNTRIGGERED": OpportunityState.ORDER_WORKING,
    "CANCELLED": OpportunityState.CANCELLED,
    "CANCELED": OpportunityState.CANCELLED,
    "MISSED": OpportunityState.EXPIRED,
}

#: Outbox states mapped to the lifecycle they prove. `execution._event` writes
#: the event name straight into `execution_outbox.state`, so these ARE the
#: event names. The outbox is the lifecycle authority for a dispatched intent
#: — its own docstring says so ("the outbox state is the retry authority") —
#: which is why nothing here reads `paper_positions.state` as well. That table
#: owns the ACCOUNT (entry, exit, R, costs); this one owns the ORDER. One
#: authority per number, and they are two different numbers.
_OUTBOX_LIFECYCLE = {
    "PENDING": OpportunityState.ORDER_WORKING,
    "SUBMITTING": OpportunityState.ORDER_WORKING,
    "SUBMITTED": OpportunityState.ORDER_WORKING,
    "PARTIALLY_FILLED": OpportunityState.ORDER_WORKING,
    "PAPER_ROUTED": OpportunityState.ORDER_WORKING,
    "SHADOW_RECORDED": OpportunityState.ORDER_WORKING,
    "PAPER_FILLED": OpportunityState.POSITION_OPEN,
    "PAPER_EXPIRED": OpportunityState.EXPIRED,
    "PAPER_CLOSED": OpportunityState.CLOSED,
    "LIFECYCLE_COMPLETE": OpportunityState.CLOSED,
    "ORDER_LIFECYCLE_COMPLETE": OpportunityState.CLOSED,
    "CUSTODY_CLOSED": OpportunityState.CLOSED,
    # Queued and refused before the wire. Neither is exposure, and neither is
    # "no attempt" — the domain acted and declined, which is a lifecycle fact.
    "RISK_REJECTED": OpportunityState.BLOCKED,
    "HELD_OFF": OpportunityState.BLOCKED,
    "SUBMIT_FAILED": OpportunityState.BLOCKED,
}

#: managed_positions speaks for a REAL position, outranking the outbox's
#: account of the order that opened it. Private domains only.
_CUSTODY_LIFECYCLE = {
    "OPEN": OpportunityState.POSITION_OPEN,
    "UNPROTECTED": OpportunityState.POSITION_OPEN,
    "EMERGENCY_CLOSE": OpportunityState.POSITION_OPEN,
    "CLOSED": OpportunityState.CLOSED,
}


def risk_source(domain: str) -> tuple[str, str]:
    """Which (kind, version) holds THIS domain's risk verdicts.

    The replay's `risk` facts size against a simulated account that has never
    held an order; the paper ledger's `risk_paper` facts size against the book
    that actually will. Reading the wrong one is not a display bug — it is the
    dispatcher approving an order against someone else's balance, and it is
    the single biggest hazard in this whole separation. A paper order routed
    on the replay's approval while the paper ledger sits halted or already at
    `MAX_CONCURRENT` shows up as two open positions at once, with both
    surfaces internally consistent and disagreeing.
    """
    if domain == ExecutionDomain.RESEARCH.value:
        return "risk", risk.RISK_VERSION
    from . import riskpaper
    return riskpaper.PAPER_RISK_KIND, riskpaper.PAPER_RISK_VERSION


def _missing_table(exc: Exception) -> bool:
    """True only for "this table was never created", never for a read failure.

    The distinction is load-bearing and it is why this is not a bare `except`.
    A domain with no records reads as "has not acted", and the autotrader is
    allowed to route into it. A swallowed read error would produce the exact
    same empty dict and hand the dispatcher a green light off a database
    hiccup — the loud-fallback rule, in the one place where breaking it costs
    an order.
    """
    return isinstance(exc, sqlite3.OperationalError) and "no such table" in str(exc)


def _research_records(con, since: int) -> dict[str, tuple]:
    """The replay's account of every setup, as `(state, at, story)`.

    Authority for the RESEARCH domain; DISPLAY for every other one. `story`
    travels to the wire as `research_story` so a screen can still say "the
    simulator closed this at +1.2R" beside a PAPER setup that is correctly
    READY — two populations, one row, neither pretending to be the other.
    """
    orders = _latest_by_setup(con, "order", execsim.EXEC_VERSION, since)
    exits = _latest_by_setup(con, "exec", execsim.EXEC_VERSION, since)
    out: dict[str, tuple] = {}
    for sid in set(orders) | set(exits):
        order, exit_fact = orders.get(sid) or {}, exits.get(sid) or {}
        event = str(order.get("event") or "").upper()
        story = {"order_event": order.get("event"),
                 "outcome": exit_fact.get("outcome"),
                 "r_multiple": exit_fact.get("r_multiple"),
                 "exec_version": execsim.EXEC_VERSION}
        if exit_fact.get("outcome") not in (None, "PENDING"):
            state, at = OpportunityState.CLOSED, exit_fact.get("confirmed_at")
        else:
            state, at = _RESEARCH_LIFECYCLE.get(event), order.get("confirmed_at")
            if event and state is None:
                get_logger().warning(
                    f"opportunities: unmapped research order event {event!r} "
                    f"for {sid} — treated as no record")
        out[sid] = (state, int(at or 0), story)
    return out


def _outbox_records(con, mode: str) -> dict[str, tuple]:
    """One dispatch domain's own account of each setup, as `(state, at)`.

    Reads only rows written under `mode`, which is what makes the domain rule
    structural rather than a convention somebody has to remember: PAPER cannot
    see TESTNET's orders because the query cannot return them.
    """
    private = mode in (ExecutionDomain.TESTNET.value, ExecutionDomain.LIVE.value)
    sql = ("SELECT o.setup_id, o.state, m.state, "
           "COALESCE(m.updated_at, o.updated_at) "
           "FROM execution_outbox o "
           "LEFT JOIN managed_positions m ON m.position_id = o.intent_id "
           "WHERE o.mode=? ORDER BY o.updated_at, o.id") if private else (
           "SELECT setup_id, state, NULL, updated_at FROM execution_outbox "
           "WHERE mode=? ORDER BY updated_at, id")
    try:
        rows = con.execute(sql, (mode,)).fetchall()
    except Exception as exc:
        if _missing_table(exc):
            return {}
        raise
    out: dict[str, tuple] = {}
    for setup_id, outbox_state, custody_state, updated_at in rows:
        # Last row per setup wins: several intents share a setup when the
        # quantity changed, and the newest is the live one.
        state = _CUSTODY_LIFECYCLE.get(custody_state) if custody_state else None
        if state is None:
            state = _OUTBOX_LIFECYCLE.get(str(outbox_state or "").upper())
        if state is None:
            get_logger().warning(
                f"opportunities: unmapped {mode} outbox state "
                f"{outbox_state!r} for {setup_id} — treated as no record")
            continue
        out[setup_id] = (state, int(updated_at or 0))
    return out


def real_exposure(con) -> dict[str, tuple]:
    """Every setup with a REAL order or position, across TESTNET and LIVE.

    DISPLAY ONLY, and the one deliberate crossing of the domain boundary.
    Money at a venue is a present-tense fact about the operator's account: it
    does not stop existing because the dispatcher was set back to PAPER, and a
    cockpit that answered "no setup currently meets entry rules, scanning
    continues" over an open testnet position was the defect opportunity-v0.3
    was written to fix. Restoring the domain rule must not restore that.

    What keeps it honest is the direction of travel — this can only ever
    REMOVE eligibility, never grant it — and that the dispatcher never asks
    for it. `autotrader.run` reads its own domain and nothing else.
    """
    merged: dict[str, tuple] = {}
    for mode in (ExecutionDomain.TESTNET.value, ExecutionDomain.LIVE.value):
        for sid, (state, at) in _outbox_records(con, mode).items():
            if sid not in merged or at >= merged[sid][1]:
                merged[sid] = (state, at)
    return merged


#: A lifecycle nothing can leave. A record in one of these states describes a
#: FINISHED attempt, which is the only kind that can belong to an earlier
#: touch of the same zone — hence the staleness rule below.
_TERMINAL = {OpportunityState.CLOSED, OpportunityState.EXPIRED,
             OpportunityState.CANCELLED, OpportunityState.REJECTED,
             OpportunityState.BLOCKED}


def _describes_an_earlier_attempt(state: OpportunityState, at: int,
                                  payload: dict) -> bool:
    """True when a domain's record finished BEFORE this setup confirmed.

    Both tables holding domain records are keyed on `setup_id`, which names
    the zone rather than the occurrence (`attempt_id_for`). So a completed
    lifecycle from a retest weeks ago sits on exactly the same key as a fresh
    validation of that zone, and left alone it stamps the new candidate CLOSED
    forever (audit 2026-08-08).

    Only a terminal record can be stale. A working order or an open position
    is a present-tense fact about the account and overrides unconditionally —
    whatever the setup fact says, that exposure exists right now.
    """
    if state not in _TERMINAL:
        return False
    return int(at or 0) < int(payload.get("confirmed_at") or 0)


def list_candidates(con, *, domain: str = ExecutionDomain.RESEARCH.value,
                    include_history: bool = True, now: int | None = None,
                    show_real_exposure: bool = False) -> list[dict]:
    """The read model for ONE execution domain.

    `domain` decides whose order records answer "where does this setup
    stand" — and nothing else changes: strategy, risk, ranking and copy are
    shared, because sharing logic was never the problem. Sharing STATE was.

    `show_real_exposure` adds TESTNET/LIVE positions to an operator SCREEN
    (see `real_exposure`). It is off by default so the dispatch path cannot
    reach it by forgetting an argument, and it can only take eligibility away.
    """
    observed_at = int(time.time()) if now is None else int(now)
    baseline = store.get_active_baseline(con)
    since = int(baseline["started_at"])
    setups_by_id = _latest_by_setup(con, "setup", setups.SETUP_VERSION, since)
    risk_kind, risk_version = risk_source(domain)
    risk_by_id = _latest_by_setup(con, risk_kind, risk_version, since)
    # The replay is read for EVERY domain, and consulted as state for exactly
    # one. Elsewhere it travels as `research_story`: visible, labelled, inert.
    research = _research_records(con, since)
    is_research = domain == ExecutionDomain.RESEARCH.value
    records = ({sid: (state, at) for sid, (state, at, _story) in research.items()
                if state is not None} if is_research
               else _outbox_records(con, domain))
    exposure = (real_exposure(con) if show_real_exposure and domain not in (
        ExecutionDomain.TESTNET.value, ExecutionDomain.LIVE.value) else {})
    # The operator's early closes, keyed on the version-free zone — the
    # portfolio's rule, reused rather than restated (see the v0.7 note).
    # CLOSED_EARLY only: an ADOPTED position is still open, under the
    # operator's custody, and "a position is open" stays true of it.
    from . import manual as _manual
    overrides = _manual.overridden_setups(con)
    closed_zones = {_manual.setup_zone_key(osid)
                    for osid, o in overrides.items()
                    if o.get("event") == "CLOSED_EARLY"}
    items = []
    for sid, payload in setups_by_id.items():
        payload.setdefault("setup_id", sid)
        record = records.get(sid)
        state = None
        if record is not None and not _describes_an_earlier_attempt(
                record[0], record[1], payload):
            state = record[0]
        item = candidate(
            payload, risk_fact=risk_by_id.get(sid), record=state, domain=domain,
            research_story=None if is_research else research.get(sid, (None, 0, None))[2],
            now=observed_at)
        # Real money outranks the screen's chosen domain, and only downward.
        held = exposure.get(sid)
        if held is not None and not _describes_an_earlier_attempt(
                held[0], held[1], payload):
            item = dataclasses.replace(
                item, state=held[0], eligible=False,
                entry_recommendation=recommend_entry(payload, held[0]))
        # The portfolio suppresses a hand-closed zone for the life of the
        # zone (manual.setup_zone_key explains why: the same zone re-derives
        # under every later setup version), and this model must say the
        # same thing or the chip and the directive disagree. A domain holding
        # its own record outranks the override, exactly as real custody used
        # to: an open TESTNET position is not closed by a paper close.
        # Deliberately NOT `_TERMINAL`: that set includes BLOCKED, and a
        # hand-closed zone whose candidate is merely risk-blocked has always
        # rendered CLOSED here. Widening the guard would have changed that
        # silently, which is not this version's business.
        if (sid not in records and sid not in exposure
                and _manual.setup_zone_key(sid) in closed_zones
                and item.state not in (OpportunityState.CLOSED,
                                       OpportunityState.EXPIRED,
                                       OpportunityState.CANCELLED,
                                       OpportunityState.REJECTED)):
            item = dataclasses.replace(
                item, state=OpportunityState.CLOSED, eligible=False,
                entry_recommendation=recommend_entry(payload, OpportunityState.CLOSED))
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
