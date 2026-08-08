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

`--target facts` (superseded derived generations). The spec's §3.3 reference
test: a derived fact goes only if its `algo_version` is not what the engine
writes today, the version string appears NOWHERE in engine source (a pinned
cross-generation read is a reader), the version last RAN at least
PRUNE_MIN_AGE_DAYS of wall clock ago, and no PERMANENT fact names it. Those
gates are why this is not a `DELETE ... WHERE algo_version != current`.

    python prune.py --target runs                  # dry run, changes nothing
    python prune.py --target runs --apply          # deletes
    python prune.py --target runs --keep-days 30   # widen the debug window
    python prune.py --target facts                 # dry run
    python prune.py --target facts --apply         # deletes

Run it from `app/`, like everything else here.
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from engine import store
from engine.runlog import get_logger

RETENTION_VERSION = "retention-v0.2-draft"
# v0.2: three audited holes closed before the first --apply ever ran.
# (1) A version string named anywhere in engine source is LIVE — swings.py
#     pins structure-v0.2 and liq-v0.2 as its scoring inputs, and v0.1
#     classified both as dead: deleting them would have silently changed
#     swing tiers under an unmoved swing version, the exact defect the store
#     exists to prevent, unrecoverably (the v0.2 engines no longer exist).
# (2) The 30-day guard now measures WALL CLOCK since the version last ran,
#     via engine_runs — not `confirmed_at`, which is market time and made a
#     generation bumped away from yesterday 67-76% "old enough" today.
# (3) The facts path retries through lock contention like the runs path,
#     and a prune interrupted partway still records a retention fact —
#     otherwise the deleted rows read as an outage forever.

# The operational debugging window. Nothing reads a run row this old that is
# not already covered by one of the structural keeps below — but "I am looking
# at what happened last week" is a real use and costs almost nothing to serve.
DEFAULT_KEEP_DAYS = 7

# Delete in batches so a 4M-row prune never holds a write lock long enough to
# stall the scanner mid-cycle. The supervisor owns that process; a prune that
# makes it look hung is a prune that gets killed halfway.
#
# 25,000 was the first choice and it lost the lock against a live scanner on
# the first real run — `database is locked` on batch one, with the default 5s
# busy timeout. The scanner writes continuously and holds the lock in bursts
# longer than that, so the prune has to be the patient party: smaller batches
# to shorten its own hold, a much longer timeout to outwait theirs, and a retry
# that treats contention as normal rather than as failure.
BATCH = 5_000
LOCK_TIMEOUT_MS = 60_000
LOCK_RETRIES = 8


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
        AND id NOT IN (SELECT MAX(id) FROM engine_runs GROUP BY engine, algo_version)
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


# kind -> the module constant that says what this engine writes TODAY. Read
# live rather than inferred: "newest version" cannot be computed by sorting
# strings, because `v0.9` sorts above `v0.13` and that single mistake would
# delete the current generation and keep the dead one.
#
# Only DERIVED kinds appear here. A kind absent from this map is never pruned,
# which is the safe direction for a kind nobody has classified yet.
DERIVED_KINDS = {
    "swing": ("swings", "SWING_VERSION"),
    "zone": ("zones", "ZONE_VERSION"),
    "structure": ("structure", "STRUCTURE_VERSION"),
    "liquidity": ("liquidity", "LIQ_VERSION"),
    "regime": ("regime", "REGIME_VERSION"),
    "range": ("ranges", "RANGES_VERSION"),
    "ma": ("ma", "MA_VERSION"),
    "momentum": ("momentum", "MOMENTUM_VERSION"),
    "volatility": ("volatility", "VOLATILITY_VERSION"),
    "volume": ("volume", "VOLUME_VERSION"),
    "cycle": ("cycles", "CYCLES_VERSION"),
}

# An A/B loser is evidence for as long as the comparison is live
# (SPEC-persistence-retention.md §4).
PRUNE_MIN_AGE_DAYS = 30

# Version strings of the derived kinds, as they appear in source — either
# quote style, because engine source already uses both. The stems here must
# cover every DERIVED_KINDS prefix (liq-, ranges-, cycles- differ from their
# kind names); test_prune_facts pins the invariant that every current
# version is caught by this scan, which fails on a missing stem or a format
# drift before either can cost a pinned generation.
_VERSION_IN_CODE = re.compile(
    r'["\']((?:swing|zone|structure|liq|regime|ranges|ma|momentum|volatility|'
    r'volume|cycles)-v[0-9][0-9.]*-[a-z]+)["\']')


