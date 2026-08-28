"""Entry statistics — was the resting limit at the zone edge ADVERSELY SELECTED?
READ-ONLY: this module writes no facts, opens no orders and mutates nothing (§1).

`docs/SPEC-confirmed-entry.md` §1.3 proposes replacing the resting LIMIT at the
zone edge with MARKET on the next bar's open, and justifies it partly with a 39%
miss rate (90 of 232 orders never filled). A miss rate is not on its own an
argument. It only becomes one once you know WHICH orders missed:

  * if the limits that filled were the ones about to lose — price came back into
    the zone because the zone was failing — the limit is adversely selected and
    market entry is better on outcome, before any fee argument;
  * if the misses were the winners — price left without you because the zone
    HELD — market entry is better for a different reason (you were never wrong
    about the trade, only about the fill), and the fee argument matters more.

Nobody had measured it. This tool measures it.

Method ported from three diagnostics in the prior project — `fill_rate.py`,
`entry_rr_distortion.py`, `entry_quality_probe.py`. The method survives the port;
the plumbing does not. Those read JSONL session logs where a resting limit was
inferred from a `pending` row later followed by an `executed` row. Here the fact
store records the order lifecycle explicitly (`kind='order'`, events PLACED /
FILLED / MISSED) and the outcome separately (`kind='exec'`), so the fill rate is
counted rather than inferred.

WHAT THE NUMBERS HERE DO NOT KNOW — read before quoting any of them.

 1. PAPER OVERSTATES THE FILL RATE. `execsim` fills a limit the instant a bar's
    range contains the limit price (`fill_model: BAR_TOUCH_FULL_FILL`). There is
    no queue position, no partial fill, and no trade-through requirement: a wick
    that merely touches the price is treated as a fill for the whole size. A real
    resting order at that level might sit behind the entire book and never trade.
    Every fill rate below is therefore a CEILING, and the true miss rate is
    higher than the 39% the spec quotes, not lower.

 2. THE COUNTERFACTUAL IS NOT A RESULT. A missed order has no realised R — no
    position ever existed, so there is nothing to compare a PnL against. What can
    be measured is what price DID after the miss, by walking the stored candles
    forward under the setup's own SL/TP. Every such number is prefixed `cf_` and
    labelled COUNTERFACTUAL wherever it is printed. It is never placed beside a
    recorded result without that mark. It assumes the same bar-touch fill model
    as #1, which is the same optimism, applied consistently.

 3. THE COUNTERFACTUAL IS GROSS. `execsim` nets fees and market-exit slippage
    into `r_multiple` and records the difference as `costs_r`; the walk below
    models neither. So counterfactual R is compared against the recorded book's
    `r_gross`, never against `r_multiple`. Comparing a gross counterfactual to a
    net record would manufacture an advantage out of the accounting alone. The
    entry-side fee penalty of the proposed switch (maker -> taker) is computed
    separately and exactly, from the cost profile execsim actually recorded.

 4. THE RECORDED PLANNED-vs-REALISED R:R GAP IS STRUCTURALLY ZERO. `execsim`
    fills at the limit price by construction (`"fill_price": str(entry)`) —
    verified on the live store 2026-07-29: fill_price == limit_price for all 142
    FILLED orders, without exception. So the fill geometry the old project's
    `entry_rr_distortion.py` was built to catch CANNOT appear in v0.6 facts. That
    is a finding about the measurement, not about the strategy, and it is
    reported as such. The gap that DOES inform §1.3 is the counterfactual one:
    the next bar's open is a different price from the zone edge, so the position
    would open with different geometry than the plan claimed. That is measured.

 5. NO LOOKAHEAD (house convention 2). Every walk starts at the first candle that
    OPENS at or after the setup's `available_at` (= its `confirmed_at`), never
    before — `_first_bar_at_or_after` is the single place that decision is made,
    and it is regression-tested. `market_time` is when the bar happened;
    `confirmed_at` is the first moment the system could act on it. Nothing here
    reads a bar the order could not have traded against.

 6. LOUD FALLBACK (house convention 4). Under MIN_TRADES matched trades the
    correlation block refuses to publish a number rather than printing a
    confident-looking 0.00. A refusal is a result; a fabricated zero is not.

Floats: prices, stop distances and fills are Decimal end to end (§3). The
conversion to float happens once, at the boundary where a price ratio becomes an
R-multiple — R is dimensionless and the statistics below are means, medians and
Pearson correlations over R, where float is the right type and Decimal would be
slower and no more correct. No float touches a price in this file.

Determinism: no RNG anywhere. Records are sorted by (available_at, setup_id)
before any statistic is taken, so identical input produces byte-identical output.

Usage (from app/):
  python -m engine.entrystats
  python -m engine.entrystats --tf 1D
  python -m engine.entrystats --json
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import sys
from bisect import bisect_left
from decimal import Decimal
from pathlib import Path

from . import costs, store

ENTRYSTATS_VERSION = "entrystats-v0.3-draft"
# v0.3: current MAKER_THEN_MARKET orders rest at `maker_limit`, not at the
# plan's `entry`.  The old composite join compared plan.entry to limit_price,
# so it reported zero placed orders on the entire current book.  A crossing
# order records the plan anchor explicitly as `cross_price`; use that to claim
# the plan, then join the outcome to the FILLED event's actual price.
# v0.2: the taker-entry penalty uses the spread of the symbol's OWN venue. On
# the Coinbase default it overstated the penalty on perps by ~4x (0.20% vs
# 0.05%), and this statistic is what decides whether limit or market entries are
# better — a venue-blind spread answers that question wrong.

# Versions are PINNED here, not imported from `setups.SETUP_VERSION` /
# `execsim.EXEC_VERSION`. That is deliberate and it is not tidiness.
# This tool exists to settle an argument about ONE book: the 232 orders that
# exec-v0.7-draft placed against setup-v0.6-draft plans, which is the book
# SPEC-confirmed-entry.md §1.3 quotes its 39% miss rate from. Importing the live
# constants would make the tool follow whatever the strategy module happens to be
# mid-edit — and it already would have: on 2026-07-29 `SETUP_VERSION` read
# `setup-v0.7-draft`, a version with zero facts in the store, so every geometry
# statistic silently lost its plan and reported on n=1. A report that quietly
# changes which book it describes is worse than one that is out of date.
# Override with --setup-version / --exec-version when a new book exists.
SETUP_VERSION = "setup-v0.6-draft"
EXEC_VERSION = "exec-v0.7-draft"
SCALE_VERSION = "scale-v0.2-draft"

# Cost profile comes from `costs` rather than from `setups`, for the same reason:
# it is the profile the recorded facts were priced under, and every exec fact
# carries its `cost_manifest_hash` so the claim is checkable.
# Retained ONLY as the label for reports that predate per-venue pricing. Live
# fee arithmetic must use costs.profile_for(symbol); see the note in setups.py.
LEGACY_REPORT_PROFILE = costs.DEFAULT_COST_PROFILE


def _spread(symbol):
    """Taker-minus-maker spread for THIS symbol's venue.

    The entry-fee penalty is the cost of crossing the spread instead of resting.
    Computed with the process-wide Coinbase default it overstated the penalty on
    perps by roughly 14x — and this number feeds the entry-quality statistics
    that decide whether limit or market entries are better, so a venue-blind
    spread would answer that question wrong.
    """
    p = costs.profile_for(symbol)
    return p.taker_rate - p.maker_rate

# Fallbacks only. The real window is read from the `execution` manifest that the
# exec facts themselves point at (`execution_manifest_hash`) — see
# `_execution_window`. These constants are what exec-v0.7-draft recorded, kept so
# a store whose manifest predates that field still produces a walk rather than a
# crash, and the substitution is announced.
MAX_BARS = 100
MAX_ENTRY_BARS = 4

# House convention 4. The old project's probe refused below 10 matched trades;
# the brief here raises the bar to 30, and the higher bar is the right one: at
# n=10 the noise floor is +/-0.62, which no real feature clears, so any r that
# did clear it would be an artefact being read as a discovery.
MIN_TRADES = 30

# Noise floor for a Pearson r at sample size n: +/-1.96/sqrt(n). Inside it the
# feature is indistinguishable from random and is NOT credited. Same criterion as
# the promotion table in SPEC-confirmed-entry.md §1.4, so a factor graded here
# and a factor graded there are graded identically.
NOISE_Z = 1.96

_TFS_ORDER = ("5m", "15m", "1H", "4H", "1D", "1W")

# Walk-forward window for the counterfactual, deliberately the same as the one
# the real simulator held its positions for: a counterfactual allowed to run
# longer than the recorded book would win by patience the book was never granted,
# and that advantage would look like an entry-model improvement.
CF_MAX_BARS = MAX_BARS


def _execution_window(con, exec_version: str) -> tuple[int, int, list[str]]:
    """(max_holding_bars, max_entry_bars) as RECORDED, not as currently coded.

    Every order fact carries the hash of the `execution` manifest it was produced
    under, and that manifest holds the two windows. Reading them from there
    rather than from `execsim`'s current constants means a later edit to the
    simulator cannot retroactively change what this report says about facts that
    were written under the old numbers (§7, §8). Returns the pinned fallbacks and
    a loud warning if no manifest is reachable.
    """
    warn: list[str] = []
    row = con.execute(
        "SELECT payload FROM facts WHERE kind='order' AND algo_version=? "
        "ORDER BY market_time, confirmed_at, id LIMIT 1", (exec_version,)).fetchone()
    h = json.loads(row[0]).get("execution_manifest_hash") if row else None
    man = store.get_manifest(con, h) if h else None
    if not man:
        warn.append(
            f"no execution manifest reachable for {exec_version} — falling back to "
            f"the pinned window (hold {MAX_BARS} bars, entry {MAX_ENTRY_BARS} "
            f"bars). If the simulator's constants have changed since these facts "
            f"were written, the counterfactual window no longer matches them.")
        return MAX_BARS, MAX_ENTRY_BARS, warn
    return (int(man.get("max_holding_bars", MAX_BARS)),
            int(man.get("max_entry_bars", MAX_ENTRY_BARS)), warn)


# ------------------------------------------------------------------ primitives

def _f(x, default=None):
    """Best-effort float. Used ONLY on R-multiples and already-derived ratios."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _d(x):
    """Decimal or None. Used on every price. Never returns a float."""
    if x is None:
        return None
    try:
        return Decimal(str(x))
    except (ArithmeticError, ValueError):
        return None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r, or None when it is undefined (n<2, or either side constant).

    A constant series returns None rather than 0.0 on purpose: 0.0 reads as
    "measured, no relationship" and the truth is "not measurable" (§4)."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _summary(vals: list[float]) -> dict | None:
    """Mean/median/min/max of an R series. None on an empty series — not zero."""
    if not vals:
        return None
    ordered = sorted(vals)
    return {"n": len(vals), "mean": sum(vals) / len(vals),
            "median": statistics.median(ordered),
            "min": ordered[0], "max": ordered[-1],
            "sum": sum(vals),
            "win_rate": sum(1 for v in vals if v > 0) / len(vals)}


