"""Zone engine — supply/demand zones with lifecycle + strength. algo zone-v0.8-draft.

Draft methodology (pending §30 item 7 and Item C zone-creation predicates):
- Creation: every INTERMEDIATE+ swing anchors a zone. Demand at a swing LOW:
  [low, low + 0.25*ATR]; supply at a swing HIGH: [high - 0.25*ATR, high].
  Zone exists from the swing's confirmed_at (§5).
- Lifecycle (spec §23): FRESH -> TOUCHED (1st touch episode) -> TESTED (2nd)
  -> WEAKENED (3rd+) -> BROKEN (close beyond far edge by tolerance).
  A touch EPISODE = price entering the band after having been outside it —
  consecutive bars inside count once. Episodes capped at 10 facts per zone.
  FLIP still deferred to §30 item 7 (P-ZN-FLIP is a user methodology call).
- Strength (0-100, evidence not filter — ported concept from user's prior
  project, ATR-relative and deterministic here): touch episodes, cluster
  membership (other same-type anchors inside this band), age, timeframe
  weight. Recomputed and stored on every lifecycle event as-of that moment.
- Append-only: each transition is its own fact referencing zone_id; broken
  zones keep their history (§23: state changes, never deletes).
"""
import json
from decimal import Decimal

from . import store
from .swings import compute_atr, SWING_VERSION, quote_ticks
from .runlog import RunRecorder

ZONE_VERSION = "zone-v0.13-draft"
# v0.13: the v0.12 anchor collapse keyed on market_time ALONE, and one bar can
# legitimately host BOTH a promoted HIGH and a promoted LOW — the 2025-10-10
# crash bar carries a MAJOR pair on three symbols. The later row shadowed its
# twin, so five supply zones store-wide were never created. A pivot's identity
# is (market_time, type); caught in the first live v0.12 cycle.
# v0.12: cascade from swing-v0.9. v0.8 swings re-emitted every promoted pivot
# every cycle (held_candles accrued inside the hashed payload), and this
# engine's cluster count treated each copy as a distinct neighbour — so
# formation_quality, and therefore strength, WHICH GATES REVERSAL, inflated
# monotonically as the scanner ran. The anchor read now also collapses to one
# row per pivot, so a legitimately revised pivot (sequence-tail revision, 63
# groups measured in the v0.8 store) counts once, not per revision. Promotion
# confirmed_at moved too (held window close), so zones are born later and their
# creation-time cluster counts change.
# v0.11: LOOKAHEAD CLOSED. The creation-time cluster count included swings that
# were not yet confirmed, so `formation_quality` — and therefore `strength`,
# which gates the REVERSAL playbook — was computed from the future on 7.9% of
# zones, inflated every time. Now filtered on `confirmed_at <= zone's own`.
# v0.10: the zone break tolerance was max(TICK, 0.05*ATR) with TICK hard-coded
# to 0.01 — right for BTC-USD, catastrophically wrong below a dollar, where a
# tolerance wider than any move the instrument makes means no close ever breaks
# the far edge and a zone can never leave FRESH by breaking. The tick is now
# derived per bar from the exponent of the venue's own price strings;
# `swings.quote_ticks` is the single definition of it and carries the
# measurement. Same rule, implemented honestly — it returns exactly 0.01
# wherever 0.01 was right, so majors' zone facts are unchanged.

ZONE_TIERS = ("INTERMEDIATE", "MAJOR")
ZONE_ATR = Decimal("0.25")
TOL_ATR = Decimal("0.05")
MAX_TOUCH_FACTS = 10

TF_WEIGHT = {"1W": 20, "1D": 15, "4H": 10, "1H": 5, "15m": 5}


def formation_quality(cluster: int, tf: str) -> int:
    """Immutable creation quality; mitigation must never increase it."""
    return min(100, 50 + min(30, cluster * 10) + TF_WEIGHT.get(tf, 5))


