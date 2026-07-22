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
from .swings import compute_atr, SWING_VERSION
from .runlog import RunRecorder

ZONE_VERSION = "zone-v0.9-draft"
ZONE_TIERS = ("INTERMEDIATE", "MAJOR")
ZONE_ATR = Decimal("0.25")
TICK = Decimal("0.01")
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
        n_created = n_events = 0

        swings = []
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ZONE_TIERS:
                swings.append({"market_time": r["market_time"],
                               "confirmed_at": r["confirmed_at"],
                               "type": p["type"], "price": Decimal(p["price"])})
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
            # cluster: other same-type anchors whose price falls inside this band
            cluster = sum(1 for m, o in enumerate(swings)
                          if m != k and bands[m] is not None and bands[m][0] == kind_z
                          and bottom <= o["price"] <= top)
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
                tol = max(TICK, TOL_ATR * atr[j]) if atr[j] is not None else TICK
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
