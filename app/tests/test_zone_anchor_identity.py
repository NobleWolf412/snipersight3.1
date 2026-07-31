"""A pivot's identity is (market_time, type) — one bar can host two pivots.

The S53 consumer hardening collapsed swing facts to one row per pivot so a
revised pivot could not count twice. Its first version keyed on market_time
ALONE, and one bar can legitimately carry BOTH a promoted HIGH and a promoted
LOW — the 2025-10-10 crash bar holds a MAJOR pair on three symbols. The later
row shadowed its twin: five supply zones store-wide were never created, and
the structure label walk lost one side of those bars. Caught in the first
live cycle after the collapse shipped; fixed in zone-v0.13 /
structure-v0.12 / liq-v0.11.

This test writes a same-bar HIGH+LOW pair and requires both sides to survive
into the two consumers where the shadowing was observed.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import store, structure, swings, zones

TF = 3600
SYMBOL, TFNAME = "BTC-USD", "1H"
ANCHOR_BAR = 20
MT = ANCHOR_BAR * TF


class SameBarPair(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")
        for i in range(40):
            close = Decimal("100.5") if i % 2 else Decimal("100.0")
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (SYMBOL, TFNAME, i * TF, str(close), str(close + 1),
                 str(close - 1), str(close), "1", "test", i * TF))
        # The pair: one bar, two promoted pivots, one per side. The LOW is
        # inserted second so it is the row a market_time-only collapse keeps —
        # exactly the ordering that shadowed the five live supply zones.
        for typ, price in (("HIGH", "101.5"), ("LOW", "99.0")):
            store.insert_fact(
                self.con, symbol=SYMBOL, tf=TFNAME, kind="swing",
                market_time=MT, confirmed_at=(ANCHOR_BAR + 4) * TF,
                algo_version=swings.SWING_VERSION,
                payload={"tier": "INTERMEDIATE", "type": typ, "price": price})
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_both_sides_anchor_a_zone(self):
        zones.run(self.con, SYMBOL, TFNAME, TF)
        created = set()
        for r in store.get_facts(self.con, SYMBOL, TFNAME, "zone",
                                 zones.ZONE_VERSION):
            p = json.loads(r["payload"])
            if p["event"] == "CREATED" and r["market_time"] == MT:
                created.add(p["zone_type"])
        self.assertEqual(created, {"SUPPLY", "DEMAND"},
                         "a same-bar HIGH+LOW pair must anchor one zone per "
                         "side — one twin shadowed the other")

    def test_both_sides_survive_the_structure_pivot_walk(self):
        got = {(s["market_time"], s["type"])
               for s in structure._tier_swings(self.con, SYMBOL, TFNAME)}
        self.assertEqual(got, {(MT, "HIGH"), (MT, "LOW")},
                         "the pivot collapse must key on (market_time, type)")


if __name__ == "__main__":
    unittest.main()
