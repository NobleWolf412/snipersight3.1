"""Market Weather — the strip that tells the operator why the screen is empty.

The single thing these tests exist to prevent: a SECOND copy of the
regime -> playbook mapping living in the API or the UI. `setups.playbook()` is
the authority on what can be traded. If the strip restated that mapping in
prose, the two copies would drift the first time the playbook changed, and the
strip would start telling the operator a trade is available that the engine
refuses to take — the exact failure this surface was built to end.

So the tests below do not assert fixed sentences for fixed regimes. They call
`setups.playbook()` themselves and require the endpoint to agree with it, for
every regime `regime.py` can emit.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from engine import regime, setups, store, universe

# Every regime _classify() can return. If regime.py grows a seventh, these
# tests fail rather than quietly leaving it undescribed on screen.
ALL_REGIMES = ("BULL_TREND", "BEAR_TREND", "WEAKENING_BULL", "WEAKENING_BEAR",
               "TRANSITION", "RANGE")


def play_for(zone_type, reg, swept=False, enabled=None):
    """Call the engine exactly as the server does, signature and all.

    `swept` now means "conditional evidence is present", not literally a sweep.
    setup-v0.7 replaced the sweep-only REVERSAL gate with 2-of-4 evidence
    ({CHOCH, SWEEP, VOLUME, STRENGTH}) because sweep-alone produced 5 setups in
    four years. Probing with one component would report TRANSITION as dead, so
    the conditional probe supplies a SUFFICIENT set — mirroring server._probe.
    """
    import inspect
    params = inspect.signature(setups.playbook).parameters
    if "rev_evidence" in params:
        ev = ["CHOCH", "VOLUME"] if swept else []
        return setups.playbook(zone_type, reg, swept, enabled, ev)
    if "enabled" in params:
        return setups.playbook(zone_type, reg, swept, enabled)
    return setups.playbook(zone_type, reg, swept)


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "weather.db"
        self._connect = store.connect
        self.con = self._connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def reset(self):
        """Fresh store between sub-cases, without leaking the previous temp dir."""
        self.tearDown()
        self.setUp()

    def universe(self, members):
        store.insert_fact(
            self.con, symbol="PORTFOLIO", tf="ALL", kind="universe",
            market_time=1, confirmed_at=1,
            algo_version=universe.UNIVERSE_VERSION,
            payload={"members": members})

    def regime_fact(self, symbol, tf, reg, confirmed_at=100):
        store.insert_fact(
            self.con, symbol=symbol, tf=tf, kind="regime",
            market_time=confirmed_at, confirmed_at=confirmed_at,
            algo_version=regime.REGIME_VERSION,
            payload={"regime": reg, "evidence": {}})

    def weather(self):
        self.con.commit()
        with patch("server.store.connect",
                   side_effect=lambda: self._connect(self.db)):
            return server.weather()

    def one(self, d1, tf4=None, symbol="BTCUSDT"):
        """A one-symbol universe with the given 1D / 4H regimes."""
        self.universe([{"symbol": symbol, "rank": 1, "state": "ADMITTED"}])
        self.regime_fact(symbol, "1D", d1)
        self.regime_fact(symbol, "4H", tf4 if tf4 is not None else d1)
        return self.weather()["symbols"][0]


class TestEligibilityIsDerivedNotDuplicated(TempStore):
    def test_live_flag_matches_playbook_for_every_regime(self):
        """`live` must mean exactly: playbook() returns a play with NO sweep.

        The distinction matters. REVERSAL is 'available' in TRANSITION only
        after a liquidity sweep, and most transitions never print one — so a
        strip that called TRANSITION tradeable would be advertising a trade
        that almost never exists.
        """
        for reg in ALL_REGIMES:
            with self.subTest(reg=reg):
                expected = any(play_for(z, reg, False) for z in ("DEMAND", "SUPPLY"))
                sym = self.one(reg)
                for tf in sym["timeframes"]:
                    self.assertEqual(tf["live"], expected,
                                     f"{reg} on {tf['tf']}: {tf['blocked_because']}")
                self.reset()          # fresh store for the next regime

    def test_reported_plays_are_exactly_what_the_engine_returns(self):
        for reg in ALL_REGIMES:
            with self.subTest(reg=reg):
                expected = set()
                for zone_type in ("DEMAND", "SUPPLY"):
                    for swept in (False, True):
                        play = play_for(zone_type, reg, swept)
                        if play is None:
                            continue
                        strategy, direction, _rank = play
                        # requires_sweep is True only when the sweepless call
                        # produced nothing for that same strategy+direction.
                        needs = play_for(zone_type, reg, False) is None
                        expected.add((strategy, direction, needs))
                sym = self.one(reg)
                got = {(p["strategy"], p["direction"], p["requires_sweep"])
                       for p in sym["timeframes"][0]["plays"]}
                self.assertEqual(got, expected)
                self.reset()

    def test_conditional_regimes_say_what_they_need_and_are_not_called_tradeable(self):
        """A regime that CAN be traded but needs supporting evidence must not be
        reported as tradeable — and must say what the condition is.

        The condition itself changed in setup-v0.7 (sweep-only became N-of-4),
        which is exactly why this asserts the rule as the ENGINE states it
        rather than as a sentence. The copy said "needs a liquidity sweep" for a
        full session after the engine stopped requiring one, which would have
        told a user a trade was impossible when it was merely conditional.
        """
        gated = [r for r in ALL_REGIMES
                 if not any(play_for(z, r, False) for z in ("DEMAND", "SUPPLY"))
                 and any(play_for(z, r, True) for z in ("DEMAND", "SUPPLY"))]
        self.assertTrue(gated, "no conditional regime found — has playbook() changed?")
        for reg in gated:
            with self.subTest(reg=reg):
                sym = self.one(reg)
                self.assertFalse(sym["live"])
                blob = (sym["meaning"] + " " + sym["why"]).lower()
                if hasattr(setups, "REVERSAL_MIN_EVIDENCE"):
                    self.assertIn("evidence", sym["meaning"].lower())
                    self.assertIn(str(setups.REVERSAL_MIN_EVIDENCE), blob,
                                  "the operator is not told how many are needed")
                else:
                    self.assertIn("sweep", sym["meaning"].lower())
                    self.assertIn(str(setups.SWEEP_LOOKBACK_BARS), sym["why"])
                self.reset()

    def test_regimes_with_no_play_at_all_say_no_playbook_covers_them(self):
        dead = [r for r in ALL_REGIMES
                if not any(play_for(z, r, s) for z in ("DEMAND", "SUPPLY")
                           for s in (False, True))]
        self.assertTrue(dead, "every regime is tradeable — has playbook() changed?")
        for reg in dead:
            with self.subTest(reg=reg):
                sym = self.one(reg)
                self.assertFalse(sym["live"])
                self.assertIn("no playbook", sym["meaning"].lower())
                self.reset()

    def test_direction_words_follow_the_playbook_direction(self):
        """'longs' or 'shorts' is the engine's own direction, not a guess."""
        for reg in ALL_REGIMES:
            play = play_for("DEMAND", reg, False) or play_for("SUPPLY", reg, False)
            if play is None:
                continue
            with self.subTest(reg=reg):
                sym = self.one(reg)
                word = "longs" if play[1] == "LONG" else "shorts"
                self.assertIn(word, sym["meaning"].lower())
                self.assertIn(play[0].replace("_", " ").lower(),
                              sym["meaning"].lower())
                self.reset()

    def test_operator_switching_a_strategy_off_changes_the_verdict(self):
        """The strip reports the engine AS CONFIGURED, not as shipped.

        setups.playbook() honours the strategy switches; a strip that ignored
        them would keep promising pullbacks after the operator turned pullbacks
        off. Skipped when the running engine has no switches to honour.
        """
        import inspect
        if "enabled" not in inspect.signature(setups.playbook).parameters:
            self.skipTest("this engine build has no strategy switches")
        from engine import settings
        settings.set_many(self.con, {"strategy_pullback": False})
        sym = self.one("BULL_TREND")
        self.assertFalse(sym["live"])
        self.assertIn("switched off", sym["meaning"].lower())
        self.assertIn("pullback", sym["timeframes"][0]["switched_off"][0].lower())


