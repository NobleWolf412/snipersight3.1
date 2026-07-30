"""Re-entry control — the asymmetry is the whole design, so it is pinned hard.

Nothing stopped this system from buying a level again the bar after it stopped
out. Tolerable while REVERSAL fired 5 times in four years; not once it fires 471.
"""
import json
import tempfile
import unittest
from pathlib import Path

from engine import cooldowns, store


class Durations(unittest.TestCase):
    def test_a_stop_out_locks_out_far_longer_than_a_target(self):
        """The asymmetry, stated directly. A stop-out means the level was
        INVALIDATED; a target means it RESOLVED. One number for both necessarily
        gets one of the two cases wrong, and most bots use one number."""
        for tf in ("15m", "1H", "1D"):
            with self.subTest(tf=tf):
                self.assertGreater(cooldowns.duration_hours("SL", tf),
                                   cooldowns.duration_hours("TP", tf) * 4)

    def test_lockout_scales_with_horizon(self):
        """A scalper expects several stop-outs a session; silencing a 15m symbol
        for a day over one would delete the strategy, not protect it."""
        self.assertLess(cooldowns.duration_hours("SL", "15m"),
                        cooldowns.duration_hours("SL", "1D"))

    def test_trail_and_time_exits_count_as_resolved_not_invalidated(self):
        for outcome in ("TP", "TIMEOUT", "TIME"):
            self.assertEqual(cooldowns.duration_hours(outcome, "1H"),
                             cooldowns.RESOLVED_HOURS["intraday"], outcome)


class Scope(unittest.TestCase):
    def test_long_and_short_cool_down_independently(self):
        """Being stopped out of a long says nothing about a short."""
        self.assertNotEqual(cooldowns.key("BTCUSDT", "LONG"),
                            cooldowns.key("BTCUSDT", "SHORT"))

    def test_a_cooldown_does_not_leak_across_symbols(self):
        self.assertNotEqual(cooldowns.key("BTCUSDT", "LONG"),
                            cooldowns.key("ETHUSDT", "LONG"))


class PointInTime(unittest.TestCase):
    """Every verdict is against a caller-supplied `as_of`. A cooldown that read
    the clock would lock out different trades on a replay than it did live,
    which would make the forward record unreproducible."""

    def setUp(self):
        self.t = 1_700_000_000
        self.facts = [{
            "key": "BTCUSDT|LONG", "symbol": "BTCUSDT", "direction": "LONG",
            "market_time": self.t, "expires_at": self.t + 4 * 3600,
            "outcome": "SL", "hours": 4.0}]

    def test_blocked_inside_the_window(self):
        self.assertIsNotNone(cooldowns.blocked_at(
            self.facts, self.t + 3600, "BTCUSDT", "LONG"))

    def test_not_blocked_before_the_exit_that_caused_it(self):
        """No lookahead: a cooldown cannot block a trade that happened before
        the exit which created it."""
        self.assertIsNone(cooldowns.blocked_at(
            self.facts, self.t - 1, "BTCUSDT", "LONG"))

    def test_not_blocked_after_expiry(self):
        self.assertIsNone(cooldowns.blocked_at(
            self.facts, self.t + 4 * 3600, "BTCUSDT", "LONG"))

    def test_the_longest_overlapping_lockout_wins(self):
        """A later stop-out must never be shortened by an earlier take-profit
        that happens to fire after it."""
        facts = self.facts + [{
            "key": "BTCUSDT|LONG", "symbol": "BTCUSDT", "direction": "LONG",
            "market_time": self.t + 60, "expires_at": self.t + 600,
            "outcome": "TP", "hours": 0.5}]
        got = cooldowns.blocked_at(facts, self.t + 700, "BTCUSDT", "LONG")
        self.assertIsNotNone(got, "the short TP window must not end the SL lockout")
        self.assertEqual(got["outcome"], "SL")

    def test_the_blocking_fact_is_returned_not_a_bare_boolean(self):
        """A rejection must be as auditable as an approval — the operator has to
        be able to see WHICH exit caused the lockout."""
        got = cooldowns.blocked_at(self.facts, self.t + 60, "BTCUSDT", "LONG")
        self.assertEqual(got["outcome"], "SL")
        self.assertIn("hours", got)


