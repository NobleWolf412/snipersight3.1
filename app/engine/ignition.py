"""Trend ignition — enter WHEN the trend is born, not after it has aged. READ-ONLY.

The operator's question, verbatim: "BOS makes a new higher high, makes a new
higher low confirmed. major signal. especially htf. that worked into a play
book?"

The answer to "is it in a playbook" is: as a STATE, yes — that exact trifecta
(confirmed BOS + confirmed HH + confirmed HL) is what flips a market's label to
BULL_TREND in regime.py, and BEAR_TREND is the mirror. But the label only opens
the door for PULLBACK to buy a later dip into a zone, a median 68-159 bars
afterwards. Nothing in the codebase enters when the pattern itself completes.
This module measures what that missing entry would have earned, without
creating it.

WHY THE MEASUREMENT MUST BE ALLOWED TO SAY NO. Three prior results bear
directly on this idea and two of them are graves: btcalign graded with-BTC
alignment INVERTED, bias.py's BIAS_POLICY graded with-ladder alignment
INVERTED, and trend.py's buy-strength engine graded with an interval entirely
below zero. The steelman is just as real: both inversions measured COUNTER-MOVE
entries taken long after the label, the trend replay's WITH-ladder continuation
filter was positive and predicted in advance, and regimefresh found fresher
labels associated with better outcomes in-sample. Lateness, not
trend-following, is the live suspect. This module exists to separate the two.

WHAT "CONFIRMED" COSTS, measured on this store before anything was built: a
structure BREAK is knowable one bar after it happens, but a swing LABEL (the
HH/HL themselves) confirms a median ~91 bars after its pivot bar, because an
INTERMEDIATE/MAJOR promotion is only knowable once its held-window closes. So
trend transitions are bimodal: roughly a quarter complete on a fresh BOS and
are knowable within a bar; the majority complete on a stale label arrival. The
operator's chart-eye picture of "the HL just confirmed" is usually the SLOW
cohort. Freshness is therefore a PRIMARY design axis here, fixed before any
result was read:

    fresh = the transition confirmed within FRESH_MAX_BARS of its trigger bar
    stale = everything else

PRE-REGISTERED PRIMARY CELL, chosen before the first run, correction owed by
everything else: pooled 1H+4H, both directions, FRESH cohort, the one fixed
bracket below, decided on a symbol-clustered interval. 1D and 1W are reported
but can never decide anything from this store — 80 and 12 events in total
exist at the current regime version, below any honest floor after one split.

ONE EXECUTION AUTHORITY. Brackets are built from the same shared pieces every
strategy uses (setups: vetoes, SL_BUFFER_ATR, MIN_RR, MAX_TARGET_R, the
MAKER_THEN_MARKET entry model) and every simulated trade is filled, walked and
costed by execsim's own simulate_entry / walk_exit / settle. abtest's history
records four drift incidents from having a private simulation core; this
module never gets one. Nothing here writes a fact, arms a gate, or appears in
pipeline; test_ignition pins that. If the grade ever clears the bar, a
playbook is a separate versioned proposal for the operator — five tags move
and the forward record restarts — never a side effect of this file.

Usage (from app/):
  python -m engine.ignition            # grade against the current book
  python -m engine.ignition --json
"""
import hashlib
import json
import random
import sqlite3

from decimal import Decimal

from . import bias, costs, store
from .execsim import simulate_entry, walk_exit, settle
from .regime import REGIME_VERSION
from .setups import (ENTRY_MODEL, MAKER_OFFSET_R, MAKER_WAIT_BARS,
                     MAX_TARGET_R, MIN_RISK_COST_MULT, MIN_RR, Q2,
                     SL_BUFFER_ATR, vetoes)
from .structure import STRUCTURE_VERSION
from .swings import SWING_VERSION, compute_atr, quote_ticks

