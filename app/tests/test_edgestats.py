import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import edgestats, execsim, setups, store, venues

# Synthetic books use a fixed geometry so every number below is hand-checkable:
#   entry 100, stop 90  -> stop distance (1R) = 10 price units
#   exit  = entry + r_gross * 10          (LONG, so a win exits above entry)
#   fee   = fees_r * 10 price units       (fees_r is the fee in R)
# No market-exit slippage is modelled in these books, so costs_r == fees_r and
# r_gross == r_net + fees_r exactly. That keeps the breakeven-fee arithmetic
# exact rather than approximately right.
ENTRY = Decimal("100")
STOP = Decimal("90")
RISK = ENTRY - STOP


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.con = store.connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


def add_trade(con, sid, r_net, *, fees_r="0.10", symbol="BTC-USD", tf="1D",
              market_time=None, confirmed_at=None, strategy="PULLBACK",
              outcome=None):
    """Insert the setup+exec fact pair for one filled paper trade."""
    r_net = Decimal(str(r_net))
    fees_r = Decimal(str(fees_r))
    r_gross = r_net + fees_r
    exit_price = ENTRY + r_gross * RISK
    market_time = market_time if market_time is not None else abs(hash(sid)) % 10**6
    confirmed_at = confirmed_at if confirmed_at is not None else market_time + 86400
    outcome = outcome or ("TP" if r_gross > 0 else "SL")
    store.insert_fact(
        con, symbol=symbol, tf=tf, kind="setup",
        market_time=market_time, confirmed_at=confirmed_at - 1,
        algo_version=setups.SETUP_VERSION,
        payload={"setup_id": sid, "strategy": strategy, "direction": "LONG",
                 "entry": str(ENTRY), "sl": str(STOP), "tp": str(exit_price),
                 "rr": "2", "rank": 50, "state": "VALIDATED"})
    store.insert_fact(
        con, symbol=symbol, tf=tf, kind="exec",
        market_time=market_time, confirmed_at=confirmed_at,
        algo_version=execsim.EXEC_VERSION,
        payload={"setup_id": sid, "strategy": strategy, "direction": "LONG",
                 "outcome": outcome, "entry": str(ENTRY),
                 "exit_price": str(exit_price),
                 "effective_exit_price": str(exit_price),
                 "fees_price_units": str(fees_r * RISK),
                 "r_multiple": str(r_net), "r_gross": str(r_gross),
                 "costs_r": str(fees_r),
                 "entry_fee_role": "MAKER",
                 "exit_fee_role": "MAKER" if outcome == "TP" else "TAKER"})


def add_missed(con, sid, *, symbol="BTC-USD", tf="1D", market_time=0):
    """An order that never filled. Not a trade — must not reach the statistics."""
    store.insert_fact(
        con, symbol=symbol, tf=tf, kind="setup", market_time=market_time,
        confirmed_at=market_time + 10, algo_version=setups.SETUP_VERSION,
        payload={"setup_id": sid, "strategy": "PULLBACK", "direction": "LONG",
                 "entry": str(ENTRY), "sl": str(STOP), "tp": "120", "rr": "2",
                 "rank": 50, "state": "VALIDATED"})
    store.insert_fact(
        con, symbol=symbol, tf=tf, kind="exec", market_time=market_time,
        confirmed_at=market_time + 20, algo_version=execsim.EXEC_VERSION,
        payload={"setup_id": sid, "strategy": "PULLBACK", "direction": "LONG",
                 "outcome": "MISSED", "entry": str(ENTRY), "exit_price": None,
                 "r_multiple": "0", "r_gross": "0", "costs_r": "0"})


def build(con, wins, losses, *, win_r="2.0", loss_r="-1.0", tf="1D"):
    """A book of `wins` winners then `losses` losers, interleaved by time."""
    seq = [win_r] * wins + [loss_r] * losses
    for i, r in enumerate(seq):
        add_trade(con, f"s{i}", r, tf=tf, market_time=i * 1000,
                  confirmed_at=i * 1000 + 500)


class TestDeterminism(TempStore):
    """A recorded result that changes between runs is not a result (§4)."""

    def test_two_runs_over_the_same_store_are_identical(self):
        build(self.con, 8, 12)
        a = edgestats.report(self.con, resamples=2000)
        b = edgestats.report(self.con, resamples=2000)
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))

    def test_two_independently_built_stores_agree_byte_for_byte(self):
        build(self.con, 8, 12)
        with tempfile.TemporaryDirectory() as d:
            other = store.connect(Path(d) / "other.db")
            try:
                build(other, 8, 12)
                a = edgestats.report(self.con, resamples=2000)
                b = edgestats.report(other, resamples=2000)
            finally:
                other.close()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        # And the bootstrap actually ran — an all-None report would pass the
        # equality check above for the wrong reason.
        self.assertIsNotNone(a["book"]["bootstrap"])

    def test_report_writes_no_facts(self):
        build(self.con, 8, 12)
        before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        edgestats.report(self.con, resamples=500)
        after = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        self.assertEqual(before, after)


