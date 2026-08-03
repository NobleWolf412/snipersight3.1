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
        # The charge moved into execsim.settle when the walk was extracted, so
        # the 2x2 harness charges it too — it never had. The property under
        # guard is unchanged; it just decomposed: settle charges it, and run()
        # must settle through THE costing function. Both hops asserted.
        self.assertIn("funding_cost_rate", inspect.getsource(execsim.settle),
                      "execsim must charge funding, not merely be able to")
        self.assertIn("holding_hours", inspect.getsource(execsim.settle))
        self.assertIn("settle(", inspect.getsource(execsim.run),
                      "run() must settle through THE costing function")

    def test_funding_is_deducted_from_net_not_merely_recorded(self):
        """If it were recorded but not subtracted, the fact would look right and
        the R would still be wrong.

        Asserted on the ARITHMETIC of a real simulated trade rather than on the
        source text. The previous version matched `fees = ... + funding_cost`,
        which forced funding to be folded into `fees_price_units` — a field that
        also has `funding_price_units` beside it, so any consumer summing the
        two double-counted funding. Splitting the labels is correct; what must
        never change is that BOTH reach the net.
        """
        import json
        import tempfile
        from decimal import Decimal as D
        from pathlib import Path
        from engine import store, setups as _setups

        tmp = tempfile.TemporaryDirectory()
        con = store.connect(Path(tmp.name) / "f.db")
        try:
            sym = "SOLUSDT"                       # a perp: funding is non-zero
            for ts, o, h, lo, c in ((0, 100, 110, 90, 100), (3600, 101, 104, 99, 102),
                                    (7200, 102, 106, 100, 105), (10800, 100, 101, 94, 95)):
                con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (sym, "1H", ts, str(o), str(h), str(lo), str(c), "10",
                             "phemex", ts + 60))
            store.insert_fact(
                con, symbol=sym, tf="1H", kind="setup", market_time=0,
                confirmed_at=3600, algo_version=_setups.SETUP_VERSION,
                payload={"setup_id": "s1", "strategy": "PULLBACK",
                         "direction": "LONG", "entry": "100", "sl": "95",
                         "tp": "115", "rr": "3", "rank": 50, "state": "VALIDATED"})
            execsim.run(con, sym, "1H", 3600)
            p = json.loads(store.get_facts(
                con, sym, "1H", "exec", execsim.EXEC_VERSION)[0]["payload"])

            funding = D(p["funding_price_units"])
            self.assertGreater(funding, 0, "a perp trade must accrue funding")

            entry, eff_exit = D(p["entry"]), D(p["effective_exit_price"])
            fees, risk = D(p["fees_price_units"]), entry - D("95")
            # Compared on the R scale, which is where r_multiple is rounded.
            # Converting back to price units first would multiply that rounding
            # by `risk` and manufacture a mismatch that is not there.
            expected_r = ((eff_exit - entry) - fees - funding) / risk
            self.assertAlmostEqual(float(D(p["r_multiple"])), float(expected_r),
                                   places=2, msg="funding did not reach r_multiple")

            # and dropping funding would visibly change the answer
            without_r = ((eff_exit - entry) - fees) / risk
            self.assertNotEqual(expected_r, without_r,
                                "funding term has no effect on the result")
        finally:
            con.close()
            tmp.cleanup()

    def test_fees_and_funding_are_reported_as_separate_costs(self):
        """Two fields, two costs. `fees_price_units` containing funding while
        `funding_price_units` reports it again is a double-count waiting for a
        consumer to sum them."""
        import inspect
        src = inspect.getsource(execsim.settle)      # the costing moved here
        self.assertNotRegex(src, r"fees\s*=[^\n]*\+\s*funding",
                            "funding must not be folded into the fee field")
        self.assertRegex(src, r"-\s*fees\s*-\s*funding",
                         "net must still deduct both")

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
