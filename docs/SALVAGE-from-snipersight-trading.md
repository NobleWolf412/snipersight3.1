# Salvage list — what to take from `snipersight-trading`

**Reviewed:** 2026-07-30. Read the backend strategy/confluence/diagnostics/executor
layers and the frontend lessons + HUD components. Not a skim.

**Verdict in one line:** the scoring engine is exactly the trap you named and should
not come across — but the **diagnostics are stronger than anything in snipersight3.1**,
and the **trade-management layer fills a hole this project does not know it has.**

The inversion worth stating plainly: that project built genuinely excellent
instruments to measure a system that didn't work. The instruments are
strategy-agnostic. They are the most valuable thing in the repo, and they are the
part nobody thinks to salvage.

---

## TIER 1 — Take these first. They *are* the grading rig.

I proposed building a strategy-grading harness before writing strategies. Four of
these already exist, working, with the hard-won caveats written into the docstrings.

### 1.1 `diagnostics/factor_contribution.py` — the confluence grader
Measures every confluence factor on five axes:

| Axis | What it catches |
|---|---|
| **Fire rate** | A factor absent 95% of the time carries no weight in practice |
| **Dispersion** | Near-zero std = it says the same thing every time = no discriminating power |
| **Contribution** | How much it actually moves the final score |
| **Redundancy** | **Pairwise Pearson between factors.** \|r\| ≥ 0.70 = overlapping signal |
| **Outcome edge** | Correlation between factor score and realised PnL. **Negative = the factor scores high on losers** |

> *"Effective independent factors << raw count."*

That redundancy axis is the exact multicollinearity problem I described, already
solved, already measured. **This is the highest-value file in the repo.**

Port target: the confluence block specified in `SPEC-confirmed-entry.md` §1.4.
It gives the promotion criterion teeth instead of leaving it as an intention.

### 1.2 `diagnostics/edge_significance.py` — is the edge distinguishable from zero
Bootstrap (20k resamples) of per-trade expectancy → 95% CI and P(expectancy > 0),
computed across several fee scenarios, plus the **breakeven per-side fee** — the fee
at which the edge dies.

Two details worth copying verbatim:
- **Deterministic LCG bootstrap**, no RNG seeding. Reproducible run to run — which is
  the only kind of bootstrap allowed under this project's determinism rule (§4).
- The docstring reasons carefully about whether fees are already netted, and flags
  that unmodelled funding makes swing-heavy numbers an *optimistic ceiling*.

This answers the question snipersight3.1 currently cannot: **is −102.8R over 142
trades bad luck or a real negative edge?**

### 1.3 `diagnostics/edge_by_regime.py` — the confound guard
Slices expectancy by regime × trade_type, and refuses to report naively:

> *"regime is often entangled with the wide-stop-era clamp date... a naive
> edge-by-regime reads 'up_compressed bleeds / down is fine' when the real cause is
> the (fixed) wide stops, NOT the regime."*

Every row shows its pre/post code-change split; a slice entirely on one side is
tagged **CONFOUNDED**. snipersight3.1 has the raw material for this already
(`algo_version` on every fact, baselines) but does not do the check.

### 1.4 `diagnostics/entry_quality_probe.py` — the noise floor
Correlates at-entry features with realised PnL and compares each against the
**n-based noise floor (±1.96/√n)**. A feature only counts if it clears the floor
*and* beats the current best factor.

Born from a real A/B: two indistinguishable setups, same regime, same ~81 score,
opposite outcomes — purely entry location. *"The 26 confluence factors rated them
identically."* That is the entire case for confirmation-gated entry, discovered
independently from the other side.

### 1.5 `diagnostics/fill_rate.py` — settles an open question in the spec
Maker-vs-taker fill rates plus an **adverse-selection probe**: do resting limits fill
only when they're about to lose? And the honest caveat — *"paper OVERSTATES maker
fill rate (fills the instant price touches; no queue position)."*

`SPEC-confirmed-entry.md` §1.3 proposes switching to market-on-next-open partly
because the current limit model **misses 39% of orders**. This tool measures whether
that trade is worth it instead of assuming.

### 1.6 `diagnostics/entry_rr_distortion.py` — planned vs realised R:R
Compares each trade's *planned* R:R against the R:R measured **from the actual fill**.
A large gap means the position opened with inverted geometry.

Directly relevant: snipersight3.1's median planned R:R is 6.4 against a median
favourable excursion of 1.53R. This is the tool that proves whether the plan and the
reality ever agreed.

---

## TIER 2 — Trade management. snipersight3.1 has none of this.

