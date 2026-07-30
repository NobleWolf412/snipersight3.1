"""Volatility engine tests — the properties that must not regress.

Three synthetic constructions, each chosen so the expected answer is arithmetic
this file can state rather than a baseline it has to trust.

FLAT: close pinned at 100 with a 99/101 range on every bar. The true range is
exactly 2 on every bar so ATR is exactly 2.00000000; the standard deviation of
twenty identical closes is exactly 0, so the Bollinger bands collapse onto 100
while the Keltner channel is 100 +/- 1.5*2 = [97, 103]. The bands are inside the
channel by construction, which is a squeeze, and every number in that sentence
is exact.

SAW: closes alternating 100 / 104 over a 20-bar window. The mean is exactly 102
and every deviation is exactly 2, so the population variance is exactly 4 and
the standard deviation exactly 2 — a non-trivial Bollinger value with no
irrational part anywhere in it.

RAMP: closes rising by 2 with a 1-wide pad. The true range settles at exactly 3
(previous close to this bar's high) while the standard deviation of twenty
ramp closes is 2 * sqrt(399/12) = 11.53, so the bands sit far OUTSIDE a channel
of 1.5 * 3 = 4.5. A trend is the case where a squeeze must be off, and this is
the arithmetic reason why.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import store, volatility

TF = 3600
PAD = Decimal("1")
FLAT_ATR = Decimal("2.00000000")


def bars(closes: list, pad: Decimal = PAD, start: int = 0) -> list[dict]:
    out, prev = [], None
    for i, close in enumerate(closes):
        out.append({"open_ts": (start + i) * TF,
                    "open": close if prev is None else prev,
                    "high": close + pad, "low": close - pad, "close": close})
        prev = close
    return out


class VolatilityCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, closes, pad=PAD, start=0):
        for b in bars(closes, pad, start):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1H", b["open_ts"], str(b["open"]), str(b["high"]),
                 str(b["low"]), str(b["close"]), "10", "test", b["open_ts"]))
        self.con.commit()

    def facts(self, event=None, as_of=None):
        rows = store.get_facts(self.con, "BTC-USD", "1H", "volatility",
                               volatility.VOLATILITY_VERSION, as_of=as_of)
        out = [{"market_time": r["market_time"], "confirmed_at": r["confirmed_at"],
                **json.loads(r["payload"])} for r in rows]
        return [f for f in out if event is None or f["event"] == event]


class TestBollinger(unittest.TestCase):
    def test_bands_are_the_hand_computed_ones(self):
        closes = [Decimal(100 if i % 2 == 0 else 104) for i in range(20)]
        mid, up, low = volatility.bollinger(closes, 20, Decimal(2))
        # mean = 102 ; every deviation is 2 ; population variance = 4 ; sd = 2
        self.assertEqual(mid[19], Decimal(102))
        self.assertEqual(up[19], Decimal(106))
        self.assertEqual(low[19], Decimal(98))

    def test_zero_dispersion_collapses_the_bands_onto_the_mean(self):
        closes = [Decimal(100)] * 20
        mid, up, low = volatility.bollinger(closes, 20, Decimal(2))
        self.assertEqual((mid[19], up[19], low[19]),
                         (Decimal(100), Decimal(100), Decimal(100)))

    def test_warmup_is_refused_not_approximated(self):
        """A 20-period standard deviation of five closes is not a noisier
        20-period standard deviation. It is a different statistic."""
        closes = [Decimal(100) + i for i in range(19)]
        mid, up, low = volatility.bollinger(closes, 20, Decimal(2))
        self.assertEqual(mid, [None] * 19)
        self.assertEqual(up, [None] * 19)
        self.assertEqual(low, [None] * 19)

    def test_decimal_survives_a_deviation_floats_get_wrong(self):
        closes = [Decimal("0.1") if i % 2 == 0 else Decimal("0.3")
                  for i in range(20)]
        mid, up, low = volatility.bollinger(closes, 20, Decimal(2))
        # mean 0.2, deviation 0.1, sd 0.1, bands 0.0 and 0.4 — in binary
        # floating point the mean alone comes out 0.19999999999999998.
        self.assertEqual(mid[19], Decimal("0.2"))
        self.assertEqual(up[19], Decimal("0.4"))
        self.assertEqual(low[19], Decimal(0))


class TestKeltner(unittest.TestCase):
    def test_channel_is_the_ema_plus_and_minus_its_atr_multiple(self):
        closes = [Decimal(100)] * 30
        atr = [None] * 14 + [Decimal(2)] * 16
        mid, up, low = volatility.keltner(closes, atr, 20, Decimal("1.5"))
        self.assertEqual(mid[29], Decimal(100))
        self.assertEqual(up[29], Decimal(103))
        self.assertEqual(low[29], Decimal(97))

    def test_no_channel_without_an_atr(self):
        closes = [Decimal(100)] * 30
        mid, up, low = volatility.keltner(closes, [None] * 30, 20, Decimal("1.5"))
        self.assertIsNotNone(mid[29])
        self.assertIsNone(up[29])
        self.assertIsNone(low[29])


class TestPercentile(unittest.TestCase):
    def test_rank_within_the_trailing_window(self):
        atr = [None, None] + [Decimal(v) for v in (1, 2, 3, 4)]
        got = volatility.atr_percentiles(atr, window=4)
        self.assertEqual(got[:5], [None] * 5)
        # window [1,2,3,4], 4 is the highest: midrank (3+4)/2 of 4 -> 87.5%
        self.assertEqual(got[5], Decimal("87.50"))

    def test_the_window_actually_rolls(self):
        atr = [None] + [Decimal(v) for v in (1, 2, 3, 4, "0.5")]
        got = volatility.atr_percentiles(atr, window=4)
        # at the last bar the window is [2,3,4,0.5]; 0.5 is the lowest, so the
        # midrank is (0+1)/2 of 4 -> 12.5%
        self.assertEqual(got[5], Decimal("12.50"))

    def test_a_flat_window_sits_in_the_middle_of_its_own_distribution(self):
        """The obvious tie rule — count everything at or below — would report a
        dead-flat series at the 100th percentile and the state machine would
        call silence HIGH volatility. Midrank says 50."""
        atr = [Decimal(2)] * 10
        got = volatility.atr_percentiles(atr, window=5)
        self.assertEqual(got[9], Decimal("50.00"))

    def test_regime_holds_through_its_deadband(self):
        self.assertEqual(volatility.atr_regime(None, Decimal(50)), "NORMAL")
        self.assertEqual(volatility.atr_regime("NORMAL", Decimal(20)), "LOW")
        self.assertEqual(volatility.atr_regime("LOW", Decimal(25)), "LOW")
        self.assertEqual(volatility.atr_regime("LOW", Decimal(35)), "NORMAL")
        self.assertEqual(volatility.atr_regime("NORMAL", Decimal(80)), "HIGH")
        self.assertEqual(volatility.atr_regime("HIGH", Decimal(75)), "HIGH")
        self.assertEqual(volatility.atr_regime("HIGH", Decimal(65)), "NORMAL")


class TestSqueeze(VolatilityCase):
    def test_a_flat_market_is_a_squeeze_and_the_numbers_say_why(self):
        self.load([Decimal(100)] * 40)
        result = volatility.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(result["squeeze"], 1)
        f = self.facts("SQUEEZE")[0]
        self.assertEqual((f["squeeze"], f["state"]), ("ON", "ESTABLISHED"))
        self.assertEqual(f["bar_index"], 19)
        self.assertEqual(Decimal(f["atr"]), FLAT_ATR)
        self.assertEqual(Decimal(f["bb_upper"]), Decimal(100))
        self.assertEqual(Decimal(f["bb_lower"]), Decimal(100))
        self.assertEqual(Decimal(f["kc_upper"]), Decimal(103))
        self.assertEqual(Decimal(f["kc_lower"]), Decimal(97))
        self.assertEqual(f["bb_width_pct"], "0.00")
        self.assertIsNone(f["bars_in_prev_state"])

    def test_a_trend_releases_it(self):
        """The bands are 2*sd = 23.07 wide either side on this ramp against a
        channel of 1.5*ATR = 4.5. A squeeze cannot survive that."""
        self.load([Decimal(100)] * 60)
        self.load([Decimal(100) + 2 * i for i in range(1, 81)], start=60)
        volatility.run(self.con, "BTC-USD", "1H", TF)
        states = [(f["squeeze"], f["bar_index"]) for f in self.facts("SQUEEZE")]
        self.assertEqual([s for s, _ in states][:2], ["ON", "OFF"])
        off = self.facts("SQUEEZE")[1]
        # The rule is a conjunction, so releasing it takes only ONE band
        # escaping. It is the LOWER one here, and that asymmetry is a real
        # property rather than an accident: the Bollinger centre is a simple
        # average and the Keltner centre an exponential one, so on a rising
        # ramp the bands sit lower than the channel and the floor gives first.
        self.assertLessEqual(Decimal(off["bb_lower"]), Decimal(off["kc_lower"]))
        self.assertFalse(Decimal(off["bb_upper"]) < Decimal(off["kc_upper"])
                         and Decimal(off["bb_lower"]) > Decimal(off["kc_lower"]))
        self.assertGreater(off["bars_in_prev_state"], 0)

    def test_nothing_is_emitted_before_the_bands_exist(self):
        self.load([Decimal(100)] * 19)
        self.assertEqual(volatility.run(self.con, "BTC-USD", "1H", TF)["squeeze"], 0)
        self.assertEqual(self.facts(), [])


class TestAtrRegime(VolatilityCase):
    def test_no_regime_fact_before_a_hundred_atr_readings(self):
        """ATR itself needs 15 bars and the percentile needs 100 of them, so
        the first possible ATR_REGIME bar is 113. A rank out of eleven samples
        is not a percentile."""
        self.load([Decimal(100)] * 113)
        self.assertEqual(
            volatility.run(self.con, "BTC-USD", "1H", TF)["atr_regime"], 0)
        self.con.execute("DELETE FROM facts")
        self.load([Decimal(100)] * 5, start=113)
        volatility.run(self.con, "BTC-USD", "1H", TF)
        regimes = self.facts("ATR_REGIME")
        self.assertTrue(regimes)
        self.assertEqual(regimes[0]["bar_index"], 113)

    def test_a_falling_atr_is_recorded_as_a_low_regime(self):
        # loud bars first, then quiet ones: ATR decays and its rank collapses
        self.load([Decimal(100)] * 150, pad=Decimal(10))
        self.load([Decimal(100)] * 160, pad=Decimal(1), start=150)
        volatility.run(self.con, "BTC-USD", "1H", TF)
        seen = [f["regime"] for f in self.facts("ATR_REGIME")]
        self.assertEqual(seen[0], "NORMAL")     # flat window -> midrank 50
        self.assertIn("LOW", seen)
        low = next(f for f in self.facts("ATR_REGIME") if f["regime"] == "LOW")
        self.assertLessEqual(Decimal(low["atr_percentile"]),
                             volatility.ATR_LOW_IN)
        self.assertEqual(low["percentile_window"], volatility.PCTL_WINDOW)


class TestCausality(VolatilityCase):
    def test_a_fact_confirms_exactly_at_its_own_bar_close(self):
        self.load([Decimal(100)] * 60)
        self.load([Decimal(100) + 2 * i for i in range(1, 81)], start=60)
        volatility.run(self.con, "BTC-USD", "1H", TF)
        facts = self.facts()
        self.assertTrue(facts)
        for f in facts:
            self.assertEqual(f["confirmed_at"], f["market_time"] + TF)
            self.assertGreater(f["confirmed_at"], f["market_time"])

    def test_the_as_of_cursor_hides_a_fact_until_its_bar_closed(self):
        self.load([Decimal(100)] * 40)
        volatility.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts()[0]
        self.assertEqual(self.facts(as_of=f["confirmed_at"] - 1), [])
        self.assertEqual(len(self.facts(as_of=f["confirmed_at"])), 1)

    def test_the_percentile_window_never_reaches_forward(self):
        """A rank computed from bars the system had not seen would be the
        cleanest possible lookahead. Truncating the series must not change the
        readings that survive."""
        closes = [Decimal(100) + (i % 7) for i in range(200)]
        full = volatility.atr_percentiles(
            volatility.compute_atr(bars(closes)))
        short = volatility.atr_percentiles(
            volatility.compute_atr(bars(closes[:160])))
        self.assertEqual(full[:160], short)


class TestDeterminism(VolatilityCase):
    def _loaded(self):
        self.load([Decimal(100)] * 130)
        self.load([Decimal(100) + 2 * i for i in range(1, 101)], start=130)

    def test_rerun_writes_zero_new_facts(self):
        self._loaded()
        first = volatility.run(self.con, "BTC-USD", "1H", TF)
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        second = volatility.run(self.con, "BTC-USD", "1H", TF)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertGreater(first["squeeze"] + first["atr_regime"], 0)
        self.assertEqual((second["squeeze"], second["atr_regime"]), (0, 0))
        self.assertEqual(before, after)

    def test_every_emitted_number_is_a_decimal_string(self):
        self._loaded()
        volatility.run(self.con, "BTC-USD", "1H", TF)
        for f in self.facts():
            for key in ("close", "atr", "atr_percentile", "bb_upper", "bb_lower",
                        "bb_mid", "bb_width_pct", "kc_upper", "kc_lower",
                        "kc_mid"):
                if f.get(key) is None:
                    continue
                self.assertNotIn("e", f[key].lower(), (f["event"], key))
                self.assertIsInstance(Decimal(f[key]), Decimal)
        sq = self.facts("SQUEEZE")[0]
        self.assertEqual(Decimal(sq["kc_upper"]) - Decimal(sq["kc_mid"]),
                         volatility.KC_K * Decimal(sq["atr"]))


if __name__ == "__main__":
    unittest.main()
