"""Real SQLite admission seam: scratch stores only, including OS-process races."""
import json
import multiprocessing
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from engine import automation, execution, manual, paperbook, shared_account, store
from engine.contracts import AutomationMode, DecisionReason, ExecutionPlan, OrderIntent, OrderKind, RiskDecision


def bot_plan(key="bot", amount="200"):
    now = int(time.time())
    q = Decimal(amount) / Decimal(2)
    i = OrderIntent(key, key, AutomationMode.PAPER, "BTCUSDT", "LONG", OrderKind.LIMIT,
        q, Decimal(100), Decimal(98), (Decimal(104),), False, now, "test", key,
        timeframe="1H", attempt_id="attempt-" + key, expires_at=now + 86400)
    r = RiskDecision(True, "APPROVED", Decimal(amount), q, q * 100, q / 100,
        (DecisionReason("OK", "fixture strategy approval"),), Decimal(10000), "PAPER_LEDGER")
    return ExecutionPlan(i, r, "phemex-perp", "ISOLATED", "ONE_WAY")


def account(tmp_path):
    con = store.connect(tmp_path / "account.db")
    shared_account.ensure(con)
    automation.transition(con, "PAPER", expected_revision=0)
    con.commit()
    return con


def arm(con, symbol="ETHUSDT", at=None, risk_usd="25"):
    return manual.create_intent(con, symbol, "1H", "LONG", 100, 104, 98,
                               at if at is not None else int(time.time()), risk_usd=risk_usd)


def race_worker(path, origin, start, result):
    con = store.connect(Path(path))
    start.wait(20)
    try:
        if origin == "BOT":
            shared_account.admit_plan(con, bot_plan())
        else:
            arm(con)
        result.put((origin, "admitted"))
    except (shared_account.AdmissionRejected, manual.IntentRejected) as exc:
        result.put((origin, str(exc)))
    finally:
        con.close()


def test_two_os_processes_compete_for_one_slot(tmp_path):
    con = account(tmp_path)
    con.close()
    ctx = multiprocessing.get_context("spawn")
    start, results = ctx.Barrier(3), ctx.Queue()
    workers = [ctx.Process(target=race_worker, args=(str(tmp_path / "account.db"),
                origin, start, results)) for origin in ("BOT", "OPERATOR")]
    for p in workers:
        p.start()
    start.wait(20)
    responses = [results.get(timeout=30) for _ in workers]
    for p in workers:
        p.join(30)
        assert p.exitcode == 0
    assert sum(message == "admitted" for _, message in responses) == 1
    assert any("CONCURRENT_LIMIT(1)" in message for _, message in responses)
    con = store.connect(tmp_path / "account.db")
    assert con.execute("SELECT count(*) FROM execution_outbox").fetchone()[0] == 1
    assert paperbook.snapshot(con)["reserved_slots"] == 1
    con.close()


@pytest.mark.parametrize("first", ["BOT", "OPERATOR"])
def test_both_origins_share_gate_in_both_orders(tmp_path, first):
    con = account(tmp_path)
    if first == "BOT":
        shared_account.admit_plan(con, bot_plan())
        with pytest.raises(manual.IntentRejected, match="CONCURRENT_LIMIT"):
            arm(con)
    else:
        arm(con)
        with pytest.raises(shared_account.AdmissionRejected, match="CONCURRENT_LIMIT"):
            shared_account.admit_plan(con, bot_plan())
    assert con.execute("SELECT count(*) FROM execution_outbox").fetchone()[0] == 1


def test_duplicate_is_a_receipt_even_while_draining(tmp_path):
    con = account(tmp_path)
    original = arm(con, at=100)
    shared_account.request_cutover(con, "drain")
    replay = arm(con, at=100)
    assert replay["intent_id"] == original["intent_id"]
    assert replay["execution_receipt"]["duplicate"]
    with pytest.raises(manual.IntentRejected, match="REQUEST_CONFLICT"):
        arm(con, at=100, risk_usd="24")
    assert con.execute("SELECT count(*) FROM execution_outbox").fetchone()[0] == 1


