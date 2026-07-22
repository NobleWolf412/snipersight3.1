---
name: SniperSight3 v0.1 — Re-audit of Architect Drafts A and B
description: Auditor's independent re-review of the Architect's Determinism Policy (item A) and Layer Boundary Schemas (item B) drafts, plus a ruling on the Architect's re-sequencing of the eight-item remediation queue. Follow-up to audit-v0.1/findings-report.md.
type: reference
---

# Re-audit — SniperSight3 v0.1 Drafts A & B

**Source docs re-audited:**
- `personas/architect/memory/projects/snipersight3.1/remediation-plan-v0.1.md`
- `personas/architect/memory/projects/snipersight3.1/determinism-policy-draft.md`
- `personas/architect/memory/projects/snipersight3.1/layer-boundary-schemas-draft.md`

**Baseline:** `personas/auditor/memory/projects/snipersight3.1/audit-v0.1/findings-report.md`
**Date:** 2026-07-17
**Scope:** (i) is the Architect's re-sequencing of the remediation queue sound? (ii) do drafts A and B close the audit findings they claim to close, and what new gaps have they introduced?

---

## 1. Ruling on the sequencing deviation

**Concur with the Architect's re-sequence.** Move to A–H order (Determinism → Schemas → State Tables → Persistence → Applicability Tags → §30 → Governance → Editorial).

**Why the original audit put §30 first.** Severity ordering — §30 is the deepest source of ambiguity and gates the most §29 rows. The audit sorted by "what breaks v0 hardest," not "what unblocks the author's next keystroke."

**Why the Architect's ordering is better.** Two arguments both hold:
1. **Dependency.** §30 rules are written in the vocabulary of the Determinism Policy (ATR, tolerance, tie-break, numeric type). Writing §30 before Item A means either forward-referencing undefined machinery or committing to prose that Item A will later contradict. Item A is a true prerequisite.
2. **Authorability.** Six of ten §30 items are trading-methodology calls the Architect cannot answer. Blocking A–E on a user working session for §30 wastes ~10 days of parallelizable work.

**One caveat the Architect must accept for the re-sequence to be safe.**
Items A–E cannot be *frozen* until F closes. Some §30 answers will retroactively require changes to D3 (e.g., a new entity_kind_rank if §30 introduces a new fact kind), to the swing/zone kind bodies in S3, or to the state-transition table in Item C. Architect must:
- Version items A–E as `draft-v0.2` and not merge to the Constitution until F closes.
- Maintain an explicit back-reference from each §30 resolution to the fields in A/B/C it touches.
- Re-audit is triggered at F-close on the union of A–E, not just F.

**Sequencing verdict: SOUND with the freeze-caveat above. No re-bounce needed on this dimension.**

---

## 2. Draft A — Determinism Policy §4.1

Draft A substantially advances FINDING-002, FINDING-003, FINDING-006, FINDING-017, and partially FINDING-011. New findings below are numbered A-01…A-08 to distinguish from v0.1.

### BLOCKERS (Draft A)

**FINDING-A-01**
Section: Draft A §D6 (content_hash)
Severity: BLOCKER
Category: Determinism
Observation: D6 says `content_hash = BLAKE2b-256 of the canonical serialization of the fact body`. The canonical serialization format is not specified — no mention of JSON canonicalization (RFC 8785), CBOR, Protobuf, MessagePack, or a bespoke rule. Two implementations of "canonical serialization" produce different hashes for the same fact.
Impact: The content-hash-based immutability mechanism, and any bit-exact §29(11) test that reads a stored fact, is non-reproducible across implementations. Directly undermines D6's own purpose.
Remedy: Pick one canonical form and specify it exhaustively. Recommend RFC 8785 JSON Canonicalization Scheme (JCS) with Decimal serialized as a string in fixed scientific notation, or a Protobuf schema pinned by `policy_version`. Whichever is chosen, produce a golden test vector in the doc.

### MAJOR (Draft A)

**FINDING-A-02**
Section: Draft A §D2 (ATR canonical)
Severity: MAJOR
Category: Determinism
Observation: Wilder's RMA is defined as a recurrence `atr[i] = (atr[i-1] * 13 + tr[i]) / 14` but the seed `atr[13]` (the value used to start the recursion at bar 14) is not specified. Common conventions differ: seed = `SMA(TR[0..13])`, seed = `TR[13]`, or seed = `mean(TR)` of the whole warmup window. Different seeds → different ATR series forever.
Impact: All ATR-scaled thresholds diverge across implementations despite the policy naming period, method, and TR formula.
Remedy: State the seed explicitly. Recommend `atr[13] = SMA(TR[0..13])`, matching the classical Wilder formulation.

