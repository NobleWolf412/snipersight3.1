---
target: app/static/shell.html
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-08-06T00-03-42Z
slug: app-static-shell-html
---
Method: dual-agent (A: a938a12a409471703 · B: a559b612fec7a97f7)

Surface mode: **Operate**. Target `app/static/shell.html`, inspected live at `http://localhost:8422` at 412, 820, 1280 and 1440. Read-only: no POST/PUT/DELETE. HEAD `9c4eb1c`.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | `#healthChip` reading DEGRADED is `display:none` at ≤900px, because the escape hatch fires only on the fetch-failure path and not on the pipeline audit's own verdict. |
| 2 | Match System / Real World | 3 | Best-in-class reason dictionary, undermined by "5 were examined and refused" sitting 400px above "looked at 144 chances" with no scoping word on either. |
| 3 | User Control and Freedom | 3 | The skip link navigates you off whatever surface you were on and leaves focus on `<body>`. |
| 4 | Consistency and Standards | 3 | Real token system, one focus floor, one dialog language. But Settings' Risk and Guardrails restate four identical constants under different labels, and Results does not use the disposition pattern Command established. |
| 5 | Error Prevention | 4 | `#tkBlock` disables Arm, names the cause and offers the fix on the control; `#tkFling` catches a mis-drag; `SSConfirm` restates the terms, focuses Cancel, traps Tab, refuses to stack. |
| 6 | Recognition Rather Than Recall | 2 | The risk budget that explains a refusal is ~1,400px above the refusal citing it. |
| 7 | Flexibility and Efficiency | 3 | 1–5 switch surfaces, `c` opens the copilot, `?` prints a key list, the picker takes arrow keys. But `?` has no discovery affordance anywhere, and the 85 picker rows are all tabbable. |
| 8 | Aesthetic and Minimalist Design | 2 | In `data-mode="paper"` — the resting state whenever anything is open — Command measures **169 amber-tinted elements to 24 green**. |
| 9 | Error Recovery | 4 | "Why nothing fired" names the stage, count, plain reason and links to Settings. `#tkBlock` refuses and remedies. |
| 10 | Help and Documentation | 3 | Glossary at point of use with Enter/Space. But the LEARN surface PRODUCT.md lists as current is an empty marker at `shell.html:966` with no nav entry. |
| **Total** | | **30/40** | **Good** |

**Trend: 24 → 28 → 32 → 30.** The first drop. Two axes fell: Recognition 3→2 and Match 4→3, and Aesthetic stayed at 2 for a new reason. Nothing regressed in the code; a different reviewer weighted volume and colour harder, and one large defect surfaced that three previous runs had missed.

## Design Specificity Verdict

**The words are unmistakably this product; the shapes are interchangeable. Specificity is near 100% in language and near 0% in form.**

The Setup Deck's *empty* state is authored prose: "The engine looked at 144 chances in this window and passed on every one — 102 no strategy covers that market condition, 42 the target was not far enough away to justify the stop." The symbol picker groups 85 pairs into SCANNED / SHADOW — NEVER SIZED / NOT SCANNED with venue and leverage per row: venue-derived-from-symbol expressed as information architecture rather than asserted in a footnote.

The chassis is not specific at all. Five uppercase mono words in a left rail, a chip row, a 4-tile grid, a status bar, panels inside panels. Nothing in the *form* says sniper; the binding identity is carried by a logo PNG and a green that, as shipped, is almost never on screen.

**Deterministic scan.** 5 findings, unchanged across all four runs: `side-tab` ×3, `overused-font` ×1, `em-dash-overuse` ×1 (advisory). Scope `type`: 1. Scope `layout`: **0**.

Two tooling findings, both new this run:

- The single-file false all-clear is confirmed again, with a caveat that matters: the directory scan only catches the CSS items by scanning `ss.css` as a standalone regex target. `shell.html`'s *element-level cascade still resolves to zero CSS*, which is why `--scope layout` returns 0 rather than any real layout verdict.
- **URL mode fails silently.** `detect.mjs --json http://localhost:8422/` writes "puppeteer is required" to stderr but emits `[]` on stdout and **exits 0**. Anything consuming the JSON reads a clean pass.

## The finding three previous runs missed

