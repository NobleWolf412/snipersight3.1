"""2x2 replay harness — the properties that make its verdict believable.

The harness decides what ships. Its own correctness is therefore load-bearing,
and the tests below pin the things that would silently invalidate a verdict:
calibration honesty, no lookahead, the ambiguous-bar convention, the antagonism
check that caught the real result — and, since 2026-08-04, that the harness
prices an ENTRY the way production prices one.

That last one is here because it was the third time the harness drifted from
`execsim.py` by keeping a copy of something. The exit-fee convention drifted,
then funding, then the fill model: the harness never received the exec-v0.14
correction that stopped the crossing leg filling at the plan's price two bars
stale, so 76 of 497 replayed trades disagreed with the book by +0.1207 R each,
all of it flattering the replay. `calibrate()` reported the disagreement and
could not locate it, because comparing sum_r to sum_r never can.
"""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import abtest, costs, execsim, store  # noqa: E402
from engine.universe import all_tracked_symbols   # noqa: E402

TFS = ("15m", "1H", "4H", "1D", "1W")


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


class OneFillModel(unittest.TestCase):
    """The harness must not own an entry model. Structural, not behavioural:
    two implementations that agree today are two implementations."""

    def test_the_replay_routes_entries_through_the_engine(self):
        """A fill loop of its own is the shape the defect had. Scanning bars for
        a touch — `Decimal(candles[k]["low"])` and friends — is that loop's
        signature, and run_variant must not contain one: it hands the bars to
        the engine and takes back a fill."""
        src = (APP / "engine" / "abtest.py").read_text(encoding="utf-8")
        body = src[src.index("def run_variant("):src.index("def summarise(")]
        self.assertIn("execsim.simulate_entry(", body,
                      "the replay must fill orders with the engine's fill model")
        self.assertNotIn("Decimal(candles[", body,
                         "run_variant is scanning bars for a fill again — a "
                         "second fill model is how it lost the exec-v0.14 "
                         "cross correction the first time")

    def test_a_crossed_order_is_priced_on_the_bar_it_crossed_on(self):
        """The defect itself, at unit level. The passive limit rests below every
        low so it can never fill; the engine crosses once the window closes, at
        THAT bar's open. The old copy crossed immediately at the plan's price —
        which here is 4 points better and sits against a risk denominator 40%
        too small, inflating R twice over from one mistake.
        """
        c = _bars([(100, 101, 99, 100), (100, 101, 99, 100),
                   (104, 105, 103, 104)] + [(104, 105, 103, 104)] * 5)
        atr = [None] * 8
        fill = execsim.simulate_entry(
            c, atr, 0, Decimal(100), Decimal(90), True,
            entry_model="MAKER_THEN_MARKET", maker_limit=Decimal(80),
            maker_wait=2, profile=PROFILE)
        self.assertEqual(fill["status"], "FILLED")
        self.assertEqual(fill["fill_i"], 2, "the cross fires after the window")
        self.assertEqual(fill["entry"], Decimal(104),
                         "a market order fills at the market, not at the plan")
        self.assertEqual(fill["entry_role"], "TAKER", "crossing pays taker")
        self.assertEqual(fill["risk"], Decimal(14),
                         "risk is measured from the FILL to the same structural "
                         "stop — 104-90, not the plan's 100-90")


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


class CalibrationAgainstTheLiveStore(unittest.TestCase):
    """THE pin: the harness reproduces the book production actually wrote,
    trade by trade, on the real store.

    Everything else in this file is constructed. This one is not, and it is the
    only test that would have caught the drift, because the drift needed a real
    book to show up in: a crossing leg only differs from the plan when price
    moved between the order and the cross, which no hand-built fixture is
    obliged to contain.

    It asserts three separate things, and they fail for three different reasons:
      · `diverged_n` — the two price the same trade differently. A simulation
        difference. This is what the fill-model fork caused.
      · `unmatched_*` — one side is looking at trades the other cannot see. An
        INPUT-SET difference, which no per-trade comparison can find because
        there is nothing to compare. This is what loading only the setup
        generation caused, hiding 2 scale-in adds.
      · coverage — the book still contains crossed orders at all. Without it
        this test goes quietly green the day the entry model stops crossing,
        while claiming to pin the thing that only crossing exercises.

    Skips on a clean checkout so the suite still runs without a store.
    """

    @classmethod
    def setUpClass(cls):
        if not (APP / "data" / "snipersight.db").exists():
            raise unittest.SkipTest("no live store")
        cls.con = store.connect()
        symbols = all_tracked_symbols(cls.con)
        cls.cal = abtest.calibrate(cls.con, symbols, TFS)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "con"):
            cls.con.close()

    def test_every_recorded_trade_is_reproduced_to_the_cent(self):
        cal = self.cal
        if cal["status"] == "UNAVAILABLE":
            self.skipTest(f"{execsim.EXEC_VERSION}: {cal['detail']}")
        self.assertGreater(cal["matched"], 0,
                           "nothing joined — the pin would pass vacuously")
        self.assertEqual(cal["diverged_n"], 0,
                         f"the replay and the engine settled "
                         f"{cal['diverged_n']} of {cal['matched']} shared "
                         f"trades for different money (worst "
                         f"{cal['worst_trade_diff_r']:+} R): "
                         f"{cal['examples'][:3]}")

    def test_the_replay_and_the_record_hold_the_same_trades(self):
        cal = self.cal
        if cal["status"] == "UNAVAILABLE":
            self.skipTest(f"{execsim.EXEC_VERSION}: {cal['detail']}")
        self.assertEqual(
            (cal["unmatched_recorded"], cal["unmatched_replayed"]), (0, 0),
            f"{cal['unmatched_recorded']} recorded trades the replay never "
            f"loaded and {cal['unmatched_replayed']} replayed trades the record "
            f"does not contain — the harness is grading a different book than "
            f"the one production traded: {cal['examples'][:3]}")

    def test_the_harness_says_it_is_trustworthy(self):
        cal = self.cal
        if cal["status"] == "UNAVAILABLE":
            self.skipTest(f"{execsim.EXEC_VERSION}: {cal['detail']}")
        self.assertTrue(cal["trustworthy"], cal["detail"])

    def test_the_book_still_exercises_the_crossing_leg(self):
        """Coverage, asserted rather than assumed. The maker fills agreed all
        along; only the 76 crossed orders ever diverged. A book with no crosses
        would pin nothing while reporting success."""
        crossed = filled = 0
        for symbol in all_tracked_symbols(self.con):
            for tf in TFS:
                for r in store.get_facts(self.con, symbol, tf, "exec",
                                         execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
                    if p["outcome"] == "MISSED":
                        continue
                    filled += 1
                    if p.get("entry_fee_role") == "TAKER":
                        crossed += 1
        if not filled:
            self.skipTest(f"no {execsim.EXEC_VERSION} facts yet — re-run the "
                          f"simulator to populate them")
        self.assertGreater(
            crossed, 0,
            f"all {filled} recorded trades filled passively, so the agreement "
            f"pins above cover only the leg that never disagreed. The crossing "
            f"leg is the one that drifted; if the entry model no longer crosses, "
            f"say so deliberately rather than letting this pin go quiet.")


if __name__ == "__main__":
    unittest.main()
