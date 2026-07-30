"""Cost profiles are venue facts, not a process global.

Regression cover for the defect this change exists to fix: `execsim` and the
`setups` economic gate both charged `costs.DEFAULT_COST_PROFILE`
(coinbase-retail-v1, 0.40%/0.60%) to every symbol, while the traded book was
mostly Phemex USDT perps whose real round trip is 0.07% rather than 1.00%. The
consequences were two, and the second is the worse one:
  * every recorded perp trade was over-charged ~14x on fees;
  * the pre-trade gate used the same profile, so perp setups were rejected for
    being uneconomic against fees their venue never charges.
"""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import costs, execsim, scalein, setups, store, venues

D = Decimal

# The cost manifest hash carried by the 232 exec-v0.7-draft facts already in the
# live store. It is load-bearing: those facts reference it as their proof of what
# they were charged, so coinbase-retail-v1's payload must stay byte-identical.
COINBASE_V1_MANIFEST = \
    "d0dd32c4689a3af1a3dcc8dba3b918c30bbfe4cd546c152aaceecbc06be56319"


def candle(con, symbol, tf, ts, o, h, lo, c, volume="10"):
    con.execute(
        "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
        (symbol, tf, ts, str(o), str(h), str(lo), str(c), volume,
         "phemex", ts + 60))


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.con = store.connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class ProfileResolutionTest(unittest.TestCase):
    def test_symbol_selects_its_own_venues_profile(self):
        self.assertEqual(costs.profile_for("BTC-USD").version,
                         "coinbase-retail-v1")
        self.assertEqual(costs.profile_for("SOLUSDT").version,
                         "phemex-perp-v1")

    def test_profile_matches_the_venue_it_claims_to_price(self):
        """One authority per number (§6): the profile must not restate a rate."""
        for venue in venues.ALL:
            p = costs.by_version(venue.cost_profile)
            self.assertEqual(p.maker_rate, venue.maker_rate, venue.key)
            self.assertEqual(p.taker_rate, venue.taker_rate, venue.key)
            self.assertEqual(p.market_slippage_atr, venue.slippage_atr, venue.key)

    def test_perp_round_trip_is_cheaper_than_spot(self):
        perp, spot = costs.profile_for("SOLUSDT"), costs.profile_for("BTC-USD")
        self.assertLess(perp.maker_rate + perp.taker_rate,
                        spot.maker_rate + spot.taker_rate)

    def test_unknown_symbol_raises_rather_than_charging_a_default(self):
        """Falling back to a default profile is the original bug. A wrong fee is
        not a safer answer than a loud failure."""
        for bad in ("", "MYSTERY", "BTC/USD", "BTCUSDC"):
            with self.assertRaises(ValueError, msg=bad):
                costs.profile_for(bad)

    def test_unknown_profile_version_raises(self):
        with self.assertRaises(ValueError):
            costs.by_version("kraken-retail-v9")


class ImmutabilityTest(unittest.TestCase):
    def test_coinbase_profile_hash_is_unchanged(self):
        """The 232 existing exec facts reference this hash. Deriving the profile
        from venues.COINBASE_SPOT would have rewritten the `venue` label and
        invalidated every one of them."""
        canonical = store.canonical_payload(costs.DEFAULT_COST_PROFILE.payload())
        digest = hashlib.sha256(f"cost_profile|{canonical}".encode()).hexdigest()
        self.assertEqual(digest, COINBASE_V1_MANIFEST)

    def test_profiles_are_frozen(self):
        with self.assertRaises(Exception):
            costs.PHEMEX_PERP_COST_PROFILE.maker_rate = D("0.99")

    def test_drift_between_profile_and_venue_is_caught(self):
        """Editing a rate in venues.py without minting a new profile version is
        the mistake the import-time guard exists to catch."""
        drifted = venues.Venue(
            **{**venues.COINBASE_SPOT.__dict__, "maker_rate": D("0.0099")})
        with self.assertRaises(AssertionError):
            costs._assert_venue_rates(costs.DEFAULT_COST_PROFILE, drifted)

    def test_round_trip_cost_requires_an_explicit_profile(self):
        """No default argument: charging the wrong venue must not be the path of
        least resistance for a caller."""
        with self.assertRaises(TypeError):
            costs.estimated_round_trip_cost(D("100"), D("10"))


