"""Factor-grading diagnostics. The properties tested here are the ones that would
have caught the previous project's 26-factors-that-were-really-5 failure: that a
duplicated signal is named as duplicated, that a factor which says the same thing
every time is called out, that a correlation inside the noise floor earns no credit,
and that a factor scoring high on losers is reported rather than swallowed.
"""
import json
import tempfile
import unittest
from pathlib import Path

from engine import execsim, factorstats, setups, store


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.con = store.connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


def candidates(rows):
    """Build the shape `analyze` consumes without touching the store: each row is
    (payload_extras, realised_r_or_None)."""
    out = []
    for i, (extra, r) in enumerate(rows):
        out.append({"setup_id": f"s{i}", "symbol": "BTC-USD", "tf": "1D",
                    "market_time": i, "confirmed_at": i + 1,
                    "payload": {"setup_id": f"s{i}", "rank": 50, **extra},
                    "outcome": "SL" if (r or 0) < 0 else "TP", "r": r})
    return out


class TestRedundancy(unittest.TestCase):
    def test_perfectly_correlated_pair_is_flagged_redundant(self):
        """Two names, one signal. `b` is `a` on a different scale — the exact shape
        of the 26-factor problem, where 'HTF trend', 'regime' and 'BTC bias' were
        three readings of one moving average."""
        rows = [({"a": float(i % 7), "noise": float((i * 5) % 11)}, None)
                for i in range(60)]

        def factors(p):
            return {"a": p["a"], "b": p["a"] * 3.0 + 1.0, "noise": p["noise"]}

        res = factorstats.analyze(candidates(rows), factors=factors,
                                  composite=lambda p: None)
        pair = [q for q in res["redundant_pairs"] if {q["a"], q["b"]} == {"a", "b"}]
        self.assertEqual(len(pair), 1)
        self.assertAlmostEqual(pair[0]["r"], 1.0, places=6)
        self.assertIn(["a", "b"], res["clusters"])
        self.assertEqual(len(res["redundant"]), 1)
        self.assertIn(res["redundant"][0], ("a", "b"))
        self.assertTrue(res["stats"][res["redundant"][0]]["verdict"]
                        .startswith("REDUNDANT"))
        # 3 declared names, 2 actual signals — the headline number that matters.
        self.assertEqual(res["raw_factor_count"], 3)
        self.assertEqual(res["effective_independent_factors"], 2)

    def test_independent_factors_are_not_merged(self):
        rows = [({"a": float(i % 7), "b": float((i * 3) % 5)}, None) for i in range(60)]
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"a": p["a"], "b": p["b"]},
            composite=lambda p: None)
        self.assertEqual(res["redundant_pairs"], [])
        self.assertEqual(res["redundant"], [])
        self.assertEqual(res["effective_independent_factors"], 2)

    def test_redundancy_is_transitive_across_a_cluster(self):
        """A~B and B~C means all three read one thing, even when A and C never touch
        directly. Without transitivity the count of 'independent' factors is inflated
        exactly where it hurts most."""
        rows = [({"x": float(i % 9)}, None) for i in range(60)]

        def factors(p):
            x = p["x"]
            return {"a": x, "b": x * 2.0, "c": x * -4.0 + 3.0}

        res = factorstats.analyze(candidates(rows), factors=factors,
                                  composite=lambda p: None)
        self.assertEqual(res["clusters"], [["a", "b", "c"]])
        self.assertEqual(res["effective_independent_factors"], 1)
        self.assertEqual(len(res["redundant"]), 2)