def _tf_sort_key(tf: str) -> tuple:
    return (_TFS_ORDER.index(tf), "") if tf in _TFS_ORDER else (len(_TFS_ORDER), tf)


# ------------------------------------------------------- no-lookahead boundary

def _first_bar_at_or_after(candle_times: list[int], available_at: int) -> int | None:
    """Index of the first candle that OPENS at or after `available_at`.

    This is the ONLY place the causality boundary is decided (house convention
    2), so it is the only place a lookahead bug can enter. A bar whose open_ts is
    strictly less than `available_at` was already in progress — or already
    finished — when the setup was confirmed; an order placed on confirmation
    could not have traded against its open, and using it would let the walk buy
    at a price that had already passed.

    `available_at` is itself a bar-close time (`touch_bar.open_ts + tf_seconds`),
    so the returned bar is the one immediately following the confirming bar, and
    its OPEN is the first price the order could possibly have transacted at.
    Returns None when the store holds no such bar yet.
    """
    i = bisect_left(candle_times, available_at)
    if i >= len(candle_times):
        return None
    return i


def walk_forward(candles: list[dict], start_i: int, *, direction: str,
                 sl: Decimal, tp: Decimal, max_bars: int = CF_MAX_BARS) -> dict:
    """Resolve a hypothetical position against stored bars. COUNTERFACTUAL.

    Rules mirror `execsim.run` exactly, and deliberately so — a counterfactual
    judged under friendlier rules than the recorded book is not a comparison:
      * SL when a bar trades through the stop, TP when it trades through the
        target, and a bar that reaches BOTH counts as SL (`same_bar_stop_target:
        STOP_FIRST`, flagged `ambiguous`). Sub-bar sequencing needs LTF data the
        store does not hold.
      * TIMEOUT at `max_bars` unresolved, exiting at that bar's close.
      * UNRESOLVED when the store runs out of bars before either happens. That is
        NOT a timeout and NOT a zero — it is missing data, and it is excluded
        from every distribution rather than counted as a flat trade.
    """
    long = direction == "LONG"
    end = min(start_i + max_bars, len(candles))
    for j in range(start_i, end):
        c = candles[j]
        hi, lo = _d(c["high"]), _d(c["low"])
        hit_sl = lo <= sl if long else hi >= sl
        hit_tp = hi >= tp if long else lo <= tp
        if hit_sl or hit_tp:
            return {"outcome": "SL" if hit_sl else "TP",
                    "exit_price": sl if hit_sl else tp,
                    "exit_bar": j, "bars_held": j - start_i,
                    "ambiguous": bool(hit_sl and hit_tp)}
    if start_i + max_bars <= len(candles):
        j = start_i + max_bars - 1
        return {"outcome": "TIMEOUT", "exit_price": _d(candles[j]["close"]),
                "exit_bar": j, "bars_held": j - start_i, "ambiguous": False}
    return {"outcome": "UNRESOLVED", "exit_price": None, "exit_bar": None,
            "bars_held": None, "ambiguous": False}


def counterfactual(candles: list[dict], available_at: int, *, direction: str,
                   entry: Decimal, sl: Decimal, tp: Decimal,
                   max_bars: int = CF_MAX_BARS) -> dict | None:
    """What the trade WOULD have done. COUNTERFACTUAL — never a recorded result.

    One walk answers two questions, because SL and TP are the same levels under
    both fill assumptions and the start bar is shared, so the OUTCOME LABEL is
    identical and only the R denominator differs:

      cf_r_plan    R if the limit had somehow filled at the planned entry. Price
                   demonstrably did NOT trade there during the entry window when
                   the order MISSED, so this is a geometry-preserving fiction:
                   read it for direction (did the thesis play out?), not as a
                   number the account could have earned.
      cf_r_market  R filling at the next bar's OPEN — the SPEC §1.3 proposal. The
                   open is a price that demonstrably traded, so no fill
                   assumption is required, but the geometry is NOT the plan's:
                   risk is measured from the open, not from the zone edge.

    Returns None when no bar exists at or after `available_at`.
    """
    times = [c["open_ts"] for c in candles]
    i = _first_bar_at_or_after(times, available_at)
    if i is None:
        return None
    # The guarantee, asserted rather than assumed. If this ever fails the walk is
    # reading a bar that had already opened when the setup confirmed.
    if candles[i]["open_ts"] < available_at:
        raise AssertionError(
            f"lookahead: bar opens {candles[i]['open_ts']} < available_at {available_at}")

    fill = _d(candles[i]["open"])
    walk = walk_forward(candles, i, direction=direction, sl=sl, tp=tp,
                        max_bars=max_bars)
    long = direction == "LONG"
    risk_plan = (entry - sl) if long else (sl - entry)
    risk_market = (fill - sl) if long else (sl - fill)

    # Geometry sanity on the market fill. A next-bar open that has already gapped
    # through the stop is not a trade with a bad R:R, it is a trade that is over
    # before it opens; averaging a -1R into it would understate how bad the gap
    # was. Same for an open already past the target. Both are counted and
    # reported, never silently folded into a mean.
    invalid = None
    if risk_market is None or risk_market <= 0:
        invalid = "STOP_ALREADY_BREACHED_AT_OPEN"
    elif (fill >= tp) if long else (fill <= tp):
        invalid = "TARGET_ALREADY_REACHED_AT_OPEN"

    out = {"fill_bar": i, "fill_open_ts": candles[i]["open_ts"],
           "cf_fill_price": str(fill),
           "cf_outcome": walk["outcome"], "cf_bars_held": walk["bars_held"],
           "cf_ambiguous": walk["ambiguous"],
           "cf_same_bar": (walk["bars_held"] == 0
                           if walk["bars_held"] is not None else None),
           "cf_market_geometry": invalid or "OK",
           "cf_rr_plan": None, "cf_rr_market": None,
           "cf_r_plan": None, "cf_r_market": None}

    reward_plan = (tp - entry) if long else (entry - tp)
    if risk_plan > 0:
        out["cf_rr_plan"] = _f(reward_plan / risk_plan)
    if invalid is None:
        out["cf_rr_market"] = _f(((tp - fill) if long else (fill - tp)) / risk_market)

    ex = walk["exit_price"]
    if ex is not None:
        move = (ex - entry) if long else (entry - ex)
        if risk_plan > 0:
            out["cf_r_plan"] = _f(move / risk_plan)
        if invalid is None:
            move_m = (ex - fill) if long else (fill - ex)
            out["cf_r_market"] = _f(move_m / risk_market)
    return out


