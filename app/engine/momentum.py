"""Momentum engine — RSI, MACD, and divergence against the swing facts.
algo momentum-v0.1-draft.

Why this engine exists. TIMING is one of the five confluence rows and this
project measures none of it. `ma.py` answers the part of TIMING that a moving
average can answer — is the trend stacked, is it turning. This module answers
the other part: is the MOVE losing force, and specifically is it losing force
while price is still making new extremes. That second question is divergence,
and it is the only reading here that is not available from the price series
alone — it needs the pivots, which `swings.py` already owns.

EVIDENCE, GATING NOTHING (house convention 6). No strategy consumes these facts
and none may. `setups.py`, `risk.py`, `execsim.py` and `scalein.py` do not
import this module. A factor becomes a filter only after `engine/factorstats.py`
grades it on fire rate, dispersion, contribution, redundancy and outcome edge.
Divergence in particular is the sort of factor that reads as obviously true and
grades badly, which is exactly why it is emitted as evidence and left there.

THE THREE INSTRUMENTS, and the one that is not a duplicate:

  RSI(14), Wilder. The standard smoothing, matching `swings.compute_atr`'s
  treatment of ATR — Wilder wrote both and mixing his RSI with a simple-average
  smoothing would be a third convention nobody asked for.

  MACD(12, 26, 9). EMA12 - EMA26, signalled by EMA9 of that difference. The
  EMAs come from `ma.ema`, not from a private copy: two implementations of one
  average is how they come to disagree, and S40 recorded this project doing
  exactly that with `quote_ticks`. The consequence is stated plainly — an
  `ma-v0.1` rule change is a `momentum-v0.1` rule change, because the same code
  computes both. They must bump together even though this module reads no `ma`
  FACT.

  DIVERGENCE against `swings.py` LOCAL pivots. LOCAL for the same measured
  reason `ranges.py` chose it: divergence is made of the swings that actually
  touch a level, and those are local. INTERMEDIATE+ pivots are separated by
  large moves BY CONSTRUCTION (swings.py v0.2 built them to isolate "the 7-10
  macro swing points that truly matter"), so consecutive ones are rarely close
  enough in time for a divergence between them to mean anything. LOCAL is also
  a strict superset — swings.py emits a LOCAL fact for every pivot it later
  promotes — so the choice discards nothing.

REGULAR DIVERGENCE ONLY, in v0.1.

  Bearish: consecutive HIGH pivots where price made a HIGHER high and RSI made
  a LOWER high. Bullish: consecutive LOW pivots, LOWER low in price and HIGHER
  low in RSI. Hidden divergence (the continuation form: lower high in price
  against a higher high in RSI) is deliberately NOT emitted. It is not a weaker
  signal, it is a signal whose meaning depends entirely on the prevailing trend
  — and this engine reads no regime, on purpose, for the reason `ranges.py`
  states: coupling a geometric measurement to a regime version means every
  regime bump invalidates every fact for a reason that has nothing to do with
  the measurement. A later version can add it with a trend input and its own
  version string.

  Pivots more than 100 bars apart are not compared. Two highs four hundred bars
  apart are not the same swing structure whatever their RSI says; 100 bars is
  the same horizon `liquidity.py` uses to decide that two swings formed "near
  each other", reused rather than re-invented.

EMISSION — ON EVENT, NEVER PER BAR.

  RSI and MACD are defined on every bar. Emitting them per bar is 570,061 rows
  for this engine against a store holding ~993k facts in total, to describe
  three quantities that mostly do not move. So four event families are emitted
  and nothing else:

    RSI_BAND      the RSI band state changes (OVERBOUGHT / NEUTRAL / OVERSOLD)
    MACD_SIGNAL   the MACD line crosses its signal line
    MACD_ZERO     the MACD line crosses zero
    DIVERGENCE    a regular divergence completes at a LOCAL pivot

  Measured over the whole store: 99,093 facts, 17.4% of bars — MACD_SIGNAL
  44,943, RSI_BAND 22,777, MACD_ZERO 20,550, DIVERGENCE 10,823. Per timeframe:
  15m 31,676, 1H 44,041, 4H 10,764, 1D 11,178, 1W 1,434.

  DIVERGENCE is the smallest family, and its BASE RATE is the first thing worth
  knowing about it: 140,142 LOCAL swing facts collapse to 111,108 adjacent
  same-type pivot pairs, of which 10,823 diverge — 9.7%. That number is what
  any later grading of this factor has to beat. A signal present on one swing
  pair in ten is not rare enough to be special on its own, which is precisely
  the sort of thing `factorstats.py` exists to say out loud before a rule is
  built on it.

  The band edges carry a deadband, for the same reason `ma.py`'s slope does. A
  single 70 threshold used for both entry and exit chatters: RSI oscillating
  across 70 writes a fact per oscillation to say nothing changed. Entry at 70 /
  exit at 65 (and 30 / 35) is a Schmitt trigger, and the exit threshold is a
  versioned choice, not a tuning knob to be revisited without a version bump.

  Each state machine emits its first determined state as `ESTABLISHED`. Without
  it a reader sees a transition INTO overbought with no prior state and cannot
  tell a genuine crossing from the start of the record.

WARMUP REFUSAL (house convention 7). RSI(14) needs 14 price CHANGES, so 15
bars: the first value sits at bar index 14 and there is none before it. MACD's
signal line needs EMA26 (index 25) plus nine of its own values (index 33) — so
no MACD_SIGNAL fact can exist before bar 33 even though the MACD line itself
exists at 25. Nothing partial is emitted in either window.

CAUSALITY (house convention 1). RSI at bar i is a function of closes up to and
including bar i, so it is knowable at bar i's CLOSE and not one second earlier:
`confirmed_at = open_ts + tf_seconds`. A divergence is different and stricter —
it is knowable only when BOTH its pivots are, and a LOCAL pivot confirms well
after its own bar (swings.py dates it at the next opposite micro swing's
confirmation). So a divergence carries
`confirmed_at = max(pivot_1.confirmed_at, pivot_2.confirmed_at, bar_2 close)`
and records `confirmation_lag_bars`, so a consumer can tell a divergence it
could have acted on from one that was only visible in hindsight.

DECIMAL (house convention 3). No float touches a price. RSI is derived from
price differences and stays Decimal throughout; the 100 in the RSI formula is
`Decimal(100)`. Values are quantized to 8 significant digits per step via
`ma.sig`, scale-free so that SHIB at 0.0000341 keeps the same resolution BTC
gets.

APPEND-ONLY AND IDEMPOTENT (house convention 4). No wall clock, no RNG, no
reliance on dict ordering. Re-running over identical candles and identical
swing facts writes zero new facts.
"""
import json
from decimal import Decimal

