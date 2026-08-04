"""Fair value gaps — three-candle displacement imbalances. algo fvg-v0.1-draft.

Why this engine exists. The prior project's structural-anchor gate accepted an
FVG as one of the three level types an entry could stand on (order block, FVG,
confirmed sweep), and its entry-zone builder scored them; this codebase detects
zones and liquidity but has no gap detector at all, so the factor cannot even
be graded. That gap-in-the-evidence is the whole justification: the value is
UNKNOWN here, and unknown is measurable.

EVIDENCE, GATING NOTHING (house convention 6). No strategy consumes these
facts and none may. `setups.py`, `risk.py`, `execsim.py` and `scalein.py` do
not import this module. A factor becomes a filter only after
`engine/factorstats.py` grades it on fire rate, dispersion, contribution,
redundancy and outcome edge — and the neighbouring grading of BTC alignment
(engine/btcalign.py) is the cautionary tale in this repo's own data: the prior
project's version of THAT rule graded inverted on this book.

THE DEFINITION, and only this definition:

  A bullish FVG exists at bar i when candles[i-2].high < candles[i].low — the
  middle bar moved hard enough that the wicks around it never overlapped,
  leaving [c(i-2).high, c(i).low] untraded. Bearish mirrors it:
  candles[i-2].low > candles[i].high. The gap is the imbalance the market
  skipped; the thesis it will later be graded on is that price returning to it
  finds resting interest.

RECORDING FLOOR, not a quality filter. Gaps smaller than MIN_GAP_ATR of the
creation bar's ATR are not emitted: below that a "gap" is inside ordinary
bar-to-bar noise and would flood the store with rows describing nothing —
the same store-hygiene arithmetic that made `momentum.py` emit events rather
than per-bar values. The floor is a versioned modelling constant. Above it,
EVERYTHING is emitted with `size_atr` on the fact, so any later grading can
draw its own quality line; recording is not the place that line gets drawn.

TWO EVENT FAMILIES, nothing else:

  CREATED   knowable at bar i's close. Carries the geometry (top, bottom,
            midpoint), `size_atr`, and the displacement bar's direction.
  FILLED    the first LATER bar that trades through the gap's FAR edge — a
            bull gap is filled when some bar's low <= the gap bottom. Full
            traversal only, deliberately: "touched", "half-mitigated" and
            friends are a taxonomy of ambiguity, and each grade would spam a
            fact per touch. A gap that is never traversed simply has no FILLED
            fact — absence is the record that it held. Carries
            `fill_lag_bars`, because a gap filled two bars later and one
            filled two hundred bars later are different findings.

CAUSALITY (house convention 1). CREATED confirms at the third bar's close —
the pattern does not exist before the bar that completes it. FILLED confirms
at the filling bar's close. Nothing back-dates.

DECIMAL (house convention 3). All geometry is Decimal; `size_atr` is quantized
via `ma.sig`, scale-free, so a SHIB gap and a BTC gap carry equal resolution.

APPEND-ONLY AND IDEMPOTENT (house convention 4). Pure function of the candle
series; re-running over identical candles writes zero new facts. New candles
can only append new CREATED events and resolve open gaps into FILLED events —
nothing historical is ever restated.
"""
import json  # noqa: F401  (kept for symmetry with sibling engines' fact I/O)
from decimal import Decimal

from . import store
from .ma import plain, sig
from .runlog import RunRecorder
from .swings import compute_atr

FVG_VERSION = "fvg-v0.1-draft"

#: Recording floor, in creation-bar ATRs. Below this the "gap" is bar noise.
#: A versioned modelling constant — moving it is a new fact generation.
MIN_GAP_ATR = Decimal("0.25")


def detect(candles: list, atr: list) -> list[dict]:
    """Every qualifying gap in the series, with its fill if one ever printed.

    Pure and store-free so the geometry is testable on hand-stated bars.
    Returns dicts with: direction, created_i, top, bottom, size, size_atr,
    filled_i (None while the gap stands).
    """
    gaps: list[dict] = []
    open_gaps: list[dict] = []
    for i in range(2, len(candles)):
        # resolve standing gaps against THIS bar before detecting on it — a
        # gap cannot be filled by a bar that predates its own completion
        lo, hi = Decimal(candles[i]["low"]), Decimal(candles[i]["high"])
        still = []
        for g in open_gaps:
            filled = (lo <= g["bottom"]) if g["direction"] == "BULL" \
                else (hi >= g["top"])
            if filled:
                g["filled_i"] = i
            else:
                still.append(g)
        open_gaps = still

        if atr[i] is None or atr[i] <= 0:
            continue                        # warmup refusal: no scale, no fact
        h2, l2 = Decimal(candles[i - 2]["high"]), Decimal(candles[i - 2]["low"])
        if h2 < lo:
            direction, top, bottom = "BULL", lo, h2
        elif l2 > hi:
            direction, top, bottom = "BEAR", l2, hi
        else:
            continue
        size = top - bottom
        size_atr = sig(size / atr[i])
        if size_atr < MIN_GAP_ATR:
            continue
        g = {"direction": direction, "created_i": i, "top": top,
             "bottom": bottom, "size": size, "size_atr": size_atr,
             "filled_i": None}
        gaps.append(g)
        open_gaps.append(g)
    return gaps


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "fvg", FVG_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        atr = compute_atr(candles)
        counts = {"CREATED": 0, "FILLED": 0}

        for g in detect(candles, atr):
            ci = g["created_i"]
            created_ts = candles[ci]["open_ts"]
            gap_id = f"{symbol}|{tf}|FVG|{g['direction']}|{created_ts}"
            payload = {"event": "CREATED", "gap_id": gap_id,
                       "direction": g["direction"],
                       "top": plain(g["top"]), "bottom": plain(g["bottom"]),
                       "midpoint": plain(sig((g["top"] + g["bottom"]) / 2)),
                       "size": plain(g["size"]),
                       "size_atr": plain(g["size_atr"]),
                       "min_gap_atr": plain(MIN_GAP_ATR)}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="fvg",
                                 market_time=created_ts,
                                 confirmed_at=created_ts + tf_seconds,
                                 algo_version=FVG_VERSION, payload=payload):
                counts["CREATED"] += 1
            if g["filled_i"] is None:
                continue
            fi = g["filled_i"]
            fill_payload = {"event": "FILLED", "gap_id": gap_id,
                            "direction": g["direction"],
                            "top": plain(g["top"]), "bottom": plain(g["bottom"]),
                            "fill_lag_bars": fi - ci}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="fvg",
                                 market_time=candles[fi]["open_ts"],
                                 confirmed_at=candles[fi]["open_ts"] + tf_seconds,
                                 algo_version=FVG_VERSION, payload=fill_payload):
                counts["FILLED"] += 1

        con.commit()
        rec.n_new_facts = sum(counts.values())
        return {"symbol": symbol, "tf": tf, **counts}
