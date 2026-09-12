"""The paper account, and the risk authority that sizes against it.

Before this existed, `risk.run()` walked `START_EQUITY` forward through the
RESEARCH replay's simulated exits and stamped that figure onto every decision
the dispatcher read. So a live cycle sized paper orders against a balance that
existed only inside a backtest, and refused them for slots, same-day losses and
cooldowns that had happened only in replay. Measured on the live store
2026-09-11: 23 CONCURRENT_LIMIT blocks and 19 SAME_SIDE_HALT blocks against a
`paper_positions` table holding zero rows.

The rule these pin: *research and paper share logic, never state*. Both books
call `risk.decide`; only the account differs.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import execution, paperbook, risk, riskpaper, store
from engine.contracts import AutomationMode


DAY = 86_400
T0 = 1_700_000_000


def _con(case):
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    con = store.connect(Path(tmp.name) / "t.db")
    case.addCleanup(con.close)
    execution._ensure(con)
    return con


def _intent(con, intent_id, setup_id, risk_usd, state="PAPER_ROUTED",
            symbol="BTCUSDT", updated_at=T0):
    con.execute(
        "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,"
        "symbol,payload,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (intent_id, intent_id, "PAPER", setup_id, symbol,
         json.dumps({"risk": {"risk_usd": str(risk_usd)}}), state,
         updated_at, updated_at))
    con.commit()


def _position(con, intent_id, *, direction="LONG", state="OPEN",
              filled_at=T0, closed_at=None, r=None, symbol="BTCUSDT"):
    con.execute(
        "INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,"
        "entry,stop,target,state,filled_at,closed_at,outcome,exit_price,"
        "r_multiple) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (intent_id, symbol, "1H", direction, "1", "50000", "49000", "52000",
         state, filled_at, closed_at, None if r is None else "SL", None,
         None if r is None else str(r)))
    con.commit()


class TheLedger(unittest.TestCase):
    def test_an_empty_book_is_the_opening_balance_and_nothing_else(self):
        snap = paperbook.snapshot(_con(self))
        self.assertEqual(snap["equity"], paperbook.opening_equity())
        self.assertEqual(snap["open_risk_usd"], Decimal(0))
        self.assertEqual(snap["concurrent"], 0)
        self.assertEqual(snap["closed_count"], 0)

    def test_dollars_come_from_the_stored_plan_not_a_re_derivation(self):
        """`paper_positions` stores `r_multiple` and costs in price units and
        no dollar figure at all. Recomputing the risk from prices here would
        be a second authority for a number the sizing decision already owns."""
        con = _con(self)
        _intent(con, "i-1", "s-1", Decimal("200"))
        _position(con, "i-1", state="CLOSED", closed_at=T0 + 3600, r="-1.0")
        snap = paperbook.snapshot(con)
        self.assertEqual(snap["equity"],
                         paperbook.opening_equity() - Decimal("200"))

    def test_a_pending_intent_reserves_its_risk(self):
        """Sizing that ignores reservations approves a second trade against a
        budget the first has already claimed but not yet filled."""
        con = _con(self)
        _intent(con, "i-1", "s-1", Decimal("200"), state="PENDING")
        snap = paperbook.snapshot(con)
        self.assertEqual(snap["reserved_risk_usd"], Decimal("200"))
        self.assertEqual(snap["committed_risk_usd"], Decimal("200"))
        self.assertEqual(snap["concurrent"], 0)

    def test_a_filled_intents_risk_is_exposure_not_also_a_reservation(self):
        con = _con(self)
        _intent(con, "i-1", "s-1", Decimal("200"), state="PAPER_FILLED")
        _position(con, "i-1")
        snap = paperbook.snapshot(con)
        self.assertEqual(snap["open_risk_usd"], Decimal("200"))
        self.assertEqual(snap["reserved_risk_usd"], Decimal(0))
        self.assertEqual(snap["committed_risk_usd"], Decimal("200"),
                         "counted in both would double the exposure")

    def test_another_modes_position_is_never_pooled_into_this_book(self):
        con = _con(self)
        con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,"
            "setup_id,symbol,payload,state,created_at,updated_at) "
            "VALUES('k','i-9','TESTNET','s-9','BTCUSDT','{}','SUBMITTED',1,1)")
        con.commit()
        _position(con, "i-9")
        self.assertEqual(paperbook.snapshot(con)["concurrent"], 0)

    def test_an_intent_with_no_recorded_risk_is_counted_and_named(self):
        """Loud fallback: it contributes nothing to exposure, so the budget
        silently widens, and a reader that cannot see how many there are
        cannot tell a quiet book from a broken one."""
        con = _con(self)
        con.execute(
            "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,"
            "setup_id,symbol,payload,state,created_at,updated_at) "
            "VALUES('k','i-1','PAPER','s-1','BTCUSDT','{}','PENDING',1,1)")
        con.commit()
        self.assertEqual(paperbook.snapshot(con)["unpriced_intents"], 1)

    def test_losses_are_counted_by_day_and_side_excluding_adds(self):
        """Same rule as the replay's `settle`: a scale-in stopping at its
        parent's entry is one idea being wrong once, not twice."""
        con = _con(self)
        _intent(con, "i-1", "s-1", Decimal("100"))
        _position(con, "i-1", state="CLOSED", closed_at=T0, r="-1.0")
        _intent(con, "i-2", "s-1|ADD", Decimal("100"))
        _position(con, "i-2", state="CLOSED", closed_at=T0, r="-1.0")
        snap = paperbook.snapshot(con)
        self.assertEqual(sum(snap["side_losses"].values()), 1)

    def test_the_daily_loss_limit_halts_that_day_only(self):
        con = _con(self)
        gates = risk.gates_for_mode(AutomationMode.PAPER)
        # One full stop-out per 2% of equity; the daily limit is 4R, so five
        # losing trades on one day clears it with room to spare.
        for i in range(5):
            _intent(con, f"i-{i}", f"s-{i}", Decimal("200"))
            _position(con, f"i-{i}", state="CLOSED", closed_at=T0, r="-1.0")
        _intent(con, "i-late", "s-late", Decimal("200"))
        _position(con, "i-late", state="CLOSED", closed_at=T0 + DAY * 3, r="-1.0")
        snap = paperbook.snapshot(con, gates=gates)
        self.assertEqual(len(snap["halted_days"]), 1)
        self.assertIn(paperbook._day(T0), snap["halted_days"])

    def test_total_drawdown_trips_once_and_reports_the_depth(self):
        con = _con(self)
        for i in range(6):
            _intent(con, f"i-{i}", f"s-{i}", Decimal("400"))
            _position(con, f"i-{i}", state="CLOSED",
                      closed_at=T0 + i * DAY, r="-1.0")
        snap = paperbook.snapshot(con, max_drawdown_pct=20)
        self.assertIsNotNone(snap["drawdown"])
        self.assertGreaterEqual(Decimal(snap["drawdown"]["drawdown_pct"]),
                                Decimal(20))


