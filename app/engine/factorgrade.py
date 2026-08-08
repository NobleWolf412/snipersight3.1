"""Grade every unwired evidence engine against the book. READ-ONLY.

Seven engines run on every scan cycle and none of them touches a trading
decision. They became DRAWABLE on 4 Aug 2026, which is a soft form of gating —
an operator who can see a signal beside a setup is one step from believing it
means something — so house convention 6 applies: a factor must be graded
before it can gate, and drawing counts.

`divstats.py` did this for momentum divergence and found nothing. This does the
same for the rest, in one pass, so the panel can be read together instead of
one engine at a time.

THE SHAPE, unchanged from `btcalign.py`: a pure JOIN over facts the store
already holds, read as_of each setup's confirmation (§5 — nothing here reads a
fact the system could not have known at decision time), bootstrapped by
`edgestats._bootstrap_mean`, the same deterministic LCG the edge panel and the
live gate use. No fact written, no version bumped, no gate armed.

TWO SHAPES OF FACTOR, because the engines answer two different questions:

  DIRECTIONAL   the state implies a side, so the cohort is whether the trade
                agreed with it — MA position ABOVE argues for a long, a BULL
                fair-value gap argues for a long, price above VWAP argues for
                a long.
  STATEFUL      the state is a condition the trade happened inside, with no
                side of its own — squeezed or not, at a high-volume node or a
                low one, in a live range or not. The cohort is the state.

EVERY STATE VALUE BELOW WAS ENUMERATED FROM THE STORE, not read off the code.
That is not belt-and-braces: the volume-profile chart layer matched 'HVN' when
the engine writes 'AT_HVN' and silently drew nothing over 81 real facts, and
the squeeze marker tested `squeeze === true` when the engine writes the STRING
'ON'. Both bugs looked correct in review. A mapping that matches nothing
produces an empty cohort, and an empty cohort reads as "no effect" rather than
as "no reading" — the one failure this whole module exists to avoid.

Usage (from app/):
  python -m engine.factorgrade
  python -m engine.factorgrade --json
  python -m engine.factorgrade --window 20
"""
import json
import sqlite3

from . import store
from .divstats import latest_before, WINDOWS, DEFAULT_WINDOW

#: Enumerated from the store 4 Aug 2026. `field` is the payload key holding the
#: RESULTING state (never `from`, which is the previous one, and never `state`
#: on the volatility/volume engines, where it is the event phase).
FACTORS = [
    # ---- directional: the state argues for a side -------------------------
    {"name": "ma_position", "kind": "ma", "version_from": "ma",
     "event": None, "field": "position",
     "supports": {"ABOVE": "LONG", "BELOW": "SHORT"},        # INSIDE -> neither
     "note": "price above or below the moving-average ribbon"},
    {"name": "ma_stack", "kind": "ma", "version_from": "ma",
     "event": None, "field": "stack",
     "supports": {"BULL": "LONG", "BEAR": "SHORT"},          # MIXED -> neither
     "note": "the ribbon stacked bullish or bearish"},
    {"name": "vwap_side", "kind": "volume", "version_from": "volume",
     "event": "VWAP_CROSS", "field": "side",
     "supports": {"ABOVE": "LONG", "BELOW": "SHORT"},
     "note": "close above or below session VWAP"},
    # ---- stateful: a condition the trade happened inside ------------------
    {"name": "squeeze", "kind": "volatility", "version_from": "volatility",
     "event": "SQUEEZE", "field": "squeeze", "supports": None,
     "note": "Bollinger bands inside Keltner channels"},
    {"name": "atr_regime", "kind": "volatility", "version_from": "volatility",
     "event": "ATR_REGIME", "field": "regime", "supports": None,
     "note": "ATR percentile band"},
    {"name": "rvol", "kind": "volume", "version_from": "volume",
     "event": "RVOL", "field": "rvol_state", "supports": None,
     "note": "relative volume arrival (NORMAL is never emitted)"},
    {"name": "volprofile", "kind": "volprofile", "version_from": "volprofile",
     "event": "VP_STATE", "field": "state", "supports": None,
     "note": "at a high-volume node, a low-volume node, or mid"},
    {"name": "range_state", "kind": "range", "version_from": "ranges",
     "event": None, "field": "state", "supports": None,
     "note": "inside a formed range, testing its edge, or broken out"},
    # ---- continuous: bucketed, because the directional form is degenerate --
    #
    # `ma_position` CANNOT be graded as agreement on this book, and the reason
    # is structural rather than statistical. Measured 4 Aug 2026 over all 477
    # closed trades:
    #
    #     LONG  x price BELOW ribbon   190        LONG  x ABOVE   0
    #     SHORT x price ABOVE ribbon   146        SHORT x BELOW   0
    #
    # Not one trade in the book was taken trend-following. Both playbooks
    # enter counter-move — longs buy dips into demand, shorts sell rips into
    # supply — so "does the trade agree with the moving average" is a constant,
    # and a constant predicts nothing. Filtering to the continuation playbook
    # does not rescue it: PULLBACK alone is 91 OPPOSES and 0 AGREES.
    #
    # What DOES vary is how far price had run from the ribbon when the trade
    # was taken, which the engine already records in ATR units. That is the
    # gradable question, so it is the one asked.
    {"name": "ma_depth", "kind": "ma", "version_from": "ma",
     "event": None, "field": "close_to_fast_atr", "supports": None,
     "buckets": ((0.5, "shallow<0.5"), (1.5, "medium0.5-1.5"), (None, "deep>=1.5")),
     "note": "distance from the fast MA in ATR at entry, unsigned"},
]