class TestKnownBooks(TempStore):
    def test_positive_book_has_a_ci_entirely_above_zero(self):
        build(self.con, 14, 6)
        rep = edgestats.report(self.con, resamples=4000)
        book = rep["book"]
        self.assertEqual(book["n"], 20)
        self.assertAlmostEqual(book["mean_r"], (14 * 2.0 - 6 * 1.0) / 20)
        self.assertAlmostEqual(book["win_rate"], 0.7)
        self.assertAlmostEqual(book["profit_factor"], 28.0 / 6.0)
        self.assertGreater(book["bootstrap"]["ci_lo"], 0)
        self.assertEqual(book["bootstrap"]["p_gt_zero"], 1.0)
        self.assertEqual(rep["verdict"]["code"], "POSITIVE_EDGE")

    def test_negative_book_has_a_ci_entirely_below_zero(self):
        build(self.con, 4, 21)
        rep = edgestats.report(self.con, resamples=4000)
        book = rep["book"]
        self.assertEqual(book["n"], 25)
        self.assertAlmostEqual(book["mean_r"], (4 * 2.0 - 21 * 1.0) / 25)
        self.assertLess(book["bootstrap"]["ci_hi"], 0)
        self.assertLess(book["bootstrap"]["p_gt_zero"], 0.05)
        self.assertEqual(rep["verdict"]["code"], "NEGATIVE_EDGE")

    def test_longest_losing_streak_is_counted_in_confirmation_order(self):
        # 4 winners first, then 21 straight losers: the streak the operator
        # would actually have lived through is 21.
        build(self.con, 4, 21)
        rep = edgestats.report(self.con, resamples=500)
        self.assertEqual(rep["book"]["max_consecutive_losses"], 21)

    def test_unfilled_orders_never_reach_the_statistics(self):
        build(self.con, 6, 6)
        for i in range(5):
            add_missed(self.con, f"missed{i}", market_time=900000 + i)
        rep = edgestats.report(self.con, resamples=500)
        self.assertEqual(rep["counts"]["exec_facts"], 17)
        self.assertEqual(rep["counts"]["unfilled_missed"], 5)
        self.assertEqual(rep["book"]["n"], 12)
        # 6 wins at +2 and 6 losses at -1 -> +0.5, not the +0.353 that five
        # zero-R non-trades would have diluted it to.
        self.assertAlmostEqual(rep["book"]["mean_r"], 0.5)


class TestSmallSampleRefusal(TempStore):
    def test_short_book_refuses_instead_of_returning_a_confident_zero(self):
        build(self.con, 2, 3)
        rep = edgestats.report(self.con, resamples=500)
        self.assertFalse(rep["sufficient"])
        self.assertIsNone(rep["book"])
        self.assertIsNone(rep["scenarios"])
        self.assertIsNone(rep["breakeven_fee"])
        self.assertIsNone(rep["verdict"])
        self.assertIn("refusal, not a result of zero", rep["refusal"])
        self.assertEqual(rep["counts"]["filled"], 5)

    def test_empty_book_refuses_rather_than_reporting_zero_expectancy(self):
        rep = edgestats.report(self.con, resamples=500)
        self.assertFalse(rep["sufficient"])
        self.assertIsNone(rep["book"])
        self.assertIn("0 filled trade", rep["refusal"])

    def test_thin_timeframe_is_refused_without_poisoning_the_book(self):
        build(self.con, 7, 8)                      # 15 trades on 1D
        add_trade(self.con, "h1", "3.0", tf="1H", market_time=50, confirmed_at=60)
        rep = edgestats.report(self.con, resamples=1000)
        self.assertTrue(rep["book"]["sufficient"])
        self.assertFalse(rep["by_tf"]["1H"]["sufficient"])
        self.assertIsNone(rep["by_tf"]["1H"]["mean_r"])
        self.assertIsNone(rep["by_tf"]["1H"]["bootstrap"])
        self.assertIn("below the 10-trade floor", rep["by_tf"]["1H"]["refusal"])
        self.assertTrue(rep["by_tf"]["1D"]["sufficient"])


