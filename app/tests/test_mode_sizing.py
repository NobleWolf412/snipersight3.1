"""Mode-aware R sizing — the properties that make paper a rehearsal for live.

The design: gates are stated in R and identical in every mode; only the R
size differs (paper/shadow 2%, testnet/live 0.25%). The paper replay is never
mode-aware — a mode flip mid-baseline must not mint a second generation of
DECISION facts. The real-venue size is applied at dispatch, by scaling the
paper-sized quantity.

Everything here drives a temp store. Nothing touches the live database.
"""
import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import execsim, risk, settings, setups, store
from engine.contracts import AutomationMode as Mode


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

    def validated_setup(self, sid="s1", strategy="PULLBACK", confirmed_at=None,
                        **extra):
        # Dated AFTER the active baseline: flipping a behavioural setting in a
        # test (set_many) cuts a fresh baseline at "now", and the replay only
        # reads intents confirmed inside it.
        import time as _time
        payload = {"setup_id": sid, "strategy": strategy, "direction": "LONG",
                   "entry": "100", "sl": "95", "tp": "110", "rr": "2",
                   "rank": 50, "state": "VALIDATED", **extra}
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="setup",
            market_time=100,
            confirmed_at=confirmed_at or int(_time.time()) + 3600,
            algo_version=setups.SETUP_VERSION, payload=payload)

    def decisions(self):
        return [json.loads(r["payload"]) for r in store.get_facts(
            self.con, "BTC-USD", "1D", "risk", risk.RISK_VERSION)]


class ReplayIsPaperAlways(TempStore):
    def test_the_replay_sizes_at_paper_r_and_says_so_on_the_fact(self):
        """A DECISION fact explains itself: it records the pct it was sized
        with and that the basis is PAPER — so no reader ever needs this
        module's constants to interpret it, and a mode flip cannot change
        what a re-run writes."""
        candle(self.con, "BTC-USD", "1D", 0, 100, 101, 99, 100)
        self.validated_setup()
        risk.run(self.con)
        d = self.decisions()[-1]
        self.assertEqual(d["risk_pct"], "0.02")
        self.assertEqual(d["pct_basis"], "PAPER")
        # 2% of 10,000 start equity, spot venue caps leverage at 1x:
        # intended $200, entry 100/sl 95 -> within the cap, full size.
        self.assertEqual(d["intended_risk_usd"], "200.00")

    def test_a_zero_r_add_is_rejected_inside_the_replay_too(self):
        """size_order() refusing 0R is not enough — run() computes `intended`
        itself. With the strategy switch ON, a SCALE_IN must book REJECTED
        with the 0R reason, never APPROVED at zero size (audit 2026-08-08,
        finding 4: the arithmetic enforced the contract and nothing said so).
        """
        settings.set_many(self.con, {"strategy_scale_in": True},
                          note="test: exercise the 0R gate")
        candle(self.con, "BTC-USD", "1D", 0, 100, 101, 99, 100)
        self.validated_setup(sid="parent", strategy="PULLBACK")
        self.validated_setup(sid="parent|ADD", strategy="SCALE_IN",
                             parent_setup_id="parent")
        risk.run(self.con)
        add = [d for d in self.decisions() if d["setup_id"] == "parent|ADD"]
        self.assertEqual(len(add), 1)
        self.assertEqual(add[0]["decision"], "REJECTED")
        self.assertEqual(add[0]["reasons"], ["SCALE_IN_FORBIDDEN(0R)"])
        self.assertEqual(add[0]["risk_usd"], "0")

    def test_no_decision_ever_books_approved_at_zero_risk(self):
        """The belt-and-braces guard, exercised end to end: whatever path a
        decision takes, APPROVED/REDUCED implies positive risk dollars."""
        settings.set_many(self.con, {"strategy_scale_in": True},
                          note="test: exercise the 0R gate")
        candle(self.con, "BTC-USD", "1D", 0, 100, 101, 99, 100)
        self.validated_setup(sid="a")
        self.validated_setup(sid="a|ADD", strategy="SCALE_IN",
                             parent_setup_id="a")
        risk.run(self.con)
        for d in self.decisions():
            with self.subTest(setup=d["setup_id"]):
                if d["decision"] in ("APPROVED", "REDUCED"):
                    self.assertGreater(Decimal(d["risk_usd"]), 0)


class ArmingIsPaperAlways(TempStore):
    def test_forming_facts_are_sized_at_paper_r(self):
        """The armed order bakes its size in at arming; that size is paper's
        2% of start equity, deterministically, regardless of any mode ever
        set. (The setup fixture below is what the arming pass produces; here
        we pin the sizer call it makes.)"""
        out = risk.size_order(
            equity=risk.START_EQUITY, entry=Decimal("100"), sl=Decimal("95"),
            direction="LONG", symbol="BTC-USD",
            risk_pct=risk.gates_for_mode(Mode.PAPER)["risk_pct"],
            base_risk_pct=risk.gates_for_mode(Mode.PAPER)["risk_pct"])
        self.assertEqual(out["decision"], "APPROVED")
        self.assertEqual(out["risk_usd"], Decimal("200.00"))
        self.assertEqual(out["units"], Decimal("40.00000000"))


class DispatchCarriesTheModeR(unittest.TestCase):
    """The one place testnet/live R binds: quantity scaling at plan build."""

    ROW = {
        "eligible": True, "state": "READY",
        "setup": {"setup_id": "BTC-USD|1D|PULLBACK|z|setup-v0.18-draft",
                  "symbol": "BTCUSDT", "direction": "LONG", "entry": "100",
                  "stop": "95", "targets": ["110"], "venue": "phemex-perp",
                  "timeframe": "1D", "expires_at": None, "version": "x"},
        "risk_decision": {"decision": "APPROVED", "units": "40.00000000",
                          "risk_usd": "200.00", "notional_usd": "4000.00",
                          "implied_leverage": "0.40",
                          "reasons": ["WITHIN_LIMITS"]},
        "entry_recommendation": {"order_kind": "LIMIT", "limit_price": "100",
                                 "entry_model": "MAKER_PULLBACK",
                                 "maker_wait_bars": 4},
    }

    def test_testnet_quantity_is_the_paper_quantity_at_the_r_ratio(self):
        from engine import autotrader
        plan = autotrader.build_plan(dict(self.ROW), Mode.TESTNET)
        self.assertEqual(plan.intent.quantity, Decimal("5.00000000"))
        self.assertEqual(plan.risk.risk_usd, Decimal("25.00"))
        self.assertEqual(plan.risk.notional_usd, Decimal("500.00"))

    def test_paper_and_shadow_quantities_are_untouched(self):
        from engine import autotrader
        for mode in (Mode.PAPER, Mode.SHADOW):
            with self.subTest(mode=mode.value):
                plan = autotrader.build_plan(dict(self.ROW), mode)
                self.assertEqual(plan.intent.quantity, Decimal("40.00000000"))
                self.assertEqual(plan.risk.risk_usd, Decimal("200.00"))

    def test_plan_and_intent_quantity_stay_consistent(self):
        """execution.dispatch requires plan/intent quantity equality; the
        scale must apply to both or every testnet dispatch is refused."""
        from engine import autotrader
        plan = autotrader.build_plan(dict(self.ROW), Mode.TESTNET)
        self.assertEqual(plan.intent.quantity, plan.risk.quantity)


if __name__ == "__main__":
    unittest.main()
