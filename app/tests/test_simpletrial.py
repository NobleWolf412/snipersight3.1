"""Prospective comparison on a scratch store; no account or network effects."""
import json
from decimal import Decimal

import pytest

from engine import execsim, setups, simpletrial as trial, store, swings, trend

STEP = trial.STEP
START = 200 * STEP


def test_dependencies_are_pinned_to_current_detectors():
    assert trial.DEPENDENCIES == {
        "setup": setups.SETUP_VERSION, "trend": trend.TREND_VERSION,
        "exec": execsim.EXEC_VERSION, "swing": swings.SWING_VERSION}


@pytest.fixture
def con(tmp_path):
    db = store.connect(tmp_path / "simple-trial.db")
    yield db
    db.close()


def candle(con, ts, *, symbol="BTCUSDT", open="100", close="100", high="101", low="99"):
    con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, "4H", ts, open, high, low, close, "1", "fixture", ts+STEP))
    con.commit()


def history(con):
    for ts in range(START-40*STEP, START, STEP):
        candle(con, ts)


def test_channel_uses_prior_bars_and_only_closed_signal(con):
    history(con)
    candle(con, START, close="103", high="105", low="100")
    rows = [dict(r) for r in store.get_candles(con, "BTCUSDT", "4H")]
    plan = trial.channel_signal(rows, "BTCUSDT")
    assert plan["direction"] == "LONG"
    assert plan["confirmed_bar_ts"] == START
    assert Decimal(plan["sl"]) < Decimal(plan["maker_limit"]) < Decimal(plan["entry"])
    assert trial.channel_signal(rows[:-1], "BTCUSDT") is None


def test_activation_does_not_backfill_and_observation_starts_future_window(con):
    history(con)
    candle(con, START, close="103", high="105", low="100")
    trial.run(con, {"BTCUSDT"}, cutoff=START+STEP,
              observed_at=START+STEP+10)
    assert all("PLACED" not in r for r in trial._records(con).values())
    candle(con, START+STEP, close="106", high="107", low="101")
    trial.run(con, {"BTCUSDT"}, cutoff=START+2*STEP,
              observed_at=START+2*STEP+10)
    record = next(r for r in trial._records(con).values() if "PLACED" in r)
    assert record["OBSERVED"]["confirmed_at"] == START+2*STEP
    assert record["PLACED"]["active_at"] == START+3*STEP
    assert "FILLED" not in record
    assert trial.unresolved(con) == {("BTCUSDT", "4H")}
    assert con.execute("SELECT COUNT(*) FROM facts WHERE kind IN ('order','exec','risk','account')").fetchone()[0] == 0


def test_late_network_time_cannot_move_candle_cutoff(con):
    history(con)
    trial.run(con, {"BTCUSDT"}, cutoff=START, observed_at=START+10)
    candle(con, START, close="103", high="105", low="100")
    trial.run(con, {"BTCUSDT"}, cutoff=START,
              observed_at=START+STEP+10)
    assert trial._records(con) == {}
    trial.run(con, {"BTCUSDT"}, cutoff=START+STEP,
              observed_at=START+STEP+20)
    assert trial._records(con)  # the next pass may observe the closed bar


def test_frozen_entry_and_exit_survive_a_revised_import(con):
    history(con)
    trial.run(con, {"BTCUSDT"}, cutoff=START, observed_at=START+10)
    candle(con, START, close="103", high="105", low="100")
    trial.run(con, {"BTCUSDT"}, cutoff=START+STEP,
              observed_at=START+STEP+10)
    placed = next(r["PLACED"] for r in trial._records(con).values()
                  if "PLACED" in r)
    active = placed["active_at"]
    candle(con, active-STEP, open="103", close="103", high="104", low="102")
    candle(con, active, open="106", close="105", high="107", low="101")
    trial.run(con, set(), cutoff=active+STEP, observed_at=active+STEP+10)
    record = next(r for r in trial._records(con).values() if "FILLED" in r)
    assert record["FILLED"]["entry_role"] == "MAKER"
    assert record["FILLED"]["at"] == active
    con.execute("UPDATE candles SET low='1' WHERE symbol='BTCUSDT' AND tf='4H' AND open_ts=?", (active,))
    candle(con, active+STEP, open="106", close="120", high="130", low="105")
    trial.run(con, set(), cutoff=active+2*STEP,
              observed_at=active+2*STEP+10)
    record = next(r for r in trial._records(con).values() if "CLOSED" in r)
    assert record["CLOSED"]["outcome"] == "TP"
    assert Decimal(record["CLOSED"]["pnl_usd"]) > 0
    assert trial.unresolved(con) == set()
    assert con.execute("SELECT COUNT(*) FROM facts WHERE kind IN ('order','exec','risk','account')").fetchone()[0] == 0


def test_report_stays_unknown_until_both_sample_floors(con):
    trial.run(con, set(), cutoff=START, observed_at=START)
    for arm in ("CURRENT", "CHANNEL"):
        for i in range(30):
            sid = f"{arm}:{i}"
            symbol = f"S{i % (7 if arm == 'CURRENT' else 8)}USDT"
            trial._event(con, arm, sid, "OBSERVED", START, {"symbol": symbol})
            trial._event(con, arm, sid, "PLACED", START, {"direction": "LONG"})
            trial._event(con, arm, sid, "CLOSED", START+STEP,
                         {"at": START+STEP+i, "pnl_usd": "1", "r_multiple": "0.01"})
    con.commit()
    assert trial.report(con)["primary"]["verdict"] == "UNKNOWN"
    sid = "CURRENT:29"
    con.execute("UPDATE simple_trial_events SET payload=? WHERE arm='CURRENT' AND signal_id=? AND event='OBSERVED'",
                (json.dumps({"symbol": "S7USDT"}), sid))
    con.commit()
    assert trial.report(con)["primary"]["verdict"] != "UNKNOWN"


def test_rule_change_pauses_without_repricing(con, monkeypatch):
    trial.run(con, set(), cutoff=START, observed_at=START)
    monkeypatch.setattr(trial.execsim, "EXEC_VERSION", "changed")
    trial.run(con, set(), cutoff=START+STEP, observed_at=START+STEP)
    assert trial.report(con)["state"] == "PAUSED"
