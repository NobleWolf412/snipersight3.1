"""SniperSight API server — read-only over the fact store (§3: UI reads facts,
never derives them). Serves the chart UI at / and JSON at /api/*.

Run: uvicorn server:app --port 8422
"""
import json
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from engine import store, swings, importer, structure, zones, liquidity, regime, setups, execsim, risk, scalein, cycles, universe, marketdata, telemetry, quality

KIND_VERSIONS = {"swing": swings.SWING_VERSION,
                 "structure": structure.STRUCTURE_VERSION,
                 "zone": zones.ZONE_VERSION,
                 "liquidity": liquidity.LIQ_VERSION,
                 "regime": regime.REGIME_VERSION,
                 "setup": setups.SETUP_VERSION,
                 "setup_rejection": setups.SETUP_VERSION,
                 "exec": execsim.EXEC_VERSION,
                 "order": execsim.EXEC_VERSION,
                 "cycle": cycles.CYCLES_VERSION}

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
            scanner = {"alive": _t.time() - hb["ts"] < 150,
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
    """Run the read-only A-to-Z contract audit used to qualify performance."""
    con = store.connect()
    try:
        return quality.audit(con, symbol=symbol, persist=False)
    finally:
        con.close()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html",
                        headers={"Cache-Control": "no-cache, must-revalidate"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
