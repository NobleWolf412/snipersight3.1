"""The six audited holes in the private path, pinned shut.

Every broker here is a fake; nothing touches a network or the live store.
Where a test opens the dispatch gate (operational=shadow_ready()), the thing
the gate protects — the venue — is a fake injected in the same test, per the
house rule about tests that force guards open.
"""
import sqlite3
import time
import unittest
from decimal import Decimal

from engine import automation, execution, opportunities, phemex_private
from engine.contracts import (AutomationMode, BrokerOrder, DecisionReason,
                              ExecutionPlan, OrderIntent, OrderKind,
                              RiskDecision)

PRODUCT = [{"symbol": "BTCUSDT", "tick_size": "0.1", "qty_step": "0.001",
            "min_notional": "1", "max_order_qty": "1000",
            "max_leverage": "10"}]


def memory():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT,"
                "updated_at INTEGER)")
    return con


def shadow_ready():
    return {"shadow_days": 14, "shadow_intents": 100,
            "shadow_paired_results": 100,
            "shadow_pair_integrity_failures": 0}


def make_plan(*, kind=OrderKind.LIMIT, expires_at=None, implied=Decimal("0.05"),
              stop=Decimal("49000.1"), targets=(Decimal("52000.1"),),
              intent_id="intent-1", key="a" * 64):
    intent = OrderIntent(
        intent_id, "setup-1", AutomationMode.TESTNET, "BTCUSDT", "LONG",
        kind, Decimal("0.010"),
        Decimal("50000.1") if kind == OrderKind.LIMIT else None,
        stop, targets, False, 1, "pullback-v1", key,
        expires_at=expires_at)
    risk = RiskDecision(True, "APPROVED", Decimal("10"), Decimal("0.010"),
                        Decimal("500.001"), implied,
                        (DecisionReason("OK", "within limits"),))
    return ExecutionPlan(intent, risk, "phemex-perp", "ISOLATED", "ONE_WAY")


def enter_testnet(con):
    automation.transition(
        con, "TESTNET", expected_revision=0,
        acknowledgement=automation.ACKNOWLEDGEMENTS[AutomationMode.TESTNET],
        operational=shadow_ready())


def broker_with(transport):
    return phemex_private.PhemexBroker(
        "key", "secret", transport=transport, products=PRODUCT)


# ---------------------------------------------------------------- phase 1


