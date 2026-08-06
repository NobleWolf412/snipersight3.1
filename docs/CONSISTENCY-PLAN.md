# ONE ORDERED IMPLEMENTATION PLAN — SniperSight frontend

Verified against source. Every claim below carries `file:line`. Where the audits disagree I say so and rule.

---

# 1. THE ONE RANKING VOCABULARY

## The diagnosis, in one sentence

The operator is not confused by the words — he is confused because **one badge slot changes its question depending on which tab he is on**, and a letter grade beside it silently re-states both answers at once.

Proof: all four Overwatch tabs render the same `.mc` card with the same `.mc-stamp` span, filled from four different engine fields — `engine_reach` (shell.js:2093), `engine_reach` again but always `OUT_OF_RANGE` (shell.js:2028 → 2093), `weather.live` (shell.js:2153-2154), and `risk.decision` (shell.js:1685-1688). `#allMarkets` iterates the whole weather universe (`[...wx.values()]`, shell.js:2144) while `#near` iterates near-level rows, so the tabs are **not a partition** — `#allMarkets` is a superset. The same symbol therefore renders as `CONTACT` (green) on one tab and `NO PLAY` (grey) on the next, with the **same letter B** on both, because `gradeOf` is a pure function of exactly those two fields (shell.js:1964-1978).

## The scale

**Name: Reach & Play.** One badge, in one slot, on every setup card, on every surface. Two clauses, four colours.

The badge is `<REACH WORD>` plus, when the second fact is not favourable, ` · <PLAY CLAUSE>`.

**Clause 1 — reach.** 1:1 with `engine_reach`, the engine's own field (`app/engine/nearlevels.py:67-83`). Four values, four words, no fifth invented:

| `engine_reach` | Badge word | Plain meaning a newcomer can decode |
|---|---|---|
| `AT_ZONE` | **IN THE ZONE** | Price is inside the structure the engine watches. |
| `IN_RANGE` | **NEARBY** | Close enough that the engine is considering this zone. |
| `NO_FORMING_ON_TF` | **NOT PLANNED HERE** | The engine does not plan ahead on this timeframe; it acts only once price arrives. |
| `OUT_OF_RANGE` | **OUT OF REACH** | Further than the engine looks. Anything the chart draws here is the chart's, not the engine's. |

**Clause 2 — playbook coverage.** From `weather.live` (`app/server.py:1850`, per-timeframe at `:1724`). Three states, because an absent reading must never be drawn as a flat one (the argument already made at shell.js:2067-2071):

| `w.live` | Suffix |
|---|---|
| `true` | *(nothing — the good case is the quiet case)* |
| `false` | ` · NO PLAY` |
| symbol absent from `/api/weather` | ` · NO READ` |

**Colour = the rank.** Reuse the four existing stamp classes exactly as they are (`ss.css:1432-1435`), driven by the same lattice `gradeOf` computes today (shell.js:1965-1977) — the lattice survives, the letter does not:

| Colour | Class | Condition |
|---|---|---|
| **Green** | `st-t3` | IN THE ZONE, playbook live |
| **Amber** | `st-t2` | IN THE ZONE · NO PLAY, **or** NEARBY with a playbook |
| **Cyan** | `st-t1` | NEARBY · NO PLAY, **or** NOT PLANNED HERE |
| **Grey** | `st-t0` | OUT OF REACH |

**Sort order** = colour rank descending, then `distance_atr` ascending. Printed in the panel lede in words: *"Ranked by how close price is to a zone the engine watches, then by whether a playbook trades this market's condition."*

**Basis on screen.** The existing `gradeOf().why` sentences (shell.js:1966-1977) move verbatim from `.wl-grade-why` into the card body. They already name both fields in English — *"Price is in the zone and a playbook trades this condition."* That satisfies the no-uncalibrated-score constraint: the badge's entire basis is one sentence below it, and it names only published engine fields.

## Why this exact shape and not a merged tier word

A single tier word ordering both facts (e.g. READY / HALF-READY / EARLY) would be **inventing a claim**. `nearlevels.py:72-75` explicitly refuses to model playbook coverage, and `server.py:1724` knows nothing of risk. The two facts are not commensurable — the off-diagonal cases (in the zone with no playbook; far away with one) would misread under any total order. Keeping the badge as `reach · play` means the tier word is a pure function of one field, the suffix a pure function of another, and only the **colour** carries the combined ranking. Nothing is fused; the ranking is still total.

It also kills the complaint directly: `PLAYABLE` and `CONTACT` can never again appear as alternatives, because both facts are on every card on every list.

## Precisely what it replaces

| Removed | Where |
|---|---|
| `CONTACT / TRACKING / HOLDING / OUT OF REACH` as stamp words | `NEAR_SAY` labels, shell.js:1903, 1906, 1909, 1912 |
| `PLAYABLE / NO PLAY` as a standalone stamp | shell.js:2153-2154 |
| `A / B / C / D` letter and `.wl-grade` / `.wl-grade-why` | shell.js:2102-2103, 2164-2165; CSS `ss.css:1859-1873` |
| `chip-t3..chip-t0` (already dead — index 1 of every `NEAR_SAY` tuple, never read) | shell.js:1903-1912; `ss.css:1846-1849` |

The `NEAR_SAY` **sentences** (`say[2]`, shell.js:2113) survive — they are the plain-language half the design argument at shell.js:1892-1900 insists on, and `test_near_levels_panel.js:96-109` pins one of them.

## Precisely what must survive separately, and why

Each answers a different question backed by a different engine field. Fusing any two invents a claim.

| Vocabulary | Field | Why it cannot merge |
|---|---|---|
| `IN TRADE` / `ORDER RESTING` (`st-live`/`st-rest`, ss.css:1389-1394) | lifecycle, shell.js:356-359, 947-948 | "Is my money on this" is not "where is price". Mission Briefs only. |
| `FORMING` (`st-form` dashed, ss.css:1436) | `overview.approaching`, shell.js:1774, 1820 | A scanner setup-state, not a distance reading. |
| `CLEARED / REDUCED SIZE / NOT TRADED / AWAITING VERDICT` | `risk.decision`, shell.js:1685-1688 | The risk authority's verdict. `PLAYABLE` does not imply it — `server.py:1724` never consults `risk.py`. Moves to Diagnostics with the refused cards. |
| `ADMITTED / SHADOW / WARMING` | universe state, `engine/universe.py:403-436` | Can this symbol *ever* be sized. Currently printed as a **raw enum** at shell.js:2155 — must be given labels. |
| `PASS / DEGRADED / BLOCKED` | pipeline audit, shell.js:3488 | Data trust. |
| `NO CONNECTION / API DEGRADED` | transport, shell.js:289-296 | Can the browser reach the PC. **Shares `#healthTxt` with the above** and shares the word DEGRADED — split (step 12). |
| `WATCHING / NOT WATCHING` | scanner, shell.js:520-527 | Engine liveness. |
| Regime labels | `server.py:1594-1597` | Market condition. |
| `PLAN / ENGINE / YOURS / LIVE` | `base.kind`, chart.js:333-356 | Whose bracket is on the chart. |
| `MET / NOT MET` | live-gate, shell.js:4105 | Record-quality criteria. |
| ~45 `failure_code` sentences + `SHORT_REASON` | funnel.js:68-281, shell.js:649-664 | Deliberate documented pair (shell.js:646-648). Fine. |

## Two collateral vocabulary fixes in the same pass

