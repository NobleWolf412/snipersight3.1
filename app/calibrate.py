"""Diff engine output against user golden data (verification/golden-btc-1d.json).

Scores MAJOR swings and structure breaks on BTC-USD 1D:
- MATCH: engine fact within tolerance_days and 10% price of a golden entry
- MISS:  golden entry with no matching engine fact (worst failure)
- EXTRA: engine MAJOR fact inside the window matching nothing (over-detection)
Usage: python calibrate.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from engine import store, swings, structure

GOLDEN = Path(__file__).resolve().parent / "verification" / "golden-btc-1d.json"
PRICE_TOL = 0.10


def ts(datestr):
    return int(datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def d(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")


def match(golden_list, engine_list, key_price, extra_filter=None):
    matches, misses = [], []
    used = set()
    for g in golden_list:
        g_ts, tol = ts(g["date"]), g["tolerance_days"] * 86400
        found = None
        for i, e in enumerate(engine_list):
            if i in used or (extra_filter and not extra_filter(g, e)):
                continue
            if abs(e["market_time"] - g_ts) <= tol and \
               abs(key_price(e) - g["price"]) / g["price"] <= PRICE_TOL:
                found = (i, e)
                break
        if found:
            used.add(found[0])
            matches.append((g, found[1]))
        else:
            misses.append(g)
    extras = [e for i, e in enumerate(engine_list) if i not in used]
    return matches, misses, extras


def main():
    golden = json.loads(GOLDEN.read_text())
    w0, w1 = ts(golden["window"][0]), ts(golden["window"][1]) + 86400
    con = store.connect()

    majors, breaks = [], []
    for r in store.get_facts(con, "BTC-USD", "1D", "swing", swings.SWING_VERSION):
        p = json.loads(r["payload"])
        if p["tier"] == "MAJOR" and w0 <= r["market_time"] < w1:
            majors.append({"market_time": r["market_time"], **p})
    for r in store.get_facts(con, "BTC-USD", "1D", "structure", structure.STRUCTURE_VERSION):
        p = json.loads(r["payload"])
        if p["event"] in ("BOS", "CHOCH") and w0 <= r["market_time"] < w1:
            breaks.append({"market_time": r["market_time"], **p})

    print(f"=== MAJOR swings: engine={len(majors)} golden={len(golden['swings'])} ===")
    m, mi, ex = match(golden["swings"], majors, lambda e: float(e["price"]),
                      lambda g, e: g["type"] == e["type"])
    for g, e in m:
        print(f"  MATCH {g['type']:4s} golden {g['date']} ~{g['price']:>9,.0f}"
              f"  <- engine {d(e['market_time'])} {float(e['price']):>10,.2f}")
    for g in mi:
        print(f"  MISS  {g['type']:4s} golden {g['date']} ~{g['price']:>9,.0f}  ({g['note']})")
    for e in ex:
        print(f"  EXTRA {e['type']:4s} engine {d(e['market_time'])} {float(e['price']):>10,.2f}")

    print(f"\n=== Structure breaks: engine={len(breaks)} golden={len(golden['breaks'])} ===")
    m, mi, ex = match(golden["breaks"], breaks, lambda e: float(e["level"]),
                      lambda g, e: g["event"] == e["event"] and g["direction"] == e["direction"])
    for g, e in m:
        print(f"  MATCH {g['event']:5s} {g['direction']:4s} golden {g['date']} ~{g['price']:>9,.0f}"
              f"  <- engine {d(e['market_time'])} level {float(e['level']):>10,.2f}")
    for g in mi:
        print(f"  MISS  {g['event']:5s} {g['direction']:4s} golden {g['date']} ~{g['price']:>9,.0f}  ({g['note']})")
    for e in ex:
        print(f"  EXTRA {e['event']:5s} {e['direction']:4s} engine {d(e['market_time'])}"
              f" level {float(e['level']):>10,.2f}")


if __name__ == "__main__":
    main()
