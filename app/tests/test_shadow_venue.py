"""SHADOW venue — warmed for a switch, and provably not traded.

The operator can access Phemex today and does not know for how long. Kraken is
the CFTC-regulated fallback. The expensive part of switching is NOT the code —
a new symbol enters WARMING and needs 200 daily candles before it is tradeable,
so discovering the switch under pressure costs weeks of forward record.

Carrying Kraken as SHADOW makes the switch a flag. The property that has to hold
for that to be safe is narrow and total: a shadow symbol must be scanned,
imported and derived, and must NEVER reach the risk authority.
"""
import json
import tempfile
import unittest
from pathlib import Path

from engine import store, universe


class ShadowIsNotTradeable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="universe",
            market_time=1_700_000_000, confirmed_at=1_700_000_000,
            algo_version=universe.UNIVERSE_VERSION,
            payload={"members": [
                {"symbol": "BTCUSDT", "state": "ADMITTED", "reason": "liquid_and_warm"},
                {"symbol": "PF_XBTUSD", "state": "SHADOW",
                 "reason": "warming_for_venue_switch"},
                {"symbol": "COLD-USD", "state": "WARMING", "reason": "insufficient_history"},
            ], "top_n": 20, "min_volume_usd": 3_000_000,
               "min_daily_candles": 200, "rank_health": {}})
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_shadow_is_scanned_so_its_data_stays_warm(self):
        """The entire point. A shadow symbol that is not scanned goes cold and
        the switch it exists to enable costs weeks again."""
        self.assertIn("PF_XBTUSD", universe.scan_symbols(self.con))

    def test_shadow_is_NOT_in_the_tradeable_set(self):
        self.assertNotIn("PF_XBTUSD", universe.current_symbols(self.con))
        self.assertIn("BTCUSDT", universe.current_symbols(self.con))

    def test_risk_refuses_a_shadow_symbol_at_any_time(self):
        """`admitted_at` gates every sizing decision. If it ever returned True
        for a SHADOW symbol, the shadow venue would silently start trading."""
        for as_of in (1_699_999_999, 1_700_000_000, 2_000_000_000):
            self.assertFalse(
                universe.admitted_at(self.con, "PF_XBTUSD", as_of),
                f"a SHADOW symbol was admitted at {as_of}")
        self.assertTrue(universe.admitted_at(self.con, "BTCUSDT", 1_700_000_001))

    def test_scan_set_is_a_superset_of_the_traded_set(self):
        traded = set(universe.current_symbols(self.con))
        scanned = set(universe.scan_symbols(self.con))
        self.assertTrue(traded <= scanned)
        self.assertTrue(scanned - traded, "shadow symbols must add to the scan")

    def test_the_two_sets_are_distinct_functions(self):
        """Collapsing `scan_symbols` into `current_symbols` is exactly how a
        shadow venue would quietly become a traded one."""
        self.assertIsNot(universe.scan_symbols, universe.current_symbols)

    def test_live_loop_scans_rather_than_trades(self):
        import inspect

        import live
        src = inspect.getsource(live.cycle)
        self.assertIn("universe.scan_symbols", src,
                      "the live loop must scan shadow symbols to keep them warm")


class ShadowClassification(unittest.TestCase):
    def test_the_flag_is_what_makes_the_switch_one_line(self):
        self.assertTrue(hasattr(universe, "KRAKEN_SHADOW_ONLY"))
        self.assertIs(universe.KRAKEN_SHADOW_ONLY, True)

    def test_only_kraken_symbols_are_shadowed(self):
        """Phemex is the traded venue. If shadow membership ever came from
        anywhere else the live book would go dark without a single error.

        Asserted on `shadow_candidates` rather than on `refresh` — shadow
        membership moved OUT of the admission classifier precisely so it could
        not displace a traded symbol, so that is where the rule now lives.
        """
        from unittest import mock
        with mock.patch.object(universe.kraken, "rank_by_volume",
                               return_value=[("PF_XBTUSD", 9e9),
                                             ("PF_ETHUSD", 8e9)]):
            got = universe.shadow_candidates()
        self.assertTrue(got)
        for sym, _ in got:
            self.assertTrue(sym.startswith("PF_"), sym)

    def test_shadow_candidates_are_empty_once_the_switch_is_made(self):
        """After KRAKEN_SHADOW_ONLY goes off, Kraken is a normal ranked venue
        and nothing should be carried as shadow — otherwise a symbol would be
        both traded and warmed, which is two states for one thing."""
        from unittest import mock
        with mock.patch.object(universe, "KRAKEN_SHADOW_ONLY", False):
            self.assertEqual(universe.shadow_candidates(), [])

    def test_a_shadow_candidate_still_has_to_clear_the_liquidity_floor(self):
        """Warming a book too thin to fill a structural stop would waste weeks
        of history on a symbol that could never be traded anyway."""
        from unittest import mock
        with mock.patch.object(universe.kraken, "rank_by_volume",
                               return_value=[("PF_XBTUSD", 9e9),
                                             ("PF_TINYUSD", 1.0)]):
            got = {s for s, _ in universe.shadow_candidates()}
        self.assertIn("PF_XBTUSD", got)
        self.assertNotIn("PF_TINYUSD", got)


if __name__ == "__main__":
    unittest.main()
