"""Phemex open-interest collection and one-hour research observations."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import time

from . import phemex, research, store
from .ma import plain, sig


OPEN_INTEREST_VERSION = "open-interest-v0.1-draft"
ONE_HOUR_MIN_SECONDS = 3600
ONE_HOUR_MAX_SECONDS = 4500


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def collect(con, symbols: list[str], observed_at: int) -> dict:
    """Collect one public ticker snapshot using the scan's fixed opening time."""
    wanted = {s for s in symbols if s.endswith("USDT")}
    if not wanted:
        return {"attempted": 0, "succeeded": 0, "missing": 0, "failed": 0,
                "observed_at": observed_at}
    attempted = len(wanted)
    try:
        tickers = phemex.open_interest_snapshot(wanted)
    except Exception as exc:
        collected_at = int(time.time())
        con.execute("INSERT INTO open_interest_runs "
                    "(observed_at,collected_at,attempted,succeeded,missing,failed,"
                    "supported_contracts,error,version) VALUES (?,?,?,?,?,?,?,?,?)",
                    (observed_at, collected_at, attempted, 0, attempted, 1, None,
                     f"{type(exc).__name__}: {exc}"[:300], OPEN_INTEREST_VERSION))
        con.commit()
        return {"attempted": attempted, "succeeded": 0, "missing": attempted,
                "failed": 1, "observed_at": observed_at, "error": str(exc)}
    supported_contracts = getattr(tickers, "supported_contract_count", None)
    succeeded = 0
    for symbol in sorted(wanted):
        row = tickers.get(symbol)
        oi = _decimal((row or {}).get("open_interest"))
        price = _decimal((row or {}).get("price"))
        if oi is None or price is None:
            continue
        collected_at = int(time.time())
        con.execute("INSERT OR IGNORE INTO open_interest "
                    "(symbol,observed_at,value,price,source,source_ts,collected_at,version) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (symbol, observed_at, plain(oi), plain(price),
                     "phemex-perp", (row or {}).get("source_ts"), collected_at,
                     OPEN_INTEREST_VERSION))
        succeeded += 1
        _emit_signal(con, symbol, observed_at, oi, price)
    missing = attempted - succeeded
    collected_at = int(time.time())
    con.execute("INSERT INTO open_interest_runs "
                "(observed_at,collected_at,attempted,succeeded,missing,failed,"
                "supported_contracts,error,version) VALUES (?,?,?,?,?,?,?,?,?)",
                (observed_at, collected_at, attempted, succeeded, missing, 0,
                 supported_contracts, None, OPEN_INTEREST_VERSION))
    con.commit()
    return {"attempted": attempted, "succeeded": succeeded, "missing": missing,
            "failed": 0, "observed_at": observed_at}


def _emit_signal(con, symbol, observed_at, oi, price):
    prior = con.execute(
        "SELECT observed_at,value,price FROM open_interest WHERE symbol=? "
        "AND observed_at BETWEEN ? AND ? ORDER BY observed_at DESC LIMIT 1",
        (symbol, observed_at - ONE_HOUR_MAX_SECONDS,
         observed_at - ONE_HOUR_MIN_SECONDS)).fetchone()
    if not prior:
        return
    prior_oi, prior_price = Decimal(prior[1]), Decimal(prior[2])
    oi_change = sig(oi - prior_oi)
    price_change = sig(price - prior_price)
    oi_pct = None if prior_oi == 0 else sig(oi_change * Decimal(100) / prior_oi)
    price_pct = None if prior_price == 0 else sig(price_change * Decimal(100) / prior_price)
    if price_change > 0 and oi_change > 0:
        quadrant, direction, label = "PRICE_UP_OI_UP", "BULL", "Expanding"
    elif price_change < 0 and oi_change > 0:
        quadrant, direction, label = "PRICE_DOWN_OI_UP", "BEAR", "Expanding"
    elif price_change > 0 and oi_change < 0:
        quadrant, direction, label = "PRICE_UP_OI_DOWN", "NEUTRAL", "Contracting"
    elif price_change < 0 and oi_change < 0:
        quadrant, direction, label = "PRICE_DOWN_OI_DOWN", "NEUTRAL", "Contracting"
    else:
        quadrant, direction, label = "UNCHANGED", "NEUTRAL", "Neutral"
    payload = {"event": "ONE_HOUR_CHANGE", "direction": direction,
               "label": label, "quadrant": quadrant,
               "value": plain(oi), "previous_value": plain(prior_oi),
               "change_1h": plain(oi_change),
               "change_1h_pct": plain(oi_pct) if oi_pct is not None else None,
               "price": plain(price), "previous_price": plain(prior_price),
               "price_change_1h_pct": plain(price_pct) if price_pct is not None else None,
               "interval_seconds": observed_at - prior[0],
               "previous_observed_at": prior[0], "observed_at": observed_at}
    store.insert_fact(con, symbol=symbol, tf="1H", kind="open_interest_signal",
                      market_time=observed_at, confirmed_at=observed_at,
                      algo_version=research.OPEN_INTEREST_SIGNAL_VERSION,
                      payload=payload)


