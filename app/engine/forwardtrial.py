"""Prospective breakout trial. Own ledger; never creates account or order facts.

Observation time, not a backdated strategy confirmation, starts the entry clock.
Accepted candles and fills are frozen so later imports cannot rewrite results.
"""
import json
import time
from decimal import Decimal

from . import breakout, costs, execsim, importer, store, swings, venues

TRIAL_VERSION = "forward-trial-v0.1-draft"
# Frozen on purpose, and re-pointed by hand when an input moves. A trial
# whose stored config names other versions goes PAUSED rather than
# repricing across the change (`active`), because its record is evidence
# about the rules that made it. Confirmation lifecycle moves exec to v29;
# existing stored configurations stay unchanged and visibly pause.
DEPENDENCIES = {"breakout": "breakout-v0.8-draft", "exec": "exec-v0.29-draft",
                "swing": "swing-v0.11-draft"}
STARTING_BALANCE = Decimal("10000")
RISK_USD = Decimal("100")
MAX_SLOTS = 5


def _json(value):
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def exists(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name='forward_trial'").fetchone() is not None


def activate(con, now):
    """Scanner-only, once. Caller holds the cross-process write lock."""
    con.execute("CREATE TABLE IF NOT EXISTS forward_trial (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS forward_trial_events (id INTEGER PRIMARY KEY, setup_id TEXT NOT NULL, event TEXT NOT NULL, observed_at INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(setup_id,event))")
    con.execute("CREATE TABLE IF NOT EXISTS forward_trial_checks (id INTEGER PRIMARY KEY, checked_at INTEGER NOT NULL, payload TEXT NOT NULL)")
    con.execute("INSERT OR IGNORE INTO forward_trial VALUES (1,?)", (_json({
        "version": TRIAL_VERSION, "dependencies": DEPENDENCIES, "started_at": now,
        "watermark": con.execute("SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0],
        "starting_balance": str(STARTING_BALANCE), "risk_usd": str(RISK_USD),
        "max_slots": MAX_SLOTS, "timeframes": ["5m", "15m", "1H"],
        "cost_profiles": {v.key: costs.profile_for(s).payload() for s, v in
                          [("BTC-USD", venues.venue_for("BTC-USD")),
                           ("BTCUSDT", venues.venue_for("BTCUSDT")),
                           ("PF_XBTUSD", venues.venue_for("PF_XBTUSD"))]},
    }),))


def _event(con, sid, event, now, payload):
    con.execute("INSERT OR IGNORE INTO forward_trial_events(setup_id,event,observed_at,payload) VALUES (?,?,?,?)",
                (sid, event, now, _json(payload)))


def _records(con):
    records = {}
    for sid, event, observed, payload in con.execute(
            "SELECT setup_id,event,observed_at,payload FROM forward_trial_events ORDER BY id"):
        records.setdefault(sid, {})[event] = json.loads(payload)
    return records


def unresolved(con):
    if not exists(con):
        return set()
    return {(r["PLACED"]["symbol"], r["PLACED"]["tf"]) for r in _records(con).values()
            if "PLACED" in r and "CLOSED" not in r and "EXPIRED" not in r}


def _compatible(config):
    return (config["version"] == TRIAL_VERSION and config["dependencies"] == DEPENDENCIES
            and DEPENDENCIES == {"breakout": breakout.BREAKOUT_VERSION,
                                 "exec": execsim.EXEC_VERSION, "swing": swings.SWING_VERSION}
            and all(costs.by_version(p["version"]).payload() == p
                    for p in config["cost_profiles"].values()))


def _closed(con, symbol, tf, start, now):
    step = importer.TF_SECONDS[tf]
    return [dict(c) for c in store.get_candles(con, symbol, tf, start_ts=start,
                                              end_ts=now-step+1)]


def _advance(con, sid, record, now):
    p = record["PLACED"]
    step = importer.TF_SECONDS[p["tf"]]
    bars = [record[k] for k in sorted(record) if k.startswith("BAR:")]
    bars.sort(key=lambda b: b["open_ts"])
    expected = bars[-1]["open_ts"] + step if bars else p["warmup"][-1]["open_ts"]+step
    # Freeze only a contiguous prefix. Even acknowledged empty candles are
    # insufficient evidence for ordering a simulated stop and target.
    end = min(now, p["active_at"] + (execsim.MAX_BARS + 8) * step)
    for c in _closed(con, p["symbol"], p["tf"], expected, end):
        if c["open_ts"] != expected:
            break
        _event(con, sid, f"BAR:{expected}", now, c)
        bars.append(c)
        expected += step
    if not bars or bars[-1]["open_ts"] < p["active_at"]:
        return "Waiting for the next complete price candle." if now < expected+step else "Waiting for missing price data. No fill or result has been assumed."
    candles = p["warmup"] + bars
    offset = next(i for i, b in enumerate(candles) if b["open_ts"] == p["active_at"])
    atr = swings.compute_atr(candles)
    long = p["direction"] == "LONG"
    sl, tp = Decimal(p["sl"]), Decimal(p["tp"])
    profile = costs.by_version(p["cost_profile"])
    fill = record.get("FILLED")
    if not fill:
        entry_end = next((i for i, b in enumerate(candles) if b["open_ts"] >= p["expires_at"]), len(candles))
        # Entry slippage uses ATR known BEFORE the fill candle opened.
        prior_atr = [None] + atr[:-1]
        result = execsim.simulate_entry(candles[:entry_end], prior_atr[:entry_end], offset,
            Decimal(p["entry"]), sl, long, entry_model=p["entry_model"],
            maker_limit=Decimal(p["maker_limit"]), maker_wait=p["maker_wait_bars"], profile=profile)
        if result["status"] != "FILLED":
            if result["status"] == "MISSED" or expected >= p["expires_at"]:
                _event(con, sid, "EXPIRED", now, {"reason": "The entry window ended without a valid fill.", "at": p["expires_at"]})
                return None
            return "Waiting for missing price data." if expected+step <= now else "Waiting for the entry price."
        fi = result["fill_i"]
        if result["entry"]*Decimal(p["quantity"])*(1+profile.taker_rate) > Decimal(p["reserved_usd"]):
            _event(con, sid, "EXPIRED", now, {"reason": "The entry price rose beyond the trial's reserved cash.", "at": candles[fi]["open_ts"]})
            return None
        fill = {"entry": str(result["entry"]), "risk": str(result["risk"]),
                "entry_role": result["entry_role"], "at": candles[fi]["open_ts"],
                "note": result["note"], "actual_risk_usd": str(result["risk"]*Decimal(p["quantity"]))}
        # A late cross beyond the target is not a valid bracket.
        if (long and result["entry"] >= tp) or (not long and result["entry"] <= tp):
            _event(con, sid, "EXPIRED", now, {"reason": "Price moved beyond the target before entry.", "at": fill["at"]})
            return None
        _event(con, sid, "FILLED", now, fill)
    fi = next(i for i, b in enumerate(candles) if b["open_ts"] == fill["at"])
    exit_result = execsim.walk_exit(candles, fi, sl, tp, long)
    if exit_result:
        outcome, price, ei, ambiguous = exit_result
        entry, quantity = Decimal(fill["entry"]), Decimal(p["quantity"])
        settlement = execsim.settle(profile, p["symbol"], entry, price, Decimal(fill["risk"]),
            long, outcome, ei-fi+1, step, atr[ei], entry_role=fill["entry_role"])
        net_unit = ((settlement["eff_exit"]-entry) if long else (entry-settlement["eff_exit"])) - settlement["fees"] - settlement["funding"]
        pnl = net_unit * quantity
        _event(con, sid, "CLOSED", now, {"outcome": outcome, "at": candles[ei]["open_ts"]+step,
            "exit": str(settlement["eff_exit"]), "pnl_usd": str(pnl),
            "r_multiple": str(pnl/Decimal(p["risk_usd"])), "fees_usd": str(settlement["fees"]*quantity),
            "funding_usd": str(settlement["funding"]*quantity), "ambiguous": ambiguous,
            "slip_missing": settlement["slip_missing"]})
        return None
    return "Waiting for missing price data. The trade remains open." if expected+step <= now else "Trade open: watching its stop-loss and target."


def run(con, symbols, now=None):
    now = int(time.time()) if now is None else now
    if con.in_transaction:
        raise RuntimeError("Forward trial requires its own transaction")
    con.execute("BEGIN IMMEDIATE")
    try:
        activate(con, now)
        config = json.loads(con.execute("SELECT payload FROM forward_trial").fetchone()[0])
        if not _compatible(config):
            con.execute("INSERT INTO forward_trial_checks(checked_at,payload) VALUES (?,?)",
                        (now, _json({"paused": "Trial paused because its strategy or simulation rules changed.", "waiting": {}})))
            con.commit()
            return
        records = _records(con)
        waiting = {}
        for sid, r in records.items():
            if "PLACED" in r and not ({"CLOSED", "EXPIRED"} & r.keys()):
                note = _advance(con, sid, r, now)
                if note:
                    waiting[sid] = note
        records = _records(con)
        balance = Decimal(config["starting_balance"]) + sum(
            (Decimal(r["CLOSED"]["pnl_usd"]) for r in records.values() if "CLOSED" in r), Decimal(0))
        active = [r["PLACED"] for r in records.values() if "PLACED" in r and not ({"CLOSED", "EXPIRED"} & r.keys())]
        rows = con.execute("SELECT id,symbol,tf,confirmed_at,payload,content_hash FROM facts WHERE id>? AND kind='setup' AND algo_version=? ORDER BY id",
                           (config["watermark"], DEPENDENCIES["breakout"])).fetchall()
        for fid, symbol, tf, confirmed, raw, content_hash in rows:
            plan = json.loads(raw)
            sid = plan.get("setup_id") or f"invalid:{fid}"
            if sid in records:
                continue
            observed = {"symbol": symbol, "tf": tf, "observed_at": now, "source_id": fid,
                        "source_hash": content_hash, "confirmed_at": confirmed, "plan": plan}
            reason = None
            try:
                if tf not in config["timeframes"]:
                    raise ValueError("unsupported timeframe")
                step = importer.TF_SECONDS[tf]
                active_at = (now//step+1)*step
                expiry = int(plan["expires_at_ts"])
                entry, sl, tp, maker = [Decimal(plan[k]) for k in ("entry", "sl", "tp", "maker_limit")]
                long = plan["direction"] == "LONG"
                risk = entry-sl if long else sl-entry
                if not all(x.is_finite() and x > 0 for x in (entry, sl, tp, maker)) or risk <= 0:
                    raise ValueError("invalid prices")
                if plan["direction"] not in ("LONG", "SHORT") or not (sl < maker < entry < tp if long else tp < entry < maker < sl):
                    raise ValueError("invalid bracket")
                if plan["state"] != "VALIDATED" or plan["entry_model"] != "MAKER_THEN_MARKET":
                    raise ValueError("unsupported plan")
                wait = int(plan["maker_wait_bars"])
                if not 1 <= wait <= 4:
                    raise ValueError("invalid wait")
                quantity = Decimal(config["risk_usd"])/risk
                notional = quantity*entry
                warmup = _closed(con, symbol, tf, max(0, active_at-101*step), now)
                # Keep only the contiguous history immediately before activation.
                for i in range(len(warmup)-1, 0, -1):
                    if warmup[i]["open_ts"]-warmup[i-1]["open_ts"] != step:
                        warmup = warmup[i:]
                        break
                if confirmed < config["started_at"]:
                    reason = "This setup formed before the trial started."
                elif confirmed > now or now-confirmed > 3*step:
                    reason = "The setup arrived too late to test from fresh prices."
                elif symbol not in symbols:
                    reason = "This market is outside the current scan."
                elif expiry <= active_at:
                    reason = "The entry deadline passed before the trial could start watching."
                elif not long and not venues.venue_for(symbol).allow_shorts:
                    reason = "This market does not support short trades."
                elif len(warmup) < 15 or warmup[-1]["open_ts"]+step < now-step:
                    reason = "There is not enough recent, continuous price data."
                elif len(active) >= config["max_slots"]:
                    reason = "The trial already has five orders or trades open."
                elif any(p["symbol"] == symbol for p in active):
                    reason = "The trial is already watching a trade in this market."
                elif notional + sum((Decimal(p["reserved_usd"]) for p in active), Decimal(0)) > balance:
                    reason = "The trial has insufficient unreserved cash for this trade without borrowing."
                if not reason:
                    profile = config["cost_profiles"][venues.venue_for(symbol).key]
                    # Reserve an extra 2% for crossing price and modeled costs.
                    reserve = notional*Decimal("1.02")
                    if reserve + sum((Decimal(p["reserved_usd"]) for p in active), Decimal(0)) > balance:
                        reason = "The trial has insufficient cash after allowing for trading costs."
                    else:
                        placed = {**observed, **{k: plan[k] for k in ("entry", "sl", "tp", "direction", "maker_limit", "entry_model")},
                            # A fresh prospective execution window preserves the
                            # two passive candles AND the market fallback. The
                            # source deadline is checked above, never replayed.
                            "active_at": active_at, "expires_at": active_at+(wait+1)*step,
                            "source_expires_at": expiry, "maker_wait_bars": wait,
                            "quantity": str(quantity), "risk_usd": config["risk_usd"],
                            "reserved_usd": str(reserve), "warmup": warmup, "cost_profile": profile["version"]}
                        _event(con, sid, "PLACED", now, placed)
                        active.append(placed)
                        waiting[sid] = "Waiting for the next complete price candle."
            except (KeyError, ValueError, ArithmeticError, TypeError):
                reason = "The setup is missing valid prices or entry instructions."
            _event(con, sid, "OBSERVED", now, observed)
            if reason:
                _event(con, sid, "SKIPPED", now, {"reason": reason})
            records[sid] = {}
        con.execute("INSERT INTO forward_trial_checks(checked_at,payload) VALUES (?,?)", (now, _json({"waiting": waiting})))
        con.commit()
    except Exception:
        con.rollback()
        raise


def report(con, now=None):
    """Read-only, including before the scanner creates the trial."""
    if not exists(con):
        return {"state": "NOT_STARTED", "items": [], "note": "The trial starts on the scanner's next pass."}
    config = json.loads(con.execute("SELECT payload FROM forward_trial").fetchone()[0])
    check = con.execute("SELECT checked_at,payload FROM forward_trial_checks ORDER BY id DESC LIMIT 1").fetchone()
    status = json.loads(check[1]) if check else {}
    now = int(time.time()) if now is None else now
    if check and now-check[0] > 1800:
        status["paused"] = "Trial updates are delayed. Check the bot status; the last results are shown below."
    items, curve = [], [{"time": config["started_at"], "value": config["starting_balance"]}]
    for sid, r in _records(con).items():
        observed = r["OBSERVED"]
        p = r.get("PLACED", observed["plan"])
        closed = r.get("CLOSED", {})
        state = next((s for s in ("SKIPPED", "CLOSED", "EXPIRED", "FILLED", "PLACED") if s in r), "OBSERVED")
        items.append({"setup_id": sid, "symbol": observed["symbol"], "tf": observed["tf"],
            "observed_at": observed["observed_at"], "state": state,
            "entry": r.get("FILLED", {}).get("entry", p.get("entry")), "sl": p.get("sl"), "tp": p.get("tp"),
            "direction": p.get("direction"), "active_at": p.get("active_at"),
            "reason": r.get("SKIPPED", r.get("EXPIRED", {})).get("reason") or status.get("waiting", {}).get(sid),
            "fill": r.get("FILLED"), "result": closed or None, "pnl_usd": closed.get("pnl_usd")})
    balance = Decimal(config["starting_balance"])
    for item in sorted((i for i in items if i["result"]), key=lambda i: i["result"]["at"]):
        balance += Decimal(item["pnl_usd"])
        curve.append({"time": item["result"]["at"], "value": str(balance)})
    return {"state": "PAUSED" if status.get("paused") else "COLLECTING", "note": status.get("paused"),
        "started_at": config["started_at"], "checked_at": check[0] if check else None,
        "starting_balance": config["starting_balance"], "balance": str(balance),
        "pnl_usd": str(balance-Decimal(config["starting_balance"])), "risk_usd": config["risk_usd"],
        "max_slots": config["max_slots"], "curve": curve,
        "counts": {s: sum(i["state"] == s for i in items) for s in ("PLACED", "FILLED", "CLOSED", "SKIPPED", "EXPIRED")},
        "items": sorted(items, key=lambda i: i["observed_at"], reverse=True)[:100]}
