"""Persistent automation mode and promotion-gate authority.

Mode is operational state, not a strategy rule.  Changing it never rewrites a
research baseline.  Every transition is revision-checked and append-only
audited; a stale browser cannot promote a mode after the operator changed it in
another tab.
"""
from __future__ import annotations

import json
import time
from decimal import Decimal

from .contracts import (AutomationMode, AutomationStatus, DecisionReason,
                        CONTRACT_VERSION)


AUTOMATION_VERSION = "automation-v0.5-draft"
# v0.5: every drill now names and enforces the evidence a pass requires; only
# `disconnect` had requirements before, so the restart drill passed on any
# lost-response recovery inside a single process — one of seven gates on
# TESTNET -> LIVE, satisfiable without a restart. Fail-closed: an observation
# missing its required fields completes nothing.
DEFAULT_MODE = AutomationMode.PAPER
REQUIRED_SAFETY_DRILLS = {"disconnect", "restart", "stale_data",
                          "rejected_order", "partial_fill",
                          "protective_stop", "kill_switch"}
_DRILL_EVENTS = {
    "DISCONNECT_RECOVERED": "disconnect",
    "RESTART_RECOVERED": "restart",
    "STALE_RECONCILIATION_BLOCKED": "stale_data",
    "ORDER_REJECTED": "rejected_order",
    "PARTIAL_FILL_PROTECTED": "partial_fill",
    "PROTECTIVE_STOP_CONFIRMED": "protective_stop",
    "KILL_SWITCH_BLOCKED": "kill_switch",
}

# What a PASS must prove, per drill. A drill with no stated evidence is a
# drill any adjacent code path can satisfy by accident — restart was passed
# by ordinary lost-response recovery until the boot-id requirement below.
# `None` means the field must merely be present and truthy; a callable is a
# predicate on the whole observation.
_DRILL_EVIDENCE: dict = {
    "restart": {
        "intent_id": None, "client_order_id": None,
        # The submission and the recovery must come from different
        # processes — that difference IS the restart.
        "_check": lambda ev: (ev.get("submitting_boot_id") and
                              ev.get("recovering_boot_id") and
                              ev["submitting_boot_id"] != ev["recovering_boot_id"]),
    },
    "partial_fill": {
        "intent_id": None,
        "_check": lambda ev: Decimal(str(ev.get("filled_quantity") or "0")) > 0,
    },
    "protective_stop": {"position_id": None, "protection_client_id": None},
    "kill_switch": {"intent_id": None, "mode": None},
    "rejected_order": {"intent_id": None},
    "stale_data": {"environment": None, "observed_at": None},
    # disconnect keeps its dedicated two-phase check in observe_safety_event.
}

# Deliberately false in the first implementation.  Evidence and operational
# gates may make LIVE ready; only a separately reviewed build may make it able
# to submit mainnet orders.
LIVE_ROUTER_BUILD_ENABLED = False

ACKNOWLEDGEMENTS = {
    AutomationMode.SHADOW: "I UNDERSTAND SHADOW SENDS NO ORDERS",
    AutomationMode.TESTNET: "I UNDERSTAND TESTNET USES TEST FUNDS",
    AutomationMode.LIVE: "ENABLE LIVE TRADING WITH REAL FUNDS",
}


class ModeConflict(RuntimeError):
    pass


class ModeRejected(ValueError):
    pass


