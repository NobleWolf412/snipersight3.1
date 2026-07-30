"""Dynamic universe selection — top Coinbase USD pairs by live 24h volume.

Reconciled with the determinism model (§4/§7): the LIVE ranking is the only
network/time-varying step, and every selection is RECORDED as a `universe`
fact (rank, volume, decision, reason) so any past membership is reconstructable.
All reprocessing/backfill iterates symbols already in the store — deterministic.

Two-gate admission (structure edge needs history, not just liquidity):
  - liquid: 24h USD volume >= MIN_VOLUME_USD
  - warm:   >= MIN_DAILY_CANDLES daily candles in store (else backfilling)
A symbol that is liquid but not warm is ADMITTED-PENDING (kept in the universe,
backfilled, but not scanned for setups until warm). Below the floor -> rejected.

Ported lesson from the prior project's pair_selection.py: rank by liquidity,
refuse thin books ("NEAR ran $5M/24h with $2 at the touch" — structural stops
don't fill on illiquid pairs). Perp/leverage/CoinGecko machinery intentionally
dropped — we are Coinbase spot with a curated-by-liquidity pool.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import phemex, store
from .runlog import RunRecorder

# v0.2: the ranking sweep is throttled, retried, and now fails CLOSED on poor
# coverage. v0.1 emitted rankings built from ~72% of the market (the rest lost
# to HTTP 429), so membership — and therefore trade eligibility — varied run to
# run on identical market conditions. The admission RULES are unchanged; only
# the completeness of their input is. Version bumped because the outputs differ.
UNIVERSE_VERSION = "universe-v0.3-draft"
# v0.3: ranks across venues (spot + perps), deduped by underlying asset with the
# PERP preferred where a coin trades on both. Membership therefore differs from
# v0.2, hence the bump. SEED stays BTC/ETH spot — the golden-calibration anchors.
API = "https://api.exchange.coinbase.com"
TOP_N = 20
MIN_VOLUME_USD = 3_000_000        # daily-volume floor (structural stops must fill)
MIN_DAILY_CANDLES = 200           # ~structure-map warmup before a symbol is tradeable
REFRESH_SECONDS = 3600            # volume ranking barely moves intraday
SEED = ("BTC-USD", "ETH-USD")     # always-present anchors (golden-calibrated)
REQUEST_PAUSE = 0.15
RANK_WORKERS = 4
# v0.2: Coinbase's public endpoints allow roughly 10 requests/second per IP.
# Six workers firing 388 stats calls flat out measured 39% HTTP 429 — and a
# DIFFERENT third failed on every run, so "top 20 by volume" was really "top 20
# of whichever two thirds happened to answer". Membership churned 3-5 symbols
# between refreshes minutes apart, which made point-in-time eligibility — the
# gate on every trade — partly a coin flip. Throttled and retried below.
RANK_RPS = 10.0
RANK_RETRIES = 3
RANK_BACKOFF = 0.5
RETRY_CODES = (429, 500, 502, 503, 504)
# Below this coverage the ranking is not trustworthy enough to overwrite a good
# universe with. Measured clean runs sit at 100%.
MIN_RANK_COVERAGE = 0.97
# Perps are ranked alongside spot. Turned off, the universe is spot-only and the
# system behaves exactly as v0.2 did.
ENABLE_PERPS = True
LAST_RANK_HEALTH = {"attempted": 0, "succeeded": 0, "failed": 0}
_UA = {"User-Agent": "snipersight/0.1"}
# stablecoin bases have no tradeable structure (ported from prior project's
# _is_stable_base) — a ~$1 pegged asset must never enter the universe.
STABLE_BASES = {"USDT", "USDC", "DAI", "USDS", "PYUSD", "USDD", "TUSD",
                "FDUSD", "GUSD", "USDP", "EUROC", "EURC", "PAX", "BUSD"}


def _is_stable(pid: str) -> bool:
    return pid.split("-")[0].upper() in STABLE_BASES


class _RateLimiter:
    """Thread-safe minimum spacing between requests, shared by all rank workers.

    A per-worker sleep would not work: N workers each pausing 1/N of a second
    still bursts N requests at once. The gate has to be global to the process.
    """

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
    """Throttled GET with backoff on rate limits and transient server errors.

    Retrying matters as much as throttling: without it a single 429 silently
    drops that symbol from the ranking, and a dropped symbol is indistinguishable
    from a symbol with no volume.
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        _LIMITER.acquire()
        try:
            req = urllib.request.Request(API + path, headers=_UA)
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRY_CODES:
                raise
            retry_after = 0.0
            try:                      # servers may tell us exactly how long
                retry_after = float(exc.headers.get("Retry-After") or 0)
            except (TypeError, ValueError):
                pass
            delay = retry_after or RANK_BACKOFF * (2 ** attempt)
        except urllib.error.URLError as exc:
            last = exc
            delay = RANK_BACKOFF * (2 ** attempt)
        if attempt < retries:
            time.sleep(delay)
    raise last


