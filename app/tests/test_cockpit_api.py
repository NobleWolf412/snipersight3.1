"""Cockpit account journey, always on a scratch store with no private effects."""
import time
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import server
import ui_api
from engine import automation, manual, shared_account, store
from tests.test_shared_account import bot_plan


@pytest.fixture
def cockpit(tmp_path):
    path = tmp_path / 'cockpit.db'
    connect = store.connect
    con = connect(path)
    shared_account.ensure(con)
    automation.transition(con, 'PAPER', expected_revision=0)
    shared_account.set_risk_percent(con, '0.25', 'legacy', '0.02')
    shared_account.request_cutover(con, 'drain')
    shared_account.request_cutover(con, 'complete')
    now = int(time.time())
    bar = now // 3600 * 3600 - 3600
    con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
                ('ETHUSDT','1H',bar,'100','101','99','100','1','fixture',bar+3600))
    con.commit()
    def scratch(db_path=None):
        assert db_path in (None,path), 'Test cannot open another database'
        return connect(path)
    with patch('engine.store.connect', side_effect=scratch):
        yield TestClient(server.app), con
    con.close()


def terms():
    return dict(workspace='CRYPTO',symbol='ETHUSDT',tf='1H',direction='LONG',entry='100',sl='98',tp='104')


def test_full_account_preview_arm_retry_and_journal(cockpit):
    client, con = cockpit
    home = client.get('/api/ui/v1/home').json()
    assert home['context']['risk_pct'] == '0.0025'
    preview = client.post('/api/ui/v1/ticket/preview',json=terms())
    assert preview.status_code == 200, preview.text
    request = preview.json()['request']
    assert Decimal(preview.json()['risk_usd']) == 25
    assert con.execute('SELECT count(*) FROM execution_outbox').fetchone()[0] == 0
    result = client.post('/api/ui/v1/ticket/arm',json=request)
    assert result.status_code == 200, result.text
    repeat = client.post('/api/ui/v1/ticket/arm',json=request)
    assert repeat.json()['receipt']['already_armed']
    with pytest.raises(shared_account.AdmissionRejected,match='CONCURRENT_LIMIT'):
        shared_account.admit_plan(con, bot_plan())
    journal = client.get('/api/ui/v1/journal').json()['items']
    assert len(journal) == 1
    assert journal[0]['origin'] == journal[0]['controller'] == 'OPERATOR'
    assert journal[0]['grade_eligible'] is False
    assert Decimal(journal[0]['risk_usd']) == 25
    assert client.get('/api/ui/v1/home').json()['context']['account']['reserved_slots'] == 1


def test_preview_cannot_activate_order_in_the_past_and_old_receipt_survives(cockpit):
    client, con = cockpit
    request = client.post('/api/ui/v1/ticket/preview',json=terms()).json()['request']
    with patch('engine.shared_account.time.time', return_value=request['created_at']+90):
        result = client.post('/api/ui/v1/ticket/arm',json=request)
    assert result.status_code == 200
    receipt = result.json()['receipt']
    assert receipt['armed_at'] == request['created_at']+90
    with patch('engine.shared_account.time.time', return_value=request['created_at']+3600):
        repeat = client.post('/api/ui/v1/ticket/arm',json=request)
    assert repeat.status_code == 200 and repeat.json()['receipt']['armed_at'] == receipt['armed_at']
    assert con.execute('SELECT count(*) FROM execution_outbox').fetchone()[0] == 1


def test_account_change_and_stale_candles_refuse_new_ticket(cockpit):
    client, con = cockpit
    request = client.post('/api/ui/v1/ticket/preview',json=terms()).json()['request']
    shared_account.request_cutover(con,'drain')
    shared_account.request_cutover(con,'complete')
    assert client.get('/api/ui/v1/journal',params={'epoch_id':request['expected_epoch']}).status_code==409
    result=client.post('/api/ui/v1/ticket/arm',json=request)
    assert result.status_code==400 and 'ACCOUNT_CHANGED' in result.text
    con.execute('DELETE FROM candles');con.commit()
    result=client.post('/api/ui/v1/ticket/preview',json=terms())
    assert result.status_code==400 and 'recent closed candle' in result.text


def test_stock_reads_do_not_touch_crypto_store(cockpit):
    client,_=cockpit
    with patch('engine.store.connect',side_effect=AssertionError('Crypto boundary crossed')):
        for endpoint in ('context','home','opportunities','positions','journal','research'):
            result=client.get(f'/api/ui/v1/{endpoint}?workspace=STOCKS')
            assert result.status_code==200,result.text
        result=client.post('/api/ui/v1/ticket/preview',json={**terms(),'workspace':'STOCKS'})
        assert result.status_code==409


