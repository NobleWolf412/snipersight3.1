"""A delisted market's holes are unrepairable, so they must not halt the store.

CRVUSDT was removed from Phemex and failed quality with SEQUENCE_GAPS on every
cycle: the venue answers `code:0 OK` with zero rows, no import can ever fill
the history, and the operator has no action to take. Blocking forever on a
market that no longer exists is the same cry-wolf failure STALE_SERIES was
scoped against; these pin the scoping for gaps, in BOTH directions — the
narrowness is the point, because every case that stops blocking is a
fail-closed gate switched off.
"""
import json
import tempfile
import unittest
from pathlib import Path

from engine import quality, store, universe


class RetiredMarketCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "retired.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def gapped_series(self, sym):
        """Two 1H candles two hours apart — one unexplained hole between them,
        with no import_log row to acknowledge it."""
        for ts in (0, 7200):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sym, "1H", ts, "100", "102", "98", "101", "1",
                 "phemex-perp", ts + 1))
        self.con.commit()

    def universe_fact(self, members):
        self.con.execute(
            "INSERT INTO facts (symbol, tf, kind, market_time, confirmed_at, "
            "algo_version, payload, content_hash) VALUES (?,?,?,?,?,?,?,?)",
            ("UNIVERSE", "1D", "universe", 0, 0, universe.UNIVERSE_VERSION,
             json.dumps({"members": members}), f"h{len(members)}{members}"))
        self.con.commit()

    def codes(self, sym):
        return {c["code"]: c for c in
                quality.audit_market_inputs(self.con, sym, now=100_000)}

    def test_delisted_market_degrades_instead_of_blocking(self):
        self.gapped_series("CRVUSDT")
        # the venue's ranking no longer carries CRVUSDT at all
        self.universe_fact([{"symbol": "BTCUSDT", "state": "ADMITTED"}])
        found = self.codes("CRVUSDT")
        self.assertNotIn("SEQUENCE_GAPS", found)
        self.assertIn("RETIRED_SEQUENCE_GAPS", found)
        self.assertEqual(found["RETIRED_SEQUENCE_GAPS"]["status"], "DEGRADED")
        self.assertEqual(found["RETIRED_SEQUENCE_GAPS"]["rung"], "QUARANTINE")

    def test_listed_market_still_blocks(self):
        self.gapped_series("CRVUSDT")
        self.universe_fact([{"symbol": "CRVUSDT", "state": "ADMITTED"}])
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_warming_market_still_blocks(self):
        """A symbol short of history is a MEMBER, not a retirement. Testing
        tradeability instead of membership would stop blocking on every
        symbol still warming up — silently, and on the day it was added."""
        self.gapped_series("CRVUSDT")
        self.universe_fact([{"symbol": "CRVUSDT", "state": "WARMING"}])
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_illiquid_rejected_market_still_blocks(self):
        """A REJECTED market still receives import and exit resolution, so its
        data is live and repairable — CLAUDE.md's unresolved-order rule."""
        self.gapped_series("CRVUSDT")
        self.universe_fact([{"symbol": "CRVUSDT", "state": "REJECTED"}])
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_no_universe_fact_keeps_blocking(self):
        """Fails CLOSED. 'Cannot tell' must never read as 'everything retired'
        — a cold store would otherwise disable the gate store-wide."""
        self.gapped_series("CRVUSDT")
        self.assertIsNone(universe.known_symbols(self.con))
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_empty_member_list_keeps_blocking(self):
        """refresh() records no members when the venue sweep's rank coverage is
        too low to overwrite the universe. One failed HTTP sweep must not read
        as every market delisting at once."""
        self.gapped_series("CRVUSDT")
        self.universe_fact([])
        self.assertIsNone(universe.known_symbols(self.con))
        self.assertIn("SEQUENCE_GAPS", self.codes("CRVUSDT"))

    def test_only_gaps_demote_on_a_retired_market(self):
        """Malformed rows indict the STORE, which is live and repairable
        whatever the venue did. Widening the demotion to every DATA finding
        would hide real corruption behind a delisting."""
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("CRVUSDT", "1H", 0, "100", "97", "98", "101", "1",
             "phemex-perp", 1))          # high below open — impossible
        self.con.commit()
        self.universe_fact([{"symbol": "BTCUSDT", "state": "ADMITTED"}])
        found = self.codes("CRVUSDT")
        self.assertIn("OHLC_INVARIANT_FAILURE", found)
        self.assertEqual(found["OHLC_INVARIANT_FAILURE"]["status"], "BLOCKED")

    def test_reference_key_keeps_its_own_demotion(self):
        """Reference keys are never universe members, so the retired branch
        would claim them and produce REFERENCE_RETIRED_SEQUENCE_GAPS — a code
        no CODE_RUNG entry declares. The REFERENCE_ pass owns them."""
        self.gapped_series("BICOUSDT@binance-spot")
        self.universe_fact([{"symbol": "BTCUSDT", "state": "ADMITTED"}])
        found = self.codes("BICOUSDT@binance-spot")
        self.assertIn("REFERENCE_SEQUENCE_GAPS", found)
        self.assertNotIn("RETIRED_SEQUENCE_GAPS", found)


if __name__ == "__main__":
    unittest.main()
