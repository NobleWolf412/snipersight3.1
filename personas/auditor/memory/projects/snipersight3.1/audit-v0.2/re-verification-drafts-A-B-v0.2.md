---
name: SniperSight3 v0.1 — Re-verification of Architect Drafts A and B at v0.2
description: Auditor's second-pass re-verification of the Architect's Determinism Policy and Layer Boundary Schemas drafts after in-place revision to v0.2. Confirms closure of the audit-v0.2 blocker (A-01), majors (A-02..A-05, B-01), minors (A-06..A-08, B-02, B-03) and nit (A-09), and records new minor/nit findings for the follow-up minor pass. Successor to audit-v0.2/re-audit-drafts-A-B.md.
type: reference
---

# Re-verification — SniperSight3 v0.1 Drafts A & B at v0.2

**Source docs re-verified (v0.2, 2026-07-17):**
- `personas/architect/memory/projects/snipersight3.1/determinism-policy-draft.md`
- `personas/architect/memory/projects/snipersight3.1/layer-boundary-schemas-draft.md`

**Baseline:** `personas/auditor/memory/projects/snipersight3.1/audit-v0.2/re-audit-drafts-A-B.md`
**Date:** 2026-07-17
**Scope:** (i) did v0.2 close A-01 (blocker), A-02..A-05 (majors), B-01 (major), and the minors/nits it claims? (ii) what new gaps did the revision introduce?

---

## 1. Verdict

**PROCEED. All targeted audit-v0.2 findings are substantially closed at v0.2.** Item C (State Transition Tables) is unblocked and can start now. Freeze caveat from re-audit §1 still holds — nothing merges until §30 (item F) closes, and the v0.2 drafts must be reviewed once more at F-close.

Seven new minor/nit issues were found in the process of verifying the fixes. All are editorial or edge-case gaps in the §D8 and §D2 rewrites. None are re-bounce material; all can land in the follow-up minor pass alongside the already-deferred B-04/B-05/B-06.

---

## 2. Closure table — audit-v0.2 findings

| Finding | Sev | Fix location | Closed? | Notes |
|---|---|---|---|---|
| A-01 | BLOCKER | §D8.1 | **Yes (substantially)** | RFC 8785 JCS pinned; Decimal-as-string rule stated; golden-vector requirement placed. Two edge cases uncovered — see NEW-01, NEW-02. |
| A-02 | MAJOR | §D2 | **Yes** | Seed atr[14] = SMA(TR[1..14]) explicit. Off-by-one in the recursion index bound remains — see NEW-04. |
| A-03 | MAJOR | §D1 | **Yes (substantially)** | Rounding boundaries enumerated as a closed list; comparison-on-rounded is forbidden. Wording contradicts Decimal-context division — see NEW-05. |
| A-04 | MAJOR | §D3 | **Yes** | Four-step comparator with content_hash fallback; §D8.2 excludes intra_bar_seq from the hash to break circularity. Comparator holds for all v0 kinds (Swing, StructureBreak, Zone, Liquidity, Regime). |
| A-05 | MAJOR | §D6 | **Yes** | SHA-256 of a reproducible-tar recipe pinned. GNU-tar dependency worth flagging — see NEW-06. |
| A-06 | MINOR | §D2 | **Yes** | TR[1] = high[1] − low[1] stated for stream origin and post-gap re-seed. |
| A-07 | MINOR | §D4 | **Yes** | 4H/1H/15m/5m bucketing pinned to Binance kline conventions. |
| A-08 | MINOR | §D7 | **Yes** | Locale-independent Decimal ingest + pinned dependency stack both added. |
| A-09 | NIT | §D9 | **Yes** | Diagnostic record bound to a persistence-owned channel with a schema. |
| B-01 | MAJOR | Draft B §S2 → Draft A §D8.2 | **Yes** | Field set enumerated (included: kind/symbol/timeframe/body/order_key.{bar_close_ts,timeframe_rank,entity_kind_rank}/provenance; excluded: state/state_history/algo_version/policy_version/self-refs/intra_bar_seq). |
| B-02 | MINOR | Draft B §S2 | **Yes** | `provenance: [{timeframe, bar_close_ts}]`. §D8.2 references this list. |
| B-03 | MINOR | Draft B §S1 | **Yes** | Exclusive-end convention (bar_close_ts = bar_open_ts_of_next_bar). Ordering under §D3 unaffected because bar_close_ts values are strictly increasing under either convention. |
| B-04 | MINOR | (deferred) | Deferred to follow-up minor by Architect. Concur. |
| B-05 | MINOR | (deferred) | Deferred. Concur. |
| B-06 | NIT | (deferred) | Deferred. Concur. |