class OneRulebookTwoBooks(unittest.TestCase):
    def test_both_producers_call_the_same_decision_function(self):
        """The property the whole separation rests on. Two copies of the gate
        ladder is how the two books would start taking different trades for
        reasons nobody chose."""
        import inspect
        self.assertIn("risk.decide", inspect.getsource(riskpaper.run))
        self.assertIn("decide(", inspect.getsource(risk.run))

    def test_the_paper_book_writes_its_own_kind(self):
        """Not a field on `risk`: `_latest_by_setup` selects on (kind,
        version) and the store has no domain column, so the domain has to live
        in the kind."""
        self.assertEqual(riskpaper.PAPER_RISK_KIND, "risk_paper")
        self.assertNotEqual(riskpaper.PAPER_RISK_VERSION, risk.RISK_VERSION)

    def test_the_read_model_asks_each_domain_for_its_own_verdict(self):
        from engine import opportunities
        from engine.contracts import ExecutionDomain
        self.assertEqual(opportunities.risk_source(ExecutionDomain.RESEARCH.value),
                         ("risk", risk.RISK_VERSION))
        self.assertEqual(opportunities.risk_source(ExecutionDomain.PAPER.value),
                         (riskpaper.PAPER_RISK_KIND, riskpaper.PAPER_RISK_VERSION))

    def test_a_decision_sizes_against_the_account_it_was_handed(self):
        """`decide` is pure with respect to the book: hand it a different
        account and the same setup sizes differently. That is the seam."""
        intent = {"setup_id": "s-1", "symbol": "BTCUSDT", "direction": "LONG",
                  "entry": "50000", "sl": "49000", "strategy": "PULLBACK",
                  "confirmed_at": T0, "universe_eligible": True}
        policy = {"gates": risk.gates_for_mode(AutomationMode.PAPER),
                  "operator_halted": False, "data_blocked": False,
                  "strategy_enabled": {"PULLBACK": True},
                  "cooldown": lambda *_: None, "vol24": {},
                  "same_side_limit": 0}
        rich = risk.decide(intent, {"equity": Decimal("10000"),
                                    "open_positions": [], "halted_days": set(),
                                    "side_losses": {}, "drawdown": None}, policy)
        poor = risk.decide(intent, {"equity": Decimal("1000"),
                                    "open_positions": [], "halted_days": set(),
                                    "side_losses": {}, "drawdown": None}, policy)
        self.assertGreater(rich["risk_usd"], poor["risk_usd"])

    def test_a_full_paper_slot_blocks_a_new_paper_entry(self):
        """The defect in its corrected form. This block must now come from a
        position in `paper_positions`, never from one the replay imagined."""
        gates = risk.gates_for_mode(AutomationMode.PAPER)
        intent = {"setup_id": "s-2", "symbol": "BTCUSDT", "direction": "LONG",
                  "entry": "50000", "sl": "49000", "strategy": "PULLBACK",
                  "confirmed_at": T0, "universe_eligible": True}
        policy = {"gates": gates, "operator_halted": False,
                  "data_blocked": False, "strategy_enabled": {"PULLBACK": True},
                  "cooldown": lambda *_: None, "vol24": {},
                  "same_side_limit": 0}
        held = risk.decide(
            intent, {"equity": Decimal("10000"),
                     "open_positions": [{"setup_id": "s-1",
                                         "risk_usd": Decimal("200")}],
                     "halted_days": set(), "side_losses": {}, "drawdown": None},
            policy)
        self.assertEqual(held["decision"], "REJECTED")
        self.assertTrue(any(r.startswith("CONCURRENT_LIMIT")
                            for r in held["reasons"]))


