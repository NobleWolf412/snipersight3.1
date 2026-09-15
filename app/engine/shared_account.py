"""Account admission and cutover authority. The SQLite writer lock is the gate.

No network work, run recorder, or implicit-commit helper belongs inside an
admission transaction. Both supervised processes use this module.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal

from . import execution, paperbook, risk, settings, cooldowns
from .contracts import (AutomationMode, DecisionReason, ExecutionPlan, OrderIntent,
                        OrderKind, RiskDecision, to_wire)

SHARED_ACCOUNT_VERSION = "shared-account-v0.2-draft"
PROFILE_VERSION = "shared-paper-profile-v0.2-draft"
TERMINAL = ("PAPER_CLOSED", "PAPER_EXPIRED", "CANCELLED", "RISK_REJECTED",
            "HELD_OFF", "REJECTED", "CLOSED", "ORDER_LIFECYCLE_COMPLETE")


class AdmissionRejected(execution.DispatchRejected, ValueError):
    pass


def ensure(con):
    execution._ensure(con)
    settings._ensure(con)
    con.execute("""CREATE TABLE IF NOT EXISTS account_epochs (
        id TEXT PRIMARY KEY, workspace TEXT NOT NULL, mode TEXT NOT NULL,
        opened_at INTEGER NOT NULL, opening_equity TEXT NOT NULL,
        profile_version TEXT NOT NULL, risk_pct TEXT NOT NULL,
        active INTEGER NOT NULL, closed_at INTEGER, label TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('OPEN','DRAINING','SEALED')))""")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS account_epoch_active "
                "ON account_epochs(workspace,mode) WHERE active=1")
    con.execute("""CREATE TABLE IF NOT EXISTS account_requests (
        request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
        intent_id TEXT NOT NULL, receipt TEXT NOT NULL, created_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS account_events (
        id INTEGER PRIMARY KEY, epoch_id TEXT, occurred_at INTEGER NOT NULL,
        event TEXT NOT NULL, payload TEXT NOT NULL)""")


@contextmanager
def immediate(con):
    if con.in_transaction:
        raise AdmissionRejected("ACCOUNT_TRANSACTION_REQUIRED: finish caller writes first")
    try:
        con.execute("BEGIN IMMEDIATE")
        yield
        con.commit()
    except sqlite3.OperationalError as exc:
        con.rollback()
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise AdmissionRejected("ACCOUNT_BUSY: retry the same request") from exc
        raise
    except BaseException:
        con.rollback()
        raise


def current_epoch(con):
    """Missing row means the untouched legacy paper book, not an automatic reset."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='account_epochs'").fetchone():
        return None
    row = con.execute("SELECT id,workspace,mode,opened_at,opening_equity,profile_version,"
                      "risk_pct,active,closed_at,label,state FROM account_epochs "
                      "WHERE workspace='CRYPTO' AND mode='PAPER' AND active=1").fetchone()
    return dict(zip(("id", "workspace", "mode", "opened_at", "opening_equity",
                     "profile_version", "risk_pct", "active", "closed_at", "label",
                     "state"), row)) if row else None


def gates_for_account(con):
    epoch = current_epoch(con)
    gates = risk.gates_for_mode(AutomationMode.PAPER)
    if epoch:
        pct = Decimal(epoch["risk_pct"])
        gates.update(risk_pct=pct, scale_risk_pct=risk.SCALE_ADD_R * pct,
                     max_total_open_risk_pct=risk.MAX_OPEN_R * pct,
                     daily_loss_limit_pct=risk.DAILY_LOSS_R * pct)
    return gates


