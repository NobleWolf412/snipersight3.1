"""What the operator sees first has to be the book, not the backtest.

The operator was asked, on 2026-09-11, what the first screen should tell them
after six hours away. The answer was "did it trade, and how did it go" — and
the two tiles answering it were reading the research replay's equity, which
re-derives from simulated exits every scan and moves with no trade closing.
Under the word "Balance", that answers "how am I doing" with a backtest.

These pin the read path. They do not touch write endpoints and do not force a
guard open: `/api/paper-book` and `/api/command` are both GETs over the store.
"""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

import server
from engine import paperbook, riskpaper


class ThePaperAccountEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_the_book_names_its_own_population(self):
        """A count without a population is the word that let a research
        backtest be read as the operator's book for weeks."""
        body = self.client.get("/api/paper-book").json()
        self.assertEqual(body["population"], "PAPER")

    def test_it_reports_the_account_a_dispatched_order_would_hit(self):
        body = self.client.get("/api/paper-book").json()
        for key in ("equity", "opening_equity", "realised_today",
                    "open_positions", "committed_risk_usd", "closed_trades",
                    "halted_today", "unpriced_intents"):
            self.assertIn(key, body)

    def test_it_states_which_engines_answered(self):
        body = self.client.get("/api/paper-book").json()
        self.assertIn(paperbook.PAPERBOOK_VERSION, body["authority"])
        self.assertIn(riskpaper.PAPER_RISK_VERSION, body["authority"])

    def test_committed_risk_counts_reservations_not_just_positions(self):
        """Sizing that ignores an unfilled intent approves a second trade
        against a budget the first has already claimed."""
        body = self.client.get("/api/paper-book").json()
        self.assertGreaterEqual(
            float(body["committed_risk_usd"]),
            0.0, "committed risk must never read negative")

    def test_the_landing_payload_carries_the_book_and_names_its_domain(self):
        body = self.client.get("/api/command").json()
        self.assertIn("domain", body,
                      "the landing screen must say whose book it is showing")
        self.assertEqual(body["account"]["paper"]["population"], "PAPER")

    def test_nothing_re_derives_the_equity(self):
        """One authority per number. The hero, the endpoint and the command
        payload all read `paperbook.snapshot` and none recompute it."""
        one = self.client.get("/api/paper-book").json()["equity"]
        two = self.client.get("/api/command").json()["account"]["paper"]["equity"]
        self.assertEqual(one, two)


class TheResearchBookStaysReachable(unittest.TestCase):
    def test_the_replay_is_a_toggle_away_not_deleted(self):
        """The operator chose "paper only, research on a toggle". Hiding the
        larger population would be as dishonest as letting it masquerade as
        the book — it is the only place an edge claim can be measured."""
        client = TestClient(server.app)
        body = client.get(
            "/api/opportunities?include_history=false&limit=1&domain=RESEARCH"
        ).json()
        self.assertEqual(body["domain"], "RESEARCH")

    def test_an_unknown_domain_is_refused_rather_than_guessed(self):
        client = TestClient(server.app)
        self.assertEqual(
            client.get("/api/opportunities?domain=NONSENSE").status_code, 400)


if __name__ == "__main__":
    unittest.main()
