"""The Overview directive is an ordered read model, never a browser guess.

The data-status ordering is deliberate and matches the engine's own
vocabulary: only BLOCKED stops risk.py sizing, so only BLOCKED may hide a
READY setup behind a data card. DEGRADED trades straight through, so it
surfaces only when nothing more urgent is on the book — the old single
"not clean enough" card for every non-PASS status told the operator not to
trust a setup the engine was about to size.
"""
from server import _next_action


def row(state, symbol="UNIUSDT", setup_id="setup-1"):
    return {"state": state, "setup": {"setup_id": setup_id,
            "symbol": symbol, "direction": "SHORT", "timeframe": "15m"}}


def action(rows=(), *, halted=False, scanner="SCANNING", quality="PASS",
           positions=0, orders=0, citadel=True, report=None):
    return _next_action(
        rows=list(rows), mode={"mode": "PAPER", "halted": halted},
        scanner={"state": scanner},
        account={"open_positions": positions, "working_orders": orders},
        data_status=quality,
        citadel={"reachable": citadel, "control_url": "https://citadel.test/"},
        quality=report)


def test_halt_outranks_every_trade_directive():
    result = action([row("POSITION_OPEN")], halted=True, positions=1)
    assert result["state"] == "PAUSED"
    assert result["primary"]["route"] == "system-diagnostics"


def test_dead_scanner_hands_phone_recovery_to_citadel():
    result = action([], scanner="OFFLINE")
    assert result["state"] == "RECOVER"
    assert result["primary"]["external_url"] == "https://citadel.test/"


def test_open_position_outranks_ready_setup_and_preserves_selection():
    result = action([row("READY", "BTCUSDT", "ready"),
                     row("POSITION_OPEN", "UNIUSDT", "open")], positions=1)
    assert result["title"] == "Manage UNIUSDT short"
    assert result["primary"]["route"] == "trade"
    assert result["primary"]["setup_id"] == "open"


def test_ready_setup_is_the_next_review():
    result = action([row("READY")])
    assert result["state"] == "READY"
    assert result["primary"]["label"] == "Review setup"


def test_blocked_data_outranks_a_ready_setup_and_names_the_cause():
    report = {"blockers": [
        {"code": "SEQUENCE_GAPS", "symbol": "BTCUSDT", "tf": "15m"},
        {"code": "SEQUENCE_GAPS", "symbol": "XRPUSDT", "tf": "1H"},
    ]}
    result = action([row("READY")], quality="BLOCKED", report=report)
    assert result["state"] == "CHECK"
    assert result["primary"]["route"] == "system-diagnostics"
    # The card names what failed and where, in plain words — never a bare
    # "not clean enough" the operator can only shrug at.
    assert "holes" in result["summary"]
    assert "BTCUSDT" in result["summary"] and "XRPUSDT" in result["summary"]
    assert "2 market" in result["title"]
    assert "SEQUENCE_GAPS" not in result["summary"], \
        "engine codes stay in Diagnostics; the card speaks plain English"


def test_blocked_without_a_readable_report_still_fails_closed():
    result = action([row("READY")], quality="BLOCKED", report=None)
    assert result["state"] == "CHECK"
    assert "Diagnostics" in result["summary"]


def test_unrecognised_status_fails_closed_like_blocked():
    result = action([row("READY")], quality="WARN")
    assert result["state"] == "CHECK"
    assert result["primary"]["route"] == "system-diagnostics"


def test_degraded_data_does_not_hide_the_setup_the_engine_would_size():
    result = action([row("READY")], quality="DEGRADED")
    assert result["state"] == "READY"


def test_degraded_data_surfaces_on_a_quiet_book_as_flagged_not_blocked():
    report = {"warnings": [
        {"code": "STALE_SERIES", "symbol": "XLMUSDT", "tf": "15m"}]}
    result = action([], quality="DEGRADED", report=report)
    assert result["state"] == "CHECK"
    assert "flagged" in result["title"].lower()
    assert "XLMUSDT" in result["summary"]
    assert "Trading continues" in result["bot_handling"]


def test_unknown_verdict_is_pending_never_dirty():
    result = action([], quality="UNKNOWN")
    assert result["state"] == "WATCHING"
    assert "not recorded" in result["summary"] \
        or "has not recorded" in result["summary"]


def test_quiet_paper_book_is_explicitly_no_trade_and_points_to_shadow():
    result = action([])
    assert result["state"] == "CLEAR"
    assert "No trade" in result["summary"]
    assert result["secondary"] == {
        "label": "Review Shadow mode", "route": "system", "view": "automation"}