class Derivation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _exec(self, outcome, ts, direction="LONG", sid="S1"):
        from engine.execsim import EXEC_VERSION
        store.insert_fact(self.con, symbol="BTCUSDT", tf="1H", kind="exec",
                          market_time=ts, confirmed_at=ts,
                          algo_version=EXEC_VERSION,
                          payload={"setup_id": sid, "outcome": outcome,
                                   "direction": direction, "r_multiple": "-1"})
        self.con.commit()

    def test_cooldowns_are_derived_from_exits_not_held_as_live_state(self):
        self._exec("SL", 1_700_000_000)
        cooldowns.run(self.con, "BTCUSDT", "1H", 3600)
        facts = cooldowns.load(self.con)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["outcome"], "SL")
        self.assertTrue(facts[0]["invalidating"])

    def test_a_missed_order_creates_no_cooldown(self):
        """No position was taken, so no level was tested. Cooling down on a miss
        would silence a symbol for a trade that never happened."""
        self._exec("MISSED", 1_700_000_000)
        cooldowns.run(self.con, "BTCUSDT", "1H", 3600)
        self.assertEqual(cooldowns.load(self.con), [])

    def test_rerunning_writes_zero_new_facts(self):
        self._exec("SL", 1_700_000_000)
        first = cooldowns.run(self.con, "BTCUSDT", "1H", 3600)["cooldowns"]
        second = cooldowns.run(self.con, "BTCUSDT", "1H", 3600)["cooldowns"]
        self.assertEqual(first, 1)
        self.assertEqual(second, 0, "cooldown derivation must be idempotent")

    def test_the_cooldown_starts_at_the_EXIT_not_at_run_time(self):
        """Stamping it with wall-clock would make a replay lock out different
        trades than the live pass did."""
        exit_ts = 1_700_000_000
        self._exec("SL", exit_ts)
        cooldowns.run(self.con, "BTCUSDT", "1H", 3600)
        f = cooldowns.load(self.con)[0]
        self.assertEqual(f["market_time"], exit_ts)
        self.assertEqual(f["expires_at"],
                         exit_ts + int(cooldowns.duration_hours("SL", "1H") * 3600))


class RiskIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_risk_refuses_a_cooled_down_entry_and_says_why(self):
        from unittest import mock

        from engine import execsim, risk, setups
        base = store.start_baseline(self.con, label="cd",
                                    strategy_version=setups.SETUP_VERSION,
                                    execution_version=execsim.EXEC_VERSION,
                                    risk_version=risk.RISK_VERSION)
        t0 = base["started_at"]
        # risk.run iterates symbols that have 1D candles — without these the
        # portfolio pass has nothing to walk and the test would pass vacuously.
        for i in range(3):
            self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                             ("BTCUSDT", "1D", t0 + i * 86400, "100", "102",
                              "98", "100", "1", "phemex-perp", t0))
        # a stop-out at t0, then a fresh LONG intent one hour later
        store.insert_fact(self.con, symbol="BTCUSDT", tf="1H", kind="cooldown",
                          market_time=t0, confirmed_at=t0,
                          algo_version=cooldowns.COOLDOWN_VERSION,
                          payload={"event": "COOLDOWN", "key": "BTCUSDT|LONG",
                                   "symbol": "BTCUSDT", "direction": "LONG",
                                   "tf": "1H", "horizon": "intraday",
                                   "outcome": "SL", "invalidating": True,
                                   "hours": 12.0, "market_time": t0,
                                   "expires_at": t0 + 12 * 3600,
                                   "setup_id": "OLD", "reason": "test"})
        store.insert_fact(self.con, symbol="BTCUSDT", tf="1H", kind="setup",
                          market_time=t0 + 3600, confirmed_at=t0 + 3600,
                          algo_version=setups.SETUP_VERSION,
                          payload={"setup_id": "NEW", "state": "VALIDATED",
                                   "direction": "LONG", "strategy": "PULLBACK",
                                   "entry": "100", "sl": "90", "tp": "130",
                                   "rr": "3", "rank": 50, "why": "t"})
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        decisions = [json.loads(r[0]) for r in self.con.execute(
            "SELECT payload FROM facts WHERE kind='risk'").fetchall()]
        blocked = [d for d in decisions
                   if any("COOLDOWN" in x for x in (d.get("reasons") or []))]
        self.assertTrue(blocked, "a cooled-down symbol must not be re-entered")
        self.assertEqual(blocked[0]["decision"], "REJECTED")
        self.assertIn("SL", blocked[0]["reasons"][0],
                      "the reason must name the exit that caused the lockout")
        self.assertEqual(blocked[0]["risk_usd"], "0",
                         "a refused entry must consume no exposure budget")


if __name__ == "__main__":
    unittest.main()
