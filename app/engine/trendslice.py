"""Trend continuation sliced by volatility state x ladder alignment. READ-ONLY.

THE HYPOTHESIS, and it was written down before this module ran. The 2026-08-04
grade in `engine/bias.py` measured the TREND_CONTINUATION replay at -0.1498 R
with an interval entirely below zero, and filtering it to WITH-ladder trades
moved it to -0.0639 R, CI [-0.182, +0.058] — from proven-losing to unproven,
predicted in advance and worth +0.086 R/trade. The obvious next cut, PREDICTED
HERE BEFORE THE FIRST RUN of this module: a continuation entry needs the market
to actually be going somewhere, so the WITH cohort should separate further on
the volatility state at entry. The pre-registered primary cell is
(EXPANSION or BREAKOUT) x WITH — the ladder agrees AND the tape is moving —
and it is the only cell in this table that may ever decide anything.

ONE AUTHORITY FOR THE STATE. The volatility reading is NOT re-derived here from
ATR_REGIME/SQUEEZE facts: `market_context.snapshot` already owns the canonical
fold (BREAKOUT / COMPRESSION / EXPANSION / UNSTABLE / the base regime), so this
module calls it as-of each setup's `confirmed_at` and takes the state it emits.
A second mapping of the same facts, however faithful today, is the fill-model
disease abtest paid four versions of tuition for — one fold, called by both the
live surface and this audition.

ONE EXECUTION AUTHORITY. Outcomes come from `abtest.run_variant` over the
trend cohort's own version, under the entry model its facts recorded
(`recorded_entry_model`) — the replay path `test_abtest` pins to execsim trade
by trade against the live store. Nothing here fills, walks or costs a trade
itself.

AS-OF DISCIPLINE. Both slices are read at the setup's `confirmed_at` — the
moment the trade became knowable. The ladder reading uses `bias.load(...)
.reading(as_of)` (convention 3: `confirmed_at`, never `market_time`), and the
snapshot's own `_latest` reads only facts confirmed at or before that instant.

MULTIPLE-COMPARISONS HONESTY. This table holds one pre-registered cell and a
grid of exploratory ones (state x alignment is ~30 cells). Some cell somewhere
looking significant is expected by chance — the same sentence bias.py wrote
about its 5x5x4 pass — so every non-primary cell is labelled exploratory in
the output and none of them may promote anything. A verdict is only reported
where the floors clear; below them the counts are printed and nothing else,
because counts are facts and verdicts need floors.

NOT A GATE. This module writes no facts, arms nothing, and appears in no
pipeline roster; deleting it changes no trade. If the primary cell ever clears
its floor, enabling the trend engine under a WITH+EXPANSION policy is a
versioned proposal to the operator — five tags move and the forward record
restarts — never a side effect of this file.

Usage (from app/):
  python -m engine.trendslice            # grade against the current book
  python -m engine.trendslice --json
"""
import json
import sqlite3

from . import bias, market_context, store
# The clustered interval and its floors are the harness's own, imported rather
# than restated: `abtest.MIN_CLUSTERS` (>= 8 symbols or the resample describes
# two markets, not a strategy) and `edgestats.MIN_TRADES` (>= 10 trades or the
# interval describes those trades, not the system) both gate inside
# `_cluster_bootstrap`, which returns None below either — so a cell under the
# floors structurally cannot produce a verdict here.
from .abtest import (MIN_CLUSTERS, _cluster_bootstrap, recorded_entry_model,
                     run_variant)
from .edgestats import MIN_TRADES
from .importer import TF_SECONDS
from .trend import TREND_VERSION

#: THE PRE-REGISTERED PRIMARY CELL, fixed before the first run (see the module
#: docstring for the prediction and the bias.py measurement behind it).
#: EXPANSION is high-ATR-regime plus a recent structural break; BREAKOUT is a
#: validated breakout release — both are market_context's words for "the tape
#: is actually moving", which is the condition a CONTINUATION entry is supposed
#: to need. Everything outside this cell is exploratory.
PRIMARY_STATES = ("EXPANSION", "BREAKOUT")
PRIMARY_ALIGNMENT = "WITH"

