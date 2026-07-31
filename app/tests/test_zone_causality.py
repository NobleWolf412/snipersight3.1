"""A fact stamped `confirmed_at = T` may not depend on anything after T.

`zones.run` computed a zone's creation-time cluster count over EVERY swing in
the series, with no `confirmed_at` filter — while writing the resulting fact
with `confirmed_at = s["confirmed_at"]`. So a zone created in 2023 could be
rated on swings from 2025.

It mattered because the number is load-bearing. `formation_quality` feeds
`strength`, and `strength` was one of the four evidence components the REVERSAL
playbook counted (`setups.reversal_evidence`, `REVERSAL_MIN_ZONE_STRENGTH`).
A quality computed from the future fed straight into which setups exist.

(S50 has since retired STRENGTH from `setups.REVERSAL_COMPONENTS` — it is
recorded, not counted — so a wrong cluster no longer changes admission. It
still corrupts the `zone_cluster` / `zone_quality` / `zone_strength` evidence
recorded on every setup fact, which is what a grader reads to decide whether
STRENGTH ever earns its place back. The causality rule is not conditional on
who is currently listening.)

Measured before the fix (12 symbols x 4H/1D/1W, 2,006 zones): 159 (7.9%)
counted future swings; 96 of those got a different `formation_quality`, and the
shipped value was HIGHER in every single case — 75->65, 90->60, 95->65. Worst
observed: quality 90 from a cluster of 18, of which zero were knowable at that
zone's own creation time. The bias had one direction, and it was flattering.

Three layers, in order of how much they can be trusted as a gate:

1. `ZoneClusterIsCausal` — the arithmetic invariant and a source check, no I/O.
2. `ZoneRunRecordsCausalClusters` — runs the real `zones.run` over a
   constructed store and reads back what it wrote. This is THE gate: it fails
   if and only if the engine regresses. Verified by mutation — deleting the
   `confirmed_at` filter from zones.py fails it 2 ways.
3. `RecordedZonesRespectTheirCausalBound` — a live-store audit, one-sided on
   purpose. See its docstring for why equality against a fresh recount is not
   a sound assertion on a store the scanner is still writing to, and why this
   file no longer makes one.

The distinction matters because layer 3 used to be written as an equality and
could not tell "the engine regressed" from "the scanner wrote more data since
the last run" — it passed and failed 11 minutes apart with no code change.
Regressions are caught by layer 2, which owns no such ambiguity.
"""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine import store, zones  # noqa: E402
from engine.swings import SWING_VERSION, compute_atr  # noqa: E402

DAY = 86400


class ZoneClusterIsCausal(unittest.TestCase):
    def test_cluster_ignores_swings_confirmed_after_the_zone(self):
        """Constructed: three lows in one band, the third confirmed LATER.

        The band is built from the first low. The second is knowable at
        creation, the third is not. A causal cluster sees 1; the buggy one saw
        2, and `formation_quality` differs by a full 10 points.
        """
        swings = [
            {"market_time": 100, "confirmed_at": 110, "type": "LOW", "price": Decimal("100")},
            {"market_time": 105, "confirmed_at": 108, "type": "LOW", "price": Decimal("101")},
            {"market_time": 900, "confirmed_at": 950, "type": "LOW", "price": Decimal("101")},
        ]
        anchor = swings[0]
        bottom, top = Decimal("100"), Decimal("110")

        def cluster(causal):
            return sum(1 for m, o in enumerate(swings)
                       if m != 0 and bottom <= o["price"] <= top
                       and (not causal or o["confirmed_at"] <= anchor["confirmed_at"]))

        self.assertEqual(cluster(causal=False), 2, "sanity: the old count saw both")
        self.assertEqual(cluster(causal=True), 1, "the future swing must not count")
        self.assertNotEqual(zones.formation_quality(2, "1D"),
                            zones.formation_quality(1, "1D"),
                            "if quality did not move, this test proves nothing")

    def test_source_applies_the_confirmed_at_filter(self):
        src = (APP / "engine" / "zones.py").read_text(encoding="utf-8")
        i = src.index("cluster = sum(")
        expr = src[i:i + 400]
        self.assertIn("confirmed_at", expr,
                      "the cluster count must filter on confirmed_at, or it "
                      "reads the future")


