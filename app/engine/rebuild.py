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

from .execsim import EXEC_VERSION
from .setups import SETUP_VERSION

#: A pair the scanner has not visited in this long has left the scan set.
SCAN_SET_WINDOW_S = 24 * 3600


def status(con, *, engine: str = "setup", version: str = SETUP_VERSION,
           window_s: int = SCAN_SET_WINDOW_S, now: int | None = None) -> dict:
    now = int(time.time()) if now is None else int(now)
    # WORK OWED IS WORK THE SCANNER WILL ACTUALLY DO. The 24h window is a
    # PROXY for "still in the scan set", and it is a slow one: a universe
    # change leaves the pairs it dropped inside the window for a full day. On
    # 2026-09-10 the swing-v0.11 rebuild finished every one of the 222 live
    # pairs and the notice still read 222/270, because 48 pairs on markets
    # that had just left the universe (AERO-USD, DASH-USD, ...) were counted
    # as owed and could never be paid. A provisional banner that stays up for
    # a day after the record is complete is the cry-wolf failure this module
    # exists to prevent, one direction over.
    #
    # So ask the universe directly and keep the window as the fallback: an
    # empty or unreadable scan set means "cannot tell", never "nothing owed".
    scan: set = set()
    try:
        from . import universe
        # A universe FACT is what makes the scan set real. Without one
        # `current_symbols` falls back to the seed pair, which is a default,
        # not a measurement — filtering on it would report a fresh store as
        # owing nothing. The window is the honest answer there.
        if con.execute("SELECT 1 FROM facts WHERE kind='universe' AND "
                       "algo_version=? LIMIT 1",
                       (universe.UNIVERSE_VERSION,)).fetchone():
            scan = set(universe.scan_symbols(con))
    except Exception:
        scan = set()
    if scan:
        marks = ",".join("?" for _ in scan)
        where, args = f" AND symbol IN ({marks})", tuple(sorted(scan))
    else:
        where, args = "", ()
    total = con.execute(
        "SELECT COUNT(DISTINCT symbol || '|' || tf) FROM engine_runs "
        "WHERE engine=? AND run_at>=?" + where,
        (engine, now - window_s, *args)).fetchone()[0]
    # The SAME window and the same scan set as `total`. Counted all-time,
    # `done` included pairs the scanner stopped visiting — 114 retired setup
    # pairs and 42 execsim pairs already carried current-version runs on
    # 2026-09-10 — and `min(done, total)` then reported complete while live
    # pairs were still unrebuilt. That is the exact way the PROVISIONAL
    # notice went quiet early on 09-05.
    done = con.execute(
        "SELECT COUNT(DISTINCT symbol || '|' || tf) FROM engine_runs "
        "WHERE engine=? AND algo_version=? AND run_at>=?" + where,
        (engine, version, now - window_s, *args)).fetchone()[0]
    last = con.execute(
        "SELECT MAX(run_at) FROM engine_runs WHERE engine=? AND algo_version=?",
        (engine, version)).fetchone()[0]
    done = min(done, total) if total else done
    return {"active": bool(total) and done < total, "engine": engine, "version": version,
            "done": int(done), "total": int(total),
            "last_run_at": None if last is None else int(last)}


#: The engines the ACCOUNT is replayed from, in the order a rebuild reaches
#: them. `setups` decides which trades exist; `execsim` decides how they
#: settled, and `risk` replays equity, the daily halt and the same-side
#: governor off those settlements.
#:
#: These are RUNLOG labels, not module names, and the two differ: execsim
#: records its runs as "execsim" while its facts and version are tagged "exec".
#: Writing "exec" here is not an error anything raises — `status()` finds no
#: runs, reports total=0, and therefore active=False, so the notice stays
#: silent in exactly the case it exists for. Caught in testing on 2026-09-07;
#: `test_rebuild_status.py` now pins every label against engine_runs.
ACCOUNT_ENGINES = (("setup", lambda: SETUP_VERSION),
                   ("execsim", lambda: EXEC_VERSION))


def account_status(con, *, window_s: int = SCAN_SET_WINDOW_S, now=None) -> dict:
    """The one reading behind the provisional-equity notice.

    `status()` defaults to the SETUP engine, and that default was the whole
    notice until 2026-09-07: an exec-only version bump rebuilt 879 settlements
    with the screen saying the record was complete. Same failure the module was
    written for on 2026-09-05, one engine over — which is the argument for
    asking about every engine the account is replayed from rather than the one
    that happened to bump first.

    Returns the ACTIVE rebuild if there is one, preferring the engine furthest
    upstream, because that is the one whose completion the others are waiting
    on. With nothing rebuilding it returns the setup reading, so the shape the
    UI reads is always present.

    A SECOND WAY THE BOOK IS EMPTY, which `status()` alone reports as calm:
    `total` counts only runs inside the scan-set window, so if the version is
    bumped while the scanner is down — or it stays down past the window — then
    total is 0, `active` is False, and the notice hides for precisely the state
    it exists to announce. So an engine with NO runs under the current version
    but runs under some earlier one is provisional too: its facts are a
    generation the account cannot read yet, whether or not anything is
    currently working on them.
    """
    readings = []
    for engine, version_of in ACCOUNT_ENGINES:
        version = version_of()
        r = status(con, engine=engine, version=version,
                   window_s=window_s, now=now)
        if not r["active"] and r["done"] == 0:
            had = con.execute(
                "SELECT 1 FROM engine_runs WHERE engine=? AND algo_version<>? "
                "LIMIT 1", (engine, version)).fetchone()
            if had:
                # `total` stays as measured — it is the honest count of the
                # live scan set, which may genuinely be 0 while the scanner is
                # down. The UI renders "0 of 0"; the sentence beside it is what
                # carries the meaning, and the alternative is silence.
                r = {**r, "active": True, "idle": True}
        readings.append(r)
    return next((r for r in readings if r["active"]), readings[0])
