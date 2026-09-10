"""Why is the position slot held by a trade that has no exit? READ-ONLY.

    cd app
    python orphans.py                  # every orphan, then UNI in detail
    python orphans.py PF_UNIUSD        # a different symbol

SELECTs only. It writes nothing, emits no fact and calls no endpoint, so it is
safe against the live store while the scanner runs.

THE SHAPE OF THE FAULT. `risk.py` replays the account from exec facts under the
CURRENT `EXEC_VERSION` only. An approved intent whose exit was recorded under a
previous generation therefore reads as "approved, never closed": `ex is None`,
it joins `open_pos` with `exit_ts=None`, and `settle()` — which removes only
positions that HAVE an exit timestamp — can never release it. With
MAX_CONCURRENT at 1, one such intent rejects every later setup with
CONCURRENT_LIMIT(1) for as long as it sits there. Nothing ages it out.

That is by design for a genuinely open position: `walk_exit` returns None while
fewer than MAX_BARS bars exist past the fill, and that trade SHOULD hold the
slot. The defect is the case where the releasing fact can never arrive at all,
because nothing will run the engine that would write it.

WHAT THIS SCRIPT IS FOR: four causes produce that identical signature, and they
need different repairs. The queries below separate them.

    T4  the orphan set        one symbol, or a class that left together
    T3  universe state        ADMITTED or SHADOW means it is still scanned
    T2  engine_runs           did execsim run at all, and did it raise
    T1  gates and faults      quality-blocked, or throwing and swallowed

Read T2 first once you have the set. A run under the current version with
status PASS means execsim ran and declined to write — a live position, not an
orphan. An ERROR row is a swallowed exception (`pipeline.py` records the fault
and carries on, so the funnel never shows it). NO row at all means the symbol
never reached the engine, and T3 then says whether that is universe churn
(it left ADMITTED and SHADOW both) or the quality gate in T1, which skips
every engine for a symbol regardless of membership.

Written 2026-09-10 for a UNI intent approved on 24 August whose stop-out was
recorded under exec-v0.25 and absent under exec-v0.26. The bump that stranded
it is the same one `manual.py` protects its own book against by keeping the
previous version readable — the argument for this script is that the
simulator's work list does not.

The provisional-equity notice cannot see any of this: `rebuild.status` counts
`total` only from pairs with a run inside the scan-set window, so an orphaned
pair drops out of the denominator and `active` never goes True for it.
"""
import json
import sys

from engine import execsim, risk, store, universe


def orphans(con):
    """Approved intents with no exit fact under the current exec generation."""
    return con.execute(
        "SELECT DISTINCT r.symbol, r.tf, json_extract(r.payload,'$.setup_id') AS sid "
        "FROM facts r WHERE r.kind='risk' AND r.algo_version=? "
        "AND json_extract(r.payload,'$.decision') IN ('APPROVED','REDUCED') "
        "AND NOT EXISTS (SELECT 1 FROM facts e WHERE e.kind='exec' "
        "  AND e.algo_version=? "
        "  AND json_extract(e.payload,'$.setup_id')=sid) "
        "ORDER BY r.symbol, sid", (risk.RISK_VERSION, execsim.EXEC_VERSION)).fetchall()


def universe_state(con, needle):
    """Every member of the newest universe fact whose symbol matches."""
    row = con.execute(
        "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
        "ORDER BY confirmed_at DESC, id DESC LIMIT 1",
        (universe.UNIVERSE_VERSION,)).fetchone()
    if row is None:
        return None
    return [m for m in json.loads(row[0])["members"]
            if needle.upper() in m["symbol"].upper()]


def main(needle="UNI"):
    # `store.connect()` CREATES the file when it is missing, so a wrong working
    # directory would silently produce an empty store and a clean bill of
    # health for every check below. Run from `app/`.
    if not store.DB_PATH.exists():
        sys.exit(f"no store at {store.DB_PATH} — run this from app/")
    con = store.connect()
    print(f"exec={execsim.EXEC_VERSION}  risk={risk.RISK_VERSION}  "
          f"universe={universe.UNIVERSE_VERSION}\n")

    rows = orphans(con)
    print(f"T4  {len(rows)} approved intent(s) holding a slot with no "
          f"{execsim.EXEC_VERSION} exit:")
    for sym, tf, sid in rows:
        print(f"      {sym:<16} {tf:<4} {sid}")
    print("    One symbol points at that market; a set that left together is "
          "structural.\n")

    members = universe_state(con, needle)
    if members is None:
        print(f"T3  no universe fact under {universe.UNIVERSE_VERSION} at all.\n")
    else:
        print(f"T3  {needle} in the newest universe fact:")
        for m in members or [None]:
            print(f"      {m}" if m else "      ABSENT from members")
        print("    ADMITTED or SHADOW means it is still scanned every cycle, "
              "and universe churn is NOT the cause.\n")

    print(f"T2  execsim runs on {needle} (newest first):")
    runs = con.execute(
        "SELECT algo_version, status, n_new_facts, run_at FROM engine_runs "
        "WHERE engine='execsim' AND symbol LIKE ? "
        "ORDER BY run_at DESC LIMIT 12", (f"%{needle}%",)).fetchall()
    for r in runs:
        print("     ", *r)
    if not any(r[0] == execsim.EXEC_VERSION for r in runs):
        print(f"    -> NO run under {execsim.EXEC_VERSION}: it never reached "
              f"the engine. T3 and T1 say why.")
    print()

    for tbl, cols in (("pipeline_gates", "symbol, tf, gate"),
                      ("engine_faults", "symbol, tf, engine, error, times")):
        rows = con.execute(
            f"SELECT {cols} FROM {tbl} WHERE symbol LIKE ?",
            (f"%{needle}%",)).fetchall()
        print(f"T1  {tbl}:", [tuple(r) for r in rows] or "clean")
    print("    A QUALITY_BLOCKED gate skips EVERY engine for the symbol, "
          "whatever the universe says.\n")

    print(f"T5  {needle} exec facts by generation:")
    for r in con.execute(
            "SELECT algo_version, COUNT(*) FROM facts WHERE kind='exec' "
            "AND symbol LIKE ? GROUP BY algo_version ORDER BY algo_version",
            (f"%{needle}%",)):
        print("     ", *r)
    print("    A fact under every earlier generation but not this one means "
          "the orphan is new with this bump, not chronic.")
    con.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "UNI")
