"""Prospective, research-only comparison of three independent 4H signal books.

Orders begin after the scanner observed a signal. Accepted candles and plans
are frozen in an append-only ledger; none of these rows enters account routing.
"""
import json
import time
from decimal import Decimal

from . import costs, execsim, importer, setups, store, swings, trend, venues


TRIAL_VERSION = "simple-trial-v0.1-draft"
DEPENDENCIES = {
    "setup": "setup-v0.24-draft", "trend": "trend-v0.4-draft",
    "exec": "exec-v0.30-draft", "swing": "swing-v0.11-draft",
}
STEP = importer.TF_SECONDS["4H"]
LOOKBACK = 20
STOP_BUFFER_ATR = Decimal("0.20")
TARGET_R = Decimal("2")
MAKER_OFFSET_R = Decimal("0.20")
MAKER_WAIT_BARS = 2
WINDOW_SECONDS = 90 * 86400
STARTING_BALANCE = Decimal("10000")
RISK_USD = Decimal("100")
MAX_SLOTS = 5
MIN_TRADES = 30
MIN_SYMBOLS = 8
ARMS = ("CURRENT", "CHANNEL", "TREND")


def _json(value):
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def _tables(con):
    con.execute("CREATE TABLE IF NOT EXISTS simple_trial_config "
                "(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS simple_trial_events "
                "(id INTEGER PRIMARY KEY, arm TEXT NOT NULL, signal_id TEXT NOT NULL, "
                "event TEXT NOT NULL, observed_at INTEGER NOT NULL, payload TEXT NOT NULL, "
                "UNIQUE(arm,signal_id,event))")
    con.execute("CREATE TABLE IF NOT EXISTS simple_trial_checks "
                "(id INTEGER PRIMARY KEY, checked_at INTEGER NOT NULL, payload TEXT NOT NULL)")


