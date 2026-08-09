"""Moving-average engine — the ribbon, its slope, and where price sits in it.
algo ma-v0.1-draft.

Why this engine exists. The confluence matrix this project is being built
against has five rows. LOCATION is answered by `zones.py` and `liquidity.py`,
DIRECTION by `structure.py` and `regime.py`. TIMING, CONDITION and
PARTICIPATION had no measurement at all — not a weak one, none. This module is
the first of four that fill them, and it answers the part of TIMING a moving
average can honestly answer: is the trend structure of price stacked, which way
is it turning, and is price above it, below it or inside it.

EVIDENCE, GATING NOTHING (house convention 6). Nothing consumes these facts.
`setups.py`, `risk.py`, `execsim.py` and `scalein.py` do not import this module
and must not: a factor earns the right to become a filter from
`engine/factorstats.py`, which grades it on fire rate, dispersion, contribution,
redundancy and outcome edge FIRST. S39 is why that order is not negotiable — the
`rank` composite had been sorting the deck since it was introduced and, when it
was finally graded, it turned out to be NON-MONOTONE at its own mode: the modal
bucket, 51% of the deck, was the worst-performing one. An ungraded factor that
gates a trade is that failure waiting to happen again.

THE RIBBON: EMA20, EMA50, SMA200.

  Not a tuned set — the canonical one. These are the three averages that appear
  on other people's charts, which is the only property that matters for an
  average: a level is self-fulfilling in proportion to how many participants are
  watching it, and nobody is watching an EMA37. Two exponential and one simple is
  also the conventional pairing, and the mix is doing real work: the EMAs weight
  the recent bars that TIMING is about, the SMA weights all two hundred of them
  equally and so moves only when the whole sample moves.

  The seed for both EMAs is the SMA of their own first `period` closes, which is
  the standard construction. It is a versioned choice and it matters at the head
  of a series: an EMA seeded from the first close instead would carry that one
  bar's noise for ~3 periods.

WARMUP REFUSAL (house convention 7). No ribbon fact exists before bar index 199,
the first bar at which SMA200 is defined. Not "an SMA200 computed from the 60
bars available" — nothing. A partial average that looks like a real one is
exactly the lie a backtest tells.

  What that costs, measured on the 59-symbol store: SMA200 needs 200 closed
  bars, and the series that have them are 15m 59/59, 1H 59/59, 4H 58/59,
  1D 55/59 — and 1W 19/59 (median 188 bars). So the 1W row is silent on two
  thirds of the book. That silence is CORRECT rather than a gap: 200 weeks is
  3.8 years and most of these instruments are younger than their own slow
  average. The count of `ESTABLISHED` facts is exactly 250, which is that same
  arithmetic read back out of the store.

EMISSION — ON CHANGE, ONE FACT PER TRANSITION.

  A value per bar per symbol per timeframe is 570,061 rows for this engine
  alone against a store that held ~993k facts in total before it ran. So the
  emitted object is not the average, it is the ribbon's STATE, and a fact is
  written only when that state differs from the last one written:

    stack     BULL (e20>e50>s200) | BEAR (e20<e50<s200) | MIXED
    position  ABOVE | INSIDE | BELOW the ribbon envelope, by CLOSE
    slope     UP | DOWN | UNDECIDED, per average

  One fact carries all three, rather than three facts carrying one each. When a
  20/50 cross and a price re-entry land on the same bar they are one event in
  the market and should be one row in the store; the `changed` list says which
  components moved, so a consumer asking only "when did the 20 cross the 50"
  still gets an exact answer.

  The first bar the ribbon exists is emitted as `ESTABLISHED`. Without it a
  reader of the fact stream sees a transition INTO bull stack with no prior
  state and cannot tell a genuine flip from the beginning of the record.

  Measured over the whole store: 121,577 facts, 21.3% of bars. By component
  (a fact can name more than one), position 85,834, slope_ema20 17,223, stack
  14,128, slope_ema50 8,423, slope_sma200 2,309, plus the 250 establishments.
  Per timeframe: 15m 41,415, 1H 55,444, 4H 12,241, 1D 12,370, 1W 107.

  `position` is two thirds of that and it is NOT chatter — see `position` below
  for the measurement that ruled that out. Price crosses this ribbon roughly
  every seventh bar, and no threshold makes that untrue.

SLOPE NEEDS A DEADBAND, and this is the one place a naive implementation is
badly wrong. `ma[i] > ma[i-1]` flips on noise: measured across the 514,231
bars of this store where an EMA20 and an ATR both exist, the raw one-bar sign
of EMA20 changes 73,091 times — 14.2% of bars, to describe a quantity that is
mostly not moving. The rule below reduces that to 17,129 flips (3.3%), and the
engine's own `slope_ema20` count of 17,223 is that number read back out of the
store. So slope is a SCHMITT TRIGGER:

  · measured over the average's OWN scale, `period // 4` bars (5, 12, 50), not
    one bar — a 200-period average asked whether it rose since yesterday is
    being asked a question it was built not to answer;
  · it changes state only when the move exceeds 0.25 * ATR14 in the opposite
    direction, and holds its previous state inside that band. 0.25*ATR is not a
    new number — it is `zones.ZONE_ATR`, the width of one supply/demand band.
    A turn smaller than the width of one zone is not a turn.
  · until the first move clears the band the slope is UNDECIDED and is reported
    as null, not as a guess.

CAUSALITY (house convention 1). Every average at bar i is a function of closes
at or before bar i, so the state at bar i is knowable exactly at bar i's CLOSE:
`confirmed_at = open_ts + tf_seconds`, and `market_time = open_ts`. They are
never equal. No developing bar is ever read — the loop only ever indexes
candles the store has already closed, and the store's own aggregator refuses to
emit a developing bucket.

DECIMAL (house convention 3). No float touches a price anywhere in this module.
Averages are quantized to 8 SIGNIFICANT digits at every step, mirroring
`swings.compute_atr`'s per-step quantize. Significant digits rather than decimal
places deliberately: `compute_atr`'s 8dp is right for BTC at 47,000 and leaves
SHIB at 0.0000341 with three digits of resolution. The rounding is part of the
versioned rule and the emitted number IS the number the state decision used, so
the fact can be re-derived from its own payload.

APPEND-ONLY AND IDEMPOTENT (house convention 4). No wall clock, no RNG, no dict
iteration order. Re-running over identical candles writes zero facts; the
lockfile test and `test_ma.py` both hold that.
"""
from decimal import Decimal

