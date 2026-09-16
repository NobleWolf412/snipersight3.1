"""Scratch-only prospective zone comparison and timing contracts."""
import json
from pathlib import Path
import multiprocessing
from decimal import Decimal
from unittest.mock import patch

import pytest
from engine import costs, execution, store, zonestudy as study

START = 1800000
STEP = 300


def bar(i, low="99", high="101", close="100", opening="100", observed=None):
    c = dict(open_ts=START+i*STEP, open=opening, high=high, low=low, close=close, volume="1")
    if observed is not None:
        c["observed_at"] = observed
    return c


def model():
    return dict(symbol="BTCUSDT", tf="15m", management_tf="5m", direction="LONG", stop="97", target="110", max_bars=100, cost_profile=costs.profile_for("BTCUSDT").version)


def fill():
    return dict(entry="100", quantity="10", at=START, entry_role="MAKER", warmup=[bar(i) for i in range(-20,0)])


def swing_bars(observed=None):
    lows=["99","98.5","98.2","98.7","99","99.8","99.5","99.2","99.6","99.9","100","100"]
    return [bar(i,low=v, high="102", close="101", opening="101",observed=observed) for i,v in enumerate(lows)]


def test_next_boundary_and_observation_delay():
    arms=study.simulate(model(),fill(),swing_bars(START+10*STEP+1))
    assert arms["SWING_IDEAL"]["moves"][0]["at"] == START+10*STEP
    assert arms["SWING_OBSERVED"]["moves"][0]["at"] == START+11*STEP
    assert Decimal(arms["SWING_IDEAL"]["moves"][0]["price"]) < Decimal("99.2")


def test_gap_through_late_stop_is_not_credited():
    bars=swing_bars(START+10*STEP+1)
    bars[-1]=bar(11,low="98",high="99",opening="98.1",close="98.5")
    arms=study.simulate(model(),fill(),bars)
    assert not arms["SWING_OBSERVED"]["moves"]
    assert arms["SWING_OBSERVED"]["diagnostics"][0]["kind"] == "MISSED"
    assert arms["SWING_IDEAL"]["result"]["outcome"] == "SL"


def test_deadline_parent_time_not_management_count():
    p=model();p["max_bars"]=2
    arms=study.simulate(p,fill(),[bar(i) for i in range(6)])
    assert all(a["result"]["at"] == START+5*STEP for a in arms.values())
    assert all(a["result"]["outcome"] == "TIMEOUT" for a in arms.values())


def test_entry_parent_target_not_credited_and_stop_is_conservative():
    bars=[bar(0,high="111"),bar(1),bar(2),bar(3,low="96",high="111")]
    arms=study.simulate(model(),fill(),bars)
    assert all(a["result"]["at"] == START+3*STEP for a in arms.values())
    assert all(a["result"]["ambiguous"] for a in arms.values())
    assert all(not a["moves"] for a in arms.values())


def test_short_mirrors_stop_prices():
    p=model();f=fill();bars=swing_bars()
    original=study.simulate(p,f,bars)
    p.update(direction="SHORT",stop="103",target="90")
    def mirror(c):
        return dict(c,open=str(200-Decimal(c["open"])),close=str(200-Decimal(c["close"])),low=str(200-Decimal(c["high"])),high=str(200-Decimal(c["low"])))
    f["warmup"]=[mirror(c) for c in f["warmup"]]
    result=study.simulate(p,f,[mirror(c) for c in bars])
    assert Decimal(result["SWING_IDEAL"]["moves"][0]["price"]) == 200-Decimal(original["SWING_IDEAL"]["moves"][0]["price"])


def test_zone_detection_defense_then_next_bar_move():
    # Supply deterministic confirmed pivots/ATR to isolate zone lifecycle timing.
    f=fill();bars=[bar(i) for i in range(8)]
    bars[3]=bar(3,low="99",high="101",opening="100.5",close="100")
    bars[4]=bar(4,low="100",high="104",opening="100",close="103")
    bars[5]=bar(5,low="99.5",high="104",opening="103",close="102")
    def pivot(c,j,low):
        return Decimal("102") if j==len(f["warmup"])+2 and not low else None
    with patch.object(study,"_pivot",side_effect=pivot),patch.object(study.swings,"compute_atr",side_effect=lambda c:[Decimal("1")]*len(c)):
        arms=study.simulate(model(),f,bars)
    events=arms["HOLD"]["zones"]
    assert events[0]["kind"] == "FORMED"
    assert events[0]["at"] == START+5*STEP
    assert events[1]["kind"] == "DEFENDED"
    assert arms["ZONE_IDEAL"]["moves"][0]["at"] == START+6*STEP
    assert arms["ZONE_IDEAL"]["moves"][0]["price"] == "98.75"


@pytest.fixture
def con(tmp_path):
    c=store.connect(tmp_path/"zones.db");execution._ensure(c);c.commit();study.run(c,now=START)
    yield c
    c.close()


def source(c):
    p=dict(symbol="BTCUSDT",timeframe="15m",direction="LONG",stop="97",targets=["110"])
    c.execute("INSERT INTO execution_outbox(idempotency_key,intent_id,mode,setup_id,symbol,payload,state,created_at,updated_at,origin,controller,grade_eligible) VALUES ('new','new','PAPER','new','BTCUSDT',?,'PAPER_FILLED',?,?,'BOT','BOT',1)",(json.dumps({"intent":p}),START,START))
    c.execute("INSERT INTO paper_positions(intent_id,symbol,tf,direction,quantity,entry,stop,target,state,filled_at,entry_role) VALUES ('new','BTCUSDT','15m','LONG','10','100','97','110','OPEN',?,'MAKER')",(START,));c.commit()


