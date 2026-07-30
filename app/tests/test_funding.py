"""Funding — the perp cost that was defined in S32 and never charged.

`venues.funding_cost_rate` shipped with its reasoning written out ("funding is
charged repeatedly, not once") and no caller. Every multi-day perp position was
therefore simulated as free to hold. Measured on the recorded book at the
modelled rate: 1D ~0.03 R, 1W ~0.12 R — small next to the 14x cost-profile error
of S37, but 0.03 R is roughly 17% of the 1D book's expectancy, and a cost that
only ever flatters is the kind that survives review.
"""
import unittest
from decimal import Decimal

from engine import execsim, venues


class Accrual(unittest.TestCase):
    def test_funding_scales_with_holding_time_not_charged_once(self):
        """The whole point of the S32 note. A position held three days pays
        three days of settlements, not one fee."""
        one = venues.funding_cost_rate("BTCUSDT", Decimal("0.0001"), Decimal(8))
        three_days = venues.funding_cost_rate("BTCUSDT", Decimal("0.0001"),
                                              Decimal(72))
        self.assertAlmostEqual(float(three_days / one), 9.0, places=6)

    def test_spot_pays_nothing_by_venue_declaration_not_by_a_branch(self):
        """Coinbase declares 0 settlements/day, so the same call returns zero on
        spot without execsim needing to know which venue it is looking at."""
        self.assertEqual(
            venues.funding_cost_rate("BTC-USD", Decimal("0.0001"), Decimal(240)),
            Decimal(0))

    def test_three_settlements_a_day_on_phemex(self):
        day = venues.funding_cost_rate("BTCUSDT", Decimal("0.001"), Decimal(24))
        self.assertEqual(day, Decimal("0.003"))


class ChargedInSimulation(unittest.TestCase):
    def test_execsim_actually_calls_it(self):
        """The regression that matters. The function existed for eight sessions
        with zero callers; a test that only checks the arithmetic would have
        passed the entire time it was doing nothing."""
        import inspect
        src = inspect.getsource(execsim.run)
        self.assertIn("funding_cost_rate", src,
                      "execsim must charge funding, not merely be able to")
        self.assertIn("holding_hours", src)

    def test_funding_is_added_to_fees_not_reported_beside_them(self):
        """If it were recorded but not summed into the cost of the trade, the
        fact would look right and the R would still be wrong."""
        import inspect
        src = inspect.getsource(execsim.run)
        self.assertRegex(src, r"fees\s*=.*\+\s*funding_cost",
                         "funding must enter the fee total that nets r_multiple")

    def test_the_modelled_rate_is_declared_as_a_model(self):
        """Real funding varies per settlement and this store holds no historical
        series. Using a constant is legitimate; calling it a measurement is not,
        so the constant is named for what it is."""
        self.assertTrue(hasattr(execsim, "FUNDING_RATE_PER_SETTLEMENT"))
        self.assertIn("MODELLED", inspect_source().upper())

    def test_it_is_charged_to_both_directions_deliberately(self):
        """In reality the paying side flips with the sign of the rate — a short
        RECEIVES funding when longs are paying. Charging both is the pessimistic
        reading, which is this engine's standing rule for costs."""
        src = inspect_source()
        self.assertNotIn("if long:\n                funding", src,
                         "funding must not branch on direction")


def inspect_source():
    import inspect
    return inspect.getsource(execsim)


class Magnitude(unittest.TestCase):
    def test_a_week_long_hold_costs_more_than_an_hour_long_one_by_far(self):
        hour = venues.funding_cost_rate("BTCUSDT",
                                        execsim.FUNDING_RATE_PER_SETTLEMENT,
                                        Decimal(1))
        week = venues.funding_cost_rate("BTCUSDT",
                                        execsim.FUNDING_RATE_PER_SETTLEMENT,
                                        Decimal(168))
        self.assertGreater(week, hour * 100)

    def test_the_modelled_rate_stays_conservative(self):
        """A rate low enough to be negligible would make this change cosmetic.
        0.01%/settlement is the figure S32 reasoned from and is in the range
        Phemex actually publishes."""
        self.assertGreaterEqual(execsim.FUNDING_RATE_PER_SETTLEMENT,
                                Decimal("0.00005"))
        self.assertLessEqual(execsim.FUNDING_RATE_PER_SETTLEMENT,
                             Decimal("0.001"))


if __name__ == "__main__":
    unittest.main()
