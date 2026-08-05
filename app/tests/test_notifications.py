"""Notification discipline — a toast is a claim that something is actionable NOW.

Three regressions are pinned here, all measured on the live store 2026-07-29:

  · the announce path fired on new fact ROWS, so onboarding a symbol replayed
    years of history as live alerts (87 in one cycle, newest dated 2025-01);
  · the drift monitor compared live price against a candle with no staleness
    check, so a symbol whose imports lagged alerted every 15 minutes forever
    (COTI-USD and EUL-USD, reference closes 2.8 and 3.5 days old);
  · every price fetch was hard-wired to Coinbase, so once the traded universe
    became Phemex perps the monitor was 100% blind and merely noisy about it.
"""
import inspect
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import live
from engine import (breakout, execsim, marketdata, phemex, scalein, setups,
                    store, trend)


class _Log:
    """Captures what the loop said it did — suppression must be audible."""

    def __init__(self):
        self.lines = []

    def _rec(self, msg):
        self.lines.append(str(msg))

    info = warning = error = debug = _rec

    def saw(self, needle):
        return any(needle in line for line in self.lines)


class TempStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class TestAnnounceRecency(TempStore):
    """cycle() must announce events, not rows."""

    def _setup_fact(self, *, tf, confirmed_at, state="VALIDATED",
                    version=None, strategy="PULLBACK"):
        """A setup fact under a TRADED version by default.

        The version is a parameter rather than a constant because it is now
        load-bearing: `announceable` only surfaces engines the book actually
        trades, so a fixture pinned to an invented tag would test the filter
        against a case that can never occur and miss the one that did.
        """
        version = version or setups.SETUP_VERSION
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf=tf, kind="setup",
            market_time=confirmed_at, confirmed_at=confirmed_at,
            algo_version=version, payload={
                "setup_id": f"BTCUSDT|{tf}|{strategy}|{confirmed_at}",
                "state": state, "strategy": strategy, "direction": "LONG",
                "entry": "100", "sl": "99", "tp": "104", "rr": "4", "rank": 50})
        self.con.commit()

    def _fired(self, now):
        """Drive THE filter — the real one, not a copy of it.

        This used to re-implement the gates inline, and that is precisely how
        the not-enabled-engine defect survived a passing suite: the mirror had
        no version gate, so it could not fail when the code needed one. A test
        that restates the logic it is testing proves the restatement.
        """
        baseline_start = store.get_active_baseline(self.con)["started_at"]
        return live.announceable(self.con, 0, now, baseline_start)

    def test_backfilled_history_is_not_announced(self):
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 86400)
        self._setup_fact(tf="1D", confirmed_at=now - 400 * 86400)   # 2025-ish
        self.assertEqual(self._fired(now), [],
                         "a setup from over a year ago must never toast")

    def test_pre_baseline_setup_is_not_announced(self):
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 3600)
        self._setup_fact(tf="1H", confirmed_at=now - 7200)   # before the window
        self.assertEqual(self._fired(now), [])

    def test_current_setup_is_announced(self):
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 86400)
        self._setup_fact(tf="1H", confirmed_at=now - 60)
        self.assertEqual(len(self._fired(now)), 1)

    def test_lateness_is_measured_in_the_setups_own_timeframe(self):
        """3 hours late is history on 15m and perfectly fresh on 1D."""
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 30 * 86400)
        self._setup_fact(tf="15m", confirmed_at=now - 3 * 3600)
        self._setup_fact(tf="1D", confirmed_at=now - 3 * 3600)
        fired = self._fired(now)
        self.assertEqual([tf for _, tf, _ in fired], ["1D"])


