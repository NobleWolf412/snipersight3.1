"""Private Phemex USDT-perpetual REST adapter.

The adapter is injectable and testnet-first.  Constructing a mainnet client is
refused while the automation build gate is false.  It never reads credentials
from HTTP code and never logs request headers or bodies.

Official contract used here (retrieved 2026-08-07): signatures are
HMAC-SHA256(path + query + expiry + body); USDT orders use ``/g-orders`` and
real-value ``*Rp/*Rq`` fields; one-way positions use ``posSide=Merged``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Callable

from . import automation, phemex
from .contracts import BrokerExecution, BrokerOrder, ExecutionPlan, OrderKind


PHEMEX_PRIVATE_VERSION = "phemex-private-v0.3-draft"
TESTNET_API = "https://testnet-api.phemex.com"
MAINNET_API = "https://api.phemex.com"


class PhemexError(RuntimeError):
    pass


class AmbiguousSubmission(PhemexError):
    """The venue may have accepted the order; reconcile before retrying."""


def signature(secret: str, path: str, query: str, expiry: int,
              body: str = "") -> str:
    message = f"{path}{query}{expiry}{body}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _urllib_transport(method: str, url: str, headers: dict,
                      body: bytes | None, timeout: int = 20) -> dict:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if exc.code >= 500:
            raise AmbiguousSubmission(
                f"Phemex returned HTTP {exc.code}; execution state is unknown") from exc
        raise PhemexError(f"Phemex returned HTTP {exc.code}: {raw[:240]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AmbiguousSubmission(
            "Phemex request ended without a definitive response; reconcile by "
            "client order id before retrying") from exc


class PhemexBroker:
    account_wide_open_orders = True

    def __init__(self, api_key: str, api_secret: str, *,
                 environment: str = "testnet", withdrawal_enabled: bool = False,
                 transport: Callable | None = None,
                 products: list[dict] | None = None):
        if not api_key or not api_secret:
            raise ValueError("Phemex API key and secret are required")
        if environment not in ("testnet", "mainnet"):
            raise ValueError("environment must be testnet or mainnet")
        if withdrawal_enabled:
            raise ValueError("withdrawal-enabled API credentials are forbidden")
        if environment == "mainnet" and not automation.LIVE_ROUTER_BUILD_ENABLED:
            raise PhemexError("mainnet broker construction is build-locked")
        self.api_key = api_key
        self._secret = api_secret
        self.environment = environment
        self.base_url = TESTNET_API if environment == "testnet" else MAINNET_API
        self._transport = transport or _urllib_transport
        self._products = {row["symbol"]: row for row in (products or [])}
        self._server_offset_seconds = 0
        self.clock_synchronized = False

    def refresh_products(self) -> list[dict]:
        """Load instrument rules from this broker's own environment."""
        result = self._transport(
            "GET", self.base_url + "/public/products",
            {"User-Agent": "snipersight/0.1"}, None)
        products = phemex.normalize_products(result)
        if not products:
            raise PhemexError(
                f"Phemex {self.environment} returned no USDT perpetual metadata")
        self._products = {row["symbol"]: row for row in products}
        return products

    def sync_time(self) -> int:
        """Synchronize signing expiry to Phemex server time."""
        result = self._transport(
            "GET", self.base_url + "/public/time",
            {"User-Agent": "snipersight/0.1"}, None)
        raw = result.get("data") if isinstance(result, dict) else None
        if isinstance(raw, dict):
            raw = raw.get("serverTime") or raw.get("timestamp")
        if raw is None and isinstance(result, dict):
            raw = result.get("serverTime")
        if raw is None:
            raise PhemexError("Phemex server-time response has no timestamp")
        server = int(raw)
        if server > 10_000_000_000:
            server //= 1000
        self._server_offset_seconds = server - int(time.time())
        self.clock_synchronized = True
        return self._server_offset_seconds

    def _request(self, method: str, path: str, *, query: dict | None = None,
                 payload: dict | None = None,
                 timeout_seconds: float | None = None) -> dict:
        query_string = urllib.parse.urlencode(query or {})
        body_text = (json.dumps(payload, sort_keys=True, separators=(",", ":"))
                     if payload is not None else "")
        expiry = int(time.time()) + self._server_offset_seconds + 60
        headers = {
            "x-phemex-access-token": self.api_key,
            "x-phemex-request-expiry": str(expiry),
            "x-phemex-request-signature": signature(
                self._secret, path, query_string, expiry, body_text),
            "x-phemex-request-tracing": hashlib.sha256(
                f"{expiry}:{path}:{query_string}".encode()).hexdigest()[:32],
            "Content-Type": "application/json",
            "User-Agent": "snipersight/0.1",
        }
        url = self.base_url + path + ("?" + query_string if query_string else "")
        attempts = 0
        deadline = (time.monotonic() + timeout_seconds
                    if timeout_seconds is not None else None)
        while True:
            attempts += 1
            try:
                args = (method, url, headers,
                        body_text.encode("utf-8") if body_text else None)
                if self._transport is _urllib_transport and timeout_seconds is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise PhemexError("request deadline expired")
                    result = self._transport(*args, timeout=max(0.1, remaining))
                else:
                    result = self._transport(*args)
                break
            except PhemexError as exc:
                if "HTTP 429" not in str(exc) or attempts >= 3:
                    raise
                delay = 0.25 * attempts
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= delay:
                        raise PhemexError("request deadline expired") from exc
                time.sleep(delay)
        if not isinstance(result, dict):
            raise PhemexError("Phemex returned a non-object response")
        if result.get("code") not in (None, 0):
            raise PhemexError(
                f"Phemex code {result.get('code')}: {result.get('msg') or 'unknown error'}")
        return result

    def _product(self, symbol: str) -> dict:
        if symbol not in self._products:
            raise PhemexError(
                f"no instrument metadata loaded for {symbol}; refusing to guess "
                "tick, lot or notional rules")
        return self._products[symbol]

    @staticmethod
    def _multiple(value: Decimal, step) -> bool:
        if step in (None, "", 0, "0"):
            return False
        quantum = Decimal(str(step))
        return value % quantum == 0

    def validate_plan(self, plan: ExecutionPlan) -> None:
        intent, risk_decision = plan.intent, plan.risk
        product = self._product(intent.symbol)
        if plan.margin_mode != "ISOLATED" or plan.position_mode != "ONE_WAY":
            raise PhemexError("Phemex execution requires ISOLATED and ONE_WAY")
        if not risk_decision.approved or risk_decision.quantity <= 0:
            raise PhemexError("risk authority did not approve a positive quantity")
        if not self._multiple(risk_decision.quantity, product.get("qty_step")):
            raise PhemexError("quantity is not an exact instrument lot multiple")
        if intent.order_kind == OrderKind.LIMIT:
            if intent.entry is None or not self._multiple(intent.entry,
                                                           product.get("tick_size")):
                raise PhemexError("limit price is not an exact instrument tick multiple")
        notional = risk_decision.notional_usd
        minimum = Decimal(str(product.get("min_notional") or "0"))
        if minimum > 0 and notional < minimum:
            raise PhemexError("order is below the instrument minimum notional")
        maximum = Decimal(str(product.get("max_order_qty") or "0"))
        if maximum > 0 and risk_decision.quantity > maximum:
            raise PhemexError("order exceeds the instrument maximum quantity")

    @staticmethod
    def _client_id(plan: ExecutionPlan) -> str:
        # Phemex max is 40 bytes. A stable prefix of the already-hashed key
        # preserves retry identity without leaking the composite setup id.
        return "ss-" + plan.intent.idempotency_key[:37]

    def client_order_id(self, plan: ExecutionPlan) -> str:
        return self._client_id(plan)

    @staticmethod
    def _order(row: dict, *, fallback_client_id: str = "") -> BrokerOrder:
        raw_kind = row.get("orderType") or row.get("ordType") or "Limit"
        kind = {1: "MARKET", 2: "LIMIT", 3: "STOP", 4: "STOPLIMIT"}.get(
            raw_kind, str(raw_kind).upper())
        raw_status = row.get("ordStatus")
        if raw_status is None:
            raw_status = row.get("execStatus") or "UNKNOWN"
        status = {0: "Created", 1: "Untriggered", 2: "Deactivated",
                  3: "Triggered", 4: "Rejected", 5: "New",
                  6: "PartiallyFilled", 7: "Filled", 8: "Canceled"}.get(
                      raw_status, str(raw_status))
        return BrokerOrder(
            broker_order_id=row.get("orderID") or row.get("orderId"),
            client_order_id=str(row.get("clOrdID") or row.get("clOrdId") or
                                fallback_client_id),
            symbol=str(row.get("symbol") or ""),
            status=status,
            order_kind=OrderKind.MARKET if kind == "MARKET" else OrderKind.LIMIT,
            quantity=Decimal(str(row.get("orderQtyRq") or "0")),
            filled_quantity=Decimal(str(row.get("cumQtyRq") or "0")),
            limit_price=(Decimal(str(row["priceRp"])) if row.get("priceRp") not in
                         (None, "") else None),
            reduce_only=bool(row.get("reduceOnly")),
            updated_at=int(int(row.get("transactTimeNs") or
                               row.get("actionTimeNs") or time.time_ns()) //
                           1_000_000_000),
            average_fill_price=(Decimal(str(row["avgPriceRp"]))
                                if row.get("avgPriceRp") not in (None, "")
                                else None),
            cumulative_fee=Decimal(str(row.get("cumFeeRv") or
                                       row.get("execFeeRv") or "0")),
            raw_code=str(row.get("bizError")) if row.get("bizError") else None,
            version=PHEMEX_PRIVATE_VERSION)

    def submit(self, plan: ExecutionPlan) -> BrokerOrder:
        self.validate_plan(plan)
        intent = plan.intent
        client_id = self._client_id(plan)
        self.enforce_one_way(intent.symbol)
        self.set_leverage(intent.symbol, Decimal("1"))
        payload = {
            "clOrdID": client_id, "symbol": intent.symbol,
            "side": "Buy" if intent.direction == "LONG" else "Sell",
            "posSide": "Merged", "orderQtyRq": str(plan.risk.quantity),
            "ordType": "Market" if intent.order_kind == OrderKind.MARKET else "Limit",
            "timeInForce": ("ImmediateOrCancel" if intent.order_kind == OrderKind.MARKET
                            else "PostOnly"),
            "reduceOnly": bool(intent.reduce_only), "closeOnTrigger": False,
            "stopLossRp": str(intent.stop), "slTrigger": "ByMarkPrice",
            "text": "SniperSight " + intent.playbook_version,
        }
        if intent.entry is not None and intent.order_kind == OrderKind.LIMIT:
            payload["priceRp"] = str(intent.entry)
        try:
            result = self._request("POST", "/g-orders", payload=payload)
        except AmbiguousSubmission:
            # A POST timeout is not a failure. Query the open book by symbol and
            # recover the order with the same client id before allowing a retry.
            matches = [o for o in self.open_orders(intent.symbol)
                       if o.client_order_id == client_id]
            if matches:
                return matches[0]
            raise
        return self._order(result.get("data") or {}, fallback_client_id=client_id)

    def cancel(self, symbol: str, client_order_id: str) -> BrokerOrder:
        result = self._request(
            "DELETE", "/g-orders/cancel",
            query={"symbol": symbol, "origClOrdID": client_order_id,
                   "posSide": "Merged"})
        return self._order(result.get("data") or {}, fallback_client_id=client_order_id)

    def replace(self, symbol: str, client_order_id: str, *,
                quantity: Decimal | None = None,
                price: Decimal | None = None,
                stop: Decimal | None = None,
                timeout_seconds: float | None = None) -> BrokerOrder:
        """Amend one known order; the client identity is never changed."""
        product = self._product(symbol)
        query = {"symbol": symbol, "origClOrdID": client_order_id,
                 "posSide": "Merged"}
        if quantity is not None:
            if not self._multiple(quantity, product.get("qty_step")):
                raise PhemexError("replacement quantity is not an exact lot multiple")
            query["orderQtyRq"] = str(quantity)
        if price is not None:
            if not self._multiple(price, product.get("tick_size")):
                raise PhemexError("replacement price is not an exact tick multiple")
            query["priceRp"] = str(price)
        if stop is not None:
            if not self._multiple(stop, product.get("tick_size")):
                raise PhemexError("replacement stop is not an exact tick multiple")
            query["stopPxRp"] = str(stop)
        if len(query) == 3:
            raise ValueError("replacement requires quantity, price or stop")
        result = self._request("PUT", "/g-orders/replace", query=query,
                               timeout_seconds=timeout_seconds)
        return self._order(result.get("data") or {},
                           fallback_client_id=client_order_id)

    def order_status(self, symbol: str, client_order_id: str,
                     broker_order_id: str | None = None) -> BrokerOrder | None:
        """Poll active state, then closed history when an order id is known."""
        for order in self.open_orders(symbol):
            if order.client_order_id == client_order_id:
                return order
        if not broker_order_id:
            result = self._request(
                "GET", "/api-data/g-futures/orders/by-order-id",
                query={"symbol": symbol, "clOrdID": client_order_id})
            data = result.get("data") or {}
            rows = data.get("rows") or [] if isinstance(data, dict) else []
            row = rows[0] if rows else None
            if row is None and isinstance(data, dict) and data.get("ordStatus"):
                row = data
            return None if not row else self._order(
                row, fallback_client_id=client_order_id)
        result = self._request(
            "GET", "/api-data/g-futures/orders/by-order-id",
            query={"symbol": symbol, "orderID": broker_order_id})
        data = result.get("data") or {}
        rows = data.get("rows") or [] if isinstance(data, dict) else []
        row = rows[0] if rows else None
        if row is None and isinstance(data, dict) and data.get("orderID"):
            row = data
        return None if not row else self._order(
            row, fallback_client_id=client_order_id)

    def open_orders(self, symbol: str | None = None) -> list[BrokerOrder]:
        if symbol:
            result = self._request("GET", "/g-orders/activeList",
                                   query={"symbol": symbol})
            rows = (result.get("data") or {}).get("rows") or []
        else:
            # Phemex has no all-symbol active-order endpoint. History is capped
            # at 90 days, so it cannot prove an older GTC order absent. Enumerate
            # every listed product instead: slower, but account-complete.
            rows = []
            for product_symbol in sorted(self._products):
                result = self._request(
                    "GET", "/g-orders/activeList",
                    query={"symbol": product_symbol})
                rows.extend((result.get("data") or {}).get("rows") or [])
        orders = [self._order(row) for row in rows]
        if symbol:
            return orders
        open_statuses = {"NEW", "PARTIALLYFILLED", "UNTRIGGERED", "TRIGGERED"}
        return [order for order in orders
                if str(order.status).upper().replace("_", "") in open_statuses]

    def executions(self, symbol: str, *, start_at: int) -> list[BrokerExecution]:
        """Return every venue execution since ``start_at`` with exact fees.

        Phemex defaults this endpoint to a short recent window. Explicit
        millisecond bounds and pagination are mandatory: lifecycle evidence
        must not disappear merely because an order lived longer than two days.
        """
        end_ms = int(time.time() * 1000)
        start_ms = int(start_at) * 1000
        offset, found = 0, []
        while True:
            result = self._request(
                "GET", "/api-data/g-futures/trades",
                query={"symbol": symbol, "start": start_ms, "end": end_ms,
                       "offset": offset, "limit": 200, "withCount": 1})
            data = result.get("data") or {}
            rows = data.get("rows") or [] if isinstance(data, dict) else data
            rows = list(rows or [])
            for row in rows:
                execution_id = str(row.get("execID") or row.get("execId") or "")
                order_id = str(row.get("orderID") or row.get("orderId") or "")
                if not execution_id or not order_id:
                    continue
                found.append(BrokerExecution(
                    execution_id=execution_id, broker_order_id=order_id,
                    client_order_id=str(row.get("clOrdID") or
                                        row.get("clOrdId") or ""),
                    symbol=str(row.get("symbol") or symbol),
                    side=str(row.get("side") or ""),
                    quantity=Decimal(str(row.get("execQtyRq") or "0")),
                    price=Decimal(str(row.get("execPriceRp") or "0")),
                    fee=Decimal(str(row.get("execFeeRv") or "0")),
                    fee_currency=str(row.get("currency") or "USDT"),
                    occurred_at=int(int(row.get("transactTimeNs") or 0) /
                                    1_000_000_000),
                    version=PHEMEX_PRIVATE_VERSION))
            if len(rows) < 200:
                break
            offset += len(rows)
            if offset > 10_000:
                raise PhemexError("execution history pagination exceeded safety bound")
        return sorted(found, key=lambda item: (item.occurred_at,
                                                item.execution_id))

    def positions(self, symbol: str | None = None, *,
                  timeout_seconds: float | None = None) -> list[dict]:
        query = {"currency": "USDT"}
        if symbol:
            query["symbol"] = symbol
        result = self._request("GET", "/g-accounts/accountPositions", query=query,
                               timeout_seconds=timeout_seconds)
        return list((result.get("data") or {}).get("positions") or [])

    def submit_protective_stop(self, *, symbol: str, direction: str,
                               quantity: Decimal, stop: Decimal,
                               client_order_id: str,
                               timeout_seconds: float | None = None) -> BrokerOrder:
        """Create a standalone reduce-only stop for actual filled exposure."""
        product = self._product(symbol)
        if not self._multiple(quantity, product.get("qty_step")):
            raise PhemexError("protective quantity is not an exact lot multiple")
        if not self._multiple(stop, product.get("tick_size")):
            raise PhemexError("protective stop is not an exact tick multiple")
        result = self._request("POST", "/g-orders", payload={
            "clOrdID": client_order_id[:40], "symbol": symbol,
            "side": "Sell" if direction == "LONG" else "Buy",
            "posSide": "Merged", "orderQtyRq": str(quantity),
            "ordType": "Stop", "stopPxRp": str(stop),
            "triggerType": "ByMarkPrice", "timeInForce": "GoodTillCancel",
            "reduceOnly": True, "closeOnTrigger": True,
            "text": "SniperSight protective stop",
        }, timeout_seconds=timeout_seconds)
        return self._order(result.get("data") or {},
                           fallback_client_id=client_order_id[:40])

    def submit_target(self, *, symbol: str, direction: str,
                      quantity: Decimal, target: Decimal,
                      client_order_id: str,
                      timeout_seconds: float | None = None) -> BrokerOrder:
        """Create one deterministic reduce-only first-target order."""
        product = self._product(symbol)
        if not self._multiple(quantity, product.get("qty_step")):
            raise PhemexError("target quantity is not an exact lot multiple")
        if not self._multiple(target, product.get("tick_size")):
            raise PhemexError("target is not an exact tick multiple")
        result = self._request("POST", "/g-orders", payload={
            "clOrdID": client_order_id[:40], "symbol": symbol,
            "side": "Sell" if direction == "LONG" else "Buy",
            "posSide": "Merged", "orderQtyRq": str(quantity),
            "ordType": "Limit", "priceRp": str(target),
            "timeInForce": "GoodTillCancel", "reduceOnly": True,
            "closeOnTrigger": False, "text": "SniperSight target 1",
        }, timeout_seconds=timeout_seconds)
        return self._order(result.get("data") or {},
                           fallback_client_id=client_order_id[:40])

    def confirm_attached_protection(self, *, symbol: str, direction: str,
                                    quantity: Decimal, stop: Decimal,
                                    client_order_id: str,
                                    timeout_seconds: float | None = None) -> BrokerOrder | None:
        """Confirm the stop attached atomically to the entry order."""
        for row in self.positions(symbol, timeout_seconds=timeout_seconds):
            if str(row.get("symbol")) != symbol:
                continue
            size = abs(Decimal(str(row.get("sizeRq") or row.get("size") or "0")))
            side = str(row.get("posSide") or row.get("side") or "").upper()
            if direction == "LONG" and side in {"SHORT", "SELL"}:
                continue
            if direction == "SHORT" and side in {"LONG", "BUY"}:
                continue
            recorded_stop = row.get("stopLossRp") or row.get("stopPxRp")
            if size >= quantity and recorded_stop not in (None, "") and \
                    Decimal(str(recorded_stop)) == stop:
                return BrokerOrder(
                    broker_order_id=None, client_order_id=client_order_id[:40],
                    symbol=symbol, status="OPEN", order_kind=OrderKind.MARKET,
                    quantity=quantity, filled_quantity=quantity,
                    limit_price=stop, reduce_only=True,
                    updated_at=int(time.time()),
                    version=PHEMEX_PRIVATE_VERSION)
        return None

    def emergency_close(self, *, symbol: str, direction: str,
                        quantity: Decimal, client_order_id: str,
                        timeout_seconds: float | None = None) -> BrokerOrder:
        """Flatten exposure using a reduce-only IOC market order."""
        result = self._request("POST", "/g-orders", payload={
            "clOrdID": client_order_id[:40], "symbol": symbol,
            "side": "Sell" if direction == "LONG" else "Buy",
            "posSide": "Merged", "orderQtyRq": str(quantity),
            "ordType": "Market", "timeInForce": "ImmediateOrCancel",
            "reduceOnly": True, "closeOnTrigger": False,
            "text": "SniperSight emergency close",
        }, timeout_seconds=timeout_seconds)
        return self._order(result.get("data") or {},
                           fallback_client_id=client_order_id[:40])

    def enforce_one_way(self, symbol: str) -> None:
        self._request("PUT", "/g-positions/switch-pos-mode-sync",
                      query={"symbol": symbol, "targetPosMode": "OneWay"})

    def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        if leverage <= 0:
            raise ValueError("leverage must be positive")
        self._request("PUT", "/g-positions/leverage",
                      query={"symbol": symbol, "leverageRr": str(leverage)})
