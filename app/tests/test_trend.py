"""The trend-continuation playbook — what it must enter, and what it must not do.

Built 4 Aug 2026 to answer a MEASUREMENT problem, not a P&L one. Grading the
moving average against the book returned LONG x ABOVE = 0 and SHORT x BELOW = 0
across all 477 closed trades: both shipped playbooks enter counter-move, so
every trend-following factor is a constant on this book and cannot be graded at
all. This module records trades that buy strength, which is the only thing that
can populate that cohort.

Two properties matter more than anything about its returns:

  1. IT MUST ENTER WITH THE TREND. If it drifts into buying dips like the
     others, the empty cohort stays empty and the module has no reason to
     exist.
  2. IT MUST NOT TRADE. It ships measured-and-not-enabled, isolated by version
     exactly as `breakout` is — no execsim, no risk, no book.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import ma, pipeline, store, trend
from engine.trend import TREND_VERSION


class IsolationCase(unittest.TestCase):
    """It ships switched off, and the switch is structural rather than a flag."""

    def test_it_emits_under_its_own_version(self):
        from engine.setups import SETUP_VERSION
        self.assertNotEqual(TREND_VERSION, SETUP_VERSION,
                            "sharing the setup version would put these trades "
                            "straight into the graded book")

    def test_the_trading_path_cannot_see_it(self):
        """execsim and risk query SETUP_VERSION / SCALE_VERSION. Neither reads
        TREND_VERSION, so the isolation is a property of the query rather than
        of a flag someone has to remember."""
        for mod in ("execsim", "risk"):
            src = (Path(__file__).resolve().parent.parent / "engine"
                   / f"{mod}.py").read_text(encoding="utf-8")
            self.assertNotIn("TREND_VERSION", src,
                             f"{mod} reads the trend version — it would trade")
            self.assertNotIn("trend", src.split("\n")[0:40].__str__().lower()
                             .replace("trending", ""),
                             f"{mod} imports the trend engine")

    def test_it_is_measured_not_enabled(self):
        self.assertIn(trend, pipeline.MEASURED_NOT_ENABLED)
        self.assertNotIn(trend, pipeline.TRADING)

    def test_it_still_runs_every_cycle(self):
        """An engine that is built and never run emits nothing to grade —
        which is how ranges.py and cooldowns.py both died."""
        self.assertIn(trend, pipeline.PER_SYMBOL)


class TriggerCase(unittest.TestCase):
    """Synthetic candles, because the trigger must be provable rather than
    observed. A rising series puts price above a rising ribbon; a dip toward
    the fast average and a close back above it is the trade."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    # *USDT resolves to the Phemex perp in venues.py; a bare name has no
    # venue and costs.profile_for refuses it, which is correct behaviour.
    def _load(self, closes, tf="1H", symbol="TRENDUSDT"):
        """Bars whose close sits at the END of their move, not in the middle.

        The first version put close exactly midway between high and low, which
        can NEVER satisfy the conviction test (close in the top/bottom third) —
        so the fixture, not the engine, was rejecting every candidate. A real
        bar that closes on its high is what conviction looks like.
        """
        sec = 3600
        prev = closes[0]
        for i, cl in enumerate(closes):
            up = cl >= prev
            hi = cl * 1.0005 if up else max(prev, cl) * 1.001
            lo = min(prev, cl) * 0.999 if up else cl * 0.9995
            prev = cl
            self.con.execute(
                "INSERT OR REPLACE INTO candles"
                "(symbol,tf,open_ts,open,high,low,close,volume,source,imported_at)"
                " VALUES(?,?,?,?,?,?,?,?,'test',0)",
                (symbol, tf, 1_600_000_000 + i * sec, str(cl), str(hi),
                 str(lo), str(cl), "100"))
        self.con.commit()
        # Targets come from INTERMEDIATE+ swing facts, so the real dependency
        # runs here rather than being faked — a hand-written swing fact would
        # let the trigger pass a test the pipeline would fail.
        from engine import swings
        swings.run(self.con, symbol, tf, sec)


    @staticmethod
    def _continuation_series():
        """A rise to a PEAK, a fall, then a fresh uptrend that pulls back and
        resumes BELOW that peak.

        The peak is not decoration: `target()` needs an INTERMEDIATE+ swing
        HIGH above the entry, and a monotonic rise never has one — the entry
        is always at the highest price. That is a real property of the
        strategy (a continuation long into blue sky has nothing overhead to
        aim at, and is correctly rejected), so the fixture has to supply the
        overhead level the trade needs.
        """
        xs = []
        for i in range(120):                       # climb to the peak, wavy
            xs.append(100 + i * 2.5 + (6 if i % 7 < 3 else -6))
        peak = xs[-1]
        for i in range(1, 61):                     # give it back
            xs.append(peak - i * 2.4)
        base = xs[-1]
        for i in range(1, 121):                    # fresh uptrend, under peak
            xs.append(base + i * 1.0 + (4 if i % 9 < 4 else -4))
        top = xs[-1]
        for i in range(1, 8):                      # the pullback
            xs.append(top - i * 3.2)
        dip = xs[-1]
        for i in range(1, 14):                     # the resumption
            xs.append(dip + i * 4.0)
        return xs

    def test_a_ribbon_that_never_stacks_produces_nothing(self):
        """Flat, entwined averages describe a market with no trend, and MIXED
        is a real state rather than a failure to classify (ma.stack)."""
        self._load([100.0] * 260)
        out = trend.run(self.con, "TRENDUSDT", "1H", 3600)
        self.assertEqual(out["setups"], 0)

    def test_entries_land_on_the_trend_side_of_the_ribbon(self):
        """THE PROPERTY THE MODULE EXISTS FOR. Every emitted long must have
        closed ABOVE the whole ribbon envelope, every short BELOW it — that is
        the cohort the book was missing."""
        # a long rise, a dip back toward the average, then a resumption
        closes = self._continuation_series()
        self._load(closes)
        trend.run(self.con, "TRENDUSDT", "1H", 3600)
        rows = list(store.get_facts(self.con, "TRENDUSDT", "1H", "setup",
                                    TREND_VERSION))
        self.assertTrue(rows, "no setup fired on a textbook continuation")
        candles = [dict(r) for r in store.get_candles(self.con, "TRENDUSDT", "1H")]
        ribbon = trend._ribbon(candles)
        by_ts = {c["open_ts"]: i for i, c in enumerate(candles)}
        from engine.swings import compute_atr
        atr = compute_atr(candles)
        for r in rows:
            p = json.loads(r["payload"])
            i = by_ts[p["confirmed_bar_ts"]]
            tol = ma.SLOPE_DEADBAND_ATR * atr[i]
            pos = ma.position(Decimal(candles[i]["close"]), ribbon[i], tol)
            want = "ABOVE" if p["direction"] == "LONG" else "BELOW"
            self.assertEqual(pos, want,
                             f"a {p['direction']} confirmed while price was "
                             f"{pos} the ribbon — that is the counter-move "
                             f"entry the existing playbooks already make")

    def test_the_stack_agrees_with_the_direction(self):
        closes = self._continuation_series()
        self._load(closes)
        trend.run(self.con, "TRENDUSDT", "1H", 3600)
        for r in store.get_facts(self.con, "TRENDUSDT", "1H", "setup", TREND_VERSION):
            p = json.loads(r["payload"])
            self.assertEqual(p["ribbon_stack"],
                             "BULL" if p["direction"] == "LONG" else "BEAR")

    def test_the_bracket_is_the_house_bracket(self):
        closes = self._continuation_series()
        self._load(closes)
        trend.run(self.con, "TRENDUSDT", "1H", 3600)
        from engine.setups import ENTRY_MODEL, MIN_RR
        for r in store.get_facts(self.con, "TRENDUSDT", "1H", "setup", TREND_VERSION):
            p = json.loads(r["payload"])
            self.assertEqual(p["entry_model"], ENTRY_MODEL,
                             "a second entry model would make any difference "
                             "in results unattributable to the trigger")
            self.assertGreaterEqual(Decimal(p["rr"]), MIN_RR)
            entry, sl, tp = (Decimal(p["entry"]), Decimal(p["sl"]),
                             Decimal(p["tp"]))
            if p["direction"] == "LONG":
                self.assertLess(sl, entry)
                self.assertGreater(tp, entry)
            else:
                self.assertGreater(sl, entry)
                self.assertLess(tp, entry)

    def test_short_history_is_declined_rather_than_guessed(self):
        """The slowest ribbon member needs its whole window; without it the
        engine would be describing a trend it cannot see."""
        self._load([100 + i for i in range(120)])
        self.assertEqual(trend.run(self.con, "TRENDUSDT", "1H", 3600)["setups"], 0)

    def test_it_is_deterministic(self):
        closes = self._continuation_series()
        self._load(closes)
        a = trend.run(self.con, "TRENDUSDT", "1H", 3600)
        b = trend.run(self.con, "TRENDUSDT", "1H", 3600)
        self.assertGreater(a["setups"], 0)
        self.assertEqual(b["setups"], 0,
                         "a second identical pass emitted new facts — content "
                         "hashing should have made it a no-op")


class RibbonCase(unittest.TestCase):
    def test_the_ribbon_uses_the_engines_own_averages(self):
        """ma.py: 'two implementations of one average is how they come to
        disagree.' A private EMA here would drift from the facts the chart and
        the grader read."""
        src = (Path(__file__).resolve().parent.parent / "engine"
               / "trend.py").read_text(encoding="utf-8")
        self.assertIn("ma.ema", src)
        self.assertIn("ma.sma", src)
        self.assertNotIn("def ema", src, "a private EMA implementation")
        self.assertNotIn("def sma", src, "a private SMA implementation")

    def test_short_windows_yield_no_ribbon_rather_than_a_partial_one(self):
        candles = [{"close": str(100 + i)} for i in range(50)]
        r = trend._ribbon(candles)
        self.assertIsNone(r[0])
        self.assertIsNone(r[-1], "a 200-period average cannot exist at bar 50")


if __name__ == "__main__":
    unittest.main()
