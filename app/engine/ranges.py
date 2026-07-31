"""Range engine — horizontal ranges, their boundaries, and their lifecycle.
algo ranges-v0.1-draft.

Why this engine exists, with the measurement that motivated it: 554 of the
2,146 `NO_ELIGIBLE_PLAYBOOK` setup rejections on the live store (26%, and 27%
of the ones carrying a regime at all) were zone touches in a RANGE regime —
1,010 of 3,893 as the pipeline has re-run since. `setups.playbook()` maps
BULL/BEAR/WEAKENING/TRANSITION to a play and returns None for RANGE, so the
scanner saw the market, classified it, and had nothing to say. A fade needs a
LEVEL to fade and no engine produced one. This engine produces the level. It
does not produce a strategy: per §3 the description layer never forms an
opinion, it only says what is there.

Read `swings.quote_ticks` before drawing conclusions from that 27%. It is
largely not what it looks like.

Draft methodology (every constant below is a draft choice, versioned):

- Pivots: LOCAL swings, collapsed to a strictly alternating HIGH/LOW sequence
  with `swings.alternate`. Reusing alternate() is deliberate rather than
  convenient: the tier recursion already defines what an alternating pivot
  sequence is, and a second definition here would be a second answer to the
  same question.

  The TIER was measured, and the measurement overturned the obvious choice.
  INTERMEDIATE+ — what zones.py and liquidity.py build on, and the tier this
  engine was first written against — produced EIGHT qualifying windows in the
  entire 59-symbol store. That is not a tuning failure, it is structural:
  swings.py v0.2 defines INTERMEDIATE by a composite score built to isolate
  "the 7-10 macro swing points that truly matter", so consecutive
  INTERMEDIATE pivots are separated by large moves BY CONSTRUCTION. Across
  all 7,471 four-pivot INTERMEDIATE windows in the store: median height
  13.86 ATR, median boundary-cluster spread 6.05 ATR. No honest tolerance
  calls that a level. The identical scan over LOCAL pivots gives 110,799
  windows, median height 3.93 ATR, median spread 1.74 ATR — the scale at
  which a boundary is a boundary. A range boundary is made of the swings that
  TOUCH it, and those are local. LOCAL is also a strict superset of the higher
  tiers: swings.py emits a LOCAL fact for every pivot it later promotes, so
  choosing it discards nothing.

- FORMATION. The EARLIEST window of 4 consecutive alternating pivots (so two
  highs and two lows — the minimum that gives each boundary two supports)
  satisfying all three of:

    (a) TIGHTNESS — every high within 0.25*ATR of the highest, every low
        within 0.25*ATR of the lowest. This one predicate IS the no-trend
        test the methodology asks for: two highs making a higher high by more
        than the tolerance cannot both sit within the tolerance of their own
        maximum, and the same holds for lows, so a consistent HH/HL or LH/LL
        sequence fails here without a second rule needing to state it.
        0.25*ATR is not a new number — it is `zones.ZONE_ATR`, the width of a
        supply/demand band. Two swings are "the same level" here exactly when
        one zone would cover both.
        This is the predicate that does the work: of 110,808 candidate
        windows 96% clear the height bound and 97% clear containment, but
        only 2,555 (2.3%) are tight enough to have boundaries at all.

    (b) HEIGHT bounded, 1.0*ATR <= (top - bottom) <= 8*ATR. The floor is
        DERIVED, not chosen: it is 4x the 0.25*ATR boundary tolerance, so each
        boundary band occupies at most a quarter of the range and the two
        cannot overlap — below it, "top" and "bottom" stop naming different
        things. The ceiling is a GUARD RAIL, not a selector, and the
        measurement says so plainly: moving it from 6 ATR to 15 ATR changes
        the detected population by one range (1,534 -> 1,535), because
        tightness has already excluded everything that tall. It stays because
        a detector whose only limit is "was it contained" would eventually
        call a slow drift on a quiet symbol a range.

    (c) CONTAINMENT — no bar between the first and last forming pivot CLOSED
        beyond a boundary by more than max(1 tick, 0.05*ATR). That is
        deliberately the identical predicate that later BREAKS the range
        (structure.py §22; wicks never break). A range whose own formation
        window contains its own break is not a range, and a range that broke
        on a rule of its own would disagree with the BOS printed by the same
        candle — leaving the operator two truths to reconcile.
        "1 tick" is DERIVED from the venue's quoting rather than hardcoded to
        0.01; see `swings.quote_ticks`, which is the single definition of the
        tick shared with structure.py, zones.py and liquidity.py, and which
        documents the error that constant carries on a sub-dollar symbol and
        what it had already done to the structure and regime facts. This engine
        deliberately does not keep its own copy: two implementations of one
        convention is how they come to disagree, and the copy that lived here
        did — it returned 1 for an integer-quoted series where the shared one
        returns 0.

- CAUSALITY (§5). The range exists from the LAST forming pivot's confirmed_at,
  never the first. The window is the earliest that qualifies, never the
  longest: a maximal window can only be recognised as maximal by looking at
  the pivot that ENDED it, and that pivot is the future. Later pivots inside
  a formed range need no special handling — they show up in the forward walk
  as boundary tests, which is what they are.

  A LOCAL pivot confirms after its own bar — swings.py dates it at the next
  opposite micro swing's own confirmation — so a range can be born already
  dead, and on higher tiers it routinely would be. Rather
  than hide those bars, the forward walk replays them and stamps any event
  they produce with confirmed_at = max(bar close, range confirmed_at) — it
  happened then, it was knowable no earlier than the range itself. Every fact
  carries `confirmation_lag_bars` so a consumer can tell a level it could have
  traded from one that was already gone when it appeared.

- LIFECYCLE, append-only, one fact per transition (zones.py's shape):
  FORMED -> TESTED -> BROKEN. A test EPISODE follows zones.py exactly: price
  entering a boundary band after having been outside it, consecutive bars
  counting once, capped at 10 facts per range so one chopping market cannot
  dominate the store.

- ONE ACTIVE RANGE at a time per symbol/tf. A market is in one range or none;
  emitting a range from every shifted 4-pivot window would mint correlated
  duplicates of a single level, which is the exact failure `claimed_member_ts`
  exists to prevent in liquidity.py. A new range may only form from pivots
  that occur after the previous one broke — `min_pivot_ts`, the same
  consumed-until guard structure.py uses to re-arm a broken level.

- EVIDENCE, never a filter (§22). Touch counts per boundary, bars held, height
  in ATR, formation span and the forming pivots are recorded on every fact and
  gate nothing. A factor earns a gate from `factorstats`, after grading.

- No regime input, deliberately. A range is geometry. Ranges must be
  CONSISTENT with `regime.py` but are not scoped to RANGE regime, and coupling
  them to it would mean every regime version bump invalidates every range fact
  for a reason that has nothing to do with where the boundaries are.

WHAT v0.1 ACTUALLY DESCRIBES, so no consumer has to guess. Over the whole
store: 1,882 ranges, median height 1.98 ATR, median 6 bars held, median 1 test
episode, and only ~2% of market time spent inside one. That is a
CONSOLIDATION detector at local-pivot scale, not a months-long trading-range
detector — four CONSECUTIVE local pivots cannot span a macro box, they can
only describe a sub-box inside it. 121 ranges (6%) reach 3+ tests and 20+ bars
held, which is the population a fade would actually want; the evidence fields
are there so that judgement is the consumer's rather than this engine's.

The short life is NOT an artefact of the break tolerance, which was the
obvious suspect: loosening it 5x (0.05 -> 0.25 ATR) moves median bars held
from 6 to 7 and total covered bars by 21%. Requiring 6 pivots instead of 4
collapses the population from 1,882 to 36. Both were measured before this
version shipped.
"""
import json
from decimal import Decimal

