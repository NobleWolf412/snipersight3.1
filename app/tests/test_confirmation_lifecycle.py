"""Incremental closed-candle tests: replaying a full history hid these defects."""
import json

import pytest

from engine import opportunities, regime, setups, store, swings, zones


@pytest.fixture
def setup_store(tmp_path):
    con = store.connect(tmp_path / "confirmation.db")
    for i in range(20):
        bar(con, i, (100, 102, 98, 100))
    base = {"zone_id": "z1", "zone_type": "DEMAND", "bottom": "95", "top": "100"}
    for event, mt, ct in (("CREATED", 0, 3600), ("TOUCH", 20*3600, 21*3600)):
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="zone",
                          market_time=mt, confirmed_at=ct, algo_version=zones.ZONE_VERSION,
                          payload={**base, "event": event, "state": "TOUCHED", "episode": 1})
    store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime", market_time=0,
                      confirmed_at=3600, algo_version=regime.REGIME_VERSION,
                      payload={"regime": "BULL_TREND"})
    con.commit()
    yield con
    con.close()


def bar(con, i, values):
    con.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("TESTUSDT", "1H", i*3600, *map(str, values), "1", "test", (i+1)*3600))
    con.commit()


def target(con, price="130"):
    store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="swing", market_time=0,
                      confirmed_at=3600, algo_version=swings.SWING_VERSION,
                      payload={"tier": "INTERMEDIATE", "type": "HIGH", "price": price})


def run(con):
    setups.run(con, "TESTUSDT", "1H", 3600)
    return [json.loads(r[0]) for r in con.execute(
        "SELECT payload FROM facts WHERE kind='setup' AND algo_version=? ORDER BY confirmed_at,id",
        (setups.SETUP_VERSION,))]


def test_confirms_without_next_candle_and_reference_never_uses_future_open(setup_store):
    con = setup_store
    target(con)
    bar(con, 20, (100, 107, "99.5", 106))
    valid = [p for p in run(con) if p['state'] == 'VALIDATED']
    assert len(valid) == 1
    assert valid[0]['entry'] == '106'
    assert valid[0]['entry_reference'] == 'CONFIRMATION_CLOSE'
    assert valid[0]['expires_at_ts'] == 25*3600
    bar(con, 21, (120, 125, 115, 122))
    assert [p for p in run(con) if p['state'] == 'VALIDATED'] == valid


def test_incomplete_window_stays_confirming_then_can_validate(setup_store):
    con = setup_store
    target(con)
    bar(con, 20, (100, 101, 99, "99.8"))
    assert [p['state'] for p in run(con)] == ['CONFIRMING']
    bar(con, 21, (100, 107, "99.5", 106))
    assert run(con)[-1]['state'] == 'VALIDATED'


def test_timeout_waits_for_last_confirmation_candle(setup_store):
    con = setup_store
    target(con)
    for i in range(20, 24):
        bar(con, i, (100, 101, 99, "99.8"))
        latest = run(con)[-1]
        assert latest['state'] == ('CANCELLED' if i == 23 else 'CONFIRMING')
    assert latest['cancel_reason'] == 'CONFIRMATION_TIMEOUT'


@pytest.mark.parametrize('reason', ['RR_BELOW_MINIMUM', 'NO_CAUSAL_TARGET', 'UNECONOMIC_AFTER_COSTS'])
def test_after_confirmation_failure_records_actual_terminal_reason(setup_store, monkeypatch, reason):
    con = setup_store
    if reason != 'NO_CAUSAL_TARGET':
        target(con, '108' if reason == 'RR_BELOW_MINIMUM' else '130')
    if reason == 'UNECONOMIC_AFTER_COSTS':
        monkeypatch.setattr(setups, 'MIN_RISK_COST_MULT', 10000)
    bar(con, 20, (100, 107, '99.5', 106))
    p = run(con)[-1]
    assert p['state'] == 'REJECTED'
    assert p['rejection_reason'] == reason
    p.update(symbol='TESTUSDT', tf='1H')
    item = opportunities.candidate(p, now=21*3600)
    assert item.state.value == 'REJECTED'
    assert 'expiry' not in item.strongest_counterargument


def test_confirming_uses_confirmation_deadline_not_entry_deadline():
    p = dict(setup_id='TESTUSDT|1H|PULLBACK|z',symbol='TESTUSDT',tf='1H',
             strategy='PULLBACK',direction='LONG',state='CONFIRMING',confirm_deadline_ts=200)
    assert opportunities.candidate(p, now=199).state.value == 'FORMING'
    assert not opportunities.candidate(p, now=199).eligible
    assert opportunities.candidate(p, now=200).state.value == 'EXPIRED'


def test_expired_risk_rejection_is_not_a_current_block():
    p = dict(setup_id='TESTUSDT|1H|PULLBACK|z',symbol='TESTUSDT',tf='1H',
             strategy='PULLBACK',direction='LONG',state='VALIDATED',expires_at_ts=100)
    risk = {'decision':'REJECTED','reasons':['CONCURRENT_LIMIT(1)']}
    assert opportunities.candidate(p, risk_fact=risk, now=200).state.value == 'EXPIRED'
