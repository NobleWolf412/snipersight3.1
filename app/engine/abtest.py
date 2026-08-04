"""2x2 replay harness — the gate on setup-v0.7. READ-ONLY, writes no facts.

`docs/SPEC-confirmed-entry.md` changes the ENTRY (touch -> confirmed close) and
the EXIT (hold-to-SL/TP -> partials + trail + breakeven + time stop) in the same
version. A single before/after therefore cannot attribute the result, and the
attribution is not academic: if the exit change carries the whole improvement,
the confirmation rule is optional complexity that should be DROPPED rather than
shipped. Median MFE 1.53R against a median 6.4R target makes that a live
possibility, not a hedge.

So: four variants over the same candles, same cost model, same code path.

                     hold to SL/TP        managed exit
    touch entry      v0.6 baseline        isolates the EXIT fix
    confirmed entry  isolates the ENTRY   proposed v0.7

WHY THIS HAS ITS OWN SIMULATION CORE, which is normally the wrong answer:
`execsim.py` is the production simulator and a second one risks the two
disagreeing. Two things make it correct here. First, all four variants share
THIS core, so the comparison between them is internally valid regardless of any
absolute offset from production. Second, and the reason it is safe: the harness
CALIBRATES against the recorded book before it reports anything. `calibrate()`
replays the v0.6 setups under the hold-exit variant and compares against the
exec facts execsim actually wrote. If the reproduction drifts beyond a tight
tolerance the harness says so and refuses to present its numbers as comparable —
a measurement tool that cannot reproduce a known result has not earned the right
to describe an unknown one.

Determinism: pure function of stored candles and setup facts. No RNG, no clock,
no network. Decimal throughout for prices.
"""
import json
from decimal import Decimal

from . import costs, execsim, store
from .importer import TF_SECONDS
from .swings import compute_atr

ABTEST_VERSION = "abtest-v0.1"

# The engine's own window, not a copy that "matches" it. A comment claiming
# equality is the roster disease — the number it describes drifts and the
# comment stays.
MAX_HOLD_BARS = execsim.MAX_BARS
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")

# --- managed-exit parameters (SPEC-confirmed-entry §1.6) ---
TP1_R = Decimal("1.5")            # first target, in R
PARTIAL_FRACTION = Decimal("0.5")  # fraction closed at TP1
TRAIL_ACTIVATE_R = Decimal("1.5")
TRAIL_DISTANCE_R = Decimal("0.5")
BE_TRIGGER_R = Decimal("1.0")
STAGNATION_FLOOR_RATIO = Decimal("0.7")
# Adaptive time stop, in BARS of the setup's own timeframe rather than hours —
# the same 48h means something different on 15m and 1D, and bar-counting keeps
# the harness free of wall-clock reasoning.
HOLD_BARS_BY_TF = {"15m": 20, "1H": 14, "4H": 12, "1D": 10, "1W": 8}
# Bars a maker limit rests before it is abandoned. Short on purpose: the
# thesis is 'the level held and price is leaving', so a limit that has not
# filled in two bars is waiting for a move that already went without it.
MAKER_WAIT_BARS = 2
# How far better than the market the maker limit rests, in R of the
# PLANNED risk. Must be > 0 or the order is marketable and pays taker.
MAKER_OFFSET_R = Decimal("0.10")


class _Pos:
    """Open position state. Exists because a managed exit cannot be expressed
    as a single terminal outcome — partials mean realised R accrues in pieces."""

    __slots__ = ("entry", "sl", "tp", "long", "risk", "qty", "realised_r",
                 "be_moved", "trailing", "extreme", "partials")

    def __init__(self, entry, sl, tp, long, risk):
        self.entry, self.sl, self.tp, self.long, self.risk = entry, sl, tp, long, risk
        self.qty = Decimal(1)
        self.realised_r = Decimal(0)
        self.be_moved = False
        self.trailing = False
        self.extreme = entry
        self.partials = []

    def r_at(self, price):
        move = (price - self.entry) if self.long else (self.entry - price)
        return move / self.risk