1. **`READY` vs `CLEARED` on one card.** For `decision === 'APPROVED'` the stamp says `READY` (shell.js:1685) and the chip 30px below on the same card says `CLEARED` (shell.js:1671, via `DECISION_LABELS` at shell.js:1533-1535). Same for `AWAITING VERDICT` vs lowercase `awaiting decision` (shell.js:1688 vs 1677). **Fix: the stamp reads `DECISION_LABELS` — one map, one word per enum value.**

2. **The Results stat wheel puts a metric NOUN in the verdict slot.** `.mc-stamp` holds "Worst trade", "Max drawdown", "Win rate" (shell.js:3905-3951, printed 3966) and colours them `st-go`/`st-dead`/`st-wait` (shell.js:3965-3966) — so "Worst trade" wears the red that elsewhere means NOT TRADED. This resolves itself when the stat wheel is deleted (step 8); if it is kept, the slot must become a neutral `.mc-label`.

3. **`LOCKED` means two things.** Results Progression `EARNED / LOCKED` (shell.js:4036) is a milestone the record has not reached; Settings `LOCKED — see Going live` (shell.js:3788) is live execution being off. After the merge in step 8, Progression uses **`MET / NOT MET`** for everything and `LOCKED` survives only on Settings, meaning one thing. Note `test_rules_surface.js:100-104` pins the exact string `LOCKED — see Going live` — leave that string alone.

---

# 2. SURFACE MAP

## Command — "What should I do right now?" (shell.html:86-382)

| # | Panel | Change |
|---|---|---|
| 1 | Disposition line `#disposition` (shell.html:107) | Keep. Its "in the deck below" (shell.js:851) becomes true again once `ordered` renders into the rail. |
| 2 | Briefing `#firstRun` (shell.html:116) | Keep. |
| 3 | Scanner + 4 tiles (shell.html:137-185) | Keep. Panel treatment normalised (step 10). |
| 4 | Rules of engagement `#budgetPanel` (shell.html:195) | Keep. Today's P&L now read from one authority (step 11). |
| 5 | **Mission Briefs** `#mbTrack` (shell.html:262-305) | Keep, promoted to the surface's only rendering of the book. **Absorbs** `ordered` setup cards, plus the keyboard, copilot and trace affordances from the deleted Engaged detail. |
| 6 | Hand-picked `#minePanel` (shell.html:218) | Keep, **moved to sit directly after Mission Briefs**. Separate panel, separate header — never merged (shell.js:2478-2481, shell.html:212-214). |
| 7 | **Overwatch** `#nearPanel` (shell.html:329) | **One ranked rail, no tabs.** |
| 8 | `#missionLede` (shell.html:303) | Keep — weather.js:241 still writes it. |
| 9 | Bitcoin cycle backdrop | **Moves to Chart.** |

**Out of Command:**

- **`#posPanel` / `#positions` "Engaged — detail" (shell.html:237-243) — DELETED.** Operator's explicit instruction, and it is a literal duplicate: `renderPositions` builds `active_positions` + `pending_orders` (shell.js:2329, 2336) — the same two arrays `renderMissions` builds (shell.js:887-888) — and calls `renderMissions` itself at shell.js:2327.
- **Refused tab `#passed` → Diagnostics.** shell.js's own comment at 1044-1049 says why: *"the question they answer is 'why did nothing fire', and that is not the question the rail answers."* Command asks what to do now; Diagnostics asks what failed. Diagnostics already holds the aggregate view of exactly this (shell.html:1022, funnel.js:661).
- **Three of four tabs (`#nearFar`, `#allMarkets`, `#mwSeg`) — DELETED.** "Out of reach" is now just the grey bottom of the one ranking. "All markets" is now the rail itself.
- **Bitcoin cycle backdrop → Chart.** Its own footer says *"Never consumed by any trading engine — nothing here opens, sizes or blocks a trade"* (weather.js:183-184) and it carries an "observational" chip (weather.js:175). Nothing on it can answer "what should I do right now". Chart answers "is this setup worth taking?" — context for one decision is exactly what it is.

**Overwatch after the change:** one panel, one rail, **one card per symbol** over the whole weather universe, each carrying its nearest zone row (`nearestBySym`, shell.js:2138-2143 — already the honest summary argued at shell.js:2134-2137), ranked by the Reach & Play scale.

The per-timeframe detail is not lost: the regime strip already prints every timeframe with its label bound to it (`wl-regs`, shell.js:2175-2177), which is exactly the property `test_audit_closeout.js:120-125` pins. What *is* lost is a second card for a symbol at `AT_ZONE` on 15m and `IN_RANGE` on 4H. That is the trade the operator asked for ("one deck, ranked"). Flagging it explicitly; if he wants the extra rows back, they go behind a per-card `<details>`, not a tab.

## Chart — "Is this setup worth taking?" (shell.html:385-689)

Structurally unchanged. Two additions/fixes:

- **Bitcoin cycle backdrop** lands below the chart pane, collapsed (`<details>`, weather.js:171).
- **Regime is printed raw** at chart.js:992 (`reg.replace('_',' ')`) and chart.js:724, while Overwatch prints the mapped label (`server.py:1594-1597`). Same field, two registers, two surfaces. Use the label on both.

## Results — "Is this actually working?" (shell.html:692-854)

| # | Panel | Change |
|---|---|---|
| 1 | Era band `#resultsEra` (shell.html:699) | Keep. |
| 2 | ~~Stat wheel `#statTrack`~~ (shell.html:712-724) | **DELETE** — see the carousel rule in §3. |
| 3 | Money tiles + Method tiles + `#rSample` (shell.html:726-748) | Keep. These are the surviving rendering of the eight headline numbers. |
| 4 | **Progression** `#progTrack` (shell.html:764) | Keep as a rail, and **absorb the four Going-live criteria from Settings**. One track, one `MET / NOT MET` vocabulary. |
| 5 | Trade Journal (shell.html:775) | Keep. |
| 6 | Equity Curve + `#baselineChip` (shell.html:784-799) | Keep. `#baselineChip` gets a Results-surface loader (fixes the frozen chip). |
| 7 | By Symbol / By Strategy (shell.html:826-845) | Keep. |
| 8 | Forward Record `#resultsNote` (shell.html:847) | Keep. |
| 9 | Link row to **Ledger** | New, one line, no numbers restated. |

**Why Going-live's criteria move here:** both are wheels of `.mc` cards with a met/not-met stamp, a progress ring and a note; both measure the forward record; they share two criteria outright (sample size — gate at shell.js:4090 vs Progression rows at shell.js:4000/4003; drawdown — gate at shell.js:4092 vs "Shallow water" at shell.js:4009). Progression's 100-trade row literally cites the gate: *"Settings → Going live holds real orders until this lands."* Results asks "is this actually working?"; Settings is configuration. shell.html:964-968 already flags the gates as *"the only card-shaped thing on Settings."*

**Ruling on `#edgeRoot` ("Is the edge real?"):** the audits found `shell.html` carrying two contradictory comments fourteen lines apart — 1052-1057 says *"It now sits under the equity curve on Results"*, 1066-1069 says *"moved here from Results (operator ruling)"*. The DOM agrees with the second (shell.html:1070). **Recommendation: it stays on Diagnostics.** The operator ruling is the later authority, and shell.html:801-817 records that a previous attempt at this move broke the document tree. Fix the copy instead: edgeview.js:270-272 says *"the tiles above"* on a surface with no tiles above it — name the surface. Delete the stale comment at shell.html:1052-1057.

## Settings — "keys · Claude · configuration" (shell.html:857-978)

