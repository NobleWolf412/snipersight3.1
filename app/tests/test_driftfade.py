"""Drift fade is an AUDITION, and these are the properties that keep it one.

The module answers "what did fading an already-moving market earn" without
creating a filter. Everything here defends the honesty of that answer: the
drift may only read bars closed at the as-of moment, a gapped series lands in
MISSING rather than measuring multi-day drift under a 24h name, and no trading
module may consume any of it until the operator promotes a gate under a new
setups version.
"""
import inspect
import unittest

from engine import driftfade, execsim, risk, scalein, setups


def _closes(tf, n, price=lambda i: 100.0 + i):
    return [(i * tf, price(i)) for i in range(n)]


class DriftCase(unittest.TestCase):
    TF = 3600
    DAY = 86400

    def test_measures_the_trailing_window_exactly(self):
        closes = _closes(self.TF, 60)
        as_of = 48 * self.TF
        # newest closed bar opens at 47h, reference one window earlier at 23h
        want = (closes[47][1] / closes[23][1] - 1) * 100
        pct, span = driftfade.drift_pct(closes, as_of, self.TF)
        self.assertAlmostEqual(pct, want)
        self.assertEqual(span, (47 - 23) * self.TF,
                         "the span must be the real distance, not the name")

    def test_a_developing_bar_is_never_read(self):
        """Convention 4 for measurements: as-of mid-bar, the newest close the
        factor may see is the bar BEFORE the one still printing."""
        closes = _closes(self.TF, 60)
        mid_bar = 48 * self.TF + 1800
        want = (closes[47][1] / closes[23][1] - 1) * 100
        pct, _ = driftfade.drift_pct(closes, mid_bar, self.TF)
        self.assertAlmostEqual(pct, want)

    def test_a_stale_newest_close_is_missing_not_drift_now(self):
        """The audit's counterexample: hourly closes ending 10 bars before
        as_of produced a 15h drift stamped as the drift at as_of. Both ends
        need the freshness guard, not just the reference."""
        closes = _closes(self.TF, 31)          # newest bar opens at 30h
        self.assertIsNone(driftfade.drift_pct(closes, 40 * self.TF, self.TF))
        # ...while one venue-acknowledged empty bucket is tolerated
        self.assertIsNotNone(
            driftfade.drift_pct(closes, 32 * self.TF, self.TF))

    def test_missing_window_is_none_not_zero(self):
        closes = _closes(self.TF, 10)          # 10h of bars, 24h window
        self.assertIsNone(driftfade.drift_pct(closes, 10 * self.TF, self.TF))
        self.assertIsNone(driftfade.drift_pct([], 10 * self.TF, self.TF))

    def test_an_overaged_reference_is_missing_not_multiday_drift(self):
        """A venue-acknowledged gap can push the nearest reference close days
        back. That measurement is real but it is not 24h drift, and renaming
        it would be the exact laundering MISSING exists to stop."""
        tf, day = self.TF, self.DAY
        closes = [(0, 100.0)] + [(3 * day + i * tf, 100.0 + i)
                                 for i in range(30)]
        # 10h into the dense run the 24h reference falls inside the gap; the
        # nearest close at-or-before is the 3-day-old orphan, past MAX age.
        self.assertIsNone(driftfade.drift_pct(closes, 3 * day + 10 * tf, tf))
        # 25h in, the window is covered by the dense run itself and measures —
        # and the tolerated stretch is written on the result, not hidden in it.
        pct, span = driftfade.drift_pct(closes, 3 * day + 25 * tf, tf)
        self.assertEqual(span, 24 * tf)

    def test_counter_is_three_states(self):
        thr = driftfade.COUNTER_DRIFT_PCT
        self.assertTrue(driftfade.counter("SHORT", thr))
        self.assertTrue(driftfade.counter("LONG", -thr))
        self.assertFalse(driftfade.counter("SHORT", thr - 0.01))
        self.assertFalse(driftfade.counter("LONG", thr))   # with, not counter
        self.assertIsNone(driftfade.counter("SHORT", None))
        self.assertIsNone(driftfade.counter("SIDEWAYS", 5.0))


