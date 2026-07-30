"""A fact stamped `confirmed_at = T` may not depend on anything after T.

`zones.run` computed a zone's creation-time cluster count over EVERY swing in
the series, with no `confirmed_at` filter — while writing the resulting fact
with `confirmed_at = s["confirmed_at"]`. So a zone created in 2023 could be
rated on swings from 2025.

It mattered because the number is load-bearing. `formation_quality` feeds
`strength`, and `strength` is one of the four evidence components the REVERSAL
playbook counts (`setups.reversal_evidence`, `REVERSAL_MIN_ZONE_STRENGTH`).
A quality computed from the future fed straight into which setups exist.

Measured before the fix (12 symbols x 4H/1D/1W, 2,006 zones): 159 (7.9%)
counted future swings; 96 of those got a different `formation_quality`, and the
shipped value was HIGHER in every single case — 75->65, 90->60, 95->65. Worst
observed: quality 90 from a cluster of 18, of which zero were knowable at that
zone's own creation time. The bias had one direction, and it was flattering.

The first test is the general invariant, applied to the engine that broke it.
The second is the specific regression, constructed so the two answers must
differ.
"""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import store, zones  # noqa: E402
from engine.swings import SWING_VERSION, compute_atr  # noqa: E402


class ZoneClusterIsCausal(unittest.TestCase):
    def test_cluster_ignores_swings_confirmed_after_the_zone(self):
        """Constructed: three lows in one band, the third confirmed LATER.

        The band is built from the first low. The second is knowable at
        creation, the third is not. A causal cluster sees 1; the buggy one saw
        2, and `formation_quality` differs by a full 10 points.
        """
        swings = [
            {"market_time": 100, "confirmed_at": 110, "type": "LOW", "price": Decimal("100")},
            {"market_time": 105, "confirmed_at": 108, "type": "LOW", "price": Decimal("101")},
            {"market_time": 900, "confirmed_at": 950, "type": "LOW", "price": Decimal("101")},
        ]
        anchor = swings[0]
        bottom, top = Decimal("100"), Decimal("110")

        def cluster(causal):
            return sum(1 for m, o in enumerate(swings)
                       if m != 0 and bottom <= o["price"] <= top
                       and (not causal or o["confirmed_at"] <= anchor["confirmed_at"]))

        self.assertEqual(cluster(causal=False), 2, "sanity: the old count saw both")
        self.assertEqual(cluster(causal=True), 1, "the future swing must not count")
        self.assertNotEqual(zones.formation_quality(2, "1D"),
                            zones.formation_quality(1, "1D"),
                            "if quality did not move, this test proves nothing")

    def test_source_applies_the_confirmed_at_filter(self):
        src = (APP / "engine" / "zones.py").read_text(encoding="utf-8")
        i = src.index("cluster = sum(")
        expr = src[i:i + 400]
        self.assertIn("confirmed_at", expr,
                      "the cluster count must filter on confirmed_at, or it "
                      "reads the future")


class RecordedZonesAreCausal(unittest.TestCase):
    """Store-level: recompute each zone's cluster causally and require a match.

    Skips on a clean checkout. On a real store this is the check that would
    have caught the defect the day zones.py shipped.
    """

    @classmethod
    def setUpClass(cls):
        if not (APP / "data" / "snipersight.db").exists():
            raise unittest.SkipTest("no live store")
        cls.con = store.connect()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "con"):
            cls.con.close()

    def test_no_zone_counts_a_swing_it_could_not_see(self):
        syms = [r[0] for r in self.con.execute(
            "SELECT DISTINCT symbol FROM candles WHERE tf='1D' "
            "ORDER BY symbol LIMIT 6").fetchall()]
        bad, checked = [], 0
        for sym in syms:
            for tf in ("4H", "1D"):
                candles = [dict(r) for r in store.get_candles(self.con, sym, tf)]
                if len(candles) < 30:
                    continue
                idx = {c["open_ts"]: i for i, c in enumerate(candles)}
                atr = compute_atr(candles)
                sw = []
                for r in store.get_facts(self.con, sym, tf, "swing", SWING_VERSION):
                    p = json.loads(r["payload"])
                    if p["tier"] in zones.ZONE_TIERS:
                        sw.append((r["market_time"], r["confirmed_at"],
                                   p["type"], Decimal(p["price"])))
                bands = []
                for mt, _ca, ty, px in sw:
                    i = idx.get(mt)
                    if i is None or atr[i] is None:
                        bands.append(None)
                        continue
                    w = zones.ZONE_ATR * atr[i]
                    bands.append(("DEMAND", px, px + w) if ty == "LOW"
                                 else ("SUPPLY", px - w, px))
                for k, (mt, ca, _ty, _px) in enumerate(sw):
                    if bands[k] is None:
                        continue
                    kind, bot, top = bands[k]
                    causal = sum(1 for m, (_m2, ca2, _t2, px2) in enumerate(sw)
                                 if m != k and bands[m] and bands[m][0] == kind
                                 and bot <= px2 <= top and ca2 <= ca)
                    row = self.con.execute(
                        "SELECT payload FROM facts WHERE symbol=? AND tf=? "
                        "AND kind='zone' AND algo_version=? AND market_time=? "
                        "AND json_extract(payload,'$.event')='CREATED' LIMIT 1",
                        (sym, tf, zones.ZONE_VERSION, mt)).fetchone()
                    if not row:
                        continue
                    checked += 1
                    rec = json.loads(row[0])["cluster_members"]
                    if rec != causal:
                        bad.append((sym, tf, mt, rec, causal))
        if not checked:
            self.skipTest(f"no {zones.ZONE_VERSION} zone facts yet — "
                          f"re-run the zone engine to populate them")
        self.assertFalse(bad, (
            f"{len(bad)} of {checked} recorded zones have a cluster count that "
            f"differs from the causal one — the engine is reading the future. "
            f"First few (symbol, tf, market_time, recorded, causal): {bad[:5]}"))


if __name__ == "__main__":
    unittest.main()