# ------------------------------------------------------------------- loading

def _rows(con, kind: str, algo_version: str, as_of: int | None):
    """Facts of one kind/version across the whole portfolio, in causal order.

    `store.get_facts` is scoped to one symbol+tf; entry quality is a property of
    the ORDER BOOK, not of a chart, so this reads portfolio-wide the way
    `risk.py` reasons portfolio-wide. Ordering matches `store.get_facts` exactly
    (market_time, confirmed_at, id) so lifecycle events cannot be read out of
    causal order when timestamps tie.
    """
    con.row_factory = sqlite3.Row
    q = ("SELECT symbol, tf, market_time, confirmed_at, payload FROM facts "
         "WHERE kind=? AND algo_version=?")
    args: list = [kind, algo_version]
    if as_of is not None:
        q += " AND confirmed_at<=?"
        args.append(as_of)
    q += " ORDER BY market_time, confirmed_at, id"
    return con.execute(q, args).fetchall()


def _plans_elsewhere(con, keys: set, tried: list[str]) -> list[tuple[str, int]]:
    """Which OTHER setup versions claim these order keys.

    Diagnostic only, and it earns its place: `setup_id` is
    `symbol|tf|strategy|zone_id`, which is stable ACROSS strategy versions, and
    `execsim` did not bump its own version when `setups.py` went to v0.7. So the
    store now holds two books of order facts under one `algo_version`, sharing
    setup_ids. Joining on setup_id alone silently merges them — observed on
    2026-07-29 as an order that was both FILLED and MISSED. This answers the
    question that follows from the loud warning: 'so whose orders are those?'
    """
    found: dict[str, int] = {}
    for r in con.execute(
            "SELECT algo_version, confirmed_at, payload FROM facts WHERE kind='setup'"):
        if r[0] in tried:
            continue
        p = json.loads(r[2])
        if p.get("state") == "VALIDATED" and \
                (p.get("setup_id"), r[1], p.get("entry")) in keys:
            found[r[0]] = found.get(r[0], 0) + 1
    return sorted(found.items())


def _plan_anchor(order: dict):
    """The plan price an order was created from, not necessarily its limit.

    MAKER_THEN_MARKET records a better passive `limit_price` and keeps the
    approved setup price in `cross_price`. Older direct-limit facts have no
    cross price, where the limit itself remains the correct anchor.
    """
    return order.get("cross_price") or order.get("limit_price")


def load_orders(con, *, setup_version: str = SETUP_VERSION,
                exec_version: str = EXEC_VERSION, symbol: str | None = None,
                tf: str | None = None, strategy: str | None = None,
                as_of: int | None = None,
                with_counterfactual: bool = True,
                max_bars: int | None = None) -> tuple[list[dict], dict, list[str]]:
    """One record per VALIDATED plan, joined to its order lifecycle, its outcome
    and (optionally) its counterfactual walk. READ-ONLY.

    THE JOIN KEY IS (setup_id, available_at, plan_anchor), NOT setup_id.
    `setup_id` is `symbol|tf|strategy|zone_id` and carries no version, so the
    same id names a v0.6 plan and a v0.7 plan for the same zone. `execsim` did
    not bump its own version when `setups.py` moved to v0.7, so both books' order
    facts now sit under `exec-v0.7-draft`. Joining on setup_id alone merged them
    — observed on 2026-07-29 as a single "order" that was simultaneously FILLED
    and MISSED, and as a fill rate of 74% for a book whose real rate is 61%. The
    The anchor is `cross_price` for MAKER_THEN_MARKET and `limit_price` for
    direct limits; both equal the approved plan entry. `available_at` equals
    plan.confirmed_at, so the composite reconstructs one book cleanly.

    Driving off PLANS rather than off orders is the other half of that: the
    question is "of the setups this version validated, how many filled", and a
    denominator assembled from whatever order facts happen to be in the table
    answers a different question.

    Returns (records, counts, warnings). Records are sorted by
    (available_at, setup_id) so every downstream statistic is order-stable.
    """
    warnings: list[str] = []
    hold_bars, entry_bars, w = _execution_window(con, exec_version)
    warnings.extend(w)
    if max_bars is None:
        max_bars = hold_bars

    # Plans. A setup_id carries several states (FORMING, VALIDATED, EXPIRED,
    # CANCELLED) — VALIDATED is the tradeable one and the only one execsim acts
    # on. Last VALIDATED fact in causal order wins, which is what `execsim` does
    # (`setups[p["setup_id"]] = ...` over the same ordering): re-runs after new
    # candles can re-emit a plan with a different ATR-derived stop, and the book
    # that was actually simulated is the latest one.
    plans: dict[str, dict] = {}
    # FORMING is kept separately because it is the only place `zone_strength` and
    # the approach distance are recorded. It is confirmed BEFORE the touch, so
    # reading it introduces no lookahead — but only the ones confirmed at or
    # before the plan are eligible, which is enforced at attach time below.
    forming: dict[str, list[dict]] = {}
    # A SCALE_IN add is a real order in the same book under its own version;
    # dropping it would silently shrink the denominator of the fill rate.
    # The default report is deliberately pinned to the legacy study. An
    # explicit request for the live setup generation must bring its live scale
    # generation too; otherwise every add is reported as an unclaimed order.
    from . import scalein, setups as live_setups
    scale_version = (scalein.SCALE_VERSION
                     if setup_version == live_setups.SETUP_VERSION
                     else SCALE_VERSION)
    versions = [setup_version, scale_version]
    for ver in versions:
        for r in _rows(con, "setup", ver, as_of):
            p = json.loads(r["payload"])
            rec = {"symbol": r["symbol"], "tf": r["tf"],
                   "setup_confirmed_at": r["confirmed_at"],
                   "setup_market_time": r["market_time"],
                   "setup_algo_version": ver, **p}
            if p.get("state") == "VALIDATED":
                plans[p["setup_id"]] = rec
            elif p.get("state") == "FORMING":
                forming.setdefault(p["setup_id"], []).append(rec)

    orders: dict[tuple, dict] = {}
    for r in _rows(con, "order", exec_version, as_of):
        p = json.loads(r["payload"])
        key = (p["setup_id"], p.get("available_at"), _plan_anchor(p))
        slot = orders.setdefault(key, {"symbol": r["symbol"], "tf": r["tf"],
                                       "events": {}})
        slot["events"][p["event"]] = {"confirmed_at": r["confirmed_at"],
                                      "market_time": r["market_time"], **p}

    outcomes: dict[tuple, dict] = {}
    for r in _rows(con, "exec", exec_version, as_of):
        p = json.loads(r["payload"])
        outcomes[(p["setup_id"], p.get("available_at"), p.get("entry"))] = {
            "exit_confirmed_at": r["confirmed_at"], **p}

    counts = {"plans": len(plans), "placed": 0, "filled": 0, "missed": 0,
              "unresolved_order": 0, "no_order": 0, "unclaimed_orders": 0,
              "no_candles": 0, "cf_walked": 0, "filtered_out": 0,
              "max_holding_bars": max_bars, "max_entry_bars": entry_bars}
    candle_cache: dict[tuple[str, str], list[dict]] = {}
    claimed: set = set()

    records: list[dict] = []
    for sid in sorted(plans):
        plan = plans[sid]
        key = (sid, plan["setup_confirmed_at"], plan.get("entry"))
        o = orders.get(key)
        if o is None:
            # No order was ever placed for this plan — execsim has not run over
            # it yet, or it fell in the PENDING branch (not enough bars). Not a
            # miss: counting it as one would inflate the miss rate with orders
            # that were never live.
            counts["no_order"] += 1
            continue
        claimed.add(key)
        ev = o["events"]
        placed = ev.get("PLACED")
        if placed is None:
            warnings.append(
                f"{sid}: order events exist with no PLACED event; excluded from "
                f"the fill rate because its denominator is unknown")
            continue
        sym, t = plan["symbol"], plan["tf"]
        if symbol and sym != symbol:
            counts["filtered_out"] += 1
            continue
        if tf and t != tf:
            counts["filtered_out"] += 1
            continue
        strat = plan.get("strategy")
        if strategy and strat != strategy:
            counts["filtered_out"] += 1
            continue
        filled = "FILLED" in ev
        missed = "MISSED" in ev
        fill_event = ev.get("FILLED", {})
        # A crossed order settles from the actual market fill, not from either
        # the plan anchor or the resting maker limit. Joining to the filled
        # event makes that distinction explicit and still keeps the version-
        # ambiguous legacy books separate through available_at.
        ex = outcomes.get((sid, plan["setup_confirmed_at"],
                           fill_event.get("fill_price"))) if filled else None
        counts["placed"] += 1
        counts["filled"] += int(filled)
        counts["missed"] += int(missed)
        if not filled and not missed:
            counts["unresolved_order"] += 1

        # Causal FORMING attach: the latest approach fact confirmed at or before
        # the plan itself. A later FORMING fact for the same zone describes a
        # different approach and could not have informed this entry (§5).
        prior = [x for x in forming.get(sid, [])
                 if x["setup_confirmed_at"] <= plan["setup_confirmed_at"]]
        fm = max(prior, key=lambda x: (x["setup_confirmed_at"],
                                       x["setup_market_time"])) if prior else {}

        rec: dict = {
            "setup_id": sid, "symbol": sym, "tf": t,
            "strategy": strat,
            "direction": plan.get("direction"),
            "regime": plan.get("regime"),
            "rank": plan.get("rank"),
            "available_at": placed.get("available_at", placed["confirmed_at"]),
            "state": "FILLED" if filled else ("MISSED" if missed else "UNRESOLVED"),
            "planned_rr": _f(plan.get("rr")),
            "entry": plan.get("entry"),
            "sl": plan.get("sl"),
            "tp": plan.get("tp"),
            "limit_price": placed.get("limit_price"),
            "fill_price": fill_event.get("fill_price"),
            "bars_to_fill": fill_event.get("bars_to_fill"),
            "outcome": (ex or {}).get("outcome"),
            "r_multiple": _f((ex or {}).get("r_multiple")),
            "r_gross": _f((ex or {}).get("r_gross")),
            "costs_r": _f((ex or {}).get("costs_r")),
            "mae_r": _f((ex or {}).get("mae_r")),
            "mfe_r": _f((ex or {}).get("mfe_r")),
            "bars_held": (ex or {}).get("bars_held"),
            "ambiguous_bar": (ex or {}).get("ambiguous_bar"),
            "had_forming": bool(prior),
            "zone_strength": _f(fm.get("zone_strength")),
            "distance_atr": _f(fm.get("distance_atr")),
            "cf": None,
        }

        # Recomputed plan geometry, at full precision. The `rr` on the fact is
        # quantised to 2dp at emit; recomputing from the levels separates a
        # quantisation difference from a real geometry difference.
        e, s_, tp_ = _d(rec["entry"]), _d(rec["sl"]), _d(rec["tp"])
        if e is not None and s_ is not None and tp_ is not None and rec["direction"]:
            long = rec["direction"] == "LONG"
            risk = (e - s_) if long else (s_ - e)
            reward = (tp_ - e) if long else (e - tp_)
            rec["risk_price_units"] = str(risk)
            rec["stop_width_pct"] = _f(risk / e * 100) if e > 0 else None
            rec["plan_rr_exact"] = _f(reward / risk) if risk > 0 else None
            fp = _d(rec["fill_price"])
            if fp is not None and risk > 0:
                risk_f = (fp - s_) if long else (s_ - fp)
                reward_f = (tp_ - fp) if long else (fp - tp_)
                rec["realised_rr"] = _f(reward_f / risk_f) if risk_f > 0 else None
                rec["fill_equals_limit"] = (fp == _d(rec["limit_price"]))
                # Entry-side fee penalty of SPEC §1.3, in R, computed from the
                # cost profile execsim actually recorded rather than from the
                # spec's quoted rates — so the number belongs to this book.
                rec["taker_entry_penalty_r"] = _f(
                    _spread(rec["symbol"]) * fp / risk)

            if with_counterfactual:
                key = (sym, t)
                if key not in candle_cache:
                    candle_cache[key] = [dict(c) for c in
                                         store.get_candles(con, sym, t)]
                cands = candle_cache[key]
                cf = counterfactual(cands, rec["available_at"],
                                    direction=rec["direction"], entry=e, sl=s_,
                                    tp=tp_, max_bars=max_bars)
                if cf is None:
                    counts["no_candles"] += 1
                else:
                    counts["cf_walked"] += 1
                    # The taker penalty under the PROPOSED model is charged on
                    # the open, not on the zone edge, and against the market
                    # risk — different denominator, so it is computed here too.
                    fillm = _d(cf["cf_fill_price"])
                    riskm = (fillm - s_) if long else (s_ - fillm)
                    cf["cf_taker_entry_penalty_r"] = (
                        _f(_spread(rec["symbol"])
                           * fillm / riskm) if riskm > 0 else None)
                rec["cf"] = cf
        records.append(rec)

    records.sort(key=lambda r: (r["available_at"], r["setup_id"]))

    unclaimed = {k for k, v in orders.items()
                 if k not in claimed and "PLACED" in v["events"]}
    counts["unclaimed_orders"] = len(unclaimed)
    if unclaimed:
        # One aggregated warning, not one line per order — 100 identical lines
        # would bury the thing they are trying to say. And name WHERE those
        # orders' plans live, because the failure this catches (two books sharing
        # one exec algo_version) otherwise reads as a quiet, plausible number.
        elsewhere = _plans_elsewhere(con, unclaimed, versions)
        extra = ("" if not elsewhere else
                 " Their plans live under: "
                 + ", ".join(f"{v} ({n})" for v, n in elsewhere) + ".")
        warnings.append(
            f"{len(unclaimed)} PLACED order(s) under {exec_version} belong to no "
            f"VALIDATED plan in {'/'.join(versions)} and are EXCLUDED from every "
            f"number here, including the fill rate.{extra} If that version is the "
            f"book you meant to read, pass --setup-version.")
    if counts["no_order"]:
        warnings.append(
            f"{counts['no_order']} VALIDATED plan(s) in {setup_version} have no "
            f"matching PLACED order — execsim has not simulated them, or they fell "
            f"in its PENDING branch. They are NOT counted as misses.")
    if counts["unresolved_order"]:
        warnings.append(
            f"{counts['unresolved_order']} order(s) PLACED with neither FILLED nor "
            f"MISSED — still live at the end of data. Excluded from the fill-rate "
            f"denominator; they are not misses.")
    if counts["no_candles"]:
        warnings.append(
            f"{counts['no_candles']} order(s) have no stored bar at or after their "
            f"available_at — no counterfactual walk is possible for them.")
    return records, counts, warnings


