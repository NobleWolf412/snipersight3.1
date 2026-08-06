"""An operator's close must outlive the engine version it was written under.

THE CLASS OF BUG, not the one instance. `setup_id` embeds SETUP_VERSION on
purpose — two engine generations must never mint the same id, or every
downstream join merges them silently (setups.py:975-983). That rule is right
for facts and wrong for a decision. A setup fact is a derivation: bump the
engine and the same zone touch is re-derived, correctly, under a new id. An
override is not a derivation. It is the operator saying "I am out of this
trade", and the trade is the zone, not the generation of code that described
it.

Keying the portfolio's suppression on the exact id therefore gave every
operator close a silent expiry date: the next `setups` bump re-minted the id,
the match stopped firing, and a closed position came back as live exposure.

Measured live 2026-08-06 before the fix, and this is what it cost:

    active_positions  UNIUSDT 4H  …|setup-v0.17-draft   risk_usd 194.60
    operator_closed   UNIUSDT 4H  …|setup-v0.15-draft   usd_at_close +136.22
    open_risk_usd     194.6

Same symbol, same timeframe, same zone, same entry 4.379 — one trade, printed
twice, once as money made and once as money still on the table. It was the only
position, so `open_risk_usd` was ENTIRELY a closed trade, and that figure drives
the risk meters, the free-slot chip and the exposure accent. The VALIDATED setup
facts under setup-v0.13 through v0.17 all carry the identical `confirmed_at`
(1785470400) and byte-identical entry/sl/tp, so it was one zone touch re-derived
five times, not five signals.

These tests fail if the suppression is ever keyed on the version again. They are
written against a scratch database and never POST to a write endpoint, because
`/api/positions/close` writes to the operator's real book.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from engine import execsim, manual, risk, setups, store

SYM, TF = "BTC-USD", "1D"
#: The zone identity, version-free: symbol|tf|strategy|zone_id. `zone_id` is
#: itself `symbol|tf|zone_type|created_ts` (zones.py:141), so it carries pipes —
#: which is exactly why the stripper matches the tail rather than splitting.
ZONE = f"{SYM}|{TF}|REVERSAL|{SYM}|{TF}|SUPPLY|1000"
#: A superseded engine tag. Deliberately not built from SETUP_VERSION: the whole
#: point is an id minted by a generation that is no longer current.
OLD_TAG = "setup-v0.15-draft"


class SetupZoneKey(unittest.TestCase):
    """The stripping rule itself. Cheap to state, expensive to get wrong."""

    def test_the_engine_version_is_stripped_and_the_zone_survives(self):
        self.assertEqual(
            manual.setup_zone_key(f"{ZONE}|{setups.SETUP_VERSION}"), ZONE)
        self.assertEqual(manual.setup_zone_key(f"{ZONE}|{OLD_TAG}"), ZONE)

    def test_two_generations_of_one_zone_agree_on_the_key(self):
        """The property in one line — this is the whole fix."""
        self.assertEqual(manual.setup_zone_key(f"{ZONE}|{OLD_TAG}"),
                         manual.setup_zone_key(f"{ZONE}|{setups.SETUP_VERSION}"))

    def test_every_engine_that_mints_a_setup_id_is_covered(self):
        """setups, breakout and trend all end their ids with their own version
        tag. A stripper that only knew `setup-` would leave two of them
        version-scoped and the bug alive on those playbooks."""
        for tag in ("setup-v0.17-draft", "breakout-v0.5-draft",
                    "trend-v0.2-draft", "scale-v0.15-draft"):
            with self.subTest(tag=tag):
                self.assertEqual(manual.setup_zone_key(f"{ZONE}|{tag}"), ZONE)

    def test_an_id_with_no_version_is_left_exactly_as_it_is(self):
        """Ids minted before the version was added have no tail to strip
        (setups.py:977-984), and the operator's store still holds them."""
        self.assertEqual(manual.setup_zone_key(ZONE), ZONE)
        self.assertEqual(manual.setup_zone_key("SID|4H|X"), "SID|4H|X")
        self.assertEqual(manual.setup_zone_key("ENG|2"), "ENG|2")
        self.assertEqual(manual.setup_zone_key("trace-1"), "trace-1")

    def test_a_trailing_component_that_is_not_a_version_is_not_eaten(self):
        """Blind rpartition would swallow the zone timestamp on a legacy id and
        merge every zone created on that symbol into one key — an override on
        one zone would then suppress a position on another. Silently."""
        for tail in ("1770811200", "SUPPLY", "v0.17", "4H", ""):
            with self.subTest(tail=tail):
                sid = f"{ZONE}|{tail}"
                self.assertEqual(manual.setup_zone_key(sid), sid)


