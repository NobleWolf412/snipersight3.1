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

EXEC_VERSION = "exec-v0.18-draft"
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

# v0.2 (EXEC-1, §14): trading costs modeled. Entry is a resting limit at the
# zone edge -> fee only, no slippage. TP is a resting limit -> fee only.
# SL and TIMEOUT exits are market orders -> fee + slippage (0.05 ATR at exit).
# r_multiple is NET of costs; r_gross preserved. Cost constants live in
# setups.py (single source of truth — the setup gate uses the same numbers).


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "execsim", EXEC_VERSION, symbol, tf) as rec:
        # Venue-derived: spot fees on a perp are a 14x over-charge, and
        # they price the slippage on every stop, not just the fees.
        COST_PROFILE = costs.profile_for(symbol)
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        candle_times = [c["open_ts"] for c in candles]
        atr = compute_atr(candles)

        from .scalein import SCALE_VERSION   # lazy: avoids circular import
        setups = {}
        for ver in (SETUP_VERSION, SCALE_VERSION):
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
            risk = (entry - sl) if long else (sl - entry)
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

            fill_i = None
            entry_role = "MAKER"
            if passive_then_cross and maker_limit is not None:
                # Passive leg: the limit rests BETTER than the market, so it can
                # only fill if price comes back. A limit AT the market would be
                # marketable and pay taker — claiming maker for that is a fee
                # saving the exchange never granted.
                wait_end = min(order_i + maker_wait, len(candles))
                for k in range(order_i, wait_end):
                    lo, hi = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
                    if lo <= maker_limit <= hi:
                        fill_i = k
                        entry = maker_limit          # a real, better fill price
                        break
                if fill_i is None and wait_end < len(candles):
                    # CROSS: the passive limit never filled, so we take the
                    # market. A market order fills at the market — NOT at the
                    # plan's price.
                    #
                    # This paid taker at `entry` and left `entry` untouched, and
                    # `entry` is `candles[ci+1]["open"]` (setups.py) — a print
                    # from TWO BARS EARLIER, since order_i = ci+1 and
                    # MAKER_WAIT_BARS = 2 puts the cross on bar ci+3. The comment
                    # at setups.py licensing that price says it is "a price that
                    # demonstrably traded", which is true on the bar it was taken
                    # from and false on the bar it was being applied to.
                    #
                    # Measured on exec-v0.13, 95 crossed orders: 78 (82.1%) were
                    # booked at a price OUTSIDE the fill bar's own [low, high],
                    # and the direction was never adverse — 94 of 95 filled
                    # better than the crossing bar's open. One ETHUSDT long was
                    # booked at 2075.49 on a bar whose LOW was 2094.69. The free
                    # entry advantage totalled +86 R of raw edge.
                    #
                    # Book impact, re-simulated: +95.85 R -> +31.95 R over 642
                    # trades (+0.1493 -> +0.0498 R/trade). REVERSAL on the traded
                    # book falls from +0.266 R CI [+0.038,+0.498] to +0.151 R
                    # CI [-0.066,+0.379] — it stops clearing zero.
                    #
                    # The honest fill is the crossing bar's OPEN: that is the
                    # first price available once the passive window has closed,
                    # it demonstrably traded on THIS bar, and it requires no
                    # assumption about intrabar path. Slippage is charged because
                    # this leg is a market order, exactly as SL and TIMEOUT
                    # exits are.
                    fill_i = wait_end
                    entry_role = "TAKER"
                    cross_open = Decimal(candles[fill_i]["open"])
                    cross_slip = Decimal(0)
                    if atr[fill_i] is not None:
                        cross_slip = COST_PROFILE.market_slippage_atr * atr[fill_i]
                    else:
                        # loud-fallback rule: a degraded path must be audible
                        rec.notes = ((rec.notes or "") +
                                     f" cross slippage NOT applied at bar "
                                     f"{candles[fill_i]['open_ts']} (no ATR);")
                    # Crossing costs you: a long pays up, a short sells down.
                    entry = (cross_open + cross_slip) if long else (cross_open - cross_slip)
                elif fill_i is None:
                    counts["PENDING"] += 1
                    continue
                # A better fill against the SAME structural stop is a smaller
                # risk denominator. Recompute from the actual fill rather than
                # inheriting the plan's, or every passive fill reports inflated R.
                risk = (entry - sl) if long else (sl - entry)
                if risk <= 0:
                    counts["PENDING"] += 1
                    continue
            else:
                entry_role = "TAKER" if market_entry else "MAKER"
                entry_end = min(order_i + MAX_ENTRY_BARS, len(candles))
                for k in range(order_i, entry_end):
                    lo, hi = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
                    if lo <= entry <= hi:
                        fill_i = k
                        break
            if fill_i is None:
                if order_i + MAX_ENTRY_BARS > len(candles):
                    counts["PENDING"] += 1
                    continue
                miss_ts = candles[entry_end - 1]["open_ts"] + tf_seconds
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

            i = fill_i
            fill_ts = candles[i]["open_ts"] + tf_seconds
            store.insert_fact(con, symbol=symbol, tf=tf, kind="order",
                              market_time=s["market_time"], confirmed_at=fill_ts,
                              algo_version=EXEC_VERSION,
                              payload={**order_base, "event": "FILLED",
                                       "fill_price": str(entry),
                                       "entry_fee_role": entry_role,
                                       "bars_to_fill": i - order_i})
            outcome = exit_price = exit_ts = None
            ambiguous = False
            for j in range(i, min(i + MAX_BARS, len(candles))):
                c = candles[j]
                hi, lo = Decimal(c["high"]), Decimal(c["low"])
                hit_sl = lo <= sl if long else hi >= sl
                hit_tp = hi >= tp if long else lo <= tp
                if hit_sl or hit_tp:
                    ambiguous = hit_sl and hit_tp
                    outcome = "SL" if hit_sl else "TP"
                    exit_price = sl if hit_sl else tp
                    exit_ts = c["open_ts"] + tf_seconds
                    break
            else:
                if i + MAX_BARS <= len(candles):   # full window elapsed unresolved
                    j = i + MAX_BARS - 1
                    outcome = "TIMEOUT"
                    exit_price = Decimal(candles[j]["close"])
                    exit_ts = candles[j]["open_ts"] + tf_seconds
            if outcome is None:                    # not enough data yet
                counts["OPEN"] += 1
                continue
            slip = Decimal(0)
            if outcome in ("SL", "TIMEOUT"):
                if atr[j] is not None:
                    slip = COST_PROFILE.market_slippage_atr * atr[j]
                else:
                    # loud-fallback rule: degrading (no slippage modeled) must be audible
                    from .runlog import get_logger
                    get_logger().warning(
                        f"execsim {symbol} {tf}: no ATR at exit bar for {sid} — "
                        f"market-exit slippage NOT applied (results slightly flattering)")
            # Funding accrues over the HOLD, on notional, per settlement.
            holding_hours = Decimal((j - i) * tf_seconds) / Decimal(3600)
            funding_rate = venues.funding_cost_rate(
                symbol, FUNDING_RATE_PER_SETTLEMENT, holding_hours)
            funding_cost = funding_rate * entry      # price units, on notional
            eff_exit = (exit_price - slip) if long else (exit_price + slip)
            exit_rate = (COST_PROFILE.maker_rate if outcome == "TP"
                         else COST_PROFILE.taker_rate)
            entry_rate = (COST_PROFILE.taker_rate if entry_role == "TAKER"
                          else COST_PROFILE.maker_rate)
            # `fees_price_units` means EXCHANGE FEES. Funding was being folded in
            # here while also reported as `funding_price_units`, so any consumer
            # adding the two double-counted the funding leg. Net P&L is
            # unchanged — both are still deducted below — only the labelling is
            # now honest about which cost is which.
            fees = entry_rate * entry + exit_rate * eff_exit
            gross = (exit_price - entry) if long else (entry - exit_price)
            net = (((eff_exit - entry) if long else (entry - eff_exit))
                   - fees - funding_cost)
            r_gross = (gross / risk).quantize(Q2) if risk > 0 else Decimal(0)
            r_mult = (net / risk).quantize(Q2) if risk > 0 else Decimal(0)
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
