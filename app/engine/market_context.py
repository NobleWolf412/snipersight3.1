"""Canonical point-in-time market phase assembled from recorded facts."""
from __future__ import annotations

import json
import time

from . import breakout, importer, liquidity, regime, structure, volatility
from .contracts import MarketContextSnapshot, to_wire


MARKET_CONTEXT_VERSION = "market-context-v0.1-draft"


def _latest(con, symbol: str, tf: str, kind: str, version: str,
            as_of: int, *, event: str | None = None) -> tuple[int, dict] | None:
    rows = con.execute(
        "SELECT confirmed_at,payload FROM facts WHERE symbol=? AND tf=? AND kind=? "
        "AND algo_version=? AND confirmed_at<=? ORDER BY confirmed_at DESC,id DESC",
        (symbol, tf, kind, version, as_of))
    for confirmed_at, raw in rows:
        payload = json.loads(raw)
        if event is None or payload.get("event") == event:
            return int(confirmed_at), payload
    return None


def snapshot(con, symbol: str, tf: str, *, as_of: int | None = None) -> dict:
    observed_at = int(time.time()) if as_of is None else int(as_of)
    if tf not in importer.TF_SECONDS:
        raise ValueError(f"unsupported timeframe {tf}")
    granularity = importer.TF_SECONDS[tf]
    candle = con.execute(
        "SELECT MAX(open_ts) FROM candles WHERE symbol=? AND tf=? AND open_ts+?<=?",
        (symbol, tf, granularity, observed_at)).fetchone()[0]
    if candle is None:
        data_status = "MISSING"
    elif observed_at - (int(candle) + granularity) > 2 * granularity:
        data_status = "DEGRADED"
    else:
        data_status = "HEALTHY"

    reg = _latest(con, symbol, tf, "regime", regime.REGIME_VERSION, observed_at)
    struct = _latest(
        con, symbol, tf, "structure", structure.STRUCTURE_VERSION, observed_at)
    squeeze = _latest(
        con, symbol, tf, "volatility", volatility.VOLATILITY_VERSION,
        observed_at, event="SQUEEZE")
    atr = _latest(
        con, symbol, tf, "volatility", volatility.VOLATILITY_VERSION,
        observed_at, event="ATR_REGIME")
    liq = _latest(
        con, symbol, tf, "liquidity", liquidity.LIQ_VERSION, observed_at)
    release = _latest(
        con, symbol, tf, "setup", breakout.BREAKOUT_VERSION, observed_at)

    base = str((reg or (0, {}))[1].get("regime") or "UNKNOWN")
    squeeze_state = (squeeze or (0, {}))[1].get("squeeze")
    atr_state = (atr or (0, {}))[1].get("regime")
    recent_release = bool(
        release and observed_at - release[0] <= 3 * granularity and
        release[1].get("state") == "VALIDATED")
    recent_break = bool(
        struct and observed_at - struct[0] <= 3 * granularity and
        struct[1].get("event") in ("BOS", "CHOCH"))

    if data_status != "HEALTHY":
        canonical = "UNSTABLE"
    elif recent_release:
        canonical = "BREAKOUT"
    elif squeeze_state == "ON":
        canonical = "COMPRESSION"
    elif atr_state == "HIGH" and recent_break:
        canonical = "EXPANSION"
    else:
        canonical = base

    struct_payload = (struct or (0, {}))[1]
    structure_state = "/".join(str(x) for x in (
        struct_payload.get("event"), struct_payload.get("direction") or
        struct_payload.get("label")) if x) or None
    volatility_state = "/".join(str(x) for x in (
        squeeze_state, atr_state) if x) or None
    liquidity_payload = (liq or (0, {}))[1]
    liquidity_state = str(liquidity_payload.get("event") or
                          liquidity_payload.get("state") or "") or None
    return to_wire(MarketContextSnapshot(
        symbol=symbol, timeframe=tf, as_of=observed_at, regime=canonical,
        structure=structure_state, volatility=volatility_state,
        liquidity_state=liquidity_state, data_status=data_status,
        version=MARKET_CONTEXT_VERSION))
