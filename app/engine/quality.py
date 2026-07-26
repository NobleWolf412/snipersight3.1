"""Fail-closed A-to-Z pipeline quality and reconciliation audits.

The checks in this module are observational. They do not alter strategy rules.
Market-input blockers can stop downstream engines; full-pipeline blockers mark
performance as invalid for interpretation until the evidence is repaired.
"""
from __future__ import annotations

import json
import time
from decimal import Decimal

from . import aggregator, importer

STAGES = ("DATA", "AGGREGATION", "FACTS", "SETUP", "RISK", "EXECUTION", "ACCOUNTING")
ORDER = {"PASS": 0, "DEGRADED": 1, "BLOCKED": 2}


def _current_versions():
    """Active engine chain. Generation-specific checks (SETUP/RISK/EXECUTION)
    evaluate ONLY the active chain: per docs/HARDENING.md, older generations
    are retained as historical artifacts and are not comparable — auditing
    them as if they were the live pipeline permanently blocks evaluation on
    facts that the active chain never produced. Lazy import avoids cycles."""
    from . import setups, scalein, execsim, risk
    return {"setup": (setups.SETUP_VERSION, scalein.SCALE_VERSION),
            "risk": (risk.RISK_VERSION,),
            "exec": (execsim.EXEC_VERSION,),
            "order": (execsim.EXEC_VERSION,)}


def _known_gap_buckets(con, sym: str, tf: str) -> tuple[set[int], int]:
    """Gaps the importer acknowledged at import time (gap-honesty rule: gaps are
    logged, never fabricated). Coinbase legitimately omits a bucket when zero
    trades occurred in it — an acknowledged void is data, not corruption.

    Returns (explicitly listed timestamps, total acknowledged count). The list is
    truncated at import (gaps[:200]) while n_gaps is exact, so a thin listing
    like EUL-USD 15m with 830 real voids must be judged on the COUNT — otherwise
    truncation alone re-wedges the fail-closed gate (regression seen 2026-07-26).
    """
    listed: set[int] = set()
    total = 0
    for g, n in con.execute(
            "SELECT gaps, n_gaps FROM import_log WHERE symbol=? AND tf=?", (sym, tf)):
        total += int(n or 0)
        try:
            listed.update(int(t) for t in json.loads(g))
        except Exception:
            continue
    return listed, total


class DataQualityError(RuntimeError):
    pass


def _issue(checks, stage, status, code, details, symbol=None, tf=None):
    checks.append({"stage": stage, "status": status, "code": code,
                   "symbol": symbol, "tf": tf, "details": details})


def _stage_status(checks, stage):
    relevant = [c["status"] for c in checks if c["stage"] == stage]
    return max(relevant, key=ORDER.get) if relevant else "PASS"


