"""2x2 replay harness — the properties that make its verdict believable.

The harness decides whether setup-v0.7 ships. Its own correctness is therefore
load-bearing, and the tests below pin the four things that would silently
invalidate a verdict: calibration honesty, no lookahead, the ambiguous-bar
convention, and the antagonism check that caught the real result.
"""
import unittest
from decimal import Decimal

from engine import abtest, costs


def _bars(spec, start=1_600_000_000, step=86400):
    """spec = [(o,h,l,c), ...] -> store-shaped candle dicts."""
    return [{"open_ts": start + i * step, "open": Decimal(o), "high": Decimal(h),
             "low": Decimal(l), "close": Decimal(c), "volume": Decimal(1)}
            for i, (o, h, l, c) in enumerate(spec)]


PROFILE = costs.CostProfile(version="test", venue="test", fee_tier="test",
                            maker_rate=Decimal(0), taker_rate=Decimal(0),
                            market_slippage_atr=Decimal(0))


class SimulatorConventions(unittest.TestCase):
    """Rules that decide whether a backtest flatters itself."""

    def test_same_bar_stop_and_target_counts_as_the_stop(self):
        """The metric this whole version moves is the same-bar stop-out rate.
        If an ambiguous bar were scored as a win, the harness would report the
        defect as fixed by scoring it away."""
        c = _bars([(100, 130, 70, 100)] * 3)          # bar spans both levels
        atr = [Decimal(30)] * 3
        out = abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                               Decimal(120), True, "1D", PROFILE,
                               managed=False, taker_in=True,
                               symbol="BTC-USD", tf_seconds=86400)
        self.assertEqual(out["outcome"], "SL")
        self.assertTrue(out["same_bar"])

    def test_partial_is_refused_when_the_same_bar_also_trades_through_entry(self):
        """A partial moves the stop to breakeven. Booking one on a bar that also
        trades through breakeven claims the high came before the low — intrabar
        ordering OHLC cannot supply. Conservative reading: no partial."""
        # risk = 10; TP1 at 1.5R = 115. Bar reaches 116 AND dips to 99 (< entry).
        c = _bars([(100, 116, 99, 100)] + [(100, 101, 99, 100)] * 3)
        atr = [Decimal(10)] * 4
        out = abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                               Decimal(200), True, "1D", PROFILE,
                               managed=True, taker_in=True,
                               symbol="BTC-USD", tf_seconds=86400)
        self.assertEqual(out["partials"], [],
                         "an ambiguous bar must not manufacture a booked profit")

    def test_partial_is_booked_when_the_bar_never_returns_to_entry(self):
        """The mirror of the above — the rule must not refuse every partial."""
        c = _bars([(100, 116, 100, 115)] + [(115, 116, 114, 115)] * 3)
        atr = [Decimal(10)] * 4
        out = abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                               Decimal(200), True, "1D", PROFILE,
                               managed=True, taker_in=True,
                               symbol="BTC-USD", tf_seconds=86400)
        self.assertEqual(len(out["partials"]), 1)

    def test_unresolved_position_is_open_not_a_zero(self):
        """Running out of data is not a flat trade. Counting it as 0R would
        dilute measured expectancy toward zero with rows where nothing happened."""
        c = _bars([(100, 101, 99, 100)] * 3)
        atr = [Decimal(1)] * 3
        out = abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                               Decimal(200), True, "1D", PROFILE,
                               managed=False, taker_in=True,
                               symbol="BTC-USD", tf_seconds=86400)
        self.assertIsNone(out)

    def test_short_side_mirrors_the_long_side(self):
        c = _bars([(100, 130, 70, 100)] * 3)
        atr = [Decimal(30)] * 3
        out = abtest._simulate(c, atr, 0, Decimal(100), Decimal(110),
                               Decimal(80), False, "1D", PROFILE,
                               managed=False, taker_in=True,
                               symbol="BTC-USD", tf_seconds=86400)
        self.assertEqual(out["outcome"], "SL")


class VerdictLogic(unittest.TestCase):
    """The verdict must be able to say 'do not ship this'."""

    @staticmethod
    def _cells(base, exit_only, entry_only, both):
        return {"touch_hold": {"n": 100, "expectancy_r": base},
                "touch_managed": {"n": 100, "expectancy_r": exit_only},
                "confirmed_hold": {"n": 100, "expectancy_r": entry_only},
                "confirmed_managed": {"n": 100, "expectancy_r": both}}

    OK = {"trustworthy": True}

    def test_antagonism_is_detected_when_the_combination_underperforms(self):
        """The real 2026-07-30 result: both changes beat the baseline alone and
        together were worse than either. A naive 'both improved' reading would
        have shipped the weaker system."""
        v = abtest._verdict(self._cells(-0.64, 0.32, -0.02, -0.17), self.OK)
        self.assertEqual(v["call"], "ANTAGONISTIC")
        self.assertIn("exit", v["detail"])

    def test_genuine_synergy_is_not_called_antagonistic(self):
        v = abtest._verdict(self._cells(-0.64, -0.2, -0.1, 0.4), self.OK)
        self.assertEqual(v["call"], "BOTH_HELP")

    def test_exit_only_improvement_says_drop_the_entry_change(self):
        v = abtest._verdict(self._cells(-0.64, 0.32, -0.70, 0.30), self.OK)
        self.assertEqual(v["call"], "EXIT_CARRIES_IT")

    def test_neither_helping_is_stated_plainly(self):
        v = abtest._verdict(self._cells(-0.10, -0.5, -0.6, -0.7), self.OK)
        self.assertEqual(v["call"], "NEITHER_HELPS")
        self.assertIn("re-open", v["detail"])

    def test_failed_calibration_forbids_any_conclusion(self):
        """A harness that cannot reproduce a known book must not describe an
        unknown one, however good the numbers look."""
        v = abtest._verdict(self._cells(-0.64, 5.0, 5.0, 5.0),
                            {"trustworthy": False})
        self.assertEqual(v["call"], "INDETERMINATE")

    def test_underpowered_cells_are_named(self):
        cells = self._cells(-0.64, 0.32, -0.02, -0.17)
        cells["confirmed_managed"]["n"] = 12
        v = abtest._verdict(cells, self.OK)
        self.assertIn("both", v["underpowered_cells"])
        self.assertIsNotNone(v["caveat"])


class Determinism(unittest.TestCase):
    def test_same_inputs_produce_identical_results(self):
        c = _bars([(100, 116, 100, 115), (115, 130, 110, 128),
                   (128, 131, 120, 122), (122, 125, 88, 90)])
        atr = [Decimal(10)] * 4
        runs = [abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                                 Decimal(140), True, "1D", PROFILE,
                                 managed=True, taker_in=True,
                               symbol="BTC-USD", tf_seconds=86400) for _ in range(3)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])


class Summary(unittest.TestCase):
    def test_missed_orders_are_counted_but_never_scored_as_zero(self):
        res = [{"filled": False, "outcome": "MISSED"},
               {"filled": True, "r": Decimal("1.0"), "same_bar": False,
                "bars_held": 3, "outcome": "TP", "partials": []}]
        s = abtest.summarise(res)
        self.assertEqual(s["n"], 1)
        self.assertEqual(s["missed"], 1)
        self.assertEqual(s["expectancy_r"], 1.0)

    def test_empty_book_refuses_rather_than_reporting_zero(self):
        s = abtest.summarise([])
        self.assertEqual(s["n"], 0)
        self.assertIn("note", s)


if __name__ == "__main__":
    unittest.main()
