"""Coinbase Exchange market-data importer (public endpoints, no credentials — §16).

Native granularities used: 900 (15m), 3600 (1H), 86400 (1D).
4H and 1W are built by the aggregator, never imported.
Deterministic re-import: candles are keyed (symbol, tf, open_ts) and REPLACEd
with identical venue values; prices kept as exact decimal strings via
json parse_float=Decimal so no float ever touches a price.
"""
import json
import time
import urllib.request
from decimal import Decimal
from datetime import datetime, timezone

API = "https://api.exchange.coinbase.com"
IMPORTER_VERSION = "importer-v0.2-draft"
# v0.2: OHLC integrity validation (ported from user's prior project, which
# learned it in production): a candle with high<low, extremes that don't
# contain open/close, or non-positive prices is REJECTED — loudly logged,
# counted in import_log.n_bad, and left as a gap. Never repaired, never
# fabricated (gap-honesty rule).

TF_SECONDS = {"15m": 900, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}
NATIVE_TFS = {"15m": 900, "1H": 3600, "1D": 86400}
MAX_CANDLES_PER_REQ = 300
REQUEST_PAUSE_S = 0.15


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(product: str, granularity: int, start_ts: int, end_ts: int) -> list:
    url = (f"{API}/products/{product}/candles?granularity={granularity}"
           f"&start={_iso(start_ts)}&end={_iso(end_ts)}")
    req = urllib.request.Request(url, headers={"User-Agent": "snipersight/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        # parse_float=Decimal keeps venue prices exact end to end
        return json.loads(r.read().decode(), parse_float=Decimal)


def backfill(con, symbol: str, tf: str, start_ts: int, end_ts: int) -> dict:
    """Import [start_ts, end_ts) for a native timeframe. Returns import summary."""
    if tf not in NATIVE_TFS:
        raise ValueError(f"{tf} is not a native venue timeframe; use the aggregator")
    gran = NATIVE_TFS[tf]
    start_ts -= start_ts % gran
    now = int(time.time())
    end_ts = min(end_ts, now - now % gran)  # never import the developing candle (§5)

    from .runlog import get_logger
    seen: dict[int, tuple] = {}
    n_bad = 0
    cursor = start_ts
    while cursor < end_ts:
        chunk_end = min(cursor + MAX_CANDLES_PER_REQ * gran, end_ts)
        rows = _fetch(symbol, gran, cursor, chunk_end - 1)
        for t, lo, hi, op, cl, vol in rows:
            t = int(t)
            if not (start_ts <= t < end_ts):
                continue
            if not (hi >= lo and hi >= op and hi >= cl and lo <= op and lo <= cl
                    and lo > 0 and vol >= 0):
                n_bad += 1
                get_logger().warning(
                    f"REJECTED malformed candle {symbol} {tf} open_ts={t}: "
                    f"O={op} H={hi} L={lo} C={cl} V={vol} — excluded, becomes a "
                    f"gap (never repaired)")
                continue
            seen[t] = (str(op), str(hi), str(lo), str(cl), str(vol))
        cursor = chunk_end
        time.sleep(REQUEST_PAUSE_S)

    imported_at = int(time.time())
    con.executemany(
        "INSERT OR REPLACE INTO candles "
        "(symbol, tf, open_ts, open, high, low, close, volume, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(symbol, tf, t, *ohlcv, "coinbase", imported_at)
         for t, ohlcv in sorted(seen.items())])

    expected = range(start_ts, end_ts, gran)
    gaps = [t for t in expected if t not in seen]
    con.execute(
        "INSERT INTO import_log "
        "(symbol, tf, range_start, range_end, n_candles, n_gaps, gaps, source, run_at, n_bad) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (symbol, tf, start_ts, end_ts, len(seen), len(gaps),
         json.dumps(gaps[:200]), "coinbase", imported_at, n_bad))
    con.commit()
    return {"symbol": symbol, "tf": tf, "candles": len(seen), "gaps": len(gaps),
            "bad": n_bad}
