---
name: SniperSight3 v0.1 Constitution & Spec — Audit Report
description: Auditor's independent review of SniperSight3_Product_Constitution_and_v0_System_Specification.docx v0.1. Verdict, findings by severity, appendices for Phases B/D/E/G/H, and ordered pre-implementation remediation list.
type: reference
---

# SniperSight3 v0.1 — Audit Report

**Source doc:** `SniperSight3_Product_Constitution_and_v0_System_Specification.docx` v0.1
**Auditor:** Auditor persona, 2026-07-17
**Scope:** Specification quality only. Trading methodology (swings, zones, regime taxonomy) taken as given per §1 of the audit protocol.
**Process:** Phases A–J of `audit-process-constitution-v0.1.md`.

---

## 1. Executive Verdict

**Not buildable as written. NO-GO on starting v0 implementation.**

The document is a *good constitution* and a *thin spec*. The constitution (§1–§16) is coherent, principled, and mostly implementable. The v0 spec (§17–§31) is not: it names ten functional modules whose behavior depends on rules the doc explicitly defers to §30 ("Completion Gate Before Strategy Development"). §30 is a list of ten items the doc itself flags as unresolved — swing confirmation, structural-tier hierarchy, protected-level logic, BOS/CHoCH selection, wick-vs-close, break tolerance, zone flip, retest, HTF influence, and provisional-vs-tradable classification. Every one of these is a hard prerequisite for the swing engine, structure engine, zone engine, and fact inspector listed in §19. Two engineers handed this spec today will produce two incompatible engines by lunch.

**Top three blockers (all forcing incompatible choices at day 1):**

1. **§30 items are v0 dependencies, not v0 sequels.** §30 says these must be resolved *before strategy development*, but §29 acceptance criteria (deterministic structural facts, accurate swing confirmation times, complete zone lifecycle, inspectable BOS/CHoCH) cannot be met without them. The spec effectively depends on its own postscript.
2. **No numeric/temporal reproducibility policy.** ATR period, floating-point library, rounding, timezone / candle-boundary origin, tie-breaking on identical timestamps, and ordering across timeframes are all UNSPECIFIED. §4 asserts determinism as a principle; no mechanism is named. Same code, same CSV, different machines → different structural facts.
3. **No fact / layer-boundary schema.** §3 defines five layers and forbids skipping them, but no object schema, invariants, or persistence format is given for anything crossing a boundary. §8's ten auditability questions therefore have no storage target.

**Recommended next step:** the Architect resolves §30 as a first-class specification annex before any Layer-2 code is written. Estimated 2–3 weeks. Details in §4 below.

---

## 2. Findings (sorted by Severity, then Section)

### BLOCKERS

**FINDING-001**
Section: §30 vs §19, §29
Severity: BLOCKER
Category: Scope, Testability
Observation: §30 lists ten rules the doc admits are unresolved ("swing confirmation, structural-tier hierarchy, protected-high/low, BOS/CHoCH level selection, wick vs close, break tolerance, zone break/flip, retest, HTF influence, provisional-vs-tradable") and gates them *before strategy development*. But §19 requires implementing the swing, structure, and zone engines in v0, and §29 acceptance criteria 3, 4, 5, 6 require correctness of those engines.
Impact: v0 cannot be built without the §30 rules; §30 is not slated to be resolved before v0. Two engineers will pick incompatible rule sets and both will pass §29 by accident on their own charts.
Remedy: Move §30 upstream. Treat §30 as v0's real specification annex. Either resolve every §30 item in a numbered subsection before implementation, or scope §29(3–6) out of v0.

