"""Venue capabilities and the liquidation gate.

Regression cover for the defect this module exists to fix: `ALLOW_SHORTS` was a
process-wide `False`, so 31% of all validated setups (44 of 143 — every SHORT the
playbook produced) were rejected regardless of which venue they belonged to.
"""
import unittest
from decimal import Decimal

from engine import risk, venues

D = Decimal


class VenueResolutionTest(unittest.TestCase):
    def test_coinbase_spot_from_dashed_usd_symbol(self):
        v = venues.venue_for("BTC-USD")
        self.assertEqual(v.key, "coinbase-spot")
        self.assertFalse(v.allow_shorts, "spot cannot sell inventory it lacks")
        self.assertEqual(v.max_leverage, D("1"))

    def test_phemex_perp_from_usdt_symbol(self):
        v = venues.venue_for("BTCUSDT")
        self.assertEqual(v.key, "phemex-perp")
        self.assertTrue(v.allow_shorts)
        self.assertGreater(v.max_leverage, D("1"))

    def test_unknown_symbol_raises_rather_than_guessing(self):
        """Guessing a venue means guessing whether shorting is allowed."""
        for bad in ("", "BTC", "BTC/USD", "BTC-EUR", "BTCUSDC"):
            with self.assertRaises(ValueError, msg=bad):
                venues.venue_for(bad)

    def test_perp_flag(self):
        self.assertTrue(venues.venue_for("ETHUSDT").is_perp)
        self.assertFalse(venues.venue_for("ETH-USD").is_perp)


class ShortCapabilityTest(unittest.TestCase):
    def test_shorts_are_venue_derived_not_global(self):
        self.assertFalse(venues.allow_shorts("BTC-USD"))
        self.assertTrue(venues.allow_shorts("BTCUSDT"))

    def test_risk_helper_falls_back_to_refusing_the_short(self):
        """An unrecognised symbol must not be assumed shortable — that would
        record trades which could never have been placed."""
        self.assertFalse(risk._venue_allows_shorts("MYSTERY"))
        self.assertEqual(risk._venue_max_leverage("MYSTERY"), D("1"))

    def test_risk_helper_agrees_with_the_venue_table(self):
        self.assertFalse(risk._venue_allows_shorts("BTC-USD"))
        self.assertTrue(risk._venue_allows_shorts("BTCUSDT"))
        self.assertEqual(risk._venue_max_leverage("BTC-USD"), D("1"))


class LiquidationTest(unittest.TestCase):
    def test_no_liquidation_price_at_1x(self):
        self.assertIsNone(venues.liquidation_price(D("100"), D("1"), "LONG"))

    def test_long_liquidation_sits_below_entry(self):
        liq = venues.liquidation_price(D("100"), D("10"), "LONG")
        self.assertLess(liq, D("100"))
        # 1/10 minus 0.5% maintenance -> ~9.5% below
        self.assertAlmostEqual(float(liq), 90.5, places=6)

    def test_short_liquidation_sits_above_entry(self):
        liq = venues.liquidation_price(D("100"), D("10"), "SHORT")
        self.assertGreater(liq, D("100"))
        self.assertAlmostEqual(float(liq), 109.5, places=6)

    def test_maintenance_margin_makes_it_conservative(self):
        """Liquidation is modelled NEARER than the naive 1/leverage estimate.
        The failure to avoid is believing a stop is safe when it is not."""
        naive = D("100") * (D("1") - D("1") / D("10"))     # 90
        modelled = venues.liquidation_price(D("100"), D("10"), "LONG")
        self.assertGreater(modelled, naive)

    def test_spot_always_survives(self):
        ok, liq = venues.stop_survives_liquidation(D("100"), D("50"), D("1"), "LONG")
        self.assertTrue(ok)
        self.assertIsNone(liq)

    def test_stop_inside_liquidation_survives(self):
        # 10x long: liquidation ~90.5. A stop at 95 triggers first.
        ok, liq = venues.stop_survives_liquidation(D("100"), D("95"), D("10"), "LONG")
        self.assertTrue(ok)
        self.assertAlmostEqual(float(liq), 90.5, places=6)

    def test_stop_beyond_liquidation_is_refused_long(self):
        # a stop at 85 is past liquidation: the exchange closes first, for MORE
        # than the amount risked, and the R-multiple becomes fiction
        ok, liq = venues.stop_survives_liquidation(D("100"), D("85"), D("10"), "LONG")
        self.assertFalse(ok)

    def test_stop_beyond_liquidation_is_refused_short(self):
        ok, _ = venues.stop_survives_liquidation(D("100"), D("115"), D("10"), "SHORT")
        self.assertFalse(ok)

    def test_short_stop_inside_liquidation_survives(self):
        ok, _ = venues.stop_survives_liquidation(D("100"), D("105"), D("10"), "SHORT")
        self.assertTrue(ok)


