"""Cold-start import floor — the 1970 bug.

`live.cycle` computed its incremental start as `MAX(open_ts) + granularity`.
`MAX` is NULL for a symbol with no candles, the fallback was `or 0`, and so a
cold symbol asked the venue for history from **1970-01-01**. The adapter's
no-forward-progress guard aborted that walk in the 1990s, before reaching real
data, and nothing imported.

Measured before the fix: PF_XLMUSD failed this way on 24 consecutive cycles,
writing 1,983,798 fabricated 15m gaps per run across 4,950 `import_log` rows.
The wasted requests were the small part. `/api/health` sums `n_gaps`, and
`risk.py` halts on a BLOCKED data-health verdict — so a single cold symbol could
poison the signal the risk authority trusts.
"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from engine import ingest, store


class HistoryFloor(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())

    def test_no_timeframe_ever_reaches_back_to_1970(self):
        """The bug, stated as the property that must never hold again."""
        for tf in ("15m", "1H", "4H", "1D", "1W"):
            with self.subTest(tf=tf):
                self.assertGreater(ingest.history_floor(tf, self.now),
                                   86400 * 365 * 30,   # ~2000-01-01
                                   f"{tf} floor is in the 20th century")

    def test_floors_are_ordered_by_how_much_history_a_timeframe_needs(self):
        """15m needs weeks, 1D needs years. Asking for four years of 15m would
        be a million bars of data no engine reads."""
        self.assertLess(ingest.history_floor("1D", self.now),
                        ingest.history_floor("1H", self.now))
        self.assertLess(ingest.history_floor("1H", self.now),
                        ingest.history_floor("15m", self.now))

    def test_the_daily_floor_matches_the_declared_constant(self):
        """One floor, defined once. If onboarding and the live loop disagreed,
        a symbol would import different history depending on which path first
        touched it."""
        from datetime import datetime, timezone
        expected = int(datetime.strptime(ingest.DAILY_SINCE, "%Y-%m-%d")
                       .replace(tzinfo=timezone.utc).timestamp())
        self.assertEqual(ingest.history_floor("1D", self.now), expected)

    def test_an_unknown_timeframe_falls_back_to_the_daily_floor(self):
        """Conservative: too much history is a slow import, too little is a
        silently short series that the warmth gate then judges."""
        self.assertEqual(ingest.history_floor("4H", self.now),
                         ingest.history_floor("1D", self.now))


class LiveLoopUsesIt(unittest.TestCase):
    def test_the_live_loop_no_longer_defaults_to_zero(self):
        import inspect

        import live
        src = inspect.getsource(live.cycle)
        self.assertIn("ingest.history_floor", src,
                      "the live loop must floor a cold symbol, not start at 0")
        self.assertNotIn("fetchone()[0] or 0", src,
                         "the `or 0` fallback is what asked for 1970")

    def test_a_warm_symbol_still_resumes_incrementally(self):
        """The fix must not turn every cycle into a full re-import — the whole
        loop depends on asking only for what is new."""
        import inspect

        import live
        src = inspect.getsource(live.cycle)
        self.assertIn("(last + gran) if last else", src,
                      "a warm symbol must resume from its own watermark")


# --- The sibling bug: a PARTIAL onboard ----------------------------------
#
# `history_floor` repairs a timeframe with NO candles, because the watermark is
# NULL and `live.cycle` falls through to the floor. It cannot repair one that is
# merely SHORT: a partial onboard leaves a non-NULL watermark and the loop only
# ever walks forward from it. Nothing else repaired it either — `universe.refresh`
# picks the retry set by DAILY candle count, so a symbol with warm 1D and empty
# intraday never entered `warming`. That is precisely how PF_XLMUSD got stuck.


def _warm(con, sym, tf, gran, first, n, source="kraken-perp"):
    # OR REPLACE because `importer.backfill` re-imports idempotently, and the
    # repair counter has to stay right when it re-serves bars we already hold.
    con.executemany(
        "INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(sym, tf, first + i * gran, "1", "2", "0.5", "1.5", "10", source, 0)
         for i in range(n)])
    con.commit()


class MissingHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "h.db")
        self.now = int(time.time())
        # a properly onboarded 1D series: the anchor everything else is judged
        # against, so these symbols are NOT young listings
        _warm(self.con, "PF_AAAUSD", "1D", 86400,
              ingest.history_floor("1D", self.now), 400)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_an_empty_timeframe_is_flagged(self):
        """PF_XLMUSD exactly: 1D warm, 1H and 15m at zero."""
        self.assertEqual(sorted(ingest.missing_history(self.con, "PF_AAAUSD", self.now)),
                         ["15m", "1H"])

    def test_a_partial_timeframe_is_flagged(self):
        """The case `history_floor` CANNOT reach — a non-NULL watermark means
        the live loop only ever walks forward, leaving the history behind it
        missing for as long as the symbol is tracked."""
        _warm(self.con, "PF_AAAUSD", "1H", 3600, self.now - 2 * 86400, 48)
        self.assertIn("1H", ingest.missing_history(self.con, "PF_AAAUSD", self.now))

    def test_a_complete_timeframe_is_not_flagged(self):
        _warm(self.con, "PF_AAAUSD", "1H", 3600,
              ingest.history_floor("1H", self.now), 24)
        self.assertNotIn("1H", ingest.missing_history(self.con, "PF_AAAUSD", self.now))

    def test_a_young_listing_is_never_flagged(self):
        """A coin listed ten days ago has ten days of 15m and that is the truth,
        not a hole. Without the anchor it would be flagged on every refresh for
        the life of the symbol."""
        listed = self.now - 10 * 86400
        for tf, gran in (("1D", 86400), ("1H", 3600), ("15m", 900)):
            _warm(self.con, "PF_NEWUSD", tf, gran, listed, 5)
        self.assertEqual(ingest.missing_history(self.con, "PF_NEWUSD", self.now), [])

    def test_a_productive_import_retires_the_question(self):
        """Self-termination. Once we have asked from the floor and the venue
        served candles, the series starts where the venue's history starts and
        re-asking cannot conjure a bar that does not exist."""
        self.con.execute(
            "INSERT INTO import_log (symbol,tf,range_start,range_end,n_candles,"
            "n_gaps,gaps,source,run_at,n_bad) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("PF_AAAUSD", "1H", ingest.history_floor("1H", self.now) - 3600,
             self.now, 900, 0, "[]", "kraken-perp", self.now, 0))
        self.con.commit()
        self.assertNotIn("1H", ingest.missing_history(self.con, "PF_AAAUSD", self.now))

    def test_the_1970_rows_do_not_count_as_having_asked(self):
        """The 4,950 epoch rows reached back further than any floor but imported
        NOTHING. Treating them as a productive attempt would suppress the repair
        on exactly the symbol that needs it most."""
        self.con.execute(
            "INSERT INTO import_log (symbol,tf,range_start,range_end,n_candles,"
            "n_gaps,gaps,source,run_at,n_bad) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("PF_AAAUSD", "1H", 3600, self.now, 0, 495948, "[]",
             "kraken-perp", self.now, 0))
        self.con.commit()
        self.assertIn("1H", ingest.missing_history(self.con, "PF_AAAUSD", self.now))

    def test_aggregate_candles_are_not_history(self):
        """A 4H bar is derived from 1H candles we already hold. Counting it
        would let a symbol look warm on the strength of data it does not have."""
        _warm(self.con, "PF_AAAUSD", "1H", 3600,
              ingest.history_floor("1H", self.now), 24, source="agg:4H")
        self.assertIn("1H", ingest.missing_history(self.con, "PF_AAAUSD", self.now))


class RepairHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "r.db")
        self.now = int(time.time())

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_it_counts_rows_added_not_rows_seen(self):
        """`importer.backfill` re-imports the whole window and REPLACEs what is
        already there, so its own `candles` figure is the window's SIZE. Using
        it would report a repair every hour on a symbol that gained nothing."""
        floor = ingest.history_floor("1H", self.now)
        _warm(self.con, "PF_BBBUSD", "1H", 3600, floor, 10)

        def fake_backfill(con, symbol, tf, start_ts, end_ts):
            # re-serves the 10 rows already stored, adds nothing
            _warm(con, symbol, tf, 3600, floor, 10)
            return {"candles": 10, "gaps": 0, "bad": 0}

        with mock.patch.object(ingest.importer, "backfill", fake_backfill):
            gained = ingest.repair_history(self.con, "PF_BBBUSD", ["1H"], self.now)
        self.assertEqual(gained, {"1H": 0}, "re-serving the same bars is not a repair")

    def test_it_reports_what_actually_landed(self):
        floor = ingest.history_floor("1H", self.now)

        def fake_backfill(con, symbol, tf, start_ts, end_ts):
            _warm(con, symbol, tf, 3600, floor, 24)
            return {"candles": 24, "gaps": 0, "bad": 0}

        with mock.patch.object(ingest.importer, "backfill", fake_backfill):
            gained = ingest.repair_history(self.con, "PF_BBBUSD", ["1H"], self.now)
        self.assertEqual(gained, {"1H": 24})

    def test_it_asks_from_the_floor_not_from_the_watermark(self):
        """The whole point: resuming from the watermark is what left the hole."""
        _warm(self.con, "PF_BBBUSD", "1H", 3600, self.now - 2 * 86400, 48)
        seen = {}

        def fake_backfill(con, symbol, tf, start_ts, end_ts):
            seen[tf] = start_ts
            return {"candles": 0, "gaps": 0, "bad": 0}

        with mock.patch.object(ingest.importer, "backfill", fake_backfill):
            ingest.repair_history(self.con, "PF_BBBUSD", ["1H"], self.now)
        self.assertEqual(seen["1H"], ingest.history_floor("1H", self.now))


class OnboardingPathIsCallable(unittest.TestCase):
    """`run_engines` is the recovery path this whole file is about. It spent a
    window referring to a `scalein` its module no longer imported, so every
    `onboard` — and so every repair — would have died on a NameError. Nothing
    in the suite called it, which is why nothing caught it."""

    def test_run_engines_resolves_every_name_it_uses(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = store.connect(Path(tmp.name) / "e.db")
        self.addCleanup(con.close)
        # Patched on `engine.quality` itself: the engine loop moved into
        # `pipeline.run_symbol`, which imports quality lazily, so ingest no
        # longer re-exports it. The property under test is unchanged.
        from engine import quality
        with mock.patch.object(quality, "assert_market_ready",
                               lambda *a, **k: None):
            try:
                ingest.run_engines(con, "PF_AAAUSD")
            except NameError as exc:
                self.fail(f"run_engines has an unbound name: {exc}")

    def test_onboarding_and_the_live_loop_share_one_floor(self):
        """If they disagreed, a symbol would import different history depending
        on which path first touched it."""
        import inspect
        src = inspect.getsource(ingest.backfill_history)
        self.assertIn("history_floor", src,
                      "onboarding must read the same floor table as live.cycle")


class RefreshUniverseRepairs(unittest.TestCase):
    """The repair only ever fires from the hourly refresh, so these pin that it
    is actually wired in — and that a failed ranking sweep does not disable it."""

    def setUp(self):
        import live
        self.live = live
        self._saved = live._last_universe_refresh
        live._last_universe_refresh = 0.0      # defeat the hourly throttle
        self.addCleanup(setattr, live, "_last_universe_refresh", self._saved)
        self.log = mock.MagicMock()

    def _run_with(self, refresh_result):
        called = []
        with mock.patch.object(self.live.universe, "refresh",
                               return_value=refresh_result), \
             mock.patch.object(self.live, "repair_short_history",
                               lambda *a, **k: called.append(True)):
            self.live.refresh_universe(None, self.log)
        return called

    def test_a_normal_refresh_runs_the_repair_pass(self):
        self.assertTrue(
            self._run_with({"source": "coinbase", "members": [], "warming": []}),
            "a partial onboard is only ever repaired here")

    def test_an_unavailable_ranking_does_not_disable_the_repair(self):
        """The early return used to skip everything below it. A hole in the
        candle store is not a fact about whether the rank endpoint was up."""
        self.assertTrue(
            self._run_with({"source": "unavailable", "members": [], "warming": []}),
            "a failed ranking sweep must not suppress the history repair")


if __name__ == "__main__":
    unittest.main()