from . import store
# `break_tolerance` is the house answer to "did price close THROUGH this level",
# max(1 tick, 0.05*ATR). structure.py, zones.py, liquidity.py and ranges.py all
# break a level on it and only it, and this engine asks the same question of the
# ribbon. It is imported from `ranges`, where it happens to be defined, rather
# than restated here: S40 is the record of what a second copy of one convention
# costs — `ranges` kept a private `quote_ticks` that had already drifted from
# the shared one before anybody looked.
from .ranges import break_tolerance
from .runlog import RunRecorder
from .swings import compute_atr, quote_ticks

MA_VERSION = "ma-v0.2-draft"
# v0.2: input cascade from agg-v0.2 — acknowledged-partial 4H/1W buckets
# change the series every average here is computed over; no rule change.

# (label, kind, period) — evaluated fast to slow. The order is load-bearing:
# `stack` reads it left to right, so changing it changes the meaning of BULL.
RIBBON = (("ema20", "EMA", 20), ("ema50", "EMA", 50), ("sma200", "SMA", 200))
SLOPE_DEADBAND_ATR = Decimal("0.25")     # == zones.ZONE_ATR; see docstring
SIG = 8                                  # significant digits kept per step
Q2 = Decimal("0.01")


def sig(x: Decimal) -> Decimal:
    """Round to SIG significant digits — scale-free, unlike a fixed dp.

    `swings.compute_atr` quantizes to 8 DECIMAL PLACES, which is 13 significant
    digits on BTC at 47,000 and 3 on SHIB at 0.0000341. Every engine in this
    file is asked to work on both, so the rounding has to follow the price
    rather than the decimal point.
    """
    if not x:
        return Decimal(0)
    return x.quantize(Decimal(1).scaleb(x.adjusted() - (SIG - 1)))


