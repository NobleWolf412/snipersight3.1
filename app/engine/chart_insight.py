"""Read-only presentation of existing chart evidence. Never writes trading facts."""
from . import analyst_context, chartread, setups

INSIGHT_VERSION = "chart-insight-v0.1-draft"


def snapshot(con, symbol, tf, *, as_of=None):
    evidence = analyst_context.snapshot(con, symbol, tf, as_of=as_of)
    frames = []
    for row in evidence["top_down"]:
        chart = row["chart"]
        start, end = chart.get("window_start_ts"), chart.get("window_end_ts")
        count = con.execute(
            "SELECT COUNT(*) FROM candles WHERE symbol=? AND tf=? AND open_ts>=? AND open_ts<=?",
            (symbol, row["timeframe"], start, end)).fetchone()[0] if start is not None else 0
        frames.append({"timeframe": row["timeframe"], "freshness": row["freshness"],
                       "last_closed_at": row["last_closed_at"],
                       "window_start": start, "window_end": end,
                       "lookback_bars": count, "target_bars": chartread.window_bars(row["timeframe"]),
                       "read": chart["read"], "direction": chart.get("bias"),
                       "location": chart.get("location"), "phase": row["phase"]["phase"],
                       "trading_regime": row["phase"]["regime"],
                       "top_down_call": row["top_down_call"]})
    return {"version": INSIGHT_VERSION, "symbol": symbol, "timeframe": tf,
            "as_of": evidence["as_of"], "basis": "CURRENT_CLOSED_CANDLES",
            "frames": frames, "scanner_quality": evidence["scanner_quality"],
            "usage": {"regime": "TRADING_INPUT",
                      "chart": "OBSERVATION_ONLY" if all(v == "ALLOW" for v in setups.WINDOW_POLICY.values()) else "POLICY_DEPENDENT",
                      "higher_timeframes": "OBSERVATION_ONLY" if all(v == "ALLOW" for v in setups.BIAS_POLICY.values()) and all(v == "ALLOW" for v in setups.PULLBACK_CONTEXT_POLICY.values()) else "POLICY_DEPENDENT"},
            "notice": "Current chart context is not trade approval or a reconstruction of an earlier decision."}
