"""Prospective trial contracts, exclusively on a scratch store."""
import json
import multiprocessing
from decimal import Decimal

import pytest

from engine import breakout, execsim, forwardtrial as trial, store, swings

START = 1800000
STEP = 900


@pytest.fixture
def con(tmp_path):
    c = store.connect(tmp_path/'trial.db')
    trial.run(c, {'BTCUSDT'}, now=START)
    yield c
    c.close()


def candle(c, ts, *, low='99', high='101', open='100', close='100'):
    c.execute('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)',
              ('BTCUSDT', '15m', ts, open, high, low, close, '1', 'fixture', ts+STEP))
    c.commit()


def setup(c, *, sid='one', confirmed=START+STEP, now=START+2*STEP+10, **changes):
    for t in range(START-30*STEP, now//STEP*STEP, STEP):
        candle(c, t)
    plan = dict(setup_id=sid, state='VALIDATED', strategy='BREAKOUT_RETEST',
                direction='LONG', entry='100', sl='98', tp='104', maker_limit='99.5',
                maker_wait_bars=2, entry_model='MAKER_THEN_MARKET', expires_at_ts=confirmed+4*STEP)
    plan.update(changes)
    store.insert_fact(c, symbol='BTCUSDT', tf='15m', kind='setup', market_time=confirmed-STEP,
                      confirmed_at=confirmed, algo_version=breakout.BREAKOUT_VERSION, payload=plan)
    c.commit()
    return now


def records(c):
    return trial._records(c)


def test_activation_and_get_are_read_only_after_initial_creation(con):
    changes = con.total_changes
    con.execute('PRAGMA query_only=ON')
    assert trial.report(con, now=START)['state'] == 'COLLECTING'
    assert trial.unresolved(con) == set()
    assert con.total_changes == changes


def test_new_backfill_is_excluded(con):
    now = setup(con, confirmed=START-STEP)
    trial.run(con, {'BTCUSDT'}, now=now)
    assert 'SKIPPED' in records(con)['one']
    assert 'before the trial' in records(con)['one']['SKIPPED']['reason']


def test_no_hindsight_and_restart_deduplicates_identity(con):
    now = setup(con)
    trial.run(con, {'BTCUSDT'}, now=now)
    p = records(con)['one']['PLACED']
    assert p['active_at'] > now
    assert 'FILLED' not in records(con)['one']
    trial.run(con, {'BTCUSDT'}, now=now)
    setup(con, tp='105')  # a changed fact with the same setup identity
    trial.run(con, {'BTCUSDT'}, now=now)
    assert con.execute("SELECT COUNT(*) FROM forward_trial_events WHERE event='PLACED'").fetchone()[0] == 1
    assert records(con)['one']['PLACED']['tp'] == '104'
    assert trial.unresolved(con) == {('BTCUSDT', '15m')}


def test_market_fallback_has_full_prospective_window(con):
    now = setup(con)
    trial.run(con, {'BTCUSDT'}, now=now)
    p = records(con)['one']['PLACED']
    # Context candle after observation, then two no-touch candles, then cross.
    for t in range(p['warmup'][-1]['open_ts']+STEP, p['active_at']+3*STEP, STEP):
        candle(con, t, low='100', high='101')
    trial.run(con, {'BTCUSDT'}, now=p['active_at']+3*STEP)
    f = records(con)['one']['FILLED']
    assert f['entry_role'] == 'TAKER'
    assert f['at'] == p['active_at']+2*STEP
    assert f['at'] >= p['source_expires_at']


def test_gap_holds_then_frozen_fill_and_exact_costs(con):
    now = setup(con)
    trial.run(con, {'BTCUSDT'}, now=now)
    p = records(con)['one']['PLACED']
    active = p['active_at']
    candle(con, active, low='99', high='101')
    trial.run(con, set(), now=active+STEP)
    assert 'FILLED' not in records(con)['one']  # missing intervening context candle
    candle(con, active-STEP)
    trial.run(con, set(), now=active+STEP)
    assert records(con)['one']['FILLED']['entry'] == '99.5'
    candle(con, active, low='97', high='110')  # revised import must not rewrite frozen bar
    candle(con, active+STEP, low='100', high='105', open='101', close='104')
    trial.run(con, set(), now=active+2*STEP)
    r = records(con)['one']
    assert r['CLOSED']['outcome'] == 'TP'
    quantity = Decimal(p['quantity'])
    fees = (Decimal('99.5')+Decimal('104'))*Decimal('.0001')*quantity
    funding = Decimal(r['CLOSED']['funding_usd'])
    assert Decimal(r['CLOSED']['pnl_usd']) == (Decimal('104')-Decimal('99.5'))*quantity-fees-funding
    assert Decimal(r['CLOSED']['fees_usd']) == fees
    assert trial.unresolved(con) == set()
    assert con.execute("SELECT COUNT(*) FROM facts WHERE kind IN ('order','exec','risk','account')").fetchone()[0] == 0
    changes = con.execute('SELECT COUNT(*) FROM forward_trial_events').fetchone()[0]
    trial.run(con, set(), now=active+3*STEP)
    assert con.execute('SELECT COUNT(*) FROM forward_trial_events').fetchone()[0] == changes


def test_rule_change_pauses_without_repricing(con, monkeypatch):
    now = setup(con)
    trial.run(con, {'BTCUSDT'}, now=now)
    monkeypatch.setattr(execsim, 'EXEC_VERSION', 'changed')
    trial.run(con, {'BTCUSDT'}, now=now+STEP)
    assert trial.report(con, now=now+STEP)['state'] == 'PAUSED'
    assert 'FILLED' not in records(con)['one']


def test_dependencies_are_explicit():
    assert trial.DEPENDENCIES == {'breakout': breakout.BREAKOUT_VERSION,
                                  'exec': execsim.EXEC_VERSION, 'swing': swings.SWING_VERSION}


def test_stale_trial_is_visible(con):
    assert trial.report(con, now=START+1801)['state'] == 'PAUSED'


def test_initial_watermark_excludes_existing_setup(tmp_path):
    c = store.connect(tmp_path/'initial.db')
    setup(c)
    trial.run(c, {'BTCUSDT'}, now=START)
    assert not records(c)
    initial = json.loads(c.execute('SELECT payload FROM forward_trial').fetchone()[0])
    trial.run(c, {'BTCUSDT'}, now=START+STEP)
    assert json.loads(c.execute('SELECT payload FROM forward_trial').fetchone()[0]) == initial
    c.close()


def _process_update(path, now):
    from pathlib import Path
    c = store.connect(Path(path))
    trial.run(c, {'BTCUSDT'}, now=now)
    c.close()


def test_two_real_processes_cannot_duplicate_a_placement(con):
    now = setup(con)
    path = con.execute('PRAGMA database_list').fetchone()[2]
    context = multiprocessing.get_context('spawn')
    workers = [context.Process(target=_process_update, args=(path, now)) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(30)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            pytest.fail('Trial writer did not finish')
        assert worker.exitcode == 0
    assert con.execute("SELECT COUNT(*) FROM forward_trial_events WHERE event='PLACED'").fetchone()[0] == 1
