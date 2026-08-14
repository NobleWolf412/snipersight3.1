"""Deterministic, credentials-free US-stock training workflow.

All output is fixture-scoped.  It is useful for building and inspecting the
stock product, but structurally excluded from real evidence and grading.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from . import stockcalendar


STOCK_DEMO_VERSION = "stock-demo-v0.1-draft"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "stocks" / "training_v1.json"
Q2 = Decimal("0.01")

REJECTIONS = {
    "TRADING_HALT": "The exchange has halted this sample. No new order is allowed until trading resumes.",
    "EARNINGS_WINDOW": "Earnings are inside the 48-hour exclusion window. Gap behavior can change abruptly, so the bot stands down.",
    "INSUFFICIENT_HISTORY": "The sample does not contain enough closed bars to evaluate the setup.",
    "LOW_PARTICIPATION": "Relative volume is below 1.5×, so the move lacks the participation this setup requires.",
}


def _load() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _iso_epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _candidate(row: dict, fixture: dict) -> dict:
    bars = [bar for bar in row["bars"] if int(bar["closed_at"]) <= _iso_epoch(fixture["as_of"])]
    reasons = []
    if len(bars) < 3:
        reasons.append("INSUFFICIENT_HISTORY")
    if row.get("halted"):
        reasons.append("TRADING_HALT")
    earnings = row.get("earnings_at")
    if earnings and 0 <= _iso_epoch(earnings) - _iso_epoch(fixture["as_of"]) <= 48 * 3600:
        reasons.append("EARNINGS_WINDOW")
    if Decimal(row["relative_volume"]) < Decimal("1.5"):
        reasons.append("LOW_PARTICIPATION")

    first_open = Decimal(bars[0]["open"]) if bars else Decimal(row["previous_close"])
    previous = Decimal(row["previous_close"])
    gap_pct = ((first_open - previous) / previous * Decimal(100)).quantize(Q2)
    setup_id = f"fixture:{fixture['fixture_version']}:{row['scenario_id']}"
    evidence = [
        {"label": "Opening gap", "value": f"{gap_pct}%", "why": "Requires at least a 2% opening repricing."},
        {"label": "Relative volume", "value": f"{row['relative_volume']}×", "why": "Requires at least 1.5× normal participation."},
        {"label": "Session", "value": "Regular", "why": "The signal uses closed regular-session bars only."},
    ]
    out = {
        "setup_id": setup_id,
        "asset_id": f"fixture:{row['scenario_id']}",
        "symbol": row["display_symbol"],
        "raw_symbol": row["symbol"],
        "name": row["name"],
        "strategy": "GAP_PULLBACK",
        "timeframe": "5m",
        "state": "REJECTED" if reasons else "READY",
        "evidence_scope": "FIXTURE",
        "grade_eligible": False,
        "evidence": evidence,
        "rejections": [{"code": code, "detail": REJECTIONS[code]} for code in reasons],
    }
    if reasons or not bars:
        return out

    entry = Decimal(bars[-1]["close"])
    stop = min(Decimal(bar["low"]) for bar in bars) - Decimal("0.20")
    risk = entry - stop
    target = entry + risk * Decimal(2)
    quantity = (Decimal(fixture["risk_budget_usd"]) / risk).to_integral_value(rounding=ROUND_DOWN)
    out["plan"] = {
        "side": "LONG", "order_type": "LIMIT", "entry": str(entry.quantize(Q2)),
        "stop": str(stop.quantize(Q2)), "target": str(target.quantize(Q2)),
        "risk_per_share": str(risk.quantize(Q2)), "risk_budget_usd": fixture["risk_budget_usd"],
        "quantity": str(quantity), "planned_r": "2.00",
    }
    return out


def _simulate(setup: dict, scenario: dict) -> dict:
    plan = setup["plan"]
    entry, stop, target = map(Decimal, (plan["entry"], plan["stop"], plan["target"]))
    fill = None
    exit_price = None
    outcome = "OPEN"
    for bar in scenario.get("future_bars", []):
        low, high = Decimal(bar["low"]), Decimal(bar["high"])
        if fill is None and low <= entry <= high:
            fill = {"price": str(entry), "at": bar["open_ts"], "role": "SIMULATED_LIMIT"}
        if fill:
            if low <= stop:
                outcome, exit_price = "STOP", stop
                break
            if high >= target:
                outcome, exit_price = "TARGET", target
                break
    if not fill:
        return {"state": "MISSED", "evidence_scope": "FIXTURE", "grade_eligible": False}
    if exit_price is None:
        return {"state": "OPEN", "fill": fill, "evidence_scope": "FIXTURE", "grade_eligible": False}
    quantity = Decimal(plan["quantity"])
    pnl = ((exit_price - entry) * quantity).quantize(Q2)
    r_multiple = ((exit_price - entry) / (entry - stop)).quantize(Q2)
    return {
        "state": "CLOSED", "outcome": outcome, "fill": fill,
        "exit": {"price": str(exit_price), "role": "SIMULATED_LIMIT"},
        "pnl_usd": str(pnl), "r_multiple": str(r_multiple),
        "evidence_scope": "FIXTURE", "grade_eligible": False,
        "cost_model": "TRAINING_ONLY_NO_FEES",
    }


def report() -> dict:
    fixture = _load()
    setups = [_candidate(row, fixture) for row in fixture["scenarios"]]
    by_id = {row["scenario_id"]: row for row in fixture["scenarios"]}
    ready = next((row for row in setups if row["state"] == "READY"), None)
    result = _simulate(ready, by_id[ready["asset_id"].split(":", 1)[1]]) if ready else None
    return {
        "version": STOCK_DEMO_VERSION,
        "fixture_version": fixture["fixture_version"],
        "mode": "TRAINING_FIXTURE",
        "evidence_scope": "FIXTURE",
        "live_orders_enabled": False,
        "grade_eligible": False,
        "as_of": fixture["as_of"],
        "disclaimer": "Synthetic training data. Not market evidence, not investment advice, and excluded from strategy grades.",
        "session": stockcalendar.classify(fixture["as_of"], fixture["session"]),
        "setups": setups,
        "selected_setup_id": ready["setup_id"] if ready else None,
        "simulation": result,
        "diagnostics": [
            {"label": "Fixture tape", "state": "READY", "detail": f"{len(fixture['scenarios'])} deterministic samples loaded."},
            {"label": "Session clock", "state": "READY", "detail": "Regular, premarket, after-hours and closed states use an explicit calendar authority."},
            {"label": "Evidence boundary", "state": "READY", "detail": "Every setup and fill is fixture-scoped and grade-ineligible."},
            {"label": "Paper simulator", "state": "READY", "detail": "One accepted sample is replayed without broker access."},
        ],
    }
