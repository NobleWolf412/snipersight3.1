"""Market-context states graded as a FACTOR against the closed live book. READ-ONLY.

WHAT IS BEING GRADED. `market_context.snapshot` folds recorded facts into one
canonical point-in-time state — BREAKOUT (a validated release just confirmed),
COMPRESSION (squeeze on), EXPANSION (high ATR regime plus a fresh structural
break), UNSTABLE (the data itself is degraded), or the base regime label
(BULL_TREND / BEAR_TREND / WEAKENING_* / RANGE / TRANSITION / UNKNOWN) when
none of those fire. The fold ships on operator surfaces and has never been
asked the only question that matters about a factor: do its states separate
the outcomes of the trades the book actually took? This module asks exactly
that, factorstats-style — record first, grade, promote never.

ONE AUTHORITY FOR THE STATE. The state is NOT re-derived here from volatility
and structure facts: `snapshot` is called as-of each trade's entry decision
time and its own `regime` field is taken verbatim. A second fold would drift
from the shipped one the way every second copy in this repo's history has.

AS-OF DISCIPLINE (convention 3). The entry decision time is the setup's
`confirmed_at` — the moment the trade became knowable — and `snapshot`'s
`_latest` reads only facts confirmed at or before that instant, so no state
here is computed from anything the gate could not have seen. Reading at the
exec fact's exit time instead would grade the exit's context under the
entry's name.

THE JOIN is `factorstats.load_candidates` — VALIDATED setup facts under the
current setup version joined to exec facts under the current exec version,
per-trade R from the settled `r_multiple`, MISSED excluded (no realised R).
Nothing is re-priced and nothing is re-walked; this reads the record.

FIRE RATE AND DISPERSION, in factorstats' spirit, because a factor can fail
before its outcome column is even read: a state that fires on 98% of trades
is a constant wearing a factor's name (the S50 stuck-value signature —
STRENGTH appeared in 985 of 985 setups), and one that never fires cannot be
graded. Both are reported beside the outcome table.

FLOORS. Counts are facts, verdicts need floors: a state's mean and interval
are withheld below MIN_CLOSED closed trades, and the interval reported is the
WIDER of symbol- and week-clustered (ignition's discipline — context states
arrive in BTC-driven waves, so per-trade resampling overstates the sample).

NOT A GATE, AND THE LITMUS IS LITERAL: deleting this module must change no
trade. It writes no facts, arms nothing, is imported by no trading module and
appears in no pipeline roster. If a state ever clears the bar it becomes a
candidate for the §1.4 promotion criterion, proposed to the operator under a
versioned change — never a side effect of this file.

Usage (from app/):
  python -m engine.contextgrade            # grade against the current book
  python -m engine.contextgrade --json
"""
import datetime
import json
import sqlite3

from . import market_context, store
# One authority for the clustered interval: ignition owns the helper, exactly
# as driftfade imports it.
from .ignition import MIN_CLOSED, cluster_ci

#: A state covering at least this share of the graded book is flagged as
#: near-constant. 0.90 rather than the literal 1.0 of the STRENGTH finding,
#: because a factor does not have to be structurally true to be useless — at
#: nine trades in ten on one value, the other states cannot reach any floor
#: and the "factor" is mostly a restatement of the base rate.
NEAR_CONSTANT_SHARE = 0.90


def annotate(con, candidates) -> int:
    """Stamp `context_state` / `context_data_status` onto each candidate's
    payload, as-of its confirmed_at. In-place, driftfade.annotate's
    convention. Returns the number annotated."""
    n = 0
    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or not tf:
            continue
        try:
            snap = market_context.snapshot(con, symbol, tf,
                                           as_of=c["confirmed_at"])
        except ValueError:
            continue                      # unsupported timeframe: unannotated
        p["context_state"] = snap["regime"]
        p["context_data_status"] = snap["data_status"]
        n += 1
    return n