# --------------------------------------------------------------- measurements

def fill_rate(records: list[dict], max_entry_bars: int = MAX_ENTRY_BARS) -> dict:
    """1. filled / (filled + MISSED), overall and per timeframe.

    CEILING, not an estimate. See caveat #1 in the module docstring: the paper
    fill model fills on touch with no queue position, so a real book fills less
    often than this and the 39% miss rate in SPEC §1.3 is a FLOOR on the miss
    rate. That direction matters — it strengthens the case for market entry
    rather than weakening it.
    """
    def _one(rs: list[dict]) -> dict:
        filled = sum(1 for r in rs if r["state"] == "FILLED")
        missed = sum(1 for r in rs if r["state"] == "MISSED")
        live = sum(1 for r in rs if r["state"] == "UNRESOLVED")
        denom = filled + missed
        return {"placed": len(rs), "filled": filled, "missed": missed,
                "still_live": live,
                "resolved": denom,
                "fill_rate_ceiling": (filled / denom) if denom else None,
                "miss_rate_floor": (missed / denom) if denom else None}

    by_tf: dict = {}
    for t in sorted({r["tf"] for r in records}, key=_tf_sort_key):
        by_tf[t] = _one([r for r in records if r["tf"] == t])
    return {"overall": _one(records), "by_tf": by_tf,
            "model": "BAR_TOUCH_FULL_FILL (paper; no queue position, no partial "
                     "fill, no trade-through) — every rate here is a CEILING",
            "max_entry_bars": max_entry_bars}


