"""Deterministic synthetic-series tests for the nested-cycle satellite.
No network, no database — pure functions only.
Run: python -m unittest tests.test_nested_cycles -v
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import cycles  # noqa: E402

DAY = 86400
T0 = int(datetime(2022, 11, 21, tzinfo=timezone.utc).timestamp())  # seed low


def series(n_days, low_days, base=100.0, top_days=None):
    """Synthetic daily candles: flat drift with planted V-lows and optional tops.
    Planted lows dip to base-10 (neighbors base-2); tops spike to base+10."""
    out = []
    for d in range(n_days):
        o = h = c = base
        lo = base - 1
        if d in low_days:
            lo = base - 10
        elif any(abs(d - ld) <= cycles.FRACTAL_W for ld in low_days):
            lo = base - 2
        if top_days and d in top_days:
            h = base + 10
        out.append({"open_ts": T0 + d * DAY, "open": str(o), "high": str(h),
                    "low": str(lo), "close": str(c), "volume": "1"})
    return out


class TestDCLDetection(unittest.TestCase):
    def test_finds_planted_lows_inside_band(self):
        cnd = series(200, low_days=[0, 60, 120, 180])
        lows, inv = cycles.detect_lows(cnd, T0, cycles.DCL_BAND_DAYS)
        self.assertEqual([(l["ts"] - T0) // DAY for l in lows], [0, 60, 120, 180])
        self.assertEqual(inv, [])

    def test_ignores_lows_outside_band(self):
        # planted low at day 30 (before band) must NOT become the DCL; day 60 must
        cnd = series(100, low_days=[0, 30, 60])
        lows, _ = cycles.detect_lows(cnd, T0, cycles.DCL_BAND_DAYS)
        self.assertEqual([(l["ts"] - T0) // DAY for l in lows], [0, 60])


class TestTranslation(unittest.TestCase):
    def _one_cycle(self, top_day):
        cnd = series(70, low_days=[0, 60], top_days=[top_day])
        lows, _ = cycles.detect_lows(cnd, T0, cycles.DCL_BAND_DAYS)
        return cycles.classify_cycles(cnd, lows)[0]

    def test_left_mid_right(self):
        self.assertEqual(self._one_cycle(12)["translation"], "left")
        self.assertEqual(self._one_cycle(30)["translation"], "mid")
        self.assertEqual(self._one_cycle(48)["translation"], "right")

    def test_fraction_reported(self):
        c = self._one_cycle(30)
        self.assertAlmostEqual(c["fraction"], 0.5, places=2)


class TestFailedCycle(unittest.TestCase):
    def test_failed_flag(self):
        # cycle 1 top at 105; cycle 2 closes below its own start-low before
        # ever exceeding 105 -> failed
        cnd = series(130, low_days=[0, 60, 120], top_days=[30])
        for d in range(70, 80):          # close below cycle-2 start low (90)
            cnd[d]["close"] = "85"
            cnd[d]["low"] = "84"
        lows, _ = cycles.detect_lows(cnd, T0, cycles.DCL_BAND_DAYS)
        cyc = cycles.classify_cycles(cnd, lows)
        self.assertTrue(cyc[1]["failed"])

    def test_not_failed_when_high_first(self):
        cnd = series(130, low_days=[0, 60, 120], top_days=[30, 65])
        cnd[65]["high"] = "120"          # exceeds prior top before any breakdown
        lows, _ = cycles.detect_lows(cnd, T0, cycles.DCL_BAND_DAYS)
        cyc = cycles.classify_cycles(cnd, lows)
        self.assertFalse(cyc[1]["failed"])


class TestInversion(unittest.TestCase):
    def test_inversion_flag_and_counts(self):
        # no low in the 54-66d band; next low arrives day 90 (late)
        cnd = series(160, low_days=[0, 90, 150])
        lows, inv = cycles.detect_lows(cnd, T0, cycles.DCL_BAND_DAYS)
        self.assertEqual(len(inv), 1)
        self.assertTrue(any(l["late"] for l in lows))
        s = cycles.summarize(cnd, cnd[-1]["open_ts"])
        self.assertEqual(s["daily"]["inverted_count"],
                         s["daily"]["primary_count"] + 1)


class TestNesting(unittest.TestCase):
    def test_three_to_one(self):
        # DCLs every 60d for ~2 years; WCLs should land every ~180d (3 DCLs)
        cnd = series(740, low_days=list(range(0, 740, 60)))
        s = cycles.summarize(cnd, cnd[-1]["open_ts"])
        nest_sizes = [len(n) for n in s["weekly"]["nest"]]
        self.assertTrue(nest_sizes, "no weekly nests recovered")
        for size in nest_sizes:
            self.assertEqual(size, 3)


class TestWindows(unittest.TestCase):
    def test_low_to_low_brackets_nov_2022(self):
        # self-consistency: 2018-12-15 + 44..52 months must bracket 2022-11-21
        from datetime import date
        prior = date.fromisoformat("2018-12-15")
        lo = cycles.add_months(prior, cycles.FY_LOW_TO_LOW_MONTHS[0])
        hi = cycles.add_months(prior, cycles.FY_LOW_TO_LOW_MONTHS[1])
        self.assertTrue(lo <= date.fromisoformat("2022-11-21") <= hi)

    def test_halving_anchor_brackets_nov_2022(self):
        from datetime import date
        h = date.fromisoformat("2024-04-19")
        lo = cycles.add_months(h, -cycles.HALVING_LOW_OFFSET_MONTHS[0])
        hi = cycles.add_months(h, -cycles.HALVING_LOW_OFFSET_MONTHS[1])
        self.assertTrue(lo <= date.fromisoformat("2022-11-21") <= hi)

    def test_pushout_only_when_right_translated(self):
        from datetime import date
        w_off = cycles.four_year_windows(False)
        w_on = cycles.four_year_windows(True)
        self.assertIsNone(w_off["pushout_extended_window"])
        ext = w_on["pushout_extended_window"]
        self.assertIsNotNone(ext)
        delta = (date.fromisoformat(ext["end"])
                 - date.fromisoformat(w_on["low_to_low"]["end"])).days
        self.assertEqual(delta, cycles.PUSHOUT_DAYS)
        self.assertIn("n~=2", ext["note"])

    def test_windows_never_merged(self):
        w = cycles.four_year_windows(True)
        self.assertNotEqual(w["low_to_low"], w["halving_anchored"])

    def test_4y_translation_pushout_variant(self):
        # right-translated 4Y (fraction > 0.6) fires the 4Y variant regardless
        # of the weekly variant; left 4Y does not
        w = cycles.four_year_windows(False, fy_top_fraction=0.72)
        self.assertIsNone(w["pushout_extended_window"])
        self.assertIsNotNone(w["pushout_extended_window_4y"])
        self.assertIn("4Y-TRANSLATION", w["pushout_extended_window_4y"]["note"])
        w2 = cycles.four_year_windows(False, fy_top_fraction=0.35)
        self.assertIsNone(w2["pushout_extended_window_4y"])


class TestContractHonesty(unittest.TestCase):
    def test_payload_flags(self):
        import json
        cnd = series(200, low_days=[0, 60, 120, 180])
        s = cycles.summarize(cnd, cnd[-1]["open_ts"])
        json.dumps(s)                    # JSON-safe
        self.assertTrue(s["observational"])
        self.assertTrue(len(s["note"]) > 20)
        self.assertNotIn("peak", json.dumps(s).lower())  # no top forecasts

    def test_fail_soft(self):
        s = cycles.summarize([], 0)
        self.assertEqual(s["source"], "unavailable")
        self.assertTrue(s["observational"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
