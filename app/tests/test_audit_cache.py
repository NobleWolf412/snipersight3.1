"""The audit cache must not answer questions about one store using another's verdict.

Found 2026-07-30. `quality._AUDIT_CACHE` was a single module-level dict keyed on
nothing, and its background refresh called `store.connect()` with no argument —
so it audited the DEFAULT store regardless of which connection the caller
passed, then served that verdict to everyone.

With one production database the bug is invisible. It stopped being invisible
the moment a second store existed: `risk.py`'s data-health gate read a cached
BLOCKED verdict belonging to a different database, rejected every trade intent
as DATA_HEALTH_BLOCKED, and a drawdown-halt test therefore observed no halt —
because no position was ever opened to draw the account down. The test failed
only when run alongside others, which is the worst way for a bug to present.

Any second store hits this: a replay copy, a scratch database, an A/B run.
"""
import tempfile
import unittest
from pathlib import Path

from engine import quality, store


class AuditCacheIsolation(unittest.TestCase):
    def setUp(self):
        self.a = tempfile.TemporaryDirectory()
        self.b = tempfile.TemporaryDirectory()
        self.con_a = store.connect(Path(self.a.name) / "a.db")
        self.con_b = store.connect(Path(self.b.name) / "b.db")

    def tearDown(self):
        self.con_a.close()
        self.con_b.close()
        self.a.cleanup()
        self.b.cleanup()

    def test_two_stores_get_two_cache_slots(self):
        self.assertNotEqual(quality._db_key(self.con_a),
                            quality._db_key(self.con_b))

    def test_a_verdict_does_not_leak_between_stores(self):
        """The exact failure: poison one store's slot, read the other."""
        key_a = quality._db_key(self.con_a)
        quality._slot(key_a).update(
            {"report": {"evaluation_allowed": False, "status": "BLOCKED"},
             "at": 2 ** 40})                       # far future: never stale
        self.assertIsNone(
            quality.cached_audit(self.con_b),
            "store B must report PENDING, never inherit store A's BLOCKED verdict")

    def test_non_default_store_never_spawns_a_background_audit(self):
        """A daemon thread holding a temporary store open outlives its owner —
        on Windows that makes the directory undeletable, and everywhere it means
        auditing a database whose lifetime we do not control."""
        import threading
        before = threading.active_count()
        for _ in range(5):
            quality.cached_audit(self.con_a)
        self.assertEqual(threading.active_count(), before,
                         "no background thread may be spawned for a non-default store")
        self.assertFalse(quality._slot(quality._db_key(self.con_a))["refreshing"])

    def test_pending_is_none_not_a_confident_verdict(self):
        """Loud-fallback rule: 'we have not audited yet' must never render as
        'audited and fine'. Callers key off None to show PENDING."""
        self.assertIsNone(quality.cached_audit(self.con_a))

    def test_force_audits_the_store_it_was_given(self):
        report = quality.cached_audit(self.con_a, force=True)
        self.assertIsNotNone(report)
        self.assertIs(quality._slot(quality._db_key(self.con_a))["report"], report)
        # ...and did not touch the other store's slot
        self.assertIsNone(quality._slot(quality._db_key(self.con_b))["report"])


class RiskGateConsequence(unittest.TestCase):
    """The behaviour the leak actually broke, pinned directly."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_foreign_blocked_verdict_does_not_block_this_store(self):
        from engine import risk
        other = tempfile.TemporaryDirectory()
        try:
            con_other = store.connect(Path(other.name) / "o.db")
            quality._slot(quality._db_key(con_other)).update(
                {"report": {"evaluation_allowed": False}, "at": 2 ** 40})
            con_other.close()
            # risk.run must not see the foreign BLOCKED verdict
            result = risk.run(self.con)
            self.assertIsInstance(result, dict)
            blocked = [
                r for r in self.con.execute(
                    "SELECT payload FROM facts WHERE kind='risk'").fetchall()
                if "DATA_HEALTH_BLOCKED" in r[0]]
            self.assertEqual(blocked, [],
                             "another store's audit must never gate this one's trades")
        finally:
            other.cleanup()


if __name__ == "__main__":
    unittest.main()
