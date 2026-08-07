"""SniperSight API server — read-only over the fact store (§3: UI reads facts,
never derives them). Serves the chart UI at / and JSON at /api/*.

Run: uvicorn server:app --port 8422
"""
import json
import threading
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from engine import store, swings, importer, structure, zones, liquidity, regime, setups, execsim, risk, scalein, cycles, universe, marketdata, telemetry, quality, apexbridge

KIND_VERSIONS = {"swing": swings.SWING_VERSION,
                 "structure": structure.STRUCTURE_VERSION,
                 "zone": zones.ZONE_VERSION,
                 "liquidity": liquidity.LIQ_VERSION,
                 "regime": regime.REGIME_VERSION,
                 "setup": setups.SETUP_VERSION,
                 "setup_rejection": setups.SETUP_VERSION,
                 "exec": execsim.EXEC_VERSION,
                 "order": execsim.EXEC_VERSION,
                 "cycle": cycles.CYCLES_VERSION,
                 # the chart's order ticket reads the sizing verdict for the
                 # setup it is showing, so it can never invite the operator to
                 # size a trade the risk authority already refused
                 "risk": risk.RISK_VERSION}

app = FastAPI(title="SniperSight", version="0.1-draft")
STATIC = Path(__file__).resolve().parent / "static"

VALID_TFS = set(importer.TF_SECONDS)


def _baseline_setup_ids(con, *, symbol: str | None = None,
                        tf: str | None = None) -> tuple[dict, set[str]]:
    """Single source of truth for facts visible in the active paper window."""
    baseline = store.get_active_baseline(con)
    clauses = ["kind='setup'", "confirmed_at>=?"]
    args: list = [baseline["started_at"]]
    if symbol is not None:
        clauses.append("symbol=?")
        args.append(symbol)
    if tf is not None:
        clauses.append("tf=?")
        args.append(tf)
    clauses.append("algo_version IN (?,?)")
    args.extend((setups.SETUP_VERSION, scalein.SCALE_VERSION))
    rows = con.execute(
        "SELECT payload FROM facts WHERE " + " AND ".join(clauses), args
    ).fetchall()
    ids = set()
    for (raw,) in rows:
        payload = json.loads(raw)
        if payload.get("state") == "VALIDATED":
            ids.add(payload["setup_id"])
    return baseline, ids


@app.get("/api/candles")
def candles(symbol: str = Query("BTC-USD", pattern=r"^[A-Z0-9]+-USD$"),
            tf: str = "1H", limit: int = Query(1500, ge=1, le=5000),
            end_ts: int | None = None):
    """end_ts enables replay: only candles opening BEFORE end_ts are returned."""
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    con = store.connect()
    try:
        rows = store.get_candles(con, symbol, tf, end_ts=end_ts or 2**53, limit=limit)
        return [{"time": r["open_ts"], "open": float(r["open"]),
                 "high": float(r["high"]), "low": float(r["low"]),
                 "close": float(r["close"]), "volume": float(r["volume"])}
                for r in rows]
    finally:
        con.close()


@app.get("/api/swings")
def swing_facts(symbol: str = "BTC-USD", tf: str = "1H",
                as_of: int | None = None, tier: str | None = None):
    """The exact as_of-cursored query the chart and (later) the strategy share."""
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    con = store.connect()
    try:
        rows = store.get_facts(con, symbol, tf, "swing", swings.SWING_VERSION, as_of)
        out = []
        for r in rows:
            p = json.loads(r["payload"])
            if tier and p["tier"] != tier:
                continue
            out.append({"market_time": r["market_time"],
                        "confirmed_at": r["confirmed_at"],
                        "algo_version": r["algo_version"], **p})
        return out
    finally:
        con.close()


@app.get("/api/facts")
def facts(kind: str, symbol: str = "BTC-USD", tf: str = "1H",
          as_of: int | None = None):
    """Generic as_of-cursored fact query — the same contract for every engine."""
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    if kind not in KIND_VERSIONS:
        raise HTTPException(400, f"kind must be one of {sorted(KIND_VERSIONS)}")
    versions = ([setups.SETUP_VERSION, scalein.SCALE_VERSION] if kind == "setup"
                else [KIND_VERSIONS[kind]])
    con = store.connect()
    try:
        out = []
        for ver in versions:
            for r in store.get_facts(con, symbol, tf, kind, ver, as_of):
                out.append({"market_time": r["market_time"],
                            "confirmed_at": r["confirmed_at"],
                            "algo_version": r["algo_version"], **json.loads(r["payload"])})
        out.sort(key=lambda f: f["market_time"])
        return out
    finally:
        con.close()


@app.get("/api/track")
def track(symbol: str = "BTC-USD", tf: str = "1H"):
    """Paper track record from exec facts — §15 metrics, R-multiple based."""
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    con = store.connect()
    try:
        baseline, eligible = _baseline_setup_ids(con, symbol=symbol, tf=tf)
        rows = store.get_facts(con, symbol, tf, "exec", execsim.EXEC_VERSION)
        outs = [p for r in rows if (p := json.loads(r["payload"]))["setup_id"] in eligible]
        filled = [o for o in outs if o["outcome"] != "MISSED"]
        rs = [float(o["r_multiple"]) for o in filled]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r < 0]
        return {"baseline": baseline, "n": len(filled), "signals": len(outs),
                "missed": sum(1 for o in outs if o["outcome"] == "MISSED"),
                "fill_rate": round(len(filled) / len(outs), 3) if outs else None,
                "tp": sum(1 for o in filled if o["outcome"] == "TP"),
                "sl": sum(1 for o in filled if o["outcome"] == "SL"),
                "timeout": sum(1 for o in filled if o["outcome"] == "TIMEOUT"),
                "win_rate": round(len(wins) / len(rs), 3) if rs else None,
                "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
                "sum_r": round(sum(rs), 2), "by_setup": {o["setup_id"]: o for o in outs}}
    finally:
        con.close()


