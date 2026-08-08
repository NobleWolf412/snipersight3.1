"""Retention — delete what nothing can read, and nothing else.

`docs/SPEC-persistence-retention.md` §5 names this file and demands one shape:
dry-run first, always; refuse to act without a flag; emit a fact recording what
went. That is implemented here for **one** target.

`--target runs` (engine_runs). Measured 2026-08-07 on the live store:

    rows                                     4,176,954
    produced 0 new facts                     4,089,688   97.9%
    run_ids any fact actually points at         86,155    2.1%

The table is telemetry, not evidence. It is also the largest single row count
in the database — larger than facts and candles together — because RunRecorder
appends one row per engine per symbol per timeframe per scan cycle whether or
not that run learned anything, and 97.9% of the time it learned nothing.

`--target facts` is deliberately **not** implemented. Fact pruning is governed
by the reference test in that spec's §3.3 and is a bigger, more careful job;
the flag exists so the omission is visible rather than looking like an
oversight.

    python prune.py --target runs                  # dry run, changes nothing
    python prune.py --target runs --apply          # deletes
    python prune.py --target runs --keep-days 30   # widen the debug window

Run it from `app/`, like everything else here.
"""
import argparse
import json
import sys
import time

from engine import store
from engine.runlog import get_logger

RETENTION_VERSION = "retention-v0.1-draft"

# The operational debugging window. Nothing reads a run row this old that is
# not already covered by one of the structural keeps below — but "I am looking
# at what happened last week" is a real use and costs almost nothing to serve.
DEFAULT_KEEP_DAYS = 7

# Delete in batches so a 4M-row prune never holds a write lock long enough to
# stall the scanner mid-cycle. The supervisor owns that process; a prune that
# makes it look hung is a prune that gets killed halfway.
BATCH = 25_000


def plan_runs(con, keep_days: int) -> dict:
    """What would go, and what each keep rule is protecting.

    Four keeps, and every one of them exists because something would break or
    a question would become unanswerable without it:

      referenced  a fact carries this run_id in `producer_run_id`. Deleting it
                  orphans the lineage — the fact could no longer say what
                  produced it, which is the one thing RunRecorder exists for.
      failed      status != PASS. 2 rows in 4.1M. The whole population of
                  things that went wrong is a rounding error; keeping it
                  forever is free and losing it is not recoverable.
      newest      the last run of each engine. `/api/overview` asks exactly
                  this question twice a minute (server.py:2144).
      recent      run_at inside the keep window.
    """
    cutoff = int(time.time()) - keep_days * 86_400

    con.execute("DROP TABLE IF EXISTS temp.keep_runs")
    con.execute("CREATE TEMP TABLE keep_runs (run_id TEXT PRIMARY KEY)")
    # One pass over facts rather than a correlated subquery per row: at 2.6M
    # facts and 4.2M runs the correlated form is the difference between
    # seconds and hours.
    con.execute(
        "INSERT OR IGNORE INTO temp.keep_runs (run_id) "
        "SELECT DISTINCT producer_run_id FROM facts "
        "WHERE producer_run_id IS NOT NULL AND producer_run_id != ''")
    referenced = con.execute("SELECT COUNT(*) FROM temp.keep_runs").fetchone()[0]

    where_delete = """
        status = 'PASS'
        AND run_at < ?
        AND (run_id = '' OR run_id NOT IN (SELECT run_id FROM temp.keep_runs))
        AND id NOT IN (SELECT MAX(id) FROM engine_runs GROUP BY engine)
    """
    total = con.execute("SELECT COUNT(*) FROM engine_runs").fetchone()[0]
    doomed = con.execute(
        "SELECT COUNT(*) FROM engine_runs WHERE" + where_delete, (cutoff,)).fetchone()[0]
    by_engine = con.execute(
        "SELECT engine, COUNT(*) FROM engine_runs WHERE" + where_delete +
        " GROUP BY engine ORDER BY 2 DESC", (cutoff,)).fetchall()

    return {
        "target": "runs",
        "keep_days": keep_days,
        "cutoff": cutoff,
        "rows_before": total,
        "referenced_run_ids": referenced,
        "deletable": doomed,
        "keeping": total - doomed,
        "by_engine": [{"engine": e, "rows": n} for e, n in by_engine],
        "where": where_delete,
    }


