from unittest import mock

import pytest

from engine import broker_factory, phemex_private
from engine.contracts import AutomationMode


PRODUCTS = [{"symbol": "BTCUSDT", "tick_size": "0.1",
             "qty_step": "0.001", "min_notional": "1",
             "max_order_qty": "100"}]


def test_non_private_modes_never_read_credentials():
    with mock.patch("engine.broker_factory.credentials.read_secret") as read:
        with pytest.raises(broker_factory.BrokerConfigurationError,
                           match="no private broker"):
            broker_factory.phemex_for_mode(AutomationMode.SHADOW,
                                           products=PRODUCTS)
    read.assert_not_called()


def test_testnet_reads_only_testnet_namespace():
    seen = []

    def secret(target, field):
        seen.append((target, field))
        return "value"

    with mock.patch("engine.broker_factory.credentials.read_secret",
                    side_effect=secret):
        broker = broker_factory.phemex_for_mode(
            AutomationMode.TESTNET, products=PRODUCTS,
            transport=lambda *args: {"code": 0})
    assert broker.environment == "testnet"
    assert {target for target, _ in seen} == {"phemex-testnet"}


def test_mainnet_factory_stays_build_locked_before_reading_secrets():
    with mock.patch("engine.broker_factory.credentials.read_secret",
                    return_value="value"):
        with pytest.raises(broker_factory.BrokerConfigurationError,
                           match="build-locked"):
            broker_factory.phemex_for_mode(AutomationMode.LIVE,
                                           products=PRODUCTS)
