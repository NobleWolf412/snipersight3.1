"""Confirmation explanations use recorded evidence, never wall-clock guesses."""
import json
from decimal import Decimal

import pytest

from engine import setups, store, zones
from setup_guide import Reader


@pytest.fixture
def fixture(tmp_path):
    con = store.connect(tmp_path/'guide.db')
    manifest = store.record_manifest(con, 'strategy', dict(
        version=setups.SETUP_VERSION, confirm_max_bars=3, rejection_fraction='0.66',
        inputs=dict(zone=zones.ZONE_VERSION, regime='regime-test')))
    def fact(kind, payload, at, version):
        store.insert_fact(con, symbol='TESTUSDT', tf='15m', kind=kind,
                          market_time=at-900, confirmed_at=at, algo_version=version, payload=payload)
    fact('zone',dict(zone_id='z',event='CREATED',bottom='3.1105',top='3.1780'),900,zones.ZONE_VERSION)
    fact('setup',dict(setup_id='s',zone_id='z',direction='SHORT',state='CONFIRMING',
                      confirm_deadline_ts=4500,manifest_hash=manifest),1800,setups.SETUP_VERSION)
    fact('regime',dict(regime='TRANSITION', evidence={'last_break':{'event':'CHOCH','direction':'BEAR'}}),900,'regime-test')
    # A later bullish transition must not rewrite the setup's original context.
    fact('regime',dict(regime='BULL_TREND'),2700,'regime-test')
    for ts in (900,1800,3600):
        con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('TESTUSDT','15m',ts,'3.14','3.17','3.10','3.12','1','fixture',ts+900))
    con.commit()
    yield con
    con.close()


def test_short_rules_progress_and_future_candles(fixture):
    g=Reader(fixture,2800).guide('s')
    assert g['available'] and g['confirmation_boundary']=='3.1105'
    assert g['conditions']==['High at or above 3.1105','Close strictly below 3.1105','Close in the bottom 34% of that candle’s range']
    assert g['completed_followup_bars']==1 and len(g['steps'])==3
    assert g['next_close_at']==3600 and g['touch_close']==1800
    assert g['last_closed_at']==2700 and len(g['mini_chart']['bars'])==2
    assert g['market_context']=='15m structure turning bearish'
    assert 'above 3.1780' in g['skip_if'] and '5%' in g['skip_if']


def test_missing_candle_never_counts_as_completed(fixture):
    g=Reader(fixture,4600).guide('s')
    assert g['completed_followup_bars']==2
    assert g['missing_candles'] and g['window_ended'] and g['next_close_at'] is None
    assert not g['steps'][1]['complete']


def test_manifest_parameters_not_current_constants(fixture,monkeypatch):
    monkeypatch.setattr(setups,'REJECTION_FRACTION',Decimal('.90'))
    monkeypatch.setattr(setups,'CONFIRM_MAX_BARS',9)
    g=Reader(fixture,2800).guide('s')
    assert '34%' in g['confirmation'] and g['max_followup_bars']==3


def test_missing_manifest_is_explicit_and_no_progress(fixture):
    fixture.execute('DELETE FROM manifests')
    g=Reader(fixture,2800).guide('s')
    assert not g['available'] and 'missing' in g['unavailable_reason']
    assert 'steps' not in g


def test_long_mirrors_short_and_geometry_stays_decimal(fixture):
    raw=fixture.execute("SELECT payload FROM facts WHERE kind='setup'").fetchone()[0]
    payload={**json.loads(raw),'setup_id':'long','direction':'LONG'}
    store.insert_fact(fixture,symbol='TESTUSDT',tf='15m',kind='setup',market_time=900,
                      confirmed_at=1800,algo_version=setups.SETUP_VERSION,payload=payload)
    g=Reader(fixture,2800).guide('long')
    assert g['confirmation_boundary']=='3.1780'
    assert 'Close strictly above 3.1780' in g['conditions']
    assert 'top 34%' in g['confirmation'] and 'below 3.1105' in g['skip_if']
    assert isinstance(g['mini_chart']['boundary_y'],str)
    assert g['last_price']=='3.12'


def test_no_candles_reports_missing_and_stale(fixture):
    fixture.execute('DELETE FROM candles')
    g=Reader(fixture,2800).guide('s')
    assert g['mini_chart'] is None and g['last_price'] is None
    assert g['data_stale'] and g['missing_candles']
