"""SniperSight API server — read-only over the fact store (§3: UI reads facts,
never derives them). Serves the chart UI at / and JSON at /api/*.

Run: uvicorn server:app --port 8422
"""
import json
import os
import re
import threading
import time
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engine import registry, store, swings, importer, structure, zones, liquidity, regime, setups, execsim, risk, scalein, cycles, universe, marketdata, telemetry, quality, apexbridge
from engine import momentum, volatility, volume, ma, fvg, volprofile, ranges
from engine import costs, venues
from engine import achievements, automation, broker_factory, contracts, execution, learning, market_context, opportunities, positions, venues
from engine import factorgrade as factorgrade_engine, factorstats as factorstats_engine
from engine import edgestats

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
                 "risk": risk.RISK_VERSION,
                 # THE EVIDENCE ENGINES, previously unreachable over HTTP.
                 # They ran on every cycle and wrote hundreds of thousands of
                 # facts that no surface could request: momentum 194,753,
                 # volume 231,946, ma 171,982, volatility 83,771, fvg 74,596,
                 # volprofile 20,050, range 12,367 (measured 4 Aug 2026).
                 # Meanwhile the chart offered a Cycle layer over 116 facts.
                 # An engine the operator cannot see is an engine that cannot
                 # inform a decision.
                 "momentum": momentum.MOMENTUM_VERSION,
                 "volatility": volatility.VOLATILITY_VERSION,
                 "volume": volume.VOLUME_VERSION,
                 "ma": ma.MA_VERSION,
                 "fvg": fvg.FVG_VERSION,
                 "volprofile": volprofile.VOLPROFILE_VERSION,
                 "range": ranges.RANGES_VERSION}

app = FastAPI(title="SniperSight", version="0.1-draft")
STATIC = Path(__file__).resolve().parent / "static"

# Responses compress before they leave. Loopback made this look pointless; a
# phone on cellular is the case that pays for it. Measured 4 Aug 2026 on this
# store: overview 8x, setup-telemetry 10x, pipeline-health 29x. The floor keeps
# small JSON uncompressed, where the header costs more than the saving.
app.add_middleware(GZipMiddleware, minimum_size=1000)


#: How far a client-supplied arm timestamp may sit from this machine's clock.
#: Wide enough for a phone that has not synced in a while and for a retry that
#: waited out a cellular stall; far short of a value stale enough to name the
#: wrong bar. See /api/manual/arm for why the caller gets to name it at all.
ARM_CLOCK_SKEW_S = 120

ALLOWED_USERS_FILE = Path(__file__).resolve().parent / "data" / "allowed-users.txt"


def _allowed_users() -> set:
    """Who may reach this app from another device on the tailnet.

    One address per line, `#` comments ignored, matched case-insensitively.
    Read per request rather than cached: revoking access should take effect
    when the operator saves the file, not when they next remember to restart.
    The file is small and the OS caches it.

    `SNIPERSIGHT_ALLOWED_USERS` (comma separated) overrides the file, for a
    scratch instance that should not touch the operator's config.
    """
    env = os.environ.get("SNIPERSIGHT_ALLOWED_USERS")
    if env is not None:
        return {u.strip().lower() for u in env.split(",") if u.strip()}
    try:
        lines = ALLOWED_USERS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {ln.strip().lower() for ln in lines
            if ln.strip() and not ln.lstrip().startswith("#")}


@app.middleware("http")
async def _gate(request, call_next):
    """Who is allowed in, and what a page they merely visited may make them do.

    Two refusals, deliberately in one place, because both answer "should this
    request run at all" and splitting them invites an ordering bug.

    ── WHO ──────────────────────────────────────────────────────────────────
    uvicorn binds 127.0.0.1, so there are exactly two ways to arrive: from
    this machine, or through the `tailscale serve` proxy. Measured 4 Aug 2026,
    the proxy injects `X-Forwarded-For` and `Tailscale-User-Login` and
    OVERWRITES both if the client sent its own — a request carrying a forged
    `attacker@evil.example` arrived with the real address substituted. So the
    identity is Tailscale's assertion, not the caller's claim.

    That makes a password the weaker option, not the stronger one. The device
    is on the tailnet because it already authenticated; a second secret would
    add something to phish, forget and leak, and would still be revoked from
    the same admin console. Access is withdrawn by removing the device or the
    user there, or by editing data/allowed-users.txt.

    `X-Forwarded-For` absent means nothing proxied the request, so it came
    from this machine — the desktop cockpit, the watchdog's health poll, the
    suites. Those are exempt: anything with code execution here already has
    the database. A browser cannot forge the header either way; it is on the
    forbidden list that page script may not set.

    Present-but-no-identity is refused rather than trusted. That is what a
    Tailscale *Funnel* request looks like — the public internet — so enabling
    Funnel by accident fails closed instead of publishing the book.

    ── WHAT ─────────────────────────────────────────────────────────────────
    Twelve endpoints write. Four took their arguments from the query string —
    `/api/system/restart`, `/api/analyse`, `/api/baseline/reset`, `/api/scan`
    — and a POST with no body is exactly what a plain HTML form sends, so any
    page the operator happened to visit could fire them at localhost:8422. The
    browser blocks the attacker from READING the reply; it does not block the
    request, and the side effect has already happened. `/api/baseline/reset`
    is the one that hurts: undoable only by editing the database by hand.

    Guarding here rather than per endpoint covers all twelve POSTs plus the
    two GET handlers that call `manual.run()` and therefore record fills — a
    per-endpoint body change would have left those two open, which is the more
    interesting hole — and needs no edit to the ~17 fetch() call sites.

    `Sec-Fetch-Site` is set by the browser and page script cannot forge it.
    Absent means the caller is not a browser, which is not the case CSRF
    describes. `none` is a typed address or a bookmark; the app's own requests
    are `same-origin`.
    """
    who = request.headers.get("tailscale-user-login")
    if request.headers.get("x-forwarded-for") is not None:
        allowed = _allowed_users()
        if not who:
            return _refuse(request, 403, "anonymous",
                           "This request reached the app without a Tailscale "
                           "identity. Funnel and other public proxies are not "
                           "permitted; use the tailnet address.")
        if who.lower() not in allowed:
            return _refuse(
                request, 403, who,
                f"{who} is not permitted on this instance. Add the address to "
                f"{ALLOWED_USERS_FILE.name} on the host, one per line."
                if allowed else
                f"No operator is configured, so every remote device is "
                f"refused. Create {ALLOWED_USERS_FILE} containing {who}.")

    if request.url.path.startswith("/api/"):
        site = request.headers.get("sec-fetch-site")
        if site is not None and site not in ("same-origin", "none"):
            return JSONResponse(
                {"detail": f"cross-site request to {request.url.path} refused"},
                status_code=403)
    return await call_next(request)


def _refuse(request, code: int, who: str, detail: str):
    """A refusal the operator can act on, in the format the caller can read.

    A phone that gets bare JSON where it expected a page shows a blank screen,
    which reads as "the app is broken" rather than "this device is not on the
    list" — and the second is the one that tells them what to do.
    """
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": detail, "identity": who}, status_code=code)
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>SniperSight — not permitted</title>"
        "<body style=\"margin:0;display:grid;place-items:center;min-height:100vh;"
        "background:#11120e;color:#d6dbd0;font:14px/1.6 system-ui,sans-serif\">"
        "<main style='max-width:34rem;padding:2rem'>"
        "<h1 style='font:600 15px system-ui;letter-spacing:.12em'>NOT PERMITTED</h1>"
        f"<p>{detail}</p>"
        "<p style='color:#7d857a'>Paper trading only. No live execution exists "
        "in this application.</p></main>", status_code=code)


@app.get("/api/whoami")
def whoami(request: Request):
    """How the app sees the caller. Reaching this at all means it let you in.

    Exists so "is the phone actually authenticated, or merely reaching a
    server that never checks?" is a question with an observable answer. A gate
    nobody can see the output of is a gate nobody notices has stopped working.
    """
    proxied = request.headers.get("x-forwarded-for") is not None
    return {"identity": request.headers.get("tailscale-user-login"),
            "name": request.headers.get("tailscale-user-name"),
            "via": "tailnet" if proxied else "this machine",
            "checked": proxied,
            "allowed_users_configured": len(_allowed_users())}

VALID_TFS = set(importer.TF_SECONDS)

# Ticker shape. This was `^[A-Z0-9]+-USD$` — a Coinbase-spot spelling, written
# when every symbol looked like BTC-USD. The universe moved to perps in S34 and
# the pattern did not, so FastAPI rejected the entire tradeable universe at
# validation before a single line of handler ran.
#
# Measured 2026-07-30, every symbol in `universe.scan_symbols`: **0 of 33 could
# load a chart. All 33 returned HTTP 422.** `BTCUSDT` has no hyphen; `PF_XBTUSD`
# additionally has an underscore, which `[A-Z0-9]` excludes. The Chart surface
# has been completely dead for the whole perp era, and it failed at the
# framework boundary — so no handler logged anything and no health check saw it.
#
# Deliberately a SHAPE check, not a whitelist: the handler already returns an
# empty series for a symbol it does not hold, which is the honest answer for an
# unknown ticker. A regex that encodes one venue's naming convention is exactly
# what went wrong here, and swapping it for a different hardcoded convention
# would repeat it.
SYMBOL_PATTERN = r"^[A-Z0-9][A-Z0-9_-]{1,23}$"


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
def candles(symbol: str = Query("BTC-USD", pattern=SYMBOL_PATTERN),
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


# /api/swings and /api/track retired 2026-07-31 (audit, part C).
#
# swings was a strict subset of /api/facts?kind=swing — the SAME store.get_facts
# call with the same as_of cursor, plus a tier filter any client can apply to
# the rows it already has. The chart moved to /api/facts long ago, and a second
# route over one query is a second contract to keep honest for zero readers.
#
# track computed a per-symbol R record that /api/performance.by_symbol already
# serves to Results. The audit's verdict was "surface it or delete"; it was
# redundant with what is surfaced, so it is deleted. Neither route had a single
# reference anywhere in static/, tests/ or tools when removed.


@app.get("/api/facts")
def facts(kind: str, symbol: str = "BTC-USD", tf: str = "1H",
          as_of: int | None = None,
          bars: int | None = Query(None, ge=1, le=5000),
          response: Response = None):
    """Generic as_of-cursored fact query — the same contract for every engine.

    `bars` bounds the answer to the last N BARS, not the last N facts, and the
    window is computed from the candle table — the same rows the caller is
    drawing. That distinction matters: a count of facts would cut a different
    depth for every kind, so the swings would reach further back than the
    moving averages and the chart would draw a structure whose supporting
    evidence had been trimmed off.

    Unbounded by default, because this endpoint had no limit clause at all and
    the fact store is append-only and grows forever. Measured 4 Aug 2026 for
    BTCUSDT 4H alone: swing 134KB, ma 131KB, volume 70KB, momentum 63KB, fvg
    56KB, volatility 53KB — about half a megabyte for one symbol on one
    timeframe, every load, to draw markers over 1500 bars. The chart never had
    any use for a fact older than its oldest candle; it downloaded them and
    threw them away, which is invisible on loopback and is most of the page
    weight on a phone.

    Truncation is announced in `X-Facts-Window`, never silent. A caller that
    asked for a window it did not get must be able to find out without
    counting rows and guessing.
    """
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    if kind not in KIND_VERSIONS:
        raise HTTPException(400, f"kind must be one of {sorted(KIND_VERSIONS)}")
    versions = ([setups.SETUP_VERSION, scalein.SCALE_VERSION] if kind == "setup"
                else [KIND_VERSIONS[kind]])
    con = store.connect()
    try:
        cutoff = None
        if bars is not None:
            window = store.get_candles(con, symbol, tf,
                                       end_ts=as_of or 2**53, limit=bars)
            if window:
                cutoff = window[0]["open_ts"]
        out = []
        dropped = 0
        for ver in versions:
            for r in store.get_facts(con, symbol, tf, kind, ver, as_of):
                if cutoff is not None and r["market_time"] < cutoff:
                    dropped += 1
                    continue
                out.append({"market_time": r["market_time"],
                            "confirmed_at": r["confirmed_at"],
                            "algo_version": r["algo_version"], **json.loads(r["payload"])})
        out.sort(key=lambda f: f["market_time"])
        if response is not None:
            response.headers["X-Facts-Window"] = (
                "unbounded" if cutoff is None
                else f"from={cutoff} bars={bars} kept={len(out)} older_dropped={dropped}")
        return out
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
                # Keyed on setup_id alone, deliberately. A setup_id is
                # `symbol|tf|strategy|zone_id|version` and a zone validates once,
                # so this is already unique per VALIDATED setup: checked across
                # every setup version in the store, zero setup_ids reach
                # VALIDATED at two different confirmed_at. Repeat facts under one
                # id are the same instance re-recorded with fresher `confluence`
                # (144 of them in the current book), and collapsing those to the
                # newest is the intended behaviour, not a merge defect.
                setup_by_id[p["setup_id"]] = {
                    "symbol": sym, "tf": timeframe, "market_time": market_time,
                    "confirmed_at": confirmed_at, "algo_version": algo_version, **p}

        def lifecycle_map(kind, version):
            """Latest downstream fact per setup.

            `ORDER BY confirmed_at,id` plus overwrite means the newest event
            wins, which is the point for orders — PLACED and FILLED both exist
            and the later one is the state. Where one setup_id carries several
            exec facts (the same trade re-simulated under a different cost
            manifest) the newest is likewise the current costing.
            """
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

        # The stage BEFORE the funnel's first stage. The funnel starts at
        # "candidates" — zones price actually reached — so a symbol whose DATA
        # never arrived produces no candidates and simply isn't in the picture.
        # PF_XLMUSD spent 24 cycles that way, invisible precisely where "why is
        # nothing firing" needed the answer. `pipeline_gates` is current state,
        # written by the one engine loop; a tf filter must keep the '*' rows,
        # because a symbol-wide gate applies to every timeframe asked about.
        data_gates = [
            {"symbol": s, "tf": t, "gate": g, "detail": d, "since": m}
            for s, t, g, d, m in con.execute(
                "SELECT symbol, tf, gate, detail, measured_at FROM pipeline_gates "
                "ORDER BY measured_at, symbol, tf")
            if (not symbol or s == symbol) and (not tf or t in (tf, "*"))]

        # Engine exceptions, as current state — the list Diagnostics leads
        # with. Same lifecycle as data_gates: a clean run clears the row.
        engine_faults = [
            {"symbol": r0, "tf": r1, "engine": r2, "error": r3,
             "since": r4, "last_seen": r5, "times": r6}
            for r0, r1, r2, r3, r4, r5, r6 in con.execute(
                "SELECT symbol, tf, engine, error, first_seen, last_seen, times "
                "FROM engine_faults ORDER BY last_seen DESC")
            if (not symbol or r0 == symbol) and (not tf or r1 == tf)]

        # Vocabulary drift, marked where it becomes visible. A reason string
        # in the store that `setups.REJECTION_REASONS` does not contain means
        # an engine grew a word the funnel has no sentence for — the exact
        # silent decay the prior project guarded with _KNOWN_REASONS.
        unlabelled = sorted(
            r for r in rejected_candidates
            if r.split("(")[0] not in setups.REJECTION_REASONS)

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
            "data_gates": data_gates,
            "engine_faults": engine_faults,
            "unlabelled_rejections": unlabelled,
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
        #
        # Deliberately NOT pinned to the current algo_version, unlike the funnel
        # endpoints. A trace is asked about one setup the operator can see; if
        # the engine version has since moved on, "404 unknown setup" would be a
        # lie about a setup that plainly exists. Instead every fact reports the
        # version it was written under and `stale_versions` names the mismatch,
        # so the drawer can say "recorded under an older engine" out loud.
        def payloads(kind: str) -> list[dict]:
            out = []
            rows = con.execute(
                "SELECT symbol,tf,market_time,confirmed_at,algo_version,payload "
                "FROM facts WHERE kind=? ORDER BY confirmed_at,id", (kind,)).fetchall()
            for sym, timeframe, market_time, confirmed_at, algo_version, raw in rows:
                p = json.loads(raw)
                if p.get("setup_id") != setup_id:
                    continue
                out.append({"symbol": sym, "tf": timeframe,
                            "market_time": market_time,
                            "confirmed_at": confirmed_at,
                            "algo_version": algo_version, **p})
            return out

        setup_facts = payloads("setup")
        if not setup_facts:
            raise HTTPException(
                404, f"no setup recorded with id {setup_id!r}")

        # The last fact is the setup's current truth; the earlier ones are its
        # state history (FORMING -> VALIDATED, or -> CANCELLED).
        setup = setup_facts[-1]
        risk_facts = [p for p in payloads("risk")
                      if p.get("event") == "DECISION"]
        order_facts = payloads("order")
        exec_facts = payloads("exec")
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
                 "CONFIRMING": "pending", "CANCELLED": "fail",
                 "EXPIRED": "fail"}.get(state, "skip"),
                value=state, expected="VALIDATED",
                detail={"VALIDATED": "price reached the zone and every entry gate passed",
                        "FORMING": "price is approaching the zone but has not reached it",
                        "CONFIRMING": "price reached the zone; waiting for the confirming close",
                        "CANCELLED": "the structure this setup relied on broke first",
                        "EXPIRED": "the entry window closed before price confirmed"
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
                value=("not filled" if outcome == "MISSED"
                       else f"{outcome} · {net_r}R net"),
                expected="a positive net R after costs",
                # Deliberately NOT lifecycle["detail"]: on a risk-rejected setup
                # that reads "NOT_IN_POINT_IN_TIME_UNIVERSE" on the exit row,
                # which describes a different gate entirely.
                detail=("the limit was never touched inside the entry window"
                        if outcome == "MISSED" else
                        f"held {exec_fact.get('bars_held')} bars · "
                        f"{exec_fact.get('r_gross')}R gross became {net_r}R "
                        f"after {exec_fact.get('costs_r')}R of costs"),
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

        # A fact written by a superseded engine is still a real fact, but the
        # thresholds it was judged against may no longer be the running ones.
        # Name every mismatch instead of quietly rendering old numbers as fresh.
        stale = []
        for kind, fact, current in (
                ("setup", setup, (setups.SETUP_VERSION, scalein.SCALE_VERSION)),
                ("risk", risk_fact, (risk.RISK_VERSION,)),
                ("order", order_fact, (execsim.EXEC_VERSION,)),
                ("execution", exec_fact, (execsim.EXEC_VERSION,))):
            if fact and fact["algo_version"] not in current:
                stale.append({"kind": kind, "recorded": fact["algo_version"],
                              "current": current[0]})

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
            "versions": {
                "recorded": {"setup": setup["algo_version"],
                             "risk": risk_fact["algo_version"] if risk_fact else None,
                             "order": order_fact["algo_version"] if order_fact else None,
                             "execution": exec_fact["algo_version"] if exec_fact else None},
                "current": {"setup": setups.SETUP_VERSION,
                            "scale_in": scalein.SCALE_VERSION,
                            "risk": risk.RISK_VERSION,
                            "execution": execsim.EXEC_VERSION}},
            # Named so the drawer can say "this trace predates the running
            # engine" rather than presenting stale numbers as current ones.
            "stale_versions": stale,
        }
    finally:
        con.close()


