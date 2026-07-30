# SniperSight 3.1 — Program Plan

**Written:** 2026-07-30. Supersedes the sequencing sections of `REDESIGN-PLAN.md`,
`PRODUCT-REVIEW-2026-07-29.md`, `SPEC-confirmed-entry.md` and
`SALVAGE-from-snipersight-trading.md` — those remain authoritative for their own
detail; this is the order and the ownership.

---

## 1. Where 3.1 actually stands

**Assets — genuinely strong, better than most funded products:**
- Append-only versioned fact store, 914k facts, content-hash idempotent
- `confirmed_at` / `market_time` split — the backtest cannot cheat
- Venue abstraction with liquidation and funding modelled; perps live, 20 symbols
- Portfolio-scoped risk authority with kill switch and point-in-time universe
- Fail-closed quality audit; per-stage heartbeat; telemetry and diagnostics scaffolding
- Five-surface UI (phase 1), glossary over 40 terms
- Notification discipline fixed today (S35)

**Liabilities — every one of them measured, not asserted:**

| # | Liability | Evidence |
|---|---|---|
| L1 | The one strategy loses money | `exec-v0.7`: 142 trades, 13% win, **−102.8R** |
| L2 | Entry geometry is self-defeating | **59% of stops hit on the fill bar** (73/124) |
| L3 | **No exit management whatsoever** | median MFE **1.53R** vs median target **6.4R** |
| L4 | No duplicate/re-entry control | nothing stops re-buying a level that just stopped you |
| L5 | Two-thirds of opportunity discarded | 7,149 `NO_ELIGIBLE_PLAYBOOK` (41% TRANSITION, 27% RANGE) |
| L6 | Strategy toggles are inert | `settings.py` defines them; `setups.py` never reads them |
| L7 | Broken test baseline | `static/index.html` deleted but still served at `/legacy` — 9 tests red |
| L8 | Forward record is empty | baseline reset 2026-07-29; 0 risk decisions |
| L9 | Nobody can use it | no onboarding, no playbook catalogue, no "why is it quiet" |

**The honest read:** this is a strong engine with **no proven edge and no exit
logic.** L2 and L3 are execution defects, not strategy defects — which means L1 is
currently unfalsifiable. We do not know whether the idea is bad or whether it has
never been given a fair test.

**That single sentence sets the whole order below.** Everything expansionary
(strategies, asset classes, auto-trade, brokers) is downstream of answering it, and
building any of it first means building on an unmeasured foundation.

---

## 2. The order, and why

```
  WAVE 0 ── measure & unblock ──────────────► can run NOW, gate-free
  WAVE 1 ── fix execution (entry + exit) ───► the crux. Sequential. Coupled.
  ════════ GATE: the 2×2. Human decision. ═══════════════════════════
  WAVE 2 ── strategy plurality ─────────────► only if the gate passes
  WAVE 3 ── understandability ──────────────► parallel throughout, ungated
  WAVE 4 ── expansion (venues, auto, assets)► only after a proven forward record
```

### Why the gate is real

`SPEC-confirmed-entry.md` §6 changes entry **and** exit at once. A single
before/after cannot attribute the result, so the gate is a **2×2 replay**:

| | hold to SL/TP | trail + BE + time stop |
|---|---|---|
| **entry on touch** | v0.6 baseline: 13%, −102.8R | isolates the **exit** fix |
| **entry on confirmation** | isolates the **entry** fix | proposed v0.7 |

Four outcomes, four different programs:

| Result | What it means | What we do |
|---|---|---|
| Both help | Diagnosis correct | Proceed to Wave 2 as planned |
| **Only the exit helps** | The confirmation rule is optional complexity | **Drop it.** Ship exits, re-measure, revisit entry later |
| Only the entry helps | Exits are neutral here | Keep both anyway — exits reduce variance |
| Neither helps | The pullback premise is wrong | **Stop.** Do not build 4 more strategies on it. Re-open the diagnosis |

Row 2 is a live possibility — median MFE 1.53R against a 6.4R target is a large
finding on its own. Row 4 is the one that must not be quietly skipped.

---

## 3. Wave 0 — measure & unblock (now, gate-free)

| # | Deliverable | Depends on | Parallel? |
|---|---|---|---|
| 0.1 | **`engine/edgestats.py`** — port `edge_significance`: deterministic-LCG bootstrap CI on expectancy, P(edge>0), breakeven per-side fee, across fee scenarios. Run on the existing 928-trade book | nothing | ✅ isolated |
| 0.2 | **`engine/factorstats.py`** — port `factor_contribution`: fire rate / dispersion / contribution / **pairwise-Pearson redundancy** / outcome-edge vs `±1.96/√n` noise floor | nothing | ✅ isolated |
| 0.3 | **Resolve `/legacy`** — `index.html` is staged-deleted but still routed. Either restore or remove route + tests | nothing | ✅ isolated |
| 0.4 | **Restart the scanner** — pid running pre-S35 code | nothing | manual |

