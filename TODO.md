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
- [x] Item D: Persistence & Retention — `docs/SPEC-persistence-retention.md`.
      Measured (1.4 GB, 38.1% superseded), policy written, deletion
      deliberately NOT implemented. Cheap wins done and found nothing.
- [~] Item I: design annex I-6 **superseded** by the shipped five-surface
      shell, design system and Learn surface. Remaining: the two user rulings.
      Original: SS4 Blueprint Reconciliation — adopt Platform & Stack + Delivery (M1–M4) sections from `sources/ss4_blueprint/`; design annex I-6 (regenerate tokens.json from home.html, mockup↔constitution alignment, v0 replay-first screen variant). Run I-5 fact-store tie-in jointly with Item D. Plan: `personas/architect/memory/projects/snipersight3.1/ss4-blueprint-reconciliation.md`
- [ ] Follow-up minor pass (B-04, B-05, B-06, R-01..R-07, CR-A-1/A-2, CR-B-1..B-6)

## Blocked on user
- [~] Item F: §30 — **3 of 6 answered by measurement** (swing confirmation,
      BOS/CHoCH tier, HTF influence — see the S43 reconciliation). Remaining:
      protected high/low, zone flip (P-ZN-FLIP), structural displacement.
      Original item text: 6 methodology decisions (swing confirmation/P-SW-VIOL, protected H/L, BOS/CHoCH tier P-SB-TIER, zone flip P-ZN-FLIP, HTF influence, structural displacement θ_disp) + 2 new additions from Item C (zone creation predicates; ratification of P-SW-TIE/P-SB-LABEL/P-ZN-INVAL)
- [ ] Item I rulings: (I-1) scope — stocks in v0 or post-validation? (recommend: post-validation, keep §18 BTCUSDT/ETHUSDT gate); (I-2) canonical product name — SniperSight3 vs SniperSight4
- [ ] Item F: §30 Annex authoring (after working session, ~10–15d)
- [ ] Item G: Governance addenda (joint, ~2d)

## Endgame
- [ ] Item H: Editorial pass (Scribe, ~0.5d)
- [ ] Final re-review of A/B/C/E at §30 close, then merge

---

# Active tracker — S41 completion pass (2026-07-30)

Source of truth: `docs/PROGRAM-PLAN.md` + `docs/SALVAGE-from-snipersight-trading.md`.
Legend: `[ ]` open · `[~]` in progress · `[x]` done · `[-]` **closed by evidence**
(measured, deliberately NOT built — the reason is the deliverable)

## A — Correctness debt (blocking; affects live behaviour)
- [x] A1 `risk.py`->v0.8, `scalein.py`->v0.3. Both import `SETUP_VERSION`/`EXEC_VERSION`
      which S40 bumped, so their FACTS changed while their TAGS did not. This is the
      S37 collision reproducing, self-inflicted.
- [x] A2 Wire `ranges.py` into `live.ENGINES` — built, tested, and never run.
- [x] A3 Scanner restarted and verified on current code. The rc=1 crash loop was
      the watchdog respawning a process that imports `engine/*.py` WHILE those
      files were being rewritten by concurrent sessions — not a code defect, but
      a real hazard: the watchdog turns a transient half-written module into a
      tight restart loop. Live store now carries setup-v0.9 / exec-v0.10.
- [x] A4 Duplicate background tasks (execsim bump, tick fix) — both already done
      and superseded; re-applying could regress versions.

## B — Live-trading gap (SPEC §1.7, never built)
- [x] B1 Cooldown manager. Nothing stops re-entering a level that just stopped you
      out. Asymmetric: long after a stop-out (level invalidated), short after a
      target (resolved, not failed). Matters far more now REVERSAL fires 471x.

## C — Measurement completeness
- [x] C1 Confound guard in `edgestats` (SALVAGE 1.3). Six versions moved in S40 and
      the re-measurement was done by hand.
- [x] C2 Adaptive time stop graded ALONE (SALVAGE 2.1/2.4). Rejected as part of a
      bundle; never tested on its own merits.

## D — Confluence candidates: recorded, gating nothing
- [x] D1 Premium/discount (SALVAGE 3.4)
- [x] D2 HTF composite (SALVAGE 3.2) — redundancy measured at r=0.93, never collapsed
- [x] D3 VETO pattern (SALVAGE 3.1) — gates are not weights
- [x] D4 `participation_rate` (SALVAGE 3.6) — no size-vs-book gate exists anywhere
- [-] D5 Sessions / kill zones — **closed with cause**: crypto perps trade 24/7
      and the concept earns its keep at the equities/forex boundary (Wave 4).
      Adding an ungraded factor to a book that cannot test it is the failure
      mode this project keeps documenting.

