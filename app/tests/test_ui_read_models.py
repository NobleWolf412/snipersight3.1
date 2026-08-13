from decimal import Decimal

import server


def _trade(r, *, strategy="PULLBACK", regime="BULL_TREND",
           horizon=None, direction="LONG", order_type=None, pnl=None,
           symbol="BTCUSDT"):
    return {
        "r_multiple": r,
        "pnl_usd": pnl if pnl is not None else Decimal(str(r)) * Decimal("25"),
        "strategy": strategy, "regime": regime, "horizon": horizon,
        "direction": direction, "order_type": order_type, "symbol": symbol,
    }


def test_forward_summary_is_server_owned_and_refuses_small_sample():
    rows = [_trade("1.25"), _trade("-0.50"), _trade("0.25")]
    out = server._journal_performance_summary(
        rows, {"baseline_id": "base-1", "started_at": 100})
    assert out["population"] == "FUNDED_PAPER_TRADES"
    assert out["window"] == "ACTIVE_BASELINE"
    assert out["trades"] == 3
    assert out["average_r"] == 0.3333
    assert out["profit_factor"] == 3.0
    assert out["verdict"]["code"] == "INSUFFICIENT_EVIDENCE"
    assert out["confidence_interval_r"] == {
        "status": "INSUFFICIENT_EVIDENCE", "lo": None, "hi": None,
        "resamples": 0, "minimum_trades": 10,
        "method": "DETERMINISTIC_BOOTSTRAP_MEAN"}


def test_forward_summary_confidence_interval_is_active_baseline_and_deterministic():
    rows = [_trade(str(value)) for value in
            (1, -0.5, 0.75, 0.25, -1, 1.5, 0.5, -0.25, 1.25, 0.1)]
    first = server._journal_performance_summary(
        rows, {"baseline_id": "base-1", "started_at": 100})
    second = server._journal_performance_summary(
        rows, {"baseline_id": "base-1", "started_at": 100})
    assert first["population"] == "FUNDED_PAPER_TRADES"
    assert first["window"] == "ACTIVE_BASELINE"
    assert first["confidence_interval_r"] == second["confidence_interval_r"]
    assert first["confidence_interval_r"]["status"] == "MEASURED"
    assert first["confidence_interval_r"]["lo"] is not None
    assert first["confidence_interval_r"]["hi"] is not None


def test_dimensions_never_replace_missing_metadata_with_a_guess():
    rows = [_trade("1", horizon=None, order_type=None),
            _trade("-1", horizon="swing", order_type="LIMIT")]
    out = server._performance_dimensions(rows, {"baseline_id": "base-1"})
    horizons = {row["key"] for row in out["dimensions"]["horizon"]}
    order_types = {row["key"] for row in out["dimensions"]["order_type"]}
    assert horizons == {"NOT_REPORTED", "swing"}
    assert order_types == {"NOT_REPORTED", "LIMIT"}
    assert {row["key"] for row in out["dimensions"]["symbol"]} == {"BTCUSDT"}
    assert all(row["population"] == "FUNDED_PAPER_TRADES"
               for group in out["dimensions"].values() for row in group)


def test_empty_forward_book_has_no_confident_zero_metrics():
    out = server._journal_performance_summary([], {"started_at": 100})
    assert out["trades"] == 0
    assert out["win_pct"] is None
    assert out["average_r"] is None
    assert out["profit_factor"] is None


def test_trade_config_names_both_custody_modes_without_client_guessing():
    venue = server.trade_config("BTCUSDT")["venue"]
    assert venue["margin_mode"] == "ISOLATED"
    assert venue["position_mode"] == "ONE_WAY"
