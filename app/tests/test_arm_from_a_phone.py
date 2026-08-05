"""Arming over a connection that can drop mid-request.

On loopback, `fetch()` rejecting means the request never left. Over a tunnel or
on cellular it means one of two things — it never left, OR it arrived, was
recorded, and the REPLY was lost — and the client cannot tell them apart. The
cockpit used to answer that ambiguity by asserting "nothing was armed", which
is a coin flip stated as fact on the one screen where being wrong means arming
a second position while believing you have none.

The fix has two halves and this suite pins both:

  · The caller names the moment. `create_intent` builds its intent_id as
    `symbol|tf|MANUAL|created_at`, so a client that reuses one created_at
    across a retry produces an identical intent_id and an identical payload,
    which the content-hashed store collapses onto the row it already holds.
    Retrying becomes safe instead of frightening.

  · The server does not take that timestamp on trust. It is written into an
    append-only fact and is the moment the record will forever claim the plan
    was authored, so a phone with a wrong clock must not be able to set it.

Nothing here arms against the operator's real book. The engine-level tests use
a scratch database; the HTTP tests exercise only refusals, which are decided
before any handler runs.
"""
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server
from engine import manual, store

TF_S = 3600
SPOT = "BTC-USD"


class RetryingAnArmIsSafe(unittest.TestCase):
    """The half that makes a dropped reply harmless."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "test.db")
        for i, (o, h, l, c) in enumerate([(100, 101, 99, 100)] * 40):
            self.con.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                (SPOT, "1H", i * TF_S, str(o), str(h), str(l), str(c),
                 "1", "test", i * TF_S))
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _intents(self):
        return store.get_facts(self.con, SPOT, "1H", "manual_intent",
                               manual.MANUAL_VERSION)

    def test_the_same_moment_twice_leaves_one_trade(self):
        """The retry case, exactly: the operator taps Arm, the reply is lost,
        the client sends the identical request again."""
        kw = dict(entry=100, tp=104, sl=98, created_at=1_700_000_000)
        manual.create_intent(self.con, SPOT, "1H", "LONG", **kw)
        before = len(self._intents())
        try:
            manual.create_intent(self.con, SPOT, "1H", "LONG", **kw)
        except manual.IntentRejected:
            # Equally acceptable: refusing the second is also "one trade".
            # What must never happen is a second one being written.
            pass
        self.assertEqual(len(self._intents()), before,
                         "a retry with the same created_at wrote a second intent")

    def test_a_different_moment_is_a_different_intent_id(self):
        """The property the retry safety rests on. If intent_id stopped
        deriving from created_at, the test above would still pass — by way of
        the duplicate guard — while retrying had silently stopped being
        idempotent."""
        a = manual.create_intent(self.con, SPOT, "1H", "LONG",
                                 entry=100, tp=104, sl=98, created_at=1_700_000_000)
        self.assertIn("intent_id", a, "create_intent stopped returning an intent_id")
        # the key itself, not str(payload) — created_at appears elsewhere in
        # the payload, so a looser check would pass while intent_id had
        # stopped deriving from it and retries had silently stopped collapsing
        self.assertEqual(a["intent_id"], f"{SPOT}|1H|MANUAL|1700000000")


class TheServerDoesNotTrustThePhonesClock(unittest.TestCase):
    """The half that keeps a wrong clock out of an append-only record.

    Every case here is refused before the handler runs, so none of them
    touches the operator's book.
    """

    def setUp(self):
        self.client = TestClient(server.app)
        # THIS SUITE MUST NOT BE ABLE TO WRITE, EVEN IF THE CLAMP IS REMOVED.
        #
        # TestClient drives the real app against the real store, so every
        # request here is one clamp away from the operator's actual book.
        # Writing this suite the obvious way — post a bad timestamp, assert
        # 400 — was safe only for as long as the code under test kept working,
        # which is precisely the assumption a test exists to stop making. A
        # mutation run that disabled the clamp sent a live arm at the real
        # database and was stopped by an unrelated validation.
        #
        # So create_intent is replaced with something that raises. That is not
        # merely a guard: reaching it AT ALL is the failure these tests are
        # about, because the whole claim is that a bad timestamp is refused
        # before any handler runs.
        self._real = manual.create_intent
        manual.create_intent = self._must_not_be_called

    def tearDown(self):
        manual.create_intent = self._real

    @staticmethod
    def _must_not_be_called(*a, **kw):
        raise AssertionError(
            "the arm handler was reached with a timestamp that should have "
            "been refused — this would have written to the operator's book")

    def _arm(self, created_at):
        return self.client.post("/api/manual/arm", json={
            "symbol": SPOT, "tf": "1H", "direction": "LONG",
            "entry": 100, "tp": 104, "sl": 98, "created_at": created_at})

    def test_a_timestamp_from_last_year_is_refused(self):
        r = self._arm(int(time.time()) - 400_000)
        self.assertEqual(r.status_code, 400)
        self.assertIn("clock", r.json()["detail"])

    def test_a_timestamp_from_the_future_is_refused(self):
        r = self._arm(int(time.time()) + 400_000)
        self.assertEqual(r.status_code, 400)
        self.assertIn("clock", r.json()["detail"])

    def test_the_refusal_says_how_far_off_and_by_what_limit(self):
        """'Invalid timestamp' sends the operator nowhere. The device's clock
        is the thing to go and fix, and the message has to say so."""
        r = self._arm(int(time.time()) + 400_000)
        detail = r.json()["detail"]
        self.assertIn(str(server.ARM_CLOCK_SKEW_S), detail)
        self.assertIn("recorded permanently", detail)

    def test_a_non_numeric_timestamp_is_refused(self):
        r = self._arm("yesterday")
        self.assertEqual(r.status_code, 400)
        self.assertIn("unix timestamp", r.json()["detail"])

    def test_the_window_is_wide_enough_to_be_useful(self):
        """A phone that has not synced in a while, and a retry that waited out
        a cellular stall, both have to fit. Too tight and the idempotency this
        exists to enable stops working exactly when it is needed."""
        self.assertGreaterEqual(server.ARM_CLOCK_SKEW_S, 60)
        self.assertLessEqual(server.ARM_CLOCK_SKEW_S, 900)


class TheStaleGateKnowsHowLongABarIs(unittest.TestCase):
    """chart.js refuses to arm when the prices it would size against are older
    than one bar of the chosen timeframe. That comparison needs seconds-per-bar
    in the browser, and the engine already owns that number.

    The first version of the table spelled every key in lower case while the
    engine uses '15m' but '1H', '4H', '1D', '1W'. Every lookup missed, the code
    fell back to 60 seconds, and on a 4H chart Arm switched itself off after a
    minute of staleness while blaming a four-hour bar. Nothing failed; it just
    produced the sentence "15 min — longer than one 4H bar", which is arithmetic
    nobody would write on purpose.

    So the two tables are compared directly. A timeframe added to the engine
    without reaching the browser fails here rather than in a refusal message
    the operator has to disbelieve.
    """

    def test_the_browser_table_matches_the_engine_exactly(self):
        import re
        from engine import importer
        src = (Path(__file__).resolve().parents[1] / "static" / "chart.js").read_text(
            encoding="utf-8")
        m = re.search(r"const TF_S = \{([^}]*)\}", src)
        self.assertIsNotNone(m, "chart.js no longer declares TF_S")
        pairs = dict(re.findall(r"'([^']+)':\s*(\d+)", m.group(1)))
        self.assertEqual(
            set(pairs), set(importer.TF_SECONDS),
            "chart.js and importer.TF_SECONDS disagree about which timeframes "
            "exist — case included; the spellings are not interchangeable")
        for tf, secs in pairs.items():
            self.assertEqual(int(secs), importer.TF_SECONDS[tf],
                             f"{tf} is a different length in the browser")

    def test_an_unknown_timeframe_refuses_rather_than_guessing(self):
        """The silent 60-second fallback is what made the bug invisible. A
        timeframe this build does not recognise must turn Arm OFF and say so,
        not pick a number."""
        src = (Path(__file__).resolve().parents[1] / "static" / "chart.js").read_text(
            encoding="utf-8")
        self.assertNotIn("TF_S[tf] || 60", src,
                         "the silent fallback is back")
        self.assertIn("does not know", src,
                      "an unrecognised timeframe no longer says so")


if __name__ == "__main__":
    unittest.main()
