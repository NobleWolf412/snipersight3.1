import json
import sqlite3
from decimal import Decimal

import pytest

from engine import automation, execution, lifecycle, positions
from engine.contracts import (AutomationMode, BrokerExecution, BrokerOrder,
                              DecisionReason, ExecutionPlan, Fill, OrderIntent,
                              OrderKind, RiskDecision)


def plan():
    intent = OrderIntent(
        "intent-1", "setup-1", AutomationMode.TESTNET, "BTCUSDT", "LONG",
        OrderKind.LIMIT, Decimal("0.010"), Decimal("50000"), Decimal("49000"),
        (Decimal("52000"),), False, 1, "playbook-v1", "a" * 64)
    risk = RiskDecision(
        True, "APPROVED", Decimal("10"), Decimal("0.010"), Decimal("500"),
        Decimal("0.05"), (DecisionReason("OK", "within limits"),))
    return ExecutionPlan(intent, risk, "phemex-perp", "ISOLATED", "ONE_WAY")


def broker_order(client, status="New", *, reduce_only=True,
                 quantity=Decimal("0.010"), filled=Decimal("0")):
    return BrokerOrder(
        f"venue-{client}", client, "BTCUSDT", status, OrderKind.LIMIT,
        quantity, filled, Decimal("52000"), reduce_only, 10)


class LifecycleBroker:
    environment = "testnet"

    def __init__(self, exit_role="TARGET_1"):
        self.exit_role = exit_role
        self.orders = {
            "entry-client": broker_order(
                "entry-client", "Filled", reduce_only=False,
                filled=Decimal("0.010")),
        }
        self.cancels = []

    def positions(self):
        return []

    def confirm_attached_protection(self, **kwargs):
        order = broker_order(kwargs["client_order_id"], "New")
        self.orders[order.client_order_id] = order
        return order

    def submit_protective_stop(self, **kwargs):
        order = broker_order(kwargs["client_order_id"], "New")
        self.orders[order.client_order_id] = order
        return order

    def submit_target(self, **kwargs):
        order = broker_order(kwargs["client_order_id"], "New")
        self.orders[order.client_order_id] = order
        return order

    def replace(self, symbol, client_order_id, **kwargs):
        order = broker_order(client_order_id, "New", quantity=kwargs["quantity"])
        self.orders[client_order_id] = order
        return order

    def order_status(self, symbol, client_order_id, broker_order_id=None):
        order = self.orders.get(client_order_id)
        if order and ((self.exit_role == "TARGET_1" and client_order_id.endswith("-tp1")) or
                      (self.exit_role == "STOP" and client_order_id.endswith("-sl"))):
            return broker_order(client_order_id, "Filled",
                                filled=Decimal("0.010"))
        return order

    def cancel(self, symbol, client_order_id):
        self.cancels.append(client_order_id)
        order = broker_order(client_order_id, "Canceled")
        self.orders[client_order_id] = order
        return order

    def open_orders(self, symbol):
        return [item for item in self.orders.values()
                if item.status in {"New", "Untriggered"}]

    def executions(self, symbol, *, start_at):
        role_client = ("intent-1-tp1" if self.exit_role == "TARGET_1"
                       else "intent-1-sl")
        return [
            BrokerExecution(
                "entry-exec", "venue-entry", "entry-client", symbol, "Buy",
                Decimal("0.004"), Decimal("50000"), Decimal("0.10"),
                "USDT", start_at + 1),
            BrokerExecution(
                "entry-exec-2", "venue-entry", "entry-client", symbol, "Buy",
                Decimal("0.006"), Decimal("50010"), Decimal("0.15"),
                "USDT", start_at + 2),
            BrokerExecution(
                "exit-exec", f"venue-{role_client}", role_client, symbol, "Sell",
                Decimal("0.010"),
                Decimal("52000" if self.exit_role == "TARGET_1" else "49000"),
                Decimal("0.20"), "USDT", start_at + 3),
        ]


def prepared(exit_role="TARGET_1"):
    con = sqlite3.connect(":memory:")
    p = plan()
    execution.enqueue(con, p.intent, plan=p)
    execution._event(con, p.intent.intent_id, "SUBMITTED", {
        "client_order_id": "entry-client", "broker_order_id": "venue-entry"})
    broker = LifecycleBroker(exit_role)
    positions.apply_fill(
        con, broker, p,
        Fill("fill-1", "venue-entry", "BTCUSDT", Decimal("0.010"),
             Decimal("50006"), Decimal("0.25"), 11))
    return con, broker