**FINDING-A-03**
Section: Draft A §D1 (numeric library)
Severity: MAJOR
Category: Determinism
Observation: "Rounding applied only at explicit rounding boundaries; intermediate values retain full working precision." The set of explicit rounding boundaries is not enumerated. Candidates include: ATR value at each recursion step, threshold comparison in a rule predicate, tick-quantization at price display, `input_hash` canonicalization. Without an enumeration, two implementations round at different points and produce different fact bodies.
Impact: Non-reproducibility despite the Decimal mandate.
Remedy: Enumerate rounding boundaries as a closed list. Recommend: (a) no rounding inside ATR recursion — full precision retained; (b) tick-quantization only on prices read *from* the candle stream (already tick-quantized by venue); (c) rounding on comparison is forbidden — comparisons use `Decimal` `==`/`<` directly on full-precision operands.

**FINDING-A-04**
Section: Draft A §D3 (intra_bar_seq)
Severity: MAJOR
Category: Determinism
Observation: `intra_bar_seq` breaks ties when multiple facts of the same kind confirm at the same bar close (e.g., two liquidity sweeps in one bar). The rule for assigning `intra_bar_seq` deterministically is not given. Alphabetical by `fact_id`? Ascending by price level? Descending by input-order? Two implementations will pick different orders.
Impact: Order_key is only a total order if intra_bar_seq is deterministic. Currently it is under-specified for the case the field was invented for.
Remedy: Specify assignment rule. Recommend: `intra_bar_seq = rank of (price, side)` under a stated comparator (e.g., ascending price, then side lexicographic).

**FINDING-A-05**
Section: Draft A §D6 (algo source hash)
Severity: MAJOR
Category: Versioning
Observation: Registry key is `(algo_version, content_hash of algo source)`. "algo source" is undefined — is it a single file, a package tree, the transitive dependency closure, the built wheel, the container image? Each choice has different reproducibility properties.
Impact: The immutability guarantee is only as strong as the hash target. Hashing a single file leaves imports mutable; hashing a container is heavy but airtight.
Remedy: Pick and document. Recommend: `content_hash of algo source` = SHA-256 of a pinned lockfile-plus-source tarball produced by a documented build step, not a live file-tree hash.

### MINOR (Draft A)

**FINDING-A-06**
Section: Draft A §D2 (True Range at bar 0)
Severity: MINOR
Category: Determinism
Observation: `TR[i] = max(high - low, |high - prev_close|, |low - prev_close|)`. `prev_close` is undefined for the first bar of a stream. Standard convention is `TR[0] = high - low`. Not stated.
Impact: A rare edge case (very first bar) diverges across implementations. Effect is small — first-bar TR feeds into warmup only — but non-zero.
Remedy: Add "TR[0] = high[0] - low[0]."

**FINDING-A-07**
Section: Draft A §D4 (4H alignment)
Severity: MINOR
Category: Determinism
Observation: "4H / 1H / 15m / 5m: aligned to UTC midnight." Ambiguous: does 4H mean bars anchored at 00, 04, 08, 12, 16, 20 UTC (Binance kline convention), or something else? "Aligned to UTC midnight" only pins the day origin, not the intra-day bucketing.
Impact: A conforming reader could produce a shifted 4H series.
Remedy: State explicitly that 4H bars begin at UTC hours {0, 4, 8, 12, 16, 20}; 1H bars begin at UTC hours {0..23}; 15m bars begin at UTC minutes {0, 15, 30, 45} of each hour; 5m analogously.

**FINDING-A-08**
Section: Draft A §D7 (forbidden non-determinism sources)
Severity: MINOR
Category: Determinism
Observation: List omits two common pitfalls in a numeric-Python stack: (i) pandas / numpy version-dependent behavior (groupby ordering changed in pandas 2.0; certain numpy sort implementations are non-stable); (ii) locale-dependent decimal parsing at ingest.
Impact: A pinned Decimal policy can still be defeated by an unpinned library stack.
Remedy: Add "runtime dependency versions are pinned in the version registry" and "all decimal parsing uses `Decimal('...')` with a locale-independent string, never `float(s)` or `locale.atof`."