**161 visible text elements are below AA, and every one is caused by an ancestor `opacity` rather than a colour choice.** B verified this by re-measuring each failure with ancestor opacities forced to 1: all 161 pass.

| selector | opacity source | measured | if opaque | n |
|---|---|---|---|---|
| `.t-label`, `.deck-why`, `.term`, `summary` | `.deck-row.dead` @ 0.55 | **2.59** | 5.82 | ~94 |
| `.chip-red` ("NOT TRADED") | `.deck-row.dead` @ 0.55 | **2.65** | 5.97 | 8 |
| the refusal sentence | `.deck-row.dead` @ 0.55 | **2.82** | — | 5 |
| entry / tp / sl prices | `.deck-row.dead` @ 0.55 | **3.10** | — | 25 |
| "Ask copilot", "Open chart" | `.deck-row.dead` @ 0.55 | **3.51** | — | 10 |
| `#equityRet` (−3.81%) | own `opacity:0.7` | **4.09** | 6.98 | 1 |

"Looked at, not taken" is the only place the product writes **why** the engine refused a setup — the mechanism its entire positioning rests on — and it is the least readable text in the app. The `ss.css` header records lifting `--fg-3`/`--fg-4` "until the DIMMEST step clears 4.5:1 on the darkest surface it is ever drawn on". An opacity multiplier applied downstream silently undoes that whole exercise.

This is worth stating plainly: **the first critique in this series praised that exact rule as a strength** — "the stylesheet demotes it deliberately rather than incidentally". It does. It also puts the product's core claim below the legibility floor, and no contrast pass caught it for three runs because every previous resolver measured colour without compositing ancestor opacity.

Three previous runs reported "0 contrast failures". Those numbers were wrong, not because the tool lied about colour but because nobody multiplied by 0.55.

## Where the two assessments disagreed

**A reported a P1 that B disproved.** A measured the ticket clipped at 1280×720 — stop-loss field and nudge row past the bottom edge, `.commit-bar` growing to 136px and stealing height. B measured `.ticket` clientHeight **413** = scrollHeight **413**, the stop field's bottom at **345**, inside the box, and `.commit-bar` at **52px** and a *sibling* of `.ticket`, not a child. Nothing is clipped. The four `.fld` elements measuring 0×0 are `display:none` collapsed panes.

**B also invalidated a measurement method.** `resize_window` is a no-op in this pane — it reports success while `innerWidth` stays 1920 and media queries never flip. B got real viewport control with same-origin iframes, verified by `matchMedia('(max-width:900px)')` flipping true at 412. Any narrow-width number in earlier runs taken through `resize_window` alone should be treated as unverified.

## Overall Impression

Nothing regressed. The score fell because a reviewer weighted the two things that have been true all along — volume and an amber-saturated chrome — more heavily, and because a defect class that three previous contrast passes could not see finally surfaced.

The shape of the product is now clear and consistent across four independent reviews: **every strength is a sentence and every weakness is a shape.** The copy could be pasted into a competitor and still be the best writing in the category; the layout could have been pasted *from* one. The disposition line, the refusal dictionary, the scope-before-number pattern and the commit funnel are all genuinely excellent and all made of words. The 4.9-screen Command surface, the 169-to-24 amber chrome, the five identical primary buttons and the interchangeable rail are all made of shapes.

## What's Working

**1. The refusal writing is the positioning rendered as UI, not asserted in a footer.** `NO_ELIGIBLE_PLAYBOOK` → "no strategy covers that market condition". The Diagnostics bottleneck pill names the stage, the count, the plain reason and offers "OPEN SETTINGS →".

**2. The commit path is a three-stage funnel, each stage naming a different class of mistake with its own remedy.** `#tkBlock` refuses over-margining and hands over a one-click correction; `#tkFling` catches a >3× risk change and is deliberately *not* a refusal; `SSConfirm` restates the terms last. Verified live: `role="alertdialog"`, `aria-modal`, Cancel focused, Tab trapped both directions, focus restored, no stacking, HTML escaped.

**3. Scope is placed before the number, as a repeated layout primitive.** `.era-band` on Results, the edge panel's own preamble, the picker's SHADOW — NEVER SIZED group, "hand-picked · not engine record", "11 shadow symbols are not listed". Five places a number could be misread, and in every one the scope arrives first.

