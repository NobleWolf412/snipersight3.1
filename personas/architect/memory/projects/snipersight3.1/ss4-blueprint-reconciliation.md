---
name: ss4-blueprint-reconciliation
description: New queue item — reconcile the SniperSight4 app-builder blueprint (sources/ss4_blueprint/) into the Constitution. Adopts platform/stack, delivery milestones, and design annex; resolves scope, naming, vocabulary, and token conflicts.
type: project
---

# Item I — SS4 Blueprint Reconciliation

**Source material:** `sources/ss4_blueprint/` (copied 2026-07-20 from `C:\Users\macca\Blueprints\snipersight4\`)
**Status:** Queued, architect-solo except two user rulings (I-1, I-2 below).
**Fits after:** Item D (persistence) — the blueprint's SQLite/fact-store decisions belong in the same pass. Design annex (I-6) is independent and can run anytime.

## Why this item exists

The SS4 blueprint is the same product as the SS3 Constitution, one altitude up. Its fact-store architecture (append-only facts with `market_time` / `confirmed_at` / `invalidated_at` / `algo_version`, `as_of` queries) is Constitution §4–§8 restated as implementation design — no conflict there. What it adds that the Constitution currently lacks: a platform/stack decision, a milestone plan, and a design language with tokens and a home mockup. Those get adopted. A handful of conflicts need explicit rulings first.

## Conflicts requiring user ruling

- **I-1 · Scope.** Blueprint scope is "crypto and stocks"; Constitution v0 (§18) is BTCUSDT/ETHUSDT on one venue. The mockup's scan universe shows 14 instruments including NVDA/SPY/TSLA. **Recommend:** keep §18 as the v0 gate; record stocks as a post-validation expansion in the scope constitution. Mockup universe is aspirational end-state, not v0.
- **I-2 · Naming.** SniperSight3 (constitution) vs SniperSight4 (blueprint). Pick one canonical product name so spec versions and app versions don't fork. No recommendation — user's call.

## Architect-solo adoptions (mechanism)

- **I-3 · Platform & Stack section (new constitution section).** Adopt from blueprint: React/TypeScript + TradingView lightweight-charts in a Tauri 2 shell; Python FastAPI analysis engine as a bundled local sidecar, UI talks to it only over HTTP/WebSocket; SQLite for v0 with a stated Postgres/Timescale upgrade path; read-only market-data credentials only, no order-placement credentials. Record Tauri 2 explicitly as the mobile/APK path so §16's "no mobile apps in v0" stays true without foreclosing it. Cross-ref: engine-behind-HTTP boundary must cite the layer-boundary schemas ([[layer-boundary-schemas-draft]]) as the wire contract.
- **I-4 · Delivery section (new constitution section).** Adopt M1–M4 vertical slices with their determinism gates: M1 importer + fact store + swing engine (gate: byte-identical re-runs; `as_of=T` reconstructs any past state); M2 remaining engines + chart overlay reading the same `as_of` query the strategy reads (gate: chart and bot provably agree); M3 strategy + risk authority + exec sim (gate: automated no-lookahead check on `confirmed_at` cursor); M4 validation harness (gate: two `algo_version`s coexist queryably). **Hard constraint:** M3 stays gated behind §30 closure (Item F). The blueprint does not unblock Item F.
- **I-5 · Persistence tie-in.** Blueprint's fact-store field set (`market_time`, `confirmed_at`, `invalidated_at`, `algo_version`) must reconcile with the Item D canonical schema and [[htf-level-query-shape-sketch]]. One schema, not two. Blueprint's `architecture.mmd` is a 3-node placeholder — ignore it; [[layer-boundary-schemas-draft]] is authoritative.

## I-6 · Design annex (architect-solo, independent)

The blueprint ships three design artifacts of unequal quality:

1. **`design/tokens.json` — stale, do not adopt as-is.** Single accent `#3fb8d8`, one surface level, no glow treatment. Contradicts the blueprint's own look spec (2 accents, 3 surface levels, 1 glow).
2. **`mockups/home.html` — the real token source.** Its CSS `:root` block implements the look spec correctly: base `#05080b`, three surfaces (`#0a0f14`/`#10171f`/`#161f2a`), cyan `#2fd6e8` (structure/info) + amber `#ffb547` (risk/execution), green/red semantic pair, mono numerics with `tabular-nums`, defined glow treatments (`--glow-c`, `--glow-a`). **Action:** regenerate tokens.json from home.html's variables; that becomes the canonical token set for the §19 chart-interface module.
3. **Mockup ↔ Constitution alignment.** The mockup is impressively spec-aware — footer shows append-only fact count + algo version, a NO-LOOKAHEAD CHECK status, `as_of … cursor: confirmed_at` chip on the chart, PAPER MODE pill, per-engine LEDs matching the §19 module list, session bar (ASIA/LON/NY-O/NY-PM/CLOSE), and setup cards with entry/TP/SL + plain-language WHY. Keep all of that. Fix these before it becomes a build reference:
   - **Vocabulary:** feed tabs say VALIDATED / FORMING / EXPIRED; §6 fact states are DEVELOPING / PROVISIONAL / CONFIRMED / INVALIDATED / EXPIRED / SUPERSEDED. Map FORMING→PROVISIONAL, VALIDATED→CONFIRMED, or justify a separate setup-level vocabulary distinct from fact states — but pick one and write it down.
   - **"P 78" score:** §25 forbids "an uncalibrated mystery percentage" and the ML constitution (§12) limits ML to ranking valid setups. The score chip needs a click-through to its evidence basis (the WHY line is a start, not the whole answer), or should be relabeled as a rank, not a probability, until calibration exists.
   - **Timeframes:** mockup offers 5m/15m/1H/4H/1D; §18 specifies 1W/1D/4H/1H/15m with 5m optional-dev-only. Add 1W; demote 5m.
   - **Screen identity:** the home mockup depicts the M3+ live-scanner end-state. v0's primary surface per §28 is replay + fact inspector. The mockup is the north star, not the v0 home screen — v0 needs a replay-first variant (replay transport controls, fact inspector panel) using the same chrome and tokens.
   - **§13 dashboard gaps:** human-control constitution requires visible automation status, active strategy version, and kill-switch access. Strategy version and sim-only banner are present in the footer; add explicit automation-state control (even in paper mode) to the chrome spec.

## Definition of done

Constitution gains Platform & Stack and Delivery sections sourced from the blueprint; scope/naming rulings recorded; tokens.json regenerated from home.html and stored as the design annex; mockup deviations either fixed in a v0-replay variant spec or logged as deliberate end-state items. Auditor pass over the two new sections.
