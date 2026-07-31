"""The Kraken candle walk must cover the whole span, or say that it did not.

`fetch_candles` bounded its walk with a guard re-evaluated every pass:

    while cursor < end_ts and guard <= 2 + (end_ts - cursor) // window:

`guard` grows by one per iteration while that allowance SHRINKS by one, so the
two meet at the halfway mark: a span needing N windows stopped at about N/2.
Not a 1970-only fault — it truncated from ANY start date. It stayed invisible
because every floor in `ingest.history_floor` fits inside one 5000-bucket
window (N = 0), so the arithmetic was never exercised until a cold symbol asked
for history from the epoch.

The silence was the expensive half. A truncated walk returned a short list that
looked exactly like "the venue has no more data", and `importer.backfill` booked
every unreached bucket as a gap — 1,983,795 of them in a single 15m run, into
the column `/api/health` sums and `risk.py` halts on.

These tests use a stub transport. None of them touch the network.
"""
import unittest
from unittest import mock

from engine import kraken

GRAN = 86400                       # 1D, so a bucket is a day
START = 1600000000 - 1600000000 % GRAN
SPAN = 100                         # buckets; with MAX=10 that is 10 windows


def _bar(ts):
    return {"time": ts * 1000,     # Kraken serves MILLISECONDS
            "open": "1", "high": "2", "low": "0.5", "close": "1.5",
            "volume": "10"}


def _window(path):
    """The [from, to) the walk asked for, bucket-aligned."""
    params = dict(p.split("=") for p in path.split("?", 1)[1].split("&"))
    lo, hi = int(params["from"]), int(params["to"])
    return lo - lo % GRAN, hi


def _dense(path, retries=None):
    """Every bucket in the requested window — a fully listed contract."""
    lo, hi = _window(path)
    return {"candles": [_bar(t) for t in range(lo, hi, GRAN)]}


class WalkCoversTheWholeSpan(unittest.TestCase):
    def setUp(self):
        self.end = START + SPAN * GRAN
        self.small = mock.patch.object(kraken, "MAX_CANDLES_PER_REQ", 10)
        self.small.start()
        self.addCleanup(self.small.stop)

    def test_a_multi_window_span_is_walked_to_the_end(self):
        """The regression. Ten windows in, ten windows walked — the old guard
        allowed about six and returned 70% of the data as if that were all."""
        with mock.patch.object(kraken, "_get", _dense):
            got = kraken.fetch_candles("PF_XBTUSD", "1D", START, self.end)
        self.assertEqual(len(got), SPAN, "the walk stopped short of the span")
        self.assertEqual(got[0]["open_ts"], START)
        self.assertEqual(got[-1]["open_ts"], self.end - GRAN)

    def test_it_issues_at_least_one_request_per_window(self):
        calls = []

        def counting(path, retries=None):
            calls.append(path)
            return _dense(path)

        with mock.patch.object(kraken, "_get", counting):
            kraken.fetch_candles("PF_XBTUSD", "1D", START, self.end)
        self.assertGreaterEqual(len(calls), SPAN // 10,
                                "fewer requests than there are windows to cover")

    def test_coverage_does_not_degrade_as_the_span_grows(self):
        """The old guard's signature, stated directly: the longer the span, the
        larger the fraction silently dropped, because the allowance was re-read
        against the shrinking remainder on every pass. Full coverage at every
        size is the property that forbids it."""
        with mock.patch.object(kraken, "_get", _dense):
            for windows in (1, 4, 10, 20):
                with self.subTest(windows=windows):
                    buckets = windows * 10
                    got = kraken.fetch_candles(
                        "PF_XBTUSD", "1D", START, START + buckets * GRAN)
                    self.assertEqual(len(got), buckets)

    def test_a_gap_before_listing_is_skipped_not_read_as_the_end(self):
        """A contract listed mid-span must still be found. An empty window means
        'nothing listed yet in THIS range', not 'no data at all'."""
        listed = START + 60 * GRAN

        def after_listing(path, retries=None):
            lo, hi = _window(path)
            return {"candles": [_bar(t) for t in range(max(lo, listed), hi, GRAN)]}

        with mock.patch.object(kraken, "_get", after_listing):
            got = kraken.fetch_candles("PF_NEWUSD", "1D", START, self.end)
        self.assertEqual(len(got), SPAN - 60)
        self.assertEqual(got[0]["open_ts"], listed)


class WalkStillTerminates(unittest.TestCase):
    """Fixing the truncation must not reintroduce the spin it was guarding."""

    def setUp(self):
        self.end = START + SPAN * GRAN
        self.small = mock.patch.object(kraken, "MAX_CANDLES_PER_REQ", 10)
        self.small.start()
        self.addCleanup(self.small.stop)

    def test_a_venue_that_never_advances_stops(self):
        calls = []

        def stuck(path, retries=None):
            calls.append(path)
            return {"candles": [_bar(START)]}      # same bucket, forever

        with mock.patch.object(kraken, "_get", stuck):
            got = kraken.fetch_candles("PF_STUCKUSD", "1D", START, self.end)
        self.assertLessEqual(len(calls), 3, "no-forward-progress must break early")
        self.assertEqual(len(got), 1)

    def test_exhausting_the_budget_is_loud(self):
        """The backstop firing means the returned span is PARTIAL. Saying so is
        the whole difference between a short list and a fabricated gap run."""
        def crawl(path, retries=None):
            lo, _ = _window(path)
            return {"candles": [_bar(lo), _bar(lo + GRAN)]}   # 2 buckets a pass

        log = mock.MagicMock()
        with mock.patch.object(kraken, "_get", crawl), \
             mock.patch("engine.runlog.get_logger", return_value=log):
            got = kraken.fetch_candles("PF_SLOWUSD", "1D", START, self.end)
        self.assertTrue(log.warning.called,
                        "a truncated walk must never return silently")
        self.assertIn("PARTIAL", log.warning.call_args[0][0])
        self.assertLess(len(got), SPAN, "this walk is expected to be short")

    def test_a_healthy_walk_says_nothing(self):
        """The backstop is sized never to fire on a well-behaved venue — a
        warning per import would be the cry-wolf failure all over again."""
        log = mock.MagicMock()
        with mock.patch.object(kraken, "_get", _dense), \
             mock.patch("engine.runlog.get_logger", return_value=log):
            kraken.fetch_candles("PF_XBTUSD", "1D", START, self.end)
        self.assertFalse(log.warning.called)


class RealFloorsFitTheBudget(unittest.TestCase):
    """Why this was never seen in production: at the shipped
    MAX_CANDLES_PER_REQ every floor is a single window, so N = 0 and the broken
    arithmetic had nothing to get wrong. That is luck, not design."""

    def test_every_history_floor_needs_one_window(self):
        import time

        from engine import ingest
        now = int(time.time())
        for tf, gran in kraken.NATIVE_TFS.items():
            with self.subTest(tf=tf):
                span = now - ingest.history_floor(tf, now)
                self.assertLess(span, gran * kraken.MAX_CANDLES_PER_REQ,
                                f"{tf} now needs a multi-window walk")


if __name__ == "__main__":
    unittest.main()
