"""Retention on superseded derived facts — the reference test, mostly.

`SPEC-persistence-retention.md` §3.3 allows a derived fact to go when its
version is superseded, it is old enough, and no PERMANENT fact names it. The
first two are arithmetic. The third is the whole risk: `zone_id` is
`SYMBOL|TF|TYPE|TS` and carries **no version**, so a setup written under
`zone-v0.9` names a string that a `zone-v0.13` fact would name too. Resolving
that reference by version — or substituting the current generation for the one
the setup was actually built from — is the join hazard in
`docs/AUDIT-setup-id-join-hazards.md`: same id, different top and bottom,
silently different reconstruction.

So the rule these tests pin is blunt on purpose: if a permanent fact names a
zone id, every generation of that zone stays.
"""
import json
import sqlite3
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prune  # noqa: E402
from engine import store  # noqa: E402

DAY = 86_400


class PruneFactsCase(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(store.SCHEMA)
        self.now = int(time.time())
        self.live = prune.current_versions()

    def tearDown(self):
        self.con.close()

    def fact(self, kind, version, *, age_days=90, payload=None, symbol="BTC-USD"):
        at = self.now - int(age_days * DAY)
        store.insert_fact(
            self.con, symbol=symbol, tf="1H", kind=kind,
            market_time=at, confirmed_at=at, algo_version=version,
            payload=payload or {"n": age_days})
        self.con.commit()
        # content_hash, not rowid: SQLite reuses a rowid the moment the prune
        # frees it, so the retention fact this very prune writes can land on
        # the id of the row it just deleted and read back as "still there".
        return self.con.execute(
            "SELECT content_hash FROM facts ORDER BY id DESC LIMIT 1").fetchone()[0]

    def alive(self):
        return {r[0] for r in self.con.execute("SELECT content_hash FROM facts")}

    def prune_facts(self, min_age_days=30):
        plan = prune.plan_facts(self.con, min_age_days)
        prune.apply_facts(self.con, plan)
        return plan

    # ------------------------------------------------------- version and age

    def test_the_current_generation_is_never_deleted(self):
        """Whatever the engine writes today stays, at any age."""
        kept = self.fact("swing", self.live["swing"], age_days=900)
        self.prune_facts()
        self.assertIn(kept, self.alive())

    def test_a_superseded_generation_goes(self):
        doomed = self.fact("swing", "swing-v0.2-draft", age_days=90)
        self.prune_facts()
        self.assertNotIn(doomed, self.alive())

    def test_a_recent_superseded_generation_is_held(self):
        """An A/B loser is evidence while the comparison is live (spec §4)."""
        young = self.fact("swing", "swing-v0.2-draft", age_days=3)
        self.prune_facts(min_age_days=30)
        self.assertIn(young, self.alive())

    def test_current_versions_are_read_from_the_engines_not_sorted(self):
        """`v0.9` sorts above `v0.13`. Sorting version strings would delete the
        live generation and keep the dead one — the exact inversion this map
        exists to prevent."""
        self.assertEqual("zone-v0.13-draft", self.live["zone"])
        self.assertGreater("zone-v0.9-draft", "zone-v0.13-draft",
                           "string order really is inverted here")

    def test_every_derived_kind_resolves_to_a_real_engine_constant(self):
        for kind, version in self.live.items():
            with self.subTest(kind=kind):
                self.assertTrue(version, f"{kind} has no current version")
                self.assertIn("-v", version)

    # ------------------------------------------------------ the reference test

    def test_a_superseded_zone_a_setup_names_is_kept(self):
        zid = "BTC-USD|1H|DEMAND|1700000000"
        held = self.fact("zone", "zone-v0.9-draft", age_days=200,
                         payload={"zone_id": zid, "top": "1", "bottom": "0"})
        self.fact("setup", "setup-v0.17-draft", age_days=200,
                  payload={"zone_id": zid, "setup_id": "s1", "state": "TRIGGERED"})
        plan = self.prune_facts()
        self.assertIn(held, self.alive(),
                      "deleting this orphans the setup's zone reference")
        self.assertEqual(1, plan["held_by_reference"])

    def test_an_unreferenced_superseded_zone_goes(self):
        doomed = self.fact("zone", "zone-v0.9-draft", age_days=200,
                           payload={"zone_id": "BTC-USD|1H|DEMAND|1", "top": "1"})
        self.fact("setup", "setup-v0.17-draft", age_days=200,
                  payload={"zone_id": "ETH-USD|1H|SUPPLY|9", "setup_id": "s2"})
        self.prune_facts()
        self.assertNotIn(doomed, self.alive())

    def test_a_reference_protects_every_generation_of_that_zone(self):
        """The id carries no version, so the reference cannot pick one."""
        zid = "BTC-USD|1H|DEMAND|1700000000"
        old = self.fact("zone", "zone-v0.8-draft", age_days=300,
                        payload={"zone_id": zid, "top": "1"})
        mid = self.fact("zone", "zone-v0.9-draft", age_days=200,
                        payload={"zone_id": zid, "top": "2"})
        self.fact("setup", "setup-v0.17-draft", age_days=200,
                  payload={"zone_id": zid, "setup_id": "s3"})
        self.prune_facts()
        self.assertIn(old, self.alive())
        self.assertIn(mid, self.alive())

    def test_orders_and_risk_decisions_also_hold_a_reference(self):
        zid = "BTC-USD|1H|DEMAND|1700000001"
        held = self.fact("zone", "zone-v0.9-draft", age_days=300,
                         payload={"zone_id": zid})
        self.fact("order", "exec-v0.21-draft", age_days=300,
                  payload={"zone_id": zid, "event": "FILLED"})
        self.prune_facts()
        self.assertIn(held, self.alive())

    # ------------------------------------------------------------ the classes

    def test_permanent_kinds_are_never_eligible(self):
        keep = [self.fact(k, "old-v0.1-draft", age_days=900)
                for k in ("setup", "exec", "order", "risk", "account",
                          "cooldown", "universe")]
        self.prune_facts()
        alive = self.alive()
        for fid in keep:
            self.assertIn(fid, alive)

    def test_an_unclassified_kind_is_never_touched(self):
        """A kind absent from DERIVED_KINDS is left alone — the safe direction
        for something nobody has classified yet."""
        unknown = self.fact("brand_new_kind", "brand-v0.1-draft", age_days=900)
        self.prune_facts()
        self.assertIn(unknown, self.alive())

    # ------------------------------------------------------------- the shape

    def test_planning_alone_deletes_nothing(self):
        self.fact("swing", "swing-v0.2-draft", age_days=900)
        before = self.alive()
        prune.plan_facts(self.con, 30)
        self.assertEqual(before, self.alive())

    def test_the_prune_records_itself_as_a_fact(self):
        self.fact("swing", "swing-v0.2-draft", age_days=900)
        self.prune_facts()
        row = self.con.execute(
            "SELECT payload FROM facts WHERE kind='retention'").fetchone()
        self.assertIsNotNone(row)
        p = json.loads(row[0])
        self.assertEqual("facts", p["target"])
        self.assertEqual(1, p["removed"])

    def test_candles_are_never_touched(self):
        self.con.execute(
            "INSERT INTO candles (symbol, tf, open_ts, open, high, low, close,"
            " volume, source, imported_at) VALUES "
            "('BTC-USD','1H',1,'1','1','1','1','1','test',1)")
        self.con.commit()
        self.fact("swing", "swing-v0.2-draft", age_days=900)
        self.prune_facts()
        self.assertEqual(
            1, self.con.execute("SELECT COUNT(*) FROM candles").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
