import sqlite3
from decimal import Decimal

import pytest

from engine import automation, execution
from engine.contracts import (AutomationMode, BrokerOrder, DecisionReason,
                              ExecutionPlan, OrderIntent, OrderKind, RiskDecision)


def memory():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT,updated_at INTEGER)")
    return con


def live_gate(ready=False):
    return {"ready": ready, "criteria": [
        {"key": key, "pass": ready} for key in
        ("sample", "edge", "drawdown", "quality")]}


def shadow_ready():
    return {"shadow_days": 14, "shadow_intents": 100,
            "shadow_paired_results": 100,
            "shadow_pair_integrity_failures": 0}


def intent(mode, intent_id="i-1"):
    return OrderIntent(
        intent_id=intent_id, setup_id="setup-1", mode=mode, symbol="BTCUSDT",
        direction="LONG", order_kind=OrderKind.LIMIT,
        quantity=Decimal("0.01"), entry=Decimal("50000"),
        stop=Decimal("49000"), targets=(Decimal("52000"),),
        reduce_only=False, created_at=1, playbook_version="p1",
        idempotency_key="same-key")


def plan(mode):
    risk = RiskDecision(True, "APPROVED", Decimal("25"), Decimal("0.01"),
                        Decimal("500"), Decimal("0.05"),
                        (DecisionReason("OK", "within limits"),))
    return ExecutionPlan(intent(mode), risk, "phemex-perp", "ISOLATED", "ONE_WAY")


def test_mode_transition_is_optimistically_locked_and_audited():
    con = memory()
    out = automation.transition(con, "OFF", expected_revision=0)
    assert out.mode == AutomationMode.OFF
    assert out.revision == 1
    with pytest.raises(automation.ModeConflict):
        automation.transition(con, "PAPER", expected_revision=0)
    assert automation.history(con)[0]["to"] == "OFF"


def test_testnet_requires_shadow_gate_and_exact_acknowledgement():
    con = memory()
    with pytest.raises(automation.ModeRejected):
        automation.transition(con, "TESTNET", expected_revision=0,
                              acknowledgement=automation.ACKNOWLEDGEMENTS[
                                  AutomationMode.TESTNET])
    with pytest.raises(automation.ModeRejected):
        automation.transition(con, "TESTNET", expected_revision=0,
                              acknowledgement="yes", operational=shadow_ready())
    out = automation.transition(
        con, "TESTNET", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.TESTNET],
        operational=shadow_ready())
    assert out.mode == AutomationMode.TESTNET


def test_live_stays_build_locked_even_when_evidence_is_ready():
    con = memory()
    op = {**shadow_ready(), "testnet_days": 30, "testnet_lifecycles": 100,
          "duplicate_orders": 0, "orphan_positions": 0,
          "reconciliation_rate": 0.999, "safety_drills_passed": True}
    with pytest.raises(automation.ModeRejected, match="build"):
        automation.transition(
            con, "LIVE", expected_revision=0,
            acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.LIVE],
            live_gate=live_gate(True), operational=op)


def test_safety_drill_requires_testnet_ack_and_real_matching_observation():
    con = memory()
    execution._ensure(con)
    automation.transition(
        con, "TESTNET", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.TESTNET],
        operational=shadow_ready())
    with pytest.raises(automation.ModeRejected, match="exact acknowledgement"):
        automation.start_safety_drill(con, "disconnect", acknowledgement="yes")
    run = automation.start_safety_drill(
        con, "disconnect",
        acknowledgement="RUN TESTNET SAFETY DRILL: disconnect")
    assert automation.observe_safety_event(
        con, "RESTART_RECOVERED", {"wrong": "drill"}) is False
    assert automation.safety_drills(con)[0]["status"] == "ACTIVE"
    assert automation.observe_safety_event(
        con, "DISCONNECT_RECOVERED", {"intent_id": "i-1"}) is False
    assert automation.observe_safety_event(
        con, "DISCONNECT_OBSERVED", {
            "intent_id": "i-1", "client_order_id": "c-1",
            "error_type": "AttributeError", "transport_failure": False}) is False
    assert automation.safety_drills(con)[0]["evidence"] == {}
    assert automation.observe_safety_event(
        con, "DISCONNECT_OBSERVED", {
            "intent_id": "i-1", "client_order_id": "c-1",
            "error_type": "TimeoutError", "transport_failure": True}) is False
    assert automation.observe_safety_event(
        con, "DISCONNECT_RECOVERED", {
            "intent_id": "different", "client_order_id": "c-1"}) is False
    assert automation.observe_safety_event(
        con, "DISCONNECT_RECOVERED", {
            "intent_id": "i-1", "client_order_id": "c-1"}) is True
    assert automation.safety_drills(con)[0]["status"] == "PASSED"
    assert con.execute(
        "SELECT COUNT(*) FROM execution_events WHERE event='SAFETY_DRILL'").fetchone()[0] == 1


