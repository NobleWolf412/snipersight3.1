# Architect — Working State (snipersight3.1)

**Updated:** 2026-07-18

## Active goal
v0 remediation queue toward buildable spec (per `TODO.md` and `mem:remediation-plan-v0.1`). Items A/B/C/E drafted and closed against their blockers/majors; awaiting user for Item F §30 working session; Item D and minor-pass follow-ups are architect-solo when scheduled.

## Recent decisions / activity
- Items A, B, C, E drafted; auditor re-verification PROCEED on A+B v0.2.
- HTF level query shape captured as design sketch (`mem:htf-level-query-shape-sketch`) to feed Item D — surfaced from operator convo on chart/scanner symmetry.

## Open threads
- Item D (Persistence & Retention) — architect-solo, unblocked, ~2d. HTF query-shape sketch must be reconciled into it.
- Item I (SS4 Blueprint Reconciliation, `mem:ss4-blueprint-reconciliation`) — blueprint copied to `sources/ss4_blueprint/` 2026-07-20. Architect-solo except two user rulings (scope: stocks in/out of v0; naming: SS3 vs SS4). Fact-store field set must reconcile with Item D — run them together. Design annex (I-6) independent: regenerate tokens.json from home.html, fix mockup vocabulary/score/timeframes, spec a v0 replay-first screen variant.
- Follow-up minor pass — B-04/05/06, R-01..R-07, CR-A-1/2, CR-B-1..6.
- Item F blocked on user — 6 §30 methodology decisions + 2 additions from Item C (zone creation predicates; ratification of P-SW-TIE / P-SB-LABEL / P-ZN-INVAL).

## Build track (started 2026-07-20, runs parallel to spec track)
- Venue ruling: **Coinbase** primary (user is US, Binance geoblocked); Kraken designed-in second source. Instruments now BTC-USD/ETH-USD (fold into Item I).
- Approach ratified by user: build on versioned §30 defaults (`swing-v0.1-draft` etc.), calibrate via verification packs against user's TradingView reads.
- Session 1 DONE: `app/` in-workspace (monorepo for now) — importer/aggregator/fact store/swing engine/FastAPI server (:8422)/chart UI. Determinism gate PASS. Gaps logged, never fabricated.
- **Calibration flag:** ~90% of micro swings promote to LOCAL — 0.75 ATR reversal-to-next-opposite-swing barely filters. Await user's pack-001 marks before changing.
- Known draft caveat: fractal neighbors are index-adjacent, not time-adjacent — a candle gap makes neighbors span the gap. Gap counts are tiny (10 candles); revisit if user marks errors near gap dates.
- Session 2 DONE (user directive: build-first, log-as-you-go, verify at end): structure/zone/liquidity/regime engines all v0.1-draft; run logging via `engine_runs` table + `data/engine.log`; knowledge graph `graphify-out/graph.json` (keep updated on module/contract changes); BUILDLOG.md is the append-only build journal. 35,842 facts, full-pipeline determinism PASS.
- Cascade flags (BUILDLOG CAL-1/2/3): noisy local swings (0.75 ATR) → flappy regimes (76 changes/180d on 4H) and dense breaks. One root cause; fix at swing calibration, everything downstream re-measures.
- User's verification style: batch formal tests/verification at END of build; inline determinism re-runs stay.
- Awaiting user: marked-up `app/verification/pack-001-swings.md` (now doubly important — swing calibration unblocks CAL-2/3).

- S3 DONE (2026-07-21): user golden data received (swings.docx → `app/verification/golden-btc-1d.json`). Tier hierarchy shipped: swing-v0.2 (INTERMEDIATE/MAJOR via swings-of-swings recursion), structure/zone/liq rewired to high tiers. A/B ran (structure v0.3 lost, v0.2 won — recorded in BUILDLOG S3). Scorecard: 5/8 swings, 4/7 breaks matched; misses explained. Chart now 21 majors/10 breaks on 1D (was 262/116). CAL-1/2/3 closed; CAV-2 opened (alternate() replacement chains need live-mode confirmed_at audit before replay).
- pack-001 (md checklist) OBSOLETE — superseded by golden-data flow + calibrate.py. User feedback channel is now: adjust golden-btc-1d.json or say it in chat.

- S4 DONE (2026-07-21): user endorsed calibration (swing2.docx). swing-v0.3 ships promotion evidence (margin_pct / reversal_atr / held_candles / vol_ratio) on every INTERMEDIATE/MAJOR fact — recorded, not filtered (§22). Inspection table of 21 majors delivered (`app/verification/major-inspection-btc-1d.md`).

