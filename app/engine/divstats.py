"""Did momentum divergence predict anything? READ-ONLY audition.

`momentum.py` has emitted DIVERGENCE facts since v0.1 and says in its own
docstring why they were emitted rather than acted on:

    "Divergence in particular is the sort of factor that reads as obviously
     true and grades badly, which is exactly why it is emitted as evidence and
     left there."

It is now drawn on the chart (4 Aug 2026), which makes the question sharper
rather than softer: an operator looking at a purple DIV arrow beside a setup
is one step from believing it means something. House convention 6 says a
factor must be graded before it can gate, and drawing a thing is a soft form
of gating — it changes what the operator does.

So this is the measurement, in the shape `btcalign.py` established: a pure
JOIN over facts the store already holds, read as_of each setup's confirmation
(§5: nothing here reads a fact the system could not have known at decision
time), handed to `factorstats.outcome_split`, whose sample floors and
missing-bucket honesty do the judging. No fact written, no version bumped, no
gate armed.

THE MAPPING. `momentum.py` emits REGULAR divergence only, and its own
semantics fix the direction:

    BULL   lower low in price, higher low in RSI  -> supports a LONG
    BEAR   higher high in price, lower high in RSI -> supports a SHORT

    AGREES   the divergence points the way the trade was taken
    OPPOSES  it points the other way
    (none)   no divergence inside the window -> MISSING, never "below"

RECENCY IS THE WHOLE ARGUMENT, so it is a parameter and the report grades
several values of it. A divergence forty bars before an entry has had ample
time to play out or fail and is no longer describing that entry; one on the
entry bar plainly is. Any single cutoff is a choice, and a factor that only
works at one hand-picked window is an artefact of the window. Grading at
5/10/20/40 bars costs one extra pass and makes that visible instead of
hiding it behind a default.

Usage (from app/):
  python -m engine.divstats            # grade against the current book
  python -m engine.divstats --json
"""
import json
import sqlite3

from . import store
from .momentum import MOMENTUM_VERSION

#: Bar windows the report grades at. See the docstring: a factor that only
#: survives at one of these is an artefact of that choice, and the reader is
#: entitled to see all four.
WINDOWS = (5, 10, 20, 40)

#: The default the summary leads with. 10 bars on the setup's own timeframe —
#: recent enough to still describe the entry, long enough that a divergence
#: confirming a bar or two before the setup is not missed by an off-by-one.
DEFAULT_WINDOW = 10

SUPPORTS = {"BULL": "LONG", "BEAR": "SHORT"}


def _divergences(con, symbol: str, tf: str) -> list[tuple[int, str]]:
    """(confirmed_at, direction) for one symbol/timeframe, in confirmation
    order. `confirmed_at` already carries momentum.py's pivot-confirmation
    lag, so this is the moment the system could first have known."""
    out = []
    for r in store.get_facts(con, symbol, tf, "momentum", MOMENTUM_VERSION):
        p = json.loads(r["payload"])
        if p.get("event") == "DIVERGENCE":
            out.append((r["confirmed_at"], p.get("direction")))
    out.sort()
    return out


def latest_before(series: list[tuple[int, str]], ts: int,
                  max_age_s: int) -> str | None:
    """The most recent divergence direction known at `ts` and no older than
    `max_age_s`, or None. Strictly `<= ts`: a divergence confirmed after the
    setup could not have informed it."""
    best = None
    for confirmed_at, direction in series:
        if confirmed_at > ts:
            break
        if ts - confirmed_at <= max_age_s:
            best = direction
    return best


def stance(direction: str | None, div_direction: str | None) -> str | None:
    """AGREES / OPPOSES, or None when there is nothing to compare."""
    if div_direction is None or direction is None:
        return None
    return "AGREES" if SUPPORTS.get(div_direction) == direction else "OPPOSES"


