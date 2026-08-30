"""Sessions engine — the properties that must not regress.

The engine is a clock labeller, and every defect a clock labeller can have is
a quiet one: a boundary off by an hour mislabels a fifth of every day forever,
a per-bar emission buries the five real transitions a day under hundreds of
calendar rows, and a label on a 4H bar claims a precision the bar does not
have. Each test pins one of those against arithmetic this file can state.

Timestamps are built from epoch hours: epoch 0 is 1970-01-01 00:00 UTC, so
open_ts = h * 3600 puts a bar's open at UTC hour h.
"""
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from engine import execsim, pipeline, risk, scalein, sessions, setups, store

TF = 3600


class SessionMap(unittest.TestCase):
    """The boundary table itself, hour by hour."""

    def test_every_boundary_hour_lands_on_the_right_side(self):
        """An off-by-one here mislabels an hour of every day forever, and
        nothing downstream would ever notice — the label is only wrong, not
        missing."""
        for hour, want in ((23, "ASIA"), (0, "ASIA"), (6, "ASIA"),
                          (7, "LONDON"), (11, "LONDON"),
                          (12, "NY_OVERLAP"), (15, "NY_OVERLAP"),
                          (16, "NY"), (20, "NY"),
                          (21, "QUIET"), (22, "QUIET")):
            with self.subTest(hour=hour):
                self.assertEqual(sessions.session_label(hour * TF), want)

    def test_the_map_is_total_over_the_day(self):
        """Every UTC hour has exactly one session — a gap would raise at label
        time, on data rather than on code, in production."""
        labels = {sessions.session_label(h * TF) for h in range(24)}
        self.assertEqual(labels,
                         {name for name, _s, _e in sessions.SESSIONS})

    def test_sub_hour_bars_inherit_their_hour(self):
        """A 15m bar opening at 06:45 is still ASIA; the label reads the hour
        of the OPEN, and 15m/5m bars never straddle an hour boundary."""
        self.assertEqual(sessions.session_label(6 * TF + 2700), "ASIA")
        self.assertEqual(sessions.session_label(7 * TF), "LONDON")


class EngineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, tf, hours):
        for h in hours:
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", tf, h * TF, "100", "102", "98", "100", "1",
                 "test", h * TF))
        self.con.commit()

    def facts(self, tf="1H"):
        rows = store.get_facts(self.con, "BTC-USD", tf, "sessions",
                               sessions.SESSIONS_VERSION)
        return [{"market_time": r["market_time"],
                 "confirmed_at": r["confirmed_at"],
                 **json.loads(r["payload"])} for r in rows]

    def test_emits_only_on_session_change(self):
        """The session of every bar is derivable from the clock; per-bar
        emission would be hundreds of rows of calendar around five rows of
        content. Bars 5..9 span the 07:00 ASIA->LONDON boundary: two facts,
        not five."""
        self.load("1H", range(5, 10))
        sessions.run(self.con, "BTC-USD", "1H", TF)
        got = self.facts()
        self.assertEqual([(f["session"], f["state"]) for f in got],
                         [("ASIA", "ESTABLISHED"), ("LONDON", "CHANGED")])
        self.assertEqual(got[1]["market_time"], 7 * TF)
        self.assertEqual(got[1]["from"], "ASIA")
        self.assertEqual(got[1]["bars_in_prev_state"], 2)

    def test_facts_confirm_at_bar_close_only(self):
        """Closed candles only (convention 4): the label is clock-derivable at
        the open, but one convention for 'when was this knowable' outranks a
        bar of lead time — everything a grader joins the label to exists only
        at the close."""
        self.load("1H", range(5, 10))
        sessions.run(self.con, "BTC-USD", "1H", TF)
        for f in self.facts():
            self.assertEqual(f["confirmed_at"], f["market_time"] + TF)

    def test_a_bar_spanning_sessions_gets_no_label(self):
        """A 4H bucket opening at 04:00 covers ASIA, LONDON and the overlap; a
        label naming one of them would be mostly false. The refusal is
        structural, not a warmup."""
        self.load("4H", (0, 4, 8))          # open_ts in hours of 4H grid
        out = sessions.run(self.con, "BTC-USD", "4H", 4 * TF)
        self.assertTrue(out["unsupported"])
        self.assertEqual(self.facts("4H"), [])

    def test_no_candles_means_no_facts(self):
        out = sessions.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(out["changes"], 0)
        self.assertEqual(self.facts(), [])

    def test_rerun_over_identical_candles_is_a_noop(self):
        """Append-only idempotence (convention 1): the content hash makes a
        re-run write zero new rows."""
        self.load("1H", range(5, 10))
        sessions.run(self.con, "BTC-USD", "1H", TF)
        again = sessions.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(again["changes"], 0)
        self.assertEqual(len(self.facts()), 2)

    def test_a_quiet_session_with_no_bars_emits_nothing_for_those_hours(self):
        """A venue-acknowledged empty stretch has no bars, so the sessions it
        covered leave no label — the engine describes bars that exist, never
        hours that merely passed. Bars at 06 and 13 skip LONDON entirely: the
        13:00 bar emits NY_OVERLAP directly from ASIA."""
        self.load("1H", (6, 13))
        sessions.run(self.con, "BTC-USD", "1H", TF)
        got = self.facts()
        self.assertEqual([f["session"] for f in got], ["ASIA", "NY_OVERLAP"])
        self.assertNotIn("LONDON", [f["session"] for f in got])


class RecordedNotFilteredOn(unittest.TestCase):
    """Convention 7 — a session label gates nothing until it is graded."""

    def test_no_trading_module_imports_sessions(self):
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("sessions", inspect.getsource(mod),
                             f"{mod.__name__} must not consume session labels "
                             f"before factorstats grades them")

    def test_the_engine_is_scheduled_as_descriptive(self):
        """An engine that is built, tested and never run emits nothing to
        grade — how ranges and cooldowns both died. The roster is the fix."""
        self.assertIn(sessions, pipeline.DESCRIPTIVE)
        self.assertIn(sessions, pipeline.PER_SYMBOL)
        self.assertNotIn(sessions, pipeline.TRADING)


if __name__ == "__main__":
    unittest.main()
