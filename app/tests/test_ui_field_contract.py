"""The UI may only read fields its endpoint actually emits.

The Results page read `r.net_r ?? r.total_r ?? 0` and `r[key]` where `key` was
'symbol'/'strategy'. `/api/performance` has never emitted any of those four
names — it keys rows `key` and reports R as `sum_r`. Both reads fell through,
so every row rendered an em-dash and `+0.00R` in GREEN. Measured 2026-07-30:
a -3.91 R forward book displayed as break-even, with `n` correct so the row
looked alive rather than broken.

That is the whole failure mode: a missing number defaulting to zero, and zero
reading as flat rather than as absent. Type-checking would not have caught it
(both sides are plain JSON), and neither would coverage — the code ran, every
time, and produced a confident wrong answer.

So this test compares the two directly: parse the field names the JS reads off
each payload, call the endpoint, and require every name to exist. It is
deliberately a PYTHON test rather than a JS one — `test_ticket_math.js` asserts
the ticket's fee maths against a constant copied from the engine into the test
file, which cannot fail when the engine moves. A contract test has to hold the
two real artifacts against each other.
"""
import json
import re
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402

STATIC = APP / "static"


def _client():
    return TestClient(server.app)


def _reads_in(js: str, func: str) -> set[str]:
    """Field names read off the row variable inside one JS function body.

    Scoped to the function so an unrelated `r.foo` elsewhere in the file cannot
    make this pass or fail by accident.
    """
    i = js.find(f"function {func}(")
    assert i >= 0, f"{func}() not found — did it get renamed?"
    depth, j, started = 0, i, False
    while j < len(js):
        if js[j] == "{":
            depth += 1
            started = True
        elif js[j] == "}":
            depth -= 1
            if started and depth == 0:
                break
        j += 1
    body = js[i:j]
    names = set(re.findall(r"\br\.([A-Za-z_][A-Za-z0-9_]*)", body))
    names |= set(re.findall(r"\br\[['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\]", body))
    return names


def test_performance_rows_expose_every_field_the_page_reads():
    js = (STATIC / "shell.js").read_text(encoding="utf-8")
    reads = _reads_in(js, "perfRows")
    assert reads, "perfRows reads nothing off the row — the parse is broken"

    payload = _client().get("/api/performance").json()
    buckets = ["by_symbol", "by_strategy", "shadow_by_symbol", "shadow_by_strategy"]
    rows = [r for b in buckets for r in (payload.get(b) or [])]
    if not rows:
        pytest.skip("no closed trades in this store — nothing to contract-check")

    emitted = set()
    for r in rows:
        emitted |= set(r)
    missing = reads - emitted
    assert not missing, (
        f"shell.js perfRows reads {sorted(missing)} off /api/performance rows, "
        f"which emit {sorted(emitted)}. A field the endpoint does not send "
        f"renders as its fallback — and a numeric fallback of 0 reads as "
        f"break-even, not as missing.")


def test_performance_never_reports_a_loss_as_zero():
    """The specific regression: `+(undefined ?? 0)` is 0, and 0 renders green.

    Asserts the payload carries a real R figure on every row, so the page has
    something to render other than a fallback.
    """
    payload = _client().get("/api/performance").json()
    rows = [r for b in ("by_symbol", "by_strategy") for r in (payload.get(b) or [])]
    for r in rows:
        assert "sum_r" in r and r["sum_r"] is not None, (
            f"row {r.get('key')} carries no sum_r; the page would render 0.00R")
        assert r.get("n"), f"row {r.get('key')} has trades but n={r.get('n')}"


def test_shadow_trades_are_not_in_the_track_record():
    """A SHADOW symbol is never sizeable — `risk.py` rejects every intent with
    NOT_IN_POINT_IN_TIME_UNIVERSE. Counting its simulated trades into the
    operator's record reports a book that could not have been placed.

    Measured 2026-07-30: 5 of the 6 baseline trades (83%) were Kraken PF_*
    shadow symbols. Only the $-column excluded them, because `sized` reads the
    risk decision and the R-columns did not.
    """
    from engine import store, universe
    con = store.connect()
    try:
        shadow = set(universe.shadow_symbols(con))
    finally:
        con.close()
    if not shadow:
        pytest.skip("no shadow venue configured in this store")

    payload = _client().get("/api/performance").json()
    traded_keys = {r["key"] for r in (payload.get("by_symbol") or [])}
    leaked = traded_keys & shadow
    assert not leaked, (
        f"shadow symbols {sorted(leaked)} appear in the traded track record")

    # ...and they must still be VISIBLE somewhere, or a warmed venue's evidence
    # silently disappears and nothing can justify admitting it.
    assert "shadow_by_symbol" in payload, (
        "shadow trades were removed from the record but not reported "
        "separately — that trades one lie for a blind spot")


def test_edge_stats_defaults_to_the_tradeable_book():
    """This panel renders beside the equity curve, which implies they describe
    the same trades. Until 2026-07-30 they did not: 276 of 639 (43.2%) were
    Kraken SHADOW."""
    r = _client().get("/api/edge-stats?resamples=500").json()
    assert r["filters"]["venue_state"] == "TRADED"
    counts = r["counts"]
    assert "shadow_venue" in counts and "traded_venue" in counts, (
        "the split must be reported even when filtered, or a filtered report "
        "cannot say what it left out")
    if r.get("book"):
        assert r["book"]["n"] == counts["traded_venue"]
