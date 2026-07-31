"""The write-ahead log must not be able to eat the machine again.

On 2026-07-30 the WAL reached 966 MB against a 1.7 GB database and GET
/api/overview took 57 SECONDS. Restarting the stack checkpointed it to 1 MB and
the same request took 0.90s. Nothing was wrong with the data.

Two causes, both measured rather than assumed:

  * A checkpoint cannot reset the WAL while ANY reader holds an open snapshot.
    With one reader open, `wal_checkpoint(TRUNCATE)` returns busy=1 and leaves
    frames behind; with it closed the same call returns frames=0 and the file
    drops to zero. The API polls continuously and the scan loop reads for most
    of a ~300s cycle, so reader-free instants are rare.
  * `journal_size_limit` defaulted to -1, so a checkpoint that DID succeed
    still left the file at its high-water mark. Size only ratcheted upward.

These tests pin the settings and the mechanism. The busy-reader test is the
important one: it is the reason a size limit alone is not a fix, and the reason
the scanner checkpoints between cycles rather than during them.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine import store


class WalIsBounded(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.con = store.connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_wal_mode_is_on(self):
        self.assertEqual(
            self.con.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")

    def test_journal_size_limit_is_set(self):
        limit = self.con.execute("PRAGMA journal_size_limit").fetchone()[0]
        self.assertNotEqual(
            limit, -1,
            "journal_size_limit is unbounded — a checkpointed WAL still never "
            "shrinks, which is how 966 MB accumulated and stayed")
        self.assertGreater(limit, 0)
        self.assertEqual(limit, store.WAL_SIZE_LIMIT_BYTES)

    def test_checkpoint_reclaims_the_log(self):
        for i in range(400):
            store.insert_fact(self.con, symbol="T", tf="15m", kind="probe",
                              market_time=i, confirmed_at=i,
                              algo_version="test-v1", payload={"i": i})
        self.con.commit()
        wal = Path(str(self.db) + "-wal")
        self.assertTrue(wal.exists() and wal.stat().st_size > 0,
                        "no WAL was produced, so this proves nothing")
        out = store.checkpoint_wal(self.con)
        self.assertEqual(out["busy"], 0)
        self.assertEqual(wal.stat().st_size, 0,
                         "TRUNCATE left the file at its high-water mark")

    def test_an_open_reader_blocks_the_reset(self):
        """The mechanism itself. If this ever stops being true, the whole
        between-cycles placement of the scanner's checkpoint is pointless."""
        for i in range(400):
            store.insert_fact(self.con, symbol="T", tf="15m", kind="probe",
                              market_time=i, confirmed_at=i,
                              algo_version="test-v1", payload={"i": i})
        self.con.commit()

        reader = sqlite3.connect(self.db)
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM facts").fetchone()
        try:
            blocked = store.checkpoint_wal(self.con)
            self.assertEqual(
                blocked["busy"], 1,
                "an open read snapshot no longer blocks the reset — if SQLite "
                "changed this, the cycle-boundary placement can be simplified")
        finally:
            reader.rollback()
            reader.close()

        after = store.checkpoint_wal(self.con)
        self.assertEqual(after["busy"], 0, "reset still blocked with no readers")
        self.assertEqual(Path(str(self.db) + "-wal").stat().st_size, 0)

    def test_checkpoint_never_raises(self):
        """Housekeeping must never be able to kill a scan cycle."""
        closed = store.connect(Path(self.tmp.name) / "u.db")
        closed.close()
        out = store.checkpoint_wal(closed)          # operating on a closed handle
        self.assertIn("error", out)
        self.assertIsNone(out["busy"])


class ScannerCheckpointsBetweenCycles(unittest.TestCase):
    """Placement matters as much as existence: the loop holds a read snapshot
    for most of a ~300s cycle, so a checkpoint called mid-cycle reports busy and
    reclaims nothing."""

    def test_live_loop_checkpoints_outside_the_work(self):
        src = (Path(__file__).resolve().parent.parent / "live.py").read_text(
            encoding="utf-8")
        self.assertIn("store.checkpoint_wal", src,
                      "the scan loop never reclaims the WAL")
        call = src.index("store.checkpoint_wal")
        cycle = src.index("n, fired = cycle(")
        self.assertGreater(call, cycle,
                           "the checkpoint runs before the cycle's work, while "
                           "the previous snapshot may still be open")


if __name__ == "__main__":
    unittest.main()
