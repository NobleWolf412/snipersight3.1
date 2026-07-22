# Verification Pack 001 — Swing Engine (swing-v0.1-draft)

Generated 2026-07-21 03:11 UTC · venue Coinbase · append-only fact store, determinism gate PASS

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

## BTC-USD · 1D · LOCAL swings · last ~200 days (57 rows)

| Bar (UTC) | Type | Price | Reversal | Confirmed (UTC) | Your check |
|---|---|---|---|---|---|
| 2026-01-05 | HIGH | 94,825.27 | 2.22x | 2026-01-11 |  |
| 2026-01-08 | LOW | 89,200.00 | 3.37x | 2026-01-17 |  |
| 2026-01-12 | LOW | 90,003.46 | 3.40x | 2026-01-17 |  |
| 2026-01-14 | HIGH | 97,963.62 | 4.13x | 2026-01-24 |  |
| 2026-01-21 | LOW | 87,156.00 | 1.56x | 2026-01-26 |  |
| 2026-01-23 | HIGH | 91,147.01 | 2.04x | 2026-01-28 |  |
| 2026-01-25 | LOW | 86,000.13 | 1.82x | 2026-01-31 |  |
| 2026-01-28 | HIGH | 90,476.81 | 12.76x | 2026-02-09 |  |
| 2026-02-06 | LOW | 60,001.00 | 2.61x | 2026-02-11 |  |
| 2026-02-08 | HIGH | 72,232.17 | 1.57x | 2026-02-15 |  |
| 2026-02-12 | LOW | 65,065.47 | 1.39x | 2026-02-18 |  |
| 2026-02-15 | HIGH | 70,941.65 | 1.36x | 2026-02-22 |  |
| 2026-02-19 | LOW | 65,604.63 | 0.87x | 2026-02-24 |  |
| 2026-02-21 | HIGH | 68,683.27 | 1.89x | 2026-02-27 |  |
| 2026-02-24 | LOW | 62,534.61 | 2.41x | 2026-02-28 |  |
| 2026-02-25 | HIGH | 70,020.00 | 2.11x | 2026-03-03 |  |
| 2026-02-28 | LOW | 63,019.60 | 3.30x | 2026-03-07 |  |
| 2026-03-04 | HIGH | 74,100.00 | 2.31x | 2026-03-11 |  |
| 2026-03-08 | LOW | 65,618.51 | 1.81x | 2026-03-13 |  |
| 2026-03-10 | HIGH | 71,800.00 | 1.30x | 2026-03-25 |  |
| 2026-03-13 | HIGH | 73,968.00 | 2.04x | 2026-03-25 |  |
| 2026-03-17 | HIGH | 76,022.60 | 2.90x | 2026-03-25 |  |
| 2026-03-22 | LOW | 67,332.05 | 1.62x | 2026-03-28 |  |
| 2026-03-25 | HIGH | 72,030.29 | 2.46x | 2026-04-01 |  |
| 2026-03-29 | LOW | 64,938.66 | 1.55x | 2026-04-04 |  |
| 2026-04-01 | HIGH | 69,285.99 | 1.34x | 2026-04-05 |  |
| 2026-04-02 | LOW | 65,696.96 | 3.85x | 2026-04-17 |  |
| 2026-04-12 | LOW | 70,512.70 | 2.27x | 2026-04-17 |  |
| 2026-04-14 | HIGH | 76,127.18 | 1.09x | 2026-04-19 |  |
| 2026-04-16 | LOW | 73,298.01 | 2.02x | 2026-04-20 |  |
| 2026-04-17 | HIGH | 78,390.00 | 1.78x | 2026-04-23 |  |
| 2026-04-20 | LOW | 73,741.53 | 2.24x | 2026-04-25 |  |
| 2026-04-22 | HIGH | 79,523.00 | 1.77x | 2026-05-02 |  |
| 2026-04-27 | HIGH | 79,496.00 | 1.96x | 2026-05-02 |  |
| 2026-04-29 | LOW | 74,914.00 | 3.36x | 2026-05-09 |  |
| 2026-05-06 | HIGH | 82,814.23 | 1.55x | 2026-05-10 |  |
| 2026-05-07 | LOW | 79,456.00 | 1.37x | 2026-05-13 |  |
| 2026-05-10 | HIGH | 82,450.00 | 3.19x | 2026-05-21 |  |
| 2026-05-14 | HIGH | 82,066.22 | 2.84x | 2026-05-21 |  |
| 2026-05-18 | LOW | 75,992.00 | 1.01x | 2026-05-24 |  |
| 2026-05-21 | HIGH | 78,123.68 | 2.00x | 2026-05-26 |  |
| 2026-05-23 | LOW | 74,197.11 | 1.83x | 2026-05-29 |  |
| 2026-05-26 | HIGH | 78,015.46 | 2.82x | 2026-06-01 |  |
| 2026-05-29 | LOW | 72,364.13 | 4.09x | 2026-06-10 |  |
| 2026-06-05 | LOW | 59,073.01 | 2.04x | 2026-06-10 |  |
| 2026-06-07 | HIGH | 64,234.45 | 1.37x | 2026-06-13 |  |
| 2026-06-10 | LOW | 60,708.92 | 2.62x | 2026-06-18 |  |
| 2026-06-15 | HIGH | 67,264.00 | 2.21x | 2026-06-21 |  |
| 2026-06-18 | LOW | 62,159.76 | 1.47x | 2026-06-25 |  |
| 2026-06-22 | HIGH | 65,553.39 | 3.57x | 2026-06-28 |  |
| 2026-06-25 | LOW | 58,000.00 | 2.78x | 2026-07-09 |  |
| 2026-07-01 | LOW | 57,717.55 | 3.00x | 2026-07-09 |  |
| 2026-07-06 | HIGH | 64,658.85 | 1.51x | 2026-07-09 |  |
| 2026-07-06 | LOW | 61,250.00 | 1.52x | 2026-07-13 |  |
| 2026-07-10 | HIGH | 64,669.42 | 1.35x | 2026-07-16 |  |
| 2026-07-13 | LOW | 61,750.90 | 1.90x | 2026-07-18 |  |
| 2026-07-15 | HIGH | 65,559.50 | 1.55x | 2026-07-20 |  |

