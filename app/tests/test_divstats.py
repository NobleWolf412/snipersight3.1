"""The divergence audition — read-only, point-in-time, and honest about MISSING.

`momentum.py` predicted this factor's fate in its own docstring: "Divergence in
particular is the sort of factor that reads as obviously true and grades badly,
which is exactly why it is emitted as evidence and left there." Drawing it on
the chart (4 Aug 2026) raised the stakes — an operator looking at a purple DIV
arrow beside a setup is one step from believing it means something — so it was
graded. Result on the 477-trade book: every cohort's interval crosses zero at
every window. Nothing to gate on.

These tests pin the MEASUREMENT, not the verdict. The verdict will move as the
book grows; what must not move is the causality, the direction mapping, and the
refusal to let "there wasn't one" read as "there was one pointing the other
way".
"""
import json
import tempfile
import unittest
from pathlib import Path

from engine import divstats, store
from engine.momentum import MOMENTUM_VERSION


class DirectionMappingCase(unittest.TestCase):
    """BULL divergence supports a LONG; BEAR supports a SHORT.

    Straight from momentum.py: bullish is a LOWER low in price against a
    HIGHER low in RSI — the sellers are exhausting, which argues for upside.
    Inverting this would flip the entire grade and still look plausible.
    """

    def test_bull_supports_long(self):
        self.assertEqual(divstats.stance("LONG", "BULL"), "AGREES")
        self.assertEqual(divstats.stance("SHORT", "BULL"), "OPPOSES")

    def test_bear_supports_short(self):
        self.assertEqual(divstats.stance("SHORT", "BEAR"), "AGREES")
        self.assertEqual(divstats.stance("LONG", "BEAR"), "OPPOSES")

    def test_nothing_to_compare_is_none_not_a_side(self):
        self.assertIsNone(divstats.stance("LONG", None))
        self.assertIsNone(divstats.stance(None, "BULL"))

    def test_the_mapping_matches_the_engine_that_writes_it(self):
        self.assertEqual(divstats.SUPPORTS, {"BULL": "LONG", "BEAR": "SHORT"})


class RecencyCase(unittest.TestCase):
    """`latest_before` is where lookahead would enter, so it is pinned hard."""

    SERIES = [(1000, "BULL"), (2000, "BEAR"), (3000, "BULL")]

    def test_a_divergence_confirmed_after_the_setup_is_invisible(self):
        """§5: nothing may read a fact the system could not have known."""
        self.assertIsNone(
            divstats.latest_before(self.SERIES, 999, max_age_s=10_000),
            "a divergence confirmed after the entry informed that entry — "
            "that is lookahead, and it would make any grade meaningless")

    def test_the_boundary_is_inclusive(self):
        self.assertEqual(
            divstats.latest_before(self.SERIES, 1000, max_age_s=10_000), "BULL")

    def test_the_most_recent_one_wins(self):
        self.assertEqual(
            divstats.latest_before(self.SERIES, 3500, max_age_s=10_000), "BULL")
        self.assertEqual(
            divstats.latest_before(self.SERIES, 2500, max_age_s=10_000), "BEAR")

    def test_a_stale_divergence_is_not_reported(self):
        """Forty bars on, it has had ample time to play out or fail."""
        self.assertIsNone(
            divstats.latest_before(self.SERIES, 5000, max_age_s=500))
        self.assertEqual(
            divstats.latest_before(self.SERIES, 3200, max_age_s=500), "BULL")

    def test_an_empty_series_is_none(self):
        self.assertIsNone(divstats.latest_before([], 1000, max_age_s=10_000))


class ExtractorCase(unittest.TestCase):
    def test_unannotated_yields_no_keys_so_missing_stays_missing(self):
        """Folding MISSING into "below" is how "we didn't look" launders itself
        into "we looked and it wasn't there" (factorstats.outcome_split)."""
        self.assertEqual(divstats.factor_extractors({}), {})

    def test_both_flags_are_emitted_and_are_exclusive(self):
        a = divstats.factor_extractors({"div_stance": "AGREES"})
        o = divstats.factor_extractors({"div_stance": "OPPOSES"})
        self.assertEqual(a, {"div_agrees": 1.0, "div_opposes": 0.0})
        self.assertEqual(o, {"div_agrees": 0.0, "div_opposes": 1.0})


class AnnotationCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _div(self, symbol, tf, confirmed_at, direction):
        store.insert_fact(
            self.con, symbol=symbol, tf=tf, kind="momentum",
            algo_version=MOMENTUM_VERSION, market_time=confirmed_at,
            confirmed_at=confirmed_at,
            payload={"event": "DIVERGENCE", "direction": direction})

    def _cand(self, symbol, tf, confirmed_at, direction):
        return {"confirmed_at": confirmed_at, "r": 1.0,
                "payload": {"symbol": symbol, "tf": tf, "direction": direction}}

    def test_only_divergence_events_are_read(self):
        """momentum writes MACD_SIGNAL, MACD_ZERO and RSI_BAND on the same
        kind and version; reading those as divergences would quietly grade a
        different factor."""
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind="momentum",
            algo_version=MOMENTUM_VERSION, market_time=1000, confirmed_at=1000,
            payload={"event": "MACD_SIGNAL", "direction": "BULL"})
        cands = [self._cand("BTCUSDT", "1H", 1500, "LONG")]
        self.assertEqual(
            divstats.annotate(self.con, cands, window_bars=10), 0)
        self.assertNotIn("div_stance", cands[0]["payload"])

    def test_a_candidate_in_range_is_annotated(self):
        self._div("BTCUSDT", "1H", 1_000_000, "BULL")
        cands = [self._cand("BTCUSDT", "1H", 1_003_600, "LONG")]  # 1 bar later
        self.assertEqual(
            divstats.annotate(self.con, cands, window_bars=10), 1)
        self.assertEqual(cands[0]["payload"]["div_stance"], "AGREES")

    def test_out_of_range_is_left_unannotated(self):
        self._div("BTCUSDT", "1H", 1_000_000, "BULL")
        cands = [self._cand("BTCUSDT", "1H", 1_000_000 + 40 * 3600, "LONG")]
        self.assertEqual(
            divstats.annotate(self.con, cands, window_bars=10), 0)
        self.assertNotIn("div_stance", cands[0]["payload"])

    def test_the_window_is_measured_on_the_candidates_own_timeframe(self):
        """10 bars means 10 hours on 1H and 150 minutes on 15m. A window in
        seconds would silently be ten times stricter on the fast charts."""
        self._div("SOLUSDT", "15m", 1_000_000, "BEAR")
        near = [self._cand("SOLUSDT", "15m", 1_000_000 + 5 * 900, "SHORT")]
        far = [self._cand("SOLUSDT", "15m", 1_000_000 + 5 * 3600, "SHORT")]
        self.assertEqual(divstats.annotate(self.con, near, window_bars=10), 1)
        self.assertEqual(divstats.annotate(self.con, far, window_bars=10), 0)

    def test_symbols_do_not_bleed_into_each_other(self):
        self._div("BTCUSDT", "1H", 1_000_000, "BULL")
        cands = [self._cand("ETHUSDT", "1H", 1_000_100, "LONG")]
        self.assertEqual(
            divstats.annotate(self.con, cands, window_bars=10), 0)

    def test_clear_removes_the_previous_windows_verdict(self):
        """The report grades four windows over ONE candidate list. A stale
        stance would silently grade the previous window's answer."""
        self._div("BTCUSDT", "1H", 1_000_000, "BULL")
        cands = [self._cand("BTCUSDT", "1H", 1_003_600, "LONG")]
        divstats.annotate(self.con, cands, window_bars=10)
        self.assertIn("div_stance", cands[0]["payload"])
        divstats._clear(cands)
        self.assertNotIn("div_stance", cands[0]["payload"])
        self.assertNotIn("div_direction", cands[0]["payload"])

    def test_grading_writes_nothing(self):
        """READ-ONLY: a factor that recorded facts would grade its own
        evidence, and this one has not earned the right to gate anything."""
        self._div("BTCUSDT", "1H", 1_000_000, "BULL")
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        divstats.grade(self.con)
        self.assertEqual(
            before, self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0])

    def test_the_report_grades_every_window(self):
        rep = divstats.grade(self.con)
        self.assertEqual(sorted(rep["windows"]), sorted(divstats.WINDOWS))
        self.assertTrue(rep["derived_at_analysis_time"])
        self.assertIn(divstats.DEFAULT_WINDOW, divstats.WINDOWS)


if __name__ == "__main__":
    unittest.main()
