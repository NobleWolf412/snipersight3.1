"""Trend continuation — buy strength inside an established trend. UNGRADED.

WHY THIS EXISTS, and it is a measurement problem before it is a strategy.
Grading the moving average against the book on 4 Aug 2026 returned this:

    LONG  x price BELOW ribbon   190        LONG  x ABOVE   0
    SHORT x price ABOVE ribbon   146        SHORT x BELOW   0

Not one trade in 477 was taken trend-following. Both existing playbooks enter
counter-move — REVERSAL fades an extreme, PULLBACK buys a dip into demand — so
"does this trade agree with the trend" is a CONSTANT on this book, and a
constant predicts nothing. An entire class of factor (MA position, MA stack,
VWAP side, gap direction) is not merely unproven here; it is UNTESTABLE, and no
amount of further sampling of the current playbooks will change that.

The only way to make those factors answerable is to record trades that buy
strength. That is this module. Its first job is to populate the empty cohort;
whether it also makes money is a question its own sample will answer later.

THE TRIGGER, and every part of it comes from the ribbon rather than a regime
label. `ma.stack` is the trend definition — BULL means the averages are ordered
fast-above-slow by the house break tolerance, which is a geometric fact about
this chart and nothing else. Coupling to `regime` would mean every regime
version bump invalidates every setup here for a reason that has nothing to do
with the trade, which is the argument `ranges.py` and `momentum.py` both make
for staying regime-free.

    1. TREND      ribbon stacked BULL (long) or BEAR (short).
    2. EXTENSION  price was ABOVE the whole ribbon envelope (long).
    3. PULLBACK   price comes back to within PULLBACK_PROX_ATR of the fast
                  average without the envelope position flipping to the far
                  side — a dip inside the trend, not a break of it.
    4. RESUMPTION a bar closes back ABOVE the envelope, in the top third of
                  its own range — `setups.confirms`' conviction test, applied
                  by `resumes`.

At entry, price is above the whole ribbon and the ribbon is stacked. That is
the definition of the cohort the book is missing, so this cannot fail to fill
it — which is the point, and also why its P&L must be judged separately from
its usefulness as evidence.

SHARED, imported rather than reimplemented — the same list `breakout.py` keeps,
for the same reason:
  · `setups.vetoes`, and `setups.REJECTION_FRACTION` — the conviction test
    from `setups.confirms`, reused rather than re-numbered. Its ENGAGEMENT
    test is carried by the pullback leg instead of the confirming bar; see
    `resumes` for the measurement that forced that split.
  · the bracket shape: entry at next bar's open, stop beyond the confirmation
    bar's extreme, target capped at MAX_TARGET_R
  · the entry model (MAKER_THEN_MARKET) and its offset
  · `ma.ema` / `ma.sma` / `ma.stack` / `ma.position` — the ribbon is computed
    with the ENGINE'S OWN functions, never a private copy. ma.py states the
    rule: "two implementations of one average is how they come to disagree."
    The consequence is that an `ma-v0.1` rule change is a `trend-v0.1` rule
    change even though this module reads no `ma` FACT, and the version cascade
    records that.

So this changes WHERE a trade comes from, not HOW it is executed or sized.

**MEASURED AND NOT ENABLED.** It emits setup facts under its own version, which
neither `execsim` nor `risk` queries, so it trades nothing — the same
structural isolation that keeps `breakout` out of the book. It ships switched
off, it accumulates a sample, and it earns a place only by clearing the same
bar every other factor here has failed: an interval above zero. Shipping it on
plausibility is exactly what this codebase refuses to do.

Usage (from app/):
  python -m engine.trend BTCUSDT 1H
"""
import json
from decimal import Decimal

from . import costs, ma, store
from .ma import MA_VERSION
from .setups import (ENTRY_MAX_BARS, ENTRY_MODEL, MAKER_OFFSET_R,
                     MAKER_WAIT_BARS, MAX_TARGET_R, MIN_RR,
                     MIN_RISK_COST_MULT, Q2, REJECTION_FRACTION,
                     SL_BUFFER_ATR, vetoes)