def exists(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name='simple_trial_config'").fetchone() is not None


def unresolved(con):
    if not exists(con):
        return set()
    return {(r["PLACED"]["symbol"], "4H") for r in _records(con).values()
            if "PLACED" in r and not ({"CLOSED", "EXPIRED"} & r.keys())}


def _activate(con, now):
    _tables(con)
    con.execute("INSERT OR IGNORE INTO simple_trial_config VALUES(1,?)", (_json({
        "version": TRIAL_VERSION, "dependencies": DEPENDENCIES,
        "started_at": now, "ends_at": now+WINDOW_SECONDS,
        "fact_watermark": con.execute(
            "SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0],
        "risk_usd": str(RISK_USD), "starting_balance": str(STARTING_BALANCE),
        "max_slots": MAX_SLOTS, "channel_lookback": LOOKBACK,
        "stop_buffer_atr": str(STOP_BUFFER_ATR),
        "target_r": str(TARGET_R), "maker_offset_r": str(MAKER_OFFSET_R),
        "maker_wait_bars": MAKER_WAIT_BARS, "timeframe": "4H",
    }),))


def _event(con, arm, sid, event, now, payload):
    con.execute("INSERT OR IGNORE INTO simple_trial_events"
                "(arm,signal_id,event,observed_at,payload) VALUES(?,?,?,?,?)",
                (arm, sid, event, now, _json(payload)))


def _records(con):
    records = {}
    for arm, sid, event, observed, raw in con.execute(
            "SELECT arm,signal_id,event,observed_at,payload "
            "FROM simple_trial_events ORDER BY id"):
        records.setdefault((arm, sid), {})[event] = json.loads(raw)
    return records


def _closed(con, symbol, start, now):
    return [dict(row) for row in store.get_candles(
        con, symbol, "4H", start_ts=start, end_ts=now-STEP+1)]


def channel_signal(candles: list[dict], symbol: str) -> dict | None:
    """One prior-20-bar close breakout; the signal bar is never in its channel."""
    if len(candles) < max(LOOKBACK+1, 35):
        return None
    bar, prior = candles[-1], candles[-LOOKBACK-1:-1]
    if any(prior[i]["open_ts"]+STEP != prior[i+1]["open_ts"]
           for i in range(len(prior)-1)):
        return None
    if prior[-1]["open_ts"]+STEP != bar["open_ts"]:
        return None
    close = Decimal(bar["close"])
    high = max(Decimal(p["high"]) for p in prior)
    low = min(Decimal(p["low"]) for p in prior)
    direction = ("LONG" if close > high else
                 "SHORT" if close < low else None)
    if direction is None or (direction == "SHORT" and
                             not venues.venue_for(symbol).allow_shorts):
        return None
    atr = swings.compute_atr(candles)[-1]
    if atr is None or atr <= 0:
        return None
    stop = (Decimal(bar["low"])-STOP_BUFFER_ATR*atr if direction == "LONG"
            else Decimal(bar["high"])+STOP_BUFFER_ATR*atr)
    risk = (close-stop if direction == "LONG" else stop-close)
    if risk <= 0:
        return None
    target = close + (TARGET_R*risk if direction == "LONG" else -TARGET_R*risk)
    maker = close + (-MAKER_OFFSET_R*risk if direction == "LONG"
                     else MAKER_OFFSET_R*risk)
    return {
        "setup_id": f"channel:{symbol}:{bar['open_ts']}:{TRIAL_VERSION}",
        "strategy": "SIMPLE_CHANNEL_BREAKOUT", "direction": direction,
        "state": "VALIDATED", "entry": str(close), "sl": str(stop),
        "tp": str(target), "maker_limit": str(maker),
        "entry_model": "MAKER_THEN_MARKET",
        "maker_wait_bars": MAKER_WAIT_BARS,
        "expires_at_ts": bar["open_ts"]+(MAKER_WAIT_BARS+3)*STEP,
        "confirmed_bar_ts": bar["open_ts"],
    }


def _advance(con, arm, sid, record, now):
    p = record["PLACED"]
    bars = [value for key, value in record.items() if key.startswith("BAR:")]
    bars.sort(key=lambda value: value["open_ts"])
    expected = (bars[-1]["open_ts"]+STEP if bars else
                p["warmup"][-1]["open_ts"]+STEP)
    until = min(now, p["active_at"]+(execsim.MAX_BARS+8)*STEP)
    for bar in _closed(con, p["symbol"], expected, until):
        if bar["open_ts"] != expected:
            break
        _event(con, arm, sid, f"BAR:{expected}", now, bar)
        bars.append(bar)
        expected += STEP
    if not bars or bars[-1]["open_ts"] < p["active_at"]:
        return
    candles = p["warmup"]+bars
    offset = next(i for i, bar in enumerate(candles)
                  if bar["open_ts"] == p["active_at"])
    atr = swings.compute_atr(candles)
    fill = record.get("FILLED")
    long = p["direction"] == "LONG"
    stop, target = Decimal(p["sl"]), Decimal(p["tp"])
    profile = costs.by_version(p["cost_profile"])
    if fill is None:
        end = next((i for i, bar in enumerate(candles)
                    if bar["open_ts"] >= p["expires_at"]), len(candles))
        # Entry slippage may read only ATR known before the fill bar opened.
        prior_atr = [None]+atr[:-1]
        result = execsim.simulate_entry(
            candles[:end], prior_atr[:end], offset, Decimal(p["entry"]),
            stop, long, entry_model=p["entry_model"],
            maker_limit=Decimal(p["maker_limit"]),
            maker_wait=p["maker_wait_bars"], profile=profile,
            max_entry_bars=max(1, end-offset))
        if result["status"] != "FILLED":
            if result["status"] == "MISSED" or expected >= p["expires_at"]:
                _event(con, arm, sid, "EXPIRED", now, {
                    "at": p["expires_at"], "reason": "Entry window ended unfilled."})
            return
        index = result["fill_i"]
        fill = {"at": candles[index]["open_ts"], "entry": str(result["entry"]),
                "risk": str(result["risk"]), "entry_role": result["entry_role"],
                "quantity": p["quantity"], "note": result["note"]}
        if ((long and result["entry"] >= target) or
                (not long and result["entry"] <= target)):
            _event(con, arm, sid, "EXPIRED", now, {
                "at": fill["at"], "reason": "Fill moved beyond target."})
            return
        _event(con, arm, sid, "FILLED", now, fill)
    fi = next(i for i, bar in enumerate(candles) if bar["open_ts"] == fill["at"])
    walked = execsim.walk_exit(candles, fi, stop, target, long)
    if walked is None:
        return
    outcome, price, ei, ambiguous = walked
    entry, qty = Decimal(fill["entry"]), Decimal(fill["quantity"])
    settlement = execsim.settle(
        profile, p["symbol"], entry, price, Decimal(fill["risk"]),
        long, outcome, ei-fi+1, STEP, atr[ei], entry_role=fill["entry_role"])
    net_unit = (((settlement["eff_exit"]-entry) if long
                 else (entry-settlement["eff_exit"]))
                - settlement["fees"]-settlement["funding"])
    pnl = net_unit*qty
    _event(con, arm, sid, "CLOSED", now, {
        "at": candles[ei]["open_ts"]+STEP, "outcome": outcome,
        "exit": str(settlement["eff_exit"]), "pnl_usd": str(pnl),
        "r_multiple": str(pnl/Decimal(p["risk_usd"])),
        "fees_usd": str(settlement["fees"]*qty),
        "funding_usd": str(settlement["funding"]*qty),
        "ambiguous_bar": ambiguous,
        "slippage_missing": settlement["slip_missing"]})


def _place(con, config, records, arm, sid, symbol, confirmed, plan, observed_at,
           *, cutoff: int, scan_symbols: set[str], source: dict):
    observed = {"symbol": symbol, "confirmed_at": confirmed,
                "observed_at": observed_at, "cutoff": cutoff,
                "source": source, "plan": plan}
    _event(con, arm, sid, "OBSERVED", observed_at, observed)
    if (arm, sid) in records:
        return
    reason = None
    try:
        direction = plan["direction"]
        entry, stop, target, maker = (Decimal(plan[key]) for key in
                                      ("entry", "sl", "tp", "maker_limit"))
        long = direction == "LONG"
        risk = entry-stop if long else stop-entry
        if (direction not in ("LONG", "SHORT") or risk <= 0 or
                not all(value.is_finite() and value > 0 for value in
                        (entry, stop, target, maker)) or
                not (stop < maker < entry < target if long
                     else target < entry < maker < stop)):
            raise ValueError("invalid bracket")
        if plan["entry_model"] != "MAKER_THEN_MARKET":
            raise ValueError("unsupported entry model")
        wait = int(plan["maker_wait_bars"])
        if not 1 <= wait <= 4:
            raise ValueError("invalid maker wait")
        active_at = (observed_at//STEP+1)*STEP
        expiry = min(int(plan["expires_at_ts"]),
                     active_at+(wait+1)*STEP)
        history = _closed(con, symbol, max(0, active_at-101*STEP), cutoff)
        for i in range(len(history)-1, 0, -1):
            if history[i]["open_ts"]-history[i-1]["open_ts"] != STEP:
                history = history[i:]
                break
        live = [r["PLACED"] for (a, _), r in records.items()
                if a == arm and "PLACED" in r and
                not ({"CLOSED", "EXPIRED"} & r.keys())]
        balance = Decimal(config["starting_balance"])+sum(
            (Decimal(r["CLOSED"]["pnl_usd"]) for (a, _), r in records.items()
             if a == arm and "CLOSED" in r), Decimal(0))
        quantity = Decimal(config["risk_usd"])/risk
        reserve = entry*quantity*Decimal("1.02")
        if (confirmed < config["started_at"] or confirmed > cutoff or
                confirmed > observed_at or observed_at-confirmed > STEP):
            reason = "Signal was not observed in its fresh 4H window."
        elif observed_at >= config["ends_at"]:
            reason = "Fixed collection window ended."
        elif symbol not in scan_symbols:
            reason = "Market outside current scan."
        elif expiry <= active_at:
            reason = "Entry expired before observation."
        elif len(history) < 35 or history[-1]["open_ts"]+STEP > cutoff:
            reason = "Recent contiguous 4H history unavailable."
        elif len(live) >= config["max_slots"]:
            reason = "Study book has five open orders or trades."
        elif any(p["symbol"] == symbol for p in live):
            reason = "Study book already holds this symbol."
        elif reserve+sum((Decimal(p["reserved_usd"]) for p in live),
                         Decimal(0)) > balance:
            reason = "Study book lacks unreserved cash."
        elif direction == "SHORT" and not venues.venue_for(symbol).allow_shorts:
            reason = "Venue does not permit short trades."
        if reason is None:
            profile = costs.profile_for(symbol)
            placed = {**observed, **{key: plan[key] for key in (
                "entry", "sl", "tp", "direction", "maker_limit", "entry_model")},
                "symbol": symbol, "active_at": active_at,
                "expires_at": expiry, "maker_wait_bars": wait,
                "quantity": str(quantity), "risk_usd": config["risk_usd"],
                "reserved_usd": str(reserve), "warmup": history,
                "cost_profile": profile.version}
            _event(con, arm, sid, "PLACED", observed_at, placed)
            records[(arm, sid)] = {"PLACED": placed}
        else:
            _event(con, arm, sid, "SKIPPED", observed_at, {"reason": reason})
            records[(arm, sid)] = {"SKIPPED": {"reason": reason}}
    except (KeyError, ValueError, ArithmeticError, TypeError):
        _event(con, arm, sid, "SKIPPED", observed_at, {
            "reason": "Signal has invalid or unavailable execution fields."})
        records[(arm, sid)] = {"SKIPPED": {}}


def run(con, symbols: set[str], cutoff: int | None = None,
        *, observed_at: int | None = None):
    """Scanner-owned single transaction. Never emits account/order facts."""
    observed_at = int(time.time()) if observed_at is None else observed_at
    cutoff = observed_at if cutoff is None else cutoff
    if cutoff > observed_at:
        raise ValueError("Candle cutoff cannot be later than observation")
    if con.in_transaction:
        raise RuntimeError("Simple trial requires its own transaction")
    con.execute("BEGIN IMMEDIATE")
    try:
        _activate(con, observed_at)
        config = json.loads(con.execute(
            "SELECT payload FROM simple_trial_config WHERE id=1").fetchone()[0])
        if (config["version"] != TRIAL_VERSION or
                config["dependencies"] != DEPENDENCIES or
                DEPENDENCIES != {"setup": setups.SETUP_VERSION,
                                 "trend": trend.TREND_VERSION,
                                 "exec": execsim.EXEC_VERSION,
                                 "swing": swings.SWING_VERSION}):
            con.execute("INSERT INTO simple_trial_checks(checked_at,payload) "
                        "VALUES(?,?)", (observed_at, _json({"paused": "Pinned rules changed."})))
            con.commit()
            return
        records = _records(con)
        for (arm, sid), record in records.items():
            if "PLACED" in record and not ({"CLOSED", "EXPIRED"} & record.keys()):
                _advance(con, arm, sid, record, cutoff)
        records = _records(con)
        if observed_at < config["ends_at"]:
            rows = con.execute(
                "SELECT id,symbol,tf,confirmed_at,algo_version,payload,content_hash "
                "FROM facts WHERE id>? AND kind='setup' AND tf='4H' "
                "AND algo_version IN (?,?) ORDER BY id",
                (config["fact_watermark"], DEPENDENCIES["setup"],
                 DEPENDENCIES["trend"])).fetchall()
            for fid, symbol, tf, confirmed, version, raw, digest in rows:
                plan = json.loads(raw)
                if plan.get("state") != "VALIDATED":
                    continue
                arm = "TREND" if version == DEPENDENCIES["trend"] else "CURRENT"
                if arm == "CURRENT" and plan.get("strategy") not in ("PULLBACK", "REVERSAL"):
                    continue
                sid = str(plan.get("setup_id") or f"invalid:{fid}")
                _place(con, config, records, arm, sid, symbol, confirmed,
                       plan, observed_at, cutoff=cutoff, scan_symbols=symbols,
                       source={"fact_id": fid, "content_hash": digest,
                               "version": version})
            for symbol in sorted(symbols):
                candles = _closed(con, symbol, max(0, cutoff-101*STEP), cutoff)
                plan = channel_signal(candles, symbol)
                if plan is not None:
                    sid = plan["setup_id"]
                    _place(con, config, records, "CHANNEL", sid, symbol,
                           candles[-1]["open_ts"]+STEP, plan, observed_at,
                           cutoff=cutoff, scan_symbols=symbols,
                           source={"bar_open_ts": candles[-1]["open_ts"]})
        config["fact_watermark"] = con.execute(
            "SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0]
        con.execute("UPDATE simple_trial_config SET payload=? WHERE id=1",
                    (_json(config),))
        con.execute("INSERT INTO simple_trial_checks(checked_at,payload) "
                    "VALUES(?,?)", (observed_at, _json({"checked": True,
                                                         "cutoff": cutoff})))
        con.commit()
    except Exception:
        con.rollback()
        raise


def _bootstrap_difference(high, low, count=2000):
    groups = {"high": {}, "low": {}}
    for name, rows in (("high", high), ("low", low)):
        for row in rows:
            groups[name].setdefault(row["symbol"], []).append(float(row["r"]))
    symbols = sorted(set(groups["high"]) | set(groups["low"]))
    state, mask, values = 0x2545F4914F6CDD1D, (1 << 64)-1, []
    for _ in range(count):
        a, b = [], []
        for _ in symbols:
            state = (state*6364136223846793005+1442695040888963407) & mask
            symbol = symbols[(state >> 33) % len(symbols)]
            a.extend(groups["high"].get(symbol, ()))
            b.extend(groups["low"].get(symbol, ()))
        if a and b:
            values.append(sum(a)/len(a)-sum(b)/len(b))
    if not values:
        return None
    values.sort()
    return {"uplift_r": sum(r["r"] for r in high)/len(high) -
            sum(r["r"] for r in low)/len(low),
            "ci_lo": values[int(.025*len(values))],
            "ci_hi": values[min(len(values)-1, int(.975*len(values)))],
            "resamples": len(values)}


def report(con, now: int | None = None) -> dict:
    """Read-only verdict; an underfilled future sample always stays UNKNOWN."""
    now = int(time.time()) if now is None else now
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='simple_trial_config'").fetchone():
        return {"state": "NOT_STARTED", "affects_trading": False,
                "primary": {"verdict": "UNKNOWN"}}
    config = json.loads(con.execute(
        "SELECT payload FROM simple_trial_config WHERE id=1").fetchone()[0])
    check = con.execute("SELECT checked_at,payload FROM simple_trial_checks "
                        "ORDER BY id DESC LIMIT 1").fetchone()
    paused = json.loads(check[1]).get("paused") if check else None
    records = _records(con)
    arms, samples = {}, {}
    for arm in ARMS:
        closed = [(r["OBSERVED"]["symbol"], r["PLACED"]["direction"],
                   r["CLOSED"]) for (a, _), r in records.items()
                  if a == arm and "CLOSED" in r]
        samples[arm] = [{"symbol": s, "r": float(x["r_multiple"])}
                        for s, _, x in closed]
        balance = Decimal(config["starting_balance"])
        peak, drawdown = balance, Decimal(0)
        for _, _, result in sorted(closed, key=lambda row: row[2]["at"]):
            balance += Decimal(result["pnl_usd"])
            peak = max(peak, balance)
            if peak > 0:
                drawdown = max(drawdown, (peak-balance)/peak)
        by_direction = {}
        for direction in ("LONG", "SHORT"):
            side = [result for _, d, result in closed if d == direction]
            by_direction[direction] = {
                "closed": len(side),
                "net_usd": str(sum((Decimal(result["pnl_usd"]) for result in side),
                                   Decimal(0))),
                "mean_r": (str(sum((Decimal(result["r_multiple"]) for result in side),
                                    Decimal(0))/len(side)) if side else None),
            }
        arms[arm] = {
            "closed": len(closed), "symbols": len({s for s, _, _ in closed}),
            "placed": sum(a == arm and "PLACED" in r for (a, _), r in records.items()),
            "skipped": sum(a == arm and "SKIPPED" in r for (a, _), r in records.items()),
            "unresolved": sum(a == arm and "PLACED" in r and
                              not ({"CLOSED", "EXPIRED"} & r.keys())
                              for (a, _), r in records.items()),
            "net_usd": str(balance-Decimal(config["starting_balance"])),
            "return_pct": str((balance/Decimal(config["starting_balance"])-1)*100),
            "max_drawdown_pct": str(drawdown*100),
            "long_closed": sum(d == "LONG" for _, d, _ in closed),
            "short_closed": sum(d == "SHORT" for _, d, _ in closed),
            "by_direction": by_direction,
            "mean_r": (str(sum(Decimal(x["r_multiple"]) for _, _, x in closed)
                           /len(closed)) if closed else None)}
    enough = all(arms[a]["closed"] >= MIN_TRADES and
                 arms[a]["symbols"] >= MIN_SYMBOLS for a in ("CHANNEL", "CURRENT"))
    interval = (_bootstrap_difference(samples["CHANNEL"], samples["CURRENT"])
                if enough else None)
    verdict = ("UNKNOWN" if not enough or interval is None else
               "PROMISING_UNPROVEN" if interval["ci_lo"] > 0 else
               "NO_RELIABLE_IMPROVEMENT")
    return {
        "state": ("PAUSED" if paused else
                  "COMPLETE" if now >= config["ends_at"] and
                  not any(a["unresolved"] for a in arms.values()) else
                  "COLLECTING"),
        "reason": paused, "version": config["version"],
        "started_at": config["started_at"], "ends_at": config["ends_at"],
        "checked_at": check[0] if check else None,
        "affects_trading": False, "arms": arms,
        "primary": {"hypothesis": "Simple 4H channel breakout vs current playbooks",
                    "verdict": verdict, "interval": interval,
                    "minimum_trades_each": MIN_TRADES,
                    "minimum_symbols_each": MIN_SYMBOLS},
        "secondary": {"hypothesis": "Trend pullback/reclaim",
                      "verdict": "EXPLORATORY"},
    }