class EconomicGateTest(unittest.TestCase):
    """The gate is `risk >= 2 x estimated_round_trip_cost`. On the wrong profile
    a perp needed a ~14x wider stop before it counted as economic."""

    def test_perp_gate_is_cheaper_to_clear_than_spot_gate(self):
        entry, atr = D("100"), D("1")
        perp = costs.estimated_round_trip_cost(
            entry, atr, costs.profile_for("SOLUSDT"))
        spot = costs.estimated_round_trip_cost(
            entry, atr, costs.profile_for("BTC-USD"))
        self.assertLess(perp, spot)

    def test_setup_economic_on_its_own_venue_was_rejected_on_coinbase_costs(self):
        """The behavioural defect, stated as arithmetic.

        A stop 0.30 wide on a 100-priced perp with no ATR slippage term: the
        Phemex round trip is 0.07 so the gate needs 0.14 and the setup passes.
        The Coinbase round trip is 1.00 so the gate needed 2.00 and it failed.
        """
        entry, atr, risk = D("100"), D("0"), D("0.30")
        k = setups.MIN_RISK_COST_MULT
        perp_required = k * costs.estimated_round_trip_cost(
            entry, atr, costs.profile_for("SOLUSDT"))
        spot_required = k * costs.estimated_round_trip_cost(
            entry, atr, costs.profile_for("BTC-USD"))
        self.assertGreaterEqual(risk, perp_required, "economic on its own venue")
        self.assertLess(risk, spot_required, "rejected on the wrong venue's fees")

    def test_setups_no_longer_exports_a_global_profile(self):
        """The global is what made the mistake invisible: every consumer that
        imported the name silently inherited Coinbase rates."""
        self.assertFalse(hasattr(setups, "COST_PROFILE"))


class ExecSimVenueCostTest(TempStore):
    """End to end: a perp trade must be charged perp fees."""

    def _run_perp_trade(self, symbol="SOLUSDT"):
        # Fill at 100 on bar 2, then trade down through the stop at 95.
        candle(self.con, symbol, "1H", 0, 100, 110, 90, 100)
        candle(self.con, symbol, "1H", 3600, 101, 104, 99, 102)
        candle(self.con, symbol, "1H", 7200, 102, 106, 100, 105)
        candle(self.con, symbol, "1H", 10800, 100, 101, 94, 95)
        store.insert_fact(
            self.con, symbol=symbol, tf="1H", kind="setup",
            market_time=0, confirmed_at=3600, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "s1", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "100", "sl": "95",
                     "tp": "115", "rr": "3", "rank": 50, "state": "VALIDATED"})
        execsim.run(self.con, symbol, "1H", 3600)
        rows = store.get_facts(self.con, symbol, "1H", "exec",
                              execsim.EXEC_VERSION)
        self.assertEqual(len(rows), 1)
        return json.loads(rows[0]["payload"])

    def test_perp_trade_is_charged_phemex_rates(self):
        p = self._run_perp_trade()
        self.assertEqual(p["outcome"], "SL")
        self.assertEqual(p["venue"], "phemex-perp")
        self.assertEqual(p["cost_profile_version"], "phemex-perp-v1")

        profile = costs.PHEMEX_PERP_COST_PROFILE
        entry = D(p["entry"])
        eff_exit = D(p["effective_exit_price"])
        expected = profile.maker_rate * entry + profile.taker_rate * eff_exit
        self.assertEqual(D(p["fees_price_units"]), expected)

    def test_perp_fee_is_far_below_what_the_old_global_charged(self):
        p = self._run_perp_trade()
        entry = D(p["entry"])
        eff_exit = D(p["effective_exit_price"])
        old = (costs.DEFAULT_COST_PROFILE.maker_rate * entry
               + costs.DEFAULT_COST_PROFILE.taker_rate * eff_exit)
        self.assertLess(D(p["fees_price_units"]) * 10, old,
                        "perp fee should be an order of magnitude cheaper")

    def test_fields_edgestats_depends_on_survive(self):
        p = self._run_perp_trade()
        for k in ("fees_price_units", "effective_exit_price", "entry",
                  "costs_r", "r_gross", "r_multiple",
                  "entry_fee_role", "exit_fee_role"):
            self.assertIn(k, p, k)
        # costs_r must still reconcile: it is what edgestats splits fee from slip.
        self.assertEqual(D(p["costs_r"]),
                         (D(p["r_gross"]) - D(p["r_multiple"])).quantize(D("0.01")))

    def test_spot_trade_still_charged_coinbase_rates(self):
        """The change is per-venue, not a blanket discount."""
        p = self._run_perp_trade(symbol="SOL-USD")
        self.assertEqual(p["venue"], "coinbase-advanced-spot")
        self.assertEqual(p["cost_profile_version"], "coinbase-retail-v1")
        self.assertEqual(p["cost_manifest_hash"], COINBASE_V1_MANIFEST)

    def test_each_venue_records_its_own_cost_manifest(self):
        perp = self._run_perp_trade()
        self.assertNotEqual(perp["cost_manifest_hash"], COINBASE_V1_MANIFEST)
        stored = store.get_manifest(self.con, perp["cost_manifest_hash"])
        self.assertEqual(stored["version"], "phemex-perp-v1")
        self.assertEqual(stored["maker_rate"], "0.0001")

    def test_execution_manifest_is_symbol_invariant(self):
        """The execution manifest certifies the FILL model, which does not vary
        by venue. The rates are pinned separately by cost_manifest_hash, so a
        fee change must not look like an execution-model change."""
        perp = self._run_perp_trade("SOLUSDT")
        spot = self._run_perp_trade("SOL-USD")
        self.assertEqual(perp["execution_manifest_hash"],
                         spot["execution_manifest_hash"])
        self.assertNotEqual(perp["cost_manifest_hash"],
                            spot["cost_manifest_hash"])


