import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import costs, execsim, marketdata, risk, setups, store, telemetry, universe, zones


def candle(con, symbol, tf, ts, o, h, lo, c, volume="10"):
    con.execute(
        "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
        (symbol, tf, ts, str(o), str(h), str(lo), str(c), volume,
         "coinbase", ts + 60))


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.con = store.connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class TestManifestsAndCosts(TempStore):
    def test_manifest_is_content_addressed_and_idempotent(self):
        payload = {"version": "x", "rate": "0.01"}
        a = store.record_manifest(self.con, "strategy", payload)
        b = store.record_manifest(self.con, "strategy", payload)
        self.assertEqual(a, b)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM manifests").fetchone()[0], 1)
        self.assertEqual(store.get_manifest(self.con, a)["version"], "x")

    def test_conservative_round_trip_cost_uses_maker_and_taker(self):
        p = costs.DEFAULT_COST_PROFILE
        got = costs.estimated_round_trip_cost(Decimal("100"), Decimal("10"), p)
        self.assertEqual(got, Decimal("1.50"))

    def test_legacy_import_log_is_migrated_once(self):
        legacy = Path(self.tmp.name) / "legacy.db"
        con = sqlite3.connect(legacy)
        con.execute("CREATE TABLE import_log (id INTEGER PRIMARY KEY)")
        con.commit();con.close()
        migrated = store.connect(legacy)
        try:
            columns = {r[1] for r in migrated.execute(
                "PRAGMA table_info(import_log)").fetchall()}
            versions = [r[0] for r in migrated.execute(
                "SELECT version FROM schema_migrations ORDER BY version").fetchall()]
            self.assertIn("n_bad", columns)
            # Repinned 4 Aug 2026 when migration 7 landed. The list used to be
            # hardcoded, which made every future schema change break a test
            # about something else. The PROPERTY is unchanged and is what the
            # name promises: every migration ran, each recorded exactly ONCE,
            # contiguous from 1.
            self.assertEqual(versions, sorted(set(versions)),
                             "a migration was recorded twice")
            self.assertEqual(versions, list(range(1, len(versions) + 1)),
                             "migration versions are not contiguous from 1")
            self.assertGreaterEqual(len(versions), 6)
        finally:
            migrated.close()


