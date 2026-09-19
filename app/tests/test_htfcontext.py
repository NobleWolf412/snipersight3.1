"""The operator's higher-timeframe reading: which side, how hard, and where.

Pinned because each branch is a sentence a trader acts on. The one that
matters most is COUNTER_INTO_RUNNING_MOVE — a trade against a rung that is
IMPULSE, the case this system's own records flag — and it must never be
folded into plain counter-trend, which is Reversal's normal, profitable case.
"""
from decimal import Decimal
import json

import pytest

from engine import htfcontext, store
from engine.liquidity import LIQ_VERSION


def rung(tf, phase):
    return {"tf": tf, "phase": phase}


# ---------------------------------------------------------------- the ladder

def test_the_ladder_stops_at_daily():
    """Operator ruling 2026-09-18: daily, not weekly — weekly history is thin
    on most perps and would usually read 'not available'."""
    assert htfcontext.rungs("15m") == ("1H", "4H", "1D")
    assert htfcontext.rungs("1H") == ("4H", "1D")
    assert htfcontext.rungs("4H") == ("1D",)
    assert htfcontext.rungs("1D") == ()


# ---------------------------------------------------------------- the stance

def test_a_short_into_a_running_move_is_named_as_such():
    s = htfcontext.stance("SHORT", [rung("1H", "IMPULSE_UP"), rung("4H", "DRIFT_DOWN"),
                                    rung("1D", "TREND_DOWN")])
    assert s["label"] == "COUNTER_INTO_RUNNING_MOVE"
    assert "1H is running up hard" in s["sentence"]
    # The first live read (PF_SUIUSD, 2026-09-18) had the daily WITH the short.
    # The warning leads; the supporting timeframe must not be dropped.
    assert "daily is with this trade" in s["sentence"]


def test_a_long_into_a_falling_move_is_named_as_such():
    s = htfcontext.stance("LONG", [rung("1H", "IMPULSE_DOWN")])
    assert s["label"] == "COUNTER_INTO_RUNNING_MOVE"
    assert "falling hard" in s["sentence"]


def test_plain_counter_trend_is_not_the_alarm():
    """Counter a confirmed trend — including a stretched one — is counter-trend,
    not a running move. Only an IMPULSE carries the alarm."""
    for phase in ("TREND_UP", "TREND_UP_EXTENDED"):
        assert htfcontext.stance("SHORT", [rung("1H", phase)])["label"] == "COUNTER_TREND"


def test_with_the_trend():
    s = htfcontext.stance("LONG", [rung("1H", "TREND_UP"), rung("1D", "TREND_UP")])
    assert s["label"] == "WITH_TREND"
    assert s["sentence"] == "With the trend on the 1H and daily."


def test_disagreeing_timeframes_are_mixed():
    s = htfcontext.stance("LONG", [rung("1H", "TREND_UP"), rung("1D", "TREND_DOWN")])
    assert s["label"] == "MIXED"
    assert "1H with this trade" in s["sentence"] and "daily against it" in s["sentence"]


def test_a_drift_or_a_turn_is_not_a_trend():
    """A fresh turn or an aged drift has a direction but not a trend's energy —
    the same split bias._DIRECTIONAL_PHASES makes. Against one is not
    counter-trend, and never the running-move alarm."""
    for phase in ("DRIFT_UP", "TURN_UP"):
        assert htfcontext.stance("SHORT", [rung("1H", phase)])["label"] == "NO_CLEAR_TREND"


def test_missing_history_is_not_a_market_condition():
    """Every rung unread is 'not enough history', never 'ranging'."""
    s = htfcontext.stance("SHORT", [rung("1H", "UNKNOWN"), rung("4H", "UNKNOWN")])
    assert s["label"] == "NOT_ENOUGH_HISTORY"
    assert "ranging" not in s["sentence"]
    assert htfcontext.stance("SHORT", [rung("1H", "RANGE")])["label"] == "NO_CLEAR_TREND"


def test_a_daily_setup_has_nothing_above_to_check():
    assert htfcontext.stance("SHORT", [])["label"] == "NO_HIGHER_TIMEFRAME"


# ---------------------------------------------------------------- the pools

def pool(tf, side, level, confirmed_at=100, broken_at=None, swept_at=None, members=2):
    return {"tf": tf, "side": side, "level": Decimal(level), "members": members,
            "confirmed_at": confirmed_at, "broken_at": broken_at, "swept_at": swept_at}


def test_against_a_short_is_the_pool_above_and_against_a_long_the_pool_below():
    pools = {"1H": [pool("1H", "HIGH", "110"), pool("1H", "LOW", "90")]}
    short = htfcontext.pools_around(pools, "SHORT", "100", 1000)
    assert [p["level"] for p in short["against"]] == ["110"]
    assert [p["level"] for p in short["toward"]] == ["90"]
    long = htfcontext.pools_around(pools, "LONG", "100", 1000)
    assert [p["level"] for p in long["against"]] == ["90"]
    assert [p["level"] for p in long["toward"]] == ["110"]


