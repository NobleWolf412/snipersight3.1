"""One read per series per walk — and the invariant that makes it safe.

The engine roster reads the same candle series once per module: seventeen
modules with execsim twice meant up to EIGHTEEN parses of identical rows out
of SQLite for every (symbol, timeframe) a scan pass walked. The cache is
scoped to one `pipeline.run_symbol` call, and the scope is the correctness
argument, not a tuning choice: within one walk the series cannot change,
because engines write facts and never candles, and imports/aggregation both
finish before the walk begins.

That invariant is load-bearing enough to pin with a source scan
(EngineWritesNothing): the day an engine grows a candle write, the cache
becomes a stale-read bug, and that day must be a red test, not a forensic.
"""
import inspect
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine import ingest, pipeline, quality, store

TF, TFS = "1H", 3600
SYM = "BTCUSDT"


class CacheCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        for i in range(6):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (SYM, TF, i * TFS, "1", "2", "0.5", "1.5", "9", "test", i * TFS))
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _count_candle_selects(self, fn):
        hits = []
        self.con.set_trace_callback(
            lambda sql: hits.append(sql) if "FROM candles" in sql else None)
        try:
            fn()
        finally:
            self.con.set_trace_callback(None)
        return len(hits)

    # ---------- the win ----------

    def test_one_select_per_series_inside_the_scope(self):
        with store.candle_cache(self.con):
            n = self._count_candle_selects(
                lambda: [store.get_candles(self.con, SYM, TF) for _ in range(18)])
        self.assertEqual(n, 1, "eighteen engine reads must cost one parse")

    def test_no_cache_means_todays_behaviour_exactly(self):
        n = self._count_candle_selects(
            lambda: [store.get_candles(self.con, SYM, TF) for _ in range(3)])
        self.assertEqual(n, 3, "outside a walk, nothing may change")

    def test_the_scope_ends_when_the_walk_ends(self):
        with store.candle_cache(self.con):
            store.get_candles(self.con, SYM, TF)
        n = self._count_candle_selects(
            lambda: store.get_candles(self.con, SYM, TF))
        self.assertEqual(n, 1, "the cache must not outlive its walk")

    # ---------- the data is the same data ----------

    def test_cached_and_uncached_reads_are_equal(self):
        plain = [dict(r) for r in store.get_candles(self.con, SYM, TF)]
        with store.candle_cache(self.con):
            cached = [dict(r) for r in store.get_candles(self.con, SYM, TF)]
        self.assertEqual(plain, cached)

    def test_every_consumer_idiom_still_works(self):
        """Engines do `[dict(r) for r in rows]` then index by name. Both must
        hold on the cached form."""
        with store.candle_cache(self.con):
            rows = store.get_candles(self.con, SYM, TF)
            as_dicts = [dict(r) for r in rows]
        self.assertEqual(as_dicts[0]["close"], "1.5")
        self.assertEqual(rows[0]["symbol"], SYM)

    def test_consumers_get_private_copies(self):
        """The comprehension every engine opens with is also its isolation:
        mutating one engine's dicts must not reach the next engine's."""
        with store.candle_cache(self.con):
            first = [dict(r) for r in store.get_candles(self.con, SYM, TF)]
            first[0]["close"] = "POISONED"
            second = [dict(r) for r in store.get_candles(self.con, SYM, TF)]
        self.assertEqual(second[0]["close"], "1.5")

    # ---------- the boundaries ----------

    def test_a_ranged_call_bypasses_the_cache(self):
        """Only the whole-series form is cached — the only form an engine
        uses. A windowed call cannot even reach the cached entry, so the
        server's ranged endpoints are outside this design by construction."""
        with store.candle_cache(self.con):
            store.get_candles(self.con, SYM, TF)              # primes the cache
            n = self._count_candle_selects(
                lambda: store.get_candles(self.con, SYM, TF, start_ts=TFS))
        self.assertEqual(n, 1, "a ranged read must go to the database")

    def test_two_connections_do_not_share_a_cache(self):
        # Closed inside the test, not via addCleanup: cleanups run AFTER
        # tearDown on this class, and Windows will not delete the temp dir
        # while the second connection still holds its file.
        con2 = store.connect(Path(self.tmp.name) / "t2.db")
        try:
            with store.candle_cache(self.con):
                store.get_candles(self.con, SYM, TF)
                self.assertEqual(store.get_candles(con2, SYM, TF), [],
                                 "another connection must see its own database, "
                                 "never a neighbour's cache")
        finally:
            con2.close()

    def test_the_scope_survives_an_engine_raising(self):
        try:
            with store.candle_cache(self.con):
                store.get_candles(self.con, SYM, TF)
                raise RuntimeError("an engine died mid-walk")
        except RuntimeError:
            pass
        self.assertNotIn(id(self.con), store._CANDLE_CACHE,
                         "a crash inside the walk must not leak the cache")

    # ---------- run_symbol wears it ----------

    def test_the_walk_runs_inside_the_scope(self):
        seen = []

        def probe_run(con, symbol, tf, tf_seconds):
            seen.append(id(con) in store._CANDLE_CACHE)

        probe = SimpleNamespace(run=probe_run, __name__="probe")
        with patch.object(pipeline, "PER_SYMBOL", (probe,)), \
             patch.object(quality, "assert_market_ready", lambda *a, **k: None), \
             patch.object(ingest, "missing_history", lambda *a, **k: []):
            pipeline.run_symbol(self.con, SYM)
        self.assertTrue(seen and all(seen),
                        "every engine must run inside the candle cache")
        self.assertNotIn(id(self.con), store._CANDLE_CACHE,
                         "and the cache must be gone when the walk returns")


class EngineWritesNothing(unittest.TestCase):
    """The invariant the cache's correctness rests on, pinned as source.

    A cached series is safe precisely because nothing in the walk writes
    candles. `importer` and `aggregator` do — and they run before the walk and
    are not in the roster. The day a roster engine grows an INSERT/UPDATE/
    DELETE on candles, this test is the tripwire that turns a stale-read bug
    into a red diff.
    """

    def test_no_roster_engine_writes_candles(self):
        for mod in dict.fromkeys(pipeline.PER_SYMBOL):
            src = inspect.getsource(mod)
            for verb in ("INSERT INTO candles", "UPDATE candles",
                         "DELETE FROM candles", "REPLACE INTO candles"):
                self.assertNotIn(
                    verb, src,
                    f"{mod.__name__} writes candles — the walk-scoped candle "
                    f"cache is no longer sound; see store.candle_cache")


if __name__ == "__main__":
    unittest.main()
