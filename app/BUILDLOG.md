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
