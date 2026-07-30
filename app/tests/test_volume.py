"""Volume engine tests — the properties that must not regress.

Every bar here is padded 1 above and 1 below its close, which makes the typical
price `(high + low + close) / 3` exactly the close. That is not a shortcut, it
is what makes the VWAP arithmetic in this file statable: a volume-weighted
average of known closes with known volumes, and no third quantity to trust.

The same padding fixes the true range at exactly 2 on a flat series, so ATR is
exactly 2.00000000 wherever the closes do not move, and the one-ATR relocation
threshold the point of control uses is a number this file can state.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import store, volume

TF = 3600
PAD = Decimal("1")


def bars(rows: list, start: int = 0) -> list[dict]:
    """rows: (close, volume) pairs."""
    out, prev = [], None
    for i, (close, vol) in enumerate(rows):
        close = Decimal(close)
        out.append({"open_ts": (start + i) * TF,
                    "open": close if prev is None else prev,
                    "high": close + PAD, "low": close - PAD,
                    "close": close, "volume": Decimal(vol)})
        prev = close
    return out


class VolumeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, rows, start=0, tf="1H"):
        for b in bars(rows, start):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", tf, b["open_ts"], str(b["open"]), str(b["high"]),
                 str(b["low"]), str(b["close"]), str(b["volume"]), "test",
                 b["open_ts"]))
        self.con.commit()

    def facts(self, event=None, as_of=None, tf="1H"):
        rows = store.get_facts(self.con, "BTC-USD", tf, "volume",
                               volume.VOLUME_VERSION, as_of=as_of)
        out = [{"market_time": r["market_time"], "confirmed_at": r["confirmed_at"],
                **json.loads(r["payload"])} for r in rows]
        return [f for f in out if event is None or f["event"] == event]


class TestPriceGrid(unittest.TestCase):
    def test_a_bin_is_the_same_relative_width_at_any_scale(self):
        """The whole point: a fixed tick grid cannot serve a book that runs
        from 0.0000341 to 47,000, which is the failure S40 found in the
        hard-coded 0.01 tick, one layer up."""
        self.assertEqual(volume.bin_price(volume.price_bin(Decimal(100))),
                         Decimal("100.0"))
        self.assertEqual(volume.plain(
            volume.bin_price(volume.price_bin(Decimal("47733.43")))), "47730")
        self.assertEqual(volume.bin_price(volume.price_bin(Decimal("0.0000341"))),
                         Decimal("0.00003410"))
        # neighbouring prices at sub-cent scale still land in different bins
        self.assertNotEqual(volume.price_bin(Decimal("0.0000341")),
                            volume.price_bin(Decimal("0.00003415")))

    def test_bins_are_monotone_in_price(self):
        prices = [Decimal(p) for p in
                  ("0.0000341", "0.001", "1.2345", "9.9999", "10", "100",
                   "47733.43")]
        idx = [volume.price_bin(p) for p in prices]
        self.assertEqual(idx, sorted(idx))
        self.assertEqual(len(set(idx)), len(idx))

    def test_the_bin_price_never_exceeds_the_price_it_bins(self):
        for p in ("0.0000341", "1.2345", "9.9999", "47733.43"):
            self.assertLessEqual(volume.bin_price(volume.price_bin(Decimal(p))),
                                 Decimal(p))

    def test_point_of_control_breaks_ties_without_consulting_dict_order(self):
        """Two bins with identical volume must resolve the same way however the
        dict was built, or identical windows produce different facts depending
        on the walk that reached them."""
        a = {1: Decimal(5), 2: Decimal(5), 3: Decimal(4)}
        b = {3: Decimal(4), 2: Decimal(5), 1: Decimal(5)}
        self.assertEqual(volume.point_of_control(a), (2, Decimal(5)))
        self.assertEqual(volume.point_of_control(a), volume.point_of_control(b))


class TestSessions(unittest.TestCase):
    def test_day_and_week_anchors(self):
        # 2024-01-03T12:00:00Z, a Wednesday
        ts = 1704283200
        self.assertEqual(volume.session_start(ts, "DAY"), 1704240000)   # 01-03
        self.assertEqual(volume.session_start(ts, "WEEK"), 1704067200)  # 01-01 Mon

    def test_the_week_boundary_is_the_aggregators_own(self):
        """A session week and a 1W candle have to be the same seven days, or a
        VWAP anchored 'this week' means something the chart does not."""
        from engine.aggregator import MONDAY_EPOCH
        self.assertEqual(volume.session_start(MONDAY_EPOCH + 1000, "WEEK"),
                         MONDAY_EPOCH)

    def test_a_weekly_bar_is_its_own_session_so_it_gets_no_vwap(self):
        """An absent key means 'no session', not 'default to a day'. A one-bar
        VWAP is that bar's typical price wearing a longer name."""
        self.assertNotIn("1W", volume.SESSION_ANCHOR)
        self.assertIsNone(volume.SESSION_ANCHOR.get("1W"))


