"""Second and third zone touches — the cohort the pullback engine never sees. READ-ONLY.

THE INVISIBLE COHORT. `setups.py` only ever trades a zone's FIRST touch: its
zone pass keeps a TOUCH fact only when `episode == 1` ("first episode is the
trigger"), so every later revisit of a level that held is structurally
invisible to the book. The zone engine still records those revisits — TOUCH
facts with `episode >= 2`, capped at ten per zone — so the question "what
would trading the second touch have earned" is answerable from the store
without creating the trade. This module answers it for episodes 2 and 3.

THE PRIORS CONFLICT, WHICH IS WHY ONLY A MEASUREMENT SETTLES IT. Two house
readings of a retested level point in opposite directions:

  * `zones.freshness` docks 25 points PER EPISODE (`mitigation_decay =
    episodes * 25`), a heuristic ported in concept from the operator's prior
    project and never graded on this store — under it a third touch has burned
    half its freshness and reads as a weaker level.
  * The trading folklore the operator's playbooks come from says the opposite
    about the SECOND touch specifically: a level that held once has proven
    buyers live there, and setups' own confirmed-entry rule exists precisely
    because "the level held" is the evidence that matters.

Neither prior has a measurement behind it here. This table is the measurement.

THE COUNTERFACTUAL IS SETUPS' OWN TRADE, not a new one. Cohort admission
mirrors the playbook table by CALLING it — `setups.playbook` with PULLBACK
enabled, so DEMAND in (BULL_TREND, WEAKENING_BULL) and SUPPLY in (BEAR_TREND,
WEAKENING_BEAR), the regime read as-of the touch's `confirmed_at`. The entry
is then built by setups' own rules and constants: a confirming close within
CONFIRM_MAX_BARS (`setups.confirms`, stopped by a zone break), entry at the
next bar's open, the stop beyond the confirmation bar's extreme
(SL_BUFFER_ATR), the shared vetoes, the pools-then-swings target capped at
MAX_TARGET_R, MIN_RR and the cost gate. Fills, walks and costs are execsim's
own `simulate_entry` / `walk_exit` / `settle` — the ignition discipline: no
private simulation core, ever. Refusals are counted per gate, never dropped,
because attrition is part of the answer.

WHY NOMINAL n OVERSTATES EFFECTIVE n, stated before the first run so the
output cannot soften it: an episode-2 entry sits at the SAME LEVEL as its
episode-1 sibling, in the same regime, usually within days — the two outcomes
are serially correlated by construction, and second touches across forty
alt-coins ride the same BTC wave besides. So the per-trade count is not the
sample size. The SYMBOL-CLUSTERED interval (the wider of symbol- and
week-clustered, ignition's discipline) is the deciding one, and the floors are
the house bar it inherits: `cluster_ci` refuses below 8 clusters or
MIN_CLOSED trades, and no cell may be called a finding unless its clustered
interval clears zero.

NOT A GATE. This module writes no facts, arms nothing, and appears in no
pipeline roster; deleting it changes no trade. If episode 2 ever clears the
bar, admitting later episodes is a versioned `setups.py` change proposed to
the operator — the zone pass's `episode == 1` filter moves under a new tag —
never a side effect of this file.

Usage (from app/):
  python -m engine.episodes            # grade against the current book
  python -m engine.episodes --json
"""
import json
import sqlite3

from decimal import Decimal

from . import costs, store
from .execsim import simulate_entry, walk_exit, settle
# One authority for the clustered interval and the bar clock — the audition
# that introduced cluster resampling owns the helper (driftfade's precedent).
from .ignition import MIN_CLOSED, TF_SECONDS, cluster_ci
from .liquidity import LIQ_VERSION
from .regime import REGIME_VERSION
from .setups import (CONFIRM_MAX_BARS, ENTRY_MODEL, MAKER_OFFSET_R,
                     MAKER_WAIT_BARS, MAX_TARGET_R, MIN_RISK_COST_MULT,
                     MIN_RR, Q2, SL_BUFFER_ATR, confirms, playbook, vetoes)
