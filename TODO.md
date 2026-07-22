# SniperSight3.1 — v0 Remediation Tracker

Owner: Architect. Updated as items complete. Source of truth for queue order:
`personas/architect/memory/projects/snipersight3.1/remediation-plan-v0.1.md`

## Done
- [x] Build Session 1 (2026-07-20): `app/` — Coinbase importer (BTC-USD/ETH-USD, 15m/1H/1D native + 4H/1W aggregated), append-only fact store, swing engine v0.1-draft, chart UI at :8422, determinism gate PASS (11,119 facts, zero on re-run). Verification pack for user: `app/verification/pack-001-swings.md`
- [x] Build Session 2 (2026-07-20): structure/zone/liquidity/regime engines (all v0.1-draft), run logging (engine_runs + engine.log), knowledge graph (graphify-out/, 32 nodes), chart overlays (BOS/CHoCH, zone rails, sweeps, regime badge). Determinism PASS: 35,842 facts, full-pipeline re-run = 0 new. Journal: `app/BUILDLOG.md`
- [x] Build Session 3 (2026-07-21): user golden data → tier hierarchy (swing-v0.2: INTERMEDIATE/MAJOR), structure/zone/liq v0.2 keyed to high tiers, first A/B (structure v0.3 lost), calibrate.py scorecard 5/8 swings + 4/7 breaks matched. 1D view: 21 majors/10 breaks (was 262/116). Vendored chart lib (CDN → blank page bug), start.bat launcher.
- [x] Build Sessions 4–5 (2026-07-21): promotion evidence (swing-v0.3) → composite Major Score per user spec (v0.4–v0.7 chain, converged: 20 majors, 112k demoted, ATH kept). Determinism PASS at 123k facts.
- [x] Build Session 6 (2026-07-21): setup detector (PULLBACK playbook) — 34 validated setups, HUD card + entry/TP/SL rails in UI. Flags: CAL-5 (4H zero setups), SET-1 (no time expiry).
- [x] Build Session 7 (2026-07-21): REVERSAL playbook (CAL-5 resolved — TRANSITION had no play) + execution sim + paper track record (/api/track, footer PF/ΣR, HUD outcomes). 200 setups: PULLBACK flat, REVERSAL +147.7R fat-tail (UNVALIDATED — needs M4 walk-forward + fees per EXEC-1).
- [x] Build Session 8 (2026-07-21): M4 validation harness — exec-v0.2 with fees/slippage, validate.py cohort report. Costs flip intraday book negative (fees 3–6R on 15m tight stops); edge survives on 1D REVERSAL (PF 3.66), 4H REVERSAL (1.52), 1D PULLBACK (1.47). Next: fee-aware setup gate (S9).
- [x] Build Session 9 (2026-07-21): fee gate K=2 (30 pass/170 rejected, all intraday), validation-002 (REVERSAL PF 4.49 but tail-dependent, n=14 — verdict: forward paper only from here), replay engine (as_of cursor, no-repaint verified on screen), fact inspector (click bar → facts + evidence). v0 §29 checklist nearly closed.
- [x] Build Session 10 (2026-07-21): forward paper loop LIVE — live.py 60s poll + WinRT toast notifications (tested), start.bat launches scanner+server+chart. Forward OOS track record running from today; target 30 days per vision doc.
- [x] Build Session 11 (2026-07-21): cockpit UI — SS4 tactical-HUD identity (session bar, scan rail, engine LEDs, SETUP FEED with outcomes + click-to-jump, scanner status, /api/overview). Distinct from TradingView per user directive. + live price ticker (display-only).
- [x] Build Session 12 (2026-07-21): Risk Authority (§9, paper) — 1%/trade sizing, concurrency/exposure/leverage caps, daily-loss kill switch, DECISION facts with reasons, /api/portfolio + footer equity. Historical: 29✓/1↓/0✗, $10k → $16,486 (+64.9%, demo-grade). Next: S13 scale-in playbook.
- [x] Build Session 13 (2026-07-21): scale-in playbook — 1H adds inside active HTF setups (≥1R progress trigger, BE stop, fee-gated), exec-v0.5 + risk-v0.2 governance (half-size, PARENT_CLOSED guard). ETH 3 adds / BTC 0 (correct filtering). Flag SCALE-1: parent trail-to-BE → exec v0.6 stateful position manager.
- [x] Build Session 14/14b (2026-07-21): old-project ports — OHLC integrity validation (importer-v0.2, retro sweep clean), loud-fallback rule, price-drift monitor (⚠ FAST MOVE alerts). Fib ruled out pending forward evidence.
- [x] Build Session 15 (2026-07-21): operational hardening — watchdog (auto-restart, proven live: pid 12096→13164 in 5s), true heartbeat → UI scanner light, logon autostart INSTALLED, start.bat crash-proofed.
- [x] Build Session 16 (2026-07-21): zone strength (episodes/TESTED/WEAKENED/cluster, zone-v0.8) + FORMING/CANCELLED setups (setup-v0.5, 1-ATR proximity, 👁 toasts) + FORMING feed tab. Validated book bit-identical, equity exact. FEATURE FREEZE begins — forward record until ~2026-08-20.
- [x] Build Session 17 (2026-07-21): Nested Cycle Satellite (observational-only, freeze-compatible) — DCL/WCL detection, translation, failed/inversion flags, dual 4Y-low windows, push-out heuristic. 14 tests green (first test suite). Real read: failed left-translated weekly = textbook bear; 4Y low-to-low window opened TODAY. Zero trading-engine consumers (grep-proven).
- [x] Audit v0.1 of Constitution & v0 Spec — verdict NO-GO (6 blockers, 12 majors)
- [x] Remediation plan — queue re-sequenced dependency-first (items A–H)
- [x] Item A: Determinism Policy — v0.3 (blocker A-01, majors A-02..A-05, minors A-06..A-08, nit A-09 closed; re-verification R-01..R-07 closed)
- [x] Item B: Layer Boundary Schemas — v0.2 passed auditor re-verification (PROCEED)
- [x] Auditor re-verification pass on A+B v0.2 → PROCEED verdict
- [x] Item C: State Transition Tables — v0.1 drafted (FINDING-005 blocker closed; FINDING-007/022/024 majors/minors closed; §30 mechanism items 2/6/8/10 resolved; CR-A/CR-B filed for follow-up minor pass)
- [x] Item E: Applicability Tags — v0.1 drafted (FINDING-015 major closed)

