"""Per-symbol onboarding — backfill history, aggregate, run all fact engines.

Used both by the batch backfill (all symbols) and the live loop (onboarding a
newly-admitted universe entrant). Deterministic given the candle store.
"""
import time
from datetime import datetime, timezone

from . import importer, aggregator, pipeline

DAILY_SINCE = "2022-01-01"
HOURS_DAYS = 180
M15_DAYS = 30
# Kraken's native 5m endpoint is capped at 5,000 candles. Fourteen days stays
# within one bounded walk (4,032 bars) while still warming the scalp features.
M5_DAYS = 14
# How far inside its floor a stored series may START before we call it a HOLE
# rather than simply where the venue's own history begins. Two bars absorbs
# bucket alignment and the bar that was still forming when onboarding ran.
HISTORY_SLACK_BARS = 2
# Widest hole `reacknowledge_bucket` will close with ONE venue answer. Coinbase
# serves 300 buckets per request, so anything under that is a single honest
# answer; beyond it the repair is `repair_history`, not a stitched-together one.
REACK_MAX_SPAN_BARS = 200
# One roster, declared in `engine/pipeline.py`. This list used to be maintained
# separately from `live.ENGINES` and had fallen six engines behind it, so a
# symbol onboarded today received full history for the older engines and
# forward-only facts for `ranges, ma, momentum, volatility, volume, breakout` —
# two populations in one fact store with nothing marking which was which.
PER_SYMBOL_ENGINES = pipeline.PER_SYMBOL


def history_floor(tf: str, now: int) -> int:
    """Earliest timestamp worth requesting for a symbol with NO candles yet.

    Exists because `live.cycle` computed its incremental start as
    `MAX(open_ts) + granularity` and `MAX` is NULL on a cold symbol — so the
    fallback `or 0` asked the venue for history from **1970-01-01**. The
    adapter's no-forward-progress guard then aborted the walk somewhere in the
    1990s, before reaching any real data, and the symbol imported nothing.

    Measured damage before the fix: PF_XLMUSD failed this way on 24 consecutive
    cycles, logging **1,983,798 fabricated 15m gaps per run across 4,950 rows**
    and burning ~200 pointless HTTP requests per timeframe per cycle,
    indefinitely. Those gaps are worse than the wasted traffic: `/api/health`
    sums `import_log.n_gaps`, so a cold symbol silently poisons the data-health
    signal that the risk authority halts on.

    One floor, defined once, used by both onboarding and the live loop.
    """
    since_1d = int(datetime.strptime(DAILY_SINCE, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp())
    return {"1D": since_1d,
            "1H": now - HOURS_DAYS * 86400,
            "5m": now - M5_DAYS * 86400,
            "15m": now - M15_DAYS * 86400}.get(tf, since_1d)


def _native_first(con, symbol: str, tf: str | None = None):
    """Earliest NATIVE candle for a symbol, optionally within one timeframe.

    `source NOT LIKE 'agg:%'` throughout: a 4H bar is derived from 1H candles
    we already hold, so counting aggregates as history would let a symbol look
    warm on the strength of data it does not have.
    """
    sql = ("SELECT MIN(open_ts) FROM candles WHERE symbol=? "
           "AND source NOT LIKE 'agg:%'")
    args = [symbol]
    if tf is not None:
        sql += " AND tf=?"
        args.append(tf)
    return con.execute(sql, args).fetchone()[0]


def _native_count(con, symbol: str, tf: str) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM candles WHERE symbol=? AND tf=? "
        "AND source NOT LIKE 'agg:%'", (symbol, tf)).fetchone()[0]


