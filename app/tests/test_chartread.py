"""The chart read (engine/chartread.py): the regime a trader sees in the
window a chart opens with. Pinned on hand-built bars, because the read is
what a playbook will one day be allowed to condition on, and a read whose
branches were never pinned is a read that drifts.

The property above all: it sees only CLOSED bars and calls a pivot only once
FRACTAL_WING bars have closed after it — three bars slower than the eye, and
never a bar ahead of it.
"""
import pathlib
import re
import unittest
from decimal import Decimal

from engine import chartread as cr


def _bars(highs, lows, start=0, step=3600):
    out = []
    for i, (h, l) in enumerate(zip(highs, lows)):
        c = (Decimal(h) + Decimal(l)) / 2
        out.append({"open_ts": start + i * step, "open": str(c), "high": str(h),
                    "low": str(l), "close": str(c), "volume": "1"})
    return out


def _zigzag(levels, wing=3):
    """Bars that make a clean pivot at each level in turn: each level is held
    for one bar, the bars between step linearly, so every peak/trough is a
    fractal with `wing` lower/higher bars on either side."""
    highs, lows = [], []
    for a, b in zip(levels, levels[1:]):
        for k in range(wing + 1):
            v = Decimal(a) + (Decimal(b) - Decimal(a)) * k / (wing + 1)
            highs.append(v + 1)
            lows.append(v - 1)
    highs.append(Decimal(levels[-1]) + 1)
    lows.append(Decimal(levels[-1]) - 1)
    return _bars(highs, lows)


class Pivots(unittest.TestCase):
    def test_alternating_fractals(self):
        bars = _zigzag([100, 110, 105, 115, 108, 120, 112])
        pv = cr.pivots(bars)
        types = [p["type"] for p in pv]
        # the first level sits at the window's edge with no left wing, so the
        # first knowable pivot is the HIGH after it — the eye would call the
        # edge a low; the reader, honestly, cannot
        self.assertEqual(types[:5], ["HIGH", "LOW", "HIGH", "LOW", "HIGH"])
        self.assertEqual([str(p["price"]) for p in pv if p["type"] == "HIGH"][:3],
                         ["111", "116", "121"])

    def test_a_pivot_is_knowable_only_after_the_wing_closes(self):
        bars = _zigzag([100, 110, 100])
        pv = cr.pivots(bars)
        hi = next(p for p in pv if p["type"] == "HIGH")
        self.assertEqual(hi["known_i"], hi["i"] + cr.FRACTAL_WING)


