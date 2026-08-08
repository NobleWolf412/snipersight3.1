from decimal import Decimal

from engine import contracts, risk, settings


def test_first_live_risk_envelope_is_conservative():
    assert risk.RISK_PCT == Decimal("0.0025")
    assert risk.MAX_CONCURRENT == 1
    assert risk.MAX_TOTAL_OPEN_RISK_PCT == Decimal("0.005")
    assert risk.DAILY_LOSS_LIMIT_PCT == Decimal("0.01")
    assert risk.SCALE_RISK_PCT == 0
    assert settings.defaults()["strategy_scale_in"] is False


def test_public_contract_serialises_decimal_as_exact_string():
    reason = contracts.DecisionReason("OK", "within limits")
    decision = contracts.RiskDecision(
        approved=True, decision="APPROVED", risk_usd=Decimal("25.00"),
        quantity=Decimal("0.01250000"), notional_usd=Decimal("812.34"),
        implied_leverage=Decimal("0.08"), reasons=(reason,))
    wire = contracts.to_wire(decision)
    assert wire["risk_usd"] == "25.00"
    assert wire["quantity"] == "0.01250000"
    assert wire["reasons"][0]["code"] == "OK"


def test_closed_vocabularies_match_the_product_contract():
    assert {m.value for m in contracts.AutomationMode} == {
        "OFF", "PAPER", "SHADOW", "TESTNET", "LIVE"}
    assert {s.value for s in contracts.TopDownState} == {
        "ALIGNED", "CONDITIONAL", "CONFLICT", "BLOCKED"}
    assert "READY" in {s.value for s in contracts.OpportunityState}
    assert "POSITION_OPEN" in {s.value for s in contracts.OpportunityState}
