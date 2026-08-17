"""Execution simulator — paper-trades every VALIDATED setup. algo exec-v0.1-draft.

No live orders exist anywhere in this system (§16). This engine replays each
setup as a limit fill at entry on its trigger bar (guaranteed by construction:
the touch bar overlaps the zone edge), then walks forward bar by bar:
- SL hit when a bar trades through the stop; TP hit when it trades through the
  target. Same bar reaches BOTH -> counted as SL (conservative draft rule,
  flagged ambiguous=true; sub-bar sequencing needs LTF data, deferred).
- TIMEOUT after MAX_BARS unresolved -> exit at that bar's close (§11 expiration).
- Still unresolved at end of data -> OPEN (no exit fact emitted yet; emitted on
  a later run once resolvable — append-only, deterministic).
Outcome facts carry r_multiple so the track record is position-size agnostic.
"""
import json
from bisect import bisect_left
from decimal import Decimal

from . import costs, store, venues
from .setups import SETUP_VERSION
from .swings import compute_atr
from .runlog import RunRecorder

EXEC_VERSION = "exec-v0.23-draft"
# v0.23: input cascade from agg-v0.2 via setup-v0.19 — and directly: fills
# simulate against the candle series, and a 4H setup now meets partial 4H
# bars. No fill, cost or exit rule changed.
# v0.22: cascade from setup-v0.18 / risk-v0.22 (R-denominated envelope, paper
# R back to 2%). No fill, cost or exit rule changed here; `setup_id` is
# version-scoped, so a new setup generation is a new order flow by definition.
# v0.21: cascade from setup-v0.17 (VALIDATED setups carry the top-down bias
# block). The simulator executes whatever setups exist; a new setup generation
# is a new order flow, the same reason as v0.18/v0.19/v0.20. NOTHING HERE READS
# `bias` and no fill, cost or exit changed — the trades are the same trades.
# The tag still moves, because `setup_id` is version-scoped, so every order and
# exec fact this pass writes joins to a v0.17 plan and a consumer that mixed
# them with v0.16 rows would be double-counting the same setups under two
# generations. That is the S37/v0.14 defect and the version is what prevents it.
# v0.20: cascade from setup-v0.16 (magnitude-scaled WHY prices upstream). The
# simulator executes whatever setups exist; a new setup generation is a new
# order flow.
# v0.19: cascade from setup-v0.15 (the same-bar pivot-pair fix upstream).
# v0.18: cascade from setup-v0.14 (swing-v0.9 at the root). The simulator
# executes whatever setups exist; a new setup generation is a new order flow.
# v0.17: two output changes, both labelling rather than economics.
#  * `fees_price_units` is now EXCHANGE FEES ONLY. Funding was folded in while
#    also reported as `funding_price_units`, so a consumer summing the two
#    double-counted it. Net P&L and r_multiple are unchanged — both legs are
#    still deducted — but the recorded numbers differ, so the version moves.
#  * the execution manifest no longer embeds the cost profile. That manifest
#    certifies the FILL MODEL, which is identical on every venue; including
#    costs made its hash vary by symbol, so a fee change was indistinguishable
#    from an execution-model change. What was charged is proven by
#    cost_manifest_hash, which is per-venue by design.
# v0.15: **exec-v0.14 IS POISONED — do not read it.** It covers two setup
#   generations. The cross-fill correction below was simulated and tagged
#   v0.14 while SETUP_VERSION was still v0.11; the zone lookahead fix then
#   moved setups to v0.12 and the same tag simulated those plans too. Result:
#   637 facts from setup-v0.11 plans and 637 from setup-v0.12 plans under ONE
#   algo_version, which double-counted every strategy statistic read off it.
#   That is the S37 defect committed again, by the person writing the fix for
#   the one above it. v0.15 exists so the corrected generation has a tag that
#   means one thing. Nothing is deleted; v0.14 stays in the store as the record
#   of what happened, and no consumer may join on it.
# v0.14: THE CROSS NO LONGER FILLS AT A PRICE THE BAR NEVER TRADED.
#   The MAKER_THEN_MARKET crossing leg booked a market fill at the PLAN's entry
#   price — `candles[ci+1]["open"]`, two bars stale by the time the cross fires.
#   Measured: 78 of 95 crossed orders (82.1%) booked outside their own fill
#   bar's [low, high], never adversely. The book restates +95.85 R -> +31.95 R
#   over 642 trades, and REVERSAL stops clearing zero on the traded book.
#   The cross now fills at the crossing bar's OPEN and pays market slippage.
# v0.13: simulates setup-v0.11 plans.

