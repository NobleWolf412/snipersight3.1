"""Observational setup lifecycle telemetry.

This module never creates signals or changes decisions. It joins already
recorded setup, risk, order, and execution facts so failures can be attributed
to the strategy, portfolio authority, entry model, or exit economics.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation

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
        "entry_role": execution.get("entry_fee_role") if execution else None,
        "fill_price": execution.get("entry") if execution else None,
        "fill_ts": execution.get("fill_ts") if execution else None,
        "closed_at": execution.get("confirmed_at") if execution else None,
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


def _decimal(value, default=Decimal(0)) -> Decimal:
    """Parse recorded numeric text without letting malformed evidence lie."""
    try:
        return Decimal(str(value)) if value is not None else default
    except (InvalidOperation, ValueError):
        return default


def _median(values: list[Decimal]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    value = (ordered[middle] if len(ordered) % 2 else
             (ordered[middle - 1] + ordered[middle]) / Decimal(2))
    return round(float(value), 3)


def loss_autopsy(records: list[dict]) -> dict:
    """Locate the weak lifecycle stage in the current funded paper book.

    This is descriptive, not a strategy gate.  It deliberately uses only
    setups the account approved, and only their recorded execution evidence.
    Small cohorts are named as watch items, never promoted into trading rules.
    """
    funded = [r for r in records
              if r.get("risk_decision") in ("APPROVED", "REDUCED")]
    closed = [r for r in funded
              if r.get("outcome") not in (None, "MISSED")]
    if not closed:
        return {
            "scope": "CURRENT_FORWARD_FUNDED", "status": "COLLECTING",
            "diagnosis": "INSUFFICIENT_EVIDENCE", "closed": 0,
            "headline": "No funded trade has closed in this forward window yet.",
            "evidence": {}, "weakest_slices": [],
            "actions": [{"code": "KEEP_PAPER",
                         "label": "Keep collecting paper outcomes"}],
        }

    def net(r):
        return _decimal(r.get("net_r"))

    winners = [r for r in closed if net(r) > 0]
    losers = [r for r in closed if net(r) <= 0]
    stops = [r for r in losers if r.get("outcome") == "SL"]
    timeouts = [r for r in losers if r.get("outcome") == "TIMEOUT"]
    cost_erased = [r for r in losers if r.get("failure_code") == "COSTS_ERASED_EDGE"]
    net_r = sum((net(r) for r in closed), Decimal(0))
    gross_r = sum((_decimal(r.get("gross_r"), net(r)) for r in closed), Decimal(0))
    costs_r = sum((_decimal(r.get("costs_r")) for r in closed), Decimal(0))

    ordered = sorted(closed, key=lambda r: (r.get("closed_at") or 0,
                                            r.get("setup_id") or ""),
                     reverse=True)
    losing_streak = 0
    for row in ordered:
        if net(row) > 0:
            break
        losing_streak += 1

    loser_mfe = [_decimal(r.get("mfe_r")) for r in losers
                 if r.get("mfe_r") is not None]
    loser_mae = [_decimal(r.get("mae_r")) for r in losers
                 if r.get("mae_r") is not None]
    loser_holds = [_decimal(r.get("bars_held")) for r in losers
                   if r.get("bars_held") is not None]
    avg_loser_mfe = (sum(loser_mfe, Decimal(0)) / len(loser_mfe)
                     if loser_mfe else None)

    if losers and len(cost_erased) * 2 >= len(losers):
        diagnosis = "COSTS"
        headline = "The trade idea moves correctly, but costs erase most losing outcomes."
    elif (losers and len(stops) / len(losers) >= .7 and
          avg_loser_mfe is not None and avg_loser_mfe < Decimal("0.5")):
        diagnosis = "SETUP_SELECTION"
        headline = ("Losses are born at entry: losing setups show little favorable "
                    "movement before structural stops are reached.")
    elif losers and len(timeouts) * 2 >= len(losers):
        diagnosis = "EXIT_TIMING"
        headline = "Most losing trades survive the stop but decay into the time limit."
    else:
        diagnosis = "MIXED"
        headline = "No single lifecycle stage explains most losses yet."

    def slice_rows(field: str, label: str) -> list[dict]:
        groups: dict[str, list[dict]] = {}
        for row in closed:
            value = row.get(field)
            if value is not None:
                groups.setdefault(str(value), []).append(row)
        out = []
        for value, rows in groups.items():
            # Three is enough to put a cohort on the WATCHLIST, never enough
            # to turn it into a rule. The response says that explicitly.
            if len(rows) < 3:
                continue
            total = sum((net(r) for r in rows), Decimal(0))
            out.append({
                "dimension": label, "value": value, "n": len(rows),
                "wins": sum(net(r) > 0 for r in rows),
                "net_r": round(float(total), 2),
                "expectancy_r": round(float(total / len(rows)), 3),
            })
        return out

    slices = []
    for field, label in (("tf", "timeframe"), ("direction", "direction"),
                         ("strategy", "playbook"), ("entry_role", "fill")):
        slices.extend(slice_rows(field, label))
    weakest = sorted((s for s in slices if s["expectancy_r"] < 0),
                     key=lambda s: (s["expectancy_r"], -s["n"]))[:4]

    sample_status = "EARLY" if len(closed) < 30 else "ESTABLISHING"
    actions = [{
        "code": "KEEP_PAPER",
        "label": ("Keep PAPER mode; this sample is too small to rewrite a "
                  "strategy from." if sample_status == "EARLY" else
                  "Keep risk unchanged until a candidate clears the edge gate."),
    }]
    if diagnosis == "SETUP_SELECTION":
        actions.append({
            "code": "REPAIR_ENTRY_FILTER",
            "label": "Test entry filters; do not loosen structural stops.",
        })
    if weakest:
        names = ", ".join(f"{s['value']} {s['dimension']}" for s in weakest[:2])
        actions.append({
            "code": "WATCH_WEAK_SLICES",
            "label": f"Watch {names}; these are clues, not automatic blocks.",
        })

    return {
        "scope": "CURRENT_FORWARD_FUNDED", "status": sample_status,
        "diagnosis": diagnosis, "closed": len(closed), "headline": headline,
        "evidence": {
            "wins": len(winners), "losses": len(losers),
            "net_r": round(float(net_r), 2),
            "gross_r": round(float(gross_r), 2),
            "costs_r": round(float(costs_r), 2),
            "current_losing_streak": losing_streak,
            "stop_losses": len(stops), "timeouts": len(timeouts),
            "cost_erased": len(cost_erased),
            "loser_avg_mfe_r": (round(float(avg_loser_mfe), 3)
                                 if avg_loser_mfe is not None else None),
            "loser_avg_mae_r": (round(float(sum(loser_mae, Decimal(0)) /
                                             len(loser_mae)), 3)
                                 if loser_mae else None),
            "loser_median_bars": _median(loser_holds),
        },
        "weakest_slices": weakest,
        "cohort_floor": 3,
        "cohort_caveat": ("Watchlist only: slices with at least 3 funded closes; "
                           "not evidence for an automatic trading rule."),
        "actions": actions,
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
