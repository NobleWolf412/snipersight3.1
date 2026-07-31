"""Watchdog dispatches by Kill-Switch rung, not by hardcoded code lists —
so every new finding in quality.py auto-inherits its response with no
watchdog edit. See war-room/ideas-2026-07-26 items #2, #4, #9, #12."""
import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP = Path(__file__).resolve().parent.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import watchdog  # noqa: E402


class _FakeChild:
    def __init__(self, alive=True):
        self._alive = alive
        self.proc = MagicMock()

    def alive(self):
        return self._alive


class TestWatchdogRungDispatch(unittest.TestCase):
    def _run(self, report, prior=None):
        prior = prior or {}
        state = {"counts": prior, "at": 0.0}
        child = _FakeChild(alive=True)
        fake_con = MagicMock()
        fake_store = MagicMock(connect=MagicMock(return_value=fake_con))
        fake_quality = MagicMock(audit=MagicMock(return_value=report))
        with patch.dict("sys.modules",
                        {"engine": MagicMock(store=fake_store, quality=fake_quality),
                         "engine.store": fake_store,
                         "engine.quality": fake_quality}):
            with patch.object(watchdog, "toast") as toast, \
                 patch.object(watchdog, "log"):
                new_state = watchdog.audit_tick(state, child)
        return new_state, child, toast

    def test_halt_finding_restarts_live(self):
        report = {"worst_rung": "HALT",
                  "rung_counts": {"HALT": 1, "SERVE_FLAG": 0, "QUARANTINE": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [{"code": "OHLC_INVARIANT_FAILURE", "rung": "HALT"}],
                  "warnings": []}
        _, child, toast = self._run(report)
        child.proc.terminate.assert_called_once()
        toast.assert_called_once()

    def test_a_single_quarantine_climb_does_not_restart(self):
        """THE 184-RESTART BUG. One tick of climb used to be a kill.

        A scan cycle measures ~296s and the audit runs every 60s, so the
        scanner was terminated ~78s in and never once finished a pass. The
        climb was STALE_SERIES — candles behind — and the response was to kill
        the process whose job is catching them up."""
        report = {"worst_rung": "QUARANTINE",
                  "rung_counts": {"HALT": 0, "QUARANTINE": 3, "SERVE_FLAG": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [],
                  "warnings": [{"code": "STALE_SERIES", "rung": "QUARANTINE"}]}
        _, child, toast = self._run(report, prior={"QUARANTINE": 1})
        child.proc.terminate.assert_not_called()
        toast.assert_not_called()

    def test_quarantine_stable_does_not_restart(self):
        report = {"worst_rung": "QUARANTINE",
                  "rung_counts": {"HALT": 0, "QUARANTINE": 2, "SERVE_FLAG": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [], "warnings": []}
        _, child, toast = self._run(report, prior={"QUARANTINE": 2})
        child.proc.terminate.assert_not_called()
        toast.assert_not_called()

    def test_serve_flag_only_does_not_restart(self):
        report = {"worst_rung": "SERVE_FLAG",
                  "rung_counts": {"HALT": 0, "QUARANTINE": 0, "SERVE_FLAG": 4,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [], "warnings": []}
        _, child, toast = self._run(report)
        child.proc.terminate.assert_not_called()
        toast.assert_not_called()

    def test_clean_report_does_not_restart(self):
        report = {"worst_rung": "SERVE",
                  "rung_counts": {r: 0 for r in ("HALT", "QUARANTINE",
                                                 "SERVE_FLAG", "AUTO_DISABLE",
                                                 "SERVE")},
                  "blockers": [], "warnings": []}
        _, child, toast = self._run(report)
        child.proc.terminate.assert_not_called()
        toast.assert_not_called()

    def test_state_tracks_counts_for_climb_detection(self):
        report = {"worst_rung": "QUARANTINE",
                  "rung_counts": {"HALT": 0, "QUARANTINE": 5, "SERVE_FLAG": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [], "warnings": []}
        new_state, _, _ = self._run(report, prior={"QUARANTINE": 5})
        self.assertEqual(new_state["counts"], report["rung_counts"])


class TestQuarantinePersistence(unittest.TestCase):
    """A climb must PERSIST before it counts as a fault.

    The whole point is the difference between a reading that is moving while an
    import catches up and one that is genuinely stuck. The observed sequence on
    2026-07-30 was 19 -> 19 -> 4 -> 0: it recovered unaided, and every one of
    those ticks was a kill under the old rule."""

    def _sequence(self, quarantines, age=10_000.0):
        """Feed consecutive audits and report when a terminate happened."""
        child = _FakeChild(alive=True)
        child.started_at = 0.0
        state = {"counts": {}, "at": 0.0}
        fake_con = MagicMock()
        fake_store = MagicMock(connect=MagicMock(return_value=fake_con))
        kills = []
        for q in quarantines:
            report = {"worst_rung": "QUARANTINE" if q else "SERVE",
                      "rung_counts": {"HALT": 0, "QUARANTINE": q, "SERVE_FLAG": 0,
                                       "AUTO_DISABLE": 0, "SERVE": 0},
                      "blockers": [],
                      "warnings": [{"code": "STALE_SERIES", "rung": "QUARANTINE"}] * q}
            fake_quality = MagicMock(audit=MagicMock(return_value=report))
            with patch.dict("sys.modules",
                            {"engine": MagicMock(store=fake_store, quality=fake_quality),
                             "engine.store": fake_store,
                             "engine.quality": fake_quality}):
                with patch.object(watchdog, "toast"), patch.object(watchdog, "log"), \
                     patch.object(watchdog.time, "monotonic", return_value=age):
                    state = watchdog.audit_tick(state, child)
            kills.append(child.proc.terminate.call_count)
        return kills

    def test_the_observed_recovering_sequence_never_restarts(self):
        # the exact live reading that produced the restart loop
        self.assertEqual(self._sequence([19, 19, 4, 0])[-1], 0)

    def test_a_sustained_climb_still_restarts(self):
        # stuck high and not recovering IS a fault; the guard must not mute it
        kills = self._sequence([5, 9, 14])
        self.assertEqual(kills[0], 0, "restarted on the first tick")
        self.assertEqual(kills[1], 0, "restarted before the streak was met")
        self.assertEqual(kills[-1], 1, "a genuine sustained climb was never acted on")

    def test_stuck_at_a_high_level_restarts(self):
        # a count that climbs then holds is not recovering
        self.assertEqual(self._sequence([7, 7, 7])[-1], 1)

    def test_recovery_rearms_the_streak(self):
        # dropping back must clear the count, or an old climb fires later
        self.assertEqual(self._sequence([9, 9, 1, 9])[-1], 0)

    def test_a_young_scanner_is_not_killed_mid_cycle(self):
        """A cycle needs ~296s. Terminating before that guarantees it never
        completes, which is precisely how the loop sustained itself."""
        kills = self._sequence([5, 9, 14], age=30.0)
        self.assertEqual(kills[-1], 0,
                         "a scanner too young to have finished a pass was killed")


class TestAuditWarmup(unittest.TestCase):
    """Warmup seeds prior counts so a first-tick QUARANTINE reading isn't
    misread as climb-from-0 (Auditor FIND-2)."""

    def _run(self, report, warmup):
        child = _FakeChild(alive=True)
        fake_con = MagicMock()
        fake_store = MagicMock(connect=MagicMock(return_value=fake_con))
        fake_quality = MagicMock(audit=MagicMock(return_value=report))
        with patch.dict("sys.modules",
                        {"engine": MagicMock(store=fake_store, quality=fake_quality),
                         "engine.store": fake_store,
                         "engine.quality": fake_quality}):
            with patch.object(watchdog, "toast") as toast, \
                 patch.object(watchdog, "log"):
                new_state = watchdog.audit_tick(
                    {"counts": {}, "at": 0.0}, child, warmup=warmup)
        return new_state, child, toast

    def test_warmup_suppresses_quarantine_climb_restart(self):
        report = {"worst_rung": "QUARANTINE",
                  "rung_counts": {"HALT": 0, "QUARANTINE": 3, "SERVE_FLAG": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [], "warnings": []}
        new_state, child, toast = self._run(report, warmup=True)
        child.proc.terminate.assert_not_called()
        toast.assert_not_called()
        self.assertEqual(new_state["counts"]["QUARANTINE"], 3)

    def test_warmup_still_dispatches_halt(self):
        # A broken pipeline at boot is still broken — HALT ignores warmup.
        report = {"worst_rung": "HALT",
                  "rung_counts": {"HALT": 2, "QUARANTINE": 0, "SERVE_FLAG": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [{"code": "NO_CANDLES", "rung": "HALT"}],
                  "warnings": []}
        _, child, toast = self._run(report, warmup=True)
        child.proc.terminate.assert_called_once()
        toast.assert_called_once()


class TestAuditCadenceOnSkip(unittest.TestCase):
    """Skip returns (import or db) must still stamp `at` so cadence stays 60s
    instead of hammering audit every 10s (Auditor FIND-3)."""

    def test_import_skip_stamps_at(self):
        child = _FakeChild(alive=True)
        # engine module absent → ImportError inside audit_tick
        with patch.dict("sys.modules", {"engine": None}):
            with patch.object(watchdog, "log"):
                new_state = watchdog.audit_tick(
                    {"counts": {}, "at": 0.0}, child)
        self.assertGreater(new_state["at"], 0.0)

    def test_db_skip_stamps_at(self):
        child = _FakeChild(alive=True)
        fake_store = MagicMock(
            connect=MagicMock(side_effect=RuntimeError("db not ready")))
        fake_quality = MagicMock()
        with patch.dict("sys.modules",
                        {"engine": MagicMock(store=fake_store, quality=fake_quality),
                         "engine.store": fake_store,
                         "engine.quality": fake_quality}):
            with patch.object(watchdog, "log"):
                new_state = watchdog.audit_tick(
                    {"counts": {}, "at": 0.0}, child)
        self.assertGreater(new_state["at"], 0.0)


class TestChildErrorCapture(unittest.TestCase):
    """An exit code alone cannot tell a crash from a deliberate terminate.

    Children used to inherit this process's stderr, which under start.bat is a
    console window — so 184 `rc=1` events were recorded with their tracebacks
    printed somewhere nothing kept. That is most of why they went a day without
    a diagnosis. The child's stderr is now captured and its tail is logged with
    the exit."""

    def _child(self, code):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        c = watchdog.Child("probe", [sys.executable, "-c", code])
        c._err_path = Path(tmp.name) / "probe.err.log"
        return c

    def test_a_traceback_is_captured_and_surfaced(self):
        c = self._child("raise RuntimeError('the actual reason')")
        with patch.object(watchdog, "log"):
            c.start()
        c.proc.wait(timeout=30)
        if c._err:
            c._err.close()
            c._err = None
        self.assertNotEqual(c.proc.returncode, 0, "the probe was meant to fail")
        why = c._last_error()
        self.assertIn("the actual reason", why,
                      "the child's traceback is still being thrown away")
        self.assertIn("RuntimeError", why)

    def test_a_clean_child_surfaces_nothing(self):
        c = self._child("pass")
        with patch.object(watchdog, "log"):
            c.start()
        c.proc.wait(timeout=30)
        if c._err:
            c._err.close()
            c._err = None
        self.assertEqual(c._last_error(), "",
                         "a silent clean exit invented an explanation")

    def test_capture_failure_never_blocks_a_start(self):
        """Logging is housekeeping; it must not stop the scanner coming back."""
        c = self._child("pass")
        c._err_path = Path("Z:/definitely/not/writable/probe.err.log")
        with patch.object(watchdog, "log"):
            c.start()                      # must not raise
        c.proc.wait(timeout=30)
        self.assertEqual(c.proc.returncode, 0)


class TestOrphanClearing(unittest.TestCase):
    """watchdog.log records 8 starts and 1 clean stop. Seven supervisors died
    without reaching the finally that terminates their children, and Popen
    children outlive their parent on Windows — so each left a live.py running
    and the next supervisor started a SECOND one beside it. Two scanners on one
    SQLite file is the `database is locked` storm the log shows: 154 in an
    hour."""

    def _wmic(self, stdout):
        return patch.object(watchdog.subprocess, "run",
                            return_value=MagicMock(stdout=stdout, returncode=0))

    def test_a_leftover_scanner_is_found(self):
        rows = ("Node,CommandLine,ProcessId\n"
                "PC,python.exe -X utf8 live.py,4321\n")
        with self._wmic(rows), patch.object(watchdog.sys, "platform", "win32"):
            found = watchdog._orphans()
        self.assertIn((4321, "live.py"), found)

    def test_this_process_is_never_its_own_orphan(self):
        import os
        rows = f"Node,CommandLine,ProcessId\nPC,python.exe live.py,{os.getpid()}\n"
        with self._wmic(rows), patch.object(watchdog.sys, "platform", "win32"):
            self.assertEqual(watchdog._orphans(), [])

    def test_a_supervised_child_is_never_cleared(self):
        """The takeover path clears orphans while this supervisor already has a
        scanner running. Without an exclusion it would kill its own child —
        the exact failure this function exists to prevent."""
        rows = ("Node,CommandLine,ProcessId\n"
                "PC,python.exe -X utf8 live.py,5555\n")
        with self._wmic(rows), patch.object(watchdog.sys, "platform", "win32"):
            self.assertEqual(watchdog._orphans(exclude={5555}), [])
            self.assertEqual(watchdog._orphans(), [(5555, "live.py")])

    def test_unrelated_python_is_left_alone(self):
        rows = ("Node,CommandLine,ProcessId\n"
                "PC,python.exe some_other_tool.py,999\n")
        with self._wmic(rows), patch.object(watchdog.sys, "platform", "win32"):
            self.assertEqual(watchdog._orphans(), [])

    def test_clearing_survives_a_failing_taskkill(self):
        with patch.object(watchdog, "_orphans", return_value=[(1234, "live.py")]), \
             patch.object(watchdog.subprocess, "run", side_effect=OSError("nope")), \
             patch.object(watchdog, "log") as log:
            watchdog.clear_orphans()          # must not raise
        self.assertTrue(any("could not clear" in str(c) for c in log.call_args_list))

    def test_startup_clears_before_spawning(self):
        """Order matters: clearing after spawning would kill the new scanner."""
        src = (Path(watchdog.__file__)).read_text(encoding="utf-8")
        body = src[src.index("def main("):]
        self.assertIn("clear_orphans()", body, "startup never clears orphans")
        self.assertLess(body.index("clear_orphans()"), body.index("live.tick()"),
                        "orphans are cleared after the supervisor starts working")


class TestTakeoverHysteresis(unittest.TestCase):
    """`server_up()` probed with a 3s timeout an endpoint measured at 6.9s under
    a bloated WAL. One slow answer read as "the external server vanished", so
    the watchdog started a SECOND uvicorn on a port the first still held — which
    cannot bind, exits, and restart-loops."""

    def test_probe_timeout_exceeds_the_measured_endpoint(self):
        self.assertGreaterEqual(
            watchdog.SERVER_PROBE_TIMEOUT, 10,
            "a liveness probe faster than the thing it probes reports false death")

    def test_takeover_needs_repeated_misses(self):
        self.assertGreaterEqual(watchdog.SERVER_MISSES_BEFORE_TAKEOVER, 2)
        src = (Path(watchdog.__file__)).read_text(encoding="utf-8")
        body = src[src.index("def main("):]
        self.assertIn("SERVER_MISSES_BEFORE_TAKEOVER", body,
                      "takeover still fires on a single missed probe")

    def test_grace_covers_the_slowest_measured_cycle(self):
        # 347.1s observed 2026-07-30; the constant was first sized from 295.8s
        self.assertGreater(watchdog.RESTART_GRACE_SEC, 347,
                           "the grace window is under a cycle time already seen")


if __name__ == "__main__":
    unittest.main()