def set_risk_percent(con, value, expected_epoch, expected_risk_pct):
    """Change future admission under the same cross-process writer lock."""
    try:
        pct = Decimal(str(value)) / 100
    except Exception as exc:
        raise AdmissionRejected("Enter a valid risk percentage") from exc
    if not pct.is_finite() or not Decimal("0") < pct <= Decimal("1"):
        raise AdmissionRejected("Risk must be greater than 0% and at most 100%")
    ensure(con)
    with immediate(con):
        epoch = current_epoch(con)
        old = gates_for_account(con)["risk_pct"]
        if expected_epoch != (epoch["id"] if epoch else "legacy") or str(old) != str(expected_risk_pct):
            raise AdmissionRejected("ACCOUNT_CHANGED: reload Settings before saving risk")
        if epoch is None:
            con.execute("INSERT INTO account_epochs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        ("legacy", "CRYPTO", "PAPER", 0, str(paperbook.opening_equity()),
                         PROFILE_VERSION, str(pct), 1, None, "Current paper account", "OPEN"))
            con.execute("UPDATE execution_outbox SET account_epoch_id='legacy' "
                        "WHERE mode='PAPER' AND account_epoch_id IS NULL")
        else:
            con.execute("UPDATE account_epochs SET risk_pct=?,profile_version=? WHERE id=?",
                        (str(pct), PROFILE_VERSION, epoch["id"]))
        con.execute("INSERT INTO account_events(epoch_id,occurred_at,event,payload) VALUES(?,?,?,?)",
                    (epoch["id"] if epoch else "legacy", int(time.time()), "RISK_CHANGED",
                     json.dumps({"previous_risk_pct":str(old), "risk_pct":str(pct),
                                 "version":SHARED_ACCOUNT_VERSION})))
    return context(con)



