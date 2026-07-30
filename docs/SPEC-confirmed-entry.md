# SPEC — Confirmed Entry, Confluence Evidence, and the Explanatory Layer

**Status:** §1.1–1.5 BUILT and MEASURED. §1.6 (managed exit) **REJECTED by its own gate.**
Written 2026-07-30, updated the same day with the 2×2 result.
**Supersedes nothing.** Every version bump below leaves existing facts in place.

---

## RESULT — read this before the spec below

The 2×2 ran (`engine/abtest.py`, calibrated to reproduce the recorded book to
1.2%). On the **actually-traded universe** — the 20 Phemex perps; the spot book
is history and is not coming back:

| cell | n | win% | ΣR | expectancy | 95% CI | **same-bar stop-outs** |
|---|---|---|---|---|---|---|
| touch + hold *(v0.6 baseline)* | 53 | 11.3% | −22.9 | −0.433 R | [−0.953, +0.251] | **57.4%** |
| touch + managed exit | 53 | 30.2% | −1.5 | −0.028 R | [−0.321, +0.284] | 70.3% |
| **confirmed + hold** | **114** | **30.7%** | **−1.9** | **−0.017 R** | [−0.326, +0.310] | **13.9%** |
| confirmed + managed exit | 115 | 31.3% | −19.6 | −0.171 R | [−0.357, +0.017] | 20.3% |

**Three findings, in order of importance:**

1. **The confirmation rule works, and did exactly what it was designed to do.**
   Same-bar stop-outs **57.4% → 13.9%**, comfortably inside the <20% pass
   criterion. Win rate nearly tripled (11.3% → 30.7%). Sample size more than
   doubled (53 → 114) because market-on-next-open eliminates the 39% miss rate.
   Expectancy moved from −0.433 R to −0.017 R. **§1.1–1.5 SHIP.**

2. **The managed exit must NOT ship.** It makes the confirmed entry *worse*
   (−0.017 → −0.171 R). The mechanism is coherent: a partial at 1.5R plus a
   breakeven move caps a trade that now has a wide enough stop to actually run,
   and converts would-be winners into scratches. §1.6 was written from excursion
   data measured on the BROKEN entry — median MFE 1.53R was a symptom of trades
   dying early, not evidence that 1.5R is where they should be cut.
   **§1.6 is rejected. It was my recommendation and the data disagrees with it.**

3. **Fixing the entry did not create an edge — it made the strategy measurable.**
   −0.017 R with a CI straddling zero is *flat*, not profitable. What changed is
   that the book is no longer dominated by an execution defect, so from here a
   strategy comparison means something. That is the honest win.

**A near-miss worth recording.** Across the FULL history (including retired
Coinbase spot symbols) the touch+managed cell showed +0.322 R, PF 1.69, P(>0)
99.4% — and it was an artifact: **96% of that profit came from three illiquid
spot alts** (LSETH-USD, DIA-USD, COTI-USD), two of which are the same symbols
whose stale candles were generating the drift-alert spam. Dropping the top 3
trades collapsed it to +0.189 R with a CI including zero. Reporting that number
without the concentration check would have shipped the wrong system on a
confident-looking statistic.

This spec covers one engine change and everything downstream of it, including
what a first-time user sees and how they learn what any of it means.

---

## 0. Why (one paragraph, so the spec can be argued with)

Measured on the store: `exec-v0.7-draft` is 142 filled trades, 13% win rate,
−102.8R. **59% of stop-outs happen on the bar that fills the entry** (73 of 124).
Entry fires the instant price contacts a zone, the stop sits ~0.5 ATR away, and
the bar that makes contact has a range of roughly 1 ATR — so the trigger bar and
the killing bar are the same bar. Separately, median target is 6.4R against a
median favourable excursion of 1.53R, because risk is pinned near 0.5 ATR and the
R:R ≥ 1.5 gate can therefore only be satisfied by a distant target. The gate
selects for improbability.

**A confirmation rule fixes both at once.** Waiting for a close means the wick
that would have stopped you has already happened, and it hands you a real
structural stop — a low the market visibly rejected — instead of an arbitrary
ATR offset. A wider, earned stop un-pins risk, which lets targets come back to
reachable distances.

