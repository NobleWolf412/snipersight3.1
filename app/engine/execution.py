"""Broker-neutral, idempotent execution outbox.

This module is the only seam allowed to call a private venue adapter.  OFF,
PAPER and SHADOW cannot reach ``Broker.submit`` by construction.  TESTNET may
dispatch only after its shadow promotion gate; LIVE remains build-locked.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Protocol

from . import automation
from .contracts import (AutomationMode, BrokerExecution, BrokerOrder, DecisionReason,
                        ExecutionPlan, Fill, OrderIntent, OrderKind,
                        RiskDecision, to_wire)


EXECUTION_CORE_VERSION = "execution-core-v0.6-draft"
# v0.6: three audited holes in the private path closed. (1) A resting private
# entry now honours intent.expires_at — monitor_private cancels the remainder
# at the venue; before this only the PAPER monitor read expiry, so an expired
# setup's PostOnly order rested forever and could fill days later against a
# dead setup's stop. (2) A definitive pre-wire refusal (validate_plan /
# enforce_one_way / set_leverage / a 4xx on POST — none of which create an
# order) records SUBMIT_FAILED and is retryable; before, the row stuck at
# SUBMITTING forever, and silently. Ambiguous failures keep the old, correct
# never-resubmit behaviour. (3) RESTART_RECOVERED requires the process boot
# id recorded at SUBMITTING to differ from the current one — resolving a
# lost response inside one process is not a restart, and it was passing the
# restart promotion drill.
PAPER_MAX_HOLDING_BARS = 100

# One id per process, minted at import. Recorded into every SUBMITTING event
# so recovery can prove "a different process finished this" — the evidence
# the restart drill exists to demand.
import uuid as _uuid
PROCESS_BOOT_ID = _uuid.uuid4().hex


class Broker(Protocol):
    environment: str

    def submit(self, plan: ExecutionPlan) -> BrokerOrder: ...
    def cancel(self, symbol: str, client_order_id: str) -> BrokerOrder: ...
    def open_orders(self, symbol: str | None = None) -> list[BrokerOrder]: ...
    def positions(self) -> list[dict]: ...
    def executions(self, symbol: str, *, start_at: int) -> list[BrokerExecution]: ...


class DispatchRejected(RuntimeError):
    pass


def intent_key(setup_id: str, mode: AutomationMode, order_kind: str,
               quantity: str, entry: str | None) -> str:
    raw = "|".join((setup_id, mode.value, order_kind, quantity, entry or "MARKET"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS execution_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key TEXT NOT NULL UNIQUE,
        intent_id TEXT NOT NULL UNIQUE,
        mode TEXT NOT NULL,
        setup_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        payload TEXT NOT NULL,
        state TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS execution_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        intent_id TEXT NOT NULL,
        event TEXT NOT NULL,
        occurred_at INTEGER NOT NULL,
        payload TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS paper_positions (
        intent_id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        tf TEXT NOT NULL,
        direction TEXT NOT NULL,
        quantity TEXT NOT NULL,
        entry TEXT NOT NULL,
        stop TEXT NOT NULL,
        target TEXT,
        state TEXT NOT NULL,
        filled_at INTEGER NOT NULL,
        closed_at INTEGER,
        outcome TEXT,
        exit_price TEXT)""")
    paper_columns = {row[1] for row in con.execute(
        "PRAGMA table_info(paper_positions)").fetchall()}
    for name in ("entry_role", "r_multiple", "fees_price_units", "funding_price_units",
                 "slippage_price_units", "cost_profile_version"):
        if name not in paper_columns:
            con.execute(f"ALTER TABLE paper_positions ADD COLUMN {name} TEXT")


