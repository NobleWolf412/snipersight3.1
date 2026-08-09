"""Canonical higher-timeframe candle aggregator (§19).

4H is built from 1H (UTC-aligned buckets: 00/04/08/12/16/20).
1W is built from 1D (weeks start Monday 00:00 UTC — crypto convention).
Aggregation is pure Decimal string arithmetic. A bucket is emitted only when
every source candle it lacks is one the venue itself acknowledged serving
nothing for — so a gap in 1H never fabricates a 4H, and an hour in which
nobody traded no longer deletes the three hours in which somebody did.
"""
import time
from decimal import Decimal

from . import importer

AGG_VERSION = "agg-v0.2-draft"
# v0.2: acknowledged-partial buckets. v0.1 emitted a bucket only when every
# source candle was present, treating "nobody traded that hour" and "the
# import failed" as the same absence. On thin markets that discarded more
# bars than it kept — measured 2026-08-08: BICO-USD had 621 4H windows with
# real trading inside them skipped against 479 built (1,442 real hours
# thrown away); LSETH-USD 662 skipped vs 164 built; every one of 93 symbols
# affected, mildly on 1W. The two absences were distinguishable all along:
# import_log records, per (symbol, tf), every bucket the venue served
# nothing for (gap-honesty rule, importer.backfill). A bucket may now be
# built from the candles that exist iff every missing source bucket is in
# that record — the bar then contains exactly the trades the venue reported
# for the window, which is what the venue's own native bar would hold.
# A missing bucket that is NOT acknowledged (never fetched, fetch failed,
# truncated out of the 5000-entry list, or logged by a quarantined pre-2000
# cold-start row) still blocks the bucket: nothing is ever fabricated.
# Pre-listing windows stay unbuilt for free — pre-listing buckets are
# excluded from the gap record at import, so they are never acknowledged.
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
    src_sec = importer.TF_SECONDS[rule["source"]]
    rows = con.execute(
        "SELECT open_ts, open, high, low, close, volume FROM candles "
        "WHERE symbol=? AND tf=? ORDER BY open_ts",
        (symbol, rule["source"])).fetchall()

    buckets: dict[int, list] = {}
    for row in rows:
        buckets.setdefault(_bucket_start(row[0], tf), []).append(row)

    now = int(time.time())
    # Loaded lazily: most calls on a liquid symbol see only complete buckets,
    # and the acknowledgment set costs a JSON parse per import_log row.
    acknowledged: set[int] | None = None
    out, skipped = [], 0
    for bstart, group in sorted(buckets.items()):
        if bstart + rule["bucket"] > now:  # developing bucket — never emit (§5)
            continue
        present = {r[0] for r in group}
        slots = range(bstart, bstart + rule["bucket"], src_sec)
        if not present.issubset(slots):
            # A misaligned source candle (open_ts off the grid) would land in
            # H/L/V — and as the CLOSE, if it sorts last — of a bar whose slot
            # arithmetic never saw it. Never build over one; the DATA-stage
            # alignment audit (OHLC_INVARIANT_FAILURE) reports the candle
            # itself. An earlier draft claimed the missing-slot check below
            # caught this; it does not when the stray sits BESIDE aligned
            # candles, which is why this guard is code and not a comment.
            skipped += 1
            continue
        if len(group) != rule["n_expected"]:
            # Partial bucket. Build it ONLY if every missing slot is a bucket
            # the venue acknowledged serving nothing for — see AGG_VERSION.
            missing = [t for t in slots if t not in present]
            if acknowledged is None:
                acknowledged = importer.acknowledged_gaps(
                    con, symbol, rule["source"])
            if any(t not in acknowledged for t in missing):
                skipped += 1
                continue
        o = group[0][1]
        h = str(max(Decimal(r[2]) for r in group))
        l = str(min(Decimal(r[3]) for r in group))
        c = group[-1][4]
        v = str(sum(Decimal(r[5]) for r in group))
        out.append((symbol, tf, bstart, o, h, l, c, v, f"agg:{rule['source']}", now))

    # A bar that CHANGES CONTENT after emission is legal here for the first
    # time — a late-served source candle can complete (or extend) a bucket
    # previously built partial — and it must not be silent (loud-fallback
    # rule): facts downstream were derived from the bar being replaced, and
    # they stay in the store beside recomputes from the new one. Under v0.1
    # every emitted bar was a pure function of a complete, immutable group,
    # so this comparison would have been dead code.
    existing = {r[0]: tuple(map(str, r[1:6])) for r in con.execute(
        "SELECT open_ts, open, high, low, close, volume FROM candles "
        "WHERE symbol=? AND tf=?", (symbol, tf))}
    rewritten = [o[2] for o in out
                 if o[2] in existing and existing[o[2]] != tuple(o[3:8])]
    if rewritten:
        from .runlog import get_logger
        get_logger().warning(
            f"AGGREGATE REWRITE {symbol} {tf}: {len(rewritten)} previously "
            f"emitted bar(s) changed content — late source candles arrived "
            f"for buckets {rewritten[:5]}{'…' if len(rewritten) > 5 else ''}; "
            f"facts derived from the old bars remain in the store")
    con.executemany(
        "INSERT OR REPLACE INTO candles "
        "(symbol, tf, open_ts, open, high, low, close, volume, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", out)
    con.commit()
    return {"symbol": symbol, "tf": tf, "candles": len(out),
            "skipped_incomplete": skipped, "rewritten": len(rewritten)}
