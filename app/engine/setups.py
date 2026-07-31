"""Setup detector — pullback playbook. algo setup-v0.1-draft.

The strategy layer consumes ONLY confirmed facts through the same as_of
semantics as the chart (§3: no layer skipping — this engine never looks at
candles to form an opinion, only to measure ATR/volume at the trigger bar).

Draft playbook (user's regime->strategy mapping; versioned):
- LONG:  regime BULL_TREND at touch time + price touches a DEMAND zone.
- SHORT: regime BEAR_TREND at touch time + price touches a SUPPLY zone.
- Entry = zone edge nearest price (top of demand / bottom of supply).
- SL    = structural invalidation: far edge of zone -/+ 0.25 ATR (§9: stops
  are structure, not percentages).
- TP    = nearest unbroken liquidity pool beyond entry; fallback: nearest
  INTERMEDIATE/MAJOR opposing swing. No target -> no setup.
- Gate  = R:R >= 1.5 or the setup is never emitted.
- Rank  = deterministic confluence score 0-100 (NOT a probability, §25):
  base 50 + sweep-nearby 20 + touch-bar volume 15 + R:R >= 2.5 15.
- Lifecycle: VALIDATED at zone touch; EXPIRED when the zone breaks.
Every setup carries a plain-language WHY assembled from the facts it used (§8).
"""
import json
from decimal import Decimal

from . import store
from .swings import compute_atr, SWING_VERSION
from .zones import ZONE_VERSION
from .liquidity import LIQ_VERSION
from .regime import REGIME_VERSION
from .runlog import RunRecorder
from . import costs

SETUP_VERSION = "setup-v0.7-draft"
# ── v0.7 — CONFIRMED ENTRY. The change this version exists for. ──────────────
# Measured on the v0.6 book (142 filled trades, 13% win, -102.8R):
#   · 73 of 124 stop-outs (59%) resolved on the BAR THAT FILLED THE ENTRY
#   · median bars_held = 0
#   · median MAE 1.65R — the typical trade traded straight through its stop
# Cause, and it is geometric rather than a matter of tuning: the zone is
# 0.25 ATR wide and the stop sat 0.25 ATR beyond its far edge, so total risk was
# ~0.5 ATR. The bar that touches an ATR-anchored zone has a range of roughly
# 1 ATR by construction. The stop was inside the noise of its own trigger bar,
# so the trigger bar and the killing bar were the same bar.
#
# Second-order consequence, equally damaging: with risk pinned near 0.5 ATR the
# ONLY way a setup could satisfy R:R >= 1.5 was a distant target. Median target
# ran 6.4R against a median favourable excursion of 1.53R. The gate meant to
# enforce quality was selecting for improbability.
#
# v0.7 waits for a CLOSE that proves the level held before calling it a trade:
#   TOUCH -> CONFIRMING -> (confirming close) -> VALIDATED
#                       -> (window elapses)   -> CANCELLED CONFIRMATION_TIMEOUT
#                       -> (zone breaks)      -> CANCELLED ZONE_BROKE_UNCONFIRMED
# The wick that would have stopped you has already printed, and the stop becomes
# a low the market visibly rejected instead of an ATR offset. It is wider on
# purpose: a wider, earned stop un-pins risk and lets targets come back to
# reachable distances.
FORMING_TFS = ("4H", "1D", "1W")
PROX_ATR = Decimal(1)
MIN_RR = Decimal("1.5")
GOOD_RR = Decimal("2.5")
SL_ATR = Decimal("0.25")            # v0.6 zone-offset stop; kept for FORMING previews
SWEEP_LOOKBACK_BARS = 10
Q2 = Decimal("0.01")
# Armed-order window: number of bars a limit stays live before it MISSES.
# MUST equal execsim.MAX_ENTRY_BARS — Phase G will collapse to one source.
ENTRY_MAX_BARS = 4

