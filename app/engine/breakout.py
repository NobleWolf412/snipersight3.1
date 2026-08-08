"""Breakout-retest — trade the level that just broke, when it holds as support.

PROGRAM-PLAN Wave 2.4/F4. The first strategy whose TRIGGER is structural rather
than zonal: `setups.py` fires when price returns to a supply/demand zone, this
fires when price returns to a level that was just BROKEN and the level holds
from the other side. Same market, different reason to be there.

Why it lives in its own module rather than as another branch of
`setups.playbook()`: it reads a different fact kind. `setups.py` is organised
around zone lifecycle — its whole loop is `for zone_id, z in zones.items()` —
and a structural trigger has no zone to iterate. `scalein.py` set this precedent
already (a 1H structural trigger inside an HTF parent, emitting setup facts
under its own version), and following it keeps each module's loop honest about
what it actually walks.

What is deliberately SHARED, imported rather than reimplemented:
  · `setups.confirms` — the confirmation predicate. A second copy would drift,
    and the S40 tick bug is what a duplicated constant looks like at scale.
  · `setups.vetoes` — the disqualifying conditions.
  · the bracket shape: entry at the next bar's open, stop beyond the
    confirmation bar's extreme, target capped at MAX_TARGET_R.
  · the entry model (MAKER_THEN_MARKET) and its offset.

So this changes WHERE a trade comes from, not HOW it is executed or sized. That
is the smallest honest surface for a new strategy, and it means any difference
in its results is attributable to the trigger rather than to a hundred small
divergences in the machinery around it.

**Ungraded on arrival.** Nothing here has earned a place in the book. It emits
setup facts so `abtest` can measure it against the existing strategies on the
same candles, with the same costs, through the same simulator — and it should be
switched off if it does not clear that bar, exactly as range fade was closed by
evidence rather than shipped on plausibility.
"""
import json
from decimal import Decimal

from . import bias, costs, registry, store
from .liquidity import LIQ_VERSION
from .regime import REGIME_VERSION
from .runlog import RunRecorder
from .setups import (CONFIRM_MAX_BARS, ENTRY_MAX_BARS, ENTRY_MODEL, GOOD_RR,
                     MAKER_OFFSET_R, MAKER_WAIT_BARS, MAX_TARGET_R, MIN_RR,
                     MIN_RISK_COST_MULT, Q2, SL_BUFFER_ATR, confirms, vetoes)
from .structure import STRUCTURE_VERSION
from .swings import SWING_VERSION, compute_atr, quote_ticks

BREAKOUT_VERSION = "breakout-v0.5-draft"
# v0.5: records the TOP-DOWN BIAS BLOCK on every setup. No rule changed and no
# trade differs — `BIAS_POLICY` is ALLOW everywhere. The version moves because
# the payload does.
#
# This engine is the reason the bias layer is a SHARED module rather than a
# field on the trend playbook. It was ungraded on arrival and stayed that way
# (n=55, -0.076 R, CI [-0.545, +0.426] on 2026-07-30 — indistinguishable from
# zero), and a retest trade has an obvious top-down question of its own: a
# broken level that holds is worth more in the direction the rungs above are
# already going. Recording it here costs nothing and means the question is
# answerable for this cohort the day anyone asks, instead of needing a version
# bump and a re-run first.

#: What this playbook does about each bias alignment. RECORD-ONLY in v0.5 —
#: every state ALLOWs. See engine/bias.py for the vocabulary and for why
#: UNKNOWN may never be anything but ALLOW.
BIAS_POLICY = bias.validate_policy({
    "WITH": "ALLOW",
    "AGAINST": "ALLOW",
    "MIXED": "ALLOW",
    "FLAT": "ALLOW",
    "UNKNOWN": "ALLOW",
}, who="breakout.BIAS_POLICY")
# v0.4: cascade from structure-v0.12 (same-bar pivot pairs no longer shadow
# each other in the break series this engine trades from).
# v0.3: cascade from swing-v0.9 and structure-v0.11. Targets come from
# INTERMEDIATE+ swing prices and entries from structure breaks, so both input
# generations moved under this engine. NOTE: this engine read swing facts all
# along but was absent from CONSUMERS["swing"] in test_version_cascade.py —
# the exact gap that map exists to close; fixed there in the same commit.
# v0.2: same funding-aware economics gate as setup-v0.11.


