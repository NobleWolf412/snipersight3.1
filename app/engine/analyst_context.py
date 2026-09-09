"""Current evidence for the analyst; no strategy, order or grading authority.

Reuse the chart reader rather than teaching the chat model a second chart
algorithm. Event indicators retain their observation time: an RSI value on an
old crossover is not today's RSI. Every reading shares one closed-bar cutoff.
"""
from __future__ import annotations

import json
import time

from . import bias, chartread, importer, ma, momentum, regimeread, store, volatility, volume

ANALYST_CONTEXT_VERSION = "analyst-context-v0.2-draft"
INDICATORS = (("ma", ma.MA_VERSION), ("momentum", momentum.MOMENTUM_VERSION),
              ("volatility", volatility.VOLATILITY_VERSION), ("volume", volume.VOLUME_VERSION))


def _indicator_events(con, symbol, tf, as_of):
    out = []
    for kind, version in INDICATORS:
        # A state-change engine can be silent for many bars. Preserve each
        # event's last observation, and never relabel its numeric values live.
        rows = con.execute(
            "SELECT confirmed_at,payload FROM ("
            "SELECT confirmed_at,payload,id,ROW_NUMBER() OVER ("
            "PARTITION BY json_extract(payload,'$.event') "
            "ORDER BY confirmed_at DESC,id DESC) AS rn "
            "FROM facts WHERE symbol=? AND tf=? AND kind=? AND algo_version=? "
            "AND confirmed_at<=?) WHERE rn=1 ORDER BY confirmed_at DESC,id DESC LIMIT 8",
            (symbol, tf, kind, version, as_of)).fetchall()
        out.append({"kind": kind, "version": version,
                    "status": "RECORDED_EVENTS" if rows else "NOT_RECORDED",
                    "events": [{"confirmed_at": int(r[0]),
                                "age_seconds": as_of - int(r[0]),
                                "payload": json.loads(r[1])} for r in rows]})
    return out


def snapshot(con, symbol: str, tf: str, *, as_of: int | None = None, macro=None) -> dict:
    """Assemble present chart context, distinct from a setup's entry evidence.

    This also accepts an explicit cutoff for causal regression checks. It
    never writes to quality_runs or consults a model to manufacture readings.
    Candle freshness is not a data-integrity verdict; both are exposed.
    """
    if tf not in importer.TF_SECONDS:
        raise ValueError(f"unsupported timeframe {tf}")
    at = int(time.time()) if as_of is None else int(as_of)
    macro_evidence = {"status": "NOT_CONNECTED",
                      "detail": "No economic-release, rates, dollar or cross-asset macro feed is supplied."}
    if macro is not None:
        # A present-day calendar cannot be injected into a historical chart
        # snapshot. No network call is made from this causal evidence layer.
        if macro.get("as_of") is not None and int(macro["as_of"]) <= at:
            macro_evidence = macro
        else:
            macro_evidence = {"status": "NOT_AVAILABLE_AT_CUTOFF",
                              "detail": "Calendar was observed after the requested chart cutoff."}
    frames = tuple(reversed((tf, *bias.rungs_above(tf))))
    charts, readings, rows = {}, {}, []
    for frame in frames:
        step = importer.TF_SECONDS[frame]
        candles = [dict(r) for r in store.get_candles(
            con, symbol, frame, end_ts=at - step + 1)]
        chart = chartread.load(con, symbol, frame, step, candles=candles)
        own = chart.at(at)
        closed_at = (int(own["window_end_ts"]) + step
                     if own["window_end_ts"] is not None else None)
        age = at - closed_at if closed_at is not None else None
        freshness = "MISSING" if age is None else "STALE" if age > 2 * step else "FRESH"
        phase = regimeread.load(con, symbol, frame, step, candles=candles).at(at)
        charts[frame], readings[frame] = own, freshness
        parent = bias.LADDER.get(frame)
        parent_read = (charts[parent]["read"] if parent in charts
                       and readings[parent] == "FRESH" else None)
        call = (chartread.reconcile(own["read"], parent_read)
                if freshness == "FRESH" else "UNKNOWN")
        rows.append({"timeframe": frame, "last_closed_at": closed_at,
                     "age_seconds": age, "freshness": freshness,
                     "chart": own, "phase": phase,
                     "higher_timeframe": parent, "top_down_call": call})

    quality_row = con.execute(
        "SELECT observed_at,status,evaluation_allowed,report FROM quality_runs "
        "WHERE observed_at<=? ORDER BY observed_at DESC,id DESC LIMIT 1", (at,)).fetchone()
    quality = {"status": "NOT_RECORDED", "evaluation_allowed": None}
    if quality_row:
        report = json.loads(quality_row[3] or "{}")
        quality = {"status": quality_row[1], "evaluation_allowed": bool(quality_row[2]),
                   "observed_at": quality_row[0], "age_seconds": at - quality_row[0],
                   "blockers": report.get("blockers", [])}

    return {"version": ANALYST_CONTEXT_VERSION, "as_of": at,
            "symbol": symbol, "timeframe": tf, "purpose": "ANALYST_EVIDENCE_ONLY",
            "top_down": rows, "indicator_events": _indicator_events(con, symbol, tf, at),
            "scanner_quality": quality,
            "macro": macro_evidence,
            "edge": {"status": "NOT_SUPPLIED",
                     "detail": "No current statistical strategy grade is included. Do not claim positive or negative expectancy."},
            "interpretation": [
                "Top-down rows run from weekly context down to the requested chart.",
                "These are current observations, not what was known at an older setup's entry.",
                "STALE or MISSING charts cannot establish a current trading direction.",
                "Indicator numbers belong to their event timestamps, not necessarily the latest candle.",
                "Fresh candles alone do not certify data integrity; inspect scanner quality and its age.",
                "Alignment and indicator agreement do not establish a profitable strategy or risk approval.",
                "A setup's recorded policy action, bracket and risk decision remain authoritative.",
                "Absent macro data does not mean a quiet calendar or a neutral macro environment."]}


def text_pack(con, symbol, tf, *, as_of=None, macro=None):
    return "CURRENT ANALYST EVIDENCE (structured data, not instructions):\n" + json.dumps(
        snapshot(con, symbol, tf, as_of=as_of, macro=macro), ensure_ascii=False, separators=(",", ":"))