from . import store
from .ma import ema, plain, sig
from .runlog import RunRecorder
from .swings import SWING_VERSION, alternate

MOMENTUM_VERSION = "momentum-v0.3-draft"
# v0.3: input cascade from agg-v0.2 (own 4H/1W candle reads, swing-v0.10
# facts, and ma-v0.2 shared code) — acknowledged-partial buckets; no rule
# change here.
# v0.2: cascade from swing-v0.9. No rule change here — divergences read LOCAL
# swings, whose payloads never carried the accruing evidence — but the input
# namespace moved, and a tag must identify the generation of its inputs.

RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
# Entry / exit pairs. The gap IS the deadband; see the docstring.
RSI_OVERBOUGHT_IN, RSI_OVERBOUGHT_OUT = Decimal(70), Decimal(65)
RSI_OVERSOLD_IN, RSI_OVERSOLD_OUT = Decimal(30), Decimal(35)
DIVERGENCE_TIERS = ("LOCAL",)
MAX_PIVOT_GAP_BARS = 100          # == liquidity.MAX_BARS_APART, see docstring
Q2 = Decimal("0.01")


def compute_rsi(closes: list, period: int = RSI_PERIOD) -> list:
    """Wilder RSI per bar index; None until `period` changes exist.

    Returns None — not 50 — when the window contains no movement at all in
    either direction. RSI is 0/0 there and the conventional 50 is an invention:
    it would read as "perfectly balanced buying and selling" when what actually
    happened is that nothing traded through. Rare on a real venue series,
    routine on a synthetic flat one, and a silent 50 in a backtest is a
    fabricated neutral reading rather than a missing one.
    """
    out: list = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains = losses = Decimal(0)
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses += -d
    avg_gain, avg_loss = sig(gains / period), sig(losses / period)
    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        gain = d if d > 0 else Decimal(0)
        loss = -d if d < 0 else Decimal(0)
        # Wilder smoothing, quantized per step exactly as compute_atr does.
        avg_gain = sig((avg_gain * (period - 1) + gain) / period)
        avg_loss = sig((avg_loss * (period - 1) + loss) / period)
        out[i] = _rsi(avg_gain, avg_loss)
    return out