class TheForwardBook(unittest.TestCase):
    def test_an_expired_setup_is_not_ruled_on(self):
        """The replay rules on everything since the baseline because it is
        measuring history. A forward book ruling on a setup whose window shut
        days ago would size a trade nobody can take, against an account that
        has moved since — and consume a slot doing it."""
        con = _con(self)
        store.insert_fact(
            con, symbol="BTCUSDT", tf="1H", kind="setup", market_time=T0,
            confirmed_at=T0, algo_version=riskpaper.SETUP_VERSION,
            payload={"setup_id": "s-1", "state": "VALIDATED",
                     "strategy": "PULLBACK", "direction": "LONG",
                     "entry": "50000", "sl": "49000",
                     "expires_at_ts": T0 + 600})
        con.commit()
        self.assertEqual(
            riskpaper.live_intents(con, T0 - DAY, T0 + 1200), [],
            "a shut entry window is not a live intent")

    def test_an_unreadable_expiry_fails_closed(self):
        con = _con(self)
        store.insert_fact(
            con, symbol="BTCUSDT", tf="1H", kind="setup", market_time=T0,
            confirmed_at=T0, algo_version=riskpaper.SETUP_VERSION,
            payload={"setup_id": "s-1", "state": "VALIDATED",
                     "strategy": "PULLBACK", "direction": "LONG",
                     "entry": "50000", "sl": "49000",
                     "expires_at_ts": "not-a-timestamp"})
        con.commit()
        self.assertEqual(riskpaper.live_intents(con, T0 - DAY, T0), [])

    def test_an_unchanged_verdict_is_not_rewritten_every_cycle(self):
        """A paper verdict's `confirmed_at` is when it was made, so stamping
        wall-clock on an unchanged decision every scan would append thousands
        of identical facts a day. A fact is written when the verdict MOVES."""
        con = _con(self)
        first = riskpaper.run(con, now=T0)
        again = riskpaper.run(con, now=T0 + 600)
        self.assertEqual(again["written"], 0)
        self.assertEqual(first["version"], riskpaper.PAPER_RISK_VERSION)

    def test_the_live_cycle_settles_before_it_sizes(self):
        """Order is behaviour: size first and every decision is made against
        the previous cycle's account."""
        import inspect
        import live
        src = inspect.getsource(live)
        self.assertLess(src.index("execution.monitor_paper(con)"),
                        src.index("riskpaper.run(con)"),
                        "the paper book must settle before it is sized")
        self.assertLess(src.index("riskpaper.run(con)"),
                        src.index("autotrader.run(con"),
                        "it must be sized before the dispatcher reads it")


if __name__ == "__main__":
    unittest.main()
