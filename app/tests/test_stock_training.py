import json
import tempfile
import unittest
from pathlib import Path

from engine import stockcalendar, stockdemo, stockstore


class StockCalendarTest(unittest.TestCase):
    session = {
        "premarket_open": "2026-11-27T04:00:00-05:00",
        "regular_open": "2026-11-27T09:30:00-05:00",
        "regular_close": "2026-11-27T13:00:00-05:00",
        "after_hours_close": "2026-11-27T17:00:00-05:00",
        "authority": "TEST_CALENDAR",
    }

    def test_explicit_early_close_is_not_assumed_to_be_a_normal_session(self):
        self.assertEqual(stockcalendar.classify(
            "2026-11-27T12:59:00-05:00", self.session)["phase"], "REGULAR")
        self.assertEqual(stockcalendar.classify(
            "2026-11-27T13:01:00-05:00", self.session)["phase"], "AFTER_HOURS")

    def test_closed_session_is_not_tradable(self):
        out = stockcalendar.classify("2026-11-27T18:00:00-05:00", self.session)
        self.assertEqual(out["phase"], "CLOSED")
        self.assertFalse(out["tradable"])


class StockTrainingWorkflowTest(unittest.TestCase):
    def test_report_is_loudly_synthetic_and_never_gradeable(self):
        out = stockdemo.report()
        self.assertEqual(out["mode"], "TRAINING_FIXTURE")
        self.assertEqual(out["evidence_scope"], "FIXTURE")
        self.assertFalse(out["live_orders_enabled"])
        self.assertFalse(out["grade_eligible"])
        self.assertTrue(all(row["evidence_scope"] == "FIXTURE" for row in out["setups"]))
        self.assertTrue(all(not row["grade_eligible"] for row in out["setups"]))

    def test_scanner_explains_acceptance_and_stock_native_rejections(self):
        out = stockdemo.report()
        by_symbol = {row["raw_symbol"]: row for row in out["setups"]}
        self.assertEqual(by_symbol["AAPL"]["state"], "READY")
        self.assertEqual(by_symbol["AAPL"]["plan"]["planned_r"], "2.00")
        self.assertEqual(by_symbol["TSLA"]["rejections"][0]["code"], "EARNINGS_WINDOW")
        self.assertEqual(by_symbol["GME"]["rejections"][0]["code"], "TRADING_HALT")

    def test_simulator_uses_server_owned_decimal_strings(self):
        result = stockdemo.report()["simulation"]
        self.assertEqual(result["state"], "CLOSED")
        self.assertEqual(result["outcome"], "TARGET")
        self.assertEqual(result["r_multiple"], "2.00")
        self.assertIsInstance(result["pnl_usd"], str)
        self.assertFalse(result["grade_eligible"])


class StockStoreIsolationTest(unittest.TestCase):
    def test_store_is_append_only_and_rejects_unlabelled_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = stockstore.connect(Path(tmp) / "stocks.db")
            payload = {"state": "READY", "entry": "205.50"}
            args = dict(asset_id="fixture:gap", symbol="AAPL", kind="setup",
                        market_time=1, confirmed_at=2,
                        algo_version=stockdemo.STOCK_DEMO_VERSION,
                        payload=payload, evidence_scope="FIXTURE")
            self.assertTrue(stockstore.insert_fact(con, **args))
            self.assertFalse(stockstore.insert_fact(con, **args))
            row = con.execute("SELECT payload,evidence_scope FROM stock_facts").fetchone()
            self.assertEqual(json.loads(row[0]), payload)
            self.assertEqual(row[1], "FIXTURE")
            with self.assertRaises(ValueError):
                stockstore.insert_fact(con, **{**args, "market_time": 3,
                                               "evidence_scope": "CRYPTO"})
            con.close()


if __name__ == "__main__":
    unittest.main()
