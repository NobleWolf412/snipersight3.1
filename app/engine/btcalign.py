"""BTC alignment — was BTC trending WITH or AGAINST this alt setup? READ-ONLY.

The prior project hard-blocked this at scan time: its Gate 3 rejected alt
entries against a strong opposing BTC impulse, checked before scoring on every
symbol. Its own cohort forensics both justified and complicated the gate —
counter-BTC longs lost, but with-BTC longs lost MORE in the degraded window,
which is why the 2026-05-29 root-cause doc demoted the gate from prime suspect.
A rule that plausible and that contested is exactly what this codebase's house
convention exists for: EVIDENCE IS RECORDED, NOT FILTERED ON — a factor must be
graded before it can gate.

So this module is the measurement, not the gate. It derives the factor as a
pure JOIN over facts the store already holds — BTC's own regime facts, read
as_of each setup's confirmation (§5: nothing here reads a fact the system could
not have known at decision time) — and hands the annotated candidates to
`factorstats.outcome_split`, whose sample floors and missing-bucket honesty do
the judging. No setup payload changes, no version bump, no fact written: the
factor exists at analysis time, which is the cheapest place a factor can earn
or lose its right to exist.

The mapping is deliberately conservative, matching the gate it is auditioning
to replace ("strong opposing impulse", not any disagreement):

    OPPOSED   LONG into BEAR_TREND, or SHORT into BULL_TREND — the full trend
              only. WEAKENING_* is a trend losing force; blocking on it would
              block exactly the turns the REVERSAL playbook hunts.
    ALIGNED   LONG into BULL_TREND, SHORT into BEAR_TREND.
    NEUTRAL   everything else: TRANSITION, RANGE, WEAKENING_*.

BTC's own setups are left UNANNOTATED (the factor is about alts riding or
fighting the tide; BTC is the tide), and so are setups confirmed before BTC's
first regime fact on that timeframe — both land in outcome_split's MISSING
bucket, which exists precisely so "we didn't look" cannot launder itself into
"we looked and it wasn't there".

If the split one day clears the floor with a real edge, gating is a SEPARATE,
deliberate change: a setups version bump, a new order flow, a new era for the
record — a decision for the operator, never a side effect of this file.

Usage (from app/):
  python -m engine.btcalign            # grade against the current book
  python -m engine.btcalign --json
"""
import json
import sqlite3

from . import store
from .regime import REGIME_VERSION

#: The tide itself. The scan universe has been Phemex perps since S34 and the
#: store's BTC facts live under this symbol.
BTC_SYMBOL = "BTCUSDT"

OPPOSES = {"LONG": "BEAR_TREND", "SHORT": "BULL_TREND"}
ALIGNS = {"LONG": "BULL_TREND", "SHORT": "BEAR_TREND"}


def alignment(direction: str, btc_regime: str | None) -> str | None:
    """OPPOSED / ALIGNED / NEUTRAL, or None when BTC's state is unknowable."""
    if btc_regime is None:
        return None
    if btc_regime == OPPOSES.get(direction):
        return "OPPOSED"
    if btc_regime == ALIGNS.get(direction):
        return "ALIGNED"
    return "NEUTRAL"


def _btc_regime_series(con, tf: str) -> list[tuple[int, str]]:
    """(confirmed_at, regime) for BTC on one timeframe, in confirmation order."""
    out = []
    for r in store.get_facts(con, BTC_SYMBOL, tf, "regime", REGIME_VERSION):
        out.append((r["confirmed_at"], json.loads(r["payload"])["regime"]))
    out.sort()
    return out


def regime_asof(series: list[tuple[int, str]], ts: int) -> str | None:
    """BTC's regime as the system could have known it at `ts` — the latest
    fact confirmed at or before that moment, None before the first one."""
    label = None
    for confirmed_at, regime in series:
        if confirmed_at > ts:
            break
        label = regime
    return label


def annotate(con, candidates: list[dict]) -> int:
    """Stamp `btc_regime_asof` / `btc_alignment` onto alt candidates' payloads.

    Mutates the payload dicts in place — the same convention
    `factorstats.load_candidates` uses to surface tf/symbol — and returns how
    many candidates were annotated. BTC's own setups and pre-first-fact
    candidates are left untouched, landing in the MISSING bucket by design.
    """
    series: dict[str, list] = {}
    n = 0
    for c in candidates:
        p = c["payload"]
        if p.get("symbol") == BTC_SYMBOL:
            continue
        tf = p.get("tf")
        if tf not in series:
            series[tf] = _btc_regime_series(con, tf)
        label = regime_asof(series[tf], c["confirmed_at"])
        side = alignment(p.get("direction"), label)
        if side is None:
            continue
        p["btc_regime_asof"] = label
        p["btc_alignment"] = side
        n += 1
    return n


def factor_extractors(payload: dict) -> dict[str, float]:
    """0/1 flags for outcome_split. Absent when unannotated, so the MISSING
    bucket stays honest."""
    side = payload.get("btc_alignment")
    if side is None:
        return {}
    return {"btc_opposed": 1.0 if side == "OPPOSED" else 0.0,
            "btc_aligned": 1.0 if side == "ALIGNED" else 0.0}


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    """The whole audition: load, annotate, split, and say what held."""
    from . import factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    n_annotated = annotate(con, candidates)
    closed = [c for c in candidates if c.get("r") is not None]
    sides = {}
    for c in closed:
        sides.setdefault(c["payload"].get("btc_alignment", "UNANNOTATED"),
                         []).append(c["r"])
    splits = {name: factorstats.outcome_split(candidates, name,
                                              factors=factor_extractors)
              for name in ("btc_opposed", "btc_aligned")}
    return {
        "derived_at_analysis_time": True,       # no fact written, no gate armed
        "candidates": len(candidates),
        "annotated": n_annotated,
        "closed_trades": len(closed),
        "by_alignment": {
            k: {"n": len(v),
                "total_r": round(sum(v), 2),
                "mean_r": (round(sum(v) / len(v), 4)
                           if len(v) >= factorstats.MIN_TRADES else None)}
            for k, v in sorted(sides.items())},
        "min_trades": factorstats.MIN_TRADES,
        "splits": splits,
        "warnings": warnings,
    }


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--setup-version", default=None)
    ap.add_argument("--exec-version", default=None)
    args = ap.parse_args(argv)
    con = store.connect()
    try:
        res = grade(con, setup_version=args.setup_version,
                    exec_version=args.exec_version)
    finally:
        con.close()
    if args.json:
        print(json.dumps(res, indent=1))
        return 0
    print(f"BTC alignment — derived factor audition "
          f"({res['annotated']}/{res['candidates']} candidates annotated, "
          f"{res['closed_trades']} closed)")
    for side, g in res["by_alignment"].items():
        mean = "withheld (below floor)" if g["mean_r"] is None else f"{g['mean_r']:+.4f}"
        print(f"  {side:12} n={g['n']:4}  total {g['total_r']:+8.2f} R  mean {mean}")
    for name, sp in res["splits"].items():
        hi, lo = sp["groups"]["at_or_above"], sp["groups"]["below"]
        d = sp["delta_mean_r"]
        print(f"  split {name}: yes n={hi['n']}, no n={lo['n']}, "
              f"missing n={sp['groups']['missing']['n']}"
              + (f", delta mean R {d:+.4f}" if d is not None
                 else " — delta withheld (a side is below the floor)"))
    for w in res["warnings"]:
        print(f"  note: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