**0.1 is the single most important thing in this document.** It answers whether
−102.8R over 142 trades is a real negative edge or noise. Every downstream decision
is conditioned on that answer and nobody currently knows it.

---

## 4. Wave 1 — fix execution (the crux, sequential)

Per `SPEC-confirmed-entry.md` §1. **Not parallelisable**: `setups`, `execsim`,
`risk` and `scalein` all import `SETUP_VERSION` from each other and must bump
together, or the pipeline silently reads v0.7 facts under v0.6 assumptions.

| # | Deliverable |
|---|---|
| 1.1 | `setups.py` → **v0.7**: `CONFIRMING` state, confirmation predicate, structural stop, capped target, confluence block (recorded, `score=0`), read `settings.strategy_*` (fixes **L6**) |
| 1.2 | `execsim.py` → **v0.8**: market-on-next-open, trailing 1.5R/0.5R, breakeven at 1R, adaptive time stop, `STAGNATION_FLOOR_RATIO` (fixes **L3**) |
| 1.3 | `cooldowns` — asymmetric stop-out vs resolved, per symbol+direction, emitted as facts (fixes **L4**) |
| 1.4 | `risk.py` v0.8, `scalein.py` v0.3, `quality.py` state awareness |
| 1.5 | **The 2×2 replay** and its report |

**One owner, sequential.** Splitting this across agents produces four files that
each compile and together do not agree.

---

## 5. Wave 2 — strategy plurality (gated)

Only if the gate passes.

| # | Deliverable | Addresses |
|---|---|---|
| 2.1 | **Strategy registry** — each strategy owns bracket, confirmation rule, horizon, timeframes, asset classes | L5, L6 |
| 2.2 | **Fix the TRANSITION gate** — replace "sweep within 10 bars" (98 sweeps exist in the whole store; REVERSAL has fired 5 times) with 3-of-4 composition per `SALVAGE` §3.5 | **41% of L5** |
| 2.3 | **Range fade** — RANGE regime, buy demand at range low / sell supply at range high | **27% of L5** |
| 2.4 | Indicator fact engines — `ma`, `momentum`, `volatility`, `volume`, `sessions` | unlocks 2.5 |
| 2.5 | Breakout–retest, compression→expansion, sweep-reversal scalp | remaining L5 |
| 2.6 | **Grade every one** through 0.1/0.2 before it ships. One factor per information category | prevents repeating the old project |

---

## 6. Wave 3 — understandability (ungated, parallel throughout)

This wave is **independent of which strategy wins.** What a zone, a regime or a
break *is* does not change based on the 2×2. It can and should run alongside
Waves 0–2.

| # | Deliverable | Addresses |
|---|---|---|
| 3.1 | **Lessons system** — port the structure from `SALVAGE` §4.1: *core mechanic → why it works → common mistakes → interactive widget*. Rewrite all specifics against 3.1's real engines | L9 |
| 3.2 | **Playbook catalogue** — one card per strategy, same five labels, **live record including losses**, wired to the `settings` toggles | L9, L6 |
| 3.3 | **Market Weather strip** — regime × timeframe with a plain-English "what this means", so silence explains itself | L9 |
| 3.4 | **Bottleneck pill** on the rejection funnel — names the biggest drop-off, links to the fix | L9 |
| 3.5 | **Per-setup trace drawer** — "why didn't *this one* fire" | L9 |
| 3.6 | **Diagnose wizard** — numbered checks, ✓/✗, CTA per failure | L9 |

---

## 7. Wave 4 — expansion (only after a proven forward record)

Kraken perps (removes the Phemex US-legality risk) → position manager + shadow mode
→ Alpaca equities → auto mode + per-strategy circuit breakers → Schwab + options
expression layer → futures/forex. Detail in `PRODUCT-REVIEW-2026-07-29.md` §4.

**Entry condition:** a forward paper record with real sample size, quality gate
green, and an explicit unlock. Not enthusiasm.

---

## 8. Parallelisation — what agents can and cannot do here

**Can be parallel** (disjoint file sets, no shared version constants):
Wave 0 items · all of Wave 3 · Wave 2.4 indicator engines

**Must be sequential and single-owner:**
Wave 1 in full · Wave 2.1–2.3 (they land inside the registry)

**Must not start yet:**
Everything gated on the 2×2. Building UI, strategies or venue adapters for a
strategy that may be discarded is the specific waste the gate exists to prevent.

**Convention risk — the real hazard.** This codebase has unusually strong,
*unstated-in-code* conventions. Any agent working here must be given them
explicitly or it will produce code that passes tests and violates the constitution:

