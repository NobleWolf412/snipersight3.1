"""The guards that stop a strategy grade from being a confident wrong number.

A grader is only worth having if it can say no. These pin the four ways this
one is built to say no — clustered rather than IID intervals, a multiplicity
correction, a floor on clusters as well as trades, and a hard refusal when the
harness cannot reproduce the book it already has.

None of this touches the store, the app, or a live endpoint: every case builds
its own rows.
"""
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import abtest, edgestats, strategygrade   # noqa: E402


def _rows(per_symbol: dict) -> list[dict]:
    return [{"symbol": sym, "r": r} for sym, rs in per_symbol.items() for r in rs]


class ClusterBootstrap(unittest.TestCase):
    """Resampling symbols, not trades."""

    def test_correlated_symbols_widen_the_interval(self):
        """THE WHOLE POINT. Forty alts turning with BTC is one market move, not
        forty facts. Same trades, same mean; the clustered interval must be
        wider than the IID one because it stops counting a repeated move as
        repeated evidence."""
        # Eight symbols, each internally consistent (one "move" per symbol),
        # disagreeing with each other — the shape correlation actually takes.
        per_symbol = {f"S{i}": [0.9] * 12 if i % 2 else [-0.9] * 12
                      for i in range(8)}
        rows = _rows(per_symbol)
        vals = [r["r"] for r in rows]

        iid = edgestats._bootstrap_mean(vals, 2000)
        clustered = abtest._cluster_bootstrap(rows, 2000)
        self.assertIsNotNone(clustered)
        iid_width = iid["ci_hi"] - iid["ci_lo"]
        cl_width = clustered["ci_hi"] - clustered["ci_lo"]
        self.assertGreater(
            cl_width, iid_width,
            "the clustered interval is not wider than the IID one on perfectly "
            "correlated within-symbol data — the correction is not correcting")

    def test_it_is_deterministic(self):
        """Same data, same interval, byte for byte (the repo forbids a result
        that moves between runs of the same input)."""
        rows = _rows({f"S{i}": [0.4, -0.2, 0.7, -1.0] for i in range(10)})
        a = abtest._cluster_bootstrap(rows, 500)
        b = abtest._cluster_bootstrap(rows, 500)
        self.assertEqual(a, b)

    def test_too_few_symbols_returns_no_interval(self):
        """Four hundred trades on three symbols is three observations. The
        honest answer is no answer, not a tight interval around a coincidence."""
        rows = _rows({f"S{i}": [0.5] * 200 for i in range(3)})
        self.assertGreaterEqual(len(rows), edgestats.MIN_TRADES)
        self.assertIsNone(
            abtest._cluster_bootstrap(rows, 200),
            "a verdict was produced from fewer clusters than MIN_CLUSTERS")

    def test_enough_symbols_but_too_few_trades_returns_no_interval(self):
        """The mirror: the trade floor still applies. Both must clear."""
        rows = _rows({f"S{i}": [0.5] for i in range(abtest.MIN_CLUSTERS)})
        self.assertLess(len(rows), edgestats.MIN_TRADES)
        self.assertIsNone(abtest._cluster_bootstrap(rows, 200))