## E — The 1W blind spot
- [x] E1 The 1D book cannot have an HTF regime at all. The only factor that ever
      cleared the noise floor is unmeasurable on the best-performing timeframe.

## F — Strategy plurality (Wave 2)
- [x] F1 Strategy registry
- [-] F2 Range fade — **closed by evidence**: 3 of the RANGE rejections had a live
      range; ZERO on structure-sound symbols. `ranges.py` kept as the proof.
- [x] F3 Indicator engines (`ma`, `momentum`, `volatility`, `volume`). All four
      emit on STATE CHANGE, not per bar, with Schmitt-trigger thresholds; 436k
      facts total, each under the 200k ceiling. Wired into `live.ENGINES` —
      25s added to a cycle over the admitted set, verified idempotent across
      two consecutive passes. Nothing consumes them and nothing may until
      `factorstats` grades them.
- [~] F4 **Breakout-retest BUILT, GRADED, REFUSED** — n=55, -0.076 R, CI
      [-0.545, +0.426]. Emits facts, trades nothing, re-gradeable as sample
      grows. Remaining: compression->expansion (volatility engine now exists,
      so unblocked); sweep-reversal still blocked by 98 SWEEP facts total.
      **Gated on F3** (compression needs the volatility engine) and, for the
      sweep scalp, on sweep scarcity — 98 SWEEP facts exist in the entire
      store, which is what made the old REVERSAL gate a lottery ticket.
      Breakout-retest is buildable from structure facts today and is the one
      to start with; it must clear `abtest` before it ships, like REVERSAL did.

## G — Recorded, not in this pass
- [ ] Kraken perp adapter · position manager + shadow mode · Alpaca · auto mode ·
      Schwab + options expression layer
- [ ] **Forward confirmation of REVERSAL.** The CI clears zero on REPLAYED history
      only. A waiting item, not a building item.

---

# Reconciliation — S43 (2026-07-30)

Every open item from earlier sessions, checked against the code as it stands.
The spec track (Items D–I) ran in parallel with the build for weeks; several of
its open questions have since been **answered by measurement** rather than by a
working session, and saying so is more useful than leaving them queued.

## Answered empirically by the build — close, do not schedule

| Item | Was | Now |
|---|---|---|
| §30-1 swing confirmation / P-SW-VIOL | awaiting ruling | `swing-v0.8` composite Major Score, calibrated against the user's golden data (S3–S5). Shipped and in use |
| §30-3 BOS/CHoCH tier (P-SB-TIER) | awaiting ruling | Settled twice by A/B: 1D=MAJOR **won** against INTERMEDIATE (S3); 1W=INTERMEDIATE adopted S41 with a measured cause — 194 weekly bars yield 14 MAJOR pivots across 11 symbols, which cannot form a sequence |
| §30-5 HTF influence | awaiting ruling | Measured S41: TRENDING **+0.258 R** / FLAT **−0.108 R** / UNKNOWN **−0.244 R**, n=198/380/45. A 0.37 R/trade spread. Recorded, gating nothing until `factorstats` grades it |
| Item I-6 design annex (tokens, mockups, replay screen) | queued | Superseded — the five-surface shell, design system and Learn surface shipped (S35–S42). `docs/DESIGN-SYSTEM.md` is the live token source |

## Still genuinely open — spec/documentation debt, not build debt

- **§30-2 protected high/low**, **§30-4 zone flip (P-ZN-FLIP)**, **§30-6
  structural displacement θ_disp** — three of the original six. `zones.py` still
  carries `FLIP still deferred`. None block the current book.
- **Item D — Persistence & Retention spec.** The store has run append-only for
  weeks at 992k facts with no retention policy written down. Not urgent; it
  becomes urgent the first time the store needs pruning, and by then the policy
  should predate the need.
- **Items G / H / final re-review** — governance addenda and editorial pass.
  Documentation-track, unblocked, no code dependency.
- **Item I rulings (user):** (I-1) stocks in v0 or post-validation?
  (I-2) canonical name SS3 vs SS4. Both still unanswered; (I-1) is effectively
  decided in practice — the build went crypto-perps-only.

## Actionable now — approved, unblocked, coder-owned

**`forming-armed-order-plan.md` Phases E→K.** Both user rulings are already in
(freeze exception GRANTED; sizing seam = **A**, extract a pure
`risk.size_order`). Phase B (memo) and Phase D (payload scaffolding) are done —
the fields exist on every FORMING/VALIDATED fact and are all `None`.

