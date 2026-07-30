"""Momentum engine tests — the properties that must not regress.

Two synthetic constructions, each chosen so the answer is arithmetic this file
can state rather than a number it has to trust.

For RSI, a saw of +2 / -1 steps: over fourteen changes that is seven gains
totalling 14 and seven losses totalling 7, so the first Wilder averages are
exactly 1 and 0.5, RS is exactly 2, and RSI is 100 - 100/3 = 66.666667.

For MACD, a LINEAR RAMP. On a ramp of step s the EMA of period n sits exactly
at `close - s*(n-1)/2` (the SMA seed this engine uses IS the EMA's fixed point
there, so the recursion never has to converge), which makes

    MACD = EMA12 - EMA26 = s*(12.5 - 5.5) = 7s

a CONSTANT — 3.5 at s = 0.5. An EMA of a constant is that constant, so the
signal line is also exactly 3.5 and the histogram is exactly zero. A MACD test
on a ramp is therefore a closed-form test, not a regression baseline.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import momentum, store, swings

TF = 3600
PAD = Decimal("1")


def candles(closes: list, start: int = 0) -> list[dict]:
    bars, prev = [], None
    for i, close in enumerate(closes):
        bars.append({"open_ts": (start + i) * TF,
                     "open": close if prev is None else prev,
                     "high": close + PAD, "low": close - PAD, "close": close})
        prev = close
    return bars


def leg(start: Decimal, step: Decimal, n: int) -> list[Decimal]:
    return [start + step * i for i in range(1, n + 1)]


class MomentumCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, closes):
        for b in candles(closes):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1H", b["open_ts"], str(b["open"]), str(b["high"]),
                 str(b["low"]), str(b["close"]), "10", "test", b["open_ts"]))
        self.con.commit()

    def swing(self, bar, kind, price, lag=4, tier="LOCAL"):
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="swing",
            market_time=bar * TF, confirmed_at=(bar + lag) * TF,
            algo_version=swings.SWING_VERSION,
            payload={"tier": tier, "type": kind, "price": str(price)})

    def facts(self, event=None, as_of=None):
        rows = store.get_facts(self.con, "BTC-USD", "1H", "momentum",
                               momentum.MOMENTUM_VERSION, as_of=as_of)
        out = [{"market_time": r["market_time"], "confirmed_at": r["confirmed_at"],
                **json.loads(r["payload"])} for r in rows]
        return [f for f in out if event is None or f["event"] == event]


class TestRsiArithmetic(unittest.TestCase):
    SAW = [Decimal(v) for v in
           ("100", "102", "101", "103", "102", "104", "103", "105",
            "104", "106", "105", "107", "106", "108", "107", "109")]

    def test_first_value_is_the_hand_computed_one(self):
        rsi = momentum.compute_rsi(self.SAW)
        # 14 changes: 7 gains of 2 (sum 14) and 7 losses of 1 (sum 7).
        # avg_gain = 14/14 = 1 ; avg_loss = 7/14 = 0.5 ; RS = 2
        # RSI = 100 - 100/(1+2) = 66.666666... -> 8 significant digits
        self.assertEqual(rsi[14], Decimal("66.666667"))

    def test_wilder_smoothing_carries_forward(self):
        rsi = momentum.compute_rsi(self.SAW)
        # bar 15 is +2, so avg_gain = (1*13 + 2)/14 = 1.0714286 and
        # avg_loss = (0.5*13 + 0)/14 = 0.46428571 ; RS = 2.3076923
        # RSI = 100 - 100/3.3076923 = 69.767443
        self.assertEqual(rsi[15], Decimal("69.767443"))

    def test_warmup_is_refused_not_approximated(self):
        """RSI(14) needs 14 CHANGES, which is 15 bars. There is no such thing
        as a 14-period RSI at bar 6."""
        rsi = momentum.compute_rsi(self.SAW)
        self.assertEqual(rsi[:14], [None] * 14)
        self.assertEqual(momentum.compute_rsi(self.SAW[:14]), [None] * 14)

    def test_no_losses_is_100_and_no_movement_at_all_is_unknown(self):
        """avg_loss = 0 with gains is RSI 100 — the standard answer. avg_loss
        AND avg_gain both 0 is 0/0, and the conventional 50 would report
        'perfectly balanced' about a window in which nothing traded through."""
        self.assertEqual(
            momentum.compute_rsi([Decimal(100) + i for i in range(20)])[14],
            Decimal(100))
        self.assertIsNone(momentum.compute_rsi([Decimal(100)] * 20)[14])

    def test_decimal_survives(self):
        closes = [Decimal("0.1") * i for i in range(1, 20)]
        rsi = momentum.compute_rsi(closes)
        self.assertEqual(rsi[14], Decimal(100))
        self.assertIsInstance(rsi[14], Decimal)


class TestMacdArithmetic(unittest.TestCase):
    RAMP = [Decimal(100) + Decimal("0.5") * i for i in range(60)]

    def test_macd_on_a_ramp_is_the_closed_form_constant(self):
        macd, signal, hist = momentum.compute_macd(self.RAMP)
        # 0.5 * (12.5 - 5.5) = 3.5, on every bar the MACD line exists.
        self.assertEqual(macd[25], Decimal("3.5"))
        self.assertEqual(macd[59], Decimal("3.5"))
        self.assertEqual(signal[59], Decimal("3.5"))
        self.assertEqual(hist[59], Decimal(0))

    def test_the_signal_line_has_a_warmup_of_its_own(self):
        """EMA26 starts at bar 25; the signal is a 9-period EMA OF THAT, so it
        cannot start before bar 33. Seeding it with zeros standing in for the
        missing bars would put a signal line under candles there was nothing to
        average."""
        macd, signal, hist = momentum.compute_macd(self.RAMP)
        self.assertEqual(macd[:25], [None] * 25)
        self.assertIsNotNone(macd[25])
        self.assertEqual(signal[:33], [None] * 33)
        self.assertIsNotNone(signal[33])
        self.assertEqual(hist[:33], [None] * 33)

    def test_a_series_shorter_than_the_slow_ema_yields_nothing(self):
        macd, signal, hist = momentum.compute_macd(self.RAMP[:20])
        self.assertEqual(macd, [None] * 20)
        self.assertEqual(signal, [None] * 20)
        self.assertEqual(hist, [None] * 20)


class TestStateMachines(unittest.TestCase):
    def test_rsi_band_holds_through_its_deadband(self):
        self.assertEqual(momentum.rsi_band(None, Decimal(50)), "NEUTRAL")
        self.assertEqual(momentum.rsi_band("NEUTRAL", Decimal(70)), "OVERBOUGHT")
        # 68 is below the 70 entry but above the 65 exit: still overbought.
        self.assertEqual(momentum.rsi_band("OVERBOUGHT", Decimal(68)), "OVERBOUGHT")
        self.assertEqual(momentum.rsi_band("OVERBOUGHT", Decimal(64)), "NEUTRAL")
        self.assertEqual(momentum.rsi_band("NEUTRAL", Decimal(30)), "OVERSOLD")
        self.assertEqual(momentum.rsi_band("OVERSOLD", Decimal(33)), "OVERSOLD")
        self.assertEqual(momentum.rsi_band("OVERSOLD", Decimal(36)), "NEUTRAL")

    def test_an_exact_zero_is_not_a_crossing(self):
        self.assertEqual(momentum.sign_state("ABOVE", Decimal(0)), "ABOVE")
        self.assertEqual(momentum.sign_state("BELOW", Decimal(0)), "BELOW")
        self.assertIsNone(momentum.sign_state(None, Decimal(0)))
        self.assertEqual(momentum.sign_state("BELOW", Decimal("0.01")), "ABOVE")


class TestEmission(MomentumCase):
    def test_a_ramp_establishes_a_state_once_and_never_flips(self):
        """A straight line has no crossings, so each state machine writes its
        opening state and then nothing.

        MACD_SIGNAL writes nothing AT ALL here, and that is the correct answer
        rather than a gap: on a ramp the histogram is identically zero, the
        MACD line never separates from its signal, and an exact zero is a value
        ON the line rather than a side of it. Scoring it as ABOVE would report a
        crossing that the arithmetic says did not happen."""
        self.load([Decimal(100) + Decimal("0.5") * i for i in range(60)])
        result = momentum.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(result["rsi_band"], 1)
        self.assertEqual(result["macd_zero"], 1)
        self.assertEqual(result["macd_signal"], 0)
        self.assertEqual(result["divergence"], 0)
        band = self.facts("RSI_BAND")[0]
        self.assertEqual((band["band"], band["state"]), ("OVERBOUGHT",
                                                         "ESTABLISHED"))
        self.assertIsNone(band["from"])

    def test_no_macd_fact_can_predate_its_own_warmup(self):
        # up, down, up — so the MACD line genuinely crosses its signal in both
        # directions rather than resting on it
        self.load(leg(Decimal(100), Decimal(1), 40)
                  + leg(Decimal(140), Decimal(-1), 40)
                  + leg(Decimal(100), Decimal(1), 40))
        momentum.run(self.con, "BTC-USD", "1H", TF)
        self.assertGreaterEqual(self.facts("MACD_SIGNAL")[0]["bar_index"], 33)
        self.assertGreaterEqual(self.facts("MACD_ZERO")[0]["bar_index"], 25)
        self.assertGreaterEqual(self.facts("RSI_BAND")[0]["bar_index"], 14)
        crosses = self.facts("MACD_SIGNAL")
        self.assertGreaterEqual(len(crosses), 2)
        self.assertEqual(crosses[0]["state"], "ESTABLISHED")
        self.assertEqual(crosses[0]["direction"], "BEAR")
        self.assertEqual(crosses[1]["direction"], "BULL")
        self.assertEqual(crosses[1]["from"], "BELOW")

    def test_nothing_is_emitted_before_any_indicator_exists(self):
        self.load([Decimal(100) + i for i in range(10)])
        result = momentum.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(sum(v for v in result.values() if isinstance(v, int)), 0)
        self.assertEqual(self.facts(), [])

    def test_the_band_round_trip_is_two_facts_not_a_stream(self):
        closes = ([Decimal(100) + 2 * i for i in range(20)]        # into 70+
                  + leg(Decimal(138), Decimal(-2), 20))            # back down
        self.load(closes)
        momentum.run(self.con, "BTC-USD", "1H", TF)
        bands = [(f["band"], f["bar_index"]) for f in self.facts("RSI_BAND")]
        self.assertEqual([b for b, _ in bands][:3],
                         ["OVERBOUGHT", "NEUTRAL", "OVERSOLD"])


class TestDivergence(MomentumCase):
    def _series(self):
        """A hard rally to 140, a pullback, then a slow grind to a HIGHER high.
        The second peak is higher in price and reached with far less force, so
        RSI must be lower there — that is what a bearish divergence is."""
        closes = ([Decimal(100)]
                  + leg(Decimal(100), Decimal(2), 20)          # bars 1-20 -> 140
                  + leg(Decimal(140), Decimal(-1), 15)         # bars 21-35 -> 125
                  + leg(Decimal(125), Decimal("0.8"), 20))     # bars 36-55 -> 141
        return closes

    def test_a_higher_high_on_weaker_rsi_is_a_bearish_divergence(self):
        closes = self._series()
        self.load(closes)
        self.swing(20, "HIGH", closes[20])
        self.swing(35, "LOW", closes[35])
        self.swing(55, "HIGH", closes[55])
        result = momentum.run(self.con, "BTC-USD", "1H", TF)
        self.assertEqual(result["divergence"], 1)
        d = self.facts("DIVERGENCE")[0]
        rsi = momentum.compute_rsi(closes)
        self.assertEqual((d["divergence"], d["direction"]), ("BEARISH", "BEAR"))
        self.assertGreater(Decimal(d["price"]), Decimal(d["price_prev"]))
        self.assertLess(Decimal(d["rsi"]), Decimal(d["rsi_prev"]))
        # the payload must be the engine's own reading, not a rounded retelling
        self.assertEqual(Decimal(d["rsi"]), rsi[55])
        self.assertEqual(Decimal(d["rsi_prev"]), rsi[20])
        self.assertEqual(d["bars_apart"], 35)
        self.assertEqual(d["prev_pivot_ts"], 20 * TF)

    def test_a_lower_low_on_stronger_rsi_is_a_bullish_divergence(self):
        closes = ([Decimal(200)]
                  + leg(Decimal(200), Decimal(-2), 20)          # bars 1-20 -> 160
                  + leg(Decimal(160), Decimal(1), 15)           # bars 21-35 -> 175
                  + leg(Decimal(175), Decimal("-0.8"), 20))     # bars 36-55 -> 159
        self.load(closes)
        self.swing(20, "LOW", closes[20])
        self.swing(35, "HIGH", closes[35])
        self.swing(55, "LOW", closes[55])
        self.assertEqual(
            momentum.run(self.con, "BTC-USD", "1H", TF)["divergence"], 1)
        d = self.facts("DIVERGENCE")[0]
        self.assertEqual((d["divergence"], d["direction"]), ("BULLISH", "BULL"))
        self.assertLess(Decimal(d["price"]), Decimal(d["price_prev"]))
        self.assertGreater(Decimal(d["rsi"]), Decimal(d["rsi_prev"]))

    def test_price_and_rsi_agreeing_is_not_a_divergence(self):
        """A higher high on STRONGER momentum is a trend. The engine must not
        find a divergence in it — this is the assertion that separates
        'compares two pivots' from 'measures disagreement'."""
        # bars 1-20 saw +1.5 / -0.5 (RSI 75 at the peak: avg gain 0.75 against
        # avg loss 0.25, RS 3), then a decline, then a hard straight second leg
        # (RSI 100 — fourteen gains and no losses).
        saw = []
        price = Decimal(100)
        for i in range(1, 21):
            price += Decimal("1.5") if i % 2 == 0 else Decimal("-0.5")
            saw.append(price)
        closes = ([Decimal(100)] + saw
                  + leg(saw[-1], Decimal(-1), 15)
                  + leg(saw[-1] - 15, Decimal(2), 20))
        self.load(closes)
        self.swing(20, "HIGH", closes[20])
        self.swing(35, "LOW", closes[35])
        self.swing(55, "HIGH", closes[55])
        rsi = momentum.compute_rsi(closes)
        self.assertGreater(closes[55], closes[20])
        self.assertGreater(rsi[55], rsi[20])
        self.assertEqual(
            momentum.run(self.con, "BTC-USD", "1H", TF)["divergence"], 0)

    def test_pivots_too_far_apart_are_not_compared(self):
        """Two highs 120 bars apart are not one swing structure, whatever their
        RSI says. The horizon is liquidity.py's 100 bars."""
        closes = self._series() + leg(Decimal(141), Decimal("0.05"), 80)
        self.load(closes)
        self.swing(20, "HIGH", closes[20])
        self.swing(35, "LOW", closes[35])
        self.swing(130, "HIGH", closes[130])
        self.assertGreater(momentum.MAX_PIVOT_GAP_BARS, 0)
        self.assertEqual(
            momentum.run(self.con, "BTC-USD", "1H", TF)["divergence"], 0)

    def test_micro_pivots_are_not_divergence_material(self):
        closes = self._series()
        self.load(closes)
        for bar, kind in ((20, "HIGH"), (35, "LOW"), (55, "HIGH")):
            self.swing(bar, kind, closes[bar], tier="MICRO")
        self.assertEqual(
            momentum.run(self.con, "BTC-USD", "1H", TF)["divergence"], 0)