class TestStrategyGuards(unittest.TestCase):
    def test_transition_requires_real_evidence_not_regime_alone(self):
        """The property this has always protected: TRANSITION must not trade on
        regime alone.

        The THRESHOLD moved in S50 and the trades did not. v0.7 demanded 2 of
        {CHOCH, SWEEP, VOLUME, STRENGTH} — but STRENGTH cannot be false
        (`zones.strength` floors at 77 against a gate of 60), so it was present
        on 985 of 985 setups and "2 of 4" was really "1 of 3". The gate now says
        that: 1 of {CHOCH, SWEEP, VOLUME}, with STRENGTH still recorded on the
        fact but not counted. Proven equivalent over all 8 reachable inputs.

        This test previously asserted that a lone SWEEP was refused. It never
        was — the real engine always also had STRENGTH on the same zone, so it
        passed. The assertion described a rule the engine did not follow.
        """
        # regime alone, no evidence at all: refused, and that is the invariant
        self.assertIsNone(setups.playbook("DEMAND", "TRANSITION", swept=False))
        self.assertIsNone(setups.playbook("DEMAND", "TRANSITION", rev_evidence=[]))
        # STRENGTH alone is NOT evidence — it is the component that cannot fail
        self.assertIsNone(
            setups.playbook("DEMAND", "TRANSITION", rev_evidence=["STRENGTH"]),
            "STRENGTH is structurally always-true; on its own it must not "
            "clear the bar, or the gate is unconditional")
        # any ONE real component: a play, in the direction the zone implies
        for ev in (["CHOCH"], ["SWEEP"], ["VOLUME"]):
            self.assertEqual(
                setups.playbook("DEMAND", "TRANSITION", rev_evidence=ev)[:2],
                ("REVERSAL", "LONG"), f"{ev} should clear the bar")
        self.assertEqual(
            setups.playbook("SUPPLY", "TRANSITION",
                            rev_evidence=["SWEEP", "STRENGTH"])[:2],
            ("REVERSAL", "SHORT"))

    def test_strength_is_recorded_but_never_counted(self):
        """It stays on the fact so a grader can measure it later; it just does
        not gate. House rule: evidence is recorded, not filtered on — a factor
        must be graded before it can gate, and this one has now been graded."""
        self.assertNotIn("STRENGTH", setups.REVERSAL_COMPONENTS)
        self.assertIn("STRENGTH", setups.REVERSAL_RECORDED_COMPONENTS)
        ev = setups.reversal_evidence(choch_recent=False, swept=False,
                                      vol_ratio=None, zone_strength=95)
        self.assertEqual(ev, ["STRENGTH"], "still reported on the fact")
        self.assertIsNone(setups.playbook("DEMAND", "TRANSITION", rev_evidence=ev),
                          "but it must not, by itself, produce a trade")

    def test_the_new_gate_takes_exactly_the_same_trades_as_the_old_one(self):
        """S50 equivalence proof, kept as a test rather than a claim.

        OLD: len(components incl. STRENGTH) >= 2, where STRENGTH is always
        present. NEW: len(components excl. STRENGTH) >= 1. Enumerated over
        every reachable combination — the two agree on all 8.
        """
        import itertools
        real = ("CHOCH", "SWEEP", "VOLUME")
        for r in range(len(real) + 1):
            for combo in itertools.combinations(real, r):
                ev = list(combo) + ["STRENGTH"]     # STRENGTH always fires
                old = len(ev) >= 2
                new = setups.playbook("DEMAND", "TRANSITION",
                                      rev_evidence=ev) is not None
                self.assertEqual(old, new,
                                 f"{combo}: old={old} new={new} — the change "
                                 f"was supposed to alter no trades")

    def test_reversal_evidence_reads_each_component_independently(self):
        ev = setups.reversal_evidence(
            choch_recent=True, swept=False,
            vol_ratio=setups.REVERSAL_VOL_RATIO,
            zone_strength=setups.REVERSAL_MIN_ZONE_STRENGTH)
        self.assertEqual(set(ev), {"CHOCH", "VOLUME", "STRENGTH"})
        # a component that is absent must not be invented, and a malformed
        # volume reading must not be counted as present
        self.assertEqual(
            setups.reversal_evidence(choch_recent=False, swept=False,
                                     vol_ratio=None, zone_strength=None), [])
        self.assertNotIn("VOLUME", setups.reversal_evidence(
            choch_recent=False, swept=False, vol_ratio="not-a-number",
            zone_strength=None))
        # strictly below either threshold does not count
        self.assertEqual(
            setups.reversal_evidence(
                choch_recent=False, swept=False,
                vol_ratio=setups.REVERSAL_VOL_RATIO - Decimal("0.01"),
                zone_strength=setups.REVERSAL_MIN_ZONE_STRENGTH - 1), [])

    def test_zone_freshness_decays_instead_of_rising(self):
        self.assertGreater(zones.freshness(0, 0), zones.freshness(1, 0))
        self.assertGreater(zones.freshness(1, 0), zones.freshness(2, 0))
        self.assertEqual(zones.freshness(0, 0, broken=True), 0)


class TestRejectionFacts(TempStore):
    def test_no_playbook_is_recorded_not_silently_dropped(self):
        for i in range(20):
            candle(self.con, "BTC-USD", "1H", i * 3600, 100, 102, 98, 100)
        base = {"zone_id": "z1", "zone_type": "DEMAND",
                "bottom": "95", "top": "100", "anchor_swing_ts": 0,
                "cluster_members": 0, "strength": 80}
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="zone",
            market_time=0, confirmed_at=3600, algo_version=zones.ZONE_VERSION,
            payload={**base, "event": "CREATED", "state": "FRESH"})
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="zone",
            market_time=15 * 3600, confirmed_at=16 * 3600,
            algo_version=zones.ZONE_VERSION,
            payload={**base, "event": "TOUCH", "state": "TOUCHED", "episode": 1})
        result = setups.run(self.con, "BTC-USD", "1H", 3600)
        self.assertEqual(result["rejected"], 1)
        rows = store.get_facts(
            self.con, "BTC-USD", "1H", "setup_rejection", setups.SETUP_VERSION)
        self.assertEqual(json.loads(rows[0]["payload"])["reason"],
                         "NO_ELIGIBLE_PLAYBOOK")


