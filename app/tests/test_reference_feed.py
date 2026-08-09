"""The reference feed's one law: analysis may borrow the deep venue's series,
money may not.

Phases 1-2 of the 2026-08-09 scoping. A thin market's candles under-describe
it, so venues.REFERENCE points analysis at the deepest venue's series, stored
under '@'-keys — and everything that sizes, fills or settles must be unable to
reach those series even by accident. The enforcement is a raise, not a
convention, and these tests pin the raise.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import basis, binance, importer, quality, store, universe, venues


class RefStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "ref.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def candle(self, symbol, tf, ts, close="100", source="coinbase"):
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            (symbol, tf, ts, "100", "102", "98", close, "1", source, ts + 1))


class TestReferenceContract(unittest.TestCase):
    def test_every_mapped_symbol_yields_a_key_no_venue_will_size(self):
        """The load-bearing property. If venue_for ever LEARNS to resolve a
        reference key, sizing, liquidation and the participation cap can read
        a book the operator does not trade on."""
        for sym in venues.REFERENCE:
            rkey = venues.ref_key(sym)
            self.assertIn("@", rkey)
            self.assertNotEqual(rkey, sym,
                "a reference key colliding with a trading symbol would let "
                "INSERT OR REPLACE overwrite the execution venue's candles")
            with self.assertRaises(ValueError):
                venues.venue_for(rkey)

    def test_reference_for_is_absent_not_guessed(self):
        # IMU-USD is genuinely unmapped — Binance does not list it (probed
        # 2026-08-09). Absence must read as None, never as a guessed spelling.
        self.assertIsNone(venues.reference_for("IMU-USD"))
        with self.assertRaises(ValueError):
            venues.ref_key("IMU-USD")

    def test_trading_symbols_still_resolve(self):
        # The '@' guard must not have widened: every real symbol class resolves.
        self.assertEqual(venues.venue_for("BICO-USD").key, "coinbase-spot")
        self.assertEqual(venues.venue_for("BTCUSDT").key, "phemex-perp")
        self.assertEqual(venues.venue_for("PF_XBTUSD").key, "kraken-perp")

    def test_the_key_names_its_own_source(self):
        # importer.backfill derives `source` from the key's tail — the two
        # cannot drift because they are one string.
        venue_key, native = venues.REFERENCE["BICO-USD"]
        self.assertEqual(venues.ref_key("BICO-USD"), f"{native}@{venue_key}")


class TestImporterRouting(RefStoreCase):
    def test_reference_key_routes_to_binance_with_truthful_source(self):
        rows = [{"open_ts": 0, "open": "1", "high": "2", "low": "0.5",
                 "close": "1.5", "volume": "10"}]
        with patch("engine.importer.binance.fetch_candles",
                   return_value=rows) as fc, \
             patch("engine.importer.time.time", return_value=10000):
            r = importer.backfill(self.con, "BICOUSDT@binance-spot", "1H",
                                  0, 3600)
        self.assertEqual(fc.call_args[0][0], "BICOUSDT",
            "the adapter must be asked for the venue's own spelling, "
            "not the '@'-key")
        self.assertEqual(r["candles"], 1)
        src = self.con.execute(
            "SELECT source FROM candles WHERE symbol=?",
            ("BICOUSDT@binance-spot",)).fetchone()[0]
        self.assertEqual(src, "binance-spot")

    def test_venue_unknown_fallback_is_loud(self):
        """The silent half of the old fallback is what would have imported
        garbage under an honest-looking label. It survives, but it speaks."""
        with patch("engine.importer._fetch", return_value=[]), \
             patch("engine.importer.time.time", return_value=10000), \
             patch("engine.importer.time.sleep"), \
             patch("engine.runlog.get_logger") as gl:
            importer.backfill(self.con, "WEIRD/SYM", "1H", 0, 3600)
        warned = " ".join(str(c) for c in gl.return_value.warning.call_args_list)
        self.assertIn("no venue contract", warned)


class TestBinanceNormalisation(unittest.TestCase):
    def test_aggregate_timeframes_are_refused_not_served(self):
        # The venue serves 4H natively and this adapter must refuse it — a
        # natively-fetched aggregate occupying the aggregator's row is the
        # two-writers defect. The refusal is code, not a comment.
        with self.assertRaises(ValueError):
            binance.fetch_candles("BTCUSDT", "4H", 0, 86400)
        with self.assertRaises(ValueError):
            binance.fetch_candles("BTCUSDT", "1W", 0, 86400)

    def test_milliseconds_become_seconds_and_forming_is_dropped(self):
        # [openTime ms, o, h, l, c, v, closeTime, ...] — prices as strings.
        raw = [[3600_000, "1.0", "2.0", "0.5", "1.5", "10", 0],
               [7200_000, "1.5", "2.5", "1.0", "2.0", "20", 0]]
        with patch("engine.binance._get", return_value=raw), \
             patch("engine.binance.time.time", return_value=7200):
            out = binance.fetch_candles("BICOUSDT", "1H", 0, 86400)
        # the 7200 bar's bucket has not closed at now=7200 — never emitted
        self.assertEqual([c["open_ts"] for c in out], [3600])
        self.assertEqual(out[0]["close"], "1.5")


class TestQualityDemotion(RefStoreCase):
    def test_reference_findings_cannot_block_or_halt(self):
        """A hole behind the reference watermark is the unhealable-HALT shape
        from 2026-08-08: forward-only import never refetches it, so a BLOCKED
        finding would wedge the evaluation gate or restart-loop the scanner —
        over a series nothing trades on."""
        rkey = "BICOUSDT@binance-spot"
        self.candle(rkey, "1H", 0, source="binance-spot")
        self.candle(rkey, "1H", 7200, source="binance-spot")   # gap at 3600
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, rkey, now=100_000)
        ours = [c for c in checks if c["symbol"] == rkey]
        self.assertTrue(ours, "the series must still be audited at all")
        for c in ours:
            self.assertNotEqual(c["status"], "BLOCKED", c)
            self.assertNotEqual(c["rung"], "HALT", c)
        self.assertIn("REFERENCE_SEQUENCE_GAPS", {c["code"] for c in ours},
            "the finding must survive under its own name, not vanish")

    def test_trading_symbols_still_block(self):
        # The demotion must be scoped to '@'-keys — the same gap on a real
        # symbol keeps its teeth.
        self.candle("BICO-USD", "1H", 0)
        self.candle("BICO-USD", "1H", 7200)
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, "BICO-USD", now=100_000)
        self.assertIn("BLOCKED", {c["status"] for c in checks})

    def test_every_reference_code_has_an_explicit_rung(self):
        # quality.py's own rule: no implicit CODE_RUNG mapping. The demotion
        # prefixes codes mechanically, so each reachable prefixed code must be
        # declared — and declared as QUARANTINE, nothing higher.
        for code, rung in quality.CODE_RUNG.items():
            if code.startswith("REFERENCE_"):
                self.assertEqual(rung, "QUARANTINE", code)


class TestReferenceSilenceIsLoud(RefStoreCase):
    def test_a_dead_reference_feed_is_reported_not_silent(self):
        """The failure this feed will actually have: Binance delists the
        symbol, every later import serves nothing, backfill returns
        candles=0 gaps=0 — and without this check the basis stream ends in
        total silence while grading accumulates a sample that stopped.
        STALE_SERIES structurally cannot fire here (reference keys are never
        universe members), so the reference branch owns it."""
        rkey = "BICOUSDT@binance-spot"
        self.candle(rkey, "1H", 0, source="binance-spot")
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, rkey, now=100_000)
        stale = [c for c in checks if c["code"] == "REFERENCE_STALE_SERIES"]
        self.assertTrue(stale, "a feed dead for 27 hours said nothing")
        self.assertEqual(stale[0]["status"], "DEGRADED")
        self.assertEqual(stale[0]["rung"], "QUARANTINE")

    def test_fresh_reference_feed_is_not_nagged(self):
        rkey = "BICOUSDT@binance-spot"
        self.candle(rkey, "1H", 96_000, source="binance-spot")
        self.con.commit()
        checks = quality.audit_market_inputs(self.con, rkey, now=100_000)
        self.assertNotIn("REFERENCE_STALE_SERIES", {c["code"] for c in checks})


class TestAuditLevelDemotion(RefStoreCase):
    def test_fact_level_findings_on_a_reference_key_cannot_block(self):
        """Facts on an '@'-key are themselves a bug (nothing should write
        them), and the invariant is about the REPORT: that bug must surface
        as QUARANTINE findings, not as a wedged evaluation gate. The
        market-input demotion runs too early to see fact-level issuers, so
        audit() repeats it over the full list."""
        rkey = "BICOUSDT@binance-spot"
        self.candle(rkey, "1H", 96_000, source="binance-spot")
        store.insert_fact(self.con, symbol=rkey, tf="1H", kind="test",
                          market_time=100, confirmed_at=99,   # impossible
                          algo_version="test-v1", payload={"event": "X"})
        self.con.commit()
        report = quality.audit(self.con, symbol=rkey, now=100_000)
        self.assertFalse([c for c in report["blockers"]
                          if c["symbol"] == rkey],
                         "a reference-key finding reached BLOCKED")
        self.assertIn("REFERENCE_CAUSALITY_VIOLATION",
                      {c["code"] for c in report["warnings"]})


class TestUniverseFallback(RefStoreCase):
    def test_cold_store_fallback_excludes_reference_keys(self):
        self.candle("BICO-USD", "1D", 0)
        self.candle("BICOUSDT@binance-spot", "1D", 0, source="binance-spot")
        self.con.commit()
        syms = universe.current_symbols(self.con)
        self.assertIn("BICO-USD", syms)
        self.assertNotIn("BICOUSDT@binance-spot", syms,
            "an unsizeable key leaked into the TRADEABLE set on the cold-"
            "store path — refusal-at-sizing is a fault, not a filter")


class TestBasisEngine(RefStoreCase):
    def _pair(self, ts, exec_close, ref_close):
        self.candle("BICO-USD", "1H", ts, close=exec_close)
        if ref_close is not None:
            self.candle("BICOUSDT@binance-spot", "1H", ts, close=ref_close,
                        source="binance-spot")

    def test_records_the_spread_and_only_where_both_closed(self):
        self._pair(0, "0.0700", "0.0693")
        self._pair(3600, "0.0710", None)          # thin venue traded, deep did not…
        self._pair(7200, "0.0720", "0.0720")
        self.con.commit()
        r = basis.run(self.con, "BICO-USD", "1H", 3600)
        self.assertEqual(r["facts"], 2, "absence must stay absence, never zero")
        rows = self.con.execute(
            "SELECT market_time, confirmed_at, payload FROM facts "
            "WHERE kind='basis' ORDER BY market_time").fetchall()
        p0 = json.loads(rows[0][2])
        self.assertEqual(p0["basis"], "0.0007")
        self.assertEqual(p0["exec_close"], "0.0700")
        self.assertEqual(p0["ref_source"], "binance-spot")
        self.assertEqual(p0["ref_quote"], "USDT")
        # knowability: the reading exists at the bar's close, not before
        self.assertEqual(rows[0][1], rows[0][0] + 3600)
        # Decimal-as-text end to end — a float would print differently
        self.assertNotIn("e", p0["basis_pct"].lower())

    def test_idempotent_and_late_reference_bars_backfill(self):
        self._pair(0, "0.07", "0.069")
        self.con.commit()
        self.assertEqual(basis.run(self.con, "BICO-USD", "1H", 3600)["facts"], 1)
        self.assertEqual(basis.run(self.con, "BICO-USD", "1H", 3600)["facts"], 0,
                         "re-run over identical data must be a no-op")
        # the deep venue serves an older bar late — the fact appears on the
        # next pass with the content it would always have had
        self.candle("BICOUSDT@binance-spot", "1H", 3600, close="0.07",
                    source="binance-spot")
        self.candle("BICO-USD", "1H", 3600, close="0.071")
        self.con.commit()
        self.assertEqual(basis.run(self.con, "BICO-USD", "1H", 3600)["facts"], 1)

    def test_silent_for_unmapped_symbols_and_other_tfs(self):
        # ETHUSDT is mapped since the 2026-08-09 widening, so it passes the
        # reference gate — but this store holds no candles for it, so zero
        # facts is still the required answer (absence is never zero). IMU-USD
        # pins the truly-unmapped branch.
        self.assertEqual(basis.run(self.con, "IMU-USD", "1H", 3600)["facts"], 0)
        self.assertEqual(basis.run(self.con, "ETHUSDT", "1H", 3600)["facts"], 0)
        self.assertEqual(basis.run(self.con, "BICO-USD", "15m", 900)["facts"], 0)

    def test_facts_key_on_the_trading_symbol(self):
        self._pair(0, "0.07", "0.069")
        self.con.commit()
        basis.run(self.con, "BICO-USD", "1H", 3600)
        syms = {r[0] for r in self.con.execute(
            "SELECT DISTINCT symbol FROM facts WHERE kind='basis'")}
        self.assertEqual(syms, {"BICO-USD"},
            "the reading is about the market the operator trades; the "
            "reference key is plumbing and stays inside the payload")


class TestMoneyPathsNeverReachTheReference(unittest.TestCase):
    def test_no_trading_engine_touches_reference_plumbing(self):
        """Source-level pin, same style as the JS suites: the trading tail
        must not name the reference machinery at all. The runtime guard is
        venue_for's raise; this catches the day someone starts threading a
        reference series INTO sizing or fills, before it runs."""
        import inspect
        from engine import execsim, risk, scalein, setups
        for mod in (execsim, risk, scalein, setups):
            src = inspect.getsource(mod)
            for name in ("ref_key", "reference_for", "is_reference_key",
                         "REFERENCE", "binance"):
                self.assertNotIn(name, src,
                    f"{mod.__name__} references {name} — analysis may borrow "
                    f"the deep venue's series, money may not")


if __name__ == "__main__":
    unittest.main()
