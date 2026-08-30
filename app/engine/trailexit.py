"""Trail-only exits on the continuation cohort — does the exit verdict transfer? READ-ONLY.

WHY THE §1.6 REJECTION DOES NOT SETTLE THIS. The managed exit (partials +
breakeven + trail + time stop, SPEC-confirmed-entry §1.6) was rejected by its
own 2x2 gate — it moved the confirmed entry from -0.017 R to -0.171 R — and
execsim holds to SL/TP on the strength of that measurement. But that
measurement was taken on the FADE book: PULLBACK and REVERSAL both enter
counter-move, where the favourable excursion is the bounce off a level and a
trail gives back exactly the mean-reversion it harvested. It does not transfer
to the continuation cohort, whose entries buy strength inside an established
trend and whose MFE structure is the opposite shape — the winners are the
trades that keep going, which is the one case a trail exists for. Same exit
question, different excursion distribution, so it has to be asked again on
this cohort's own trades.

WHAT IS COMPARED, and why it is a clean pair. Both cells replay the SAME
trend-v setups through `abtest.run_variant` under the entry model their facts
recorded, so the fills are identical by determinism and every difference in R
is the exit and nothing else:

    hold    managed=False                      — execsim's own walk, SL/TP
    trail   partials=False, trail=True,        — breakeven at BE_TRIGGER_R,
            timestop=False                       trail armed at TRAIL_ACTIVATE_R,
                                                 distance TRAIL_DISTANCE_R;
                                                 no partials, no time stop

The trail parameters are abtest's §1.6 constants, deliberately unchanged: this
audition asks whether the REJECTED exit works HERE, not whether a re-tuned one
would — a re-tuned trail graded on the sample that tuned it is driftfade's
in-sample confession all over again. `_simulate` already isolates each
managed-exit component behind its own switch ("a bundle verdict is not a
component verdict"), so nothing in abtest changes and the recorded 2x2 cells
are untouched.

THE PRE-REGISTERED FLOOR, fixed before the first run: trail-only must BEAT the
hold baseline on the same cohort (paired per-trade delta, its clustered
interval clear of zero in the positive direction) AND the trail cell's own
clustered interval must clear zero — both on the house floors
(abtest.MIN_CLUSTERS symbols, edgestats.MIN_TRADES trades, enforced inside the
cluster bootstrap). Below that, the delta is reported with its interval and
the honest sentence is "this hasn't proven anything yet".

NOT A GATE. This module writes no facts, arms nothing, and appears in no
pipeline roster; deleting it changes no trade. If the floor is ever cleared,
a trail exit for a continuation playbook is a versioned execsim/setups
proposal to the operator — never a side effect of this file.

Usage (from app/):
  python -m engine.trailexit            # grade against the current book
  python -m engine.trailexit --json
"""
import json
import sqlite3

from . import store
from .abtest import recorded_entry_model, run_variant
from .importer import TF_SECONDS
from .trend import TREND_VERSION
# One cell shape across the continuation auditions: trendslice owns the
# clustered-interval cell (which itself defers to abtest._cluster_bootstrap
# and its floors), so the two tables cannot disagree about what a verdict
# needs.
from .trendslice import RESAMPLES, cell


def paired_deltas(hold_results, trail_results) -> tuple[list, int]:
    """Per-trade (trail R - hold R) for every setup filled in BOTH cells.

    Paired rather than cell-vs-cell because the trades are the same trades:
    identical fills, one exit rule apart, so the per-trade difference is the
    exit's whole effect and the between-trade variance cancels out of it.
    Returns (rows for the cluster bootstrap, n_unpaired) — a trade closed in
    one cell and OPEN in the other (a trail exits earlier, so it can resolve
    where a hold runs out of data) is counted, never silently dropped.
    """
    hold = {r["setup_id"]: r for r in hold_results if r.get("filled")}
    trail = {r["setup_id"]: r for r in trail_results if r.get("filled")}
    rows, unpaired = [], 0
    for sid in set(hold) | set(trail):
        h, t = hold.get(sid), trail.get(sid)
        if h is None or t is None:
            unpaired += 1
            continue
        rows.append({"symbol": h["symbol"],
                     "r": float(t["r"]) - float(h["r"])})
    return rows, unpaired