# FIRST GRADING — 2026-08-21, full store, current versions, paper replay.
#
# THE GATES ANSWERED BEFORE THE MARKET DID. Of 1,752 transitions, the book's
# own economics refused 1,323 ignition attempts for RR_BELOW_MINIMUM and 255
# more for NO_TARGET: at the moment the trifecta completes, price sits at the
# top of known structure — the trend just MADE the nearest swing — so the
# structural target discipline finds nothing 1.5R away to aim at. That is not
# a defect in the audition; it is the reason PULLBACK waits for a dip. The
# pattern's completion is real and the room to trade it is not there.
#
# What survived the gates: 99 closed, -0.153 R, symbol-clustered interval
# [-0.437, +0.183] — indistinguishable from zero. The pre-registered primary
# cell (pooled 1H+4H, FRESH) closed NINE trades against its 120 floor: the
# initiation hypothesis cannot even be tested at the spot chosen for it,
# because fresh transitions that survive the gates are that rare. Fresh did
# not beat stale (n=15 -0.40 vs n=84 -0.11, both under the cell floor).
#
# The two baselines frame it. Random in-state entries: n=113, -0.612 R,
# interval [-0.803, -0.387] — ENTIRELY below zero, so trend states do not
# rescue arbitrary entries, and ignition's trigger does add ~0.46 R over
# random. The delayed twin (+68 bars, PULLBACK's median wait): n=52,
# +0.106 R, crossing zero — better than ignition, but read it with its bias:
# the delayed arm only exists where the trend state SURVIVED 68 bars, which
# selects the trends that did not immediately die. Suggestive that waiting
# loses nothing; not proof that waiting wins.
#
# VERDICT: not a playbook on this book. Keep the state as the gate it already
# is; do not add the event as an entry.

#: The freshness cut, in the transition's own bars, FIXED BEFORE THE FIRST RUN.
#: The measured p25 of transition lag is 1 bar (a completing BOS is knowable at
#: its own bar close); 5 gives the fresh cohort room for settlement jitter
#: without letting a 91-bar label arrival masquerade as fresh. Chosen from the
#: lag distribution, never from outcomes.
FRESH_MAX_BARS = 5

#: The delayed-entry baseline lags the same events by PULLBACK's own measured
#: median wait between label and zone-touch fire. If initiation entries and
#: 68-bar-later entries earn the same, "enter when it is born" adds nothing
#: over what the book already does.
DELAY_BARS = 68

#: Full trend states, the only transitions measured. WEAKENING_* is a trend
#: losing force and TRANSITION is the reversal playbook's territory.
TREND = {"BULL_TREND": "LONG", "BEAR_TREND": "SHORT"}

TF_SECONDS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400,
              "1D": 86400, "1W": 604800}

#: Floors, stated rather than discovered: a cell below MIN_CLOSED closed trades
#: is printed as SAMPLE TOO SMALL, whatever its mean says. The primary cell
#: needs MIN_PRIMARY to be read at all — the contrarian's arithmetic for a
#: freshness x baseline comparison to mean anything.
MIN_CLOSED = 30
MIN_PRIMARY = 120


# ---------------------------------------------------------------- extraction