from .swings import SWING_VERSION, compute_atr, quote_ticks
from .zones import ZONE_VERSION

#: The episodes measured, fixed before the first run. 2 and 3 separately —
#: pooling them would let a strong second touch carry a weak third, and the
#: freshness heuristic under audit treats them differently (50 vs 75 points
#: docked). Episode 1 is the traded book and is deliberately absent: it
#: already has a graded record and re-deriving it here would be a second
#: authority for numbers edgestats owns.
EPISODES = (2, 3)


def target_level(direction, entry, as_of, pools, pool_broken, tier_swings):
    """setups' target rule, rebuilt on the same facts: the nearest unbroken
    liquidity pool beyond entry, else the nearest INTERMEDIATE+ opposing swing.

    `setups.target` is a closure over its run()'s own fact loads and cannot be
    imported; this is the same rule over the same fact kinds, kept pure so a
    test can pin the mirror (pool preferred over swing, broken pools excluded,
    everything as-of) instead of trusting this sentence.

    `pools` are dicts with confirmed_at/side/level/pool_id; `pool_broken` maps
    pool_id -> broken confirmed_at; `tier_swings` maps side -> list of
    (confirmed_at, price).
    """
    side = "HIGH" if direction == "LONG" else "LOW"
    beyond = [p["level"] for p in pools
              if p["side"] == side and p["confirmed_at"] <= as_of
              and pool_broken.get(p["pool_id"], 2**53) > as_of
              and (p["level"] > entry if direction == "LONG"
                   else p["level"] < entry)]
    if not beyond:
        beyond = [price for confirmed_at, price in tier_swings[side]
                  if confirmed_at <= as_of
                  and (price > entry if direction == "LONG"
                       else price < entry)]
    if not beyond:
        return None
    return min(beyond) if direction == "LONG" else max(beyond)


# ---------------------------------------------------------------- collection