**FINDING-002**
Section: §4, §22, §24, §20
Severity: BLOCKER
Category: Determinism
Observation: ATR is referenced as the unit for three named thresholds (§20 local swing 0.75 ATR, §22 break tolerance 0.05 ATR, §24 equal-highs tolerance 0.10 ATR) but the ATR period, smoothing method (Wilder RMA vs SMA vs EMA), and per-timeframe ATR source are UNSPECIFIED.
Impact: Every derived fact that uses these thresholds is non-reproducible across implementations. §4's determinism principle is unenforceable.
Remedy: Add a subsection to §20 specifying ATR(period, smoothing, per-timeframe source, warmup handling, missing-data behavior) as a single canonical function.

**FINDING-003**
Section: §4, §5
Severity: BLOCKER
Category: Determinism
Observation: No numeric-library policy (float64 vs Decimal), rounding rule, or tie-breaking rule when two facts share a timestamp. Ordering of facts across timeframes when they resolve on the same wall-clock instant is not specified.
Impact: Same input, different runtimes → different swing confirmation and different structural facts. Directly contradicts §4.
Remedy: Name the arithmetic library, precision, rounding mode, and a total ordering (e.g. (timestamp, timeframe rank, sequence within timeframe)) for all Layer-2 fact emission.

**FINDING-004**
Section: §3, §8
Severity: BLOCKER
Category: Interface
Observation: The five layers and the ten auditability questions are stated but no schema is provided for any object crossing a layer boundary — no candle schema, no derived-fact schema, no trade-intent schema, no persistence format.
Impact: §8 reconstruction is undefined. §7 versioning has nothing to attach a version to. Engineers cannot implement the fact inspector (§19) without a fact schema.
Remedy: Add a "Layer Boundary Schemas" section defining the minimum required fields, invariants, and version tag placement for one object per boundary. Reference implementation later; schema first.

**FINDING-005**
Section: §6
Severity: BLOCKER
Category: Lifecycle
Observation: Six fact states are named (DEVELOPING, PROVISIONAL, CONFIRMED, INVALIDATED, EXPIRED, SUPERSEDED) with zero transition rules and no entity-by-entity applicability. It is unclear which states apply to candles, swings, zones, liquidity levels, or regime — and which transitions are legal.
Impact: The replay engine (§19) and fact inspector cannot be implemented consistently. §5's "labeled provisional" instruction has no target state machine.
Remedy: For each stateful entity (candle, swing, zone, liquidity level, regime), publish a state-transition table with entry condition, exit condition, and terminal state.

**FINDING-006**
Section: §5, §18
Severity: BLOCKER
Category: Determinism
Observation: Timezone / candle-boundary origin is UNSPECIFIED. §18 lists 1W, 1D, 4H, 1H, 15m timeframes. Weekly and daily candle boundaries differ materially across UTC, exchange-local, and Monday-vs-Sunday-anchored week conventions.
Impact: "Deterministic re-import" (§19) and "Canonical higher-timeframe candles with exchange-aware boundaries" (§19) have no single answer. Different weekly aggregations produce different major swings.
Remedy: Fix the venue's declared boundary (crypto venues typically publish UTC-anchored kline boundaries; state which venue, cite the venue rule, and pin week start).

### MAJOR

**FINDING-007**
Section: §23
Severity: MAJOR
Category: Lifecycle
Observation: Zone lifecycle enumerates FRESH, TOUCHED, TESTED, WEAKENED, BROKEN, FLIPPED, INVALIDATED with no criterion distinguishing TOUCHED from TESTED, no rule for when TESTED becomes WEAKENED, and no BROKEN → FLIPPED entry condition. §30 punts on this.
Impact: Zone engine (§19) has no ground truth; §29(6) "complete zone lifecycle" is untestable.
Remedy: Add a per-transition rule table with observable trigger conditions.

**FINDING-008**
Section: §22, §20
Severity: MAJOR
Category: Terminology, Determinism
Observation: "Meaningful displacement," "significant directional leg," "small tick buffer," "follow-through," "reclaim behavior," "relative volume," and "close location" appear in structural-break and swing rules without quantitative definition.
Impact: Structural swing and BOS confirmation are subjective. §29(3, 4) fail.
Remedy: Either define each as a numeric predicate or remove them from the rule and demote to "evidence recorded for future filter research."