def current_versions() -> dict:
    """What each derived engine writes right now, read from the engines."""
    import importlib
    out = {}
    for kind, (mod, const) in DERIVED_KINDS.items():
        m = importlib.import_module(f"engine.{mod}")
        out[kind] = getattr(m, const)
    return out


def versions_named_in_code() -> set:
    """Every derived-kind version string that appears anywhere in engine
    source. A version an engine NAMES is a version an engine READS — the
    current constants trivially, but also deliberate cross-generation pins
    like swings.PRIOR_STRUCTURE = "structure-v0.2-draft". "Not the current
    version" is not the same claim as "nothing reads it", and conflating the
    two was this tool's stop-ship defect.
    """
    named = set()
    for p in (Path(__file__).parent / "engine").glob("*.py"):
        named |= set(_VERSION_IN_CODE.findall(p.read_text(encoding="utf-8")))
    return named


def _last_ran_at(con, version: str) -> int | None:
    """Wall-clock time this algo_version last produced a run. engine_runs is
    the only clock in the store that is not market time — run_at is when the
    process actually executed. plan_runs deliberately preserves the newest
    row per (engine, algo_version) so this marker survives a runs prune.
    """
    try:
        row = con.execute(
            "SELECT MAX(run_at) FROM engine_runs WHERE algo_version=?",
            (version,)).fetchone()
    except sqlite3.OperationalError:
        return None          # no engine_runs table at all -> undatable, held
    return row[0] if row else None


def referenced_zone_ids(con) -> set:
    """Zone ids named by a PERMANENT fact.

    `zone_id` is `SYMBOL|TF|TYPE|TS` and carries **no version** — a setup
    written under `zone-v0.9` names the same string a `zone-v0.13` fact would.
    So the reference cannot be resolved by version at all: if any retained
    setup names a zone id, every generation of that zone stays. Substituting a
    current-generation zone with the same id would be the join hazard
    docs/AUDIT-setup-id-join-hazards.md exists about — same id, different
    top/bottom, silently different reconstruction.
    """
    ids = set()
    for (payload,) in con.execute(
            "SELECT payload FROM facts WHERE kind IN ('setup','order','exec','risk')"):
        # Substring test first: json.loads on every permanent fact is the
        # slowest part of the plan, and most payloads have no zone_id at all.
        if '"zone_id"' not in payload:
            continue
        try:
            z = json.loads(payload).get("zone_id")
        except ValueError:
            continue
        if z:
            ids.add(z)
    return ids


def plan_facts(con, min_age_days: int) -> dict:
    """Superseded derived generations that nothing reads and nothing names.

    Four gates, every one fail-closed:
      current   the version is not what the engine writes today
      named     the version string appears nowhere in engine source — a
                cross-generation pin (swings reads structure-v0.2) is a
                READER, whatever the version tags say
      age       the version last RAN at least min_age_days of wall clock
                ago (engine_runs.run_at); a version with no run history at
                all is held, because "we cannot date it" is not "it is old"
      reference for zones: no permanent fact names the zone_id
    """
    now = int(time.time())
    window = min_age_days * 86_400
    current = current_versions()
    named = versions_named_in_code()
    zone_ids = referenced_zone_ids(con)

    rows_before = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    doomed_ids, by_kind = [], {}
    held = {"by_reference": 0, "named_in_code": 0, "too_recent": 0,
            "undatable": 0}
    _age_cache: dict = {}

    for kind, live_version in current.items():
        rows = con.execute(
            "SELECT id, algo_version, payload FROM facts "
            "WHERE kind=? AND algo_version!=?",
            (kind, live_version)).fetchall()
        for fid, version, payload in rows:
            if version in named:
                held["named_in_code"] += 1
                continue
            if version not in _age_cache:
                _age_cache[version] = _last_ran_at(con, version)
            last_ran = _age_cache[version]
            if last_ran is None:
                held["undatable"] += 1
                continue
            if now - last_ran < window:
                held["too_recent"] += 1
                continue
            if kind == "zone" and zone_ids:
                try:
                    z = json.loads(payload).get("zone_id")
                except ValueError:
                    z = None
                if z in zone_ids:
                    held["by_reference"] += 1
                    continue
            doomed_ids.append(fid)
            by_kind.setdefault(kind, {}).setdefault(version, 0)
            by_kind[kind][version] += 1

    return {
        "target": "facts",
        "min_age_days": min_age_days,
        "rows_before": rows_before,
        "current_versions": current,
        "versions_named_in_code": sorted(named),
        "referenced_zone_ids": len(zone_ids),
        "held": held,
        "held_by_reference": held["by_reference"],
        "deletable": len(doomed_ids),
        "ids": doomed_ids,
        "by_kind": by_kind,
    }


