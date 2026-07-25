import unittest

from engine import diagnostics, telemetry


class DiagnosticTests(unittest.TestCase):
    def setup_fact(self, **overrides):
        fact = {
            "setup_id": "BTC-USD|1H|TEST",
            "symbol": "BTC-USD",
            "tf": "1H",
            "strategy": "PULLBACK",
            "direction": "LONG",
            "entry": "100",
            "sl": "100",
            "tp": "120",
            "why": "test fixture",
        }
        fact.update(overrides)
        return fact

    def test_invalid_stop_explains_expected_and_actual(self):
        risk = {
            "decision": "REJECTED",
            "reasons": ["INVALID_STOP_DISTANCE"],
            "equity_at": "10000",
            "intended_risk_usd": "200",
            "risk_usd": "0",
        }
        events = diagnostics.explain_risk(self.setup_fact(), risk)
        self.assertEqual(events[0]["rule_id"], "RISK.003")
        self.assertEqual(events[0]["expected"], "> 0")
        self.assertEqual(events[0]["actual"], 0.0)
        self.assertEqual(events[0]["source"], "app/engine/risk.py")

    def test_uncaptured_portfolio_state_is_explicit(self):
        risk = {
            "decision": "REJECTED",
            "reasons": ["EXPOSURE_LIMIT"],
            "equity_at": "10000",
            "intended_risk_usd": "200",
            "risk_usd": "0",
        }
        event = diagnostics.explain_risk(self.setup_fact(sl="95"), risk)[0]
        self.assertIn("portfolio_state_snapshot", event["missing_evidence"])
        self.assertEqual(event["rule_id"], "RISK.007")

    def test_stop_loss_is_outcome_not_system_defect(self):
        setup = self.setup_fact(sl="95")
        record = telemetry.build_record(
            setup,
            {"decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
             "equity_at": "10000", "intended_risk_usd": "200", "risk_usd": "200"},
            {"event": "FILLED"},
            {"outcome": "SL", "r_multiple": "-1", "r_gross": "-1"},
        )
        lifecycle = record["diagnostics"][-1]
        self.assertEqual(lifecycle["category"], "TRADING_OUTCOME")
        self.assertEqual(lifecycle["severity"], "OUTCOME")

    def test_unknown_reason_is_never_silently_accepted(self):
        risk = {"decision": "REJECTED", "reasons": ["NEW_REASON"],
                "equity_at": "10000", "intended_risk_usd": "200", "risk_usd": "0"}
        event = diagnostics.explain_risk(self.setup_fact(sl="95"), risk)[0]
        self.assertEqual(event["rule_id"], "RISK.UNMAPPED")
        self.assertIn("rule_catalog_entry", event["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
