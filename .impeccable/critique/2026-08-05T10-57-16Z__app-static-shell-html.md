---
target: app/static/shell.html
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-08-05T10-57-16Z
slug: app-static-shell-html
---
Method: dual-agent (A: a389fb5ea16dcb2e1 · B: aacd3433e116adc00)

Surface mode: **Operate**. Target `app/static/shell.html`, inspected live at `http://localhost:8422` at 412, 820, 1280 and 1440 px. Read-only throughout. HEAD `a52d1b0`.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Three health readouts disagree on one screen: top bar "API DEGRADED", Diagnostics "Failing now: ALL CLEAR", "Pipeline: DEGRADED". The degraded chip asserts "Nothing on this page has loaded successfully yet" while equity, deck, weather and positions are all rendered. |
| 2 | Match System / Real World | 3 | Copy is outstanding. Leaks: `NO_ELIGIBLE_PLAYBOOK` and `RR_BELOW_MINIMUM` as headings; "1W — 1 trades"; the weather lead uses "11" for three different quantities in one sentence. |
| 3 | User Control and Freedom | 3 | Escape closes everything, every write confirms, Discard and Reset-to-engine exist. The chart never re-fits after a resize; on a phone the fifth nav destination is off-screen. |
| 4 | Consistency and Standards | 2 | Every high-stakes commit is a native `window.confirm()` while the app owns a proper `role="dialog" aria-modal` pattern it uses nowhere near the money. Four `.btn-primary` visible at once on Command. |
| 5 | Error Prevention | 4 | The best thing here. The reason Arm is off sits on the control with a one-click corrective; the fling guard fires on a drag that changes risk >3x; leverage and liquidation are adjacent by design. |
| 6 | Recognition Rather Than Recall | 2 | Command shows three counts of "looked at and not taken" — disposition, tile and deck — and denominators 19 / 86 / 11 / 31 / 122 / 145 float unlinked. |
| 7 | Flexibility and Efficiency | 2 | Zero keyboard shortcuts. No `/` to search symbols, no digit keys for surfaces or timeframes. 13 tab stops from load to "Check now", 11 of them glossary terms. |
| 8 | Aesthetic and Minimalist Design | 3 | Command 1545px against a 718px stage, Diagnostics 2926px. Six co-equal panels on Command. Counterweight: the type scale is real and colour restraint mostly holds. |
| 9 | Error Recovery | 3 | "Why nothing fired" names a bottleneck and jumps to Settings. But the escalation route from a degraded state is a `<span>` with a click handler — no role, no tabindex, mouse-only. |
| 10 | Help and Documentation | 3 | 38 glossary terms at point of use, dismissible first-run, per-setting descriptions. Against that, nine load-bearing explanations reachable only by hover. |
| **Total** | | **28/40** | **Good — solid foundation, address weak areas** |

**Trend: 24 → 28 out of 40.** Consistency and Recognition are unchanged at 2; Error Prevention holds at 4.

## Design Specificity Verdict

**Product-specific in its words, generic in its visual system, and the one bridge between them is disconnected.**

The language could not have been written for anything else. The nudge row steps in `-tick / -0.1R`, this trade's own units. The Arm block says "This posts $19,903 of margin against a $10,028 account. A tighter stop sizes a smaller position" beside a button reading "Use 2x — posts $9,952". The Going-live gate ends: "Even with every criterion met, this system cannot send a real order: no order-routing code exists in it. That is a build task, not something the record earns." That is the product's constitution rendered as UI.

The costume is the default dark-terminal kit: near-black, one green accent, uppercase mono at .18em, pill chips, a scanline overlay, 4-up tiles, left rail. Share Tech Mono signals "hacker", not "sniper". Nothing in the composition references sighting, ranging, or holding fire — the brand's own idea, and the one thing a competitor could not copy.

**The mechanism meant to tie chrome to product state is dead code.** `ss.css:98-100` declares the Dynamic Accent Rule (green idle, amber paper, red live). `shell.html:14` writes `data-mode="idle"` as a literal and nothing in the repo ever changes it — one hit across all `.js`, `.py` and `.html`. The comment claiming "the primary button is amber while the book is paper" describes behaviour the app does not have.

**Deterministic scan.** CLI directory scan: **5 findings** (side-tab 3, overused-font 1, em-dash-overuse 1 advisory). Scope `type`: 1. Scope `layout`: **0**. Scope `color` is not a valid scope — only `type` and `layout` exist.