def _causal_clusters(candles, sw):
    """Recompute every anchor's causal cluster. Returns {index: count}.

    Mirrors `zones.run` exactly, including the `confirmed_at <= anchor's`
    filter that is the thing under test.
    """
    idx = {c["open_ts"]: i for i, c in enumerate(candles)}
    atr = compute_atr(candles)
    bands = []
    for mt, _ca, ty, px in sw:
        i = idx.get(mt)
        if i is None or atr[i] is None:
            bands.append(None)
            continue
        w = zones.ZONE_ATR * atr[i]
        bands.append(("DEMAND", px, px + w) if ty == "LOW" else ("SUPPLY", px - w, px))
    out = {}
    for k, (_mt, ca, _ty, _px) in enumerate(sw):
        if bands[k] is None:
            continue
        kind, bot, top = bands[k]
        out[k] = sum(1 for m, (_m2, ca2, _t2, px2) in enumerate(sw)
                     if m != k and bands[m] and bands[m][0] == kind
                     and bot <= px2 <= top and ca2 <= ca)
    return out


class ZoneRunRecordsCausalClusters(unittest.TestCase):
    """The gate: run the real engine over a constructed store and check what
    it wrote. Deterministic — no dependence on what the live scanner has done.

    Constant true range (high +1, low -1, flat closes) makes ATR exactly
    2.00000000, so the demand band at a 100.00 low is exactly [100.00, 100.50]
    and every membership decision below is arithmetic this test can state.
    """

    SYMBOL, TF = "BTC-USD", "1D"
    ANCHOR_BAR = 20
    # (bar, type, price, confirmed_at bar, counts toward the anchor's cluster?)
    SWINGS = (
        (15, "LOW", "101.00", 19, False),   # outside the band
        (16, "LOW", "100.20", 22, True),    # in band, knowable at anchor time
        (18, "HIGH", "100.20", 22, False),  # in band by price, but SUPPLY
        (20, "LOW", "100.00", 24, None),    # the anchor itself
        (30, "LOW", "100.30", 40, False),   # in band, but confirmed LATER
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")
        for i in range(60):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.SYMBOL, self.TF, i * DAY, "100.00", "101.00", "99.00",
                 "100.00", "1", "test", 0))
        for bar, kind, price, ca_bar, _ in self.SWINGS:
            store.insert_fact(
                self.con, symbol=self.SYMBOL, tf=self.TF, kind="swing",
                market_time=bar * DAY, confirmed_at=ca_bar * DAY,
                algo_version=SWING_VERSION,
                payload={"tier": "INTERMEDIATE", "type": kind, "price": price})
        self.con.commit()
        zones.run(self.con, self.SYMBOL, self.TF, DAY)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def created(self):
        return {r["market_time"]: json.loads(r["payload"]) for r in
                store.get_facts(self.con, self.SYMBOL, self.TF, "zone",
                                zones.ZONE_VERSION)
                if json.loads(r["payload"])["event"] == "CREATED"}

    def test_the_anchor_counts_only_what_was_knowable(self):
        want = sum(1 for _b, _k, _p, _c, counts in self.SWINGS if counts)
        zone = self.created()[self.ANCHOR_BAR * DAY]
        self.assertEqual(zone["bottom"], "100.00")
        self.assertEqual(zone["top"], "100.5000000000")
        self.assertEqual(zone["cluster_members"], want)
        self.assertEqual(zone["formation_quality"],
                         zones.formation_quality(want, self.TF))

    def test_the_later_swing_would_have_changed_the_verdict(self):
        """Drop the confirmed_at filter and the anchor counts 2, not 1 — and
        `formation_quality` moves with it. If this ever stops holding, the
        fixture has gone slack and the test above proves nothing.
        """
        causal = sum(1 for _b, _k, _p, _c, counts in self.SWINGS if counts)
        # same band, same kind filter, but blind to when the swing was knowable
        naive = sum(1 for _b, kind, price, _c, counts in self.SWINGS
                    if counts is not None and kind == "LOW"
                    and Decimal("100.00") <= Decimal(price) <= Decimal("100.50"))
        self.assertEqual((causal, naive), (1, 2), "the fixture must discriminate")
        self.assertNotEqual(zones.formation_quality(naive, self.TF),
                            zones.formation_quality(causal, self.TF))

    def test_every_recorded_cluster_matches_the_causal_recount(self):
        candles = [dict(r) for r in store.get_candles(self.con, self.SYMBOL, self.TF)]
        sw = [(b * DAY, c * DAY, k, Decimal(p)) for b, k, p, c, _ in self.SWINGS]
        causal = _causal_clusters(candles, sw)
        created = self.created()
        self.assertEqual(len(created), len(causal), "one CREATED fact per anchor")
        for k, want in causal.items():
            mt = sw[k][0]
            self.assertEqual(created[mt]["cluster_members"], want,
                             f"anchor at bar {mt // DAY} recorded "
                             f"{created[mt]['cluster_members']}, causal {want}")


