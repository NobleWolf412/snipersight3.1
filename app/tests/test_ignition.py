"""Trend ignition is an AUDITION, and these are the properties that keep it one.

The module answers "what would entering at trend birth have earned" without
creating the entry. Everything here defends the honesty of that answer: the
event may only be read at its confirmed_at, the baseline may not wander
between runs, refusals are counted rather than dropped, and no trading module
may consume any of it until the operator promotes a playbook under a new
version.
"""
import inspect
import unittest

from engine import execsim, ignition, risk, scalein, setups


def _regime(mt, ca, regime, trig_at=None, trig_event=None, bull=True):
    ev = {"last_break": {"direction": "BULL" if bull else "BEAR"},
          "last_high_label": "HH" if bull else "LH",
          "last_low_label": "HL" if bull else "LL"}
    if trig_at is not None:
        ev["trigger"] = {"at": trig_at, "event": trig_event or "LABEL"}
    return (mt, ca, {"regime": regime, "evidence": ev})


class ExtractCase(unittest.TestCase):
    TF = 3600

    def test_only_transitions_into_full_trend_count(self):
        rows = [_regime(100, 100, "RANGE"),
                _regime(200, 200, "BULL_TREND", 190, "BOS"),
                _regime(300, 300, "WEAKENING_BULL"),
                _regime(400, 400, "BULL_TREND", 210, "LABEL")]
        events = ignition.extract_events(rows, self.TF)
        self.assertEqual(len(events), 2)
        self.assertEqual([e["confirmed_at"] for e in events], [200, 400])

    def test_freshness_is_the_transitions_own_lag(self):
        rows = [_regime(0, 0, "RANGE"),
                _regime(100, 100 + 4 * self.TF, "BULL_TREND", 100, "BOS"),
                _regime(200, 200 + 400 * self.TF, "RANGE"),
                _regime(300, 300 + 500 * self.TF, "BULL_TREND",
                        300 + 300 * self.TF, "LABEL")]
        events = ignition.extract_events(rows, self.TF)
        self.assertTrue(events[0]["fresh"], "4-bar lag must be fresh")
        self.assertFalse(events[1]["fresh"], "200-bar lag must be stale")

    def test_state_end_bounds_the_random_baseline(self):
        rows = [_regime(0, 0, "RANGE"),
                _regime(100, 1000, "BULL_TREND", 990, "BOS"),
                _regime(200, 5000, "RANGE")]
        events = ignition.extract_events(rows, self.TF)
        self.assertEqual(events[0]["state_end"], 5000,
                         "an in-state entry may not outlive the state")

    def test_mismatched_evidence_is_flagged_not_traded(self):
        bad = _regime(100, 100, "BULL_TREND", 90, "BOS", bull=False)
        events = ignition.extract_events(
            [_regime(0, 0, "RANGE"), bad], self.TF)
        self.assertFalse(ignition.trifecta_ok(events[0]),
                         "BULL_TREND with bear evidence must fail the check")


class StopLevelCase(unittest.TestCase):
    LABELS = [(100, "LOW", "HL", 10), (200, "HIGH", "LH", 20),
              (300, "LOW", "HL", 12), (400, "LOW", "LL", 8)]

    def test_reads_only_labels_already_confirmed(self):
        self.assertEqual(
            ignition.label_level_asof(self.LABELS, 250, "LOW"), 10,
            "the HL at 300 was not knowable at 250")

    def test_the_latest_confirmed_hl_wins(self):
        self.assertEqual(
            ignition.label_level_asof(self.LABELS, 350, "LOW"), 12)

    def test_wrong_label_kind_is_never_a_stop(self):
        # after 400 the last LOW label is LL — an LL is not an uptrend's
        # invalidation, and returning it would hang a long's stop off a level
        # the pattern does not claim.
        self.assertEqual(
            ignition.label_level_asof(self.LABELS, 450, "LOW"), 12)

    def test_no_label_yet_is_none_not_zero(self):
        self.assertIsNone(ignition.label_level_asof(self.LABELS, 50, "LOW"))


class BaselineCase(unittest.TestCase):
    def test_random_bar_is_deterministic_across_runs(self):
        a = ignition.pick_baseline_bar("BTCUSDT|1H|12345", 10, 500)
        b = ignition.pick_baseline_bar("BTCUSDT|1H|12345", 10, 500)
        self.assertEqual(a, b, "an audition whose baseline moves between runs "
                               "cannot be audited")

    def test_different_events_get_different_bars(self):
        picks = {ignition.pick_baseline_bar(f"S|1H|{i}", 0, 10_000)
                 for i in range(50)}
        self.assertGreater(len(picks), 40)

    def test_degenerate_window_returns_its_only_bar(self):
        self.assertEqual(ignition.pick_baseline_bar("k", 7, 7), 7)


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """Evidence is recorded, not filtered on. A passing grade here is a
        versioned playbook PROPOSAL for the operator — five tags move and the
        forward record restarts — never an import."""
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("ignition", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")

    def test_the_module_writes_nothing(self):
        src = inspect.getsource(ignition)
        self.assertNotIn("insert_fact", src,
                         "the audition wrote a fact — it is no longer "
                         "derived at analysis time")
        self.assertIn("mode=ro", src,
                      "main() must open the store read-only")

    def test_one_execution_authority(self):
        src = inspect.getsource(ignition)
        for shared in ("simulate_entry", "walk_exit", "settle"):
            self.assertIn(shared, src)
        self.assertNotIn("def simulate_entry", src,
                         "a private simulation core is how replays drift")


if __name__ == "__main__":
    unittest.main()
