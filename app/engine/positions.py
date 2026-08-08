"""Reconciled position custody and mandatory protection.

No new TESTNET/LIVE entry is safe until local intent state agrees with the
broker.  The first fill immediately creates actual exposure, so protection is
confirmed against actual filled quantity; failure triggers a reduce-only close
and an operator halt.  PAPER/SHADOW may exercise the same state machine with a
simulated broker, but cannot reach a private adapter through this module.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from decimal import Decimal

from . import settings
from .contracts import ControlOwner, ExecutionPlan, Fill, to_wire


POSITION_VERSION = "positions-v0.3-draft"
PROTECTION_DEADLINE_SECONDS = 5
RECONCILIATION_MAX_AGE_SECONDS = 60
CUSTODY_CONFIRMATION_GAP_SECONDS = 5


class ReconciliationBlocked(RuntimeError):
    pass


class ProtectionFailed(RuntimeError):
    pass


def _ensure(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS managed_positions (
        position_id TEXT PRIMARY KEY,
        intent_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        quantity TEXT NOT NULL,
        entry TEXT NOT NULL,
        stop TEXT NOT NULL,
        owner TEXT NOT NULL,
        protection_client_id TEXT,
        protection_status TEXT NOT NULL,
        state TEXT NOT NULL,
        updated_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS position_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position_id TEXT NOT NULL,
        event TEXT NOT NULL,
        occurred_at INTEGER NOT NULL,
        payload TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS reconciliation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        environment TEXT NOT NULL,
        observed_at INTEGER NOT NULL,
        matched INTEGER NOT NULL,
        payload TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS custody_observations (
        position_id TEXT PRIMARY KEY,
        missing_count INTEGER NOT NULL DEFAULT 0,
        last_observed_at INTEGER NOT NULL)""")


def _event(con, position_id: str, event: str, payload: dict) -> None:
    con.execute(
        "INSERT INTO position_events(position_id,event,occurred_at,payload) "
        "VALUES(?,?,?,?)",
        (position_id, event, int(time.time()),
         json.dumps(payload, sort_keys=True, separators=(",", ":"))))


def _known_order_clients(con) -> set[str]:
    try:
        rows = con.execute(
            "SELECT e.payload FROM execution_events e "
            "LEFT JOIN managed_positions p ON p.intent_id=e.intent_id "
            "WHERE e.event='SUBMITTED' AND (p.state IS NULL OR p.state!='CLOSED')"
        ).fetchall()
    except Exception:
        return set()
    out = set()
    for (raw,) in rows:
        try:
            client = json.loads(raw).get("client_order_id")
        except (TypeError, ValueError):
            client = None
        if client:
            out.add(str(client))
    try:
        rows = con.execute(
            "SELECT protection_client_id FROM managed_positions "
            "WHERE state!='CLOSED' AND protection_client_id IS NOT NULL").fetchall()
        out.update(str(row[0]) for row in rows if row[0])
    except Exception:
        pass
    return out


def _execution_event_once(con, event: str, payload: dict) -> None:
    """Record one operational finding per stable payload, not per poll."""
    raw = json.dumps(payload, sort_keys=True)
    try:
        exists = con.execute(
            "SELECT 1 FROM execution_events WHERE event=? AND payload=? LIMIT 1",
            (event, raw)).fetchone()
        if not exists:
            con.execute(
                "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
                "VALUES(?,?,?,?)", ("RECONCILIATION", event, int(time.time()), raw))
    except Exception:
        pass


def _position_quantity(row: dict) -> Decimal:
    for key in ("sizeRq", "size", "qty", "positionQtyRq"):
        if row.get(key) not in (None, ""):
            return Decimal(str(row[key]))
    return Decimal(0)


def _signed_broker_quantity(row: dict) -> Decimal:
    quantity = _position_quantity(row)
    if quantity == 0:
        return quantity
    side = str(row.get("posSide") or row.get("side") or "").upper()
    if side in {"SHORT", "SELL"}:
        return -abs(quantity)
    if side in {"LONG", "BUY"}:
        return abs(quantity)
    return quantity