def _journal_performance_summary(journal: list[dict], baseline: dict) -> dict:
    """One server-owned scoreboard for the current funded forward book."""
    values = [Decimal(str(row["r_multiple"])) for row in journal
              if row.get("r_multiple") is not None]
    wins = [value for value in values if value > 0]
    losses = [-value for value in values if value < 0]
    n = len(values)
    avg = (sum(values, Decimal(0)) / n if n else None)
    profit_factor = (sum(wins, Decimal(0)) / sum(losses, Decimal(0))
                     if losses and wins else None)
    boot = edgestats._bootstrap_mean([float(value) for value in values], 5000)
    confidence = ({"status": "MEASURED", "lo": round(boot["ci_lo"], 4),
                   "hi": round(boot["ci_hi"], 4), "resamples": 5000,
                   "method": "DETERMINISTIC_BOOTSTRAP_MEAN"}
                  if boot else {"status": "INSUFFICIENT_EVIDENCE", "lo": None,
                                "hi": None, "resamples": 0,
                                "minimum_trades": edgestats.MIN_TRADES,
                                "method": "DETERMINISTIC_BOOTSTRAP_MEAN"})
    if n < 10:
        verdict = {"code": "INSUFFICIENT_EVIDENCE",
                   "text": f"{n} closed trade{'s' if n != 1 else ''}; too few to judge the method."}
    else:
        verdict = {"code": "REVIEW_CONFIDENCE_INTERVAL",
                   "text": "The sample can be measured; read the confidence interval before trusting it."}
    return {
        "population": "FUNDED_PAPER_TRADES", "window": "ACTIVE_BASELINE",
        "baseline_id": baseline.get("baseline_id") or baseline.get("id"),
        "started_at": baseline.get("started_at"), "trades": n,
        "wins": len(wins), "win_pct": (round(100 * len(wins) / n) if n else None),
        "average_r": (float(avg.quantize(Decimal("0.0001"))) if avg is not None else None),
        "profit_factor": (float(profit_factor.quantize(Decimal("0.01")))
                          if profit_factor is not None else None),
        "has_losses": bool(losses),
        "best_r": float(max(values)) if values else None,
        "worst_r": float(min(values)) if values else None,
        "confidence_interval_r": confidence,
        "verdict": verdict,
    }


def _performance_dimensions(journal: list[dict], baseline: dict) -> dict:
    """Comparable funded-book cuts; unknown metadata stays explicitly unknown."""
    def rows(field):
        buckets: dict[str, list[dict]] = {}
        for trade in journal:
            key = str(trade.get(field) or "NOT_REPORTED")
            buckets.setdefault(key, []).append(trade)
        out = []
        for key, trades in sorted(buckets.items()):
            rs = [Decimal(str(trade.get("r_multiple") or 0)) for trade in trades]
            pnl = sum((Decimal(str(trade.get("pnl_usd") or 0)) for trade in trades), Decimal(0))
            wins = sum(value > 0 for value in rs)
            out.append({"key": key, "n": len(trades),
                        "win_pct": round(100 * wins / len(trades)),
                        "average_r": float((sum(rs, Decimal(0)) / len(rs)).quantize(Decimal("0.0001"))),
                        "sum_r": float(sum(rs, Decimal(0)).quantize(Decimal("0.01"))),
                        "pnl_usd": float(pnl.quantize(Decimal("0.01"))),
                        "population": "FUNDED_PAPER_TRADES"})
        return out
    return {"window": "ACTIVE_BASELINE", "population": "FUNDED_PAPER_TRADES",
            "baseline": baseline, "dimensions": {
                field: rows(field) for field in
                ("strategy", "symbol", "regime", "horizon", "direction", "order_type")}}


