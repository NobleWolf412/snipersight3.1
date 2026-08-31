"""Context grade is an AUDITION, and these are the properties that keep it one.

The module grades market_context's canonical states against the closed live
book. Everything here defends the honesty of that grade: the state is read
as-of the ENTRY decision (a state computed at exit time would grade hindsight
under the entry's name), MISSED orders never enter the outcome table, a state
below the floor reports counts and no mean, the near-constant flag catches the
S50 stuck-value signature before an outcome column gets read, and no trading
module may consume any of it — deleting the module must change no trade.
"""
import inspect
import sqlite3
import unittest

from engine import (contextgrade, execsim, regime, risk, scalein, setups,
                    store)


def _scratch():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(store.SCHEMA)
    # One closed candle ending exactly at the entry decision time, so the
    # snapshot's data_status is HEALTHY and the canonical state is the base
    # regime rather than UNSTABLE.
    con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("TESTUSDT", "1H", 3600, "100", "102", "98", "100", "1",
                 "test", 3600))
    return con


def _trade(con, sid="TESTUSDT|1H|PULLBACK|z1|" + setups.SETUP_VERSION,
           outcome="TP", r="1.5", entry_at=7200, exit_at=10800):
    store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="setup",
                      market_time=entry_at - 3600, confirmed_at=entry_at,
                      algo_version=setups.SETUP_VERSION,
                      payload={"setup_id": sid, "state": "VALIDATED",
                               "strategy": "PULLBACK", "direction": "LONG",
                               "entry": "100", "sl": "90", "tp": "120"})
    store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="exec",
                      market_time=entry_at - 3600, confirmed_at=exit_at,
                      algo_version=execsim.EXEC_VERSION,
                      payload={"setup_id": sid, "outcome": outcome,
                               "r_multiple": r,
                               "exit_price": None if outcome == "MISSED"
                               else "120"})


class AsOfDiscipline(unittest.TestCase):
    def test_the_state_is_the_entry_decisions_not_the_exits(self):
        """A RANGE label at entry and a BULL_TREND label confirmed between
        entry and exit: the trade must be graded under RANGE. Reading the exit
        moment's state would let the trade's own move relabel it."""
        con = _scratch()
        try:
            store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                              market_time=0, confirmed_at=3600,
                              algo_version=regime.REGIME_VERSION,
                              payload={"regime": "RANGE"})
            store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                              market_time=8000, confirmed_at=9000,
                              algo_version=regime.REGIME_VERSION,
                              payload={"regime": "BULL_TREND"})
            _trade(con)
            con.commit()
            rep = contextgrade.grade(con)
        finally:
            con.close()
        self.assertEqual(rep["closed_trades"], 1)
        self.assertIn("RANGE", rep["cells"])
        self.assertNotIn("BULL_TREND", rep["cells"],
                         "the state was read after the entry decision")

    def test_a_missed_order_never_enters_the_outcome_table(self):
        """A MISSED row has no realised R; counting its recorded '0' would
        dilute every state toward zero with rows where no money moved."""
        con = _scratch()
        try:
            store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                              market_time=0, confirmed_at=3600,
                              algo_version=regime.REGIME_VERSION,
                              payload={"regime": "RANGE"})
            _trade(con)
            _trade(con, sid="TESTUSDT|1H|PULLBACK|z2|" + setups.SETUP_VERSION,
                   outcome="MISSED", r="0")
            con.commit()
            rep = contextgrade.grade(con)
        finally:
            con.close()
        self.assertEqual(rep["candidates"], 2)
        self.assertEqual(rep["closed_trades"], 1)


class FloorsAndFireRate(unittest.TestCase):
    @staticmethod
    def _rows(n, symbols=10, r=1.0):
        return [{"r": r, "symbol": f"S{i % symbols}",
                 "t": 1_700_000_000 + i * 86400} for i in range(n)]

    def test_below_the_floor_counts_are_facts_and_the_mean_is_withheld(self):
        c = contextgrade._cell(self._rows(5))
        self.assertEqual(c, {"n": 5, "sample_ok": False},
                         "a mean over five trades would read as measurement")

    def test_above_the_floor_the_clustered_interval_decides(self):
        c = contextgrade._cell(self._rows(40))
        self.assertTrue(c["sample_ok"])
        self.assertEqual(c["mean_r"], 1.0)
        self.assertTrue(c["clears_zero"])

    def test_a_near_constant_state_is_flagged(self):
        """The S50 signature: a factor stuck on one value predicts nothing,
        and its minority states can never reach a floor. The flag has to fire
        BEFORE anyone reads the outcome table."""
        con = _scratch()
        try:
            store.insert_fact(con, symbol="TESTUSDT", tf="1H", kind="regime",
                              market_time=0, confirmed_at=3600,
                              algo_version=regime.REGIME_VERSION,
                              payload={"regime": "RANGE"})
            for i in range(3):
                _trade(con, sid=f"TESTUSDT|1H|PULLBACK|z{i}|"
                                + setups.SETUP_VERSION)
            con.commit()
            rep = contextgrade.grade(con)
        finally:
            con.close()
        self.assertTrue(rep["fire"]["near_constant"])
        self.assertEqual(rep["fire"]["state_shares"], {"RANGE": 1.0})


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """The litmus is literal: deleting this module must change no trade."""
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("contextgrade", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")

    def test_the_module_writes_nothing(self):
        src = inspect.getsource(contextgrade)
        self.assertNotIn("insert_fact", src,
                         "the audition wrote a fact — it is no longer "
                         "derived at analysis time")
        self.assertIn("mode=ro", src,
                      "main() must open the store read-only")

    def test_one_authority_for_the_state_and_the_join(self):
        """The state comes from market_context.snapshot and the closed book
        from factorstats.load_candidates — the module issues no SQL of its
        own, so it cannot quietly become a second reader of either."""
        src = inspect.getsource(contextgrade)
        self.assertIn("market_context.snapshot", src)
        self.assertIn("load_candidates", src)
        self.assertNotIn("SELECT", src)


if __name__ == "__main__":
    unittest.main()