# --- confirmation (v0.7) ---
# Bars after the touch in which a confirming close may appear. Three is a
# deliberate opening guess, not a calibrated value: long enough that a zone
# needing a retest still qualifies, short enough that "it eventually went up"
# is not mistaken for "the level held". The 2x2 replay grades it.
CONFIRM_MAX_BARS = 3
# The confirming bar must close in this fraction of its own range, measured
# from the far side — i.e. a LONG needs a close in the upper third. This is
# what separates a rejection wick from a bar that merely drifted back out.
REJECTION_FRACTION = Decimal("0.66")
# Structural buffer beyond the confirmation bar's own extreme. Small, because
# the extreme is ALREADY a tested level; this only clears the tick noise around
# it rather than inventing a second cushion.
SL_BUFFER_ATR = Decimal("0.15")
# Targets are capped in R. `target()` returns the nearest opposing structure,
# which on a daily chart can be a quarter away. Both the capped and uncapped
# values are recorded so a later version can measure whether the cap helped.
MAX_TARGET_R = Decimal(3)
ENTRY_MODEL = "MARKET_NEXT_OPEN"
# The higher timeframe each timeframe defers to, for the HTF-alignment factor.
# scalein.py already encodes the principle — "the higher timeframe GATES the
# lower" — it was simply never applied to the primary entry.
HTF_LADDER = {"15m": "1H", "1H": "4H", "4H": "1D", "1D": "1W", "1W": None}

# Cost model is an immutable profile shared with execution simulation, resolved
# PER SYMBOL from its venue via costs.profile_for. There is deliberately no
# module-level COST_PROFILE any more: a single global here is what charged
# Coinbase spot fees to Phemex perps, and it made the mistake invisible because
# every consumer that imported the name inherited it.

# v0.3 (validation-001 finding): tight stops make fees enormous in R terms —
# 15m round-trip costs ran 3-6R and the whole intraday book was net-negative.
# Fee-aware gate: a setup is only economic if risk >= K x estimated round-trip
# cost (2 fees on entry notional + one market-exit slippage).
# v0.4: K=2 (max ~0.5R cost drag). K=4 was unattainable with 0.5-ATR structural
# stops on BTC 1D (fees are % of notional; max achievable ratio ~2.9) and
# rejected 193/200 including the profitable 1D book — the user's named failure
# mode. Deterministic, pre-trade, evaluated at validation time.
MIN_RISK_COST_MULT = Decimal(2)

# v0.2 (CAL-5 diagnosis 2026-07-21): TRANSITION regimes ate most zone touches
# with no playbook to trade them — user's own mapping says exhaustion->reversal.
# Added REVERSAL playbook (TRANSITION + zone touch, lower base rank) and
# WEAKENING_* continuation entries. Draft pending §30 item 9 ratification.


def playbook(zone_type: str, reg: str | None, swept: bool = False,
             enabled: set | None = None):
    """Returns (strategy, direction, base_rank) or None if no play.

    `enabled` is the operator's strategy selection. `settings.py` has defined
    `strategy_pullback` / `strategy_reversal` / `strategy_scale_in` as
    BEHAVIOURAL settings since S34 and `/api/settings` has been wired the whole
    time, but nothing ever READ them — the switches were inert and turning one
    off changed nothing. Honouring them here is what makes the setting real;
    the active set is recorded in the strategy manifest so any fact can be
    traced to the configuration that produced it.
    """
    def allow(strategy):
        return enabled is None or strategy in enabled

    if zone_type == "DEMAND":
        if reg in ("BULL_TREND", "WEAKENING_BULL") and allow("PULLBACK"):
            return "PULLBACK", "LONG", 50
        if reg == "TRANSITION" and swept and allow("REVERSAL"):
            return "REVERSAL", "LONG", 40
    else:
        if reg in ("BEAR_TREND", "WEAKENING_BEAR") and allow("PULLBACK"):
            return "PULLBACK", "SHORT", 50
        if reg == "TRANSITION" and swept and allow("REVERSAL"):
            return "REVERSAL", "SHORT", 40
    return None