@app.get("/api/setup-telemetry")
def setup_telemetry(symbol: str | None = None, tf: str | None = None,
                    strategy: str | None = None,
                    limit: int = Query(100, ge=1, le=500)):
    """Diagnostic-only lifecycle ledger for every validated setup.

    This joins immutable facts; it never feeds the strategy or risk authority.
    Summary counts are calculated before the response row limit is applied.
    """
    if tf is not None and tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    con = store.connect()
    try:
        baseline = store.get_active_baseline(con)
        setup_by_id = {}
        for version in (setups.SETUP_VERSION, scalein.SCALE_VERSION):
            rows = con.execute(
                "SELECT symbol,tf,market_time,confirmed_at,payload,algo_version "
                "FROM facts WHERE kind='setup' AND algo_version=? "
                "ORDER BY confirmed_at,id", (version,)).fetchall()
            for sym, timeframe, market_time, confirmed_at, raw, algo_version in rows:
                p = json.loads(raw)
                if p.get("state") != "VALIDATED":
                    continue
                if confirmed_at < baseline["started_at"]:
                    continue
                if symbol and sym != symbol:
                    continue
                if tf and timeframe != tf:
                    continue
                if strategy and p.get("strategy") != strategy:
                    continue
                setup_by_id[p["setup_id"]] = {
                    "symbol": sym, "tf": timeframe, "market_time": market_time,
                    "confirmed_at": confirmed_at, "algo_version": algo_version, **p}

        def lifecycle_map(kind, version):
            out = {}
            rows = con.execute(
                "SELECT confirmed_at,payload FROM facts WHERE kind=? AND algo_version=? "
                "ORDER BY confirmed_at,id", (kind, version)).fetchall()
            for confirmed_at, raw in rows:
                p = json.loads(raw)
                sid = p.get("setup_id")
                if sid in setup_by_id:
                    out[sid] = {"confirmed_at": confirmed_at, **p}
            return out

        risk_by_id = lifecycle_map("risk", risk.RISK_VERSION)
        order_by_id = lifecycle_map("order", execsim.EXEC_VERSION)
        exec_by_id = lifecycle_map("exec", execsim.EXEC_VERSION)
        records = [telemetry.build_record(s, risk_by_id.get(sid),
                                           order_by_id.get(sid), exec_by_id.get(sid))
                   for sid, s in setup_by_id.items()]
        records.sort(key=lambda r: r["confirmed_at"], reverse=True)

        stages = Counter(r["stage"] for r in records)
        failures = Counter(r["failure_code"] for r in records
                           if r["failure_code"] not in telemetry.NON_FAILURES)
        rejected_candidates = Counter()
        rows = con.execute(
            "SELECT symbol,tf,payload FROM facts WHERE kind='setup_rejection' "
            "AND algo_version=? AND confirmed_at>=?",
            (setups.SETUP_VERSION, baseline["started_at"])).fetchall()
        for sym, timeframe, raw in rows:
            if symbol and sym != symbol:
                continue
            if tf and timeframe != tf:
                continue
            rejected_candidates[json.loads(raw).get("reason", "UNKNOWN")] += 1

        cohorts = {}
        for r in records:
            c = cohorts.setdefault(r.get("strategy") or "UNKNOWN",
                                   {"validated": 0, "closed": 0, "wins": 0,
                                    "net_r": 0.0, "stop_losses": 0})
            c["validated"] += 1
            if r["outcome"] and r["outcome"] != "MISSED":
                c["closed"] += 1
                net = float(r["net_r"] or 0)
                c["net_r"] += net
                c["wins"] += net > 0
                c["stop_losses"] += r["failure_code"] == "STOP_LOSS"
        for c in cohorts.values():
            c["net_r"] = round(c["net_r"], 2)
            c["win_rate"] = round(c["wins"] / c["closed"], 3) if c["closed"] else None

        approved = sum(r["risk_decision"] in ("APPROVED", "REDUCED") for r in records)
        eligible = [r for r in records
                    if r["risk_decision"] in ("APPROVED", "REDUCED")]
        placed = sum(r["order_event"] is not None for r in eligible)
        filled = sum(r["order_event"] == "FILLED" or
                     (r["outcome"] is not None and r["outcome"] != "MISSED")
                     for r in eligible)
        closed = sum(r["outcome"] is not None and r["outcome"] != "MISSED"
                     for r in eligible)
        winners = sum(r["failure_code"] == "WINNER" for r in eligible)
        return {
            "diagnostic_only": True,
            "baseline": baseline,
            "filters": {"symbol": symbol, "tf": tf, "strategy": strategy},
            "versions": {"setup": setups.SETUP_VERSION, "risk": risk.RISK_VERSION,
                         "execution": execsim.EXEC_VERSION},
            "funnel": {"rejected_candidates": sum(rejected_candidates.values()),
                       "validated": len(records), "risk_approved": approved,
                       "order_placed": placed, "filled": filled,
                       "closed": closed, "winners": winners},
            "stages": dict(stages),
            "failure_points": dict(failures.most_common()),
            "candidate_rejections": dict(rejected_candidates.most_common()),
            "cohorts": cohorts,
            "records": records[:limit],
        }
    finally:
        con.close()


def _trace_stage(key: str, label: str, status: str, value=None,
                 expected=None, detail: str = "", facts: dict | None = None) -> dict:
    """One gate in a setup's journey.

    `value` is mandatory-by-convention rather than by type: a stage that renders
    only a tick tells the operator the gate ran, not why it decided what it
    decided. Every caller below passes the number the gate actually compared.
    """
    return {"key": key, "label": label, "status": status,
            "value": value, "expected": expected, "detail": detail,
            "facts": facts or {}}


