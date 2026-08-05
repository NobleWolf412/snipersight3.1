"""The top-down bias layer, and the rules that must not quietly rot.

Three things are pinned here beyond the arithmetic:

  · UNKNOWN can never be scored as a bad reading. That rule cost 1.02 R/trade
    the last time it was violated and it fell entirely on the only profitable
    timeframe, so it is enforced at write (`validate_policy` raises) and
    asserted here rather than left to review.
  · MIXED is a state, not a rounding error. A bearish daily over a bullish 4H
    must not resolve to either one.
  · Every playbook declares a policy. The roster test below fails for a NEW
    setup-emitting engine that ships without one — which is the whole claim
    that this layer is reusable rather than two hand-wired special cases.
"""
import inspect
import pathlib
import unittest

from engine import bias, breakout, setups, trend


class Ladder(unittest.TestCase):
    def test_rungs_are_the_whole_chain_not_one_step(self):
        """MIXED cannot exist with a single rung, and MIXED is the state a
        trader actually asks about. A 15m trade must be able to see the daily."""
        self.assertEqual(bias.rungs_above("15m"), ("1H", "4H", "1D", "1W"))
        self.assertEqual(bias.rungs_above("4H"), ("1D", "1W"))

    def test_the_top_rung_has_nothing_above_it(self):
        self.assertEqual(bias.rungs_above("1W"), ())

    def test_an_unknown_timeframe_has_no_rungs_rather_than_raising(self):
        """A timeframe outside the ladder reads UNKNOWN, which ALLOWs. It must
        not raise: the alternative is a scan that dies on an unfamiliar tf."""
        self.assertEqual(bias.rungs_above("3m"), ())

    def test_setups_re_exports_the_one_ladder(self):
        """Two copies of one ladder is the same disease as two copies of one
        fill model — they agree until one of them moves."""
        self.assertIs(setups.HTF_LADDER, bias.LADDER)


class Composite(unittest.TestCase):
    def test_agreement_is_a_side(self):
        self.assertEqual(bias.composite(["UP", "UP", "UP"]), "UP")
        self.assertEqual(bias.composite(["DOWN", "DOWN"]), "DOWN")

    def test_a_flat_rung_does_not_break_agreement(self):
        """FLAT is not a dissenting vote. One quiet rung above two trending
        ones does not make the ladder undecided about direction."""
        self.assertEqual(bias.composite(["UP", "FLAT", "UP"]), "UP")

    def test_disagreement_is_mixed_and_stays_mixed(self):
        """The user's case: bearish daily over a bullish 4H. Collapsing this
        to whichever rung a tie-break picked would invent a consensus the
        market is explicitly not showing."""
        self.assertEqual(bias.composite(["UP", "DOWN"]), "MIXED")
        self.assertEqual(bias.composite(["DOWN", "FLAT", "UP"]), "MIXED")

    def test_nothing_trending_is_flat(self):
        self.assertEqual(bias.composite(["FLAT", "FLAT"]), "FLAT")

    def test_nothing_measurable_is_unknown(self):
        self.assertEqual(bias.composite([None, None]), "UNKNOWN")
        self.assertEqual(bias.composite([]), "UNKNOWN")

    def test_an_unmeasured_rung_is_skipped_not_counted_as_flat(self):
        """"We did not look" and "we looked and it was quiet" are different
        findings. A None rung must not drag the composite toward FLAT."""
        self.assertEqual(bias.composite([None, "UP"]), "UP")
        self.assertEqual(bias.composite([None, "FLAT"]), "FLAT")


class Alignment(unittest.TestCase):
    def test_with_and_against_follow_the_side(self):
        self.assertEqual(bias.alignment("DOWN", "SHORT"), "WITH")
        self.assertEqual(bias.alignment("DOWN", "LONG"), "AGAINST")
        self.assertEqual(bias.alignment("UP", "LONG"), "WITH")
        self.assertEqual(bias.alignment("UP", "SHORT"), "AGAINST")

    def test_mixed_flat_and_unknown_pass_through_as_themselves(self):
        """None of the three collapses into AGAINST. They are different market
        conditions and a policy has to be able to treat them differently."""
        for comp in ("MIXED", "FLAT", "UNKNOWN"):
            for direction in ("LONG", "SHORT"):
                self.assertEqual(bias.alignment(comp, direction), comp)

    def test_a_nonsense_direction_raises(self):
        with self.assertRaises(ValueError):
            bias.alignment("UP", "SIDEWAYS")


