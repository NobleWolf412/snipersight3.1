"""Structure engine — HH/HL/LH/LL labels, BOS, CHoCH. algo structure-v0.1-draft.

Draft methodology (pending §30 items 3/4/5; versioned):
- Labels: each LOCAL swing vs the previous LOCAL swing of the same type:
  higher high -> HH, lower high -> LH, higher low -> HL, lower low -> LL.
- Break rule (§22): a CLOSED candle's close beyond the level of the most recent
  *confirmed* local swing by tolerance max(1 tick, 0.05*ATR). Wicks never break.
- Causality: a swing level is only breakable from its confirmed_at onward —
  the engine walks bars in time order and admits swings as they confirm.
- BOS = break in the direction of the current structural direction (or from
  NEUTRAL); CHoCH = break against it. After a break, that side's level is
  consumed: no re-break until a NEW local swing (formed after the break bar)
  confirms on that side.
"""
import json
from decimal import Decimal

from . import store
from .swings import compute_atr, SWING_VERSION, quote_ticks
from .runlog import RunRecorder

STRUCTURE_VERSION = "structure-v0.11-draft"
# v0.11: cascade from swing-v0.9, which stopped re-emitting every promoted pivot
# each cycle (held_candles accrued inside the hashed payload) and moved a
# promotion's confirmed_at to when its held window closes. Labels and breaks key
# off those pivots, so both the pivot set and its knowability times change.
# v0.9: the break tolerance was max(TICK, 0.05*ATR) with TICK hard-coded to
# 0.01 — right for BTC-USD, catastrophically wrong below a dollar, where a
# tolerance wider than any move the instrument makes means NO close ever breaks
# ANY level. This engine is where that went blind, and the store showed it
# plainly: u1000SHIBUSDT had 1 break against 127 labels, SHIB-USD 0 against 101,
# PUMP-USD 0 against 145. Because `regime._classify` returns RANGE when
# `last_break is None`, those symbols sat in a permanent false RANGE and
# dominated the "27% of rejections are ranging markets" bucket. It was never a
# ranging market; it was a blind structure engine.
#
# The tick is now derived per bar from the exponent of the venue's own price
# strings. `swings.quote_ticks` is the SINGLE definition of it and carries the
# measurement — deliberately not restated here, in zones.py or in liquidity.py,
# because four copies of a figure measured against a growing store is four
# things to drift. Same rule, implemented honestly: it returns exactly 0.01
# wherever 0.01 was right, so the majors are untouched (BTCUSDT 47 breaks
# before and after, ETHUSDT 52) while u1000SHIBUSDT goes 1 -> 52.

TOL_ATR = Decimal("0.05")

# v0.2 (user golden data 2026-07-21): BOS/CHoCH key off high-tier swings only —
# "only ~7-10 macro swing points truly matter; everything else is LTF noise."
# MAJOR on 1D/1W; INTERMEDIATE on intraday TFs. A/B RESULT (see BUILDLOG S3):
# v0.3 tried 1D=INTERMEDIATE -> 28 breaks vs golden 7, worse matches. v0.2 won
# (4/7 golden breaks, 10 total). v0.3 facts remain in store as the A/B loser.
# v0.10: 1W drops to INTERMEDIATE. The golden-data A/B that chose MAJOR tested
# 1D and grouped 1W in with it without separate evidence, and 1W cannot support
# the tier: MAJOR is a DOUBLE recursion (local -> intermediate -> major) and the
# perp book holds 194 weekly bars, which yields 14 MAJOR pivots across 11
# symbols — one or two each, never an alternating sequence. So 1W structure
# existed for 1 perp symbol of 21, 1W regime for 1, and therefore the ENTIRE 1D
# book had no higher-timeframe regime at all.
#
# That is not a cosmetic gap. `htf_regime_aligned` is the only confluence factor
# ever measured above the noise floor (r=+0.261 against a +/-0.130 floor), and it
# was unmeasurable on 1D — the timeframe carrying the book. Setups there were
# additionally docked for the missing value until S39 made UNKNOWN its own state.
# At INTERMEDIATE, 18 of 21 perps have enough pivots to form a sequence.
# 1D stays MAJOR: that one WAS tested (v0.3 tried INTERMEDIATE -> 28 breaks
# against golden 7, and lost).
TIER_BY_TF = {"1W": "INTERMEDIATE", "1D": "MAJOR",
              "4H": "INTERMEDIATE", "1H": "INTERMEDIATE", "15m": "INTERMEDIATE"}


