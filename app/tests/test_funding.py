"""Real funding, measured against the constant execsim charges.

The properties here are the ones that make the measurement trustworthy rather
than merely different from the model: the SIGN, the refusal to price a hold the
published history does not cover, and the paging that decides how much of the
book can be priced at all.

No network. Every test stubs the fetch, because a suite that reaches two
exchanges is a suite that fails on a train.
"""
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import funding, store


def series(pairs):
    """(hour offset, rate) -> the (unix, Decimal) shape history() returns."""
    return [(3600 * h, Decimal(str(r))) for h, r in pairs]


class TheSign(unittest.TestCase):
    """A short is PAID when the rate is positive. execsim subtracts funding in
    both directions, which on a book where half the settlements are negative is
    not a magnitude error — it is the wrong side of zero."""

    def test_a_long_pays_a_positive_rate(self):
        c = funding.charge(series([(0, "0.001"), (1, "0.001")]),
                           "LONG", 0, Decimal(2), Decimal(100))
        self.assertEqual(c["settlements"], 2)
        self.assertEqual(c["rate_sum"], Decimal("0.002"))
        self.assertEqual(c["price_units"], Decimal("0.2"))    # a cost

    def test_a_short_is_paid_the_same_rate(self):
        c = funding.charge(series([(0, "0.001"), (1, "0.001")]),
                           "SHORT", 0, Decimal(2), Decimal(100))
        self.assertEqual(c["rate_sum"], Decimal("-0.002"))
        self.assertEqual(c["price_units"], Decimal("-0.2"))   # a credit

    def test_a_negative_rate_reverses_both(self):
        long = funding.charge(series([(0, "-0.001")]), "LONG", 0, Decimal(1), Decimal(100))
        short = funding.charge(series([(0, "-0.001")]), "SHORT", 0, Decimal(1), Decimal(100))
        self.assertLess(long["price_units"], 0, "a long RECEIVES a negative rate")
        self.assertGreater(short["price_units"], 0, "a short PAYS a negative rate")

    def test_only_settlements_inside_the_hold_are_charged(self):
        s = series([(0, "0.01"), (1, "0.01"), (2, "0.01"), (3, "0.01")])
        c = funding.charge(s, "LONG", 3600, Decimal(2), Decimal(100))
        self.assertEqual(c["settlements"], 2, "the hold covers hours 1 and 2 only")


class CoverageIsRefused(unittest.TestCase):
    """A hold priced from a partial window reports a cost that is too small for
    the honest reason that we could not see all of it. §4: that is
    flattering-by-omission, and the caller has to be able to drop the trade."""

    def test_a_hold_that_starts_before_the_history_is_not_covered(self):
        s = series([(10, "0.001"), (11, "0.001")])
        c = funding.charge(s, "LONG", 3600 * 5, Decimal(10), Decimal(100))
        self.assertFalse(c["covered"])

    def test_a_hold_that_ends_after_the_history_is_not_covered(self):
        s = series([(0, "0.001"), (1, "0.001")])
        c = funding.charge(s, "LONG", 0, Decimal(50), Decimal(100))
        self.assertFalse(c["covered"])

    def test_a_fully_spanned_hold_is_covered(self):
        s = series([(0, "0.001"), (1, "0.001"), (2, "0.001"), (3, "0.001")])
        c = funding.charge(s, "LONG", 3600, Decimal(1), Decimal(100))
        self.assertTrue(c["covered"])

    def test_an_empty_series_is_never_covered(self):
        self.assertFalse(funding.charge([], "LONG", 0, Decimal(1), Decimal(100))["covered"])


class Paging(unittest.TestCase):
    """Phemex answers 100 settlements per call whatever `limit` asks, so the
    history is only reachable by walking `end` backwards.

    This is the test the first implementation would have failed. It sent
    `start` as well, the feed answered with the rows at the START of a wide
    window, and the loop stopped on page one holding nothing recent — priced
    trades fell from 345 to 269. The bug was visible only as a coverage number
    going the wrong way, which is exactly the kind of regression a suite should
    not need a human to notice."""

    def setUp(self):
        self.calls = []
        self.real_get, self.real_now = funding._get, funding._now
        funding._now = lambda: 1_000_000
        # 8-hourly settlements, newest first, exactly as the venue returns them
        def fake(url):
            self.calls.append(url)
            end = int(url.split("end=")[1].split("&")[0]) // 1000
            rows = [{"fundingTime": (end - i * 28800) * 1000,
                     "fundingRate": "0.00001"} for i in range(1, 101)]
            return {"data": {"rows": rows}}
        funding._get = fake

    def tearDown(self):
        funding._get, funding._now = self.real_get, self.real_now

    def test_it_walks_back_until_the_window_is_covered(self):
        want = 1_000_000 - 400 * 28800          # 400 settlements back
        got = funding.phemex_history("BTCUSDT", since_ts=want)
        self.assertGreaterEqual(len(got), 400)
        self.assertLessEqual(got[0][0], want, "did not reach the requested start")
        self.assertGreater(len(self.calls), 1, "one page cannot cover 400 settlements")

    def test_it_never_sends_start(self):
        funding.phemex_history("BTCUSDT", since_ts=1_000_000 - 200 * 28800)
        self.assertTrue(self.calls)
        for url in self.calls:
            self.assertNotIn("start=", url,
                             "sending `start` makes the feed answer from the OLD "
                             "end of the window and the walk stops on page one")

    def test_it_stops_rather_than_paging_forever(self):
        funding._get = lambda url: {"data": {"rows": []}}
        self.assertEqual(funding.phemex_history("BTCUSDT", since_ts=0), [])


class ReadOnly(unittest.TestCase):
    def test_the_report_writes_no_facts(self):
        """§1. A measurement that mutates the thing it measures is not one."""
        with tempfile.TemporaryDirectory() as d:
            con = store.connect(Path(d) / "t.db")
            try:
                before = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
                rep = funding.report(con)
                after = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
                self.assertEqual(before, after)
                self.assertIsNone(rep["totals"], "an empty store prices nothing")
            finally:
                con.close()


class SpotPaysNothing(unittest.TestCase):
    def test_a_spot_symbol_has_no_funding_series(self):
        """Asked of `venues`, not re-decided here (§6) — a venue whose
        settlement schedule changes changes in one place."""
        self.assertEqual(funding.history("BTC-USD"), [])


if __name__ == "__main__":
    unittest.main()
