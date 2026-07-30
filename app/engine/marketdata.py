"""Display-only live market-data helpers; never consumed by fact engines.

Venue-routed since v0.2. Every call here used to go to Coinbase unconditionally,
which was correct while the universe was spot. It stopped being correct the
moment the traded set became Phemex perps: `BTCUSDT` is not a Coinbase product,
so every request 404'd. The visible symptom was `/api/ticker` reporting DEGRADED
for the entire universe and the drift monitor logging twenty 404s a minute
forever — a monitor that cannot see any price is not a quiet monitor, it is a
broken one.
"""
import json
import urllib.request

from . import phemex, venues


def _coinbase_ticker(sym: str, opener) -> float:
    req = urllib.request.Request(
        f"https://api.exchange.coinbase.com/products/{sym}/ticker",
        headers={"User-Agent": "snipersight/0.1"})
    with opener(req, timeout=5) as response:
        return json.loads(response.read().decode())


def last_prices(symbols, opener=urllib.request.urlopen) -> dict:
    """symbol -> last traded price. Missing symbols are absent, never zero.

    Perps are fetched in ONE batched call; spot is per-symbol because Coinbase
    has no equivalent all-tickers endpoint. A symbol the venue could not price
    is left out of the mapping rather than defaulted — a caller comparing
    against a fabricated price would compute drift against a number that never
    traded.
    """
    out: dict = {}
    perps = [s for s in symbols if _is_perp(s)]
    spot = [s for s in symbols if not _is_perp(s)]
    if perps:
        try:
            out.update(phemex.last_prices(perps))
        except Exception:
            pass                       # caller reports the gap; see docstring
    for sym in spot:
        try:
            out[sym] = float(_coinbase_ticker(sym, opener)["price"])
        except Exception:
            continue
    return out


def _is_perp(symbol: str) -> bool:
    try:
        return venues.venue_for(symbol).is_perp
    except ValueError:
        return False                   # unknown -> treat as spot, the old path


def fetch_tickers(symbols, opener=urllib.request.urlopen) -> dict:
    """Per-symbol status map for the UI. DEGRADED is reported, never hidden."""
    out = {}
    perps = [s for s in symbols if _is_perp(s)]
    priced: dict = {}
    if perps:
        try:
            priced = phemex.last_prices(perps)
        except Exception as exc:
            for sym in perps:
                out[sym] = {"price": None, "time": None, "status": "DEGRADED",
                            "error": type(exc).__name__}
    for sym in perps:
        if sym in out:
            continue
        if sym in priced:
            out[sym] = {"price": priced[sym], "time": None, "status": "OK"}
        else:
            out[sym] = {"price": None, "time": None, "status": "DEGRADED",
                        "error": "NotListed"}
    for sym in symbols:
        if sym in out:
            continue
        try:
            data = _coinbase_ticker(sym, opener)
            out[sym] = {"price": float(data["price"]), "time": data["time"],
                        "status": "OK"}
        except Exception as exc:
            out[sym] = {"price": None, "time": None, "status": "DEGRADED",
                        "error": type(exc).__name__}
    return out