class TestWhatTheStripSays(TempStore):
    def test_agreeing_timeframes_are_marked_aligned(self):
        sym = self.one("BULL_TREND", "BULL_TREND")
        self.assertEqual(sym["tier"], 0)
        self.assertTrue(sym["live"])
        # 4H defers to 1D in setups.HTF_LADDER, and they want the same side
        four = [t for t in sym["timeframes"] if t["tf"] == "4H"][0]
        self.assertEqual(four["htf"], "1D")
        self.assertIs(four["htf_agrees"], True)

    def test_disagreeing_timeframes_say_so(self):
        sym = self.one("BULL_TREND", "BEAR_TREND")
        self.assertIn("disagree", sym["meaning"].lower())
        four = [t for t in sym["timeframes"] if t["tf"] == "4H"][0]
        self.assertIs(four["htf_agrees"], False)
        # both are still tradeable on their own timeframe; the engine does not
        # gate on alignment, it only ranks on it, and the copy must not overclaim
        self.assertTrue(all(t["live"] for t in sym["timeframes"]))

    def test_one_live_timeframe_names_which_one(self):
        sym = self.one("BULL_TREND", "RANGE")
        self.assertIn("1D only", sym["meaning"])
        self.assertTrue(sym["live"])
        self.assertEqual(sym["tier"], 1)

    def test_missing_regime_reads_as_missing_data_not_as_calm(self):
        """Loud fallback: an unmapped symbol must never render as tradeable
        silence. It has to say the data is not there."""
        self.universe([{"symbol": "NEWUSDT", "rank": 1, "state": "ADMITTED"}])
        sym = self.weather()["symbols"][0]
        self.assertFalse(sym["live"])
        self.assertEqual(sym["tier"], 4)
        self.assertIn("no regime recorded", sym["meaning"].lower())
        self.assertIn("missing data", sym["why"].lower())

    def test_warming_symbols_are_not_reported_as_a_quiet_market(self):
        self.universe([{"symbol": "NEWUSDT", "rank": 1, "state": "WARMING"}])
        self.regime_fact("NEWUSDT", "1D", "BULL_TREND")
        self.regime_fact("NEWUSDT", "4H", "BULL_TREND")
        sym = self.weather()["symbols"][0]
        self.assertEqual(sym["tier"], 4)
        self.assertIn("warming", sym["meaning"].lower())

    def test_tradeable_symbols_sort_first(self):
        self.universe([
            {"symbol": "AAA", "rank": 1, "state": "ADMITTED"},
            {"symbol": "BBB", "rank": 2, "state": "ADMITTED"},
            {"symbol": "CCC", "rank": 3, "state": "ADMITTED"}])
        for tf in ("1D", "4H"):
            self.regime_fact("AAA", tf, "RANGE")
            self.regime_fact("BBB", tf, "TRANSITION")
            self.regime_fact("CCC", tf, "BULL_TREND")
        out = self.weather()
        self.assertEqual([s["symbol"] for s in out["symbols"]],
                         ["CCC", "BBB", "AAA"])
        self.assertEqual(out["n_live"], 1)
        self.assertEqual(out["n_total"], 3)

    def test_only_the_latest_regime_per_timeframe_is_reported(self):
        """Regime facts are appended on every change; the strip shows now."""
        self.universe([{"symbol": "BTCUSDT", "rank": 1, "state": "ADMITTED"}])
        self.regime_fact("BTCUSDT", "1D", "BULL_TREND", confirmed_at=100)
        self.regime_fact("BTCUSDT", "1D", "RANGE", confirmed_at=200)
        self.regime_fact("BTCUSDT", "4H", "RANGE", confirmed_at=200)
        sym = self.weather()["symbols"][0]
        self.assertEqual(sym["timeframes"][0]["regime"], "RANGE")
        self.assertFalse(sym["live"])

    def test_every_regime_has_a_display_label_and_a_sentence(self):
        for reg in ALL_REGIMES:
            with self.subTest(reg=reg):
                sym = self.one(reg)
                for tf in sym["timeframes"]:
                    self.assertTrue(tf["label"] and tf["label"] != reg,
                                    f"{reg} has no plain-English label")
                self.assertTrue(sym["meaning"].strip())
                self.assertTrue(sym["why"].strip())
                self.reset()

    def test_response_names_the_engine_versions_that_produced_it(self):
        self.universe([{"symbol": "BTCUSDT", "rank": 1, "state": "ADMITTED"}])
        out = self.weather()
        self.assertEqual(out["regime_version"], regime.REGIME_VERSION)
        self.assertEqual(out["strategy_version"], setups.SETUP_VERSION)
        self.assertEqual(out["timeframes"], list(server.WEATHER_TFS))