def collect(con) -> dict:
    """Every episode-2/3 counterfactual pullback, walked by the engine's own
    machinery. Read-only over the store, derived at analysis time."""
    con.row_factory = sqlite3.Row
    pairs = [tuple(r) for r in con.execute(
        "SELECT DISTINCT symbol, tf FROM facts WHERE kind='zone' "
        "AND algo_version=?", (ZONE_VERSION,))]
    rows, refusals = [], {}
    n_touches = n_out_of_cohort = 0

    def refuse(reason):
        refusals[reason] = refusals.get(reason, 0) + 1

    for symbol, tf in sorted(pairs):
        tf_seconds = TF_SECONDS.get(tf)
        if not tf_seconds:
            continue
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        if len(candles) < 30:
            continue
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)
        profile = costs.profile_for(symbol)

        regimes = []
        for r in store.get_facts(con, symbol, tf, "regime", REGIME_VERSION):
            regimes.append((r["confirmed_at"],
                            json.loads(r["payload"])["regime"]))
        regimes.sort()

        def regime_at(ts):
            cur = None
            for conf, reg in regimes:
                if conf > ts:
                    break
                cur = reg
            return cur

        pools, pool_broken = [], {}
        for r in store.get_facts(con, symbol, tf, "liquidity", LIQ_VERSION):
            p = json.loads(r["payload"])
            if p["event"] == "POOL":
                pools.append({"confirmed_at": r["confirmed_at"],
                              "side": p["side"],
                              "level": Decimal(p["level"]),
                              "pool_id": p["pool_id"]})
            elif p["event"] == "BROKEN":
                pool_broken[p["pool_id"]] = r["confirmed_at"]
        tier_swings = {"HIGH": [], "LOW": []}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p.get("tier") in ("INTERMEDIATE", "MAJOR"):
                tier_swings[p["type"]].append(
                    (r["confirmed_at"], Decimal(p["price"])))
        for side in tier_swings:
            tier_swings[side].sort()

        zones: dict = {}
        for r in store.get_facts(con, symbol, tf, "zone", ZONE_VERSION):
            p = json.loads(r["payload"])
            z = zones.setdefault(p["zone_id"], {"touches": []})
            rec_p = {"market_time": r["market_time"],
                     "confirmed_at": r["confirmed_at"], **p}
            if p["event"] == "TOUCH":
                z["touches"].append(rec_p)
            else:
                z[p["event"]] = rec_p

        for zone_id, z in zones.items():
            created = z.get("CREATED")
            if not created:
                continue
            broken = z.get("BROKEN")
            break_ts = broken["market_time"] if broken else 2**53
            top, bottom = Decimal(created["top"]), Decimal(created["bottom"])
            for touch in z["touches"]:
                ep = touch.get("episode")
                if ep not in EPISODES:
                    continue
                n_touches += 1
                reg = regime_at(touch["confirmed_at"])
                # The playbook table itself decides admission — imported, not
                # copied, so the cohort here can never drift from the one the
                # first-touch engine trades.
                play = playbook(created["zone_type"], reg, swept=False,
                                enabled={"PULLBACK"}, rev_evidence=[])
                if play is None:
                    n_out_of_cohort += 1
                    continue
                _strategy, direction, _base = play
                i0 = ts_index.get(touch["market_time"])
                if i0 is None:
                    refuse("NO_TOUCH_BAR")
                    continue
                # setups rejects ATR_UNAVAILABLE at the TOUCH bar, before its
                # confirmation walk ever runs. Checking only the confirm bar
                # here admitted touches the first-touch engine would have
                # refused — a cohort drift, not a bracket detail — so the
                # authority's gate is mirrored under its own name.
                if atr[i0] is None:
                    refuse("ATR_UNAVAILABLE")
                    continue
                ci = None
                for j in range(i0, min(i0 + 1 + CONFIRM_MAX_BARS,
                                       len(candles))):
                    c = candles[j]
                    if c["open_ts"] >= break_ts:
                        break              # the zone failed before it proved
                    if (c["open_ts"] + tf_seconds <= touch["confirmed_at"]
                            and j != i0):
                        continue
                    if confirms(c, direction, top, bottom):
                        ci = j
                        break
                if ci is None:
                    cancel_at = min(i0 + CONFIRM_MAX_BARS, len(candles) - 1)
                    refuse("ZONE_BROKE_UNCONFIRMED"
                           if broken and broken["market_time"]
                           <= candles[cancel_at]["open_ts"]
                           else "CONFIRMATION_TIMEOUT")
                    continue
                cb = candles[ci]
                bct = cb["open_ts"] + tf_seconds
                if atr[ci] is None:
                    refuse("ATR_UNAVAILABLE")
                    continue
                if ci + 1 >= len(candles):
                    refuse("NO_NEXT_BAR")
                    continue
                long = direction == "LONG"
                entry = Decimal(candles[ci + 1]["open"])
                if long:
                    sl = min(Decimal(cb["low"]), bottom) \
                        - SL_BUFFER_ATR * atr[ci]
                else:
                    sl = max(Decimal(cb["high"]), top) \
                        + SL_BUFFER_ATR * atr[ci]
                risk = (entry - sl) if long else (sl - entry)
                if risk <= 0:
                    refuse("INVALID_BRACKET")
                    continue
                if vetoes(confirm_bar=cb, atr_at_confirm=atr[ci],
                          entry=entry, sl=sl, tick=ticks[ci]):
                    refuse("VETOED")
                    continue
                tp_uncapped = target_level(direction, entry, bct, pools,
                                           pool_broken, tier_swings)
                if tp_uncapped is None:
                    refuse("NO_CAUSAL_TARGET")
                    continue
                cap = entry + MAX_TARGET_R * risk if long \
                    else entry - MAX_TARGET_R * risk
                tp = min(tp_uncapped, cap) if long else max(tp_uncapped, cap)
                rr = (((tp - entry) if long else (entry - tp))
                      / risk).quantize(Q2)
                if rr < MIN_RR:
                    refuse("RR_BELOW_MINIMUM")
                    continue
                if risk < MIN_RISK_COST_MULT * costs.estimated_round_trip_cost(
                        entry, atr[ci], profile, symbol=symbol,
                        tf_seconds=tf_seconds):
                    refuse("UNECONOMIC_AFTER_COSTS")
                    continue
                maker_limit = (entry - MAKER_OFFSET_R * risk) if long \
                    else (entry + MAKER_OFFSET_R * risk)
                fill = simulate_entry(candles, atr, ci + 1, entry, sl, long,
                                      entry_model=ENTRY_MODEL,
                                      maker_limit=maker_limit,
                                      maker_wait=MAKER_WAIT_BARS,
                                      profile=profile)
                if fill["status"] == "MISSED":
                    rows.append({"episode": ep, "symbol": symbol, "tf": tf,
                                 "outcome": "MISSED", "r": None, "t": bct})
                    continue
                if fill["status"] != "FILLED":
                    refuse("PENDING")
                    continue
                walked = walk_exit(candles, fill["fill_i"], sl, tp, long)
                if walked is None:
                    refuse("OPEN")
                    continue
                outcome, exit_px, j, _ambiguous = walked
                priced = settle(profile, symbol, fill["entry"], exit_px,
                                fill["risk"], long, outcome,
                                j - fill["fill_i"], tf_seconds, atr[j],
                                entry_role=fill["entry_role"])
                rows.append({"episode": ep, "symbol": symbol, "tf": tf,
                             "outcome": outcome,
                             "r": float(priced["r_mult"]), "t": bct})
    return {"rows": rows, "refusals": refusals, "touches": n_touches,
            "out_of_cohort": n_out_of_cohort}


