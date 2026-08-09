"""Volume engine — relative volume, session VWAP, and where volume actually sat.
algo volume-v0.1-draft.

Why this engine exists. PARTICIPATION is one of the five confluence rows and
this project measures almost none of it. The one existing reading is a single
line inside `swings.evidence` — a bar's volume over its trailing 20-bar average
— which is computed, attached to a promotion, and then never asked anything
else. Volume is the only series in the store that says how many people were
present for a move, and "the level held" versus "the level held on nobody
trading" are different facts that this project has so far recorded identically.

EVIDENCE, GATING NOTHING (house convention 6). Nothing consumes these facts and
nothing may. `setups.py`, `risk.py`, `execsim.py` and `scalein.py` do not import
this module. A factor becomes a filter only after `engine/factorstats.py` grades
it. This is not a formality here, it is the exact mistake this project has
already made with a volume factor: `setups.py` awarded +15 rank points for
"high volume at touch", and when S39 finally graded that term against 228 closed
trades it scored r=+0.09 — inside its own noise floor, 45% of the composite's
variance, and diluting the one term that did work. The rank is retained for
history and decides nothing now. A volume factor that gates a trade before it is
graded is that finding waiting to happen a second time.

SHARED DEFINITIONS, DELIBERATELY. `compute_atr` comes from `swings.py`, the
averages from `ma.py`, and the weekly session boundary from
`aggregator.MONDAY_EPOCH`. None is re-implemented. S40 recorded what the
alternative costs when `ranges.py` kept a private `quote_ticks` that had drifted
from the shared one. The consequence is stated plainly — an `ma-v0.1` rule
change is a `volume-v0.1` rule change, because the same code computes the
average. They must bump together even though this module reads no `ma` FACT.

THE THREE READINGS:

  RELATIVE VOLUME. This bar's volume over the mean of the PREVIOUS 20 bars —
  previous, not including itself, which is the whole point: a spike included in
  its own baseline dilutes its own reading, and at n=20 a 5x bar reports 4.2x.
  The trailing-20 convention is `swings.evidence`'s, reused so that "relative
  volume" means one thing in this codebase.

  SESSION VWAP. Volume-weighted average price since the session anchor, using
  each bar's typical price (high + low + close) / 3. The anchor is the UTC day
  for 15m and 1H, and the Monday-anchored week for 4H and 1D — chosen so that a
  session always contains enough bars for a weighted average to mean anything
  (96, 24, 42 and 7 respectively). 1W gets NO VWAP: a weekly bar IS the session,
  and a one-bar VWAP is that bar's typical price wearing a longer name.

  VOLUME AT LEVEL. A rolling 100-bar volume profile and its point of control —
  the price bin holding the most volume in the window. 100 bars is the horizon
  `liquidity.py` already uses to decide that two swings formed near each other,
  reused rather than re-invented.

    This is an APPROXIMATION and the shape of the error is worth stating: the
    store holds OHLCV bars, not trades, so a bar's entire volume is assigned to
    its typical price. A wide bar really distributed its volume across its whole
    range. The reading is therefore honest about WHERE trade concentrated over
    a hundred bars and dishonest about the fine structure inside any one of
    them, which is why the emission trigger below is a one-ATR relocation and
    not a bin-by-bin migration.

    The price grid is 4 SIGNIFICANT digits, not a fixed tick. A fixed grid
    cannot serve a book that runs from SHIB at 0.0000341 to BTC at 47,000 —
    that is the same failure S40 found in the hard-coded 0.01 tick, at a
    different place in the stack. The grid is exact Decimal arithmetic (the
    decimal exponent and the leading digits), not a rounded logarithm, so a
    price falls in exactly one bin and always the same one.

EMISSION — ON EVENT, NEVER PER BAR.

  All three readings are defined on every bar; per-bar emission is 570,061 rows
  for this engine alone against a store holding ~993k facts in total. Three
  event families are emitted:

    RVOL        unusual participation ARRIVES (HOT >= 2.0x, DRY <= 0.5x)
    VWAP_CROSS  the close crosses the session VWAP
    POC_MOVE    the point of control relocates by >= 1 ATR

  Measured over the whole store: 156,772 facts, 27.5% of bars — RVOL 84,226
  (DRY 51,518, HOT 32,708), VWAP_CROSS 59,877, POC_MOVE 12,669. Per timeframe:
  15m 52,998, 1H 72,235, 4H 15,750, 1D 14,957, 1W 832. This is the loudest of
  the four indicator engines by a wide margin, and that is a finding rather
  than a defect: participation genuinely is the fastest-changing of the five
  confluence rows.

  RVOL emits only the ARRIVAL of an unusual reading, never the return to
  normal. "Volume went back to average" is the absence of an event, and
  emitting it measured 139,859 facts for this family — 24.5% of every bar in
  the store, which is per-bar emission wearing a state machine. The NORMAL
  state is still tracked, because it is what re-arms the next arrival.

  RVOL states are also Schmitt-triggered, like `ma.py`'s slope and
  `momentum.py`'s bands: HOT is entered at 2.0x and left at 1.5x, DRY entered
  at 0.5x and left at 0.7x. Volume is the burstiest series in the store and a
  single threshold makes it chatter hardest — a ratio oscillating either side
  of 2.0 would write a fact per oscillation, none of them describing a change.

  VWAP_CROSS deliberately does NOT emit at each session open. The anchor
  resetting at midnight is a property of the clock, not an event in the market,
  and ~23,000 facts saying "the new session opened somewhere" would bury the
  crossings that are events. The side is re-established silently at the first
  qualifying bar of each session.

  POC_MOVE's threshold is one ATR from the LAST EMITTED point of control, not
  from the previous bar's. That is what makes it a relocation rather than a
  jitter: the 4-significant-digit grid shifts the POC by a bin now and then for
  reasons that are about binning rather than about trade, and a hysteresis
  measured against the last thing actually recorded absorbs all of it.

WARMUP REFUSAL (house convention 7). No RVOL fact before bar index 20 — a
"20-bar average volume" computed from six bars is not a small sample, it is a
different statistic. No VWAP fact until its session holds 3 closed bars. No POC
fact before bar index 100. A bar whose 20-bar baseline volume is ZERO emits
nothing at all rather than an infinite or invented ratio; the same for a session
whose cumulative volume is zero. Both occur on genuinely untraded series and
neither is a number.

WHAT v0.1's POINT OF CONTROL ACTUALLY DESCRIBES, so no consumer has to guess.
Measured over its own 12,669 facts, the POC bin holds a MEDIAN 4.96% of the
window's volume (p10 2.84%, p90 10.19%; by timeframe 6.59 / 4.81 / 3.84 / 3.40 /
3.75 for 15m / 1H / 4H / 1D / 1W). That is a MODAL bin, not a dominant node — a
4-significant-digit grid is between 0.01% and 0.1% of price, and a hundred bars
of a volatile perp traverse hundreds of those, so the volume is spread thin by
construction and the winner wins narrowly. The relocation events are still
meaningful (they are one-ATR moves of the mode) but "the POC" here should not be
read as the high-volume node a real market profile would name. Sizing the bins
to the instrument's own ATR rather than to a fixed relative width is the obvious
v0.2, and it is deliberately not attempted in v0.1: ATR moves within the window,
so an ATR-sized bin grid changes shape underneath its own histogram, and getting
that causal and idempotent is a redesign rather than a constant.

CAUSALITY (house convention 1). Every reading at bar i uses bars up to and
including i and is knowable at bar i's CLOSE: `confirmed_at = open_ts +
tf_seconds`, `market_time = open_ts`. The RVOL baseline is strictly the previous
20 bars, the VWAP accumulates only closed bars of the current session, and the
profile window is strictly trailing. Nothing reads a developing bar.

DECIMAL (house convention 3). No float touches a price. Volumes are Decimal too,
even though they are not prices, because they multiply prices in the VWAP and a
float there would put a float in a price. The only integers are bin indices and
bar counts.

APPEND-ONLY AND IDEMPOTENT (house convention 4). No wall clock, no RNG. The
point-of-control tie-break is explicit (highest volume, then highest bin index)
rather than whatever `max()` happens to reach first in a dict, because a
dict-order tie-break would make the facts depend on insertion history — the
exact non-determinism convention 4 forbids.
"""
from decimal import ROUND_FLOOR, Decimal

