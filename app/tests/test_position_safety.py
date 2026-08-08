import sqlite3
from decimal import Decimal

import pytest

from engine import execution, positions, settings
from engine.contracts import (AutomationMode, BrokerOrder, DecisionReason,
                              ExecutionPlan, Fill, OrderIntent, OrderKind,
                              RiskDecision)


def memory():
    return sqlite3.connect(":memory:")


def order(client="stop-1", status="New"):
    return BrokerOrder("broker-1", client, "BTCUSDT", status, OrderKind.MARKET,
                       Decimal("0.01"), Decimal("0"), None, True, 1)


def plan():
    intent = OrderIntent(
        "intent-1", "setup-1", AutomationMode.TESTNET, "BTCUSDT", "LONG",
        OrderKind.LIMIT, Decimal("0.01"), Decimal("50000"), Decimal("49000"),
        (Decimal("52000"),), False, 1, "playbook-v1", "a" * 64)
    decision = RiskDecision(
        True, "APPROVED", Decimal("25"), Decimal("0.01"), Decimal("500"),
        Decimal("0.05"), (DecisionReason("OK", "within limits"),))
    return ExecutionPlan(intent, decision, "phemex-perp", "ISOLATED", "ONE_WAY")


class Broker:
    environment = "testnet"
    def __init__(self, *, unknown=False, position=False, protection=True,
                 emergency_failure=False, position_side="Buy"):
        self.unknown = unknown
        self.position = position
        self.protection = protection
        self.emergency_failure = emergency_failure
        self.position_side = position_side
        self.closed = False
        self.synced = False
        self.replaced = []
    def sync_time(self):
        self.synced = True
    def open_orders(self, symbol):
        return [order("unknown")] if self.unknown else []
    def positions(self):
        return [{"symbol": "BTCUSDT", "sizeRq": "0.01",
                 "side": self.position_side}] if self.position else []
    def confirm_attached_protection(self, **kwargs):
        if not self.protection:
            return None
        return order(kwargs["client_order_id"], "Open")
    def submit_protective_stop(self, **kwargs):
        if not self.protection:
            raise RuntimeError("venue refused stop")
        return order(kwargs["client_order_id"], "New")
    def emergency_close(self, **kwargs):
        if self.emergency_failure:
            raise RuntimeError("close state unknown")
        self.closed = True
        return order(kwargs["client_order_id"], "Filled")
    def replace(self, symbol, client_order_id, **kwargs):
        self.replaced.append((symbol, client_order_id, kwargs["quantity"]))
        return order(client_order_id, "New")
    def order_status(self, symbol, client_order_id, broker_order_id=None):
        return order(client_order_id, "New")


class AccountWideBroker(Broker):
    account_wide_open_orders = True
    def __init__(self):
        super().__init__()
        self.queries = []
    def open_orders(self, symbol):
        self.queries.append(symbol)
        return [order("foreign-untracked")]


class DuplicateAndOrphanBroker(Broker):
    def open_orders(self, symbol):
        return [order("duplicate"), order("duplicate")]
    def positions(self):
        return [{"symbol": "ETHUSDT", "sizeRq": "1", "side": "Buy"}]


def test_startup_reconciliation_is_required_and_unknown_state_blocks():
    con = memory()
    with pytest.raises(positions.ReconciliationBlocked):
        positions.require_reconciled(con, "testnet")
    report = positions.reconcile(con, Broker(), symbols=["BTCUSDT"])
    assert report["matched"] is True
    positions.require_reconciled(con, "testnet")
    bad = positions.reconcile(con, Broker(unknown=True), symbols=["BTCUSDT"])
    assert bad["matched"] is False


def test_account_wide_reconciliation_finds_untracked_foreign_order():
    con = memory()
    broker = AccountWideBroker()
    report = positions.reconcile(con, broker, symbols=["BTCUSDT"])
    assert report["unknown_orders"] == ["foreign-untracked"]
    assert broker.queries == [None]


