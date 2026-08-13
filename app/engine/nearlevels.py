"""Where price is standing at a level, across the whole tradeable universe.
Read-only: writes no facts, mutates nothing (§1).

## The gap this fills

`draft.py` answers "is price near a zone on THIS chart" — for one symbol and
one timeframe, because the ticket asks it the moment an operator opens a chart.
Nothing ever asked it of the universe. So the only way to find out where price
was actually sitting was to open charts one at a time, and an operator doing
that ends up drafting a bracket on a market the engine has never looked at and
reading it as the engine's plan. Measured 2026-08-05: LINKUSDT 1D drew a
LONG bracket off a demand zone 2.46 ATR away, while the engine's own attention
stops at 1 ATR and it had zero validated setups on that symbol all baseline.

## What this is NOT

It is not a setup list and it never becomes one. The Setup Deck is the engine's
plans; the "Approaching" panel is the engine's own FORMING signal — a candidate
it has already accepted and is waiting on. This is neither. A row here says only
that price is near a zone and here is the bracket the ticket would draw, which
is exactly as much as `draft.py` claims and no more.

The distinction is load-bearing, so it is carried in the data rather than left
to a caption: every row is stamped with `engine_reach`, which says whether the
engine is even looking at that zone. Three horizontal price lines outweigh any
caption — the same lesson `chart.js` learned when a seeded bracket was captioned
as manual and drawn as engine output anyway.

## Why it calls draft.py instead of restating the geometry

One authority per number (§6). The distance, the bracket and the basis a row
shows are the SAME call the ticket makes on that chart, so a row here and the
chart it points at cannot disagree. Restating the zone search would create a
second answer to "how far is price from that level", and two answers is how the
equity number diverged on 2026-07-26.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from . import draft, setups, universe

#: Every timeframe the scanner derives structure on, nearest-term first in the
#: order the rest of the app lists them. Not `setups.FORMING_TFS` — that is the
#: narrower set the engine will FORM a setup on, and the difference between the
#: two is a fact this module exists to report rather than to hide by filtering.
TIMEFRAMES = ("5m", "15m", "1H", "4H", "1D", "1W")

#: Price is inside the zone's band. `setups.py` breaks out of its forming loop
#: at `dist <= 0` and hands the zone to the TOUCH -> CONFIRMING path, so this is
#: not "as close as it gets to forming" — it is a different route entirely.
AT_ZONE = "AT_ZONE"
#: Inside `setups.PROX_ATR` on a timeframe the engine forms setups on. Necessary
#: and NOT sufficient: `playbook()` must also cover the regime, and 91 of the
#: 122 candidates examined in the current window died on exactly that.
IN_RANGE = "IN_RANGE"
#: Inside the distance bound but on a timeframe outside `setups.FORMING_TFS`.
#: The engine will not announce this one in advance at all; it only reacts once
#: price actually reaches the zone.
NO_FORMING_ON_TF = "NO_FORMING_ON_TF"
#: Beyond `setups.PROX_ATR`. The engine is not considering this zone. The
#: bracket is the ticket's, and calling it the engine's would be the misreading
#: this whole module was written to prevent.
OUT_OF_RANGE = "OUT_OF_RANGE"


def engine_reach(tf: str, distance_atr: Decimal) -> str:
    """Where this row stands relative to the engine's own attention.

    Mirrors the gates in `setups.py`'s forming loop and nothing else: the
    timeframe check (`FORMING_TFS`), the `dist <= 0` break, and the
    `dist > PROX_ATR * atr` skip. Deliberately does NOT model `playbook()` —
    whether a strategy covers the condition depends on regime and sweep state
    at the bar, and guessing at it here would put a second, worse answer beside
    the engine's own.
    """
    if distance_atr <= 0:
        return AT_ZONE
    if distance_atr > setups.PROX_ATR:
        return OUT_OF_RANGE
    if tf not in setups.FORMING_TFS:
        return NO_FORMING_ON_TF
    return IN_RANGE


def _distance(row: dict) -> Decimal | None:
    try:
        return Decimal(str(row["distance_atr"]))
    except (KeyError, TypeError, InvalidOperation):
        return None


def sweep(con, *, timeframes: tuple[str, ...] = TIMEFRAMES) -> dict:
    """Every tradeable symbol/timeframe where price is within draft reach.

    Scans the TRADEABLE universe only. A shadow symbol is carried to keep a
    venue warm and `risk.py` refuses to size one at any time, so a row for it
    would be a level nobody can trade — but the count is reported rather than
    silently dropped, because a list that cannot say what it left out is the
    same defect `/api/edge-stats` had.
    """
    tradeable = universe.current_symbols(con)
    shadow = universe.shadow_symbols(con)

    rows: list[dict] = []
    warnings: list[str] = []
    counts = {"symbols": len(tradeable), "shadow_excluded": len(shadow),
              "pairs": 0, "no_structure": 0, "errored": 0}

    for symbol in tradeable:
        for tf in timeframes:
            counts["pairs"] += 1
            try:
                d = draft.for_symbol(con, symbol, tf)
            except Exception as exc:                 # noqa: BLE001
                # Audible, never silent (§4). A symbol whose structure cannot
                # be read is missing from this list, and a list that quietly
                # drops rows reads as "price is not near anything there".
                counts["errored"] += 1
                warnings.append(
                    f"{symbol} {tf}: structure could not be read "
                    f"({type(exc).__name__}) — this market is missing from the "
                    f"list rather than known to be far from a level")
                continue
            if d is None:
                counts["no_structure"] += 1
                continue
            dist = _distance(d)
            if dist is None:
                counts["errored"] += 1
                warnings.append(
                    f"{symbol} {tf}: draft returned no distance — row dropped")
                continue
            rows.append({"symbol": symbol, "tf": tf,
                         "engine_reach": engine_reach(tf, dist), **d})

    # Nearest first, then the order the app lists timeframes in, so two markets
    # sitting the same distance out do not swap places between polls.
    tf_order = {t: i for i, t in enumerate(timeframes)}
    rows.sort(key=lambda r: (_distance(r), tf_order.get(r["tf"], 99), r["symbol"]))

    counts["found"] = len(rows)
    counts["in_engine_range"] = sum(
        1 for r in rows if r["engine_reach"] in (AT_ZONE, IN_RANGE))
    counts["markets_in_engine_range"] = len({
        r["symbol"] for r in rows
        if r["engine_reach"] in (AT_ZONE, IN_RANGE)
    })
    return {
        # Sent so the client never hard-codes either bound. The meter on the
        # Approaching panel was scaled against the wrong one of these two
        # constants and encoded nothing for it; the fix was to put the number
        # on the payload, and this follows that.
        "prox_atr": str(setups.PROX_ATR),
        "max_distance_atr": str(draft.MAX_DISTANCE_ATR),
        "forming_tfs": list(setups.FORMING_TFS),
        "timeframes": list(timeframes),
        "counts": counts,
        "warnings": warnings,
        "rows": rows,
    }
