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
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from engine import manual, store, execsim, setups

TF = 3600
SPOT = "BTC-USD"        # coinbase-spot — cannot short
PERP = "BTCUSDT"        # phemex-perp   — can short
PERP2 = "ETHUSDT"       # a second perp, for tests that need two live orders at once


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
        # Two perps carrying IDENTICAL candles, because one chart may now hold
        # only one unresolved order per side — the double-arm guard. The
        # invariant is unchanged and if anything stated more strongly: same
        # prices, same bars, different leverage, one outcome.
        self.load(bars, symbol=PERP)
        self.load(bars, symbol=PERP2)
        a = manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                                 sl=98, created_at=0, risk_usd=200, leverage=1)
        b = manual.create_intent(self.con, PERP2, "1H", "LONG", entry=100, tp=104,
                                 sl=98, created_at=0, risk_usd=200, leverage=10)
        self.assertEqual(a["size_units"], b["size_units"], "size must not move")
        # margin is what moves: notional / leverage
        self.assertEqual(Decimal(a["margin_usd"]) / 10, Decimal(b["margin_usd"]))
        self.assertIsNone(a["liquidation"], "1x cannot be liquidated by price")
        self.assertEqual(Decimal(b["liquidation"]), Decimal("90.500"))
        self.run_engine(symbol=PERP)
        self.run_engine(symbol=PERP2)
        rs = {r["intent_id"]: r
              for r in self.execs(symbol=PERP) + self.execs(symbol=PERP2)}
        self.assertEqual(len(rs), 2)
        vals = {r["r_multiple"] for r in rs.values()}
        self.assertEqual(len(vals), 1,
                         f"leverage changed the outcome: {vals}")

    def test_arming_the_same_side_twice_is_refused(self):
        """The ticket stayed on "New trade" with Arm live after an order was
        already resting, so a double-click armed the same trade twice. Both
        fill on the same touch and the book carries double the risk the budget
        was told about.
        """
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        with self.assertRaises(manual.IntentRejected) as cm:
            manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                                 sl=98, created_at=TF, risk_usd=200)
        self.assertIn("already have an unresolved LONG", str(cm.exception))

    def test_the_guard_is_on_the_SIDE_not_the_prices(self):
        """Two shorts at different entries is the same mistake wearing a
        different number. A rule that only caught identical levels would miss
        every case worth catching."""
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "SHORT", entry=100, tp=96,
                             sl=102, created_at=0, risk_usd=200)
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, PERP, "1H", "SHORT", entry=101,
                                 tp=95, sl=103, created_at=TF, risk_usd=200)

    def test_the_opposite_side_is_left_alone(self):
        """A hedge is a different argument. Refusing it here would be this
        function inventing a position policy it was never asked for."""
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        manual.create_intent(self.con, PERP, "1H", "SHORT", entry=100, tp=96,
                             sl=102, created_at=TF, risk_usd=200)

    # ---------- the refusal and the book must agree ----------
    #
    # The operator's report: "i do remember getting an error when trying to
    # place the trade saying i already had one waiting or something but it
    # still shows as a pending order." An error surfaced and an order exists,
    # and on the surface where money is committed those two readings cannot be
    # left to be reconciled by guesswork. Either the refusal is real and the
    # pen is empty, or the request landed and it is a receipt. Nothing between.

    def _rows(self):
        """Every fact and every manifest — the whole of what a write is."""
        return (self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
                self.con.execute("SELECT COUNT(*) FROM manifests").fetchone()[0])

    def test_a_refused_arm_writes_nothing_at_all(self):
        """Not "no second intent" — NOTHING. The guard sits ahead of the cost
        manifest as well as the fact, and a refusal that still left a row
        behind would be the same defect one table over."""
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        before = self._rows()
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, PERP, "1H", "LONG", entry=101,
                                 tp=105, sl=99, created_at=TF, risk_usd=200)
        self.assertEqual(self._rows(), before,
                         "a refused arm wrote something")

    def test_the_refusal_names_the_order_that_blocked_it(self):
        """"You already have one waiting" is not findable. The operator has to
        be able to walk to the row it means, so it carries the market, the
        timeframe, the entry, the stop and the moment it was armed — and leads
        with the fact that this attempt was not recorded."""
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "SHORT", entry=100, tp=96,
                             sl=102, created_at=0, risk_usd=200)
        with self.assertRaises(manual.IntentRejected) as cm:
            manual.create_intent(self.con, PERP, "1H", "SHORT", entry=101,
                                 tp=95, sl=103, created_at=TF, risk_usd=200)
        msg = str(cm.exception)
        self.assertIn("nothing was armed", msg)
        for token in (PERP, "1H", "100", "102"):          # symbol, tf, entry, stop
            self.assertIn(token, msg, f"the refusal does not name {token}")

    def test_the_same_order_arriving_twice_is_a_receipt_not_a_refusal(self):
        """THE REPORTED BUG. `created_at` is chosen by the caller so a retry
        rebuilds the same intent_id and the same plan — the whole point of
        letting a phone name the moment. The same-side guard sat in front of
        that and refused, so a request that had already succeeded came back as
        an error while its order rested on the book."""
        self.load(self.flat(6), symbol=PERP)
        kw = dict(entry=100, tp=104, sl=98, created_at=0, risk_usd=200)
        first = manual.create_intent(self.con, PERP, "1H", "LONG", **kw)
        self.assertFalse(first["already_armed"])
        self.assertTrue(first["written"])
        before = self._rows()
        again = manual.create_intent(self.con, PERP, "1H", "LONG", **kw)
        self.assertTrue(again["already_armed"], "a retry was not recognised")
        self.assertFalse(again["written"], "a retry wrote a second intent")
        self.assertEqual(again["intent_id"], first["intent_id"])
        self.assertEqual(self._rows(), before, "a retry wrote something")

    def test_the_receipt_is_the_recorded_plan_not_the_second_request(self):
        """A retry is answered with what the book HOLDS. Anything else and the
        ticket would read back a number that was never armed."""
        self.load(self.flat(6), symbol=PERP)
        kw = dict(entry=100, tp=104, sl=98, created_at=0, risk_usd=200)
        manual.create_intent(self.con, PERP, "1H", "LONG", note="first", **kw)
        again = manual.create_intent(self.con, PERP, "1H", "LONG",
                                     note="typed something else", **kw)
        self.assertEqual(again["note"], "first")

    def test_a_changed_plan_is_not_the_same_order(self):
        """Same second, different levels — a nudge between two taps. That is
        not the order on the book and must not be reported as it."""
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        before = self._rows()
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, PERP, "1H", "LONG", entry=100.5,
                                 tp=104, sl=98, created_at=0, risk_usd=200)
        self.assertEqual(self._rows(), before)

    def test_a_settled_order_id_is_not_answered_as_still_armed(self):
        """The receipt is only a receipt while the order is still on the book.
        Repeating an id whose trade has closed cannot be written — the id is
        spent — and must not be answered "already armed" either, which would
        point the operator at a position that no longer exists."""
        bars = self.flat(2) + [(100, 105, 99, 104)] + self.flat(3)
        self.load(bars, symbol=PERP)
        kw = dict(entry=100, tp=104, sl=98, created_at=0, risk_usd=200)
        manual.create_intent(self.con, PERP, "1H", "LONG", **kw)
        self.run_engine(symbol=PERP)
        self.assertTrue(self.execs(symbol=PERP), "fixture did not settle")
        before = self._rows()
        with self.assertRaises(manual.IntentRejected) as cm:
            manual.create_intent(self.con, PERP, "1H", "LONG", **kw)
        self.assertIn("has since settled", str(cm.exception))
        self.assertEqual(self._rows(), before)

    def test_two_plans_cannot_share_one_order_id(self):
        """A LONG and a SHORT armed on one chart within the same second is a
        legitimate hedge that the same-side guard does not look at — and they
        carry the same `symbol|tf|MANUAL|created_at`. Both used to be written.
        `unresolved` keys its work list on intent_id and `run` keys its
        done-set on it, so one of the two would be dropped by whichever read
        last: armed, unresolvable, invisible on every surface, and liable to be
        marked settled by the other one's exit."""
        self.load(self.flat(6), symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        before = self._rows()
        with self.assertRaises(manual.IntentRejected) as cm:
            manual.create_intent(self.con, PERP, "1H", "SHORT", entry=100,
                                 tp=96, sl=102, created_at=0, risk_usd=200)
        self.assertIn("nothing was armed", str(cm.exception))
        self.assertEqual(self._rows(), before)
        ids = [p["intent_id"]
               for plans in manual.unresolved(self.con).values() for p in plans]
        self.assertEqual(len(ids), len(set(ids)), "two intents share one id")

    def test_a_resolved_order_stops_blocking_the_next_one(self):
        """The guard reads UNRESOLVED intents. Once a trade settles, the same
        side must be armable again or the chart is permanently spent."""
        bars = self.flat(2) + [(100, 105, 99, 104)] + self.flat(3)
        self.load(bars, symbol=PERP)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        self.run_engine(symbol=PERP)
        self.assertTrue(self.execs(symbol=PERP), "fixture did not settle")
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=TF * 5, risk_usd=200)

    def test_another_timeframe_on_the_same_symbol_is_its_own_chart(self):
        self.load(self.flat(6), symbol=PERP)
        self.load(self.flat(6), symbol=PERP, tf="4H")
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)
        manual.create_intent(self.con, PERP, "4H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0, risk_usd=200)

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

    # ---------- partial exits: the blend, pinned to hand arithmetic ----------
    #
    # Every expected figure below is computed IN THE COMMENT from the fixture's
    # own prices and the venue's own published rates, the way test_one_walk.py
    # pins execsim: a number this file can point at, not one it read back from
    # the engine and enshrined. SPOT is used deliberately — coinbase-spot pays
    # no funding, so each leg's cost is two fee terms and nothing else, and an
    # arithmetic error cannot hide inside a funding accrual.
    #
    # coinbase-spot: maker 0.0040, taker 0.0060, slippage 0.05 ATR.

    def scale_bars(self):
        """Fill at 100, rung at 104 on bar 1, target 110 on bar 2."""
        return [(100, 100.5, 99.5, 100),      # fills at 100
                (100, 104.5, 99.8, 104),      # covers 104 — the rung fills
                (104, 110.5, 103, 110)]       # covers 110 — the remainder TPs

    def test_half_off_at_a_level_blends_two_settlements(self):
        """The headline case: half off at +2R, the rest rides to the target.

        Hand arithmetic, risk = 100 - 98 = 2:

          rung  50% at 104, a LIMIT order -> maker both ends, no slippage
                gross  (104 - 100) / 2                        = 2.0000 R
                fees   0.0040*100 + 0.0040*104 = 0.4 + 0.416   = 0.816
                net    (4 - 0.816) / 2                         = 1.5920 R
          rest  50% at 110, the target -> maker both ends
                gross  (110 - 100) / 2                        = 5.0000 R
                fees   0.0040*100 + 0.0040*110 = 0.4 + 0.44    = 0.840
                net    (10 - 0.840) / 2                        = 4.5800 R

          blended net    0.5*1.5920 + 0.5*4.5800 = 3.086 -> 3.09
          blended gross  0.5*2      + 0.5*5      = 3.50
        """
        self.load(self.scale_bars())
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0, risk_usd=200,
                             partials=[{"fraction": "0.5", "price": "104"}])
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TP", "the REMAINDER's exit rule names "
                         "the trade — a scale-out is not an outcome")
        self.assertEqual(row["r_multiple"], "3.09")
        self.assertEqual(row["r_gross"], "3.50")
        self.assertTrue(row["scaled_out"])
        self.assertEqual(row["n_partials"], 1)
        legs = row["legs"]
        self.assertEqual([l["kind"] for l in legs], ["PARTIAL", "REMAINDER"])
        self.assertEqual([l["fraction"] for l in legs], ["0.5", "0.5"])
        self.assertEqual(Decimal(legs[0]["r_net"]), Decimal("1.592"))
        self.assertEqual(Decimal(legs[1]["r_net"]), Decimal("4.58"))
        self.assertEqual(Decimal(legs[0]["fees_price_units"]), Decimal("0.816"))
        self.assertEqual(Decimal(legs[1]["fees_price_units"]), Decimal("0.840"))

    def test_the_blend_is_reproducible_from_the_recorded_legs_alone(self):
        """The house rule, as a property rather than a promise.

        `blend_r` is the function `run` used to produce `r_multiple`; feeding
        it the legs the fact carries must return the figure the fact carries.
        If these ever disagree, the settled number stopped being derivable from
        the record and became something only the engine could vouch for — the
        exact drift test_one_walk.py was written after paying for twice.
        """
        self.load(self.scale_bars())
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0, risk_usd=200,
                             partials=[{"fraction": "0.25", "price": "102"},
                                       {"fraction": "0.25", "price": "104"}])
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(str(manual.blend_r(row["legs"], "r_net")),
                         row["r_multiple"], "the recorded legs do not reproduce "
                         "the recorded result")
        self.assertEqual(str(manual.blend_r(row["legs"], "r_gross")),
                         row["r_gross"])
        # ...and the weights are a whole position, no more and no less
        self.assertEqual(sum(Decimal(l["fraction"]) for l in row["legs"]),
                         Decimal(1))

    def test_every_settled_trade_in_the_book_reproduces_its_own_headline(self):
        """The same property, swept over a book of mixed shapes.

        One passing example is a passing example; the claim is that it holds
        for every settlement this engine writes — scaled and unscaled, target
        and stop, spot and perp. Anything that starts computing `r_multiple`
        by a second route shows up here rather than in a report months later.
        """
        cases = [
            # (symbol, bars, kwargs) — TP scaled, TP held, SL, and a trail
            (SPOT, self.scale_bars(),
             dict(tp=110, partials=[{"fraction": "0.5", "price": "104"}])),
            (PERP, self.scale_bars(), dict(tp=110)),
            (PERP2, [(100, 100.5, 99.5, 100), (100, 104.5, 97, 98)],
             dict(tp=110, partials=[{"fraction": "0.4", "price": "102"}])),
            ("SOLUSDT", [(100, 100.5, 99.5, 100), (100, 110, 99.8, 109),
                         (109, 109.5, 103, 104)],
             dict(tp=200, trail_r=1.0,
                  partials=[{"fraction": "0.3", "price": "104"}])),
        ]
        for symbol, bars, kw in cases:
            self.load(bars, symbol=symbol)
            manual.create_intent(self.con, symbol, "1H", "LONG", entry=100,
                                 sl=98, created_at=0, **kw)
            self.run_engine(symbol=symbol)
        settled = manual.book(self.con)["trades"]
        self.assertEqual(len(settled), len(cases), "fixture did not settle")
        # The sweep is only worth running if it sweeps. These four fixtures
        # settle as SL, TP scaled, TP held and TRAIL_STOP scaled — assert that,
        # so the day one of them degenerates the test says so instead of
        # passing four times over the same trade.
        self.assertEqual({r["outcome"] for r in settled},
                         {"SL", "TP", "TRAIL_STOP"})
        self.assertEqual(sorted(len(r["legs"]) for r in settled), [1, 1, 2, 2])
        for row in settled:
            with self.subTest(intent=row["intent_id"], outcome=row["outcome"]):
                self.assertEqual(str(manual.blend_r(row["legs"], "r_net")),
                                 row["r_multiple"])
                self.assertEqual(str(manual.blend_r(row["legs"], "r_gross")),
                                 row["r_gross"])
                self.assertEqual(sum(Decimal(l["fraction"]) for l in row["legs"]),
                                 Decimal(1), "the legs are not a whole position")
                # exactly one leg settles by a terminal rule, always the last
                self.assertEqual([l["kind"] for l in row["legs"]].count("REMAINDER"), 1)
                self.assertEqual(row["legs"][-1]["outcome"], row["outcome"])

    def test_scaling_out_costs_R_when_the_trade_runs(self):
        """The comparison this feature exists to make possible, on one fixture.

        Identical bars, identical bracket, one with a rung at +2R and one
        without. Taking half off at 104 blends 3.09R where holding settles
        4.58R. That is not an argument against scaling out — it is the number
        that has to be recorded for the argument to ever be settled, the same
        way the trailing rule has to be gradable against holding.
        """
        bars = self.scale_bars()
        self.load(bars, symbol=PERP)
        self.load(bars, symbol=PERP2)
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0,
                             partials=[{"fraction": "0.5", "price": "104"}])
        manual.create_intent(self.con, PERP2, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0)
        self.run_engine(symbol=PERP)
        self.run_engine(symbol=PERP2)
        scaled = self.execs(symbol=PERP)[0]
        held = self.execs(symbol=PERP2)[0]
        self.assertEqual(scaled["outcome"], held["outcome"], "same fixture")
        self.assertLess(Decimal(scaled["r_multiple"]), Decimal(held["r_multiple"]))
        self.assertFalse(held["scaled_out"])

    def test_a_stop_bar_takes_the_whole_remainder_and_fills_no_rung(self):
        """STOP_FIRST, extended to the ladder, and the flattering reading refused.

        Bar 1 covers BOTH the rung at 104 and the stop at 98. OHLC cannot say
        which came first, and the house rule for that ambiguity is already
        written down. Booking the scale-out anyway would hand the operator a
        profit banked moments before the loss — plausible, flattering, and
        unprovable, which is the whole class of error this book is built to
        avoid.
        """
        self.load([(100, 100.5, 99.5, 100),
                   (100, 105, 97, 98)])        # covers the rung AND the stop
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0,
                             partials=[{"fraction": "0.5", "price": "104"}])
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "SL")
        self.assertFalse(row["scaled_out"], "a rung filled on the stop's own bar")
        self.assertEqual([l["fraction"] for l in row["legs"]], ["1"],
                         "the stop takes the whole position")
        self.assertTrue(row["ambiguous_bar"],
                        "a bar that reached both must be flagged, as a "
                        "stop/target bar always was")

    def test_a_rung_price_never_reached_leaves_one_leg(self):
        """A plan is not an event. The trade goes the other way and stops out
        without ever reaching 104, so the whole position settles at the stop —
        but the ladder stays on the record, because an unfilled rung is a
        decision that was made and its absence from `legs` must not read as if
        it was never intended."""
        self.load([(100, 100.5, 99.5, 100),
                   (100, 101, 97, 98)])        # nowhere near the rung at 104
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0,
                             partials=[{"fraction": "0.5", "price": "104"}])
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "SL")
        self.assertFalse(row["scaled_out"])
        self.assertEqual(len(row["legs"]), 1)
        self.assertFalse(row["ambiguous_bar"], "the bar reached only the stop")
        self.assertEqual(row["partials_planned"],
                         [{"fraction": "0.5", "price": "104"}],
                         "the rung that never filled must still be on the record")

    def test_a_bar_that_reaches_the_target_fills_the_rung_on_its_way(self):
        """Price cannot arrive at 110 without passing 104. Settling only the
        target would book the WHOLE position at the best price of the trade —
        flattering, and not what the plan said would happen."""
        self.load([(100, 100.5, 99.5, 100),
                   (100, 110.5, 99.8, 110)])   # one bar covering rung and target
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0,
                             partials=[{"fraction": "0.5", "price": "104"}])
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["outcome"], "TP")
        self.assertTrue(row["scaled_out"], "the rung the bar covered was skipped")
        self.assertEqual([l["exit_price"] for l in row["legs"]], ["104", "110"])

    def test_a_trade_with_no_ladder_settles_exactly_as_it_did_before(self):
        """The migration's load-bearing claim, asserted rather than trusted.

        One leg of fraction 1 must blend to that leg's own quotient, so every
        v0.1 intent settles to the figure the pre-partials resolver would have
        written. Hand arithmetic, risk 2, target 104, maker both ends:
            fees  0.0040*100 + 0.0040*104 = 0.816
            net   (4 - 0.816) / 2         = 1.592 -> 1.59
        """
        self.load(self.flat(2) + [(100, 104.5, 99, 104)])
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=104,
                             sl=98, created_at=0)
        self.run_engine()
        row = self.execs()[0]
        self.assertEqual(row["r_multiple"], "1.59")
        self.assertEqual(row["r_gross"], "2.00")
        self.assertEqual(len(row["legs"]), 1)
        self.assertEqual(row["legs"][0]["fraction"], "1")
        self.assertEqual(row["legs"][0]["kind"], "REMAINDER")
        # the top-line costs still describe the whole position, unweighted by
        # anything, because there is only one leg to weigh
        self.assertEqual(Decimal(row["fees_price_units"]), Decimal("0.816"))

    def test_each_leg_pays_funding_for_its_own_holding_period(self):
        """A rung taken at bar 1 did not hold the position to bar 2.

        Charging the trade's full holding period on size that was closed early
        is a cost the operator never carried — the mirror image of the S45
        defect where funding was defined and never charged at all.
        """
        self.load(self.scale_bars(), symbol=PERP)     # phemex-perp: funding is real
        manual.create_intent(self.con, PERP, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0,
                             partials=[{"fraction": "0.5", "price": "104"}])
        self.run_engine(symbol=PERP)
        rung, rest = self.execs(symbol=PERP)[0]["legs"]
        self.assertEqual(rung["bars_held"], 1)
        self.assertEqual(rest["bars_held"], 2)
        self.assertGreater(Decimal(rung["funding_price_units"]), 0,
                           "a perp leg held a bar pays funding for it")
        self.assertLess(Decimal(rung["funding_price_units"]),
                        Decimal(rest["funding_price_units"]),
                        "the leg closed first must pay less to hold")

    def test_rungs_fill_in_the_order_price_reaches_them(self):
        self.load([(100, 100.5, 99.5, 100),
                   (100, 102.5, 99.8, 102),    # covers 102 only
                   (102, 106, 101, 105)])      # covers 104
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=110,
                             sl=98, created_at=0,
                             partials=[{"fraction": "0.2", "price": "104"},
                                       {"fraction": "0.3", "price": "102"}])
        st = manual.status(self.con, SPOT, "1H", TF)
        self.assertEqual([f["price"] for f in st[0]["partials_filled"]],
                         ["102", "104"], "the nearer rung must fill first")

    def test_a_rung_outside_the_bracket_is_refused_before_anything_is_written(self):
        """Outside the stop and target it is not a scale-out, it is an
        instruction that can never run — the trade settles at one end or the
        other before price gets there."""
        self.load(self.flat(4))
        for price in (112, 97, 110, 98):     # beyond tp, beyond sl, AT each
            with self.subTest(price=price):
                with self.assertRaises(manual.IntentRejected):
                    manual.create_intent(
                        self.con, SPOT, "1H", "LONG", entry=100, tp=110, sl=98,
                        created_at=0,
                        partials=[{"fraction": "0.5", "price": str(price)}])
        self.assertEqual(
            store.get_facts(self.con, SPOT, "1H", manual.INTENT_KIND,
                            manual.MANUAL_VERSION), [])

    def test_a_rung_below_the_entry_is_allowed(self):
        """De-risking is a real thing traders do and the R arithmetic is
        identical. Refusing it would be this book inventing a position policy
        it was never asked for — the same mistake `validate_position` exists to
        undo for profit-side stops."""
        self.load(self.flat(4))
        out = manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100,
                                   tp=110, sl=98, created_at=0,
                                   partials=[{"fraction": "0.5", "price": "99"}])
        self.assertEqual(out["partials"], [{"fraction": "0.5", "price": "99"}])

    def test_a_ladder_that_closes_the_whole_position_is_refused(self):
        """A trade whose last rung closes it has no terminal exit rule to
        record — nothing to grade TRAIL against HOLD with, and a last rung that
        is a target under another name. The refusal says so, and says what to
        do instead."""
        self.load(self.flat(4))
        with self.assertRaises(manual.IntentRejected) as cm:
            manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100,
                                 tp=110, sl=98, created_at=0,
                                 partials=[{"fraction": "0.5", "price": "102"},
                                           {"fraction": "0.5", "price": "104"}])
        self.assertIn("TARGET", str(cm.exception))

    def test_a_dust_sized_rung_is_refused(self):
        self.load(self.flat(4))
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100,
                                 tp=110, sl=98, created_at=0,
                                 partials=[{"fraction": "0.0001", "price": "104"}])

    def test_more_rungs_than_the_cap_is_refused(self):
        self.load(self.flat(4))
        with self.assertRaises(manual.IntentRejected):
            manual.create_intent(
                self.con, SPOT, "1H", "LONG", entry=100, tp=110, sl=98,
                created_at=0,
                partials=[{"fraction": "0.1", "price": str(101 + i)}
                          for i in range(manual.MAX_PARTIALS + 1)])

    def test_status_reports_a_partly_closed_position_as_partly_closed(self):
        """The panel bug this closes: a position with half taken off rendered
        as fully open, so the operator read the whole size as still at risk.

        Marks, before costs, exactly as `unrealized_r` always has been:
          rung     50% banked at 104 -> 0.5 * (4/2)     = +1.00 R
          open     50% at the last close 106 -> (6/2)   = +3.00 R per unit
          blended  1.00 + 0.5 * 3.00                    = +2.50 R
        """
        self.load([(100, 100.5, 99.5, 100),
                   (100, 104.5, 99.8, 104),
                   (104, 107, 103, 106)])
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=120,
                             sl=98, created_at=0, risk_usd=200,
                             partials=[{"fraction": "0.5", "price": "104"}])
        st = manual.status(self.con, SPOT, "1H", TF)[0]
        self.assertEqual(st["state"], "OPEN")
        self.assertEqual(st["closed_fraction"], "0.5")
        self.assertEqual(st["open_fraction"], "0.5")
        self.assertEqual(st["realized_r"], "1.00")
        self.assertEqual(st["unrealized_r"], "3.00", "per unit of what is STILL on")
        self.assertEqual(st["blended_r"], "2.50")
        # the dollars follow the blend, not the open half alone
        self.assertEqual(st["unrealized_usd"], "500.00")
        self.assertEqual(st["partials_filled"],
                         [{"price": "104", "fraction": "0.5", "r_gross": "2.00"}])

    def test_an_untouched_position_reports_the_same_numbers_it_always_did(self):
        """The new fields must not move the old ones. With nothing scaled out,
        `blended_r` IS `unrealized_r` and the dollars are unchanged."""
        self.load([(120, 121, 99, 101), (101, 108, 100, 106)])
        manual.create_intent(self.con, SPOT, "1H", "LONG", entry=100, tp=125,
                             sl=96, created_at=0, risk_usd=100)
        st = manual.status(self.con, SPOT, "1H", TF)[0]
        self.assertEqual(st["unrealized_r"], "1.50")
        self.assertEqual(st["blended_r"], "1.50")
        self.assertEqual(st["realized_r"], "0.00")
        self.assertEqual(st["open_fraction"], "1")
        self.assertEqual(st["unrealized_usd"], "150.00")

    def test_an_adopted_position_can_scale_out(self):
        """Custody means the operator's exit rules apply — the ladder with the
        rest of them."""
        self.load([(100, 100.5, 99.5, 100),
                   (100, 104.5, 99.8, 104),
                   (104, 110.5, 103, 110)])
        manual.adopt_position(self.con, "ENG|SCALE", SPOT, "1H", "LONG",
                              entry=100, sl=98, tp=110, fill_ts=0, adopted_at=0,
                              partials=[{"fraction": "0.5", "price": "104"}])
        self.run_engine()
        row = self.execs()[0]
        self.assertTrue(row["scaled_out"])
        self.assertEqual(row["r_multiple"], "3.09")   # same hand arithmetic

    # ---------- the version bump, and the intents it must not strand ----------

    def write_v01(self, kind, payload, symbol=PERP, tf="1H", at=0):
        """A fact under the RETIRED tag, written the way the old code wrote it.

        The migration cannot be tested against facts the current code produces,
        because the current code produces the current tag. These are stand-ins
        for what is already in the operator's store.
        """
        store.insert_fact(self.con, symbol=symbol, tf=tf, kind=kind,
                          market_time=at, confirmed_at=at,
                          algo_version="manual-v0.1-draft", payload=payload)
        self.con.commit()

    def v01_intent(self, iid="OLD|1", **kw):
        p = {"intent_id": iid, "source": "OPERATOR", "state": "ARMED",
             "direction": "LONG", "entry": "100", "tp": "104", "sl": "98",
             "risk_per_unit": "2", "risk_usd": "200", "armed_at": 0}
        p.update(kw)
        return p

    #: Every tag this book has SHIPPED. Append on a bump; never remove. This
    #: list is the assertion — naming only the newest one made the test fail
    #: on the NEXT bump for being a bump, which is not what it guards.
    SHIPPED_MANUAL_TAGS = ("manual-v0.1-draft", "manual-v0.2-draft",
                           "manual-v0.3-draft", "manual-v0.4-draft")

    def test_the_retired_tags_are_read_and_never_written(self):
        """The read set only ever grows. Dropping a tag strands every order
        still open under it — never settled, never expired, absent from every
        surface, because the resolver finds work by querying algo_version."""
        for tag in self.SHIPPED_MANUAL_TAGS:
            self.assertIn(tag, manual.MANUAL_VERSIONS,
                          f"{tag} left the read set — its open orders are stranded")
        self.assertIn(manual.MANUAL_VERSION, manual.MANUAL_VERSIONS)
        self.assertEqual(manual.MANUAL_VERSIONS[-1], manual.MANUAL_VERSION,
                         "the write tag must be the newest entry, last")
        self.assertEqual(len(set(manual.MANUAL_VERSIONS)),
                         len(manual.MANUAL_VERSIONS), "a tag is listed twice")

    def test_an_intent_still_open_under_the_old_tag_is_not_stranded(self):
        """The defect the bump would otherwise have shipped.

        The resolver finds work by querying `algo_version`. Moving the constant
        without widening the read set would leave every v0.1 order armed
        forever: never settled, never expired, and absent from every surface —
        an order the operator placed that the app quietly stopped believing in.
        """
        self.load(self.flat(2) + [(100, 104.5, 99, 104)], symbol=PERP)
        self.write_v01(manual.INTENT_KIND, self.v01_intent())
        self.assertIn((PERP, "1H"), manual.unresolved(self.con),
                      "a v0.1 order fell off the resolver's work list")
        self.assertEqual([r["intent_id"] for r in manual.live(self.con)], [],
                         "and it settles rather than sitting open")
        rows = self.execs(symbol=PERP)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "TP")

    def test_an_old_intent_settles_under_the_version_that_settled_it(self):
        """The exit fact names the code that PRODUCED it, which after the bump
        is v0.2. The intent keeps its own tag; the pair is joined by intent_id,
        which is what a join has always used."""
        self.load(self.flat(2) + [(100, 104.5, 99, 104)], symbol=PERP)
        self.write_v01(manual.INTENT_KIND, self.v01_intent())
        self.run_engine(symbol=PERP)
        new = store.get_facts(self.con, PERP, "1H", manual.EXEC_KIND,
                              manual.MANUAL_VERSION)
        self.assertEqual(len(new), 1, "the settlement must carry the new tag")
        # and the number is the one v0.1 would have written: one leg, no ladder
        p = __import__("json").loads(new[0]["payload"])
        self.assertEqual(len(p["legs"]), 1)
        self.assertEqual(str(manual.blend_r(p["legs"])), p["r_multiple"])

    def test_an_old_trade_that_already_settled_is_not_settled_again(self):
        """`done` reads across versions too. Without that, every trade the v0.1
        book closed would be re-resolved under the new tag — a second terminal
        fact for one trade, and the curve counting it twice."""
        self.load(self.flat(2) + [(100, 104.5, 99, 104)], symbol=PERP)
        self.write_v01(manual.INTENT_KIND, self.v01_intent())
        self.write_v01(manual.EXEC_KIND,
                       {"intent_id": "OLD|1", "source": "OPERATOR",
                        "direction": "LONG", "outcome": "TP", "entry": "100",
                        "exit_price": "104", "r_multiple": "1.59",
                        "r_gross": "2.00", "bars_held": 2}, at=3 * TF)
        r = self.run_engine(symbol=PERP)
        self.assertEqual(r["TP"], 0, "an already-settled trade was re-resolved")
        self.assertEqual(self.execs(symbol=PERP), [],
                         "a second terminal fact was written under the new tag")
        self.assertEqual(manual.book(self.con)["n"], 1,
                         "and the curve must count the trade once")

    def test_the_settled_book_does_not_blank_itself_when_the_tag_moves(self):
        """An operator's record is their record across a version bump. A book
        that reported only what the current code wrote would appear to reset on
        the day of the change — losing the history whose entire value is being
        long enough to mean something."""
        self.write_v01(manual.EXEC_KIND,
                       {"intent_id": "OLD|2", "source": "OPERATOR",
                        "direction": "LONG", "outcome": "TP", "entry": "100",
                        "exit_price": "104", "r_multiple": "1.59",
                        "r_gross": "2.00", "bars_held": 2}, at=3 * TF)
        b = manual.book(self.con)
        self.assertEqual(b["n"], 1, "the old book vanished")
        self.assertEqual(b["wins"], 1)
        self.assertEqual(b["total_r"], "1.59")
        self.assertEqual(b["version"], manual.MANUAL_VERSION)

    def test_an_old_open_order_can_still_be_cancelled(self):
        self.load(self.flat(2), symbol=PERP)
        self.write_v01(manual.INTENT_KIND,
                       self.v01_intent(iid="OLD|3", entry="90", tp="94",
                                       sl="88", armed_at=TF))
        res = manual.cancel_intent(self.con, "OLD|3", at=2 * TF)
        self.assertTrue(res["written"])
        self.assertEqual(manual.unresolved(self.con), {})

    def test_the_old_tag_is_isolated_from_every_strategy_query_too(self):
        """The isolation rule is what the separate book is FOR, and it has to
        hold for the retired tag as much as the current one."""
        for version in manual.MANUAL_VERSIONS:
            self.assertNotIn(version, (setups.SETUP_VERSION,
                                       execsim.EXEC_VERSION))
        self.load(self.flat(2) + [(100, 104.5, 99, 104)], symbol=PERP)
        self.write_v01(manual.INTENT_KIND, self.v01_intent())
        self.run_engine(symbol=PERP)
        for version in (setups.SETUP_VERSION, execsim.EXEC_VERSION):
            for kind in ("setup", "exec", "order", "setup_rejection"):
                self.assertEqual(
                    store.get_facts(self.con, PERP, "1H", kind, version), [],
                    f"a migrated manual trade surfaced under {kind}/{version}")

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

    def test_a_winning_position_may_move_its_stop_into_profit(self):
        """The bug an operator hit: up +1.5R on a SHORT, dragging the stop down
        to lock it in, and being told "a SHORT stop must sit ABOVE the entry" —
        advice for a trade that has not happened yet. R is fixed by the risk
        TAKEN at entry, so a profit-side stop simply guarantees a win."""
        self.load(self.flat(3), symbol=PERP)
        out = manual.adopt_position(
            self.con, "ENG|W", PERP, "1H", "SHORT",
            entry=100, original_sl=104, sl=96, tp=80,   # stop now in profit
            fill_ts=0, adopted_at=TF, risk_usd=200)
        # denominator stays the ENTRY risk (104-100), not the new stop
        self.assertEqual(Decimal(out["risk_per_unit"]), Decimal(4))
        self.assertEqual(Decimal(out["risk_ref_sl"]), Decimal(104))
        self.assertEqual(Decimal(out["size_units"]), Decimal(50))

    def test_a_profit_stop_settles_as_a_win_on_the_original_R(self):
        # short from 100, risk 4; stop locked at 96 -> +1R when it triggers
        self.load([(100, 101, 99, 100), (97, 99, 95, 96)], symbol=PERP)
        manual.adopt_position(self.con, "ENG|W2", PERP, "1H", "SHORT",
                              entry=100, original_sl=104, sl=96, tp=80,
                              fill_ts=0, adopted_at=0)
        self.run_engine(symbol=PERP)
        row = self.execs(symbol=PERP)[0]
        self.assertEqual(row["outcome"], "SL")          # the stop, but a winning one
        self.assertEqual(row["r_gross"], "1.00")
        self.assertGreater(Decimal(row["r_multiple"]), 0)

    def test_the_chart_shows_the_same_sign_the_book_settles(self):
        """status() priced R off the CURRENT stop, so a profit-side stop
        inverted unrealized R on screen while the book settled it correctly —
        the two surfaces disagreeing about whether a trade was winning."""
        # A profit-lock on a SHORT sits BELOW entry and ABOVE the market:
        # entered 100, price now 97.5, stop moved to 99. Adopted at bar 1, so
        # the new stop applies from bar 1 — bar 0's high of 101 belongs to the
        # trade as it was, not as it has just been redefined.
        self.load([(100, 101, 99, 100), (98, 98.5, 97, 97.5)], symbol=PERP)
        manual.adopt_position(self.con, "ENG|SIGN", PERP, "1H", "SHORT",
                              entry=100, original_sl=104, sl=99, tp=80,
                              fill_ts=0, adopted_at=TF, risk_usd=200)
        st = manual.status(self.con, PERP, "1H", TF)
        self.assertEqual(st[0]["state"], "OPEN")
        # short from 100 now at 97.5, risk 4 -> +0.625R, POSITIVE.
        # 0.62 not 0.63: Decimal quantizes half-to-even, like every other R
        # in this book.
        self.assertGreater(Decimal(st[0]["unrealized_r"]), 0)
        self.assertEqual(st[0]["unrealized_r"], "0.62")

    def test_new_levels_do_not_reach_back_and_stop_an_old_bar(self):
        """Moving a stop today must not stop the trade out on a bar that
        closed days ago. Those bars provably hit nothing — the position is
        still open — so re-judging them against new levels would fabricate an
        exit that never happened."""
        # bar 0 spiked to 101; a stop moved to 99 at bar 2 must ignore it
        self.load([(100, 101, 99, 100), (99, 99.5, 97, 97.5),
                   (97, 98, 96, 97)], symbol=PERP)
        manual.adopt_position(self.con, "ENG|BACK", PERP, "1H", "SHORT",
                              entry=100, original_sl=104, sl=99, tp=80,
                              fill_ts=0, adopted_at=2 * TF)
        self.run_engine(symbol=PERP)
        self.assertEqual(self.execs(symbol=PERP), [],
                         "an old bar was allowed to trigger a new stop")

    def test_adoption_still_refuses_a_target_on_the_wrong_side(self):
        """Position geometry is looser than entry geometry, not absent."""
        self.load(self.flat(3))
        with self.assertRaises(manual.IntentRejected):
            manual.adopt_position(self.con, "ENG|4", SPOT, "1H", "LONG",
                                  entry=100, original_sl=95, sl=98, tp=90,
                                  fill_ts=0, adopted_at=TF)

    def test_a_stop_beyond_the_target_is_refused(self):
        self.load(self.flat(3))
        with self.assertRaises(manual.IntentRejected):
            manual.adopt_position(self.con, "ENG|5", SPOT, "1H", "LONG",
                                  entry=100, original_sl=95, sl=125, tp=120,
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

    # ---------- the book in dollars ----------
    #
    # `book()` is a READ VIEW. It derives these and persists nothing, which is
    # the whole reason they need no version bump — see the comment in
    # manual.book(). If a future change writes pnl_usd into a payload, this
    # section is where the bump argument has to be re-made.

    def test_a_settled_trade_is_priced_with_the_engine_books_arithmetic(self):
        """R times the dollars at risk, quantized ROUND_HALF_UP.

        The rounding mode is the point, not decoration. Both operands arrive
        2dp-quantized so the product lands on four decimals and half-cent ties
        are reachable, where Python's round() banks to even. server.py builds
        the ENGINE journal's pnl_usd with ROUND_HALF_UP; if this side ever
        drifted, the two books on the Ledger would disagree by a cent on the
        same trade and neither would be believable.
        """
        self.load(self.flat(6) + [(100, 104, 99, 103)] + self.flat(5))
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0,
                             risk_usd=100)
        self.run_engine()
        b = manual.book(self.con)
        self.assertEqual(b["n"], 1, "precondition: one settled trade")
        row = b["trades"][0]
        want = (Decimal(row["r_multiple"]) * Decimal(row["risk_usd"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(row["pnl_usd"], str(want))
        self.assertEqual(b["total_pnl_usd"], str(want))
        self.assertEqual(b["n_no_risk_usd"], 0)

    def test_a_settled_trade_with_no_risk_figure_is_counted_never_dropped(self):
        """An R with no dollars behind it, permanently — and it must be loud.

        chart.js sends risk_usd=null when the ticket has no valid risk figure
        and the intent stores the null, so the trade settles with a real R and
        no way to ever price it. Dropping it from the total silently would make
        the dollar figure quietly cover fewer trades than the R figure beside
        it. The count is what lets the surface say "across 4 of 5 trades".
        """
        self.load(self.flat(6) + [(100, 104, 99, 103)] + self.flat(5))
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        b = manual.book(self.con)
        self.assertEqual(b["n"], 1, "precondition: it IS a settled trade")
        self.assertIsNone(b["trades"][0]["pnl_usd"])
        self.assertEqual(b["n_no_risk_usd"], 1)
        self.assertIsNone(b["total_pnl_usd"],
                          "no priced trade means no total — $0.00 would read "
                          "as break-even on a trade that lost or won")

    def test_pnl_usd_is_a_key_on_every_row_even_when_it_is_absent(self):
        """Absent, not missing. A reader's `?? 0` turns a missing key into 0."""
        self.load(self.flat(6) + [(100, 104, 99, 103)] + self.flat(5))
        manual.create_intent(self.con, SPOT, "1H", "LONG",
                             entry=100, tp=104, sl=98, created_at=0)
        self.run_engine()
        for row in manual.book(self.con)["trades"]:
            self.assertIn("pnl_usd", row)

    def test_a_cancelled_order_contributes_no_dollars(self):
        """Cancelling must not move the money curve any more than the R curve.

        The same argument as `test_cancel_resolves_the_intent_without_
        recording_a_trade`: if a withdrawn order counted, anyone could improve
        their record by cancelling the ones that looked like losers.
        """
        self.load(self.flat(4), symbol=PERP, tf="1H")
        intent = manual.create_intent(self.con, PERP, "1H", "LONG",
                                      entry=90, tp=94, sl=88, created_at=2 * TF,
                                      risk_usd=100)
        manual.cancel_intent(self.con, intent["intent_id"], at=4 * TF)
        b = manual.book(self.con)
        self.assertEqual([t["outcome"] for t in b["trades"]], ["CANCELLED"])
        self.assertIsNone(b["trades"][0]["pnl_usd"])
        self.assertIsNone(b["total_pnl_usd"], "nothing settled, so no total")
        self.assertEqual(b["n_no_risk_usd"], 0,
                         "a cancellation is not a trade missing its dollars")

    def test_the_total_covers_the_priced_trades_and_says_what_it_omits(self):
        """One priced settled trade, one unpriced, one cancelled — in one book.

        The total must equal the priced one alone, and `n_no_risk_usd` must
        name the gap. This is the shape the Ledger renders and the shape that
        would otherwise lie.
        """
        self.load(self.flat(6) + [(100, 104, 99, 103)] + self.flat(5))
        self.load(self.flat(6) + [(100, 104, 99, 103)] + self.flat(5),
                  symbol=PERP, tf="1H")
        self.load(self.flat(4), symbol=PERP2, tf="1H")
        manual.create_intent(self.con, SPOT, "1H", "LONG",       # priced
                             entry=100, tp=104, sl=98, created_at=0,
                             risk_usd=100)
        manual.create_intent(self.con, PERP, "1H", "LONG",       # no dollars
                             entry=100, tp=104, sl=98, created_at=0)
        cancelled = manual.create_intent(self.con, PERP2, "1H", "LONG",
                                         entry=90, tp=94, sl=88,
                                         created_at=2 * TF, risk_usd=100)
        self.run_engine()
        self.run_engine(symbol=PERP, tf="1H")
        manual.cancel_intent(self.con, cancelled["intent_id"], at=4 * TF)
        b = manual.book(self.con)
        self.assertEqual(b["n"], 2, "two settled trades, one of them unpriced")
        self.assertEqual(b["n_no_risk_usd"], 1)
        priced = [t for t in b["trades"] if t["pnl_usd"] is not None]
        self.assertEqual(len(priced), 1)
        self.assertEqual(b["total_pnl_usd"], priced[0]["pnl_usd"],
                         "the total must be the priced rows and only those")

    # ---------- the whole book, live: the bug that hid three orders ----------

    def test_live_reports_open_intents_across_every_market(self):
        """`status()` answers for one chart; three orders lived on three.

        This is the defect the panel exists to close: `/api/manual/book` reports
        the STORED state, which is `ARMED` forever because the resolver only
        writes at terminal outcomes, and `/api/manual/open` resolves properly
        but only for the symbol AND timeframe currently on screen. Neither could
        answer "what orders do I have out?", so armed trades were invisible on
        every surface — Command reads the engine's book, which by design they
        are not in.
        """
        # Armed at bar 8 of 10, so only two bars have closed since — inside the
        # 4-bar entry window, and price never reaches either entry. These are
        # resting orders, which is the state that was invisible.
        self.load(self.flat(10), symbol=PERP, tf="1H")
        self.load(self.flat(10), symbol=PERP2, tf="1H")
        manual.create_intent(self.con, PERP, "1H", "LONG",
                             entry=90, tp=94, sl=88, created_at=8 * TF, risk_usd=100)
        manual.create_intent(self.con, PERP2, "1H", "SHORT",
                             entry=110, tp=106, sl=112, created_at=8 * TF, risk_usd=50)
        rows = manual.live(self.con)
        self.assertEqual({r["symbol"] for r in rows}, {PERP, PERP2},
                         "live() must sweep every market with open work, not one chart")
        for r in rows:
            self.assertEqual(r["state"], "PENDING")
            self.assertEqual(r["tf"], "1H")
            self.assertTrue(r["bars_left"] > 0, "an order with no window left is not waiting")
            self.assertTrue(r["tf_seconds"] > 0, "the UI cannot say '1h left' without this")

    def test_live_reports_nothing_when_the_book_is_empty(self):
        """Zero orders is a fact, not a failure — and must not raise."""
        self.assertEqual(manual.live(self.con), [])

    # ---------- cancelling a resting order ----------

    def test_cancel_resolves_the_intent_without_recording_a_trade(self):
        """A withdrawn order is kept, never deleted, and never counted.

        Append-only: "what happened to that order?" has to stay answerable. But
        declining to take a trade is not a trade — if a cancellation counted,
        anyone could improve their record by cancelling the ones that looked
        like losers.
        """
        self.load(self.flat(4), symbol=PERP, tf="1H")
        intent = manual.create_intent(self.con, PERP, "1H", "LONG",
                                      entry=90, tp=94, sl=88, created_at=2 * TF,
                                      risk_usd=100)
        self.assertEqual([r["state"] for r in manual.live(self.con)], ["PENDING"],
                         "precondition: a resting order, not one already missed")
        res = manual.cancel_intent(self.con, intent["intent_id"], at=4 * TF)
        self.assertTrue(res["written"])
        self.assertEqual(manual.live(self.con), [], "a cancelled order is not open")
        self.assertEqual(manual.unresolved(self.con), {})
        b = manual.book(self.con)
        self.assertEqual(b["open_intents"], [], "it must leave the open list")
        self.assertEqual(b["n"], 0, "a cancellation is not a settled trade")
        self.assertEqual(b["wins"], 0)
        self.assertEqual(b["total_r"], "0.00", "cancelling must not move the curve")
        outcomes = [e["outcome"] for e in self.execs(symbol=PERP, tf="1H")]
        self.assertEqual(outcomes, ["CANCELLED"], "the fact must survive")

    def test_cancel_refuses_a_position_that_already_filled(self):
        """A filled trade is closed, not cancelled.

        Resolving one at zero R would erase a real result — the exact move that
        would let a losing trade be quietly un-taken.
        """
        # bar 1 trades through the entry, so the intent is OPEN, not resting
        self.load([(100, 101, 99, 100), (100, 101, 89, 95)] + self.flat(2),
                  symbol=PERP, tf="1H")
        intent = manual.create_intent(self.con, PERP, "1H", "LONG",
                                      entry=90, tp=120, sl=88, created_at=0,
                                      risk_usd=100)
        live = manual.live(self.con)
        self.assertEqual([r["state"] for r in live], ["OPEN"], "precondition")
        with self.assertRaises(manual.IntentRejected):
            manual.cancel_intent(self.con, intent["intent_id"])

    def test_cancel_refuses_an_unknown_intent(self):
        with self.assertRaises(manual.IntentRejected):
            manual.cancel_intent(self.con, "NOPE|1H|MANUAL|0")

    def test_a_cancelled_intent_stays_invisible_to_every_strategy_query(self):
        """The isolation rule holds for the new fact kind too."""
        self.load(self.flat(4), symbol=PERP, tf="1H")
        intent = manual.create_intent(self.con, PERP, "1H", "LONG",
                                      entry=90, tp=94, sl=88, created_at=2 * TF)
        manual.cancel_intent(self.con, intent["intent_id"], at=4 * TF)
        for version in (setups.SETUP_VERSION, execsim.EXEC_VERSION):
            for kind in ("setup", "exec", "order", "setup_rejection"):
                self.assertEqual(
                    store.get_facts(self.con, PERP, "1H", kind, version), [],
                    f"a cancelled manual order surfaced under {kind}/{version}")


FINE = 900          # 15m
COARSE = 14400      # 4H
SCALE = COARSE // FINE
# Every fixture below plans the same trade: LONG, entry 100, stop 98, target
# 104. These three bar shapes are the whole vocabulary, and they sit inside the
# bracket so that a bar which is not meant to do anything does nothing — a
# "quiet" bar that dipped under 98 would stop every trade out on the bar after
# its fill and every assertion here would be about that instead.
QUIET = ("101", "101.5", "100.5", "101")    # touches neither entry, stop nor tp
TOUCH = ("101", "101.2", "99.9", "101")     # contains the entry, nothing else
THROUGH = ("101", "105", "99.9", "101")     # contains the entry AND the target


class FinestTimeframeCase(unittest.TestCase):
    """An OPEN intent resolves on the finest series the store actually holds.

    The rule being fixed is not the causality rule — that one is right and
    every test here re-asserts it. It is that the rule was being applied at the
    CHART's timeframe: a 4H order armed four minutes into a bar threw away the
    whole four hours, because OHLC could not say whether that bar's high came
    before or after the arm. Fifteen minutes of granularity answers the same
    question outright, and a real exchange would have filled the order.

    Every fixture here is a 15m series with a 4H series AGGREGATED FROM IT, so
    the two timeframes are two readings of one market rather than two invented
    ones. Where a test needs them to disagree it says so.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    # ---------- fixtures ----------

    def fine(self, n=96, special=None):
        """`n` 15m bars from ts 0, quiet except where `special` names one."""
        special = special or {}
        return [(i * FINE, *special.get(i * FINE, QUIET)) for i in range(n)]

    def coarse(self, fine):
        """The 4H series those 15m bars aggregate to — same market, one view.

        Only whole buckets: a half-formed 4H bar is not a bar the store holds.
        """
        out, buckets = [], {}
        for ts, o, h, l, c in fine:
            buckets.setdefault(ts - ts % COARSE, []).append((ts, o, h, l, c))
        for ts0 in sorted(buckets):
            rows = buckets[ts0]
            if len(rows) < SCALE:
                continue
            out.append((ts0, rows[0][1],
                        str(max(Decimal(r[2]) for r in rows)),
                        str(min(Decimal(r[3]) for r in rows)),
                        rows[-1][4]))
        return out

    def write(self, symbol, tf, bars):
        for ts, o, h, l, c in bars:
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, tf, ts, str(o), str(h), str(l), str(c),
                 "1", "test", ts))
        self.con.commit()

    def arm(self, symbol=SPOT, armed_at=15000, **kw):
        return manual.create_intent(self.con, symbol, "4H", "LONG",
                                    entry=100, tp=104, sl=98,
                                    created_at=armed_at, risk_usd=100, **kw)

    def resolve(self, symbol=SPOT):
        return manual.run(self.con, symbol, "4H", COARSE)

    def execs(self, symbol=SPOT):
        import json
        return [json.loads(r["payload"]) for r in store.get_facts(
            self.con, symbol, "4H", manual.EXEC_KIND, manual.MANUAL_VERSION)]

    def notes(self):
        return [r[0] for r in self.con.execute(
            "SELECT notes FROM engine_runs WHERE engine='manual' "
            "ORDER BY id DESC LIMIT 1")]

    # ---------- the fix ----------

    def test_the_finest_stored_timeframe_is_what_an_open_intent_resolves_on(self):
        """The operator's ADAUSDT case, in miniature.

        Armed at 15000 — four minutes into the 15m bar that opened at 14400 and
        an hour into the 4H bar that opened at the same moment. The entry is
        touched by the NEXT 15m bar, 15300, which opened after the order did.
        At 4H granularity the whole 14400 bar is discarded and price never
        returns, so the order dies MISSED; at 15m it fills, because 15300 is
        provably clean.
        """
        fine = self.fine(special={
            # in progress when armed: trades through the entry AND the target.
            # If this bar is ever admitted the trade reports a fast winner.
            14400: THROUGH,
            # the first bar that OPENS after the arm, and it touches the entry
            15300: TOUCH})
        self.write(SPOT, "15m", fine)
        self.write(SPOT, "4H", self.coarse(fine))
        self.arm()

        out = self.resolve()
        self.assertEqual(out["resolution"], {"15m": 1})
        self.assertEqual(out["OPEN"], 1)
        self.assertEqual(self.execs(), [], "an open position settles nothing")

        row = manual.status(self.con, SPOT, "4H", COARSE)[0]
        self.assertEqual(row["state"], "OPEN")
        self.assertEqual(row["fill_price"], "100")
        self.assertEqual(row["resolution_tf"], "15m")
        self.assertIsNone(row["resolution_degraded"])
        # the REAL bar: 15300 opens, 16200 closes. Not the arm time, and not a
        # boundary of the 4H chart it was armed on.
        self.assertEqual(row["fill_ts"], 15300 + FINE)
        # and it is emphatically not the target, which only the discarded
        # in-progress bar ever reached
        self.assertNotIn("TP", [e["outcome"] for e in self.execs()])

    def test_a_fill_still_needs_a_bar_that_opened_after_the_order(self):
        """No-lookahead, re-asked at the finer grid where it now applies.

        The ONLY bar that ever touches the entry is the 15m bar in progress
        when the order was armed. Finer granularity must not admit it: OHLC
        still cannot say whether that touch came before or after the arm.
        """
        fine = self.fine(special={14400: THROUGH})
        self.write(SPOT, "15m", fine)
        self.write(SPOT, "4H", self.coarse(fine))
        self.arm()

        times = [b[0] for b in fine]
        self.assertEqual(manual._first_eligible_bar(times, FINE, 15000), 17,
                         "bar 16 opened at 14400 and was already running")
        self.assertEqual(times[16], 14400, "bar 16 is the one with the touch")

        self.resolve()
        rows = self.execs()
        self.assertEqual([r["outcome"] for r in rows], ["MISSED"])
        self.assertEqual(rows[0]["resolution_tf"], "15m",
                         "it missed ON the finer series, not by falling back")
        self.assertIsNone(rows[0]["resolution_degraded"])

    def test_the_entry_window_keeps_its_length_in_time_not_in_bars(self):
        """4 bars of 4H is sixteen hours, however the bars are cut.

        Left at the raw constant the window would become 4 bars of 15m — one
        hour — and would kill fifteen out of every sixteen resting orders.
        """
        order_i = 17                      # first 15m bar opening after 15000
        for symbol, offset, expect in ((SPOT, 63, "OPEN"), (PERP, 64, "MISSED")):
            with self.subTest(symbol=symbol, offset=offset):
                ts = (order_i + offset) * FINE
                fine = self.fine(special={ts: TOUCH})
                self.write(symbol, "15m", fine)
                self.write(symbol, "4H", self.coarse(fine))
                self.arm(symbol=symbol)
                self.resolve(symbol=symbol)
                if expect == "OPEN":
                    self.assertEqual(self.execs(symbol), [],
                                     "the last bar of the window still fills")
                    self.assertEqual(
                        manual.status(self.con, symbol, "4H", COARSE)[0]["state"],
                        "OPEN")
                else:
                    self.assertEqual(
                        [r["outcome"] for r in self.execs(symbol)], ["MISSED"],
                        "one bar past the window is past the window")

    def test_a_pending_row_counts_its_remaining_bars_in_the_chart_bars(self):
        """The screen prints these beside a 4H chart, so they must be 4H bars.

        The exact count on the resolving grid lives on the settled fact, where
        `resolution_tf` names its unit. A row that said "40 bars left" next to a
        4H chart would be a true number under a unit nobody would guess.
        """
        fine = self.fine(n=41)            # last close 36900, nothing touched
        self.write(SPOT, "15m", fine)
        self.write(SPOT, "4H", self.coarse(fine))
        self.arm()
        self.resolve()
        row = manual.status(self.con, SPOT, "4H", COARSE)[0]
        self.assertEqual(row["state"], "PENDING")
        self.assertEqual(row["resolution_tf"], "15m")
        # 17 + 64 - 41 = 40 fifteen-minute bars, which is 2.5 four-hour bars,
        # rounded UP so the row never promises less time than the order has.
        self.assertEqual(row["bars_left"], 3)

    # ---------- the fallback, and it must be audible ----------

    def test_with_no_finer_series_it_falls_back_and_says_so(self):
        """The old behaviour exactly — plus a sentence saying that is what ran.

        Same fixture as the fix's own test with the 15m series simply absent.
        The order dies MISSED, which is what every 4H order armed mid-bar used
        to do, and the fact and the run log both name the reason.
        """
        fine = self.fine(special={
            14400: THROUGH,
            15300: TOUCH})
        self.write(SPOT, "4H", self.coarse(fine))     # no 15m series at all
        self.arm()

        out = self.resolve()
        self.assertEqual(out["resolution"],
                         {"4H<no series finer than 4H is stored": 1})
        rows = self.execs()
        self.assertEqual([r["outcome"] for r in rows], ["MISSED"])
        self.assertEqual(rows[0]["resolution_tf"], "4H")
        self.assertEqual(rows[0]["resolution_degraded"],
                         "no series finer than 4H is stored")
        self.assertIn("res:4H<no series finer than 4H is stored=1",
                      self.notes()[0], "a silent fallback is a bug")

    def test_a_finer_series_that_begins_after_the_order_is_refused_audibly(self):
        """Its first stored bar is not the first bar after the arm.

        It is only the earliest one we happen to hold, so the fill window would
        start from there and the order would appear to have rested through
        hours it never rested through.
        """
        fine = self.fine(special={15300: TOUCH})
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", [b for b in fine if b[0] >= 43200])
        self.arm()

        out = self.resolve()
        self.assertEqual(
            out["resolution"],
            {"4H<15m history begins after the order was armed": 1})
        rows = self.execs()
        self.assertEqual(rows[0]["resolution_tf"], "4H")
        self.assertEqual(rows[0]["resolution_degraded"],
                         "15m history begins after the order was armed")

    def test_a_finer_series_that_stopped_being_ingested_is_refused_audibly(self):
        """A stale mark is the harm here, so the coarse series is the truth."""
        fine = self.fine()
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", [b for b in fine if b[0] < 14400])
        self.arm()
        out = self.resolve()
        self.assertEqual(
            out["resolution"],
            {"4H<15m bars have not reached the newest 4H bar": 1})
        self.assertEqual(self.execs()[0]["resolution_tf"], "4H")

    def test_one_cycle_of_ingestion_lag_does_not_downgrade_the_grid(self):
        """The staleness guard is loose on purpose.

        Trip it tightly and it fires whenever the two timeframes land in a
        different order inside one ingestion cycle — and a fill resolved on the
        coarse grid during that flap would be settled on the coarse grid
        forever. A transient race must not permanently downgrade a trade.
        """
        fine = self.fine(special={15300: TOUCH})
        self.write(SPOT, "4H", self.coarse(fine))
        # the newest 4H bar has landed; the 15m bars inside it have not yet
        self.write(SPOT, "15m", [b for b in fine if b[0] < 72000])
        self.arm()
        out = self.resolve()
        self.assertEqual(out["resolution"], {"15m": 1})

    # ---------- history does not move ----------

    def test_a_settled_trade_is_not_touched_when_finer_bars_arrive(self):
        """The operator chose the option that leaves history alone.

        A trade settled on 4H bars keeps its stored fact, byte for byte, when
        a 15m series for the same symbol appears afterwards — even though the
        finer series would have filled it on a different bar. Settled intents
        are skipped before any series is chosen, so there is no path by which
        an outcome can move; this pins that there is no other one.
        """
        import json
        fine = self.fine(special={
            # fills inside the FIRST eligible 4H bar at 15m granularity, but
            # only reaches the entry and the target on the 4H bar after it
            43200: TOUCH,
            60300: ("101", "104", "100.5", "104")})
        self.write(SPOT, "4H", self.coarse(fine))
        intent = self.arm()
        self.resolve()
        before = [dict(r) for r in store.get_facts(
            self.con, SPOT, "4H", manual.EXEC_KIND, manual.MANUAL_VERSION)]
        self.assertEqual([json.loads(r["payload"])["outcome"] for r in before],
                         ["TP"], "precondition: it settled on the 4H bars")
        self.assertEqual(json.loads(before[0]["payload"])["fill_ts"],
                         43200 + COARSE, "it filled on the close of a 4H bar")
        book_before = manual.book(self.con)

        self.write(SPOT, "15m", fine)     # the finer series arrives late
        # ...and it really would have answered differently, or this test is
        # asserting that nothing changed about nothing.
        finer = manual._finer_series(self.con, SPOT, "4H", COARSE)
        w = manual._walk(intent, finer["candles"], finer["candle_times"], FINE,
                         max_entry_bars=4 * SCALE, max_bars=100 * SCALE)
        self.assertEqual(
            finer["candles"][w["fill_i"]]["open_ts"] + FINE, 43200 + FINE,
            "the 15m walk fills on a different bar entirely")

        self.resolve()
        self.resolve()
        after = [dict(r) for r in store.get_facts(
            self.con, SPOT, "4H", manual.EXEC_KIND, manual.MANUAL_VERSION)]
        self.assertEqual(after, before, "a settled fact was rewritten")
        self.assertEqual(manual.book(self.con), book_before,
                         "a settled outcome moved")

    # ---------- an adopted position is located by ITS OWN fill ----------

    def adopt(self, fill_ts, adopted_at=50000, symbol=SPOT):
        """An engine LONG the operator takes custody of, filled at `fill_ts`.

        Entry 100 with the bracket outside every fixture bar, so the position
        simply stays OPEN and any exit an assertion sees is a fabricated one.
        """
        return manual.adopt_position(
            self.con, "ENG|ADOPTED", symbol, "4H", "LONG",
            entry=100, sl=98, tp=104,
            fill_ts=fill_ts, adopted_at=adopted_at, risk_usd=100)

    def half_fine(self, fine):
        """The 15m series as it really is on the store: shorter than the chart.

        15m history is retained for weeks and 1D history for years, so an
        adopted position whose engine fill is older than a few weeks routinely
        predates every 15m bar the store holds.
        """
        return [b for b in fine if b[0] >= 43200]

    def test_a_finer_series_that_begins_after_an_ADOPTED_fill_is_refused(self):
        """The fill is INDEXED, not hunted, so a short series cannot be late.

        `armed_at` on an adopted position is when custody was taken; the fill
        is `adopted_fill_ts` and can be months earlier. Judged on `armed_at`
        the 15m series looked usable, and then `bisect_left` on a timestamp
        before its first bar returned 0 and pinned the fill to whatever bar
        the series happens to begin on — a price and a time with no relation
        to the trade, written with `resolution_degraded` null.
        """
        fine = self.fine()
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", self.half_fine(fine))     # begins at 43200
        self.adopt(fill_ts=10000)                         # engine filled before that

        out = self.resolve()
        self.assertEqual(
            out["resolution"],
            {"4H<15m history begins after the position filled": 1},
            "the finer series was admitted on a moment this fill never had")
        self.assertEqual(out["OPEN"], 1)
        self.assertEqual(self.execs(), [],
                         "an open position settled itself on fabricated bars")
        self.assertIn("res:4H<15m history begins after the position filled=1",
                      self.notes()[0], "a silent fallback is a bug")

        row = manual.status(self.con, SPOT, "4H", COARSE)[0]
        self.assertEqual(row["state"], "OPEN")
        self.assertEqual(row["resolution_tf"], "4H")
        self.assertEqual(row["resolution_degraded"],
                         "15m history begins after the position filled")
        # the first 4H bar OPENING at or after the real fill, closing 28800 —
        # not 44100, which is where the 15m series merely begins.
        self.assertEqual(row["fill_ts"], 14400 + COARSE)

    def test_an_adopted_fill_the_finer_series_covers_still_resolves_finely(self):
        """The guard must refuse the uncovered fill, not adopted positions.

        Same fixture, same short 15m series, a fill inside it: the finer grid
        is used, and it locates the fill on its own bar.
        """
        fine = self.fine()
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", self.half_fine(fine))
        self.adopt(fill_ts=46800)

        out = self.resolve()
        self.assertEqual(out["resolution"], {"15m": 1})
        row = manual.status(self.con, SPOT, "4H", COARSE)[0]
        self.assertEqual(row["resolution_tf"], "15m")
        self.assertIsNone(row["resolution_degraded"])
        self.assertEqual(row["fill_ts"], 46800 + FINE)

    def test_a_series_beginning_exactly_on_the_fill_is_covered(self):
        """The boundary the guard is drawn at: `>`, not `>=`.

        A series whose first bar opens at the fill moment holds that fill, and
        index 0 is then the right answer rather than an accident of where the
        history starts.
        """
        fine = self.fine()
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", self.half_fine(fine))
        self.adopt(fill_ts=43200)
        self.assertEqual(self.resolve()["resolution"], {"15m": 1})
        row = manual.status(self.con, SPOT, "4H", COARSE)[0]
        self.assertEqual(row["fill_ts"], 43200 + FINE)

    def test_the_series_is_admitted_and_the_fill_indexed_by_ONE_timestamp(self):
        """The property, stated structurally rather than by example.

        The bug was two timestamps: the guard asked `armed_at` and the index
        asked `adopted_fill_ts`. Any answer at all is safe as long as both
        sides ask the SAME question, so this replaces the question with one of
        its own and requires both sides to have moved.

        A re-inlined `p["armed_at"]` in `_resolution` or `p["adopted_fill_ts"]`
        in `_walk` stops consulting `_fill_anchor` and fails here, which is
        exactly the regression this pins.
        """
        from unittest import mock
        fine = self.fine()
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", self.half_fine(fine))
        p = self.adopt(fill_ts=46800)                 # covered by the 15m series
        base_rows = [dict(r) for r in store.get_candles(self.con, SPOT, "4H")]
        base = {"tf": "4H", "tf_seconds": COARSE, "candles": base_rows,
                "candle_times": [c["open_ts"] for c in base_rows],
                "scale": 1, "atr": None}
        finer = manual._finer_series(self.con, SPOT, "4H", COARSE)

        # unpatched: covered, so the finer grid is used and locates the fill
        res, degraded = manual._resolution(base, finer, p)
        self.assertEqual((res["tf"], degraded), ("15m", None))
        w = manual._walk(p, res["candles"], res["candle_times"],
                         res["tf_seconds"], max_entry_bars=4 * res["scale"],
                         max_bars=100 * res["scale"])
        self.assertEqual(res["candles"][w["fill_i"]]["open_ts"], 46800)

        # move the anchor to before the 15m history and BOTH sides must follow:
        # the guard refuses, and the walk on what is left indexes the new
        # moment rather than the old one.
        with mock.patch.object(manual, "_fill_anchor", return_value=10000):
            res2, degraded2 = manual._resolution(base, finer, p)
            self.assertEqual(res2["tf"], "4H",
                             "_resolution did not ask _fill_anchor")
            self.assertEqual(degraded2,
                             "15m history begins after the position filled")
            w2 = manual._walk(p, res2["candles"], res2["candle_times"],
                              res2["tf_seconds"],
                              max_entry_bars=4 * res2["scale"],
                              max_bars=100 * res2["scale"])
            self.assertEqual(res2["candles"][w2["fill_i"]]["open_ts"], 14400,
                             "_walk did not ask _fill_anchor")

    def test_an_ordinary_order_is_still_anchored_to_when_it_was_armed(self):
        """A resting order has no fill yet, so its moment is the arm — and the
        wording on the fallback still says so."""
        self.assertEqual(manual._fill_anchor({"armed_at": 15000}), 15000)
        self.assertEqual(
            manual._fill_anchor({"armed_at": 15000, "adopted_fill_ts": None}),
            15000)
        self.assertEqual(
            manual._fill_anchor({"armed_at": 50000, "adopted_fill_ts": 10000}),
            10000)
        fine = self.fine(special={15300: TOUCH})
        self.write(SPOT, "4H", self.coarse(fine))
        self.write(SPOT, "15m", self.half_fine(fine))
        self.arm()
        self.assertEqual(
            self.resolve()["resolution"],
            {"4H<15m history begins after the order was armed": 1})

    # ---------- the guards that read the walk ----------

    def test_cancel_sees_a_fill_that_landed_on_the_finer_series(self):
        """Cancelling a filled position at 0R would erase a real result.

        The guard asks the walk whether the intent is OPEN. Asked at the
        chart's timeframe it would not yet see a fill the resolver already has,
        and the operator could un-take a live trade.
        """
        fine = self.fine(special={15300: TOUCH})
        self.write(SPOT, "15m", fine)
        self.write(SPOT, "4H", self.coarse(fine))
        intent = self.arm()
        self.assertEqual(manual.status(self.con, SPOT, "4H", COARSE)[0]["state"],
                         "OPEN", "precondition")
        with self.assertRaises(manual.IntentRejected):
            manual.cancel_intent(self.con, intent["intent_id"])


if __name__ == "__main__":
    unittest.main()