def adverse_selection(records: list[dict]) -> dict:
    """2. Were the limits that FILLED the ones about to lose?

    A missed order has no realised R, so PnL cannot be compared directly. What is
    compared instead:
      * FILLED — recorded outcome distribution and recorded GROSS R (`r_gross`,
        not `r_multiple`: the counterfactual models no costs, so the recorded net
        would be the wrong side of the comparison — see caveat #3);
      * MISSED — COUNTERFACTUAL outcome distribution from walking the stored
        candles forward under the setup's own SL/TP, plus counterfactual R under
        both fill assumptions.

    The verdict is a comparison of outcome DISTRIBUTIONS, not of a recorded
    result against a counterfactual one. Every missed-side number is marked.
    """
    filled = [r for r in records if r["state"] == "FILLED" and r["outcome"]]
    missed = [r for r in records if r["state"] == "MISSED"]

    def _dist(labels: list[str]) -> dict:
        out: dict = {}
        for lb in labels:
            out[lb] = out.get(lb, 0) + 1
        return {k: out[k] for k in sorted(out)}

    filled_outcomes = _dist([r["outcome"] for r in filled])
    filled_gross = _summary([r["r_gross"] for r in filled
                             if r["r_gross"] is not None])
    filled_net = _summary([r["r_multiple"] for r in filled
                           if r["r_multiple"] is not None])

    cfs = [r["cf"] for r in missed if r["cf"]]
    resolved = [c for c in cfs if c["cf_outcome"] in ("TP", "SL", "TIMEOUT")]
    cf_outcomes = _dist([c["cf_outcome"] for c in cfs])
    cf_r_plan = _summary([c["cf_r_plan"] for c in resolved
                          if c["cf_r_plan"] is not None])
    cf_r_market = _summary([c["cf_r_market"] for c in resolved
                            if c["cf_r_market"] is not None])

    # The comparison that answers the question. Win rate on the FILLED book is a
    # recorded fact; win rate on the MISSED book is a counterfactual. Naming them
    # apart in the payload is not decoration — it is house convention 6.
    f_res = [r for r in filled if r["outcome"] in ("TP", "SL", "TIMEOUT")]
    filled_tp_rate = (sum(1 for r in f_res if r["outcome"] == "TP") / len(f_res)
                      if f_res else None)
    cf_tp_rate = (sum(1 for c in resolved if c["cf_outcome"] == "TP") / len(resolved)
                  if resolved else None)

    verdict = _adverse_verdict(len(f_res), len(resolved), filled_tp_rate, cf_tp_rate,
                               filled_gross, cf_r_plan)
    return {
        "filled": {"n": len(filled), "recorded_outcomes": filled_outcomes,
                   "recorded_tp_rate": filled_tp_rate,
                   "recorded_r_gross": filled_gross,
                   "recorded_r_net": filled_net},
        "missed_COUNTERFACTUAL": {
            "n": len(missed), "walked": len(cfs), "resolved": len(resolved),
            "cf_outcomes": cf_outcomes, "cf_tp_rate": cf_tp_rate,
            "cf_r_plan_geometry": cf_r_plan,
            "cf_r_market_next_open": cf_r_market,
            "label": "COUNTERFACTUAL — no position ever existed; these are walks "
                     "over stored candles under the setup's own SL/TP, gross of "
                     "all costs"},
        "verdict": verdict,
    }


def _adverse_verdict(n_filled, n_missed, filled_tp, cf_tp, filled_r, cf_r) -> dict:
    """The one-line answer, phrased so a counterfactual can never be mistaken for
    a record and a small sample can never be mistaken for a finding."""
    if n_filled < MIN_TRADES or n_missed < MIN_TRADES:
        return {"code": "INSUFFICIENT",
                "text": (f"{n_filled} resolved fills and {n_missed} resolved "
                         f"counterfactual misses — below the {MIN_TRADES}-trade "
                         f"floor on at least one side. No adverse-selection "
                         f"verdict. This is a refusal, not a finding of 'no "
                         f"difference'.")}
    d_tp = cf_tp - filled_tp
    d_r = (cf_r["mean"] - filled_r["mean"]) if (cf_r and filled_r) else None
    if d_tp > 0.05 and (d_r is None or d_r > 0):
        code = "ADVERSELY_SELECTED"
        text = (f"The limits that FILLED were the worse trades. Recorded target "
                f"rate on fills {filled_tp:.1%} vs {cf_tp:.1%} counterfactual on "
                f"the misses (+{100 * d_tp:.1f}pp). Price came back to the zone "
                f"edge because the zone was FAILING; when it held, the order was "
                f"left behind. Market-on-next-open is better on OUTCOME, before "
                f"any argument about the miss rate.")
    elif d_tp < -0.05:
        code = "FAVOURABLY_SELECTED"
        text = (f"The limits that filled were the BETTER trades: recorded target "
                f"rate {filled_tp:.1%} vs {cf_tp:.1%} counterfactual on the "
                f"misses ({100 * d_tp:.1f}pp). The resting limit is selecting "
                f"FOR quality, so switching to market entry buys throughput at "
                f"the cost of per-trade quality — the §1.3 trade-off is real and "
                f"points the other way.")
    else:
        code = "NOT_SELECTED"
        text = (f"No material selection either way: recorded target rate on fills "
                f"{filled_tp:.1%} vs {cf_tp:.1%} counterfactual on the misses "
                f"({100 * d_tp:+.1f}pp, inside the +/-5pp band). The misses are "
                f"neither the winners nor the losers — the limit is not choosing, "
                f"it is only thinning. §1.3 cannot be justified on adverse "
                f"selection; it has to stand on throughput and on the same-bar "
                f"number instead.")
    return {"code": code, "text": text, "delta_tp_rate": d_tp,
            "delta_mean_r_COUNTERFACTUAL": d_r}


def rr_distortion(records: list[dict]) -> dict:
    """3. Planned R:R against the R:R the ACTUAL fill implies, on the same SL/TP.

    Two answers, and the first one is about the measurement rather than about the
    book. `execsim` fills at the limit price by construction, so on v0.6 facts
    realised R:R == planned R:R for every filled order and the gap the old
    project's `entry_rr_distortion.py` existed to catch cannot appear. Reporting
    that as "no distortion detected" would be a confident-looking zero (§4), so
    it is reported as STRUCTURALLY_ZERO with the reason attached.

    The gap that DOES bear on SPEC §1.3 is the counterfactual one: the next bar's
    open is a different price from the zone edge, so under the proposed entry the
    position opens with geometry the plan never described. That is the number
    below, and it is labelled COUNTERFACTUAL.
    """
    have_plan = [r for r in records if r.get("plan_rr_exact") is not None]
    filled = [r for r in have_plan if r.get("realised_rr") is not None]

    quant = [abs(r["realised_rr"] - r["planned_rr"]) for r in filled
             if r["planned_rr"] is not None]
    geom = [abs(r["realised_rr"] - r["plan_rr_exact"]) for r in filled]
    all_at_limit = all(r.get("fill_equals_limit") for r in filled) if filled else None
    recorded_note = (
        "Every recorded fill equals its resting limit, so realised geometry "
        "equals planned geometry apart from the plan's 2dp rr field."
        if all_at_limit else
        "Recorded fills include prices away from the resting maker limit. "
        "The realised distribution uses each actual fill against the original "
        "structural stop and target; this is measured execution distortion, "
        "not a counterfactual."
    )

    cf_pairs = [(r["plan_rr_exact"], r["cf"]["cf_rr_market"], r)
                for r in have_plan
                if r["cf"] and r["cf"].get("cf_rr_market") is not None]
    cf_gap = [(b - a) for a, b, _ in cf_pairs]
    cf_ratio = [(b / a) for a, b, _ in cf_pairs if a > 0]
    bad_geom = {}
    for r in have_plan:
        if r["cf"]:
            g = r["cf"]["cf_market_geometry"]
            if g != "OK":
                bad_geom[g] = bad_geom.get(g, 0) + 1

    return {
        "recorded": {
            "n_filled_with_plan": len(filled),
            "fill_price_equals_limit_price_for_all": all_at_limit,
            "max_abs_gap_vs_exact_plan_rr": max(geom) if geom else None,
            "max_abs_gap_vs_recorded_rr_field": max(quant) if quant else None,
            "planned_rr": _summary([r["plan_rr_exact"] for r in filled]),
            "realised_rr": _summary([r["realised_rr"] for r in filled]),
            "status": "STRUCTURALLY_ZERO" if all_at_limit else "MEASURED",
            "note": recorded_note,
        },
        "counterfactual_market_next_open": {
            "n": len(cf_pairs),
            "label": "COUNTERFACTUAL — geometry the SPEC §1.3 entry would open with",
            "planned_rr": _summary([a for a, _, _ in cf_pairs]),
            "cf_realised_rr": _summary([b for _, b, _ in cf_pairs]),
            "gap": _summary(cf_gap),
            "ratio_realised_over_planned": _summary(cf_ratio),
            "share_below_1r": (sum(1 for _, b, _ in cf_pairs if b < 1.0) / len(cf_pairs)
                               if cf_pairs else None),
            "share_collapsed_below_half_plan":
                (sum(1 for a, b, _ in cf_pairs if a > 0 and b < a * 0.5) / len(cf_pairs)
                 if cf_pairs else None),
            "share_below_setup_min_rr_1_5":
                (sum(1 for _, b, _ in cf_pairs if b < 1.5) / len(cf_pairs)
                 if cf_pairs else None),
            "unopenable_geometry": bad_geom,
        },
    }


