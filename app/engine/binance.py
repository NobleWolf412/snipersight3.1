"""Binance public market data — REFERENCE feeds only. Nothing trades here.

This adapter exists for one purpose: serving the deepest venue's candle
series for thin markets, stored under `@`-suffixed reference keys (see
`venues.REFERENCE`). It is deliberately not a Venue in `venues.ALL` — it has
no leverage, no shorts flag, no fees and no book, because no order may ever
be sized against it. `venues.venue_for` raises on every reference key, and
that raise is the enforcement.

THE HOST IS THE PUBLIC DATA MIRROR, not the exchange API. `api.binance.com`
refuses US connections outright (HTTP 451, probed 2026-08-09 from the
operator's machine), while `data-api.binance.vision` is Binance's keyless
public mirror of the same global-exchange market data and answered the same
probe with live candles. binance.us was rejected the same day for the same
reason it exists: thinner books — its BICO market last printed in mid-2023,
which is exactly the starvation this feed is meant to cure.

Prices arrive as STRINGS in the JSON and stay strings end to end — no float
ever touches them (`parse_float=Decimal` guards the fields that are not
strings, i.e. nothing we read). Timestamps are MILLISECONDS, like Kraken's,
and are divided down at the edge for the same reason recorded there: every
consumer compares timestamps to each other, so a missed division would be
silently self-consistent.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal

API = "https://data-api.binance.vision"
VENUE = "binance-spot"
_UA = {"User-Agent": "snipersight/0.1"}

QUOTE = "USDT"   # every mapped reference symbol is USDT-quoted; recorded on
                 # basis facts so grading can see the USD/USDT blend (§risk 2
                 # of the 2026-08-09 scoping: normalising is an operator call)

RESOLUTION = {"5m": "5m", "15m": "15m", "1H": "1h", "4H": "4h",
              "1D": "1d", "1W": "1w"}
TF_SECONDS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400,
              "1D": 86400, "1W": 604800}

# Same policy as kraken.py/phemex.py, same reason: the venue serves 4H and 1W
# natively and we refuse them, because a natively-fetched aggregate would
# occupy the same (symbol, tf, open_ts) row the aggregator writes, and two
# writers for one bucket is how they disagree at a gap.
NATIVE_TFS = {"5m": 300, "15m": 900, "1H": 3600, "1D": 86400}

MAX_CANDLES_PER_REQ = 1000

# The mirror shares the exchange's 6000-weight/min budget and a klines call
# weighs 2, so the ceiling is ~50 requests/second. 2 rps is two orders of
# magnitude under it — reference feeds are a background trickle, and the
# steady-state cycle needs single-digit requests.
RANK_RPS = 2.0
RANK_RETRIES = 5
RANK_BACKOFF = 1.0
# 418 is Binance's "auto-banned for ignoring 429" — if it ever appears the
# only correct response is to back off harder, same as 429.
RETRY_CODES = (418, 429, 500, 502, 503, 504)


class _RateLimiter:
    """Shared spacing — same shape as kraken.py's, same reason: a per-worker
    sleep still bursts N requests at once, so the gate is process-global."""

    def __init__(self, rps: float):
        self._gap = 1.0 / rps
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + self._gap
        if wait:
            time.sleep(wait)


_LIMITER = _RateLimiter(RANK_RPS)


def _get(path: str, retries: int = RANK_RETRIES):
    """Throttled GET with backoff. Same contract as kraken._get: a dropped
    request is indistinguishable from an empty range, so retrying is not
    optional."""
    last = None
    for attempt in range(retries + 1):
        _LIMITER.acquire()
        try:
            req = urllib.request.Request(API + path, headers=_UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode(), parse_float=Decimal)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRY_CODES:
                raise
            delay = RANK_BACKOFF * (2 ** attempt)
        except urllib.error.URLError as exc:
            last = exc
            delay = RANK_BACKOFF * (2 ** attempt)
        if attempt < retries:
            time.sleep(delay)
    raise last


def fetch_candles(symbol: str, tf: str, start_ts: int, end_ts: int) -> list[dict]:
    """Closed candles in [start_ts, end_ts), ascending, as store-shaped dicts.

    `symbol` is Binance's own spelling (BICOUSDT), i.e. the part of the
    reference key before the `@` — the caller strips it.

    The walk is bounded by a request budget fixed before it starts, for the
    reason kraken.py documents at length: a budget re-derived per pass shrank
    as the walk advanced and silently abandoned half of any long range, and
    the short result read as "the venue has no more data" — which backfill
    then recorded as ~2M fabricated gaps. Exhausting the budget is LOUD.
    """
    if tf not in NATIVE_TFS:
        # The refusal the NATIVE_TFS comment promises, performed rather than
        # implied. importer.backfill refuses aggregate tfs on its own, but a
        # direct caller used to get a native 4H here — and a natively-fetched
        # aggregate occupying the aggregator's row is the two-writers defect
        # this whole codebase keeps a rule against.
        raise ValueError(f"{tf} is not fetched natively; the aggregator owns "
                         f"4H/1W — see NATIVE_TFS")
    gran = TF_SECONDS[tf]
    now = int(time.time())
    closed_until = now - now % gran        # start of the still-forming bucket
    end_ts = min(end_ts, closed_until)
    out: list[dict] = []
    cursor = start_ts - start_ts % gran
    window = gran * MAX_CANDLES_PER_REQ
    budget = 2 * (2 + max(0, end_ts - cursor) // window)
    walked = 0
    while cursor < end_ts:
        if walked >= budget:
            from .runlog import get_logger
            get_logger().warning(
                f"binance {symbol} {tf}: request budget ({budget}) exhausted "
                f"at {cursor} of {end_ts} — returning {len(out)} candles for "
                f"a PARTIAL span. Everything past {cursor} is unreached, not "
                f"absent; do not read it as a venue gap.")
            break
        walked += 1
        window_end = min(cursor + window, end_ts)
        rows = _get(f"/api/v3/klines?symbol={symbol}"
                    f"&interval={RESOLUTION[tf]}"
                    f"&startTime={cursor * 1000}"
                    f"&endTime={window_end * 1000 - 1}"
                    f"&limit={MAX_CANDLES_PER_REQ}") or []
        advanced = cursor
        for row in rows:
            # [openTime(ms), open, high, low, close, volume, closeTime, ...]
            # — prices are already strings in the JSON.
            t = int(row[0]) // 1000
            if t + gran > closed_until:
                continue                   # forming bucket — never emit (§5)
            if not (cursor <= t < window_end):
                continue
            out.append({"open_ts": t, "open": str(row[1]), "high": str(row[2]),
                        "low": str(row[3]), "close": str(row[4]),
                        "volume": str(row[5])})
            advanced = t + gran
        if len(rows) < MAX_CANDLES_PER_REQ:
            cursor = window_end            # venue has nothing more in-window
        elif advanced > cursor:
            cursor = advanced
        else:
            break                          # no forward progress — stop, loudly short
    return out