def freshness(episodes: int, age_bars: int, broken: bool = False) -> int:
    """Remaining zone freshness decays with mitigation and age."""
    if broken:
        return 0
    mitigation_decay = episodes * 25
    age_decay = min(25, age_bars // 100)
    return max(0, 100 - mitigation_decay - age_decay)


def strength(quality: int, remaining_freshness: int) -> int:
    return (quality + remaining_freshness) // 2


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "zone", ZONE_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)
        n_created = n_events = 0

        # One anchor per pivot, LATEST row winning (get_facts orders by
        # market_time, confirmed_at, id) — a revised pivot is one swing, not two,
        # and the cluster count below counts anchors. Identity is
        # (market_time, TYPE): one bar can host both a promoted HIGH and a
        # promoted LOW, and each anchors its own zone.
        latest = {}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ZONE_TIERS:
                latest[(r["market_time"], p["type"])] = {
                    "market_time": r["market_time"],
                    "confirmed_at": r["confirmed_at"],
                    "type": p["type"], "price": Decimal(p["price"])}
        swings = list(latest.values())
        rec.n_inputs = len(swings)

        # precompute bands so cluster membership is knowable per zone
        bands = []
        for s in swings:
            i = ts_index.get(s["market_time"])
            if i is None or atr[i] is None:
                bands.append(None)
                continue
            width = ZONE_ATR * atr[i]
            if s["type"] == "LOW":
                bands.append(("DEMAND", s["price"], s["price"] + width))
            else:
                bands.append(("SUPPLY", s["price"] - width, s["price"]))

        for k, s in enumerate(swings):
            if bands[k] is None:
                continue
            kind_z, bottom, top = bands[k]
            i = ts_index[s["market_time"]]
            # Cluster: other same-type anchors whose price falls inside this
            # band AND which were already knowable when this zone was created.
            #
            # The `confirmed_at` filter was missing, so the count included
            # swings that had not happened yet — and the fact is written with
            # `confirmed_at = s["confirmed_at"]`, meaning a fact stamped at time
            # T carried a value derived from information that only existed after
            # T. That is the causality rule this project is built on, broken in
            # the engine that feeds the strategy layer.
            #
            # Measured before the fix, 12 symbols x 4H/1D/1W, 2,006 zones: 159
            # (7.9%) counted future swings, and 96 of those got a different
            # formation_quality — inflated in every single case, never
            # deflated. Worst observed: a zone rated 90 on a cluster of 18, of
            # which ZERO were knowable at its own creation time.
            cluster = sum(1 for m, o in enumerate(swings)
                          if m != k and bands[m] is not None and bands[m][0] == kind_z
                          and bottom <= o["price"] <= top
                          and o["confirmed_at"] <= s["confirmed_at"])
            zone_id = f"{symbol}|{tf}|{kind_z}|{s['market_time']}"
            base = {"zone_id": zone_id, "zone_type": kind_z,
                    "bottom": str(bottom), "top": str(top),
                    "anchor_swing_ts": s["market_time"], "cluster_members": cluster}
            quality = formation_quality(cluster, tf)
            fresh = freshness(0, 0)
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="zone",
                                 market_time=s["market_time"],
                                 confirmed_at=s["confirmed_at"],
                                 algo_version=ZONE_VERSION,
                                 payload={**base, "event": "CREATED", "state": "FRESH",
                                          "formation_quality": quality,
                                          "freshness": fresh,
                                          "strength": strength(quality, fresh)}):
                n_created += 1

            episodes = 0
            inside = False
            for j in range(i + 1, len(candles)):
                c = candles[j]
                bar_close_ts = c["open_ts"] + tf_seconds
                if bar_close_ts <= s["confirmed_at"]:
                    continue
                hi, lo, close = Decimal(c["high"]), Decimal(c["low"]), Decimal(c["close"])
                tol = max(ticks[j], TOL_ATR * atr[j]) if atr[j] is not None else ticks[j]
                broken = (close < bottom - tol) if kind_z == "DEMAND" else (close > top + tol)
                if broken:
                    fresh = freshness(episodes, j - i, broken=True)
                    if store.insert_fact(con, symbol=symbol, tf=tf, kind="zone",
                                         market_time=c["open_ts"], confirmed_at=bar_close_ts,
                                         algo_version=ZONE_VERSION,
                                         payload={**base, "event": "BROKEN", "state": "BROKEN",
                                                  "episodes": episodes,
                                                  "formation_quality": quality,
                                                  "freshness": fresh,
                                                  "strength": strength(quality, fresh)}):
                        n_events += 1
                    break
                overlap = lo <= top and hi >= bottom
                if overlap and not inside:
                    episodes += 1
                    if episodes <= MAX_TOUCH_FACTS:
                        state = ("TOUCHED" if episodes == 1 else
                                 "TESTED" if episodes == 2 else "WEAKENED")
                        fresh = freshness(episodes, j - i)
                        if store.insert_fact(con, symbol=symbol, tf=tf, kind="zone",
                                             market_time=c["open_ts"], confirmed_at=bar_close_ts,
                                             algo_version=ZONE_VERSION,
                                             payload={**base, "event": "TOUCH", "state": state,
                                                      "episode": episodes,
                                                      "formation_quality": quality,
                                                      "freshness": fresh,
                                                      "strength": strength(quality, fresh)}):
                            n_events += 1
                inside = overlap

        con.commit()
        rec.n_new_facts = n_created + n_events
        return {"symbol": symbol, "tf": tf, "created": n_created, "events": n_events}
