"""One attempt, all the way through, on a scratch store.

This is the phase gate the 2026-09-11 review asked for: until a single setup
goes VALIDATED -> APPROVED -> READY -> PAPER_ROUTED -> PAPER_FILLED ->
PAPER_CLOSED with an R-multiple, every claim about the paper book is
speculation. Before the domain and ledger work it could not: the research
replay had already stamped every risk-approved setup CLOSED, so none reached
READY and `autotrader.run` — which dispatches READY only — had never been
handed one. `paper_positions` held zero rows and `execution_events` was empty.

Scratch database, real engines, no production gate bypassed and no safety
guard forced open. It drives the actual dispatch path, so if a future change
breaks the chain anywhere along it, this is the test that says where.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path

from engine import (autotrader, execution, opportunities, paperbook, riskpaper,
                    setups, store)
from engine.contracts import ExecutionDomain


HOUR = 3600


def _hourly(con, symbol, tf, start_ts, bars):
    for i, (o, h, low, c) in enumerate(bars):
        con.execute(
            "INSERT OR REPLACE INTO candles(symbol,tf,open_ts,open,high,low,"
            "close,volume,source,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (symbol, tf, start_ts + i * HOUR, str(o), str(h), str(low),
             str(c), "1000", "fixture", start_ts + i * HOUR))
    con.commit()


class OnePaperAttempt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.con.close)
        execution._ensure(self.con)
        # Aligned to the hour so the candle series and the intent clock agree.
        self.now = (int(time.time()) // HOUR) * HOUR
        # BTC-USD is the declared seed universe: `admitted_at` is True with no
        # universe fact, and `universe.all_tracked_symbols` returns it on an
        # empty store — so the portfolio pass actually scans it. Point-in-time
        # eligibility without inventing a universe snapshot.
        self.symbol, self.tf = "BTC-USD", "1H"
        # A prior bar so the symbol is tracked before anything is dispatched.
        _hourly(self.con, self.symbol, self.tf, self.now - HOUR,
                [(50500, 50600, 50400, 50500)])
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

    def _paper_rows(self):
        return opportunities.list_candidates(
            self.con, domain=ExecutionDomain.PAPER.value,
            include_history=True, now=self.now)

    def _row(self):
        return [r for r in self._paper_rows()
                if r["setup"]["setup_id"] == self.setup_id][0]

    def test_the_whole_chain(self):
        # ---------------------------------------------------------- VALIDATED
        row = self._row()
        self.assertEqual(row["state"], "READY",
                         "a live validated setup starts READY in its own domain")
        self.assertTrue(row["setup"]["attempt_id"],
                        "it is an attempt, and attempts have identity")

        # ----------------------------------------------------------- APPROVED
        verdict = riskpaper.run(self.con, now=self.now)
        self.assertEqual(verdict["APPROVED"] + verdict["REDUCED"], 1, verdict)
        self.assertEqual(verdict["written"], 1)
        row = self._row()
        self.assertEqual(row["risk_decision"]["pct_basis"], "PAPER_LEDGER",
                         "sized against the ledger, not the replay")
        self.assertEqual(row["risk_decision"]["equity_at"],
                         str(paperbook.opening_equity()))
        self.assertTrue(row["eligible"], row["strongest_counterargument"])

        # ------------------------------------------------------- PAPER_ROUTED
        routed = autotrader.run(self.con)
        self.assertEqual(routed["mode"], "PAPER")
        self.assertEqual(len(routed["routed"]), 1, routed)
        self.assertEqual(routed["routed"][0]["state"], "PAPER_ROUTED")
        self.assertEqual(self._row()["state"], "ORDER_WORKING")

        # The dispatcher stored the plan, so the ledger can price the
        # reservation — this is the number `risk.decide` will budget against.
        book = paperbook.snapshot(self.con)
        self.assertGreater(book["reserved_risk_usd"], Decimal(0))
        self.assertEqual(book["committed_risk_usd"], book["reserved_risk_usd"])

        # ------------------------------------------------------- PAPER_FILLED
        # Price trades down through the resting limit, then rallies to target.
        # Placed from the NEXT bar: `monitor_paper` reads candles whose open_ts
        # is at or after the intent's `created_at`, which is wall-clock at
        # dispatch and therefore inside the current hour — a series starting at
        # the current bucket would be filtered out entirely and nothing would
        # fill, which looks exactly like a broken entry model.
        _hourly(self.con, self.symbol, self.tf, self.now + HOUR, [
            (50400, 50450, 49900, 50100),     # touches 50000 — the maker fill
            (50100, 50800, 50050, 50700),
            (50700, 52100, 50600, 52050),     # takes 52000 — the target
        ])
        execution.monitor_paper(self.con)
        position = self.con.execute(
            "SELECT state,entry,r_multiple,outcome FROM paper_positions "
            "WHERE intent_id=?", (routed["routed"][0]["queue"]["intent_id"],)
        ).fetchone()
        self.assertIsNotNone(position, "the paper book must hold the position")

        # ------------------------------------------------------- PAPER_CLOSED
        state, entry, r_multiple, outcome = position
        self.assertEqual(state, "CLOSED", f"outcome={outcome}")
        self.assertEqual(outcome, "TP")
        self.assertIsNotNone(r_multiple, "a closed trade owes an R-multiple")
        self.assertGreater(Decimal(r_multiple), Decimal(0),
                           "a target hit is a winning R after costs")
        self.assertEqual(self._row()["state"], "CLOSED")

        # ------------------------------------------------- the account moved
        after = paperbook.snapshot(self.con)
        self.assertEqual(after["closed_count"], 1)
        self.assertEqual(after["concurrent"], 0)
        self.assertEqual(after["committed_risk_usd"], Decimal(0),
                         "a closed trade releases its budget")
        self.assertGreater(after["equity"], paperbook.opening_equity(),
                           "the paper account is richer than it started")

        # ---------------------------------- and the next decision sees it
        riskpaper.run(self.con, now=self.now + 4 * HOUR)
        latest = riskpaper._latest(self.con).get(self.setup_id)
        self.assertEqual(latest["equity_at"], str(after["equity"]),
                         "the next verdict sizes against the NEW balance — "
                         "this is the loop that did not exist")

    def test_the_trace_shows_the_paper_chain_beside_the_research_one(self):
        """The gate's second half: the whole chain has to be READABLE.

        Rendered as two sections, never one merged timeline — reading the
        replay's account as the book's is the mistake that ran through this
        project for weeks, and interleaving them would invite it back.
        """
        riskpaper.run(self.con, now=self.now)
        routed = autotrader.run(self.con)
        _hourly(self.con, self.symbol, self.tf, self.now + HOUR, [
            (50400, 50450, 49900, 50100),
            (50100, 50800, 50050, 50700),
            (50700, 52100, 50600, 52050),
        ])
        execution.monitor_paper(self.con)

        import server
        trace = server._paper_trace(self.con, self.setup_id)
        self.assertEqual(trace["domain"], "PAPER")
        self.assertEqual(trace["intents"], len(routed["routed"]))
        self.assertEqual(trace["verdict"]["pct_basis"], "PAPER_LEDGER")
        reached = {s["key"]: s["status"] for s in trace["stages"]}
        for key in ("PAPER_RISK", "PAPER_ROUTED", "PAPER_FILLED", "PAPER_CLOSED"):
            self.assertEqual(reached.get(key), "pass",
                             f"{key} should be reached: {reached}")
        self.assertEqual(trace["position"]["outcome"], "TP")
        self.assertIsNotNone(trace["position"]["r_multiple"])

    def test_the_research_replay_never_touches_this_chain(self):
        """The same setup, with the simulator having already closed it. Before
        opportunity-v0.8 this alone stopped every paper trade in the book."""
        from engine import execsim
        store.insert_fact(
            self.con, symbol=self.symbol, tf=self.tf, kind="exec",
            market_time=self.now - HOUR, confirmed_at=self.now - HOUR,
            algo_version=execsim.EXEC_VERSION,
            payload={"setup_id": self.setup_id, "outcome": "SL",
                     "r_multiple": "-1.0"})
        self.con.commit()
        self.assertEqual(self._row()["state"], "READY")
        riskpaper.run(self.con, now=self.now)
        routed = autotrader.run(self.con)
        self.assertEqual(len(routed["routed"]), 1,
                         "a setup the replay has closed still routes to paper")
        # And the replay's story is still on the row, labelled and inert.
        self.assertEqual(self._row()["research_story"]["outcome"], "SL")


if __name__ == "__main__":
    unittest.main()