def audit_market_inputs(con, symbol: str | None = None, now: int | None = None):
    now = int(time.time()) if now is None else now
    checks = []
    args = []
    where = ""
    if symbol:
        where = " WHERE symbol=?"
        args.append(symbol)
    series = con.execute(
        "SELECT DISTINCT symbol,tf FROM candles" + where + " ORDER BY symbol,tf",
        args).fetchall()
    if not series:
        _issue(checks, "DATA", "BLOCKED", "NO_CANDLES",
               "no market candles are available", symbol)

    for sym, tf in series:
        sec = importer.TF_SECONDS.get(tf)
        if not sec:
            _issue(checks, "DATA", "BLOCKED", "UNKNOWN_TIMEFRAME", tf, sym, tf)
            continue
        rows = con.execute(
            "SELECT open_ts,open,high,low,close,volume,source FROM candles "
            "WHERE symbol=? AND tf=? ORDER BY open_ts", (sym, tf)).fetchall()
        bad = 0
        for ts, op, hi, lo, cl, vol, _ in rows:
            op, hi, lo, cl, vol = map(Decimal, (op, hi, lo, cl, vol))
            aligned = (aggregator._bucket_start(ts, "1W") == ts
                       if tf == "1W" else ts % sec == 0)
            bad += not (aligned and hi >= max(op, cl) and
                        lo <= min(op, cl) and lo > 0 and vol >= 0)
        if bad:
            _issue(checks, "DATA", "BLOCKED", "OHLC_INVARIANT_FAILURE",
                   f"{bad} malformed or misaligned candles", sym, tf)
        missing: list[int] = []
        for i in range(1, len(rows)):
            t = rows[i - 1][0] + sec
            while t < rows[i][0] and len(missing) <= 5000:
                missing.append(t)
                t += sec
        if missing:
            if tf in importer.NATIVE_TFS:
                listed, acknowledged = _known_gap_buckets(con, sym, tf)
                remaining = [t for t in missing if t not in listed]
                # voids the importer counted but could not list (truncation)
                budget = max(0, acknowledged - len([t for t in missing if t in listed]))
                unexplained = remaining[budget:]
            else:
                # Aggregate TFs: a missing bucket is BY DESIGN when its source
                # bucket was incomplete (never fabricate). Genuine aggregation
                # failures are caught independently by MISSING_AGGREGATE below.
                unexplained = []
            if unexplained:
                _issue(checks, "DATA", "BLOCKED", "SEQUENCE_GAPS",
                       f"{len(unexplained)} unexplained discontinuities in candle sequence",
                       sym, tf)
            if len(missing) > len(unexplained):
                _issue(checks, "DATA", "DEGRADED", "KNOWN_VENUE_GAPS",
                       f"{len(missing) - len(unexplained)} venue-acknowledged empty "
                       f"buckets (logged at import; no trades or venue outage)", sym, tf)
        developing = sum(r[0] + sec > now for r in rows)
        if developing:
            _issue(checks, "DATA", "BLOCKED", "DEVELOPING_CANDLES",
                   f"{developing} candles have not closed", sym, tf)
        if rows and now - (rows[-1][0] + sec) > 2 * sec:
            _issue(checks, "DATA", "DEGRADED", "STALE_SERIES",
                   f"latest closed candle is {now - (rows[-1][0] + sec)}s old", sym, tf)

    for target, rule in aggregator.RULES.items():
        sources = con.execute(
            "SELECT DISTINCT symbol FROM candles WHERE tf=?" +
            (" AND symbol=?" if symbol else ""),
            (rule["source"], symbol) if symbol else (rule["source"],)).fetchall()
        for (sym,) in sources:
            source_rows = con.execute(
                "SELECT open_ts,open,high,low,close,volume FROM candles "
                "WHERE symbol=? AND tf=? ORDER BY open_ts", (sym, rule["source"])).fetchall()
            by_bucket = {}
            for row in source_rows:
                by_bucket.setdefault(aggregator._bucket_start(row[0], target), []).append(row)
            actual = {r[0]: r[1:] for r in con.execute(
                "SELECT open_ts,open,high,low,close,volume FROM candles "
                "WHERE symbol=? AND tf=?", (sym, target)).fetchall()}
            expected = 0
            for bstart, group in by_bucket.items():
                if bstart + rule["bucket"] > now or len(group) != rule["n_expected"]:
                    continue
                if any(group[i][0] - group[i - 1][0] != importer.TF_SECONDS[rule["source"]]
                       for i in range(1, len(group))):
                    continue
                expected += 1
                want = (group[0][1], str(max(Decimal(r[2]) for r in group)),
                        str(min(Decimal(r[3]) for r in group)), group[-1][4],
                        str(sum(Decimal(r[5]) for r in group)))
                got = actual.get(bstart)
                if got is None:
                    # A bucket that closed moments ago simply has not been
                    # aggregated yet — that is scheduling lag, not corruption,
                    # and blocking on it wedges the pipeline against itself
                    # (regression 2026-07-26: ONDO/SUI 4H). Only a bucket that
                    # stayed unemitted for more than one further bucket period
                    # is a genuine aggregation failure.
                    lagging = now - (bstart + rule["bucket"]) <= 2 * rule["bucket"]
                    _issue(checks, "AGGREGATION",
                           "DEGRADED" if lagging else "BLOCKED",
                           "AGGREGATE_PENDING" if lagging else "MISSING_AGGREGATE",
                           (f"complete {target} bucket {bstart} not yet emitted "
                            f"(awaiting next aggregation pass)" if lagging else
                            f"complete {target} bucket {bstart} was not emitted"),
                           sym, target)
                elif tuple(map(str, got)) != tuple(map(str, want)):
                    _issue(checks, "AGGREGATION", "BLOCKED", "AGGREGATE_MISMATCH",
                           f"{target} bucket {bstart} does not reconcile to {rule['source']}", sym, target)
            extras = set(actual) - set(by_bucket)
            if extras:
                _issue(checks, "AGGREGATION", "BLOCKED", "ORPHAN_AGGREGATE",
                       f"{len(extras)} aggregate candles lack source buckets", sym, target)
            if expected == 0 and source_rows:
                _issue(checks, "AGGREGATION", "DEGRADED", "NO_COMPLETE_BUCKETS",
                       f"no complete closed {target} bucket could be verified", sym, target)
    return checks


