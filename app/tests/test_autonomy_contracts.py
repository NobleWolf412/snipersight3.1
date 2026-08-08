"""The risk envelope and wire contracts, locked.

A `unittest.TestCase` deliberately: the previous version of this file was bare
pytest functions, which `python -m unittest discover -s tests` — the command CI
runs — collected as zero tests. The one assertion locking the envelope's
constants ran only for whoever happened to use pytest.
"""
import unittest
from decimal import Decimal

from engine import contracts, risk, settings
from engine.contracts import AutomationMode as Mode


class RiskEnvelopeLock(unittest.TestCase):
    """The envelope is stated in R and identical in every mode; only the R
    size differs. These constants ARE the safety contract — a change here is
    a deliberate policy decision, never a tuning knob."""

    def test_gates_are_stated_in_r_once(self):
        self.assertEqual(risk.MAX_OPEN_R, Decimal("2"))
        self.assertEqual(risk.DAILY_LOSS_R, Decimal("4"))
        self.assertEqual(risk.MAX_CONCURRENT, 1)
        self.assertEqual(risk.SCALE_ADD_R, Decimal("0"))
        self.assertIs(settings.defaults()["strategy_scale_in"], False)

    def test_r_size_by_mode(self):
        """Paper is rehearsal for live: research runs at 2%, real venues at
        0.25%. OFF maps to paper because the research book keeps running
        when dispatch is off."""
        self.assertEqual(risk.MODE_RISK_PCT[Mode.PAPER], Decimal("0.02"))
        self.assertEqual(risk.MODE_RISK_PCT[Mode.SHADOW], Decimal("0.02"))
        self.assertEqual(risk.MODE_RISK_PCT[Mode.OFF], Decimal("0.02"))
        self.assertEqual(risk.MODE_RISK_PCT[Mode.TESTNET], Decimal("0.0025"))
        self.assertEqual(risk.MODE_RISK_PCT[Mode.LIVE], Decimal("0.0025"))
        self.assertEqual(set(risk.MODE_RISK_PCT), set(Mode),
                         "every mode must have an R size — gates_for_mode "
                         "raises on a missing one, at dispatch time, in prod")

    def test_gates_are_identical_in_r_across_all_modes(self):
        """THE property that makes paper a rehearsal rather than a different
        system: divide any mode's envelope by its own R and every mode gives
        the same numbers."""
        for mode in Mode:
            with self.subTest(mode=mode.value):
                g = risk.gates_for_mode(mode)
                pct = g["risk_pct"]
                self.assertEqual(g["max_total_open_risk_pct"] / pct, Decimal("2"))
                self.assertEqual(g["daily_loss_limit_pct"] / pct, Decimal("4"))
                self.assertEqual(g["max_concurrent"], 1)
                self.assertEqual(g["scale_risk_pct"], Decimal("0") * pct)

    def test_testnet_gates_reproduce_the_v021_live_envelope(self):
        """The v0.21 constants were the intended live policy; restating them
        in R must not have changed what testnet/live actually get."""
        g = risk.gates_for_mode(Mode.TESTNET)
        self.assertEqual(g["risk_pct"], Decimal("0.0025"))
        self.assertEqual(g["max_total_open_risk_pct"], Decimal("0.005"))
        self.assertEqual(g["daily_loss_limit_pct"], Decimal("0.01"))

    def test_dispatch_scale(self):
        """A paper-sized quantity crossing to a real venue shrinks by exactly
        the R ratio — the 8x-oversize first testnet order, prevented."""
        self.assertEqual(risk.dispatch_scale(Mode.TESTNET), Decimal("0.125"))
        self.assertEqual(risk.dispatch_scale(Mode.LIVE), Decimal("0.125"))
        self.assertEqual(risk.dispatch_scale(Mode.PAPER), Decimal("1"))
        self.assertEqual(risk.dispatch_scale(Mode.SHADOW), Decimal("1"))

    def test_an_unknown_mode_raises_rather_than_defaulting(self):
        """A silent fallback here would size real orders under a guess."""
        with self.assertRaises(KeyError):
            risk.gates_for_mode("MAINNET")

    def test_a_zero_r_add_is_rejected_with_its_own_reason(self):
        """The 0R contract is enforced by a stated rejection, not by
        arithmetic producing a zero that books as APPROVED (audit 2026-08-08,
        finding 4)."""
        out = risk.size_order(equity=Decimal(10000), entry=Decimal(100),
                              sl=Decimal(99), direction="LONG",
                              symbol="BTC-USD", is_add=True)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertEqual(out["reasons"], ["SCALE_IN_FORBIDDEN"])
        self.assertEqual(out["risk_usd"], Decimal(0))
        self.assertEqual(out["units"], Decimal(0))


class WireContractLock(unittest.TestCase):
    def test_public_contract_serialises_decimal_as_exact_string(self):
        reason = contracts.DecisionReason("OK", "within limits")
        decision = contracts.RiskDecision(
            approved=True, decision="APPROVED", risk_usd=Decimal("25.00"),
            quantity=Decimal("0.01250000"), notional_usd=Decimal("812.34"),
            implied_leverage=Decimal("0.08"), reasons=(reason,))
        wire = contracts.to_wire(decision)
        self.assertEqual(wire["risk_usd"], "25.00")
        self.assertEqual(wire["quantity"], "0.01250000")
        self.assertEqual(wire["reasons"][0]["code"], "OK")

    def test_closed_vocabularies_match_the_product_contract(self):
        self.assertEqual({m.value for m in contracts.AutomationMode},
                         {"OFF", "PAPER", "SHADOW", "TESTNET", "LIVE"})
        self.assertEqual({s.value for s in contracts.TopDownState},
                         {"ALIGNED", "CONDITIONAL", "CONFLICT", "BLOCKED"})
        self.assertIn("READY", {s.value for s in contracts.OpportunityState})
        self.assertIn("POSITION_OPEN",
                      {s.value for s in contracts.OpportunityState})


if __name__ == "__main__":
    unittest.main()
