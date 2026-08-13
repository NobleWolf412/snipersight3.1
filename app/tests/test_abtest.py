"""2x2 replay harness — the properties that make its verdict believable.

The harness decides what ships. Its own correctness is therefore load-bearing,
and the tests below pin the things that would silently invalidate a verdict:
calibration honesty, no lookahead, the ambiguous-bar convention, the antagonism
check that caught the real result — and that the harness prices an ENTRY the
way production prices one.

That last one is here because the harness has now drifted from `execsim.py`
four times by keeping a copy of something: the exit-fee convention, then
funding, then the crossing fill (+0.1207 R/trade on 76 of 497 trades), then the
model AROUND the crossing fill once the price itself had been shared — which
bar to cross on, which maker limit to rest, which risk denominator to divide by.
`calibrate()` reported every one of them and could locate none, because
comparing sum_r to sum_r never can.
"""
import json
import sqlite3
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import abtest, costs, execsim, store, venues  # noqa: E402
from engine.universe import all_tracked_symbols   # noqa: E402


def tradeable_symbols(con) -> list[str]:
    """The tracked set, minus the reference series.

    `all_tracked_symbols` is "everything with stored candles", and since the
    reference feed (venues.REFERENCE) that includes '@'-keys like
    BICOUSDT@binance-spot. Those carry a deep venue's price series for
    analysis and deliberately have NO venue: `venues.venue_for` raises on
    them, and that raise is the contract keeping a borrowed order book away
    from anything that sizes money.

    Calibration prices trades, so it reaches costs.profile_for and through it
    that raise. Filtering here rather than loosening the raise is the point —
    the enforcement should stay absolute, and it is the caller's job to not
    ask what a reference series would fill at.
    """
    return [s for s in all_tracked_symbols(con) if not venues.is_reference_key(s)]


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

    def test_degraded_fill_warning_survives_the_summary(self):
        s = abtest.summarise([
            {"filled": True, "r": Decimal("0.5"), "same_bar": False,
             "bars_held": 2, "outcome": "TIMEOUT", "partials": [],
             "warnings": ["cross slippage NOT applied"]}])
        self.assertEqual(s["warnings"], ["cross slippage NOT applied"])

    def test_standalone_report_surfaces_each_degraded_replay_cell(self):
        result = {"filled": True, "r": Decimal("0.5"), "same_bar": False,
                  "bars_held": 2, "outcome": "TIMEOUT", "partials": [],
                  "warnings": ["cross slippage NOT applied"]}
        with patch.object(abtest, "calibrate",
                          return_value={"trustworthy": False}), \
             patch.object(abtest, "run_variant", return_value=[result]):
            report = abtest.report(object(), symbols=["TESTUSDT"], tfs=("1H",))
        self.assertEqual(len(report["replay_degradations"]), len(abtest.CELLS))
        self.assertTrue(all(
            item["note"] == "cross slippage NOT applied"
            for item in report["replay_degradations"]))

    def test_calibration_surfaces_degraded_replay_fills(self):
        sid = "TESTUSDT|1H|PULLBACK|setup-v0.19-draft"
        fact = {"payload": json.dumps({
            "setup_id": sid, "strategy": "PULLBACK", "outcome": "TP",
            "r_multiple": "0.5"})}
        replay = {"setup_id": sid, "symbol": "TESTUSDT", "tf": "1H",
                  "filled": True, "r": Decimal("0.5"), "same_bar": False,
                  "bars_held": 2, "outcome": "TP", "partials": [],
                  "warnings": ["cross slippage NOT applied"]}
        with patch.object(abtest.store, "get_facts", return_value=[fact]), \
             patch.object(abtest, "run_variant", return_value=[replay]):
            cal = abtest.calibrate(object(), ["TESTUSDT"], ("1H",))
        self.assertEqual(cal["status"], "OK")
        self.assertEqual(cal["replay_degradations"],
                         ["cross slippage NOT applied"])


