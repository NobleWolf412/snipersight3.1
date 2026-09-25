"""One closed-candle profit-protection decision for paper and private custody.

An intent pins OFF or COST_COVER at creation.  A candidate is considered only
after a complete parent candle survived, reached +1R, and had an available ATR
for an adverse protective-stop fill.  Execution adapters decide how to amend
their own stop; this module never routes an order.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from . import costs, execsim


PROFIT_PROTECTION_VERSION = "profit-protection-v0.2-draft"
OFF = "OFF"
COST_COVER = "COST_COVER"


def candidate(*, policy: str, symbol: str, direction: str, entry: Decimal,
              original_stop: Decimal, current_stop: Decimal,
              target: Decimal | None, bar: dict, bars_survived: int,
              atr: Decimal | None, entry_role: str, tf_seconds: int,
              tick: Decimal | None = None) -> Decimal | None:
    """Return a tighter cost-cover stop effective after this bar, or None.

    The caller must check this bar's existing stop and target *before* calling.
    A late scanner cannot use this decision to alter an earlier candle.
    """
    if policy != COST_COVER or bars_survived < 2 or atr is None:
        return None
    entry, original_stop, current_stop, atr = map(
        Decimal, (entry, original_stop, current_stop, atr))
    if not all(x.is_finite() and x > 0 for x in
               (entry, original_stop, current_stop, atr)):
        return None
    long = direction == "LONG"
    risk = entry-original_stop if long else original_stop-entry
    if risk <= 0 or entry_role not in ("MAKER", "TAKER"):
        return None
    high, low = Decimal(bar["high"]), Decimal(bar["low"])
    if (high-entry < risk) if long else (entry-low < risk):
        return None
    profile = costs.profile_for(symbol)
    # One future candle is charged because the amended stop cannot fill in
    # the confirmation bar.  The estimate deliberately includes adverse
    # slippage and a taker exit, matching the paper settlement convention.
    st = execsim.settle(profile, symbol, entry, entry, risk, long, "SL",
                        bars_survived+1, tf_seconds, atr,
                        entry_role=entry_role)
    entry_fee = (profile.maker_rate if entry_role == "MAKER"
                 else profile.taker_rate)
    if long:
        stop = ((entry*(1+entry_fee)+st["funding"])/
                (1-profile.taker_rate)+st["slip"])
    else:
        stop = ((entry*(1-entry_fee)-st["funding"])/
                (1+profile.taker_rate)-st["slip"])
    if tick is not None:
        tick = Decimal(tick)
        if not tick.is_finite() or tick <= 0:
            return None
        rounding = ROUND_CEILING if long else ROUND_FLOOR
        stop = (stop/tick).to_integral_value(rounding=rounding)*tick
    if long:
        return stop if (current_stop < stop < Decimal(bar["close"]) and
                        (target is None or stop < target)) else None
    return stop if (current_stop > stop > Decimal(bar["close"]) and
                    (target is None or stop > target)) else None


def walk_paper(*, policy: str, symbol: str, direction: str,
               entry: Decimal, original_stop: Decimal, target: Decimal | None,
               bars: list[dict], atr: list[Decimal | None], entry_role: str,
               tf_seconds: int, max_bars: int, cutoff: int, observed_at: int,
               scheduled_move: dict | None = None) -> dict:
    """Replay a stop scheduled at observation time, then consider one fresh bar.

    Historical candles can resolve a trade, but cannot retrospectively create
    a protective amendment.  Only the latest closed bar may propose a move,
    and the scanner's decision time determines when it becomes effective.
    """
    if policy not in (OFF, COST_COVER):
        raise ValueError("unknown profit-protection policy")
    if len(atr) != len(bars):
        raise ValueError("ATR must align with paper bars")
    long = direction == "LONG"
    stop = Decimal(original_stop)
    tp = (Decimal(target) if target is not None else
          (Decimal("Infinity") if long else Decimal("-Infinity")))
    proposal = None
    for j, bar in enumerate(bars[:max_bars]):
        if scheduled_move and int(bar["open_ts"]) >= scheduled_move["effective_at"]:
            stop = Decimal(scheduled_move["stop"])
        hi, lo = Decimal(bar["high"]), Decimal(bar["low"])
        hit_stop = lo <= stop if long else hi >= stop
        hit_target = hi >= tp if long else lo <= tp
        if hit_stop or hit_target:
            price = stop if hit_stop else tp
            if hit_stop and j > 0:
                price = execsim.stop_gap_fill(stop, Decimal(bar["open"]), long)
            return {"exit": ("SL" if hit_stop else "TP", price, j,
                             hit_stop and hit_target),
                    "stop": stop, "proposal": None}
        if j+1 >= max_bars:
            return {"exit": ("TIMEOUT", Decimal(bar["close"]), j, False),
                    "stop": stop, "proposal": None}
        closed_at = int(bar["open_ts"])+tf_seconds
        if (scheduled_move is None and j == len(bars)-1 and
                closed_at <= cutoff and observed_at < closed_at+tf_seconds):
            next_stop = candidate(
                policy=policy, symbol=symbol, direction=direction, entry=entry,
                original_stop=original_stop, current_stop=stop, target=target,
                bar=bar, bars_survived=j+1, atr=atr[j], entry_role=entry_role,
                tf_seconds=tf_seconds)
            if next_stop is not None:
                proposal = {"confirmed_at": closed_at,
                            "observed_at": observed_at,
                            "effective_at": ((observed_at+tf_seconds-1)//tf_seconds)*tf_seconds,
                            "stop": str(next_stop),
                            "reason": "COST_COVER_AFTER_1R",
                            "version": PROFIT_PROTECTION_VERSION}
    if scheduled_move and observed_at >= scheduled_move["effective_at"]:
        stop = Decimal(scheduled_move["stop"])
    return {"exit": None, "stop": stop, "proposal": proposal}
