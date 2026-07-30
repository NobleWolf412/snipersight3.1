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


def v07_payload(**over):
    """A `setup-v0.7-draft` VALIDATED payload, in the shape `setups.py` writes it:
    confluence fields nested, numerics stringified where the emitter stringifies
    them (`rr`, `volume_expansion`, `target_distance_r` are all Decimal->str)."""
    conf = {"htf_timeframe": "4H", "htf_regime": "BEAR_TREND",
            "htf_regime_aligned": True, "zone_strength": 77, "zone_quality": 55,
            "zone_cluster": 0, "volume_expansion": "0.86", "sweep_nearby": False,
            "bars_since_break": 88, "target_distance_r": "5.74", "score": 0}
    conf.update(over.pop("confluence", {}))
    payload = {"rr": "3.00", "rank": 75, "strategy": "PULLBACK",
               "direction": "SHORT", "tf": "1H", "confirm_bars_waited": 0,
               "state": "VALIDATED", "confluence": conf}
    payload.update(over)
    return payload


class TestConfluenceV07Extractor(unittest.TestCase):
    """The v0.7 extractor is the first thing in this project to read a `confluence`
    block. What matters is not that it reads the fields — it is that an UNRECORDED
    field stays unrecorded instead of becoming a zero, because on this book a third
    of `htf_regime` is missing and zeroing it would invent 74 disagreeing setups."""

    def test_reads_every_field_the_v07_confluence_block_emits(self):
        f = factorstats.confluence_v07_factors(v07_payload())
        self.assertEqual(f["rr"], 3.0)
        self.assertEqual(f["rr_good"], 1.0)
        self.assertEqual(f["rank"], 75.0)
        self.assertEqual(f["confirm_bars_waited"], 0.0)
        self.assertEqual(f["tf_ordinal"], 2.0)
        self.assertEqual(f["direction_long"], 0.0)
        self.assertEqual(f["strategy_pullback"], 1.0)
        self.assertEqual(f["htf_regime_ordinal"], -2.0)
        self.assertEqual(f["htf_regime_conviction"], 2.0)
        self.assertEqual(f["htf_regime_aligned"], 1.0)
        self.assertEqual(f["zone_strength"], 77.0)
        self.assertEqual(f["zone_quality"], 55.0)
        self.assertEqual(f["zone_cluster"], 0.0)
        self.assertEqual(f["volume_expansion"], 0.86)
        self.assertEqual(f["volume_hot"], 0.0)
        self.assertEqual(f["sweep_nearby"], 0.0)
        self.assertEqual(f["bars_since_break"], 88.0)
        self.assertEqual(f["target_distance_r"], 5.74)

    def test_unknown_htf_regime_is_omitted_not_scored_as_disagreeing(self):
        """`rank` treats a missing HTF regime exactly like a disagreeing one. The
        extractor must NOT: 'we never looked' and 'we looked and it disagreed' are
        different observations, and on this book they have different outcomes."""
        f = factorstats.confluence_v07_factors(
            v07_payload(confluence={"htf_regime": None, "htf_regime_aligned": None}))
        for key in ("htf_regime_ordinal", "htf_regime_conviction",
                    "htf_align_strength", "htf_regime_aligned"):
            self.assertNotIn(key, f)
        self.assertEqual(f["zone_strength"], 77.0)   # the rest still extracted

    def test_range_regime_is_read_as_zero_conviction_not_dropped(self):
        """`RANGE` never appears in a setup's OWN regime (no playbook trades it) but
        does appear on the higher timeframe, and dropping it would silently discard
        28 candidates from the axis."""
        f = factorstats.confluence_v07_factors(
            v07_payload(confluence={"htf_regime": "RANGE",
                                    "htf_regime_aligned": False}))
        self.assertEqual(f["htf_regime_conviction"], 0.0)
        self.assertEqual(f["htf_regime_ordinal"], 0.0)
        self.assertEqual(f["htf_regime_aligned"], 0.0)

    def test_align_strength_is_signed_toward_the_trade(self):
        """The graded version of the +10 flag: a hard bear HTF is +2 for a SHORT and
        -2 for a LONG, which the flag cannot express."""
        short = factorstats.confluence_v07_factors(v07_payload(direction="SHORT"))
        long_ = factorstats.confluence_v07_factors(v07_payload(direction="LONG"))
        self.assertEqual(short["htf_align_strength"], +2.0)
        self.assertEqual(long_["htf_align_strength"], -2.0)

    def test_binary_rank_inputs_are_extracted_beside_their_raw_values(self):
        hot = factorstats.confluence_v07_factors(
            v07_payload(rr="2.00", confluence={"volume_expansion": "2.39"}))
        self.assertEqual(hot["volume_expansion"], 2.39)
        self.assertEqual(hot["volume_hot"], 1.0)
        self.assertEqual(hot["rr"], 2.0)
        self.assertEqual(hot["rr_good"], 0.0)

    def test_placeholder_score_field_is_not_extracted(self):
        """`setups.py` emits `score: 0` as a reserved slot consumed by nothing. It is
        constant by construction and would only add a ZERO_DISPERSION row about a
        field that holds no data."""
        self.assertNotIn("score", factorstats.confluence_v07_factors(v07_payload()))

    def test_a_payload_without_a_confluence_block_yields_only_top_level_factors(self):
        f = factorstats.confluence_v07_factors({"rr": "3.00", "tf": "1D"})
        self.assertEqual(f["rr"], 3.0)
        self.assertNotIn("zone_strength", f)
        self.assertNotIn("sweep_nearby", f)

    def test_registered_under_a_name_for_the_cli(self):
        self.assertIs(factorstats.EXTRACTORS["confluence-v07"],
                      factorstats.confluence_v07_factors)
        self.assertIs(factorstats.EXTRACTORS["rank-components"],
                      factorstats.rank_components)