- S5 DONE (2026-07-21): composite Major Score per user's answer.docx spec (weights: reversal 24 > impact 26 > margin 18 > held 14 > dominance 12 > vol 12 log-scaled > liq 8; MAJOR ≥55). Version chain v0.4 (dud) → v0.5 (dud) → v0.6 → v0.7 (converged) — all recorded in BUILDLOG S5. User verdicts encoded: 112k demoted, ATH kept. 20 majors on BTC 1D. Server on v0.7, 123,151 facts. CAV-3 (as-of-now evidence accrual), CAV-4 (float log2 in vol scoring) opened; graph.json update deferred to S6.

- S6 DONE (2026-07-21): setup detector shipped (setup-v0.1-draft, PULLBACK playbook) — 34 validated setups all-history, HUD card + ENTRY/TP/SL rails live in UI. Original product loop closed (exchange → structure → plotted entries). Graph updated. Flags: CAL-5 (4H zero setups — gate diagnosis), SET-1 (no time expiry §11), CAV-4 still open.

- S7 DONE (2026-07-21): CAL-5 diagnosed (TRANSITION had no playbook, rest were correct rejections) → setup-v0.2 adds REVERSAL playbook + WEAKENING_* continuations (200 setups, 4H unblocked). execsim (exec-v0.1) paper-trades everything: PULLBACK flat (+0.9R/52), REVERSAL fat-tail (+147.7R/148, avg winner ~10R, all SL exactly -1R, top winners verified real). /api/track + footer PAPER stats + HUD outcome live. SET-1 resolved (TIMEOUT). NEW: EXEC-1 (no fees/slippage — §14 gap). Determinism PASS at 123,801 facts.

- S8 DONE (2026-07-21): M4 validation harness. exec-v0.2 models costs (0.25%/side + 0.05 ATR slip on market exits); validate.py emits cohort report (`app/verification/validation-001.md`). VERDICT: costs flip the book negative overall (REVERSAL +147.7R gross → −108.9R net) because tight stops make fees huge in R terms on 15m/1H (3–6R round-trip). Survivors: 1D REVERSAL PF 3.66, 4H REVERSAL PF 1.52, 1D PULLBACK PF 1.47. Edge lives on HTFs. EXEC-1 closed.

- S9 DONE (2026-07-21): fee gate K=2 (v0.3 K=4 was a recorded dud — over-rejection), 30 setups pass / 170 cost-rejected. validation-002: REVERSAL PF 4.49 but tail-dependent (minus-top-3 negative) and n=14 — historical well is DRY, further tuning = curve fitting. Replay engine (as_of cursor, verified no-repaint) + fact inspector (click bar → all facts + evidence) shipped; §29 checklist mostly ✓ (multi-TF sync view and zone FLIP outstanding).

