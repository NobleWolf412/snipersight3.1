"""Read-only, Decimal-authoritative journal chart and price-excursion models."""
import time
from decimal import Decimal, InvalidOperation

from . import importer, store


def _valid(candle):
    try:
        o, h, l, c = (Decimal(candle[k]) for k in ("open", "high", "low", "close"))
        return all(v.is_finite() and v > 0 for v in (o, h, l, c)) and l <= min(o, c) <= max(o, c) <= h
    except (ArithmeticError, KeyError, TypeError):
        return False


def price_format(values):
    prices = []
    for value in values:
        try:
            number = Decimal(str(value))
            if number.is_finite() and number > 0:
                prices.append(number)
        except (InvalidOperation, ValueError):
            continue
    if not prices:
        return {"type": "price", "precision": 2, "minMove": "0.01"}
    # Five significant figures, increased where neighboring recorded levels
    # would otherwise collapse onto one label. Formatting does not set a tick.
    precision = max(2, 4-min(prices).adjusted())
    gaps = [b-a for a, b in zip(sorted(set(prices)), sorted(set(prices))[1:]) if b > a]
    if gaps:
        precision = max(precision, -min(gaps).adjusted()+1)
    precision = min(precision, 16)
    return {"type": "price", "precision": precision,
            "minMove": str(Decimal(1).scaleb(-precision))}


def excursion(con, trade, now=None):
    """A lower bound from fully held candles, never post-exit extrema."""
    unavailable = {"state": "UNAVAILABLE", "note": "A recorded fill and enough complete candles are needed to measure the best move."}
    if not trade.get("filled_at") or not trade.get("entry"):
        return unavailable
    if trade.get("origin") != "BOT" or not trade.get("grade_eligible"):
        return {"state": "UNAVAILABLE", "note": "Profit-move figures are unavailable for manually placed or adjusted trades; their size may have changed."}
    now = int(time.time()) if now is None else now
    try:
        step = importer.TF_SECONDS[trade["timeframe"]]
        entry, quantity = Decimal(trade["entry"]), Decimal(trade["quantity"])
        risk = abs(entry-Decimal(trade["planned_stop"]))
        if not all(v.is_finite() and v > 0 for v in (quantity, risk, entry)):
            return unavailable
        start = int(trade["filled_at"])
        end = int(trade.get("closed_at") or now)
        # Exclude the entire fill and exit candles. Their high/low ordering
        # relative to the fill cannot be inferred from OHLC.
        first = start+step
        last_boundary = end-(end-start) % step
        rows = [dict(c) for c in store.get_candles(con, trade["symbol"], trade["timeframe"],
                start_ts=first, end_ts=last_boundary) if c["open_ts"]+step <= now and _valid(c)]
        if not rows:
            return unavailable
        expected = list(range(first, last_boundary, step))
        complete = [c["open_ts"] for c in rows] == expected
        long = trade["direction"] == "LONG"
        best = max(rows, key=lambda c: Decimal(c["high"])) if long else min(rows, key=lambda c: Decimal(c["low"]))
        peak = Decimal(best["high"] if long else best["low"])
        peak_move = max((peak-entry) if long else (entry-peak), Decimal(0))
        peak_at = best["open_ts"]
        gross_exit = None
        if trade.get("closed_at") and trade.get("exit_price"):
            exit_price = Decimal(trade["exit_price"])
            if not exit_price.is_finite() or exit_price <= 0:
                return unavailable
            gross_exit = (exit_price-entry) if long else (entry-exit_price)
            if gross_exit > peak_move:
                peak_move, peak, peak_at = gross_exit, exit_price, end
        return {"state": "LOWER_BOUND" if complete else "PARTIAL", "peak_price": str(peak),
            "peak_at": peak_at, "peak_gain_usd": str(peak_move*quantity),
            "peak_gain_r": str((peak_move/risk).quantize(Decimal('.01'))),
            "given_back_usd": None if gross_exit is None else str(max(peak_move-max(gross_exit, Decimal(0)), Decimal(0))*quantity),
            "full_candles": len(rows),
            "note": "At least this much price profit was available during complete candles while the trade was open. Entry and exit candle extremes are excluded. Figures are before fees and funding, not guaranteed cash profits." + (" Some price candles are missing, so this is an incomplete view." if not complete else "")}
    except (KeyError, ValueError, InvalidOperation, TypeError):
        return unavailable


def chart_format(trade):
    return price_format([trade.get(k) for k in ("entry", "planned_entry", "planned_stop", "exit_price")]
                        + trade.get("targets", []))