@app.get("/api/setup-trace/{setup_id}")
def setup_trace(setup_id: str):
    """One setup's stage-by-stage journey — "why didn't THIS one fire?".

    The rejection funnel answers the aggregate question ("why is nothing
    firing?"). This answers the one an operator actually asks, about the single
    setup in front of them, and it carries the ACTUAL value at each gate —
    the R:R that was measured against the minimum, the regime the playbook was
    chosen for, the equity the risk authority sized against.

    Read-only join over immutable facts, exactly like /api/setup-telemetry.
    Nothing here is consulted by any engine. An unknown id is a 404 rather than
    an empty skeleton: a trace that renders blank looks like "this setup sailed
    through", which is the opposite of the truth.
    """
    con = store.connect()
    try:
        baseline = store.get_active_baseline(con)

        # Facts are keyed by (symbol, tf, kind) and the setup_id lives inside the
        # payload, so there is no index to seek on. Scanning the four relevant
        # kinds is cheap at this store's size and keeps the query honest — no
        # LIKE-matching on serialized JSON, which would silently miss a payload
        # written with different separators.
        def payloads(kind: str, versions: tuple[str, ...]) -> list[dict]:
            out = []
            marks = ",".join("?" * len(versions))
            rows = con.execute(
                f"SELECT symbol,tf,market_time,confirmed_at,algo_version,payload "
                f"FROM facts WHERE kind=? AND algo_version IN ({marks}) "
                f"ORDER BY confirmed_at,id", (kind, *versions)).fetchall()
            for sym, timeframe, market_time, confirmed_at, algo_version, raw in rows:
                p = json.loads(raw)
                if p.get("setup_id") != setup_id:
                    continue
                out.append({"symbol": sym, "tf": timeframe,
                            "market_time": market_time,
                            "confirmed_at": confirmed_at,
                            "algo_version": algo_version, **p})
            return out

        setup_facts = payloads("setup", (setups.SETUP_VERSION, scalein.SCALE_VERSION))
        if not setup_facts:
            raise HTTPException(
                404, f"no setup recorded with id {setup_id!r}")

        # The last fact is the setup's current truth; the earlier ones are its
        # state history (FORMING -> VALIDATED, or -> CANCELLED).
        setup = setup_facts[-1]
        risk_facts = [p for p in payloads("risk", (risk.RISK_VERSION,))
                      if p.get("event") == "DECISION"]
        order_facts = payloads("order", (execsim.EXEC_VERSION,))
        exec_facts = payloads("exec", (execsim.EXEC_VERSION,))
        risk_fact = risk_facts[-1] if risk_facts else None
        order_fact = order_facts[-1] if order_facts else None
        exec_fact = exec_facts[-1] if exec_facts else None

        # One authority for the lifecycle verdict: the same telemetry builder the
        # funnel counts with, so the drawer can never disagree with the funnel.
        record = telemetry.build_record(setup, risk_fact, order_fact, exec_fact)
        lifecycle = {k: record[k] for k in
                     ("stage", "failure_code", "failure_owner", "detail",
                      "classification")}

        state = setup.get("state")
        rr = record.get("computed_rr")
        min_rr = float(setups.MIN_RR)
        stages = [
            _trace_stage(
                "CANDIDATE", "Candidate found", "pass",
                value=f"{setup['symbol']} {setup['tf']}",
                detail=setup.get("why") or "a price zone was touched",
                facts={"zone_id": setup.get("zone_id"),
                       "zone_strength": setup.get("zone_strength"),
                       "market_time": setup["market_time"],
                       "confirmed_at": setup["confirmed_at"]}),
            _trace_stage(
                "PLAYBOOK", "Strategy matched", "pass",
                value=f"{setup.get('strategy') or 'UNKNOWN'} · {setup.get('direction') or '—'}",
                expected="a strategy whose conditions cover this regime",
                detail=f"regime at the time was {setup.get('regime') or 'unrecorded'}",
                facts={"strategy": setup.get("strategy"),
                       "direction": setup.get("direction"),
                       "regime": setup.get("regime"),
                       "rank": setup.get("rank")}),
            _trace_stage(
                "BRACKET", "Entry, stop and target",
                "pass" if record["stop_distance"] else "fail",
                value=(f"entry {setup.get('entry')} · stop {setup.get('sl')} "
                       f"· target {setup.get('tp')}"),
                expected="a stop a non-zero distance from the entry",
                detail=("stop is "
                        f"{record['stop_distance']} away, target is "
                        f"{record['reward_distance']} away"),
                facts={"entry": setup.get("entry"), "sl": setup.get("sl"),
                       "tp": setup.get("tp"),
                       "stop_distance": record["stop_distance"],
                       "reward_distance": record["reward_distance"]}),
            _trace_stage(
                "RR_GATE", "Reward against risk",
                "pass" if rr is not None and rr >= min_rr else "fail",
                value=rr, expected=f">= {min_rr}",
                detail=(f"the target is {rr}x the stop distance"
                        if rr is not None else
                        "R:R could not be computed from this setup's bracket"),
                facts={"computed_rr": rr, "recorded_rr": setup.get("rr"),
                       "min_rr": str(setups.MIN_RR)}),
            _trace_stage(
                "VALIDATION", "Setup validated",
                {"VALIDATED": "pass", "FORMING": "pending",
                 "CANCELLED": "fail"}.get(state, "skip"),
                value=state, expected="VALIDATED",
                detail={"VALIDATED": "price reached the zone and every entry gate passed",
                        "FORMING": "price is approaching the zone but has not reached it",
                        "CANCELLED": "the structure this setup relied on broke first"
                        }.get(state, "no recorded state"),
                facts={"state": state, "armed": setup.get("armed"),
                       "expires_at_ts": setup.get("expires_at_ts")}),
        ]

        if risk_fact:
            decision = risk_fact.get("decision")
            reasons = risk_fact.get("reasons") or []
            stages.append(_trace_stage(
                "RISK", "Risk authority",
                {"APPROVED": "pass", "REDUCED": "warn",
                 "REJECTED": "fail"}.get(decision, "skip"),
                value=decision,
                expected="APPROVED or REDUCED to place an order",
                detail=" · ".join(reasons) if reasons else "no reason recorded",
                facts={"decision": decision, "reasons": reasons,
                       "risk_usd": risk_fact.get("risk_usd"),
                       "intended_risk_usd": risk_fact.get("intended_risk_usd"),
                       "equity_at": risk_fact.get("equity_at"),
                       "units": risk_fact.get("units"),
                       "notional_usd": risk_fact.get("notional_usd"),
                       "implied_leverage": risk_fact.get("implied_leverage")}))
        else:
            stages.append(_trace_stage(
                "RISK", "Risk authority", "skip", value=None,
                expected="APPROVED or REDUCED to place an order",
                detail="the risk authority has not ruled on this setup yet"))

        if order_fact:
            event = order_fact.get("event")
            stages.append(_trace_stage(
                "ORDER", "Order placed",
                "pass" if event in ("PLACED", "FILLED") else "fail",
                value=event, expected="PLACED",
                detail=(f"{order_fact.get('order_type') or 'order'} at "
                        f"{order_fact.get('limit_price')}"),
                facts={"event": event, "order_type": order_fact.get("order_type"),
                       "limit_price": order_fact.get("limit_price"),
                       "available_at": order_fact.get("available_at"),
                       "max_entry_bars": order_fact.get("max_entry_bars"),
                       # every order in this build is a shadow simulation; the
                       # drawer must never imply a real order went to a venue
                       "scope": "SHADOW_SIMULATION"}))
            filled = event == "FILLED"
            stages.append(_trace_stage(
                "FILL", "Filled", "pass" if filled else "fail",
                value=order_fact.get("fill_price") if filled else "not filled",
                expected="price trades through the limit inside the entry window",
                detail=("filled after "
                        f"{order_fact.get('bars_to_fill')} bars" if filled else
                        "price never came back to the entry before the order expired"),
                facts={"fill_price": order_fact.get("fill_price"),
                       "bars_to_fill": order_fact.get("bars_to_fill")}))
        else:
            for key, label in (("ORDER", "Order placed"), ("FILL", "Filled")):
                stages.append(_trace_stage(
                    key, label, "skip", value=None,
                    detail="no order simulated for this setup"))

        if exec_fact:
            outcome = exec_fact.get("outcome")
            net_r = exec_fact.get("r_multiple")
            won = record["failure_code"] == "WINNER"
            stages.append(_trace_stage(
                "EXIT", "Closed",
                "pass" if won else ("skip" if outcome == "MISSED" else "fail"),
                value=f"{outcome} · {net_r}R net",
                expected="a positive net R after costs",
                detail=lifecycle["detail"],
                facts={"outcome": outcome, "net_r": net_r,
                       "gross_r": exec_fact.get("r_gross"),
                       "costs_r": exec_fact.get("costs_r"),
                       "mae_r": exec_fact.get("mae_r"),
                       "mfe_r": exec_fact.get("mfe_r"),
                       "bars_held": exec_fact.get("bars_held"),
                       "exit_price": exec_fact.get("exit_price")}))
        else:
            stages.append(_trace_stage(
                "EXIT", "Closed", "skip", value=None,
                detail="no terminal exit fact recorded yet"))

        return {
            "diagnostic_only": True,
            "setup_id": setup_id,
            "symbol": setup["symbol"], "tf": setup["tf"],
            "market_time": setup["market_time"],
            "confirmed_at": setup["confirmed_at"],
            "algo_version": setup["algo_version"],
            "strategy": setup.get("strategy"), "direction": setup.get("direction"),
            "state": state, "regime": setup.get("regime"),
            "rank": setup.get("rank"), "why": setup.get("why"),
            "baseline": baseline,
            # A setup confirmed before the active baseline is real history, not a
            # missing record. Say which it is rather than hiding it.
            "in_baseline": setup["confirmed_at"] >= baseline["started_at"],
            "lifecycle": lifecycle,
            "stages": stages,
            "history": [{"state": f.get("state"),
                         "market_time": f["market_time"],
                         "confirmed_at": f["confirmed_at"]} for f in setup_facts],
            "risk": risk_fact, "order": order_fact, "execution": exec_fact,
            "diagnostics": record["diagnostics"],
            "missing_evidence": record["missing_evidence"],
            "thresholds": {"min_rr": str(setups.MIN_RR)},
            "versions": {"setup": setup["algo_version"],
                         "risk": risk.RISK_VERSION,
                         "execution": execsim.EXEC_VERSION},
        }
    finally:
        con.close()


