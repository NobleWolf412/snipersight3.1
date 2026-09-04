"""The context gate (setups.PULLBACK_CONTEXT_POLICY, setup-v0.20).

Built and armed nowhere: every value is ALLOW, and the first of these tests is
the lockfile that says so. The rest prove the mechanism with a test-only
policy — a branch that has never fired is a branch nobody has tested — and
pin the vocabulary, so the day a value moves the refusal already has a
sentence.
"""
import inspect
import pathlib
import unittest

from engine import setups


class Lockfile(unittest.TestCase):
    def test_the_shipped_policy_is_allow_everywhere(self):
        """Recording must not change a single trade. If this stops being
        ALLOW everywhere, that is enforcement: it needs a version bump and a
        grade on trades confirmed after 2026-09-03, not before."""
        self.assertEqual(set(setups.PULLBACK_CONTEXT_POLICY.values()), {"ALLOW"})
        self.assertEqual(set(setups.PULLBACK_CONTEXT_POLICY), set(setups.CONTEXT_STATES))

    def test_the_manifest_records_it(self):
        src = inspect.getsource(setups)
        self.assertIn('"pullback_context_policy": dict(PULLBACK_CONTEXT_POLICY)', src)
        self.assertIn('"regimeread": REGIMEREAD_VERSION', src)


class Validation(unittest.TestCase):
    def test_a_policy_silent_on_a_state_is_rejected(self):
        with self.assertRaises(ValueError):
            setups.validate_context_policy({"BOTH": "ALLOW", "UP": "ALLOW", "DOWN": "ALLOW"})

    def test_an_unknown_action_or_state_is_rejected(self):
        with self.assertRaises(ValueError):
            setups.validate_context_policy({**setups.PULLBACK_CONTEXT_POLICY, "UP": "MAYBE"})
        with self.assertRaises(ValueError):
            setups.validate_context_policy({**setups.PULLBACK_CONTEXT_POLICY, "SIDEWAYS": "ALLOW"})


class Enforcement(unittest.TestCase):
    BLOCK_TRENDS = {"BOTH": "ALLOW", "UP": "BLOCK", "DOWN": "BLOCK", "NONE": "ALLOW"}

    def test_a_block_policy_actually_blocks_a_pullback_inside_a_trend(self):
        v = setups.context_verdict("PULLBACK", "UP", self.BLOCK_TRENDS)
        self.assertTrue(setups.context_blocked(v))
        self.assertEqual(v["permitted"], "UP")

    def test_the_same_policy_allows_a_pullback_with_no_direction_asserted(self):
        v = setups.context_verdict("PULLBACK", "BOTH", self.BLOCK_TRENDS)
        self.assertFalse(setups.context_blocked(v))

    def test_it_is_keyed_on_pullback_only(self):
        v = setups.context_verdict("REVERSAL", "UP", self.BLOCK_TRENDS)
        self.assertFalse(setups.context_blocked(v))
        self.assertFalse(v["applies"])

    def test_no_reading_is_not_a_hostile_reading(self):
        """UNKNOWN is never a weak form of AGAINST — the rule every gate in
        this codebase follows, enforced here for a missing context."""
        v = setups.context_verdict("PULLBACK", None, self.BLOCK_TRENDS)
        self.assertFalse(setups.context_blocked(v))

    def test_blocked_is_the_one_place_the_question_is_asked(self):
        src = inspect.getsource(setups)
        self.assertIn("context_blocked(", src)
        self.assertNotIn('["action"] == "BLOCK"', src.replace("def context_blocked", ""))


class Vocabulary(unittest.TestCase):
    def test_the_reason_is_canonical_and_has_a_funnel_sentence(self):
        self.assertEqual(setups.CONTEXT_BLOCK_REASON, "CONTEXT_BLOCKED")
        self.assertIn("CONTEXT_BLOCKED", setups.REJECTION_REASONS)
        funnel = (pathlib.Path(inspect.getfile(setups)).parents[1]
                  / "static" / "funnel.js").read_text(encoding="utf-8")
        self.assertIn("CONTEXT_BLOCKED:", funnel)

    def test_the_validated_payload_records_the_reading(self):
        """The fields a later grade reads. Text-pinned, because the payload is
        assembled inline and a dropped key fails nothing at runtime."""
        src = inspect.getsource(setups)
        for key in ('"phase": _phase["phase"]', '"htf_phase": _htf_phase',
                    '"permitted": _permitted', '"agrees": _agrees', '"context": _ctx'):
            self.assertIn(key, src, f"VALIDATED payload no longer records {key}")


if __name__ == "__main__":
    unittest.main()