def test_shadow_never_calls_private_broker_and_outbox_is_idempotent():
    con = memory()
    automation.transition(
        con, "SHADOW", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.SHADOW])

    class MustNotRun:
        environment = "mainnet"
        def submit(self, _):
            raise AssertionError("shadow reached private order submission")

    coordinator = execution.Coordinator(MustNotRun())
    first = coordinator.dispatch(con, plan(AutomationMode.SHADOW))
    second = coordinator.dispatch(con, plan(AutomationMode.SHADOW))
    assert first["submitted"] is False
    assert second["queue"]["intent_id"] == "i-1"
    assert second["idempotent_replay"] is True
    assert con.execute("SELECT COUNT(*) FROM execution_outbox").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0] == 3
    assert con.execute(
        "SELECT COUNT(*) FROM execution_events WHERE event='SHADOW_PAIRED_RESULT'"
    ).fetchone()[0] == 0
    assert con.execute(
        "SELECT COUNT(*) FROM execution_events WHERE event='SHADOW_PAIRED'"
    ).fetchone()[0] == 1
    stored = con.execute("SELECT payload FROM execution_outbox").fetchone()[0]
    assert '"margin_mode":"ISOLATED"' in stored
    assert '"risk"' in stored


def test_execution_core_refuses_unapproved_risk_decision():
    con = memory()
    rejected = plan(AutomationMode.PAPER)
    object.__setattr__(rejected.risk, "approved", False)
    result = execution.Coordinator().dispatch(con, rejected)
    assert result["state"] == "RISK_REJECTED"
    assert con.execute(
        "SELECT event FROM execution_events ORDER BY id DESC").fetchone()[0] == \
        "RISK_REJECTED"


def test_paper_intent_fills_and_closes_from_closed_candles():
    con = memory()
    con.execute("CREATE TABLE candles(symbol TEXT,tf TEXT,open_ts INTEGER,"
                "open TEXT,high TEXT,low TEXT,close TEXT,volume TEXT,source TEXT,"
                "imported_at INTEGER,PRIMARY KEY(symbol,tf,open_ts))")
    con.executemany(
        "INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)", [
            ("BTCUSDT", "5m", 10, "50100", "51000", "49900", "50500",
             "1", "test", 400),
            ("BTCUSDT", "5m", 310, "50500", "52100", "50400", "52000",
             "1", "test", 700)])
    automation.transition(con, "PAPER", expected_revision=0)
    paper_plan = plan(AutomationMode.PAPER)
    object.__setattr__(paper_plan.intent, "timeframe", "5m")
    execution.Coordinator().dispatch(con, paper_plan)
    result = execution.monitor_paper(con)
    assert result["updated"][-1]["state"] == "PAPER_CLOSED"
    assert result["updated"][-1]["outcome"] == "TP"
    row = execution.paper_positions(con, include_closed=True)[0]
    assert row["entry"] == "50000"
    assert row["exit_price"] == "52000"
    assert row["r_multiple"] == "1.99"
    assert row["fees_price_units"] == "10.2000"
    assert row["cost_profile_version"] == "phemex-perp-v1"
    events = [r[0] for r in con.execute(
        "SELECT event FROM execution_events WHERE intent_id='i-1' ORDER BY id")]
    assert events == ["PAPER_ROUTED", "PAPER_FILLED", "PAPER_CLOSED",
                      "ORDER_LIFECYCLE_COMPLETE"]


def test_paper_entry_uses_shared_maker_then_market_fill_authority():
    con = memory()
    con.execute("CREATE TABLE candles(symbol TEXT,tf TEXT,open_ts INTEGER,"
                "open TEXT,high TEXT,low TEXT,close TEXT,volume TEXT,source TEXT,"
                "imported_at INTEGER,PRIMARY KEY(symbol,tf,open_ts))")
    con.executemany(
        "INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)", [
            ("BTCUSDT", "5m", 10, "50100", "51000", "50050", "50500",
             "1", "test", 400),
            ("BTCUSDT", "5m", 310, "51000", "51500", "50500", "51200",
             "1", "test", 700)])
    automation.transition(con, "PAPER", expected_revision=0)
    paper_plan = plan(AutomationMode.PAPER)
    object.__setattr__(paper_plan.intent, "timeframe", "5m")
    object.__setattr__(paper_plan.intent, "entry_model", "MAKER_THEN_MARKET")
    object.__setattr__(paper_plan.intent, "maker_wait_bars", 1)
    execution.Coordinator().dispatch(con, paper_plan)

    execution.monitor_paper(con)

    row = execution.paper_positions(con, include_closed=True)[0]
    assert row["entry"] == "51000"
    assert row["entry_role"] == "TAKER"
    fill = con.execute(
        "SELECT payload FROM execution_events WHERE event='PAPER_FILLED'"
    ).fetchone()[0]
    assert '"entry_model": "MAKER_THEN_MARKET"' in fill
    assert '"entry_role": "TAKER"' in fill


