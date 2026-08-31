"""Trail-only exit audition — the properties that keep its answer honest.

The module re-asks the §1.6 exit question on the continuation cohort using
abtest's own component switches, so the tests pin three things: that the
trail-only configuration really is trail-only (no partial sneaks in, no time
stop fires), that the pre-registered floor refuses a verdict below the house
bars and says so in the required words, and that the audition neither writes
facts nor grows a private simulation core beside the one abtest already paid
four drift incidents to retire.
"""
import inspect
import unittest
from decimal import Decimal

from engine import abtest, costs, execsim, risk, scalein, setups, trailexit

PROFILE = costs.CostProfile(version="test", venue="test", fee_tier="test",
                            maker_rate=Decimal(0), taker_rate=Decimal(0),
                            market_slippage_atr=Decimal(0))


def _bars(spec, start=1_600_000_000, step=86400):
    return [{"open_ts": start + i * step, "open": Decimal(o),
             "high": Decimal(h), "low": Decimal(lo), "close": Decimal(c),
             "volume": Decimal(1)}
            for i, (o, h, lo, c) in enumerate(spec)]


class TrailOnlyConfiguration(unittest.TestCase):
    """The switches must isolate the trail — a bundle verdict is not a
    component verdict, and that cuts both ways."""

    # entry 100, sl 90, risk 10, tp far at 200. Bar 1 runs to 2R (120) which
    # arms the trail at TRAIL_ACTIVATE_R=1.5 and sets it 0.5R below the
    # extreme: 115. Bar 2 trades down through 115.
    BARS = [(100, 101, 99, 100),        # fill bar
            (100, 120, 116, 119),       # extreme 120; trail moves to 115
            (118, 119, 114, 114),       # tags the trail
            (114, 115, 89, 90),         # would tag the ORIGINAL stop
            (90, 91, 89, 90)]

    def _run(self, **switches):
        c = _bars(self.BARS)
        atr = [Decimal(1)] * len(c)
        return abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                                Decimal(200), True, "1D", PROFILE,
                                managed=False, taker_in=False,
                                symbol="BTC-USD", tf_seconds=86400,
                                **switches)

    def test_the_trail_banks_what_the_hold_gives_back(self):
        """Zero-fee profile so the numbers are arithmetic: the trail exits at
        115 for +1.5R where hold-to-SL/TP rides the same bars down to the
        structural stop for -1.0R. This construction IS the continuation
        thesis — the favourable excursion comes first."""
        trail = self._run(partials=False, trail=True, timestop=False)
        self.assertEqual(trail["outcome"], "SL")
        self.assertEqual(trail["r"], Decimal("1.5"))
        hold = self._run()                       # all switches default off
        self.assertEqual(hold["outcome"], "SL")
        self.assertEqual(hold["r"], Decimal("-1"))

    def test_no_partial_is_booked_with_partials_off(self):
        """Bar 1 crosses TP1 (1.5R = 115). With partials disabled nothing may
        be banked there — a partial leaking in would grade the rejected §1.6
        bundle under the trail's name."""
        trail = self._run(partials=False, trail=True, timestop=False)
        self.assertEqual(trail["partials"], [])

    def test_no_time_stop_fires_with_timestop_off(self):
        """A quiet series longer than HOLD_BARS_BY_TF must stay open to the
        full engine window rather than time-stop — the time stop is a §1.6
        component and it is switched off here."""
        quiet = [(100, 101, 99, 100)] * (abtest.HOLD_BARS_BY_TF["1D"] + 5)
        c = _bars(quiet)
        atr = [Decimal(1)] * len(c)
        out = abtest._simulate(c, atr, 0, Decimal(100), Decimal(90),
                               Decimal(200), True, "1D", PROFILE,
                               managed=False, taker_in=False,
                               symbol="BTC-USD", tf_seconds=86400,
                               partials=False, trail=True, timestop=False)
        self.assertIsNone(out, "still open — a TIME outcome means the time "
                               "stop fired in a trail-only cell")