# At-entry features: everything below is knowable at or before the moment the
# position opens, so a correlation against realised R is not leakage. `rank`,
# `planned_rr` and `stop_width_pct` come off the setup fact; `zone_strength` and
# `distance_atr` come off the earlier FORMING fact for the same setup_id, which is
# confirmed BEFORE the touch. `bars_to_fill` is known at the fill itself.
_AT_ENTRY = (
    ("planned_rr", "setup fact `rr` — reward/risk the plan claimed"),
    ("rank", "setup fact `rank` — the 0-100 confluence score (NOT a probability)"),
    ("stop_width_pct", "|entry-sl|/entry as a percentage — how tight the stop is"),
    ("bars_to_fill", "bars the limit rested before it filled (0-3)"),
    ("zone_strength", "zones.py strength, via the FORMING fact (partial coverage)"),
    ("distance_atr", "ATR distance when FORMING fired (partial coverage)"),
    ("is_short", "direction == SHORT"),
    ("is_reversal", "strategy == REVERSAL"),
    ("had_forming", "an approach was tracked before the touch"),
)

# Post-entry PATH features. These are outcomes of the trade, not inputs to it.
# The source probe (`entry_quality_probe.py`) deliberately excluded max adverse /
# favourable excursion as leakage, and that judgement is kept: they are reported
# here because the brief asks for them, under a heading that says they describe
# the trade rather than predict it. A gate built on any of these would be a
# time machine.
_POST_ENTRY = (
    ("mae_r", "max adverse excursion in R (LEAKAGE — known only after the fact)"),
    ("mfe_r", "max favourable excursion in R (LEAKAGE)"),
    ("bars_held", "bars from fill to exit (LEAKAGE)"),
    ("ambiguous_bar", "SL and TP both reached on one bar (LEAKAGE)"),
)


def _feature(r: dict, name: str):
    if name == "is_short":
        return 1.0 if r["direction"] == "SHORT" else 0.0
    if name == "is_reversal":
        return 1.0 if r["strategy"] == "REVERSAL" else 0.0
    if name == "had_forming":
        return 1.0 if r["had_forming"] else 0.0
    if name == "ambiguous_bar":
        v = r.get("ambiguous_bar")
        return None if v is None else (1.0 if v else 0.0)
    return _f(r.get(name))


def entry_probe(records: list[dict]) -> dict:
    """4. Does anything visible at entry correlate with realised R?

    Judged against the noise floor +/-1.96/sqrt(n) — the same bar SPEC §1.4 sets
    for promoting a confluence factor to a gate, so a feature graded here and a
    factor graded there are graded identically. Nothing here is wired into
    scoring, sizing or filtering; it is evidence, recorded, per house convention
    3 and the rule already written into `swings.py`.

    Refuses below MIN_TRADES rather than publishing a correlation nobody should
    act on (§4). At n=20 the floor is +/-0.44 — wide enough that a real effect
    would fail to clear it and a spurious one would sail through.
    """
    closed = [r for r in records
              if r["state"] == "FILLED" and r["r_multiple"] is not None]
    n = len(closed)
    out: dict = {"n_closed": n, "min_trades": MIN_TRADES,
                 "noise_floor": None, "sufficient": False, "refusal": None,
                 "at_entry": [], "post_entry_path": [], "by_group": {}}
    if n < MIN_TRADES:
        out["refusal"] = (
            f"{n} closed trade(s) — below the {MIN_TRADES}-trade floor. No "
            f"correlation is reported. This is a refusal, not a measurement of "
            f"no relationship.")
        return out
    out["sufficient"] = True
    floor = NOISE_Z / math.sqrt(n)
    out["noise_floor"] = floor
    ys_all = [r["r_multiple"] for r in closed]

    def _grade(spec):
        rows = []
        for name, note in spec:
            xs, ys = [], []
            for r, y in zip(closed, ys_all):
                v = _feature(r, name)
                if v is not None:
                    xs.append(v)
                    ys.append(y)
            cov = len(xs)
            # The floor belongs to the FEATURE's sample, not to the book's.
            # zone_strength is recorded on only 100 of the 142 closed trades
            # (it comes off the FORMING fact, and not every setup had one), and
            # judging its r against the n=142 floor of +/-0.16 instead of its own
            # +/-0.20 promoted it from noise to a finding. Same trap the source
            # probe avoided by reporting per-feature coverage next to r.
            f_floor = NOISE_Z / math.sqrt(cov) if cov >= 2 else None
            r_out = _pearson(xs, ys) if cov >= MIN_TRADES else None
            if cov < MIN_TRADES:
                verdict = f"REFUSED — {cov} of {n} trades carry this feature (<{MIN_TRADES})"
            elif r_out is None:
                verdict = "not measurable — the feature is constant here"
            elif abs(r_out) >= f_floor:
                verdict = "above noise"
            else:
                verdict = "indistinguishable from random"
            rows.append({
                "feature": name, "note": note, "coverage": cov,
                "noise_floor": f_floor, "r_outcome": r_out,
                "clears_noise": (r_out is not None and f_floor is not None
                                 and abs(r_out) >= f_floor),
                "verdict": verdict,
            })
        rows.sort(key=lambda d: (-(abs(d["r_outcome"]) if d["r_outcome"] is not None
                                   else -1.0), d["feature"]))
        return rows

    out["at_entry"] = _grade(_AT_ENTRY)
    out["post_entry_path"] = _grade(_POST_ENTRY)

    # Categoricals get group means rather than a correlation — a Pearson r
    # against an arbitrary label encoding would be an artefact of the encoding.
    groups: dict = {}
    for key in ("tf", "strategy", "direction", "regime", "outcome"):
        g: dict = {}
        for r in closed:
            k = str(r.get(key))
            g.setdefault(k, []).append(r["r_multiple"])
        groups[key] = {k: {"n": len(v), "mean_r": sum(v) / len(v),
                           "win_rate": sum(1 for x in v if x > 0) / len(v),
                           "sufficient": len(v) >= MIN_TRADES}
                       for k, v in sorted(g.items())}
    out["by_group"] = groups
    return out


def same_bar_resolution(records: list[dict]) -> dict:
    """5. What fraction of fills resolve on the bar that filled them?

    The headline metric of the whole program. SPEC §0 measures it as 59% of
    STOP-OUTS landing on the trigger bar (73 of 124), and SPEC §6 step 4 makes it
    the pass/fail gate for the confirmation change. Two different denominators
    get quoted for it, so both are computed here and named apart:

      same_bar_resolution_rate  bars_held == 0 over ALL fills
      same_bar_stop_out_rate    bars_held == 0 over SL fills only  <- the 59%

    The counterfactual column answers the question §1.3 actually turns on: does
    entering on the NEXT bar's open move the number? It cannot be read as a
    result — the trades it describes were never taken.
    """
    def _one(rs: list[dict]) -> dict:
        fills = [r for r in rs if r["state"] == "FILLED" and r["bars_held"] is not None]
        sls = [r for r in fills if r["outcome"] == "SL"]
        same = [r for r in fills if r["bars_held"] == 0]
        same_sl = [r for r in sls if r["bars_held"] == 0]
        cf = [r["cf"] for r in rs
              if r["cf"] and r["cf"]["cf_bars_held"] is not None]
        cf_sl = [c for c in cf if c["cf_outcome"] == "SL"]
        cf_same = [c for c in cf if c["cf_bars_held"] == 0]
        cf_same_sl = [c for c in cf_sl if c["cf_bars_held"] == 0]
        return {
            "n_fills": len(fills), "n_same_bar": len(same),
            "same_bar_resolution_rate": (len(same) / len(fills)) if fills else None,
            "n_stop_outs": len(sls), "n_same_bar_stop_outs": len(same_sl),
            "same_bar_stop_out_rate": (len(same_sl) / len(sls)) if sls else None,
            "cf_n": len(cf),
            "cf_same_bar_resolution_rate_COUNTERFACTUAL":
                (len(cf_same) / len(cf)) if cf else None,
            "cf_same_bar_stop_out_rate_COUNTERFACTUAL":
                (len(cf_same_sl) / len(cf_sl)) if cf_sl else None,
        }

    by_tf: dict = {}
    for t in sorted({r["tf"] for r in records}, key=_tf_sort_key):
        by_tf[t] = _one([r for r in records if r["tf"] == t])
    return {"overall": _one(records), "by_tf": by_tf,
            "counterfactual_note": (
                "cf_* columns walk EVERY order — filled and missed alike — from "
                "the open of the first bar at or after available_at, under the "
                "SPEC §1.3 entry. They are counterfactual and gross of costs.")}