#: Same resample count as abtest.by_strategy, so the two surfaces cannot
#: disagree about an interval for want of a knob.
RESAMPLES = 10000


def is_primary(state: str | None, alignment: str | None) -> bool:
    """Membership in the one pre-registered cell. Pure, so a test can pin the
    registration rather than trust the prose."""
    return state in PRIMARY_STATES and alignment == PRIMARY_ALIGNMENT


def cell(rows, resamples: int = RESAMPLES) -> dict:
    """One cell's honest summary: counts always, verdict only above the floors.

    `clears_zero` follows abtest.by_strategy's convention — the CLUSTERED lower
    bound above zero, the positive direction only, because the floor this
    audition pre-registered is "entirely above zero". A cell entirely BELOW
    zero is visible from the printed interval; it is not dressed as a finding.
    """
    n = len(rows)
    if not n:
        return {"n": 0, "sample_ok": False}
    rs = [float(x["r"]) for x in rows]
    cb = _cluster_bootstrap(rows, resamples)
    return {
        "n": n,
        "expectancy_r": round(sum(rs) / n, 4),
        "win_pct": round(100 * sum(1 for r in rs if r > 0) / n, 1),
        "clusters": None if cb is None else cb["clusters"],
        "cluster_ci_lo": None if cb is None else round(cb["ci_lo"], 4),
        "cluster_ci_hi": None if cb is None else round(cb["ci_hi"], 4),
        "cluster_p_gt_zero": None if cb is None else cb["p_gt_zero"],
        "clears_zero": bool(cb and cb["ci_lo"] > 0),
        "sample_ok": cb is not None,
    }


def _trend_setups(con, symbols, tfs) -> dict:
    """setup_id -> {direction, confirmed_at, symbol, tf} for the trend cohort.

    The same VALIDATED, entry-bearing population run_variant replays, read the
    same way, so the annotation below can never describe a trade the replay
    did not take.
    """
    out = {}
    for symbol in symbols:
        for tf in tfs:
            for r in store.get_facts(con, symbol, tf, "setup", TREND_VERSION):
                p = json.loads(r["payload"])
                if p.get("state") != "VALIDATED" or not p.get("entry"):
                    continue
                out[p["setup_id"]] = {"direction": p["direction"],
                                      "confirmed_at": r["confirmed_at"],
                                      "symbol": symbol, "tf": tf}
    return out


def collect(con, symbols=None, tfs=None) -> dict:
    """Replay the trend cohort and stamp each filled trade with its two slices.

    Read-only over the store, derived at analysis time — no fact is written and
    no gate is armed.
    """
    from . import venues
    from .universe import all_tracked_symbols
    if symbols is None:
        # Reference series ('@'-keys) have no venue by contract and the replay
        # prices trades, so they are filtered here rather than by loosening
        # venues.venue_for's raise.
        symbols = [s for s in all_tracked_symbols(con)
                   if not venues.is_reference_key(s)]
    tfs = tuple(tfs or TF_SECONDS)
    setups = _trend_setups(con, symbols, tfs)
    model = recorded_entry_model(con, symbols, tfs, TREND_VERSION)
    results = run_variant(con, symbols, tfs, TREND_VERSION,
                          managed=False, entry_model=model)
    rows, missed, unjoined = [], 0, 0
    bias_cache: dict = {}
    for res in results:
        if not res.get("filled"):
            missed += 1
            continue
        s = setups.get(res["setup_id"])
        if s is None:
            unjoined += 1                     # counted, never silently dropped
            continue
        as_of = s["confirmed_at"]
        key = (s["symbol"], s["tf"])
        if key not in bias_cache:
            bias_cache[key] = bias.load(con, s["symbol"], s["tf"])
        reading = bias_cache[key].reading(as_of)
        align = bias.alignment(reading["composite"], s["direction"])
        snap = market_context.snapshot(con, s["symbol"], s["tf"], as_of=as_of)
        rows.append({"symbol": s["symbol"], "tf": s["tf"], "r": res["r"],
                     "t": as_of, "direction": s["direction"],
                     "state": snap["regime"], "alignment": align,
                     "data_status": snap["data_status"]})
    return {"rows": rows, "missed": missed, "unjoined": unjoined,
            "entry_model": model, "setup_version": TREND_VERSION}


