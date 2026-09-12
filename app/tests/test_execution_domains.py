"""The domain rule, and the attempt identity that makes it safe.

opportunity-v0.8 stopped the research replay deciding whether anything else
could trade. These pin the two properties that fix depends on:

  · a domain's routing state comes from that domain's own records, and the
    absence of a record means THAT DOMAIN HAS NOT ACTED — never a reason to
    read another domain's history;
  · an attempt is a zone touch, not a zone, so a finished attempt cannot
    suppress a later one and an engine bump cannot split one attempt in two.

Measured 2026-09-11, before the fix, on the live baseline: 1035 setups, 40
claimed by the replay's own exits, ZERO reaching READY, all 37 risk-approved
among the 40, and `paper_positions` empty in consequence.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine import execution, opportunities, setups, store
from engine.contracts import (AutomationMode, ExecutionDomain,
                              OpportunityState, domain_for_mode)


CONFIRMED_AT = 1_700_000_000
CONFIRM_BAR = 1_699_999_000


def _con(tmp: tempfile.TemporaryDirectory):
    return store.connect(Path(tmp.name) / "t.db")


def _ready_setup(con, setup_id="BTCUSDT|1H|PULLBACK|z-1|" + setups.SETUP_VERSION,
                 confirmed_at=CONFIRMED_AT, confirm_bar=CONFIRM_BAR):
    store.insert_fact(
        con, symbol="BTCUSDT", tf="1H", kind="setup",
        market_time=confirmed_at - 3600, confirmed_at=confirmed_at,
        algo_version=setups.SETUP_VERSION,
        payload={"setup_id": setup_id, "strategy": "PULLBACK",
                 "direction": "LONG", "entry": "50000", "sl": "49000",
                 "tp": "52000", "rr": "2", "state": "VALIDATED",
                 "confirmed_bar_ts": confirm_bar,
                 "expires_at_ts": confirmed_at + 86_400})
    con.commit()
    return setup_id


def _outbox(con, setup_id, mode, state, updated_at, intent_id="i-1"):
    from engine import positions
    execution._ensure(con)
    # The private read joins managed_positions; without the table the join
    # raises "no such table" and the domain correctly reports no records.
    positions._ensure(con)
    con.execute(
        "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,"
        "symbol,payload,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (intent_id, intent_id, mode, setup_id, "BTCUSDT", "{}", state,
         updated_at, updated_at))
    con.commit()


class TheDomainRule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.con = _con(self.tmp)
        self.addCleanup(self.con.close)
        self.sid = _ready_setup(self.con)

    def _states(self, domain, **kw):
        rows = opportunities.list_candidates(
            self.con, domain=domain, now=CONFIRMED_AT + 60, **kw)
        return {r["setup"]["setup_id"]: r["state"] for r in rows}

    def test_a_setup_the_replay_has_closed_is_still_ready_for_paper(self):
        """The whole defect, in one assertion.

        The simulator reaches every setup first (execsim.run runs before
        risk.run in the live cycle) and settles it. Before v0.8 that stamped
        the candidate CLOSED for every caller including the dispatcher, so no
        risk-approved setup could ever be offered to the paper broker.
        """
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind="exec",
            market_time=CONFIRMED_AT, confirmed_at=CONFIRMED_AT + 10,
            algo_version=opportunities.execsim.EXEC_VERSION,
            payload={"setup_id": self.sid, "outcome": "SL",
                     "r_multiple": "-1.0"})
        self.con.commit()
        self.assertEqual(self._states(ExecutionDomain.RESEARCH.value)[self.sid],
                         "CLOSED")
        self.assertEqual(self._states(ExecutionDomain.PAPER.value)[self.sid],
                         "READY")

    def test_the_replay_travels_as_display_and_never_as_state(self):
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind="exec",
            market_time=CONFIRMED_AT, confirmed_at=CONFIRMED_AT + 10,
            algo_version=opportunities.execsim.EXEC_VERSION,
            payload={"setup_id": self.sid, "outcome": "TP", "r_multiple": "2.0"})
        self.con.commit()
        row = [r for r in opportunities.list_candidates(
            self.con, domain=ExecutionDomain.PAPER.value, now=CONFIRMED_AT + 60)
            if r["setup"]["setup_id"] == self.sid][0]
        self.assertEqual(row["state"], "READY")
        self.assertTrue(row["eligible"])
        self.assertEqual(row["domain"], "PAPER")
        self.assertEqual(row["research_story"]["outcome"], "TP")
        self.assertEqual(row["research_story"]["r_multiple"], "2.0")

    def test_one_domain_cannot_see_another_domains_orders(self):
        """Structural, not conventional: the query cannot return the rows."""
        _outbox(self.con, self.sid, "TESTNET", "SUBMITTED", CONFIRMED_AT + 10)
        self.assertEqual(self._states(ExecutionDomain.PAPER.value)[self.sid],
                         "READY")
        self.assertEqual(self._states(ExecutionDomain.TESTNET.value)[self.sid],
                         "ORDER_WORKING")

    def test_paper_reads_its_own_outbox(self):
        _outbox(self.con, self.sid, "PAPER", "PAPER_FILLED", CONFIRMED_AT + 10)
        self.assertEqual(self._states(ExecutionDomain.PAPER.value)[self.sid],
                         "POSITION_OPEN")

    def test_a_finished_attempt_cannot_suppress_a_later_one(self):
        """A terminal record older than the setup's own confirmation belongs
        to an earlier touch of the same zone (audit 2026-08-08)."""
        _outbox(self.con, self.sid, "PAPER", "PAPER_CLOSED", CONFIRMED_AT - 5000)
        self.assertEqual(self._states(ExecutionDomain.PAPER.value)[self.sid],
                         "READY")

    def test_a_live_position_overrides_regardless_of_timestamps(self):
        """Present tense beats bookkeeping: the exposure exists right now."""
        _outbox(self.con, self.sid, "PAPER", "PAPER_FILLED", CONFIRMED_AT - 5000)
        self.assertEqual(self._states(ExecutionDomain.PAPER.value)[self.sid],
                         "POSITION_OPEN")

    def test_real_exposure_is_display_only_and_never_grants_ready(self):
        _outbox(self.con, self.sid, "TESTNET", "SUBMITTED", CONFIRMED_AT + 10)
        shown = self._states(ExecutionDomain.PAPER.value, show_real_exposure=True)
        self.assertEqual(shown[self.sid], "ORDER_WORKING")
        row = [r for r in opportunities.list_candidates(
            self.con, domain=ExecutionDomain.PAPER.value,
            now=CONFIRMED_AT + 60, show_real_exposure=True)
            if r["setup"]["setup_id"] == self.sid][0]
        self.assertFalse(row["eligible"])

    def test_the_dispatch_path_never_sees_real_exposure(self):
        """`show_real_exposure` defaults off so a forgotten argument cannot
        route one domain's order against another domain's position."""
        import inspect
        from engine import autotrader
        sig = inspect.signature(opportunities.list_candidates)
        self.assertIs(sig.parameters["show_real_exposure"].default, False)
        src = inspect.getsource(autotrader)
        self.assertIn("list_candidates", src, "guard reads the wrong module")
        self.assertNotIn("show_real_exposure", src)


class ReadFailuresAreLoud(unittest.TestCase):
    def test_a_broken_read_raises_instead_of_reporting_an_empty_book(self):
        """The loud-fallback rule, in the one place breaking it costs an order.

        A domain with no records reads as "has not acted", and the dispatcher
        is allowed to route into it. A swallowed read error produces the same
        empty dict and hands it a green light off a database hiccup.
        """
        class Exploding:
            def execute(self, *_a, **_k):
                raise sqlite3.OperationalError("database disk image is malformed")

        with self.assertRaises(sqlite3.OperationalError):
            opportunities._outbox_records(Exploding(), "PAPER")

    def test_a_table_that_was_never_created_is_simply_empty(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = _con(tmp)
        self.addCleanup(con.close)
        con.execute("DROP TABLE IF EXISTS execution_outbox")
        con.commit()
        self.assertEqual(opportunities._outbox_records(con, "PAPER"), {})


class AttemptIdentity(unittest.TestCase):
    """Built to MERGE, because over-splitting is the failure that happened."""

    def test_an_engine_bump_does_not_split_one_attempt(self):
        """The 2026-08-06 regression: one UNIUSDT 4H REVERSAL touch minted
        five ids across setup-v0.13 to v0.17 with one confirmed_at and
        byte-identical prices, and a hand-closed position came back as live
        exposure under the new tag."""
        payload = {"confirmed_bar_ts": 1_785_470_400}
        ids = {opportunities.attempt_id_for(
            f"UNIUSDT|4H|REVERSAL|UNIUSDT|4H|SUPPLY|1785200000|setup-v0.{n}-draft",
            payload) for n in (13, 14, 15, 16, 17)}
        self.assertEqual(len(ids), 1, f"one zone touch minted {len(ids)} ids")

    def test_a_later_retest_of_the_same_zone_is_a_different_attempt(self):
        zone = "BTCUSDT|1H|PULLBACK|BTCUSDT|1H|DEMAND|1700000000|" + setups.SETUP_VERSION
        first = opportunities.attempt_id_for(zone, {"confirmed_bar_ts": 1_700_003_600})
        later = opportunities.attempt_id_for(zone, {"confirmed_bar_ts": 1_702_400_000})
        self.assertNotEqual(first, later)

    def test_a_setup_that_has_not_confirmed_has_no_attempt(self):
        """Not a missing value to paper over — an unconfirmed setup is not yet
        an attempt, and the store agrees: `confirmed_bar_ts` is present on
        every VALIDATED and EXPIRED fact and absent from every FORMING,
        CONFIRMING and CANCELLED one (measured 2026-09-11)."""
        self.assertIsNone(opportunities.attempt_id_for("BTCUSDT|1H|PULLBACK|z|v",
                                                       {"state": "FORMING"}))

    def test_every_candidate_carries_its_attempt(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = _con(tmp)
        self.addCleanup(con.close)
        sid = _ready_setup(con)
        row = opportunities.list_candidates(
            con, domain=ExecutionDomain.PAPER.value, now=CONFIRMED_AT + 60)[0]
        self.assertEqual(row["setup"]["setup_id"], sid)
        self.assertTrue(row["setup"]["attempt_id"].endswith(f"|{CONFIRM_BAR}"))
        self.assertNotIn(setups.SETUP_VERSION, row["setup"]["attempt_id"])


class ModeToDomain(unittest.TestCase):
    def test_shadow_and_off_write_the_paper_book(self):
        for mode in (AutomationMode.OFF, AutomationMode.PAPER,
                     AutomationMode.SHADOW):
            self.assertEqual(domain_for_mode(mode), ExecutionDomain.PAPER)

    def test_private_modes_own_their_own_records(self):
        self.assertEqual(domain_for_mode(AutomationMode.TESTNET),
                         ExecutionDomain.TESTNET)
        self.assertEqual(domain_for_mode(AutomationMode.LIVE),
                         ExecutionDomain.LIVE)

    def test_no_mode_ever_resolves_to_research(self):
        """The replay is not a dispatcher and no dispatcher may read its
        records as its own."""
        for mode in AutomationMode:
            self.assertNotEqual(domain_for_mode(mode), ExecutionDomain.RESEARCH)

    def test_the_autotrader_asks_for_the_active_modes_domain(self):
        import inspect
        from engine import autotrader
        src = inspect.getsource(autotrader.run)
        self.assertIn("domain_for_mode(active.mode)", src,
                      "the dispatcher must read the book it is dispatching "
                      "into, not the default read model")


class LifecycleOwnership(unittest.TestCase):
    def test_absence_of_a_record_is_not_a_terminal_state(self):
        self.assertEqual(opportunities.lifecycle("VALIDATED", None, None),
                         OpportunityState.READY)

    def test_risk_rejection_outranks_a_domain_record(self):
        """A domain that recorded a fill against a REJECTED decision is
        describing a bug, not a position."""
        self.assertEqual(
            opportunities.lifecycle(
                "VALIDATED", {"decision": "REJECTED"},
                OpportunityState.POSITION_OPEN),
            OpportunityState.BLOCKED)

    def test_lifecycle_takes_no_research_argument_at_all(self):
        """Structural guard on the rule. `lifecycle()` used to accept the
        replay's `order` and `exec` facts; reintroducing either parameter is
        how a later edit would quietly restore cross-domain fallback."""
        import inspect
        names = set(inspect.signature(opportunities.lifecycle).parameters)
        self.assertEqual(names, {"setup_state", "risk_fact", "record"})


if __name__ == "__main__":
    unittest.main()