from . import store
from .aggregator import MONDAY_EPOCH
from .ma import plain, sig
# The house answer to "did price close THROUGH this level", max(1 tick,
# 0.05*ATR) — the same predicate structure.py, zones.py, liquidity.py and
# ranges.py break a level on. A session VWAP is a level and gets the same rule
# rather than a second one; see the docstring for what it costs not to.
from .ranges import break_tolerance
from .runlog import RunRecorder
from .swings import compute_atr, quote_ticks

VOLUME_VERSION = "volume-v0.2-draft"
# v0.2: input cascade from agg-v0.2 (own 4H/1W candle reads and ma-v0.2
# shared code) — acknowledged-partial buckets; no rule change here. RVOL on a
# thin market is the reading that moves most: partial buckets carry genuinely
# smaller sums, which is the truth about those windows, not a distortion.

RVOL_PERIOD = 20
# Entry / exit pairs. The gap IS the deadband; see the docstring.
RVOL_HOT_IN, RVOL_HOT_OUT = Decimal("2.0"), Decimal("1.5")
RVOL_DRY_IN, RVOL_DRY_OUT = Decimal("0.5"), Decimal("0.7")

# Session anchor per timeframe. 1W is absent on purpose: a weekly bar IS the
# session. An absent key means "this timeframe has no session", not "default to
# a day" — a silent default here would emit a one-bar VWAP and call it an
# average.
SESSION_ANCHOR = {"5m": "DAY", "15m": "DAY", "1H": "DAY",
                  "4H": "WEEK", "1D": "WEEK"}
