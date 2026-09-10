"""A zero ATR must not crash the swing engine — and the artefact that first
produced one is gone.

ORIGINALLY: on an 8dp-quoted low-tick coin in a dead hour, a one-tick true
range Wilder-averages to ~1e-8/14 = 7e-10, which a FIXED Q8 rounds to 0E-8 —
the bar is not flat, but its recorded ATR is zero. The LOCAL promotion then
computed `reversal < 0.75 * 0` (False, since a strict fractal always reverses
by at least a tick) and fell straight into `reversal / atr` —
decimal.DivisionByZero, 1,151 ERROR rows in engine_runs (PF_PEPEUSD 5m 1,041,
PF_SHIBUSD 5m 110), and no swing facts for either series past each crash.

The guard treats ATR==0 exactly like ATR==None — "no usable ATR measurement",
skip the ATR-normalized promotion, keep the micro fact.

SINCE swing-v0.11 the quantum follows the price scale (`scale_quantum`), so
that same fixture measures 7.1429E-10 instead of 0E-8 and the artefact cannot
recur. A zero ATR is now only what it always claimed to be: a market that did
not move at all. That is still reachable — and a fractal bar's own true range
is never zero, so no candle series can put a zero ATR *at a swing bar* any
more. The guard is therefore exercised here by feeding it the zero directly,
which is the honest way to test a guard whose trigger has become unreachable
by accident.

These tests pin:

  · the old artefact is gone, and the value it now carries is a real one;
  · a genuinely flat market still measures exactly zero;
  · handed a zero ATR at a swing bar, the run completes, records the micro
    swings, and emits no LOCAL promotion (an undefined reversal-in-ATRs is
    not evidence, and threshold-0 would have promoted EVERY swing);
  · a re-run writes nothing (idempotence survives the guard);
  · once ATR is measurable, promotions work — the guard skips a bar, not
    the engine.
"""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import store, swings  # noqa: E402

TF, TFS = "5m", 300
T0 = 1_700_000_000


class ZeroAtrDoesNotCrash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, spec, symbol="PF_PEPEUSD"):
        for i, (o, h, l, c) in enumerate(spec):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, TF, T0 + i * TFS, o, h, l, c, "10", "test", i))
        self.con.commit()

    @staticmethod
    def tick_series():
        """25 bars at 0.00000100 with a one-tick fractal HIGH at bar 16 and a
        one-tick fractal LOW at bar 20 — the PF_PEPEUSD 5m dead-hour shape."""
        base, hi, lo = "0.00000100", "0.00000101", "0.00000099"
        return [(base,
                 hi if i == 16 else base,
                 lo if i == 20 else base,
                 base) for i in range(25)]

    @staticmethod
    def zero_atr(candles):
        """What the engine used to be handed by its own quantum."""
        return [None] * swings.ATR_PERIOD + \
               [Decimal(0)] * (len(candles) - swings.ATR_PERIOD)

    def test_the_quantization_artefact_is_gone(self):
        """swing-v0.11. The same dead-hour series that used to record 0E-8
        now records the measurement it actually made."""
        self.load(self.tick_series())
        candles = [dict(r) for r in store.get_candles(self.con, "PF_PEPEUSD", TF)]
        atr = swings.compute_atr(candles)
        self.assertGreater(atr[16], 0,
                           "a bar that moved a tick must not measure zero ATR")
        self.assertEqual(atr[16].quantize(swings.Q8), Decimal("0E-8"),
                         "sanity: this is exactly the value the old fixed "
                         "quantum threw away")
        self.assertEqual(len(atr[16].as_tuple().digits), swings.MIN_SIG,
                         "the quantum follows the price scale")

    def test_a_flat_market_still_measures_exactly_zero(self):
        """The guard's remaining real trigger: nothing moved, so there is no
        range to average. Scale-free rounding cannot invent one."""
        flat = [("0.00000100",) * 4] * 25
        self.load(flat, symbol="FLATUSDT")
        candles = [dict(r) for r in store.get_candles(self.con, "FLATUSDT", TF)]
        atr = swings.compute_atr(candles)
        self.assertEqual(atr[16], Decimal(0))

    def test_a_zero_atr_at_a_swing_bar_skips_the_undefined_promotion(self):
        self.load(self.tick_series())
        with mock.patch.object(swings, "compute_atr", self.zero_atr):
            r = swings.run(self.con, "PF_PEPEUSD", TF, TFS)   # crashed before the guard
        self.assertEqual(r["micro"], 2,
                         "both fractal swings are still recorded as MICRO")
        self.assertEqual(r["local"], 0,
                         "a reversal in ATRs is undefined at ATR==0; with the "
                         "old threshold-0 comparison every swing would promote")
        for row in store.get_facts(self.con, "PF_PEPEUSD", TF, "swing",
                                   swings.SWING_VERSION):
            payload = json.loads(row["payload"])
            self.assertEqual(payload["tier"], "MICRO")
            self.assertEqual(Decimal(payload["atr"]), Decimal(0),
                             "the zero ATR is recorded on the fact, not hidden")

    def test_rerun_writes_nothing(self):
        self.load(self.tick_series())
        with mock.patch.object(swings, "compute_atr", self.zero_atr):
            swings.run(self.con, "PF_PEPEUSD", TF, TFS)
            r2 = swings.run(self.con, "PF_PEPEUSD", TF, TFS)
        self.assertEqual((r2["micro"], r2["local"]), (0, 0),
                         "idempotence must survive the guard")

    def test_atr_recovering_later_still_promotes(self):
        """The guard skips a bar, not the engine: append a volatile stretch
        after the dead hour and its swings must still reach LOCAL."""
        base = self.tick_series()
        # same coin, same scale — a 20-tick range is enough to keep the
        # Wilder average comfortably measurable
        volatile = [("0.00000100", "0.00000110", "0.00000090",
                     "0.00000100")] * 40
        k = len(base) + 20
        volatile[20] = ("0.00000100", "0.00000150", "0.00000090",
                        "0.00000100")                 # fractal HIGH at bar k
        volatile[24] = ("0.00000100", "0.00000110", "0.00000050",
                        "0.00000100")                 # fractal LOW, > 0.75 ATR away
        self.load(base + volatile)
        r = swings.run(self.con, "PF_PEPEUSD", TF, TFS)
        candles = [dict(r_) for r_ in store.get_candles(self.con, "PF_PEPEUSD", TF)]
        atr = swings.compute_atr(candles)
        self.assertGreater(atr[k], 0, "sanity: ATR must be measurable")
        self.assertGreaterEqual(r["local"], 1,
                                "a measurable reversal after the dead hour "
                                "must still promote")


if __name__ == "__main__":
    unittest.main()