def _envelope_config(con, eq: float) -> dict:
    """The envelope of the book being DISPLAYED — the paper book — plus the
    dispatch mode's R as separate, labelled information.

    One basis per calculation. The meters here divide paper-book dollars by
    envelope budgets, so the budgets must be paper's (2% R): subtracting a
    $200 paper position from a 0.25%-mode $50 budget reads as an exhausted
    envelope while actual testnet exposure is $25 against $50 (cold audit
    2026-08-08, finding 1). What the CURRENT mode risks per dispatched trade
    is reported alongside, never mixed into the arithmetic.
    """
    mode = automation.current(con)[0]
    g = risk.gates_for_mode(risk.AutomationMode.PAPER)
    dispatch_pct = risk.MODE_RISK_PCT[mode]
    return {"mode": mode.value,
            "risk_pct": float(g["risk_pct"]) * 100,
            "max_total_risk_pct": float(g["max_total_open_risk_pct"]) * 100,
            "max_concurrent": g["max_concurrent"],
            "max_leverage": float(risk.MAX_LEVERAGE),
            "daily_loss_pct": float(g["daily_loss_limit_pct"]) * 100,
            "next_risk_usd": round(eq * float(g["risk_pct"]), 2),
            "dispatch_risk_pct": float(dispatch_pct) * 100}


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
        exec_by_id: dict = {}
        for r in store.get_facts(con, "PORTFOLIO", "ALL", "risk", risk.RISK_VERSION):
            p = json.loads(r["payload"])
            if r["confirmed_at"] >= since and p.get("event") == "KILL_SWITCH":
                kills += 1
        for sym in universe.all_tracked_symbols(con):
            for tf in ("5m", "15m", "1H", "4H", "1D", "1W"):
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
                    p = json.loads(r["payload"])
                    sid = p["setup_id"]
                    if sid in eligible:
                        completed.add(sid)
                        # keep the ending, not just the fact that one exists —
                        # this payload is the closed-trade journal's raw material
                        exec_by_id[sid] = {"symbol": sym, "tf": tf,
                                           "ts": r["confirmed_at"], **p}
        recent.sort(key=lambda d: d["ts"])
        # An operator override closes the position on the OPERATOR's book. The
        # engine's simulation is untouched and will still record its own
        # outcome for this setup; this only stops the cockpit showing exposure
        # the operator has declared finished.
        #
        # Matched on the VERSION-STRIPPED id, not the id itself. `setup_id`
        # embeds SETUP_VERSION, so an exact-match key made every override
        # expire the moment the engine version moved: the same zone was
        # re-derived under the new tag, the suppression stopped firing, and a
        # position the operator had closed came back as live exposure with
        # nothing announcing it. See `manual.setup_zone_key` for the measured
        # case and for what the wider key does and does not cover.
        from engine import manual as _manual
        overrides = _manual.overridden_setups(con)
        override_zones = _manual.overridden_zone_keys(overrides)
        positions, pending_orders = [], []
        for sid, order in latest_order.items():
            if sid in completed or _manual.setup_zone_key(sid) in override_zones:
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

        # The closed-trade journal. Only trades the risk authority actually
        # sized (APPROVED/REDUCED) — execsim also simulates every validated
        # setup as research, and mixing those shadow runs into the account's
        # own history would overstate activity the book never had. pnl_usd is
        # net R times the dollars that were at risk: the same arithmetic the
        # equity curve is built from.
        journal = []
        for sid, ex in exec_by_id.items():
            sized = risk_by_id.get(sid, {})
            if sized.get("decision") not in ("APPROVED", "REDUCED"):
                continue
            # A MISSED order is not a trade. execsim writes outcome='MISSED'
            # with r_multiple='0' when an armed limit's entry window expires
            # without price returning, and risk.py:490 excludes exactly these
            # from open_pos so they never become a position. Admitting them
            # here put a phantom row in the journal AND — because the
            # scoreboard counts anything not a winner as a loss — reported it
            # as a losing trade. Every other consumer in this file already
            # excludes MISSED; this is the one that forgot.
            if ex.get("outcome") == "MISSED":
                continue
            risk_usd = float(sized.get("risk_usd") or 0)
            r_net = float(ex.get("r_multiple") or 0)
            # The reason the trade was taken, from the setup that took it —
            # the setup's own `why` sentence and the regime it fired in. The
            # journal is the surface an operator reads to learn what their
            # system does; a row with an outcome but no reason teaches nothing.
            setup = setup_by_id.get(sid, {})
            strategy_contract = registry.for_engine_name(str(setup.get("strategy") or ""))
            order = latest_order.get(sid, {})
            journal.append({
                "setup_id": sid, "symbol": ex["symbol"], "tf": ex["tf"],
                "why": setup.get("why"),
                "regime": setup.get("regime"),
                "ts": ex["ts"],
                "direction": ex.get("direction"),
                "strategy": ex.get("strategy"),
                "horizon": setup.get("horizon") or (
                    strategy_contract.horizon if strategy_contract else None),
                "order_type": order.get("order_type") or setup.get("entry_model"),
                "outcome": ex.get("outcome"),
                "r_multiple": r_net,
                "r_gross": float(ex.get("r_gross") or 0),
                "costs_r": float(ex.get("costs_r") or 0),
                "holding_hours": ex.get("holding_hours"),
                "risk_usd": risk_usd,
                # Decimal, from the raw payload strings, quantized the same way
                # risk.py builds the equity curve. Both operands arrive 2dp-
                # quantized, so the product lands on exactly 4 decimals and
                # half-cent ties are reachable — where Python's round() banks
                # to even and the engine's quantize() rounds half up. A journal
                # that disagrees with the curve by a cent is a journal nobody
                # trusts the rest of.
                "pnl_usd": float((Decimal(str(ex.get("r_multiple") or 0)) *
                                  Decimal(str(sized.get("risk_usd") or 0)))
                                 .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "entry": ex.get("entry"), "exit_price": ex.get("exit_price"),
                "decision": sized.get("decision")})
        journal.sort(key=lambda j: -j["ts"])
        eq = float(acct["final_equity"]) if acct else float(risk.START_EQUITY)
        return {"baseline": baseline,
                "start_equity": float(risk.START_EQUITY), "equity": round(eq, 2),
                "return_pct": float(acct["return_pct"]) if acct else 0.0,
                "max_drawdown_pct": acct.get("max_drawdown_pct") if acct else None,
                "decisions": acct["decisions"] if acct else {},
                "kill_switch_days": kills,
                "active_positions": positions,
                "operator_closed": sorted(overrides.values(),
                                          key=lambda d: d["closed_at"],
                                          reverse=True)[:20],
                # The operator's own exits on the ENGINE's trades — the engine
                # picked the setup, the operator picked the moment. This money
                # is counted in no other total on this payload or in the manual
                # book, so without this field it is on screen row by row and
                # nowhere in a sum.
                #
                # Summed over EVERY override, not over the 20 rows above: the
                # same rule `journal`/`journal_total` follows two fields down.
                # A total that silently meant "the visible ones" would be
                # wrong the day a 21st close is recorded, and wrong quietly.
                # `usd_at_close` is already 2dp from manual.py, so the sum is
                # exact and the quantize is shape, not rounding.
                # NULL IS NOT ZERO, the same rule `total_pnl_usd` follows on
                # the manual book. Summing with Decimal(0) always produced a
                # float, so a book whose every close was unpriceable reported
                # $0.00 — which reads as "broke even" rather than "could not
                # be priced", and the UI's `== null` guard could never fire.
                # THREE ANSWERS, NOT TWO, and the middle one is the whole
                # point. `if any(priceable) else None` collapsed the first two:
                #
                #   nothing closed at all        -> 0.00, a REAL zero. You
                #                                   closed nothing, so you made
                #                                   nothing. Saying "unknown"
                #                                   here is its own lie.
                #   closed, none priceable       -> None. The money is not
                #                                   knowable, and 0.00 would
                #                                   read as "broke even".
                #   closed, some priceable       -> the sum.
                #
                # An empty book therefore reported "unknown" on a surface whose
                # rule is that null and zero are different claims. Caught by
                # test_ledger_field_contract's own sentence — "no closes is a
                # real zero, but only when there are no closes" — which fails
                # against an empty store and passes against a populated one,
                # so it only ever fired where nobody was looking: CI.
                "operator_closed_usd": (
                    0.0 if not overrides
                    else float(sum((Decimal(str(o["usd_at_close"]))
                                    for o in overrides.values()
                                    if o.get("usd_at_close") is not None), Decimal(0))
                               .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    if any(o.get("usd_at_close") is not None
                           for o in overrides.values()) else None),
                # How many closes that sum leaves out. A close recorded against
                # a position with no risk figure has an R and no dollars,
                # permanently — the same degraded path `n_no_risk_usd` reports
                # on the manual book, and audible for the same reason.
                "operator_closed_no_usd": sum(
                    1 for o in overrides.values()
                    if o.get("usd_at_close") is None),
                "pending_orders": pending_orders,
                "open_risk_usd": round(sum(float(p["risk_usd"] or 0)
                                           for p in positions), 2),
                "curve": [{"ts": c["ts"], "equity": float(c["equity"])}
                          for c in (acct["curve"] if acct else [])],
                "recent": recent[-25:],
                # Untruncated. The UI reduces over this list to produce the
                # "closed today" tile and the risk-budget loss meter, and a
                # sliced list would make both quietly wrong the moment the
                # window held more trades than the slice — while the chip
                # above them read "30 closed" as if it were the window total.
                # `journal_total` is emitted regardless so that a cap
                # reintroduced later cannot silently lie about being complete.
                "journal": journal,
                "journal_total": len(journal),
                "performance_summary": _journal_performance_summary(journal, baseline),
                "config": _envelope_config(con, eq)}
    finally:
        con.close()


SCANNER_STALE_S = 90            # heartbeat beats per stage; 90s means stuck
WATCHDOG_LOCK_PORT = 8423       # watchdog.py holds a listening lock socket here
HEARTBEAT = STATIC.parent / "data" / "heartbeat.json"


def _audit_kill(pid: int) -> None:
    """Write who asked for a process to die, next to the supervisor's own log.

    Best-effort and silent on failure: an audit line must never be able to stop
    the thing it is auditing, which is the same rule the notifier learned.
    """
    import traceback
    try:
        # The call stack names the endpoint. `/api/system/restart` and the
        # wizard's `?target=scanner` are different callers reaching the same
        # taskkill, and the difference is the whole question.
        stack = [f.name for f in traceback.extract_stack()[:-2]][-6:]
        line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"api-server: KILLING pid={pid} via {' > '.join(stack)}\n")
        with open(STATIC.parent / "data" / "watchdog.log", "a",
                  encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _stop_pid(pid: int) -> tuple[bool, str]:
    """Stop a process and report the OBSERVED outcome.

    Windows note: os.kill(pid, SIGTERM) does terminate the target but can still
    raise WinError 87, so trusting the exception produced a false "stop failed"
    while the watchdog log showed a clean exit. taskkill reports truthfully.

    EVERY KILL FROM HERE IS RECORDED, into the supervisor's own log rather than
    only into the HTTP reply nobody keeps.

    The scanner has exited 356 times, always rc=1, always "NOT ended by this
    supervisor". rc=1 is what `taskkill /F` produces, and taskkill is reached
    from exactly two places: this function, and the watchdog's clear_orphans —
    which already logs every kill it makes. So if the deaths are taskkills and
    the supervisor is not making them, they came through here, and until now
    that left no trace at all: the caller got a JSON reply and the log got
    nothing. The next exit therefore answers the question either way — a line
    beside it, or the absence of one.
    """
    import os
    import signal
    import subprocess
    import sys
    _audit_kill(pid)
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


@app.get("/api/performance/dimensions")
def performance_dimensions():
    """Funded forward-book results by operator comparison dimension."""
    payload = portfolio()
    return _performance_dimensions(payload.get("journal") or [],
                                   payload.get("baseline") or {})


@app.get("/api/performance")
def performance():
    """Per-symbol / per-strategy paper performance, PARTITIONED BY WHETHER THE
    ACCOUNT ACTUALLY TOOK THE TRADE.

    This used to mix two populations inside one row: n/win_pct/pf/sum_r counted
    every trade the simulator closed, while sized/pnl_usd counted only the ones
    the risk authority funded. The row described nothing — no arithmetic got you
    from one column to the next. Live, BTCUSDT read "2 trades, 50% win, +1.77R"
    beside "-$19.46", because a +1.87R trade the account was never allowed to
    take was summed into the R column and correctly absent from the dollars.
    The Trade Journal, three panels above, showed the same symbol at -0.10R.

    Every exec fact now answers one question — did the risk authority put money
    behind it? — and everything else (untradeable venue, concurrency cap,
    point-in-time universe) is the REASON it did not, which belongs on the row
    rather than in a bucket name:

        by_*          the account's book: trades it funded
        untaken_*     found on a tradeable symbol, never funded
        shadow_*      found on a venue that was never tradeable at all

    Every field in a row describes the same population, so the row reconciles.
    """
    con = store.connect()
    try:
        baseline, eligible = _baseline_setup_ids(con)
        sized = {}    # setup_id -> risk_usd for APPROVED/REDUCED
        refused = {}  # setup_id -> the reason it was not funded
        for sym in universe.all_tracked_symbols(con):
            for tf in ("5m", "15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "risk", risk.RISK_VERSION):
                    p = json.loads(r["payload"])
                    if p.get("event") != "DECISION" or p.get("setup_id") not in eligible:
                        continue
                    if p["decision"] in ("APPROVED", "REDUCED"):
                        sized[p["setup_id"]] = float(p["risk_usd"])
                    else:
                        rs = p.get("reasons") or []
                        refused[p["setup_id"]] = rs[0] if rs else "REJECTED"

        # A SHADOW symbol is imported and derived but never tradeable, and
        # `risk.py` rejects every one of its intents with
        # NOT_IN_POINT_IN_TIME_UNIVERSE. Counting those exec facts into the
        # operator's track record was reporting a book that could not have been
        # placed: measured 2026-07-30, 5 of the 6 baseline trades (83%) were
        # Kraken PF_* shadow symbols. Only the $-column excluded them, because
        # `sized` reads the risk decision and the R-columns did not.
        #
        # They are still SEPARATED rather than dropped — a warmed venue's
        # simulated record is the evidence for admitting it, so it has to remain
        # visible. It just must not be added to the traded book.
        shadow = set(universe.shadow_symbols(con))

        def blank():
            return {"n": 0, "wins": 0, "sum_r": 0.0, "pos_r": 0.0, "neg_r": 0.0,
                    "pnl_usd": 0.0, "reasons": {}}
        by_sym, by_strat = {}, {}          # taken — the account's book
        un_sym, un_strat = {}, {}          # tradeable symbol, never funded
        sh_sym, sh_strat = {}, {}          # untradeable venue
        untaken_n = {}                     # taken key -> trades it did NOT fund
        for sym in universe.all_tracked_symbols(con):
            is_shadow = sym in shadow
            for tf in ("5m", "15m", "1H", "4H", "1D", "1W"):
                for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                    p = json.loads(r["payload"])
                    if p["setup_id"] not in eligible or p["outcome"] == "MISSED":
                        continue
                    rm = float(p["r_multiple"])
                    ru = sized.get(p["setup_id"])
                    # Route on MONEY first, venue second. Routing on shadow
                    # first would file a funded trade under "never tradeable"
                    # if its venue were demoted later in the window — the
                    # membership is read at request time, the trade is not.
                    if ru is not None:
                        tgt = (by_sym, by_strat)
                    elif is_shadow:
                        tgt = (sh_sym, sh_strat)
                    else:
                        tgt = (un_sym, un_strat)
                    for key, bucket in ((sym, tgt[0]), (p["strategy"], tgt[1])):
                        a = bucket.setdefault(key, blank())
                        a["n"] += 1
                        a["wins"] += rm > 0
                        a["sum_r"] += rm
                        a["pos_r" if rm > 0 else "neg_r"] += rm
                        if ru is not None:
                            a["pnl_usd"] += ru * rm
                        else:
                            why = refused.get(p["setup_id"], "not funded")
                            a["reasons"][why] = a["reasons"].get(why, 0) + 1
                            # Counts the UNTAKEN bucket only, never shadow.
                            # This number is a pointer — "1 more found, not
                            # funded" sends the reader to the untaken block, so
                            # it has to equal what they will find there. Shadow
                            # has its own block and its own count; folding it in
                            # made by_strategy REVERSAL promise 5 rows against
                            # an untaken block holding 2.
                            if not is_shadow:
                                untaken_n[key] = untaken_n.get(key, 0) + 1

        def rows(bucket, population):
            taken = population == "taken"
            out = []
            for k, a in bucket.items():
                pf = round(a["pos_r"] / abs(a["neg_r"]), 2) if a["neg_r"] < 0 and a["pos_r"] > 0 else None
                row = {"key": k, "n": a["n"],
                       "win_pct": round(100 * a["wins"] / a["n"]) if a["n"] else 0,
                       "pf": pf, "sum_r": round(a["sum_r"], 2),
                       # NEVER 0.0 off the book. Zero renders as break-even, and
                       # a trade that was never funded did not break even — it
                       # did not happen. The empty-window rule, on a new row.
                       "pnl_usd": round(a["pnl_usd"], 2) if taken else None,
                       "population": population,
                       # Stable row schema: non-taken populations have no
                       # additional untaken cohort, but clients may render the
                       # same component for every population.
                       "untaken_n": untaken_n.get(k, 0) if taken else 0,
                       # kept for existing consumers that branch on it
                       "shadow": population == "shadow"}
                if taken:
                    # The exclusion travels WITH the figure it changes the
                    # meaning of: "1 trade, -0.10R" reads very differently once
                    # you know one more was found and not funded. The COUNT
                    # only — an R from the other population inside the traded
                    # table is the exact bug this partition removes.
                    row["untaken_n"] = untaken_n.get(k, 0)
                else:
                    row["reasons"] = dict(sorted(a["reasons"].items(),
                                                 key=lambda kv: -kv[1]))
                out.append(row)
            out.sort(key=lambda x: x["sum_r"])
            return out

        def totals(bucket, population):
            n = sum(a["n"] for a in bucket.values())
            return {"n": n,
                    "sum_r": round(sum(a["sum_r"] for a in bucket.values()), 2),
                    "pnl_usd": (round(sum(a["pnl_usd"] for a in bucket.values()), 2)
                                if population == "taken" else None)}

        return {"baseline": baseline,
                "by_symbol": rows(by_sym, "taken"),
                "by_strategy": rows(by_strat, "taken"),
                "untaken_by_symbol": rows(un_sym, "untaken"),
                "untaken_by_strategy": rows(un_strat, "untaken"),
                "shadow_by_symbol": rows(sh_sym, "shadow"),
                "shadow_by_strategy": rows(sh_strat, "shadow"),
                "totals": {"taken": totals(by_sym, "taken"),
                           "untaken": totals(un_sym, "untaken"),
                           "shadow": totals(sh_sym, "shadow")},
                "shadow_symbols": sorted(shadow)}
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
                f"A candle has to close back OUT of the zone, finishing in the "
                f"last {tail}% of its own range. That is the market rejecting "
                f"the level, not drifting off it. {setups.CONFIRM_MAX_BARS} bars "
                f"to do it, or the setup is dropped."),
            "stop_goes": (
                f"Just past the candle that did the rejecting: "
                f"{setups.SL_BUFFER_ATR} ATR beyond its low to buy, its high to "
                f"sell — a fraction of that market's usual daily movement. A "
                f"price the market has already tested and turned away from."),
        }
    return {
        "confirms": (
            "Nothing beyond the touch itself: the trade opens the moment price "
            "reaches the zone. This is the weakest part of the current engine "
            "and the entry rework exists to fix it."),
        "stop_goes": (
            f"A fraction of that market's typical daily movement "
            f"({setups.SL_ATR} ATR) beyond the far edge of the zone — the price "
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
            # The record now counts only trades the account FUNDED, matching
            # /api/performance's taken bucket — a catalogue that counted the
            # engine's unfunded research would advertise a strategy on trades
            # the operator was never allowed to take.
            return {"n": 0, "win_pct": None, "pf": None, "sum_r": 0.0,
                    "pnl_usd": 0.0, "untaken_n": 0, "population": "taken"}
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
    horizon = ("As long as the timeframe that found it: a 15m setup is usually "
               "over inside a day, a 1D setup can run for weeks.")

    cards = [
        {"key": registry.PULLBACK.key, "name": registry.PULLBACK.name,
         "status": registry.PULLBACK.status,
         "record_key": registry.PULLBACK.key.upper(),
         "setting": registry.PULLBACK.setting,
         "one_liner": "Buy the dip in an uptrend, sell the bounce in a downtrend.",
         "hunts": ("Trending markets. The engine's read has to be an uptrend to "
                   "buy and a downtrend to sell, including trends that are "
                   "weakening but not yet broken."),
         "triggers": ("Price comes back to a zone that turned it before — a "
                      "demand zone underneath in an uptrend, a supply zone "
                      "overhead in a downtrend."),
         "confirms": rules["confirms"], "stop_goes": rules["stop_goes"],
         "holds_for": horizon,
         "timeframes": list(registry.PULLBACK.timeframes),
         "notes": (f"Every candidate has to offer at least {setups.MIN_RR} of "
                   f"reward for every 1 it puts at risk, and has to risk at "
                   f"least {setups.MIN_RISK_COST_MULT}x what the trade will cost "
                   f"in exchange fees, or it is turned down before you see it.")},
        {"key": registry.REVERSAL.key, "name": registry.REVERSAL.name,
         "status": registry.REVERSAL.status,
         "record_key": registry.REVERSAL.key.upper(),
         "setting": registry.REVERSAL.setting,
         "one_liner": "Fade a move that has just run out of buyers, or sellers.",
         "hunts": ("Markets in transition — the old trend has broken down and "
                   "a new one has not formed yet."),
         "triggers": (f"A zone touch while the market is in transition, "
                      f"supported by {_reversal_rule_words()}. A transition on "
                      f"its own is not a trade — but one piece of evidence is "
                      f"not enough either, so two must agree."),
         "confirms": rules["confirms"], "stop_goes": rules["stop_goes"],
         "holds_for": horizon,
         "timeframes": list(registry.REVERSAL.timeframes),
         "notes": ("Starts 10 rank points below Pullback. Catching a turn is a "
                   "harder claim than following a trend, and the ranking says so.")},
        {"key": registry.SCALE_IN.key, "name": registry.SCALE_IN.name,
         "status": registry.SCALE_IN.status,
         "record_key": registry.SCALE_IN.key.upper(),
         "setting": registry.SCALE_IN.setting,
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
         "notes": ("Each add is sized as brand new exposure rather than folded "
                   "into the trade it joins, so a run of good luck cannot "
                   "quietly turn into one oversized bet.")},
        # NOT "planned" — measured and declined, and the card must say so.
        # ranges.py was built to hunt this trade and came back with the reason
        # not to take it (S40/S44): of the RANGE-regime rejections, 3 had a
        # live detected range at the moment of rejection, and on
        # structure-sound symbols ZERO did. Most of "the market is ranging"
        # was a blind structure engine (the tick floor), not a range to fade.
        {"key": "range_fade", "name": "Range Fade", "status": "planned",
         "record_key": None, "setting": None,
         "one_liner": "Sell the ceiling and buy the floor while a market goes nowhere.",
         "hunts": "Markets stuck between a ceiling and a floor, with no trend.",
         "triggers": ("Measured and declined, not pending. A range detector was "
                      "built to hunt this trade — 1,882 ranges across the "
                      "store — and at the moments this playbook would have "
                      "fired, almost none of them were live: 3 rejections had "
                      "an active range, zero on structurally sound symbols."),
         "confirms": ("Nothing is traded on this, on evidence rather than by "
                      "omission. Most of what looked like ranging markets was "
                      "a measurement bug since fixed, not fadeable ranges."),
         "stop_goes": "Would be beyond the range edge — untraded, so untested.",
         "holds_for": ("Revisited if ranges are redefined over something "
                       "longer-lived than a handful of consecutive pivots — "
                       "the current detector describes boxes inside macro "
                       "ranges, never the range itself."),
         "timeframes": [], "notes": None},
        # The 'Reversal, Reworked' planned card was REMOVED, not edited: the
        # work shipped in S38. Its 2-of-4 evidence gate replaced the sweep-only
        # rule and took REVERSAL from 5 setups in four years to several hundred.
        # A roadmap that still lists a delivered item as planned is a roadmap
        # nobody can trust — and this one described the OLD rule while the live
        # Reversal card described the new one, so the page contradicted itself.

    ]

    # Research playbooks are real contracts, not "coming soon" decoration.
    # They remain non-live and have no funded record, but the API publishes the
    # trigger, timeframe, evidence state and exact contraindications now so the
    # scanner and UI have one vocabulary when evidence eventually promotes one.
    for spec in (registry.BREAKOUT_RETEST,
                 registry.LIQUIDITY_SWEEP_REVERSAL,
                 registry.COMPRESSION_RELEASE):
        cards.append({
            "key": spec.key, "name": spec.name, "status": "planned",
            "record_key": None, "setting": None,
            "one_liner": spec.one_liner, "hunts": spec.hunts,
            "triggers": spec.requires or "; ".join(spec.structure_requires),
            "confirms": ("Required factors: " + ", ".join(spec.required_factors)
                         if spec.required_factors else
                         "The versioned playbook trigger must close before entry."),
            "stop_goes": spec.invalidation_policy.replace("_", " ").title(),
            "holds_for": spec.exit_policy.replace("_", " ").title(),
            "timeframes": list(spec.timeframes), "notes": spec.gap,
        })

    out = []
    for c in cards:
        card = dict(c)
        spec = registry.BY_KEY.get(card["key"])
        if spec:
            card.update({
                "evidence_status": spec.evidence_status,
                "horizons": list(spec.horizons),
                "trigger_timeframe": spec.trigger_timeframe,
                "structure_requires": list(spec.structure_requires),
                "required_factors": list(spec.required_factors),
                "optional_factors": list(spec.optional_factors),
                "entry_policy": spec.entry_policy,
                "expiry_policy": spec.expiry_policy,
                "invalidation_policy": spec.invalidation_policy,
                "exit_policy": spec.exit_policy,
                "contraindications": list(spec.contraindications),
                "directions": list(spec.directions),
                "higher_timeframe_relationship": spec.higher_timeframe_relationship,
                "trigger_rule": spec.trigger_rule,
                "minimum_rr_after_costs": spec.minimum_rr_after_costs,
                "liquidity_rule": spec.liquidity_rule,
                "spread_rule": spec.spread_rule,
                "volatility_rule": spec.volatility_rule,
                "freshness_rule": spec.freshness_rule,
                "contract_version": spec.version,
            })
        if card["status"] == "live":
            card["enabled"] = bool(values.get(card["setting"], True))
            card["record"] = record(card["record_key"])
        else:
            card["enabled"] = None
            card["record"] = None
            if card["key"] in _PLANNED_GAP:
                card.update(gap(card["key"]))
            else:
                card.update({"gap": (spec.gap if spec else card.get("notes")),
                             "gap_pct": None, "gap_n": 0})
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
        # Resolve the ASSET, not a ticker. Reading `cycles.BTC` unconditionally
        # pointed this endpoint at BTC-USD, which stopped being imported when
        # the universe moved to perps — so the panel served a frozen series
        # while two live BTC feeds sat unused.
        sym = cycles.btc_series(con)
        if sym is None:
            return {"unavailable": True,
                    "why": "no Bitcoin series is tracked in this store",
                    "note": cycles.NOTE}
        candles = [dict(r) for r in store.get_candles(con, sym, "1D")]
        out = cycles.summarize(candles, int(_t.time()))
        # Which series answered, and how fresh it is — a cycle count read off a
        # stale feed looks identical to one read off a live feed.
        out["source_symbol"] = sym
        out["last_candle_ts"] = candles[-1]["open_ts"] if candles else None
        out["candles"] = len(candles)
        return out
    finally:
        con.close()


@app.get("/api/ticker")
def ticker():
    """Display-only live prices (Coinbase spot ticker). NEVER consumed by
    engines — analysis stays closed-candle-only (§5); this exists purely so
    the human sees the market move between candle closes."""
    con = store.connect()
    try:
        # Reference keys hold candles and therefore appear in tracked symbols,
        # but this endpoint polls the EXECUTION venues' tickers — asking
        # Coinbase for 'BICOUSDT@binance-spot' is a guaranteed 404 painted as
        # a permanently DEGRADED row, every poll, forever.
        symbols = [s for s in universe.all_tracked_symbols(con)
                   if not venues.is_reference_key(s)]
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
        symbol: str = Query("BTC-USD", pattern=SYMBOL_PATTERN),
        as_of: int | None = None):
    """Compact synchronized context strip for the decision workspace."""
    con = store.connect()
    try:
        out = []
        for tf in ("1W", "1D", "4H", "1H", "15m", "5m"):
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
            # `regime` is the engine's enum and stays the machine-readable
            # field; `label` is the SAME reading in the wording every other
            # surface prints. Market Weather and Overwatch already read that
            # noun off the server (_regime_label below), and the chart was the
            # one surface de-underscoring the enum itself — so one recording
            # appeared as "Bull weakening" on Command and "WEAKENING BULL" on
            # the chart, forty pixels from the Arm button.
            out.append({"tf": tf, "regime": reg, "label": _regime_label(reg),
                        "active_zones": sum(s != "BROKEN" for s in zone_state.values()),
                        "forming": sum(s == "FORMING" for s in setups_state.values()),
                        "ready": sum(s == "VALIDATED" for s in setups_state.values())})
        return {"symbol": symbol, "as_of": as_of, "timeframes": out}
    finally:
        con.close()


# ── Market Weather ───────────────────────────────────────────────────────────
# Regime is a chip on the chart and nothing else, so a user who has never traded
# has no way to know what it is FOR. Meanwhile the scanner produces roughly one
# setup a day and the silence reads as a fault. This endpoint exists to make the
# silence explain itself: per symbol, the recorded regime on each timeframe and
# — the whole point — what that condition means for whether anything is
# tradeable right now.
#
# Every eligibility claim below is PROBED from setups.playbook() rather than
# restated. A second copy of "a bull trend means pullback longs" would drift
# from the engine's copy the first time the playbook changed, and this strip
# would start advertising trades the scanner refuses to take.
WEATHER_TFS = ("1D", "4H")

# Display nouns only. regime.py owns the classification; this owns the wording.
REGIME_LABELS = {"BULL_TREND": "Bull trend", "BEAR_TREND": "Bear trend",
                 "WEAKENING_BULL": "Bull weakening",
                 "WEAKENING_BEAR": "Bear weakening",
                 "TRANSITION": "Transition", "RANGE": "Range"}


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _regime_label(reg: str | None) -> str:
    """The display noun for one recorded regime — the single authority for how
    a regime is WORDED on screen.

    It was inline in _tf_weather() and therefore reachable only through
    /api/weather, so /api/context (the chart's reader) had no way to get the
    noun and de-underscored the enum instead. Two registers for one field.
    Anything that prints a regime calls this."""
    if reg is None:
        return "Not mapped"
    return REGIME_LABELS.get(reg) or _cap(reg.replace("_", " ").lower())


def _side_word(direction: str | None) -> str:
    return {"LONG": "longs", "SHORT": "shorts"}.get(direction, "trades")


def _strategy_words(plays: list[dict]) -> str:
    """'pullback', or 'pullback or reversal' — names taken from the engine."""
    return " or ".join(sorted({p["strategy"].replace("_", " ").lower()
                               for p in plays}))


def _play_phrase(plays: list[dict]) -> str:
    """'pullback longs' — assembled from playbook()'s own return tuple, so a
    playbook added tomorrow describes itself here without an edit."""
    sides = sorted({_side_word(p["direction"]) for p in plays})
    return f"{_strategy_words(plays)} {' and '.join(sides)}"


def _reversal_rule_words() -> str:
    """The REVERSAL gate in words, derived from the engine's own constants.

    Restating it as prose is how the copy came to claim "needs a liquidity
    sweep" for a full session after setup-v0.7 replaced that rule with 2-of-4
    evidence. A user reading the old sentence would have been told a trade was
    impossible when it was merely conditional.
    """
    names = {"CHOCH": "a structural break", "SWEEP": "a liquidity sweep",
             "VOLUME": "heavy volume", "STRENGTH": "a strong zone"}
    parts = [names.get(c, c.lower()) for c in
             getattr(setups, "REVERSAL_COMPONENTS",
                     ("CHOCH", "SWEEP", "VOLUME", "STRENGTH"))]
    n = getattr(setups, "REVERSAL_MIN_EVIDENCE", 2)
    return f"at least {n} of: {', '.join(parts)}"


def _regime_plays(reg: str | None, enabled: set | None) -> list[dict]:
    """What setups.playbook() would trade in this regime. Probed, not restated."""
    import inspect
    # setups.py is mid-version and gained an `enabled` parameter with S-series
    # strategy switches. Testing for the capability rather than a version string
    # keeps this endpoint working across the change, the same way _entry_rules
    # does for the confirmation model.
    params = inspect.signature(setups.playbook).parameters
    takes_enabled = "enabled" in params
    # setup-v0.7 replaced the sweep-only REVERSAL gate with "2 of {CHOCH, SWEEP,
    # VOLUME, STRENGTH}", because sweep-alone produced 5 setups in four years.
    # Probing with a lone sweep would now report TRANSITION as untradeable —
    # which is wrong, and would tell the operator no playbook exists when one
    # does. The second probe therefore supplies a SUFFICIENT evidence set rather
    # than a single component. Still probed from the engine, never restated.
    takes_evidence = "rev_evidence" in params
    sufficient = (["CHOCH", "VOLUME"] if takes_evidence else None)

    def _probe(zone_type, conditional):
        if takes_evidence:
            ev = sufficient if conditional else []
            return setups.playbook(zone_type, reg, conditional, enabled, ev)
        if takes_enabled:
            return setups.playbook(zone_type, reg, conditional, enabled)
        return setups.playbook(zone_type, reg, conditional)

    found: dict[tuple, dict] = {}
    for zone_type in ("DEMAND", "SUPPLY"):
        # unconditional first: a play that survives with NO extra evidence is
        # always live, and the conditional pass must never downgrade it back.
        for swept in (False, True):
            play = _probe(zone_type, swept)
            if play is None:
                continue
            strategy, direction, _base_rank = play
            cur = found.get((strategy, direction))
            if cur is None:
                found[(strategy, direction)] = {
                    "strategy": strategy, "direction": direction,
                    "zone_type": zone_type, "requires_sweep": swept}
            elif not swept:
                cur["requires_sweep"] = False
    return sorted(found.values(),
                  key=lambda p: (p["requires_sweep"], p["strategy"],
                                 p["direction"]))


def _tf_weather(tf: str, reg: str | None, enabled: set | None) -> dict:
    """One timeframe's cell: the regime, and whether it can be traded."""
    plays = _regime_plays(reg, enabled)
    # The same probe ignoring the operator's switches. The difference between
    # the two is the honest distinction between "we never built a play for this"
    # and "you turned that play off" — two very different reasons for silence.
    switched_off = sorted({p["strategy"] for p in _regime_plays(reg, None)}
                          - {p["strategy"] for p in plays})
    live = [p for p in plays if not p["requires_sweep"]]
    gated = [p for p in plays if p["requires_sweep"]]
    label = _regime_label(reg)
    dirs = {p["direction"] for p in live}

    because = detail = None
    if not live:
        if reg is None:
            because = "the scanner has not classified this timeframe yet"
            detail = (f"No regime fact exists for {tf}. That is missing data, "
                      f"not a calm market.")
        elif switched_off and not plays:
            names = " and ".join(s.replace("_", " ").lower()
                                 for s in switched_off)
            because = f"{names} is switched off"
            detail = (f"A {label.lower()} is tradeable, but {names} is turned "
                      f"off in Scanner Setup, so nothing here is eligible.")
        elif not plays:
            because = f"no playbook covers a {label.lower()} yet"
            detail = (f"A {label.lower()} produces no candidates at all — no "
                      f"live playbook takes one. The playbook catalogue lists "
                      f"what is planned for it.")
        else:
            because = (f"a {_strategy_words(gated)} here needs supporting "
                       f"evidence first")
            detail = (f"The only play in a {label.lower()} is a "
                      f"{_strategy_words(gated)}, and it counts only with "
                      f"{_reversal_rule_words()}. A transition on its own is "
                      f"not a trade.")
    return {"tf": tf, "regime": reg, "label": label, "plays": plays,
            "live": bool(live), "requires_sweep": bool(gated) and not live,
            "bias": (dirs.pop() if len(dirs) == 1 else "BOTH") if dirs else None,
            "phrase": _play_phrase(live) if live else None,
            "switched_off": switched_off,
            "blocked_because": because, "blocked_detail": detail}


def _weather_tier(tfs: list[dict], state: str) -> int:
    """Rank of usefulness, 0 best. Drives both the sort and the row styling, so
    the UI never has to re-derive 'is this one worth looking at'."""
    if (state and state != "ADMITTED") or any(t["regime"] is None for t in tfs):
        return 4                                  # no data — not a calm market
    live = [t for t in tfs if t["live"]]
    if len(live) == len(tfs) and len({t["bias"] for t in live}) == 1:
        return 0                                  # every timeframe wants the same side
    if live:
        return 1                                  # tradeable somewhere
    if any(t["requires_sweep"] for t in tfs):
        return 2                                  # conditional on a sweep that rarely comes
    return 3                                      # no playbook at all


def _weather_meaning(tfs: list[dict], state: str) -> tuple[str, str]:
    """The right-hand column: what this condition means, in one sentence."""
    if state and state != "ADMITTED":
        return ("Not scanned yet — still warming up",
                "The symbol is in the universe but has too little daily history "
                "to map structure, so no playbook runs on it yet.")
    # Loud fallback: an unmapped timeframe is missing data. Rendering it as a
    # quiet market would be the confident-looking zero this house forbids.
    unmapped = [t["tf"] for t in tfs if t["regime"] is None]
    if unmapped:
        return ("No regime recorded on " + " and ".join(unmapped),
                "The scanner has not classified this symbol there yet. Missing "
                "data, not a quiet market.")

    live = [t for t in tfs if t["live"]]
    blocked = [t for t in tfs if not t["live"]]
    if not live:
        reasons = {t["blocked_because"] for t in blocked}
        details = list(dict.fromkeys(t["blocked_detail"] for t in blocked))
        if len(reasons) == 1:
            return _cap(reasons.pop()), " ".join(details)
        return ("Nothing to trade — " +
                ", ".join(f"{t['tf']} {t['label'].lower()}" for t in tfs),
                " ".join(details))

    if len(live) == len(tfs):
        if len({t["bias"] for t in live}) == 1:
            return (_cap(live[0]["phrase"]) + " are live",
                    "Both timeframes want the same side, so a setup on the "
                    "lower one also earns the higher-timeframe agreement it is "
                    "scored on. The scanner is waiting for price to return to a "
                    "zone and close back out of it.")
        return ("Timeframes disagree — " +
                ", ".join(f"{t['tf']} wants {_side_word(t['bias'])}" for t in tfs),
                "Either can still produce a setup — the engine trades each "
                "timeframe on its own — but the lower one is ranked down, "
                "because the timeframe above it disagrees.")

    on = live[0]
    return (_cap(on["phrase"]) + f" live on {on['tf']} only",
            " ".join(f"{t['tf']}: {t['blocked_detail']}" for t in blocked))


@app.get("/api/weather")
def weather():
    """Market Weather — regime per timeframe, and what it means for trading.

    One batched query for the whole universe. Per-symbol /api/context calls
    would be 40 round trips against a 1GB store every refresh, for a strip that
    sits above the fold.
    """
    import time as _t
    con = store.connect()
    try:
        enabled = (setups.enabled_strategies(con)
                   if hasattr(setups, "enabled_strategies") else None)
        urow = con.execute(
            "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
            "ORDER BY id DESC LIMIT 1", (universe.UNIVERSE_VERSION,)).fetchone()
        if urow:
            members = [{"symbol": m["symbol"], "rank": m.get("rank"),
                        "state": m.get("state", "ADMITTED")}
                       for m in json.loads(urow[0])["members"]]
        else:
            # No ranking snapshot yet. Everything with candles is a truer answer
            # than an empty strip, and the missing ranks say so by being null.
            # Minus reference keys: labelling an unsizeable '@'-series
            # "ADMITTED" on the weather strip is the same cold-store leak
            # universe.current_symbols filters, display-side.
            members = [{"symbol": s, "rank": None, "state": "ADMITTED"}
                       for s in universe.all_tracked_symbols(con)
                       if not venues.is_reference_key(s)]

        latest: dict[tuple, str] = {}
        syms = [m["symbol"] for m in members]
        if syms:
            rows = con.execute(
                "SELECT symbol, tf, payload FROM facts WHERE kind='regime' "
                "AND algo_version=? AND symbol IN (%s) AND tf IN (%s) "
                "ORDER BY confirmed_at, id"
                % (",".join("?" * len(syms)), ",".join("?" * len(WEATHER_TFS))),
                (regime.REGIME_VERSION, *syms, *WEATHER_TFS)).fetchall()
            for sym, tf, payload in rows:
                latest[(sym, tf)] = payload      # ordered scan: last one wins
    finally:
        con.close()

    out = []
    for m in members:
        tfs = []
        for tf in WEATHER_TFS:
            raw = latest.get((m["symbol"], tf))
            tfs.append(_tf_weather(
                tf, json.loads(raw)["regime"] if raw else None, enabled))
        by_tf = {t["tf"]: t for t in tfs}
        for t in tfs:
            # setups.py scores a setup up when the timeframe above it agrees.
            # "Agrees" there means the parent regime offers a play in the same
            # direction — which is exactly what `bias` already is, so this reads
            # the factor off the same probe instead of copying its condition.
            parent = by_tf.get(getattr(setups, "HTF_LADDER", {}).get(t["tf"]))
            t["htf"] = parent["tf"] if parent else None
            t["htf_agrees"] = (None if parent is None or t["bias"] is None
                               or parent["bias"] is None
                               else parent["bias"] == t["bias"])
        meaning, why = _weather_meaning(tfs, m["state"])
        out.append({"symbol": m["symbol"], "rank": m["rank"],
                    "state": m["state"], "timeframes": tfs,
                    "live": any(t["live"] for t in tfs),
                    "tier": _weather_tier(tfs, m["state"]),
                    "meaning": meaning, "why": why})

    # Opportunity first: the strip should surface what can be traded, not read
    # top to bottom as a liquidity ranking.
    out.sort(key=lambda s: (s["tier"],
                            9999 if s["rank"] is None else s["rank"], s["symbol"]))
    # THE DENOMINATOR THIS PANEL IS ABOUT.
    #
    # `n_live`/`n_total` counted every member of the ranking snapshot, which
    # includes SHADOW and WARMING. Measured 2026-07-31, the strip therefore
    # reported "20 of 29 tradeable" while only ELEVEN of those twenty could be
    # sized: the other nine were shadow symbols, which the risk authority never
    # sizes by definition. Command read `universe_counts.admitted` and showed 19
    # on the same screen, so the two panels disagreed about the size of the
    # universe AND about what "tradeable" means.
    #
    # A panel whose stated job is "whether anything can be traded" must not
    # count things that cannot be. `n_live`/`n_total` are now scoped to
    # ADMITTED — the same population Command counts — and the shadow and warming
    # figures are reported separately so nothing is hidden, just no longer
    # folded into a headline that reads as opportunity.
    sizeable = [s for s in out if s["state"] == "ADMITTED"]
    return {"generated_at": int(_t.time()), "timeframes": list(WEATHER_TFS),
            "symbols": out,
            "n_live": sum(1 for s in sizeable if s["live"]),
            "n_total": len(sizeable),
            "n_shadow": sum(1 for s in out if s["state"] == "SHADOW"),
            "n_warming": sum(1 for s in out if s["state"] == "WARMING"),
            "n_shadow_live": sum(1 for s in out
                                 if s["state"] == "SHADOW" and s["live"]),
            # EVERY ROW LANDS IN EXACTLY ONE BUCKET, and this is the one that
            # makes that true. The three above name ADMITTED, SHADOW and
            # WARMING; the universe also holds REJECTED, and a symbol in it
            # appeared in no count the panel reported. Measured 2026-08-06:
            # 18 + 12 + 1 = 31 against 32 rows, with u1000SHIBUSDT
            # (below_liquidity_floor) explained by nothing.
            #
            # Counted as the REMAINDER rather than by naming REJECTED, so a
            # state added to the universe later cannot fall through this the
            # way REJECTED did — a new word costs the reader precision here,
            # never a silent disappearance. test_weather.py asserts the four
            # sum to n_rows.
            "n_other": sum(1 for s in out if s["state"]
                           not in ("ADMITTED", "SHADOW", "WARMING")),
            "n_rows": len(out),
            "enabled_strategies": sorted(enabled) if enabled else None,
            "regime_version": regime.REGIME_VERSION,
            "strategy_version": setups.SETUP_VERSION}


@app.get("/api/overview")
def overview():
    """One call for the cockpit rails: watchlist, setup feed, engine health."""
    from engine import venues
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
            # A symbol with candles but NO universe row is not admitted — it is
            # a symbol we still hold history for. Defaulting it to "ADMITTED"
            # inflated the headline count from 19 to 76, and the UI then
            # filtered that list itself and rendered 75, while Market Weather
            # 200px below reported 34 from the universe fact. Three
            # irreconcilable universe sizes on one screen, all describing the
            # same store.
            # Venue is served, never re-derived in the browser. `venues.py` is
            # the only thing allowed to map a symbol to what a market ALLOWS,
            # and a JS copy of that rule would be a second authority for
            # whether shorting is permitted and what leverage is available.
            # It also answers the operator's question directly: BTC-USD and
            # BTCUSDT are one coin on two exchanges at two prices, and the
            # picker never said which one you were about to arm on.
            try:
                v = venues.venue_for(sym)
                vinfo = {"key": v.key, "kind": v.kind,
                         "max_leverage": float(v.max_leverage),
                         "allow_shorts": v.allow_shorts}
            except ValueError:
                vinfo = None          # unknown instrument; say nothing rather than guess
            symbols.append({"symbol": sym, "price": price, "change_pct": chg,
                            "regime": reg, "state": m.get("state", "UNTRACKED"),
                            "rank": m.get("rank"), "vol_usd": m.get("vol_usd"),
                            "venue": vinfo})
        # rank order: by universe rank, unranked last
        symbols.sort(key=lambda s: (s["rank"] is None, s["rank"] or 0))

        # The engine owns this number. The UI was re-deriving it with its own
        # filter — the same "one authority per number" breach as ticket-math.js,
        # and it disagreed for the same reason: a filter is not a definition.
        universe_counts = {
            "admitted": sum(1 for s in symbols if s["state"] == "ADMITTED"),
            "shadow": sum(1 for s in symbols if s["state"] == "SHADOW"),
            "warming": sum(1 for s in symbols if s["state"] == "WARMING"),
            "untracked_with_candles": sum(1 for s in symbols
                                          if s["state"] == "UNTRACKED"),
        }

        # BULK, not per-symbol. This built the feed with a query per
        # (symbol x timeframe x fact kind) — ~1,520 round trips once the
        # universe reached 76 symbols, and `/api/overview` took **36.7s** on the
        # live store while returning in 0.6s against a warm cache in-process.
        # It is the Command surface, so that is the whole app feeling broken.
        #
        # Three queries now, filtered by version in SQL and grouped in Python.
        # The output is byte-identical; only the number of round trips changed.
        feed = []
        last_state: dict = {}
        # Setups still on approach. `eligible` is VALIDATED-only by definition,
        # so a setup whose latest state is FORMING never reached the feed at
        # all — the engine's own "price is closing on a zone" signal went to
        # desktop notifications and nowhere in the cockpit. Same last-write-
        # wins walk, second dict; a FORMING fact that later upgraded or was
        # cancelled is overwritten here and never shown.
        forming_last: dict = {}
        for sym, tf, mt, cat, raw in con.execute(
                "SELECT symbol, tf, market_time, confirmed_at, payload FROM facts "
                "WHERE kind='setup' AND algo_version IN (?,?) "
                "AND confirmed_at>=? ORDER BY confirmed_at, id",
                (setups.SETUP_VERSION, scalein.SCALE_VERSION,
                 baseline["started_at"])).fetchall():
            p = json.loads(raw)
            if p.get("setup_id") not in eligible:
                forming_last[p.get("setup_id")] = {"symbol": sym, "tf": tf,
                                                   "market_time": mt,
                                                   "confirmed_at": cat, **p}
                continue
            # later rows win, matching the previous loop's last-write-wins
            last_state[p["setup_id"]] = {"symbol": sym, "tf": tf,
                                         "market_time": mt, **p}
        now_ts = int(time.time())
        approaching = sorted(
            (st for st in forming_last.values()
             if st.get("state") == "FORMING"
             and int(st.get("expires_at_ts") or 0) > now_ts),
            key=lambda s: float(s.get("distance_atr") or 9e9))[:8]
        # `distance_atr` is measured ONCE, at the bar that armed the setup
        # (setups.py breaks after the first qualifying bar, so there is exactly
        # one FORMING fact per setup_id) and is never refreshed. The UI must be
        # able to date it rather than assert a days-old figure in the present
        # tense, so carry the measurement time and the engine's own proximity
        # bound instead of leaving the client to hard-code either.
        for st in approaching:
            st["measured_at"] = st.get("confirmed_at") or st.get("market_time")
        prox_atr = float(setups.PROX_ATR)
        outs: dict = {}
        for (raw,) in con.execute(
                "SELECT payload FROM facts WHERE kind='exec' AND algo_version=? "
                "ORDER BY confirmed_at, id", (execsim.EXEC_VERSION,)).fetchall():
            p = json.loads(raw)
            if p.get("setup_id") in eligible:
                outs[p["setup_id"]] = {"outcome": p["outcome"],
                                       "r_multiple": p["r_multiple"]}
        for st in last_state.values():
            st["result"] = outs.get(st["setup_id"])
            feed.append(st)
        feed.sort(key=lambda s: -s["market_time"])

        # attach the risk authority's sizing decision to each feed item
        risk_by_setup = {}
        for (raw,) in con.execute(
                "SELECT payload FROM facts WHERE kind='risk' AND algo_version=? "
                "ORDER BY confirmed_at, id", (risk.RISK_VERSION,)).fetchall():
            p = json.loads(raw)
            if p.get("event") == "DECISION" and p.get("setup_id") in eligible:
                risk_by_setup[p["setup_id"]] = {
                    "decision": p["decision"], "risk_usd": p.get("risk_usd"),
                    "units": p.get("units"), "leverage": p.get("implied_leverage"),
                    "reasons": p.get("reasons")}
        for s in feed:
            s["risk"] = risk_by_setup.get(s["setup_id"])

        # 22 rows, read out of 3,038,265. `GROUP BY engine` over an unindexed
        # append-only table scanned all of it — **2,432 ms of this endpoint's
        # 2,900 ms**, every 30 seconds, and ~300 MB of page cache with it.
        #
        # The rewrite is two index moves. `names` is the loose-index-scan
        # idiom: MIN(engine), then repeatedly the next engine greater than the
        # last, so the 22 distinct values cost 22 seeks instead of a scan of
        # three million (SELECT DISTINCT still scans — measured 177 ms).
        # Each name then seeks its own newest row.
        #
        # `ORDER BY run_at DESC, x.id` is NOT a new tie-break — it is the one
        # the old query already had. SQLite's bare-column rule takes
        # `duration_ms` from the first row reaching MAX(run_at) in scan order,
        # and a scan reads in rowid order. Ties are the norm here, not the
        # exception: 16 of the 22 engines finish their last run in the same
        # second as their siblings and disagree on duration_ms, so leaving it
        # implicit would have made the answer depend on which access path the
        # planner chose. Stated, it is the same row every time — verified
        # equal to the old query's output, row for row, on the live store.
        engines = con.execute("""
            WITH RECURSIVE names(engine) AS (
                SELECT MIN(engine) FROM engine_runs
                UNION ALL
                SELECT (SELECT MIN(engine) FROM engine_runs
                         WHERE engine > names.engine)
                  FROM names WHERE names.engine IS NOT NULL)
            SELECT r.engine, r.run_at, r.duration_ms
              FROM names JOIN engine_runs r ON r.id = (
                   SELECT x.id FROM engine_runs x WHERE x.engine = names.engine
                    ORDER BY x.run_at DESC, x.id LIMIT 1)
             WHERE names.engine IS NOT NULL
             ORDER BY r.engine""").fetchall()

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
                "approaching": approaching,
                "prox_atr": prox_atr,
                "universe_counts": universe_counts,
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
    # PAPER basis: the manual order ticket arms the operator's paper book,
    # so its sizing constants are that book's. (The dispatch mode's R never
    # applies here — manual arms do not cross to a real venue.)
    g = risk.gates_for_mode(risk.AutomationMode.PAPER)
    return {
        "risk_pct": float(g["risk_pct"]),
        "max_total_risk_pct": float(g["max_total_open_risk_pct"]),
        "max_concurrent": g["max_concurrent"],
        "max_leverage": float(v.max_leverage),
        "daily_loss_pct": float(g["daily_loss_limit_pct"]),
        "venue": {"key": v.key, "kind": v.kind, "quote": v.quote,
                  "allow_shorts": v.allow_shorts,
                  "funding_per_day": v.funding_settlements_per_day,
                  # The ticket draws a liquidation line from the SAME formula
                  # `venues.liquidation_price` uses, so both inputs to it are
                  # served rather than hard-coded on the other side of the wire.
                  # A JS copy of either would be a second authority for the
                  # price at which a position dies.
                  "margin_mode": v.margin_mode,
                  "position_mode": "ONE_WAY",
                  "maintenance_margin": float(venues.MAINTENANCE_MARGIN)},
        "venues": [{"key": x.key, "kind": x.kind, "allow_shorts": x.allow_shorts,
                    "max_leverage": float(x.max_leverage)} for x in venues.ALL],
        "cost": {"version": v.cost_profile, "venue": v.key,
                 "maker_rate": float(v.maker_rate),
                 "taker_rate": float(v.taker_rate),
                 "slippage_atr": float(v.slippage_atr),
                 # FUNDING, which the simulator has always charged and no
                 # surface ever showed. A perp held over a weekend pays every
                 # settlement, and on a tight target that can exceed the edge
                 # — so the cost of HOLDING belongs on screen before the trade
                 # is taken, not only in the settled result (UX audit,
                 # 4 Aug 2026). Modelled, not polled: this is the same
                 # constant `costs.round_trip_cost` charges, and the ticket
                 # says so rather than implying a live venue quote.
                 "funding_rate": float(costs.DEFAULT_FUNDING_RATE),
                 "funding_per_day": v.funding_settlements_per_day},
        # Live order submission is locked until the forward record earns it.
        # The UI reads this rather than deciding for itself.
        "live_enabled": False,
        # WHAT "earned" MEANS. This sentence used to be the whole answer, and
        # nothing in the system defined the condition it named — see
        # engine/livegate.py. The criteria are measurable and live at
        # /api/live-gate; the reason now points at them instead of gesturing.
        # The four criteria MOVED to Results -> Progression; Settings keeps the
        # lock and its consequence. This sentence is printed on the arming
        # ticket — the surface where money is committed — so a pointer at the
        # wrong panel is worse here than anywhere else in the app.
        "live_locked_reason": "Forward paper evidence has not yet earned live "
                              "execution — see Results for the four criteria "
                              "and where the record stands against them.",
    }


@app.get("/api/live-gate")
def live_gate():
    """The four criteria that stand between the paper book and real money.

    Read-only, and deliberately assembled from authorities that already exist:
    the forward journal and drawdown come from `/api/portfolio` (§8: never
    re-derive equity), the confidence interval from `edgestats`' own bootstrap,
    the audit status from the last `quality_runs` row. Nothing here computes a
    second opinion about a number another surface is already showing.
    """
    from engine import livegate
    con = store.connect()
    try:
        pf = portfolio()
        return _live_gate_from(con, pf)
    finally:
        con.close()


def _live_gate_from(con, pf: dict) -> dict:
    """Evaluate the gate from an already-authoritative portfolio payload."""
    from engine import livegate
    q = con.execute("SELECT status FROM quality_runs "
                    "ORDER BY observed_at DESC LIMIT 1").fetchone()
    return livegate.evaluate(
        con, journal=pf.get("journal") or [],
        max_drawdown_pct=pf.get("max_drawdown_pct") or 0.0,
        quality_status=q[0] if q else None,
        baseline=pf.get("baseline"), strategy_version=setups.SETUP_VERSION)


def _automation_read(con, gate: dict | None = None) -> tuple[dict, dict]:
    """One server-owned automation answer for every cockpit surface."""
    operational = automation.operational_evidence(con)
    result = automation.status(con, live_gate=gate or live_gate(),
                               operational=operational)
    return contracts.to_wire(result), operational


@app.get("/api/automation/status")
def automation_status():
    """Current mode, locks and promotion evidence.  This endpoint never arms."""
    con = store.connect()
    try:
        status_row, operational = _automation_read(con)
        return {**status_row, "operational": operational,
                "evidence_scope": {
                    "population": "PROMOTION_EVENTS_BY_STAGE",
                    "window": "CUMULATIVE_CURRENT_AUTOMATION_VERSION",
                    "version": automation.AUTOMATION_VERSION},
                "history": automation.history(con, 20)}
    finally:
        con.close()


@app.post("/api/automation/mode")
def automation_mode(payload: dict):
    """Revision-checked mode transition with explicit high-risk acknowledgement."""
    if "expected_revision" not in payload:
        raise HTTPException(400, "expected_revision is required")
    note = str(payload.get("note") or "")[:500]
    acknowledgement = str(payload.get("acknowledgement") or "")
    con = store.connect()
    try:
        gate = live_gate()
        operational = automation.operational_evidence(con)
        try:
            result = automation.transition(
                con, str(payload.get("mode") or ""),
                expected_revision=int(payload["expected_revision"]),
                acknowledgement=acknowledgement, note=note,
                live_gate=gate, operational=operational)
        except automation.ModeConflict as exc:
            raise HTTPException(409, str(exc))
        except (automation.ModeRejected, TypeError, ValueError) as exc:
            raise HTTPException(423, str(exc))
        return {**contracts.to_wire(result), "operational": operational}
    finally:
        con.close()


@app.get("/api/automation/drills")
def automation_drills():
    con = store.connect()
    try:
        return {"items": automation.safety_drills(con),
                "required": sorted(automation.REQUIRED_SAFETY_DRILLS),
                "authority": automation.AUTOMATION_VERSION}
    finally:
        con.close()


@app.post("/api/automation/drills")
def automation_drill_start(payload: dict):
    """Stage one TESTNET drill; the endpoint never performs the fault."""
    con = store.connect()
    try:
        try:
            return automation.start_safety_drill(
                con, str(payload.get("drill") or ""),
                acknowledgement=str(payload.get("acknowledgement") or ""))
        except automation.ModeConflict as exc:
            raise HTTPException(409, str(exc))
        except automation.ModeRejected as exc:
            raise HTTPException(423, str(exc))
    finally:
        con.close()


@app.get("/api/positions/managed")
def managed_positions(include_closed: bool = Query(False)):
    """Custody state used by the Trade workspace and reconciliation UI."""
    con = store.connect()
    try:
        return {"items": positions.managed(con, include_closed=include_closed),
                "authority": positions.POSITION_VERSION}
    finally:
        con.close()


@app.get("/api/positions/paper")
def simulated_positions(include_closed: bool = Query(False)):
    """Deterministic closed-candle PAPER fills and exits."""
    con = store.connect()
    try:
        return {"items": execution.paper_positions(
                    con, include_closed=include_closed),
                "authority": execution.EXECUTION_CORE_VERSION}
    finally:
        con.close()


@app.post("/api/positions/{position_id}/manual-override")
def position_manual_override(position_id: str, payload: dict):
    if payload.get("acknowledgement") != (
            "I UNDERSTAND BOT DISCRETIONARY MANAGEMENT WILL STOP"):
        raise HTTPException(400, "exact manual-override acknowledgement required")
    con = store.connect()
    try:
        try:
            return positions.manual_override(con, position_id)
        except (ValueError, positions.ProtectionFailed) as exc:
            raise HTTPException(409, str(exc))
    finally:
        con.close()


@app.post("/api/positions/{position_id}/return-control")
def position_return_control(position_id: str, payload: dict):
    if payload.get("acknowledgement") != "RETURN CONTROL TO BOT":
        raise HTTPException(400, "exact return-control acknowledgement required")
    con = store.connect()
    try:
        try:
            row = con.execute(
                "SELECT o.mode FROM managed_positions p JOIN execution_outbox o "
                "ON o.intent_id=p.intent_id WHERE p.position_id=?",
                (position_id,)).fetchone()
            if not row or row[0] not in ("TESTNET", "LIVE"):
                raise ValueError("managed private execution environment not found")
            broker = broker_factory.phemex_for_mode(automation.AutomationMode(row[0]))
            return positions.return_control(con, position_id, broker)
        except (ValueError, positions.ProtectionFailed,
                broker_factory.BrokerConfigurationError) as exc:
            raise HTTPException(409, str(exc))
    finally:
        con.close()


@app.get("/api/opportunities")
def opportunity_list(
        state: str | None = Query(None),
        horizon: str | None = Query(None),
        include_history: bool = Query(True),
        limit: int = Query(200, ge=1, le=500)):
    """Ranked, server-owned setup read model; legacy volume rank is ignored."""
    con = store.connect()
    try:
        rows = opportunities.list_candidates(con, include_history=include_history)
        if state:
            wanted = {s.strip().upper() for s in state.split(",") if s.strip()}
            rows = [row for row in rows if row["state"] in wanted]
        if horizon:
            wanted_h = {h.strip().lower() for h in horizon.split(",") if h.strip()}
            rows = [row for row in rows
                    if str(row["setup"].get("horizon") or "").lower() in wanted_h]
        rows = rows[:limit]
        return {"generated_at": int(time.time()),
                "summary": opportunities.summary(rows), "items": rows,
                "authority": opportunities.OPPORTUNITY_VERSION}
    finally:
        con.close()


@app.get("/api/market-context/{symbol}")
def market_context_snapshot(symbol: str, tf: str = Query("15m")):
    """Canonical closed-candle phase: trend/range/compression/release/unstable."""
    con = store.connect()
    try:
        try:
            return market_context.snapshot(con, symbol, tf)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    finally:
        con.close()


@app.get("/api/opportunities/{setup_id}")
def opportunity_detail(setup_id: str):
    """The same record used by card, chart, ticket and later attribution."""
    con = store.connect()
    try:
        for row in opportunities.list_candidates(con, include_history=True):
            if row["setup"]["setup_id"] == setup_id:
                return row
        raise HTTPException(404, "opportunity not found in the current baseline")
    finally:
        con.close()


@app.get("/api/operations")
def operations_read_model():
    """Compact command-layer state shared by every cockpit destination."""
    pf = portfolio()
    con = store.connect()
    try:
        gate = _live_gate_from(con, pf)
        mode, operational = _automation_read(con, gate)
        rows = opportunities.list_candidates(con, include_history=False)
        opp_summary = opportunities.summary(rows)

        quality_row = con.execute(
            "SELECT status,observed_at FROM quality_runs "
            "ORDER BY observed_at DESC LIMIT 1").fetchone()
        quality_status = quality_row[0] if quality_row else "UNKNOWN"
        universe_row = con.execute(
            "SELECT payload FROM facts WHERE kind='universe' "
            "AND algo_version=? ORDER BY id DESC LIMIT 1",
            (universe.UNIVERSE_VERSION,)).fetchone()
        members = json.loads(universe_row[0]).get("members", []) if universe_row else []
        eligible_markets = sum(1 for member in members
                               if member.get("state") == "ADMITTED")

        try:
            hb = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
            scanner_age = max(0, int(time.time() - float(hb["ts"])))
            scanner = {"state": "SCANNING" if scanner_age < SCANNER_STALE_S
                       else "STALE", "age_s": scanner_age,
                       "stage": hb.get("phase")}
        except (OSError, ValueError, KeyError, TypeError):
            scanner = {"state": "OFFLINE", "age_s": None, "stage": None}

        equity = Decimal(str(pf.get("equity") or risk.START_EQUITY))
        open_risk = Decimal(str(pf.get("open_risk_usd") or 0))
        # PAPER gates, because every dollar below is a paper-book dollar —
        # equity, open_risk and the journal all come from the research book,
        # and one basis per calculation is the rule. The dispatch mode's R is
        # reported as its own labelled field, never subtracted from paper's.
        _gates = risk.gates_for_mode(risk.AutomationMode.PAPER)
        _dispatch_pct = risk.MODE_RISK_PCT[automation.current(con)[0]]
        total_budget = (equity * _gates["max_total_open_risk_pct"])
        utc_day_start = int(time.time()) // 86_400 * 86_400
        today_pnl = sum((Decimal(str(row.get("pnl_usd") or 0))
                         for row in pf.get("journal", [])
                         if int(row.get("ts") or 0) >= utc_day_start), Decimal(0))
        day_open_equity = equity - today_pnl
        daily_budget = day_open_equity * _gates["daily_loss_limit_pct"]
        daily_remaining = max(Decimal(0), daily_budget + min(Decimal(0), today_pnl))
        return {
            "generated_at": int(time.time()), "venue": "PHEMEX_USDT_PERPETUAL",
            "automation": mode,
            "account": {
                "equity": str(equity.quantize(Decimal("0.01"))),
                "risk_per_trade_pct": str(_gates["risk_pct"] * 100),
                "next_risk_usd": str((equity * _gates["risk_pct"]).quantize(Decimal("0.01"))),
                "dispatch_risk_pct": str(_dispatch_pct * 100),
                "open_risk_usd": str(open_risk.quantize(Decimal("0.01"))),
                "total_risk_remaining_usd": str(max(Decimal(0), total_budget - open_risk)
                                                .quantize(Decimal("0.01"))),
                "daily_loss_remaining_usd": str(daily_remaining.quantize(Decimal("0.01"))),
                "open_positions": len(pf.get("active_positions") or []),
                "working_orders": len(pf.get("pending_orders") or []),
            },
            "scanner": {**scanner, "eligible_markets": eligible_markets},
            "data": {"status": quality_status,
                     "observed_at": quality_row[1] if quality_row else None},
            "opportunities": opp_summary,
            "promotion": gate,
            "operational_evidence": operational,
        }
    finally:
        con.close()


@app.get("/api/achievements")
def achievement_progress():
    """Progression that rewards evidence, documentation and safety drills only."""
    pf = portfolio()
    con = store.connect()
    try:
        gate = _live_gate_from(con, pf)
        mode, _ = _automation_read(con, gate)
        q = con.execute("SELECT status FROM quality_runs "
                        "ORDER BY observed_at DESC LIMIT 1").fetchone()
        items = achievements.calculate(
            live_gate=gate, automation_status=mode,
            journal_count=int(pf.get("journal_total") or 0),
            quality_status=q[0] if q else None)
        return {"items": items, "version": achievements.ACHIEVEMENT_VERSION,
                "policy": "Discipline only; profit, leverage and frequency earn nothing."}
    finally:
        con.close()


@app.get("/api/learning/registry")
def learning_registry():
    """Champion/challenger state; it has no authority over risk or live mode."""
    con = store.connect()
    try:
        return learning.registry(con)
    finally:
        con.close()


@app.get("/api/factor-evidence")
def factor_evidence():
    """Point-in-time, chronological factor uplift; never a trade permission."""
    con = store.connect()
    try:
        candidates, warnings = factorstats_engine.load_candidates(con)
        report = factorstats_engine.evidence_report(candidates)
        report["population"] = "POINT_IN_TIME_CLOSED_TRADES"
        report["window"] = "CUMULATIVE_CURRENT_FACTORSTATS_VERSION"
        report["warnings"] = warnings + report.get("warnings", [])
        return report
    finally:
        con.close()


@app.get("/api/factor-grade")
def factor_grade():
    """Explanation-only calibration over the current factor evidence."""
    con = store.connect()
    try:
        candidates, warnings = factorstats_engine.load_candidates(con)
        evidence = factorstats_engine.evidence_report(candidates)
        grade = factorgrade_engine.calibrated_grade(evidence)
        grade["population"] = "VALIDATED_FACTOR_COHORTS"
        grade["window"] = "CUMULATIVE_CURRENT_FACTORGRADE_VERSION"
        grade["warnings"] = warnings + grade.get("warnings", [])
        grade["permission"] = "RANK_AND_EXPLAIN_ONLY"
        return grade
    finally:
        con.close()


@app.post("/api/learning/propose")
def learning_propose(payload: dict):
    con = store.connect()
    try:
        try:
            return learning.propose(
                con, proposal_id=str(payload.get("proposal_id") or ""),
                model_id=str(payload.get("model_id") or ""),
                target_stage=str(payload.get("target_stage") or ""),
                expected_algorithm_version=str(
                    payload.get("expected_algorithm_version") or ""),
                note=str(payload.get("note") or ""))
        except learning.LearningRejected as exc:
            raise HTTPException(400, str(exc))
    finally:
        con.close()


@app.post("/api/learning/approve")
def learning_approve(payload: dict):
    """Explicit human promotion; never toggles a strategy or execution mode."""
    if payload.get("acknowledgement") != "I APPROVE MODEL PROMOTION":
        raise HTTPException(400, "exact model-promotion acknowledgement required")
    con = store.connect()
    try:
        try:
            return learning.approve(
                con, str(payload.get("proposal_id") or ""),
                human_approver=str(payload.get("human_approver") or ""),
                new_algorithm_version=str(payload.get("new_algorithm_version") or ""))
        except learning.LearningRejected as exc:
            raise HTTPException(400, str(exc))
    finally:
        con.close()


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


@app.post("/api/manual/arm")
def manual_arm(payload: dict):
    """Arm one operator plan as a PAPER trade.

    This endpoint remains PAPER-only, and it records the same canonical
    execution plan as autonomous routing. The intent is also recorded under
    the manual book's own version, a
    tag no strategy consumer queries, so it cannot reach the record that
    `edgestats`/`factorstats` grade. See `engine/manual.py` for why that
    separation is structural rather than a filter someone has to remember.

    `partials` is the scale-out ladder and is passed through unexamined: the
    geometry rules live in `manual.validate_partials`, which is where the stop
    and target it has to sit between are already known. Re-checking it here
    would be a second authority on the same rule.
    """
    import time
    from engine import manual
    symbol = str(payload.get("symbol") or "")
    tf = str(payload.get("tf") or "")
    if not symbol:
        raise HTTPException(400, "symbol required")
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    # THE CALLER MAY NAME THE MOMENT, WITHIN REASON.
    #
    # `create_intent` builds its intent_id as `symbol|tf|MANUAL|created_at`, so
    # a client that reuses one created_at across a retry rebuilds the identical
    # intent_id, which `create_intent` recognises as THIS order arriving again
    # and answers with the recorded one — `already_armed`, nothing written.
    # That is what makes arming from a phone safe to retry: a request whose
    # REPLY was lost can simply be sent again instead of the operator guessing
    # whether it landed. (It used to be the content-hashed store that collapsed
    # the second write, which was never reached: the same-side guard refused
    # first, so the retry-safe design reported the operator's own resting order
    # back to them as an error.)
    #
    # But created_at is written into an append-only fact and is the moment the
    # record will forever claim the plan was authored. A phone with a wrong
    # clock — or a stale value replayed hours later — would stamp a false one,
    # and nothing downstream could tell. So the caller may choose it only
    # within sight of this machine's clock; outside that it is refused rather
    # than silently corrected, because a corrected timestamp would break the
    # very idempotency it was sent for.
    now = int(time.time())
    supplied = payload.get("created_at")
    if supplied in (None, ""):
        created_at = now
    else:
        try:
            created_at = int(supplied)
        except (TypeError, ValueError):
            raise HTTPException(400, "created_at must be a unix timestamp in seconds")
        if abs(created_at - now) > ARM_CLOCK_SKEW_S:
            raise HTTPException(
                400,
                f"created_at is {abs(created_at - now)}s from this machine's "
                f"clock (limit {ARM_CLOCK_SKEW_S}s). Check the device's time; "
                f"the moment a plan was authored is recorded permanently.")
    con = store.connect()
    try:
        try:
            intent = manual.create_intent(
                con, symbol, tf,
                direction=str(payload.get("direction") or "").upper(),
                entry=payload.get("entry"), tp=payload.get("tp"),
                sl=payload.get("sl"),
                created_at=created_at,
                risk_usd=payload.get("risk_usd"),
                leverage=payload.get("leverage") or 1,
                trail_r=payload.get("trail_r"),
                partials=payload.get("partials"),
                note=str(payload.get("note") or ""))
        except manual.IntentRejected as exc:
            # A refused plan is a 400 carrying the REASON. The operator needs to
            # know which rule stopped them, not that "something went wrong".
            # Logged as well as returned: a refusal is a path the operator took
            # and could not act on, and one that leaves no trace cannot be
            # matched afterwards against what the book actually holds.
            from engine.runlog import get_logger
            get_logger().info(f"MANUAL ARM REFUSED {symbol} {tf} "
                              f"{str(payload.get('direction') or '').upper()} "
                              f"— nothing written — {exc}")
            raise HTTPException(400, str(exc))
        except (ValueError, ArithmeticError) as exc:
            raise HTTPException(400, str(exc))
        # Manual and autonomous plans now enter the same durable intent
        # vocabulary. The legacy manual resolver remains the PAPER fill model,
        # but there is no second order identity or un-audited broker-shaped
        # record. A later TESTNET/LIVE review can consume this exact contract.
        quantity = Decimal(str(intent.get("size_units") or "0"))
        core_key = execution.intent_key(
            intent["intent_id"], contracts.AutomationMode.PAPER,
            contracts.OrderKind.LIMIT.value, str(quantity), intent.get("entry"))
        core_intent = contracts.OrderIntent(
            intent_id=intent["intent_id"],
            setup_id="manual:" + intent["intent_id"],
            mode=contracts.AutomationMode.PAPER, symbol=symbol,
            direction=intent["direction"], order_kind=contracts.OrderKind.LIMIT,
            quantity=quantity, entry=Decimal(str(intent["entry"])),
            stop=Decimal(str(intent["sl"])),
            targets=(Decimal(str(intent["tp"])),), reduce_only=False,
            created_at=created_at, playbook_version=manual.MANUAL_VERSION,
            idempotency_key=core_key, timeframe=tf,
            expires_at=int(intent["expires_at_ts"])
            if intent.get("expires_at_ts") is not None else None)
        manual_risk = Decimal(str(intent.get("risk_usd") or "0"))
        notional = quantity * Decimal(str(intent["entry"]))
        approved = quantity > 0 and manual_risk > 0
        core_risk = contracts.RiskDecision(
            approved=approved,
            decision="APPROVED" if approved else "REJECTED",
            risk_usd=manual_risk if approved else Decimal(0),
            quantity=quantity, notional_usd=notional,
            implied_leverage=Decimal(str(intent.get("leverage") or "1")),
            reasons=(contracts.DecisionReason(
                "MANUAL_PLAN_VALIDATED" if approved else "UNSIZED_PAPER_PLAN",
                "The server validated the manual plan and its risk amount."
                if approved else
                "This paper plan has no positive risk amount and cannot be dispatched.",
                "INFO" if approved else "WARNING"),))
        core_plan = contracts.ExecutionPlan(
            intent=core_intent, risk=core_risk,
            venue=venues.venue_for(symbol).key,
            margin_mode="ISOLATED", position_mode="ONE_WAY",
            protection_deadline_seconds=5,
            version=execution.EXECUTION_CORE_VERSION)
        core_receipt = execution.enqueue(con, core_intent, plan=core_plan)
        from engine.runlog import get_logger
        # Resolve immediately, so the response reflects bars that have already
        # closed. Usually a no-op — the order was just placed and no eligible
        # bar exists yet — which is the correct causal answer, not a failure.
        #
        # AFTER the intent is committed, so a resolver failure is not an arming
        # failure and must not be reported as one. Raising here would answer a
        # request that succeeded with a 500, and the ticket would say the trade
        # was refused while the order rested on the book — the same message/
        # state disagreement the duplicate guard used to produce, arriving by
        # the other door. Said out loud instead: the order stands, its first
        # resolution pass did not.
        resolve_failed = None
        try:
            manual.run(con, symbol, tf, importer.TF_SECONDS[tf])
        except Exception as exc:                      # noqa: BLE001 - see above
            resolve_failed = f"{type(exc).__name__}: {exc}"
            get_logger().error(
                f"MANUAL ARM {symbol} {tf} recorded, but the first resolve pass "
                f"failed: {resolve_failed}")
        rungs = intent.get("partials") or []
        get_logger().info(
            ("MANUAL ARM ALREADY ARMED (no new order) " if intent.get("already_armed")
             else "MANUAL ARM ")
            + f"{symbol} {tf} {intent['direction']} "
            f"entry={intent['entry']} tp={intent['tp']} sl={intent['sl']}"
            + ("".join(f" scale={r['fraction']}@{r['price']}" for r in rungs))
            + " (paper)")
        return {"ok": True,
                # The request landed either way; this says whether it CREATED
                # anything. The ticket words its receipt off this, so a retry
                # cannot be announced as a second trade.
                "already_armed": bool(intent.get("already_armed")),
                "resolve_failed": resolve_failed,
                "intent": intent, "order_intent": contracts.to_wire(core_intent),
                "risk_decision": contracts.to_wire(core_risk),
                "execution_plan": contracts.to_wire(core_plan),
                "execution_receipt": core_receipt, "book": manual.book(con)}
    finally:
        con.close()


@app.get("/api/draft")
def draft_bracket(symbol: str, tf: str = "1H"):
    """A structure-anchored DRAFT bracket for the ticket — never a setup.

    Returns `null` when price is not near any live zone, and that is a real
    answer rather than a failure: it is what the ruler could never say. The
    engine's own proximity notion is 1 ATR (`setups.PROX_ATR`); this allows 3,
    so a decline means price genuinely is not at a level.
    """
    from engine import draft as _draft
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    con = store.connect()
    try:
        return {"symbol": symbol, "tf": tf, "draft": _draft.for_symbol(con, symbol, tf)}
    finally:
        con.close()


@app.get("/api/near-levels")
def near_levels():
    """The same question `/api/draft` answers for one chart, asked of them all.

    "Which markets is price standing at a level in" had no answer anywhere, so
    finding out meant opening charts one at a time — and a draft bracket on a
    chart the engine has never looked at reads exactly like the engine's own
    plan. Measured 2026-08-05: LINKUSDT 1D drew a LONG off a demand zone
    2.46 ATR away while the engine's attention stops at 1 ATR and it had no
    validated setup on that symbol all baseline.

    NOT a setup list. The Setup Deck is the engine's plans and "Approaching" is
    the engine's own FORMING signal; this is structure, and every row carries
    `engine_reach` saying whether the engine is even looking at that zone.

    Its own endpoint rather than a field on `/api/overview`: the sweep costs
    ~1.4s across 95 symbol/timeframe pairs, and overview is on the 30s poll
    that every surface waits behind.
    """
    from engine import nearlevels
    con = store.connect()
    try:
        return nearlevels.sweep(con)
    finally:
        con.close()


@app.post("/api/analyse")
def analyse_symbol(symbol: str, response: Response):
    """Run the engine chain over ONE symbol, on demand.

    48 of the symbols in the chart picker are outside the scan universe, so the
    engine has never looked at them and they carry no zones, no regime and no
    structure. This is how an operator asks it to look. It runs
    `pipeline.DESCRIPTIVE` in the roster's own order, so a per-symbol analysis
    cannot describe a market differently from the scanner, and facts are
    content-hashed, so overlapping with the scanner's own tick duplicates
    nothing.

    **The DESCRIPTION layer only — the trading engines are excluded.**
    `setups`/`execsim`/`scalein`/`cooldowns` would write simulated trades on a
    symbol nobody is scanning, and `edgestats`/`factorstats` grade that
    population. Wiring them to a button would make the graded book depend on
    which symbols an operator happened to click, which is not a record anyone
    can reproduce. What this produces is what the draft bracket needs — zones,
    liquidity, structure, regime — and nothing that reaches the strategy record.

    Synchronous, and it takes roughly 10-20s. That is deliberate: it is one
    symbol, triggered by an explicit click, and the caller wants the answer
    rather than a job id. The cycle-wide `/api/scan` is the async one because it
    covers 19 symbols and takes minutes.
    """
    import time as _t
    from engine import pipeline
    con = store.connect()
    try:
        if symbol not in universe.all_tracked_symbols(con):
            raise HTTPException(
                404, f"{symbol} has no stored candles — nothing to analyse")
        t0 = _t.time()
        produced, failed = {}, []
        for mod in pipeline.DESCRIPTIVE:
            name = mod.__name__.rsplit(".", 1)[-1]
            for tf in ("5m", "15m", "1H", "4H", "1D", "1W"):
                try:
                    r = mod.run(con, symbol, tf, importer.TF_SECONDS[tf])
                except Exception as exc:
                    # One engine failing must not abort the rest — a partial
                    # analysis is useful and a silent one is not (loud fallback).
                    failed.append(f"{name}/{tf}: {type(exc).__name__}")
                    continue
                for k, v in (r or {}).items():
                    if k in ("symbol", "tf") or not isinstance(v, int):
                        continue
                    produced[name] = produced.get(name, 0) + v
        con.commit()
        from engine.runlog import get_logger
        get_logger().info(
            f"ANALYSE {symbol}: {sum(produced.values())} new facts in "
            f"{_t.time() - t0:.1f}s" + (f", {len(failed)} engine errors" if failed else ""))
        if failed:
            response.status_code = 207        # partial: say so rather than imply success
        return {"ok": not failed, "symbol": symbol,
                "seconds": round(_t.time() - t0, 1),
                "new_facts": {k: v for k, v in produced.items() if v},
                "errors": failed}
    finally:
        con.close()


@app.post("/api/positions/close")
def close_position(payload: dict):
    """Operator closes an ENGINE position early, at the last closed bar.

    Records ONE override fact under the manual version and changes nothing
    else. The engine's simulation of that setup carries on and still records
    what holding to SL/TP produced, so the strategy record stays pure AND the
    pair of outcomes measures whether the early exit beat the rule.
    """
    from engine import manual
    sid = str(payload.get("setup_id") or "")
    if not sid:
        raise HTTPException(400, "setup_id required")
    con = store.connect()
    try:
        pf = portfolio()
        pos = next((p for p in pf.get("active_positions", [])
                    if p["setup_id"] == sid), None)
        if not pos:
            raise HTTPException(404, "no open engine position with that setup id "
                                     "— it may have already resolved")
        try:
            out = manual.close_engine_position(
                con, sid, pos["symbol"], pos["tf"], pos["direction"],
                pos["entry"], pos["sl"], risk_usd=pos.get("risk_usd"),
                note=str(payload.get("note") or ""))
        except manual.IntentRejected as exc:
            raise HTTPException(400, str(exc))
        from engine.runlog import get_logger
        get_logger().info(
            f"OPERATOR CLOSED {pos['symbol']} {pos['tf']} early at "
            f"{out['exit_price']} ({out['r_at_close']}R) — engine simulation "
            f"of {sid} continues and still records the held outcome")
        return {"ok": True, "closed": out}
    finally:
        con.close()


@app.post("/api/positions/adopt")
def adopt_position(payload: dict):
    """Operator takes custody of an engine position with their own levels.

    The engine entered it; the operator changes where it ends. Writes an
    intent (seeded at the ORIGINAL fill price, flagged already-filled) plus an
    override marking the engine position adopted. The engine's simulation
    keeps running its own plan, so both exits get recorded and the comparison
    is real rather than rhetorical.
    """
    import time
    from engine import manual
    sid = str(payload.get("setup_id") or "")
    if not sid:
        raise HTTPException(400, "setup_id required")
    con = store.connect()
    try:
        pf = portfolio()
        pos = next((p for p in pf.get("active_positions", [])
                    if p["setup_id"] == sid), None)
        if not pos:
            raise HTTPException(404, "no open engine position with that setup id")
        # The fill bar is where custody starts; without it the resolver would
        # hunt for an entry that already happened.
        row = con.execute(
            "SELECT confirmed_at, payload FROM facts WHERE symbol=? AND tf=? "
            "AND kind='order' AND algo_version=? "
            "AND json_extract(payload,'$.setup_id')=? "
            "AND json_extract(payload,'$.event')='FILLED' ORDER BY id DESC LIMIT 1",
            (pos["symbol"], pos["tf"], execsim.EXEC_VERSION, sid)).fetchone()
        if not row:
            raise HTTPException(409, "that position has no recorded fill to adopt")
        fill = json.loads(row[1])
        try:
            out = manual.adopt_position(
                con, sid, pos["symbol"], pos["tf"], pos["direction"],
                entry=fill.get("fill_price") or pos["entry"],
                sl=payload.get("sl", pos["sl"]), tp=payload.get("tp", pos["tp"]),
                original_sl=pos["sl"],
                fill_ts=row[0], adopted_at=int(time.time()),
                risk_usd=pos.get("risk_usd"), trail_r=payload.get("trail_r"),
                partials=payload.get("partials"),
                note=str(payload.get("note") or ""))
        except manual.IntentRejected as exc:
            raise HTTPException(400, str(exc))
        manual.run(con, pos["symbol"], pos["tf"],
                   importer.TF_SECONDS[pos["tf"]])
        from engine.runlog import get_logger
        get_logger().info(
            f"OPERATOR ADOPTED {pos['symbol']} {pos['tf']} — sl {out['sl']} "
            f"tp {out['tp']}"
            + (f" trail {out['trail_r']}R" if out.get('trail_r') else "")
            + ("".join(f" scale={r['fraction']}@{r['price']}"
                       for r in (out.get("partials") or [])))
            + f"; engine simulation of {sid} continues on its own plan")
        return {"ok": True, "adopted": out}
    finally:
        con.close()


@app.get("/api/manual/open")
def manual_open(symbol: str, tf: str = "1H"):
    """Live state of the operator's open trades on one chart.

    Resolves first, then reports: `manual.run` is idempotent and cheap for one
    symbol/tf, and without it a trade whose stop was hit two bars ago would
    still be described as OPEN until the next scanner cycle happened to visit.
    """
    from engine import manual
    if tf not in VALID_TFS:
        raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
    con = store.connect()
    try:
        manual.run(con, symbol, tf, importer.TF_SECONDS[tf])
        # The ENGINE's position on this chart too, so the ticket can offer to
        # take custody of it. One fetch, both books.
        eng = next((p for p in portfolio().get("active_positions", [])
                    if p["symbol"] == symbol and p["tf"] == tf), None)
        return {"symbol": symbol, "tf": tf,
                "open": manual.status(con, symbol, tf, importer.TF_SECONDS[tf]),
                "engine": eng}
    finally:
        con.close()


@app.get("/api/copilot/health")
def copilot_health():
    """Does the copilot's engine exist? Runs `claude --version`, nothing more.

    The Settings panel offers this as a button because the copilot's failure
    mode without the CLI is a mid-question error — a check that can be run
    BEFORE the first question is the difference between configuration and
    debugging."""
    import shutil
    import subprocess
    exe = shutil.which("claude")
    if not exe:
        return {"ok": False, "error": "the `claude` CLI is not on PATH"}
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True,
                           timeout=15)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "`claude --version` timed out"}
    if r.returncode != 0:
        return {"ok": False,
                "error": (r.stderr or r.stdout or "CLI failed").strip()[:200]}
    return {"ok": True, "version": (r.stdout or "").strip()[:80]}


