"""Phemex USDT-perpetual adapter — market data and ranking.

Why this venue exists in the project (measured, not assumed):
  · Only 19 Coinbase USD pairs clear the $3M liquidity floor, so the spot
    universe cannot be widened — the floor binds before TOP_N does.
  · 31% of all validated setups (44 of 143) are SHORTs, and every one is
    rejected because spot cannot short.
Together those capped throughput at roughly one setup a week, which cannot
produce forward evidence on any useful timescale. Perps lift both ceilings.

Scope of THIS module: public market data only. It reads candles, products and
24h turnover. It holds no credentials, signs nothing, and cannot place an
order. Live order submission stays locked behind forward evidence, and API keys
are the operator's to enter into OS credential storage — never handled here,
never logged, never stored in the fact store.

Endpoint contract verified against the live API 2026-07-29:
  GET /public/products                 -> data.perpProductsV2[]
  GET /md/v2/ticker/24hr/all           -> result[] with turnoverRv (quote volume)
  GET /exchange/public/md/v2/kline/list?symbol&resolution&from&to
      -> data.rows[] ascending, each [ts, res, lastClose, open, high, low, close, vol]
The v1 kline paths and the v2 `limit` form both return HTTP 400 — `kline/list`
with from/to is the one that works.
"""
import json
import threading
import time
import urllib.error
import urllib.request

API = "https://api.phemex.com"
VENUE = "phemex-perp"
_UA = {"User-Agent": "snipersight/0.1"}

# Perps trade both ways and quote in USDT.
QUOTE = "USDT"
SETTLE = "USDT"

# Same shape as importer.TF_SECONDS so timeframe handling is venue-agnostic.
TF_SECONDS = {"15m": 900, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}
# Phemex serves 4H natively, unlike Coinbase which forces aggregation.
NATIVE_TFS = {"15m": 900, "1H": 3600, "4H": 14400, "1D": 86400}
MAX_ROWS_PER_REQ = 1000

# 5/s, not 10: the limiter is process-GLOBAL but not machine-global, and both
# the scanner and the API server hit this venue. Two processes at 10/s each
# measured sustained HTTP 429 that outlasted the retries and killed a whole
# scan cycle (2026-07-29 21:44). Halving leaves headroom for both.
RANK_RPS = 5.0
RANK_RETRIES = 5
RANK_BACKOFF = 1.0
RETRY_CODES = (429, 500, 502, 503, 504)

LAST_RANK_HEALTH = {"attempted": 0, "succeeded": 0, "failed": 0}


class _RateLimiter:
    """Shared spacing, same reasoning as universe._RateLimiter: a per-worker
    sleep still bursts N requests at once, so the gate must be process-global."""

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
    """Throttled GET with backoff. See universe._get — a dropped symbol is
    indistinguishable from an illiquid one, so retrying is not optional."""
    last = None
    for attempt in range(retries + 1):
        _LIMITER.acquire()
        try:
            req = urllib.request.Request(API + path, headers=_UA)
            with urllib.request.urlopen(req, timeout=20) as r:
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


def list_products() -> list[dict]:
    """Live USDT-settled perpetuals, normalised to the fields we care about."""
    data = (_get("/public/products") or {}).get("data") or {}
    out = []
    for p in data.get("perpProductsV2") or []:
        if p.get("status") not in (None, "Listed"):
            continue
        if p.get("settleCurrency") != SETTLE or p.get("quoteCurrency") != QUOTE:
            continue
        out.append({
            "symbol": p["symbol"],                 # e.g. BTCUSDT
            "base": p.get("contractUnderlyingAssets") or p.get("baseCurrency"),
            "tick_size": p.get("tickSize"),
            "max_leverage": p.get("maxLeverage"),
            "funding_symbol": p.get("fundingRateSymbol"),
        })
    return out