def _leg_r(profile, symbol, entry, px, risk, long, taker_in, taker_out,
           atr_exit, bars_held, tf_seconds):
    """NET R of one closed leg, priced by execsim.settle — THE costing.

    This replaces a local `_cost_r` that had already drifted from the engine in
    the two ways copies drift: its exit fee was charged on the nominal price
    where the engine charges the slipped one, and it never charged funding —
    the cost execsim v0.12 added precisely because an unmodelled cost that only
    ever flatters is the kind that survives review. Every cell of the 2x2 was
    flattered by the funding its holds accrued; the managed cells, which hold
    longest, were flattered most, and the harness's whole job is comparing them.

    Per-leg funding is correct by distribution: settle charges funding on the
    FULL notional to this leg's close, and the caller multiplies the leg by its
    fraction — fraction x full == funding on the fraction. The entry fee sums
    the same way across legs to exactly one entry's fee.
    """
    st = execsim.settle(profile, symbol, entry, px, risk, long,
                        "SL" if taker_out else "TP",
                        bars_held, tf_seconds, atr_exit,
                        entry_role="TAKER" if taker_in else "MAKER")
    return st["r_mult"]


def _simulate(candles, atr, i_fill, entry, sl, tp, long, tf, profile, managed,
              taker_in, *, symbol, tf_seconds, partials=None, trail=None,
              timestop=None):
    """Walk bars from the fill and return one outcome dict, or None if the data
    runs out before the position resolves (OPEN — never counted as a result).

    Conservative rule kept from execsim: a bar that touches BOTH stop and target
    counts as the STOP. Sub-bar sequencing needs lower-timeframe data we do not
    have, and flattering an ambiguous bar is how a backtest lies.
    """
    # The managed exit was rejected as a BUNDLE (partials + breakeven + trail +
    # time stop), and a bundle verdict is not a component verdict. Each piece is
    # now switchable so it can earn or lose on its own merits; `managed` remains
    # the shorthand for "all of them", which is what the 2x2 measured.
    use_partials = managed if partials is None else partials
    use_trail = managed if trail is None else trail
    use_timestop = managed if timestop is None else timestop
    risk = (entry - sl) if long else (sl - entry)
    if risk <= 0:
        return None

    if not (use_partials or use_trail or use_timestop):
        # The hold cell IS the engine. No re-implementation, however faithful:
        # the walk that settles the record walks the counterfactual, so the
        # baseline cell of every 2x2 agrees with execsim by construction —
        # which is what the calibrate() pass used to have to establish
        # empirically, and what the drift it tolerated used to erode.
        w = execsim.walk_exit(candles, i_fill, sl, tp, long,
                              max_bars=MAX_HOLD_BARS)
        if w is None:
            return None                       # OPEN — never counted as a result
        outcome, px, j, _ambiguous = w
        st = execsim.settle(profile, symbol, entry, px, risk, long, outcome,
                            j - i_fill, tf_seconds, atr[j],
                            entry_role="TAKER" if taker_in else "MAKER")
        held = candles[i_fill:j + 1]
        if long:
            mfe = max(Decimal(c["high"]) - entry for c in held) / risk
            mae = max(entry - Decimal(c["low"]) for c in held) / risk
        else:
            mfe = max(entry - Decimal(c["low"]) for c in held) / risk
            mae = max(Decimal(c["high"]) - entry for c in held) / risk
        return {"outcome": outcome, "r": st["r_mult"],
                "bars_held": j - i_fill,
                "same_bar": j == i_fill and outcome in ("SL", "TP"),
                "mfe_r": max(mfe, Decimal(0)), "mae_r": max(mae, Decimal(0)),
                "partials": [], "r_if_held": None}

    pos = _Pos(entry, sl, tp, long, risk)
    max_hold = HOLD_BARS_BY_TF.get(tf, 12) if use_timestop else MAX_HOLD_BARS
    limit = min(i_fill + MAX_HOLD_BARS, len(candles))
    same_bar = False
    mfe = mae = Decimal(0)

    for j in range(i_fill, limit):
        c = candles[j]
        hi, lo = Decimal(c["high"]), Decimal(c["low"])
        fav = (hi - entry) if long else (entry - lo)
        adv = (entry - lo) if long else (hi - entry)
        mfe = max(mfe, fav / risk)
        mae = max(mae, adv / risk)
        bars_held = j - i_fill

        if use_partials:
            # TP1 partial. Checked before the stop on the same bar ONLY when the
            # bar's own extreme reached it before the stop could have — which we
            # cannot know from OHLC. So: if both are touched on one bar, the stop
            # wins and no partial is booked. Conservative, and it keeps the
            # partial from manufacturing profit out of an ambiguous bar.
            tp1 = entry + TP1_R * risk if long else entry - TP1_R * risk
            hit_tp1 = (hi >= tp1) if long else (lo <= tp1)
            hit_sl_now = (lo <= pos.sl) if long else (hi >= pos.sl)
            # A partial moves the stop to breakeven. If THIS SAME BAR also
            # trades through breakeven, we would be claiming the high came
            # before the low — intrabar ordering OHLC cannot tell us. execsim's
            # convention for that ambiguity is "stop first", and it must apply
            # here or the managed-exit cells get to bank a profit out of a bar
            # that may have gone the other way first. Skipping the partial on
            # such a bar is the conservative reading, and it matters most
            # exactly where the bars are largest relative to risk — which is
            # the touch-entry cell this comparison is judging.
            # Strict: a bar whose low merely TOUCHES entry has not traded
            # through breakeven, and the fill sits at that price anyway.
            be_touched_same_bar = (lo < entry) if long else (hi > entry)
            if hit_tp1 and not hit_sl_now and not be_touched_same_bar \
                    and not pos.partials:
                booked = PARTIAL_FRACTION * _leg_r(
                    profile, symbol, entry, tp1, risk, long, taker_in, False,
                    None, bars_held, tf_seconds)
                pos.realised_r += booked
                pos.qty -= PARTIAL_FRACTION
                pos.partials.append({"r": str(TP1_R.quantize(Q2)),
                                     "fraction": str(PARTIAL_FRACTION),
                                     "bar": bars_held})
                # breakeven follows the first partial: the remainder is now
                # riding on money already banked
                pos.sl = entry
                pos.be_moved = True

        if use_trail:
            if not pos.be_moved:
                r_now = pos.r_at(hi if long else lo)
                if r_now >= BE_TRIGGER_R:
                    pos.sl = entry
                    pos.be_moved = True

            pos.extreme = max(pos.extreme, hi) if long else min(pos.extreme, lo)
            ext_r = pos.r_at(pos.extreme)
            if ext_r >= TRAIL_ACTIVATE_R:
                pos.trailing = True
            if pos.trailing:
                trail = (pos.extreme - TRAIL_DISTANCE_R * risk) if long \
                    else (pos.extreme + TRAIL_DISTANCE_R * risk)
                pos.sl = max(pos.sl, trail) if long else min(pos.sl, trail)

        hit_sl = (lo <= pos.sl) if long else (hi >= pos.sl)
        hit_tp = (hi >= pos.tp) if long else (lo <= pos.tp)
        if hit_sl or hit_tp:
            if bars_held == 0:
                same_bar = True
            outcome = "SL" if hit_sl else "TP"
            px = pos.sl if hit_sl else pos.tp
            taker_out = hit_sl
            leg_r = _leg_r(profile, symbol, entry, px, risk, long, taker_in,
                           taker_out, atr[j], bars_held, tf_seconds)
            total = pos.realised_r + pos.qty * leg_r
            return {"outcome": outcome, "r": total, "bars_held": bars_held,
                    "same_bar": same_bar, "mfe_r": mfe, "mae_r": mae,
                    "partials": pos.partials,
                    "r_if_held": None}

        if use_timestop and bars_held >= max_hold:
            # Adaptive time stop, with the floor guard: never time-stop a trade
            # already most of the way to its stop — defer to the stop, which is
            # the exit that was actually planned for that outcome.
            px = Decimal(c["close"])
            if pos.r_at(px) <= -STAGNATION_FLOOR_RATIO:
                continue
            leg_r = _leg_r(profile, symbol, entry, px, risk, long, taker_in,
                           True, atr[j], bars_held, tf_seconds)
            total = pos.realised_r + pos.qty * leg_r
            return {"outcome": "TIME", "r": total, "bars_held": bars_held,
                    "same_bar": False, "mfe_r": mfe, "mae_r": mae,
                    "partials": pos.partials, "r_if_held": None}

    if not use_timestop and i_fill + MAX_HOLD_BARS <= len(candles):
        j = i_fill + MAX_HOLD_BARS - 1
        c = candles[j]
        px = Decimal(c["close"])
        leg_r = _leg_r(profile, symbol, entry, px, risk, long, taker_in, True,
                       atr[j], j - i_fill, tf_seconds)
        return {"outcome": "TIMEOUT", "r": pos.realised_r + pos.qty * leg_r,
                "bars_held": MAX_HOLD_BARS - 1, "same_bar": False,
                "mfe_r": mfe, "mae_r": mae, "partials": [], "r_if_held": None}
    return None                                    # still open at end of data


