"""Nested Cycle Satellite — Bob Loukas / Camel Finance school. OBSERVATIONAL ONLY.

Litmus test: deleting this module must not change a single trade. No strategy,
exec, or risk engine may import from it or read `cycle` facts — promotion to an
enforced input would be a separate, validated setup-version step (NOT built).

Mechanical (exact): fractal swing-low detection, band arithmetic, translation
fractions, calendar-month window math.
Heuristic (labeled, not fitted): band widths (54-66d daily, 150-200d weekly,
44-52mo four-year), translation thresholds (40%/60%), the push-out rule
(right-translated weekly cycle extends the 4Y-low window end by one daily
cycle) — an n~=2 observation from the cycle-trading community, not a forecast.

Data honesty: our candle store starts 2022-01; the 2015/2018 four-year lows
are accepted constants from the cycle-trading literature, not detections.
The fractal here deliberately REIMPLEMENTS the 2-bar convention rather than
importing the swing engine — the one-way boundary matters more than DRY.
"""
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from . import store
from .runlog import RunRecorder

CYCLES_VERSION = "cycles-v0.2-draft"
# v0.2: the engine was DEAD. `run()` early-returned unless `symbol == "BTC-USD"`,
# and BTC-USD left the scan set when the universe moved to perps — so the engine
# no-opped for every symbol on every cycle. Measured 2026-07-30: BTC-USD carried
# 1,670 daily candles ending 2026-07-28 (stale, no longer imported) while the
# two tracked BTC series, PF_XBTUSD and BTCUSDT, were current and ignored. The
# newest cycle fact was 2026-06-08.
#
# The cycle model is about BITCOIN, not about one venue's ticker. Hardcoding a
# spelling made an asset-level model depend on a venue listing — the same class
# of error as the Coinbase-hardcoded price fetch (S37) and `TICK = 0.01` (S40).

# Known spellings of the same asset. Order is NOT preference — `btc_series`
# picks by history depth among the ones actually being kept current.
BTC_ALIASES = ("BTC-USD", "BTCUSDT", "PF_XBTUSD", "XBTUSD", "BTC-USDT")
BTC = "BTC-USD"          # legacy default, retained for callers that pass no con


def btc_series(con, *, require_current: bool = True) -> str | None:
    """Which stored series to read Bitcoin's cycle from.

    Deepest daily history wins, because the model anchors on a 2022 four-year
    low and a series that starts after it cannot see the count. But depth only
    counts if the series is still being IMPORTED: BTC-USD is the deepest in this
    store and has been frozen since it left the universe, so preferring it would
    have kept the engine looking at a dead file forever — a subtler version of
    the bug this function exists to fix.

    Returns None when no BTC series is tracked at all, so the caller can say so
    rather than silently emitting nothing (loud-fallback rule).
    """
    from . import universe
    live = set(universe.scan_symbols(con)) if require_current else None
    best, best_n = None, 0
    for sym in BTC_ALIASES:
        if live is not None and sym not in live:
            continue
        n = con.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND tf='1D'",
                        (sym,)).fetchone()[0]
        if n > best_n:
            best, best_n = sym, n
    if best is None and require_current:
        # Nothing current — fall back to the deepest stored series and let the
        # caller see that it is not live.
        return btc_series(con, require_current=False)
    return best

# --- heuristic constants (round numbers, community convention, not fitted) ---
FRACTAL_W = 2                       # bars each side (mirrors swing-engine convention)
DCL_BAND_DAYS = (54, 66)            # ~60d daily cycle
WCL_BAND_DAYS = (150, 200)          # ~24w weekly cycle (~3 daily cycles)
TRANSLATION_LEFT = 0.40
TRANSLATION_RIGHT = 0.60
PUSHOUT_DAYS = 60                   # +1 daily cycle
FY_LOW_TO_LOW_MONTHS = (44, 52)
HALVING_LOW_OFFSET_MONTHS = (18, 12)   # 4Y low ~12-18mo BEFORE the next halving

# accepted history (constants, not detections — see module docstring)
FOUR_YEAR_LOWS = ("2015-01-14", "2018-12-15", "2022-11-21")
HALVINGS = ("2012-11-28", "2016-07-09", "2020-05-11", "2024-04-19")
NEXT_HALVING_EST = "2028-04-15"     # ESTIMATED (~210k blocks); not block-derived
SEED_LOW = "2022-11-21"             # confirmed 4Y low; anchors DCL/WCL counts

