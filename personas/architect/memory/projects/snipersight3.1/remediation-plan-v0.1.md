---
name: SniperSight3 v0.1 — Architect Remediation Plan
description: Architect's response to the Auditor's NO-GO verdict on Constitution & v0 Spec v0.1. Concurs with the blockers, re-sequences the remediation queue by dependency and by who can actually author each item, and lists the trading-judgment questions the user must arbitrate before §30 can be closed.
type: project
---

# Architect Remediation Plan — SniperSight3 v0.1

**Responding to:** `personas/auditor/memory/projects/snipersight3.1/audit-v0.1/findings-report.md`
**Date:** 2026-07-17
**Verdict on the audit:** Concur. NO-GO on v0 implementation is correct.

---

## 1. Where I agree, disagree, and refine

**Agree with the three top blockers as stated.** §30-as-postscript, no determinism mechanism, no layer-boundary schema. These are the right three and they are in the right order.

**One refinement to the audit's sequencing.** The audit lists eight items with a ~23-day total. Two dimensions the audit does not separate:

1. **Author.** Items 2, 3, 4, 7 are pure spec-authoring — Architect can execute alone. Item 1 (§30) and Item 6 (governance) require user trading-judgment or org-process input. Item 5 (persistence) is architect-authored but should follow item 3.
2. **Dependency.** Item 2 (determinism policy) is a prerequisite for item 1 (§30 rule set uses ATR, tolerance, tie-break) *and* item 3 (schemas need a numeric type). The audit does item 1 first; that's backwards.

**Corrected order (dependency-first, author-partitioned):**

| # | Item | Author | Blocks | Time |
|---|---|---|---|---|
| A | Determinism Policy (was #2) | Architect solo | everything downstream | 3d |
| B | Layer Boundary Schemas (was #3) | Architect solo | §30 rules, state tables, persistence | 3d |
| C | State Transition Tables (was #4) | Architect solo | §30 zone lifecycle, replay engine | 2d |
| D | Persistence & Retention (was #5) | Architect solo | audit trail, version registry | 2d |
| E | Applicability Tags (was #7) | Architect solo | scope legibility | 0.5d |
| F | §30 Annex (was #1) | Architect + **user (trading judgment)** | §29(3–6) | 10–15d |
| G | Governance Addenda (was #6) | Architect + user | golden-chart process, ML enforcement | 2d |
| H | Editorial (was #8) | Scribe | none | 0.5d |

**Net effect:** items A–E are ~10.5 days of pure architect work with no user dependency. They should proceed now. Items F, G are the ones that need the user to sit in the room.

**What the audit understates.** FINDING-011 (immutability enforcement) is filed as MAJOR, but if we go with content-hash + append-only registry, that's a non-trivial infrastructure choice with runtime cost — it belongs in the determinism policy discussion, not deferred to governance.

**What the audit overweights.** FINDING-017 (replay granularity) is real but self-solving: for v0 the only defensible choice is **event-clock at bar close**. Sub-bar replay is a v1 concern. I'll fix this in the determinism policy in one sentence and it's done.

---

## 2. §30 — the ten items and who decides what

The audit correctly identifies §30 as a spec-annex-in-disguise. Architect cannot author it alone because most items require the user's trading judgment. Below: each item, whether it's a **methodology** call (user decides) or a **mechanism** call (architect decides), and my recommendation where I have one.

| §30 item | Type | Recommendation |
|---|---|---|
| 1. Swing confirmation criteria | methodology | User must pick: N right-side closes at what displacement threshold? Recommend 2 right-side closes + ≥0.25 ATR against last extreme, but user owns this. |
| 2. Structural-tier hierarchy (micro/local/major) | mixed | Architect can define the deterministic promotion function once user names the promotion thresholds. |
| 3. Protected high / protected low | methodology | User: is "protected" = last confirmed structural swing above/below a BOS, or something else? |
| 4. BOS / CHoCH level selection | methodology | User must pick which swing tier a break must clear to count as BOS (recommend: local for CHoCH, structural for BOS). |
| 5. Wick vs close for break confirmation | methodology | Strongly recommend close-based for determinism; wick-based is defensible but noisier. |
| 6. Break tolerance | mechanism | Architect: `max(1 tick, 0.05 ATR)`. Audit's FINDING-024 tick buffer resolves here. |
| 7. Zone break vs flip | methodology | User: does a broken demand zone flip to supply on any close through, or only after a retest-and-rejection? |
| 8. Retest definition | mechanism, given #7 | Architect can specify once #7 is answered. |
| 9. HTF influence | methodology | User: does HTF regime *filter* LTF setups, *rank* them, or *annotate* them? |
| 10. Provisional-vs-tradable | mechanism | Architect: PROVISIONAL = fact exists but confirmation-timer not elapsed; TRADABLE = strategy-layer concept, not §30's problem, defer to v1. |

**Six of ten items are user-judgment. Four are mechanism.** The mechanism items I will draft now inside the state-transition tables (item C). The methodology items block on a working session with the user.

---

## 3. What I am producing in this handoff

1. This plan.
2. `determinism-policy-draft.md` — first pass at item A, ready for user review.
3. `layer-boundary-schemas-draft.md` — first pass at item B, ready for user review.

Items C, D, E can be drafted in the next session without user input. Item F (§30) is blocked pending the working session described in §2 above.

---

## 4. Handoff back to user

The audit's remediation queue is sound but re-sequenced above. I have started the architect-solo work. Before I can close §30, I need answers on the six methodology items in §2. That is a working session, not a document — best done live.