def _load_setups(con, symbol, tf, version):
    out = {}
    for r in store.get_facts(con, symbol, tf, "setup", version):
        p = json.loads(r["payload"])
        if p.get("state") != "VALIDATED" or not p.get("entry"):
            continue
        out[p["setup_id"]] = {"confirmed_at": r["confirmed_at"],
                              "market_time": r["market_time"], **p}
    return out


def _bisect_fill(candle_times, available_at):
    lo, hi = 0, len(candle_times)
    while lo < hi:
        mid = (lo + hi) // 2
        if candle_times[mid] < available_at:
            lo = mid + 1
        else:
            hi = mid
    return lo


def run_variant(con, symbols, tfs, setup_version, *, managed, entry_model,
                profile_override=None, partials=None, trail=None,
                timestop=None):
    """One cell of the 2x2. Returns per-trade results, never aggregates alone.

    `profile_override` exists for calibration only. Reproducing a historical
    result requires the cost model that PRODUCED it, and execsim wrote every
    recorded fact under the venue-blind Coinbase default (fixed 2026-07-30, see
    costs.profile_for). Replaying that book with the corrected 14x-cheaper perp
    fees is not a reproduction — it is a different experiment that happens to
    share inputs. The 2x2 cells all use the CORRECTED model, so the comparison
    between them stays internally valid.
    """
    results = []
    for symbol in symbols:
        profile = profile_override or costs.profile_for(symbol)
        for tf in tfs:
            candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
            if not candles:
                continue
            atr = compute_atr(candles)
            times = [c["open_ts"] for c in candles]
            idx = {t: i for i, t in enumerate(times)}
            for sid, s in _load_setups(con, symbol, tf, setup_version).items():
                entry, sl, tp = (Decimal(s["entry"]), Decimal(s["sl"]),
                                 Decimal(s["tp"]))
                long = s["direction"] == "LONG"
                if entry_model in ("MAKER_PULLBACK", "MAKER_THEN_MARKET"):
                    # Maker variant of the confirmed entry. The break-even fee on
                    # the live book sits at 0.033%/side against Phemex taker
                    # 0.06% / maker 0.01%, so the entry fee role alone spans the
                    # difference between a losing and a winning book. But it
                    # cannot be assumed: `entrystats` measured v0.6's resting
                    # limits as ADVERSELY SELECTED — the 90 misses had a 58.4%
                    # target rate against 12.7% for the fills, because price came
                    # back to the level precisely when the level was failing.
                    #
                    # This variant is materially different from that one: the
                    # limit rests AFTER a confirming close, not before it, so it
                    # is not waiting to find out whether the zone holds. Whether
                    # that removes the adverse selection is exactly what this
                    # cell exists to answer.
                    ci = idx.get(s.get("confirmed_bar_ts"))
                    if ci is None or ci + 1 >= len(candles):
                        continue
                    # A limit AT the next open is marketable — it crosses the
                    # spread and pays TAKER. Claiming maker for it would be a
                    # free lunch invented by the model, so the limit must rest
                    # at a BETTER price than the market and genuinely wait.
                    base_risk = (entry - sl) if long else (sl - entry)
                    if base_risk <= 0:
                        continue
                    px = (entry - MAKER_OFFSET_R * base_risk) if long                         else (entry + MAKER_OFFSET_R * base_risk)
                    i_fill = None
                    for k in range(ci + 1, min(ci + 1 + MAKER_WAIT_BARS, len(candles))):
                        lo_k, hi_k = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
                        if lo_k <= px <= hi_k:
                            i_fill = k
                            break
                    if i_fill is None:
                        if entry_model == "MAKER_THEN_MARKET":
                            # Post passive, cross if it does not fill. The pure
                            # maker variant is ADVERSELY SELECTED — measured on
                            # this book, its 32 unfilled orders would have made
                            # +0.365R each at market against +0.074R for the ones
                            # that filled. Price walked away precisely when the
                            # trade was right. Saving a fee by declining those is
                            # paying for the fee with the edge.
                            #
                            # THE CROSS IS execsim's CROSS, and until 4 Aug 2026
                            # it was not. This booked `entry` — the plan's price,
                            # a print from two bars earlier — at bar ci+1, while
                            # execsim had already been fixed to take the CROSSING
                            # bar's open plus slippage at the end of the passive
                            # window. So the harness built to validate the
                            # simulator was running the exact bug the simulator
                            # had corrected, and flattered the book by 62 R
                            # (70.0 replayed against 7.9 recorded).
                            i_fill = ci + 1 + MAKER_WAIT_BARS
                            if i_fill >= len(candles):
                                continue          # the window has not closed yet
                            entry_px, _ = execsim.cross_fill(
                                candles, i_fill, long, atr[i_fill], profile)
                            taker_in = True
                        else:
                            if ci + 1 + MAKER_WAIT_BARS <= len(candles):
                                results.append({"setup_id": sid, "symbol": symbol,
                                                "tf": tf, "outcome": "MISSED",
                                                "r": Decimal(0), "same_bar": False,
                                                "bars_held": 0, "filled": False})
                            continue
                    else:
                        entry_px = px
                        taker_in = False
                    entry = entry_px
                    # A better fill with the SAME structural stop is a smaller
                    # risk denominator, so R is recomputed from the real fill —
                    # not inherited from the plan. Reusing the planned R here
                    # would silently inflate every maker trade.
                elif entry_model == "MARKET_NEXT_OPEN":
                    # The setup already records the next bar's open as `entry`;
                    # the fill bar is the one whose open_ts follows the
                    # confirmation bar. No lookahead: both had already closed.
                    ci = idx.get(s.get("confirmed_bar_ts"))
                    i_fill = (ci + 1) if ci is not None else None
                    if i_fill is None or i_fill >= len(candles):
                        continue
                    taker_in = True
                else:
                    # Resting limit: the original model. It may never fill, and
                    # a MISS is a real outcome — 90 of 232 in the recorded book.
                    order_i = _bisect_fill(times, s["confirmed_at"])
                    i_fill = None
                    entry_end = min(order_i + execsim.MAX_ENTRY_BARS, len(candles))
                    for k in range(order_i, entry_end):
                        if Decimal(candles[k]["low"]) <= entry <= Decimal(candles[k]["high"]):
                            i_fill = k
                            break
                    if i_fill is None:
                        if order_i + execsim.MAX_ENTRY_BARS <= len(candles):
                            results.append({"setup_id": sid, "symbol": symbol,
                                            "tf": tf, "outcome": "MISSED",
                                            "r": Decimal(0), "same_bar": False,
                                            "bars_held": 0, "filled": False})
                        continue
                    taker_in = False
                out = _simulate(candles, atr, i_fill, entry, sl, tp, long, tf,
                                profile, managed, taker_in,
                                symbol=symbol, tf_seconds=TF_SECONDS[tf],
                                partials=partials, trail=trail,
                                timestop=timestop)
                if out is None:
                    continue
                results.append({"setup_id": sid, "symbol": symbol, "tf": tf,
                                "filled": True, **out})
    return results


