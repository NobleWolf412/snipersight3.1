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

---

## S36 — Confirmed entry: the defect is fixed, the edge is not (yet) there

**setup-v0.7-draft.** `TOUCH -> CONFIRMING -> VALIDATED`. A zone touch no longer
IS a trade; it is a candidate that must be proved by a closed bar which engages
the zone, closes back out of it, AND closes in the top third of its own range
(rejection, not drift). Entry moves to the next bar's OPEN — a price that
demonstrably traded, so no fill assumption is needed. Stop moves to the
confirmation bar's own extreme, a level the market visibly rejected. Targets cap
at 3R, with `tp_uncapped` recorded alongside so the cap can be graded later.

**Measured geometry change:** stop distance went from **0.30x to 0.93x** the
trigger bar's range. The v0.6 stop sat inside the noise of the bar that created
the signal; that is why 59% of stop-outs landed on the fill bar.

**The 2x2 (`engine/abtest.py`).** Entry and exit both changed, so a single
before/after could not attribute the result. The harness calibrates first —
replaying v0.6 under the production cost model and comparing against the exec
facts execsim actually wrote — and refuses to report if it cannot reproduce
them. It reproduced 142 trades / -102.8R as 141 / -101.6R, 1.2% drift.

On the traded universe (20 perps):

| cell | n | win% | expectancy | same-bar |
|---|---|---|---|---|
| touch + hold (v0.6) | 53 | 11.3% | -0.433 R | **57.4%** |
| touch + managed | 53 | 30.2% | -0.028 R | 70.3% |
| **confirmed + hold** | **114** | **30.7%** | **-0.017 R** | **13.9%** |
| confirmed + managed | 115 | 31.3% | -0.171 R | 20.3% |

**The managed exit (partials + trail + breakeven) is REJECTED by its own gate.**
It makes the confirmed entry worse. It was specced from excursion data measured
on the broken entry: a 1.53R median MFE was a symptom of trades dying early, not
proof that 1.5R is where to cut them. Once the stop is wide enough for a trade to
run, cutting half at 1.5R and moving to breakeven caps the winners.

**The near-miss.** Across all history the touch+managed cell read +0.322R, PF
1.69, P(>0) 99.4%. Then the concentration check: **96% of that profit came from
three illiquid retired spot alts** — LSETH-USD, DIA-USD, COTI-USD, two of them
the same symbols whose stale candles produced the S35 drift spam. Dropping the
top 3 trades left +0.189R with a CI including zero. A confident statistic, and
wrong.

**Honest verdict:** confirmation fixed the defect it was built for and made the
book measurable. It did not create an edge. -0.017R with a CI straddling zero is
flat. What it bought is a fair test for the strategy work that follows.

### Two bugs found along the way, both in production code

**1. The cost profile was venue-blind.** Every one of the 232 exec facts carried
`coinbase-retail-v1` (1.00% round trip) while the traded universe has been 100%
Phemex perps (0.07%) since S34 — a 14x over-charge. It bit hardest in the GATE
direction: `MIN_RISK_COST_MULT` demands risk >= K x round-trip cost, so an
inflated cost demanded a ~14x wider stop before a setup counted as economic.
`costs.profile_for(symbol)` is now venue-derived and falls back to the COSTLIER
profile on an unknown symbol. `UNECONOMIC_AFTER_COSTS` rejections on the perp
book went **675 -> 0**; those were real setups screened out on another venue's
fees.

**2. `quality._AUDIT_CACHE` answered questions about one store using another's
verdict.** It was a single module-level dict keyed on nothing, and its background
refresh called `store.connect()` with NO argument — so it audited the DEFAULT
store regardless of which connection the caller passed. Invisible with one
database. Not invisible with two: `risk.py`'s data-health gate read a cached
BLOCKED verdict belonging to a different store, rejected every intent as
DATA_HEALTH_BLOCKED, and a drawdown-halt test then observed no halt — because no
position ever opened to draw the account down. It failed only when run alongside
other tests. Now keyed by database path, and the background refresh runs ONLY
against the default store; any other store gets an honest `None` (pending)
rather than a borrowed answer. Six regression tests pin it.

**Also wired:** `settings.strategy_pullback` / `_reversal` / `_scale_in` have
existed as BEHAVIOURAL settings with a working API since S34 and nothing ever
read them — the switches were inert. `setups.playbook()` now honours them and
the active set is recorded in the strategy manifest.

**315 python tests green**, 1 skipped.

**Open, deliberately not done here:** `execsim.py` still holds to SL/TP; since
the managed exit is rejected, that is now correct rather than pending. Confluence
is recorded on every v0.7 setup and gates nothing — `engine/factorstats.py`
grades it before any of it is allowed to become a filter.

---

## S37 — Version collision, and the book turns gross-positive

**Two defects, one root cause: identity.**

`setup_id` was `{symbol}|{tf}|{strategy}|{zone_id}` with NO version component, so
setup-v0.6 and setup-v0.7 minted the SAME id for the same zone. Measured on the
live store the moment both versions were resident: **136 ids present in BOTH
books; 130 of 346 exec facts joined to a setup that existed twice.** One order
came back FILLED and MISSED at once. Every downstream join — execsim, risk,
telemetry, the trace endpoint — merged them silently, because a join on a
colliding key cannot tell that it is merging. Ids are now version-scoped.

The other half: **execsim kept writing `exec-v0.7-draft` while simulating v0.7
plans**, so one version label covered two strategy generations. A version tag
whose meaning changes underneath it is worse than none, because every consumer
trusts it. `exec-v0.8-draft` separates them, and it was overdue on its own
merits — the spec had already stated that setups/execsim/risk/scalein must bump
together or the pipeline reads new facts under old assumptions. It did exactly
that for one session.

**exec-v0.8 also fixes two things the version bump made unavoidable:**
  · cost profile is venue-derived (was Coinbase spot on a 100%-perp universe —
    a 14x over-charge on fees AND on the slippage that prices every stop)
  · fee role follows the strategy's DECLARED entry model. setup-v0.7 enters
    MARKET at the next bar's open, which pays TAKER; charging maker understated
    cost by ~0.045 R/trade while claiming a fill model the plan never asked for.

**Production pipeline re-run end to end (58 symbols, all timeframes):**

| | v0.6 + exec-v0.7 | v0.7 + exec-v0.8 |
|---|---|---|
| filled trades | 142 | **304** |
| MISSED orders | 90 (39%) | **0** |
| win rate | 12.8% | **30.3%** |
| expectancy | -0.641 R | **-0.084 R** |

**The finding that changes what to do next.** On the live book
(n=217, `/api/edge-stats`):

```
mean net    -0.037 R    CI95 [-0.260, +0.195]   P(>0) 37.1%
mean GROSS  +0.093 R
mean costs   0.130 R
break-even fee  0.033% per side
```

**The strategy is now gross-POSITIVE and cost-negative.** That is a different
problem from the one this session started with, and a better one: the entry no
longer donates to noise, and what remains is an execution-cost problem with
known levers — maker entry instead of taker, fewer and larger trades, or a
venue with a better fee tier. The break-even fee sits at 0.033%/side against
Phemex maker 0.01% / taker 0.06%: entering maker rather than taker would put
the book above water on these numbers alone.

Stated plainly so it is not over-read: the CI still crosses zero. This is not a
proven edge. It is a book that is no longer proven to be losing, with the
remaining gap attributable to a cost line rather than to the thesis.

**Also shipped this session (six parallel workstreams):** `edgestats` (bootstrap
CI, break-even fee), `factorstats` (five-axis factor grading incl. pairwise
redundancy), `entrystats` (fill rate, adverse selection, entry-location probe),
`abtest` (the calibrated 2x2), Learn surface (8 chapters, 8 interactive SVG
widgets, each stamped with the engine version it documents), playbook catalogue,
Market Weather, staged rejection funnel with bottleneck pill, per-setup trace
drawer, diagnose wizard, and `/api/edge-stats` + its panel.

**315 python + 50 js tests green.**

---

## S38 — Maker-then-market entry, and the TRANSITION gate finally fires

### 1. Entry model, chosen by measurement

Three variants through `abtest`, confirmed entry + hold exit, perps, n=228:

| model | expectancy | P(>0) | missed |
|---|---|---|---|
| MARKET_NEXT_OPEN | -0.017 R | 43.6% | 0 |
| MAKER_PULLBACK | +0.074 R | 70.8% | 32 |
| **MAKER_THEN_MARKET** | **+0.115 R** | **82.2%** | **0** |

**A first attempt at the maker variant was wrong and had to be thrown away.** It
rested the limit AT the next bar's open, which is marketable — it crosses the
spread and pays TAKER — so it was claiming a maker rebate the exchange would
never have granted. It scored +0.028 R on a free lunch invented by the model.
The honest version rests 0.10 R BETTER than the market and must genuinely wait.

That honest version is **adversely selected**, exactly as v0.6's resting limits
were: its 32 unfilled orders would have made **+0.365 R each** at market against
**+0.074 R** for the ones that filled. Price walks away precisely when the trade
is right. Saving a fee by declining those trades pays for the fee with the edge.

So: post passive, cross if unfilled after 2 bars. Both legs load-bearing — the
passive leg because the book's break-even fee is 0.033%/side against a 0.06%
taker, the crossing leg because the passive leg alone forfeits the winners.
Production confirms both fire: 169 maker fills, 249 crosses.

### 2. TRANSITION: 5 setups in four years -> 429

The REVERSAL playbook demanded a liquidity sweep within 10 bars. The entire
store holds **98 SWEEP facts** across every symbol and timeframe, so the play
fired five times, ever — while TRANSITION accounted for 2,959 of 7,149
`NO_ELIGIBLE_PLAYBOOK` rejections (41%). That was not a confluence requirement,
it was a lottery ticket.

Replaced with **2 of 4 independent components**, one per information type:
`CHOCH` (structure) · `SWEEP` (liquidity) · `VOLUME` (participation) ·
`STRENGTH` (location). One is noise; all four reproduces the original problem at
a new threshold. Rejections now record WHICH components were present, so the
funnel can say "you were one component away" instead of "no playbook".

**Measured, perps only, exec-v0.8:**

| strategy | n | win% | sum R | expectancy | CI95 | P(>0) |
|---|---|---|---|---|---|---|
| PULLBACK | 339 | 30.1% | +0.1 | +0.0004 R | [-0.187, +0.193] | 50.0% |
| **REVERSAL** | **209** | **34.9%** | **+67.6** | **+0.324 R** | **[+0.055, +0.598]** | **99.1%** |
| ALL | 549 | 31.9% | +66.7 | +0.122 R | [-0.033, +0.280] | 93.6% |