def private_environments_with_exposure(con) -> set[str]:
    """Private environments that still require custody, regardless of mode."""
    _ensure(con)
    try:
        rows = con.execute(
            "SELECT DISTINCT o.mode FROM managed_positions p "
            "JOIN execution_outbox o ON o.intent_id=p.intent_id "
            "WHERE p.state!='CLOSED' AND o.mode IN ('TESTNET','LIVE')").fetchall()
    except Exception:
        return set()
    return {"testnet" if row[0] == "TESTNET" else "mainnet" for row in rows}


def reconcile(con, broker, *, symbols: list[str]) -> dict:
    """Compare broker truth to durable local custody and record the verdict."""
    _ensure(con)
    if hasattr(broker, "sync_time"):
        broker.sync_time()
    expected_orders = _known_order_clients(con)
    durable_symbols = {str(row[0]) for row in con.execute(
        "SELECT symbol FROM managed_positions").fetchall()}
    try:
        durable_symbols.update(str(row[0]) for row in con.execute(
            "SELECT symbol FROM execution_outbox").fetchall())
    except Exception:
        pass
    if getattr(broker, "account_wide_open_orders", False):
        broker_orders = list(broker.open_orders(None))
    else:
        broker_orders = []
        for symbol in sorted(set(symbols) | durable_symbols):
            broker_orders.extend(broker.open_orders(symbol))
    unknown_orders = [o.client_order_id for o in broker_orders
                      if o.client_order_id not in expected_orders]
    duplicate_clients = sorted(
        client for client, count in Counter(
            o.client_order_id for o in broker_orders if o.client_order_id).items()
        if count > 1)

    managed: dict[str, Decimal] = {}
    for symbol, direction, quantity in con.execute(
            "SELECT symbol,direction,quantity FROM managed_positions WHERE state!='CLOSED' "
            "ORDER BY position_id").fetchall():
        signed = Decimal(str(quantity)) * (Decimal(-1) if direction == "SHORT" else Decimal(1))
        managed[str(symbol)] = managed.get(str(symbol), Decimal(0)) + signed
    broker_positions = [p for p in broker.positions()
                        if _position_quantity(p) != 0]
    broker_by_symbol: dict[str, Decimal] = {}
    for row in broker_positions:
        symbol = str(row.get("symbol"))
        broker_by_symbol[symbol] = broker_by_symbol.get(symbol, Decimal(0)) + \
            _signed_broker_quantity(row)
    orphan_positions = [symbol for symbol in broker_by_symbol if symbol not in managed]
    disagreements = [symbol for symbol in set(managed) | set(broker_by_symbol)
                     if abs(managed.get(symbol, Decimal(0)) -
                            broker_by_symbol.get(symbol, Decimal(0))) > Decimal("0")]
    matched = not (unknown_orders or duplicate_clients or orphan_positions or disagreements)
    report = {
        "matched": matched, "unknown_orders": sorted(unknown_orders),
        "duplicate_orders": duplicate_clients,
        "orphan_positions": sorted(orphan_positions),
        "position_disagreements": sorted(disagreements),
        "environment": broker.environment, "version": POSITION_VERSION,
    }
    now = int(time.time())
    for client_id in duplicate_clients:
        _execution_event_once(con, "DUPLICATE_BROKER_ORDER", {
            "environment": broker.environment, "client_order_id": client_id})
    for symbol in orphan_positions:
        _execution_event_once(con, "ORPHAN_POSITION", {
            "environment": broker.environment, "symbol": symbol})
    con.execute(
        "INSERT INTO reconciliation_runs(environment,observed_at,matched,payload) "
        "VALUES(?,?,?,?)", (broker.environment, now, int(matched),
                            json.dumps(report, sort_keys=True)))
    # Feed the promotion evidence through the execution event vocabulary.
    try:
        con.execute(
            "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
            "VALUES(?,?,?,?)", ("RECONCILIATION", "RECONCILIATION", now,
                                json.dumps({"matched": matched,
                                            "environment": broker.environment})))
    except Exception:
        pass
    con.commit()
    return report


def require_reconciled(con, environment: str, *,
                       max_age_seconds: int = RECONCILIATION_MAX_AGE_SECONDS) -> None:
    _ensure(con)
    row = con.execute(
        "SELECT matched,payload,observed_at FROM reconciliation_runs WHERE environment=? "
        "ORDER BY id DESC LIMIT 1", (environment,)).fetchone()
    stale = bool(row and int(time.time()) - int(row[2]) > max_age_seconds)
    if not row or not row[0] or stale:
        detail = "startup reconciliation has not passed" if not row else row[1]
        if stale:
            detail = "private reconciliation is stale; reconcile again before dispatch"
            from . import automation
            automation.observe_safety_event(con, "STALE_RECONCILIATION_BLOCKED", {
                "environment": environment, "observed_at": row[2],
                "max_age_seconds": max_age_seconds})
        raise ReconciliationBlocked(detail)


