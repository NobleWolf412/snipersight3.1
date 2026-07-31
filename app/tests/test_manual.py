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
