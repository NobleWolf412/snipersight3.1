"""Higher-timeframe context for a setup — the zone above it, and the target
the regime would choose. READ-ONLY: writes no facts, arms nothing.

TWO QUESTIONS a top-down desk asks of every lower-timeframe entry, and which
`setups.py` cannot answer today because it reads zones, pools and ranges on
its OWN timeframe only:

  1. IS THERE A HIGHER-TIMEFRAME LEVEL HERE? A 15m supply zone is a 15m swing
     high. In a 4H uptrend it is noise; at a 4H or 1D supply zone it is the
     trade. `htf_zone_at` returns the nearest-rung HTF zone of the same type
     whose band intersects the setup's zone, as-of the setup's confirmation,
     or None.

  2. WHERE WOULD THE REGIME SEND THE TARGET? `setups.target()` takes the
     nearest opposing pool or swing on the trade's own timeframe, capped at
     MAX_TARGET_R. That is a full-retrace target regardless of what the market
     is doing. `target_alt` answers by phase (regimeread): with the direction
     of an IMPULSE/TREND, the next unbroken HTF pool beyond the structure
     target; inside a RANGE/DRIFT, the range's opposing boundary; otherwise
     None — the structure target stands.

Both are computed at ANALYSIS time from facts the store already holds, as-of
confirmation (rule 3), and graded against the recorded book before either
touches a setup fact. Recording them on the fact is the versioned setups
change that follows a grade, not the grade itself (rule 7). Same in-place
annotate convention as driftfade and regimeread.

WHAT THE COUNTERFACTUAL CANNOT KNOW. `cf_r_alt` re-walks the stored candles
from the recorded fill bar under `entrystats.walk_forward` — execsim's own
rules (stop-first on an ambiguous bar, TIMEOUT at MAX_BARS) — with the
recorded stop and the ALTERNATIVE target. It is gross of costs, as every
`cf_` figure in this codebase is, and it is a comparison of targets on the
same fills, never a result. It is reported beside the recorded net R with
that mark and never without it.

Usage (from app/):
  python -m engine.htfread            # grade against the current book
  python -m engine.htfread --json
"""
import bisect
import json
from decimal import Decimal

from . import store
from .bias import rungs_above
from .liquidity import LIQ_VERSION
from .ranges import RANGES_VERSION
from .zones import ZONE_VERSION

HTFREAD_VERSION = "htfread-v0.1-draft"
#: How many rungs above the trade's timeframe are consulted for a zone.
#: Two: the next timeframe up and the one above it (15m -> 1H, 4H). The
#: rungs beyond that are the ladder's business (bias.py), not a level's.
ZONE_RUNGS = 2
Q2 = Decimal("0.01")


def _d(v):
    return None if v is None else Decimal(str(v))


class HtfContext:
    """One symbol/timeframe's HTF zones, HTF pools and own-tf ranges, loaded
    once and read as-of."""

    def __init__(self, tf, zones_by_rung, pools_by_rung, ranges, own_zones=None):
        self.tf = tf
        self.zones_by_rung = zones_by_rung   # {rung: [zone dicts with created_at, broken_at]}
        self.pools_by_rung = pools_by_rung   # {rung: [pool dicts with confirmed_at, broken_at]}
        self.ranges = ranges                 # own tf: [range dicts with formed_at, broken_at]
        self.own_zones = own_zones or {}     # own tf: zone_id -> {zone_type, bottom, top}

    def htf_zone_at(self, zone_type, bottom, top, as_of):
        """Nearest-rung HTF zone of `zone_type` intersecting [bottom, top],
        alive at as_of. Bands are ATR-scaled per timeframe (zones.ZONE_ATR),
        so a 4H band is wider than a 15m one — intersection is the test."""
        bottom, top = _d(bottom), _d(top)
        for rung in rungs_above(self.tf)[:ZONE_RUNGS]:
            best = None
            for z in self.zones_by_rung.get(rung, ()):
                if z["zone_type"] != zone_type or z["created_at"] > as_of:
                    continue
                if z["broken_at"] is not None and z["broken_at"] <= as_of:
                    continue
                if z["bottom"] <= top and z["top"] >= bottom:
                    if best is None or z["created_at"] > best["created_at"]:
                        best = z
            if best is not None:
                return {"tf": rung, "zone_id": best["zone_id"],
                        "bottom": str(best["bottom"]), "top": str(best["top"])}
        return None

    def next_htf_pool(self, direction, beyond, as_of):
        """Nearest unbroken HTF pool on the trade's target side, strictly beyond
        `beyond` (the structure target), nearest rung first."""
        side = "HIGH" if direction == "LONG" else "LOW"
        beyond = _d(beyond)
        for rung in rungs_above(self.tf)[:ZONE_RUNGS]:
            cands = [p["level"] for p in self.pools_by_rung.get(rung, ())
                     if p["side"] == side and p["confirmed_at"] <= as_of
                     and (p["broken_at"] is None or p["broken_at"] > as_of)
                     and ((p["level"] > beyond) if direction == "LONG" else (p["level"] < beyond))]
            if cands:
                return (min(cands) if direction == "LONG" else max(cands)), rung
        return None, None

    def range_at(self, price, as_of):
        """The own-tf range containing `price`, alive at as_of, or None."""
        price = _d(price)
        best = None
        for r in self.ranges:
            if r["formed_at"] > as_of or (r["broken_at"] is not None and r["broken_at"] <= as_of):
                continue
            if r["bottom"] <= price <= r["top"]:
                if best is None or r["formed_at"] > best["formed_at"]:
                    best = r
        return best