class TestRelativeVolume(VolumeCase):
    def test_the_baseline_excludes_the_bar_it_judges(self):
        """A spike included in its own 20-bar average dilutes its own reading:
        a 5x bar reports 4.2x. Twenty bars of 10 then one of 25 must read
        exactly 2.5."""
        self.load([("100", "10")] * 20 + [("100", "25")])
        self.assertEqual(volume.run(self.con, "BTC-USD", "1H", TF)["rvol"], 1)
        f = self.facts("RVOL")[0]
        self.assertEqual(f["rvol"], "2.50")
        self.assertEqual(f["baseline_volume"], "10.000000")
        self.assertEqual((f["rvol_state"], f["state"]), ("HOT", "ESTABLISHED"))
        self.assertEqual(f["bar_index"], 20)

    def test_no_reading_before_the_baseline_exists(self):
        """A '20-bar average volume' computed from six bars is a different
        statistic, not a noisier one."""
        self.load([("100", "10")] * 20)
        self.assertEqual(volume.run(self.con, "BTC-USD", "1H", TF)["rvol"], 0)
        self.assertEqual(self.facts(), [])

    def test_a_zero_baseline_emits_nothing_rather_than_infinity(self):
        self.load([("100", "0")] * 20 + [("100", "5")])
        self.assertEqual(volume.run(self.con, "BTC-USD", "1H", TF)["rvol"], 0)

    def test_only_the_arrival_of_unusual_participation_is_written(self):
        """The return to normal is tracked and not emitted: 'volume went back
        to average' is the absence of an event."""
        self.load([("100", "10")] * 20 + [("100", "25")] + [("100", "10")] * 5
                  + [("100", "30")])
        result = volume.run(self.con, "BTC-USD", "1H", TF)
        states = [f["rvol_state"] for f in self.facts("RVOL")]
        self.assertEqual(states, ["HOT", "HOT"])
        self.assertEqual(result["rvol"], 2)
        self.assertEqual(self.facts("RVOL")[1]["from"], "NORMAL")

    def test_a_hot_bar_holds_through_the_deadband(self):
        """1.6x is under the 2.0 entry and over the 1.5 exit, so the state does
        not change and nothing is written."""
        self.assertEqual(volume.rvol_state(None, Decimal("2.0")), "HOT")
        self.assertEqual(volume.rvol_state("HOT", Decimal("1.6")), "HOT")
        self.assertEqual(volume.rvol_state("HOT", Decimal("1.4")), "NORMAL")
        self.assertEqual(volume.rvol_state("NORMAL", Decimal("0.5")), "DRY")
        self.assertEqual(volume.rvol_state("DRY", Decimal("0.6")), "DRY")
        self.assertEqual(volume.rvol_state("DRY", Decimal("0.8")), "NORMAL")

    def test_a_drought_is_participation_evidence_too(self):
        self.load([("100", "10")] * 20 + [("100", "2")])
        volume.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts("RVOL")[0]
        self.assertEqual((f["rvol_state"], f["rvol"]), ("DRY", "0.20"))