def test_cutover_is_explicit_resumable_and_preserves_configured_risk(tmp_path):
    con = account(tmp_path)
    assert shared_account.current_epoch(con) is None
    assert shared_account.gates_for_account(con)["risk_pct"] == Decimal(".02")
    shared_account.set_risk_percent(con, "0.25", "legacy", "0.02")
    arm(con, at=100)
    shared_account.request_cutover(con, "drain")
    con.close()
    con = store.connect(tmp_path / "account.db")
    with pytest.raises(shared_account.AdmissionRejected, match="CUTOVER_WAITING"):
        shared_account.request_cutover(con, "complete")
    with pytest.raises(manual.IntentRejected, match="DRAINING"):
        arm(con, at=101)
    shared_account.request_cutover(con, "resume")
    assert shared_account.current_epoch(con)["state"] == "OPEN"
    manual.cancel_intent(con, "ETHUSDT|1H|MANUAL|100", at=102)
    shared_account.request_cutover(con, "drain")
    shared_account.request_cutover(con, "complete")
    assert shared_account.gates_for_account(con)["risk_pct"] == Decimal(".0025")
    plan, _ = shared_account.admit_plan(con, bot_plan())
    assert plan.risk.risk_usd == Decimal(25)
    assert plan.intent.quantity == Decimal("12.5")
    assert con.execute("SELECT count(*) FROM account_epochs WHERE state='SEALED'").fetchone()[0] == 1
    assert paperbook.snapshot(con)["equity"] == Decimal(10000)
    assert len(shared_account.journal(con)) == 1
    assert len(shared_account.journal(con, include_legacy=True)) == 2


def test_crash_pending_recovers_without_candidate_and_expiry_releases(tmp_path):
    con = account(tmp_path)
    p, _ = shared_account.admit_plan(con, bot_plan())
    con.close()
    con = store.connect(tmp_path / "account.db")
    assert shared_account.recover_pending(con)[0]["state"] == "PAPER_ROUTED"
    assert shared_account.recover_pending(con) == []
    assert paperbook.snapshot(con)["reserved_slots"] == 1
    # Separate reservation created before a simulated downtime.
    con.execute("UPDATE execution_outbox SET state='PAPER_CLOSED'")
    con.commit()
    p, _ = shared_account.admit_plan(con, bot_plan("next"))
    raw = json.loads(con.execute("SELECT payload FROM execution_outbox WHERE intent_id='next'").fetchone()[0])
    raw["intent"]["expires_at"] = 1
    con.execute("UPDATE execution_outbox SET payload=? WHERE intent_id='next'", (json.dumps(raw),))
    con.commit()
    assert shared_account.recover_pending(con)[0]["state"] == "PAPER_EXPIRED"
    assert paperbook.snapshot(con)["reserved_slots"] == 0


def test_manual_resolution_settles_shared_cash_exactly_once(tmp_path):
    con = account(tmp_path)
    arm(con, at=0)
    con.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)", [
        ("ETHUSDT", "1H", t, "100", hi, "99", "100", "1", "test", t + 3600)
        for t, hi in [(0, "101"), (3600, "101"), (7200, "105")]])
    con.commit()
    manual.run(con, "ETHUSDT", "1H", 3600)
    first = paperbook.snapshot(con)
    assert first["closed_count"] == 1 and first["equity"] > Decimal(10000)
    shared_account.sync_manual(con)
    assert paperbook.snapshot(con)["equity"] == first["equity"]
    row = shared_account.journal(con)[0]
    assert row["origin"] == row["controller"] == "OPERATOR"
    assert row["grade_eligible"] is False
    assert row["state"] == "PAPER_CLOSED"


