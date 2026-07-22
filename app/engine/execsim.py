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

from . import costs, store
from .setups import SETUP_VERSION, COST_PROFILE
from .swings import compute_atr
from .runlog import RunRecorder

EXEC_VERSION = "exec-v0.7-draft"
MAX_BARS = 100
MAX_ENTRY_BARS = 4
Q2 = Decimal("0.01")

# v0.2 (EXEC-1, §14): trading costs modeled. Entry is a resting limit at the
# zone edge -> fee only, no slippage. TP is a resting limit -> fee only.
# SL and TIMEOUT exits are market orders -> fee + slippage (0.05 ATR at exit).
# r_multiple is NET of costs; r_gross preserved. Cost constants live in
# setups.py (single source of truth — the setup gate uses the same numbers).


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "execsim", EXEC_VERSION, symbol, tf) as rec:
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
            order_base = {"setup_id": sid, "side": s["direction"],
                          "order_type": "LIMIT", "limit_price": str(entry),
                          "available_at": available_at,
                          "max_entry_bars": MAX_ENTRY_BARS,
                          "cost_manifest_hash": cost_manifest_hash}
            store.insert_fact(con, symbol=symbol, tf=tf, kind="order",
                              market_time=s["market_time"], confirmed_at=available_at,
                              algo_version=EXEC_VERSION,
                              payload={**order_base, "event": "PLACED"})

            fill_i = None
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
                payload = {"setup_id": sid, "strategy": s["strategy"],
                           "direction": s["direction"], "outcome": "MISSED",
                           "entry": str(entry), "exit_price": None,
                           "r_multiple": "0", "r_gross": "0", "costs_r": "0",
                           "bars_held": 0, "bars_to_fill": None,
                           "available_at": available_at, "fill_ts": None,
                           "ambiguous_bar": False,
                           "cost_manifest_hash": cost_manifest_hash,
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
            eff_exit = (exit_price - slip) if long else (exit_price + slip)
            exit_rate = (COST_PROFILE.maker_rate if outcome == "TP"
                         else COST_PROFILE.taker_rate)
            fees = COST_PROFILE.maker_rate * entry + exit_rate * eff_exit
            gross = (exit_price - entry) if long else (entry - exit_price)
            net = ((eff_exit - entry) if long else (entry - eff_exit)) - fees
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
            payload = {"setup_id": sid, "strategy": s["strategy"],
                       "direction": s["direction"], "outcome": outcome,
                       "entry": str(entry), "exit_price": str(exit_price),
                       "effective_exit_price": str(eff_exit),
                       "fees_price_units": str(fees),
                       "r_multiple": str(r_mult), "r_gross": str(r_gross),
                       "costs_r": str((r_gross - r_mult).quantize(Q2)),
                       "bars_held": j - i, "bars_to_fill": i - order_i,
                       "mae_r": str((mae / risk).quantize(Q2)) if risk > 0 else "0",
                       "mfe_r": str((mfe / risk).quantize(Q2)) if risk > 0 else "0",
                       "available_at": available_at, "fill_ts": fill_ts,
                       "ambiguous_bar": ambiguous,
                       "entry_fee_role": "MAKER",
                       "exit_fee_role": "MAKER" if outcome == "TP" else "TAKER",
                       "cost_manifest_hash": cost_manifest_hash,
                       "manifest_hash": s.get("manifest_hash")}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="exec",
                                 market_time=s["market_time"], confirmed_at=exit_ts,
                                 algo_version=EXEC_VERSION, payload=payload):
                n_out += 1

        con.commit()
        rec.n_new_facts = n_out
        return {"symbol": symbol, "tf": tf, **counts}