def missing_history(con, symbol: str, now: int | None = None) -> list[str]:
    """Native timeframes whose stored history starts LATER than their floor.

    The hole `history_floor` cannot close. That fix repairs a timeframe with NO
    candles, because `MAX(open_ts)` is NULL and the live loop then falls through
    to the floor. It cannot repair a PARTIAL one: if onboarding wrote even a
    single 1H bar before failing, the watermark is not NULL, the live loop
    resumes from it, and the 180 days behind it are never requested again.

    Nothing else repairs it either. `universe.refresh` decides who needs
    backfilling from the DAILY candle count alone, so a symbol past
    MIN_DAILY_CANDLES is "warm" by that test no matter what its other
    timeframes hold — which is exactly how PF_XLMUSD sat for 24 cycles with 1D
    warm and both intraday timeframes at zero, in neither `warming` nor any
    other retry path.

    Two conditions, and BOTH must hold, because each alone has a false positive
    that matters:

      · the series starts more than HISTORY_SLACK_BARS after its floor — where
        that floor is itself raised to the symbol's OWN earliest native candle.
        A coin listed ten days ago has ten days of 15m and that is not a hole;
        without the anchor it would be flagged on every refresh forever.
      · no PRODUCTIVE import has ever asked for that window. If we already
        requested from the floor and the venue served candles, then the series
        starts where the venue's history starts, and asking again cannot
        conjure a bar that does not exist. `n_candles > 0` is what makes this
        self-terminating — the repair asks once and the row it writes retires
        the question — and it is also what stops the 1970 rows from counting as
        an answer: all 4,950 of them imported nothing.
    """
    now = int(time.time()) if now is None else now
    anchor = _native_first(con, symbol)
    out = []
    for tf, gran in importer.native_tfs(symbol).items():
        floor = history_floor(tf, now)
        if anchor is not None:
            floor = max(floor, anchor)
        first = _native_first(con, symbol, tf)
        if first is not None and first - floor <= HISTORY_SLACK_BARS * gran:
            continue
        if con.execute("SELECT 1 FROM import_log WHERE symbol=? AND tf=? "
                       "AND range_start<=? AND n_candles>0 LIMIT 1",
                       (symbol, tf, floor)).fetchone():
            continue
        out.append(tf)
    return out


def repair_history(con, symbol: str, tfs: list[str] | None = None,
                   now: int | None = None) -> dict:
    """Re-request the floor window for timeframes onboarding left short.

    Targeted on purpose. `onboard` would also close the hole, but it re-runs
    every engine over every timeframe for a symbol whose only problem may be one
    missing 1H window — and it is gated on `assert_market_ready`, which the very
    hole being repaired can make it fail. So: import first, and leave running
    the engines to the caller, who can see whether anything actually landed.

    Returns {tf: rows_ADDED}. Counting rows added rather than rows seen is the
    whole point: `importer.backfill` re-imports the entire window and REPLACEs
    what is already there, so its own `candles` figure is the window's size and
    says nothing about whether a hole closed.
    """
    now = int(time.time()) if now is None else now
    tfs = missing_history(con, symbol, now) if tfs is None else tfs
    gained = {}
    for tf in tfs:
        before = _native_count(con, symbol, tf)
        importer.backfill(con, symbol, tf, history_floor(tf, now), now)
        gained[tf] = _native_count(con, symbol, tf) - before
    if any(gained.values()):
        for tf in ("4H", "1W"):
            aggregator.aggregate(con, symbol, tf)
    return gained


