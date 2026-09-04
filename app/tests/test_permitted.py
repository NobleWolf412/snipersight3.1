"""The permitted direction (bias.permitted): one tradeable side, or none.

Pinned branch by branch because this is the reading a direction-first
playbook will be allowed to refuse on. The rung-above PHASE outranks the
ladder — that ordering is the whole reason the reading exists — and UNKNOWN
permits BOTH for the same reason `validate_policy` refuses to map UNKNOWN to
anything but ALLOW."""
import unittest

from engine import bias


class Permitted(unittest.TestCase):
    def test_the_ladder_alone(self):
        self.assertEqual(bias.permitted("UP"), "UP")
        self.assertEqual(bias.permitted("DOWN"), "DOWN")
        self.assertEqual(bias.permitted("FLAT"), "BOTH")
        self.assertEqual(bias.permitted("MIXED"), "NONE")

    def test_unknown_permits_both_never_none(self):
        self.assertEqual(bias.permitted("UNKNOWN"), "BOTH")
        self.assertEqual(bias.permitted(None), "BOTH")

    def test_an_impulse_one_rung_up_outranks_a_flat_or_mixed_ladder(self):
        """2026-09-03: ladder FLAT for LINK on a day it was up 7%; the 1H phase
        was IMPULSE_UP. The short was the wrong side and the ladder could not
        say so."""
        self.assertEqual(bias.permitted("FLAT", "IMPULSE_UP"), "UP")
        self.assertEqual(bias.permitted("MIXED", "IMPULSE_DOWN"), "DOWN")
        self.assertEqual(bias.permitted("UP", "TREND_DOWN_EXTENDED"), "DOWN")

    def test_a_turn_or_drift_one_rung_up_does_not_assert_a_side(self):
        self.assertEqual(bias.permitted("FLAT", "TURN_UP"), "BOTH")
        self.assertEqual(bias.permitted("FLAT", "DRIFT_DOWN"), "BOTH")
        self.assertEqual(bias.permitted("UP", "DRIFT_DOWN"), "UP")
        self.assertEqual(bias.permitted("FLAT", "RANGE"), "BOTH")
        self.assertEqual(bias.permitted("FLAT", "UNKNOWN"), "BOTH")


class Agrees(unittest.TestCase):
    def test_sides(self):
        self.assertTrue(bias.agrees("LONG", "UP"))
        self.assertFalse(bias.agrees("SHORT", "UP"))
        self.assertTrue(bias.agrees("SHORT", "DOWN"))

    def test_both_admits_either_and_none_admits_neither(self):
        self.assertTrue(bias.agrees("LONG", "BOTH"))
        self.assertTrue(bias.agrees("SHORT", "BOTH"))
        self.assertFalse(bias.agrees("LONG", "NONE"))
        self.assertFalse(bias.agrees("SHORT", "NONE"))

    def test_a_nonsense_direction_raises(self):
        with self.assertRaises(ValueError):
            bias.agrees("SIDEWAYS", "UP")


if __name__ == "__main__":
    unittest.main()
