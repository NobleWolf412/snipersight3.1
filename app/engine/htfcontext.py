"""Higher-timeframe context for one trade, for the operator to READ.

A LIBRARY, not an engine: writes no facts, arms nothing, gates nothing. It
answers the question a trader asks before taking a lower-timeframe entry —
"am I standing in front of a bigger move, and where is the liquidity it is
heading for?" — from facts the store already holds.

WHY A SEPARATE MODULE. `htfread` already has a pool search, but it answers a
different question and it feeds a stored study's grade: it looks only on the
trade's TARGET side, only two rungs up, and it treats a pool that has been
swept as untouched. Changing it would silently move that study's numbers. So
the operator's reading lives here, and `htfread` stays exactly as graded.

THREE READINGS, each labelled as what it is, never folded into one number:

  1. The ladder, rung by rung, from `regimeread` phases — not from the older
     structural label. A market ripping upward without a higher low still
     reads FLAT on the structural ladder (it is a TRANSITION the whole way
     up); its phase reads IMPULSE_UP. `bias.permitted` consults the phase for
     exactly that reason, and so does this.
  2. Liquidity pools against the trade (for a short, the equal highs ABOVE;
     for a long, the equal lows BELOW) and toward it, nearest per rung, with
     whether each has already been swept.
  3. Support and resistance from the chart read — a different model from
     liquidity, reported separately and never merged with it.

The ladder stops at DAILY (operator ruling 2026-09-18). Weekly history is thin
on most perps and would usually read "not available".

NOT A GATE. Refusing trades on higher-timeframe direction was tried in this
system and removed the better half of the results — most reversal winners are
counter-trend by design. `stance` describes; nothing reads it to decide. Any
future gate on it is a measured, versioned change (rule 7).
"""
from __future__ import annotations

import json
from decimal import Decimal

from . import bias, chartread, importer, regimeread, store
from .liquidity import LIQ_VERSION

#: The highest rung the operator's check walks to.
TOP = "1D"

Q2 = Decimal("0.01")

#: Plain English for every phase `regimeread.phase_of` can return.
PHASE_WORDS = {
    "TREND_UP": "trending up",
    "TREND_DOWN": "trending down",
    "TREND_UP_EXTENDED": "trending up, stretched far past its last break",
    "TREND_DOWN_EXTENDED": "trending down, stretched far past its last break",
    "IMPULSE_UP": "running up hard",
    "IMPULSE_DOWN": "falling hard",
    "TURN_UP": "just turned up",
    "TURN_DOWN": "just turned down",
    "DRIFT_UP": "drifting up, momentum faded",
    "DRIFT_DOWN": "drifting down, momentum faded",
    "RANGE": "ranging",
    "UNKNOWN": "not enough history",
}

_WANT = {"LONG": "UP", "SHORT": "DOWN"}


def rungs(tf: str) -> tuple:
    """Every timeframe above `tf`, nearest first, stopping at TOP inclusive.

    A daily setup therefore has no rungs: the check stops at daily, and the
    panel says so rather than reaching for a weekly it was told not to use.
    """
    out = []
    for r in bias.rungs_above(tf):
        if importer.TF_SECONDS.get(r) is None:
            continue
        if importer.TF_SECONDS[r] > importer.TF_SECONDS[TOP]:
            break
        out.append(r)
    return tuple(out)


def strength(phase: str | None) -> str | None:
    """STRONG for a trend or an impulse, LEANING for a turn or a drift.

    The same split `bias._DIRECTIONAL_PHASES` makes: trend and impulse are a
    known direction now; a fresh turn or an aged drift has a direction but not
    the energy to call it a trend.
    """
    if not phase:
        return None
    if phase.startswith(("TREND_", "IMPULSE_")):
        return "STRONG"
    if phase.startswith(("TURN_", "DRIFT_")):
        return "LEANING"
    return None