from .runlog import RunRecorder
from .swings import SWING_VERSION, compute_atr, quote_ticks

TREND_VERSION = "trend-v0.1-draft"

#: How near the fast average counts as a pullback. Wider than the break
#: tolerance on purpose: a trend pullback that only grazes the average is not
#: the retest this trades, and one that punches through it is a break.
PULLBACK_PROX_ATR = Decimal("0.60")

#: Bars a pullback may last and still be one. Beyond this, price is not pulling
#: back to the average — the average has caught up to price, which is a
#: different market and not this trade.
PULLBACK_MAX_BARS = 10

#: Bars after the pullback in which the resumption must confirm.
RESUME_MAX_BARS = 6

#: Minimum bars of established extension before a pullback counts, so a single
#: bar poking above a freshly-crossed ribbon cannot arm this.
MIN_EXTENSION_BARS = 3


def resumes(candle: dict, direction: str, edge: Decimal) -> bool:
    """Did this CLOSED bar prove the trend resumed?

    `setups.confirms` requires three things of a zone touch, and only the FIRST
    of them is wrong here:

      1. the bar engaged the level          low <= top
      2. and closed back out of it          close > top
      3. with the close in the upper third  close >= low + 0.66 * (high - low)

    (1) assumes the engagement and the rejection happen on ONE bar, which is
    true of a zone that price dips into and leaves. A trend pullback is a LEG:
    price spends several bars inside the ribbon envelope and then closes back
    out of it, and the bar that closes out often never trades down to the edge
    again. Requiring (1) of the resumption bar therefore rejects the textbook
    case — measured on a synthetic continuation, every candidate failed on
    `low <= edge` while satisfying both of the conditions that carry meaning.

    So the engagement test is carried by the LEG (the caller only reaches here
    after the envelope position has been INSIDE or at the fast average), and
    this keeps (2) and (3) verbatim, including `setups.REJECTION_FRACTION`
    rather than a second copy of the number. (3) is the one that matters: it is
    what separates a bar that reclaimed the trend from one that drifted back
    over the line.
    """
    hi, lo = Decimal(candle["high"]), Decimal(candle["low"])
    close = Decimal(candle["close"])
    rng = hi - lo
    if direction == "LONG":
        if close <= edge:
            return False
        return rng <= 0 or close >= lo + REJECTION_FRACTION * rng
    if close >= edge:
        return False
    return rng <= 0 or close <= hi - REJECTION_FRACTION * rng


