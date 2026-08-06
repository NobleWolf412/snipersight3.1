"""The Ledger's money fields, held against the endpoints that emit them.

Same failure mode as `test_ui_field_contract.py`, one surface further on: a
missing number defaulting to zero, and zero reading as flat rather than as
absent. On Results that showed a -3.91 R book as break-even. On a page whose
entire question is "where are the wins coming from", a renamed server field
would show one book's dollars as $0 and the operator would conclude that half
of his trading makes no money.

So this file does what that one does — takes the names the surface must read,
calls the real endpoint, and requires every name to exist — with one difference
that matters. `test_ui_field_contract` parses the names out of the JS. The
Ledger's JS does not exist yet, and the point of a contract is to be written
BEFORE the reader, so the names are stated here as constants. When the surface
lands, the constants below are what it may read; anything it reads that is not
in this list has no contract behind it.

The four fields:

  · manual/book.trades[].pnl_usd   net R times the dollars the ticket risked
  · manual/book.total_pnl_usd      the sum, over the priced settled trades
  · manual/book.n_no_risk_usd      how many settled trades that sum omits
  · portfolio.operator_closed_usd  the operator's own exits on engine trades

They are derived in read views and persisted nowhere, which is why they carry
no version bump. `test_version_cascade.py` holds the other half of that
argument: `manual` stays locked at its current tag.
"""
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402

#: Names the Ledger reads off `/api/manual/book`. Top level.
BOOK_FIELDS = ("n", "wins", "win_rate", "total_r", "expectancy_r",
               "total_pnl_usd", "n_no_risk_usd")
#: Names it reads off EVERY row of `book.trades`, settled or not.
BOOK_ROW_FIELDS = ("symbol", "tf", "outcome", "r_multiple", "pnl_usd",
                   "resolved_at", "entry", "exit_price")
#: Names that exist only on a row that actually took size. A CANCELLED or
#: MISSED fact is written with a deliberately smaller payload (manual.py's
#: cancel_intent and the MISSED branch of run()) — no `risk_usd`, no
#: `size_units`, no `venue`, because none of the three ever happened. The
#: Ledger's per-trade table must therefore not read `risk_usd` off an arbitrary
#: row: `money(undefined)` renders "$NaN", which is how a field that was never
#: meant to be there gets onto a money surface.
BOOK_SETTLED_ROW_FIELDS = ("risk_usd", "size_units", "venue")
#: Names it reads off `/api/portfolio`. `max_drawdown_pct` and `baseline` were
#: added when the surface landed: the engine column prints the drawdown beside
#: the return, and stamps the book with the date the forward window opened.
#: The four method figures (trades, win rate, average R, profit factor) are NOT
#: here on purpose — the Ledger reads them off `lastScore`, which
#: `renderScoreboard` derives once for the Results tiles. One derivation, two
#: presentations; a second one here is how two surfaces start disagreeing.
PORTFOLIO_FIELDS = ("equity", "start_equity", "return_pct", "max_drawdown_pct",
                    "baseline", "open_risk_usd",
                    "operator_closed", "operator_closed_usd",
                    "operator_closed_no_usd")
#: Names it reads off each row of `portfolio.operator_closed`.
OVERRIDE_ROW_FIELDS = ("symbol", "tf", "direction", "r_at_close",
                       "usd_at_close", "closed_at")

CENT = Decimal("0.01")
SETTLED = ("TP", "SL", "TRAIL_STOP", "TIMEOUT")


def _client():
    return TestClient(server.app)


def _book():
    return _client().get("/api/manual/book").json()


def _portfolio():
    return _client().get("/api/portfolio").json()


def test_manual_book_emits_every_name_the_ledger_reads():
    payload = _book()
    missing = [f for f in BOOK_FIELDS if f not in payload]
    assert not missing, (
        f"/api/manual/book does not emit {missing}. The Ledger renders these "
        f"as dollars; a field the endpoint does not send renders as its "
        f"fallback, and a numeric fallback of 0 reads as break-even.")


def test_every_manual_row_carries_the_money_keys():
    """Present on EVERY row, not only the settled ones.

    A cancelled order has no P&L. The honest rendering is an em-dash, which
    needs the key to be there holding None — an absent key and a `?? 0` render
    it as $0, which reads as a trade that broke even.
    """
    rows = _book()["trades"]
    if not rows:
        pytest.skip("no manual trades in this store — nothing to contract-check")
    for r in rows:
        missing = [f for f in BOOK_ROW_FIELDS if f not in r]
        assert not missing, f"manual row {r.get('symbol')} lacks {missing}"
        if r["outcome"] in SETTLED:
            missing = [f for f in BOOK_SETTLED_ROW_FIELDS if f not in r]
            assert not missing, (
                f"settled row {r.get('symbol')} lacks {missing} — a trade that "
                f"took size and cannot say how much")
        else:
            absent = [f for f in BOOK_SETTLED_ROW_FIELDS if f in r]
            assert not absent, (
                f"{r['outcome']} row {r.get('symbol')} carries {absent}. It "
                f"never took size; a size field here would be rendered as one "
                f"that did.")


def test_manual_pnl_is_present_exactly_when_dollars_are_knowable():
    """Not "usually", not "when convenient" — exactly.

    A settled trade with a risk figure has a dollar result. A settled trade
    without one never will, because nothing can reconstruct the size after the
    fact. Anything else — a cancelled order, a missed entry — never had size.
    """
    rows = _book()["trades"]
    if not rows:
        pytest.skip("no manual trades in this store")
    for r in rows:
        knowable = r["outcome"] in SETTLED and r.get("risk_usd") is not None
        if knowable:
            assert r["pnl_usd"] is not None, (
                f"{r['symbol']} {r['outcome']} risked {r['risk_usd']} and "
                f"reports no dollars")
        else:
            assert r["pnl_usd"] is None, (
                f"{r['symbol']} {r['outcome']} risk_usd={r.get('risk_usd')} "
                f"reports {r['pnl_usd']} — a number where there is no number")


