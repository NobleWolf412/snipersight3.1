"""Trend slice is an AUDITION, and these are the properties that keep it one.

The module answers "which volatility-state x ladder-alignment cell of the
continuation cohort earns" without creating a filter. Everything here defends
the honesty of that answer: the primary cell is fixed in code rather than in
prose, the canonical state comes from market_context's one fold rather than a
private second mapping, both slices are read as-of the setup's confirmed_at,
floors refuse verdicts rather than shrinking intervals, and no trading module
may consume any of it until the operator promotes a policy under a new
version.
"""
import inspect
import json
import sqlite3
import unittest

from engine import (execsim, regime, risk, scalein, setups, store, trend,
                    trendslice, volatility)


class PreRegistration(unittest.TestCase):
    """The primary cell is code, not prose — a test can hold it still."""

    def test_the_primary_cell_is_expansion_or_breakout_with(self):
        self.assertTrue(trendslice.is_primary("EXPANSION", "WITH"))
        self.assertTrue(trendslice.is_primary("BREAKOUT", "WITH"))

    def test_everything_else_is_exploratory(self):
        """A moving-market state with the ladder AGAINST, or an agreeing
        ladder in a quiet market, is not the registered prediction — counting
        it as primary after the fact would be the multiple-comparisons cheat
        the docstring promises not to make."""
        self.assertFalse(trendslice.is_primary("EXPANSION", "AGAINST"))
        self.assertFalse(trendslice.is_primary("COMPRESSION", "WITH"))
        self.assertFalse(trendslice.is_primary("BULL_TREND", "WITH"))
        self.assertFalse(trendslice.is_primary(None, None))


class Floors(unittest.TestCase):
    @staticmethod
    def _rows(n_symbols, per, r=1.0):
        return [{"symbol": f"S{i}", "r": r}
                for i in range(n_symbols) for _ in range(per)]

    def test_below_the_cluster_floor_counts_are_reported_and_no_verdict(self):
        """Four symbols' worth of trades is four observations however many
        rows it holds — the cell keeps its counts (those are facts) and
        refuses the interval (a verdict needs floors)."""
        c = trendslice.cell(self._rows(4, 10), resamples=200)
        self.assertEqual(c["n"], 40)
        self.assertFalse(c["sample_ok"])
        self.assertIsNone(c["cluster_ci_lo"])
        self.assertFalse(c["clears_zero"])

    def test_above_the_floors_a_uniform_win_clears_zero(self):
        c = trendslice.cell(self._rows(10, 3), resamples=200)
        self.assertTrue(c["sample_ok"])
        self.assertGreater(c["cluster_ci_lo"], 0)
        self.assertTrue(c["clears_zero"])

    def test_an_empty_cell_is_zero_not_a_crash(self):
        self.assertEqual(trendslice.cell([], resamples=200),
                         {"n": 0, "sample_ok": False})


class AnnotationCase(unittest.TestCase):
    """One replayed trade through the real store path, both slices stamped."""

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        for i, (o, h, lo, c) in enumerate(
                [(100, 102, 98, 100)] * 3          # history
                + [(100, 101, 98, 100)]            # order bar: maker fills @99
                + [(100, 121, 99, 120)]            # target bar
                + [(120, 121, 119, 120)] * 3):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("TESTUSDT", "1H", i * 3600, str(o), str(h), str(lo), str(c),
                 "1", "test", i * 3600))
        store.insert_fact(
            self.con, symbol="TESTUSDT", tf="1H", kind="setup",
            market_time=2 * 3600, confirmed_at=3 * 3600,
            algo_version=trend.TREND_VERSION,
            payload={"setup_id": f"TESTUSDT|1H|TREND_CONTINUATION|7200|"
                                 f"{trend.TREND_VERSION}",
                     "state": "VALIDATED", "strategy": "TREND_CONTINUATION",
                     "direction": "LONG", "entry": "100", "sl": "90",
                     "tp": "120", "entry_model": "MAKER_THEN_MARKET",
                     "maker_limit": "99", "maker_wait_bars": 2})
        # The rung above 1H is 4H: a BULL_TREND there, confirmed before the
        # setup, makes the ladder composite UP and a LONG trade WITH.
        store.insert_fact(
            self.con, symbol="TESTUSDT", tf="4H", kind="regime",
            market_time=0, confirmed_at=3600,
            algo_version=regime.REGIME_VERSION,
            payload={"regime": "BULL_TREND"})
        # Squeeze ON as-of the setup: market_context folds that to COMPRESSION.
        store.insert_fact(
            self.con, symbol="TESTUSDT", tf="1H", kind="volatility",
            market_time=0, confirmed_at=3600,
            algo_version=volatility.VOLATILITY_VERSION,
            payload={"event": "SQUEEZE", "squeeze": "ON"})
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_the_replayed_trade_carries_both_slices(self):
        data = trendslice.collect(self.con, symbols=["TESTUSDT"], tfs=("1H",))
        self.assertEqual(len(data["rows"]), 1, data)
        row = data["rows"][0]
        self.assertEqual(row["alignment"], "WITH")
        self.assertEqual(row["state"], "COMPRESSION",
                         "the state must be market_context's fold, not a "
                         "private second mapping")
        self.assertGreater(float(row["r"]), 0)

    def test_a_rung_reading_from_the_future_is_never_consulted(self):
        """Convention 3: the ladder is read at the setup's confirmed_at. A
        BEAR_TREND confirming on the rung AFTER the trade was decided must not
        flip the alignment the gate would actually have seen."""
        store.insert_fact(
            self.con, symbol="TESTUSDT", tf="4H", kind="regime",
            market_time=18000, confirmed_at=20000,
            algo_version=regime.REGIME_VERSION,
            payload={"regime": "BEAR_TREND"})
        self.con.commit()
        data = trendslice.collect(self.con, symbols=["TESTUSDT"], tfs=("1H",))
        self.assertEqual(data["rows"][0]["alignment"], "WITH")


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """Evidence is recorded, not filtered on. A passing grade here is a
        versioned policy PROPOSAL for the operator, never an import."""
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("trendslice", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")

    def test_the_module_writes_nothing(self):
        src = inspect.getsource(trendslice)
        self.assertNotIn("insert_fact", src,
                         "the audition wrote a fact — it is no longer "
                         "derived at analysis time")
        self.assertIn("mode=ro", src,
                      "main() must open the store read-only")

    def test_one_authority_for_the_canonical_state(self):
        """The state must come from market_context.snapshot — a second fold of
        the same volatility facts is the fill-model drift disease. The module
        may not query volatility facts itself."""
        src = inspect.getsource(trendslice)
        self.assertIn("market_context.snapshot", src)
        for private_read in ('"volatility"', "'volatility'",
                             '"SQUEEZE"', "'SQUEEZE'"):
            self.assertNotIn(private_read, src,
                             "trendslice re-derives the volatility state — "
                             "market_context owns that fold")

    def test_one_execution_authority(self):
        """Outcomes come from abtest.run_variant (itself pinned to execsim by
        test_abtest); a private simulation core is how replays drift."""
        src = inspect.getsource(trendslice)
        self.assertIn("run_variant", src)
        for private in ("def simulate_entry", "def walk_exit", "def settle",
                        "def _simulate"):
            self.assertNotIn(private, src)


if __name__ == "__main__":
    unittest.main()