def _freelist_bytes(con) -> int:
    page = con.execute("PRAGMA page_size").fetchone()[0]
    free = con.execute("PRAGMA freelist_count").fetchone()[0]
    return page * free


def apply_runs(con, plan: dict) -> dict:
    """Delete in batches, then record the deletion as a fact.

    The fact matters more than it looks. Without it, a store that has been
    pruned is indistinguishable from a store whose scanner was down for the
    same period — the absence of rows reads as an outage, forever. A
    `retention` fact is the note saying the gap was chosen.
    """
    log = get_logger()
    freed_before = _freelist_bytes(con)
    removed = 0
    while True:
        cur = con.execute(
            "DELETE FROM engine_runs WHERE id IN ("
            "  SELECT id FROM engine_runs WHERE" + plan["where"] + " LIMIT ?)",
            (plan["cutoff"], BATCH))
        con.commit()
        if cur.rowcount <= 0:
            break
        removed += cur.rowcount
        log.info(f"RETENTION runs: {removed:,}/{plan['deletable']:,} deleted")

    after = con.execute("SELECT COUNT(*) FROM engine_runs").fetchone()[0]
    reclaimable = _freelist_bytes(con) - freed_before
    now = int(time.time())
    store.insert_fact(
        con,
        symbol="PORTFOLIO", tf="ALL", kind="retention",
        market_time=now, confirmed_at=now,
        algo_version=RETENTION_VERSION,
        payload={
            "target": "runs",
            "keep_days": plan["keep_days"],
            "cutoff": plan["cutoff"],
            "rows_before": plan["rows_before"],
            "rows_after": after,
            "removed": removed,
            "reclaimable_bytes": reclaimable,
        })
    con.commit()
    log.info(f"RETENTION runs complete: {removed:,} rows removed, "
             f"{after:,} kept, {reclaimable / 1e6:.0f} MB reclaimable "
             f"(VACUUM to return it to the filesystem)")
    return {"removed": removed, "rows_after": after, "reclaimable_bytes": reclaimable}


def _report(plan: dict) -> None:
    print(f"target        : engine_runs")
    print(f"keep window   : {plan['keep_days']} days")
    print(f"rows now      : {plan['rows_before']:,}")
    print(f"referenced    : {plan['referenced_run_ids']:,} run_ids carried by facts")
    print(f"would delete  : {plan['deletable']:,} "
          f"({plan['deletable'] / max(plan['rows_before'], 1) * 100:.1f}%)")
    print(f"would keep    : {plan['keeping']:,}")
    if plan["by_engine"]:
        print("\nby engine:")
        for row in plan["by_engine"][:20]:
            print(f"  {row['engine']:14s} {row['rows']:>12,}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, choices=("runs", "facts"))
    ap.add_argument("--apply", action="store_true",
                    help="actually delete. Without it this is a dry run.")
    ap.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS)
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    args = ap.parse_args(argv)

    if args.target == "facts":
        print("--target facts is not implemented. Fact pruning needs the "
              "reference test in docs/SPEC-persistence-retention.md §3.3 — "
              "a superseded fact that a retained setup was built from is NOT "
              "eligible, and nothing here checks that yet.", file=sys.stderr)
        return 2

    con = store.connect()
    plan = plan_runs(con, args.keep_days)
    if args.json:
        print(json.dumps({k: v for k, v in plan.items() if k != "where"}, indent=2))
    else:
        _report(plan)

    if not args.apply:
        print("\nDRY RUN — nothing deleted. Re-run with --apply to act.")
        return 0
    if plan["deletable"] == 0:
        print("\nNothing to delete.")
        return 0

    result = apply_runs(con, plan)
    print(f"\nDeleted {result['removed']:,} rows. {result['rows_after']:,} remain.")
    print(f"{result['reclaimable_bytes'] / 1e6:.0f} MB is now free space inside "
          f"the database file. SQLite reuses it; `VACUUM` returns it to the "
          f"filesystem but rewrites the whole 3.3 GB file and needs that much "
          f"free disk, so it is deliberately not run here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