| # | Panel | Change |
|---|---|---|
| 1 | Exchanges `#credFields` (shell.html:873) | Keep. Future home of the wallet-balance wiring. |
| 2 | **Risk + Guardrails → one panel** (shell.html:889-911 + 949-956) | **MERGE.** Both print daily loss halt, max concurrent and total open risk. `#riskNow` reads `/api/trade-config` where values are fractions (shell.js:3583-3596); `#guardRows` reads `/api/settings.values.risk_config` where they are percentages **and invents client-side fallbacks of 6, 2 and 4** (shell.js:3776-3788). Two authorities, two unit conventions, UI-invented defaults for numbers the engine owns. Keep `/api/trade-config` only; delete the fallbacks. |
| 3 | Strategies & Universe (shell.html:912) | Keep. |
| 4 | Claude (shell.html:934) | Keep. |
| 5 | **Going live** (shell.html:961-976) | Reduced to **the lock and its consequence**: `#gateChip`, `#gateFoot` (the `build_note` from livegate.py:195-197), and a link to Results → Progression. The four criteria cards leave. |

Also fix: `loadRisk()` is tagged `'command'` in `LOADER_SURFACE` (shell.js:4778) but its only DOM output is `$('riskNow')` — on **Settings**. Verified: `go()` rewrites the hash (shell.js:77), so any reload or `POST /api/system/restart` while on Settings leaves the panel **literally blank**, with no empty-state rule on `.tk-out` (ss.css:1162-1173) — a silent blank, which brushes the audible-degradation rule. Re-tag to `null`. (Note the `'command'` tag does not even buy the side effect it looks like it was for: `setAccentMode()` is already called from the ungated `loadPortfolio` chain at shell.js:2510 and 3109.)

## Diagnostics — "what is failing, and why" (shell.html:981-1106)

| # | Panel | Change |
|---|---|---|
| 1 | Failing now `#failingRoot` | Keep. |
| 2 | Pipeline `#dVerdict` | Keep. |
| 3 | Why nothing fired `#dFunnel` + `#funnelRoot` | Keep. |
| 4 | **Refused setups** (`#passed` → `#refused`) | **NEW HOME.** Per-instance view immediately under its own aggregate. **Needs its own `LOADER_SURFACE` entry** — see §6 step 6. |
| 5 | Open Issues / Setup Telemetry | Keep. |
| 6 | Is the edge real? `#edgeRoot` | Keep here; fix its copy. |
| 7 | Decision Provenance | Keep. |
| 8 | Backend Console | Keep. |

## NEW SURFACE — `s-ledger`, "Where are the wins coming from?"

**Name: Ledger.** Nav key `6`. This is the operator's own request, and it is buildable today from data already on disk.

### Three books, side by side, never summed

**Column A — Engine, paper account.** From `/api/portfolio` (server.py:792-964). Equity **$9,406.82**, start $10,000, return **−5.93%**, max drawdown 5.14%, decisions `{APPROVED:4, REDUCED:5, REJECTED:30}`, plus trades closed / win rate / avg R / profit factor from the journal. Era label: **"forward window"** — scoped to the active baseline (server.py:797-798, 229-251).

**Column B — Your hand-armed trades.** From `/api/manual/book` (server.py:2696-2704 → manual.py:1283-1328). `n` settled, `wins`, `win_rate`, `total_r`, `expectancy_r`, cumulative-R curve, and a **new dollar total** (below). Era label: **"recorded book"** — all history, no baseline filter, by design (manual.py:1289-1293).

**Column C — Your exits on engine trades.** From `/api/portfolio.operator_closed` (server.py:939-941). Live today: 1 row, UNIUSDT 4H SHORT, `r_at_close` 0.70, `usd_at_close` **+$136.22**. This money is counted in **no** total anywhere — `risk.py` contains no reference to `manual` or `override`, and `manual.book()` reads `EXEC_KIND` only (manual.py:1296). It is the purest measure of operator skill in the store: the engine picked the trade, the operator picked the exit, both outcomes recorded.

Below each column: a per-trade table (symbol, date, R, $). The manual side has everything already — manual.py:1220-1274 carries symbol, tf, direction, outcome, entry, exit, r_multiple, r_gross, costs, `risk_usd`, venue, `fill_ts`, `resolved_at`.

### The honesty banner, above all three, non-optional

One short paragraph stating: the three books cover **different windows and different capital**, they are **not added**, and the forward record is currently negative. `manual.arm` never consults the risk authority (server.py:2643-2646), so hand-armed size was never drawn from the engine's $10,000 — a combined "main wallet" figure would be an invention today. Two figures with two labels is honest; one figure made of both is the exact leak the version separation exists to prevent (manual.py:8-10, 18-23; test_manual.py:58-78).

### Server work required (the UI may not derive these)

| New field | Where | Definition |
|---|---|---|
| `pnl_usd` per settled row | `manual.book()`, manual.py:1298-1299 | `Decimal(r_multiple) × Decimal(risk_usd)`, quantized `ROUND_HALF_UP` — **the same arithmetic as server.py:925-927**, so the two books' dollars are apples to apples. |
| `total_pnl_usd` | `manual.book()` return, manual.py:1318-1328 | Sum of the above. |
| `n_no_risk_usd` | same | Count of settled trades where `risk_usd` is null. **Printed on screen** — `chart.js:2204` sends null when the ticket has no valid risk figure and `manual.py:411` stores it, so such a trade has an R but no dollars, permanently. Silence there would be a silent degraded path. Live: 1 of 6 intents. |
| `operator_closed_usd` | `/api/portfolio`, server.py:939-941 | Sum of `usd_at_close`. |

**Version question, answered:** `MANUAL_VERSION` tags *facts*. `book()` is a read view and already reads every manual version (manual.py:1289-1293). Adding a derived aggregate to a read view is **not** a second generation of output under an existing `algo_version` — **no bump**. If the P&L were ever persisted as a fact, that *would* be a bump.

### Where the wallet balance slots in later, without faking it now

A fourth band, visually separate, at the top: **"Exchange wallet — not connected."** No number, ever, until a real balance arrives.

The gap is real and specific: the credential vault exists (`credentials.py`, DPAPI-encrypted per venue), `read_secret` exists (credentials.py:129-138) and is documented as *"NOT reachable from any HTTP route… A signed-request layer would call this directly"* — and has **no caller**. There is **no `hmac` import anywhere in `app/`**; `kraken.py:10-12` and `phemex.py:14-16` both say *"It holds no credentials, signs nothing, and cannot place an order."* `POST /api/credentials/test` does not exist and shell.js:4402-4404 handles the 404 honestly with *"not available in this build"*.

Build order when it comes: (1) per-venue request signing; (2) `balance(venue)` on the adapter returning Decimal, following `venues.py:20`'s rule that nothing else branches on venue by name; (3) a **read-through endpoint that stores nothing**, with `measured_at` on the payload the way `/api/manual/live` already does (server.py:2670) — a polled balance is a live reading, not a fact; (4) an audible failure path that says "unreachable" rather than showing the last figure; (5) hard separation from paper equity — never the same tile, colour or arithmetic. A balance read is **not** progress against the live-execution gate (`credentials.py:16-18`, `server.py:2160` pins `live_enabled: False`) and must not look like it.

---

# 3. WHERE A CAROUSEL IS RIGHT AND WHERE IT IS WRONG

**The rule, applicable to the next panel by anyone:**

> **Use a card rail when the operator can answer their question from the front card alone. Use a grid or a table when answering it requires seeing two items at the same time.**

That single test decides it. Three supporting conditions must also hold for a rail:

