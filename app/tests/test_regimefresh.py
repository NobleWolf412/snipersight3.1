"""Regime freshness is an AUDITION, and these are the properties that keep it one.

Two rules this file exists to hold. The factor may only read what the trade
could have read (§6 rule 3 — confirmed_at is when the engine could first have
known), and nothing in a trading path may consume it until the operator has
graded it and bumped a version (§6 rule 7).

The second one has teeth here because the same idea has been wrong twice
already on this book: btcalign graded OPPOSED at +0.536 R against ALIGNED at
-0.244 R, and BIAS_POLICY graded AGAINST at +0.2755 R against WITH at -0.0736 R.
Both were the obvious rule; both were backwards. "Do not trade a stale label"
reads just as obviously and has earned no more trust than they had.
"""
import inspect
import sqlite3
import unittest

from engine import execsim, regimefresh, risk, scalein, setups


class TriggerCase(unittest.TestCase):
    def test_trigger_at_reads_the_event_the_label_names(self):
        payload = {"regime": "BEAR_TREND",
                   "evidence": {"trigger": {"at": 1642636800, "event": "LABEL"}}}
        self.assertEqual(regimefresh.trigger_at(payload), 1642636800)

    def test_an_unrecorded_trigger_is_none_not_zero(self):
        """A missing trigger must not become an age of 'the epoch', which would
        render every such label maximally stale and invent the finding."""
        self.assertIsNone(regimefresh.trigger_at({"regime": "RANGE"}))
        self.assertIsNone(regimefresh.trigger_at({"evidence": {}}))
        self.assertIsNone(regimefresh.trigger_at({}))


class AsOfCase(unittest.TestCase):
    """The whole factor is worthless if it can see forward."""

    SERIES = [(100, "BULL_TREND", 60), (200, "WEAKENING_BULL", 170),
              (300, "BEAR_TREND", 250)]

    def test_reads_only_labels_already_confirmed(self):
        regime, confirmed_at, trig, _ = regimefresh.label_asof(self.SERIES, 250)
        self.assertEqual(regime, "WEAKENING_BULL")
        self.assertEqual(confirmed_at, 200)
        self.assertEqual(trig, 170)

    def test_a_label_confirmed_one_second_later_is_invisible(self):
        regime, _, _, _ = regimefresh.label_asof(self.SERIES, 299)
        self.assertEqual(regime, "WEAKENING_BULL",
                         "the factor read a regime the trade could not have known")

    def test_before_the_first_fact_there_is_no_label(self):
        regime, confirmed_at, trig, seen = regimefresh.label_asof(self.SERIES, 99)
        self.assertIsNone(regime)
        self.assertIsNone(confirmed_at)
        self.assertIsNone(trig)
        self.assertIsNone(seen)


class ExtractorCase(unittest.TestCase):
    def test_unannotated_yields_no_flags_so_missing_stays_missing(self):
        """An unreadable regime history is not a fresh one. Returning 0.0 here
        would launder 'we did not look' into 'we looked and it was fine'."""
        self.assertEqual(regimefresh.factor_extractors({"tf": "1H"}), {})

    def test_stale_and_fresh_are_complements_not_both(self):
        secs = regimefresh.TF_SECONDS["1H"]
        old = {"regime_asof": "BEAR_TREND", "tf": "1H",
               "regime_age_bars": regimefresh.STALE_AFTER_BARS + 1,
               "regime_age_s": secs * 100}
        new = dict(old, regime_age_bars=1.0)
        self.assertEqual(regimefresh.factor_extractors(old)["regime_stale"], 1.0)
        self.assertEqual(regimefresh.factor_extractors(old)["regime_fresh"], 0.0)
        self.assertEqual(regimefresh.factor_extractors(new)["regime_stale"], 0.0)
        self.assertEqual(regimefresh.factor_extractors(new)["regime_fresh"], 1.0)

    def test_an_unknown_timeframe_yields_no_age_flag_rather_than_a_guess(self):
        payload = {"regime_asof": "BEAR_TREND", "tf": "3H", "regime_lag_s": 999}
        self.assertNotIn("label_late", regimefresh.factor_extractors(payload))


class AnnotateCase(unittest.TestCase):
    def test_a_candidate_with_no_market_is_skipped_not_crashed(self):
        con = sqlite3.connect(":memory:")
        try:
            cands = [{"confirmed_at": 500, "payload": {}}]
            self.assertEqual(regimefresh.annotate(con, cands), 0)
            self.assertEqual(cands[0]["payload"], {})
        finally:
            con.close()


class VerifiesItselfCase(unittest.TestCase):
    """The defect this module shipped with, turned into a test.

    Its first version reconstructed labels from ONE of the thirteen regime
    versions in the store, matched the engine's own recorded regime 68% of the
    time, and reported a split anyway. A reconstruction that reads a different
    label than the gate did is not a weaker measurement of the same thing - it
    is a measurement of something else, and it cannot announce that itself.
    """

    def test_grade_reports_how_well_it_reproduced_the_engine(self):
        src = inspect.getsource(regimefresh.grade)
        self.assertIn("verify(", src,
                      "grade() presents a split without checking the labels "
                      "under it against what the engine actually read")
        self.assertIn("reconstruction", inspect.getsource(regimefresh.grade))

    def test_a_floor_exists_and_is_not_perfection(self):
        self.assertLess(regimefresh.VERIFY_FLOOR, 1.0,
                        "demanding a perfect match fails on the 13 of 5,940 "
                        "that genuinely disagree")
        self.assertGreater(regimefresh.VERIFY_FLOOR, 0.9)

    def test_the_cli_refuses_to_present_an_untrusted_split_quietly(self):
        src = inspect.getsource(regimefresh.main)
        self.assertIn("trustworthy", src)
        self.assertIn("Do not quote these numbers", src)


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """House convention: evidence is recorded, not filtered on. Wiring this
        into a trading path is a versioned decision for the operator — five tags
        move together and the forward record restarts from its current 49
        trades — never an import."""
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("regimefresh", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")


if __name__ == "__main__":
    unittest.main()
