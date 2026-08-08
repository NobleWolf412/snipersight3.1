from decimal import Decimal

import pytest

from engine import autotrader
from engine.contracts import AutomationMode, OrderKind


def ready(**updates):
    row = {
        "state": "READY", "eligible": True,
        "setup": {"setup_id": "s1", "symbol": "BTCUSDT",
                  "venue": "phemex-perp", "direction": "LONG",
                  "entry": "50000", "stop": "49000", "targets": ["52000"],
                  "version": "setup-v1"},
        "entry_recommendation": {"order_kind": "LIMIT", "limit_price": "50000"},
        "risk_decision": {"decision": "APPROVED", "risk_usd": "25",
                          "units": "0.025", "notional_usd": "1250",
                          "implied_leverage": "0.125", "reasons": ["WITHIN_LIMITS"]},
    }
    row.update(updates)
    return row


def test_ready_candidate_becomes_decimal_isolated_one_way_plan():
    plan = autotrader.build_plan(ready(), AutomationMode.SHADOW)
    assert plan.intent.order_kind == OrderKind.LIMIT
    assert plan.intent.quantity == Decimal("0.025")
    assert plan.margin_mode == "ISOLATED"
    assert plan.position_mode == "ONE_WAY"
    assert plan.protection_deadline_seconds == 5


def test_no_trade_or_risk_rejection_never_becomes_intent():
    with pytest.raises(ValueError, match="eligible READY"):
        autotrader.build_plan(ready(state="BLOCKED", eligible=False),
                              AutomationMode.PAPER)
    row = ready()
    row["risk_decision"]["decision"] = "REJECTED"
    with pytest.raises(ValueError, match="risk authority"):
        autotrader.build_plan(row, AutomationMode.PAPER)
