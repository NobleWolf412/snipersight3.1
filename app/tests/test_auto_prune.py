"""The scanner's routine telemetry sweep — cadence, receipts, and its cage.

The sweep may only ever touch the RUNS target. The facts target deletes
research generations and keeps a human trigger by design; these tests pin
that the routine path cannot reach it, that the cadence is enforced by the
receipts themselves, and that a sweep failure cannot take the scan cycle
down. All stores here are in-memory; nothing touches the live database.
"""
import json
import sqlite3
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prune  # noqa: E402
from engine import runlog, store  # noqa: E402

DAY = 86_400


class AutoPruneCase(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(store.SCHEMA)
        self.con.executescript(runlog.RUNS_SCHEMA)
        self.now = int(time.time())

    def tearDown(self):
        self.con.close()

    def add_run(self, *, age_days=30, engine="swings"):
        self.con.execute(
            "INSERT INTO engine_runs (engine, algo_version, symbol, tf,"
            " n_inputs, n_new_facts, duration_ms, run_at) "
            "VALUES (?,?,?,?,0,0,1,?)",
            (engine, f"{engine}-v0.1", "BTC-USD", "1H",
             self.now - int(age_days * DAY)))
        self.con.commit()

    def receipts(self):
        return [json.loads(r[0]) for r in self.con.execute(
            "SELECT payload FROM facts WHERE kind='retention' ORDER BY id")]

    # ------------------------------------------------------------- cadence

    def test_first_sweep_runs_and_leaves_a_receipt(self):
        self.add_run(age_days=30)
        self.add_run(age_days=0)             # newest survives
        out = prune.maybe_auto_prune_runs(self.con)
        self.assertIsNotNone(out)
        self.assertEqual(out["removed"], 1)
        self.assertEqual(len(self.receipts()), 1)

    def test_a_second_sweep_the_same_day_is_refused(self):
        self.add_run(age_days=30)
        self.add_run(age_days=0)
        prune.maybe_auto_prune_runs(self.con)
        self.add_run(age_days=40)            # newly eligible junk
        self.assertIsNone(prune.maybe_auto_prune_runs(self.con),
                          "the cadence gate must hold even with work waiting")
        self.assertEqual(len(self.receipts()), 1)

    def test_the_receipt_is_the_schedule_state(self):
        """No sidecar file, no settings row: due-ness is read from the last
        runs receipt, so the schedule cannot drift from what happened."""
        self.add_run(age_days=0)
        prune.maybe_auto_prune_runs(self.con)          # zero-removed receipt
        receipts = self.receipts()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["removed"], 0,
                         "checked-nothing-eligible is a receipt, not silence")
        self.assertIsNotNone(prune.last_runs_prune_at(self.con))

    def test_a_facts_receipt_does_not_satisfy_the_runs_cadence(self):
        """The two targets keep separate clocks — a manual facts prune must
        not postpone the telemetry sweep."""
        now = int(time.time())
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="retention",
            market_time=now, confirmed_at=now,
            algo_version=prune.RETENTION_VERSION,
            payload={"target": "facts", "removed": 5})
        self.con.commit()
        self.assertIsNone(prune.last_runs_prune_at(self.con))

    def test_an_old_receipt_makes_the_sweep_due_again(self):
        self.add_run(age_days=30)
        self.add_run(age_days=0)
        old = self.now - 2 * DAY
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="retention",
            market_time=old, confirmed_at=old,
            algo_version=prune.RETENTION_VERSION,
            payload={"target": "runs", "removed": 0})
        self.con.commit()
        self.assertIsNotNone(prune.maybe_auto_prune_runs(self.con))

    # ------------------------------------------------------------- the cage

    def test_the_routine_path_can_never_reach_the_facts_target(self):
        """The cage, pinned at the AST: every function the sweep calls is on
        an allowlist, so a future edit that wires plan_facts/apply_facts (or
        anything new and undeclared) into the routine path fails here rather
        than deleting research on a timer."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(prune.maybe_auto_prune_runs))
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)}
        allowed = {"last_runs_prune_at", "plan_runs", "apply_runs", "int"}
        self.assertLessEqual(called, allowed,
                             f"the sweep calls {sorted(called - allowed)} — "
                             "anything beyond the runs pipeline needs a "
                             "human trigger, not a timer")

    def test_kept_rows_survive_the_sweep(self):
        """The sweep inherits every keep rule — referenced, failed, newest,
        window — because it IS apply_runs. One spot check: the newest run."""
        self.add_run(age_days=30)
        self.add_run(age_days=0)
        prune.maybe_auto_prune_runs(self.con)
        self.assertEqual(
            self.con.execute("SELECT COUNT(*) FROM engine_runs").fetchone()[0], 1)

    def test_the_heartbeat_is_beaten_per_batch(self):
        beats = []
        self.add_run(age_days=30)
        self.add_run(age_days=0)
        prune.maybe_auto_prune_runs(self.con, beat=beats.append)
        self.assertGreaterEqual(len(beats), 1,
                                "a silent long sweep reads as a hung scanner")

    def test_this_suite_cannot_reach_the_live_store(self):
        import re
        src = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual([], re.findall(r"store\.connect\(\s*\)", src))


if __name__ == "__main__":
    unittest.main()