class EntryModelAuthority(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)

    def tearDown(self):
        self.con.close()

    def _setup(self, sid, model="ABSENT", state="VALIDATED"):
        payload = {"setup_id": sid, "state": state, "strategy": "TEST",
                   "direction": "LONG", "entry": "100", "sl": "90",
                   "tp": "120"}
        if model != "ABSENT":
            payload["entry_model"] = model
        store.insert_fact(self.con, symbol="TESTUSDT", tf="1H", kind="setup",
                          market_time=0, confirmed_at=3600,
                          algo_version="setup-test", payload=payload)

    def test_missing_model_means_the_recorded_direct_limit_path(self):
        self._setup("direct")
        self.assertIsNone(abtest.recorded_entry_model(
            self.con, ["TESTUSDT"], ["1H"], "setup-test"))

    def test_forming_rows_without_a_model_do_not_conflict_with_final_plans(self):
        self._setup("forming", state="FORMING")
        self._setup("final", "MAKER_THEN_MARKET")
        self.assertEqual(abtest.recorded_entry_model(
            self.con, ["TESTUSDT"], ["1H"], "setup-test"),
            "MAKER_THEN_MARKET")

    def test_mixed_models_refuse_instead_of_selecting_one(self):
        self._setup("direct")
        self._setup("maker", "MAKER_THEN_MARKET")
        with self.assertRaisesRegex(ValueError, "multiple entry models"):
            abtest.recorded_entry_model(
                self.con, ["TESTUSDT"], ["1H"], "setup-test")


class OneFillModel(unittest.TestCase):
    """The whole fill model is the engine's, not just the crossing price."""

    def test_a_crossed_order_is_priced_on_the_bar_it_crossed_on(self):
        """The passive limit rests below every low so it can never fill; the
        engine crosses once the window closes, at THAT bar's open. The old copy
        crossed immediately at the plan's price — 4 points better here, against
        a risk denominator 40% too small, so one mistake inflated R twice."""
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

    def test_a_missing_atr_on_the_cross_degrades_audibly(self):
        """`cross_fill` returns a `slipped` flag and abtest discarded it
        (`entry_px, _ =`), so a fill with no ATR was silent in the harness and
        loud in the engine. The note now rides on the fill itself, which is the
        only way both callers can be made to surface it."""
        c = _bars([(100, 101, 99, 100)] * 2 + [(104, 105, 103, 104)] * 6)
        fill = execsim.simulate_entry(
            c, [None] * 8, 0, Decimal(100), Decimal(90), True,
            entry_model="MAKER_THEN_MARKET", maker_limit=Decimal(80),
            maker_wait=2, profile=PROFILE)
        self.assertIn("NOT applied", fill["note"] or "",
                      "a degraded fill must announce itself to every caller")