def test_failure_between_fact_and_reservation_rolls_back_both(tmp_path, monkeypatch):
    con = account(tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError("simulated crash")
    monkeypatch.setattr(execution, "enqueue", fail)
    with pytest.raises(RuntimeError, match="simulated crash"):
        arm(con)
    assert con.execute("SELECT count(*) FROM facts WHERE kind='manual_intent'").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM account_requests").fetchone()[0] == 0


def test_market_fill_cash_uses_exact_settlement_and_late_route_cannot_reopen(tmp_path, monkeypatch):
    con = account(tmp_path)
    plan = bot_plan('gap')
    at = (int(time.time()) // 3600) * 3600 - 7200
    plan = replace(plan, intent=replace(plan.intent, created_at=at + 1,
        order_kind=OrderKind.MARKET, entry_model='MARKET_NEXT_OPEN'))
    con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
        ('BTCUSDT','1H',at+3600,'102','105','101','104','1','fixture',at+7200))
    con.commit()
    admit = shared_account.admit_plan
    def recovered_before_dispatch_returns(connection, candidate):
        approved, receipt = admit(connection, candidate)
        execution.monitor_paper(connection)
        return approved, receipt
    monkeypatch.setattr(shared_account, 'admit_plan', recovered_before_dispatch_returns)
    receipt = execution.Coordinator().dispatch(con, plan)
    assert receipt['state'] == 'ORDER_LIFECYCLE_COMPLETE'
    position = con.execute('SELECT realised_usd,r_multiple,state FROM paper_positions').fetchone()
    assert Decimal(position[0]) == Decimal('192.8400')
    assert Decimal(position[1]) == Decimal('.48')
    assert position[2] == 'CLOSED'
    assert paperbook.snapshot(con)['equity'] == Decimal('10192.8400')
    execution.monitor_paper(con)
    assert con.execute('SELECT count(*) FROM paper_positions').fetchone()[0] == 1


def test_journal_exposes_current_and_planned_protection_separately(tmp_path):
    con = account(tmp_path)
    shared_account.admit_plan(con, bot_plan())
    con.execute("INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,entry,stop,target,state,filled_at) "
                "VALUES('bot','BTCUSDT','1H','LONG','100','100','101','104','OPEN',100)")
    con.commit()
    from ui_api import trade_rows
    row = trade_rows(con)[0]
    assert row['stop'] == '101' and row['planned_stop'] == '98'


def test_handoff_latches_grade_ineligible(tmp_path):
    con = account(tmp_path)
    shared_account.admit_plan(con, bot_plan())
    con.execute("INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,entry,stop,target,state,filled_at) "
                "VALUES('bot','BTCUSDT','1H','LONG','100','100','98','104','OPEN',100)")
    con.commit()
    shared_account.change_controller(con, "bot", "OPERATOR")
    shared_account.change_controller(con, "bot", "BOT")
    row = shared_account.journal(con)[0]
    assert row["origin"] == row["controller"] == "BOT"
    assert row["grade_eligible"] is False


def test_untracked_legacy_manual_blocks_cutover(tmp_path):
    con = account(tmp_path)
    manual._create_intent_legacy(con, "ETHUSDT", "1H", "LONG", 100, 104, 98, 0, risk_usd=25)
    shared_account.request_cutover(con, "drain")
    with pytest.raises(shared_account.AdmissionRejected, match="legacy-manual"):
        shared_account.request_cutover(con, "complete")


def test_shared_bot_close_is_account_scoped_and_idempotent(tmp_path, monkeypatch):
    con = account(tmp_path)
    plan = bot_plan()
    shared_account.admit_plan(con, plan)
    opened_at = ((plan.intent.created_at + 3599) // 3600) * 3600
    con.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("BTCUSDT", "1H", opened_at,
                 "100", "102", "99", "101", "1", "test", opened_at + 3600))
    con.commit()
    monkeypatch.setattr('engine.execution.time.time',lambda:opened_at + 3600)
    execution.monitor_paper(con)
    closed = shared_account.close_paper(con, "bot")
    assert closed["state"] == "PAPER_CLOSED"
    assert shared_account.close_paper(con, "bot")["duplicate"]
    assert paperbook.snapshot(con)["closed_count"] == 1
    assert not shared_account.journal(con)[0]["grade_eligible"]
    assert con.execute("SELECT count(*) FROM facts WHERE kind='manual_override'").fetchone()[0] == 0


def test_manual_partials_cash_and_close_preserve_ladder(tmp_path):
    con = account(tmp_path)
    manual.create_intent(con, "ETHUSDT", "1H", "LONG", 100, 108, 98, 0, risk_usd=25,
                         partials=[{"fraction": "0.5", "price": "102"}])
    con.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)", [
        ("ETHUSDT", "1H", t, "100", hi, "99", close, "1", "test", t + 3600)
        for t, hi, close in [(0, "101", "100"), (3600, "101", "100"), (7200, "103", "103")]])
    con.commit()
    manual.run(con, "ETHUSDT", "1H", 3600)
    mark = paperbook.snapshot(con)
    assert mark["partial_realised_usd"] > 0
    assert mark["cash"] > mark["settled_balance"]
    assert mark["marked_equity"] > mark["cash"]
    closed = shared_account.close_paper(con, "ETHUSDT|1H|MANUAL|0")
    assert len(closed["result"]["legs"]) == 2
    before = paperbook.snapshot(con)["equity"]
    manual.run(con, "ETHUSDT", "1H", 3600)
    assert paperbook.snapshot(con)["equity"] == before
    assert paperbook.snapshot(con)["partial_realised_usd"] == 0