def _hash(value):
    return hashlib.sha256(json.dumps(to_wire(value), sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _existing(con, request_id, digest):
    row = con.execute("SELECT request_hash,receipt FROM account_requests WHERE request_id=?",
                      (request_id,)).fetchone()
    if row:
        if row[0] != digest:
            raise AdmissionRejected("REQUEST_CONFLICT: this request identity has different terms")
        return {**json.loads(row[1]), "duplicate": True}
    return None


def _record(con, request_id, digest, receipt):
    con.execute("INSERT INTO account_requests VALUES(?,?,?,?,?)",
                (request_id, digest, receipt["intent_id"], json.dumps(to_wire(receipt)),
                 int(time.time())))


def _legacy_untracked(con):
    from . import manual
    known = {r[0] for r in con.execute("SELECT intent_id FROM execution_outbox")}
    return [p for plans in manual.unresolved(con).values() for p in plans
            if p["intent_id"] not in known]


def _decision(con, *, symbol, direction, entry, stop, now, requested=None):
    epoch = current_epoch(con)
    if epoch and epoch["state"] != "OPEN":
        raise AdmissionRejected("ACCOUNT_DRAINING: new entries paused for cutover")
    if _legacy_untracked(con):
        raise AdmissionRejected("LEGACY_EXPOSURE: unresolved manual trades occupy the account")
    gates = gates_for_account(con)
    policy = risk.policy_for(con, gates, 0)
    account = paperbook.snapshot(con, gates=gates,
                                 max_drawdown_pct=policy["max_drawdown_pct"])
    # Manual and bot share only account-level admission. A discretionary plan
    # is never represented as a strategy approval.
    policy = dict(policy, decision_at=now, strategy_enabled={},
                  cooldown=lambda ts, sym, side: cooldowns.blocked_at(
                      account["cooldowns"], ts, sym, side))
    if account["unpriced_intents"]:
        # Only unresolved unpriced orders can consume unknown risk.
        for iid, raw, state in con.execute(
                "SELECT intent_id,payload,state FROM execution_outbox WHERE mode='PAPER'"):
            if state not in TERMINAL and paperbook._plan_risk_usd(raw) <= 0:
                raise AdmissionRejected("UNPRICED_EXPOSURE: reconcile the unresolved order")
    verdict = risk.decide({"entry": str(entry), "sl": str(stop), "symbol": symbol,
                           "direction": direction, "confirmed_at": now,
                           "strategy": "ACCOUNT_ENTRY", "universe_eligible": True},
                          account, policy)
    if verdict["decision"] == "REJECTED":
        held = []
        for raw, state in con.execute("SELECT payload,state FROM execution_outbox WHERE mode='PAPER'"):
            if state not in TERMINAL:
                plan = execution._plan_from_wire(raw)
                if plan:
                    i = plan.intent
                    held.append(f"{i.symbol} {i.timeframe} entry {i.entry} stop {i.stop}")
        detail = ("; account occupied by " + ", ".join(held)) if held else ""
        raise AdmissionRejected("; ".join(verdict["reasons"]) + detail + "; nothing was armed")
    allowed = verdict["risk_usd"]
    if requested is not None:
        requested = Decimal(str(requested))
        if not requested.is_finite() or requested <= 0:
            raise AdmissionRejected("INVALID_RISK: risk must be finite and positive")
        if requested > allowed:
            raise AdmissionRejected(f"RISK_LIMIT: requested {requested}; account allows {allowed}")
        allowed = requested
    return account, allowed, epoch


def admit_plan(con, plan: ExecutionPlan):
    """Check latest account state and reserve exactly once across processes."""
    ensure(con)
    digest = _hash(replace(plan.intent, created_at=0))
    with immediate(con):
        old = _existing(con, plan.intent.idempotency_key, digest)
        if old:
            stored = con.execute("SELECT payload,state FROM execution_outbox WHERE intent_id=?",
                                 (old["intent_id"],)).fetchone()
            return execution._plan_from_wire(stored[0]), {**old, "state": stored[1]}
        # Migration retry: do not mint a second row for an already queued order.
        oldrow = con.execute("SELECT payload,intent_id,state FROM execution_outbox "
                             "WHERE idempotency_key=?", (plan.intent.idempotency_key,)).fetchone()
        if oldrow:
            stored = execution._plan_from_wire(oldrow[0])
            if stored is None:
                raise AdmissionRejected("LEGACY_RECEIPT_UNREADABLE")
            return stored, {"intent_id": oldrow[1], "state": oldrow[2], "duplicate": True}
        intent = plan.intent
        if intent.expires_at is not None and intent.expires_at <= int(time.time()):
            raise AdmissionRejected("ATTEMPT_EXPIRED")
        entry = intent.entry
        if entry is None:
            # A market order still needs an authoritative sizing mark.
            entry = plan.risk.notional_usd / intent.quantity if intent.quantity > 0 else None
        if entry is None or not entry.is_finite() or entry <= 0:
            raise AdmissionRejected("MISSING_ENTRY_MARK")
        account, amount, epoch = _decision(con, symbol=intent.symbol,
            direction=intent.direction, entry=entry, stop=intent.stop, now=int(time.time()))
        if not plan.risk.approved or plan.risk.quantity != intent.quantity:
            raise AdmissionRejected("RISK_REJECTED: no strategy-approved size")
        # Rebase the requested strategy size onto the current account cap.
        # Never enlarge a strategy's approved size; new epochs shrink 2% to .25%
        # here, without a second dispatch_scale multiplication.
        amount = min(amount, plan.risk.risk_usd)
        if amount <= 0:
            raise AdmissionRejected("ZERO_RISK_SIZE")
        quantity = (intent.quantity * amount / plan.risk.risk_usd).quantize(Decimal("0.00000001"))
        if quantity <= 0:
            raise AdmissionRejected("ZERO_RISK_SIZE")
        approved = replace(plan, intent=replace(intent, quantity=quantity,
                           account_epoch_id=epoch["id"] if epoch else None),
                           risk=replace(plan.risk, risk_usd=amount, quantity=quantity,
                           notional_usd=quantity * entry,
                           implied_leverage=quantity * entry / account["equity"],
                           equity_basis_usd=account["equity"], equity_basis_source="PAPER_LEDGER"))
        receipt = execution.enqueue(con, approved.intent, plan=approved, commit=False)
        _record(con, intent.idempotency_key, digest, receipt)
        return approved, receipt


def create_manual(con, symbol, tf, direction, entry, tp, sl, created_at,
                  risk_usd=None, size_units=None, note="", leverage=1,
                  trail_r=None, partials=None, expected_epoch=None, max_age=None):
    from . import manual, venues
    ensure(con)
    request_id = f"{symbol}|{tf}|MANUAL|{created_at}"
    terms = dict(symbol=symbol, tf=tf, direction=direction, entry=str(entry), tp=str(tp),
                 sl=str(sl), risk_usd=risk_usd, size_units=size_units, leverage=leverage,
                 trail_r=trail_r, partials=partials)
    digest = _hash(terms)
    with immediate(con):
        old = _existing(con, request_id, digest)
        if old:
            return {**old["manual"], "written": False, "already_armed": True,
                    "execution_receipt": old}
        epoch = current_epoch(con)
        if expected_epoch is not None and expected_epoch != (epoch["id"] if epoch else "legacy"):
            raise AdmissionRejected("ACCOUNT_CHANGED: review the ticket again")
        if max_age is not None and abs(int(time.time()) - created_at) > max_age:
            raise AdmissionRejected("PREVIEW_EXPIRED: review the ticket again")
        entry, stop = Decimal(str(entry)), Decimal(str(sl))
        manual.validate(symbol, direction, entry, Decimal(str(tp)), stop, Decimal(str(leverage or 1)))
        if size_units is not None:
            implied = Decimal(str(size_units)) * abs(entry - stop)
            if risk_usd is not None and abs(implied - Decimal(str(risk_usd))) > Decimal("0.01"):
                raise AdmissionRejected("RISK_SIZE_MISMATCH")
            risk_usd = implied
        account, amount, epoch = _decision(con, symbol=symbol, direction=direction,
            entry=entry, stop=stop, now=int(time.time()), requested=risk_usd)
        quantity = amount / abs(entry - stop)
        # Browser timestamps identify requests; only server acceptance activates
        # an order. Trusted offline callers may supply their simulation clock.
        accepted_at = int(time.time()) if max_age is not None else created_at
        payload = manual._create_intent_legacy(con, symbol, tf, direction, entry, tp, sl,
            created_at, risk_usd=amount, size_units=quantity, note=note,
            leverage=leverage, trail_r=trail_r, partials=partials, commit=False, accepted_at=accepted_at)
        intent = OrderIntent(intent_id=request_id, setup_id="manual:" + request_id,
            mode=AutomationMode.PAPER, symbol=symbol, direction=direction,
            order_kind=OrderKind.LIMIT, quantity=quantity, entry=entry, stop=stop,
            targets=(Decimal(str(tp)),), reduce_only=False, created_at=accepted_at,
            playbook_version=manual.MANUAL_VERSION, idempotency_key=request_id,
            timeframe=tf, attempt_id=request_id, origin="OPERATOR",
            account_epoch_id=epoch["id"] if epoch else None)
        decision = RiskDecision(True, "APPROVED", amount, quantity, quantity * entry,
            quantity * entry / account["equity"],
            (DecisionReason("ACCOUNT_APPROVED", "Within the shared account limits"),),
            account["equity"], "PAPER_LEDGER")
        plan = ExecutionPlan(intent, decision, venues.venue_for(symbol).key, "ISOLATED", "ONE_WAY")
        receipt = execution.enqueue(con, intent, plan=plan, commit=False)
        # Manual's proven resolver owns its partial and trailing fills. PENDING
        # is a reservation, and this durable marker prevents the generic monitor
        # from independently settling the same trade.
        receipt["manual"] = payload
        _record(con, request_id, digest, receipt)
        return {**payload, "execution_receipt": receipt}


def request_cutover(con, action, expected_epoch=None):
    ensure(con)
    with immediate(con):
        epoch = current_epoch(con)
        if expected_epoch is not None and expected_epoch != (epoch['id'] if epoch else 'legacy'):
            raise AdmissionRejected('ACCOUNT_CHANGED: review the account transition again')
        now = int(time.time())
        if epoch is None:
            if action != "drain":
                raise AdmissionRejected("Start cutover with drain")
            con.execute("INSERT INTO account_epochs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("legacy", "CRYPTO", "PAPER", 0, str(paperbook.opening_equity()),
                 "legacy-paper-2pct", "0.02", 1, None, "Legacy paper", "OPEN"))
            # Metadata only. Null membership is the legacy book.
            con.execute("UPDATE execution_outbox SET account_epoch_id='legacy' "
                        "WHERE mode='PAPER' AND account_epoch_id IS NULL")
            epoch = current_epoch(con)
        if action == "drain":
            con.execute("UPDATE account_epochs SET state='DRAINING' WHERE id=?", (epoch["id"],))
        elif action == "resume":
            con.execute("UPDATE account_epochs SET state='OPEN' WHERE id=?", (epoch["id"],))
        elif action == "complete":
            if epoch["state"] != "DRAINING":
                raise AdmissionRejected("Account must be DRAINING before completing cutover")
            blockers = cutover_blockers(con, epoch["id"])
            if blockers:
                raise AdmissionRejected("CUTOVER_WAITING: " + ", ".join(blockers))
            con.execute("UPDATE account_epochs SET state='SEALED',active=0,closed_at=? WHERE id=?",
                        (now, epoch["id"]))
            # ONE SPELLING OF THE OPENING BALANCE. This was the literal
            # "10000" while the legacy epoch nineteen lines above asked
            # `paperbook.opening_equity()`. Equal today, because
            # `risk.START_EQUITY` is Decimal("10000") — and silently different
            # the day that constant moves, which is exactly the divergence
            # `paperbook.opening_equity` exists to prevent.
            con.execute("INSERT INTO account_epochs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, "CRYPTO", "PAPER", now,
                 str(paperbook.opening_equity()), PROFILE_VERSION,
                 epoch["risk_pct"], 1, None, "Current paper account", "OPEN"))
        else:
            raise AdmissionRejected("action must be drain, resume, or complete")
        con.execute("INSERT INTO account_events(epoch_id,occurred_at,event,payload) VALUES(?,?,?,?)",
                    (epoch["id"], now, "CUTOVER_" + action.upper(), "{}"))
    return context(con)


