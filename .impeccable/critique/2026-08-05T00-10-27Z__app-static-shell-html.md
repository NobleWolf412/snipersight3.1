---
target: app/static/shell.html
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-08-05T00-10-27Z
slug: app-static-shell-html
---
Method: dual-agent (A: acef66d7f71d24ee4 · B: a2f09bb8dc0ec51a3)

Surface mode: **Operate**. Target resolved to `app/static/shell.html`, inspected live at `http://localhost:8422` at 1440×900, 780×820 and 510×1020. Read-only throughout — 320 requests, all GET; `git status` empty before and after.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Excellent instrumentation (scan-phase chip, freshness dot, budget ceilings, space-holding skeletons) — but Settings and Diagnostics render an empty stage, and Results ends in two skeletons that shimmer forever. Status lies at the two worst moments. |
| 2 | Match System / Real World | 4 | Exemplary. Surface-as-question IA; "stopped out Aug 3 · held under an hour · risked $197"; "hit target — too close to pay"; engine codes translated to "no strategy covers that market condition". |
| 3 | User Control and Freedom | 2 | HALT persistent everywhere, Reset-to-engine, Discard, Default. But 2 of 5 destinations dead-end with no message and no recovery. |
| 4 | Consistency and Standards | 2 | Internal visual language very consistent; standards are not. `aria-pressed` on `#tkTabs` but absent on `#tkDir`, `#cTfs` and all 9 Layers toggles; no `aria-current` on the rail; `ss.css:56-66` declares a four-step breakpoint scale then uses seven. |
| 5 | Error Prevention | 3 | Arm disabled with the reason *on* the control plus a fix button; "Arm (paper)" names the book; read-only risk with rationale. Deduction: Chart cold-opens in a self-inflicted breach the operator never composed. |
| 6 | Recognition Rather Than Recall | 2 | 46 inline glossary terms is a real asset. But number-key shortcuts 1–5 have zero UI hint, and every cross-surface pointer demands recall *and* is broken. |
| 7 | Flexibility and Efficiency | 2 | Shortcuts, CSV export, symbol search, lazy layers, per-trade risk override. Undermined by undiscoverable shortcuts (2 landing on blank screens), no density control, total collapse below ~900px. |
| 8 | Aesthetic and Minimalist Design | 3 | Disciplined: olive-tinted near-black (never `#000`), accent reassigned by `[data-mode]`. But 348 elements below the 11px floor is not minimalism — it is uniform density, where everything shouts in the same small voice. |
| 9 | Error Recovery | 1 | Weakest by far. The blank-surface failure produces no message, no error, no route back. Orphan skeletons have no timeout and no failure state. The `.toast-bad` machinery exists; the failures that actually occur never reach it. |
| 10 | Help and Documentation | 3 | 46 point-of-use definitions, "Start here" first-run, gate criteria as progress bars, "Why nothing fired". Deduction: the LEARN surface PRODUCT.md names exists only as a bare comment at `shell.html:825`. |
| **Total** | | **24/40** | **Acceptable — significant improvements needed** |

## Design Specificity Verdict

**LLM assessment.** The specificity lives in the language, the state semantics, and the mid-level components, and there it is genuinely authored. No other dashboard ships a Setup Deck whose empty state reads "the engine looked at 102 chances in this window and passed on every one" followed by a ranked reason census, or a `.deck-divider` labelled "LOOKED AT, NOT TAKEN" that dims a persuasive rationale to `--fg-4` precisely so a refused setup cannot read as advice (`ss.css:777-788`). `.pos-track` reasons at the level of the data model: it refuses a red→green gradient over stop→target space because a 3:1 trade's entry sits at 25% by construction and would always paint "in the red" (`ss.css:866-871`). Amber means "your money is on this" and nothing else, and four independently-owned modules agree on it without a shared component.

