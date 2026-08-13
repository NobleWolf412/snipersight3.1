"""One verdict, and it is the one the engine acted on.

`cached_audit` holds its report in module state, so the api-server and the
scanner each kept their own — two processes, two caches, and no reason for
them to agree. `risk.py` runs inside the scanner and gates trading on THAT
process's verdict. The UI read the api-server's, which audited at whatever
moment an HTTP request happened to arrive.

Measured 4 Aug 2026:

  · server  audited 11:44:58 → BLOCKED. It caught 23 symbols whose 15m bar
    closed at 11:45 — legitimately still open, flagged DEVELOPING_CANDLES,
    which sits at the HALT rung.
  · scanner audited 11:45:06 → DEGRADED, evaluation_allowed, trading fine.

Because `cached_audit` serves its last report until a background refresh
replaces it, the server was still publishing that BLOCKED snapshot four
minutes later, under a chip whose hover read "the engine is refusing to size
new entries". It was not, and no operator action could have cleared it.

A read-only surface must never publish a verdict the engine never acted on.
"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from engine import apexbridge, quality, store


class OneVerdictCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _record(self, *, status, allowed, at, report=None):
        """Write a quality_runs row the way audit(persist=True) does."""
        body = report if report is not None else {
            "status": status, "evaluation_allowed": allowed,
            "worst_rung": "HALT" if status == "BLOCKED" else "SERVE_FLAG",
            "rung_counts": {}, "stages": [], "blockers": [], "warnings": []}
        self.con.execute(
            "INSERT INTO quality_runs"
            "(observed_at,status,evaluation_allowed,summary,report) "
            "VALUES (?,?,?,?,?)",
            (at, status, int(allowed), json.dumps({}), json.dumps(body)))
        self.con.commit()

    # ------------------------------------------------------------- the store
    def test_the_full_report_is_persisted_not_just_its_counts(self):
        """`summary` held four numbers, so any surface wanting the issue list
        had to re-run the audit — which is the whole cause of the split."""
        cols = {r[1] for r in self.con.execute(
            "PRAGMA table_info(quality_runs)").fetchall()}
        self.assertIn("report", cols,
                      "quality_runs cannot carry the full verdict, so surfaces "
                      "must re-derive it and can disagree")

    def test_migration_is_recorded(self):
        applied = {r[0] for r in self.con.execute(
            "SELECT version FROM schema_migrations").fetchall()}
        self.assertIn(7, applied)

    # --------------------------------------------------------- last_persisted
    def test_returns_none_before_the_scanner_has_recorded_one(self):
        self.assertIsNone(quality.last_persisted(self.con),
                          "an empty table must read as pending, never as a "
                          "confident verdict")

    def test_serves_the_recorded_verdict_verbatim(self):
        self._record(status="DEGRADED", allowed=True, at=int(time.time()) - 30)
        rep = quality.last_persisted(self.con)
        self.assertEqual(rep["status"], "DEGRADED")
        self.assertTrue(rep["evaluation_allowed"])
        self.assertEqual(rep["source"], "scanner")

    def test_reports_its_own_age(self):
        """A scanner that has stopped must be visible as staleness, not hidden
        behind a fresh-looking audit nobody used."""
        self._record(status="DEGRADED", allowed=True, at=int(time.time()) - 600)
        rep = quality.last_persisted(self.con)
        self.assertGreaterEqual(rep["age_s"], 590)

    def test_the_newest_recorded_verdict_wins(self):
        now = int(time.time())
        self._record(status="BLOCKED", allowed=False, at=now - 300)
        self._record(status="DEGRADED", allowed=True, at=now - 10)
        self.assertEqual(quality.last_persisted(self.con)["status"], "DEGRADED")

    def test_rows_without_a_report_are_skipped(self):
        """Rows written before migration 7 are valid summaries but cannot
        answer for the whole verdict."""
        self.con.execute(
            "INSERT INTO quality_runs"
            "(observed_at,status,evaluation_allowed,summary) VALUES (?,?,?,?)",
            (int(time.time()), "BLOCKED", 0, json.dumps({})))
        self.con.commit()
        self.assertIsNone(quality.last_persisted(self.con))

    def test_unreadable_report_json_is_not_a_verdict(self):
        self.con.execute(
            "INSERT INTO quality_runs"
            "(observed_at,status,evaluation_allowed,summary,report) "
            "VALUES (?,?,?,?,?)",
            (int(time.time()), "BLOCKED", 0, "{}", "not json"))
        self.con.commit()
        self.assertIsNone(quality.last_persisted(self.con),
                          "a corrupt row must read as pending, never as BLOCKED")

    # ------------------------------------------------------------ the endpoint
    def test_the_endpoint_serves_the_scanner_not_its_own_audit(self):
        import server
        self._record(status="DEGRADED", allowed=True, at=int(time.time()) - 20)

        def _must_not_run(*a, **k):
            raise AssertionError(
                "the endpoint audited in-process — that is what produced a "
                "BLOCKED verdict the trading engine never saw")

        with mock.patch.object(server.store, "connect", return_value=self.con), \
             mock.patch.object(server.quality, "cached_audit", _must_not_run), \
             mock.patch.object(server.quality, "audit", _must_not_run):
            r = server.pipeline_health()
        self.assertEqual(r["status"], "DEGRADED")
        self.assertEqual(r["source"], "scanner")

    def test_the_endpoint_falls_back_only_when_nothing_is_recorded(self):
        """A fresh store still shows something, and says it is provisional."""
        import server
        local = {"status": "PASS", "evaluation_allowed": True,
                 "stages": [], "blockers": [], "warnings": []}
        with mock.patch.object(server.store, "connect", return_value=self.con), \
             mock.patch.object(server.quality, "cached_audit",
                               return_value=local):
            r = server.pipeline_health()
        self.assertEqual(r["source"], "local",
                         "the fallback must name itself, or a provisional "
                         "verdict is indistinguishable from the recorded one")

    def test_pending_when_there_is_no_verdict_at_all(self):
        import server
        with mock.patch.object(server.store, "connect", return_value=self.con), \
             mock.patch.object(server.quality, "cached_audit", return_value=None):
            r = server.pipeline_health()
        self.assertEqual(r["status"], "PENDING")
        self.assertTrue(r["pending"])
        self.assertTrue(r["evaluation_allowed"],
                        "an audit that has not run must not read as a block")

    def test_a_recorded_block_is_still_published(self):
        """The fix must not swallow a real BLOCKED — only ones the engine
        never acted on."""
        import server
        self._record(status="BLOCKED", allowed=False, at=int(time.time()) - 5)
        with mock.patch.object(server.store, "connect", return_value=self.con):
            r = server.pipeline_health()
        self.assertEqual(r["status"], "BLOCKED")
        self.assertFalse(r["evaluation_allowed"])

    def test_bridge_refresh_cannot_persist_a_competing_verdict(self):
        self._record(status="DEGRADED", allowed=True,
                     at=int(time.time()) - 20)
        before = self.con.execute(
            "SELECT COUNT(*) FROM quality_runs").fetchone()[0]
        with mock.patch.object(
                quality, "audit",
                side_effect=AssertionError("observer recomputed health")):
            result = apexbridge.action(self.con, "audit")
        after = self.con.execute(
            "SELECT COUNT(*) FROM quality_runs").fetchone()[0]
        self.assertTrue(result["ok"])
        self.assertIn("scanner audit", result["detail"])
        self.assertEqual(after, before)

    def test_forced_cache_refresh_is_not_durable_authority(self):
        before = self.con.execute(
            "SELECT COUNT(*) FROM quality_runs").fetchone()[0]
        self.assertIsNotNone(quality.cached_audit(self.con, force=True))
        after = self.con.execute(
            "SELECT COUNT(*) FROM quality_runs").fetchone()[0]
        self.assertEqual(after, before)

    def test_offline_backfill_cannot_publish_a_scanner_verdict(self):
        backfill = (Path(__file__).resolve().parents[1] / "backfill.py").read_text(
            encoding="utf-8")
        self.assertNotIn("quality.audit(con, now=now, persist=True)", backfill)


if __name__ == "__main__":
    unittest.main()
