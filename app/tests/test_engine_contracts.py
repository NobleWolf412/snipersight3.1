import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import aggregator, importer, liquidity, store, structure, swings
from validate import bootstrap_mean_ci


def insert_candle(con, tf, ts, o="100", h="102", lo="98", c="100"):
    con.execute(
        "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("BTC-USD", tf, ts, o, h, lo, c, "1", "coinbase", ts + 1))


class EngineStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class TestAggregator(EngineStoreCase):
    def test_only_complete_closed_bucket_is_emitted(self):
        for i in range(4):
            insert_candle(self.con, "1H", i * 3600, o=str(100 + i),
                          h=str(102 + i), lo=str(98 + i), c=str(101 + i))
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 1)
        row = store.get_candles(self.con, "BTC-USD", "4H")[0]
        self.assertEqual(row["open"], "100")
        self.assertEqual(row["high"], "105")
        self.assertEqual(row["low"], "98")
        self.assertEqual(row["close"], "104")

    def test_gap_prevents_aggregate(self):
        """An UNACKNOWLEDGED gap still blocks the bucket (agg-v0.2).

        Written under v0.1 to pin all-or-nothing; it survives the partial-
        bucket change with its meaning sharpened rather than lost — there is
        no import_log row here, so the missing 02:00 hour could be a failed
        fetch, and a bar built over it would be the fabrication the
        gap-honesty rule forbids. Acknowledged absences are the next test.
        """
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600)
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["skipped_incomplete"], 1)

    def _acknowledge(self, tf, gaps, *, range_start=None, n_gaps=None, n_bad=0):
        """An import_log row acknowledging `gaps` — what backfill() writes when
        the venue serves nothing for a bucket inside its own served span.

        range_start defaults to importer.PRE_2000 exactly: acknowledgment rows
        whose range_start predates 2000 are quarantined as cold-start
        artefacts, and this fixture's candles live near the epoch, so a naive
        0 here silently quarantines the very acknowledgment under test. (That
        the filter caught this fixture is the filter working.)"""
        if range_start is None:
            range_start = importer.PRE_2000
        self.con.execute(
            "INSERT INTO import_log (symbol, tf, range_start, range_end, "
            "n_candles, n_gaps, gaps, source, run_at, n_bad) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("BTC-USD", tf, range_start, 20000, 3,
             len(gaps) if n_gaps is None else n_gaps,
             json.dumps(gaps), "coinbase", 19999, n_bad))

    def test_acknowledged_partial_bucket_builds(self):
        """agg-v0.2: an hour NOBODY TRADED no longer deletes the hours somebody
        did. Three present hours + the venue's own acknowledgment that 02:00
        served nothing -> the bar the venue's native 4H would hold: open from
        the first PRESENT candle, close from the last, extremes and volume
        over what exists. Measured motivation: BICO-USD alone had 621 such
        windows (1,442 real trading hours) discarded."""
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600, o=str(100 + i),
                          h=str(102 + i), c=str(101 + i))
        self._acknowledge("1H", [2 * 3600])
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 1)
        self.assertEqual(result["skipped_incomplete"], 0)
        row = store.get_candles(self.con, "BTC-USD", "4H")[0]
        self.assertEqual(row["open"], "100")    # first present, not first slot
        self.assertEqual(row["high"], "105")    # max over present
        self.assertEqual(row["low"], "98")
        self.assertEqual(row["close"], "104")   # last present
        self.assertEqual(row["volume"], "3")    # sum over present, not 4

    def test_quarantined_acknowledgment_is_ignored(self):
        """A pre-2000 import_log row is a cold-start artefact (importer.py:
        PRE_2000) holding fabricated gap lists. Its 'acknowledgment' must not
        clear a partial bucket."""
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600)
        self._acknowledge("1H", [2 * 3600], range_start=-100)
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["skipped_incomplete"], 1)

    def test_counted_but_unlisted_gap_blocks(self):
        """The gap LIST is capped at import (gaps[:5000]) while n_gaps stays
        exact. A gap that was counted but truncated out of the list cannot be
        attributed to a specific bucket, so it clears nothing — 'some bucket
        somewhere was empty' is not clearance for THIS one."""
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600)
        self._acknowledge("1H", [], n_gaps=1)   # counted, not listed
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)

    def test_rejected_candle_row_acknowledges_nothing(self):
        """backfill() logs a served-but-REJECTED malformed bar in the same
        gaps list as a no-trades bucket, and the list does not say which entry
        is which. A rejected bar means real trades happened, so a row that
        rejected anything (n_bad > 0) must clear no partial bucket — otherwise
        the built bar omits real volume while claiming to hold every trade
        the venue reported."""
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600)
        self._acknowledge("1H", [2 * 3600], n_bad=1)
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["skipped_incomplete"], 1)

    def test_misaligned_extra_candle_blocks_the_bucket(self):
        """A source candle OFF the slot grid, sitting beside aligned ones,
        must block the bucket: slot arithmetic never sees it, so it would leak
        into H/L/V — and the CLOSE, when it sorts last — of a bar built as if
        it did not exist. The candle itself is OHLC_INVARIANT_FAILURE's to
        report; this engine's job is only to refuse to build over it."""
        for i in (0, 1):
            insert_candle(self.con, "1H", i * 3600)
        insert_candle(self.con, "1H", 4000)          # off-grid stray
        self._acknowledge("1H", [2 * 3600, 3 * 3600])
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["skipped_incomplete"], 1)

    def test_late_candle_rewrite_is_loud(self):
        """agg-v0.2 is the first design in which a legitimately emitted bar
        can legally change content: a late-served source candle completes a
        bucket previously built partial. The loud-fallback rule applies — the
        rewrite must be reported, because facts derived from the old bar stay
        in the store."""
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600, o=str(100 + i),
                          h=str(102 + i), c=str(101 + i))
        self._acknowledge("1H", [2 * 3600])
        with patch("engine.aggregator.time.time", return_value=20000):
            first = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(first["rewritten"], 0)
        insert_candle(self.con, "1H", 2 * 3600, h="200")   # late arrival
        with patch("engine.aggregator.time.time", return_value=20000):
            second = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(second["rewritten"], 1)
        row = store.get_candles(self.con, "BTC-USD", "4H")[0]
        self.assertEqual(row["high"], "200")
        self.assertEqual(row["volume"], "4")

    def test_partial_developing_bucket_never_emits(self):
        """Closed-buckets-only (§5) outranks acknowledgment: a partial bucket
        whose window has not closed is not emitted however well-explained its
        absences are."""
        for i in (0, 1):
            insert_candle(self.con, "1H", i * 3600)
        self._acknowledge("1H", [2 * 3600, 3 * 3600])
        with patch("engine.aggregator.time.time", return_value=10000):  # mid-window
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)

    def test_pre_listing_window_stays_unbuilt(self):
        """A symbol listed mid-window: the buckets before its first-ever candle
        are PRE-LISTING, which backfill() deliberately excludes from the gap
        record — so they are never acknowledged and the first partial window
        never builds. Nothing here to assert about import_log: its absence IS
        the mechanism."""
        insert_candle(self.con, "1H", 2 * 3600)
        insert_candle(self.con, "1H", 3 * 3600)
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)

    def test_acknowledged_partial_week_builds(self):
        """Same rule, 1W from 1D: a market that traded five of seven days has
        a week, provided the venue acknowledged the two quiet days."""
        monday = aggregator.MONDAY_EPOCH
        missing = [monday + 2 * 86400, monday + 5 * 86400]
        for i in (0, 1, 3, 4, 6):
            insert_candle(self.con, "1D", monday + i * 86400, o=str(200 + i),
                          h=str(202 + i), c=str(201 + i))
        self._acknowledge("1D", missing)
        with patch("engine.aggregator.time.time",
                   return_value=monday + 8 * 86400):
            result = aggregator.aggregate(self.con, "BTC-USD", "1W")
        self.assertEqual(result["candles"], 1)
        row = store.get_candles(self.con, "BTC-USD", "1W")[0]
        self.assertEqual(row["open"], "200")
        self.assertEqual(row["close"], "207")
        self.assertEqual(row["volume"], "5")