def extract_events(regime_rows, tf_seconds):
    """Transitions INTO a full trend, from one market's regime facts.

    `regime_rows` are (market_time, confirmed_at, payload_dict) tuples under
    ONE version, unordered. Returns events as dicts, ordered by confirmed_at.
    A transition is counted when the classification CHANGES into BULL_TREND or
    BEAR_TREND — regime.py only emits on change, so consecutive rows differ by
    construction; the guard against equal states is kept anyway because this
    module must hold even if that upstream property ever relaxes.
    """
    rows = sorted(regime_rows, key=lambda r: (r[1], r[0]))
    events, prev = [], None
    for market_time, confirmed_at, payload in rows:
        cur = payload.get("regime")
        if cur in TREND and prev != cur:
            trigger = (payload.get("evidence") or {}).get("trigger") or {}
            trig_at = trigger.get("at")
            lag_bars = ((confirmed_at - int(trig_at)) / tf_seconds
                        if isinstance(trig_at, (int, float)) else None)
            events.append({
                "market_time": market_time, "confirmed_at": confirmed_at,
                "regime": cur, "direction": TREND[cur],
                "trigger_event": trigger.get("event"),
                "lag_bars": lag_bars,
                "fresh": lag_bars is not None and lag_bars <= FRESH_MAX_BARS,
                "evidence": payload.get("evidence") or {},
            })
        prev = cur
    # The state's end bounds the random baseline: an entry "while the trend
    # label governs" may not outlive the label.
    ends = sorted({r[1] for r in rows})
    for e in events:
        later = [t for t in ends if t > e["confirmed_at"]]
        e["state_end"] = later[0] if later else None
    return events


def trifecta_ok(event):
    """Does the fact's own evidence spell the operator's pattern?

    regime.py already enforces this in _classify, so a mismatch here means THIS
    module misread the store, not that the engine misfired — which is exactly
    what a verify() exists to catch (the regimefresh lesson: a reconstruction
    that reads different labels than the engine did is a measurement of
    something else, and it cannot announce that itself).
    """
    ev = event["evidence"]
    brk = (ev.get("last_break") or {})
    if event["regime"] == "BULL_TREND":
        return (brk.get("direction") == "BULL"
                and ev.get("last_high_label") == "HH"
                and ev.get("last_low_label") == "HL")
    return (brk.get("direction") == "BEAR"
            and ev.get("last_high_label") == "LH"
            and ev.get("last_low_label") == "LL")


def label_level_asof(labels, ts, side):
    """Price of the last confirmed HL (side='LOW') or LH ('HIGH') at `ts`.

    `labels` are (confirmed_at, type, label, price) sorted by confirmed_at.
    The stop hangs off this level: the trend premise IS that this pivot holds,
    so trading through it is the structural invalidation.
    """
    want = {"LOW": "HL", "HIGH": "LH"}[side]
    level = None
    for confirmed_at, typ, label, price in labels:
        if confirmed_at > ts:
            break
        if typ == side and label == want:
            level = price
    return level


def pick_baseline_bar(setup_key, lo_i, hi_i):
    """Deterministic 'random' bar in [lo_i, hi_i] for the same-state baseline.

    Seeded from the event's identity so every run of this module reproduces
    the same table — an audition whose baseline moves between runs cannot be
    audited. hashlib rather than hash(): the latter is salted per process.
    """
    if hi_i <= lo_i:
        return lo_i
    seed = int(hashlib.sha256(setup_key.encode()).hexdigest()[:12], 16)
    return lo_i + random.Random(seed).randrange(hi_i - lo_i + 1)


# ---------------------------------------------------------------- simulation