---

## 1. Engine — `setup-v0.7-draft`

### 1.1 New lifecycle

```
FORMING ──► CONFIRMING ──► VALIDATED ──► EXPIRED
   │             │
   └─►CANCELLED  └─►CANCELLED
```

| State | Meaning | Tradeable? | Notifies? |
|---|---|---|---|
| `FORMING` | Price approaching an aligned zone | no | no |
| `CONFIRMING` | **new** — price is IN the zone, waiting for proof it held | no | no |
| `VALIDATED` | Confirmation printed. This is a trade | yes | **yes** |
| `EXPIRED` | Zone broke after validation | no | no |
| `CANCELLED` | Confirmation never came, or the zone broke first | no | no |

`CONFIRMING` is the state that used to be `VALIDATED`. Nothing that reads
`VALIDATED` today starts trading something new — it starts trading something
*later and better evidenced*.

### 1.2 Confirmation predicate

A candidate enters `CONFIRMING` on the touch bar. From the next bar, for at most
`CONFIRM_MAX_BARS = 3` bars, it confirms when a **closed** bar satisfies all of:

**LONG (demand zone):**
1. `low <= zone.top` — the bar engaged the zone
2. `close > zone.top` — and closed back out of it (reclaim)
3. `close >= low + REJECTION_FRACTION * (high - low)`, `REJECTION_FRACTION = 0.66`
   — the close sits in the upper third: a rejection wick, not a weak drift

**SHORT (supply zone):** mirrored (`high >= zone.bottom`, `close < zone.bottom`,
`close <= high - 0.66 * (high - low)`).

Terminal transitions from `CONFIRMING`:
- confirming bar found → `VALIDATED`
- `CONFIRM_MAX_BARS` elapse → `CANCELLED`, reason `CONFIRMATION_TIMEOUT`
- zone breaks first → `CANCELLED`, reason `ZONE_BROKE_UNCONFIRMED`

> **Determinism note.** Every input is a closed bar. `confirmed_at` is the
> confirming bar's close time. No developing-candle data enters (§5).

### 1.3 New bracket

| | Today (v0.6) | Proposed (v0.7) |
|---|---|---|
| Entry | zone edge, resting LIMIT | **next bar's OPEN**, MARKET |
| Stop | far zone edge ∓ 0.25 ATR | beyond the **confirmation bar's extreme** ∓ `SL_BUFFER_ATR` (0.15) |
| Target | nearest unbroken liquidity pool | nearest opposing structure of **either** kind, capped at `MAX_TARGET_R = 3` |

Three deliberate changes, each with a cost stated:

**Entry becomes market-on-next-open.** The next bar's open is a price that
demonstrably traded — no fill assumption is required. This eliminates the
`MISSED` outcome entirely (currently **90 of 232 orders, a 39% miss rate**) at
the cost of paying taker fees on entry instead of maker. On perps that is 0.06%
vs 0.01%; on spot it would be 0.6% vs 0.4% and this choice should be revisited.
Record `entry_fee_role: "TAKER"`.

**Stop becomes the confirmation bar's low (LONG), not a zone offset.** Structural
and already tested by the market. It will be **wider**, which reduces position
size for the same dollar risk — that is the point, not a side effect.

**Target caps at 3R and considers swings as well as pools.** Today `target()`
prefers pools and only falls back to swings, which is what produces 6.4R medians.
Record BOTH `tp_uncapped` and `tp` so a later version can measure whether the cap
helped or cost.

### 1.4 Confluence — recorded, not filtered