1. **The items are peers of one kind** — same fields, same badge vocabulary, same question answered. A rail mixing kinds teaches nothing.
2. **The set is open-ended.** You cannot know at build time how many there will be. A fixed, known-at-build-time set should be laid out, not paged.
3. **Order carries meaning.** Position 1 is better/next/nearer than position 2, and the panel says on what basis.

**Applied:**

| Panel | Front card enough? | Verdict |
|---|---|---|
| Mission Briefs (shell.html:262) | Yes — "what am I in" is answered one trade at a time | **Rail** ✓ |
| Overwatch (shell.html:329) | Yes — "what is closest to being tradeable" | **Rail** ✓ |
| Progression + Going-live gates | Yes — "what is the next milestone" | **Rail** ✓ |
| **Results stat wheel** (shell.html:712-724) | **No** — a win rate is meaningless without the trade count beside it; a return is meaningless without the drawdown | **Grid** ✗ → delete the wheel, keep the tiles |
| Risk / Guardrails (shell.html:889, 949) | No — they are a set of caps read together | **Key/value rows** ✗ |
| By Symbol / By Strategy, Setup Telemetry | No — the whole task is comparison | **Table** ✗ (shell.js:3358-3363 already argues this) |
| Open Issues | No | **`<details>` list** ✗ |

**Ruling to confirm with the operator:** deleting the stat wheel undoes recent work. The alternative — delete the eight tiles and keep the wheel — is *not* my recommendation, because eight numbers whose whole purpose is mutual comparison belong side by side. The wheel/grid pair is currently documented as deliberate at shell.html:702-711; one of the two has to go, and the rule says the wheel.

**And fix the affordance split.** `makeRail`'s `prev`/`next`/`status` options are passed by only two of eight call sites — Mission Briefs (shell.js:1418) and the stat wheel (shell.js:3979). Progression (shell.js:4052), Going live (shell.js:4122) and all four Overwatch groups (shell.js:1406) get bare rails: **no arrows, no `card 3 of 9` announcement** (`navState`, shell.js:1306-1313, is a no-op without `opts.status`). After this change there are three rails; **all three get full chrome.**

---

# 4. DELETIONS

## 4a. Dead JS — zero references anywhere

