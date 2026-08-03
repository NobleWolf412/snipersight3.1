"""The engine loop is one function, and absence has a name.

Two defects this file exists to make unrepeatable, both already paid for:

  · The LOOP drifted even after the roster was unified. `live.cycle` had a
    per-engine guard and a per-symbol quality gate; `ingest.run_engines` had
    neither. Whichever loop grew a check, the other silently lacked it — the
    same disease as the roster drift that let `cooldowns` sit outside every
    runner and never fire.

  · Absence was invisible. PF_XLMUSD ran 24 cycles with both intraday
    timeframes at zero candles, and nothing anywhere said so — the funnel
    starts at "candidates", and a symbol whose data never arrived produces no
    candidates to count. The staged-gate shape is ported from the prior
    project's orchestrator, where `no_data` / `missing_critical_tf` are named
    buckets checked before any compute.

The asymmetry between the gates is deliberate and tested as such: NO_DATA
skips engines (zero candles in, zero facts out — the skip changes no record),
while SHORT_HISTORY is observed and NOT enforced, because engines running on
short history have already written facts into the recorded book, and blocking
them now would change what the book contains under the same algo versions.
"""
import inspect
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine import ingest, pipeline, quality, setups, store
import live

TF = 900
SYM = "BTCUSDT"


def fake_engine(name, calls):
    def run(con, symbol, tf, tf_seconds):
        calls.append((name, tf))
    return SimpleNamespace(run=run, __name__=name)


class GateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        self.calls = []
        self._patches = [
            patch.object(pipeline, "PER_SYMBOL",
                         (fake_engine("alpha", self.calls),
                          fake_engine("beta", self.calls))),
            patch.object(quality, "assert_market_ready", lambda *a, **k: None),
            patch.object(ingest, "missing_history", lambda *a, **k: []),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.con.close()
        self.tmp.cleanup()

    def candles(self, tf, n):
        for i in range(n):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (SYM, tf, i * TF, "1", "2", "0.5", "1", "1", "test", i * TF))
        self.con.commit()

    def gates(self):
        return {(tf, g): d for tf, g, d in self.con.execute(
            "SELECT tf, gate, detail FROM pipeline_gates WHERE symbol=?", (SYM,))}

    # ---------- NO_DATA: skipped, named, and cleared ----------

    def test_a_timeframe_with_no_candles_is_skipped_and_named(self):
        self.candles("15m", 5)
        r = pipeline.run_symbol(self.con, SYM)
        self.assertIsNone(r["blocked"])
        ran_tfs = {tf for _, tf in self.calls}
        self.assertEqual(ran_tfs, {"15m"},
                         "engines must run ONLY where candles exist")
        g = self.gates()
        for tf in ("1H", "4H", "1D", "1W"):
            self.assertIn((tf, "NO_DATA"), g, f"{tf}'s absence must be named")
        self.assertNotIn(("15m", "NO_DATA"), g)

    def test_the_gate_clears_the_cycle_the_data_arrives(self):
        """Current state, not history: a stale row would keep reporting a hole
        the last cycle already closed."""
        self.candles("15m", 5)
        pipeline.run_symbol(self.con, SYM)
        self.assertIn(("1H", "NO_DATA"), self.gates())
        self.candles("1H", 5)
        pipeline.run_symbol(self.con, SYM)
        self.assertNotIn(("1H", "NO_DATA"), self.gates())

    def test_first_seen_survives_a_retrip(self):
        """'NO_DATA since 26 Jul' is the useful sentence; a timestamp that
        resets every cycle can never say it."""
        self.candles("15m", 5)
        pipeline.run_symbol(self.con, SYM, now=1000)
        pipeline.run_symbol(self.con, SYM, now=2000)
        (since,) = self.con.execute(
            "SELECT measured_at FROM pipeline_gates WHERE symbol=? AND tf=? "
            "AND gate='NO_DATA'", (SYM, "1H")).fetchone()
        self.assertEqual(since, 1000)

    def test_engine_order_is_module_outer(self):
        """Load-bearing: scalein's 1H pass reads the HTF facts execsim writes
        on 4H/1D, so every module must finish a full timeframe sweep before the
        next module starts — exactly as both runners always ran."""
        self.candles("15m", 3)
        self.candles("1H", 3)
        pipeline.run_symbol(self.con, SYM)
        names = [n for n, _ in self.calls]
        self.assertEqual(names, sorted(names, key=names.index))
        self.assertEqual(names, ["alpha", "alpha", "beta", "beta"],
                         "alpha must sweep every timeframe before beta starts")

    # ---------- QUALITY_BLOCKED: skipped, loud, caller keeps policy ----------

    def test_a_blocked_symbol_runs_nothing_and_says_why(self):
        self.candles("15m", 5)
        with patch.object(quality, "assert_market_ready",
                          side_effect=RuntimeError("SEQUENCE_GAPS")):
            r = pipeline.run_symbol(self.con, SYM)
        self.assertIn("SEQUENCE_GAPS", r["blocked"])
        self.assertEqual(self.calls, [], "a blocked symbol must not run engines")
        self.assertIn(("*", "QUALITY_BLOCKED"), self.gates())

    def test_onboarding_still_raises_on_a_blocked_symbol(self):
        """The loop is shared; the POLICY is not. Onboarding a symbol whose
        market data fails audit should fail the onboard, exactly as before."""
        with patch.object(quality, "assert_market_ready",
                          side_effect=RuntimeError("SEQUENCE_GAPS")):
            with self.assertRaises(RuntimeError):
                ingest.run_engines(self.con, SYM)

    # ---------- SHORT_HISTORY: observed, never enforced ----------

    def test_short_history_is_named_but_engines_still_run(self):
        """Blocking on short history would change what the recorded book
        contains under the same algo versions — the rewrite the versioning
        rule forbids. The gate makes the condition visible; whether it should
        ever gate is a question for measurement, not a default."""
        self.candles("15m", 5)
        with patch.object(ingest, "missing_history", lambda *a, **k: ["15m"]):
            pipeline.run_symbol(self.con, SYM)
        self.assertIn(("15m", "SHORT_HISTORY"), self.gates())
        self.assertIn(("alpha", "15m"), self.calls,
                      "SHORT_HISTORY must not stop the engines")

    def test_a_broken_detector_cannot_block_the_loop(self):
        self.candles("15m", 5)
        with patch.object(ingest, "missing_history",
                          side_effect=RuntimeError("boom")):
            pipeline.run_symbol(self.con, SYM)
        self.assertIn(("alpha", "15m"), self.calls)

    # ---------- the vocabulary is closed ----------

    def test_an_unknown_gate_name_raises(self):
        """Gates are minted beside their declaration; drift here is a typo,
        not vocabulary growth, and a typo must not become a silent bucket."""
        with self.assertRaises(ValueError):
            pipeline._record_gate(self.con, SYM, "*", "NO_DATTA", "", 0)