The point of the remaining phases: **no runtime decision at execution.** Today
VALIDATED recomputes entry/SL/TP at touch time; the plan makes it INHERIT the
armed order that FORMING already computed, so what gets executed is provably
what was decided when the setup was armed.

- [x] **E** — extract pure `risk.size_order(...)`, call it at FORMING emission
- [x] **F** — VALIDATED inherits FORMING verbatim by `setup_id` (4H/1D/1W only;
      LTF has no FORMING by design)
- [x] **G** — `execsim` places the armed order verbatim; `forming_id` propagates
- [x] **H** — MISSED-limit lineage + a missed-by-armed-window column
- [x] **I** — the five acceptance tests named in the plan
- [x] **J** — determinism + replay diff, documented in BUILDLOG
- [~] **K** — substantive review done against the plan's criteria (inheritance
      proven, 0 bracket mismatches; `forming_id` present on order/exec/MISSED;
      replay diff explained in BUILDLOG S43). Formal **Auditor-persona sign-off
      is a separate seat** and remains outstanding — that is a role action, not
      a code task.

## Redesign-plan phases (checked S45)

- [x] Phase 1 Foundation · [x] Phase 2 COMMAND+CHART · [x] Phase 3 Settings+venue seam
- [x] **Phase 4 Perps** — adapter, shorts, leverage, liquidation gate all S32–S34;
      **funding costs closed S45** (defined in S32, zero callers for eight sessions)
- [~] Phase 5 AUTO + guardrails — drawdown/data-health halts and the settings
      switches exist; arm/disarm, session timer and HALT ALL do not
- [x] Phase 6 Diagnostics + Results — funnel, tracer, wizard, edge stats, Learn
- [ ] **Locked:** live submission. `/api/trade-config` still serves
      `live_enabled: false`; correct until forward evidence earns it

