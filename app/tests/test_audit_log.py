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

    def test_a_failed_audit_handler_leaves_no_handler_attached(self):
        """Attach-as-you-build leaked one engine.log handler per get_logger
        retry when the audit file was unopenable — read-only being a natural
        state for a file labelled evidence. Every retry then multiplied
        writes and every RunRecorder exit raised after its commit."""
        import unittest.mock as mock
        lg = logging.getLogger("snipersight")
        before = len(lg.handlers)
        real_handler = logging.FileHandler

        def hot_ok_audit_fails(path, *a, **kw):
            # The leak scenario, precisely: the HOT handler constructs fine,
            # the AUDIT handler fails. Failing the first construction too
            # would pass under the old attach-as-you-build code and pin
            # nothing (audit 2026-08-08, finding 3).
            if Path(path).name == "engine-audit.log":
                raise OSError("audit file is read-only")
            return real_handler(path, *a, **kw)

        with mock.patch.object(runlog.logging, "FileHandler",
                               side_effect=hot_ok_audit_fails):
            for _ in range(3):
                runlog._logger = None
                with self.assertRaises(OSError):
                    runlog.get_logger()
        self.assertEqual(before, len(lg.handlers),
                         "a failed audit handler must leave NOTHING attached "
                         "— one leaked hot handler per retry multiplies "
                         "every line and 500s every write endpoint")
        runlog._logger = None          # let the next test rebuild cleanly

    def test_an_unrenderable_message_is_kept_not_raised(self):
        """Handler.handle runs filters outside emit()'s try/except, so a
        filter that raises turns a bad log line in a write endpoint into a
        500. It must neither raise nor lose the record."""
        class _Hostile:
            def __str__(self):
                raise RuntimeError("unrenderable")
        # propagate=False for this call only: pytest's own capture handler
        # sits on the root logger and re-raises formatting errors by design,
        # which would test the harness rather than our filter.
        self.log.propagate = False
        try:
            self.log.info(_Hostile())          # must not raise
        except RuntimeError:
            self.fail("a bad log message escaped into the caller")
        finally:
            self.log.propagate = True

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

    APP = Path(__file__).resolve().parent.parent
    # Files whose INFO lines can be write actions, and the lines in each that
    # are deliberately NOT evidence (heartbeat, already-in-facts telemetry).
    # An entry here is a decision, not a default — the test forces every new
    # INFO line into one list or the other.
    SCANNED = {
        "server.py": ("announce filter", "live loop start", "cycle done"),
        "live.py": ("live loop start", "cycle done", "cycle", "sleeping",
                    "awake", "WAL checkpoint", "announce filter",
                    "already announced", "UNIVERSE onboarded", "SETUP FIRED",
                    "import ", "backfill", "history probe", "universe refresh",
                    "drift ", "scan "),
        "prune.py": (),
    }
    # The audit that motivated this widening found the original test caught
    # one of three real spellings. All three are matched now:
    #   get_logger().info(f"...")     get_logger().info(f'...')
    #   log = get_logger() ... log.info("...")
    _CALL = re.compile(r"(?:get_logger\(\)|log(?:ger)?)\s*\.\s*info\(")
    _LIT = re.compile(r'''f?("([^"]*)"|'([^']*)')''')

    def test_every_info_line_that_could_be_evidence_is_classified(self):
        uncovered = []
        for name, not_evidence in self.SCANNED.items():
            src = (self.APP / name).read_text(encoding="utf-8", errors="replace")
            for m in self._CALL.finditer(src):
                lit = self._LIT.search(src[m.end():m.end() + 400])
                if not lit:
                    continue
                head = (lit.group(2) or lit.group(3) or "").split("{")[0].strip()
                if not head or len(head) < 3:
                    continue
                if head.startswith(runlog.AUDIT_PREFIXES):
                    continue
                if head.lower().startswith(tuple(p.lower() for p in not_evidence)):
                    continue
                uncovered.append(f"{name}: {head!r}")
        self.assertEqual(
            [], uncovered,
            "these INFO lines are neither an evidence prefix nor declared "
            "heartbeat. If one is a write action add its prefix to "
            "runlog.AUDIT_PREFIXES; if it is heartbeat add it to SCANNED "
            "here. Unclassified means silently discarded on rotation: "
            + repr(uncovered))

    def test_the_autotrader_routing_line_is_evidence(self):
        """The system sending real orders to a venue is a bigger write action
        than any manual arm, and for a while its log line was the only trace
        at any level — INFO, unmatched, gone on first rotation."""
        self.assertIn("AUTOTRADER", runlog.AUDIT_PREFIXES)
        live = (self.APP / "live.py").read_text(encoding="utf-8")
        self.assertIn('f"AUTOTRADER {', live,
                      "live.py stopped logging routing under the prefix")


if __name__ == "__main__":
    unittest.main()