@app.post("/api/copilot")
def copilot_chat(payload: dict):
    """One copilot turn. Observer only: returns prose, writes no facts.

    Runs on the operator's Claude subscription through the local `claude` CLI
    (print mode) — no API key, no per-token bill. The context pack is
    assembled server-side from the fact store and sent once per conversation;
    resumed turns ride the CLI session. Tools are disabled in the spawned
    session; even if they were not, its working directory is an empty scratch
    folder.
    """
    from engine import copilot
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message required")
    symbol = str(payload.get("symbol") or "")
    tf = str(payload.get("tf") or "1H")
    session_id = payload.get("session_id") or None
    model = str(payload.get("model") or copilot.DEFAULT_MODEL)
    context = str(payload.get("context") or "chart")
    pack = None
    if not session_id:
        con = store.connect()
        try:
            if context == "diagnostics":
                # the code-diagnosis pack: faults, gates, quality, log tail —
                # no symbol needed, the machine itself is the subject
                pack = copilot.build_diag_pack(con)
            else:
                if not symbol:
                    raise HTTPException(400, "symbol required on the first turn")
                if tf not in VALID_TFS:
                    raise HTTPException(400, f"tf must be one of {sorted(VALID_TFS)}")
                # The engine position on this chart, if the operator is in
                # one. Looked up HERE rather than inside build_pack, so
                # engine/ never has to import server to know what the
                # portfolio holds.
                sid = payload.get("setup_id") or None
                pos = next((p for p in portfolio().get("active_positions", [])
                            if p["symbol"] == symbol and p["tf"] == tf
                            and (not sid or p["setup_id"] == sid)), None)
                pack = copilot.build_pack(con, symbol, tf, sid, position=pos)
        finally:
            con.close()
    out = copilot.ask(message, pack=pack, session_id=session_id, model=model)
    if not out.get("ok"):
        raise HTTPException(502, out.get("error", "copilot failed"))
    return out