class ClusterCountsSwingsNotFacts(unittest.TestCase):
    """A pivot re-emitted N times is still ONE cluster member.

    `swings` appends a fresh fact every time a pivot's accrued evidence moves —
    `held_candles` ticks with each bar the level holds — so the store carries
    rows identical in market_time, confirmed_at, tier, type and price, differing
    only in a block `zones` never reads. Counting rows made `m != k` exclude the
    ROW and not the SWING, so a zone counted copies of its own anchor: 65.8% of
    2,066 anchors inflated, quality higher in 1,359 and lower in zero.

    Here one in-band neighbour is written 5 times and the anchor 4 times. The
    honest cluster is 1. Counting facts gives 4.
    """

    SYMBOL, TF = "BTC-USD", "1D"
    ANCHOR_BAR, NEIGHBOUR_BAR = 20, 16

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")
        for i in range(60):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.SYMBOL, self.TF, i * DAY, "100.00", "101.00", "99.00",
                 "100.00", "1", "test", 0))
        # identical swing, re-emitted as its evidence accrues
        for bar, price, ca_bar, copies in ((self.NEIGHBOUR_BAR, "100.20", 22, 5),
                                           (self.ANCHOR_BAR, "100.00", 24, 4)):
            for held in range(copies):
                store.insert_fact(
                    self.con, symbol=self.SYMBOL, tf=self.TF, kind="swing",
                    market_time=bar * DAY, confirmed_at=ca_bar * DAY,
                    algo_version=SWING_VERSION,
                    payload={"tier": "INTERMEDIATE", "type": "LOW",
                             "price": price, "evidence": {"held_candles": held}})
        self.con.commit()
        zones.run(self.con, self.SYMBOL, self.TF, DAY)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_the_fixture_really_does_hold_duplicate_facts(self):
        """If dedupe moved upstream into `swings`, this test stops proving
        anything and should be deleted rather than left passing vacuously."""
        n = self.con.execute(
            "SELECT COUNT(*) FROM facts WHERE kind='swing' AND market_time=?",
            (self.ANCHOR_BAR * DAY,)).fetchone()[0]
        self.assertEqual(n, 4, "insert_fact should keep all four generations")

    def test_a_repeated_pivot_counts_once(self):
        created = {r["market_time"]: json.loads(r["payload"]) for r in
                   store.get_facts(self.con, self.SYMBOL, self.TF, "zone",
                                   zones.ZONE_VERSION)
                   if json.loads(r["payload"])["event"] == "CREATED"}
        self.assertEqual(len(created), 2, "one zone per distinct pivot")
        zone = created[self.ANCHOR_BAR * DAY]
        self.assertEqual(zone["cluster_members"], 1)
        self.assertEqual(zone["formation_quality"],
                         zones.formation_quality(1, self.TF))

    def test_a_zone_never_counts_a_copy_of_its_own_anchor(self):
        """The sharpest form: with the neighbour removed the cluster is 0, and
        counting rows would have returned 3 — pure self-membership."""
        self.con.execute("DELETE FROM facts WHERE kind='zone'")
        self.con.execute("DELETE FROM facts WHERE kind='swing' AND market_time=?",
                         (self.NEIGHBOUR_BAR * DAY,))
        self.con.commit()
        zones.run(self.con, self.SYMBOL, self.TF, DAY)
        zone = [json.loads(r["payload"]) for r in
                store.get_facts(self.con, self.SYMBOL, self.TF, "zone",
                                zones.ZONE_VERSION)
                if json.loads(r["payload"])["event"] == "CREATED"][0]
        self.assertEqual(zone["cluster_members"], 0)


