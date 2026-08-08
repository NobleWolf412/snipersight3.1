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
        from engine import runlog
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(store.SCHEMA)
        self.con.executescript(runlog.RUNS_SCHEMA)
        self.now = int(time.time())
        self.live = prune.current_versions()

    def tearDown(self):
        self.con.close()

    def ran(self, version, *, engine="test", days_ago=90):
        """Record that this algo_version last RAN this long ago. The age gate
        measures wall clock via engine_runs, never market time."""
        self.con.execute(
            "INSERT INTO engine_runs (engine, algo_version, symbol, tf,"
            " n_inputs, n_new_facts, duration_ms, run_at) "
            "VALUES (?,?,?,?,0,0,1,?)",
            (engine, version, "BTC-USD", "1H",
             self.now - int(days_ago * DAY)))
        self.con.commit()

    def fact(self, kind, version, *, age_days=90, payload=None, symbol="BTC-USD",
             last_ran_days_ago=None):
        at = self.now - int(age_days * DAY)
        store.insert_fact(
            self.con, symbol=symbol, tf="1H", kind=kind,
            market_time=at, confirmed_at=at, algo_version=version,
            payload=payload or {"n": age_days})
        self.con.commit()
        # Default: give the version run history matching the fact's age, so
        # tests about OTHER gates aren't silently held by the age gate.
        self.ran(version, days_ago=(last_ran_days_ago
                                    if last_ran_days_ago is not None
                                    else age_days))
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
        """An A/B loser is evidence while the comparison is live (spec §4).
        Age is WALL CLOCK since the version last ran — the original
        market-time guard made a generation bumped away yesterday 67-76%
        eligible today, because its facts describe old candles."""
        young = self.fact("swing", "swing-v0.2-draft",
                          age_days=200, last_ran_days_ago=3)
        self.prune_facts(min_age_days=30)
        self.assertIn(young, self.alive())

    def test_a_version_with_no_run_history_is_held_not_guessed_old(self):
        """'We cannot date it' is not 'it is old'. Fail closed."""
        undatable = self.fact("swing", "swing-v0.2-draft",
                              age_days=400, last_ran_days_ago=None)
        self.con.execute("DELETE FROM engine_runs")   # no history at all
        self.con.commit()
        plan = self.prune_facts()
        self.assertIn(undatable, self.alive())
        self.assertEqual(plan["held"]["undatable"], 1)

    def test_a_version_pinned_in_engine_source_is_never_deleted(self):
        """The stop-ship finding. swings.py reads structure-v0.2-draft and
        liq-v0.2-draft by name on every scan cycle — 'not the current
        version' is not 'nothing reads it', and deleting those rows would
        change swing tiers under an unmoved swing tag, unrecoverably."""
        for version, kind in (("structure-v0.2-draft", "structure"),
                              ("liq-v0.2-draft", "liquidity")):
            with self.subTest(version=version):
                pinned = self.fact(kind, version, age_days=400)
                plan = self.prune_facts()
                self.assertIn(pinned, self.alive(),
                              f"{version} is named in engine source")
                self.assertGreater(plan["held"]["named_in_code"], 0)

    def test_the_pin_scan_actually_sees_the_swings_pins(self):
        named = prune.versions_named_in_code()
        self.assertIn("structure-v0.2-draft", named)
        self.assertIn("liq-v0.2-draft", named)

    def test_every_current_version_is_visible_to_the_pin_scan(self):
        """The invariant that keeps the scan honest as kinds are added: every
        DERIVED_KINDS current version is itself a double- or single-quoted
        literal in engine source, so if the scan cannot see one, either a
        stem is missing from the regex or the version format drifted —
        both of which would blind the named-in-code gate to a future pin."""
        named = prune.versions_named_in_code()
        for kind, version in prune.current_versions().items():
            with self.subTest(kind=kind):
                self.assertIn(version, named,
                              f"{kind}'s own current version is invisible "
                              f"to versions_named_in_code — fix the regex "
                              f"before trusting the named gate")

    def test_a_single_quoted_pin_is_seen(self):
        """engine source already mixes quote styles (factorstats has
        single-quoted version literals); a pin spelled 'structure-v0.2-draft'
        must be as protective as the double-quoted one."""
        import re as _re
        self.assertTrue(_re.search(prune._VERSION_IN_CODE,
                                   "PRIOR_X = 'structure-v0.2-draft'"))

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

    def test_this_suite_cannot_reach_the_live_store(self):
        """The mitigation CLAUDE.md documents for suites that exercise
        dangerous machinery: assert the property about the suite itself.
        store.connect with no path argument opens the operator's real
        database, and one future test writing that turns `unittest discover`
        into a mass delete on the live book."""
        import re
        from pathlib import Path
        src = Path(__file__).read_text(encoding="utf-8")
        bare = re.findall(r"store\.connect\(\s*\)", src)
        self.assertEqual([], bare,
                         "a prune test opened the live store — every "
                         "connection here must name an explicit temp path "
                         "or use :memory:")

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