Per the house rule already written into `swings.py` (*"evidence becomes a
required filter only after the user grades it"*), **v0.7 scores confluence and
gates on none of it.** Every setup fact — and every rejection fact — carries:

```jsonc
"confluence": {
  "htf_regime_aligned":   true,     // 1D regime agrees with a 4H trade
  "htf_regime":           "BULL_TREND",
  "zone_strength":        72,       // zones.py already computes this
  "zone_episode":         1,        // 1 = untouched before now
  "anchor_tier":          "MAJOR",
  "volume_expansion":     1.8,      // confirm bar vs 20-bar average
  "sweep_nearby":         false,
  "bars_since_break":     4,        // structure recency, trade direction
  "target_distance_r":    2.4,
  "score":                0         // ALWAYS 0 in v0.7 — see below
}
```

`score` is emitted as 0 and unused. It exists so the field is present in the
schema from day one and a later version can populate it without a migration.

**How the factors get graded — and this is the cheap part.** The store already
holds 928 closed simulated trades and 8,102 rejected candidates. Every factor
above is computable at timestamps it was knowable, and `admitted_at` already
guards against lookahead. A factor earns a gate only when it separates outcome
distributions on that existing data. No forward waiting required.

**The promotion criterion, stated so it can't be fudged.** Ported from
`snipersight-trading/backend/diagnostics/factor_contribution.py` — see
`SALVAGE-from-snipersight-trading.md` §1.1. A factor is promoted from evidence to
gate only when it clears all five:

| Axis | Bar |
|---|---|
| **Fire rate** | present in ≥ 10% of candidates — a factor that never fires cannot help |
| **Dispersion** | score std ≥ 8 when present — near-zero means it says the same thing every time |
| **Contribution** | measurably moves the composite |
| **Redundancy** | \|Pearson r\| < 0.70 against every already-promoted factor. **One factor per information category** |
| **Outcome edge** | correlation with realised R clears the noise floor **±1.96/√n**. A *negative* r means the factor scores high on losers — that is a finding, not a failure |

The redundancy axis is the whole reason the old project's 26-factor scorer failed:
five correlated HTF inputs counted as five confirmations were one. It ships as a
gate here, not as advice.

Of these, **`htf_regime_aligned` is the one to watch.** The entire 1D book is
−91R, and `scalein.py` already encodes the principle — *"the higher timeframe
GATES the lower"* — it simply was never applied to the primary entry.

### 1.5 Strategy toggles become real

`engine/settings.py` already defines `strategy_pullback`, `strategy_reversal`,
`strategy_scale_in` as BEHAVIOURAL settings with baseline-reset semantics, and
`/api/settings` is wired. **`setups.py` does not read them** — the toggles are
currently inert. v0.7 reads them in `playbook()` and records the active set in
the strategy manifest, so a fact can be traced to the configuration that
produced it.

### 1.6 Trade management — promoted INTO this change

> **Added after reviewing `snipersight-trading`.** Originally out of scope. It is
> not: median MFE is **1.53R** against a median target of **6.4R**, which says the
> exit is at least as broken as the entry. A confirmed entry with an unchanged
> hold-to-TP-or-SL exit fixes half the problem and would measure as a partial
> failure — hiding the fact that the entry fix worked.

`execsim.py` currently walks bars to SL or TP and stops. No partial exits, no
breakeven move, no trailing, no time stop. Three additions, all R-denominated so
they stay position-size agnostic:

**a) Partial exits — the piece that actually matches the measurement.**
Two targets, not one. `TP1 = 1.5R` closes `PARTIAL_FRACTION = 0.5` of the
position; the remainder runs to the structural target with the stop trailing.

This is the direct answer to the excursion data. Median MFE is **1.53R** — meaning
*half of all trades reach 1.5R* — against a median target of 6.4R that almost
nothing reaches. A fixed 1.5R first target converts the most common favourable
outcome in the book from a round trip into a realised gain. Nothing else in this
spec touches that population.

Requires `execsim` to carry position state across bars (quantity, realised R so
far) rather than resolving each setup to a single terminal outcome. That is a real
structural change to the simulator and the largest single piece of work here.

Exec facts gain `partials: [{r, fraction, ts}]` and `r_multiple` becomes the
**weighted** result. Keep `r_if_held` alongside it — without that, we cannot tell
whether taking partials helped or cost, which is exactly the question.

**b) Trailing stop.** Activates at `TRAIL_ACTIVATE_R = 1.5`, trails
`TRAIL_DISTANCE_R = 0.5` behind the running favourable extreme, on the remainder
after TP1.

**c) Breakeven move.** Stop → entry once `BE_TRIGGER_R = 1.0` is reached. Record
`be_moved_at` so the telemetry can separate "stopped at breakeven" from "stopped
for a loss" — they are different outcomes and averaging them hides both.