def _tier_swings(con, symbol, tf):
    tier = TIER_BY_TF[tf]
    # One pivot per market_time, LATEST promotion row winning (get_facts orders
    # by market_time, confirmed_at, id). swing-v0.9 payloads are deterministic,
    # but a pivot near the sequence tail can still be legitimately revised —
    # margin, even tier — when a more extreme same-type swing replaces its right
    # neighbour; 63 such revision groups measured in the v0.8 store. Collapse
    # across BOTH promotion tiers before filtering, so a demoted pivot's stale
    # higher-tier row cannot survive; the label walk below is sequence-sensitive
    # and must never see the same pivot twice.
    latest = {}
    for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
        p = json.loads(r["payload"])
        if p["tier"] in ("INTERMEDIATE", "MAJOR"):
            latest[r["market_time"]] = (r, p)
    return [{"market_time": r["market_time"], "confirmed_at": r["confirmed_at"],
             "type": p["type"], "price": Decimal(p["price"])}
            for r, p in latest.values() if p["tier"] == tier]


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "structure", STRUCTURE_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        swings = _tier_swings(con, symbol, tf)
        rec.n_inputs = len(swings)
        if not swings or len(candles) < 20:
            return {"symbol": symbol, "tf": tf, "labels": 0, "breaks": 0}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)

        # --- labels ---
        n_labels = 0
        prev = {"HIGH": None, "LOW": None}
        labels = {}  # market_time -> label
        for s in sorted(swings, key=lambda x: x["market_time"]):
            if prev[s["type"]] is not None:
                if s["type"] == "HIGH":
                    lab = "HH" if s["price"] > prev["HIGH"]["price"] else "LH"
                else:
                    lab = "HL" if s["price"] > prev["LOW"]["price"] else "LL"
                labels[s["market_time"]] = lab
                if store.insert_fact(
                        con, symbol=symbol, tf=tf, kind="structure",
                        market_time=s["market_time"], confirmed_at=s["confirmed_at"],
                        algo_version=STRUCTURE_VERSION,
                        payload={"event": "LABEL", "label": lab, "type": s["type"],
                                 "price": str(s["price"])}):
                    n_labels += 1
            prev[s["type"]] = s

        # --- breaks: walk bars, admit swings as they confirm ---
        n_breaks = 0
        by_conf = sorted(swings, key=lambda x: (x["confirmed_at"], x["market_time"]))
        si = 0
        active = {"HIGH": None, "LOW": None}   # breakable level per side
        min_ts = {"HIGH": 0, "LOW": 0}         # consumed-until guard
        direction = "NEUTRAL"
        for i, c in enumerate(candles):
            bar_close_ts = c["open_ts"] + tf_seconds
            while si < len(by_conf) and by_conf[si]["confirmed_at"] <= bar_close_ts:
                s = by_conf[si]
                if s["market_time"] >= min_ts[s["type"]]:
                    cur = active[s["type"]]
                    if cur is None or s["market_time"] > cur["market_time"]:
                        active[s["type"]] = s
                si += 1
            if atr[i] is None:
                continue
            tol = max(ticks[i], (TOL_ATR * atr[i]))
            close = Decimal(c["close"])
            for side, cmp_up in (("HIGH", True), ("LOW", False)):
                lvl = active[side]
                if lvl is None or lvl["confirmed_at"] > bar_close_ts:
                    continue
                broken = (close > lvl["price"] + tol) if cmp_up else (close < lvl["price"] - tol)
                if not broken:
                    continue
                new_dir = "BULL" if cmp_up else "BEAR"
                event = "BOS" if direction in (new_dir, "NEUTRAL") else "CHOCH"
                direction = new_dir
                payload = {"event": event, "direction": new_dir,
                           "level": str(lvl["price"]), "level_swing_ts": lvl["market_time"],
                           "level_label": labels.get(lvl["market_time"]),
                           "close": str(close), "tolerance": str(tol)}
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="structure",
                                     market_time=c["open_ts"], confirmed_at=bar_close_ts,
                                     algo_version=STRUCTURE_VERSION, payload=payload):
                    n_breaks += 1
                active[side] = None
                min_ts[side] = c["open_ts"] + 1  # only swings formed after the break re-arm

        con.commit()
        rec.n_new_facts = n_labels + n_breaks
        return {"symbol": symbol, "tf": tf, "labels": n_labels, "breaks": n_breaks}
