"""US-equity workspace foundation and provider connection contracts.

This module deliberately owns no scanner and sends no orders.  It answers the
first honest stock-workspace question: are the two external authorities needed
to build the stock book configured and reachable?

Alpaca paper is the execution/account authority and the SIP market-data seam.
Massive is the point-in-time universe and corporate-action authority.  Neither
is added to ``venues.ALL``: that resolver is intentionally based on crypto
symbol spelling, and allowing an equity ticker through it would apply crypto
shorting, leverage, fee and funding rules to a stock.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from . import credentials


STOCKS_FOUNDATION_VERSION = "stocks-foundation-v0.1-draft"
ALPACA_TARGET = "alpaca-paper"
MASSIVE_TARGET = "massive-stocks"
ALPACA_PAPER_API = "https://paper-api.alpaca.markets"
ALPACA_DATA_API = "https://data.alpaca.markets"
MASSIVE_API = "https://api.massive.com"
STOCK_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "stocks.db"


class StockProviderError(RuntimeError):
    """A provider refusal safe to show without exposing request credentials."""


def _get_json(url: str, headers: dict[str, str], *,
              opener: Callable = urllib.request.urlopen) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "snipersight-stocks/0.1", **headers})
    try:
        with opener(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            raw = json.loads(exc.read().decode("utf-8"))
            detail = raw.get("message") or raw.get("error") or "request refused"
        except Exception:
            detail = "request refused"
        # Do not stringify the Request or exception: provider error objects can
        # contain a URL, and query-string credentials must never reach the log
        # or UI even though these integrations use headers today.
        raise StockProviderError(f"provider returned HTTP {exc.code}: {detail}") from None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise StockProviderError(f"provider could not be read: {type(exc).__name__}") from None
    if not isinstance(payload, dict):
        raise StockProviderError("provider returned an unexpected response")
    return payload


def _secret(target: str, field: str) -> str:
    value = credentials.read_secret(target, field)
    if not value:
        raise StockProviderError(
            f"{target.replace('-', ' ')} {field.replace('_', ' ')} is not stored")
    return value


def _alpaca_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": _secret(ALPACA_TARGET, "api_key"),
        "APCA-API-SECRET-KEY": _secret(ALPACA_TARGET, "api_secret"),
    }


def test_connection(target: str, *, opener: Callable = urllib.request.urlopen) -> dict:
    """Run only read-only provider checks; never submit, cancel, or modify.

    Alpaca is intentionally two checks.  A valid paper account does not prove
    access to the consolidated SIP feed the stock scanner requires.
    """
    if target == ALPACA_TARGET:
        headers = _alpaca_headers()
        account = _get_json(f"{ALPACA_PAPER_API}/v2/account", headers,
                            opener=opener)
        account_ok = bool(account.get("id")) and account.get("status") != "ACCOUNT_CLOSED"
        if not account_ok:
            raise StockProviderError("Alpaca paper account was not active")
        try:
            latest = _get_json(
                f"{ALPACA_DATA_API}/v2/stocks/AAPL/bars/latest?feed=sip",
                headers, opener=opener)
        except StockProviderError as exc:
            return {
                "ok": False,
                "target": target,
                "paper_account": True,
                "sip_data": False,
                "detail": "Paper account connected, but consolidated SIP data "
                          f"is not available ({exc}).",
            }
        sip_ok = isinstance(latest.get("bar"), dict)
        return {
            "ok": sip_ok,
            "target": target,
            "paper_account": True,
            "sip_data": sip_ok,
            "detail": ("Paper account and SIP market data connected."
                       if sip_ok else
                       "Paper account connected, but SIP returned no latest bar."),
        }
    if target == MASSIVE_TARGET:
        key = _secret(MASSIVE_TARGET, "api_key")
        query = urllib.parse.urlencode({
            "market": "stocks", "locale": "us", "active": "true", "limit": 1,
        })
        payload = _get_json(
            f"{MASSIVE_API}/v3/reference/tickers?{query}",
            {"Authorization": f"Bearer {key}"}, opener=opener)
        ok = payload.get("status") == "OK" and bool(payload.get("results"))
        return {
            "ok": ok,
            "target": target,
            "point_in_time_universe": ok,
            "detail": ("Massive stock reference data connected."
                       if ok else "Massive returned no active US stock reference row."),
        }
    raise StockProviderError(f"unknown stock provider {target!r}")


def status() -> dict:
    """Server-owned readiness; configured is never presented as verified."""
    stored = credentials.status()
    alpaca = stored[ALPACA_TARGET]
    massive = stored[MASSIVE_TARGET]
    alpaca_ready = all(alpaca.values())
    massive_ready = all(massive.values())
    connections_ready = alpaca_ready and massive_ready
    blockers = []
    if not alpaca_ready:
        blockers.append("Store an Alpaca paper API key and secret.")
    if not massive_ready:
        blockers.append("Store a Massive API key for the point-in-time universe.")
    if connections_ready:
        blockers.append("Verify both connections before importing a stock universe.")
    blockers.extend([
        "The isolated stock universe has not been imported.",
        "The stock scanner and stock-native strategies are not enabled.",
    ])
    return {
        "version": STOCKS_FOUNDATION_VERSION,
        "asset_class": "US_EQUITY",
        "workspace": "STOCKS",
        "state": "CONNECTIONS_CONFIGURED" if connections_ready else "SETUP_REQUIRED",
        "mode": "PAPER",
        "live_enabled": False,
        "scanner_enabled": False,
        "data_store": {
            "isolated": True,
            "exists": STOCK_DB_PATH.exists(),
            "name": STOCK_DB_PATH.name,
        },
        "providers": {
            ALPACA_TARGET: {
                "label": "Alpaca Paper + SIP",
                "role": "paper execution, account custody, and consolidated live tape",
                "configured": alpaca_ready,
                "required_fields": list(credentials.TARGET_FIELDS[ALPACA_TARGET]),
                "verification": "NOT_RUN",
            },
            MASSIVE_TARGET: {
                "label": "Massive Stocks",
                "role": "point-in-time universe, listings, delistings, and corporate actions",
                "configured": massive_ready,
                "required_fields": list(credentials.TARGET_FIELDS[MASSIVE_TARGET]),
                "verification": "NOT_RUN",
            },
        },
        "progress": [
            {"key": "connections", "label": "Connections",
             "state": "READY_TO_VERIFY" if connections_ready else "ACTION_REQUIRED",
             "detail": "Encrypted provider keys are stored." if connections_ready
                       else "Both stock data authorities must be configured."},
            {"key": "universe", "label": "Point-in-time universe", "state": "BLOCKED",
             "detail": "Waiting for verified Massive reference access."},
            {"key": "scanner", "label": "Stock scout", "state": "BLOCKED",
             "detail": "Waiting for an isolated universe and stock-native evidence rules."},
            {"key": "paper", "label": "Paper execution", "state": "BLOCKED",
             "detail": "No stock order route exists in this foundation build."},
        ],
        "blockers": blockers,
    }