**This is the first confidence interval this project has produced that clears
zero.** It was put through the same concentration check that killed the last
99% result:

  · top 3 TRADES = 15% of profit (the retired-spot artifact was 43%)
  · CI still clears zero after dropping the top 3 trades; straddles at top 5
  · positive on ALL FOUR timeframes (15m +23.4, 1H +34.2, 1D +8.6, 4H +1.4) —
    the artifact was 1D-only
  · 11 of 17 symbols positive
  · **top 3 SYMBOLS = 82% of profit** (ETHUSDT, XRPUSDT, AAVEUSDT) — high, and
    the reason this is promising rather than proven. Unlike the artifact these
    are major liquid perps in the ACTIVE universe, not retired illiquid alts,
    but 82% from 3 of 17 needs forward confirmation before it is believed.

PULLBACK at +0.0004 R is exactly flat, consistent with every other measurement
of it this session. The book is carried entirely by the strategy that could not
previously fire.

### 3. Copy that had started lying

Changing the gate made three user-facing strings false — the Market Weather
cell, the Reversal playbook card, and the planned-card rationale all still said
"needs a liquidity sweep within 10 bars". A user reading that would be told a
trade was impossible when it had become merely conditional. All three now derive
from `setups.REVERSAL_COMPONENTS` / `REVERSAL_MIN_EVIDENCE` via one helper,
and the tests assert the RULE as the engine states it rather than a sentence.

Four tests encoded the old rule. All four were **updated to encode the new one**,
not deleted — the property each protected (TRANSITION must not trade on regime
alone; the UI must state the real condition) is unchanged.

**354 python tests green**, 1 skipped.

---

## S39 — `rank` retired. It sorted the deck backwards at its own mode.

`engine/factorstats.py` graded every v0.7 confluence field against 228 closed
`exec-v0.8` trades. The composite the deck sorted on does not survive.

**The ablation is the whole argument** (book-wide noise floor +/-0.130):

| score | r vs realised R | verdict |
|---|---|---|
| `rank` as shipped | +0.210 | clears |
| `rank` MINUS its +10 HTF term | **+0.111** | **inside the floor** |
| that +10 HTF term ALONE | **+0.261** | clears |

A single 10-point term outscores the whole 100-point composite. The other 86% of
the score's variance is `pts_volume` (45.1% of variance, r=+0.09) and
`pts_rr_good` (40.6%, r=+0.03) — neither clears its own floor, and together they
do not merely fail to help, they DILUTE the one term that works.

**And it is non-monotone, which a correlation hides:**

```
rank 50   n= 30   win 40.0%   +0.027 R
rank 65   n=116   win 13.8%   -0.643 R   <- worst bucket, 51% of the deck
rank 75   n= 32   win 56.2%   +1.082 R
rank 80   n= 40   win 45.0%   +0.641 R
```

The lowest bucket beats the modal bucket by 0.67 R/trade. A number that orders
the deck backwards where most of the deck sits is not a confidence score, and
showing it as one invites the operator to trust an ordering the data contradicts.

**Rebuilding it was considered and rejected**, because the obvious replacement
inputs are one signal wearing four names: `zone_quality` is algebraically
`50 + min(30, 10*cluster) + TF_WEIGHT[tf]` and `zone_strength` is
`(quality + freshness)//2` — the identity verified on 228/228 trades. Pearson
only caught the pair at r=1.00 because the clamp breaks linearity elsewhere.
Rebuilding from "strength + quality + cluster" would triple-count the cluster and
smuggle the timeframe in three times. That is the previous project's 26-factor
failure reproducing itself inside one 10-field block.

**Shipped instead:**
  · The deck sorts by **expiry urgency** — which decision dies first. Setups
    expire after `ENTRY_MAX_BARS`, so it is operationally true and claims
    nothing it cannot support. The countdown is rendered ON the card: a deck
    ordered by an invisible key is worse than one ordered by a bad score.
  · `rank` stays in the payload (history must stay readable) but is no longer
    displayed or sorted on, with the measurement recorded at the site.
  · HTF context is a **three-state label** — TRENDING / FLAT / **UNKNOWN**.

### The UNKNOWN state is a bug fix, not a display choice

`if conf.get("htf_regime_aligned")` scored None identically to False, so a
MISSING measurement was penalised exactly like a CONTRARY one. Measured: unknown
-HTF trades ran **38.9% win / +0.404 R**, genuinely opposed ones **17.2% /
-0.616 R**. Folding them together is a 1.02 R/trade libel.

And it fell entirely on one book. `htf_regime` is None on 74/230 setups, and
**68 of those are the whole 1D book** — the only profitable timeframe. Root
cause traced: `HTF_LADDER["1D"] = "1W"`, 1W regime needs `structure` facts,
`structure.TIER_BY_TF["1W"] = "MAJOR"`, and 194 weeks of perp history yields
**14 MAJOR swings across 11 symbols** — one or two each, far too few to form an
alternating sequence. So 1W structure exists for 1 perp symbol out of 21, and
the 1D book cannot have an HTF regime at all. It was being docked 10 points for
a data gap it has no way to close.

A missing measurement must never be scored as a bad measurement.

**Not yet done, and named so it is not lost:** backfill deeper 1W history (or
demote `TIER_BY_TF["1W"]` under a structure version bump) so the 1D book becomes
measurable, then re-grade. `htf_trending` (r=+0.473, n=156) currently beats
`htf_regime_aligned` (+0.42), which hints the real signal is "the higher
timeframe is trending at all" rather than "it agrees" — but trend-but-opposed is
n=16 and was correctly REFUSED, so direction remains untested.

**357 python + 50 js tests green.**

---

## S40 — The tick floor: 44 of 59 symbols could not see a break

Commissioned a range-detection engine to attack the "27% of rejections are
ranging markets" gap. It came back with the gap's actual cause instead.

**`TICK = Decimal("0.01")` is hard-coded in `structure.py`, `zones.py` and
`liquidity.py`, and the break rule is `max(TICK, 0.05*ATR)`.** That is the right
tick for BTC-USD and catastrophically wrong below a dollar. Measured across all
59 tracked symbols: **on 44 of them `0.05*ATR` is SMALLER than 0.01** on at
least one timeframe — 185 of the 293 symbol/tf series in the store, evaluated at
each series' latest ATR-bearing bar.

State the method with the number, because the number MOVES: ATR is
re-measured every bar, so a borderline symbol crosses the 0.01 line in both
directions as data arrives, and a figure quoted without its method cannot be
reproduced later. Earlier passes in this section recorded 34 and 35 for the same
predicate; 44 is what the same query returns now. The conclusion is not
sensitive to that drift, which is the point of recording it.

Per-symbol, on 15m, taking the median ATR over the series:

```
SHIB-USD        median ATR 4.0e-8      0.05*ATR 2.0e-9      floor is 5,000,000x larger
PUMP-USD        median ATR 0.00001284  0.05*ATR 6.420e-7    floor is    15,576x larger
u1000PEPEUSDT   median ATR 0.00001331  0.05*ATR 6.655e-7    floor is    15,026x larger
u1000SHIBUSDT   median ATR 0.00001577  0.05*ATR 7.885e-7    floor is    12,682x larger
```

A tolerance larger than any move the instrument makes means **no close ever
breaks any level**. The store shows exactly that: SHIB-USD had **0 breaks against
101 labels**, PUMP-USD **0 against 145**. And `regime._classify` returns RANGE
when `last_break is None` — so those symbols sat in a permanent, false RANGE, and
that is where most of the "ranging market" bucket came from. It was never a
ranging market. It was a blind structure engine.

**Fix:** the tick is read from the exponent of the venue's own price strings
(`swings.quote_ticks`), as a RUNNING maximum over past bars so it stays causal
and idempotent — a later bar quoted to more decimals can never change an already
emitted fact. It returns exactly 0.01 wherever 0.01 was right.

One landmine closed on the way in: the original returned `Decimal(1)` when a
series carried no fractional digits, which would inflate the tolerance *worse
than the bug being fixed*. An unknown tick now returns ZERO and lets the ATR term
govern — the conservative direction. No real venue row in the store is
integer-quoted; a test fixture was, which is exactly when a landmine matters.

**And it stayed open in a second copy.** `ranges.py`, where the derivation was
first written, kept its own `quote_ticks` returning `Decimal(1)` for that case
after the shared one in `swings.py` had been corrected to `0` — two
implementations of one convention, already disagreeing, in the exact way that
having one definition is supposed to prevent. `ranges.py` now imports the shared
one and the copy is deleted. Verified a no-op before deleting it: the two
functions return identical tick vectors on all **295** candle series in the
store, so no range fact changes and `ranges-v0.1` does not need a bump — the
disagreement was confined to a case no real venue row reaches. The dead
`TICK = Decimal("0.01")` constants left behind in `structure.py`, `zones.py` and
`liquidity.py` are removed too, and `ranges.break_tolerance` now REQUIRES its
`tick` argument rather than defaulting it to 0.01, so the constant cannot creep
back in via a caller that forgets to pass one.

**Version cascade, all forced:** `structure-v0.9`, `zone-v0.10`, `liq-v0.9`,
`regime-v0.9` (no rule change — it classifies FROM breaks), `setup-v0.8`,
`exec-v0.9`. Not one of these changed a rule. Every one changed its facts, and
S37 already recorded what happens when a version tag covers two generations.

### Measured effect

Re-measured against the persisted store, old version vs new, so every figure
below is a query someone else can re-run rather than a number from a scratch
recomputation. Structure breaks, `structure-v0.8` -> `structure-v0.9`, label
count unchanged in every case (labels do not depend on the tolerance):

```
u1000SHIBUSDT   1 -> 52   (127 labels)      XLMUSDT    20 -> 53
DOGEUSDT       10 -> 44                     ADAUSDT    22 -> 48
ENAUSDT        14 -> 50                     ONDOUSDT   32 -> 51
OPUSDT         17 -> 47                     XRPUSDT    36 -> 45
```

And the control — symbols where 0.01 already WAS the tick are byte-identical,
which is the claim `swings.quote_ticks` makes about itself:

```
BTCUSDT  47 -> 47     ETHUSDT  52 -> 52     BNBUSDT  55 -> 55     AAVEUSDT  50 -> 50
```

The headline the range engine was commissioned against, strictly like-for-like
on the 20 symbols that carry both generations of rejection facts:

```
NO_ELIGIBLE_PLAYBOOK        3,535 -> 1,109
...of which regime=RANGE    1,010 ->   176      (877 -> 176 on the same 20 symbols: -80%)
RANGE as a share of NEP      28.6% -> 15.9%
```

u1000SHIBUSDT alone accounted for 290 of the old 877 and now accounts for 6. The
176 that remain are the real ranging population, and they are no longer
concentrated in the sub-dollar symbols: 74% sit on tick-affected symbols now
versus 92% before, i.e. what is left is spread across the book rather than being
one instrument's blindness.

