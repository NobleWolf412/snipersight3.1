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

# Kill-Switch Ladder — the single vocabulary every audit finding declares itself
# in, and the routing table the watchdog dispatches on. Adding a new _issue()
# code without an entry in CODE_RUNG falls back to HALT/SERVE_FLAG (see
# _rung_for) — safe, but the mapping must be made explicit in the same change.
RUNGS = ("SERVE", "SERVE_FLAG", "QUARANTINE", "AUTO_DISABLE", "HALT")
RUNG_ORD = {r: i for i, r in enumerate(RUNGS)}

CODE_RUNG = {
    # DATA
    "NO_CANDLES":              "HALT",
    # Per-(symbol, tf) — audit_market_inputs `continue`s past an unknown tf and
    # evaluates the rest, so this cannot break the pipeline the way HALT
    # implies. It was HALT and the watchdog restart-looped a live scanner every
    # ~7 minutes on 2026-08-08 over 27 findings that were never data at all:
    # THIS module reads importer.TF_SECONDS from whatever commit the auditing
    # process booted from, `5m` had been added after the supervisor started,
    # and 27 symbols carried 5m candles. The rows were fine; the reader was
    # two days stale, and restarting the SCANNER could never fix either.
    # Same reasoning as STALE_SERIES → QUARANTINE and watchdog.py's "a data
    # verdict is not a process fault" — plus one this code can't see: the
    # finding may indict the auditing process itself, and the rung must not
    # hand that process a gun.
    "UNKNOWN_TIMEFRAME":       "QUARANTINE",
    "OHLC_INVARIANT_FAILURE":  "HALT",
    "SEQUENCE_GAPS":           "HALT",
    "DEVELOPING_CANDLES":      "HALT",
    "STALE_SERIES":            "QUARANTINE",   # per-symbol/tf degrade
    "KNOWN_VENUE_GAPS":        "SERVE_FLAG",   # documented, not corruption
    # AGGREGATION
    "AGGREGATE_PENDING":       "SERVE_FLAG",   # scheduling lag
    "MISSING_AGGREGATE":       "HALT",
    "AGGREGATE_MISMATCH":      "HALT",
    "ORPHAN_AGGREGATE":        "HALT",
    "NO_COMPLETE_BUCKETS":     "SERVE_FLAG",
    # FACTS
    "CAUSALITY_VIOLATION":     "HALT",
    "UNATTRIBUTED_LEGACY_FACTS": "SERVE_FLAG",
    # SETUP
    "INVALID_BRACKET":         "AUTO_DISABLE",
    "INCOMPLETE_LINEAGE":      "SERVE_FLAG",
    # RISK
    "ORPHAN_RISK_DECISION":    "HALT",
    "REJECTED_WITH_EXPOSURE":  "HALT",
    "SIZED_DECISION_INCOMPLETE": "HALT",
    # EXECUTION
    "ORPHAN_ORDER":            "HALT",
    "ORDER_BEFORE_AVAILABLE":  "HALT",
    "EXIT_WITHOUT_ORDER":      "HALT",
    "EXIT_BEFORE_FILL":        "HALT",
    # ACCOUNTING
    "ACCOUNT_SUMMARY_MISSING": "HALT",
    "EQUITY_RECONCILIATION_FAILED": "HALT",
}


def _rung_for(status: str, code: str) -> str:
    if code in CODE_RUNG:
        return CODE_RUNG[code]
    return "HALT" if status == "BLOCKED" else "SERVE_FLAG"


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
    # range_start >= PRE_2000: the quarantined cold-start rows (importer.py)
    # hold ~2M fabricated gap entries each. This reader ingested their counts
    # into its budget until 2026-08-09 — harmless only because those symbols'
    # real voids dwarfed nothing, but a budget built on fabricated numbers is
    # the exact defect the quarantine exists to contain.
    for g, n in con.execute(
            "SELECT gaps, n_gaps FROM import_log WHERE symbol=? AND tf=? "
            "AND range_start>=?", (sym, tf, importer.PRE_2000)):
        total += int(n or 0)
        try:
            listed.update(int(t) for t in json.loads(g))
        except Exception:
            continue
    return listed, total


