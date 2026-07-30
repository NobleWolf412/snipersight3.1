# SniperSight — Product Review & Expansion Proposal

**Written:** 2026-07-29. Fresh read of the whole system, measured against the fact store, not asserted.
**Status:** proposal. Nothing here is built.

---

## Part 1 — How it actually works today

### The spine

Everything is one idea, executed unusually well: **a versioned, append-only fact store, with a strict
one-way layer boundary.** Each engine reads only the facts below it and writes its own kind. Nothing
looks at raw candles to form an opinion.

```
Coinbase spot ─┐
               ├─► importer ──► candles (Decimal strings, closed bars only)
Phemex perps ──┘        │
                        └─► aggregator ──► 4H, 1W (never imported; built)
                                    │
   swings ──► structure ──► zones ──────┐
      │          │            │         ├──► setups ──► execsim ──► risk ──► account
      │          └──► regime ─┘         │      (strategy)  (paper)   (authority)
      └──► liquidity ──────────────────┘
                                    scalein ──► (adds, re-runs execsim)
                                    cycles  ──► observational satellite, zero consumers
```

Two properties do most of the work here and are worth protecting at all costs:

- **`confirmed_at` vs `market_time`.** Every fact records both when it *happened* and when it became
  *knowable*. That single pair is what makes the backtest honest — no engine can act on a swing before
  its right-side bars closed. Most retail backtesters get this wrong and never find out.
- **Content-hash idempotency.** Re-running the whole pipeline over identical data writes zero facts.
  Determinism is checked, not claimed.

Add the version tag on every fact (`swing-v0.8-draft`, `setup-v0.6-draft`, …) and you get something rare:
every past decision is reconstructable, and A/B losers stay in the store as evidence rather than being
deleted. 914,251 facts, 58 symbols.

### The supporting cast

| Module | Job |
|---|---|
| `venues.py` | Single place that knows what a market *allows* — shorts, max leverage, fees, funding, liquidation math |
| `costs.py` | Immutable fee profiles; the same numbers gate the setup and price the simulated exit |
| `risk.py` | Portfolio-scoped authority. Sizes from equity, caps concurrency, halts the day at −6% |
| `quality.py` | Fail-closed A-to-Z contract audit. Refuses to evaluate performance on data it doesn't trust |
| `universe.py` | Hourly liquidity ranking across venues; fails closed below 97% rank coverage |
| `execsim.py` | Bar-walk paper fills, net of fees and slippage, with MAE/MFE recorded |
| `watchdog.py` + heartbeat | Per-stage liveness so "busy" and "hung" are distinguishable |

### The UI

Five surfaces (Command / Chart / Results / Scanner Setup / Diagnostics), phase 1 of the redesign is in.
Command and Diagnostics carry real data; Scanner Setup is four stubs; the order ticket is wired to
ticket math but `live_enabled: false` is served from the backend and the Arm button is locked.

---

## Part 2 — What's actually available

### Strategies: there are two and a half

| Name | Trigger | Bracket |
|---|---|---|
| **PULLBACK** | Trend regime + price touches an aligned supply/demand zone | Entry at zone edge, SL 0.25 ATR past far edge, TP at nearest liquidity pool |
| **REVERSAL** | TRANSITION regime + zone touch + recent liquidity sweep | same |
| **SCALE_IN** | 1H BOS inside an open 4H/1D parent that's already 1R in profit | Entry at break close, SL at parent entry, TP shared |
| *CYCLES* | Bob Loukas nested-cycle detection, BTC 1D only | **Observational. Zero consumers by design.** |

That is the entire strategy surface. PULLBACK and REVERSAL are the *same* entry logic with a different
regime gate and base rank. In the store: **559 PULLBACK setups vs 4 REVERSAL.** So functionally, the
product currently ships **one strategy**.

### Features

Manual scan trigger, universe auto-selection, setup deck with plain-English WHY, risk verdict on every
card, rejection funnel ("why nothing fired"), paper equity curve, per-symbol/per-strategy scoreboards,
setup telemetry, pipeline health audit, drift alerts, an order ticket with editable entry/TP/SL and
per-trade risk override, and a glossary layer over every domain term.

### Venues

Coinbase spot (long only, 1.00% round-trip) and Phemex perps (shorts, ≤10× declared, 0.07% round-trip).
As of S33/S34 the traded universe is **20 perps, 0 spot** — Phemex turnover beats Coinbase on every
overlapping coin, and at 14× cheaper fees routing to spot would knowingly pick the losing version.