class PolicyValidation(unittest.TestCase):
    OK = {"WITH": "ALLOW", "AGAINST": "REQUIRE_EVIDENCE", "MIXED": "ALLOW",
          "FLAT": "ALLOW", "UNKNOWN": "ALLOW"}

    def test_a_complete_policy_validates_and_is_returned(self):
        self.assertEqual(bias.validate_policy(dict(self.OK)), self.OK)

    def test_unknown_may_never_be_anything_but_allow(self):
        """THE rule. `setups.py` scored a missing HTF reading identically to a
        contrary one: unknown-HTF trades ran 38.9% win / +0.404 R against
        17.2% / -0.616 R for genuinely opposed ones, and the whole 1D book had
        no 1W regime to read. A missing measurement is not a bad one."""
        for bad in ("BLOCK", "REQUIRE_EVIDENCE"):
            with self.subTest(action=bad):
                with self.assertRaises(ValueError) as e:
                    bias.validate_policy({**self.OK, "UNKNOWN": bad})
                self.assertIn("missing measurement", str(e.exception))

    def test_a_policy_silent_on_an_alignment_is_rejected(self):
        """A playbook that has not thought about MIXED has not declared a
        policy, it has declared four fifths of one."""
        partial = {k: v for k, v in self.OK.items() if k != "MIXED"}
        with self.assertRaises(ValueError) as e:
            bias.validate_policy(partial)
        self.assertIn("MIXED", str(e.exception))

    def test_an_unknown_action_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            bias.validate_policy({**self.OK, "WITH": "MAYBE"})

    def test_a_typo_in_an_alignment_name_is_caught(self):
        with self.assertRaises(ValueError):
            bias.validate_policy({**self.OK, "AGAINTS": "ALLOW"})


class Verdict(unittest.TestCase):
    READ = {"composite": "DOWN", "rungs": {"1D": "DOWN"}}
    POLICY = {"WITH": "ALLOW", "AGAINST": "REQUIRE_EVIDENCE", "MIXED": "ALLOW",
              "FLAT": "ALLOW", "UNKNOWN": "ALLOW"}

    def test_with_the_ladder_flows(self):
        v = bias.verdict(self.READ, "SHORT", self.POLICY)
        self.assertEqual((v["alignment"], v["resolved"]), ("WITH", "ALLOW"))

    def test_against_the_ladder_needs_the_permission_slip(self):
        """The user's rule, in one assertion: HTF downtrend, shorts flow,
        longs only on confirmed evidence."""
        blocked = bias.verdict(self.READ, "LONG", self.POLICY, evidence_ok=False)
        allowed = bias.verdict(self.READ, "LONG", self.POLICY, evidence_ok=True)
        self.assertEqual(blocked["resolved"], "BLOCK")
        self.assertEqual(allowed["resolved"], "ALLOW")
        self.assertEqual(blocked["action"], "REQUIRE_EVIDENCE",
                         "the fact must record what the RULE said, not only "
                         "what happened to it")

    def test_an_unasked_evidence_question_is_not_a_satisfied_one(self):
        """`evidence_ok=None` means the caller never looked. Treating that as
        pass would let a filter report itself as applied when it was not."""
        v = bias.verdict(self.READ, "LONG", self.POLICY)
        self.assertEqual(v["resolved"], "BLOCK")

    def test_the_verdict_carries_its_own_version(self):
        self.assertEqual(bias.verdict(self.READ, "SHORT", self.POLICY)["version"],
                         bias.BIAS_VERSION)


