"""Paired exits from scratch evidence; no main-book mutations or broker calls."""
import json
import multiprocessing
from decimal import Decimal

import pytest

from engine import costs, execution, forwardtrial, stopstudy as study, store

START = 1800000
STEP = 900


def bar(i, low='99', high='101', close='100', opening='100'):
    return dict(open_ts=START+i*STEP, open=opening, high=high, low=low, close=close, volume='1')


def model(long=True):
    return dict(symbol='BTCUSDT', tf='15m', direction='LONG' if long else 'SHORT',
                stop='98' if long else '102', target='106' if long else '94',
                max_bars=100, cost_profile=costs.profile_for('BTCUSDT').version)


def fill():
    return dict(entry='100', quantity='10', at=START, entry_role='MAKER', warmup=[bar(i) for i in range(-20, 0)])


def test_cost_cover_applies_next_bar_never_retroactively():
    bars = [bar(0), bar(1, high='103', close='102'), bar(2, low='100', high='102', close='101', opening='101')]
    arms = study.simulate(model(), fill(), bars)
    be = arms['COST_COVER']
    assert be['moves'][0]['at'] == START+2*STEP
    assert be['result']['at'] == START+2*STEP
    assert arms['HOLD']['result'] is None
    assert Decimal(be['result']['pnl_usd']) > -1  # estimated protection is not guaranteed zero


def test_entry_bar_extreme_cannot_trigger_cost_cover():
    arms = study.simulate(model(), fill(), [bar(0, high='104'), bar(1)])
    assert not arms['COST_COVER']['moves']


def test_stop_wins_before_trigger_and_ambiguous_target():
    arms = study.simulate(model(), fill(), [bar(0), bar(1, low='97', high='107')])
    for arm in arms.values():
        assert arm['result']['outcome'] == 'SL'
        assert arm['result']['ambiguous']
        assert not arm['moves']


def test_protected_stop_still_pays_a_gap():
    bars = [bar(0), bar(1, high='103', close='102'), bar(2, low='89', high='91', close='90', opening='90')]
    arms = study.simulate(model(), fill(), bars)
    assert Decimal(arms['COST_COVER']['result']['exit']) < Decimal('90')
    assert Decimal(arms['COST_COVER']['result']['pnl_usd']) < Decimal('-100')


def test_short_cost_cover_is_mirrored():
    arms = study.simulate(model(False), fill(), [bar(0), bar(1, low='97', high='100', close='98'),
        bar(2, low='98', high='100', close='99', opening='99')])
    assert Decimal(arms['COST_COVER']['moves'][0]['price']) < Decimal('100')
    assert arms['COST_COVER']['result']['at'] == START+2*STEP
    assert arms['HOLD']['result'] is None


@pytest.mark.parametrize('long', [True, False])
def test_confirmed_pivot_needs_two_right_bars_and_only_tightens(long):
    p = model(long)
    p.update(stop='97' if long else '103', target='110' if long else '90')
    f = fill()
    f['warmup'] = []
    lows = ['99', '98.5', '98.2', '98.7', '99', '99.8', '99.5', '99.2', '99.6', '99.9']
    candles = [bar(i, low=v, high='101') if long else bar(i, low='99', high=str(Decimal('200')-Decimal(v))) for i, v in enumerate(lows)]
    assert not study.simulate(p, f, candles[:-1])['STRUCTURE']['moves']
    moves = study.simulate(p, f, candles)['STRUCTURE']['moves']
    assert moves == [{'at': START+10*STEP, 'confirmed_at': START+10*STEP, 'price': '99.2' if long else '100.8'}]


@pytest.fixture
def con(tmp_path):
    c = store.connect(tmp_path/'comparison.db')
    execution._ensure(c)
    c.commit()
    study.run(c, now=START)
    yield c
    c.close()


def source(c, iid='new', created=START+STEP, state='PAPER_FILLED', controller='BOT', filled=True):
    p = dict(symbol='BTCUSDT', timeframe='15m', direction='LONG', stop='98', targets=['106'], quantity='10')
    c.execute("INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,symbol,payload,state,created_at,updated_at,origin,controller,grade_eligible) VALUES (?,?, 'PAPER',?,'BTCUSDT',?,?,?,?, 'BOT',?,1)",
              (iid, iid, iid, json.dumps({'intent': p}), state, created, created, controller))
    if filled:
        c.execute("INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,entry,stop,target,state,filled_at,entry_role) VALUES (?,'BTCUSDT','15m','LONG','10','100','98','106','OPEN',?,'MAKER')", (iid, created))
    c.commit()


def candles(c, bars):
    for b in bars:
        c.execute('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)',
                  ('BTCUSDT', '15m', b['open_ts'], b['open'], b['high'], b['low'], b['close'], '1', 'FIXTURE', b['open_ts']+STEP))
    c.commit()


def test_historical_order_is_excluded_even_when_inserted_late(con):
    source(con, created=START-STEP)
    study.run(con, now=START+2*STEP)
    assert study.report(con, now=START+2*STEP)['excluded_count'] == 1
    assert not study.unresolved(con)