class TestRankComponents(unittest.TestCase):
    """The rank decomposition has one job: attribute var(rank) across the terms of
    the formula that produced it. If it does not reproduce `rank` exactly, every
    share it reports is fiction."""

    def test_terms_reproduce_the_shipped_rank_exactly(self):
        f = factorstats.rank_components(v07_payload())
        self.assertEqual(f["pts_base"], 50.0)
        self.assertEqual(f["pts_sweep"], 0.0)
        self.assertEqual(f["pts_volume"], 0.0)      # 0.86x volume
        self.assertEqual(f["pts_rr_good"], 15.0)    # 3.00 R:R
        self.assertEqual(f["pts_htf_aligned"], 10.0)
        self.assertEqual(f["rank_reproduction_error"], 0.0)

    def test_reproduction_error_is_non_zero_when_the_formula_stops_matching(self):
        """The self-check is a factor ROW, not an assert, so a formula drift shows up
        as a visible line in the table rather than an exception nobody ran."""
        f = factorstats.rank_components(v07_payload(rank=65))
        self.assertEqual(f["rank_reproduction_error"], 10.0)

    def test_terms_are_points_not_flags(self):
        """cov(20*sweep, rank) is 20x cov(sweep, rank). Emitting bare flags would give
        every term a share blind to its weight, and the weights are the question."""
        f = factorstats.rank_components(
            v07_payload(confluence={"sweep_nearby": True}))
        self.assertEqual(f["pts_sweep"], 20.0)

    def test_unknown_htf_scores_zero_points_because_the_formula_does(self):
        """Deliberately UNLIKE the confluence extractor: `setups.py` writes
        `if conf.get("htf_regime_aligned")`, so None and False both pay nothing. A
        decomposition has to model the formula as written, not as intended."""
        f = factorstats.rank_components(
            v07_payload(confluence={"htf_regime": None, "htf_regime_aligned": None}))
        self.assertEqual(f["pts_htf_aligned"], 0.0)

    def test_shares_sum_to_one_over_a_synthetic_book(self):
        """The sum IS the self-check: rank is the unweighted sum of these terms, so
        anything other than 1.00 means the decomposition has stopped describing the
        formula. (The other three bonuses all co-fire when i % 12 == 0, so sweep is
        put on `i % 12 == 5` to keep all four apart: 50+20+15+15+10 = 110 would hit
        the min(100, ...) clamp, and the clamp is not linear — a book where it binds
        genuinely cannot decompose to 1.00. On the real v0.7 book the highest rank
        observed is 90, so it never binds there.)"""
        rows = []
        for i in range(80):
            conf = {"sweep_nearby": bool(i % 12 == 5),
                    "volume_expansion": "2.39" if i % 3 == 0 else "0.86",
                    "htf_regime_aligned": bool(i % 4 == 0)}
            rr = "3.00" if i % 2 == 0 else "2.00"
            rank = min(100, 50 + (20 if conf["sweep_nearby"] else 0)
                       + (15 if i % 3 == 0 else 0) + (15 if i % 2 == 0 else 0)
                       + (10 if conf["htf_regime_aligned"] else 0))
            rows.append((v07_payload(rr=rr, rank=rank, confluence=conf), None))
        res = factorstats.analyze(candidates(rows), factors=factorstats.rank_components)
        self.assertAlmostEqual(res["contribution_share_sum"], 1.0, places=4)
        self.assertEqual(res["stats"]["rank_reproduction_error"]["std_all"], 0.0)

    def test_a_non_v07_payload_decomposes_into_nothing(self):
        self.assertEqual(factorstats.rank_components({"rank": 65}), {})