class DeltaCase(unittest.TestCase):
    @staticmethod
    def _rows(n_clusters=10, per=6, counter_clusters=None):
        rows = []
        for ci in range(n_clusters):
            for k in range(per):
                is_counter = ((ci in counter_clusters)
                              if counter_clusters is not None
                              else (k % 2 == 0))
                rows.append({"r": -1.0 if is_counter else 1.0,
                             "t": 1786000000 + ci * 604800 + k * 3600,
                             "symbol": f"S{ci}", "counter": is_counter})
        return rows

    def test_delta_reads_the_real_difference(self):
        d = driftfade.cluster_delta_ci(self._rows())
        self.assertAlmostEqual(d["point"], -2.0)
        self.assertTrue(d["clears_zero"])
        self.assertIn("resamples_dropped", d,
                      "drops must be visible in the result")

    def test_a_conditioned_interval_is_refused_not_narrowed(self):
        """When counter trades live in 2 of 10 clusters, many resamples draw
        none and have no delta. Percentiles over the survivors would be an
        interval conditioned on the split existing — the audit's finding.
        Past the drop budget the honest answer is no interval."""
        d = driftfade.cluster_delta_ci(
            self._rows(counter_clusters={0, 1}), iters=400)
        self.assertIsNone(d)

    def test_below_the_cluster_floor_is_none(self):
        self.assertIsNone(driftfade.cluster_delta_ci(self._rows(n_clusters=4)))


class ExtractorCase(unittest.TestCase):
    def test_unannotated_payload_yields_no_keys(self):
        """{} not {0}: outcome_split's MISSING bucket only stays honest if
        'we didn't look' is the absence of the key, never a zero."""
        self.assertEqual(driftfade.factor_extractors({}), {})

    def test_flags_are_exclusive_binaries(self):
        p = {"counter_drift": True, "with_drift": False}
        self.assertEqual(driftfade.factor_extractors(p),
                         {"counter_drift": 1.0, "with_drift": 0.0})
        p = {"counter_drift": False, "with_drift": True}
        self.assertEqual(driftfade.factor_extractors(p),
                         {"counter_drift": 0.0, "with_drift": 1.0})


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """Evidence is recorded, not filtered on. A passing grade here is a
        versioned setups PROPOSAL for the operator, never an import."""
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("driftfade", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")

    def test_the_module_writes_nothing(self):
        src = inspect.getsource(driftfade)
        self.assertNotIn("insert_fact", src,
                         "the audition wrote a fact — it is no longer "
                         "derived at analysis time")
        self.assertIn("mode=ro", src,
                      "main() must open the store read-only")

    def test_the_in_sample_confession_is_in_the_output(self):
        """The threshold was chosen from the outcomes it now grades. The
        report must say so on every run — a number whose provenance lives
        only in a docstring gets quoted without it."""
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, symbol TEXT,"
                    " tf TEXT, kind TEXT, market_time INT, confirmed_at INT,"
                    " invalidated_at INT, algo_version TEXT, payload TEXT,"
                    " content_hash TEXT, producer_run_id TEXT)")
        con.execute("CREATE TABLE candles (symbol TEXT, tf TEXT, open_ts INT,"
                    " open TEXT, high TEXT, low TEXT, close TEXT,"
                    " volume TEXT, source TEXT, imported_at INT)")
        con.execute("INSERT INTO facts (symbol, tf, kind, market_time,"
                    " confirmed_at, algo_version, payload, content_hash)"
                    " VALUES ('X','1H','setup',1,1,'v','{}','h')")
        before = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        res = driftfade.grade(con)
        after = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertEqual(before, after,
                         "grade() changed the fact count — the audition wrote")
        self.assertIn("in_sample_note", res)
        self.assertIn("2026-08-23", res["in_sample_note"])
        self.assertTrue(res["derived_at_analysis_time"])


if __name__ == "__main__":
    unittest.main()
