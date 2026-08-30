# SniperSight 3.1 — Program Plan

**Rewritten:** 2026-07-31, against the code and the fact store rather than against
the previous draft. Supersedes the sequencing sections of `REDESIGN-PLAN.md`,
`PRODUCT-REVIEW-2026-07-29.md`, `SPEC-confirmed-entry.md` and
`SALVAGE-from-snipersight-trading.md` — those remain authoritative for their own
detail; this is the order, the ownership, and now the status.

Every status below was verified by query, not by recollection. Where a claim is
inferred rather than measured it says so.

**This is a dated snapshot, and it is meant to read as one.** Statuses, counts
and measurements below were true on the date beside them and are not
re-verified on edit — the test count in §2 was already half of what the suite
reports by 08-07. The rules that do *not* expire moved to `CLAUDE.md` (see §6);
what is left here is planning, which is allowed to age.

---

## 1. The numbering, because there were two of them

This project has been planned twice under two schemes, and they collided:

- **`REDESIGN-PLAN.md` §6 — Phases 1–6.** A UI/product build sequence written
  2026-07-28. Phase 4 is *Perps*.
- **`PROGRAM-PLAN.md` — Waves 0–4.** An evidence-led engine sequence written
  2026-07-30. Wave 4 is *expansion (venues, auto, assets)*.

Both numbered a venue milestone "4" while meaning different things, and the UI
still cites phase numbers. The cost was real: the venue switcher in `shell.js`
told the operator *"Phemex adapter lands in phase 4"* while the scanner was
trading 19 Phemex perps and nothing else, because the phase number it quoted
belonged to a plan the newer document had renumbered.

**From here, WAVES are the only forward scheme.** Phases are historical and are
recorded below so old references resolve. New work is never given a phase number.

| Phase (historical) | Contents | Status |
|---|---|---|
| 1. Foundation | design system, app shell, 5-surface nav, glossary | **done** |
| 2. COMMAND + CHART | setup deck, chart with draggable levels, order ticket | **done** |
| 3. Settings + venue seam | scanner setup, credential vault, venue interface | **done** |
| 4. Perps | Phemex adapter, shorts, leverage, liquidation + gate, funding | **done** — engine closed in S45; the operator-facing half (leverage dial, liquidation readout) landed 2026-07-31 |
| 5. AUTO + guardrails | arm/disarm, drawdown + data-health + timer halts | **partial** — guardrails exist and are wired; AUTO is deliberately locked |
| 6. Diagnostics + Results | unified debug surface, dual scoreboards | **done** |
| Locked | live submission | **locked, no longer empty** — the execution outbox and a signed Phemex adapter exist and serve the TESTNET path; mainnet routing is build-locked (`automation.LIVE_ROUTER_BUILD_ENABLED = False`, `broker_factory` raises) |

---

## 2. Where 3.1 actually stands (verified 2026-07-31)

**Assets:**
- Append-only versioned fact store, **1.85M facts**, content-hash idempotent
- `confirmed_at` / `market_time` split — the backtest cannot cheat
- Venue abstraction across **three** venues (Coinbase spot, Phemex perp, Kraken
  perp) with funding, ISOLATED liquidation and a stop-safety gate
- Portfolio-scoped risk authority, kill switch, point-in-time universe
- Version lockfile (`test_version_cascade.py`) — caught three cascades in one
  session and is the reason each was deliberate
- Five surfaces, Learn/lessons, playbook catalogue, weather strip, rejection
  funnel, per-setup trace, diagnose wizard
- **646 python + 56 js tests**

**The liability that matters, and it is the only one that still does:**

| # | Liability | Evidence |
|---|---|---|
| L1 | **No strategy clears zero** | REVERSAL n=277, **+0.1523 R, CI [−0.070, +0.372]**; all strategies n=411, +0.0648 R, CI [−0.108, +0.247] |

