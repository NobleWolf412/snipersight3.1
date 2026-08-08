"""Construct private brokers only from environment-isolated local secrets."""
from __future__ import annotations

from . import automation, credentials, phemex_private
from .contracts import AutomationMode


class BrokerConfigurationError(RuntimeError):
    pass


def phemex_for_mode(mode: AutomationMode, *, products: list[dict] | None = None,
                    transport=None) -> phemex_private.PhemexBroker:
    if mode not in (AutomationMode.TESTNET, AutomationMode.LIVE):
        raise BrokerConfigurationError(
            f"{mode.value} has no private broker; no credentials were read")
    environment = "testnet" if mode == AutomationMode.TESTNET else "mainnet"
    target = f"phemex-{environment}"
    if environment == "mainnet" and not automation.LIVE_ROUTER_BUILD_ENABLED:
        raise BrokerConfigurationError("mainnet private routing is build-locked")
    api_key = credentials.read_secret(target, "api_key")
    api_secret = credentials.read_secret(target, "api_secret")
    if not api_key or not api_secret:
        raise BrokerConfigurationError(
            f"{target} API key and secret are required; credentials from the "
            "other environment are never reused")
    broker = phemex_private.PhemexBroker(
        api_key, api_secret, environment=environment, transport=transport,
        products=products or [], withdrawal_enabled=False)
    if products is None:
        try:
            broker.refresh_products()
        except phemex_private.PhemexError as exc:
            raise BrokerConfigurationError(str(exc)) from exc
    return broker