def test_fill_handoff_records_standalone_stop_and_target_identities():
    con, _ = prepared()
    assert con.execute(
        "SELECT role,client_order_id FROM lifecycle_orders ORDER BY role"
    ).fetchall() == [
        ("STOP", "intent-1-sl"), ("TARGET_1", "intent-1-tp1")]


@pytest.mark.parametrize("exit_role,expected", [
    ("TARGET_1", "52000"), ("STOP", "49000")])
def test_known_exit_receipt_cleanup_and_two_flat_polls_earn_one_lifecycle(
        exit_role, expected):
    con, broker = prepared(exit_role)
    first = lifecycle.monitor(con, broker)
    assert first["completed"] == []
    con.execute(
        "UPDATE lifecycle_flat_observations SET last_observed_at=last_observed_at-5")
    second = lifecycle.monitor(con, broker)
    assert second["completed"] == ["intent-1"]
    third = lifecycle.monitor(con, broker)
    assert third["completed"] == []
    assert con.execute("SELECT COUNT(*) FROM qualified_lifecycles").fetchone()[0] == 1

    raw = con.execute(
        "SELECT payload FROM execution_events "
        "WHERE event='ORDER_LIFECYCLE_COMPLETE'").fetchone()[0]
    evidence = json.loads(raw)
    assert evidence["qualified"] is True
    assert evidence["schema"] == "testnet-lifecycle-v1"
    assert evidence["exit_cause"] == exit_role
    assert evidence["exit_vwap"] == expected
    assert evidence["entry_execution_ids"] == ["entry-exec", "entry-exec-2"]
    assert evidence["exit_execution_ids"] == ["exit-exec"]
    assert evidence["entry_fee"] == "0.25"
    assert evidence["exit_fee"] == "0.20"
    assert automation.operational_evidence(con)["testnet_lifecycles"] == 1


def test_flat_without_known_exit_receipt_never_qualifies():
    con, broker = prepared()
    broker.executions = lambda *args, **kwargs: []
    lifecycle.monitor(con, broker)
    con.execute(
        "UPDATE lifecycle_flat_observations SET last_observed_at=last_observed_at-5")
    lifecycle.monitor(con, broker)
    assert con.execute(
        "SELECT COUNT(*) FROM execution_events "
        "WHERE event='ORDER_LIFECYCLE_COMPLETE'").fetchone()[0] == 0


def test_legacy_flat_only_event_does_not_block_later_qualification():
    con, broker = prepared()
    con.execute(
        "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
        "VALUES('intent-1','ORDER_LIFECYCLE_COMPLETE',1,?)",
        (json.dumps({"environment": "testnet", "qualified": False}),))
    lifecycle.monitor(con, broker)
    con.execute(
        "UPDATE lifecycle_flat_observations SET last_observed_at=last_observed_at-5")
    assert lifecycle.monitor(con, broker)["completed"] == ["intent-1"]
    assert con.execute("SELECT COUNT(*) FROM qualified_lifecycles").fetchone()[0] == 1


def test_manual_override_exit_closes_no_autonomous_evidence():
    con, broker = prepared()
    con.execute("UPDATE managed_positions SET owner='MANUAL_OVERRIDE'")
    con.commit()
    result = lifecycle.monitor(con, broker)
    assert "manual custody" in result["blocked"][0]["reason"]
    assert automation.operational_evidence(con)["testnet_lifecycles"] == 0


