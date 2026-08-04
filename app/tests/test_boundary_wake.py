"""Wakes land just past candle boundaries, and never starve the heartbeat.

The sleep was a blind 60-second tick. A candle is this system's unit of
knowledge — engines are deliberately blind between closes (§5) — yet when one
closed, the scanner was a uniformly random 0-60s into its nap before looking.
The prior project met the same defect from the caching side: elapsed-anchored
expiry served a reading up to ~59 minutes stale past a boundary, and 84 LONG
rejections in one session traced to it. Staleness anchors to the BOUNDARY,
because the boundary is when the world can change.

Two constraints share the nap, and both are pinned here:
  · a wake lands inside (boundary, boundary + buffer + poll-jitter] of every
    boundary — the alignment the change exists for
  · consecutive wakes never exceed POLL_SECONDS apart — the drift monitor
    wants elapsed cadence, and the health light declares the scanner stuck at
    90s; both hold because next_wake is capped, by construction
"""
import inspect
import unittest

import live
from engine import importer


class GridCoversEveryBoundary(unittest.TestCase):
    """The claim that lets ONE grid serve every timeframe, pinned as fact."""

    def test_every_tracked_granularity_sits_on_the_grid(self):
        for tf, gran in importer.TF_SECONDS.items():
            self.assertEqual(gran % live.CANDLE_GRID_S, 0,
                             f"{tf} closes off the 15m grid — one aligned wake "
                             f"no longer covers every boundary")

    def test_daily_and_weekly_edges_sit_on_the_grid(self):
        """Midnight UTC and Monday 00:00 UTC are epoch multiples of 900s, so
        the calendar boundaries land on the grid too."""
        import datetime as dt
        midnight = dt.datetime(2026, 8, 4, tzinfo=dt.timezone.utc).timestamp()
        monday = dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual(midnight % live.CANDLE_GRID_S, 0)
        self.assertEqual(monday % live.CANDLE_GRID_S, 0)


class NextWakeMath(unittest.TestCase):
    B = 1_700_000_100 - (1_700_000_100 % 900)      # a boundary, exactly

    def test_just_before_a_boundary_lands_just_after_it(self):
        sleep = live.next_wake(self.B - 10)
        self.assertAlmostEqual(sleep, 10 + live.CANDLE_FINALIZATION_S)

    def test_inside_the_finalization_window_waits_only_for_it(self):
        """now = boundary+2 with a 5s buffer must sleep 3s — not 903. The
        candidate list starts at THIS boundary's target for exactly this case."""
        sleep = live.next_wake(self.B + 2)
        self.assertAlmostEqual(sleep, live.CANDLE_FINALIZATION_S - 2)

    def test_mid_candle_is_the_heartbeat(self):
        sleep = live.next_wake(self.B + 300)
        self.assertEqual(sleep, live.POLL_SECONDS,
                         "far from a boundary, the drift heartbeat rules")

    def test_never_longer_than_the_poll(self):
        for off in range(0, 900, 7):
            self.assertLessEqual(live.next_wake(self.B + off), live.POLL_SECONDS,
                                 "a nap past POLL_SECONDS starves the drift "
                                 "monitor and trips the 90s health light")

    def test_never_a_hot_loop(self):
        for off in (live.CANDLE_FINALIZATION_S - 0.2,
                    live.CANDLE_FINALIZATION_S - 0.001, 899.9):
            self.assertGreaterEqual(live.next_wake(self.B + off), 1.0,
                                    "a wake a hair before its target must not "
                                    "degenerate into a spin")

    def test_every_boundary_gets_an_aligned_wake(self):
        """The property the whole change exists for: walk the clock forward by
        repeated next_wake naps from an arbitrary start, and every boundary in
        two hours is visited inside its finalization window."""
        t = self.B + 137.3                          # arbitrary mid-candle start
        wakes = []
        while t < self.B + 2 * 3600:
            t += live.next_wake(t)
            wakes.append(t)
        for k in range(1, 8):
            edge = self.B + k * 900
            hits = [w for w in wakes
                    if edge < w <= edge + live.CANDLE_FINALIZATION_S + 1.0]
            self.assertTrue(hits, f"boundary +{k*900}s got no aligned wake")

    def test_heartbeat_spacing_holds_across_the_walk(self):
        t = self.B + 41.0
        prev = t
        for _ in range(300):
            t += live.next_wake(t)
            self.assertLessEqual(t - prev, live.POLL_SECONDS + 1e-9)
            prev = t


class TheLoopWearsIt(unittest.TestCase):
    def test_main_sleeps_through_next_wake(self):
        src = inspect.getsource(live.main)
        self.assertIn("time.sleep(next_wake(", src,
                      "the loop has gone back to a blind tick")
        self.assertNotIn("time.sleep(POLL_SECONDS)", src)

    def test_the_pass_logs_its_boundary_lag(self):
        """The buffer is a modelled constant until production logs argue
        otherwise — the lag figure is how the argument gets made."""
        src = inspect.getsource(live.main)
        self.assertIn("boundary_lag", src)


if __name__ == "__main__":
    unittest.main()
