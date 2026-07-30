"""Phemex perp adapter — contract and safety tests. No network.

The endpoint shapes here were captured from the live API on 2026-07-29. If
Phemex changes them these tests keep passing while reality breaks, so the live
probe in BUILDLOG S31 is the companion check — these guard OUR logic.
"""
import time
import unittest
import urllib.error
from unittest import mock

from engine import phemex


def _rows(start, gran, n, price=100.0):
    """[ts, resolution, lastClose, open, high, low, close, volume]"""
    return [[start + i * gran, gran, str(price), str(price), str(price + 2),
             str(price - 2), str(price + 1), "10"] for i in range(n)]


class ProductsTest(unittest.TestCase):
    def test_only_usdt_settled_perps_are_listed(self):
        payload = {"data": {"perpProductsV2": [
            {"symbol": "BTCUSDT", "settleCurrency": "USDT", "quoteCurrency": "USDT",
             "contractUnderlyingAssets": "BTC", "status": "Listed", "maxLeverage": 100},
            {"symbol": "BTCUSDC", "settleCurrency": "USDC", "quoteCurrency": "USDC",
             "contractUnderlyingAssets": "BTC", "status": "Listed"},
            {"symbol": "OLDUSDT", "settleCurrency": "USDT", "quoteCurrency": "USDT",
             "contractUnderlyingAssets": "OLD", "status": "Delisted"},
        ]}}
        with mock.patch.object(phemex, "_get", return_value=payload):
            out = phemex.list_products()
        self.assertEqual([p["symbol"] for p in out], ["BTCUSDT"],
                         "USDC-settled and delisted contracts must be excluded")


class RankTest(unittest.TestCase):
    def _patched(self, tickers, listed=("BTCUSDT", "ETHUSDT")):
        def fake(path, **kw):
            if path.startswith("/public/products"):
                return {"data": {"perpProductsV2": [
                    {"symbol": s, "settleCurrency": "USDT", "quoteCurrency": "USDT",
                     "contractUnderlyingAssets": s[:-4], "status": "Listed"}
                    for s in listed]}}
            return {"result": tickers}
        return mock.patch.object(phemex, "_get", side_effect=fake)

    def test_ranked_descending_by_turnover(self):
        with self._patched([{"symbol": "ETHUSDT", "turnoverRv": "50"},
                            {"symbol": "BTCUSDT", "turnoverRv": "350"}]):
            r = phemex.rank_by_volume()
        self.assertEqual(r, [("BTCUSDT", 350.0), ("ETHUSDT", 50.0)])

    def test_unlisted_ticker_symbols_are_ignored(self):
        """The ticker feed carries contracts we do not trade; ranking them would
        admit a symbol with no product definition."""
        with self._patched([{"symbol": "BTCUSDT", "turnoverRv": "350"},
                            {"symbol": "GHOSTUSDT", "turnoverRv": "999"}]):
            r = phemex.rank_by_volume()
        self.assertEqual([s for s, _ in r], ["BTCUSDT"])

    def test_malformed_turnover_is_counted_not_crashed(self):
        with self._patched([{"symbol": "BTCUSDT", "turnoverRv": "350"},
                            {"symbol": "ETHUSDT", "turnoverRv": None}]):
            r = phemex.rank_by_volume()
        self.assertEqual(len(r), 1)
        self.assertEqual(phemex.LAST_RANK_HEALTH["failed"], 1)


