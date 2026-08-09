"""Market-data importer (public endpoints, no credentials — §16).

Multi-venue since v0.3: the fetch is routed by `venues.venue_for(symbol)`, so
`BTC-USD` comes from Coinbase spot and `BTCUSDT` from Phemex perps. Native
granularities differ by venue — Coinbase serves 900/3600/86400 and forces 4H to
be aggregated, while Phemex serves 4H directly — so `native_tfs(symbol)` is the
authority rather than a module-level constant.
1W is built by the aggregator on both venues, never imported.
Deterministic re-import: candles are keyed (symbol, tf, open_ts) and REPLACEd
with identical venue values; prices kept as exact decimal strings via
json parse_float=Decimal so no float ever touches a price.
"""
import json
import time
import urllib.request
from decimal import Decimal
from datetime import datetime, timezone

from . import kraken, phemex, venues

API = "https://api.exchange.coinbase.com"
IMPORTER_VERSION = "importer-v0.3-draft"
# v0.3: venue-routed fetch and a truthful `source` column. It was hard-coded
# "coinbase", which would have labelled Phemex perp candles as spot data — and
# the quality audit's known-venue-gap allowances are keyed on source, so the
# mislabel would have applied Coinbase's gap rules to a venue that has none.
# v0.2: OHLC integrity validation (ported from user's prior project, which
# learned it in production): a candle with high<low, extremes that don't
# contain open/close, or non-positive prices is REJECTED — loudly logged,
# counted in import_log.n_bad, and left as a gap. Never repaired, never
# fabricated (gap-honesty rule).

TF_SECONDS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400,
              "1D": 86400, "1W": 604800}
NATIVE_TFS = {"5m": 300, "15m": 900, "1H": 3600, "1D": 86400}
MAX_CANDLES_PER_REQ = 300
REQUEST_PAUSE_S = 0.15
# import_log rows whose range_start predates 2000 are cold-start artefacts:
# before the pre-listing fix below (2026-07-30) a cold symbol asked for history
# from 1970 and logged every bucket since as a gap — 6.19bn fabricated entries
# against ~700k real ones. The rows are retained as evidence but nothing may
# treat their gap lists as acknowledgment. This constant was born in server.py's
# /api/health; it lives here now because the importer owns the gap record and
# three readers (health, quality, aggregator) need the same cutoff.
PRE_2000 = 946_684_800


