"""Swing engine — micro and local swings per spec §20, algo swing-v0.1-draft.

Draft methodology (pending §30 ratification; every choice below is versioned):
- MICRO swing: 5-candle fractal — bar i is a swing high when high[i] is STRICTLY
  greater than the highs of i-2, i-1, i+1, i+2 (ties produce no swing; P-SW-TIE
  draft rule). Mirrored for lows. confirmed_at = close time of bar i+2 (§5:
  a swing needing right-side candles is unknowable until they close).
- LOCAL swing: a confirmed micro swing whose reversal to the NEXT opposite-type
  micro swing is >= 0.75 * ATR14 measured at the swing bar. confirmed_at = the
  opposite swing's confirmed_at (the reversal magnitude is unknowable earlier).
- ATR14: Wilder. TR from bar 1; ATR[14] = SMA(TR 1..14); then
  ATR[i] = (ATR[i-1]*13 + TR[i]) / 14, Decimal, quantized to 8 dp.
All arithmetic is Decimal; facts are append-only and idempotent on re-run.
"""
from decimal import Decimal

from . import store
from .runlog import RunRecorder

SWING_VERSION = "swing-v0.10-draft"
# v0.10: input cascade from agg-v0.2 — the 4H/1W series now include
# acknowledged-partial buckets (thin markets regain windows v0.1 discarded;
# BICO-USD 4H alone regains ~621), so pivots over those series differ with no
# rule change here. Full-series recompute means new facts would have appended
# beside the sparse-series generation under one label — the S53 defect — so
# every fact-level reader moves too; see tests/test_version_cascade.py.
# v0.9: the promotion payload is now a pure function of the candles. v0.8 embedded
# `evidence.held_candles` — which accrues per BAR — inside a content-hashed,
# append-only fact, so every scan cycle re-appended every promoted pivot with the
# integer bumped: 193,718 promotion rows for 15,603 pivots, one AAVEUSDT 4H pivot
# 11 times (held 987..997), and zones/liquidity counting the copies as distinct
# neighbours. held_candles is now CENSORED at HELD_FULL (90) — the cap the score
# card already applied — and the fact is emitted only once that window has
# CLOSED: price traded beyond the extreme, or 90 bars elapsed. confirmed_at =
# when that became knowable (§5). Score-identical for every settled pivot, so
# the golden calibration stands. The alternative — freezing held at geometric
# confirmation — was measured and rejected: it is v0.4's held-as-confirmation-lag
# dud again (45% of pivots change tier; 2,687 of 4,016 majors demote; the golden
# BTC-1D set loses 2 of 20). Honest cost of this rule: a promotion is knowable a
# median ~65 bars later than v0.8 pretended, and 440 frontier pivots (2.8%)
# defer until their window closes.
# v0.7: launched-impact window for dominant pivots runs to the next same-type
# DOMINANT pivot (v0.6 cut it at the next intermediate pivot — the 126k cycle
# top got zero credit for the bear CHoCH it caused and scored 54.22 vs 55).
# v0.6: (a) dominant swings score at the scale they dominate — major-recursion
# survivors use major-scale margin/reversal (v0.5 scored everything at
# intermediate scale; the Nov'22 bottom showed margin 0.34% and fell out).
# (b) impact = LAUNCHED + BROKEN: breaks in the away-direction before the next
# same-type pivot (what the swing caused) plus breaks of the swing's own level
# (how it mattered as a level). v0.5's broken-only impact scored trend origins
# zero — exactly backwards, per user's Nov'22 example.
LOCAL_ATR_MULT = Decimal("0.75")
ATR_PERIOD = 14
Q8 = Decimal("0.00000001")
Q2 = Decimal("0.01")