def cutover_blockers(con, epoch_id):
    marks = ",".join("?" for _ in TERMINAL)
    blockers = ["order:" + r[0] for r in con.execute(
        f"SELECT intent_id FROM execution_outbox WHERE mode='PAPER' AND "
        f"(account_epoch_id=? OR account_epoch_id IS NULL) AND state NOT IN ({marks})",
        (epoch_id, *TERMINAL))]
    blockers += ["position:" + r[0] for r in con.execute(
        "SELECT p.intent_id FROM paper_positions p JOIN execution_outbox o USING(intent_id) "
        "WHERE p.state!='CLOSED' AND (o.account_epoch_id=? OR o.account_epoch_id IS NULL)", (epoch_id,))]
    blockers += ["legacy-manual:" + p["intent_id"] for p in _legacy_untracked(con)]
    return blockers


def context(con):
    ensure(con)
    epoch = current_epoch(con)
    gates = gates_for_account(con)
    account = paperbook.snapshot(con, gates=gates)
    account = dict(account, halted_days=sorted(account["halted_days"]))
    return to_wire({"authority": "shared_account", "workspace": "CRYPTO", "mode": "PAPER",
        "epoch": epoch, "epoch_id": epoch["id"] if epoch else "legacy",
        "state": epoch["state"] if epoch else "OPEN", "risk_pct": gates["risk_pct"],
        "slot_ceiling": gates["max_concurrent"], "account": account,
        "cutover_blockers": cutover_blockers(con, epoch["id"] if epoch else "legacy"),
        "observed_at": int(time.time()), "version": SHARED_ACCOUNT_VERSION})