class TestDispersion(unittest.TestCase):
    def test_constant_factor_is_flagged_zero_dispersion(self):
        rows = [({"v": float(i % 13)}, None) for i in range(60)]

        def factors(p):
            return {"always_one": 1.0, "varies": p["v"]}

        res = factorstats.analyze(candidates(rows), factors=factors,
                                  composite=lambda p: None)
        s = res["stats"]["always_one"]
        self.assertEqual(s["structural"], "ZERO_DISPERSION")
        self.assertTrue(s["verdict"].startswith("ZERO_DISPERSION"))
        self.assertEqual(s["std_all"], 0.0)
        self.assertEqual(s["fire_rate"], 1.0)
        # A constant cannot be redundant with anything — correlation is undefined,
        # and reporting it as an overlap would be a second wrong answer.
        self.assertNotIn("always_one", res["redundant"])
        self.assertIsNone(res["stats"]["always_one"]["r_outcome"])

    def test_binary_flag_is_not_mistaken_for_zero_dispersion(self):
        """A 0/1 flag is constant *when present* by construction. Grading it on that
        alone would condemn every boolean confluence factor in the system."""
        rows = [({"i": i}, None) for i in range(60)]
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"flag": 1.0 if p["i"] % 2 else 0.0},
            composite=lambda p: None)
        s = res["stats"]["flag"]
        self.assertEqual(s["std_when_present"], 0.0)
        self.assertIsNone(s["structural"])
        self.assertAlmostEqual(s["fire_rate"], 0.5, places=6)

    def test_rare_factor_is_flagged_rare(self):
        rows = [({"i": i}, None) for i in range(100)]
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"rare": 1.0 if p["i"] < 4 else 0.0},
            composite=lambda p: None)
        self.assertEqual(res["stats"]["rare"]["structural"], "RARE")

    def test_missing_is_not_imputed_as_zero(self):
        """An omitted key means "never recorded", not "recorded as zero". Imputing
        would invent observations and drag every correlation toward the imputed
        value."""
        rows = [({"i": i}, None) for i in range(60)]

        def factors(p):
            return {"sparse": 80.0} if p["i"] % 2 else {}

        res = factorstats.analyze(candidates(rows), factors=factors,
                                  composite=lambda p: None)
        s = res["stats"]["sparse"]
        self.assertEqual(s["n_observed"], 30)
        self.assertAlmostEqual(s["coverage"], 0.5, places=6)
        self.assertEqual(s["std_all"], 0.0)          # constant where it IS observed
        self.assertEqual(s["structural"], "ZERO_DISPERSION")


class TestOutcomeEdge(unittest.TestCase):
    def _rows(self, n, fn):
        return [({"i": i}, fn(i)) for i in range(n)]

    def test_small_sample_refuses_to_report_a_correlation(self):
        """Loud fallback: below MIN_TRADES the honest output is 'unknown'. The prior
        project's worst calls all came from trusting r on a dozen trades."""
        rows = self._rows(20, lambda i: 1.0 if i % 2 else -1.0)
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"f": float(p["i"] % 2)},
            composite=lambda p: None)
        self.assertFalse(res["outcome_sample_ok"])
        self.assertIsNone(res["noise_floor"])
        self.assertIsNone(res["stats"]["f"]["r_outcome"])
        self.assertTrue(res["stats"]["f"]["verdict"].startswith("UNPROVEN"))
        self.assertTrue(any("outcome edge NOT reported" in w
                            for w in res["warnings"]))

    def test_weak_correlation_under_the_noise_floor_is_not_credited(self):
        """r != 0 is not edge. At n=120 the floor is ±0.18; a factor sitting under it
        is indistinguishable from a coin and must not be reported as predictive."""
        # Deterministic near-orthogonal pairing: R cycles independently of the factor.
        rows = [({"i": i}, [(-1.0), 2.0, -1.0, 2.0, -1.0][i % 5]) for i in range(120)]
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"f": float(p["i"] % 7)},
            composite=lambda p: None)
        s = res["stats"]["f"]
        self.assertTrue(res["outcome_sample_ok"])
        self.assertLess(abs(s["r_outcome"]), res["noise_floor"])
        self.assertFalse(s["clears_noise_floor"])
        self.assertTrue(s["verdict"].startswith("NOISE"))
        self.assertNotIn("EDGE", s["verdict"])

    def test_factor_that_scores_high_on_losers_reports_negative_r(self):
        """A negative r is a finding, not a bug: the factor is actively steering the
        book into losses and the verdict has to say so out loud."""
        rows = [({"i": i}, (-2.0 if i % 2 else 1.5)) for i in range(120)]

        def factors(p):
            # high (10) on every loser, low (1) on every winner
            return {"misleading": 10.0 if p["i"] % 2 else 1.0}

        res = factorstats.analyze(candidates(rows), factors=factors,
                                  composite=lambda p: None)
        s = res["stats"]["misleading"]
        self.assertLess(s["r_outcome"], 0)
        self.assertTrue(s["clears_noise_floor"])
        self.assertTrue(s["verdict"].startswith("ANTI"))
        self.assertIn("LOSERS", s["verdict"])

    def test_genuine_predictor_clears_the_floor_and_is_credited(self):
        rows = [({"i": i}, (1.5 if i % 2 else -2.0)) for i in range(120)]
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"good": 10.0 if p["i"] % 2 else 1.0},
            composite=lambda p: None)
        s = res["stats"]["good"]
        self.assertGreater(s["r_outcome"], 0)
        self.assertTrue(s["clears_noise_floor"])
        self.assertTrue(s["verdict"].startswith("EDGE"))

    def test_noise_floor_matches_the_published_formula(self):
        self.assertAlmostEqual(factorstats.noise_floor(100), 0.196, places=6)
        self.assertIsNone(factorstats.noise_floor(0))