def test_risk_change_preserves_existing_orders_and_rejects_stale_settings(tmp_path):
    con = account(tmp_path)
    arm(con, at=100, risk_usd="100")
    before = con.execute("SELECT payload FROM execution_outbox").fetchone()[0]
    shared_account.set_risk_percent(con, "0.5", "legacy", "0.02")
    assert con.execute("SELECT payload FROM execution_outbox").fetchone()[0] == before
    assert paperbook.snapshot(con)["reserved_risk_usd"] == Decimal("100")
    assert shared_account.gates_for_account(con)["risk_pct"] == Decimal(".005")
    with pytest.raises(shared_account.AdmissionRejected, match="ACCOUNT_CHANGED"):
        shared_account.set_risk_percent(con, "1", "legacy", "0.02")
    assert con.execute("SELECT count(*) FROM account_events WHERE event='RISK_CHANGED'").fetchone()[0] == 1
    manual.cancel_intent(con, "ETHUSDT|1H|MANUAL|100", at=101)
    plan, _ = shared_account.admit_plan(con, bot_plan())
    assert plan.risk.risk_usd == Decimal("50")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "101", None, "bad"])
def test_invalid_risk_does_not_change_account(tmp_path, value):
    con = account(tmp_path)
    with pytest.raises(shared_account.AdmissionRejected):
        shared_account.set_risk_percent(con, value, "legacy", "0.02")
    assert shared_account.current_epoch(con) is None


def test_risk_decision_records_changed_percentage_even_when_size_is_capped():
    from engine import riskpaper
    old = dict(decision="REDUCED", reasons=["LEVERAGE_CAP"], risk_usd="25",
               units="12.5", risk_pct="0.0025", account_epoch_id="one")
    assert riskpaper._moved(old, {**old, "risk_pct":"0.005"})
    assert riskpaper._moved(old, {**old, "account_epoch_id":"two"})
    assert not riskpaper._moved(old, dict(old))


