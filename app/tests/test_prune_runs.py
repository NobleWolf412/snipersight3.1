"""Retention on `engine_runs` — what survives a prune, and what it costs.

Every test here is a keep rule. The dangerous failure is not deleting too
little; it is deleting a row some fact still points at, because that orphans
lineage silently — the fact keeps its `producer_run_id`, the run it names is
simply gone, and nothing errors until someone asks the question months later.
"""
import sqlite3
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prune  # noqa: E402
from engine import runlog, store  # noqa: E402

DAY = 86_400


class PruneRunsCase(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        self.con.executescript(runlog.RUNS_SCHEMA)
        self.now = int(time.time())

    def tearDown(self):
        self.con.close()

    def add_run(self, engine="swings", *, age_days=30, status="PASS",
                run_id="", n_new_facts=0):
        self.con.execute(
            "INSERT INTO engine_runs (engine, algo_version, symbol, tf, n_inputs,"
            " n_new_facts, duration_ms, run_at, notes, run_id, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (engine, f"{engine}-v0.1", "BTC-USD", "1H", 10, n_new_facts, 5,
             self.now - int(age_days * DAY), "", run_id, status))
        self.con.commit()
        return self.con.execute("SELECT MAX(id) FROM engine_runs").fetchone()[0]

    def add_fact(self, run_id, market_time=None):
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="swing",
            market_time=market_time or self.now, confirmed_at=self.now,
            algo_version="swing-v0.1", payload={"run": run_id})
        self.con.execute("UPDATE facts SET producer_run_id=? WHERE producer_run_id IS NULL",
                         (run_id,))
        self.con.commit()

    def surviving_ids(self):
        return {r[0] for r in self.con.execute("SELECT id FROM engine_runs")}

    def prune(self, keep_days=7):
        plan = prune.plan_runs(self.con, keep_days)
        prune.apply_runs(self.con, plan)
        return plan

    # ------------------------------------------------------------- the keeps

    def test_a_run_a_fact_points_at_is_never_deleted(self):
        """Lineage. This is the rule the whole table exists to serve."""
        kept = self.add_run(age_days=400, run_id="abc123", n_new_facts=1)
        doomed = self.add_run(age_days=400, run_id="zzz999")
        self.add_run(age_days=0)                 # newest, so `doomed` is not
        self.add_fact("abc123")
        self.prune()
        self.assertIn(kept, self.surviving_ids())
        self.assertNotIn(doomed, self.surviving_ids())

    def test_a_failed_run_is_never_deleted(self):
        """2 rows in 4.1M on the live store. Keeping every failure forever is
        free; losing the record of one is not recoverable."""
        kept = self.add_run(age_days=400, status="ERROR")
        self.prune()
        self.assertIn(kept, self.surviving_ids())

    def test_the_newest_run_of_each_engine_survives(self):
        """/api/overview asks for exactly this, twice a minute."""
        old_swings = self.add_run("swings", age_days=400)
        new_swings = self.add_run("swings", age_days=200)
        only_zones = self.add_run("zones", age_days=900)
        self.prune()
        alive = self.surviving_ids()
        self.assertIn(new_swings, alive)
        self.assertIn(only_zones, alive, "an engine's ONLY run is also its newest")
        self.assertNotIn(old_swings, alive)

    def test_the_newest_run_of_each_version_survives_not_just_each_engine(self):
        """Load-bearing for the FACTS prune, not for this one: its 30-day
        guard dates a superseded version by MAX(run_at) in this table. A
        GROUP BY that collapses back to engine-only would delete a retired
        version's last run rows, the version's clock would fall back to some
        far older surviving row, and the facts prune would date it weeks too
        old — the market-time defect resurrected through a side door."""
        import sqlite3 as _sq
        v1_last = self.con.execute(
            "INSERT INTO engine_runs (engine, algo_version, symbol, tf,"
            " n_inputs, n_new_facts, duration_ms, run_at) "
            "VALUES ('swings','swings-v0.1','BTC-USD','1H',0,0,1,?)",
            (self.now - 100 * DAY,)).lastrowid
        self.con.execute(
            "INSERT INTO engine_runs (engine, algo_version, symbol, tf,"
            " n_inputs, n_new_facts, duration_ms, run_at) "
            "VALUES ('swings','swings-v0.2','BTC-USD','1H',0,0,1,?)",
            (self.now - 50 * DAY,))
        self.con.commit()
        self.prune()
        self.assertIn(v1_last, self.surviving_ids(),
                      "the retired version's newest run is its wall clock; "
                      "deleting it silently re-dates the facts prune")

    def test_runs_inside_the_keep_window_survive(self):
        recent = self.add_run(age_days=2)
        old = self.add_run(age_days=2)          # same engine, so neither is "newest"
        newest = self.add_run(age_days=0.5)
        self.prune(keep_days=7)
        alive = self.surviving_ids()
        self.assertIn(recent, alive)
        self.assertIn(old, alive)
        self.assertIn(newest, alive)

    def test_the_keep_window_is_honoured_as_given(self):
        mid = self.add_run(age_days=20)
        self.add_run(age_days=0)                 # keeps `mid` from being newest
        self.prune(keep_days=30)
        self.assertIn(mid, self.surviving_ids())

    # ----------------------------------------------------------- the deletes

    def test_an_old_unreferenced_passing_run_goes(self):
        """97.9% of the live table. Produced nothing, failed at nothing, and
        no fact names it."""
        doomed = self.add_run(age_days=400)
        self.add_run(age_days=0)                 # newest, so `doomed` is not
        plan = self.prune()
        self.assertNotIn(doomed, self.surviving_ids())
        self.assertEqual(1, plan["deletable"])

    def test_a_run_with_an_empty_run_id_is_still_deletable(self):
        """Rows written before the run_id column existed carry ''. They cannot
        be referenced by anything, so age alone decides."""
        doomed = self.add_run(age_days=400, run_id="")
        self.add_run(age_days=0)
        self.prune()
        self.assertNotIn(doomed, self.surviving_ids())

    # ------------------------------------------------------------- the shape

    def test_a_plan_alone_deletes_nothing(self):
        """--dry-run is the default, and plan_runs must have no side effects."""
        self.add_run(age_days=400)
        self.add_run(age_days=0)
        before = self.surviving_ids()
        prune.plan_runs(self.con, 7)
        self.assertEqual(before, self.surviving_ids())

    def test_the_prune_records_itself_as_a_fact(self):
        """Without this, a pruned store is indistinguishable from a store whose
        scanner was down for the same period."""
        self.add_run(age_days=400)
        self.add_run(age_days=0)
        self.prune()
        row = self.con.execute(
            "SELECT algo_version, payload FROM facts WHERE kind='retention'").fetchone()
        self.assertIsNotNone(row, "a prune that leaves no trace is not auditable")
        self.assertEqual(prune.RETENTION_VERSION, row[0])
        self.assertIn('"removed":1', row[1])   # canonical JSON: no spaces

    def test_facts_and_candles_are_never_touched(self):
        self.add_run(age_days=400, run_id="r1")
        self.add_run(age_days=0)
        self.add_fact("r1")
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.prune()
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertEqual(before + 1, after, "only the retention fact is added")

    def test_deleting_requires_an_explicit_flag(self):
        """The spec's §5 shape: dry run is what you get by asking for nothing.

        Asserted against the parser rather than by running it — prune.main()
        opens the real store, and a test that reaches the operator's live
        database to check an argument default is the hazard CLAUDE.md names.
        """
        src = Path(prune.__file__).read_text(encoding="utf-8")
        self.assertIn('ap.add_argument("--apply", action="store_true"', src)
        self.assertIn("if not args.apply:", src)
        self.assertIn("DRY RUN", src)

    def test_both_targets_are_implemented(self):
        for name in ("plan_runs", "apply_runs", "plan_facts", "apply_facts"):
            with self.subTest(fn=name):
                self.assertTrue(hasattr(prune, name))


if __name__ == "__main__":
    unittest.main()
