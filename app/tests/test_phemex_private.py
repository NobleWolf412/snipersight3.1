import hashlib
import hmac
from decimal import Decimal
from unittest import mock

import pytest

from engine import phemex_private
from engine.contracts import (AutomationMode, DecisionReason, ExecutionPlan,
                              OrderIntent, OrderKind, RiskDecision)


PRODUCT = [{"symbol": "BTCUSDT", "tick_size": "0.1", "qty_step": "0.001",
            "min_notional": "1", "max_order_qty": "1000"}]


def plan(kind=OrderKind.LIMIT):
    intent = OrderIntent(
        "intent-1", "setup-1", AutomationMode.TESTNET, "BTCUSDT", "LONG",
        kind, Decimal("0.010"), Decimal("50000.1") if kind == OrderKind.LIMIT else None,
        Decimal("49000.1"), (Decimal("52000.1"),), False, 1, "pullback-v1",
        "a" * 64)
    risk = RiskDecision(True, "APPROVED", Decimal("10"), Decimal("0.010"),
                        Decimal("500.001"), Decimal("0.05"),
                        (DecisionReason("OK", "within limits"),))
    return ExecutionPlan(intent, risk, "phemex-perp", "ISOLATED", "ONE_WAY")


def test_signature_matches_official_formula():
    expected = hmac.new(b"secret", b"/g-orderssymbol=BTCUSDT123{}",
                        hashlib.sha256).hexdigest()
    assert phemex_private.signature(
        "secret", "/g-orders", "symbol=BTCUSDT", 123, "{}") == expected


def test_mainnet_client_is_build_locked_and_withdrawal_keys_are_refused():
    with pytest.raises(phemex_private.PhemexError, match="build-locked"):
        phemex_private.PhemexBroker("k", "s", environment="mainnet", products=PRODUCT)
    with pytest.raises(ValueError, match="withdrawal"):
        phemex_private.PhemexBroker(
            "k", "s", withdrawal_enabled=True, products=PRODUCT)


def test_instrument_metadata_is_loaded_from_the_selected_environment():
    seen = []

    def transport(method, url, headers, body):
        seen.append(url)
        return {"data": {"perpProductsV2": [{
            "symbol": "BTCUSDT", "status": "Listed",
            "settleCurrency": "USDT", "quoteCurrency": "USDT",
            "tickSize": "0.1", "qtyStepSize": "0.001",
            "minOrderValueRv": "1", "maxOrderQtyRq": "100"}]}}

    broker = phemex_private.PhemexBroker(
        "key", "secret", environment="testnet", transport=transport)
    products = broker.refresh_products()
    assert products[0]["qty_step"] == "0.001"
    assert seen == [phemex_private.TESTNET_API + "/public/products"]


def test_testnet_order_uses_real_value_fields_one_way_and_attached_stop_only():
    calls = []
    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        return {"code": 0, "data": {"orderID": "o-1", "clOrdID": "ss-" + "a" * 37,
                "symbol": "BTCUSDT", "orderType": "Limit", "ordStatus": "New",
                "orderQtyRq": "0.010", "cumQtyRq": "0", "priceRp": "50000.1"}}
    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=transport, products=PRODUCT)
    order = broker.submit(plan())
    assert calls[0][0] == "PUT" and "switch-pos-mode-sync" in calls[0][1]
    assert calls[1][0] == "PUT" and "/g-positions/leverage?" in calls[1][1]
    submit_call = next(call for call in calls if call[0] == "POST")
    body = submit_call[3].decode()
    assert submit_call[1].startswith(phemex_private.TESTNET_API + "/g-orders")
    assert '"posSide":"Merged"' in body
    assert '"stopLossRp":"49000.1"' in body
    assert '"takeProfitRp"' not in body
    assert order.client_order_id.startswith("ss-")


def test_adapter_refuses_to_round_invalid_tick_or_lot_silently():
    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=lambda *args: {}, products=PRODUCT)
    bad = plan()
    object.__setattr__(bad.intent, "entry", Decimal("50000.15"))
    with pytest.raises(phemex_private.PhemexError, match="tick"):
        broker.validate_plan(bad)


def test_replace_preserves_client_identity_and_validates_metadata():
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url))
        return {"code": 0, "data": {"orderID": "o-1", "clOrdID": "c-1",
                "symbol": "BTCUSDT", "ordStatus": "New",
                "orderQtyRq": "0.020", "priceRp": "50001.0"}}

    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=transport, products=PRODUCT)
    amended = broker.replace("BTCUSDT", "c-1", quantity=Decimal("0.020"),
                             price=Decimal("50001.0"))
    assert amended.client_order_id == "c-1"
    assert calls[0][0] == "PUT"
    assert "/g-orders/replace?" in calls[0][1]


