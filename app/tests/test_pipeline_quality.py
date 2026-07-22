import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import aggregator, quality, setups, store
from engine.runlog import RunRecorder


class QualityStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "quality.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def candle(self, tf, ts, op="100", hi="102", lo="98", cl="101"):
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("BTC-USD", tf, ts, op, hi, lo, cl, "1", "coinbase", ts + 1))

    def complete_market(self):
        for i in range(4):
            self.candle("1H", i * 3600, op=str(100 + i), hi=str(102 + i),
                        lo=str(98 + i), cl=str(101 + i))
        monday = aggregator.MONDAY_EPOCH
        for i in range(7):
            self.candle("1D", monday + i * 86400, op=str(200 + i),
                        hi=str(202 + i), lo=str(198 + i), cl=str(201 + i))
        self.con.commit()
        with patch("engine.aggregator.time.time", return_value=2_000_000):
            aggregator.aggregate(self.con, "BTC-USD", "4H")
            aggregator.aggregate(self.con, "BTC-USD", "1W")


class TestMarketQuality(QualityStoreCase):
    def test_complete_aggregates_reconcile(self):
        self.complete_market()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        self.assertFalse([c for c in checks if c["status"] == "BLOCKED"])

    def test_gap_blocks_downstream_engines(self):
        self.candle("1H", 0)
        self.candle("1H", 7200)
        self.con.commit()
        with self.assertRaises(quality.DataQualityError):
            quality.assert_market_ready(self.con, "BTC-USD", now=100_000)

    def test_aggregate_mismatch_is_blocking(self):
        self.complete_market()
        self.con.execute(
            "UPDATE candles SET high='999' WHERE symbol='BTC-USD' AND tf='4H'")
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        self.assertIn("AGGREGATE_MISMATCH", {c["code"] for c in checks})


class TestPipelineContracts(QualityStoreCase):
    def test_fact_causality_violation_is_visible(self):
        store.insert_fact(self.con, symbol="BTC-USD", tf="1H", kind="test",
                          market_time=100, confirmed_at=99, algo_version="test-v1",
                          payload={"event": "IMPOSSIBLE"})
        self.con.commit()
        report = quality.audit(self.con, now=1000)
        self.assertFalse(report["evaluation_allowed"])
        self.assertIn("CAUSALITY_VIOLATION", {c["code"] for c in report["blockers"]})

    def test_equity_summary_must_reconcile_to_ledger(self):
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="account",
            market_time=10, confirmed_at=10, algo_version="risk-test",
            payload={"start_equity": "10000", "final_equity": "9000",
                     "curve": [{"ts": 10, "equity": "9500"}]})
        self.con.commit()
        report = quality.audit(self.con, now=1000)
        self.assertIn("EQUITY_RECONCILIATION_FAILED",
                      {c["code"] for c in report["blockers"]})

    def test_quality_history_is_persisted(self):
        report = quality.audit(self.con, now=1000, persist=True)
        self.assertIsNotNone(report["quality_run_id"])
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM quality_runs").fetchone()[0], 1)

    def test_run_recorder_carries_lineage_envelope(self):
        with RunRecorder(self.con, "test", "test-v1", "BTC-USD", "1H") as rec:
            rec.n_inputs = 0
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1H", kind="test",
                market_time=1, confirmed_at=2, algo_version="test-v1",
                payload={"event": "ATTRIBUTED"})
        row = self.con.execute(
            "SELECT run_id,status,input_watermark,input_fingerprint,output_fingerprint "
            "FROM engine_runs").fetchone()
        self.assertTrue(row[0])
        self.assertEqual(row[1], "PASS")
        self.assertEqual(len(row[3]), 64)
        self.assertEqual(len(row[4]), 64)
        producer = self.con.execute(
            "SELECT producer_run_id FROM facts WHERE kind='test'").fetchone()[0]
        self.assertEqual(producer, row[0])


class TestStrategyRulesRemainFrozen(unittest.TestCase):
    def test_observability_did_not_change_strategy_constants(self):
        self.assertEqual(setups.MIN_RR, Decimal("1.5"))
        self.assertEqual(setups.GOOD_RR, Decimal("2.5"))
        self.assertEqual(setups.SL_ATR, Decimal("0.25"))
        self.assertEqual(setups.SWEEP_LOOKBACK_BARS, 10)
        self.assertEqual(setups.MIN_RISK_COST_MULT, Decimal(2))


if __name__ == "__main__":
    unittest.main()
