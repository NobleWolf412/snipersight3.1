"""Isolated append-only US-equity research store.

This schema is deliberately incompatible with the crypto store: asset IDs,
session labels and evidence scope are required on every record.  Fixture rows
can therefore be queried and demonstrated without ever joining the live book.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


STOCK_STORE_VERSION = "stock-store-v0.1-draft"
EVIDENCE_SCOPES = frozenset(("FIXTURE", "PROVIDER"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_candles (
  asset_id TEXT NOT NULL, symbol TEXT NOT NULL, tf TEXT NOT NULL,
  open_ts INTEGER NOT NULL, closed_at INTEGER NOT NULL,
  open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL,
  volume TEXT NOT NULL, session TEXT NOT NULL, source TEXT NOT NULL,
  evidence_scope TEXT NOT NULL CHECK(evidence_scope IN ('FIXTURE','PROVIDER')),
  PRIMARY KEY(asset_id, tf, open_ts, source)
);
CREATE TABLE IF NOT EXISTS stock_facts (
  id INTEGER PRIMARY KEY, asset_id TEXT NOT NULL, symbol TEXT NOT NULL,
  kind TEXT NOT NULL, market_time INTEGER NOT NULL, confirmed_at INTEGER NOT NULL,
  algo_version TEXT NOT NULL, payload TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
  evidence_scope TEXT NOT NULL CHECK(evidence_scope IN ('FIXTURE','PROVIDER'))
);
CREATE TABLE IF NOT EXISTS stock_paper_events (
  id INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, setup_id TEXT NOT NULL,
  event_type TEXT NOT NULL, occurred_at INTEGER NOT NULL, payload TEXT NOT NULL,
  simulator_version TEXT NOT NULL,
  evidence_scope TEXT NOT NULL CHECK(evidence_scope = 'FIXTURE')
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def _require_scope(value: str, *, paper: bool = False) -> None:
    allowed = frozenset(("FIXTURE",)) if paper else EVIDENCE_SCOPES
    if value not in allowed:
        raise ValueError(f"stock evidence scope must be one of {sorted(allowed)}")


def insert_fact(con: sqlite3.Connection, *, asset_id: str, symbol: str,
                kind: str, market_time: int, confirmed_at: int,
                algo_version: str, payload: dict, evidence_scope: str) -> bool:
    _require_scope(evidence_scope)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(
        f"{asset_id}|{kind}|{market_time}|{confirmed_at}|{algo_version}|{evidence_scope}|{canonical}".encode()
    ).hexdigest()
    before = con.total_changes
    con.execute(
        "INSERT OR IGNORE INTO stock_facts "
        "(asset_id,symbol,kind,market_time,confirmed_at,algo_version,payload,content_hash,evidence_scope) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (asset_id, symbol, kind, market_time, confirmed_at, algo_version,
         canonical, digest, evidence_scope),
    )
    return con.total_changes > before


def insert_candle(con: sqlite3.Connection, *, asset_id: str, symbol: str,
                  tf: str, bar: dict, session: str, source: str,
                  evidence_scope: str) -> bool:
    _require_scope(evidence_scope)
    before = con.total_changes
    con.execute(
        "INSERT OR IGNORE INTO stock_candles "
        "(asset_id,symbol,tf,open_ts,closed_at,open,high,low,close,volume,session,source,evidence_scope) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (asset_id, symbol, tf, int(bar["open_ts"]), int(bar["closed_at"]),
         str(bar["open"]), str(bar["high"]), str(bar["low"]), str(bar["close"]),
         str(bar["volume"]), session, source, evidence_scope),
    )
    return con.total_changes > before


def insert_paper_event(con: sqlite3.Connection, *, event_id: str, setup_id: str,
                       event_type: str, occurred_at: int, payload: dict,
                       simulator_version: str, evidence_scope: str = "FIXTURE") -> bool:
    _require_scope(evidence_scope, paper=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    before = con.total_changes
    con.execute(
        "INSERT OR IGNORE INTO stock_paper_events "
        "(event_id,setup_id,event_type,occurred_at,payload,simulator_version,evidence_scope) "
        "VALUES (?,?,?,?,?,?,?)",
        (event_id, setup_id, event_type, occurred_at, canonical,
         simulator_version, evidence_scope),
    )
    return con.total_changes > before