def grade(con, symbols=None, tfs=None, resamples: int = RESAMPLES) -> dict:
    data = collect(con, symbols=symbols, tfs=tfs)
    rows = data["rows"]

    def pick(**want):
        out = []
        for x in rows:
            ok = True
            for k, v in want.items():
                got = x.get(k)
                ok = ok and (got in v if isinstance(v, tuple) else got == v)
            if ok:
                out.append(x)
        return out

    primary_rows = [x for x in rows
                    if is_primary(x["state"], x["alignment"])]
    primary = cell(primary_rows, resamples)

    exploratory: dict = {}
    states = sorted({x["state"] for x in rows})
    aligns = [a for a in bias.ALIGNMENTS]
    for st in states:
        exploratory[f"state:{st}"] = cell(pick(state=st), resamples)
    for al in aligns:
        exploratory[f"alignment:{al}"] = cell(pick(alignment=al), resamples)
    for st in states:
        for al in aligns:
            grid = pick(state=st, alignment=al)
            if grid:
                exploratory[f"{st} x {al}"] = cell(grid, resamples)

    floor_met = bool(primary.get("sample_ok") and primary.get("clears_zero"))
    return {
        "derived_at_analysis_time": True,     # no fact written, no gate armed
        "setup_version": data["setup_version"],
        "entry_model": data["entry_model"],
        "n_closed": len(rows), "missed": data["missed"],
        "unjoined": data["unjoined"],
        "primary_cell": f"{'|'.join(PRIMARY_STATES)} x {PRIMARY_ALIGNMENT}",
        "primary": primary,
        "primary_floor": {"min_clusters": MIN_CLUSTERS,
                          "min_trades": MIN_TRADES,
                          "bar": "clustered CI entirely above zero"},
        "primary_floor_met": floor_met,
        "exploratory": exploratory,
        "note": ("one pre-registered cell, ~30 exploratory ones — some cell "
                 "somewhere looking significant is expected by chance; only "
                 "the primary may decide anything"),
    }


def _print_cell(pad, c):
    if not c.get("n"):
        print(f"{pad}n=0")
        return
    if not c["sample_ok"]:
        print(f"{pad}n={c['n']} closed — BELOW THE FLOORS "
              f"(needs >= {MIN_CLUSTERS} symbols and >= {MIN_TRADES} trades). "
              f"Counts are facts, verdicts need floors.")
        return
    print(f"{pad}n={c['n']} · {c['expectancy_r']:+.4f} R · win {c['win_pct']}% "
          f"· cluster CI [{c['cluster_ci_lo']:+.3f}, {c['cluster_ci_hi']:+.3f}]"
          f" over {c['clusters']} symbols"
          f"{' · CLEARS ZERO' if c['clears_zero'] else ''}")


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
    print(f"trend slice — {rep['n_closed']} closed replayed trades "
          f"({rep['missed']} missed, {rep['unjoined']} unjoined) under "
          f"{rep['setup_version']}, entry model {rep['entry_model']}")
    print(f"\nPRIMARY (pre-registered): {rep['primary_cell']}")
    _print_cell("  ", rep["primary"])
    if not rep["primary_floor_met"]:
        print("  the primary floor is not met — this hasn't proven anything "
              "yet, and nothing below may promote anything.")
    print(f"\nexploratory (correction owed — {rep['note']}):")
    for name, c in rep["exploratory"].items():
        print(f"  {name}")
        _print_cell("    ", c)
    print("\nNOT A GATE. Evidence is recorded, not filtered on, until it has "
          "been graded (rule 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
