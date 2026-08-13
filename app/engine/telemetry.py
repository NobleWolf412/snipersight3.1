"""Observational setup lifecycle telemetry.

This module never creates signals or changes decisions. It joins already
recorded setup, risk, order, and execution facts so failures can be attributed
to the strategy, portfolio authority, entry model, or exit economics.
"""
from __future__ import annotations

from collections import Counter

from . import diagnostics


NON_FAILURES = {"WINNER", "OPEN_POSITION", "WAITING_FOR_FILL", "AWAITING_RISK"}
NORMAL_OUTCOMES = {
    "WINNER", "STOP_LOSS", "LOSING_EXIT", "TIMEOUT_EXIT",
    "ENTRY_NOT_FILLED", "COSTS_ERASED_EDGE", "OPEN_POSITION",
    "WAITING_FOR_FILL", "AWAITING_RISK", "RISK_REJECTED",
}


def classify_failure(risk: dict | None, order: dict | None,
                     execution: dict | None) -> dict:
    """Return one mutually-exclusive lifecycle state and diagnostic owner."""
    if risk and risk.get("decision") == "REJECTED":
        reasons = risk.get("reasons") or ["UNSPECIFIED"]
        return {"stage": "RISK REJECTED", "failure_code": "RISK_REJECTED",
                "failure_owner": "PORTFOLIO", "detail": " · ".join(reasons)}

    if execution:
        outcome = execution.get("outcome")
        if outcome == "MISSED":
            return {"stage": "MISSED", "failure_code": "ENTRY_NOT_FILLED",
                    "failure_owner": "EXECUTION",
                    "detail": "limit was not touched inside the entry window"}
        if outcome == "SL":
            return {"stage": "CLOSED", "failure_code": "STOP_LOSS",
                    "failure_owner": "SETUP_OR_STOP",
                    "detail": "price reached structural invalidation before target"}
        if outcome == "TIMEOUT":
            return {"stage": "CLOSED", "failure_code": "TIMEOUT_EXIT",
                    "failure_owner": "EXIT_LOGIC",
                    "detail": "target and stop were unresolved at the holding limit"}
        net_r = float(execution.get("r_multiple") or 0)
        gross_r = float(execution.get("r_gross") or net_r)
        if net_r <= 0 < gross_r:
            return {"stage": "CLOSED", "failure_code": "COSTS_ERASED_EDGE",
                    "failure_owner": "ECONOMICS",
                    "detail": "gross-positive move became non-positive after costs"}
        if net_r > 0:
            return {"stage": "CLOSED", "failure_code": "WINNER",
                    "failure_owner": None, "detail": "closed with positive net R"}
        return {"stage": "CLOSED", "failure_code": "LOSING_EXIT",
                "failure_owner": "EXIT_LOGIC", "detail": f"{outcome or 'exit'} closed at non-positive net R"}

    if order and order.get("event") == "FILLED":
        return {"stage": "OPEN", "failure_code": "OPEN_POSITION",
                "failure_owner": None, "detail": "filled; no terminal exit fact yet"}
    if order and order.get("event") == "MISSED":
        return {"stage": "MISSED", "failure_code": "ENTRY_NOT_FILLED",
                "failure_owner": "EXECUTION",
                "detail": "limit expired before a fill"}
    if order and order.get("event") == "PLACED":
        return {"stage": "ORDER PENDING", "failure_code": "WAITING_FOR_FILL",
                "failure_owner": None, "detail": "limit is inside its fill window"}
    return {"stage": "VALIDATED", "failure_code": "AWAITING_RISK",
            "failure_owner": None, "detail": "validated; no downstream decision recorded yet"}


def build_record(setup: dict, risk: dict | None = None,
                 order: dict | None = None,
                 execution: dict | None = None) -> dict:
    lifecycle = classify_failure(risk, order, execution)
    entry = float(setup["entry"])
    stop = float(setup["sl"])
    target = float(setup["tp"])
    stop_distance = abs(entry - stop)
    reward_distance = abs(target - entry)
    diagnostic_events = diagnostics.explain_lifecycle(
        setup, risk, order, execution, lifecycle)
    defect_count = sum(d["category"] in {"SYSTEM_DEFECT", "MISSING_EVIDENCE", "INPUT_VALIDATION", "DATA_CONTRACT"}
                       and d["severity"] not in {"INFO", "OUTCOME"}
                       for d in diagnostic_events)
    missing_evidence = sorted({field for d in diagnostic_events
                               for field in d.get("missing_evidence", [])})
    return {
        **setup,
        **lifecycle,
        "classification": "EXPECTED_ATTRITION" if lifecycle["failure_code"] in NORMAL_OUTCOMES else "DEFECT",
        "stop_distance": round(stop_distance, 10),
        "reward_distance": round(reward_distance, 10),
        "computed_rr": round(reward_distance / stop_distance, 2) if stop_distance else None,
        "risk_decision": risk.get("decision") if risk else None,
        "risk_reasons": risk.get("reasons", []) if risk else [],
        "risk_usd": risk.get("risk_usd") if risk else None,
        "order_event": order.get("event") if order else None,
        "order_scope": "SHADOW_SIMULATION" if order else None,
        "order_available_at": order.get("available_at") if order else None,
        "fill_ts": execution.get("fill_ts") if execution else None,
        "outcome": execution.get("outcome") if execution else None,
        "net_r": execution.get("r_multiple") if execution else None,
        "gross_r": execution.get("r_gross") if execution else None,
        "costs_r": execution.get("costs_r") if execution else None,
        "mae_r": execution.get("mae_r") if execution else None,
        "mfe_r": execution.get("mfe_r") if execution else None,
        "bars_to_fill": execution.get("bars_to_fill") if execution else None,
        "bars_held": execution.get("bars_held") if execution else None,
        "diagnostics": diagnostic_events,
        "diagnostic_count": len(diagnostic_events),
        "defect_count": defect_count,
        "missing_evidence": missing_evidence,
    }


def summarize_diagnostics(records: list[dict]) -> dict:
    """Aggregate diagnostics without conflating trading outcomes and defects."""
    categories = Counter()
    severities = Counter()
    root_causes = Counter()
    rules = Counter()
    missing = Counter()
    for record in records:
        for event in record.get("diagnostics", []):
            categories[event.get("category") or "UNKNOWN"] += 1
            severities[event.get("severity") or "UNKNOWN"] += 1
            rules[event.get("rule_id") or "UNKNOWN"] += 1
            if event.get("severity") not in {"INFO", "OUTCOME"}:
                root_causes[diagnostics.root_cause_key(event)] += 1
            for field in event.get("missing_evidence", []):
                missing[field] += 1
    return {
        "categories": dict(categories.most_common()),
        "severities": dict(severities.most_common()),
        "root_causes": dict(root_causes.most_common()),
        "rules": dict(rules.most_common()),
        "missing_evidence": dict(missing.most_common()),
    }
