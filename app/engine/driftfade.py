"""Drift fade — was this entry fading a market that was already moving? READ-ONLY.

Between 2026-08-19 and 08-21 BTC rose ~23% in three days. Most alt labels sat
in TRANSITION the whole way (a vertical move makes no pullback, so no HL ever
confirms, so no BULL_TREND can print), and TRANSITION plus a supply-zone touch
is the REVERSAL short. The machine faded that rally 54 times in simulation for
-47 R; the risk gates funded five, and all five stopped out. The mirror
happened a week earlier with the signs flipped: 15 REVERSAL longs filled into
the 08-12/13 downdrift for -14.2 R while BTC's own 24h change never left
-0.65%. BTC's speed misses that cluster entirely; the SYMBOL'S OWN speed
catches both. That asymmetry is why the factor here is own-symbol drift, not
BTC drift — the contrarian pass on the streak diagnosis is what surfaced it.

The one-number summary that motivated this module, measured on all 104
REVERSAL fills of the then-current baseline before anything was built: entries
fading a >=2%/24h move in the entry's own symbol averaged -0.78 R (n=68);
every other REVERSAL entry averaged +0.20 R (n=36); the difference held a
symbol-clustered interval of [-1.66, -0.36]. On the funded book the same flag
marked 7 of the 11 losses — both clusters, both directions, PULLBACK included
— and none of the winners.

WHY THIS IS A MEASUREMENT AND NOT A GATE. Two auditioned rules that read just
as obviously came back INVERTED (btcalign: OPPOSED beat ALIGNED; BIAS_POLICY:
AGAINST beat WITH), and rule 7 is explicit: evidence is recorded, not filtered
on, until it has been graded. If this factor one day clears its floors, gating
it is a versioned setups change proposed to the operator — never a side effect
of this file.

WHAT THIS GRADE CANNOT PROVE YET, stated before the first run so the output
cannot soften it:

* The threshold and window (2%/24h, own symbol) were chosen IN SAMPLE, after
  reading the Aug 12-23 outcomes on this store. Unlike ignition's cells they
  were not fixed blind, so on today's book this split GRADES ITS OWN TEACHER
  and will flatter itself. The number that decides anything is the same split
  on trades closed after 2026-08-23; until then every run of this module is
  context, not verdict.
* The store so far holds essentially two drift episodes (one down, one up).
  Symbol-clustered intervals treat symbols as independent; within one episode
  they are not, which is why the week-clustered interval is computed as well
  and the WIDER of the two is reported (ignition's discipline, same reason).
* The flag knows only realised drift. XRPUSDT was shorted one hour BEFORE the
  08-19 breakout candle at +0.7%/24h and lost like the rest; nothing
  conditioned on past drift can see that trade coming.

Usage (from app/):
  python -m engine.driftfade            # grade against the current book
  python -m engine.driftfade --json
"""
import bisect
import datetime
import json
import sqlite3

from . import store
# One authority for the clustered interval and the bar clock: the audition
# that introduced cluster resampling to this repo owns the helper.
from .ignition import MIN_CLOSED, TF_SECONDS, cluster_ci

#: Trailing window the drift is measured over, in seconds. A day, because the
#: two motivating clusters were day-scale moves and because 24h of bars exists
#: on every tf the pipeline trades (6 bars of 4H up to 96 bars of 15m).
DRIFT_WINDOW_SECONDS = 86400

#: The fade line, in percent over the window. IN-SAMPLE (see docstring): it
#: separated the motivating clusters from the profitable remainder at the
#: widest margin of the thresholds looked at (2% -> delta -0.98 with the
#: symbol-clustered interval clear of zero; 5% -> -0.38 crossing zero).
COUNTER_DRIFT_PCT = 2.0

#: The reference close may be at most this far behind the window's nominal
#: start. Thin markets carry venue-acknowledged empty buckets; a reference
#: found further back than one extra window would silently measure multi-day
#: drift under a 24h name, so it lands in MISSING instead.
MAX_REFERENCE_AGE_SECONDS = 2 * DRIFT_WINDOW_SECONDS