| Item | Location | Evidence |
|---|---|---|
| `LADDER_TONE` | chart.js:709-713 | The only zero-reference declaration in the entire static tree. `grep -n LADDER_TONE` returns its own line only. eslint `no-unused-vars`. |
| `deckPainted` | shell.js:1207 (decl), 1104 (write) | Write-only. Its consumer (`animationend` listener) no longer exists — `grep animationend` over static/*.js returns nothing. |
| `mwActive` | shell.js:2233 (decl), 2237 (write) | Write-only. Dies with the tabs anyway. |
| `const uc = o.universe_counts \|\| {}` | shell.js:485 | Leftover duplicate of the **live** one at shell.js:409 (read at 412-415). |
| `long` | chart.js:411 | Assigned, never used. |
| `dupWarnEl` | chart.js:1883 | Assigned, never used. |

## 4b. Dead CSS — defined, never emitted

**Going-live gate bars (~16 rules).** `ss.css:2331` `.gate-row`, `:2333` `.gate-head`, `:2335` `.gate-mark`, `:2337` `.gate-label`, `:2339` `.gate-have`, `:2341` `.gate-bar` (incl. reduced-motion at `:2345`), `:2346` `.gate-note`, plus `.gate-list` as a dead member of the live selector group at `ss.css:352`. Zero emitters. Replaced by `.mc.gate-card` (shell.js:4103) with its ring at shell.js:4113. **Keep** `.gate-card`, `.gate-body` (shell.html:964), `.gate-foot` (ss.css:2348).

**Chart context ladder (10 rules).** `ss.css:449-462`: `.ctx-ladder`, `.lx`, `.lx.on`, `.lx-bull`, `.lx-bull-w`, `.lx-bear`, `.lx-bear-w`, `.lx-trans`, `.lx-range`, `.lx-none`. chart.js:700's own comment says the ladder *"had zero callers"*; `loadContext()` (chart.js:714-732) now only sets `el.title`.

**Card-arrival animation (6 rules + 3 keyframes).** `ss.css:1514-1516` `.mc-new`, `.mc-new .mc-stamp`, `.mc-new .mc-ring-fill`; `@keyframes mcLand` (`:1524`), `mcStamp` (`:1525`), `mcRing` (`:1527`), each used by exactly one `.mc-new` rule; plus the reduced-motion rule at `:1570`. `grep mc-new` over static/*.js/*.html returns nothing — the class is never applied. Goes with `deckPainted`.

**Reach chips.** `ss.css:1846-1849` `.chip-t3`..`.chip-t0` plus the misleading comment at `:1845`. **Also delete the comment at shell.js:1899-1900** which asserts the chips are live.

**`.chip-live`** `ss.css:388-390` plus `@keyframes livePulse` `ss.css:391` — its only rule.

**Twelve further orphans, four pinned by *negative* test assertions** (the tests assert the markup must NOT return, so deleting the CSS cannot break them and none of them reads `ss.css`):

`ss.css:466-473` `.fine-print` (5 rules — `test_rules_surface.js:70`); `ss.css:2204-2207` `.panel-sub` (3 — `test_word_budget.js:77`); `ss.css:564` `.deck-note` (2 — `test_word_budget.js:78`); `ss.css:1995-1996` `.cp-scrim` / `.cp-drawer` (`test_copilot_dock.js:64`; copilot.js emits `.cp-dock` at copilot.js:77). Plus: `ss.css:487` `.explainer-body` (3) and `:490` `.explainer-steps` (4) — the one `.explainer` in the tree (shell.html:1079) uses `.prov-body` (shell.html:1084); `ss.css:558-559` `.locked-ctl` / `.locked-why`; `ss.css:598` `.btn-lg`; `ss.css:783-785` `.cols-3` (3); `ss.css:1769` `.radar-meter` (3) plus its reduced-motion rule at `:1964` — **`.radar-say` IS live** (shell.js:1841, 2113, 2180), do not confuse them; `ss.css:1986` `.stub` (2); `ss.css:2149` `.readonly-block` (2).

**weather.css — ~30 classes, roughly 60% of the file.** The per-symbol grid `weather.js` no longer renders (weather.js:61-73 says so; `test_audit_closeout.js:120` asserts `!/wx-row|wx-data/` against weather.js, confirming the removal was deliberate). Dead: `.wx-body:25`, `.wx-row:27` (11 rules), `.wx-data:29` (3), `.wx-head:34` (4), `.wx-sym:39` (4), `.wx-toggle:48` (2), `.wx-tf:58` (8), `.tfk:63`, `.reg:65`, `.r-bull:69`, `.r-bull-w:70`, `.r-bear:71`, `.r-bear-w:72`, `.r-trans:73`, `.r-range:74`, `.r-none:75`, `.b-long:78`, `.b-short:79`, `.b-gated:80` (2), `.b-flat:81` (2), `.b-unknown:85`, `.wx-mean:89` (6), `.wx-arrow:93`, `.tier-3`/`.tier-4:94` (2), `.wx-why:99` (3), `.wx-foot:106` (2), `.wx-ver:110`, `.wx-lead:169`, `.wx-summary:171` (6), `.wx-details:177`. Also `--wx-cols` (weather.css:17 plus overrides at `:125` and `:128`) — consumed only by the dead `.wx-row`.

**Two traps in that list.** `.wx-details` hides from a naive scan because the string appears in a shell.js **comment** at line 2023 — it is dead. And in `weather.css:126-139` only `.wx-sub{display:none}` at `:127` stays.

## 4c. DO NOT DELETE — looks dead, is not

| Item | Why |
|---|---|
| `.deck-row` | Emitted at shell.js:915 and 1078; 16 rules in ss.css. Also read by `glossary.js:149`'s selector list — a future removal must update that too. |
| `.lvl-entry` / `.lvl-tp` / `.lvl-sl` (ss.css:932) | Built dynamically: `el.className = 'lvl lvl-' + k` (chart.js:188) over `['entry','tp','sl']` (chart.js:186). |
| `.toast-good` / `.toast-warn` / `.toast-bad` (ss.css:1016-1018) | Built dynamically at shell.js:4609. |
| `#btnAuto` (shell.html:156) | No runtime consumer, but `test_action_feedback.js:81` references it. |
| `#budgetPanel` (shell.html:195) | Same — `test_trade_surfaces.js:61`. |
| `#venueNote` (shell.html:47) | Targeted by `ss.css:660`. |
| `.wl-btn`, `.wl-say` | Comment-only; no rule exists (`ss.css:1962`). Nothing to delete. |

`.gate-bar`'s CSS is safe to delete despite `test_rules_surface.js:115` — that assertion is an either/or (`/ringSvg\(\(c\.progress/ || /gate-bar/`) satisfied by the first branch today.

## 4d. Inert ids and undefined classes

**Ids with no consumer of any kind:** `#modeChip` (shell.html:49), `#chartPane` (shell.html:453 — styled by its `.chart-pane` class at ss.css:910). Leave `#failingPanel` (shell.html:1004) — its children are live and the id costs nothing.

**Classes applied but defined nowhere:** `.mb-panel` (shell.html:262) — grep across ss.css, weather.css, diagnostics-ui.css, every .js and every test returns nothing. And **`.floating-head` / `.floating-body`**, which is a live layout bug, not just dead markup — see step 10.

## 4e. Panels deleted by this plan

| Removed | Lines |
|---|---|
| `#posPanel` / `#positions` markup + `renderPositions()` + `#positions` keydown handler | shell.html:237-243; shell.js:2321-2469, 3088-3097 |
| `#mwSeg`, `#nearFar`, `#allMarkets`, `MW_GROUPS`, `mwShow`, `mwCounts`, `wireMarketWatch` | shell.html:334-355; shell.js:2232-2273 |
| Stat wheel `#statTrack` markup + `statCards()` + `renderStatWheel()` | shell.html:712-724; shell.js:3897-3983 |
| `#guardRows` markup + `gr()` block | shell.html:949-956; shell.js:3776-3790 |
| `gradeOf()` and `.wl-grade` / `.wl-grade-why` CSS | shell.js:1964-1978; ss.css:1859-1873 |

Carried out of `renderPositions` before it goes: the keyboard-operable symbol control, the `data-trace` button, the composed `holdAsk` copilot offer, and `lastPortfolio = p || {}`. See §5.

---

# 5. TEST CONTRACT CHANGES

23 JS suites and 4 Python suites read the shell. **26 assertions** touch this plan.

## Must be re-pinned (the property survives; the shape does not)

| Assertion | File:line | Property it must keep protecting | Re-pin to |
|---|---|---|---|
| `id="positions"` in anchors list | `test_core_hardening.py:405-407` | An open trade is readable without already knowing which chart it is on | `id="deck"` is already in the same list — drop `id="positions"` and **update the docstring at :400-404**, which explains the old shape |
| `id="rEquity"`, `id="rDD"` in the same list | `test_core_hardening.py:405-407` | Equity and drawdown are surfaced | Unchanged if the tiles stay (they do) |
| `indexOf('id="minePanel"') < indexOf('id="posPanel"')` | `test_your_trades.js:75-76` | Your book is never merged into the engine's | `indexOf('id="deck"') < indexOf('id="minePanel"')`. Note this **reverses** the old ordering. Its two companions (`!/active_positions.*\.concat\(.*manual/i` and `hand-picked · not engine record`) carry the safety invariant on their own and are unaffected |
| `(JS.match(/class="pos-sym pos-open"/g)).length >= 2` | `test_trade_surfaces.js:202-219` | A filled position **and** a resting order are both keyboard-operable | The mission card's real `<button>`. **Mission cards do not satisfy this today** — they carry `data-sym`/`data-tf` (shell.js:974), not a focusable symbol control |
| `$('positions').addEventListener('keydown'` + `data-manage` + `go('chart')` | `test_trade_surfaces.js:466-473` | Enter/Space does the same thing as a click | The mission rail's own handler |
| `<button class="btn" data-trace=` | `test_trade_surfaces.js:458-465` | The trace is reachable as its own control | Mission cards use `data-why` (shell.js:972); `>Reasons</button>` survives at shell.js:973 and 1739 |
| `.pos-acts` min-height 48px below 900px | `test_responsive_layout.js:138-146` | Write controls are thumb-sized | `.pos-acts` has no emitter outside `renderPositions` (shell.js:2415, 2460) → re-point at the mission card's action row |
| `.pos-ends{`, `.pos-r .t-sub{` must not use `var(--fg-4)` | `test_trade_surfaces.js:271-279` | Prices and dollars clear the contrast floor | Both selectors survive via `renderMine` (shell.js:2556, 2562, 2611, 2617) — **no change needed**, but confirm after the move |
| `.deck-row .btn` min-height 48px | `test_responsive_layout.js:127-136` | Thumb targets on Command | Rule already covers `.mc .btn` (ss.css:1558-1560) — safe if the new cards stay `.mc` |
| `const SURFACES = [...five ids]` | `test_shell_structure.js:50` | **Fails OPEN.** A sixth surface is not depth-checked at all | Add `'s-ledger'` in the same commit as the section. This is the one item that stays green while covering nothing — and blank Settings/Diagnostics is exactly the defect this file exists for (`test_shell_structure.js:1-20`) |
| `CEILINGS = {command:120, chart:200, results:130, diagnostics:220, settings:260}` | `test_word_budget.js:96` | Static prose does not creep back | **Also fails open** — an unbudgeted surface can carry any prose. Measure Ledger and add its ceiling in the same commit |
| `KEYS` map, `'2'..'5'` loop | `test_trader_basics.js:87-92` | Every surface has an accelerator | Add `'6'`. **Then re-verify the money-off-hotkeys check at `:105-116`** — it slices a **fixed 1400 chars** after `const KEYS = ` and asserts `tkArm`/`btnHalt`/`arm(`/`cancel` are absent; a sixth entry pulls ~20 more characters into that window |
| `Keys: 1–5 switch surfaces` toast | shell.js:214 (**not pinned**) | — | Update or it silently becomes a lie |
| `assert(/no setups right now/.test(JS))` | `test_loading_states.js:114-119` | Genuine empty states stay as text, not skeletons | **Currently matches only comments** — the rendered string is `No setups right now.` (capital N, shell.js:717). Fix to `/[Nn]o setups right now/` while the file is open, or the empty state could be deleted with the suite green |

## Must travel with the moved code (property is load-bearing, unchanged)

| Assertion | File:line | Property |
|---|---|---|
| `s.why` reaches the deck; `.deck-why`; **`.deck-row.dead .deck-why`** | `test_ui_field_contract.py:172-202` | *"a persuasive rationale shown at full contrast on a setup the RISK AUTHORITY REFUSED is the worst thing this deck can render."* The `dead` class is applied at shell.js:1078 from `decision === 'REJECTED'` — **if the badge rewrite renames it, this Python test fails and the visual guard disappears with it.** Highest-priority item to carry to Diagnostics |
| Three distinct `deckEmptyHtml` branches | `test_empty_state_honesty.js:156-171` | A fresh baseline must not read as "broken" |
| `:scope > .skeleton, :scope > .empty` cleared **before** the first `appendChild` | `test_loading_states.js:96-112` | Found live: the keyed differ appends, so a real setup once rendered *underneath* the loading skeleton |
| `deckRowInner(s, now)` + `const now = Date.now()/1000` above the loop | `test_render_scope.js:74-101` | The row clock is bound once, in seconds. **`bodyOf` returns null if `renderDeck` becomes a `const` arrow** — the test then fails with "renamed?" |
| Four `engine_reach` states have a sentence in JS **and** exist in Python | `test_near_levels_panel.js:96-104` | No orphan state |
| The `OUT_OF_RANGE` sentence contains `not considering` **and** `not the engine` | `test_near_levels_panel.js:106-107` | Far rows must not read as an engine plan. **Fragile slice**: bounded by the first `OUT_OF_RANGE:` and the literal `function renderNear` — moving the vocabulary table below `renderNear`, or converting it to an arrow, inverts or empties the slice |
| `#nearPanel`, `#near`, `#nearLede` exist; empty list hides the panel; no `PROX_ATR`/`FORMING_TFS`/hard-coded `1` in the client; `d.warnings` + `could not be read`; `shadow_excluded` in the lede; `['command', () => loadNearLevels()]` and **not** `[null, …]` | `test_near_levels_panel.js:51-132` | Six honesty invariants. **All six must hold on the single ranked deck** |
| `!/wx-row\|wx-data/` on weather.js; `class="wl-reg` **and** `<b>${esc(t.tf)}</b>` in shell.js | `test_audit_closeout.js:120-125` | Every regime label stays bound to its timeframe. *"A bare 'Bear weakening' with the '4H' lost is the accessibility failure this assertion exists to catch"* |
| `SSState` owns `engaged()`, `lifecycleOf(`, `deck()`, `symbolSets()`; `window.SSFormat` carries `money`, `px`, `rr`, `pct`, `units` | `test_one_source_of_truth.js:34-40, 91-96` | **Critical for Ledger.** A new money surface formatting its own dollars reintroduces the exact bug at `:82-89` — *"$193 / $195 / 194.68 / $194 was the money version of this"* |
| `ERAS = ['forward window', 'recorded book']` and both surfaces cross-link | `test_era_labels.js:39, 61-80` | **Also critical for Ledger.** The engine book is baseline-scoped, the manual book is not — the two nouns must be used exactly, and Ledger must be added to this test's coverage |
| `perfRows`/`/api/performance` field names held against the live endpoint | `test_ui_field_contract.py:67-88` | *"a missing number defaulting to zero, and zero reading as flat rather than as absent."* **Ledger needs its own `_reads_in` contract test** or it will render a confident zero |

## Shape-agnostic — nothing to re-pin, just comply

`test_responsive_layout.js:89-125` (any new `grid-template-columns` with a ≥300px pixel floor needs a ≤900px counterpart; new media queries **only** at 640/900/1100/1180 — *"The file was rescued from twelve of these once"*). `test_loading_states.js:38-56` (every `class="skeleton"` must be exactly `class="skeleton" role="status" aria-label="loading"`, and named blocks need `height:\d+px`). `test_semantics_and_keyboard.js:33-50` (`<h2>` count ≥15, no `<span class="t-section">`, balanced tags). `test_trade_surfaces.js:237-269` (every `<div id="…Root">` between `</main>` and the statusbar must be covered by the `.shell > #…Root{position:absolute}` rule — self-extending by design). `test_word_budget.js:76-90` (panel titles under four words; `panel-sub` stays deleted). `test_rules_surface.js:31` (`data-s="settings">Settings<` — the label must follow the attribute **immediately**; copy the Command/Diagnostics pattern at shell.html:70/75 where the `nav-count` span comes **after** the label).

## Fixed-window slices to re-read after ANY step lands

These slice `shell.js` by byte offset or first-match anchor. Restructuring shifts them, and the failure is **silent in one direction** — an undershooting slice passes vacuously. The repo already documents this scar three times (`test_trade_surfaces.js:576-581`, `test_action_feedback.js:55-57`, `test_loading_states.js:104-106`).

`test_trade_surfaces.js:215` (`[\s\S]{0,900}?pos-acts`), `:455` (`{0,220}`), `:469` (`{0,420}`); `test_action_feedback.js:63-69` (`JS.slice(i, i+1200)`); `test_near_levels_panel.js:106`; `test_trader_basics.js:109` (`+1400`).

**A green suite is not evidence these still delimit what they name. Re-read all six by hand after each step.**

---

# 6. ORDERED WORK PLAN

Each step ships independently and leaves the app working. Verify every step with:

```
cd app
python -m pytest tests -q
for f in tests/test_*.js; do node "$f"; done
npx eslint .
python -c "import pathlib;bad=lambda r:[i for i,b in enumerate(r) if b<32 and b not in (9,10,13)];[print(p,bad(p.read_bytes())[:8]) for p in pathlib.Path('app').rglob('*') if p.suffix in {'.js','.py','.css','.html'} and bad(p.read_bytes())]"
```
(byte scan from repo root; silence is a pass) — **plus** the app in a browser, because the JS suites assert against source text, not a rendered DOM.

---

### Step 0 — Dead-code sweep (no behaviour change, unblocks everything)
**Touches:** `static/ss.css`, `static/weather.css`, `static/chart.js`, `static/shell.js`
Delete everything in §4a, §4b, §4d. Keep §4c untouched.
**Verify:** suites + eslint (the four `no-unused-vars` warnings for `LADDER_TONE`, `deckPainted`, `mwActive`, `uc` should disappear). Visual smoke on all five surfaces.

### Step 1 — Fix the live defects found during the audits (small, high value)
**Touches:** `static/shell.js`
1. shell.js:2655 — `toast('cancelled …', 'ok')` → `'good'`. `'ok'` is the only toast kind with no CSS rule (ss.css:1016-1018), so a successful cancel is the one success path rendering unstyled.
2. shell.js:741-744 — `deckSplit`'s token dedupe uses strict `<` on expiry, so on a tie the **first** row wins. Live, `PF_UNIUSD 4H (REJECTED)` beat `UNIUSDT 4H (APPROVED)` on the same token and the approved plan silently lost its slot. **Prefer the non-spent card on a tie.**
3. shell.js:4778 — re-tag `loadRisk` from `'command'` to `null` (otherwise the Settings Risk panel is blank on any boot at `#settings`).
4. shell.js:545-547 — `#baselineChip` is written only inside `loadOverview` (gated to Command), so on Results it is frozen or never written at all. Move it to a Results-tagged loader. Note it and `#resultsEra` come from **two different endpoints** (`/api/overview.baseline` vs `/api/portfolio.baseline`) that resolve to the same `store.get_active_baseline` (server.py:797, 1894) — so today they can name two different moments on one screen.
**Verify:** cancel a manual intent (green toast); reload on `#settings` (Risk populated); reload on `#results` (chip named).

### Step 2 — Engine fix: version-orphaned operator overrides
**Touches:** `app/engine/manual.py`, `app/server.py`
`setup_id` embeds `SETUP_VERSION` (setups.py:984), `manual.overridden_setups` keys on it verbatim (manual.py:439-445), and server.py:853 suppresses only on exact match. A version bump therefore re-mints the id and the suppression stops working **silently**. Live right now: UNIUSDT 4H appears as `…|setup-v0.17-draft` in `active_positions` **and** `…|setup-v0.15-draft` in `operator_closed`, same entry 4.379 — a trade the operator closed for **+$136.22** is reported as **$194.60 of live exposure**, and it is the only position, so `open_risk_usd` is entirely this one trade.

Confirmed not a re-validation: the VALIDATED setup facts under v0.13–v0.17 all carry the **identical `confirmed_at` (1785470400)** and byte-identical entry/sl/tp. It is one zone touch re-derived five times.

**Fix:** key overrides on the version-stripped setup id (symbol|tf|strategy|zone_id). **This is a behaviour change in what the engine reports** — bump the relevant version per CLAUDE.md and check `test_version_cascade.py`.
**Do this before Step 11**, or the Ledger surface ships with a wrong exposure number on day one.
**Verify:** `GET :8422/api/portfolio` — `active_positions` empty, `open_risk_usd` 0, `operator_closed` unchanged. Never POST to a write endpoint to test.

### Step 3 — The one ranking vocabulary (no layout change yet)
**Touches:** `static/shell.js`, `static/ss.css`
Introduce one `REACH_PLAY` function producing `{word, suffix, colourClass, rank, why}` from `(engine_reach, weather.live)`. Apply it at **both** existing call sites (shell.js:2093 and 2153-2154). Delete `gradeOf` (shell.js:1964-1978) and `.wl-grade`/`.wl-grade-why` (shell.js:2102-2103, 2164-2165; ss.css:1859-1873); the `why` sentence moves to the card body. Fix the risk stamp to read `DECISION_LABELS` (shell.js:1533-1535 → 1685-1688). Label the raw universe enum at shell.js:2155.
**Watch:** keep the `NEAR_SAY` table **above** `function renderNear` and keep `renderNear` a `function` declaration, or `test_near_levels_panel.js:106` inverts its slice.
**Verify:** on one symbol present in both `#near` and `#allMarkets`, the badge is now **identical** on both tabs.

### Step 4 — Collapse Overwatch to one ranked rail
**Touches:** `static/shell.html`, `static/shell.js`, `static/ss.css`
Delete `#mwSeg`, `#nearFar`, `#allMarkets` (shell.html:334-355) and `MW_GROUPS`/`mwShow`/`mwCounts`/`wireMarketWatch` (shell.js:2232-2273). One rail over the weather universe, one card per symbol carrying its nearest zone row, sorted by rank then `distance_atr`. Lede states the sweep, the shadow exclusions, and the ranking rule. Full rail chrome (`prev`/`next`/`status`) via `makeRail` (shell.js:1244-1392).
**Also fix the three ATR rings**, which today draw the same number at three different lengths: radar divides by `prox_atr` (shell.js:1800-1801), `#near` by `max_distance_atr` (shell.js:2029, 2038), `#allMarkets` by a **hardcoded 3** (shell.js:2169). One denominator — `d.max_distance_atr` off the payload. shell.js:1794-1799 records this exact bug class being fixed once already.
**Must still hold:** all six `test_near_levels_panel.js:51-132` properties, and `test_audit_closeout.js:120-125` (regime label bound to its `<b>${tf}</b>`).
**Verify:** empty near-levels hides the panel; a market with no zone renders `— · no zone`; ring fill matches the printed digits across cards.

### Step 5 — Delete the Engaged detail, promote Mission Briefs
**Touches:** `static/shell.html`, `static/shell.js`, `static/ss.css`, four test files
Delete `#posPanel`/`#positions` (shell.html:237-243) and `renderPositions` (shell.js:2321-2469) plus its keydown handler (shell.js:3088-3097). **Carry four things onto the mission card first:**
1. `lastPortfolio = p || {}` (shell.js:2322) — it is the **first line** of `renderPositions` and `renderMissions` reads it at shell.js:886. Deleting the function wholesale silently blanks the rail.
2. A real focusable `<button>` on the symbol, with `data-manage` and an Enter/Space handler doing what a click does.
3. The `data-trace` "Reasons" control.
4. The composed `holdAsk(t)` copilot **offer** (shell.js:2312-2319, 3057-3067) — it must reach the dock as a suggestion chip and must **never** auto-send (`test_copilot_dock.js:99-111` asserts both directions).
Render `deckSplit().ordered` into the rail so the "Active setups" tile (shell.js:504), the nav badge (shell.js:507) and the disposition line's *"in the deck below"* (shell.js:851) finally point at something that exists.
Move `#minePanel` to sit after Mission Briefs.
**Re-pin:** `test_core_hardening.py:405`, `test_your_trades.js:75`, `test_trade_surfaces.js:202-219, 458-473`, `test_responsive_layout.js:138-146`.
**Verify in the browser, not just the suites:** tab to a mission card, press Enter, confirm the chart opens on that symbol. Then re-read all six fixed-window slices listed in §5.

### Step 6 — Move Refused setups to Diagnostics
**Touches:** `static/shell.html`, `static/shell.js`, `static/diagnostics-ui.css`
Move `#passed` (shell.html:356-360) into Diagnostics as `#refused`, directly under "Why nothing fired" (shell.html:1022). **Add a `LOADER_SURFACE` entry** (shell.js:4774-4787) — `renderDeck` is fed only by `loadOverview`, gated to `'command'` (shell.js:4777), so without one, arriving on Diagnostics by hash, bookmark or the `5` key shows a stale paint with nothing saying so. Do **not** ungate `loadOverview`; give the refused feed its own loader (`test_near_levels_panel.js:127-132` pins the opposite direction for `loadNearLevels`, and a ~1.7s sweep on every surface is against the grain).
**Must travel:** `.deck-row.dead .deck-why` dimming (`test_ui_field_contract.py:172-202` — *"a rationale at full contrast under a refusal invites the operator to override it"*); `deckEmptyHtml`'s three distinct branches (`test_empty_state_honesty.js:156-171`); skeleton/empty cleared **before** the first `appendChild` (`test_loading_states.js:96-112`).
**Also fix the stale copy** at shell.js:715 (*"Market Weather below…"* — the grid moved into Overwatch, weather.js:247-254).
**Verify:** deep-link to `#diagnostics` in a fresh tab; refused cards populate on arrival, not on a later tick.

### Step 7 — Merge Settings' Risk and Guardrails
**Touches:** `static/shell.html`, `static/shell.js`
One panel, one authority: `/api/trade-config` only. Delete `#guardRows` (shell.html:949-956, shell.js:3776-3790) and its **UI-invented fallbacks of 6, 2 and 4** (shell.js:3777-3781). Keep the halt-state row and the `LOCKED — see Going live` string exactly as written — `test_rules_surface.js:100-104` pins it verbatim.
**Verify:** the three caps appear once, with the engine's units, and `#riskNow` populates on a reload at `#settings` (needs step 1.3).

### Step 8 — Results: delete the stat wheel, merge Going-live into Progression
**Touches:** `static/shell.html`, `static/shell.js`, `static/ss.css`
Delete `#statTrack` markup (shell.html:712-724), `statCards()` (shell.js:3897-3953) and `renderStatWheel()` (shell.js:3955-3983). Keep the tile grids.
Move the four live-gate criteria (shell.js:4087-4119) onto the Progression rail (shell.js:3991-4054). One rail, one `MET / NOT MET` vocabulary — `EARNED / LOCKED` (shell.js:4036) goes. Settings keeps `#gateChip`, `#gateFoot` (the `build_note`) and a link to Results.
**Then fix the two contradictory explanations of the same lock**, which is a bigger inconsistency than the badge word: `livegate.py:195-197` says it is a **build** task ("no order-routing code exists in it"), while `server.py:2158-2159` and `:2165-2167` say it is **evidence-gated** ("Forward paper evidence has not yet earned live execution") — and the second is the string the chart ticket prints (chart.js:1911-1914). Pick one; my recommendation is to state **both, in that order**, because both are true: the code does not exist *and* the record has not earned it.
**Re-pin:** `test_core_hardening.py:405` if any tile id changes (it should not).
**Get an operator ruling on the wheel deletion before shipping.**

### Step 9 — Move the Bitcoin backdrop to Chart, fix stale copy
**Touches:** `static/shell.html`, `static/weather.js`, `static/chart.js`, `static/edgeview.js`
Backdrop to Chart (collapsed); `#missionLede` stays on Command. Regime uses the mapped label on the chart too (chart.js:724, 992). Fix `edgeview.js:270-272` (*"the tiles above"* on a surface with none) and delete the contradictory comment at `shell.html:1052-1057`. Fix `renderDisposition`'s and `weather.js:279-281`'s stale directional copy.
**Watch:** Chart's word ceiling is 200 (`test_word_budget.js:96`) — measure before and after.

### Step 10 — Panel-treatment normalisation
**Touches:** `static/shell.html`, `static/ss.css`
**The live bug first:** eight Results panel headers write `<div class="panel floating-head">` / `floating-body` — and **neither class exists** in ss.css, weather.css, diagnostics-ui.css, any .js or any test. Two consequences, both live: (1) the header gets `.panel` (ss.css:303-309) so every Results panel renders a bordered box nested inside a borderless floating one — the opposite of the intent; (2) `.panel.floating > .panel-head` (ss.css:341-343) and `> .panel-body` (ss.css:350) never fire, so the larger heading and the padding are dead on that surface. Every other surface uses `.panel-head` correctly (shell.html:138, 196, 219, 263, 330, 874, 892, 913, 935, 950, 962, 1005, 1010, 1022, 1032, 1040, 1099). Fix: `panel floating-head` → `panel-head` at shell.html:765, 776, 785, 787, 828, 837, 848, 849.
Then: Command drops to **two** treatments (accented bordered for Scanner, floating for the two rails); every surface uses one `.panel-head`/`.panel-body` pattern; drop `.mb-panel` (undefined).
**Consolidate the six `<details>` variants** to the three named at shell.js:2022-2023 — `.explainer`, `.issue`, `.cy-details`. The bare `<details style="border-top:…">` at shell.js:3439-3441 is the only inline-styled one; it goes first.
**Verify:** every `@media` stays at 640/900/1100/1180 (`test_responsive_layout.js:118-125`); no new fixed pixel column ≥300px without a ≤900px counterpart.

### Step 11 — Server: manual dollar aggregates
**Touches:** `app/engine/manual.py`, `app/server.py`, `app/tests/test_manual.py`
Add `pnl_usd` per settled row, `total_pnl_usd`, `n_no_risk_usd` to `manual.book()` (manual.py:1298-1299, 1318-1328); add `operator_closed_usd` to `/api/portfolio` (server.py:939-941). Decimal, `ROUND_HALF_UP`, matching server.py:925-927 exactly. **No version bump** — `book()` is a read view (justified in §2). Add a test asserting `n_no_risk_usd` is emitted and that `total_pnl_usd` excludes CANCELLED/MISSED rows (which never copy `risk_usd` forward — manual.py:1174-1180, 672-678).
**Restart the server after this change** — a running server holds the imported module.
**Verify:** `GET :8422/api/manual/book` — `total_pnl_usd` = −254.76 (−1.32 × 193) and `n_no_risk_usd` = 1 against today's store.

### Step 12 — The Ledger surface
**Touches:** `static/shell.html`, `static/shell.js`, `static/ss.css`, `tests/test_shell_structure.js`, `tests/test_word_budget.js`, `tests/test_trader_basics.js`, `tests/test_era_labels.js`, new `tests/test_ledger.py`
Add `<section class="surface" id="s-ledger">` **after** `#s-diagnostics` (never between its opening tag and `#edgeRoot` — `test_shell_structure.js:117-127`). Nav anchor with `data-s="ledger">Ledger<` and the `nav-count` span **after** the label. Key `6`. `LOADER_SURFACE` entry. Three columns + honesty banner as specified in §2.
**Non-negotiable:** all money through `window.SSFormat.money` (`test_one_source_of_truth.js:91-96`) — never a local formatter. Era nouns exactly `forward window` and `recorded book` (`test_era_labels.js:39`). A `_reads_in` field-name contract test against the live endpoints (`test_ui_field_contract.py:67-88` pattern) or the surface will render a confident zero.
**In the same commit:** `SURFACES` gains `'s-ledger'`; `CEILINGS` gains a measured `ledger` entry; `KEYS` gains `'6'` and the 1400-char window at `test_trader_basics.js:109` is re-verified; shell.js:214's `Keys: 1–5` toast is updated.
**Verify:** deep-link to `#ledger` in a fresh tab (it must fetch on arrival, not sit on a skeleton); confirm no figure anywhere adds two books; confirm the wallet band shows no number.

### Step 13 — Close-out sweep
**Touches:** tests, comments
Re-read the six fixed-window slices (§5) and confirm each still delimits what it names. Fix `test_loading_states.js:114` to `/[Nn]o setups right now/`. Update the two docstrings that describe deleted shape (`test_core_hardening.py:400-404`, `test_your_trades.js:75`). Run the byte scan. Run the full suite plus eslint. Walk all six surfaces in the browser with the rAF and `matchMedia` shims from CLAUDE.md, since the hidden preview pane never fires rAF and `go()` defers its scroll-to-panel that way.

---

## Where the audits disagreed, and my rulings

| Question | Ruling |
|---|---|
| Does `#edgeRoot` belong on Results or Diagnostics? | **Diagnostics.** shell.html carries both stories (1052-1057 vs 1066-1069); the DOM and the later "operator ruling" agree, and a previous move broke the document tree (shell.html:801-817). Fix the copy, not the location. |
| Stat wheel or tiles? | **Tiles.** Eight numbers whose purpose is mutual comparison belong side by side. This undoes recent work — get the ruling before shipping step 8. |
| Is `gradeOf` "uncalibrated" the way the removed `rank` score was? | **No.** `rank` was a 0–100 composite measured against 228 closed trades and it failed (shell.js:604-620). `gradeOf` is a deterministic two-input lookup over published fields that makes no forward claim. The defect is a **reading** defect — a bare letter reads as a ranking whatever the caption says — not a calibration one. "Calibrate it" is not an available move; deleting the letter and keeping the lattice as colour + sort is. |
| Is `ordered` ever non-empty? | **Reachable, and present in the store.** `execsim.py:429-431` counts PENDING when `confirmed_at` lands past the last stored candle; 48 VALIDATED setups exist under the current version with 3 lacking an exec fact, one of them risk-APPROVED. Whether it has *ever* rendered is unprovable because of the tie-break bug fixed in step 1.2. |
| Was the orphaned override "a genuinely new signal"? | **No.** The VALIDATED facts under v0.13–v0.17 share an identical `confirmed_at` and byte-identical bracket. Mark it certain, not likely. |
| Two escapers (`esc` at shell.js:4496 vs `escHtml` at 3624) | Out of scope for this plan, but worth one line: `esc` is the **only** escaper in the codebase that does not coerce with `String(…)`, and it is quote-blind while being interpolated into double-quoted attributes at shell.js:1712, 1737, 2102, 2382. No current payload field is likely to contain a quote, so this is a latent inconsistency, not an observed bug. Fix it opportunistically when step 3 rewrites those lines. |