MIN_SESSION_BARS = 3
DAY_SECONDS = 86400
WEEK_SECONDS = 604800

POC_WINDOW = 100                  # == liquidity.MAX_BARS_APART, see docstring
POC_MOVE_ATR = Decimal(1)
BIN_SIG = 4                       # significant digits per price bin
_BIN_Q = 10 ** (BIN_SIG - 1)
Q2 = Decimal("0.01")


def price_bin(p: Decimal) -> int:
    """Index of the 4-significant-digit bin containing `p`.

    Scale-free by construction: one bin is between 0.01% and 0.1% of price
    everywhere from 0.0000341 to 47,000, which no fixed tick grid can be. Built
    from the Decimal's own exponent and leading digits, so it is exact integer
    arithmetic — a logarithm would give a nicer uniform bin width and would put
    a rounded transcendental between a price and the bin it lands in.
    """
    adj = p.adjusted()
    lead = int(p.scaleb(BIN_SIG - 1 - adj).to_integral_value(rounding=ROUND_FLOOR))
    return adj * 9 * _BIN_Q + (lead - _BIN_Q)


def bin_price(index: int) -> Decimal:
    """The representative (lower-edge) price of a bin. Exact inverse of
    `price_bin` on that edge."""
    adj, rest = divmod(index, 9 * _BIN_Q)
    return Decimal(rest + _BIN_Q).scaleb(adj - (BIN_SIG - 1))


def typical(candle: dict) -> Decimal:
    """(high + low + close) / 3 — the standard single-price proxy for where a
    bar's volume traded, and the only one available without trade data."""
    return (Decimal(candle["high"]) + Decimal(candle["low"])
            + Decimal(candle["close"])) / 3


def session_start(ts: int, anchor: str) -> int:
    """UTC-midnight or Monday-midnight bucket start.

    The weekly boundary is `aggregator.MONDAY_EPOCH`, imported rather than
    restated, so a session week and a 1W candle mean the same seven days.
    """
    if anchor == "WEEK":
        return ts - ((ts - MONDAY_EPOCH) % WEEK_SECONDS)
    return ts - (ts % DAY_SECONDS)