def rank_by_volume(progress=None) -> list[tuple[str, float]]:
    """Live: all online USD spot pairs, ranked by 24h USD volume. Fail-soft.

    `progress(done, total)` is called during the sweep. Throttling to 10 req/s
    makes this a ~40s blocking call, which is long enough that a caller's
    liveness heartbeat needs to tick inside it rather than around it.
    """
    try:
        prods = _get("/products")
    except Exception:
        return []
    usd = [p["id"] for p in prods
           if p.get("quote_currency") == "USD" and p.get("status") == "online"
           and not p.get("trading_disabled") and not p.get("limit_only")
           and not p.get("auction_mode") and not _is_stable(p["id"])]
    # /products is NOT volume-ordered, so we must stat every online USD pair to
    # rank correctly (missing a high-volume pair like SOL/XRP would silently
    # shrink the universe). ~388 calls, hourly refresh — well within limits.
    global LAST_RANK_HEALTH
    rows, failed = [], []

    def stat(pid):
        s = _get(f"/products/{pid}/stats")
        return pid, float(s["last"]) * float(s["volume"])

    with ThreadPoolExecutor(max_workers=RANK_WORKERS) as pool:
        futures = {pool.submit(stat, pid): pid for pid in usd}
        for done, future in enumerate(as_completed(futures), 1):
            pid = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                failed.append({"symbol": pid, "error": type(exc).__name__})
            if progress and done % 20 == 0:
                progress(done, len(usd))
    LAST_RANK_HEALTH = {"attempted": len(usd), "succeeded": len(rows),
                        "failed": len(failed), "sample_failures": failed[:10]}
    if failed:
        from .runlog import get_logger
        get_logger().warning(
            f"universe rank coverage {len(rows)}/{len(usd)}; "
            f"{len(failed)} product stats failed")
    rows.sort(key=lambda r: -r[1])
    return rows


def _base_asset(symbol: str) -> str:
    """The underlying, so the same coin on two venues is one candidate."""
    if symbol.endswith("-USD"):
        return symbol[:-4]
    if symbol.endswith("USDT"):
        return symbol[:-4]
    return symbol


def rank_all_venues(progress=None, enable_perps: bool | None = None) -> list[tuple[str, float]]:
    """Merged ranking across enabled venues, deduped by underlying asset.

    Where a coin trades on both venues the PERP wins. That is not a preference:
    round-trip fees are 0.07% of notional on Phemex against 1.00% on Coinbase
    spot, and at a 0.1% stop the same 3.00-gross trade nets -7.00R on spot and
    +2.30R on the perp. Routing an overlapping asset to spot would knowingly
    pick the version that loses money. Perps also short, which spot cannot.

    Spot-only assets are kept — they are still the only venue for those coins.
    """
    merged: dict[str, tuple[str, float]] = {}
    for pid, vol in rank_by_volume(progress):          # coinbase spot
        merged[_base_asset(pid)] = (pid, vol)
    if ENABLE_PERPS if enable_perps is None else enable_perps:
        try:
            for pid, vol in phemex.rank_by_volume():
                base = _base_asset(pid)
                # perp replaces spot for the same underlying; keeps its own
                # (deeper or shallower) volume figure for the liquidity gate
                merged[base] = (pid, vol)
        except Exception as exc:
            from .runlog import get_logger
            get_logger().warning(
                f"perp ranking unavailable, spot-only this refresh: {exc}")
    out = sorted(merged.values(), key=lambda r: -r[1])
    return out