- S10 DONE (2026-07-21): forward paper loop live — live.py (60s poll, closed-candles-only, idempotent cycles, 3.7s full pipeline) + notify.py (WinRT toast, tested on user's desktop) + start.bat launches scanner+server+chart. Forward OOS track record starts now; user's bar = ~30 days of logged signals.

- S11 DONE (2026-07-21): cockpit UI — full SS4 tactical-HUD rebuild (session bar, scan-universe rail, engine LEDs, SETUP FEED right rail w/ ACTIVE/EXPIRED/CLOSED + click-to-jump, scanner status footer, /api/overview). Answers "where do I see setups" with one glance.

- S12 DONE (2026-07-21): Risk Authority (risk-v0.1-draft) — §9 realized on paper. $10k account, 1%/trade, 2-concurrent / 2%-total-risk / 3x-leverage caps, daily -3% kill switch; DECISION facts with reasons; /api/portfolio + footer EQUITY. Historical: 29✓ 1↓ 0✗, equity +64.9% (accounting demo, same n=30 caveats). Determinism PASS.

- S13 DONE (2026-07-21): scale-in playbook (scale-v0.1-draft) — 1H BOS adds inside active 1D/4H setups, ≥1R-progress trigger, SL at parent entry, fee-gated, max 2/parent. exec-v0.5 (both setup sources, double pass), risk-v0.2 (adds half-size, concurrency-exempt, PARENT_CLOSED guard). Results: BTC 0 adds (trigger filtering), ETH 3 adds (−1.10R contained, +1.21R and +0.23R open-flavored TIMEOUTs). Equity $16,499.59. SCALE-1 flag: parent trail-to-BE needs stateful position manager (exec v0.6). Draft answer to §30 item 9 recorded.

- S14 DONE (2026-07-21): old-project review + ports — OHLC integrity validation (importer-v0.2, n_bad column, retro sweep clean: 20,532 candles 0 malformed) and loud-fallback rule (toast failure + execsim missing-ATR now audible). Not ported: candle fabrication, float math, TTL cache. Filed for scale-up: parallel fetch pattern. Old project path: C:\Users\macca\snipersight-trading (has more modules — telemetry/, bot/, adapters — unreviewed).
- S14b DONE: price-drift monitor in live loop (drift-v0.1) — ⚠ FAST MOVE toast + alert fact when spot drifts ≥3% from last closed 15m candle; once per symbol per bucket; awareness-only (§5 intact). Tested both paths.

- S15 DONE (2026-07-21): operational hardening — watchdog.py (auto-restart w/ backoff, restart toasts, single-instance lock, external-server aware), true heartbeat (live.py → heartbeat.json every poll → UI footer light), install_autostart.py (Startup .vbs, INSTALLED on user machine), start.bat routes through watchdog. Crash test passed live: killed scanner pid 12096 → auto-restarted as 13164 in 5s. Fib ruled OUT (user accepted recommendation; reopen only on forward-data evidence).

- S16 DONE (2026-07-21): zone-v0.8 (episodes, TESTED/WEAKENED, cluster, strength evidence) + setup-v0.5 FORMING/CANCELLED states (1-ATR proximity, 4H/1D/1W, same gates, 👁 toasts) + FORMING feed tab. Validated book bit-identical through the change (equity $16,499.59 exact). 31 historical FORMING / 7 CANCELLED. exec-v0.6/risk-v0.3. Watchdog takeover path proven live.

- S18 DONE (2026-07-21): risk envelope 1%→2%/trade (user directive, freeze exception, versioned risk-v0.4) — coherent re-tune: 4% total cap, 6% daily halt, 1% scale add. Historical $10k→$24,203 (+142%, return+drawdown both ~2x). UI: per-card risk line ($/units/leverage/decision) + footer account strip (next risk $ + envelope). Forward record uses 2% from here.

- S19 DONE (2026-07-21): dynamic universe (universe-v0.1) — live volume-ranked top-20 Coinbase USD pairs, $3M floor + 200-daily-candle history gate, selection recorded as facts, hourly refresh + auto-onboard, stablecoin exclusion. Rewired risk/server/live off hardcoded BTC/ETH. Fixed portfolio equity double-derivation (authoritative `account` SUMMARY fact, deterministic anchor). **CRITICAL FINDING: broadening to 19 symbols collapsed the book +142%→−68.3% (75.7% maxDD, 13 kill days). The edge does NOT generalize past BTC/ETH — symbol-specific/small-sample.** Live trading must stay gated to where forward evidence supports.

## FEATURE FREEZE (from 2026-07-21)
No new trade logic until forward record ~30 days (target ~2026-08-20). Allowed: Tauri packaging, Telegram alerts, §30 session, Item I rulings, bugfixes. Weekly check: /api/track + /api/portfolio + engine.log. Scanner autostarts at logon (Startup .vbs installed).

- S17 DONE (2026-07-21): Nested Cycle Satellite (cycles-v0.1-draft, observational-only, freeze-compatible — grep-proven zero consumers). 14 synthetic tests all green (first formal test suite). Real read: 21 DCLs/7 WCLs since 2022-11 seed; last weekly cycles right 0.93 → right 0.64 → LEFT 0.17 FAILED; 4Y windows low-to-low 2026-07-21→2027-03-21 (opened today) & halving-est 2026-10-15→2027-04-15; push-out NOT active (latest weekly is left/failed — divergence from user's thesis surfaced, not resolved). /api/cycles + rail panel + chart markers. Queued decision: whether cycle features ever join setup evidence = §8-style validated promotion, explicitly not built.

## Single next step
Nothing build-critical — let the record accumulate. On user request during freeze: Tauri or Telegram. On user return with rulings: §30 session (now trivially concrete — every rule runs live on the chart).

## In flight — 2026-07-24 War Room follow-up
- War Room idea #5 ("Complete FORMING → armed order") — plan APPROVED (`mem:forming-armed-order-plan`, Phases A–K). Grounding memo corrects the pitch: FORMING already carries entry/sl/tp/rr; missed-limit accounting already ships; real delta is `size` + `expiry_bar_count` + VALIDATED-inherits-FORMING.
- **Rulings (2026-07-24):** freeze exception GRANTED (one-off, forward clock not reset); sizing seam A chosen (extract pure `risk.size_order`, §9 preserved).
- Handed off to Coder — Phase D (schema-only) → Phase K (Auditor review). Handoff packet in the plan note (files in play, contracts, bit-identity acceptance, expected replay diff, non-scope).
