"""Draft bracket tests — the properties that keep it honest.

The draft exists because the alternative was a ruler. These tests hold the two
things that make it better than one: it is anchored to a real level, and it
says None rather than inventing a level when there is nothing near price.
"""
import unittest
from decimal import Decimal

from engine import draft

ATR = Decimal(10)
PRICE = Decimal(100)


def zone(kind, bottom, top, state="FRESH", zid=None, strength=80):
    return {"zone_id": zid or f"Z|{kind}|{bottom}", "zone_type": kind,
            "bottom": str(bottom), "top": str(top), "state": state,
            "strength": strength}


def pool(side, level, state="ACTIVE", pid=None):
    return {"pool_id": pid or f"P|{side}|{level}", "side": side,
            "level": str(level), "state": state}


class DraftBracket(unittest.TestCase):

    def test_anchors_the_entry_to_the_zone_edge_not_to_price(self):
        """The whole point. The ruler put entry AT the last close; this puts it
        at a level the market has already reacted to."""
        d = draft.bracket([zone("DEMAND", 94, 97)], [], ATR, PRICE)
        self.assertEqual(d["direction"], "LONG")
        self.assertEqual(Decimal(d["entry"]), Decimal(97))     # top of demand
        self.assertNotEqual(Decimal(d["entry"]), PRICE)

    def test_stop_sits_beyond_the_far_edge_by_the_declared_buffer(self):
        d = draft.bracket([zone("DEMAND", 94, 97)], [], ATR, PRICE)
        # 94 - 0.25*10
        self.assertEqual(Decimal(d["sl"]), Decimal("91.50"))

    def test_target_is_the_nearest_unbroken_pool_it_would_run_into(self):
        pools = [pool("HIGH", 130), pool("HIGH", 110), pool("LOW", 80),
                 pool("HIGH", 105, state="BROKEN")]
        d = draft.bracket([zone("DEMAND", 94, 97)], pools, ATR, PRICE)
        self.assertEqual(Decimal(d["tp"]), Decimal(110), "nearest HIGH above entry")
        self.assertIsNotNone(d["pool_id"])

    def test_a_broken_pool_is_never_a_target(self):
        d = draft.bracket([zone("DEMAND", 94, 97)],
                          [pool("HIGH", 105, state="BROKEN")], ATR, PRICE)
        # falls back to 2R rather than aiming at a level already taken out
        self.assertIsNone(d["pool_id"])
        risk = Decimal(d["entry"]) - Decimal(d["sl"])
        self.assertEqual(Decimal(d["tp"]), Decimal(d["entry"]) + 2 * risk)

    def test_broken_zones_are_not_anchors(self):
        d = draft.bracket([zone("DEMAND", 94, 97, state="BROKEN")], [], ATR, PRICE)
        self.assertIsNone(d)

    def test_price_standing_inside_a_zone_is_the_nearest_thing_there_is(self):
        """Distance zero, and the case the draft most needs to handle: price in
        a demand zone is a live touch. The first cut tested `top <= price`, so
        a zone price was standing in matched nothing and the draft declined at
        exactly the moment it was useful."""
        inside = zone("DEMAND", 98, 103)          # price 100 sits within it
        d = draft.bracket([inside], [], ATR, PRICE)
        self.assertIsNotNone(d)
        self.assertEqual(Decimal(d["distance_atr"]), Decimal(0))
        self.assertEqual(Decimal(d["entry"]), Decimal(103))
        # and it beats a zone price is merely near
        d2 = draft.bracket([inside, zone("DEMAND", 94, 97, zid="near")],
                           [], ATR, PRICE)
        self.assertEqual(d2["zone_id"], inside["zone_id"])

    def test_price_below_a_demand_zone_is_not_an_anchor(self):
        """It did not hold. Entering at its top would be chasing a broken level
        rather than trading one."""
        self.assertIsNone(
            draft.bracket([zone("DEMAND", 110, 115)], [], ATR, PRICE))

    def test_returns_None_when_nothing_is_near_price(self):
        """'Price is not near anything this system recognises' is a real answer
        and a better one than a bracket drawn around a level 9 ATR away."""
        far = zone("DEMAND", 5, 8)             # ~9 ATR below a price of 100
        self.assertIsNone(draft.bracket([far], [], ATR, PRICE))

    def test_the_nearest_zone_wins_when_several_are_live(self):
        zones = [zone("DEMAND", 70, 75, zid="far"), zone("DEMAND", 94, 97, zid="near")]
        d = draft.bracket(zones, [], ATR, PRICE)
        self.assertEqual(d["zone_id"], "near")

    def test_supply_above_price_drafts_a_short(self):
        d = draft.bracket([zone("SUPPLY", 103, 106)], [], ATR, PRICE)
        self.assertEqual(d["direction"], "SHORT")
        self.assertEqual(Decimal(d["entry"]), Decimal(103))    # bottom of supply
        self.assertEqual(Decimal(d["sl"]), Decimal("108.50"))  # 106 + 0.25*10

    def test_a_spot_venue_is_never_drafted_a_short(self):
        """`venues.allow_shorts` is a venue capability, not a preference. A
        draft that suggests a trade the account cannot place is worse than no
        draft, because the ticket would then refuse it at arm time."""
        d = draft.bracket([zone("SUPPLY", 103, 106)], [], ATR, PRICE,
                          allow_shorts=False)
        self.assertIsNone(d)

    def test_missing_atr_or_price_yields_nothing_rather_than_a_guess(self):
        for atr, price in ((None, PRICE), (Decimal(0), PRICE), (ATR, None)):
            with self.subTest(atr=atr, price=price):
                self.assertIsNone(
                    draft.bracket([zone("DEMAND", 94, 97)], [], atr, price))

    def test_every_draft_says_what_it_stands_on(self):
        """`basis` is the thing the ruler could never provide — it had no
        reasoning to report. If a draft cannot explain itself it is a ruler
        with extra steps."""
        d = draft.bracket([zone("DEMAND", 94, 97)], [pool("HIGH", 110)], ATR, PRICE)
        self.assertTrue(d["basis"])
        self.assertTrue(any("DEMAND" in b for b in d["basis"]))
        self.assertTrue(any("pool" in b for b in d["basis"]))

    def test_the_draft_is_a_valid_ticket(self):
        """Whatever it produces must satisfy the ticket's own geometry rules,
        or the operator is handed a plan the Arm button will refuse."""
        for z, pools in ((zone("DEMAND", 94, 97), [pool("HIGH", 110)]),
                         (zone("SUPPLY", 103, 106), [pool("LOW", 90)])):
            with self.subTest(kind=z["zone_type"]):
                d = draft.bracket([z], pools, ATR, PRICE)
                e, sl, tp = (Decimal(d["entry"]), Decimal(d["sl"]),
                             Decimal(d["tp"]))
                if d["direction"] == "LONG":
                    self.assertLess(sl, e); self.assertGreater(tp, e)
                else:
                    self.assertGreater(sl, e); self.assertLess(tp, e)


if __name__ == "__main__":
    unittest.main()