#: ...and the NEWEST close must be at most this many bars behind as_of, or the
#: "drift now" is a drift as of some earlier hour wearing today's timestamp.
#: The audit demonstrated a 15h drift ending 9h before as_of passing without
#: this guard. Two bars: the confirming bar closes AT confirmed_at for every
#: real candidate, so one venue-acknowledged empty bucket is tolerated and a
#: genuinely stale tail lands in MISSING.
MAX_LATEST_AGE_BARS = 2


# ---------------------------------------------------------------- the factor

def drift_pct(closes, as_of, tf_seconds,
              window=DRIFT_WINDOW_SECONDS, max_age=MAX_REFERENCE_AGE_SECONDS):
    """Percent change over the trailing `window` ending at `as_of`.

    `closes` is a list of (open_ts, close_float) sorted by open_ts. Only bars
    CLOSED by `as_of` count (open_ts + tf_seconds <= as_of) — convention 4's
    closed-candles rule applies to a measurement exactly as it applies to an
    engine, or the factor reads a price the gate could not have known.

    Returns (pct, span_seconds) — the span is the REAL distance between the
    two closes, which a gapped series can stretch past the nominal window; the
    caller stamps it so no consumer has to trust the window's name. Returns
    None when either end of the window is missing, when the reference close is
    older than `max_age` before `as_of`, or when the newest close is more than
    MAX_LATEST_AGE_BARS behind `as_of` — a stale tail is not "drift now".
    """
    if not closes:
        return None
    last_open = as_of - tf_seconds          # newest bar fully closed at as_of
    ref_open = as_of - window - tf_seconds  # its counterpart one window back
    i = bisect.bisect_right(closes, (last_open, float("inf"))) - 1
    j = bisect.bisect_right(closes, (ref_open, float("inf"))) - 1
    if i < 0 or j < 0 or i == j:
        return None
    if closes[i][0] + tf_seconds < as_of - MAX_LATEST_AGE_BARS * tf_seconds:
        return None
    if closes[j][0] + tf_seconds < as_of - max_age:
        return None
    now, ref = closes[i][1], closes[j][1]
    if ref <= 0:
        return None
    return (now / ref - 1.0) * 100.0, closes[i][0] - closes[j][0]


def counter(direction, drift):
    """True when the entry fades a move of at least COUNTER_DRIFT_PCT.

    SHORT into a rising tape or LONG into a falling one. WITH the move is not
    the complement — a quiet tape is neither — so callers get three states:
    True / False / None(unknown drift).
    """
    if drift is None:
        return None
    if direction == "SHORT":
        return drift >= COUNTER_DRIFT_PCT
    if direction == "LONG":
        return drift <= -COUNTER_DRIFT_PCT
    return None


# ---------------------------------------------------------------- annotation

def _closes(con, symbol, tf):
    return [(r[0], float(r[1])) for r in con.execute(
        "SELECT open_ts, close FROM candles WHERE symbol=? AND tf=? "
        "ORDER BY open_ts", (symbol, tf))]


def annotate(con, candidates):
    """Stamp own_drift_24h_pct / counter_drift / with_drift onto payloads.

    Same in-place convention as btcalign.annotate. The drift is taken as-of
    the setup's confirmed_at — the moment a gate would have evaluated it, per
    convention 3 — from the setup's OWN symbol and timeframe, so every
    candidate the pipeline produced has its series by construction. Unknowable
    drift (missing window, over-aged reference) leaves the payload untouched
    and the candidate in outcome_split's MISSING bucket.
    """
    series = {}
    n = 0
    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        tf_seconds = TF_SECONDS.get(tf)
        if not symbol or not tf_seconds:
            continue
        if (symbol, tf) not in series:
            series[(symbol, tf)] = _closes(con, symbol, tf)
        got = drift_pct(series[(symbol, tf)], c["confirmed_at"], tf_seconds)
        if got is None:
            continue
        d, span = got
        flag = counter(p.get("direction"), d)
        if flag is None:
            continue
        p["own_drift_24h_pct"] = round(d, 3)
        p["own_drift_span_hours"] = round(span / 3600, 1)
        p["counter_drift"] = flag
        p["with_drift"] = ((p["direction"] == "LONG" and d >= COUNTER_DRIFT_PCT)
                           or (p["direction"] == "SHORT"
                               and d <= -COUNTER_DRIFT_PCT))
        n += 1
    return n


