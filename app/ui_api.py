"""Versioned cockpit read models. Account money never falls back to replay."""
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime, timezone
import json
import time

from fastapi import APIRouter, HTTPException, Query
from engine import automation, importer, livegate, manual, opportunities, settings, shared_account, stocks, store
from engine.contracts import to_wire

router = APIRouter(prefix="/api/ui/v1")
VERSION = "cockpit-readmodel-v2"


def workspace_scope(workspace):
    if workspace not in ("CRYPTO", "STOCKS"):
        raise HTTPException(400, "Unknown workspace")
    return workspace


@contextmanager
def account_read(expected_epoch=None):
    con = store.connect()
    try:
        shared_account.ensure(con)
        con.execute("BEGIN")
        epoch = shared_account.current_epoch(con)
        if expected_epoch is not None and expected_epoch != (epoch['id'] if epoch else 'legacy'):
            raise HTTPException(409, 'ACCOUNT_CHANGED: refresh this workspace before continuing')
        yield con
    finally:
        con.rollback()
        con.close()


def stock_context():
    return {"version": VERSION, "workspace": "STOCKS", "mode": "PAPER", "epoch_id": "stocks-unavailable",
            "state": "UNAVAILABLE", "account": None, "capabilities": stocks.status(),
            "observed_at": int(time.time())}


def context_model(con):
    model = shared_account.context(con)
    mode, revision, changed_at = automation.current(con)
    model["automation"] = {"mode": mode.value, "revision": revision, "changed_at": changed_at,
                           "halted": settings.all_settings(con)["halted"]}
    model["risk_percent_label"] = format((Decimal(model["risk_pct"]) * 100).normalize(), "f") + "%"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    model["today_realised_usd"] = model["account"]["realised_by_day"].get(today, "0")
    # `live_reason` is READ from the authority, never restated here. This used
    # to say "Required venue safety drills are not complete", which is not why
    # live is locked and would have kept saying it after the drills passed.
    model["capabilities"] = {"paper": True, "live": False,
        "live_reason": livegate.BUILD_NOTE,
        "scale_in": False, "spotter": "ADVISORY_ONLY"}
    model["version"] = VERSION
    return model


@router.get("/context")
def context(workspace: str = "CRYPTO"):
    if workspace_scope(workspace) == "STOCKS":
        return stock_context()
    with account_read() as con:
        return context_model(con)


def trade_rows(con, archive=False):
    rows = shared_account.journal(con, include_legacy=archive)
    epoch = shared_account.current_epoch(con)
    out = []
    for row in rows:
        if archive and (row["account_epoch_id"] == epoch["id"] if epoch else row["account_epoch_id"] is None):
            continue
        plan = row.pop("plan")
        intent, risk = plan.get("intent", {}), plan.get("risk", {})
        row.update(symbol=intent.get("symbol"), timeframe=intent.get("timeframe"),
                   direction=intent.get("direction"), planned_entry=intent.get("entry"),
                   stop=row.get("current_stop") or intent.get("stop"), planned_stop=intent.get("stop"), targets=intent.get("targets", []),
                   quantity=intent.get("quantity"), risk_usd=risk.get("risk_usd"),
                   evidence_scope="ARCHIVED_ACCOUNT" if archive else "EXECUTED_ACCOUNT")
        row["pnl_basis"] = 'EXACT_SETTLEMENT' if row['realised_usd'] is not None else 'LEGACY_R_ESTIMATE'
        if row['realised_usd'] is None:
            row["realised_usd"] = (str(Decimal(row["r_multiple"]) * Decimal(risk["risk_usd"]))
                                   if row["r_multiple"] is not None and risk.get("risk_usd") else None)
        for field in ('fees', 'funding', 'slippage'):
            value = row.get(field + '_price_units')
            row[field + '_usd'] = str(Decimal(value) * Decimal(row['quantity'])) if value is not None and row['quantity'] else None
        row["terminal"] = row["state"] in shared_account.TERMINAL
        row["active"] = not row["terminal"]
        out.append(row)
    if archive:
        known = {r[0] for r in con.execute('SELECT intent_id FROM execution_outbox')}
        for fact in manual._facts(con, manual.EXEC_KIND):
            result = json.loads(fact['payload'])
            if result['intent_id'] in known:
                continue
            original = manual._intent_by_id(con, fact['symbol'], fact['tf'], result['intent_id']) or {}
            out.append(dict(intent_id=result['intent_id'], attempt_id=result['intent_id'],
                symbol=fact['symbol'], timeframe=fact['tf'], origin='OPERATOR', controller='OPERATOR',
                grade_eligible=False, state='LEGACY_MANUAL', outcome=result.get('outcome'),
                direction=result.get('direction'), r_multiple=result.get('r_multiple'),
                realised_usd=result.get('realised_usd'), risk_usd=original.get('risk_usd'),
                entry=result.get('entry'), exit_price=result.get('exit_price'),
                stop=original.get('sl'), planned_stop=original.get('sl'), targets=[original.get('tp')],
                created_at=original.get('armed_at'), closed_at=fact['confirmed_at'],
                active=False, terminal=True, pnl_basis='LEGACY_MANUAL_RECORD',
                evidence_scope='LEGACY_MANUAL_ONLY', fees_usd=None, funding_usd=None, slippage_usd=None))
    return out


