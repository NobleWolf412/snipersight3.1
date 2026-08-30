"""The second-touch audition, and the properties that keep it honest.

The module answers "what would trading a zone's second and third touches have
earned" for a cohort setups.py structurally never sees (its zone pass keeps
only episode-1 TOUCH facts). Everything here defends the honesty of that
answer: cohort admission is the playbook table itself rather than a copy of
it, the counterfactual bracket is setups' own rules over the same facts,
refusals are counted per gate rather than dropped, the traded episode-1
cohort is never re-counted, and no trading module may consume any of it until
the operator promotes a rule under a new setups version.
"""
import inspect
import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import episodes, execsim, regime, risk, scalein, \
    setups, store, swings, zones


class TargetMirror(unittest.TestCase):
    """episodes.target_level mirrors setups' closure: pools first, swings as
    fallback, everything as-of. A drift here would price the counterfactual
    against a different target than the engine gives a first touch."""

    POOLS = [{"confirmed_at": 100, "side": "HIGH", "level": Decimal(120),
              "pool_id": "p1"},
             {"confirmed_at": 100, "side": "HIGH", "level": Decimal(115),
              "pool_id": "p2"}]
    SWINGS = {"HIGH": [(100, Decimal(140))], "LOW": []}

    def test_the_nearest_unbroken_pool_wins_over_the_swing(self):
        got = episodes.target_level("LONG", Decimal(100), 200, self.POOLS,
                                    {}, self.SWINGS)
        self.assertEqual(got, Decimal(115))

    def test_a_broken_pool_is_not_a_target(self):
        got = episodes.target_level("LONG", Decimal(100), 200, self.POOLS,
                                    {"p2": 150}, self.SWINGS)
        self.assertEqual(got, Decimal(120),
                         "a pool broken before as_of is not a destination")

    def test_a_pool_from_the_future_is_never_consulted(self):
        got = episodes.target_level("LONG", Decimal(100), 50, self.POOLS,
                                    {}, self.SWINGS)
        self.assertIsNone(got, "nothing was knowable at as_of=50")

    def test_swings_are_the_fallback_when_no_pool_is_beyond(self):
        got = episodes.target_level("LONG", Decimal(130), 200, self.POOLS,
                                    {}, self.SWINGS)
        self.assertEqual(got, Decimal(140))


class CohortIsThePlaybookTable(unittest.TestCase):
    """Admission calls setups.playbook — imported, not copied — so the cohort
    cannot drift from the one the first-touch engine trades."""

    def test_trending_regimes_admit_and_transition_does_not(self):
        self.assertEqual(
            setups.playbook("DEMAND", "BULL_TREND", enabled={"PULLBACK"},
                            rev_evidence=[])[:2], ("PULLBACK", "LONG"))
        self.assertEqual(
            setups.playbook("SUPPLY", "WEAKENING_BEAR", enabled={"PULLBACK"},
                            rev_evidence=[])[:2], ("PULLBACK", "SHORT"))
        # TRANSITION is REVERSAL territory, and REVERSAL is not this cohort.
        self.assertIsNone(
            setups.playbook("DEMAND", "TRANSITION", enabled={"PULLBACK"},
                            rev_evidence=["CHOCH"]))
        self.assertIsNone(
            setups.playbook("DEMAND", "BEAR_TREND", enabled={"PULLBACK"},
                            rev_evidence=[]))