def test_duplicate_or_incomplete_events_do_not_inflate_promotion():
    con = sqlite3.connect(":memory:")
    execution._ensure(con)
    lifecycle._ensure(con)
    good = {
        "qualified": True, "schema": "testnet-lifecycle-v1",
        "environment": "testnet", "intent_id": "i-1",
        "position_id": "p-1", "version": "lifecycle-v0.1-draft",
        "exit_cause": "TARGET_1", "quantity": "0.01",
        "entry_vwap": "50000", "exit_vwap": "52000",
        "entry_fee": "0.1", "exit_fee": "0.1", "fee_currency": "USDT",
        "entry_execution_ids": ["e1"], "exit_execution_ids": ["x1"],
        "cleanup": {"ENTRY": "FILLED", "STOP": "CANCELED",
                    "TARGET_1": "FILLED"}, "flat_observations": 2}
    con.execute(
        "INSERT INTO qualified_lifecycles VALUES('i-1','p-1',1,?)",
        (json.dumps(good),))
    con.execute(
        "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
        "VALUES('i-1','ORDER_LIFECYCLE_COMPLETE',1,?)", (json.dumps(good),))
    con.execute(
        "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
        "VALUES('i-1','ORDER_LIFECYCLE_COMPLETE',2,?)", (json.dumps(good),))
    assert automation.operational_evidence(con)["testnet_lifecycles"] == 1

    forged = {"environment": "testnet", "qualified": True}
    con.execute(
        "INSERT INTO qualified_lifecycles VALUES('i-2','p-2',1,?)",
        (json.dumps(forged),))
    assert automation.operational_evidence(con)["testnet_lifecycles"] == 1


def test_ambiguous_target_submit_recovers_by_client_id_without_resubmit():
    con = sqlite3.connect(":memory:")
    submits = []
    accepted = broker_order("intent-1-tp1", "New")

    class LostResponse:
        def submit_target(self, **kwargs):
            submits.append(kwargs["client_order_id"])
            raise TimeoutError("response lost after venue acceptance")

        def order_status(self, symbol, client_order_id, broker_order_id=None):
            return accepted

    broker = LostResponse()
    with pytest.raises(TimeoutError):
        lifecycle.ensure_target(
            con, broker, position_id="intent-1", symbol="BTCUSDT",
            direction="LONG", quantity=Decimal("0.010"),
            target=Decimal("52000"))
    recovered = lifecycle.ensure_target(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.010"),
        target=Decimal("52000"))
    assert recovered.client_order_id == "intent-1-tp1"
    assert submits == ["intent-1-tp1"]