def journal(con, *, include_legacy=False):
    ensure(con)
    epoch = current_epoch(con)
    rows = con.execute("SELECT o.intent_id,o.setup_id,o.attempt_id,o.account_epoch_id,o.origin,"
        "o.controller,o.grade_eligible,o.state,o.payload,o.created_at,p.entry,p.exit_price,"
        "p.r_multiple,p.filled_at,p.closed_at,p.outcome,p.stop,p.realised_usd,"
        "p.fees_price_units,p.funding_price_units,p.slippage_price_units FROM execution_outbox o "
        "LEFT JOIN paper_positions p USING(intent_id) WHERE o.mode='PAPER' ORDER BY o.id DESC").fetchall()
    keys = ("intent_id", "setup_id", "attempt_id", "account_epoch_id", "origin", "controller",
            "grade_eligible", "state", "payload", "created_at", "entry", "exit_price",
            "r_multiple", "filled_at", "closed_at", "outcome", "current_stop", "realised_usd",
            "fees_price_units", "funding_price_units", "slippage_price_units")
    result = []
    for raw in rows:
        row = dict(zip(keys, raw))
        if not include_legacy and epoch and row["account_epoch_id"] != epoch["id"]:
            continue
        row["plan"] = json.loads(row.pop("payload"))
        row["grade_eligible"] = bool(row["grade_eligible"])
        result.append(row)
    return result