@app.get("/api/portfolio")
def portfolio():
    """Paper account state from risk-authority facts (§9/§13 dashboard)."""
    con = store.connect()
    try:
        baseline, eligible = _baseline_setup_ids(con)
        since = baseline["started_at"]
        # authoritative summary from the risk authority (§8: never re-derive equity)
        arow = con.execute(
            "SELECT payload FROM facts WHERE kind='account' AND algo_version=? "
            "AND confirmed_at>=? ORDER BY id DESC LIMIT 1",
            (risk.RISK_VERSION, since)).fetchone()
        acct = json.loads(arow[0]) if arow else None
        recent, kills = [], 0
        setup_by_id, risk_by_id, latest_order, completed = {}, {}, {}, set()
        for r in store.get_facts(con, "PORTFOLIO", "ALL", "risk", risk.RISK_VERSION):
            p = json.loads(r["payload"])
            if r["confirmed_at"] >= since and p.get("event") == "KILL_SWITCH":
                kills += 1
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for version in (setups.SETUP_VERSION, scalein.SCALE_VERSION):
                    for r in store.get_facts(con, sym, tf, "setup", version):
                        p = json.loads(r["payload"])
                        if p.get("state") == "VALIDATED" and p["setup_id"] in eligible:
                            setup_by_id[p["setup_id"]] = {
                                "symbol": sym, "tf": tf,
                                "confirmed_at": r["confirmed_at"], **p}
                for r in store.get_facts(con, sym, tf, "risk", risk.RISK_VERSION):
                    p = json.loads(r["payload"])
                    if p.get("event") == "DECISION" and p.get("setup_id") in eligible:
                        decision = {"symbol": sym, "tf": tf,
                                    "ts": r["confirmed_at"], **p}
                        recent.append(decision)
                        risk_by_id[p["setup_id"]] = decision
                for r in store.get_facts(con, sym, tf, "order", execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
                    if p.get("setup_id") not in eligible:
                        continue
                    latest_order[p["setup_id"]] = {
                        "symbol": sym, "tf": tf,
                        "confirmed_at": r["confirmed_at"], **p}
                for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                    sid = json.loads(r["payload"])["setup_id"]
                    if sid in eligible:
                        completed.add(sid)
        recent.sort(key=lambda d: d["ts"])
        positions, pending_orders = [], []
        for sid, order in latest_order.items():
            if sid in completed:
                continue
            detail = setup_by_id.get(sid, {})
            sized = risk_by_id.get(sid, {})
            # execsim creates shadow orders for strategy research before the
            # risk authority runs. Only sized decisions are portfolio exposure.
            if sized.get("decision") not in ("APPROVED", "REDUCED"):
                continue
            item = {"setup_id": sid, "symbol": order["symbol"],
                    "tf": order["tf"], "direction": order.get("side"),
                    "strategy": detail.get("strategy"),
                    "entry": detail.get("entry", order.get("limit_price")),
                    "tp": detail.get("tp"), "sl": detail.get("sl"),
                    "risk_usd": sized.get("risk_usd"),
                    "notional_usd": sized.get("notional_usd"),
                    "decision": sized.get("decision"),
                    "updated_at": order["confirmed_at"]}
            if order.get("event") == "FILLED":
                positions.append(item)
            elif order.get("event") == "PLACED":
                pending_orders.append(item)
        positions.sort(key=lambda p: p["updated_at"], reverse=True)
        pending_orders.sort(key=lambda p: p["updated_at"], reverse=True)
        eq = float(acct["final_equity"]) if acct else float(risk.START_EQUITY)
        return {"baseline": baseline,
                "start_equity": float(risk.START_EQUITY), "equity": round(eq, 2),
                "return_pct": float(acct["return_pct"]) if acct else 0.0,
                "max_drawdown_pct": acct.get("max_drawdown_pct") if acct else None,
                "decisions": acct["decisions"] if acct else {},
                "kill_switch_days": kills,
                "active_positions": positions,
                "pending_orders": pending_orders,
                "open_risk_usd": round(sum(float(p["risk_usd"] or 0)
                                           for p in positions), 2),
                "curve": [{"ts": c["ts"], "equity": float(c["equity"])}
                          for c in (acct["curve"] if acct else [])],
                "recent": recent[-25:],
                "config": {"risk_pct": float(risk.RISK_PCT) * 100,
                           "max_total_risk_pct": float(risk.MAX_TOTAL_OPEN_RISK_PCT) * 100,
                           "max_concurrent": risk.MAX_CONCURRENT,
                           "max_leverage": float(risk.MAX_LEVERAGE),
                           "daily_loss_pct": float(risk.DAILY_LOSS_LIMIT_PCT) * 100,
                           "next_risk_usd": round(eq * float(risk.RISK_PCT), 2)}}
    finally:
        con.close()


SCANNER_STALE_S = 90            # heartbeat beats per stage; 90s means stuck
WATCHDOG_LOCK_PORT = 8423       # watchdog.py holds a listening lock socket here
HEARTBEAT = STATIC.parent / "data" / "heartbeat.json"


def _stop_pid(pid: int) -> tuple[bool, str]:
    """Stop a process and report the OBSERVED outcome.

    Windows note: os.kill(pid, SIGTERM) does terminate the target but can still
    raise WinError 87, so trusting the exception produced a false "stop failed"
    while the watchdog log showed a clean exit. taskkill reports truthfully.
    """
    import os
    import signal
    import subprocess
    import sys
    if sys.platform == "win32":
        r = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, text=True, timeout=10)
        msg = (r.stdout or r.stderr or "").strip().splitlines()
        return r.returncode == 0, (msg[-1] if msg else f"taskkill rc={r.returncode}")
    os.kill(pid, signal.SIGTERM)
    return True, "SIGTERM sent"