# v0.12 — FUNDING IS NOW CHARGED. `venues.funding_cost_rate` was written in S32
# with the reasoning spelled out ("funding is charged repeatedly, not once") and
# then **never called by anything**. Perps pay it every settlement — 3/day on
# Phemex — and the simulator charged zero, so every multi-day position was
# flattered. Measured on the recorded book at a 0.01%/settlement model:
#   15m ~0.00 R · 1H ~0.01 R · 4H ~0.01 R · 1D ~0.03 R · 1W ~0.12 R
# Small next to the 14x cost-profile error of S37, but 0.03 R is ~17% of the
# 1D book's expectancy, and an unmodelled cost that only ever flatters is the
# kind that survives review.
#
# TWO HONEST LIMITATIONS, stated rather than buried:
#  1. The rate is a MODELLED CONSTANT. Real funding varies per settlement and
#     Phemex publishes it, but this store holds no historical funding series —
#     `phemex.funding_rate()` fetches only the CURRENT rate, which cannot price
#     a trade from 2024. Using a constant is a model; calling it a measurement
#     would be a lie.
#  2. It is charged to BOTH directions. In reality the side paying flips with
#     the sign of the rate — a short receives funding when longs are paying.
#     Charging both is deliberately pessimistic: this engine's standing rule is
#     that the failure to avoid is believing a cost is smaller than it is.
# v0.11: simulates setup-v0.10 plans and carries the armed-order lineage
# (forming_id, armed_at, armed_size_units, bars_armed_exceeded) onto every
# order and exec fact, including MISSED. Plan Phases G/H.

# v0.10: execution model unchanged; it now simulates setup-v0.9 plans.

# v0.9: execution model unchanged; it now simulates setup-v0.8 plans, which are
# built on the tick-corrected structure/regime facts. Same reason as v0.8 —
# one version label must never cover two strategy generations.

# v0.8 — forced by setup-v0.7, and it had already gone wrong before this bump.
#
# 1. TWO BOOKS UNDER ONE VERSION. execsim kept writing `exec-v0.7-draft` while
#    simulating v0.7 plans, so the same version label covered two different
#    strategy generations. Measured on the live store: 346 exec facts, of which
#    130 joined to a setup_id that existed in BOTH the v0.6 and v0.7 books. One
#    order came back FILLED and MISSED at once. A version tag whose meaning
#    changes underneath it is worse than no version tag, because every consumer
#    trusts it. (setups.py separately version-scoped `setup_id`, which was the
#    other half of the same defect.)
#
# 2. VENUE-BLIND COSTS. The cost profile was the module-level Coinbase default
#    for every symbol while the traded universe has been 100% Phemex perps since
#    S34 — a 14x over-charge on fees AND on the market-exit slippage that prices
#    every stop. Now venue-derived via costs.profile_for(symbol).
#
# NOT changed, deliberately: exits still hold to SL/TP. The managed exit
# (partials + trailing + breakeven + adaptive time stop) specified in
# SPEC-confirmed-entry §1.6 was REJECTED by its own 2x2 gate — it made the
# confirmed entry worse (-0.017R -> -0.171R), because it was designed from
# excursion data measured on the broken entry. Holding is now the measured
# choice rather than the unexamined default.
MAX_BARS = 100
MAX_ENTRY_BARS = 4
# Modelled funding, per settlement. Conservative round number, not a measurement
# — see the version note above. Spot venues declare 0 settlements/day so this is
# inert there by construction rather than by a branch.
FUNDING_RATE_PER_SETTLEMENT = Decimal("0.0001")
Q2 = Decimal("0.01")


