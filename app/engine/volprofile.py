"""Volume profile — is price sitting where volume lived? algo volprofile-v0.1-draft.

Why this engine exists. CONDITION and LOCATION each have engines; what nothing
here measures is ACCEPTANCE — whether the price a setup fires at is one the
market has transacted heavily at (a high-volume node, where resting interest
lives and moves stall) or barely at all (a low-volume node, which price tends
to transit fast). The prior project consumed exactly this reading twice: its
entry engine scored levels backed by volume, and its target builder refused to
place a TP on the far side of an HVN. Neither use is portable before the
underlying fact exists to grade — this engine records the fact.

EVIDENCE, GATING NOTHING (house convention 6). No strategy consumes these
facts and none may. `setups.py`, `risk.py`, `execsim.py` and `scalein.py` do
not import this module. A factor becomes a filter only after
`engine/factorstats.py` grades it — and the BTC-alignment audition next door
is this repo's own proof of why: the ported-untested version of that rule
graded inverted on this book.

THE MEASUREMENT. A rolling window of VP_WINDOW_BARS closed bars, each bar's
volume spread UNIFORMLY across the fixed-width price bins its high-low range
covers. Uniform allocation is a stated simplification, not a discovery: OHLC
says where a bar traded, never how volume distributed within it, and any
cleverer split would be an invention wearing precision. Each bar's CLOSE is
then classified by how its bin's volume compares to the window's median
nonzero bin:

    AT_HVN   ratio >= 2.0, holding until it falls below 1.5
    AT_LVN   ratio <= 0.35, holding until it rises above 0.5
    MID      everything else

The enter/hold pairs are Schmitt triggers for the same reason `momentum.py`'s
RSI bands carry a deadband: a single threshold chatters, writing a fact per
oscillation to say nothing changed.

EMISSION — ON STATE CHANGE, NEVER PER BAR (the `momentum.py` arithmetic:
per-bar emission would be one row per bar per symbol per timeframe to mostly
restate yesterday). VP_STATE facts carry the state, the ratio, the bin bounds
and the window parameters; the first determined state is ESTABLISHED.

TWO ENGINEERING CHOICES THAT ARE CORRECTNESS CHOICES:

  · Bins sit on an ABSOLUTE grid whose step is fixed per series from the FIRST
    close's magnitude (VP_BIN_PCT of it, price-rounded). The tempting
    alternative — bins spanning the current window's range — re-anchors every
    bin as the window drifts, which silently re-labels HISTORY: each new candle
    would shift what old bars' states "were", and an append-only store would
    fill with near-duplicate restatements every cycle. The first candle of a
    series is immutable in an append-only store, so a step derived from it is
    both causal and permanently stable. The cost is honesty about scale: a
    symbol that later moves 10x has bins 10x finer relative to price than at
    anchor. That is a versioned limitation, stated here, not a surprise.

  · The MEDIAN is refreshed every VP_MEDIAN_STRIDE bars, not every bar. The
    median of a 240-bar profile drifts slowly by construction; recomputing it
    per bar is an O(bins log bins) sort inside the hottest loop of an engine
    that walks full history every cycle, for a denominator that barely moved.
    Deterministic (the stride is fixed, the walk is ordered) and causal (each
    refresh uses only the window as of that bar).

VOLUME IS NOT A PRICE. Bin population and ratios run in float: the house rule
protects prices from float drift, and volumes arrive as venue-reported
quantities feeding thresholds of 2.0 and 0.35 — a 1e-12 wobble cannot cross
them. Bin EDGES are prices and stay Decimal.

WARMUP REFUSAL (house convention 7). No classification exists before the first
full window; the engine emits nothing there rather than classifying against a
profile that does not yet exist.

CAUSALITY (house convention 1). A bar's state is a function of the window
ending at that bar, knowable at its close: confirmed_at = open_ts + tf_seconds.

APPEND-ONLY AND IDEMPOTENT (house convention 4). Pure function of the candle
series. Re-running over identical candles writes zero new facts; a new candle
can only append transitions at the frontier, never restate old ones.
"""
from decimal import Decimal

from . import store
from .ma import plain, sig
from .runlog import RunRecorder