`execsim.py` walks bars to SL or TP and stops. There is no position manager, no
partial exit, no breakeven move, no trailing stop, no time stop, no re-entry control.
That is a real gap, and the old project's answer is good.

### 2.1 Adaptive stagnation — the best single idea in the repo
Not a flat timer. Hold time scales with what the trade actually is:

```
base:     scalp 5h · intraday 14h · swing 48h
× trend:  strong trend 1.5 · trend 1.3 · sideways 0.8
× vol:    compressed 0.7 · normal 1.0 · elevated 1.2
× counter-trend: 0.7   (a LONG in a downtrend gets less patience, not more)
clamp 1h–120h; runners (partially exited) get 2×
```

Plus two guards that show real scar tissue:
- **Minimum P&L threshold before stagnation applies** (scalp 0.2% / intraday 0.5% /
  swing 1.5%) — so a slow winner isn't cut as "stagnant."
- **`STAGNATION_FLOOR_RATIO = 0.7`** — never stagnation-exit a trade already more than
  70% of the way to its stop. Defer to the stop. Expressed as a fraction of *stop
  distance*, not a fixed %, so it self-scales.

This is also the concrete answer to *"scalp, intraday, swing"* — a horizon isn't a
timeframe, it's a **hold-time policy plus an exit policy.**

### 2.2 Cooldown manager — the duplicate-trade answer
Per **symbol + direction**, persisted to disk, with **differentiated durations**:

- **Stop-out cooldown** — long (~24h). The level was invalidated; stop re-buying it.
- **Target/stagnation cooldown** — short (scalp 0.25h / intraday 0.5h / swing 1h),
  with the reasoning attached: *"the level isn't invalidated, just recently resolved."*

That distinction is exactly right and it's the thing most bots get wrong — they
either re-enter instantly after a stop or lock out a level that just paid them.

### 2.3 Partial exits + breakeven + trailing activation
- Multiple targets, partial close at each
- **Move stop to breakeven after target N**
- **Trailing activates at an R multiple** (default 1.5R) and trails a fixed R distance
  (0.5R) behind the running extreme — not a % and not a fixed price

R-denominated trailing is the right unit and matches this project's accounting.

Direct relevance: snipersight3.1's median MFE is **1.53R** with a median target of
**6.4R**. A trailing stop activating at 1.5R would have banked most of that book.
This may be worth more than the entry fix.

### 2.4 `_is_making_progress` — stagnant vs slow
30-minute price sampling over a 12-hour window to distinguish "going nowhere" from
"working slowly toward TP." Prevents the time stop cutting winners.

---

## TIER 3 — Concepts to port, not code

| # | Concept | Why |
|---|---|---|
| 3.1 | **VETO factors** — a hard block that cannot be offset by any other score | The right pattern: some conditions are **gates**, not weights. A high score should never buy its way past a disqualifying condition |
| 3.2 | **HTF composite** — *"5 correlated HTF inputs collapsed to 1 composite weight"* | They hit multicollinearity and fixed it. Confirms the one-factor-per-category rule |
| 3.3 | **Kill zones / sessions** (DST-aware via `zoneinfo`, not hardcoded UTC−5) | Needed the moment equities or forex arrive. The DST bug is already fixed here |
| 3.4 | **Premium/discount** — where price sits in the current range (0–100%) | Cheap, genuinely orthogonal to structure. Buying demand in the lower third ≠ buying it in the upper third |
| 3.5 | **Reversal detector composition** — cycle extreme + CHoCH + volume displacement + sweep; **3-of-4 unlocks a bypass** | The right shape for the TRANSITION gap. Your current REVERSAL demands a sweep *alone* and has fired 5 times ever. Requiring 3 of 4 is both looser and better evidenced |
| 3.6 | **`participation_rate`** — position ≤ 0.5% of 24h volume | Real liquidity constraint. `universe.py` gates the symbol; nothing gates the *position* |

---

## TIER 4 — UI. Take more of this than you'd expect.

### 4.1 The lessons system — the answer to "no one knows how to use this"
`src/content/lessons/` — nine chapters, each with the same skeleton:

> **CORE MECHANIC** → **WHY IT WORKS** → **COMMON MISTAKES** → interactive widget

01 order blocks · 02 FVG · 03 BOS/CHoCH · 04 liquidity sweeps · 05 Wyckoff ·
06 confluence · 07 regime · 08 position sizing · 09 kill zones

And five **interactive SVG widgets**, dependency-free, that teach by manipulation:
`FvgBuilder` (step through construction) · `WickVsCloseDemo` (why a wick isn't a
break) · `SweepVsBreakoutTwin` (same bar, two outcomes, side by side) ·
`KillZoneClock` · `WyckoffSchematic`.