class TestCausality(MomentumCase):
    def test_an_indicator_fact_confirms_at_its_own_bar_close(self):
        self.load([Decimal(100) + Decimal("0.5") * i for i in range(60)])
        momentum.run(self.con, "BTC-USD", "1H", TF)
        facts = self.facts()
        self.assertTrue(facts)
        for f in facts:
            self.assertEqual(f["confirmed_at"], f["market_time"] + TF)

    def test_a_divergence_waits_for_both_of_its_pivots(self):
        """The second pivot confirms 30 bars after its own bar here. The
        divergence is not knowable until then, and it must not be backdated to
        the bar it happened on."""
        closes = self._series = ([Decimal(100)]
                                 + leg(Decimal(100), Decimal(2), 20)
                                 + leg(Decimal(140), Decimal(-1), 15)
                                 + leg(Decimal(125), Decimal("0.8"), 20))
        self.load(closes)
        self.swing(20, "HIGH", closes[20], lag=4)
        self.swing(35, "LOW", closes[35], lag=4)
        self.swing(55, "HIGH", closes[55], lag=30)
        momentum.run(self.con, "BTC-USD", "1H", TF)
        d = self.facts("DIVERGENCE")[0]
        self.assertEqual(d["market_time"], 55 * TF)
        self.assertEqual(d["confirmed_at"], 85 * TF)
        self.assertEqual(d["confirmation_lag_bars"], 29)
        # and the as_of cursor every consumer reads through agrees
        self.assertEqual(self.facts("DIVERGENCE", as_of=85 * TF - 1), [])
        self.assertEqual(len(self.facts("DIVERGENCE", as_of=85 * TF)), 1)

    def test_a_divergence_never_confirms_before_its_own_bar_closed(self):
        closes = ([Decimal(100)] + leg(Decimal(100), Decimal(2), 20)
                  + leg(Decimal(140), Decimal(-1), 15)
                  + leg(Decimal(125), Decimal("0.8"), 20))
        self.load(closes)
        self.swing(20, "HIGH", closes[20], lag=0)
        self.swing(35, "LOW", closes[35], lag=0)
        self.swing(55, "HIGH", closes[55], lag=0)
        momentum.run(self.con, "BTC-USD", "1H", TF)
        d = self.facts("DIVERGENCE")[0]
        self.assertEqual(d["confirmed_at"], 56 * TF)
        self.assertGreater(d["confirmed_at"], d["market_time"])