L2–L9 from the previous draft are closed. Entry geometry (L2) and exit
management (L3) were rebuilt in Wave 1; duplicate/re-entry control (L4) shipped
as `cooldowns`; the discarded-opportunity bucket (L5) was measured and turned out
to be **largely a tick-floor bug** rather than absent playbooks (S40 — RANGE
rejections fell 877 → 176 on the same 20 symbols once the break tolerance stopped
being blind below a dollar); strategy toggles (L6) are read; `/legacy` (L7) is
retired; the forward record (L8) exists; onboarding (L9) shipped as Wave 3.

---

## 3. The gate: it ran, and the answer was not the hoped-for one

The previous draft made everything expansionary conditional on a 2×2 replay that
would attribute the fix between entry and exit. **That replay was built
(`engine/abtest.py`) and it ran.** Entry and exit were both rebuilt.

Then S50 found that the simulator had been inventing fills. The
`MAKER_THEN_MARKET` crossing leg booked a market fill at the *plan's* price —
two bars stale — and 78 of 95 crossed orders filled at a price outside their own
bar's `[low, high]`, never adversely. One ETHUSDT long was booked at 2075.49 on a
bar whose low was 2094.69. It bought below the bar.

Re-simulated honestly:

| | as shipped | honest fills |
|---|---|---|
| whole book | +95.85 R / 642 | **+31.95 R** |
| **REVERSAL (traded)** | +0.266 R, CI **[+0.038, +0.498]** | **+0.152 R, CI [−0.070, +0.372]** |
| PULLBACK (traded) | −0.139 R | −0.228 R |

**Two thirds of the book's apparent edge was the simulator handing out free
entries**, and REVERSAL — the one result this project had been reporting as real
— stopped clearing zero.

So the gate's four outcomes resolve to a fifth the original table did not
contemplate: *the measurement apparatus was wrong, and the result it produced was
not a result.* The apparatus is now correct. The remaining +0.15 R on REVERSAL is
**something to test forward, not something to trust.**

**What that means for order:** the previous draft said everything expansionary is
downstream of answering "is the edge real". It is answered — *not yet, on this
evidence* — so Wave 2 strategy plurality is **not unlocked**, and building more
strategies on this foundation would be exactly the waste the gate exists to
prevent. The correct next move is forward evidence on a correct simulator, not
more strategies.

---

## 4. Waves, with real status

### Wave 0 — measure & unblock · **DONE**

| # | Deliverable | Status |
|---|---|---|
| 0.1 | `edgestats.py` — bootstrap CI, P(edge>0), breakeven fee | done |
| 0.2 | `factorstats.py` — fire rate, dispersion, pairwise redundancy, noise floor | done |
| 0.3 | Resolve `/legacy` | retired 2026-07-29 |
| 0.4 | Restart the scanner | done (and the crash loop behind it root-caused — a toast was killing it 191 times) |
| 0.5 | Regime slicing with **confound guard** | done — `edgestats.confound_report` |
| 0.6 | `entrystats.py` — fill rate, adverse selection, planned-vs-realised R:R | done |

### Wave 1 — fix execution · **DONE**

`setup-v0.13`, `exec-v0.17`, `risk-v0.16`, `scale-v0.11`, `cooldown-v0.5`. The
plan targeted v0.7/v0.8; the cascade has moved well past it, each step forced by
the lockfile rather than discovered later.

### GATE · **answered — see §3. Wave 2 is NOT unlocked.**

### Wave 2 — strategy plurality · **deliberately incomplete**

| # | Deliverable | Status |
|---|---|---|
| 2.1 | Strategy registry | `registry.py` exists and is **deliberately thin** — PULLBACK and REVERSAL share every mechanic, so a bracket-owning interface would hold two identical brackets |
| 2.2 | Fix the TRANSITION gate | open |
| 2.3 | Range fade | **CLOSED BY EVIDENCE** — of the RANGE-regime rejections, 3 had a live detected range; zero on structure-sound symbols. `ranges.py` is kept as the measurement that proves it |
| 2.4 | Indicator engines | `ma`, `momentum`, `volatility`, `volume` done; **`sessions` not built** |
| 2.5 | Breakout–retest, compression, sweep-reversal | `breakout` built, graded (n=55, −0.076 R, CI [−0.545, +0.426]) and **MEASURED AND NOT ENABLED**; the rest open |
| 2.6 | Grade every one before it ships | holding — 2.3 and 2.5 were both refused on their own evidence |

