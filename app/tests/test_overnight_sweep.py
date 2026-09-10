"""Behavioural pins for the 2026-09-10 sweep — the parts nothing else tested.

Every test runs against a scratch store or a stubbed process; nothing here
touches app/data, wakes the live scanner, or runs a cycle.
"""
import json
import tempfile
import threading
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import live
import server
from engine import quality, risk, store


class NapUntilWoken(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wake = Path(self.tmp.name) / "scan-request"

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_full_nap_returns_false_and_leaves_nothing_behind(self):
        t0 = time.monotonic()
        self.assertFalse(live.nap_until_woken(0.3, self.wake, tick=0.05))
        self.assertGreaterEqual(time.monotonic() - t0, 0.25)
        self.assertFalse(self.wake.exists())

    def test_a_request_ends_the_nap_early_and_is_consumed(self):
        threading.Timer(0.15, self.wake.touch).start()
        t0 = time.monotonic()
        self.assertTrue(live.nap_until_woken(5.0, self.wake, tick=0.05))
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertFalse(self.wake.exists(), "one press must mean one cycle")

    def test_a_request_already_waiting_ends_the_nap_at_once(self):
        self.wake.touch()
        self.assertTrue(live.nap_until_woken(5.0, self.wake, tick=0.05))


class CheckNow(unittest.TestCase):
    """POST /api/scan owns no cycle while a scanner process exists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wake = Path(self.tmp.name) / "scan-request"
        server._scan.update(running=False, woken_cycles=None, detail="")
        self.stack = [
            mock.patch.object(live, "WAKE_REQUEST", self.wake),
            mock.patch.object(live, "cycle", side_effect=AssertionError(
                "a cycle ran inside the API server")),
        ]
        for p in self.stack:
            p.start()

    def tearDown(self):
        for p in self.stack:
            p.stop()
        server._scan.update(running=False, woken_cycles=None, detail="")
        self.tmp.cleanup()

    def _status(self, state, pid=4242, cycles=7, stage="import"):
        return {"state": state, "age_s": 5, "stage": stage, "pid": pid,
                "cycles": cycles}

    def test_a_scanning_scanner_is_woken_not_duplicated(self):
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("SCANNING")), \
             mock.patch.object(server, "_pid_alive", return_value=True):
            out = server.scan_now(mock.Mock())
        self.assertTrue(out["ok"])
        self.assertFalse(out["ran_here"])
        self.assertTrue(self.wake.exists())
        self.assertTrue(server._scan["running"], "the button needs a transition")

    def test_a_stale_heartbeat_with_a_live_pid_is_still_woken(self):
        """STALE is 'busy or napping', never 'gone'. The old branch read a
        95 s heartbeat as absence and ran a second cycle here — the exact
        concurrent-cycle fault the wake file exists to prevent."""
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("STALE")), \
             mock.patch.object(server, "_pid_alive", return_value=True):
            out = server.scan_now(mock.Mock())
        self.assertFalse(out["ran_here"])
        self.assertTrue(self.wake.exists())

    def test_no_scanner_process_means_the_server_runs_the_pass(self):
        ran = threading.Event()
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("STALE", pid=1)), \
             mock.patch.object(server, "_pid_alive", return_value=False), \
             mock.patch.object(live, "cycle",
                               side_effect=lambda *a, **k: (ran.set(), (0, []))[1]), \
             mock.patch.object(server.store, "connect",
                               return_value=mock.MagicMock()):
            out = server.scan_now(mock.Mock())
            self.assertTrue(out["ran_here"])
            self.assertTrue(ran.wait(5), "the bare-server path did not run a cycle")
        self.assertFalse(self.wake.exists())

    def test_the_woken_pass_reports_done_when_the_cycle_counter_moves(self):
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("SCANNING", cycles=7)), \
             mock.patch.object(server, "_pid_alive", return_value=True):
            server.scan_now(mock.Mock())
            self.assertTrue(server.scan_state()["running"])
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("SCANNING", cycles=8)), \
             mock.patch.object(server, "_pid_alive", return_value=True):
            state = server.scan_state()
        self.assertFalse(state["running"])
        self.assertIn("cycle 8", state["detail"])

    def test_a_scanner_that_dies_after_the_press_says_so(self):
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("SCANNING")), \
             mock.patch.object(server, "_pid_alive", return_value=True):
            server.scan_now(mock.Mock())
        with mock.patch.object(server, "_scanner_status",
                               return_value=self._status("STALE")), \
             mock.patch.object(server, "_pid_alive", return_value=False):
            state = server.scan_state()
        self.assertFalse(state["running"])
        self.assertIn("went away", state["detail"])


class IntegrityCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "s.db"
        self.con = store.connect(self.db)
        server._integrity.update(value=None, checked_at=0, running=False)

    def tearDown(self):
        self.con.close()
        server._integrity.update(value=None, checked_at=0, running=False)
        self.tmp.cleanup()

    def test_a_small_store_is_checked_on_the_request_and_then_cached(self):
        with mock.patch.object(server.store, "DB_PATH", self.db):
            self.assertEqual(server.db_integrity(self.con), "ok")
            # A cache hit never touches the connection it is handed.
            untouched = mock.Mock()
            untouched.execute.side_effect = AssertionError("quick_check re-ran")
            self.assertEqual(server.db_integrity(untouched), "ok")
            # ...and deep=1 does, on that connection.
            self.assertEqual(server.db_integrity(self.con, deep=True), "ok")

    def test_a_big_store_reports_checking_then_the_answer(self):
        with mock.patch.object(server.store, "DB_PATH", self.db), \
             mock.patch.object(server, "INTEGRITY_SYNC_MAX_BYTES", 0):
            first = server.db_integrity(self.con)
            self.assertEqual(first, "checking")
            for _ in range(100):
                if server._integrity["value"]:
                    break
                time.sleep(0.05)
            self.assertEqual(server.db_integrity(self.con), "ok")

    def test_a_background_failure_cannot_wedge_checking_forever(self):
        with mock.patch.object(server.store, "DB_PATH", self.db), \
             mock.patch.object(server, "INTEGRITY_SYNC_MAX_BYTES", 0), \
             mock.patch.object(server.store, "connect",
                               side_effect=RuntimeError("database is locked")):
            self.assertEqual(server.db_integrity(self.con), "checking")
            for _ in range(100):
                if not server._integrity["running"]:
                    break
                time.sleep(0.05)
        self.assertFalse(server._integrity["running"])
        self.assertIn("check failed", server._integrity["value"])

    def test_checking_is_unknown_not_degraded(self):
        """The first poll after a boot must not paint the chip amber for a
        verdict nobody has reached; the field itself says 'checking'."""
        with mock.patch.object(server, "db_integrity", return_value="checking"), \
             mock.patch.object(server.store, "connect", return_value=self.con), \
             mock.patch.object(server.universe, "scan_symbols", return_value=[]):
            out = server.health()
        self.assertEqual(out["database"], "checking")
        self.assertEqual(out["status"], "OK")


class StalenessFloor(unittest.TestCase):
    """quality-v0.5: a feed imported once per cycle is not stale mid-cycle."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "q.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _series(self, sym, tf, sec, newest_close_age):
        now = 10 ** 9
        last_open = now - newest_close_age - sec
        for i in range(3):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sym, tf, last_open - (2 - i) * sec, "1", "1", "1", "1", "1",
                 "coinbase", 1))
        self.con.commit()
        return now

    def _codes(self, sym, now):
        with mock.patch("engine.universe.current_symbols", return_value=[sym]):
            return {c["code"] for c in quality.audit_market_inputs(self.con, sym, now)}

    def test_eleven_minutes_on_a_five_minute_series_is_not_stale(self):
        now = self._series("BTCUSDT", "5m", 300, 11 * 60)
        self.assertNotIn("STALE_SERIES", self._codes("BTCUSDT", now))

    def test_the_floor_is_thirty_minutes(self):
        now = self._series("BTCUSDT", "5m", 300, 31 * 60)
        self.assertIn("STALE_SERIES", self._codes("BTCUSDT", now))

    def test_two_bars_still_rule_on_slow_timeframes(self):
        now = self._series("BTCUSDT", "1H", 3600, 121 * 60)
        self.assertIn("STALE_SERIES", self._codes("BTCUSDT", now))
        now = self._series("ETHUSDT", "1H", 3600, 119 * 60)
        self.assertNotIn("STALE_SERIES", self._codes("ETHUSDT", now))


