"""Moving-average engine tests — the properties that must not regress.

The synthetic series is a LINEAR RAMP with a constant true range, and both
choices are load-bearing rather than convenient.

Constant true range makes ATR exactly 2.00000000, so the slope deadband
(0.25 * ATR) is exactly 0.5 and this file can state it rather than trust it.

The linear ramp makes every average in the ribbon hand-computable in closed
form, which is the only way a test of an average is a test at all. On a ramp of
step s, the simple average of the last n closes is `close - s*(n-1)/2`; and the
EMA's fixed point is `close - s*(1-k)/k` with `k = 2/(n+1)`, which is the SAME
expression. So the SMA seed this engine uses to start each EMA is already the
EMA's own fixed point, the recursion never has to converge, and every value on
the ribbon at every bar is:

    EMA20   = close - 0.5 *  9.5 = close -  4.75
    EMA50   = close - 0.5 * 24.5 = close - 12.25
    SMA200  = close - 0.5 * 99.5 = close - 49.75

The exact-arithmetic assertions live on `sma` and `ema` directly, at period 3
where k = 2/4 = 0.5 and nothing repeats. The engine-level ribbon values are
asserted against the closed form to within one part in a million, because the
real smoothing constants (2/21, 2/51, 2/201) are repeating decimals — that
tolerance is a statement about base-10 arithmetic, not about the engine.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import ma, store

TF = 3600
BASE = Decimal("100")
STEP = Decimal("0.5")
PAD = Decimal("1")
ATR = Decimal("2.00000000")           # constant TR = 2 on every bar
DEADBAND = ma.SLOPE_DEADBAND_ATR * ATR    # 0.5
CLOSED = Decimal("1e-6")              # base-10 tolerance, see module docstring


def ramp(n: int, start: int = 0, base: Decimal = BASE,
         step: Decimal = STEP) -> list[dict]:
    """A straight line in close, padded so the true range is constant."""
    bars, prev = [], None
    for i in range(n):
        close = base + step * i
        bars.append({"open_ts": (start + i) * TF,
                     "open": close if prev is None else prev,
                     "high": close + PAD, "low": close - PAD, "close": close})
        prev = close
    return bars


class MaCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, bars):
        for b in bars:
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1H", b["open_ts"], str(b["open"]), str(b["high"]),
                 str(b["low"]), str(b["close"]), "10", "test", b["open_ts"]))
        self.con.commit()

    def facts(self, as_of=None):
        rows = store.get_facts(self.con, "BTC-USD", "1H", "ma", ma.MA_VERSION,
                               as_of=as_of)
        return [{"market_time": r["market_time"],
                 "confirmed_at": r["confirmed_at"],
                 **json.loads(r["payload"])} for r in rows]

    def value(self, fact, name):
        return Decimal(next(m["value"] for m in fact["ribbon"]
                            if m["name"] == name))


class TestAverages(unittest.TestCase):
    """Hand arithmetic on the two primitives, stated in full."""

    def test_sma_is_the_mean_of_the_last_period_values(self):
        vals = [Decimal(v) for v in ("1", "2", "3", "4", "5")]
        got = ma.sma(vals, 3)
        # (1+2+3)/3 = 2 ; (2+3+4)/3 = 3 ; (3+4+5)/3 = 4
        self.assertEqual(got, [None, None, Decimal(2), Decimal(3), Decimal(4)])

    def test_ema_is_sma_seeded_then_recursive(self):
        vals = [Decimal(v) for v in ("1", "2", "3", "4", "5")]
        # period 3 -> k = 2/(3+1) = 0.5 exactly, so nothing here repeats.
        # seed  = SMA(1,2,3)          = 2
        # i=3   = 2 + 0.5*(4 - 2)     = 3
        # i=4   = 3 + 0.5*(5 - 3)     = 4
        self.assertEqual(ma.ema(vals, 3),
                         [None, None, Decimal(2), Decimal(3), Decimal(4)])

    def test_an_average_refuses_its_own_warmup(self):
        """A 20-period average has no value at bar 5. None, not a partial."""
        vals = [Decimal(i) for i in range(10)]
        self.assertEqual(ma.sma(vals, 20), [None] * 10)
        self.assertEqual(ma.ema(vals, 20), [None] * 10)
        self.assertIsNone(ma.sma(vals, 4)[2])
        self.assertIsNotNone(ma.sma(vals, 4)[3])

    def test_decimal_survives_a_sum_that_floats_get_wrong(self):
        """0.1 + 0.2 + 0.3 is 0.6000000000000001 in binary floating point, and
        a third of that is 0.20000000000000004."""
        vals = [Decimal("0.1"), Decimal("0.2"), Decimal("0.3")]
        self.assertEqual(ma.sma(vals, 3)[2], Decimal("0.2"))
        self.assertEqual(str(ma.sma(vals, 3)[2]), "0.20000000")

    def test_rounding_follows_the_price_not_the_decimal_point(self):
        """`swings.compute_atr` quantizes to 8 DECIMAL PLACES, which leaves a
        sub-dollar token three digits of resolution. 8 SIGNIFICANT digits gives
        BTC and SHIB the same precision."""
        self.assertEqual(ma.sig(Decimal("47733.432198765")), Decimal("47733.432"))
        self.assertEqual(ma.sig(Decimal("0.000034123456789")),
                         Decimal("0.000034123457"))
        self.assertEqual(ma.sig(Decimal(0)), Decimal(0))
        self.assertEqual(ma.sig(Decimal("-1.23456789012")), Decimal("-1.2345679"))

    def test_plain_never_emits_an_exponent(self):
        """A payload that spells one price two ways is two facts to
        `content_hash`, and idempotency dies quietly."""
        self.assertEqual(ma.plain(Decimal("4.773E+4")), "47730")
        self.assertEqual(ma.plain(Decimal("3.41E-5")), "0.0000341")


class TestPredicates(unittest.TestCase):
    def test_stack_needs_real_separation_not_a_hair(self):
        entwined = [Decimal("100.02"), Decimal("100.01"), Decimal(100)]
        clear = [Decimal(110), Decimal(105), Decimal(100)]
        tol = Decimal("0.5")
        self.assertEqual(ma.stack(entwined, tol), "MIXED")
        self.assertEqual(ma.stack(clear, tol), "BULL")
        self.assertEqual(ma.stack(list(reversed(clear)), tol), "BEAR")
        # With no tolerance at all the entwined ribbon reads as a trend.
        self.assertEqual(ma.stack(entwined, Decimal(0)), "BULL")

    def test_position_is_read_against_the_whole_envelope(self):
        ribbon = [Decimal(110), Decimal(105), Decimal(100)]
        tol = Decimal("0.5")
        self.assertEqual(ma.position(Decimal(120), ribbon, tol), "ABOVE")
        self.assertEqual(ma.position(Decimal(107), ribbon, tol), "INSIDE")
        self.assertEqual(ma.position(Decimal(90), ribbon, tol), "BELOW")
        # Exactly at the edge, and one tolerance beyond it, are both INSIDE.
        self.assertEqual(ma.position(Decimal(110), ribbon, tol), "INSIDE")
        self.assertEqual(ma.position(Decimal("110.5"), ribbon, tol), "INSIDE")
        self.assertEqual(ma.position(Decimal("110.51"), ribbon, tol), "ABOVE")

    def test_slope_latches_and_holds_through_the_deadband(self):
        db = Decimal("0.5")
        self.assertIsNone(ma.slope_state(None, Decimal("0.4"), db))
        self.assertEqual(ma.slope_state(None, Decimal("0.6"), db), "UP")
        # inside the band the previous answer stands — that is the whole point
        self.assertEqual(ma.slope_state("UP", Decimal("-0.4"), db), "UP")
        self.assertEqual(ma.slope_state("UP", Decimal("-0.6"), db), "DOWN")


class TestWarmup(MaCase):
    def test_nothing_is_emitted_before_the_slowest_average_exists(self):
        """199 bars is one short of an SMA200. A 200-period average computed
        from 199 bars is not a slightly-worse average, it is a different
        statistic wearing the name."""
        self.load(ramp(199))
        self.assertEqual(ma.run(self.con, "BTC-USD", "1H", TF)["facts"], 0)
        self.assertEqual(self.facts(), [])

    def test_the_first_fact_lands_on_the_first_bar_the_ribbon_exists(self):
        self.load(ramp(200))
        self.assertEqual(ma.run(self.con, "BTC-USD", "1H", TF)["facts"], 1)
        f = self.facts()[0]
        self.assertEqual(f["event"], "ESTABLISHED")
        self.assertEqual(f["bar_index"], 199)
        self.assertEqual(f["market_time"], 199 * TF)

    def test_a_slope_with_no_history_is_undecided_rather_than_flat(self):
        """SMA200 exists at bar 199 and has existed for exactly one bar, so it
        has no 50-bar slope. Reported as null — an average that has not yet
        moved is not an average that is going nowhere."""
        self.load(ramp(200))
        ma.run(self.con, "BTC-USD", "1H", TF)
        ribbon = {m["name"]: m for m in self.facts()[0]["ribbon"]}
        self.assertEqual(ribbon["ema20"]["slope"], "UP")
        self.assertEqual(ribbon["ema50"]["slope"], "UP")
        self.assertIsNone(ribbon["sma200"]["slope"])


class TestRibbonValues(MaCase):
    def test_every_average_matches_its_closed_form_on_a_ramp(self):
        self.load(ramp(200))
        ma.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts()[0]
        close = BASE + STEP * 199                       # 199.5
        self.assertEqual(Decimal(f["close"]), close)
        # SMA of a ramp is exact: close - step*(n-1)/2.
        self.assertEqual(self.value(f, "sma200"), close - STEP * Decimal("99.5"))
        for name, n in (("ema20", Decimal("9.5")), ("ema50", Decimal("24.5"))):
            self.assertLess(abs(self.value(f, name) - (close - STEP * n)), CLOSED)
        self.assertEqual(Decimal(f["atr"]), ATR)
        self.assertEqual(Decimal(f["slope_deadband"]), DEADBAND)
        self.assertEqual((f["stack"], f["position"]), ("BULL", "ABOVE"))

    def test_ribbon_values_are_decimal_strings_not_floats(self):
        self.load(ramp(200))
        ma.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts()[0]
        for key in ("close", "atr", "slope_deadband", "level_tolerance",
                    "close_to_fast_atr", "close_to_slow_atr"):
            self.assertNotIn("e", f[key].lower(), key)
            self.assertIsInstance(Decimal(f[key]), Decimal)
        for member in f["ribbon"]:
            self.assertNotIn("e", member["value"].lower(), member["name"])
        # close - ema20 = 4.75, and ATR is 2, so 2.38 (not 2.375 -> banker's
        # rounding on a float would give 2.37).
        self.assertEqual(f["close_to_fast_atr"], "2.38")
        self.assertEqual(f["close_to_slow_atr"], "24.88")


class TestTransitions(MaCase):
    """A ramp up, a ramp down, and the states the turn has to produce."""

    def _turn(self):
        up = ramp(260)
        peak = BASE + STEP * 259
        down = ramp(140, start=260, base=peak - STEP, step=-STEP)
        self.load(up + down)
        return ma.run(self.con, "BTC-USD", "1H", TF)

    def test_the_ribbon_reports_the_turn(self):
        self._turn()
        events = self.facts()
        self.assertEqual(events[0]["event"], "ESTABLISHED")
        self.assertEqual(sum(1 for f in events if f["event"] == "ESTABLISHED"), 1)
        seen = [(f["stack"], f["position"]) for f in events]
        self.assertIn(("BULL", "ABOVE"), seen)
        self.assertIn(("BEAR", "BELOW"), seen)
        # Every non-establishing fact names at least one component that moved,
        # and names only components that really did.
        for prev, cur in zip(events, events[1:]):
            self.assertTrue(cur["changed"], cur)
            if "stack" in cur["changed"]:
                self.assertNotEqual(cur["stack"], prev["stack"])
            else:
                self.assertEqual(cur["stack"], prev["stack"])

    def test_the_slow_slope_flips_only_after_its_own_lookback(self):
        """SMA200's slope is measured over 50 bars, so it cannot report DOWN
        until 50 bars of the down-ramp have closed. Anything sooner would be a
        200-period average answering a question about yesterday."""
        self._turn()
        flips = [f for f in self.facts() if "slope_sma200" in f["changed"]
                 and next(m["slope"] for m in f["ribbon"]
                          if m["name"] == "sma200") == "DOWN"]
        self.assertTrue(flips)
        # the ramp turns at bar 260; SMA200 peaks 99 bars later and the 50-bar
        # comparison cannot see the fall before then
        self.assertGreater(flips[0]["bar_index"], 260 + 50)

    def test_a_move_inside_the_deadband_does_not_flip_a_slope(self):
        """0.5 is the deadband here (0.25 * ATR of 2). A drift of 0.02/bar
        moves EMA20 by 0.1 over its 5-bar lookback and must not be read as a
        turn."""
        up = ramp(260)
        peak = BASE + STEP * 259
        drift = ramp(80, start=260, base=peak - Decimal("0.02"),
                     step=Decimal("-0.02"))
        self.load(up + drift)
        ma.run(self.con, "BTC-USD", "1H", TF)
        for f in self.facts():
            if f["bar_index"] < 260:
                continue
            for member in f["ribbon"]:
                self.assertNotEqual(member["slope"], "DOWN",
                                    f"{member['name']} @ {f['bar_index']}")


class TestCausality(MaCase):
    def test_a_state_is_knowable_exactly_at_its_own_bar_close(self):
        self.load(ramp(260))
        ma.run(self.con, "BTC-USD", "1H", TF)
        facts = self.facts()
        self.assertTrue(facts)
        for f in facts:
            self.assertEqual(f["confirmed_at"], f["market_time"] + TF)
            self.assertGreater(f["confirmed_at"], f["market_time"])

    def test_no_fact_is_visible_through_the_as_of_cursor_before_it_confirmed(self):
        self.load(ramp(200))
        ma.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts()[0]
        self.assertEqual(self.facts(as_of=f["confirmed_at"] - 1), [])
        self.assertEqual(len(self.facts(as_of=f["confirmed_at"])), 1)

    def test_the_last_bar_of_the_series_is_still_a_closed_bar(self):
        """Nothing here reads a developing candle: the store only holds closed
        ones, and the engine indexes no bar beyond the last row it was given."""
        self.load(ramp(260))
        ma.run(self.con, "BTC-USD", "1H", TF)
        last_open = 259 * TF
        for f in self.facts():
            self.assertLessEqual(f["market_time"], last_open)


class TestDeterminism(MaCase):
    def test_rerun_writes_zero_new_facts(self):
        self.load(ramp(300))
        first = ma.run(self.con, "BTC-USD", "1H", TF)
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        second = ma.run(self.con, "BTC-USD", "1H", TF)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertGreater(first["facts"], 0)
        self.assertEqual(second["facts"], 0)
        self.assertEqual(before, after)

    def test_appending_bars_never_rewrites_an_earlier_fact(self):
        """Append-only in the sense that matters: the facts already written
        must be byte-identical after more data arrives."""
        self.load(ramp(260))
        ma.run(self.con, "BTC-USD", "1H", TF)
        before = self.facts()
        peak = BASE + STEP * 259
        self.load(ramp(60, start=260, base=peak - STEP, step=-STEP))
        ma.run(self.con, "BTC-USD", "1H", TF)
        after = self.facts()
        self.assertGreater(len(after), len(before))
        self.assertEqual(after[:len(before)], before)


if __name__ == "__main__":
    unittest.main()