def test_reconciliation_emits_deduplicated_promotion_failures():
    con = memory()
    execution._ensure(con)
    broker = DuplicateAndOrphanBroker()
    first = positions.reconcile(con, broker, symbols=["BTCUSDT"])
    positions.reconcile(con, broker, symbols=["BTCUSDT"])
    assert first["duplicate_orders"] == ["duplicate"]
    events = con.execute(
        "SELECT event,COUNT(*) FROM execution_events "
        "WHERE event IN ('DUPLICATE_BROKER_ORDER','ORPHAN_POSITION') "
        "GROUP BY event ORDER BY event").fetchall()
    assert events == [("DUPLICATE_BROKER_ORDER", 1), ("ORPHAN_POSITION", 1)]
    with pytest.raises(positions.ReconciliationBlocked):
        positions.require_reconciled(con, "testnet")


def test_first_and_partial_fills_resize_confirmed_protection():
    con = memory()
    broker = Broker()
    first = Fill("f1", "b1", "BTCUSDT", Decimal("0.004"), Decimal("50000"),
                 Decimal("0.10"), 10)
    second = Fill("f2", "b1", "BTCUSDT", Decimal("0.006"), Decimal("50010"),
                  Decimal("0.10"), 11)
    assert positions.apply_fill(con, broker, plan(), first)["quantity"] == "0.004"
    assert positions.apply_fill(con, broker, plan(), second)["quantity"] == "0.010"
    row = con.execute("SELECT quantity,protection_status FROM managed_positions").fetchone()
    assert row == ("0.010", "CONFIRMED")


def test_failed_protection_emergency_closes_and_halts_new_entries():
    con = memory()
    broker = Broker(protection=False)
    fill = Fill("f1", "b1", "BTCUSDT", Decimal("0.01"), Decimal("50000"),
                Decimal("0.10"), 10)
    with pytest.raises(positions.ProtectionFailed):
        positions.apply_fill(con, broker, plan(), fill)
    assert broker.closed is True
    assert settings.all_settings(con)["halted"] is True


def test_manual_override_keeps_stop_and_requires_explicit_return():
    con = memory()
    positions.apply_fill(
        con, Broker(), plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.01"), Decimal("50000"),
             Decimal("0.10"), 10))
    out = positions.manual_override(con, "intent-1")
    assert out["protection_left_active"] is True
    assert positions.return_control(con, "intent-1", Broker())["owner"] == "BOT"


def test_emergency_close_failure_halts_and_records_unknown_exposure():
    con = memory()
    broker = Broker(protection=False, emergency_failure=True)
    fill = Fill("f1", "b1", "BTCUSDT", Decimal("0.01"), Decimal("50000"),
                Decimal("0.10"), 10)
    with pytest.raises(positions.ProtectionFailed, match="unknown"):
        positions.apply_fill(con, broker, plan(), fill)
    assert settings.all_settings(con)["halted"] is True
    assert con.execute(
        "SELECT state,protection_status FROM managed_positions").fetchone() == \
        ("UNPROTECTED", "FAILED")
    events = [row[0] for row in con.execute(
        "SELECT event FROM position_events ORDER BY id").fetchall()]
    assert events[-2:] == ["PROTECTION_FAILED", "EMERGENCY_CLOSE_UNKNOWN"]


def test_reconciliation_rejects_equal_size_opposite_direction():
    con = memory()
    positions.apply_fill(
        con, Broker(), plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.01"), Decimal("50000"),
             Decimal("0.10"), 10))
    report = positions.reconcile(
        con, Broker(position=True, position_side="Sell"), symbols=["BTCUSDT"])
    assert report["matched"] is False
    assert report["position_disagreements"] == ["BTCUSDT"]


def test_own_protective_order_is_known_and_partial_fill_amends_it():
    con = memory()
    broker = Broker()
    positions.apply_fill(
        con, broker, plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.004"), Decimal("50000"),
             Decimal("0.10"), 10))
    positions.apply_fill(
        con, broker, plan(),
        Fill("f2", "b1", "BTCUSDT", Decimal("0.006"), Decimal("50010"),
             Decimal("0.10"), 11))
    assert broker.replaced[-1][2] == Decimal("0.010")


def test_stale_reconciliation_does_not_authorize_dispatch():
    con = memory()
    positions.reconcile(con, Broker(), symbols=["BTCUSDT"])
    con.execute("UPDATE reconciliation_runs SET observed_at=0")
    with pytest.raises(positions.ReconciliationBlocked, match="stale"):
        positions.require_reconciled(con, "testnet")