def test_manual_pnl_uses_the_same_arithmetic_as_the_engine_journal():
    """The Ledger puts the two books side by side. They must be comparable.

    Both sides multiply Decimal R by Decimal risk and quantize ROUND_HALF_UP.
    Half-cent ties are reachable — both operands arrive 2dp-quantized so the
    product lands on four decimals — and Python's round() banks to even. A cent
    of disagreement between two columns of the same page is not a rounding
    detail, it is the reason a reader stops believing either column.
    """
    for r in _book()["trades"]:
        if r["pnl_usd"] is None:
            continue
        want = (Decimal(str(r["r_multiple"])) * Decimal(str(r["risk_usd"]))
                ).quantize(CENT, rounding=ROUND_HALF_UP)
        assert Decimal(str(r["pnl_usd"])) == want, (
            f"{r['symbol']}: book says {r['pnl_usd']}, "
            f"R x risk half-up is {want}")

    for j in _portfolio()["journal"]:
        want = (Decimal(str(j["r_multiple"])) * Decimal(str(j["risk_usd"]))
                ).quantize(CENT, rounding=ROUND_HALF_UP)
        assert Decimal(str(j["pnl_usd"])) == want, (
            f"engine journal {j['symbol']}: {j['pnl_usd']} != {want}")


def test_the_manual_total_is_the_priced_rows_and_only_those():
    payload = _book()
    priced = [Decimal(str(r["pnl_usd"])) for r in payload["trades"]
              if r["pnl_usd"] is not None]
    if not priced:
        assert payload["total_pnl_usd"] is None, (
            "nothing is priced, so there is no total. $0.00 here would read as "
            "break-even across trades that won or lost.")
        return
    if len(payload["trades"]) >= 200:
        # `trades` is capped at `limit`; the total is over the whole book, the
        # same rule `n`/`wins`/`total_r` follow. Only the untruncated case can
        # be checked row by row from out here.
        pytest.skip("book truncated at the row limit — sum not checkable here")
    assert Decimal(str(payload["total_pnl_usd"])) == sum(priced), (
        f"total_pnl_usd {payload['total_pnl_usd']} is not the sum of the "
        f"{len(priced)} priced rows ({sum(priced)})")


def test_the_manual_total_names_what_it_leaves_out():
    """The degraded path has to be audible, which means countable.

    `n_no_risk_usd` is how many settled trades the dollar total does NOT cover.
    Live it is normally 0; the count still has to be emitted, because a surface
    that only prints it when it is non-zero has no way to know it is non-zero.
    """
    payload = _book()
    n_no_risk = payload["n_no_risk_usd"]
    assert isinstance(n_no_risk, int), (
        f"n_no_risk_usd is {n_no_risk!r} — the surface prints it as a count")
    unpriced = [r for r in payload["trades"]
                if r["outcome"] in SETTLED and r.get("risk_usd") is None]
    assert n_no_risk == len(unpriced)
    assert n_no_risk <= payload["n"], (
        "more unpriced trades than settled trades — the two are counted off "
        "different sets")


def test_portfolio_emits_every_name_the_ledger_reads():
    payload = _portfolio()
    missing = [f for f in PORTFOLIO_FIELDS if f not in payload]
    assert not missing, f"/api/portfolio does not emit {missing}"
    for r in payload["operator_closed"]:
        row_missing = [f for f in OVERRIDE_ROW_FIELDS if f not in r]
        assert not row_missing, (
            f"operator_closed row {r.get('symbol')} lacks {row_missing}")


def test_operator_closed_usd_is_the_sum_of_the_closes():
    """The purest measure of operator skill in the store, and it had no total.

    The engine picked the setup, the operator picked the exit. This money is
    counted in no other total anywhere — not in the engine's equity curve, not
    in the manual book, which reads exec facts only.
    """
    payload = _portfolio()
    total = Decimal(str(payload["operator_closed_usd"]))
    visible = sum((Decimal(str(o["usd_at_close"]))
                   for o in payload["operator_closed"]
                   if o.get("usd_at_close") is not None), Decimal(0))
    if len(payload["operator_closed"]) < 20:
        # Not truncated, so the sum and the rows on screen cover the same set.
        assert total == visible, (
            f"operator_closed_usd {total} against {visible} in the rows")
    else:
        # `operator_closed` is capped at 20; the total is over ALL of them, the
        # same rule `journal_total` follows. It may exceed what is on screen —
        # it may never be less.
        assert abs(total) >= abs(visible) or total == visible


def test_operator_closed_counts_the_closes_it_cannot_price():
    payload = _portfolio()
    n = payload["operator_closed_no_usd"]
    assert isinstance(n, int), f"operator_closed_no_usd is {n!r}"
    assert n >= 0


def test_no_money_field_is_ever_a_bare_zero_standing_in_for_absent():
    """The one rule under all of the above, stated once.

    Every field here is either a real figure or null. None of them may be 0 as
    a way of saying "we do not know", because on a money surface 0 is a claim:
    it says the trading broke even.
    """
    book, portfolio = _book(), _portfolio()
    if book["n"] == 0:
        assert book["total_pnl_usd"] is None
        assert book["expectancy_r"] is None
    if not portfolio["operator_closed"]:
        assert portfolio["operator_closed_usd"] == 0.0, (
            "no closes is a real zero — but only when there are no closes")