1. Facts are append-only, content-hash idempotent, and carry an `algo_version`
2. A rule change means a **new version**, never an edit to an old one
3. `confirmed_at` ≠ `market_time`; nothing may act on a fact before it was knowable
4. Closed candles only — never a developing bar
5. Decimal end to end; no float touches a price
6. **Loud-fallback rule**: a degraded path must never degrade silently
7. **Evidence is recorded, not filtered on**, until it has been graded
8. Comments explain **why**, with the measurement that motivated them
9. Rejections are as auditable as approvals
10. One authority per number — the UI reads it, never re-derives it

---

## 9. Salvage coverage audit

Every item in `SALVAGE-from-snipersight-trading.md`, and where it lands. Audited
2026-07-30 because "is everything covered?" deserved a table, not an assurance.

| Item | Status | Owner |
|---|---|---|
| 1.1 `factor_contribution` — five-axis factor grader | ✅ | Wave 0.2 |
| 1.2 `edge_significance` — bootstrap CI | ✅ | Wave 0.1 |
| 1.3 `edge_by_regime` — **confound guard** | ⚠️ **added** | Wave 0.5 |
| 1.4 `entry_quality_probe` — noise floor | ◐ partial | floor in 0.2; location probe → 0.6 |
| 1.5 `fill_rate` — maker fill + adverse selection | ⚠️ **added** | Wave 0.6 |
| 1.6 `entry_rr_distortion` — planned vs realised R:R | ⚠️ **added** | Wave 0.6 |
| 2.1 Adaptive stagnation | ✅ | spec §1.6c |
| 2.2 Cooldowns (asymmetric) | ✅ | spec §1.7 |
| 2.3 **Partial exits** + BE + trailing | ⚠️ **partials were missing** | spec §1.6a — added |
| 2.4 `_is_making_progress` | ✅ | spec §1.6c |
| 3.1 **VETO pattern** — gates ≠ weights | ⚠️ **added** | Wave 2.1 |
| 3.2 HTF composite | ◐ partial | redundancy axis in 0.2; composite → Wave 2.1 |
| 3.3 Kill zones / sessions | ✅ | Wave 2.4 |
| 3.4 **Premium/discount** | ⚠️ **added** | Wave 2.4 |
| 3.5 Reversal 3-of-4 composition | ✅ | Wave 2.2 |
| 3.6 **`participation_rate`** — position ≤ 0.5% of 24h vol | ⚠️ **added** | Wave 2.1 |
| 4.1 Lessons system | ✅ | Wave 3.1 |
| 4.2 Bottleneck pill | ✅ | Wave 3.4 |
| 4.3 Per-setup trace drawer | ✅ | Wave 3.5 |
| 4.4 Diagnose wizard | ✅ | Wave 3.6 |

**Result of the audit: 12 covered, 3 partial, 5 were unassigned.** Now placed:

### New Wave 0 items
- **0.5 — regime slicing with confound guard.** Extends `edgestats.py`: expectancy
  by regime × horizon, with every slice tagged by which `algo_version` produced it.
  A slice sitting entirely on one side of a version change is **CONFOUNDED** and
  must be labelled, not reported. This project has the raw material (`algo_version`
  on every fact, baselines) and does not currently do the check.
- **0.6 — `entrystats.py`**: fill rate + adverse selection + planned-vs-realised
  R:R + entry-location probe. **Load-bearing for the gate**: spec §1.3 switches to
  market-on-next-open partly because the limit model misses 39% of orders. If those
  misses were adversely selected — limits filling only when about to lose — market
  entry is strictly better and the change is justified. If the misses were winners,
  it is justified differently. Right now it is justified by assumption.

### New Wave 2.1 items (fold into the strategy registry)
- **VETO pattern** — some conditions are gates, not weights. A high confluence
  score must never buy its way past a disqualifying condition. Structural, and it
  belongs in the registry contract rather than in any one strategy.
- **`participation_rate`** — reject a position exceeding ~0.5% of 24h volume.
  `universe.py` gates which *symbols* are liquid enough; nothing gates whether a
  given *position* is too large for the book it must fill in.
- **HTF composite** — correlated higher-timeframe inputs collapse to one weight.

### New Wave 2.4
- **Premium/discount** — where price sits in the current range (0–100%). Cheap,
  and genuinely orthogonal to structure: buying demand in the lower third of a
  range is a different trade from buying it in the upper third.

---

## 10. What "done" looks like

Not "the features are built." Three checkpoints, in order:

1. **Wave 0 done:** we know whether the current book is a real negative edge.
2. **Gate passed:** same-bar stop-outs below ~20%, ΣR improved, and we know whether
   entry, exit, or both did it.
3. **Wave 2 done:** three or more strategies, each independently graded, each
   showing its own record on its own card — including the ones that lost.

Only then does live execution become a conversation.