**FINDING-009**
Section: §12, §3
Severity: MAJOR
Category: Interface
Observation: ML output is described as "rank valid setups" and "estimate outcome probabilities" (§12) but the layer at which ML output lives is not stated. If rank is a Layer-2 fact, it becomes an input to strategies; if Layer-3, it competes with strategy hypotheses.
Impact: The determinism regime for ML output is ambiguous. §4's seed/data-version discipline applies only if ML output is a Layer-2 fact.
Remedy: Declare ML rank/probability as a Layer-2 fact with a versioned model tag, or as a Layer-3 annotation; either way pick and document.

**FINDING-010**
Section: §9
Severity: MAJOR
Category: Interface
Observation: Risk authority is stated as independent from strategy but the approve / reduce / reject message format, latency budget, and mid-intent modification rules are UNSPECIFIED. Reducing an intent requires a well-defined mutation — quantity? risk? both? — which is not given.
Impact: Layer 4 → Layer 5 boundary is undefined even for the paper-trading path implicit in v0's downstream work.
Remedy: Publish the risk-authority response schema (verdict enum, modified quantity, modified stop, rejection reason code) with an example.

**FINDING-011**
Section: §7
Severity: MAJOR
Category: Versioning, Governance
Observation: "A version becomes immutable once used in a recorded backtest, paper trade, or live trade." No enforcement mechanism is named — is this a policy or is it tooling (e.g., content-addressed storage, signed manifests, git tag pinning)?
Impact: Without tooling, immutability is honor-system. §14 research runs and §29(10) comparison reports become disputable.
Remedy: Name the mechanism (recommend content hash + append-only version registry) and where it lives.

**FINDING-012**
Section: §27
Severity: MAJOR
Category: Governance
Observation: Golden-chart library lifecycle is undefined: who labels, how many independent reviewers, tie-breaking, conflict resolution, and — critically — the diff process when an algorithm update changes a golden example's expected output. §29(9, 10) depend on this.
Impact: Golden-chart tests will drift into rubber-stamps or die when the first legitimate algorithm improvement flips an example.
Remedy: Add a subsection specifying labeling roles, minimum reviewers per example, algo-change diff review, and a "re-label" audit trail.

**FINDING-013**
Section: §12
Severity: MAJOR
Category: Governance
Observation: §12 lists four ML must-nots (change leverage/risk, remove/widen stops, bypass determinism, self-promote). No enforcement mechanism is named. §12 as written is honor-system.
Impact: A well-intentioned ML PR can violate any of these without tripping a gate.
Remedy: Bind each must-not to a code-level check (e.g., type system forbids ML output as risk parameter; CI check forbids stop-mutation call sites in ML-owned modules).

**FINDING-014**
Section: §25
Severity: MAJOR
Category: Terminology, Testability
Observation: Regime enum lists nine states (BULL_TREND, WEAKENING_BULL, ..., DISORDERED) with no classification rule, no transition rule, and no "supporting evidence" schema. §26 shows an example table but does not commit to a rule.
Impact: Regime engine (§19) has no specification. §29(4) determinism is testable only for whatever rule an engineer invents.
Remedy: Specify the classifier as a deterministic function of Layer-2 facts, with a per-state entry/exit table and a supporting-evidence schema.

**FINDING-015**
Section: §17–§31 vs §7–§15
Severity: MAJOR
Category: Scope
Observation: The doc mixes long-term constitution (§7 Versioning, §8 Auditability, §9 Risk, §10 Execution, §11 Strategy, §12 ML, §13 Human Control, §14 Research, §15 Performance) with v0 spec (§17–§31). It does not mark which constitutional sections must be implemented in v0. §10 Execution and §9 Risk plainly are not v0 (§16 excludes live execution) but §7 Versioning, §8 Auditability, and §14 Research clearly must be.
Impact: An engineer reading §17–§31 alone will under-scope v0 (miss versioning/auditability). An engineer reading the whole doc as v0 will over-scope (build risk & execution).
Remedy: Add a per-constitution-section applicability tag: `v0`, `v0-partial`, `v1+`.

