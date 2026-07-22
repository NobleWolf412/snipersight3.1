import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from engine import execsim, risk, setups, store


class TestSetupTelemetryAPI(unittest.TestCase):
    def test_active_baseline_hides_pre_reset_losses_everywhere(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "baseline.db"
            original_connect = store.connect
            con = original_connect(db)
            setup = {"setup_id": "old-loss", "state": "VALIDATED",
                     "strategy": "PULLBACK", "direction": "LONG",
                     "entry": "100", "sl": "95", "tp": "110", "rr": "2",
                     "rank": 65, "why": "legacy test setup"}
            store.insert_fact(con, symbol="BTC-USD", tf="1D", kind="setup",
                              market_time=10, confirmed_at=20,
                              algo_version=setups.SETUP_VERSION, payload=setup)
            store.insert_fact(
                con, symbol="BTC-USD", tf="1D", kind="exec", market_time=10,
                confirmed_at=30, algo_version=execsim.EXEC_VERSION,
                payload={"setup_id": "old-loss", "strategy": "PULLBACK",
                         "outcome": "SL", "r_multiple": "-1.2"})
            store.start_baseline(con, started_at=100)
            risk.run(con)
            con.close()

            with patch("server.store.connect", side_effect=lambda: original_connect(db)):
                track = server.track("BTC-USD", "1D")
                trace = server.setup_telemetry(None, None, None, 100)
                performance = server.performance()
                portfolio = server.portfolio()

        self.assertEqual(track["n"], 0)
        self.assertEqual(trace["funnel"]["validated"], 0)
        self.assertEqual(performance["by_symbol"], [])
        self.assertEqual(portfolio["equity"], 10000.0)
        self.assertEqual(portfolio["active_positions"], [])
        self.assertEqual(portfolio["baseline"]["started_at"], 100)

    def test_lifecycle_funnel_and_failure_attribution(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "telemetry.db"
            original_connect = store.connect
            con = original_connect(db)
            setup = {"setup_id": "trace-1", "state": "VALIDATED",
                     "strategy": "PULLBACK", "direction": "LONG",
                     "entry": "100", "sl": "95", "tp": "110", "rr": "2",
                     "rank": 65, "why": "bull regime plus demand zone"}
            store.insert_fact(con, symbol="BTC-USD", tf="1D", kind="setup",
                              market_time=10, confirmed_at=20,
                              algo_version=setups.SETUP_VERSION, payload=setup)
            store.insert_fact(
                con, symbol="BTC-USD", tf="1D", kind="risk", market_time=10,
                confirmed_at=21, algo_version=risk.RISK_VERSION,
                payload={"event": "DECISION", "setup_id": "trace-1",
                         "decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
                         "risk_usd": "200"})
            order = {"setup_id": "trace-1", "side": "LONG",
                     "order_type": "LIMIT", "limit_price": "100",
                     "available_at": 20, "event": "FILLED"}
            store.insert_fact(con, symbol="BTC-USD", tf="1D", kind="order",
                              market_time=10, confirmed_at=22,
                              algo_version=execsim.EXEC_VERSION, payload=order)
            store.insert_fact(
                con, symbol="BTC-USD", tf="1D", kind="exec", market_time=10,
                confirmed_at=30, algo_version=execsim.EXEC_VERSION,
                payload={"setup_id": "trace-1", "outcome": "SL",
                         "r_multiple": "-1.2", "r_gross": "-1",
                         "costs_r": "0.2", "mae_r": "1", "mfe_r": "0.3",
                         "fill_ts": 22, "bars_to_fill": 0, "bars_held": 2})
            con.commit()
            con.close()

            with patch("server.store.connect",
                       side_effect=lambda: original_connect(db)):
                result = server.setup_telemetry(None, None, None, 100)

        self.assertEqual(result["funnel"], {
            "rejected_candidates": 0, "validated": 1, "risk_approved": 1,
            "order_placed": 1, "filled": 1, "closed": 1, "winners": 0})
        self.assertEqual(result["failure_points"], {"STOP_LOSS": 1})
        self.assertEqual(result["records"][0]["why"],
                         "bull regime plus demand zone")


if __name__ == "__main__":
    unittest.main()
