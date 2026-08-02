"""Manual paper book — the properties that make it safe to have at all.

Two of these tests are the reason the module exists rather than nice-to-haves:

  · ISOLATION. A manual trade must be unreachable from every strategy query.
    If this regresses, discretionary trades silently join the record that
    decides whether live execution is unlocked.
  · CAUSALITY. An intent armed now must not fill on a bar that already closed.
    If this regresses the book still "works" and simply reports a skill the
    operator never had, which is the worst possible failure mode: plausible,
    flattering, and invisible.

Bars are stated explicitly rather than generated, so every fill price in an
assertion is a number this file can point at.
"""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import manual, store, execsim, setups

TF = 3600
SPOT = "BTC-USD"        # coinbase-spot — cannot short
PERP = "BTCUSDT"        # phemex-perp   — can short


class ManualCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def load(self, bars, symbol=SPOT, tf="1H"):
        for i, (o, h, l, c) in enumerate(bars):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, tf, i * TF, str(o), str(h), str(l), str(c),
                 "1", "test", i * TF))
        self.con.commit()

    def flat(self, n, o=100, h=101, l=99, c=100):
        return [(o, h, l, c)] * n

    def run_engine(self, symbol=SPOT, tf="1H"):
        return manual.run(self.con, symbol, tf, TF)

    def execs(self, symbol=SPOT, tf="1H"):
        return [__import__("json").loads(r["payload"]) for r in store.get_facts(
            self.con, symbol, tf, manual.EXEC_KIND, manual.MANUAL_VERSION)]

    # ---------- isolation: the reason for a separate book ----------

    def test_manual_facts_are_invisible_to_every_strategy_query(self):
        """The separation must be structural, not a filter someone remembers.

        `edgestats`/`factorstats` read the book by algo_version. If a manual
        trade ever answers one of those queries, the graded record silently
        becomes 'strategy plus operator' and every expectancy figure built on
        it is wrong in an undetectable direction.
        """
        self.load(self.flat(6) + [(100, 104, 99, 103)] + self.flat(5))
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        self.assertTrue(self.execs(), "precondition: manual facts exist")
        for version in (setups.SETUP_VERSION, execsim.EXEC_VERSION):
            for kind in ("setup", "exec", "order", "setup_rejection"):
                self.assertEqual(
                    store.get_facts(self.con, SPOT, "1H", kind, version), [],
                    f"a manual trade surfaced under {kind}/{version}")
        # and the manual version is not, and must never become, a strategy tag
        self.assertNotIn(manual.MANUAL_VERSION,
                         (setups.SETUP_VERSION, execsim.EXEC_VERSION))

    # ---------- causality: §5, and the one that would fake a track record ----

    def test_an_intent_cannot_fill_on_a_bar_that_already_closed(self):
        """Arming at bar 30 must ignore bars 0-29 entirely.

        Those bars trade straight through the entry AND the target, so a
        resolver that scanned from the start would report a fast, confident
        winner. The only honest answer is MISSED: after the order existed,
        price never came back to the entry.
        """
        past = [(100, 105, 95, 100)] * 30      # trades through entry 100 and tp 104
        after = [(88, 90, 85, 88)] * 11        # nowhere near the entry
        self.load(past + after)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=30 * TF)
        self.run_engine()
        rows = self.execs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "MISSED")
        self.assertEqual(rows[0]["r_multiple"], "0")

    def test_the_bar_in_progress_when_armed_is_not_eligible(self):
        """A bar that closes exactly AT `armed_at` is still the past.

        Bar 9 closes at 10*TF. Arming at 10*TF must start at bar 10 — the
        conservative reading, because a bar already in progress has printed
        part of its range before the order existed.
        """
        times = [i * TF for i in range(20)]
        self.assertEqual(manual._first_eligible_bar(times, TF, 10 * TF), 10)
        # one second into bar 10 still cannot use bar 10's own close
        self.assertEqual(manual._first_eligible_bar(times, TF, 10 * TF + 1), 11)

    # ---------- resolution, mirroring execsim ----------

    def test_target_hit_resolves_tp_with_costs_deducted(self):
        bars = self.flat(6) + [(100, 104, 99, 103)] + self.flat(5)
        self.load(bars)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TP")
        # gross is exactly 2R on a 2-wide stop and a 4-wide target
        self.assertEqual(row["r_gross"], "2.00")
        # net must be strictly worse than gross: fees are always paid
        self.assertLess(Decimal(row["r_multiple"]), Decimal(row["r_gross"]))

    def test_stop_hit_resolves_sl(self):
        bars = self.flat(4) + [(100, 101, 98, 99)] + self.flat(5)
        self.load(bars)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        self.assertEqual(self.execs()[0]["outcome"], "SL")

    def test_a_bar_reaching_both_counts_as_the_stop(self):
        """execsim's STOP_FIRST rule, restated here only as an assertion.

        Two paper books that resolved the same bar differently would make the
        comparison the operator actually wants — judgement vs engine —
        meaningless, because the plans would not be the only thing differing.
        """
        bars = self.flat(3) + [(100, 105, 97, 100)] + self.flat(4)
        self.load(bars)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "SL")
        self.assertTrue(row["ambiguous_bar"])

    def test_entry_never_touched_within_the_window_is_missed(self):
        self.load([(120, 121, 119, 120)] * 10)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        self.assertEqual(self.execs()[0]["outcome"], "MISSED")

    def test_unresolved_intent_stays_open_and_writes_nothing(self):
        """Append-only: an intent that cannot resolve yet must not guess."""
        self.load(self.flat(3))
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        r = self.run_engine()
        self.assertEqual(r["OPEN"], 1)
        self.assertEqual(self.execs(), [])

    def test_rerunning_does_not_resolve_the_same_intent_twice(self):
        bars = self.flat(6) + [(100, 104, 99, 103)] + self.flat(5)
        self.load(bars)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        self.run_engine()
        self.run_engine()
        self.assertEqual(len(self.execs()), 1)

    # ---------- validation: refuse before recording ----------

    def test_spot_cannot_short_and_nothing_is_written(self):
        self.load(self.flat(10))
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, SPOT, "1H", "SHORT",
                                 entry=100, tp=96, sl=102, created_at=0)
        self.assertEqual(
            store.get_facts(self.con, SPOT, "1H", manual.INTENT_KIND,
                            manual.MANUAL_VERSION), [])

    def test_a_perp_may_short(self):
        self.load(self.flat(10), symbol=PERP)
        out = manual.create_intent(self.con, PERP, "1H", "SHORT",
                                   entry=100, tp=96, sl=102, created_at=0)
        self.assertEqual(out["venue"], "phemex-perp")

    def test_stop_on_the_wrong_side_is_refused(self):
        for direction, entry, tp, sl in (("LONG", 100, 104, 101),
                                         ("LONG", 100, 99, 98)):
            with self.subTest(direction=direction, sl=sl):
                with self.assertRaises(manual.IntentRejected):
                    manual.create_intent(self.con, SPOT, "1H", direction,
                                         entry=entry, tp=tp, sl=sl, created_at=0)

    def test_size_is_derived_from_risk_and_the_stop_distance(self):
        self.load(self.flat(10))
        out = manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100,
                                   tp=104, sl=98, created_at=0, risk_usd=200)
        # $200 risked over a $2 stop is 100 units
        self.assertEqual(Decimal(out["size_units"]), Decimal(100))

    # ---------- leverage: margin only, and the liquidation gate ----------

    def test_leverage_changes_margin_but_never_size_or_outcome(self):
        """The spec's rule, asserted rather than trusted: "risk stays distance
        to stop; margin = notional / leverage. Leverage never widens a stop."

        Same prices at 1x and 10x must resolve to the SAME r_multiple. If they
        ever diverge, leverage has leaked into sizing and 2%-per-trade has
        stopped meaning 2%.
        """
        bars = self.flat(6) + [(100, 104, 99, 103)] + self.flat(5)
        self.load(bars, symbol=PERP)
        a = manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                                 sl=98, created_at=0, risk_usd=200, leverage=1)
        b = manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                                 sl=98, created_at=TF, risk_usd=200, leverage=10)
        self.assertEqual(a["size_units"], b["size_units"], "size must not move")
        # margin is what moves: notional / leverage
        self.assertEqual(Decimal(a["margin_usd"]) / 10, Decimal(b["margin_usd"]))
        self.assertIsNone(a["liquidation"], "1x cannot be liquidated by price")
        self.assertEqual(Decimal(b["liquidation"]), Decimal("90.500"))
        self.run_engine(symbol=PERP)
        rs = {r["intent_id"]: r for r in self.execs(symbol=PERP)}
        self.assertEqual(len(rs), 2)
        vals = {r["r_multiple"] for r in rs.values()}
        self.assertEqual(len(vals), 1,
                         f"leverage changed the outcome: {vals}")

    def test_a_stop_beyond_liquidation_is_refused_by_the_api_not_just_the_ui(self):
        """The ticket blocks this, but the ticket is a client. An endpoint that
        trusts its own UI to have validated the request has no validation."""
        self.load(self.flat(10), symbol=PERP)
        with self.assertRaises(manual.IntentRejected) as ctx:
            manual.create_intent(self.con, PERP, "1H", "LONG", entry=100,
                                 tp=130, sl=85, created_at=0, leverage=10)
        self.assertIn("liquidat", str(ctx.exception).lower())
        self.assertEqual(
            store.get_facts(self.con, PERP, "1H", manual.INTENT_KIND,
                            manual.MANUAL_VERSION), [])
        # the identical stop is fine with less leverage — liquidation moves away
        ok = manual.create_intent(self.con, PERP, "1H", "LONG", entry=100,
                                  tp=130, sl=85, created_at=0, leverage=2)
        self.assertEqual(Decimal(ok["liquidation"]), Decimal("50.500"))

    def test_leverage_cannot_exceed_the_venue_maximum(self):
        self.load(self.flat(10), symbol=PERP)
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, PERP, "1H", "LONG", entry=100,
                                 tp=104, sl=98, created_at=0, leverage=50)

    def test_spot_is_pinned_to_1x(self):
        """Not a policy choice — a spot position is not financed, so there is
        no leverage to set and no liquidation to price."""
        self.load(self.flat(10))
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100,
                                 tp=104, sl=98, created_at=0, leverage=5)
        ok = manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100,
                                  tp=104, sl=98, created_at=0, leverage=1)
        self.assertIsNone(ok["liquidation"])

    # ---------- discovery and live status: the never-resolves fix ----------

    def test_unresolved_finds_work_wherever_it_lives(self):
        """The live loop resolves manual intents by asking WHERE they are, not
        by assuming they sit inside the scan universe. Before this, an intent
        on an unscanned symbol was checked once at arm time and then sat ARMED
        forever — a trade the operator placed and could never see settle."""
        self.load(self.flat(3))                       # not enough bars to resolve
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.assertIn((SPOT, "1H"), manual.unresolved(self.con))
        # settle it, and the work list must empty
        for i, (o, h, l, c) in enumerate(
                [(100, 104, 99, 103)] + self.flat(5), start=3):
            self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (SPOT, "1H", i * TF, str(o), str(h), str(l), str(c),
                              "1", "test", i * TF))
        self.con.commit()
        self.run_engine()
        self.assertNotIn((SPOT, "1H"), manual.unresolved(self.con))

    def test_status_reports_pending_then_open_with_unrealized(self):
        # bar 0 closes flat; entry untouched -> PENDING
        self.load([(120, 121, 119, 120)])
        # tp sits ABOVE every fixture high: the old status() never tested
        # exits, and its fixture had already struck TP intra-window while
        # being reported OPEN. The shared walk exposed that.
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=130, sl=95, created_at=0)
        st = manual.status(self.con, SPOT, "1H", TF)
        self.assertEqual(st[0]["state"], "PENDING")
        # a bar touches entry, next closes at 102.5 -> OPEN, +0.5R on a 5-wide stop
        for i, bar in enumerate([(120, 121, 99, 101), (101, 103, 100, "102.5")],
                                start=1):
            o, h, l, c = bar
            self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (SPOT, "1H", i * TF, str(o), str(h), str(l), str(c),
                              "1", "test", i * TF))
        self.con.commit()
        st = manual.status(self.con, SPOT, "1H", TF)
        self.assertEqual(st[0]["state"], "OPEN")
        self.assertEqual(st[0]["unrealized_r"], "0.50")

    def test_status_marks_to_the_last_closed_bar_not_a_live_tick(self):
        """The unrealized figure must come from the same price authority as
        every other number on screen — the last CLOSED candle."""
        self.load([(120, 121, 99, 101), (101, 108, 100, 106)])
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=125, sl=96, created_at=0)
        st = manual.status(self.con, SPOT, "1H", TF)
        # (106 - 100) / 4 = 1.5R — the close, not the 108 high
        self.assertEqual(st[0]["unrealized_r"], "1.50")

    # ---------- trailing: the operator's exit rule, honestly simulated ------

    def trail_intent(self, symbol=SPOT, **kw):
        args = dict(entry=100, tp=120, sl=98, created_at=0, risk_usd=200,
                    trail_r=1.0)
        args.update(kw)
        return manual.create_intent(self.con, symbol, "1H", "LONG", **args)

    def test_trailing_stop_locks_in_profit(self):
        """Risk is 2, trail is 1R: at a best of 110 the stop sits at 108, and
        the pullback through it settles as TRAIL_STOP at +4R gross."""
        self.load([(105, 106, 99.5, 105),      # fills at 100, ratchets to 104
                   (105, 110, 104.5, 109),     # best 110 -> stop 108
                   (109, 109.5, 107, 107.5)])  # 107 <= 108: trailed out
        self.trail_intent()
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TRAIL_STOP")
        self.assertEqual(row["exit_price"], "108.0")
        self.assertEqual(row["r_gross"], "4.00")
        self.assertEqual(row["exit_rule"], "TRAIL")
        self.assertLess(Decimal(row["r_multiple"]), Decimal(row["r_gross"]),
                        "a trailed stop is a market exit and pays for it")

    def test_the_ratchet_cannot_act_on_its_own_bar(self):
        """A bar that makes the new high AND falls through the stop that high
        implies must NOT exit on it — OHLC cannot say which came first. The
        ratchet arms for the NEXT bar, conservative by exactly one bar."""
        self.load([(100, 100.5, 99.5, 100),    # fill, no progress
                   (100, 110, 107, 108),       # high 110 -> stop 108; low 107 IGNORED
                   (108, 108.5, 107.5, 108)])  # exits HERE at 108
        self.trail_intent()
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TRAIL_STOP")
        self.assertEqual(row["bars_held"], 2, "the exit must land on bar 2, "
                         "not the bar whose own high armed the stop")

    def test_the_trail_never_loosens(self):
        """An adverse bar moves nothing: the stop only ratchets toward price."""
        self.load([(100, 100, 99.5, 100),      # fill; high == entry, no progress
                   (99, 99.5, 98.5, 99)])      # adverse; 98.5 > 98 survives
        self.trail_intent()
        r = self.run_engine()
        self.assertEqual(r["OPEN"], 1)
        st = manual.status(self.con, SPOT, "1H", TF)
        self.assertEqual(st[0]["state"], "OPEN")
        self.assertEqual(Decimal(st[0]["current_stop"]), Decimal(98),
                         "adverse movement must not move the stop")
        self.assertFalse(st[0]["trailed"])

    def test_status_reports_the_ratcheted_stop_for_the_chart(self):
        """The gold SL line draws `current_stop` — showing the original stop on
        a trailed trade would misstate where the trade dies."""
        self.load([(100, 100.5, 99.5, 100),
                   (100, 110, 104.5, 109)])    # best 110 -> stop 108, no exit yet
        self.trail_intent()
        st = manual.status(self.con, SPOT, "1H", TF)
        self.assertEqual(st[0]["state"], "OPEN")
        self.assertEqual(Decimal(st[0]["current_stop"]), Decimal(108))
        self.assertTrue(st[0]["trailed"])

    def test_a_hair_trigger_trail_is_refused(self):
        with self.assertRaises(manual.IntentRejected):
            self.trail_intent(trail_r=0.05)

    def test_without_trailing_nothing_changed(self):
        """trail_r=None must resolve byte-identically to the pre-trailing
        resolver — that equivalence is why MANUAL_VERSION did not bump."""
        self.load([(100, 100.5, 99.5, 100),
                   (100, 110, 104.5, 109),     # would have trailed to 108...
                   (109, 109.5, 107, 107.5),   # ...and exited here if trailing
                   (107, 121, 106, 120)])      # instead rides to TP
        self.trail_intent(trail_r=None)
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TP")
        self.assertEqual(row["exit_rule"], "HOLD")

    def test_book_counts_a_profitable_trail_as_a_win(self):
        self.load([(105, 106, 99.5, 105),
                   (105, 110, 104.5, 109),
                   (109, 109.5, 107, 107.5)])
        self.trail_intent()
        self.run_engine()
        b = manual.book(self.con)
        self.assertEqual(b["n"], 1)
        self.assertEqual(b["wins"], 1, "TRAIL_STOP at +4R gross is a win")

    # ---------- operator override of an ENGINE position ----------

    def test_closing_an_engine_position_never_touches_the_strategy_record(self):
        """The override is the whole design: the engine's simulation of this
        setup must carry on and still record what holding produced, or the
        comparison the override exists to enable does not exist."""
        self.load([(100, 101, 99, 100), (100, 106, 99, 105)])
        out = manual.close_engine_position(
            self.con, "SID|4H|X", SPOT, "1H", "LONG",
            entry=100, sl=98, risk_usd=200)
        self.assertTrue(out["written"])
        # priced at the last CLOSED bar: (105-100)/2 = 2.5R
        self.assertEqual(out["r_at_close"], "2.50")
        self.assertEqual(out["usd_at_close"], "500.00")
        self.assertEqual(out["exit_price"], "105")
        self.assertTrue(out["not_the_strategy_record"])
        # nothing written under any strategy version or kind
        for kind in ("exec", "order", "setup"):
            self.assertEqual(
                store.get_facts(self.con, SPOT, "1H", kind,
                                execsim.EXEC_VERSION), [],
                f"an override reached {kind}/{execsim.EXEC_VERSION}")
        self.assertIn("SID|4H|X", manual.overridden_setups(self.con))

    def test_a_short_override_prices_the_right_direction(self):
        self.load([(100, 101, 99, 100), (100, 101, 94, 95)], symbol=PERP)
        out = manual.close_engine_position(
            self.con, "S2", PERP, "1H", "SHORT", entry=100, sl=102)
        self.assertEqual(out["r_at_close"], "2.50")   # (100-95)/2

    def test_a_market_close_pays_slippage_like_every_other_market_exit(self):
        """execsim charges its market exits fee AND slippage. The first cut of
        the override charged the fee alone, which priced operator closes better
        than engine stops and would have biased the operator-vs-rule comparison
        this feature exists to enable — flatteringly, and invisibly."""
        # 20 flat-range bars so ATR is defined, then a close at 105
        self.load([(100, 102, 98, 100)] * 20 + [(100, 106, 99, 105)])
        out = manual.close_engine_position(
            self.con, "SLIP", SPOT, "1H", "LONG", entry=100, sl=98)
        self.assertEqual(out["order_type"], "MARKET")
        self.assertGreater(Decimal(out["slippage_price_units"]), 0)
        # effective exit is WORSE than the quoted close for a long
        self.assertLess(Decimal(out["effective_exit_price"]),
                        Decimal(out["exit_price"]))
        self.assertLess(Decimal(out["r_at_close"]), Decimal("2.50"))

    def test_an_override_without_candles_is_refused_not_guessed(self):
        with self.assertRaises(manual.IntentRejected):
            manual.close_engine_position(self.con, "S3", SPOT, "1H", "LONG",
                                         entry=100, sl=98)

    # ---------- adopting an engine position ----------

    def test_an_adopted_position_holds_instead_of_hunting_for_a_fill(self):
        """The entry already happened. Searching for a limit fill would be
        wrong twice: the price is recorded, and a failed search would mark a
        live position as never entered."""
        # fill on bar 1; entry 100 is never touched again afterwards
        self.load([(100, 101, 99, 100), (100, 100.5, 99.5, 100),
                   (90, 91, 89, 90), (90, 91, 84, 85)])
        manual.adopt_position(self.con, "ENG|1", SPOT, "1H", "LONG",
                              entry=100, sl=86, tp=130,
                              fill_ts=1 * TF, adopted_at=2 * TF, risk_usd=140)
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "SL")       # held, then stopped at 86
        self.assertEqual(row["exit_price"], "86")

    def test_adoption_moves_the_position_off_the_engine_book(self):
        self.load(self.flat(3))
        manual.adopt_position(self.con, "ENG|2", SPOT, "1H", "LONG",
                              entry=100, sl=95, tp=120,
                              fill_ts=0, adopted_at=TF)
        ov = manual.overridden_setups(self.con)
        self.assertIn("ENG|2", ov)
        self.assertEqual(ov["ENG|2"]["event"], "ADOPTED")
        self.assertTrue(ov["ENG|2"]["not_the_strategy_record"])
        # and the strategy record itself is still untouched
        for kind in ("setup", "exec", "order"):
            self.assertEqual(store.get_facts(self.con, SPOT, "1H", kind,
                                             execsim.EXEC_VERSION), [])

    def test_an_adopted_position_can_trail(self):
        """Custody means the operator's exit rules apply, trailing included."""
        self.load([(100, 100.5, 99.5, 100),      # fill bar
                   (100, 110, 99.5, 109),        # best 110 -> stop 108 next bar
                   (109, 109.5, 107, 107.5)])    # trailed out
        manual.adopt_position(self.con, "ENG|3", SPOT, "1H", "LONG",
                              entry=100, sl=98, tp=200,
                              fill_ts=0, adopted_at=0, trail_r=1.0)
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TRAIL_STOP")
        self.assertEqual(row["exit_price"], "108.0")

    def test_adoption_refuses_a_stop_on_the_wrong_side(self):
        self.load(self.flat(3))
        with self.assertRaises(manual.IntentRejected):
            manual.adopt_position(self.con, "ENG|4", SPOT, "1H", "LONG",
                                  entry=100, sl=105, tp=120,
                                  fill_ts=0, adopted_at=TF)

    # ---------- the book ----------

    def test_book_reports_only_manual_trades(self):
        bars = self.flat(6) + [(100, 104, 99, 103)] + self.flat(5)
        self.load(bars)
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        b = manual.book(self.con)
        self.assertEqual(b["version"], manual.MANUAL_VERSION)
        self.assertEqual(b["n"], 1)
        self.assertEqual(b["wins"], 1)
        self.assertEqual(len(b["curve"]), 1)
        self.assertTrue(all(t["source"] == "OPERATOR" for t in b["trades"]))


if __name__ == "__main__":
    unittest.main()