class TestOnlyTradedEnginesAnnounce(TempStore):
    """A toast claims something is ACTIONABLE. An engine that trades nothing
    can never produce one.

    The defect, measured on the live scanner log 2026-08-05: 17 alerts reading
    `SETUP FIRED ◉ TREND_CONTINUATION SHORT — GIGGLEUSDT 15m`, for a playbook
    whose own docstring opens by saying it trades nothing and whose grade is
    -0.1500 R over 2,816 trades with the interval ENTIRELY below zero. The
    announce query asked for `kind='setup'` and every engine that writes one
    landed in it. The gates it did have were about time and state; none was
    about which engine.
    """

    def _fact(self, version, strategy, now):
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind="setup",
            market_time=now - 60, confirmed_at=now - 60,
            algo_version=version, payload={
                "setup_id": f"BTCUSDT|1H|{strategy}|{now}|{version}",
                "state": "VALIDATED", "strategy": strategy,
                "direction": "LONG", "entry": "100", "sl": "99", "tp": "104",
                "rr": "4", "rank": 0})
        self.con.commit()

    def _fired(self, now):
        return live.announceable(
            self.con, 0, now, store.get_active_baseline(self.con)["started_at"])

    def test_the_not_enabled_playbooks_never_announce(self):
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 86400)
        self._fact(trend.TREND_VERSION, "TREND_CONTINUATION", now)
        self._fact(breakout.BREAKOUT_VERSION, "BREAKOUT_RETEST", now)
        self.assertEqual(
            self._fired(now), [],
            "an engine that execsim does not execute must never toast — the "
            "operator would be alerted to trade something ungraded")

    def test_the_traded_playbooks_still_announce(self):
        """The gate must not silence the book it exists to protect."""
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 86400)
        self._fact(setups.SETUP_VERSION, "REVERSAL", now)
        self.assertEqual(len(self._fired(now)), 1)

    def test_the_gate_is_the_simulators_own_definition(self):
        """One authority. If execsim starts executing a new plan source, the
        notifier follows in the same commit rather than a version later."""
        self.assertEqual(set(execsim.plan_versions()),
                         {setups.SETUP_VERSION, scalein.SCALE_VERSION})
        src = inspect.getsource(live.announceable)
        self.assertIn("plan_versions", src)

    def test_suppression_is_audible(self):
        """A notifier that swallows silently is indistinguishable from a quiet
        market, and this codebase treats a silent fallback as a bug."""
        now = int(time.time())
        store.start_baseline(self.con, started_at=now - 86400)
        self._fact(trend.TREND_VERSION, "TREND_CONTINUATION", now)
        log = _Log()
        live.announceable(self.con, 0, now,
                          store.get_active_baseline(self.con)["started_at"], log)
        self.assertTrue(log.saw("not-enabled engines"),
                        "dropping an alert must be counted where it can be read")