## Priority Issues

### [P1] Ancestor opacity puts the product's core claim below AA

`.deck-row.dead{opacity:.55}` (ss.css:1166) and `.deck-row.done{opacity:.72}` multiply down onto text that passes at full opacity. 161 elements measured below 4.5:1; the refusal sentence itself at **2.82:1**, the prices at **3.10:1**, the action buttons at **3.51:1**.

**Fix.** Delete the opacity. Mark dead rows structurally — the `.deck-row.done` inset rule already does this — and if de-emphasis is still wanted, drop the *chrome* a step rather than the content.

**Suggested command:** `/impeccable audit`

### [P1] The skip link navigates off-surface and never moves focus

`shell.html:18` is `href="#s-command"`, hard-coded, with no JS handler anywhere. Measured from all five surfaces: from four of them it navigates **away** to Command, and in all five `document.activeElement` ends as `BODY`. `#s-command` is a `<section>` with no `tabindex`, so it cannot receive focus.

The earlier fix stopped this emptying the app. It did not make the link do its job: the one control that exists exclusively for keyboard and screen-reader users still teleports the reader and drops focus on the floor.

**Fix.** Point the href at the active surface (the same place the router sets `nav a.on`), give each `.surface` `tabindex="-1"`, and call `.focus()` on the target so focus lands in content.

**Suggested command:** `/impeccable harden`

### [P1] DEGRADED is shed at ≤900px because the escape hatch covers one path of two

`ss.css:581` hides `#healthChip` below 900px, with `#healthChip.degraded{display:inline-flex}` as the only escape. `shell.js` adds `.degraded` at line **299 only** — inside `markDegraded()`, the fetch-failure branch. The pipeline audit's own verdict at line **2619** sets `textContent = h.status` (PASS / DEGRADED / BLOCKED) and adds no class.

Measured at 820 and 412: `display:none`, `className === 'chip'`, text `DEGRADED`, rect 0×0. The status bar carries no health and `#nDiag` counts blockers only, so at tablet and phone width the operator has no permanent signal that the data behind every number on screen is flagged.

The comment at `ss.css:582` says "shell.js adds .degraded when a refresh fails" — accurate about what was built, and the tell that only one path was considered.

**Fix.** Key the rule off state rather than a class one branch happens to set: add `.degraded` wherever `healthTone()` is not clean, or invert the query to hide only when the audit is clean.

**Suggested command:** `/impeccable harden`

### [P2] The copy contradicts the state it describes, twice on one surface

`expiresIn()` at `shell.js:558` returns `'expiring now'` for any `m <= 0`. All five "Looked at, not taken" rows carry it in `var(--amber)`, including one found six days ago that the differ has already classed `.dead`. The row knows it is dead; the label manufactures urgency on something that cannot be acted on.

Separately the disposition says "5 were examined and refused" while the deck 400px below says "looked at 144 chances and passed on every one". Two genuinely different populations, near-identical verbs, no scoping word on either.

**Fix.** Add the past branch: `expired ${ago}` in `--fg-4`, reserving amber for `m > 0`. Scope both phrasings: "5 setups passed the engine and were not taken" / "144 candidates never became a setup".

**Suggested command:** `/impeccable clarify`

### [P2] Amber has eaten the accent

`[data-mode="paper"]` reassigns `--accent` to `--amber`, and with a hard 2-position cap that is currently full, paper is effectively the permanent state. Measured across Command and chrome: **169 amber-tinted elements to 24 green**. `.t-page`, `.nav a.on` and every `.btn-primary` now share the hue that `.deck-row.held`, `.ticket.managing` and `#tkOpen` use to mean "your money is on this".

Permanent caution is no caution, and the binding green identity is visible only when flat.

**Fix.** Fire the mode on *pending or armed* rather than any exposure, or confine amber to the exposure components and leave the chrome green.

**Suggested command:** `/impeccable colorize`

## Persona Red Flags

