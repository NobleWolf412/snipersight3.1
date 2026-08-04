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

    def test_round_trip_fee_is_the_house_model_not_taker_squared(self):
        """First live answer quoted taker x2 (0.120%) where the engine prices
        maker-in/taker-out (0.070%). Defensible worst case, wrong house number
        — the pack now states the model figure and names taker x2 as the worst
        case, so the copilot leads with the number the book is priced on."""
        pack = copilot.build_pack(self.con, "BTCUSDT", "1H")
        self.assertIn("ROUND-TRIP FEE: 0.070%", pack)
        self.assertIn("not taker x2", pack)
        self.assertIn("0.120%", pack)          # the worst case, named as such

    def test_an_engine_position_reaches_the_pack(self):
        """Every row in the Open Trades panel IS an engine position, and the
        pack only ever described the operator's own manual book — so a question
        asked from that panel reached a copilot that did not know the operator
        was in the trade, and it answered "should you take this" about a trade
        already taken."""
        self.load([(100, 100.5, 99.5, 100), (100, 104, 99, 103)])
        pos = {"direction": "LONG", "entry": "100", "sl": "98", "tp": "110",
               "risk_usd": "200", "setup_id": "S1"}
        pack = copilot.build_pack(self.con, "BTCUSDT", "1H", position=pos)
        self.assertIn("THE ENGINE HOLDS THIS TRADE", pack)
        self.assertIn("The question is NOT whether to enter", pack)
        # marked to the last CLOSED bar, like every other surface: 103 on a
        # 100 entry with a 2-wide stop is +1.50R
        self.assertIn("unrealized=1.50R", pack)

    def test_no_position_means_no_holding_claim(self):
        self.load([(100, 100.5, 99.5, 100)])
        pack = copilot.build_pack(self.con, "BTCUSDT", "1H")
        self.assertNotIn("THE ENGINE HOLDS THIS TRADE", pack)

    def test_a_position_with_an_unusable_stop_still_builds_a_pack(self):
        """A pack that raises is a chat box that will not open. The live R is
        the optional part; naming the position is not."""
        self.load([(100, 100.5, 99.5, 100)])
        pos = {"direction": "LONG", "entry": "100", "sl": "100", "tp": "110",
               "risk_usd": "200", "setup_id": "S1"}
        pack = copilot.build_pack(self.con, "BTCUSDT", "1H", position=pos)
        self.assertIn("THE ENGINE HOLDS THIS TRADE", pack)
        self.assertNotIn("unrealized=", pack)

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
