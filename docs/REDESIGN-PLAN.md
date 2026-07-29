# SniperSight — UI & Capability Redesign Plan

**Status:** proposed, not started. Written 2026-07-28 after an operator interview.
**Rule:** no code until this is approved.

---

## 1. Why the current UI fails

Measured on the live page, not asserted:

- **14 distinct font sizes** (8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 13.3, 14, 15, 17, 24px). That is not a
  type scale; nothing can be emphasised when everything differs.
- **31 interactive elements** and **15 tabs** on one screen.
- The footer is five unrelated facts glued with pipes: *"SCANNER — ⟳ RESTART | FACT STORE 701,329 ·
  append-only · swing-v0.8-draft | PAPER — no closed trades | — | view: 56 majors / 9 breaks / 8 zones."*
  That is **telemetry cosplaying as insight** — it answers a question nobody asked.
- Off-brand: cyan-on-black with glow, ALL-CAPS letterspaced mono everywhere, ◉ ◈ ⟳ 👁 symbols. The actual
  brand is a **gunmetal scope ring with a green reticle**.
- Operator verdict, verbatim: *"ok what do I do? Can't run the scanner manually, can't enter a trade, can't
  see what's active. There's lingo I have no idea what it means. There are features I don't know what they
  are. There's zero explanation."*

Root cause: the screen was built to display what the engine produces, instead of to answer what the operator
needs to decide.

---

## 2. Design system — adopt the brand that already exists

`snipersight-trading/DESIGN.md` already defines a real system. We adopt it rather than invent a third one.

- **Colour:** oklch olive-tinted darks (`bg 0.18 0.008 120` → `card-2 0.30`), foreground ramp `fg`…`fg-4`.
  Accents: **green `#00ffaa` (primary — matches the reticle)**, amber, red, cyan, blue. Cyan is demoted from
  "everything" to "one of five".
- **Type:** `Share Tech Mono` for display/titles, **`Inter` for body**, `JetBrains Mono` for numbers with
  tabular figures. Named roles only: display / page-title / section-title / metric-value / body / label /
  mono. **Six sizes, not fourteen.**
- **Spacing:** 4 / 8 / 14 / 18 / 24, shell padding 28. Radii 8–14, pill for chips.
- **Components:** panel, chip (+accent/red/cyan), btn (+cyan/red), metric-tile — already specified there.
- **Logo:** `snipersight-trading/src/assets/images/1000016768.png` (scope + wordmark). Copy into
  `app/static/assets/`.
- **Glow:** reserved for one thing — a live actionable signal. Never decoration.

