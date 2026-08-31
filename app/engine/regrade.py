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


def run(con, now: int | None = None, *, resamples: int = RESAMPLES,
        beat=None) -> dict:
    """One full regrade pass, recorded. Read-only against the fact store.

    `beat` is an optional heartbeat callback, threaded down to the per-symbol
    replay loops — a full replay of the book takes minutes against the
    watchdog's dark-scanner threshold, and the retention sweep already set the
    precedent: beat inside the work "so a sweep is never mistaken for a hang".
    """
    from . import abtest, universe, venues
    from .pipeline import ALL_TFS
    _ensure(con)
    observed_at = int(time.time()) if now is None else int(now)
    # Reference series ('@'-keys such as BTCUSDT@binance-spot) are tracked —
    # they hold 1D candles, so all_tracked_symbols returns them — and they
    # have NO venue by contract: venues.venue_for raises on them, and the
    # replay prices trades through costs.profile_for. Unfiltered, the first
    # reference key raised BEFORE the row insert, so due() stayed true and
    # the "daily" regrade became an every-cycle crash loop. Same predicate
    # trendslice/trailexit use, for the same reason: the raise is the
    # contract keeping a borrowed order book away from money paths, and the
    # caller's job is not to ask what a reference series would fill at.
    symbols = [s for s in universe.all_tracked_symbols(con)
               if not venues.is_reference_key(s)]
    report = abtest.by_strategy(con, symbols, ALL_TFS,
                                versions=versions_to_grade(),
                                resamples=resamples, beat=beat)
    # Two writers CAN race this insert — `live.py --once` beside the CLI
    # `python -m engine.regrade` writes two rows for one day. Benign by
    # design: rows are append-only readings, last_run() takes the latest,
    # and due() only ever stretches the next interval.
    con.execute(
        "INSERT INTO strategy_regrades (observed_at, regrade_version, "
        "abtest_version, trustworthy, report) VALUES (?,?,?,?,?)",
        (observed_at, REGRADE_VERSION, report["version"],
         1 if report.get("trustworthy") else 0,
         json.dumps(report, sort_keys=True)))
    con.commit()
    return {"observed_at": observed_at, "trustworthy": report.get("trustworthy"),
            "report": report}


def maybe_run(con, now: int, log=None, beat=None) -> dict | None:
    """The scheduled entry point `live.cycle` calls. None means not due yet."""
    if not due(con, now):
        return None
    try:
        res = run(con, now, beat=beat)
    except Exception as exc:
        # A failed regrade must still COUNT AS AN ATTEMPT. Without this row,
        # due() stays true and the next cycle retries at cycle cadence — a
        # deterministic failure (the reference-key crash above was one)
        # turns the daily schedule into a per-cycle crash loop. The failure
        # is recorded untrustworthy with the error as its report, loudly
        # logged, and the next try waits the full interval. live.cycle's own
        # try/except stays as the belt for a failure inside THIS handler.
        _ensure(con)
        failure = {"error": f"{type(exc).__name__}: {exc}"}
        con.execute(
            "INSERT INTO strategy_regrades (observed_at, regrade_version, "
            "abtest_version, trustworthy, report) VALUES (?,?,?,?,?)",
            (int(now), REGRADE_VERSION, "unavailable", 0,
             json.dumps(failure, sort_keys=True)))
        con.commit()
        if log is not None:
            log.error(f"REGRADE failed and was recorded as an attempt "
                      f"({failure['error']}) — next try in "
                      f"{INTERVAL_SECONDS}s, not next cycle")
        return {"observed_at": int(now), "trustworthy": False,
                "report": failure}
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
