"""The one sanctioned duplicate, pinned by execution rather than by two
hand-copied numbers.

CLAUDE.md rule 9 allows exactly one re-derivation: `static/ticket-math.js`
re-implements `venues.liquidation_price` so the order ticket can warn without
a round trip. Until 2026-09-10 the pin was `test_ticket_math.js` asserting
90.5 / 109.5 / 50.5 against a hard-coded maintenance margin and
`test_venues.py` asserting the same 90.5 in Python — move
`venues.MAINTENANCE_MARGIN` and both stay green while the two formulas drift.

This runs the JS with the constants the server actually serves and compares
it to the Python over a grid.
"""
import json
import shutil
import subprocess
import unittest
from decimal import Decimal
from pathlib import Path

from engine import venues

APP = Path(__file__).resolve().parents[1]
GRID = [
    ("LONG", "100", "1"), ("LONG", "100", "2"), ("LONG", "100", "5"),
    ("LONG", "100", "10"), ("SHORT", "100", "2"), ("SHORT", "100", "10"),
    ("LONG", "0.5", "3"), ("SHORT", "25000", "4"), ("LONG", "3.75", "7"),
]


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class LiquidationContract(unittest.TestCase):
    def test_the_ticket_and_the_engine_agree_where_a_position_dies(self):
        script = r"""
        const tm = require(process.argv[1]);
        const grid = JSON.parse(process.argv[2]);
        const maint = Number(process.argv[3]);
        const out = grid.map(([dir, entry, lev]) => {
          const e = Number(entry), long = dir === 'LONG';
          const m = tm.ticketMath({dir, entry: e, tp: long ? e * 1.1 : e * 0.9,
                                   sl: long ? e * 0.99 : e * 1.01, equity: 10000,
                                   leverage: Number(lev),
                                   cfg: {risk_pct: 0.02, max_leverage: 50,
                                         max_total_risk_pct: 0.04, max_concurrent: 1,
                                         daily_loss_pct: 0.08,
                                         venue: {maintenance_margin: maint,
                                                 max_leverage: 50, allow_shorts: true},
                                         cost: {maker_rate: 0.0001, taker_rate: 0.0006,
                                                slippage_atr: 0.05}}});
          return m.liquidation;
        });
        process.stdout.write(JSON.stringify(out));
        """
        proc = subprocess.run(
            ["node", "-e", script, str(APP / "static" / "ticket-math.js"),
             json.dumps(GRID), str(venues.MAINTENANCE_MARGIN)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        js = json.loads(proc.stdout)
        self.assertEqual(len(js), len(GRID))
        for (direction, entry, lev), got in zip(GRID, js):
            want = venues.liquidation_price(Decimal(entry), Decimal(lev), direction)
            with self.subTest(direction=direction, entry=entry, leverage=lev):
                if want is None:
                    self.assertIsNone(got)
                    continue
                self.assertIsNotNone(got, "the ticket drew no liquidation line")
                # The JS works in floats; agree to a hundredth of a percent of
                # entry, which is far inside any tick the ticket can show.
                self.assertLess(abs(Decimal(str(got)) - want),
                                Decimal(entry) * Decimal("0.0001"),
                                f"ticket {got} vs engine {want}")


if __name__ == "__main__":
    unittest.main()