def unresolved(con) -> dict[tuple[str, str], list[dict]]:
    """Current simulator orders that still need market data to become terminal.

    The universe is allowed to reject a market at any refresh; an already
    placed order is not allowed to disappear with it.  This work list is read
    from durable lifecycle facts so it survives both universe churn and process
    restarts.  Only the current execution generation belongs to the current
    paper book; older generations remain recorded history.
    """
    rows = con.execute(
        "WITH latest_order AS ("
        " SELECT symbol,tf,json_extract(payload,'$.setup_id') AS setup_id,"
        " json_extract(payload,'$.event') AS event,"
        " ROW_NUMBER() OVER (PARTITION BY json_extract(payload,'$.setup_id')"
        " ORDER BY confirmed_at DESC,id DESC) AS rn"
        " FROM facts WHERE kind='order' AND algo_version=?"
        "), terminal AS ("
        " SELECT DISTINCT json_extract(payload,'$.setup_id') AS setup_id"
        " FROM facts WHERE kind='exec' AND algo_version=?"
        ") SELECT o.symbol,o.tf,o.setup_id,o.event FROM latest_order o"
        " LEFT JOIN terminal t ON t.setup_id=o.setup_id"
        " WHERE o.rn=1 AND o.setup_id IS NOT NULL AND t.setup_id IS NULL"
        " AND o.event IN ('PLACED','FILLED')"
        " ORDER BY o.symbol,o.tf,o.setup_id",
        (EXEC_VERSION, EXEC_VERSION)).fetchall()
    work: dict[tuple[str, str], list[dict]] = {}
    for symbol, tf, setup_id, event in rows:
        work.setdefault((symbol, tf), []).append(
            {"setup_id": setup_id, "event": event})
    return work

# v0.2 (EXEC-1, §14): trading costs modeled. Entry is a resting limit at the
# zone edge -> fee only, no slippage. TP is a resting limit -> fee only.
# SL and TIMEOUT exits are market orders -> fee + slippage (0.05 ATR at exit).
# r_multiple is NET of costs; r_gross preserved. Cost constants live in
# setups.py (single source of truth — the setup gate uses the same numbers).


# ------------------------------------------------------------- the one walk
#
# Extracted from run()'s inline loop so the 2x2 harness can stop keeping a
# second copy. `abtest.py` opens by naming the risk of its own simulation core
# ("a second one risks the two disagreeing") and defends it with a runtime
# calibration pass. The drift happened anyway, in the two ways drift always
# happens — a convention differed (its exit fees were charged on the nominal
# price, not the slipped one) and a later fix never arrived (funding, added
# here in v0.12 precisely because "an unmodelled cost that only ever flatters
# is the kind that survives review", was never charged there at all).
#
# The session that produced this refactor paid the same tuition externally
# first: a bar-replay of the prior project's book validated at 47.7% against
# its own recorded exits, because the replay modelled a bracket the executor
# didn't run. The lesson is structural — the code that settles must BE the
# code that replays, so agreement is a property rather than a calibration
# result. These functions are that property. run() calls them for the record;
# abtest calls them for the counterfactual; the pin test in test_one_walk.py
# holds the extraction to the pre-refactor settlements to the digit.
#
# `simulate_entry` completes the set, and it is the same lesson a fourth time.
# Sharing `cross_fill` fixed the 76 trades that had diverged, but left the
# harness still choosing WHICH BAR to cross on, whether the passive leg had
# filled, and what the risk denominator was — the whole model around the one
# line that had been extracted. Two of those three were already wrong at the
# time (`ci+1` against a bisect on `confirmed_at`, and a maker limit re-derived
# rather than read from the plan that recorded it); they happened to agree on
# this book. "Agrees today" is not a convention.

def walk_exit(candles, i, sl, tp, long, max_bars=MAX_BARS):
    """Walk forward from the fill bar to a terminal outcome.

    Returns (outcome, exit_price, j, ambiguous) — j the exit bar's index — or
    None while the position is still OPEN at the end of data. OPEN is never a
    result: counting it as one would dilute expectancy with rows where nothing
    happened. A bar that reaches BOTH levels settles as the STOP, flagged
    ambiguous — sub-bar sequencing needs LTF data we do not have, and
    flattering an ambiguous bar is how a backtest lies.
    """
    for j in range(i, min(i + max_bars, len(candles))):
        c = candles[j]
        hi, lo = Decimal(c["high"]), Decimal(c["low"])
        hit_sl = lo <= sl if long else hi >= sl
        hit_tp = hi >= tp if long else lo <= tp
        if hit_sl or hit_tp:
            return ("SL" if hit_sl else "TP",
                    sl if hit_sl else tp, j, hit_sl and hit_tp)
    if i + max_bars <= len(candles):        # full window elapsed unresolved
        j = i + max_bars - 1
        return "TIMEOUT", Decimal(candles[j]["close"]), j, False
    return None                             # not enough data yet — OPEN