class PairedDelta(unittest.TestCase):
    def test_deltas_pair_on_setup_id_and_count_the_unpaired(self):
        hold = [{"setup_id": "a", "symbol": "S1", "filled": True,
                 "r": Decimal("-1")},
                {"setup_id": "b", "symbol": "S2", "filled": True,
                 "r": Decimal("0.5")},
                {"setup_id": "miss", "symbol": "S3", "filled": False}]
        trail = [{"setup_id": "a", "symbol": "S1", "filled": True,
                  "r": Decimal("1.5")},
                 {"setup_id": "only-trail", "symbol": "S4", "filled": True,
                  "r": Decimal("0.2")}]
        rows, unpaired = trailexit.paired_deltas(hold, trail)
        self.assertEqual(rows, [{"symbol": "S1", "r": 2.5}])
        self.assertEqual(unpaired, 2,
                         "a trade resolved in only one cell is counted, "
                         "never silently dropped")


class VerdictFloor(unittest.TestCase):
    """The pre-registered floor, held in place by words as well as logic."""

    OK = {"n": 50, "sample_ok": True, "expectancy_r": 0.2,
          "clears_zero": True}
    WEAK = {"n": 5, "sample_ok": False}

    def test_below_the_floors_the_required_sentence_appears(self):
        v = trailexit.verdict(self.OK, self.WEAK, self.WEAK)
        self.assertEqual(v["call"], "SAMPLE_TOO_SMALL")
        self.assertIn("hasn't proven anything yet", v["detail"])

    def test_beating_hold_without_clearing_zero_is_not_a_finding(self):
        trail = {"n": 50, "sample_ok": True, "expectancy_r": 0.1,
                 "clears_zero": False}
        hold = {"n": 50, "sample_ok": True, "expectancy_r": -0.1,
                "clears_zero": False}
        delta = {"n": 50, "sample_ok": True, "expectancy_r": 0.2,
                 "clears_zero": True}
        v = trailexit.verdict(hold, trail, delta)
        self.assertEqual(v["call"], "NOT_PROVEN")
        self.assertIn("hasn't proven anything yet", v["detail"])

    def test_clearing_zero_without_beating_hold_is_not_a_finding(self):
        trail = {"n": 50, "sample_ok": True, "expectancy_r": 0.1,
                 "clears_zero": True}
        hold = {"n": 50, "sample_ok": True, "expectancy_r": 0.3,
                "clears_zero": True}
        delta = {"n": 50, "sample_ok": True, "expectancy_r": -0.2,
                 "clears_zero": False}
        v = trailexit.verdict(hold, trail, delta)
        self.assertEqual(v["call"], "NOT_PROVEN")

    def test_the_floor_cleared_call_still_calls_itself_a_proposal(self):
        trail = {"n": 50, "sample_ok": True, "expectancy_r": 0.3,
                 "clears_zero": True}
        hold = {"n": 50, "sample_ok": True, "expectancy_r": -0.1,
                "clears_zero": False}
        delta = {"n": 50, "sample_ok": True, "expectancy_r": 0.4,
                 "clears_zero": True}
        v = trailexit.verdict(hold, trail, delta)
        self.assertEqual(v["call"], "FLOOR_CLEARED")
        self.assertIn("proposal", v["detail"],
                      "even a cleared floor promotes nothing by itself")


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("trailexit", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")

    def test_the_module_writes_nothing(self):
        src = inspect.getsource(trailexit)
        self.assertNotIn("insert_fact", src,
                         "the audition wrote a fact — it is no longer "
                         "derived at analysis time")
        self.assertIn("mode=ro", src,
                      "main() must open the store read-only")

    def test_no_private_simulation_core(self):
        """abtest paid four drift incidents for a private core; this audition
        may only configure the shared one."""
        src = inspect.getsource(trailexit)
        self.assertIn("run_variant", src)
        for private in ("def _simulate", "def simulate_entry",
                        "def walk_exit", "def settle"):
            self.assertNotIn(private, src)

    def test_the_recorded_2x2_is_untouched(self):
        """The audition must not redefine the cells the recorded verdicts came
        from — CELLS is abtest's history, not this module's input."""
        self.assertNotIn("CELLS", inspect.getsource(trailexit))


if __name__ == "__main__":
    unittest.main()