**c) Adaptive time stop.** Not a flat timer — hold time scales with what the trade
is (ported concept, `SALVAGE` §2.1):

```
base:           scalp 5h · intraday 14h · swing 48h
× trend:        strong 1.5 · normal 1.3 · sideways 0.8
× volatility:   compressed 0.7 · normal 1.0 · elevated 1.2
× counter-trend: 0.7      (a LONG in a downtrend gets LESS patience, not more)
clamp 1h–120h
```

Two guards, both load-bearing:
- **Minimum-progress threshold** before the time stop may fire, so a slow winner is
  not cut as stagnant.
- **`STAGNATION_FLOOR_RATIO = 0.7`** — never time-stop a trade already more than 70%
  of the way to its stop; defer to the stop. Expressed as a fraction of *stop
  distance*, so it self-scales to each trade.

This is also what makes **scalp / intraday / swing** mean something. A horizon is
not a timeframe — it is a hold-time policy plus an exit policy. `Strategy.horizon`
selects this block.

### 1.7 Cooldowns — duplicate-trade control

Nothing currently stops the scanner re-entering a level that just stopped it out.
Per **symbol + direction**, persisted, with the durations deliberately asymmetric:

| Exit reason | Cooldown | Why |
|---|---|---|
| Stop-out | 24h | The level was **invalidated**. Re-buying it is buying a broken thesis |
| Target / trail / time stop | scalp 0.25h · intraday 0.5h · swing 1h | The level is **not invalidated, just recently resolved** |

Emitted as a `cooldown` fact so a rejection is auditable like every other, with
reason `SYMBOL_IN_COOLDOWN` and the expiry attached.

### 1.8 Constants

```python
SETUP_VERSION       = "setup-v0.7-draft"
CONFIRM_MAX_BARS    = 3
REJECTION_FRACTION  = Decimal("0.66")
SL_BUFFER_ATR       = Decimal("0.15")
MAX_TARGET_R        = Decimal("3")
ENTRY_MODEL         = "MARKET_NEXT_OPEN"
# exit management (§1.6)
TRAIL_ACTIVATE_R      = Decimal("1.5")
TRAIL_DISTANCE_R      = Decimal("0.5")
BE_TRIGGER_R          = Decimal("1.0")
STAGNATION_FLOOR_RATIO = Decimal("0.7")
# cooldowns (§1.7), hours
COOLDOWN_STOP_OUT     = 24.0
COOLDOWN_RESOLVED     = {"scalp": 0.25, "intraday": 0.5, "swing": 1.0}
```

---

## 2. Dependency map — everything this touches

### 2.1 Engine (Python)

| File | Change | Version bump |
|---|---|---|
| `engine/setups.py` | The above | **`setup-v0.7-draft`** |
| `engine/execsim.py` | Handle `MARKET_NEXT_OPEN` (fill = next open, no `MISSED` path); entry fee role TAKER; skip `CONFIRMING` facts | **`exec-v0.8-draft`** |
| `engine/risk.py` | `state == "VALIDATED"` filter still correct, but brackets differ → sizes differ → decisions differ | **`risk-v0.8-draft`** |
| `engine/scalein.py` | Parent brackets change → adds differ | **`scale-v0.3-draft`** |
| `engine/quality.py` | `_versions()` map; SETUP-stage checks must recognise `CONFIRMING`/`CANCELLED` as valid non-terminal states, not anomalies | no bump (audit, not facts) |
| `engine/apexbridge.py` | Reads `setups.SETUP_VERSION` — follows automatically | none |
| `engine/settings.py` | No change; `setups.py` starts reading it | none |
| `engine/store.py` | **No schema change.** Payload is JSON | none |
| `engine/telemetry.py` | New lifecycle stage + failure codes (§3) | none |
| `engine/diagnostics.py` | New rule ids for the confirmation stage | none |

> **Ordering constraint.** `execsim`, `risk` and `scalein` all import
> `SETUP_VERSION` from `setups`. They must be bumped in the same change, or the
> pipeline will silently read v0.7 setups with v0.6-era assumptions.

### 2.2 API (`server.py`)

