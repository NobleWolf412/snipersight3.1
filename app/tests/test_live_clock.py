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
             patch("engine.manual.unresolved", return_value={}):
            self.assertEqual(live.cycle(_Connection(), Mock()), (0, []))

        self.assertEqual(calls, [("TESTUSDT", "5m", 0, 599, 599)])