Browser measurements:

- **Type scale holds.** Distribution clusters on 11 / 12.5 / 14 / 16 / 20 / 26 / 32 and nowhere else. `ss.css` has one remaining px font-size; `weather.css` and `diagnostics-ui.css` have zero. Three elements break the 11px floor — `span.ev-tf-ticklab` at 9.5px on Diagnostics.
- **Contrast: 0 failures.** 175/175 elements resolved on Command, 73/73 on Chart, range 6.50:1 to 17.75:1. Focus ring 15.88:1 against a 3:1 requirement.
- **Focus: 18/18 real tab stops match `:focus-visible`**, all `solid 2px rgb(0,255,170)` at 2px offset (`.term` gets 1px).
- **ARIA state correct throughout.** `#tkDir`, `#cTfs` and all nine `#cLayersPop` toggles carry `aria-pressed` with exactly the right one true; the rail carries a single `aria-current="page"`.

**Where the two assessments disagreed, and who was right.**

- A counted **31** hover-only explanations. B resolved it to **9**: thirty of those are glossary terms that also carry `role="button"`, `tabindex="0"` and a matching `aria-description`, so they are keyboard- and screen-reader-reachable. B is right; the real number is 9.
- A reported the chart clipped and frozen at every width. B **retracted the same finding** after proving `requestAnimationFrame` fired 0 times in 1200ms and a fresh `ResizeObserver` never delivered its initial observation in 1500ms — the pane is not compositing, so the chart's sizing lifecycle cannot run at all here. **Chart responsive behaviour is untested, not passing.** Neither agent could measure it; it needs a visible browser.
- A counted 11 elements under the 11px floor from source; B measured 3 in the computed DOM. Both are partly right — the others are SVG `font-size` attributes in JS-written markup, which are real but live in SVG user units the CSS scale cannot reach.

**Method note worth keeping.** B's first contrast pass reported a false clean from only 31 of 175 elements: **144 of the text colours on Command are `oklch()`**, which a standard rgb/hex regex silently drops. Any contrast tooling pointed at this codebase must handle `oklch` or it will report a pass it did not earn.

**Tooling finding, still true.** Scanning `shell.html` alone reports exit 0 and one advisory — a false all-clear that misses all four CSS findings. `css-cascade.mjs:958` resolves the stylesheet with `path.resolve(fileDir, href)`, and `href="/static/ss.css"` becomes `C:\static\ss.css`, which throws into a bare catch. **Always scan the directory.**

**Visual overlays.** None available. Screenshots fail with "the Browser pane is not displayed, so the page is not compositing frames." All evidence is JavaScript evaluation.

## Overall Impression

Four points better, and the gains are where the work went: the type scale is real and in rem, contrast is clean at 175/175, focus is a zero-specificity floor that 18 of 18 tab stops honour, and ARIA state is correct everywhere it was missing. Those are settled.

What is left is a different class of problem. The remaining defects are not oversights — they are places where the product's own good pattern exists and is not being used. There is a designed modal, and the trade confirmation is a `window.confirm()`. There is a Dynamic Accent Rule, and nothing writes `data-mode`. There is a `.t-note` pattern for putting a reason on a control, used once, while nine explanations sit in `title` attributes on a surface that now ships a phone manifest. The biggest opportunity is no longer adding anything; it is finishing what is already half-applied.

## What's Working

**1. The blocked-Arm pattern.** `#tkBlock` names the constraint in dollars, names the consequence, and offers the specific correction as one click — and is kept separate from `#tkWarn`, `#tkDup` and `#tkFling` so four writers can never overwrite each other. Better error prevention than most funded trading products ship.

**2. The type scale is real, and it is rem.** Every visible size across five surfaces lands on seven steps and nowhere else. One px font-size left in `ss.css`, zero in the other two stylesheets. A reader who enlarges their browser default now gets it.

**3. Reconciling two books instead of hiding the disagreement.** Results says 8 trades, Diagnostics says 320, and both carry the same sentence explaining why, stated before the numbers rather than under them. The instinct in most products is to pick one and suppress the other.

## Priority Issues

### [P1] The disposition line under-reports for the first 30 seconds after load

**Verified live, with the mechanism pinned.** Immediately after a reload: disposition reads "Nothing to take right now."; `#mSetupsSub` 40px below reads "3 examined, not taken"; the deck reads "The engine looked at 122 chances". One poll later the same line reads "Nothing to take right now. **3 were examined and refused.**" — it heals itself.