def cross_fill(candles, fill_i, long, atr_at_fill, profile):
    """The price a crossing market order actually gets, and the ONE definition.

    THE FILL IS THE CROSSING BAR'S OPEN, plus slippage against you. It is the
    first price available once the passive window has closed, it demonstrably
    traded on THAT bar, and it needs no assumption about intrabar path.

    This was a bug in v0.13 and its measurement is the reason the rule is
    written down here rather than inlined: the cross used to book the PLAN's
    price, a print from two bars earlier. On 95 crossed orders, 78 (82.1%) were
    booked outside the fill bar's own [low, high], never adversely — 94 of 95
    filled better than the crossing bar's open. That free entry advantage was
    +86 R of raw edge, and re-simulating the book without it moved +95.85 R to
    +31.95 R over 642 trades.

    Extracted 4 Aug 2026 because `abtest` still had the v0.13 behaviour long
    after execsim was fixed — the harness meant to VALIDATE the simulator was
    quietly running the bug the simulator had corrected, and reported 70.0 R
    against the book's real 7.9 R. Two implementations of one fill model is how
    they come to disagree; there is now one, and both call it.

    Returns (fill_price, slipped) — `slipped` False means no ATR was available
    and the caller must degrade LOUDLY rather than book a flattered fill.
    """
    px = Decimal(candles[fill_i]["open"])
    if atr_at_fill is None:
        return px, False
    slip = profile.market_slippage_atr * atr_at_fill
    return ((px + slip) if long else (px - slip)), True


def settle(profile, symbol, entry, exit_price, risk, long, outcome,
           bars_held, tf_seconds, atr_exit, *, entry_role):
    """Price one closed leg: slippage, fees, funding, and the R they leave.

    THE costing of a settlement — the record and every replay must charge a
    trade through this function or they are measuring different worlds. The
    conventions it encodes, each once load-bearing enough to get a version
    bump: market exits (SL, TIMEOUT) pay taker plus slippage and the exit fee
    is charged on the SLIPPED price; TP is a resting limit and pays maker;
    funding accrues per settlement over the hold, keyed on the venue so spot
    is inert by construction; a missing ATR at the exit degrades LOUDLY via
    `slip_missing` rather than silently flattering the fill.
    """
    slip = Decimal(0)
    slip_missing = False
    if outcome in ("SL", "TIMEOUT"):
        if atr_exit is not None:
            slip = profile.market_slippage_atr * atr_exit
        else:
            slip_missing = True
    holding_hours = Decimal(bars_held * tf_seconds) / Decimal(3600)
    funding_rate = venues.funding_cost_rate(
        symbol, FUNDING_RATE_PER_SETTLEMENT, holding_hours)
    funding = funding_rate * entry           # price units, on notional
    eff_exit = (exit_price - slip) if long else (exit_price + slip)
    exit_rate = (profile.maker_rate if outcome == "TP" else profile.taker_rate)
    entry_rate = (profile.taker_rate if entry_role == "TAKER"
                  else profile.maker_rate)
    fees = entry_rate * entry + exit_rate * eff_exit
    gross = (exit_price - entry) if long else (entry - exit_price)
    net = (((eff_exit - entry) if long else (entry - eff_exit))
           - fees - funding)
    return {
        "slip": slip, "slip_missing": slip_missing, "eff_exit": eff_exit,
        "fees": fees, "funding": funding, "holding_hours": holding_hours,
        "r_gross": (gross / risk).quantize(Q2) if risk > 0 else Decimal(0),
        "r_mult": (net / risk).quantize(Q2) if risk > 0 else Decimal(0),
    }