def actionable(row, now=None):
    """Can the operator act on this row RIGHT NOW.

    One definition, because this file had three and they disagreed. The
    `/opportunities` count and the Ready filter asked for state plus
    eligibility plus finite positive prices plus an unexpired entry window;
    `progress_label` and the sort order asked for `state == "READY"` alone; and
    `/home` asked for state plus eligibility. So a setup whose entry window had
    closed — the ordinary case, since `state` is computed when the scanner runs
    and the window is checked when the request arrives — was badged "Ready to
    trade", sorted to the top of the list, and given a "Review trade" button,
    while the Ready tab beside it said there was nothing ready and the count
    read zero.

    Expiry is why this cannot be answered at scan time: it is a question about
    the moment someone looks.
    """
    now = int(time.time()) if now is None else now
    setup = row.get("setup") or {}
    try:
        prices = [Decimal(str(v)) for v in (setup.get("entry"), setup.get("stop"),
                                            (setup.get("targets") or [None])[0])]
        return (row.get("state") == "READY" and bool(row.get("eligible"))
                and all(v.is_finite() and v > 0 for v in prices)
                and int(setup.get("expires_at") or 0) > now)
    except (ArithmeticError, TypeError, ValueError):
        return False


def opportunity_rows(con, search="", state="", domain="PAPER"):
    rows = opportunities.list_candidates(con, domain=domain, include_history=(domain == "RESEARCH"), show_real_exposure=False)
    if search:
        rows = [r for r in rows if search.upper() in r["setup"]["symbol"].upper()]
    if state:
        rows = [r for r in rows if r["state"] == state]
    def order(row):
        distance = row.get("economics", {}).get("distance_atr")
        try:
            distance = abs(Decimal(str(distance)))
            if not distance.is_finite():
                distance = Decimal("Infinity")
        except ArithmeticError:
            distance = Decimal("Infinity")
        return (opportunities._STATE_ORDER.get(row["state"], 99), distance,
                row["setup"]["symbol"], row["setup"]["timeframe"], row["setup"]["setup_id"])
    rows.sort(key=order)
    stories = opportunities._research_records(con, int(store.get_active_baseline(con)["started_at"])) if domain == "RESEARCH" else {}

    from engine import setups
    recorded_setups = opportunities._latest_by_setup(con, "setup", setups.SETUP_VERSION, int(store.get_active_baseline(con)["started_at"]))
    for row in rows:
        evidence = recorded_setups.get(row["setup"]["setup_id"], {})
        recorded_distance = evidence.get("distance_atr")
        if recorded_distance is None:
            recorded_distance = evidence.get("prox_atr")
        if recorded_distance is not None:
            row.setdefault("economics", {})["distance_atr"] = recorded_distance
        row["progress_stage"] = ("confirmation" if evidence.get("state") == "CONFIRMING" else
                                 "price" if evidence.get("state") == "FORMING" else "watching")
        # The badge the cockpit renders, and the button beside it. It must
        # agree with the Ready filter and the count — see `actionable`.
        row["actionable"] = actionable(row)
        row["progress_label"] = (
            "Ready to trade" if row["actionable"] else
            "Entry window closed" if row["state"] == "READY" else
            "Waiting for confirmation" if row["progress_stage"] == "confirmation" else
            "Waiting for price" if row["progress_stage"] == "price" else "Developing setup")
        row["confirmation_deadline"] = evidence.get("confirm_deadline_ts")
        row["cancel_reason"] = evidence.get("cancel_reason")
        if domain == "RESEARCH":
            recorded = stories.get(row["setup"]["setup_id"])
            if recorded and opportunities._describes_an_earlier_attempt(recorded[0], recorded[1], row["setup"]):
                recorded = None
            row["simulation"] = recorded[2] if recorded else None
            row["simulation_updated_at"] = recorded[1] if recorded else None
        for key in ("quality_score", "ranking_components", "legacy_rank", "research_story"):
            row.pop(key, None)
        # Candidate sizing was computed by the scanner. Only a fresh ticket
        # preview may describe current shared-account purchasing power.
        row.pop("risk_decision", None)
        row["economics"] = {k: v for k, v in row.get("economics", {}).items()
                            if k not in ("risk_usd", "notional_usd")}
    if domain == "RESEARCH":
        rows.sort(key=lambda row: row.get("simulation_updated_at") or row["setup"].get("confirmed_at") or 0, reverse=True)
    return rows