class TestImporter(EngineStoreCase):
    def test_pinned_snapshot_cannot_advance_when_import_crosses_a_boundary(self):
        """importer-v0.6. A scan beginning one second before the next hour
        must not import that hour's bar merely because the request finishes two
        seconds later. Quality judges the whole cycle against the opening clock;
        admitting the later bar makes a closed candle look DEVELOPING and skips
        otherwise healthy markets."""
        rows = [
            [0, Decimal("9"), Decimal("11"), Decimal("10"), Decimal("10"),
             Decimal("1")],
            [3600, Decimal("19"), Decimal("21"), Decimal("20"), Decimal("20"),
             Decimal("1")],
        ]
        with patch("engine.importer._fetch", return_value=rows), \
             patch("engine.importer.time.time", return_value=7201), \
             patch("engine.importer.time.sleep"):
            importer.backfill(self.con, "BTC-USD", "1H", 0, 7201,
                              as_of=7199)
        opens = [r["open_ts"] for r in
                 store.get_candles(self.con, "BTC-USD", "1H")]
        self.assertEqual(opens, [0],
                         "the importer advanced beyond the cycle's clock")

    def test_empty_answer_after_listing_acknowledges_the_quiet_window(self):
        """importer-v0.5. A steady-state cycle imports exactly the newest
        bucket; on a thin market a quiet bucket arrives as its own EMPTY
        response, and until this change nothing ever vouched for it — the
        unexplained-hole count crept up until SEQUENCE_GAPS halted the store
        (PENGU-USD, 2026-08-10, 122 unvouched quiet minutes). A successful
        empty answer about a post-listing window is the venue saying "no
        trades here", and it is recorded as exactly that."""
        insert_candle(self.con, "1H", 0)             # the market has listed
        with patch("engine.importer._fetch", return_value=[]), \
             patch("engine.importer.time.time", return_value=10000), \
             patch("engine.importer.time.sleep"):
            r = importer.backfill(self.con, "BTC-USD", "1H", 3600, 7200)
        self.assertEqual(r["candles"], 0)
        self.assertEqual(r["gaps"], 1, "the quiet bucket went unvouched again")
        self.assertEqual(r["pre_listing"], 0)
        listed = self.con.execute(
            "SELECT gaps FROM import_log ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertEqual(json.loads(listed), [3600])

    def test_empty_answer_before_listing_acknowledges_nothing(self):
        # No prior candles: this range may simply predate the listing, and
        # recording gaps would claim the venue lost data it never had.
        with patch("engine.importer._fetch", return_value=[]), \
             patch("engine.importer.time.time", return_value=10000), \
             patch("engine.importer.time.sleep"):
            r = importer.backfill(self.con, "BTC-USD", "1H", 3600, 7200)
        self.assertEqual(r["gaps"], 0)
        self.assertEqual(r["pre_listing"], 1)

    def test_served_window_with_omitted_head_after_listing_acknowledges_the_head(self):
        """importer-v0.7. The v0.5 sibling above covers an EMPTY answer; a
        PARTIAL answer that omits only its first bucket fell through to the
        served branch, which counted everything before the first served bucket
        as pre-listing. `live.py` requests from `MAX(open_ts) + gran` with no
        overlap, so the omitted bucket is always at the head and nothing ever
        re-asked for it. AERO-USD / LIGHTER-USD / VET-USD, 2026-09-02: 17 such
        buckets, every one a SEQUENCE_GAPS blocker no restart could clear."""
        insert_candle(self.con, "1H", 0)             # the market has listed
        with patch("engine.importer._fetch",
                   return_value=[(7200, 98, 102, 100, 100, 1)]), \
             patch("engine.importer.time.time", return_value=20000), \
             patch("engine.importer.time.sleep"):
            r = importer.backfill(self.con, "BTC-USD", "1H", 3600, 10800)
        self.assertEqual(r["candles"], 1)
        self.assertEqual(r["gaps"], 1, "the head bucket went unvouched again")
        self.assertEqual(r["pre_listing"], 0)
        listed = self.con.execute(
            "SELECT gaps FROM import_log ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertEqual(json.loads(listed), [3600])

    def test_served_window_with_omitted_head_before_listing_stays_pre_listing(self):
        # The guard for the cold-start class of defect: with nothing stored
        # before the window, a late first bucket is where the venue's history
        # begins, not a hole. Acknowledging it would inflate n_gaps and let
        # the aggregator build a first 4H from one hour of trade.
        with patch("engine.importer._fetch",
                   return_value=[(7200, 98, 102, 100, 100, 1)]), \
             patch("engine.importer.time.time", return_value=20000), \
             patch("engine.importer.time.sleep"):
            r = importer.backfill(self.con, "BTC-USD", "1H", 3600, 10800)
        self.assertEqual(r["candles"], 1)
        self.assertEqual(r["gaps"], 0)
        self.assertEqual(r["pre_listing"], 1)

    def test_malformed_candle_is_rejected_and_logged_as_gap(self):
        # Coinbase response order: time, low, high, open, close, volume.
        rows = [[0, Decimal("110"), Decimal("100"), Decimal("105"),
                 Decimal("106"), Decimal("1")]]
        with patch("engine.importer._fetch", return_value=rows), \
             patch("engine.importer.time.time", return_value=10000), \
             patch("engine.importer.time.sleep", return_value=None):
            result = importer.backfill(self.con, "BTC-USD", "1H", 0, 3600)
        self.assertEqual(result["bad"], 1)
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["gaps"], 1)


class TestSwingCausality(unittest.TestCase):
    def _series(self, highs):
        return [{"open_ts": i * 60, "open": "10", "high": str(h),
                 "low": "1", "close": "5", "volume": "1"}
                for i, h in enumerate(highs)]

    def test_right_side_confirmation_is_required(self):
        self.assertEqual(swings.detect_micro(self._series([1, 2, 9, 2])), [])
        found = swings.detect_micro(self._series([1, 2, 9, 2, 1]))
        self.assertEqual([(x["i"], x["type"]) for x in found], [(2, "HIGH")])

    def test_equal_high_tie_is_not_a_swing(self):
        found = swings.detect_micro(self._series([1, 9, 9, 2, 1]))
        self.assertNotIn("HIGH", [x["type"] for x in found])


class TestStructureBreaks(EngineStoreCase):
    def test_wick_does_not_break_but_close_does(self):
        for i in range(22):
            close, high = ("100", "102")
            if i == 19:
                high = "120"                 # wick above the level only
            if i == 20:
                close, high = "111", "112"   # closed displacement
            insert_candle(self.con, "1H", i * 3600, h=high, c=close)
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="swing",
            market_time=10 * 3600, confirmed_at=13 * 3600,
            algo_version=swings.SWING_VERSION,
            payload={"tier": "INTERMEDIATE", "type": "HIGH", "price": "110"})
        structure.run(self.con, "BTC-USD", "1H", 3600)
        rows = store.get_facts(
            self.con, "BTC-USD", "1H", "structure", structure.STRUCTURE_VERSION)
        breaks = [{"market_time": r["market_time"], **json.loads(r["payload"])}
                  for r in rows if json.loads(r["payload"])["event"] != "LABEL"]
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0]["market_time"], 20 * 3600)