def simulate_entry(candles, atr, order_i, entry, sl, long, *, entry_model,
                   maker_limit, maker_wait, profile,
                   max_entry_bars=MAX_ENTRY_BARS):
    """Turn a PLAN into the fill it actually got: which bar, what price, whose
    fee, and the risk denominator that follows from all three.

    `cross_fill` above is the crossing PRICE and this is the model around it.
    Sharing the price alone left the harness still deciding on its own WHICH
    BAR to cross on, whether the passive leg had filled first, and what the
    risk denominator was — three more chances to answer differently, in the
    code immediately next to the one that had already been answered
    differently for a version. Sharing the price fixed the 76 trades; sharing
    the model is what stops the next one.

    Returns a dict whose `status` is one of:
      FILLED   `fill_i`, `entry` (the price PAID, not the plan's), `entry_role`
               (whose fee schedule applies) and `risk` are all set.
      MISSED   the order expired unfilled; `scan_end` is the exclusive end of
               the scan, so the caller can date the expiry.
      PENDING  the data runs out before the order resolves. Not a result.
    `note` carries loud-fallback text when a degraded path was taken — the
    caller must surface it. abtest took `cross_fill`'s `slipped` flag and threw
    it away (`entry_px, _ =`), so a fill with no ATR degraded silently in the
    harness while degrading audibly in the engine.

    THE RISK RECOMPUTE IS PART OF THE FILL. A fill that differs from the plan
    sits a different distance from the SAME structural stop, so it has a
    different R denominator. A better fill is a smaller one; a crossed fill
    that chased the market is a larger one. Inheriting the plan's rescales
    every trade the fill moved — silently, and in the flattering direction,
    because the plan price is by construction the one the strategy wanted.
    """
    # The two passive models differ only in what they do when the limit does
    # not fill, and that difference is the whole measurement. MAKER_PULLBACK
    # declines the trade; MAKER_THEN_MARKET crosses. The pure-maker version is
    # ADVERSELY SELECTED — measured on this book, its 32 unfilled orders would
    # have made +0.365 R each at market against +0.074 R for the ones that
    # filled, because price walks away precisely when the trade was right. It
    # is kept as a model so the 2x2 can keep re-asking, not because it won.
    passive = entry_model in ("MAKER_THEN_MARKET", "MAKER_PULLBACK")
    cross_on_expiry = entry_model == "MAKER_THEN_MARKET"
    market_entry = entry_model == "MARKET_NEXT_OPEN"

    fill_i, entry_role, note = None, "MAKER", None

    def unfilled(status, scan_end=None):
        """No position. `entry` is whatever the plan asked for — the MISSED
        record quotes the price it wanted and never got."""
        return {"status": status, "fill_i": None, "entry": entry,
                "entry_role": entry_role, "risk": None,
                "scan_end": scan_end, "note": note}

    if passive and maker_limit is not None:
        # Passive leg: the limit rests BETTER than the market, so it can only
        # fill if price comes back. A limit AT the market would be marketable
        # and pay taker — claiming maker for that is a fee saving the exchange
        # never granted.
        wait_end = min(order_i + maker_wait, len(candles))
        scan_end = wait_end
        for k in range(order_i, wait_end):
            lo, hi = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
            if lo <= maker_limit <= hi:
                fill_i = k
                entry = maker_limit          # a real, better fill price
                break
        if fill_i is None and cross_on_expiry and wait_end < len(candles):
            # CROSS: the passive limit never filled, so we take the market at
            # the end of the window. ONE definition of what that costs — see
            # cross_fill for the measurement, and for the divergence that came
            # from fixing it in only one of the two places that crossed.
            fill_i = wait_end
            entry_role = "TAKER"
            entry, slipped = cross_fill(candles, fill_i, long,
                                        atr[fill_i], profile)
            if not slipped:
                note = (f"cross slippage NOT applied at bar "
                        f"{candles[fill_i]['open_ts']} (no ATR);")
        elif fill_i is None:
            # A pure-maker model declines the trade rather than crossing; the
            # window must have fully elapsed for that to be a MISS rather than
            # a position we simply cannot resolve yet.
            if not cross_on_expiry and order_i + maker_wait <= len(candles):
                return unfilled("MISSED", scan_end)
            return unfilled("PENDING")
    else:
        entry_role = "TAKER" if market_entry else "MAKER"
        scan_end = min(order_i + max_entry_bars, len(candles))
        for k in range(order_i, scan_end):
            lo, hi = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
            if lo <= entry <= hi:
                fill_i = k
                break
        if fill_i is None:
            if order_i + max_entry_bars > len(candles):
                return unfilled("PENDING")
            return unfilled("MISSED", scan_end)

    risk = (entry - sl) if long else (sl - entry)
    if risk <= 0:
        # No denominator, no R. Booking such a trade at 0R would enter the book
        # as a flat result rather than as the unpriceable plan it is.
        return unfilled("PENDING")
    return {"status": "FILLED", "fill_i": fill_i, "entry": entry,
            "entry_role": entry_role, "risk": risk, "scan_end": scan_end,
            "note": note}