def _bracket_and_trade(candles, atr, ticks, order_i, direction, stop_level,
                       tier_swings, as_of, profile, symbol, tf_seconds):
    """One plan, filled, walked and costed by the engine's own machinery.

    Returns a result dict, or (None, reason) when the shared gates refuse the
    trade — refusals are counted, never silently dropped, because attrition is
    part of the answer (a signal that survives its own economics gate half the
    time is half the signal).
    """
    long = direction == "LONG"
    cb = candles[order_i - 1]
    a = atr[order_i - 1]
    if a is None:
        return None, "NO_ATR"
    entry = Decimal(candles[order_i]["open"])
    if long:
        sl = min(Decimal(cb["low"]), stop_level) - SL_BUFFER_ATR * a
    else:
        sl = max(Decimal(cb["high"]), stop_level) + SL_BUFFER_ATR * a
    risk = (entry - sl) if long else (sl - entry)
    if risk <= 0:
        return None, "INVALID_BRACKET"
    fired = vetoes(confirm_bar=cb, atr_at_confirm=a, entry=entry, sl=sl,
                   tick=ticks[order_i - 1])
    if fired:
        return None, "VETOED"
    side = "HIGH" if long else "LOW"
    beyond = [p for confirmed_at, p in tier_swings[side]
              if confirmed_at <= as_of
              and (p > entry if long else p < entry)]
    if not beyond:
        return None, "NO_TARGET"
    tp_uncapped = min(beyond) if long else max(beyond)
    cap = entry + MAX_TARGET_R * risk if long else entry - MAX_TARGET_R * risk
    tp = min(tp_uncapped, cap) if long else max(tp_uncapped, cap)
    rr = (((tp - entry) if long else (entry - tp)) / risk).quantize(Q2)
    if rr < MIN_RR:
        return None, "RR_BELOW_MINIMUM"
    if risk < MIN_RISK_COST_MULT * costs.estimated_round_trip_cost(
            entry, a, profile, symbol=symbol, tf_seconds=tf_seconds):
        return None, "UNECONOMIC_AFTER_COSTS"

    maker_limit = (entry - MAKER_OFFSET_R * risk) if long \
        else (entry + MAKER_OFFSET_R * risk)
    fill = simulate_entry(candles, atr, order_i, entry, sl, long,
                          entry_model=ENTRY_MODEL, maker_limit=maker_limit,
                          maker_wait=MAKER_WAIT_BARS, profile=profile)
    if fill["status"] == "MISSED":
        return {"outcome": "MISSED", "r": None}, None
    if fill["status"] != "FILLED":
        return None, "PENDING"
    walked = walk_exit(candles, fill["fill_i"], sl, tp, long)
    if walked is None:
        return None, "OPEN"
    outcome, exit_px, j, ambiguous = walked
    priced = settle(profile, symbol, fill["entry"], exit_px, fill["risk"],
                    long, outcome, j - fill["fill_i"], tf_seconds, atr[j],
                    entry_role=fill["entry_role"])
    return {"outcome": outcome, "r": float(priced["r_mult"]),
            "ambiguous": ambiguous}, None


# ------------------------------------------------------------------- grading

