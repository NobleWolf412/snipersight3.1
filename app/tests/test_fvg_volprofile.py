"""FVG and volume-profile — evidence engines, held to the house conventions.

The properties pinned here are the ones that make an evidence engine safe to
leave running unattended for months:

  · GEOMETRY on hand-stated bars — every threshold in an assertion is a number
    this file can point at (the test_manual convention).
  · CAUSALITY — a fact confirms at the close of the bar that completes it,
    and a gap can never be filled by a bar that predates its own completion.
  · NO RESTATEMENT — a longer series only APPENDS events; the frontier test
    is what makes an append-only store and a rolling measurement compatible.
  · IDEMPOTENCE — a re-run over identical candles writes zero new facts.
  · NOT A GATE — no trading module imports either engine, and both sit in the
    roster so they actually run (an engine that is built, tested and never
    run emits nothing to grade — how `ranges` and `cooldowns` both died).
"""
import inspect
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import execsim, fvg, pipeline, risk, scalein, setups, store, volprofile
from engine.swings import compute_atr

TF, TFS = "1H", 3600


def bars(spec):
    """spec = [(o,h,l,c,v), ...] -> store-shaped candle dicts."""
    return [{"open_ts": 1_700_000_000 + i * TFS, "open": Decimal(str(o)),
             "high": Decimal(str(h)), "low": Decimal(str(l)),
             "close": Decimal(str(c)), "volume": Decimal(str(v))}
            for i, (o, h, l, c, v) in enumerate(spec)]


def flat(n, base=100, v=10):
    return [(base, base + 1, base - 1, base, v)] * n


class FvgGeometry(unittest.TestCase):
    def series(self, *extra):
        # 20 warm bars so ATR(14) exists, then the pattern under test.
        return bars(flat(20) + list(extra))

    def detect(self, c):
        return fvg.detect(c, compute_atr(c))

    def test_bullish_gap_between_nonoverlapping_wicks(self):
        # bar A high 101 ... bar C low 104 -> gap [101, 104], ~1.5 ATR wide
        c = self.series((100, 103, 100, 103, 10),      # displacement bar
                        (103, 106, 104, 105, 10))      # third bar, low 104 > 101
        gaps = self.detect(c)
        self.assertEqual(len(gaps), 1)
        g = gaps[0]
        self.assertEqual(g["direction"], "BULL")
        self.assertEqual(g["bottom"], Decimal(101))
        self.assertEqual(g["top"], Decimal(104))
        self.assertIsNone(g["filled_i"], "nothing has traded back through it")

    def test_bearish_gap_mirrors(self):
        c = self.series((100, 100, 97, 97, 10),
                        (97, 96, 94, 95, 10))          # high 96 < bar-A low 99
        gaps = self.detect(c)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["direction"], "BEAR")
        self.assertEqual(gaps[0]["top"], Decimal(99))
        self.assertEqual(gaps[0]["bottom"], Decimal(96))

    def test_overlapping_wicks_are_no_gap(self):
        c = self.series((100, 102, 100, 101, 10),
                        (101, 103, 100.5, 102, 10))    # low 100.5 < bar-A high 101
        self.assertEqual(self.detect(c), [])

    def test_the_recording_floor_drops_bar_noise(self):
        """A 0.2-ATR sliver is inside ordinary wick-to-wick jitter. The floor
        is a recording floor, not a quality grade — above it everything is
        emitted with size_atr, and any quality line is drawn at grading time."""
        c = self.series((100, 101.1, 100, 101, 10),
                        (101, 102, 101.2, 101.5, 10))  # gap 101->101.2, ~0.1 ATR
        self.assertEqual(self.detect(c), [])

    def test_full_traversal_fills_and_dates_the_fill(self):
        c = self.series((100, 103, 100, 103, 10),
                        (103, 106, 104, 105, 10),      # gap [101,104] at index 21
                        (105, 105, 100.5, 102, 10))    # low 100.5 <= 101: filled
        g = self.detect(c)[0]
        self.assertEqual(g["filled_i"], 22)

    def test_a_touch_is_not_a_fill(self):
        """Entering the gap without traversing it leaves the gap standing.
        'Half-mitigated' taxonomies are ambiguity wearing labels; absence of a
        FILLED fact is the record that it held."""
        c = self.series((100, 103, 100, 103, 10),
                        (103, 106, 104, 105, 10),
                        (105, 105, 102, 103, 10))      # dips to 102, above 101
        self.assertIsNone(self.detect(c)[0]["filled_i"])

    def test_warmup_refusal(self):
        """No ATR, no scale, no fact — a gap with no volatility yardstick
        would carry a size_atr someone downstream would believe."""
        c = bars([(100, 103, 100, 103, 10), (100, 103, 100, 103, 10),
                  (103, 106, 104, 105, 10)])
        self.assertEqual(self.detect(c), [])


