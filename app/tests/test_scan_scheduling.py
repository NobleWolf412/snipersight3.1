"""Scheduling contracts against a scratch store; no network or order effects."""
from collections import Counter
from contextlib import ExitStack
import json
from unittest.mock import Mock, patch

import pytest

import live
from engine import execution, pipeline, store


@pytest.fixture
def book(tmp_path):
    con = store.connect(tmp_path / 'schedule.db')
    store.start_baseline(con, started_at=0, label='fixture')
    yield con
    con.close()


def run_cycle(con, new_candles, paper_pins=None):
    events = []
    with ExitStack() as stack:
        def stub(target, **kw):
            return stack.enter_context(patch(target, **kw))

        stub('live.time.time', return_value=100000)
        stub('live.universe.scan_symbols', return_value=['BTCUSDT', 'ETHUSDT'])
        stub('live.universe.all_tracked_symbols', return_value=[])
        stub('live.execsim.unresolved', return_value={})
        stub('live.execution_rebuild_work', return_value={})
        stub('live.execution.paper_open_symbols', return_value=paper_pins or set())
        stub('engine.manual.unresolved', return_value={})
        for name in ('zonestudy', 'stopstudy', 'forwardtrial'):
            stub(f'live.{name}.exists', return_value=True)
            stub(f'live.{name}.unresolved', return_value=set())
            stub(f'live.{name}.run', side_effect=lambda *a, label=name: events.append(label))
        stub('live.importer.native_tfs', return_value={'15m': 900})
        stub('live.importer.backfill', return_value={'candles': new_candles, 'gaps': 0})
        stub('live.ingest.history_floor', return_value=0)
        stub('live.funding.store_history', return_value={})
        stub('live.venues.REFERENCE', new={})
        stub('live.aggregator.aggregate')
        stub('live.pipeline.run_symbol', side_effect=lambda c, s, **kw:
             events.append(('deferred' if kw.get('deferred') else 'priority', s)) or {'blocked': None})
        stub('live.execution.monitor_paper', side_effect=lambda c: events.append('monitor'))
        stub('live.riskpaper.run', side_effect=lambda c:
             events.append('paper_risk') or {'written': 0, 'unpriced_intents': 0})
        stub('live.risk.run', side_effect=lambda c: events.append('research_risk'))
        stub('live.automation.current', return_value=(live.automation.AutomationMode.PAPER, 0))
        stub('live.positions.private_environments_with_exposure', return_value=set())
        broker = stub('live.broker_factory.phemex_for_mode')
        stub('live.autotrader.run', side_effect=lambda *a, **kw:
             events.append('dispatch') or {'routed': [], 'refused': []})
        stub('live.quality.audit')
        stub('prune.maybe_auto_prune_runs')
        stub('engine.regrade.maybe_run')
        stub('live.announceable', return_value=[])
        live.cycle(con, Mock())
        broker.assert_not_called()
    return events


def test_all_markets_and_fresh_account_precede_dispatch_and_research(book):
    events = run_cycle(book, new_candles=1)
    assert events[:4] == [('priority', 'BTCUSDT'), ('priority', 'ETHUSDT'),
                          'monitor', 'paper_risk']
    dispatch = events.index('dispatch')
    assert all(events.index(event) > dispatch for event in
               [('deferred', 'BTCUSDT'), ('deferred', 'ETHUSDT'), 'forwardtrial', 'research_risk'])


def test_idle_import_still_checks_existing_orders(book):
    events = run_cycle(book, new_candles=0, paper_pins={'BTCUSDT'})
    assert events.index('monitor') > events.index(('priority', 'BTCUSDT'))
    assert events.index('monitor') < events.index('paper_risk')


def test_retired_paper_market_refreshes_settlement_inputs_before_monitor(book):
    events = run_cycle(book, new_candles=1, paper_pins={'SOLUSDT'})
    assert events.index(('priority', 'SOLUSDT')) < events.index('monitor')


def test_phase_partition_executes_each_roster_pair_once_in_dependency_order(book):
    # Includes the intentionally repeated execution pass; count it twice.
    calls = []
    for tf in pipeline.ALL_TFS:
        book.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                     ('BTCUSDT', tf, 0, '100', '101', '99', '100', '1', 'fixture', 0))
    book.commit()
    with ExitStack() as stack:
        stack.enter_context(patch('engine.quality.assert_market_ready', return_value=[]))
        stack.enter_context(patch('engine.ingest.missing_history', return_value=[]))
        for mod in set(pipeline.PER_SYMBOL):
            stack.enter_context(patch.object(mod, 'run', side_effect=lambda c, s, tf, gran, m=mod:
                                            calls.append((m.__name__, tf))))
        pipeline.run_symbol(book, 'BTCUSDT', modules=pipeline.phase_modules(), timeframes=pipeline.PRIORITY_TFS)
        priority_calls = list(calls)
        pipeline.run_symbol(book, 'BTCUSDT', deferred=True)
    expected = [(m.__name__, tf) for m in pipeline.PER_SYMBOL for tf in pipeline.ALL_TFS]
    assert Counter(calls) == Counter(expected)
    assert priority_calls == [(m.__name__, tf) for m in pipeline.phase_modules() for tf in pipeline.PRIORITY_TFS]


def test_deferred_pass_cannot_clear_a_priority_engine_failure(book):
    book.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                 ('BTCUSDT', '15m', 0, '100', '101', '99', '100', '1', 'fixture', 0))
    book.commit()
    with patch('engine.quality.assert_market_ready', return_value=[]), \
         patch('engine.ingest.missing_history', return_value=[]), \
         patch.object(pipeline.volatility, 'run', side_effect=RuntimeError('fixture')):
        pipeline.run_symbol(book, 'BTCUSDT', modules=(pipeline.volatility,), timeframes=('15m',))
        pipeline.run_symbol(book, 'BTCUSDT', modules=(pipeline.volatility,), deferred=True)
    assert book.execute("SELECT count(*) FROM engine_faults WHERE engine='volatility'").fetchone()[0] == 1


def test_order_latency_uses_recorded_time_and_matching_version_and_attempt(book):
    execution._ensure(book)
    for version, attempt, confirmed in [('retired', 'current', 100),
                                        ('fixture', 'previous', 200),
                                        ('fixture', 'current', 300)]:
        store.insert_fact(book, symbol='BTCUSDT', tf='15m', kind='setup',
                          market_time=0, confirmed_at=confirmed, algo_version=version,
                          payload={'setup_id': 'setup', 'attempt_id': attempt, 'state': 'VALIDATED'})
    book.execute('INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,symbol,payload,state,created_at,updated_at) '
                 'VALUES(?,?,?,?,?,?,?,?,?)',
                 ('key', 'order', 'PAPER', 'setup', 'BTCUSDT',
                  json.dumps({'intent': {'playbook_version': 'fixture', 'attempt_id': 'current'}}),
                  'PAPER_ROUTED', 450, 999))
    book.commit()
    log = Mock()
    with patch('live.time.time', return_value=9999):
        live.record_order_latency(book, [{'intent_id': 'order', 'setup_id': 'setup'}], log)
    event = json.loads(log.info.call_args.args[0].removeprefix('ORDER LATENCY '))
    assert event['confirmed_at'] == 300
    assert event['order_created_at'] == 450
    assert event['confirmation_to_order_s'] == 150