class TestContribution(unittest.TestCase):
    def test_shares_sum_to_one_when_the_composite_is_the_factor_sum(self):
        rows = [({"a": float(i % 7), "b": float((i * 3) % 5)}, None) for i in range(60)]
        res = factorstats.analyze(
            candidates(rows), factors=lambda p: {"a": p["a"], "b": p["b"]},
            composite=lambda p: p["a"] + p["b"])
        self.assertAlmostEqual(res["contribution_share_sum"], 1.0, places=5)

    def test_duplicated_factor_makes_the_share_sum_exceed_one(self):
        """The double-counting alarm. Adding a copy of `a` under a new name does not
        add information, but it does add another full share of the same variance."""
        rows = [({"a": float(i % 7), "b": float((i * 3) % 5)}, None) for i in range(60)]
        res = factorstats.analyze(
            candidates(rows),
            factors=lambda p: {"a": p["a"], "a_again": p["a"], "b": p["b"]},
            composite=lambda p: p["a"] + p["b"])
        self.assertGreater(res["contribution_share_sum"], 1.5)
        self.assertTrue(any("double-counting" in w for w in res["warnings"]))


class TestDeterminism(TempStore):
    def test_identical_input_gives_byte_identical_output(self):
        rows = [({"i": i}, (1.0 if i % 3 else -1.0)) for i in range(120)]
        cands = candidates(rows)

        def factors(p):
            return {"a": float(p["i"] % 5), "b": float(p["i"] % 5) * 2.0,
                    "c": float((p["i"] * 7) % 11)}

        first = json.dumps(factorstats.analyze(cands, factors=factors,
                                               composite=lambda p: None),
                           sort_keys=True)
        second = json.dumps(factorstats.analyze(list(reversed(list(reversed(cands)))),
                                                factors=factors,
                                                composite=lambda p: None),
                            sort_keys=True)
        self.assertEqual(first, second)

    def test_report_over_a_real_store_is_stable_and_writes_nothing(self):
        self._seed()
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        a = json.dumps(factorstats.report(self.con), sort_keys=True)
        b = json.dumps(factorstats.report(self.con), sort_keys=True)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertEqual(a, b)
        self.assertEqual(before, after)       # READ-ONLY: not one new fact

    def _seed(self):
        for i in range(40):
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1D", kind="setup",
                market_time=i * 86400, confirmed_at=i * 86400 + 3600,
                algo_version=setups.SETUP_VERSION,
                payload={"setup_id": f"s{i}", "strategy": "PULLBACK",
                         "direction": "LONG" if i % 2 else "SHORT",
                         "entry": "100", "sl": "95", "tp": "110",
                         "rr": str(1.5 + (i % 4)), "rank": 50 + (i % 3) * 15,
                         "regime": "BULL_TREND" if i % 2 else "BEAR_TREND",
                         "state": "VALIDATED",
                         "why": "BULL_TREND regime · pullback into DEMAND zone"
                                + (" · high volume at touch" if i % 3 else "")})
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1D", kind="exec",
                market_time=i * 86400, confirmed_at=i * 86400 + 7200,
                algo_version=execsim.EXEC_VERSION,
                payload={"setup_id": f"s{i}", "outcome": "TP" if i % 2 else "SL",
                         "r_multiple": "2.0" if i % 2 else "-1.1"})
        self.con.commit()


