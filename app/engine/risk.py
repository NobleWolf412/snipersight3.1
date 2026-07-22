"""Risk Authority — §9: strategies request risk, this engine decides. Paper only.

Portfolio-scoped (one pass over ALL symbols/timeframes in strict time order —
risk is an account property, not a per-chart property). For every VALIDATED
setup intent, at its confirmed_at moment:
  1. settle any positions whose exits have occurred (equity moves),
  2. check the kill switch (daily realized loss beyond limit halts the day, §9/§13),
  3. check concurrent-position and total-open-risk limits (BTC and ETH count
     together — correlated crypto exposure),
  4. size the position: risk_usd = equity * RISK_PCT; units = risk_usd / stop
     distance; implied leverage capped by reducing size, never by widening
     stops (§9: stops are structure).
Decisions: APPROVED / REDUCED / REJECTED — each a fact with machine-readable
reasons (§8: rejections are as auditable as approvals).
"""
import json
from datetime import datetime, timezone
from decimal import Decimal

from . import store
from .setups import SETUP_VERSION
from .execsim import EXEC_VERSION
from .runlog import RunRecorder
from .universe import admitted_at

RISK_VERSION = "risk-v0.5-draft"
# v0.4 (user directive 2026-07-21): per-trade risk 1% -> 2%. Coherently
# re-tuned the whole envelope so the concurrency and kill-switch don't silently
# break: total cap 2% -> 4% (keeps 2 concurrent at 2% each), daily halt 3% ->
# 6% (~3 stop-outs, not ~1.5), scale-in add 0.5% -> 1% (stays half a base).
# v0.2: governs SCALE_IN adds — exempt from the concurrency count (attach to a
# parent) but consume the total-open-risk budget; REJECTED with PARENT_CLOSED
# if the parent position already exited.
SCALE_RISK_PCT = Decimal("0.01")

START_EQUITY = Decimal("10000")
RISK_PCT = Decimal("0.02")            # 2% of current equity per trade
MAX_CONCURRENT = 2
MAX_TOTAL_OPEN_RISK_PCT = Decimal("0.04")   # 4% of equity at risk at once
MAX_LEVERAGE = Decimal("1")              # declared venue is Coinbase spot
ALLOW_SHORTS = False                     # spot inventory shorting is unsupported
MIN_NOTIONAL_USD = Decimal("1")
DAILY_LOSS_LIMIT_PCT = Decimal("0.06")      # realized -6% in a UTC day -> halt
MIN_REDUCED_FRACTION = Decimal("0.25")      # reduce below 25% of intended -> reject
QC = Decimal("0.01")

TFS = ("15m", "1H", "4H", "1D", "1W")


