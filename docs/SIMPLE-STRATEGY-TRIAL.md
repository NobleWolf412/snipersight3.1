# Prospective simple-strategy comparison

Status: research-only implementation in `codex/complete-open-trading-work`.
The cohort starts on the first scanner pass after deployment; there is no
historical result or authority to route a new strategy.

## Locked question

**Primary:** Does a simple 4H close breakout of the preceding 20 complete
4H bars have a higher average net R than the existing 4H pullback/reversal
setups, over the same future 90-day calendar window? Trend pullback/reclaim is
an exploratory third arm and cannot supply a primary success claim.

The breakout's entry is the signal close; the stop is the signal low minus
0.20 ATR for a long (signal high plus 0.20 ATR for a short), the target is
2 initial price-risk units away, and its passive limit is 0.20 initial risk
units better than the signal close. All three arms independently use the
shared maker-then-market entry model: two full 4H candles to touch the passive
price and a following market cross if it did not. Shorts require venue
support. Existing strategy plans enter with their own recorded immutable
prices and expiry; the comparison does not retune them.

Each arm has an independent $10,000 simulated cash book, $100 planned price
risk per order, at most five active orders/positions and one per market. Fees,
slippage and funding use the same versioned `execsim` and cost profile.
Fills, bars, costs and outcomes are append-only facts in this study's own
SQLite tables. The scan's fixed closed-candle cutoff and actual observation
time are recorded separately. No setup confirmed before activation can be
placed; every entry begins at a future 4H boundary. Missing candles hold an
open result rather than fabricate a fill or exit.

The comparison is `UNKNOWN` until **both** primary arms have at least 30
closed trades from at least 8 distinct symbols. Then a deterministic
symbol-cluster bootstrap reports the difference in mean net R and a 95%
interval. An interval above zero is labelled only **Promising, still
unproven**. The Results card also reports counts, net dollars, return,
drawdown, and separate long/short outcomes. Unequal signal frequency and
cash-slot competition remain part of what these complete strategies do;
the interval alone cannot establish causal superiority or justify promotion.

The study's pinned dependency versions pause the collector if any input rule
changes. No observation changes setup score, eligibility, sizing, paper
orders, private orders or the real-money build lock. A later promotion would
require a separate strategy decision and safety review.
