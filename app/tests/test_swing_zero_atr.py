"""A zero-quantized ATR must not crash the swing engine.

On an 8dp-quoted low-tick coin in a dead hour, a one-tick true range
Wilder-averages to ~1e-8/14 = 7e-10, which Q8 rounds to 0E-8: the bar is not
flat, but its recorded ATR is zero. The LOCAL promotion then computed
`reversal < 0.75 * 0` (False, since a strict fractal always reverses by at
least a tick) and fell straight into `reversal / atr` —
decimal.DivisionByZero, 1,151 ERROR rows in engine_runs (PF_PEPEUSD 5m
1,041, PF_SHIBUSD 5m 110), and no swing facts for either series past each
run's crash point.

The fix treats ATR==0 exactly like ATR==None — "no usable ATR measurement",
skip the ATR-normalized promotion, keep the micro fact — the same guard
ma.py applies to its ribbon distances. These tests pin:

  · the fixture genuinely reaches ATR==0E-8 at a swing bar (else the guard
    is untested and this file proves nothing);
  · the run completes, records the micro swings, and emits no LOCAL
    promotion for the zero-ATR swing (an undefined reversal-in-ATRs is not
    evidence, and threshold-0 would have promoted EVERY swing);
  · a re-run writes nothing (idempotence survives the guard);
  · once ATR becomes measurable later in the same series, promotions work
    again — the guard skips a bar, not the engine.

No version bump: the unguarded code CRASHED here, and RunRecorder commits
on the error path, so every fact v0.10 ever committed for these series is
byte-identical under the guard — the fix only adds facts where none could
exist. There is no second generation under the label.
"""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

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

    def test_fixture_reaches_zero_atr_at_the_swing_bar(self):
        self.load(self.tick_series())
        candles = [dict(r) for r in store.get_candles(self.con, "PF_PEPEUSD", TF)]
        atr = swings.compute_atr(candles)
        self.assertEqual(atr[16], Decimal("0E-8"),
                         "the one-tick TR must quantize to zero at Q8, or "
                         "nothing below exercises the guard")

    def test_run_completes_and_skips_the_undefined_promotion(self):
        self.load(self.tick_series())
        r = swings.run(self.con, "PF_PEPEUSD", TF, TFS)   # crashed before the fix
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
        swings.run(self.con, "PF_PEPEUSD", TF, TFS)
        r2 = swings.run(self.con, "PF_PEPEUSD", TF, TFS)
        self.assertEqual((r2["micro"], r2["local"]), (0, 0),
                         "idempotence must survive the guard")

    def test_atr_recovering_later_still_promotes(self):
        """The guard skips a bar, not the engine: append a volatile stretch
        after the dead hour and its swings must still reach LOCAL."""
        base = self.tick_series()
        # same coin, same scale — a 20-tick range is enough to keep the
        # Wilder average comfortably above Q8 (2e-7/14 ~ 1.4e-8 > 0E-8)
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
        self.assertGreater(atr[k], 0, "sanity: ATR must be measurable again")
        self.assertGreaterEqual(r["local"], 1,
                                "a measurable reversal after the dead hour "
                                "must still promote")


if __name__ == "__main__":
    unittest.main()