def _ribbon(candles: list) -> list[list[Decimal]]:
    """Per-bar ribbon values, computed with ma.py's OWN functions.

    Returns one list per bar, ordered fast-to-slow, or None where any average
    has insufficient history. Never a private EMA: see the module docstring.
    """
    closes = [Decimal(c["close"]) for c in candles]
    series = []
    for _name, kind, period in ma.RIBBON:
        series.append(ma.ema(closes, period) if kind == "EMA"
                      else ma.sma(closes, period))
    out = []
    for i in range(len(candles)):
        vals = [s[i] for s in series]
        out.append(None if any(v is None for v in vals) else vals)
    return out


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "trend", TREND_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        # the slowest ribbon member needs its full window before anything here
        # can describe a trend
        if len(candles) < 210:
            return {"symbol": symbol, "tf": tf, "setups": 0, "rejected": 0}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)
        ribbon = _ribbon(candles)
        rec.n_inputs = sum(1 for r in ribbon if r is not None)
        profile = costs.profile_for(symbol)
        cost_manifest_hash = costs.record(con, profile)
        manifest_hash = store.record_manifest(con, "strategy", {
            "version": TREND_VERSION,
            "pullback_prox_atr": str(PULLBACK_PROX_ATR),
            "pullback_max_bars": PULLBACK_MAX_BARS,
            "resume_max_bars": RESUME_MAX_BARS,
            "min_extension_bars": MIN_EXTENSION_BARS,
            "min_rr": str(MIN_RR), "max_target_r": str(MAX_TARGET_R),
            "entry_model": ENTRY_MODEL,
            "ribbon": [[n, k, p] for n, k, p in ma.RIBBON],
            "cost_profile": profile.payload(),
            # No `regime` input, deliberately — see the docstring. `ma` is
            # listed because this computes the ribbon with ma's functions, so
            # an ma rule change is a rule change here.
            "inputs": {"ma": MA_VERSION, "swing": SWING_VERSION},
        })

        tier_swings = {"HIGH": [], "LOW": []}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ("INTERMEDIATE", "MAJOR"):
                tier_swings[p["type"]].append(
                    {"confirmed_at": r["confirmed_at"], "price": Decimal(p["price"])})

        def target(direction, entry, as_of):
            side = "HIGH" if direction == "LONG" else "LOW"
            beyond = [s["price"] for s in tier_swings[side]
                      if s["confirmed_at"] <= as_of
                      and (s["price"] > entry if direction == "LONG"
                           else s["price"] < entry)]
            if not beyond:
                return None
            return min(beyond) if direction == "LONG" else max(beyond)

        n_setups = n_rejected = 0
        extended = 0            # consecutive bars price has held beyond the ribbon
        pullback_at = None      # bar index where the dip to the average began
        pullback_ext = None     # its extreme, which becomes the stop reference
        side = None

        for i in range(len(candles)):
            vals, a = ribbon[i], atr[i]
            if vals is None or a is None or a <= 0:
                extended, pullback_at = 0, None
                continue
            c = candles[i]
            close = Decimal(c["close"])
            tol = ma.SLOPE_DEADBAND_ATR * a
            st = ma.stack(vals, tol)
            pos = ma.position(close, vals, tol)
            want = "LONG" if st == "BULL" else "SHORT" if st == "BEAR" else None

            if want is None:                       # ribbon entwined: no trend
                extended, pullback_at, side = 0, None, None
                continue
            if side != want:                       # trend flipped: start over
                extended, pullback_at, side = 0, None, want

            beyond = "ABOVE" if want == "LONG" else "BELOW"
            fast = vals[0]
            near_fast = (abs(close - fast) <= PULLBACK_PROX_ATR * a)
            broke = (pos == ("BELOW" if want == "LONG" else "ABOVE"))

            if broke:                              # trend structure lost
                extended, pullback_at = 0, None
                continue

            if pullback_at is None:
                # still building the extension leg
                if pos == beyond:
                    extended += 1
                    if extended >= MIN_EXTENSION_BARS and near_fast:
                        pullback_at, pullback_ext = i, (
                            Decimal(c["low"]) if want == "LONG"
                            else Decimal(c["high"]))
                elif pos == "INSIDE" and extended >= MIN_EXTENSION_BARS:
                    pullback_at, pullback_ext = i, (
                        Decimal(c["low"]) if want == "LONG"
                        else Decimal(c["high"]))
                continue

            # --- inside a pullback: track its extreme, wait for resumption ---
            pullback_ext = (min(pullback_ext, Decimal(c["low"])) if want == "LONG"
                            else max(pullback_ext, Decimal(c["high"])))
            if i - pullback_at > PULLBACK_MAX_BARS + RESUME_MAX_BARS:
                extended, pullback_at = 0, None    # not a pullback any more
                continue
            if pos != beyond:
                continue                           # not resumed yet

            # The envelope edge is treated as a band so the SAME confirmation
            # predicate applies as it does to a zone. Reusing setups.confirms
            # rather than restating it is the point.
            edge = max(vals) if want == "LONG" else min(vals)
            if not resumes(c, want, edge):
                continue
            if i + 1 >= len(candles):
                break                              # next bar has not closed

            entry = Decimal(candles[i + 1]["open"])
            if want == "LONG":
                sl = min(pullback_ext, Decimal(c["low"])) - SL_BUFFER_ATR * a
            else:
                sl = max(pullback_ext, Decimal(c["high"])) + SL_BUFFER_ATR * a
            risk = (entry - sl) if want == "LONG" else (sl - entry)
            bct = c["open_ts"] + tf_seconds
            bars_pulling = i - pullback_at
            extended, pullback_at = 0, None        # consumed either way

            if risk <= 0:
                continue
            if vetoes(confirm_bar=c, atr_at_confirm=a, entry=entry, sl=sl,
                      tick=ticks[i]):
                n_rejected += 1
                continue
            tp_uncapped = target(want, entry, bct)
            if tp_uncapped is None:
                n_rejected += 1
                continue
            cap = ((entry + MAX_TARGET_R * risk) if want == "LONG"
                   else (entry - MAX_TARGET_R * risk))
            tp = (min(tp_uncapped, cap) if want == "LONG"
                  else max(tp_uncapped, cap))
            rr = (((tp - entry) if want == "LONG" else (entry - tp))
                  / risk).quantize(Q2)
            if rr < MIN_RR:
                n_rejected += 1
                continue
            if risk < MIN_RISK_COST_MULT * costs.estimated_round_trip_cost(
                    entry, a, profile, symbol=symbol, tf_seconds=tf_seconds):
                n_rejected += 1
                continue

            maker_limit = ((entry - MAKER_OFFSET_R * risk) if want == "LONG"
                           else (entry + MAKER_OFFSET_R * risk))
            setup_id = (f"{symbol}|{tf}|TREND_CONTINUATION|{c['open_ts']}"
                        f"|{TREND_VERSION}")
            payload = {
                "setup_id": setup_id, "strategy": "TREND_CONTINUATION",
                "direction": want, "state": "VALIDATED",
                "entry": str(entry), "sl": str(sl), "tp": str(tp),
                "tp_uncapped": str(tp_uncapped), "rr": str(rr),
                "rank": 0,                    # rank is retired; see setups.py S39
                "maker_limit": str(maker_limit),
                "maker_wait_bars": MAKER_WAIT_BARS,
                "entry_model": ENTRY_MODEL,
                "ribbon_stack": st,
                "ribbon_edge": str(edge),
                "pullback_bars": bars_pulling,
                "pullback_extreme": str(pullback_ext),
                "confirmed_bar_ts": c["open_ts"],
                "why": (f"{st.lower()} ribbon held · price pulled back to the "
                        f"fast average for {bars_pulling} bar"
                        f"{'' if bars_pulling == 1 else 's'} and closed back "
                        f"{'above' if want == 'LONG' else 'below'} the ribbon "
                        f"· R:R {rr}"),
                "manifest_hash": manifest_hash,
                "cost_manifest_hash": cost_manifest_hash,
                "armed": False, "armed_at": bct,
                "expiry_bar_count": ENTRY_MAX_BARS,
                "expires_at_ts": bct + ENTRY_MAX_BARS * tf_seconds,
                "inherited_from_forming": False, "forming_id": None,
                "size_units": None, "risk_usd": None, "notional_usd": None,
                "implied_leverage": None, "risk_decision": None,
                "risk_reasons": [],
            }
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=c["open_ts"], confirmed_at=bct,
                                 algo_version=TREND_VERSION, payload=payload):
                n_setups += 1

        con.commit()
        rec.n_new_facts = n_setups
        rec.notes = f"rejected={n_rejected}"
        return {"symbol": symbol, "tf": tf, "setups": n_setups,
                "rejected": n_rejected}


def main(argv=None) -> int:
    import argparse
    from .importer import TF_SECONDS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("symbol")
    ap.add_argument("tf")
    args = ap.parse_args(argv)
    con = store.connect()
    try:
        print(json.dumps(run(con, args.symbol, args.tf,
                             TF_SECONDS[args.tf]), indent=2))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