def rank_by_volume(progress=None) -> list[tuple[str, float]]:
    """USDT perps ranked by 24h turnover in quote currency (USD-equivalent).

    One request for all tickers, so unlike the Coinbase sweep there is no
    per-symbol fan-out to rate-limit and no partial-coverage failure mode.
    """
    global LAST_RANK_HEALTH
    listed = {p["symbol"] for p in list_products()}
    if progress:
        progress(1, 2)
    payload = _get("/md/v2/ticker/24hr/all") or {}
    rows = payload.get("result") or payload.get("data") or []
    ranked, skipped = [], 0
    for r in rows:
        sym = r.get("symbol")
        if sym not in listed:
            continue
        try:
            ranked.append((sym, float(r["turnoverRv"])))
        except (KeyError, TypeError, ValueError):
            skipped += 1
    ranked.sort(key=lambda x: -x[1])
    LAST_RANK_HEALTH = {"attempted": len(listed), "succeeded": len(ranked),
                        "failed": skipped, "sample_failures": []}
    if progress:
        progress(2, 2)
    return ranked


def last_prices(symbols=None) -> dict:
    """Last traded price per perp, from the single 24h ticker call.

    One request covers every symbol, so a drift monitor costs one call per poll
    instead of one per symbol. `closeRp` is the last TRADED price: the same
    quantity the candle store holds as `close`, which is what makes a
    spot-vs-last-close comparison apples-to-apples. `markPriceRp` would not be —
    it is an index-anchored fair value that differs from traded price by design,
    so comparing it against a traded close would report drift that never happened.
    """
    payload = _get("/md/v2/ticker/24hr/all") or {}
    want = set(symbols) if symbols is not None else None
    out = {}
    for r in payload.get("result") or payload.get("data") or []:
        sym = r.get("symbol")
        if want is not None and sym not in want:
            continue
        try:
            out[sym] = float(r["closeRp"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def fetch_candles(symbol: str, tf: str, start_ts: int, end_ts: int) -> list[dict]:
    """Closed candles in [start_ts, end_ts), ascending, as store-shaped dicts.

    Only CLOSED buckets are returned. A forming candle has a moving high, low
    and close, and admitting one would let an engine confirm structure against
    a bar that has not finished — the determinism model forbids it.
    """
    if tf not in TF_SECONDS:
        raise ValueError(f"unsupported tf {tf}")
    gran = TF_SECONDS[tf]
    now = int(time.time())
    closed_until = now - now % gran          # start of the still-forming bucket
    end_ts = min(end_ts, closed_until)
    out: list[dict] = []
    cursor = start_ts - start_ts % gran
    windows = 0
    max_windows = 2 + (end_ts - cursor) // (gran * MAX_ROWS_PER_REQ)
    while cursor < end_ts and windows <= max_windows:
        windows += 1
        window_end = min(cursor + gran * MAX_ROWS_PER_REQ, end_ts)
        payload = _get(f"/exchange/public/md/v2/kline/list?symbol={symbol}"
                       f"&resolution={gran}&from={cursor}&to={window_end}")
        rows = ((payload or {}).get("data") or {}).get("rows") or []
        if not rows:
            # An empty window means "nothing listed yet in THIS range", not
            # "no data at all". Breaking here silently gave zero daily candles
            # to every symbol listed after the first window — and since daily
            # is the timeframe the history gate counts, those symbols sat in
            # WARMING forever. Skip the empty span and keep looking.
            cursor = window_end
            continue
        for row in rows:
            # [ts, resolution, lastClose, open, high, low, close, volume]
            ts = int(row[0])
            if ts < start_ts or ts >= end_ts:
                continue
            out.append({"open_ts": ts, "open": str(row[3]), "high": str(row[4]),
                        "low": str(row[5]), "close": str(row[6]),
                        "volume": str(row[7])})
        last_ts = int(rows[-1][0])
        if last_ts + gran <= cursor:         # no forward progress — stop, never spin
            break
        cursor = last_ts + gran
    out.sort(key=lambda c: c["open_ts"])
    # de-duplicate on open_ts; overlapping windows can repeat a boundary bar
    seen, dedup = set(), []
    for c in out:
        if c["open_ts"] in seen:
            continue
        seen.add(c["open_ts"])
        dedup.append(c)
    return dedup


def funding_rate(symbol: str) -> float | None:
    """Current funding rate for a perp, or None if the venue does not say.

    Funding is a real holding cost on perps and belongs in the cost model, not
    in a footnote — a position held across settlements pays it repeatedly.
    """
    payload = _get("/md/v2/ticker/24hr/all") or {}
    for r in payload.get("result") or []:
        if r.get("symbol") == symbol:
            for key in ("fundingRateRr", "predFundingRateRr"):
                try:
                    return float(r[key])
                except (KeyError, TypeError, ValueError):
                    continue
    return None