def _cell(rows) -> dict:
    """Counts always; mean, win rate and the WIDER clustered interval only at
    or above the floor — below it a mean would read as measurement."""
    if not rows:
        return {"n": 0, "sample_ok": False}
    if len(rows) < MIN_CLOSED:
        return {"n": len(rows), "sample_ok": False}
    rs = [x["r"] for x in rows]
    ci_sym = cluster_ci(rows, lambda x: x["symbol"])
    ci_wk = cluster_ci(rows, lambda x: datetime.date.fromtimestamp(x["t"])
                       .isocalendar()[:2])
    wide = None
    for ci in (ci_sym, ci_wk):
        if ci and (wide is None or (ci[1] - ci[0]) > (wide[1] - wide[0])):
            wide = ci
    return {"n": len(rows), "sample_ok": True,
            "mean_r": round(sum(rs) / len(rs), 4),
            "win_rate": round(sum(1 for r in rs if r > 0) / len(rs), 3),
            "ci": wide,
            "clears_zero": bool(wide and (wide[0] > 0 or wide[1] < 0))}


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    from . import factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    n_annotated = annotate(con, candidates)

    closed = []
    for c in candidates:
        if c.get("r") is None:
            continue                       # MISSED or still open: no realised R
        p = c["payload"]
        closed.append({"r": c["r"], "t": c["confirmed_at"],
                       "symbol": p.get("symbol"),
                       "strategy": p.get("strategy"),
                       "state": p.get("context_state"),
                       "data_status": p.get("context_data_status")})

    by_state: dict = {}
    for x in closed:
        by_state.setdefault(x["state"] or "UNANNOTATED", []).append(x)
    cells = {state: _cell(rows) for state, rows in sorted(by_state.items())}

    n_closed = len(closed)
    shares = {state: round(len(rows) / n_closed, 3)
              for state, rows in sorted(by_state.items())} if n_closed else {}
    modal = max(shares.values()) if shares else None
    data_status = {}
    for x in closed:
        key = x["data_status"] or "UNANNOTATED"
        data_status[key] = data_status.get(key, 0) + 1

    return {
        "derived_at_analysis_time": True,   # no fact written, no gate armed
        "candidates": len(candidates),
        "annotated": n_annotated,
        "closed_trades": n_closed,
        "cells": cells,
        # factorstats' spirit: a factor can fail on fire rate or dispersion
        # before its outcome column is read at all.
        "fire": {
            "state_shares": shares,
            "near_constant": bool(modal is not None
                                  and modal >= NEAR_CONSTANT_SHARE),
            "near_constant_share": NEAR_CONSTANT_SHARE,
            "data_status_at_entry": data_status,
        },
        "floor": {"min_closed": MIN_CLOSED,
                  "bar": ("wider of symbol/week clustered interval clear of "
                          "zero; below the floor a state reports counts only")},
        "warnings": warnings,
    }


def _print_cell(pad, name, c):
    if not c.get("n"):
        print(f"{pad}{name:<16} n=0")
        return
    if not c["sample_ok"]:
        print(f"{pad}{name:<16} n={c['n']:<5} SAMPLE TOO SMALL — counts are "
              f"facts, verdicts need floors")
        return
    ci = c.get("ci")
    shown = f"ci[{ci[0]:+.3f},{ci[1]:+.3f}]" if ci else "no honest interval"
    print(f"{pad}{name:<16} n={c['n']:<5} {c['mean_r']:+.4f} R · "
          f"win {c['win_rate']:.0%} · {shown}"
          f"{' CLEARS ZERO' if c.get('clears_zero') else ''}")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--setup-version", default=None)
    ap.add_argument("--exec-version", default=None)
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rep = grade(con, setup_version=args.setup_version,
                    exec_version=args.exec_version)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return 0
    print(f"context grade — {rep['annotated']}/{rep['candidates']} candidates "
          f"annotated, {rep['closed_trades']} closed")
    for name, c in rep["cells"].items():
        _print_cell("  ", name, c)
    fire = rep["fire"]
    print(f"  state shares: {fire['state_shares']}")
    if fire["near_constant"]:
        print(f"  NEAR-CONSTANT: one state covers >= "
              f"{fire['near_constant_share']:.0%} of the book — the S50 "
              f"stuck-value signature; the outcome table above cannot "
              f"separate what barely varies")
    print(f"  data status at entry: {fire['data_status_at_entry']}")
    for w in rep["warnings"]:
        print(f"  ! {w}")
    print("NOT A GATE. Deleting this module must change no trade — evidence "
          "is recorded, not filtered on, until it has been graded (rule 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