class TestOneWordingForOneRegime(TempStore):
    """A regime has ONE display noun, and the server writes it.

    /api/weather feeds Market Weather and the Overwatch cards; /api/context
    feeds the chart. Both read the same recorded fact. Until `_regime_label`
    existed only the first of them carried the wording, so chart.js
    de-underscored the enum itself — and one recording read as "Bull weakening"
    on Command and "WEAKENING BULL" on the chart, forty pixels from Arm.

    These tests do not pin the words. They pin that both endpoints emit the
    SAME ones, for every regime regime.py can produce.
    """

    def context(self, symbol="BTCUSDT"):
        self.con.commit()
        with patch("server.store.connect",
                   side_effect=lambda: self._connect(self.db)):
            return server.multi_timeframe_context(symbol=symbol)

    def test_both_endpoints_word_the_same_reading_the_same_way(self):
        for reg in ALL_REGIMES:
            with self.subTest(reg=reg):
                self.universe([{"symbol": "BTCUSDT", "rank": 1,
                                "state": "ADMITTED"}])
                for tf in ("1W", "1D", "4H", "1H", "15m", "5m"):
                    self.regime_fact("BTCUSDT", tf, reg)
                rows = self.context()["timeframes"]
                for row in rows:
                    self.assertEqual(row["regime"], reg)
                    self.assertNotEqual(
                        row["label"], reg,
                        f"{reg} reaches the chart as the raw engine enum")
                    self.assertEqual(row["label"], server._regime_label(reg))
                # the identical string, not merely an equivalent one
                for wtf in self.weather()["symbols"][0]["timeframes"]:
                    self.assertEqual(
                        wtf["label"],
                        next(r["label"] for r in rows if r["tf"] == wtf["tf"]))
                self.reset()

    def test_an_unclassified_timeframe_is_labelled_rather_than_blank(self):
        """No regime fact is missing DATA, and the label has to say so — a
        blank would read as a calm market, which is a different claim."""
        self.universe([{"symbol": "BTCUSDT", "rank": 1, "state": "ADMITTED"}])
        row = self.context()["timeframes"][0]
        self.assertIsNone(row["regime"])
        self.assertTrue(row["label"].strip())
        self.assertEqual(row["label"], server._regime_label(None))


