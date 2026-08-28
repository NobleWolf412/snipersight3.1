"""Regression tests for `engine.entrystats`.

The four properties that make this tool safe to quote in a design decision:
determinism, the no-lookahead guarantee in the counterfactual walk, the
small-sample refusal, and the planned-vs-realised arithmetic. Plus the two
failure modes actually hit while building it against the live store — a
version-ambiguous join that merged two books under one `exec` algo_version, and
a noise floor taken from the book's n rather than the feature's coverage.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import entrystats, store

DAY = 86400


def candle(con, symbol, tf, ts, o, h, lo, c, volume="10"):
    con.execute(
        "INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
        (symbol, tf, ts, str(o), str(h), str(lo), str(c), volume,
         "coinbase", ts + 60))


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.con = store.connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    # ------------------------------------------------------------- fixtures

    def exec_manifest(self, *, hold=5, entry_bars=4):
        """Record the execution manifest the order facts will point at, so the
        counterfactual walk window is read from the facts rather than guessed."""
        return store.record_manifest(self.con, "execution", {
            "version": entrystats.EXEC_VERSION, "max_holding_bars": hold,
            "max_entry_bars": entry_bars, "fill_model": "BAR_TOUCH_FULL_FILL"})

    def plan(self, sid, *, confirmed_at, entry="100", sl="95", tp="115",
             rr="3", direction="LONG", symbol="BTC-USD", tf="1D",
             version=None, rank=50, regime="BULL_TREND",
             strategy="PULLBACK", state="VALIDATED"):
        store.insert_fact(
            self.con, symbol=symbol, tf=tf, kind="setup",
            market_time=confirmed_at - DAY, confirmed_at=confirmed_at,
            algo_version=version or entrystats.SETUP_VERSION,
            payload={"setup_id": sid, "strategy": strategy,
                     "direction": direction, "entry": entry, "sl": sl, "tp": tp,
                     "rr": rr, "rank": rank, "regime": regime, "state": state})

    def order(self, sid, *, available_at, event, entry="100", manifest=None,
              symbol="BTC-USD", tf="1D", direction="LONG", bars_to_fill=0,
              limit_price=None, cross_price=None, fill_price=None):
        base = {"setup_id": sid, "side": direction, "order_type": "LIMIT",
                "limit_price": limit_price or entry,
                "cross_price": cross_price,
                "available_at": available_at,
                "max_entry_bars": 4, "execution_manifest_hash": manifest}
        extra = {}
        if event == "FILLED":
            extra = {"fill_price": fill_price or entry,
                     "bars_to_fill": bars_to_fill}
        store.insert_fact(
            self.con, symbol=symbol, tf=tf, kind="order",
            market_time=available_at - DAY,
            confirmed_at=available_at + (0 if event == "PLACED" else DAY),
            algo_version=entrystats.EXEC_VERSION,
            payload={**base, **extra, "event": event})

    def outcome(self, sid, *, available_at, outcome, entry="100",
                r_multiple="-1.10", r_gross="-1.00", bars_held=0,
                mae_r="1.00", mfe_r="0.20", symbol="BTC-USD", tf="1D",
                direction="LONG"):
        store.insert_fact(
            self.con, symbol=symbol, tf=tf, kind="exec",
            market_time=available_at - DAY, confirmed_at=available_at + 2 * DAY,
            algo_version=entrystats.EXEC_VERSION,
            payload={"setup_id": sid, "strategy": "PULLBACK",
                     "direction": direction, "outcome": outcome, "entry": entry,
                     "r_multiple": r_multiple, "r_gross": r_gross,
                     "costs_r": "0.10", "bars_held": bars_held,
                     "mae_r": mae_r, "mfe_r": mfe_r,
                     "available_at": available_at, "ambiguous_bar": False})

    def book(self, n_fills, n_misses, *, hold=5):
        """A synthetic book on well-separated 10-bar windows.

        Each setup gets its own window so a walk capped at `hold` bars cannot
        wander into the next setup's candles and resolve against them.
        """
        man = self.exec_manifest(hold=hold)
        total = n_fills + n_misses
        for i in range(total * 10 + 20):
            candle(self.con, "BTC-USD", "1D", i * DAY, 100, 101, 99, 100)
        for i in range(total):
            b = i * 10 + 2                       # order-live bar index
            avail = b * DAY
            sid = f"BTC-USD|1D|PULLBACK|z{i}"
            filled = i < n_fills
            if filled:
                # opens above the zone edge, then trades down through the stop
                candle(self.con, "BTC-USD", "1D", b * DAY, 102, 103, 94, 95)
            else:
                # opens above and runs to the target: the classic missed limit
                candle(self.con, "BTC-USD", "1D", b * DAY, 102, 116, 101, 115)
            self.plan(sid, confirmed_at=avail)
            self.order(sid, available_at=avail, event="PLACED", manifest=man)
            if filled:
                self.order(sid, available_at=avail, event="FILLED", manifest=man)
                self.outcome(sid, available_at=avail, outcome="SL")
            else:
                self.order(sid, available_at=avail, event="MISSED", manifest=man)
                self.outcome(sid, available_at=avail, outcome="MISSED",
                             r_multiple="0", r_gross="0", bars_held=0,
                             mae_r="0", mfe_r="0")
        self.con.commit()
        return man


# --------------------------------------------------------- no lookahead (§5)

class TestNoLookahead(TempStore):
    def test_first_bar_is_never_before_available_at(self):
        times = [0, DAY, 2 * DAY, 3 * DAY]
        # exact boundary: available_at IS a bar open -> that bar, not the one before
        self.assertEqual(entrystats._first_bar_at_or_after(times, 2 * DAY), 2)
        # mid-bar: the bar already in progress is NOT tradeable at its open
        self.assertEqual(entrystats._first_bar_at_or_after(times, 2 * DAY - 1), 2)
        self.assertEqual(entrystats._first_bar_at_or_after(times, 0), 0)
        self.assertIsNone(entrystats._first_bar_at_or_after(times, 4 * DAY))
        self.assertIsNone(entrystats._first_bar_at_or_after([], 0))

    def test_walk_ignores_the_bar_that_would_have_won_before_confirmation(self):
        """The bar BEFORE confirmation reaches the target. A walk that looked
        back one bar would score this a TP; the causal answer is SL."""
        cs = [
            {"open_ts": 0, "open": "100", "high": "999", "low": "100", "close": "900"},
            {"open_ts": DAY, "open": "102", "high": "103", "low": "94", "close": "95"},
            {"open_ts": 2 * DAY, "open": "95", "high": "96", "low": "94", "close": "95"},
        ]
        cf = entrystats.counterfactual(
            cs, DAY, direction="LONG", entry=Decimal("100"), sl=Decimal("95"),
            tp=Decimal("115"), max_bars=2)
        self.assertEqual(cf["fill_bar"], 1)
        self.assertEqual(cf["fill_open_ts"], DAY)
        self.assertEqual(cf["cf_outcome"], "SL")

    def test_a_bar_opening_before_available_at_is_refused_loudly(self):
        """Belt and braces on the boundary: if the index selection is ever
        changed to something looser, the walk must crash rather than quietly
        trade on a bar that had already opened."""
        cs = [{"open_ts": 0, "open": "100", "high": "101", "low": "99", "close": "100"}]
        with patch.object(entrystats, "_first_bar_at_or_after", return_value=0):
            with self.assertRaises(AssertionError):
                entrystats.counterfactual(
                    cs, 10 * DAY, direction="LONG", entry=Decimal("100"),
                    sl=Decimal("95"), tp=Decimal("115"))

    def test_report_walks_start_at_or_after_every_available_at(self):
        self.book(3, 2, hold=5)
        recs, _, _ = entrystats.load_orders(self.con)
        self.assertEqual(len(recs), 5)
        for r in recs:
            self.assertIsNotNone(r["cf"])
            self.assertGreaterEqual(r["cf"]["fill_open_ts"], r["available_at"])


# ------------------------------------------------------------- walk mechanics

class TestWalkForward(TempStore):
    def _c(self, ts, o, h, lo, c):
        return {"open_ts": ts, "open": str(o), "high": str(h),
                "low": str(lo), "close": str(c)}

    def test_a_bar_reaching_both_counts_as_a_stop(self):
        """Mirrors execsim's STOP_FIRST rule. A counterfactual that resolved
        ambiguity the other way would beat the recorded book on bookkeeping."""
        cs = [self._c(0, 100, 200, 10, 100)]
        w = entrystats.walk_forward(cs, 0, direction="LONG", sl=Decimal("95"),
                                    tp=Decimal("115"), max_bars=1)
        self.assertEqual(w["outcome"], "SL")
        self.assertTrue(w["ambiguous"])

    def test_timeout_and_unresolved_are_different_answers(self):
        flat = [self._c(i * DAY, 100, 101, 99, 100) for i in range(3)]
        done = entrystats.walk_forward(flat, 0, direction="LONG", sl=Decimal("95"),
                                       tp=Decimal("115"), max_bars=3)
        self.assertEqual(done["outcome"], "TIMEOUT")
        short = entrystats.walk_forward(flat, 0, direction="LONG", sl=Decimal("95"),
                                        tp=Decimal("115"), max_bars=10)
        self.assertEqual(short["outcome"], "UNRESOLVED")
        self.assertIsNone(short["bars_held"])

    def test_short_direction_mirrors_the_levels(self):
        cs = [self._c(0, 100, 106, 99, 105)]
        w = entrystats.walk_forward(cs, 0, direction="SHORT", sl=Decimal("105"),
                                    tp=Decimal("85"), max_bars=1)
        self.assertEqual(w["outcome"], "SL")

    def test_open_already_through_the_stop_is_unopenable_not_a_minus_one(self):
        cs = [self._c(0, 90, 95, 89, 90), self._c(DAY, 90, 91, 80, 85)]
        cf = entrystats.counterfactual(
            cs, 0, direction="LONG", entry=Decimal("100"), sl=Decimal("95"),
            tp=Decimal("115"), max_bars=2)
        self.assertEqual(cf["cf_market_geometry"], "STOP_ALREADY_BREACHED_AT_OPEN")
        self.assertIsNone(cf["cf_r_market"])
        self.assertIsNone(cf["cf_rr_market"])
        # the plan-geometry leg is still computable — it uses the planned entry
        self.assertIsNotNone(cf["cf_r_plan"])


# ------------------------------------------------- planned vs realised R:R (3)

class TestPlannedVsRealised(TempStore):
    def test_recorded_gap_is_zero_and_says_why(self):
        """entry 100 / sl 95 / tp 115 -> plan R:R 3.0, and execsim fills at the
        limit, so the realised R:R must be 3.0 exactly — not 'about' 3.0."""
        self.book(2, 0, hold=5)
        rep = entrystats.report(self.con)
        rec = rep["rr_distortion"]["recorded"]
        self.assertEqual(rec["status"], "STRUCTURALLY_ZERO")
        self.assertTrue(rec["fill_price_equals_limit_price_for_all"])
        self.assertEqual(rec["max_abs_gap_vs_exact_plan_rr"], 0.0)
        self.assertAlmostEqual(rec["planned_rr"]["median"], 3.0, places=12)
        self.assertAlmostEqual(rec["realised_rr"]["median"], 3.0, places=12)

    def test_counterfactual_geometry_is_measured_off_the_actual_open(self):
        """The fill bar opens at 102. Plan risk is 100-95=5 and plan reward
        115-100=15 (R:R 3.0); market risk is 102-95=7 and market reward
        115-102=13, so the position would open at R:R 13/7, not at 3.0. That
        collapse is the whole content of measurement 3 under SPEC 1.3."""
        self.book(1, 0, hold=5)
        recs, _, _ = entrystats.load_orders(self.con)
        cf = recs[0]["cf"]
        self.assertAlmostEqual(cf["cf_rr_plan"], 3.0, places=12)
        self.assertAlmostEqual(cf["cf_rr_market"], 13.0 / 7.0, places=12)
        # and the walk stops out, so R off the market fill is exactly -1
        self.assertEqual(cf["cf_outcome"], "SL")
        self.assertAlmostEqual(cf["cf_r_market"], -1.0, places=12)
        # while off the PLANNED entry the same exit is only -(5/5) = -1 too;
        # use a winner to prove the denominators really differ
        self.assertAlmostEqual(cf["cf_r_plan"], -1.0, places=12)

    def test_counterfactual_r_differs_between_plan_and_market_geometry(self):
        cs = [{"open_ts": 0, "open": "100", "high": "101", "low": "99", "close": "100"},
              {"open_ts": DAY, "open": "102", "high": "116", "low": "101",
               "close": "115"}]
        cf = entrystats.counterfactual(
            cs, DAY, direction="LONG", entry=Decimal("100"), sl=Decimal("95"),
            tp=Decimal("115"), max_bars=2)
        self.assertEqual(cf["cf_outcome"], "TP")
        self.assertAlmostEqual(cf["cf_r_plan"], 15.0 / 5.0, places=12)     # 3.00
        self.assertAlmostEqual(cf["cf_r_market"], 13.0 / 7.0, places=12)   # 1.857
        self.assertLess(cf["cf_r_market"], cf["cf_r_plan"])

    def test_short_geometry_is_not_the_long_formula_with_a_sign_flip(self):
        self.exec_manifest(hold=3)
        cf = entrystats.counterfactual(
            [{"open_ts": 0, "open": "98", "high": "99", "low": "84", "close": "85"}],
            0, direction="SHORT", entry=Decimal("100"), sl=Decimal("105"),
            tp=Decimal("85"), max_bars=1)
        self.assertEqual(cf["cf_outcome"], "TP")
        self.assertAlmostEqual(cf["cf_rr_plan"], 15.0 / 5.0, places=12)
        self.assertAlmostEqual(cf["cf_rr_market"], 13.0 / 7.0, places=12)


# --------------------------------------------------------- small-n refusal (4)

class TestSmallSampleRefusal(TempStore):
    def test_probe_refuses_below_the_floor_instead_of_reporting_zero(self):
        self.book(5, 2, hold=5)
        rep = entrystats.report(self.con)
        probe = rep["entry_probe"]
        self.assertFalse(probe["sufficient"])
        self.assertIsNone(probe["noise_floor"])
        self.assertEqual(probe["at_entry"], [])
        self.assertEqual(probe["post_entry_path"], [])
        self.assertIn(str(entrystats.MIN_TRADES), probe["refusal"])
        self.assertIn("refusal, not a measurement", probe["refusal"])

    def test_adverse_verdict_refuses_rather_than_declaring_no_difference(self):
        self.book(5, 2, hold=5)
        rep = entrystats.report(self.con)
        v = rep["adverse_selection"]["verdict"]
        self.assertEqual(v["code"], "INSUFFICIENT")
        self.assertIn("refusal, not a finding", v["text"])
        # no fabricated deltas: a refusal must not carry a confident-looking 0
        self.assertNotIn("delta_tp_rate", v)
        self.assertNotIn("delta_mean_r_COUNTERFACTUAL", v)

    def test_sufficient_sample_does_produce_a_verdict(self):
        self.book(entrystats.MIN_TRADES, entrystats.MIN_TRADES, hold=5)
        rep = entrystats.report(self.con)
        probe = rep["entry_probe"]
        self.assertTrue(probe["sufficient"])
        self.assertAlmostEqual(probe["noise_floor"],
                               entrystats.NOISE_Z / (entrystats.MIN_TRADES ** 0.5),
                               places=12)
        # every fill stopped out and every miss would have hit target: the
        # textbook adversely-selected book
        self.assertEqual(rep["adverse_selection"]["verdict"]["code"],
                         "ADVERSELY_SELECTED")

    def test_a_feature_is_judged_against_its_own_coverage_floor(self):
        """A feature present on 40 of 60 trades must not borrow the n=60 floor.
        Judging zone_strength (100 of 142 trades) against the book's floor was
        promoting it from noise to a finding on the live store."""
        self.book(entrystats.MIN_TRADES, entrystats.MIN_TRADES, hold=5)
        rep = entrystats.report(self.con)
        rows = {r["feature"]: r for r in rep["entry_probe"]["at_entry"]}
        for row in rows.values():
            if row["noise_floor"] is not None and row["coverage"] >= 2:
                self.assertAlmostEqual(
                    row["noise_floor"],
                    entrystats.NOISE_Z / (row["coverage"] ** 0.5), places=12)
        # zone_strength is absent from this fixture entirely -> refused, not 0.00
        self.assertIsNone(rows["zone_strength"]["r_outcome"])
        self.assertIn("REFUSED", rows["zone_strength"]["verdict"])


# ----------------------------------------------------------- determinism (§4)

class TestDeterminism(TempStore):
    def test_two_runs_produce_identical_dicts_and_identical_text(self):
        self.book(6, 4, hold=5)
        a = entrystats.report(self.con)
        b = entrystats.report(self.con)
        self.assertEqual(json.dumps(a, sort_keys=True, default=str),
                         json.dumps(b, sort_keys=True, default=str))
        self.assertEqual(entrystats.format_report(a), entrystats.format_report(b))

    def test_report_is_json_serialisable_without_a_fallback_encoder(self):
        self.book(4, 3, hold=5)
        json.dumps(entrystats.report(self.con))

    def test_record_order_does_not_depend_on_dict_insertion_order(self):
        self.book(4, 3, hold=5)
        recs, _, _ = entrystats.load_orders(self.con)
        self.assertEqual(recs, sorted(recs, key=lambda r: (r["available_at"],
                                                           r["setup_id"])))


# ------------------------------------------------------------- read-only (§1)

class TestReadOnly(TempStore):
    def test_report_writes_no_facts_and_no_manifests(self):
        self.book(5, 3, hold=5)
        before = (self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
                  self.con.execute("SELECT COUNT(*) FROM manifests").fetchone()[0],
                  self.con.execute("SELECT COUNT(*) FROM candles").fetchone()[0])
        entrystats.report(self.con)
        after = (self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
                 self.con.execute("SELECT COUNT(*) FROM manifests").fetchone()[0],
                 self.con.execute("SELECT COUNT(*) FROM candles").fetchone()[0])
        self.assertEqual(before, after)


# ------------------------------------------------------------- fill rate (1)

class TestFillRate(TempStore):
    def test_fill_rate_counts_only_resolved_orders(self):
        self.book(6, 4, hold=5)
        rep = entrystats.report(self.con)
        o = rep["fill_rate"]["overall"]
        self.assertEqual((o["placed"], o["filled"], o["missed"]), (10, 6, 4))
        self.assertAlmostEqual(o["fill_rate_ceiling"], 0.6, places=12)
        self.assertAlmostEqual(o["miss_rate_floor"], 0.4, places=12)

    def test_a_live_order_is_not_counted_as_a_miss(self):
        man = self.exec_manifest(hold=5)
        for i in range(20):
            candle(self.con, "BTC-USD", "1D", i * DAY, 100, 101, 99, 100)
        self.plan("BTC-USD|1D|PULLBACK|live", confirmed_at=2 * DAY)
        self.order("BTC-USD|1D|PULLBACK|live", available_at=2 * DAY,
                   event="PLACED", manifest=man)
        self.con.commit()
        rep = entrystats.report(self.con)
        o = rep["fill_rate"]["overall"]
        self.assertEqual(o["still_live"], 1)
        self.assertEqual(o["resolved"], 0)
        self.assertIsNone(o["fill_rate_ceiling"])
        self.assertTrue(any("still live" in w or "neither FILLED nor MISSED" in w
                            for w in rep["warnings"]))

    def test_the_ceiling_caveat_is_stated_in_the_payload(self):
        self.book(2, 1, hold=5)
        rep = entrystats.report(self.con)
        self.assertIn("CEILING", rep["fill_rate"]["model"])
        self.assertTrue(any("CEILING" in c for c in rep["caveats"]))


# ------------------------------------------- version-safe join (the live bug)

class TestVersionSafeJoin(TempStore):
    """`setup_id` is symbol|tf|strategy|zone_id and carries no version, and
    execsim did not bump its own version when setups went to v0.7. Joining on
    setup_id alone merged the two books: one order came back both FILLED and
    MISSED, and the v0.6 fill rate read 74% instead of 61%."""

    def _two_books(self):
        man = self.exec_manifest(hold=5)
        for i in range(40):
            candle(self.con, "BTC-USD", "1D", i * DAY, 100, 103, 94, 100)
        sid = "BTC-USD|1D|PULLBACK|shared"
        # v0.6 plan: entry 100, confirmed day 2 -> MISSED
        self.plan(sid, confirmed_at=2 * DAY, entry="100")
        self.order(sid, available_at=2 * DAY, event="PLACED", entry="100",
                   manifest=man)
        self.order(sid, available_at=2 * DAY, event="MISSED", entry="100",
                   manifest=man)
        self.outcome(sid, available_at=2 * DAY, outcome="MISSED", entry="100",
                     r_multiple="0", r_gross="0")
        # v0.7 plan: same setup_id, later confirmation, different entry -> FILLED
        self.plan(sid, confirmed_at=6 * DAY, entry="98", sl="93", tp="113",
                  version="setup-v0.7-draft")
        self.order(sid, available_at=6 * DAY, event="PLACED", entry="98",
                   manifest=man)
        self.order(sid, available_at=6 * DAY, event="FILLED", entry="98",
                   manifest=man)
        self.outcome(sid, available_at=6 * DAY, outcome="SL", entry="98")
        self.con.commit()

    def test_each_book_reports_only_its_own_orders(self):
        self._two_books()
        v6 = entrystats.report(self.con, setup_version="setup-v0.6-draft")
        self.assertEqual(v6["fill_rate"]["overall"]["placed"], 1)
        self.assertEqual(v6["fill_rate"]["overall"]["missed"], 1)
        self.assertEqual(v6["fill_rate"]["overall"]["filled"], 0)

        v7 = entrystats.report(self.con, setup_version="setup-v0.7-draft")
        self.assertEqual(v7["fill_rate"]["overall"]["placed"], 1)
        self.assertEqual(v7["fill_rate"]["overall"]["filled"], 1)
        self.assertEqual(v7["fill_rate"]["overall"]["missed"], 0)

    def test_the_other_book_is_named_loudly_not_silently_dropped(self):
        self._two_books()
        rep = entrystats.report(self.con, setup_version="setup-v0.6-draft")
        self.assertEqual(rep["counts"]["unclaimed_orders"], 1)
        self.assertTrue(any("setup-v0.7-draft" in w for w in rep["warnings"]),
                        rep["warnings"])

    def test_no_order_can_be_both_filled_and_missed(self):
        self._two_books()
        for ver in ("setup-v0.6-draft", "setup-v0.7-draft"):
            recs, _, _ = entrystats.load_orders(self.con, setup_version=ver)
            for r in recs:
                self.assertIn(r["state"], ("FILLED", "MISSED", "UNRESOLVED"))

    def test_maker_then_market_joins_plan_limit_and_actual_fill_once(self):
        """The current order carries three prices with three different jobs."""
        sid = "BTC-USD|1D|PULLBACK|cross|setup-v0.19-draft"
        available = 2 * DAY
        self.plan(sid, confirmed_at=available, entry="100", sl="95", tp="115",
                  version="setup-v0.19-draft")
        for event in ("PLACED", "FILLED"):
            self.order(sid, available_at=available, event=event,
                       limit_price="99.5", cross_price="100",
                       fill_price="102", entry="100")
        self.outcome(sid, available_at=available, outcome="SL", entry="102")
        self.con.commit()

        rows, counts, warnings = entrystats.load_orders(
            self.con, setup_version="setup-v0.19-draft",
            with_counterfactual=False)

        self.assertEqual((counts["plans"], counts["placed"], counts["filled"]),
                         (1, 1, 1))
        self.assertEqual(counts["unclaimed_orders"], 0)
        self.assertEqual(rows[0]["limit_price"], "99.5")
        self.assertEqual(rows[0]["fill_price"], "102")
        self.assertEqual(rows[0]["outcome"], "SL")
        self.assertFalse([w for w in warnings if "no matching PLACED" in w])


# ----------------------------------------- execution window comes from facts

class TestExecutionWindow(TempStore):
    def test_walk_window_is_read_from_the_recorded_manifest(self):
        self.book(1, 1, hold=7)
        _, counts, warns = entrystats.load_orders(self.con)
        self.assertEqual(counts["max_holding_bars"], 7)
        self.assertFalse([w for w in warns if "no execution manifest" in w])

    def test_missing_manifest_falls_back_loudly(self):
        for i in range(20):
            candle(self.con, "BTC-USD", "1D", i * DAY, 100, 101, 99, 100)
        self.plan("BTC-USD|1D|PULLBACK|z", confirmed_at=2 * DAY)
        self.order("BTC-USD|1D|PULLBACK|z", available_at=2 * DAY, event="PLACED")
        self.con.commit()
        _, counts, warns = entrystats.load_orders(self.con)
        self.assertEqual(counts["max_holding_bars"], entrystats.MAX_BARS)
        self.assertTrue(any("no execution manifest" in w for w in warns), warns)


# ------------------------------------------ counterfactual labelling (conv. 6)

class TestCounterfactualLabelling(TempStore):
    def test_every_counterfactual_number_is_marked_as_one(self):
        self.book(entrystats.MIN_TRADES, entrystats.MIN_TRADES, hold=5)
        rep = entrystats.report(self.con)
        ad = rep["adverse_selection"]
        self.assertIn("missed_COUNTERFACTUAL", ad)
        self.assertIn("COUNTERFACTUAL", ad["missed_COUNTERFACTUAL"]["label"])
        self.assertIn("COUNTERFACTUAL",
                      rep["rr_distortion"]["counterfactual_market_next_open"]["label"])
        self.assertIn("COUNTERFACTUAL", rep["book_counterfactual"]["label"])
        sb = rep["same_bar_resolution"]["overall"]
        self.assertIn("cf_same_bar_stop_out_rate_COUNTERFACTUAL", sb)
        text = entrystats.format_report(rep)
        self.assertIn("COUNTERFACTUAL", text)

    def test_recorded_and_counterfactual_r_are_never_the_same_field(self):
        self.book(4, 3, hold=5)
        rep = entrystats.report(self.con)
        ad = rep["adverse_selection"]
        self.assertIn("recorded_r_gross", ad["filled"])
        self.assertNotIn("recorded_r_gross", ad["missed_COUNTERFACTUAL"])
        self.assertIn("cf_r_plan_geometry", ad["missed_COUNTERFACTUAL"])


# ------------------------------------------------ same-bar resolution (5)

class TestSameBarResolution(TempStore):
    def test_both_denominators_are_reported_and_named_apart(self):
        """SPEC 0 quotes 59% as the same-bar STOP-OUT rate; the resolution rate
        over all fills is a different number and the two get conflated."""
        man = self.exec_manifest(hold=5)
        for i in range(60):
            candle(self.con, "BTC-USD", "1D", i * DAY, 100, 103, 94, 100)
        # 4 fills: 2 stop out on the fill bar, 1 stops out later, 1 wins later
        spec = [("SL", 0), ("SL", 0), ("SL", 3), ("TP", 4)]
        for i, (out, held) in enumerate(spec):
            sid = f"BTC-USD|1D|PULLBACK|z{i}"
            avail = (i * 10 + 2) * DAY
            self.plan(sid, confirmed_at=avail)
            self.order(sid, available_at=avail, event="PLACED", manifest=man)
            self.order(sid, available_at=avail, event="FILLED", manifest=man)
            self.outcome(sid, available_at=avail, outcome=out, bars_held=held,
                         r_multiple="2.90" if out == "TP" else "-1.10",
                         r_gross="3.00" if out == "TP" else "-1.00")
        self.con.commit()
        o = entrystats.report(self.con)["same_bar_resolution"]["overall"]
        self.assertEqual((o["n_fills"], o["n_same_bar"]), (4, 2))
        self.assertAlmostEqual(o["same_bar_resolution_rate"], 0.5, places=12)
        self.assertEqual((o["n_stop_outs"], o["n_same_bar_stop_outs"]), (3, 2))
        self.assertAlmostEqual(o["same_bar_stop_out_rate"], 2 / 3, places=12)

    def test_per_timeframe_breakdown_exists(self):
        self.book(4, 2, hold=5)
        rep = entrystats.report(self.con)
        self.assertIn("1D", rep["same_bar_resolution"]["by_tf"])


# ------------------------------------------------------------------ CLI

class TestCli(TempStore):
    def test_cli_runs_and_reports_success_only_with_orders(self):
        self.book(3, 2, hold=5)
        self.con.commit()
        self.assertEqual(entrystats.main(["--db", str(self.db)]), 0)
        self.assertEqual(entrystats.main(["--db", str(self.db), "--json"]), 0)

    def test_cli_returns_nonzero_on_an_empty_book(self):
        empty = Path(self.tmp.name) / "empty.db"
        store.connect(empty).close()
        self.assertEqual(entrystats.main(["--db", str(empty)]), 1)


if __name__ == "__main__":
    unittest.main()