class ReadWindow(unittest.TestCase):
    def test_higher_highs_and_higher_lows_is_up(self):
        r = cr.read_window(_zigzag([100, 110, 104, 116, 109, 122, 114]), Decimal("2"))
        self.assertEqual(r["read"], "UP")
        self.assertTrue(r["hh"] and r["hl"])

    def test_lower_highs_and_lower_lows_is_down(self):
        r = cr.read_window(_zigzag([130, 118, 125, 112, 120, 105, 113]), Decimal("2"))
        self.assertEqual(r["read"], "DOWN")

    def test_two_lines_you_could_draw_is_range(self):
        r = cr.read_window(_zigzag([100, 110, 100, 110, 100, 110, 100]), Decimal("2"))
        self.assertEqual(r["read"], "RANGE")
        self.assertEqual(len(r["resistance"]), 1)
        self.assertEqual(r["resistance"][0]["touches"], 3)
        self.assertEqual(len(r["support"]), 1)

    def test_no_sequence_and_no_lines_is_chop(self):
        r = cr.read_window(_zigzag([100, 112, 96, 104, 90, 118, 102]), Decimal("2"))
        self.assertEqual(r["read"], "CHOP")

    def test_a_trend_with_a_late_retracement_is_still_the_trend(self):
        """The operator's rule and the first pilot's five misses: classify the
        window, not the last leg. Five days up then a deep retrace is UP with
        a DOWN bias — two facts, two fields."""
        r = cr.read_window(_zigzag([100, 110, 104, 116, 109, 122, 103, 112]), Decimal("2"))
        self.assertEqual(r["read"], "UP")
        self.assertNotEqual(r["bias"], "UP", "the last leg is down; the bias must say so")
        r = cr.read_window(_zigzag([130, 118, 125, 112, 120, 105, 124, 114]), Decimal("2"))
        self.assertEqual(r["read"], "DOWN")
        self.assertNotEqual(r["bias"], "DOWN")

    def test_range_is_boundaries_each_touched_twice_with_no_dominant_sequence(self):
        # highs at ~111, lows at ~100, three visits each — two lines, rotation.
        # The extra leg at the end gives the last low its right-hand wing.
        r = cr.read_window(_zigzag([100, 110, 101, 111, 100, 110, 101, 110]), Decimal("2"))
        self.assertEqual(r["read"], "RANGE")
        self.assertGreaterEqual(max(l["touches"] for l in r["resistance"]), 2)
        self.assertGreaterEqual(max(l["touches"] for l in r["support"]), 2)

    def test_a_range_whose_edge_was_broken_and_reversed_is_chop(self):
        """The operator's CHOP, from two blind pilots: "falsely broke out and
        dumped back". Same boundaries, same touches — one excursion that
        closes through the top and is back inside within a few bars, and the
        window is CHOP, not RANGE. The count is on the read."""
        bars = _zigzag([100, 110, 101, 111, 100, 110, 101, 110, 100, 110, 101, 110])
        r = cr.read_window(bars, Decimal("2"))
        self.assertEqual(r["read"], "RANGE")
        self.assertEqual(r["false_breaks"], 0)
        # a false break: right after the first touch of the top, three bars
        # close well through it, then price is back inside within five bars.
        # The other touches of the top survive, so the boundaries still exist —
        # the only thing that changed is that one of them failed to hold.
        broken = [dict(b) for b in bars]
        for k in range(5, 8):
            broken[k] = {**broken[k], "high": "116", "close": "115"}
        r = cr.read_window(broken, Decimal("2"))
        self.assertGreaterEqual(r["false_breaks"], 1)
        self.assertEqual(r["read"], "CHOP")

    def test_small_swings_inside_a_big_move_do_not_count_as_structure(self):
        """The house rule from swings.py: a pivot is a LOCAL swing only if the
        reversal to the next opposite pivot is at least LOCAL_ATR_MULT x ATR.
        Without it, a 1H retracement full of one-ATR wiggles out-votes the
        five-day advance it sits inside (ARB, first pilot)."""
        big = [100, 130, 110, 140, 120, 150]
        wiggles = [128, 126, 128, 126, 128, 126, 128]   # < 0.75 ATR at atr=4
        r = cr.read_window(_zigzag(big + wiggles), Decimal("4"))
        self.assertEqual(r["read"], "UP")

    def test_too_few_pivots_is_unknown_not_a_guess(self):
        r = cr.read_window(_zigzag([100, 110]), Decimal("2"))
        self.assertEqual(r["read"], "UNKNOWN")

    def test_efficiency_is_one_for_a_straight_line_and_small_for_noise(self):
        line = _bars([Decimal(100 + i) for i in range(20)], [Decimal(98 + i) for i in range(20)])
        self.assertEqual(cr.efficiency([Decimal(c["close"]) for c in line]), Decimal(1))
        noise = _zigzag([100, 110, 100, 110, 100, 110, 100])
        self.assertLess(cr.efficiency([Decimal(c["close"]) for c in noise]), Decimal("0.1"))