@app.post("/api/spotter/analyze")
def spotter_analyze(payload: dict):
    """Analyze sampled recording frames without touching the book or store.

    The browser retains the video and sends a bounded set of timestamped JPEG
    frames. The engine reviews them through an ephemeral, read-only Codex turn
    in a temporary directory, then deletes those files before this returns.
    """
    from engine import copilot
    frames = payload.get("frames")
    if not isinstance(frames, list) or not frames:
        raise HTTPException(400, "frames required")
    out = copilot.analyze_frames(frames)
    if not out.get("ok"):
        raise HTTPException(502, out.get("error", "Spotter analysis failed"))
    return out


@app.get("/api/manual/live")
def manual_live():
    """Every open operator order, across every market, with its live state.

    `/api/manual/book` reports STORED state — `ARMED` on all of them, forever,
    because the resolver only writes at terminal outcomes. `/api/manual/open`
    resolves properly but answers for one chart. Neither could answer "what
    orders do I have out?", which is why three armed trades sat invisible on
    every surface: Command reads the ENGINE's book, and hand-picked trades are
    deliberately not in it.

    Also reports the risk those orders have already spoken for. That figure is
    NOT part of the engine's budget and this endpoint does not make it one —
    `manual.arm` does not consult the risk authority and nothing here changes
    that. It is reported so the operator can see the exposure the budget panel
    does not know about, rather than discovering it at a fill.
    """
    from engine import manual
    con = store.connect()
    try:
        rows = manual.live(con)
        pending_risk = sum((Decimal(str(r["risk_usd"])) for r in rows
                            if r["state"] == "PENDING" and r.get("risk_usd")),
                           Decimal(0))
        # Only the size still ON is still exposed. A position with half taken
        # off can lose half of what it was armed for, and quoting the original
        # stake here would overstate the very figure this endpoint exists to
        # disclose. `open_fraction` is 1 on a trade that has not been scaled,
        # so an ordinary book reports exactly what it always did.
        open_risk = sum((Decimal(str(r["risk_usd"]))
                         * Decimal(str(r.get("open_fraction") or 1))
                         for r in rows
                         if r["state"] == "OPEN" and r.get("risk_usd")),
                        Decimal(0))
        return {"version": manual.MANUAL_VERSION, "open": rows,
                "n_pending": sum(1 for r in rows if r["state"] == "PENDING"),
                "n_open": sum(1 for r in rows if r["state"] == "OPEN"),
                "pending_risk_usd": str(pending_risk),
                "open_risk_usd": str(open_risk),
                "measured_at": int(time.time())}
    finally:
        con.close()