| Location | Change |
|---|---|
| `KIND_VERSIONS` | new setup/exec/risk versions |
| `_baseline_setup_ids()` | still filters `state == "VALIDATED"` — **correct, no change**, but add a docstring note that `CONFIRMING` is deliberately excluded from the tradeable set |
| `/api/facts?kind=setup` | version list gains v0.7 |
| `/api/overview` → `feed` | carry `CONFIRMING` items so the deck can show them |
| `/api/context` | `{forming, confirming, ready}` — new middle count |
| `/api/setup-telemetry` | new funnel stage (§3) |
| `/api/performance` | unchanged shape; numbers change |
| `/api/trade-config` | add `entry_model` so the ticket can label MARKET vs LIMIT honestly |
| **`/api/playbooks`** | **new** — see §5.1 |

### 2.3 Front end

| File | Change |
|---|---|
| `static/shell.js` | Deck renders three tiers (§4.1); counts; empty-state copy |
| `static/shell.html` | Playbook catalogue panel; Market Weather strip; first-run guide |
| `static/chart.js` | Draw the confirmation bar marker, the new structural stop, and the zone that produced it |
| `static/glossary.js` | New terms (§5.4) |
| `static/ss.css` | One new chip state for `CONFIRMING` |

### 2.4 Baseline

A behavioural change resets the forward baseline — that rule already exists in
`settings.py` and applies here. Old facts are retained; the v0.6 record stays
readable as the A/B loser. **State this in the UI when it happens**, don't let a
user discover their track record restarted.

---

## 3. Telemetry & Diagnostics

### 3.1 The funnel gains its most important stage

Today: `rejected → validated → risk_approved → placed → filled → closed → winners`

Proposed:

```
candidates rejected  →  CONFIRMING  →  confirmed (VALIDATED)  →  risk approved
                            │
                            └──► cancelled: timeout / zone broke
                    →  filled  →  closed  →  winners
```