class Multiplicity(unittest.TestCase):
    """Grading five playbooks and promoting the luckiest is not evidence."""

    def test_holm_scales_with_how_many_were_tested(self):
        alone = strategygrade._holm({"A": 0.02})
        crowd = strategygrade._holm({"A": 0.02, "B": 0.4, "C": 0.6,
                                     "D": 0.8, "E": 0.9})
        self.assertAlmostEqual(alone["A"], 0.02, places=4)
        self.assertGreater(
            crowd["A"], alone["A"],
            "the same p-value survives unchanged when five playbooks were "
            "graded — looking five times is being treated as looking once")

    def test_holm_is_monotone(self):
        """A worse raw p may never come out better than a stronger one."""
        adj = strategygrade._holm({"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.9})
        seq = [adj[k] for k in ("A", "B", "C", "D")]
        self.assertEqual(seq, sorted(seq),
                         f"adjusted p-values are not monotone: {seq}")

    def test_holm_is_never_more_lenient_than_the_raw_value(self):
        raw = {"A": 0.001, "B": 0.049, "C": 0.5}
        adj = strategygrade._holm(raw)
        for k in raw:
            self.assertGreaterEqual(adj[k], raw[k])

    def test_empty_input_is_not_an_error(self):
        self.assertEqual(strategygrade._holm({}), {})


class RefusalPaths(unittest.TestCase):
    """What it does when it cannot answer."""

    def test_untrustworthy_calibration_prints_no_numbers(self):
        """If the harness cannot rebuild a book it has, it is not evidence
        about one it has not. The refusal must not leak the table anyway."""
        text = strategygrade._render({
            "version": "abtest-vX",
            "trustworthy": False,
            "calibration": {"status": "MISMATCH",
                            "detail": "3 of 598 differ by more than 0.01 R"},
            "strategies": {"PULLBACK": {"n": 999, "expectancy_r": 9.99,
                                        "sample_ok": True, "clusters": 40,
                                        "cluster_ci_lo": 1.0,
                                        "cluster_ci_hi": 2.0,
                                        "ci_lo": 1.0, "ci_hi": 2.0,
                                        "fill_pct": 100.0, "p_adjusted": 0.0,
                                        "verdict": "POSITIVE_EDGE",
                                        "survives_correction": True}},
            "strategies_tested": 1,
            "bar": "x",
        })
        self.assertIn("NO VERDICT", text)
        self.assertIn("3 of 598 differ", text,
                      "the refusal does not say what failed")
        for leaked in ("PULLBACK", "9.99", "POSITIVE_EDGE"):
            self.assertNotIn(leaked, text,
                             f"{leaked!r} printed through an untrustworthy "
                             "calibration — the table leaked past the refusal")

    def test_rendered_output_is_ascii(self):
        """A Windows console is cp1252 and this repo has paid for that twice.
        The stream is reconfigured to UTF-8 in main(), and the lines this module
        writes are ASCII as well — two independent defences, and this pins the
        second one."""
        text = strategygrade._render({
            "version": "abtest-v0.2", "trustworthy": True,
            "calibration": {"status": "OK", "detail": "reproduced"},
            "strategies": {
                "A": {"n": 50, "clusters": 12, "fill_pct": 90.0,
                      "expectancy_r": 0.1, "sample_ok": True,
                      "cluster_ci_lo": 0.01, "cluster_ci_hi": 0.2,
                      "ci_lo": 0.02, "ci_hi": 0.19, "p_adjusted": 0.01,
                      "verdict": "POSITIVE_EDGE", "survives_correction": True},
                "B": {"n": 4, "clusters": None, "fill_pct": None,
                      "expectancy_r": -0.5, "sample_ok": False,
                      "cluster_ci_lo": None, "cluster_ci_hi": None,
                      "ci_lo": None, "ci_hi": None, "p_adjusted": None,
                      "verdict": "INSUFFICIENT", "survives_correction": False},
            },
            "strategies_tested": 1, "bar": "the bar",
        })
        bad = sorted({c for c in text if ord(c) > 127})
        self.assertEqual(bad, [], f"non-ASCII in rendered output: {bad}")

    def test_mixed_entry_models_refuse_loudly(self):
        text = strategygrade._render({
            "version": "abtest-v0.3", "trustworthy": False,
            "calibration": {"status": "OK", "detail": "reproduced"},
            "entry_model_conflicts": {
                "setup-vX": "setup-vX records multiple entry models: "
                            "DIRECT_LIMIT, MAKER_THEN_MARKET"},
            "strategies": {"PULLBACK": {"expectancy_r": 9.99}},
        })
        self.assertIn("NO VERDICT", text)
        self.assertIn("more than one entry model", text)
        self.assertNotIn("PULLBACK", text)

    def test_degraded_replay_fill_is_visible_before_the_grade(self):
        text = strategygrade._render({
            "version": "abtest-v0.3", "trustworthy": True,
            "calibration": {"status": "OK", "detail": "reproduced"},
            "replay_degradations": [{"symbol": "TESTUSDT", "tf": "1H",
                                      "note": "cross slippage NOT applied"}],
            "bar": "x", "strategies_tested": 0, "strategies": {},
        })
        self.assertIn("WARNING: 1 replay fill", text)
        self.assertIn("slippage NOT applied", text)

    def test_the_correction_caveat_blames_only_what_it_should(self):
        """An INDISTINGUISHABLE row must not be annotated as having been killed
        by the correction — its interval covered zero on its own, and saying
        otherwise reads as 'there was an edge and statistics took it away'."""
        base = {"n": 80, "clusters": 20, "fill_pct": 100.0, "sample_ok": True,
                "ci_lo": -0.3, "ci_hi": 0.2, "p_adjusted": 0.9}
        text = strategygrade._render({
            "version": "v", "trustworthy": True,
            "calibration": {"status": "OK", "detail": "d"},
            "strategies": {"FLAT": {**base, "expectancy_r": -0.01,
                                    "cluster_ci_lo": -0.3, "cluster_ci_hi": 0.2,
                                    "verdict": "INDISTINGUISHABLE",
                                    "survives_correction": False}},
            "strategies_tested": 4, "bar": "b",
        })
        self.assertNotIn("but not after correcting", text)


class GradeIsNotAPromotion(unittest.TestCase):
    """The surface must stay read-only, and must not become the button."""

    def test_it_writes_nothing_and_enables_nothing(self):
        src = (APP / "engine" / "strategygrade.py").read_text(encoding="utf-8")
        for forbidden in ("insert_fact", "set_many", "plan_versions()  =",
                          "start_baseline"):
            self.assertNotIn(forbidden, src,
                             f"the grader calls {forbidden!r} — grading a "
                             "strategy must not change what the engine does")

    def test_the_traded_set_is_still_only_pullback_and_reversal(self):
        """A companion pin to the version-cascade lockfile: if someone widens
        the whitelist because a grade looked good, this fails and points at the
        cascade they also owe."""
        from engine import execsim, scalein
        from engine.setups import SETUP_VERSION
        self.assertEqual(execsim.plan_versions(),
                         (SETUP_VERSION, scalein.SCALE_VERSION),
                         "the traded version set changed — a promotion "
                         "happened, and it owes a version cascade plus the "
                         "hardcoded tuples in server.py")


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