def test_the_nearest_pool_on_each_timeframe_is_the_one_shown():
    pools = {"1H": [pool("1H", "HIGH", "130"), pool("1H", "HIGH", "105")],
             "1D": [pool("1D", "HIGH", "150")]}
    out = htfcontext.pools_around(pools, "SHORT", "100", 1000)["against"]
    assert [(p["tf"], p["level"]) for p in out] == [("1H", "105"), ("1D", "150")]
    assert out[0]["distance_pct"] == "5.00"


def test_a_pool_on_the_wrong_side_of_price_is_not_counted():
    """Equal highs BELOW price are already taken out; they are not buy-stop
    liquidity waiting above a short."""
    pools = {"1H": [pool("1H", "HIGH", "95")]}
    assert htfcontext.pools_around(pools, "SHORT", "100", 1000)["against"] == []


def test_pools_respect_what_was_knowable_and_what_was_broken():
    pools = {"1H": [pool("1H", "HIGH", "105", confirmed_at=2000),        # not yet knowable
                    pool("1H", "HIGH", "106", broken_at=500),             # already broken
                    pool("1H", "HIGH", "107", broken_at=5000)]}           # broken LATER
    out = htfcontext.pools_around(pools, "SHORT", "100", 1000)["against"]
    assert [p["level"] for p in out] == ["107"]


def test_a_swept_pool_says_so_and_only_once_the_sweep_happened():
    pools = {"1H": [pool("1H", "HIGH", "105", swept_at=800)]}
    before = htfcontext.pools_around(pools, "SHORT", "100", 700)["against"][0]
    after = htfcontext.pools_around(pools, "SHORT", "100", 900)["against"][0]
    assert not before["swept"] and after["swept"]
    assert after["status"] == "swept once, by a closed 1H candle"


def test_an_unswept_pool_claims_only_what_was_recorded():
    """Never "untouched". A pool is read from COMPLETED candles on its own
    timeframe, and a candle that trades through and closes just past the level
    records neither a sweep nor a break — so the most the record supports is
    that no sweep was recorded by the last closed candle (cold audit)."""
    status = htfcontext.pools_around({"1D": [pool("1D", "HIGH", "105")]},
                                     "SHORT", "100", 1000)["against"][0]["status"]
    assert status == "no sweep recorded by the last closed 1D candle"
    assert "untouched" not in status


def test_no_liquidity_record_is_not_the_same_as_no_pool_in_the_way():
    """Otherwise an unmeasured market sorts as the one with the most room."""
    measured = htfcontext.pools_around({"1H": [pool("1H", "LOW", "90")], "4H": []},
                                       "SHORT", "100", 1000)
    assert measured["against"] == [] and measured["measured"] == ["1H"]
    assert htfcontext.pools_around({"1H": []}, "SHORT", "100", 1000)["measured"] == []


def test_distance_in_atr_only_when_an_atr_is_given():
    pools = {"1H": [pool("1H", "HIGH", "110")]}
    assert htfcontext.pools_around(pools, "SHORT", "100", 1000)["against"][0]["distance_atr"] is None
    assert htfcontext.pools_around(pools, "SHORT", "100", 1000,
                                   atr=Decimal("2"))["against"][0]["distance_atr"] == "5.00"


# ---------------------------------------------------------------- from the store

@pytest.fixture
def con(tmp_path):
    c = store.connect(tmp_path / "htf.db")
    yield c
    c.close()


def liq(con, tf, at, payload):
    store.insert_fact(con, symbol="TESTUSDT", tf=tf, kind="liquidity",
                      market_time=at - 3600, confirmed_at=at,
                      algo_version=LIQ_VERSION, payload=payload)


def test_pools_load_with_their_sweep_and_break(con):
    base = {"pool_id": "p", "side": "HIGH", "level": "105", "n_members": 3}
    liq(con, "1H", 1000, {**base, "event": "POOL"})
    liq(con, "1H", 2000, {**base, "event": "SWEEP"})
    liq(con, "1H", 3000, {**base, "event": "BROKEN"})
    liq(con, "1H", 4000, {"pool_id": "ghost", "event": "SWEEP"})    # no POOL: ignored
    con.commit()
    loaded = htfcontext.load_pools(con, "TESTUSDT", ("1H",))["1H"]
    assert len(loaded) == 1
    p = loaded[0]
    assert (p["confirmed_at"], p["swept_at"], p["broken_at"], p["members"]) == (1000, 2000, 3000, 3)


def test_the_whole_reading_on_a_market_with_no_history(con):
    """A freshly listed market must read as unmeasured, not crash and not
    invent a trend."""
    r = htfcontext.read(con, "NEWUSDT", "15m", "SHORT", "1.00", 10_000)
    assert [x["tf"] for x in r["ladder"]] == ["1H", "4H", "1D"]
    assert r["stance"]["label"] == "NOT_ENOUGH_HISTORY"
    assert r["pools"] == {"against": [], "toward": [], "measured": []}
    assert all(l["resistance"] is None and l["support"] is None for l in r["levels"])
    json.dumps(r)                                   # the wire shape is plain JSON
