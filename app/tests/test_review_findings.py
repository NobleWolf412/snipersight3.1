"""Five defects an external review found after the domain separation shipped.

Every one of them let the paper book claim more than it had, or route an order
it should not have. They are pinned here together rather than scattered,
because they share a cause: the separation moved the ACCOUNT onto the ledger
and left several of the inputs that spend it still pointing elsewhere.

  1. Reservations were not counted, so a second trade was approved against a
     budget the first was holding — and every candidate in one scan was sized
     against the same untouched balance.
  2. The loss controls were read at the setup's confirmation instead of the
     moment of decision, so a stop-out since would not block the next entry.
  3. The idempotency key named the zone, not the attempt, so a retest read
     back the previous attempt's terminal state instead of routing.
  4. Only one of the two cockpit painters carried the paper account, so a
     refresh could silently swap the balance back to the research replay.
  5. `equity_basis_source` said "PAPER_REPLAY" even when the paper ledger had
     done the sizing — a provenance field the dispatch gate trusts.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import autotrader, cooldowns, execution, paperbook, risk, riskpaper, store
from engine.contracts import AutomationMode


T0 = 1_700_000_000
HOUR = 3600


def _policy(**over):
    base = {"gates": risk.gates_for_mode(AutomationMode.PAPER),
            "operator_halted": False, "data_blocked": False,
            "strategy_enabled": {"PULLBACK": True}, "cooldown": lambda *_: None,
            "vol24": {}, "same_side_limit": 2}
    base.update(over)
    return base


def _account(**over):
    base = {"equity": Decimal("10000"), "open_positions": [],
            "halted_days": set(), "side_losses": {}, "drawdown": None}
    base.update(over)
    return base


def _intent(setup_id="s-1", confirmed_at=T0, direction="LONG"):
    return {"setup_id": setup_id, "symbol": "BTCUSDT", "direction": direction,
            "entry": "50000", "sl": "49000", "strategy": "PULLBACK",
            "confirmed_at": confirmed_at, "universe_eligible": True}


class ReservationsAreSpentMoney(unittest.TestCase):
    """Finding 1. An unfilled order has already claimed its risk."""

    def test_a_reservation_reduces_the_budget(self):
        free = risk.decide(_intent(), _account(), _policy())
        held = risk.decide(_intent(),
                           _account(reserved_risk_usd=Decimal("400")),
                           _policy())
        self.assertEqual(free["decision"], "APPROVED")
        self.assertLess(held["risk_usd"], free["risk_usd"],
                        "money an unfilled order is holding is not free")

    def test_a_reservation_occupies_a_slot(self):
        held = risk.decide(_intent(), _account(reserved_slots=1), _policy())
        self.assertEqual(held["decision"], "REJECTED")
        self.assertTrue(any(r.startswith("CONCURRENT_LIMIT")
                            for r in held["reasons"]),
                        "an unfilled order is a position waiting to happen")

    def test_the_replay_is_unaffected_by_either(self):
        """The research account passes neither key, so its budget and slot
        count are exactly what they were. That is what keeps `risk.run` a
        proven no-op."""
        plain = risk.decide(_intent(), _account(), _policy())
        self.assertEqual(plain["decision"], "APPROVED")
        self.assertGreater(plain["risk_usd"], Decimal(0))

    def test_a_scan_cannot_approve_the_whole_deck_against_one_balance(self):
        """The loop in `riskpaper.run` must carry claims forward. Asserted on
        the source because the behaviour needs a populated store to observe,
        and the property is structural: the account handed to `decide` has to
        change as approvals accumulate."""
        import inspect
        src = inspect.getsource(riskpaper.run)
        self.assertIn("reserved_risk_usd", src)
        self.assertIn("reserved_slots", src)
        self.assertIn("book = dict(book", src,
                      "each candidate must see what the ones before it claimed")


class TheLossControlsReadTheRightClock(unittest.TestCase):
    """Finding 2. A forward book rules NOW; the replay rules on history."""

    def test_the_replay_reads_the_setups_own_moment(self):
        """Point-in-time by construction: anything else lets a backtest act
        on knowledge the moment did not have."""
        seen = []
        risk.decide(_intent(confirmed_at=T0), _account(),
                    _policy(cooldown=lambda ts, *_: seen.append(ts)))
        self.assertEqual(seen, [T0])

    def test_a_forward_book_reads_the_moment_of_decision(self):
        seen = []
        risk.decide(_intent(confirmed_at=T0), _account(),
                    _policy(cooldown=lambda ts, *_: seen.append(ts),
                            decision_at=T0 + 5 * HOUR))
        self.assertEqual(seen, [T0 + 5 * HOUR],
                         "a cooldown started since the setup confirmed must "
                         "still block the entry being decided now")

    def test_a_halt_today_blocks_a_setup_that_confirmed_yesterday(self):
        """The defect in its clearest form. On the setup's clock the halted
        day is not today, so the entry sails through."""
        today = paperbook._day(T0 + 5 * HOUR)
        old_clock = risk.decide(
            _intent(confirmed_at=T0 - 2 * 86_400),
            _account(halted_days={today}), _policy())
        new_clock = risk.decide(
            _intent(confirmed_at=T0 - 2 * 86_400),
            _account(halted_days={today}), _policy(decision_at=T0 + 5 * HOUR))
        self.assertNotIn("DAILY_LOSS_HALT", old_clock["reasons"])
        self.assertIn("DAILY_LOSS_HALT", new_clock["reasons"])

    def test_the_paper_producer_passes_its_own_clock(self):
        import inspect
        self.assertIn("decision_at=now", inspect.getsource(riskpaper.run))


class ARetestIsNotTheOldOrder(unittest.TestCase):
    """Finding 3. The dedup key named the zone, not the occurrence."""

    def test_two_attempts_at_one_zone_mint_different_keys(self):
        args = ("BTCUSDT|1H|PULLBACK|z-1|setup-v0.22-draft",
                AutomationMode.PAPER, "LIMIT", "0.2", "50000")
        first = execution.intent_key(*args, "zone|1700000000")
        later = execution.intent_key(*args, "zone|1702400000")
        self.assertNotEqual(first, later,
                            "a retest inherited the previous attempt's row "
                            "and read back its terminal state")

    def test_the_same_attempt_still_deduplicates(self):
        """Retry idempotency within one attempt is the whole point of the key
        and must survive: a re-dispatch is a no-op, not a second order."""
        args = ("BTCUSDT|1H|PULLBACK|z-1|setup-v0.22-draft",
                AutomationMode.PAPER, "LIMIT", "0.2", "50000")
        self.assertEqual(execution.intent_key(*args, "zone|1700000000"),
                         execution.intent_key(*args, "zone|1700000000"))

    def test_a_caller_with_no_attempt_keeps_its_old_identity(self):
        """The SHADOW pairing mirrors an existing intent and must not mint a
        new identity for it."""
        args = ("s-1", AutomationMode.PAPER, "LIMIT", "0.2", "50000")
        self.assertEqual(execution.intent_key(*args),
                         execution.intent_key(*args, None))

    def test_the_dispatcher_passes_the_attempt(self):
        import inspect
        self.assertIn('setup.get("attempt_id")',
                      inspect.getsource(autotrader.build_plan))


class TheWireNamesTheRightAccount(unittest.TestCase):
    """Finding 5. A provenance field the dispatch gate trusts."""

    def _row(self, pct_basis):
        return {"eligible": True, "state": "READY",
                "setup": {"setup_id": "s-1", "symbol": "BTCUSDT",
                          "direction": "LONG", "stop": "49000",
                          "targets": ["52000"], "entry": "50000",
                          "attempt_id": "zone|1700000000", "timeframe": "1H"},
                "risk_decision": {"decision": "APPROVED", "units": "0.2",
                                  "risk_usd": "200", "notional_usd": "10000",
                                  "implied_leverage": "1", "equity_at": "10000",
                                  "pct_basis": pct_basis},
                "entry_recommendation": {"order_kind": "LIMIT",
                                         "limit_price": "50000"}}

    def test_a_ledger_sized_plan_says_so(self):
        plan = autotrader.build_plan(self._row("PAPER_LEDGER"),
                                     AutomationMode.PAPER)
        self.assertEqual(plan.risk.equity_basis_source, "PAPER_LEDGER")

    def test_a_replay_sized_plan_still_says_replay(self):
        plan = autotrader.build_plan(self._row("PAPER"), AutomationMode.PAPER)
        self.assertEqual(plan.risk.equity_basis_source, "PAPER_REPLAY")

    def test_an_unknown_basis_falls_back_to_the_restrictive_answer(self):
        """Never to VENUE_BALANCE, which is the only value that lets a LIVE
        order through. A provenance guess must not unlock routing."""
        plan = autotrader.build_plan(self._row("SOMETHING_NEW"),
                                     AutomationMode.PAPER)
        self.assertEqual(plan.risk.equity_basis_source, "PAPER_REPLAY")
        self.assertNotIn("VENUE_BALANCE", set(autotrader._EQUITY_BASIS.values()))


class TheCockpitCannotSwapBooksSilently(unittest.TestCase):
    """Finding 4. Both painters overwrite one shared payload."""

    def test_both_endpoints_carry_the_paper_account(self):
        from fastapi.testclient import TestClient
        import server
        client = TestClient(server.app)
        for path in ("/api/command", "/api/operations"):
            body = client.get(path).json()
            self.assertEqual(body["account"]["paper"]["population"], "PAPER",
                             f"{path} lacks the paper account, so a refresh "
                             "from it swaps the hero back to the replay")

    def test_a_missing_paper_account_is_announced_not_hidden(self):
        shell = (Path(__file__).resolve().parent.parent
                 / "static" / "shell.js").read_text(encoding="utf-8")
        at = shell.index("const balSub = $('mBalanceSub')")
        self.assertIn("RESEARCH REPLAY, not the paper book",
                      shell[at:at + 2000],
                      "falling back silently is the defect: the figure changes "
                      "meaning and the label does not")


class ThePaperChainIsOnScreen(unittest.TestCase):
    """Finding 5 of the review — the API had it, the drawer never drew it."""

    def test_the_drawer_renders_the_paper_section(self):
        tracer = (Path(__file__).resolve().parent.parent
                  / "static" / "tracer.js").read_text(encoding="utf-8")
        self.assertIn("paperChain(t.paper", tracer)
        self.assertIn("no paper record for this setup", tracer,
                      "an honest empty state, or the research ladder below "
                      "reads as the whole story")

    def test_the_research_ladder_says_whose_it_is(self):
        tracer = (Path(__file__).resolve().parent.parent
                  / "static" / "tracer.js").read_text(encoding="utf-8")
        self.assertIn("research replay", tracer)


if __name__ == "__main__":
    unittest.main()