class VolprofileStates(unittest.TestCase):
    def test_hysteresis_enters_and_holds(self):
        self.assertEqual(volprofile.classify(None, 2.5), "AT_HVN")
        self.assertEqual(volprofile.classify("AT_HVN", 1.7), "AT_HVN",
                         "inside the deadband the state holds")
        self.assertEqual(volprofile.classify("AT_HVN", 1.4), "MID")
        self.assertEqual(volprofile.classify(None, 0.3), "AT_LVN")
        self.assertEqual(volprofile.classify("AT_LVN", 0.45), "AT_LVN")
        self.assertEqual(volprofile.classify("AT_LVN", 0.6), "MID")
        self.assertEqual(volprofile.classify(None, 1.0), "MID")

    def test_warmup_refusal(self):
        c = bars(flat(volprofile.VP_WINDOW_BARS))      # one short of window+1
        self.assertEqual(volprofile.walk_states(c), [])

    @staticmethod
    def shelf(n):
        """A window with CONTRAST: price camps in a narrow band on heavy
        volume, punctuated by wide thin bars that spread a little volume
        across many bins and hold the median down. A first draft of this
        fixture used uniform narrow bars only — and the engine correctly
        called that MID, because a profile where every nonzero bin is equal
        has no node relative to its own median. An HVN is a relative claim."""
        out = []
        for i in range(n):
            out.append((90, 110, 90, 100, 10) if i % 8 == 7
                       else (100, 101, 99, 100, 100))
        return out

    def test_heavy_shelf_then_thin_excursion(self):
        """Price camped in one band against a contrasted window is AT its own
        high-volume node; a bar breaking to prices the window barely traded
        lands at a low-volume one."""
        c = bars(self.shelf(volprofile.VP_WINDOW_BARS + 30)
                 + [(100, 121, 119, 120, 1)] * 3)      # thin push past the wides
        states = volprofile.walk_states(c)
        self.assertTrue(states, "a state must establish once the window fills")
        self.assertEqual(states[0]["from"], None, "first state is ESTABLISHED")
        self.assertEqual(states[0]["state"], "AT_HVN",
                         "camping in one band against thin surroundings IS the node")
        self.assertEqual(states[-1]["state"], "AT_LVN",
                         "a thin excursion prices where volume never lived")

    def test_the_frontier_only_appends(self):
        """THE property that makes a rolling measurement compatible with an
        append-only store: growing the series must extend the transition list,
        never rewrite it. This is why bins sit on an absolute grid anchored to
        the immutable first candle — window-ranged bins would re-label history
        with every close."""
        c = bars(self.shelf(volprofile.VP_WINDOW_BARS + 40)
                 + [(100, 121, 119, 120, 1)] * 6)
        shorter = volprofile.walk_states(c[:-6])
        longer = volprofile.walk_states(c)
        self.assertEqual(longer[:len(shorter)], shorter,
                         "a new candle restated history — the store would fill "
                         "with near-duplicate transitions every cycle")

    def test_bin_step_is_scale_free_and_fixed(self):
        self.assertEqual(volprofile.bin_step(Decimal("40000")), Decimal("100.00000000"))
        self.assertGreater(volprofile.bin_step(Decimal("0.00003410")), 0)


class EngineContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, spec, symbol="BTCUSDT"):
        for i, (o, h, l, c, v) in enumerate(spec):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, TF, 1_700_000_000 + i * TFS, str(o), str(h), str(l),
                 str(c), str(v), "test", i))
        self.con.commit()

    def test_fvg_run_writes_causal_facts_and_is_idempotent(self):
        self.load(flat(20) + [(100, 103, 100, 103, 10), (103, 106, 104, 105, 10),
                              (105, 105, 100.5, 102, 10)])
        r1 = fvg.run(self.con, "BTCUSDT", TF, TFS)
        self.assertEqual((r1["CREATED"], r1["FILLED"]), (1, 1))
        rows = store.get_facts(self.con, "BTCUSDT", TF, "fvg", fvg.FVG_VERSION)
        for row in rows:
            self.assertEqual(row["confirmed_at"], row["market_time"] + TFS,
                             "an event is knowable at its bar's close, not before")
        r2 = fvg.run(self.con, "BTCUSDT", TF, TFS)
        self.assertEqual((r2["CREATED"], r2["FILLED"]), (0, 0),
                         "a re-run over identical candles must write nothing")

    def test_volprofile_run_is_idempotent(self):
        self.load(flat(volprofile.VP_WINDOW_BARS + 30, v=100)
                  + [(100, 121, 119, 120, 1)] * 3)
        r1 = volprofile.run(self.con, "BTCUSDT", TF, TFS)
        self.assertGreater(r1["VP_STATE"], 0)
        r2 = volprofile.run(self.con, "BTCUSDT", TF, TFS)
        self.assertEqual(r2["VP_STATE"], 0)


class HouseConventions(unittest.TestCase):
    def test_no_trading_module_consumes_the_evidence(self):
        for consumer in (setups, risk, execsim, scalein):
            src = inspect.getsource(consumer)
            for name in ("fvg", "volprofile"):
                self.assertNotIn(f"import {name}", src,
                                 f"{consumer.__name__} consumes ungraded evidence")
                self.assertNotIn(f"{name}.", src.replace(f"# {name}.", ""),
                                 f"{consumer.__name__} reaches into {name}")

    def test_both_engines_are_rostered(self):
        """Built, tested and never run is how `ranges` and `cooldowns` died."""
        self.assertIn(fvg, pipeline.DESCRIPTIVE)
        self.assertIn(volprofile, pipeline.DESCRIPTIVE)
        self.assertIn("fvg", pipeline.names())
        self.assertIn("volprofile", pipeline.names())


if __name__ == "__main__":
    unittest.main()
