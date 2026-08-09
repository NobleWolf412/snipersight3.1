"""Volatility engine — ATR percentile, Bollinger width, and the squeeze.
algo volatility-v0.1-draft.

Why this engine exists. CONDITION is one of the five confluence rows and this
project measures none of it. Every other engine here describes WHERE price is
(`zones`, `liquidity`, `ranges`), WHICH WAY it is going (`structure`, `regime`,
`ma`) or HOW HARD (`momentum`). None of them says whether the market is coiled
or extended — and that is the reading that decides whether a level is likely to
be respected or run through, and whether a stop placed one ATR away is generous
or suicidal. ATR is already computed on every bar by `swings.compute_atr` and
is already used to size zones, ranges and tolerances; what has never existed is
a statement of whether TODAY's ATR is high or low FOR THIS SERIES.

EVIDENCE, GATING NOTHING (house convention 6). Nothing consumes these facts and
nothing may. `setups.py`, `risk.py`, `execsim.py` and `scalein.py` do not import
this module. A factor becomes a filter only after `engine/factorstats.py` grades
it — fire rate, dispersion, contribution, redundancy, outcome edge. A squeeze
flag is a particularly tempting gate ("don't trade the chop") and therefore
exactly the kind that has to be graded before it is trusted.

SHARED DEFINITIONS, DELIBERATELY. `compute_atr` comes from `swings.py` and the
averages come from `ma.py`. Neither is re-implemented here. S40 recorded what
the alternative costs: `ranges.py` kept a private copy of `quote_ticks` after
the shared one was corrected, and the two disagreed in exactly the case having
one definition was supposed to prevent. The consequence is stated plainly — an
`ma-v0.1` rule change is a `volatility-v0.1` rule change, because the same code
computes both averages. They must bump together even though this module reads
no `ma` FACT.

THE THREE READINGS:

  ATR PERCENTILE. The rank of the current ATR within the trailing 100 bars of
  the same series, as a percentage. Percentile rather than an absolute ATR, or
  an ATR-to-price ratio, because the question is comparative and only
  comparative: 0.9% daily range is dead for SOL and violent for a stablecoin
  pair. The window is 100 BARS, not 100 days, so the statement means the same
  thing on every timeframe — "compared with the last hundred bars of this
  chart". At n=100 one percentile point is one observation, which is the
  smallest window where a rank is not mostly a coin flip. Ties take the MIDRANK;
  `atr_percentiles` carries the reason, and it is not a detail — the obvious
  tie rule labels a dead-flat market as the 100th percentile.

  BOLLINGER WIDTH. (upper - lower) / middle, on the standard BB(20, 2): a
  20-period SMA of closes plus and minus two POPULATION standard deviations.
  Population (divide by n) rather than sample (n-1) is the textbook Bollinger
  construction, and it is a versioned choice — the two differ by 2.6% of the
  band width at n=20, which is not nothing when the squeeze test below is a
  comparison of two bands.

  THE SQUEEZE. Bollinger bands entirely INSIDE Keltner channels — the classic
  construction, and the reason both of the above are computed. It fires when
  standard deviation has fallen below average true range, i.e. when closes have
  stopped dispersing faster than bars are ranging, which is the measurable form
  of "the market has stopped going anywhere".

    The Keltner channel here is EMA20 +/- 1.5 * ATR14. The textbook uses a
    20-period ATR; this uses Wilder's 14 because `swings.compute_atr` is the
    single ATR definition in this codebase and a second one, differing only in
    its period, is precisely the drift `swings.py` and `ranges.py` were written
    to avoid. The house was asked for one ATR and gets one ATR. Recorded as a
    deviation from the textbook so that a later version can measure it rather
    than discover it.

EMISSION — ON STATE TRANSITION, NEVER PER BAR.

  Both readings are defined on every bar; per-bar emission is 570,061 rows for
  this engine alone against a store holding ~993k facts in total. A squeeze is
  natively a state, so it emits when the state flips. The percentile is
  natively continuous, so it is bucketed and the bucket emits when IT flips:

    SQUEEZE      ON <-> OFF
    ATR_REGIME   LOW <-> NORMAL <-> HIGH

  Measured over the whole store: 59,050 facts, 10.4% of bars — ATR_REGIME
  32,403, SQUEEZE 26,647. Per timeframe: 15m 18,116, 1H 27,349, 4H 6,575,
  1D 6,340, 1W 670. This is the quietest of the four indicator engines, which
  is what a CONDITION reading should be: condition is supposed to persist.

  The buckets are Schmitt-triggered, like `ma.py`'s slope and `momentum.py`'s
  RSI bands: LOW is entered at the 20th percentile and left at the 30th, HIGH
  entered at the 80th and left at the 70th. A single threshold at 20 would emit
  a pair of facts every time the percentile jittered across it and neither fact
  would describe a change in the market. The exit thresholds are versioned
  rules, not knobs.

  Every transition carries `bars_in_prev_state`. For a squeeze that is the whole
  point of the fact: a two-bar squeeze and a forty-bar squeeze are different
  objects, and the release of a long one is the event people actually mean when
  they say squeeze. Recorded, never thresholded here.

WARMUP REFUSAL (house convention 7). No squeeze fact before bar index 19 — a
20-period standard deviation of five bars is not a small-sample standard
deviation, it is a different statistic wearing the name. No ATR_REGIME fact
before bar index 113: ATR itself needs 15 bars and the percentile needs 100 ATR
values after that. Series shorter than that emit nothing rather than a rank out
of eleven samples.

CAUSALITY (house convention 1). Every quantity at bar i is a function of bars up
to and including i, so it is knowable at bar i's CLOSE:
`confirmed_at = open_ts + tf_seconds`, `market_time = open_ts`. The percentile
window is strictly trailing and inclusive — it never contains a bar the system
had not seen. No developing bar is read.

DECIMAL (house convention 3). No float touches a price. The standard deviation
uses `Decimal.sqrt()`, which is correctly rounded at the context precision and
therefore reproducible, rather than `math.sqrt` on a float. The only integers
here are counts (how many window values are at or below the current one), which
are counts of observations and not prices.

APPEND-ONLY AND IDEMPOTENT (house convention 4). No wall clock, no RNG, no
dict-ordering dependence. Re-running over identical candles writes zero facts.
"""
import bisect
from decimal import Decimal