def enqueue(con, intent: OrderIntent, *, plan: ExecutionPlan | None = None) -> dict:
    """Persist once. Repeated delivery returns the original row unchanged.

    Store the complete server-approved plan when one is available so restart
    recovery never has to reconstruct risk or custody rules from an order
    fragment. ``intent`` alone remains valid for migration callers.
    """
    _ensure(con)
    now = int(time.time())
    payload = json.dumps(to_wire(plan if plan is not None else intent),
                         sort_keys=True, separators=(",", ":"))
    con.execute(
        "INSERT OR IGNORE INTO execution_outbox(idempotency_key,intent_id,mode,"
        "setup_id,symbol,payload,state,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?, ?,?)",
        (intent.idempotency_key, intent.intent_id, intent.mode.value,
         intent.setup_id, intent.symbol, payload, "PENDING", now, now))
    row = con.execute(
        "SELECT intent_id,state,created_at,updated_at FROM execution_outbox "
        "WHERE idempotency_key=?", (intent.idempotency_key,)).fetchone()
    con.commit()
    return {"intent_id": row[0], "state": row[1], "created_at": row[2],
            "updated_at": row[3], "duplicate": row[0] != intent.intent_id}


def _event(con, intent_id: str, event: str, payload: dict) -> None:
    now = int(time.time())
    con.execute(
        "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
        "VALUES(?,?,?,?)", (intent_id, event, now,
                            json.dumps(payload, sort_keys=True)))
    con.execute("UPDATE execution_outbox SET state=?,updated_at=? WHERE intent_id=?",
                (event, now, intent_id))
    con.commit()


def _audit_event(con, intent_id: str, event: str, payload: dict) -> None:
    """Append evidence without changing the outbox lifecycle state."""
    con.execute(
        "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
        "VALUES(?,?,?,?)", (intent_id, event, int(time.time()),
                            json.dumps(payload, sort_keys=True)))
    con.commit()