class TestStoreJoin(TempStore):
    def test_outcome_confirmed_before_its_setup_is_refused_not_used(self):
        """Causality (house convention 2). An exec fact that predates its setup means
        the join is wrong; using it would make the whole outcome axis fiction."""
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="setup",
            market_time=1000, confirmed_at=5000,
            algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "backwards", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                     "rr": "2", "rank": 65, "regime": "BULL_TREND",
                     "state": "VALIDATED", "why": "x"})
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="exec",
            market_time=1000, confirmed_at=4000,
            algo_version=execsim.EXEC_VERSION,
            payload={"setup_id": "backwards", "outcome": "TP", "r_multiple": "3.0"})
        cands, warns = factorstats.load_candidates(self.con)
        self.assertEqual(len(cands), 1)
        self.assertIsNone(cands[0]["r"])
        self.assertTrue(any("confirmed BEFORE" in w for w in warns))

    def test_missed_orders_are_excluded_from_the_outcome_axis(self):
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="setup",
            market_time=1000, confirmed_at=2000,
            algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "never-filled", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                     "rr": "2", "rank": 65, "regime": "BULL_TREND",
                     "state": "VALIDATED", "why": "x"})
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1D", kind="exec",
            market_time=1000, confirmed_at=3000,
            algo_version=execsim.EXEC_VERSION,
            payload={"setup_id": "never-filled", "outcome": "MISSED",
                     "r_multiple": "0"})
        cands, warns = factorstats.load_candidates(self.con)
        self.assertIsNone(cands[0]["r"])
        self.assertEqual(cands[0]["outcome"], "MISSED")
        self.assertTrue(any("MISSED" in w for w in warns))

    def test_empty_store_says_so_rather_than_reporting_zeros(self):
        res = factorstats.report(self.con)
        self.assertEqual(res["n_candidates"], 0)
        self.assertEqual(res["stats"], {})
        self.assertFalse(res["outcome_sample_ok"])
        self.assertTrue(any("nothing to grade" in w for w in res["warnings"]))


class TestDefaultExtractor(unittest.TestCase):
    def test_only_fields_setup_v06_actually_emits_are_read(self):
        payload = {"rr": "3.45", "rank": 65, "regime": "BEAR_TREND",
                   "direction": "SHORT", "strategy": "PULLBACK", "tf": "1D",
                   "zone_strength": 82,
                   "why": "BEAR_TREND regime · pullback into SUPPLY zone "
                          "· liquidity sweep nearby · R:R 3.45"}
        f = factorstats.default_factors(payload)
        self.assertEqual(f["rr"], 3.45)
        self.assertEqual(f["rr_good"], 1.0)
        self.assertEqual(f["rank"], 65.0)
        self.assertEqual(f["zone_strength"], 82.0)
        self.assertEqual(f["regime_ordinal"], -2.0)
        self.assertEqual(f["regime_conviction"], 2.0)
        self.assertEqual(f["tf_ordinal"], 4.0)
        self.assertEqual(f["direction_long"], 0.0)
        self.assertEqual(f["strategy_pullback"], 1.0)
        self.assertEqual(f["why_sweep"], 1.0)
        self.assertEqual(f["why_volume"], 0.0)

    def test_absent_fields_are_omitted_not_zeroed(self):
        f = factorstats.default_factors({"why": ""})
        for key in ("rr", "rank", "zone_strength", "regime_ordinal", "tf_ordinal",
                    "direction_long"):
            self.assertNotIn(key, f)

    def test_a_future_confluence_block_needs_no_change_here(self):
        """The interface contract: `factors(payload) -> dict[str, float]`. A setup
        version that ships a `confluence` block plugs straight in."""
        def confluence_factors(p):
            return {k: float(v) for k, v in (p.get("confluence") or {}).items()}

        rows = [({"confluence": {"htf": i % 5, "vol": (i * 3) % 7}}, None)
                for i in range(60)]
        res = factorstats.analyze(candidates(rows), factors=confluence_factors,
                                  composite=lambda p: None)
        self.assertEqual(res["factors"], ["htf", "vol"])


if __name__ == "__main__":
    unittest.main()