class TestBreakevenFee(TempStore):
    def test_breakeven_per_side_fee_is_mean_fee_free_r_over_mean_leg_r(self):
        # 12 identical trades: r_net +0.90 with a 0.10 R fee already netted, so
        # fee-free expectancy is +1.00 R. Exit sits at 110 (r_gross +1.00), so
        # the fee base is (100 + 110) / 10 = 21 R per trade.
        #   breakeven per-side fee = 1.00 / 21 = 4.7619%
        for i in range(12):
            add_trade(self.con, f"b{i}", "0.90", fees_r="0.10",
                      market_time=i * 1000, confirmed_at=i * 1000 + 500)
        be = edgestats.report(self.con, resamples=500)["breakeven_fee"]
        self.assertTrue(be["computable"])
        self.assertAlmostEqual(be["mean_r_ex_fee"], 1.0)
        self.assertAlmostEqual(be["mean_legs_r"], 21.0)
        self.assertAlmostEqual(be["per_side"], 1.0 / 21.0)
        self.assertAlmostEqual(be["round_trip"], 2.0 / 21.0)
        self.assertFalse(be["no_fee_rescues_it"])

    def test_breakeven_is_compared_against_the_venue_not_a_hard_coded_rate(self):
        for i in range(12):
            add_trade(self.con, f"b{i}", "0.90", fees_r="0.10",
                      market_time=i * 1000, confirmed_at=i * 1000 + 500)
        be = edgestats.report(self.con, resamples=500)["breakeven_fee"]
        row = next(v for v in be["venues"] if v["venue"] == "coinbase-spot")
        self.assertEqual(row["n_trades"], 12)
        # One authority per number: these must equal venues.py, not a copy.
        self.assertAlmostEqual(row["maker_rate"],
                               float(venues.COINBASE_SPOT.maker_rate))
        self.assertAlmostEqual(row["taker_rate"],
                               float(venues.COINBASE_SPOT.taker_rate))
        self.assertAlmostEqual(
            row["round_trip_rate"],
            float(venues.round_trip_cost_rate("BTC-USD")))
        # 9.52% round-trip breakeven clears Coinbase's 1.00% round trip.
        self.assertTrue(row["survives"])

    def test_a_book_that_loses_before_fees_reports_no_fee_rescues_it(self):
        for i in range(12):
            add_trade(self.con, f"b{i}", "-1.10", fees_r="0.10",
                      market_time=i * 1000, confirmed_at=i * 1000 + 500)
        rep = edgestats.report(self.con, resamples=1000)
        be = rep["breakeven_fee"]
        self.assertAlmostEqual(be["mean_r_ex_fee"], -1.0)
        self.assertLess(be["per_side"], 0)
        self.assertTrue(be["no_fee_rescues_it"])
        self.assertFalse(
            next(v for v in be["venues"] if v["venue"] == "coinbase-spot")["survives"])
        self.assertIn("already losing at ZERO fees", rep["verdict"]["text"])


class TestFeeScenarios(TempStore):
    def test_recorded_r_is_not_re_netted_and_venue_rates_re_price_it(self):
        """The caveat that inverts on the port: r_multiple already has fees in.

        The 'as recorded' scenario must reproduce mean(r_multiple) exactly, and
        'fee-free' must be exactly that plus the recorded fee — anything else
        means a fee got counted twice.
        """
        for i in range(12):
            add_trade(self.con, f"b{i}", "0.90", fees_r="0.10",
                      market_time=i * 1000, confirmed_at=i * 1000 + 500)
        rep = edgestats.report(self.con, resamples=500)
        recorded, fee_free, venue_real = rep["scenarios"]
        self.assertAlmostEqual(recorded["mean_r"], 0.9)
        self.assertAlmostEqual(fee_free["mean_r"], 1.0)
        # Coinbase maker both sides (TP exits on a resting limit): 0.40% of
        # (100 + 110) = 0.84 price units = 0.084 R.
        self.assertAlmostEqual(venue_real["mean_r"], 1.0 - 0.084)

    def test_filters_narrow_the_book(self):
        build(self.con, 6, 6)
        for i in range(11):
            add_trade(self.con, f"rev{i}", "-1.0", strategy="REVERSAL",
                      market_time=500000 + i * 1000,
                      confirmed_at=500000 + i * 1000 + 500)
        rep = edgestats.report(self.con, strategy="REVERSAL", resamples=500)
        self.assertEqual(rep["book"]["n"], 11)
        self.assertAlmostEqual(rep["book"]["mean_r"], -1.0)
        self.assertEqual(rep["counts"]["filtered_out_strategy"], 12)


if __name__ == "__main__":
    unittest.main()