class TestDriftStaleness(TempStore):
    """Drift must measure the market, not the importer."""

    def _candle(self, symbol, open_ts, close):
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            (symbol, "15m", open_ts, close, close, close, close, "10",
             "phemex-perp", open_ts))
        self.con.commit()

    def setUp(self):
        super().setUp()
        live._drift_alerted.clear()
        live._drift_muted.clear()

    def test_stale_reference_is_muted_and_says_why(self):
        now = int(time.time())
        self._candle("BTCUSDT", now - 3 * 86400, "50000")     # 3 days old
        log = _Log()
        with patch.object(live.universe, "current_symbols", return_value=["BTCUSDT"]), \
             patch.object(live.marketdata, "last_prices", return_value={"BTCUSDT": 64000.0}):
            live.check_drift(self.con, log)
        alerts = self.con.execute(
            "SELECT COUNT(*) FROM facts WHERE kind='alert'").fetchone()[0]
        self.assertEqual(alerts, 0, "a 28% 'drift' against a 3-day-old close is import lag")
        self.assertTrue(log.saw("muted"), "muting must be logged, never silent")
        self.assertTrue(log.saw("IMPORT lag"))

    def test_mute_is_logged_once_per_bucket_not_once_per_poll(self):
        now = int(time.time())
        self._candle("BTCUSDT", now - 3 * 86400, "50000")
        log = _Log()
        with patch.object(live.universe, "current_symbols", return_value=["BTCUSDT"]), \
             patch.object(live.marketdata, "last_prices", return_value={"BTCUSDT": 64000.0}):
            for _ in range(5):                    # five polls inside one bucket
                live.check_drift(self.con, log)
        self.assertEqual(sum("muted for BTCUSDT" in ln for ln in log.lines), 1,
                         "the fix must not trade an alert flood for a log flood")

    def test_fresh_reference_still_alerts(self):
        now = int(time.time())
        self._candle("BTCUSDT", now - 900, "50000")           # last closed bar
        log = _Log()
        with patch.object(live.universe, "current_symbols", return_value=["BTCUSDT"]), \
             patch.object(live.marketdata, "last_prices", return_value={"BTCUSDT": 53000.0}), \
             patch.object(live.notify, "toast", return_value=True):
            live.check_drift(self.con, log)
        rows = self.con.execute(
            "SELECT payload FROM facts WHERE kind='alert'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0][0])["drift_pct"], "6.00")

    def test_blindness_is_reported_not_swallowed(self):
        """No live price for a symbol is a monitoring gap and must be said so."""
        now = int(time.time())
        self._candle("BTCUSDT", now - 900, "50000")
        log = _Log()
        with patch.object(live.universe, "current_symbols", return_value=["BTCUSDT"]), \
             patch.object(live.marketdata, "last_prices", return_value={}):
            live.check_drift(self.con, log)
        self.assertTrue(log.saw("drift monitor blind for 1/1"))


class TestPriceRoutingByVenue(unittest.TestCase):
    """The reason drift went 100% blind: perp symbols sent to a spot endpoint."""

    def test_perps_go_to_phemex_not_coinbase(self):
        def boom(*a, **k):
            raise AssertionError("a perp must never be fetched from Coinbase")
        with patch.object(phemex, "last_prices", return_value={"BTCUSDT": 64000.0}):
            out = marketdata.last_prices(["BTCUSDT"], opener=boom)
        self.assertEqual(out, {"BTCUSDT": 64000.0})

    def test_spot_still_uses_coinbase(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"price":"123.45","time":"now"}'
        out = marketdata.last_prices(["BTC-USD"], opener=lambda *a, **k: Response())
        self.assertEqual(out["BTC-USD"], 123.45)

    def test_mixed_universe_routes_each_symbol_to_its_own_venue(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"price":"10","time":"now"}'
        with patch.object(phemex, "last_prices", return_value={"ETHUSDT": 3000.0}):
            out = marketdata.last_prices(["ETHUSDT", "BTC-USD"],
                                         opener=lambda *a, **k: Response())
        self.assertEqual(out, {"ETHUSDT": 3000.0, "BTC-USD": 10.0})

    def test_unpriceable_symbol_is_absent_never_zero(self):
        """A fabricated price would produce drift against a number that never
        traded — worse than reporting nothing."""
        with patch.object(phemex, "last_prices", return_value={}):
            out = marketdata.last_prices(["BTCUSDT"])
        self.assertNotIn("BTCUSDT", out)

    def test_ticker_endpoint_reports_perps_ok(self):
        with patch.object(phemex, "last_prices", return_value={"BTCUSDT": 64000.0}):
            out = marketdata.fetch_tickers(["BTCUSDT"])
        self.assertEqual(out["BTCUSDT"]["status"], "OK")
        self.assertEqual(out["BTCUSDT"]["price"], 64000.0)

    def test_ticker_endpoint_still_reports_degraded_honestly(self):
        with patch.object(phemex, "last_prices", side_effect=RuntimeError("down")):
            out = marketdata.fetch_tickers(["BTCUSDT"])
        self.assertEqual(out["BTCUSDT"]["status"], "DEGRADED")


class TestPhemexLastPrices(unittest.TestCase):
    def test_uses_last_traded_price_not_mark_price(self):
        """Mark price is an index-anchored fair value. Comparing it against a
        traded close reports drift that never happened."""
        payload = {"result": [{"symbol": "BTCUSDT", "closeRp": "64352",
                               "markPriceRp": "64354.9", "indexPriceRp": "64383"}]}
        with patch.object(phemex, "_get", return_value=payload):
            self.assertEqual(phemex.last_prices(["BTCUSDT"]), {"BTCUSDT": 64352.0})

    def test_one_call_covers_every_symbol(self):
        calls = []

        def spy(path, **k):
            calls.append(path)
            return {"result": [{"symbol": "BTCUSDT", "closeRp": "1"},
                               {"symbol": "ETHUSDT", "closeRp": "2"}]}
        with patch.object(phemex, "_get", spy):
            out = phemex.last_prices(["BTCUSDT", "ETHUSDT"])
        self.assertEqual(len(calls), 1, "batched: one request, not one per symbol")
        self.assertEqual(out, {"BTCUSDT": 1.0, "ETHUSDT": 2.0})

    def test_unparseable_row_is_skipped_not_defaulted(self):
        payload = {"result": [{"symbol": "BTCUSDT", "closeRp": None},
                              {"symbol": "ETHUSDT", "closeRp": "2"}]}
        with patch.object(phemex, "_get", return_value=payload):
            self.assertEqual(phemex.last_prices(), {"ETHUSDT": 2.0})


if __name__ == "__main__":
    unittest.main()