def collect(con):
    """Every trend-ignition trade, its delayed twin, and its random twin.

    Read-only over the live store, current versions only, derived at analysis
    time — no fact is written and no gate is armed.
    """
    con.row_factory = sqlite3.Row
    pairs = [tuple(r) for r in con.execute(
        "SELECT DISTINCT symbol, tf FROM facts WHERE kind='regime' "
        "AND algo_version=?", (REGIME_VERSION,))]
    rows, refusals, bad_evidence, n_events = [], {}, 0, 0
    for symbol, tf in sorted(pairs):
        tf_seconds = TF_SECONDS.get(tf)
        if not tf_seconds:
            continue
        regime_rows = [(r["market_time"], r["confirmed_at"],
                        json.loads(r["payload"]))
                       for r in store.get_facts(con, symbol, tf, "regime",
                                                REGIME_VERSION)]
        events = extract_events(regime_rows, tf_seconds)
        if not events:
            continue
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        if len(candles) < 30:
            continue
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)
        profile = costs.profile_for(symbol)
        bias_src = bias.load(con, symbol, tf)
        labels, tier_swings = [], {"HIGH": [], "LOW": []}
        for r in store.get_facts(con, symbol, tf, "structure",
                                 STRUCTURE_VERSION):
            p = json.loads(r["payload"])
            if p.get("event") == "LABEL":
                labels.append((r["confirmed_at"], p["type"], p["label"],
                               Decimal(p["price"])))
        labels.sort()
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p.get("tier") in ("INTERMEDIATE", "MAJOR"):
                tier_swings[p["type"]].append(
                    (r["confirmed_at"], Decimal(p["price"])))
        for side in tier_swings:
            tier_swings[side].sort()
        # candles indexed once; order bar = first bar wholly after knowability
        opens = [c["open_ts"] for c in candles]

        def order_index(ts):
            import bisect
            i = bisect.bisect_left(opens, ts)
            return i if i < len(candles) else None

        for e in events:
            n_events += 1
            if not trifecta_ok(e):
                bad_evidence += 1
                continue
            side = "LOW" if e["direction"] == "LONG" else "HIGH"
            arms = [("ignition", e["confirmed_at"])]
            if e["state_end"] is None or \
                    e["confirmed_at"] + DELAY_BARS * tf_seconds < e["state_end"]:
                arms.append(("delayed",
                             e["confirmed_at"] + DELAY_BARS * tf_seconds))
            for name, at in list(arms):
                if name == "ignition":
                    lo = order_index(e["confirmed_at"])
                    hi = order_index(e["state_end"]) if e["state_end"] else None
                    hi = (hi - 1) if hi is not None else len(candles) - 1
                    if lo is not None and hi is not None and hi > lo:
                        key = f"{symbol}|{tf}|{e['confirmed_at']}"
                        arms.append(("random",
                                     candles[pick_baseline_bar(key, lo, hi)]
                                     ["open_ts"]))
            for name, at in arms:
                i = order_index(at)
                if i is None or i < 1 or i >= len(candles):
                    refusals[f"{name}:NO_FORWARD_BARS"] = \
                        refusals.get(f"{name}:NO_FORWARD_BARS", 0) + 1
                    continue
                level = label_level_asof(labels, at, side)
                if level is None:
                    refusals[f"{name}:NO_STOP_LEVEL"] = \
                        refusals.get(f"{name}:NO_STOP_LEVEL", 0) + 1
                    continue
                result, reason = _bracket_and_trade(
                    candles, atr, ticks, i, e["direction"], level,
                    tier_swings, at, profile, symbol, tf_seconds)
                if result is None:
                    refusals[f"{name}:{reason}"] = \
                        refusals.get(f"{name}:{reason}", 0) + 1
                    continue
                block = bias_src.check(e["direction"], at, tf_seconds,
                                       {"WITH": "ALLOW", "AGAINST": "ALLOW",
                                        "MIXED": "ALLOW", "FLAT": "ALLOW",
                                        "UNKNOWN": "ALLOW"})
                rows.append({
                    "arm": name, "symbol": symbol, "tf": tf,
                    "direction": e["direction"], "fresh": e["fresh"],
                    "trigger": e["trigger_event"], "t": at,
                    "bias": block.get("state", "UNKNOWN"),
                    "outcome": result["outcome"], "r": result["r"],
                })
    return {"rows": rows, "refusals": refusals, "events": n_events,
            "bad_evidence": bad_evidence}


def cluster_ci(rows, key, iters=3000, seed=17):
    """Bootstrap the mean R by resampling CLUSTERS, never trades.

    Trend transitions fire in BTC-driven waves, so per-trade resampling
    overstates the sample. Clusters are given by `key` (symbol, or ISO week);
    the caller reports whichever interval is WIDER, which is the honest one.
    """
    by = {}
    for x in rows:
        by.setdefault(key(x), []).append(x["r"])
    if len(by) < 8 or sum(len(v) for v in by.values()) < MIN_CLOSED:
        return None
    keys, rnd, means = list(by), random.Random(seed), []
    for _ in range(iters):
        pool = []
        for _ in keys:
            pool.extend(by[rnd.choice(keys)])
        means.append(sum(pool) / len(pool))
    means.sort()
    return means[int(.025 * iters)], means[int(.975 * iters)]


