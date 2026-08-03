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
# How far inside its floor a stored series may START before we call it a HOLE
# rather than simply where the venue's own history begins. Two bars absorbs
# bucket alignment and the bar that was still forming when onboarding ran.
HISTORY_SLACK_BARS = 2
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