def stance(direction: str, ladder: list) -> dict:
    """Where a trade stands against the rungs above it. A description.

    `ladder` is `[{"tf", "phase"}]`. The dangerous case is named on its own:
    counter-trend is Reversal's normal case, but counter-trend into a move
    that is still RUNNING (an impulse on a rung above) is the one this
    system's own records flag — so it is never folded into plain
    "counter-trend".
    """
    want = _WANT[direction]
    strong_with, strong_against, running_against, leaning = [], [], [], []
    for rung in ladder:
        phase, side = rung.get("phase"), regimeread.phase_side(rung.get("phase") or "")
        if side is None:
            continue
        s = strength(phase)
        if s == "LEANING":
            leaning.append(rung["tf"])
            continue
        (strong_with if side == want else strong_against).append(rung["tf"])
        if side != want and phase.startswith("IMPULSE_"):
            running_against.append(rung["tf"])

    def names(tfs):
        return _join([_tf_word(t) for t in tfs])

    if not ladder:
        return {"label": "NO_HIGHER_TIMEFRAME",
                "sentence": "No higher timeframe up to daily to check against."}
    # A missing measurement is not a market condition. Every rung unread is
    # its own answer, never "ranging" — the same rule setups.confluence_block
    # keeps for UNKNOWN versus OPPOSED.
    if all(r.get("phase") in (None, "UNKNOWN") for r in ladder):
        return {"label": "NOT_ENOUGH_HISTORY",
                "sentence": "Not enough higher-timeframe history to read yet."}
    if running_against:
        moving = "running up hard" if want == "DOWN" else "falling hard"
        sentence = (f"Counter-trend into a move that is still running: "
                    f"the {names(running_against)} "
                    f"{'is' if len(running_against) == 1 else 'are'} {moving}.")
        # Never drop the other half of a split picture. Measured on the first
        # live read (PF_SUIUSD 15m short, 2026-09-18): 1H running up hard and
        # the daily trending DOWN, with the trade. The warning is the headline;
        # the timeframe on the trade's side still belongs in the sentence.
        if strong_with:
            sentence += (f" The {names(strong_with)} "
                         f"{'is' if len(strong_with) == 1 else 'are'} with this trade.")
        return {"label": "COUNTER_INTO_RUNNING_MOVE", "timeframes": running_against,
                "with": strong_with, "sentence": sentence}
    if strong_against and not strong_with:
        return {"label": "COUNTER_TREND", "timeframes": strong_against,
                "sentence": f"Counter-trend on the {names(strong_against)}."}
    if strong_with and not strong_against:
        return {"label": "WITH_TREND", "timeframes": strong_with,
                "sentence": f"With the trend on the {names(strong_with)}."}
    if strong_with and strong_against:
        return {"label": "MIXED", "timeframes": strong_with + strong_against,
                "sentence": f"Higher timeframes disagree: the {names(strong_with)} "
                            f"with this trade, the {names(strong_against)} against it."}
    if leaning:
        return {"label": "NO_CLEAR_TREND", "timeframes": leaning,
                "sentence": "No clear trend above: the "
                            f"{names(leaning)} {'has' if len(leaning) == 1 else 'have'} "
                            "turned or drifted but not trended."}
    return {"label": "NO_CLEAR_TREND",
            "sentence": "No clear trend above: the higher timeframes are ranging "
                        "or have too little history."}


def _tf_word(tf: str) -> str:
    return "daily" if tf == "1D" else tf


def _join(words: list) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def ladder_now(con, symbol: str, tf: str, as_of: int) -> list:
    """Each rung's phase as of `as_of`, from facts confirmed by then."""
    out = []
    for rung in rungs(tf):
        read = regimeread.load(con, symbol, rung, importer.TF_SECONDS[rung]).at(as_of)
        phase = read.get("phase") if read.get("regime") is not None else "UNKNOWN"
        out.append({"tf": rung, "phase": phase,
                    "words": PHASE_WORDS.get(phase, phase.lower().replace("_", " "))})
    return out


def load_pools(con, symbol: str, tfs) -> dict:
    """Every pool per rung, with when it was broken and whether it was swept.

    Two passes so an event is never read before its pool. `liquidity` records
    at most one SWEEP per pool before a BROKEN ends it, so "swept" is yes or
    no — not a count, and the panel does not pretend otherwise.
    """
    out = {}
    for rung in tfs:
        rows = [(r["confirmed_at"], json.loads(r["payload"]))
                for r in store.get_facts(con, symbol, rung, "liquidity", LIQ_VERSION)]
        pools = {}
        for at, p in rows:
            if p.get("event") == "POOL":
                pools[p["pool_id"]] = {"tf": rung, "side": p["side"],
                                       "level": Decimal(p["level"]),
                                       "members": p.get("n_members"),
                                       "confirmed_at": at, "broken_at": None,
                                       "swept_at": None}
        for at, p in rows:
            pool = pools.get(p.get("pool_id"))
            if pool is None:
                continue
            if p.get("event") == "BROKEN":
                pool["broken_at"] = at
            elif p.get("event") == "SWEEP" and pool["swept_at"] is None:
                pool["swept_at"] = at
        out[rung] = list(pools.values())
    return out