**The gap that hid this, and the backfill that closed it.** `live.cycle` runs the
engines over `universe.current_symbols` — the scan universe, 19 symbols — not
over `all_tracked_symbols`, now 76. A tracked symbol that leaves the scan set
keeps whatever facts it had on the way out, so the blinded generation survived
in place for every symbol the scanner had stopped looking at. That is why an
earlier draft of this section reported "SHIB-USD 0->35, PUMP-USD 0->40" as
measured effect and the store disagreed: those symbols had no post-fix facts at
all, the numbers came from an ad-hoc recomputation, and nothing had been written.

The description layer has now been re-run over the 40 tracked symbols that
lacked current-version facts (`swings -> structure -> zones -> liquidity ->
regime -> ranges` plus the indicator engines, the `pipeline.PER_SYMBOL` order,
431s, no errors). The claim is finally a query rather than an assertion —
labels/breaks, blinded generation vs now:

```
SHIB-USD  101L /  0B  ->  104L / 43B        ACH-USD   123L /  4B  ->  125L / 60B
PUMP-USD  145L /  0B  ->  145L / 63B        HBAR-USD  146L /  6B  ->  147L / 64B
USDT-USD   95L /  0B  ->   98L / 13B        DOGE-USD  153L / 13B  ->  159L / 63B
```

All three symbols that could not print a single break now print them. Across the
59 symbols carrying both generations, total breaks went **2,294 -> 3,344**, and
regime RANGE share over the same set **18.1% -> 15.1%**. `structure-v0.10` and
`regime-v0.10` now cover all 76 tracked symbols with none missing.

**The trading engines were deliberately NOT run in this backfill.** `setups`,
`execsim`, `scalein` and `cooldowns` would add simulated trades on symbols
outside the scan universe, and `edgestats`/`factorstats` grade that population —
so extending it is a decision about what the edge numbers MEAN, not a
housekeeping step, and it does not get made as a side effect of fixing
structure. The description layer is now correct everywhere; whether the book
should include symbols nobody is scanning is a separate question.

**The REVERSAL result survived a change that reclassified a third of the market,
and got MORE robust:**

| | before tick fix | after |
|---|---|---|
| n | 209 | **250** |
| expectancy | +0.324 R | +0.277 R |
| CI95 | [+0.055, +0.598] | **[+0.036, +0.521]** |
| P(>0) | 99.1% | 98.8% |
| top-3 symbol concentration | 82% | **72%** |
| symbols positive | 11/17 | **13/21** |

CI still clears zero after dropping the top 3 trades. The top symbols also
CHANGED (XRPUSDT out, ENAUSDT in), which is the useful part: a result that holds
while its own composition turns over is not a story about three symbols.

PULLBACK fell to n=98 / -0.061 R — many BULL/BEAR_TREND classifications became
TRANSITION, so the book moved from the flat strategy to the one with an edge.

### Range fade: NOT built, and the evidence says do not

`ranges.py` (v0.1, 21 tests) detects 1,882 ranges across the store. Of the
RANGE-regime rejections, **3 had a live detected range at the moment of
rejection; one had the touched zone inside the band.** Of the rejections on
structure-SOUND symbols, **zero** did. A range fade has essentially nothing to
trade. The engine is kept as the measurement that proves it, and because the
question becomes live again once ranges are defined over something longer-lived
than four consecutive local pivots — a 6-bar median box describes a sub-box
inside a macro range, never the range itself.

**378 python green (1 skipped, 27 subtests); js suites green.** The consolidation
added no new test function — it is a deletion, and the existing tick tests in
`test_ranges.py` now exercise the shared `swings.quote_ticks` through `ranges`
rather than a private copy. `test_break_tolerance_floors_at_one_tick` gained one
assertion: that calling `break_tolerance` WITHOUT a tick raises. That assertion
is the only thing standing between the shared derivation and a silent 0.01
default creeping back in.

---

## S41 — Completion pass: the backlog closed, and a guard so one bug stops recurring

Worked the outstanding items A-to-Z. Two were closed by evidence rather than
built, which is recorded here as the deliverable rather than as a gap.

### A — correctness debt, self-inflicted

`risk.py` and `scalein.py` still carried v0.7/v0.2 after S40 moved setup-v0.8 and
exec-v0.9. Both import those constants, so their FACTS changed while their TAGS
did not. **That is the S37 defect committed a second time — while writing the
note explaining the first one.**

Fixed, and then fixed properly: **`tests/test_version_cascade.py` is a version
lockfile.** Any version move now fails the suite until the tuple is updated,
which forces a deliberate look at everything downstream. It also asserts the
consumer map describes the CODE (each listed consumer must actually reference the
constant it claims to read), that no two engines share a version string, and that
every version names its own engine. The fix for this bug was never vigilance.

It earned its keep within the hour: the E1 change below tripped it immediately
and drove a five-engine cascade that would otherwise have been missed again.

`ranges.py` was also built, tested and **never wired into `live.ENGINES`** —
dead in production. Now runs.

### B — cooldowns (SPEC §1.7, never built)

Nothing prevented re-entering a level that had just stopped the system out.
Tolerable at 5 REVERSAL setups in four years; not at 471. `cooldowns.py`:

  · **stop-out -> long lockout** (4h scalp / 12h intraday / 24h swing). The level
    was INVALIDATED; re-entering re-buys a refuted thesis.
  · **target or time exit -> short lockout** (0.25h / 0.5h / 1h). The level
    RESOLVED, it did not fail. One number for both necessarily gets one wrong.

Per (symbol, direction) — not per zone, because a stopped-out demand zone sits in
a cluster and its neighbour is the same trade wearing a different `zone_id`.
DERIVED from exec facts rather than held as live state: mutable state cannot be
replayed, and a cooldown that cannot be replayed silently changes which trades a
historical run would have taken. Wired into `risk.py` as a rejection reason that
names the exit which caused it.

Two bugs caught by its own tests: `record()` reported success even when the
content-hash made the insert a no-op (so a re-run would report fresh cooldowns
forever), and the first `risk` integration issued two queries per intent inside
the hot loop.

### C — measurement

**C1 confound guard** in `edgestats`. Every slice is tagged with the engine
generations behind it; a slice living entirely on one side of a version boundary
is CONFOUNDED and labelled, never silently compared. Six versions moved in S40
and that re-measurement was done by hand. Includes a **materiality floor** —
3 orphan rows out of 340 were flagging 3 of 4 timeframes, and a label that cries
wolf gets ignored, which costs more than the label is worth.

**C2 — the rejected exit bundle, graded component by component.** A bundle
verdict is not a component verdict:

| exit | n | win% | sum R | expectancy | P(>0) |
|---|---|---|---|---|---|
| **hold to SL/TP (shipped)** | 348 | 31.6% | **+63.3** | **+0.182** | 96.1% |
| + partials only | 348 | 45.7% | +43.3 | +0.125 | 94.5% |
| + time stop only | 352 | 41.2% | +26.1 | +0.074 | 81.6% |
| **+ trail/breakeven only** | 351 | 34.8% | **-13.8** | **-0.039** | 24.8% |
| all three (rejected bundle) | 352 | 37.2% | -3.6 | -0.010 | 42.7% |

**Trail/breakeven is the poison** — the only component negative alone. And the
shape is diagnostic: win rate RISES with every component added (31.6 -> 45.7%)
while expectancy FALLS. That is cutting winners early, exactly. Holding remains
correct, now for a measured reason rather than an unexamined default.

### D — confluence candidates, recorded and gating nothing

D1 premium/discount (where price sits in its range — orthogonal to zone quality,
which measures a level, not a location). D2 HTF composite (three correlated
readings at r up to 0.93 collapsed to one three-state field, so a future scorer
cannot count one signal thrice). D3 **VETO pattern** — gates are not weights; a
veto cannot be outscored, and the two implemented describe trades that cannot be
EXECUTED as planned rather than ones that are unattractive. D4
`participation_rate` — REDUCES rather than rejects, because a position too large
for the book is a bad size, not a bad trade. Inert in paper by nature, which is
exactly why it had to exist before live.

**D5 sessions/kill zones — closed with cause.** Perps trade 24/7; the concept
earns its keep at the equities/forex boundary. Adding an ungraded factor to a
book that cannot test it is the failure this project keeps documenting.

### E — the 1W blind spot, closed

`structure.TIER_BY_TF["1W"] = "MAJOR"` needed a DOUBLE recursion the data cannot
support: 194 weekly bars yield 14 MAJOR pivots across 11 symbols, one or two
each. So 1W structure existed for 1 perp of 21, 1W regime for 1, and the ENTIRE
1D book had no higher-timeframe regime — while `htf_regime_aligned` was the only
confluence factor ever measured above the noise floor.

The golden-data A/B that chose MAJOR tested **1D** and grouped 1W in without
separate evidence. 1W now uses INTERMEDIATE (18 of 21 perps have enough pivots);
1D stays MAJOR, because that one was tested and won.

Result: 1W regime for **20 perp symbols (was 1)**. The 1D book went from 100%
UNKNOWN to **54 TRENDING / 70 FLAT / 19 UNKNOWN** — and the factor now separates
outcomes across the whole book:

```
TRENDING   n=198   win 35.9%   meanR +0.258
FLAT       n=380   win 26.8%   meanR -0.108
UNKNOWN    n= 45   win 24.4%   meanR -0.244
```

A 0.37 R/trade spread, both groups far above the n>=30 floor — and it confirms
the S39 hypothesis that the real signal is **"is the higher timeframe trending
at all"**, not "does it agree". Still recorded, still gating nothing:
`factorstats` grades it before it earns a weight.

REVERSAL held at **+0.277 R, CI [+0.037, +0.520], P(>0) 98.8%** through this
cascade — its fourth consecutive survival of a change to its own inputs.

### F — strategy registry, deliberately thin

Wave 2.1 specifies a registry where each strategy owns its bracket. This one does
not build that, and the reason is the point: PULLBACK and REVERSAL share every
mechanic and differ only in which regime admits them, range fade is closed by
evidence, so a bracket-owning interface would today hold two identical brackets —
the speculative generality this codebase argues against everywhere.

What DOES exist is a real duplication with a real cost: strategy metadata was
hand-written in `server.py` while behaviour lived in `setups.py`, and they drifted
(the "needs a liquidity sweep" copy survived a full session after the engine
stopped requiring one). `registry.py` is the single declaration both read, held
against the ENGINE by tests rather than against prose. The full Wave 2.1 shape
becomes correct when a strategy needs a different bracket — that is the trigger,
not a version number.

Also removed: the "Reversal, Reworked" PLANNED card, whose work shipped in S38.
It described the OLD rule while the live Reversal card described the new one, so
the roadmap contradicted the catalogue on the same page.

### Operational

The scanner had been in a **crash-restart loop** (rc=1 every ~30s since 05:58).
Cause: the watchdog respawning a process that imports `engine/*.py` **while those
files were being rewritten** — by two background tasks and by this session at
once. Not a code defect; a concurrency hazard worth naming, because the watchdog
faithfully turns a transient half-written module into a tight restart loop.
Verified stable after edits settled: 100s clean run, `--once` exit 0, and the
live store now carries setup-v0.9 / exec-v0.10 / structure-v0.10 / regime-v0.10.