@router.get("/setup-guide")
def setup_guide(setup_id: str, workspace: str = "CRYPTO"):
    if workspace_scope(workspace) != "CRYPTO":
        raise HTTPException(404, "Stock setup levels are not available")
    from engine import setups, zones
    with account_read() as con:
        record = con.execute("SELECT payload,confirmed_at FROM facts WHERE kind='setup' AND algo_version=? "
                             "AND json_extract(payload,'$.setup_id')=? ORDER BY confirmed_at DESC,id DESC LIMIT 1",
                             (setups.SETUP_VERSION, setup_id)).fetchone()
        if not record:
            raise HTTPException(404, "The recorded setup is no longer available")
        payload = json.loads(record[0])
        zone = con.execute("SELECT payload FROM facts WHERE kind='zone' AND algo_version=? "
                           "AND json_extract(payload,'$.zone_id')=? AND json_extract(payload,'$.event')='CREATED' "
                           "ORDER BY confirmed_at DESC,id DESC LIMIT 1", (zones.ZONE_VERSION, payload.get('zone_id'))).fetchone()
        bounds = json.loads(zone[0]) if zone else {}
        long = payload.get('direction') == 'LONG'
        return {"setup_id":setup_id, "updated_at":record[1], "zone_bottom":bounds.get('bottom'),
                "zone_top":bounds.get('top'), "confirmation_boundary":bounds.get('top' if long else 'bottom'),
                "confirmation":("A completed candle must touch the area, close above its upper edge, and finish in the top 34% of its range." if long else
                                "A completed candle must touch the area, close below its lower edge, and finish in the bottom 34% of its range."),
                "confirmation_deadline":payload.get('confirm_deadline_ts'),
                "entry_deadline":payload.get('expires_at_ts'), "stop":payload.get('sl'),
                "skip_if":"The zone breaks before confirmation, confirmation takes too long, or later entry and risk checks fail. The zone-break threshold includes a changing volatility/tick buffer; the zone edge alone is not that threshold.",
                "cancel_reason":payload.get('cancel_reason'), "state":payload.get('state')}


@router.get("/home")
def home(workspace: str = "CRYPTO", epoch_id: str | None = None):
    if workspace_scope(workspace) == "STOCKS":
        return {"context": stock_context(), "positions": [], "recent": [], "opportunities": []}
    with account_read(epoch_id) as con:
        rows = trade_rows(con)
        return {"context": context_model(con), "positions": [r for r in rows if r["active"]],
                "recent": [r for r in rows if r["closed_at"] is not None][:5],
                "opportunities": [row for row in opportunity_rows(con) if actionable(row)][:5]}


