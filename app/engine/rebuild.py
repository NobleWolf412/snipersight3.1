"""Is the record being rebuilt? READ-ONLY, one reading, from `engine_runs`.

A version bump makes an engine re-derive every fact it owns under the new
label — symbol by symbol, cycle by cycle, over several hours — while the
account is REPLAYED from the simulated exits on every cycle. Until the
rebuild completes the equity and return move with no trade closing. On
2026-09-05 the operator watched that for a day as a slow loss, because
nothing on screen said a rebuild was underway. Loud-fallback rule: a degraded
reading must announce itself where it is read.

THE ONE AUTHORITY is `engine_runs`: the scanner records a run per (engine,
version, symbol, tf) each time it processes a pair. `total` is the pairs the
scanner has processed for this engine in the last `window_s` under ANY
version — the live scan set, which retires a market on its own a day after
the scanner stops visiting it. `done` is the pairs that have a run under the
CURRENT version. The rebuild is active while done < total. Nothing here is a
count of facts: a pair with zero setups is still done once its run is
recorded, and a fact count would call it unfinished forever.
"""
import time

from .setups import SETUP_VERSION

#: A pair the scanner has not visited in this long has left the scan set.
SCAN_SET_WINDOW_S = 24 * 3600


def status(con, *, engine: str = "setup", version: str = SETUP_VERSION,
           window_s: int = SCAN_SET_WINDOW_S, now: int | None = None) -> dict:
    now = int(time.time()) if now is None else int(now)
    total = con.execute(
        "SELECT COUNT(DISTINCT symbol || '|' || tf) FROM engine_runs "
        "WHERE engine=? AND run_at>=?", (engine, now - window_s)).fetchone()[0]
    done = con.execute(
        "SELECT COUNT(DISTINCT symbol || '|' || tf) FROM engine_runs "
        "WHERE engine=? AND algo_version=?", (engine, version)).fetchone()[0]
    last = con.execute(
        "SELECT MAX(run_at) FROM engine_runs WHERE engine=? AND algo_version=?",
        (engine, version)).fetchone()[0]
    done = min(done, total) if total else done
    return {"active": bool(total) and done < total, "engine": engine, "version": version,
            "done": int(done), "total": int(total),
            "last_run_at": None if last is None else int(last)}