@app.post("/api/manual/cancel")
def manual_cancel(payload: dict):
    """Withdraw a resting operator order that has not filled."""
    from engine import manual
    intent_id = str(payload.get("intent_id") or "")
    if not intent_id:
        raise HTTPException(400, "intent_id required")
    con = store.connect()
    try:
        try:
            res = manual.cancel_intent(con, intent_id)
        except manual.IntentRejected as exc:
            raise HTTPException(400, str(exc))
        from engine.runlog import get_logger
        get_logger().info(
            f"MANUAL CANCEL {res['symbol']} {res['tf']} {intent_id} (paper)")
        return {"ok": True, **res}
    finally:
        con.close()


@app.get("/api/manual/book")
def manual_book():
    """The operator's paper record — separate curve, separate everything."""
    from engine import manual
    con = store.connect()
    try:
        return manual.book(con)
    finally:
        con.close()


@app.get("/api/settings")
def get_settings():
    from engine import settings as _settings
    con = store.connect()
    try:
        values = _settings.all_settings(con)
        # the guardrail panel shows engine-owned limits beside operator ones;
        # it must read them, never restate them. PAPER basis: these are the
        # limits enforced on the book the panel sits beside.
        _g = risk.gates_for_mode(risk.AutomationMode.PAPER)
        values["risk_config"] = {
            "daily_loss_pct": float(_g["daily_loss_limit_pct"]) * 100,
            "max_total_risk_pct": float(_g["max_total_open_risk_pct"]) * 100,
            "max_concurrent": _g["max_concurrent"],
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


@app.get("/api/edge-stats")
def edge_stats(algo_version: str | None = None, symbol: str | None = None,
               tf: str | None = None, venue_state: str | None = "TRADED",
               resamples: int = Query(5000, ge=500, le=20000)):
    """Is the recorded book distinguishable from zero?

    Bootstrap CI on per-trade expectancy plus the breakeven fee. The UI shows
    this beside the equity curve because a curve alone cannot answer it — a
    losing run and an unlucky run look identical on a chart, and the difference
    decides whether you change the strategy or wait for sample.

    Resamples default lower than the CLI's 20k: this is a request path, and the
    CI barely moves above ~5k. The value used is returned so the number on
    screen is never mistaken for the deeper offline one.

    Defaults to the TRADED book. This panel sits beside the equity curve, which
    implies the two describe the same trades — and until 2026-07-30 they did
    not: 276 of 639 (43.2%) were Kraken SHADOW symbols `risk.py` refuses to
    size. `counts` still reports both halves, and `?venue_state=` overrides for
    research (SHADOW, or empty for the combined book).
    """
    from engine import edgestats
    con = store.connect()
    try:
        return edgestats.report(con, algo_version=algo_version, symbol=symbol,
                                tf=tf, venue_state=venue_state or None,
                                resamples=resamples)
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
def reset_baseline(payload: dict):
    """Start a clean paper window. Historical facts and candles are retained.

    The confirmation moved out of the query string and into a JSON body on
    4 Aug 2026, belt-and-braces behind `_reject_cross_site_api`. This is the
    one endpoint here whose effect cannot be undone from the app, so it gets
    the second lock: a plain HTML form cannot produce a body FastAPI will
    parse as JSON, so a form POST is refused at validation before any handler
    runs — even if the browser ever stops sending `Sec-Fetch-Site`.
    """
    if not payload.get("confirm"):
        raise HTTPException(400, 'a JSON body {"confirm": true} is required; '
                                 "no data will be deleted")
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
        # MAINTAINED vs MERELY STORED. The live loop refreshes candles for
        # `universe.scan_symbols` and nothing else (live.py:236, :350). Every
        # other symbol in this table is history the store happens to hold —
        # the chart picker offers 48 symbols outside the scan universe, and
        # opening one fetches candles that then sit there ageing forever, by
        # design.
        #
        # Measured 4 Aug 2026: 227 of 419 series were stale and ZERO of them
        # were in the scan universe. `status` was computed over all of them,
        # so it had been DEGRADED continuously and could never read OK again
        # — a status that cannot change is not a status. Worse, the Diagnose
        # wizard reads this and told the operator to "run a scan to
        # re-import", which cannot work for a symbol the scanner does not
        # fetch: advice that never succeeds, in the one tool whose job is
        # telling you what to do.
        maintained = set(universe.scan_symbols(con))
        series = []
        for symbol, tf, last_open in rows:
            sec = importer.TF_SECONDS[tf]
            age_s = max(0, now - (last_open + sec))
            series.append({"symbol": symbol, "tf": tf, "last_open": last_open,
                           "age_s": age_s, "stale": age_s > 2 * sec,
                           "maintained": symbol in maintained})
        stale_maintained = [s for s in series if s["stale"] and s["maintained"]]
        stale_stored = [s for s in series if s["stale"] and not s["maintained"]]
        # Gap rows whose requested range STARTS before 2000 are artefacts of the
        # cold-start bug fixed 2026-07-30: a symbol with no candles asked the
        # venue for history from 1970 and logged every bucket since as missing.
        # They are quarantined at the read site rather than deleted — the log is
        # evidence of what happened, including of the bug — but they must not
        # reach this metric: 6,187,847,452 fabricated gaps against 699,726 real
        # ones made `gaps_logged` 99.99% noise, and `risk.py` halts on the
        # data-health verdict this feeds. The cutoff was born here; it lives in
        # importer.PRE_2000 now because the quality audit and the aggregator
        # apply the same quarantine to the same rows.
        bad, gaps = con.execute(
            "SELECT COALESCE(SUM(n_bad),0), COALESCE(SUM(n_gaps),0) "
            "FROM import_log WHERE range_start >= ?", (importer.PRE_2000,)).fetchone()
        quarantined = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(n_gaps),0) FROM import_log "
            "WHERE range_start < ?", (importer.PRE_2000,)).fetchone()
        return {"status": "OK" if integrity == "ok" and not stale_maintained
                          else "DEGRADED",
                "database": integrity, "bad_candles_rejected": bad,
                "gaps_logged": gaps,
                "quarantined_gap_rows": quarantined[0],
                "quarantined_gaps": quarantined[1],
                "quarantine_reason": (
                    "import_log rows requesting history from before 2000 are "
                    "cold-start artefacts (fixed 2026-07-30); excluded from "
                    "gaps_logged but retained in the log"
                ) if quarantined[0] else None,
                "series": series,
                "maintained_series": sum(1 for s in series if s["maintained"]),
                # `stale_series` means STALE AND MAINTAINED: the ones a scan
                # can actually fix. Its consumer (the Diagnose wizard) turns
                # this into an instruction, and an instruction that cannot
                # succeed is worse than none.
                "stale_series": stale_maintained,
                # Nothing is hidden — the rest is reported, and named as what
                # it is rather than counted as a fault.
                "stored_stale_count": len(stale_stored),
                "stored_stale_reason": (
                    f"{len(stale_stored)} series are history for symbols "
                    f"outside the scan universe. Nothing refreshes them by "
                    f"design — they are candles fetched when a chart was "
                    f"opened. Not a fault, and no scan will change it."
                ) if stale_stored else None}
    finally:
        con.close()