@router.get("/opportunities")
def opportunity_list(workspace: str = "CRYPTO", search: str = "", state: str = "",
                     limit: int = Query(10, ge=1, le=200), group: str = "all", epoch_id: str | None = None,
                     sort: str = "progress"):
    if workspace_scope(workspace) == "STOCKS":
        return {"items": [], "capabilities": stocks.status(), "workspace": workspace}
    with account_read(epoch_id) as con:
        rows = opportunity_rows(con, search, state)
        if sort not in ("progress", "newest", "distance"):
            raise HTTPException(400, "Unknown opportunity sort")
        now = int(time.time())
        ready = lambda row: actionable(row, now)
        counts = {"ready": sum(ready(r) for r in rows), "watching": sum(r["state"] in ("FORMING", "WATCHING") for r in rows)}
        if group == "ready":
            rows = [r for r in rows if ready(r)]
        elif group == "watching":
            rows = [r for r in rows if r["state"] in ("FORMING", "WATCHING")]
        elif group != "all":
            raise HTTPException(400, "Unknown opportunity group")
        def order(row):
            setup = row["setup"]
            try:
                distance = abs(Decimal(str(row.get("economics", {}).get("distance_atr"))))
                if not distance.is_finite():
                    distance = Decimal("Infinity")
            except (ArithmeticError, TypeError, ValueError):
                distance = Decimal("Infinity")
            # `ready`, not `state`: a row the Ready tab excludes must not be
            # sorted above the setups that are genuinely actionable.
            stage = 0 if ready(row) else {"confirmation": 1, "price": 2}.get(row.get("progress_stage"), 3)
            newest = -int(setup.get("confirmed_at") or 0)
            identity = (setup["symbol"], setup["timeframe"], setup["setup_id"])
            return ((newest, stage, distance) if sort == "newest" else (distance, stage, newest) if sort == "distance" else (stage, distance, newest)) + identity
        rows.sort(key=order)
        ordering = {"progress": "Confirmation stage first, then recorded proximity to the zone. This is not a prediction of which trade will win.",
                    "newest": "Newest recorded setups first.", "distance": "Nearest zone when the setup was recorded. This is not live distance to entry."}[sort]
        return {"items": rows[:limit], "total": len(rows), "counts": counts, "workspace": workspace, "domain": "PAPER",
                "ordering": ordering}


@router.get("/positions")
def positions(workspace: str = "CRYPTO", epoch_id: str | None = None):
    if workspace_scope(workspace) == "STOCKS":
        return {"items": [], "workspace": workspace}
    with account_read(epoch_id) as con:
        return {"items": [r for r in trade_rows(con) if r["active"]], "workspace": workspace}


@router.get("/journal")
def journal(workspace: str = "CRYPTO", archive: bool = False, epoch_id: str | None = None):
    if workspace_scope(workspace) == "STOCKS":
        return {"items": [], "workspace": workspace, "scope": "UNAVAILABLE"}
    with account_read(epoch_id) as con:
        return {"items": trade_rows(con, archive), "workspace": workspace,
                "scope": "ARCHIVED_ACCOUNT" if archive else "EXECUTED_ACCOUNT",
                "note": "Compare different risk profiles in R, not dollars. Cancelled orders are not trades."}


@router.get("/trades/{intent_id}/diagnosis")
def diagnosis(intent_id: str, workspace: str = "CRYPTO"):
    if workspace_scope(workspace) != "CRYPTO":
        raise HTTPException(404, "No stock account trade")
    with account_read() as con:
        rows = trade_rows(con) + trade_rows(con, True)
        row = next((r for r in rows if r["intent_id"] == intent_id), None)
        if row is None:
            raise HTTPException(404, "Account trade not found")
        from engine import stopstudy, tradevisuals, zonestudy
        row["price_format"] = tradevisuals.chart_format(row)
        row["excursion"] = tradevisuals.excursion(con, row)
        return {"trade": row, "authority": "RECORDED_EXECUTION", "advisory_only": True,
                "stop_comparison": stopstudy.report(con, key="paper:"+intent_id),
                "zone_comparison": zonestudy.report(con, key="paper:"+intent_id),
                "facts": [f"Origin: {row['origin']}. Current controller: {row['controller']}.",
                    f"Recorded outcome: {row['outcome'] or row['state']}.",
                    f"Net result: {row['r_multiple']} R." if row['r_multiple'] is not None else "No settled R result yet.",
                    "Eligible for the bot execution cohort." if row['grade_eligible'] else
                    "Excluded from the bot execution cohort because of operator origin or intervention."],
                "limits": "These facts describe execution. They do not establish why the market moved or predict the next trade."}


@router.get("/research")
def research(workspace: str = "CRYPTO"):
    if workspace_scope(workspace) == "STOCKS":
        from engine import stockdemo
        return {"scope": "FIXTURE", "training": stockdemo.report()}
    with account_read() as con:
        return {"scope": "RESEARCH", "items": opportunity_rows(con, domain="RESEARCH"),
                "note": "Counterfactual strategy replay. These are not orders in your account."}


@router.get("/market-pulse")
def market_pulse(workspace: str = "CRYPTO"):
    workspace_scope(workspace)
    from engine import marketpulse
    return marketpulse.current()


@router.get("/forward-trial")
def forward_trial(workspace: str = "CRYPTO"):
    from engine import forwardtrial
    if workspace_scope(workspace) != "CRYPTO":
        return {"state": "UNAVAILABLE", "items": [], "note": "This trial uses crypto markets."}
    con = store.connect()
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        return forwardtrial.report(con)
    finally:
        con.rollback()
        con.close()