def monitor_closures(con, broker) -> dict:
    """Confirm venue-flat custody twice before closing a durable position.

    Attached TP/SL orders are venue-managed and do not have an independent
    client id. Two consecutive private account snapshots prevent one delayed
    response from manufacturing an exit while still allowing the lifecycle to
    complete after the venue has flattened exposure.
    """
    _ensure(con)
    now = int(time.time())
    broker_by_symbol: dict[str, Decimal] = {}
    for row in broker.positions():
        symbol = str(row.get("symbol"))
        broker_by_symbol[symbol] = broker_by_symbol.get(symbol, Decimal(0)) + \
            _signed_broker_quantity(row)
    closed, pending = [], []
    rows = con.execute(
        "SELECT position_id,intent_id,symbol,direction,quantity FROM managed_positions "
        "WHERE state!='CLOSED' ORDER BY position_id").fetchall()
    for position_id, intent_id, symbol, direction, raw_quantity in rows:
        expected = Decimal(raw_quantity) * (
            Decimal(-1) if direction == "SHORT" else Decimal(1))
        actual = broker_by_symbol.get(symbol, Decimal(0))
        if actual != 0:
            con.execute(
                "INSERT INTO custody_observations(position_id,missing_count,last_observed_at) "
                "VALUES(?,0,?) ON CONFLICT(position_id) DO UPDATE SET "
                "missing_count=0,last_observed_at=excluded.last_observed_at",
                (position_id, now))
            continue
        try:
            open_entries = [order for order in broker.open_orders(symbol)
                            if order.filled_quantity < order.quantity]
        except Exception:
            open_entries = [object()]  # unknown entry state cannot authorize closure
        if open_entries:
            pending.append(position_id)
            continue
        prior = con.execute(
            "SELECT missing_count,last_observed_at FROM custody_observations "
            "WHERE position_id=?",
            (position_id,)).fetchone()
        if prior and now - int(prior[1]) < CUSTODY_CONFIRMATION_GAP_SECONDS:
            pending.append(position_id)
            continue
        count = (int(prior[0]) if prior else 0) + 1
        con.execute(
            "INSERT INTO custody_observations(position_id,missing_count,last_observed_at) "
            "VALUES(?,?,?) ON CONFLICT(position_id) DO UPDATE SET "
            "missing_count=excluded.missing_count,last_observed_at=excluded.last_observed_at",
            (position_id, count, now))
        if count < 2:
            pending.append(position_id)
            continue
        con.execute(
            "UPDATE managed_positions SET state='CLOSED',updated_at=? "
            "WHERE position_id=?", (now, position_id))
        con.execute(
            "UPDATE execution_outbox SET state='CUSTODY_CLOSED',updated_at=? "
            "WHERE intent_id=?", (now, intent_id))
        _event(con, position_id, "VENUE_FLAT_CONFIRMED", {
            "prior_quantity": str(expected), "observations": count,
            "environment": broker.environment})
        _execution_event_once(con, "CUSTODY_FLAT_CONFIRMED", {
            "environment": broker.environment, "intent_id": intent_id,
            "position_id": position_id, "closed_at": now,
            "close_reason": "VENUE_FLAT_CONFIRMED"})
        closed.append(position_id)
    con.commit()
    return {"closed": closed, "pending_confirmation": pending,
            "environment": broker.environment, "version": POSITION_VERSION}