### NIT (Draft A)

**FINDING-A-09**
Section: Draft A §D2 (warmup diagnostic)
Severity: NIT
Category: Interface
Observation: Warmup rule says "Any Layer-2 rule with an ATR-scaled threshold emits no fact during warmup and records a `reason: "atr_warmup"` diagnostic." The diagnostic channel is not defined anywhere (schema, sink, retention).
Impact: Diagnostic is invented in isolation and may not survive persistence spec (Item D).
Remedy: Either bind the diagnostic to a defined channel (e.g., a diagnostic record in the audit store) in Item D, or drop the field name from Item A and let Item D own it.

### Coverage vs audit v0.1

| v0.1 Finding | Addressed by Draft A? | Notes |
|---|---|---|
| FINDING-002 (ATR) | Partial | Seed missing (FINDING-A-02); TR[0] convention missing (A-06). |
| FINDING-003 (numeric policy, tie-break) | Partial | Canonical serialization missing (A-01, blocker); rounding boundaries under-specified (A-03); intra_bar_seq assignment missing (A-04). |
| FINDING-006 (candle boundary origin) | Yes, pending user venue confirmation | 4H bucket alignment needs one clarifying line (A-07). |
| FINDING-017 (replay granularity) | Yes | Event-clock at bar close, cross-timeframe rule stated. Clean close. |
| FINDING-011 (immutability enforcement) | Partial | Registry named, but algo-source hash target undefined (A-05). |

**Draft A verdict: MUST-FIX A-01 before merge; SHOULD-FIX A-02, A-03, A-04, A-05 before merge. Rest can land in a follow-up minor.**

---

## 3. Draft B — Layer Boundary Schemas §3.1

Draft B substantially advances FINDING-004, FINDING-023, and partially FINDING-010. New findings numbered B-01…B-05.

### BLOCKERS (Draft B)

None.

### MAJOR (Draft B)

**FINDING-B-01**
Section: Draft B §S2 (Fact envelope) and Draft A §D6 (content_hash)
Severity: MAJOR
Category: Determinism, Interface
Observation: `content_hash` is a required field on `Fact` but Draft B does not state which fields are included in the hash and which are excluded (Draft A says "excluding algo_version, policy_version, content_hash" but says nothing about `state`, `state_history`, `fact_id`, or `order_key`). If `state` is included, the hash changes every time the fact transitions (defeating immutability of the identity). If `state` is excluded, then two facts with same content but different state histories share the same hash (defeating uniqueness on lookup).
Impact: `fact_id` is defined as "content_hash prefixed with kind" — so its stability across state transitions is directly load-bearing. The specification does not pin the answer.
Remedy: Explicitly enumerate `content_hash` inputs. Recommend: content_hash covers `{kind, symbol, timeframe, body, provenance, order_key.bar_close_ts, order_key.timeframe_rank, order_key.entity_kind_rank, order_key.intra_bar_seq}` and excludes `{state, state_history, algo_version, policy_version, content_hash, input_hash, fact_id}`. Cross-reference into Draft A §D6.

### MINOR (Draft B)

**FINDING-B-02**
Section: Draft B §S2 (provenance)
Severity: MINOR
Category: Interface
Observation: `provenance: [candle_bar_close_ts, ...]` is a list of timestamps only. A fact can reference candles from multiple timeframes (e.g., a 4H structure break confirmed by evidence in the 15m stream). Without a timeframe tag per provenance entry, the `input_hash` of a multi-timeframe fact is ambiguous.
Impact: Multi-timeframe facts cannot be uniquely reproduced from their stored provenance.
Remedy: Change to `provenance: [{timeframe, bar_close_ts}]`. Cost is trivial; benefit is uniqueness.

**FINDING-B-03**
Section: Draft B §S1 (Candle bar_close_ts)
Severity: MINOR
Category: Determinism
Observation: `bar_close_ts` is marked "exclusive-close boundary" but `bar_close_ts - bar_open_ts = fixed per timeframe` implies inclusive. E.g., a 15m bar starting at 00:00:00 has `bar_close_ts` = 00:15:00 (exclusive end) *or* 00:14:59.999999999 (inclusive end). Both conventions exist; Binance kline uses inclusive-end.
Impact: Two implementations can differ by one nanosecond on every `bar_close_ts`, which propagates into every `order_key` and every `provenance` reference.
Remedy: Pick one. Recommend `bar_close_ts` = start_of_next_bar (exclusive-end convention) — this is what most kline APIs actually return in their "close time" field for the previous bar boundary. Then update D3 rank so ordering is unaffected.