def book_counterfactual(records: list[dict]) -> dict:
    """The whole book re-run under SPEC §1.3 entry. COUNTERFACTUAL, gross.

    This is the number the decision actually turns on: not "what happened to the
    90 misses", but "what would all 232 orders have done if entry had been market
    on the next open". Compared against the recorded book's GROSS R, because the
    walk models no costs (caveat #3). The entry-side fee the switch would add is
    quantified beside it, in R, from the cost profile execsim recorded — so the
    net direction of the change is visible rather than assumed.
    """
    cf = [r["cf"] for r in records if r["cf"]]
    resolved = [c for c in cf if c["cf_outcome"] in ("TP", "SL", "TIMEOUT")]
    usable = [c for c in resolved if c["cf_r_market"] is not None]
    recorded = [r for r in records
                if r["state"] == "FILLED" and r["r_gross"] is not None]

    dist: dict = {}
    for c in cf:
        dist[c["cf_outcome"]] = dist.get(c["cf_outcome"], 0) + 1
    # Which way the excluded orders bias the answer. An open already past the
    # TARGET would have been an instant winner; one already past the STOP an
    # instant loser. Dropping both is unavoidable (neither has a definable R off
    # its own fill), but the counts must be shown side by side, because dropping
    # more winners than losers makes the counterfactual look WORSE than it was —
    # and a bias that flatters the status quo is still a bias.
    bad: dict = {}
    for c in cf:
        g = c["cf_market_geometry"]
        if g != "OK":
            bad[g] = bad.get(g, 0) + 1
    penalties = [c["cf_taker_entry_penalty_r"] for c in usable
                 if c.get("cf_taker_entry_penalty_r") is not None]
    pen = _summary(penalties)
    cf_r = _summary([c["cf_r_market"] for c in usable])
    rec_r = _summary([r["r_gross"] for r in recorded])
    net_after_fee = None
    if cf_r and pen:
        # Subtract only the fee DELTA (taker minus maker on the entry leg). The
        # exit leg and the exit slippage are unchanged by §1.3, so charging them
        # again here would double-count what execsim already charged the
        # recorded book.
        net_after_fee = cf_r["mean"] - pen["mean"]
    return {
        "label": "COUNTERFACTUAL — every order re-entered at the next bar's open; "
                 "gross of costs, bar-touch SL/TP, same 100-bar window",
        "n_orders": len(records), "n_walked": len(cf), "n_resolved": len(resolved),
        "n_usable": len(usable),
        "cf_outcomes": {k: dist[k] for k in sorted(dist)},
        "cf_r_gross": cf_r,
        "recorded_r_gross_filled_only": rec_r,
        "cf_taker_entry_penalty_r": pen,
        "cf_mean_r_after_entry_fee_delta": net_after_fee,
        "unopenable_geometry": {k: bad[k] for k in sorted(bad)},
        "exclusion_bias": (
            "excluding %d instant winners and %d instant losers — the "
            "counterfactual mean is understated, not flattered"
            % (bad.get("TARGET_ALREADY_REACHED_AT_OPEN", 0),
               bad.get("STOP_ALREADY_BREACHED_AT_OPEN", 0))) if bad else None,
    }


# ------------------------------------------------------------------- report

def report(con=None, *, db_path: Path | None = None,
           setup_version: str = SETUP_VERSION, exec_version: str = EXEC_VERSION,
           symbol: str | None = None, tf: str | None = None,
           strategy: str | None = None, as_of: int | None = None,
           max_bars: int | None = None,
           with_counterfactual: bool = True) -> dict:
    """The whole entry-quality read as a plain, JSON-serialisable dict. READ-ONLY.

    Pass an open connection, or a `db_path`, or neither (the default store)."""
    own = False
    if con is None:
        con = store.connect(db_path or store.DB_PATH)
        own = True
    try:
        records, counts, warnings = load_orders(
            con, setup_version=setup_version, exec_version=exec_version,
            symbol=symbol, tf=tf, strategy=strategy, as_of=as_of,
            with_counterfactual=with_counterfactual, max_bars=max_bars)
    finally:
        if own:
            con.close()

    return {
        "entrystats_version": ENTRYSTATS_VERSION,
        "setup_version": setup_version,
        "exec_version": exec_version,
        "cost_profile": LEGACY_REPORT_PROFILE.payload(),
        "filters": {"symbol": symbol, "tf": tf, "strategy": strategy,
                    "as_of": as_of},
        "counts": counts,
        "warnings": warnings,
        "caveats": [
            "Paper OVERSTATES limit fill rate: BAR_TOUCH_FULL_FILL fills the "
            "instant a bar's range contains the limit, with no queue position "
            "and no partial fill. Every fill rate here is a CEILING and every "
            "miss rate a FLOOR.",
            "Everything prefixed cf_ is a COUNTERFACTUAL walk over stored "
            "candles. No position existed; it is not a recorded result and is "
            "never presented as one.",
            "Counterfactual R is GROSS. It is compared against the recorded "
            "book's r_gross, never against the cost-netted r_multiple.",
            ("Recorded R:R uses the actual fill against the approved structural "
             "stop and target; delayed crosses can therefore differ from the plan."
             if setup_version != SETUP_VERSION else
             "Recorded planned-vs-realised R:R is structurally zero under v0.6 — "
             "execsim fills at the limit price by construction."),
            "Funding is not modelled anywhere in this engine; USDT-perp symbols "
            "settle it 3x/day, so every perp number is an optimistic ceiling.",
            f"No lookahead: every walk starts at the first bar opening at or "
            f"after available_at, and the walk is capped at "
            f"{counts['max_holding_bars']} bars — the window the RECORDED "
            f"execution manifest says the simulator held a real position for.",
        ],
        "fill_rate": fill_rate(records, counts["max_entry_bars"]),
        "adverse_selection": adverse_selection(records),
        "rr_distortion": rr_distortion(records),
        "entry_probe": entry_probe(records),
        "same_bar_resolution": same_bar_resolution(records),
        "book_counterfactual": book_counterfactual(records),
    }


# ---------------------------------------------------------------------- CLI

def _pct(x, dash="  n/a"):
    return dash if x is None else f"{100 * x:5.1f}%"


def _num(x, spec="+.2f", dash="n/a"):
    return dash if x is None else format(x, spec)