class TestPointInTimeUniverse(TempStore):
    def test_non_seed_is_ineligible_before_first_snapshot(self):
        self.assertTrue(universe.admitted_at(self.con, "BTC-USD", 10))
        self.assertFalse(universe.admitted_at(self.con, "SOL-USD", 10))

    def test_snapshot_controls_eligibility(self):
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="universe",
            market_time=100, confirmed_at=100, algo_version=universe.UNIVERSE_VERSION,
            payload={"members": [{"symbol": "SOL-USD", "state": "ADMITTED"}]})
        self.assertFalse(universe.admitted_at(self.con, "SOL-USD", 99))
        self.assertTrue(universe.admitted_at(self.con, "SOL-USD", 100))

    def test_ranker_accounts_for_failed_product_stats(self):
        products = [
            {"id": "BTC-USD", "quote_currency": "USD", "status": "online"},
            {"id": "SOL-USD", "quote_currency": "USD", "status": "online"},
        ]

        def fake_get(path):
            if path == "/products":
                return products
            if "SOL" in path:
                raise TimeoutError()
            return {"last": "100", "volume": "2"}

        with patch.object(universe, "_get", side_effect=fake_get):
            ranked = universe.rank_by_volume()
        self.assertEqual(ranked, [("BTC-USD", 200.0)])
        self.assertEqual(universe.LAST_RANK_HEALTH["failed"], 1)


class TestExecutionRealism(TempStore):
    def _setup(self, direction="LONG", entry="100", sl="95", tp="105"):
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="setup",
            market_time=0, confirmed_at=3600, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "s1", "strategy": "PULLBACK",
                     "direction": direction, "entry": entry, "sl": sl, "tp": tp,
                     "rr": "1", "rank": 50, "state": "VALIDATED"})

    def test_order_cannot_fill_before_signal_is_available(self):
        candle(self.con, "BTC-USD", "1H", 0, 100, 110, 90, 100)
        candle(self.con, "BTC-USD", "1H", 3600, 101, 104, 99, 102)
        candle(self.con, "BTC-USD", "1H", 7200, 102, 106, 101, 105)
        self._setup()
        execsim.run(self.con, "BTC-USD", "1H", 3600)
        row = store.get_facts(
            self.con, "BTC-USD", "1H", "exec", execsim.EXEC_VERSION)[0]
        p = json.loads(row["payload"])
        self.assertEqual(p["fill_ts"], 7200)
        self.assertEqual(p["bars_to_fill"], 0)

    def test_unrevisited_limit_becomes_missed(self):
        candle(self.con, "BTC-USD", "1H", 0, 100, 110, 90, 100)
        for i in range(1, 6):
            candle(self.con, "BTC-USD", "1H", i * 3600, 110, 112, 108, 111)
        self._setup()
        execsim.run(self.con, "BTC-USD", "1H", 3600)
        p = json.loads(store.get_facts(
            self.con, "BTC-USD", "1H", "exec", execsim.EXEC_VERSION)[0]["payload"])
        self.assertEqual(p["outcome"], "MISSED")
        self.assertIsNone(p["fill_ts"])


