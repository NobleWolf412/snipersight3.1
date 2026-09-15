"""Disposable UI harness. NEVER opens the operator's store or private effects.

Run from the repository root: .venv/Scripts/python.exe app/tests/cockpit_preview.py
The port is fixed to 8437 to distinguish it from the supervised application.
"""
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from engine import automation, credentials, marketpulse, opportunities, settings, shared_account, store
from engine.contracts import to_wire

DB = ROOT/'artifacts'/('cockpit-preview-'+uuid.uuid4().hex+'.db')
DB.parent.mkdir(exist_ok=True)
connect = store.connect
def scratch(path=None):
    if path not in (None,DB):
        raise RuntimeError('Preview cannot open any other database')
    return connect(DB)
store.connect=scratch
con=scratch()
shared_account.ensure(con)
automation.transition(con,'PAPER',expected_revision=0)
shared_account.request_cutover(con,'drain')
shared_account.request_cutover(con,'complete')
con.execute("UPDATE account_epochs SET label='Isolated preview · synthetic' WHERE active=1")
now=int(time.time())
bar=now//3600*3600-3600
symbols=['BTCUSDT','ETHUSDT','SOLUSDT','LINKUSDT','AVAXUSDT']
for n,symbol in enumerate(symbols):
    for i in range(90):
        t=bar-(89-i)*3600
        # Synthetic candles, intentionally simple and reproducible.
        close=100+(i%9-4)/4
        con.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?)',
            (symbol,'1H',t,str(close-.1),str(close+1),str(close-1),str(close),'1','FIXTURE',t+3600))
con.commit()
# Browser layout fixtures contain no grades, account money, or admission mocks.
real_candidates=opportunities.list_candidates
def candidates(connection,**kwargs):
    assert connection.execute('PRAGMA database_list').fetchone()[2] == str(DB)
    return [to_wire(opportunities.candidate(dict(setup_id=f'{s}|1H|PULLBACK|fixture-{n}|fixture',
        symbol=s,tf='1H',strategy='PULLBACK',direction='LONG',state='VALIDATED',entry='100',sl='98',
        tp='104',rr='2',confirmed_at=now,expires_at=now+3600,why='Synthetic layout fixture: structure retest at the stored level.'),
        domain=kwargs.get('domain','PAPER'),now=now)) for n,s in enumerate(symbols)]
opportunities.list_candidates=candidates
marketpulse.current=lambda:{'sources':[{'source':'Fixture feed','status':'UNAVAILABLE','observed_at':None}],
    'items':[],'calendar':{'status':'UNAVAILABLE','events':[]},'note':'Isolated preview. External feeds are stubbed; no coverage is implied.'}
credentials.status=lambda:{target:{field:False for field in fields} for target,fields in credentials.TARGET_FIELDS.items()}
def forbidden(*args,**kwargs):
    raise RuntimeError('Protected effects disabled in preview')
credentials.store_secret=forbidden
credentials.clear=forbidden
import server
server._stop_pid=forbidden
server._watchdog_alive=lambda:False
server._scan['running']=True
con.close()
if __name__=='__main__':
    import uvicorn
    print(f'SCRATCH ONLY: {DB}',flush=True)
    uvicorn.run(server.app,host='127.0.0.1',port=8437)
