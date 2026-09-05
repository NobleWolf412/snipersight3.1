"""The window gate (setups.WINDOW_POLICY, setup-v0.21).

Four situations keyed on the chart-eye read against the trade, every value
ALLOW. The first test is the lockfile; the rest prove the mechanism with a
test-only policy and pin the vocabulary and the recorded fields.
"""
import inspect
import pathlib
import unittest

from engine import setups


class Lockfile(unittest.TestCase):
    def test_the_shipped_policy_is_allow_everywhere(self):
        self.assertEqual(set(setups.WINDOW_POLICY.values()), {"ALLOW"})
        self.assertEqual(set(setups.WINDOW_POLICY), set(setups.WINDOW_SITUATIONS))

    def test_the_manifest_records_it_and_the_reader_version(self):
        src = inspect.getsource(setups)
        self.assertIn('"window_policy": dict(WINDOW_POLICY)', src)
        self.assertIn('"chartread": CHARTREAD_VERSION', src)


class Situations(unittest.TestCase):
    def test_the_four_situations_and_nothing_else(self):
        s = setups.window_situation
        self.assertEqual(s("REVERSAL", "SHORT", "UP"), "REVERSAL_SHORT_IN_UP")
        self.assertEqual(s("REVERSAL", "LONG", "DOWN"), "REVERSAL_LONG_IN_DOWN")
        self.assertEqual(s("PULLBACK", "SHORT", "CHOP"), "PULLBACK_SHORT_IN_CHOP")
        self.assertEqual(s("PULLBACK", "LONG", "CHOP"), "PULLBACK_LONG_IN_CHOP")
        # with the window, in a range, or unread: not a situation
        self.assertIsNone(s("REVERSAL", "LONG", "UP"))
        self.assertIsNone(s("REVERSAL", "SHORT", "RANGE"))
        self.assertIsNone(s("PULLBACK", "LONG", "UP"))
        self.assertIsNone(s("PULLBACK", "LONG", None))


class Enforcement(unittest.TestCase):
    BLOCK_TWO = {"REVERSAL_SHORT_IN_UP": "BLOCK", "REVERSAL_LONG_IN_DOWN": "ALLOW",
                 "PULLBACK_SHORT_IN_CHOP": "BLOCK", "PULLBACK_LONG_IN_CHOP": "ALLOW"}

    def test_a_block_policy_actually_blocks(self):
        v = setups.window_verdict("REVERSAL", "SHORT", "UP", self.BLOCK_TWO)
        self.assertTrue(setups.window_blocked(v))
        self.assertEqual(v["situation"], "REVERSAL_SHORT_IN_UP")

    def test_the_mirror_is_its_own_value(self):
        v = setups.window_verdict("REVERSAL", "LONG", "DOWN", self.BLOCK_TWO)
        self.assertFalse(setups.window_blocked(v))

    def test_no_reading_is_not_a_hostile_reading(self):
        v = setups.window_verdict("REVERSAL", "SHORT", None, self.BLOCK_TWO)
        self.assertFalse(setups.window_blocked(v))
        self.assertIsNone(v["situation"])

    def test_validation_refuses_a_silent_or_misspelt_policy(self):
        with self.assertRaises(ValueError):
            setups.validate_window_policy({k: "ALLOW" for k in setups.WINDOW_SITUATIONS[:3]})
        with self.assertRaises(ValueError):
            setups.validate_window_policy({**setups.WINDOW_POLICY, "REVERSAL_SHORT_IN_UP": "MAYBE"})

    def test_blocked_is_the_one_place_the_question_is_asked(self):
        src = inspect.getsource(setups)
        self.assertIn("window_blocked(", src)
        self.assertNotIn('== "BLOCK"', src)


class Vocabulary(unittest.TestCase):
    def test_the_reason_is_canonical_and_has_a_funnel_sentence(self):
        self.assertEqual(setups.WINDOW_BLOCK_REASON, "WINDOW_BLOCKED")
        self.assertIn("WINDOW_BLOCKED", setups.REJECTION_REASONS)
        funnel = (pathlib.Path(inspect.getfile(setups)).parents[1]
                  / "static" / "funnel.js").read_text(encoding="utf-8")
        self.assertIn("WINDOW_BLOCKED:", funnel)

    def test_the_validated_payload_records_the_chart_read(self):
        src = inspect.getsource(setups)
        self.assertIn('"chart": _chart', src)
        for key in ('"read": _cc["read"]', '"bias": _own.get("bias")', '"call": _cc["call"]',
                    '"false_breaks": _own.get("false_breaks")', '"htf_read": _cc["htf_read"]'):
            self.assertIn(key, src, f"the chart block no longer records {key}")


if __name__ == "__main__":
    unittest.main()
