# SniperSight — Build Log

Append-only. Newest entry last. Every session records: what was built, decisions
made (with the "why"), open flags, and the determinism check result. When
debugging, read this + `SELECT * FROM engine_runs ORDER BY id DESC` +
`data/engine.log` before reading code.

---

## S1 — 2026-07-20 — Data spine + swing engine + chart

**Built:** `engine/store.py` (SQLite fact store: candles / facts / import_log),
`engine/importer.py` (Coinbase public REST, 15m/1H/1D native), `engine/aggregator.py`
(4H from 1H, 1W from 1D), `engine/swings.py` (micro fractal + local 0.75 ATR,
Wilder ATR14), `server.py` (FastAPI :8422), `static/index.html` (lightweight-charts
UI), `backfill.py`, `verify_pack.py`.

**Decisions:**
- Venue = Coinbase (user is US; Binance geoblocked). Instruments BTC-USD, ETH-USD.
- Prices are TEXT end-to-end; JSON parsed with `parse_float=Decimal`; all math
  Decimal, quantized q8. No float touches a price.
- Facts append-only, idempotent via `INSERT OR IGNORE` on content_hash =
  sha256(symbol|tf|kind|market_time|algo_version|canonical_payload).
- Developing candles never imported; developing agg buckets never emitted (§5).
- 4H/1W buckets require ALL source bars (no fabrication over gaps).
- Swing ties (equal highs in fractal window) produce NO swing — P-SW-TIE draft.

**Flags:**
- CAL-1: ~90% of micro swings promote to LOCAL (0.75 ATR too loose on crypto).
  Verification pack-001 sent to user; awaiting marks.
- CAV-1: fractal neighbors are index-adjacent, not time-adjacent — a candle gap
  makes neighbors span it. 10 gap candles total logged; revisit only if user
  marks errors near gap dates.

**Determinism:** PASS (11,119 facts; re-run = 0 new).

**Bug fixed:** ResizeObserver callback called fitContent()/resize() unconditionally
→ infinite relayout loop → renderer hang. Now applyOptions with contentRect only.

---

## S2 — 2026-07-20 — Structure/zone/liquidity/regime engines + run logging + graph

**Built:** `engine/runlog.py` (engine_runs table + data/engine.log — every engine
invocation recorded: inputs, new facts, duration), `engine/structure.py`
(HH/HL/LH/LL labels + BOS/CHoCH), `engine/zones.py` (supply/demand, FRESH→
TOUCHED→BROKEN), `engine/liquidity.py` (equal-H/L pools + rejected sweeps),
`engine/regime.py` (BULL/BEAR_TREND, WEAKENING_*, TRANSITION, RANGE with
evidence). Generic `/api/facts?kind=` endpoint. Chart overlays: BOS/CHoCH
markers, zone rails (price lines, last 8 unbroken), sweep markers, regime badge.
Knowledge graph at `graphify-out/graph.json` (32 nodes / 42 edges; queryable via
graphify MCP) — update it when modules or contracts change.

**Decisions:**
- Break rule (§22 draft): close beyond level by max(1 tick, 0.05 ATR); wicks
  never break. A broken side re-arms only on a swing formed AFTER the break bar.
- BOS from NEUTRAL direction counts as BOS, not CHoCH.
- Causality in structure engine: swing levels admitted bar-by-bar as their
  confirmed_at elapses — a level cannot be broken before the system knew it.
- Zones: every LOCAL swing anchors one; width 0.25 ATR from the swing extreme.
  FLIP deferred to §30 item 7 (P-ZN-FLIP is a user methodology call).
- Liquidity pools: 2+ local swings within 0.10 ATR and 100 bars; anchored at the
  later swing. One terminal event per pool (SWEEP or BROKEN) in draft.
- Regime: emitted only on classification change; evidence always attached (§25).
  COMPRESSION/EXPANSION deferred (needs volatility-state facts).

**Flags:**
- CAL-2: regime changes ~every 2.4 days on 4H (76 in 180d) — flappy, downstream
  of CAL-1 (noisy local swings feed everything). Fix CAL-1 first, re-measure.
- CAL-3: 75 4H breaks in 180 days — same root cause, same plan.
- UI-1: default view is dense at long ranges; HH/LL text labels behind a
  default-off toggle. Real fix later: viewport-aware decluttering (Session 3+).

**Determinism:** PASS (35,842 facts across 5 kinds; full-pipeline re-run = 0 new).

**Deferred by user directive:** formal verification/tests batched to end of build.
Determinism re-run checks stay inline (cheap, catch regressions immediately).

---

## S3 — 2026-07-21 — Golden-data calibration: tier hierarchy + A/B

**Input:** user's swings.docx → `verification/golden-btc-1d.json` (8 major
swings, 7 breaks, 12 liquidity levels; window 2022-11-01..2026-07-21).

**Built:** swing-v0.2-draft — INTERMEDIATE and MAJOR tiers via swings-of-swings
recursion (alternate → promote, twice; self-scaling, no new parameters).
structure-v0.2 keys breaks off MAJOR (1D/1W) / INTERMEDIATE (intraday);
zone-v0.2 + liq-v0.2 anchor at INTERMEDIATE+. `calibrate.py` scores engine vs
golden (MATCH/MISS/EXTRA). Vendored lightweight-charts locally (CDN dependency
caused blank page for user). start.bat one-click launcher.

**A/B (the M4 mechanism, early):** structure-v0.3 tried 1D=INTERMEDIATE →
28 breaks vs golden 7, worse match quality. v0.2 (1D=MAJOR) won: 4/7 breaks,
10 total. v0.3 facts remain in store as the recorded loser.

**Calibration scorecard (BTC 1D, swing-v0.2):**
- Swings: 5/8 MATCH (bear bottom to the day; ATH to the day; cycle high;
  Jan'25 HH; Jan'26 LH). 3 MISS explained: Jan'23 HL (golden date/price is
  approximate — engine's 2023-03-10 19.5k low is the same structural HL);
  Apr'24 56k absorbed by deeper Aug'24 49k low (alternation keeps extremes);
  Jul'25 118k not > both neighbors (112k / 126k) so not tier-major by rule.
- Breaks: 4/7 MATCH. Dec'25 89k appears as engine BOS-bear 2026-01-31 @80.5k
  (same conclusion, stricter level — engine only breaks confirmed majors).
- Engine ranks 21 majors in window vs user's 8 "biggest only" — extras include
  Aug'24 49k crash low, Apr'25 74.4k low: plausibly legit. AWAITING USER:
  keep-or-demote call on extras list (see final S3 report in chat).

**Flags:** CAL-1/2/3 resolved by tiering (view: 21 majors / 10 breaks / 8 zones
vs v0.1's 262 swings / 116 breaks). CAV-2 (new): tier confirmed_at is
conservative (max of inputs) but replacement chains in `alternate()` need a
live-mode audit before replay ships — batch recompute is deterministic today.

**Determinism:** engines idempotent on re-run (spot-checked post-v0.2).

---

## S4 — 2026-07-21 — Promotion evidence (user feedback round 2)

**Input:** swing2.docx — calibration ACCEPTED (all matches + miss-explanations
endorsed). Two requests: (1) middle tier — already exists (MICRO/LOCAL/
INTERMEDIATE/MAJOR), clarified to user; (2) promotion reasons on every
promoted swing — built.

**Built:** swing-v0.3-draft — every INTERMEDIATE/MAJOR fact carries
`promoted_from` + `evidence`: neighbor prices, margin_pct (dominance over
same-type neighbors), reversal_atr (displacement to next opposite pivot),
held_candles (formation→confirmation), vol_ratio (pivot bar vs 20-bar avg).
Evidence recorded, NOT filtered on (§22: user grades evidence before it
becomes a required filter). Inspection report:
`verification/major-inspection-btc-1d.md` (21 majors + evidence).

**Versioning note:** downstream engines (structure/zone/liq v0.2) now read
swing-v0.3 facts without a version bump of their own — legitimate only because
v0.3 tier pivot sets are bit-identical to v0.2 (payload additions only);
verified idempotent (downstream re-run = 0 new facts). Any change that alters
pivot SETS must bump downstream versions too.

**Awaiting user:** KEEP/DEMOTE marks on the 21-major inspection table → that
grading decides which evidence dimensions become promotion filters in v0.4.

---

## S5 — 2026-07-21 — Composite Major Score (user feedback round 3, answer.docx)

**Directives taken:** demote 2025-05-22 112k (done — falls to INTERMEDIATE);
keep 2024-03-14 ATH (done — impact points carry it); score-based promotion with
ATR-heavy weights, log-scaled volume, structure-impact and liquidity-harvested
evidence dimensions.

**Version chain (each config change = new version, §7):**
- swing-v0.4: composite score, first cut. DUD — held measured confirmation lag,
  nothing could reach the MAJOR bar; 0 majors. Recorded, kept.
- swing-v0.5: held = candles until price took the level out; IMPACT_FULL 2;
  thresholds 55/30. Bear bottom fell out (scored at intermediate scale,
  margin 0.34%; broken-only impact = 0 for never-broken origins). DUD, kept.
- swing-v0.6: dominant pivots score at the scale they dominate; impact =
  LAUNCHED (away-direction breaks before next same-type pivot) + BROKEN.
  Cycle high 126k missed by 0.78 (launch window cut at next intermediate).
- swing-v0.7: launch window for dominant pivots runs to next same-type
  DOMINANT pivot. CONVERGED: 20 majors = user-endorsed v0.3 set minus 112k;
  bear bottom 71.10, cycle high 67.22, ATH 59.94, 112k demoted. Breaks
  unchanged vs v0.2 winner. Golden diff: 5/8 + 3 endorsed-explained misses.
- structure/zone/liq/regime all bumped v0.7 (input tier sets changed).

**Score weights (points):** margin 18 (5%=full) · reversal 24 (15 ATR=full) ·
held 14 (90 bars=full) · volume 12 (log2, 6x=full) · liquidity 8 (took-prev +
equal-cluster) · impact 26 (2 breaks=full) · dominance 12. MAJOR ≥55, INTER ≥30.

**New caveats:** CAV-3 — held/impact accrue as-of-now (batch); live/replay mode
needs score-update facts to keep as_of purity. CAV-4 — math.log2 (float) in
volume scoring; swap for Decimal.ln() before determinism policy sign-off.
Impact/liquidity evidence still bootstraps from structure-v0.2/liq-v0.2
(fixed-point iteration deferred). graph.json update deferred to S6.

**Determinism:** PASS (123,151 facts, full-pipeline re-run = 0 new).

---

## S6 — 2026-07-21 — Setup detector + HUD (the original ask: plotted entries)

**Built:** `engine/setups.py` (setup-v0.1-draft) — PULLBACK playbook, fact-driven:
zone TOUCHED x regime alignment -> entry (zone edge) / SL (structure +0.25 ATR) /
TP (nearest unbroken liquidity pool, swing fallback) / R:R gate >= 1.5 /
deterministic rank 0-100 (base 50 + sweep 20 + volume 15 + R:R>=2.5 15 — a rank,
NOT a probability, §25) / plain-language WHY assembled from consumed facts (§8).
Lifecycle VALIDATED -> EXPIRED (zone break). UI: HUD card (SS4 mockup chrome),
ENTRY/TP/SL price rails, ◈ setup markers, SETUPS toggle. Server: setup kind +
no-cache header on / (stale-cache bug: user saw old UI after redeploys).
Graph updated (setup engine + composite score + golden data nodes).

**Results:** 34 validated setups all-history across both symbols x 5 TFs.
Spot-check BTC 1D Mar-2025: LONG 77,852 / SL 75,667 / TP 99,517 (pool), R:R 9.91
— historically played out. Determinism PASS post-setups.

**Flags:**
- CAL-5: BTC 4H = 0 setups — user's stated failure mode is "no setups due to
  too-strong gates." Suspects: regime rarely BULL/BEAR_TREND at touch time on
  4H (TRANSITION flapping), R:R gate, zone-touch ordering. Diagnose next session.
- SET-1: no time-based expiration (§11 requires it) — a 2024 setup still shows
  VALIDATED in 2026 HUD. v0.2: expire after N bars unfilled.
- CAV-4 still open (float log2 in vol scoring; swap to Decimal.ln, bumps chain).

**User-visible:** http://localhost:8422 -> 1D shows HUD card + rails. This
closes the original product loop: exchange-connected, structure mapped, chart
with plotted entries.

---

## S7 — 2026-07-21 — REVERSAL playbook + execution sim (paper track record)

**CAL-5 diagnosis:** not a too-strong gate — TRANSITION regime absorbed most
zone touches (8/20 on 4H) with no playbook for it, and the rest were correctly
rejected counter-trend entries. Fix per user's own strategy table (exhaustion ->
reversal): setup-v0.2 adds REVERSAL playbook (TRANSITION + zone touch, base
rank 40) and WEAKENING_* continuations. 4H unblocked (8 BTC / 12 ETH). 200
validated setups all-history (was 34).