def format_report(res: dict) -> str:
    """Paste-friendly rendering. Order follows the question being asked: how many
    filled, were they the bad ones, did the geometry survive, does anything at
    entry predict, and how many die on the bar they were born."""
    out: list[str] = []
    a = out.append
    a("=== ENTRY STATISTICS (read-only; writes no facts) ===")
    a(f"setups {res['setup_version']} x orders/execs {res['exec_version']}")
    c = res["counts"]
    a(f"orders placed {c['placed']}   filled {c['filled']}   missed {c['missed']}"
      f"   still live {c['unresolved_order']}   counterfactual walks {c['cf_walked']}")
    a("")

    fr = res["fill_rate"]
    a("--- 1. FILL RATE (a CEILING: paper fills on touch, no queue position) ---")
    o = fr["overall"]
    a(f"  overall   filled {o['filled']:>4} / {o['resolved']:<4} "
      f"= {_pct(o['fill_rate_ceiling'])}   miss {_pct(o['miss_rate_floor'])} (a FLOOR)")
    a(f"  {'tf':>6}{'placed':>8}{'filled':>8}{'missed':>8}{'fill%':>9}{'miss%':>9}")
    for t, s in fr["by_tf"].items():
        a(f"  {t:>6}{s['placed']:>8}{s['filled']:>8}{s['missed']:>8}"
          f"{_pct(s['fill_rate_ceiling']):>9}{_pct(s['miss_rate_floor']):>9}")
    a(f"  entry window: {fr['max_entry_bars']} bars. Model: {fr['model']}")
    a("")

    ad = res["adverse_selection"]
    f_, m_ = ad["filled"], ad["missed_COUNTERFACTUAL"]
    a("--- 2. ADVERSE SELECTION (did the fills select the losers?) ---")
    a(f"  FILLED (RECORDED)          n={f_['n']:<4} outcomes {f_['recorded_outcomes']}")
    if f_["recorded_r_gross"]:
        g = f_["recorded_r_gross"]
        a(f"    target rate {_pct(f_['recorded_tp_rate'])}   "
          f"mean R_gross {_num(g['mean'])}   median {_num(g['median'])}   "
          f"sum {_num(g['sum'], '+.1f')}")
    if f_["recorded_r_net"]:
        g = f_["recorded_r_net"]
        a(f"    (net of modelled costs: mean {_num(g['mean'])}, "
          f"sum {_num(g['sum'], '+.1f')} — NOT the comparison basis below)")
    a(f"  MISSED (COUNTERFACTUAL)    n={m_['n']:<4} walked={m_['walked']} "
      f"resolved={m_['resolved']}  outcomes {m_['cf_outcomes']}")
    if m_["cf_r_plan_geometry"]:
        g = m_["cf_r_plan_geometry"]
        a(f"    cf target rate {_pct(m_['cf_tp_rate'])}   "
          f"cf mean R (plan geometry, GROSS) {_num(g['mean'])}   "
          f"median {_num(g['median'])}   sum {_num(g['sum'], '+.1f')}")
    if m_["cf_r_market_next_open"]:
        g = m_["cf_r_market_next_open"]
        a(f"    cf mean R (market next open, GROSS) {_num(g['mean'])}   "
          f"median {_num(g['median'])}   sum {_num(g['sum'], '+.1f')}")
    a(f"  VERDICT [{ad['verdict']['code']}]")
    for line in _wrap(ad["verdict"]["text"], 74):
        a(f"    {line}")
    a("")

    rr = res["rr_distortion"]
    rec, cfm = rr["recorded"], rr["counterfactual_market_next_open"]
    a("--- 3. PLANNED vs REALISED R:R ---")
    a(f"  RECORDED  n={rec['n_filled_with_plan']}  status={rec['status']}  "
      f"fill_price==limit_price for all: {rec['fill_price_equals_limit_price_for_all']}")
    a(f"    max |realised - planned| = "
      f"{_num(rec['max_abs_gap_vs_exact_plan_rr'], '.6f')} (exact plan geometry), "
      f"{_num(rec['max_abs_gap_vs_recorded_rr_field'], '.4f')} (vs the 2dp `rr` field)")
    for line in _wrap(rec["note"], 74):
        a(f"    {line}")
    a(f"  COUNTERFACTUAL (SPEC 1.3 market-on-next-open)  n={cfm['n']}")
    if cfm["planned_rr"] and cfm["cf_realised_rr"]:
        a(f"    planned R:R  median {_num(cfm['planned_rr']['median'], '.2f')}   "
          f"mean {_num(cfm['planned_rr']['mean'], '.2f')}")
        a(f"    cf realised  median {_num(cfm['cf_realised_rr']['median'], '.2f')}   "
          f"mean {_num(cfm['cf_realised_rr']['mean'], '.2f')}")
    if cfm["gap"]:
        a(f"    gap (cf - planned)  median {_num(cfm['gap']['median'])}   "
          f"mean {_num(cfm['gap']['mean'])}   "
          f"min {_num(cfm['gap']['min'])}  max {_num(cfm['gap']['max'])}")
    a(f"    cf R:R below 1.0: {_pct(cfm['share_below_1r'])}   "
      f"below the 1.5 setup gate: {_pct(cfm['share_below_setup_min_rr_1_5'])}   "
      f"collapsed under half of plan: {_pct(cfm['share_collapsed_below_half_plan'])}")
    if cfm["unopenable_geometry"]:
        a(f"    UNOPENABLE at the open: {cfm['unopenable_geometry']}")
    a("")

    ep = res["entry_probe"]
    a("--- 4. ENTRY-LOCATION PROBE (evidence only; gates nothing) ---")
    if not ep["sufficient"]:
        a(f"  REFUSED — {ep['refusal']}")
    else:
        a(f"  closed trades n={ep['n_closed']}   noise floor at full n "
          f"+/-{ep['noise_floor']:.2f}; each row is judged against ITS OWN "
          f"coverage floor")
        a(f"  {'feature':18}{'cov':>5}{'floor':>8}{'r_out':>8}  verdict / note")
        for row in ep["at_entry"]:
            a(f"  {row['feature'][:17]:18}{row['coverage']:>5}"
              f"{_num(row['noise_floor'], '.2f'):>8}{_num(row['r_outcome']):>8}"
              f"  {row['verdict']} — {row['note']}")
        a("  -- post-entry PATH (leakage; describes the trade, cannot predict it) --")
        for row in ep["post_entry_path"]:
            a(f"  {row['feature'][:17]:18}{row['coverage']:>5}"
              f"{_num(row['noise_floor'], '.2f'):>8}{_num(row['r_outcome']):>8}"
              f"  {row['verdict']}")
        for key in ("tf", "strategy", "direction", "regime"):
            g = ep["by_group"].get(key) or {}
            bits = ", ".join(
                f"{k} n={v['n']} meanR {v['mean_r']:+.2f}"
                + ("" if v["sufficient"] else " (n<%d)" % MIN_TRADES)
                for k, v in g.items())
            a(f"  by {key:10} {bits}")
    a("")

    sb = res["same_bar_resolution"]
    o = sb["overall"]
    a("--- 5. SAME-BAR RESOLUTION (the headline metric) ---")
    a(f"  RECORDED  resolution on the fill bar {o['n_same_bar']}/{o['n_fills']} "
      f"= {_pct(o['same_bar_resolution_rate'])}")
    a(f"            STOP-OUTS on the fill bar   {o['n_same_bar_stop_outs']}/"
      f"{o['n_stop_outs']} = {_pct(o['same_bar_stop_out_rate'])}  <- the SPEC 0 number")
    a(f"  COUNTERFACTUAL (market next open)  resolution "
      f"{_pct(o['cf_same_bar_resolution_rate_COUNTERFACTUAL'])}   stop-outs "
      f"{_pct(o['cf_same_bar_stop_out_rate_COUNTERFACTUAL'])}")
    a(f"  {'tf':>6}{'fills':>7}{'sameBar':>9}{'SLs':>6}{'sameBarSL':>11}"
      f"{'cf sameSL':>11}")
    for t, s in sb["by_tf"].items():
        a(f"  {t:>6}{s['n_fills']:>7}{_pct(s['same_bar_resolution_rate']):>9}"
          f"{s['n_stop_outs']:>6}{_pct(s['same_bar_stop_out_rate']):>11}"
          f"{_pct(s['cf_same_bar_stop_out_rate_COUNTERFACTUAL']):>11}")
    a("")

    bc = res["book_counterfactual"]
    a("--- 6. WHOLE BOOK UNDER SPEC 1.3 ENTRY (COUNTERFACTUAL, GROSS) ---")
    a(f"  orders {bc['n_orders']}  walked {bc['n_walked']}  resolved "
      f"{bc['n_resolved']}  usable {bc['n_usable']}   outcomes {bc['cf_outcomes']}")
    if bc["cf_r_gross"]:
        g = bc["cf_r_gross"]
        a(f"  cf   n={g['n']:<4} win {_pct(g['win_rate'])}  mean R {_num(g['mean'])}  "
          f"median {_num(g['median'])}  sum {_num(g['sum'], '+.1f')}")
    if bc["recorded_r_gross_filled_only"]:
        g = bc["recorded_r_gross_filled_only"]
        a(f"  rec  n={g['n']:<4} win {_pct(g['win_rate'])}  mean R {_num(g['mean'])}  "
          f"median {_num(g['median'])}  sum {_num(g['sum'], '+.1f')}   (RECORDED, gross)")
    if bc["cf_taker_entry_penalty_r"]:
        p = bc["cf_taker_entry_penalty_r"]
        a(f"  entry fee delta of the switch (maker->taker, recorded cost profile): "
          f"mean {_num(p['mean'], '+.4f')} R/trade")
        a(f"  cf mean R after that fee delta: "
          f"{_num(bc['cf_mean_r_after_entry_fee_delta'])}")
    if bc["unopenable_geometry"]:
        a(f"  unopenable at the open: {bc['unopenable_geometry']}")
        a(f"  bias: {bc['exclusion_bias']}")

    if res["warnings"]:
        a("")
        a("--- warnings (loud fallback: these are NOT confident zeros) ---")
        for w in res["warnings"][:20]:
            a(f"  ! {w}")
        if len(res["warnings"]) > 20:
            a(f"  ! ... and {len(res['warnings']) - 20} more")
    return "\n".join(out)


def _wrap(text: str, width: int) -> list[str]:
    """Deterministic greedy wrap. `textwrap` would do, but this keeps the output
    identical across Python versions, which byte-identical output requires."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        prog="python -m engine.entrystats",
        description="Entry quality (read-only): fill rate, adverse selection, "
                    "planned-vs-realised R:R, entry-location probe, same-bar "
                    "resolution.")
    ap.add_argument("--db", default=None, help="path to the fact store")
    ap.add_argument("--setup-version", default=SETUP_VERSION)
    ap.add_argument("--exec-version", default=EXEC_VERSION)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--tf", default=None)
    ap.add_argument("--strategy", default=None)
    ap.add_argument("--as-of", type=int, default=None,
                    help="only facts confirmed at or before this epoch second")
    ap.add_argument("--max-bars", type=int, default=None,
                    help="counterfactual walk-forward window, in bars "
                         "(default: whatever the recorded execution manifest says)")
    ap.add_argument("--no-counterfactual", action="store_true",
                    help="skip the walk-forward entirely (fill rate only)")
    ap.add_argument("--json", action="store_true", help="emit the raw report dict")
    args = ap.parse_args(argv)

    res = report(db_path=Path(args.db) if args.db else None,
                 setup_version=args.setup_version, exec_version=args.exec_version,
                 symbol=args.symbol, tf=args.tf, strategy=args.strategy,
                 as_of=args.as_of, max_bars=args.max_bars,
                 with_counterfactual=not args.no_counterfactual)
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True, default=str))
    else:
        print(format_report(res))
    return 0 if res["counts"]["placed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