## BTC-USD · 4H · LOCAL swings · last 21 days (26 rows)

| Bar (UTC) | Type | Price | Reversal | Confirmed (UTC) | Your check |
|---|---|---|---|---|---|
| 2026-06-30 12:00 | LOW | 58,056.00 | 3.82x | 2026-07-02 08:00 |  |
| 2026-07-01 00:00 | LOW | 57,717.55 | 4.21x | 2026-07-02 08:00 |  |
| 2026-07-01 12:00 | LOW | 58,242.82 | 3.25x | 2026-07-02 08:00 |  |
| 2026-07-01 20:00 | HIGH | 61,287.33 | 1.86x | 2026-07-02 12:00 |  |
| 2026-07-02 00:00 | LOW | 59,520.02 | 2.65x | 2026-07-03 00:00 |  |
| 2026-07-04 16:00 | HIGH | 63,410.00 | 1.41x | 2026-07-05 20:00 |  |
| 2026-07-05 08:00 | LOW | 62,384.08 | 2.29x | 2026-07-06 08:00 |  |
| 2026-07-05 20:00 | HIGH | 63,940.79 | 3.92x | 2026-07-07 00:00 |  |
| 2026-07-06 12:00 | LOW | 61,250.00 | 4.27x | 2026-07-07 08:00 |  |
| 2026-07-06 20:00 | HIGH | 64,658.85 | 2.57x | 2026-07-08 00:00 |  |
| 2026-07-07 12:00 | LOW | 62,583.00 | 1.91x | 2026-07-08 04:00 |  |
| 2026-07-07 16:00 | HIGH | 64,199.93 | 3.24x | 2026-07-09 00:00 |  |
| 2026-07-08 12:00 | LOW | 61,453.09 | 2.04x | 2026-07-09 16:00 |  |
| 2026-07-10 12:00 | HIGH | 64,669.42 | 1.33x | 2026-07-11 08:00 |  |
| 2026-07-10 20:00 | LOW | 63,608.54 | 0.87x | 2026-07-11 12:00 |  |
| 2026-07-11 00:00 | HIGH | 64,270.80 | 0.93x | 2026-07-12 16:00 |  |
| 2026-07-11 12:00 | HIGH | 64,458.70 | 1.33x | 2026-07-12 16:00 |  |
| 2026-07-12 04:00 | LOW | 63,588.20 | 1.07x | 2026-07-13 00:00 |  |
| 2026-07-12 12:00 | HIGH | 64,250.56 | 4.29x | 2026-07-14 04:00 |  |
| 2026-07-13 00:00 | HIGH | 64,388.01 | 4.10x | 2026-07-14 04:00 |  |
| 2026-07-13 16:00 | LOW | 61,750.90 | 5.82x | 2026-07-16 00:00 |  |
| 2026-07-15 12:00 | HIGH | 65,559.50 | 4.43x | 2026-07-18 00:00 |  |
| 2026-07-17 12:00 | LOW | 62,452.52 | 2.63x | 2026-07-18 04:00 |  |
| 2026-07-19 00:00 | HIGH | 64,918.70 | 1.24x | 2026-07-20 00:00 |  |
| 2026-07-19 12:00 | LOW | 64,238.08 | 1.62x | 2026-07-20 12:00 |  |
| 2026-07-20 00:00 | HIGH | 65,050.87 | 2.62x | 2026-07-20 16:00 |  |

## Engine notes for this run

- Store totals: 5,699 MICRO / 5,420 LOCAL swing facts across both
  symbols and 5 timeframes. Import gaps logged: 10 candles (excluded, never
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
