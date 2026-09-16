"""A liquidity pool may not be knowable before the swings that define it.

Same invariant as `test_zone_causality.py`, one engine over. `liquidity.run`
clusters swings by `market_time` and stamped the POOL fact with the
`confirmed_at` of the newest member BY MARKET TIME — but those are two
different orderings. `swings` sets

    confirmed = max(s["confirmed_at"], candles[held_close_bar]["open_ts"] + tf)

so a pivot's confirmation can run far past its own market_time, and an EARLIER
member can therefore confirm LATER than the anchor. The pool was then stamped
knowable before one of its own inputs existed.

It matters because `setups.py` gates pools on `confirmed_at <= as_of` when it
picks targets: a take-profit level was reachable before the market had made the
swings that define it, which is the rule that stops a backtest cheating
(CLAUDE.md §6 rule 3).

Measured on the live store under liq-v0.13: 4 of 319 POOL facts confirmed
before their newest member swing did — VTHO-USD 1D by 19 days, PF_ARBUSD 1D by
3, PF_XLMUSD 1D by 1, PF_XRPUSD 1H by 3 bars.

`quality.audit`'s CAUSALITY_VIOLATION check compares `confirmed_at` against
`market_time` WITHIN a single fact, so it is structurally blind to a fact that
confirms before a DIFFERENT fact it depends on. This is that gap's test.
"""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from engine import liquidity, store  # noqa: E402
from engine.swings import SWING_VERSION  # noqa: E402

TF, TF_S = "1H", 3600


class LiquidityPoolCausality(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "liq.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def candles(self, n, base=1_700_000_000):
        """A flat series — the pool comes from the swing facts, not the bars.
        ATR must be non-zero or the equal-tolerance test is degenerate."""
        for i in range(n):
            ts = base + i * TF_S
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("BTC-USD", TF, ts, "100", "101", "99", "100", "10",
                 "test", ts + TF_S))
        self.con.commit()
        return base

    def swing(self, market_time, confirmed_at, price, kind="HIGH"):
        store.insert_fact(
            self.con, symbol="BTC-USD", tf=TF, kind="swing",
            market_time=market_time, confirmed_at=confirmed_at,
            algo_version=SWING_VERSION,
            payload={"type": kind, "tier": "INTERMEDIATE", "price": str(price)})

    def pools(self):
        out = []
        for r in store.get_facts(self.con, "BTC-USD", TF, "liquidity",
                                 liquidity.LIQ_VERSION):
            p = json.loads(r["payload"])
            if p.get("event") == "POOL":
                out.append({"market_time": r["market_time"],
                            "confirmed_at": r["confirmed_at"],
                            "member_ts": p["member_ts"]})
        return out

    def test_a_pool_confirms_no_earlier_than_its_latest_member(self):
        """The regression, built so the two answers must differ.

        The EARLIER swing is the one that took longer to confirm — which is
        ordinary: `swings` holds a pivot until its window closes, and a wide
        window on an earlier pivot outlives a narrow one on a later pivot.
        """
        base = self.candles(60)
        early_mt = base + 10 * TF_S
        late_mt = base + 20 * TF_S
        early_conf = base + 40 * TF_S       # confirmed LATE
        late_conf = base + 22 * TF_S        # anchor, confirmed early

        self.swing(early_mt, early_conf, Decimal("100.00"))
        self.swing(late_mt, late_conf, Decimal("100.01"))
        liquidity.run(self.con, "BTC-USD", TF, TF_S)

        pools = self.pools()
        self.assertEqual(len(pools), 1, "fixture did not produce one pool")
        pool = pools[0]
        self.assertEqual(pool["market_time"], late_mt,
                         "the MARKET made this pool when it made the last "
                         "swing; only knowability moves")
        self.assertGreaterEqual(
            pool["confirmed_at"], early_conf,
            "the pool confirmed before a swing it is built from — it was "
            "usable as a target before the market had made it")

    def test_the_invariant_holds_across_every_pool_in_a_series(self):
        """The general form, not just the constructed case: no POOL fact may
        confirm before any swing it names as a member."""
        base = self.candles(120)
        confirmations = {}
        for i, (offset, delay) in enumerate(
                ((5, 30), (9, 4), (14, 25), (19, 3), (40, 12), (44, 2))):
            mt = base + offset * TF_S
            conf = base + (offset + delay) * TF_S
            confirmations[mt] = conf
            # Prices inside one ATR of each other so they cluster.
            self.swing(mt, conf, Decimal("100") + Decimal("0.01") * (i % 2))
        liquidity.run(self.con, "BTC-USD", TF, TF_S)

        found = self.pools()
        self.assertTrue(found, "fixture produced no pools to check")
        for pool in found:
            latest = max(confirmations[t] for t in pool["member_ts"])
            self.assertGreaterEqual(
                pool["confirmed_at"], latest,
                f"pool at {pool['market_time']} confirmed at "
                f"{pool['confirmed_at']}, before its member confirmed at "
                f"{latest}")


if __name__ == "__main__":
    unittest.main()