**393 python + 50 js tests green.** 992,592 facts.

---

## S42 — Indicator engines: the three confluence categories structure cannot see

`ma`, `momentum`, `volatility`, `volume` — v0.1 each. They fill TIMING,
CONDITION and PARTICIPATION; the structure layer already owned LOCATION and
DIRECTION, and those three rows had no measurement at all.

**Every one emits on STATE CHANGE, never per bar**, which is what keeps them
affordable: RSI is defined on every bar and interesting on few. A per-bar design
over 570,061 bars would have written millions of rows into a 992k-fact store.

| engine | fires on | facts | % of bars |
|---|---|---|---|
| `ma` | ribbon state tuple (stack, position, slope) changes | 121,577 | 21.3% |
| `momentum` | RSI band · MACD signal · MACD zero · divergence at a pivot pair | 99,093 | 17.4% |
| `volatility` | squeeze ON/OFF · ATR regime LOW/NORMAL/HIGH | 59,050 | 10.4% |
| `volume` | RVOL *arrival* of HOT/DRY · VWAP cross · POC move >= 1 ATR | 156,772 | 27.5% |

Every threshold pair is a **Schmitt trigger** (enter 70 / exit 65; enter 2.0x /
exit 1.5x; +/-0.25 ATR slope deadband), with the reason measured rather than
asserted: a raw one-bar EMA20 slope sign flips on **14.2% of bars** (73,091
times); deadbanded over 5 bars it flips on 3.3%.

`volume` came in at **215,605 on its first pass — over the ceiling — and was
redesigned rather than shipped**: emitting the RETURN to normal RVOL was 24.5%
of every bar, a per-bar emitter wearing a state machine. Emitting only the
ARRIVAL of unusual participation brought it to 156,772.

### Three findings recorded rather than smoothed over

**The house break tolerance does nothing for chatter here.** Applying
`max(1 tick, 0.05*ATR)` to `ma.position` moved it 85,153 -> 85,834 — *up*,
because widening the INSIDE band splits some ABOVE->BELOW flips into two.
Raising it 20x to a full ATR buys 19%. Price genuinely crosses this ribbon every
~7 bars; that is a property of the market, not of the threshold. Kept anyway,
because on a sub-dollar symbol a bare comparison flips on a quote tick — the
S40 failure one layer up.

**ATR percentile ties take the MIDRANK.** The obvious "count everything at or
below" rule labels a dead-flat market as the *100th* percentile, and the regime
machine would then have classified silence as HIGH volatility.

**SMA200 silences 1W on 40 of 59 symbols** (19 have 200 weekly bars; median
188). Correct, not a gap: 200 weeks is 3.8 years and most of these instruments
are younger than their own slow average. Emitting a partial average that looks
like a real one is how a backtest lies.

Also fixed mid-build: zero-volume daily bars crashed the rolling volume profile
(a bin evicted the moment its volume hit zero left nothing to subtract when the
bar left the window). Regression test added.

### The wiring, which is where the last two engines died

Both `ranges.py` and all four of these were built, tested — and **not in
`live.ENGINES`**. An engine that never runs emits nothing to grade, so it cannot
earn the promotion the whole discipline is built around. All five are wired now.
Cost measured on the ADMITTED set rather than the backfill, since that is what a
live cycle actually pays: **25s**, idempotent across two consecutive passes.

### One coupling the version lockfile could not see

`momentum`, `volatility` and `volume` all `from .ma import ema, plain, sig`.
That is a CODE-level dependency with no `*_VERSION` constant to grep for, so the
lockfile's generic import check passed it vacuously — a change to the EMA
formula would silently change three other engines' facts. Now declared in
`CONSUMERS["ma"]` with its own assertion.

**489 python + 50 js tests green.**

---

## S43 — Armed order completed (plan Phases E–K), and the backlog reconciled

Circled back through every open item from earlier sessions. Most of the spec
track turned out to be answerable from the build rather than from a working
session, and the one genuinely actionable plan — `forming-armed-order-plan.md`,
approved 2026-07-24 with both user rulings already in — had never been executed
past its scaffolding.

### What the reconciliation found

Three of the six §30 methodology questions have been **answered by measurement**
since they were queued:

  · **swing confirmation** — `swing-v0.8` composite Major Score, calibrated
    against the user's golden data (S3–S5).
  · **BOS/CHoCH tier** — settled twice by A/B. 1D=MAJOR won against
    INTERMEDIATE (S3); 1W=INTERMEDIATE adopted in S41 because 194 weekly bars
    yield 14 MAJOR pivots across 11 symbols, which cannot form a sequence.
  · **HTF influence** — measured S41: TRENDING +0.258 R / FLAT -0.108 R /
    UNKNOWN -0.244 R across n=198/380/45.

Item I-6 (design annex, tokens, replay screen) is superseded by the shipped
five-surface shell and Learn surface. Still genuinely open and recorded as
documentation debt: §30 protected-high/low, zone flip, structural displacement;
Item D persistence spec; Items G/H; and the two user rulings under Item I.

### The armed order — "no runtime decision at execution"

Before: FORMING announced a zone approach with every armed field `None`, and
VALIDATED **recomputed** entry/SL/TP at touch. The bracket that executed was
therefore not provably the bracket that was decided — ATR, structure and equity
all move in between, so "computed the same way" is a weaker claim than
"inherited".

**Phase E** — `risk.size_order(...)` extracted as a PURE function (plan Phase C
ruling, option A). §9 is preserved: `risk.py` still owns the code; `setups.py`
now calls it at arming time. The split is deliberate — order-level constraints
(exposure, leverage, liquidation, min-notional, participation) go in the helper;
account-level ones (kill switch, concurrency, cooldowns, point-in-time
eligibility) stay in `risk.run`, because a FORMING fact must never claim an
approval the portfolio never granted.

**Phase F** — VALIDATED inherits the armed bracket verbatim by `setup_id`.
15m/1H have no FORMING pass by design and still compute.

**Phases G/H** — `forming_id`, `armed_at`, `armed_size_units`,
`armed_risk_decision` and `expires_at_ts` ride on every order and exec fact,
including MISSED. MISSED additionally records `bars_armed_exceeded` and
`armed_lead_bars`, so `MAX_ENTRY_BARS` can finally be judged against real arming
lead times instead of assumed correct.

### Phase J — the replay diff, and the two defects it caught

This is what the phase exists for, and it earned it twice.

**1. The version collision, a third time.** Wiring Phase E changed what
`setup-v0.9` produces without bumping it. The replay showed **107 armed and 107
unarmed FORMING rows describing the same 1D zones** — two payload generations
under one tag. Bumped to `setup-v0.10`, cascading `exec-v0.11`, `risk-v0.10`,
`scale-v0.5`. The version lockfile flagged the cascade immediately.

**2. Inheritance was 0% on every timeframe, including the three that arm.**
`armed_by_id` was read from the store BEFORE the FORMING pass ran, so on a fresh
store nothing could ever inherit — a zone arms and validates inside one
invocation. Now populated by the FORMING pass itself and seeded from prior runs.

**After the fix:**

```
FORMING armed at approach     1D 107 · 4H 47 · 1W 17   (all APPROVED)
VALIDATED inherited           1D  20 · 4H  5 · 1W  4
Phase F acceptance            29 inherited setups, 0 bracket mismatches
```

Byte-identical to the armed order in every inherited case.

**The honest number: 29 of 171 armed orders produced an inherited VALIDATED**,
and on 1D only 20 of 46 validated setups inherited. That is expected rather than
broken — a zone only arms if price came within 1 ATR *and* the regime aligned at
approach, and the regime can differ by the time it is touched, which produces a
different strategy and therefore a different `setup_id`. But it means the armed
path currently covers under half the 1D book, and that ratio is now measurable
for the first time.

### Phase K

Substantive review against the plan's own criteria: the VALIDATED order IS
provably inherited (asserted, 0 mismatches); `forming_id` is present on order
and exec facts including MISSED; the replay diff is explained above. Formal
Auditor-persona sign-off is a separate seat and remains outstanding.

**500 python + 50 js tests green.**

---

## S44 — Item D specced, breakout-retest MEASURED AND REFUSED, and a flaw in my own method

### Item D — Persistence & Retention (`docs/SPEC-persistence-retention.md`)

Measured first: **1.4 GB, 1,432,051 facts, and 38.1% of them belong to engine
versions nothing reads.** `swing` and `zone` alone are 63.5% of the store; the
facts that constitute the actual track record — setup, exec, order, risk — are
under 2%.

The policy resolves append-only against retention by scoping the promise:
append-only governs how the system WRITES; what must stay reconstructable is a
DECISION, not every intermediate fact a superseded engine generation produced.
Four classes, and **retention is measured in VERSIONS, not days** — a time-based
rule would delete the four years of perp history that make a backtest meaningful
while leaving last week's dead generation untouched.

**Nothing is implemented, deliberately.** 1.4 GB is not a problem; every
deletion mechanism is a chance to delete the wrong thing. The cheap wins the
spec named were done instead and **found nothing**: `ANALYZE` had never been run
(now has), two composite indexes already cover the hot query shapes, and the hot
query measures sub-millisecond before and after. Triggers for revisiting are
written down.

### Breakout-retest — built, graded, and NOT enabled

`breakout.py` (v0.1) is the first strategy whose TRIGGER is structural rather
than zonal: it fires when price returns to a level that was just broken and the
level holds from the other side. It lives in its own module for a concrete
reason — `setups.py`'s loop is `for zone_id, z in zones.items()` and a
structural trigger has no zone to iterate; `scalein.py` set that precedent.

Deliberately SHARED by import, not reimplemented: `setups.confirms`,
`setups.vetoes`, the bracket shape, the entry model. So this changes WHERE a
trade comes from and nothing about how it is executed or sized — which means any
difference in results is attributable to the trigger rather than to a hundred
small divergences in the machinery around it.

**Then it was graded on the same harness REVERSAL had to clear:**

```
n=55   win 27.3%   sumR -4.2   expectancy -0.076 R
CI95 [-0.545, +0.426]   P(>0) 37.4%   same-bar stop-outs 27.5%
symbols positive 6/18
```

Indistinguishable from zero. **It does not ship.** REVERSAL cleared this bar
with a CI above zero; this did not, so it is wired to KEEP EMITTING FACTS —
neither `execsim` nor `risk` reads `BREAKOUT_VERSION`, so it trades nothing —
and its sample keeps growing for a later re-grade.

That required a third registry status. `measured` is not `planned`: the engine
EXISTS and runs. Collapsing the two would hide a strategy already producing
gradeable evidence behind a label that says it does not exist yet.

