"""The lock that had no key.

`live_enabled` was a hardcoded False beside the sentence "Forward paper
evidence has not yet earned live execution". The UI printed that on two
surfaces and nothing in the system defined the condition it named — no trade
count, no expectancy bar, no drawdown ceiling, no progress. The app's stated
purpose sat behind a door with no handle (UX audit, 4 Aug 2026).

These tests pin the four things that must stay true of the replacement:

  1. The bar is the HOUSE bar — a confidence interval that clears zero, the
     same test that keeps `breakout` measured-and-not-enabled.
  2. Evidence earned is never permission to send an order. Two verdicts, two
     failure modes, two different people who fix them.
  3. Scope is forward-only. Grading on the 390-trade recorded book would
     answer a question about a strategy that no longer exists.
  4. Every criterion is a number that MOVES, because "how close am I" is the
     only question worth asking of a lock.
"""
import tempfile
import unittest
from pathlib import Path

from engine import livegate, store


def _journal(rs):
    return [{"r_multiple": r} for r in rs]


class LiveGateCase(unittest.TestCase):
    def setUp(self):
        # A real file, like every other suite here: store.connect mkdirs the
        # parent, so ":memory:" is not a path it accepts.
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _eval(self, rs, dd=1.0, quality="PASS", **kw):
        return livegate.evaluate(self.con, journal=_journal(rs),
                                 max_drawdown_pct=dd, quality_status=quality,
                                 **kw)

    # ---------------------------------------------------------------- shape
    def test_every_criterion_is_a_number_that_moves(self):
        g = self._eval([0.5] * 40)
        self.assertEqual(len(g["criteria"]), 4)
        for c in g["criteria"]:
            self.assertIn("have", c, f"{c['key']} shows no measured value")
            self.assertIn("need", c, f"{c['key']} shows no target")
            self.assertIsInstance(c["progress"], float)
            self.assertGreaterEqual(c["progress"], 0.0)
            self.assertLessEqual(c["progress"], 1.0)
            self.assertTrue(c["note"], f"{c['key']} has no explanation")

    def test_sample_progress_is_a_real_fraction(self):
        g = self._eval([0.1] * 25)
        s = next(c for c in g["criteria"] if c["key"] == "sample")
        self.assertEqual(s["have"], 25)
        self.assertEqual(s["need"], livegate.MIN_FORWARD_TRADES)
        self.assertAlmostEqual(s["progress"], 25 / livegate.MIN_FORWARD_TRADES)
        self.assertFalse(s["pass"])

    # ----------------------------------------------------------- the bar
    def test_edge_uses_the_house_bar_not_the_mean(self):
        """A positive average is not an edge. The lower bound must clear zero.

        This is the whole reason `breakout` ships disabled with a mean of
        -0.076 R and a CI spanning zero: the house does not act on a point
        estimate. A gate that unlocked real money on `mean > 0` would be a
        different and much weaker promise than the one the app makes
        everywhere else.
        """
        # Mean is clearly positive, but the spread is enormous, so the 95%
        # interval straddles zero.
        noisy = [8.0, -7.0] * 30 + [0.4]
        g = self._eval(noisy)
        edge = next(c for c in g["criteria"] if c["key"] == "edge")
        self.assertGreater(sum(noisy) / len(noisy), 0,
                           "fixture is wrong: the mean should be positive")
        self.assertLess(edge["ci_lo"], 0)
        self.assertFalse(edge["pass"],
                         "a positive MEAN unlocked the gate — the bar is the "
                         "lower bound of the interval, not the average")

    def test_a_clean_positive_record_passes_the_edge(self):
        g = self._eval([0.9, 1.1] * 40)
        edge = next(c for c in g["criteria"] if c["key"] == "edge")
        self.assertTrue(edge["pass"])
        self.assertGreater(edge["ci_lo"], 0)

    def test_too_few_trades_is_not_measurable_rather_than_failed(self):
        g = self._eval([1.0] * 5)
        edge = next(c for c in g["criteria"] if c["key"] == "edge")
        self.assertIsNone(edge["ci_lo"])
        self.assertFalse(edge["pass"])
        self.assertIn("Not measurable", edge["note"])

    def test_bootstrap_is_deterministic(self):
        """Two runs over identical data must agree, or the bar moves on its own."""
        rs = [0.7, -1.0, 1.4, 0.2] * 15
        a = self._eval(rs)["criteria"][1]
        b = self._eval(rs)["criteria"][1]
        self.assertEqual(a["ci_lo"], b["ci_lo"])
        self.assertEqual(a["ci_hi"], b["ci_hi"])

    # --------------------------------------------------------- the guardrails
    def test_drawdown_is_graded_against_the_operators_own_limit(self):
        from engine import settings
        limit = float(settings.all_settings(self.con)["max_drawdown_pct"])
        ok = self._eval([0.1] * 12, dd=limit - 0.01)
        bad = self._eval([0.1] * 12, dd=limit + 0.01)
        self.assertTrue(next(c for c in ok["criteria"] if c["key"] == "drawdown")["pass"])
        self.assertFalse(next(c for c in bad["criteria"] if c["key"] == "drawdown")["pass"])

    def test_blocked_data_fails_the_gate(self):
        g = self._eval([1.0] * 12, quality="BLOCKED")
        q = next(c for c in g["criteria"] if c["key"] == "quality")
        self.assertFalse(q["pass"])
        self.assertFalse(g["ready"])

    def test_degraded_data_does_not_fail_the_gate(self):
        """DEGRADED is the app's normal working state; only BLOCKED stops it."""
        q = next(c for c in self._eval([1.0] * 12, quality="DEGRADED")["criteria"]
                 if c["key"] == "quality")
        self.assertTrue(q["pass"])

    # ------------------------------------------------------------ the promise
    def test_ready_requires_every_criterion(self):
        good = [0.9, 1.1] * (livegate.MIN_FORWARD_TRADES // 2)
        self.assertTrue(self._eval(good)["ready"])
        # any single failure takes it down
        self.assertFalse(self._eval(good, quality="BLOCKED")["ready"])
        self.assertFalse(self._eval(good, dd=99.0)["ready"])
        self.assertFalse(self._eval(good[:20])["ready"])

    def test_ready_is_never_permission_to_send_an_order(self):
        """The two verdicts must not merge.

        Folding "the evidence is good" into "you may trade" is how the Arm
        button came to be wired to a live flag and stayed dead for months.
        The operator moves the evidence bar by trading the paper book; only a
        deliberate build unlocks the mainnet router, and no amount of good
        trading opens that lock.
        """
        g = self._eval([0.9, 1.1] * (livegate.MIN_FORWARD_TRADES // 2))
        self.assertTrue(g["ready"])
        self.assertFalse(g["enabled"],
                         "a passing evidence bar enabled live execution — "
                         "mainnet routing is build-locked and must stay so")
        self.assertTrue(g["blocked_by_build"])
        self.assertIn("order", g["build_note"].lower())

    def test_the_headline_names_what_is_missing(self):
        g = self._eval([0.1] * 3)
        self.assertIn("of 4 met", g["headline"])
        self.assertIn("forward trades closed", g["headline"].lower())

    # ------------------------------------------------------------- the reset
    def test_a_strategy_bump_explains_its_own_zero(self):
        """Watched live: a parallel session shipped setup-v0.16 and the count
        fell from 7 to 0 within the hour. Correct — the forward record is
        evidence about the rules that made it — but a counter that silently
        resets reads as a bug."""
        g = self._eval([1.0] * 7,
                       baseline={"strategy_version": "setup-v0.13-draft"},
                       strategy_version="setup-v0.16-draft")
        s = next(c for c in g["criteria"] if c["key"] == "sample")
        self.assertTrue(s["baseline_restarted"])
        self.assertIn("setup-v0.16-draft", s["note"])
        self.assertIn("setup-v0.13-draft", s["note"])

    def test_matching_versions_do_not_claim_a_restart(self):
        g = self._eval([1.0] * 7,
                       baseline={"strategy_version": "setup-v0.16-draft"},
                       strategy_version="setup-v0.16-draft")
        s = next(c for c in g["criteria"] if c["key"] == "sample")
        self.assertFalse(s["baseline_restarted"])

    def test_it_writes_nothing(self):
        """Read-only: a gate that recorded facts would grade its own evidence."""
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self._eval([0.5] * 30)
        self.assertEqual(before,
                         self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
