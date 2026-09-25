"""A live scan has one clock snapshot from import through quality.

The scan takes several minutes. When import quietly advanced to a later candle
boundary but engines and quality kept the opening timestamp, healthy bars were
called DEVELOPING_CANDLES and 12-18 markets were skipped at once.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import live  # noqa: E402


class _Rows:
    def fetchone(self):
        return (None,)


class _Connection:
    def execute(self, *_args, **_kwargs):
        return _Rows()


class LiveClockContract(unittest.TestCase):
    def test_trial_feed_survives_removal_and_idle_pass_updates_trial(self):
        calls = []
        with patch.object(live.time, "time", return_value=599), \
             patch.object(live.universe, "scan_symbols", return_value=[]), \
             patch.object(live.execsim, "unresolved", return_value={}), \
             patch.object(live, "execution_rebuild_work", return_value={}), \
             patch.object(live.zonestudy, "exists", return_value=True), \
             patch.object(live.zonestudy, "unresolved", return_value=set()), \
             patch.object(live.zonestudy, "run"), \
             patch.object(live.stopstudy, "exists", return_value=True), \
             patch.object(live.stopstudy, "unresolved", return_value=set()), \
             patch.object(live.stopstudy, "run"), \
             patch.object(live.forwardtrial, "exists", return_value=True), \
             patch.object(live.forwardtrial, "unresolved", return_value={("BTCUSDT", "15m")}), \
             patch.object(live.forwardtrial, "run") as run, \
             patch.object(live.simpletrial, "exists", return_value=True), \
             patch.object(live.simpletrial, "unresolved", return_value=set()), \
             patch.object(live.simpletrial, "run"), \
             patch.object(live.importer, "native_tfs", return_value={"5m": 300}), \
             patch.object(live.importer, "backfill", side_effect=lambda *args, **kwargs: calls.append(args[1]) or {"candles": 0, "gaps": 0}), \
             patch.object(live.ingest, "history_floor", return_value=0), \
             patch.object(live.venues, "REFERENCE", {}), \
             patch("engine.manual.unresolved", return_value={}):
            self.assertEqual(live.cycle(_Connection(), Mock()), (0, []))
        self.assertEqual(calls, ["BTCUSDT"])
        run.assert_called_once()

    def test_cycle_passes_its_opening_clock_to_the_importer(self):
        calls = []

        def backfill(_con, symbol, tf, start, end, *, as_of=None):
            calls.append((symbol, tf, start, end, as_of))
            return {"candles": 0, "gaps": 0}

        with patch.object(live.time, "time", return_value=599), \
             patch.object(live.universe, "scan_symbols",
                          return_value=["TESTUSDT"]), \
             patch.object(live.importer, "native_tfs",
                          return_value={"5m": 300}), \
             patch.object(live.importer, "backfill", side_effect=backfill), \
             patch.object(live.ingest, "history_floor", return_value=0), \
             patch.object(live.venues, "REFERENCE", {}), \
             patch.object(live.execsim, "unresolved", return_value={}), \
             patch.object(live, "execution_rebuild_work", return_value={}), \
             patch.object(live.zonestudy, "exists", return_value=True), \
             patch.object(live.zonestudy, "unresolved", return_value=set()), \
             patch.object(live.zonestudy, "run"), \
             patch.object(live.stopstudy, "exists", return_value=True), \
             patch.object(live.stopstudy, "unresolved", return_value=set()), \
             patch.object(live.stopstudy, "run"), \
             patch.object(live.forwardtrial, "exists", return_value=True), \
             patch.object(live.forwardtrial, "unresolved", return_value=set()), \
             patch.object(live.forwardtrial, "run"), \
             patch.object(live.simpletrial, "exists", return_value=True), \
             patch.object(live.simpletrial, "unresolved", return_value=set()), \
             patch.object(live.simpletrial, "run"), \
             patch("engine.manual.unresolved", return_value={}):
            self.assertEqual(live.cycle(_Connection(), Mock()), (0, []))

        self.assertEqual(calls, [("TESTUSDT", "5m", 0, 599, 599)])

    def test_cycle_imports_an_unresolved_trade_after_universe_removal(self):
        calls = []

        def backfill(_con, symbol, tf, start, end, *, as_of=None):
            calls.append((symbol, tf, start, end, as_of))
            return {"candles": 0, "gaps": 0}

        pinned = {("XLMUSDT", "15m"): [
            {"setup_id": "xlm|setup", "event": "FILLED"}]}
        with patch.object(live.time, "time", return_value=599), \
             patch.object(live.universe, "scan_symbols",
                          return_value=["BTCUSDT"]), \
             patch.object(live.execsim, "unresolved", return_value=pinned), \
             patch.object(live, "execution_rebuild_work", return_value={}), \
             patch.object(live.zonestudy, "exists", return_value=True), \
             patch.object(live.zonestudy, "unresolved", return_value=set()), \
             patch.object(live.zonestudy, "run"), \
             patch.object(live.stopstudy, "exists", return_value=True), \
             patch.object(live.stopstudy, "unresolved", return_value=set()), \
             patch.object(live.stopstudy, "run"), \
             patch.object(live.forwardtrial, "exists", return_value=True), \
             patch.object(live.forwardtrial, "unresolved", return_value=set()), \
             patch.object(live.forwardtrial, "run"), \
             patch.object(live.simpletrial, "exists", return_value=True), \
             patch.object(live.simpletrial, "unresolved", return_value=set()), \
             patch.object(live.simpletrial, "run"), \
             patch.object(live.importer, "native_tfs",
                          return_value={"5m": 300}), \
             patch.object(live.importer, "backfill", side_effect=backfill), \
             patch.object(live.ingest, "history_floor", return_value=0), \
             patch.object(live.venues, "REFERENCE", {}), \
             patch("engine.manual.unresolved", return_value={}):
            self.assertEqual(live.cycle(_Connection(), Mock()), (0, []))

        self.assertEqual(
            calls,
            [("BTCUSDT", "5m", 0, 599, 599),
             ("XLMUSDT", "5m", 0, 599, 599)])