Its same-bar stop-out rate (27.5%) is also notably worse than the confirmed
zone strategies (13.9%), which suggests a retest of a LINE is weaker evidence
than a rejection from a BAND. That is a hypothesis, recorded, not acted on.

### A flaw in my own measurement method

Every measurement this project takes runs against a copy of the store. Those
copies were being made with `shutil.copy` after `PRAGMA wal_checkpoint(FULL)` —
and that is wrong on a 1.4 GB WAL-mode database with a live scanner writing to
it. The checkpoint is an instant; the copy takes seconds; the writer does not
stop.

Caught when a copy failed `quick_check` with hundreds of **"Rowid out of order"**
errors on the facts B-tree and every engine run against it raised `database disk
image is malformed`. **The live store passed a full `integrity_check` — the
corruption existed only in the copy**, which is precisely the dangerous version:
a measurement can be taken from a broken snapshot and look like a result.

`engine/snapshot.py` uses `sqlite3.Connection.backup()`, which holds a read
transaction and restarts if a writer intervenes, then **verifies the result with
`quick_check` and raises** rather than returning a corrupt file. Silently
handing back a bad snapshot would be strictly worse than the `shutil.copy` it
replaces, which at least failed loudly on first use. Cost: 7s instead of ~3s.

Mitigating note, stated because it matters for everything reported earlier: the
`abtest` calibration step reproduced the recorded book exactly (drift 0.0) on
those copies, which is strong evidence they were consistent. "Strong evidence"
is not "guaranteed", and it is now guaranteed.

**500 python + 50 js tests green.**

---

## S45 — Phase 4 (Perps) closed out: funding was defined and never charged

The operator asked whether there was still a Phase 4. There was, and it was not
finished. `REDESIGN-PLAN.md` §6 lists Phase 4 as *Perps: Phemex adapter, shorts,
leverage, liquidation model + safety gate, funding costs*. Four of those five
shipped in S32–S34. The fifth did not.

### `venues.funding_cost_rate` had ZERO callers

It was written in S32 with the reasoning spelled out — *"funding is charged
repeatedly, not once. A perp held over a weekend pays every settlement, and on a
tight target that can exceed the edge"* — and then nothing ever called it. Eight
sessions of perp simulation charged **no funding at all**.

Measured before fixing, at a 0.01%/settlement model against the recorded book:

```
15m ~0.00 R   1H ~0.01 R   4H ~0.01 R   1D ~0.03 R   1W ~0.12 R
```

Small beside the 14x cost-profile error of S37, but 0.03 R is roughly 17% of the
1D book's expectancy — and an unmodelled cost that only ever flatters is exactly
the kind that survives review.

**Charged in `exec-v0.13`.** Effect on the perp book:

| | n | win | sum R | expectancy | CI95 | P(>0) |
|---|---|---|---|---|---|---|
| before | 342 | 30.4% | +48.0 | +0.1405 | [-0.066, +0.355] | 90.8% |
| after | 340 | 30.3% | +42.5 | **+0.1251** | [-0.081, +0.338] | 88.3% |

Two limitations stated rather than buried. The rate is a **modelled constant**:
real funding varies per settlement, Phemex publishes it, and this store holds no
historical series — `phemex.funding_rate()` fetches only the CURRENT rate, which
cannot price a trade from 2024. And it is charged to **both directions**, though
in reality the paying side flips with the sign of the rate; a short receives
funding when longs are paying. Charging both is the pessimistic reading, which
is this engine's standing rule for costs.

### And it was missing from the pre-trade gate too

The plan is explicit — *"funding cost enters the fee-aware gate — a multi-day
swing long pays funding repeatedly, which changes whether a setup is economic"*
— and `costs.estimated_round_trip_cost` priced only fees and slippage. On a
perp the gate cost rises steeply with the timeframe once funding is in it:

```
1H +7.6%   4H +30.5%   1D +183%   1W +1282%
```

Spot is unchanged, by venue declaration (0 settlements/day) rather than by a
branch.

**And it is non-binding at current geometry** — re-running every setup changed
exactly one 15m candidate and no 1D/4H/1W ones, because confirmed-entry stops
are already wide enough to clear the higher bar. Worth recording precisely
because it is the opposite of the S37 finding: there, a wrong cost model was
rejecting real setups; here, a corrected one rejects almost nothing. The fix was
for correctness, not because the gate was misbehaving.

### A version bump with byte-identical output

`setup-v0.11` produces the same facts as v0.10 on today's book. It is still
correct to bump: the RULES changed, a tighter-stopped setup would now be judged
differently, and a version tag identifies the rules that produced a fact rather
than the bytes that came out. Cascaded to exec-v0.13, risk-v0.12, scale-v0.7,
breakout-v0.2 — the lockfile forced all five.

### Phase 4 status

| element | |
|---|---|
| Phemex adapter | done S33 |
| shorts | done S32 |
| leverage + cap | done S32 |
| liquidation model + safety gate | done S32 |
| **funding costs** | **done here — S45** |

**Still open and NOT ours to close:** the plan's own question #1, *"Phemex may
restrict US users — operator's call"*, remains unanswered, and the entire traded
universe is Phemex. Question #2 (margin mode: isolated vs cross) is also still
open; the liquidation model assumes a 0.5% maintenance allowance without
declaring which mode it prices.

**509 python + 50 js tests green.**

---

## S46 — Kraken adopted, margin declared ISOLATED (operator rulings 2026-07-30)

Two rulings, both of which had been open questions in `REDESIGN-PLAN.md` since
2026-07-28 while the whole book depended on the answers.

### Ruling 1 — isolated margin, not cross

The operator's reasoning, verbatim: *"that could wipe your whole acct."* Correct,
and it is the reason this matters more than a config flag. Under CROSS margin
every position is backed by the entire account balance, so liquidation distance
depends on every other open position and one trade can take everything. Under
ISOLATED a position can only lose the margin posted to it.

`risk.py` sizes by "distance to stop" and caps total open risk at 4%. **Both of
those are advisory under cross margin**, because the exchange can close a
position at a loss far larger than the one that was risked. Isolated is the only
mode under which "2% per trade" means what it says.

The model was ALREADY isolated — `(1/leverage) - maintenance` prices the move
that exhausts this position's own margin — it simply never declared which mode
it was pricing. Now `Venue.margin_mode` states it, and `liquidation_price`
**raises on CROSS rather than returning the isolated number under a cross
label**. A liquidation estimate wrong in the optimistic direction is worse than
none, because the stop-safety gate is built on top of it.

### Ruling 2 — use Kraken

`engine/kraken.py`, contract VERIFIED against the live API rather than assumed:

```
/derivatives/api/v3/instruments   281 tradeable perps, PF_XBTUSD style
/derivatives/api/v3/tickers       volumeQuote = 24h USD notional
/api/charts/v1/trade/{sym}/{res}  all five resolutions native
```

Three things the live check settled:

  · **`countriesBanned` is empty** on PF_XBTUSD and no perp on the venue flags
    US. Recorded as a data point, not interpreted as legal advice — but it is
    the first evidence either way on a question that has been open for two days.
  · **The venue publishes `maintenanceMargin: 0.005`** at tier one — the exact
    figure `venues.liquidation_price` has assumed as a conservative default
    since S32. The model was right, and is now corroborated by the venue rather
    than trusted.
  · Kraken serves all five timeframes natively, and we still import only three
    and let the aggregator build 4H/1W — same reasoning as Phemex. Two writers
    for one `(symbol, tf, open_ts)` bucket is how they disagree at a gap.

**Kraken WINS overlaps, and that deliberately overrides volume.** Everywhere
else in `universe.py` the deeper book wins, because thin books do not fill
structural stops. Here regulatory access outranks depth: an unfillable order is
a bad trade, but an inaccessible venue is not a trade at all.

**The XBT trap, caught before it bit.** Kraken writes Bitcoin as XBT, so
`PF_XBTUSD` and `BTCUSDT` are one coin under two spellings. Without an alias the
dedupe sees two candidates, admits both, and the account holds the same exposure
twice while `MAX_CONCURRENT` counts it once — precisely the S33 double-exposure
bug returning through a different spelling. `_BASE_ALIASES` maps XBT->BTC and
XDG->DOGE; verified 0 duplicate underlyings across 665 merged candidates.

**Measured effect on the universe:**

```
Kraken USD perps ranked            271 (health 271/271, one request)
clearing the $3M liquidity floor    16
merged top 25                       17 kraken · 5 phemex · 3 coinbase
would be admitted (top 20)          18 -> 16 kraken, 2 phemex
```

### The cost of the ruling, stated plainly

The tradeable universe **shrinks**. Only 16 Kraken perps clear the $3M floor
against 21 on Phemex, so the admitted set becomes smaller and more concentrated
in majors. That is the price of trading somewhere the operator can actually
trade, and it is the right trade — but it is a real narrowing and should not be
discovered later as a surprise.

Also note a genuine difference in cost structure: **Kraken funds hourly (24
settlements/day) against Phemex's 8-hourly (3)**. Same nominal rate, eight times
the accrual. Funding now being charged (S45) is what makes that visible instead
of invisible.

**512 python + 50 js tests green.** Nothing has been re-onboarded yet — the
store holds no Kraken candles, so the next universe refresh will place every
admitted Kraken symbol into WARMING and backfill it. That is a real change of
what the forward record measures and should not start silently.

---

## S47 — Kraken carried as a SHADOW venue: warmed, measured, never traded

Operator: *"phemex works for me fyi. for how long I don't know so you say the
word. good data is what I want."*

The call, and the reasoning matters more than the answer.

**Trade Phemex.** It works today, 21 symbols clear the liquidity floor against
Kraken's 16, the books are deeper, and it funds 3x/day against Kraken's 24. On
pure data quality today it is the better venue.

**But the thing that would actually cost is a broken record, not a worse venue.**
Everything measured so far is replayed history; the forward baseline is hours old
with zero closed trades. If Phemex access disappears mid-record we do not lose a
venue, we lose CONTINUITY — and the expensive part of a switch is not the code,
it is that a new symbol enters WARMING needing 200 daily candles. A switch under
pressure costs weeks of dead forward record.

So: **SHADOW venue.** Kraken symbols are imported, aggregated and run through
every descriptive engine, and are never admitted. `admitted_at` gates every
sizing decision on ADMITTED membership, so a shadow symbol can accumulate
candles, facts and even setups without one dollar of paper risk reaching it.
`KRAKEN_SHADOW_ONLY = False` is the whole switch, and by then the history is
already warm.

`live.cycle` now scans `universe.scan_symbols` (traded ∪ shadow) rather than
`current_symbols` (traded). Keeping those two as separate functions is the
safety property — collapsing them is exactly how a shadow venue quietly becomes
a traded one, and a test asserts they are not the same object.

### The interaction that nearly went out

