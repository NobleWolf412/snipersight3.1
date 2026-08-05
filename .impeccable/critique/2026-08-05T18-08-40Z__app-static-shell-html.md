---
target: app/static/shell.html
total_score: 32
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-08-05T18-08-40Z
slug: app-static-shell-html
---
Method: dual-agent (A: aafeed9da96febe48 · B: aebb12d73f1307bae)

Surface mode: **Operate**. Target `app/static/shell.html`, inspected live at `http://localhost:8422` at 412, 820 and 1440 px. Read-only: 60 observed requests, all GET. HEAD `dd99947`.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | One topbar chip carries two unrelated failure domains one word apart: `DEGRADED` (pipeline audit) and `API DEGRADED` (browser cannot reach the server). |
| 2 | Match System / Real World | 4 | Best in class. Deductions: `min_volume_usd` renders as raw `3000000`, no separators, no unit; "Scale-in adds" is the only setting with no description. |
| 3 | User Control and Freedom | 3 | The skip link blanks the app. `.stage` scroll resets to 0 on every surface change, on a 5,072px surface. Escape closes the symbol picker and not the Layers popover. |
| 4 | Consistency and Standards | 2 | `role="listbox"` shipped with no arrow-key model and no `aria-selected`, thirty lines below a comment refusing to do exactly that with `role="tablist"`. `.locked-ctl`/`.locked-why` defined and used zero times. |
| 5 | Error Prevention | 4 | `#tkBlock` reads "This posts $20,351 of margin against a $10,032 account" and offers `USE 3X — POSTS $6,784`. No hotkey binds arm, halt or cancel. |
| 6 | Recognition Rather Than Recall | 3 | `#btnAuto`'s entire meaning is a 148-character title on a **disabled** button — skipped in AT focus mode. The At-a-level rows repeat one 130-character sentence verbatim eight times. |
| 7 | Flexibility and Efficiency | 3 | Number keys 1–5 work and are documented nowhere. An 85-option symbol picker traversable only by Tab. |
| 8 | Aesthetic and Minimalist Design | 2 | Command is **5,072px against an 818px stage** at 1440, **11,787px** at 412. `#nearPanel` is 66% of it, and 17 of its 28 rows say "ENGINE IS NOT LOOKING". |
| 9 | Error Recovery | 4 | The funnel names an 81% bottleneck, the code behind it, and jumps to the setting that causes it. Deduction: the blanked-app state has no message and no recovery. |
| 10 | Help and Documentation | 4 | 40-term glossary at point of use with `aria-description`, not `aria-label`. Deduction: the edge panel says compare against "the tiles above" while sitting on a surface with no tiles. |
| **Total** | | **32/40** | **Good — solid foundation, address weak areas** |

**Trend: 24 → 28 → 32.** Error Recovery 1 → 3 → 4. Help 3 → 3 → 4. Consistency has sat at **2** all three runs.

## Design Specificity Verdict

**Strongly specific. The identity is carried by language and by honesty, not by the reticle, and the sniper register survives without the decoration.**

Almost nothing here survives being lifted into another product. The deck's empty state reads "The engine looked at 142 chances in this window and passed on every one" and names the top refusal reasons in English. The At-a-level rows are stamped `ENGINE IS WATCHING` / `WAITS FOR PRICE` / `ENGINE IS NOT LOOKING` because the chart draws a bracket on markets the engine never considered and the row has to disown it. `venueNote` is a chip rather than a select, with a comment explaining that the select it replaced *actively lied*.

Two slips toward generic: **Settings** is the only surface that does not pose a question, and **Results** answers "Is this actually working?" with eight co-equal 26px tiles — the KPI-strip move Command was rebuilt to stop doing.

**Deterministic scan.** 5 findings, unchanged across all three runs: `side-tab` ×3, `overused-font` ×1, `em-dash-overuse` ×1 (advisory, self-marked). Scope `type`: 1. Scope `layout`: **0**.