def _live(pool, as_of):
    return (pool["confirmed_at"] <= as_of
            and (pool["broken_at"] is None or pool["broken_at"] > as_of))


def _distance(level: Decimal, price: Decimal, atr) -> dict:
    gap = abs(level - price)
    return {"distance_pct": str((gap / price * 100).quantize(Q2)) if price else None,
            "distance_atr": (str((gap / atr).quantize(Q2))
                             if atr not in (None, 0) else None)}


def pools_around(pools_by_rung: dict, direction: str, price, as_of: int, atr=None) -> dict:
    """Nearest live pool per rung AGAINST the trade and TOWARD it.

    Against a short is the equal-highs pool ABOVE price — buy-stop liquidity a
    squeeze runs to take. Against a long is the equal-lows pool BELOW. Toward
    is the mirror: where the trade would be paid if it is right.
    """
    price = Decimal(str(price))
    above, below = [], []
    for rung, pools in pools_by_rung.items():
        live = [p for p in pools if _live(p, as_of)]
        ups = [p for p in live if p["side"] == "HIGH" and p["level"] > price]
        downs = [p for p in live if p["side"] == "LOW" and p["level"] < price]
        if ups:
            above.append(min(ups, key=lambda p: p["level"]))
        if downs:
            below.append(max(downs, key=lambda p: p["level"]))

    def show(p):
        swept = p["swept_at"] is not None and p["swept_at"] <= as_of
        # "No sweep recorded", never "untouched". Two things the record cannot
        # see (cold audit, 2026-09-18): a pool is read from COMPLETED candles
        # on its own timeframe, so a daily candle still forming may already
        # have run it; and `liquidity` records a sweep only on a close back
        # inside and a break only on a close beyond its tolerance, so a candle
        # that trades through and closes just past the level records neither.
        return {"tf": p["tf"], "level": str(p["level"]), "members": p["members"],
                "swept": swept,
                "status": (f"swept once, by a closed {p['tf']} candle" if swept
                           else f"no sweep recorded by the last closed {p['tf']} candle"),
                **_distance(p["level"], price, atr)}

    against = above if direction == "SHORT" else below
    toward = below if direction == "SHORT" else above
    # Which rungs carry any liquidity record at all. Without it, "the engine
    # never produced a pool here" and "it did, and none is in the way" both
    # read as "none found" — and a sort by room before a pool would rank an
    # unmeasured market as the safest.
    return {"against": [show(p) for p in against],
            "toward": [show(p) for p in toward],
            "measured": [rung for rung, pools in pools_by_rung.items() if pools]}


def levels_around(con, symbol: str, tf: str, price, as_of: int, atr=None) -> list:
    """Nearest support below and resistance above per rung, from `chartread`.

    Support/resistance is a price that has been touched repeatedly — a
    different model from liquidity pools, reported under its own heading.
    Loads each rung's full candle history, so it belongs on a single setup's
    view, never in a list.
    """
    price = Decimal(str(price))
    out = []
    for rung in rungs(tf):
        read = chartread.load(con, symbol, rung, importer.TF_SECONDS[rung]).at(as_of)
        res = [l for l in read.get("resistance", []) if Decimal(l["price"]) > price]
        sup = [l for l in read.get("support", []) if Decimal(l["price"]) < price]
        r = min(res, key=lambda l: Decimal(l["price"])) if res else None
        s = max(sup, key=lambda l: Decimal(l["price"])) if sup else None
        out.append({
            "tf": rung,
            "resistance": None if r is None else {
                "price": r["price"], "touches": r["touches"],
                **_distance(Decimal(r["price"]), price, atr)},
            "support": None if s is None else {
                "price": s["price"], "touches": s["touches"],
                **_distance(Decimal(s["price"]), price, atr)},
        })
    return out


def read(con, symbol: str, tf: str, direction: str, price, as_of: int,
         atr=None, levels: bool = True) -> dict:
    """The whole panel for one trade, as of `as_of`.

    `levels=False` skips the chart read, which loads full candle history per
    rung and is too heavy for a list of trades.
    """
    ladder = ladder_now(con, symbol, tf, as_of)
    out = {"as_of": as_of, "top": TOP, "ladder": ladder,
           "stance": stance(direction, ladder),
           "pools": pools_around(load_pools(con, symbol, rungs(tf)),
                                 direction, price, as_of, atr)}
    if levels:
        out["levels"] = levels_around(con, symbol, tf, price, as_of, atr)
    return out