### Wave 3 — understandability · **DONE**

All six surfaces shipped: lessons, playbook catalogue, weather strip, bottleneck
pill, per-setup trace drawer, diagnose wizard — plus `edgeview`.

### Wave 4 — expansion · **partly shipped ahead of its own gate**

Kraken perps adopted and carried as a **shadow venue** (warmed, measured, never
traded). Phemex live. That is further than the entry condition permits, and it is
recorded here rather than quietly enjoyed: the condition was *a forward paper
record with real sample size and an explicit unlock*, and §3 says we do not have
one.

Still unbuilt: position manager, shadow mode as a mandatory live step, Alpaca
equities, AUTO mode, options/futures.

---

## 5. What is actually left

In the order the evidence argues for:

1. **Forward record on a correct simulator.** Everything else is downstream. The
   book was re-derived after S50; what it needs now is time, not features.
2. **`sessions.py`** (Wave 2.4) — the only unbuilt indicator engine.
3. **TRANSITION gate** (Wave 2.2) — the largest remaining rejection bucket now
   that RANGE has been explained.
4. **Doc reconciliation** — this file. The stale set it used to list was
   reconciled 2026-08-07; `docs/README.md` now carries the index.
5. **Order router**, if and only if the forward record earns it. It does not
   exist today, and `live_enabled` is a hard-coded literal, which is correct.

---

## 6. Parallelisation — what agents can and cannot do here

**Can be parallel** (disjoint files, no shared version constants): Wave 0 items ·
all of Wave 3 · Wave 2.4 indicator engines.

**Must be sequential and single-owner:** anything touching
`setups`/`execsim`/`risk`/`scalein` together — they import each other's VERSION
constants and must bump together or the pipeline reads one generation's facts
under another's assumptions. The lockfile now fails the suite when that is
attempted, which converts a silent corruption into a test failure.

**Convention risk — the real hazard.** This codebase has unusually strong,
*unstated-in-code* conventions. Any agent working here must be given them
explicitly or it will produce code that passes tests and violates the
constitution.

**The list moved to `CLAUDE.md` on 2026-08-07** — see "The conventions" there.
Comments in the code citing `§6` mean that list. It moved because this document
is a dated status snapshot and the conventions are not: binding them together
let a reader discount the rules along with the stale wave statuses, and
`CLAUDE.md` is the file that is always loaded. Two of the ten were corrected in
the move — Decimal is enforced by the store's text representation rather than
by a test, and "one authority per number" has a single deliberate, tested
exception in `ticket-math.js`.

Nothing else about parallelisation changes: the sequencing rules above are what
this section is for.

---

## 7. Documents

`docs/README.md` is the index: what each document is, and whether it is
current. It replaced the staleness table that used to sit here.

That table is worth one sentence of postmortem, because it failed in the way
this whole document can fail. It flagged `HARDENING.md` and `README.md` as
stale and wrong; both were repaired within days and the rows stayed wrong for a
week. **A staleness audit that goes stale is worse than no audit** — it is
read as current by definition. Trust the header of the file itself, which each
document carries, over any table describing it.

## 8. What "done" looks like

Unchanged in spirit, re-answered in fact:

1. **Wave 0 done — ✅ answered.** We know what the book is worth: nothing yet
   clears zero, and two thirds of what it appeared to be worth was a simulator
   defect.
2. **Gate passed — ❌ not passed.** The 2×2 ran and the apparatus was found
   faulty; the honest re-measurement leaves REVERSAL at +0.15 R with a CI through
   zero. This is a *forward* question now.
3. **Wave 2 done — not started, correctly.** Three or more independently graded
   strategies, each showing its own record including the losses. Two candidates
   have already been refused on evidence, which is the process working.

Only then does live execution become a conversation.
