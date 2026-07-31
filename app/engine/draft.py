"""Structure-anchored DRAFT bracket for the order ticket. Writes nothing.

## What this replaces, and why it is not an engine

When the chart has no engine setup, the ticket used to seed levels from
`last close ± average 14-bar range`, always LONG. That number consulted no
zone, no structure, no regime and no liquidity — it was a ruler laid around the
current price to produce a 2:1 shape. On 48 of the 78 symbols in the picker
that is the only thing an operator ever sees, because the scanner does not scan
them.

This composes a starting point out of facts that already exist instead: the
nearest live zone for the entry, its far edge for the stop, the nearest
unbroken opposing liquidity pool for the target.

**It is emphatically NOT a setup and never becomes one.** It writes no facts,
it has no version, no consumer reads it, and nothing it produces can reach the
graded record. It exists so that when the operator drags a level, they are
adjusting something anchored to the market rather than to arithmetic. Every
result carries `basis` — the plain-English list of what it used — so the ticket
can say what the draft is standing on, which the ruler never could.

## Why the bracket rules are restated rather than imported

`setups.py` builds its bracket inline inside `run()`; there is no function to
call. Extracting one would mean refactoring a version-locked engine on the
trading path for the sake of a UI helper, and any behaviour change there
cascades through `exec`, `risk`, `scale` and `cooldown`. So these rules are
DELIBERATELY a separate, simpler statement — and because they are separate,
this module must never be described as "what the engine would do". It is a
draft. The engine's answer is a setup fact, and its absence is itself the
answer this draft exists to make workable.

The shapes are borrowed honestly, though: entry at the zone edge nearest price
and a stop beyond the far edge are the same geometry `setups.py` uses, so a
draft and a real setup on the same zone land in the same neighbourhood rather
than describing two different trades.
"""
import json
from decimal import Decimal

from . import store, venues
from .zones import ZONE_VERSION, ZONE_ATR
from .liquidity import LIQ_VERSION
from .swings import compute_atr

#: Buffer beyond the zone's far edge, mirroring `setups.SL_ATR`. A stop exactly
#: on the edge is inside the noise of the level it is meant to survive.
SL_ATR = Decimal("0.25")
#: How far from price a zone may sit and still be worth drafting against.
#: Beyond this the "nearest" zone is not a level price is trading at, it is a
#: level somewhere else, and anchoring to it would be worse than saying nothing.
MAX_DISTANCE_ATR = Decimal(3)
#: Fallback reward multiple when no opposing pool exists to aim at. Declared
#: rather than hidden: 2R is a convention, not a measurement.
FALLBACK_RR = Decimal(2)


def _latest_by_id(rows: list, id_key: str) -> list[dict]:
    """Last recorded state per object. Facts are append-only, so a zone appears
    once per lifecycle transition and only the newest one describes it now."""
    out: dict[str, dict] = {}
    for r in rows:
        p = json.loads(r["payload"])
        out[p[id_key]] = p
    return list(out.values())


def bracket(zones: list[dict], pools: list[dict], atr: Decimal,
            price: Decimal, allow_shorts: bool = True) -> dict | None:
    """Draft entry/stop/target from live structure, or None if there is none.

    Returning None is a real answer and the caller must be able to say it:
    "price is not near anything this system recognises" is more useful than a
    bracket drawn around a level 9 ATR away.
    """
    if atr is None or atr <= 0 or price is None or price <= 0:
        return None
    live = [z for z in zones if z.get("state") != "BROKEN"]
    limit = MAX_DISTANCE_ATR * atr

    best = None                      # (distance, direction, zone)
    for z in live:
        top, bottom = Decimal(z["top"]), Decimal(z["bottom"])
        # Distance is ZERO when price is inside the band, which is the case
        # that matters most — price sitting in a demand zone is a live touch,
        # exactly the moment a draft is worth having. The first version tested
        # `top <= price`, so a zone price was standing in matched neither
        # branch and the draft declined precisely when it was most useful.
        # Price must still be at or above a demand zone's floor: below it, the
        # level did not hold and entering at its top would be chasing.
        if z.get("zone_type") == "DEMAND" and price >= bottom:
            d = max(Decimal(0), price - top)
        elif (z.get("zone_type") == "SUPPLY" and price <= top and allow_shorts):
            d = max(Decimal(0), bottom - price)
        else:
            continue
        if d > limit:
            continue
        direction = "LONG" if z["zone_type"] == "DEMAND" else "SHORT"
        if best is None or d < best[0]:
            best = (d, direction, z)
    if best is None:
        return None

    dist, direction, z = best
    top, bottom = Decimal(z["top"]), Decimal(z["bottom"])
    long = direction == "LONG"
    entry = top if long else bottom
    sl = (bottom - SL_ATR * atr) if long else (top + SL_ATR * atr)
    risk = (entry - sl) if long else (sl - entry)
    if risk <= 0:
        return None

    # Target: the nearest unbroken pool the trade would run INTO. A pool is a
    # cluster of equal highs/lows — a place resting stops are likely to sit —
    # which is why it is a plausible destination rather than an arbitrary R.
    tp, tp_basis = None, None
    for p in pools:
        if p.get("state") == "BROKEN":
            continue
        lvl = Decimal(p["level"])
        if long and p.get("side") == "HIGH" and lvl > entry:
            if tp is None or lvl < tp:
                tp, tp_basis = lvl, p.get("pool_id")
        elif not long and p.get("side") == "LOW" and lvl < entry:
            if tp is None or lvl > tp:
                tp, tp_basis = lvl, p.get("pool_id")
    if tp is None:
        tp = entry + FALLBACK_RR * risk if long else entry - FALLBACK_RR * risk
        tp_basis = None

    basis = [f"nearest live {z['zone_type']} zone "
             f"{bottom}–{top} ({z.get('state', 'FRESH')}, strength "
             f"{z.get('strength', '—')})",
             f"stop {SL_ATR} ATR beyond its far edge",
             (f"target at the nearest unbroken {'high' if long else 'low'} "
              f"liquidity pool" if tp_basis
              else f"no opposing pool in range — target defaulted to {FALLBACK_RR}R")]
    return {"direction": direction, "entry": str(entry), "sl": str(sl),
            "tp": str(tp), "zone_id": z.get("zone_id"), "pool_id": tp_basis,
            "distance_atr": str((dist / atr).quantize(Decimal("0.01"))),
            "basis": basis}


def for_symbol(con, symbol: str, tf: str) -> dict | None:
    """Draft for one symbol/timeframe, read straight from the stored facts."""
    candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
    if not candles:
        return None
    atr_series = compute_atr(candles)
    atr = next((a for a in reversed(atr_series) if a is not None), None)
    price = Decimal(candles[-1]["close"])
    zones = _latest_by_id(
        store.get_facts(con, symbol, tf, "zone", ZONE_VERSION), "zone_id")
    pools = _latest_by_id(
        store.get_facts(con, symbol, tf, "liquidity", LIQ_VERSION), "pool_id")
    try:
        allow_shorts = venues.venue_for(symbol).allow_shorts
    except ValueError:
        allow_shorts = False          # unknown instrument: refuse the riskier side
    return bracket(zones, pools, atr, price, allow_shorts)
