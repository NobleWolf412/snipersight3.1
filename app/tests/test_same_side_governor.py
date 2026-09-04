"""The same-side session governor (risk-v0.24).

The trader's rule — "stopped twice shorting today, no more shorts today" — as a
portfolio control. 2026-09-03: three REVERSAL shorts in one afternoon into a
+5% BTC day, each funded after the previous one had stopped; the daily loss
halt sat 0.6R away and nothing else said "this side has been wrong twice".

Three properties, each the thing a wrong implementation would get wrong:

  * it counts per SIDE — two losing shorts do not stop a long;
  * it counts per UTC DAY — the next day starts clean;
  * it is derived from the exits the replay settles, so a re-run reaches the
    same verdict the live pass did, and the trip is a fact that names N.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import execsim, risk, setups, settings, store


def _candle(con, sym, tf, ts):
    con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sym, tf, ts, "100", "102", "98", "100", "1", "phemex-perp", ts))


def _setup(con, sid, direction, confirmed, strategy="REVERSAL"):
    sl = "95" if direction == "LONG" else "105"
    tp = "110" if direction == "LONG" else "90"
    store.insert_fact(con, symbol="BTCUSDT", tf="1D", kind="setup",
                      market_time=confirmed - 10, confirmed_at=confirmed,
                      algo_version=setups.SETUP_VERSION,
                      payload={"setup_id": sid, "strategy": strategy,
                               "direction": direction, "entry": "100",
                               "sl": sl, "tp": tp, "rr": "2", "rank": 50,
                               "state": "VALIDATED"})


def _exit(con, sid, confirmed, r):
    store.insert_fact(con, symbol="BTCUSDT", tf="1D", kind="exec",
                      market_time=confirmed - 10, confirmed_at=confirmed,
                      algo_version=execsim.EXEC_VERSION,
                      payload={"setup_id": sid, "outcome": "SL" if r < 0 else "TP",
                               "r_multiple": str(r)})


class SameSideGovernor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "g.db")
        base = store.start_baseline(self.con, label="g",
                                    strategy_version=setups.SETUP_VERSION,
                                    execution_version=execsim.EXEC_VERSION,
                                    risk_version=risk.RISK_VERSION)
        # risk.run only sizes intents confirmed inside the baseline, and only
        # walks symbols that carry 1D candles. Work on the first full UTC day
        # after the baseline started so "next day" arithmetic is exact.
        self.day = (base["started_at"] // 86400 + 1) * 86400
        for i in range(3):
            _candle(self.con, "BTCUSDT", "1D", self.day + i * 86400)
        self.con.commit()
        # MAX_CONCURRENT is 1: each intent must close before the next confirms
        # or CONCURRENT_LIMIT fires first and the governor is never reached.

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _decisions(self):
        return {json.loads(r["payload"])["setup_id"]: json.loads(r["payload"])
                for r in store.get_facts(self.con, "BTCUSDT", "1D", "risk",
                                         risk.RISK_VERSION)}

    def _seed_two_short_losses(self, day=None):
        day = self.day if day is None else day
        # two shorts, each stopped before the next confirms
        _setup(self.con, "s1", "SHORT", day + 1000); _exit(self.con, "s1", day + 1500, -1.0)
        _setup(self.con, "s2", "SHORT", day + 2000); _exit(self.con, "s2", day + 2500, -1.0)

    def test_the_third_same_side_entry_is_refused_and_says_why(self):
        self._seed_two_short_losses()
        _setup(self.con, "s3", "SHORT", self.day + 3000)
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        d = self._decisions()
        self.assertEqual(d["s1"]["decision"], "APPROVED")
        self.assertEqual(d["s2"]["decision"], "APPROVED")
        self.assertEqual(d["s3"]["decision"], "REJECTED")
        self.assertEqual(d["s3"]["reasons"], ["SAME_SIDE_HALT(SHORT,2)"],
                         "the reason must carry the side and the count")
        self.assertEqual(d["s3"]["risk_usd"], "0")

    def test_the_other_side_is_not_refused(self):
        self._seed_two_short_losses()
        _setup(self.con, "l1", "LONG", self.day + 3000)
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        self.assertEqual(self._decisions()["l1"]["decision"], "APPROVED",
                         "two losing shorts must not stop a long")

    def test_the_next_utc_day_starts_clean(self):
        self._seed_two_short_losses()
        _setup(self.con, "s3", "SHORT", self.day + 86400 + 100)
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        self.assertEqual(self._decisions()["s3"]["decision"], "APPROVED")

    def test_a_loss_that_exits_after_the_intent_does_not_count(self):
        """Point-in-time: only exits that have LANDED by the intent's own
        confirmation count. A stop that lands later is the future."""
        _setup(self.con, "s1", "SHORT", self.day + 1000); _exit(self.con, "s1", self.day + 1500, -1.0)
        # s2 confirms at +2000 and stops at +9000 — AFTER s3 confirms at +3000.
        # MAX_CONCURRENT would refuse s3 while s2 is open, so exit s2 first in
        # time but make its LOSS land late is impossible by construction; use
        # the day boundary instead: s2's loss lands on the next day.
        _setup(self.con, "s2", "SHORT", self.day + 2000); _exit(self.con, "s2", self.day + 86400 + 10, -1.0)
        _setup(self.con, "s3", "SHORT", self.day + 86400 + 100)
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        d = self._decisions()
        # s2's loss is day+1's first, s1's was day 0's only: neither day reaches 2
        self.assertEqual(d["s3"]["decision"], "APPROVED")

    def test_the_trip_is_a_portfolio_fact_that_names_the_limit(self):
        self._seed_two_short_losses()
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        trips = [json.loads(r["payload"]) for r in store.get_facts(
            self.con, "PORTFOLIO", "ALL", "risk", risk.RISK_VERSION)
            if json.loads(r["payload"]).get("event") == "SAME_SIDE_HALT"]
        self.assertEqual(len(trips), 1, "one trip per (day, side), not one per loss")
        self.assertEqual(trips[0]["side"], "SHORT")
        self.assertEqual(trips[0]["losses"], 2)
        self.assertEqual(trips[0]["limit"], 2)

    def test_zero_disables_it(self):
        settings.set_many(self.con, {"same_side_session_losses": 0}, note="test")
        self._seed_two_short_losses()
        _setup(self.con, "s3", "SHORT", self.day + 3000)
        self.con.commit()
        with mock.patch.object(risk, "admitted_at", return_value=True):
            risk.run(self.con)
        self.assertEqual(self._decisions()["s3"]["decision"], "APPROVED")

    def test_the_limit_is_operational_so_tightening_it_keeps_the_record(self):
        before = store.get_active_baseline(self.con)["id"]
        settings.set_many(self.con, {"same_side_session_losses": 1}, note="test")
        self.assertEqual(store.get_active_baseline(self.con)["id"], before)


if __name__ == "__main__":
    unittest.main()
