"""What funding ACTUALLY cost, against the constant the simulator charges.
READ-ONLY: this module writes no facts and mutates nothing (§1).

## Why this exists

`execsim` charges funding as `FUNDING_RATE_PER_SETTLEMENT` — one modelled
constant, 0.0001 — multiplied by the number of settlements a position was held
across, and subtracts it as a cost every time. Its own header calls the rate
"a conservative round number, not a measurement", and `edgestats` calls the
whole term "an assumption wearing a measurement's clothes". Both were right to
flag it and neither could do better, because the reason is recorded too: the
store holds no historical funding series, and `phemex.funding_rate()` fetches
only the CURRENT rate, which cannot price a trade that closed last week.

Both venues publish the history. Measured 2026-08-06 against what the simulator
charges, on 2,000 hourly Kraken settlements and 100 8-hourly Phemex ones:

    PF_XBTUSD   real 0.0166%/day   charged 0.2400%/day    14.5x
    PF_ETHUSD   real 0.0237%/day   charged 0.2400%/day    10.1x
    PF_SOLUSD   real 0.0407%/day   charged 0.2400%/day     5.9x
    BTCUSDT     real 0.0153%/day   charged 0.0300%/day     2.0x
    ETHUSDT     real 0.0088%/day   charged 0.0300%/day     3.4x
    SOLUSDT     real 0.0144%/day   charged 0.0300%/day     2.1x

The error is worst on Kraken, which is where funding matters most: 24
settlements a day against Phemex's 3, and 58.9% of modelled cost on that half
of the book.

## The second error, which is not a magnitude

REAL FUNDING HAS A SIGN. When the rate is negative the short side is PAID to
hold. On PF_SOLUSD that was 53% of settlements — more than half. `execsim`
subtracts funding as a cost in both directions, so on those settlements it is
not merely too large, it is pointed the wrong way.

## What this module does NOT do

It does not re-price the graded record. Nothing here writes a fact, bumps a
version, or re-simulates anything: this reports what the recorded book WOULD
have cost on real funding so the size of the correction is known before anyone
decides to make it. Charging trades from a real series is an execution-version
change and cascades through risk, scale and cooldown — that is a separate,
deliberate act, and it should be taken with this number already in hand.

The arithmetic below therefore mirrors `execsim.settle` exactly and differs in
ONE variable, the rate: same notional basis (entry price), same settlement
count from the same `venues` schedule, same conversion to R. Anything else
would measure two changes at once.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

from . import edgestats, venues
from .execsim import EXEC_VERSION, FUNDING_RATE_PER_SETTLEMENT

FUNDING_VERSION = "funding-v0.1-draft"

_KRAKEN = "https://futures.kraken.com/derivatives/api/v4/historicalfundingrates"
_PHEMEX = "https://api.phemex.com/api-data/public/data/funding-rate-history"
_UA = {"User-Agent": "snipersight-research"}
_TIMEOUT = 30


def _now() -> int:
    """Wall clock, in one place so a test can pin it."""
    return int(time.time())


def _get(url: str) -> dict:
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=_UA), timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode())


def kraken_history(symbol: str) -> list[tuple[int, Decimal]]:
    """(settlement unix seconds, rate) hourly, oldest first.

    `relativeFundingRate` is the rate; `fundingRate` on the same row is an
    absolute quote-currency figure and is NOT what a percentage cost is
    computed from. Taking the wrong one is a 5-order-of-magnitude error that
    looks plausible in a table, so it is named here rather than left to a
    future reader's guess.
    """
    d = _get(f"{_KRAKEN}?symbol={symbol}")
    out = []
    for row in d.get("rates") or []:
        rate = row.get("relativeFundingRate")
        if rate is None:
            continue
        ts = int(datetime.fromisoformat(
            row["timestamp"].replace("Z", "+00:00")).timestamp())
        out.append((ts, Decimal(str(rate))))
    return sorted(out)


#: Phemex returns at most 100 settlements per call whatever `limit` asks for —
#: 500 and 1000 both come back with 100. It DOES honour `start`/`end`, so the
#: history is reachable by walking the window backwards. One page is ~33 days.
_PHEMEX_PAGE = 100
#: A stop, not a budget. Without it a symbol whose feed returns a short page
#: forever would page until the request timed out; 40 pages is ~3.6 years,
#: comfortably past the oldest fact in the store.
_PHEMEX_MAX_PAGES = 40


def phemex_history(symbol: str, since_ts: int | None = None) -> list[tuple[int, Decimal]]:
    """(settlement unix seconds, rate) 8-hourly, oldest first.

    Keyed on the INDEX symbol `.{SYMBOL}FR8H`, not the trading symbol. Querying
    `BTCUSDT` directly returns `{"rows": []}` — a success with no data, which
    reads exactly like "this market has no funding" and is the trap this
    docstring exists to disarm.

    Paged backwards to `since_ts`, because one call reaches 33 days and the
    recorded book reaches years. Unpaged, 242 of 587 trades could not be priced
    at all and every one of them was an OLD trade — which would have quietly
    made this a report about the last month wearing the label of a report about
    the book.
    """
    # ANCHOR ON `end` ALONE, and walk it backwards.
    #
    # Sending `start` as well looks like the obvious way to ask for a range
    # and is the thing that broke it: given a wide window the feed answers
    # with the rows at the START of it, so page one came back full of year-old
    # settlements, `oldest <= since_ts` was already true, the loop stopped, and
    # the series held nothing recent. Coverage went DOWN when the paging was
    # added — 345 priced trades to 269 — which is how it was caught. `end`
    # alone returns the 100 settlements before that moment, which is what
    # walking backwards actually needs.
    out: dict = {}
    end_ms = int(_now() * 1000)
    for _ in range(_PHEMEX_MAX_PAGES):
        url = f"{_PHEMEX}?symbol=.{symbol}FR8H&limit={_PHEMEX_PAGE}&end={end_ms}"
        rows = (_get(url).get("data") or {}).get("rows") or []
        fresh = {int(r["fundingTime"]) // 1000: Decimal(str(r["fundingRate"]))
                 for r in rows if r.get("fundingRate") is not None}
        new = {k: v for k, v in fresh.items() if k not in out}
        if not new:
            break                       # the feed has nothing older to give
        out.update(new)
        oldest = min(new)
        if since_ts and oldest <= since_ts:
            break
        end_ms = oldest * 1000          # step the window back one page
    return sorted(out.items())


def history(symbol: str, since_ts: int | None = None) -> list[tuple[int, Decimal]]:
    """Real settlements for one symbol, or [] where the venue charges none.

    Spot pays no funding, and `venues` already knows that as
    `funding_settlements_per_day == 0` — asked here rather than re-decided, so
    a venue whose schedule changes changes in one place (§6).
    """
    v = venues.venue_for(symbol)
    if not v.funding_settlements_per_day:
        return []
    if v.key.startswith("kraken"):
        return kraken_history(symbol)
    if v.key.startswith("phemex"):
        return phemex_history(symbol, since_ts)
    raise ValueError(f"no funding source wired for venue {v.key!r} ({symbol})")


def charge(series: list[tuple[int, Decimal]], direction: str,
           start_ts: int, holding_hours: Decimal,
           entry: Decimal) -> dict:
    """What this hold really paid — signed, in price units on entry notional.

    SIGN IS THE POINT. A LONG pays the rate; a SHORT pays its negative, which
    means a short RECEIVES funding whenever the rate is positive. `execsim`
    subtracts the modelled figure in both directions, and on a book where half
    the settlements are negative that is not a magnitude error.

    `covered` is false when the fetched series does not span the whole hold.
    A hold priced from a partial window would report a cost that is too small
    for the honest reason that we could not see all of it, which is precisely
    the flattering-by-omission this project refuses (§4) — the caller must be
    able to drop the trade rather than average it in.
    """
    end_ts = start_ts + int(holding_hours * 3600)
    inside = [(ts, r) for ts, r in series if start_ts <= ts < end_ts]
    long = str(direction).upper() == "LONG"
    signed = sum((r if long else -r) for _, r in inside) or Decimal(0)
    covered = bool(series) and series[0][0] <= start_ts and series[-1][0] >= end_ts
    return {
        "settlements": len(inside),
        "rate_sum": signed,
        "price_units": signed * entry,
        "covered": covered,
    }


def report(con, *, algo_version: str | None = None,
           symbol: str | None = None) -> dict:
    """Re-price the recorded book on real funding. Writes nothing.

    The R denominator, the version-correct fee/funding split and the trade set
    all come from `edgestats.load_trades` rather than a second reading of the
    store — one authority for every number this shares with the edge report
    (§6), so the two can be compared line for line.
    """
    algo_version = algo_version or EXEC_VERSION
    trades, counts, warnings = edgestats.load_trades(
        con, algo_version=algo_version, symbol=symbol)

    # fill_ts and holding_hours are not on the load_trades dict; they are read
    # back by fact id rather than by re-running the query, so the two views
    # cannot drift apart on which trades they mean.
    ids = {t["id"] for t in trades}
    held: dict = {}
    for fid, raw in con.execute(
            "SELECT id, payload FROM facts WHERE kind='exec' AND algo_version=?",
            (algo_version,)):
        if fid in ids:
            p = json.loads(raw)
            held[fid] = (p.get("fill_ts"), p.get("holding_hours"))

    # How far back each symbol's feed has to reach: its OLDEST trade, less a
    # day's grace so the window brackets the fill rather than starting on it.
    # Computed up front because the fetch is paged — asking per trade would
    # page the same history once per trade.
    earliest: dict = {}
    for t in trades:
        ft = held.get(t["id"], (None, None))[0]
        if ft is None:
            continue
        prev = earliest.get(t["symbol"])
        ft = int(ft) - 24 * 3600
        earliest[t["symbol"]] = ft if prev is None else min(prev, ft)

    series_cache: dict = {}
    rows, skipped = [], []
    for t in trades:
        sym = t["symbol"]
        if sym not in series_cache:
            try:
                series_cache[sym] = history(sym, earliest.get(sym))
            except Exception as exc:                      # noqa: BLE001
                series_cache[sym] = None
                warnings.append(
                    f"{sym}: funding history unavailable ({type(exc).__name__}) — "
                    f"its trades are EXCLUDED from this comparison, not priced at zero")
        series = series_cache[sym]
        fill_ts, hours = held.get(t["id"], (None, None))
        if series is None or fill_ts is None or hours is None:
            skipped.append({"id": t["id"], "symbol": sym,
                            "why": "no series" if series is None else "no fill time"})
            continue
        if not series and not venues.venue_for(sym).funding_settlements_per_day:
            # Spot: charged nothing, really pays nothing. A true zero, and it
            # belongs in the comparison rather than in the skipped pile.
            real = {"settlements": 0, "rate_sum": Decimal(0),
                    "price_units": Decimal(0), "covered": True}
        else:
            real = charge(series, t["direction"], int(fill_ts),
                          Decimal(str(hours)), t["entry"])
        if not real["covered"]:
            skipped.append({"id": t["id"], "symbol": sym,
                            "why": "the published history does not span this hold"})
            continue
        real_r = float(real["price_units"] / t["risk"])
        rows.append({
            "id": t["id"], "symbol": sym, "tf": t["tf"],
            "direction": t["direction"], "venue": t["venue"],
            "charged_funding_r": t["funding_r"],
            "real_funding_r": real_r,
            "delta_r": t["funding_r"] - real_r,       # positive = overcharged
            "settlements": real["settlements"],
            "r_net_as_recorded": t["r_net"],
            "r_net_on_real_funding": t["r_net"] + (t["funding_r"] - real_r),
        })

    n = len(rows)
    tot_charged = sum(r["charged_funding_r"] for r in rows)
    tot_real = sum(r["real_funding_r"] for r in rows)
    return {
        "funding_version": FUNDING_VERSION,
        "algo_version": algo_version,
        "modelled_rate_per_settlement": str(FUNDING_RATE_PER_SETTLEMENT),
        "counts": {**counts, "priced": n, "skipped": len(skipped)},
        "skipped": skipped[:20],
        "warnings": warnings,
        "totals": None if not n else {
            "trades": n,
            "charged_funding_r_total": tot_charged,
            "real_funding_r_total": tot_real,
            "overcharge_r_total": tot_charged - tot_real,
            "overcharge_r_per_trade": (tot_charged - tot_real) / n,
            "mean_r_as_recorded": sum(r["r_net_as_recorded"] for r in rows) / n,
            "mean_r_on_real_funding": sum(r["r_net_on_real_funding"] for r in rows) / n,
        },
        "rows": rows,
    }


if __name__ == "__main__":                                # pragma: no cover
    from . import store
    con = store.connect()
    try:
        rep = report(con)
    finally:
        con.close()
    t = rep["totals"]
    print(f"funding {rep['funding_version']} · {rep['algo_version']}")
    print(f"modelled rate/settlement: {rep['modelled_rate_per_settlement']}")
    print(f"priced {rep['counts']['priced']} trades, skipped {rep['counts']['skipped']}")
    for w in rep["warnings"]:
        print(f"  ! {w}")
    if not t:
        print("no trades priced")
    else:
        print(f"  charged funding   {t['charged_funding_r_total']:+.4f} R total")
        print(f"  real funding      {t['real_funding_r_total']:+.4f} R total")
        print(f"  OVERCHARGED       {t['overcharge_r_total']:+.4f} R "
              f"({t['overcharge_r_per_trade']:+.4f} R/trade)")
        print(f"  mean R as recorded      {t['mean_r_as_recorded']:+.4f}")
        print(f"  mean R on real funding  {t['mean_r_on_real_funding']:+.4f}")
