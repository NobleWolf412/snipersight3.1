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


if __name__ == "__main__":
    unittest.main()
