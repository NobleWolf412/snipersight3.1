"""Scheduled strategy regrades — the committed script that reproduces the grades.

WHY THIS EXISTS. Every strategy verdict this project has acted on was produced
by a harness run that no committed script reproduces. `trend.py` says it in its
own voice: the -0.1500 R verdict is "NOT REPRODUCIBLE FROM THE STORE, noted
2026-08-10 ... 4,531 setups with no way to regrade them on a schedule. The
verdict is left" — and `pipeline.py` says the same about the record-only
engines: `abtest.by_strategy` "exists, it is not wired to anything, and
nothing runs it on a schedule." The consequence, measured on 2026-08-27: every
decisive number in the store was dated 2026-08-04 or earlier, which predates
the two August drift episodes (`driftfade.py`), so arguments about the current
book were being settled with pre-crash grades on samples that had since grown
by 60%. A grade that is not on a schedule is a snapshot wearing a verdict's
clothes.

WHAT RUNS. `abtest.by_strategy` over the tracked universe, on every setup
generation the store trades OR merely records — the traded book
(`setups.SETUP_VERSION`, `scalein.SCALE_VERSION`) and the measured-not-enabled
engines (`breakout`, `trend`), which emit setup facts that never become exec
facts and therefore can ONLY be graded by replay. Calibration runs inside
`by_strategy` and its verdict is stored alongside, so a regrade row can never
be quoted without the flag that says whether it may be believed.

WHAT IS RECORDED, AND WHERE. One row per run in `strategy_regrades`, the whole
`by_strategy` report as JSON. Its own table rather than fact rows: a regrade
is a READING of the book, not a market fact — a `regrade` fact series would
restate exec facts under a second name, the two-authorities defect `bias.py`
names. And not `engine_runs`, because that table is telemetry under retention
and a grade must outlive a sweep. The scanner is the only writer, which keeps
the quality_runs lesson: one authority, recorded where it acted.

WHAT THIS DELIBERATELY DOES NOT DO. It promotes nothing, disables nothing,
and changes no gate. A regrade that moved a policy by itself would be a
filter shipping without a human reading the interval. The output is the
number and its interval; what to DO about them stays a versioned code change.

Scheduling: `live.cycle` calls `maybe_run` once per INTERVAL_SECONDS,
fail-closed like the retention sweep — a failed regrade logs and never stops
the market being recorded. `python -m engine.regrade` runs one on demand.
"""
from __future__ import annotations

import json
import time

REGRADE_VERSION = "regrade-v0.1-draft"

#: Daily. The book grows by a handful of closed trades a day, so a tighter
#: cadence would regrade noise; a looser one recreates the stale-verdict
#: problem this module exists to close.
INTERVAL_SECONDS = 24 * 3600

#: Bootstrap resamples. The offline number (10k) rather than the request-path
#: 5k: this runs once a day off any request path, so the deeper interval is
#: free where it matters.
RESAMPLES = 10000


def _ensure(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS strategy_regrades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        observed_at INTEGER NOT NULL,
        regrade_version TEXT NOT NULL,
        abtest_version TEXT NOT NULL,
        trustworthy INTEGER NOT NULL,
        report TEXT NOT NULL)""")


def versions_to_grade() -> tuple:
    """Every setup generation worth regrading, traded or record-only.

    Imported lazily by the callers rather than frozen here, so a version bump
    in any engine flows through on the next run instead of grading a book that
    no longer exists — the exact staleness this module is for.
    """
    from . import breakout, scalein, trend
    from .setups import SETUP_VERSION
    return (SETUP_VERSION, scalein.SCALE_VERSION,
            breakout.BREAKOUT_VERSION, trend.TREND_VERSION)


def last_run(con) -> dict | None:
    _ensure(con)
    row = con.execute(
        "SELECT observed_at, regrade_version, abtest_version, trustworthy, "
        "report FROM strategy_regrades ORDER BY observed_at DESC, id DESC "
        "LIMIT 1").fetchone()
    if row is None:
        return None
    return {"observed_at": row[0], "regrade_version": row[1],
            "abtest_version": row[2], "trustworthy": bool(row[3]),
            "report": json.loads(row[4])}


def due(con, now: int) -> bool:
    prev = last_run(con)
    return prev is None or now - int(prev["observed_at"]) >= INTERVAL_SECONDS


def run(con, now: int | None = None, *, resamples: int = RESAMPLES) -> dict:
    """One full regrade pass, recorded. Read-only against the fact store."""
    from . import abtest, universe
    from .pipeline import ALL_TFS
    _ensure(con)
    observed_at = int(time.time()) if now is None else int(now)
    symbols = universe.all_tracked_symbols(con)
    report = abtest.by_strategy(con, symbols, ALL_TFS,
                                versions=versions_to_grade(),
                                resamples=resamples)
    con.execute(
        "INSERT INTO strategy_regrades (observed_at, regrade_version, "
        "abtest_version, trustworthy, report) VALUES (?,?,?,?,?)",
        (observed_at, REGRADE_VERSION, report["version"],
         1 if report.get("trustworthy") else 0,
         json.dumps(report, sort_keys=True)))
    con.commit()
    return {"observed_at": observed_at, "trustworthy": report.get("trustworthy"),
            "report": report}


def maybe_run(con, now: int, log=None) -> dict | None:
    """The scheduled entry point `live.cycle` calls. None means not due yet."""
    if not due(con, now):
        return None
    res = run(con, now)
    if log is not None:
        rep = res["report"]
        # REGRADE is an evidence prefix for the same reason AUTOTRADER is:
        # this line is the system's own record of what its strategies grade
        # at today, and an unlogged regrade is a silent one.
        for name, g in sorted((rep.get("strategies") or {}).items()):
            lo, hi = g.get("cluster_ci_lo"), g.get("cluster_ci_hi")
            interval = (f"cluster CI [{lo:+.4f}, {hi:+.4f}]"
                        if lo is not None and hi is not None
                        else "no clustered interval (sample too thin)")
            log.info(f"REGRADE {name}: n={g['n']} "
                     f"exp={g['expectancy_r']:+.4f}R {interval} "
                     f"clears_zero={g['clears_zero']}")
        if not rep.get("trustworthy"):
            log.warning("REGRADE untrustworthy: calibration failed or entry "
                        "models conflicted — numbers recorded, not believable")
    return res


def main():
    from . import store
    con = store.connect()
    try:
        res = run(con)
        rep = res["report"]
        print(f"regrade @ {res['observed_at']} trustworthy={res['trustworthy']}")
        for name, g in sorted((rep.get("strategies") or {}).items()):
            print(f"  {name:22} n={g['n']:>5} exp={g['expectancy_r']:+.4f}R "
                  f"cluster CI [{g.get('cluster_ci_lo')}, "
                  f"{g.get('cluster_ci_hi')}] clears_zero={g['clears_zero']}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
