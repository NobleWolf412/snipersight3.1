import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from engine import execsim, risk, setups, store, telemetry


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
                # /api/track was retired 2026-07-31 (redundant with
                # performance.by_symbol, zero readers). Its slice of this
                # invariant — pre-baseline losses stay out of the per-symbol
                # record — is carried by the by_symbol assertion below, so the
                # property this test exists for is still checked everywhere it
                # can be observed.
                trace = server.setup_telemetry(None, None, None, 100)
                performance = server.performance()
                portfolio = server.portfolio()

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
        self.assertEqual(result["loss_autopsy"]["diagnosis"], "SETUP_SELECTION")
        self.assertEqual(result["loss_autopsy"]["evidence"]["loser_avg_mfe_r"],
                         0.3)

    def test_loss_autopsy_uses_only_approved_trades_and_names_weak_slices(self):
        def row(sid, result, *, tf="1H", direction="SHORT", role="MAKER",
                approved=True, closed_at=1):
            return {
                "setup_id": sid, "tf": tf, "direction": direction,
                "strategy": "REVERSAL", "entry_role": role,
                "risk_decision": "APPROVED" if approved else "REJECTED",
                "outcome": "TP" if result > 0 else "SL",
                "failure_code": "WINNER" if result > 0 else "STOP_LOSS",
                "net_r": str(result), "gross_r": str(result + .1),
                "costs_r": ".1", "mfe_r": "2.0" if result > 0 else ".2",
                "mae_r": ".2" if result > 0 else "1.2",
                "bars_held": 9 if result > 0 else 2,
                "closed_at": closed_at,
            }

        records = [row("a", -1.1, closed_at=4), row("b", -1.0, closed_at=3),
                   row("c", -1.2, closed_at=2), row("d", 2.5, tf="15m",
                                                       direction="LONG",
                                                       closed_at=1),
                   row("rejected", 10, approved=False, closed_at=5)]
        result = telemetry.loss_autopsy(records)

        self.assertEqual(result["closed"], 4)
        self.assertEqual(result["diagnosis"], "SETUP_SELECTION")
        self.assertEqual(result["evidence"]["current_losing_streak"], 3)
        self.assertEqual(result["evidence"]["net_r"], -0.8)
        self.assertIn("SHORT", {s["value"] for s in result["weakest_slices"]})
        self.assertIn("not automatic blocks", result["actions"][-1]["label"])


if __name__ == "__main__":
    unittest.main()