def _decision_hash(plan: ExecutionPlan) -> str:
    decision = to_wire({
        "symbol": plan.intent.symbol, "direction": plan.intent.direction,
        "order_kind": plan.intent.order_kind.value,
        "quantity": plan.intent.quantity, "entry": plan.intent.entry,
        "stop": plan.intent.stop, "targets": plan.intent.targets,
        "risk": plan.risk})
    return hashlib.sha256(json.dumps(
        decision, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _complete_shadow_comparison(con, paper_intent_id: str,
                                paper_result: dict) -> None:
    for shadow_intent_id, raw in con.execute(
            "SELECT intent_id,payload FROM execution_events "
            "WHERE event='SHADOW_PAIRED'").fetchall():
        try:
            paired = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if paired.get("paper_intent_id") != paper_intent_id:
            continue
        exists = con.execute(
            "SELECT 1 FROM execution_events WHERE intent_id=? "
            "AND event IN ('SHADOW_PAIRED_RESULT',"
            "'SHADOW_PAIR_INTEGRITY_FAILURE') LIMIT 1",
            (shadow_intent_id,)).fetchone()
        if not exists:
            paper_row = con.execute(
                "SELECT payload FROM execution_outbox WHERE intent_id=?",
                (paper_intent_id,)).fetchone()
            paper_plan = _plan_from_wire(paper_row[0]) if paper_row else None
            expected_hash = paired.get("decision_hash")
            actual_hash = _decision_hash(paper_plan) if paper_plan else None
            matched = bool(expected_hash and actual_hash == expected_hash)
            event = ("SHADOW_PAIRED_RESULT" if matched else
                     "SHADOW_PAIR_INTEGRITY_FAILURE")
            _audit_event(con, shadow_intent_id, event, {
                "matched": matched, "explained": False,
                "paper_intent_id": paper_intent_id,
                "expected_decision_hash": expected_hash,
                "paper_decision_hash": actual_hash,
                "paper_result": paper_result})
        return


def _plan_from_wire(raw: str) -> ExecutionPlan | None:
    try:
        payload = json.loads(raw)
        i, r = payload["intent"], payload["risk"]
        intent = OrderIntent(
            intent_id=i["intent_id"], setup_id=i["setup_id"],
            mode=AutomationMode(i["mode"]), symbol=i["symbol"],
            direction=i["direction"], order_kind=OrderKind(i["order_kind"]),
            quantity=Decimal(i["quantity"]),
            entry=None if i.get("entry") is None else Decimal(i["entry"]),
            stop=Decimal(i["stop"]),
            targets=tuple(Decimal(x) for x in i.get("targets") or []),
            reduce_only=bool(i["reduce_only"]), created_at=int(i["created_at"]),
            playbook_version=i["playbook_version"],
            idempotency_key=i["idempotency_key"],
            version=i.get("version") or EXECUTION_CORE_VERSION,
            timeframe=i.get("timeframe"), expires_at=i.get("expires_at"),
            entry_model=i.get("entry_model"),
            maker_wait_bars=i.get("maker_wait_bars"))
        risk = RiskDecision(
            approved=bool(r["approved"]), decision=r["decision"],
            risk_usd=Decimal(r["risk_usd"]), quantity=Decimal(r["quantity"]),
            notional_usd=Decimal(r["notional_usd"]),
            implied_leverage=Decimal(r["implied_leverage"]),
            reasons=tuple(DecisionReason(x["code"], x["summary"],
                                         x.get("severity", "INFO"))
                          for x in r.get("reasons") or []),
            version=r.get("version") or EXECUTION_CORE_VERSION)
        return ExecutionPlan(
            intent=intent, risk=risk, venue=payload["venue"],
            margin_mode=payload["margin_mode"],
            position_mode=payload["position_mode"],
            protection_deadline_seconds=int(
                payload.get("protection_deadline_seconds", 5)),
            version=payload.get("version") or EXECUTION_CORE_VERSION)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def monitor_private(con, broker) -> dict:
    """REST reconciliation fallback for submitted and partially filled entries."""
    _ensure(con)
    from . import positions
    positions._ensure(con)
    mode = "TESTNET" if broker.environment == "testnet" else "LIVE"
    rows = con.execute(
        "SELECT intent_id,payload,state FROM execution_outbox WHERE mode=? "
        "AND state IN ('SUBMITTING','SUBMITTED','PARTIALLY_FILLED') ORDER BY id",
        (mode,)).fetchall()
    updated, refused = [], []
    for intent_id, raw_plan, _ in rows:
        plan = _plan_from_wire(raw_plan)
        if plan is None:
            refused.append({"intent_id": intent_id,
                            "reason": "durable execution plan is unreadable"})
            continue
        event = con.execute(
            "SELECT payload FROM execution_events WHERE intent_id=? "
            "AND event IN ('SUBMITTING','SUBMITTED') "
            "ORDER BY id DESC LIMIT 1", (intent_id,)).fetchone()
        submitted = json.loads(event[0]) if event else {}
        try:
            order = broker.order_status(
                plan.intent.symbol,
                str(submitted.get("client_order_id") or ""),
                submitted.get("broker_order_id"))
        except Exception as exc:
            from .phemex_private import AmbiguousSubmission
            if isinstance(exc, (AmbiguousSubmission, TimeoutError,
                                ConnectionError)):
                automation.observe_safety_event(con, "DISCONNECT_OBSERVED", {
                    "intent_id": intent_id,
                    "client_order_id": str(
                        submitted.get("client_order_id") or ""),
                    "error_type": type(exc).__name__,
                    "transport_failure": True})
            from .runlog import get_logger
            get_logger().warning(
                f"private order monitor disconnected for {intent_id}: "
                f"{type(exc).__name__}: {exc}")
            refused.append({"intent_id": intent_id,
                            "reason": "private order lookup failed"})
            continue
        if order is None:
            refused.append({"intent_id": intent_id,
                            "reason": "broker order state is not yet definitive"})
            continue
        automation.observe_safety_event(con, "DISCONNECT_RECOVERED", {
            "intent_id": intent_id, "client_order_id": order.client_order_id})
        if _ == "SUBMITTING":
            _event(con, intent_id, "SUBMITTED", to_wire(order))
            # A restart claim needs restart evidence: the boot id recorded
            # when SUBMITTING was written must belong to a DIFFERENT process
            # than the one recovering it. Resolving a lost response inside
            # one process is disconnect recovery, and it was passing the
            # restart promotion drill without any restart. Legacy rows with
            # no boot id earn no pass — fail closed.
            submitting_boot = str(submitted.get("boot_id") or "")
            if submitting_boot and submitting_boot != PROCESS_BOOT_ID:
                automation.observe_safety_event(con, "RESTART_RECOVERED", {
                    "intent_id": intent_id,
                    "client_order_id": order.client_order_id,
                    "submitting_boot_id": submitting_boot,
                    "recovering_boot_id": PROCESS_BOOT_ID})
        local = con.execute(
            "SELECT quantity FROM managed_positions WHERE position_id=?",
            (intent_id,)).fetchone()
        recorded_quantity = Decimal(local[0]) if local else Decimal(0)
        delta = order.filled_quantity - recorded_quantity
        if delta > 0:
            fee_rows = con.execute(
                "SELECT payload FROM position_events WHERE position_id=? AND event='FILL'",
                (intent_id,)).fetchall() if local else []
            recorded_fee = sum((Decimal(str(json.loads(x[0]).get("fee") or "0"))
                                for x in fee_rows), Decimal(0))
            delta_fee = max(Decimal(0), order.cumulative_fee - recorded_fee)
            fill_price = order.average_fill_price or order.limit_price or plan.intent.entry
            if fill_price is None:
                refused.append({"intent_id": intent_id,
                                "reason": "fill price unavailable; protection cannot be audited"})
                continue
            fill = Fill(
                fill_id=f"{order.broker_order_id or order.client_order_id}:{order.filled_quantity}",
                broker_order_id=str(order.broker_order_id or ""),
                symbol=order.symbol, quantity=delta, price=fill_price,
                fee=delta_fee, occurred_at=order.updated_at)
            positions.apply_fill(con, broker, plan, fill)
        # Expiry, honoured on the private path the way the paper monitor has
        # always honoured it. (Paper compares candle open_ts; here it is wall
        # clock — a small, deliberate skew, because a resting venue order has
        # no candle.) Any unfilled remainder past expires_at is cancelled at
        # the venue; fills already recorded above are kept. The failure modes
        # are loud on purpose: a cancel that races a fill 4xxes, the audit
        # event says so, and the next poll sees whichever won.
        status = str(order.status).upper().replace("_", "")
        _active = status not in {"FILLED", "DONE", "CANCELED", "CANCELLED",
                                 "REJECTED", "EXPIRED"}
        _total = order.quantity or plan.risk.quantity
        if (plan.intent.expires_at and _active
                and int(time.time()) >= int(plan.intent.expires_at)
                and order.filled_quantity < _total):
            _cancel_id = (order.client_order_id or
                          str(submitted.get("client_order_id") or ""))
            _pre_cancel_fill = order.filled_quantity
            try:
                order = broker.cancel(plan.intent.symbol, _cancel_id)
                # A cancel ack that omits the cumulative fill must not erase
                # one we already saw — mapping a partially-filled entry to
                # ENTRY_CANCELED would drop it from this monitor's scan set
                # while custody still holds the fill.
                if order.filled_quantity < _pre_cancel_fill:
                    from dataclasses import replace as _dc_replace
                    order = _dc_replace(order,
                                        filled_quantity=_pre_cancel_fill)
                _audit_event(con, intent_id, "EXPIRY_CANCELLED", {
                    "expires_at": int(plan.intent.expires_at),
                    "filled_quantity": str(order.filled_quantity)})
            except Exception as exc:
                from .phemex_private import AmbiguousSubmission, PhemexError
                if isinstance(exc, AmbiguousSubmission):
                    refused.append({"intent_id": intent_id,
                                    "reason": "expiry cancel ambiguous; retrying next cycle"})
                    continue
                if isinstance(exc, PhemexError):
                    _audit_event(con, intent_id, "EXPIRY_CANCEL_FAILED", {
                        "reason": str(exc)[:400]})
                    from .runlog import get_logger
                    get_logger().warning(
                        f"expiry cancel failed for {intent_id}: {exc}")
                else:
                    raise
            status = str(order.status).upper().replace("_", "")
        if status in {"FILLED", "DONE"}:
            next_state = "ENTRY_FILLED"
        elif order.filled_quantity > 0:
            # Includes a partially-filled entry whose remainder was just
            # cancelled: it stays PARTIALLY_FILLED until lifecycle qualifies
            # the exit — pre-existing custody behaviour, deliberately kept.
            next_state = "PARTIALLY_FILLED"
        elif status in {"CANCELED", "CANCELLED", "REJECTED", "EXPIRED"}:
            next_state = "ENTRY_" + status
        else:
            next_state = "SUBMITTED"
        if next_state != "SUBMITTED":
            _event(con, intent_id, next_state, to_wire(order))
        if next_state == "PARTIALLY_FILLED":
            automation.observe_safety_event(con, "PARTIAL_FILL_PROTECTED", {
                "intent_id": intent_id,
                "filled_quantity": str(order.filled_quantity)})
        if next_state == "ENTRY_REJECTED":
            automation.observe_safety_event(con, "ORDER_REJECTED", {
                "intent_id": intent_id, "raw_code": order.raw_code})
        updated.append({"intent_id": intent_id, "state": next_state,
                        "filled_quantity": str(order.filled_quantity)})
    if refused:
        # A monitor that cannot resolve an order is a degraded path, and the
        # house rule is that degraded paths are audible. live.py used to
        # discard this return entirely.
        from .runlog import get_logger
        get_logger().warning(
            f"private monitor: {len(refused)} intent(s) unresolved — " +
            "; ".join(f"{r['intent_id']}: {r['reason']}" for r in refused[:5]))
    return {"updated": updated, "refused": refused,
            "environment": broker.environment,
            "version": EXECUTION_CORE_VERSION}


def monitor_paper(con) -> dict:
    """Resolve durable PAPER intents from closed candles, deterministically.

    This is research execution, not a broker surrogate: limits fill on touch,
    markets fill at the next closed candle's open, and same-bar stop/target
    ambiguity resolves stop-first. Every transition stays in the outbox log.
    """
    _ensure(con)
    rows = con.execute(
        "SELECT intent_id,payload,state FROM execution_outbox WHERE mode='PAPER' "
        "AND state IN ('PAPER_ROUTED','PAPER_FILLED') ORDER BY id").fetchall()
    updated, refused = [], []
    for intent_id, raw_plan, state in rows:
        plan = _plan_from_wire(raw_plan)
        if plan is None or not plan.intent.timeframe:
            refused.append({"intent_id": intent_id,
                            "reason": "paper plan has no readable timeframe"})
            continue
        intent, tf = plan.intent, plan.intent.timeframe
        candles = con.execute(
            "SELECT open_ts,open,high,low,close FROM candles "
            "WHERE symbol=? AND tf=? AND open_ts>=? ORDER BY open_ts",
            (intent.symbol, tf, intent.created_at)).fetchall()
        if not candles:
            continue
        position = con.execute(
            "SELECT entry,filled_at,target,entry_role FROM paper_positions WHERE intent_id=?",
            (intent_id,)).fetchone()
        if state == "PAPER_ROUTED":
            from . import costs, execsim
            eligible = [c for c in candles if intent.expires_at is None or
                        c[0] < intent.expires_at]
            if not eligible:
                expired_at = intent.expires_at or candles[0][0]
                _event(con, intent_id, "PAPER_EXPIRED", {
                    "environment": "paper", "expired_at": expired_at})
                updated.append({"intent_id": intent_id, "state": "PAPER_EXPIRED"})
                _complete_shadow_comparison(con, intent_id, {
                    "state": "PAPER_EXPIRED", "expired_at": expired_at})
                continue
            paper_candles = [
                {"open_ts": c[0], "open": c[1], "high": c[2],
                 "low": c[3], "close": c[4]} for c in eligible]
            entry_model = intent.entry_model or (
                "MARKET_NEXT_OPEN" if intent.order_kind == OrderKind.MARKET
                else "MAKER_PULLBACK")
            model_entry = (Decimal(eligible[0][1])
                           if intent.order_kind == OrderKind.MARKET
                           else intent.entry)
            if model_entry is None:
                refused.append({"intent_id": intent_id,
                                "reason": "paper plan has no entry price"})
                continue
            simulation = execsim.simulate_entry(
                paper_candles, [None] * len(paper_candles), 0,
                model_entry, intent.stop, intent.direction == "LONG",
                entry_model=entry_model,
                maker_limit=intent.entry,
                maker_wait=max(1, int(intent.maker_wait_bars or len(eligible))),
                profile=costs.profile_for(intent.symbol),
                max_entry_bars=max(1, len(eligible)))
            if simulation["note"]:
                from .runlog import get_logger
                get_logger().warning(
                    f"paper {intent.symbol} {tf}: {simulation['note']}")
            if simulation["status"] == "PENDING":
                continue
            if simulation["status"] == "MISSED":
                expired_at = (intent.expires_at or
                              eligible[-1][0])
                _event(con, intent_id, "PAPER_EXPIRED", {
                    "environment": "paper", "expired_at": expired_at,
                    "entry_model": entry_model})
                updated.append({"intent_id": intent_id, "state": "PAPER_EXPIRED"})
                _complete_shadow_comparison(con, intent_id, {
                    "state": "PAPER_EXPIRED", "expired_at": expired_at})
                continue
            fill_row = eligible[simulation["fill_i"]]
            fill_price = simulation["entry"]
            entry_role = simulation["entry_role"]
            target = intent.targets[0] if intent.targets else None
            con.execute(
                "INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,"
                "entry,stop,target,state,filled_at,entry_role) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (intent_id, intent.symbol, tf, intent.direction, str(intent.quantity),
                 str(fill_price), str(intent.stop),
                 None if target is None else str(target), "OPEN", fill_row[0],
                 entry_role))
            _event(con, intent_id, "PAPER_FILLED", {
                "environment": "paper", "price": str(fill_price),
                "quantity": str(intent.quantity), "filled_at": fill_row[0],
                "entry_role": entry_role, "entry_model": entry_model})
            position = (str(fill_price), fill_row[0],
                        None if target is None else str(target), entry_role)
            state = "PAPER_FILLED"
        if state != "PAPER_FILLED" or position is None:
            continue
        entry, filled_at, raw_target = Decimal(position[0]), int(position[1]), position[2]
        entry_role = position[3] or (
            "TAKER" if intent.order_kind == OrderKind.MARKET else "MAKER")
        target = None if raw_target is None else Decimal(raw_target)
        held = [c for c in candles if c[0] >= filled_at]
        close = None
        for index, candle in enumerate(held):
            high, low = Decimal(candle[2]), Decimal(candle[3])
            stop_hit = (low <= intent.stop if intent.direction == "LONG"
                        else high >= intent.stop)
            target_hit = bool(target is not None and (
                high >= target if intent.direction == "LONG" else low <= target))
            if stop_hit:
                close = ("SL", intent.stop, candle[0]); break
            if target_hit:
                close = ("TP", target, candle[0]); break
            if index + 1 >= PAPER_MAX_HOLDING_BARS:
                close = ("TIMEOUT", Decimal(candle[4]), candle[0]); break
        if close is None:
            updated.append({"intent_id": intent_id, "state": "PAPER_FILLED"})
            continue
        outcome, exit_price, closed_at = close
        risk_per_unit = abs(entry - intent.stop)
        from . import costs, execsim, importer, volatility
        profile = costs.profile_for(intent.symbol)
        atr_exit = None
        try:
            atr_row = con.execute(
                "SELECT payload FROM facts WHERE symbol=? AND tf=? "
                "AND kind='volatility' AND algo_version=? AND market_time<=? "
                "ORDER BY market_time DESC,id DESC LIMIT 1",
                (intent.symbol, tf, volatility.VOLATILITY_VERSION,
                 closed_at)).fetchone()
            atr_value = json.loads(atr_row[0]).get("atr") if atr_row else None
            atr_exit = None if atr_value in (None, "") else Decimal(str(atr_value))
        except Exception:
            atr_exit = None
        settlement = execsim.settle(
            profile, intent.symbol, entry, exit_price, risk_per_unit,
            intent.direction == "LONG", outcome, held.index(next(
                candle for candle in held if candle[0] == closed_at)),
            importer.TF_SECONDS[tf], atr_exit,
            entry_role=entry_role)
        if settlement["slip_missing"]:
            from .runlog import get_logger
            get_logger().warning(
                f"paper {intent.symbol} {tf}: no ATR at exit for {intent_id}; "
                "slippage recorded as unavailable")
        r_multiple = settlement["r_mult"]
        con.execute(
            "UPDATE paper_positions SET state='CLOSED',closed_at=?,outcome=?,"
            "exit_price=?,r_multiple=?,fees_price_units=?,funding_price_units=?,"
            "slippage_price_units=?,cost_profile_version=? WHERE intent_id=?",
            (closed_at, outcome, str(settlement["eff_exit"]), str(r_multiple),
             str(settlement["fees"]), str(settlement["funding"]),
             str(settlement["slip"]), profile.version, intent_id))
        payload = {"environment": "paper", "outcome": outcome,
                   "exit_price": str(exit_price),
                   "effective_exit_price": str(settlement["eff_exit"]),
                   "r_gross": str(settlement["r_gross"]),
                   "r_multiple": str(r_multiple),
                   "fees_price_units": str(settlement["fees"]),
                   "funding_price_units": str(settlement["funding"]),
                   "slippage_price_units": str(settlement["slip"]),
                   "slippage_missing": settlement["slip_missing"],
                   "cost_profile_version": profile.version,
                   "closed_at": closed_at}
        _event(con, intent_id, "PAPER_CLOSED", payload)
        _event(con, intent_id, "ORDER_LIFECYCLE_COMPLETE", payload)
        _complete_shadow_comparison(con, intent_id, {
            "state": "PAPER_CLOSED", **payload})
        updated.append({"intent_id": intent_id, "state": "PAPER_CLOSED",
                        "outcome": outcome, "r_multiple": str(r_multiple)})
    return {"updated": updated, "refused": refused,
            "version": EXECUTION_CORE_VERSION}


def paper_positions(con, *, include_closed: bool = False) -> list[dict]:
    _ensure(con)
    where = "" if include_closed else " WHERE state='OPEN'"
    columns = [row[1] for row in con.execute("PRAGMA table_info(paper_positions)")]
    return [dict(zip(columns, row)) for row in con.execute(
        "SELECT * FROM paper_positions" + where + " ORDER BY filled_at DESC").fetchall()]


@dataclass
class Coordinator:
    broker: Broker | None = None

    def dispatch(self, con, plan: ExecutionPlan, *, live_gate: dict | None = None,
                 operational: dict | None = None) -> dict:
        queued = enqueue(con, plan.intent, plan=plan)
        mode = plan.intent.mode
        state = automation.status(con, live_gate=live_gate, operational=operational)
        if mode != state.mode:
            raise DispatchRejected(
                f"intent mode {mode.value} does not match active mode {state.mode.value}")
        # The outbox state is the retry authority. Once an intent has crossed a
        # routing boundary, an identical scan/retry returns that recorded state
        # and must never call the broker a second time. SUBMIT_FAILED is the
        # one deliberate exception: it is only ever written for failures
        # proven to have happened BEFORE the wire, so no order can exist and
        # a retry is safe.
        if queued["state"] not in {"PENDING", "SUBMITTING", "SUBMIT_FAILED"}:
            return {"submitted": queued["state"] == "SUBMITTED",
                    "state": queued["state"], "queue": queued,
                    "idempotent_replay": True}
        if (not plan.risk.approved or plan.risk.quantity <= 0 or
                plan.risk.quantity != plan.intent.quantity):
            _event(con, plan.intent.intent_id, "RISK_REJECTED", {
                "submitted": False, "decision": plan.risk.decision,
                "reasons": to_wire(plan.risk.reasons)})
            return {"submitted": False, "state": "RISK_REJECTED", "queue": queued}
        if mode == AutomationMode.OFF:
            _event(con, plan.intent.intent_id, "HELD_OFF", {"submitted": False})
            return {"submitted": False, "state": "HELD_OFF", "queue": queued}
        if mode == AutomationMode.PAPER:
            _event(con, plan.intent.intent_id, "PAPER_ROUTED", {"submitted": False})
            return {"submitted": False, "state": "PAPER_ROUTED", "queue": queued}
        if mode == AutomationMode.SHADOW:
            paper_key = intent_key(
                plan.intent.setup_id, AutomationMode.PAPER,
                plan.intent.order_kind.value, str(plan.intent.quantity),
                None if plan.intent.entry is None else str(plan.intent.entry))
            paper_intent = replace(
                plan.intent, mode=AutomationMode.PAPER,
                intent_id="paper-" + hashlib.sha256(
                    f"shadow|{plan.intent.intent_id}".encode()).hexdigest()[:32],
                idempotency_key=paper_key)
            paper_plan = replace(plan, intent=paper_intent)
            paper_queue = enqueue(con, paper_intent, plan=paper_plan)
            paper_intent_id = paper_queue["intent_id"]
            if paper_queue["state"] == "PENDING":
                _event(con, paper_intent_id, "PAPER_ROUTED", {
                    "submitted": False, "shadow_intent_id": plan.intent.intent_id})
            _audit_event(con, plan.intent.intent_id, "SHADOW_PAIRED", {
                "paper_intent_id": paper_intent_id,
                "decision_hash": _decision_hash(plan)})
            _event(con, plan.intent.intent_id, "SHADOW_RECORDED", {"submitted": False})
            return {"submitted": False, "state": "SHADOW_RECORDED", "queue": queued}
        if not state.dispatch_allowed:
            if state.halted and mode == AutomationMode.TESTNET:
                automation.observe_safety_event(con, "KILL_SWITCH_BLOCKED", {
                    "intent_id": plan.intent.intent_id, "mode": mode.value})
            raise DispatchRejected(f"{mode.value} dispatch is promotion-gated")
        if self.broker is None:
            raise DispatchRejected("no private broker adapter is configured")
        expected_environment = "testnet" if mode == AutomationMode.TESTNET else "mainnet"
        if self.broker.environment != expected_environment:
            raise DispatchRejected(
                f"{mode.value} cannot use a {self.broker.environment} broker")
        # A process restart, private-stream gap or manual venue action can make
        # durable intent state disagree with the account. No new exposure is
        # permitted until an explicit reconciliation says they match.
        from . import positions
        try:
            positions.require_reconciled(con, expected_environment)
        except positions.ReconciliationBlocked as exc:
            raise DispatchRejected(str(exc)) from exc
        if queued["state"] == "SUBMITTING":
            event = con.execute(
                "SELECT payload FROM execution_events WHERE intent_id=? "
                "AND event='SUBMITTING' ORDER BY id DESC LIMIT 1",
                (plan.intent.intent_id,)).fetchone()
            payload = json.loads(event[0]) if event else {}
            client_id = str(payload.get("client_order_id") or "")
            recovered = self.broker.order_status(
                plan.intent.symbol, client_id, payload.get("broker_order_id"))
            if recovered is None:
                raise DispatchRejected(
                    "prior venue submission is unresolved; refusing to resubmit")
            _event(con, plan.intent.intent_id, "SUBMITTED", to_wire(recovered))
            return {"submitted": True, "state": "SUBMITTED",
                    "order": to_wire(recovered), "queue": queued,
                    "idempotent_replay": True}
        client_id = (self.broker.client_order_id(plan)
                     if hasattr(self.broker, "client_order_id") else
                     "ss-" + plan.intent.idempotency_key[:37])
        _event(con, plan.intent.intent_id, "SUBMITTING", {
            "client_order_id": client_id, "symbol": plan.intent.symbol,
            "boot_id": PROCESS_BOOT_ID})
        try:
            order = self.broker.submit(plan)
        except Exception as exc:
            from .phemex_private import AmbiguousSubmission, PhemexError
            if isinstance(exc, PhemexError) and not isinstance(exc, AmbiguousSubmission):
                # Proven pre-wire: validate_plan is pure, enforce_one_way and
                # set_leverage precede the order POST, and a 4xx creates no
                # order. No venue order can exist, so the refusal is recorded
                # as its own state and the intent stays retryable. This must
                # NOT fire ORDER_REJECTED — that drill is for the venue
                # rejecting a real submission, and a local refusal passing it
                # would be the restart-drill defect again in a new spot.
                _event(con, plan.intent.intent_id, "SUBMIT_FAILED", {
                    "submitted": False, "reason": str(exc)[:400],
                    "error_type": type(exc).__name__})
                from .runlog import get_logger
                get_logger().warning(
                    f"dispatch {plan.intent.intent_id} refused before the "
                    f"wire: {type(exc).__name__}: {exc}")
                return {"submitted": False, "state": "SUBMIT_FAILED",
                        "reason": str(exc)[:400], "queue": queued}
            raise  # ambiguous or unexpected: stay SUBMITTING, never resubmit
        _event(con, plan.intent.intent_id, "SUBMITTED", to_wire(order))
        return {"submitted": True, "state": "SUBMITTED", "order": to_wire(order),
                "queue": queued}
