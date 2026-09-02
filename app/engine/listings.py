"""Venue listing record — the store's own answer to "does this market exist".

Why this module exists (measured, not assumed): the quality audit blocks a
symbol whose candle history has unexplained holes, and that blocker is correct
for a live market — the next import can repair it. For a DELISTED market it is
unrepairable by construction, so it halts the store forever with no action
available to the operator. CRVUSDT sat delisted from Phemex doing exactly that.

Telling the two apart needs a fact the store did not record. The universe fact
looks like the obvious source and is not: `universe.refresh` builds `members`
from the top `top_n` of the ranking (default 20), so on 2026-09-01 Phemex
listed 101 perps while `members` could hold 20 — AAVEUSDT, ZECUSDT, LITUSDT and
ONDOUSDT were live, listed and absent from it. Reading absence as delisting
demoted 81 live markets and was reverted (ba9d8fb).

So this module asks the venues' PRODUCT endpoints, which are the listing, and
appends what they say. It holds no credentials and places no orders.

THE ASYMMETRY IS THE WHOLE DESIGN. `listed_on_venue` returns False only on
positive evidence that this venue answered and did not name the symbol.
Every other outcome — never swept, sweep failed, record stale, venue unknown —
returns None, and a None caller must keep whatever guard it was considering
lifting. The failure this protects against is concrete: `rank_all_venues`
catches a Phemex outage and continues SPOT-ONLY, while the MIN_RANK_COVERAGE
guard measures only the Coinbase sweep, so a total perp outage records a
healthy-looking universe with no perps in it. Under a naive reader every USDT
perp in the book would read as delisted in the same hour the outage stopped
their imports and created the very holes being judged.
"""
import json
import time

from . import kraken, phemex, store, universe, venues
from .runlog import RunRecorder, get_logger

LISTINGS_VERSION = "listings-v0.1-draft"

# Several multiples of universe.REFRESH_SECONDS (3600). A record older than
# this means the sweep stopped running, which is not evidence about any venue's
# listing — a stale "not listed" would outlive the outage that caused it.
MAX_LISTING_AGE = 6 * 3600

FACT_KIND = "venue_listing"

# KNOWN COST, recorded rather than hidden. `market_time=now` is what makes
# freshness real — a content-hash-identical sweep would otherwise dedupe into
# the first row and `latest()` would report the age of an answer from days ago.
# The price is that every sweep appends: 3 rows/hour, and Coinbase's ~400 ids
# are ~5KB, so roughly 26k rows and tens of MB a year. `prune.DERIVED_KINDS`
# cannot help — it retires SUPERSEDED VERSIONS of per-symbol derived facts, and
# every row here is current under one version. Bounding this needs its own
# retention rule (only the newest row per venue is ever read); it is not
# urgent at this rate, and a wrong prune here would silently blind the audit.


# LISTED, never "tradeable right now". Each adapter's `list_products` drops
# anything not currently tradeable because it feeds a tradeable universe; a
# maintenance halt or a cancel-only wind-down would then read as a DELISTING,
# and this module's False answer would tell the operator a live market's
# repairable candle holes are unrepairable. These three read the venue's
# naming and nothing else.
def _phemex_symbols() -> list[str]:
    return phemex.listed_symbols()


def _kraken_symbols() -> list[str]:
    return kraken.listed_symbols()


def _coinbase_symbols() -> list[str]:
    return [p["id"] for p in universe.coinbase_products()]


# (venue key, fetch, endpoint) — the key comes from the venue contract rather
# than a local literal so the symbol->venue map and this record cannot drift
# into two spellings of the same venue.
SOURCES = (
    (venues.PHEMEX_PERP.key, _phemex_symbols, "/public/products"),
    (venues.COINBASE_SPOT.key, _coinbase_symbols, "/products"),
    (venues.KRAKEN_PERP.key, _kraken_symbols, "/derivatives/api/v3/instruments"),
)