def test_the_account_gates_are_the_ones_the_surfaces_read(tmp_path):
    """The read models must describe the envelope the bot ENFORCES.

    `riskpaper.run` gates on `gates_for_account`, which overrides risk_pct and
    the three limits derived from it off the active epoch. Six server read
    models asked `risk.gates_for_mode(PAPER)` instead — the fixed 2% default.
    They agreed only while no epoch row existed, which was true right up until
    the operator used the risk control that shipped with this account layer.

    At 0.25% the real daily-loss limit is 1% of day-start equity and the
    surfaces reported 8%. The order ticket was the one that costs a trade
    rather than a wrong label: it would size against a budget the book then
    refuses.
    """
    from engine import risk
    from engine.contracts import AutomationMode as Mode

    con = account(tmp_path)
    default = risk.gates_for_mode(Mode.PAPER)
    assert shared_account.gates_for_account(con) == default, (
        "with no epoch the account gates ARE the mode default — that fallback "
        "is what makes reading the account authority safe everywhere")

    shared_account.set_risk_percent(con, "0.25", "legacy", str(default["risk_pct"]))
    gates = shared_account.gates_for_account(con)

    assert gates["risk_pct"] == Decimal("0.0025")
    assert gates != default, "the epoch must actually move the envelope"
    for limit in ("daily_loss_limit_pct", "max_total_open_risk_pct"):
        assert gates[limit] != default[limit], (
            f"{limit} is derived from risk_pct and must move with it — a "
            f"surface reading the default reports it eight times too wide")
    # `scale_risk_pct` is SCALE_ADD_R x risk_pct and SCALE_ADD_R is zero
    # (pyramiding forbidden by contract, risk.py), so it is zero at every
    # percentage. It moves with risk_pct the day that contract changes, which
    # is why it is derived rather than pinned.
    assert gates["scale_risk_pct"] == 0 == default["scale_risk_pct"]


def test_an_adopted_engine_position_does_not_freeze_the_account(tmp_path):
    """One Adopt used to stop the whole book admitting anything.

    `manual.adopt_position` lays the operator's exit levels over a position the
    RESEARCH replay is simulating — no outbox row and no paper capital behind
    it, by construction. `_legacy_untracked` read that as untracked manual
    exposure, so `_decision` raised LEGACY_EXPOSURE on every later admission,
    bot and manual alike, until the adoption settled. On a 1D chart that is
    days of a book that silently refuses every order while the autotrader
    reports "0 routed, N refused".

    A genuine pre-account manual arm must still block — it really did occupy
    the account — so this pins both halves.
    """
    con = account(tmp_path)
    manual.adopt_position(
        con, "BTCUSDT|1H|REV|900", "BTCUSDT", "1H", "LONG",
        entry=Decimal("100"), sl=Decimal("98"), tp=Decimal("104"),
        original_sl=Decimal("98"), fill_ts=900, adopted_at=1000,
        risk_usd=Decimal("25"))
    con.commit()

    adopted = [p for plans in manual.unresolved(con).values() for p in plans
               if p.get("state") == "ADOPTED"]
    assert adopted, "fixture did not actually create an adopted intent"
    assert not shared_account._legacy_untracked(con), (
        "an adopted overlay on a replay position is not this account's "
        "untracked exposure")
    assert not shared_account.cutover_blockers(con, "legacy"), (
        "an adoption must not become a permanent cutover blocker either")

    after, _ = shared_account.admit_plan(con, bot_plan(key="after"))
    assert after.risk.approved, "the account froze after an adoption"

    # ...and the guard still does its job for real manual exposure: a manual
    # intent fact with no outbox row behind it, which is what the pre-account
    # book left lying around.
    con.execute("UPDATE execution_outbox SET state='PAPER_CLOSED'")
    con.commit()
    arm(con, at=4242)
    con.execute("DELETE FROM execution_outbox WHERE intent_id LIKE '%MANUAL%'")
    con.commit()
    assert shared_account._legacy_untracked(con), (
        "a manual arm with no outbox row IS untracked exposure and must "
        "still close the gate")