class RecordedZonesRespectTheirCausalBound(unittest.TestCase):
    """Live-store audit. Advisory by construction, and deliberately one-sided.

    Equality against a fresh recount is NOT a sound assertion here, and the
    old version of this test asserted exactly that. Two reasons it flaps:

    1. `insert_fact` keys on a content hash that includes the payload, so a
       re-run whose cluster count has changed appends a SECOND `CREATED` fact
       rather than replacing the first. 1,512 of 15,329 zone market_times in
       the observed store carry more than one, up to 20. The old query took
       `LIMIT 1` with no ORDER BY — the oldest row — and compared a fact
       written weeks ago against a recount over today's swings.
    2. The swing set only ever grows, and `swings` re-emits a swing whenever
       its accrued evidence changes, so the recount drifts upward under a
       test that is not writing any of it.

    What IS sound is the inequality. Every swing the engine could legitimately
    have counted at write time is still in the store today and still passes
    `confirmed_at <= anchor's`, so today's recount is an upper bound on any
    honest historical count. A recorded count ABOVE it counted something that
    is not causally available now and never was — which is the lookahead this
    file exists to catch. Staleness can only push the recorded count below the
    bound, never above it, so this cannot fail for the reason the old one did.
    """

    @classmethod
    def setUpClass(cls):
        if not (APP / "data" / "snipersight.db").exists():
            raise unittest.SkipTest("no live store")
        cls.con = store.connect()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "con"):
            cls.con.close()

    def test_no_recorded_zone_exceeds_its_causal_upper_bound(self):
        syms = [r[0] for r in self.con.execute(
            "SELECT DISTINCT symbol FROM candles WHERE tf='1D' "
            "ORDER BY symbol LIMIT 6").fetchall()]
        bad, checked = [], 0
        for sym in syms:
            for tf in ("4H", "1D"):
                candles = [dict(r) for r in store.get_candles(self.con, sym, tf)]
                if len(candles) < 30:
                    continue
                # Read the zone facts BEFORE the swings. The scanner is running
                # while this test runs; anything it wrote up to this read used a
                # swing set no larger than the one read on the next line, which
                # is what makes the bound below sound under concurrent writes.
                # (Reading swings first would let a fact written mid-test count
                # a swing this test never saw, and fail honestly-written data.)
                recorded = {}
                for r in self.con.execute(
                        "SELECT market_time, payload FROM facts WHERE symbol=? "
                        "AND tf=? AND kind='zone' AND algo_version=? "
                        "AND json_extract(payload,'$.event')='CREATED'",
                        (sym, tf, zones.ZONE_VERSION)):
                    recorded.setdefault(r[0], []).append(
                        json.loads(r[1])["cluster_members"])
                sw = []
                for r in store.get_facts(self.con, sym, tf, "swing", SWING_VERSION):
                    p = json.loads(r["payload"])
                    if p["tier"] in zones.ZONE_TIERS:
                        sw.append((r["market_time"], r["confirmed_at"],
                                   p["type"], Decimal(p["price"])))
                causal = _causal_clusters(candles, sw)
                for k, bound in causal.items():
                    # EVERY recorded generation must respect the bound, not
                    # just whichever one an unordered LIMIT 1 happens to hit.
                    for rec in recorded.get(sw[k][0], ()):
                        checked += 1
                        if rec > bound:
                            bad.append((sym, tf, sw[k][0], rec, bound))
        if not checked:
            self.skipTest(f"no {zones.ZONE_VERSION} zone facts yet — "
                          f"re-run the zone engine to populate them")
        self.assertFalse(bad, (
            f"{len(bad)} of {checked} recorded zones counted MORE members than "
            f"are causally available even now — the engine is reading the "
            f"future. (symbol, tf, market_time, recorded, bound): {bad[:5]}"))


if __name__ == "__main__":
    unittest.main()