**The "WHY IT WORKS" sections are the differentiator.** They explain the mechanism —
why market makers must return to an FVG, why stops cluster beyond a swing — rather
than asserting a rule. That is what turns a user into someone who can judge a setup
instead of obeying one.

This is a far better answer to the education problem than the first-run guide in
`SPEC-confirmed-entry.md` §5.2, and it should replace it as the ambition.

> **Caveat:** the lesson copy is written to the *old* engine's rules (mode names,
> Grade A/B/C tiers, specific ATR multipliers). Port the **structure, the widgets, and
> the "why it works" framing**; rewrite the specifics against snipersight3.1's actual
> engines, or the docs will lie about the code.

### 4.2 `GauntletBreakdown` — the rejection funnel, done properly
Three-column funnel (**PRE-SCORE / POST-SCORE / EXECUTION**), each stage clickable to
filter, plus a **bottleneck-insight pill** that names the biggest drop-off and links
to the surface that fixes it.

snipersight3.1 shows the rejection funnel as a flat list of counts. This turns it
into navigation. With 88% of rejections at one stage (`NO_ELIGIBLE_PLAYBOOK`), a
bottleneck pill would have surfaced that on day one.

### 4.3 `PipelineTracer` — per-setup drawer
Flattened ~11-stage horizontal flowchart **for a single signal**, each stage showing
pass/fail *and the actual value* (score, threshold, R:R, regime), expandable to
substages.

The funnel answers *"why is nothing firing?"* This answers *"why didn't **this one**
fire?"* — and that's the question a user actually asks.

Note the discipline: when the trace has been evicted from the ring buffer it renders
an explicit amber state rather than degrading silently. Same loud-fallback rule this
project already follows.

### 4.4 `DiagnoseWizard` — 9-step guided troubleshooting
A modal walking numbered checks — *venue healthy? universe non-empty? cycles running?
where are signals dying?* — each rendering ✓/✗ inline with a **CTA to the surface that
fixes it**. Orchestrates existing endpoints; no new backend.

This is what the Diagnostics surface should be for a non-expert. Today that page
reports state; this one tells you what to *do* about it.

---

## DO NOT TAKE

| | Why |
|---|---|
| `strategy/confluence/scorer.py` (**5,985 lines, 26 factors**) | The trap, exactly as you called it. Its own `factor_contribution.py` exists because the file could not be reasoned about |
| **Synergy bonuses / conflict penalties** | Free-parameter farm. Bonuses that offset penalties, with per-mode caps on the offset, means the score can be tuned to any answer. A comment even notes bonuses "inflating past the confluence threshold via unearned synergy points" |
| **Scanner modes** (SURGICAL / OVERWATCH / STRIKE / STEALTH) | Four sets of thresholds = 4× the overfit surface and 4× the sample fragmentation. Pick one rule set and grade it |
| **ML gate + SHAP importance** | At n≈900 with 26 correlated features this fits noise. Revisit at n in the thousands, never before |
| **Grade A/B/C tiers with per-mode multipliers** | Tiering on a threshold that itself varies by mode is two free parameters wearing one name |

---

## Recommended additions to `SPEC-confirmed-entry.md`

1. **§1.4 confluence** — adopt `factor_contribution.py`'s five axes as the literal
   promotion criterion, redundancy included. Promotion currently says "must earn it"
   without saying how it's judged.
2. **New §1.7 — trade management.** Trailing activation at 1.5R and adaptive
   stagnation should be in *this* change, not a later one. Median MFE 1.53R against a
   6.4R median target says the exit is at least as broken as the entry, and a
   confirmed entry with an unchanged exit only fixes half the problem.
3. **New §1.8 — cooldowns.** Stop-out vs target-exit durations, per symbol+direction.
   Currently nothing prevents re-entering a level that just stopped you out.
4. **§3 diagnostics** — port `edge_significance` first. Before building strategies,
   settle whether the current −102.8R is a real negative edge or noise.
5. **§5 explanatory layer** — replace the four-step first-run guide with the lessons
   structure (mechanic / why it works / mistakes / widget), rewritten against this
   project's real engines.
6. **§4 UI** — add the bottleneck pill to the rejection funnel, and the per-setup
   trace drawer.

---

## The one-line summary

Take the **measuring instruments**, the **trade-management layer**, and the
**teaching layer**. Leave the **scoring engine** and everything that tunes it.

The old project's real lesson isn't in its code — it's that it *knew* it wasn't
working and built the tools to prove it. Those tools belong in a project whose
strategy might actually be worth measuring.