# ------------------------------------------------------------------- grading

def summarise(rows) -> dict:
    """ignition's cell shape: counts always, interval only above the floors,
    the WIDER of symbol- and week-clustered reported (see the docstring for
    why the clustered one decides)."""
    closed = [x for x in rows if x["r"] is not None]
    missed = sum(1 for x in rows if x["outcome"] == "MISSED")
    if not closed:
        return {"n": 0, "missed": missed, "sample_ok": False}
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


def grade(con) -> dict:
    data = collect(con)
    rows = data["rows"]
    report = {
        "derived_at_analysis_time": True,   # no fact written, no gate armed
        "touches": data["touches"],
        "out_of_cohort": data["out_of_cohort"],
        "refusals": data["refusals"],
        "cells": {},
        "floor": {"min_closed": MIN_CLOSED, "min_clusters": 8,
                  "bar": ("symbol-clustered interval (the wider of symbol and "
                          "week) clear of zero — nominal n overstates "
                          "effective n here, see the module docstring")},
    }
    for ep in EPISODES:
        report["cells"][f"episode_{ep}"] = summarise(
            [x for x in rows if x["episode"] == ep])
    report["cells"]["pooled_2_and_3"] = summarise(rows)
    return report


def _print_cell(pad, c):
    if not c.get("n"):
        print(f"{pad}no closed trades · {c.get('missed', 0)} missed")
        return
    ci = c.get("ci")
    shown = f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "no honest interval"
    flag = "" if c.get("sample_ok") else "  SAMPLE TOO SMALL"
    print(f"{pad}n={c['n']} closed · {c['missed']} missed · "
          f"{c['mean_r']:+.3f} R · win {c['win_rate']:.0%} · {shown}"
          f"{' CLEARS ZERO' if c.get('clears_zero') else ''}{flag}")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    try:
        rep = grade(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return 0
    print(f"second touch — {rep['touches']} episode-2/3 touches, "
          f"{rep['out_of_cohort']} outside the playbook's regimes")
    print(f"  refusals: {rep['refusals']}")
    for name, c in rep["cells"].items():
        print(f"  {name}")
        _print_cell("    ", c)
    print(f"  floor: {rep['floor']['bar']}")
    print("NOT A GATE. Evidence is recorded, not filtered on, until it has "
          "been graded (rule 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