from . import store
from .ma import ema, plain, sig
from .runlog import RunRecorder
from .swings import compute_atr

VOLATILITY_VERSION = "volatility-v0.2-draft"
# v0.2: input cascade from agg-v0.2 (own 4H/1W candle reads and ma-v0.2
# shared code) — acknowledged-partial buckets; no rule change here.

BB_PERIOD = 20
BB_K = Decimal(2)
KC_PERIOD = 20
KC_K = Decimal("1.5")
PCTL_WINDOW = 100
# Entry / exit pairs. The gap IS the deadband; see the docstring.
ATR_LOW_IN, ATR_LOW_OUT = Decimal(20), Decimal(30)
ATR_HIGH_IN, ATR_HIGH_OUT = Decimal(80), Decimal(70)
Q2 = Decimal("0.01")


def bollinger(closes: list, period: int = BB_PERIOD, k: Decimal = BB_K):
    """(middle, upper, lower) per bar index; None inside the warmup.

    POPULATION standard deviation (divide by n). That is Bollinger's own
    construction and it is stated here because the alternative is not visibly
    wrong: at n=20 the sample deviation is 2.6% wider, which would move the
    squeeze test's answer on the bars where it is closest.
    """
    mid: list = [None] * len(closes)
    up: list = [None] * len(closes)
    low: list = [None] * len(closes)
    if len(closes) < period:
        return mid, up, low
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        m = sum(window) / period
        var = sum((v - m) * (v - m) for v in window) / period
        # Decimal.sqrt is correctly rounded at the context precision, so this is
        # reproducible across runtimes in a way math.sqrt on a float is not.
        sd = var.sqrt()
        mid[i], up[i], low[i] = sig(m), sig(m + k * sd), sig(m - k * sd)
    return mid, up, low


def keltner(closes: list, atr: list, period: int = KC_PERIOD, k: Decimal = KC_K):
    """(middle, upper, lower) per bar index, EMA-centred and ATR-scaled.

    ATR is `swings.compute_atr` — Wilder's 14, not the textbook Keltner 20. One
    ATR definition per codebase; see the module docstring.
    """
    mid = ema(closes, period)
    up: list = [None] * len(closes)
    low: list = [None] * len(closes)
    for i in range(len(closes)):
        if mid[i] is None or atr[i] is None:
            continue
        up[i], low[i] = sig(mid[i] + k * atr[i]), sig(mid[i] - k * atr[i])
    return mid, up, low


def atr_regime(prev: str | None, pct: Decimal) -> str:
    """Schmitt-triggered percentile bucket. Enter at 20/80, leave at 30/70."""
    if pct <= ATR_LOW_IN:
        return "LOW"
    if pct >= ATR_HIGH_IN:
        return "HIGH"
    if prev == "LOW" and pct <= ATR_LOW_OUT:
        return "LOW"
    if prev == "HIGH" and pct >= ATR_HIGH_OUT:
        return "HIGH"
    return "NORMAL"


