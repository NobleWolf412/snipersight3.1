""""At a level" — the sweep that says where price is standing, and what the
engine thinks of it.

The panel exists because a draft bracket on a chart the engine had never looked
at was indistinguishable from the engine's own plan. So the property that
matters most here is not the arithmetic — `draft.py` owns that and has its own
tests — it is that every row is honestly labelled with whether the engine is
even considering that zone, and that the labels are derived from the ENGINE's
constants rather than from a second copy of them.
"""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import draft, nearlevels, setups, store, universe
from engine.zones import ZONE_VERSION

# Every bar high 102 / low 98 gives a true range of 4, so ATR is exactly 4 and
# a distance in ATR is (price - zone top) / 4 with no rounding to reason about.
ATR = Decimal(4)
PRICE = Decimal(100)
T0 = 1_700_000_000


class ReachIsTheEnginesOwnBound(unittest.TestCase):
    """`engine_reach` mirrors the gates in `setups.py`'s forming loop.

    Read the constants out of `setups` rather than writing 1 and ("4H","1D","1W")
    here: a test that hard-codes the bound passes after someone moves the bound
    and stops describing the system, which is the failure mode
    `test_version_cascade.py` exists for one layer up.
    """

    def test_the_engines_exact_bound_is_still_in_range(self):
        """`setups.py` skips at `dist > PROX_ATR * atr`, so a distance EQUAL to
        the bound is one the engine still forms on. An exclusive comparison here
        would report the engine as blind to a zone it is watching."""
        self.assertEqual(
            nearlevels.engine_reach("1D", Decimal(setups.PROX_ATR)),
            nearlevels.IN_RANGE)

    def test_a_hair_past_the_bound_is_out_of_range(self):
        past = Decimal(setups.PROX_ATR) + Decimal("0.01")
        self.assertEqual(nearlevels.engine_reach("1D", past),
                         nearlevels.OUT_OF_RANGE)

    def test_price_inside_the_zone_is_its_own_state_not_merely_closest(self):
        """At `dist <= 0` setups.py BREAKS out of the forming loop and hands the
        zone to the TOUCH -> CONFIRMING path. Calling that "in range" would
        describe the wrong route through the engine."""
        self.assertEqual(nearlevels.engine_reach("1D", Decimal(0)),
                         nearlevels.AT_ZONE)
        self.assertEqual(nearlevels.engine_reach("1D", Decimal("-0.5")),
                         nearlevels.AT_ZONE)

    def test_a_timeframe_the_engine_never_forms_on_says_so(self):
        """The trap this panel is for. 15m and 1H are outside FORMING_TFS, so a
        row sitting 0.2 ATR from a zone on 1H is NOT something the engine is
        about to announce — it will not plan ahead there at all."""
        for tf in ("15m", "1H"):
            self.assertNotIn(tf, setups.FORMING_TFS, "premise of this test moved")
            self.assertEqual(nearlevels.engine_reach(tf, Decimal("0.2")),
                             nearlevels.NO_FORMING_ON_TF)
        for tf in setups.FORMING_TFS:
            self.assertEqual(nearlevels.engine_reach(tf, Decimal("0.2")),
                             nearlevels.IN_RANGE)

    def test_out_of_range_wins_over_the_timeframe_rule(self):
        """A 1H row 2 ATR out is out of range for the distance reason first.
        Reporting it as "the engine does not plan ahead on 1H" would imply the
        distance was fine."""
        self.assertEqual(nearlevels.engine_reach("1H", Decimal(2)),
                         nearlevels.OUT_OF_RANGE)


