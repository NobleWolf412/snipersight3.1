"""Run logging — every engine invocation is recorded (file log + engine_runs table).

Debug-first discipline: when output looks wrong, `SELECT * FROM engine_runs
ORDER BY id DESC` shows exactly what ran, over what inputs, producing how many
facts, in what order. The file log (data/engine.log) carries the same trail in
human-readable form.
"""
import logging
import hashlib
import json
import time
import uuid
from contextvars import ContextVar
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "engine.log"

# The index exists for ONE reader: `/api/overview` asks for the last run of
# each engine, and this table is append-only and enormous — 3,038,265 rows at
# 2026-08-05, roughly 300 MB. Unindexed, "last run per engine" is a full table
# scan: it measured **2,432 ms of the endpoint's 2,900 ms**, on the 30s poll
# every cockpit surface waits behind, dragging that much of the store through
# the page cache each time and slowing everything else reading the same file.
# With the index the same answer is 22 seeks. Descending on run_at so the
# newest row of an engine is the first entry reached rather than the last.
RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS engine_runs (
    id           INTEGER PRIMARY KEY,
    engine       TEXT NOT NULL,
    algo_version TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    tf           TEXT NOT NULL,
    n_inputs     INTEGER NOT NULL,
    n_new_facts  INTEGER NOT NULL,
    duration_ms  INTEGER NOT NULL,
    run_at       INTEGER NOT NULL,
    notes        TEXT NOT NULL DEFAULT ''
    ,run_id       TEXT NOT NULL DEFAULT ''
    ,status       TEXT NOT NULL DEFAULT 'PASS'
    ,input_watermark INTEGER
    ,input_fingerprint TEXT NOT NULL DEFAULT ''
    ,output_fingerprint TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_engine_runs_engine_recent
    ON engine_runs (engine, run_at DESC);
"""

_logger = None
_CURRENT_RUN_ID = ContextVar("snipersight_run_id", default=None)


def current_run_id():
    return _CURRENT_RUN_ID.get()


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        lg = logging.getLogger("snipersight")
        lg.setLevel(logging.DEBUG)
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-5s %(message)s", "%Y-%m-%d %H:%M:%S"))
        lg.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)-5s %(message)s"))
        sh.setLevel(logging.INFO)
        lg.addHandler(sh)
        _logger = lg
    return _logger


class RunRecorder:
    """Context manager: times an engine run and records it on exit."""

    def __init__(self, con, engine: str, algo_version: str, symbol: str, tf: str):
        self.con, self.engine, self.version = con, engine, algo_version
        self.symbol, self.tf = symbol, tf
        self.n_inputs = self.n_new_facts = 0
        self.notes = ""

    def __enter__(self):
        self.con.executescript(RUNS_SCHEMA)
        columns = {r[1] for r in self.con.execute("PRAGMA table_info(engine_runs)")}
        for name, definition in (
                ("run_id", "TEXT NOT NULL DEFAULT ''"),
                ("status", "TEXT NOT NULL DEFAULT 'PASS'"),
                ("input_watermark", "INTEGER"),
                ("input_fingerprint", "TEXT NOT NULL DEFAULT ''"),
                ("output_fingerprint", "TEXT NOT NULL DEFAULT ''")):
            if name not in columns:
                self.con.execute(f"ALTER TABLE engine_runs ADD COLUMN {name} {definition}")
        self.run_id = uuid.uuid4().hex
        self._run_token = _CURRENT_RUN_ID.set(self.run_id)
        self.input_watermark, self.input_fingerprint = self._fingerprint()
        self.t0 = time.monotonic()
        return self

    def _fingerprint(self):
        candle_where, fact_where, args = "", "", []
        if self.symbol != "PORTFOLIO":
            candle_where = " WHERE symbol=?" + (" AND tf=?" if self.tf != "ALL" else "")
            fact_where = candle_where
            args = [self.symbol] + ([self.tf] if self.tf != "ALL" else [])
        candles = self.con.execute(
            "SELECT COUNT(*),COALESCE(MAX(open_ts),0),COALESCE(MAX(imported_at),0) "
            "FROM candles" + candle_where, args).fetchone()
        facts = self.con.execute(
            "SELECT COUNT(*),COALESCE(MAX(id),0),COALESCE(MAX(confirmed_at),0) "
            "FROM facts" + fact_where, args).fetchone()
        snapshot = {"candles": list(candles), "facts": list(facts)}
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        return max(candles[1], facts[2]), digest

    def __exit__(self, exc_type, exc, tb):
        ms = int((time.monotonic() - self.t0) * 1000)
        if exc:
            self.notes = f"ERROR: {exc}"[:500]
        _, output_fingerprint = self._fingerprint()
        status = "ERROR" if exc else "PASS"
        self.con.execute(
            "INSERT INTO engine_runs "
            "(engine, algo_version, symbol, tf, n_inputs, n_new_facts, duration_ms, run_at, notes,"
            "run_id,status,input_watermark,input_fingerprint,output_fingerprint) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.engine, self.version, self.symbol, self.tf, self.n_inputs,
             self.n_new_facts, ms, int(time.time()), self.notes, self.run_id,
             status, self.input_watermark, self.input_fingerprint, output_fingerprint))
        self.con.commit()
        get_logger().log(
            logging.ERROR if exc else logging.DEBUG,
            f"{self.engine:10s} {self.version:22s} {self.symbol:8s} {self.tf:3s} "
            f"in={self.n_inputs:6d} new={self.n_new_facts:5d} {ms}ms {self.notes}")
        _CURRENT_RUN_ID.reset(self._run_token)
        return False