**FINDING-016**
Section: §8
Severity: MAJOR
Category: Versioning
Observation: §8 asks ten reconstruction questions but the doc names no persistence layer, retention policy, storage format, or query interface for any of them. Where do "which algorithms and versions created them" live? For how long?
Impact: v0 acceptance criterion 8 ("algorithm lineage on every fact") is untestable without a persistence contract.
Remedy: Add a "Persistence" subsection specifying the audit store (append-only), the record schema for each of the ten questions relevant to v0, and retention.

**FINDING-017**
Section: §5, §19
Severity: MAJOR
Category: Determinism
Observation: Replay engine (§19) plays candle-by-candle. Whether replay uses wall-clock ticks, event-clock (bar close), or trade-tape granularity is UNSPECIFIED. Provisional / confirmed transitions inside a bar depend on this choice.
Impact: Two implementations of the replay engine will disagree on when a fact goes provisional vs confirmed.
Remedy: Fix replay granularity for v0 (recommend event-clock at bar-close boundaries; anything sub-bar deferred to v1).

**FINDING-018**
Section: §30
Severity: MAJOR
Category: Governance
Observation: §30 is described as a "completion gate" but names no owner, no artifact, and no sign-off procedure.
Impact: Nobody can declare v0 complete.
Remedy: Assign an owner (recommend the Architect) and an artifact (recommend a signed checklist that references the §30 subsection resolutions).

### MINOR

**FINDING-019**
Section: §18
Severity: MINOR
Category: Scope
Observation: 5m timeframe is "optional." Optional timeframes create a determinism footgun: golden-chart results may or may not include 5m context.
Impact: §29(11) "stable results after restart" is ambiguous when 5m is toggled.
Remedy: Either commit 5m to v0 or defer it to v1 explicitly.

**FINDING-020**
Section: §27
Severity: MINOR
Category: Testability
Observation: "Approximately 50 BTC and 50 ETH examples." Approximate library sizes drift.
Impact: §29(9) automated golden-chart tests have a moving denominator.
Remedy: Set exact counts and require a policy for adding/retiring examples.

**FINDING-021**
Section: §26
Severity: MINOR
Category: Interface
Observation: The multi-timeframe context table looks like a schema but the doc does not say whether it is illustrative or normative.
Impact: Engineers may implement it as UI copy or as a data contract.
Remedy: Mark clearly as example.

**FINDING-022**
Section: §6
Severity: MINOR
Category: Lifecycle
Observation: SUPERSEDED and EXPIRED states are named without any entity attaching to them. Neither term reappears in the spec.
Impact: Dead enum values invite misuse.
Remedy: Delete or bind to specific transitions (likely EXPIRED for provisional facts crossing a bar-count TTL; SUPERSEDED for facts replaced by a higher-tier equivalent).

**FINDING-023**
Section: §19
Severity: MINOR
Category: Terminology
Observation: "Fact inspector" module lists "lineage" but §7 does not use that word. "Lineage" is used interchangeably with "version" and "algorithm chain" without a fixed meaning.
Impact: Minor confusion; possible schema divergence.
Remedy: Pick "lineage" or "version chain" and use one term.

**FINDING-024**
Section: §22
Severity: MINOR
Category: Terminology
Observation: "Small tick buffer" is unquantified.
Impact: Structural break tolerance has two components (tick buffer OR 0.05 ATR) and only one is specified numerically.
Remedy: Specify the tick buffer in venue ticks (recommend 1–2 ticks) or drop it in favor of pure ATR.

### NIT