class DataQualityError(RuntimeError):
    pass


def _live_symbols(con) -> set:
    """Symbols currently in the scan universe.

    Computed once per audit and passed down — deliberately NOT cached in a
    module global. A cache keyed on nothing is shared across CONNECTIONS, so an
    audit of one database would suppress warnings in another.
    """
    try:
        from . import universe
        return set(universe.current_symbols(con))
    except Exception:
        # Fail OPEN: if we cannot tell what is live, report staleness rather
        # than silently suppressing a real one.
        return {r[0] for r in con.execute(
            "SELECT DISTINCT symbol FROM candles").fetchall()}


def _issue(checks, stage, status, code, details, symbol=None, tf=None):
    checks.append({"stage": stage, "status": status, "code": code,
                   "rung": _rung_for(status, code),
                   "symbol": symbol, "tf": tf, "details": details})


def _stage_status(checks, stage):
    relevant = [c["status"] for c in checks if c["stage"] == stage]
    return max(relevant, key=ORDER.get) if relevant else "PASS"


def _stage_rung(checks, stage):
    relevant = [c["rung"] for c in checks if c["stage"] == stage]
    return max(relevant, key=RUNG_ORD.get) if relevant else "SERVE"


# Keyed BY DATABASE PATH. It was a single global, and the background refresh
# below called store.connect() with no argument — so a caller passing any other
# store got back a verdict audited from the DEFAULT one. With a single
# production database that is invisible; it is still a violation of the rule
# this module exists to enforce, because an audit belongs to the store it
# audited and to no other.
#
# Found 2026-07-30 by a test that could not fail on its own: risk.py's
# data-health gate read a cached BLOCKED verdict belonging to a different
# database, rejected every intent as DATA_HEALTH_BLOCKED, and the drawdown halt
# it was testing therefore never fired. Silent, order-dependent, and it would
# have behaved the same way against any second store — a replay copy, a
# scratch DB, an A/B run.
_AUDIT_CACHE: dict = {}
AUDIT_TTL = 300


def _db_key(con) -> str:
    """Identify the store behind a connection, so a verdict cannot cross stores."""
    try:
        for _, name, path in con.execute("PRAGMA database_list").fetchall():
            if name == "main":
                return path or ":memory:"
    except Exception:
        pass
    return f"unknown-{id(con)}"


def _slot(key: str) -> dict:
    return _AUDIT_CACHE.setdefault(
        key, {"at": 0.0, "report": None, "refreshing": False})


def _default_db_key() -> str:
    """Path of the production store, resolved the same way store.connect does."""
    try:
        from . import store
        return str(store.DB_PATH)
    except Exception:
        return "unresolvable-default"


def last_persisted(con):
    """The most recent audit THE SCANNER RECORDED, or None before the first.

    ONE VERDICT, AND IT IS THIS ONE. `cached_audit` keeps its report in module
    state, so the api-server and the scanner each hold their own — two
    processes, two caches, no reason for them to agree. `risk.py` runs inside
    the scanner and gates trading on that process's verdict; the UI read the
    api-server's, which audits at whatever moment a request happens to arrive.

    Measured 4 Aug 2026: the server audited at 11:44:58 and caught 23 symbols
    whose 15m bar closed at 11:45 — legitimately open, flagged DEVELOPING_
    CANDLES, which is a HALT-rung code, so it published BLOCKED. The scanner
    audited the same store at 11:45:06, eight seconds later, and recorded
    DEGRADED with trading allowed. Because `cached_audit` serves its last
    report until a background refresh replaces it, the server was still
    serving that BLOCKED snapshot four minutes later, under a chip reading
    "the engine is refusing to size new entries". It was not.

    A read-only surface must never publish a verdict the engine never acted
    on. This returns the recorded one, with its age, so a scanner that has
    stopped is visible as staleness rather than hidden behind a fresh-looking
    audit nobody used.
    """
    row = con.execute(
        "SELECT observed_at, report FROM quality_runs "
        "WHERE report IS NOT NULL ORDER BY observed_at DESC LIMIT 1").fetchone()
    if row is None:
        return None
    try:
        report = json.loads(row[1])
    except (ValueError, TypeError):
        return None
    report["observed_at"] = row[0]
    report["age_s"] = max(0, int(time.time()) - row[0])
    report["source"] = "scanner"
    return report