def test_shadow_comparison_is_earned_only_after_paired_paper_result():
    con = memory()
    con.execute("CREATE TABLE candles(symbol TEXT,tf TEXT,open_ts INTEGER,"
                "open TEXT,high TEXT,low TEXT,close TEXT,volume TEXT,source TEXT,"
                "imported_at INTEGER,PRIMARY KEY(symbol,tf,open_ts))")
    con.executemany(
        "INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)", [
            ("BTCUSDT", "5m", 10, "50100", "51000", "49900", "50500",
             "1", "test", 400),
            ("BTCUSDT", "5m", 310, "50500", "52100", "50400", "52000",
             "1", "test", 700)])
    automation.transition(
        con, "SHADOW", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.SHADOW])
    shadow_plan = plan(AutomationMode.SHADOW)
    object.__setattr__(shadow_plan.intent, "timeframe", "5m")
    execution.Coordinator().dispatch(con, shadow_plan)
    assert con.execute(
        "SELECT COUNT(*) FROM execution_events WHERE event='SHADOW_PAIRED_RESULT'"
    ).fetchone()[0] == 0

    execution.monitor_paper(con)

    comparison = con.execute(
        "SELECT payload FROM execution_events WHERE intent_id='i-1' "
        "AND event='SHADOW_PAIRED_RESULT'"
    ).fetchone()
    assert comparison is not None
    assert '"state": "PAPER_CLOSED"' in comparison[0]
    assert automation.operational_evidence(con)["shadow_paired_results"] == 1


def test_shadow_pair_mismatch_records_integrity_failure_not_result():
    con = memory()
    con.execute("CREATE TABLE candles(symbol TEXT,tf TEXT,open_ts INTEGER,"
                "open TEXT,high TEXT,low TEXT,close TEXT,volume TEXT,source TEXT,"
                "imported_at INTEGER,PRIMARY KEY(symbol,tf,open_ts))")
    con.executemany(
        "INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)", [
            ("BTCUSDT", "5m", 10, "50100", "51000", "49900", "50500",
             "1", "test", 400),
            ("BTCUSDT", "5m", 310, "50500", "52100", "50400", "52000",
             "1", "test", 700)])
    automation.transition(
        con, "SHADOW", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.SHADOW])
    shadow_plan = plan(AutomationMode.SHADOW)
    object.__setattr__(shadow_plan.intent, "timeframe", "5m")
    execution.Coordinator().dispatch(con, shadow_plan)
    paper_id, raw = con.execute(
        "SELECT intent_id,payload FROM execution_outbox WHERE mode='PAPER'"
    ).fetchone()
    import json
    payload = json.loads(raw)
    payload["risk"]["decision"] = "DIFFERENT_PAPER_DECISION"
    con.execute("UPDATE execution_outbox SET payload=? WHERE intent_id=?",
                (json.dumps(payload, sort_keys=True), paper_id))

    execution.monitor_paper(con)

    assert con.execute(
        "SELECT COUNT(*) FROM execution_events WHERE event='SHADOW_PAIRED_RESULT'"
    ).fetchone()[0] == 0
    divergence = con.execute(
        "SELECT payload FROM execution_events "
        "WHERE event='SHADOW_PAIR_INTEGRITY_FAILURE'"
    ).fetchone()
    assert divergence is not None
    assert '"matched": false' in divergence[0]
    assert automation.operational_evidence(con)[
        "shadow_pair_integrity_failures"] == 1