def factor_extractors(payload):
    """0/1 flags for outcome_split; absent when unannotated so the MISSING
    bucket stays honest."""
    if "counter_drift" not in payload:
        return {}
    return {"counter_drift": 1.0 if payload["counter_drift"] else 0.0,
            "with_drift": 1.0 if payload["with_drift"] else 0.0}


# ------------------------------------------------------------------ grading

def cluster_delta_ci(rows, iters=3000, seed=17):
    """Clustered interval on mean_R(counter) - mean_R(rest).

    Two per-cell intervals that overlap do not answer "is there a difference"
    — the delta has its own interval, resampled the same way cluster_ci
    resamples cells: whole clusters, never trades, by symbol and by ISO week,
    the WIDER interval reported. Returns (point, lo, hi) or None below the
    same floors cluster_ci applies (>=8 clusters, MIN_CLOSED trades total).
    """
    import random
    pop = [x for x in rows if x["counter"] is not None]

    def delta(sample):
        a = [x["r"] for x in sample if x["counter"]]
        b = [x["r"] for x in sample if not x["counter"]]
        if not a or not b:
            return None
        return sum(a) / len(a) - sum(b) / len(b)

    point = delta(pop)
    if point is None:
        return None
    #: A resample that draws no counter rows (or no rest rows) has no delta.
    #: Dropping it and reading percentiles over the survivors CONDITIONS the
    #: interval on the split existing — narrowest exactly when the sample is
    #: weakest, which is the out-of-sample run this module exists for. Up to
    #: this fraction of drops is tolerated and REPORTED; past it the interval
    #: is refused rather than quietly conditioned (rule 6).
    max_dropped = 0.10
    wide, wide_dropped = None, None
    for key in (lambda x: x["symbol"],
                lambda x: datetime.date.fromtimestamp(x["t"]).isocalendar()[:2]):
        by = {}
        for x in pop:
            by.setdefault(key(x), []).append(x)
        if len(by) < 8 or len(pop) < MIN_CLOSED:
            continue
        keys, rnd, deltas, dropped = list(by), random.Random(seed), [], 0
        for _ in range(iters):
            pool = []
            for _ in keys:
                pool.extend(by[rnd.choice(keys)])
            d = delta(pool)
            if d is None:
                dropped += 1
            else:
                deltas.append(d)
        if not deltas or dropped > max_dropped * iters:
            continue
        deltas.sort()
        ci = (deltas[int(.025 * len(deltas))], deltas[int(.975 * len(deltas))])
        if wide is None or (ci[1] - ci[0]) > (wide[1] - wide[0]):
            wide, wide_dropped = ci, dropped
    if wide is None:
        return None
    return {"point": round(point, 4), "ci": [round(wide[0], 4), round(wide[1], 4)],
            "resamples_dropped": wide_dropped, "iters": iters,
            "clears_zero": bool(wide[0] > 0 or wide[1] < 0)}


def _cell(rows):
    """Mean, win rate and the WIDER of the two clustered intervals for one
    cell of closed trades, or a sample-too-small marker below the floor."""
    if not rows:
        return {"n": 0}
    rs = [x["r"] for x in rows]
    ci_sym = cluster_ci(rows, lambda x: x["symbol"])
    ci_wk = cluster_ci(rows, lambda x: datetime.date.fromtimestamp(x["t"])
                       .isocalendar()[:2])
    wide = None
    for ci in (ci_sym, ci_wk):
        if ci and (wide is None or (ci[1] - ci[0]) > (wide[1] - wide[0])):
            wide = ci
    return {"n": len(rows), "mean_r": round(sum(rs) / len(rs), 4),
            "win_rate": round(sum(1 for r in rs if r > 0) / len(rs), 3),
            "ci": wide, "sample_ok": len(rows) >= MIN_CLOSED,
            "clears_zero": bool(wide and (wide[0] > 0 or wide[1] < 0))}