class TestRiskVenueContract(TempStore):
    def test_forward_baseline_excludes_old_loss_without_deleting_it(self):
        candle(self.con, "BTC-USD", "1D", 0, 100, 101, 99, 100)
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="setup",
            market_time=10, confirmed_at=20, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "old-loss", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                     "rr": "2", "rank": 50, "state": "VALIDATED"})
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="exec",
            market_time=10, confirmed_at=30, algo_version=execsim.EXEC_VERSION,
            payload={"setup_id": "old-loss", "strategy": "PULLBACK",
                     "outcome": "SL", "r_multiple": "-1.1"})
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        first = store.start_baseline(self.con, started_at=100)
        second = store.start_baseline(self.con, started_at=200)
        result = risk.run(self.con)

        self.assertEqual(result["final_equity"], "10000")
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM facts WHERE kind IN ('setup','exec')").fetchone()[0], 2)
        self.assertGreater(self.con.execute(
            "SELECT COUNT(*) FROM facts").fetchone()[0], before)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(store.get_active_baseline(self.con)["id"], second["id"])
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM research_baselines WHERE active=1").fetchone()[0], 1)

    def test_short_is_rejected_for_coinbase_spot_and_has_zero_risk(self):
        candle(self.con, "BTC-USD", "1D", 0, 100, 101, 99, 100)
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="setup",
            market_time=0, confirmed_at=86400, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "short", "strategy": "PULLBACK",
                     "direction": "SHORT", "entry": "100", "sl": "105", "tp": "90",
                     "rr": "2", "rank": 50, "state": "VALIDATED"})
        risk.run(self.con)
        rows = store.get_facts(self.con, "BTC-USD", "1D", "risk", risk.RISK_VERSION)
        p = json.loads(rows[0]["payload"])
        self.assertEqual(p["decision"], "REJECTED")
        self.assertEqual(p["risk_usd"], "0")
        self.assertIn("SHORT_UNSUPPORTED_COINBASE_SPOT", p["reasons"])
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        second = risk.run(self.con)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(second["REJECTED"], 1)

    def test_daily_halt_uses_start_of_day_equity(self):
        candle(self.con, "BTC-USD", "1D", 0, 100, 101, 99, 100)
        day = 86400
        # The halt is 4R of paper's 2% R (8% of day-start equity, $800 here).
        # Four 1.10R losses compound to ~$851 > $800, so the day halts and
        # the fifth intent must be rejected. The margin is the 0.10R excess
        # per loss — four flat -1.00R losses would sit exactly AT the limit.
        for i in range(5):
            sid = f"long-{i}"
            confirmed = day + 100 + i * 1000
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1D", kind="setup",
                market_time=i, confirmed_at=confirmed,
                algo_version=setups.SETUP_VERSION,
                payload={"setup_id": sid, "strategy": "PULLBACK",
                         "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                         "rr": "2", "rank": 50, "state": "VALIDATED"})
            if i < 4:
                store.insert_fact(
                    self.con, symbol="BTC-USD", tf="1D", kind="exec",
                    market_time=i, confirmed_at=confirmed + 500,
                    algo_version=execsim.EXEC_VERSION,
                    payload={"setup_id": sid, "outcome": "SL", "r_multiple": "-1.10"})
        risk.run(self.con)
        decisions = [json.loads(r["payload"]) for r in store.get_facts(
            self.con, "BTC-USD", "1D", "risk", risk.RISK_VERSION)]
        self.assertEqual(decisions[-1]["decision"], "REJECTED")
        self.assertIn("DAILY_LOSS_HALT", decisions[-1]["reasons"])
        kills = [json.loads(r["payload"]) for r in store.get_facts(
            self.con, "PORTFOLIO", "ALL", "risk", risk.RISK_VERSION)]
        self.assertEqual(kills[0]["day_start_equity"], "10000")


class TestTickerEndpoint(TempStore):
    def test_ticker_returns_typed_status(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"price":"123.45","time":"now"}'

        result = marketdata.fetch_tickers(
            ["BTC-USD"], opener=lambda *args, **kwargs: Response())
        self.assertEqual(result["BTC-USD"]["price"], 123.45)
        self.assertEqual(result["BTC-USD"]["status"], "OK")


class TestFactLifecycleOrdering(TempStore):
    def test_order_events_are_returned_in_causal_order(self):
        base = {"setup_id": "s1", "side": "LONG", "order_type": "LIMIT",
                "limit_price": "100", "available_at": 100}
        store.insert_fact(self.con, symbol="BTC-USD", tf="1H", kind="order",
                          market_time=50, confirmed_at=100,
                          algo_version=execsim.EXEC_VERSION,
                          payload={**base, "event": "PLACED"})
        store.insert_fact(self.con, symbol="BTC-USD", tf="1H", kind="order",
                          market_time=50, confirmed_at=200,
                          algo_version=execsim.EXEC_VERSION,
                          payload={**base, "event": "FILLED"})
        events = [json.loads(r["payload"])["event"] for r in store.get_facts(
            self.con, "BTC-USD", "1H", "order", execsim.EXEC_VERSION)]
        self.assertEqual(events, ["PLACED", "FILLED"])


class TestCockpitHierarchy(unittest.TestCase):
    """The account must be readable from anywhere, and the things that can stop
    trading must always be reachable.

    Retargeted from the legacy cockpit (retired 2026-07-29) to the shell. The
    property is unchanged: equity, the forward window, and the halt are
    persistent landmarks rather than something you navigate to find.
    """

    def setUp(self):
        static = Path(__file__).parents[1] / "static"
        self.html = (static / "shell.html").read_text(encoding="utf-8")
        self.js = (static / "shell.js").read_text(encoding="utf-8")

    def test_equity_is_visible_from_every_surface(self):
        """It lives in the topbar, outside any <section class="surface">, so
        the operator never has to navigate away to see what the risk % is a
        percentage OF."""
        self.assertIn('id="equityChip"', self.html)
        self.assertLess(self.html.index('id="equityChip"'),
                        self.html.index('<main class="stage">'))

    def test_halt_is_always_reachable(self):
        self.assertIn('id="btnHalt"', self.html)
        self.assertLess(self.html.index('id="btnHalt"'),
                        self.html.index('<main class="stage">'))
        self.assertIn("btnHalt", self.js)

    def test_forward_window_and_positions_are_surfaced(self):
        """`id="sbBaseline"` was the status bar's baseline DATE. It is gone on
        purpose: the bar answered three questions nobody asked (fact-store row
        count, engine build, window start date) on the only strip that is on
        screen no matter which surface you are on, and it now answers the one
        that matters — whether what you are looking at is current.

        The property this test defends is unchanged and is in fact better
        served than it was: the forward window is still named, by the chip on
        the equity curve, and POSITIONS are surfaced by the Mission Briefs
        rail — an open trade used to be reachable only through the chart of
        the symbol it was on.

        Re-pinned: `#positions` is gone. It was an 'Engaged - detail' panel
        rendering the same active_positions and pending_orders the rail
        already carried, on the same surface, in a different shape. `#deck`
        IS the open-trade surface now, and it is already in this list, so the
        property is still covered by the anchor above."""
        for anchor in ('id="baselineChip"', 'id="deck"',
                       'id="rEquity"', 'id="rDD"'):
            self.assertIn(anchor, self.html, anchor)

    def test_open_risk_is_shown_against_its_ceiling(self):
        """A risk number without its cap beside it cannot be acted on: "$195 at
        risk" says nothing about whether another trade fits. The caps were
        enforced from day one and displayed nowhere, which is what made a
        REDUCED verdict read as arbitrary."""
        self.assertIn('id="budgetPanel"', self.html)
        self.assertIn('id="budget"', self.html)
        self.assertIn("renderRiskBudget", self.js)
        # the binding constraint is named, not left to be inferred from bars
        self.assertIn("no slots free", self.js)
        self.assertIn("halted for today", self.js)

    def test_guardrails_and_telemetry_have_a_home(self):
        self.assertIn('id="guardRows"', self.html)
        self.assertIn('id="dTelemetry"', self.html)

    def test_scanner_state_is_persistent_chrome(self):
        self.assertIn('id="scanChip"', self.html)
        self.assertLess(self.html.index('id="scanChip"'),
                        self.html.index('<main class="stage">'))


class TestSetupTelemetry(unittest.TestCase):
    def setUp(self):
        self.setup = {"setup_id": "s1", "symbol": "BTC-USD", "tf": "1D",
                      "entry": "100", "sl": "95", "tp": "110", "rr": "2",
                      "why": "trend plus demand zone"}

    def test_record_exposes_entry_geometry_and_reason(self):
        row = telemetry.build_record(self.setup)
        self.assertEqual(row["stop_distance"], 5)
        self.assertEqual(row["reward_distance"], 10)
        self.assertEqual(row["computed_rr"], 2)
        self.assertEqual(row["why"], "trend plus demand zone")

    def test_risk_rejection_is_owned_by_portfolio(self):
        row = telemetry.build_record(
            self.setup, {"decision": "REJECTED", "reasons": ["EXPOSURE_LIMIT"]})
        self.assertEqual(row["failure_code"], "RISK_REJECTED")
        self.assertEqual(row["failure_owner"], "PORTFOLIO")

    def test_expected_risk_rejection_is_not_a_system_defect(self):
        row = telemetry.build_record(
            self.setup,
            {"decision": "REJECTED",
             "reasons": ["NOT_IN_POINT_IN_TIME_UNIVERSE"]})
        self.assertEqual(row["classification"], "EXPECTED_ATTRITION")
        self.assertEqual(row["defect_count"], 0)

    def test_known_parameterised_risk_limit_has_catalog_evidence(self):
        row = telemetry.build_record(
            self.setup,
            {"decision": "REDUCED",
             "reasons": ["PARTICIPATION_CAP(0.5%_of_24h)"]})
        self.assertEqual(row["defect_count"], 0)
        self.assertNotIn("rule_catalog_entry", row["missing_evidence"])

    def test_known_data_gate_rejection_has_catalog_evidence(self):
        row = telemetry.build_record(
            self.setup,
            {"decision": "REJECTED", "reasons": ["DATA_HEALTH_BLOCKED"]})
        self.assertEqual(row["defect_count"], 0)
        self.assertNotIn("rule_catalog_entry", row["missing_evidence"])

    def test_unfilled_limit_is_execution_failure(self):
        row = telemetry.build_record(
            self.setup, {"decision": "APPROVED"}, {"event": "MISSED"})
        self.assertEqual(row["failure_code"], "ENTRY_NOT_FILLED")
        self.assertEqual(row["failure_owner"], "EXECUTION")

    def test_stop_is_distinct_from_cost_failure(self):
        stopped = telemetry.build_record(
            self.setup, execution={"outcome": "SL", "r_multiple": "-1.2"})
        costly = telemetry.build_record(
            self.setup, execution={"outcome": "TP", "r_multiple": "-0.1",
                                   "r_gross": "0.4"})
        self.assertEqual(stopped["failure_code"], "STOP_LOSS")
        self.assertEqual(costly["failure_code"], "COSTS_ERASED_EDGE")


if __name__ == "__main__":
    unittest.main()