def apply_fill(con, broker, plan: ExecutionPlan, fill: Fill) -> dict:
    """Resize exposure and confirm a reduce-only stop within the deadline."""
    _ensure(con)
    position_id = plan.intent.intent_id
    row = con.execute(
        "SELECT quantity,protection_client_id FROM managed_positions WHERE position_id=?",
        (position_id,)).fetchone()
    quantity = (Decimal(row[0]) if row else Decimal(0)) + fill.quantity
    prior_protection_client_id = row[1] if row else None
    now = int(time.time())
    con.execute(
        "INSERT INTO managed_positions(position_id,intent_id,symbol,direction,"
        "quantity,entry,stop,owner,protection_client_id,protection_status,state,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(position_id) DO UPDATE SET "
        "quantity=excluded.quantity,entry=excluded.entry,stop=excluded.stop,"
        "protection_status='PENDING',state='OPEN',updated_at=excluded.updated_at",
        (position_id, plan.intent.intent_id, fill.symbol, plan.intent.direction,
         str(quantity), str(fill.price), str(plan.intent.stop), ControlOwner.BOT.value,
         None, "PENDING", "OPEN", now))
    _event(con, position_id, "FILL", to_wire(fill))
    con.commit()

    start = time.monotonic()
    protection = None
    error = None
    try:
        remaining = lambda: max(0.0, plan.protection_deadline_seconds -
                                (time.monotonic() - start))
        attached = None
        if not prior_protection_client_id and hasattr(broker, "confirm_attached_protection"):
            attached = broker.confirm_attached_protection(
                symbol=fill.symbol, direction=plan.intent.direction,
                quantity=quantity, stop=plan.intent.stop,
                client_order_id=f"{position_id[:24]}-sl",
                timeout_seconds=remaining())
        if remaining() <= 0 and attached is None:
            raise ProtectionFailed("protective stop deadline expired")
        from . import lifecycle
        protection = lifecycle.ensure_stop(
            con, broker, position_id=position_id, symbol=fill.symbol,
            direction=plan.intent.direction, quantity=quantity,
            stop=plan.intent.stop, timeout_seconds=remaining())
        confirmed = str(protection.status).upper() in {
            "NEW", "CREATED", "UNTRIGGERED", "OPEN", "PARTIALLYFILLED"}
        if not confirmed or time.monotonic() - start > plan.protection_deadline_seconds:
            raise ProtectionFailed("protective stop was not confirmed before the deadline")
    except Exception as exc:  # exposure exists: recovery is more important than type
        error = f"{type(exc).__name__}: {exc}"

    if error:
        con.execute(
            "UPDATE managed_positions SET protection_status='FAILED',state='UNPROTECTED',"
            "updated_at=? WHERE position_id=?", (int(time.time()), position_id))
        _event(con, position_id, "PROTECTION_FAILED", {"error": error,
                                                       "emergency_close": "PENDING"})
        settings.set_many(con, {"halted": True}, note="protective stop failure")
        con.commit()
        try:
            from . import lifecycle
            close = lifecycle.ensure_emergency(
                con, broker, position_id=position_id, symbol=fill.symbol,
                direction=plan.intent.direction, quantity=quantity,
                timeout_seconds=max(0.1, plan.protection_deadline_seconds -
                                    (time.monotonic() - start)))
            con.execute(
                "UPDATE managed_positions SET state='EMERGENCY_CLOSE',updated_at=? "
                "WHERE position_id=?", (int(time.time()), position_id))
            _event(con, position_id, "EMERGENCY_CLOSE_SUBMITTED", to_wire(close))
            con.commit()
        except Exception as close_exc:
            _event(con, position_id, "EMERGENCY_CLOSE_UNKNOWN", {
                "error": f"{type(close_exc).__name__}: {close_exc}"})
            con.commit()
            raise ProtectionFailed(
                f"{error}; emergency close state unknown: {close_exc}") from close_exc
        raise ProtectionFailed(error)

    con.execute(
        "UPDATE managed_positions SET protection_client_id=?,protection_status='CONFIRMED',"
        "updated_at=? WHERE position_id=?",
        (protection.client_order_id, int(time.time()), position_id))
    _event(con, position_id, "PROTECTION_CONFIRMED", to_wire(protection))
    from . import lifecycle
    try:
        target = plan.intent.targets[0] if plan.intent.targets else None
        target_order = (lifecycle.ensure_target(
            con, broker, position_id=position_id, symbol=fill.symbol,
            direction=plan.intent.direction, quantity=quantity, target=target)
            if target is not None and hasattr(broker, "submit_target") else None)
        if target_order is not None:
            _event(con, position_id, "TARGET_CONFIRMED", to_wire(target_order))
    except Exception as exc:
        settings.set_many(con, {"halted": True},
                          note="autonomous target state ambiguous")
        _event(con, position_id, "TARGET_UNKNOWN", {
            "error": f"{type(exc).__name__}: {exc}"})
        con.commit()
        raise lifecycle.LifecycleBlocked(
            "position is protected but target state is ambiguous") from exc
    from . import automation
    automation.observe_safety_event(con, "PROTECTIVE_STOP_CONFIRMED", {
        "position_id": position_id, "symbol": fill.symbol,
        "protection_client_id": protection.client_order_id})
    con.commit()
    return {"position_id": position_id, "quantity": str(quantity),
            "protection": to_wire(protection), "version": POSITION_VERSION}