def apply_facts(con, plan: dict) -> dict:
    """Delete in retried batches; ALWAYS leave a retention fact behind.

    The fact is written even when the prune stops partway through lock
    contention — a store missing rows with no note saying why reads as an
    outage forever, which this module's own runs path already refused to
    allow. `partial: true` on the payload is the honest version of stopping.
    """
    log = get_logger()
    con.execute(f"PRAGMA busy_timeout={LOCK_TIMEOUT_MS}")
    freed_before = _freelist_bytes(con)
    ids, removed, partial = plan["ids"], 0, False
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        try:
            cur = _retry_locked(
                con, lambda: con.execute(
                    "DELETE FROM facts WHERE id IN (%s)"
                    % ",".join("?" * len(chunk)), chunk))
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc) and "busy" not in str(exc):
                raise      # readonly store etc. — not resumable, say so by dying
            partial = True
            log.warning(f"RETENTION facts paused at {removed:,}/"
                        f"{len(ids):,}: {exc}. Deleted batches are "
                        f"committed; re-run to continue.")
            break
        removed += cur.rowcount
        log.info(f"RETENTION facts: {removed:,}/{len(ids):,} deleted")

    after = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    reclaimable = _freelist_bytes(con) - freed_before
    store.checkpoint_wal(con, log=log)
    now = int(time.time())
    payload = {
        "target": "facts",
        "min_age_days": plan["min_age_days"],
        "rows_before": plan["rows_before"],
        "rows_after": after,
        "removed": removed,
        "partial": partial,
        "held": plan["held"],
        "by_kind": {k: sorted(v) for k, v in plan["by_kind"].items()},
        "reclaimable_bytes": reclaimable,
    }
    # The retention fact goes through the same lock retry as the deletes —
    # the partial path exists precisely because the database was contended,
    # and writing the note about that on the still-contended database was
    # the one write with no retry (audit 2026-08-08). If even the retried
    # insert fails, the log line below is the fallback record: loud, with
    # the exact numbers, so the gap never reads as an unexplained outage.
    try:
        _retry_locked(con, lambda: store.insert_fact(
            con, symbol="PORTFOLIO", tf="ALL", kind="retention",
            market_time=now, confirmed_at=now,
            algo_version=RETENTION_VERSION, payload=payload))
    except sqlite3.OperationalError as exc:
        log.error(f"RETENTION facts: the retention fact itself could not be "
                  f"written ({exc}). {removed:,} deletions ARE committed; "
                  f"payload for the record: {json.dumps(payload, sort_keys=True)}")
    log.info(f"RETENTION facts complete: {removed:,} removed, {after:,} kept"
             + (" (PARTIAL — re-run to continue)" if partial else ""))
    return {"removed": removed, "rows_after": after, "partial": partial,
            "reclaimable_bytes": reclaimable}


def _retry_locked(con, op):
    """Run one write op through lock contention; the scanner is a legitimate
    concurrent writer, not an error condition."""
    delay = 0.5
    for attempt in range(LOCK_RETRIES):
        try:
            cur = op()
            con.commit()
            return cur
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc) and "busy" not in str(exc):
                raise
            con.rollback()
            if attempt == LOCK_RETRIES - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 8.0)


