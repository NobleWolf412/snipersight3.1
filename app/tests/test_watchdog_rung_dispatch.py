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

    def test_quarantine_climb_restarts_live(self):
        report = {"worst_rung": "QUARANTINE",
                  "rung_counts": {"HALT": 0, "QUARANTINE": 3, "SERVE_FLAG": 0,
                                   "AUTO_DISABLE": 0, "SERVE": 0},
                  "blockers": [],
                  "warnings": [{"code": "STALE_SERIES", "rung": "QUARANTINE"}]}
        _, child, toast = self._run(report, prior={"QUARANTINE": 1})
        child.proc.terminate.assert_called_once()
        toast.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
