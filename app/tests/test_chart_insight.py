"""The chart insight is a read model, not another trading engine."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from engine import chart_insight, chartread, setups, store
import server


class ChartInsightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "scratch.db"
        self.con = store.connect(self.path)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def candle(self, ts):
        self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                         ("BTCUSDT", "1H", ts, "100", "101", "99", "100", "1", "test", ts))

    def test_empty_and_query_only_connection(self):
        before = self.con.total_changes
        self.con.execute("PRAGMA query_only=ON")
        result = chart_insight.snapshot(self.con, "BTCUSDT", "1H", as_of=7200)
        self.assertEqual(self.con.total_changes, before)
        self.assertEqual(result["basis"], "CURRENT_CLOSED_CANDLES")
        self.assertTrue(all(row["freshness"] == "MISSING" for row in result["frames"]))
        self.assertTrue(all(row["lookback_bars"] == 0 for row in result["frames"]))
        self.assertEqual(result["usage"]["chart"], "OBSERVATION_ONLY")
        self.assertEqual(result["usage"]["higher_timeframes"], "OBSERVATION_ONLY")

    def test_exact_closed_lookback_and_future_stability(self):
        for i in range(150):
            self.candle(i * 3600)
        before = self.con.total_changes
        result = chart_insight.snapshot(self.con, "BTCUSDT", "1H", as_of=149 * 3600)
        own = result["frames"][-1]
        self.assertEqual(own["lookback_bars"], chartread.window_bars("1H"))
        self.assertEqual(own["last_closed_at"], 149 * 3600)
        self.assertEqual(own["freshness"], "FRESH")
        self.assertEqual(self.con.total_changes, before)
        self.candle(150 * 3600)
        self.assertEqual(result, chart_insight.snapshot(self.con, "BTCUSDT", "1H", as_of=149 * 3600))

    def test_old_candles_and_policy_labels_are_not_approval(self):
        self.candle(0)
        with patch.dict(setups.WINDOW_POLICY, {"test": "BLOCK"}):
            result = chart_insight.snapshot(self.con, "BTCUSDT", "1H", as_of=20000)
        self.assertEqual(result["frames"][-1]["freshness"], "STALE")
        self.assertEqual(result["usage"]["chart"], "POLICY_DEPENDENT")
        self.assertIn("not trade approval", result["notice"])

    def test_endpoint_reads_only_scratch_and_validates_input(self):
        self.con.commit()
        real_connect = store.connect
        def scratch():
            con = real_connect(self.path)
            con.execute("PRAGMA query_only=ON")
            return con
        with patch.object(server.store, "connect", side_effect=scratch):
            client = TestClient(server.app)
            response = client.get("/api/chart-insight?symbol=BTCUSDT&tf=1H")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["symbol"], "BTCUSDT")
            self.assertEqual(client.get("/api/chart-insight?tf=bad").status_code, 422)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0], 0)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM quality_runs").fetchone()[0], 0)
