import json
import tempfile
import unittest
from unittest import mock
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import aggregator, importer, quality, setups, store
from engine.runlog import RunRecorder


class QualityStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "quality.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def candle(self, tf, ts, op="100", hi="102", lo="98", cl="101"):
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("BTC-USD", tf, ts, op, hi, lo, cl, "1", "coinbase", ts + 1))

    def complete_market(self):
        for i in range(4):
            self.candle("1H", i * 3600, op=str(100 + i), hi=str(102 + i),
                        lo=str(98 + i), cl=str(101 + i))
        monday = aggregator.MONDAY_EPOCH
        for i in range(7):
            self.candle("1D", monday + i * 86400, op=str(200 + i),
                        hi=str(202 + i), lo=str(198 + i), cl=str(201 + i))
        self.con.commit()
        with patch("engine.aggregator.time.time", return_value=2_000_000):
            aggregator.aggregate(self.con, "BTC-USD", "4H")
            aggregator.aggregate(self.con, "BTC-USD", "1W")


class TestMarketQuality(QualityStoreCase):
    def test_complete_aggregates_reconcile(self):
        self.complete_market()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        self.assertFalse([c for c in checks if c["status"] == "BLOCKED"])

    def test_gap_blocks_downstream_engines(self):
        self.candle("1H", 0)
        self.candle("1H", 7200)
        self.con.commit()
        with self.assertRaises(quality.DataQualityError):
            quality.assert_market_ready(self.con, "BTC-USD", now=100_000)

    def test_retried_empty_tail_does_not_multiply_known_gap_budget(self):
        """A quiet market retries from the same last candle every cycle.

        The 1-gap and later 2-gap log rows describe one expanding window, not
        three venue acknowledgements. Summing them let the duplicate budget
        excuse all three holes in this series; the third must remain visible.
        """
        base = importer.PRE_2000
        self.candle("1H", base)
        self.candle("1H", base + 4 * 3600)
        for end, n_gaps in ((base + 2 * 3600, 1),
                            (base + 3 * 3600, 2)):
            self.con.execute(
                "INSERT INTO import_log (symbol,tf,range_start,range_end,"
                "n_candles,n_gaps,gaps,source,run_at,n_bad) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1H", base, end, 0, n_gaps, "[]",
                 "coinbase", end, 0))
        self.con.commit()
        checks = quality.audit_market_inputs(
            self.con, "BTC-USD", now=base + 6 * 3600)
        self.assertIn("SEQUENCE_GAPS", {c["code"] for c in checks})

    def test_final_candle_does_not_erase_prior_gap_acknowledgements(self):
        base = importer.PRE_2000
        self.candle("1H", base)
        self.candle("1H", base + 3 * 3600)
        rows = [
            (base + 3 * 3600, 0, 2,
             json.dumps([base + 3600, base + 2 * 3600])),
            (base + 4 * 3600, 1, 0, "[]"),
        ]
        for end, n_candles, n_gaps, gaps in rows:
            self.con.execute(
                "INSERT INTO import_log (symbol,tf,range_start,range_end,"
                "n_candles,n_gaps,gaps,source,run_at,n_bad) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1H", base, end, n_candles, n_gaps, gaps,
                 "coinbase", end, 0))
        self.con.commit()
        checks = quality.audit_market_inputs(
            self.con, "BTC-USD", now=base + 5 * 3600)
        self.assertNotIn("SEQUENCE_GAPS", {c["code"] for c in checks})
        self.assertIn("KNOWN_VENUE_GAPS", {c["code"] for c in checks})
        known = next(c for c in checks if c["code"] == "KNOWN_VENUE_GAPS")
        self.assertEqual(known["status"], "PASS",
                         "an accepted venue void is evidence, not degraded health")
        self.assertEqual(known["rung"], "SERVE_FLAG",
                         "the accepted absence must remain visible")

    def test_aggregate_mismatch_is_blocking(self):
        self.complete_market()
        self.con.execute(
            "UPDATE candles SET high='999' WHERE symbol='BTC-USD' AND tf='4H'")
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        self.assertIn("AGGREGATE_MISMATCH", {c["code"] for c in checks})

    def _partial_market(self, *, acknowledged=True, aggregate=True):
        """Three of four hours traded; 02:00 the venue served nothing for.

        range_start sits at importer.PRE_2000 exactly — acknowledgment rows
        starting before 2000 are quarantined as cold-start artefacts, and this
        fixture's candles live near the epoch."""
        from engine import importer
        for i in (0, 1, 3):
            self.candle("1H", i * 3600, op=str(100 + i), hi=str(102 + i),
                        lo=str(98 + i), cl=str(101 + i))
        if acknowledged:
            self.con.execute(
                "INSERT INTO import_log (symbol, tf, range_start, range_end, "
                "n_candles, n_gaps, gaps, source, run_at, n_bad) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1H", importer.PRE_2000, 20000, 3, 1,
                 json.dumps([2 * 3600]), "coinbase", 19999, 0))
        self.con.commit()
        if aggregate:
            with patch("engine.aggregator.time.time", return_value=2_000_000):
                aggregator.aggregate(self.con, "BTC-USD", "4H")

    def test_acknowledged_partial_bar_reconciles(self):
        """agg-v0.2's mirror: a partial bar the aggregator was entitled to
        build is VERIFIED, not skipped. Before this, the mirror ignored every
        partial group — correct while the aggregator refused to build them,
        and a silent verification hole the day it stopped refusing."""
        self._partial_market()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        self.assertFalse([c for c in checks if c["status"] == "BLOCKED"])
        # ...and the bucket counts as verified, so a store whose only closed
        # buckets are qualifying partials is not reported as unverifiable.
        self.assertNotIn("NO_COMPLETE_BUCKETS",
                         {c["code"] for c in checks if c["tf"] == "4H"})

    def test_acknowledged_gap_is_a_note_not_a_warning(self):
        self._partial_market()
        report = quality.audit(self.con, now=20_000)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["warnings"], [])
        self.assertIn("KNOWN_VENUE_GAPS",
                      {c["code"] for c in report["notes"]})

    def test_corrupted_partial_bar_is_blocking(self):
        """A partial bar that does not reconcile to its present source candles
        is corruption, exactly as a complete one is."""
        self._partial_market()
        self.con.execute(
            "UPDATE candles SET high='999' WHERE symbol='BTC-USD' AND tf='4H'")
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        self.assertIn("AGGREGATE_MISMATCH", {c["code"] for c in checks})

    def test_unemitted_partial_bucket_flags_without_blocking(self):
        """A qualifying partial bucket the aggregator has not built yet is a
        DEGRADED flag, never a HALT — ~48 stored symbols sit outside the scan
        universe where nothing ever re-aggregates, and a HALT no scanner pass
        can heal is the watchdog's documented anti-pattern (the
        UNKNOWN_TIMEFRAME restart loop, 2026-08-08)."""
        self._partial_market(aggregate=False)
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        agg = [c for c in checks if c["tf"] == "4H"]
        self.assertIn("AGGREGATE_PENDING", {c["code"] for c in agg})
        self.assertNotIn("MISSING_AGGREGATE", {c["code"] for c in agg})
        self.assertFalse([c for c in agg if c["status"] == "BLOCKED"])

    def test_unknown_timeframe_is_quarantine_not_halt(self):
        """Pin for the 2026-08-08 restart loop. An unrecognised tf may indict
        the AUDITING process rather than the data — this audit reads
        importer.TF_SECONDS from whatever commit its process booted from, and
        a supervisor two days stale reported 27 phantom findings while the
        rows were fine. QUARANTINE never hands the watchdog a restart; HALT
        did, every ~7 minutes, against a scanner that could not heal it."""
        self.candle("7H", 0)
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        unknown = [c for c in checks if c["code"] == "UNKNOWN_TIMEFRAME"]
        self.assertTrue(unknown, "an unrecognised tf must still be reported")
        self.assertEqual({c["rung"] for c in unknown}, {"QUARANTINE"})

    def test_unacknowledged_partial_stays_outside_the_mirror(self):
        """No acknowledgment -> the aggregator refuses the bucket and the
        mirror neither expects a bar nor reports its absence. The missing hour
        itself stays visible where it belongs: as a gap on the 1H series."""
        self._partial_market(acknowledged=False, aggregate=False)
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=2_000_000)
        agg_codes = {c["code"] for c in checks if c["tf"] == "4H"}
        self.assertNotIn("AGGREGATE_PENDING", agg_codes)
        self.assertNotIn("MISSING_AGGREGATE", agg_codes)
        self.assertIn("SEQUENCE_GAPS", {c["code"] for c in checks
                                        if c["tf"] == "1H"})