class TestDeterminism(MomentumCase):
    def _loaded(self):
        closes = ([Decimal(100)] + leg(Decimal(100), Decimal(2), 20)
                  + leg(Decimal(140), Decimal(-1), 15)
                  + leg(Decimal(125), Decimal("0.8"), 20))
        self.load(closes)
        self.swing(20, "HIGH", closes[20])
        self.swing(35, "LOW", closes[35])
        self.swing(55, "HIGH", closes[55])

    def test_rerun_writes_zero_new_facts(self):
        self._loaded()
        first = momentum.run(self.con, "BTC-USD", "1H", TF)
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        second = momentum.run(self.con, "BTC-USD", "1H", TF)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertGreater(sum(v for v in first.values() if isinstance(v, int)), 0)
        self.assertEqual(sum(v for v in second.values() if isinstance(v, int)), 0)
        self.assertEqual(before, after)

    def test_every_emitted_number_is_a_decimal_string(self):
        self._loaded()
        momentum.run(self.con, "BTC-USD", "1H", TF)
        for f in self.facts():
            for key in ("close", "rsi", "macd", "macd_signal", "macd_hist"):
                if f.get(key) is None:
                    continue
                self.assertNotIn("e", f[key].lower(), (f["event"], key))
                self.assertIsInstance(Decimal(f[key]), Decimal)
        d = self.facts("DIVERGENCE")[0]
        for key in ("price", "price_prev", "rsi", "rsi_prev", "rsi_delta"):
            self.assertNotIn("e", d[key].lower(), key)
        self.assertEqual(Decimal(d["rsi"]) - Decimal(d["rsi_prev"]),
                         Decimal(d["rsi_delta"]))


if __name__ == "__main__":
    unittest.main()