First implementation merged Kraken into the ranking (winning overlaps, per the
S46 precedence) and THEN classified the winners as SHADOW. Preview:

```
SHADOW 16 · ADMITTED/WARMING 3 · REJECTED 1
traded: ['u1000SHIBUSDT', 'CAP-USD', 'u1000PEPEUSDT', 'ZAMAUSDT']
```

**Every overlapping coin was won by Kraken and immediately made untradeable.**
BTC, ETH, SOL and the rest went dark; the tradeable set collapsed to the three
junk symbols Kraken does not list. That is the whole book, silently, with no
error anywhere.

Cause: warming and trading were being answered by one mechanism. They are two
questions. `shadow_candidates()` is now separate from `rank_all_venues()` —
shadow symbols ride alongside and never compete for a TOP_N slot, and the
underlying they duplicate keeps trading wherever it already traded. Safe
precisely because SHADOW cannot hold a position: the double-exposure rule the
dedupe enforces is about POSITIONS, and the S46 dedupe still applies in full to
the traded set.

After the fix:

```
TRADED  20 symbols, unchanged  (BTCUSDT, ETHUSDT, SOLUSDT, ...)
SHADOW  16 Kraken perps warming (PF_XBTUSD, PF_ETHUSD, PF_SOLUSD, ...)
```

The post-switch tests from S46 still assert Kraken-wins behaviour, now correctly
scoped to `KRAKEN_SHADOW_ONLY = False`, and a regression test pins the collapse
so it cannot come back.

### What this buys

  · the better venue is traded today
  · the fallback is warm the day it is needed, not 200 days later
  · a free venue A/B: the same strategies run on both books under
    venue-derived costs, so "is Kraken's 24x funding accrual actually worse in
    R" becomes a measurement rather than an argument

**523 python + 50 js tests green.**

---

## S48 — Kraken warmed, and a cold-start bug that had been poisoning data health

### The backfill

16 Kraken perps imported into the live store, all clearing the 200-day gate —
most with four years of history (PF_XBTUSD/ETH/SOL/XRP/ADA/UNI back to
2022-03-23, the venue's own earliest). Native timeframes only; 4H and 1W built
by the aggregator, so `source` reads `kraken-perp` on all 135,889 native rows
and `agg:*` on the rest — zero rows written by two writers.

`PRAGMA quick_check` ok before, after, and on re-check. **Zero malformed candles.
Zero in-life gaps** — verified by walking each daily series from its own first
candle rather than from the requested start. 79 seconds total.

The universe now classifies exactly as intended: **19 ADMITTED (all Phemex/spot),
16 SHADOW (all Kraken), zero Kraken admitted.**

### The cold-start bug — found by the backfill, not by the tests

`live.cycle` computed its incremental start as `MAX(open_ts) + granularity`, and
`MAX` is NULL for a symbol with no candles. The fallback was `or 0`, so a cold
symbol asked the venue for history **from 1970-01-01**. The adapter's
no-forward-progress guard then aborted the walk in the 1990s, before reaching
real data, and nothing imported — forever, every cycle.

`PF_XLMUSD` had been failing this way on **24 consecutive cycles**.

The wasted requests were the small part. The real damage:

```
/api/health gaps_logged      6,188,547,178
of which fabricated          6,187,847,452   (99.99%)
actually real                      699,726
affected import_log rows             7,401
```

`risk.py` halts on a BLOCKED data-health verdict, and that verdict is fed by
this column. **A single cold symbol could poison the signal the risk authority
trusts.** It went unnoticed because a bigger number in a gap counter reads as
diligence.

Three fixes, at three different depths:

**1. The floor.** `ingest.history_floor(tf, now)` — one definition, used by both
onboarding and the live loop, so they cannot disagree about how much history a
cold symbol gets. 1D from 2022-01-01, 1H 180 days, 15m 30 days.

**2. The accounting, which was the actual defect.** `importer.backfill` counted
every bucket in the RANGE IT ASKED FOR as a gap. A gap is a missing bucket
inside the span the venue actually SERVED; buckets before the venue's first bar
are pre-listing, and recording them as gaps claims the venue lost data it never
had — the mirror image of fabricating a candle, and just as dishonest.

A test caught a real error in the first version of this fix: a bar the venue
**served and we rejected as malformed** IS a gap, and my first cut silently
reclassified it as pre-listing. The span is now defined by what was SERVED, not
by what was KEPT. That distinction is the gap-honesty rule, and the suite
defended it.

**3. The historical poison.** Quarantined at the read site rather than deleted —
the log is evidence of what happened, including of the bug. `/api/health` now
reports `gaps_logged: 699,726` with `quarantined_gap_rows: 7,401` and a stated
reason beside it, so nothing is hidden and nothing is fabricated.

**529 python + 50 js tests green.**

## S49 — two audits: the operator-facing lies, and the guardrails never wired

Two adversarial passes ran against a verified snapshot: a full-stack correctness
audit and a second-pass salvage sweep of the retired project. The engine layer
held — no lookahead, no fabricated candle, no version tag covering two
generations. **Every confirmed defect was at a boundary**: numbers that left the
engine correct and were degraded on the way to the operator, and guardrails that
were built, tested, documented and never scheduled.

### The Results page reported a losing book as break-even, in green

`shell.js perfRows` read `r.net_r ?? r.total_r ?? 0` and `r[key]` where key was
`symbol`/`strategy`. `/api/performance` has never emitted any of those four
names — rows are keyed `key` and report R as `sum_r`. Both reads fell through,
so a **−3.91 R** forward book rendered `+0.00R` on every row, in green, with an
em-dash for the symbol. `n` was correct, which made the row look alive rather
than broken.

A missing number defaulted to zero, and zero read as flat rather than as absent.
Neither type-checking nor coverage would have caught it: the code ran every time
and produced a confident wrong answer.

Fixed at the read, and locked with `tests/test_ui_field_contract.py` — it parses
the field names the JS reads off each row, calls the endpoint, and requires
every one to exist. Verified against the old source: it fails on
`net_r, total_r, trades`. Deliberately a python test rather than a JS one;
`test_ticket_math.js` asserts the ticket's fee maths against a constant copied
into the test file, which cannot fail when the engine moves.

### The track record counted a venue that can never be traded

`_baseline_setup_ids` filtered on baseline + VALIDATED and never consulted
admission. Measured: **5 of the 6 baseline trades (83%)** were Kraken `PF_*`
SHADOW symbols. `risk.py` rejected every one with
`NOT_IN_POINT_IN_TIME_UNIVERSE` — and their R was counted into `n`, `win_pct`
and `sum_r` anyway. Only the dollar column excluded them, because `sized` reads
the risk decision and the R columns did not. `/api/edge-stats` applied no filter
at all: **276 of 639 trades, 43.2%**, sitting beside the equity curve implying it
described the same book.

S47's safety property — "`admitted_at` gates every sizing decision" — held in
`risk.py` and was absent from every read surface.

Shadow is now SEPARATED rather than dropped. A warmed venue's simulated record
is the evidence for admitting it, so it stays visible; it just cannot be added
to the traded book. `/api/edge-stats` defaults to `venue_state="TRADED"` and
always reports both halves, so a filtered report still says what it left out.

**This changed a headline.** Split by tradability:

| | n | mean | CI95 | P(>0) |
|---|---|---|---|---|
| TRADED | 363 | +0.1455 R | [−0.049, +0.356] | 92.9% |
| SHADOW | 276 | +0.1664 R | [−0.056, +0.383] | 92.7% |
| combined | 639 | +0.1545 R | [+0.002, +0.308] | 97.6% |

**Neither half clears zero on its own.** The combined CI cleared only because
pooling two venues doubled the sample. Per strategy, tradeable symbols only:

| | n | mean | CI95 | P(>0) |
|---|---|---|---|---|
| REVERSAL traded | 259 | **+0.2544 R** | **[+0.013, +0.500]** | 98.1% |
| REVERSAL shadow | 215 | +0.1412 R | [−0.106, +0.392] | 86.7% |
| PULLBACK traded | 102 | **−0.1080 R** | [−0.477, +0.303] | 28.5% |
| PULLBACK shadow | 58 | +0.3062 R | [−0.185, +0.814] | 88.0% |

REVERSAL **survives the strictest cut available** — it clears zero on symbols
the risk authority will actually size, a harder test than the one it had passed.
PULLBACK's mildly-positive combined figure was entirely shadow flattery; on the
traded book it is negative.

### edgestats stripped funding out of the scenario its verdict reads

`execsim` folds funding into `fees_price_units`. edgestats built
`r_ex_fee = r_net + fees_r`, adding funding back, then re-charged **fees only**
in the venue-real scenario — the one `_verdict` reads. Measured across all 639
trades: **+0.2262 R shipped against +0.1545 R restored, a +0.0717 R/trade
overstatement (46%)**, with 84% of it on the Kraken half whose 24×/day
settlement makes funding the dominant term.

S45's defect one layer up: a cost charged in the simulator and subtracted back
out in the engine that grades it. `funding_price_units` was already recorded per
fact, so the fix carries it as `funding_r` and re-charges it.
`edgestats-v0.1 → v0.2`; a reported number moved, so the tag moved with it.

Two stale claims removed with it: the docstring asserting funding "is not
modelled ANYWHERE in this engine" (which had stopped being a limitation and
become a bug), and the one asserting the store's cost profile is Coinbase for
every symbol (fixed in S37). The venue-real scenario now reproduces the recorded
book exactly, which is itself the check that the two agree.

### Three engine rosters, and the guardrail in none of them

`live.ENGINES`, `ingest.PER_SYMBOL_ENGINES` and `backfill.ENGINES` were three
hand-maintained copies of one sequence. They had drifted, silently, because
nothing compared them:

* **`cooldowns` was in none of them.** Built in S41, tested, documented, and
  consumed by `risk.py` — which read an empty list on every pass. Measured:
  **0 cooldown facts** in the store, and `cooldowns` absent from `engine_runs`
  entirely while all sixteen other engines were present. The rejection branch
  was unreachable code wearing a guardrail's clothes. Counterfactual on the
  recorded book: **86 of 1,007 VALIDATED intents (8.5%) would have been
  blocked**, all by a prior stop-out on the same symbol+direction; the 53 that
  filled returned **−5.19 R**. Precisely the re-entry-after-stop-out pattern S41
  built it to stop.
* `ranges, ma, momentum, volatility, volume, breakout` were in `live` only, so a
  symbol onboarded today got full history for the older engines and forward-only
  facts for these six — two populations in one fact store, nothing marking which.

Now one authority: `engine/pipeline.py`, imported by all three runners. Order is
load-bearing and preserved (`execsim` twice, `cooldowns` last so scale-in exits
are visible to the lockout). `tests/test_pipeline_roster.py` locks it, including
a generalised check that walks `risk.py`'s imports by AST and asserts every
per-symbol engine it consumes is actually scheduled.