class TestOnboardingIsNotAFailure(QualityStoreCase):
    def candle_at(self, tf, ts, imported_at):
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("BTC-USD", tf, ts, "100", "102", "98", "101", "1", "coinbase",
             imported_at))

    def test_freshly_imported_history_is_lag_not_missing(self):
        """2026-08-10 13:46: OPUSDT joined the universe, one cycle imported
        months of history, every historical 4H window became complete at
        once, and the bucket-age test alone read all 63 as ancient
        aggregation failures — HALT — killing the scanner seconds before its
        own aggregation pass. Sources imported within the last ~cycle are
        scheduling lag whatever their market_time says."""
        now = 2_000_000
        for i in range(8):                       # two complete 4H windows,
            self.candle_at("1H", i * 3600, now - 60)   # imported a minute ago
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=now)
        agg = [c for c in checks if c["tf"] == "4H"]
        self.assertIn("AGGREGATE_PENDING", {c["code"] for c in agg})
        self.assertNotIn("MISSING_AGGREGATE", {c["code"] for c in agg})
        self.assertFalse([c for c in agg if c["status"] == "BLOCKED"])

    def test_long_unaggregated_history_still_blocks(self):
        # The same shape with STALE imports is a genuine failure: the sources
        # have sat for hours and no aggregation pass picked them up.
        now = 2_000_000
        for i in range(8):
            self.candle_at("1H", i * 3600, now - 7200)  # imported 2h ago
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BTC-USD", now=now)
        self.assertIn("MISSING_AGGREGATE",
                      {c["code"] for c in checks if c["tf"] == "4H"})