Cause: `renderDisposition()` at `shell.js:723` reads `deckSplit(lastDeckArgs ? lastDeckArgs[0] : [])`, and `lastDeckArgs` is only set by `renderDeck()`, which the overview handler calls *after* it calls `renderDisposition()`. On first paint the split is empty, so `refused` is 0 and the clause is omitted. Every later cycle is correct.

**Why it matters.** It is wrong during exactly one of the three session shapes PRODUCT.md names — the twenty-second check — and right for the other two. The comment at `shell.html:81-95` claims this class of disagreement was designed out; it was, for steady state, and not for first paint.

**Fix.** Have `renderDisposition()` read the same memoised split the tile uses rather than a nullable module variable, or call it after `renderDeck()` in the overview handler. One-line ordering change; the authority is already shared.

**Suggested command:** `/impeccable harden`

### [P1] Four tables on Results are clipped with no way to reach the content

At 412px, six `table.data-table` render at 473px inside a 345px box. Two are fine — inside `#perfSymbol` and `#perfStrategy`, which have `overflow-x:auto` and genuinely scroll. The other four are direct children of `<details>` with `overflow-x:visible`, inside a `.panel` with `overflow:hidden`. No scrollbar, no pan, 90px of every row simply unreachable. Command, Chart, Settings and Diagnostics have zero non-chart overflow at 412, 820 and 1440.

**Fix.** Give the four `<details>` the same `overflow-x:auto` wrapper the two working panels already use. The pattern exists in the file; it was applied to two of six.

**Suggested command:** `/impeccable adapt`

### [P1] Nine load-bearing explanations are reachable only by hover

Not 31 — B resolved the glossary terms as genuinely reachable. The nine that are not, all on Command: `#tkLiq` (232 chars, no role, not focusable), the Exchanges DPAPI chip (**211** — the entire security guarantee, read by someone about to paste an API key), the risk-is-not-editable chip (180), `#cRegime` (177), `#healthChip` (143), `#guardChip` (120), `#cPrice` (106), and two more.

**Why it matters.** The app now ships `manifest.webmanifest` with `display:standalone` and phone icons — it is explicitly a touch target, where none of these exist. `shell.html:391-396` already fixed exactly this for `#tkDirWhy`, with a comment saying "the reason was written into the button's title, which a mouse reveals and a finger cannot." The lesson was learned in one place and not applied to the other nine.

**Fix.** Promote them to visible text with the `.t-note` pattern already in the file. Rule: `title` may only duplicate visible text, never carry it.

**Suggested command:** `/impeccable clarify`

### [P2] Every high-stakes commit is a native `window.confirm()`

`chart.js:2067` (Arm), `shell.js:1832` (Close), `1516` (Cancel), `2793` (Halt), `2768` (Apply), plus `alert()` for the new baseline. The content is excellent — direction, symbol, entry with distance from market, stop with percentage, risk, leverage, the scale-out rung, and "PAPER — this writes to your paper book." The container is a browser dialog: system font, plain `\n`, no emphasis available on the number that matters, and on some mobile platforms a truncated body, which would cut the fling warning `chart.js:2059` deliberately puts last so it cannot be scrolled past.

The app already owns the right pattern — `wizard.js:421` is a `role="dialog" aria-modal` modal, `tracer.js:75` a drawer. Using neither at the money is the largest consistency break on the surface.

**Fix.** One `confirmDialog()` on the existing `.dx-modal` shell, promise-returning, focus-trapped, with the deciding number in `.t-metric`. Migrate all five call sites.

**Suggested command:** `/impeccable harden`

### [P2] The alarm colour is spent on noise; the mode accent is spent on nothing

`chart.js:955` sets the price chip green or red with no dead band. Measured live: BTCUSDT at **-0.02%** — functionally flat — paints the whole chip red on the surface where the decision is committed. Red is the loudest thing in this palette and the app has real red states (HALT, a bad orb, a blocked audit). Spending it on a 0.02% tick trains the operator to filter red out.

Meanwhile `[data-mode]` never fires, so the one rule that would make colour carry product state is inert. And the cyan reported as removed survives in `ss.css:43` (token), `ss.css:768` (`.lvl-entry`, the entry price line) and four hard-coded `#22d3ee` in `chart.js`.

