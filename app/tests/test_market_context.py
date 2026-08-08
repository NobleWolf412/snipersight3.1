import json
import sqlite3

from engine import market_context, regime, store, structure, volatility


def memory():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE candles(symbol TEXT,tf TEXT,open_ts INTEGER,open TEXT,high TEXT,low TEXT,close TEXT,volume TEXT,source TEXT,ingested_at INTEGER)")
    con.execute("CREATE TABLE facts(id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT,tf TEXT,kind TEXT,market_time INTEGER,confirmed_at INTEGER,algo_version TEXT,payload TEXT,payload_hash TEXT,producer_run_id TEXT)")
    return con


def fact(con, kind, version, at, payload):
    con.execute(
        "INSERT INTO facts(symbol,tf,kind,market_time,confirmed_at,algo_version,payload,payload_hash) VALUES('BTCUSDT','15m',?,?,?,?,?,?)",
        (kind, at - 900, at, version, json.dumps(payload), str(at) + kind))


def test_context_marks_stale_data_unstable_even_when_old_regime_was_trending():
    con = memory()
    con.execute("INSERT INTO candles VALUES('BTCUSDT','15m',0,'1','1','1','1','1','x',1)")
    fact(con, "regime", regime.REGIME_VERSION, 900, {"regime": "BULL_TREND"})
    row = market_context.snapshot(con, "BTCUSDT", "15m", as_of=10_000)
    assert row["regime"] == "UNSTABLE"
    assert row["data_status"] == "DEGRADED"


def test_context_promotes_squeeze_to_compression_on_fresh_closed_data():
    con = memory()
    con.execute("INSERT INTO candles VALUES('BTCUSDT','15m',900,'1','1','1','1','1','x',1)")
    fact(con, "regime", regime.REGIME_VERSION, 1800, {"regime": "RANGE"})
    fact(con, "volatility", volatility.VOLATILITY_VERSION, 1800,
         {"event": "SQUEEZE", "squeeze": "ON"})
    row = market_context.snapshot(con, "BTCUSDT", "15m", as_of=1800)
    assert row["regime"] == "COMPRESSION"
    assert row["timeframe"] == "15m"
