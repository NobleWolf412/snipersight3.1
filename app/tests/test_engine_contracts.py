import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import aggregator, importer, liquidity, store, structure, swings
from validate import bootstrap_mean_ci


def insert_candle(con, tf, ts, o="100", h="102", lo="98", c="100"):
    con.execute(
        "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("BTC-USD", tf, ts, o, h, lo, c, "1", "coinbase", ts + 1))


class EngineStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class TestAggregator(EngineStoreCase):
    def test_only_complete_closed_bucket_is_emitted(self):
        for i in range(4):
            insert_candle(self.con, "1H", i * 3600, o=str(100 + i),
                          h=str(102 + i), lo=str(98 + i), c=str(101 + i))
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 1)
        row = store.get_candles(self.con, "BTC-USD", "4H")[0]
        self.assertEqual(row["open"], "100")
        self.assertEqual(row["high"], "105")
        self.assertEqual(row["low"], "98")
        self.assertEqual(row["close"], "104")

    def test_gap_prevents_aggregate(self):
        for i in (0, 1, 3):
            insert_candle(self.con, "1H", i * 3600)
        with patch("engine.aggregator.time.time", return_value=20000):
            result = aggregator.aggregate(self.con, "BTC-USD", "4H")
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["skipped_incomplete"], 1)


class TestImporter(EngineStoreCase):
    def test_malformed_candle_is_rejected_and_logged_as_gap(self):
        # Coinbase response order: time, low, high, open, close, volume.
        rows = [[0, Decimal("110"), Decimal("100"), Decimal("105"),
                 Decimal("106"), Decimal("1")]]
        with patch("engine.importer._fetch", return_value=rows), \
             patch("engine.importer.time.time", return_value=10000), \
             patch("engine.importer.time.sleep", return_value=None):
            result = importer.backfill(self.con, "BTC-USD", "1H", 0, 3600)
        self.assertEqual(result["bad"], 1)
        self.assertEqual(result["candles"], 0)
        self.assertEqual(result["gaps"], 1)


class TestSwingCausality(unittest.TestCase):
    def _series(self, highs):
        return [{"open_ts": i * 60, "open": "10", "high": str(h),
                 "low": "1", "close": "5", "volume": "1"}
                for i, h in enumerate(highs)]

    def test_right_side_confirmation_is_required(self):
        self.assertEqual(swings.detect_micro(self._series([1, 2, 9, 2])), [])
        found = swings.detect_micro(self._series([1, 2, 9, 2, 1]))
        self.assertEqual([(x["i"], x["type"]) for x in found], [(2, "HIGH")])

    def test_equal_high_tie_is_not_a_swing(self):
        found = swings.detect_micro(self._series([1, 9, 9, 2, 1]))
        self.assertNotIn("HIGH", [x["type"] for x in found])


class TestStructureBreaks(EngineStoreCase):
    def test_wick_does_not_break_but_close_does(self):
        for i in range(22):
            close, high = ("100", "102")
            if i == 19:
                high = "120"                 # wick above the level only
            if i == 20:
                close, high = "111", "112"   # closed displacement
            insert_candle(self.con, "1H", i * 3600, h=high, c=close)
        store.insert_fact(
            self.con, symbol="BTC-USD", tf="1H", kind="swing",
            market_time=10 * 3600, confirmed_at=13 * 3600,
            algo_version=swings.SWING_VERSION,
            payload={"tier": "INTERMEDIATE", "type": "HIGH", "price": "110"})
        structure.run(self.con, "BTC-USD", "1H", 3600)
        rows = store.get_facts(
            self.con, "BTC-USD", "1H", "structure", structure.STRUCTURE_VERSION)
        breaks = [{"market_time": r["market_time"], **json.loads(r["payload"])}
                  for r in rows if json.loads(r["payload"])["event"] != "LABEL"]
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0]["market_time"], 20 * 3600)


class TestLiquidityCanonicalization(EngineStoreCase):
    def test_overlapping_equal_high_cluster_emits_one_pool(self):
        for i in range(24):
            insert_candle(self.con, "1H", i * 3600, h="101", lo="91", c="96")
        for i, price in ((14, "100"), (15, "100.5"), (16, "100.2")):
            store.insert_fact(
                self.con, symbol="BTC-USD", tf="1H", kind="swing",
                market_time=i * 3600, confirmed_at=(i + 1) * 3600,
                algo_version=swings.SWING_VERSION,
                payload={"tier": "INTERMEDIATE", "type": "HIGH", "price": price})
        liquidity.run(self.con, "BTC-USD", "1H", 3600)
        rows = store.get_facts(
            self.con, "BTC-USD", "1H", "liquidity", liquidity.LIQ_VERSION)
        pools = [r for r in rows if json.loads(r["payload"])["event"] == "POOL"]
        self.assertEqual(len(pools), 1)


class TestDecimalScoring(unittest.TestCase):
    def test_decimal_ln_is_available_and_repeatable(self):
        x = (Decimal("6") + 1).ln() / Decimal(2).ln()
        self.assertEqual(x, (Decimal("6") + 1).ln() / Decimal(2).ln())


class TestValidationStatistics(unittest.TestCase):
    def test_bootstrap_is_seeded_and_deterministic(self):
        self.assertEqual(bootstrap_mean_ci([1, -1, 2], n=200),
                         bootstrap_mean_ci([1, -1, 2], n=200))


if __name__ == "__main__":
    unittest.main()
