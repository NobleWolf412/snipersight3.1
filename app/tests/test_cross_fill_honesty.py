"""A simulated fill must be a price the bar actually traded.

The MAKER_THEN_MARKET crossing leg booked its market fill at the PLAN's entry
price and never looked at the bar it was filling on. That price is
`candles[ci+1]["open"]` (setups.py), and `order_i = ci+1` with
`MAKER_WAIT_BARS = 2` puts the cross on bar ci+3 — so the model was booking a
market order at a print from two bars earlier. The comment licensing that price
calls it "a price that demonstrably traded", which is true of the bar it came
from and false of the bar it was applied to.

Measured on exec-v0.13 before the fix: 95 crossed orders, **78 (82.1%) booked
outside their own fill bar's [low, high]**, and never adversely — 94 of 95
filled better than the crossing bar's open. One ETHUSDT long was booked at
2075.49 on a bar whose LOW was 2094.69.

Consequence, re-simulated: the book restates from +95.85 R to +31.95 R over 642
trades (+0.1493 -> +0.0498 per trade), and REVERSAL on the traded book falls
from +0.266 R CI [+0.038, +0.498] to +0.151 R CI [-0.066, +0.379] — it stops
clearing zero. The strategy's headline result was substantially an artifact of
this bug.

The invariant below is the general form, and it is cheap: for every FILLED
order, the entry must lie within the traded range of the bar it filled on, once
modelled slippage is allowed for. Nothing about it is specific to the crossing
leg, which is why it would have caught this the day it shipped.
"""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import costs, execsim, store  # noqa: E402
from engine.swings import compute_atr  # noqa: E402

TF_SECONDS = {"15m": 900, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}


class CrossFillHonesty(unittest.TestCase):
    """Unit-level: the crossing branch must price off the crossing bar."""

    def test_cross_fills_at_the_crossing_bar_not_the_plan(self):
        """A cross is a market order. It fills at the market, on THIS bar.

        Constructed so the passive limit can never fill: the plan rests below
        every subsequent low, and price runs away upward. Before the fix the
        cross booked `entry` (the plan price, far below the crossing bar) and
        handed the trade a free gain it never earned.
        """
        """Repinned 4 Aug 2026: the branch now DELEGATES to execsim.cross_fill.

        The rule was enforced here on execsim's inline code while `abtest` kept
        the v0.13 behaviour it was supposed to be validating — the harness ran
        the exact bug the simulator had fixed and flattered the book by 62 R.
        One implementation now, so the properties are asserted where they live
        and both callers get them.
        """
        src = (APP / "engine" / "execsim.py").read_text(encoding="utf-8")
        cross = src[src.index("# CROSS:"):src.index("elif fill_i is None:")]
        self.assertIn("cross_fill(", cross,
                      "the crossing branch must use the shared fill model")

        fn = src[src.index("def cross_fill("):src.index("def settle(")]
        self.assertIn('candles[fill_i]["open"]', fn,
                      "the cross must price off the bar it fills on, not the plan")
        self.assertIn("market_slippage_atr", fn,
                      "a market cross pays slippage, like every other market order")
        self.assertIn("atr_at_fill is None", fn,
                      "a missing ATR must degrade loudly, never book a free fill")

        # and the harness must use the SAME model, which is the whole point.
        #
        # Repinned again: this asked for `execsim.cross_fill(` in abtest, which
        # was right when the crossing PRICE was the shared surface. It no longer
        # is — abtest now enters through `execsim.simulate_entry`, which calls
        # cross_fill itself. Sharing the price alone still left the harness
        # choosing its own crossing BAR, its own maker limit and its own risk
        # denominator, so the assertion has to follow the surface up rather than
        # keep pinning the narrower one.
        ab = (APP / "engine" / "abtest.py").read_text(encoding="utf-8")
        self.assertIn("execsim.simulate_entry(", ab,
                      "abtest fills on its own terms again — that divergence "
                      "reported 70.0 R against the book's real 7.9 R")
        self.assertNotIn("entry_px = entry          # market: the planned open", ab,
                         "the v0.13 plan-price cross is back in the harness")
        entry_block = ab[ab.index("def run_variant("):ab.index("def summarise(")]
        self.assertNotIn("Decimal(candles[", entry_block,
                         "run_variant is scanning bars for a fill again — a "
                         "second fill model is how it lost this correction "
                         "the first time")


class RecordedFillsLieWithinTheirBar(unittest.TestCase):
    """Store-level: no recorded fill may sit outside the bar it filled on.

    The general invariant. Skips when the live store is unavailable so the
    suite still runs on a clean checkout, but on a real store this is the check
    that would have caught the defect on day one.
    """

    @classmethod
    def setUpClass(cls):
        db = APP / "data" / "snipersight.db"
        if not db.exists():
            raise unittest.SkipTest("no live store")
        cls.con = store.connect()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "con"):
            cls.con.close()

    def test_no_fill_is_priced_outside_its_own_bar(self):
        bad, checked = [], 0
        rows = self.con.execute(
            "SELECT symbol, tf, payload FROM facts WHERE kind='exec' "
            "AND algo_version=?", (execsim.EXEC_VERSION,)).fetchall()
        if not rows:
            self.skipTest(f"no {execsim.EXEC_VERSION} facts yet — "
                          f"re-run the simulator to populate them")
        for sym, tf, raw in rows:
            p = json.loads(raw)
            ft = p.get("fill_ts")
            if ft is None:
                continue
            bar = self.con.execute(
                "SELECT open, high, low FROM candles WHERE symbol=? AND tf=? "
                "AND open_ts=?", (sym, tf, int(ft) - TF_SECONDS[tf])).fetchone()
            if not bar:
                continue
            checked += 1
            entry = Decimal(p["entry"])
            _open, _high, _low = bar[0], bar[1], bar[2]
            lo, hi = Decimal(_low), Decimal(_high)
            # Slippage can legitimately carry a market fill PAST the bar's
            # extreme, so the band is widened by the modelled amount. It can
            # never carry it to the favourable side, which is the direction the
            # bug always ran.
            prof = costs.profile_for(sym)
            candles = [dict(r) for r in store.get_candles(self.con, sym, tf)]
            idx = {c["open_ts"]: i for i, c in enumerate(candles)}
            i = idx.get(int(ft) - TF_SECONDS[tf])
            atr = compute_atr(candles)[i] if i is not None else None
            slack = prof.market_slippage_atr * atr if atr else Decimal(0)
            if not (lo - slack <= entry <= hi + slack):
                bad.append((sym, tf, p.get("strategy"), str(entry),
                            f"{lo}-{hi}", p.get("entry_fee_role")))
        self.assertFalse(bad, (
            f"{len(bad)} of {checked} recorded fills are priced outside the bar "
            f"they filled on — the simulator is inventing prices. "
            f"First few: {bad[:5]}"))


if __name__ == "__main__":
    unittest.main()