Third module to die this way — `ranges` sat dead for the same reason, and the
four indicator engines were one release from it.

### One BLOCKED symbol aborted the whole cycle, including the risk pass

The import loop guards each symbol with the comment *"one symbol's transient
venue error must not abort the scan."* The engine loop immediately below it did
not, and `quality.assert_market_ready` **raises**. Measured in `data/engine.log`:
**364 aborted cycles against 584 completed (38%)**, 454 `blocked by market-data
quality` events, every one `EUL-USD: SEQUENCE_GAPS`. Each abort skipped the
remaining symbols' engines, `risk.run(con)` **and** `quality.audit(...)`.

A blocked symbol is still skipped — that is the gate working, and it stays loud
— but it can no longer take the other 74 symbols and the risk authority with it.

### Carried forward: measured, not yet fixed

* **Funding is per-*settlement* against venues whose schedules differ 8×.**
  `FUNDING_RATE_PER_SETTLEMENT = 0.0001` applied identically to Phemex (3/day)
  and Kraken (24/day). Measured: Kraken 0.0100%/h against Phemex 0.00125%/h —
  exactly 8×, entirely an artifact of the constant. S47's rationale ("is
  Kraken's 24× accrual actually worse in R becomes a measurement rather than an
  argument") is defeated at the constant. Two constants for one quantity
  (`execsim.FUNDING_RATE_PER_SETTLEMENT`, `costs.DEFAULT_FUNDING_RATE`), neither
  reading the other.
* **`scalein.py` missed the venue-cost migration** — still on `COST_PROFILE`
  (Coinbase spot, 1.00% round trip) on a 100%-perp universe, and passes neither
  `symbol` nor `tf_seconds`, so the one strategy that adds to an open position
  prices no funding at all. 5 adds at `scale-v0.7` across the whole store; the
  ~14× inflated gate is a plausible cause.
* **`ticket-math.js` is a second authority for position size** and diverges from
  `risk.size_order` in the permissive direction every time: renders un-reduced
  size where the engine reduces for leverage, has no `open_risk` parameter at
  all, and omits the liquidation gate, min-notional and participation cap
  (`/api/trade-config` does not even expose `MAX_PARTICIPATION`). Its fee figure
  also omits slippage and funding — funding alone is **49.1% of modelled cost
  per trade** across the exec book.
* **`risk.run()` does not call `size_order()`.** The armed order is sized by a
  separate inline reimplementation using `START_EQUITY` (10,000 against a live
  9,772) with no `open_risk`. All **220** armed orders report `APPROVED /
  WITHIN_LIMITS` while the risk authority's real decisions include participation
  reductions and universe rejections. Weakens the S43 claim that "the thing that
  gets executed is the thing that was decided" — the bracket is inherited, the
  *size* is two independent computations.
* **`chart.js`** renders a stale chart and a full order ticket after a failed
  load (the error text is written into an element only ever unhidden on the
  success path), and freezes equity for the page's lifetime (the guard is on
  `cfg`, the fetch is for `equity`) while `shell.js` refreshes it every 30s.
* **`/api/overview` takes 34.5s over HTTP** against 0.65s in-process. De-N+1'd
  (1,520 queries → 3) with no effect. Suspect remains the background audit
  thread holding the GIL. Unconfirmed.

### From the salvage sweep — two corrections to what was already taken

* **The participation cap was salvaged; its refutation was not.**
  `MAX_PARTICIPATION = 0.005` came from the old project's `participation_rate`
  — which that project then measured and discredited: 24h volume is not
  instantaneous book depth. Their witness: NEAR at $5M/24h with **~$2 at the
  touch**. They shipped a per-scan depth-at-touch gate instead. Keep the volume
  cap as a cheap pre-filter; it is necessary and not sufficient. Cost is real —
  no venue adapter here reads an order book at all.
* **Premium/discount was salvaged as "cheap, genuinely orthogonal"; it was
  measured, and its endorsement inverts in trends.** n=123: P/D favouring the
  direction returned **−4.42** avg; P/D opposing with an aligned BOS returned
  **+1.71**. Premium during an uptrend is just price advancing. If it goes in it
  must be conditioned on structure, or it will score highest on the losing
  cohort.

Worth taking, in order: **the validation-instrument gap** (a simulator blind to
thin books cannot validate thin-book safety — grounded here by one flat
`market_slippage_atr = 0.05` across all venues and symbols); **Phemex venue
facts** (measured minimum order **BTC ~$59.67** against this system's global
`MIN_NOTIONAL_USD = 1`, and lot-step flooring against a fixed 1e-8 quantize — we
currently size positions the venue would reject); **the reachability probe**
(feed a gate the input that must trip it, assert it did something — the old
project hit dead-safety-feature four independent times); and the **stuck-value
cardinality audit** (a recorded field with cardinality 1 across N facts is dead,
defaulted, or broken — one partitioning surfaced two independent bugs, and it is
a `GROUP BY` over an append-only store).

The most portable artifact in the retired project is not a file: it is
`decisions/`, 81 dated entries each carrying "why it matters next time",
including a permanent **REFUTED** section recording hypotheses that were
disproven. This BUILDLOG does much of that already; the refuted-hypothesis
register is the piece it does not have.

**538 python + 50 js tests green.**

## S50 — the simulator was inventing fills, and two thirds of the edge with them

A 13-agent audit of the three position-sizing authorities also swept for dead
gates and stuck fields. The sizing findings were the expected ones. The finding
that mattered was somewhere else entirely, and it invalidates every expectancy
number this project has reported.

### The crossing leg booked market fills at prices the bar never traded

`execsim` line 193: when the passive limit did not fill, the cross set
`fill_i = wait_end` and `entry_role = "TAKER"` — and **never touched `entry`**.
So the market order was priced at the PLAN's entry, `candles[ci+1]["open"]`,
while `order_i = ci+1` and `MAKER_WAIT_BARS = 2` put the cross on bar `ci+3`.
A market fill, booked at a print from two bars earlier, with no range check
against the bar it was filling on.

Measured on exec-v0.13, verified independently three times (two agents plus my
own queries):

* **95 crossed orders; 78 of them (82.1%) booked outside their own fill bar's
  `[low, high]`.**
* The direction was **never adverse** — 94 of 95 filled better than the
  crossing bar's open.
* One ETHUSDT long booked at **2075.49 on a bar whose LOW was 2094.69**. It
  bought below the bar.

The tell had been sitting in the store for eight sessions: **`MISSED` has not
occurred once since exec-v0.8** — 90 in v0.7, zero across 2,569 facts after. A
cross that always fills, at a favourable stale price, can never miss. Line 219
proves it structurally: it references `entry_end`, bound only in the `else`
branch, so reaching it from the passive path would `NameError`.

Restated, re-simulating the cross at the crossing bar's open with identical
SL/TP/costs:

| | as shipped | honest fills |
|---|---|---|
| whole book | +95.85 R / 642 | **+31.95 R** |
| per trade | +0.1493 R | **+0.0498 R** |
| **REVERSAL (traded)** | +0.266 R, CI **[+0.038, +0.498]** | **+0.152 R, CI [-0.070, +0.372]** |
| PULLBACK (traded) | -0.139 R | -0.228 R |

**Two thirds of the book's apparent edge was the simulator handing trades free
entries, and REVERSAL — the one result this project has been reporting as real
— stops clearing zero.** It remains the best thing here at P(>0) 91.1%, but it
does not clear the bar the project set for itself.

Fixed: the cross fills at the crossing bar's OPEN and pays market slippage, like
every other market order in the model. `MISSED` is alive again (2 recorded).
`tests/test_cross_fill_honesty.py` pins the general invariant — **no recorded
fill may be priced outside the bar it filled on**, slippage allowance included.
Nothing about that is specific to the crossing leg, which is why it would have
caught this the day it shipped.

### A real lookahead, in the engine that feeds the strategy layer

`zones.run` computed a zone's creation-time cluster over EVERY swing in the
series with no `confirmed_at` filter, then wrote the fact with
`confirmed_at = s["confirmed_at"]`. A zone created in 2023 could be rated on
swings from 2025.

Measured, 12 symbols x 4H/1D/1W, 2,006 zones: **159 (7.9%) counted future
swings**, and 96 of those got a different `formation_quality` — **inflated in
every single case, never deflated**. Worst: quality 90 from a cluster of 18, of
which zero were knowable at that zone's own creation.

The previous session's audit reported no lookahead anywhere. It was wrong.

Fixed and cascaded (`zone-v0.11 -> setup-v0.12`, which pulls exec/risk/scale),
pinned by `tests/test_zone_causality.py` at both the unit and the store level.

**And it changed the outcome numbers by exactly zero.** +0.1523 R before, and
+0.1523 R after. Which leads directly to:

### The STRENGTH evidence component can never be false

`formation_quality` feeds `strength`, and `strength` is one of the four
components `setups.reversal_evidence` counts against `REVERSAL_MIN_EVIDENCE = 2`.
So the lookahead fed a gate — and the gate cannot fail:

    strength   = (quality + freshness) // 2
    freshness  = 100 at creation, always, and the setup reads the CREATION value
    quality    >= 55 (the weakest zone the engine can build: cluster 0, 15m)
    => strength >= 77,  against REVERSAL_MIN_ZONE_STRENGTH = 60

Every timeframe, every cluster count, including zero. Which is why `STRENGTH`
appears in **985 of 985** VALIDATED REVERSAL setups — cardinality 1, precisely
the stuck-value signature the salvage sweep said to look for.

REVERSAL's "2-of-4 evidence" is therefore **1-of-3 plus a free point**, and
**81.3%** of its setups were admitted on a single real piece of evidence.

The obvious remedy is the wrong one. Splitting the traded book by REAL evidence,
excluding the always-true component:

| REVERSAL (traded) | n | mean | CI95 | P(>0) |
|---|---|---|---|---|
| 2+ real evidence | 63 | **+0.020 R** | [-0.388, +0.444] | 51.9% |
| 1 real evidence | 214 | **+0.191 R** | [-0.053, +0.451] | 93.4% |

**More confluence performed worse.** Demanding genuine 2-of-3 would cut the book
to 63 trades and roughly erase the edge. That is the confluence-stacking trap
this project was built to avoid, found in this project's own gate. The threshold
is left alone pending an operator ruling; tightening it looks actively wrong on
the evidence, and it is a strategy decision rather than a defect fix.

### And then I committed the S37 defect myself

Re-simulating under `exec-v0.14` happened BEFORE `SETUP_VERSION` moved to v0.12.
The zone fix then bumped setups, and the same exec tag simulated those plans
too — **637 facts from setup-v0.11 plans and 637 from setup-v0.12 plans under
one `algo_version`**, which double-counted every statistic read off it. The mean
was identical at exactly double the sample, which is what gave it away.