def plan_versions() -> tuple:
    """THE definition of what this book trades — the setup generations the
    simulator executes, and nothing else.

    Extracted because it had quietly become three copies: this simulator's own
    loop, `risk.py`'s intent scan, and — by OMISSION — `live.py`'s announcer,
    which had no copy at all. Its filter gated on the setup's state, on the
    baseline window and on how late the setup was, but never on which ENGINE
    produced it, so it announced every module that writes a `setup` fact. That
    includes the two that are MEASURED AND NOT ENABLED, and the operator was
    being alerted to take TREND_CONTINUATION trades from a playbook measured at
    -0.1500 R with its interval entirely below zero. 17 of them.

    A WHITELIST, deliberately, rather than a blacklist of the not-enabled. The
    two failure modes are not symmetric: an engine that should alert and does
    not is a missed trade, while an engine that should not alert and does is
    the operator trading something the book has never graded. A new playbook
    must therefore be silent until someone adds it here — the same reason
    `pipeline.GATES` raises on an unknown name rather than warning.
    """
    from .scalein import SCALE_VERSION   # lazy: avoids circular import
    return (SETUP_VERSION, SCALE_VERSION)


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "execsim", EXEC_VERSION, symbol, tf) as rec:
        # Venue-derived: spot fees on a perp are a 14x over-charge, and
        # they price the slippage on every stop, not just the fees.
        COST_PROFILE = costs.profile_for(symbol)
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        candle_times = [c["open_ts"] for c in candles]
        atr = compute_atr(candles)

        setups = {}
        for ver in plan_versions():
            for r in store.get_facts(con, symbol, tf, "setup", ver):
                p = json.loads(r["payload"])
                if p["state"] == "VALIDATED":
                    setups[p["setup_id"]] = {
                        "market_time": r["market_time"],
                        "available_at": r["confirmed_at"], **p}
        rec.n_inputs = len(setups)

        n_out = 0
        cost_manifest_hash = costs.record(con, COST_PROFILE)
        execution_manifest_hash = store.record_manifest(con, "execution", {
            "version": EXEC_VERSION, "max_entry_bars": MAX_ENTRY_BARS,
            "max_holding_bars": MAX_BARS,
            "order_available_after_confirmation": True,
            "fill_model": "BAR_TOUCH_FULL_FILL",
            "same_bar_stop_target": "STOP_FIRST",
            "partial_fills": "UNAVAILABLE_WITH_OHLC_ONLY",
            # No cost reference here, deliberately. This manifest certifies the
            # FILL MODEL, which is identical on every venue. Folding costs in
            # made the hash vary by symbol, so a fee change was indistinguishable
            # from an execution-model change and two books running identical
            # rules looked like they ran different ones. What each trade was
            # charged is proven separately by cost_manifest_hash.
        })
        counts = {"TP": 0, "SL": 0, "TIMEOUT": 0, "OPEN": 0,
                  "MISSED": 0, "PENDING": 0}
        for sid, s in setups.items():
            available_at = s["available_at"]
            order_i = bisect_left(candle_times, available_at)
            if order_i >= len(candles):
                counts["PENDING"] += 1
                continue
            entry, sl, tp = Decimal(s["entry"]), Decimal(s["sl"]), Decimal(s["tp"])
            long = s["direction"] == "LONG"
            # No `risk` here on purpose. The plan's risk is not this trade's
            # risk — only the fill knows that, and a plan-derived value sitting
            # in scope is exactly what a later edit reaches for by mistake.
            # simulate_entry() returns the one that counts.
            # The strategy declares how it intends to get in, and the fee role
            # follows from that — not the other way round. setup-v0.7 enters
            # MARKET at the next bar's open, which pays TAKER. Labelling that
            # order a LIMIT and charging maker would understate cost on every
            # v0.7 trade (measured delta ~0.045 R/trade) while also claiming a
            # fill model the plan never asked for.
            entry_model = s.get("entry_model")
            # MAKER_THEN_MARKET rests a passive limit at `maker_limit` and
            # crosses if it has not filled within `maker_wait_bars`. Both legs
            # are load-bearing and each was measured: passive-only is adversely
            # selected (its misses were the winners, +0.365R vs +0.074R), and
            # market-only forfeits a fee saving that spans losing and winning on
            # a book whose break-even fee is 0.033%/side. See setups.ENTRY_MODEL.
            passive_then_cross = entry_model == "MAKER_THEN_MARKET"
            market_entry = entry_model == "MARKET_NEXT_OPEN"
            maker_limit = (Decimal(s["maker_limit"])
                           if passive_then_cross and s.get("maker_limit") else None)
            maker_wait = int(s.get("maker_wait_bars") or 0)
            # PHASE G/H — armed-order lineage. The order placed here must be
            # traceable to the FORMING fact that decided it, or "no runtime
            # decision at execution" is a claim with nothing behind it. These
            # ride on every order and exec fact, including MISSED.
            armed_lineage = {
                "forming_id": s.get("forming_id"),
                "inherited_from_forming": bool(s.get("inherited_from_forming")),
                "armed_at": s.get("armed_at"),
                "armed_size_units": s.get("armed_size_units"),
                "armed_risk_decision": s.get("armed_risk_decision"),
                "expires_at_ts": s.get("expires_at_ts"),
            }
            order_base = {**armed_lineage, "setup_id": sid, "side": s["direction"],
                          "order_type": ("LIMIT_THEN_MARKET" if passive_then_cross
                                         else "MARKET" if market_entry else "LIMIT"),
                          "limit_price": str(maker_limit if maker_limit is not None else entry),
                          "cross_price": str(entry) if passive_then_cross else None,
                          "available_at": available_at,
                          "max_entry_bars": MAX_ENTRY_BARS,
                          "cost_manifest_hash": cost_manifest_hash,
                          "execution_manifest_hash": execution_manifest_hash}
            store.insert_fact(con, symbol=symbol, tf=tf, kind="order",
                              market_time=s["market_time"], confirmed_at=available_at,
                              algo_version=EXEC_VERSION,
                              payload={**order_base, "event": "PLACED"})

            # The fill model lives in simulate_entry(), which abtest replays
            # through as well — the record and the counterfactual cannot price
            # an entry differently if there is only one place that prices one.
            fill = simulate_entry(candles, atr, order_i, entry, sl, long,
                                  entry_model=entry_model,
                                  maker_limit=maker_limit,
                                  maker_wait=maker_wait,
                                  profile=COST_PROFILE)
            if fill["note"]:
                # loud-fallback rule: a degraded path must be audible
                rec.notes = (rec.notes or "") + " " + fill["note"]
            if fill["status"] == "PENDING":
                counts["PENDING"] += 1
                continue
            if fill["status"] == "MISSED":
                miss_ts = candles[fill["scan_end"] - 1]["open_ts"] + tf_seconds
                # PHASE H — a MISSED order is the armed window expiring. Record
                # whether it expired BECAUSE the window was too short, so
                # MAX_ENTRY_BARS can be judged against real arming lead times
                # instead of assumed to be right.
                _armed_at = s.get("armed_at")
                _expires = s.get("expires_at_ts")
                payload = {**armed_lineage,
                           "expires_at_observed": miss_ts,
                           "bars_armed_exceeded": bool(
                               _expires is not None and miss_ts >= _expires),
                           "armed_lead_bars": (
                               (available_at - _armed_at) // tf_seconds
                               if _armed_at else None),
                           "setup_id": sid, "strategy": s["strategy"],
                           "direction": s["direction"], "outcome": "MISSED",
                           "entry": str(entry), "exit_price": None,
                           "r_multiple": "0", "r_gross": "0", "costs_r": "0",
                           "bars_held": 0, "bars_to_fill": None,
                           "available_at": available_at, "fill_ts": None,
                           "ambiguous_bar": False,
                           "cost_manifest_hash": cost_manifest_hash,
                           "execution_manifest_hash": execution_manifest_hash,
                           "manifest_hash": s.get("manifest_hash")}
                store.insert_fact(con, symbol=symbol, tf=tf, kind="order",
                                  market_time=s["market_time"], confirmed_at=miss_ts,
                                  algo_version=EXEC_VERSION,
                                  payload={**order_base, "event": "MISSED"})
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="exec",
                                     market_time=s["market_time"], confirmed_at=miss_ts,
                                     algo_version=EXEC_VERSION, payload=payload):
                    n_out += 1
                counts["MISSED"] += 1
                continue

            # The fill is what gets recorded from here down: the price PAID, the
            # fee role that price earned, and the risk denominator measured from
            # it. Nothing below may reach back for the plan's version of any of
            # the three.
            entry, entry_role, risk = (fill["entry"], fill["entry_role"],
                                       fill["risk"])
            i = fill["fill_i"]
            fill_ts = candles[i]["open_ts"] + tf_seconds
            store.insert_fact(con, symbol=symbol, tf=tf, kind="order",
                              market_time=s["market_time"], confirmed_at=fill_ts,
                              algo_version=EXEC_VERSION,
                              payload={**order_base, "event": "FILLED",
                                       "fill_price": str(entry),
                                       "entry_fee_role": entry_role,
                                       "bars_to_fill": i - order_i})
            w = walk_exit(candles, i, sl, tp, long)
            if w is None:                          # not enough data yet
                counts["OPEN"] += 1
                continue
            outcome, exit_price, j, ambiguous = w
            exit_ts = candles[j]["open_ts"] + tf_seconds
            # `fees_price_units` means EXCHANGE FEES; funding is reported
            # separately (a consumer summing the two must not double-count).
            # Both are still deducted from net — see settle().
            st = settle(COST_PROFILE, symbol, entry, exit_price, risk, long,
                        outcome, j - i, tf_seconds, atr[j],
                        entry_role=entry_role)
            if st["slip_missing"]:
                # loud-fallback rule: degrading (no slippage modeled) must be audible
                from .runlog import get_logger
                get_logger().warning(
                    f"execsim {symbol} {tf}: no ATR at exit bar for {sid} — "
                    f"market-exit slippage NOT applied (results slightly flattering)")
            eff_exit, fees = st["eff_exit"], st["fees"]
            funding_cost, holding_hours = st["funding"], st["holding_hours"]
            r_gross, r_mult = st["r_gross"], st["r_mult"]
            held = candles[i:j + 1]
            if long:
                mfe = max(Decimal(c["high"]) - entry for c in held)
                mae = max(entry - Decimal(c["low"]) for c in held)
            else:
                mfe = max(entry - Decimal(c["low"]) for c in held)
                mae = max(Decimal(c["high"]) - entry for c in held)
            counts[outcome] += 1
            payload = {**armed_lineage,
                       "setup_id": sid, "strategy": s["strategy"],
                       "direction": s["direction"], "outcome": outcome,
                       "entry": str(entry), "exit_price": str(exit_price),
                       "effective_exit_price": str(eff_exit),
                       "fees_price_units": str(fees),
                       "funding_price_units": str(funding_cost),
                       "funding_rate_modelled": str(FUNDING_RATE_PER_SETTLEMENT),
                       "holding_hours": str(holding_hours),
                       "r_multiple": str(r_mult), "r_gross": str(r_gross),
                       "costs_r": str((r_gross - r_mult).quantize(Q2)),
                       "bars_held": j - i, "bars_to_fill": i - order_i,
                       "mae_r": str((mae / risk).quantize(Q2)) if risk > 0 else "0",
                       "mfe_r": str((mfe / risk).quantize(Q2)) if risk > 0 else "0",
                       "available_at": available_at, "fill_ts": fill_ts,
                       "ambiguous_bar": ambiguous,
                       "entry_fee_role": entry_role,
                       "exit_fee_role": "MAKER" if outcome == "TP" else "TAKER",
                       # Which venue's fee schedule this trade was actually
                       # charged. The manifest hash already proves it, but a
                       # hash is not readable: with the label on the fact, a
                       # book priced on the wrong venue is visible at a glance
                       # instead of needing 232 facts to be re-derived.
                       "venue": COST_PROFILE.venue,
                       "cost_profile_version": COST_PROFILE.version,
                       "cost_manifest_hash": cost_manifest_hash,
                       "execution_manifest_hash": execution_manifest_hash,
                       "manifest_hash": s.get("manifest_hash")}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="exec",
                                 market_time=s["market_time"], confirmed_at=exit_ts,
                                 algo_version=EXEC_VERSION, payload=payload):
                n_out += 1

        con.commit()
        rec.n_new_facts = n_out
        return {"symbol": symbol, "tf": tf, **counts}