---

## Part 3 — The finding that has to come first

I pulled the current engine generation out of the fact store rather than trusting the buildlog summary.

**`exec-v0.7-draft`: 142 filled trades, 13% win rate, −102.8R cumulative.**
The 1D book alone is −91.1R over 131 trades.

At the gate's own minimum R:R of 1.5 you need >40% wins to break even. At 13% you need R:R above 6.7
on *every* trade. This is not a tuning problem. So I went looking for the cause:

| Measurement | Value | What it means |
|---|---|---|
| Median R:R of validated setups | **6.4** (mean 8.0, max 36) | The target is far away — almost always |
| Median MFE | **1.53R** | The typical trade gets 1.5R in your favour and dies |
| Median MAE | **1.65R** | The typical trade goes *past the stop* |
| Median bars held | **0** | Most trades resolve on the bar that filled them |
| Stop-outs on the entry bar | **73 of 124 (59%)** | — |
| Ambiguous (SL+TP same bar) | 5 of 142 | So this is **not** a measurement artifact |

### The geometry is self-defeating

Zone width is `0.25 × ATR`. The stop sits `0.25 × ATR` beyond the far edge. Total risk ≈ **0.5 ATR**.
The bar that touches the zone has a range of roughly 1 ATR — by definition, since it just traded into
a zone anchored to ATR.

**The stop is inside the noise of the entry candle.** 59% of losses happen before a second bar even opens.

Then the R:R ≥ 1.5 gate makes it worse, not better. Risk is pinned near 0.5 ATR, so the *only* way a setup
passes the gate is a distant target. The gate is therefore selecting for exactly the trades least likely
to reach TP — median target 6.4R against median favourable excursion of 1.5R. The filter that was supposed
to enforce quality is instead a filter for improbability.

Two independent bugs, both fixable, neither requiring new asset classes:

1. **Stop is too tight for its own entry bar.** A structural stop has to sit beyond the *bar* that created
   the signal, not beyond an ATR-fraction of a zone.
2. **Target is unreachable.** "Nearest unbroken liquidity pool" is not a take-profit; on a 1D chart it's
   a destination three months out. There is no partial-exit or trail logic to bank the 1.5R that the
   median trade *does* offer.

**Everything else in this proposal is worth building. None of it is worth building first.** The
architecture is the asset here — it's better than most funded products. The strategy on top of it is
currently a −103R machine, and adding stocks, options and forex to a losing strategy just loses money
in five asset classes instead of one.

---

## Part 4 — Proposal

### 4.1 Make the strategy layer plural (the unlock everything else needs)

Right now "strategy" is a hard-coded function in `setups.py`. Everything the operator wants — choosing a
strategy on the setup screen, scalp vs intraday vs swing, pattern-based entries, options plays — needs the
same structural change first: **a strategy registry.**

```python
@dataclass(frozen=True)
class Strategy:
    key: str                    # "pullback", "breakout", "hs-reversal"
    version: str                # own version tag; own fact lineage
    horizon: str                # scalp | intraday | swing | position
    timeframes: tuple           # which TFs it's allowed to fire on
    asset_classes: tuple        # crypto-perp | equity | option | fx | future
    requires: tuple             # fact kinds it consumes
    def evaluate(ctx) -> Candidate | None: ...
    def bracket(ctx, c) -> Bracket: ...      # entry/SL/TP — strategy owns its own geometry
```

Why this specific shape:

- **Each strategy owns its bracket.** The current SL/TP formula is baked into the pipeline, which is why
  one geometry bug poisons every setup. A breakout strategy needs a different stop than a mean-reversion
  one. This is the fix for Part 3 and the enabler for everything below, in one change.
- **Own version tag per strategy.** A change to the breakout rules must not invalidate the pullback track
  record. The versioning discipline already exists; this extends it to the right granularity.
- **Per-strategy scoreboards fall out for free.** `/api/performance` already buckets by strategy. With N
  real strategies that page becomes the most valuable screen in the product: *which of my strategies is
  actually working, on which symbol, on which timeframe.*
- **The Scanner Setup toggles become real.** "Toggle Pullback / Reversal / Scale-in" is a stub today
  because there's nothing to toggle. With a registry it's a list render.

**Proposed starting library** — all deterministic, all buildable on facts that already exist:

