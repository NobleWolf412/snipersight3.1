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

SETUP_VERSION = "setup-v0.6-draft"
# v0.5: FORMING state (accepted S14 recommendation) — price approaching an
# active zone (within PROX_ATR of the edge, 4H/1D/1W only) with regime
# aligned AND the prospective trade passing the same R:R + fee gates emits a
# FORMING fact: early context, zero trade logic. Upgrades to VALIDATED on
# touch (same setup_id when regime holds); zone broken untouched -> CANCELLED.
FORMING_TFS = ("4H", "1D", "1W")
PROX_ATR = Decimal(1)
MIN_RR = Decimal("1.5")
GOOD_RR = Decimal("2.5")
SL_ATR = Decimal("0.25")
SWEEP_LOOKBACK_BARS = 10
Q2 = Decimal("0.01")

# Cost model is an immutable profile shared with execution simulation.
COST_PROFILE = costs.DEFAULT_COST_PROFILE
SLIP_ATR = COST_PROFILE.market_slippage_atr  # compatibility for older consumers

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


def playbook(zone_type: str, reg: str | None, swept: bool = False):
    """Returns (strategy, direction, base_rank) or None if no play."""
    if zone_type == "DEMAND":
        if reg in ("BULL_TREND", "WEAKENING_BULL"):
            return "PULLBACK", "LONG", 50
        if reg == "TRANSITION" and swept:
            return "REVERSAL", "LONG", 40
    else:
        if reg in ("BEAR_TREND", "WEAKENING_BEAR"):
            return "PULLBACK", "SHORT", 50
        if reg == "TRANSITION" and swept:
            return "REVERSAL", "SHORT", 40
    return None


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "setup", SETUP_VERSION, symbol, tf) as rec:
        strategy_manifest = {
            "version": SETUP_VERSION, "min_rr": str(MIN_RR),
            "good_rr": str(GOOD_RR), "sl_atr": str(SL_ATR),
            "sweep_lookback_bars": SWEEP_LOOKBACK_BARS,
            "min_risk_cost_multiple": str(MIN_RISK_COST_MULT),
            "reversal_requires_sweep": True,
            "cost_profile": COST_PROFILE.payload(),
        }
        manifest_hash = store.record_manifest(con, "strategy", strategy_manifest)
        cost_manifest_hash = costs.record(con, COST_PROFILE)
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
        n_setups = n_expired = n_cost_rejected = n_forming = n_cancelled = 0

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
                    entry, a, COST_PROFILE):
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
                               "cost_manifest_hash": cost_manifest_hash}
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
            play = playbook(created["zone_type"], reg, swept)
            if play is None:
                continue
            strategy, direction, base_rank = play
            i = ts_index.get(touched["market_time"])
            if i is None or atr[i] is None:
                continue
            top, bottom = Decimal(created["top"]), Decimal(created["bottom"])
            if direction == "LONG":
                entry, sl = top, bottom - SL_ATR * atr[i]
            else:
                entry, sl = bottom, top + SL_ATR * atr[i]
            tp = target(direction, entry, touched["confirmed_at"])
            if tp is None:
                continue
            risk = (entry - sl) if direction == "LONG" else (sl - entry)
            reward = (tp - entry) if direction == "LONG" else (entry - tp)
            if risk <= 0:
                continue
            rr = (reward / risk).quantize(Q2)
            if rr < MIN_RR:
                continue
            est_cost = costs.estimated_round_trip_cost(entry, atr[i], COST_PROFILE)
            if risk < MIN_RISK_COST_MULT * est_cost:
                n_cost_rejected += 1
                continue

            vol_hot = False
            if i >= 20:
                avg = sum(Decimal(candles[j]["volume"]) for j in range(i - 20, i)) / 20
                vol_hot = avg > 0 and Decimal(candles[i]["volume"]) / avg > Decimal("1.5")
            rank = base_rank + (20 if swept else 0) + (15 if vol_hot else 0) + (15 if rr >= GOOD_RR else 0)

            verb = "pullback into" if strategy == "PULLBACK" else "reversal off"
            why = (f"{reg} regime · {verb} {created['zone_type']} zone "
                   f"{float(bottom):,.2f}-{float(top):,.2f}"
                   + (" · liquidity sweep nearby" if swept else "")
                   + (" · high volume at touch" if vol_hot else "")
                   + f" · TP at {'pool' if pools else 'swing'} {float(tp):,.2f} · R:R {rr}")
            payload = {"setup_id": f"{symbol}|{tf}|{strategy}|{zone_id}",
                       "strategy": strategy, "direction": direction,
                       "entry": str(entry), "sl": str(sl), "tp": str(tp),
                       "rr": str(rr), "rank": rank, "why": why,
                       "zone_id": zone_id, "regime": reg, "state": "VALIDATED",
                       "manifest_hash": manifest_hash,
                       "cost_manifest_hash": cost_manifest_hash}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=touched["market_time"],
                                 confirmed_at=touched["confirmed_at"],
                                 algo_version=SETUP_VERSION, payload=payload):
                n_setups += 1
            broken = z.get("BROKEN")
            if broken:
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                     market_time=broken["market_time"],
                                     confirmed_at=broken["confirmed_at"],
                                     algo_version=SETUP_VERSION,
                                     payload={**payload, "state": "EXPIRED"}):
                    n_expired += 1

        con.commit()
        rec.n_new_facts = n_setups + n_expired + n_forming + n_cancelled
        rec.notes = f"cost_rejected={n_cost_rejected}"
        return {"symbol": symbol, "tf": tf, "setups": n_setups,
                "expired": n_expired, "cost_rejected": n_cost_rejected,
                "forming": n_forming, "cancelled": n_cancelled}