def _version(name: str) -> str:
    from . import fvg, ma, ranges, volatility, volprofile, volume
    return {"ma": ma.MA_VERSION, "volume": volume.VOLUME_VERSION,
            "volatility": volatility.VOLATILITY_VERSION,
            "volprofile": volprofile.VOLPROFILE_VERSION,
            "ranges": ranges.RANGES_VERSION, "fvg": fvg.FVG_VERSION}[name]


def _series(con, symbol, tf, spec) -> list[tuple[int, str]]:
    """(confirmed_at, state) for one symbol/timeframe, in confirmation order."""
    out = []
    for r in store.get_facts(con, symbol, tf, spec["kind"],
                             _version(spec["version_from"])):
        p = json.loads(r["payload"])
        if spec["event"] and p.get("event") != spec["event"]:
            continue
        v = p.get(spec["field"])
        if v is not None:
            out.append((r["confirmed_at"], str(v)))
    out.sort()
    return out


def _fvg_series(con, symbol, tf) -> list[tuple[int, str]]:
    """The direction of the most recently CREATED gap that is still unfilled.

    A gap is a two-event object, so its state at a moment is not one fact's
    field: the walk carries CREATED/FILLED per gap_id forward and emits, at
    each event, the direction of the newest gap still open. Deliberately does
    NOT test how near price is to the gap — that refinement would need the
    entry price and a distance rule, and inventing one here would be a second
    unaudited judgement inside a measurement. Read this cohort as "an unfilled
    gap of this direction existed", not "price was at it".
    """
    from .fvg import FVG_VERSION
    events, open_gaps, out = [], {}, []
    for r in store.get_facts(con, symbol, tf, "fvg", FVG_VERSION):
        p = json.loads(r["payload"])
        events.append((r["confirmed_at"], p.get("event"), p.get("gap_id"),
                       p.get("direction")))
    events.sort()
    for ts, event, gid, direction in events:
        if event == "CREATED":
            open_gaps[gid] = (ts, direction)
        elif event == "FILLED":
            open_gaps.pop(gid, None)
        if open_gaps:
            newest = max(open_gaps.values(), key=lambda v: v[0])
            out.append((ts, newest[1]))
    return out