- **Type scale holds.** 1024 visible text elements across ten computed sizes; 964 of them land on the seven-step token scale. The 11 below the 11px floor are all SVG `<text>` in the equity curve and the Diagnostics axis, written from JS as `font-size="10"` / `"9.5"` attributes in SVG user units, which the CSS scale cannot reach. Fourteen at 13px come from two inline `style="font-size:13px"` writes in `shell.js`.
- **Contrast: 0 failures**, 395 elements on Command and 241 on Results, floor **5.82:1**. B rebuilt the resolver on a canvas round-trip after finding that **308 of 395 foregrounds are `oklch()`** — a hex/rgb regex silently drops ~78% and reports a false clean. It then re-ran compositing every ancestor gradient colour stop as a worst-case backdrop. Both passes returned zero.
- **Hover-only content: 0 remaining.** The `reachableTitles()` MutationObserver stamps every long title with `tabindex` and `aria-description`. B measured 8 undescribed on a first sample and 0 after a 3-second settle — those 8 were inside the observer's own 250 ms debounce on freshly-polled position rows. A real but self-healing sub-250 ms window, not a standing defect.
- **No page-level horizontal overflow at any width.** The 95 elements past the right edge at 412 are all inside `#perfSymbol` and `#perfStrategy`, which are deliberate `overflow-x:auto` scrollers. Non-scroller overflow at 412: **0**. `#btnHalt` fully inside the viewport at all three widths.

**Tooling finding, still true on the third run.** Scanning `shell.html` alone returns exit 0 and one advisory — a false all-clear that misses all four CSS findings, because `css-cascade.mjs:958` resolves `/static/ss.css` to `C:\static\ss.css` and the read throws into a bare catch at 968. Always scan the directory.

**Visual overlays.** None. Screenshots fail; the pane does not composite. Two artifacts of that were excluded by brief and confirmed by B: `requestAnimationFrame` never fires (so transitioning colours freeze and hover/focus contrast is unmeasured) and `ResizeObserver` never delivers (so chart canvas geometry is unmeasurable). Neither is counted against the surface.

## Overall Impression

Four points again, and this time the gains are in recovery and help rather than mechanics. The measured floor is genuinely good: zero contrast failures under a resolver that handles `oklch`, zero hover-only explanations, zero non-scroller overflow at phone width, ARIA state correct on every segmented control and the rail.

What is left divides cleanly in two. One half is **volume**: Command is now 5,072px at desktop and 11,787px at 412, and two thirds of it is markets the engine has explicitly disowned, each carrying the same sentence. The prior audit called this surface a failure at 2,133px; it is 2.4× longer now. The other half is **contracts asserted but not implemented**: a `role="listbox"` with no keyboard model, a `role="button"` wrapping three real buttons, a `.locked-ctl` pattern written for disabled controls and used nowhere, and a skip link pointing at an id the router cannot resolve. In every case the codebase already contains the correct reasoning, written down, next to the thing that does not follow it.

## What's Working

**1. The confirmation layer, verified end to end.** `role="alertdialog"`, `aria-modal`, `aria-labelledby` resolving to the title, a real Tab trap, focus returning to the opener, Escape resolving `false` and removing the node, and Cancel focused first with the reasoning stated in the source. Five call sites, all with plain-English consequences — *"Open positions still settle — refusing to close a position is not safety."*

**2. Refusal is a first-class result everywhere.** The deck's empty state, the funnel's named bottleneck with a jump to its cause, and `#tkBlock`'s `USE 3X — POSTS $6,784` all name the constraint, quantify it, and hand back the one action that resolves it. Most trading tools show a spinner and a disabled button.

**3. The colour system holds up under a resolver that can actually read it.** 636 elements measured across two surfaces, zero failures, floor 5.82:1, focus ring 14.22:1, `prefers-reduced-motion` honoured globally at `*` rather than at eight sites.

## Priority Issues

### [P0] The skip link blanks the entire application, from every surface

**Verified live.** `shell.html:18` is `<a class="skip-link" href="#s-command">`. `shell.js:129` routes on `go(location.hash.slice(1))`, and `go()` at line 50 toggles `.on` where `s.id === 's-' + name`. The skip link sets the hash to `s-command`, so `go('s-command')` looks for `#s-s-command`, matches nothing, and turns every surface and every rail item off. `SURFACE_ALIASES` at line 42 maps only `setup` and `rules`, so nothing rescues it.

Measured: stage text **10,734 characters → 0**, `surfacesOn: []`, `navOn: []`. Recovery requires clicking a rail item; there is no message and no affordance.

**Why it matters.** This is the first tab stop on the page and the one control an accessibility-dependent user reaches before anything else. It is also the failure mode for any bookmarked or mistyped hash.