def test_private_monitor_turns_partial_fill_into_exact_protected_custody():
    con = memory()
    private_plan = plan(AutomationMode.TESTNET)
    execution.enqueue(con, private_plan.intent, plan=private_plan)
    execution._event(con, private_plan.intent.intent_id, "SUBMITTED", {
        "broker_order_id": "b-1", "client_order_id": "c-1"})

    class Broker:
        environment = "testnet"

        def order_status(self, symbol, client_order_id, broker_order_id):
            return BrokerOrder(
                "b-1", "c-1", symbol, "PartiallyFilled", OrderKind.LIMIT,
                Decimal("0.01"), Decimal("0.004"), Decimal("50000"), False, 10,
                average_fill_price=Decimal("50000.2"),
                cumulative_fee=Decimal("0.12"))

        def confirm_attached_protection(self, **kwargs):
            return BrokerOrder(
                None, kwargs["client_order_id"], kwargs["symbol"], "OPEN",
                OrderKind.MARKET, kwargs["quantity"], kwargs["quantity"],
                kwargs["stop"], True, 10)

        def submit_protective_stop(self, **kwargs):
            return BrokerOrder(
                "stop-1", kwargs["client_order_id"], kwargs["symbol"], "OPEN",
                OrderKind.MARKET, kwargs["quantity"], Decimal("0"),
                kwargs["stop"], True, 10)

    result = execution.monitor_private(con, Broker())
    assert result["updated"][0]["state"] == "PARTIALLY_FILLED"
    custody = con.execute(
        "SELECT quantity,protection_status FROM managed_positions").fetchone()
    assert custody == ("0.004", "CONFIRMED")
    fill_payload = con.execute(
        "SELECT payload FROM position_events WHERE event='FILL'").fetchone()[0]
    assert '"fee":"0.12"' in fill_payload


def test_operational_evidence_fails_closed_without_reconciliation_or_drills():
    con = memory()
    coordinator = execution.Coordinator()
    automation.transition(
        con, "SHADOW", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.SHADOW])
    coordinator.dispatch(con, plan(AutomationMode.SHADOW))
    evidence = automation.operational_evidence(con)
    assert evidence["shadow_intents"] == 1
    assert evidence["reconciliation_rate"] == 0
    assert evidence["safety_drills_passed"] is False
    assert automation.promotion_summary(operational=evidence)["shadow_ready"] is False


def test_accepted_submission_is_recovered_after_crash_without_resubmit():
    con = memory()
    automation.transition(
        con, "TESTNET", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.TESTNET],
        operational=shadow_ready())

    class AcceptedThenLost:
        environment = "testnet"
        submits = 0
        def client_order_id(self, _plan):
            return "ss-restart-safe"
        def submit(self, _plan):
            self.submits += 1
            raise RuntimeError("process lost response after venue acceptance")
        def sync_time(self):
            pass
        def open_orders(self, _symbol):
            return []
        def positions(self):
            return []

    first = AcceptedThenLost()
    from engine import positions
    positions.reconcile(con, first, symbols=["BTCUSDT"])
    with pytest.raises(RuntimeError):
        execution.Coordinator(first).dispatch(
            con, plan(AutomationMode.TESTNET), operational=shadow_ready())
    assert con.execute(
        "SELECT state FROM execution_outbox").fetchone()[0] == "SUBMITTING"

    recovered_order = BrokerOrder(
        "venue-1", "ss-restart-safe", "BTCUSDT", "Filled", OrderKind.LIMIT,
        Decimal("0.01"), Decimal("0.01"), Decimal("50000"), False, 2)

    class RecoverOnly(AcceptedThenLost):
        def submit(self, _plan):
            raise AssertionError("restart attempted a duplicate submission")
        def order_status(self, symbol, client_order_id, broker_order_id):
            assert client_order_id == "ss-restart-safe"
            return recovered_order

    result = execution.Coordinator(RecoverOnly()).dispatch(
        con, plan(AutomationMode.TESTNET), operational=shadow_ready())
    assert result["idempotent_replay"] is True
    assert result["order"]["broker_order_id"] == "venue-1"


def test_private_mode_cannot_be_downgraded_while_exposure_is_open():
    con = memory()
    automation.transition(
        con, "TESTNET", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.TESTNET],
        operational=shadow_ready())
    execution._ensure(con)
    con.execute("CREATE TABLE managed_positions(position_id TEXT PRIMARY KEY,"
                "intent_id TEXT,state TEXT)")
    con.execute("INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,"
                "symbol,payload,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                ("k", "private-1", "TESTNET", "s", "BTCUSDT", "{}", "SUBMITTED", 1, 1))
    con.execute("INSERT INTO managed_positions VALUES(?,?,?)",
                ("private-1", "private-1", "OPEN"))
    with pytest.raises(automation.ModeRejected, match="flat"):
        automation.transition(con, "OFF", expected_revision=1)