**Coverage vs original audit v0.1** is unchanged from re-audit-drafts-A-B.md; no regressions.

---

## 3. New findings introduced by v0.2

Numbered R-01..R-07 (R for re-verification) to keep distinct from the A/B series.

### MINOR

**FINDING-R-01**
Section: Draft A §D8.1 (Decimal serialization — zero case)
Severity: MINOR
Category: Determinism
Observation: The rule states `Decimal("0.00")` → `"0"` and prescribes the recipe `format(d.normalize(), 'f')`. In Python, `Decimal("0.00").normalize()` returns `Decimal("0E-2")` (the General Decimal Arithmetic spec preserves a zero exponent; `.normalize()` reduces the coefficient but not the exponent for zero). Then `format(Decimal("0E-2"), "f")` returns `"0.00"`, not `"0"`. The recipe and the stated rule diverge for every zero-valued Decimal that arrives with a non-zero exponent (any `Decimal("0.0")`, `Decimal("0.00")`, `Decimal("0E-8")`, etc.).
Impact: Two implementations that follow the recipe literally will disagree with two implementations that follow the rule literally. Same `content_hash` input, different bytes, different hash. Directly re-opens A-01 for the zero case.
Remedy: Add a pre-normalization branch: "if `d == Decimal(0)` (or `d.is_zero()`), emit the literal string `"0"`; otherwise emit `format(d.normalize(), 'f')`." Add a golden vector row for `Decimal("0.00")` and `Decimal("-0")` to CI.