DAY = 86400
NOTE = ("observational satellite — swing/band detection is mechanical; band "
        "widths, translation thresholds and the push-out rule are community "
        "heuristics (n~=2-3 four-year samples). Never consumed by any trading "
        "engine. 2015/2018 lows are accepted constants, not detections.")


def _ts(datestr: str) -> int:
    return int(datetime.strptime(datestr, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp())


def add_months(d: date, months: int) -> date:
    y, m = d.year + (d.month - 1 + months) // 12, (d.month - 1 + months) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


def fractal_lows(candles: list, w: int = FRACTAL_W) -> list[int]:
    """Indices whose low is strictly the lowest of +/-w neighbors."""
    out = []
    for i in range(w, len(candles) - w):
        lo = Decimal(candles[i]["low"])
        if all(lo < Decimal(candles[j]["low"])
               for j in range(i - w, i + w + 1) if j != i):
            out.append(i)
    return out


def detect_lows(candles: list, seed_ts: int, band_days: tuple,
                pool_idx: list[int] | None = None) -> tuple[list[dict], list[dict]]:
    """Walk forward from the seed low, confirming one low per timing band.
    Returns (lows, inversions). A band that elapses with no qualifying low
    while price printed a local high inside it raises an inversion flag; the
    count is NOT re-anchored — the next low after the band is accepted late.
    """
    idx_by_ts = {c["open_ts"]: i for i, c in enumerate(candles)}
    lows_idx = pool_idx if pool_idx is not None else fractal_lows(candles)
    lo_set = sorted(lows_idx)
    seed_i = idx_by_ts.get(seed_ts)
    if seed_i is None:
        return [], []
    lows = [{"idx": seed_i, "ts": candles[seed_i]["open_ts"],
             "price": candles[seed_i]["low"], "late": False, "seed": True}]
    inversions = []
    last_ts = seed_ts
    end_of_data = candles[-1]["open_ts"]
    while True:
        b0, b1 = last_ts + band_days[0] * DAY, last_ts + band_days[1] * DAY
        in_band = [i for i in lo_set if b0 <= candles[i]["open_ts"] <= b1
                   and candles[i]["open_ts"] > last_ts]
        if in_band:
            pick = min(in_band, key=lambda i: (Decimal(candles[i]["low"]),
                                               candles[i]["open_ts"]))
            lows.append({"idx": pick, "ts": candles[pick]["open_ts"],
                         "price": candles[pick]["low"], "late": False, "seed": False})
            last_ts = candles[pick]["open_ts"]
            continue
        if b1 + FRACTAL_W * DAY > end_of_data:
            break                                   # band still open — cycle in progress
        inversions.append({"band_start": b0, "band_end": b1,
                           "after_low_ts": last_ts})
        late = [i for i in lo_set if candles[i]["open_ts"] > b1]
        if not late:
            break
        pick = late[0]
        lows.append({"idx": pick, "ts": candles[pick]["open_ts"],
                     "price": candles[pick]["low"], "late": True, "seed": False})
        last_ts = candles[pick]["open_ts"]
    return lows, inversions


def classify_cycles(candles: list, lows: list[dict]) -> list[dict]:
    """Completed cycles between consecutive lows: top, translation, failed flag."""
    cycles = []
    prev_top_price = None
    for k in range(len(lows) - 1):
        i0, i1 = lows[k]["idx"], lows[k + 1]["idx"]
        if i1 <= i0 + 1:
            continue
        top_i = max(range(i0, i1 + 1), key=lambda i: Decimal(candles[i]["high"]))
        frac = (top_i - i0) / (i1 - i0)
        label = ("left" if frac < TRANSLATION_LEFT else
                 "right" if frac > TRANSLATION_RIGHT else "mid")
        failed = False
        if prev_top_price is not None:
            start_low = Decimal(lows[k]["price"])
            first_break_down = first_break_up = None
            for i in range(i0 + 1, i1 + 1):
                if first_break_down is None and Decimal(candles[i]["close"]) < start_low:
                    first_break_down = i
                if first_break_up is None and Decimal(candles[i]["high"]) > prev_top_price:
                    first_break_up = i
            failed = (first_break_down is not None and
                      (first_break_up is None or first_break_down < first_break_up))
        cycles.append({"start_ts": lows[k]["ts"], "end_ts": lows[k + 1]["ts"],
                       "top_ts": candles[top_i]["open_ts"],
                       "top_price": candles[top_i]["high"],
                       "fraction": round(frac, 3), "translation": label,
                       "failed": failed, "late_end": lows[k + 1]["late"]})
        prev_top_price = Decimal(candles[top_i]["high"])
    return cycles


NOMINAL_4Y_DAYS = 1461   # 48 months — midpoint of the 44-52mo band


def four_year_windows(weekly_right_translated: bool,
                      fy_top_fraction: float | None = None) -> dict:
    """Two INDEPENDENT window estimates — never merged. Disagreement is data.
    TWO push-out variants, also never merged:
    - weekly variant: the build-prompt operationalization (current weekly
      cycle right-translated).
    - 4Y-translation variant: the original 'extended translation pushes the
      low out' framing — the 4-year cycle's own top-so-far fraction > 60%.
    Both are n~=2 heuristics; both shown when active; neither is a forecast."""
    last_low = date.fromisoformat(FOUR_YEAR_LOWS[-1])
    ltl = {"start": str(add_months(last_low, FY_LOW_TO_LOW_MONTHS[0])),
           "end": str(add_months(last_low, FY_LOW_TO_LOW_MONTHS[1])),
           "basis": f"low-to-low: {FOUR_YEAR_LOWS[-1]} + {FY_LOW_TO_LOW_MONTHS} months"}
    nh = date.fromisoformat(NEXT_HALVING_EST)
    ha = {"start": str(add_months(nh, -HALVING_LOW_OFFSET_MONTHS[0])),
          "end": str(add_months(nh, -HALVING_LOW_OFFSET_MONTHS[1])),
          "basis": f"halving-anchored: est. halving {NEXT_HALVING_EST} - "
                   f"{HALVING_LOW_OFFSET_MONTHS} months (halving date ESTIMATED)"}
    ext_end = str(date.fromisoformat(ltl["end"]) + timedelta(days=PUSHOUT_DAYS))
    out = {"low_to_low": ltl, "halving_anchored": ha,
           "pushout_extended_window": None,
           "pushout_extended_window_4y": None,
           "fy_top_fraction": fy_top_fraction}
    if weekly_right_translated:
        out["pushout_extended_window"] = {
            "start": ltl["start"], "end": ext_end,
            "note": (f"push-out heuristic (n~=2), WEEKLY variant: right-translated "
                     f"weekly cycle extends low-to-low end by {PUSHOUT_DAYS}d. "
                     f"Not a forecast.")}
    if fy_top_fraction is not None and fy_top_fraction > TRANSLATION_RIGHT:
        out["pushout_extended_window_4y"] = {
            "start": ltl["start"], "end": ext_end,
            "note": (f"push-out heuristic (n~=2), 4Y-TRANSLATION variant: 4-year "
                     f"cycle top-so-far at {fy_top_fraction:.2f} of nominal length "
                     f"(right-translated) extends low-to-low end by {PUSHOUT_DAYS}d. "
                     f"Not a forecast.")}
    return out


def summarize(candles: list, now_ts: int) -> dict:
    """Pure summary for the API — computed, never stored (facts hold detections)."""
    if len(candles) < 30:
        return {"observational": True, "source": "unavailable", "note": NOTE,
                "ts": now_ts, "daily": None, "weekly": None, "windows": None}
    seed = _ts(SEED_LOW)
    dcls, d_inv = detect_lows(candles, seed, DCL_BAND_DAYS)
    dcl_idx = [l["idx"] for l in dcls]
    wcls, w_inv = detect_lows(candles, seed, WCL_BAND_DAYS, pool_idx=dcl_idx)
    d_cycles = classify_cycles(candles, dcls)
    w_cycles = classify_cycles(candles, wcls)

    def current(lows, avg_target):
        last = lows[-1]
        days = (now_ts - last["ts"]) // DAY
        seg = [c for c in candles if c["open_ts"] >= last["ts"]]
        top_i = max(range(len(seg)), key=lambda i: Decimal(seg[i]["high"])) if seg else 0
        frac = round(top_i / max(1, len(seg) - 1), 3) if len(seg) > 1 else 0.0
        return {"last_low": last["ts"], "last_low_price": str(last["price"]),
                "days_since": days, "nominal_len_days": avg_target,
                "provisional_top_fraction": frac,
                "provisional_translation": ("right" if frac > TRANSLATION_RIGHT else
                                            "left" if frac < TRANSLATION_LEFT else "mid")}

    cur_w = current(wcls, 168)
    wk_right = (w_cycles[-1]["translation"] == "right" if w_cycles
                else cur_w["provisional_translation"] == "right")
    # 4Y translation: days from last accepted 4Y low to the top-so-far,
    # over the nominal 48mo length (top-so-far — provisional by nature)
    fy_low_ts = _ts(FOUR_YEAR_LOWS[-1])
    seg = [c for c in candles if c["open_ts"] >= fy_low_ts]
    fy_frac = None
    if seg:
        top_c = max(seg, key=lambda c: Decimal(c["high"]))
        fy_frac = round(((top_c["open_ts"] - fy_low_ts) // DAY) / NOMINAL_4Y_DAYS, 3)
    return {"observational": True, "source": "coinbase-store", "note": NOTE,
            "ts": now_ts, "algo_version": CYCLES_VERSION,
            "daily": {"count_since_seed": len(dcls) - 1, "cycles": d_cycles,
                      "inversions": d_inv, "current": current(dcls, 60),
                      "primary_count": len(dcls) - 1,
                      "inverted_count": len(dcls) - 1 + len(d_inv)},
            "weekly": {"count_since_seed": len(wcls) - 1, "cycles": w_cycles,
                       "inversions": w_inv, "current": cur_w,
                       "nest": [[l["ts"] for l in dcls
                                 if w0["ts"] < l["ts"] <= w1["ts"]]
                                for w0, w1 in zip(wcls, wcls[1:])],
                       "primary_count": len(wcls) - 1,
                       "inverted_count": len(wcls) - 1 + len(w_inv)},
            "windows": four_year_windows(wk_right, fy_frac),
            "seed_low": SEED_LOW, "accepted_4y_lows": list(FOUR_YEAR_LOWS)}


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    """Emit detection facts (BTC 1D only). Summary stays computed, not stored.

    The symbol test resolves the ASSET rather than comparing to a hardcoded
    ticker — see `btc_series` and the v0.2 note for what that cost.
    """
    if tf != "1D":
        return {"symbol": symbol, "tf": tf, "facts": 0}
    if symbol != btc_series(con):
        return {"symbol": symbol, "tf": tf, "facts": 0}
    with RunRecorder(con, "cycles", CYCLES_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        if len(candles) < 30:
            return {"symbol": symbol, "tf": tf, "facts": 0}
        seed = _ts(SEED_LOW)
        dcls, d_inv = detect_lows(candles, seed, DCL_BAND_DAYS)
        wcls, w_inv = detect_lows(candles, seed, WCL_BAND_DAYS,
                                  pool_idx=[l["idx"] for l in dcls])
        n = 0
        for kind, lows, invs in (("DCL", dcls, d_inv), ("WCL", wcls, w_inv)):
            for l in lows:
                if l["seed"]:
                    continue
                conf = candles[min(l["idx"] + FRACTAL_W, len(candles) - 1)]["open_ts"] + tf_seconds
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="cycle",
                                     market_time=l["ts"], confirmed_at=conf,
                                     algo_version=CYCLES_VERSION,
                                     payload={"event": kind, "price": str(l["price"]),
                                              "late": l["late"], "observational": True,
                                              "note": NOTE[:80]}):
                    n += 1
            for iv in invs:
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="cycle",
                                     market_time=iv["band_end"], confirmed_at=iv["band_end"],
                                     algo_version=CYCLES_VERSION,
                                     payload={"event": f"{kind}_INVERSION", **iv,
                                              "observational": True, "note": NOTE[:80]}):
                    n += 1
        for kind, lows in (("DAILY", dcls), ("WEEKLY", wcls)):
            for c in classify_cycles(candles, lows):
                conf = c["end_ts"] + (FRACTAL_W + 1) * DAY
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="cycle",
                                     market_time=c["top_ts"], confirmed_at=conf,
                                     algo_version=CYCLES_VERSION,
                                     payload={"event": "CYCLE", "cycle_kind": kind, **c,
                                              "observational": True, "note": NOTE[:80]}):
                    n += 1
        con.commit()
        rec.n_new_facts = n
        return {"symbol": symbol, "tf": tf, "facts": n}