def acknowledged_gaps(con, symbol: str, tf: str) -> set[int]:
    """Bucket timestamps the venue itself served nothing for, per import_log.

    LISTED-ONLY, deliberately. `n_gaps` is exact while `gaps` is capped at
    5000 entries per row, so a count can exceed its list — but a gap that was
    counted and not listed cannot be attributed to a specific bucket, and the
    caller (the aggregator, deciding whether a PARTIAL 4H/1W bar may be built)
    must not accept "some bucket somewhere was empty" as clearance for THIS
    one. quality._known_gap_buckets budgets on the count instead, and that is
    the right call there: excusing a symbol's gap tally is a different question
    from building a bar out of what remains.

    n_bad=0 ONLY. backfill() records a served-but-REJECTED malformed bar in
    the same gaps list as a bucket with no trades (gap-honesty: rejected data
    is a genuine hole), and the list does not say which entry is which. A
    rejected bar means REAL TRADES happened in that bucket, so treating its
    entry as "nobody traded" would clear a partial bar that omits real
    volume and possibly the window's true extremes. A row that rejected
    anything therefore acknowledges nothing (auditor finding, 2026-08-09;
    zero such rows exist on the live store today, which is why this is a
    guard and not a migration).
    """
    listed: set[int] = set()
    for (g,) in con.execute(
            "SELECT gaps FROM import_log WHERE symbol=? AND tf=? "
            "AND n_gaps>0 AND n_bad=0 AND range_start>=?",
            (symbol, tf, PRE_2000)):
        try:
            listed.update(int(t) for t in json.loads(g))
        except Exception:
            continue
    return listed


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(product: str, granularity: int, start_ts: int, end_ts: int) -> list:
    url = (f"{API}/products/{product}/candles?granularity={granularity}"
           f"&start={_iso(start_ts)}&end={_iso(end_ts)}")
    req = urllib.request.Request(url, headers={"User-Agent": "snipersight/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        # parse_float=Decimal keeps venue prices exact end to end
        return json.loads(r.read().decode(), parse_float=Decimal)


def native_tfs(symbol: str) -> dict:
    """Timeframes imported directly for THIS symbol.

    Phemex *can* serve 4H natively (see phemex.NATIVE_TFS) and Coinbase cannot.
    We deliberately import the same set from both and let the aggregator build
    4H everywhere: the aggregator is the single contract the quality audit
    checks, and a natively-fetched 4H would sit in the same (symbol, tf, open_ts)
    row the aggregator writes. Two writers for one bucket is how the two
    disagree at a gap and the audit starts reporting a conflict it cannot
    explain. Consistency is worth more here than one saved request.
    """
    return NATIVE_TFS


def _fetch_rows(symbol: str, tf: str, gran: int, start_ts: int, end_ts: int):
    """Normalised (open_ts, open, high, low, close, volume) for either venue.

    Coinbase returns [t, low, high, open, close, volume] positionally; Phemex
    returns dicts. Normalising here keeps the validation and storage below
    venue-agnostic — the alternative is two copies of the OHLC integrity check,
    which is exactly the sort of duplication that drifts apart.
    """
    try:
        v = venues.venue_for(symbol)
    except ValueError:
        v = venues.COINBASE_SPOT
    if v.key == "kraken-perp":
        for c in kraken.fetch_candles(symbol, tf, start_ts, end_ts):
            yield (int(c["open_ts"]), Decimal(c["open"]), Decimal(c["high"]),
                   Decimal(c["low"]), Decimal(c["close"]), Decimal(c["volume"]))
        return
    if v.is_perp:
        for c in phemex.fetch_candles(symbol, tf, start_ts, end_ts):
            yield (int(c["open_ts"]), Decimal(c["open"]), Decimal(c["high"]),
                   Decimal(c["low"]), Decimal(c["close"]), Decimal(c["volume"]))
        return
    cursor = start_ts
    while cursor < end_ts:
        chunk_end = min(cursor + MAX_CANDLES_PER_REQ * gran, end_ts)
        for t, lo, hi, op, cl, vol in _fetch(symbol, gran, cursor, chunk_end - 1):
            yield (int(t), op, hi, lo, cl, vol)
        cursor = chunk_end
        time.sleep(REQUEST_PAUSE_S)


def backfill(con, symbol: str, tf: str, start_ts: int, end_ts: int) -> dict:
    """Import [start_ts, end_ts) for a native timeframe. Returns import summary."""
    native = native_tfs(symbol)
    if tf not in native:
        raise ValueError(f"{tf} is not a native timeframe for {symbol}; use the aggregator")
    gran = native[tf]
    # `source` records WHICH venue served the bar. It was hard-coded "coinbase",
    # which would have silently labelled Phemex perp candles as spot data.
    try:
        src = venues.venue_for(symbol).key
    except ValueError:
        src = "coinbase"
    start_ts -= start_ts % gran
    now = int(time.time())
    end_ts = min(end_ts, now - now % gran)  # never import the developing candle (§5)

    from .runlog import get_logger
    seen: dict[int, tuple] = {}
    served: set = set()          # every bucket the venue returned, kept or not
    n_bad = 0
    for t, op, hi, lo, cl, vol in _fetch_rows(symbol, tf, gran, start_ts, end_ts):
        if not (start_ts <= t < end_ts):
            continue
        served.add(t)
        if not (hi >= lo and hi >= op and hi >= cl and lo <= op and lo <= cl
                and lo > 0 and vol >= 0):
            n_bad += 1
            get_logger().warning(
                f"REJECTED malformed candle {symbol} {tf} open_ts={t}: "
                f"O={op} H={hi} L={lo} C={cl} V={vol} — excluded, becomes a "
                f"gap (never repaired)")
            continue
        seen[t] = (str(op), str(hi), str(lo), str(cl), str(vol))

    imported_at = int(time.time())
    con.executemany(
        "INSERT OR REPLACE INTO candles "
        "(symbol, tf, open_ts, open, high, low, close, volume, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(symbol, tf, t, *ohlcv, src, imported_at)
         for t, ohlcv in sorted(seen.items())])

    # A GAP is a missing bucket INSIDE the span the venue actually served —
    # not every bucket in the range we happened to ask for. The distinction is
    # the same one S34 recorded for the fetch loop ("an empty window means
    # nothing listed yet in THIS range, not no data at all"), and it was never
    # applied to the gap accounting.
    #
    # Consequence measured 2026-07-30: a cold symbol asked for history from
    # 1970 and logged EVERY bucket since as a gap — 6,187,847,452 fabricated
    # gaps against 699,726 real ones, 99.99% of the metric. `/api/health` sums
    # this column and `risk.py` halts on a BLOCKED data-health verdict, so the
    # signal the risk authority trusts was almost entirely noise.
    #
    # Buckets before the first candle the venue ever served are PRE-LISTING, not
    # missing. Recording them as gaps claims the venue lost data it never had —
    # which is the mirror image of fabricating a candle, and just as dishonest.
    # The span is defined by what the venue SERVED, not by what we kept. A bar
    # the venue returned and we REJECTED as malformed is a genuine hole — that
    # is the gap-honesty rule at the top of this module, and a test pins it.
    # Only buckets the venue never returned at all are pre-listing.
    if served:
        first, last = min(served), max(served)
        expected = range(first, last + gran, gran)
        gaps = [t for t in expected if t not in seen]
        pre_listing = len([t for t in range(start_ts, first, gran)])
    else:
        # Nothing served at all. That is not a range full of gaps; it is a
        # symbol with no data in this window, and it is recorded as such.
        gaps = []
        pre_listing = len(range(start_ts, end_ts, gran))
    con.execute(
        "INSERT INTO import_log "
        "(symbol, tf, range_start, range_end, n_candles, n_gaps, gaps, source, run_at, n_bad) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        # gap-list cap raised from 200: truncation made real voids look
        # "unexplained" to the quality audit and re-wedged the fail-closed gate.
        (symbol, tf, start_ts, end_ts, len(seen), len(gaps),
         json.dumps(gaps[:5000]), src, imported_at, n_bad))
    con.commit()
    return {"symbol": symbol, "tf": tf, "candles": len(seen), "gaps": len(gaps),
            "bad": n_bad, "pre_listing": pre_listing}