def load(con, symbol, tf) -> HtfContext:
    zones_by_rung, pools_by_rung = {}, {}
    for rung in rungs_above(tf)[:ZONE_RUNGS]:
        zs: dict = {}
        for r in store.get_facts(con, symbol, rung, "zone", ZONE_VERSION):
            p = json.loads(r["payload"])
            z = zs.setdefault(p["zone_id"], {"zone_id": p["zone_id"], "zone_type": p["zone_type"],
                                             "bottom": _d(p["bottom"]), "top": _d(p["top"]),
                                             "created_at": None, "broken_at": None})
            if p["event"] == "CREATED":
                z["created_at"] = r["confirmed_at"]
            elif p["event"] == "BROKEN":
                z["broken_at"] = r["confirmed_at"]
        zones_by_rung[rung] = [z for z in zs.values() if z["created_at"] is not None]
        ps: dict = {}
        for r in store.get_facts(con, symbol, rung, "liquidity", LIQ_VERSION):
            p = json.loads(r["payload"])
            if p["event"] == "POOL":
                ps[p["pool_id"]] = {"pool_id": p["pool_id"], "side": p["side"],
                                    "level": _d(p["level"]), "confirmed_at": r["confirmed_at"],
                                    "broken_at": None}
            elif p["event"] == "BROKEN" and p["pool_id"] in ps:
                ps[p["pool_id"]]["broken_at"] = r["confirmed_at"]
        pools_by_rung[rung] = list(ps.values())
    rs: dict = {}
    for r in store.get_facts(con, symbol, tf, "range", RANGES_VERSION):
        p = json.loads(r["payload"])
        rg = rs.setdefault(p["range_id"], {"range_id": p["range_id"], "top": _d(p["top"]),
                                           "bottom": _d(p["bottom"]), "formed_at": None,
                                           "broken_at": None})
        if p["event"] == "FORMED":
            rg["formed_at"] = r["confirmed_at"]
        elif p["event"] == "BROKEN":
            rg["broken_at"] = r["confirmed_at"]
    ranges = [x for x in rs.values() if x["formed_at"] is not None]
    # A setup fact names its zone by id, not by band; the band lives on the
    # zone's own CREATED fact.
    own_zones: dict = {}
    for r in store.get_facts(con, symbol, tf, "zone", ZONE_VERSION):
        p = json.loads(r["payload"])
        if p["event"] == "CREATED":
            own_zones[p["zone_id"]] = {"zone_type": p["zone_type"],
                                       "bottom": _d(p["bottom"]), "top": _d(p["top"])}
    return HtfContext(tf, zones_by_rung, pools_by_rung, ranges, own_zones)


