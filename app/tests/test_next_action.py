"""The Overview directive is an ordered read model, never a browser guess."""
from server import _next_action


def row(state, symbol="UNIUSDT", setup_id="setup-1"):
    return {"state": state, "setup": {"setup_id": setup_id,
            "symbol": symbol, "direction": "SHORT", "timeframe": "15m"}}


def action(rows=(), *, halted=False, scanner="SCANNING", quality="PASS",
           positions=0, orders=0, citadel=True):
    return _next_action(
        rows=list(rows), mode={"mode": "PAPER", "halted": halted},
        scanner={"state": scanner},
        account={"open_positions": positions, "working_orders": orders},
        data_status=quality,
        citadel={"reachable": citadel, "control_url": "https://citadel.test/"})


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


def test_data_warning_blocks_a_ready_setup():
    result = action([row("READY")], quality="WARN")
    assert result["state"] == "CHECK"
    assert result["primary"]["route"] == "system-diagnostics"


def test_quiet_paper_book_is_explicitly_no_trade_and_points_to_shadow():
    result = action([])
    assert result["state"] == "CLEAR"
    assert "No trade" in result["summary"]
    assert result["secondary"] == {
        "label": "Review Shadow mode", "route": "system", "view": "automation"}
