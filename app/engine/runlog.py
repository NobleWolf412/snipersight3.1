"""Run logging — every engine invocation is recorded (file log + engine_runs table).

Debug-first discipline: when output looks wrong, `SELECT * FROM engine_runs
ORDER BY id DESC` shows exactly what ran, over what inputs, producing how many
facts, in what order. The file log (data/engine.log) carries the same trail in
human-readable form.
"""
import logging
import time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "engine.log"

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
);
"""

_logger = None


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
        self.t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        ms = int((time.monotonic() - self.t0) * 1000)
        if exc:
            self.notes = f"ERROR: {exc}"[:500]
        self.con.execute(
            "INSERT INTO engine_runs "
            "(engine, algo_version, symbol, tf, n_inputs, n_new_facts, duration_ms, run_at, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (self.engine, self.version, self.symbol, self.tf, self.n_inputs,
             self.n_new_facts, ms, int(time.time()), self.notes))
        self.con.commit()
        get_logger().log(
            logging.ERROR if exc else logging.DEBUG,
            f"{self.engine:10s} {self.version:22s} {self.symbol:8s} {self.tf:3s} "
            f"in={self.n_inputs:6d} new={self.n_new_facts:5d} {ms}ms {self.notes}")
        return False