# v0.4 (user feedback answer.docx, 2026-07-21): composite Major Score decides
# tiers instead of pure geometry. Weights per user: ATR reversal heaviest,
# volume log-scaled, margin capped, plus structure impact (breaks this swing's
# level caused) and liquidity harvested (took prior extreme / equal-cluster).
# Verdicts encoded: 2025-05-22 112k demotes; 2024-03-14 ATH keeps (impact).
# Component caps (points):
W_MARGIN, MARGIN_FULL = Decimal(18), Decimal("0.05")      # 5% margin = full
W_ATR, ATR_FULL = Decimal(24), Decimal(15)                # 15 ATR = full
W_HELD, HELD_FULL = Decimal(14), Decimal(90)              # 90 candles = full
W_VOL, VOL_FULL = Decimal(12), Decimal(6)                 # log2-scaled to 6x
W_LIQ = Decimal(8)                                        # took_prev + cluster
W_IMPACT, IMPACT_FULL = Decimal(26), Decimal(2)           # 2 breaks = full
W_DOM = Decimal(12)                                       # survived 2nd recursion
MAJOR_MIN, INTER_MIN = Decimal(55), Decimal(30)
# v0.5: held_candles redefined — candles until price first traded beyond the
# swing extreme (as-of-now evidence, accrues like impact; CAV-3). v0.4's
# held-as-confirmation-lag made 65+ unreachable (0 majors) — recorded dud.
# Impact/liquidity evidence is read from the PRIOR engine generation (bootstrap;
# CAV-3: fixed-point iteration between swing rank and structure deferred).
PRIOR_STRUCTURE = "structure-v0.2-draft"
PRIOR_LIQ = "liq-v0.2-draft"

# v0.2: tier hierarchy above LOCAL via swings-of-swings recursion, calibrated
# against user golden data (verification/golden-btc-1d.json, 2026-07-21).
# INTERMEDIATE = a local swing more extreme than the adjacent same-type local
# swings in the alternating pivot sequence; MAJOR = same rule applied to the
# INTERMEDIATE sequence. Self-scaling per timeframe, no extra parameters.
# v0.3 (user feedback 2026-07-21): every promoted swing carries a promotion-
# evidence block (neighbor margins, reversal displacement, hold duration,
# relative volume). Evidence is RECORDED, not filtered on — §22 discipline:
# evidence becomes a required filter only after the user grades it.


