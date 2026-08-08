"""Test-process bootstrap. Both runners import this package first.

The logger paths are redirected BEFORE any test can build the singleton,
because `data/engine-audit.log` is the permanent evidence file — the record
of real operator actions — and the suites drive the real app: within twelve
hours of the file existing it held 78 MANUAL ARM lines, every one a fixture,
byte-identical in shape to a real arm, and zero real ones. A test suite that
writes fabricated evidence into the file that answers "did I arm this trade"
defeats the file's entire reason to exist (audit 2026-08-08).

This runs for `python -m pytest tests` and `python -m unittest discover -s
tests` alike — both import the `tests` package before collecting from it.
"""
import tempfile
from pathlib import Path

from engine import runlog

_LOG_DIR = Path(tempfile.mkdtemp(prefix="snipersight-test-logs-"))
runlog.LOG_PATH = _LOG_DIR / "engine.log"
runlog.AUDIT_PATH = _LOG_DIR / "engine-audit.log"