**FINDING-025**
Section: cover
Severity: NIT
Category: Governance
Observation: Version "0.1" with no changelog and no prior-version reference.
Impact: When v0.2 lands, no diff is possible.
Remedy: Add a changelog appendix and require version bumps to enumerate changed sections.

**FINDING-026**
Section: §31
Severity: NIT
Category: Scope
Observation: §31 sketches v1 inline. It is helpful context but risks being read as v0 requirement.
Impact: Reader confusion.
Remedy: Prefix with "Non-normative preview" or move to an appendix.

---

## 3. Appendices

### Appendix B — Terminology Gap List

**Defined precisely in doc:** micro swing (§20, 5-candle fractal, 2 closed sides), sweep (§24), rejected sweep (§24), equal highs/lows tolerance (§24, 0.10 ATR), five layers (§3), instruments and timeframes (§18).

**Named but not precisely defined (each required by at least one v0 rule):**
- BOS — used §3, §5, §19, §22, §26, §29; not defined.
- CHoCH — §3, §5, §19, §21, §26, §29; §21 gives interpretation ("transition risk"), not rule.
- Swing (base concept) — types defined but "swing" primitive relies on undefined "fractal"/"reversal."
- Protected level / protected high / protected low — §3, §19, §30; undefined.
- Structural swing — §20, §22; defined by reference to undefined terms.
- Local swing — §20; defined via "reversal of at least 0.75 ATR" but "reversal" is undefined.
- Major swing — §20; described by chart, not by rule.
- Zone strength — §19; unquantified.
- Zone lifecycle transitions — §23; enum only.
- Cluster (both zone §23 and liquidity §24) — undefined; §24 hints "three or more nearby" but no proximity metric.
- Regime states (§25) — enum only, no classification function.
- "Supporting evidence" (§25) — schema unspecified.
- Meaningful displacement, significant directional leg — §20, §22.
- Follow-through, reclaim behavior, relative volume, close location — §22.
- Retest — §22, §30; undefined.
- Higher-timeframe influence — §30; undefined.
- Provisional-vs-tradable classification — §30; undefined.

**Terms requiring outside knowledge to interpret:** ATR (period/smoothing not given), Wilder smoothing, funding, open interest, order-book "clusters," idempotency semantics for exchange orders.

**Red flag summary:** every §30 item is a term used in a rule (§20, §22, §23) without a precise definition. This is the audit's central concern.

### Appendix D — Lifecycle & State Tables

For each stateful entity: **[E]** enumerated states, **[T]** transitions defined, **[G]** gaps.

**Candle**
- [E] DEVELOPING → CLOSED (implicit).
- [T] Close on bar boundary. §5.
- [G] Bar boundary rule for weekly / daily (see FINDING-006).

**Swing**
- [E] potential, confirmed, hierarchical, protected, invalidated (§19).
- [T] Only "confirmed" has any rule (§5, right-side candles close).
- [G] potential → confirmed criteria beyond right-side closure. Hierarchical entry. Protected entry/exit. Invalidated entry.

**Zone**
- [E] FRESH, TOUCHED, TESTED, WEAKENED, BROKEN, FLIPPED, INVALIDATED (§23).
- [T] None specified.
- [G] All transitions (see FINDING-007).

**Liquidity level**
- [E] Implied: forming, present, swept, accepted, rejected (§24).
- [T] Sweep defined; rejected/accepted partially defined.
- [G] "Forming" entry; retirement rule.

**Regime**
- [E] BULL_TREND, WEAKENING_BULL, BEAR_TREND, WEAKENING_BEAR, RANGE, COMPRESSION, EXPANSION, TRANSITION, DISORDERED (§25).
- [T] None.
- [G] All (see FINDING-014).

**Fact provisional/confirmed layer (§6)**
- [E] DEVELOPING, PROVISIONAL, CONFIRMED, INVALIDATED, EXPIRED, SUPERSEDED.
- [T] None; no entity mapping.
- [G] All (see FINDING-005).

