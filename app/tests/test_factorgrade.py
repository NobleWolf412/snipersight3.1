"""Grading the unwired engines — the mappings, and the bar.

Seven engines run every cycle and touch no trading decision. They became
drawable on 4 Aug 2026, which is a soft form of gating, so they were graded.
Result on 477 closed trades: nothing clears.

THE TESTS THAT MATTER MOST ARE THE MAPPING ONES. Twice now a chart layer has
matched a state string the engine never writes and silently drawn nothing:
`HVN` against the engine's `AT_HVN`, and `squeeze === true` against the
engine's string `'ON'`. Both looked correct in review. In a GRADE the same
mistake is worse than an empty layer — an unmatched mapping produces an empty
cohort, and an empty cohort reads as "no effect" rather than "no reading".

So every state value here is asserted against the engine module that writes
it. If an engine renames a state, these fail loudly instead of quietly
grading nothing.
"""
import tempfile
import unittest
from pathlib import Path

from engine import factorgrade, store


def _spec(name):
    return next(s for s in factorgrade.FACTORS if s["name"] == name)


class MappingCase(unittest.TestCase):
    """Every state string must exist in the engine that emits it."""

    def _src(self, module):
        p = Path(__file__).resolve().parent.parent / "engine" / f"{module}.py"
        return p.read_text(encoding="utf-8")

    def test_volatility_states_match_the_engine(self):
        src = self._src("volatility")
        # volatility.py: {"squeeze": new, ...} where new is "ON"/"OFF"
        self.assertIn('"ON" if on else "OFF"', src)
        self.assertEqual(_spec("squeeze")["field"], "squeeze",
                         "grading the event PHASE instead of the squeeze state")
        # and the ATR band lives in `regime`, not in `state`
        self.assertIn('"regime": new', src)
        self.assertEqual(_spec("atr_regime")["field"], "regime")

    def test_volume_states_match_the_engine(self):
        src = self._src("volume")
        self.assertIn('"rvol_state": new', src)
        self.assertEqual(_spec("rvol")["field"], "rvol_state")
        self.assertIn('"side": new', src)
        self.assertEqual(_spec("vwap_side")["field"], "side")

    def test_volprofile_uses_the_schmitt_names(self):
        """AT_HVN, not HVN. This exact mismatch shipped once."""
        src = self._src("volprofile")
        self.assertIn("AT_HVN", src)
        self.assertEqual(_spec("volprofile")["field"], "state")

    def test_no_factor_grades_the_from_field(self):
        """`from` is the PREVIOUS state. Grading it would measure where the
        market came from, not where it was when the trade was taken."""
        for spec in factorgrade.FACTORS:
            self.assertNotEqual(spec["field"], "from", spec["name"])

    def test_directional_maps_only_use_real_sides(self):
        for spec in factorgrade.FACTORS:
            if spec["supports"] is None:
                continue
            for state, side in spec["supports"].items():
                self.assertIn(side, ("LONG", "SHORT"),
                              f"{spec['name']}:{state} maps to {side}")

    def test_neutral_states_are_left_out_of_directional_maps(self):
        """INSIDE and MIXED argue for neither side; forcing them into one
        would invent a signal the engine never gave."""
        self.assertNotIn("INSIDE", _spec("ma_position")["supports"])
        self.assertNotIn("MIXED", _spec("ma_stack")["supports"])


class GradingCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_it_writes_nothing(self):
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        factorgrade.grade(self.con)
        self.assertEqual(
            before, self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0])

    def test_the_report_covers_every_factor(self):
        rep = factorgrade.grade(self.con)
        for spec in factorgrade.FACTORS:
            self.assertIn(spec["name"], rep["factors"])
        self.assertIn("fvg_gap", rep["factors"], "the gap factor is not graded")
        self.assertTrue(rep["derived_at_analysis_time"])

    def test_the_bar_is_the_interval_not_the_mean(self):
        """The house bar everywhere else — edgestats' verdict, livegate's edge
        criterion — is that the interval clears zero. A cohort with a handsome
        mean and an interval spanning zero has shown nothing."""
        import inspect
        src = inspect.getsource(factorgrade.grade)
        self.assertIn('b["ci_lo"] > 0', src)
        self.assertNotIn('mean_r"] > 0', src)

    def test_a_cohort_under_the_floor_reports_counts_but_no_verdict(self):
        """Loud fallback, house convention 4: the counts are facts, the mean
        is not trustworthy, and `clears_zero` must never be true on a sample
        too small to bootstrap."""
        rep = factorgrade.grade(self.con)
        for d in rep["factors"].values():
            for r in d["cohorts"].values():
                if not r["sample_ok"]:
                    self.assertIsNone(r["ci_lo"])
                    self.assertFalse(r["clears_zero"])

    def test_missing_is_its_own_cohort(self):
        """A candidate with no reading lands in NONE, never folded into a
        state it was never observed in."""
        cands = [{"confirmed_at": 1000, "r": 1.0,
                  "payload": {"symbol": "BTCUSDT", "tf": "1H",
                              "direction": "LONG"}}]
        n = factorgrade.annotate(self.con, cands, _spec("squeeze"),
                                 window_bars=10)
        self.assertEqual(n, 0)
        self.assertNotIn("squeeze", cands[0]["payload"])

    def test_clear_removes_every_factor_key(self):
        """The report grades nine factors over ONE candidate list; a stale key
        would silently grade the previous factor's answer."""
        names = [s["name"] for s in factorgrade.FACTORS]
        c = {"payload": {n: "X" for n in names}}
        factorgrade._clear([c], names)
        self.assertEqual(c["payload"], {})


if __name__ == "__main__":
    unittest.main()
