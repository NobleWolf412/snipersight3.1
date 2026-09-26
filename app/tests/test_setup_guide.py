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
    assert g['market_context']=='15m turned bearish'
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


# ---------------------------------------------------------------- trade evidence

from setup_guide import confluence_rows  # noqa: E402

CONFLUENCE = dict(htf_timeframe='1H', htf_regime='BEAR_TREND', htf_composite='WITH',
                  premium_discount=70, volume_expansion='1.60', sweep_nearby=True,
                  zone_strength=77, bars_since_break=12, target_distance_r='3.14159',
                  score=0)


def states(payload):
    return {r['key']: r['state'] for r in confluence_rows(payload)}


def test_each_factor_points_the_way_the_trade_needs_it():
    short = states(dict(direction='SHORT', confluence=CONFLUENCE))
    assert short['htf'] == 'SUPPORTS'
    assert short['range_location'] == 'SUPPORTS'      # selling the upper half
    assert short['sweep'] == 'SUPPORTS'
    # Volume is shown, never judged: the engine's own grading found no edge
    # in it, so painting it green as support would be a false statement.
    assert short['volume'] == 'INFO'
    # The same range location is a CONFLICT for a long: buying the upper half.
    assert states(dict(direction='LONG', confluence=CONFLUENCE))['range_location'] == 'CONFLICTS'


def test_the_neutral_and_unavailable_edges():
    c = dict(CONFLUENCE, htf_composite='FLAT', premium_discount=50,
             volume_expansion='1.50', sweep_nearby=False)
    s = states(dict(direction='SHORT', confluence=c))
    assert s['htf'] == 'NEUTRAL' and s['range_location'] == 'NEUTRAL'
    assert s['sweep'] == 'NEUTRAL', 'no sweep is absent evidence, not a conflict'
    missing = states(dict(direction='SHORT', confluence=dict(
        CONFLUENCE, htf_composite=None, premium_discount=None, volume_expansion=None,
        sweep_nearby=None, zone_strength=None)))
    assert {missing[k] for k in ('htf', 'range_location', 'volume', 'sweep',
                                 'zone_strength')} == {'UNAVAILABLE'}


def test_context_factors_are_shown_and_never_judged():
    s = states(dict(direction='SHORT', confluence=CONFLUENCE))
    assert s['zone_strength'] == s['bars_since_break'] == s['target_distance'] == 'INFO'
    target = next(r for r in confluence_rows(dict(direction='SHORT', confluence=CONFLUENCE))
                  if r['key'] == 'target_distance')
    assert target['value'] == '3.14 R'


def _keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from _keys(v)


def test_no_score_ever_reaches_the_operator(fixture):
    """THE POINT OF THE DESIGN. No factor has been graded, so nothing may add
    them up, count them or rank by them. The engine's own placeholder `score`
    (always 0) must not travel either — a zero next to a trade reads as a
    verdict."""
    ev = Reader(fixture, 2800).evidence('s')
    rows = confluence_rows(dict(direction='SHORT', confluence=CONFLUENCE))
    forbidden = {'score', 'total', 'rank', 'confidence', 'quality_score',
                 'supports_count', 'rating'}
    assert not forbidden & set(_keys(ev))
    assert not forbidden & set(_keys(rows))


def test_a_waiting_setup_says_confluence_comes_at_confirmation(fixture):
    """Confluence is written when a setup confirms; before that there is no
    plan for it to be about. The panel says so instead of inventing one — but
    the higher-timeframe picture is live and still shown."""
    ev = Reader(fixture, 2800).evidence('s')
    assert 'factors' not in ev and 'required' not in ev
    assert 'confirms' in ev['confluence_reason']
    assert ev['higher_timeframe']['stance']['label'] == 'NOT_ENOUGH_HISTORY'
    assert ev['higher_timeframe']['price'] == '3.12'


def test_an_expired_setup_keeps_its_confirmation_evidence(fixture):
    """The confluence block is carried forward past VALIDATED. Keying the panel
    on state == VALIDATED blanked it on every setup the operator reviews after
    its window closed — found on the first live read."""
    for i in range(20):
        ts = 10_000 + i * 900
        fixture.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                        ('TESTUSDT', '15m', ts, '100', '102', '98', '100', '1', 'fixture', ts + 900))
    confirm = 10_000 + 19 * 900
    store.insert_fact(fixture, symbol='TESTUSDT', tf='15m', kind='setup',
                      market_time=confirm, confirmed_at=confirm + 900,
                      algo_version=setups.SETUP_VERSION,
                      payload=dict(setup_id='x', zone_id='z', direction='SHORT', state='EXPIRED',
                                   strategy='REVERSAL', entry='100', sl='101', tp='97', rr='3.00',
                                   confirmed_bar_ts=confirm, confluence=CONFLUENCE,
                                   htf_phase='DRIFT_UP', bias={'alignment': 'WITH'}))
    fixture.commit()
    ev = Reader(fixture, confirm + 1800).evidence('x')
    assert ev['state'] == 'EXPIRED' and ev['factors']
    econ = ev['economics']
    # Net is gross less the cost, both in R; the browser never divides.
    assert Decimal(econ['rr_net']) + Decimal(econ['cost_r']) == Decimal(econ['rr_gross'])
    assert Decimal(econ['rr_net']) < Decimal(econ['rr_gross'])
    assert [c['passed'] for c in ev['required']] == [True, True, True]
    assert ev['recorded_context']['alignment_words'] == 'with this trade'


