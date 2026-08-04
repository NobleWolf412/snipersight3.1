"""BTC alignment — a factor auditioning, never a gate. The properties:

  · CAUSALITY — the regime joined to a setup is the one BTC's facts had
    CONFIRMED at that setup's confirmation, never a later one. This factor is
    derived at analysis time, which is precisely where lookahead sneaks in.
  · CONSERVATISM — OPPOSED means the full opposing trend only. WEAKENING_* is
    a trend losing force, and counting it would block exactly the turns the
    REVERSAL playbook hunts.
  · HONEST ABSENCE — BTC's own setups and pre-first-fact candidates stay
    unannotated and land in outcome_split's MISSING bucket. "We didn't look"
    must never be laundered into "we looked and it wasn't there".
  · NOT A GATE — no trading module may import this. The audition already
    returned its first verdict (the prior project's Gate 3, ported as-is,
    would have blocked the one cohort on this book that clears zero), which
    is the whole argument for measuring before gating.
"""
import inspect
import tempfile
import unittest
from pathlib import Path

from engine import btcalign, execsim, risk, scalein, setups, store
from engine.regime import REGIME_VERSION


def cand(symbol, tf, direction, confirmed_at, r=None):
    return {"confirmed_at": confirmed_at, "r": r,
            "payload": {"symbol": symbol, "tf": tf, "direction": direction,
                        "setup_id": f"{symbol}|{tf}|X|{confirmed_at}"}}


class MappingCase(unittest.TestCase):
    def test_opposed_is_the_full_trend_only(self):
        self.assertEqual(btcalign.alignment("LONG", "BEAR_TREND"), "OPPOSED")
        self.assertEqual(btcalign.alignment("SHORT", "BULL_TREND"), "OPPOSED")

    def test_aligned_is_the_full_trend_only(self):
        self.assertEqual(btcalign.alignment("LONG", "BULL_TREND"), "ALIGNED")
        self.assertEqual(btcalign.alignment("SHORT", "BEAR_TREND"), "ALIGNED")

    def test_weakening_and_sideways_states_are_neutral(self):
        """A weakening trend is a turn forming — the REVERSAL playbook's whole
        hunting ground. Blocking on it would gate the strategy's habitat."""
        for state in ("WEAKENING_BEAR", "WEAKENING_BULL", "TRANSITION", "RANGE"):
            for side in ("LONG", "SHORT"):
                self.assertEqual(btcalign.alignment(side, state), "NEUTRAL",
                                 f"{side} vs {state} must be NEUTRAL")

    def test_unknown_btc_state_is_none_not_neutral(self):
        """None means 'could not know'; NEUTRAL means 'knew, and it was
        neither'. Conflating them pads the neutral cohort with ignorance."""
        self.assertIsNone(btcalign.alignment("LONG", None))


class CausalityCase(unittest.TestCase):
    SERIES = [(100, "BULL_TREND"), (200, "TRANSITION"), (300, "BEAR_TREND")]

    def test_asof_reads_the_latest_confirmed_fact(self):
        self.assertEqual(btcalign.regime_asof(self.SERIES, 250), "TRANSITION")

    def test_asof_never_reads_the_future(self):
        """A setup confirmed at 299 must not see the regime confirmed at 300 —
        one second of lookahead is still lookahead."""
        self.assertEqual(btcalign.regime_asof(self.SERIES, 299), "TRANSITION")
        self.assertEqual(btcalign.regime_asof(self.SERIES, 300), "BEAR_TREND")

    def test_before_the_first_fact_is_unknowable(self):
        self.assertIsNone(btcalign.regime_asof(self.SERIES, 99))


class AnnotateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        for at, label in ((100, "BULL_TREND"), (300, "BEAR_TREND")):
            store.insert_fact(self.con, symbol=btcalign.BTC_SYMBOL, tf="1H",
                              kind="regime", market_time=at, confirmed_at=at,
                              algo_version=REGIME_VERSION,
                              payload={"regime": label})
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_alt_setups_are_stamped_with_the_asof_regime(self):
        c = cand("LINKUSDT", "1H", "LONG", 350)
        n = btcalign.annotate(self.con, [c])
        self.assertEqual(n, 1)
        self.assertEqual(c["payload"]["btc_regime_asof"], "BEAR_TREND")
        self.assertEqual(c["payload"]["btc_alignment"], "OPPOSED")

    def test_btc_itself_is_never_annotated(self):
        """The factor is about alts riding or fighting the tide. BTC is the
        tide; stamping it would let it agree with itself in every sample."""
        c = cand(btcalign.BTC_SYMBOL, "1H", "LONG", 350)
        self.assertEqual(btcalign.annotate(self.con, [c]), 0)
        self.assertNotIn("btc_alignment", c["payload"])

    def test_pre_first_fact_setups_stay_unannotated(self):
        c = cand("LINKUSDT", "1H", "LONG", 50)      # before BTC's first fact
        self.assertEqual(btcalign.annotate(self.con, [c]), 0)
        self.assertNotIn("btc_alignment", c["payload"])

    def test_unannotated_lands_in_the_missing_bucket(self):
        annotated = cand("LINKUSDT", "1H", "LONG", 350, r=1.0)
        unknowable = cand("LINKUSDT", "1H", "LONG", 50, r=-1.0)
        btcalign.annotate(self.con, [annotated, unknowable])
        from engine import factorstats
        split = factorstats.outcome_split(
            [annotated, unknowable], "btc_opposed",
            factors=btcalign.factor_extractors)
        self.assertEqual(split["groups"]["missing"]["n"], 1,
                         "an unknowable BTC state is MISSING, not 'not opposed'")


class NotAGateCase(unittest.TestCase):
    def test_no_trading_module_imports_the_audition(self):
        """House convention: evidence is recorded, not filtered on. The first
        grading run is itself the argument — the prior project's gate, ported
        untested, would have blocked the +37.5R cohort and kept the -24.4R one.
        Wiring this into a trading path is a versioned decision for the
        operator, never an import."""
        for mod in (setups, risk, execsim, scalein):
            self.assertNotIn("btcalign", inspect.getsource(mod),
                             f"{mod.__name__} must not consume the audition")


if __name__ == "__main__":
    unittest.main()
