"""Canonical higher-timeframe candle aggregator (§19).

4H is built from 1H (UTC-aligned buckets: 00/04/08/12/16/20).
1W is built from 1D (weeks start Monday 00:00 UTC — crypto convention).
Aggregation is pure Decimal string arithmetic; a bucket is only emitted when
every expected source candle is present, so a gap in 1H never fabricates a 4H.
"""
import time
from decimal import Decimal

AGG_VERSION = "agg-v0.1-draft"
MONDAY_EPOCH = 345600  # 1970-01-05T00:00:00Z, first Monday after epoch

RULES = {
    "4H": {"source": "1H", "bucket": 14400, "n_expected": 4},
    "1W": {"source": "1D", "bucket": 604800, "n_expected": 7},
}


def _bucket_start(ts: int, tf: str) -> int:
    if tf == "1W":
        return ts - ((ts - MONDAY_EPOCH) % 604800)
    return ts - (ts % RULES[tf]["bucket"])


def aggregate(con, symbol: str, tf: str) -> dict:
    rule = RULES[tf]
    rows = con.execute(
        "SELECT open_ts, open, high, low, close, volume FROM candles "
        "WHERE symbol=? AND tf=? ORDER BY open_ts",
        (symbol, rule["source"])).fetchall()

    buckets: dict[int, list] = {}
    for row in rows:
        buckets.setdefault(_bucket_start(row[0], tf), []).append(row)

    now = int(time.time())
    out, skipped = [], 0
    for bstart, group in sorted(buckets.items()):
        if bstart + rule["bucket"] > now:  # developing bucket — never emit (§5)
            continue
        if len(group) != rule["n_expected"]:
            skipped += 1
            continue
        o = group[0][1]
        h = str(max(Decimal(r[2]) for r in group))
        l = str(min(Decimal(r[3]) for r in group))
        c = group[-1][4]
        v = str(sum(Decimal(r[5]) for r in group))
        out.append((symbol, tf, bstart, o, h, l, c, v, f"agg:{rule['source']}", now))

    con.executemany(
        "INSERT OR REPLACE INTO candles "
        "(symbol, tf, open_ts, open, high, low, close, volume, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", out)
    con.commit()
    return {"symbol": symbol, "tf": tf, "candles": len(out), "skipped_incomplete": skipped}
