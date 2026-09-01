"""The venue listing record, and the gap demotion that reads it.

A delisted market's holes are unrepairable, so blocking on them halts the store
forever (CRVUSDT/Phemex). An earlier fix keyed "delisted" on universe
membership and demoted 81 live perps, because `members` is the top_n slice of
the ranking — reverted as ba9d8fb. These pin the replacement, and most of them
exist to prove the demotion does NOT fire: every case that stops blocking is a
fail-closed gate switched off, so the narrowness is the property under test.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import listings, quality, store, venues


class ListingCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "listings.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def record(self, venue_key, symbols, *, swept=True, at=1_000_000):
        payload = {"venue": venue_key, "venues_version": venues.VENUES_VERSION,
                   "swept": swept, "symbols": sorted(symbols),
                   "n_listed": len(symbols), "source": "/test"}
        if not swept:
            payload = {"venue": venue_key, "venues_version": venues.VENUES_VERSION,
                       "swept": False, "n_listed": 0, "source": "/test",
                       "error": "HTTPError: 503"}
        store.insert_fact(self.con, symbol="PORTFOLIO", tf="ALL",
                          kind=listings.FACT_KIND, market_time=at,
                          confirmed_at=at, algo_version=listings.LISTINGS_VERSION,
                          payload=payload)
        self.con.commit()

    def gapped(self, sym):
        """Two 1H candles two hours apart — one unexplained hole, unacknowledged."""
        for ts in (0, 7200):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sym, "1H", ts, "100", "102", "98", "101", "1", "phemex-perp", ts + 1))
        self.con.commit()

    def codes(self, sym, now=1_000_100):
        return {c["code"]: c for c in
                quality.audit_market_inputs(self.con, sym, now=now)}


class TestListedOnVenue(ListingCase):
    def test_false_only_on_positive_evidence(self):
        self.record("phemex-perp", ["BTCUSDT", "ETHUSDT"])
        self.assertIs(listings.listed_on_venue(self.con, "BTCUSDT", 1_000_100), True)
        self.assertIs(listings.listed_on_venue(self.con, "CRVUSDT", 1_000_100), False)

    def test_no_record_is_none(self):
        self.assertIsNone(listings.listed_on_venue(self.con, "CRVUSDT", 1_000_100))

    def test_failed_sweep_is_none(self):
        """The outage case. rank_all_venues continues spot-only on a Phemex
        failure and the coverage guard only measures Coinbase, so this is the
        state a real perp outage reaches."""
        self.record("phemex-perp", [], swept=False)
        self.assertIsNone(listings.listed_on_venue(self.con, "CRVUSDT", 1_000_100))

    def test_stale_record_is_none(self):
        self.record("phemex-perp", ["BTCUSDT"])
        far = 1_000_000 + listings.MAX_LISTING_AGE + 1
        self.assertIsNone(listings.listed_on_venue(self.con, "CRVUSDT", far))

    def test_another_venues_sweep_does_not_answer_for_this_one(self):
        """A Coinbase sweep says nothing about whether Phemex lists a perp."""
        self.record("coinbase-spot", ["BTC-USD", "ETH-USD"])
        self.assertIsNone(listings.listed_on_venue(self.con, "CRVUSDT", 1_000_100))

    def test_reference_key_and_unknown_symbol_are_none(self):
        self.record("phemex-perp", ["BTCUSDT"])
        self.assertIsNone(listings.listed_on_venue(self.con, "BICOUSDT@binance-spot", 1_000_100))
        self.assertIsNone(listings.listed_on_venue(self.con, "not a symbol", 1_000_100))

    def test_empty_symbol_list_is_none_not_mass_delisting(self):
        payload = {"venue": "phemex-perp", "venues_version": venues.VENUES_VERSION,
                   "swept": True, "symbols": [], "n_listed": 0, "source": "/test"}
        store.insert_fact(self.con, symbol="PORTFOLIO", tf="ALL",
                          kind=listings.FACT_KIND, market_time=1_000_000,
                          confirmed_at=1_000_000,
                          algo_version=listings.LISTINGS_VERSION, payload=payload)
        self.con.commit()
        self.assertIsNone(listings.listed_on_venue(self.con, "CRVUSDT", 1_000_100))


class TestSweepRecordsBothOutcomes(ListingCase):
    def test_a_failed_venue_still_writes_its_fact(self):
        """Writing nothing on failure is indistinguishable from never running,
        and that ambiguity is the defect the module exists to remove."""
        with mock.patch.object(listings, "SOURCES",
                               ((venues.PHEMEX_PERP.key,
                                 mock.Mock(side_effect=OSError("boom")), "/t"),)):
            out = listings.sweep(self.con, now=1_000_000)
        self.assertFalse(out["phemex-perp"]["swept"])
        self.assertIn("OSError", out["phemex-perp"]["error"])
        self.assertIsNone(listings.listed_on_venue(self.con, "CRVUSDT", 1_000_100))

    def test_facts_carry_a_producer_run(self):
        """A fact with no producer run is reported UNATTRIBUTED_CURRENT_FACTS
        at BLOCKED — writing these unattributed would halt the store."""
        with mock.patch.object(listings, "SOURCES",
                               ((venues.PHEMEX_PERP.key,
                                 lambda: ["BTCUSDT"], "/t"),)):
            listings.sweep(self.con, now=1_000_000)
        run = self.con.execute(
            "SELECT producer_run_id FROM facts WHERE kind=?",
            (listings.FACT_KIND,)).fetchone()
        self.assertTrue(run[0])


class TestGapDemotion(ListingCase):
    def test_delisted_market_degrades_instead_of_blocking(self):
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT", "ETHUSDT"])
        found = self.codes("CRVUSDT")
        self.assertNotIn("SEQUENCE_GAPS", found)
        self.assertEqual(found["RETIRED_SEQUENCE_GAPS"]["status"], "PASS")
        self.assertEqual(found["RETIRED_SEQUENCE_GAPS"]["rung"], "SERVE_FLAG")

    def test_a_live_but_low_ranked_market_still_blocks(self):
        """THE REGRESSION THAT CAUSED THE REVERT. Phemex listed 101 perps while
        the universe holds the top 20; AAVEUSDT/ZECUSDT/LITUSDT/ONDOUSDT were
        live, listed, and outside it. Membership is not listing."""
        self.gapped("AAVEUSDT")
        self.record("phemex-perp", ["BTCUSDT", "AAVEUSDT", "ZECUSDT"])
        self.assertIn("SEQUENCE_GAPS", self.codes("AAVEUSDT"))

    def test_venue_outage_does_not_retire_the_book(self):
        self.gapped("CRVUSDT")
        self.record("phemex-perp", [], swept=False)
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_no_listing_record_keeps_blocking(self):
        """Fails closed: a cold store must not read as everything retired."""
        self.gapped("CRVUSDT")
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_a_market_with_an_open_order_still_blocks(self):
        """live.py resolves pinned exits for symbols outside the scan set, and
        assert_market_ready — BLOCKED only — is the sole gate before
        execsim.run. Inventing a fill is worse on a delisted market: the bars
        are never coming, so the invention is permanent."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.execsim.unresolved",
                        return_value={("CRVUSDT", "1H"): [{}]}), \
                mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_unreadable_order_book_keeps_blocking(self):
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.execsim.unresolved",
                        side_effect=RuntimeError("db locked")):
            self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_an_unresolved_manual_intent_still_blocks(self):
        """manual.run settles the operator's hand-armed trades by walking
        candles, on the same roster. The quality gate is the only thing
        stopping it settling across the hole."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.manual.unresolved",
                        return_value={("CRVUSDT", "1H"): [{}]}), \
                mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_a_symbol_still_in_the_scan_set_blocks(self):
        """The audit computes the open-order set ONCE, before its loop, but
        the pipeline creates a setup and simulates it moments after this gate
        passes — so a scanned symbol acquires an order that did not exist when
        we looked. universe.refresh also keeps its previous members
        indefinitely under low rank coverage, so this window is not one hour."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.universe.scan_symbols", return_value=["CRVUSDT"]):
            self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_only_gaps_demote(self):
        """Malformed rows indict the STORE, which is live and repairable
        whatever the venue did."""
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("CRVUSDT", "1H", 0, "100", "97", "98", "101", "1", "phemex-perp", 1))
        self.con.commit()
        self.record("phemex-perp", ["BTCUSDT"])
        self.assertEqual(self.codes("CRVUSDT")["OHLC_INVARIANT_FAILURE"]["status"],
                         "BLOCKED")

    def test_reference_key_keeps_its_own_demotion(self):
        self.gapped("BICOUSDT@binance-spot")
        self.record("phemex-perp", ["BTCUSDT"])
        found = self.codes("BICOUSDT@binance-spot")
        self.assertIn("REFERENCE_SEQUENCE_GAPS", found)
        self.assertNotIn("RETIRED_SEQUENCE_GAPS", found)

    def test_the_scanner_gate_actually_opens_for_a_delisted_market(self):
        """The behaviour the operator sees: assert_market_ready is what stops
        the scan, and auditing checks in isolation would not prove it."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        quality.assert_market_ready(self.con, "CRVUSDT", now=1_000_100)


if __name__ == "__main__":
    unittest.main()


class TestListingSourcesAreListingsNotTradeability(ListingCase):
    """The adapters' own product rosters drop anything not currently tradeable,
    because they feed a TRADEABLE universe. Reading those as the listing turns
    a maintenance halt or a cancel-only wind-down into a delisting — which
    tells the operator a live market's repairable holes are unrepairable. The
    sweep must read the venue's NAMING instead.
    """

    def test_coinbase_keeps_halts_and_drops_only_delisted(self):
        from engine import universe
        payload = [
            {"id": "AAA-USD", "quote_currency": "USD", "status": "online"},
            {"id": "BBB-USD", "quote_currency": "USD", "status": "online",
             "trading_disabled": True},          # maintenance halt -> LISTED
            {"id": "CCC-USD", "quote_currency": "USD", "status": "online",
             "limit_only": True},                # serving history -> LISTED
            {"id": "DDD-USD", "quote_currency": "USD", "status": "delisted",
             "trading_disabled": True},          # end of life -> NOT listed
            {"id": "EEE-EUR", "quote_currency": "EUR", "status": "online"},
        ]
        with mock.patch.object(universe, "_get", return_value=payload):
            listed = {p["id"] for p in universe.coinbase_products()}
        self.assertEqual(listed, {"AAA-USD", "BBB-USD", "CCC-USD"})

    def test_the_ranking_filter_survived_the_extraction(self):
        """coinbase_products widened; rank_by_volume must NOT have. A halted or
        limit_only pair entering the ranking would change the universe under an
        unmoved UNIVERSE_VERSION."""
        from engine import universe
        payload = [
            {"id": "AAA-USD", "quote_currency": "USD", "status": "online"},
            {"id": "BBB-USD", "quote_currency": "USD", "status": "online",
             "trading_disabled": True},
            {"id": "CCC-USD", "quote_currency": "USD", "status": "online",
             "limit_only": True},
            {"id": "EEE-USD", "quote_currency": "USD", "status": "online",
             "auction_mode": True},
            {"id": "FFF-USD", "quote_currency": "USD", "status": "offline"},
        ]
        seen = []

        def fake_get(path):
            if path == "/products":
                return payload
            seen.append(path.split("/")[2])
            return {"last": "1", "volume": "1"}

        with mock.patch.object(universe, "_get", side_effect=fake_get):
            universe.rank_by_volume()
        self.assertEqual(set(seen), {"AAA-USD"})

    def test_phemex_keeps_a_suspended_perp_and_drops_a_delisted_one(self):
        """Phemex states the delisting: 101 Listed vs 772 Delisted on
        2026-09-01, CRVUSDT among the latter. An unrecognised future status is
        kept — doubt means listed."""
        from engine import phemex
        payload = {"data": {"perpProductsV2": [
            {"symbol": "AAAUSDT", "status": "Listed",
             "settleCurrency": "USDT", "quoteCurrency": "USDT"},
            {"symbol": "BBBUSDT", "status": "Suspended",
             "settleCurrency": "USDT", "quoteCurrency": "USDT"},
            {"symbol": "CRVUSDT", "status": "Delisted",
             "settleCurrency": "USDT", "quoteCurrency": "USDT"},
            {"symbol": "DDDUSDT", "status": "SomethingNew",
             "settleCurrency": "USDT", "quoteCurrency": "USDT"},
            {"symbol": "EEEUSD", "status": "Listed",
             "settleCurrency": "USD", "quoteCurrency": "USD"},
        ]}}
        with mock.patch.object(phemex, "_get", return_value=payload):
            self.assertEqual(set(phemex.listed_symbols()),
                             {"AAAUSDT", "BBBUSDT", "DDDUSDT"})

    def test_kraken_keeps_a_halted_instrument_and_drops_an_expired_one(self):
        from engine import kraken
        payload = {"instruments": [
            {"symbol": "PF_AAAUSD", "tradeable": True},
            {"symbol": "PF_BBBUSD", "tradeable": False},   # halt -> LISTED
            {"symbol": "PF_CCCUSD", "tradeable": False, "isExpired": True},
            {"symbol": "FI_DDDUSD", "tradeable": True},    # not a perpetual
        ]}
        with mock.patch.object(kraken, "_get", return_value=payload):
            self.assertEqual(set(kraken.listed_symbols()),
                             {"PF_AAAUSD", "PF_BBBUSD"})

    def test_every_source_names_a_real_venue_and_a_working_fetcher(self):
        """SOURCES is patched wholesale by the sweep tests, so without this the
        three fetchers and their venue keys are dead code under test."""
        for key, fetch, source in listings.SOURCES:
            self.assertTrue(venues.by_key(key), key)
            self.assertTrue(source.startswith("/"), source)
            self.assertTrue(callable(fetch))


class TestWiringAndConstants(ListingCase):
    def test_the_scan_cycle_actually_runs_the_sweep(self):
        """Existing refresh_universe tests pass con=None, so the sweep dies in
        RunRecorder and is swallowed — they pass identically if the call is
        deleted, and the feature silently reverts to CRVUSDT blocking forever."""
        import live
        import inspect
        source = inspect.getsource(live.refresh_universe)
        self.assertIn("listings.sweep(con", source)
        self.assertIn("beat=beat", source)

    def test_the_freshness_window_outlives_several_missed_sweeps(self):
        """The staleness argument is that the window covers missed hourly
        sweeps. If either constant moves alone, nothing else notices."""
        from engine import universe
        self.assertGreater(listings.MAX_LISTING_AGE, universe.REFRESH_SECONDS * 2)

    def test_the_sweep_beats_between_venues(self):
        """~375s of stacked timeouts with all three venues black-holing, past
        watchdog.SCANNER_DARK_AFTER_S — a silent sweep fires a false alarm."""
        beats = []
        with mock.patch.object(listings, "SOURCES",
                               ((venues.PHEMEX_PERP.key, lambda: ["BTCUSDT"], "/t"),
                                (venues.COINBASE_SPOT.key, lambda: ["BTC-USD"], "/t"))):
            listings.sweep(self.con, now=1_000_000, beat=beats.append)
        self.assertEqual(len(beats), 2)