def reacknowledge_bucket(con, symbol: str, tf: str, open_ts: int,
                         now: int | None = None) -> dict:
    """Re-ask the venue about one bucket that sits unvouched between two
    stored candles, so its answer lands in `import_log`.

    The overlap is the whole method. The steady-state import requests from
    the last stored bucket + 1, so a bucket the venue omitted at the head of
    that window was never inside a served span and nothing acknowledged it
    (importer-v0.7 stops that recurring; this repairs what it already left).
    Asking for one bucket either side puts the hole INSIDE the served span,
    where the importer's ordinary accounting records it as venue-quiet. The
    row it writes is a real venue answer, and it is the entire audit trail —
    `quality._known_gap_buckets` reads it directly, so nothing else is
    written and no second authority is created. Facts are untouched.

    Two checks, because the failure shape is quiet. The precondition — a
    stored candle on each side — is asserted before asking: called on the
    first bucket of a wider hole, the venue's answer starts one bucket later,
    the accounting is correct and acknowledges nothing, and the return dict
    is the only tell (auditor, 2026-09-02). Afterwards the row just written
    is read back: if the bucket is not in its listed gaps the venue served
    it, or served nothing at all, and either way this was not the repair the
    caller thinks it was — say so, never pass it off as one.
    """
    gran = importer.TF_SECONDS[tf]
    q = ("SELECT open_ts FROM candles WHERE symbol=? AND tf=? AND open_ts {} ? "
         "AND source NOT LIKE 'agg:%' ORDER BY open_ts {} LIMIT 1")
    if con.execute(q.format("=", "ASC"), (symbol, tf, open_ts)).fetchone():
        raise ValueError(f"{symbol} {tf} open_ts={open_ts} is stored; nothing to acknowledge")
    # Bracket with the nearest STORED candle each side, not the adjacent
    # bucket. The first live run stopped on LIGHTER-USD 07:35Z: its neighbour
    # 07:30Z was already an acknowledged quiet bucket, so the hole was a
    # one-bucket hole to quality and a two-bucket one to an adjacency check.
    # Asking from stored candle to stored candle puts every bucket between
    # them inside the served span, and the venue's one answer lists them all
    # — which is also the honest repair for a run of several.
    before = con.execute(q.format("<", "DESC"), (symbol, tf, open_ts)).fetchone()
    after = con.execute(q.format(">", "ASC"), (symbol, tf, open_ts)).fetchone()
    if not (before and after):
        raise ValueError(
            f"{symbol} {tf} open_ts={open_ts} has no stored candle on "
            f"{'both sides' if not (before or after) else 'one side'} — not a "
            f"hole between candles; a short history is `repair_history`")
    if after[0] - before[0] > REACK_MAX_SPAN_BARS * gran:
        raise ValueError(
            f"{symbol} {tf} open_ts={open_ts}: nearest stored candles are "
            f"{(after[0] - before[0]) // gran} buckets apart — wider than this "
            f"one-answer repair covers; that is `repair_history`")
    r = importer.backfill(con, symbol, tf, before[0], after[0] + gran, as_of=now)
    # Either outcome closes the hole: the venue lists it as quiet, or — the
    # rarer one — it now serves the bar it omitted first time, and the bar
    # is stored. Both are honest answers; only silence about it is not.
    row = con.execute(
        "SELECT gaps FROM import_log WHERE symbol=? AND tf=? "
        "ORDER BY id DESC LIMIT 1", (symbol, tf)).fetchone()
    import json
    listed = bool(row) and open_ts in {int(t) for t in json.loads(row[0])}
    filled = con.execute(
        "SELECT 1 FROM candles WHERE symbol=? AND tf=? AND open_ts=? "
        "AND source NOT LIKE 'agg:%'", (symbol, tf, open_ts)).fetchone() is not None
    if not (listed or filled):
        from .runlog import get_logger
        get_logger().warning(
            f"reacknowledge {symbol} {tf} open_ts={open_ts}: the venue's answer "
            f"neither served the bar nor listed it as quiet (served "
            f"{r['candles']} candle(s)) — NOT repaired; check the venue before "
            f"trusting this series")
    return {**r, "acknowledged": listed, "filled": filled,
            "repaired": listed or filled}


def backfill_history(con, symbol: str) -> dict:
    """Import native candles + build aggregates for one symbol.

    The per-timeframe starts come from `history_floor`, which is what makes its
    "one floor, defined once" claim true: onboarding and the live loop now read
    the same table, so a symbol imports the same history whichever path first
    touches it.
    """
    now = int(time.time())
    out = {}
    for tf in importer.native_tfs(symbol):
        r = importer.backfill(con, symbol, tf, history_floor(tf, now), now)
        out[tf] = r["candles"]
    for tf in ("4H", "1W"):
        aggregator.aggregate(con, symbol, tf)
    return out


def run_engines(con, symbol: str) -> None:
    """Run every per-symbol fact engine across all timeframes.

    The loop itself lives in `pipeline.run_symbol`, shared with `live.cycle` —
    one roster AND one loop, so a guard grown by either runner exists in both.
    What stays here is this runner's POLICY: onboarding a symbol whose market
    data fails the audit should fail the onboard, so a blocked symbol RAISES
    here where the live loop merely skips it and carries on.
    """
    r = pipeline.run_symbol(con, symbol)
    if r["blocked"]:
        raise RuntimeError(f"market data not ready for {symbol}: {r['blocked']}")


def onboard(con, symbol: str) -> dict:
    """Full onboarding for a new symbol: history + engines."""
    counts = backfill_history(con, symbol)
    run_engines(con, symbol)
    return {"symbol": symbol, "candles": counts}