def summarise(rows):
    closed = [x for x in rows if x["r"] is not None]
    missed = sum(1 for x in rows if x["outcome"] == "MISSED")
    if not closed:
        return {"n": 0, "missed": missed}
    import datetime as dt
    rs = [x["r"] for x in closed]
    ci_sym = cluster_ci(closed, lambda x: x["symbol"])
    ci_wk = cluster_ci(closed, lambda x: dt.date.fromtimestamp(x["t"])
                       .isocalendar()[:2])
    wide = None
    for ci in (ci_sym, ci_wk):
        if ci and (wide is None or (ci[1] - ci[0]) > (wide[1] - wide[0])):
            wide = ci
    return {"n": len(closed), "missed": missed,
            "mean_r": sum(rs) / len(rs),
            "win_rate": sum(1 for r in rs if r > 0) / len(rs),
            "ci": wide, "sample_ok": len(closed) >= MIN_CLOSED,
            "clears_zero": bool(wide and (wide[0] > 0 or wide[1] < 0))}


def grade(con):
    data = collect(con)
    rows = data["rows"]
    n_evidence = data["events"] - data["bad_evidence"]
    verify_rate = n_evidence / data["events"] if data["events"] else None

    def cell(**want):
        out = []
        for x in rows:
            if all(x.get(k) == v or (isinstance(v, tuple) and x.get(k) in v)
                   for k, v in want.items()):
                out.append(x)
        return out

    primary = summarise(cell(arm="ignition", fresh=True, tf=("1H", "4H")))
    report = {
        "derived_at_analysis_time": True,
        "verify": {"events": data["events"],
                   "evidence_ok": n_evidence, "rate": verify_rate},
        "refusals": data["refusals"],
        "primary_cell_pooled_1H_4H_fresh": primary,
        "primary_floor": MIN_PRIMARY,
        "cells": {},
    }
    for name, want in (
            ("ignition_all", {"arm": "ignition"}),
            ("ignition_fresh", {"arm": "ignition", "fresh": True}),
            ("ignition_stale", {"arm": "ignition", "fresh": False}),
            ("delayed_all", {"arm": "delayed"}),
            ("delayed_fresh_events", {"arm": "delayed", "fresh": True}),
            ("random_in_state", {"arm": "random"}),
            ("ignition_long", {"arm": "ignition", "direction": "LONG"}),
            ("ignition_short", {"arm": "ignition", "direction": "SHORT"})):
        report["cells"][name] = summarise(cell(**want))
    for tf in ("5m", "15m", "1H", "4H", "1D", "1W"):
        report["cells"][f"ignition_{tf}"] = summarise(
            cell(arm="ignition", tf=tf))
    return report


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    try:
        report = grade(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0
    v = report["verify"]
    print(f"evidence check: {v['evidence_ok']} of {v['events']} transitions "
          f"spell the trifecta ({v['rate']:.1%})")
    p = report["primary_cell_pooled_1H_4H_fresh"]
    print("\nPRIMARY (pre-registered): pooled 1H+4H, fresh, both directions")
    if p.get("n", 0) < report["primary_floor"]:
        print(f"  n={p.get('n', 0)} closed — BELOW THE {report['primary_floor']}"
              " FLOOR. The primary question is unanswered; nothing below may"
              " promote anything.")
    _print_cell("  ", p)
    print("\nexploratory (correction owed — many cells, one book):")
    for name, c in report["cells"].items():
        print(f"  {name}")
        _print_cell("    ", c)
    print("\nNOT A GATE. Promotion is a versioned operator decision; this "
          "module only measures.")
    return 0


def _print_cell(pad, c):
    if not c or not c.get("n"):
        print(f"{pad}no closed trades" + (f" · {c.get('missed', 0)} missed"
                                          if c else ""))
        return
    ci = c.get("ci")
    shown = f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "no honest interval"
    flag = "" if c.get("sample_ok") else "  SAMPLE TOO SMALL"
    print(f"{pad}n={c['n']} closed · {c['missed']} missed · "
          f"{c['mean_r']:+.3f} R · win {c['win_rate']:.0%} · {shown}{flag}")


if __name__ == "__main__":
    raise SystemExit(main())