from . import store
from .swings import SWING_VERSION, alternate, compute_atr, quote_ticks
from .runlog import RunRecorder

RANGES_VERSION = "ranges-v0.2-draft"
# v0.2: cascade from swing-v0.9. No rule change here — this engine reads LOCAL
# swings, whose payloads never carried the accruing evidence — but the input
# namespace moved, and a tag must identify the generation of its inputs.
RANGE_TIERS = ("LOCAL",)                    # superset of INTERMEDIATE+, see docstring
MIN_PIVOTS = 4                              # 2 highs + 2 lows
BOUNDARY_ATR = Decimal("0.25")              # == zones.ZONE_ATR, see docstring (a)
MIN_HEIGHT_ATR = BOUNDARY_ATR * 4           # derived, see docstring (b)
MAX_HEIGHT_ATR = Decimal(8)
TOL_ATR = Decimal("0.05")
MAX_TEST_FACTS = 10
Q2 = Decimal("0.01")


def break_tolerance(atr_value, tick: Decimal) -> Decimal:
    """The house break tolerance: max(1 tick, 0.05*ATR).

    structure.py, zones.py and liquidity.py all break a level on this and only
    this. Ranges use it for BOTH the formation containment test and the break
    event, so the question "did price close through this level" has one answer
    everywhere in the engine.
    """
    if atr_value is None:
        return tick
    return max(tick, TOL_ATR * atr_value)