class DailyBudget(unittest.TestCase):
    def test_it_settles_on_the_utc_day_and_day_open_equity(self):
        day = int(time.time()) // 86_400 * 86_400
        journal = [{"ts": day - 1, "pnl_usd": -500},      # yesterday, ignored
                   {"ts": day + 60, "pnl_usd": -120.5},
                   {"ts": day + 120, "pnl_usd": 20}]
        gates = risk.gates_for_mode(risk.AutomationMode.PAPER)
        out = server._daily_budget(journal, Decimal("9899.50"), gates)
        self.assertEqual(out["today_pnl_usd"], "-100.50")
        self.assertEqual(out["day_open_equity_usd"], "10000.00")
        self.assertEqual(out["lost_today_usd"], "100.50")
        budget = Decimal("10000.00") * gates["daily_loss_limit_pct"]
        self.assertEqual(out["budget_usd"], str(budget.quantize(Decimal("0.01"))))
        self.assertEqual(out["remaining_usd"],
                         str((budget - Decimal("100.50")).quantize(Decimal("0.01"))))
        self.assertEqual(out["day_start_ts"], day)

    def test_a_winning_day_leaves_the_whole_budget(self):
        day = int(time.time()) // 86_400 * 86_400
        gates = risk.gates_for_mode(risk.AutomationMode.PAPER)
        out = server._daily_budget([{"ts": day + 5, "pnl_usd": 300}],
                                   Decimal("10300"), gates)
        self.assertEqual(out["lost_today_usd"], "0.00")
        self.assertEqual(out["remaining_usd"], out["budget_usd"])

    def test_the_portfolio_reads_the_same_helper_the_panel_reads(self):
        src = Path(server.__file__).read_text(encoding="utf-8")
        self.assertIn('"daily_loss": _daily_budget(', src)
        shell = (Path(server.__file__).parent / "static" / "shell.js").read_text(
            encoding="utf-8")
        self.assertIn("p.daily_loss", shell)
        self.assertNotIn("midnight.setHours(0, 0, 0, 0);\n    const cut", shell,
                         "the panel re-derives today's loss from local midnight")