def test_managed_read_model_exposes_server_custody_fields():
    con = memory()
    positions.apply_fill(
        con, Broker(), plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.010"), Decimal("50000"),
             Decimal("0.10"), 10))
    rows = positions.managed(con)
    assert rows[0]["owner"] == "BOT"
    assert rows[0]["protection_status"] == "CONFIRMED"
    assert rows[0]["quantity"] == "0.010"


def test_unprotected_exposure_remains_in_private_custody_and_reconciliation():
    con = memory()
    broker = Broker(position=True)
    execution.enqueue(con, plan().intent, plan=plan())
    positions.apply_fill(
        con, broker, plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.010"), Decimal("50000"),
             Decimal("0.10"), 10))
    con.execute("UPDATE managed_positions SET state='UNPROTECTED'")
    con.commit()
    assert positions.private_environments_with_exposure(con) == {"testnet"}
    assert positions.reconcile(con, broker, symbols=["BTCUSDT"])["matched"] is True
    assert positions.managed(con)[0]["state"] == "UNPROTECTED"


def test_two_distinct_venue_flat_snapshots_close_custody_without_lifecycle_credit():
    con = memory()
    execution.enqueue(con, plan().intent, plan=plan())
    broker = Broker(position=True)
    positions.apply_fill(
        con, broker, plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.010"), Decimal("50000"),
             Decimal("0.10"), 10))
    broker.position = False
    first = positions.monitor_closures(con, broker)
    assert first["pending_confirmation"] == ["intent-1"]
    assert positions.managed(con)[0]["state"] == "OPEN"
    con.execute("UPDATE custody_observations SET last_observed_at=last_observed_at-5")
    second = positions.monitor_closures(con, broker)
    assert second["closed"] == ["intent-1"]
    assert positions.managed(con) == []
    assert positions.managed(con, include_closed=True)[0]["quantity"] == "0.010"
    positions.monitor_closures(con, broker)
    lifecycle_events = con.execute(
        "SELECT COUNT(*) FROM execution_events "
        "WHERE event='ORDER_LIFECYCLE_COMPLETE'").fetchone()[0]
    custody_events = con.execute(
        "SELECT COUNT(*) FROM execution_events "
        "WHERE event='CUSTODY_FLAT_CONFIRMED'").fetchone()[0]
    assert lifecycle_events == 0
    assert custody_events == 1


def test_lingering_stop_from_closed_position_blocks_reconciliation():
    con = memory()
    execution.enqueue(con, plan().intent, plan=plan())
    broker = Broker(position=True)
    positions.apply_fill(
        con, broker, plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.010"), Decimal("50000"),
             Decimal("0.10"), 10))
    con.execute("UPDATE managed_positions SET state='CLOSED'")
    con.commit()
    broker.open_orders = lambda symbol: [order("intent-1-sl", "Untriggered")]
    report = positions.reconcile(con, broker, symbols=["BTCUSDT"])
    assert report["matched"] is False
    assert report["unknown_orders"] == ["intent-1-sl"]


def test_flat_partial_fill_cannot_close_while_entry_remainder_is_active():
    con = memory()
    execution.enqueue(con, plan().intent, plan=plan())
    broker = Broker(position=True)
    positions.apply_fill(
        con, broker, plan(),
        Fill("f1", "b1", "BTCUSDT", Decimal("0.004"), Decimal("50000"),
             Decimal("0.10"), 10))
    broker.position = False
    remainder = BrokerOrder(
        "entry-1", "ss-entry", "BTCUSDT", "PartiallyFilled", OrderKind.LIMIT,
        Decimal("0.010"), Decimal("0.004"), Decimal("50000"), False, 11)
    broker.open_orders = lambda symbol: [remainder]
    assert positions.monitor_closures(con, broker)["closed"] == []
    con.execute("UPDATE custody_observations SET last_observed_at=0")
    assert positions.monitor_closures(con, broker)["closed"] == []
    assert positions.managed(con)[0]["state"] == "OPEN"
