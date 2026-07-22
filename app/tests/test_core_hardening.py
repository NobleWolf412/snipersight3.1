import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import costs, execsim, marketdata, risk, setups, store, universe, zones


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


class TestStrategyGuards(unittest.TestCase):
    def test_transition_requires_liquidity_sweep(self):
        self.assertIsNone(setups.playbook("DEMAND", "TRANSITION", swept=False))
        self.assertEqual(setups.playbook("DEMAND", "TRANSITION", swept=True)[:2],
                         ("REVERSAL", "LONG"))

    def test_zone_freshness_decays_instead_of_rising(self):
        self.assertGreater(zones.freshness(0, 0), zones.freshness(1, 0))
        self.assertGreater(zones.freshness(1, 0), zones.freshness(2, 0))
        self.assertEqual(zones.freshness(0, 0, broken=True), 0)


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
        for i in range(4):
            sid = f"long-{i}"
            confirmed = day + 100 + i * 1000
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1D", kind="setup",
                market_time=i, confirmed_at=confirmed,
                algo_version=setups.SETUP_VERSION,
                payload={"setup_id": sid, "strategy": "PULLBACK",
                         "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                         "rr": "2", "rank": 50, "state": "VALIDATED"})
            if i < 3:
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


if __name__ == "__main__":
    unittest.main()