VOLPROFILE_VERSION = "volprofile-v0.1-draft"

VP_WINDOW_BARS = 240          # ~2.5 days of 15m, ~10 days of 1H
VP_BIN_PCT = Decimal("0.0025")  # bin step = 0.25% of the series' first close
VP_MEDIAN_STRIDE = 16         # bars between median refreshes; see docstring
HVN_ENTER, HVN_HOLD = 2.0, 1.5
LVN_ENTER, LVN_HOLD = 0.35, 0.5


def bin_step(first_close: Decimal) -> Decimal:
    """The series' permanent bin width: VP_BIN_PCT of its first close,
    quantized scale-free so SHIB and BTC bin with equal resolution."""
    return sig(first_close * VP_BIN_PCT)


def classify(prev: str | None, ratio: float) -> str:
    """Schmitt-triggered node state for one close's bin ratio."""
    if ratio >= HVN_ENTER:
        return "AT_HVN"
    if ratio <= LVN_ENTER:
        return "AT_LVN"
    if prev == "AT_HVN" and ratio >= HVN_HOLD:
        return "AT_HVN"
    if prev == "AT_LVN" and ratio <= LVN_HOLD:
        return "AT_LVN"
    return "MID"


def walk_states(candles: list) -> list[dict]:
    """(bar_index, state, from, ratio, bin bounds) per transition. Pure.

    Rolling absolute-grid profile: O(bars x bins-per-bar) to maintain, one
    median sort every VP_MEDIAN_STRIDE bars.
    """
    if len(candles) < VP_WINDOW_BARS + 1:
        return []
    step = bin_step(Decimal(candles[0]["close"]))
    if step <= 0:
        return []
    stepf = float(step)

    bins: dict[int, float] = {}

    def spread(i: int, sign: float) -> None:
        c = candles[i]
        lo, hi = float(c["low"]), float(c["high"])
        vol = float(c["volume"]) * sign
        b0, b1 = int(lo // stepf), int(hi // stepf)
        share = vol / (b1 - b0 + 1)
        for b in range(b0, b1 + 1):
            nv = bins.get(b, 0.0) + share
            if nv <= 1e-12:
                bins.pop(b, None)
            else:
                bins[b] = nv

    for i in range(VP_WINDOW_BARS):
        spread(i, +1.0)

    out: list[dict] = []
    state: str | None = None
    median = 0.0
    for i in range(VP_WINDOW_BARS, len(candles)):
        spread(i, +1.0)
        spread(i - VP_WINDOW_BARS, -1.0)
        if (i - VP_WINDOW_BARS) % VP_MEDIAN_STRIDE == 0 or median <= 0:
            vols = sorted(bins.values())
            median = vols[len(vols) // 2] if vols else 0.0
        if median <= 0:
            continue
        cb = int(float(candles[i]["close"]) // stepf)
        ratio = bins.get(cb, 0.0) / median
        new = classify(state, ratio)
        if new != state:
            out.append({"i": i, "state": new, "from": state,
                        "ratio": round(ratio, 4),
                        "bin_lo": step * cb, "bin_hi": step * (cb + 1)})
            state = new
    return out


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "volprofile", VOLPROFILE_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        counts = {"VP_STATE": 0}
        for t in walk_states(candles):
            c = candles[t["i"]]
            payload = {"event": "VP_STATE", "state": t["state"],
                       "from": t["from"],
                       "phase": "ESTABLISHED" if t["from"] is None else "CHANGED",
                       "ratio": t["ratio"],
                       "bin_lo": plain(sig(t["bin_lo"])),
                       "bin_hi": plain(sig(t["bin_hi"])),
                       "close": c["close"],
                       "window_bars": VP_WINDOW_BARS,
                       "median_stride": VP_MEDIAN_STRIDE,
                       "hvn_enter": HVN_ENTER, "lvn_enter": LVN_ENTER}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="volprofile",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=VOLPROFILE_VERSION,
                                 payload=payload):
                counts["VP_STATE"] += 1
        con.commit()
        rec.n_new_facts = counts["VP_STATE"]
        return {"symbol": symbol, "tf": tf, **counts}