def target_alt(ctx: HtfContext, *, direction, entry, sl, tp, phase, as_of):
    """The regime-aware alternative target, or None when structure stands.

    Pure given a context. Returns (price, source) where source names the
    rule that chose it — a number nobody can trace is a number nobody trusts.
    """
    entry, sl, tp = _d(entry), _d(sl), _d(tp)
    if None in (entry, sl, tp) or phase is None:
        return None, None
    want = {"LONG": "UP", "SHORT": "DOWN"}.get(direction)
    side = "UP" if "_UP" in phase else "DOWN" if "_DOWN" in phase else None
    if side is not None and side == want and (phase.startswith("IMPULSE") or phase.startswith("TREND")):
        level, rung = ctx.next_htf_pool(direction, tp, as_of)
        if level is not None:
            return level, f"HTF_POOL_{rung}"
        return None, None
    if phase == "RANGE" or phase.startswith("DRIFT"):
        rg = ctx.range_at(entry, as_of)
        if rg is not None:
            edge = rg["top"] if direction == "LONG" else rg["bottom"]
            ok = (edge > entry) if direction == "LONG" else (edge < entry)
            if ok:
                return edge, "RANGE_EDGE"
    return None, None


def annotate(con, candidates) -> int:
    """Stamp htf_zone / target_alt onto each candidate's payload, as-of its
    confirmation. Requires `phase` (regimeread.annotate) for target_alt;
    htf_zone needs only the zone band, which every setup payload carries."""
    ctxs: dict = {}
    n = 0
    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or not tf:
            continue
        key = (symbol, tf)
        if key not in ctxs:
            ctxs[key] = load(con, symbol, tf)
        ctx = ctxs[key]
        own = ctx.own_zones.get(p.get("zone_id"))
        if own is not None:
            zt, zb, zt_ = own["zone_type"], own["bottom"], own["top"]
        else:
            # no zone fact under this id (retired generation): the entry
            # stands in as a point band, the type follows the direction
            zt = "DEMAND" if p.get("direction") == "LONG" else "SUPPLY"
            zb = zt_ = p.get("entry")
        if zb is not None:
            p["htf_zone"] = ctx.htf_zone_at(zt, zb, zt_, c["confirmed_at"])
            p["has_htf_zone"] = p["htf_zone"] is not None
        alt, src = target_alt(ctx, direction=p.get("direction"), entry=p.get("entry"),
                              sl=p.get("sl"), tp=p.get("tp"), phase=p.get("phase"),
                              as_of=c["confirmed_at"])
        if alt is not None:
            risk = abs(_d(p["entry"]) - _d(p["sl"]))
            p["target_alt"] = str(alt)
            p["target_alt_source"] = src
            p["target_alt_r"] = str((abs(alt - _d(p["entry"])) / risk).quantize(Q2)) if risk else None
        n += 1
    return n


def factor_extractors(payload) -> dict:
    if "has_htf_zone" not in payload:
        return {}
    return {"has_htf_zone": 1.0 if payload["has_htf_zone"] else 0.0,
            "has_target_alt": 1.0 if payload.get("target_alt") is not None else 0.0}


def _fill_bar(con, symbol, tf, setup_id, candles_opens):
    """Index of the recorded fill bar for this setup, from its exec fact."""
    from .execsim import EXEC_VERSION
    for (p,) in con.execute(
            "SELECT payload FROM facts WHERE kind='exec' AND symbol=? AND tf=? "
            "AND algo_version=? ORDER BY confirmed_at DESC", (symbol, tf, EXEC_VERSION)):
        d = json.loads(p)
        if d.get("setup_id") == setup_id and d.get("fill_ts"):
            i = bisect.bisect_left(candles_opens, int(d["fill_ts"]))
            return i if i < len(candles_opens) else None
    return None