def current_symbols(con) -> list[str]:
    """Admitted + warm symbols from the latest universe fact. Falls back to
    whatever has candles in the store, then to SEED — never empty, never network."""
    row = con.execute(
        "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
        "ORDER BY id DESC LIMIT 1", (UNIVERSE_VERSION,)).fetchone()
    if row:
        p = json.loads(row[0])
        syms = [s["symbol"] for s in p["members"] if s["state"] == "ADMITTED"]
        if syms:
            return syms
    have = [r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM candles WHERE tf='1D'").fetchall()]
    return have or list(SEED)


def all_tracked_symbols(con) -> list[str]:
    """Every symbol with stored candles — the deterministic reprocessing set."""
    have = [r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM candles WHERE tf='1D'").fetchall()]
    return sorted(set(have) | set(SEED))


def admitted_at(con, symbol: str, as_of: int) -> bool:
    """Point-in-time eligibility used to prevent present-universe backtests."""
    row = con.execute(
        "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
        "AND confirmed_at<=? ORDER BY confirmed_at DESC, id DESC LIMIT 1",
        (UNIVERSE_VERSION, as_of)).fetchone()
    if row is None:
        # BTC/ETH are the declared, golden-calibrated seed universe. Other
        # assets have no defensible eligibility before the first snapshot.
        return symbol in SEED
    members = json.loads(row[0])["members"]
    return any(m["symbol"] == symbol and m["state"] == "ADMITTED" for m in members)


def refresh(con, ranked: list[tuple[str, float]] | None = None,
            progress=None) -> dict:
    """Rank live, classify each candidate, record one universe fact. Returns
    the classification incl. which symbols need backfill (WARMING)."""
    with RunRecorder(con, "universe", UNIVERSE_VERSION, "PORTFOLIO", "ALL") as rec:
        # Operator settings override the module defaults. Read ONCE per refresh
        # so a mid-refresh edit cannot classify half the universe under one
        # config and half under another.
        from . import settings as _settings
        cfg = _settings.all_settings(con)
        injected = ranked is not None
        ranked = ranked if ranked is not None else rank_all_venues(
            progress, enable_perps=cfg["enable_perps"])
        rank_health = ({"attempted": len(ranked), "succeeded": len(ranked), "failed": 0,
                        "source": "injected"} if injected else LAST_RANK_HEALTH)
        if not ranked:
            rec.notes = "rank source unavailable — universe unchanged"
            return {"members": [], "warming": [], "source": "unavailable"}

        # Fail closed on partial coverage. A ranking built from a fraction of
        # the market does two bad things at once: it can drop a genuine top-20
        # pair, and it can PROMOTE a pair into the top 20 only because bigger
        # rivals failed to load. Both silently rewrite who is tradeable. Keeping
        # the last good universe is strictly safer than recording a plausible
        # wrong one — and the previous fact stays authoritative for admitted_at.
        attempted = rank_health.get("attempted") or 0
        coverage = (rank_health.get("succeeded", 0) / attempted) if attempted else 0.0
        if not injected and coverage < MIN_RANK_COVERAGE:
            from .runlog import get_logger
            get_logger().warning(
                f"UNIVERSE UNCHANGED: rank coverage {coverage:.1%} < "
                f"{MIN_RANK_COVERAGE:.0%} ({rank_health.get('failed')} of "
                f"{attempted} failed) — refusing to overwrite the universe")
            rec.notes = f"coverage {coverage:.1%} below floor — universe unchanged"
            return {"members": [], "warming": [], "source": "low_coverage",
                    "coverage": coverage}

        top_n = cfg["top_n"]
        min_volume = cfg["min_volume_usd"]

        candle_counts = dict(con.execute(
            "SELECT symbol, COUNT(*) FROM candles WHERE tf='1D' GROUP BY symbol").fetchall())
        members, warming = [], []
        for rank, (pid, vol) in enumerate(ranked, 1):
            if rank > top_n and pid not in SEED:
                break
            n_daily = candle_counts.get(pid, 0)
            if vol < min_volume and pid not in SEED:
                state, reason = "REJECTED", "below_liquidity_floor"
            elif n_daily < MIN_DAILY_CANDLES:
                state, reason = "WARMING", "insufficient_history"
                warming.append(pid)
            else:
                state, reason = "ADMITTED", "liquid_and_warm"
            members.append({"symbol": pid, "rank": rank, "vol_usd": round(vol),
                            "n_daily": n_daily, "state": state, "reason": reason})
        # SEED anchors always present even if outside the volume sweep — but
        # NEVER as a duplicate underlying. With perps preferred, BTCUSDT already
        # represents BTC; re-adding BTC-USD would let the same coin hold two
        # positions at once, each counted separately against MAX_CONCURRENT,
        # which is double exposure the risk envelope never agreed to.
        seen = {m["symbol"] for m in members}
        seen_bases = {_base_asset(m["symbol"]) for m in members}
        for pid in SEED:
            if _base_asset(pid) in seen_bases:
                continue
            if pid not in seen:
                n = candle_counts.get(pid, 0)
                members.append({"symbol": pid, "rank": None, "vol_usd": None,
                                "n_daily": n,
                                "state": "ADMITTED" if n >= MIN_DAILY_CANDLES else "WARMING",
                                "reason": "seed_anchor"})
                if n < MIN_DAILY_CANDLES:
                    warming.append(pid)

        store.insert_fact(con, symbol="PORTFOLIO", tf="ALL", kind="universe",
                          market_time=int(time.time()), confirmed_at=int(time.time()),
                          algo_version=UNIVERSE_VERSION,
                          payload={"members": members, "top_n": top_n,
                                   "min_volume_usd": min_volume,
                                   "min_daily_candles": MIN_DAILY_CANDLES,
                                   "rank_health": rank_health})
        con.commit()
        rec.n_new_facts = 1
        n_adm = sum(1 for m in members if m["state"] == "ADMITTED")
        rec.notes = f"admitted={n_adm} warming={len(warming)}"
        return {"members": members, "warming": warming, "source": "coinbase"}
