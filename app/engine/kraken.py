"""Kraken Futures adapter — market data and ranking. No credentials, no orders.

Operator ruling 2026-07-30: **use Kraken.** The reason is regulatory rather than
technical. The entire traded universe has been Phemex since S34, and the
redesign plan's open question #1 — "Phemex may restrict US users, operator's
call" — went unanswered for two days while every trade in the book depended on
the answer. Kraken runs CFTC-regulated perpetual futures for US traders, which
converts that open question into a settled one.

Scope of THIS module, identical to `phemex.py`: public market data only. It
reads candles, instruments and 24h turnover. It holds no credentials, signs
nothing, and cannot place an order.

Endpoint contract VERIFIED against the live API 2026-07-30:
  GET /derivatives/api/v3/instruments      -> instruments[]; 281 tradeable perps,
                                              type 'flexible_futures', symbols
                                              like PF_XBTUSD
  GET /derivatives/api/v3/tickers          -> tickers[] with `volumeQuote`
                                              (24h USD notional — exactly the
                                              ranking input, no price*volume
                                              multiply needed)
  GET /api/charts/v1/trade/{sym}/{res}?from=&to=
                                           -> candles[] {time, open, high, low,
                                              close, volume}
All five resolutions this project uses are NATIVE here (15m/1h/4h/1d/1w), unlike
both other venues — but see `native_tfs` below for why that is not taken up.

Two things the live check settled that were assumptions elsewhere:

  · `countriesBanned` is **empty** on PF_XBTUSD, and no perp on the venue flags
    US. That is a data point, not legal advice, and it is recorded rather than
    interpreted.
  · The instrument's own margin schedule reports `maintenanceMargin: 0.005` at
    the first tier — the exact figure `venues.liquidation_price` has been
    assuming as a conservative default. The model was right; now it is
    corroborated by the venue rather than by a guess.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal

API = "https://futures.kraken.com"
VENUE = "kraken-perp"
_UA = {"User-Agent": "snipersight/0.1"}

QUOTE = "USD"

# Kraken's own resolution names, mapped from ours. Kept as a table rather than a
# lowercase() call because the two vocabularies agreeing today is a coincidence,
# not a contract.
RESOLUTION = {"5m": "5m", "15m": "15m", "1H": "1h", "4H": "4h",
              "1D": "1d", "1W": "1w"}
TF_SECONDS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400,
              "1D": 86400, "1W": 604800}

# Kraken serves ALL FIVE timeframes natively. We still import only these three
# and let the aggregator build 4H and 1W, for the same reason recorded in
# `importer.native_tfs` for Phemex: a natively-fetched 4H would occupy the same
# (symbol, tf, open_ts) row the aggregator writes, and two writers for one bucket
# is how they disagree at a gap and the audit reports a conflict it cannot
# explain. One saved request is not worth a second write path.
NATIVE_TFS = {"5m": 300, "15m": 900, "1H": 3600, "1D": 86400}

MAX_CANDLES_PER_REQ = 5000

# Same reasoning as phemex.RANK_RPS: the limiter is process-global but not
# machine-global, and both the scanner and the API server hit this venue.
RANK_RPS = 5.0
RANK_RETRIES = 5
RANK_BACKOFF = 1.0
RETRY_CODES = (429, 500, 502, 503, 504)

LAST_RANK_HEALTH = {"attempted": 0, "succeeded": 0, "failed": 0}


class _RateLimiter:
    """Shared spacing. A per-worker sleep still bursts N requests at once, so
    the gate has to be global to the process."""

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
    """Throttled GET with backoff. A dropped symbol is indistinguishable from an
    illiquid one, so retrying is not optional."""
    last = None
    for attempt in range(retries + 1):
        _LIMITER.acquire()
        try:
            req = urllib.request.Request(API + path, headers=_UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
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


def listed_symbols() -> list[str]:
    """Every USD-quoted perpetual the venue NAMES, tradeable or not.

    `list_products` skips anything not `tradeable` because it feeds a tradeable
    universe. `tradeable: false` is a HALT and is kept here: a halted
    instrument is still listed and still serves history, and reading a halt as
    a delisting would call live, repairable candle holes unrepairable.
    `isExpired` is the venue's end-of-life marker and is the one exclusion.
    (On 2026-09-01 all 274 PF_ instruments were tradeable and unexpired, so the
    distinction costs nothing today and exists for the day it does not.)
    """
    data = _get("/derivatives/api/v3/instruments") or {}
    return [i["symbol"] for i in data.get("instruments") or []
            if i.get("symbol", "").startswith("PF_")
            and i.get("symbol", "").upper().endswith(QUOTE)
            and not i.get("isExpired")]


def list_products() -> list[dict]:
    """Tradeable USD-quoted perpetuals, normalised to the fields we care about.

    `countriesBanned` is carried through untouched. This module records what the
    venue says about access; deciding what it means for a given operator is not
    a market-data question.
    """
    data = _get("/derivatives/api/v3/instruments") or {}
    out = []
    for i in data.get("instruments") or []:
        sym = i.get("symbol", "")
        if not i.get("tradeable") or i.get("isExpired"):
            continue
        if not sym.startswith("PF_") or not sym.upper().endswith(QUOTE):
            continue                      # PF_ = perpetual, USD-quoted only
        out.append({
            "symbol": sym,
            "base": i.get("base"),
            "tick_size": i.get("tickSize"),
            "contract_size": i.get("contractSize"),
            "countries_banned": i.get("countriesBanned") or [],
            "margin_levels": i.get("marginLevels") or [],
        })
    return out


def maintenance_margin(symbol: str) -> Decimal | None:
    """First-tier maintenance margin as the venue publishes it.

    `venues.liquidation_price` has assumed 0.005 as a conservative default since
    S32. Kraken publishes 0.005 at tier one for PF_XBTUSD, so on this venue the
    assumption can be replaced by the venue's own number instead of trusted.
    Returns None rather than a guess when the schedule is absent.
    """
    for p in list_products():
        if p["symbol"] != symbol:
            continue
        for tier in p["margin_levels"]:
            mm = tier.get("maintenanceMargin")
            if mm is not None:
                return Decimal(str(mm))
    return None


def rank_by_volume(progress=None) -> list[tuple[str, float]]:
    """USD perps ranked by 24h quote volume.

    `volumeQuote` is already notional in USD, so unlike the Coinbase sweep there
    is no price*volume multiply and no per-symbol fan-out — one request ranks the
    whole venue, which removes the partial-coverage failure mode that forced
    `universe.MIN_RANK_COVERAGE` to exist.
    """
    global LAST_RANK_HEALTH
    listed = {p["symbol"] for p in list_products()}
    if progress:
        progress(1, 2)
    payload = _get("/derivatives/api/v3/tickers") or {}
    ranked, skipped = [], 0
    for t in payload.get("tickers") or []:
        sym = t.get("symbol")
        if sym not in listed:
            continue
        try:
            ranked.append((sym, float(t["volumeQuote"])))
        except (KeyError, TypeError, ValueError):
            skipped += 1
    ranked.sort(key=lambda x: -x[1])
    LAST_RANK_HEALTH = {"attempted": len(listed), "succeeded": len(ranked),
                        "failed": skipped, "sample_failures": []}
    if progress:
        progress(2, 2)
    return ranked


def funding_rate(symbol: str) -> float | None:
    """Current funding rate, or None if the venue does not say.

    Only the CURRENT rate is available — as on Phemex, there is no historical
    series here, which is why `execsim` prices funding from a declared constant
    and says so rather than pretending to measure it.
    """
    payload = _get("/derivatives/api/v3/tickers") or {}
    for t in payload.get("tickers") or []:
        if t.get("symbol") == symbol:
            try:
                return float(t["fundingRate"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def fetch_candles(symbol: str, tf: str, start_ts: int, end_ts: int) -> list[dict]:
    """Closed candles in [start_ts, end_ts), ascending, as store-shaped dicts.

    Only CLOSED buckets are returned. A forming candle has a moving high, low
    and close, and admitting one would let an engine confirm structure against a
    bar that has not finished — the determinism model forbids it.

    Kraken timestamps are MILLISECONDS. Every other venue here is in seconds, so
    a missed division would silently place every bar 55,000 years in the future
    and the causality checks would never fire, because they compare timestamps
    to each other rather than to a plausible range.

    The walk is bounded by a request BUDGET fixed before it starts. It used to be
    re-evaluated every pass as `guard <= 2 + (end_ts - cursor) // window`, and
    that allowance SHRINKS by one for every pass `guard` grows by one — so the
    two met at the halfway mark and the walk abandoned the rest of the range
    having said nothing. From ANY start date, not only 1970: a span needing N
    windows always stopped near N/2. It went unnoticed because every floor in
    `ingest.history_floor` fits inside a single 5000-bucket window (N = 0), so
    the arithmetic never got a chance to be wrong until a cold symbol asked for
    history from the epoch. Widening DAILY_SINCE or importing 4H natively would
    have re-armed it.

    Exhausting the budget is now LOUD. That is the half that actually cost us:
    the old guard returned a short list indistinguishable from "the venue has
    no more data", and `importer.backfill` then recorded every unreached bucket
    as a gap — 1,983,795 of them in one 15m run.
    """
    if tf not in RESOLUTION:
        raise ValueError(f"unsupported tf {tf}")
    gran = TF_SECONDS[tf]
    res = RESOLUTION[tf]
    now = int(time.time())
    closed_until = now - now % gran        # start of the still-forming bucket
    end_ts = min(end_ts, closed_until)
    out: list[dict] = []
    cursor = start_ts - start_ts % gran
    window = gran * MAX_CANDLES_PER_REQ
    # Two requests per window, not one: a window holding only a few candles
    # advances the cursor to the last of THEM rather than to its end, and the
    # following pass finds the remainder empty and skips it. Termination does
    # not rest on this number — the empty-window branch and the no-forward-
    # progress break below already guarantee it. This is a backstop against a
    # logic error, so it is sized never to fire on a healthy walk.
    budget = 2 * (2 + max(0, end_ts - cursor) // window)
    walked = 0
    while cursor < end_ts:
        if walked >= budget:
            from .runlog import get_logger
            get_logger().warning(
                f"kraken {symbol} {tf}: request budget ({budget}) exhausted at "
                f"{cursor} of {end_ts} — returning {len(out)} candles for a "
                f"PARTIAL span. Everything past {cursor} is unreached, not "
                f"absent; do not read it as a venue gap.")
            break
        walked += 1
        window_end = min(cursor + window, end_ts)
        payload = _get(f"/api/charts/v1/trade/{symbol}/{res}"
                       f"?from={cursor}&to={window_end}")
        rows = (payload or {}).get("candles") or []
        if not rows:
            # An empty window means "nothing listed yet in THIS range", not "no
            # data at all" — the exact bug that gave DEXEUSDT zero daily candles
            # on Phemex (S34). Skip the span and keep looking.
            cursor = window_end
            continue
        for c in rows:
            ts = int(c["time"]) // 1000    # ms -> s
            if ts < start_ts or ts >= end_ts:
                continue
            out.append({"open_ts": ts, "open": str(c["open"]),
                        "high": str(c["high"]), "low": str(c["low"]),
                        "close": str(c["close"]), "volume": str(c["volume"])})
        last_ts = int(rows[-1]["time"]) // 1000
        if last_ts + gran <= cursor:       # no forward progress — stop, never spin
            break
        cursor = last_ts + gran
    out.sort(key=lambda c: c["open_ts"])
    seen, dedup = set(), []
    for c in out:
        if c["open_ts"] in seen:
            continue
        seen.add(c["open_ts"])
        dedup.append(c)
    return dedup