class StopAndLeverageValidation(unittest.TestCase):
    def test_off_tick_stop_is_rejected_for_every_order_kind(self):
        """submit sends stopLossRp on EVERY order; an off-tick stop that
        survives validation is discovered by the protection path after a
        real fill, as a halt plus emergency close."""
        broker = broker_with(lambda *a: {})
        for kind in (OrderKind.LIMIT, OrderKind.MARKET):
            with self.subTest(kind=kind.value):
                bad = make_plan(kind=kind, stop=Decimal("49000.157"))
                with self.assertRaisesRegex(phemex_private.PhemexError,
                                            "stop price"):
                    broker.validate_plan(bad)

    def test_off_tick_target_is_rejected_before_any_order_exists(self):
        broker = broker_with(lambda *a: {})
        bad = make_plan(targets=(Decimal("52000.13"),))
        with self.assertRaisesRegex(phemex_private.PhemexError, "target price"):
            broker.validate_plan(bad)

    def test_submit_sets_the_leverage_the_plan_implies_never_a_hardcoded_bucket(self):
        """Sized against the venue contract (up to 10x), dispatched at
        ceil(implied). Denomination caveat: implied leverage is computed on
        paper equity, so true margin sufficiency is only proven at the venue
        — this pins that we ASK for the right bucket, not that it suffices."""
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url, body))
            return {"code": 0, "data": {"orderID": "o-1",
                    "clOrdID": "ss-" + "a" * 37, "symbol": "BTCUSDT",
                    "orderType": "Limit", "ordStatus": "New",
                    "orderQtyRq": "0.010", "cumQtyRq": "0"}}

        broker = broker_with(transport)
        broker.submit(make_plan(implied=Decimal("1.25")))
        lev_call = next(url for m, url, _ in calls if "/g-positions/leverage?" in url)
        self.assertIn("leverageRr=2", lev_call,
                      "1.25x implied must ceil to a 2x bucket, not clamp to 1x")

    def test_low_implied_leverage_still_gets_the_1x_floor(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append(url)
            return {"code": 0, "data": {"orderID": "o-1",
                    "clOrdID": "ss-" + "a" * 37, "symbol": "BTCUSDT",
                    "orderType": "Limit", "ordStatus": "New",
                    "orderQtyRq": "0.010", "cumQtyRq": "0"}}

        broker = broker_with(transport)
        broker.submit(make_plan(implied=Decimal("0.05")))
        lev_call = next(url for url in calls if "/g-positions/leverage?" in url)
        self.assertIn("leverageRr=1", lev_call)

    def test_validate_plan_rejects_implied_leverage_beyond_instrument_maximum(self):
        broker = broker_with(lambda *a: {})
        bad = make_plan(implied=Decimal("12"))
        with self.assertRaisesRegex(phemex_private.PhemexError,
                                    "instrument maximum"):
            broker.validate_plan(bad)

    def test_stop_must_survive_liquidation_at_the_ceiled_bucket_not_at_implied(self):
        """submit() ceils implied leverage to a whole bucket, and a higher
        bucket pulls liquidation closer than the risk gate checked. Implied
        9.2x with a ~10% stop passes at 9.2x (liq ~10.4% away) and liquidates
        first at the 10x bucket (liq ~9.5% away). Latent at today's 0.125
        dispatch scale; enforced rather than assumed."""
        broker = broker_with(lambda *a: {})
        bad = make_plan(implied=Decimal("9.2"), stop=Decimal("45000.1"))
        with self.assertRaisesRegex(phemex_private.PhemexError,
                                    "does not survive liquidation"):
            broker.validate_plan(bad)

    def test_a_recovery_failure_after_an_ambiguous_post_stays_ambiguous(self):
        """The POST times out (the order may exist at the venue); the
        open-book recovery GET then gets rate-limited. Before the audit fix
        that surfaced as plain PhemexError, which dispatch classified as
        'proven pre-wire' — and retried an order that may be live."""
        def transport(method, url, headers, body):
            if method == "POST":
                raise phemex_private.AmbiguousSubmission("POST timed out")
            if method == "GET":                  # the open-book recovery
                raise phemex_private.PhemexError(
                    "Phemex returned HTTP 400: rejected")
            return {"code": 0, "data": {}}       # one-way + leverage PUTs

        broker = broker_with(transport)
        with self.assertRaises(phemex_private.AmbiguousSubmission):
            broker.submit(make_plan())

    def test_a_non_object_200_response_on_the_order_post_is_ambiguous(self):
        """A successful HTTP round trip with an unreadable body is a request
        the venue PROCESSED — 'no order can exist' cannot be claimed."""
        def transport(method, url, headers, body):
            if method == "POST" and "/g-orders" in url:
                return "gateway returned html"          # non-dict after 200
            return {"code": 0, "data": {}}

        broker = broker_with(transport)
        with self.assertRaises(phemex_private.AmbiguousSubmission):
            broker.submit(make_plan())


# ---------------------------------------------------------------- phase 2


class _FakeCancelBroker:
    """order_status returns a resting order; cancel returns it cancelled."""
    environment = "testnet"

    def __init__(self, *, cancel_error=None, filled=Decimal("0")):
        self.cancelled = []
        self.cancel_error = cancel_error
        self.filled = filled

    def order_status(self, symbol, client_order_id, broker_order_id=None):
        return BrokerOrder(
            "b-1", "c-1", symbol, "New", OrderKind.LIMIT,
            Decimal("0.010"), self.filled, Decimal("50000.1"), False,
            int(time.time()),
            average_fill_price=(Decimal("50000.1") if self.filled else None),
            cumulative_fee=Decimal("0"))

    def cancel(self, symbol, client_order_id):
        if self.cancel_error is not None:
            raise self.cancel_error
        self.cancelled.append(client_order_id)
        return BrokerOrder(
            "b-1", client_order_id, symbol, "Canceled", OrderKind.LIMIT,
            Decimal("0.010"), self.filled, Decimal("50000.1"), False,
            int(time.time()))

    def confirm_attached_protection(self, **kwargs):
        return BrokerOrder(
            None, kwargs["client_order_id"], kwargs["symbol"], "OPEN",
            OrderKind.MARKET, kwargs["quantity"], kwargs["quantity"],
            kwargs["stop"], True, int(time.time()))

    def submit_protective_stop(self, **kwargs):
        return BrokerOrder(
            "stop-1", kwargs["client_order_id"], kwargs["symbol"], "OPEN",
            OrderKind.MARKET, kwargs["quantity"], Decimal("0"),
            kwargs["stop"], True, int(time.time()))


def _submitted_private_intent(con, *, expires_at):
    p = make_plan(expires_at=expires_at)
    execution.enqueue(con, p.intent, plan=p)
    execution._event(con, p.intent.intent_id, "SUBMITTED", {
        "broker_order_id": "b-1", "client_order_id": "c-1"})
    return p


class ExpiryCancelsTheVenueOrder(unittest.TestCase):
    def test_private_resting_entry_is_cancelled_at_expiry(self):
        con = memory()
        _submitted_private_intent(con, expires_at=int(time.time()) - 60)
        broker = _FakeCancelBroker()
        result = execution.monitor_private(con, broker)
        self.assertEqual(broker.cancelled, ["c-1"],
                         "the venue order must be cancelled, not just the card")
        self.assertEqual(result["updated"][0]["state"], "ENTRY_CANCELED")

    def test_an_unexpired_entry_is_left_resting(self):
        con = memory()
        _submitted_private_intent(con, expires_at=int(time.time()) + 3600)
        broker = _FakeCancelBroker()
        execution.monitor_private(con, broker)
        self.assertEqual(broker.cancelled, [])

    def test_partial_fill_past_expiry_cancels_the_remainder_and_keeps_custody(self):
        con = memory()
        from engine import positions
        positions._ensure(con)
        _submitted_private_intent(con, expires_at=int(time.time()) - 60)
        broker = _FakeCancelBroker(filled=Decimal("0.004"))
        result = execution.monitor_private(con, broker)
        self.assertEqual(broker.cancelled, ["c-1"])
        # The filled 0.004 is a real position; the pre-existing custody rule
        # (PARTIALLY_FILLED until lifecycle qualifies the exit) is kept.
        self.assertEqual(result["updated"][0]["state"], "PARTIALLY_FILLED")
        custody = con.execute(
            "SELECT quantity FROM managed_positions").fetchone()
        self.assertEqual(custody[0], "0.004")

    def test_a_cancel_ack_that_omits_the_fill_does_not_erase_a_seen_partial(self):
        """If the venue's cancel ack drops cumQtyRq, the fill we already
        recorded must win — mapping this row to ENTRY_CANCELED would remove
        it from the monitor's scan set while custody holds the position."""
        con = memory()
        from engine import positions
        positions._ensure(con)
        _submitted_private_intent(con, expires_at=int(time.time()) - 60)
        broker = _FakeCancelBroker(filled=Decimal("0.004"))
        original_cancel = broker.cancel

        def forgetful_cancel(symbol, client_order_id):
            order = original_cancel(symbol, client_order_id)
            import dataclasses as _dc
            return _dc.replace(order, filled_quantity=Decimal("0"))

        broker.cancel = forgetful_cancel
        result = execution.monitor_private(con, broker)
        self.assertEqual(result["updated"][0]["state"], "PARTIALLY_FILLED")

    def test_expiry_cancel_failure_is_audible_not_silent(self):
        con = memory()
        _submitted_private_intent(con, expires_at=int(time.time()) - 60)
        broker = _FakeCancelBroker(
            cancel_error=phemex_private.PhemexError("HTTP 400: order filled"))
        with self.assertLogs("snipersight", level="WARNING") as logs:
            execution.monitor_private(con, broker)
        self.assertTrue(any("expiry cancel failed" in m for m in logs.output))
        audit = con.execute(
            "SELECT COUNT(*) FROM execution_events "
            "WHERE event='EXPIRY_CANCEL_FAILED'").fetchone()[0]
        self.assertEqual(audit, 1)


class PreWireRefusalIsRetryableAndLoud(unittest.TestCase):
    def _dispatch(self, con, broker, p):
        from engine import positions
        positions.reconcile(con, broker, symbols=["BTCUSDT"])
        return execution.Coordinator(broker).dispatch(
            con, p, operational=shadow_ready())

    class _RefusesPreWire:
        environment = "testnet"
        def client_order_id(self, _plan):
            return "ss-prewire"
        def submit(self, _plan):
            raise phemex_private.PhemexError(
                "stop price is not an exact instrument tick multiple")
        def sync_time(self):
            pass
        def open_orders(self, _symbol=None):
            return []
        def positions(self):
            return []

    def test_pre_wire_rejection_marks_submit_failed_and_permits_retry(self):
        con = memory()
        enter_testnet(con)
        broker = self._RefusesPreWire()
        with self.assertLogs("snipersight", level="WARNING"):
            out = self._dispatch(con, broker, make_plan())
        self.assertEqual(out["state"], "SUBMIT_FAILED")
        self.assertEqual(
            con.execute("SELECT state FROM execution_outbox").fetchone()[0],
            "SUBMIT_FAILED")

        class _NowAccepts(self._RefusesPreWire):
            def submit(self, _plan):
                return BrokerOrder(
                    "b-2", "ss-prewire", "BTCUSDT", "New", OrderKind.LIMIT,
                    Decimal("0.010"), Decimal("0"), Decimal("50000.1"),
                    False, 2)

        retry = self._dispatch(con, _NowAccepts(), make_plan())
        self.assertTrue(retry["submitted"],
                        "a proven pre-wire refusal must not jam the setup forever")

    def test_ambiguous_submission_still_stays_submitting_and_never_resubmits(self):
        con = memory()
        enter_testnet(con)

        class _Ambiguous(self._RefusesPreWire):
            def submit(self, _plan):
                raise phemex_private.AmbiguousSubmission("timeout mid-POST")

        with self.assertRaises(phemex_private.AmbiguousSubmission):
            self._dispatch(con, _Ambiguous(), make_plan())
        self.assertEqual(
            con.execute("SELECT state FROM execution_outbox").fetchone()[0],
            "SUBMITTING")

    def test_pre_wire_failure_never_awards_the_rejected_order_drill(self):
        con = memory()
        enter_testnet(con)
        execution._ensure(con)
        automation.start_safety_drill(
            con, "rejected_order",
            acknowledgement="RUN TESTNET SAFETY DRILL: rejected_order")
        with self.assertLogs("snipersight", level="WARNING"):
            self._dispatch(con, self._RefusesPreWire(), make_plan())
        self.assertEqual(automation.safety_drills(con)[0]["status"], "ACTIVE",
                         "a local refusal is not a venue rejection")


class RestartNeedsARestart(unittest.TestCase):
    def test_restart_recovery_in_the_same_process_is_not_a_restart(self):
        con = memory()
        enter_testnet(con)
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        p = make_plan()
        execution.enqueue(con, p.intent, plan=p)
        # SUBMITTING written by THIS process — boot ids will match.
        execution._event(con, p.intent.intent_id, "SUBMITTING", {
            "client_order_id": "c-1", "boot_id": execution.PROCESS_BOOT_ID})
        automation.start_safety_drill(
            con, "restart",
            acknowledgement="RUN TESTNET SAFETY DRILL: restart")
        execution.monitor_private(con, _FakeCancelBroker())
        self.assertEqual(automation.safety_drills(con)[0]["status"], "ACTIVE")

    def test_recovery_from_a_different_boot_passes_the_drill(self):
        con = memory()
        enter_testnet(con)
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        p = make_plan()
        execution.enqueue(con, p.intent, plan=p)
        execution._event(con, p.intent.intent_id, "SUBMITTING", {
            "client_order_id": "c-1", "boot_id": "a-previous-process"})
        automation.start_safety_drill(
            con, "restart",
            acknowledgement="RUN TESTNET SAFETY DRILL: restart")
        execution.monitor_private(con, _FakeCancelBroker())
        self.assertEqual(automation.safety_drills(con)[0]["status"], "PASSED")

    def test_legacy_submitting_rows_without_boot_marker_earn_no_pass(self):
        con = memory()
        enter_testnet(con)
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        p = make_plan()
        execution.enqueue(con, p.intent, plan=p)
        execution._event(con, p.intent.intent_id, "SUBMITTING", {
            "client_order_id": "c-1"})          # pre-v0.6 row: no boot_id
        automation.start_safety_drill(
            con, "restart",
            acknowledgement="RUN TESTNET SAFETY DRILL: restart")
        execution.monitor_private(con, _FakeCancelBroker())
        self.assertEqual(automation.safety_drills(con)[0]["status"], "ACTIVE",
                         "missing evidence fails closed")


# ---------------------------------------------------------------- phase 3


class EveryDrillNamesItsEvidence(unittest.TestCase):
    def _staged(self, con, drill):
        execution._ensure(con)
        automation.start_safety_drill(
            con, drill,
            acknowledgement=f"RUN TESTNET SAFETY DRILL: {drill}")

    def test_each_drill_rejects_an_observation_missing_its_evidence(self):
        cases = {
            "restart": ("RESTART_RECOVERED", {"intent_id": "i-1"}),
            "partial_fill": ("PARTIAL_FILL_PROTECTED",
                             {"intent_id": "i-1", "filled_quantity": "0"}),
            "protective_stop": ("PROTECTIVE_STOP_CONFIRMED",
                                {"position_id": "p-1"}),
            "kill_switch": ("KILL_SWITCH_BLOCKED", {"intent_id": "i-1"}),
            "rejected_order": ("ORDER_REJECTED", {}),
            "stale_data": ("STALE_RECONCILIATION_BLOCKED",
                           {"environment": "testnet"}),
        }
        for drill, (event, thin_evidence) in cases.items():
            with self.subTest(drill=drill):
                con = memory()
                enter_testnet(con)
                self._staged(con, drill)
                self.assertFalse(
                    automation.observe_safety_event(con, event, thin_evidence),
                    f"{drill} passed on evidence that proves nothing")

    def test_complete_evidence_still_passes(self):
        con = memory()
        enter_testnet(con)
        self._staged(con, "partial_fill")
        self.assertTrue(automation.observe_safety_event(
            con, "PARTIAL_FILL_PROTECTED",
            {"intent_id": "i-1", "filled_quantity": "0.004"}))


# ---------------------------------------------------------------- phase 5


class CustodyOverridesTheSimulatorsStory(unittest.TestCase):
    def _store_with_ready_setup(self):
        import tempfile
        from pathlib import Path
        from engine import setups, store
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        con = store.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(con.close)
        now = int(time.time())
        store.insert_fact(
            con, symbol="BTCUSDT", tf="1H", kind="setup",
            market_time=now, confirmed_at=now + 3600,
            algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "s-1", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "50000", "sl": "49000",
                     "tp": "52000", "rr": "2", "rank": 50,
                     "state": "VALIDATED"})
        return con

    def test_real_custody_overrides_the_paper_lifecycle_state(self):
        con = self._store_with_ready_setup()
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,"
            "setup_id,symbol,payload,state,created_at,updated_at) "
            "VALUES('k','i-1','TESTNET','s-1','BTCUSDT','{}','SUBMITTED',1,1)")
        con.execute(
            "INSERT INTO managed_positions(position_id,intent_id,symbol,"
            "direction,quantity,entry,stop,owner,protection_client_id,"
            "protection_status,state,updated_at) VALUES('i-1','i-1','BTCUSDT',"
            "'LONG','0.004','50000','49000','bot',NULL,'CONFIRMED','OPEN',2)")
        con.commit()
        rows = opportunities.list_candidates(con, include_history=False)
        states = {r["setup"]["setup_id"]: r["state"] for r in rows}
        self.assertEqual(states.get("s-1"), "POSITION_OPEN")

    def test_operations_summary_reports_an_open_private_position(self):
        con = self._store_with_ready_setup()
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,"
            "setup_id,symbol,payload,state,created_at,updated_at) "
            "VALUES('k','i-1','TESTNET','s-1','BTCUSDT','{}','SUBMITTED',1,1)")
        con.execute(
            "INSERT INTO managed_positions(position_id,intent_id,symbol,"
            "direction,quantity,entry,stop,owner,protection_client_id,"
            "protection_status,state,updated_at) VALUES('i-1','i-1','BTCUSDT',"
            "'LONG','0.004','50000','49000','bot',NULL,'CONFIRMED','OPEN',2)")
        con.commit()
        summary = opportunities.summary(
            opportunities.list_candidates(con, include_history=False))
        self.assertIn("Managing 1 open position", summary["narrative"],
                      "the operator must never read 'scanning continues' "
                      "over an open real position")

    def test_an_old_closed_lifecycle_does_not_mask_a_revalidated_setup(self):
        """setup_id embeds zone and version, so a persistent zone retested
        weeks later re-validates under the SAME id. A completed lifecycle
        from the previous validation must not stamp the fresh candidate
        CLOSED — that would hide a valid, tradeable setup forever."""
        con = self._store_with_ready_setup()      # confirmed_at = now + 3600
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,"
            "setup_id,symbol,payload,state,created_at,updated_at) "
            "VALUES('k','i-1','TESTNET','s-1','BTCUSDT','{}',"
            "'LIFECYCLE_COMPLETE',1,1)")          # updated_at=1: long ago
        con.commit()
        rows = opportunities.list_candidates(con, include_history=False)
        states = {r["setup"]["setup_id"]: r["state"] for r in rows}
        self.assertIn("s-1", states, "the fresh validation must be visible")
        self.assertNotEqual(states["s-1"], "CLOSED")

    def test_a_current_open_position_overlays_regardless_of_timestamps(self):
        """An open real position is a present-tense fact; it overlays even a
        setup fact confirmed after the position opened."""
        con = self._store_with_ready_setup()
        execution._ensure(con)
        from engine import positions
        positions._ensure(con)
        con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,"
            "setup_id,symbol,payload,state,created_at,updated_at) "
            "VALUES('k','i-1','TESTNET','s-1','BTCUSDT','{}','SUBMITTED',1,1)")
        con.execute(
            "INSERT INTO managed_positions(position_id,intent_id,symbol,"
            "direction,quantity,entry,stop,owner,protection_client_id,"
            "protection_status,state,updated_at) VALUES('i-1','i-1','BTCUSDT',"
            "'LONG','0.004','50000','49000','bot',NULL,'CONFIRMED','OPEN',1)")
        con.commit()
        rows = opportunities.list_candidates(con, include_history=False)
        states = {r["setup"]["setup_id"]: r["state"] for r in rows}
        self.assertEqual(states.get("s-1"), "POSITION_OPEN")

    def test_paper_read_model_is_unchanged_when_no_private_custody_exists(self):
        con = self._store_with_ready_setup()
        rows = opportunities.list_candidates(con, include_history=False)
        self.assertEqual(len(rows), 1)
        self.assertNotIn(rows[0]["state"],
                         ("POSITION_OPEN", "ORDER_WORKING", "CLOSED"))


if __name__ == "__main__":
    unittest.main()