`exec-v0.15` exists so the corrected generation has a tag that means one thing.
`exec-v0.14` stays in the store as the record of what happened and no consumer
may join on it. The lesson is ordering: **bump every version in the cascade
BEFORE re-deriving, never between passes.**

The lockfile did its job three times this session — it is the reason each
cascade was deliberate rather than discovered later.

### Where the numbers stand

    zone-v0.11 | setup-v0.12 | exec-v0.15 | risk-v0.14 | scale-v0.9 | cooldown-v0.3

| traded book | n | mean | CI95 | P(>0) |
|---|---|---|---|---|
| all strategies | 411 | +0.0648 R | [-0.108, +0.247] | 76.8% |
| **REVERSAL** | 277 | **+0.1523 R** | [-0.070, +0.372] | 91.1% |
| PULLBACK | 109 | -0.1391 R | [-0.472, +0.226] | 21.4% |

**No strategy clears zero.** This session removed fictitious edge rather than
adding any, which is the correct outcome for an audit and the uncomfortable one
for the operator. The system now measures itself honestly, which it did not
before; the remaining +0.15 R on REVERSAL is something to test forward, not
something to trust.

**555 python + 50 js tests green.**

---

## S52 — Venue-blind costs fixed: the 15.7x fee over-charge

Closes the defect flagged when the `cool-golick-5c5baa` worktree was preserved.
Its `test_venue_costs.py` was the specification; this session made it pass.

**What was already right:** the parallel work had `costs.profile_for(symbol)`
and per-venue profiles, and `execsim`/`setups` already resolved per symbol.

**What was still wrong, and it was the load-bearing half:**
  · `costs.profile_for` FELL BACK to the Coinbase default on an unrecognised
    symbol. A silent default is how the whole class of bug happens; it now
    raises. Every symbol in the traded universe resolves, so a raise means a
    genuinely unknown instrument reached pricing.
  · `estimated_round_trip_cost` defaulted its profile argument, making "charge
    the wrong venue" the path of least resistance for a caller. Now required.
  · `setups.COST_PROFILE` — a module global every consumer inherited. Removed.
  · **`scalein` imported it**, so every scale-in add on a perp had to clear a
    gate built from ~14x the fees its venue charges.
  · **`entrystats`** used it for the taker-entry penalty — the statistic that
    decides whether limit or market entries are better. A venue-blind spread
    answers that question wrong (0.20% vs the perp's real 0.05%).
  · No `by_version()`, so a recorded fact's profile could not be resolved from
    its version without guessing.
  · No guard against `venues.py` and `costs.py` drifting apart. They duplicate
    three rates each by necessity — profiles are immutable because facts cite
    them, venues carry live capability. `_assert_venue_rates` now runs at
    IMPORT, so editing a rate without minting a new profile version fails at
    startup rather than quietly re-pricing history.

**Two labelling defects found while making the spec pass:**
  1. `fees_price_units` included funding, while `funding_price_units` reported
     the same funding beside it — any consumer summing them double-counted.
     Split. Net P&L and r_multiple are unchanged; both legs still deduct.
  2. The EXECUTION manifest embedded the cost profile, so a hash certifying the
     FILL MODEL varied by venue — a fee change was indistinguishable from an
     execution-model change, and two books running identical rules looked
     different. Costs are proven separately by `cost_manifest_hash`.

**A test asserted the wrong thing.** `test_funding` pinned
`fees = ... + funding_cost` by SOURCE REGEX, which forced the double-count. Its
docstring stated the real intent — "if it were recorded but not summed into the
cost of the trade... the R would still be wrong" — so it was rewritten to assert
the ARITHMETIC of a simulated trade: funding must reach `r_multiple`. Stronger
than the regex and no longer in conflict with correct labelling. (My first
version compared on the price scale where `r_multiple` is rounded on the R
scale, manufacturing a 5x-amplified mismatch. Fixed.)

**Version cascade, caught by the lockfile rather than by vigilance.**
`test_version_cascade` failed on the exec bump and named its consumers, exactly
as designed. exec-v0.16 -> v0.17, and with it risk -> v0.16, scale -> v0.11
(also changed on its own account), cooldown -> v0.5. setup did NOT move: it
already resolved per symbol, so its outputs are unchanged.

**Measured on the re-simulated book, 639 resolved trades:**
  · pricing now: **356 phemex · 276 kraken · 7 coinbase** — previously all 639
    were charged Coinbase spot rates
  · fees charged **1,582** price units against **24,764** at the old profile —
    a **15.7x over-charge**
  · the pre-trade gate: a perp setup needed a **2.00%** stop to count as
    economic, now **0.14%** — 14.3x easier to clear, which is a large share of
    the UNECONOMIC_AFTER_COSTS rejections
  · book total **+33.76 R**

573 python + 50 js green.

## S53 — 178,115 phantom facts: the promotion payload accrued per bar

Closes the S49-audit headline item ("`swings` re-emits every promoted pivot
every cycle"), diagnosed 2026-07-31 and deliberately left for a single owner.

**The defect.** The INTERMEDIATE/MAJOR promotion payload embedded
`evidence.held_candles`, which increments every candle a pivot holds — a
run-time-dependent value inside a content-hashed, append-only fact. Every scan
cycle the integer moved, the hash moved, and `insert_fact` appended the same
pivot again. Measured at fix time: **193,718 promotion rows for 15,603 pivots
(3,283 duplicated keys, 178,115 excess rows)**, one AAVEUSDT 4H pivot 11 times
differing only in held 987..997. Downstream, `zones` counted the copies as
cluster neighbours and `liquidity` as pool members, so `formation_quality` →
`strength` — **which gates REVERSAL** — inflated monotonically for as long as
the scanner stayed up. Also the true cause of the standing
`test_zone_causality` live-store failure: the phantom population grew between
a zone's write and the test's recount.

**The rule (swing-v0.9).** `held_candles` is censored at `HELD_FULL` (90 —
the cap the score card applied all along), and the promotion fact is emitted
only once that window has CLOSED: price traded beyond the extreme, or 90 bars
elapsed. `confirmed_at = max(geometric confirmation, window close)` — when the
evidence became knowable (§5). The payload is now a pure function of the
candles; re-runs are no-ops.

**The alternative was measured and rejected.** Freezing held at geometric
confirmation — the other option in the audit note — is v0.4's
held-as-confirmation-lag dud again: simulated over every latest recorded
pivot, **45% change tier** (4,313 of 15,546 INTERMEDIATEs drop out, 2,687 of
4,016 MAJORs demote, the golden BTC-1D set loses 2 of 20 majors). The chosen
rule is score-IDENTICAL for every settled pivot, because held points always
capped at 90. Replayed on real candles (AAVEUSDT 4H, BTC-USD 1D): re-run
inserts 0 facts; all 27 + 48 settled pivots match the latest v0.8 copies in
tier AND score; the only absences are frontier pivots whose window is open —
including the one golden major minted 2026-05-06, back ~2026-08-04. Honest
cost: a promotion is knowable a median ~65 bars later than v0.8 pretended
(v0.8's early copies carried lower drifting scores — it published the
trajectory as duplicates); 440 frontier pivots (2.8%) defer until settle.

**The cascade, and a hole in the map.** Widest bump the lockfile has recorded:
swing-v0.9 → structure-v0.11, zone-v0.12, liq-v0.10, ranges-v0.2,
momentum-v0.2, setup-v0.14, breakout-v0.3 → regime-v0.11 → exec-v0.18,
risk-v0.17, scale-v0.12, cooldown-v0.6. **`setup` and `breakout` read swing
facts directly but were missing from `CONSUMERS["swing"]`** (and from
`CONSUMERS["structure"]`) — the cascade plan drafted from that map missed them
both, which is precisely the failure the map exists to prevent. Fixed in the
same commit.

**Residual, named rather than hidden.** 63 of the 3,283 duplicate groups
varied in something other than held — a pivot near the sequence tail is
legitimately revised when a more extreme same-type swing replaces its right
neighbour. Bounded (one revision window per pivot), and the count-sensitive
consumers now collapse to one row per pivot, LATEST winning: `structure`
(sequence-sensitive label walk, collapsed across both tiers so a demoted
pivot's stale higher-tier row cannot survive), `zones` (cluster counts
anchors), `liquidity` (n_members counts pivots). `ranges`/`momentum` already
pass swing facts through `alternate()`, which tolerates repeats;
`setups`/`breakout` do price lookups, which duplicate rows cannot distort.

New regression suite `test_swing_promotion_stability.py` drives the real
recursion over a constructed zigzag: appending a bar re-emits nothing; an open
window emits nothing; a breach closes the window early and stamps
`confirmed_at` at the breach bar's close.

The old v0.8 facts remain in the store as the recorded dud, per house rule.
Forward baseline: every recorded number downstream changes generation; the
S50 "baseline reset" operator ruling now covers this cascade too (TODO.md).

658 python green.

### S53 addendum — the collapse itself shipped a bug, caught in its first cycle

The cascade merged, the services restarted through `/api/system/restart`, and
the first v0.9 cycle backfilled the new generation end to end (149k swing
facts, 142 symbol/tf pairs, the trading tail included). Verification of that
cycle found 5 promotion keys duplicated on (symbol, tf, market_time, tier) —
and zero on the key that includes TYPE. They were not duplicates. **One bar
can host both a promoted HIGH and a promoted LOW** — 2025-10-10 carries a
MAJOR pair on LTCUSDT, UNIUSDT and PF_UNIUSD — and the new consumer collapse
keyed on market_time alone, so the later row shadowed its twin. Measured in
the store the cycle had just written: all five bars created only their DEMAND
zone; **five supply zones did not exist**, and the structure walk lost the
same side.

Pivot identity is **(market_time, type)**. structure/zones/liquidity rules
changed again, so their tags and everything downstream moved again:
structure-v0.12, zone-v0.13, liq-v0.11 → regime-v0.12, setup-v0.15,
breakout-v0.4 → exec-v0.19, risk-v0.18, scale-v0.13, cooldown-v0.7. The
one-cycle v0.11/v0.12/v0.10 facts remain in the store as the recorded dud.
`test_zone_causality` passed against the shadowed store because it only
recounts zones that EXIST — a missing zone is invisible to it. The new
`test_zone_anchor_identity.py` writes a same-bar pair and requires both sides
to survive into zones and the structure walk.

**Verified live after the first v0.13-generation cycle** (17:02:33Z, 144.0s,
2 new setups): all five bars carry BOTH zones and BOTH structure labels —
LTCUSDT 1D got its SUPPLY back at [133.06 .. 135.86] beside the DEMAND at
[50.04 .. 52.84], the twins' identical scores (65.04/65.04) confirming one
recursion minted the pair; ETHUSDT's HIGH shows held=52 where its LOW shows
90, the censored window settling each side on its own evidence.
`test_zone_causality` re-run against the populated store: 3/3, no skips —
the recount that drifted weekly under v0.8 is now a fixed point.

660 python green.
