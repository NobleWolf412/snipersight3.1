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


class TestTheGuardIsCompleteAndCheap(ListingCase):
    """The demotion turns a BLOCKED verdict into a PASS, so the set of things
    that could still resolve a trade across the hole is the whole safety
    argument — and it runs once per scan symbol, so its cost is the whole
    performance argument.
    """

    def outbox(self, symbol, state="PAPER_FILLED", mode="PAPER"):
        from engine import execution
        execution._ensure(self.con)
        self.con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,"
            "symbol,payload,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"k-{symbol}-{state}", f"i-{symbol}-{state}", mode, "s1", symbol,
             "{}", state, 1, 1))
        self.con.commit()

    def test_a_durable_paper_intent_still_blocks(self):
        """execution.monitor_paper walks candles from intent.created_at to
        fill, stop or target. It was missing from the guard entirely."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        self.outbox("CRVUSDT")
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_a_settled_paper_intent_does_not_block(self):
        """Only the two states monitor_paper actually reads are the roster.
        Pinning every historical intent would retire nothing, ever."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        self.outbox("CRVUSDT", state="PAPER_CLOSED")
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("RETIRED_SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_a_missing_outbox_is_an_empty_population_not_an_unreadable_one(self):
        """execution._ensure creates the table on the first arm, so a store
        where nothing was ever armed does not have it. Letting that raise would
        reach the fail-closed handler and pin every symbol on exactly the cold
        stores this is supposed to work on."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM sqlite_master WHERE name='execution_outbox'"
        ).fetchone()[0], 0)
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("RETIRED_SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_the_expensive_guard_is_not_consulted_for_a_listed_market(self):
        """THE PERFORMANCE REGRESSION. `execsim.unresolved` measured 14 ms at
        500 current-generation order facts and 1,726 ms at 6,000; computing it
        eagerly ran that once per scan symbol and discarded it on every healthy
        one. Ordered cheap-first, a market the venue still lists never reaches
        it at all."""
        self.gapped("AAVEUSDT")
        self.record("phemex-perp", ["BTCUSDT", "AAVEUSDT"])
        with mock.patch.object(quality, "_symbols_that_must_keep_blocking") as guard:
            self.assertIn("SEQUENCE_GAPS", self.codes("AAVEUSDT"))
        guard.assert_not_called()

    def test_the_guard_is_computed_once_per_audit_not_once_per_symbol(self):
        """The set is identical for every symbol in a cycle."""
        for sym in ("CRVUSDT", "OLDUSDT", "GONEUSDT"):
            self.gapped(sym)
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch.object(quality, "_symbols_that_must_keep_blocking",
                               return_value=set()) as guard:
            quality.audit_market_inputs(self.con, now=1_000_100)
        self.assertEqual(guard.call_count, 1)


class TestTheDemotionSaysSoOutLoud(ListingCase):
    def test_lifting_the_blocker_is_logged(self):
        """Loud-fallback rule: this is the only path in v0.3 that LIFTS a
        blocker, and it was the only one that announced nothing. The store can
        go evaluation_allowed False -> True between two cycles, and without
        this data/live.log says nothing about why."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            with self.assertLogs("snipersight", level="WARNING") as logs:
                self.codes("CRVUSDT")
        said = "\n".join(logs.output)
        self.assertIn("CRVUSDT", said)
        self.assertIn("no longer", said)

    def test_the_note_is_a_note_and_not_a_warning(self):
        """The version note claimed DEGRADED; the code emits PASS at
        SERVE_FLAG. An operator told 'degraded' looks in the warnings group,
        and the UI splits notes from warnings — it is not there."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            found = self.codes("CRVUSDT")["RETIRED_SEQUENCE_GAPS"]
        self.assertEqual((found["status"], found["rung"]), ("PASS", "SERVE_FLAG"))


class TestTheOtherVenueActuallyWorks(ListingCase):
    """Every demotion test above is Phemex. Coinbase reported 85 delisted USD
    products against 402 online on 2026-09-01, so retired SPOT is the larger
    production population and its spelling path — `BTC-USD`, not `BTCUSDT` —
    was exercised nowhere.
    """

    def spot_gapped(self, sym):
        for ts in (0, 7200):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sym, "1H", ts, "100", "102", "98", "101", "1",
                 "coinbase-spot", ts + 1))
        self.con.commit()

    def test_a_delisted_spot_pair_demotes(self):
        self.spot_gapped("OLD-USD")
        self.record("coinbase-spot", ["BTC-USD", "ETH-USD"])
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("RETIRED_SEQUENCE_GAPS", self.codes("OLD-USD"))

    def test_a_listed_spot_pair_still_blocks(self):
        self.spot_gapped("BTC-USD")
        self.record("coinbase-spot", ["BTC-USD", "ETH-USD"])
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("SEQUENCE_GAPS", self.codes("BTC-USD"))

    def test_a_perp_sweep_does_not_answer_for_a_spot_pair(self):
        """Each venue answers only for its own symbols; the cross-venue
        direction is pinned above, this is the mirror of it."""
        self.spot_gapped("OLD-USD")
        self.record("phemex-perp", ["BTCUSDT"])
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("SEQUENCE_GAPS", self.codes("OLD-USD"))


class TestTheSweepsFallbackIsAudible(ListingCase):
    def test_a_failed_venue_says_so_in_the_log_as_well_as_the_fact(self):
        """Loud-fallback rule. The fact carries swept=false, but a silent
        failure in the log looks exactly like a clean sweep that happened to
        list nothing — and nothing in the suite would have noticed it going
        quiet."""
        with mock.patch.object(listings, "SOURCES",
                               ((venues.PHEMEX_PERP.key,
                                 mock.Mock(side_effect=OSError("boom")), "/t"),)):
            with self.assertLogs("snipersight", level="WARNING") as logs:
                listings.sweep(self.con, now=1_000_000)
        said = "\n".join(logs.output)
        self.assertIn("phemex-perp", said)
        self.assertIn("FAILED", said)


class TestNothingActsOnAFactBeforeItWasKnowable(ListingCase):
    """Constitution rule 3, applied to the listing record.

    `confirmed_at` is when the engine could first have known. A reader that
    ignores it can answer a question about one moment using evidence from a
    later one, and here that evidence LIFTS a blocker.

    No caller passes a past clock today, so these pin a property rather than
    fix a live symptom — except the skew case, which the code could reach and
    had no answer for.
    """

    def test_a_record_from_after_the_question_is_not_used(self):
        self.record("phemex-perp", ["BTCUSDT"], at=1_000_000)
        self.assertIsNone(listings.latest(self.con, "phemex-perp", 999_999))
        self.assertIsNone(
            listings.listed_on_venue(self.con, "CRVUSDT", 999_999))

    def test_a_record_exactly_at_the_question_is_used(self):
        """`confirmed_at` is the moment it BECAME knowable, so that moment
        counts. An exclusive bound would drop a sweep from this same second."""
        self.record("phemex-perp", ["BTCUSDT"], at=1_000_000)
        self.assertIsNotNone(listings.latest(self.con, "phemex-perp", 1_000_000))

    def test_an_older_record_is_still_reachable_behind_a_newer_one(self):
        """The filter must narrow the candidates, not just reject the newest.
        Taking the newest row and then discarding it would answer None while a
        perfectly good earlier sweep sat right there."""
        self.record("phemex-perp", ["BTCUSDT"], at=1_000_000)
        self.record("phemex-perp", ["BTCUSDT", "ETHUSDT"], at=1_000_500)
        payload = listings.latest(self.con, "phemex-perp", 1_000_100)
        self.assertEqual(payload["symbols"], ["BTCUSDT"])

    def test_a_backwards_clock_step_cannot_freeze_a_stale_record(self):
        """THE REACHABLE ONE. An NTP correction, a VM restore or a DST bug
        steps the host clock back. Rows written minutes ago are then dated
        ahead of `now`, so `now - confirmed_at` goes NEGATIVE — younger than
        any window, so the staleness check passes forever. Unfiltered, that is
        the one condition under which a listing record never expires."""
        self.record("phemex-perp", ["BTCUSDT"], at=2_000_000)
        skewed = 2_000_000 - 86_400
        self.assertIsNone(listings.latest(self.con, "phemex-perp", skewed))
        self.assertIsNone(
            listings.listed_on_venue(self.con, "CRVUSDT", skewed))

    def test_the_demotion_does_not_fire_on_evidence_from_the_future(self):
        """The behaviour that matters: unknowable evidence must not lift a
        blocker. Checking `latest` alone would not prove the guard held."""
        self.gapped("CRVUSDT")
        self.record("phemex-perp", ["BTCUSDT"], at=1_000_000)
        with mock.patch("engine.universe.scan_symbols", return_value=[]):
            self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT", now=999_999))


if __name__ == "__main__":
    unittest.main()