def _ensure(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS automation_state (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        mode TEXT NOT NULL,
        revision INTEGER NOT NULL,
        updated_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS automation_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_mode TEXT NOT NULL,
        to_mode TEXT NOT NULL,
        from_revision INTEGER NOT NULL,
        to_revision INTEGER NOT NULL,
        changed_at INTEGER NOT NULL,
        acknowledgement TEXT NOT NULL,
        note TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS safety_drill_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drill TEXT NOT NULL,
        environment TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at INTEGER NOT NULL,
        completed_at INTEGER,
        evidence TEXT NOT NULL DEFAULT '{}')""")


def current(con) -> tuple[AutomationMode, int, int | None]:
    """Read mode without creating state during a GET request."""
    try:
        row = con.execute(
            "SELECT mode, revision, updated_at FROM automation_state "
            "WHERE singleton=1").fetchone()
    except Exception:
        row = None
    if not row:
        return DEFAULT_MODE, 0, None
    try:
        return AutomationMode(row[0]), int(row[1]), int(row[2])
    except (ValueError, TypeError):
        return DEFAULT_MODE, 0, None


def _criterion(gate: dict, key: str) -> bool:
    for item in gate.get("criteria", []):
        if item.get("key") == key:
            return bool(item.get("pass"))
    return False


def promotion_summary(live_gate: dict | None = None,
                      operational: dict | None = None) -> dict:
    gate = live_gate or {}
    op = operational or {}
    shadow_ready = bool(op.get("shadow_days", 0) >= 14 and
                        op.get("shadow_intents", 0) >= 100 and
                        op.get("shadow_paired_results", 0) >= 100 and
                        op.get("shadow_pair_integrity_failures", 1) == 0)
    testnet_ready = bool(op.get("testnet_days", 0) >= 30 and
                         op.get("testnet_lifecycles", 0) >= 100 and
                         op.get("duplicate_orders", 1) == 0 and
                         op.get("orphan_positions", 1) == 0 and
                         op.get("reconciliation_rate", 0) >= 0.999 and
                         op.get("safety_drills_passed", False))
    evidence_ready = bool(gate.get("ready"))
    return {
        "evidence_ready": evidence_ready,
        "sample_pass": _criterion(gate, "sample"),
        "edge_pass": _criterion(gate, "edge"),
        "drawdown_pass": _criterion(gate, "drawdown"),
        "quality_pass": _criterion(gate, "quality"),
        "shadow_ready": shadow_ready,
        "testnet_ready": testnet_ready,
        "live_ready": evidence_ready and testnet_ready,
        "live_router_build_enabled": LIVE_ROUTER_BUILD_ENABLED,
        "operational": op,
    }


def status(con, *, live_gate: dict | None = None,
           operational: dict | None = None) -> AutomationStatus:
    mode, revision, _ = current(con)
    promotion = promotion_summary(live_gate, operational)
    try:
        from . import settings
        halted = bool(settings.all_settings(con)["halted"])
    except Exception:
        halted = True
    live_enabled = bool(LIVE_ROUTER_BUILD_ENABLED and
                        promotion["live_ready"] and not halted)
    dispatch = (mode == AutomationMode.TESTNET and
                promotion["shadow_ready"] and not halted) or (
                    mode == AutomationMode.LIVE and live_enabled)
    reasons = []
    if halted:
        reasons.append(DecisionReason("OPERATOR_HALT", "New entries are halted.",
                                      "CRITICAL"))
    if mode == AutomationMode.LIVE and not live_enabled:
        reasons.append(DecisionReason(
            "LIVE_LOCKED", "Live submission has not passed every build, evidence, "
            "and operational gate.", "CRITICAL"))
    if not reasons:
        reasons.append(DecisionReason("MODE_ACTIVE", f"{mode.value} mode is active."))
    return AutomationStatus(
        mode=mode, revision=revision, halted=halted,
        live_submission_enabled=live_enabled, dispatch_allowed=dispatch,
        promotion=promotion, reasons=tuple(reasons), version=AUTOMATION_VERSION)


def transition(con, requested: str | AutomationMode, *, expected_revision: int,
               acknowledgement: str = "", note: str = "",
               live_gate: dict | None = None,
               operational: dict | None = None) -> AutomationStatus:
    try:
        target = requested if isinstance(requested, AutomationMode) else AutomationMode(requested)
    except ValueError as exc:
        raise ModeRejected(f"unknown automation mode {requested!r}") from exc
    before, revision, _ = current(con)
    if revision != int(expected_revision):
        raise ModeConflict(
            f"automation state changed: expected revision {expected_revision}, "
            f"current revision is {revision}")
    required = ACKNOWLEDGEMENTS.get(target)
    if required and acknowledgement != required:
        raise ModeRejected(f"{target.value} requires its exact acknowledgement")
    promotion = promotion_summary(live_gate, operational)
    if target == AutomationMode.TESTNET and not promotion["shadow_ready"]:
        raise ModeRejected("TESTNET is locked until the shadow gate passes")
    if target == AutomationMode.LIVE:
        if not promotion["live_ready"]:
            raise ModeRejected("LIVE is locked until evidence and testnet gates pass")
        if not LIVE_ROUTER_BUILD_ENABLED:
            raise ModeRejected("LIVE is evidence-ready but this build cannot submit mainnet orders")
    if before in (AutomationMode.TESTNET, AutomationMode.LIVE) and target not in (
            AutomationMode.TESTNET, AutomationMode.LIVE):
        try:
            open_private = con.execute(
                "SELECT COUNT(*) FROM managed_positions p JOIN execution_outbox o "
                "ON o.intent_id=p.intent_id WHERE p.state!='CLOSED' "
                "AND o.mode IN ('TESTNET','LIVE')").fetchone()[0]
        except Exception:
            open_private = 0
        if open_private:
            raise ModeRejected(
                "private positions must be flat before leaving private custody mode")

    _ensure(con)
    now, next_revision = int(time.time()), revision + 1
    con.execute(
        "INSERT INTO automation_state(singleton,mode,revision,updated_at) "
        "VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET "
        "mode=excluded.mode, revision=excluded.revision, "
        "updated_at=excluded.updated_at",
        (target.value, next_revision, now))
    con.execute(
        "INSERT INTO automation_events(from_mode,to_mode,from_revision,to_revision,"
        "changed_at,acknowledgement,note) VALUES(?,?,?,?,?,?,?)",
        (before.value, target.value, revision, next_revision, now,
         acknowledgement, note))
    con.commit()
    return status(con, live_gate=live_gate, operational=operational)


def history(con, limit: int = 50) -> list[dict]:
    try:
        rows = con.execute(
            "SELECT from_mode,to_mode,from_revision,to_revision,changed_at,note "
            "FROM automation_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    except Exception:
        return []
    return [{"from": r[0], "to": r[1], "from_revision": r[2],
             "to_revision": r[3], "changed_at": r[4], "note": r[5],
             "version": AUTOMATION_VERSION} for r in rows]


def start_safety_drill(con, drill: str, *, acknowledgement: str) -> dict:
    """Stage one real TESTNET fault drill; this never performs the fault."""
    if drill not in REQUIRED_SAFETY_DRILLS:
        raise ModeRejected(f"unknown safety drill {drill!r}")
    if current(con)[0] != AutomationMode.TESTNET:
        raise ModeRejected("safety drills can only be staged in TESTNET mode")
    required = f"RUN TESTNET SAFETY DRILL: {drill}"
    if acknowledgement != required:
        raise ModeRejected(f"exact acknowledgement required: {required}")
    _ensure(con)
    active = con.execute(
        "SELECT id FROM safety_drill_runs WHERE status='ACTIVE'").fetchone()
    if active:
        raise ModeConflict("another safety drill is already active")
    now = int(time.time())
    cur = con.execute(
        "INSERT INTO safety_drill_runs(drill,environment,status,started_at) "
        "VALUES(?,'testnet','ACTIVE',?)", (drill, now))
    con.commit()
    return {"id": cur.lastrowid, "drill": drill, "status": "ACTIVE",
            "started_at": now, "version": AUTOMATION_VERSION}


def observe_safety_event(con, event: str, evidence: dict) -> bool:
    """Complete only the staged drill whose real code path was observed."""
    drill = "disconnect" if event == "DISCONNECT_OBSERVED" else _DRILL_EVENTS.get(event)
    if not drill:
        return False
    _ensure(con)
    row = con.execute(
        "SELECT id,evidence FROM safety_drill_runs WHERE drill=? AND environment='testnet' "
        "AND status='ACTIVE' ORDER BY id DESC LIMIT 1", (drill,)).fetchone()
    if not row:
        return False
    prior_evidence = json.loads(row[1] or "{}")
    if event == "DISCONNECT_OBSERVED":
        if (not evidence.get("transport_failure") or
                not evidence.get("intent_id") or
                not evidence.get("client_order_id")):
            return False
        staged = {"disconnect_seen": True, "failure": evidence,
                  "observed_at": int(time.time())}
        con.execute("UPDATE safety_drill_runs SET evidence=? WHERE id=?",
                    (json.dumps(staged, sort_keys=True), row[0]))
        con.commit()
        return False
    if drill == "disconnect" and not prior_evidence.get("disconnect_seen"):
        return False
    if drill == "disconnect":
        failure = prior_evidence.get("failure") or {}
        if (evidence.get("intent_id") != failure.get("intent_id") or
                evidence.get("client_order_id") != failure.get("client_order_id")):
            return False
    required = _DRILL_EVIDENCE.get(drill)
    if required:
        for field, _unused in required.items():
            if field == "_check":
                continue
            if not evidence.get(field):
                return False
        check = required.get("_check")
        try:
            if check is not None and not check(evidence):
                return False
        except Exception:
            return False          # malformed evidence proves nothing
    now = int(time.time())
    payload = {"drill": drill, "passed": True, "observed_event": event,
               "evidence": {"observation": evidence, "prior": prior_evidence},
               "run_id": row[0], "environment": "testnet"}
    con.execute(
        "UPDATE safety_drill_runs SET status='PASSED',completed_at=?,evidence=? "
        "WHERE id=? AND status='ACTIVE'",
        (now, json.dumps(payload, sort_keys=True), row[0]))
    con.execute(
        "INSERT INTO execution_events(intent_id,event,occurred_at,payload) "
        "VALUES(?,?,?,?)", (f"DRILL:{row[0]}", "SAFETY_DRILL", now,
                            json.dumps(payload, sort_keys=True)))
    con.commit()
    return True


def safety_drills(con) -> list[dict]:
    _ensure(con)
    return [{"id": r[0], "drill": r[1], "environment": r[2],
             "status": r[3], "started_at": r[4], "completed_at": r[5],
             "evidence": json.loads(r[6]), "version": AUTOMATION_VERSION}
            for r in con.execute(
                "SELECT id,drill,environment,status,started_at,completed_at,evidence "
                "FROM safety_drill_runs ORDER BY id DESC").fetchall()]


def operational_evidence(con) -> dict:
    """Promotion evidence recorded by the shared execution pipeline.

    Missing tables and missing observations fail closed.  Calendar duration is
    measured from the first qualifying event, not inferred from intent count.
    Reconciliation and drill results require explicit observations; a quiet
    system cannot accidentally promote itself.
    """
    now = int(time.time())
    try:
        outbox = con.execute(
            "SELECT mode,COUNT(*),MIN(created_at) FROM execution_outbox "
            "GROUP BY mode").fetchall()
        events = con.execute(
            "SELECT intent_id,event,payload FROM execution_events").fetchall()
    except Exception:
        outbox, events = [], []
    try:
        qualified_rows = con.execute(
            "SELECT intent_id,payload FROM qualified_lifecycles").fetchall()
    except Exception:
        qualified_rows = []

    by_mode = {str(mode): {"count": int(count), "first": first}
               for mode, count, first in outbox}
    shadow = by_mode.get("SHADOW", {})
    testnet = by_mode.get("TESTNET", {})

    def days(row):
        first = row.get("first")
        return 0 if first is None else max(0, (now - int(first)) // 86_400 + 1)

    duplicate_orders = orphan_positions = 0
    reconciled = reconciliation_total = 0
    drills: dict[str, bool] = {}
    pair_integrity_failures = 0
    shadow_paired_results = 0
    completed_lifecycle_intents: set[str] = set()
    for intent_id, event, raw in events:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            payload = {}
        name = str(event).upper()
        if name == "SHADOW_PAIR_INTEGRITY_FAILURE":
            pair_integrity_failures += 1
        elif name == "SHADOW_PAIRED_RESULT" and payload.get("matched"):
            shadow_paired_results += 1
        elif name == "DUPLICATE_BROKER_ORDER" and payload.get("environment") == "testnet":
            duplicate_orders += 1
        elif name == "ORPHAN_POSITION" and payload.get("environment") == "testnet":
            orphan_positions += 1
        elif name == "RECONCILIATION" and payload.get("environment") == "testnet":
            reconciliation_total += 1
            reconciled += int(bool(payload.get("matched")))
        elif name == "SAFETY_DRILL":
            drill = str(payload.get("drill") or "")
            if drill:
                drills[drill] = bool(payload.get("passed"))

    terminal = {"FILLED", "DONE", "CANCELED", "CANCELLED", "REJECTED",
                "EXPIRED", "DEACTIVATED"}
    candidates = []
    receipt_owners: dict[str, set[str]] = {}
    for intent_id, raw in qualified_rows:
        try:
            payload = json.loads(raw)
            entry_ids = [str(x) for x in payload["entry_execution_ids"]]
            exit_ids = [str(x) for x in payload["exit_execution_ids"]]
            numeric = [Decimal(str(payload[key])) for key in (
                "quantity", "entry_vwap", "exit_vwap", "entry_fee", "exit_fee")]
            cleanup = payload["cleanup"]
            valid = (
                payload.get("qualified") is True and
                payload.get("schema") == "testnet-lifecycle-v1" and
                payload.get("environment") == "testnet" and
                payload.get("intent_id") == intent_id and
                payload.get("exit_cause") in {"STOP", "TARGET_1", "EMERGENCY"} and
                str(payload.get("version") or "").startswith("lifecycle-v") and
                bool(payload.get("fee_currency")) and entry_ids and exit_ids and
                len(set(entry_ids + exit_ids)) == len(entry_ids + exit_ids) and
                all(value.is_finite() for value in numeric) and
                numeric[0] > 0 and numeric[1] > 0 and numeric[2] > 0 and
                isinstance(cleanup, dict) and cleanup and
                all(str(value).upper().replace("_", "") in terminal
                    for value in cleanup.values()) and
                int(payload.get("flat_observations") or 0) >= 2)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
            entry_ids, exit_ids = [], []
        if not valid:
            continue
        candidates.append((str(intent_id), entry_ids + exit_ids))
        for receipt in entry_ids + exit_ids:
            receipt_owners.setdefault(receipt, set()).add(str(intent_id))
    for intent_id, receipts in candidates:
        if all(len(receipt_owners[receipt]) == 1 for receipt in receipts):
            completed_lifecycle_intents.add(intent_id)

    required_drills = REQUIRED_SAFETY_DRILLS
    return {
        "shadow_days": days(shadow),
        "shadow_intents": shadow.get("count", 0),
        "shadow_paired_results": shadow_paired_results,
        "shadow_pair_integrity_failures": pair_integrity_failures,
        "testnet_days": days(testnet),
        "testnet_lifecycles": len(completed_lifecycle_intents),
        "duplicate_orders": duplicate_orders,
        "orphan_positions": orphan_positions,
        "reconciliation_rate": (reconciled / reconciliation_total
                                if reconciliation_total else 0.0),
        "safety_drills_passed": required_drills.issubset(drills) and
                                all(drills[d] for d in required_drills),
        "safety_drills": {d: bool(drills.get(d)) for d in sorted(required_drills)},
    }