The frame around all of that is stock. A 56px topbar, 186px left rail, status bar, and a `.grid.cols-4` KPI tile row as the first thing on the primary surface — the default admin-console skeleton, with the most interchangeable component in the product occupying the most valuable real estate. More pointedly: the brand commitment is *sniper/tactical*, and what shipped is generic *terminal-cyber* — uppercase mono tracking, scanlines at .35 opacity, corner brackets, green-on-near-black. A SOC dashboard would wear that costume unchanged. The one genuinely sniper-shaped idea the product owns — the discipline of not taking the shot — is a grey empty-state paragraph two-thirds down a 2.61-screen scroll.

**Verdict: authored-for-this-product in its copy, states and data objects; category-interchangeable in its shell, chrome and hero composition.** The identity is in the sentences, not the layout.

**Deterministic scan.** 479 findings across 423 elements in the browser pass. Largest groups: `undersized-ui-text` 348, `ai-color-palette` 67, `tiny-text` 19, `all-caps-body` 13, `dark-glow` 10, `wide-tracking` 8, `layout-transition` 7. CLI directory scan of `app/static` returned 11 findings: `side-tab` ×5, `layout-transition` ×4, `overused-font` ×1, `em-dash-overuse` ×1 (advisory).

Two detector results the design review did not reach:

- **`ai-color-palette` ×67.** Cyan gradient backgrounds on `#btnCopilot`, `#firstRun` and the three `Save <venue>` buttons; cyan neon text on *every* `h1.t-page`, `#cTfs > button.on`, `#resultsEra > a`. `docs/REDESIGN-PLAN.md` §1 named "cyan-on-black with glow" as the off-brand look the redesign existed to remove. It is still the page-title colour on every surface.
- **`layout-transition` ×7.** `transition: width` on `.budget-bar > i`, `.gate-bar > i`, and three more. Animating a layout property forces layout on every frame, and it is a named prohibition in the shared design laws.

**False positives, correctly identified by the detector pass itself:**

- `monotonous-spacing` ("~4px used 468/474 times, 99%") is self-contamination. The rule reads only `<style>` blocks and inline `style` attributes, never the external stylesheet — and 429 of the 479 inline spacing declarations at scan time belonged to the detector's own injected overlay nodes, 422 of them `3px`. `ss.css:52` defines a real six-step scale the rule never sees. The finding measures the tool, not the app.
- `side-tab` at `diagnostics-ui.css:16` matched prose inside a comment that *prohibits* side-stripe borders. The genuine instances are `ss.css:296` and `diagnostics-ui.css:434`.

**Visual overlays.** No user-visible overlay is available. Injection succeeded and the detector executed, but 422 of 423 overlay nodes were `display:none`, and screenshots failed with "the Browser pane is not displayed". All evidence above is console and programmatic-API output.

**Tooling finding worth acting on.** Scanning `shell.html` alone reads *no CSS at all* and reports 1 advisory finding — a false all-clear. `shell.html:8` links `href="/static/ss.css?v=20"`, and the static-HTML engine resolves it with `path.resolve(fileDir, href)`, which turns a web-root-absolute path into `C:\static\ss.css`. The read throws and is swallowed by a bare `catch` with no warning. Scan the directory, not the file.

## Overall Impression

This is a well-designed product with a broken frame. The copy, the state semantics and the refusal-rendering are better than most shipped trading software — genuinely principled work where the stylesheet enforces the product's honesty commitments rather than merely decorating them. And two of its five surfaces have been rendering blank.

The single biggest opportunity is not visual. It is that the design's own connective tissue — every "see Settings", every "full book in Diagnostics", the bootstrap confidence interval that PRODUCT.md positions as the core honesty mechanism — points at surfaces that do not render. Fix the frame and a large amount of already-authored quality comes back online for free.

## What's Working