class Sweep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="universe",
            market_time=T0, confirmed_at=T0,
            algo_version=universe.UNIVERSE_VERSION,
            payload={"members": [
                {"symbol": "BTCUSDT", "state": "ADMITTED", "reason": "liquid_and_warm"},
                {"symbol": "ETHUSDT", "state": "ADMITTED", "reason": "liquid_and_warm"},
                {"symbol": "PF_XBTUSD", "state": "SHADOW",
                 "reason": "warming_for_venue_switch"},
            ], "top_n": 20, "min_volume_usd": 3_000_000,
               "min_daily_candles": 200, "rank_health": {}})
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _candles(self, symbol, tf, step=86400, n=40):
        for i in range(n):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, tf, T0 + i * step, "100", "102", "98", "100", "1",
                 "phemex-perp", T0))

    def _zone(self, symbol, tf, bottom, top, zid="Z1"):
        store.insert_fact(
            self.con, symbol=symbol, tf=tf, kind="zone", market_time=T0,
            confirmed_at=T0, algo_version=ZONE_VERSION,
            payload={"zone_id": f"{symbol}|{tf}|{zid}", "zone_type": "DEMAND",
                     "bottom": str(bottom), "top": str(top), "state": "TESTED",
                     "strength": 60})

    def test_it_writes_nothing(self):
        """Read-only (§1). A panel that mutated the store while rendering would
        make the act of looking part of the record."""
        self._candles("BTCUSDT", "1D")
        self._zone("BTCUSDT", "1D", 94, 96)
        self.con.commit()
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        nearlevels.sweep(self.con)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertEqual(before, after)

    def test_shadow_symbols_are_excluded_and_counted(self):
        """`risk.py` refuses to size a SHADOW symbol at any time, so a row for
        one is a level nobody can trade. It is left out — and SAID, because a
        list that cannot report what it excluded reads as a complete one."""
        self._candles("BTCUSDT", "1D")
        self._zone("BTCUSDT", "1D", 94, 96)
        self._candles("PF_XBTUSD", "1D")
        self._zone("PF_XBTUSD", "1D", 94, 96)
        self.con.commit()
        out = nearlevels.sweep(self.con)
        self.assertEqual({r["symbol"] for r in out["rows"]}, {"BTCUSDT"})
        self.assertEqual(out["counts"]["shadow_excluded"], 1)
        self.assertEqual(out["counts"]["symbols"], 2)

    def test_the_distance_is_the_one_the_chart_will_draw(self):
        """One authority per number (§6). A row and the ticket on that chart
        must not disagree about how far price is from the level, so the sweep
        calls `draft.for_symbol` rather than restating the zone search."""
        self._candles("BTCUSDT", "1D")
        self._zone("BTCUSDT", "1D", 94, 96)          # price 100, ATR 4 -> 1.00
        self.con.commit()
        row = next(r for r in nearlevels.sweep(self.con)["rows"]
                   if r["tf"] == "1D")
        chart = draft.for_symbol(self.con, "BTCUSDT", "1D")
        self.assertEqual(row["distance_atr"], chart["distance_atr"])
        self.assertEqual(row["entry"], chart["entry"])
        self.assertEqual(row["sl"], chart["sl"])
        self.assertEqual(Decimal(row["distance_atr"]), Decimal(1))
        self.assertEqual(row["engine_reach"], nearlevels.IN_RANGE)

    def test_in_reach_market_count_deduplicates_timeframes(self):
        """Overwatch draws one card per market, so its tab count must use the
        same identity even when two timeframes are simultaneously in reach."""
        self._candles("BTCUSDT", "4H", step=14_400)
        self._zone("BTCUSDT", "4H", 96, 100)
        self._candles("BTCUSDT", "1D")
        self._zone("BTCUSDT", "1D", 96, 100)
        self.con.commit()
        counts = nearlevels.sweep(
            self.con, timeframes=("4H", "1D"))["counts"]
        self.assertEqual(counts["in_engine_range"], 2)
        self.assertEqual(counts["markets_in_engine_range"], 1)

    def test_rows_come_back_nearest_first(self):
        self._candles("BTCUSDT", "1D")
        self._zone("BTCUSDT", "1D", 90, 92)          # 8 price units -> 2.00 ATR
        self._candles("ETHUSDT", "1D")
        self._zone("ETHUSDT", "1D", 96, 99)          # 1 price unit  -> 0.25 ATR
        self.con.commit()
        rows = nearlevels.sweep(self.con)["rows"]
        self.assertEqual([r["symbol"] for r in rows], ["ETHUSDT", "BTCUSDT"])
        self.assertEqual(rows[0]["engine_reach"], nearlevels.IN_RANGE)
        self.assertEqual(rows[1]["engine_reach"], nearlevels.OUT_OF_RANGE)

    def test_a_market_that_cannot_be_read_is_named_never_dropped_silently(self):
        """Degraded paths are audible (§4). A symbol missing from this list
        because its structure would not load is indistinguishable, on screen,
        from a symbol whose price is nowhere near a level — and that is the
        strongest possible wrong answer for a panel whose whole claim is "here
        is where price is standing"."""
        self._candles("BTCUSDT", "1D")
        self._zone("BTCUSDT", "1D", 94, 96)
        self.con.commit()
        real = draft.for_symbol

        def boom(con, symbol, tf):
            if symbol == "BTCUSDT" and tf == "1D":
                raise RuntimeError("zone facts unreadable")
            return real(con, symbol, tf)

        draft.for_symbol = boom
        try:
            out = nearlevels.sweep(self.con)
        finally:
            draft.for_symbol = real
        self.assertEqual(out["rows"], [])
        self.assertEqual(out["counts"]["errored"], 1)
        self.assertTrue(any("BTCUSDT" in w and "1D" in w for w in out["warnings"]),
                        "the market that could not be read must be named")

    def test_the_payload_carries_the_bounds_so_the_client_never_guesses(self):
        """The Approaching meter was scaled against the wrong constant because
        the client held its own copy. Both bounds ride on the payload."""
        out = nearlevels.sweep(self.con)
        self.assertEqual(Decimal(out["prox_atr"]), Decimal(setups.PROX_ATR))
        self.assertEqual(Decimal(out["max_distance_atr"]),
                         Decimal(draft.MAX_DISTANCE_ATR))
        self.assertEqual(out["forming_tfs"], list(setups.FORMING_TFS))


if __name__ == "__main__":
    unittest.main()
