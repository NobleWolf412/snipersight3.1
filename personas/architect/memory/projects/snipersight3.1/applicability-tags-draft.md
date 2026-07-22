---
name: SniperSight3 Applicability Tags — Draft (Remediation Item E)
description: Per-section v0/v0-partial/v1+ tags for the Constitution (§1–§16). Addresses FINDING-015 (MAJOR). Short standalone insert; can be placed as a header table in the Constitution document or as a named appendix.
type: project
---

# Applicability Tags — Draft Appendix AT

**Status:** Architect draft **v0.1**, 2026-07-17.
**Addresses:** FINDING-015 (MAJOR — constitution/v0 sections unmarked).
**Scope:** Constitutional sections §1–§16 only. Spec sections §17–§31 are v0 by definition (they are the v0 spec). The tags below answer: which constitutional rules must be *implemented* in v0, which require partial implementation, and which are v1+ only.

Tag definitions:
- **v0** — must be implemented before §29 acceptance. Absence is a blocker.
- **v0-partial** — a subset is required for v0; the remainder is scaffolded or documented but not built.
- **v1+** — constitutional rule applies eventually but no v0 implementation required; note what scaffolding (if any) v0 must provide so v1 is not a rip-and-replace.

---

## AT1. Section applicability table

| § | Title | Tag | v0 scope | v1+ note |
|---|---|---|---|---|
| 1 | Purpose | v0 | Read-only governance; no implementation. Must be cited in the §29 sign-off checklist as the authority it enforces. | — |
| 2 | Product Identity | v0 | Read-only governance; the "is not" list is the v0 scope fence. | — |
| 3 | Core Operating Layers | v0 | All five layers exist in v0. Layers 3–5 exist as scaffolding stubs only per §16, but the **boundary contracts** (Draft B schemas S1–S6) are v0. No component may skip layers. | — |
| 4 | Determinism Principle | v0 | The whole section is normative for v0 Layer-1/2. Draft A (§4.1) is the implementation doc. ML seed/version discipline applies to any v0 research run under §14. | — |
| 5 | Causality and Look-Ahead Prevention | v0 | All of §5 applies to v0 Layer-2: PROVISIONAL/CONFIRMED labeling, market-time vs confirmation-time recording, no future-data display in replay. | — |
| 6 | Provisional and Confirmed Information | v0 | The six-state enum is v0. Appendix ST binds states to entities. DEVELOPING is v0-defined but not persisted (v0 bar-close event clock). | — |
| 7 | Versioning Constitution | v0-partial | **v0 required:** `algo_version` and `policy_version` stamps on every fact; immutability once used in a backtest (append-only registry, Draft A §D6). **v1+:** strategy logic, risk rules, sizing, execution simulation, fees/slippage versioning — none exist in v0. v0 must provide an extensible registry schema so v1 adds version types without migration. |  |
| 8 | Auditability Constitution | v0-partial | **v0 required:** Q1 (market data available), Q2 (market facts), Q3 (algorithm version). These are the audit-store questions answerable in v0. **v1+:** Q4–Q10 (strategy, intent, risk, orders, fills, management, close). v0 must provision the audit store with a schema that Q4–Q10 can extend without a rip-and-replace. | Item D (Persistence) owns the audit-store schema. |
| 9 | Risk Constitution | v1+ | Zero v0 implementation (§16 excludes live execution and risk). **v0 scaffolding required:** `RiskVerdict` stub schema (Draft B §S6) so Layer 3→4 boundary is versioned from day one. | — |
| 10 | Execution Constitution | v1+ | Zero v0 implementation (§16). No v0 scaffolding needed beyond Layer 4→5 boundary stub. | — |
| 11 | Strategy Constitution | v1+ | Zero v0 implementation. **v0 scaffolding required:** `TradeIntent` stub schema (Draft B §S5) and Layer 3→4 contract, so strategy development in v1 lands on a defined seam. | — |
| 12 | Machine-Learning Constitution | v1+ | Zero v0 implementation. **v0 note:** §4 Determinism Principle already mandates seed/version recording for any v0 research run that uses ML (§14); that is covered under §4/§7/§14, not here. | — |
| 13 | Human-Control Constitution | v0-partial | **v0 required:** dashboard shows automation status (off in v0), fact inspector (§19), replay controls. Kill-switch and disable-all apply to replay only. **v1+:** live automation controls, position display, order cancellation. | — |
| 14 | Research Constitution | v0-partial | **v0 required:** every research run records algo version, instruments, period, data source/version, parameters, software commit, run timestamp, and results are immutable. **v1+:** fees, funding, live fills, risk rules in the run record. | — |
| 15 | Performance-Reporting Constitution | v1+ | No live or paper trades in v0; no performance metrics to report. **v0 note:** golden-chart comparison reports (§29(10)) are a precursor and are v0, but they live under §27/§29, not §15. | — |
| 16 | Scope Constitution | v0 | The exclusion list is hard-normative for v0. Cite verbatim in the §29 sign-off checklist as a negative-scope check. | — |

---

## AT2. Summary counts

| Tag | Sections |
|---|---|
| v0 | §1, §2, §3, §4, §5, §6, §16 (7 sections) |
| v0-partial | §7, §8, §13, §14 (4 sections) |
| v1+ | §9, §10, §11, §12, §15 (5 sections) |

**v0-partial scaffolding obligations (all owned by Item D — Persistence, unless noted):**
- §7: extensible version-registry schema
- §8: audit-store schema with Q4–Q10 extension slots
- §11: `TradeIntent` stub (Draft B §S5 — already done)
- §9: `RiskVerdict` stub (Draft B §S6 — already done)

---

## Open items

None. This section is self-contained. Tags require user ratification at §29 sign-off only.