**Built:** `engine/execsim.py` (exec-v0.1-draft) — §16-compliant paper sim:
fill at entry on trigger bar, walk to SL/TP; same-bar both = SL (conservative,
ambiguous flagged); TIMEOUT at 100 bars exits at close (resolves SET-1/§11);
unresolved tail = OPEN, emitted when resolvable. R-multiple per trade.
`/api/track` (§15 metrics), footer PAPER W/L · PF · ΣR, HUD outcome line.

**First honest track record (no fees/slippage yet):**
- PULLBACK: n=52, 19% TP, ΣR +0.9 — flat. The S6 "9.91R winner" actually
  stopped out (April 2025 dip broke the zone first) — exec sim catching our own
  eyeball bias is the system working as constitutionally intended.
- REVERSAL: n=148, 18% TP, ΣR +147.7 — fat-tail profile (avg winner ~10R,
  all losers -1R). Top winners verified as real market events (ETH 1,386
  crash-bottom long -> 3,447; 2026 bear shorts). PROMISING, NOT VALIDATED:
  needs M4 walk-forward, fees/slippage, and OOS splits before trust.

**Flags:** CAL-5 RESOLVED. SET-1 RESOLVED (TIMEOUT). NEW EXEC-1: no fees,
slippage, or spread modeled (§14 requires them in research records) — expect
ΣR to compress, especially on 15m. CAV-4 still open.

**Determinism:** PASS post-S7 (idempotent re-run, 0 new facts).

---

## S8 — 2026-07-21 — M4 validation harness: costs kill the intraday book

**Built:** exec-v0.2-draft (EXEC-1 closed): fees 0.25%/side on notional; limit
fills (entry, TP) fee-only; market exits (SL, TIMEOUT) fee + 0.05 ATR slippage.
r_multiple now NET; r_gross retained. `validate.py` -> verification/
validation-001.md: per-strategy x symbol x tf x year cohorts, PF, maxDD(R),
longest-underwater, tail-dependence (minus top-N winners). Scope caveat printed
in the report: rules were calibrated with hindsight — this measures robustness,
not OOS edge.

**Findings (the harness earning its keep):**
- Gross-vs-net: REVERSAL +147.7R gross -> -108.9R net. PULLBACK +0.9 -> -78.8.
- Root cause is structural, not random: stops are tight (0.25 ATR beyond a
  0.25 ATR zone) so RISK is small, while fees are % of NOTIONAL — on 15m,
  round-trip costs alone run 3-6R (avg net -2.95R/trade). Tight-stop scalping
  cannot pay retail taker fees. Confound noted: 15m/1H data only spans 2026,
  so the "2026 is bad" cohort is mostly the same finding.
- What SURVIVES costs: 1D REVERSAL net PF 3.66 (+38.4R/13), 4H REVERSAL
  PF 1.52 (+13.2R/18), 1D PULLBACK PF 1.47 (+7.3R/16). The economics live on
  higher timeframes, exactly where the structure map is strongest.

**Next knob (S9 candidate):** fee-aware setup gate — reject any setup whose
risk < K x round-trip cost (deterministic, pre-trade, §9-compatible). Kills the
uneconomic intraday book at the source instead of discovering it in the ledger.

**Determinism:** engines idempotent post-v0.2 (0 new facts on re-run).

---

## S9 — 2026-07-21 — Fee gate + replay engine + fact inspector (v0 spec closed)

**Fee-aware gate:** setup-v0.3 (K=4) rejected 193/200 including the profitable
1D book — K=4 is unattainable with 0.5-ATR structural stops (fees are % of
notional; BTC 1D max ratio ~2.9). Recorded dud. setup-v0.4: K=2 (~0.5R max
cost drag) -> 30 setups pass, 170 cost-rejected (all intraday). exec-v0.4.
Cost constants moved to setups.py (single source of truth with execsim).

**validation-002 (post-gate, net):** REVERSAL n=14 PF 4.49 +50.5R — but
minus-top-3 = -14.5R (edge is 2-3 monster trades) and BTC-side is 0/5.
PULLBACK n=16 PF 1.47. VERDICT: shape is promising, n is statistically
nothing, tail-dependent, hindsight-calibrated. The historical well is dry —
further knob-turning would be curve fitting. Next evidence must be FORWARD
paper trading (live loop).

**Replay engine (§28):** as_of cursor in UI — date picker + step/LIVE buttons;
candles end_ts + all fact queries as_of; title shows REPLAY timestamp.
Verified: at as_of 2025-10-15 the later-confirmed cycle high is absent — the
no-repaint guarantee is now user-visible.

**Fact inspector (§19/§28):** click any bar -> panel lists every fact at that
bar (kind/tier/event/state, market vs confirmed time, algo_version, full
payload incl. score_parts). Explainability surfaced end to end.

**v0 acceptance criteria (§29) status:** import+gaps ✓ · no-lookahead replay ✓
· swing confirm times ✓ · deterministic facts ✓ · inspectable BOS/CHoCH ✓ ·
zone lifecycle partial (FLIP pending §30-7) · synchronized multi-TF views ✗
(single chart w/ TF switch) · lineage on facts ✓ · golden tests ✓ (calibrate)
· comparison reports ✓ (A/B versions) · restart-stable ✓ · regenerable ✓.

**Determinism:** PASS (idempotent re-runs across v0.4 chain).

---

## S10 — 2026-07-21 — Forward paper loop (the scanner goes live)

**Built:** `live.py` — poll every 60s; import newly CLOSED candles only (§5),
re-aggregate, re-run all engines (idempotent: quiet cycle = zero writes),
detect new VALIDATED setup facts, notify. `notify.py` — Windows toast via
PowerShell WinRT, zero dependencies, console fallback. start.bat now launches
scanner + server + chart together.

**Live test:** first cycle pulled 166 real candles (day since backfill),
full pipeline in 3.7s, 0 new setups (correctly quiet in current conditions).
Test toast delivered to user's desktop.

**This starts the forward paper track record** — every setup from here on is
out-of-sample by construction (§15). The user's own bar: ~30 days of logged
signals before any live-capital conversation.

**Deferred/open:** Tauri packaging (next); Telegram notify (when user wants
phone alerts); multi-TF sync view + zone FLIP (§29 leftovers); CAV-3/CAV-4;
§30 session + Item I rulings (user).

---

## S11 — 2026-07-21 — Cockpit UI (SS4 tactical-HUD identity + setup feed)

**Why:** user: "make it different than TradingView — this needs to stand out."
The SS4 blueprint design language (glass-cockpit avionics, glow-as-signal,
grid-etched near-black, mono numerics) was already specified — implemented it
fully from the mockup's own CSS DNA.

**Built:** full index.html rebuild as a 3-rail cockpit:
- Top: crosshair logo, live SESSION bar (ASIA/LON/NY-O/NY-PM/LATE, current
  segment glowing, HIGH-VOL pill in LON/NY-O), PAPER MODE pill, replay
  controls, UTC clock.
- Left rail: SCAN UNIVERSE (live price/24h/regime per symbol, click to load),
  overlay toggles, FACT ENGINES LED panel (green = ran <24h).
- Center: chart w/ grid-etched background, regime readout, HUD card,
  REPLAY/LIVE as_of chip (amber glow in replay).