def annotate(con, candidates, spec, *, window_bars: int) -> int:
    """Stamp `spec['name']` onto candidates whose window holds a reading.

    Untouched when there is no reading, so it lands in the MISSING bucket —
    "we didn't look" must not launder itself into "we looked and it wasn't
    there" (factorstats.outcome_split).
    """
    from .importer import TF_SECONDS
    key_name, series, n = spec["name"], {}, 0
    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or tf not in TF_SECONDS:
            continue
        k = (symbol, tf)
        if k not in series:
            series[k] = (_fvg_series(con, symbol, tf) if spec["kind"] == "fvg"
                         else _series(con, symbol, tf, spec))
        state = latest_before(series[k], c["confirmed_at"],
                              window_bars * TF_SECONDS[tf])
        if state is None:
            continue
        if spec.get("buckets"):
            # A continuous reading, bucketed. UNSIGNED on purpose: the sign is
            # the direction the entry already encodes (longs sit below the
            # ribbon, shorts above), so keeping it would re-split the cohorts
            # by side and measure the entry model a second time.
            try:
                v = abs(float(state))
            except (TypeError, ValueError):
                continue
            for edge, label in spec["buckets"]:
                if edge is None or v < edge:
                    p[key_name] = label
                    break
        elif spec["supports"] is None:
            p[key_name] = state
        else:
            side = spec["supports"].get(state)
            if side is None:
                continue                     # INSIDE / MIXED argue for neither
            p[key_name] = "AGREES" if side == p.get("direction") else "OPPOSES"
        n += 1
    return n


def _clear(candidates, names) -> None:
    for c in candidates:
        for n in names:
            c["payload"].pop(n, None)


def grade(con, *, window_bars: int = DEFAULT_WINDOW, resamples: int = 5000,
          strategy: str | None = None,
          setup_version=None, exec_version=None) -> dict:
    """Grade every factor at one window. Returns cohorts with bootstrap CIs.

    `strategy` restricts the book — PULLBACK is the CONTINUATION playbook and
    REVERSAL the counter-trend one, and a factor can behave oppositely on the
    two. Splitting costs sample, so a filtered run will push more cohorts under
    the floor; that is reported rather than hidden.
    """
    from . import edgestats, factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    if strategy:
        candidates = [c for c in candidates
                      if c["payload"].get("strategy") == strategy]
    specs = FACTORS + [{"name": "fvg_gap", "kind": "fvg", "version_from": "fvg",
                        "event": None, "field": "direction",
                        "supports": {"BULL": "LONG", "BEAR": "SHORT"},
                        "note": "an unfilled fair-value gap of this direction"}]
    names = [s["name"] for s in specs]

    out = {}
    for spec in specs:
        _clear(candidates, names)
        annotated = annotate(con, candidates, spec, window_bars=window_bars)
        cohorts: dict[str, list[float]] = {}
        for c in candidates:
            if c.get("r") is None:
                continue
            cohorts.setdefault(c["payload"].get(spec["name"], "NONE"),
                               []).append(c["r"])
        rows = {}
        for name, rs in sorted(cohorts.items()):
            b = (edgestats._bootstrap_mean(rs, resamples)
                 if len(rs) >= factorstats.MIN_TRADES else None)
            rows[name] = {
                "n": len(rs), "total_r": round(sum(rs), 2),
                "mean_r": round(sum(rs) / len(rs), 4) if rs else None,
                "ci_lo": None if b is None else round(b["ci_lo"], 4),
                "ci_hi": None if b is None else round(b["ci_hi"], 4),
                "p_gt_zero": None if b is None else b["p_gt_zero"],
                # THE HOUSE BAR, the same one edgestats and livegate apply:
                # a mean above zero is not an edge, an interval above zero is.
                "clears_zero": bool(b and b["ci_lo"] > 0),
                "sample_ok": b is not None,
            }
        out[spec["name"]] = {"note": spec["note"], "annotated": annotated,
                             "directional": spec["supports"] is not None,
                             "cohorts": rows}
    _clear(candidates, names)

    any_clear = [f"{f}/{c}" for f, d in out.items()
                 for c, r in d["cohorts"].items()
                 if r["clears_zero"] and c != "NONE"]
    return {
        "derived_at_analysis_time": True,
        "window_bars": window_bars, "resamples": resamples,
        "strategy": strategy or "ALL",
        "candidates": len(candidates),
        "closed_trades": sum(1 for c in candidates if c.get("r") is not None),
        "min_trades": factorstats.MIN_TRADES,
        "factors": out,
        "cleared_zero": any_clear,
        "warnings": warnings,
    }


