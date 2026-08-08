"""Operator settings: audited, correctly classed, and honest about baselines."""
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from engine import settings, store


class SettingsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "s.db")
        store.start_baseline(self.con, label="test", strategy_version="s",
                             execution_version="e", risk_version="r")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _baselines(self):
        return self.con.execute("SELECT COUNT(*) FROM research_baselines").fetchone()[0]

    def test_defaults_when_nothing_set(self):
        self.assertEqual(settings.all_settings(self.con), settings.defaults())

    def test_change_is_persisted_and_logged(self):
        settings.set_many(self.con, {"top_n": 35}, note="wider")
        self.assertEqual(settings.get(self.con, "top_n"), 35)
        h = settings.history(self.con)
        self.assertEqual(h[0]["name"], "top_n")
        self.assertEqual(h[0]["from"], 20)
        self.assertEqual(h[0]["to"], 35)
        self.assertEqual(h[0]["note"], "wider")

    def test_behavioural_change_starts_a_new_baseline(self):
        """A record spanning two configs cannot say which produced which result."""
        before = self._baselines()
        r = settings.set_many(self.con, {"top_n": 35})
        self.assertEqual(r["behavioural"], ["top_n"])
        self.assertIsNotNone(r["baseline"])
        self.assertEqual(self._baselines(), before + 1)

    def test_halt_is_operational_and_must_not_reset_the_baseline(self):
        """Halting is how the operator stays safe. If it destroyed the forward
        record, the safety control would punish the caution it exists to allow."""
        before = self._baselines()
        r = settings.set_many(self.con, {"halted": True})
        self.assertEqual(r["behavioural"], [], "halt must not be behavioural")
        self.assertIsNone(r["baseline"])
        self.assertEqual(self._baselines(), before, "halt reset the baseline")
        self.assertTrue(settings.get(self.con, "halted"))

    def test_halt_and_resume_are_both_audited(self):
        settings.set_many(self.con, {"halted": True}, note="market open")
        settings.set_many(self.con, {"halted": False}, note="resumed")
        names = [h["name"] for h in settings.history(self.con)]
        self.assertEqual(names.count("halted"), 2)
        self.assertEqual(self._baselines(), 1)

    def test_no_op_change_is_not_logged(self):
        settings.set_many(self.con, {"top_n": 20})       # already the default
        self.assertEqual(settings.history(self.con), [])
        self.assertEqual(self._baselines(), 1, "a no-op must not reset anything")

    def test_unknown_setting_is_refused(self):
        with self.assertRaises(ValueError):
            settings.set_many(self.con, {"make_me_rich": True})

    def test_bool_coercion_from_json_and_strings(self):
        settings.set_many(self.con, {"enable_perps": False})
        self.assertIs(settings.get(self.con, "enable_perps"), False)
        settings.set_many(self.con, {"enable_perps": "true"})
        self.assertIs(settings.get(self.con, "enable_perps"), True)

    def test_corrupt_row_falls_back_to_default_rather_than_crashing(self):
        settings._ensure(self.con)
        self.con.execute("INSERT INTO settings (name,value,updated_at) VALUES (?,?,?)",
                         ("top_n", "{not json", 0))
        self.con.commit()
        self.assertEqual(settings.get(self.con, "top_n"), 20)

    def test_every_setting_is_classified(self):
        for name, spec in settings.SPEC.items():
            self.assertIn(spec[0], ("BEHAVIOURAL", "OPERATIONAL", "PREFERENCE"), name)


if __name__ == "__main__":
    unittest.main()


class DrawdownGuardTest(unittest.TestCase):
    """The total-drawdown halt: the guardrail the daily halt cannot provide.

    A daily limit catches a bad DAY. It does not catch a slow bleed — a run of
    small losses can drain the account without any single day breaching -6%.
    """

    def test_drawdown_limit_is_operational_not_behavioural(self):
        """Tightening a guardrail must not reset the forward record, or the
        operator is penalised for becoming more careful."""
        self.assertEqual(settings.SPEC["max_drawdown_pct"][0], "OPERATIONAL")
        self.assertEqual(settings.SPEC["halt_on_data_blocked"][0], "OPERATIONAL")

    def test_drawdown_default_is_a_real_limit(self):
        pct = settings.SPEC["max_drawdown_pct"][2]
        self.assertGreater(pct, 0)
        self.assertLess(pct, 100, "a 100% limit is not a limit")


class DrawdownHaltTest(unittest.TestCase):
    """Drive the risk authority to an actual drawdown halt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "dd.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_halt_trips_and_blocks_later_entries(self):
        import json as _json
        from engine import risk, setups, execsim

        base = store.start_baseline(
            self.con, label="dd", strategy_version=setups.SETUP_VERSION,
            execution_version=execsim.EXEC_VERSION, risk_version=risk.RISK_VERSION)
        settings.set_many(self.con, {"max_drawdown_pct": 5.0})

        # Facts must land AFTER the baseline start or risk.run filters them out
        # as pre-window history — the same scoping that (correctly) excluded the
        # 87 imported perp setups from the live record.
        day = 86400
        t0 = base["started_at"]
        for i in range(28):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", "1D", t0 + day * i, "100", "102", "98", "100", "1",
                 "coinbase", t0 + day * i + 1))

        # Consecutive full stop-outs at 0.25% risk: no single UTC account day
        # breaches the 1% daily halt, but the cumulative book exceeds 5%.
        for i in range(24):
            sid = f"S{i}"
            ts = t0 + day * (i + 1)
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1D", kind="setup",
                market_time=ts, confirmed_at=ts,
                algo_version=setups.SETUP_VERSION,
                payload={"setup_id": sid, "state": "VALIDATED", "direction": "LONG",
                         "strategy": "PULLBACK", "entry": "100", "sl": "90",
                         "tp": "130", "rr": "3", "rank": 50, "why": "t"})
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1D", kind="exec",
                market_time=ts + 3600, confirmed_at=ts + 3600,
                algo_version=execsim.EXEC_VERSION,
                payload={"setup_id": sid, "outcome": "SL", "r_multiple": "-1"})
        self.con.commit()

        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)

        halts = [r for r in self.con.execute(
            "SELECT payload FROM facts WHERE kind='risk'").fetchall()
            if _json.loads(r[0]).get("event") == "DRAWDOWN_HALT"]
        self.assertTrue(halts, "drawdown halt never fired")

        decisions = [_json.loads(r[0]) for r in self.con.execute(
            "SELECT payload FROM facts WHERE kind='risk'").fetchall()
            if _json.loads(r[0]).get("event") == "DECISION"]
        blocked = [d for d in decisions
                   if any("DRAWDOWN_HALT" in x for x in (d.get("reasons") or []))]
        self.assertTrue(blocked, "entries continued after the halt tripped")
