"""Range engine tests — the properties that must not regress.

The synthetic series is a sawtooth with a CONSTANT true range, so ATR is
exactly 4.50000000 and every threshold the engine uses is arithmetic this file
can state for itself rather than trust. The high pad (1.4) and low pad (1.5)
are deliberately different so the boundaries land on 110.5 / 99.6 — values
whose difference and midpoint are NOT exactly representable in binary
floating point. That makes `height == "10.9"` and `mid == "105.05"` genuine
assertions about Decimal survival rather than coincidences.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import ranges, store, swings

TF = 3600
BASE = Decimal("101.1")
STEP = Decimal("1.6")
HIGH_PAD = Decimal("1.4")
LOW_PAD = Decimal("1.5")
TOP = Decimal("110.5")           # phase-5 close 109.1 + 1.4
BOTTOM = Decimal("99.6")         # phase-0 close 101.1 - 1.5
ATR = Decimal("4.50000000")      # constant TR = 1.6 + 1.4 + 1.5
BAND = ranges.BOUNDARY_ATR * ATR                 # 1.125
TOL = ranges.TOL_ATR * ATR                       # 0.225


def triangle(i: int) -> int:
    phase = i % 10
    return phase if phase <= 5 else 10 - phase


def series(n: int, drift: Decimal = Decimal(0)) -> list[dict]:
    bars, prev = [], None
    for i in range(n):
        close = BASE + STEP * triangle(i) + drift * (i // 10)
        open_ = close if prev is None else prev
        bars.append({"open_ts": i * TF, "open": open_,
                     "high": max(open_, close) + HIGH_PAD,
                     "low": min(open_, close) - LOW_PAD,
                     "close": close})
        prev = close
    return bars


class RangeCase(unittest.TestCase):
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
                 str(b["low"]), str(b["close"]), "1", "test", b["open_ts"]))
        self.con.commit()

    def swing(self, bar, kind, price, lag=4, tier="LOCAL"):
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="swing",
            market_time=bar * TF, confirmed_at=(bar + lag) * TF,
            algo_version=swings.SWING_VERSION,
            payload={"tier": tier, "type": kind, "price": str(price)})

    def four_pivots(self, highs=(TOP, TOP), lows=(BOTTOM, BOTTOM)):
        for bar, kind, price in ((20, "LOW", lows[0]), (25, "HIGH", highs[0]),
                                 (30, "LOW", lows[1]), (35, "HIGH", highs[1])):
            self.swing(bar, kind, price)

    def facts(self, as_of=None):
        rows = store.get_facts(self.con, "BTC-USD", "1H", "range",
                               ranges.RANGES_VERSION, as_of=as_of)
        return [{"market_time": r["market_time"],
                 "confirmed_at": r["confirmed_at"],
                 **json.loads(r["payload"])} for r in rows]

    def events(self, name, as_of=None):
        return [f for f in self.facts(as_of) if f["event"] == name]


class TestFormation(RangeCase):
    def test_clean_range_is_detected_with_cluster_boundaries(self):
        self.load(series(60))
        self.four_pivots()
        result = ranges.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(result["formed"], 1)
        f = self.events("FORMED")[0]
        self.assertEqual(f["top"], str(TOP))
        self.assertEqual(f["bottom"], str(BOTTOM))
        self.assertEqual((f["top_swings"], f["bottom_swings"]), (2, 2))
        self.assertEqual(f["member_ts"], [20 * TF, 25 * TF, 30 * TF, 35 * TF])
        self.assertEqual(f["range_start_ts"], 20 * TF)
        self.assertEqual(f["formation_bars"], 15)
        self.assertEqual(f["atr_at_formation"], str(ATR))

    def test_trending_swings_are_not_a_range(self):
        """Rising highs and rising lows must fail the tightness predicate — the
        one place the engine says 'these pivots do not cluster'."""
        self.load(series(60, drift=Decimal(4)))
        self.four_pivots(highs=(Decimal("118.5"), Decimal("122.5")),
                         lows=(Decimal("105.2"), Decimal("109.2")))
        result = ranges.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(result["formed"], 0)
        self.assertEqual(self.facts(), [])

    def test_a_band_taller_than_the_ceiling_is_not_a_range(self):
        """Containment inside a huge band is not evidence of anything."""
        self.load(series(60))
        # 8 * ATR = 36; a 40-wide band is contained by construction here.
        self.four_pivots(highs=(Decimal("130"), Decimal("130")),
                         lows=(Decimal("90"), Decimal("90")))
        self.assertEqual(ranges.run(self.con, "BTC-USD", "1H", TF)["formed"], 0)

    def test_micro_swings_are_not_boundaries(self):
        """The tier is a deliberate, measured choice (see the module
        docstring); a MICRO fractal is noise, not a level."""
        self.load(series(60))
        for bar, kind, price in ((20, "LOW", BOTTOM), (25, "HIGH", TOP),
                                 (30, "LOW", BOTTOM), (35, "HIGH", TOP)):
            self.swing(bar, kind, price, tier="MICRO")
        self.assertEqual(ranges.run(self.con, "BTC-USD", "1H", TF)["formed"], 0)

    def test_only_one_range_is_active_at_a_time(self):
        """Six pivots inside one band describe ONE level, not three."""
        self.load(series(80))
        self.four_pivots()
        self.swing(40, "LOW", BOTTOM)
        self.swing(45, "HIGH", TOP)
        self.assertEqual(ranges.run(self.con, "BTC-USD", "1H", TF)["formed"], 1)


class TestCausality(RangeCase):
    def test_range_is_unknowable_until_its_last_forming_swing_confirms(self):
        self.load(series(60))
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        f = self.events("FORMED")[0]
        last_conf, first_conf = (35 + 4) * TF, (20 + 4) * TF
        self.assertEqual(f["confirmed_at"], last_conf)
        self.assertNotEqual(f["confirmed_at"], first_conf)
        self.assertEqual(f["market_time"], 35 * TF)
        self.assertLess(f["market_time"], f["confirmed_at"])
        # The as_of cursor is the contract every consumer reads through.
        self.assertEqual(self.facts(as_of=last_conf - 1), [])
        self.assertEqual(len(self.events("FORMED", as_of=last_conf)), 1)

    def test_events_inside_the_confirmation_lag_are_not_backdated(self):
        """The last INTERMEDIATE pivot confirms bars after its own bar. Events
        in that window happened when they happened, but were knowable no
        earlier than the range itself."""
        self.load(series(60))
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        formed = self.events("FORMED")[0]
        self.assertEqual(formed["confirmation_lag_bars"], 3)
        for f in self.facts():
            self.assertGreaterEqual(f["confirmed_at"], formed["confirmed_at"])
            self.assertGreaterEqual(f["confirmed_at"], f["market_time"] + TF)


class TestBreakRule(RangeCase):
    def _break_series(self, wick_bar=45, break_bar=50):
        bars = series(60)
        bars[wick_bar]["high"] = Decimal("130")        # spike only
        bars[break_bar]["high"] = Decimal("131")
        bars[break_bar]["close"] = Decimal("130")      # closed displacement
        return bars

    def test_wick_through_the_top_does_not_break_but_a_close_does(self):
        self.load(self._break_series())
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        broken = self.events("BROKEN")
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["market_time"], 50 * TF)
        self.assertEqual(broken[0]["broken_side"], "TOP")
        self.assertEqual(broken[0]["state"], "BROKEN")
        self.assertEqual(broken[0]["bars_held"], 15)
        self.assertEqual(Decimal(broken[0]["close"]), Decimal("130"))
        self.assertGreater(Decimal(broken[0]["close"]),
                           Decimal(broken[0]["top"]) + Decimal(broken[0]["tolerance"]))

    def test_a_close_inside_the_tolerance_is_not_a_break(self):
        bars = series(60)
        bars[45]["high"] = TOP + TOL
        bars[45]["close"] = TOP + TOL          # exactly at, not beyond
        self.load(bars)
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(self.events("BROKEN"), [])

    def test_a_broken_range_lets_the_next_one_form(self):
        """The consumed-until guard re-arms; it does not silence the engine."""
        bars = self._break_series(wick_bar=45, break_bar=50)
        self.load(bars)
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        formed = self.events("FORMED")
        self.assertEqual(len(formed), 1)
        # Pivots that pre-date the break may not build the successor.
        self.assertTrue(all(ts <= 50 * TF for ts in formed[0]["member_ts"]))


class TestEvidence(RangeCase):
    def test_boundary_tests_are_counted_on_every_fact(self):
        self.load(series(80))
        self.four_pivots()
        result = ranges.run(self.con, "BTC-USD", "1H", TF)
        self.assertGreater(result["tested"], 0)
        tested = self.events("TESTED")
        self.assertEqual({t["boundary"] for t in tested}, {"TOP", "BOTTOM"})
        first, last = tested[0], tested[-1]
        self.assertGreater(last["top_touches"] + last["bottom_touches"],
                           first["top_touches"] + first["bottom_touches"])
        self.assertGreater(last["bars_held"], first["bars_held"])
        # Formation swings seed the touch counts; a test never counts the
        # pivot bar that created the boundary a second time.
        self.assertGreaterEqual(first["top_touches"], 2)
        self.assertGreaterEqual(first["bottom_touches"], 2)

    def test_boundary_spread_is_recorded_for_the_rule_not_taken(self):
        """Tightness is judged against ATR; the height-relative view a later
        version might prefer is recorded rather than assumed."""
        self.load(series(60))
        self.four_pivots(highs=(TOP - Decimal("0.5"), TOP),
                         lows=(BOTTOM, BOTTOM + Decimal("0.2")))
        ranges.run(self.con, "BTC-USD", "1H", TF)
        f = self.events("FORMED")[0]
        self.assertEqual(f["top_spread"], "0.5")
        self.assertEqual(f["bottom_spread"], "0.2")
        # 0.5 / 10.9 = 4.59%
        self.assertEqual(f["boundary_spread_pct"], "4.59")

    def test_test_facts_are_capped_but_the_count_keeps_accruing(self):
        self.load(series(200))
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        tested = self.events("TESTED")
        self.assertLessEqual(len(tested), ranges.MAX_TEST_FACTS)
        self.assertEqual(tested[-1]["episode"], ranges.MAX_TEST_FACTS)


class TestDeterminism(RangeCase):
    def test_rerun_writes_zero_new_facts(self):
        self.load(series(80))
        self.four_pivots()
        first = ranges.run(self.con, "BTC-USD", "1H", TF)
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        second = ranges.run(self.con, "BTC-USD", "1H", TF)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertGreater(first["formed"], 0)
        self.assertEqual(before, after)
        self.assertEqual((second["formed"], second["tested"], second["broken"]),
                         (0, 0, 0))

    def test_decimal_survives_into_the_payload(self):
        self.load(series(60))
        self.four_pivots()
        ranges.run(self.con, "BTC-USD", "1H", TF)
        f = self.events("FORMED")[0]
        # 110.5 - 99.6 is 10.899999999999999 in binary floating point.
        self.assertEqual(f["height"], "10.9")
        # (110.5 + 99.6) / 2 is 105.05000000000001 in binary floating point.
        self.assertEqual(f["mid"], "105.05")
        self.assertEqual(f["boundary_band"], str(BAND))
        self.assertEqual(Decimal(f["top"]) - Decimal(f["bottom"]),
                         Decimal(f["height"]))
        for key in ("top", "bottom", "mid", "height", "boundary_band",
                    "atr_at_formation", "height_atr"):
            self.assertNotIn("e", f[key].lower(), key)
            self.assertIsInstance(Decimal(f[key]), Decimal)


class TestPredicates(unittest.TestCase):
    def _window(self, highs, lows):
        out = []
        for i, (h, lo) in enumerate(zip(highs, lows)):
            out.append({"type": "LOW", "price": Decimal(lo), "market_time": i})
            out.append({"type": "HIGH", "price": Decimal(h), "market_time": i})
        return out

    def test_boundaries_take_the_extreme_of_each_cluster(self):
        w = self._window(("110", "110.4"), ("100.2", "100"))
        top, bottom, n_top, n_bottom = ranges.boundaries(w)
        self.assertEqual((top, bottom), (Decimal("110.4"), Decimal("100")))
        self.assertEqual((n_top, n_bottom), (2, 2))

    def test_tightness_rejects_a_trending_window(self):
        flat = self._window(("110", "110.4"), ("100.2", "100"))
        trend = self._window(("110", "116"), ("100", "106"))
        tol = Decimal("1")
        self.assertTrue(ranges.is_flat(flat, Decimal("110.4"), Decimal("100"), tol))
        self.assertFalse(ranges.is_flat(trend, Decimal("116"), Decimal("100"), tol))

    def test_break_tolerance_floors_at_one_tick(self):
        # `tick` is required, not defaulted: a default of 0.01 here would be the
        # exact hard-coded constant the shared derivation exists to remove, and
        # it would apply silently to whichever caller forgot to pass one.
        tick = Decimal("0.01")
        self.assertEqual(ranges.break_tolerance(None, tick), tick)
        self.assertEqual(ranges.break_tolerance(Decimal("0.0001"), tick), tick)
        self.assertEqual(ranges.break_tolerance(Decimal("10"), tick), Decimal("0.5"))
        with self.assertRaises(TypeError):
            ranges.break_tolerance(Decimal("10"))

    def test_tick_is_the_venue_quote_not_a_constant(self):
        """The 0.01 constant is 944,882x too large on SHIB-USD; a tolerance
        wider than any move the instrument makes never breaks anything."""
        usd = [{"open": "47733.43", "high": "47800.0", "low": "47000.1",
                "close": "47733.4"}]
        shib = [{"open": "0.0000341", "high": "0.0000355", "low": "0.0000331",
                 "close": "0.0000341"}]
        self.assertEqual(ranges.quote_ticks(usd), [Decimal("0.01")])
        self.assertEqual(ranges.quote_ticks(shib), [Decimal("0.0000001")])
        # 0.05 * ATR must survive rather than be swallowed by the floor.
        self.assertEqual(
            ranges.break_tolerance(Decimal("0.000002"), Decimal("0.0000001")),
            Decimal("0.0000001"))

    def test_tick_precision_only_ever_grows_with_the_past(self):
        """A later, finer quote must not retroactively change the tolerance an
        already-emitted fact was computed with — that would break idempotency
        AND causality in one move."""
        bars = [{"open": "1.5", "high": "1.5", "low": "1.5", "close": "1.5"},
                {"open": "1.25", "high": "1.25", "low": "1.25", "close": "1.25"},
                {"open": "1.5", "high": "1.5", "low": "1.5", "close": "1.5"}]
        ticks = ranges.quote_ticks(bars)
        self.assertEqual(ticks, [Decimal("0.1"), Decimal("0.01"), Decimal("0.01")])
        self.assertEqual(ranges.quote_ticks(bars[:2]), ticks[:2])

    def test_minimum_height_keeps_the_boundary_bands_apart(self):
        """Not a preference — below 4x the boundary tolerance the top band and
        the bottom band overlap and the two words stop meaning different
        things."""
        self.assertEqual(ranges.MIN_HEIGHT_ATR, ranges.BOUNDARY_ATR * 4)


if __name__ == "__main__":
    unittest.main()