**Alex (power user).** Accelerators are better than they look — 1–5 for surfaces, `c` for copilot, `?` for the list, arrow keys in the picker, ±tick/±0.1R nudges — but `?` has no discovery affordance anywhere in the chrome. Command is 3,920px at 1440 with no way to collapse a panel he has read four hundred times. The picker's 85 rows are all tabbable even though arrow keys work. `#tkReset` is all-or-nothing with no per-level revert on a surface whose primary interaction is dragging.

**Sam (accessibility-dependent).** The skip link teleports him and drops focus. The refusal reasons sit at 2.59–2.82:1, unreadable for low vision without being formally hidden. `aria-description` is the sole non-visual carrier for the 40-term glossary — an ARIA 1.3 attribute with uneven support, and the visible fallback popover has no role and no `aria-live`. `#cSymBtn` still advertises `aria-haspopup="listbox"` while the list is `role="group"` with no `aria-selected`, no `aria-activedescendant` and 85 tab stops: the widget *behaves* as a listbox (arrow keys and Enter are implemented and verified), the button promises one, and the list denies being one. Touch targets: 21 of 35 interactive elements under 44×44 on Command at 412, 26 of 45 on Chart, 12 of 13 on Settings — while `.tk-nudge` is 44px at every width, which proves the floor is understood and simply was not applied.

**Briefed-but-new reader.** Their first act of arithmetic on the home screen fails: 5 vs 144. Five amber "EXPIRING NOW" rows on things that expired days ago read as "you keep missing trades". "DEGRADED" sits in the permanent top bar with no on-screen explanation. **"Copilot" is the loudest button on a live position row, above "Close"** — a new reader concludes the assistant is the recommended action on an open trade. And nothing on any surface states the thing the product is for: that no strategy currently clears zero. Results shows −3.77% and 0.62 profit factor and leaves the conclusion to the reader, on a surface whose sibling proves the team knows exactly how to write that sentence.

## Minor Observations

- **"Cancel" beside "Cancel the order"** — two adjacent uppercase buttons, one dismissing and one proceeding. Rename the dismiss to "Keep the order".
- **Duplicated permanent chrome.** `#scanChip` "WATCHING 19 TRADEABLE" over a status bar reading "WATCHING THE MARKET · 19 TRADEABLE"; `#modeChip` "PAPER" over "Sim only — no live orders". 82px of a 720px viewport is permanent chrome and a third of it repeats itself.
- **Settings' Risk and Guardrails restate four constants under different names**, two read-only panels in the same column stack.
- **Results has no disposition line.** "Not proven: 7 trades, average −0.27R, and the interval crosses zero" would cost nothing and is the app's own house style.
- **Command's last panel is "Bitcoin backdrop — OBSERVATIONAL"**, documented as having zero consumers, closing a 4.9-screen surface that asks what to do right now.
- `#nearCount` counts something the rows do not: chip reads "7 OF 25 IN RANGE" with 10 rows above the fold and 15 folded.
- `.stage` keeps `padding:24px 28px` at 412 — 13.6% of the width — while the nav runs full-bleed.
- **PRODUCT.md drift:** it names a LEARN surface among current surfaces; the shell has neither route nor nav entry. Either the surface or the line should go.
- **Hover-only content: 0 remain** after a 3-second settle. 56 long titles, all stamped, all described, all focusable. The only gap is the 250ms debounce window on freshly-injected elements.
- **No horizontal document scroll at any width** on any of the five surfaces. The only horizontal scroller is the nav at 412, which is deliberate.

## Questions to Consider

1. **The disposition line is the best idea in this product. Why does it exist on exactly one of five surfaces?** Write the sentence for Chart, Results, Settings and Diagnostics. If two are hard to write, that says something about those surfaces, not about the exercise.
2. **The account is capped at 2 positions and holds 2, so the app is amber essentially always.** What is a mode indicator for when its "on" state is the resting state?
3. **Every strength here is a sentence and every weakness is a shape.** What would the shell look like if the reticle were a layout principle — one centred aperture, everything else falling away — rather than a PNG in the corner?
4. **Five setups say "EXPIRING NOW" while dead, at 55% opacity, under "Looked at, not taken".** Is that panel a record or a reproach? If it is the most important record in the product, why is it the dimmest thing on the screen?
5. **"Copilot" is the primary button on a live position, above "Close".** If the assistant can never act, why is it the loudest control on the one row where acting is the only thing that matters?