def plain(x: Decimal) -> str:
    """Decimal -> string without an exponent.

    `str(Decimal("4.773E+4"))` keeps the exponent, and a payload that sometimes
    says 47730 and sometimes 4.773E+4 for the same price is two spellings of one
    fact — which is how `content_hash` idempotency quietly dies.
    """
    return format(x, "f")


def sma(values: list, period: int) -> list:
    """Simple moving average per index; None until `period` values exist.

    The running sum is exact rather than merely close: a venue price string
    carries at most ~12 significant digits, 200 of them sum to at most ~15, and
    Decimal's default context holds 28 — so no add or subtract in this loop
    rounds, and the value at bar 3,000 is the same number a fresh window sum
    would give. That is what makes the rolling form safe to prefer over the
    O(period) one.
    """
    out: list = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    run = sum(values[:period])
    out[period - 1] = sig(run / period)
    for i in range(period, len(values)):
        run += values[i] - values[i - period]
        out[i] = sig(run / period)
    return out


def ema(values: list, period: int) -> list:
    """Exponentially weighted MA, seeded with the SMA of the first `period`
    values — the standard construction, and a versioned choice: seeding from a
    single close instead would carry that one bar's noise for roughly three
    periods before the weight decayed out of it."""
    out: list = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = Decimal(2) / (period + 1)
    prev = sig(sum(values[:period]) / period)
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = sig(prev + k * (values[i] - prev))
        out[i] = prev
    return out


def stack(values: list, tol: Decimal) -> str:
    """BULL when the ribbon is ordered fast-above-slow, BEAR when reversed.

    "Above" means above by the house break tolerance, not by a hair. Two
    averages within a tick of each other have not stacked, they are entwined,
    and a bare `a > b` reports a fresh BULL stack every time the noise between
    them changes sign.

    MIXED is not a failure to classify, it is the third real state: a ribbon
    whose averages have crossed — or have not yet separated — is describing a
    market that has not decided, and collapsing it into the nearest of the other
    two would invent a trend the averages are explicitly not showing.
    """
    if all(a > b + tol for a, b in zip(values, values[1:])):
        return "BULL"
    if all(a < b - tol for a, b in zip(values, values[1:])):
        return "BEAR"
    return "MIXED"


def position(close: Decimal, values: list, tol: Decimal) -> str:
    """Where the close sits relative to the ribbon ENVELOPE, not to any one
    average. INSIDE is the interesting state and it is only nameable against the
    envelope: price between the 20 and the 50 is at a different kind of place
    from price above both, and a rule written against a single average cannot
    say so.

    The envelope is fattened by the house break tolerance on both sides, so
    that "above the ribbon" means here exactly what "above a level" means in
    structure.py, zones.py and ranges.py.

    IT DOES NOT MAKE THE ENGINE QUIETER, and the measurement is worth recording
    because the opposite was the obvious expectation. Before the tolerance,
    `position` moved 85,153 times over the store; with it, 85,834 — slightly
    MORE, because widening INSIDE turns some single ABOVE -> BELOW flips into
    two. Nor is the size of the tolerance the lever: on a 12-symbol sample,
    position transitions run 17,372 / 17,423 / 17,418 / 16,867 / 14,142 at
    0.05 / 0.15 / 0.25 / 0.50 / 1.00 * ATR. A twentyfold increase in the
    threshold buys 19%.

    So the rate is a property of the market rather than of the threshold: price
    genuinely crosses this ribbon about every seventh bar. The tolerance stays
    because consistency with the rest of the codebase is what it is for — and
    because on a sub-dollar symbol a bare comparison would flip on a quote tick,
    which is the failure S40 recorded one layer up.
    """
    if close > max(values) + tol:
        return "ABOVE"
    if close < min(values) - tol:
        return "BELOW"
    return "INSIDE"