def atr_percentiles(atr: list, window: int = PCTL_WINDOW) -> list:
    """Rank of each ATR within the trailing `window` values, as a percentage.

    MIDRANK on ties, which is the one decision in this function that changes
    what the number means. Counting ties as "at or below" is the obvious
    implementation and it reports a perfectly flat series at the 100th
    percentile — nothing in the window is higher, which is true and useless: a
    dead market would be labelled maximum volatility, and the ATR_REGIME state
    machine would classify silence as HIGH. The midrank of a flat window is 50,
    which says what a flat window actually means — this reading is neither
    unusually high nor unusually low, it sits in the middle of its own
    distribution.

    Inclusive of the bar itself, so the scale runs from 0.5 (the lowest reading
    in a 100-bar window) to 99.5 (the highest).

    Kept as an ordered window with binary search rather than a re-sort per bar.
    The result is identical either way; the difference is that a fresh sort of
    100 Decimals on each of 570,061 bars is the single slowest thing this
    engine would do.
    """
    out: list = [None] * len(atr)
    ordered: list = []
    for i, a in enumerate(atr):
        if a is None:
            continue
        bisect.insort(ordered, a)
        if len(ordered) > window:
            leaving = atr[i - window]
            if leaving is not None:
                ordered.pop(bisect.bisect_left(ordered, leaving))
        if len(ordered) < window:
            continue                        # warmup: no partial rank (§7)
        lo = bisect.bisect_left(ordered, a)
        hi = bisect.bisect_right(ordered, a)
        out[i] = (Decimal(100 * (lo + hi)) / (2 * len(ordered))).quantize(Q2)
    return out


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "volatility", VOLATILITY_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        closes = [Decimal(c["close"]) for c in candles]
        atr = compute_atr(candles)
        bb_mid, bb_up, bb_low = bollinger(closes)
        kc_mid, kc_up, kc_low = keltner(closes, atr)
        pctl = atr_percentiles(atr)

        counts = {"SQUEEZE": 0, "ATR_REGIME": 0}

        def emit(i: int, event: str, extra: dict) -> None:
            c = candles[i]
            payload = {"event": event, "bar_index": i,
                       "close": plain(closes[i]),
                       "atr": None if atr[i] is None else plain(atr[i]),
                       "atr_percentile": None if pctl[i] is None else plain(pctl[i]),
                       **extra}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="volatility",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=VOLATILITY_VERSION, payload=payload):
                counts[event] += 1

        # --- squeeze: Bollinger inside Keltner ------------------------------
        state, since = None, None
        for i in range(len(candles)):
            if None in (bb_up[i], bb_low[i], kc_up[i], kc_low[i], bb_mid[i]):
                continue
            on = bb_up[i] < kc_up[i] and bb_low[i] > kc_low[i]
            new = "ON" if on else "OFF"
            if new == state:
                continue
            width = (bb_up[i] - bb_low[i]) / bb_mid[i] * 100 if bb_mid[i] else None
            emit(i, "SQUEEZE",
                 {"squeeze": new, "from": state,
                  "state": "ESTABLISHED" if state is None else "CHANGED",
                  "bars_in_prev_state": None if since is None else i - since,
                  "bb_upper": plain(bb_up[i]), "bb_lower": plain(bb_low[i]),
                  "bb_mid": plain(bb_mid[i]),
                  "bb_width_pct": None if width is None else plain(width.quantize(Q2)),
                  "kc_upper": plain(kc_up[i]), "kc_lower": plain(kc_low[i]),
                  "kc_mid": plain(kc_mid[i])})
            state, since = new, i

        # --- ATR percentile regime ------------------------------------------
        regime, since = None, None
        for i in range(len(candles)):
            if pctl[i] is None:
                continue
            new = atr_regime(regime, pctl[i])
            if new == regime:
                continue
            emit(i, "ATR_REGIME",
                 {"regime": new, "from": regime,
                  "state": "ESTABLISHED" if regime is None else "CHANGED",
                  "bars_in_prev_state": None if since is None else i - since,
                  "percentile_window": PCTL_WINDOW,
                  "low_at": plain(ATR_LOW_IN), "high_at": plain(ATR_HIGH_IN)})
            regime, since = new, i

        con.commit()
        rec.n_new_facts = sum(counts.values())
        rec.notes = " ".join(f"{k.lower()}={v}" for k, v in counts.items())
        return {"symbol": symbol, "tf": tf,
                **{k.lower(): v for k, v in counts.items()}}