def series(con, symbol: str, *, as_of: int | None = None,
           limit: int = 1500) -> list[dict]:
    cutoff = as_of if as_of is not None else 2**63 - 1
    rows = con.execute(
        "SELECT observed_at,value,price,source,version FROM open_interest "
        "WHERE symbol=? AND observed_at<=? ORDER BY observed_at DESC LIMIT ?",
        (symbol, cutoff, limit)).fetchall()
    rows.reverse()
    signals = {r["confirmed_at"]: r for r in research._facts(
        con, symbol, "1H", "open_interest_signal", research.OPEN_INTEREST_SIGNAL_VERSION)}
    out = []
    previous = None
    for observed_at, value, price, source, version in rows:
        if previous is not None and observed_at - previous > research.OI_STALE_AFTER:
            out.append({"time": previous + 1, "value": None, "status": "MISSING",
                        "missing_reason": "Open-interest observations are missing in this interval."})
        signal = signals.get(observed_at, {})
        out.append({"time": observed_at, "value": value, "price": price,
                    "source": source, "version": version, "status": "AVAILABLE",
                    "change_1h": signal.get("change_1h"),
                    "change_1h_pct": signal.get("change_1h_pct"),
                    "price_change_1h_pct": signal.get("price_change_1h_pct"),
                    "quadrant": signal.get("quadrant")})
        previous = observed_at
    return out


def status(con, now: int) -> dict:
    run = con.execute(
        "SELECT observed_at,attempted,succeeded,missing,failed,error,version,"
        "supported_contracts "
        "FROM open_interest_runs ORDER BY observed_at DESC,id DESC LIMIT 1").fetchone()
    first = con.execute("SELECT MIN(observed_at) FROM open_interest").fetchone()[0]
    if first is None:
        first = research.collection_start(
            con, "open_interest", research.OPEN_INTEREST_SIGNAL_VERSION)
    last_success = con.execute("SELECT MAX(observed_at) FROM open_interest").fetchone()[0]
    supported_row = con.execute(
        "SELECT supported_contracts FROM open_interest_runs "
        "WHERE supported_contracts IS NOT NULL ORDER BY observed_at DESC,id DESC "
        "LIMIT 1").fetchone()
    supported = supported_row[0] if supported_row else None
    totals = con.execute(
        "SELECT COALESCE(SUM(missing),0),COALESCE(SUM(failed),0) "
        "FROM open_interest_runs WHERE version=?", (OPEN_INTEREST_VERSION,)).fetchone()
    if not run:
        return {"version": OPEN_INTEREST_VERSION, "supported_contract_count": None,
                "last_successful_observation": None, "freshness": "MISSING",
                "missing_contract_observations": totals[0],
                "failed_collection_attempts": totals[1],
                "missing_requests": totals[0], "failed_requests": totals[1],
                "collection_start": first, "affects_trading": False,
                "label": "Collecting only — unused by trading."}
    freshness = ("MISSING" if last_success is None else
                 "FRESH" if now - last_success <= research.OI_STALE_AFTER else "STALE")
    return {"version": run[6], "supported_contract_count": supported,
            "last_successful_observation": last_success, "freshness": freshness,
            "missing_contract_observations": totals[0],
            "failed_collection_attempts": totals[1],
            "missing_requests": totals[0], "failed_requests": totals[1],
            "last_missing_contract_observations": run[3],
            "last_failed_collection_attempts": run[4],
            "last_attempt": run[0], "last_error": run[5],
            "collection_start": first, "affects_trading": False,
            "label": "Collecting only — unused by trading."}