class Reconcile(unittest.TestCase):
    def test_the_operators_calls(self):
        self.assertEqual(cr.reconcile("UP", "DOWN"), "PULLBACK_IN_HTF_DOWN")
        self.assertEqual(cr.reconcile("DOWN", "UP"), "PULLBACK_IN_HTF_UP")
        self.assertEqual(cr.reconcile("UP", "UP"), "TREND_UP_ALIGNED")
        self.assertEqual(cr.reconcile("CHOP", "UP"), "CONSOLIDATION_IN_HTF_UP")
        self.assertEqual(cr.reconcile("RANGE", "DOWN"), "CONSOLIDATION_IN_HTF_DOWN")
        self.assertEqual(cr.reconcile("UP", "RANGE"), "LTF_TREND_IN_HTF_RANGE")
        self.assertEqual(cr.reconcile("RANGE", "CHOP"), "RANGE")
        self.assertEqual(cr.reconcile("UP", None), "TREND_UP_NO_HTF")
        self.assertEqual(cr.reconcile("UNKNOWN", "UP"), "UNKNOWN")


class AsOf(unittest.TestCase):
    def test_the_window_stops_at_the_last_closed_bar(self):
        bars = _zigzag([100, 110, 104, 116, 109, 122, 114] * 4)
        ch = cr.Chart("1H", 3600, bars)
        mid = bars[50]["open_ts"] + 1800          # inside bar 50, not closed
        start, end = ch.window(mid)
        self.assertEqual(end, 50, "the forming bar must not be in the window")
        self.assertEqual(end - start, min(50, cr.WINDOW_BARS))

    def test_the_window_is_sized_to_the_timeframes_job(self):
        """One number for every timeframe misleads: 120 weekly bars is 2.3
        years, 120 five-minute bars is ten hours. The anchor is shorter, the
        execution context longer, and the rest is the chart's own window."""
        self.assertEqual(cr.window_bars("1W"), 78)
        self.assertEqual(cr.window_bars("5m"), 200)
        for tf in ("15m", "1H", "4H", "1D"):
            self.assertEqual(cr.window_bars(tf), cr.WINDOW_BARS)
        bars = _zigzag([100, 110, 104, 116, 109, 122, 114] * 20)
        weekly = cr.Chart("1W", 604800, bars)
        s, e = weekly.window(bars[-1]["open_ts"] + 604800)
        self.assertEqual(e - s, 78)

    def test_location_and_structure_state_are_composed_not_invented(self):
        r = cr.read_window(_zigzag([100, 110, 104, 116, 109, 122, 103, 112]), Decimal("2"))
        self.assertEqual(r["read"], "UP")
        self.assertEqual(r["structure_state"], "PULLBACK")
        self.assertIn(r["location"], ("DISCOUNT", "EQUILIBRIUM", "PREMIUM"))
        self.assertEqual(cr.structure_state("DOWN", "UP"), "RECOVERY")
        self.assertEqual(cr.structure_state("DOWN", "DOWN"), "CONTINUATION")
        self.assertEqual(cr.structure_state("RANGE", "DOWN"), "ROTATION")
        self.assertEqual(cr.structure_state("UNKNOWN", "UP"), "UNKNOWN")

    def test_the_window_is_the_charts_own(self):
        chart_js = (pathlib.Path(__file__).parents[1] / "static" / "chart.js").read_text(encoding="utf-8")
        m = re.search(r"const VISIBLE_BARS = (\d+);", chart_js)
        self.assertIsNotNone(m, "chart.js no longer declares VISIBLE_BARS")
        self.assertEqual(cr.WINDOW_BARS, int(m.group(1)),
                         "the reader's window and the chart's opening window drifted apart")

    def test_the_level_width_is_a_zones_width(self):
        from engine import zones
        self.assertEqual(cr.LEVEL_ATR, zones.ZONE_ATR)


class HtfLevels(unittest.TestCase):
    def test_nearest_resistance_above_and_support_below_in_own_atr(self):
        htf = {"resistance": [{"price": "120"}, {"price": "140"}],
               "support": [{"price": "90"}, {"price": "80"}]}
        out = cr.nearest_htf_levels(htf, Decimal("100"), Decimal("4"))
        self.assertEqual(out, {"resistance_above": "5.00", "support_below": "2.50"})


if __name__ == "__main__":
    unittest.main()