def cached_audit(con, force: bool = False):
    """The one verdict every surface reads, for THIS store.

    A full audit was measured at 72s cold while contending with the scanner's
    writes. Any HTTP handler that calls audit() directly therefore hangs its
    caller — which is exactly how the redesigned shell's health chip and the
    ApexShell pane came to disagree and stall. Serve the last known report and
    refresh off the request path; `force` runs it synchronously for a button.
    Returns None only before the very first audit completes — callers must
    render that as "pending", never as a confident zero.
    """
    import threading
    key = _db_key(con)
    slot = _slot(key)
    if force:
        slot["report"] = audit(con, persist=True)
        slot["at"] = time.time()
        return slot["report"]

    stale = (slot["report"] is None or time.time() - slot["at"] > AUDIT_TTL)
    # The background refresh exists for ONE reason: keeping the production
    # request path off a 72s audit. It is therefore only ever run against the
    # default store. Backgrounding a thread into whatever database a caller
    # happened to pass is how this function came to hold a temporary store open
    # past its owner's lifetime — and, before the cache was keyed, how it came
    # to answer questions about one database using another's verdict.
    # Any other store gets the honest answer: None, meaning "pending". A caller
    # that needs a real verdict for it uses force=True or audit() directly.
    if stale and not slot["refreshing"] and key == _default_db_key():
        slot["refreshing"] = True

        def _bg(target=slot):
            from . import store
            try:
                c = store.connect()
                try:
                    target["report"] = audit(c)
                    target["at"] = time.time()
                finally:
                    c.close()
            except Exception:
                pass
            finally:
                target["refreshing"] = False

        threading.Thread(target=_bg, daemon=True).start()
    return slot["report"]


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
    live = _live_symbols(con)

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
        # Staleness only means something for a symbol we are STILL tracking. A
        # symbol deliberately dropped from the universe has retired data, not
        # stale data, and reporting it forever buries the one series that goes
        # quiet while it matters. Switching to perps retired 108 spot symbols
        # and produced 108 permanent warnings — the same cry-wolf failure as the
        # 1,364 blockers that wedged the scanner for days.
        if rows and sym in live and now - (rows[-1][0] + sec) > 2 * sec:
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
            src_sec = importer.TF_SECONDS[rule["source"]]
            # Lazy for the same reason the aggregator's copy is: on a liquid
            # symbol no bucket is partial and the set is never built.
            acknowledged: set | None = None
            expected = 0
            for bstart, group in by_bucket.items():
                if bstart + rule["bucket"] > now:
                    continue
                partial = len(group) != rule["n_expected"]
                if partial:
                    # MIRROR OF THE AGGREGATOR'S OWN RULE (agg-v0.2), asked
                    # independently against the same records: a partial bucket
                    # is verifiable iff every source candle occupies a slot
                    # and every missing slot is one the venue acknowledged
                    # serving nothing for. Before v0.2 this loop skipped every
                    # partial group, which was correct while the aggregator
                    # refused to build them and would have been a silent
                    # verification hole the day it stopped refusing — a
                    # partial bar on disk that no check ever reconciled.
                    present = {r[0] for r in group}
                    slots = range(bstart, bstart + rule["bucket"], src_sec)
                    if not present.issubset(slots):
                        # Misaligned source candle beside aligned ones — the
                        # aggregator refuses the bucket for the same reason,
                        # and the candle itself is OHLC_INVARIANT_FAILURE's.
                        continue
                    missing = [t for t in slots if t not in present]
                    if acknowledged is None:
                        acknowledged = importer.acknowledged_gaps(
                            con, sym, rule["source"])
                    if any(t not in acknowledged for t in missing):
                        # Unverifiable absence (never fetched / failed fetch /
                        # pre-listing). The aggregator refuses these too, so
                        # there is no bar to check; if one somehow exists it
                        # reconciles against nothing and stays visible via the
                        # source-tf SEQUENCE_GAPS check instead.
                        continue
                elif any(group[i][0] - group[i - 1][0] != src_sec
                         for i in range(1, len(group))):
                    # A full-count group with uneven spacing means a misaligned
                    # source candle; OHLC_INVARIANT_FAILURE reports it.
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
                    # (regression 2026-07-26: ONDO/SUI 4H). Only a COMPLETE
                    # bucket that stayed unemitted for more than one further
                    # bucket period is a genuine aggregation failure. A
                    # PARTIAL one never escalates past DEGRADED: ~48 stored
                    # symbols are outside the scan universe, nothing ever
                    # re-aggregates them, and a HALT the scanner cannot heal
                    # is the watchdog's documented anti-pattern — the same
                    # shape as UNKNOWN_TIMEFRAME above.
                    lagging = now - (bstart + rule["bucket"]) <= 2 * rule["bucket"]
                    if partial:
                        _issue(checks, "AGGREGATION", "DEGRADED",
                               "AGGREGATE_PENDING",
                               f"qualifying partial {target} bucket {bstart} "
                               f"({len(group)}/{rule['n_expected']} source candles, "
                               f"absences venue-acknowledged) not emitted",
                               sym, target)
                    else:
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
               "rung": _stage_rung(checks, stage),
               "checks": [c for c in checks if c["stage"] == stage]}
              for stage in STAGES]
    status = max((s["status"] for s in stages), key=ORDER.get)
    worst_rung = max((s["rung"] for s in stages), key=RUNG_ORD.get)
    rung_counts = {r: 0 for r in RUNGS}
    for c in checks:
        rung_counts[c["rung"]] = rung_counts.get(c["rung"], 0) + 1
    result = {"observed_at": now, "status": status, "worst_rung": worst_rung,
              "rung_counts": rung_counts,
              "evaluation_allowed": status != "BLOCKED",
              "strategy_rules_changed": False, "stages": stages,
              "blockers": [c for c in checks if c["status"] == "BLOCKED"],
              "warnings": [c for c in checks if c["status"] == "DEGRADED"]}
    if persist:
        cur = con.execute(
            "INSERT INTO quality_runs"
            "(observed_at,status,evaluation_allowed,summary,report) "
            "VALUES (?,?,?,?,?)", (now, status, int(result["evaluation_allowed"]),
                                  json.dumps({"blockers": len(result["blockers"]),
                                              "warnings": len(result["warnings"]),
                                              "worst_rung": worst_rung,
                                              "rung_counts": rung_counts}),
                                  # THE WHOLE VERDICT. ~40 KB per row, written
                                  # every few minutes by the scanner, so that
                                  # read-only surfaces never have to re-derive
                                  # it — see `last_persisted` for why.
                                  json.dumps(result)))
        run_id = cur.lastrowid
        con.executemany(
            "INSERT INTO quality_checks(quality_run_id,stage,status,code,rung,symbol,tf,details) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(run_id, c["stage"], c["status"], c["code"], c["rung"],
              c.get("symbol"), c.get("tf"), c["details"]) for c in checks])
        con.commit(); result["quality_run_id"] = run_id
    return result


def assert_market_ready(con, symbol: str, now: int | None = None):
    checks = audit_market_inputs(con, symbol, now)
    blockers = [c for c in checks if c["status"] == "BLOCKED"]
    if blockers:
        codes = ", ".join(sorted({c["code"] for c in blockers}))
        raise DataQualityError(f"{symbol} blocked by market-data quality: {codes}")
    return checks