class TestPerFactorNoiseFloor(unittest.TestCase):
    """A factor the store only recorded on part of the book is measured on part of
    the book. Judging it against the FULL book's floor credits it with a confidence
    its own coverage never earned."""

    def _partial_book(self, n, n_covered):
        """`partial` is recorded on the first `n_covered` candidates and omitted on
        the rest. Its values are 1.0/2.0 rather than 0.0/1.0 so the factor is PRESENT
        wherever it is observed — this isolates the coverage question from the fire
        -rate axis, which would otherwise call it RARE first and never reach the
        outcome verdict under test."""
        rows = []
        for i in range(n):
            extra = {"i": i}
            if i < n_covered:
                extra["partial"] = 2.0 if i % 2 else 1.0
            rows.append((extra, 1.5 if i % 2 else -2.0))
        return candidates(rows)

    def test_partial_coverage_gets_its_own_wider_floor(self):
        res = factorstats.analyze(
            self._partial_book(200, 40),
            factors=lambda p: ({"partial": p["partial"]} if "partial" in p else {}),
            composite=lambda p: None)
        s = res["stats"]["partial"]
        self.assertEqual(s["n_outcome"], 40)
        self.assertAlmostEqual(s["noise_floor"], factorstats.noise_floor(40), places=6)
        self.assertGreater(s["noise_floor"], res["noise_floor"])   # wider than n=200

    def test_a_factor_under_the_trade_floor_is_withheld_even_on_a_big_book(self):
        res = factorstats.analyze(
            self._partial_book(200, 20),
            factors=lambda p: ({"partial": p["partial"]} if "partial" in p else {}),
            composite=lambda p: None)
        s = res["stats"]["partial"]
        self.assertTrue(res["outcome_sample_ok"])       # the BOOK is big enough
        self.assertIsNone(s["r_outcome"])               # this FACTOR is not
        self.assertFalse(s["clears_noise_floor"])
        self.assertTrue(s["verdict"].startswith("UNPROVEN"))
        self.assertTrue(any("recorded on only 20 of 200" in w
                            for w in res["warnings"]))


class TestOutcomeSplit(unittest.TestCase):
    """The readable form of a 0/1 factor's outcome edge. A rank term paying points to
    the losing side is the finding this exists to make unmissable."""

    def _book(self, flag_wins: bool):
        rows = []
        for i in range(120):
            flag = 1.0 if i % 2 else 0.0
            good = (flag == 1.0) if flag_wins else (flag == 0.0)
            rows.append(({"flag": flag}, 2.0 if good else -1.0))
        return candidates(rows)

    def test_reports_win_rate_and_mean_r_on_each_side(self):
        s = factorstats.outcome_split(self._book(True), "flag",
                                      factors=lambda p: {"flag": p["flag"]})
        self.assertEqual(s["groups"]["at_or_above"]["n"], 60)
        self.assertEqual(s["groups"]["at_or_above"]["win_rate"], 1.0)
        self.assertEqual(s["groups"]["below"]["win_rate"], 0.0)
        self.assertEqual(s["delta_mean_r"], 3.0)

    def test_a_backwards_factor_reports_a_negative_delta(self):
        s = factorstats.outcome_split(self._book(False), "flag",
                                      factors=lambda p: {"flag": p["flag"]})
        self.assertLess(s["delta_mean_r"], 0)

    def test_missing_is_its_own_group_never_folded_into_below(self):
        """Folding 'the store never recorded it' into 'it was absent' is how a
        coverage gap gets laundered into a measurement."""
        rows = [(({"flag": 1.0} if i % 2 else {}), 1.0) for i in range(80)]
        s = factorstats.outcome_split(
            candidates(rows), "flag",
            factors=lambda p: ({"flag": p["flag"]} if "flag" in p else {}))
        self.assertEqual(s["groups"]["at_or_above"]["n"], 40)
        self.assertEqual(s["groups"]["below"]["n"], 0)
        self.assertEqual(s["groups"]["missing"]["n"], 40)

    def test_a_group_under_the_floor_keeps_its_counts_but_withholds_rates(self):
        rows = [({"flag": 1.0 if i < 5 else 0.0}, 2.0 if i < 5 else -1.0)
                for i in range(120)]
        s = factorstats.outcome_split(candidates(rows), "flag",
                                      factors=lambda p: {"flag": p["flag"]})
        hi = s["groups"]["at_or_above"]
        self.assertEqual(hi["n"], 5)
        self.assertEqual(hi["n_wins"], 5)          # counts are facts
        self.assertIsNone(hi["win_rate"])          # rates are not, at n=5
        self.assertIsNone(hi["mean_r"])
        self.assertIsNone(s["delta_mean_r"])
        self.assertTrue(any("below the 30-trade floor" in w for w in s["warnings"]))

    def test_open_and_missed_candidates_are_excluded(self):
        rows = [({"flag": 1.0}, None) for _ in range(40)]
        s = factorstats.outcome_split(candidates(rows), "flag",
                                      factors=lambda p: {"flag": p["flag"]})
        self.assertEqual(s["n_trades"], 0)


if __name__ == "__main__":
    unittest.main()