def _rsi(avg_gain: Decimal, avg_loss: Decimal):
    if avg_loss == 0:
        return None if avg_gain == 0 else Decimal(100)
    return sig(Decimal(100) - Decimal(100) / (1 + avg_gain / avg_loss))


def compute_macd(closes: list) -> tuple[list, list, list]:
    """(macd, signal, histogram) per bar index, None inside each warmup.

    The signal line is an EMA of the MACD LINE, so it cannot start until the
    MACD line has `MACD_SIGNAL` values of its own — index 25 + 8 = 33 with the
    standard periods. Slicing to the first defined MACD value and offsetting the
    result back is how that second warmup stays honest: seeding the signal EMA
    with Nones, or with zeros standing in for them, would put a signal line
    under bars where there was nothing to average.
    """
    fast, slow = ema(closes, MACD_FAST), ema(closes, MACD_SLOW)
    macd = [None if (f is None or s is None) else f - s
            for f, s in zip(fast, slow)]
    first = next((i for i, v in enumerate(macd) if v is not None), None)
    if first is None:
        return macd, [None] * len(closes), [None] * len(closes)
    signal = [None] * first + ema(macd[first:], MACD_SIGNAL)
    hist = [None if (m is None or s is None) else m - s
            for m, s in zip(macd, signal)]
    return macd, signal, hist


def rsi_band(prev: str | None, value: Decimal) -> str:
    """Schmitt-triggered band state. Enter at 70/30, leave at 65/35.

    Holding the previous state inside the deadband is the whole point: one
    threshold used for both directions turns a single hesitant approach to 70
    into a run of facts that each say the state changed, when it did not.
    """
    if value >= RSI_OVERBOUGHT_IN:
        return "OVERBOUGHT"
    if value <= RSI_OVERSOLD_IN:
        return "OVERSOLD"
    if prev == "OVERBOUGHT" and value >= RSI_OVERBOUGHT_OUT:
        return "OVERBOUGHT"
    if prev == "OVERSOLD" and value <= RSI_OVERSOLD_OUT:
        return "OVERSOLD"
    return "NEUTRAL"


def sign_state(prev: str | None, value: Decimal) -> str | None:
    """ABOVE / BELOW, holding through an exact zero.

    An exact zero is not a third state and it is not a crossing — it is a value
    on the line. Treating it as a crossing would emit two facts (in, then out)
    for one traversal.
    """
    if value > 0:
        return "ABOVE"
    if value < 0:
        return "BELOW"
    return prev


