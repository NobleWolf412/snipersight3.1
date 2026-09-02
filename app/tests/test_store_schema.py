"""A connected store is a COMPLETE store — every table the readers query.

`engine_runs` was the exception, and it was invisible on a warm machine.
`runlog.RunRecorder.__enter__` created it on the way to writing the first row,
so the table appeared the moment any engine ran and never disappeared again.
Every developer store, and the operator's, had run an engine within seconds of
existing. Nothing was left to notice the window.

`/api/overview` queries the table unconditionally — it is the endpoint every
cockpit surface polls at 30s — so on a store that had never completed an engine
run the answer was `sqlite3.OperationalError: no such table: engine_runs`,
surfacing as a 500. That is the state of a fresh clone: the scanner and the API
server come up together under the watchdog, and the server serves before the
scanner's first cycle finishes.

It reached CI as one red test (`test_phone_front_door`
`test_bridge_token_opens_an_allowlisted_read`, which builds a TestClient over a
cold store) and read as an unrelated bridge-auth failure, because the traceback
names the endpoint and not the missing table.

The fix moved the DDL call into `store.connect`. `runlog` still OWNS the
definition — `connect` asks it for `RUNS_SCHEMA` rather than restating the
columns — so the two cannot drift into different shapes of the same table.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine import runlog, store


class AFreshStoreHasEveryTableItsReadersQuery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "cold.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_engine_runs_exists_before_any_engine_has_run(self):
        """The bug, stated as the property that must never hold again."""
        self.assertEqual(
            self.con.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='table' AND name='engine_runs'").fetchone()[0], 1,
            "a connected store is missing engine_runs — /api/overview 500s "
            "until something happens to run an engine")

    def test_the_last_run_per_engine_query_answers_empty_not_raises(self):
        """The shape `/api/overview` actually asks. An empty store must answer
        'no runs yet', which renders; raising is what became the 500."""
        rows = self.con.execute(
            "SELECT engine, run_at, duration_ms FROM engine_runs "
            "ORDER BY run_at DESC").fetchall()
        self.assertEqual(rows, [])

    def test_the_overview_index_is_there_too(self):
        """Without it, 'last run per engine' is a full scan of a table that
        reached 3,038,265 rows / ~300 MB — measured at 2,432 ms of the
        endpoint's 2,900 ms. A table created without its index would be
        correct and unusably slow, which is harder to notice than a 500."""
        self.assertEqual(
            self.con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='index' "
                "AND name='ix_engine_runs_engine_recent'").fetchone()[0], 1)

    def test_runlog_still_owns_the_definition(self):
        """`connect` must ASK runlog for the DDL, never restate it. Two
        spellings of one table is how a column gets added to one and not the
        other, and RunRecorder's own ALTER migration then runs against a shape
        it did not write."""
        source = Path(store.__file__).read_text(encoding="utf-8")
        self.assertIn("runlog.RUNS_SCHEMA", source)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS engine_runs", source)

    def test_a_recorder_on_a_connected_store_still_works(self):
        """RunRecorder's CREATE is idempotent, so it must survive the table
        already existing — it still runs, and still adds any column a store
        written by an older build is missing."""
        with runlog.RunRecorder(self.con, "t", "t-v0.1", "PORTFOLIO", "ALL") as rec:
            rec.n_new_facts = 1
        self.con.commit()
        self.assertEqual(
            self.con.execute("SELECT count(*) FROM engine_runs").fetchone()[0], 1)

    def test_connect_is_idempotent(self):
        """Called on every request in some paths; a second connect to the same
        file must not fail on the table it already created."""
        again = store.connect(Path(self.tmp.name) / "cold.db")
        try:
            self.assertEqual(
                again.execute("SELECT count(*) FROM engine_runs").fetchone()[0], 0)
        finally:
            again.close()


class TheEndpointThatFoundIt(unittest.TestCase):
    def test_overview_answers_on_a_cold_store(self):
        """The behaviour the operator sees. Asserting the table exists would
        not prove the endpoint stopped 500ing — that is what regressed."""
        from fastapi.testclient import TestClient
        import server

        client = TestClient(server.app)
        r = client.get("/api/overview")
        self.assertNotEqual(r.status_code, 500, r.text[:400])


if __name__ == "__main__":
    unittest.main()