**1. Refusals are first-class content, in CSS as well as copy.** `#deck`'s empty state, the "LOOKED AT, NOT TAKEN" divider, `.deck-row.dead{opacity:.55}` and `.deck-row.dead .deck-why{color:var(--fg-4)}` (`ss.css:777-788`). A persuasive rationale attached to a setup the risk authority refused is the most dangerous thing this deck can render, and the stylesheet demotes it deliberately. The product principle is enforced by the cascade, not by review.

**2. One semantic colour, four independently-owned surfaces.** Amber means "your money is on this" across `.deck-row.held`, `.ticket.managing`, `.tk-open` and `.tkm-dot` — four modules with separate mount points agreeing on one state without a shared component, so the deck and the chart tell the same story before either is read.

**3. The accessibility annotations are true.** Converting the OKLCH tokens to sRGB: `--fg-3` on `--bg` measures 7.60:1 against a claimed 7.0; `--fg-4` on `--card` measures 4.80:1 against a claimed 4.8. Every body ramp clears AA on every ground it is drawn on, and the visual contrast analysis returned zero findings. Comments in this codebase that claim a measurement are honest.

## Priority Issues

### [P0] Unbalanced markup closes `.shell` early — Settings and Diagnostics render blank

**Why it matters.** Dead: 2 of 5 nav destinations, number-key shortcuts 4 and 5, the permanent "Sim only — no live orders" safety statement, the Developer mode toggle, `#edgeRoot`, Decision Provenance, and the entire Settings surface including Going-live criteria and Guardrails. Also broken: every in-product cross-reference the design deliberately built. `#s-settings` sits at `top:1470px` inside `body{overflow:hidden}` and cannot be reached by any input.

**Evidence.** Counting the served page, there is a net of one more `</div>` than `<div>` before `#s-settings`; `#s-settings`, `#s-diagnostics` and `footer.statusbar` parse as direct children of `<body>` rather than `.shell`. The site is `shell.html:570-573`: two orphaned `.skel skel-line` divs and their closers, left behind by the edge-panel move the comment at 561-568 describes — `#edgeRoot` actually lives at line 787, inside Diagnostics, not in Results where that comment places it.

**Fix.** Repair the block at 570-573, then assert *parsed DOM shape* rather than file text: `document.querySelector('.shell').children.length` and `footer.statusbar`'s `parentElement`. Note the comment at `shell.html:792-795` records a previous instance of this exact failure — "when two closing divs went missing here" — so this is a recurrence, not a first offence. The JS suites assert against the text of static files, which is precisely why it shipped.

**Suggested command:** `/impeccable harden`

### [P1] Focus indicators removed from the three controls that define a trade

**Why it matters.** `.fld input:focus{outline:0;border-color:var(--accent)}` (`ss.css:669`) governs `#tkEntry`, `#tkTp` and `#tkSl`. A 1px border-colour change is the only focus indicator on the fields that set entry, target and stop. Three more removals at 1076, 1163, 1294. Across all three stylesheets there are 16 focus rules and none covers `.btn`, `.nav a`, `.seg button`, `.sym-row` or the 9 `.layers-pop` buttons. Compounding: `#tkDir` (Long/Short — the most consequential state in the ticket) has no `aria-pressed`, the rail has no `aria-current`, 46 `.term` spans carry `role="button"` for a non-action, and CLOSE on a live position renders 55×19px against WCAG 2.2 AA 2.5.8's 24×24 minimum. This is the money path.

**Fix.** Replace every `outline:0` focus rule with `outline:2px solid var(--accent); outline-offset:2px`. Add one `:where(.btn,.nav a,.seg button,.sym-row,.layers-pop button):focus-visible` rule. Add `aria-pressed` to `#tkDir`/`#cTfs`/Layers, `aria-current="page"` to the active rail link. Drop `role="button"` from `.term`, keep `tabindex="0"`, and back the definition with `aria-describedby` — `aria-description` (45 uses) is ARIA 1.3 draft with incomplete AT support and may never be announced.