This is the single most diagnostic number the system will have. **"How many
zone touches survive confirmation"** directly measures whether the confirmation
rule is too strict (nothing confirms, throughput collapses) or too loose (it
confirms everything and the win rate doesn't move). Neither failure is visible
without this stage.

### 3.2 `telemetry.classify_failure()` additions

| Stage | `failure_code` | `failure_owner` | Detail |
|---|---|---|---|
| `CONFIRMING` | `AWAITING_CONFIRMATION` | none | in the confirmation window |
| `CANCELLED` | `CONFIRMATION_TIMEOUT` | `ENTRY_MODEL` | zone held but never printed a confirming close |
| `CANCELLED` | `ZONE_BROKE_UNCONFIRMED` | `SETUP` | the level failed — correctly avoided |

Add `AWAITING_CONFIRMATION` to `NON_FAILURES` and all three to
`NORMAL_OUTCOMES`. **`ZONE_BROKE_UNCONFIRMED` is a save, not a failure** — the
UI must present it as "avoided a loser," because presenting avoided losses as
attrition teaches the user to distrust the filter that is helping them.

### 3.3 Diagnostics surface

Add to the Diagnostics page:
- **Confirmation yield** — `confirmed / (confirmed + cancelled)` per timeframe.
  Target range 15–40%; below 10% the rule is choking throughput, above 60% it
  isn't filtering.
- **Same-bar stop-out rate** — the metric that started this. Today 59%.
  This is the pass/fail number for the whole change and it belongs on screen.
- **Confluence factor table** — each factor, split by outcome, on closed trades.
  Read-only evidence. This is what earns a factor its promotion to a gate.

---

## 4. What the user sees

### 4.1 Three tiers, and only one of them interrupts you

This also settles the notification policy question:

| Tier | Where | Notification |
|---|---|---|
| `FORMING` | **Watchlist** — a quiet collapsed list, count only | never |
| `CONFIRMING` | **Deck**, amber, "waiting for confirmation · 2 bars left" | never |
| `VALIDATED` **and** risk-approved | **Deck**, green, actionable | **yes** |
| `VALIDATED` but risk-rejected | Deck, greyed, with the reason | never |

A notification is an interruption; it should mean *"you can act on this right
now."* Everything else is a dashboard, not a buzz. `ANNOUNCE_STATES` becomes
`("VALIDATED",)` and the announce path additionally consults the risk verdict.

### 4.2 The setup card explains itself in four lines

```
┌────────────────────────────────────────────────────────┐
│ SOLUSDT   4H   PULLBACK          LONG      rank 78     │
│                                                        │
│ WHY        Bull trend · pullback into demand           │
│            182.40–184.10                               │
│ CONFIRMED  Closed back above the zone with a           │
│            rejection wick · volume 1.8×                │
│ SUPPORT    Daily trend agrees · zone untouched ·        │
│            major swing anchor                          │
│ RISK       APPROVED · risks $204 · 1.12 units          │
│                                                        │
│ entry 184.30   stop 181.90   target 191.50   R:R 2.9   │
└────────────────────────────────────────────────────────┘
```

- **WHY** — the market condition (exists today)
- **CONFIRMED** — *what actually printed*. New, and the most trust-building line
  on the card: it names the evidence rather than asserting a score
- **SUPPORT** — confluence in plain words, no numbers, no fake precision
- **RISK** — the authority's verdict (exists today)

### 4.3 Market Weather — the missing conceptual link

Users don't know what "regime" is *for*. Regime is currently a chip on the chart
and nothing else. Put a strip on Command that connects condition → playbook:

```
MARKET WEATHER                                    what this means
SOLUSDT   1D  Bull trend    4H  Bull trend    →   Pullback longs are live
BTCUSDT   1D  Range         4H  Range         →   No playbook covers ranges yet
ETHUSDT   1D  Bull trend    4H  Transition    →   Timeframes disagree — waiting
```

The right column is the whole point: it tells the user **why the scanner is
quiet**, in a sentence, without them learning any vocabulary first.

### 4.4 Empty states keep teaching

Extend the existing rejection funnel copy from *what was rejected* to *what
would change it*:

> **No setups right now.**
> 41 candidates checked in the last hour.
> 28 — no playbook for a ranging market *(a range strategy is planned)*
> 9 — the zone broke before confirming *(a loss avoided)*
> 4 — reward wasn't worth the risk

---

## 5. The explanatory layer

The operator's own verdict, quoted in the redesign plan, was *"there's lingo I
have no idea what it means, features I don't know what they are, zero
explanation."* The glossary (40 terms, hover-to-define) fixed vocabulary.
It did not fix **orientation** — what to do, in what order, and why.

### 5.1 Playbook catalogue — new panel on Scanner Setup

`GET /api/playbooks` returns, per strategy, its rules **and its live scoreboard**
from the same facts the Results page uses. One card each:

```
┌─ PULLBACK ────────────────────────────── [ ON ] ─┐
│ Buy the dip in an uptrend, sell the bounce       │
│ in a downtrend.                                  │
│                                                  │
│ HUNTS       Trending markets                     │
│ TRIGGERS    Price returns to a zone that         │
│             previously turned it                 │
│ CONFIRMS    A close back out of the zone with    │
│             a rejection wick                     │
│ STOP GOES   Below the low that rejected          │
│ HOLDS FOR   Hours to days (4H / 1D)              │
│                                                  │
│ RECORD      31 trades · 42% win · +8.4R          │
└──────────────────────────────────────────────────┘
```

Five labels, same five on every card, so they become comparable at a glance.
**The record line is not optional.** A playbook that shows its own losing record
is the difference between a tool and a sales page — and it is the only honest way
to let a user choose between strategies.

Cards render for planned strategies too, greyed, marked *planned*, with the gap
named ("27% of rejected candidates are ranging markets — this is why"). That
turns the roadmap into an explanation instead of a promise.

The `[ ON ]` toggle writes to `/api/settings` and inherits its existing warning:
*this starts a new forward record.*

### 5.2 First-run guide

Dismissible card, top of Command, returns via a `?` in the top bar. Four steps,
no jargon:

1. **Pick your market.** Right now: crypto perpetuals on Phemex.
2. **The scanner watches for setups.** It checks every minute and only speaks
   up when something is tradeable. Quiet is normal — roughly one a day.
3. **When a setup appears**, the card tells you why, what confirmed it, and what
   it risks. Click through to the chart to adjust entry, target or stop.
4. **Nothing is real yet.** This is paper trading. Live orders unlock when the
   forward record earns it.

Ends with: *"Everything underlined explains itself — hover it."*

### 5.3 Persistent orientation

Each surface header already asks its question (*"What should I do right now?"*).
Extend to a one-line answer beneath:

| Surface | Existing question | Add |
|---|---|---|
| Command | What should I do right now? | *Setups appear here when the market meets a playbook's conditions.* |
| Chart | Is this trade good, and what are my levels? | *Drag entry, target or stop — size updates live.* |
| Results | Is this actually working? | *Only trades since the current baseline count.* |
| Scanner Setup | What is the bot allowed to do? | *Changes marked ⚠ restart your track record.* |
| Diagnostics | Is the machine telling me the truth? | *Check here before trusting any number on Results.* |

### 5.4 Glossary additions

`confirmation`, `confirming`, `confluence`, `playbook`, `htfAlignment`,
`rejectionWick`, `structuralStop`, `entryModel`, `confirmationYield`.

House style, plain sentence first:

> **confirmation** — Proof that a level held before the trade opens. Price
> touching a zone isn't enough; SniperSight waits for a candle to close back out
> of it. Costs a little of the move, avoids a lot of the losses.

> **confluence** — Separate reasons pointing the same way — the daily trend
> agreeing, a fresh zone, heavy volume. Currently recorded and shown, but not yet
> used to accept or reject anything: a factor has to prove it predicts outcomes
> before it's allowed to.

---

## 6. Build order

| # | Step | Verifies |
|---|---|---|
| 0 | **`edge_significance` port** — bootstrap CI on the *existing* book | settles whether −102.8R is a real negative edge or noise, before anything is built on the assumption |
| 1 | `setups.py` v0.7 + confirmation + new bracket, **behind a version, off the live path** | replay over existing store |
| 2 | `execsim.py` v0.8 — market entry, trailing, breakeven, adaptive time stop (§1.6) | `MISSED` count → 0 |
| 3 | **Measure.** Re-run over the full store, compare v0.6 vs v0.7 | win %, ΣR, **same-bar stop-out rate**, confirmation yield, **and the exit change isolated from the entry change** |
| 4 | Gate: proceed only if same-bar stop-outs fall below ~20% and ΣR improves | — |
| 5 | `risk.py` v0.8, `scalein.py` v0.3, `quality.py` states | 164 tests green |
| 6 | Telemetry + diagnostics stages | funnel shows confirmation |
| 7 | UI three tiers + card lines + Market Weather | — |
| 8 | Playbook catalogue + `/api/playbooks` + settings toggles wired | toggling changes output |
| 9 | First-run guide, surface subtitles, glossary | — |

**Step 3 is a real gate, not a formality.** The whole premise is that
confirmation fixes the same-bar stop-out. If the number doesn't move, the
diagnosis was wrong and steps 5–9 should not be built on it.

**Step 3 must be a 2×2, not a single comparison.** Entry and exit both change in
this spec, so a single before/after cannot attribute the result. Replay is cheap
and deterministic — run all four:

| | old exit (hold to SL/TP) | new exit (trail + BE + time stop) |
|---|---|---|
| **old entry** (touch) | v0.6 baseline — known: 13%, −102.8R | isolates the **exit** fix |
| **new entry** (confirmed) | isolates the **entry** fix | the proposed v0.7 |

If the exit change carries the whole improvement, the confirmation rule is
optional complexity and should be dropped. That is a real possible outcome —
median MFE 1.53R against a 6.4R target is a large finding on its own — and the
2×2 is the only way to find out.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Confirmation is too strict → throughput collapses | Confirmation yield is measured in step 3. `CONFIRM_MAX_BARS` and `REJECTION_FRACTION` are the dials |
| Wider stops → smaller size → smaller wins | Intended. Compare on **R**, which is size-independent, not dollars |
| Market entry costs more than limit entry | True; measured. Perp taker is 0.06%. **Revisit before any spot venue** |
| Baseline resets, user thinks results were deleted | Say so explicitly in the UI; nothing is deleted |
| Confluence quietly becomes a filter | `score` is hard-coded 0 in v0.7. Promotion needs a version bump and recorded evidence |
| Playbook cards read as promises | Every card shows its own live record, including bad ones |