def sync_manual(con, symbol=None, tf=None):
    """Project the manual resolver's results, never run a second exit model.

    Idempotent upserts bridge a crash after the append-only result was saved.
    Readers still see a reservation until this bridge completes; money cannot
    be spent twice during that gap.
    """
    from . import manual
    ensure(con)
    with immediate(con):
        intents = {}
        for r in manual._facts(con, manual.INTENT_KIND, symbol, tf):
            p = json.loads(r["payload"])
            intents[p["intent_id"]] = (p, r["symbol"], r["tf"])
        exits = {}
        for r in manual._facts(con, manual.EXEC_KIND, symbol, tf):
            p = json.loads(r["payload"])
            exits.setdefault(p["intent_id"], (p, r["confirmed_at"]))
        open_rows = {}
        for sym, frame in {(s, t) for _, s, t in intents.values()}:
            for p in manual.status(con, sym, frame, manual._tf_seconds_of(frame)):
                open_rows[p["intent_id"]] = p
        for iid, (intent, sym, frame) in intents.items():
            outbox = con.execute("SELECT state FROM execution_outbox WHERE intent_id=?", (iid,)).fetchone()
            if not outbox or outbox[0] in TERMINAL:
                continue  # Explicit legacy cutover blocker; do not invent ancestry.
            con.execute("UPDATE execution_outbox SET origin='OPERATOR',controller='OPERATOR',"
                        "grade_eligible=0 WHERE intent_id=?", (iid,))
            if iid in exits:
                result, closed_at = exits[iid]
                state = ("PAPER_EXPIRED" if result["outcome"] == "MISSED" else
                         "CANCELLED" if result["outcome"] == "CANCELLED" else "PAPER_CLOSED")
                if state == "PAPER_CLOSED":
                    realised = result.get("realised_usd")
                    if realised is None and result.get('legs') and intent.get('size_units'):
                        realised = str(manual.settled_dollars(result['legs'], result['entry'],
                            intent['size_units'], intent['direction'] == 'LONG'))
                    con.execute("INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,"
                        "entry,stop,target,state,filled_at,closed_at,outcome,exit_price,r_multiple,"
                        "fees_price_units,funding_price_units,slippage_price_units,realised_usd) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(intent_id) DO UPDATE SET "
                        "state=excluded.state,closed_at=excluded.closed_at,outcome=excluded.outcome,"
                        "exit_price=excluded.exit_price,r_multiple=excluded.r_multiple,"
                        "fees_price_units=excluded.fees_price_units,funding_price_units=excluded.funding_price_units,"
                        "slippage_price_units=excluded.slippage_price_units,realised_usd=excluded.realised_usd",
                        (iid, sym, frame, intent["direction"], intent.get("size_units") or "0",
                         result["entry"], intent["sl"], intent["tp"], "CLOSED",
                         result.get("fill_ts") or intent["armed_at"], closed_at, result["outcome"],
                         result.get("exit_price"), result["r_multiple"], result.get("fees_price_units"),
                         result.get("funding_price_units"), result.get("slippage_price_units"), realised))
            elif iid in open_rows and open_rows[iid]["state"] == "OPEN":
                p = open_rows[iid]
                state = "PAPER_FILLED"
                con.execute("INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,"
                    "entry,stop,target,state,filled_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(intent_id) DO UPDATE SET stop=excluded.stop",
                    (iid, sym, frame, intent["direction"], intent.get("size_units") or "0",
                     p["entry"], p["current_stop"], p["tp"], "OPEN", p["fill_ts"]))
            else:
                continue
            if outbox[0] != state:
                now = int(time.time())
                con.execute("UPDATE execution_outbox SET state=?,updated_at=? WHERE intent_id=?", (state, now, iid))
                con.execute("INSERT INTO execution_events(intent_id,event,occurred_at,payload) VALUES(?,?,?,?)",
                            (iid, state, now, json.dumps({"authority": "manual", "bridged": True})))


def recover_pending(con):
    """Recover committed PAPER reservations without rebuilding candidate lists.

    Private SUBMITTING rows are deliberately untouched: they require venue
    reconciliation. Only definitely unsent PENDING bot orders can expire here.
    """
    ensure(con)
    now = int(time.time())
    recovered = []
    with immediate(con):
        for iid, raw in con.execute("SELECT intent_id,payload FROM execution_outbox "
            "WHERE mode='PAPER' AND state='PENDING' AND origin='BOT' "
            "AND setup_id NOT LIKE 'manual:%'").fetchall():
            plan = execution._plan_from_wire(raw)
            if plan is None:
                continue  # Unreadable reservations remain visible and held.
            state = ("PAPER_EXPIRED" if plan.intent.expires_at is not None and
                     plan.intent.expires_at <= now else "PAPER_ROUTED")
            con.execute("UPDATE execution_outbox SET state=?,updated_at=? WHERE intent_id=? AND state='PENDING'",
                        (state, now, iid))
            con.execute("INSERT INTO execution_events(intent_id,event,occurred_at,payload) VALUES(?,?,?,?)",
                        (iid, state, now, json.dumps({"recovery": True})))
            recovered.append({"intent_id": iid, "state": state})
    return recovered