def grade(con, *, setup_version=None, exec_version=None):
    """The whole audition: load, annotate, split, and say what held."""
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
            continue
        p = c["payload"]
        closed.append({"r": c["r"], "t": c["confirmed_at"],
                       "symbol": p.get("symbol"),
                       "strategy": p.get("strategy"),
                       "counter": p.get("counter_drift")})

    def bucket(pred):
        return [x for x in closed if pred(x)]

    cells = {
        "counter_drift": _cell(bucket(lambda x: x["counter"] is True)),
        "rest": _cell(bucket(lambda x: x["counter"] is False)),
        "missing": _cell(bucket(lambda x: x["counter"] is None)),
    }
    delta = cluster_delta_ci(closed)
    by_strategy = {}
    for strat in sorted({x["strategy"] for x in closed if x["strategy"]}):
        pool = bucket(lambda x, s=strat: x["strategy"] == s)
        by_strategy[strat] = {
            "counter_drift": _cell([x for x in pool if x["counter"] is True]),
            "rest": _cell([x for x in pool if x["counter"] is False]),
            "delta": cluster_delta_ci(pool),
        }

    splits = {name: factorstats.outcome_split(candidates, name,
                                              factors=factor_extractors)
              for name in ("counter_drift", "with_drift")}
    return {
        "derived_at_analysis_time": True,       # no fact written, no gate armed
        "in_sample_note": ("threshold and window were chosen from this store's "
                           "Aug 2026 outcomes; only trades closed after "
                           "2026-08-23 test the factor rather than teach it"),
        "window_seconds": DRIFT_WINDOW_SECONDS,
        "counter_drift_pct": COUNTER_DRIFT_PCT,
        "candidates": len(candidates),
        "annotated": n_annotated,
        "closed_trades": len(closed),
        "cells": cells,
        "delta": delta,
        "by_strategy": by_strategy,
        "splits": splits,
        "warnings": warnings,
    }


def _print_cell(pad, name, c):
    if not c.get("n"):
        print(f"{pad}{name:<14} n=0")
        return
    mean = f"{c['mean_r']:+.3f} R" if c["sample_ok"] else "SAMPLE TOO SMALL"
    ci = (f"  ci[{c['ci'][0]:+.2f},{c['ci'][1]:+.2f}]"
          f"{' CLEARS ZERO' if c['clears_zero'] else ''}" if c.get("ci") else "")
    print(f"{pad}{name:<14} n={c['n']:<5} {mean}{ci}")


def _print_delta(pad, d):
    if not d:
        print(f"{pad}{'delta':<14} SAMPLE TOO SMALL")
        return
    print(f"{pad}{'delta':<14} {d['point']:+.3f} R  "
          f"ci[{d['ci'][0]:+.2f},{d['ci'][1]:+.2f}]"
          f"{' CLEARS ZERO' if d['clears_zero'] else ''}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--setup-version", default=None)
    ap.add_argument("--exec-version", default=None)
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    try:
        res = grade(con, setup_version=args.setup_version,
                    exec_version=args.exec_version)
    finally:
        con.close()
    if args.json:
        print(json.dumps(res, indent=1, default=str))
        return 0
    print(f"drift fade — {res['annotated']}/{res['candidates']} candidates "
          f"annotated, {res['closed_trades']} closed "
          f"(fade line {COUNTER_DRIFT_PCT}%/24h, own symbol)")
    print(f"  {res['in_sample_note']}")
    for name, c in res["cells"].items():
        _print_cell("  ", name, c)
    _print_delta("  ", res["delta"])
    for strat, cells in res["by_strategy"].items():
        print(f"  {strat}")
        for name, c in cells.items():
            if name == "delta":
                _print_delta("    ", c)
            else:
                _print_cell("    ", name, c)
    print("NOT A GATE. Evidence is recorded, not filtered on, until it has "
          "been graded (rule 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
