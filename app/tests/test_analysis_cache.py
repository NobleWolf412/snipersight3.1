import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engine import (basis, ingest, manual, pipeline, quality, scalein, setups,
                    store, swings, volatility)
from engine.analysis_cache import AnalysisCache


@pytest.fixture
def book(tmp_path):
    con = store.connect(tmp_path/'cache.db')
    for tf, seconds in [('5m',300),('15m',900),('1H',3600),('4H',14400)]:
        for i in range(55):
            price = 100+i%9
            con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                        ('BTCUSDT',tf,i*seconds,str(price),str(price+2),str(price-2),str(price+1),'10','fixture',i*seconds))
    con.commit()
    with patch.object(quality,'assert_market_ready',return_value=[]), patch.object(ingest,'missing_history',return_value=[]):
        yield con
    con.close()


def run(con, cache, modules=(volatility,)):
    return pipeline.run_symbol(con,'BTCUSDT',modules=modules,timeframes=('15m',),cache=cache)


def test_unchanged_input_skips_but_quality_still_runs(book):
    cache=AnalysisCache()
    with patch.object(volatility,'run',wraps=volatility.run) as engine, patch.object(quality,'assert_market_ready',return_value=[]) as gate:
        run(book,cache);run(book,cache)
        assert engine.call_count==1 and gate.call_count==2
        assert cache.skipped==1


@pytest.mark.parametrize('change', ['repair','append','version','remove_output'])
def test_content_version_and_output_changes_invalidate(book,change):
    cache=AnalysisCache();run(book,cache)
    if change=='repair':
        book.execute("UPDATE candles SET high='120',volume='99' WHERE symbol='BTCUSDT' AND tf='15m' AND open_ts=0")
    elif change=='append':
        book.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',('BTCUSDT','15m',55*900,'100','103','98','102','12','fixture',55*900))
    elif change=='remove_output':
        book.execute("DELETE FROM facts WHERE kind='volatility'")
    book.commit()
    with patch.object(volatility,'VOLATILITY_VERSION', 'cache-test' if change=='version' else volatility.VOLATILITY_VERSION), patch.object(volatility,'run',wraps=volatility.run) as engine:
        run(book,cache)
        assert engine.call_count==1


def test_failed_engine_is_retried(book):
    cache=AnalysisCache()
    with patch.object(volatility,'run',side_effect=RuntimeError('fixture failure')):
        run(book,cache)
    with patch.object(volatility,'run',wraps=volatility.run) as engine:
        run(book,cache)
        assert engine.call_count==1
    assert book.execute("SELECT count(*) FROM engine_faults").fetchone()[0]==0


@pytest.mark.parametrize('kind,version',[('structure',swings.PRIOR_STRUCTURE),('liquidity',swings.PRIOR_LIQ)])
def test_swings_prior_generation_evidence_invalidates(book,kind,version):
    cache=AnalysisCache();cache.begin_symbol()
    assert not cache.unchanged(book,swings,'BTCUSDT','15m')
    cache.remember(book,swings,'BTCUSDT','15m')
    assert cache.unchanged(book,swings,'BTCUSDT','15m')
    store.insert_fact(book,symbol='BTCUSDT',tf='15m',kind=kind,market_time=0,confirmed_at=900,
                      algo_version=version,payload={'event':'fixture'})
    assert not cache.unchanged(book,swings,'BTCUSDT','15m')


def test_upstream_write_during_engine_run_cannot_be_cached(book):
    cache = AnalysisCache()
    peer = store.connect(Path(book.execute('PRAGMA database_list').fetchone()[2]))
    def concurrent_write(*_args):
        store.insert_fact(peer, symbol='BTCUSDT', tf='15m', kind='structure',
                          market_time=0, confirmed_at=900, algo_version=swings.PRIOR_STRUCTURE,
                          payload={'event': 'concurrent fixture'})
        peer.commit()
    try:
        with patch.object(swings, 'run', side_effect=concurrent_write) as engine:
            run(book, cache, modules=(swings,))
            run(book, cache, modules=(swings,))
            assert engine.call_count == 2
            run(book, cache, modules=(swings,))
            assert engine.call_count == 2
    finally:
        peer.close()


def test_cross_timeframe_settings_and_account_consumers_are_never_cached(book):
    cache=AnalysisCache()
    for mod in (setups,scalein,manual,basis):
        cache.remember(book,mod,'BTCUSDT','15m')
        assert not cache.unchanged(book,mod,'BTCUSDT','15m')


def test_phases_cover_roster_once_and_preserve_trading_dependencies(book,tmp_path):
    other=store.connect(tmp_path/'other.db');book.backup(other)
    cache=AnalysisCache()
    pipeline.run_symbol(book,'BTCUSDT')
    pipeline.run_symbol(other,'BTCUSDT',modules=pipeline.phase_modules(),timeframes=pipeline.PRIORITY_TFS,cache=cache)
    pipeline.run_symbol(other,'BTCUSDT',deferred=True,cache=cache)
    def facts(con):return {r[0] for r in con.execute('SELECT content_hash FROM facts')}
    assert facts(book)==facts(other)
    # Same-tail edits and a higher-timeframe update are both visible on the
    # next pass. In particular, setup and scale-in reads are never skipped.
    for con in (book,other):
        con.execute("UPDATE candles SET high='140' WHERE tf='15m' AND open_ts=900")
        con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',('BTCUSDT','4H',55*14400,'100','115','96','111','50','fixture',55*14400))
        con.commit()
    pipeline.run_symbol(book,'BTCUSDT')
    pipeline.run_symbol(other,'BTCUSDT',modules=pipeline.phase_modules(),timeframes=pipeline.PRIORITY_TFS,cache=cache)
    pipeline.run_symbol(other,'BTCUSDT',deferred=True,cache=cache)
    assert facts(book)==facts(other)
    for con in (book,other):
        assert not [json.loads(r[0]) for r in con.execute("SELECT payload FROM facts WHERE confirmed_at<market_time")]
    other.close()