**Fix.** Give the price chip a neutral band below ±0.25%. Either wire `data-mode` to real state or delete the rules and the comment claiming they work. Decide cyan deliberately — entry/TP/SL do need three separable hues, so either record it as a chart-semantics exception or move entry to `--accent`.

**Suggested command:** `/impeccable colorize`

## Persona Red Flags

**Alex (power user).** Zero keyboard shortcuts exist. No `/` for the symbol search that is already `type="search"`, no digit keys for surfaces despite hash routing, no `[`/`]` for timeframe. 13 tab stops from load to "Check now", 11 of them glossary terms he learned two years ago. Credit where due: the two books are handled well — "Your trades" carries `hand-picked · not engine record` and the budget aside names what the meters exclude. That is his hardest edge case and it is right.

**Sam (accessibility-dependent).** The escalation route from a failure is mouse-only: `shell.js:284` binds `click` to a `<span>` with no role and no tabindex, so when the app degrades the affordance that reaches Diagnostics is invisible to keyboard and screen reader. `.term` is `role="button"` with no `aria-haspopup`/`aria-expanded`, so 38 of them announce as "button" with no indication a definition opens. Five Settings checkboxes render 15x15 against the 24px floor; `#devToggle` is 14px tall on every surface. Against that, and verified: skip link, `aria-current`, three `aria-live` regions, `<label for>` on every input, real `<table>` with `scope`, a global reduced-motion reset, and zero contrast failures across 248 measured elements.

**The briefed-but-new reader.** Meets three health verdicts in thirty seconds — "API DEGRADED", "ALL CLEAR", "DEGRADED" — with no way to know which is authoritative. Meets `served clean 0 · flagged 99 · held back 0 · switched off 0 · halted 0`: five undefined nouns, no units. Meets `NO_ELIGIBLE_PLAYBOOK` as a heading, with excellent plain English underneath that the eye reaches second. Meets "11 of 19 tradeable symbols… 11 more are shadow… and 11 of those are live" — three different elevens in one sentence. And `shell.html:915` still carries `<!-- ─── LEARN ─── -->` as an empty stub: PRODUCT.md names LEARN and the glossary as this audience's on-ramp; the glossary shipped, the surface did not.

## Minor Observations

- `shell.js:2043/2054/2071` write equity-curve axis labels at `font-size="10"` and `"9.5"` in SVG user units, so the rem migration's benefit does not reach the axis of the only chart on Results. `ss.css:1581` sets `.c-ohlc{font-size:10px}` inside the ≤640px query — the primary numeric readout on a phone chart.
- `shell.js` writes `style="font-size:13px"` inline at 1087 and 1715, and 11px at 2850.
- "1W — 1 trades" on the Diagnostics timeframe breakdown.
- "Forward Record" is a full bordered panel holding one line. Credit: its `14 rejected` is a `.num-link` that jumps to the funnel — a pattern that deserves wider use.
- `.wx-row` rows are `role="button"` with no `aria-label`, so the accessible name is the whole concatenated row.
- `#tkWarn` carries a fuller explanation than `#tkBlock` and is hidden while `#tkBlock` shows — the better sentence is the one not being shown.
- No service worker registered and no `apple-touch-icon`, so an iOS home-screen icon falls back to a screenshot, and `display:standalone` with no offline handling shows a raw browser error if the watchdog is down.
- `#scanChip` still shows its literal initial `SCANNER —` after reload while the status bar already reads "WATCHING THE MARKET".
- `#tkDir` and `#cTfs` are bare `div.seg` with no `role="group"` and no accessible name; `<nav>` has no `aria-label`.

## Questions to Consider

1. **If `data-mode` never changes, what is the accent for?** Wire it to armed/live state and let the shell go amber when an order is resting — the most product-specific thing that could happen on this screen — or delete the rules. A design system documenting behaviour it does not have is worse than one documenting less.
2. **Command leads with a one-line answer. Why doesn't Results?** It asks "Is this actually working?" and replies with eight co-equal tiles. The pattern exists and works: *"Not yet — 8 trades, average -0.01R, and the interval still crosses zero."*
3. **What would "sniper" look like if it were structural rather than atmospheric?** Range it, wait, take one shot, account for it — that is exactly the funnel: 145 candidates, 23 validated, 9 sized, 8 closed. The product's own data has the brand's shape in it and the chrome is looking elsewhere.
4. **There is a designed modal and a designed drawer, and neither confirms a trade. What is the modal for, if not for this?**