class AsOfDiscipline(unittest.TestCase):
    """`confirmed_at` is when the engine could have known. Reading past it is
    lookahead, and a filter validated on lookahead is worth nothing."""

    def setUp(self):
        self.src = bias.Bias("4H", {"1D": [(100, "UP"), (300, "DOWN")],
                                    "1W": [(50, "UP")]},
                             [(200, "UP"), (400, "DOWN")])

    def test_a_reading_never_sees_the_future(self):
        self.assertEqual(self.src.reading(250)["rungs"]["1D"], "UP")
        self.assertEqual(self.src.reading(300)["rungs"]["1D"], "DOWN",
                         "a reading confirmed AT as_of is knowable")
        self.assertEqual(self.src.reading(299)["rungs"]["1D"], "UP")

    def test_a_rung_with_nothing_confirmed_yet_reads_none(self):
        self.assertIsNone(self.src.reading(60)["rungs"]["1D"])
        self.assertEqual(self.src.reading(60)["composite"], "UP",
                         "the 1W rung still had a reading; None is skipped")

    def test_disagreeing_rungs_surface_as_mixed(self):
        self.assertEqual(self.src.reading(350)["composite"], "MIXED")

    def test_evidence_never_sees_the_future(self):
        """The 400 break must be invisible at as_of=350 even though it is in
        the series and in the right direction."""
        self.assertFalse(self.src.evidence("SHORT", 350, 1)["ok"])

    def test_evidence_must_be_recent(self):
        """A break twenty bars back is the prevailing structure, not a change
        in it. `bars_ago` is recorded so the window can be re-tuned on data."""
        tf_seconds = 10
        near = self.src.evidence("LONG", 220, tf_seconds)
        far = self.src.evidence("LONG", 500, tf_seconds)
        self.assertTrue(near["ok"])
        self.assertEqual(near["bars_ago"], 2)
        self.assertFalse(far["ok"])

    def test_evidence_must_be_in_the_trades_direction(self):
        self.assertFalse(self.src.evidence("SHORT", 220, 10)["ok"])
        self.assertTrue(self.src.evidence("LONG", 220, 10)["ok"])

    def test_check_only_looks_for_evidence_when_the_policy_asks(self):
        """A fact must never claim a test was run that was not."""
        allow_all = {a: "ALLOW" for a in bias.ALIGNMENTS}
        self.assertIsNone(self.src.check("LONG", 350, 10, allow_all)["evidence"])
        needs = {**allow_all, "MIXED": "REQUIRE_EVIDENCE"}
        self.assertIsNotNone(self.src.check("LONG", 350, 10, needs)["evidence"])


class Enforcement(unittest.TestCase):
    """The gate exists and works, while every shipped policy leaves it inert.

    A mechanism that has never fired is a mechanism nobody has tested. These
    drive it with a TEST-ONLY policy so the code path is proven without any
    playbook shipping a BLOCK — the alternative is discovering on the day
    someone flips a value that the branch was never exercised.
    """

    BLOCK_ALL_AGAINST = {"WITH": "ALLOW", "AGAINST": "BLOCK", "MIXED": "ALLOW",
                         "FLAT": "ALLOW", "UNKNOWN": "ALLOW"}

    def setUp(self):
        self.src = bias.Bias("4H", {"1D": [(100, "DOWN")], "1W": [(50, "DOWN")]},
                             [])

    def test_a_block_policy_actually_blocks(self):
        out = self.src.check("LONG", 200, 1, self.BLOCK_ALL_AGAINST)
        self.assertEqual(out["alignment"], "AGAINST")
        self.assertTrue(bias.blocked(out))

    def test_the_same_reading_allows_the_other_side(self):
        out = self.src.check("SHORT", 200, 1, self.BLOCK_ALL_AGAINST)
        self.assertEqual(out["alignment"], "WITH")
        self.assertFalse(bias.blocked(out))

    def test_blocked_is_the_one_place_the_question_is_asked(self):
        """No engine may spell `== "BLOCK"` inline — four call sites agreeing
        until one of them does not is how a rule quietly forks."""
        import inspect

        from engine import breakout, setups, trend
        for mod in (setups, trend, breakout):
            with self.subTest(engine=mod.__name__):
                src = inspect.getsource(mod)
                self.assertIn("bias.blocked(", src)
                self.assertNotIn('== "BLOCK"', src)

    def test_the_block_reason_is_canonical_and_has_a_funnel_sentence(self):
        """A gate whose refusals have no vocabulary reaches the operator as a
        raw enum the first time it fires."""
        self.assertEqual(bias.BLOCK_REASON, "BIAS_BLOCKED")
        self.assertIn(bias.BLOCK_REASON, setups.REJECTION_REASONS)
        funnel = (pathlib.Path(inspect.getfile(setups)).parents[1]
                  / "static" / "funnel.js").read_text(encoding="utf-8")
        self.assertIn(f"{bias.BLOCK_REASON}:", funnel)

    def test_every_playbook_records_a_refusal_as_a_fact(self):
        """§8 — a rejection is as auditable as an approval. For the two
        measurement engines this matters more than for the live book: their
        product IS the sample, so a gate that shrinks it silently is worse
        than one that shrinks it loudly."""
        import inspect

        from engine import breakout, setups, trend
        for mod in (setups, trend, breakout):
            with self.subTest(engine=mod.__name__):
                src = inspect.getsource(mod)
                i = src.find("bias.blocked(")
                self.assertGreater(i, 0)
                window = src[i:i + 1200]
                self.assertTrue(
                    "setup_rejection" in window or "reject(" in window,
                    f"{mod.__name__} blocks without recording why")


