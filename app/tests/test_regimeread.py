"""The regime reading (engine/regimeread.py): direction, distance, age.

What these pin is the vocabulary, branch by branch, on hand-built series with
no store — because the phase is the thing a later playbook will be allowed
to read, and a label whose branches were never pinned is a label that drifts.
The one property above all: a vertical move after a CHoCH reads IMPULSE_<dir>,
not TRANSITION. That is the reading 2026-08-19..21 and 2026-09-03 needed.
"""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import regimeread as rr
from engine import store


def _bull_choch(level="100"):
    return {"event": "CHOCH", "direction": "BULL", "level": level}


class PhaseVocabulary(unittest.TestCase):
    def test_no_regime_is_unknown(self):
        self.assertEqual(rr.phase_of(None, None, None, None), "UNKNOWN")

    def test_a_trend_carries_its_side(self):
        self.assertEqual(rr.phase_of("BULL_TREND", None, Decimal("1"), 5), "TREND_UP")
        self.assertEqual(rr.phase_of("WEAKENING_BEAR", None, Decimal("1"), 5), "TREND_DOWN")

    def test_a_trend_far_from_its_break_is_extended(self):
        self.assertEqual(rr.phase_of("BULL_TREND", None, rr.EXTENDED_ATR, 5),
                         "TREND_UP_EXTENDED")

    def test_a_fresh_choch_is_a_turn_with_direction(self):
        self.assertEqual(rr.phase_of("TRANSITION", _bull_choch(), Decimal("0.5"), 3),
                         "TURN_UP")

    def test_a_choch_that_price_ran_from_is_an_impulse_not_a_transition(self):
        """The defining case. regime.py says TRANSITION for as long as no
        higher low confirms — which a vertical move never provides."""
        self.assertEqual(rr.phase_of("TRANSITION", _bull_choch(), rr.IMPULSE_ATR, 40),
                         "IMPULSE_UP")
        bear = {"event": "CHOCH", "direction": "BEAR", "level": "100"}
        self.assertEqual(rr.phase_of("TRANSITION", bear, rr.IMPULSE_ATR, 2),
                         "IMPULSE_DOWN")

    def test_an_aged_choch_that_never_ran_is_drift(self):
        self.assertEqual(rr.phase_of("TRANSITION", _bull_choch(), Decimal("0.4"),
                                     rr.FRESH_BARS + 1), "DRIFT_UP")

    def test_range_is_range(self):
        self.assertEqual(rr.phase_of("RANGE", _bull_choch(), Decimal("5"), 1), "RANGE")

    def test_side_is_read_off_the_phase(self):
        self.assertEqual(rr.phase_side("IMPULSE_DOWN"), "DOWN")
        self.assertEqual(rr.phase_side("TREND_UP_EXTENDED"), "UP")
        self.assertIsNone(rr.phase_side("RANGE"))
        self.assertIsNone(rr.phase_side("UNKNOWN"))


def _candles(n, start=0, step=3600, close=100, slope=0):
    out = []
    for i in range(n):
        c = Decimal(close + slope * i)
        out.append({"open_ts": start + i * step, "open": str(c), "high": str(c + 1),
                    "low": str(c - 1), "close": str(c), "volume": "1"})
    return out


