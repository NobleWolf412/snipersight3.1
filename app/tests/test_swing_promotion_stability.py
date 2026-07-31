"""A promotion fact must not change because the scanner ran again.

swing-v0.8 embedded `evidence.held_candles` — which increments every candle a
pivot holds — inside the content-hashed, append-only promotion fact. Each scan
cycle the integer moved, the hash moved, and `store.insert_fact` appended the
same pivot again: 193,718 promotion rows for 15,603 pivots on the live store,
one AAVEUSDT 4H pivot 11 times (held 987..997). zones counted the copies as
cluster neighbours and liquidity as pool members, so zone strength — a REVERSAL
gate — inflated monotonically for as long as the process stayed up.

swing-v0.9's rule: held_candles is censored at HELD_FULL (the cap the score
card always applied), and the fact is emitted only once that window has CLOSED
— price traded beyond the extreme, or HELD_FULL bars elapsed — with
confirmed_at = when that became knowable (§5).

These tests drive the REAL recursion (micro fractals -> locals -> tier
promotion) over a constructed zigzag whose middle high dominates both same-type
neighbours, and assert the three faces of the rule: appending a bar re-emits
nothing; an open window emits nothing; a close (by cap or by breach) emits
exactly once, stamped when the window closed.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import store, swings

TF = 3600
SYMBOL, TFNAME = "BTC-USD", "1H"
PAD = Decimal("0.01")
LEG_BARS = 8
# Alternating low/high anchors; index 5 (bar 40) is the dominant high — more
# extreme than the same-type pivots two steps either side of it.
ANCHORS = [50, 100, 45, 105, 40, 121, 60, 100, 55, 95, 58]
BIG_BAR = 5 * LEG_BARS
BIG_PRICE = Decimal("121.01")            # anchor close 121 + the high pad
HELD_FULL = int(swings.HELD_FULL)
WINDOW_CLOSE_BAR = BIG_BAR + HELD_FULL   # bar 130 when price never trades beyond


def closes(n_bars, tail="flat"):
    """Piecewise-linear path through ANCHORS, then a tail: 'flat' oscillates in
    a band far too small to mint new LOCAL swings; 'breach' rises 4.5/bar and
    takes out the dominant high."""
    path = [Decimal(ANCHORS[0])]
    for a, b in zip(ANCHORS, ANCHORS[1:]):
        step = (Decimal(b) - Decimal(a)) / LEG_BARS
        for k in range(1, LEG_BARS + 1):
            path.append(Decimal(a) + step * k)
    tri = (0, 1, 2, 3, 2, 1)
    while len(path) < n_bars:
        i = len(path) - LEG_BARS * (len(ANCHORS) - 1) - 1
        if tail == "flat":
            path.append(Decimal(ANCHORS[-1]) + Decimal("0.13") * tri[i % 6])
        else:
            path.append(Decimal(ANCHORS[-1]) + Decimal("4.5") * (i + 1))
    return path[:n_bars]


def bars_from(path):
    # Open at the midpoint of the leg, not the prior close: a bar that opens AT
    # the previous close carries that close in its own high/low, which ties the
    # pivot bar's extreme — and the fractal rule is STRICT, ties mint nothing.
    out, prev = [], None
    for i, close in enumerate(path):
        open_ = close if prev is None else (prev + close) / 2
        out.append({"open_ts": i * TF, "open": open_,
                    "high": max(open_, close) + PAD,
                    "low": min(open_, close) - PAD, "close": close})
        prev = close
    return out


class PromotionStability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")
        self.loaded = 0

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, bars):
        for b in bars[self.loaded:]:
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (SYMBOL, TFNAME, b["open_ts"], str(b["open"]), str(b["high"]),
                 str(b["low"]), str(b["close"]), "1", "test", b["open_ts"]))
        self.con.commit()
        self.loaded = len(bars)

    def run_engine(self):
        return swings.run(self.con, SYMBOL, TFNAME, TF)

    def promotions(self):
        out = {}
        for r in store.get_facts(self.con, SYMBOL, TFNAME, "swing",
                                 swings.SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ("INTERMEDIATE", "MAJOR"):
                out.setdefault((r["market_time"], p["tier"]), []).append(
                    (r["confirmed_at"], p))
        return out

    def assert_no_duplicates(self, promos):
        dupes = {k: len(v) for k, v in promos.items() if len(v) > 1}
        self.assertFalse(dupes, f"same pivot recorded more than once: {dupes}")

    def test_appending_a_bar_re_emits_nothing(self):
        """The defect itself: under v0.8 one more candle meant one more copy of
        every held pivot. Now a settled promotion is a fixed point."""
        self.load(bars_from(closes(WINDOW_CLOSE_BAR + 5)))
        self.run_engine()
        promos = self.promotions()
        self.assert_no_duplicates(promos)
        key = (BIG_BAR * TF, "INTERMEDIATE")
        self.assertIn(key, promos, f"dominant high missing; got {list(promos)}")
        confirmed_at, payload = promos[key][0]
        self.assertEqual(payload["evidence"]["held_candles"], HELD_FULL,
                         "an unbroken pivot's held must be censored at the cap")
        self.assertEqual(confirmed_at, (WINDOW_CLOSE_BAR + 1) * TF,
                         "confirmed_at must be the close of the bar that "
                         "closed the held window")

        before = self.con.execute(
            "SELECT COUNT(*) FROM facts WHERE kind='swing'").fetchone()[0]
        self.run_engine()
        self.assertEqual(before, self.con.execute(
            "SELECT COUNT(*) FROM facts WHERE kind='swing'").fetchone()[0],
            "an unchanged store must be a no-op re-run")

        self.load(bars_from(closes(WINDOW_CLOSE_BAR + 6)))
        self.run_engine()
        after = self.promotions()
        self.assert_no_duplicates(after)
        self.assertEqual(len(after[key]), 1,
                         "one more candle must not re-emit a settled pivot")
        self.assertEqual(after[key][0][1], payload,
                         "a settled payload must be byte-stable across bars")

    def test_an_open_window_emits_nothing(self):
        """Halfway through the held window the tier is unknowable (§5): the
        score still depends on candles that do not exist. v0.8 emitted a
        provisional value here and then chased it with duplicates."""
        self.load(bars_from(closes(BIG_BAR + 51)))
        self.run_engine()
        held_open = [k for k in self.promotions() if k[0] == BIG_BAR * TF]
        self.assertEqual(held_open, [],
                         "a pivot whose held window is open must not be in "
                         "the store yet")
        self.load(bars_from(closes(WINDOW_CLOSE_BAR + 5)))
        self.run_engine()
        promos = self.promotions()
        self.assert_no_duplicates(promos)
        self.assertIn((BIG_BAR * TF, "INTERMEDIATE"), promos,
                      "the pivot must appear once its window closes")

    def test_a_breach_closes_the_window_early(self):
        """Price trading beyond the extreme settles held before the cap does —
        the fact is emitted then, held is final, and later bars change nothing."""
        path = closes(100, tail="breach")
        bars = bars_from(path)
        breach = next(j for j in range(BIG_BAR + 1, len(bars))
                      if bars[j]["high"] > BIG_PRICE)
        self.assertLess(breach - BIG_BAR, HELD_FULL, "fixture: breach must "
                        "land inside the window or this test proves nothing")
        self.load(bars)
        self.run_engine()
        promos = self.promotions()
        self.assert_no_duplicates(promos)
        key = (BIG_BAR * TF, "INTERMEDIATE")
        self.assertIn(key, promos)
        confirmed_at, payload = promos[key][0]
        self.assertEqual(payload["evidence"]["held_candles"], breach - BIG_BAR)
        self.assertEqual(confirmed_at, (breach + 1) * TF,
                         "the breach bar's close is when held became knowable")


if __name__ == "__main__":
    unittest.main()
