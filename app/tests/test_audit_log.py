"""The evidence stream — what `data/engine-audit.log` must and must not carry.

`engine.log` is 98.5% DEBUG run lines duplicating the engine_runs table, and it
grows ~26 MB/day (docs/SPEC-log-retention.md). It will eventually be rotated.
The lines that exist nowhere else — operator write actions, degraded paths,
failures — are 0.6% of the volume, so a size cap on the hot stream discards
them at the same rate as the noise.

These tests pin the split. A regression here is silent by construction: the app
keeps running, the console keeps painting, and the only symptom is that months
later the one file that recorded an operator arming a real trade does not have
the line in it.
"""
import logging
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import runlog  # noqa: E402


class AuditStreamCase(unittest.TestCase):
    """Drives the real get_logger() with both files redirected to a temp dir."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved_singleton = runlog._logger
        self._saved_paths = (runlog.LOG_PATH, runlog.AUDIT_PATH)
        # logging.getLogger() is process-global: park any handlers a previous
        # test installed and put them back in tearDown, or this suite silences
        # every later test that logs.
        self.lg = logging.getLogger("snipersight")
        self._saved_handlers = list(self.lg.handlers)
        for h in self._saved_handlers:
            self.lg.removeHandler(h)

        runlog._logger = None
        runlog.LOG_PATH = self.tmp / "engine.log"
        runlog.AUDIT_PATH = self.tmp / "engine-audit.log"
        self.log = runlog.get_logger()

    def tearDown(self):
        for h in list(self.lg.handlers):
            h.close()
            self.lg.removeHandler(h)
        for h in self._saved_handlers:
            self.lg.addHandler(h)
        runlog._logger = self._saved_singleton
        runlog.LOG_PATH, runlog.AUDIT_PATH = self._saved_paths
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read(self, which):
        p = self.tmp / which
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def hot(self):
        return self._read("engine.log")

    def audit(self):
        return self._read("engine-audit.log")

    # ---------------------------------------------------------------- kept

    def test_a_degraded_path_warning_reaches_the_evidence_stream(self):
        """The convention that a fallback must be audible is enforced by this
        file existing, not by a test of the fallback itself."""
        self.log.warning("perp ranking unavailable, spot-only this refresh: boom")
        self.assertIn("perp ranking unavailable", self.audit())
        self.assertIn("perp ranking unavailable", self.hot())

    def test_an_error_reaches_the_evidence_stream(self):
        self.log.error("live cycle failed: ConnectionResetError")
        self.assertIn("live cycle failed", self.audit())

    def test_every_operator_write_action_is_kept(self):
        """One line per irreversible thing the operator can do to a real book."""
        actions = {
            "CREDENTIAL": "CREDENTIAL stored: phemex/key",
            "MANUAL ARM": "MANUAL ARM BTC-USD 1H LONG entry 60000",
            "MANUAL ARM REFUSED": "MANUAL ARM REFUSED BTC-USD 1H LONG — nothing written",
            "MANUAL CANCEL": "MANUAL CANCEL BTC-USD 1H abc123 (paper)",
            "OPERATOR CLOSED": "OPERATOR CLOSED BTC-USD 1H early at 61000 (1.2R)",
            "OPERATOR ADOPTED": "OPERATOR ADOPTED BTC-USD 1H — sl 59000 tp 63000",
            "SETTINGS CHANGED": "SETTINGS CHANGED: ['risk_pct']",
            "MANUAL SCAN": "MANUAL SCAN requested from cockpit",
        }
        for name, line in actions.items():
            with self.subTest(action=name):
                self.log.info(line)
                self.assertIn(line, self.audit(),
                              f"{name} is an operator write action and must be kept")

    # -------------------------------------------------------------- dropped

    def test_the_run_line_that_is_985_percent_of_the_log_is_not_duplicated(self):
        """RunRecorder's DEBUG line is already a row in engine_runs, with more
        detail than the text carries. Copying it here would rebuild the exact
        problem the split exists to solve."""
        self.log.debug("swings     swings-v0.4-draft    BTC-USD  1H  "
                       "in=  1200 new=   14 82ms")
        self.assertIn("swings-v0.4-draft", self.hot())
        self.assertEqual("", self.audit())

    def test_loop_heartbeat_is_not_kept(self):
        for line in ("sleeping 60.0s until 21:48:03",
                     "cycle done — 22 symbols",
                     "awake",
                     "WAL checkpoint returned (0, 12, 12)"):
            with self.subTest(line=line):
                self.log.info(line)
        self.assertEqual("", self.audit())
        self.assertIn("cycle done", self.hot())

    def test_the_evidence_stream_is_a_subset_never_a_replacement(self):
        """Everything in the audit file is also in the hot file. The split is
        about what survives rotation, not about routing lines away."""
        self.log.warning("REJECTED malformed candle BTC-USD 1H open_ts=1")
        self.log.info("MANUAL ARM BTC-USD 1H LONG")
        self.log.debug("swings     swings-v0.4-draft    BTC-USD  1H  in=1 new=0 1ms")
        hot, audit = self.hot(), self.audit()
        for line in audit.splitlines():
            self.assertIn(line, hot)


class AuditPrefixCoverageCase(unittest.TestCase):
    """The failure mode this guards is additive and silent.

    Someone adds a write endpoint, logs it with a new verb, and nothing breaks
    — the line lands in the hot stream and is discarded whenever rotation
    lands. Nothing in the app can notice. So the prefix list is checked against
    the call sites rather than trusted.
    """

    SERVER = Path(__file__).resolve().parent.parent / "server.py"
    # Operator-action logging lives in the endpoints; these are the INFO lines
    # in server.py that are NOT operator actions and are heartbeat/among-facts.
    NOT_EVIDENCE = ("announce filter", "live loop start", "cycle done")

    def test_every_info_line_in_server_py_is_classified(self):
        src = self.SERVER.read_text(encoding="utf-8", errors="replace")
        # Grab the first string literal that follows each get_logger().info(
        # call, then the literal prefix before any f-string placeholder.
        uncovered = []
        for m in re.finditer(r"get_logger\(\)\.info\(", src):
            tail = src[m.end():m.end() + 400]
            lit = re.search(r'f?"([^"]*)"', tail)
            if not lit:
                continue
            head = lit.group(1).split("{")[0].strip()
            if not head or len(head) < 3:
                continue
            if head.startswith(runlog.AUDIT_PREFIXES):
                continue
            if head.startswith(self.NOT_EVIDENCE):
                continue
            uncovered.append(head)
        self.assertEqual(
            [], uncovered,
            "server.py logs these INFO lines and engine/runlog.py does not "
            "classify them. If it is an operator write action add its prefix "
            "to runlog.AUDIT_PREFIXES; if it is heartbeat add it to "
            "NOT_EVIDENCE here. Leaving it unclassified means it is discarded "
            "on rotation: " + repr(uncovered))


if __name__ == "__main__":
    unittest.main()