| Strategy | Horizon | Built from facts that exist? |
|---|---|---|
| Pullback (fixed geometry) | swing | ✅ zones + regime |
| Breakout / BOS continuation | intraday–swing | ✅ structure BOS + volume |
| Liquidity sweep reversal | scalp–intraday | ✅ liquidity SWEEP + zone |
| Range fade | intraday | ✅ regime RANGE + zone edges |
| Trend pullback to MA | swing | needs a moving-average fact engine (trivial) |
| Compression → expansion | intraday | needs a volatility-state engine (ATR percentile) |

Two new low-level engines (`ma.py`, `volatility.py`) unlock four of these. Both are ~80 lines and fit the
existing engine contract exactly.

### 4.2 Pattern recognition (the Finviz idea)

Yes — and it fits the architecture better than you'd expect. Finviz classifies stocks by chart pattern:
head & shoulders, rising wedge, descending channel, triangles, double tops, flags.

**The insight: you already have the primitives.** A pattern is a *geometric relationship between swings*,
and swing detection is the most mature engine in the system (v0.8, tiered, golden-calibrated, with
promotion evidence attached). Finviz-grade pattern detection is a `patterns.py` engine that reads swing
facts and emits `pattern` facts:

```
Head & shoulders   = HIGH, higher HIGH, lower HIGH + a neckline from the two LOWs between
Double top         = two HIGHs within 0.10 ATR (this is literally your liquidity-pool rule)
Ascending triangle = flat HIGH cluster + rising HL sequence
Rising wedge       = converging trendlines, both slopes positive
Bull flag          = impulse leg + tight counter-trend channel
Channel            = parallel regression on alternating swing extremes
```

Design rules to keep it honest, following the house style:

- **Patterns are a fact kind, not a strategy.** `patterns.py` emits `pattern` facts with a confirmation
  bar and a `confirmed_at`. Strategies *consume* them. Same one-way boundary as everything else.
- **A pattern must have a break level, or it isn't emitted.** "Descending channel" with no defined
  invalidation is decoration. Every pattern fact carries `break_level`, `target`, `invalidation`.
- **Timeframe-scoped, as you said.** A 15m flag and a 1W flag are different objects. Emit per TF, filter
  in the UI by the TF being viewed.
- **Earn promotion the way cycles must.** Retro-tag historical setups with the pattern context that was
  active, compare outcome distributions, promote to a scored input only if the split is real. Otherwise
  it stays a chart overlay and a screener filter — which is still genuinely useful.

This also gives the product a **screener** surface, which is the Finviz experience proper: "show me every
symbol in my universe currently printing a bull flag on 4H." That is a feature people pay for on its own,
independent of whether it feeds auto-trading.

### 4.3 Venues and brokers — what's actually reachable by API

You asked for crypto, stocks, commodities, forex, and options, and only providers where a retail user can
actually be *tradable* through the API. Here's the honest landscape as of mid-2026.

| Provider | Assets tradable via API | Auto-trade viable? | Notes |
|---|---|---|---|
| **Schwab Trader API** | US equities, ETFs, **options incl. multi-leg** | ✅ for your own account | Your broker. Market/limit/stop/stop-limit/trailing/OCO/OTO. **No futures, no forex, no crypto** — futures orders return HTTP 400. Individual dev access is self-serve; letting *other* users connect their Schwab accounts requires a separate commercial review that explicitly scrutinises automated/AI functionality |
| **Interactive Brokers** | Equities, options, **futures, FX, bonds**, global markets | ✅ | The only single API that covers your whole asset wish-list. Heavier integration (TWS/Gateway or the newer REST) |
| **Alpaca** | US equities, ETFs, options, some crypto | ✅ | Cleanest modern REST+WebSocket. Best *first* stock adapter — paper trading is first-class, which matches how this system is built |
| **Tradier** | Equities, options | ✅ | Simple REST, low friction, options-focused |
| **Tradovate / NinjaTrader** | Futures (incl. commodities, indices) | ✅ | The commodities answer. Futures ≠ equities in margin and session handling |
| **OANDA** | Forex, CFDs | ✅ | The forex answer, mature REST API |
| **Kraken** | Crypto spot + **CFTC-regulated US perps** (9 coins, launched 2026) | ✅ | **This is the important one for you.** US-legal perps with leverage |
| **Coinbase** | Spot + CFTC-registered perpetual-style futures (BTC/ETH, ≤10×) | ✅ | Already integrated for spot |
| **Phemex** | Perps, everything | ⚠️ | Currently your traded universe. **US residency restriction is unresolved** — flagged as open question #1 in the redesign plan and still open |

**Recommended venue path, in order:**