class OneLoopCase(unittest.TestCase):
    """Both runners must call THE loop — asserted on source, the same way the
    roster test asserts identity, so a re-inlined copy fails a test instead of
    quietly starting a second lineage."""

    def test_live_cycle_uses_the_shared_loop(self):
        src = inspect.getsource(live.cycle)
        self.assertIn("pipeline.run_symbol", src)
        self.assertNotIn("for mod in ENGINES", src,
                         "live.cycle has re-grown its own engine loop")

    def test_ingest_uses_the_shared_loop(self):
        src = inspect.getsource(ingest.run_engines)
        self.assertIn("pipeline.run_symbol", src)
        self.assertNotIn("for mod in", src,
                         "ingest.run_engines has re-grown its own engine loop")


class VocabularyCase(unittest.TestCase):
    """The cross-boundary drift guard. Reasons are minted in Python and given
    sentences in JavaScript; nothing at runtime spans that boundary, so a test
    must — this is the roster test's job applied to words."""

    FUNNEL = (Path(__file__).resolve().parents[1] / "static" / "funnel.js") \
        .read_text(encoding="utf-8")

    def test_every_reason_setups_can_write_is_canonical(self):
        src = inspect.getsource(setups)
        minted = set(re.findall(
            r'reject\([^,]+,\s*[^,]+,\s*"([A-Z_]+)', src))
        self.assertTrue(minted, "the scan found no reject() call sites")
        self.assertLessEqual(minted, set(setups.REJECTION_REASONS),
                             "a reject() call site mints a reason missing from "
                             "REJECTION_REASONS — the guard cannot vouch for it")

    def test_every_canonical_reason_has_a_funnel_sentence(self):
        for reason in setups.REJECTION_REASONS:
            self.assertIn(f"{reason}:", self.FUNNEL,
                          f"{reason} has no entry in funnel.js REASONS — it "
                          f"reaches the operator as a raw enum")

    def test_every_gate_has_a_funnel_sentence(self):
        for gate in pipeline.GATES:
            self.assertIn(f"{gate}:", self.FUNNEL,
                          f"{gate} has no entry in funnel.js GATE_LABELS")

    def test_the_endpoint_marks_unlabelled_reasons(self):
        import server
        src = inspect.getsource(server.setup_telemetry)
        self.assertIn("unlabelled", src)
        self.assertIn("REJECTION_REASONS", src)


if __name__ == "__main__":
    unittest.main()
