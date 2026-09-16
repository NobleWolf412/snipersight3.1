"""Prospective paired stop study. Read source fills; write only our own ledger.

Rules are declared before enrollment. All arms use the SAME fill, size, target,
cost model and contiguous frozen candles. No arm changes an account order.
"""
import json
import time
from decimal import Decimal

from . import costs, execution, execsim, forwardtrial, importer, store, swings

STOP_STUDY_VERSION = "stop-study-v0.1-draft"
# Frozen on purpose — see forwardtrial.DEPENDENCIES. S54 moved exec.
DEPENDENCIES = {"exec": "exec-v0.28-draft", "swing": "swing-v0.11-draft",
                "execution": "execution-core-v0.10-draft", "forwardtrial": "forward-trial-v0.1-draft"}
RULES = {"HOLD": "Original stop", "COST_COVER": "Cover costs after +1R",
         "STRUCTURE": "Follow confirmed swings"}


def _json(value):
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def _has(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None


def exists(con):
    return _has(con, "stop_study")


def _maxid(con, table):
    return con.execute(f"SELECT COALESCE(MAX(id),0) FROM {table}").fetchone()[0] if _has(con, table) else 0


def _event(con, key, event, now, payload):
    con.execute("INSERT OR IGNORE INTO stop_study_events(trade_key,event,observed_at,payload) VALUES (?,?,?,?)",
                (key, event, now, _json(payload)))


def _records(con, key=None):
    if not exists(con):
        return {}
    records = {}
    query = "SELECT trade_key,event,payload FROM stop_study_events"
    for k, event, payload in con.execute(query + (" WHERE trade_key=?" if key else "") + " ORDER BY id", (key,) if key else ()):
        records.setdefault(k, {})[event] = json.loads(payload)
    return records


def _finished(record):
    return "EXCLUDED" in record or all("RESULT:"+r in record for r in RULES)


def unresolved(con):
    return {(r["ENROLLED"]["symbol"], r["ENROLLED"]["tf"]) for r in _records(con).values()
            if "ENROLLED" in r and not _finished(r)}


def _dependencies():
    return {"exec": execsim.EXEC_VERSION, "swing": swings.SWING_VERSION,
            "execution": execution.EXECUTION_CORE_VERSION, "forwardtrial": forwardtrial.TRIAL_VERSION}


def _activate(con, now):
    con.execute("CREATE TABLE IF NOT EXISTS stop_study(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS stop_study_events(id INTEGER PRIMARY KEY,trade_key TEXT NOT NULL,event TEXT NOT NULL,observed_at INTEGER NOT NULL,payload TEXT NOT NULL,UNIQUE(trade_key,event))")
    con.execute("CREATE TABLE IF NOT EXISTS stop_study_checks(id INTEGER PRIMARY KEY,checked_at INTEGER NOT NULL,payload TEXT NOT NULL)")
    con.execute("INSERT OR IGNORE INTO stop_study VALUES (1,?)", (_json({
        "version": STOP_STUDY_VERSION, "dependencies": DEPENDENCIES, "started_at": now,
        "outbox_watermark": _maxid(con, "execution_outbox"),
        "trial_watermark": _maxid(con, "forward_trial_events"),
        "profiles": {costs.profile_for(s).version: costs.profile_for(s).payload()
                     for s in ("BTC-USD", "BTCUSDT", "PF_XBTUSD")}}),))


def _compatible(config):
    return (config["version"] == STOP_STUDY_VERSION and config["dependencies"] == DEPENDENCIES
            and DEPENDENCIES == _dependencies()
            and all(costs.by_version(v).payload() == p for v, p in config["profiles"].items()))


def _enroll(con, config, records, now):
    candidates = []
    if _has(con, "execution_outbox"):
        for iid, raw, created in con.execute("SELECT intent_id,payload,created_at FROM execution_outbox WHERE id>? AND mode='PAPER' AND origin='BOT' ORDER BY id",
                                             (config["outbox_watermark"],)):
            p = json.loads(raw).get("intent", {})
            candidates.append(("paper:"+iid, {"source": "PAPER", "source_id": iid,
                "created_at": created, "symbol": p.get("symbol"), "tf": p.get("timeframe"),
                "direction": p.get("direction"), "stop": p.get("stop"),
                "target": (p.get("targets") or [None])[0], "max_bars": execution.PAPER_MAX_HOLDING_BARS,
                "strategy": json.loads(raw).get("strategy_version"), "plan": p}))
    if _has(con, "forward_trial_events"):
        for sid, raw, observed in con.execute("SELECT setup_id,payload,observed_at FROM forward_trial_events WHERE id>? AND event='PLACED' ORDER BY id",
                                              (config["trial_watermark"],)):
            p = json.loads(raw)
            candidates.append(("breakout:"+sid, {"source": "BREAKOUT_TRIAL", "source_id": sid,
                "created_at": observed, "symbol": p["symbol"], "tf": p["tf"], "direction": p["direction"],
                "stop": p["sl"], "target": p["tp"], "max_bars": execsim.MAX_BARS,
                "strategy": "BREAKOUT_RETEST", "plan": p}))
    for key, p in candidates:
        if key in records:
            continue
        reason = None
        try:
            if p["created_at"] < config["started_at"]:
                reason = "This order predates the comparison."
            if p["tf"] not in importer.TF_SECONDS or p["direction"] not in ("LONG", "SHORT"):
                raise ValueError("Unreadable trade direction or timeframe.")
            stop = Decimal(p["stop"])
            if not stop.is_finite() or stop <= 0:
                raise ValueError("The original stop is unavailable.")
            if p["target"] is not None and (not Decimal(p["target"]).is_finite() or Decimal(p["target"]) <= 0):
                raise ValueError("The original target is unavailable.")
            profile = costs.profile_for(p["symbol"])
            if profile.version not in config["profiles"]:
                raise ValueError("This cost profile was not part of the comparison at activation.")
            p["cost_profile"] = profile.version
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            reason = str(exc)
        _event(con, key, "ENROLLED", now, p)
        if reason:
            _event(con, key, "EXCLUDED", now, {"reason": reason})


def _source_fill(con, p):
    if p["source"] == "PAPER":
        row = con.execute("SELECT o.controller,o.grade_eligible,o.state,p.entry,p.quantity,p.filled_at,p.entry_role FROM execution_outbox o LEFT JOIN paper_positions p USING(intent_id) WHERE o.intent_id=?",
                          (p["source_id"],)).fetchone()
        if not row:
            return None, "The source trade is no longer available."
        controller, eligible, state, entry, quantity, at, role = row
        if controller != "BOT" or not eligible:
            return None, "Manually adjusted trades are excluded from the paired comparison."
        if entry is None:
            return (None, "The order ended without a fill.") if state in ("PAPER_CLOSED", "PAPER_EXPIRED", "CANCELLED", "RISK_REJECTED", "SUBMIT_FAILED", "HELD_OFF", "REJECTED", "CLOSED", "ORDER_LIFECYCLE_COMPLETE") else (None, None)
        if role not in ("MAKER", "TAKER"):
            return None, "The recorded entry fee type is unavailable."
        return {"entry": entry, "quantity": quantity, "at": at, "entry_role": role}, None
    rows = {e: json.loads(raw) for e, raw in con.execute(
        "SELECT event,payload FROM forward_trial_events WHERE setup_id=? AND event IN ('FILLED','EXPIRED')", (p["source_id"],))}
    if "EXPIRED" in rows:
        return None, "The trial order ended without a fill."
    if "FILLED" not in rows:
        return None, None
    return {**rows["FILLED"], "quantity": p["plan"]["quantity"]}, None


def _warmup(con, p, at):
    step = importer.TF_SECONDS[p["tf"]]
    candles = [dict(c) for c in store.get_candles(con, p["symbol"], p["tf"],
                start_ts=max(0, at-100*step), end_ts=at)]
    if not candles or candles[-1]["open_ts"]+step != at:
        return []
    for i in range(len(candles)-1, -1, -1):
        if not _valid_candle(candles[i]):
            candles = candles[i+1:]
            break
    for i in range(len(candles)-1, 0, -1):
        if candles[i]["open_ts"]-candles[i-1]["open_ts"] != step:
            return candles[i:]
    return candles


def _valid_candle(candle):
    try:
        o, h, l, c = (Decimal(candle[k]) for k in ("open", "high", "low", "close"))
        return all(v.is_finite() and v > 0 for v in (o, h, l, c)) and l <= min(o, c) <= max(o, c) <= h
    except (KeyError, TypeError, ArithmeticError):
        return False


def _cost_stop(profile, p, fill, atr, bars_held):
    """Stop trigger that approximately covers both fees, funding and slippage."""
    entry = Decimal(fill["entry"])
    risk = abs(entry-Decimal(p["stop"]))
    long = p["direction"] == "LONG"
    st = execsim.settle(profile, p["symbol"], entry, entry, risk, long, "SL",
        bars_held, importer.TF_SECONDS[p["tf"]], atr, entry_role=fill["entry_role"])
    entry_fee = profile.maker_rate if fill["entry_role"] == "MAKER" else profile.taker_rate
    if long:
        return (entry*(1+entry_fee)+st["funding"])/(1-profile.taker_rate)+st["slip"]
    return (entry*(1-entry_fee)-st["funding"])/(1+profile.taker_rate)-st["slip"]


def simulate(p, fill, bars):
    """Pure paired walk. Every stop adjustment follows the exit check."""
    candles = fill["warmup"]+bars
    start = len(fill["warmup"])
    atr = swings.compute_atr(candles)
    entry, quantity, original = Decimal(fill["entry"]), Decimal(fill["quantity"]), Decimal(p["stop"])
    long = p["direction"] == "LONG"
    risk = abs(entry-original)
    tp = Decimal(p["target"]) if p["target"] is not None else (Decimal("Infinity") if long else Decimal("-Infinity"))
    profile = costs.by_version(p["cost_profile"])
    arms = {r: {"stop": original, "moves": [], "result": None, "cost_estimate_missing": False} for r in RULES}
    previous_pivot = None
    # Seed only pivots already confirmed before the entry candle.
    for j in range(4, start):
        pivot = _pivot(candles, j, long)
        if pivot is not None:
            previous_pivot = pivot
    for j in range(start, len(candles)):
        c = candles[j]
        held = j-start
        hi, lo, opening = (Decimal(c[k]) for k in ("high", "low", "open"))
        pivot = _pivot(candles, j, long) if j >= 4 else None
        is_better_pivot = pivot is not None and previous_pivot is not None and (pivot > previous_pivot if long else pivot < previous_pivot)
        for rule, arm in arms.items():
            if arm["result"]:
                continue
            stop = arm["stop"]
            hit_stop = lo <= stop if long else hi >= stop
            hit_target = hi >= tp if long else lo <= tp
            if hit_stop or hit_target or held+1 >= p["max_bars"]:
                outcome = "SL" if hit_stop else "TP" if hit_target else "TIMEOUT"
                price = execsim.stop_gap_fill(stop, opening, long) if hit_stop and held > 0 else stop if hit_stop else tp if hit_target else Decimal(c["close"])
                # Full-candle holding convention shared by every arm. This is
                # a simulated baseline, not a replacement for recorded P&L.
                st = execsim.settle(profile, p["symbol"], entry, price, risk, long, outcome,
                    held+1, importer.TF_SECONDS[p["tf"]], atr[j], entry_role=fill["entry_role"])
                net = ((st["eff_exit"]-entry) if long else (entry-st["eff_exit"]))-st["fees"]-st["funding"]
                arm["result"] = {"outcome": outcome, "at": c["open_ts"], "exit": str(st["eff_exit"]),
                    "pnl_usd": str(net*quantity), "r_multiple": str(net/risk),
                    "fees_usd": str(st["fees"]*quantity), "funding_usd": str(st["funding"]*quantity),
                    "slip_missing": st["slip_missing"], "ambiguous": hit_stop and hit_target,
                    "cost_estimate_missing": arm["cost_estimate_missing"]}
                continue
            candidate = None
            if rule == "COST_COVER" and held > 0 and not arm["moves"] and (hi-entry >= risk if long else entry-lo >= risk):
                if atr[j] is not None:
                    candidate = _cost_stop(profile, p, fill, atr[j], held+2)
                else:
                    arm["cost_estimate_missing"] = True
            elif rule == "STRUCTURE" and is_better_pivot:
                candidate = pivot
            if candidate is not None and (stop < candidate < tp if long else tp < candidate < stop):
                arm["stop"] = candidate
                arm["moves"].append({"at": c["open_ts"]+importer.TF_SECONDS[p["tf"]],
                                     "confirmed_at": c["open_ts"]+importer.TF_SECONDS[p["tf"]],
                                     "price": str(candidate)})
        if pivot is not None:
            previous_pivot = pivot
    return arms


def _pivot(candles, j, long):
    field = "low" if long else "high"
    middle = Decimal(candles[j-2][field])
    others = [Decimal(candles[i][field]) for i in (j-4, j-3, j-1, j)]
    return middle if (all(middle < x for x in others) if long else all(middle > x for x in others)) else None


def _advance(con, key, r, now):
    p = r["ENROLLED"]
    current, reason = _source_fill(con, p)
    if reason:
        _event(con, key, "EXCLUDED", now, {"reason": reason})
        return reason
    fill = r.get("FILL")
    if fill is None:
        if current is None:
            return "Waiting for the source order to fill."
        try:
            entry, quantity, stop = Decimal(current["entry"]), Decimal(current["quantity"]), Decimal(p["stop"])
            risk = entry-stop if p["direction"] == "LONG" else stop-entry
            valid = all(v.is_finite() and v > 0 for v in (entry, quantity, stop, risk)) and current["at"] >= p["created_at"]
        except (KeyError, TypeError, ArithmeticError):
            valid = False
        if not valid:
            _event(con, key, "EXCLUDED", now, {"reason": "The recorded fill is not suitable for a prospective comparison."})
            return None
        fill = {**current, "warmup": _warmup(con, p, current["at"])}
        _event(con, key, "FILL", now, fill)
    bars = sorted((v for k, v in r.items() if k.startswith("BAR:")), key=lambda c: c["open_ts"])
    step = importer.TF_SECONDS[p["tf"]]
    expected = bars[-1]["open_ts"]+step if bars else fill["at"]
    end = min(now-step+1, fill["at"]+p["max_bars"]*step)
    frozen_trial = {}
    if p["source"] == "BREAKOUT_TRIAL":
        # Prefer the source trial's frozen evidence over later revised imports.
        frozen_trial = {b["open_ts"]: b for (raw,) in con.execute("SELECT payload FROM forward_trial_events WHERE setup_id=? AND event LIKE 'BAR:%'", (p["source_id"],)) for b in [json.loads(raw)]}
    available = {c["open_ts"]: dict(c) for c in store.get_candles(con, p["symbol"], p["tf"], start_ts=expected, end_ts=end)}
    available.update({ts: c for ts, c in frozen_trial.items() if expected <= ts < end})
    invalid = False
    for ts in sorted(available):
        c = available[ts]
        if c["open_ts"] != expected:
            break
        if not _valid_candle(c):
            invalid = True
            break
        _event(con, key, f"BAR:{expected}", now, c)
        bars.append(c)
        expected += step
    if not bars:
        return "Invalid price data is holding up this comparison." if invalid else "Waiting for complete price data after the fill."
    arms = simulate(p, fill, bars)
    for rule, arm in arms.items():
        for move in arm["moves"]:
            _event(con, key, f"MOVE:{rule}:{move['at']}", now, move)
        if arm["result"]:
            _event(con, key, "RESULT:"+rule, now, arm["result"])
    if all(a["result"] for a in arms.values()):
        return None
    if invalid:
        return "Invalid price data is holding up this comparison."
    return "Missing price candles are holding up this comparison." if expected+step <= now else "Following the remaining simulated stops."


def run(con, now=None):
    now = int(time.time()) if now is None else now
    if con.in_transaction:
        raise RuntimeError("Stop study requires its own transaction")
    con.execute("BEGIN IMMEDIATE")
    try:
        _activate(con, now)
        config = json.loads(con.execute("SELECT payload FROM stop_study").fetchone()[0])
        notes = {}
        paused = None
        if not _compatible(config):
            paused = "The comparison is paused because its simulation rules changed."
        else:
            _enroll(con, config, _records(con), now)
            for key, record in _records(con).items():
                if not _finished(record):
                    note = _advance(con, key, record, now)
                    if note:
                        notes[key] = note
        con.execute("INSERT INTO stop_study_checks(checked_at,payload) VALUES (?,?)", (now, _json({"paused": paused, "notes": notes})))
        con.commit()
    except Exception:
        con.rollback()
        raise


def _item(key, record, note=None):
    p = record["ENROLLED"]
    results = {rule: record.get("RESULT:"+rule) for rule in RULES}
    complete = all(results.values())
    incomplete_costs = complete and any(r.get("slip_missing") or r.get("cost_estimate_missing") for r in results.values())
    paired = complete and not incomplete_costs and "EXCLUDED" not in record
    return {"key": key, "source": p["source"], "symbol": p["symbol"], "tf": p["tf"],
        "created_at": p["created_at"], "direction": p["direction"], "paired": paired,
        "state": "EXCLUDED" if "EXCLUDED" in record or incomplete_costs else "COMPLETE" if paired else "OPEN" if "FILL" in record else "WAITING",
        "note": record.get("EXCLUDED", {}).get("reason") or ("Excluded from totals because a cost estimate was unavailable." if incomplete_costs else note), "results": results,
        "fill": {k: v for k, v in record.get("FILL", {}).items() if k != "warmup"},
        "moves": {rule: [v for k, v in record.items() if k.startswith("MOVE:"+rule+":")] for rule in RULES}}


def report(con, now=None, key=None):
    if not exists(con):
        return {"state": "NOT_STARTED", "items": [], "rules": RULES,
                "note": "The stop comparison starts on the next scanner pass."}
    now = int(time.time()) if now is None else now
    config = json.loads(con.execute("SELECT payload FROM stop_study").fetchone()[0])
    check = con.execute("SELECT checked_at,payload FROM stop_study_checks ORDER BY id DESC LIMIT 1").fetchone()
    check_data = json.loads(check[1]) if check else {}
    records = _records(con, key)
    items = [_item(k, r, check_data.get("notes", {}).get(k)) for k, r in records.items()]
    paired = [i for i in items if i["paired"]]
    totals = {}
    for rule in RULES:
        total = sum((Decimal(i["results"][rule]["pnl_usd"]) for i in paired), Decimal(0))
        baseline = sum((Decimal(i["results"]["HOLD"]["pnl_usd"]) for i in paired), Decimal(0))
        totals[rule] = {"pnl_usd": str(total), "difference_usd": str(total-baseline),
                        "better": sum(Decimal(i["results"][rule]["pnl_usd"]) > Decimal(i["results"]["HOLD"]["pnl_usd"]) for i in paired),
                        "worse": sum(Decimal(i["results"][rule]["pnl_usd"]) < Decimal(i["results"]["HOLD"]["pnl_usd"]) for i in paired)}
    paused = check_data.get("paused")
    if check and now-check[0] > 1800:
        paused = "Comparison updates are delayed. The last recorded results are shown."
    return {"state": "PAUSED" if paused else "COLLECTING", "note": paused, "rules": RULES,
        "started_at": config["started_at"], "checked_at": check[0] if check else None,
        "paired_count": len(paired), "pending_count": sum(i["state"] in ("WAITING", "OPEN") for i in items),
        "excluded_count": sum(i["state"] == "EXCLUDED" for i in items), "totals": totals,
        "items": sorted(items, key=lambda i: i["created_at"], reverse=True)[:100]}