# Bars after the break in which a retest may begin. Beyond this the level is not
# being retested, it is simply where price happens to be later — the causal link
# between the break and the return has gone.
RETEST_MAX_BARS = 12
# How close price must come to the broken level to count as a retest, in ATR.
# Wider than the zone band (0.25 ATR) because a broken level is a line, not a
# band, and price rarely touches a line exactly.
RETEST_PROX_ATR = Decimal("0.35")
# A retest that trades far THROUGH the level is not a retest, it is a failed
# break. Past this the setup is abandoned rather than confirmed.
RETEST_INVALIDATE_ATR = Decimal("0.75")


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "breakout", BREAKOUT_VERSION, symbol, tf) as rec:
        if tf not in registry.BREAKOUT_RETEST.timeframes:
            return {"symbol": symbol, "tf": tf, "setups": 0, "rejected": 0}
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        if len(candles) < 30:
            return {"symbol": symbol, "tf": tf, "setups": 0, "rejected": 0}
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)
        profile = costs.profile_for(symbol)
        cost_manifest_hash = costs.record(con, profile)
        manifest_hash = store.record_manifest(con, "strategy", {
            "version": BREAKOUT_VERSION,
            "retest_max_bars": RETEST_MAX_BARS,
            "retest_prox_atr": str(RETEST_PROX_ATR),
            "retest_invalidate_atr": str(RETEST_INVALIDATE_ATR),
            "confirm_max_bars": CONFIRM_MAX_BARS,
            "min_rr": str(MIN_RR), "max_target_r": str(MAX_TARGET_R),
            "entry_model": ENTRY_MODEL,
            "cost_profile": profile.payload(),
            "bias_policy": dict(BIAS_POLICY),
            "inputs": {"structure": STRUCTURE_VERSION, "swing": SWING_VERSION,
                       "regime": REGIME_VERSION, "liquidity": LIQ_VERSION,
                       **bias.inputs()},
        })
        bias_src = bias.load(con, symbol, tf)

        breaks = []
        for r in store.get_facts(con, symbol, tf, "structure", STRUCTURE_VERSION):
            p = json.loads(r["payload"])
            if p["event"] == "BOS":          # continuation only; a CHoCH retest
                breaks.append({               # is a reversal trade, not this one
                    "market_time": r["market_time"],
                    "confirmed_at": r["confirmed_at"],
                    "direction": p["direction"],
                    "level": Decimal(p["level"])})
        rec.n_inputs = len(breaks)

        # Opposing structure for the target, same source setups.py uses.
        tier_swings = {"HIGH": [], "LOW": []}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ("INTERMEDIATE", "MAJOR"):
                tier_swings[p["type"]].append(
                    {"confirmed_at": r["confirmed_at"], "price": Decimal(p["price"])})

        def target(direction, entry, as_of):
            side = "HIGH" if direction == "LONG" else "LOW"
            beyond = [s["price"] for s in tier_swings[side]
                      if s["confirmed_at"] <= as_of
                      and (s["price"] > entry if direction == "LONG"
                           else s["price"] < entry)]
            if not beyond:
                return None
            return min(beyond) if direction == "LONG" else max(beyond)

        n_setups = n_rejected = n_bias_blocked = 0
        for b in breaks:
            direction = "LONG" if b["direction"] == "BULL" else "SHORT"
            i0 = ts_index.get(b["market_time"])
            if i0 is None or atr[i0] is None:
                continue
            level = b["level"]

            # --- walk forward for a retest of the broken level ---
            ci = None
            for j in range(i0 + 1, min(i0 + 1 + RETEST_MAX_BARS, len(candles))):
                c = candles[j]
                bct = c["open_ts"] + tf_seconds
                if bct <= b["confirmed_at"] or atr[j] is None:
                    continue
                hi, lo = Decimal(c["high"]), Decimal(c["low"])
                # Did price come back to the level from the break side?
                if direction == "LONG":
                    reached = lo <= level + RETEST_PROX_ATR * atr[j]
                    failed = lo < level - RETEST_INVALIDATE_ATR * atr[j]
                else:
                    reached = hi >= level - RETEST_PROX_ATR * atr[j]
                    failed = hi > level + RETEST_INVALIDATE_ATR * atr[j]
                if failed:
                    break                    # the break failed; not a retest
                if not reached:
                    continue
                # The level is treated as a one-tick band so the SAME
                # confirmation predicate applies as it does to a zone. Reusing
                # `setups.confirms` rather than restating it is the point.
                band = ticks[j] or Decimal("0")
                if confirms(c, direction, level + band, level - band):
                    ci = j
                    break

            if ci is None:
                continue
            cb = candles[ci]
            bct = cb["open_ts"] + tf_seconds
            if ci + 1 >= len(candles):
                continue                      # next bar has not closed yet

            entry = Decimal(candles[ci + 1]["open"])
            if direction == "LONG":
                sl = min(Decimal(cb["low"]), level) - SL_BUFFER_ATR * atr[ci]
            else:
                sl = max(Decimal(cb["high"]), level) + SL_BUFFER_ATR * atr[ci]
            risk = (entry - sl) if direction == "LONG" else (sl - entry)
            if risk <= 0:
                continue

            fired = vetoes(confirm_bar=cb, atr_at_confirm=atr[ci],
                           entry=entry, sl=sl, tick=ticks[ci])
            if fired:
                n_rejected += 1
                continue

            tp_uncapped = target(direction, entry, bct)
            if tp_uncapped is None:
                n_rejected += 1
                continue
            cap = (entry + MAX_TARGET_R * risk) if direction == "LONG" \
                else (entry - MAX_TARGET_R * risk)
            tp = min(tp_uncapped, cap) if direction == "LONG" else max(tp_uncapped, cap)
            rr = (((tp - entry) if direction == "LONG" else (entry - tp))
                  / risk).quantize(Q2)
            if rr < MIN_RR:
                n_rejected += 1
                continue
            if risk < MIN_RISK_COST_MULT * costs.estimated_round_trip_cost(
                    entry, atr[ci], profile, symbol=symbol, tf_seconds=tf_seconds):
                n_rejected += 1
                continue

            maker_limit = ((entry - MAKER_OFFSET_R * risk) if direction == "LONG"
                           else (entry + MAKER_OFFSET_R * risk))
            # THE TOP-DOWN GATE. Inert while BIAS_POLICY is ALLOW everywhere,
            # and on this engine that is not a measured decision but an ABSENT
            # one: breakout has never been graded against the ladder, because
            # at n=55 it has no sample to grade with. ALLOW is what "we have
            # not looked" must resolve to, exactly as UNKNOWN is.
            bias_block = bias_src.check(direction, bct, tf_seconds, BIAS_POLICY)
            if bias.blocked(bias_block):
                store.insert_fact(
                    con, symbol=symbol, tf=tf, kind="setup_rejection",
                    market_time=cb["open_ts"], confirmed_at=bct,
                    algo_version=BREAKOUT_VERSION,
                    payload={"event": "REJECTED", "reason": "BIAS_BLOCKED",
                             "details": {"bias": bias_block,
                                         "strategy": "BREAKOUT_RETEST",
                                         "direction": direction},
                             "manifest_hash": manifest_hash})
                n_bias_blocked += 1
                continue
            setup_id = (f"{symbol}|{tf}|BREAKOUT_RETEST|{b['market_time']}"
                        f"|{BREAKOUT_VERSION}")
            payload = {
                "setup_id": setup_id, "strategy": "BREAKOUT_RETEST",
                "direction": direction, "state": "VALIDATED",
                "entry": str(entry), "sl": str(sl), "tp": str(tp),
                "tp_uncapped": str(tp_uncapped), "rr": str(rr),
                "rank": 0,                    # rank is retired; see setups.py S39
                "maker_limit": str(maker_limit),
                "maker_wait_bars": MAKER_WAIT_BARS,
                "entry_model": ENTRY_MODEL,
                "broken_level": str(level),
                "break_market_time": b["market_time"],
                "retest_bars_after_break": ci - i0,
                "confirmed_bar_ts": cb["open_ts"],
                "why": (f"{b['direction']} break of {float(level):,.4f} held on "
                        f"retest {ci - i0} bars later · confirmed by a close back "
                        f"{'above' if direction == 'LONG' else 'below'} it · "
                        f"R:R {rr}"),
                # Top-down annotation, read as-of `bct` — a setup may only know
                # the rungs that had already confirmed when it triggered.
                # The SAME block the gate judged, not a second call.
                "bias": bias_block,
                "manifest_hash": manifest_hash,
                "cost_manifest_hash": cost_manifest_hash,
                "armed": False, "armed_at": bct,
                "expiry_bar_count": ENTRY_MAX_BARS,
                "expires_at_ts": bct + ENTRY_MAX_BARS * tf_seconds,
                "inherited_from_forming": False, "forming_id": None,
                "size_units": None, "risk_usd": None, "notional_usd": None,
                "implied_leverage": None, "risk_decision": None,
                "risk_reasons": [],
            }
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=cb["open_ts"], confirmed_at=bct,
                                 algo_version=BREAKOUT_VERSION, payload=payload):
                n_setups += 1

        con.commit()
        rec.n_new_facts = n_setups
        rec.notes = f"rejected={n_rejected} bias_blocked={n_bias_blocked}"
        return {"symbol": symbol, "tf": tf, "setups": n_setups,
                "rejected": n_rejected, "bias_blocked": n_bias_blocked}