def boundaries(window: list[dict]):
    """(top, bottom, n_top, n_bottom) — the EXTREME of each cluster, not its mean.

    liquidity.py sets a pool level the same way and for the same reason: a
    level placed at the average of its cluster sits inside price the cluster
    has already traded through, so breaking it would be indistinguishable from
    the noise the cluster itself contains.
    """
    highs = [p["price"] for p in window if p["type"] == "HIGH"]
    lows = [p["price"] for p in window if p["type"] == "LOW"]
    if not highs or not lows:
        return None
    return max(highs), min(lows), len(highs), len(lows)


def is_flat(window: list[dict], top: Decimal, bottom: Decimal,
            tol: Decimal) -> bool:
    """Do the pivots CLUSTER at two levels rather than march in one direction?

    See docstring (a): tightness and no-trend are the same predicate. Stated
    once here so there is no second place for them to drift apart.
    """
    for p in window:
        if p["type"] == "HIGH" and top - p["price"] > tol:
            return False
        if p["type"] == "LOW" and p["price"] - bottom > tol:
            return False
    return True


def contained(candles: list, atr: list, ticks: list, i0: int, i1: int,
              top: Decimal, bottom: Decimal) -> bool:
    """Did every bar of the formation window close inside the band?

    Closes only — a wick through a boundary is what a range boundary is FOR.
    """
    for j in range(i0, i1 + 1):
        close = Decimal(candles[j]["close"])
        tol = break_tolerance(atr[j], ticks[j])
        if close > top + tol or close < bottom - tol:
            return False
    return True


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "ranges", RANGES_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)

        raw = []
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in RANGE_TIERS:
                raw.append({"market_time": r["market_time"],
                            "confirmed_at": r["confirmed_at"],
                            "type": p["type"], "price": p["price"]})
        # alternate() inherits confirmed_at conservatively (the LATEST seen in a
        # replacement chain), so collapsing repeats can never make a range
        # knowable earlier than the swings that built it.
        seq = [{**p, "price": Decimal(p["price"])} for p in alternate(raw)]
        rec.n_inputs = len(seq)

        n_formed = n_tests = n_broken = 0
        min_pivot_ts = 0        # consumed-until guard; see docstring, one active range

        k = MIN_PIVOTS - 1
        while k < len(seq):
            window = seq[k - MIN_PIVOTS + 1:k + 1]
            first, last = window[0], window[-1]
            i0 = ts_index.get(first["market_time"])
            i1 = ts_index.get(last["market_time"])
            if (first["market_time"] < min_pivot_ts or i0 is None or i1 is None
                    or atr[i1] is None):
                k += 1
                continue

            # ATR is measured at the LAST forming pivot's bar — the bar at
            # which the range becomes a describable object. Measuring at the
            # first would size the band on volatility the range has already
            # outlived.
            a = atr[i1]
            edges = boundaries(window)
            if edges is None:
                k += 1
                continue
            top, bottom, n_top, n_bot = edges
            band = BOUNDARY_ATR * a
            height = top - bottom
            if not (MIN_HEIGHT_ATR * a <= height <= MAX_HEIGHT_ATR * a):
                k += 1
                continue
            if not is_flat(window, top, bottom, band):
                k += 1
                continue
            if not contained(candles, atr, ticks, i0, i1, top, bottom):
                k += 1
                continue

            # The obvious alternative to an ATR-relative tolerance is a
            # HEIGHT-relative one — a boundary should be thin compared to the
            # box it bounds, which is scale-free and would admit macro ranges
            # an ATR rule cannot. Measured, that case does not exist here: only
            # 9 windows in the whole store are taller than 8 ATR AND tight to
            # 20% of their height AND contained, because a months-long box
            # holds dozens of local pivots and any four CONSECUTIVE ones
            # describe a sub-box, never the whole thing. So the tolerance stays
            # at one zone width (a level is a level when one zone covers both
            # swings) and the height-relative view is RECORDED instead — the
            # consumer gets it without the definition being loosened for it.
            top_spread = max(top - p["price"] for p in window if p["type"] == "HIGH")
            bottom_spread = max(p["price"] - bottom for p in window if p["type"] == "LOW")
            formed_conf = last["confirmed_at"]
            lag_bars = max(0, (formed_conf - (candles[i1]["open_ts"] + tf_seconds))
                           // tf_seconds)
            range_id = f"{symbol}|{tf}|RANGE|{last['market_time']}"
            base = {"range_id": range_id,
                    "top": str(top), "bottom": str(bottom),
                    "mid": str((top + bottom) / 2),
                    "height": str(height),
                    "height_atr": str((height / a).quantize(Q2)),
                    "atr_at_formation": str(a),
                    "boundary_band": str(band),
                    "top_swings": n_top, "bottom_swings": n_bot,
                    "top_spread": str(top_spread),
                    "bottom_spread": str(bottom_spread),
                    "boundary_spread_pct": str(
                        (max(top_spread, bottom_spread) / height * 100).quantize(Q2)),
                    "member_ts": [p["market_time"] for p in window],
                    "range_start_ts": first["market_time"],
                    "formation_bars": i1 - i0,
                    "confirmation_lag_bars": lag_bars}

            if store.insert_fact(con, symbol=symbol, tf=tf, kind="range",
                                 market_time=last["market_time"],
                                 confirmed_at=formed_conf,
                                 algo_version=RANGES_VERSION,
                                 payload={**base, "event": "FORMED",
                                          "state": "FORMED",
                                          "top_touches": n_top,
                                          "bottom_touches": n_bot,
                                          "test_episodes": 0,
                                          "bars_held": 0}):
                n_formed += 1

            # --- forward walk: tests, then the break that ends the range ---
            top_touches, bottom_touches = n_top, n_bot
            episodes = 0
            # Seed the episode state from the forming bar itself. That bar IS
            # at a boundary by construction, so starting "outside" would score
            # the pivot that created the level as the first test OF the level.
            in_top = Decimal(candles[i1]["high"]) >= top - band
            in_bottom = Decimal(candles[i1]["low"]) <= bottom + band
            break_bar = None
            for j in range(i1 + 1, len(candles)):
                c = candles[j]
                bar_close_ts = c["open_ts"] + tf_seconds
                # It happened when it happened; it was knowable no earlier than
                # the range itself (§5).
                knowable = max(bar_close_ts, formed_conf)
                hi, lo = Decimal(c["high"]), Decimal(c["low"])
                close = Decimal(c["close"])
                tol = break_tolerance(atr[j], ticks[j])
                if close > top + tol or close < bottom - tol:
                    side = "TOP" if close > top + tol else "BOTTOM"
                    if store.insert_fact(
                            con, symbol=symbol, tf=tf, kind="range",
                            market_time=c["open_ts"], confirmed_at=knowable,
                            algo_version=RANGES_VERSION,
                            payload={**base, "event": "BROKEN", "state": "BROKEN",
                                     "broken_side": side, "close": str(close),
                                     "tolerance": str(tol),
                                     "top_touches": top_touches,
                                     "bottom_touches": bottom_touches,
                                     "test_episodes": episodes,
                                     "bars_held": j - i1}):
                        n_broken += 1
                    break_bar = c
                    break

                at_top, at_bottom = hi >= top - band, lo <= bottom + band
                for side, at_band, was_in in (("TOP", at_top, in_top),
                                              ("BOTTOM", at_bottom, in_bottom)):
                    if not (at_band and not was_in):
                        continue
                    episodes += 1
                    if side == "TOP":
                        top_touches += 1
                    else:
                        bottom_touches += 1
                    if episodes > MAX_TEST_FACTS:
                        continue
                    if store.insert_fact(
                            con, symbol=symbol, tf=tf, kind="range",
                            market_time=c["open_ts"], confirmed_at=knowable,
                            algo_version=RANGES_VERSION,
                            payload={**base, "event": "TESTED", "state": "TESTED",
                                     "boundary": side, "episode": episodes,
                                     "reached": str(hi if side == "TOP" else lo),
                                     "top_touches": top_touches,
                                     "bottom_touches": bottom_touches,
                                     "test_episodes": episodes,
                                     "bars_held": j - i1}):
                        n_tests += 1
                in_top, in_bottom = at_top, at_bottom

            if break_bar is None:
                break           # still active: it owns the rest of the series
            # structure.py's re-arm convention: only pivots formed after the
            # break bar may build the next range.
            min_pivot_ts = break_bar["open_ts"] + 1
            k += 1

        con.commit()
        rec.n_new_facts = n_formed + n_tests + n_broken
        rec.notes = f"formed={n_formed} tested={n_tests} broken={n_broken}"
        return {"symbol": symbol, "tf": tf, "formed": n_formed,
                "tested": n_tests, "broken": n_broken}
