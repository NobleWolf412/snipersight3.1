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
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import store
from .runlog import RunRecorder

UNIVERSE_VERSION = "universe-v0.1-draft"
API = "https://api.exchange.coinbase.com"
TOP_N = 20
MIN_VOLUME_USD = 3_000_000        # daily-volume floor (structural stops must fill)
MIN_DAILY_CANDLES = 200           # ~structure-map warmup before a symbol is tradeable
REFRESH_SECONDS = 3600            # volume ranking barely moves intraday
SEED = ("BTC-USD", "ETH-USD")     # always-present anchors (golden-calibrated)
REQUEST_PAUSE = 0.15
RANK_WORKERS = 6
LAST_RANK_HEALTH = {"attempted": 0, "succeeded": 0, "failed": 0}
_UA = {"User-Agent": "snipersight/0.1"}
# stablecoin bases have no tradeable structure (ported from prior project's
# _is_stable_base) — a ~$1 pegged asset must never enter the universe.
STABLE_BASES = {"USDT", "USDC", "DAI", "USDS", "PYUSD", "USDD", "TUSD",
                "FDUSD", "GUSD", "USDP", "EUROC", "EURC", "PAX", "BUSD"}


def _is_stable(pid: str) -> bool:
    return pid.split("-")[0].upper() in STABLE_BASES


def _get(path: str):
    req = urllib.request.Request(API + path, headers=_UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def rank_by_volume() -> list[tuple[str, float]]:
    """Live: all online USD spot pairs, ranked by 24h USD volume. Fail-soft."""
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
        for future in as_completed(futures):
            pid = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                failed.append({"symbol": pid, "error": type(exc).__name__})
    LAST_RANK_HEALTH = {"attempted": len(usd), "succeeded": len(rows),
                        "failed": len(failed), "sample_failures": failed[:10]}
    if failed:
        from .runlog import get_logger
        get_logger().warning(
            f"universe rank coverage {len(rows)}/{len(usd)}; "
            f"{len(failed)} product stats failed")
    rows.sort(key=lambda r: -r[1])
    return rows


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


def refresh(con, ranked: list[tuple[str, float]] | None = None) -> dict:
    """Rank live, classify each candidate, record one universe fact. Returns
    the classification incl. which symbols need backfill (WARMING)."""
    with RunRecorder(con, "universe", UNIVERSE_VERSION, "PORTFOLIO", "ALL") as rec:
        injected = ranked is not None
        ranked = ranked if ranked is not None else rank_by_volume()
        rank_health = ({"attempted": len(ranked), "succeeded": len(ranked), "failed": 0,
                        "source": "injected"} if injected else LAST_RANK_HEALTH)
        if not ranked:
            rec.notes = "rank source unavailable — universe unchanged"
            return {"members": [], "warming": [], "source": "unavailable"}

        candle_counts = dict(con.execute(
            "SELECT symbol, COUNT(*) FROM candles WHERE tf='1D' GROUP BY symbol").fetchall())
        members, warming = [], []
        for rank, (pid, vol) in enumerate(ranked, 1):
            if rank > TOP_N and pid not in SEED:
                break
            n_daily = candle_counts.get(pid, 0)
            if vol < MIN_VOLUME_USD and pid not in SEED:
                state, reason = "REJECTED", "below_liquidity_floor"
            elif n_daily < MIN_DAILY_CANDLES:
                state, reason = "WARMING", "insufficient_history"
                warming.append(pid)
            else:
                state, reason = "ADMITTED", "liquid_and_warm"
            members.append({"symbol": pid, "rank": rank, "vol_usd": round(vol),
                            "n_daily": n_daily, "state": state, "reason": reason})
        # SEED anchors always present even if outside the volume sweep
        seen = {m["symbol"] for m in members}
        for pid in SEED:
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
                          payload={"members": members, "top_n": TOP_N,
                                   "min_volume_usd": MIN_VOLUME_USD,
                                   "min_daily_candles": MIN_DAILY_CANDLES,
                                   "rank_health": rank_health})
        con.commit()
        rec.n_new_facts = 1
        n_adm = sum(1 for m in members if m["state"] == "ADMITTED")
        rec.notes = f"admitted={n_adm} warming={len(warming)}"
        return {"members": members, "warming": warming, "source": "coinbase"}
