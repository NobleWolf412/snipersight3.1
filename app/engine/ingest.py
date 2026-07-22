"""Per-symbol onboarding — backfill history, aggregate, run all fact engines.

Used both by the batch backfill (all symbols) and the live loop (onboarding a
newly-admitted universe entrant). Deterministic given the candle store.
"""
import time
from datetime import datetime, timezone

from . import (store, importer, aggregator, swings, structure, zones,
               liquidity, regime, setups, execsim, scalein, cycles)

DAILY_SINCE = "2022-01-01"
HOURS_DAYS = 180
M15_DAYS = 30
PER_SYMBOL_ENGINES = (swings, structure, zones, liquidity, regime,
                      setups, execsim, scalein, execsim, cycles)


def backfill_history(con, symbol: str) -> dict:
    """Import native candles + build aggregates for one symbol."""
    now = int(time.time())
    since_1d = int(datetime.strptime(DAILY_SINCE, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp())
    plan = [("1D", since_1d), ("1H", now - HOURS_DAYS * 86400),
            ("15m", now - M15_DAYS * 86400)]
    out = {}
    for tf, start in plan:
        r = importer.backfill(con, symbol, tf, start, now)
        out[tf] = r["candles"]
    for tf in ("4H", "1W"):
        aggregator.aggregate(con, symbol, tf)
    return out


def run_engines(con, symbol: str) -> None:
    """Run every per-symbol fact engine across all timeframes."""
    for mod in PER_SYMBOL_ENGINES:
        if mod is scalein:
            scalein.run(con, symbol)
            continue
        for tf in ("15m", "1H", "4H", "1D", "1W"):
            mod.run(con, symbol, tf, importer.TF_SECONDS[tf])


def onboard(con, symbol: str) -> dict:
    """Full onboarding for a new symbol: history + engines."""
    counts = backfill_history(con, symbol)
    run_engines(con, symbol)
    return {"symbol": symbol, "candles": counts}
