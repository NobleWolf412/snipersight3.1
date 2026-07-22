"""Display-only live market-data helpers; never consumed by fact engines."""
import json
import urllib.request


def fetch_tickers(symbols, opener=urllib.request.urlopen) -> dict:
    out = {}
    for sym in symbols:
        try:
            req = urllib.request.Request(
                f"https://api.exchange.coinbase.com/products/{sym}/ticker",
                headers={"User-Agent": "snipersight/0.1"})
            with opener(req, timeout=5) as response:
                data = json.loads(response.read().decode())
            out[sym] = {"price": float(data["price"]), "time": data["time"],
                        "status": "OK"}
        except Exception as exc:
            out[sym] = {"price": None, "time": None, "status": "DEGRADED",
                        "error": type(exc).__name__}
    return out