**Fix.** Point the skip link at `#command`, and make `go()` refuse to land nowhere: after the alias lookup, `if(!document.getElementById('s-' + name)) name = 'command';`. Add `tabindex="-1"` to `#s-command` so focus actually moves.

**Suggested command:** `/impeccable harden`

### [P1] Command is 6.2 screens at desktop and 12.9 at phone; two thirds is markets the engine disowns

At 1440×900 the surface is 5,072px against an 818px stage. `#nearPanel` alone is 3,341px — **66%**. At 412×915 the surface is 11,787px and the panel is 73%. The chip says `8 OF 28 IN RANGE` and the other 20 render anyway; 17 sit under a divider reading "Beyond the 1 ATR the engine looks" and each repeats *"Further out than the 1 ATR the engine looks. It is not considering this zone."* The same 130-character sentence appears verbatim eight times in the in-range group alone.

All three session shapes in PRODUCT.md are penalised: the short check scrolls past 3,300px of disowned markets, the long dive loses its place on every surface change (`.stage` scroll resets to 0), and the deep dive gets no filter.

**Fix.** Wrap the 17 out-of-range rows in a `<details>` summarised by the divider text — that pattern already ships three times in this app. Cap the in-range list at 8 with a "show all". Print the explanatory sentence once per group. Estimated 5,072px → ~1,700px.

**Suggested command:** `/impeccable distill`

### [P1] ARIA roles asserted without their patterns, on the two controls that matter most

**`#cSymList` is `role="listbox"` with no keyboard model.** 85 `role="option"` children, `aria-selected` on **zero** of them — the current symbol is marked by class alone. No `aria-activedescendant`, no roving tabindex, no label on the listbox, and ArrowDown from the search box does nothing. The only traversal is Tab through 85 stops. Three roleless `div.sym-group` headers sit inside as owned content, which `listbox` does not permit. This is thirty lines below the comment that removed `role="tablist"` because *"it promised a screen-reader user a behaviour that was not there, which is worse than plain buttons."*

**`.pos-row` is `role="button"` containing three real buttons** — Reasons, Copilot and Close. ARIA prohibits focusable descendants inside `role="button"`; the accessible name computes to the entire row, and the control that ends a live position is buried in it. B found five such owners document-wide, including a `span.term[role=button]` nested inside another.

**Fix.** Either implement the listbox pattern or drop the roles and let them be plain buttons in a labelled group. Remove `role`/`tabindex` from `.pos-row`, promote the symbol to a link, leave the three actions as siblings.

**Suggested command:** `/impeccable audit`

### [P2] Results asks a question and buries its answer

`.surface-head p` reads "Is this actually working?". The answer — *"8 trades — far too few to read anything into"* — is **11px in `--fg-4`**, the dimmest step, below eight 26px metrics. Command's equivalent is 16px in `--fg` above the evidence, with a forty-line comment explaining why.

PRODUCT.md principle 1 is honest before flattering, and the stated success condition is a record honest enough to *refuse* live execution. The composition gives an unreadable sample the weight of a footnote and an 8-trade profit factor the weight of a headline.

**Fix.** Add a `.disposition` line under the Results head from the same figures the tiles read: *"Not yet. 8 closed trades, average -0.01R — too few to tell either way."* Demote the caveat to a sub-line on the trades tile.

**Suggested command:** `/impeccable layout`

### [P2] The commit bar is below the fold at both narrow widths

`.commit-bar` is `position: static` with no rule below 900px. At 412×915 `#tkArm` lands at y=1419, roughly 500px below the fold. At 820×1024 it lands at y=1401, and the chart surface scrolls at exactly the "app in a split pane" width the breakpoint comment names as ordinary. The deciding numbers, the breach warning and Arm were deliberately pulled out of the ticket so they could never be hidden behind a tab; on a phone they are hidden behind a scroll instead.

Also at 820 the ticket stretches to 753px and the entry, target and stop inputs render **623px wide for a 9-character price**.

**Fix.** `@media(max-width:900px){.commit-bar{position:sticky;bottom:0;z-index:5;background:var(--bg-2)}}`. Cap `.ticket` when it stacks.

**Suggested command:** `/impeccable adapt`

## Persona Red Flags

