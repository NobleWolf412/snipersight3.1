"""Universe ranking must be complete, throttled, and fail closed.

Regression cover for the v0.1 defect: six workers fired 388 stats calls with no
throttle and no retry, ~28% came back HTTP 429, and a DIFFERENT third failed
each run. Membership churned 3-5 symbols between refreshes minutes apart, so
point-in-time eligibility — the gate on every trade — was partly a coin flip.

These tests use a stub transport. None of them touch the network.
"""
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from engine import store, universe


def _http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


class RateLimiterTest(unittest.TestCase):
    def test_spacing_is_global_not_per_thread(self):
        """N workers each pausing 1/N s still bursts N requests at once, so the
        gate has to be shared. 10 acquires at 50/s must take >= ~0.18s."""
        lim = universe._RateLimiter(50.0)
        start = time.monotonic()
        for _ in range(10):
            lim.acquire()
        self.assertGreaterEqual(time.monotonic() - start, 0.17)

    def test_concurrent_workers_are_serialised(self):
        from concurrent.futures import ThreadPoolExecutor
        lim = universe._RateLimiter(50.0)
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: lim.acquire(), range(10)))
        self.assertGreaterEqual(time.monotonic() - start, 0.17,
                                "workers bypassed the shared limiter")


class RetryTest(unittest.TestCase):
    def test_429_is_retried_then_succeeds(self):
        calls = []

        def fake(req, timeout=None):
            calls.append(req.full_url)
            if len(calls) < 3:
                raise _http_error(429)
            return mock.MagicMock(__enter__=lambda s: mock.MagicMock(
                read=lambda: b'{"ok":1}'), __exit__=lambda *a: False)

        with mock.patch.object(universe.urllib.request, "urlopen", fake), \
             mock.patch.object(universe.time, "sleep"):
            self.assertEqual(universe._get("/x"), {"ok": 1})
        self.assertEqual(len(calls), 3, "should have retried twice")

    def test_404_is_not_retried(self):
        calls = []

        def fake(req, timeout=None):
            calls.append(1)
            raise _http_error(404)

        with mock.patch.object(universe.urllib.request, "urlopen", fake), \
             mock.patch.object(universe.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                universe._get("/x")
        self.assertEqual(len(calls), 1, "a 404 will never succeed on retry")

    def test_gives_up_after_the_configured_retries(self):
        calls = []

        def fake(req, timeout=None):
            calls.append(1)
            raise _http_error(429)

        with mock.patch.object(universe.urllib.request, "urlopen", fake), \
             mock.patch.object(universe.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                universe._get("/x", retries=2)
        self.assertEqual(len(calls), 3, "1 attempt + 2 retries")


class CoverageGateTest(unittest.TestCase):
    """The core fix: a partial ranking must NEVER overwrite a good universe."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "universe.db")
        # warm, liquid symbols so admission has something to admit
        for sym in ("BTC-USD", "ETH-USD", "AAA-USD"):
            for i in range(universe.MIN_DAILY_CANDLES + 1):
                self.con.execute(
                    "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sym, "1D", 86400 * i, "1", "2", "0.5", "1.5", "10",
                     "coinbase", 86400 * i + 1))
        self.con.commit()
        self._health = universe.LAST_RANK_HEALTH

    def tearDown(self):
        universe.LAST_RANK_HEALTH = self._health   # module global, restore it
        self.con.close()
        self.tmp.cleanup()

    def _snapshots(self):
        return self.con.execute(
            "SELECT COUNT(*) FROM facts WHERE kind='universe'").fetchone()[0]

    def test_full_coverage_records_a_snapshot(self):
        ranked = [("BTC-USD", 5e8), ("ETH-USD", 2e8), ("AAA-USD", 9e6)]
        universe.LAST_RANK_HEALTH = {"attempted": 3, "succeeded": 3, "failed": 0}
        with mock.patch.object(universe, "rank_by_volume", return_value=ranked):
            out = universe.refresh(self.con)
        self.assertEqual(out["source"], "coinbase")
        self.assertEqual(self._snapshots(), 1)

    def test_partial_coverage_refuses_to_overwrite(self):
        good = [("BTC-USD", 5e8), ("ETH-USD", 2e8), ("AAA-USD", 9e6)]
        universe.LAST_RANK_HEALTH = {"attempted": 3, "succeeded": 3, "failed": 0}
        with mock.patch.object(universe, "rank_by_volume", return_value=good):
            universe.refresh(self.con)
        self.assertEqual(self._snapshots(), 1)

        # now a degraded sweep: AAA vanished only because its call failed
        universe.LAST_RANK_HEALTH = {"attempted": 300, "succeeded": 216,
                                     "failed": 84, "sample_failures": []}
        with mock.patch.object(universe, "rank_by_volume",
                               return_value=[("BTC-USD", 5e8)]):
            out = universe.refresh(self.con)

        self.assertEqual(out["source"], "low_coverage")
        self.assertEqual(self._snapshots(), 1, "must NOT write a second fact")
        # and the good universe is still the authority
        self.assertTrue(universe.admitted_at(self.con, "AAA-USD", 10 ** 10))

    def test_boundary_just_above_floor_is_accepted(self):
        universe.LAST_RANK_HEALTH = {"attempted": 100, "succeeded": 98, "failed": 2}
        with mock.patch.object(universe, "rank_by_volume",
                               return_value=[("BTC-USD", 5e8)]):
            out = universe.refresh(self.con)
        self.assertEqual(out["source"], "coinbase")

    def test_boundary_just_below_floor_is_refused(self):
        universe.LAST_RANK_HEALTH = {"attempted": 100, "succeeded": 96, "failed": 4}
        with mock.patch.object(universe, "rank_by_volume",
                               return_value=[("BTC-USD", 5e8)]):
            out = universe.refresh(self.con)
        self.assertEqual(out["source"], "low_coverage")

    def test_injected_rankings_bypass_the_gate(self):
        """Tests and replays inject a ranking directly; it is complete by
        construction and must not be judged against network coverage."""
        universe.LAST_RANK_HEALTH = {"attempted": 300, "succeeded": 1, "failed": 299}
        out = universe.refresh(self.con, ranked=[("BTC-USD", 5e8)])
        self.assertEqual(out["source"], "coinbase")
        self.assertEqual(self._snapshots(), 1)


class VersionTest(unittest.TestCase):
    def test_version_bumped_past_the_broken_ranking(self):
        """v0.1 snapshots were built from partial data. They must not be read
        as if they came from the fixed sweep."""
        self.assertNotEqual(universe.UNIVERSE_VERSION, "universe-v0.1-draft")


if __name__ == "__main__":
    unittest.main()
