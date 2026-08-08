"""The registry must describe the engine, not an intention.

Its whole reason to exist is that strategy metadata was written by hand in
`server.py` while the behaviour lived in `setups.py`, and the two drifted: the
playbook card said REVERSAL "needs a liquidity sweep within 10 bars" for a full
session after setup-v0.7 replaced that rule with 2-of-4 evidence. A user reading
it was told a trade was impossible when it had become merely conditional.

So these tests hold the registry against the ENGINE, not against prose.
"""
import unittest

from engine import registry, settings, setups


class MatchesTheEngine(unittest.TestCase):
    def test_every_live_strategy_is_one_playbook_actually_returns(self):
        produced = set()
        for zone in ("DEMAND", "SUPPLY"):
            for reg in ("BULL_TREND", "WEAKENING_BULL", "BEAR_TREND",
                        "WEAKENING_BEAR", "TRANSITION", "RANGE", None):
                for ev in ([], ["CHOCH", "VOLUME"]):
                    play = setups.playbook(zone, reg, bool(ev), None, ev)
                    if play:
                        produced.add(play[0])
        # SCALE_IN comes from scalein.py, not playbook()
        declared = {s.key.upper() for s in registry.LIVE} - {"SCALE_IN"}
        self.assertTrue(
            declared <= produced | {"SCALE_IN"},
            f"registry declares {declared - produced} which playbook() never returns")

    def test_declared_regimes_are_regimes_the_engine_admits(self):
        """A registry naming a regime the playbook refuses would put a strategy
        on screen that can never fire."""
        for s in registry.LIVE:
            if not s.regimes:
                continue
            with self.subTest(strategy=s.key):
                fired = any(
                    setups.playbook(zone, reg, True, None, ["CHOCH", "VOLUME"])
                    for zone in ("DEMAND", "SUPPLY") for reg in s.regimes)
                self.assertTrue(fired, f"{s.key} declares {s.regimes}, none admit it")

    def test_reversal_is_marked_as_needing_extra_evidence(self):
        """The engine gates TRANSITION on composed evidence. If that ever stops
        being true this must stop claiming it."""
        self.assertIsNone(setups.playbook("DEMAND", "TRANSITION", False, None, []))
        self.assertIsNotNone(registry.REVERSAL.requires)

    def test_pullback_needs_no_extra_evidence(self):
        self.assertIsNotNone(
            setups.playbook("DEMAND", "BULL_TREND", False, None, []))
        self.assertIsNone(registry.PULLBACK.requires)


class MatchesSettings(unittest.TestCase):
    def test_every_live_strategy_maps_to_a_real_behavioural_switch(self):
        """A toggle writing a setting `settings.py` has never heard of would 400
        on apply — after telling the operator their record would reset."""
        for s in registry.LIVE:
            with self.subTest(strategy=s.key):
                self.assertIn(s.setting, settings.SPEC)
                self.assertEqual(settings.SPEC[s.setting][0], "BEHAVIOURAL",
                                 "enabling a strategy changes what the engine "
                                 "produces, so it must restart the record")

    def test_enabled_strategies_and_the_registry_agree(self):
        """`setups.enabled_strategies` reads the switches; the registry names
        them. Two lists of the same thing must not diverge."""
        engine_names = {"PULLBACK", "REVERSAL", "SCALE_IN"}
        self.assertEqual({s.key.upper() for s in registry.LIVE}, engine_names)


class Shape(unittest.TestCase):
    def test_planned_strategies_carry_a_measured_gap_and_no_record(self):
        planned = [s for s in registry.ALL if s.status == "planned"]
        self.assertTrue(planned)
        for s in planned:
            with self.subTest(strategy=s.key):
                self.assertTrue(s.gap, "a planned strategy must say why it matters")

    def test_keys_are_unique_and_slug_shaped(self):
        keys = [s.key for s in registry.ALL]
        self.assertEqual(len(keys), len(set(keys)))
        for k in keys:
            self.assertRegex(k, r"^[a-z][a-z_]*$")

    def test_every_strategy_declares_the_public_evidence_contract(self):
        allowed = {"RESEARCH", "PAPER", "SHADOW", "TESTNET",
                   "LIVE_ELIGIBLE", "DISABLED"}
        for strategy in registry.ALL:
            with self.subTest(strategy=strategy.key):
                self.assertIn(strategy.evidence_status, allowed)
                self.assertTrue(strategy.horizons)
                self.assertTrue(strategy.trigger_timeframe)
                self.assertTrue(strategy.entry_policy)
                self.assertTrue(strategy.invalidation_policy)
                self.assertTrue(strategy.exit_policy)
                self.assertTrue(strategy.directions)
                self.assertTrue(strategy.higher_timeframe_relationship)
                self.assertTrue(strategy.trigger_rule)
                self.assertTrue(strategy.minimum_rr_after_costs)
                self.assertTrue(strategy.liquidity_rule)
                self.assertTrue(strategy.spread_rule)
                self.assertTrue(strategy.volatility_rule)
                self.assertTrue(strategy.freshness_rule)
                self.assertEqual(strategy.version,
                                 registry.STRATEGY_CONTRACT_VERSION)

    def test_every_horizon_is_one_the_cooldown_policy_knows(self):
        """A horizon is a hold-time and cooldown policy. One the cooldown tables
        do not recognise would silently fall back to another strategy's rules."""
        from engine import cooldowns
        for s in registry.ALL:
            with self.subTest(strategy=s.key):
                self.assertIn(s.horizon, cooldowns.STOP_OUT_HOURS)
                self.assertIn(s.horizon, cooldowns.RESOLVED_HOURS)

    def test_lookup_by_engine_name_is_case_insensitive_and_total(self):
        for s in registry.LIVE:
            self.assertIs(registry.for_engine_name(s.key.upper()), s)
            self.assertIs(registry.for_engine_name(s.key.lower()), s)
        self.assertIsNone(registry.for_engine_name("NOT_A_STRATEGY"))
        self.assertIsNone(registry.for_engine_name(""))


if __name__ == "__main__":
    unittest.main()