def _symbols(con):
    """Every symbol with stored candles — portfolio scope spans the universe."""
    from .universe import all_tracked_symbols
    return all_tracked_symbols(con)


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def run(con) -> dict:
    with RunRecorder(con, "risk", RISK_VERSION, "PORTFOLIO", "ALL") as rec:
        from .scalein import SCALE_VERSION   # lazy: avoids circular import
        intents, exits = [], {}
        for sym in _symbols(con):
            for tf in TFS:
                for ver in (SETUP_VERSION, SCALE_VERSION):
                    for r in store.get_facts(con, sym, tf, "setup", ver):
                        p = json.loads(r["payload"])
                        if p["state"] == "VALIDATED":
                            intents.append({"symbol": sym, "tf": tf,
                                            "market_time": r["market_time"],
                                            "confirmed_at": r["confirmed_at"],
                                            "universe_eligible": admitted_at(
                                                con, sym, r["confirmed_at"]), **p})
                for r in store.get_facts(con, sym, tf, "exec", EXEC_VERSION):
                    p = json.loads(r["payload"])
                    exits[p["setup_id"]] = {"exit_ts": r["confirmed_at"],
                                            "r_net": Decimal(p["r_multiple"]),
                                            "outcome": p["outcome"]}
        intents.sort(key=lambda i: (i["confirmed_at"], i["market_time"], i["setup_id"]))
        rec.n_inputs = len(intents)

        equity = START_EQUITY
        open_pos: list[dict] = []
        daily_pnl: dict[str, Decimal] = {}
        day_start_equity: dict[str, Decimal] = {}
        halted: set[str] = set()
        curve: list[dict] = []
        n = {"APPROVED": 0, "REDUCED": 0, "REJECTED": 0, "KILL": 0}
        n_new_facts = 0

        def settle(up_to_ts):
            nonlocal equity, n_new_facts
            for p in sorted([p for p in open_pos if p["exit_ts"] and p["exit_ts"] <= up_to_ts],
                            key=lambda p: p["exit_ts"]):
                d = _day(p["exit_ts"])
                day_start_equity.setdefault(d, equity)
                pnl = (p["risk_usd"] * p["r_net"]).quantize(QC)
                equity = (equity + pnl).quantize(QC)
                daily_pnl[d] = daily_pnl.get(d, Decimal(0)) + pnl
                curve.append({"ts": p["exit_ts"], "equity": str(equity)})
                open_pos.remove(p)
                loss_limit = DAILY_LOSS_LIMIT_PCT * day_start_equity[d]
                if d not in halted and daily_pnl[d] <= -loss_limit:
                    halted.add(d)
                    n["KILL"] += 1
                    if store.insert_fact(
                            con, symbol="PORTFOLIO", tf="ALL", kind="risk",
                            market_time=p["exit_ts"], confirmed_at=p["exit_ts"],
                            algo_version=RISK_VERSION,
                            payload={"event": "KILL_SWITCH", "day": d,
                                     "daily_pnl": str(daily_pnl[d]),
                                     "day_start_equity": str(day_start_equity[d]),
                                     "loss_limit_usd": str(loss_limit),
                                     "equity": str(equity),
                                     "reason": "daily loss limit reached — no new entries today"}):
                        n_new_facts += 1

        for it in intents:
            ts = it["confirmed_at"]
            settle(ts)
            entry, sl = Decimal(it["entry"]), Decimal(it["sl"])
            stop_dist = abs(entry - sl)
            reasons, decision = [], "APPROVED"
            is_add = it["strategy"] == "SCALE_IN"
            intended = (equity * (SCALE_RISK_PCT if is_add else RISK_PCT)).quantize(QC)
            risk_usd = intended

            parents_open = {p["setup_id"] for p in open_pos}
            if _day(ts) in halted:
                decision, reasons = "REJECTED", ["DAILY_LOSS_HALT"]
            elif not it["universe_eligible"]:
                decision, reasons = "REJECTED", ["NOT_IN_POINT_IN_TIME_UNIVERSE"]
            elif stop_dist <= 0:
                decision, reasons = "REJECTED", ["INVALID_STOP_DISTANCE"]
            elif it["direction"] == "SHORT" and not ALLOW_SHORTS:
                decision, reasons = "REJECTED", ["SHORT_UNSUPPORTED_COINBASE_SPOT"]
            elif is_add and it.get("parent_setup_id") not in parents_open:
                decision, reasons = "REJECTED", ["PARENT_CLOSED"]
            elif not is_add and sum(1 for p in open_pos if "|ADD" not in p["setup_id"]) >= MAX_CONCURRENT:
                decision, reasons = "REJECTED", [f"CONCURRENT_LIMIT({MAX_CONCURRENT})"]
            else:
                open_risk = sum(p["risk_usd"] for p in open_pos)
                budget = (MAX_TOTAL_OPEN_RISK_PCT * equity - open_risk).quantize(QC)
                if budget < intended:
                    if budget < intended * MIN_REDUCED_FRACTION:
                        decision, reasons = "REJECTED", ["EXPOSURE_LIMIT"]
                    else:
                        decision, reasons = "REDUCED", ["EXPOSURE_LIMIT"]
                        risk_usd = budget
                if decision != "REJECTED" and stop_dist > 0:
                    units = risk_usd / stop_dist
                    notional = units * entry
                    lev = notional / equity
                    if lev > MAX_LEVERAGE:
                        scale = MAX_LEVERAGE / lev
                        risk_usd = (risk_usd * scale).quantize(QC)
                        units = risk_usd / stop_dist
                        notional = units * entry
                        lev = MAX_LEVERAGE
                        if decision == "APPROVED":
                            decision = "REDUCED"
                        reasons.append("SPOT_CASH_CAP(1x)")

                if decision != "REJECTED" and risk_usd > 0:
                    units = risk_usd / stop_dist
                    if units * entry < MIN_NOTIONAL_USD:
                        decision, reasons = "REJECTED", ["BELOW_MIN_NOTIONAL"]

            if decision == "REJECTED":
                risk_usd = Decimal(0)
            payload = {"event": "DECISION", "setup_id": it["setup_id"],
                       "decision": decision, "reasons": reasons or ["WITHIN_LIMITS"],
                       "intended_risk_usd": str(intended), "risk_usd": str(risk_usd),
                       "equity_at": str(equity)}
            if decision != "REJECTED" and stop_dist > 0:
                units = (risk_usd / stop_dist)
                payload.update({"units": str(units.quantize(Decimal("0.00000001"))),
                                "notional_usd": str((units * entry).quantize(QC)),
                                "implied_leverage": str((units * entry / equity).quantize(QC))})
                ex = exits.get(it["setup_id"])
                payload["fill_outcome"] = ex["outcome"] if ex else "PENDING"
                if ex is None or ex["outcome"] != "MISSED":
                    open_pos.append({"setup_id": it["setup_id"], "risk_usd": risk_usd,
                                     "exit_ts": ex["exit_ts"] if ex else None,
                                     "r_net": ex["r_net"] if ex else Decimal(0)})
            n[decision] += 1
            if store.insert_fact(con, symbol=it["symbol"], tf=it["tf"], kind="risk",
                                 market_time=it["market_time"], confirmed_at=ts,
                                 algo_version=RISK_VERSION, payload=payload):
                n_new_facts += 1

        settle(2**53)
        # authoritative account summary — the UI reads THIS, never re-derives
        # equity (a second reconstruction would drift from the compounding +
        # kill-switch accounting done here). §8: one source of truth.
        peak = float(START_EQUITY)
        maxdd = 0.0
        for pt in curve:
            e = float(pt["equity"])
            peak = max(peak, e)
            maxdd = max(maxdd, (peak - e) / peak * 100 if peak else 0)
        # deterministic anchor: last settlement (not wall-clock) so a re-run over
        # identical data produces a byte-identical summary fact (idempotent).
        summ_ts = int(curve[-1]["ts"]) if curve else 0
        if store.insert_fact(
                con, symbol="PORTFOLIO", tf="ALL", kind="account",
                market_time=summ_ts, confirmed_at=summ_ts,
                algo_version=RISK_VERSION,
                payload={"event": "SUMMARY", "start_equity": str(START_EQUITY),
                         "final_equity": str(equity),
                         "return_pct": str(((equity / START_EQUITY - 1) * 100).quantize(QC)),
                         "max_drawdown_pct": round(maxdd, 2),
                         "decisions": n, "curve": curve,
                         "venue_contract": {"venue": "coinbase-spot",
                                            "allow_shorts": ALLOW_SHORTS,
                                            "max_leverage": str(MAX_LEVERAGE)}}):
            n_new_facts += 1
        con.commit()
        rec.n_new_facts = n_new_facts
        rec.notes = f"final_equity={equity}"
        return {"final_equity": str(equity), **n}