def summarise(results) -> dict:
    filled = [r for r in results if r.get("filled")]
    rs = [float(r["r"]) for r in filled]
    if not rs:
        return {"n": 0, "missed": sum(1 for r in results if not r.get("filled")),
                "note": "no filled trades — nothing to report"}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    same_bar_losers = [r for r in filled
                       if r.get("same_bar") and float(r["r"]) <= 0]
    n_loss = sum(1 for r in rs if r <= 0)
    return {
        "n": len(rs),
        "missed": sum(1 for r in results if not r.get("filled")),
        "win_pct": round(100 * len(wins) / len(rs), 1),
        "sum_r": round(sum(rs), 1),
        "expectancy_r": round(sum(rs) / len(rs), 4),
        "profit_factor": (round(sum(wins) / abs(sum(losses)), 2)
                          if losses and wins else None),
        # THE metric this whole version exists to move: 59% on the v0.6 book.
        "same_bar_stopout_pct": (round(100 * len(same_bar_losers) / n_loss, 1)
                                 if n_loss else None),
        "median_bars_held": sorted(r["bars_held"] for r in filled)[len(filled) // 2],
        "partial_rate_pct": round(
            100 * sum(1 for r in filled if r.get("partials")) / len(filled), 1),
    }


def calibrate(con, symbols, tfs, tolerance=0.15) -> dict:
    """Reproduce the RECORDED v0.6 book, and say plainly whether we managed it.

    This is the harness's licence to be believed. It replays setup-v0.6 under
    the touch-entry + hold-exit variant — which is exactly what execsim already
    simulated — and compares against the exec facts on disk. Drift beyond
    `tolerance` means the core disagrees with production, and the 2x2 numbers
    must not then be presented as comparable to anything.
    """
    import re
    from collections import Counter
    from .execsim import EXEC_VERSION
    recorded, generations = [], Counter()
    for symbol in symbols:
        for tf in tfs:
            for r in store.get_facts(con, symbol, tf, "exec", EXEC_VERSION):
                p = json.loads(r["payload"])
                # LIKE FOR LIKE. A scale-in leg reuses its PARENT's setup_id
                # (scalein.py), so these facts carry `setup-v0.16-draft` in the
                # id while being produced by scale-v0.14 — and `run_variant` is
                # given one setup version, so it can never produce them. Counted
                # here, they were 2 trades and -2.07 R the replay was structurally
                # unable to reproduce, which on a book totalling 7.9 R showed as
                # 26% drift and kept calibration red after everything real had
                # been fixed. Grade the adds by replaying SCALE_VERSION, not by
                # folding them into a setup-version comparison.
                if p.get("strategy") == "SCALE_IN":
                    continue
                if p["outcome"] != "MISSED":
                    recorded.append(float(p["r_multiple"]))
                m = re.search(r"setup-v[\d.]+-draft", p.get("setup_id") or "")
                if m:
                    generations[m.group(0)] += 1
    if not generations:
        return {"status": "UNAVAILABLE", "trustworthy": False,
                "detail": "no recorded book to calibrate against"}

    # WHICH GENERATION THE RECORDED BOOK ACTUALLY IS, derived rather than
    # assumed. This replayed a hardcoded "setup-v0.6-draft" — correct when the
    # harness was written as the gate on v0.7, and meaningless ten versions
    # later. Measured 4 Aug 2026: every one of the 499 recorded exec facts came
    # from setup-v0.16, so the harness was replaying one book and comparing it
    # against a different one, drifting 71.6% BY CONSTRUCTION and reporting its
    # own core as untrustworthy when the core was fine and the comparison was
    # wrong. A calibration that cannot go green is worse than none: it retires
    # the tool silently.
    version = generations.most_common(1)[0][0]

    # The conditions that PRODUCED that book, which are version-dependent.
    # v0.6/v0.7 were simulated touch-entry under the venue-blind Coinbase
    # default; everything since is the entry model the setup declares, exits
    # held to SL/TP (the managed exit was rejected by its own 2x2 gate — see
    # execsim line 105), and venue-derived costs.
    legacy = version in ("setup-v0.6-draft", "setup-v0.7-draft")
    replayed = run_variant(
        con, symbols, tfs, version, managed=False,
        entry_model="LIMIT_AT_EDGE" if legacy else "MAKER_THEN_MARKET",
        profile_override=costs.DEFAULT_COST_PROFILE if legacy else None)
    rep = summarise(replayed)
    if not recorded or not rep.get("n"):
        return {"status": "UNAVAILABLE", "trustworthy": False,
                "detail": "no recorded book to calibrate against"}
    rec_sum, rec_n = sum(recorded), len(recorded)
    drift_n = abs(rep["n"] - rec_n) / rec_n
    denom = abs(rec_sum) or 1.0
    drift_r = abs(rep["sum_r"] - rec_sum) / denom
    ok = drift_n <= tolerance and drift_r <= tolerance
    return {
        "status": "OK" if ok else "DRIFT",
        "trustworthy": ok,
        "recorded": {"n": rec_n, "sum_r": round(rec_sum, 1)},
        "replayed": {"n": rep["n"], "sum_r": rep["sum_r"]},
        "drift_n": round(drift_n, 3), "drift_sum_r": round(drift_r, 3),
        "tolerance": tolerance,
        "detail": ("core reproduces the recorded book" if ok else
                   "REPLAY DISAGREES WITH THE RECORDED BOOK — the 2x2 numbers "
                   "below are NOT comparable to production and must not be used "
                   "to accept or reject the change"),
    }


CELLS = (
    ("touch_hold", "setup-v0.6-draft", False, "LIMIT_AT_EDGE",
     "v0.6 baseline"),
    ("touch_managed", "setup-v0.6-draft", True, "LIMIT_AT_EDGE",
     "isolates the EXIT fix"),
    ("confirmed_hold", "setup-v0.7-draft", False, "MARKET_NEXT_OPEN",
     "isolates the ENTRY fix"),
    ("confirmed_managed", "setup-v0.7-draft", True, "MARKET_NEXT_OPEN",
     "proposed v0.7"),
)


def report(con, symbols=None, tfs=("15m", "1H", "4H", "1D", "1W")) -> dict:
    from .universe import all_tracked_symbols
    symbols = symbols or all_tracked_symbols(con)
    cal = calibrate(con, symbols, tfs)
    cells = {}
    for key, version, managed, entry_model, label in CELLS:
        res = run_variant(con, symbols, tfs, version, managed=managed,
                          entry_model=entry_model)
        cells[key] = {"label": label, "setup_version": version,
                      "managed_exit": managed, "entry_model": entry_model,
                      **summarise(res)}
    return {"version": ABTEST_VERSION, "calibration": cal,
            "trustworthy": cal.get("trustworthy", False), "cells": cells,
            "verdict": _verdict(cells, cal)}


def _verdict(cells, cal) -> dict:
    """State which change earned the result — including 'neither'."""
    if not cal.get("trustworthy"):
        return {"call": "INDETERMINATE",
                "detail": "calibration failed; no conclusion may be drawn"}
    base = cells.get("touch_hold", {})
    exit_only = cells.get("touch_managed", {})
    entry_only = cells.get("confirmed_hold", {})
    both = cells.get("confirmed_managed", {})
    if not base.get("n"):
        return {"call": "INDETERMINATE", "detail": "no baseline trades"}

    def exp(c):
        return c.get("expectancy_r")

    b = exp(base)
    improves = {k: (exp(c) is not None and b is not None and exp(c) > b)
                for k, c in (("exit", exit_only), ("entry", entry_only),
                             ("both", both))}
    small = [k for k, c in (("exit", exit_only), ("entry", entry_only),
                            ("both", both)) if (c.get("n") or 0) < 30]
    # "Both beat the baseline" is a shallow reading and would have shipped the
    # wrong thing here. What decides the change is whether the COMBINATION beats
    # the best single change — two fixes that each help alone can interact
    # badly, and that interaction is the entire reason this is a 2x2 rather than
    # two A/Bs.
    singles = {k: exp(c) for k, c in (("exit", exit_only), ("entry", entry_only))
               if exp(c) is not None}
    best_single = max(singles.values()) if singles else None
    combo = exp(both)
    # Precedence matters. "Nothing helped" must be decided BEFORE antagonism,
    # or a uniformly losing 2x2 gets reported as an interesting interaction —
    # and antagonism is only a meaningful call when both changes helped alone,
    # because that is the case where a naive reading would ship both.
    if not any(improves.values()):
        return {"call": "NEITHER_HELPS",
                "detail": ("neither change improves expectancy — the pullback "
                           "premise itself is the thing to re-open, and no "
                           "further strategies should be built on it"),
                "baseline_expectancy_r": b,
                "underpowered_cells": small,
                "caveat": ("cells with n<30 are reported but must not decide "
                           "anything" if small else None)}
    antagonistic = (improves["exit"] and improves["entry"]
                    and best_single is not None and combo is not None
                    and combo < best_single)
    if antagonistic:
        winner = max(singles, key=singles.get)
        call = "ANTAGONISTIC"
        detail = (f"both changes beat the baseline alone, but COMBINED they are "
                  f"worse than the '{winner}' change on its own "
                  f"({combo:+.4f}R vs {best_single:+.4f}R). Ship the single "
                  f"change that wins and re-test the other against it — "
                  f"shipping both would knowingly pick the weaker system.")
    elif improves["exit"] and not improves["entry"]:
        call = "EXIT_CARRIES_IT"
        detail = ("the managed exit improves expectancy and the confirmation "
                  "rule does not — per the spec, confirmation is optional "
                  "complexity and should be dropped, not shipped")
    elif improves["entry"] and not improves["exit"]:
        call = "ENTRY_CARRIES_IT"
        detail = "confirmation improves expectancy; the exit change is neutral here"
    elif improves["entry"] and improves["exit"]:
        call = "BOTH_HELP"
        detail = "both changes improve expectancy, and together beat either alone"
    else:
        call = "NEITHER_HELPS"
        detail = ("neither change improves expectancy — the pullback premise "
                  "itself is the thing to re-open, and no further strategies "
                  "should be built on it")
    return {"call": call, "detail": detail,
            "baseline_expectancy_r": b,
            "underpowered_cells": small,
            "caveat": ("cells with n<30 are reported but must not decide "
                       "anything" if small else None)}


def main():
    import sys
    con = store.connect()
    try:
        rep = report(con)
    finally:
        con.close()
    cal = rep["calibration"]
    print(f"\ncalibration: {cal['status']} — {cal['detail']}")
    if cal.get("recorded"):
        print(f"  recorded n={cal['recorded']['n']} sumR={cal['recorded']['sum_r']}"
              f"   replayed n={cal['replayed']['n']} sumR={cal['replayed']['sum_r']}")
    print(f"\n{'cell':22} {'n':>5} {'win%':>6} {'sumR':>8} {'exp R':>8} "
          f"{'sameBar%':>9} {'missed':>7}")
    for key, _, _, _, _ in CELLS:
        c = rep["cells"][key]
        print(f"{key:22} {c.get('n',0):>5} {c.get('win_pct','—'):>6} "
              f"{c.get('sum_r','—'):>8} {c.get('expectancy_r','—'):>8} "
              f"{c.get('same_bar_stopout_pct','—'):>9} {c.get('missed',0):>7}")
    v = rep["verdict"]
    print(f"\nVERDICT: {v['call']} — {v['detail']}")
    if v.get("caveat"):
        print(f"CAVEAT: {v['caveat']} ({', '.join(v['underpowered_cells'])})")
    if not rep["trustworthy"]:
        print("\nTHESE NUMBERS ARE NOT TRUSTWORTHY — calibration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