class PlaybookRoster(unittest.TestCase):
    """Every setup-emitting engine must declare how it treats the ladder.

    This is the claim that the layer is modular rather than two special cases.
    A new playbook that ships without a `BIAS_POLICY` fails here, the same way
    an unknown `pipeline.GATES` name raises: the decision is forced at the
    moment it is cheap, instead of being noticed a version later.
    """

    #: Playbooks that emit setup facts and do NOT yet declare a policy, each
    #: with the reason. Emptying this is step 3 of the plan; anything NEW
    #: appearing in it is a playbook that skipped the decision.
    PENDING = {
        # Its adds inherit the parent's bracket and already answer to the
        # strictest HTF rule in the system (no add without an open 4H/1D
        # parent in the direction), so a second policy here would be a second
        # authority over the same question. Recorded in scalein.py's version
        # note as well, so the reason travels with the code and not only with
        # this set.
        "scalein",
    }

    def _setup_emitting_modules(self):
        root = pathlib.Path(inspect.getfile(bias)).parent
        out = []
        for path in sorted(root.glob("*.py")):
            src = path.read_text(encoding="utf-8")
            if 'kind="setup"' in src and "insert_fact" in src:
                out.append(path.stem)
        return out

    def test_the_roster_is_found_at_all(self):
        """If the scan returns nothing the guard below passes vacuously, which
        is worse than not having it."""
        found = self._setup_emitting_modules()
        for expected in ("setups", "trend", "breakout", "scalein"):
            self.assertIn(expected, found)

    def test_every_playbook_declares_a_policy_or_is_named_as_pending(self):
        import importlib
        for name in self._setup_emitting_modules():
            with self.subTest(playbook=name):
                mod = importlib.import_module(f"engine.{name}")
                if hasattr(mod, "BIAS_POLICY"):
                    bias.validate_policy(mod.BIAS_POLICY, who=f"{name}.BIAS_POLICY")
                    self.assertNotIn(name, self.PENDING,
                                     "declared a policy but is still listed as "
                                     "pending — remove it from PENDING")
                else:
                    self.assertIn(
                        name, self.PENDING,
                        f"{name} emits setup facts but declares no BIAS_POLICY. "
                        f"Every playbook must say how it treats the timeframes "
                        f"above it — add one (ALLOW everywhere is a valid "
                        f"answer and the right default) or add it to PENDING "
                        f"with the reason.")

    def test_the_wired_playbooks_are_record_only_for_now(self):
        """Recording must not change a single trade. If a policy here stops
        being ALLOW everywhere, that is enforcement and it needs its own grade
        — per playbook, because the grade says the two kinds want opposite
        answers (bias.py holds the table)."""
        for mod in (setups, trend, breakout):
            with self.subTest(playbook=mod.__name__):
                self.assertEqual(set(mod.BIAS_POLICY.values()), {"ALLOW"})


if __name__ == "__main__":
    unittest.main()