class OverrideOutlivesTheVersion(unittest.TestCase):
    """Driven through `server.portfolio()` on a scratch store, because the
    defect lived in the join, not in either engine on its own."""

    def _store(self, d, *, position_tag, override_tag):
        db = Path(d) / "override.db"
        original_connect = store.connect
        con = original_connect(db)
        sid = f"{ZONE}|{position_tag}"
        store.insert_fact(
            con, symbol=SYM, tf=TF, kind="setup", market_time=10,
            confirmed_at=20, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": sid, "state": "VALIDATED",
                     "strategy": "REVERSAL", "direction": "SHORT",
                     "entry": "4.379", "sl": "4.5930863565",
                     "tp": "3.7367409305", "rr": "3", "rank": 60,
                     "why": "price reached the supply zone"})
        store.insert_fact(
            con, symbol=SYM, tf=TF, kind="risk", market_time=10,
            confirmed_at=21, algo_version=risk.RISK_VERSION,
            payload={"event": "DECISION", "setup_id": sid,
                     "decision": "APPROVED", "reasons": ["WITHIN_LIMITS"],
                     "risk_usd": "194.60", "notional_usd": "3980.42"})
        store.insert_fact(
            con, symbol=SYM, tf=TF, kind="order", market_time=10,
            confirmed_at=22, algo_version=execsim.EXEC_VERSION,
            payload={"setup_id": sid, "side": "SHORT", "order_type": "LIMIT",
                     "limit_price": "4.379", "available_at": 20,
                     "event": "FILLED"})
        if override_tag is not None:
            store.insert_fact(
                con, symbol=SYM, tf=TF, kind=manual.OVERRIDE_KIND,
                market_time=10, confirmed_at=25,
                algo_version=manual.MANUAL_VERSION,
                payload={"setup_id": f"{ZONE}|{override_tag}",
                         "source": "OPERATOR", "event": "CLOSED_EARLY",
                         "symbol": SYM, "tf": TF, "direction": "SHORT",
                         "entry": "4.379", "sl": "4.5930863565",
                         "r_at_close": "0.70", "usd_at_close": "136.22",
                         "risk_usd": "194.60",
                         "not_the_strategy_record": True})
        store.start_baseline(con, started_at=5)
        con.commit()
        con.close()
        return db, original_connect

    def _portfolio(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            db, original = self._store(d, **kw)
            with patch("server.store.connect",
                       side_effect=lambda: original(db)):
                return server.portfolio()

    def test_without_an_override_the_position_is_reported(self):
        """The control. Without it the suppression test passes for any reason
        at all — including the fixture simply never producing a position."""
        pf = self._portfolio(position_tag=setups.SETUP_VERSION,
                             override_tag=None)
        self.assertEqual(len(pf["active_positions"]), 1)
        self.assertEqual(pf["open_risk_usd"], 194.6)
        self.assertEqual(pf["operator_closed"], [])

    def test_an_override_under_an_older_version_still_suppresses(self):
        """The bug, in one assertion. The position is minted under the CURRENT
        setup version; the operator's close was written under a superseded one.
        Same zone, same entry, one trade."""
        pf = self._portfolio(position_tag=setups.SETUP_VERSION,
                             override_tag=OLD_TAG)
        self.assertEqual(pf["active_positions"], [],
                         "a closed trade came back as live exposure after a "
                         "version bump re-minted its setup_id")
        self.assertEqual(pf["open_risk_usd"], 0,
                         "open_risk_usd is what drives the risk meters, the "
                         "free-slot chip and the exposure accent")

    def test_the_close_is_still_reported_with_the_id_it_was_written_under(self):
        """Suppression is a wider question than identity. `operator_closed` is
        the operator's money and keeps the full id it was recorded against —
        the fix must not rewrite history to make the join work."""
        pf = self._portfolio(position_tag=setups.SETUP_VERSION,
                             override_tag=OLD_TAG)
        self.assertEqual(len(pf["operator_closed"]), 1)
        row = pf["operator_closed"][0]
        self.assertEqual(row["setup_id"], f"{ZONE}|{OLD_TAG}")
        self.assertEqual(row["usd_at_close"], "136.22")

    def test_the_same_version_case_still_works(self):
        """The behaviour that already worked must not regress on the way."""
        pf = self._portfolio(position_tag=setups.SETUP_VERSION,
                             override_tag=setups.SETUP_VERSION)
        self.assertEqual(pf["active_positions"], [])
        self.assertEqual(pf["open_risk_usd"], 0)

    def test_an_override_on_a_different_zone_suppresses_nothing(self):
        """The other direction, and the one a too-eager stripper would break:
        a close on one zone must never hide a position on another."""
        with tempfile.TemporaryDirectory() as d:
            db, original = self._store(d, position_tag=setups.SETUP_VERSION,
                                       override_tag=None)
            con = original(db)
            other = f"{SYM}|{TF}|REVERSAL|{SYM}|{TF}|SUPPLY|9999"
            store.insert_fact(
                con, symbol=SYM, tf=TF, kind=manual.OVERRIDE_KIND,
                market_time=10, confirmed_at=25,
                algo_version=manual.MANUAL_VERSION,
                payload={"setup_id": f"{other}|{OLD_TAG}", "source": "OPERATOR",
                         "event": "CLOSED_EARLY", "symbol": SYM, "tf": TF,
                         "direction": "SHORT", "usd_at_close": "10.00",
                         "not_the_strategy_record": True})
            con.commit()
            con.close()
            with patch("server.store.connect",
                       side_effect=lambda: original(db)):
                pf = server.portfolio()
        self.assertEqual(len(pf["active_positions"]), 1,
                         "an override on another zone hid a live position")
        self.assertEqual(pf["open_risk_usd"], 194.6)

    def test_two_closes_on_one_zone_are_both_reported(self):
        """Why `overridden_setups` stays keyed on the FULL id. An operator can
        close the same zone in two generations; collapsing them on the stripped
        key would delete one of those closes from the record, and it is real
        money the operator earned."""
        with tempfile.TemporaryDirectory() as d:
            db, original = self._store(d, position_tag=setups.SETUP_VERSION,
                                       override_tag=OLD_TAG)
            con = original(db)
            store.insert_fact(
                con, symbol=SYM, tf=TF, kind=manual.OVERRIDE_KIND,
                market_time=10, confirmed_at=40,
                algo_version=manual.MANUAL_VERSION,
                payload={"setup_id": f"{ZONE}|{setups.SETUP_VERSION}",
                         "source": "OPERATOR", "event": "CLOSED_EARLY",
                         "symbol": SYM, "tf": TF, "direction": "SHORT",
                         "usd_at_close": "42.00",
                         "not_the_strategy_record": True})
            con.commit()
            con.close()
            with patch("server.store.connect",
                       side_effect=lambda: original(db)):
                pf = server.portfolio()
        self.assertEqual(len(pf["operator_closed"]), 2,
                         "one of two operator closes on the same zone was lost")
        self.assertEqual({r["usd_at_close"] for r in pf["operator_closed"]},
                         {"136.22", "42.00"})
        self.assertEqual(pf["active_positions"], [])


class TheReadSetCannotStrandTheBook(unittest.TestCase):
    """The other half of the bump. Suppression now spans engine versions; it
    must also span MANUAL versions, or the fix would itself orphan every
    override the moment `manual` bumps again."""

    def test_overrides_are_read_under_every_manual_version_ever_written(self):
        with tempfile.TemporaryDirectory() as d:
            con = store.connect(Path(d) / "tags.db")
            for i, tag in enumerate(manual.MANUAL_VERSIONS):
                store.insert_fact(
                    con, symbol=SYM, tf=TF, kind=manual.OVERRIDE_KIND,
                    market_time=10, confirmed_at=30 + i, algo_version=tag,
                    payload={"setup_id": f"{ZONE}|{i}x|{OLD_TAG}",
                             "source": "OPERATOR", "event": "CLOSED_EARLY"})
            con.commit()
            found = manual.overridden_setups(con)
            con.close()
        self.assertEqual(len(found), len(manual.MANUAL_VERSIONS),
                         "an override written under a retired manual tag "
                         "stopped suppressing anything")

    def test_the_suppression_set_comes_from_the_reported_map(self):
        """One authority. If the set were built from a second read, the
        portfolio could suppress something `operator_closed` never showed —
        exposure vanishing with nothing on screen accounting for it."""
        overrides = {f"{ZONE}|{OLD_TAG}": {}, "SID|4H|X": {}}
        self.assertEqual(manual.overridden_zone_keys(overrides),
                         {ZONE, "SID|4H|X"})


if __name__ == "__main__":
    unittest.main()