class StoredPriceText(unittest.TestCase):
    """importer-v0.8: the stored spelling carries no trailing zeros, so a lone
    20-decimal venue bar cannot set a series' tick to 1e-20 forever."""

    def test_trailing_fractional_zeros_are_dropped(self):
        from engine import importer
        self.assertEqual(importer.price_text(Decimal("0.20036000000000000000")),
                         "0.20036")
        self.assertEqual(importer.price_text("78262.30"), "78262.3")
        self.assertEqual(importer.price_text(Decimal("100.00")), "100")
        self.assertEqual(importer.price_text("0.0000034673"), "0.0000034673")

    def test_no_exponent_ever(self):
        from engine import importer
        for raw in ("1E+2", "1e-7", "0E-8"):
            self.assertNotRegex(importer.price_text(Decimal(raw)), r"[eE]")

    def test_the_value_is_unchanged(self):
        from engine import importer
        for raw in ("0.20036000000000000000", "78262.30", "100.00", "0.5"):
            self.assertEqual(Decimal(importer.price_text(raw)), Decimal(raw))

    def test_a_clean_bar_no_longer_inherits_a_dirty_tick(self):
        """Once the text is clean the running maximum in quote_ticks is
        driven by real precision, not by one padded row."""
        from engine import importer, swings
        dirty = [{"open": "0.2003", "high": "0.2005", "low": "0.2001", "close": "0.20036000000000000000"}]
        clean = [{k: importer.price_text(v) for k, v in dirty[0].items()}]
        self.assertEqual(swings.quote_ticks(dirty)[-1], Decimal("1E-20"))
        self.assertEqual(swings.quote_ticks(clean)[-1], Decimal("0.00001"))


class VolumeProfileBins(unittest.TestCase):
    def test_a_close_on_a_bin_edge_is_in_the_bin_that_starts_there(self):
        from engine import volprofile
        step = Decimal("0.1")
        # 0.3 // 0.1 is 2.0 in floating point; the record said bin 2.
        self.assertEqual(volprofile.bin_index("0.3", step), 3)
        self.assertEqual(volprofile.bin_index("0.29999", step), 2)
        self.assertEqual(volprofile.bin_index(Decimal("100"), Decimal("0.5")), 200)