def _delete_batch(con, plan: dict) -> int:
    """One batch, retried through contention. Raises only if it never lands.

    The scanner is a legitimate concurrent writer, not an error condition —
    `database is locked` here means "try again in a moment", and a prune that
    treats it as fatal can only ever run while the app is stopped.
    """
    delay = 0.5
    for attempt in range(LOCK_RETRIES):
        try:
            cur = con.execute(
                "DELETE FROM engine_runs WHERE id IN ("
                "  SELECT id FROM engine_runs WHERE" + plan["where"] + " LIMIT ?)",
                (plan["cutoff"], BATCH))
            con.commit()
            return cur.rowcount
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc) and "busy" not in str(exc):
                raise
            con.rollback()
            if attempt == LOCK_RETRIES - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
    return 0


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
    con.execute(f"PRAGMA busy_timeout={LOCK_TIMEOUT_MS}")
    freed_before = _freelist_bytes(con)
    removed = 0
    while True:
        try:
            cur = _delete_batch(con, plan)
        except sqlite3.OperationalError as exc:
            # Every batch already committed stays committed, so stopping here
            # loses nothing and re-running resumes. Say so, rather than leaving
            # a half-finished prune looking like a crash.
            log.warning(f"RETENTION runs paused at {removed:,}/"
                        f"{plan['deletable']:,}: {exc}. Already-deleted rows "
                        f"are committed; re-run to continue.")
            break
        if cur <= 0:
            break
        removed += cur
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
    # A delete this size writes every touched page into the WAL, which reached
    # 966 MB once before and took /api/overview to 57 seconds (store.py:164).
    # Reclaim it here rather than waiting for the scanner's next quiet moment.
    store.checkpoint_wal(con, log=log)
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


def _report_facts(plan: dict) -> None:
    held = plan["held"]
    print(f"target        : facts (superseded derived generations)")
    print(f"min age       : {plan['min_age_days']} days of wall clock since the version last ran")
    print(f"facts now     : {plan['rows_before']:,}")
    print(f"zone ids named by a permanent fact : {plan['referenced_zone_ids']:,}")
    print(f"held — named in engine source      : {held['named_in_code']:,}")
    print(f"held — ran within the window       : {held['too_recent']:,}")
    print(f"held — no run history to date them : {held['undatable']:,}")
    print(f"held — referenced by a permanent   : {held['by_reference']:,}")
    print(f"would delete  : {plan['deletable']:,} "
          f"({plan['deletable'] / max(plan['rows_before'], 1) * 100:.1f}%)")
    if plan["by_kind"]:
        print("\nby kind (current version in brackets is never touched):")
        for kind in sorted(plan["by_kind"], key=lambda k: -sum(plan["by_kind"][k].values())):
            total = sum(plan["by_kind"][kind].values())
            print(f"  {kind:12s} {total:>10,}   [{plan['current_versions'][kind]}]")
            for version, n in sorted(plan["by_kind"][kind].items(), key=lambda kv: -kv[1]):
                print(f"      {version:26s} {n:>10,}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, choices=("runs", "facts"))
    ap.add_argument("--apply", action="store_true",
                    help="actually delete. Without it this is a dry run.")
    ap.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS)
    ap.add_argument("--min-age-days", type=int, default=PRUNE_MIN_AGE_DAYS,
                    help="facts only: an A/B loser is evidence while the "
                         "comparison is live (spec §4)")
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    args = ap.parse_args(argv)

    con = store.connect()
    if args.target == "facts":
        plan = plan_facts(con, args.min_age_days)
    else:
        plan = plan_runs(con, args.keep_days)

    if args.json:
        skip = ("where", "ids")
        print(json.dumps({k: v for k, v in plan.items() if k not in skip}, indent=2))
    elif args.target == "facts":
        _report_facts(plan)
    else:
        _report(plan)

    if not args.apply:
        print("\nDRY RUN — nothing deleted. Re-run with --apply to act.")
        return 0
    if plan["deletable"] == 0:
        print("\nNothing to delete.")
        return 0

    result = apply_facts(con, plan) if args.target == "facts" else apply_runs(con, plan)
    print(f"\nDeleted {result['removed']:,} rows. {result['rows_after']:,} remain.")
    print(f"{result['reclaimable_bytes'] / 1e6:.0f} MB is now free space inside "
          f"the database file. SQLite reuses it; `VACUUM` returns it to the "
          f"filesystem but rewrites the whole 3.3 GB file and needs that much "
          f"free disk, so it is deliberately not run here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