**Trade intent / order** — n/a in v0 per §16, but §3 references them without state.

### Appendix E — Reconstruction Walkthrough (hypothetical v1 trade, six months old, three algo bumps)

Working backward through §8's ten questions:

1. **What market data was available?** — §19 importer records "timestamps, source lineage." Persistence store UNSPECIFIED. Retention UNSPECIFIED.
2. **What market facts existed?** — §7 versions everything; storage UNSPECIFIED.
3. **Which algorithms and versions created them?** — §7 asserts; storage / lookup mechanism UNSPECIFIED. See FINDING-011.
4. **Which strategy version evaluated them?** — n/a v0.
5. **Why did the strategy create a trade intent?** — n/a v0.
6. **What risk rules were applied?** — n/a v0.
7. **Why was the trade approved, modified, or rejected?** — n/a v0; risk-authority schema UNSPECIFIED (FINDING-010).
8. **What orders and fills occurred?** — n/a v0.
9. **How was the position managed?** — n/a v0.
10. **Why did it close, what was net result?** — n/a v0.

**Six-months-ago reconstruction across three algo bumps:** cannot be answered from what the doc specifies. Every question relevant to v0 (Q1–Q3) resolves to "storage UNSPECIFIED." Doc guarantees immutable versions in principle but names no persistence contract.

### Appendix G — Consolidated Config Table

| Constant | Value | Unit | Section | Purpose | Tunable? | Rationale? |
|---|---|---|---|---|---|---|
| Local swing reversal | 0.75 | ATR | §20 | Local swing amplitude gate | Implied yes ("initial research default") | Missing |
| Structural break tolerance | max(tick buffer, 0.05 ATR) | ticks / ATR | §22 | BOS confirmation | Implied yes ("initial tolerance") | Missing |
| Tick buffer | unspecified | ticks | §22 | Component of break tolerance | Implied yes | Missing |
| Equal-highs/lows tolerance | 0.10 | ATR | §24 | Liquidity clustering | Implied yes | Missing |
| Cluster count | ≥3 | count | §24 | Liquidity cluster definition | Implied yes | Missing |
| Micro-swing candles | 5 (2 each side) | candles | §20 | Fractal definition | No | Given by fractal choice |
| Golden library size | ~50 BTC / ~50 ETH | examples | §27 | Regression test corpus | Implied yes | Missing |
| ATR period | UNSPECIFIED | bars | §20, §22, §24 | Denominator of every ATR threshold | — | See FINDING-002 |
| ATR smoothing | UNSPECIFIED | — | §20, §22, §24 | — | — | See FINDING-002 |
| Numeric precision | UNSPECIFIED | — | §4 | Determinism | — | See FINDING-003 |
| Candle boundary origin | UNSPECIFIED | tz/week-start | §18, §19 | Aggregation | — | See FINDING-006 |
| Replay granularity | UNSPECIFIED | event / wall | §19 | Provisional-vs-confirmed timing | — | See FINDING-017 |
| Instruments | BTCUSDT, ETHUSDT | — | §18 | v0 scope | No | Given |
| Timeframes | 1W, 1D, 4H, 1H, 15m | — | §18 | v0 scope | No | Given |
| 5m timeframe | optional | — | §18 | Dev-only | Toggle | See FINDING-019 |

**Rule:** every "Missing" rationale is a MAJOR- or MINOR-tier finding depending on whether it drives a Layer-2 rule.

### Appendix H — Acceptance-Criteria Matrix (§29)