def annotate(con, candidates: list[dict], *, window_bars: int) -> int:
    """Stamp `div_stance` onto candidates whose window holds a divergence.

    Mutates payloads in place — the convention `factorstats.load_candidates`
    uses — and returns how many were annotated. A candidate with no divergence
    in range is left untouched so it lands in outcome_split's MISSING bucket,
    which exists precisely so "there wasn't one" cannot be read as "there was
    one pointing the other way".
    """
    from .importer import TF_SECONDS
    series: dict[tuple[str, str], list] = {}
    n = 0
    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or tf not in TF_SECONDS:
            continue
        key = (symbol, tf)
        if key not in series:
            series[key] = _divergences(con, symbol, tf)
        div = latest_before(series[key], c["confirmed_at"],
                            window_bars * TF_SECONDS[tf])
        side = stance(p.get("direction"), div)
        if side is None:
            continue
        p["div_stance"] = side
        p["div_direction"] = div
        n += 1
    return n


def factor_extractors(payload: dict) -> dict[str, float]:
    """0/1 flags for outcome_split. Absent when unannotated, so MISSING stays
    honest."""
    side = payload.get("div_stance")
    if side is None:
        return {}
    return {"div_agrees": 1.0 if side == "AGREES" else 0.0,
            "div_opposes": 1.0 if side == "OPPOSES" else 0.0}


def _clear(candidates: list[dict]) -> None:
    """Drop the annotation between windows — a payload keeps its dict across
    passes, and a stale stance would silently grade the previous window."""
    for c in candidates:
        c["payload"].pop("div_stance", None)
        c["payload"].pop("div_direction", None)


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    """The whole audition: load once, grade at every window, say what held."""
    from . import factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    closed_n = sum(1 for c in candidates if c.get("r") is not None)

    windows = {}
    for w in WINDOWS:
        _clear(candidates)
        annotated = annotate(con, candidates, window_bars=w)
        sides: dict[str, list[float]] = {}
        for c in candidates:
            if c.get("r") is None:
                continue
            sides.setdefault(c["payload"].get("div_stance", "NONE"),
                             []).append(c["r"])
        windows[w] = {
            "window_bars": w,
            "annotated": annotated,
            "by_stance": {
                k: {"n": len(v),
                    "total_r": round(sum(v), 2),
                    "mean_r": (round(sum(v) / len(v), 4)
                               if len(v) >= factorstats.MIN_TRADES else None)}
                for k, v in sorted(sides.items())},
            "splits": {name: factorstats.outcome_split(
                           candidates, name, factors=factor_extractors)
                       for name in ("div_agrees", "div_opposes")},
        }
    _clear(candidates)

    return {
        "derived_at_analysis_time": True,      # no fact written, no gate armed
        "momentum_version": MOMENTUM_VERSION,
        "candidates": len(candidates),
        "closed_trades": closed_n,
        "min_trades": factorstats.MIN_TRADES,
        "default_window": DEFAULT_WINDOW,
        "windows": windows,
        "warnings": warnings,
    }


def _fmt(report: dict) -> str:
    L = []
    L.append(f"DIVERGENCE vs THE BOOK  ({report['momentum_version']})")
    L.append(f"  candidates {report['candidates']} · "
             f"closed {report['closed_trades']} · "
             f"floor {report['min_trades']} per group")
    for w, d in report["windows"].items():
        L.append("")
        L.append(f"  within {w} bars of the entry — {d['annotated']} annotated")
        for stance_name, s in d["by_stance"].items():
            mean = "—" if s["mean_r"] is None else f"{s['mean_r']:+.4f} R"
            flag = "" if s["mean_r"] is not None else "  (under floor)"
            L.append(f"    {stance_name:8} n={s['n']:<4} "
                     f"total {s['total_r']:+9.2f} R   mean {mean}{flag}")
        for name, sp in d["splits"].items():
            delta = sp.get("delta_mean_r")
            if delta is not None:
                L.append(f"    {name}: delta mean R {delta:+.4f}")
    if report["warnings"]:
        L.append("")
        L.append("  warnings: " + "; ".join(report["warnings"][:4]))
    return "\n".join(L)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--setup-version", default=None)
    ap.add_argument("--exec-version", default=None)
    args = ap.parse_args(argv)
    con = store.connect()
    con.row_factory = sqlite3.Row
    try:
        rep = grade(con, setup_version=args.setup_version,
                    exec_version=args.exec_version)
    finally:
        con.close()
    print(json.dumps(rep, indent=2) if args.json else _fmt(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