def test_partial_fill_resizes_one_target_identity_in_place():
    con = sqlite3.connect(":memory:")
    calls = []

    class TargetBroker:
        def submit_target(self, **kwargs):
            calls.append(("submit", kwargs["client_order_id"], kwargs["quantity"]))
            return broker_order(kwargs["client_order_id"], "New",
                                quantity=kwargs["quantity"])

        def order_status(self, symbol, client_order_id, broker_order_id=None):
            return broker_order(client_order_id, "New", quantity=Decimal("0.004"))

        def replace(self, symbol, client_order_id, **kwargs):
            calls.append(("replace", client_order_id, kwargs["quantity"]))
            return broker_order(client_order_id, "New", quantity=kwargs["quantity"])

    broker = TargetBroker()
    lifecycle.ensure_target(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.004"), target=Decimal("52000"))
    lifecycle.ensure_target(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.010"), target=Decimal("52000"))
    assert calls == [
        ("submit", "intent-1-tp1", Decimal("0.004")),
        ("replace", "intent-1-tp1", Decimal("0.010"))]
    assert con.execute(
        "SELECT client_order_id,quantity FROM lifecycle_orders").fetchone() == (
            "intent-1-tp1", "0.010")


def test_late_fill_never_replaces_a_target_that_already_filled():
    con = sqlite3.connect(":memory:")
    state = {"status": "New", "replaces": 0}

    class TargetBroker:
        def submit_target(self, **kwargs):
            return broker_order(kwargs["client_order_id"], "New",
                                quantity=kwargs["quantity"])

        def order_status(self, symbol, client_order_id, broker_order_id=None):
            return broker_order(client_order_id, state["status"],
                                quantity=Decimal("0.004"),
                                filled=Decimal("0.004") if state["status"] == "Filled"
                                else Decimal("0"))

        def replace(self, *args, **kwargs):
            state["replaces"] += 1
            raise AssertionError("terminal target was replaced")

    broker = TargetBroker()
    lifecycle.ensure_target(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.004"), target=Decimal("52000"))
    state["status"] = "Filled"
    with pytest.raises(lifecycle.LifecycleBlocked, match="late fill"):
        lifecycle.ensure_target(
            con, broker, position_id="intent-1", symbol="BTCUSDT",
            direction="LONG", quantity=Decimal("0.010"), target=Decimal("52000"))
    assert state["replaces"] == 0


def test_later_partial_fill_gets_a_new_emergency_generation():
    con = sqlite3.connect(":memory:")
    submitted = []

    class EmergencyBroker:
        def emergency_close(self, **kwargs):
            submitted.append((kwargs["client_order_id"], kwargs["quantity"]))
            return broker_order(kwargs["client_order_id"], "Filled",
                                quantity=kwargs["quantity"],
                                filled=kwargs["quantity"])

        def order_status(self, symbol, client_order_id, broker_order_id=None):
            quantity = next(qty for client, qty in submitted
                            if client == client_order_id)
            return broker_order(client_order_id, "Filled", quantity=quantity,
                                filled=quantity)

    broker = EmergencyBroker()
    lifecycle.ensure_emergency(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.004"))
    lifecycle.ensure_emergency(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.010"))
    assert [quantity for _, quantity in submitted] == [
        Decimal("0.004"), Decimal("0.006")]
    assert submitted[0][0] != submitted[1][0]


@pytest.mark.parametrize("terminal,filled,expected", [
    ("Rejected", Decimal("0"), Decimal("0.004")),
    ("Canceled", Decimal("0"), Decimal("0.004")),
    ("Canceled", Decimal("0.002"), Decimal("0.002")),
])
def test_same_cumulative_emergency_retries_only_terminal_remainder(
        terminal, filled, expected):
    con = sqlite3.connect(":memory:")
    submitted = []
    statuses = {}

    class EmergencyBroker:
        def emergency_close(self, **kwargs):
            client = kwargs["client_order_id"]
            submitted.append((client, kwargs["quantity"]))
            status, done = statuses.get(client, (terminal, filled))
            statuses[client] = (status, done)
            return broker_order(client, status, quantity=kwargs["quantity"],
                                filled=done)

        def order_status(self, symbol, client_order_id, broker_order_id=None):
            status, done = statuses[client_order_id]
            quantity = next(qty for client, qty in submitted
                            if client == client_order_id)
            return broker_order(client_order_id, status, quantity=quantity,
                                filled=done)

    broker = EmergencyBroker()
    lifecycle.ensure_emergency(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.004"))
    # The first terminal attempt is durable; the retry uses a new deterministic
    # attempt identity and only the quantity the venue did not confirm filled.
    lifecycle.ensure_emergency(
        con, broker, position_id="intent-1", symbol="BTCUSDT",
        direction="LONG", quantity=Decimal("0.004"))
    assert submitted[1][1] == expected
    assert submitted[0][0] != submitted[1][0]


def test_mixed_exit_roles_halt_and_never_qualify():
    con, broker = prepared()
    original = broker.executions
    def conflicting(*args, **kwargs):
        venue = original(*args, **kwargs)
        return venue + [BrokerExecution(
            "stop-too", "venue-intent-1-sl", "intent-1-sl", "BTCUSDT", "Sell",
            Decimal("0.001"), Decimal("49000"), Decimal("0.01"), "USDT",
            venue[-1].occurred_at + 1)]
    broker.executions = conflicting
    result = lifecycle.monitor(con, broker)
    assert result["blocked"][0]["reason"] == "conflicting exit roles executed"
    assert automation.operational_evidence(con)["testnet_lifecycles"] == 0


def test_matching_client_with_wrong_broker_order_id_never_qualifies():
    con, broker = prepared()
    original = broker.executions
    def mismatched(*args, **kwargs):
        venue = original(*args, **kwargs)
        wrong = BrokerExecution(
            venue[-1].execution_id, "different-venue-order",
            venue[-1].client_order_id, venue[-1].symbol, venue[-1].side,
            venue[-1].quantity, venue[-1].price, venue[-1].fee,
            venue[-1].fee_currency, venue[-1].occurred_at)
        return venue[:-1] + [wrong]
    broker.executions = mismatched
    result = lifecycle.monitor(con, broker)
    assert result["blocked"][0]["reason"] == \
        "execution broker order identity disagrees"
    assert automation.operational_evidence(con)["testnet_lifecycles"] == 0


def test_testnet_reconciliation_rate_ignores_mainnet_results():
    con = sqlite3.connect(":memory:")
    execution._ensure(con)
    for matched, environment in ((True, "testnet"), (False, "mainnet")):
        con.execute(
            "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
            "VALUES('RECONCILIATION','RECONCILIATION',1,?)",
            (json.dumps({"matched": matched, "environment": environment}),))
    assert automation.operational_evidence(con)["reconciliation_rate"] == 1