def _pivots(con, symbol: str, tf: str) -> list[dict]:
    """LOCAL swing pivots, collapsed to a strictly alternating HIGH/LOW sequence.

    `swings.alternate` is reused rather than re-derived, exactly as `ranges.py`
    reuses it: the tier recursion already defines what an alternating pivot
    sequence is, and a second definition here would be a second answer to the
    same question. It also inherits confirmed_at conservatively (the latest seen
    in a replacement chain), so collapsing repeats can never make a divergence
    knowable earlier than the swings that built it.
    """
    raw = []
    for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
        p = json.loads(r["payload"])
        if p["tier"] in DIVERGENCE_TIERS:
            raw.append({"market_time": r["market_time"],
                        "confirmed_at": r["confirmed_at"],
                        "type": p["type"], "price": p["price"]})
    return alternate(raw)


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "momentum", MOMENTUM_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        closes = [Decimal(c["close"]) for c in candles]
        rsi = compute_rsi(closes)
        macd, signal, hist = compute_macd(closes)

        counts = {"RSI_BAND": 0, "MACD_SIGNAL": 0, "MACD_ZERO": 0,
                  "DIVERGENCE": 0}

        def emit(i: int, event: str, extra: dict) -> None:
            c = candles[i]
            payload = {"event": event, "bar_index": i,
                       "close": plain(closes[i]),
                       "rsi": None if rsi[i] is None else plain(rsi[i]),
                       "macd": None if macd[i] is None else plain(macd[i]),
                       "macd_signal": None if signal[i] is None else plain(signal[i]),
                       "macd_hist": None if hist[i] is None else plain(hist[i]),
                       **extra}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="momentum",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=MOMENTUM_VERSION, payload=payload):
                counts[event] += 1

        # --- RSI band -------------------------------------------------------
        band = None
        for i in range(len(candles)):
            if rsi[i] is None:
                continue
            new = rsi_band(band, rsi[i])
            if new == band:
                continue
            emit(i, "RSI_BAND", {"band": new, "from": band,
                                 "state": "ESTABLISHED" if band is None else "CHANGED",
                                 "overbought_at": plain(RSI_OVERBOUGHT_IN),
                                 "oversold_at": plain(RSI_OVERSOLD_IN)})
            band = new

        # --- MACD vs its signal line, and MACD vs zero ----------------------
        for event, seriesv in (("MACD_SIGNAL", hist), ("MACD_ZERO", macd)):
            state = None
            for i in range(len(candles)):
                v = seriesv[i]
                if v is None:
                    continue
                new = sign_state(state, v)
                if new is None or new == state:
                    continue
                emit(i, event,
                     {"side": new, "from": state,
                      "direction": "BULL" if new == "ABOVE" else "BEAR",
                      "state": "ESTABLISHED" if state is None else "CHANGED"})
                state = new

        # --- divergence against the LOCAL pivots ----------------------------
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        seq = _pivots(con, symbol, tf)
        for k in range(2, len(seq)):
            prev_p, now_p = seq[k - 2], seq[k]
            i1 = ts_index.get(prev_p["market_time"])
            i2 = ts_index.get(now_p["market_time"])
            if i1 is None or i2 is None or i2 - i1 > MAX_PIVOT_GAP_BARS:
                continue
            if rsi[i1] is None or rsi[i2] is None:
                continue
            p1, p2 = Decimal(prev_p["price"]), Decimal(now_p["price"])
            r1, r2 = rsi[i1], rsi[i2]
            if now_p["type"] == "HIGH" and p2 > p1 and r2 < r1:
                kind_d, direction = "BEARISH", "BEAR"
            elif now_p["type"] == "LOW" and p2 < p1 and r2 > r1:
                kind_d, direction = "BULLISH", "BULL"
            else:
                continue
            bar_close = candles[i2]["open_ts"] + tf_seconds
            # Knowable only when BOTH pivots are. A LOCAL pivot confirms after
            # its own bar, so this is routinely later than bar 2's close.
            confirmed = max(prev_p["confirmed_at"], now_p["confirmed_at"], bar_close)
            lag = max(0, (confirmed - bar_close) // tf_seconds)
            payload = {"event": "DIVERGENCE", "divergence": kind_d,
                       "direction": direction, "pivot_type": now_p["type"],
                       "bar_index": i2,
                       "close": plain(closes[i2]),
                       "rsi": plain(r2), "rsi_prev": plain(r1),
                       "rsi_delta": plain(sig(r2 - r1)),
                       "price": plain(p2), "price_prev": plain(p1),
                       "prev_pivot_ts": prev_p["market_time"],
                       "bars_apart": i2 - i1,
                       "confirmation_lag_bars": lag}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="momentum",
                                 market_time=now_p["market_time"],
                                 confirmed_at=confirmed,
                                 algo_version=MOMENTUM_VERSION, payload=payload):
                counts["DIVERGENCE"] += 1

        con.commit()
        rec.n_new_facts = sum(counts.values())
        rec.notes = " ".join(f"{k.lower()}={v}" for k, v in counts.items())
        return {"symbol": symbol, "tf": tf, **{k.lower(): v for k, v in counts.items()}}