### Phase 4 leftovers that are the operator's, not the code's
- [ ] **Phemex US-residency** (redesign-plan open question #1). Unanswered since
      2026-07-28 and the entire traded universe is Phemex. Kraken now runs
      CFTC-regulated US perps, which is the ready-made answer if the access is
      a problem.
- [x] **Margin mode: isolated or cross?** (question #2). **ANSWERED 2026-07-30
      (S46): ISOLATED**, and now declared rather than implied —
      `venues.Venue.margin_mode` carries it and `liquidation_price` REFUSES to
      price cross rather than returning the isolated number under a cross label.
      The reason is the ruling: under cross, every position is backed by the
      whole account, so "2% per trade" stops meaning what it says. The 0.5%
      maintenance allowance is now `venues.MAINTENANCE_MARGIN`, served to the
      order ticket over `/api/trade-config` so the UI cannot hold a second copy.

---

## S50 — needs an operator ruling

- [ ] **The STRENGTH evidence component can never be false.** Minimum possible
      zone strength is 77 against a gate of 60, so it fires on 100% of zones and
      appears in 985 of 985 REVERSAL setups. REVERSAL's "2-of-4 evidence" is
      really 1-of-3 plus a free point; 81.3% of its setups were admitted on a
      single real piece of evidence. **But tightening it looks wrong:** 2+ real
      evidence returns +0.020 R (n=63) against +0.191 R for 1 real evidence
      (n=214). Options: leave it degenerate and stop calling it evidence; retune
      REVERSAL_MIN_ZONE_STRENGTH so it can fail; or drop STRENGTH from the
      component set and lower REVERSAL_MIN_EVIDENCE to 1. Third option matches
      what the engine already does in practice.
- [ ] **Baseline reset.** zone-v0.11 / setup-v0.12 / exec-v0.15 change every
      recorded number. The forward track record starts over. Recommend yes — what
      it was recording was measurably wrong.

### S50 fixed
Cross-fill fabrication (execsim booked market fills at prices the bar never
traded, 78 of 95 crossed orders, never adversely — book restated +95.85 R ->
+31.95 R); the zones.py creation-time lookahead; and `exec-v0.14`, which I
poisoned by re-simulating before the setup bump and replaced with `exec-v0.15`.

## S49 audit findings — open

Fixed in S49 and closed: the Results-page field mismatch, shadow venue in the
track record and edge stats, funding stripped from the edgestats verdict, the
three-copy engine roster (`cooldowns` was scheduled by nothing), and the single
BLOCKED symbol that aborted 38% of all cycles including `risk.run`.

### Confirmed, measured, not yet fixed
- [ ] **Funding is one constant across venues whose settlement schedules differ
      8×.** Phemex 3/day, Kraken 24/day, both charged
      `FUNDING_RATE_PER_SETTLEMENT = 0.0001`. Measured: Kraken 0.0100%/h vs
      Phemex 0.00125%/h — the 8× is purely the constant. Also two constants for
      one quantity (`execsim.FUNDING_RATE_PER_SETTLEMENT`,
      `costs.DEFAULT_FUNDING_RATE`), neither reading the other.
- [~] **`scalein.py` missed the venue-cost migration** — 5 adds at `scale-v0.7`
      store-wide. **Venue half FIXED 2026-07-30 (S52, `scale-v0.11`)**: the
      add's economics gate now prices on the add's own venue via
      `costs.profile_for(symbol)`, instead of a Coinbase default ~14× the fees a
      perp charges. **Funding half STILL OPEN**: `funding` appears nowhere in
      `scalein.py`, so an add held across settlements is still priced as though
      it pays none.
- [~] **`ticket-math.js` is a second authority for position size** and diverges
      from `risk.size_order` in the permissive direction every time: un-reduced
      size where the engine reduces for leverage, no `open_risk` parameter, and
      no min-notional / participation cap. Its fee figure omits slippage and
      funding — funding alone is 49.1% of modelled cost.
      `/api/trade-config` does not expose `MAX_PARTICIPATION`, so the UI
      *cannot* replicate the engine today.
      **Liquidation gate CLOSED 2026-07-31**: the ticket now computes
      liquidation and REFUSES to arm a stop sitting beyond it, matching
      `venues.stop_survives_liquidation`. Note this also *added* a second
      implementation of an engine formula — the mitigation is that every
      liquidation figure in `test_ticket_math.js` was computed by the Python and
      both constants arrive over `/api/trade-config`, so the constants cannot
      drift even though the code is duplicated. That is a mitigation, not an
      exemption; the rest of this item stands.
- [ ] **`risk.run()` does not call `size_order()`** — the armed order is sized by
      an inline reimplementation on `START_EQUITY` (10,000 vs a live 9,772) with
      no `open_risk`. All 220 armed orders read `APPROVED / WITHIN_LIMITS`.
- [ ] **`chart.js`**: renders a stale chart + full order ticket after a failed
      load; freezes equity for the page lifetime while `shell.js` refreshes it
      every 30s.
- [ ] **`/api/overview` 34.5s over HTTP** vs 0.65s in-process. De-N+1'd with no
      effect. GIL/background-audit hypothesis unconfirmed.

### Suspected — reasoned, not measured
- [ ] Two BEHAVIOURAL settings with **zero consumers** that reset the forward
      baseline when toggled: `strategy_breakout_retest`, `strategy_range_fade`.
      Toggling either destroys the track record and changes no behaviour.
- [ ] No lot/tick rounding on order size, and `MIN_NOTIONAL_USD = 1` against a
      measured Phemex BTC floor of ~$59.67. We size positions the venue rejects.

### From the second-pass salvage
- [ ] **The participation cap's refutation was not salvaged with the cap.** 24h
      volume ≠ book depth (their witness: NEAR, $5M/24h, ~$2 at the touch). Keep
      the volume cap as a pre-filter; the real gate is depth-at-touch. Cost is
      real — no venue adapter here reads an order book at all.
- [ ] **Premium/discount inverts in trends** (n=123: favoured −4.42 avg,
      opposed-with-aligned-BOS +1.71). If it ships it must be conditioned on
      structure.
- [ ] **Stuck-value cardinality audit** — a recorded field with cardinality 1
      across N facts is dead, defaulted or broken. A `GROUP BY` over the fact
      store; `quality.py` audits structure and has no field-variance check.
      Cheapest item on this list.
- [ ] **Reachability probes** — feed each gate the input that MUST trip it and
      assert it did something. `engine/diagnostics.py` declares 10 rejection
      codes, so the work is bounded. `risk.py:348-355` fails open twice and
      silently today (missing key → permitted; exception → permitted, no log).
- [ ] **Phemex venue facts**: ccxt's `limits.amount.min` is empty — the real
      floor is `max(minOrderValueRv, precision × contractSize × price)`; lot
      sizes must FLOOR not round; Ep price scale is per-contract and a magnitude
      heuristic silently inflates sub-$0.01 coins 1e8× *through* OHLC validation.
- [ ] **A refuted-hypothesis register.** The retired project's `decisions/` kept
      a permanent REFUTED section; BUILDLOG has no equivalent, so nothing stops
      a dead idea being re-litigated.
