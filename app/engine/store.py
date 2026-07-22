"""Fact store — SQLite, append-only facts with full time/version lineage.

Constitution refs: §4 determinism, §5 causality, §7 versioning, §8 auditability.
Prices are stored as TEXT (exact decimal strings as received from the venue);
all arithmetic upstream uses Decimal. Facts are append-only: re-running an
engine over identical data must be a no-op (INSERT OR IGNORE on content_hash).
"""
import hashlib
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "snipersight.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol      TEXT NOT NULL,
    tf          TEXT NOT NULL,           -- 15m | 1H | 4H | 1D | 1W
    open_ts     INTEGER NOT NULL,        -- bucket start, epoch seconds UTC
    open        TEXT NOT NULL,
    high        TEXT NOT NULL,
    low         TEXT NOT NULL,
    close       TEXT NOT NULL,
    volume      TEXT NOT NULL,
    source      TEXT NOT NULL,           -- 'coinbase' | 'agg:1H' | 'agg:1D'
    imported_at INTEGER NOT NULL,
    PRIMARY KEY (symbol, tf, open_ts)
);

CREATE TABLE IF NOT EXISTS facts (
    id            INTEGER PRIMARY KEY,
    symbol        TEXT NOT NULL,
    tf            TEXT NOT NULL,
    kind          TEXT NOT NULL,         -- 'swing'
    market_time   INTEGER NOT NULL,      -- when the fact occurred in market time
    confirmed_at  INTEGER NOT NULL,      -- when the system could first know it (§5)
    invalidated_at INTEGER,
    algo_version  TEXT NOT NULL,
    payload       TEXT NOT NULL,         -- canonical JSON (sorted keys)
    content_hash  TEXT NOT NULL,
    producer_run_id TEXT,
    UNIQUE (content_hash)
);
CREATE INDEX IF NOT EXISTS ix_facts_query
    ON facts (symbol, tf, kind, algo_version, confirmed_at);
CREATE INDEX IF NOT EXISTS ix_facts_feed
    ON facts (kind, algo_version, confirmed_at, id);

CREATE TABLE IF NOT EXISTS manifests (
    manifest_hash TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    payload       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_log (
    id          INTEGER PRIMARY KEY,
    symbol      TEXT NOT NULL,
    tf          TEXT NOT NULL,
    range_start INTEGER NOT NULL,
    range_end   INTEGER NOT NULL,
    n_candles   INTEGER NOT NULL,
    n_gaps      INTEGER NOT NULL,
    gaps        TEXT NOT NULL,           -- JSON list of missing open_ts
    source      TEXT NOT NULL,
    run_at      INTEGER NOT NULL,
    n_bad       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quality_runs (
    id          INTEGER PRIMARY KEY,
    observed_at INTEGER NOT NULL,
    status      TEXT NOT NULL,
    evaluation_allowed INTEGER NOT NULL,
    summary     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_checks (
    id          INTEGER PRIMARY KEY,
    quality_run_id INTEGER NOT NULL,
    stage       TEXT NOT NULL,
    status      TEXT NOT NULL,
    code        TEXT NOT NULL,
    symbol      TEXT,
    tf          TEXT,
    details     TEXT NOT NULL,
    FOREIGN KEY (quality_run_id) REFERENCES quality_runs(id)
);
CREATE INDEX IF NOT EXISTS ix_quality_checks_run
    ON quality_checks (quality_run_id, stage, status);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    _migrate(con)
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """Small explicit migration runner; every schema change is recorded."""
    applied = {r[0] for r in con.execute(
        "SELECT version FROM schema_migrations").fetchall()}
    if 1 not in applied:
        columns = {r[1] for r in con.execute("PRAGMA table_info(import_log)").fetchall()}
        if "n_bad" not in columns:
            con.execute(
                "ALTER TABLE import_log ADD COLUMN n_bad INTEGER NOT NULL DEFAULT 0")
        con.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (1, "import_log_n_bad"))
    if 2 not in applied:
        con.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (2, "manifests_and_feed_index"))
    if 3 not in applied:
        con.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (3, "pipeline_quality_contract"))
    if 4 not in applied:
        columns = {r[1] for r in con.execute("PRAGMA table_info(facts)").fetchall()}
        if "producer_run_id" not in columns:
            con.execute("ALTER TABLE facts ADD COLUMN producer_run_id TEXT")
        con.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (4, "fact_producer_run_lineage"))
    con.commit()


def canonical_payload(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def record_manifest(con, kind: str, payload: dict) -> str:
    """Persist an immutable, content-addressed run/config manifest."""
    canonical = canonical_payload(payload)
    digest = hashlib.sha256(f"{kind}|{canonical}".encode()).hexdigest()
    con.execute(
        "INSERT OR IGNORE INTO manifests (manifest_hash, kind, payload) VALUES (?,?,?)",
        (digest, kind, canonical))
    return digest


def get_manifest(con, manifest_hash: str) -> dict | None:
    row = con.execute(
        "SELECT kind, payload FROM manifests WHERE manifest_hash=?", (manifest_hash,)
    ).fetchone()
    return None if row is None else {"kind": row[0], **json.loads(row[1])}


def fact_hash(symbol: str, tf: str, kind: str, market_time: int,
              algo_version: str, payload: str) -> str:
    key = f"{symbol}|{tf}|{kind}|{market_time}|{algo_version}|{payload}"
    return hashlib.sha256(key.encode()).hexdigest()


def insert_fact(con, *, symbol: str, tf: str, kind: str, market_time: int,
                confirmed_at: int, algo_version: str, payload: dict) -> bool:
    """Append a fact. Returns True if newly inserted, False if it already existed."""
    p = canonical_payload(payload)
    h = fact_hash(symbol, tf, kind, market_time, algo_version, p)
    from .runlog import current_run_id
    cur = con.execute(
        "INSERT OR IGNORE INTO facts "
        "(symbol, tf, kind, market_time, confirmed_at, algo_version, payload, "
        "content_hash, producer_run_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (symbol, tf, kind, market_time, confirmed_at, algo_version, p, h,
         current_run_id()))
    return cur.rowcount == 1


def get_candles(con, symbol: str, tf: str, start_ts: int = 0,
                end_ts: int = 2**53, limit: int | None = None) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    q = ("SELECT * FROM candles WHERE symbol=? AND tf=? AND open_ts>=? AND open_ts<? "
         "ORDER BY open_ts")
    rows = con.execute(q, (symbol, tf, start_ts, end_ts)).fetchall()
    if limit is not None:
        rows = rows[-limit:]
    return rows


def get_facts(con, symbol: str, tf: str, kind: str, algo_version: str,
              as_of: int | None = None) -> list[sqlite3.Row]:
    """The as_of-cursored query (§5): only facts confirmed at or before as_of."""
    con.row_factory = sqlite3.Row
    q = ("SELECT * FROM facts WHERE symbol=? AND tf=? AND kind=? AND algo_version=?")
    args: list = [symbol, tf, kind, algo_version]
    if as_of is not None:
        q += " AND confirmed_at<=?"
        args.append(as_of)
    # Lifecycle facts often share market_time (for example PLACED then FILLED).
    # Stable causal ordering prevents callers from mistaking an older event for
    # the current state when timestamps tie.
    q += " ORDER BY market_time, confirmed_at, id"
    return con.execute(q, args).fetchall()