def test_distances_are_measured_from_the_freshest_close_with_its_own_time(fixture):
    """The price every "% away" uses was the setup timeframe's last close,
    stamped with the moment the page opened — up to four hours old on a 4H
    plan (cold audit). It is now the freshest closed candle, with ITS time."""
    fixture.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('TESTUSDT', '5m', 3600, '3.20', '3.21', '3.19', '3.20', '1', 'fixture', 3900))
    fixture.commit()
    htf = Reader(fixture, 4000).evidence('s')['higher_timeframe']
    assert htf['price'] == '3.20' and htf['price_timeframe'] == '5m'
    assert htf['price_at'] == 3900 and htf['price_stale'] is False
    later = Reader(fixture, 3900 + 301).evidence('s')['higher_timeframe']
    assert later['price_stale'] is True, 'a feed a full candle behind reads as stale, not as now'


def test_the_note_does_not_claim_nothing_was_graded(fixture):
    """The engine's own grading exists (setups.py, the retained-rank note);
    the card must not deny it while colouring factors."""
    note = Reader(fixture, 2800).evidence('s')['note']
    assert 'graded' not in note and 'not proof' in note


# ------------------------------------------------------ structure wording + age

from setup_guide import structure_words  # noqa: E402
from engine.regime import REGIME_VERSION  # noqa: E402
from engine.structure import STRUCTURE_VERSION  # noqa: E402

BEAR_CHOCH = dict(regime='TRANSITION', evidence={'last_break': {
    'event': 'CHOCH', 'direction': 'BEAR', 'at': 1_741_478_400}})   # 2025-03-09


def _reading(phase, bars, moved):
    return dict(phase=phase, last_break=dict(bars_since=bars, displacement_atr=moved))


def test_an_old_bearish_turn_is_not_called_turning():
    """ADA, September 2026: '1W structure turning bearish' on a weekly that had
    risen since July. The label had no age and 'turning' read as fresh."""
    words = structure_words(BEAR_CHOCH, _reading('DRIFT_DOWN', 28, '-1.40'))
    assert 'turning' not in words
    assert words == ('turned bearish, no follow-through (last bearish break '
                     'Mar 9, 2025, 28 bars ago; price has since moved back past it)')


def test_each_turn_phase_has_its_own_words():
    assert structure_words(BEAR_CHOCH, _reading('TURN_DOWN', 3, '0.50')).startswith('fresh turn bearish (')
    assert structure_words(BEAR_CHOCH, _reading('IMPULSE_DOWN', 5, '4.00')).startswith('turned bearish and ran hard (')
    assert 'moved back' not in structure_words(BEAR_CHOCH, _reading('IMPULSE_DOWN', 5, '4.00'))


def test_trend_keeps_its_label_and_says_when_stretched():
    bull = dict(regime='BULL_TREND', evidence={'last_break': {'event': 'BOS', 'direction': 'BULL',
                                                              'at': 1_741_478_400}})
    assert structure_words(bull, _reading('TREND_UP_EXTENDED', 9, '3.50')) == (
        'bullish structure, stretched far past its last break (last bullish break Mar 9, 2025, 9 bars ago)')


def test_without_a_reading_only_the_recorded_fact_is_described():
    assert structure_words(BEAR_CHOCH) == 'turned bearish (last bearish break Mar 9, 2025)'
    assert structure_words(dict(regime='TRANSITION')) == 'structure changed; direction not recorded'


def test_guide_reads_the_phase_as_of_the_setup_record(tmp_path):
    con = store.connect(tmp_path/'phase.db')
    week = 604800
    manifest = store.record_manifest(con, 'strategy', dict(
        version=setups.SETUP_VERSION, confirm_max_bars=3, rejection_fraction='0.66',
        inputs=dict(zone=zones.ZONE_VERSION, regime=REGIME_VERSION)))
    for i in range(20):
        ts = i * week
        con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('TESTUSDT', '1W', ts, '1.00', '1.05', '0.95', '1.00', '1', 'fixture', ts + week))
    brk_at, recorded = 2 * week, 20 * week
    store.insert_fact(con, symbol='TESTUSDT', tf='1W', kind='structure', market_time=brk_at,
                      confirmed_at=brk_at + week, algo_version=STRUCTURE_VERSION,
                      payload=dict(event='CHOCH', direction='BEAR', level='0.90'))
    store.insert_fact(con, symbol='TESTUSDT', tf='1W', kind='regime', market_time=brk_at,
                      confirmed_at=brk_at + week, algo_version=REGIME_VERSION,
                      payload=dict(regime='TRANSITION', evidence={'last_break': {
                          'event': 'CHOCH', 'direction': 'BEAR', 'at': brk_at}}))
    store.insert_fact(con, symbol='TESTUSDT', tf='1W', kind='zone', market_time=0, confirmed_at=week,
                      algo_version=zones.ZONE_VERSION,
                      payload=dict(zone_id='z', event='CREATED', bottom='1.10', top='1.20'))
    store.insert_fact(con, symbol='TESTUSDT', tf='1W', kind='setup', market_time=19 * week,
                      confirmed_at=recorded, algo_version=setups.SETUP_VERSION,
                      payload=dict(setup_id='w', zone_id='z', direction='SHORT', state='FORMING',
                                   manifest_hash=manifest))
    con.commit()
    g = Reader(con, recorded + week).guide('w')
    assert g['market_context'] == ('1W turned bearish, no follow-through (last bearish break '
                                   'Jan 15, 1970, 17 bars ago; price has since moved back past it)')
    con.close()
