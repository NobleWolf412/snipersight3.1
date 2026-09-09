"""The analyst sees dated facts, never future candles or invented macro data."""
import json
import tempfile
import unittest
from pathlib import Path

from engine import analyst_context as ac, store


class AnalystEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "scratch.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def candle(self, ts, close, tf="1H"):
        self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                         ("BTCUSDT", tf, ts, str(close), str(close + 1),
                          str(close - 1), str(close), "1", "test", ts))

    def test_empty_store_names_unknowns_and_does_not_write(self):
        before = self.con.total_changes
        s = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=7200)
        self.assertEqual(self.con.total_changes, before)
        self.assertEqual(s["macro"]["status"], "NOT_CONNECTED")
        self.assertEqual(s["edge"]["status"], "NOT_SUPPLIED")
        self.assertIsNone(s["scanner_quality"]["evaluation_allowed"])
        self.assertEqual([r["timeframe"] for r in s["top_down"]], ["1W", "1D", "4H", "1H"])
        self.assertTrue(all(r["freshness"] == "MISSING" for r in s["top_down"]))
        self.assertEqual(s["version"], "analyst-context-v0.2-draft")

    def test_present_day_calendar_cannot_leak_into_historical_analysis(self):
        macro = {"as_of": 300, "status": "AVAILABLE", "events": [{"title": "future knowledge"}]}
        s = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=200, macro=macro)
        self.assertEqual(s["macro"]["status"], "NOT_AVAILABLE_AT_CUTOFF")
        self.assertNotIn("future knowledge", json.dumps(s))
        current = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=300, macro=macro)
        self.assertEqual(current["macro"], macro)

    def test_current_candle_is_excluded_and_closed_cutoff_is_inclusive(self):
        self.candle(0, 100)
        self.candle(3600, 200)
        self.candle(7200, 900)
        s = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=7200)
        own = s["top_down"][-1]
        self.assertEqual(own["chart"]["close"], "200")
        self.assertEqual(own["last_closed_at"], 7200)
        self.assertEqual(own["freshness"], "FRESH")
        # Adding later information must not rewrite a historical snapshot.
        self.candle(10800, 999)
        self.assertEqual(s, ac.snapshot(self.con, "BTCUSDT", "1H", as_of=7200))

    def test_old_chart_is_explicitly_stale_and_has_no_current_call(self):
        self.candle(0, 100)
        own = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=14401)["top_down"][-1]
        self.assertEqual(own["freshness"], "STALE")
        self.assertEqual(own["top_down_call"], "UNKNOWN")

    def test_indicators_are_versioned_dated_events_not_current_values(self):
        kind, version = ac.INDICATORS[1]
        for at, ver, value in [(3600, version, "40"), (7201, version, "99"),
                               (7100, "old-version", "80")]:
            store.insert_fact(self.con, symbol="BTCUSDT", tf="1H", kind=kind,
                              market_time=at, confirmed_at=at, algo_version=ver,
                              payload={"event": "RSI_CROSS", "rsi": value})
        row = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=7200)["indicator_events"][1]
        self.assertEqual(row["version"], version)
        self.assertEqual(len(row["events"]), 1)
        self.assertEqual(row["events"][0]["payload"]["rsi"], "40")
        self.assertEqual(row["events"][0]["age_seconds"], 3600)

    def test_latest_quality_before_cutoff_retains_blockers_and_age(self):
        for at, status, allowed in [(100, "BLOCKED", 0), (300, "PASS", 1)]:
            self.con.execute(
                "INSERT INTO quality_runs (observed_at,status,evaluation_allowed,summary,report) "
                "VALUES (?,?,?,?,?)", (at, status, allowed, "test",
                                       json.dumps({"blockers": ["gap"] if not allowed else []})))
        q = ac.snapshot(self.con, "BTCUSDT", "1H", as_of=200)["scanner_quality"]
        self.assertEqual(q["status"], "BLOCKED")
        self.assertFalse(q["evaluation_allowed"])
        self.assertEqual(q["age_seconds"], 100)
        self.assertEqual(q["blockers"], ["gap"])


if __name__ == "__main__":
    unittest.main()