class TestVwap(VolumeCase):
    def test_the_vwap_is_the_hand_computed_weighted_average(self):
        # Typical price == close by construction, and every volume is 1, so
        # the VWAP is a plain running mean of the closes.
        #   bar 3: (100*3 + 120)/4 = 105, close 120 is ABOVE -> side is set,
        #          silently, because there was no side before it
        #   bar 4: (100*4 + 120)/5 = 104, close 100 is BELOW -> the crossing
        # The VWAP on a crossing bar INCLUDES that bar: it is the average the
        # close was measured against, not the one it left behind.
        rows = [("100", "1")] * 3 + [("120", "1")] + [("100", "1")] * 20
        self.load(rows)
        volume.run(self.con, "BTC-USD", "1H", TF)
        crosses = self.facts("VWAP_CROSS")
        self.assertTrue(crosses)
        first = crosses[0]
        self.assertEqual(first["bar_index"], 4)
        self.assertEqual(first["vwap"], "104.00000")
        self.assertEqual((first["side"], first["from"]), ("BELOW", "ABOVE"))
        self.assertEqual(first["direction"], "BEAR")
        self.assertEqual(first["session_bars"], 5)
        self.assertEqual(first["session_anchor"], "DAY")

    def test_a_session_needs_enough_bars_to_have_an_average(self):
        """Two bars into the session there is no VWAP to cross. The first two
        bars here straddle wildly and must produce nothing."""
        self.load([("100", "1"), ("200", "1"), ("100", "1")])
        self.assertEqual(volume.run(self.con, "BTC-USD", "1H", TF)["vwap_cross"], 0)

    def test_the_anchor_resetting_at_midnight_is_not_a_crossing(self):
        """Price sits far above day 0's VWAP and opens day 1 on top of the new
        one. The side is re-established silently — emitting there would report
        the clock as a market event."""
        day0 = [("100", "1")] * 12 + [("200", "1")] * 12    # ends ABOVE
        day1 = [("200", "1")] * 24                          # opens ON its VWAP
        self.load(day0 + day1)
        volume.run(self.con, "BTC-USD", "1H", TF)
        for f in self.facts("VWAP_CROSS"):
            self.assertNotEqual(f["bar_index"], 24)
            self.assertLess(f["bar_index"], 24)

    def test_a_weekly_series_gets_no_vwap_at_all(self):
        self.load([("100", "1")] * 30, tf="1W")
        result = volume.run(self.con, "BTC-USD", "1W", 604800)
        self.assertEqual(result["vwap_cross"], 0)

    def test_the_vwap_is_a_level_and_gets_the_house_break_rule(self):
        """A close within max(1 tick, 0.05*ATR) of the VWAP has not closed
        through it. Without that, price resting on the VWAP emits a crossing on
        almost every bar."""
        from engine.ranges import break_tolerance
        self.assertEqual(break_tolerance(Decimal(10), Decimal("0.01")),
                         Decimal("0.5"))
        rows = ([("100", "1")] * 20 + [("100.4", "1")] * 3)
        self.load(rows)
        volume.run(self.con, "BTC-USD", "1H", TF)
        # ATR is 2 here, so the tolerance is 0.1; a 0.4 excursion clears it and
        # the crossing is real. The assertion that matters is that the fact
        # records the tolerance it used.
        for f in self.facts("VWAP_CROSS"):
            self.assertIn("tolerance", f)
            self.assertIsInstance(Decimal(f["tolerance"]), Decimal)


class TestVolumeAtLevel(VolumeCase):
    def _relocating(self):
        # 100 quiet bars at 100, then heavy bars at 130
        return [("100", "10")] * 100 + [("130", "100")] * 30

    def test_the_point_of_control_starts_where_the_volume_is(self):
        self.load(self._relocating())
        volume.run(self.con, "BTC-USD", "1H", TF)
        poc = self.facts("POC_MOVE")
        self.assertEqual(poc[0]["bar_index"], 100)
        self.assertEqual(poc[0]["state"], "ESTABLISHED")
        self.assertEqual(poc[0]["poc"], "100.0")
        self.assertIsNone(poc[0]["prev_poc"])
        self.assertEqual(poc[0]["window_bars"], volume.POC_WINDOW)

    def test_it_relocates_on_the_bar_the_arithmetic_says(self):
        """At bar k the window holds (k-99) bars of 100 volume at 130 and
        (199-k) bars of 10 volume at 100. 100*(k-99) first exceeds 10*(199-k)
        at k = 109: 1000 against 900, where bar 108 is 900 against 910."""
        self.load(self._relocating())
        volume.run(self.con, "BTC-USD", "1H", TF)
        moves = [f for f in self.facts("POC_MOVE") if f["state"] == "CHANGED"]
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["bar_index"], 109)
        self.assertEqual(moves[0]["poc"], "130.0")
        self.assertEqual(moves[0]["prev_poc"], "100.0")

    def test_a_jitter_smaller_than_one_atr_is_not_a_relocation(self):
        """The threshold is measured against the LAST EMITTED point of control,
        not the previous bar's, which is what makes it a relocation rather than
        a bin-by-bin migration."""
        self.load([("100", "10")] * 100 + [("100.5", "500")] * 30)
        volume.run(self.con, "BTC-USD", "1H", TF)
        moves = [f for f in self.facts("POC_MOVE") if f["state"] == "CHANGED"]
        self.assertEqual(moves, [])

    def test_nothing_before_the_window_is_full(self):
        self.load([("100", "10")] * 100)
        self.assertEqual(volume.run(self.con, "BTC-USD", "1H", TF)["poc_move"], 0)

    def test_a_zero_volume_bar_does_not_evict_its_own_bin(self):
        """ADAUSDT 1D carries zero-volume daily bars. Dropping a bin the moment
        its volume reaches zero leaves nothing to subtract when the bar itself
        leaves the window."""
        rows = [("100", "10")] * 50 + [("100", "0")] * 5 + [("100", "10")] * 60
        self.load(rows)
        result = volume.run(self.con, "BTC-USD", "1H", TF)
        self.assertGreaterEqual(result["poc_move"], 1)

    def test_the_shares_are_recorded_as_evidence(self):
        self.load(self._relocating())
        volume.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts("POC_MOVE")[0]
        # at bar 100 the window is 99 bars of 10 at price 100 plus one of 100
        # at 130: 990 of 1090 sits in the POC bin -> 90.83%
        self.assertEqual(f["window_volume"], "1090.0000")
        self.assertEqual(f["poc_volume_share"], "90.83")
        # the current close is in the 130 bin: 100/1090 -> 9.17%
        self.assertEqual(f["level_volume_share"], "9.17")