def change_controller(con, intent_id, controller):
    if controller not in ("BOT", "OPERATOR"):
        raise AdmissionRejected("controller must be BOT or OPERATOR")
    ensure(con)
    with immediate(con):
        row = con.execute("SELECT o.origin,o.controller,p.state,p.stop,o.account_epoch_id "
            "FROM execution_outbox o JOIN paper_positions p USING(intent_id) "
            "WHERE o.intent_id=? AND o.mode='PAPER'", (intent_id,)).fetchone()
        if not row or row[2] != "OPEN":
            raise AdmissionRejected("CONTROL_UNAVAILABLE: no open paper position")
        if controller == "BOT" and (row[0] != "BOT" or not row[3]):
            raise AdmissionRejected("BOT_CONTROL_UNSUPPORTED: no original bot protection")
        con.execute("UPDATE execution_outbox SET controller=?,grade_eligible=0 WHERE intent_id=?",
                    (controller, intent_id))
        con.execute("INSERT INTO account_events(epoch_id,occurred_at,event,payload) VALUES(?,?,?,?)",
                    (row[4], int(time.time()), "CONTROL_HANDOFF",
                     json.dumps({"intent_id": intent_id, "from": row[1], "to": controller})))
    return {"intent_id": intent_id, "controller": controller, "grade_eligible": False}