def test_attached_protection_rejects_opposite_direction():
    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=lambda *args: {}, products=PRODUCT)
    broker.positions = lambda symbol=None, **kwargs: [{
        "symbol": "BTCUSDT", "sizeRq": "0.010", "side": "Sell",
        "stopLossRp": "49000.1"}]
    assert broker.confirm_attached_protection(
        symbol="BTCUSDT", direction="LONG", quantity=Decimal("0.010"),
        stop=Decimal("49000.1"), client_order_id="stop-1") is None


def test_order_status_recovers_filled_order_by_client_id_history():
    def transport(method, url, headers, body):
        if "activeList" in url:
            return {"code": 0, "data": {"rows": []}}
        return {"code": 0, "data": {"rows": [{
            "orderId": "venue-1", "clOrdId": "ss-restart-safe",
            "symbol": "BTCUSDT", "ordType": "Limit", "ordStatus": "Filled",
            "orderQtyRq": "0.010", "cumQtyRq": "0.010",
            "priceRp": "50000.1"}]}}
    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=transport, products=PRODUCT)
    recovered = broker.order_status("BTCUSDT", "ss-restart-safe")
    assert recovered.broker_order_id == "venue-1"
    assert recovered.client_order_id == "ss-restart-safe"


def test_account_wide_open_orders_enumerates_every_listed_product():
    seen = []
    def transport(method, url, headers, body):
        seen.append(url)
        symbol = "ETHUSDT" if "ETHUSDT" in url else "BTCUSDT"
        rows = ([{"orderId": "open-1", "clOrdId": "foreign-open",
                  "symbol": symbol, "ordType": 2, "ordStatus": 5,
                  "orderQtyRq": "1", "cumQtyRq": "0", "priceRp": "3000"}]
                if symbol == "ETHUSDT" else [])
        return {"code": 0, "data": {"rows": rows}}
    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=transport,
        products=PRODUCT + [{**PRODUCT[0], "symbol": "ETHUSDT"}])
    orders = broker.open_orders()
    assert [order.client_order_id for order in orders] == ["foreign-open"]
    assert len(seen) == 2
    assert all("/g-orders/activeList?symbol=" in url for url in seen)


def test_execution_history_paginates_with_explicit_bounds_and_exact_fees():
    seen = []
    rows = [{
        "execID": f"exec-{i}", "orderID": "exit-1", "clOrdID": "intent-tp1",
        "symbol": "BTCUSDT", "currency": "USDT", "side": "Sell",
        "execQtyRq": "0.001", "execPriceRp": "52000.1",
        "execFeeRv": "0.0052", "transactTimeNs": 2_000_000_000 + i,
    } for i in range(201)]

    def transport(method, url, headers, body):
        seen.append(url)
        page = rows[200:] if "offset=200" in url else rows[:200]
        return {"code": 0, "data": {"rows": page}}

    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=transport, products=PRODUCT)
    executions = broker.executions("BTCUSDT", start_at=1)
    assert len(executions) == 201
    assert executions[0].fee == Decimal("0.0052")
    assert executions[0].client_order_id == "intent-tp1"
    assert all("start=1000" in url and "limit=200" in url for url in seen)
    assert len(seen) == 2


def test_target_is_deterministic_reduce_only_limit():
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, body))
        return {"code": 0, "data": {
            "orderID": "target-1", "clOrdID": "intent-1-tp1",
            "symbol": "BTCUSDT", "ordStatus": "New", "ordType": "Limit",
            "orderQtyRq": "0.010", "cumQtyRq": "0", "priceRp": "52000.1",
            "reduceOnly": True}}

    broker = phemex_private.PhemexBroker(
        "key", "secret", transport=transport, products=PRODUCT)
    target = broker.submit_target(
        symbol="BTCUSDT", direction="LONG", quantity=Decimal("0.010"),
        target=Decimal("52000.1"), client_order_id="intent-1-tp1")
    payload = calls[0][2].decode()
    assert target.client_order_id == "intent-1-tp1"
    assert '"reduceOnly":true' in payload
    assert '"side":"Sell"' in payload
    assert '"priceRp":"52000.1"' in payload