def compute_atr(candles: list) -> list:
    """ATR14 per bar index; None until enough history exists."""
    atr: list = [None] * len(candles)
    if len(candles) < ATR_PERIOD + 1:
        return atr
    trs: list = [None]
    for i in range(1, len(candles)):
        h, l = Decimal(candles[i]["high"]), Decimal(candles[i]["low"])
        pc = Decimal(candles[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = (sum(trs[1:ATR_PERIOD + 1]) / ATR_PERIOD).quantize(Q8)
    atr[ATR_PERIOD] = a
    for i in range(ATR_PERIOD + 1, len(candles)):
        a = ((a * (ATR_PERIOD - 1) + trs[i]) / ATR_PERIOD).quantize(Q8)
        atr[i] = a
    return atr



def quote_ticks(candles: list) -> list:
    """Per-bar minimum price increment, read off the venue's own quoting.

    "1 tick" in structure.py, zones.py and liquidity.py is the literal
    constant 0.01. That is the correct tick for BTC-USD and it is
    catastrophically wrong for a sub-dollar instrument. Measured across the 59
    tracked symbols: on 34 of them 0.05*ATR is SMALLER than 0.01 — by 859x on
    u1000SHIBUSDT and by 944,882x on SHIB-USD. A "tolerance" larger than any
    move the instrument makes means no close ever breaks any level, and the
    store shows exactly that: structure.py has emitted ONE break in
    u1000SHIBUSDT's entire history against 127 labels, and ZERO in SHIB-USD's
    against 101. `regime._classify` returns RANGE when there is no break, so
    those symbols are permanently labelled RANGE — and 89% of the RANGE
    rejections this engine was built for belong to those 34 symbols (498 of
    554 at the snapshot that motivated it, 898 of 1,010 now). Most of that
    "27% of the market is ranging" is not a ranging market. It is a blind
    structure engine, and the fix belongs in the shared constant rather than
    here.

    So this is not a new rule; it is the SAME convention implemented honestly.
    The tick is the smallest increment the venue quotes, taken from the
    exponent of the price strings it sent. For every symbol where 0.01 was
    right it returns 0.01.

    It is a RUNNING maximum over bars 0..j, which matters twice: the tick a
    fact was computed with depends only on that fact's past (§5), and
    appending a bar quoted to more decimals can never change an already
    emitted fact, so re-runs stay idempotent.
    """
    out, seen = [], 0
    for c in candles:
        for field in ("open", "high", "low", "close"):
            exp = Decimal(c[field]).as_tuple().exponent
            if isinstance(exp, int) and -exp > seen:
                seen = -exp
        # No fractional digits observed yet -> the tick is UNKNOWN, and an
        # unknown tick returns ZERO rather than 1. `max(tick, 0.05*ATR)` exists
        # so a tolerance is never finer than one tick; a guessed-large tick
        # would inflate the tolerance and reproduce, at a different scale, the
        # exact bug this function fixes. Zero simply lets the ATR term govern,
        # which is the conservative direction (more breaks, not fewer).
        # No real venue row in the store is integer-quoted; this is reachable
        # from synthetic data and must not be a landmine when it is.
        out.append(Decimal("0." + "0" * (seen - 1) + "1") if seen else Decimal(0))
    return out


def detect_micro(candles: list) -> list[dict]:
    """Strict 2-left/2-right fractal swings, in bar order."""
    out = []
    for i in range(2, len(candles) - 2):
        hi = Decimal(candles[i]["high"])
        lo = Decimal(candles[i]["low"])
        neighbors = [candles[j] for j in (i - 2, i - 1, i + 1, i + 2)]
        if all(hi > Decimal(n["high"]) for n in neighbors):
            out.append({"i": i, "type": "HIGH", "price": str(hi)})
        if all(lo < Decimal(n["low"]) for n in neighbors):
            out.append({"i": i, "type": "LOW", "price": str(lo)})
    return out


def alternate(swings: list[dict]) -> list[dict]:
    """Collapse to a strictly alternating HIGH/LOW pivot sequence, keeping the
    more extreme pivot when the same type repeats. Confirmation of a kept pivot
    is inherited conservatively (latest confirmed_at seen in its replacement
    chain) so downstream tiers never confirm before their inputs."""
    seq: list[dict] = []
    for s in sorted(swings, key=lambda x: x["market_time"]):
        if not seq or seq[-1]["type"] != s["type"]:
            seq.append(dict(s))
            continue
        prev = seq[-1]
        better = (Decimal(s["price"]) > Decimal(prev["price"])) if s["type"] == "HIGH" \
            else (Decimal(s["price"]) < Decimal(prev["price"]))
        if better:
            s = dict(s)
            s["confirmed_at"] = max(s["confirmed_at"], prev["confirmed_at"])
            seq[-1] = s
        else:
            prev["confirmed_at"] = max(prev["confirmed_at"], s["confirmed_at"])
    return seq


def promote_tier(seq: list[dict]) -> list[dict]:
    """A pivot survives if it is more extreme than the adjacent same-type
    pivots (k-2, k+2 in the alternating sequence). confirmed_at = when the
    right-side comparison became knowable. Carries neighbor/opposite context
    forward for the promotion-evidence block."""
    out = []
    for k in range(2, len(seq) - 2):
        s, left, right = seq[k], seq[k - 2], seq[k + 2]
        p, lp, rp = Decimal(s["price"]), Decimal(left["price"]), Decimal(right["price"])
        keep = (p > lp and p > rp) if s["type"] == "HIGH" else (p < lp and p < rp)
        if keep:
            s = dict(s)
            s["confirmed_at"] = max(s["confirmed_at"], seq[k + 1]["confirmed_at"],
                                    right["confirmed_at"])
            if s["type"] == "HIGH":
                margin = min((p - lp) / lp, (p - rp) / rp)
            else:
                margin = min((lp - p) / lp, (rp - p) / rp)
            s["_left"], s["_right"] = str(lp), str(rp)
            s["_margin_pct"] = str((margin * 100).quantize(Q2))
            s["_next_opp"] = seq[k + 1]["price"]
            out.append(s)
    return out


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "swing", SWING_VERSION, symbol, tf) as rec:
        return _run(con, rec, symbol, tf, tf_seconds)


def _run(con, rec, symbol: str, tf: str, tf_seconds: int) -> dict:
    candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
    rec.n_inputs = len(candles)
    if len(candles) < 5:
        return {"symbol": symbol, "tf": tf, "micro": 0, "local": 0}

    atr = compute_atr(candles)
    swings = detect_micro(candles)
    n_micro = n_local = 0

    for s in swings:
        i = s["i"]
        bar_ts = candles[i]["open_ts"]
        confirmed = candles[i + 2]["open_ts"] + tf_seconds
        payload = {"type": s["type"], "tier": "MICRO", "price": s["price"],
                   "bar_open_ts": bar_ts,
                   "atr": str(atr[i]) if atr[i] is not None else None}
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="swing",
                             market_time=bar_ts, confirmed_at=confirmed,
                             algo_version=SWING_VERSION, payload=payload):
            n_micro += 1

    # LOCAL promotion: reversal to the next opposite-type micro swing
    for idx, s in enumerate(swings):
        # ATR quantizes to ZERO on low-tick coins in dead hours: a one-tick
        # true range on an 8dp quote Wilder-averages to ~1e-8/14 = 7e-10,
        # which Q8 rounds to 0E-8 — so the bar is not flat, but its ATR is.
        # Unguarded, `reversal / atr` below raised decimal.DivisionByZero on
        # 1,151 recorded runs (PF_PEPEUSD 5m alone 1,041, PF_SHIBUSD 5m 110),
        # leaving both series with no swing facts past each crash point. Zero
        # joins None as "no usable ATR measurement" — same guard, same reason,
        # as ma.py's ribbon distances.
        if not atr[s["i"]]:
            continue
        opp = next((t for t in swings[idx + 1:] if t["type"] != s["type"]), None)
        if opp is None:
            continue
        reversal = abs(Decimal(s["price"]) - Decimal(opp["price"]))
        threshold = (LOCAL_ATR_MULT * atr[s["i"]]).quantize(Q8)
        if reversal < threshold:
            continue
        bar_ts = candles[s["i"]]["open_ts"]
        confirmed = candles[opp["i"] + 2]["open_ts"] + tf_seconds
        payload = {"type": s["type"], "tier": "LOCAL", "price": s["price"],
                   "bar_open_ts": bar_ts, "atr": str(atr[s["i"]]),
                   "reversal": str(reversal),
                   "reversal_atr_mult": str((reversal / atr[s["i"]]).quantize(Q8)),
                   "opp_bar_open_ts": candles[opp["i"]]["open_ts"]}
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="swing",
                             market_time=bar_ts, confirmed_at=confirmed,
                             algo_version=SWING_VERSION, payload=payload):
            n_local += 1

    # --- v0.2 tier recursion: LOCAL -> INTERMEDIATE -> MAJOR ---
    locals_ = []
    for idx, s in enumerate(swings):
        opp = next((t for t in swings[idx + 1:] if t["type"] != s["type"]), None)
        if not atr[s["i"]] or opp is None:
            continue
        if abs(Decimal(s["price"]) - Decimal(opp["price"])) < (LOCAL_ATR_MULT * atr[s["i"]]).quantize(Q8):
            continue
        locals_.append({"type": s["type"], "price": s["price"], "i": s["i"],
                        "market_time": candles[s["i"]]["open_ts"],
                        "confirmed_at": candles[opp["i"] + 2]["open_ts"] + tf_seconds})

    def evidence(s):
        """Promotion evidence — §8 explainability. v0.9: measured over a CLOSED
        window so the payload is deterministic. held_candles = bars until price
        first traded beyond the extreme, censored at HELD_FULL — beyond the cap
        it never moved the score, it only churned the hash. Returns (None, None)
        while the window is still open: the tier is unknowable until then (§5).
        Impact/liquidity evidence reads a frozen bootstrap corpus (PRIOR_*), so
        it does not accrue between runs. Second return value is the bar index
        that closed the window, for confirmed_at."""
        i = s["i"]
        p = Decimal(s["price"])
        held = close_bar = None
        for j in range(i + 1, min(i + int(HELD_FULL), len(candles) - 1) + 1):
            beyond = Decimal(candles[j]["high"]) > p if s["type"] == "HIGH" \
                else Decimal(candles[j]["low"]) < p
            if beyond:
                held, close_bar = j - i, j
                break
        if held is None:
            if len(candles) - 1 - i < int(HELD_FULL):
                return None, None
            held, close_bar = int(HELD_FULL), i + int(HELD_FULL)
        ev = {"vs_left_neighbor": s["_left"], "vs_right_neighbor": s["_right"],
              "margin_pct": s["_margin_pct"],
              "held_candles": held}
        if atr[i]:
            rev = abs(Decimal(s["price"]) - Decimal(s["_next_opp"]))
            ev["reversal_atr"] = str((rev / atr[i]).quantize(Q2))
        if i >= 20:
            avg_vol = sum(Decimal(candles[j]["volume"]) for j in range(i - 20, i)) / 20
            if avg_vol > 0:
                ev["vol_ratio"] = str((Decimal(candles[i]["volume"]) / avg_vol).quantize(Q2))
        return ev, close_bar

    inter = promote_tier(alternate(locals_))
    major_items = {s["market_time"]: s for s in promote_tier(alternate(inter))}

    # impact + liquidity evidence from prior generation (bootstrap, CAV-3)
    import json as _json
    breaks_at, pool_ts, break_events = {}, set(), []
    for r in store.get_facts(con, symbol, tf, "structure", PRIOR_STRUCTURE):
        p = _json.loads(r["payload"])
        if p["event"] in ("BOS", "CHOCH"):
            breaks_at[p["level_swing_ts"]] = breaks_at.get(p["level_swing_ts"], 0) + 1
            break_events.append({"market_time": r["market_time"],
                                 "direction": p["direction"]})
    for r in store.get_facts(con, symbol, tf, "liquidity", PRIOR_LIQ):
        p = _json.loads(r["payload"])
        if p["event"] == "POOL":
            pool_ts.update(p["member_ts"])

    def launched(s, next_same_ts):
        """Breaks in the away-direction between this pivot and the next
        same-type pivot — the structural consequence the swing caused."""
        away = "BULL" if s["type"] == "LOW" else "BEAR"
        hi = next_same_ts if next_same_ts is not None else 2**53
        return sum(1 for b in break_events
                   if b["direction"] == away and s["market_time"] < b["market_time"] < hi)

    def pts(x, full, w):
        return (min(x / full, Decimal(1)) * w).quantize(Q2)

    n_tiers = {"INTERMEDIATE": 0, "MAJOR": 0}
    prev_same: dict = {}
    for k, s in enumerate(inter):
        # dominant swings are scored at the scale they dominate
        scored = major_items.get(s["market_time"], s)
        ev, held_close_bar = evidence(scored)
        if ev is None:
            # held window still open — the score, and therefore the tier, is
            # unknowable yet (§5). The pivot is emitted on a later run, once,
            # rather than re-emitted every cycle as the evidence drifts.
            continue
        took_prev = False
        if s["type"] in prev_same:
            pp = Decimal(prev_same[s["type"]])
            took_prev = Decimal(s["price"]) > pp if s["type"] == "HIGH" else Decimal(s["price"]) < pp
        prev_same[s["type"]] = s["price"]
        in_cluster = s["market_time"] in pool_ts
        if s["market_time"] in major_items:
            next_same = next((t for t in sorted(major_items) if t > s["market_time"]
                              and major_items[t]["type"] == s["type"]), None)
        else:
            next_same = next((t["market_time"] for t in inter[k + 1:]
                              if t["type"] == s["type"]), None)
        impact = breaks_at.get(s["market_time"], 0) + launched(s, next_same)

        # log-scaled volume (user: capitulation volume >> linear weighting)
        vol = Decimal(ev.get("vol_ratio", "1"))
        # Decimal-native log2 keeps the score reproducible across runtimes.
        log2_vol = (vol + 1).ln() / Decimal(2).ln()
        log2_full = (VOL_FULL + 1).ln() / Decimal(2).ln()
        vol_pts = pts(log2_vol, log2_full, W_VOL)
        score_parts = {
            "margin": pts(Decimal(ev["margin_pct"]) / 100, MARGIN_FULL, W_MARGIN),
            "reversal": pts(Decimal(ev.get("reversal_atr", "0")), ATR_FULL, W_ATR),
            "held": pts(Decimal(ev["held_candles"]), HELD_FULL, W_HELD),
            "volume": vol_pts,
            "liquidity": (W_LIQ * (int(took_prev) + int(in_cluster)) / 2).quantize(Q2),
            "impact": pts(Decimal(impact), IMPACT_FULL, W_IMPACT),
            "dominance": W_DOM if s["market_time"] in major_items else Decimal(0),
        }
        score = sum(score_parts.values())
        tier = "MAJOR" if score >= MAJOR_MIN else \
               "INTERMEDIATE" if score >= INTER_MIN else None
        if tier is None:
            continue
        ev.update({"took_prev_extreme": took_prev, "equal_cluster": in_cluster,
                   "breaks_caused": impact,
                   "score": str(score), "score_parts": {k: str(v) for k, v in score_parts.items()}})
        payload = {"type": s["type"], "tier": tier, "price": s["price"],
                   "bar_open_ts": s["market_time"],
                   "promoted_from": "LOCAL", "evidence": ev}
        # Knowable when BOTH the sequence geometry and the held window are
        # closed — whichever came later.
        confirmed = max(s["confirmed_at"],
                        candles[held_close_bar]["open_ts"] + tf_seconds)
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="swing",
                             market_time=s["market_time"],
                             confirmed_at=confirmed,
                             algo_version=SWING_VERSION, payload=payload):
            n_tiers[tier] += 1

    con.commit()
    rec.n_new_facts = n_micro + n_local + n_tiers["INTERMEDIATE"] + n_tiers["MAJOR"]
    return {"symbol": symbol, "tf": tf, "micro": n_micro, "local": n_local,
            "inter": n_tiers["INTERMEDIATE"], "major": n_tiers["MAJOR"]}