| # | Criterion | Mechanically testable? | Test artifact | Sign-off owner | Pass threshold |
|---|---|---|---|---|---|
| 1 | Reliable historical import and gap detection | Yes | Unit + integration test on known-gap fixtures | Unspecified | Unspecified |
| 2 | No future-data leakage during replay | Yes | Property test: fact.confirmed_at ≤ any downstream read time | Unspecified | Zero leaks |
| 3 | Accurate swing confirmation times | Partial — rule undefined (§30) | Golden-chart regression | Unspecified | Unspecified |
| 4 | Deterministic structural facts | Partial — rule undefined + numeric policy missing | Repeat-run byte diff | Unspecified | Bit-exact |
| 5 | Inspectable BOS and CHoCH | Subjective as written | Manual UI check | Unspecified | Unspecified |
| 6 | Complete zone lifecycle | No — transitions undefined (§23, §30) | — | Unspecified | Unspecified |
| 7 | Synchronized multi-timeframe charts | Yes | UI test | Unspecified | Unspecified |
| 8 | Algorithm lineage on every fact | Partial — persistence schema missing | Property test | Unspecified | 100% coverage |
| 9 | Automated golden-chart tests | Partial — library process undefined (§27) | Golden-chart run | Unspecified | Unspecified |
| 10 | Visible comparison reports for algorithm changes | Vague | — | Unspecified | Unspecified |
| 11 | Stable results after restart | Yes | Snapshot round-trip | Unspecified | Bit-exact |
| 12 | All derived facts regenerable from canonical candles | Yes | Regen-from-candles test | Unspecified | Bit-exact |

**Score:** 5/12 fully testable, 5/12 partial, 2/12 not testable as written. Zero of 12 have declared owners or pass thresholds.

---

## 4. Recommended Pre-Implementation Work (Ordered, Time-boxed)

Do these in order. Each is a doc revision, not code.

1. **§30 Annex — Resolve every §30 item as a numbered subsection.** Owner: Architect. Time-box: 10–15 working days. Addresses FINDING-001, 007, 008, 018 and unblocks Appendix H rows 3–6.
2. **Determinism Policy subsection under §4.** Numeric library, precision, rounding, tie-break ordering, ATR canonical definition, replay granularity, candle-boundary origin. Owner: Architect. Time-box: 3 days. Addresses FINDING-002, 003, 006, 017.
3. **Layer Boundary Schemas section.** One schema per boundary + fact-inspector record schema. Owner: Architect. Time-box: 3 days. Addresses FINDING-004, 010, 023.
4. **State Transition Tables appendix.** Candle, swing, zone, liquidity, regime, and the §6 provisional/confirmed layer bound to entities. Owner: Architect. Time-box: 2 days. Addresses FINDING-005, 007, 014, 022.
5. **Persistence & Retention subsection under §8.** Audit-store schema, retention, version-registry mechanism (recommend content-hash + append-only). Owner: Architect. Time-box: 2 days. Addresses FINDING-011, 016.
6. **Governance addenda.** Golden-chart labeling / re-label diff process (§27); ML must-not enforcement bindings (§12); v0 completion-gate owner and artifact (§30). Owner: Architect + user. Time-box: 2 days. Addresses FINDING-012, 013, 018.
7. **Constitutional-vs-v0 applicability tags** on every constitution section. Owner: Architect. Time-box: 0.5 day. Addresses FINDING-015.
8. **Editorial pass.** Changelog, non-normative-preview tag on §31, "example" tag on §26, fix "approximately 50" → exact count, kill unused enum values. Owner: Scribe. Time-box: 0.5 day. Addresses FINDING-019–026.

**Estimated total pre-implementation window:** ~23 working days (~4.5 weeks) before writing the first Layer-2 line of code.

---

## 5. Rules-of-Engagement Compliance

- **Did not rewrite the doc.** Findings point at gaps; remedies are directional, not drafted.
- **Did not judge trading methodology.** Swing/zone/regime taxonomies taken as given.
- **Section numbers cited on every finding.**
- **Preferred specificity.** 26 findings, all reproducible against the source doc.
- **Marked UNSPECIFIED where in doubt.**

---
*End of audit report.*