class CandleTest(unittest.TestCase):
    def test_forming_candle_is_never_returned(self):
        """A forming bar has a moving high/low/close. Admitting one lets an
        engine confirm structure against a bar that has not finished."""
        now = int(time.time())
        gran = 86400
        forming = now - now % gran            # current, still-open bucket
        payload = {"data": {"rows": _rows(forming - gran * 3, gran, 4)}}
        with mock.patch.object(phemex, "_get", return_value=payload):
            out = phemex.fetch_candles("BTCUSDT", "1D", forming - gran * 3, now)
        self.assertTrue(all(c["open_ts"] < forming for c in out),
                        "a forming bucket leaked into the result")

    def test_rows_are_deduped_and_ascending(self):
        now = int(time.time())
        gran = 86400
        end = now - now % gran
        start = end - gran * 5
        dupes = {"data": {"rows": _rows(start, gran, 4) + _rows(start, gran, 4)}}
        with mock.patch.object(phemex, "_get", return_value=dupes):
            out = phemex.fetch_candles("BTCUSDT", "1D", start, end)
        stamps = [c["open_ts"] for c in out]
        self.assertEqual(len(stamps), len(set(stamps)), "duplicate open_ts")
        self.assertEqual(stamps, sorted(stamps), "not ascending")

    def test_field_mapping_matches_the_row_layout(self):
        """Row is [ts, res, lastClose, open, high, low, close, vol] — the third
        element is the PREVIOUS close, not this bar's open. Getting this wrong
        shifts every candle by one bar."""
        now = int(time.time())
        gran = 86400
        end = now - now % gran
        row = [end - gran, gran, "999", "100", "110", "90", "105", "42"]
        with mock.patch.object(phemex, "_get", return_value={"data": {"rows": [row]}}):
            out = phemex.fetch_candles("BTCUSDT", "1D", end - gran * 2, end)
        self.assertEqual(out[0], {"open_ts": end - gran, "open": "100",
                                  "high": "110", "low": "90", "close": "105",
                                  "volume": "42"})

    def test_no_forward_progress_terminates(self):
        """A venue that keeps returning the same first row must not spin."""
        now = int(time.time())
        gran = 86400
        end = now - now % gran
        stuck = {"data": {"rows": [[end - gran * 50, gran, "1", "1", "1", "1", "1", "1"]]}}
        calls = []

        def fake(path, **kw):
            calls.append(path)
            if len(calls) > 20:
                self.fail("fetch_candles did not terminate")
            return stuck

        with mock.patch.object(phemex, "_get", side_effect=fake):
            phemex.fetch_candles("BTCUSDT", "1D", end - gran * 100, end)
        self.assertLessEqual(len(calls), 20)

    def test_unknown_timeframe_is_refused(self):
        with self.assertRaises(ValueError):
            phemex.fetch_candles("BTCUSDT", "3m", 0, 1)

    def test_serves_4h_natively(self):
        """The venue CAN serve 4H directly, unlike Coinbase. The importer still
        aggregates 4H on both venues on purpose — see importer.native_tfs — so
        this records a capability, not the path we take."""
        self.assertIn("4H", phemex.NATIVE_TFS)


class SafetyTest(unittest.TestCase):
    def test_module_holds_no_credentials_and_cannot_trade(self):
        """Market data only. Key handling is the operator's, in OS credential
        storage; nothing here signs a request or places an order."""
        with open(phemex.__file__, encoding="utf-8") as fh:
            src = fh.read().lower()
        for forbidden in ("api_key", "apikey", "secret", "hmac", "signature",
                          "place_order", "/orders"):
            self.assertNotIn(forbidden, src, f"{forbidden!r} must not appear here")

    def test_retry_gives_up_rather_than_looping(self):
        def boom(req, timeout=None):
            raise urllib.error.HTTPError("http://x", 503, "e", {}, None)
        with mock.patch.object(phemex.urllib.request, "urlopen", boom), \
             mock.patch.object(phemex.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                phemex._get("/x", retries=2)

    def test_client_error_is_not_retried(self):
        calls = []

        def boom(req, timeout=None):
            calls.append(1)
            raise urllib.error.HTTPError("http://x", 400, "e", {}, None)
        with mock.patch.object(phemex.urllib.request, "urlopen", boom), \
             mock.patch.object(phemex.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                phemex._get("/x")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()


class ListingGapTest(unittest.TestCase):
    """A symbol listed after the requested start must still backfill.

    v1 broke out of the fetch loop on the first empty window, so any coin
    listed after that window got ZERO daily candles — and daily is what the
    history gate counts, so the symbol stayed WARMING forever (DEXEUSDT,
    2026-07-29: 1D=0 while 1H=4320).
    """

    def test_empty_leading_windows_are_skipped_not_fatal(self):
        gran = 86400
        now = int(time.time())
        end = now - now % gran
        start = end - gran * 2500          # 3 windows back
        listed_at = end - gran * 300       # listed inside the LAST window
        calls = []

        def fake(path, **kw):
            calls.append(path)
            frm = int(path.split("&from=")[1].split("&")[0])
            to = int(path.split("&to=")[1].split("&")[0])
            rows = [r for r in _rows(listed_at, gran, 300) if frm <= r[0] < to]
            return {"data": {"rows": rows}}

        with mock.patch.object(phemex, "_get", side_effect=fake):
            out = phemex.fetch_candles("NEWUSDT", "1D", start, end)

        self.assertGreater(len(out), 0, "listing-date gap swallowed all candles")
        self.assertGreater(len(calls), 1, "should have probed past the empty span")
        self.assertTrue(all(c["open_ts"] >= listed_at for c in out))

    def test_all_empty_still_terminates(self):
        gran = 86400
        now = int(time.time())
        end = now - now % gran
        calls = []

        def fake(path, **kw):
            calls.append(1)
            if len(calls) > 40:
                self.fail("did not terminate on a fully empty range")
            return {"data": {"rows": []}}

        with mock.patch.object(phemex, "_get", side_effect=fake):
            out = phemex.fetch_candles("GHOSTUSDT", "1D", end - gran * 3000, end)
        self.assertEqual(out, [])
        self.assertLessEqual(len(calls), 40)