def counterfactual(con, candidates) -> dict:
    """cf_r_alt vs recorded R on the trades that have a target_alt. GROSS."""
    from . import driftfade, entrystats, execsim
    series: dict = {}
    rows = []
    for c in candidates:
        p = c["payload"]
        if c.get("r") is None or p.get("target_alt") is None:
            continue
        key = (p["symbol"], p["tf"])
        if key not in series:
            cs = [dict(r) for r in store.get_candles(con, p["symbol"], p["tf"])]
            series[key] = (cs, [x["open_ts"] for x in cs])
        cs, opens = series[key]
        i = _fill_bar(con, p["symbol"], p["tf"], c["setup_id"], opens)
        if i is None:
            continue
        w = entrystats.walk_forward(cs, i, direction=p["direction"], sl=_d(p["sl"]),
                                    tp=_d(p["target_alt"]), max_bars=execsim.MAX_BARS)
        if w["outcome"] == "UNRESOLVED":
            continue
        entry = _d(p["entry"]); risk = abs(entry - _d(p["sl"]))
        move = (w["exit_price"] - entry) if p["direction"] == "LONG" else (entry - w["exit_price"])
        cf = float((move / risk).quantize(Q2)) if risk else None
        if cf is None:
            continue
        rows.append({"symbol": p["symbol"], "strategy": p.get("strategy"),
                     "source": p.get("target_alt_source"), "r": float(c["r"]),
                     "cf_r_alt": cf, "counter": True, "t": int(c["confirmed_at"])})
    out = {"n": len(rows)}
    if rows:
        out["recorded_mean_r"] = round(sum(r["r"] for r in rows) / len(rows), 3)
        out["cf_alt_mean_r_GROSS"] = round(sum(r["cf_r_alt"] for r in rows) / len(rows), 3)
        deltas = [dict(r, r=r["cf_r_alt"] - r["r"], counter=True) for r in rows]
        rest = [dict(r, r=0.0, counter=False) for r in rows]
        out["paired_delta"] = driftfade.cluster_delta_ci(deltas + rest)
        by = {}
        for r in rows:
            b = by.setdefault(r["source"], {"n": 0, "rec": 0.0, "cf": 0.0})
            b["n"] += 1; b["rec"] += r["r"]; b["cf"] += r["cf_r_alt"]
        out["by_source"] = {k: {"n": v["n"], "recorded_mean_r": round(v["rec"] / v["n"], 3),
                                "cf_alt_mean_r_GROSS": round(v["cf"] / v["n"], 3)} for k, v in by.items()}
    return out


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    from . import factorstats, regimeread
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    regimeread.annotate(con, candidates)
    n = annotate(con, candidates)
    splits = {name: factorstats.outcome_split(candidates, name, factors=factor_extractors)
              for name in ("has_htf_zone",)}
    by_strat = {}
    for strat in ("PULLBACK", "REVERSAL"):
        sub = [c for c in candidates if c["payload"].get("strategy") == strat]
        by_strat[strat] = factorstats.outcome_split(sub, "has_htf_zone", factors=factor_extractors)
    return {"version": HTFREAD_VERSION, "derived_at_analysis_time": True,
            "candidates": len(candidates), "annotated": n,
            "htf_zone_split": splits["has_htf_zone"], "htf_zone_by_strategy": by_strat,
            "target_alt_counterfactual": counterfactual(con, candidates),
            "warnings": warnings}


def main(argv=None):
    import argparse
    import sqlite3
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
        print(json.dumps(rep, indent=1, default=str))
        return 0

    def cell(x):
        return (f"n={x['n']:4d} mean={x['mean_r']:+.3f}R win={x['win_rate']:.0%}"
                if x.get("sample_ok") else f"n={x['n']:4d} SAMPLE TOO SMALL")
    print(f"HTF context {rep['version']} — {rep['annotated']}/{rep['candidates']} annotated")
    s = rep["htf_zone_split"]["groups"]
    print(f"\nhas an HTF zone under it:  {cell(s['at_or_above'])}   |  none: {cell(s['below'])}")
    for strat, sp in rep["htf_zone_by_strategy"].items():
        g = sp["groups"]
        print(f"  {strat:8s}  HTF zone: {cell(g['at_or_above'])}   |  none: {cell(g['below'])}")
    cf = rep["target_alt_counterfactual"]
    print(f"\nregime-aware target (COUNTERFACTUAL, GROSS) on n={cf.get('n', 0)} trades that had one:")
    if cf.get("n"):
        print(f"  recorded net mean R {cf['recorded_mean_r']:+.3f}   cf alt gross mean R {cf['cf_alt_mean_r_GROSS']:+.3f}")
        d = cf["paired_delta"]
        print(f"  paired delta {d['point']:+.3f}R  ci[{d['ci'][0]:+.3f},{d['ci'][1]:+.3f}]  clears_zero={d['clears_zero']}")
        for k, v in cf["by_source"].items():
            print(f"    {k:14s} n={v['n']:4d} recorded {v['recorded_mean_r']:+.3f}  cf {v['cf_alt_mean_r_GROSS']:+.3f}")
    print("\nNOT A GATE. Analysis-time only; recording either field is a versioned setups change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