class TestEveryRowIsAccountedFor(TempStore):
    """The panel's counts have to add up to the panel's rows.

    They did not. The lede named ADMITTED, SHADOW and WARMING; the universe
    also holds REJECTED, and a symbol in it was reported by nothing. Measured
    against the live store on 2026-08-06: 18 + 12 + 1 = 31 against 32 rows,
    with u1000SHIBUSDT (below_liquidity_floor) explained by no count on the
    surface whose whole job is explaining why the screen is empty.

    Asserted as a SUM rather than by checking REJECTED is present, because the
    defect is not about that word — it is about a state the counts do not know.
    A seventh state added tomorrow fails this test instead of disappearing.
    """

    def snapshot(self):
        self.universe([
            {"symbol": "BTCUSDT", "rank": 1, "state": "ADMITTED"},
            {"symbol": "ETHUSDT", "rank": 2, "state": "ADMITTED"},
            {"symbol": "PF_XBTUSD", "rank": 3, "state": "SHADOW"},
            {"symbol": "GWEI-USD", "rank": 4, "state": "WARMING"},
            {"symbol": "SHIBUSDT", "rank": 5, "state": "REJECTED"},
        ])
        for sym in ("BTCUSDT", "ETHUSDT", "PF_XBTUSD", "GWEI-USD", "SHIBUSDT"):
            for tf in ("1D", "4H"):
                self.regime_fact(sym, tf, "BULL_TREND")
        return self.weather()

    def test_the_four_buckets_sum_to_the_rows(self):
        w = self.snapshot()
        named = w["n_total"] + w["n_shadow"] + w["n_warming"] + w["n_other"]
        self.assertEqual(named, w["n_rows"],
                         f"{w['n_rows'] - named} row(s) are in no bucket the "
                         f"panel reports — that is a symbol the operator is "
                         f"never told about")

    def test_a_state_outside_the_three_named_ones_is_counted_not_dropped(self):
        w = self.snapshot()
        self.assertEqual(w["n_other"], 1, "REJECTED must land in n_other")
        self.assertEqual(w["n_total"], 2)
        self.assertEqual(w["n_shadow"], 1)
        self.assertEqual(w["n_warming"], 1)

    def test_an_unknown_future_state_lands_in_other_rather_than_nowhere(self):
        """The point of counting the remainder instead of naming REJECTED."""
        self.universe([
            {"symbol": "BTCUSDT", "rank": 1, "state": "ADMITTED"},
            {"symbol": "WEIRDUSDT", "rank": 2, "state": "SOME_FUTURE_STATE"},
        ])
        for tf in ("1D", "4H"):
            self.regime_fact("BTCUSDT", tf, "BULL_TREND")
            self.regime_fact("WEIRDUSDT", tf, "BULL_TREND")
        w = self.weather()
        self.assertEqual(w["n_other"], 1)
        self.assertEqual(w["n_total"] + w["n_shadow"] + w["n_warming"]
                         + w["n_other"], w["n_rows"])


