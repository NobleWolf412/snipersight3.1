"""The rebuild reading (engine/rebuild.py): is the record still being
re-derived under the current setup generation, and how far along?

Pinned on a temp store's engine_runs, because the only thing that can go
wrong here is the definition — counting facts instead of runs would call a
quiet market unfinished forever, and forgetting the scan-set window would
count retired markets as work still owed."""
import tempfile
import unittest
from pathlib import Path

from engine import rebuild, store

NOW = 1_800_000_000


def _run(con, version, symbol, tf, at, engine="setup"):
    con.execute("INSERT INTO engine_runs (engine, algo_version, symbol, tf, n_inputs, "
                "n_new_facts, duration_ms, run_at) VALUES (?,?,?,?,0,0,1,?)",
                (engine, version, symbol, tf, at))


class RebuildStatus(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.con = store.connect(Path(tmp.name) / "r.db")
        self.addCleanup(self.con.close)

    def test_active_while_the_current_version_has_not_covered_the_scan_set(self):
        for sym in ("A", "B", "C", "D", "E"):
            _run(self.con, "setup-vOLD", sym, "1H", NOW - 3600)
        _run(self.con, "setup-vNEW", "A", "1H", NOW - 100)
        _run(self.con, "setup-vNEW", "B", "1H", NOW - 50)
        self.con.commit()
        s = rebuild.status(self.con, version="setup-vNEW", now=NOW)
        self.assertTrue(s["active"])
        self.assertEqual((s["done"], s["total"]), (2, 5))
        self.assertEqual(s["last_run_at"], NOW - 50)

    def test_done_once_every_pair_in_the_scan_set_has_a_run_under_the_version(self):
        for sym in ("A", "B", "C"):
            _run(self.con, "setup-vOLD", sym, "1H", NOW - 3600)
            _run(self.con, "setup-vNEW", sym, "1H", NOW - 60)
        self.con.commit()
        s = rebuild.status(self.con, version="setup-vNEW", now=NOW)
        self.assertFalse(s["active"])
        self.assertEqual((s["done"], s["total"]), (3, 3))

    def test_a_market_the_scanner_stopped_visiting_is_not_work_owed(self):
        """Retired symbols: their old-version runs are older than the scan-set
        window, so they leave `total` on their own."""
        _run(self.con, "setup-vOLD", "RETIRED", "1H", NOW - 3 * 86400)
        _run(self.con, "setup-vOLD", "A", "1H", NOW - 3600)
        _run(self.con, "setup-vNEW", "A", "1H", NOW - 60)
        self.con.commit()
        s = rebuild.status(self.con, version="setup-vNEW", now=NOW)
        self.assertFalse(s["active"])
        self.assertEqual(s["total"], 1)

    def test_an_empty_store_is_not_a_rebuild(self):
        s = rebuild.status(self.con, version="setup-vNEW", now=NOW)
        self.assertFalse(s["active"])
        self.assertEqual((s["done"], s["total"]), (0, 0))

    def test_it_reads_the_current_setup_version_by_default(self):
        from engine.setups import SETUP_VERSION
        self.assertEqual(rebuild.status(self.con, now=NOW)["version"], SETUP_VERSION)

    def test_account_status_sees_an_exec_only_rebuild(self):
        """The failure this exists for: setups complete, execsim mid-rebuild.

        `status()` defaults to the setup engine, so on 2026-09-07 an exec-only
        bump re-derived every settlement while the screen said the record was
        complete — the 2026-09-05 defect one engine over."""
        from engine.execsim import EXEC_VERSION
        from engine.setups import SETUP_VERSION
        _run(self.con, SETUP_VERSION, "A", "1H", NOW - 60)
        _run(self.con, "exec-vOLD", "A", "1H", NOW - 60, engine="execsim")
        self.con.commit()
        self.assertFalse(rebuild.status(self.con, now=NOW)["active"],
                         "setups are complete — the old reading sees nothing")
        s = rebuild.account_status(self.con, now=NOW)
        self.assertTrue(s["active"], "an exec rebuild must reach the notice")
        self.assertEqual((s["engine"], s["version"]), ("execsim", EXEC_VERSION))

    def test_a_bump_while_the_scanner_is_down_still_announces_itself(self):
        """`total` counts only the last 24h, so a version bumped while the
        scanner is stopped reports 0 of 0 and `active` False — silence in
        exactly the state the notice is for. An engine with runs under an
        older version and none under the current one is provisional."""
        from engine.execsim import EXEC_VERSION
        from engine.setups import SETUP_VERSION
        _run(self.con, SETUP_VERSION, "A", "1H", NOW - 60)
        # execsim last ran three days ago, under the previous generation
        _run(self.con, "exec-vOLD", "A", "1H", NOW - 3 * 86400, engine="execsim")
        self.con.commit()
        plain = rebuild.status(self.con, engine="execsim",
                               version=EXEC_VERSION, now=NOW)
        self.assertEqual((plain["done"], plain["total"]), (0, 0))
        self.assertFalse(plain["active"], "the window-based reading sees calm")
        s = rebuild.account_status(self.con, now=NOW)
        self.assertTrue(s["active"], "an empty current-version book must say so")
        self.assertTrue(s.get("idle"), "and must say the scanner is not working")
        self.assertEqual(s["engine"], "execsim")

    def test_a_first_run_on_a_fresh_store_is_not_a_rebuild(self):
        """The other side of the rule above: an engine that has NEVER run has
        nothing to rebuild, and must not raise a permanent notice on a new
        install."""
        from engine.setups import SETUP_VERSION
        _run(self.con, SETUP_VERSION, "A", "1H", NOW - 60)
        self.con.commit()
        s = rebuild.account_status(self.con, now=NOW)
        self.assertFalse(s["active"],
                         "no execsim history at all is not a rebuild")

    def test_every_account_engine_label_matches_the_runlog(self):
        """A label no runlog uses reports total=0, so `active` is False and the
        notice goes quiet in exactly the case it is for — no exception, no
        failing assertion anywhere else. "exec" instead of "execsim" was that
        mistake, made while writing the fix above. This pins the names against
        the RunRecorder calls that actually write them."""
        import re
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "engine"
        written = set()
        for f in src.glob("*.py"):
            written.update(re.findall(r'RunRecorder\(\s*con\s*,\s*["\'](\w+)["\']',
                                      f.read_text(encoding="utf-8")))
        self.assertTrue(written, "found no RunRecorder labels to check against")
        for label, _ in rebuild.ACCOUNT_ENGINES:
            self.assertIn(label, written,
                          f"ACCOUNT_ENGINES names {label!r}, which no engine "
                          f"records runs under — the notice would stay silent")


if __name__ == "__main__":
    unittest.main()