class TestPipelineContracts(QualityStoreCase):
    def test_fact_causality_violation_is_visible(self):
        store.insert_fact(self.con, symbol="BTC-USD", tf="1H", kind="test",
                          market_time=100, confirmed_at=99, algo_version="test-v1",
                          payload={"event": "IMPOSSIBLE"})
        self.con.commit()
        report = quality.audit(self.con, now=1000)
        self.assertFalse(report["evaluation_allowed"])
        self.assertIn("CAUSALITY_VIOLATION", {c["code"] for c in report["blockers"]})

    def test_equity_summary_must_reconcile_to_ledger(self):
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="account",
            market_time=10, confirmed_at=10, algo_version="risk-test",
            payload={"start_equity": "10000", "final_equity": "9000",
                     "curve": [{"ts": 10, "equity": "9500"}]})
        self.con.commit()
        report = quality.audit(self.con, now=1000)
        self.assertIn("EQUITY_RECONCILIATION_FAILED",
                      {c["code"] for c in report["blockers"]})

    def test_quality_history_is_persisted(self):
        report = quality.audit(self.con, now=1000, persist=True)
        self.assertIsNotNone(report["quality_run_id"])
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM quality_runs").fetchone()[0], 1)

    def test_run_recorder_carries_lineage_envelope(self):
        with RunRecorder(self.con, "test", "test-v1", "BTC-USD", "1H") as rec:
            rec.n_inputs = 0
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1H", kind="test",
                market_time=1, confirmed_at=2, algo_version="test-v1",
                payload={"event": "ATTRIBUTED"})
        row = self.con.execute(
            "SELECT run_id,status,input_watermark,input_fingerprint,output_fingerprint "
            "FROM engine_runs").fetchone()
        self.assertTrue(row[0])
        self.assertEqual(row[1], "PASS")
        self.assertEqual(len(row[3]), 64)
        self.assertEqual(len(row[4]), 64)
        producer = self.con.execute(
            "SELECT producer_run_id FROM facts WHERE kind='test'").fetchone()[0]
        self.assertEqual(producer, row[0])

    def test_lineage_ignores_history_and_intentional_operational_facts(self):
        store.start_baseline(self.con, started_at=100, label="test")
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="test",
            market_time=40, confirmed_at=50, algo_version="old-v1",
            payload={"event": "PRE_BASELINE"})
        store.insert_fact(
            self.con, symbol="SYSTEM", tf="ALL", kind="alert",
            market_time=200, confirmed_at=200, algo_version="alert-v1",
            payload={"event": "OPERATOR_NOTE"})
        self.con.commit()
        report = quality.audit(self.con, now=300)
        self.assertNotIn(
            "UNATTRIBUTED_CURRENT_FACTS",
            {c["code"] for c in report["blockers"] + report["warnings"]})

    def test_current_automated_fact_without_producer_run_blocks(self):
        store.start_baseline(self.con, started_at=100, label="test")
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="test",
            market_time=150, confirmed_at=200, algo_version="test-v1",
            payload={"event": "CURRENT_WITHOUT_RUN"})
        self.con.commit()
        report = quality.audit(self.con, now=300)
        findings = [c for c in report["blockers"]
                    if c["code"] == "UNATTRIBUTED_CURRENT_FACTS"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rung"], "HALT")


class TestKillSwitchRungs(QualityStoreCase):
    """Every _issue() code declares its watchdog dispatch rung. This coverage
    test guards against a new finding being added to quality.py without a
    matching CODE_RUNG entry — the fallback in _rung_for is a safety net, not
    a substitute for the declaration."""

    def test_code_rung_is_the_watchdog_dispatch_table(self):
        # AST-walk the module and pull the CODE argument (4th positional) from
        # every _issue() call. A regex-based version of this test was a no-op
        # because it captured the FIRST quoted literal, which is the stage
        # (Auditor FIND-1, 2026-07-26). The IfExp branch handles calls where
        # the code is written as `"X" if cond else "Y"` (Auditor NR-1).
        import ast

        def _literal_strings(node: ast.AST) -> set[str]:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return {node.value}
            if isinstance(node, ast.IfExp):
                return _literal_strings(node.body) | _literal_strings(node.orelse)
            return set()

        with open(quality.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        codes: set[str] = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_issue"
                    and len(node.args) >= 4):
                codes |= _literal_strings(node.args[3])
        # sanity: the AST walk actually found calls (guard against future refactor)
        self.assertGreater(len(codes), 10,
                           "AST walk found too few _issue codes — did _issue rename?")
        missing = codes - set(quality.CODE_RUNG)
        self.assertFalse(missing, f"codes without CODE_RUNG entry: {sorted(missing)}")
        # every mapped rung is one of the five ladder rungs
        self.assertTrue(set(quality.CODE_RUNG.values()) <= set(quality.RUNGS))

    def test_stale_series_routes_to_quarantine_not_halt(self):
        # A per-symbol/tf staleness must degrade, not halt the whole pipeline —
        # the room's Contrarian was explicit: freezing on one late bar is worse
        # than the disease.
        self.candle("1H", 0)
        self.con.commit()
        report = quality.audit(self.con, now=1_000_000)
        stale = [c for c in report["warnings"] if c["code"] == "STALE_SERIES"]
        self.assertTrue(stale, "expected a STALE_SERIES warning")
        self.assertEqual(stale[0]["rung"], "QUARANTINE")

    def test_halt_codes_carry_halt_rung(self):
        # An OHLC invariant break is cardiac — it must reach rung HALT so the
        # watchdog restarts live.
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("BTC-USD", "1H", 0, "100", "50", "60", "70", "1", "coinbase", 1))
        self.con.commit()
        report = quality.audit(self.con, now=100_000)
        codes = {c["code"]: c["rung"] for c in report["blockers"]}
        self.assertEqual(codes.get("OHLC_INVARIANT_FAILURE"), "HALT")
        self.assertEqual(report["worst_rung"], "HALT")

    def test_persisted_checks_include_rung_column(self):
        report = quality.audit(self.con, now=1000, persist=True)
        self.assertIsNotNone(report["quality_run_id"])
        columns = {r[1] for r in self.con.execute(
            "PRAGMA table_info(quality_checks)").fetchall()}
        self.assertIn("rung", columns)