**Suggested command:** `/impeccable audit`

### [P1] 348 elements below the 11px floor, and browser text preference is inert

**Why it matters.** Measured distribution: 10px ×293, 9px ×47, 9.5px ×30, 10.5px ×6. 121 visible elements sit at ≤10px uppercase with .18em tracking, which destroys word shape at exactly the sizes that most need it — including table headers, every form label in Settings, and button labels like "Test connection" and "Save coinbase spot". Typography is 128 px-based `font-size` declarations against 2 `rem` occurrences (neither a font-size), so a reader who raises their browser text size gets nothing. `all-caps-body` found uppercase runs of 61, 103, 165 and 720 characters. Given PRODUCT.md's confirmed "others later" audience, this is the single biggest barrier to a newcomer reading the interface at all.

**Fix.** Move `font-size` to `rem` throughout so browser preference works. Raise the 9/9.5px tier to a minimum of 11px, and reserve uppercase-plus-tracking for short labels only — nothing above ~30 characters.

**Suggested command:** `/impeccable typeset`

### [P2] No responsive story below ~900px; the chart collapses to 2px

**Why it matters.** `.shell{grid-template-columns:186px 1fr}` (`ss.css:362`) has no media query at any width. Measured at 510px: the rail is still 186px (36% of screen), `.stage` is 194px, `#chartPane` is **2px wide**, and the stage overflows horizontally. At 780px, `#chartPane` is 256px while its own ticket is 268px — on the chart surface, the chart is the narrower column. Operate mode is judged against the real usage scene, and a half-screen split beside a terminal is a normal way to run a local tool. Separately, `ss.css:56-66` documents a four-step scale (640/900/1100/1180) and instructs "use one of these four"; the three queries three lines below use 1020/780/680, none of which is on it.

**Fix.** `@media(max-width:900px){.shell{grid-template-columns:1fr} .nav{flex-direction:row;overflow-x:auto} .chart-main{grid-template-columns:1fr}}`, and give `.chart-main` a `minmax(320px,1fr)` chart track so the chart can never be narrower than its ticket. Reconcile the breakpoints onto the declared scale or amend the comment.

**Suggested command:** `/impeccable adapt`

### [P2] Command answers its own question with seven co-equal panels, and contradicts itself above the fold

**Why it matters.** The surface asks "What should I do right now?" and presents Start here, Scanner + 4 tiles, Risk budget, Open trades, Setup Deck and Market Weather as visually equal panels across 2133px against an 818px stage — 2.61 screens. Nothing is the answer. Worse, the headline tile reads "ACTIVE SETUPS 3" while the Setup Deck directly beneath reads "no setups right now". The 3 counts the "LOOKED AT, NOT TAKEN" rows, which is defensible against the glossary and indefensible on one screen. Cognitive load fails 6 of 8 checks, with nine decision points carrying more than four visible options. All three declared session shapes fail here: the 20-second check has no single disposition to read, the long session has no anchor, and the newcomer's first impression is a metric contradicting the panel below it.

**Fix.** Promote one disposition block above the fold that states the answer in a sentence — "Nothing to take: 2 of 2 slots full, open-risk budget spent. 3 setups were examined and refused." Demote Market Weather and Start-here beneath it. Then either rename the tile or make the deck headline agree with the count; one of the two words has to move.

**Suggested command:** `/impeccable layout`

## Persona Red Flags

**Alex (power user).** Number-key shortcuts 1–5 exist in `shell.js:119-129` with zero discoverability — no hint, no legend, no `title` — and shortcuts 4 and 5 land on blank surfaces. No density control on a surface that scrolls 2.61 screens; no way to collapse or reorder Command's seven panels. `#cLayersPop` presents 9 toggles with no keyboard model and no `aria-pressed`, and on the default symbol 6 of the 9 read "— no data", so the menu costs nine reads to learn that three are live. Export exists only for the journal. `.commit-bar` reflows between 132px and 183px, resizing the chart under him whenever the block reason changes.

