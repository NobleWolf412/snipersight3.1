"""Promotion-grade private lifecycle evidence.

Flatness proves custody ended; it does not prove how.  This module qualifies a
TESTNET lifecycle only from exact venue executions belonging to deterministic
SniperSight client ids, after every related order is terminal and custody is
independently observed flat.  Ambiguity remains durable and earns no credit.
"""
from __future__ import annotations

import json
import hashlib
import time
from decimal import Decimal

from . import settings
from .contracts import BrokerExecution, BrokerOrder, ControlOwner, to_wire


LIFECYCLE_VERSION = "lifecycle-v0.1-draft"
EVIDENCE_SCHEMA = "testnet-lifecycle-v1"
FLAT_CONFIRMATION_GAP_SECONDS = 5
ACTIVE = {"NEW", "CREATED", "UNTRIGGERED", "OPEN", "PARTIALLYFILLED",
          "TRIGGERED", "SUBMITTED"}
TERMINAL = {"FILLED", "DONE", "CANCELED", "CANCELLED", "REJECTED",
            "EXPIRED", "DEACTIVATED"}


class LifecycleBlocked(RuntimeError):
    pass


def _status(value: str) -> str:
    return str(value).upper().replace("_", "")


def _ensure(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS lifecycle_orders (
        position_id TEXT NOT NULL,
        role TEXT NOT NULL,
        client_order_id TEXT NOT NULL UNIQUE,
        broker_order_id TEXT,
        quantity TEXT NOT NULL,
        price TEXT,
        state TEXT NOT NULL,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY(position_id,role))""")
    con.execute("""CREATE TABLE IF NOT EXISTS lifecycle_executions (
        execution_id TEXT PRIMARY KEY,
        position_id TEXT NOT NULL,
        role TEXT NOT NULL,
        broker_order_id TEXT NOT NULL,
        client_order_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        quantity TEXT NOT NULL,
        price TEXT NOT NULL,
        fee TEXT NOT NULL,
        fee_currency TEXT NOT NULL,
        occurred_at INTEGER NOT NULL,
        payload TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS lifecycle_flat_observations (
        position_id TEXT PRIMARY KEY,
        observation_count INTEGER NOT NULL,
        last_observed_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS qualified_lifecycles (
        intent_id TEXT PRIMARY KEY,
        position_id TEXT NOT NULL UNIQUE,
        completed_at INTEGER NOT NULL,
        payload TEXT NOT NULL)""")


def _position_event(con, position_id: str, event: str, payload: dict) -> None:
    con.execute(
        "INSERT INTO position_events(position_id,event,occurred_at,payload) "
        "VALUES(?,?,?,?)",
        (position_id, event, int(time.time()),
         json.dumps(payload, sort_keys=True, separators=(",", ":"))))


def record_order(con, position_id: str, role: str,
                 order: BrokerOrder, *, quantity: Decimal,
                 price: Decimal | None) -> None:
    """Record the venue identity of an already accepted child order."""
    _ensure(con)
    con.execute(
        "INSERT INTO lifecycle_orders(position_id,role,client_order_id,"
        "broker_order_id,quantity,price,state,updated_at) VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(position_id,role) DO UPDATE SET "
        "client_order_id=excluded.client_order_id,"
        "broker_order_id=COALESCE(excluded.broker_order_id,broker_order_id),"
        "quantity=excluded.quantity,price=excluded.price,state=excluded.state,"
        "updated_at=excluded.updated_at",
        (position_id, role, order.client_order_id, order.broker_order_id,
         str(quantity), None if price is None else str(price),
         _status(order.status), int(time.time())))
    con.commit()


def ensure_stop(con, broker, *, position_id: str, symbol: str,
                direction: str, quantity: Decimal, stop: Decimal,
                timeout_seconds: float | None = None) -> BrokerOrder:
    """Create or resize the deterministic standalone stop before relying on it."""
    _ensure(con)
    client_id = f"{position_id[:24]}-sl"[:40]
    row = con.execute(
        "SELECT broker_order_id,quantity,state FROM lifecycle_orders "
        "WHERE position_id=? AND role='STOP'", (position_id,)).fetchone()
    if row and _status(row[2]) == "SUBMITTING":
        recovered = broker.order_status(symbol, client_id, row[0])
        if recovered is None:
            raise LifecycleBlocked("protective stop submission remains ambiguous")
        record_order(con, position_id, "STOP", recovered,
                     quantity=quantity, price=stop)
        return recovered
    current = (broker.order_status(symbol, client_id, row[0]) if row else None)
    if row and current is None:
        raise LifecycleBlocked("protective stop state is not definitive")
    if row and _status(current.status) in TERMINAL:
        raise LifecycleBlocked("a late fill arrived after the protective stop terminated")
    if row and Decimal(row[1]) == quantity and _status(current.status) in ACTIVE:
        order = current
        if order is None:
            raise LifecycleBlocked("protective stop acceptance is not definitive")
        record_order(con, position_id, "STOP", order,
                     quantity=quantity, price=stop)
        return order
    if row:
        con.execute(
            "UPDATE lifecycle_orders SET state='REPLACING',quantity=?,price=?,"
            "updated_at=? WHERE position_id=? AND role='STOP'",
            (str(quantity), str(stop), int(time.time()), position_id))
        con.commit()
        order = broker.replace(
            symbol, client_id, quantity=quantity, stop=stop,
            timeout_seconds=timeout_seconds)
        record_order(con, position_id, "STOP", order,
                     quantity=quantity, price=stop)
        return order
    con.execute(
        "INSERT INTO lifecycle_orders(position_id,role,client_order_id,"
        "quantity,price,state,updated_at) VALUES(?,?,?,?,?,'SUBMITTING',?)",
        (position_id, "STOP", client_id, str(quantity), str(stop),
         int(time.time())))
    con.commit()
    order = broker.submit_protective_stop(
        symbol=symbol, direction=direction, quantity=quantity, stop=stop,
        client_order_id=client_id, timeout_seconds=timeout_seconds)
    record_order(con, position_id, "STOP", order,
                 quantity=quantity, price=stop)
    return order


def ensure_target(con, broker, *, position_id: str, symbol: str,
                  direction: str, quantity: Decimal,
                  target: Decimal | None) -> BrokerOrder | None:
    """Create or resize one deterministic reduce-only target, restart-safely."""
    if target is None:
        return None
    _ensure(con)
    client_id = f"{position_id[:24]}-tp1"[:40]
    row = con.execute(
        "SELECT broker_order_id,quantity,state FROM lifecycle_orders "
        "WHERE position_id=? AND role='TARGET_1'", (position_id,)).fetchone()
    if row and _status(row[2]) == "SUBMITTING":
        recovered = broker.order_status(symbol, client_id, row[0])
        if recovered is None:
            raise LifecycleBlocked("target submission remains ambiguous")
        record_order(con, position_id, "TARGET_1", recovered,
                     quantity=quantity, price=target)
        return recovered
    current = (broker.order_status(symbol, client_id, row[0]) if row else None)
    if row and current is None:
        raise LifecycleBlocked("target state is not definitive")
    if row and _status(current.status) in TERMINAL:
        raise LifecycleBlocked("a late fill arrived after the target terminated")
    if row and Decimal(row[1]) == quantity and _status(current.status) in ACTIVE:
        order = current
        if order is None:
            raise LifecycleBlocked("target acceptance is not yet definitive")
        record_order(con, position_id, "TARGET_1", order,
                     quantity=quantity, price=target)
        return order
    if row:
        con.execute(
            "UPDATE lifecycle_orders SET state='REPLACING',quantity=?,price=?,"
            "updated_at=? WHERE position_id=? AND role='TARGET_1'",
            (str(quantity), str(target), int(time.time()), position_id))
        con.commit()
        order = broker.replace(symbol, client_id, quantity=quantity, price=target)
        record_order(con, position_id, "TARGET_1", order,
                     quantity=quantity, price=target)
        return order

    con.execute(
        "INSERT INTO lifecycle_orders(position_id,role,client_order_id,"
        "quantity,price,state,updated_at) VALUES(?,?,?,?,?,'SUBMITTING',?)",
        (position_id, "TARGET_1", client_id, str(quantity), str(target),
         int(time.time())))
    con.commit()  # durable intent precedes the venue boundary
    order = broker.submit_target(
        symbol=symbol, direction=direction, quantity=quantity, target=target,
        client_order_id=client_id)
    record_order(con, position_id, "TARGET_1", order,
                 quantity=quantity, price=target)
    return order


def ensure_emergency(con, broker, *, position_id: str, symbol: str,
                     direction: str, quantity: Decimal,
                     timeout_seconds: float | None = None) -> BrokerOrder:
    """Submit one restart-recoverable reduce-only emergency close."""
    _ensure(con)
    prior_filled = Decimal(0)
    prior_rows = con.execute(
        "SELECT role,client_order_id,broker_order_id,quantity "
        "FROM lifecycle_orders WHERE position_id=? AND role LIKE 'EMERGENCY@%' "
        "ORDER BY updated_at,role",
        (position_id,)).fetchall()
    last = None
    for prior_role, prior_client, prior_broker, prior_quantity in prior_rows:
        prior = broker.order_status(symbol, prior_client, prior_broker)
        if prior is None:
            raise LifecycleBlocked("emergency close acceptance remains ambiguous")
        record_order(con, position_id, prior_role, prior,
                     quantity=Decimal(prior_quantity), price=None)
        if _status(prior.status) in ACTIVE:
            return prior  # never stack another close while one is still working
        prior_filled += prior.filled_quantity
        last = prior
    remaining = quantity - prior_filled
    if remaining <= 0:
        if last is None:
            raise LifecycleBlocked("emergency close has no remaining quantity")
        return last
    generation = hashlib.sha256(str(quantity).encode()).hexdigest()[:6]
    sequence = len(prior_rows) + 1
    role = f"EMERGENCY@{generation}@{sequence}"
    client_id = f"{position_id[:18]}-panic-{generation}-{sequence}"[:40]
    con.execute(
        "INSERT INTO lifecycle_orders(position_id,role,client_order_id,"
        "quantity,price,state,updated_at) VALUES(?,?,?,?,NULL,'SUBMITTING',?)",
        (position_id, role, client_id, str(remaining), int(time.time())))
    con.commit()
    order = broker.emergency_close(
        symbol=symbol, direction=direction, quantity=remaining,
        client_order_id=client_id, timeout_seconds=timeout_seconds)
    record_order(con, position_id, role, order,
                 quantity=remaining, price=None)
    return order


def _entry_identity(con, intent_id: str) -> tuple[str, str | None]:
    row = con.execute(
        "SELECT payload FROM execution_events WHERE intent_id=? "
        "AND event IN ('SUBMITTED','SUBMITTING') ORDER BY id DESC LIMIT 1",
        (intent_id,)).fetchone()
    if not row:
        return "", None
    try:
        payload = json.loads(row[0])
    except (TypeError, ValueError):
        return "", None
    return (str(payload.get("client_order_id") or ""),
            payload.get("broker_order_id"))


def _persist_executions(con, position_id: str,
                        identities: dict[str, tuple[str, str | None]],
                        executions: list[BrokerExecution]) -> list[str]:
    mismatches = []
    for item in executions:
        identity = identities.get(item.client_order_id)
        if identity is None:
            continue
        raw_role, accepted_broker_id = identity
        if accepted_broker_id and item.broker_order_id != accepted_broker_id:
            mismatches.append(item.execution_id)
            continue
        role = raw_role.split("@", 1)[0]
        con.execute(
            "INSERT OR IGNORE INTO lifecycle_executions(execution_id,position_id,"
            "role,broker_order_id,client_order_id,symbol,side,quantity,price,fee,"
            "fee_currency,occurred_at,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item.execution_id, position_id, role, item.broker_order_id,
             item.client_order_id, item.symbol, item.side, str(item.quantity),
             str(item.price), str(item.fee), item.fee_currency,
             item.occurred_at, json.dumps(to_wire(item), sort_keys=True)))
    return mismatches


def _cancel_and_confirm(con, broker, position_id: str, symbol: str,
                        entry_client: str, entry_broker: str | None,
                        winning_role: str) -> tuple[bool, dict]:
    cleanup: dict[str, str] = {}
    identities = [("ENTRY", entry_client, entry_broker)] if entry_client else []
    identities += [(row[0], row[1], row[2]) for row in con.execute(
        "SELECT role,client_order_id,broker_order_id FROM lifecycle_orders "
        "WHERE position_id=?", (position_id,)).fetchall()]
    all_terminal = True
    for role, client_id, broker_id in identities:
        order = broker.order_status(symbol, client_id, broker_id)
        if order is None:
            cleanup[role] = "UNKNOWN"
            all_terminal = False
            continue
        status = _status(order.status)
        if status in ACTIVE and role != winning_role:
            order = broker.cancel(symbol, client_id)
            status = _status(order.status)
        cleanup[role] = status
        if status not in TERMINAL:
            all_terminal = False
        if role != "ENTRY":
            con.execute(
                "UPDATE lifecycle_orders SET broker_order_id=?,state=?,updated_at=? "
                "WHERE position_id=? AND role=?",
                (order.broker_order_id, status, int(time.time()),
                 position_id, role))
    return all_terminal, cleanup


def _flat_count(con, position_id: str, flat: bool, now: int) -> int:
    prior = con.execute(
        "SELECT observation_count,last_observed_at FROM lifecycle_flat_observations "
        "WHERE position_id=?", (position_id,)).fetchone()
    if not flat:
        con.execute(
            "INSERT INTO lifecycle_flat_observations VALUES(?,0,?) "
            "ON CONFLICT(position_id) DO UPDATE SET observation_count=0,"
            "last_observed_at=excluded.last_observed_at", (position_id, now))
        return 0
    if prior and now - int(prior[1]) < FLAT_CONFIRMATION_GAP_SECONDS:
        return int(prior[0])
    count = (int(prior[0]) if prior else 0) + 1
    con.execute(
        "INSERT INTO lifecycle_flat_observations VALUES(?,?,?) "
        "ON CONFLICT(position_id) DO UPDATE SET observation_count=excluded."
        "observation_count,last_observed_at=excluded.last_observed_at",
        (position_id, count, now))
    return count


def _weighted(rows: list[tuple[Decimal, Decimal]]) -> Decimal:
    quantity = sum((qty for qty, _ in rows), Decimal(0))
    if quantity <= 0:
        raise LifecycleBlocked("execution quantity is not positive")
    return sum((qty * price for qty, price in rows), Decimal(0)) / quantity


def recover_child_orders(con, broker) -> list[dict]:
    """Resolve pre-acceptance crash windows by deterministic client identity."""
    _ensure(con)
    blocked = []
    rows = con.execute(
        "SELECT l.position_id,l.role,l.client_order_id,l.broker_order_id,"
        "l.quantity,l.price,l.state,p.symbol,p.direction FROM lifecycle_orders l "
        "JOIN managed_positions p ON p.position_id=l.position_id "
        "WHERE l.state IN ('SUBMITTING','REPLACING') ORDER BY l.updated_at"
    ).fetchall()
    for position_id, role, client_id, broker_id, raw_qty, raw_price, state, symbol, direction in rows:
        order = broker.order_status(symbol, client_id, broker_id)
        quantity = Decimal(raw_qty)
        price = None if raw_price is None else Decimal(raw_price)
        if order is None:
            blocked.append({"position_id": position_id, "role": role,
                            "reason": "venue acceptance remains ambiguous"})
            continue
        if state == "REPLACING" and _status(order.status) in TERMINAL:
            blocked.append({"position_id": position_id, "role": role,
                            "reason": "child order terminated during replacement"})
            record_order(con, position_id, role, order,
                         quantity=quantity, price=price)
            continue
        if state == "REPLACING" and order.quantity != quantity:
            kwargs = {"quantity": quantity}
            kwargs["stop" if role == "STOP" else "price"] = price
            order = broker.replace(symbol, client_id, **kwargs)
        record_order(con, position_id, role, order,
                     quantity=quantity, price=price)
    return blocked


def monitor(con, broker) -> dict:
    """Qualify exact bot-owned TESTNET exits; everything uncertain stays open."""
    _ensure(con)
    from . import positions
    positions._ensure(con)
    if broker.environment != "testnet":
        return {"completed": [], "blocked": [], "environment": broker.environment,
                "version": LIFECYCLE_VERSION}
    recovery_blocked = recover_child_orders(con, broker)
    snapshots = broker.positions()
    signed: dict[str, Decimal] = {}
    for row in snapshots:
        symbol = str(row.get("symbol"))
        signed[symbol] = signed.get(symbol, Decimal(0)) + \
            positions._signed_broker_quantity(row)
    now = int(time.time())
    completed, blocked = [], list(recovery_blocked)
    rows = con.execute(
        "SELECT p.position_id,p.intent_id,p.symbol,p.direction,p.quantity,p.owner,"
        "p.state,o.created_at FROM managed_positions p JOIN execution_outbox o "
        "ON o.intent_id=p.intent_id WHERE o.mode='TESTNET' ORDER BY p.updated_at"
    ).fetchall()
    for position_id, intent_id, symbol, direction, raw_qty, owner, state, created_at in rows:
        exists = con.execute(
            "SELECT 1 FROM qualified_lifecycles WHERE intent_id=? LIMIT 1",
            (intent_id,)).fetchone()
        if exists:
            continue
        if state in {"UNPROTECTED", "EMERGENCY_CLOSE"}:
            try:
                ensure_emergency(
                    con, broker, position_id=position_id, symbol=symbol,
                    direction=direction, quantity=Decimal(raw_qty))
            except Exception as exc:
                blocked.append({"position_id": position_id,
                                "reason": f"emergency recovery pending: {exc}"})
                continue
        entry_client, entry_broker = _entry_identity(con, intent_id)
        role_rows = con.execute(
            "SELECT role,client_order_id,broker_order_id FROM lifecycle_orders "
            "WHERE position_id=?",
            (position_id,)).fetchall()
        identities = {client: (role, broker_id)
                      for role, client, broker_id in role_rows}
        if entry_client:
            identities[entry_client] = ("ENTRY", entry_broker)
        try:
            venue = broker.executions(symbol, start_at=int(created_at))
        except Exception as exc:
            blocked.append({"position_id": position_id,
                            "reason": f"execution history unavailable: {exc}"})
            continue
        invalid_times = [item.execution_id for item in venue
                         if item.client_order_id in identities and
                         item.occurred_at < int(created_at)]
        if invalid_times:
            blocked.append({"position_id": position_id,
                            "reason": "execution predates durable intent",
                            "execution_ids": invalid_times})
            continue
        mismatches = _persist_executions(con, position_id, identities, venue)
        if mismatches:
            blocked.append({"position_id": position_id,
                            "reason": "execution broker order identity disagrees",
                            "execution_ids": mismatches})
            continue
        exit_rows = con.execute(
            "SELECT role,execution_id,broker_order_id,client_order_id,side,quantity,"
            "price,fee,fee_currency,occurred_at FROM lifecycle_executions "
            "WHERE position_id=? AND role!='ENTRY' ORDER BY occurred_at,execution_id",
            (position_id,)).fetchall()
        if not exit_rows:
            flat = signed.get(symbol, Decimal(0)) == 0
            flat_count = _flat_count(con, position_id, flat, now)
            expected_side = "SELL" if direction == "LONG" else "BUY"
            unattributed_quantity = sum((
                item.quantity for item in venue
                if item.client_order_id not in identities and
                item.side.upper() == expected_side), Decimal(0))
            if flat_count >= 2 and unattributed_quantity >= Decimal(raw_qty):
                terminal, cleanup = _cancel_and_confirm(
                    con, broker, position_id, symbol, entry_client,
                    entry_broker, "")
                blocked.append({
                    "position_id": position_id,
                    "reason": ("flat custody has only an unattributed exit execution"
                               if terminal else
                               "unattributed flat custody cleanup is pending"),
                    "cleanup": cleanup})
                con.commit()
            continue
        exit_roles = {row[0] for row in exit_rows}
        if len(exit_roles) != 1:
            settings.set_many(con, {"halted": True},
                              note="conflicting autonomous exits")
            blocked.append({"position_id": position_id,
                            "reason": "conflicting exit roles executed"})
            continue
        winning_role = next(iter(exit_roles))
        expected_side = "SELL" if direction == "LONG" else "BUY"
        if any(str(row[4]).upper() != expected_side for row in exit_rows):
            blocked.append({"position_id": position_id,
                            "reason": "exit execution direction disagrees"})
            continue
        quantity = Decimal(raw_qty)
        exit_quantity = sum((Decimal(row[5]) for row in exit_rows), Decimal(0))
        if exit_quantity != quantity:
            blocked.append({"position_id": position_id,
                            "reason": "exit quantity does not match custody"})
            continue
        if owner != ControlOwner.BOT.value:
            blocked.append({"position_id": position_id,
                            "reason": "manual custody cannot earn autonomous credit"})
            continue
        terminal, cleanup = _cancel_and_confirm(
            con, broker, position_id, symbol, entry_client, entry_broker,
            winning_role)
        flat_count = _flat_count(
            con, position_id, signed.get(symbol, Decimal(0)) == 0, now)
        if not terminal or flat_count < 2:
            blocked.append({"position_id": position_id,
                            "reason": "cleanup or flat confirmation pending"})
            con.commit()
            continue
        entry_rows = con.execute(
            "SELECT quantity,price,fee,fee_currency,execution_id,occurred_at "
            "FROM lifecycle_executions WHERE position_id=? AND role='ENTRY' "
            "ORDER BY occurred_at,execution_id", (position_id,)).fetchall()
        entry_quantity = sum((Decimal(row[0]) for row in entry_rows), Decimal(0))
        if entry_quantity != quantity:
            blocked.append({"position_id": position_id,
                            "reason": "entry execution quantity is incomplete"})
            continue
        currencies = {row[3] for row in entry_rows} | {row[8] for row in exit_rows}
        if len(currencies) != 1:
            blocked.append({"position_id": position_id,
                            "reason": "execution fee currencies disagree"})
            continue
        payload = {
            "qualified": True, "schema": EVIDENCE_SCHEMA,
            "version": LIFECYCLE_VERSION, "environment": "testnet",
            "intent_id": intent_id, "position_id": position_id,
            "symbol": symbol, "direction": direction, "exit_cause": winning_role,
            "quantity": str(quantity),
            "entry_vwap": str(_weighted([(Decimal(r[0]), Decimal(r[1]))
                                         for r in entry_rows])),
            "exit_vwap": str(_weighted([(Decimal(r[5]), Decimal(r[6]))
                                        for r in exit_rows])),
            "entry_fee": str(sum((Decimal(r[2]) for r in entry_rows), Decimal(0))),
            "exit_fee": str(sum((Decimal(r[7]) for r in exit_rows), Decimal(0))),
            "fee_currency": next(iter(currencies)),
            "entry_execution_ids": [r[4] for r in entry_rows],
            "exit_execution_ids": [r[1] for r in exit_rows],
            "cleanup": cleanup, "flat_observations": flat_count,
            "completed_at": now,
        }
        raw_payload = json.dumps(payload, sort_keys=True)
        claimed = con.execute(
            "INSERT OR IGNORE INTO qualified_lifecycles(intent_id,position_id,"
            "completed_at,payload) VALUES(?,?,?,?)",
            (intent_id, position_id, now, raw_payload)).rowcount
        if not claimed:
            continue
        con.execute(
            "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
            "VALUES(?, 'ORDER_LIFECYCLE_COMPLETE', ?, ?)",
            (intent_id, now, raw_payload))
        con.execute("UPDATE managed_positions SET state='CLOSED',updated_at=? "
                    "WHERE position_id=?", (now, position_id))
        con.execute("UPDATE execution_outbox SET state='LIFECYCLE_COMPLETE',updated_at=? "
                    "WHERE intent_id=?", (now, intent_id))
        _position_event(con, position_id, "LIFECYCLE_QUALIFIED", payload)
        completed.append(position_id)
        con.commit()
    con.commit()
    return {"completed": completed, "blocked": blocked,
            "environment": broker.environment, "version": LIFECYCLE_VERSION}