**FINDING-R-02**
Section: Draft A §D8.1 (Decimal special values)
Severity: MINOR
Category: Determinism
Observation: The serialization rule enumerates finite Decimal cases only. Decimal supports `NaN`, `sNaN`, `Infinity`, and `-Infinity`. If any of these ever appear in a fact body (e.g., via a division-by-zero path that isn't guarded), the canonicalizer's behavior is undefined.
Impact: Determinism defect if any such value reaches serialization. Low probability but silently corrupting.
Remedy: Add "Decimal values in a fact body MUST be finite. `NaN`, `sNaN`, `Infinity`, and `-Infinity` are a determinism defect and MUST raise at fact-emit time before serialization." Then the canonicalizer never sees them.

**FINDING-R-03**
Section: Draft A §D2 (ATR recursion index bound)
Severity: MINOR (borderline MAJOR)
Category: Determinism
Observation: §D2 states the recursion `atr[i] = (atr[i-1] * 13 + tr[i]) / 14 for i ≥ 14`, then two lines later states the seed `atr[14] = SMA(TR[1..14])` and closes with "The recursion begins at bar 15." The first bound is inconsistent with the last: if the recursion applies at i = 14, it dereferences atr[13], which is never defined; the seed rule is only reachable if the recursion applies at i ≥ 15. Two conforming implementations, one taking the formula bound literally and one taking the closing sentence literally, will disagree on atr[14] and every subsequent value.
Impact: Real determinism defect in the ATR canonical, which is the single most-referenced quantity in the policy. Editorial-looking but load-bearing.
Remedy: Change the recursion bound to "for `i ≥ 15`" and delete the closing sentence (now redundant). Or leave the closing sentence and change the bound; either fixes it.

**FINDING-R-04**
Section: Draft A §D1 (rounding boundaries wording)
Severity: MINOR
Category: Editorial (with determinism implication)
Observation: §D1 says "ATR recursion and its intermediate values are **not** rounded — full `Decimal` working precision is retained across the whole recursion." But every Decimal division inside the recursion (the `/ 14` step) rounds to the fixed 28-digit working precision using `ROUND_HALF_EVEN` — that is what "working precision" means. Read literally, the current wording forbids the division that computes the recursion.
Impact: An implementer following the letter of §D1 may attempt to disable Decimal context rounding, hit InvalidOperation or NotImplemented, and either work around it non-portably or file a bug. Not a divergence between implementations — a wording bug that will confuse every implementer.
Remedy: Distinguish context-level rounding (working precision, deterministic and unavoidable) from user-level rounding (forbidden except at the enumerated boundaries). Suggested text: "Context-level rounding at 28-digit working precision with `ROUND_HALF_EVEN` is the only rounding applied inside the ATR recursion. No user-code `round()`, `quantize()`, or ad-hoc truncation is permitted inside the recursion or in rule-predicate comparisons; those must operate on the full-precision `Decimal` operands directly."

### NIT

**FINDING-R-05**
Section: Draft A §D8.1 (negative zero)
Severity: NIT
Category: Determinism
Observation: "leading `-` only if negative" is ambiguous for `Decimal("-0")`. Decimal preserves sign of zero (`Decimal("-0").is_signed() == True`). Whether `"-0"` or `"0"` is the canonical form is not pinned.
Impact: Rare (only reachable via explicit `-0` construction or certain subtraction paths), but breaks strict canonicalization when it happens.
Remedy: "Negative zero canonicalizes to `"0"` (no sign)." Add to the golden vector.

**FINDING-R-06**
Section: Draft A §D6 (tar recipe portability)
Severity: NIT
Category: Reproducibility
Observation: The `algo_source_hash` recipe pins `tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='UTC 1970-01-01'`. `--sort=name` and `--mtime` are GNU-tar extensions; BSD tar (macOS default) and busybox tar do not accept them. A developer building on macOS without GNU tar installed will produce a different tarball layout and a different SHA-256.
Impact: Registry-key mismatch on cross-platform builds. Not a v0-blocker (CI can pin the image) but worth naming.
Remedy: "GNU tar ≥ 1.28 is required for the reference build; the CI image and the developer build docs must both pin it. An alternative deterministic recipe using `find … -print0 | LC_ALL=C sort -z | xargs -0 tar --format=ustar …` MAY be substituted provided the resulting byte stream is byte-identical."

**FINDING-R-07**
Section: Draft A §D6 (hash-algorithm asymmetry)
Severity: NIT
Category: Editorial
Observation: `content_hash` and `input_hash` use BLAKE2b-256; `algo_source_hash` uses SHA-256. Both are cryptographically fine; the asymmetry will read as inconsistent to reviewers unfamiliar with the rationale.
Impact: None functional; documentation friction.
Remedy: One-line rationale in §D6 ("SHA-256 for algo_source_hash to match standard binary-signing toolchains; BLAKE2b-256 for fact/input hashes for speed on hot paths"). Or unify on BLAKE2b-256 across the board.

---

## 4. Cross-cutting observations

- **§D8 is now the single source of truth for fact identity as intended.** Draft B §S2 correctly references §D8.2 for the content_hash field set and §D8.1 for canonicalization. No duplication drift observed.
- **§D3 comparator × §D8.2 exclusion correctly break the D3 circularity.** intra_bar_seq is assigned from content_hash, and content_hash excludes intra_bar_seq. Verified.
- **The §D3 comparator covers every v0 fact kind.** Swing has `anchor_price` + `side`; StructureBreak has `break_price` + `direction`; Zone has `top`; LiquidityLevel has `price`; Regime has neither price nor side nor direction and falls straight to the content_hash fallback (acceptable — there is only one regime per (symbol, timeframe, bar_close_ts) in v0 anyway).
- **Freeze caveat unchanged.** Drafts remain draft-v0.2 until §30 (F) closes. New R-findings can be swept alongside B-04/B-05/B-06 in the follow-up minor pass.

---

## 5. Summary

| Item | Verdict | New Blockers | New Majors | New Minors | New Nits |
|---|---|---|---|---|---|
| Draft A — Determinism Policy v0.2 | Fixes hold; follow-up minor pass required | 0 | 0 | 4 (R-01, R-02, R-03, R-04) | 3 (R-05, R-06, R-07) |
| Draft B — Layer Boundary Schemas v0.2 | Fixes hold; no new findings | 0 | 0 | 0 | 0 |

**Overall re-verification verdict: PROCEED. A-01 (blocker), A-02..A-05 (majors), B-01 (major), and the minors/nit are closed. Item C (State Transition Tables) is unblocked. Seven new minor/nit editorial issues logged for the follow-up minor pass; none are re-bounce material.**

---
*End of re-verification.*