def test_shell_and_ui_rollback_share_backend(cockpit):
    client,_=cockpit
    assert '/static/cockpit/app.js' in client.get('/').text
    assert '/static/shell.js' in client.get('/classic').text


def test_cancel_cannot_erase_target_before_projection(cockpit):
    _,con=cockpit
    manual.create_intent(con,'BTCUSDT','1H','LONG',100,104,98,0,risk_usd=25)
    con.executemany('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',[
        ('BTCUSDT','1H',t,'100',hi,'99','100','1','fixture',t+3600)
        for t,hi in [(0,'101'),(3600,'101'),(7200,'105')]])
    con.commit()
    with pytest.raises(manual.IntentRejected,match='already filled'):
        manual.cancel_intent(con,'BTCUSDT|1H|MANUAL|0')
    manual.run(con,'BTCUSDT','1H',3600)
    assert shared_account.context(con)['account']['closed_count']==1
    assert shared_account.journal(con)[0]['outcome']=='TP'


def test_configure_paper_risk(cockpit):
    client, con = cockpit
    current = client.get('/api/ui/v1/context').json()
    request = dict(workspace='CRYPTO', risk_percent='0.75',
                   expected_epoch=current['epoch_id'], expected_risk_pct=current['risk_pct'])
    assert client.post('/api/account/risk', json=request).status_code == 200
    assert client.get('/api/ui/v1/context').json()['risk_percent_label'] == '0.75%'
    assert client.post('/api/account/risk', json=request).status_code == 409
    assert client.post('/api/account/risk', json={**request, 'workspace':'STOCKS'}).status_code == 400


def test_setup_guide_uses_recorded_zone_prices(cockpit):
    from engine import setups, zones
    client, con = cockpit
    store.insert_fact(con, symbol='ETHUSDT', tf='1H', kind='zone', market_time=1,
                      confirmed_at=2, algo_version=zones.ZONE_VERSION,
                      payload={'zone_id':'zone-example', 'event':'CREATED', 'bottom':'98.125', 'top':'99.875'})
    store.insert_fact(con, symbol='ETHUSDT', tf='1H', kind='setup', market_time=3,
                      confirmed_at=4, algo_version=setups.SETUP_VERSION,
                      payload={'setup_id':'setup-example','zone_id':'zone-example','direction':'LONG',
                               'state':'CONFIRMING','confirm_deadline_ts':100})
    con.commit()
    response=client.get('/api/ui/v1/setup-guide',params={'setup_id':'setup-example'})
    assert response.status_code == 200
    guide=response.json()
    assert guide['zone_bottom']=='98.125'
    assert guide['confirmation_boundary']=='99.875'
    assert guide['confirmation_deadline']==100
    assert guide['stop'] is None
    assert 'buffer' in guide['skip_if']
    assert client.get('/api/ui/v1/setup-guide',params={'setup_id':'setup-example','workspace':'STOCKS'}).status_code==404


def test_research_includes_history_and_ready_filter_checks_prices(cockpit):
    client, con = cockpit
    base={'setup':{'setup_id':'x','symbol':'ETHUSDT','timeframe':'1H','entry':'100','stop':'98','targets':['104'],'confirmed_at':1,'expires_at':int(time.time())+3600},'state':'READY','eligible':True}
    with patch('engine.opportunities.list_candidates', return_value=[base]) as read:
        assert client.get('/api/ui/v1/research').status_code==200
        assert read.call_args.kwargs['include_history'] is True
    with patch('ui_api.opportunity_rows',return_value=[base,{**base,'eligible':False},{**base,'setup':{**base['setup'],'entry':'0'}}]):
        rows=client.get('/api/ui/v1/opportunities?group=ready').json()['items']
        assert len(rows)==1


def test_opportunity_tabs_filter_before_limit_and_sort_whole_population(cockpit):
    client, _ = cockpit
    now=int(time.time())
    def row(n,state="FORMING",distance=None,stage="price"):
        return dict(state=state,eligible=state=="READY",progress_stage=stage,economics={"distance_atr":distance},setup=dict(setup_id=str(n),symbol=f"COIN{n}",timeframe="1H",entry="100",stop="98",targets=["104"],confirmed_at=now-n,expires_at=now+3600))
    candidates=[row(n,distance=str(20-n)) for n in range(20)]
    candidates += [row(20,"BLOCKED","0"),row(21,"EXPIRED","0"),row(22,"POSITION_OPEN","0"),row(23,"FORMING","0","confirmation")]
    with patch('ui_api.opportunity_rows',return_value=candidates):
        data=client.get('/api/ui/v1/opportunities?group=watching&limit=10').json()
        assert len(data['items'])==10 and data['total']==21
        assert data['items'][0]['setup']['setup_id']=='23'
        assert data['items'][1]['setup']['setup_id']=='19'
        assert not {'BLOCKED','EXPIRED','POSITION_OPEN'} & {r['state'] for r in data['items']}
        newest=client.get('/api/ui/v1/opportunities?group=watching&sort=newest&limit=10').json()
        assert newest['items'][0]['setup']['setup_id']=='0'
        assert client.get('/api/ui/v1/opportunities?sort=bogus').status_code==400