**Sam (accessibility-dependent).** Focus ring removed from the entry/target/stop fields and three other inputs; no `:focus-visible` rule for buttons, nav links, segmented controls or list rows. 46 `.term` spans announce as "button" for a non-action, adding 46 false actionable stops. 75 elements carry a `title` longer than 60 characters — including `#btnAuto` at 148 and the read-only-risk explanation at 211 — which is neither touch- nor keyboard-reachable, and is the exact pattern `shell.html:113-115` argues against. `#tkDir` has no `aria-pressed`; the rail has no `aria-current`; CLOSE is 55×19px. Contrast, uniquely, is fine.

**The briefed-but-new reader (project-specific, from PRODUCT.md's confirmed "others later" audience).** Every on-ramp the design built for this exact persona terminates in an empty screen: "Start here" step 3 points to Settings → Going live (blank); `#btnAuto` points to Settings (blank); the Results era band points to Diagnostics (blank); `#healthChip`'s DEGRADED route points to Diagnostics (blank). The LEARN surface PRODUCT.md names as this audience's on-ramp does not exist — `shell.html:825` is a bare comment. The 40-term glossary survived; its host surface did not. And the first thing this reader meets is "ACTIVE SETUPS 3" above "no setups right now". The terminology-explains-itself principle is honoured beautifully at term level and broken at surface level.

## Minor Observations

- `.t-section` panel headings render at `--fg-3` while the `.chip` beside them is `--fg-2` — every panel's metadata is brighter than its own title.
- 10 `.t-section::before` dots pulse simultaneously on Command, on the same 2.8s keyframe that `.tkm-dot` and `.cp-msg.busy` reuse — so "this is a heading" and "this is loading" pulse identically.
- `dark-glow` ×10: zero-offset chromatic halos on `#modeChip`'s orb, `#healthOrb`, `#scanOrb`, plus a `#00ffaa` zero-offset text-shadow on a deck cell.
- `#scanChip{width:196px}` and `#clock{width:8ch}` are excellent anti-shift work; the layout-stability discipline is unusually thorough and worth preserving through any redesign.
- `.era-band` deliberately breaks the mono-chrome house rule for body prose with a reasoned comment (`ss.css:163-167`). It is the right call, and the app would be more readable with more of it.
- `#cLayersBtn` reporting "Layers 3/9" is honest; it would cost less if the 6 empty layers were grouped rather than listed.
- `line-length`: `#rSample` runs ~91 characters per line against a <80 target.
- The comment blocks in `shell.html` and `ss.css` are the best design-rationale record I have seen in a shipped stylesheet — and they are load-bearing documentation living somewhere no future reader is required to look.

## Questions to Consider

1. Two of five surfaces have been rendering blank, and nothing in the test suite noticed, because the JS suites assert against the *text of static files* rather than a parsed DOM — a limitation `CLAUDE.md` documents as a known convention. What else does the suite currently certify that the browser does not do?
2. The brand commitment is *sniper*. What shipped is *terminal*. A sniper's discipline is not taking the shot, and this product's most distinctive true fact is "102 chances, passed on every one." Why is that a grey empty-state paragraph instead of the hero of the Command surface?
3. `docs/REDESIGN-PLAN.md` named cyan-on-black-with-glow as the off-brand look it existed to remove. The detector finds cyan neon on every page title and gradient cyan on five buttons. Was the redesign's colour verdict ever actually executed, or only written down?
4. Seventy-five `title` attributes carry more than 60 characters of explanation. The codebase argues against this pattern in its own comments and then uses it 75 times. If the reasoning is worth writing, why is it in the one place invisible to touch, keyboard and screen reader alike?
5. Command shows "Active setups 3" above "no setups right now". Both are true under different definitions of *setup*. Which definition is the product's, and what happens to the other word?
