"""SniperSight API server — read-only over the fact store (§3: UI reads facts,
never derives them). Serves the chart UI at / and JSON at /api/*.

Run: uvicorn server:app --port 8422
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from engine import store, swings, importer, structure, zones, liquidity, regime, setups, execsim, risk, scalein, cycles, universe

KIND_VERSIONS = {"swing": swings.SWING_VERSION,
                 "structure": structure.STRUCTURE_VERSION,
                 "zone": zones.ZONE_VERSION,
                 "liquidity": liquidity.LIQ_VERSION,
                 "regime": regime.REGIME_VERSION,
                 "setup": setups.SETUP_VERSION,
                 "exec": execsim.EXEC_VERSION,
                 "cycle": cycles.CYCLES_VERSION}

app = FastAPI(title="SniperSight", version="0.1-draft")
STATIC = Path(__file__).resolve().parent / "static"

VALID_TFS = set(importer.TF_SECONDS)


@app.get("/api/candles")
def candles(symbol: str = "BTC-USD", tf: str = "1H", limit: int = 1500,
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
        rows = store.get_facts(con, symbol, tf, "exec", execsim.EXEC_VERSION)
        outs = [json.loads(r["payload"]) for r in rows]
        rs = [float(o["r_multiple"]) for o in outs]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r < 0]
        return {"n": len(outs),
                "tp": sum(1 for o in outs if o["outcome"] == "TP"),
                "sl": sum(1 for o in outs if o["outcome"] == "SL"),
                "timeout": sum(1 for o in outs if o["outcome"] == "TIMEOUT"),
                "win_rate": round(len(wins) / len(rs), 3) if rs else None,
                "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
                "sum_r": round(sum(rs), 2), "by_setup": {o["setup_id"]: o for o in outs}}
    finally:
        con.close()


@app.get("/api/portfolio")
def portfolio():
    """Paper account state from risk-authority facts (§9/§13 dashboard)."""
    con = store.connect()
    try:
        # authoritative summary from the risk authority (§8: never re-derive equity)
        arow = con.execute(
            "SELECT payload FROM facts WHERE kind='account' AND algo_version=? "
            "ORDER BY id DESC LIMIT 1", (risk.RISK_VERSION,)).fetchone()
        acct = json.loads(arow[0]) if arow else None
        recent, kills = [], 0
        for r in store.get_facts(con, "PORTFOLIO", "ALL", "risk", risk.RISK_VERSION):
            p = json.loads(r["payload"])
            if p.get("event") == "KILL_SWITCH":
                kills += 1
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "risk", risk.RISK_VERSION):
                    p = json.loads(r["payload"])
                    if p.get("event") == "DECISION":
                        recent.append({"symbol": sym, "tf": tf, "ts": r["confirmed_at"], **p})
        recent.sort(key=lambda d: d["ts"])
        eq = float(acct["final_equity"]) if acct else float(risk.START_EQUITY)
        return {"start_equity": float(risk.START_EQUITY), "equity": round(eq, 2),
                "return_pct": float(acct["return_pct"]) if acct else 0.0,
                "max_drawdown_pct": acct.get("max_drawdown_pct") if acct else None,
                "decisions": acct["decisions"] if acct else {},
                "kill_switch_days": kills,
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
        sized = {}   # setup_id -> risk_usd for APPROVED/REDUCED
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "risk", risk.RISK_VERSION):
                    p = json.loads(r["payload"])
                    if p.get("event") == "DECISION" and p["decision"] in ("APPROVED", "REDUCED"):
                        sized[p["setup_id"]] = float(p["risk_usd"])

        def blank():
            return {"n": 0, "wins": 0, "sum_r": 0.0, "pos_r": 0.0, "neg_r": 0.0,
                    "sized": 0, "pnl_usd": 0.0}
        by_sym, by_strat = {}, {}
        for sym in universe.all_tracked_symbols(con):
            for tf in ("15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
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
        return {"by_symbol": rows(by_sym), "by_strategy": rows(by_strat)}
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
    import urllib.request
    out = {}
    for sym in universe.all_tracked_symbols(con):
        try:
            req = urllib.request.Request(
                f"https://api.exchange.coinbase.com/products/{sym}/ticker",
                headers={"User-Agent": "snipersight/0.1"})
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode())
            out[sym] = {"price": float(d["price"]), "time": d["time"]}
        except Exception:
            out[sym] = None
    return out


@app.get("/api/overview")
def overview():
    """One call for the cockpit rails: watchlist, setup feed, engine health."""
    con = store.connect()
    try:
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
                        last_state[p["setup_id"]] = {"symbol": sym, "tf": tf,
                                                     "market_time": r["market_time"], **p}
                outs = {}
                for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
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
                    if p.get("event") == "DECISION":
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

        return {"symbols": symbols, "feed": feed[:40], "scanner": scanner,
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
        gaps = con.execute("SELECT COALESCE(SUM(n_gaps),0) FROM import_log").fetchone()[0]
        return {"facts": f, "gap_candles_logged": gaps, "algo_version": swings.SWING_VERSION,
                "candles": [{"symbol": s, "tf": t, "n": n, "first": lo, "last": hi}
                            for s, t, n, lo, hi in c]}
    finally:
        con.close()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html",
                        headers={"Cache-Control": "no-cache, must-revalidate"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