def test_ready_rejects_expired_and_nonfinite_plans_and_distance_zero_is_known(cockpit):
    client, _ = cockpit
    now=int(time.time())
    base=dict(state='READY',eligible=True,economics={'distance_atr':'0'},setup=dict(setup_id='valid',symbol='ETHUSDT',timeframe='1H',entry='100',stop='98',targets=['104'],confirmed_at=now,expires_at=now+60))
    bad=[{**base,'setup':{**base['setup'],'entry':v,'setup_id':v}} for v in ('NaN','Infinity','broken','0','-1')]
    bad += [{**base,'setup':{**base['setup'],'expires_at':now-1}}, {**base,'eligible':False}]
    unknown=[{**base,'setup':{**base['setup'],'setup_id':str(i)},'economics':{'distance_atr':d}} for i,d in enumerate((None,'NaN','Infinity'))]
    with patch('ui_api.opportunity_rows',return_value=bad+unknown+[base]):
        data=client.get('/api/ui/v1/opportunities?group=ready&sort=distance').json()
        assert data['total']==4 and data['counts']['ready']==4
        assert data['items'][0]['setup']['setup_id']=='valid'


def _row(**over):
    """A read-model row in the shape `actionable` reads."""
    row = {"state": "READY", "eligible": True, "progress_stage": "watching",
           "setup": {"entry": "100", "stop": "98", "targets": ["104"],
                     "expires_at": 4102444800}}
    row.update(over)
    return row


def test_one_definition_of_ready_reaches_every_surface():
    """The badge, the button, the count, the filter and the sort must agree.

    This file grew three definitions. The count and the Ready filter asked for
    state + eligibility + finite positive prices + an unexpired window;
    `progress_label` and the sort asked for `state == "READY"` alone; `/home`
    asked for state + eligibility.

    An expired setup is the ordinary case of the disagreement, because `state`
    is computed when the scanner runs and the entry window is checked when the
    request arrives. It was badged "Ready to trade", sorted to the top, and
    given a "Review trade" button, while the Ready tab beside it was empty and
    the count read zero.
    """
    now = 1_700_000_000

    assert ui_api.actionable(_row(), now)

    # Each half of the predicate, on its own, must take the row out.
    expired = _row(setup={**_row()["setup"], "expires_at": now - 1})
    assert not ui_api.actionable(expired, now), "an entry window that closed"
    assert not ui_api.actionable(_row(eligible=False), now), "not eligible"
    assert not ui_api.actionable(_row(state="FORMING"), now), "not READY"
    assert not ui_api.actionable(
        _row(setup={**_row()["setup"], "stop": "0"}), now), "a stop of zero"
    assert not ui_api.actionable(
        _row(setup={**_row()["setup"], "entry": "not a price"}), now), "junk"


def test_an_expired_setup_is_never_badged_ready(cockpit):
    """The label is what the operator reads, and it must not invite an action
    the Ready tab says is unavailable."""
    client, con = cockpit
    rows = ui_api.opportunity_rows(con)
    for row in rows:
        if not row["actionable"]:
            assert row["progress_label"] != "Ready to trade", (
                f"{row['setup']['symbol']} is labelled ready but the Ready "
                f"filter and the count both exclude it")
        else:
            assert row["state"] == "READY"


def test_the_label_and_the_count_cannot_drift_apart():
    """Derived from the source: every reader must go through `actionable`.

    A list of the four call sites would not survive the fifth, so this asserts
    the shape instead — no surface may re-test `state == "READY"` to decide
    whether the operator can act.
    """
    import inspect
    import re

    src = inspect.getsource(ui_api)
    # The only legitimate `state == "READY"` left is inside `actionable` itself
    # and the label's "Entry window closed" branch, which distinguishes an
    # expired READY row from one that never got there.
    hits = [src.count("\n", 0, m.start()) + 1
            for m in re.finditer(r'\["state"\]\s*==\s*"READY"|'
                                 r'\.get\("state"\)\s*==\s*"READY"', src)]
    assert len(hits) <= 2, (
        f"{len(hits)} places test state == READY directly (lines {hits}); "
        f"the question 'can the operator act on this' has one answer and it "
        f"is `actionable`")
