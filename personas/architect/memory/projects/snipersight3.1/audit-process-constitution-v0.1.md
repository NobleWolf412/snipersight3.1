---
name: Audit Delegation Package — SniperSight3 Constitution & v0 Spec
description: Self-contained audit process for delegating review of SniperSight3_Product_Constitution_and_v0_System_Specification.docx v0.1 to an auditor persona. Phases A–J, findings schema, deliverable format.
type: reference
---

# Audit Delegation Package — SniperSight3 Constitution & v0 Spec

Hand this to an auditor persona (or human) as-is. It assumes zero prior context.

## 0. Auditor Brief

**You are auditing:** `SniperSight3_Product_Constitution_and_v0_System_Specification.docx` v0.1 — a governance + engineering foundation doc for a deterministic market-structure platform. No code exists yet.

**Your job:** Determine whether this document is buildable as written. Flag every place where an engineer could make two defensible but incompatible choices, every unstated assumption, and every rule that cannot be mechanically verified.

**Your output:** A single audit report with per-section findings, severity, and a go/no-go recommendation on starting v0 implementation.

**What you are NOT doing:** Judging the trading merit of the methodology (swing rules, ATR thresholds, zone taxonomy). Assume the domain choices are correct. Audit the *specification quality*, not the trading thesis.

## 1. Inputs

- The docx itself. Extract with `python-docx` if needed.
- This audit process.
- No other context. If you find yourself needing external files, that is itself a finding.

## 2. Audit Phases

Execute in order. Do not skip. Each phase produces a written artifact before the next begins.

### Phase A — Structural Read (deliverable: 1-page summary)
1. Read the doc end-to-end once without notes.
2. Write a one-page summary in your own words.
3. Re-read, marking every defined term, every numeric threshold, every must/should/may verb.

**Exit gate:** you can answer in one sentence each — what are the five layers, what does "confirmed" mean, what is v0's acceptance test.

### Phase B — Terminology Audit (deliverable: glossary + gap list)
For every capitalized term or domain word (CHoCH, BOS, swing, zone, regime, sweep, protected level, displacement, etc.):
- Defined in doc? Cite section.
- If not, definable from context without external knowledge?
- List every term requiring outside knowledge.

**Red flag:** any term used in a *rule* that is not itself precisely defined.

### Phase C — Determinism Audit (deliverable: determinism gap list)
For each, cite the governing section or mark **UNSPECIFIED**:
- Floating-point / numeric library policy
- Timezone and DST handling
- Exchange data revisions / restatements
- Rolling-window reproducibility (ATR, volatility)
- Wall-clock vs event-clock in replay
- Random-seed policy
- Tie-breaking when facts share a timestamp
- Ordering of facts across timeframes

**Rule:** "same input → same output" is not an answer. Point at *the mechanism*.

### Phase D — Lifecycle & State Audit (deliverable: state transition tables)
For each stateful entity — candle, swing, zone, liquidity level, regime, trade intent, order — extract:
- Enumerated states.
- Legal transitions (table).
- Terminal states.
- Transitions mentioned but not defined.
- Transitions omitted but that must exist (e.g., FLIPPED → REACTIVATED).

**Red flag:** any state named without a defined entry or exit condition.

### Phase E — Versioning & Auditability Audit (deliverable: reconstruction walkthrough)
Pick a hypothetical trade outcome. Walk backward through §8's ten reconstruction questions. For each:
- What data would need to be persisted?
- Is persistence explicit in the doc? Cite.
- Else **UNSPECIFIED**.

Then answer: given only what the doc specifies, can a trade from six months ago be fully reconstructed after three intervening algo-version bumps? Justify.

### Phase F — Interface & Boundary Audit (deliverable: interface gap list)
For each layer boundary (1→2, 2→3, 3→4, 4→5):
- Schema of the object crossing?
- Invariants the receiver may assume?
- Documented where?

Same for:
- ML output → layer pipeline (rank is Layer-2 or Layer-3?)
- Risk authority → strategy (approval/reduction/rejection format)
- Human control → automation (what happens mid-order to "disable strategy"?)

### Phase G — Threshold & Config Audit (deliverable: consolidated config table)
Extract every numeric constant into one table: value, unit, section, purpose, tunable?, rationale?

**Red flag:** any constant used in a rule with no tunability or rationale.

### Phase H — Testability Audit (deliverable: acceptance-criteria matrix)
For each of §29's twelve v0 acceptance criteria:
- Mechanically testable? (yes/no/partial)
- Test artifact? (unit test, golden-chart run, manual, unspecified)
- Sign-off owner?
- Pass threshold?

### Phase I — Governance Audit (deliverable: process gap list)
For each governance mechanism:
- Golden-chart library: who labels, who reviews, what is the diff process when an algo update flips a golden example?
- Version immutability: what enforces it? (policy vs tooling)
- Completion gate §30: who declares it satisfied?
- ML prohibitions §12: what mechanism prevents violation?

**Rule:** every "must not" needs an enforcement mechanism or acknowledgment that it's honor-system.

### Phase J — Scope Consistency (deliverable: contradiction list)
Cross-reference every "v0 excludes" claim (§16) against functional modules (§19) and acceptance criteria (§29). List contradictions or ambiguities.

## 3. Findings Schema

```
FINDING-NNN
Section:      §<n> <title>
Severity:     BLOCKER | MAJOR | MINOR | NIT
Category:     Determinism | Lifecycle | Versioning | Interface |
              Config | Testability | Governance | Scope | Terminology
Observation:  <what the doc says or fails to say>
Impact:       <what breaks or diverges if not fixed>
Remedy:       <specific text/spec addition needed>
```

**Severity rubric:**
- **BLOCKER** — implementation cannot start; two engineers will pick incompatibly.
- **MAJOR** — implementation can start but will require rework; audit trail or determinism at risk.
- **MINOR** — clarity/consistency; slows onboarding, won't cause bugs.
- **NIT** — editorial.

## 4. Final Deliverable

Single markdown document:

1. **Executive Verdict** — one paragraph. Go/no-go on v0, with top three blockers.
2. **Findings** — all findings, sorted by severity then section.
3. **Appendices** — artifacts from Phases B, D, E, G, H.
4. **Recommended pre-implementation work** — ordered list of doc revisions required before code starts. Time-box each.

Target: 15–25 pages. Twenty sharp findings beat sixty vague ones.

## 5. Rules of Engagement

- **Do not rewrite the doc.** Point at gaps; propose remedies; do not draft the fix unless asked.
- **Do not judge trading methodology.** Swings, zones, regime definitions are given.
- **Cite section numbers for every claim.**
- **Prefer specificity over volume.**
- **When in doubt, mark UNSPECIFIED.** That is the finding.

## 6. Handoff Checklist

- [x] Source document identified
- [x] Audit process documented (this file)
- [x] Severity rubric defined
- [x] Deliverable format specified
- [x] Scope boundaries clear
- [ ] Auditor persona seated and briefed
- [ ] Findings-log location agreed (suggest: `personas/auditor/memory/projects/snipersight3.1/audit-v0.1/`)
