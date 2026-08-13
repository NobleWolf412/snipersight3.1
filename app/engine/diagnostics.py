"""Structured, read-only decision provenance for SniperSight facts.

The diagnostics layer explains immutable facts without changing strategy,
risk, execution, or accounting decisions.  It deliberately marks evidence as
``not_captured`` when an older fact did not retain a value; debugging output
must never invent inputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Diagnostic:
    category: str
    severity: str
    rule_id: str
    engine: str
    source: str
    function: str
    result: str
    summary: str
    expression: str | None
    expected: Any
    actual: Any
    inputs: dict[str, Any]
    missing_evidence: list[str]
    upstream_fact_ids: list[Any]
    config: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


def _value(mapping: dict | None, key: str, missing: list[str]):
    if mapping is None or key not in mapping:
        missing.append(key)
        return None
    return mapping.get(key)


def _risk_context(setup: dict, risk_fact: dict | None) -> tuple[dict, list[str]]:
    """Return all reproducible risk inputs retained by current/legacy facts."""
    from . import risk as risk_engine

    missing: list[str] = []
    entry = _value(setup, "entry", missing)
    stop = _value(setup, "sl", missing)
    direction = _value(setup, "direction", missing)
    strategy = _value(setup, "strategy", missing)
    parent = setup.get("parent_setup_id")
    equity = _value(risk_fact, "equity_at", missing)
    intended = _value(risk_fact, "intended_risk_usd", missing)
    approved = _value(risk_fact, "risk_usd", missing)
    stop_distance = None
    try:
        stop_distance = abs(float(entry) - float(stop))
    except (TypeError, ValueError):
        missing.append("computed.stop_distance")

    return {
        "setup_id": setup.get("setup_id"),
        "entry": entry,
        "stop": stop,
        "stop_distance": stop_distance,
        "direction": direction,
        "strategy": strategy,
        "parent_setup_id": parent,
        "universe_eligible": setup.get("universe_eligible"),
        "equity_at": equity,
        "intended_risk_usd": intended,
        "approved_risk_usd": approved,
        "decision": risk_fact.get("decision") if risk_fact else None,
        "reasons": risk_fact.get("reasons", []) if risk_fact else [],
        "units": risk_fact.get("units") if risk_fact else None,
        "notional_usd": risk_fact.get("notional_usd") if risk_fact else None,
        "implied_leverage": risk_fact.get("implied_leverage") if risk_fact else None,
    }, sorted(set(missing))


def explain_risk(setup: dict, risk_fact: dict | None) -> list[dict]:
    """Explain every risk reason as a stable rule-level diagnostic."""
    if not risk_fact:
        return []
    from . import risk as risk_engine

    inputs, missing = _risk_context(setup, risk_fact)
    # The pct comes from the FACT being explained, not from a module
    # constant: the fact that decided is the authority on what it decided
    # with. v0.22+ DECISIONs record `risk_pct`/`pct_basis`. Facts without the
    # field fall back to paper's pct — right for pre-v0.21 facts (2%), wrong
    # for the brief v0.21 generation (0.25%), which no current reader pins;
    # if one ever does, the fallback must learn to read the version tag.
    from .contracts import AutomationMode as _Mode
    _paper = risk_engine.gates_for_mode(_Mode.PAPER)
    _fact_pct = risk_fact.get("risk_pct") or str(_paper["risk_pct"])
    config = {
        "risk_version": risk_engine.RISK_VERSION,
        "risk_pct": str(_fact_pct),
        "pct_basis": risk_fact.get("pct_basis", "PAPER"),
        "scale_risk_pct": str(_paper["scale_risk_pct"]),
        "max_concurrent": _paper["max_concurrent"],
        "max_total_open_risk_pct": str(_paper["max_total_open_risk_pct"]),
        "max_leverage": str(risk_engine.MAX_LEVERAGE),
        "allow_shorts": risk_engine.ALLOW_SHORTS,
        "min_notional_usd": str(risk_engine.MIN_NOTIONAL_USD),
        "daily_loss_limit_pct": str(_paper["daily_loss_limit_pct"]),
        "min_reduced_fraction": str(risk_engine.MIN_REDUCED_FRACTION),
    }
    reasons = risk_fact.get("reasons") or ["UNSPECIFIED"]
    decision = risk_fact.get("decision") or "UNKNOWN"
    out: list[dict] = []

    catalog = {
        "DAILY_LOSS_HALT": ("RISK.001", "daily realized loss is below the halt threshold", "day not halted", "halted", "PORTFOLIO_CONTROL"),
        "NOT_IN_POINT_IN_TIME_UNIVERSE": ("RISK.002", "symbol is admitted at the setup confirmation time", True, inputs.get("universe_eligible"), "ELIGIBILITY"),
        "INVALID_STOP_DISTANCE": ("RISK.003", "abs(entry - stop) > 0", "> 0", inputs.get("stop_distance"), "INPUT_VALIDATION"),
        "SHORT_UNSUPPORTED_COINBASE_SPOT": ("RISK.004", "direction != SHORT or venue permits shorts", "supported direction", inputs.get("direction"), "VENUE_CONTRACT"),
        "PARENT_CLOSED": ("RISK.005", "scale-in parent remains open", "open parent setup", inputs.get("parent_setup_id"), "STATE_DEPENDENCY"),
        "EXPOSURE_LIMIT": ("RISK.007", "requested risk fits remaining portfolio risk budget", "within total-open-risk budget", inputs.get("intended_risk_usd"), "PORTFOLIO_CONTROL"),
        "BELOW_MIN_NOTIONAL": ("RISK.009", "units * entry >= minimum notional", f">= {risk_engine.MIN_NOTIONAL_USD}", inputs.get("notional_usd"), "INPUT_VALIDATION"),
        "SCALE_IN_FORBIDDEN": ("RISK.010", "scale-in adds are sized above 0R", "adds permitted (>0R)", "0R — pyramiding forbidden by contract", "PORTFOLIO_CONTROL"),
        "ZERO_RISK_SIZE": ("RISK.011", "an approved position carries positive risk", "> 0", inputs.get("intended_risk_usd"), "INPUT_VALIDATION"),
        "DATA_HEALTH_BLOCKED": ("RISK.012", "the scanner-recorded data audit allows evaluation", "not BLOCKED", "BLOCKED", "DATA_GATE"),
        "OPERATOR_HALT": ("RISK.013", "the operator halt is clear", False, True, "PORTFOLIO_CONTROL"),
        "PARTICIPATION_TOO_THIN": ("RISK.014", "venue participation supports at least the minimum reduced size", "sufficient liquidity", "too thin", "LIQUIDITY_CONTROL"),
        "WITHIN_LIMITS": ("RISK.000", "all risk authority rules pass", "all rules pass", decision, "DECISION"),
        "UNSPECIFIED": ("RISK.UNKNOWN", None, "machine-readable reason", None, "MISSING_EVIDENCE"),
    }

    for raw_reason in reasons:
        base = str(raw_reason).split("(", 1)[0]
        if base == "CONCURRENT_LIMIT":
            meta = ("RISK.006", "open base positions < max concurrent positions", f"< {risk_engine.MAX_CONCURRENT}", raw_reason, "PORTFOLIO_CONTROL")
        elif base == "SPOT_CASH_CAP":
            meta = ("RISK.008", "implied leverage <= venue leverage cap", f"<= {risk_engine.MAX_LEVERAGE}x", inputs.get("implied_leverage"), "VENUE_CONTRACT")
        elif base == "PARTICIPATION_CAP":
            meta = ("RISK.015", "position size stays inside the venue participation cap", "<= 0.5% of 24h volume", raw_reason, "LIQUIDITY_CONTROL")
        elif base == "LEVERAGE_CAP":
            meta = ("RISK.016", "position size stays inside the venue leverage cap", "within venue leverage", raw_reason, "VENUE_CONTRACT")
        elif base == "STOP_BEYOND_LIQUIDATION":
            meta = ("RISK.017", "the protective stop is reached before liquidation", "stop before liquidation", raw_reason, "VENUE_CONTRACT")
        elif base == "DRAWDOWN_HALT":
            meta = ("RISK.018", "portfolio drawdown remains inside the configured halt", "inside drawdown limit", raw_reason, "PORTFOLIO_CONTROL")
        elif base == "STRATEGY_DISABLED":
            meta = ("RISK.019", "the setup playbook is enabled", "enabled", raw_reason, "CONFIG_CONTROL")
        elif base == "COOLDOWN":
            meta = ("RISK.020", "the symbol and direction are outside their re-entry cooldown", "cooldown clear", raw_reason, "REENTRY_CONTROL")
        else:
            meta = catalog.get(base, ("RISK.UNMAPPED", None, "registered reason code", raw_reason, "MISSING_EVIDENCE"))
        rule_id, expression, expected, actual, category = meta
        local_missing = list(missing)
        if rule_id in {"RISK.001", "RISK.005", "RISK.006", "RISK.007"}:
            local_missing.append("portfolio_state_snapshot")
        if rule_id == "RISK.UNMAPPED":
            local_missing.append("rule_catalog_entry")
        severity = "INFO" if decision == "APPROVED" else ("WARNING" if decision == "REDUCED" else "DECISION")
        out.append(Diagnostic(
            category=category,
            severity=severity,
            rule_id=rule_id,
            engine="risk",
            source="app/engine/risk.py",
            function="run",
            result=decision,
            summary=str(raw_reason).replace("_", " "),
            expression=expression,
            expected=expected,
            actual=actual,
            inputs=inputs,
            missing_evidence=sorted(set(local_missing)),
            upstream_fact_ids=[x for x in [setup.get("fact_id"), risk_fact.get("fact_id")] if x is not None],
            config=config,
        ).to_dict())
    return out


def explain_lifecycle(setup: dict, risk_fact: dict | None, order: dict | None,
                      execution: dict | None, lifecycle: dict) -> list[dict]:
    """Return rule diagnostics plus a clearly classified lifecycle observation."""
    diagnostics = explain_risk(setup, risk_fact)
    code = lifecycle["failure_code"]
    normal_outcomes = {
        "WINNER", "STOP_LOSS", "LOSING_EXIT", "TIMEOUT_EXIT",
        "ENTRY_NOT_FILLED", "COSTS_ERASED_EDGE", "OPEN_POSITION",
        "WAITING_FOR_FILL", "AWAITING_RISK", "RISK_REJECTED",
    }
    category = ("RISK_DECISION" if code == "RISK_REJECTED" else
                "TRADING_OUTCOME" if code in normal_outcomes else "SYSTEM_DEFECT")
    diagnostics.append(Diagnostic(
        category=category,
        severity="INFO" if code in {"WINNER", "OPEN_POSITION", "WAITING_FOR_FILL", "AWAITING_RISK"} else "OUTCOME",
        rule_id=f"LIFECYCLE.{code}",
        engine="telemetry",
        source="app/engine/telemetry.py",
        function="classify_failure",
        result=code,
        summary=lifecycle["detail"],
        expression=None,
        expected=None,
        actual=execution.get("outcome") if execution else (order.get("event") if order else (risk_fact.get("decision") if risk_fact else None)),
        inputs={"risk": risk_fact, "order": order, "execution": execution},
        missing_evidence=[],
        upstream_fact_ids=[],
        config={},
    ).to_dict())
    return diagnostics


def root_cause_key(diagnostic: dict) -> str:
    """Stable grouping key used by APIs and the diagnostics console."""
    return f"{diagnostic.get('rule_id', 'UNKNOWN')}::{diagnostic.get('summary', 'UNKNOWN')}"
