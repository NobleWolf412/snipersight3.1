"""Where the paper book and the research replay are allowed to differ.

The paper book is a rehearsal for live trading. A rehearsal that is KINDER
than the backtest it rehearses is worse than no rehearsal, because every
number it produces overstates what the live system would have done.

These pin the reconciliation. Each divergence below is either eliminated, or
named here with the reason it is deliberate — a difference nobody has written
down is a difference nobody can defend.

ELIMINATED (execution-core-v0.8)
  · Gap-through stops. The paper monitor closed at the stop price even when
    the bar opened beyond it; research pays that bar's open
    (`execsim.stop_gap_fill`, exec-v0.26). Paper flattered exactly the losses
    that hurt most. Both now call `execsim.walk_exit`.
  · Ambiguous bars. A bar reaching stop AND target settles as the stop in
    both engines, but only the shared walk recorded that it happened. Paper
    closes now carry `ambiguous_bar`.

DELIBERATE, and why
  · WHICH SETUPS. Research rules on every setup since the baseline because it
    is measuring a strategy. The paper book rules only on setups still live,
    because it is running one. A forward book sizing a shut entry window
    against today's account would produce a number with no meaning.
  · WHOSE ACCOUNT. Research walks a simulated balance from START_EQUITY; paper
    reads `paperbook`. That is the whole point of the separation.
  · ENTRY CLOCK. Research fills from the setup's own bar index; paper fills
    from candles at or after the intent's `created_at`, which is wall-clock at
    dispatch. Paper therefore cannot fill on a bar that had already closed
    when the order was placed — correct, and the reason its fills can lag the
    replay's by a bar.

STILL OPEN, named rather than hidden
  · `manual.py` carries a THIRD exit walk (`_exit_walk`). It is the operator's
    hand-armed book, not the autonomous one, and reconciling it is its own
    change with its own version bump.
  · Partial fills. Neither engine models them; both fill whole or not at all.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path

from engine import autotrader, execsim, execution, riskpaper, setups, store


HOUR = 3600


def _bars(rows):
    return [{"open": str(o), "high": str(h), "low": str(low), "close": str(c)}
            for o, h, low, c in rows]


class TheSharedExitWalk(unittest.TestCase):
    def test_a_gapped_through_stop_pays_the_bars_open_not_the_stop(self):
        """The divergence that mattered. A long stopped at 49000 on a bar that
        OPENED at 47000 never got 49000 — it got 47000, and a book that
        records 49000 is describing a fill nobody received."""
        candles = _bars([
            (50000, 50100, 49900, 50000),        # fill bar
            (47000, 47500, 46800, 47100),        # gaps through the stop
        ])
        outcome, price, index, _ambiguous = execsim.walk_exit(
            candles, 0, Decimal("49000"), Decimal("52000"), True)
        self.assertEqual(outcome, "SL")
        self.assertEqual(price, Decimal("47000"),
                         "the gap is paid at the open, not the stop")
        self.assertEqual(index, 1)

    def test_the_fill_bars_own_open_is_not_treated_as_a_gap(self):
        """Its open precedes the entry, so it is not a post-entry gap."""
        candles = _bars([(47000, 50100, 48900, 50000)])
        outcome, price, _i, _a = execsim.walk_exit(
            candles, 0, Decimal("49000"), Decimal("52000"), True)
        self.assertEqual(outcome, "SL")
        self.assertEqual(price, Decimal("49000"))

    def test_a_bar_reaching_both_levels_settles_as_the_stop_and_says_so(self):
        """Sub-bar sequencing needs data we do not have, and flattering an
        ambiguous bar is how a backtest lies."""
        candles = _bars([
            (50000, 50100, 49900, 50000),
            (50000, 52500, 48500, 50000),        # reaches stop AND target
        ])
        outcome, _price, _i, ambiguous = execsim.walk_exit(
            candles, 0, Decimal("49000"), Decimal("52000"), True)
        self.assertEqual(outcome, "SL")
        self.assertTrue(ambiguous, "the ambiguity has to be recorded")


class ThePaperBookUsesIt(unittest.TestCase):
    """Not "produces the same answer" — literally the same function.

    A parity test over sample bars proves agreement on the cases it samples.
    One implementation proves it on the cases nobody thought of, which is
    where this drifted the first time.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.con.close)
        execution._ensure(self.con)
        self.now = (int(time.time()) // HOUR) * HOUR
        self.symbol, self.tf = "BTC-USD", "1H"
        self._candle(self.now - HOUR, 50500, 50600, 50400, 50500)
        self.setup_id = f"{self.symbol}|{self.tf}|PULLBACK|z-1|{setups.SETUP_VERSION}"
        store.insert_fact(
            self.con, symbol=self.symbol, tf=self.tf, kind="setup",
            market_time=self.now - HOUR, confirmed_at=self.now - HOUR,
            algo_version=setups.SETUP_VERSION,
            payload={"setup_id": self.setup_id, "state": "VALIDATED",
                     "strategy": "PULLBACK", "direction": "LONG",
                     "entry": "50000", "sl": "49000", "tp": "52000",
                     "rr": "2", "confirmed_bar_ts": self.now - HOUR,
                     "maker_limit": "50000", "maker_wait_bars": 6,
                     "expires_at_ts": self.now + 12 * HOUR})
        self.con.commit()

    def _candle(self, ts, o, h, low, c):
        self.con.execute(
            "INSERT OR REPLACE INTO candles(symbol,tf,open_ts,open,high,low,"
            "close,volume,source,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (self.symbol, self.tf, ts, str(o), str(h), str(low), str(c),
             "1000", "fixture", ts))
        self.con.commit()

    def test_a_paper_stop_that_gapped_is_recorded_at_the_open(self):
        riskpaper.run(self.con, now=self.now)
        routed = autotrader.run(self.con)
        intent_id = routed["routed"][0]["queue"]["intent_id"]
        self._candle(self.now + HOUR, 50400, 50450, 49900, 50100)   # fills
        self._candle(self.now + 2 * HOUR, 47000, 47500, 46800, 47100)  # gaps
        execution.monitor_paper(self.con)
        outcome, exit_price, r_multiple = self.con.execute(
            "SELECT outcome,exit_price,r_multiple FROM paper_positions "
            "WHERE intent_id=?", (intent_id,)).fetchone()
        self.assertEqual(outcome, "SL")
        # `exit_price` is the SETTLED price — the walk's exit plus slippage and
        # fees — so the assertion is that it landed near the bar's open rather
        # than near the stop, not that it equals either exactly.
        self.assertLess(Decimal(exit_price), Decimal("48000"),
                        "a gapped stop must not be recorded at the stop price")
        self.assertLess(Decimal(r_multiple), Decimal("-1"),
                        "a gap through the stop loses MORE than one R — which "
                        "is exactly what the old private copy could not say")

    def test_the_paper_close_records_whether_the_bar_was_ambiguous(self):
        riskpaper.run(self.con, now=self.now)
        routed = autotrader.run(self.con)
        intent_id = routed["routed"][0]["queue"]["intent_id"]
        self._candle(self.now + HOUR, 50400, 50450, 49900, 50100)
        self._candle(self.now + 2 * HOUR, 50000, 52500, 48500, 50000)
        execution.monitor_paper(self.con)
        row = self.con.execute(
            "SELECT payload FROM execution_events WHERE intent_id=? "
            "AND event='PAPER_CLOSED'", (intent_id,)).fetchone()
        import json
        payload = json.loads(row[0])
        self.assertEqual(payload["outcome"], "SL")
        self.assertTrue(payload["ambiguous_bar"],
                        "a bar that reached both levels must say so")

    def test_paper_does_not_re_implement_the_walk(self):
        """The structural guard. The copy is how it drifted last time."""
        import inspect
        src = inspect.getsource(execution.monitor_paper)
        self.assertIn("execsim.walk_exit", src)
        self.assertNotIn("stop_hit", src,
                         "a private stop comparison is a second exit model, "
                         "and a second exit model is how this drifted before")


if __name__ == "__main__":
    unittest.main()