1. **Kraken perps** — replaces the Phemex US-legality question with a CFTC-regulated answer, keeps the
   entire perp thesis (shorts, cheap fees, leverage) intact, and is a near-identical adapter to the one
   you just wrote. This is a small change that removes your single largest legal risk.
2. **Alpaca** — first equities adapter. Proves the `Venue` abstraction survives a genuinely different
   asset class (sessions, halts, gaps, corporate actions, PDT rule) at the lowest integration cost.
3. **Schwab** — your actual broker, and the options venue. Do this *after* Alpaca proves the equity model,
   because Schwab's OAuth and approval flow is more friction to iterate against.
4. **IBKR or Tradovate** — commodities/futures, once one of the above is running live.
5. **OANDA** — forex, last. Forex has the least in common with everything else you've built (no volume
   data worth trusting, 24×5 sessions, different liquidity structure).

**What each new asset class actually costs you** — this is not "add an adapter":

- **Equities:** trading sessions and overnight gaps (a stop can't fill at 3am), halts, splits and dividends
  rewriting historical prices, PDT rule under $25k, hard-to-borrow for shorts, 4H candles that don't divide
  evenly into a 6.5-hour session.
- **Options:** a different instrument model entirely — strikes, expiries, greeks, IV, assignment risk,
  spreads as single positions. Your risk authority sizes by "distance to stop," which doesn't exist for a
  long option. **This is the biggest single piece of work in the whole proposal.**
- **Futures:** contract rollover, tick values, session-based margin, expiry.
- **Forex:** no meaningful volume, pip conventions, weekend gaps.

`venues.py` already has the right shape to absorb the first, third and fourth. Options need a parallel
instrument layer, which is why I'd sequence them where I have.

### 4.4 Options — the honest version

You asked for options strategies. The structural problem: **every engine below `setups.py` assumes a
linear instrument.** Zones, ATR stops, R-multiples, and "risk = distance to stop" are all price-space
concepts. An option's P&L is a function of price, time, and volatility, and it can go to zero without
price ever touching your stop.

The clean way in — and it keeps the whole existing spine intact:

> **Options are an expression layer, not a signal layer.**

The scanner keeps producing directional theses on the *underlying* (SPY is a pullback long, R:R 2.4,
targeting 3% over ~8 days). A new `expression.py` layer translates a thesis into the best available
instrument:

| Thesis shape | Expression |
|---|---|
| Directional, high conviction, defined risk | Long call/put or vertical debit spread |
| Directional, want theta on your side | Credit spread against the invalidation level |
| Range regime, defined range | Iron condor at the range edges |
| High IV rank + directional | Sell premium; low IV rank + directional → buy premium |

Risk sizing then becomes "max loss of the structure" instead of "distance to stop," which is *cleaner* —
defined-risk option structures actually fit a risk authority better than a stop does, because max loss is
known at entry and can't gap through.

Prerequisites: an options chain feed (Schwab provides it), IV rank as a fact, and expiry/strike selection
rules. Real work, but it slots into the architecture rather than fighting it.

### 4.5 Auto mode

The rails are largely there and correctly locked. What's missing to make Auto real:

**Order state machine.** `execsim.py` simulates fills by walking bars. Live trading needs a persistent
position manager that reconciles against the broker: orders can partially fill, get rejected, or fill at a
different price. Facts should record intent *and* observed outcome, and they will disagree. This module
does not exist yet and is the single biggest gap between paper and live.

**Auto guardrails** — the redesign plan already names the right ones; I'd add two:

- Total drawdown halt (planned) · data-health halt on quality BLOCKED (planned) · arm-with-timer (planned)
  · always-visible HALT ALL (planned)
- **Per-strategy circuit breaker** — auto-disable a strategy after N consecutive losses or a drawdown
  threshold *within that strategy*. With a plural strategy layer this becomes essential; one broken
  strategy shouldn't drain the account while three good ones work.
- **Shadow mode** as the mandatory first live step: full live code path, order construction and all,
  submission suppressed and logged. Proves the plumbing before risking money. Already recommended in the
  redesign plan — I'd make it non-skippable.

**Leverage as a user dial:** keep the current principle absolutely — size is derived from risk, leverage is
the *consequence*. The dial should set a *cap*, never a multiplier on risk. The liquidation gate in
`venues.py` already does the right thing; it just needs to be surfaced in the ticket ("at 10× your stop
sits $340 from liquidation").

### 4.6 UI — keeping it simple while adding all of this

The stated goal is state-of-the-art analysis with clarity and simplicity. Those pull against each other,
and the five-surface IA is the right defence. Where the new capability lands:

- **Command** — unchanged in shape. Setup deck gains a strategy chip per card and a horizon filter
  (scalp / intraday / swing). One more chip, not one more screen.
- **Screener** (new, 6th surface) — the Finviz-style pattern grid. Symbols × patterns × timeframe.
  This is the one genuinely new surface I'd add, and it earns its place because it answers a question no
  existing surface does: *what is the whole market doing right now?*
- **Chart** — pattern overlay joins the existing toggles. Option expression shown as a second panel on the
  ticket when the venue supports it.
- **Scanner Setup** — the stubs become real: strategy toggles (from the registry), venue + credentials,
  risk envelope, auto arm. This is where "choose a strategy" lives, as you described.
- **Results** — becomes the strategy leaderboard. With N strategies this is where the product proves
  itself. Keep the STRATEGY vs OPERATOR split from the redesign plan; it's the right call.
- **Portfolio** — you mentioned "manage their portfolio AND trade in one spot." Once real broker adapters
  exist, positions and balances come from the broker, not the paper simulator. That's a genuine addition
  to Results rather than a new surface.

**One simplicity rule worth adopting explicitly:** every new capability must answer an existing surface's
question, or it needs its own surface. Nothing gets bolted onto Command.

---

## Part 5 — Sequencing

| # | Work | Why here |
|---|---|---|
| **0** | **Fix the bracket geometry.** Stop beyond the signal bar; partial exit / trail at structure; realistic targets. Re-measure. | Nothing else matters until the edge is non-negative. This is days, not weeks, and the data to validate it is already in the store |
| **1** | Strategy registry + per-strategy bracket ownership | The structural unlock for every user-facing ask |
| **2** | `ma.py`, `volatility.py`, `patterns.py` + 3–4 new strategies | Real strategy choice on the setup screen; Finviz-style screener |
| **3** | Kraken perp adapter | Removes the US-legality risk on your only traded venue |
| **4** | Position manager + shadow mode | The real paper→live gap |
| **5** | Alpaca equities adapter | Proves the venue abstraction across asset classes |
| **6** | Auto mode + guardrails + per-strategy circuit breakers | Only after the manual path is trustworthy |
| **7** | Schwab adapter + options expression layer | Largest scope; deserves its own phase |
| **8** | Futures (Tradovate/IBKR), forex (OANDA) | Breadth, once depth is proven |

Steps 0–2 are where nearly all the value is, and none of them require a new broker, a new asset class, or
a line of live-order code.

---

## Part 6 — Open questions for you

1. **Phemex US access** — do you actually have working access, or is the current traded universe legally
   unavailable to you? This determines whether step 3 is urgent or merely sensible.
2. **Product or personal tool?** "Provide a service to users" implies multi-tenant: per-user credentials,
   per-user risk envelopes, and — for Schwab specifically — a commercial approval that explicitly reviews
   automated/AI functionality. That's a very different build than one operator's cockpit. Worth deciding
   now, because it changes the credential and account model at the root.
3. **Which asset class do you actually want to trade first?** The proposal sequences crypto → equities →
   options because that's the cheapest path through the architecture. If options on Schwab are the real
   goal, the sequence changes.
4. **Auto-trade risk appetite.** The current envelope (2% per trade, 4% total, 6% daily halt) is sane for
   a proven edge. Against an unproven one, auto mode at those numbers loses money faster. Should auto mode
   start at a reduced envelope until a strategy has N forward trades?

---

## Appendix — measurements cited

All from `app/data/snipersight.db`, 2026-07-29.

```
exec-v0.7-draft (current):  n=142 filled   win=13%   ΣR=−102.8
  by timeframe:  1D n=131 ΣR=−91.1 · 1H n=6 ΣR=−8.2 · 4H n=4 ΣR=−5.7 · 15m n=1 ΣR=+2.2
  bars_held=0:   78 of 142 (73 of those were stop-outs)
  ambiguous:     5 of 142  → same-bar resolution is real, not a measurement artifact
validated setups (setup-v0.6-draft):  n=303  median R:R 6.4  mean 8.0  max 36.1
excursions:  median MAE 1.65R · median MFE 1.53R
rejections:  NO_ELIGIBLE_PLAYBOOK 7,148 · UNECONOMIC_AFTER_COSTS 675 · RR_BELOW_MINIMUM 278
setup population:  PULLBACK 559 · REVERSAL 4 · (SCALE_IN separate version)
store:  914,251 facts · 58 symbols
```