def enabled_strategies(con) -> set:
    """Operator-selected strategies, defaulting to all when unset/unavailable.

    Fails OPEN deliberately. A settings-table read failure that silently
    disabled every strategy would look identical to a quiet market, and this
    system's whole complaint about itself is that silence must never be
    ambiguous.
    """
    try:
        from . import settings
        values = settings.all_settings(con)
    except Exception:
        return {"PULLBACK", "REVERSAL", "SCALE_IN"}
    out = set()
    for key, name in (("strategy_pullback", "PULLBACK"),
                      ("strategy_reversal", "REVERSAL"),
                      ("strategy_scale_in", "SCALE_IN")):
        if values.get(key, True):
            out.add(name)
    return out


def confirms(candle: dict, direction: str, top: Decimal, bottom: Decimal) -> bool:
    """Did this CLOSED bar prove the zone held?

    Three conditions, all required (LONG shown; SHORT mirrors):
      1. the bar engaged the zone            low  <= zone top
      2. and closed back out of it           close > zone top
      3. with the close in the upper third   close >= low + 0.66 * (high - low)

    (3) is what distinguishes a rejection from a drift. A bar that closes
    fractionally above the zone after spending its session inside it has not
    demonstrated anything; a bar that spikes down into it and closes near its
    high has. Without this the rule would admit most touches and change nothing.
    """
    hi, lo = Decimal(candle["high"]), Decimal(candle["low"])
    close = Decimal(candle["close"])
    rng = hi - lo
    if direction == "LONG":
        if not (lo <= top and close > top):
            return False
        return rng <= 0 or close >= lo + REJECTION_FRACTION * rng
    if not (hi >= bottom and close < bottom):
        return False
    return rng <= 0 or close <= hi - REJECTION_FRACTION * rng


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "setup", SETUP_VERSION, symbol, tf) as rec:
        enabled = enabled_strategies(con)
        # v0.7: the cost profile is VENUE-derived, not a module constant. It was
        # Coinbase spot for every symbol while the traded universe was entirely
        # Phemex perps — a 14x over-charge that made the economics gate demand a
        # ~14x wider stop before a setup counted as economic. See costs.profile_for.
        profile = costs.profile_for(symbol)
        strategy_manifest = {
            "version": SETUP_VERSION, "min_rr": str(MIN_RR),
            "good_rr": str(GOOD_RR), "sl_atr": str(SL_ATR),
            "sweep_lookback_bars": SWEEP_LOOKBACK_BARS,
            "min_risk_cost_multiple": str(MIN_RISK_COST_MULT),
            "reversal_requires_sweep": True,
            # v0.7 — the confirmed-entry parameters are part of the manifest
            # because they change which facts exist, not merely how they look.
            "confirm_max_bars": CONFIRM_MAX_BARS,
            "rejection_fraction": str(REJECTION_FRACTION),
            "sl_buffer_atr": str(SL_BUFFER_ATR),
            "max_target_r": str(MAX_TARGET_R),
            "entry_model": ENTRY_MODEL,
            "enabled_strategies": sorted(enabled),
            "cost_profile": profile.payload(),
            "inputs": {"swing": SWING_VERSION, "zone": ZONE_VERSION,
                       "liquidity": LIQ_VERSION, "regime": REGIME_VERSION},
        }
        manifest_hash = store.record_manifest(con, "strategy", strategy_manifest)
        cost_manifest_hash = costs.record(con, profile)
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)

        regimes = []
        for r in store.get_facts(con, symbol, tf, "regime", REGIME_VERSION):
            regimes.append((r["confirmed_at"], json.loads(r["payload"])["regime"]))
        regimes.sort()

        def regime_at(ts):
            cur = None
            for conf, reg in regimes:
                if conf <= ts:
                    cur = reg
                else:
                    break
            return cur

        # Higher-timeframe regime, read with the SAME as_of discipline: a 4H
        # trade may only know the 1D regime that had already confirmed by then.
        htf = HTF_LADDER.get(tf)
        htf_regimes = []
        if htf:
            for r in store.get_facts(con, symbol, htf, "regime", REGIME_VERSION):
                htf_regimes.append((r["confirmed_at"],
                                    json.loads(r["payload"])["regime"]))
            htf_regimes.sort()

        def htf_regime_at(ts):
            cur = None
            for conf, reg in htf_regimes:
                if conf <= ts:
                    cur = reg
                else:
                    break
            return cur

        zones: dict = {}
        for r in store.get_facts(con, symbol, tf, "zone", ZONE_VERSION):
            p = json.loads(r["payload"])
            z = zones.setdefault(p["zone_id"], {})
            rec_p = {"market_time": r["market_time"],
                     "confirmed_at": r["confirmed_at"], **p}
            if p["event"] == "TOUCH":
                if p.get("episode") == 1:
                    z["TOUCHED"] = rec_p       # first episode is the trigger
            else:
                z[p["event"]] = rec_p

        pools, pool_broken, sweeps = [], {}, []
        for r in store.get_facts(con, symbol, tf, "liquidity", LIQ_VERSION):
            p = json.loads(r["payload"])
            if p["event"] == "POOL":
                pools.append({"confirmed_at": r["confirmed_at"], "side": p["side"],
                              "level": Decimal(p["level"]), "pool_id": p["pool_id"]})
            elif p["event"] == "BROKEN":
                pool_broken[p["pool_id"]] = r["confirmed_at"]
            elif p["event"] == "SWEEP":
                sweeps.append({"market_time": r["market_time"],
                               "confirmed_at": r["confirmed_at"], "side": p["side"]})

        # Structure breaks, for the "bars since the last break" confluence
        # factor only. Recorded as evidence; nothing gates on it.
        from .structure import STRUCTURE_VERSION
        breaks_by_conf = []
        for r in store.get_facts(con, symbol, tf, "structure", STRUCTURE_VERSION):
            p = json.loads(r["payload"])
            if p["event"] in ("BOS", "CHOCH"):
                breaks_by_conf.append({"market_time": r["market_time"],
                                       "confirmed_at": r["confirmed_at"]})
        breaks_by_conf.sort(key=lambda b: b["confirmed_at"])

        tier_swings = {"HIGH": [], "LOW": []}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ("INTERMEDIATE", "MAJOR"):
                tier_swings[p["type"]].append(
                    {"confirmed_at": r["confirmed_at"], "price": Decimal(p["price"])})

        def target(direction, entry, as_of):
            side = "HIGH" if direction == "LONG" else "LOW"
            beyond = [p["level"] for p in pools
                      if p["side"] == side and p["confirmed_at"] <= as_of
                      and pool_broken.get(p["pool_id"], 2**53) > as_of
                      and (p["level"] > entry if direction == "LONG" else p["level"] < entry)]
            if not beyond:
                beyond = [s["price"] for s in tier_swings[side]
                          if s["confirmed_at"] <= as_of
                          and (s["price"] > entry if direction == "LONG" else s["price"] < entry)]
            if not beyond:
                return None
            return min(beyond) if direction == "LONG" else max(beyond)

        def recent_sweep(direction, market_time, confirmed_at):
            side = "LOW" if direction == "LONG" else "HIGH"
            lookback = SWEEP_LOOKBACK_BARS * tf_seconds
            return any(s["side"] == side
                       and 0 <= market_time - s["market_time"] <= lookback
                       and s["confirmed_at"] <= confirmed_at for s in sweeps)

        rec.n_inputs = len(zones)
        n_setups = n_expired = n_cost_rejected = n_forming = n_cancelled = n_rejected = 0
        n_confirming = n_unconfirmed = 0

        def volume_ratio(i):
            """Confirmation-bar volume against its trailing 20-bar average."""
            if i < 20:
                return None
            avg = sum(Decimal(candles[j]["volume"]) for j in range(i - 20, i)) / 20
            if avg <= 0:
                return None
            return (Decimal(candles[i]["volume"]) / avg).quantize(Q2)

        def confluence_block(direction, i, created, bct, swept, target_r):
            """Evidence RECORDED, never filtered on (§22 discipline).

            `score` is deliberately emitted as 0 and consumed by nothing. The
            field exists so the schema is stable from day one and a later
            version can populate it without a migration — but a factor only
            earns a gate after `engine/factorstats.py` shows it clears fire
            rate, dispersion, redundancy against already-promoted factors, and
            an outcome correlation beyond the ±1.96/√n noise floor.

            The previous project shipped 26 factors that were really about five
            independent signals, each counted several times. Recording first and
            grading second is the whole defence against repeating that.
            """
            hr = htf_regime_at(bct)
            aligned = None
            if hr is not None:
                aligned = ((direction == "LONG" and hr in ("BULL_TREND", "WEAKENING_BULL"))
                           or (direction == "SHORT" and hr in ("BEAR_TREND", "WEAKENING_BEAR")))
            vr = volume_ratio(i)
            last_break_bars = None
            for b in reversed(breaks_by_conf):
                if b["confirmed_at"] <= bct:
                    last_break_bars = max(0, (candles[i]["open_ts"] - b["market_time"])
                                          // tf_seconds)
                    break
            return {
                "htf_timeframe": htf,
                "htf_regime": hr,
                "htf_regime_aligned": aligned,
                "zone_strength": created.get("strength"),
                "zone_quality": created.get("formation_quality"),
                "zone_cluster": created.get("cluster_members"),
                "volume_expansion": None if vr is None else str(vr),
                "sweep_nearby": swept,
                "bars_since_break": last_break_bars,
                "target_distance_r": None if target_r is None else str(target_r),
                "score": 0,
            }

        def reject(zone_id, touched, reason, details=None):
            nonlocal n_rejected
            payload = {"event": "REJECTED", "zone_id": zone_id,
                       "reason": reason, "details": details or {},
                       "manifest_hash": manifest_hash}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup_rejection",
                                 market_time=touched["market_time"],
                                 confirmed_at=touched["confirmed_at"],
                                 algo_version=SETUP_VERSION, payload=payload):
                n_rejected += 1

        def gates(direction, entry, sl, tp, a):
            """Shared R:R + fee gates. Returns rr or None."""
            risk = (entry - sl) if direction == "LONG" else (sl - entry)
            reward = (tp - entry) if direction == "LONG" else (entry - tp)
            if risk <= 0 or reward <= 0:
                return None
            rr = (reward / risk).quantize(Q2)
            if rr < MIN_RR:
                return None
            if risk < MIN_RISK_COST_MULT * costs.estimated_round_trip_cost(
                    entry, a, profile):
                return None
            return rr

        # --- FORMING pass: price approaching an untouched active zone ---
        if tf in FORMING_TFS:
            for zone_id, z in zones.items():
                created = z.get("CREATED")
                if not created:
                    continue
                touched, broken = z.get("TOUCHED"), z.get("BROKEN")
                i0 = ts_index.get(created["market_time"])
                if i0 is None:
                    continue
                end_ts = min(touched["market_time"] if touched else 2**53,
                             broken["market_time"] if broken else 2**53)
                top, bottom = Decimal(created["top"]), Decimal(created["bottom"])
                emitted = None
                for j in range(i0 + 1, len(candles)):
                    c = candles[j]
                    bct = c["open_ts"] + tf_seconds
                    if bct <= created["confirmed_at"]:
                        continue
                    if c["open_ts"] >= end_ts:
                        break
                    if atr[j] is None:
                        continue
                    lo, hi = Decimal(c["low"]), Decimal(c["high"])
                    dist = (lo - top) if created["zone_type"] == "DEMAND" else (bottom - hi)
                    if dist <= 0:
                        break                    # reached the zone; TOUCH path owns it
                    if dist > PROX_ATR * atr[j]:
                        continue
                    reg_f = regime_at(bct)
                    dir_hint = "LONG" if created["zone_type"] == "DEMAND" else "SHORT"
                    swept_f = recent_sweep(dir_hint, c["open_ts"], bct)
                    play_f = playbook(created["zone_type"], reg_f, swept_f)
                    if play_f is None:
                        continue
                    strat_f, dir_f, _ = play_f
                    if dir_f == "LONG":
                        entry_f, sl_f = top, bottom - SL_ATR * atr[j]
                    else:
                        entry_f, sl_f = bottom, top + SL_ATR * atr[j]
                    tp_f = target(dir_f, entry_f, bct)
                    if tp_f is None:
                        continue
                    rr_f = gates(dir_f, entry_f, sl_f, tp_f, atr[j])
                    if rr_f is None:
                        continue
                    dist_atr = (dist / atr[j]).quantize(Q2)
                    payload = {"setup_id": f"{symbol}|{tf}|{strat_f}|{zone_id}",
                               "strategy": strat_f, "direction": dir_f,
                               "entry": str(entry_f), "sl": str(sl_f), "tp": str(tp_f),
                               "rr": str(rr_f), "rank": 0,
                               "why": (f"price {dist_atr} ATR from {created['zone_type']} zone "
                                       f"{float(bottom):,.2f}-{float(top):,.2f} in {reg_f} · "
                                       f"prospective {strat_f} would pass all gates · watching"),
                               "zone_id": zone_id, "regime": reg_f, "state": "FORMING",
                               "distance_atr": str(dist_atr),
                               "zone_strength": created.get("strength"),
                               "manifest_hash": manifest_hash,
                               "cost_manifest_hash": cost_manifest_hash,
                               # Armed-order fields (Phase D scaffolding; sizing
                               # wired in Phase E, inheritance in Phase F).
                               "size_units": None, "risk_usd": None,
                               "notional_usd": None, "implied_leverage": None,
                               "risk_decision": None, "risk_reasons": [],
                               "armed": False,
                               "armed_at": bct,
                               "expiry_bar_count": ENTRY_MAX_BARS,
                               "expires_at_ts": bct + ENTRY_MAX_BARS * tf_seconds}
                    if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                         market_time=c["open_ts"], confirmed_at=bct,
                                         algo_version=SETUP_VERSION, payload=payload):
                        n_forming += 1
                    emitted = payload
                    break
                if emitted and broken and not touched:
                    if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                         market_time=broken["market_time"],
                                         confirmed_at=broken["confirmed_at"],
                                         algo_version=SETUP_VERSION,
                                         payload={**emitted, "state": "CANCELLED"}):
                        n_cancelled += 1

        for zone_id, z in zones.items():
            created, touched = z.get("CREATED"), z.get("TOUCHED")
            if not created or not touched:
                continue
            reg = regime_at(touched["confirmed_at"])
            dir_hint = "LONG" if created["zone_type"] == "DEMAND" else "SHORT"
            swept = recent_sweep(dir_hint, touched["market_time"], touched["confirmed_at"])
            play = playbook(created["zone_type"], reg, swept, enabled)
            if play is None:
                reject(zone_id, touched, "NO_ELIGIBLE_PLAYBOOK",
                       {"zone_type": created["zone_type"], "regime": reg,
                        "recent_sweep": swept})
                continue
            strategy, direction, base_rank = play
            i0 = ts_index.get(touched["market_time"])
            if i0 is None or atr[i0] is None:
                reject(zone_id, touched, "ATR_UNAVAILABLE")
                continue
            top, bottom = Decimal(created["top"]), Decimal(created["bottom"])
            setup_id = f"{symbol}|{tf}|{strategy}|{zone_id}"
            broken = z.get("BROKEN")
            break_ts = broken["market_time"] if broken else 2**53

            # ── CONFIRMING: price is in the zone, nothing is proven yet ──────
            # This is the state that used to be VALIDATED. Emitting it keeps the
            # candidate visible on the deck (and countable in the funnel) while
            # it is still deciding, so a user is never left wondering whether
            # the scanner noticed.
            confirming = {"setup_id": setup_id, "strategy": strategy,
                          "direction": direction, "zone_id": zone_id,
                          "regime": reg, "state": "CONFIRMING",
                          "entry": None, "sl": None, "tp": None,
                          "rr": None, "rank": 0,
                          "why": (f"price reached the {created['zone_type']} zone "
                                  f"{float(bottom):,.2f}-{float(top):,.2f} in {reg} · "
                                  f"waiting for a close that proves it held "
                                  f"({CONFIRM_MAX_BARS} bars)"),
                          "confirm_deadline_ts": (touched["confirmed_at"]
                                                  + CONFIRM_MAX_BARS * tf_seconds),
                          "manifest_hash": manifest_hash,
                          "cost_manifest_hash": cost_manifest_hash}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=touched["market_time"],
                                 confirmed_at=touched["confirmed_at"],
                                 algo_version=SETUP_VERSION, payload=confirming):
                n_confirming += 1

            # ── walk forward for a confirming close ─────────────────────────
            ci = None
            for j in range(i0, min(i0 + 1 + CONFIRM_MAX_BARS, len(candles))):
                c = candles[j]
                if c["open_ts"] >= break_ts:
                    break                      # the zone failed before it proved
                if c["open_ts"] + tf_seconds <= touched["confirmed_at"] and j != i0:
                    continue
                if confirms(c, direction, top, bottom):
                    ci = j
                    break

            if ci is None:
                cancel_at = min(i0 + CONFIRM_MAX_BARS, len(candles) - 1)
                reason = ("ZONE_BROKE_UNCONFIRMED"
                          if broken and broken["market_time"] <= candles[cancel_at]["open_ts"]
                          else "CONFIRMATION_TIMEOUT")
                # A zone that broke before confirming is a LOSS AVOIDED, not
                # attrition. The UI must present it that way or the filter that
                # is helping the operator will read as the thing failing them.
                if store.insert_fact(
                        con, symbol=symbol, tf=tf, kind="setup",
                        market_time=candles[cancel_at]["open_ts"],
                        confirmed_at=candles[cancel_at]["open_ts"] + tf_seconds,
                        algo_version=SETUP_VERSION,
                        payload={**confirming, "state": "CANCELLED",
                                 "cancel_reason": reason}):
                    n_unconfirmed += 1
                continue

            # ── VALIDATED: the level held, on the evidence of a closed bar ───
            cb = candles[ci]
            bct = cb["open_ts"] + tf_seconds          # when this became knowable
            if atr[ci] is None:
                reject(zone_id, touched, "ATR_UNAVAILABLE")
                continue
            # Entry is the NEXT bar's open — a price that demonstrably traded,
            # so no fill assumption is required. v0.6 rested a limit at the zone
            # edge and MISSED 90 of 232 orders (39%); a miss is not a neutral
            # outcome, it is a signal the book never got to express.
            if ci + 1 >= len(candles):
                continue                              # next bar has not closed yet
            entry = Decimal(candles[ci + 1]["open"])
            # Stop sits beyond the confirmation bar's own extreme: a level the
            # market has just visibly rejected, not an ATR offset from a zone.
            if direction == "LONG":
                sl = min(Decimal(cb["low"]), bottom) - SL_BUFFER_ATR * atr[ci]
            else:
                sl = max(Decimal(cb["high"]), top) + SL_BUFFER_ATR * atr[ci]
            risk = (entry - sl) if direction == "LONG" else (sl - entry)
            if risk <= 0:
                reject(zone_id, touched, "INVALID_BRACKET")
                continue

            tp_uncapped = target(direction, entry, bct)
            if tp_uncapped is None:
                reject(zone_id, touched, "NO_CAUSAL_TARGET")
                continue
            # Cap the target in R. Uncapped, `target()` returns the nearest
            # opposing structure — which on a daily chart is routinely a quarter
            # away, and produced a 6.4R median against a 1.53R median favourable
            # excursion. Both values are recorded so the cap can be graded.
            cap = (entry + MAX_TARGET_R * risk) if direction == "LONG" \
                else (entry - MAX_TARGET_R * risk)
            tp = min(tp_uncapped, cap) if direction == "LONG" else max(tp_uncapped, cap)

            rr = ((tp - entry) if direction == "LONG" else (entry - tp)) / risk
            rr = rr.quantize(Q2)
            if rr < MIN_RR:
                reject(zone_id, touched, "RR_BELOW_MINIMUM",
                       {"rr": str(rr), "minimum": str(MIN_RR)})
                continue
            est_cost = costs.estimated_round_trip_cost(entry, atr[ci], profile)
            if risk < MIN_RISK_COST_MULT * est_cost:
                n_cost_rejected += 1
                reject(zone_id, touched, "UNECONOMIC_AFTER_COSTS",
                       {"risk_price_units": str(risk),
                        "estimated_cost_price_units": str(est_cost),
                        "required_multiple": str(MIN_RISK_COST_MULT)})
                continue

            vr = volume_ratio(ci)
            vol_hot = vr is not None and vr > Decimal("1.5")
            rank = (base_rank + (20 if swept else 0) + (15 if vol_hot else 0)
                    + (15 if rr >= GOOD_RR else 0))
            conf = confluence_block(direction, ci, created, bct, swept,
                                    ((tp_uncapped - entry) if direction == "LONG"
                                     else (entry - tp_uncapped)) / risk)
            if conf.get("htf_regime_aligned"):
                rank = min(100, rank + 10)

            verb = "pullback into" if strategy == "PULLBACK" else "reversal off"
            side_word = "above" if direction == "LONG" else "below"
            why = (f"{reg} regime · {verb} {created['zone_type']} zone "
                   f"{float(bottom):,.2f}-{float(top):,.2f}"
                   + (" · liquidity sweep nearby" if swept else "")
                   + f" · confirmed by a close back {side_word} the zone"
                   + (f" on {vr}x volume" if vol_hot else "")
                   + (f" · {htf} agrees" if conf.get("htf_regime_aligned") else "")
                   + f" · TP {float(tp):,.2f} · R:R {rr}")
            payload = {"setup_id": setup_id,
                       "strategy": strategy, "direction": direction,
                       "entry": str(entry), "sl": str(sl), "tp": str(tp),
                       "tp_uncapped": str(tp_uncapped),
                       "rr": str(rr), "rank": rank, "why": why,
                       "zone_id": zone_id, "regime": reg, "state": "VALIDATED",
                       "entry_model": ENTRY_MODEL,
                       "confirmed_bar_ts": cb["open_ts"],
                       "confirm_bars_waited": ci - i0,
                       "confluence": conf,
                       "manifest_hash": manifest_hash,
                       "cost_manifest_hash": cost_manifest_hash,
                       "size_units": None, "risk_usd": None,
                       "notional_usd": None, "implied_leverage": None,
                       "risk_decision": None, "risk_reasons": [],
                       "armed": False,
                       "armed_at": bct,
                       "expiry_bar_count": ENTRY_MAX_BARS,
                       "expires_at_ts": bct + ENTRY_MAX_BARS * tf_seconds}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=cb["open_ts"], confirmed_at=bct,
                                 algo_version=SETUP_VERSION, payload=payload):
                n_setups += 1
            if broken and broken["confirmed_at"] > bct:
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                     market_time=broken["market_time"],
                                     confirmed_at=broken["confirmed_at"],
                                     algo_version=SETUP_VERSION,
                                     payload={**payload, "state": "EXPIRED"}):
                    n_expired += 1

        con.commit()
        rec.n_new_facts = (n_setups + n_expired + n_forming + n_cancelled
                           + n_rejected + n_confirming + n_unconfirmed)
        # Confirmation yield is THE diagnostic for this version: too low and the
        # rule has choked throughput, too high and it is not filtering anything.
        # Recording it per run means the answer is in the run log, not inferred.
        yield_den = n_setups + n_unconfirmed
        rec.notes = (f"cost_rejected={n_cost_rejected} confirming={n_confirming} "
                     f"confirmed={n_setups} unconfirmed={n_unconfirmed} "
                     f"yield={(n_setups / yield_den):.0%}" if yield_den else
                     f"cost_rejected={n_cost_rejected} no_candidates")
        return {"symbol": symbol, "tf": tf, "setups": n_setups,
                "expired": n_expired, "cost_rejected": n_cost_rejected,
                "forming": n_forming, "cancelled": n_cancelled,
                "rejected": n_rejected, "confirming": n_confirming,
                "unconfirmed": n_unconfirmed}