**Alex (power user).** Scroll resets to 0 on every surface change, on a 6.2-screen surface — leaving a chart and returning costs him his place every time. The 85-symbol picker has no arrow keys. The 28-row At-a-level list has no filter, sort or cap. Layers will not close on Escape though the symbol picker will, and opening it does not move focus in, so a keyboard user is left with an open popup and no way out. Number keys 1–5 work and are advertised nowhere.

**Sam (accessibility-dependent).** The first tab stop on the page destroys the view, with no announcement and no recovery. `role="listbox"` announces a listbox whose options carry no selected state and cannot be arrowed. `role="button"` wraps the control that closes a position. `#btnAuto` is `disabled`, so its 148-character description is skipped in focus mode — and `.locked-ctl`/`.locked-why`, written for exactly this and commented *"A disabled control carries its reason INLINE"*, is used **zero times**. `.btn` boundaries measure **1.74:1** against `--bg`, below the 3:1 that SC 1.4.11 asks of a component boundary. Nothing reaches 44px tall at 412; the chart timeframe buttons are 30px. On the credit side, every text-contrast, focus-ring, reduced-motion, labelling and `aria-current` check passes.

**Briefed-but-new reader.** Gets a genuinely good first sentence, then a 339px tutorial card above $387 of live risk, then 3,300px of markets the engine says it is not looking at. Cannot learn what "Auto-trade: off" costs without a mouse. Meets `DEGRADED` and `API DEGRADED` in the same chip slot for two unrelated problems. Reaches Settings — the only surface that does not say what it is for — and finds a liquidity floor rendered as `3000000`. On Diagnostics, is told to compare against "the tiles above", and there are none.

## Minor Observations

- **`confirm-dialog.js:44` — my own bug.** `/^([^:]{1,28}):\s+(.+)$/` cannot match `R:R after fees: 1.93`, because `[^:]` cannot cross the first colon. The single most important ratio in the trade is the one line in the Arm dialog that falls out of the key/value column into loose prose. Verified in a live dialog.
- **`.ssc-warn` renders at 11px directly under a 26px `.ssc-emph`, in the same hue.** The flung-stop caution is the smallest text in the dialog it was designed to survive truncation in.
- `#cLayersPop` has no role and no label; Escape does not close it; `#cLayersBtn` carries `aria-haspopup="true"` (which means *menu*) over a popup with no `role="menu"`. Six of nine layer options read "— no data" and remain enabled.
- `#tkDir` has `aria-label="Trade direction"` on a roleless generic, so the label is inert. `#cTfs` has no role or label. Both have correct `aria-pressed` on their children.
- No element in the document has `aria-controls`; the two disclosure triggers rely on `aria-haspopup` + `aria-expanded` alone.
- `CLOSED TODAY` shows `—` with no sub-line while its three neighbours all carry one, so the tile reads as broken rather than empty.
- `#nDiag` counts hard blockers only, so the rail badge is silent while Diagnostics reports `1 FAILING` and a `DEGRADED` verdict.
- The disposition reads *"Nothing to take right now. 5 were examined and refused. Also, every position slot is full."* — "Also" subordinates the binding constraint, which is the stronger fact. Four inches below, `NEXT TRADE RISK` advertises `$193` for a trade that cannot be taken.
- The comment at `shell.html:16-17` claims tab order no longer reaches header glossary terms before an action. It still does; the skip link mitigates rather than fixes it.
- Zero control bytes in `ss.css` and `ssdata.js` — the scripted-escape trap is clean.

## Questions to Consider

1. Command's own comment calls seven co-equal panels over 2,133px the defect. It is now 5,072px with eight. If the disposition line is the answer, what is the argument for the other 5,048 pixels living on the same surface rather than behind it?
2. "At a level" exists because the chart draws a bracket on markets the engine never considered. That is a defect in the *chart*, corrected by adding 3,300px to Command. Would fixing the chart let this panel disappear entirely?
3. Four surfaces pose a question in `.surface-head p`; one answers it in a sentence. Should the answer line be a required part of `.surface-head`, so a surface cannot ship a question it does not answer?
4. `.locked-ctl` was written to put a disabled control's reason inline and is used nowhere. `role="listbox"` shipped without its pattern in the same file that removed `role="tablist"` for lacking one. Both are cases where the reasoning landed and the application did not. What check would have caught either, and is `test_shell_structure.js` the right home for it?
5. The confirm dialog gives `$201 at risk` 26px and "your stop moved by a factor of 3.1" 11px. Which of those two is more likely to be the thing that costs the operator money?