class TargetAuthorityPin(unittest.TestCase):
    """The mirror pinned to the AUTHORITY, not to prose.

    `setups.target` is a closure inside `setups.run` and cannot be imported,
    so `episodes.target_level` rebuilds its rule — which makes it a second
    implementation, the exact thing this repo's fill-model history warns
    about. The pin: run the real setups pipeline on a scratch store and
    assert the mirror reproduces the `tp_uncapped` the engine RECORDED on
    its own fact, from the same fact inputs at the same as-of moment. If
    either side's rule moves, this fails on the recorded number rather than
    on anyone's memory of the rule.
    """

    def test_target_level_reproduces_a_recorded_setups_target(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = store.connect(Path(tmp.name) / "t.db")
        self.addCleanup(con.close)
        bars = [(100, 102, 98, 100)] * 20
        bars.append((100, 107, "99.5", 106))         # touch + confirm bar
        bars.append((106, 131, 104, 130))
        bars += [(130, 131, 129, 130)] * 18
        for i, (o, h, lo, c) in enumerate(bars):
            con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("TESTUSDT", "1H", i * 3600, str(o), str(h), str(lo),
                 str(c), "1", "test", i * 3600))
        base = {"zone_id": "z1", "zone_type": "DEMAND", "bottom": "95",
                "top": "100"}
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="zone",
                          market_time=0, confirmed_at=3600,
                          algo_version=zones.ZONE_VERSION,
                          payload={**base, "event": "CREATED",
                                   "state": "FRESH"})
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="zone",
                          market_time=20 * 3600, confirmed_at=21 * 3600,
                          algo_version=zones.ZONE_VERSION,
                          payload={**base, "event": "TOUCH", "episode": 1,
                                   "state": "TOUCHED"})
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                          market_time=0, confirmed_at=3600,
                          algo_version=regime.REGIME_VERSION,
                          payload={"regime": "BULL_TREND"})
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="swing",
                          market_time=0, confirmed_at=3600,
                          algo_version=swings.SWING_VERSION,
                          payload={"tier": "INTERMEDIATE", "type": "HIGH",
                                   "price": "130"})
        con.commit()
        setups.run(con, "TESTUSDT", "1H", 3600)
        validated = [
            {"confirmed_at": r["confirmed_at"], **json.loads(r["payload"])}
            for r in store.get_facts(con, "TESTUSDT", "1H", "setup",
                                     setups.SETUP_VERSION)
            if json.loads(r["payload"]).get("state") == "VALIDATED"]
        self.assertTrue(validated,
                        "the fixture no longer produces a VALIDATED setup — "
                        "the pin has nothing to pin against")
        p = validated[0]
        # The same fact inputs episodes.collect would load: no liquidity
        # pools in this store, one INTERMEDIATE opposing swing.
        tier_swings = {"HIGH": [(3600, Decimal("130"))], "LOW": []}
        got = episodes.target_level(p["direction"], Decimal(p["entry"]),
                                    p["confirmed_at"], [], {}, tier_swings)
        self.assertEqual(got, Decimal(p["tp_uncapped"]),
                         "episodes' target mirror disagrees with the target "
                         "setups' own pipeline recorded on this fact")


