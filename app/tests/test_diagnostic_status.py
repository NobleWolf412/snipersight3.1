"""Temporal diagnostics use scratch state and never mutate the trading book."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime

from engine import diagnostic_status as ds, store, copilot


class DiagnosticStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.con = store.connect(self.directory / "test.db")
        self.now = int(datetime(2026, 9, 6, 12).timestamp())

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def heartbeat(self, ts=None):
        (self.directory / "heartbeat.json").write_text(json.dumps(
            {"ts": self.now if ts is None else ts, "pid": 123, "phase": "import", "cycles": 5}))

    def audit(self, age=0, report=None, allowed=1):
        report = report if report is not None else {"blockers": [], "notes": [{"code": "KNOWN_VENUE_GAPS"}]}
        self.con.execute("INSERT INTO quality_runs(observed_at,status,evaluation_allowed,summary,report) VALUES(?,?,?,?,?)",
                         (self.now - age, "PASS" if allowed else "HALT", allowed, "", json.dumps(report)))
        self.con.commit()

    def snapshot(self):
        self.con.execute("PRAGMA query_only=ON")
        before = self.con.total_changes
        result = ds.snapshot(self.con, now=self.now, data_dir=self.directory)
        self.assertEqual(before, self.con.total_changes)
        return result

    def test_empty_state_is_not_all_clear(self):
        self.assertEqual(self.snapshot()["state"], "unverified")

    def test_fresh_progress_and_accepted_notes_do_not_require_repair(self):
        self.heartbeat()
        self.audit()
        result = self.snapshot()
        self.assertEqual(result["state"], "reporting")
        self.assertEqual(result["audit"]["accepted_notes"][0]["code"], "KNOWN_VENUE_GAPS")

    def test_stale_and_future_heartbeat_do_not_prove_progress(self):
        self.audit()
        for ts in (self.now - 91, self.now + 1, "bad"):
            self.heartbeat(ts)
            self.assertEqual(self.snapshot()["scanner"]["state"], "unverified")

    def test_stale_audit_is_not_current_health(self):
        self.heartbeat()
        self.audit(age=ds.AUDIT_FRESH_S + 1)
        self.assertEqual(self.snapshot()["state"], "unverified")

    def test_unresolved_fault_never_expires_by_age(self):
        self.heartbeat()
        self.audit()
        self.con.execute("INSERT INTO engine_faults VALUES(?,?,?,?,?,?,?)",
                         ("X", "5m", "swings", "bad", self.now - 99999, self.now - 999, 4))
        self.con.commit()
        result = self.snapshot()
        self.assertEqual(result["state"], "needs_attention")
        self.assertEqual(len(result["current"]["engine_faults"]), 1)

    def test_restart_recovery_requires_later_fresh_progress(self):
        self.heartbeat()
        (self.directory / "watchdog.log").write_text(
            "2026-09-02 16:51:06 audit: worst=HALT — restart live (HALT, codes=['SEQUENCE_GAPS'])\n"
            "2026-09-02 16:51:16 live-scanner exited rc=1 — audit HALT\n", encoding="utf-8")
        result = self.snapshot()
        self.assertEqual([e["state"] for e in result["history"]], ["recovered", "historical"])
        self.assertIn("underlying cause not proven repaired", result["history"][0]["meaning"])
        self.heartbeat(self.now - 91)
        self.assertTrue(all(e["state"] == "historical" for e in self.snapshot()["history"]))

    def test_unknown_or_future_log_time_cannot_be_recovered(self):
        self.heartbeat()
        (self.directory / "watchdog.log").write_text(
            "no date live-scanner exited rc=1\n2027-09-02 16:51:16 live-scanner exited rc=1\n")
        self.assertTrue(all(e["state"] == "historical" for e in self.snapshot()["history"]))

    def test_private_audit_does_not_replace_scanner_verdict(self):
        self.heartbeat()
        self.audit()
        (self.directory / "watchdog.log").write_text("2026-09-06 11:59:00 audit: worst=QUARANTINE counts={'HALT': 0}\n")
        result = self.snapshot()
        self.assertEqual(result["audit"]["status"], "PASS")
        self.assertIn("QUARANTINE", result["supervisor"]["detail"])

    def test_bounded_tail_drops_partial_lines(self):
        path = self.directory / "huge.log"
        path.write_bytes(b"x" * 1000 + b"\nlast line\n")
        result = ds.tail(path, limit=25)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["lines"], ["last line"])
        self.assertFalse(ds.tail(self.directory / "absent")["available"])

    def test_pack_warns_against_stale_diagnoses_and_reads_disk_not_runtime_policy(self):
        self.audit(report={"blockers": [{"code": "SEQUENCE_GAPS"}]}, allowed=0)
        self.con.execute("PRAGMA query_only=ON")
        with patch.object(ds, "DATA_DIR", self.directory):
            pack = copilot.build_diag_pack(self.con)
        self.assertIn("SEQUENCE_GAPS", pack)
        self.assertIn("Never invent a HALT code", pack)
        self.assertIn("A new answer is not a new event", pack)
        self.assertIn("generated_at_utc", pack)
        self.assertIn("No tools are available", pack)

    def test_policy_reader_never_executes_code(self):
        path = self.directory / "watchdog.py"
        path.write_text('raise RuntimeError("do not import")\nUNHEALABLE_HALT_CODES = frozenset({"SEQUENCE_GAPS"})\nRESTART_GRACE_SEC = 900\n')
        result = ds._policy(path)
        self.assertEqual(result["constants"]["UNHEALABLE_HALT_CODES"], ["SEQUENCE_GAPS"])
        self.assertIn("loaded supervisor version unknown", result["source"])


if __name__ == "__main__":
    unittest.main()