def _watchdog_alive() -> bool:
    """True when a supervisor holds the watchdog lock socket. If we can bind it,
    nothing is supervising and nothing would restart what we stop."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", WATCHDOG_LOCK_PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


@app.post("/api/system/restart")
def system_restart(target: str = Query("both", pattern="^(server|scanner|both)$")):
    """Restart supervised processes.

    Deliberately has NO spawn capability: it only asks processes to exit and
    lets the existing watchdog respawn them (5s backoff). If the watchdog is
    not running we refuse — otherwise this endpoint would be a kill switch
    rather than a restart. Local-loopback only; paper research app; the fact
    store is append-only so an interrupted cycle loses no recorded evidence.
    """
    import os
    import threading
    import time as _t

    if not _watchdog_alive():
        raise HTTPException(409, "watchdog is not running — refusing to stop "
                                 "processes nothing would restart. Start it with "
                                 "start.bat, then retry.")
    actions, warnings = [], []

    if target in ("scanner", "both"):
        try:
            hb = json.loads(HEARTBEAT.read_text())
            age = _t.time() - hb["ts"]
            if age > 180:
                # a stale heartbeat means the pid may already be recycled to an
                # unrelated process — never signal a pid we cannot vouch for
                warnings.append(f"scanner heartbeat is {int(age)}s stale; not "
                                f"signalling pid {hb['pid']} (may be recycled). "
                                f"The watchdog will respawn it on its own.")
            else:
                stopped, detail = _stop_pid(int(hb["pid"]))
                (actions if stopped else warnings).append(
                    f"scanner pid {hb['pid']} {'stopped' if stopped else 'stop failed'} ({detail})")
        except FileNotFoundError:
            warnings.append("no heartbeat file; scanner has never reported")
        except Exception as exc:
            warnings.append(f"scanner stop failed: {exc}")

    if target in ("server", "both"):
        # exit AFTER this response flushes, so the caller sees the acknowledgement
        threading.Timer(0.75, lambda: os._exit(0)).start()
        actions.append(f"api-server pid {os.getpid()} exiting")

    return {"ok": True, "target": target, "actions": actions,
            "warnings": warnings, "supervisor": "watchdog",
            "expected_back_within_s": 15}


@app.get("/api/performance")
def performance():
    """Per-symbol / per-strategy paper performance. R-stats cover every
    simulated trade; $-PnL only trades the risk authority actually sized."""
    con = store.connect()
    try:
        baseline, eligible = _baseline_setup_ids(con)
        sized = {}   # setup_id -> risk_usd for APPROVED/REDUCED
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "risk", risk.RISK_VERSION):
                    p = json.loads(r["payload"])
                    if (p.get("event") == "DECISION" and p.get("setup_id") in eligible
                            and p["decision"] in ("APPROVED", "REDUCED")):
                        sized[p["setup_id"]] = float(p["risk_usd"])

        def blank():
            return {"n": 0, "wins": 0, "sum_r": 0.0, "pos_r": 0.0, "neg_r": 0.0,
                    "sized": 0, "pnl_usd": 0.0}
        by_sym, by_strat = {}, {}
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
                    if p["setup_id"] not in eligible or p["outcome"] == "MISSED":
                        continue
                    rm = float(p["r_multiple"])
                    for key, bucket in ((sym, by_sym), (p["strategy"], by_strat)):
                        a = bucket.setdefault(key, blank())
                        a["n"] += 1
                        a["wins"] += rm > 0
                        a["sum_r"] += rm
                        a["pos_r" if rm > 0 else "neg_r"] += rm
                        ru = sized.get(p["setup_id"])
                        if ru is not None:
                            a["sized"] += 1
                            a["pnl_usd"] += ru * rm

        def rows(bucket):
            out = []
            for k, a in bucket.items():
                pf = round(a["pos_r"] / abs(a["neg_r"]), 2) if a["neg_r"] < 0 and a["pos_r"] > 0 else None
                out.append({"key": k, "n": a["n"], "win_pct": round(100 * a["wins"] / a["n"]) if a["n"] else 0,
                            "pf": pf, "sum_r": round(a["sum_r"], 1),
                            "sized": a["sized"], "pnl_usd": round(a["pnl_usd"], 2)})
            out.sort(key=lambda x: x["pnl_usd"])
            return out
        return {"baseline": baseline, "by_symbol": rows(by_sym),
                "by_strategy": rows(by_strat)}
    finally:
        con.close()


# ── Playbook catalogue ──────────────────────────────────────────────────────
# The catalogue answers the three questions a new operator actually has: what
# strategies exist, how does each one work, and is it working. The third is why
# this endpoint calls performance() rather than counting exec facts itself — a
# catalogue with its own arithmetic could disagree with the Results page, and
# the operator would have no way to know which one was lying.
#
# The prose below lives here, beside the endpoint that serves it, but every
# NUMBER and every rule with a constant behind it is read from the engine. A
# card describing rules the code stopped following is worse than no card.

# `record_key` on each card is the strategy name the engines stamp on a fact,
# and it is what joins the card to its row in performance()'s by_strategy
# bucket. A planned playbook has no record_key because it has produced nothing.
#
# A planned playbook has to justify itself with a measured gap, not a promise.
# Each one names the regime whose rejections size it. The regime is the design
# decision; the percentage is counted at request time (see below).
_PLANNED_GAP = {
    "range_fade": ("RANGE", "a market going sideways, with no trend to follow"),
    "reversal_rework": ("TRANSITION", "a market between trends"),
}


def _entry_rules() -> dict:
    """CONFIRMS / STOP GOES text, read from whichever entry model is loaded.

    setups.py is mid-version: v0.6 opened the trade on the zone touch, v0.7
    waits for a closing bar to prove the level held. The catalogue has to
    describe the engine that is actually running, so the branch tests for a
    capability the module either has or does not, never a version string.
    """
    if hasattr(setups, "confirms"):
        # 0.66 of the range measured from the far side == a close in the top 34%
        tail = int(round((1 - float(setups.REJECTION_FRACTION)) * 100))
        return {
            "confirms": (
                f"A candle has to close back OUT of the zone and finish in the "
                f"last {tail}% of its own range — the top {tail}% to buy, the "
                f"bottom {tail}% to sell. That is the market rejecting the "
                f"level, not drifting off it. It gets {setups.CONFIRM_MAX_BARS} "
                f"bars to do it, or the setup is dropped."),
            "stop_goes": (
                f"Just past the candle that did the rejecting: "
                f"{setups.SL_BUFFER_ATR} ATR beyond its low to buy, its high to "
                f"sell. A price the market has already tested and turned away "
                f"from, rather than a round number."),
        }
    return {
        "confirms": (
            "Nothing beyond the touch itself: the trade opens the moment price "
            "reaches the zone. This is the weakest part of the current engine "
            "and the entry rework exists to fix it."),
        "stop_goes": (
            f"{setups.SL_ATR} ATR beyond the far edge of the zone — the price "
            f"at which the reason for the trade has been proven wrong."),
    }


def _rejection_regime_share(con) -> dict:
    """How the candidates the scanner turned down split by market condition.

    This is what lets a PLANNED playbook state its own size instead of
    promising value. The percentages are COUNTED on every request and never
    written down: a hard-coded "27% of candidates are ranging" would go on
    claiming 27% long after the market moved, which is precisely the kind of
    confident stale number this surface exists to replace.
    """
    rows = con.execute(
        "SELECT payload FROM facts WHERE kind='setup_rejection' "
        "AND algo_version=?", (setups.SETUP_VERSION,)).fetchall()
    basis = setups.SETUP_VERSION
    if not rows:
        # A version bump leaves the new engine with no rejection history of its
        # own for a while. Falling back to the whole corpus keeps the gap
        # measurable AND says which corpus produced it — reporting 0% here
        # would read as "this gap does not exist", which is a different claim.
        rows = con.execute(
            "SELECT payload FROM facts WHERE kind='setup_rejection'").fetchall()
        basis = "every recorded setup version"
    by_regime, no_playbook = Counter(), 0
    for (raw,) in rows:
        p = json.loads(raw)
        if p.get("reason") != "NO_ELIGIBLE_PLAYBOOK":
            continue
        no_playbook += 1
        by_regime[(p.get("details") or {}).get("regime") or "UNCLASSIFIED"] += 1
    total = len(rows)
    return {"total": total, "no_playbook": no_playbook, "basis": basis,
            "by_regime": {k: {"n": v, "pct": round(100 * v / total, 1)}
                          for k, v in by_regime.items()}}


@app.get("/api/playbooks")
def playbooks():
    """Every strategy: what it hunts, how it works, and its live record.

    The record comes from /api/performance, scoped to the active baseline like
    everything else on Results. Losing strategies report their losses — a
    catalogue that hid them would be a sales page, and the operator would be
    choosing between strategies on advertising rather than evidence.
    """
    from engine import settings as _settings
    con = store.connect()
    try:
        values = _settings.all_settings(con)
        share = _rejection_regime_share(con)
        baseline = store.get_active_baseline(con)
    finally:
        con.close()

    perf = performance()
    by_strategy = {r["key"]: r for r in perf["by_strategy"]}

    def record(name):
        r = by_strategy.get(name)
        if r is None:
            # No closed trade under this baseline. n=0 with a null win rate,
            # because a "0% win rate" is a claim about trades that happened.
            return {"n": 0, "win_pct": None, "pf": None, "sum_r": 0.0,
                    "sized": 0, "pnl_usd": 0.0}
        return {k: v for k, v in r.items() if k != "key"}

    def gap(key):
        regime, plain = _PLANNED_GAP[key]
        entry = share["by_regime"].get(regime)
        if not entry or not share["total"]:
            # Loud fallback: no measurement means no percentage. Inventing one
            # to make the card look finished is the failure this rule prevents.
            return {"gap": "Not measured yet — the scanner has recorded no "
                           "rejections to size this gap against.",
                    "gap_pct": None, "gap_n": 0}
        return {"gap": (f"{entry['pct']}% of every candidate the scanner turned "
                        f"down was {plain} ({entry['n']:,} of "
                        f"{share['total']:,}). No live playbook covers one."),
                "gap_pct": entry["pct"], "gap_n": entry["n"]}

    rules = _entry_rules()
    scanned = ", ".join(importer.TF_SECONDS)
    horizon = (f"As long as the timeframe that found it: a 15m setup can be "
               f"over inside a day, a 1D setup can run for weeks. Scanned on "
               f"{scanned}.")

    cards = [
        {"key": "pullback", "name": "Pullback", "status": "live",
         "record_key": "PULLBACK", "setting": "strategy_pullback",
         "one_liner": "Buy the dip in an uptrend, sell the bounce in a downtrend.",
         "hunts": ("Trending markets. The engine's read of the chart has to be "
                   "an uptrend to buy and a downtrend to sell, including trends "
                   "that are weakening but not yet broken."),
         "triggers": ("Price comes back to a zone that turned it before — a "
                      "demand zone underneath in an uptrend, a supply zone "
                      "overhead in a downtrend."),
         "confirms": rules["confirms"], "stop_goes": rules["stop_goes"],
         "holds_for": horizon,
         "timeframes": list(importer.TF_SECONDS),
         "notes": (f"Needs at least {setups.MIN_RR} of reward for every 1 of "
                   f"risk, and enough risk that fees do not eat the trade "
                   f"({setups.MIN_RISK_COST_MULT}x the estimated round trip).")},
        {"key": "reversal", "name": "Reversal", "status": "live",
         "record_key": "REVERSAL", "setting": "strategy_reversal",
         "one_liner": "Fade a move that has just run out of buyers, or sellers.",
         "hunts": ("Markets in transition — the old trend has broken down and "
                   "a new one has not formed yet."),
         "triggers": (f"A zone touch while the market is in transition, and "
                      f"only if a liquidity sweep printed within the last "
                      f"{setups.SWEEP_LOOKBACK_BARS} bars: price reached past a "
                      f"high or low, took the stops there, and came straight "
                      f"back. Without that sweep there is no trade."),
         "confirms": rules["confirms"], "stop_goes": rules["stop_goes"],
         "holds_for": horizon,
         "timeframes": list(importer.TF_SECONDS),
         "notes": ("Starts 10 rank points below Pullback. Catching a turn is a "
                   "harder claim than following a trend, and the ranking says so.")},
        {"key": "scale_in", "name": "Scale In", "status": "live",
         "record_key": "SCALE_IN", "setting": "strategy_scale_in",
         "one_liner": "Add to a trade that is already working, at no extra risk.",
         "hunts": "Trades this system already has open and already in profit.",
         "triggers": (f"A {scalein.TRIGGER_TF} break of structure in the same "
                      f"direction as an open "
                      f"{' or '.join(scalein.PARENT_TFS)} trade, once that "
                      f"trade has already moved a full R your way. The add is "
                      f"bought with the market's progress, not with hope."),
         "confirms": (f"The break itself: a {scalein.TRIGGER_TF} candle closing "
                      f"beyond the previous structure, inside the window the "
                      f"parent trade is open."),
         "stop_goes": ("At the original trade's entry price. If the add fails, "
                       "the position it was added to is already at breakeven."),
         "holds_for": ("Until the parent trade closes. It shares that trade's "
                       f"target and never outlives it. At most "
                       f"{scalein.MAX_ADDS} adds per trade."),
         "timeframes": [scalein.TRIGGER_TF],
         "notes": ("Adds are sized as fresh exposure by the risk authority, so "
                   "two winners in a row cannot quietly become one oversized bet.")},
        {"key": "range_fade", "name": "Range Fade", "status": "planned",
         "record_key": None, "setting": None,
         "one_liner": "Sell the ceiling and buy the floor while a market goes nowhere.",
         "hunts": "Markets stuck between a ceiling and a floor, with no trend.",
         "triggers": ("Planned: price reaching the edge of an established range "
                      "rather than a trend continuation zone."),
         "confirms": "Planned. Nothing is being traded on this yet.",
         "stop_goes": "Planned: beyond the range edge, where the range is broken.",
         "holds_for": "Planned.",
         "timeframes": [], "notes": None},
        {"key": "reversal_rework", "name": "Reversal, Reworked",
         "status": "planned", "record_key": None, "setting": None,
         "one_liner": ("Trade the turn in a market between trends, without "
                       "needing a stop hunt first."),
         "hunts": ("The same transitioning markets Reversal hunts, but the ones "
                   "it currently walks away from."),
         "triggers": (f"Planned. Reversal today needs a liquidity sweep inside "
                      f"{setups.SWEEP_LOOKBACK_BARS} bars, and most "
                      f"transitioning markets never print one, so the candidate "
                      f"is dropped with no play against it."),
         "confirms": "Planned. Nothing is being traded on this yet.",
         "stop_goes": "Planned.",
         "holds_for": "Planned.",
         "timeframes": [], "notes": None},
    ]

    out = []
    for c in cards:
        card = dict(c)
        if card["status"] == "live":
            card["enabled"] = bool(values.get(card["setting"], True))
            card["record"] = record(card["record_key"])
        else:
            card["enabled"] = None
            card["record"] = None
            card.update(gap(card["key"]))
        out.append(card)

    return {"baseline": baseline, "playbooks": out,
            "entry_model": getattr(setups, "ENTRY_MODEL", "ZONE_TOUCH_LIMIT"),
            "setup_version": setups.SETUP_VERSION,
            "rejection_sample": share}


@app.get("/api/cycles")
def cycle_summary():
    """Nested-cycle satellite summary — OBSERVATIONAL ONLY, never consumed by
    any trading engine. Computed live from the candle store."""
    import time as _t
    con = store.connect()
    try:
        candles = [dict(r) for r in store.get_candles(con, cycles.BTC, "1D")]
        return cycles.summarize(candles, int(_t.time()))
    finally:
        con.close()


@app.get("/api/ticker")
def ticker():
    """Display-only live prices (Coinbase spot ticker). NEVER consumed by
    engines — analysis stays closed-candle-only (§5); this exists purely so
    the human sees the market move between candle closes."""
    con = store.connect()
    try:
        symbols = universe.all_tracked_symbols(con)
    finally:
        con.close()
    return marketdata.fetch_tickers(symbols)


@app.get("/api/manifests/{manifest_hash}")
def manifest(manifest_hash: str):
    con = store.connect()
    try:
        result = store.get_manifest(con, manifest_hash)
        if result is None:
            raise HTTPException(404, "manifest not found")
        return {"manifest_hash": manifest_hash, **result}
    finally:
        con.close()


@app.get("/api/context")
def multi_timeframe_context(
        symbol: str = Query("BTC-USD", pattern=r"^[A-Z0-9]+-USD$"),
        as_of: int | None = None):
    """Compact synchronized context strip for the decision workspace."""
    con = store.connect()
    try:
        out = []
        for tf in ("1W", "1D", "4H", "1H", "15m"):
            regs = store.get_facts(
                con, symbol, tf, "regime", regime.REGIME_VERSION, as_of)
            reg = json.loads(regs[-1]["payload"])["regime"] if regs else None
            zone_state = {}
            for row in store.get_facts(
                    con, symbol, tf, "zone", zones.ZONE_VERSION, as_of):
                p = json.loads(row["payload"])
                zone_state[p["zone_id"]] = p["state"]
            setups_state = {}
            for ver in (setups.SETUP_VERSION, scalein.SCALE_VERSION):
                for row in store.get_facts(con, symbol, tf, "setup", ver, as_of):
                    p = json.loads(row["payload"])
                    setups_state[p["setup_id"]] = p["state"]
            out.append({"tf": tf, "regime": reg,
                        "active_zones": sum(s != "BROKEN" for s in zone_state.values()),
                        "forming": sum(s == "FORMING" for s in setups_state.values()),
                        "ready": sum(s == "VALIDATED" for s in setups_state.values())})
        return {"symbol": symbol, "as_of": as_of, "timeframes": out}
    finally:
        con.close()


@app.get("/api/overview")
def overview():
    """One call for the cockpit rails: watchlist, setup feed, engine health."""
    con = store.connect()
    try:
        baseline, eligible = _baseline_setup_ids(con)
        since = baseline["started_at"]
        # latest universe membership (rank/volume/state per symbol)
        urow = con.execute(
            "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
            "ORDER BY id DESC LIMIT 1", (universe.UNIVERSE_VERSION,)).fetchone()
        umembers = {m["symbol"]: m for m in json.loads(urow[0])["members"]} if urow else {}

        symbols = []
        for sym in universe.all_tracked_symbols(con):
            days = store.get_candles(con, sym, "1D", limit=2)
            price = chg = None
            if len(days) == 2:
                prev, last = float(days[0]["close"]), float(days[1]["close"])
                price, chg = last, round(100 * (last - prev) / prev, 2)
            regs = store.get_facts(con, sym, "1D", "regime", regime.REGIME_VERSION)
            reg = json.loads(regs[-1]["payload"])["regime"] if regs else None
            m = umembers.get(sym, {})
            symbols.append({"symbol": sym, "price": price, "change_pct": chg,
                            "regime": reg, "state": m.get("state", "ADMITTED"),
                            "rank": m.get("rank"), "vol_usd": m.get("vol_usd")})
        # rank order: by universe rank, unranked last
        symbols.sort(key=lambda s: (s["rank"] is None, s["rank"] or 0))

        feed = []
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                last_state = {}
                for ver in (setups.SETUP_VERSION, scalein.SCALE_VERSION):
                    for r in store.get_facts(con, sym, tf, "setup", ver):
                        p = json.loads(r["payload"])
                        if p.get("setup_id") not in eligible:
                            continue
                        last_state[p["setup_id"]] = {"symbol": sym, "tf": tf,
                                                     "market_time": r["market_time"], **p}
                outs = {}
                for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
                    if p.get("setup_id") not in eligible:
                        continue
                    outs[p["setup_id"]] = {"outcome": p["outcome"],
                                           "r_multiple": p["r_multiple"]}
                for s in last_state.values():
                    s["result"] = outs.get(s["setup_id"])
                    feed.append(s)
        feed.sort(key=lambda s: -s["market_time"])

        # attach the risk authority's sizing decision to each feed item
        risk_by_setup = {}
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "risk", risk.RISK_VERSION):
                    p = json.loads(r["payload"])
                    if (p.get("event") == "DECISION" and
                            p.get("setup_id") in eligible):
                        risk_by_setup[p["setup_id"]] = {
                            "decision": p["decision"], "risk_usd": p.get("risk_usd"),
                            "units": p.get("units"), "leverage": p.get("implied_leverage"),
                            "reasons": p.get("reasons")}
        for s in feed:
            s["risk"] = risk_by_setup.get(s["setup_id"])

        engines = con.execute(
            "SELECT engine, MAX(run_at), duration_ms FROM engine_runs "
            "GROUP BY engine").fetchall()

        import time as _t
        hb_path = STATIC.parent / "data" / "heartbeat.json"
        try:
            hb = json.loads(hb_path.read_text())
            # The live loop now beats at every stage, not once per cycle, so a
            # short threshold genuinely means "stuck" rather than "mid-pass".
            scanner = {"alive": _t.time() - hb["ts"] < SCANNER_STALE_S,
                       "age_s": int(_t.time() - hb["ts"]), **hb}
        except Exception:
            scanner = {"alive": False, "age_s": None}

        rejection_funnel = {}
        for (payload,) in con.execute(
                "SELECT payload FROM facts WHERE kind='setup_rejection' "
                "AND algo_version=? AND confirmed_at>=?",
                (setups.SETUP_VERSION, since)).fetchall():
            reason = json.loads(payload)["reason"]
            rejection_funnel[reason] = rejection_funnel.get(reason, 0) + 1

        return {"baseline": baseline, "symbols": symbols, "feed": feed[:40], "scanner": scanner,
                "rejection_funnel": rejection_funnel,
                "engines": [{"engine": e, "last_run": t, "ms": ms}
                            for e, t, ms in engines]}
    finally:
        con.close()


@app.get("/api/status")
def status():
    con = store.connect()
    try:
        c = con.execute("SELECT symbol, tf, COUNT(*), MIN(open_ts), MAX(open_ts) "
                        "FROM candles GROUP BY symbol, tf").fetchall()
        f = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        m = con.execute("SELECT COUNT(*) FROM manifests").fetchone()[0]
        gaps = con.execute("SELECT COALESCE(SUM(n_gaps),0) FROM import_log").fetchone()[0]
        return {"baseline": store.get_active_baseline(con),
                "facts": f, "manifests": m, "gap_candles_logged": gaps,
                "algo_version": swings.SWING_VERSION,
                "versions": {**KIND_VERSIONS, "risk": risk.RISK_VERSION,
                             "scalein": scalein.SCALE_VERSION},
                "candles": [{"symbol": s, "tf": t, "n": n, "first": lo, "last": hi}
                            for s, t, n, lo, hi in c]}
    finally:
        con.close()


@app.get("/api/trade-config")
def trade_config(symbol: str | None = None):
    """Sizing and cost constants for the order ticket, for THIS symbol's venue.

    The ticket must NOT hard-code these. When the cockpit re-derived a number
    the engine already owned, the two disagreed and the operator chased a
    phantom (2026-07-26). One authority, read over the wire.

    Venue matters enormously here, not cosmetically: spot round-trip fees are
    1.00% of notional against 0.07% on perps. A 0.1%-stop trade nets -7.00R on
    spot and +2.30R on perps. Showing spot fees on a perp chart would be a lie
    that flips the sign of the decision.
    """
    from engine import venues
    try:
        v = venues.venue_for(symbol) if symbol else venues.COINBASE_SPOT
    except ValueError:
        v = venues.COINBASE_SPOT          # conservative: the costlier venue
    return {
        "risk_pct": float(risk.RISK_PCT),
        "max_total_risk_pct": float(risk.MAX_TOTAL_OPEN_RISK_PCT),
        "max_concurrent": risk.MAX_CONCURRENT,
        "max_leverage": float(v.max_leverage),
        "daily_loss_pct": float(risk.DAILY_LOSS_LIMIT_PCT),
        "venue": {"key": v.key, "kind": v.kind, "quote": v.quote,
                  "allow_shorts": v.allow_shorts,
                  "funding_per_day": v.funding_settlements_per_day},
        "venues": [{"key": x.key, "kind": x.kind, "allow_shorts": x.allow_shorts,
                    "max_leverage": float(x.max_leverage)} for x in venues.ALL],
        "cost": {"version": v.cost_profile, "venue": v.key,
                 "maker_rate": float(v.maker_rate),
                 "taker_rate": float(v.taker_rate),
                 "slippage_atr": float(v.slippage_atr)},
        # Live order submission is locked until the forward record earns it.
        # The UI reads this rather than deciding for itself.
        "live_enabled": False,
        "live_locked_reason": "Forward paper evidence has not yet earned live "
                              "execution. Rails exist; the switch is off.",
    }


@app.get("/api/credentials")
def credentials_status():
    """What credentials EXIST — never their values. There is deliberately no
    route that returns a secret; `credentials.read_secret` is in-process only."""
    from engine import credentials
    return {"available": credentials.available(), "status": credentials.status(),
            "fields": list(credentials.FIELDS),
            "note": "Stored with Windows DPAPI, encrypted to your user account. "
                    "Never written to the fact store, the log, or git. A stored "
                    "key does not enable live trading — that gate is separate."}


@app.post("/api/credentials")
def credentials_store(payload: dict):
    """Encrypt and store one credential field.

    The value is never logged, never echoed back, and never leaves this process
    in plaintext. Only the fact that it was set is reported.
    """
    from engine import credentials
    venue, field = str(payload.get("venue", "")), str(payload.get("field", ""))
    value = payload.get("value") or ""
    try:
        if payload.get("clear"):
            credentials.clear(venue, field or None)
        else:
            credentials.store_secret(venue, field, value)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc))
    from engine.runlog import get_logger
    # log the EVENT, never the value
    get_logger().info(f"CREDENTIAL {'cleared' if payload.get('clear') else 'stored'}: "
                      f"{venue}/{field or 'all'}")
    return {"ok": True, "status": credentials.status()}


@app.get("/api/settings")
def get_settings():
    from engine import settings as _settings
    con = store.connect()
    try:
        values = _settings.all_settings(con)
        # the guardrail panel shows engine-owned limits beside operator ones;
        # it must read them, never restate them
        values["risk_config"] = {
            "daily_loss_pct": float(risk.DAILY_LOSS_LIMIT_PCT) * 100,
            "max_total_risk_pct": float(risk.MAX_TOTAL_OPEN_RISK_PCT) * 100,
            "max_concurrent": risk.MAX_CONCURRENT,
        }
        return {"values": values, "spec": _settings.describe(),
                "history": _settings.history(con, 20)}
    finally:
        con.close()


@app.post("/api/settings")
def post_settings(payload: dict):
    """Apply operator settings.

    A BEHAVIOURAL change starts a new forward baseline — a record spanning two
    configurations cannot say which one produced which result. Nothing is
    deleted; the previous baseline and its facts are retained.
    """
    from engine import settings as _settings
    changes = payload.get("changes") or {}
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(400, "changes must be a non-empty object")
    con = store.connect()
    try:
        result = _settings.set_many(con, changes, note=str(payload.get("note", "")))
        if result["applied"]:
            from engine.runlog import get_logger
            get_logger().info(f"SETTINGS CHANGED: {result['applied']}")
        if result["behavioural"]:
            risk.run(con)          # re-derive the account under the new baseline
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    finally:
        con.close()


@app.get("/api/baseline")
def baseline_status():
    con = store.connect()
    try:
        return store.get_active_baseline(con)
    finally:
        con.close()


@app.post("/api/baseline/reset")
def reset_baseline(confirm: bool = False):
    """Start a clean paper window. Historical facts and candles are retained."""
    if not confirm:
        raise HTTPException(400, "confirm=true is required; no data will be deleted")
    con = store.connect()
    try:
        baseline = store.start_baseline(
            con, label="Forward paper baseline",
            strategy_version=setups.SETUP_VERSION,
            execution_version=execsim.EXEC_VERSION,
            risk_version=risk.RISK_VERSION)
        risk.run(con)
        return {"status": "RESET", "destructive": False, "baseline": baseline}
    finally:
        con.close()


@app.get("/api/health")
def health():
    """Operational health is explicit; the UI must not infer it from silence."""
    import time as _t
    now = int(_t.time())
    con = store.connect()
    try:
        integrity = con.execute("PRAGMA quick_check").fetchone()[0]
        rows = con.execute(
            "SELECT symbol, tf, MAX(open_ts) FROM candles GROUP BY symbol, tf"
        ).fetchall()
        series = []
        for symbol, tf, last_open in rows:
            sec = importer.TF_SECONDS[tf]
            age_s = max(0, now - (last_open + sec))
            series.append({"symbol": symbol, "tf": tf, "last_open": last_open,
                           "age_s": age_s, "stale": age_s > 2 * sec})
        bad, gaps = con.execute(
            "SELECT COALESCE(SUM(n_bad),0), COALESCE(SUM(n_gaps),0) FROM import_log"
        ).fetchone()
        return {"status": "OK" if integrity == "ok" and not any(
                    s["stale"] for s in series) else "DEGRADED",
                "database": integrity, "bad_candles_rejected": bad,
                "gaps_logged": gaps, "series": series,
                "stale_series": [s for s in series if s["stale"]]}
    finally:
        con.close()


@app.get("/api/pipeline-health")
def pipeline_health(symbol: str | None = None):
    """Read-only A-to-Z contract audit used to qualify performance.

    Serves the shared cached verdict (quality.cached_audit): a cold full audit
    runs ~72s, which hangs every caller and made the shell's health chip sit
    blank. A per-symbol query still audits directly since it is narrow.
    """
    con = store.connect()
    try:
        if symbol:
            return quality.audit(con, symbol=symbol, persist=False)
        report = quality.cached_audit(con)
        if report is None:
            return {"status": "PENDING", "evaluation_allowed": True,
                    "pending": True, "stages": [], "blockers": [], "warnings": [],
                    "detail": "first audit running"}
        return report
    finally:
        con.close()


NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}


@app.get("/")
def index():
    """The redesigned shell (docs/REDESIGN-PLAN.md phase 1)."""
    return FileResponse(STATIC / "shell.html", headers=NO_CACHE)


# /legacy retired 2026-07-29 (phase 6). Every surface it uniquely served now has
# a replacement in the shell — chart + order ticket (CHART), equity curve and
# per-symbol/strategy breakdown (RESULTS), setup telemetry and the rejection
# funnel (DIAGNOSTICS). The file itself is deleted rather than left dark: a
# second UI reading the same facts is a second place for them to disagree, which
# is exactly how the two equity numbers diverged on 2026-07-26.


ENGINE_LOG = STATIC.parent / "data" / "engine.log"
_scan = {"running": False, "started_at": 0, "detail": ""}
_scan_lock = threading.Lock()   # uvicorn runs sync endpoints on a threadpool,
                                # so check-then-set on _scan is NOT atomic


@app.get("/api/console")
def console(offset: int = -1, limit: int = Query(400, ge=1, le=2000)):
    """Tail the shared engine log.

    Both the scanner process and this server write here, so a byte offset is
    the only cursor that sees BOTH — an in-process ring buffer would show the
    operator half the story. offset=-1 means "start near the end".
    """
    try:
        size = ENGINE_LOG.stat().st_size
    except FileNotFoundError:
        return {"offset": 0, "lines": [], "scan": _scan, "detail": "no log yet"}
    head_partial = False
    if offset < 0 or offset > size:
        offset = max(0, size - 8192)          # first call: recent tail only
        head_partial = offset > 0             # that seek landed mid-line
    # Binary, deliberately. The log is CRLF and text mode collapses \r\n to \n,
    # so the decoded length undercounts the file by one byte per line and the
    # cursor drifts BACKWARD every poll — re-showing painted bytes mid-line.
    with open(ENGINE_LOG, "rb") as fh:
        fh.seek(offset)
        raw = fh.read()
    # Stop at the last newline: the engines are mid-write while we read, so a
    # trailing partial line would be emitted now and its remainder next poll,
    # showing the operator two fragments of one line and no whole line.
    cut = raw.rfind(b"\n") + 1
    raw, tail = raw[:cut], raw[cut:]
    new_offset = offset + cut
    if head_partial:                          # drop the half line we seeked into
        raw = raw[raw.find(b"\n") + 1:] if b"\n" in raw else b""
    text = raw.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()][-limit:]
    return {"offset": new_offset, "lines": lines, "scan": _scan,
            "pending": len(tail)}


@app.post("/api/scan", status_code=202)
def scan_now(response: Response):
    """Run one real scan cycle on demand — the same code path the live loop
    runs, so a manual scan can never diverge from an automatic one. Facts are
    content-hashed and idempotent, so overlapping with the scanner's own tick
    duplicates nothing."""
    import time as _t
    with _scan_lock:
        if _scan["running"]:
            response.status_code = 409
            return {"ok": False, "detail": "a scan is already running"}
        _scan.update(running=True, started_at=int(_t.time()), detail="scanning…")

    def _run():
        import live
        from engine.runlog import get_logger
        log = get_logger()
        con = store.connect()
        try:
            log.info("MANUAL SCAN requested from cockpit")
            n, fired = live.cycle(con, log)
            _scan["detail"] = f"{n} new candles, {len(fired)} new setups"
            log.info(f"MANUAL SCAN complete: {_scan['detail']}")
        except Exception as exc:
            _scan["detail"] = f"failed: {exc}"
            log.error(f"MANUAL SCAN failed: {exc}")
        finally:
            con.close()
            _scan["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "detail": "scan started"}


@app.get("/api/state")
def apex_state():
    """ApexShell monitor contract — the shell GETs this and binds the fields.
    Read-only; it can observe SniperSight but never steer it."""
    con = store.connect()
    try:
        return {"panes": {apexbridge.PANE_ID: apexbridge.state(con)}}
    finally:
        con.close()


@app.post("/api/action", status_code=202)
def apex_action(payload: dict, response: Response):
    """ApexShell action verbs. Allow-listed and non-destructive: `audit` re-runs
    the quality audit, `brief` writes a war-room dossier for a human to dispatch.
    Fixing is deliberately NOT a button — see engine/apexbridge.py."""
    if payload.get("paneId") not in (apexbridge.PANE_ID, None):
        raise HTTPException(404, "unknown pane")
    con = store.connect()
    try:
        result = apexbridge.action(con, str(payload.get("actionId", "")))
        if not result["ok"]:
            response.status_code = 400
        return result
    finally:
        con.close()


@app.get("/raw", include_in_schema=False)
def raw_redirect():
    """S23: the cockpit wrapper is gone — the app and its diagnostics drawer are
    one page at '/'. Kept so old bookmarks and muscle memory still land somewhere."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/", status_code=308)


class _NoCacheStatic(StaticFiles):
    """Serve UI assets without browser caching.

    Rationale (S22b): renaming a DOM id in cockpit.html while the browser
    replayed a CACHED cockpit.js left the script binding a now-missing element,
    throwing on load and silently killing the whole drawer — HTML and JS from
    two different generations. These files are a few KB on loopback, so any
    caching win is irrelevant next to serving a self-inconsistent UI.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app.mount("/static", _NoCacheStatic(directory=STATIC), name="static")