class CounterfactualCase(unittest.TestCase):
    """One episode-2 touch walked end to end through the engine's machinery,
    on a constructed store where every number is arithmetic."""

    def _store(self, confirm_bar=(100, 107, "99.5", 106)):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.executescript(store.SCHEMA)
        bars = [(100, 102, 98, 100)] * 20            # ATR warms up at ~4
        o, h, lo, c = confirm_bar
        bars.append((o, h, lo, c))                   # bar 20: the ep-2 touch
        bars.append((106, 131, 104, 130))            # bar 21: fill + target
        bars += [(130, 131, 129, 130)] * 18
        for i, (bo, bh, bl, bc) in enumerate(bars):
            con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("TESTUSDT", "1H", i * 3600, str(bo), str(bh), str(bl),
                 str(bc), "1", "test", i * 3600))
        base = {"zone_id": "z1", "zone_type": "DEMAND", "bottom": "95",
                "top": "100"}
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="zone",
                          market_time=0, confirmed_at=3600,
                          algo_version=zones.ZONE_VERSION,
                          payload={**base, "event": "CREATED",
                                   "state": "FRESH"})
        # Episode 1 is the TRADED cohort — present in the store, and it must
        # never be re-counted here.
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="zone",
                          market_time=16 * 3600, confirmed_at=17 * 3600,
                          algo_version=zones.ZONE_VERSION,
                          payload={**base, "event": "TOUCH", "episode": 1,
                                   "state": "TOUCHED"})
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="zone",
                          market_time=20 * 3600, confirmed_at=21 * 3600,
                          algo_version=zones.ZONE_VERSION,
                          payload={**base, "event": "TOUCH", "episode": 2,
                                   "state": "TESTED"})
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                          market_time=0, confirmed_at=3600,
                          algo_version=regime.REGIME_VERSION,
                          payload={"regime": "BULL_TREND"})
        store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="swing",
                          market_time=0, confirmed_at=3600,
                          algo_version=swings.SWING_VERSION,
                          payload={"tier": "INTERMEDIATE", "type": "HIGH",
                                   "price": "130"})
        con.commit()
        return con

    def test_the_second_touch_is_walked_and_the_first_is_not(self):
        con = self._store()
        try:
            data = episodes.collect(con)
        finally:
            con.close()
        self.assertEqual(len(data["rows"]), 1, data)
        row = data["rows"][0]
        self.assertEqual(row["episode"], 2,
                         "episode 1 is the traded book — re-counting it here "
                         "would be a second authority for its numbers")
        self.assertEqual(row["outcome"], "TP")
        self.assertGreater(row["r"], 0)

    def test_an_unconfirmed_touch_is_a_counted_refusal_not_a_dropped_row(self):
        """A touch bar that never proves the level held (a doji drifting back
        into the zone fails setups.confirms' upper-third test) must land in
        the refusal table — attrition is part of the answer."""
        con = self._store(confirm_bar=(100, 107, "99.5", 101))
        try:
            data = episodes.collect(con)
        finally:
            con.close()
        self.assertEqual(data["rows"], [])
        self.assertEqual(data["refusals"].get("CONFIRMATION_TIMEOUT"), 1)

    def test_a_transition_regime_touch_is_out_of_cohort(self):
        con = self._store()
        try:
            # A LATER regime flip to TRANSITION, confirmed before the ep-2
            # touch, takes the touch out of the playbook's regimes.
            store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                              market_time=18 * 3600, confirmed_at=19 * 3600,
                              algo_version=regime.REGIME_VERSION,
                              payload={"regime": "TRANSITION"})
            con.commit()
            data = episodes.collect(con)
        finally:
            con.close()
        self.assertEqual(data["rows"], [])
        self.assertEqual(data["out_of_cohort"], 1)


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """Evidence is recorded, not filtered on. A passing grade here is a
        versioned setups PROPOSAL for the operator, never an import. (The bare
        word 'episode' is zones vocabulary and appears legitimately in trading
        code; only an import of this module is the defect.)"""
        for mod in (setups, risk, execsim, scalein):
            src = inspect.getsource(mod)
            for form in ("from . import episodes", "from .episodes import",
                         "import engine.episodes", "engine.episodes"):
                self.assertNotIn(form, src,
                                 f"{mod.__name__} must not consume the "
                                 f"audition")

    def test_the_module_writes_nothing(self):
        src = inspect.getsource(episodes)
        self.assertNotIn("insert_fact", src,
                         "the audition wrote a fact — it is no longer "
                         "derived at analysis time")
        self.assertIn("mode=ro", src,
                      "main() must open the store read-only")

    def test_one_execution_authority(self):
        src = inspect.getsource(episodes)
        for shared in ("simulate_entry", "walk_exit", "settle"):
            self.assertIn(shared, src)
        for private in ("def simulate_entry", "def walk_exit", "def settle"):
            self.assertNotIn(private, src,
                             "a private simulation core is how replays drift")

    def test_the_serial_correlation_confession_is_in_the_report(self):
        """Nominal n overstates effective n here by construction; the floor
        the report states must name the clustered interval as the deciding
        one, so a quoted cell cannot shed the caveat."""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.executescript(store.SCHEMA)
        try:
            rep = episodes.grade(con)
        finally:
            con.close()
        self.assertIn("clustered", rep["floor"]["bar"])
        self.assertTrue(rep["derived_at_analysis_time"])


if __name__ == "__main__":
    unittest.main()