def close_paper(con, intent_id):
    """Close the selected account's real paper position at its latest closed bar.

    Manual ladder legs retain their own fills and costs. This never writes an
    override against the research replay or submits a private venue order.
    """
    from . import costs, manual, store
    ensure(con)
    # Settle previously observed natural outcomes before considering a new
    # discretionary close. The monitor excludes manual orders by construction.
    execution.monitor_paper(con)
    with immediate(con):
        raw = con.execute("SELECT o.payload,o.origin,o.account_epoch_id,p.state,p.entry,p.filled_at,p.entry_role "
            "FROM execution_outbox o JOIN paper_positions p USING(intent_id) "
            "WHERE o.intent_id=? AND o.mode='PAPER'", (intent_id,)).fetchone()
        if raw is None:
            raise AdmissionRejected("NO_OPEN_POSITION: an unfilled order must be cancelled")
        if raw[3] == "CLOSED":
            return {"intent_id": intent_id, "state": "PAPER_CLOSED", "duplicate": True}
        plan = execution._plan_from_wire(raw[0])
        if plan is None:
            raise AdmissionRejected("UNREADABLE_POSITION_PLAN")
        intent = plan.intent
        epoch = current_epoch(con)
        if epoch and raw[2] != epoch["id"]:
            raise AdmissionRejected("ACCOUNT_MISMATCH")
        candles = [dict(r) for r in store.get_candles(con, intent.symbol, intent.timeframe)]
        if not candles:
            raise AdmissionRejected("MISSING_EXIT_MARK")
        seconds = manual._tf_seconds_of(intent.timeframe)
        fill_i = next((n for n, c in enumerate(candles) if c["open_ts"] >= raw[5]), 0)
        partials = []
        manual_intent = None
        if raw[1] == "OPERATOR":
            manual_intent = manual._intent_by_id(con, intent.symbol, intent.timeframe, intent_id)
            if manual_intent is None:
                raise AdmissionRejected("MISSING_MANUAL_PLAN")
            # If the manual resolver already owns a terminal fact, do not
            # append another outcome. Its projection recovers on the next pass.
            for fact in manual._facts(con, manual.EXEC_KIND, intent.symbol, intent.timeframe):
                if json.loads(fact["payload"])["intent_id"] == intent_id:
                    raise AdmissionRejected("SETTLEMENT_PENDING: refresh the journal")
            base = {"tf": intent.timeframe, "tf_seconds": seconds, "candles": candles,
                    "candle_times": [c["open_ts"] for c in candles], "scale": 1, "atr": None}
            res, _ = manual._resolution(base, manual._finer_series(con, intent.symbol,
                                        intent.timeframe, seconds), manual_intent)
            candles, seconds = res["candles"], res["tf_seconds"]
            walked = manual._walk(manual_intent, candles, res["candle_times"], seconds,
                max_entry_bars=manual.MAX_ENTRY_BARS * res["scale"], max_bars=manual.MAX_BARS * res["scale"])
            if walked["phase"] != "OPEN":
                raise AdmissionRejected("SETTLEMENT_PENDING: refresh the journal")
            fill_i, partials = walked["fill_i"], walked.get("partials") or []
        entry = Decimal(raw[4])
        per_unit = abs(entry - intent.stop)
        if per_unit <= 0:
            raise AdmissionRejected("INVALID_ORIGINAL_RISK")
        last = candles[-1]
        closed_at = last["open_ts"] + seconds
        profile = costs.profile_for(intent.symbol)
        atr = manual.compute_atr(candles)
        atr_exit = atr[-1] if atr else None
        long = intent.direction == "LONG"
        legs = [manual.settle_leg(profile, intent.symbol, entry, f["price"], per_unit,
            long, f["fraction"], "PARTIAL", "PARTIAL", "LIMIT", None,
            f["exit_i"] - fill_i, seconds, candles[f["exit_i"]]["open_ts"] + seconds,
            raw[6] or "MAKER") for f in partials]
        remainder = Decimal(1) - sum((f["fraction"] for f in partials), Decimal(0))
        legs.append(manual.settle_leg(profile, intent.symbol, entry, Decimal(last["close"]),
            per_unit, long, remainder, "REMAINDER", "CLOSED_EARLY", "MARKET", atr_exit,
            max(0, len(candles) - 1 - fill_i), seconds, closed_at, raw[6] or "MAKER"))
        result = {"intent_id": intent_id, "source": "OPERATOR", "direction": intent.direction,
            "realised_usd": str(manual.settled_dollars(legs, entry, intent.quantity, long)),
            "outcome": "CLOSED_EARLY", "entry": str(entry), "exit_price": last["close"],
            "r_multiple": str(manual.blend_r(legs, "r_net")), "r_gross": str(manual.blend_r(legs, "r_gross")),
            "legs": legs, "fill_ts": raw[5], "closed_at": closed_at,
            "fees_price_units": str(manual._weighted(legs, "fees_price_units")),
            "funding_price_units": str(manual._weighted(legs, "funding_price_units")),
            "slippage_price_units": str(manual._weighted(legs, "slippage_price_units")),
            "slippage_missing": atr_exit is None, "risk_usd": str(plan.risk.risk_usd),
            "size_units": str(intent.quantity), "bars_held": max(0, len(candles) - 1 - fill_i)}
        if manual_intent is not None:
            store.insert_fact(con, symbol=intent.symbol, tf=intent.timeframe, kind=manual.EXEC_KIND,
                market_time=manual_intent["armed_at"], confirmed_at=closed_at,
                algo_version=manual.MANUAL_VERSION, payload=result)
        con.execute("UPDATE paper_positions SET state='CLOSED',closed_at=?,outcome='CLOSED_EARLY',"
            "exit_price=?,r_multiple=?,fees_price_units=?,funding_price_units=?,slippage_price_units=?,realised_usd=? "
            "WHERE intent_id=? AND state='OPEN'", (closed_at, result["exit_price"], result["r_multiple"],
            result["fees_price_units"], result["funding_price_units"], result["slippage_price_units"], result["realised_usd"], intent_id))
        con.execute("UPDATE execution_outbox SET state='PAPER_CLOSED',controller='OPERATOR',"
                    "grade_eligible=0,updated_at=? WHERE intent_id=?", (int(time.time()), intent_id))
        con.execute("INSERT INTO execution_events(intent_id,event,occurred_at,payload) VALUES(?,?,?,?)",
                    (intent_id, "PAPER_CLOSED", int(time.time()), json.dumps(result)))
    return {"intent_id": intent_id, "state": "PAPER_CLOSED", "result": result, "duplicate": False}