def slope_state(prev_state, delta: Decimal, deadband: Decimal):
    """Schmitt trigger: latch UP/DOWN, and hold through the deadband.

    Returns the new state, which is `prev_state` (possibly None) whenever the
    move is inside the band. See the module docstring for the measurement that
    forced this: the raw one-bar sign of EMA20 flips on 14.2% of bars,
    and this rule brings that to 3.3%.
    """
    if delta > deadband:
        return "UP"
    if delta < -deadband:
        return "DOWN"
    return prev_state


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "ma", MA_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        closes = [Decimal(c["close"]) for c in candles]
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)

        series, lookbacks = {}, {}
        for label, kind, period in RIBBON:
            series[label] = ema(closes, period) if kind == "EMA" else sma(closes, period)
            # The average's own scale, not one bar. See docstring.
            lookbacks[label] = max(1, period // 4)

        labels = [r[0] for r in RIBBON]
        # The ribbon exists only where EVERY average does (convention 7) and
        # where ATR does, since the slope deadband is denominated in it.
        warmup = max(p for _, _, p in RIBBON) - 1

        slopes = {label: None for label in labels}
        last_state = None
        n_facts = 0

        for i in range(warmup, len(candles)):
            values = [series[label][i] for label in labels]
            if any(v is None for v in values) or atr[i] is None:
                continue
            deadband = SLOPE_DEADBAND_ATR * atr[i]
            for label in labels:
                j = i - lookbacks[label]
                past = series[label][j] if j >= 0 else None
                if past is None:
                    continue
                slopes[label] = slope_state(slopes[label], series[label][i] - past,
                                            deadband)

            c = candles[i]
            close = closes[i]
            tol = break_tolerance(atr[i], ticks[i])
            st = stack(values, tol)
            pos = position(close, values, tol)
            state = (st, pos, tuple(slopes[label] for label in labels))
            if state == last_state:
                continue

            changed = []
            if last_state is None:
                event = "ESTABLISHED"
            else:
                event = "CHANGED"
                if st != last_state[0]:
                    changed.append("stack")
                if pos != last_state[1]:
                    changed.append("position")
                for k, label in enumerate(labels):
                    if state[2][k] != last_state[2][k]:
                        changed.append(f"slope_{label}")

            payload = {
                "event": event,
                "stack": st,
                "position": pos,
                "changed": changed,
                "close": plain(close),
                "atr": plain(atr[i]),
                "slope_deadband": plain(sig(deadband)),
                "level_tolerance": plain(sig(tol)),
                "ribbon": [{"name": label, "period": period, "kind": kind,
                            "value": plain(series[label][i]),
                            "slope": slopes[label],
                            "slope_lookback_bars": lookbacks[label]}
                           for (label, kind, period) in RIBBON],
                # Distance to the ribbon in ATR is the scale-free version of
                # "how extended is this", and it is the reading a consumer would
                # otherwise have to recompute from the values above. Recorded,
                # never thresholded here.
                "close_to_fast_atr": plain(
                    ((close - series[labels[0]][i]) / atr[i]).quantize(Q2)),
                "close_to_slow_atr": plain(
                    ((close - series[labels[-1]][i]) / atr[i]).quantize(Q2)),
                "bar_index": i,
            }
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="ma",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=MA_VERSION, payload=payload):
                n_facts += 1
            last_state = state

        con.commit()
        rec.n_new_facts = n_facts
        rec.notes = f"ribbon_states={n_facts}"
        return {"symbol": symbol, "tf": tf, "facts": n_facts}
