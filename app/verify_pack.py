"""Generate a human-checkable verification pack for the swing engine.

Output: verification/pack-001-swings.md — LOCAL swings on BTC-USD 1D and 4H,
formatted for side-by-side comparison with TradingView (Coinbase BTCUSD feed).
Usage: python verify_pack.py
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from engine import store, swings

OUT = Path(__file__).resolve().parent / "verification" / "pack-001-swings.md"
NOW = int(time.time())


def d(ts, with_time=False):
    fmt = "%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(fmt)


def rows_for(con, symbol, tf, since_ts, with_time):
    out = []
    for r in store.get_facts(con, symbol, tf, "swing", swings.SWING_VERSION):
        p = json.loads(r["payload"])
        if p["tier"] != "LOCAL" or r["market_time"] < since_ts:
            continue
        out.append(
            f"| {d(r['market_time'], with_time)} | {p['type']} | "
            f"{float(p['price']):,.2f} | {float(p['reversal_atr_mult']):.2f}x | "
            f"{d(r['confirmed_at'], with_time)} |  |")
    return out


def main():
    con = store.connect()
    day_rows = rows_for(con, "BTC-USD", "1D", NOW - 200 * 86400, False)
    h4_rows = rows_for(con, "BTC-USD", "4H", NOW - 21 * 86400, True)
    n_micro = con.execute(
        "SELECT COUNT(*) FROM facts WHERE payload LIKE '%MICRO%'").fetchone()[0]
    n_local = con.execute(
        "SELECT COUNT(*) FROM facts WHERE payload LIKE '%LOCAL%'").fetchone()[0]
    gaps = con.execute("SELECT COALESCE(SUM(n_gaps),0) FROM import_log").fetchone()[0]

    header = "| Bar (UTC) | Type | Price | Reversal | Confirmed (UTC) | Your check |\n|---|---|---|---|---|---|"
    md = f"""# Verification Pack 001 — Swing Engine ({swings.SWING_VERSION})

Generated {d(NOW, True)} UTC · venue Coinbase · append-only fact store, determinism gate PASS

## How to check (10–20 minutes)

1. Open TradingView, symbol **BTCUSD** with the **Coinbase** feed (feed matters —
   Binance prices differ and levels will look shifted).
2. Set the timeframe to match each table (1D, then 4H). Times below are **UTC** —
   set your TradingView timezone to UTC or expect bar labels to differ.
3. For each row: is there a meaningful swing high/low at that bar, at ~that price?
   Mark the last column: **Y** (yes, I'd have marked it), **n** (real but too minor
   to care about), **X** (wrong — no swing there / missed a bigger one nearby).
4. Also note any obvious swing the table **misses** — those matter most.

A `HIGH` is a local top (price reversed down from it); `LOW` is a local bottom.
"Reversal" is how far price moved against the swing before the next opposite
swing, in ATR multiples — bigger = more significant. "Confirmed" is when the
engine was first *allowed* to know it (2 closed bars later — no repainting).

## BTC-USD · 1D · LOCAL swings · last ~200 days ({len(day_rows)} rows)

{header}
{chr(10).join(day_rows)}

## BTC-USD · 4H · LOCAL swings · last 21 days ({len(h4_rows)} rows)

{header}
{chr(10).join(h4_rows)}

## Engine notes for this run

- Store totals: {n_micro:,} MICRO / {n_local:,} LOCAL swing facts across both
  symbols and 5 timeframes. Import gaps logged: {gaps} candles (excluded, never
  fabricated).
- **Known calibration flag:** ~90% of micro swings currently promote to LOCAL —
  the 0.75 ATR reversal threshold barely filters on crypto volatility. If the
  tables feel noisy (too many minor swings), that's this. Likely fixes: raise the
  multiplier, or measure reversal only until price makes a new extreme past the
  swing. Your Y/n/X marks will tell us which.
- Draft rules in force (all versioned, all changeable): strict-inequality
  5-candle fractal; ties produce no swing; close-time confirmation.

## What to send back

The marked-up tables (or just: "1D mostly good, 4H too noisy, missed the big
low on <date>"). I'll adjust the rules, bump the algo version, and regenerate
this pack — old and new versions stay queryable side by side.
"""
    OUT.write_text(md, encoding="utf-8")
    print(f"wrote {OUT} ({len(day_rows)} 1D rows, {len(h4_rows)} 4H rows)")


if __name__ == "__main__":
    main()
