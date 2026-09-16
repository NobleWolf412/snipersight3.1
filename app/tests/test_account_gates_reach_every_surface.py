"""Every surface that states the envelope must state the ACCOUNT's envelope.

`riskpaper.run` enforces `shared_account.gates_for_account` — risk_pct off the
active epoch, and the three limits derived from it. Seven places in `server.py`
asked `risk.gates_for_mode(PAPER)` instead, which is the fixed 2% default. They
agreed only while no epoch row existed, which was true right up until the
operator used the risk control that shipped with the account layer.

At a saved 0.25% the real daily-loss limit is 1% of day-start equity and every
one of those surfaces reported 8%. `/api/trade-config` is the one that costs a
trade rather than a wrong label: it sizes the order ticket, so it would offer a
position the book then refuses.

The swap itself was made and shipped with nothing exercising it end to end —
the engine helper had a test, the seven call sites had none. This is that test.
It runs against a scratch store through the same guarded fixture
`test_cockpit_api` uses: `scratch()` asserts no other database is ever opened,
so a patch that silently stopped applying becomes a red test rather than a read
of the operator's real book.
"""
from decimal import Decimal
import time
from unittest.mock import patch

import pytest

from engine import automation, risk, shared_account, store
from engine.contracts import AutomationMode

import server


#: What the epoch is set to, and what the mode default would have been.
ACCOUNT_PCT = Decimal("0.0025")
DEFAULT_PCT = Decimal("0.02")


@pytest.fixture
def account(tmp_path):
    path = tmp_path / "gates.db"
    connect = store.connect
    con = connect(path)
    shared_account.ensure(con)
    automation.transition(con, "PAPER", expected_revision=0)
    shared_account.set_risk_percent(con, "0.25", "legacy", "0.02")
    con.commit()

    def scratch(db_path=None):
        assert db_path in (None, path), "test tried to open another database"
        return connect(path)

    with patch("engine.store.connect", side_effect=scratch):
        yield con
    con.close()


def test_the_fixture_actually_moved_the_envelope(account):
    """The guard on every assertion below. If the epoch stopped applying,
    every other test here would pass by comparing two identical defaults."""
    gates = shared_account.gates_for_account(account)
    default = risk.gates_for_mode(AutomationMode.PAPER)
    assert gates["risk_pct"] == ACCOUNT_PCT
    assert default["risk_pct"] == DEFAULT_PCT
    assert gates["daily_loss_limit_pct"] != default["daily_loss_limit_pct"]
    assert gates["max_total_open_risk_pct"] != default["max_total_open_risk_pct"]


def test_the_order_ticket_sizes_on_the_account(account):
    """The site where the split costs a trade, not a label."""
    cfg = server.trade_config("ETHUSDT", "1H")
    gates = shared_account.gates_for_account(account)

    assert Decimal(str(cfg["risk_pct"])) == ACCOUNT_PCT, (
        "the ticket offered a position sized on the 2% default while the book "
        "enforces the account's percentage — it would be refused on arm")
    assert Decimal(str(cfg["max_total_risk_pct"])) == gates["max_total_open_risk_pct"]
    assert Decimal(str(cfg["daily_loss_pct"])) == gates["daily_loss_limit_pct"]
    assert Decimal(str(cfg["risk_pct"])) != DEFAULT_PCT


def test_the_envelope_config_reports_the_account(account):
    env = server._envelope_config(account, 10000.0)
    # `_envelope_config` reports risk_pct as a PERCENTAGE, not a fraction.
    assert Decimal(str(env["risk_pct"])) == ACCOUNT_PCT * 100
    assert Decimal(str(env["daily_loss_pct"])) != DEFAULT_PCT * 4 * 100


def test_the_paper_book_halts_on_the_accounts_daily_limit(account):
    """BEHAVIOUR, not a label — the one assertion that proves the swap did
    something.

    The gates reach `_paper_account` through `paperbook.snapshot`, where
    `daily_loss_limit_pct` decides `halted_days`. At the account's 0.25% the
    daily limit is 1% of day-start equity ($100 on the opening $10,000); at the
    2% mode default it is 8% ($800). A single -$200 day therefore halts the
    book under the gates the bot enforces and does not under the ones this
    surface used to read — so the operator's screen would have said trading was
    fine while `riskpaper` had stopped taking entries.
    """
    day_loss = Decimal("-200")
    now = int(time.time())
    account.execute(
        # account_epoch_id is not optional here: `paperbook.snapshot` scopes
        # the outbox to the CURRENT epoch, and `set_risk_percent` minted
        # "legacy" before this row existed — so an unstamped row belongs to no
        # epoch and is invisible, which is the separation working, not a
        # fixture convenience.
        "INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,"
        "symbol,payload,state,created_at,updated_at,account_epoch_id) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("halt", "halt", "PAPER", "s-halt", "ETHUSDT",
         '{"risk": {"risk_usd": "25"}}', "PAPER_CLOSED", now, now, "legacy"))
    account.execute(
        "INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,"
        "entry,stop,target,state,filled_at,closed_at,outcome,exit_price,"
        "r_multiple,realised_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("halt", "ETHUSDT", "1H", "LONG", "1", "100", "98", "104", "CLOSED",
         now, now, "SL", "98", "-8", str(day_loss)))
    account.commit()

    book = server._paper_account(account)
    assert book["closed_trades"] == 1, "fixture did not reach the read model"
    assert Decimal(book["realised_today"]) == day_loss

    gates = shared_account.gates_for_account(account)
    default = risk.gates_for_mode(AutomationMode.PAPER)
    opening = Decimal(book["opening_equity"])
    assert -day_loss > gates["daily_loss_limit_pct"] * opening, (
        "fixture must breach the ACCOUNT limit or it proves nothing")
    assert -day_loss < default["daily_loss_limit_pct"] * opening, (
        "and must NOT breach the mode default, or both gates agree and the "
        "test cannot tell them apart")

    assert book["halted_today"] is True, (
        "the book is halted by the gates riskpaper enforces; a surface reading "
        "the 2% default would report trading as fine while the bot refused "
        "every entry")


def test_the_guardrail_panel_reports_the_account(account):
    cfg = server.get_settings()["values"]["risk_config"]
    gates = shared_account.gates_for_account(account)
    assert Decimal(str(cfg["daily_loss_pct"])) == gates["daily_loss_limit_pct"] * 100
    assert Decimal(str(cfg["max_total_risk_pct"])) == gates["max_total_open_risk_pct"] * 100
    assert Decimal(str(cfg["daily_loss_pct"])) != DEFAULT_PCT * 4 * 100, (
        "the panel shows engine-owned limits beside the operator's own; "
        "showing the mode default there tells them a limit the bot will not "
        "enforce")


def test_no_surface_still_reads_the_mode_default(account):
    """Derived from the SOURCE, so a new surface added tomorrow is covered.

    The seven sites were found by grep, and a list of seven fixed strings
    would not survive the eighth. `risk.gates_for_mode` is legitimate inside
    `shared_account.gates_for_account` (it is the fallback when no epoch
    exists) and in the engines that describe a MODE rather than the account;
    it is not legitimate in a server read model.
    """
    import inspect
    import re

    src = inspect.getsource(server)
    offenders = []
    for match in re.finditer(r"gates_for_mode\s*\(\s*(?:risk\.|contracts\.)?"
                             r"AutomationMode\.PAPER\s*\)", src):
        line = src.count("\n", 0, match.start()) + 1
        offenders.append(line)
    assert not offenders, (
        f"server.py still asks the mode default for the PAPER envelope at "
        f"line(s) {offenders} — the account's gates are the ones the bot "
        f"enforces")