def verdict(hold_cell: dict, trail_cell: dict, delta_cell: dict) -> dict:
    """The pre-registered floor, applied. Pure so a test can pin it."""
    if not (hold_cell.get("sample_ok") and trail_cell.get("sample_ok")
            and delta_cell.get("sample_ok")):
        return {"call": "SAMPLE_TOO_SMALL",
                "detail": ("below the house floors — counts are facts, "
                           "verdicts need floors. "
                           "This hasn't proven anything yet.")}
    beats = (trail_cell["expectancy_r"] > hold_cell["expectancy_r"]
             and delta_cell["clears_zero"])
    clears = trail_cell["clears_zero"]
    if beats and clears:
        return {"call": "FLOOR_CLEARED",
                "detail": ("trail-only beats hold on the same cohort and its "
                           "clustered interval clears zero. This is a "
                           "measurement, not a promotion: a trail exit for "
                           "the continuation playbook is a versioned proposal "
                           "to the operator.")}
    return {"call": "NOT_PROVEN",
            "detail": ("the delta and its interval are reported above; "
                       "this hasn't proven anything yet.")}


def grade(con, symbols=None, tfs=None, resamples: int = RESAMPLES) -> dict:
    from . import venues
    from .universe import all_tracked_symbols
    if symbols is None:
        symbols = [s for s in all_tracked_symbols(con)
                   if not venues.is_reference_key(s)]
    tfs = tuple(tfs or TF_SECONDS)
    model = recorded_entry_model(con, symbols, tfs, TREND_VERSION)
    hold = run_variant(con, symbols, tfs, TREND_VERSION,
                       managed=False, entry_model=model)
    trail = run_variant(con, symbols, tfs, TREND_VERSION,
                        managed=False, entry_model=model,
                        partials=False, trail=True, timestop=False)

    def rows(results):
        return [{"symbol": r["symbol"], "r": r["r"]}
                for r in results if r.get("filled")]

    deltas, unpaired = paired_deltas(hold, trail)
    hold_cell = cell(rows(hold), resamples)
    trail_cell = cell(rows(trail), resamples)
    delta_cell = cell(deltas, resamples)
    return {
        "derived_at_analysis_time": True,    # no fact written, no gate armed
        "setup_version": TREND_VERSION,
        "entry_model": model,
        "cells": {"hold": hold_cell, "trail_only": trail_cell},
        "paired_delta": delta_cell,
        "unpaired": unpaired,
        "verdict": verdict(hold_cell, trail_cell, delta_cell),
        "floor": ("trail beats hold (paired delta clustered CI clear of zero, "
                  "positive) AND the trail cell's clustered CI clears zero, "
                  "both on the house floors"),
    }


def _print_cell(pad, name, c):
    if not c.get("n"):
        print(f"{pad}{name:<12} n=0")
        return
    if not c["sample_ok"]:
        print(f"{pad}{name:<12} n={c['n']} — SAMPLE TOO SMALL for an interval")
        return
    print(f"{pad}{name:<12} n={c['n']:<5} {c['expectancy_r']:+.4f} R · "
          f"ci[{c['cluster_ci_lo']:+.3f},{c['cluster_ci_hi']:+.3f}] over "
          f"{c['clusters']} symbols"
          f"{' CLEARS ZERO' if c['clears_zero'] else ''}")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rep = grade(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return 0
    print(f"trail-only exit vs hold — {rep['setup_version']}, entry model "
          f"{rep['entry_model']}")
    for name, c in rep["cells"].items():
        _print_cell("  ", name, c)
    _print_cell("  ", "delta", rep["paired_delta"])
    if rep["unpaired"]:
        print(f"  {rep['unpaired']} trade(s) resolved in only one cell — "
              f"counted, excluded from the pairing")
    v = rep["verdict"]
    print(f"\nVERDICT: {v['call']} — {v['detail']}")
    print(f"floor: {rep['floor']}")
    print("NOT A GATE. Evidence is recorded, not filtered on, until it has "
          "been graded (rule 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
