"""ApexShell bridge — speaks the shell's `http-json` monitor contract.

ApexShell (the operator's Electron "mothership") polls `GET {base}/api/state`
and posts `{paneId, actionId}` to `{base}/api/action`. This module renders
SniperSight's existing quality/scanner/account facts into that shape and
handles the small set of allowed verbs. See ApexShell main/monitors/sourceHttp.js.

Boundary (deliberate): the shell is an OBSERVER. Nothing here can change a
strategy rule, size a trade, or edit code. `brief` writes a markdown war-room
dossier for a human to hand to an agent; it never dispatches a fix itself.
Auto-remediation of a trading system from a dashboard button is exactly the
kind of unaudited mutation the constitution forbids (§7 versioning, §13 human
control) — the human stays the dispatcher.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

WAR_ROOM = Path(__file__).resolve().parents[2] / "war-room"
PANE_ID = "snipersight"
MAX_LOG = 40
APEXBRIDGE_VERSION = "apexbridge-v0.1-draft"
# v0.1: observer refreshes read the scanner-recorded quality verdict. The
# bridge must never persist an API-process audit and relabel it as scanner
# evidence; that recreates the split-brain verdict this surface was built to
# eliminate.

# monotonic log ring shared with the pane (ApexShell forwards only unseen seqs)
_log: list[dict] = []
_seq = 0
_busy = False


def log_line(line: str) -> None:
    global _seq
    _seq += 1
    _log.append({"i": _seq, "line": f"{time.strftime('%H:%M:%S')} {line}"})
    del _log[:-MAX_LOG]


def _severity(status: str) -> str:
    return {"PASS": "good", "DEGRADED": "warning"}.get(status, "critical")


def _report(con):
    """Return only the verdict the scanner recorded and acted on.

    A cold full audit was measured at 72s while contending with scanner writes,
    and an audit in this API process is a second authority even when it is
    fast. The observer therefore reads the durable scanner report or renders
    pending; it never derives a competing answer.
    """
    from . import quality
    return quality.last_persisted(con)   # one shared verdict for every surface


def state(con) -> dict:
    """The pane payload: one health verdict plus the numbers worth a glance."""
    from . import risk, setups, scalein, universe, store

    report = _report(con)
    if report is None:          # first poll after start — say so, never stall
        return {"version": APEXBRIDGE_VERSION,
                "data": {"status": "warning", "verdict": "AUDIT PENDING",
                         "actionable": "—", "blockers": "—", "warnings": "—",
                         "scanner": "—", "equity": "—", "setups": "—",
                         "issues": [{"name": "first audit running", "value": "wait"}]},
                "log": list(_log), "busy": True}
    blockers, warnings = report["blockers"], report["warnings"]

    # scanner liveness from the heartbeat the live loop writes each poll
    hb_path = Path(__file__).resolve().parents[1] / "data" / "heartbeat.json"
    try:
        hb = json.loads(hb_path.read_text())
        scanner_age = int(time.time() - hb["ts"])
        # matches server.SCANNER_STALE_S — the live loop beats at every stage
        scanner = "LIVE" if scanner_age < 90 else f"DOWN {scanner_age // 60}m"
    except Exception:
        scanner = "NEVER STARTED"

    acct = con.execute(
        "SELECT payload FROM facts WHERE kind='account' AND algo_version=? "
        "ORDER BY id DESC LIMIT 1", (risk.RISK_VERSION,)).fetchone()
    equity = json.loads(acct[0])["final_equity"] if acct else str(risk.START_EQUITY)

    baseline = store.get_active_baseline(con)
    active = 0
    for sym in universe.all_tracked_symbols(con):
        for tf in ("5m", "15m", "1H", "4H", "1D", "1W"):
            for ver in (setups.SETUP_VERSION, scalein.SCALE_VERSION):
                for r in store.get_facts(con, sym, tf, "setup", ver):
                    p = json.loads(r["payload"])
                    if p["state"] == "VALIDATED" and r["confirmed_at"] >= baseline["started_at"]:
                        active += 1

    # "Actionable" must match the cockpit's DIAGNOSTICS badge exactly — the two
    # surfaces reporting different numbers is worse than either being wrong
    # (they disagreed on 2026-07-26 and sent the operator chasing a phantom).
    # Badge formula: pipeline blockers + summed setup-telemetry defects.
    # Call the very endpoint the badge calls (lazy import: server imports this
    # module at load, so this must resolve at call time, not import time).
    # Reimplementing the sum here is how the two surfaces drift apart.
    defects = 0
    try:
        import server
        payload = server.setup_telemetry(limit=500)
        defects = sum(int(r.get("defect_count") or 0)
                      for r in payload.get("records", []))
    except Exception as exc:
        log_line(f"defect count unavailable: {exc}")   # loud-fallback rule
    actionable = len(blockers) + defects

    # the issue list the operator actually triages, worst first
    issues = [{"name": f"{c['code']} · {c.get('symbol') or 'portfolio'}",
               "value": "BLOCK"} for c in blockers[:6]]
    seen: set[str] = set()
    for c in warnings:
        if c["code"] in seen:
            continue
        seen.add(c["code"])
        n = sum(1 for w in warnings if w["code"] == c["code"])
        issues.append({"name": c["code"].replace("_", " ").title(), "value": f"x{n}"})
        if len(issues) >= 8:
            break

    return {
        "version": APEXBRIDGE_VERSION,
        "data": {
            "status": _severity(report["status"]),
            "verdict": f"{report['status']} · "
                       f"{'EVALUATION ALLOWED' if report['evaluation_allowed'] else 'BLOCKED'}",
            "actionable": actionable,
            "blockers": len(blockers),
            "warnings": len(warnings),
            "scanner": scanner,
            "equity": f"${float(equity):,.0f}",
            "setups": active,
            "issues": issues,
        },
        "log": list(_log),
        "busy": _busy,
    }


def _brief_text(con, report, state_data) -> str:
    from . import setups, quality
    stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# SniperSight diagnosis brief — {stamp}", "",
             f"**Verdict:** {state_data['verdict']}  ",
             f"**Blockers:** {len(report['blockers'])} · "
             f"**Warnings:** {len(report['warnings'])} · "
             f"**Scanner:** {state_data['scanner']}", "",
             "Generated by the ApexShell bridge. This is an OBSERVATION dossier: "
             "no fix has been applied and no strategy rule was touched.", ""]

    if report["blockers"]:
        lines += ["## Blockers (evaluation is invalid until repaired)", ""]
        for c in report["blockers"]:
            lines.append(f"- **{c['code']}** — {c.get('symbol') or 'portfolio'} "
                         f"{c.get('tf') or ''} · {c['details']}")
        lines.append("")

    by_code: dict[str, int] = {}
    for c in report["warnings"]:
        by_code[c["code"]] = by_code.get(c["code"], 0) + 1
    if by_code:
        lines += ["## Warnings (by code)", ""]
        lines += [f"- {k} × {v}" for k, v in sorted(by_code.items(), key=lambda x: -x[1])]
        lines.append("")

    funnel: dict[str, int] = {}
    baseline = report.get("baseline")
    for (payload,) in con.execute(
            "SELECT payload FROM facts WHERE kind='setup_rejection' AND algo_version=?",
            (setups.SETUP_VERSION,)).fetchall():
        reason = json.loads(payload).get("reason", "?")
        funnel[reason] = funnel.get(reason, 0) + 1
    if funnel:
        lines += ["## Why setups are not firing (recorded rejection reasons)", ""]
        lines += [f"- {k} × {v}" for k, v in sorted(funnel.items(), key=lambda x: -x[1])]
        lines.append("")

    lines += ["## Reproduce locally", "",
              "```bash",
              "cd app",
              "python -X utf8 -c \"from engine import store,quality;"
              "print(quality.audit(store.connect())['status'])\"",
              "python -X utf8 -m unittest discover -s tests",
              "```", "",
              "## Rules for whoever picks this up", "",
              "- Diagnose from the recorded facts; the store is append-only and replayable.",
              "- Any engine behaviour change needs a NEW algo_version (§7) — never edit in place.",
              "- Observability fixes must not alter strategy constants.",
              "- Re-run the audit and the suite before claiming a repair."]
    return "\n".join(lines) + "\n"


def action(con, action_id: str) -> dict:
    """Allowed verbs only. Returns {'ok':bool,'detail':str}."""
    global _busy
    from . import quality

    if action_id == "audit":
        # Compatibility for older clients whose button still sends
        # actionId=audit. It is a refresh, not authority to recompute health.
        report = quality.last_persisted(con)
        if report is None:
            return {"ok": False, "detail": "scanner audit pending",
                    "version": APEXBRIDGE_VERSION}
        log_line(f"refresh: scanner {report['status']} - {report['age_s']}s old")
        return {"ok": True,
                "detail": f"{report['status']} - scanner audit {report['age_s']}s old",
                "version": APEXBRIDGE_VERSION}

    if action_id == "brief":
        _busy = True
        try:
            report = quality.audit(con)
            data = state(con)["data"]
            WAR_ROOM.mkdir(parents=True, exist_ok=True)
            name = f"diagnosis-{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d-%H%M')}.md"
            path = WAR_ROOM / name
            path.write_text(_brief_text(con, report, data), encoding="utf-8")
            log_line(f"brief written: war-room/{name} — hand it to a seat")
            return {"ok": True, "detail": str(path),
                    "version": APEXBRIDGE_VERSION}
        finally:
            _busy = False

    log_line(f"unknown action '{action_id}' refused")
    return {"ok": False, "detail": f"unknown action: {action_id}",
            "version": APEXBRIDGE_VERSION}