def audit(con, symbol: str | None = None, now: int | None = None, persist=False):
    now = int(time.time()) if now is None else now
    checks = audit_market_inputs(con, symbol, now)
    where, args = (" AND symbol=?", [symbol]) if symbol else ("", [])
    cur = _current_versions()

    def _ver_clause(kind):
        vers = cur[kind]
        return (" AND algo_version IN (" + ",".join("?" * len(vers)) + ")",
                list(vers))

    n = con.execute("SELECT COUNT(*) FROM facts WHERE confirmed_at<market_time" + where,
                    args).fetchone()[0]
    if n:
        _issue(checks, "FACTS", "BLOCKED", "CAUSALITY_VIOLATION",
               f"{n} facts were confirmed before their market time", symbol)
    unattributed = con.execute(
        "SELECT COUNT(*) FROM facts WHERE producer_run_id IS NULL" + where,
        args).fetchone()[0]
    if unattributed:
        _issue(checks, "FACTS", "DEGRADED", "UNATTRIBUTED_LEGACY_FACTS",
               f"{unattributed} facts predate producer-run attribution; rebuild the baseline",
               symbol)

    sv_clause, sv_args = _ver_clause("setup")
    setup_rows = con.execute(
        "SELECT symbol,tf,payload FROM facts WHERE kind='setup'" + where + sv_clause,
        args + sv_args).fetchall()
    setup_ids = set()
    for sym, tf, raw in setup_rows:
        p = json.loads(raw)
        if p.get("state") != "VALIDATED":
            continue
        setup_ids.add(p.get("setup_id"))
        try:
            entry, sl, tp = map(Decimal, (p["entry"], p["sl"], p["tp"]))
            long = p.get("direction") == "LONG"
            valid = sl < entry < tp if long else tp < entry < sl
        except Exception:
            valid = False
        if not valid:
            _issue(checks, "SETUP", "BLOCKED", "INVALID_BRACKET",
                   f"{p.get('setup_id')} has an invalid entry/stop/target", sym, tf)
        missing = [k for k in ("why", "manifest_hash", "cost_manifest_hash") if not p.get(k)]
        if missing:
            _issue(checks, "SETUP", "DEGRADED", "INCOMPLETE_LINEAGE",
                   f"{p.get('setup_id')} missing {','.join(missing)}", sym, tf)

    rv_clause, rv_args = _ver_clause("risk")
    risk_rows = con.execute(
        "SELECT symbol,tf,payload FROM facts WHERE kind='risk'" + where + rv_clause,
        args + rv_args).fetchall()
    approved = set()
    for sym, tf, raw in risk_rows:
        p = json.loads(raw)
        if p.get("event") != "DECISION":
            continue
        sid, decision = p.get("setup_id"), p.get("decision")
        if sid not in setup_ids:
            _issue(checks, "RISK", "BLOCKED", "ORPHAN_RISK_DECISION",
                   f"risk decision references unknown setup {sid}", sym, tf)
        if decision == "REJECTED" and Decimal(p.get("risk_usd", "0")) != 0:
            _issue(checks, "RISK", "BLOCKED", "REJECTED_WITH_EXPOSURE",
                   f"rejected setup {sid} has non-zero risk", sym, tf)
        if decision in ("APPROVED", "REDUCED"):
            approved.add(sid)
            if not p.get("units") or not p.get("notional_usd"):
                _issue(checks, "RISK", "BLOCKED", "SIZED_DECISION_INCOMPLETE",
                       f"{sid} is missing units or notional", sym, tf)

    ov_clause, ov_args = _ver_clause("order")
    order_rows = con.execute(
        "SELECT symbol,tf,confirmed_at,payload FROM facts WHERE kind='order'" + where +
        ov_clause + " ORDER BY confirmed_at,id", args + ov_args).fetchall()
    orders = {}
    for sym, tf, confirmed_at, raw in order_rows:
        p = json.loads(raw); sid = p.get("setup_id"); orders[sid] = p
        if sid not in setup_ids:
            _issue(checks, "EXECUTION", "BLOCKED", "ORPHAN_ORDER",
                   f"order references unknown setup {sid}", sym, tf)
        if confirmed_at < int(p.get("available_at", confirmed_at)):
            _issue(checks, "EXECUTION", "BLOCKED", "ORDER_BEFORE_AVAILABLE",
                   f"{sid} order event precedes availability", sym, tf)

    ev_clause, ev_args = _ver_clause("exec")
    exec_rows = con.execute(
        "SELECT symbol,tf,confirmed_at,payload FROM facts WHERE kind='exec'" + where +
        ev_clause, args + ev_args).fetchall()
    for sym, tf, confirmed_at, raw in exec_rows:
        p = json.loads(raw); sid = p.get("setup_id")
        if sid not in orders:
            _issue(checks, "EXECUTION", "BLOCKED", "EXIT_WITHOUT_ORDER",
                   f"execution {sid} has no order lifecycle", sym, tf)
        fill_ts = p.get("fill_ts")
        if fill_ts is not None and confirmed_at < int(fill_ts):
            _issue(checks, "EXECUTION", "BLOCKED", "EXIT_BEFORE_FILL",
                   f"execution {sid} exits before its fill", sym, tf)

    # deliberately unversioned: a summary that fails to reconcile to its own
    # curve is corrupt whatever generation wrote it (internal consistency,
    # not a cross-generation comparison)
    account = con.execute(
        "SELECT payload FROM facts WHERE kind='account' ORDER BY id DESC LIMIT 1").fetchone()
    if risk_rows and account is None:
        _issue(checks, "ACCOUNTING", "BLOCKED", "ACCOUNT_SUMMARY_MISSING",
               "risk decisions exist without an authoritative account summary")
    if account:
        p = json.loads(account[0]); curve = p.get("curve") or []
        expected = Decimal(curve[-1]["equity"]) if curve else Decimal(p["start_equity"])
        if Decimal(p["final_equity"]) != expected:
            _issue(checks, "ACCOUNTING", "BLOCKED", "EQUITY_RECONCILIATION_FAILED",
                   f"summary {p['final_equity']} does not equal ledger {expected}")

    stages = [{"stage": stage, "status": _stage_status(checks, stage),
               "checks": [c for c in checks if c["stage"] == stage]}
              for stage in STAGES]
    status = max((s["status"] for s in stages), key=ORDER.get)
    result = {"observed_at": now, "status": status,
              "evaluation_allowed": status != "BLOCKED",
              "strategy_rules_changed": False, "stages": stages,
              "blockers": [c for c in checks if c["status"] == "BLOCKED"],
              "warnings": [c for c in checks if c["status"] == "DEGRADED"]}
    if persist:
        cur = con.execute(
            "INSERT INTO quality_runs(observed_at,status,evaluation_allowed,summary) "
            "VALUES (?,?,?,?)", (now, status, int(result["evaluation_allowed"]),
                                  json.dumps({"blockers": len(result["blockers"]),
                                              "warnings": len(result["warnings"])})))
        run_id = cur.lastrowid
        con.executemany(
            "INSERT INTO quality_checks(quality_run_id,stage,status,code,symbol,tf,details) "
            "VALUES (?,?,?,?,?,?,?)",
            [(run_id, c["stage"], c["status"], c["code"], c.get("symbol"),
              c.get("tf"), c["details"]) for c in checks])
        con.commit(); result["quality_run_id"] = run_id
    return result


def assert_market_ready(con, symbol: str, now: int | None = None):
    checks = audit_market_inputs(con, symbol, now)
    blockers = [c for c in checks if c["status"] == "BLOCKED"]
    if blockers:
        codes = ", ".join(sorted({c["code"] for c in blockers}))
        raise DataQualityError(f"{symbol} blocked by market-data quality: {codes}")
    return checks