class ServedShapes(unittest.TestCase):
    """The fields the cockpit reads instead of re-deriving, present and
    consistent on the served payloads. Read-only GETs against the app."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        cls.client = TestClient(server.app)

    def test_trade_config_serves_the_reachable_budget(self):
        d = self.client.get("/api/trade-config?symbol=BTCUSDT").json()
        self.assertIn("effective_max_total_risk_pct", d)
        self.assertLessEqual(d["effective_max_total_risk_pct"], d["max_total_risk_pct"])
        self.assertAlmostEqual(
            d["effective_max_total_risk_pct"],
            min(d["max_total_risk_pct"], d["risk_pct"] * d["max_concurrent"]))
        self.assertNotIn("venue_fallback", d)
        self.assertIn("venue_fallback",
                      self.client.get("/api/trade-config?symbol=NOPE-XYZ").json())

    def test_portfolio_serves_committed_risk_and_the_daily_budget(self):
        d = self.client.get("/api/portfolio").json()
        self.assertGreaterEqual(float(d["committed_risk_usd"]), float(d["open_risk_usd"]))
        for k in ("day_start_ts", "day_open_equity_usd", "lost_today_usd",
                  "budget_usd", "remaining_usd"):
            self.assertIn(k, d["daily_loss"])
        self.assertIn("operator_closed_pricing_mixed", d)

    def test_operations_names_filled_and_committed_risk_apart(self):
        a = self.client.get("/api/operations").json()["account"]
        self.assertIn("open_risk_usd", a)
        self.assertIn("committed_risk_usd", a)
        self.assertGreaterEqual(Decimal(a["committed_risk_usd"]),
                                Decimal(a["open_risk_usd"]))

    def test_telemetry_serves_risk_reasons_at_the_top_level(self):
        d = self.client.get("/api/setup-telemetry?limit=5").json()
        self.assertIn("risk_reasons", d)
        self.assertNotIn("risk_reasons", d["funnel"])
        for code in d["risk_reasons"]:
            self.assertNotIn("(", code, "parameters must be stripped for the lexicon")


class OperatorCloseReachesNextAction(unittest.TestCase):
    """opportunity-v0.7: a position the operator closed by hand is CLOSED in
    the read model Next Action reads, not only in the portfolio."""

    def setUp(self):
        from engine import manual, setups
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "o.db")
        store.start_baseline(self.con, started_at=1000, label="test")
        self.sid = "BTCUSDT|1H|PULLBACK|BTCUSDT|1H|DEMAND|5000|" + setups.SETUP_VERSION
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind="setup", market_time=5000,
            confirmed_at=8600, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": self.sid, "state": "VALIDATED", "strategy": "PULLBACK",
                     "direction": "LONG", "entry": "100", "sl": "95", "tp": "110",
                     "rr": "2", "rank": 50, "expires_at_ts": 10 ** 9})
        self.manual = manual
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _state(self):
        from engine import opportunities
        rows = opportunities.list_candidates(self.con, now=20000)
        return next(r["state"] for r in rows
                    if r["setup"]["setup_id"] == self.sid)

    def test_a_hand_close_after_the_setup_reads_closed(self):
        before = self._state()
        self.assertNotEqual(before, "CLOSED")
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind=self.manual.OVERRIDE_KIND,
            market_time=9000, confirmed_at=9000,
            algo_version=self.manual.MANUAL_VERSION,
            payload={"setup_id": self.sid, "source": "OPERATOR",
                     "event": "CLOSED_EARLY", "symbol": "BTCUSDT", "tf": "1H"})
        self.con.commit()
        self.assertEqual(self._state(), "CLOSED")

    def test_a_closed_zone_stays_closed_like_the_portfolio_says(self):
        """The portfolio suppresses a hand-closed zone for the life of the
        zone (manual.setup_zone_key); this model must agree or the exposure
        chip says "room" while Next Action says "manage". An older close
        therefore still closes a later re-validation of the same zone."""
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind=self.manual.OVERRIDE_KIND,
            market_time=2000, confirmed_at=2000,
            algo_version=self.manual.MANUAL_VERSION,
            payload={"setup_id": self.sid, "source": "OPERATOR",
                     "event": "CLOSED_EARLY", "symbol": "BTCUSDT", "tf": "1H"})
        self.con.commit()
        self.assertEqual(self._state(), "CLOSED")

    def test_an_adopted_position_is_still_open(self):
        """ADOPTED moves custody to the operator; the position has not
        closed, and "a position is open" stays true of it."""
        store.insert_fact(
            self.con, symbol="BTCUSDT", tf="1H", kind=self.manual.OVERRIDE_KIND,
            market_time=9000, confirmed_at=9000,
            algo_version=self.manual.MANUAL_VERSION,
            payload={"setup_id": self.sid, "source": "OPERATOR",
                     "event": "ADOPTED", "symbol": "BTCUSDT", "tf": "1H"})
        self.con.commit()
        self.assertNotEqual(self._state(), "CLOSED")


if __name__ == "__main__":
    unittest.main()