def candles(c,bars):
    for b in bars:
        c.execute("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",("BTCUSDT","5m",b["open_ts"],b["open"],b["high"],b["low"],b["close"],"1","FIXTURE",b["open_ts"]+STEP))
    c.commit()


def test_frozen_observation_gap_and_account_isolation(con):
    source(con);candles(con,[bar(i) for i in range(-20,2)]+[bar(3)])
    before=[tuple(r) for r in con.execute("SELECT * FROM paper_positions")]
    study.run(con,now=START+4*STEP)
    r=study._records(con)["paper:new"]
    assert len([k for k in r if k.startswith("BAR:")]) == 2
    assert r["BAR:"+str(START)]["observed_at"] == START+4*STEP
    assert ("BTCUSDT","5m") in study.unresolved(con)
    candles(con,[bar(2),bar(4,low="96")]);study.run(con,now=START+6*STEP)
    r=study._records(con)["paper:new"]
    assert r["BAR:"+str(START)]["observed_at"] == START+4*STEP
    assert r["BAR:"+str(START+2*STEP)]["observed_at"] == START+6*STEP
    assert study.report(con,now=START+6*STEP)["paired_count"] == 1
    assert [tuple(r) for r in con.execute("SELECT * FROM paper_positions")] == before
    assert not study.unresolved(con)


def test_missing_warmup_excludes_instead_of_false_no_signal(con):
    source(con);study.run(con,now=START+STEP)
    assert study.report(con,now=START+STEP)["excluded_count"] == 1


def test_strategy_group_comes_from_frozen_source_identity(con):
    source(con)
    con.execute("UPDATE execution_outbox SET setup_id='BTCUSDT|15m|PULLBACK|zone|version'")
    con.commit()
    candles(con,[bar(i) for i in range(-20,4)]+[bar(4,low="96")])
    study.run(con,now=START+6*STEP)
    report=study.report(con,now=START+6*STEP)
    assert report["items"][0]["strategy"] == "PULLBACK"
    assert report["groups"]["PAPER / PULLBACK / 15m"]["count"] == 1


def worker(path):
    c=store.connect(Path(path));study.run(c,now=START+STEP);c.close()


def test_two_process_enrollment_is_idempotent(con):
    source(con);candles(con,[bar(i) for i in range(-20,1)])
    path=con.execute("PRAGMA database_list").fetchone()[2]
    workers=[multiprocessing.get_context("spawn").Process(target=worker,args=(path,)) for _ in range(2)]
    for w in workers:w.start()
    for w in workers:
        w.join(20)
        if w.is_alive():w.terminate();pytest.fail("Writer hung")
        assert w.exitcode == 0
    assert con.execute("SELECT COUNT(*) FROM zone_study_events WHERE event='ENROLLED'").fetchone()[0] == 1


@pytest.mark.parametrize("breach",[True,False])
def test_zone_breach_or_expiry_cannot_move_stop(breach):
    f=fill();bars=[bar(i,low="102",high="104",opening="103",close="103") for i in range(18)]
    bars[:4]=[bar(i) for i in range(4)]
    bars[3]=bar(3,low="99",high="101",opening="100.5",close="100")
    bars[4]=bar(4,low="100",high="104",opening="100",close="103")
    if breach:bars[5]=bar(5,low="98.9",high="104",opening="103",close="102")
    def pivot(c,j,low):return Decimal("102") if j==len(f["warmup"])+2 and not low else None
    with patch.object(study,"_pivot",side_effect=pivot),patch.object(study.swings,"compute_atr",side_effect=lambda c:[Decimal("1")]*len(c)):
        arms=study.simulate(model(),f,bars)
    assert [e["kind"] for e in arms["HOLD"]["zones"]] == ["FORMED","BROKE" if breach else "EXPIRED"]
    assert not arms["ZONE_IDEAL"]["moves"]
    if not breach:assert arms["HOLD"]["zones"][-1]["at"] == START+17*STEP


def test_catchup_proposals_at_same_boundary_keep_tightest_move():
    f=fill();bars=[bar(i,low="99.9",high="103",opening="102",close="102",observed=START+10*STEP+1) for i in range(13)]
    def pivot(c,j,low):
        if not low:return None
        return {len(f["warmup"])-1:Decimal("98"),len(f["warmup"])+4:Decimal("99"),len(f["warmup"])+7:Decimal("100")}.get(j)
    with patch.object(study,"_pivot",side_effect=pivot),patch.object(study.swings,"compute_atr",side_effect=lambda c:[Decimal("1")]*len(c)):
        arms=study.simulate(model(),f,bars)
    moves=arms["SWING_OBSERVED"]["moves"]
    assert len(moves)==1
    assert moves[0]["price"]=="99.75"
    assert moves[0]["at"]==START+11*STEP


def test_report_readonly_and_dependency_pause(con):
    con.execute("PRAGMA query_only=ON")
    assert study.report(con,now=START)["state"]=="COLLECTING"
    with patch.object(study,"DEPENDENCIES",{}):
        assert study.report(con,now=START)["state"]=="PAUSED"