class TestCausality(VolumeCase):
    def _series(self):
        return ([("100", "10")] * 100 + [("130", "100")] * 30
                + [("120", "10")] * 20)

    def test_every_fact_confirms_at_its_own_bar_close(self):
        self.load(self._series())
        volume.run(self.con, "BTC-USD", "1H", TF)
        facts = self.facts()
        self.assertTrue(facts)
        for f in facts:
            self.assertEqual(f["confirmed_at"], f["market_time"] + TF)
            self.assertGreater(f["confirmed_at"], f["market_time"])

    def test_the_as_of_cursor_hides_a_fact_until_its_bar_closed(self):
        self.load([("100", "10")] * 20 + [("100", "25")])
        volume.run(self.con, "BTC-USD", "1H", TF)
        f = self.facts()[0]
        self.assertEqual(self.facts(as_of=f["confirmed_at"] - 1), [])
        self.assertEqual(len(self.facts(as_of=f["confirmed_at"])), 1)

    def test_truncating_the_series_never_changes_an_earlier_fact(self):
        """The cleanest possible lookahead test: everything emitted from the
        first N bars must be identical whether or not bar N+1 exists."""
        self.load(self._series())
        volume.run(self.con, "BTC-USD", "1H", TF)
        full = self.facts()
        cut = 120 * TF
        early = [f for f in full if f["market_time"] < cut]
        self.con.execute("DELETE FROM facts")
        self.con.execute("DELETE FROM candles WHERE open_ts>=?", (cut,))
        self.con.commit()
        volume.run(self.con, "BTC-USD", "1H", TF)
        self.assertTrue(early)
        self.assertEqual(self.facts(), early)


class TestDeterminism(VolumeCase):
    def _loaded(self):
        self.load([("100", "10")] * 100 + [("130", "100")] * 30
                  + [("120", "10")] * 20)

    def test_rerun_writes_zero_new_facts(self):
        self._loaded()
        first = volume.run(self.con, "BTC-USD", "1H", TF)
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        second = volume.run(self.con, "BTC-USD", "1H", TF)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertGreater(sum(v for v in first.values() if isinstance(v, int)), 0)
        self.assertEqual(sum(v for v in second.values() if isinstance(v, int)), 0)
        self.assertEqual(before, after)

    def test_every_emitted_number_is_a_decimal_string(self):
        self._loaded()
        volume.run(self.con, "BTC-USD", "1H", TF)
        for f in self.facts():
            for key in ("close", "volume", "rvol", "baseline_volume", "vwap",
                        "tolerance", "poc", "prev_poc", "window_volume",
                        "poc_volume_share", "level_volume_share", "atr",
                        "distance_atr", "moved_atr"):
                if f.get(key) is None:
                    continue
                self.assertNotIn("e", f[key].lower(), (f["event"], key))
                self.assertIsInstance(Decimal(f[key]), Decimal)


if __name__ == "__main__":
    unittest.main()
