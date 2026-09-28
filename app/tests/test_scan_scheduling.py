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


def run_cycle(con, new_candles, paper_pins=None, *, late=False, tracked=(),
              fetch_fails=()):
    events = []
    clock = {"now": 100000}
    with ExitStack() as stack:
        def stub(target, **kw):
            return stack.enter_context(patch(target, **kw))

        stub('live.time.time', side_effect=lambda: clock["now"])
        stub('live.universe.scan_symbols', return_value=['BTCUSDT', 'ETHUSDT'])
        stub('live.universe.all_tracked_symbols', return_value=list(tracked))
        stub('live.execsim.unresolved', return_value={})
        stub('live.execution_rebuild_work', return_value={})
        stub('live.execution.paper_open_symbols', return_value=paper_pins or set())
        stub('engine.manual.unresolved', return_value={})
        for name in ('zonestudy', 'stopstudy', 'forwardtrial'):
            stub(f'live.{name}.exists', return_value=True)
            stub(f'live.{name}.unresolved', return_value=set())
            stub(f'live.{name}.run', side_effect=lambda *a, label=name: events.append(label))
        stub('live.importer.native_tfs', return_value={'15m': 900})
        def fetch(s, tf, start, end, *, as_of):
            assert as_of == 100000, 'fetch clock moved'
            events.append(('fetch', s))
            if s in fetch_fails:
                raise OSError('venue down')
            return {'symbol': s, 'tf': tf}
        stub('live.importer.fetch', side_effect=fetch)
        def backfill(c, s, tf, start, end, *, as_of, fetched):
            assert fetched == {'symbol': s, 'tf': tf}, 'wrong prefetch stored'
            events.append(('store', s))
            return {'candles': new_candles, 'gaps': 0}
        stub('live.importer.backfill', side_effect=backfill)
        stub('live.ingest.history_floor', return_value=0)
        stub('live.funding.fetch_since', return_value=None)
        stub('live.funding.fetch_history', return_value=[])
        stub('live.funding.store_history', side_effect=lambda c, s, **kw:
             events.append(('funding', s)) or {})
        stub('live.venues.REFERENCE', new={})
        stub('live.aggregator.aggregate', side_effect=lambda c, s, tf:
             events.append(('aggregate', s)) if tf == '4H' else None)
        stub('live.pipeline.run_symbol', side_effect=lambda c, s, **kw:
             events.append(('deferred' if kw.get('deferred') else 'priority', s)) or {'blocked': None})
        def paper_monitor(c, *, cutoff):
            assert cutoff == 100000, 'paper cutoff moved'
            events.append('monitor')
        stub('live.execution.monitor_paper', side_effect=paper_monitor)
        def paper_risk(c):
            events.append('paper_risk')
            if late:
                clock["now"] = live.decision_deadline(100000) + 1
            return {'written': 0, 'unpriced_intents': 0}
        stub('live.riskpaper.run', side_effect=paper_risk)
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
    events = [e for e in run_cycle(book, new_candles=1)
              if not (isinstance(e, tuple) and e[0] in ('fetch', 'store', 'funding', 'aggregate'))]
    assert events[:4] == [('priority', 'BTCUSDT'), ('priority', 'ETHUSDT'),
                          'monitor', 'paper_risk']
    dispatch = events.index('dispatch')
    assert all(events.index(event) > dispatch for event in
               [('deferred', 'BTCUSDT'), ('deferred', 'ETHUSDT'), 'forwardtrial', 'research_risk'])


def test_idle_import_still_checks_existing_orders(book):
    events = run_cycle(book, new_candles=0, paper_pins={'BTCUSDT'})
    assert events.index('monitor') > events.index(('priority', 'BTCUSDT'))
    assert events.index('monitor') < events.index('paper_risk')


def test_deadline_miss_keeps_settlement_but_refuses_new_dispatch(book):
    events = run_cycle(book, new_candles=1, late=True)
    assert 'monitor' in events and 'paper_risk' in events
    assert 'dispatch' not in events
    assert live.decision_deadline(100000) == 100200


def test_retired_paper_market_refreshes_settlement_inputs_before_monitor(book):
    events = run_cycle(book, new_candles=1, paper_pins={'SOLUSDT'})
    assert events.index(('priority', 'SOLUSDT')) < events.index('monitor')


def test_every_venue_wait_precedes_the_first_write_and_writes_keep_their_order(book):
    # live-v0.18: fetches run concurrently, but the store is written from one
    # thread in the serial loop's order, each symbol's candles before its funding.
    events = run_cycle(book, new_candles=1)
    fetches = [i for i, e in enumerate(events) if e[0] == 'fetch']
    writes = [e for e in events if isinstance(e, tuple) and e[0] in ('store', 'funding')]
    assert max(fetches) < events.index(('store', 'BTCUSDT'))
    assert writes == [('store', 'BTCUSDT'), ('funding', 'BTCUSDT'),
                      ('store', 'ETHUSDT'), ('funding', 'ETHUSDT')]


def test_one_failed_venue_request_skips_only_that_market(book):
    events = run_cycle(book, new_candles=1, fetch_fails={'BTCUSDT'})
    assert ('store', 'BTCUSDT') not in events and ('funding', 'BTCUSDT') not in events
    assert ('store', 'ETHUSDT') in events and ('funding', 'ETHUSDT') in events
    assert 'dispatch' in events


def test_markets_without_new_candles_roll_up_after_the_decision(book):
    # 206 roll-ups ran ahead of a 45-market decision (67s, 2026-09-28). A
    # market this pass did not import has no new bucket to roll up.
    events = run_cycle(book, new_candles=1, tracked=['BTCUSDT', 'ETHUSDT', 'OLDUSDT'])
    first_priority = events.index(('priority', 'BTCUSDT'))
    assert events.index(('aggregate', 'BTCUSDT')) < first_priority
    assert events.index(('aggregate', 'ETHUSDT')) < first_priority
    assert events.index(('aggregate', 'OLDUSDT')) > events.index('dispatch')
    assert events.count(('aggregate', 'OLDUSDT')) == 1


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
    book.execute('INSERT INTO execution_events(intent_id,event,occurred_at,payload) VALUES(?,?,?,?)',
                 ('order', 'PAPER_ROUTED', 480, '{}'))
    book.commit()
    log = Mock()
    with patch('live.time.time', return_value=9999):
        live.record_order_latency(book, [{'queue': {'intent_id': 'order'},
                                          'setup_id': 'setup'}], log)
    event = json.loads(log.info.call_args.args[0].removeprefix('ORDER LATENCY '))
    assert event['confirmed_at'] == 300
    assert event['intent_created_at'] == 450
    assert event['confirmation_to_intent_s'] == 150
    assert event['routed_at'] == 480
    assert event['confirmation_to_route_s'] == 180