def sweep(con, now: int | None = None, beat=None) -> dict:
    """Ask every venue what it lists and append one fact per venue.

    A FAILED venue still writes its fact, carrying `swept: false` and the
    error. Writing nothing on failure is indistinguishable from "the sweep
    never ran", and that ambiguity is the entire defect this module exists to
    remove — a reader could not tell an outage from a delisting, which is how
    one bad HTTP sweep would retire a whole book.

    Runs inside a RunRecorder because a fact with no producer run is reported
    as UNATTRIBUTED_CURRENT_FACTS at BLOCKED — writing these unattributed would
    halt the store on the first cycle after they landed.
    """
    now = int(time.time()) if now is None else int(now)
    out: dict[str, dict] = {}
    with RunRecorder(con, "listings", LISTINGS_VERSION, "PORTFOLIO", "ALL") as rec:
        for key, fetch, source in SOURCES:
            # Beat from INSIDE the loop, not around it. Three venues black-
            # holing connections is ~375s of stacked timeouts and backoff,
            # past watchdog.SCANNER_DARK_AFTER_S (300) — a silent sweep would
            # fire "Scanner has stopped" at 3am while it was merely waiting.
            if beat:
                beat(f"listing sweep {key}")
            try:
                symbols = sorted({str(s) for s in fetch()})
                if not symbols:
                    # A venue that answers with an empty product list is
                    # degraded, not empty of markets. Recorded as unswept so no
                    # reader can conclude every market on it retired at once.
                    raise ValueError("venue returned an empty product list")
                payload = {"venue": key, "venues_version": venues.VENUES_VERSION,
                           "swept": True, "symbols": symbols,
                           "n_listed": len(symbols), "source": source}
            except Exception as exc:
                payload = {"venue": key, "venues_version": venues.VENUES_VERSION,
                           "swept": False, "n_listed": 0, "source": source,
                           "error": f"{type(exc).__name__}: {exc}"}
                # Loud-fallback rule: the degraded path says so, in the log and
                # in the fact. A silent one would look like a clean sweep that
                # happened to list nothing.
                get_logger().warning(
                    f"listings: {key} sweep FAILED ({type(exc).__name__}: {exc}) "
                    f"— recorded swept=false; nothing on this venue can be "
                    f"judged delisted until it answers again")
            if store.insert_fact(con, symbol="PORTFOLIO", tf="ALL",
                                 kind=FACT_KIND, market_time=now,
                                 confirmed_at=now,
                                 algo_version=LISTINGS_VERSION,
                                 payload=payload):
                rec.n_new_facts += 1
            out[key] = payload
        rec.notes = ", ".join(
            f"{k}={'?' if not p['swept'] else p['n_listed']}" for k, p in out.items())
    con.commit()
    return out


def latest(con, venue_key: str, now: int | None = None) -> dict | None:
    """The most recent usable sweep record for one venue AS OF `now`, or None.

    None covers every "cannot tell" case: no record, no record yet knowable at
    `now`, a record older than MAX_LISTING_AGE, and a record whose sweep failed.

    `confirmed_at <= now` is the constitution's third rule — confirmed_at is
    when the engine could first have known, and nothing may act on a fact
    before it was knowable. Every caller passes a live clock today, so this
    excludes nothing in normal operation; it is not a new judgement and no
    version moves for it. What it removes is a state the code could reach and
    had no answer for: if the host clock steps BACKWARDS — an NTP correction, a
    VM restore, a DST bug — rows written minutes ago are suddenly dated ahead
    of `now`, and the staleness arithmetic below turns them into a NEGATIVE
    age, which is younger than any window and so always passes. A skewed clock
    would have been the one condition under which a stale listing record could
    never expire. Filtered here instead, the same skew answers None, and None
    keeps whatever guard the caller was considering lifting.
    """
    now = int(time.time()) if now is None else int(now)
    row = con.execute(
        "SELECT payload, confirmed_at FROM facts WHERE kind=? AND algo_version=? "
        "AND json_extract(payload,'$.venue')=? AND confirmed_at<=? "
        "ORDER BY confirmed_at DESC, id DESC LIMIT 1",
        (FACT_KIND, LISTINGS_VERSION, venue_key, now)).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except ValueError:
        return None
    if now - int(row[1]) > MAX_LISTING_AGE:
        return None
    if not payload.get("swept") or not payload.get("symbols"):
        return None
    return payload


def listed_on_venue(con, symbol: str, now: int | None = None) -> bool | None:
    """True / False / None — does this symbol's venue still list it?

    False REQUIRES positive evidence: this venue was swept, answered, and did
    not name the symbol. Anything else is None. A caller lifting a guard on
    False must leave the guard exactly as it was on None.
    """
    if venues.is_reference_key(symbol):
        # A reference key names its own venue in its tail and is never a
        # universe member; the reference-series checks own its staleness.
        return None
    try:
        venue = venues.venue_for(symbol)
    except ValueError:
        return None
    payload = latest(con, venue.key, now)
    if payload is None:
        return None
    return symbol in set(payload["symbols"])
