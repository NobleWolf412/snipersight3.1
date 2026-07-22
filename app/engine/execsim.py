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
from decimal import Decimal

from . import store
from .setups import SETUP_VERSION, FEE_SIDE, SLIP_ATR
from .swings import compute_atr
from .runlog import RunRecorder

EXEC_VERSION = "exec-v0.6-draft"  # reads setup-v0.5 + scale-v0.1 adds
MAX_BARS = 100
Q2 = Decimal("0.01")

# v0.2 (EXEC-1, §14): trading costs modeled. Entry is a resting limit at the
# zone edge -> fee only, no slippage. TP is a resting limit -> fee only.
# SL and TIMEOUT exits are market orders -> fee + slippage (0.05 ATR at exit).
# r_multiple is NET of costs; r_gross preserved. Cost constants live in
# setups.py (single source of truth — the setup gate uses the same numbers).


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "execsim", EXEC_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)

        from .scalein import SCALE_VERSION   # lazy: avoids circular import
        setups = {}
        for ver in (SETUP_VERSION, SCALE_VERSION):
            for r in store.get_facts(con, symbol, tf, "setup", ver):
                p = json.loads(r["payload"])
                if p["state"] == "VALIDATED":
                    setups[p["setup_id"]] = {"market_time": r["market_time"], **p}
        rec.n_inputs = len(setups)

        n_out = 0
        counts = {"TP": 0, "SL": 0, "TIMEOUT": 0, "OPEN": 0}
        for sid, s in setups.items():
            i = ts_index.get(s["market_time"])
            if i is None:
                continue
            entry, sl, tp = Decimal(s["entry"]), Decimal(s["sl"]), Decimal(s["tp"])
            long = s["direction"] == "LONG"
            risk = (entry - sl) if long else (sl - entry)
            outcome = exit_price = exit_ts = None
            ambiguous = False
            for j in range(i, min(i + MAX_BARS, len(candles))):
                c = candles[j]
                hi, lo = Decimal(c["high"]), Decimal(c["low"])
                hit_sl = lo <= sl if long else hi >= sl
                hit_tp = hi >= tp if long else lo <= tp
                if j == i:          # entry bar: only the zone side is in play
                    hit_tp = False
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
                    slip = SLIP_ATR * atr[j]       # market exit fills worse
                else:
                    # loud-fallback rule: degrading (no slippage modeled) must be audible
                    from .runlog import get_logger
                    get_logger().warning(
                        f"execsim {symbol} {tf}: no ATR at exit bar for {sid} — "
                        f"market-exit slippage NOT applied (results slightly flattering)")
            eff_exit = (exit_price - slip) if long else (exit_price + slip)
            fees = FEE_SIDE * (entry + eff_exit)
            gross = (exit_price - entry) if long else (entry - exit_price)
            net = ((eff_exit - entry) if long else (entry - eff_exit)) - fees
            r_gross = (gross / risk).quantize(Q2) if risk > 0 else Decimal(0)
            r_mult = (net / risk).quantize(Q2) if risk > 0 else Decimal(0)
            counts[outcome] += 1
            payload = {"setup_id": sid, "strategy": s["strategy"],
                       "direction": s["direction"], "outcome": outcome,
                       "entry": str(entry), "exit_price": str(exit_price),
                       "r_multiple": str(r_mult), "r_gross": str(r_gross),
                       "costs_r": str((r_gross - r_mult).quantize(Q2)),
                       "bars_held": j - i, "ambiguous_bar": ambiguous}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="exec",
                                 market_time=s["market_time"], confirmed_at=exit_ts,
                                 algo_version=EXEC_VERSION, payload=payload):
                n_out += 1

        con.commit()
        rec.n_new_facts = n_out
        return {"symbol": symbol, "tf": tf, **counts}