**Lingo rule (operator's own constraint):** keep the tactical SniperSight voice, but *every* domain term is
explained. One glossary file drives a hover/click definition on every term (BOS, CHoCH, liquidity sweep,
translation, DCL/WCL, R-multiple, funding, liquidation). An **ADVANCED** switch hides deep internals for the
"everyday user later" path.

---

## 3. Information architecture — five surfaces, each with one job

Today: one screen doing everything badly. Proposed:

| Surface | The one question it answers |
|---|---|
| **COMMAND** (home) | *What should I do right now?* Scanner control, active setups, account strip. |
| **CHART** (setup detail) | *Is this trade good, and what are my levels?* |
| **SCANNER SETUP** | *What is the bot allowed to do?* Venue, keys, risk, leverage, strategies, AUTO. |
| **DIAGNOSTICS** | *Is the machine telling me the truth?* Telemetry + rejections + pipeline health, together. |
| **RESULTS** | *Is this working?* Equity, per-symbol, strategy vs operator scoreboards. |

### COMMAND
- **Scanner control:** venue selector (Coinbase / Phemex), **RUN SCAN** button (manual run — currently
  impossible), AUTO arm/disarm with state clearly visible, PAPER/LIVE mode indicator.
- **Setup deck:** one card per token, ranked. Card = symbol, direction, rank, R:R, entry/TP/SL, plain-English
  WHY, and dollar risk. Click → CHART.
- **Challenger cards** (operator's design): when a better setup appears for a token that already has a
  *pending* one, the new one shows as a CHALLENGER beside the incumbent with a **SWITCH** button. A token with
  a **filled** position is never auto-replaced — the challenger waits for a manual decision.
- **Empty state states the recorded reason** (already built): "190 candidates rejected — 172 no eligible
  playbook, 12 uneconomic, 6 R:R below minimum."
- **Account strip:** equity, open risk, day P&L vs limits. Small, quiet, always visible.

### CHART
- Chart owns the screen. Entry/TP/SL plotted and **draggable**; dragging re-computes R:R, position size and
  (on perps) liquidation distance live.
- **Order ticket:** size, leverage, trailing-stop toggle, TP/SL type. Submit = paper today, live when unlocked.
- **Overlay toggles, cleaned up and verified:** structure (swings/BOS/CHoCH), zones, liquidity, setups, and
  **cycle** (DCL/WCL markers, translation badges, 4-year low windows).
- Manual edits are recorded as **operator override** facts and excluded from strategy edge stats (see §5).

### SCANNER SETUP
- **Venue + credentials.** Operator enters their own API keys; keys go to OS credential storage, never the
  fact store, never logs, never git. Read-only keys recommended until live is unlocked.
- **Risk:** % per trade, total drawdown limit, max concurrent positions, leverage (per venue capability).
- **Strategies:** toggle PULLBACK / REVERSAL / SCALE-IN (+ CYCLE later, if it earns it).
- **AUTO mode:** arm/disarm plus guardrails (§4).

### DIAGNOSTICS
Everything debug in one place, per operator request: setup telemetry, rejection funnel, pipeline health,
engine versions, data quality. This is load-bearing right now — *"if code is wrong, the strategy may not prove
out properly and get false results."*

### RESULTS
Equity curve, per-symbol and per-strategy breakdown, and **two scoreboards: STRATEGY (untouched signals) vs
OPERATOR (your edits)** so hand-tuning never contaminates the edge measurement.

---

## 4. Capability plan

### Venue abstraction (new)
One `Venue` interface; two adapters.

| | Coinbase | Phemex |
|---|---|---|
| Instrument | spot | perpetual |
| Direction | long only | **long + short** |
| Leverage | 1× | operator dial, venue max |
| Extra costs | maker/taker | maker/taker **+ funding** |
| Liquidation | n/a | **modelled** |

The risk authority becomes venue-aware: it reads capability from the adapter instead of assuming Coinbase
spot. Every decision fact records which venue rules applied, so results stay comparable.

**US-residency caveat:** Phemex may restrict US users. Operator's call; noted so it is not a surprise later.

### Perps section (operator: *"maybe a whole perps section? IDK"* — yes)
Shorts and leverage are not a flag, they are a different risk model:
- **Liquidation price** computed from leverage + margin mode; drawn on the chart.
- **Liquidation-safety gate** — port `filter_by_liquidation_safety` from the old repo (proven scar tissue):
  refuse any setup whose viable stop cannot sit inside the liquidation price with a cushion. Thin books get a
  bigger cushion.
- **Funding cost** enters the fee-aware gate — a multi-day swing long pays funding repeatedly, which changes
  whether a setup is economic.
- Sizing: risk stays "distance to stop"; margin = notional ÷ leverage. Leverage never widens a stop (§9).

### AUTO mode guardrails
Operator selected **total drawdown limit**. Recommended additions (cheap, prevent the classic failures):
- **Data-health halt** — if the quality gate goes BLOCKED, stop placing orders. The system already refuses to
  trust its own numbers; it should refuse to trade on them too.
- **Arm-with-timer** — AUTO runs for a chosen session (8h / 24h / until disarmed) so a bot never runs for
  weeks because you forgot.
- Daily loss limit already exists in paper (6%).
- A large, always-visible **HALT ALL** control.

### Live execution — rails built, path locked
Everything is built and exercised by paper through *identical* code, with the live submit step gated. Unlock
requires: forward paper record with real sample size, quality gate green, and an explicit operator unlock.
Recommended first step after unlock: **shadow mode** — full live code path, order construction and all, but
submission suppressed and logged, to prove plumbing before risking money.

Honest note, stated once: the historical edge did **not** generalise (−68% across 19 symbols; ETH carried the
result), and the forward record currently has ~0 validated setups. Building the rails is right. Unlocking them
should follow evidence, not enthusiasm.

---

## 5. Measurement integrity

- **Operator overrides excluded from strategy stats.** A dragged level makes the trade an operator trade; it
  still shows in P&L, but strategy edge is measured only on untouched signals.
- **Cycle promotion is earned, not assumed.** Proposed experiment before any strategy change: retro-tag every
  historical setup with its cycle context (distance to DCL/WCL, cycle translation, position in the 4-year
  window) and compare outcome distributions. If the split is real, promote cycle to a scored input under a new
  strategy version. If not, it remains a chart overlay. Cost: one session. Risk of skipping: promoting an
  n≈2 belief into the thing that sizes real money.

---

## 6. Build sequence

| Phase | Contents | Why this order |
|---|---|---|
| **1. Foundation** | Design system (tokens, type, logo), app shell, 5-surface navigation, glossary + tooltips | Everything else renders inside it |
| **2. COMMAND + CHART** | Scanner run button, setup deck, challenger cards, chart with draggable levels, overlay cleanup | The daily-use core; answers "what do I do" |
| **3. Settings + venue seam** | Scanner setup page, credential storage, Coinbase adapter behind the new interface | Makes the bot configurable without code edits |
| **4. Perps** | Phemex adapter, shorts, leverage, liquidation model + safety gate, funding costs | Largest risk-model change; deserves its own phase |
| **5. AUTO + guardrails** | Arm/disarm, drawdown + data-health + timer halts, HALT ALL | Only after the manual path is trustworthy |
| **6. Diagnostics + Results** | Unified debug surface, dual scoreboards | Continuous; debug value is immediate |
| **Locked** | Live submission | Opens on evidence |

---

## 7. Open questions

1. Phemex US-residency restriction — does the operator have working access?
2. Margin mode on perps: isolated (recommended, bounded loss) or cross?
3. Should PAPER mode simulate the *chosen venue's* fees/funding, so paper and live are comparable? (Recommended: yes.)
4. Mobile/APK remains endgame — plan assumes desktop first.
