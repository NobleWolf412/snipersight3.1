"""Prospective paired stop study. Read source fills; write only our own ledger.

Rules are declared before enrollment. All arms use the SAME fill, size, target,
cost model and contiguous frozen candles. No arm changes an account order.
"""
import json
import time
from decimal import Decimal

from . import costs, execution, execsim, forwardtrial, importer, store, swings

ZONE_STUDY_VERSION = "zone-study-v0.5-draft"
# New-cohort dependencies only; existing configs stay frozen and pause.
DEPENDENCIES = {"exec": "exec-v0.30-draft", "swing": "swing-v0.11-draft",
                "execution": "execution-core-v0.15-draft", "forwardtrial": "forward-trial-v0.2-draft"}
MANAGEMENT = {"15m": "5m", "1H": "15m", "4H": "1H"}
RULES = {"HOLD": "Original stop", "SWING_IDEAL": "Swing trail - candle close",
         "SWING_OBSERVED": "Swing trail - scanner timing", "ZONE_IDEAL": "Defended zone - candle close",
         "ZONE_OBSERVED": "Defended zone - scanner timing"}


def _json(value):
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def _has(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None


def exists(con):
    return _has(con, "zone_study")


def _maxid(con, table):
    return con.execute(f"SELECT COALESCE(MAX(id),0) FROM {table}").fetchone()[0] if _has(con, table) else 0


def _event(con, key, event, now, payload):
    con.execute("INSERT OR IGNORE INTO zone_study_events(trade_key,event,observed_at,payload) VALUES (?,?,?,?)",
                (key, event, now, _json(payload)))


def _records(con, key=None):
    if not exists(con):
        return {}
    records = {}
    query = "SELECT trade_key,event,payload FROM zone_study_events"
    for k, event, payload in con.execute(query + (" WHERE trade_key=?" if key else "") + " ORDER BY id", (key,) if key else ()):
        records.setdefault(k, {})[event] = json.loads(payload)
    return records


def _finished(record):
    return "EXCLUDED" in record or all("RESULT:"+r in record for r in RULES)


def unresolved(con):
    return {(r["ENROLLED"]["symbol"], tf) for r in _records(con).values()
            if "ENROLLED" in r and not _finished(r)
            for tf in (r["ENROLLED"]["tf"], r["ENROLLED"].get("management_tf", r["ENROLLED"]["tf"]))}


def _dependencies():
    return {"exec": execsim.EXEC_VERSION, "swing": swings.SWING_VERSION,
            "execution": execution.EXECUTION_CORE_VERSION, "forwardtrial": forwardtrial.TRIAL_VERSION}


def _activate(con, now):
    con.execute("CREATE TABLE IF NOT EXISTS zone_study(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS zone_study_events(id INTEGER PRIMARY KEY,trade_key TEXT NOT NULL,event TEXT NOT NULL,observed_at INTEGER NOT NULL,payload TEXT NOT NULL,UNIQUE(trade_key,event))")
    con.execute("CREATE TABLE IF NOT EXISTS zone_study_checks(id INTEGER PRIMARY KEY,checked_at INTEGER NOT NULL,payload TEXT NOT NULL)")
    con.execute("INSERT OR IGNORE INTO zone_study VALUES (1,?)", (_json({
        "version": ZONE_STUDY_VERSION, "dependencies": DEPENDENCIES, "started_at": now,
        "outbox_watermark": _maxid(con, "execution_outbox"),
        "trial_watermark": _maxid(con, "forward_trial_events"),
        "profiles": {costs.profile_for(s).version: costs.profile_for(s).payload()
                     for s in ("BTC-USD", "BTCUSDT", "PF_XBTUSD")}}),))


def _compatible(config):
    return (config["version"] == ZONE_STUDY_VERSION and config["dependencies"] == DEPENDENCIES
            and DEPENDENCIES == _dependencies()
            and all(costs.by_version(v).payload() == p for v, p in config["profiles"].items()))


def _enroll(con, config, records, now):
    candidates = []
    if _has(con, "execution_outbox"):
        for iid, raw, created, setup_id in con.execute("SELECT intent_id,payload,created_at,setup_id FROM execution_outbox WHERE id>? AND mode='PAPER' AND origin='BOT' ORDER BY id",
                                             (config["outbox_watermark"],)):
            p = json.loads(raw).get("intent", {})
            candidates.append(("paper:"+iid, {"source": "PAPER", "source_id": iid,
                "created_at": created, "symbol": p.get("symbol"), "tf": p.get("timeframe"),
                "direction": p.get("direction"), "stop": p.get("stop"),
                "target": (p.get("targets") or [None])[0], "max_bars": execution.PAPER_MAX_HOLDING_BARS,
                "strategy": setup_id.split("|")[2] if setup_id and len(setup_id.split("|")) >= 4 else None, "plan": p}))
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
            if p["tf"] not in MANAGEMENT or p["direction"] not in ("LONG", "SHORT"):
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
            p["management_tf"] = MANAGEMENT[p["tf"]]
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
    step = importer.TF_SECONDS[p["management_tf"]]
    candles = [dict(c) for c in store.get_candles(con, p["symbol"], p["management_tf"],
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


def _pivot(candles, j, low):
    if j < 4:
        return None
    field = "low" if low else "high"
    value = Decimal(candles[j-2][field])
    neighbors = [Decimal(candles[i][field]) for i in (j-4, j-3, j-1, j)]
    return value if (all(value < n for n in neighbors) if low else all(value > n for n in neighbors)) else None


def simulate(p, fill, bars):
    """Frozen management candles, five paths; observation time never backdates a move.

    Parent entry candle is ambiguous: stop touches count, target-only touches
    do not. No trail decision is permitted until the entire parent candle ends.
    """
    candles = fill["warmup"] + bars
    start = len(fill["warmup"])
    atr = swings.compute_atr(candles)
    step = importer.TF_SECONDS[p["management_tf"]]
    parent = importer.TF_SECONDS[p["tf"]]
    entry_at = int(fill["at"])
    parent_open = entry_at // parent * parent
    deadline = parent_open + p["max_bars"] * parent
    entry, qty, original = map(Decimal, (fill["entry"], fill["quantity"], p["stop"]))
    long = p["direction"] == "LONG"
    risk = abs(entry-original)
    target = Decimal(p["target"]) if p["target"] is not None else (Decimal("Infinity") if long else Decimal("-Infinity"))
    profile = costs.by_version(p["cost_profile"])
    arms = {r: {"stop": original, "moves": [], "result": None, "pending": [], "diagnostics": []} for r in RULES}
    events = []
    previous = None
    broken_swing = None
    swing = None
    zone = None
    for j, c in enumerate(candles):
        if all(a["result"] for a in arms.values()):
            break
        ts = c["open_ts"]
        close_at = ts+step
        lo, hi, opening, close = (Decimal(c[k]) for k in ("low", "high", "open", "close"))
        trailing_pivot = _pivot(candles, j, long)
        break_pivot = _pivot(candles, j, not long)
        if j < start:
            if trailing_pivot is not None:
                previous = trailing_pivot
            if break_pivot is not None:
                swing = (break_pivot, close_at)
            continue
        observed = max(close_at, int(c.get("observed_at", close_at)))
        eligible = ts >= parent_open+parent
        candidates = {}
        # A pivot must be confirmed before this candle begins to be broken.
        if eligible:
            if trailing_pivot is not None and previous is not None and (trailing_pivot > previous if long else trailing_pivot < previous):
                if atr[j] is not None:
                    candidates["SWING"] = trailing_pivot + (-1 if long else 1)*Decimal("0.25")*atr[j]
            if zone:
                age = (ts-zone["break_open"])//step
                if (lo < Decimal(zone["low"]) if long else hi > Decimal(zone["high"])):
                    events.append({**zone, "kind": "BROKE", "at": close_at, "observed_at": observed})
                    zone = None
                elif (lo <= Decimal(zone["high"]) and hi >= Decimal(zone["low"]) and (close > Decimal(zone["high"]) if long else close < Decimal(zone["low"]))):
                    events.append({**zone, "kind": "DEFENDED", "at": close_at, "observed_at": observed})
                    if atr[j] is not None:
                        candidates["ZONE"] = Decimal(zone["low"] if long else zone["high"]) + (-1 if long else 1)*Decimal("0.25")*atr[j]
                    else:
                        events.append({"kind": "NO_ATR", "at": close_at, "observed_at": observed})
                    zone = None
                elif age >= 12:
                    events.append({**zone, "kind": "EXPIRED", "at": close_at, "observed_at": observed})
                    zone = None
            crosses = swing and swing != broken_swing and swing[1] <= ts and (close > swing[0] if long else close < swing[0])
            strong = j > 0 and atr[j-1] is not None and abs(close-opening) >= atr[j-1] and (close > opening if long else close < opening)
            if crosses and strong:
                broken_swing = swing
                source = next((candles[k] for k in range(j-1, max(-1,j-6), -1)
                               if (Decimal(candles[k]["close"]) < Decimal(candles[k]["open"]) if long else Decimal(candles[k]["close"]) > Decimal(candles[k]["open"]))), None)
                if source and (close > Decimal(source["high"]) if long else close < Decimal(source["low"])):
                    if zone:
                        events.append({**zone, "kind": "REPLACED", "at": close_at, "observed_at": observed})
                    zone = {"low": source["low"], "high": source["high"], "source_at": source["open_ts"], "detected_at": close_at, "break_open": ts}
                    events.append({**zone, "kind": "FORMED", "at": close_at, "observed_at": observed})
                else:
                    events.append({"kind": "NO_SOURCE", "at": close_at, "observed_at": observed})
        for rule, arm in arms.items():
            if arm["result"]:
                continue
            due = [m for m in arm["pending"] if m["at"] <= ts]
            arm["pending"] = [m for m in arm["pending"] if m["at"] > ts]
            for move in due:
                candidate = Decimal(move["price"])
                improves = candidate > arm["stop"] if long else candidate < arm["stop"]
                if not improves:
                    continue
                if rule.endswith("OBSERVED") and (opening <= candidate if long else opening >= candidate):
                    arm["diagnostics"].append({"kind": "MISSED", "at": ts, "price": str(candidate), "reason": "Price had already crossed the proposed stop when the scanner could apply it."})
                    continue
                arm["stop"] = candidate
                if arm["moves"] and arm["moves"][-1]["at"] == move["at"]:
                    arm["moves"][-1] = move
                else:
                    arm["moves"].append(move)
            stop = arm["stop"]
            hit_stop = lo <= stop if long else hi >= stop
            hit_target = eligible and (hi >= target if long else lo <= target)
            timeout = close_at >= deadline
            if hit_stop or hit_target or timeout:
                outcome = "SL" if hit_stop else "TP" if hit_target else "TIMEOUT"
                price = execsim.stop_gap_fill(stop, opening, long) if hit_stop and eligible else stop if hit_stop else target if hit_target else close
                held = max(1, (close_at-parent_open)//step)
                st = execsim.settle(profile, p["symbol"], entry, price, risk, long, outcome, held, step, atr[j], entry_role=fill["entry_role"])
                net = (st["eff_exit"]-entry if long else entry-st["eff_exit"])-st["fees"]-st["funding"]
                arm["result"] = {"at": ts, "outcome": outcome, "exit": str(st["eff_exit"]), "pnl_usd": str(net*qty), "r_multiple": str(net/risk), "fees_usd": str(st["fees"]*qty), "funding_usd": str(st["funding"]*qty), "slip_missing": st["slip_missing"], "ambiguous": hit_stop and (hi >= target if long else lo <= target), "parent_fill_ambiguous": not eligible}
                continue
            family = rule.split("_")[0]
            candidate = candidates.get(family)
            if candidate is None:
                continue
            if not (stop < candidate < min(close,target) if long else max(close,target) < candidate < stop):
                arm["diagnostics"].append({"kind": "NO_TIGHTEN", "at": close_at, "reason": "The proposed level would not tighten the stop safely."})
                continue
            effective = close_at if rule.endswith("IDEAL") else (observed//step+1)*step
            arm["pending"].append({"at": effective, "confirmed_at": close_at, "observed_at": observed, "price": str(candidate)})
        if trailing_pivot is not None:
            previous = trailing_pivot
        if break_pivot is not None:
            swing = (break_pivot, close_at)
    for arm in arms.values():
        arm["zones"] = events
    return arms


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
        fill = {**current, "warmup": _warmup(con, p, current["at"]//importer.TF_SECONDS[p["tf"]]*importer.TF_SECONDS[p["tf"]])}
        if len(fill["warmup"]) < 15:
            _event(con, key, "EXCLUDED", now, {"reason": "Not enough contiguous smaller-candle history to compare the stop rules fairly."})
            return None
        _event(con, key, "FILL", now, fill)
    bars = sorted((v for k, v in r.items() if k.startswith("BAR:")), key=lambda c: c["open_ts"])
    step = importer.TF_SECONDS[p["management_tf"]]
    expected = bars[-1]["open_ts"]+step if bars else fill["at"]//importer.TF_SECONDS[p["tf"]]*importer.TF_SECONDS[p["tf"]]
    end = min(now-step+1, fill["at"]//importer.TF_SECONDS[p["tf"]]*importer.TF_SECONDS[p["tf"]]+p["max_bars"]*importer.TF_SECONDS[p["tf"]])
    # Source trials freeze parent bars; those cannot substitute for management bars.
    available = {c["open_ts"]: dict(c) for c in store.get_candles(con, p["symbol"], p["management_tf"], start_ts=expected, end_ts=end)}
    invalid = False
    for ts in sorted(available):
        c = available[ts]
        if c["open_ts"] != expected:
            break
        if not _valid_candle(c):
            invalid = True
            break
        c["observed_at"] = now
        _event(con, key, f"BAR:{expected}", now, c)
        bars.append(c)
        expected += step
    if not bars:
        return "Invalid price data is holding up this comparison." if invalid else "Waiting for complete price data after the fill."
    arms = simulate(p, fill, bars)
    for event in arms["HOLD"]["zones"]:
        _event(con, key, f"ZONE:{event['kind']}:{event['at']}", now, event)
    for rule, arm in arms.items():
        for diagnostic in arm["diagnostics"]:
            _event(con, key, f"NOTE:{rule}:{diagnostic['kind']}:{diagnostic['at']}", now, diagnostic)
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
        raise RuntimeError("Zone study requires its own transaction")
    con.execute("BEGIN IMMEDIATE")
    try:
        _activate(con, now)
        config = json.loads(con.execute("SELECT payload FROM zone_study").fetchone()[0])
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
        con.execute("INSERT INTO zone_study_checks(checked_at,payload) VALUES (?,?)", (now, _json({"paused": paused, "notes": notes})))
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
        "management_tf": p.get("management_tf"), "strategy": p.get("strategy"),
        "zones": [v for k, v in record.items() if k.startswith("ZONE:")],
        "diagnostics": [{"rule": k.split(":")[1], **v} for k, v in record.items() if k.startswith("NOTE:")],
        "state": "EXCLUDED" if "EXCLUDED" in record or incomplete_costs else "COMPLETE" if paired else "OPEN" if "FILL" in record else "WAITING",
        "note": record.get("EXCLUDED", {}).get("reason") or ("Excluded from totals because a cost estimate was unavailable." if incomplete_costs else note), "results": results,
        "fill": {k: v for k, v in record.get("FILL", {}).items() if k != "warmup"},
        "moves": {rule: [v for k, v in record.items() if k.startswith("MOVE:"+rule+":")] for rule in RULES}}


def report(con, now=None, key=None):
    if not exists(con):
        return {"state": "NOT_STARTED", "items": [], "rules": RULES,
                "note": "The stop comparison starts on the next scanner pass."}
    now = int(time.time()) if now is None else now
    config = json.loads(con.execute("SELECT payload FROM zone_study").fetchone()[0])
    check = con.execute("SELECT checked_at,payload FROM zone_study_checks ORDER BY id DESC LIMIT 1").fetchone()
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
    groups = {}
    for item in paired:
        group = " / ".join(str(item[k] or "Unknown") for k in ("source", "strategy", "tf"))
        group_data = groups.setdefault(group, {"count": 0, "totals": {r: "0" for r in RULES}})
        group_data["count"] += 1
        for rule in RULES:
            group_data["totals"][rule] = str(Decimal(group_data["totals"][rule])+Decimal(item["results"][rule]["pnl_usd"]))
    for rule in RULES:
        totals[rule]["difference_vs_swing_usd"] = str(sum((Decimal(i["results"][rule]["pnl_usd"])-Decimal(i["results"]["SWING_OBSERVED" if rule.endswith("OBSERVED") else "SWING_IDEAL"]["pnl_usd"]) for i in paired), Decimal(0)))
        totals[rule]["activated"] = sum(bool(i["moves"][rule]) for i in paired)
        totals[rule]["never_activated"] = sum(not i["moves"][rule] for i in paired)
        totals[rule]["cut_before_target"] = sum(i["results"]["HOLD"]["outcome"] == "TP" and i["results"][rule]["outcome"] == "SL" for i in paired)
    paused = check_data.get("paused")
    if not _compatible(config):
        paused = "The comparison is paused because its simulation rules changed."

    if check and now-check[0] > 1800:
        paused = "Comparison updates are delayed. The last recorded results are shown."
    return {"state": "PAUSED" if paused else "COLLECTING", "note": paused, "rules": RULES,
        "started_at": config["started_at"], "checked_at": check[0] if check else None,
        "paired_count": len(paired), "pending_count": sum(i["state"] in ("WAITING", "OPEN") for i in items),
        "excluded_count": sum(i["state"] == "EXCLUDED" for i in items), "totals": totals, "groups": groups,
        "items": sorted(items, key=lambda i: i["created_at"], reverse=True)[:100]}