## Queued (architect-solo, unblocked)
- [ ] Item D: Persistence & Retention spec (~2d)
- [ ] Item I: SS4 Blueprint Reconciliation — adopt Platform & Stack + Delivery (M1–M4) sections from `sources/ss4_blueprint/`; design annex I-6 (regenerate tokens.json from home.html, mockup↔constitution alignment, v0 replay-first screen variant). Run I-5 fact-store tie-in jointly with Item D. Plan: `personas/architect/memory/projects/snipersight3.1/ss4-blueprint-reconciliation.md`
- [ ] Follow-up minor pass (B-04, B-05, B-06, R-01..R-07, CR-A-1/A-2, CR-B-1..B-6)

## Blocked on user
- [ ] Item F: §30 working session — 6 methodology decisions (swing confirmation/P-SW-VIOL, protected H/L, BOS/CHoCH tier P-SB-TIER, zone flip P-ZN-FLIP, HTF influence, structural displacement θ_disp) + 2 new additions from Item C (zone creation predicates; ratification of P-SW-TIE/P-SB-LABEL/P-ZN-INVAL)
- [ ] Item I rulings: (I-1) scope — stocks in v0 or post-validation? (recommend: post-validation, keep §18 BTCUSDT/ETHUSDT gate); (I-2) canonical product name — SniperSight3 vs SniperSight4
- [ ] Item F: §30 Annex authoring (after working session, ~10–15d)
- [ ] Item G: Governance addenda (joint, ~2d)

## Endgame
- [ ] Item H: Editorial pass (Scribe, ~0.5d)
- [ ] Final re-review of A/B/C/E at §30 close, then merge