def rvol_state(prev: str | None, ratio: Decimal) -> str:
    """Schmitt-triggered relative-volume state. Enter at 2.0x/0.5x, leave at
    1.5x/0.7x."""
    if ratio >= RVOL_HOT_IN:
        return "HOT"
    if ratio <= RVOL_DRY_IN:
        return "DRY"
    if prev == "HOT" and ratio >= RVOL_HOT_OUT:
        return "HOT"
    if prev == "DRY" and ratio <= RVOL_DRY_OUT:
        return "DRY"
    return "NORMAL"


def point_of_control(profile: dict) -> tuple[int, Decimal]:
    """(bin index, volume) of the heaviest bin.

    The tie-break is explicit — highest volume, then highest bin index — so the
    answer never depends on dict insertion order. That is not a theoretical
    worry: the profile dict is rebuilt bar by bar as bins enter and leave the
    window, so its iteration order encodes the history of the walk, and a
    `max()` that fell back on it would make identical windows produce different
    facts depending on how they were reached.
    """
    return max(profile.items(), key=lambda kv: (kv[1], kv[0]))


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "volume", VOLUME_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        closes = [Decimal(c["close"]) for c in candles]
        volumes = [Decimal(c["volume"]) for c in candles]
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)

        counts = {"RVOL": 0, "VWAP_CROSS": 0, "POC_MOVE": 0}

        def emit(i: int, event: str, extra: dict) -> None:
            c = candles[i]
            payload = {"event": event, "bar_index": i,
                       "close": plain(closes[i]),
                       "volume": plain(volumes[i]), **extra}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="volume",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=VOLUME_VERSION, payload=payload):
                counts[event] += 1

        # --- relative volume -------------------------------------------------
        state, since = None, None
        run_sum = sum(volumes[:RVOL_PERIOD]) if len(volumes) >= RVOL_PERIOD else None
        for i in range(RVOL_PERIOD, len(candles)):
            baseline = run_sum / RVOL_PERIOD
            # Advance the trailing window before anything else can use it, so
            # bar i is never part of its own baseline.
            run_sum += volumes[i] - volumes[i - RVOL_PERIOD]
            if baseline == 0:
                # A ratio against nothing is not a large ratio, it is undefined.
                continue
            ratio = sig(volumes[i] / baseline)
            new = rvol_state(state, ratio)
            if new == state:
                continue
            prev, state, prev_since, since = state, new, since, i
            # Only the ARRIVAL of unusual participation is emitted. The return
            # to normal is tracked (it is what re-arms the next arrival) and not
            # written: "volume went back to average" is the absence of an event,
            # and emitting it took this family from 84,226 facts to 139,859 —
            # 24.5% of every bar in the store, which is the per-bar emission
            # this engine exists to avoid, wearing a state machine.
            if new == "NORMAL":
                continue
            emit(i, "RVOL",
                 {"rvol_state": new, "from": prev,
                  "state": "ESTABLISHED" if prev is None else "CHANGED",
                  "bars_since_prev_state": None if prev_since is None
                  else i - prev_since,
                  "rvol": plain(ratio.quantize(Q2)),
                  "baseline_volume": plain(sig(baseline)),
                  "baseline_bars": RVOL_PERIOD,
                  "hot_at": plain(RVOL_HOT_IN), "dry_at": plain(RVOL_DRY_IN)})

        # --- session VWAP ----------------------------------------------------
        anchor = SESSION_ANCHOR.get(tf)
        if anchor is not None:
            cur_session = None
            pv = vol = Decimal(0)
            bars = 0
            side = None
            for i, c in enumerate(candles):
                s = session_start(c["open_ts"], anchor)
                if s != cur_session:
                    # A new anchor is a new object. Carrying the side across
                    # would report the anchor reset as a crossing.
                    cur_session, pv, vol, bars, side = s, Decimal(0), Decimal(0), 0, None
                pv += typical(c) * volumes[i]
                vol += volumes[i]
                bars += 1
                if bars < MIN_SESSION_BARS or vol == 0:
                    continue
                vwap = sig(pv / vol)
                # The VWAP is a LEVEL, so the question "is price above it" gets
                # the house answer to "did price close through this level" —
                # max(1 tick, 0.05*ATR) — and not a bare comparison. Measured,
                # it removes 4,317 of 64,194 crossings (6.7%): a smaller effect
                # than it looks like it should have, for the same reason
                # `ma.position` records, and kept for the same reason — on a
                # sub-dollar symbol a bare comparison flips on a quote tick.
                tol = break_tolerance(atr[i], ticks[i])
                new = ("ABOVE" if closes[i] > vwap + tol
                       else "BELOW" if closes[i] < vwap - tol else side)
                if new is None or new == side:
                    side = new
                    continue
                if side is not None:
                    emit(i, "VWAP_CROSS",
                         {"side": new, "from": side,
                          "direction": "BULL" if new == "ABOVE" else "BEAR",
                          "vwap": plain(vwap), "tolerance": plain(sig(tol)),
                          "session_start": s,
                          "session_anchor": anchor, "session_bars": bars,
                          "session_volume": plain(sig(vol)),
                          "distance_atr": (None if atr[i] is None or not atr[i]
                                           else plain(((closes[i] - vwap) / atr[i])
                                                      .quantize(Q2)))})
                side = new

        # --- volume at level: rolling profile and its point of control -------
        if len(candles) > POC_WINDOW:
            profile: dict[int, Decimal] = {}
            # Bars per bin, tracked alongside the volume. A bin is dropped when
            # no bar in the window occupies it, NOT when its volume reaches
            # zero: a genuinely untraded bar contributes 0, and evicting its bin
            # on that basis leaves nothing to subtract when the bar itself
            # leaves the window. That is not hypothetical — it is a KeyError on
            # ADAUSDT 1D, which carries zero-volume daily bars.
            occupancy: dict[int, int] = {}
            bins = [price_bin(typical(c)) for c in candles]
            # Running total rather than sum(profile.values()) per bar. It is
            # exact, not merely close: a venue volume string carries at most ~15
            # significant digits, a hundred of them sum to at most ~17, and
            # Decimal's context holds 28 — so no add or subtract in this loop
            # rounds and the total at bar 4,000 equals a fresh window sum.
            total = Decimal(0)
            for i in range(POC_WINDOW):
                profile[bins[i]] = profile.get(bins[i], Decimal(0)) + volumes[i]
                occupancy[bins[i]] = occupancy.get(bins[i], 0) + 1
                total += volumes[i]
            last_poc = None
            for i in range(POC_WINDOW, len(candles)):
                out_bin = bins[i - POC_WINDOW]
                profile[out_bin] -= volumes[i - POC_WINDOW]
                total -= volumes[i - POC_WINDOW]
                occupancy[out_bin] -= 1
                if occupancy[out_bin] == 0:
                    del occupancy[out_bin], profile[out_bin]
                profile[bins[i]] = profile.get(bins[i], Decimal(0)) + volumes[i]
                occupancy[bins[i]] = occupancy.get(bins[i], 0) + 1
                total += volumes[i]
                if total <= 0 or atr[i] is None or not atr[i]:
                    continue
                idx, poc_vol = point_of_control(profile)
                poc = bin_price(idx)
                moved = last_poc is None or abs(poc - last_poc) >= POC_MOVE_ATR * atr[i]
                if not moved:
                    continue
                here = profile.get(bins[i], Decimal(0))
                emit(i, "POC_MOVE",
                     {"state": "ESTABLISHED" if last_poc is None else "CHANGED",
                      "poc": plain(poc), "prev_poc": None if last_poc is None
                      else plain(last_poc),
                      "poc_volume_share": plain((poc_vol / total * 100).quantize(Q2)),
                      "level_volume_share": plain((here / total * 100).quantize(Q2)),
                      "moved_atr": None if last_poc is None
                      else plain((abs(poc - last_poc) / atr[i]).quantize(Q2)),
                      "window_bars": POC_WINDOW,
                      "window_volume": plain(sig(total)),
                      "bin_sig_digits": BIN_SIG,
                      "atr": plain(atr[i])})
                last_poc = poc

        con.commit()
        rec.n_new_facts = sum(counts.values())
        rec.notes = " ".join(f"{k.lower()}={v}" for k, v in counts.items())
        return {"symbol": symbol, "tf": tf,
                **{k.lower(): v for k, v in counts.items()}}
