"""/api/setup-trace — the per-setup "why didn't THIS one fire?" journey.

The funnel endpoints answer the aggregate question and are pinned to the
current algo_version. A trace is different: it is asked about one setup the
operator can already see on screen, so these tests pin down the two properties
that make it trustworthy — every gate carries the value it compared, and an id
that does not exist is a 404 rather than a confident-looking empty drawer.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import server
from engine import execsim, risk, setups, store


def _seed(con, *, setup_id, state="VALIDATED", risk_payload=None,
          order_payload=None, exec_payload=None, setup_version=None):
    """Write one setup's fact chain. Only the kinds passed are recorded, so a
    test can reproduce a setup that died partway down the pipeline."""
    store.insert_fact(
        con, symbol="BTC-USD", tf="1D", kind="setup", market_time=10,
        confirmed_at=20, algo_version=setup_version or setups.SETUP_VERSION,
        payload={"setup_id": setup_id, "state": state, "strategy": "PULLBACK",
                 "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                 "rr": "3", "rank": 65, "regime": "BULL_TREND",
                 "zone_id": "BTC-USD|1D|DEMAND|5",
                 "why": "pullback into demand in a bull trend"})
    if risk_payload is not None:
        store.insert_fact(con, symbol="BTC-USD", tf="1D", kind="risk",
                          market_time=10, confirmed_at=21,
                          algo_version=risk.RISK_VERSION,
                          payload={"event": "DECISION", "setup_id": setup_id,
                                   **risk_payload})
    if order_payload is not None:
        store.insert_fact(con, symbol="BTC-USD", tf="1D", kind="order",
                          market_time=10, confirmed_at=22,
                          algo_version=execsim.EXEC_VERSION,
                          payload={"setup_id": setup_id, **order_payload})
    if exec_payload is not None:
        store.insert_fact(con, symbol="BTC-USD", tf="1D", kind="exec",
                          market_time=10, confirmed_at=30,
                          algo_version=execsim.EXEC_VERSION,
                          payload={"setup_id": setup_id, **exec_payload})
    con.commit()


class _TraceCase(unittest.TestCase):
    def trace(self, setup_id, seed):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "trace.db"
            original_connect = store.connect
            con = original_connect(db)
            seed(con)
            con.close()
            with patch("server.store.connect",
                       side_effect=lambda: original_connect(db)):
                return server.setup_trace(setup_id)


class TestSetupTraceOrdering(_TraceCase):
    def test_known_id_returns_every_stage_in_pipeline_order(self):
        result = self.trace("trace-1", lambda con: _seed(
            con, setup_id="trace-1",
            risk_payload={"decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
                          "risk_usd": "200", "equity_at": "10000"},
            order_payload={"event": "FILLED", "order_type": "LIMIT",
                           "limit_price": "100", "fill_price": "100",
                           "bars_to_fill": 0, "available_at": 20},
            exec_payload={"outcome": "TP", "r_multiple": "2.5", "r_gross": "3",
                          "costs_r": "0.5", "bars_held": 4, "fill_ts": 22}))

        # Order is the contract: the drawer renders stages[] as given, so the
        # backend owns the sequence rather than the UI re-sorting it.
        self.assertEqual([s["key"] for s in result["stages"]],
                         ["CANDIDATE", "PLAYBOOK", "BRACKET", "RR_GATE",
                          "VALIDATION", "RISK", "ORDER", "FILL", "EXIT"])
        by_key = {s["key"]: s for s in result["stages"]}
        self.assertEqual(by_key["RISK"]["status"], "pass")
        self.assertEqual(by_key["EXIT"]["status"], "pass")
        self.assertEqual(result["lifecycle"]["failure_code"], "WINNER")

    def test_every_stage_carries_the_value_it_compared(self):
        """A tick alone says the gate ran, not what it decided on."""
        result = self.trace("trace-values", lambda con: _seed(
            con, setup_id="trace-values",
            risk_payload={"decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
                          "risk_usd": "200", "equity_at": "10000"}))
        by_key = {s["key"]: s for s in result["stages"]}
        # R:R is measured, not copied from the setup payload, and it is shown
        # against the threshold it was actually judged against.
        self.assertEqual(by_key["RR_GATE"]["value"], 2.0)
        self.assertEqual(by_key["RR_GATE"]["expected"],
                         f">= {float(setups.MIN_RR)}")
        self.assertEqual(by_key["RR_GATE"]["status"], "pass")
        self.assertEqual(by_key["PLAYBOOK"]["facts"]["regime"], "BULL_TREND")
        self.assertEqual(by_key["VALIDATION"]["value"], "VALIDATED")
        self.assertEqual(by_key["RISK"]["facts"]["equity_at"], "10000")
        self.assertEqual(result["thresholds"]["min_rr"], str(setups.MIN_RR))

    def test_stages_with_no_facts_are_skipped_not_failed(self):
        """No order fact means the pipeline stopped, not that the order failed.
        Rendering those as ✗ would blame execution for a risk decision."""
        result = self.trace("trace-stopped", lambda con: _seed(
            con, setup_id="trace-stopped",
            risk_payload={"decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
                          "risk_usd": "200"}))
        by_key = {s["key"]: s for s in result["stages"]}
        self.assertEqual(by_key["ORDER"]["status"], "skip")
        self.assertEqual(by_key["FILL"]["status"], "skip")
        self.assertEqual(by_key["EXIT"]["status"], "skip")
        self.assertEqual(result["lifecycle"]["failure_code"], "AWAITING_RISK")


class TestSetupTraceRiskRejection(_TraceCase):
    def test_risk_rejected_setup_surfaces_its_reasons(self):
        result = self.trace("trace-rejected", lambda con: _seed(
            con, setup_id="trace-rejected",
            risk_payload={"decision": "REJECTED", "risk_usd": "0",
                          "intended_risk_usd": "200", "equity_at": "10000",
                          "reasons": ["EXPOSURE_LIMIT",
                                      "NOT_IN_POINT_IN_TIME_UNIVERSE"]}))
        stage = {s["key"]: s for s in result["stages"]}["RISK"]
        self.assertEqual(stage["status"], "fail")
        self.assertEqual(stage["value"], "REJECTED")
        self.assertEqual(stage["facts"]["reasons"],
                         ["EXPOSURE_LIMIT", "NOT_IN_POINT_IN_TIME_UNIVERSE"])
        # the human-readable line the drawer prints under the stage
        self.assertIn("EXPOSURE_LIMIT", stage["detail"])
        self.assertIn("NOT_IN_POINT_IN_TIME_UNIVERSE", stage["detail"])
        # and the lifecycle verdict agrees with the funnel's attribution
        self.assertEqual(result["lifecycle"]["failure_code"], "RISK_REJECTED")
        self.assertEqual(result["lifecycle"]["failure_owner"], "PORTFOLIO")
        # the rule-level diagnostics are carried through so the drawer can
        # explain WHICH rule fired, not just that risk said no
        rules = {d["rule_id"] for d in result["diagnostics"]}
        self.assertIn("RISK.007", rules)          # EXPOSURE_LIMIT
        self.assertIn("RISK.002", rules)          # NOT_IN_POINT_IN_TIME_UNIVERSE

    def test_reduced_is_a_warning_not_a_failure(self):
        result = self.trace("trace-reduced", lambda con: _seed(
            con, setup_id="trace-reduced",
            risk_payload={"decision": "REDUCED", "reasons": ["EXPOSURE_LIMIT"],
                          "risk_usd": "90", "intended_risk_usd": "200"}))
        stage = {s["key"]: s for s in result["stages"]}["RISK"]
        self.assertEqual(stage["status"], "warn")
        self.assertEqual(stage["facts"]["risk_usd"], "90")


class TestSetupTraceUnknownId(_TraceCase):
    def test_unknown_id_is_a_404_not_an_empty_drawer(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "trace.db"
            original_connect = store.connect
            con = original_connect(db)
            _seed(con, setup_id="exists")
            con.close()
            with patch("server.store.connect",
                       side_effect=lambda: original_connect(db)):
                with self.assertRaises(HTTPException) as caught:
                    server.setup_trace("does-not-exist")
        self.assertEqual(caught.exception.status_code, 404)
        self.assertIn("does-not-exist", caught.exception.detail)


class TestSetupTraceHonestyFlags(_TraceCase):
    def test_pre_baseline_setup_is_returned_but_flagged(self):
        """History is not absence. The trace resolves, and says which it is."""
        def seed(con):
            _seed(con, setup_id="old-one")
            store.start_baseline(con, started_at=1000)

        result = self.trace("old-one", seed)
        self.assertFalse(result["in_baseline"])
        self.assertEqual(result["baseline"]["started_at"], 1000)

    def test_superseded_engine_version_is_named_not_hidden(self):
        """A trace pinned to the current version would 404 on a setup the
        operator can plainly see. Resolve it, and name the mismatch."""
        result = self.trace("trace-old-engine", lambda con: _seed(
            con, setup_id="trace-old-engine",
            setup_version="setup-v0.1-draft"))
        self.assertEqual(result["stale_versions"],
                         [{"kind": "setup", "recorded": "setup-v0.1-draft",
                           "current": setups.SETUP_VERSION}])
        self.assertEqual(result["versions"]["recorded"]["setup"],
                         "setup-v0.1-draft")
        self.assertEqual(result["versions"]["current"]["setup"],
                         setups.SETUP_VERSION)

    def test_state_history_is_ordered_oldest_first(self):
        def seed(con):
            _seed(con, setup_id="trace-history", state="FORMING")
            store.insert_fact(
                con, symbol="BTC-USD", tf="1D", kind="setup", market_time=10,
                confirmed_at=25, algo_version=setups.SETUP_VERSION,
                payload={"setup_id": "trace-history", "state": "VALIDATED",
                         "strategy": "PULLBACK", "direction": "LONG",
                         "entry": "100", "sl": "95", "tp": "110"})
            con.commit()

        result = self.trace("trace-history", seed)
        self.assertEqual([h["state"] for h in result["history"]],
                         ["FORMING", "VALIDATED"])
        # the latest fact is the setup's current truth
        self.assertEqual(result["state"], "VALIDATED")


if __name__ == "__main__":
    unittest.main()