class CalibrationAgainstTheLiveStore(unittest.TestCase):
    """THE pin: the harness reproduces the book production actually wrote,
    trade by trade, on the real store.

    Everything else in this file is constructed. This one is not, and it is the
    only test that would have caught the drift, because the drift needed a real
    book to show up in: a crossing leg only differs from the plan when price
    moved between the order and the cross, which no hand-built fixture is
    obliged to contain.

    It asserts three things, and they fail for three different reasons:
      · `diverged_n` — the two price the same trade differently. A simulation
        difference. This is what the fill-model fork caused.
      · `unmatched_*` — one side holds trades the other cannot see. A
        POPULATION difference, which no per-trade comparison can find because
        there is nothing to compare.
      · coverage — the book still contains crossed orders at all. Without it
        this goes quietly green the day the entry model stops crossing, while
        claiming to pin the thing only crossing exercises.

    Skips on a clean checkout so the suite still runs without a store. Note
    that means a git WORKTREE skips it entirely — app/data is gitignored, so
    green here proves nothing until it is run against the real book.
    """

    @classmethod
    def setUpClass(cls):
        if not (APP / "data" / "snipersight.db").exists():
            raise unittest.SkipTest("no live store")
        cls.con = store.connect()
        cls.cal = abtest.calibrate(cls.con, tradeable_symbols(cls.con), TFS)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "con"):
            cls.con.close()

    def _cal(self):
        if self.cal["status"] == "UNAVAILABLE":
            self.skipTest(f"{execsim.EXEC_VERSION}: {self.cal['detail']}")
        return self.cal

    def test_every_recorded_trade_is_reproduced_to_the_cent(self):
        cal = self._cal()
        self.assertGreater(cal["matched"], 0,
                           "nothing joined — the pin would pass vacuously")
        self.assertEqual(cal["diverged_n"], 0,
                         f"the replay and the engine settled "
                         f"{cal['diverged_n']} of {cal['matched']} shared "
                         f"trades for different money (worst "
                         f"{cal['worst_trade_diff_r']:+} R): "
                         f"{cal['examples'][:3]}")

    def test_the_replay_and_the_record_hold_the_same_trades(self):
        cal = self._cal()
        self.assertEqual(
            (cal["unmatched_recorded"], cal["unmatched_replayed"]), (0, 0),
            f"{cal['unmatched_recorded']} recorded trades the replay never "
            f"produced and {cal['unmatched_replayed']} replayed trades the "
            f"record does not contain — the harness is grading a different "
            f"book than the one production traded: {cal['examples'][:3]}")

    def test_the_harness_says_it_is_trustworthy(self):
        self.assertTrue(self._cal()["trustworthy"], self.cal["detail"])

    def test_the_scale_in_adds_are_actually_graded_somewhere(self):
        """calibrate() sets the adds aside on the promise that they are graded
        by replaying SCALE_VERSION. That promise was not being kept.

        `run_variant`'s maker branch keyed the fill bar on `confirmed_bar_ts`,
        which scale plans do not carry (they are adds to a parent, not their own
        confirmed setup), so every one of them hit `ci is None` and was dropped
        without a word. The adds were excluded from calibration AND absent from
        the by-strategy grade — set aside into nothing. Ordering the fill from
        `confirmed_at`, as execsim does, is what makes them replayable at all.

        So: whatever calibrate() sets aside must come back somewhere, and at
        the R the engine recorded.
        """
        cal = self._cal()
        if not cal["scale_in_set_aside"]:
            self.skipTest("no scale-in adds in the recorded book")
        from engine.scalein import SCALE_VERSION
        recorded = {}
        for symbol in tradeable_symbols(self.con):
            for tf in TFS:
                for r in store.get_facts(self.con, symbol, tf, "exec",
                                         execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
                    if (p.get("strategy") == "SCALE_IN"
                            and p["outcome"] != "MISSED"):
                        recorded[p["setup_id"]] = p
        symbols = tradeable_symbols(self.con)
        model = abtest.recorded_entry_model(
            self.con, symbols, TFS, SCALE_VERSION)
        replayed = {r["setup_id"]: r for r in abtest.run_variant(
            self.con, symbols, TFS, SCALE_VERSION,
            managed=False, entry_model=model) if r.get("filled")}
        self.assertEqual(len(recorded), cal["scale_in_set_aside"])
        for sid, p in recorded.items():
            got = replayed.get(sid)
            self.assertIsNotNone(
                got, f"{sid} was set aside by calibration and never replayed — "
                     f"it is graded nowhere")
            self.assertEqual(str(got["r"]), p["r_multiple"],
                             f"{sid}: the add replays to a different R than the "
                             f"engine recorded")

    def test_the_book_still_exercises_the_crossing_leg(self):
        """Coverage, asserted rather than assumed. The maker fills agreed all
        along; only the crossed orders ever diverged. A book with no crosses
        would pin nothing while reporting success."""
        crossed = filled = 0
        for symbol in tradeable_symbols(self.con):
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
            f"all {filled} recorded trades filled passively, so the pins above "
            f"cover only the leg that never disagreed. The crossing leg is the "
            f"one that drifted; if the entry model no longer crosses, say so "
            f"deliberately rather than letting this pin go quiet.")


if __name__ == "__main__":
    unittest.main()