def test_held_off_without_fill_is_terminal(con):
    source(con, state='HELD_OFF', filled=False)
    study.run(con, now=START+2*STEP)
    assert study.report(con, now=START+2*STEP)['excluded_count'] == 1
    assert not study.unresolved(con)


def test_missing_and_invalid_candles_cannot_settle(con):
    source(con)
    candles(con, [bar(2, low='97', high='107')])
    study.run(con, now=START+4*STEP)
    assert study.report(con, now=START+4*STEP)['paired_count'] == 0
    candles(con, [bar(1, high='NaN')])
    study.run(con, now=START+4*STEP)
    assert 'Invalid price' in study.report(con, now=START+4*STEP)['items'][0]['note']
    assert not any(k.startswith('BAR:') for k in study._records(con)['paper:new'])


def test_exact_dollars_frozen_results_and_account_isolation(con):
    source(con)
    candles(con, [bar(i) for i in range(-20, 2)]+[bar(2, high='107', close='106')])
    before = con.execute('SELECT payload,state FROM execution_outbox').fetchall()
    study.run(con, now=START+3*STEP)
    report = study.report(con, now=START+3*STEP)
    assert report['paired_count'] == 1
    result = report['items'][0]['results']['HOLD']
    expected = (Decimal(result['exit'])-Decimal('100'))*10-Decimal(result['fees_usd'])-Decimal(result['funding_usd'])
    assert Decimal(result['pnl_usd']) == expected
    assert [tuple(row) for row in con.execute('SELECT payload,state FROM execution_outbox').fetchall()] == before
    assert not study.unresolved(con)
    candles(con, [bar(2, low='1', high='107')])
    study.run(con, now=START+4*STEP)
    assert study.report(con, now=START+4*STEP)['items'][0]['results'] == report['items'][0]['results']


def test_incomplete_triplets_do_not_enter_totals(con):
    source(con)
    candles(con, [bar(i) for i in range(-20, 2)]+[bar(2, high='103', close='102'), bar(3, low='100', high='102', close='101', opening='101')])
    study.run(con, now=START+4*STEP)
    report = study.report(con, now=START+4*STEP)
    assert report['items'][0]['results']['COST_COVER']
    assert report['paired_count'] == 0
    assert all(Decimal(r['pnl_usd']) == 0 for r in report['totals'].values())
    assert study.unresolved(con) == {('BTCUSDT', '15m')}


def test_operator_intervention_excludes_a_followed_comparison(con):
    source(con)
    candles(con, [bar(i) for i in range(-20, 2)])
    study.run(con, now=START+2*STEP)
    con.execute("UPDATE execution_outbox SET controller='OPERATOR',grade_eligible=0")
    con.commit()
    study.run(con, now=START+3*STEP)
    assert study.report(con, now=START+3*STEP)['excluded_count'] == 1


def test_read_only_and_version_pause(con, monkeypatch):
    assert study.DEPENDENCIES == study._dependencies()
    monkeypatch.setattr(execution, 'EXECUTION_CORE_VERSION', 'changed')
    study.run(con, now=START+STEP)
    con.execute('PRAGMA query_only=ON')
    assert study.report(con, now=START+STEP)['state'] == 'PAUSED'


def test_missing_cost_estimate_excludes_all_three_from_totals(con):
    source(con)
    candles(con, [bar(1), bar(2, high='103'), bar(3, high='107', close='106')])
    study.run(con, now=START+4*STEP)
    report = study.report(con, now=START+4*STEP)
    assert report['paired_count'] == 0
    assert report['excluded_count'] == 1
    assert 'cost estimate' in report['items'][0]['note']
    assert not study.unresolved(con)


def _worker(path, now):
    from pathlib import Path
    c = store.connect(Path(path))
    study.run(c, now=now)
    c.close()


def test_two_processes_enroll_one_trade(con):
    source(con)
    path = con.execute('PRAGMA database_list').fetchone()[2]
    ctx = multiprocessing.get_context('spawn')
    workers = [ctx.Process(target=_worker, args=(path, START+STEP)) for _ in range(2)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(30)
        if w.is_alive():
            w.terminate()
            w.join()
            pytest.fail('Comparison writer hung')
        assert w.exitcode == 0
    assert con.execute("SELECT COUNT(*) FROM stop_study_events WHERE event='ENROLLED'").fetchone()[0] == 1


def test_new_breakout_fill_uses_source_trial_frozen_candles(con):
    forwardtrial.run(con, {'BTCUSDT'}, now=START)
    p = dict(symbol='BTCUSDT', tf='15m', direction='LONG', sl='98', tp='106', quantity='10')
    forwardtrial._event(con, 'breakout-new', 'PLACED', START+STEP, p)
    forwardtrial._event(con, 'breakout-new', 'FILLED', START+2*STEP,
                        dict(entry='100', at=START+STEP, entry_role='MAKER'))
    forwardtrial._event(con, 'breakout-new', 'BAR:'+str(START+STEP), START+2*STEP, bar(1, high='107', close='106'))
    con.commit()
    candles(con, [bar(1, low='97', high='101')])
    study.run(con, now=START+2*STEP)
    item = study.report(con, now=START+2*STEP)['items'][0]
    assert item['source'] == 'BREAKOUT_TRIAL'
    assert item['results']['HOLD']['outcome'] == 'TP'