def calibrated_grade(evidence: dict) -> dict:
    """Turn validated Factor Stats into an explanation-only setup grade.

    Only stable, forward, multiple-testing-adjusted positive uplift can earn a
    letter. The grade never grants eligibility and ``sizing_allowed`` remains
    false until a later, explicitly promoted shadow calibration says otherwise.
    """
    accepted = [row for row in evidence.get("rows", [])
                if row.get("passes_evidence")]
    total_n = sum(int(row.get("high_samples", {}).get("forward", 0))
                  for row in accepted)
    if not accepted:
        return {
            "version": "factorgrade-v0.2-draft", "score": None,
            "grade": "UNGRADED", "confidence": "INSUFFICIENT_EVIDENCE",
            "coverage": 0.0, "expected_edge_r": None, "sample_size": 0,
            "components": [], "warnings": [
                "No stable out-of-sample factor survived the evidence and "
                "multiple-testing gates."], "sizing_allowed": False,
        }
    weights = [max(1, int(row["high_samples"]["forward"])) for row in accepted]
    edge = sum(float(row["shrunk_uplift_r"]) * weight
               for row, weight in zip(accepted, weights)) / sum(weights)
    coverage = sum(float(row["coverage"]) * weight
                   for row, weight in zip(accepted, weights)) / sum(weights)
    score = max(0.0, min(100.0, 50.0 + edge * 100.0))
    grade_name = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"
    q_min = min(float(row["q_value"]) for row in accepted)
    confidence = "HIGH" if total_n >= 100 and q_min <= 0.05 else "MEDIUM"
    return {
        "version": "factorgrade-v0.2-draft", "score": round(score, 2),
        "grade": grade_name, "confidence": confidence,
        "coverage": round(coverage, 4), "expected_edge_r": round(edge, 4),
        "sample_size": total_n, "components": accepted, "warnings": [],
        "sizing_allowed": False,
    }


def _fmt(rep: dict) -> str:
    L = [f"UNWIRED ENGINES vs THE BOOK   book {rep['strategy']} · "
         f"window {rep['window_bars']} bars · "
         f"{rep['closed_trades']} closed · floor {rep['min_trades']}"]
    for name, d in rep["factors"].items():
        L.append("")
        L.append(f"  {name}  ({'directional' if d['directional'] else 'state'}"
                 f") — {d['note']}")
        for cohort, r in d["cohorts"].items():
            if not r["sample_ok"]:
                L.append(f"    {cohort:10} n={r['n']:<4} "
                         f"total {r['total_r']:+8.2f} R   (under floor)")
                continue
            mark = "  <-- clears zero" if r["clears_zero"] else ""
            L.append(f"    {cohort:10} n={r['n']:<4} "
                     f"mean {r['mean_r']:+.4f} R  "
                     f"CI [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]  "
                     f"P(>0) {r['p_gt_zero']:.0%}{mark}")
    L.append("")
    L.append("  CLEARS ZERO: " + (", ".join(rep["cleared_zero"])
                                  or "nothing — no factor here has earned a gate"))
    return "\n".join(L)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                    help=f"bars of lookback (report default {DEFAULT_WINDOW}; "
                         f"divstats grades {WINDOWS})")
    ap.add_argument("--strategy", default=None,
                    help="PULLBACK is the continuation book; REVERSAL the "
                         "counter-trend one")
    ap.add_argument("--setup-version", default=None)
    ap.add_argument("--exec-version", default=None)
    args = ap.parse_args(argv)
    con = store.connect()
    con.row_factory = sqlite3.Row
    try:
        rep = grade(con, window_bars=args.window, strategy=args.strategy,
                    setup_version=args.setup_version,
                    exec_version=args.exec_version)
    finally:
        con.close()
    print(json.dumps(rep, indent=2) if args.json else _fmt(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
