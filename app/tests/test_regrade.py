"""The daily regrade: recorded, scheduled, fail-visible — and promoting nothing.

The defect this schedule closes is recorded in `trend.py` ("NOT REPRODUCIBLE
FROM THE STORE ... no way to regrade them on a schedule") and `pipeline.py`
(`abtest.by_strategy` "exists, it is not wired to anything, and nothing runs
it on a schedule"). These tests pin the scheduling contract and the record,
not the statistics — `test_abtest.py` owns the numbers.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import regrade, runlog, store


def _fake_report(trustworthy=True):
    return {
        "version": "abtest-vTEST",
        "calibration": {"trustworthy": trustworthy},
        "trustworthy": trustworthy,
        "entry_model_conflicts": {},
        "replay_degradations": [],
        "strategies": {
            "PULLBACK": {"n": 12, "sum_r": -1.0, "expectancy_r": -0.0833,
                         "win_pct": 41.7, "profit_factor": 0.9,
                         "ci_lo": -0.4, "ci_hi": 0.2, "p_gt_zero": 0.3,
                         "missed": 1, "fill_pct": 92.3, "clusters": 9,
                         "cluster_ci_lo": -0.5, "cluster_ci_hi": 0.3,
                         "cluster_p_gt_zero": 0.28, "clears_zero": False,
                         "sample_ok": True},
        },
    }


class RegradeSchedule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.con.close)

    def _run_once(self, now, trustworthy=True):
        with mock.patch("engine.abtest.by_strategy",
                        return_value=_fake_report(trustworthy)), \
             mock.patch("engine.universe.all_tracked_symbols",
                        return_value=["BTCUSDT"]):
            return regrade.run(self.con, now)

    def test_first_run_is_due_and_then_not_due_for_a_day(self):
        self.assertTrue(regrade.due(self.con, 1_000_000))
        self._run_once(1_000_000)
        self.assertFalse(regrade.due(self.con, 1_000_000 + 60))
        self.assertFalse(
            regrade.due(self.con, 1_000_000 + regrade.INTERVAL_SECONDS - 1))
        self.assertTrue(
            regrade.due(self.con, 1_000_000 + regrade.INTERVAL_SECONDS))

    def test_run_records_the_whole_report_with_its_trust_flag(self):
        self._run_once(2_000_000, trustworthy=False)
        prev = regrade.last_run(self.con)
        self.assertEqual(prev["observed_at"], 2_000_000)
        self.assertFalse(prev["trustworthy"])
        self.assertIn("PULLBACK", prev["report"]["strategies"])
        # An untrustworthy regrade is still RECORDED — refusing to write it
        # would hide the calibration failure, the loud-fallback defect.
        self.assertEqual(prev["report"]["calibration"]["trustworthy"], False)

    def test_maybe_run_is_a_no_op_until_due_and_logs_when_it_runs(self):
        logged = []

        class _Log:
            def info(self, msg):
                logged.append(("info", msg))

            def warning(self, msg):
                logged.append(("warning", msg))

        with mock.patch("engine.abtest.by_strategy",
                        return_value=_fake_report()), \
             mock.patch("engine.universe.all_tracked_symbols",
                        return_value=["BTCUSDT"]):
            first = regrade.maybe_run(self.con, 3_000_000, log=_Log())
            second = regrade.maybe_run(self.con, 3_000_000 + 60, log=_Log())
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        regrades = [m for lvl, m in logged if m.startswith("REGRADE")]
        self.assertTrue(regrades, "a regrade that runs must say so")
        self.assertIn("PULLBACK", regrades[0])
        self.assertIn("clears_zero=False", regrades[0])

    def test_untrustworthy_regrade_warns_rather_than_passing_silently(self):
        logged = []

        class _Log:
            def info(self, msg):
                logged.append(("info", msg))

            def warning(self, msg):
                logged.append(("warning", msg))

        with mock.patch("engine.abtest.by_strategy",
                        return_value=_fake_report(trustworthy=False)), \
             mock.patch("engine.universe.all_tracked_symbols",
                        return_value=["BTCUSDT"]):
            regrade.maybe_run(self.con, 4_000_000, log=_Log())
        self.assertTrue(any(lvl == "warning" and "untrustworthy" in msg
                            for lvl, msg in logged))

    def test_regrade_lines_survive_log_retention(self):
        # The AUTOTRADER lesson: an evidence line unmatched by any audit
        # prefix is discarded on the first rotation.
        self.assertIn("REGRADE", runlog.AUDIT_PREFIXES)

    def test_versions_to_grade_covers_the_record_only_engines(self):
        from engine import breakout, trend
        vs = regrade.versions_to_grade()
        self.assertIn(breakout.BREAKOUT_VERSION, vs)
        self.assertIn(trend.TREND_VERSION, vs)

    def test_a_failed_run_is_recorded_as_an_attempt_and_waits_a_day(self):
        """The crash-loop defect: a run that raised before its INSERT left
        due() true, so a deterministic failure retried at CYCLE cadence
        forever. A failure must count as an attempt — recorded untrustworthy
        with the error as its report, loudly logged, and not retried until
        the interval elapses."""
        logged = []

        class _Log:
            def info(self, msg):
                logged.append(("info", msg))

            def warning(self, msg):
                logged.append(("warning", msg))

            def error(self, msg):
                logged.append(("error", msg))

        with mock.patch("engine.abtest.by_strategy",
                        side_effect=RuntimeError("boom")), \
             mock.patch("engine.universe.all_tracked_symbols",
                        return_value=["BTCUSDT"]):
            res = regrade.maybe_run(self.con, 5_000_000, log=_Log())
        self.assertIsNotNone(res)
        self.assertFalse(res["trustworthy"])
        self.assertIn("boom", res["report"]["error"])
        prev = regrade.last_run(self.con)
        self.assertEqual(prev["observed_at"], 5_000_000)
        self.assertFalse(prev["trustworthy"])
        self.assertIn("error", prev["report"])
        self.assertFalse(regrade.due(self.con, 5_000_000 + 60),
                         "a failure that leaves the regrade due retries at "
                         "cycle cadence — the crash loop this fix closes")
        self.assertTrue(
            regrade.due(self.con, 5_000_000 + regrade.INTERVAL_SECONDS))
        self.assertTrue(any(lvl == "error" and "REGRADE" in msg
                            for lvl, msg in logged),
                        "a recorded failure must still be loud")

    def test_the_heartbeat_is_threaded_into_the_replay(self):
        """One beat before minutes of replay reads as a hang to the watchdog
        (SCANNER_DARK_AFTER_S) — the retention sweep precedent: beat inside
        the work. The callback must reach the per-symbol loop."""
        beats = []

        def beat(msg):
            beats.append(msg)

        with mock.patch("engine.abtest.by_strategy",
                        return_value=_fake_report()) as by_strategy, \
             mock.patch("engine.universe.all_tracked_symbols",
                        return_value=["BTCUSDT"]):
            regrade.maybe_run(self.con, 6_000_000, beat=beat)
        self.assertIs(by_strategy.call_args.kwargs.get("beat"), beat)


class RegradeUnmocked(unittest.TestCase):
    """One run with nothing patched, on the store shape that crashed it.

    The mocked suite above mirrors the wiring; only an unmocked run can catch
    what the mirror lacks. A reference-series key ('@' in the symbol) is
    tracked the moment it holds a 1D candle, and venues.venue_for raises on
    it by contract — unfiltered, that raise fired before the INSERT and the
    daily regrade became an every-cycle crash loop.
    """

    def test_a_reference_key_in_the_universe_does_not_crash_the_regrade(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = store.connect(Path(tmp.name) / "t.db")
        self.addCleanup(con.close)
        con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("BTCUSDT@binance-spot", "1D", 0, "100", "102", "98", "100",
             "1", "test", 0))
        con.commit()
        res = regrade.run(con, 7_000_000, resamples=50)
        self.assertEqual(res["observed_at"], 7_000_000)
        prev = regrade.last_run(con)
        self.assertIsNotNone(prev, "the run must record its row")
        self.assertEqual(prev["observed_at"], 7_000_000)
        # An empty book grades nothing — the row still exists, which is the
        # whole point: the attempt is the record, the strategies may be {}.
        self.assertIsInstance(prev["report"].get("strategies"), dict)


if __name__ == "__main__":
    unittest.main()