class ReadingAsOf(unittest.TestCase):
    """Displacement and age come from candles CLOSED by as_of, never the
    forming bar, and every series is read by confirmed_at."""

    def _reading(self, candles, regimes, breaks):
        return rr.Reading("1H", 3600, regimes, breaks, [], [], candles)

    def test_displacement_is_signed_toward_the_break_direction(self):
        # 40 bars rising 1/bar from 100; ATR ~2. A bull CHoCH at 100 at bar 5.
        cs = _candles(40, slope=1)
        brk = [(5 * 3600 + 3600, 5 * 3600, _bull_choch("100"))]
        reg = [(5 * 3600 + 3600, 5 * 3600, "TRANSITION")]
        r = self._reading(cs, reg, brk).at(39 * 3600 + 3600)
        self.assertEqual(r["last_break"]["direction"], "BULL")
        self.assertGreater(Decimal(r["last_break"]["displacement_atr"]), rr.IMPULSE_ATR)
        self.assertEqual(r["phase"], "IMPULSE_UP")
        # the mirror: same rise, but the break was BEAR -> price went AGAINST it
        bear = [(5 * 3600 + 3600, 5 * 3600, {"event": "CHOCH", "direction": "BEAR", "level": "100"})]
        r2 = self._reading(cs, reg, bear).at(39 * 3600 + 3600)
        self.assertLess(Decimal(r2["last_break"]["displacement_atr"]), 0)
        self.assertEqual(r2["phase"], "DRIFT_DOWN")

    def test_nothing_confirmed_after_as_of_is_visible(self):
        cs = _candles(40, slope=1)
        brk = [(30 * 3600 + 3600, 30 * 3600, _bull_choch("100"))]
        reg = [(30 * 3600 + 3600, 30 * 3600, "TRANSITION")]
        r = self._reading(cs, reg, brk).at(20 * 3600)
        self.assertIsNone(r["regime"])
        self.assertIsNone(r["last_break"])
        self.assertEqual(r["phase"], "UNKNOWN")

    def test_age_and_bars_since_count_closed_bars(self):
        cs = _candles(40)
        brk = [(10 * 3600 + 3600, 10 * 3600, _bull_choch("100"))]
        reg = [(10 * 3600 + 3600, 10 * 3600, "TRANSITION")]
        r = self._reading(cs, reg, brk).at(15 * 3600 + 3600)   # bar 15 just closed
        self.assertEqual(r["last_break"]["bars_since"], 5)
        self.assertEqual(r["label_age_bars"], 5)
        self.assertEqual(r["phase"], "TURN_UP")

    def test_the_forming_bar_is_not_read(self):
        cs = _candles(40, slope=1)
        brk = [(3600, 0, _bull_choch("100"))]
        reg = [(3600, 0, "TRANSITION")]
        rd = self._reading(cs, reg, brk)
        # as_of inside bar 20 (not yet closed) must read bar 19's close
        mid = 20 * 3600 + 1800
        self.assertEqual(rd._bar_closed_by(mid), 19)


class AnnotateOnAStore(unittest.TestCase):
    def test_it_stamps_the_reading_as_of_confirmation_and_leaves_the_unknowable_alone(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = store.connect(Path(tmp.name) / "r.db")
        self.addCleanup(con.close)
        for c in _candles(40, slope=1):
            con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                        ("BTCUSDT", "1H", c["open_ts"], c["open"], c["high"],
                         c["low"], c["close"], c["volume"], "phemex-perp", 0))
        store.insert_fact(con, symbol="BTCUSDT", tf="1H", kind="structure",
                          market_time=5 * 3600, confirmed_at=6 * 3600,
                          algo_version=rr.STRUCTURE_VERSION,
                          payload={"event": "CHOCH", "direction": "BULL", "level": "100"})
        store.insert_fact(con, symbol="BTCUSDT", tf="1H", kind="regime",
                          market_time=5 * 3600, confirmed_at=6 * 3600,
                          algo_version=rr.REGIME_VERSION, payload={"regime": "TRANSITION"})
        con.commit()
        late = {"payload": {"symbol": "BTCUSDT", "tf": "1H", "direction": "SHORT"},
                "confirmed_at": 39 * 3600 + 3600, "r": -1.0}
        early = {"payload": {"symbol": "BTCUSDT", "tf": "1H", "direction": "SHORT"},
                 "confirmed_at": 2 * 3600, "r": 1.0}
        n = rr.annotate(con, [late, early])
        self.assertEqual(n, 1)
        self.assertEqual(late["payload"]["phase"], "IMPULSE_UP")
        self.assertEqual(rr.factor_extractors(late["payload"])["fades_impulse"], 1.0)
        self.assertNotIn("phase", early["payload"], "unknowable must stay MISSING")
        self.assertEqual(rr.factor_extractors(early["payload"]), {})

        # A setup-v0.20 fact carries the reading the GATE saw. The grade
        # scores that, not a recomputation — and says when the two differ.
        recorded = {"payload": {"symbol": "BTCUSDT", "tf": "1H", "direction": "SHORT",
                                "phase": "DRIFT_UP", "htf_phase": None,
                                "permitted": "BOTH", "agrees": True,
                                "context": {"action": "ALLOW"}},
                    "confirmed_at": 39 * 3600 + 3600, "r": -1.0}
        rr.annotate(con, [recorded])
        self.assertEqual(recorded["payload"]["phase"], "DRIFT_UP",
                         "the recorded reading was overwritten by a recomputation")
        self.assertEqual(recorded["payload"]["recomputed"]["phase"], "IMPULSE_UP")
        self.assertTrue(recorded["payload"]["reading_mismatch"])
        self.assertEqual(rr.factor_extractors(recorded["payload"])["fades_impulse"], 0.0,
                         "flags must follow the recorded phase")


if __name__ == "__main__":
    unittest.main()