**FINDING-B-04**
Section: Draft B §S3 (LiquidityLevelBody)
Severity: MINOR
Category: Interface
Observation: LiquidityLevelBody `kind` enum is `{equal_highs, equal_lows, session_high, session_low}`. §24 of the source doc also uses "cluster" and "sweep target" language. Is a cluster a separate kind, or a variant of equal_highs? Is a sweep target derived on the fly? Not stated.
Impact: The mapping from §24's vocabulary to this schema is not one-to-one.
Remedy: Either extend the enum to cover §24's full liquidity vocabulary or annotate this schema with the intended mapping.

**FINDING-B-05**
Section: Draft B §S3 (StructureBreakBody.tolerance_used)
Severity: MINOR
Category: Auditability
Observation: `tolerance_used: Decimal` records only the final `max(tick_buffer, 0.05 * ATR)` result. It does not record the components. When an implementation change alters either component, an auditor cannot tell from the stored fact whether the tick_buffer or the ATR contribution was decisive.
Impact: Audit reconstruction of "why did this break confirm" is coarser than needed. Not a determinism defect — a debuggability one.
Remedy: Record `{tolerance_used, tick_component, atr_component}` or note the decision explicitly ("tick" vs "atr" chose the max).

### NIT (Draft B)

**FINDING-B-06**
Section: Draft B §S4 (FactStream)
Severity: NIT
Category: Interface
Observation: FactStream is described as pull-with-cursor. "No push semantics." For v0 offline replay, this is exactly right and matches §29(11). For v1 live streaming, pull-with-cursor at nanosecond granularity does not scale. Deferring this is correct; noting it here is defensive.
Impact: None in v0.
Remedy: Add "v1: live push semantics TBD" so nobody optimizes v0 for a v1 that won't use this API.

### Coverage vs audit v0.1

| v0.1 Finding | Addressed by Draft B? | Notes |
|---|---|---|
| FINDING-004 (schemas per boundary) | Yes | S1–S6 cover all five boundaries. |
| FINDING-010 (risk verdict schema) | Yes, as stub | RiskVerdict deferred to v1 but stubbed. Sufficient for v0. |
| FINDING-023 (lineage vs version chain terminology) | Yes | Adopts "lineage." Clean close. |

**Draft B verdict: SHOULD-FIX B-01 before merge; other findings can land in a follow-up minor.**

---

## 4. Cross-cutting

- **Content-hash contract is split across A and B and inconsistent.** FINDING-A-01 (serialization format) and FINDING-B-01 (input field set) must be resolved as a *pair* — either draft could be fixed alone and still leave the other broken. Recommend a joint "Fact Identity" subsection cross-linked from both.
- **Provenance and input_hash must agree.** FINDING-B-02 (provenance per timeframe) implies input_hash must canonicalize timeframe tags. If A-01's canonical form is fixed to include timeframe tags in provenance, B-02 collapses to a cosmetic update.
- **Freeze discipline.** Reiterating from §1: no draft can merge until F closes. Both drafts should be reviewed once more after §30 resolutions land.

---

## 5. Verdict summary

| Item | Verdict | Blockers | Majors | Minors | Nits |
|---|---|---|---|---|---|
| Sequencing re-order | Concur (with freeze caveat) | 0 | 0 | 0 | 0 |
| Draft A — Determinism Policy | Substantial progress; **must-fix A-01 before merge** | 1 | 4 | 3 | 1 |
| Draft B — Layer Boundary Schemas | Substantial progress; **should-fix B-01 before merge** | 0 | 1 | 4 | 1 |

**Overall re-audit verdict: PROCEED with re-sequenced plan. Neither draft is a re-bounce; both are on-track with specific fixes enumerated.** Architect should close A-01 (blocker, canonical serialization) before continuing to Item C. Item C (State Transition Tables) can proceed in parallel with the A/B fixes since it does not depend on the specific canonical form.

---
*End of re-audit.*
