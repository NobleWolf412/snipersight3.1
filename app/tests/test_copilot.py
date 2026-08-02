"""Copilot pack tests — the analyst may only know what the store knows.

The subprocess side is deliberately untested here (it spends the operator's
subscription quota); what must hold is the pack: grounded, labelled, honest
about edge state, and safe when a chart has nothing on it.
"""
import tempfile
import unittest
from pathlib import Path

from engine import copilot, manual, store

TF = 3600


class PackCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, bars, symbol="BTCUSDT"):
        for i, (o, h, l, c) in enumerate(bars):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, "1H", i * TF, str(o), str(h), str(l), str(c),
                 "1", "test", i * TF))
        self.con.commit()

    def test_empty_chart_still_yields_an_honest_pack(self):
        """No candles, no facts — the pack must say so, not crash or invent."""
        pack = copilot.build_pack(self.con, "BTCUSDT", "1H")
        self.assertIn("phemex-perp", pack)
        self.assertIn("No engine setup exists", pack)
        self.assertIn("STRUCTURE DRAFT: none", pack)
        self.assertIn("NO strategy currently clears zero", pack)

    def test_pack_carries_venue_economics_and_the_edge_caveat(self):
        pack = copilot.build_pack(self.con, "BTC-USD", "1D")
        # spot: the copilot must know shorting is impossible and fees are 1%
        self.assertIn("coinbase-spot", pack)
        self.assertIn("not possible", pack)
        self.assertIn("The operator decides. You analyse.", pack)

    def test_open_manual_trade_reaches_the_pack(self):
        self.load([(100, 100.5, 99.5, 100), (100, 104, 99, 103)])
        manual.create_intent(self.con, "BTCUSDT", "1H", "LONG",
                             entry=100, tp=110, sl=95, created_at=0,
                             risk_usd=200)
        pack = copilot.build_pack(self.con, "BTCUSDT", "1H")
        self.assertIn("OPERATOR'S OPEN TRADE HERE", pack)
        self.assertIn("marked to last CLOSED bar", pack)

    def test_preamble_forbids_the_indicators_this_system_does_not_compute(self):
        """The single likeliest hallucination for a trading copilot is citing
        RSI on a platform that has never computed one."""
        self.assertIn("RSI", copilot.PREAMBLE)
        self.assertIn("does NOT compute", copilot.PREAMBLE)
        self.assertIn("observer", copilot.PREAMBLE.lower())

    def test_tool_denial_covers_the_dangerous_ones(self):
        for t in ("Bash", "Edit", "Write", "WebFetch"):
            self.assertIn(t, copilot.DENY_TOOLS)


if __name__ == "__main__":
    unittest.main()