class TestLiquidityCanonicalization(EngineStoreCase):
    def test_overlapping_equal_high_cluster_emits_one_pool(self):
        for i in range(24):
            insert_candle(self.con, "1H", i * 3600, h="101", lo="91", c="96")
        for i, price in ((14, "100"), (15, "100.5"), (16, "100.2")):
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1H", kind="swing",
                market_time=i * 3600, confirmed_at=(i + 1) * 3600,
                algo_version=swings.SWING_VERSION,
                payload={"tier": "INTERMEDIATE", "type": "HIGH", "price": price})
        liquidity.run(self.con, "BTC-USD", "1H", 3600)
        rows = store.get_facts(
            self.con, "BTC-USD", "1H", "liquidity", liquidity.LIQ_VERSION)
        pools = [r for r in rows if json.loads(r["payload"])["event"] == "POOL"]
        self.assertEqual(len(pools), 1)


class TestDecimalScoring(unittest.TestCase):
    def test_decimal_ln_is_available_and_repeatable(self):
        x = (Decimal("6") + 1).ln() / Decimal(2).ln()
        self.assertEqual(x, (Decimal("6") + 1).ln() / Decimal(2).ln())


class TestValidationStatistics(unittest.TestCase):
    def test_bootstrap_is_seeded_and_deterministic(self):
        self.assertEqual(bootstrap_mean_ci([1, -1, 2], n=200),
                         bootstrap_mean_ci([1, -1, 2], n=200))


if __name__ == "__main__":
    unittest.main()