@router.get("/stop-comparison")
def stop_comparison(workspace: str = "CRYPTO"):
    from engine import stopstudy
    if workspace_scope(workspace) != "CRYPTO":
        return {"state": "UNAVAILABLE", "items": [], "note": "This comparison uses crypto paper trades."}
    con = store.connect()
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        return stopstudy.report(con)
    finally:
        con.rollback()
        con.close()


@router.get("/zone-comparison")
def zone_comparison(workspace: str = "CRYPTO"):
    from engine import zonestudy
    if workspace_scope(workspace) != "CRYPTO":
        return {"state": "UNAVAILABLE", "items": [], "note": "This comparison uses crypto paper trades."}
    con = store.connect()
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        return zonestudy.report(con)
    finally:
        con.rollback()
        con.close()


@router.get("/candles")
def candles(symbol: str, tf: str = "1H", workspace: str = "CRYPTO"):
    if workspace_scope(workspace) != "CRYPTO":
        raise HTTPException(409, "Stock tape unavailable. Use synthetic training in Research.")
    if tf not in importer.TF_SECONDS:
        raise HTTPException(400, "Unknown timeframe")
    with account_read() as con:
        rows = store.get_candles(con, symbol, tf, limit=500)
        rows = [r for r in rows if r['open_ts'] + importer.TF_SECONDS[tf] <= int(time.time())]
        return {"symbol": symbol, "tf": tf, "workspace": workspace,
                "mark": rows[-1]['close'] if rows else None,
                "observed_at": rows[-1]['open_ts'] + importer.TF_SECONDS[tf] if rows else None,
                "candles": [{"time": r['open_ts'], **{k: r[k] for k in ('open','high','low','close')}} for r in rows]}


@router.post("/ticket/preview")
def preview(payload: dict):
    if workspace_scope(payload.get("workspace")) != "CRYPTO":
        raise HTTPException(409, "No stock order route is enabled")
    con = store.connect()
    try:
        shared_account.ensure(con)
        with shared_account.immediate(con):
            symbol, tf = str(payload.get('symbol', '')), str(payload.get('tf', ''))
            if tf not in importer.TF_SECONDS:
                raise ValueError("Unknown timeframe")
            direction = str(payload.get('direction', '')).upper()
            entry, stop, target = (Decimal(str(payload.get(k))) for k in ('entry','sl','tp'))
            manual.validate(symbol, direction, entry, target, stop, Decimal(1))
            now = int(time.time())
            latest = con.execute("SELECT MAX(open_ts) FROM candles WHERE symbol=? AND tf=? AND open_ts+?<=?",
                                 (symbol, tf, importer.TF_SECONDS[tf], now)).fetchone()[0]
            if latest is None or now - latest > 2 * importer.TF_SECONDS[tf]:
                raise ValueError("No recent closed candle. Wait for the scanner before placing a trade.")
            _, amount, epoch = shared_account._decision(con, symbol=symbol, direction=direction,
                entry=entry, stop=stop, now=now, requested=payload.get('risk_usd') or None)
            request = dict(symbol=symbol, tf=tf, direction=direction, entry=str(entry), sl=str(stop),
                           tp=str(target), risk_usd=str(amount), created_at=now,
                           expected_epoch=epoch['id'] if epoch else 'legacy', workspace='CRYPTO')
            return {"request": request, "quantity": str(amount / abs(entry-stop)), "risk_usd": str(amount),
                    "rr": str(abs(target-entry)/abs(entry-stop)), "expires_at": now+120,
                    "note": "Preview only. The shared account is checked again when you place the order."}
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        con.close()


@router.post("/ticket/arm")
def arm(payload: dict):
    if workspace_scope(payload.get("workspace")) != 'CRYPTO':
        raise HTTPException(409, 'No stock order route is enabled')
    con = store.connect()
    try:
        terms = {key: payload.get(key) for key in ('symbol','tf','direction','entry','tp','sl',
                                                  'created_at','risk_usd','expected_epoch')}
        if terms['tf'] not in importer.TF_SECONDS or not terms['expected_epoch']:
            raise ValueError('Review a current ticket first')
        terms['created_at'] = int(terms['created_at'])
        receipt = shared_account.create_manual(con, **terms, max_age=120)
        return {"ok": True, "receipt": receipt}
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        con.close()