class AppendOnlyVersionTest(TempStore):
    def test_exec_version_bumped_away_from_the_overcharged_book(self):
        """232 exec-v0.7-draft facts were written on the wrong profile. They stay
        valid as a record of what that algo did; a new version keeps the two
        books distinguishable instead of silently mixing them."""
        self.assertNotEqual(execsim.EXEC_VERSION, "exec-v0.7-draft")

    def test_scale_version_bumped_because_its_gate_changed(self):
        self.assertNotEqual(scalein.SCALE_VERSION, "scale-v0.2-draft")

    def test_old_facts_are_not_rewritten_by_a_new_run(self):
        old = {"setup_id": "s1", "strategy": "PULLBACK", "direction": "LONG",
               "outcome": "SL", "entry": "100", "exit_price": "95",
               "effective_exit_price": "94.9", "fees_price_units": "0.9694",
               "r_multiple": "-1.21", "r_gross": "-1.00", "costs_r": "0.21",
               "cost_manifest_hash": COINBASE_V1_MANIFEST}
        store.insert_fact(
            self.con, symbol="SOLUSDT", tf="1H", kind="exec",
            market_time=0, confirmed_at=10800,
            algo_version="exec-v0.7-draft", payload=old)

        candle(self.con, "SOLUSDT", "1H", 0, 100, 110, 90, 100)
        candle(self.con, "SOLUSDT", "1H", 3600, 101, 104, 99, 102)
        candle(self.con, "SOLUSDT", "1H", 7200, 102, 106, 100, 105)
        candle(self.con, "SOLUSDT", "1H", 10800, 100, 101, 94, 95)
        store.insert_fact(
            self.con, symbol="SOLUSDT", tf="1H", kind="setup",
            market_time=0, confirmed_at=3600, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "s1", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "100", "sl": "95",
                     "tp": "115", "rr": "3", "rank": 50, "state": "VALIDATED"})
        execsim.run(self.con, "SOLUSDT", "1H", 3600)

        kept = json.loads(store.get_facts(
            self.con, "SOLUSDT", "1H", "exec", "exec-v0.7-draft")[0]["payload"])
        self.assertEqual(kept, old, "historical fact was mutated")
        self.assertEqual(kept["cost_manifest_hash"], COINBASE_V1_MANIFEST)

        fresh = json.loads(store.get_facts(
            self.con, "SOLUSDT", "1H", "exec",
            execsim.EXEC_VERSION)[0]["payload"])
        self.assertNotEqual(fresh["cost_manifest_hash"], COINBASE_V1_MANIFEST)


if __name__ == "__main__":
    unittest.main()
