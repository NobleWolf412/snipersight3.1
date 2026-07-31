"""Liquidity engine — equal highs/lows pools and sweeps. algo liq-v0.1-draft.

Draft methodology (spec §24; versioned):
- Pool: two+ LOCAL swing highs (lows) within 0.10*ATR of each other, formed
  within 100 bars of each other. The pool is anchored at the LATER swing and
  exists from that swing's confirmed_at. Level = the extreme of the cluster.
- SWEEP: a closed bar trades beyond the level but closes back inside
  (high > level, close <= level for a high-side pool) -> rejected sweep (§24).
- BROKEN: a bar CLOSES beyond level + tolerance -> pool consumed, no sweep.
- One terminal event per pool in draft (first sweep or break ends the scan).
"""
import json
from decimal import Decimal

from . import store
from .swings import compute_atr, SWING_VERSION, quote_ticks
from .runlog import RunRecorder

LIQ_VERSION = "liq-v0.11-draft"
# v0.11: the v0.10 collapse keyed on market_time alone; a bar hosting both a
# promoted HIGH and a promoted LOW (2025-10-10 carries a MAJOR pair on three
# symbols) had one twin shadow the other out of pool membership. Identity is
# (market_time, type). Caught in the first live v0.10 cycle.
# v0.10: cascade from swing-v0.9. v0.8 swings re-emitted every promoted pivot
# every cycle, and identical-price phantom copies are trivially inside any
# equal-tolerance — pool n_members inflated as the scanner ran. The swing read
# now collapses to one row per pivot; pool membership counts pivots again.
# Promotion confirmed_at moved too (held window close), so pools are anchored
# and knowable later.
# v0.9: the pool break tolerance was max(TICK, 0.05*ATR) with TICK hard-coded to
# 0.01 — right for BTC-USD, catastrophically wrong below a dollar, where a
# tolerance wider than any move the instrument makes means no close ever breaks
# a pool, so every pool resolves as a SWEEP or never resolves at all. The tick
# is now derived per bar from the exponent of the venue's own price strings;
# `swings.quote_ticks` is the single definition of it and carries the
# measurement. Same rule, implemented honestly — it returns exactly 0.01
# wherever 0.01 was right.

# v0.2: pools cluster INTERMEDIATE+ swings (was LOCAL) — matches user's
# macro liquidity ladder (golden-btc-1d.json).
POOL_TIERS = ("INTERMEDIATE", "MAJOR")
EQ_ATR = Decimal("0.10")
TOL_ATR = Decimal("0.05")
MAX_BARS_APART = 100


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "liquidity", LIQ_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)

        # One member per pivot, LATEST row winning (get_facts orders by
        # market_time, confirmed_at, id) — n_members counts pivots, not copies.
        # Identity is (market_time, TYPE): a bar can host both a promoted HIGH
        # and a promoted LOW, one per side.
        latest = {}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in POOL_TIERS:
                latest[(r["market_time"], p["type"])] = {
                    "market_time": r["market_time"],
                    "confirmed_at": r["confirmed_at"],
                    "type": p["type"], "price": Decimal(p["price"])}
        swings = {"HIGH": [], "LOW": []}
        for s in latest.values():
            swings[s.pop("type")].append(s)
        rec.n_inputs = len(swings["HIGH"]) + len(swings["LOW"])
        n_pools = n_events = 0

        for side in ("HIGH", "LOW"):
            arr = sorted(swings[side], key=lambda s: s["market_time"])
            claimed_member_ts: set[int] = set()
            for k, s in enumerate(arr):
                i = ts_index.get(s["market_time"])
                if i is None or atr[i] is None:
                    continue
                eq_tol = EQ_ATR * atr[i]
                members = [t for t in arr[:k]
                           if 0 < (s["market_time"] - t["market_time"]) <= MAX_BARS_APART * tf_seconds
                           and abs(t["price"] - s["price"]) <= eq_tol]
                if not members:
                    continue
                cluster = members + [s]
                member_ts = {t["market_time"] for t in cluster}
                # One canonical pool per overlapping swing cluster. Later
                # qualifying members belong to the existing pool rather than
                # spawning correlated duplicate targets.
                if member_ts & claimed_member_ts:
                    continue
                claimed_member_ts.update(member_ts)
                level = (max if side == "HIGH" else min)(t["price"] for t in cluster)
                pool_id = f"{symbol}|{tf}|EQ{side[0]}|{s['market_time']}"
                base = {"pool_id": pool_id, "side": side, "level": str(level),
                        "n_members": len(cluster),
                        "member_ts": sorted(member_ts), "state": "ACTIVE"}
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="liquidity",
                                     market_time=s["market_time"],
                                     confirmed_at=s["confirmed_at"],
                                     algo_version=LIQ_VERSION,
                                     payload={**base, "event": "POOL"}):
                    n_pools += 1

                swept_once = False
                for j in range(i + 1, len(candles)):
                    c = candles[j]
                    bar_close_ts = c["open_ts"] + tf_seconds
                    if bar_close_ts <= s["confirmed_at"]:
                        continue
                    hi, lo, close = Decimal(c["high"]), Decimal(c["low"]), Decimal(c["close"])
                    tol = max(ticks[j], TOL_ATR * atr[j]) if atr[j] is not None else ticks[j]
                    if side == "HIGH":
                        broke, swept = close > level + tol, hi > level and close <= level
                    else:
                        broke, swept = close < level - tol, lo < level and close >= level
                    if broke or (swept and not swept_once):
                        ev = "BROKEN" if broke else "SWEEP"
                        payload = {**base, "event": ev,
                                   "state": "BROKEN" if broke else "SWEPT_REJECTED"}
                        if swept:
                            payload["outcome"] = "REJECTED"
                            swept_once = True
                        if store.insert_fact(con, symbol=symbol, tf=tf, kind="liquidity",
                                             market_time=c["open_ts"], confirmed_at=bar_close_ts,
                                             algo_version=LIQ_VERSION, payload=payload):
                            n_events += 1
                        if broke:
                            break

        con.commit()
        rec.n_new_facts = n_pools + n_events
        return {"symbol": symbol, "tf": tf, "pools": n_pools, "events": n_events}
