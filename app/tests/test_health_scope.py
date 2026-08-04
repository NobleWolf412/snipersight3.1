"""Health is about the data the app undertook to keep current.

`/api/health` computed `status` over EVERY series in the candles table:

    "status": "OK" if integrity == "ok" and not any(s["stale"] for s in series)

The store holds candles for far more symbols than the scanner refreshes — the
chart picker offers 48 outside the scan universe, and opening one fetches
candles that then sit there ageing forever, by design. Measured 4 Aug 2026:
227 of 419 series were stale and ZERO of them were in the scan universe.

Two consequences, both bad:

  · `status` had been DEGRADED continuously and could never read OK again. A
    status that cannot change is not a status — the operator learns it is
    always amber and stops reading it, which is precisely when it matters.

  · The Diagnose wizard reads this and told the operator to "run a scan to
    re-import". No scan will ever fetch a symbol outside the universe, so the
    one tool whose job is saying what to do was giving an instruction that
    could not succeed, permanently.

These tests pin the scope. They do NOT loosen the check: a stale MAINTAINED
series still degrades, which is the case that means something.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import store


class HealthScopeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _health(self, *, candles, scanned):
        """Run the endpoint against a fabricated store."""
        import server
        for symbol, tf, open_ts in candles:
            self.con.execute(
                "INSERT OR REPLACE INTO candles"
                "(symbol,tf,open_ts,open,high,low,close,volume,source,imported_at) "
                "VALUES(?,?,?,1,1,1,1,1,'test',0)", (symbol, tf, open_ts))
        self.con.commit()
        with mock.patch.object(server.store, "connect", return_value=self.con), \
             mock.patch.object(server.universe, "scan_symbols",
                               return_value=list(scanned)), \
             mock.patch("time.time", return_value=1_000_000):
            return server.health()

    # `now` is 1_000_000; a 1H bar opening at 999_000 closed at 1_002_600 —
    # fresh. One opening at 900_000 closed long ago — stale.
    FRESH, STALE = 999_000, 900_000

    def test_stale_unmaintained_series_do_not_degrade_the_status(self):
        r = self._health(
            candles=[("BTCUSDT", "1H", self.FRESH),      # scanned, current
                     ("AAVE-USD", "1H", self.STALE),     # merely stored, old
                     ("ACH-USD", "1H", self.STALE)],
            scanned=["BTCUSDT"])
        self.assertEqual(r["status"], "OK",
                         "history for symbols nobody scans still degrades the "
                         "status — it can then never read OK")
        self.assertEqual(r["stored_stale_count"], 2)
        self.assertIn("outside the scan universe", r["stored_stale_reason"])

    def test_a_stale_maintained_series_still_degrades(self):
        """The case that means something is not weakened."""
        r = self._health(
            candles=[("BTCUSDT", "1H", self.STALE),
                     ("AAVE-USD", "1H", self.STALE)],
            scanned=["BTCUSDT"])
        self.assertEqual(r["status"], "DEGRADED")
        self.assertEqual([s["symbol"] for s in r["stale_series"]], ["BTCUSDT"],
                         "stale_series must carry only what a scan can fix — "
                         "its consumer turns it into an instruction")

    def test_stale_series_is_actionable_only(self):
        """The wizard turns this list into "run a scan". Everything in it must
        be a symbol a scan actually refreshes."""
        r = self._health(
            candles=[("BTCUSDT", "1H", self.STALE),
                     ("AAVE-USD", "1H", self.STALE),
                     ("ACH-USD", "15m", self.STALE)],
            scanned=["BTCUSDT"])
        for s in r["stale_series"]:
            self.assertTrue(s["maintained"],
                            f"{s['symbol']} is in stale_series but nothing "
                            f"refreshes it — the advice cannot succeed")

    def test_nothing_is_hidden(self):
        """Rescoping must not mean silently dropping the count."""
        r = self._health(
            candles=[("BTCUSDT", "1H", self.FRESH),
                     ("AAVE-USD", "1H", self.STALE)],
            scanned=["BTCUSDT"])
        self.assertEqual(r["stored_stale_count"], 1)
        self.assertTrue(r["stored_stale_reason"])
        # the full picture is still on the payload
        self.assertEqual(len(r["series"]), 2)
        self.assertEqual(r["maintained_series"], 1)

    def test_every_series_says_whether_it_is_maintained(self):
        r = self._health(candles=[("BTCUSDT", "1H", self.FRESH),
                                  ("AAVE-USD", "1H", self.FRESH)],
                         scanned=["BTCUSDT"])
        by = {s["symbol"]: s["maintained"] for s in r["series"]}
        self.assertTrue(by["BTCUSDT"])
        self.assertFalse(by["AAVE-USD"])

    def test_a_clean_store_with_no_history_reads_ok(self):
        r = self._health(candles=[("BTCUSDT", "1H", self.FRESH)],
                         scanned=["BTCUSDT"])
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["stored_stale_count"], 0)
        self.assertIsNone(r["stored_stale_reason"])


if __name__ == "__main__":
    unittest.main()