class TestTheUiDoesNotRestateTheRules(unittest.TestCase):
    """weather.js is allowed to decide how a verdict LOOKS, never what it is."""

    def setUp(self):
        self.js = (Path(__file__).resolve().parents[1] /
                   "static" / "weather.js").read_text(encoding="utf-8")

    def test_ui_does_not_name_a_strategy_or_a_regime_condition(self):
        # If any of these appear in the UI, a second copy of the mapping has
        # started to grow there.
        for banned in ("BULL_TREND", "BEAR_TREND", "WEAKENING_BULL",
                       "WEAKENING_BEAR", "PULLBACK", "REVERSAL"):
            self.assertNotIn(f"'{banned}'", self.js)
            self.assertNotIn(f'"{banned}"', self.js)

    def test_ui_reads_the_weather_endpoint_and_derives_no_verdict(self):
        self.assertIn("/api/weather", self.js)
        self.assertNotIn("/api/context", self.js)

    def test_ui_has_a_loud_fallback(self):
        """A failed fetch must say so; it must never render an empty calm."""
        self.assertIn("could not load", self.js)
        self.assertIn("not a quiet market", self.js)

    def test_ui_owns_its_own_stylesheet_and_mount_point(self):
        self.assertIn("weather.css", self.js)
        self.assertIn("weatherRoot", self.js)
        shell = (Path(__file__).resolve().parents[1] /
                 "static" / "shell.html").read_text(encoding="utf-8")
        self.assertIn('id="weatherRoot"', shell)
        self.assertIn("weather.js", shell)

    def test_the_cycle_backdrop_mounts_beside_the_decision_it_bears_on(self):
        """The backdrop is long-horizon CONTEXT, and its own footer says nothing
        in it opens, sizes or blocks a trade — so it cannot answer Command's
        question, "what should I do right now?". It answers Chart's, "is this
        setup worth taking?". If #cycleRoot returns to Command it is outranking
        the mission rail again, which is the arrangement this moved away from.
        """
        self.assertIn("cycleRoot", self.js)
        shell = (Path(__file__).resolve().parents[1] /
                 "static" / "shell.html").read_text(encoding="utf-8")
        mount = shell.index('id="cycleRoot"')
        chart = shell.index('id="s-chart"')
        after_chart = shell.index('id="s-results"')
        self.assertTrue(chart < mount < after_chart,
                        "#cycleRoot is not inside the chart surface")

    def test_the_weather_mount_still_carries_the_failure(self):
        """Everything weather.js used to DRAW on Command has moved. The mount
        stays for one reason: a failed /api/weather has to announce itself on
        the surface whose quiet it would otherwise be mistaken for. Empty on
        success is correct; empty on failure is the defect."""
        self.assertIn("root.innerHTML = ''", self.js)
        fail = self.js[self.js.index("function fail("):]
        self.assertIn("root.innerHTML", fail[:400])


if __name__ == "__main__":
    unittest.main()
