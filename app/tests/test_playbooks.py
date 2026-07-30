"""The playbook catalogue: honest about its own losses, and about what it
has not measured.

Three properties are worth protecting with tests, because each one is a rule
the surface exists to enforce rather than an implementation detail:

  · a LOSING playbook prints its loss. A catalogue that dropped or softened a
    negative record would be a sales page, and choosing between strategies on
    it would be choosing on advertising.
  · a PLANNED playbook names a measured gap. "Coming soon" is a promise; "24%
    of the candidates we rejected were ranging markets" is an explanation.
  · those percentages are COUNTED, never written down. A hard-coded 27% keeps
    claiming 27% long after the market moved, which is the exact species of
    confident stale number this whole surface exists to replace.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from engine import execsim, risk, settings, setups, store

FIVE_LABELS = ("hunts", "triggers", "confirms", "stop_goes", "holds_for")


def _reject(con, reason, regime=None, ts=50, version=None):
    """One recorded rejection, shaped the way setups.py writes them."""
    store.insert_fact(
        con, symbol="BTC-USD", tf="1D", kind="setup_rejection",
        market_time=ts, confirmed_at=ts,
        algo_version=version or setups.SETUP_VERSION,
        payload={"event": "REJECTED", "zone_id": f"z{ts}", "reason": reason,
                 "details": {"regime": regime, "zone_type": "DEMAND"}})


def _trade(con, setup_id, strategy, r_multiple, *, ts, risk_usd=None):
    """A closed simulated trade, plus the sizing verdict when it was sized."""
    store.insert_fact(
        con, symbol="BTC-USD", tf="1D", kind="setup", market_time=ts,
        confirmed_at=ts, algo_version=setups.SETUP_VERSION,
        payload={"setup_id": setup_id, "state": "VALIDATED",
                 "strategy": strategy, "direction": "LONG", "entry": "100",
                 "sl": "95", "tp": "110", "rr": "2", "rank": 60, "why": "test"})
    store.insert_fact(
        con, symbol="BTC-USD", tf="1D", kind="exec", market_time=ts,
        confirmed_at=ts + 1, algo_version=execsim.EXEC_VERSION,
        payload={"setup_id": setup_id, "strategy": strategy, "outcome":
                 "TP" if r_multiple > 0 else "SL", "r_multiple": str(r_multiple)})
    if risk_usd is not None:
        store.insert_fact(
            con, symbol="BTC-USD", tf="1D", kind="risk", market_time=ts,
            confirmed_at=ts, algo_version=risk.RISK_VERSION,
            payload={"event": "DECISION", "setup_id": setup_id,
                     "decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
                     "risk_usd": str(risk_usd)})


class PlaybookCatalogueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "playbooks.db"
        self._connect = store.connect
        self.con = self._connect(self.db)
        store.start_baseline(self.con, started_at=100, label="test window")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def call(self):
        self.con.commit()
        with patch("server.store.connect",
                   side_effect=lambda: self._connect(self.db)):
            return server.playbooks()

    def by_key(self, result):
        return {p["key"]: p for p in result["playbooks"]}

    # ---------- shape ----------

    def test_every_card_carries_the_same_five_labels(self):
        """Same five labels, same order, on every card — that is what makes two
        strategies comparable at a glance instead of two paragraphs to read."""
        result = self.call()
        self.assertTrue(result["playbooks"], "catalogue served no playbooks")
        for p in result["playbooks"]:
            for field in ("key", "name", "status", "one_liner", "timeframes"):
                self.assertIn(field, p, p.get("key"))
            for label in FIVE_LABELS:
                self.assertTrue(p.get(label), f"{p['key']} has no {label}")
            self.assertIn(p["status"], ("live", "planned"))

    def test_live_cards_expose_a_record_and_a_toggle_planned_do_not(self):
        result = self.call()
        for p in result["playbooks"]:
            if p["status"] == "live":
                self.assertIsInstance(p["enabled"], bool, p["key"])
                self.assertIsInstance(p["record"], dict, p["key"])
                self.assertIsNotNone(p["setting"], p["key"])
            else:
                self.assertIsNone(p["record"], p["key"])
                self.assertIsNone(p["enabled"], p["key"])

    def test_enabled_reflects_the_operator_setting(self):
        """The switch on the card has to show what settings.py actually holds,
        or the operator turns something off and it keeps trading."""
        settings.set_many(self.con, {"strategy_reversal": False})
        cards = self.by_key(self.call())
        self.assertFalse(cards["reversal"]["enabled"])
        self.assertTrue(cards["pullback"]["enabled"])

    # ---------- the losses ----------

    def test_a_losing_playbook_reports_its_loss(self):
        """The property this surface lives or dies on."""
        _trade(self.con, "s1", "PULLBACK", -1.0, ts=200, risk_usd=200)
        _trade(self.con, "s2", "PULLBACK", -1.5, ts=300, risk_usd=200)
        _trade(self.con, "s3", "PULLBACK", 1.0, ts=400, risk_usd=200)
        rec = self.by_key(self.call())["pullback"]["record"]
        self.assertEqual(rec["n"], 3)
        self.assertEqual(rec["win_pct"], 33)
        self.assertEqual(rec["sum_r"], -1.5)
        self.assertEqual(rec["sized"], 3)
        self.assertEqual(rec["pnl_usd"], -300.0)

    def test_the_record_matches_performance_exactly(self):
        """One authority per number. If the catalogue ever computed its own
        win rate it could disagree with Results, and nothing on screen would
        tell the operator which of the two was lying."""
        _trade(self.con, "s1", "PULLBACK", -2.0, ts=200, risk_usd=150)
        _trade(self.con, "s2", "REVERSAL", 0.8, ts=300, risk_usd=150)
        self.con.commit()
        with patch("server.store.connect",
                   side_effect=lambda: self._connect(self.db)):
            perf = server.performance()
            cards = self.by_key(server.playbooks())
        rows = {r["key"]: r for r in perf["by_strategy"]}
        for name, key in (("PULLBACK", "pullback"), ("REVERSAL", "reversal")):
            for field in ("n", "win_pct", "sum_r", "sized", "pnl_usd"):
                self.assertEqual(cards[key]["record"][field], rows[name][field],
                                 f"{key}.{field} diverged from /api/performance")

    def test_no_trades_yet_is_not_reported_as_a_zero_percent_win_rate(self):
        """A 0% win rate is a claim about trades that happened. When none have,
        the card must say the window is empty, not print a confident zero."""
        rec = self.by_key(self.call())["pullback"]["record"]
        self.assertEqual(rec["n"], 0)
        self.assertIsNone(rec["win_pct"])

    def test_pre_baseline_losses_stay_out_of_the_record(self):
        """Same window as everything else on Results: a trade from before the
        current baseline belongs to an older configuration."""
        _trade(self.con, "old", "PULLBACK", -4.0, ts=10, risk_usd=200)
        _trade(self.con, "new", "PULLBACK", -1.0, ts=500, risk_usd=200)
        rec = self.by_key(self.call())["pullback"]["record"]
        self.assertEqual(rec["n"], 1)
        self.assertEqual(rec["sum_r"], -1.0)

    # ---------- planned playbooks and their measured gaps ----------

    def test_every_planned_playbook_names_a_gap(self):
        _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "RANGE", ts=10)
        _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "TRANSITION", ts=11)
        for p in self.call()["playbooks"]:
            if p["status"] != "planned":
                continue
            self.assertTrue(p.get("gap"), f"{p['key']} is planned with no reason")
            self.assertIsNotNone(p.get("gap_pct"), p["key"])
            self.assertGreater(p.get("gap_n"), 0, p["key"])

    def test_gap_percentages_are_counted_not_hard_coded(self):
        """Two different rejection corpora must produce two different gaps.

        (The second planned card, "Reversal, Reworked", was removed when that
        work shipped in S38 — the property is unchanged, it is now asserted on
        the one planned card that remains.)

        This is the test that would fail if someone pasted the spec's example
        numbers into the endpoint: those percentages would survive any change
        to the data underneath them.
        """
        # 3 of 10 rejections are ranging markets -> 30.0%
        for i in range(3):
            _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "RANGE", ts=10 + i)
        for i in range(5):
            _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "TRANSITION", ts=20 + i)
        for i in range(2):
            _reject(self.con, "RR_BELOW_MINIMUM", None, ts=30 + i)
        first = self.by_key(self.call())
        self.assertEqual(first["range_fade"]["gap_pct"], 30.0)
        self.assertEqual(first["range_fade"]["gap_n"], 3)
        self.assertIn("30.0%", first["range_fade"]["gap"])

        # move the data; the number must move with it
        for i in range(10):
            _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "RANGE", ts=100 + i)
        second = self.by_key(self.call())
        self.assertEqual(second["range_fade"]["gap_n"], 13)
        self.assertEqual(second["range_fade"]["gap_pct"], 65.0)
        self.assertNotEqual(second["range_fade"]["gap_pct"],
                            first["range_fade"]["gap_pct"])
        self.assertIn("65.0%", second["range_fade"]["gap"])

    def test_an_unmeasured_gap_says_so_instead_of_inventing_a_number(self):
        """Loud fallback. No corpus means no percentage, not a plausible one."""
        cards = self.by_key(self.call())
        planned = [k for k, c in cards.items() if c["status"] == "planned"]
        self.assertTrue(planned, "no planned card left to test the fallback on")
        for key in planned:
            self.assertIsNone(cards[key]["gap_pct"], key)
            self.assertIn("not measured", cards[key]["gap"].lower(), key)

    def test_gap_falls_back_to_older_versions_and_says_which(self):
        """A version bump leaves the new engine with no rejections of its own.
        Reporting 0% then would assert the gap had closed, which is a different
        claim from 'this engine has not measured it yet'."""
        _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "RANGE", ts=10,
                version="setup-v0.0-ancient")
        result = self.call()
        self.assertEqual(result["rejection_sample"]["basis"],
                         "every recorded setup version")
        self.assertEqual(self.by_key(result)["range_fade"]["gap_pct"], 100.0)

    def test_rejection_sample_is_published_so_the_gap_is_auditable(self):
        _reject(self.con, "NO_ELIGIBLE_PLAYBOOK", "RANGE", ts=10)
        _reject(self.con, "UNECONOMIC_AFTER_COSTS", None, ts=11)
        sample = self.call()["rejection_sample"]
        self.assertEqual(sample["total"], 2)
        self.assertEqual(sample["no_playbook"], 1)
        self.assertEqual(sample["basis"], setups.SETUP_VERSION)
        self.assertEqual(sample["by_regime"]["RANGE"], {"n": 1, "pct": 50.0})

    # ---------- the rules describe the engine that is loaded ----------

    def test_rule_text_is_read_from_the_engine_not_written_down(self):
        """The catalogue describes what the code does. If setups.py changes its
        confirmation window, the card has to change with it."""
        cards = self.by_key(self.call())
        if hasattr(setups, "confirms"):
            self.assertIn(str(setups.CONFIRM_MAX_BARS),
                          cards["pullback"]["confirms"])
            self.assertIn(str(setups.SL_BUFFER_ATR),
                          cards["pullback"]["stop_goes"])
        else:
            self.assertIn(str(setups.SL_ATR), cards["pullback"]["stop_goes"])
        # setup-v0.7 replaced the sweep-only REVERSAL gate with N-of-4 evidence.
        # The card must track THAT rule now — the same property, new rule.
        if hasattr(setups, "REVERSAL_MIN_EVIDENCE"):
            trig = cards["reversal"]["triggers"].lower()
            self.assertIn(str(setups.REVERSAL_MIN_EVIDENCE), trig,
                          "the card must state how many components are required")
            # every component the engine actually checks is named somewhere
            for component, word in (("CHOCH", "structural"), ("SWEEP", "sweep"),
                                    ("VOLUME", "volume"), ("STRENGTH", "zone")):
                if component in setups.REVERSAL_COMPONENTS:
                    self.assertIn(word, trig,
                                  f"{component} is gated on but never described")
        else:
            self.assertIn(str(setups.SWEEP_LOOKBACK_BARS),
                          cards["reversal"]["triggers"])

    def test_every_live_playbook_maps_to_a_real_settings_switch(self):
        """A toggle that writes a setting settings.py has never heard of would
        400 on apply, after telling the operator their record would reset."""
        for p in self.call()["playbooks"]:
            if p["status"] == "live":
                self.assertIn(p["setting"], settings.SPEC, p["key"])
                self.assertEqual(settings.SPEC[p["setting"]][0], "BEHAVIOURAL",
                                 "the card warns about a baseline reset; the "
                                 "setting must actually cause one")


if __name__ == "__main__":
    unittest.main()