- Right rail: SETUP FEED — the "where do I see setups" answer. Tabs
  ACTIVE/EXPIRED/CLOSED; cards show symbol/tf/rank/strategy/R:R/levels and
  paper outcome; click jumps chart to that setup. Honest empty state ("fee
  gate only passes economic setups").
- Footer: SCANNER status (live/idle Xm — run start.bat), fact store count +
  algo version, paper record, view counts, SIM ONLY banner.
- New `/api/overview` powers the rails (watchlist, feed w/ outcomes, engine
  health); 30s auto-refresh.

**Note:** browser-pane screenshot tool went flaky mid-verify; layout confirmed
via DOM/a11y tree (all regions present, zero console errors).

---

## S12 — 2026-07-21 — Risk Authority (§9, paper): the governor exists

**Built:** `engine/risk.py` (risk-v0.1-draft) — portfolio-scoped single pass in
strict time order across all symbols/TFs. Paper account $10,000; 1% equity risk
per trade; limits: 2 concurrent positions, 2% total open risk (BTC+ETH count
together), 3x implied-leverage cap (reduces SIZE, never widens stops), -3%
realized daily loss -> KILL_SWITCH fact halts new entries for the UTC day.
Every intent gets a DECISION fact: APPROVED/REDUCED/REJECTED with
machine-readable reasons — rejections as auditable as approvals (§8).
`/api/portfolio` (equity, curve, decision counts, recent decisions); footer
EQUITY readout. Wired into live.py cycle + backfill. Graph updated
(risk_authority, exec_sim, live_loop nodes).

**Historical pass:** 30 intents -> 29 APPROVED, 1 REDUCED (exposure overlap),
0 REJECTED, 0 kill days. Equity $10,000 -> $16,486.12 (+64.9%) compounding at
1%/trade. Same caveats as validation-002: tail-dependent, hindsight-calibrated,
n=30 — the number is an accounting demo, not a promise. Limits rarely bind at
n=30; they exist for the scale-in playbook (S13) where adds multiply exposure.

**Determinism:** PASS (re-run +0 facts).

**Next:** S13 scale-in playbook — 1H continuation triggers inside active 1D/4H
setups; adds must fit inside the ORIGINAL approved risk (trail-to-BE rule);
risk authority governs total. Draft answer to §30 item 9 (HTF influence).

---

## S13 — 2026-07-21 — Scale-in playbook (HTF gates LTF; draft §30 item 9)

**Built:** `engine/scalein.py` (scale-v0.1-draft) — adds inside active 1D/4H
setups only: 1H BOS in parent direction, confirmed inside the parent's
open window, close already >= 1 parent-R beyond parent entry (adds are bought
with market progress, not hope). Add bracket: entry = break close, SL = parent
entry (breakeven line), TP = parent TP. Fee gate per add. Max 2 adds/parent.
exec-v0.5 fills both setup sources (double execsim pass in pipeline: parents ->
scalein -> adds). risk-v0.2 governs adds: half-size (0.5%), exempt from
concurrency count (attached to parent) but consume the 2% total-risk budget;
REJECTED with PARENT_CLOSED if the parent already exited. UI: SCALE_IN cards
green in feed; /api/facts merges both setup versions.

**Results:** BTC 0 adds (parents never progressed 1R — trigger rule filtering
correctly), ETH 3 adds: Jan'26 add -1.10R (contained at breakeven-line stop),
two June/July'26 adds inside the live 4H reversal at +1.21R / +0.23R (TIMEOUT).
Risk pass: 32✓ 1↓ 0✗, equity $16,499.59. n=3 — mechanics proven, no edge claim.

**Flags:** SCALE-1 — parent keeps its ORIGINAL bracket in exec (no trail-to-BE
for the parent yet); true pyramiding accounting needs a stateful position
manager (exec v0.6). Until then adds are honestly modeled as additional
half-size exposure under the authority's caps.

**Determinism:** PASS (full re-run +0 facts).

---

## S14 — 2026-07-21 — Ports from the old project (snipersight-trading review)

**Reviewed:** old project's ingestion_pipeline.py + ohlcv_cache.py at user's
request. Verdict: battle-hardened, ~1/3 worth taking.

**Ported:**
1. OHLC integrity validation (importer-v0.2-draft): candles with high<low,
   extremes not containing open/close, or non-positive prices are REJECTED —
   loud warning, counted in import_log.n_bad (schema migration in connect()),
   left as gaps per the gap-honesty rule (old project fabricated flat filler
   candles; we deliberately do NOT). Retro integrity sweep of all 20,532
   stored candles: 0 malformed, 0 duplicate timestamps — history is clean.
2. Loud-fallback rule (from old cache's telemetry-on-fallback discipline):
   any defensive degradation must be audible. Applied: toast delivery failure
   now warns in live log; execsim missing-ATR slippage skip now warns
   ("results slightly flattering"). Rule recorded here as standing policy.

**Deliberately not ported:** gap-filling with fabricated candles (violates
gap-honesty), pandas/float math (we are Decimal end-to-end), in-memory TTL
cache (SQLite store supersedes; closed candles are permanent), global mutable
singleton. Noted for scale-up: their parallel fetch (stagger + batch timeout
+ failed-symbol accounting) when universe grows past ~10 symbols; candle-
boundary-anchored expiry lesson (market time, never wall clock).

---

## S14b — 2026-07-21 — Price-drift monitor (flash-move awareness)

**Built:** `check_drift()` in live.py (drift-v0.1-draft) — every 60s poll,
spot ticker vs last CLOSED 15m candle; |drift| >= 3% fires a toast + WARNING
log + an `alert` fact (PRICE_DRIFT). One alert per symbol per 15m bucket.
Awareness only — engines still never touch unclosed data (§5). Closes the
"engines are blind between candle closes" gap the old project's
price-drift-invalidation hinted at. Tested: dry-run path fires, 3% threshold
correctly silent in calm market.

---

## S15 — 2026-07-21 — Operational hardening (protect the forward record)

**Rationale:** the #1 killer of systems like this is the loop silently
stopping. The forward paper record is the project's most valuable asset.

**Built:**
- `watchdog.py` — supervises live.py + api server; restart on exit with
  exponential backoff (5s->300s, reset after 60s clean uptime); toast on
  scanner restart (loud-fallback rule: self-healing must still be audible);
  single-instance lock socket :8423; leaves an externally-run server alone.
- Heartbeat: live.py writes data/heartbeat.json EVERY poll (ts, pid, cycles);
  /api/overview serves it; UI footer light now reflects true scanner
  liveness (LIVE · cycle N / DOWN Xm / NEVER STARTED) instead of inferring
  from engine runs.
- `install_autostart.py` — Startup-folder .vbs launching watchdog headless
  (pythonw) at logon; no admin needed; --remove / --status. INSTALLED on
  user's machine per approved plan.
- start.bat now routes through the watchdog (crash-proof manual mode).

**Tested live:** heartbeat flowed (pid 12096, cycle 1) -> killed the scanner
process -> watchdog detected exit rc=-1 at 18:58:37, restarted 5s later as
pid 13164, heartbeat resumed. Restart toast fired.

**Also noted:** PC sleep/wake needs no special handling — on wake the
importer backfills from the last stored candle automatically (gap-honest).

**Next per S14 recommendation:** zone strength + FORMING setups (one
session), then feature freeze while the forward record accumulates.

---

## S16 — 2026-07-21 — Zone strength + FORMING setups (last pre-freeze feature)

**Built:**
- zone-v0.8-draft: touch EPISODES (re-entry after leaving = new episode, max
  10 facts/zone), spec §23 lifecycle states FRESH->TOUCHED->TESTED->WEAKENED->
  BROKEN, cluster_members (same-type anchors inside the band), strength 0-100
  (episodes/cluster/age/tf-weight — evidence, not filter; ported concept from
  old project, made ATR-relative + deterministic).
- setup-v0.5-draft: FORMING state — price within 1 ATR of an untouched active
  zone (4H/1D/1W only), regime aligned, prospective bracket passes the SAME
  R:R + fee gates -> FORMING fact + 👁 toast. Upgrades to VALIDATED on touch;
  zone broken untested -> CANCELLED. Shared gates() helper.
- exec-v0.6 / risk-v0.3 bumps (input version). scalein kept at v0.1 (adds
  bit-identical; verified idempotent — same shortcut precedent as S4).
- UI: FORMING tab (dashed amber cards), DEAD tab absorbs CANCELLED.
- live.py announces FORMING distinctly (👁 vs ◉).

**Verification:** validated book BIT-IDENTICAL through the zone semantics
change: 30 setups, risk 32✓/1↓/0✗, equity $16,499.59 to the cent. Historical
FORMING: 31 events, 7 CANCELLED. Determinism PASS (127,017 facts, +0).
Bonus: watchdog takeover path fired live (external server killed -> took over
supervision in 10s, pid 8228).

**FEATURE FREEZE begins (accepted S14 recommendation #4):** no new trade
logic until the forward record has ~30 days. Allowed during freeze: Tauri
packaging, Telegram, §30 session, Item I rulings, bugfixes, old-project
reviews. The scanner + autostart are live; the record accumulates on its own.

---

## S17 — 2026-07-21 — Nested Cycle Satellite (Loukas/Camel school) — OBSERVATIONAL

**Freeze-compatible by design:** litmus test = deleting it changes no trade.
Grep-proven: all 9 trading engines have zero references to cycles; `cycle`
facts have no consumers. Promotion to an enforced input = separate validated
setup version, NOT built.

**Built:** `engine/cycles.py` (cycles-v0.1-draft) — DCL detection (2-bar
fractal reimplemented locally — one-way boundary over DRY — in 54-66d bands
from the 2022-11-21 seed), WCL grouping (150-200d over the DCL pool, nest
recorded), translation classification (<40% left / >60% right, raw fraction
reported), failed-cycle flag (close below own start-low before exceeding
prior top), inversion flags (band elapsed, no low — primary_count AND
inverted_count both published, no silent re-anchor), TWO independent 4Y-low
windows (low-to-low from accepted constants 2015-01/2018-12/2022-11 + 44-52mo;
halving-anchored: est. 2028-04 halving - 12-18mo) never merged, push-out
heuristic (+60d iff weekly right-translated, labeled n~=2). Every payload:
observational=true + honest note + source. /api/cycles (computed live, facts
hold only detections). UI: CYCLES rail panel + DCL/WCL/translation/inversion
chart markers + toggle.

**Tests:** first formal test suite in the repo — tests/test_nested_cycles.py,
14 tests, all synthetic/deterministic/offline, ALL GREEN first run (planted
lows, band rejection, L/M/R translation, failed flag both ways, inversion
counts, 3:1 nesting, both windows bracket Nov-2022, pushout math + gating,
JSON-safety/flags, fail-soft).

**Real-data read (BTC, seed 2022-11-21):** 21 DCLs (1 inversion), 7 WCLs.
Last three weekly cycles: right 0.927 -> right 0.637 -> LEFT 0.174 FAILED —
the textbook topping sequence. Currently day 46/60 daily, 46/168 weekly,
provisional left. Windows: low-to-low 2026-07-21..2027-03-21 (opened TODAY);
halving-est 2026-10-15..2027-04-15. Push-out NOT active: the rule keys on the
latest weekly translation, which is left/failed — the right-translated cycles
that motivated the user's push-out thesis are two cycles back. Divergence
surfaced to user, not silently resolved.

**Also fixed:** live.py loop counter shadowed the cycles module import
(renamed n_cycles). Determinism PASS (+0). 57 cycle facts emitted.

---

## S17b — 2026-07-21 — Push-out variant clarification (user challenge: "my own rule?")

**What happened:** user's build prompt operationalized push-out on the CURRENT
WEEKLY cycle's translation (off: latest weekly is left/failed). But the user's
own thesis text said "extended translation pushes the 4-year low out" — that
keys on the 4-YEAR cycle's own translation. The prompt contradicted the thesis;
the satellite exposed it. Resolution per the module's own discipline: BOTH
variants published, labeled, never merged.

**Built:** four_year_windows() gains fy_top_fraction + pushout_extended_window_4y
(fires iff 4Y top-so-far fraction > 0.60). Test added (15 green). Panel shows
pushout·wk and pushout·4y lines separately. Summary-only change — zero fact
changes, no version bump (facts hold detections only; windows are computed).

**Real data:** 4Y top-so-far (Oct-2025, ~1050d from Nov-2022 low) = 0.719 of
nominal 1461d -> RIGHT-translated -> 4Y-variant ACTIVE: low-to-low end extends
2027-03-21 -> 2027-05-20. Weekly variant correctly stays off.

---

## S18 — 2026-07-21 — Risk envelope 1%→2% + per-trade sizing on cards

**User directive (freeze exception, authorized):** per-trade risk 1%→2%.
Re-tuned the whole envelope coherently so concurrency/kill-switch don't silently
break: RISK_PCT 2%, MAX_TOTAL_OPEN_RISK 4% (keeps 2 concurrent), DAILY_LOSS 6%
(~3 stop-outs), SCALE_RISK 1% (half a base). risk-v0.4-draft (v0.3 book stays
queryable). Historical: $10k→$24,203 (+142% vs +65% at 1%) — return AND
drawdown ~double; same thin/hindsight caveats.

**UI:** each feed card gains a risk line (RISK $ · units · leverage · decision);
footer account strip shows next-trade risk $ + full envelope
(%/trade, cap, leverage, halt). /api/overview enriches feed with per-setup risk
decision; /api/portfolio exposes config + next_risk_usd.

**Determinism:** PASS (+0). Watchdog auto-redeployed server.

**Freeze note:** trade-logic change, but user-directed and versioned. Forward
record from here uses the 2% envelope.

---

## S19 — 2026-07-21 — Dynamic universe (user: "top-whatever at scan time")

**Built:** `engine/universe.py` (universe-v0.1) — ranks ALL online Coinbase USD
spot pairs by live 24h volume, admits top-20 above a $3M/day floor that ALSO
have >=200 daily candles (structure needs history); liquid-but-new = WARMING
(backfilled, not traded). Selection recorded as a `universe` fact each refresh
(determinism preserved — reprocessing iterates stored symbols, only live
ranking is time-varying). `engine/ingest.py` onboards a symbol (backfill +
engines). live.py refreshes hourly + onboards entrants + scans admitted set.
risk/server rewired off hardcoded BTC/ETH to all-tracked. UI watchlist shows
rank/volume/⏳warming. Ported ONLY `_is_stable_base` (USDT etc. excluded);
dropped CoinGecko classifier + all perp/leverage machinery (spot, curated-by-
liquidity). Bug caught + fixed: /products isn't volume-ordered, initial [:120]
cap dropped SOL/XRP — now sweeps all pairs.

**Bug fixed (data-integrity, §8):** /api/portfolio re-derived equity by naive
sum → +84%, while risk.run's compounding+kill-switch accounting → -68%. Two
equity numbers is forbidden. Fix: risk.run emits an authoritative `account`
SUMMARY fact (final_equity, return, maxDD, curve); UI reads it, never
re-derives. Anchored summary market_time to last settlement (not wall-clock)
→ cross-second determinism PASS.

**CRITICAL FINDING (the point of all this):** broadening 2 → 19 liquid symbols
COLLAPSED the paper book: BTC/ETH-only was +142% / 0 kills; full universe is
-68.3% / 75.7% maxDD / 13 kill-switch days / 125 rejections. The apparent edge
does NOT generalize beyond BTC/ETH — it was small-sample / symbol-specific.
This is the risk authority + constitution working exactly as designed: the
universe expansion didn't add options, it revealed the strategy is unproven on
the broad set. Live trading (if ever) must stay gated to where forward evidence
supports it. Determinism PASS throughout.

---

## S20 — 2026-07-21 — ACCOUNT view (making the -68% legible)

**Built:** right rail gains FEED/ACCOUNT tabs. ACCOUNT: authoritative equity +
return + maxDD + kill days (reads the `account` SUMMARY fact, never re-derives),
SVG equity curve vs start-equity baseline, per-symbol and per-strategy tables
(worst-first, $ and R columns). /api/performance aggregates exec facts joined
to risk sizing ($-PnL counts only trades the authority sized; R columns count
every simulated trade — the difference is deliberate and visible).

**What the breakdown revealed (sharpens S19's finding):**
- ETH is the ENTIRE edge: +$12,131, 43% win, +74.1R. Next best: ZEC +$1,034.
- BTC is 0-for-12 (-$2,972) — "the BTC/ETH edge" was really an ETH edge.
- PULLBACK is a net loser everywhere (-$5,730 across 97 trades).
- XLM shows +31.6R but -$1,603: its R-positive trades were mostly unsized or
  small-equity moments — sequencing/sizing matters, which is exactly why the
  authoritative $ number is the one that counts.

**Verified:** panel renders (DOM check; screenshot tool flaky), endpoint live,
watchdog handled redeploy.
# 2026-07-22 — Non-destructive forward paper baseline

- Added a versioned active baseline marker; candles and immutable facts remain intact.
- Scoped risk accounting and all user-facing trade/performance telemetry to setups
  validated on or after the active marker.
- Added a confirmed API reset, CLI reset, and wallet control with visible start date.
- Kept all strategy eligibility, entry, exit, and sizing constants unchanged.


---

## S21 — 2026-07-25 — Unwedge the fail-closed gate (1,364 blockers -> 0)

**Symptom:** UI showed BLOCKED / EVALUATION BLOCKED (1,364 critical blockers).
Worse: engine.log showed EVERY live cycle since the hardening landed aborting
with "BTC-USD blocked by market-data quality: SEQUENCE_GAPS" — the scanner was
wedged for days and the hardened chain (setup-v0.6/exec-v0.7/risk-v0.6) had
produced ZERO facts. The forward record was frozen.

**Root causes:**
1. Gap deadlock: assert_market_ready treats ANY candle discontinuity as
   BLOCKED, but Coinbase legitimately omits buckets with zero trades and our
   constitution logs gaps rather than fabricating candles. A permanent venue
   void meant a permanently closed gate -> no engines -> no facts -> more
   audit failures downstream (MISSING_AGGREGATE x382 accumulated as imports
   continued while aggregation/engines were blocked).
2. Generation leakage: the audit evaluated ALL fact generations, so legacy
   (pre-order-lifecycle, pre-manifest) facts produced 786 EXIT_WITHOUT_ORDER +
   126 REJECTED_WITH_EXPOSURE + 597 INCOMPLETE_LINEAGE against a chain that
   never wrote them — contradicting HARDENING.md's own "older generations are
   not comparable" rule.

**Repairs (quality.py only — no strategy constants touched):**
- KNOWN_VENUE_GAPS: discontinuities acknowledged in import_log degrade instead
  of block; unexplained gaps still BLOCK (fail-closed preserved for genuine
  corruption). Aggregate-TF discontinuities defer to the MISSING_AGGREGATE
  reconciliation check (missing-by-design when sources incomplete).
- SETUP/RISK/EXECUTION checks scoped to the active engine chain (lazy-imported
  current versions). CAUSALITY and EQUITY_RECONCILIATION stay global —
  corruption is corruption in any generation (one test initially broken by
  over-scoping the account check; reverted that filter, suite green 55/55).

**Repair run:** 1,427 gap ranges re-attempted -> 0 candles recovered (all
genuine venue voids, now acknowledged); aggregates rebuilt for 31 symbols;
hardened chain ran end-to-end for the first time (31/31 symbols, 67s);
risk-v0.6 baseline account: $10,000, 0 trades (correct — nothing has validated
inside the forward window yet under the stricter v0.6 gates). Scanner + server
restarted under watchdog; first healthy cycle confirmed (universe refresh even
onboarded RE-USD).

**Final audit: 0 blockers, 116 honest warnings (70 known venue gaps, stale
non-scanned series, 1 legacy-attribution note). EVALUATION ALLOWED.**

---

## S21b — 2026-07-25 — UI self-heal (the "only shows UTC" report)

**User report:** clicked RAW COCKPIT top-right; page went empty except the UTC
clock. Diagnosis: the click landed during the S21 server-chain restart window.
The hardened UI's api() wrapper shows a DEGRADED banner on failure but never
retries — a page loaded during any server blip stayed dead until manual
refresh (the clock is pure JS, hence "only shows UTC").

**Fix:** api()'s failure path now schedules a single coalesced retry loop
(5s): hide the banner, re-run loadOverview/load/loadPipelineHealth; if the API
is still down the banner re-appears and the loop continues. Footer shows
"API UNREACHABLE — reconnecting…" during outages. (Also reverted a stray
unclosed try{ from an edit against a stale copy of index.html — the hardening
pass had rewritten the file; anchored edits now verified against disk.)

**Tested live:** killed the server under an open page -> DEGRADED banner ->
watchdog restarted it -> page self-healed to SCANNER LIVE with full data, no
manual refresh.

---

## S21c — 2026-07-26 — RAW COCKPIT was a one-way door

**User report:** "where is the WHY and raw cockpit now? it's not on the screen."

**Diagnosis:** both controls live in cockpit.html's top bar, served at `/`.
Clicking RAW COCKPIT navigates to `/raw` (index.html standalone), which has
NO link back and no WHY drawer — so after one click the user is stranded on a
page whose only route home is hand-editing the URL. Confirmed the controls
render correctly at `/` (RAW COCKPIT x=1094, WHY? x=1195 of 1280) and that the
header stays responsive down to 880px, so clipping was NOT the cause.

**Fix:** index.html gains a "◂ COCKPIT" pill linking to `/` (target=_top).
Shown only when `window.self===window.top` — the cockpit embeds this same file
in an iframe, and a self-link inside the cockpit's own frame would be noise.
Verified both ways: visible standalone at /raw (href="/"), display:none inside
the embedded frame.

---

## S22 — 2026-07-26 — One-click restart button (server + scanner)

**User ask:** a UI button to restart "both servers, front and back."

**Clarification worth recording:** there is no separate front/back server. One
FastAPI process serves BOTH the API and the UI (cockpit_server mounts server),
and the second process is the live scanner. So "both" = api-server + scanner,
which is exactly what the watchdog already supervises.

**Design — restart, never a kill switch:** `POST /api/system/restart?target=
server|scanner|both` has NO spawn capability by construction. It only asks
processes to exit (scanner: taskkill by heartbeat pid; server: os._exit after a
0.75s timer so the acknowledgement flushes first) and lets the EXISTING watchdog
respawn them on its 5s backoff. If the watchdog is not holding its lock socket
(:8423) the endpoint refuses with 409 — otherwise the button would take the app
down with nothing to bring it back. Two further guards: a heartbeat older than
180s is never signalled (the pid may be recycled to an unrelated process), and
target is regex-constrained by FastAPI (unknown targets -> 422).

**Windows honesty bug found and fixed mid-build:** os.kill(pid, SIGTERM)
terminates the target but still raises WinError 87, so the first version
reported "scanner stop failed" while the watchdog log showed a clean exit —
a lie in the response. Replaced with taskkill and OBSERVED-outcome reporting.

**UI:** "⟳ RESTART" in the footer beside the scanner light (visible in both the
standalone /raw view and the cockpit's embedded frame), with a confirm dialog
stating that the watchdog respawns within ~15s and that append-only facts are
never lost. On success the footer shows "RESTARTING — waiting for watchdog…"
and the S21b self-heal loop repaints the page unaided.

**Verified end-to-end (clicked in the browser, confirm auto-accepted):**
scanner 1160 -> 15944, api-server 18604 -> 7816, page self-healed to
SCANNER LIVE with full data, button re-enabled, no manual refresh. Note the
api-server's graceful exit logs rc=0 (vs rc=4294967295 for an external kill) —
a useful signature of an intentional restart.

**Also fixed:** two stale tests from 5645ce9 that failed at HEAD before any of
my edits — one asserted `iframe src="/"`, i.e. the cockpit embedding ITSELF
recursively, which 846f310 had deliberately fixed; the other expected the
launcher to open /static/cockpit.html rather than the origin. Corrected both to
assert the shipped design, added a guard that the recursive form never returns,
plus tests for the return-path pill and the restart endpoint's refusal path.
Suite: 71 tests green (1 skipped — the lock-port probe correctly skips while a
real watchdog holds it).

---

## S22b — 2026-07-26 — "WHY?" renamed; static-asset cache trap fixed

**User critique (correct):** "WHY?" is a question with no object — and with the
badge it read "WHY? 12", i.e. "why 12?". The control is really an inspector for
decision provenance: setup traces, rejection reasons, data health.

**Renamed:** button "WHY?" -> **DIAGNOSTICS** (badge now reads naturally as a
count of actionable items), with a title attribute that keeps the intent
explicit: "Why the engine did what it did…". Drawer header "WHY? · DIAGNOSTICS"
-> "DIAGNOSTICS · WHY THIS TRADE, WHY NOT THAT ONE" (a complete phrase, not a
dangling question). Same dangling label inside diagnostics.html: panel heading
"WHY?" -> "DECISION RATIONALE". Element ids renamed too (whyButton/whyDrawer/
whyBadge/closeWhy -> diag*) so nothing internal still says "why" while the UI
says otherwise; cockpit.js and both test files retargeted.

**Bug found while verifying (the important one):** after the id rename the
drawer silently stopped working — the browser replayed a CACHED cockpit.js that
still bound `whyButton`, hit a null, and threw at load, killing every handler
and the badge refresh. HTML and JS from two different generations. Fixes:
1. `_NoCacheStatic` — /static now serves `Cache-Control: no-cache,
   must-revalidate`. These are a few KB on loopback; a caching win is worthless
   next to serving a self-inconsistent UI. (This same trap explains the earlier
   "hard-refresh needed" notes in S16/S21b.)
2. Cache-busted the asset URLs (`cockpit.js?v=2`, diagnostics css/js, and the
   diagnostics iframe src) so the transition works even from an already-stale
   cache — no user-side Ctrl+F5 required.

**Also fixed:** diagnostics.html's COCKPIT link pointed at
`/static/cockpit.html` with no target; inside the drawer iframe that would have
nested an entire cockpit inside the cockpit. Now `href="/" target="_top"`.

**Verification note worth remembering:** the drawer appeared "stuck closed"
(transform frozen at translateX(101%) while the class was `open`) purely
because the browser pane was not compositing frames, so CSS transitions never
advanced. Disabling the transition proved the rule applies: translateX(0),
left=576 of a 1280 viewport, scrim opacity 1 — DRAWER OPENS CORRECTLY. Live
badge confirmed working ("4 ACTIONABLE DIAGNOSTICS"). Suite: 71 green.

---

## S23 — 2026-07-26 — Cockpit wrapper deleted (one page); two blockers fixed

**User decision:** full consolidation. The RAW COCKPIT button had zero
consumers — it offered the same screen minus diagnostics plus 39px of chart —
while the /raw ROUTE existed only because the wrapper embedded the app in an
iframe. 151 lines of wrapper hosted one button and one drawer.

**Consolidated:** DIAGNOSTICS button + drawer now live directly in index.html
(position:fixed overlay, no iframe of self). The diagnostics PANEL is still the
reusable /static/diagnostics.html, now LAZY-LOADED on first open so the trading
view pays nothing for it at startup. Deleted cockpit_server.py, cockpit.html,
cockpit.js. watchdog launches server:app. /raw -> 308 redirect to / so old
bookmarks land somewhere. Removed the now-pointless "back to cockpit" pill.
Verified: no self-iframe, lazy src null-then-loaded, drawer at left=576/1280,
panel headings correct, app height 800 (was 761 inside the frame) — 39px back.
Tests rewritten for the consolidated design (75 green).

**Blocker regression fixed (found while verifying, NOT user-visible before):**
audit had gone BLOCKED again with 4 blockers.
1. SEQUENCE_GAPS on EUL-USD 15m (830 "unexplained"). Root cause was MY S21 fix
   trusting import_log.gaps, which importer truncates at 200 while n_gaps stays
   exact — so any series with >200 real voids re-wedged the gate. Now judged on
   the COUNT with the listed timestamps as a budget; import cap raised to 5000.
2. MISSING_AGGREGATE on ONDO/SUI 4H. A bucket that closed moments ago simply
   has not been aggregated yet — scheduling lag, not corruption. Now
   AGGREGATE_PENDING (DEGRADED) within two bucket periods, MISSING_AGGREGATE
   (BLOCKED) only if it persists.
Audit: 0 blockers, evaluation allowed.

**Self-inflicted scare worth recording:** the cap change was applied by blind
string replace and dropped a comment INTO the middle of the SQL argument list,
commenting out the remaining args — importer.py stopped parsing while the live
scanner imports it. Caught by the very next syntax check and fixed inside a
minute. Never inject a comment mid-call via string replace.

**Answered for the user (right-rail investigation):** SETUP FEED / SETUP TRACE
are NOT broken. 1,832 setup facts exist (379 current-gen) but ZERO inside the
active baseline window — nothing has validated since the Jul-22 baseline, which
is truthful under the stricter setup-v0.6 rules. The store holds 4,492
setup_rejection facts explaining exactly why: NO_ELIGIBLE_PLAYBOOK 3,959 (88%),
UNECONOMIC_AFTER_COSTS 370 (8%), RR_BELOW_MINIMUM 163 (4%). The empty state
blames "the fee gate", which accounts for only 8% — the UI is guessing while the
real answer sits in the fact store. Proposal recorded, not yet built.

---

## S23b — 2026-07-26 — Right rail simplified; empty state stops guessing

**User:** the right rail was confusing — four top tabs over four sub-tabs, every
one reading 0 — and asked whether SETUP TRACE / PIPELINE belong in diagnostics.
They do.

**Moved:** SETUP TRACE and PIPELINE out of the trading rail and into the
DIAGNOSTICS drawer, which now has its own strip: SETUP TRACE · PIPELINE · FULL
PANEL (the reusable diagnostics.html iframe). Each tab loads only when first
shown. The trading rail keeps exactly the two operational views: SETUP FEED and
ACCOUNT. The evaluation gate now opens the drawer on its PIPELINE tab instead of
hijacking the rail.

**Empty state now states the recorded reason** instead of blaming the fee gate
(which was ~8% of rejections). Reads live from the baseline-scoped rejection
funnel, e.g. "190 candidates rejected since baseline: 172 no eligible playbook,
12 uneconomic after costs, 6 rr below minimum" with a SETUP TRACE ▸ button that
opens the drawer. A dead panel became the most informative thing on screen.

**Bug caught in verification (selector collision):** the feed sub-tab handler
bound `.ftab:not(.rt)`, which also matched the new drawer tabs, and — being
assigned later — clobbered their onclick. Symptom was subtle: the first tab
appeared to work (its content was already populated by the 60s poller) while
clicks did nothing. Scoped to `.ftab:not(.rt):not(.dt)` and moved the drawer
tabs to addEventListener so no future assignment can silently win.

**Verified end-to-end:** rail tabs = [feed, acct]; empty state renders the real
funnel; SETUP TRACE ▸ opens the drawer on trace (flex, content loaded); PIPELINE
tab switches (DEGRADED · EVALUATION ALLOWED, stages listed); FULL PANEL lazy
loads the iframe; feed sub-tabs (ACTIVE/FORMING/DEAD/CLOSED) still switch. One
stale test updated to the new gate contract. 75 tests green.

---

## S24 — 2026-07-26 — ApexShell bridge (diagnostics reach the mothership)

**Ask:** surface SniperSight's issues in ApexShell's tracker, with a button to
hand them to the war room / an agent.

**Discovery — no new ApexShell code needed.** Its Tracker already ships an
`http-json` monitor source (main/monitors/sourceHttp.js, registered in
index.js): it polls `GET {base}/api/state` for
`{panes:{<id>:{data,log,busy}}}` and posts `{paneId,actionId}` to
`{base}/api/action` (202 accept / 409 busy). So the work was to make
SniperSight speak that contract, then add one pane entry.

**Built:** `engine/apexbridge.py` + `/api/state` + `/api/action`. The pane
carries: pipeline LED (audit status), verdict, blocker/warning counts, scanner
liveness, paper equity, active setups, an Open Issues list (blockers first,
then warning codes with counts), a monotonic activity log, and two buttons.

**Deliberate boundary — no "fix it" button.** Verbs are allow-listed:
`audit` re-runs the quality audit; `brief` writes a war-room dossier
(war-room/diagnosis-<ts>.md) containing the verdict, every blocker with
evidence, warnings by code, the recorded rejection funnel, repro commands, and
the rules any fixer must follow (§7: new algo_version, never edit in place).
Unknown verbs are refused (400) and logged. The shell OBSERVES and can package
a problem; a human still dispatches the fix. Letting a dashboard button
auto-remediate a trading engine is precisely the unaudited mutation §7/§13
forbid.

**Bug caught in verification:** the pane's buttons were declared with an
`actions` key, but renderer/monitors.js reads `w.items` — they would have
rendered as an empty box. Fixed after reading the renderer rather than assuming
the schema from the README. Also verified led vocabulary (good/warning/
critical) and list row shape ({name,value}) against the renderer source.

**Verified live:** state payload binds every widget; `audit` -> 202
{"ok":true,"detail":"DEGRADED"}; `brief` -> 202 and wrote a real dossier;
`{"actionId":"rm -rf"}` -> 400 refused and logged. panes.json backed up to
panes.json.bak before edit. 75 tests green.

---

## S24b — 2026-07-26 — "4 actionable" reconciled; orphaned-symbol blocker fixed

**User caught a contradiction:** the cockpit badge said 4 ACTIONABLE while the
new ApexShell pane said 0 blockers and I had just told them nothing needed
attention. The user was right and I was wrong — I had quoted an audit snapshot
taken minutes earlier instead of re-reading.

**What the 4 actually were:** 4 pipeline blockers at that moment (3 pending 4H
aggregates + 1 gap series). By the time I looked again, three had aged out and
ONE was real: MISSING_AGGREGATE on ONDO-USD 4H.

**Root cause (a genuine bug, not noise):** ONDO had DROPPED OUT of the admitted
universe, and the live loop only aggregates the admitted scan set — while the
audit (and risk, and the server) iterate ALL TRACKED symbols. So a symbol that
leaves the universe keeps its 1H imports but stops being rolled up: ONDO had 1H
data to 07:00 and 4H stuck at 00:00, with all four source candles present. That
bucket could never be emitted, so the gate would have blocked forever, and it
would recur on every universe rotation. Fix: live.py now aggregates every
tracked symbol (a cheap roll-up of candles already held) while engines and
scanning stay scoped to the admitted set. Re-aggregation wrote 38,505 missing
higher-timeframe candles across the tracked set; audit back to 0 blockers.

**Surface consistency:** the pane now publishes `actionable` computed by calling
the very endpoint the badge calls (lazy import to dodge the circular import),
rather than a re-implementation — two surfaces reporting different numbers is
worse than either being wrong. Added as the pane's first stat, so it also feeds
the collapsed tracker-bar chip.

**Performance defect found by measurement, not assumption:** a COLD /api/state
took **72.7s** (full audit contending with the scanner's writes) while warm
polls took 0.37s. ApexShell's sourceHttp.js times out at **6s** — so every
cache expiry would have rendered the pane "svc offline". The endpoint now NEVER
audits inside the request: it serves the last known verdict, refreshes in a
daemon thread, and reports "AUDIT PENDING" on the very first poll after start.
Measured after the fix: 0.45s / 1.03s / 0.007s / 0.005s — all inside the
timeout. RE-AUDIT still forces a synchronous fresh run and reseeds the cache.

75 tests green.

---

## S25 — 2026-07-28 — UI redesign phase 1: design system, shell, glossary

**Operator verdict on the old UI: "terrible AI slop."** Measured before touching
anything: 14 distinct font sizes, 31 interactive elements, 15 tabs, and a footer
that was five unrelated facts glued with pipes — telemetry cosplaying as
insight. Root cause was not styling: the screen displayed what the ENGINE
produces instead of answering what the OPERATOR must decide.

**Interviewed rather than guessed** (operator's instruction). Answers set the
plan: build live rails but keep live locked; audience is "me now, everyday user
later"; Coinbase + Phemex; one setup per token with a challenger the user
approves; longs AND shorts with optional leverage; manual chart edits tagged and
excluded from edge stats. Plan written first: docs/REDESIGN-PLAN.md.

**Found the real brand instead of inventing a third one.** snipersight-trading
carried a full design system (docs/DESIGN-SYSTEM.md, copied here) and the logo:
a gunmetal scope ring with a GREEN reticle. My cyan-on-black HUD was off-brand
as well as undesigned. Adopted verbatim: OKLCH olive-tinted surfaces (never
#000), dynamic --accent (green rest / amber armed / red live), Share Tech Mono
for chrome, Inter for prose only, JetBrains Mono for numbers, scanlines as a
2-bit overlay, motion slow and non-celebratory.

**Built:** `ss.css` (the system), `shell.html` (five surfaces: COMMAND, CHART,
RESULTS, SCANNER SETUP, DIAGNOSTICS — each answering exactly one question),
`shell.js` (nav + live wiring), `glossary.js` (57 terms; every domain word on
screen explains itself on hover — the operator's "lingo I have no idea what it
means"). Fonts vendored locally (~100KB) so there is no runtime dependency on
Google. Old cockpit preserved at /legacy until its chart moves in phase 2 —
deleting a working tool before its replacement exists leaves you with neither.

**Measured after:** exactly **6 font sizes** (10 / 11.5 / 13 / 16 / 26 / 32),
saturated colour **0.3%** of screen against the system's ≤10% rule, 25 glossary
terms live, all surfaces carrying real data.

**Root-cause fix found while wiring (not cosmetic):** the shell's health chip
sat blank because `/api/pipeline-health` still ran a FULL synchronous audit —
the same 72-second path already fixed for the ApexShell pane but never at the
source. Two surfaces had independently cached the same verdict, which is how
they disagreed on 2026-07-26. Added `quality.cached_audit()` as the single
shared verdict (background refresh, `force` for buttons); both the endpoint and
the bridge now read it. Response time went from hanging to **7ms**. 89 tests green.

---

## S26 — Backend console + a real Run Scan button (phase 1 close-out)

**Asked:** "i click run scan, is there some sort of console that can expose
whats happening on the back end?"

**Found first:** Run Scan was a **placeholder**. It POSTed the ApexShell `audit`
verb and refreshed — it never scanned. The label lied about what the button did,
which is the worst kind of UI bug in a system whose whole premise is that the
screen tells the truth.

**Built:**
- `POST /api/scan` — runs `live.cycle(con, log)` in a daemon thread. Deliberately
  the *same code path the live loop runs*, so a manual scan can never diverge
  from an automatic one. Facts are content-hashed and idempotent, so overlapping
  with the scanner's own tick duplicates nothing. Returns 409 if one is running.
- `GET /api/console` — byte-offset tail of `data/engine.log`. Chose the shared
  log file over an in-process ring buffer **because both the scanner process and
  the server write there**; a ring buffer would have shown the operator half the
  story.
- COMMAND gets a Backend Console panel: severity-coloured, Following/Paused,
  bounded buffer, and the scan state chip.

**Three defects found by verifying instead of assuming — all real, all mine:**

1. **Check-then-set race.** `if _scan["running"]` and the assignment were not
   atomic, and uvicorn runs sync endpoints on a threadpool. Four concurrent
   POSTs all passed the guard. Added `_scan_lock`; retest gave exactly one 202
   and three 409s.

2. **Cursor drifted BACKWARD every poll.** The console kept showing a fragment
   like `"ckpit"` — the tail of "cockpit" — after every refresh. Cause: the log
   is **CRLF**, and `open(..., "r")` universal-newline mode collapses `\r\n` to
   `\n`, so `len(text.encode())` undercounted the file by **one byte per line**.
   The cursor fell behind a byte per line and re-read already-painted bytes,
   landing mid-word. Fixed by reading **binary** and decoding after slicing, so
   the offset is byte-exact. This is the second time a Windows text-mode
   assumption has cost real debugging time — offsets into a file must always be
   computed in bytes.

3. **Trailing and leading partial lines.** The engines are mid-write while we
   read, and the first fetch seeks to `size-8192` which lands mid-line. Now the
   read stops at the last `\n` (remainder reported as `pending`) and a clamped
   first seek discards the half line it landed in. Client-side, overlapping
   polls (the click handler's poll racing the 2s interval) fetched the same
   offset twice and double-painted; added a `polling` re-entrancy guard.

**Also:** the backend now owns "is a scan running", so reloading the page
mid-scan shows the same button state as the tab that started it.

**Verified:** 6 sequential polls — cursor monotonic, zero fragments. Live poll
during an active scan — zero fragments, `pending` drains to 0. Browser after
hard reload — 83 lines, **0 fragments**, 83 colourised, COMMAND intact
(universe 37, equity $10,000).

**Dud recorded:** my first verification loop declared the server up while the
*old* process was still answering, then the connection refused mid-test. Waiting
on `/api/status` is not proof of a restart when the thing you restarted is the
process answering that endpoint.

---

## S27 — Phase 2: the CHART surface and the order ticket

**Built:** `chart.js` (chart + overlays + draggable levels), `ticket-math.js`
(the arithmetic, pure and testable), `GET /api/trade-config`, and the CHART
markup/CSS. `tests/test_ticket_math.js` — 13 cases, run under node.

**The chart owns the screen.** Symbol picker, five timeframes, five overlay
toggles (swings, structure, zones, liquidity, cycle), regime and live price
chips, and a 320px order ticket rail.

**Levels are draggable.** `createPriceLine` draws them; DOM tags positioned by
`series.priceToCoordinate()` are the grab targets. Dragging freezes
`handleScroll/handleScale` — otherwise the viewport pans out from under the
cursor. Every drag recomputes the ticket live.

**Why the maths moved to its own file:** this is the code that decides how big
a trade is, so it gets tested like it. `ticket-math.js` has no DOM, runs under
node, and covers inverted stops, shorts, fee-dominated scalps, buying-power
breaches, and the no-equity case. It reads `risk_pct`, `max_leverage` and the
fee rates from `/api/trade-config`, which reads them off `engine/risk.py` and
`engine/costs.py`. Hard-coding them in JS is precisely how two surfaces came to
disagree about equity on 2026-07-26.

**The ticket shows R:R AFTER FEES, not just gross.** This is the number that
matters and the one the old UI never showed. Measured live:
  · COTI-USD 1D SHORT (real engine setup): gross 6.10 → **net 5.77**. Wide
    structural stop, fees are noise. Gross 6.10 matches the engine's own `rr`
    field exactly — the ticket and the engine agree independently.
  · BTC-USD 4H seeded 2R trade: gross 2.00 → **net 1.10**. Half the edge is fees.
  · A 0.1% stop on a 60k asset: gross 3.00 → **net NEGATIVE**. A guaranteed
    loser that looks like a 3R trade. That asymmetry — fees on notional against
    a stop measured in ticks — is what sank the intraday book, and it is now on
    screen instead of buried in a backtest.

**Nothing hand-tuned is ever labelled "engine".** The ticket carries a source
chip: `engine` (accent) only while untouched; `operator-modified` the instant
anything is dragged, typed, flipped or trailed; `operator-seeded` where no
setup exists. Where there is no engine setup the levels are seeded from the
average 14-bar range and the WHY panel says outright that they are the
operator's and count toward nothing.

**Two defects found by exercising it, both real:**

1. **Reset was a dead end.** Reset restored only *engine* levels, so on a symbol
   with no setup an operator who dragged into an invalid state had no way back —
   the button stayed disabled. Replaced `engineLevels`/`origin` with a single
   `base` (kind `engine` or `seeded`) plus a `modified` flag. Whatever the chart
   started from is now restorable, and Reset enables exactly when something was
   changed.

2. **Handle placement lived only inside the rAF loop.** A backgrounded tab
   suspends rAF, so the grab tags would have been stale the moment the operator
   came back. Extracted `placeHandles()`, called directly on every level change;
   rAF now only tracks pan and zoom.

**Verified:** deck "Open chart" carries symbol *and* timeframe and lands on the
engine setup (`engine` · entry 0.01322). Switching COTI 1D → 4H correctly drops
to seeded because no setup exists there. Edit → Reset → flip direction → Reset
round-trips cleanly. Wrong-side stops and targets are refused with a plain
sentence, never silently negated. Zero console errors. 89 python + 13 js green.

**Not done, deliberately:** `/legacy` stays up. Its telemetry and account views
have no replacement yet, and deleting a working tool before its replacement
exists leaves you with neither. Arm stays disabled and reads its lock reason
from `/api/trade-config` — the UI does not get to decide that live is allowed.

**Environment note for future sessions:** the automated browser pane runs with
`visibilityState: hidden`, so `requestAnimationFrame` never fires and
lightweight-charts cannot paint or resolve `priceToCoordinate`. Chart *rendering*
cannot be verified there — data, maths, state and wiring can. Do not read a
0x0 `chartBox` as a layout bug.

---

## S28 — Operator feedback: zoom, dead toggles, and a setup the engine refused

Three complaints, and the third exposed the worst UI defect built so far.

**1. Chart opened unreadably zoomed out.** `fitContent()` squeezed 1500 bars
into one screen. Now opens on a 120-bar working window via
`setVisibleLogicalRange`; full history is still there to scroll back through.

**2. Overlay toggles "don't seem to do anything" — they didn't.** Measured on
COTI 4H: every one of the 12 structure facts is a `LABEL` event, and
`drawOverlays()` did `if(f.event === 'LABEL') continue`. So the Structure toggle
drew *nothing* on that chart. LABEL is HH/HL/LH/LL — that IS the market
structure the strategy reads, and it was the one thing being thrown away.
Liquidity and cycle genuinely have zero facts on that timeframe, and swings
render only 17 of 257 because MICRO/LOCAL are noise tiers.

Fixed by rendering labels, and by making each toggle carry its live fact count:
`Swings 17`, `Structure 12`, `Zones 8`, and struck-through `Liquidity` /
`Cycle` when nothing exists. A control that silently draws nothing is
indistinguishable from a broken one; the count is the difference between "no
data here" and "this button is dead". BTC 1D correctly shows `Cycle 35`.

**3. "No universal account balance visible from any screen."** Correct — equity
lived only on COMMAND and RESULTS, so on the chart the ticket said "risk $200"
without ever showing what it was 2% *of*. Equity is now a topbar chip on every
surface, with start equity and open risk in the tooltip.

**The real find.** Chasing "it doesn't show the dollar amount", the deck's one
active setup — COTI-USD 1D SHORT, R:R 6.10 — turned out to be **REJECTED by the
risk authority** (`NOT_IN_POINT_IN_TIME_UNIVERSE`, `risk_usd: 0`). The dollar
amount was missing *because the engine refused to size it*. The deck was
presenting a refused setup as an opportunity, complete with an Open Chart button
and no hint of the verdict. That is the single most dangerous thing this surface
can do: invite the operator to size a trade the engine already declined.

Both surfaces now carry the verdict, from the same fact:
  · deck row dimmed, `REJECTED` chip, reason in plain words
  · ticket shows `RISK AUTHORITY: REJECTED` above the rationale, ending
    "This setup would not be traded. Anything below is analysis only."

`kind=risk` had to be added to `KIND_VERSIONS` — the generic `/api/facts`
allow-list rejected it with a 400, which would have blanked the chart. Caught
before shipping by testing the endpoint rather than assuming it.

**Scanner Setup / Risk** now reads live values from `/api/trade-config` instead
of hard-coded prose, and states plainly why the fields are not yet editable:
`risk.run()` rebuilds the account by replaying every setup, so changing the
percentage in place would re-size the entire forward record under an unchanged
`algo_version` — a §7 violation. The envelope is coupled too (total cap holds
two concurrent, daily halt is ~3 stop-outs), so no value moves alone.

**Open decision:** operator chose *auto-derive with override* for the coupled
limits. How history is treated when risk changes is still undecided — the
question was asked and answered with a different concern, so it stands.

**Verified:** 89 python + 13 js green, zero console errors, deck and ticket agree.

---

## S29 — The universe was partly a coin flip (universe-v0.2-draft)

Found while answering "if R:R was so great why did it refuse it?". The COTI
answer was mundane — the coin entered the top-20 volume list 13 hours AFTER the
trade was judged, and it was a short on spot besides. But the universe snapshots
around it were churning 3-5 symbols between refreshes minutes apart.

**Root cause, measured not guessed.** `rank_by_volume()` stats every online USD
pair to rank it (388 calls). It ran 6 workers with no throttle and no retry —
`REQUEST_PAUSE = 0.15` was defined at module level and never referenced. Probing
Coinbase directly: 150 requests at 6 workers took 3.0s (~50 req/s against a
~10 req/s public limit) and returned **59 HTTP 429s out of 150 — 39% refused**.

Because a different subset failed each run, "top 20 by volume" was really "top
20 of whichever two thirds answered". A pair could enter the top 20 purely
because bigger rivals failed to load. `admitted_at()` gates every trade on that
snapshot, so **trade eligibility was partly determined by which network calls
happened to succeed** — and it silently polluted the forward record the whole
project exists to produce.

**Fix, in three parts:**
1. `_RateLimiter` — process-global minimum spacing at 10 req/s. Deliberately
   shared, not per-worker: N workers each sleeping 1/N s still burst N at once.
2. `_get()` retries 429/5xx with exponential backoff, honouring `Retry-After`.
   Retry matters as much as throttling — without it one 429 silently drops a
   symbol, and a dropped symbol is indistinguishable from an illiquid one.
3. **`refresh()` now fails CLOSED below 97% coverage.** It logs loudly and keeps
   the previous universe rather than recording a plausible wrong one. v0.1 wrote
   the bad snapshot every time; only a *total* fetch failure aborted.

**Measured before → after:**
  · coverage 72% → **100%** (387/387, 0 failures, 39s)
  · 429s 39% → **0**
  · membership churn between consecutive snapshots 3-5 symbols → **0**
  · confirmed on three live production snapshots: churn 0, coverage 99.7-100%

**Version bumped to universe-v0.2-draft** (§7). The admission *rules* are
unchanged — only the completeness of their input — but the outputs differ, so
reading v0.1 snapshots as if they came from the fixed sweep would be a lie. The
bump costs almost nothing here: the forward baseline contained exactly 1 setup,
1 (rejected) risk decision and 1 exec.

**Tests:** `tests/test_universe_coverage.py`, 11 cases, no network. Covers global
(not per-thread) limiter spacing, 429-retry-then-succeed, 404-never-retried,
give-up-after-N, the coverage gate accepting/refusing either side of the floor,
injected rankings bypassing the gate, and the version bump itself. 100 python +
13 js green.

**Noted, not fixed:** a full scan cycle takes ~250s but scanner liveness is
judged at 150s, so the UI reports SCANNER DOWN mid-cycle on healthy runs. That
is a false alarm in the liveness threshold, not a scanner fault.

---

## S30 — Per-trade risk override, honest liveness, and why the setups dried up

**Per-trade risk override.** Operator directive: "if I decide to risk more for
one particular trade it shouldn't affect any others." That is cleaner than any
of the three history-handling options I offered — it needs no version bump and
cannot touch the record. `ticketMath` takes `riskUsdOverride`; the engine keeps
owning the 2% default. The override resets on every setup load and on symbol
switch (verified: switching BTC→ETH returned to $200/2.00%). Breaches are coded
not worded — `RISK_EXCEEDS_TOTAL_BUDGET`, `RISK_EXCEEDS_DAILY_HALT` — so the
arithmetic stays testable without asserting on prose. 8 new tests, incl. that a
later trade is unaffected and that `cfg` is never mutated. **Caught by test:** my
fixture omitted `daily_loss_pct`, so the halt guard silently no-opped behind
`|| 1`. Fixture now mirrors `/api/trade-config` and is asserted against it.

**Scanner liveness.** The heartbeat was written only AFTER `cycle()` returned,
so a ~250s pass left a 250s silence against a 150s threshold — healthy runs
reported SCANNER DOWN. Raising the threshold would only have hidden real hangs.
Instead the live loop now beats at every stage and the threshold DROPPED to 90s,
which now genuinely means stuck. First attempt still false-alarmed at 92s: the
universe stage beat once and then blocked for ~40s inside the throttled ranking
sweep. Added a `progress` callback through `universe.refresh` → `rank_by_volume`
(fires every 20 symbols, ~2s apart). Re-measured across a full cycle: worst
heartbeat age **52s**, never falsely down. The phase is now surfaced in the UI —
"SCANNER · UNIVERSE 200/387", "· ENGINES BTC-USD".

### The setup drought — diagnosed, and it is structural

6.7 days produced 1 setup. Breakdown of 400 rejections:
`NO_ELIGIBLE_PLAYBOOK` 358, `UNECONOMIC_AFTER_COSTS` 35, `RR_BELOW_MINIMUM` 7.

Split by whether the timeframe can even survive fees:

| cause | 4H/1D/1W | 15m+1H |
|---|---|---|
| TRANSITION regime but no liquidity sweep | 23 | 161 |
| RANGE regime has no playbook entry at all | 8 | 82 |
| counter-trend (correctly skipped) | 8 | 74 |

**317 of 358 misses are on 15m/1H — timeframes already proven uneconomic after
fees.** On timeframes that can actually pay, there were only 41 misses in a week.
The gates are not the main problem; higher-timeframe zone touches are just rare.

**Three structural ceilings, measured:**
1. **Only 19 Coinbase USD pairs clear the $3M liquidity floor.** `TOP_N` is 20,
   so the cap is NOT the binding constraint — the floor is. Rank 20 is already
   $2.97M, rank 30 is $1.6M. **Widening the universe on spot is impossible.**
2. **31% of all validated setups are SHORTs (44 of 143), and every one is
   rejected** — `ALLOW_SHORTS = False` on Coinbase spot. A third of the strategy
   is dead on arrival at this venue.
3. RANGE (18% of current symbol-timeframes) has no play at all; TRANSITION (43%)
   trades only with a sweep. ~61% of market conditions are untradeable by design.

**Conclusion: the throughput ceiling is the VENUE, not the calibration.** Longs
only, 19 symbols, high timeframes — roughly one setup a week, which cannot
produce forward evidence in any useful timescale. Phemex perps (operator
confirmed it works from the US) restores shorts and lifts the liquidity ceiling.
It should be reprioritised ahead of the settings work; it is the unlock, not a
later feature. Loosening the sweep requirement is the alternative lever and is
deliberately NOT taken here — it would be a strategy change made to manufacture
volume, which is how you fool yourself.

---

## S31 — Phemex perp adapter, and a correction to S30

**CORRECTION.** S30 concluded perps would "lift the liquidity ceiling". Measured
against the live API, that is **wrong**. At the $3M/24h floor:
  · Phemex USDT perps above floor: **20**
  · Coinbase USD spot above floor: **21**
Phemex is a mid-tier venue and its own turnover is not deeper than Coinbase's at
the top of the book. The union is **27 symbols** (14 overlap), so adding it is a
~29% widening, not a transformation. The real and still-decisive unlock is
**shorts**: 31% of all validated setups (44 of 143) are currently rejected
outright by `ALLOW_SHORTS = False`. Stated plainly so the reasoning does not
outlive the evidence.

  phemex-only above floor: AVAX BNB DEXE ENA 1000PEPE 1000SHIB
  coinbase-only above floor: ACH COTI HYPE PUMP UNI VVV ZEC

**Built `engine/phemex.py`** — public market data only. Endpoint contract
verified live 2026-07-29; the v1 kline paths and the v2 `limit` form both return
HTTP 400, and `/exchange/public/md/v2/kline/list?symbol&resolution&from&to` is
the one that works. Same throttle/retry design as universe-v0.2 (process-global
limiter, backoff on 429/5xx).

**Measured live:**
  · 466 USDT perps listed, ranking coverage 466/466 with **no fan-out** — one
    ticker call covers every symbol, so the partial-coverage failure mode that
    broke Coinbase ranking cannot occur here by construction.
  · BTCUSDT 1D: **399 candles** (history gate needs 200), zero duplicate
    open_ts, strictly ascending.
  · 4H served **natively** — Coinbase forces aggregation, Phemex does not.
  · Funding rate available per symbol (BTCUSDT 1.314e-05) — a real holding cost
    on perps that belongs in the cost model, not a footnote.
  · Cross-venue sanity: BTC last close 63,899.5 (Phemex) vs 63,847.1 (Coinbase),
    0.08% apart — normal basis, and good evidence both feeds are sane.

**Row layout trap, covered by test:** rows are
`[ts, resolution, lastClose, open, high, low, close, volume]`. Element 2 is the
PREVIOUS close, not this bar's open. Reading it as the open shifts every candle
by one bar — silently, and in a way that would corrupt every structure fact
downstream.

**13 tests, no network.** Includes: USDC-settled and delisted contracts
excluded; unlisted ticker symbols never ranked; forming candle never returned;
dedupe + ascending; the field mapping above; a no-forward-progress guard so a
misbehaving venue cannot spin the fetch loop; and a source-level assertion that
the module contains no key/secret/hmac/signature/order strings — market data
only, credentials stay the operator's and live stays locked.

113 python + 21 js green.

**Still to wire:** venue seam proper — `ALLOW_SHORTS` must become venue-derived
rather than a global False, cost profile per venue including funding, and the
universe/importer paths parameterised by venue. That is the remaining Phase 4
work and it touches the risk authority, so it needs its own version bump.

---

## S32 — Venue seam: shorts unlocked, and the fee finding that dwarfs it

**Built `engine/venues.py`** — the single place that knows what a market ALLOWS.
Venue is derived from the symbol string (`BTC-USD` -> coinbase spot, `BTCUSDT` ->
phemex perp), so no schema change was needed. An unrecognised symbol RAISES
rather than defaulting, because guessing a venue means guessing whether shorting
is allowed; `risk.py`'s wrappers then fall back to the SPOT answer (refuse the
short, 1x) so an unknown symbol is never assumed shortable.

**risk-v0.7-draft.** `ALLOW_SHORTS` and `MAX_LEVERAGE` are no longer process
constants. Sizing rules (2%/4%/6%) are untouched, but SHORT setups on a
shorts-capable venue now reach sizing instead of being rejected outright, so
decisions differ — hence the bump. The `venue_contract` in the account fact is
now a list of what each venue allows rather than one hard-coded Coinbase claim.

**Liquidation gate** ported. On a leveraged perp the exchange can close a
position before the stop is hit, at a loss LARGER than the one risked — which
makes the stop decorative and every downstream R-multiple fiction. Modelled with
a 0.5% maintenance allowance so liquidation sits NEARER than the naive
1/leverage estimate; the failure to avoid is believing a stop is safe when it is
not. Verified at 10x long from 100 (liquidation 90.50): stops at 96 and 92
allowed, 90 and 85 rejected.

**Funding** is charged per settlement (3/day on Phemex), not once. A perp held
three days pays 0.09% of notional at a 0.01% rate; spot pays zero.

### The fee finding — larger than the shorts unlock

Perp round-trip fees are **0.07% of notional against 1.00% on spot, 14x cheaper**.
Run through the actual ticket maths, holding gross R:R at 3.00:

| stop distance | gross | net SPOT | net PERP |
|---|---|---|---|
| 0.1% (tight intraday) | 3.00 | **-7.00** | **+2.30** |
| 0.3% | 3.00 | -0.33 | +2.77 |
| 1% | 3.00 | +2.00 | +2.93 |
| 3% (swing) | 3.00 | +2.67 | +2.98 |

A tight intraday trade loses **seven times what it risks** on spot and makes
2.30R on perps. This reframes S30's drought diagnosis: **317 of 358
`NO_ELIGIBLE_PLAYBOOK` misses were on 15m/1H**, timeframes written off as
uneconomic — and they were uneconomic *at spot fees*. Plus the 35 explicit
`UNECONOMIC_AFTER_COSTS` rejections. So perps plausibly lift throughput by close
to an order of magnitude, not the 29% symbol-widening I estimated in S31, and
not primarily via shorts either. Both earlier estimates were too pessimistic for
the same reason: I reasoned about symbol counts instead of cost structure.

`/api/trade-config` now takes `?symbol=` and answers per venue; `chart.js`
re-reads it on every symbol load. Showing spot fees on a perp chart would flip
the sign of the net-R decision, so this is correctness, not polish. Unknown
symbols fall back to the COSTLIER venue.

**134 python + 21 js green** (21 new venue tests: resolution, unknown-symbol
raising, conservative fallbacks, liquidation both directions, funding accrual,
and that the declared perp cap stays <= 10x against the venue's own 100x).

**Not yet done in Phase 4:** nothing ingests Phemex candles into the store yet —
`universe.py` still ranks only Coinbase and `importer.py` still only fetches it.
The adapter and the capability model are in place; the ingest path is next.

---

## S33 — Phemex ingest wired end to end (importer-v0.3, universe-v0.3)

**importer-v0.3.** The fetch is routed by `venues.venue_for(symbol)`, and the
`source` column now records WHICH venue served the bar. It was hard-coded
`"coinbase"` — which would have labelled Phemex perp candles as spot data, and
the quality audit's known-venue-gap allowances are keyed on source, so the
mislabel would have applied Coinbase's gap rules to a venue that has none.
`_fetch_rows()` normalises both shapes (Coinbase returns
`[t, low, high, open, close, vol]` positionally, Phemex returns dicts) so the
OHLC integrity check and the storage path stay venue-agnostic — two copies of
that validation is exactly the duplication that drifts apart.

**Deliberate non-optimisation:** Phemex *can* serve 4H natively and Coinbase
cannot, but `native_tfs()` returns the same set for both and the aggregator
builds 4H everywhere. A natively-fetched 4H would occupy the same
`(symbol, tf, open_ts)` row the aggregator writes — two writers for one bucket,
which is how they disagree at a gap and the audit reports a conflict it cannot
explain. One saved request is not worth a second write path.

**Live ingest verified** into a scratch DB: `BTCUSDT` 1D, **300 candles, 0 gaps,
0 malformed**, `source='phemex-perp'`, first 2025-10-02 last 2026-07-28. The 1H
-> 4H aggregation then ran on the same perp symbol: 59 candles, all
`source='agg:1H'`, no duplicate writer.

**universe-v0.3** ranks across venues via `rank_all_venues()`, deduped by
underlying asset with the **perp preferred** where a coin trades on both. That
is not taste: 0.07% vs 1.00% round-trip flips the same 3.00-gross trade from
-7.00R to +2.30R, so routing an overlapping asset to spot would knowingly pick
the version that loses money. Spot-only coins are kept — they have no perp.
`ENABLE_PERPS = False` restores exact v0.2 behaviour. A perp-ranking failure
degrades to spot-only with a loud warning rather than emptying the universe.

**Bug caught before shipping:** the SEED block re-added `BTC-USD`/`ETH-USD`
unconditionally. With perps preferred, `BTCUSDT` already represents BTC, so the
seed would have put the SAME UNDERLYING in the universe twice — two positions on
one coin, each counted separately against `MAX_CONCURRENT=2`. That is double
exposure the risk envelope never agreed to. SEED now skips any base asset
already present.

**Merged top-20 measured live: 20 perp, 0 spot** — Phemex turnover exceeds
Coinbase's on every overlapping coin. 21 pairs clear the $3M floor, same count
as spot-only, but they are now the cheaper, shortable versions.

138 python + 21 js green.

**Operational consequence the operator must decide on:** every admitted symbol
is now a perp the store has no history for, so all of them enter WARMING and
need a 200+ daily-candle backfill from Phemex. The existing Coinbase history is
not deleted (append-only) but stops being the traded set. This is a real change
of what the forward record measures and should not be started silently.

---

## S34 — Perps live: 87 setups in one cycle, and two bugs the switch exposed

Operator approved switching the traded universe to perps. Executed: universe
refreshed across venues, all 20 admitted symbols onboarded from Phemex.

**Bug 1 — the listing-date gap (silent, and it hit the timeframe that matters).**
`DEXEUSDT` onboarded with **1D=0** while 1H=4320 and 15m=2880. Cause:
`ingest.DAILY_SINCE` is 2022-01-01 and `phemex.fetch_candles` did `if not rows:
break`. DEXE listed 2024-12-25, so the FIRST 1000-day window came back empty and
the loop aborted before ever reaching the data. Any symbol listed after the
first window silently got zero daily candles — and daily is exactly what the
history gate counts, so those symbols would sit in WARMING forever, never
admitted, with no error anywhere. An empty window means "nothing listed yet in
this range", not "no data": the loop now skips the span and keeps looking,
bounded by the range width so a fully-empty symbol still terminates. DEXEUSDT
now backfills **582 daily candles from 2024-12-25**. Two tests added.

**Bug 2 — one symbol's 429 killed the whole cycle.** `live cycle failed: HTTP
Error 429` aborted the entire scan; every other symbol went unimported because
one call failed. Two causes, both fixed:
  · The rate limiter is process-global but NOT machine-global, and the scanner
    and API server both hit Phemex. Two processes at 10/s each produced
    sustained 429s that outlasted the retries. Phemex is now 5/s with 5 retries
    and a 1s base backoff, leaving headroom for both processes.
  · The import loop is now per-symbol fault-tolerant: a venue error skips that
    symbol with a warning and the cycle continues. The next cycle retries it and
    any resulting gap is recorded honestly either way.
The same loop also stopped hard-coding `source='coinbase'` in its
last-candle query (it now excludes `agg:%`), which would have re-imported every
perp symbol's whole history on every single cycle.

**Result, measured:**
  · clean cycle: `330 new candles, 87 new setups (103.2s)` — against **1 setup
    in 6.7 days** on spot. The cycle is also ~2.5x faster than the old 250s.
  · zero errors, zero skipped imports across the monitored run
  · scanner never falsely reported down; phase visible throughout
    (`universe 300/388` -> `import ETHUSDT (2/20)` -> `engines DOGEUSDT (9/20)`)
  · 20 perps admitted, 0 warming, all with >=200 daily candles

**Setup population now on the store:** perp 142 LONG / 7 SHORT, spot 106 LONG /
49 SHORT (spot figures are historical Coinbase data, retained not deleted).

**Correctly zero risk decisions so far.** Every one of those 87 setups confirmed
BEFORE the baseline reset at 2026-07-29 12:58, so none are eligible for the
forward record — the engines were processing four years of newly-imported perp
history. The forward record starts accumulating from the next live setup. The
shorts capability is proven by test and by direct check (`BTCUSDT -> SHORT
reaches sizing`), NOT yet by a recorded live decision; `SHORT_UNSUPPORTED = 0`
in the store means "no decisions yet", not "shorts are passing".

140 python + 21 js green.

---

## S35 — Notification discipline: the alerts were never trades

Operator report: non-stop notifications. Measured the store before touching
anything. Real VALIDATED setups over the preceding ten days: **4, 1, 2, 0, 0, 1,
0, 0, 1, 0** — about one a day. The scanner was not the noise source.

**Bug 1 — history announced as live.** `cycle()` collected every setup fact with
`id > before` and announced it. Row-newness is not event-newness: onboarding a
symbol backfills years of candles, the engines re-derive every setup those years
contained, and all of them arrive as brand-new rows. That is the "87 setups in
one cycle" from S34, and it was still running — the last twelve setup facts
written were dated 2025-01-22, 2025-02-25, 2025-03-10, 2026-04-03, 2026-04-28.

Two gates now, both already the house rule elsewhere: `confirmed_at >=`
baseline start (the same filter every `/api` surface uses to decide visibility),
and at most `ANNOUNCE_MAX_BARS = 2` late *in the setup's own timeframe*, so a
3-hour-old 15m signal is history while a 3-hour-old 1D signal is fresh. What is
filtered is logged with counts — suppression must never be silent, or the
operator cannot tell a quiet market from a swallowed notifier.

**Bug 2 — drift measured the importer, not the market.** `check_drift` compared
live price against the last stored 15m close with no staleness check. When
imports lag, the reference ages, a normal multi-day move reads as a violent
intracandle spike, and since the dedupe only spaces alerts one per 15m bucket it
re-fires every fifteen minutes indefinitely. Measured 07-26..29: **139 alerts,
over half from two symbols** — COTI-USD and EUL-USD, whose reference closes were
**2.8 and 3.5 days old**. `drift-v0.2-draft` mutes any symbol whose reference bar
closed more than `DRIFT_MAX_REF_AGE_BARS = 2` bars ago, logs the mute once per
bucket (a fix that trades an alert flood for a log flood is not a fix), and
records `ref_age_s` on every alert fact.

**Bug 3 — found while fixing 2: drift was 100% blind and merely noisy about it.**
`live._spot()` and `marketdata.fetch_tickers()` both hard-coded the Coinbase
ticker endpoint. Correct while the universe was spot; wrong the moment S34 made
the traded set Phemex perps. `BTCUSDT` is not a Coinbase product, so every
request 404'd: twenty warnings a minute in `engine.log`, zero drift coverage on
the entire traded universe, and `/api/ticker` reporting DEGRADED for everything.
Which is also why 100% of the spam came from leftover *spot* symbols — the perps
threw before they could alert.

`marketdata` is now venue-routed. Perps use a new `phemex.last_prices()`: one
batched `/md/v2/ticker/24hr/all` call for every symbol rather than one request
each, reading `closeRp` (last **traded** price — `markPriceRp` is an
index-anchored fair value and comparing it against a traded close would report
drift that never happened). A symbol the venue cannot price is absent from the
mapping, never defaulted to zero.

**Verified live:** 20/20 universe prices resolved (was 0/20), one dry cycle
produced 0 alerts and 0 log lines.

**Not changed — deliberately.** `ANNOUNCE_STATES` still includes FORMING, and the
announce path still does not consult the risk authority's verdict, so a setup
`risk.run()` rejected thirty lines earlier in the same cycle can still toast.
Both are operator policy, not engine correctness; they are now single constants
rather than inline literals so either is a one-line change once the operator
decides.

**Also measured while in here — the gate that actually matters:** of 8,102
candidates rejected at the strategy gate, **7,149 (88%) are
`NO_ELIGIBLE_PLAYBOOK`** — price touched a real zone but no playbook covers that
regime. That is not a threshold to tune, it is the absence of a second strategy.

164 python + 21 js green (17 new). The 9 failures in `test_cockpit_diagnostics`,
`test_default_cockpit_route` and `TestCockpitHierarchy` are pre-existing:
`static/index.html` is staged for deletion in the working tree while `server.py`
still serves it at `/legacy`. Untouched here, but it needs resolving.

---

## S35 — Phases 3, 5 and 6: settings, guardrails, and /legacy retired

### Phase 3 — operator settings (`engine/settings.py`)

The tension: the system is built on versioned deterministic behaviour, but the
operator wants to change things without editing code. Those coexist only if a
change is RECORDED and its cost is stated. Three classes:

  · **BEHAVIOURAL** (perps on/off, top_n, liquidity floor, strategy toggles) —
    changes what the engines produce. Automatically **starts a new baseline**,
    because a record spanning two configurations cannot say which one produced
    which result. Nothing is deleted.
  · **OPERATIONAL** (halt, drawdown limit, data-health gate) — changes WHEN
    trading stops, not what counts as a valid trade. Audited, **never** resets
    the baseline.
  · PREFERENCE — per-trade risk override, which lives in the ticket.

**Bug caught by building it:** `halted` was first classed BEHAVIOURAL, so the
first halt started a new forward window. A safety control that destroys the
evidence it protects punishes exactly the caution it exists to allow.
Reclassified, with the reasoning in the code and a test that pins it.

Settings are wired through, not decorative: `universe.refresh` reads top_n /
min_volume / enable_perps once per refresh (once, so a mid-refresh edit cannot
classify half the universe under each config), and `risk.run` reads the halt and
strategy toggles once per run.

**Credentials (`engine/credentials.py`)** — Windows DPAPI, encrypted to the
operator's own account. `keyring` is not installed here; pywin32 is, so DPAPI is
used directly. Verified: the plaintext does NOT appear in the vault file. No
route can read a secret back — `status()` returns booleans, and a test parses
`server.py`'s AST to assert no handler ever CALLS `read_secret` (a substring
match failed on the docstring that documents the rule). Vault is gitignored.
Claude never enters or transports keys; a stored key does not unlock live
trading, which is a separate gate and still closed.

### Phase 5 — guardrails

**The total-drawdown halt did not exist.** `risk.py` had a DAILY loss halt and
an open-risk cap, but nothing catching a slow bleed: a run of small losses can
drain the account without any single day breaching -6%. Added: peak-equity
tracking, a `DRAWDOWN_HALT` fact, and rejection of later entries with the
breach in the reason. Default 20% from peak.

**Data-health halt** — new entries are refused while the pipeline audit reports
BLOCKED. Trading on data known to be broken produces a record attributable to
the corruption as much as to the strategy. Fails OPEN if the gate itself errors,
so a broken check cannot wedge trading.

Driven to a real halt in test: eight stop-outs on eight separate days, none
breaching the daily limit, cumulatively -15% against a 5% cap — halt fires and
subsequent entries carry `DRAWDOWN_HALT` in their reasons. **Two fixture bugs
found on the way**, both mine: `risk.run` scopes to symbols that have CANDLES
(none inserted), and facts must post-date the baseline (mine used epoch-relative
stamps). The same scoping that correctly excluded the 87 imported perp setups.

An always-visible **HALT** sits in the topbar on every surface; the whole shell
restates the state when engaged.

### Phase 6 — /legacy retired

Every surface it uniquely served now has a replacement: chart + ticket (CHART),
equity curve and per-symbol/strategy breakdown (RESULTS), setup telemetry beside
the rejection funnel (DIAGNOSTICS — the operator's "one place for debugging").
Route removed and `static/index.html` deleted rather than left dark: a second UI
over the same facts is a second place for them to disagree, which is exactly how
two equity numbers diverged on 2026-07-26.

Three test files asserted against the deleted file. **Retargeted rather than
deleted** — the properties still matter: equity/halt/scanner state must be
persistent chrome outside any surface (asserted by index position, before
`<main class="stage">`), diagnostics must expose verdict + funnel + telemetry
together, and no page may embed the app in itself.

Curve and breakdown render honestly on an empty window — "no closed trades in
this window yet" rather than a flat line implying data.

**163 python + 21 js green.** Zero console errors. `/legacy` returns 404.

---

## S36 — Clean baseline, and 108 warnings that were crying wolf

**Baseline #5 "Forward paper baseline"** started 2026-07-30 02:30 UTC under
setup-v0.6 / risk-v0.7, replacing the stale `config change: halted` label left
behind while `halted` was briefly misclassified. Non-destructive as always.

**The 199 warnings, diagnosed.** 108 `STALE_SERIES`, and every one was on a
retired Coinbase spot symbol — **zero on a live perp**. Switching the traded
universe to perps meant those series correctly stopped updating, and the audit
kept reporting them forever.

That is not a cosmetic problem. 108 permanent warnings bury the ONE series that
goes quiet while it still matters — the same cry-wolf failure as the 1,364
blockers that wedged the scanner for days. Staleness is only meaningful for a
symbol still in the scan universe: a symbol deliberately dropped has RETIRED
data, not stale data. The check is now scoped to `universe.current_symbols`, and
**fails OPEN** — if the universe cannot be read it warns rather than silently
suppressing.

**Bug found while fixing it, worse than the original.** My first pass cached the
live-symbol set in a module global with a 30s TTL. That cache is keyed on
nothing, so it is shared across CONNECTIONS — an audit of one database would
suppress warnings in another. It surfaced as an unrelated test failing, because
a previous test's cache leaked into it. Removed; the set is computed once per
audit and passed down. A test now asserts `_LIVE_CACHE` does not exist.

**Measured after:** warnings **199 -> 91**, all explained:
  · `KNOWN_VENUE_GAPS` x90 — venue-acknowledged empty buckets, already a
    documented SERVE_FLAG degradation, not corruption
  · `UNATTRIBUTED_LEGACY_FACTS` x1 — pre-baseline history
  · `STALE_SERIES` **x0**
Blockers 0, evaluation allowed.

183 python + 21 js green.