@app.get("/api/pipeline-health")
def pipeline_health(symbol: str | None = None):
    """Read-only A-to-Z contract audit used to qualify performance.

    Serves the verdict THE SCANNER RECORDED (`quality.last_persisted`), which
    is the one `risk.py` actually gated on. It does not audit here, and that is
    the point: this process kept its own `cached_audit` slot, audited whenever
    a request happened to arrive, and could therefore publish a verdict the
    trading engine never saw. On 4 Aug 2026 it published BLOCKED — 23 symbols
    whose 15m bar had not closed yet, a HALT-rung code — while the scanner's
    audit eight seconds later recorded DEGRADED and kept trading. A read-only
    surface must not invent a verdict; see `quality.last_persisted`.

    Falls back to the in-process cache only before the scanner has ever
    recorded one, so a fresh store still shows something rather than nothing.
    A per-symbol query still audits directly since it is narrow and on demand.
    """
    con = store.connect()
    try:
        if symbol:
            return quality.audit(con, symbol=symbol, persist=False)
        report = quality.last_persisted(con)
        if report is None:
            # No recorded verdict yet. The in-process cache is the only thing
            # that can answer, and it is honest about being provisional.
            report = quality.cached_audit(con)
            if report is not None:
                report = {**report, "source": "local", "age_s": 0}
        if report is None:
            return {"version": quality.QUALITY_VERSION,
                    "status": "PENDING", "evaluation_allowed": True,
                    "pending": True, "stages": [], "blockers": [], "warnings": [],
                    "source": "none", "detail": "first audit running"}
        return report
    finally:
        con.close()


NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}


def _asset_version() -> str:
    """One cache-busting version for every asset the shell loads, derived from
    the newest mtime under static/.

    The ?v=N query strings in shell.html were HAND-MAINTAINED — thirteen tags
    edited by whoever remembered, sitting at ?v=1 for weeks and then bumped in
    a batch. The failure mode is silent and nasty: one stale module running
    against twelve fresh ones does not error, it disagrees — the exact class of
    bug this codebase keeps paying to remove between panels, reintroduced
    between files.

    mtime rather than server start time, deliberately: a restart with unchanged
    files should NOT invalidate every client cache, and a changed file must
    bust even if the server happened to restart at the same second.
    """
    newest = max((p.stat().st_mtime_ns for p in STATIC.rglob("*")
                  if p.is_file()), default=0)
    return str(newest // 1_000_000_000)


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    """What makes the phone treat this as an app rather than a page.

    Served from the ROOT, not from the /static mount, for two reasons: the
    media type has to be `application/manifest+json` and StaticFiles guesses
    it from the extension (Windows does not always register `.webmanifest`),
    and a manifest at the root cannot argue with its own `scope: "/"`.

    Deliberately NO service worker accompanies this. Chrome has not required
    one to install since v108, and the only thing a worker could usefully
    cache here is /static/* — which is exactly what `_NoCacheStatic` exists to
    prevent. That class is documented against a real failure: a cached
    cockpit.js running against a fresh cockpit.html bound a DOM id that no
    longer existed and silently killed a drawer. A service worker would
    reintroduce that, persistently, on a device the operator cannot open
    devtools on. The API must never be cached either — /api/manual/open and
    /api/manual/live call manual.run(), so they write fills; a replay queue
    over those would resolve trades nobody authored.
    """
    return FileResponse(STATIC / "manifest.webmanifest",
                        media_type="application/manifest+json",
                        headers=NO_CACHE)


@app.get("/")
def index():
    """The redesigned shell (docs/REDESIGN-PLAN.md phase 1).

    Served with every ?v=N stamped to the current asset version rather than
    whatever number was last hand-edited into the file. The file on disk keeps
    plain ?v=N so it still works opened directly; the route is the authority.
    """
    html = (STATIC / "shell.html").read_text(encoding="utf-8")
    html = re.sub(r"\?v=\d+", "?v=" + _asset_version(), html)
    return HTMLResponse(html, headers=NO_CACHE)


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
    """ApexShell action verbs. Allow-listed and non-destructive: `audit` refreshes
    the scanner-recorded verdict, `brief` writes a war-room dossier for a human.
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