def manual_override(con, position_id: str) -> dict:
    """Hand custody to the operator without removing server-side protection."""
    _ensure(con)
    row = con.execute(
        "SELECT protection_status FROM managed_positions WHERE position_id=? AND state='OPEN'",
        (position_id,)).fetchone()
    if not row:
        raise ValueError("open managed position not found")
    if row[0] != "CONFIRMED":
        raise ProtectionFailed("manual override requires a confirmed protective stop")
    con.execute("UPDATE managed_positions SET owner=?,updated_at=? WHERE position_id=?",
                (ControlOwner.MANUAL_OVERRIDE.value, int(time.time()), position_id))
    _event(con, position_id, "MANUAL_OVERRIDE", {"protection_left_active": True})
    con.commit()
    return {"position_id": position_id, "owner": ControlOwner.MANUAL_OVERRIDE.value,
            "protection_left_active": True}


def return_control(con, position_id: str, broker=None) -> dict:
    _ensure(con)
    row = con.execute(
        "SELECT symbol,direction,quantity,stop,protection_client_id "
        "FROM managed_positions WHERE position_id=? AND state='OPEN' AND owner=? "
        "AND protection_status='CONFIRMED'",
        (position_id, ControlOwner.MANUAL_OVERRIDE.value)).fetchone()
    if not row:
        raise ValueError("position is not safely eligible to return to bot control")
    if broker is None or not hasattr(broker, "confirm_attached_protection"):
        raise ProtectionFailed("return to bot requires fresh broker protection confirmation")
    protection = broker.confirm_attached_protection(
        symbol=row[0], direction=row[1], quantity=Decimal(row[2]),
        stop=Decimal(row[3]), client_order_id=row[4] or f"{position_id[:24]}-sl",
        timeout_seconds=PROTECTION_DEADLINE_SECONDS)
    if protection is None:
        raise ProtectionFailed("broker no longer confirms the protective stop")
    changed = con.execute(
        "UPDATE managed_positions SET owner=?,updated_at=? WHERE position_id=? "
        "AND state='OPEN' AND owner=? AND protection_status='CONFIRMED'",
        (ControlOwner.BOT.value, int(time.time()), position_id,
         ControlOwner.MANUAL_OVERRIDE.value)).rowcount
    if not changed:
        raise ValueError("position is not safely eligible to return to bot control")
    _event(con, position_id, "RETURNED_TO_BOT", {"protection_reconfirmed": True})
    con.commit()
    return {"position_id": position_id, "owner": ControlOwner.BOT.value}


def managed(con, *, include_closed: bool = False) -> list[dict]:
    """Read the server-owned custody view without creating state on GET."""
    where = "" if include_closed else " WHERE state!='CLOSED'"
    try:
        rows = con.execute(
            "SELECT position_id,intent_id,symbol,direction,quantity,entry,stop,"
            "owner,protection_client_id,protection_status,state,updated_at "
            "FROM managed_positions" + where +
            " ORDER BY updated_at DESC,position_id").fetchall()
    except Exception:
        return []
    def setup_id(intent_id):
        try:
            found = con.execute(
                "SELECT setup_id FROM execution_outbox WHERE intent_id=?",
                (intent_id,)).fetchone()
            return found[0] if found else None
        except Exception:
            return None
    return [{
        "position_id": row[0], "intent_id": row[1], "symbol": row[2],
        "direction": row[3], "quantity": row[4], "entry": row[5],
        "stop": row[6], "owner": row[7], "protection_client_id": row[8],
        "protection_status": row[9], "state": row[10], "updated_at": row[11],
        "setup_id": setup_id(row[1]),
        "version": POSITION_VERSION,
    } for row in rows]