class CostTest(unittest.TestCase):
    def test_perp_fees_are_cheaper_than_spot(self):
        """Not a preference — it is why perps can carry timeframes spot cannot."""
        self.assertLess(venues.round_trip_cost_rate("BTCUSDT"),
                        venues.round_trip_cost_rate("BTC-USD"))

    def test_spot_pays_no_funding(self):
        self.assertEqual(
            venues.funding_cost_rate("BTC-USD", D("0.0001"), D("24")), D("0"))

    def test_funding_accrues_per_settlement_not_once(self):
        """A perp held over a weekend pays every settlement. Charging it once
        would understate the cost of exactly the trades that hold longest."""
        one_day = venues.funding_cost_rate("BTCUSDT", D("0.0001"), D("24"))
        three_days = venues.funding_cost_rate("BTCUSDT", D("0.0001"), D("72"))
        self.assertAlmostEqual(float(one_day), 0.0003, places=9)   # 3 settlements
        self.assertAlmostEqual(float(three_days), float(one_day) * 3, places=9)

    def test_leverage_cap_is_conservative_against_the_venue_maximum(self):
        """Phemex permits 100x. Size here is derived from RISK, so a high cap
        adds no edge and only widens how badly a sizing mistake ends."""
        self.assertLessEqual(venues.PHEMEX_PERP.max_leverage, D("10"))


class VersionTest(unittest.TestCase):
    def test_risk_version_bumped_for_venue_derived_decisions(self):
        self.assertNotEqual(risk.RISK_VERSION, "risk-v0.6-draft")


class MultiVenueUniverseTest(unittest.TestCase):
    """Merged ranking must never expose the same underlying twice."""

    def setUp(self):
        from engine import universe
        self.u = universe

    def test_base_asset_extraction(self):
        self.assertEqual(self.u._base_asset("BTC-USD"), "BTC")
        self.assertEqual(self.u._base_asset("BTCUSDT"), "BTC")
        self.assertEqual(self.u._base_asset("ODDBALL"), "ODDBALL")

    def test_perp_wins_when_a_coin_trades_on_both(self):
        """Not a preference: 0.07% round-trip vs 1.00% flips a 0.1%-stop trade
        from -7.00R to +2.30R. Routing to spot would pick the losing version."""
        from unittest import mock
        with mock.patch.object(self.u, "rank_by_volume",
                               return_value=[("BTC-USD", 500.0), ("ACH-USD", 9.0)]), \
             mock.patch.object(self.u.phemex, "rank_by_volume",
                               return_value=[("BTCUSDT", 400.0)]):
            out = self.u.rank_all_venues()
        syms = [s for s, _ in out]
        self.assertIn("BTCUSDT", syms)
        self.assertNotIn("BTC-USD", syms, "same underlying listed twice")
        self.assertIn("ACH-USD", syms, "spot-only coin must be kept")

    def test_perp_ranking_failure_degrades_to_spot_only(self):
        from unittest import mock
        with mock.patch.object(self.u, "rank_by_volume",
                               return_value=[("BTC-USD", 500.0)]), \
             mock.patch.object(self.u.phemex, "rank_by_volume",
                               side_effect=RuntimeError("venue down")):
            out = self.u.rank_all_venues()
        self.assertEqual([s for s, _ in out], ["BTC-USD"])

    def test_perps_can_be_disabled(self):
        from unittest import mock
        with mock.patch.object(self.u, "ENABLE_PERPS", False), \
             mock.patch.object(self.u, "rank_by_volume",
                               return_value=[("BTC-USD", 500.0)]), \
             mock.patch.object(self.u.phemex, "rank_by_volume",
                               return_value=[("BTCUSDT", 900.0)]):
            out = self.u.rank_all_venues()
        self.assertEqual([s for s, _ in out], ["BTC-USD"])


if __name__ == "__main__":
    unittest.main()
