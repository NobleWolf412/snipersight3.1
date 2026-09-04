"""HTF context (engine/htfread.py): the zone above a setup, and the target the
regime would choose. Pure-context tests first — the as-of and nearest-rung
rules are what a later playbook will be allowed to trust."""
import unittest
from decimal import Decimal

from engine import htfread as hr


def _zone(zid, zt, bottom, top, created_at, broken_at=None):
    return {"zone_id": zid, "zone_type": zt, "bottom": Decimal(bottom),
            "top": Decimal(top), "created_at": created_at, "broken_at": broken_at}


def _pool(pid, side, level, confirmed_at, broken_at=None):
    return {"pool_id": pid, "side": side, "level": Decimal(level),
            "confirmed_at": confirmed_at, "broken_at": broken_at}


def _range(rid, bottom, top, formed_at, broken_at=None):
    return {"range_id": rid, "bottom": Decimal(bottom), "top": Decimal(top),
            "formed_at": formed_at, "broken_at": broken_at}


class HtfZone(unittest.TestCase):
    def setUp(self):
        self.ctx = hr.HtfContext(
            "15m",
            zones_by_rung={"1H": [_zone("h1", "SUPPLY", "100", "102", created_at=10),
                                  _zone("h2", "SUPPLY", "200", "203", created_at=10, broken_at=50)],
                           "4H": [_zone("f1", "SUPPLY", "99", "104", created_at=5),
                                  _zone("f2", "DEMAND", "90", "95", created_at=5)]},
            pools_by_rung={"1H": [_pool("p1", "HIGH", "110", confirmed_at=10)],
                           "4H": [_pool("p2", "HIGH", "120", confirmed_at=5),
                                  _pool("p3", "HIGH", "105", confirmed_at=5, broken_at=40)]},
            ranges=[_range("r1", "80", "120", formed_at=10)])

    def test_the_nearest_rung_wins_when_both_intersect(self):
        z = self.ctx.htf_zone_at("SUPPLY", "101", "101.5", as_of=60)
        self.assertEqual((z["tf"], z["zone_id"]), ("1H", "h1"))

    def test_intersection_not_containment(self):
        # a 15m band poking out of the 1H band still counts
        z = self.ctx.htf_zone_at("SUPPLY", "101.9", "103", as_of=60)
        self.assertEqual(z["zone_id"], "h1")

    def test_same_type_only(self):
        self.assertIsNone(self.ctx.htf_zone_at("DEMAND", "101", "101.5", as_of=60))
        self.assertEqual(self.ctx.htf_zone_at("DEMAND", "92", "93", as_of=60)["zone_id"], "f2")

    def test_a_zone_not_yet_created_or_already_broken_is_invisible(self):
        self.assertIsNone(self.ctx.htf_zone_at("SUPPLY", "101", "101.5", as_of=3))
        self.assertIsNone(self.ctx.htf_zone_at("SUPPLY", "201", "202", as_of=60))
        self.assertEqual(self.ctx.htf_zone_at("SUPPLY", "201", "202", as_of=20)["zone_id"], "h2")

    def test_falls_through_to_the_second_rung(self):
        z = self.ctx.htf_zone_at("SUPPLY", "103.5", "103.8", as_of=60)
        self.assertEqual((z["tf"], z["zone_id"]), ("4H", "f1"))


class NextPoolAndRange(unittest.TestCase):
    def setUp(self):
        HtfZone.setUp(self)

    def test_the_nearest_unbroken_htf_pool_beyond_the_structure_target(self):
        level, rung = self.ctx.next_htf_pool("LONG", beyond="108", as_of=60)
        self.assertEqual((level, rung), (Decimal("110"), "1H"))
        # p3 at 105 is broken by 40; p2 at 120 on 4H is the next beyond 115
        level, rung = self.ctx.next_htf_pool("LONG", beyond="115", as_of=60)
        self.assertEqual((level, rung), (Decimal("120"), "4H"))
        level, rung = self.ctx.next_htf_pool("LONG", beyond="104", as_of=20)
        self.assertEqual((level, rung), (Decimal("110"), "1H"))

    def test_no_pool_beyond_is_none(self):
        self.assertEqual(self.ctx.next_htf_pool("LONG", beyond="130", as_of=60), (None, None))

    def test_the_range_containing_the_entry(self):
        self.assertEqual(self.ctx.range_at("100", as_of=60)["range_id"], "r1")
        self.assertIsNone(self.ctx.range_at("130", as_of=60))
        self.assertIsNone(self.ctx.range_at("100", as_of=5))


class TargetAlt(unittest.TestCase):
    def setUp(self):
        HtfZone.setUp(self)

    def test_with_an_impulse_the_target_goes_to_the_next_htf_pool(self):
        alt, src = hr.target_alt(self.ctx, direction="LONG", entry="100", sl="98",
                                 tp="108", phase="IMPULSE_UP", as_of=60)
        self.assertEqual((alt, src), (Decimal("110"), "HTF_POOL_1H"))

    def test_against_an_impulse_the_structure_target_stands(self):
        alt, src = hr.target_alt(self.ctx, direction="SHORT", entry="100", sl="102",
                                 tp="92", phase="IMPULSE_UP", as_of=60)
        self.assertEqual((alt, src), (None, None))

    def test_in_drift_or_range_the_target_is_the_range_edge(self):
        alt, src = hr.target_alt(self.ctx, direction="LONG", entry="100", sl="98",
                                 tp="108", phase="DRIFT_DOWN", as_of=60)
        self.assertEqual((alt, src), (Decimal("120"), "RANGE_EDGE"))
        alt, src = hr.target_alt(self.ctx, direction="SHORT", entry="100", sl="102",
                                 tp="92", phase="RANGE", as_of=60)
        self.assertEqual((alt, src), (Decimal("80"), "RANGE_EDGE"))

    def test_no_phase_means_no_alternative(self):
        self.assertEqual(hr.target_alt(self.ctx, direction="LONG", entry="100", sl="98",
                                       tp="108", phase=None, as_of=60), (None, None))


if __name__ == "__main__":
    unittest.main()