class TestStrategyRulesRemainFrozen(unittest.TestCase):
    def test_observability_did_not_change_strategy_constants(self):
        self.assertEqual(setups.MIN_RR, Decimal("1.5"))
        self.assertEqual(setups.GOOD_RR, Decimal("2.5"))
        self.assertEqual(setups.SL_ATR, Decimal("0.25"))
        self.assertEqual(setups.SWEEP_LOOKBACK_BARS, 10)
        self.assertEqual(setups.MIN_RISK_COST_MULT, Decimal(2))


if __name__ == "__main__":
    unittest.main()


class RetiredSymbolStalenessTest(unittest.TestCase):
    """Staleness is only meaningful for a symbol we still track.

    Switching the universe to perps retired 108 spot symbols and produced 108
    permanent STALE_SERIES warnings — noise that would bury the one series
    going quiet while it actually mattered. Same cry-wolf failure as the 1,364
    blockers that wedged the scanner for days.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "stale.db")
        # two symbols, both with old candles: one live, one retired
        for sym in ("LIVEUSDT", "OLD-USD"):
            for i in range(3):
                self.con.execute(
                    "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sym, "1D", 86400 * i, "100", "102", "98", "100", "1",
                     "coinbase", 86400 * i + 1))
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _stale_symbols(self):
        rep = quality.audit_market_inputs(self.con, now=10 ** 9)
        return {c["symbol"] for c in rep if c["code"] == "STALE_SERIES"}

    def test_retired_symbol_is_not_reported_stale(self):
        with mock.patch("engine.universe.current_symbols",
                        return_value=["LIVEUSDT"]):
            stale = self._stale_symbols()
        self.assertIn("LIVEUSDT", stale, "a live stale series must still warn")
        self.assertNotIn("OLD-USD", stale, "retired data reported as stale")

    def test_fails_open_when_the_universe_is_unreadable(self):
        """If we cannot tell what is live, warn rather than silently suppress."""
        with mock.patch("engine.universe.current_symbols",
                        side_effect=RuntimeError("no universe")):
            stale = self._stale_symbols()
        self.assertIn("LIVEUSDT", stale)
        self.assertIn("OLD-USD", stale)

    def test_live_set_is_not_shared_across_connections(self):
        """A module-level cache keyed on nothing would let an audit of one
        database suppress warnings in another."""
        self.assertFalse(hasattr(quality, "_LIVE_CACHE"))
