# Tactical Cockpit Redesign

Status: code implementation, focused contracts, and the full repository gate
completed 2026-08-08. Overview and the persistent top bar are the reference
patterns. Opportunities, Trade, Performance, and System now follow the
focused-workspace structure below. Rendered desktop, mobile, and screen-reader
acceptance remains pending because the configured browser backend is
unavailable, and the Python runtime was not restarted under the user's explicit
prohibition. No screenshots are claimed. This redesign changes no trading
behavior; the accompanying server work is limited to additive or repaired read
models.

## Product rule

Each screen must answer one operator question before showing supporting detail.
The default view is for decisions; explanations, raw evidence, and engineering
trace belong behind deliberate disclosure.

Copy limits:

- Status: one line, ideally 12 words or fewer.
- Supporting reason: one sentence, ideally 20 words or fewer.
- Card front: no paragraphs.
- Longer evidence: drawer, disclosure, or detail pane only.
- Costs, stop, risk, invalidation, warnings, and automation state are never hidden.

## Shared shell

Use the rebuilt top bar on every destination:

- Identity: product, operating mode, venue.
- System state: scanner and data health.
- Account state: equity, free risk, positions and orders.
- Actions: Copilot and HALT.

Page headers use one title, one tactical subtitle, and at most one screen-level
action. Tabs represent genuine views of the same job, not unrelated features.

## Opportunities: Setup Radar

Question: **What deserves attention?**

Current friction:

- Cards expose nearly every field at once and become difficult to compare.
- The explanation and counterargument compete with entry, stop, and expiry.
- Filtering works, but priority and urgency are not visually dominant.

Target layout:

1. Sticky state bar: Ready, Forming, Watching, History, plus result count.
2. Compact comparison grid: pair, direction, horizon, strategy, quality,
   confidence, entry type, reward/risk, and expiry.
3. Selected-setup drawer: full economics, top-down ladder, invalidation,
   counterargument, FactorGrade, and trace.
4. One card action: `Review setup`. No capital action on this screen.

Key states: loading, quiet market, data degraded, stale setup, blocked, expired,
and selected. Keyboard movement must preserve the selected card and drawer.

Size: medium. Main dependency: reuse one setup-summary component in Trade.

## Trade: Execution Bay

Question: **Should I enter this setup, or how should I manage it?**

Current friction:

- Chart controls, evidence, and ticket compete for the same attention.
- Planning and position-management states share too much visual structure.
- Deep evidence is separated from the levels it explains.

Target desktop workspace:

1. Left evidence rail: recommendation, regime, timeframe ladder, trigger,
   invalidation, and the strongest reason not to trade.
2. Center chart: structure, entry, stop, targets, invalidation, and position
   overlays, with layer controls grouped by purpose.
3. Right action rail: order and risk ticket before fill; position controls after
   fill. The old ticket must disappear when state changes.

The same server-owned setup record drives all three panes. A prominent state
header distinguishes `PLANNING`, `ORDER WORKING`, `POSITION MANAGED`,
`MANUAL OVERRIDE`, and `HALTED` in words, not color alone.

Mobile uses a full-screen chart with bottom sheets for Evidence and Order or
Position. HALT, mode, and risk remain sticky.

Size: large. Dependencies: selected-opportunity state, position reconciliation,
and a shared setup-summary component.

## Performance: Debrief

Question: **Is the method earning trust?**

Current friction:

- Journal, equity, progression, promotion, strategy, and factor evidence read as
  one long report.
- Forward evidence and historical results can be confused.
- Important confidence and drawdown context sits beside lower-priority tables.

Target views:

- Overview: equity, drawdown, expectancy, profit factor, confidence interval,
  active baseline, and a concise trust verdict.
- Strategies: comparable results by playbook, regime, horizon, direction, and
  order type.
- Factors: Factor Stats evidence and FactorGrade calibration, with insufficient
  evidence stated plainly.
- Journal: searchable trade ledger with bot versus manual attribution.
- Promotion: paper, shadow, testnet, and live gates with blockers and evidence.

Filters remain sticky across views. Every number names its evidence window and
population. Tables become horizontally scrollable on mobile; summaries remain
visible without scrolling.

Size: large. Dependencies: existing performance and promotion read models;
factor evidence needs a compact summary contract.

## System: Control Room

Question: **What can run, and why?**

Current friction:

- Configuration and diagnostics are separate routes that still feel like long
  stacks of panels.
- Operating mode, credentials, strategies, risk, and live gates have similar
  visual weight despite very different consequences.
- Save state and blockers are not persistent while scrolling.

Target views:

- Automation: current mode, revision, halt state, allowed transitions, and
  promotion locks.
- Risk: fixed caps, current usage, daily halt, margin mode, and position mode.
- Venues: Phemex environment, credential health, permissions, metadata age,
  and connectivity.
- Strategies: playbook status, horizons, regimes, evidence status, and enablement.
- Diagnostics: failing checks first, reconciliation, stale data, rejection
  funnel, provenance, and raw console last.

A sticky change bar names unsaved settings and offers one `Apply changes`
action. Live-mode, risk, credential, halt, and capital-impacting actions retain
blocking confirmation. Read-only locks state the reason beside the control.

Size: large. Dependencies: cohesive automation and diagnostics read models.

## Delivery order

1. Extract shared page-header, status-strip, summary-card, detail-drawer, and
   sticky-filter patterns from Overview and Opportunities.
2. Redesign Opportunities, establishing the reusable setup-summary contract.
3. Redesign Trade around the synchronized three-pane state model.
4. Split Performance into focused evidence views without changing its numbers.
5. Reorganize System around consequence and add the sticky change bar.
6. Run a final vocabulary, accessibility, responsive, and cross-screen
   consistency pass.

## Acceptance

- The screen's primary question is answered above the first fold.
- No card front contains a paragraph.
- Every screen has one obvious primary action or explicitly says no action is required.
- Mode, health, equity, free risk, exposure, and HALT remain visible.
- Card, chart, ticket, journal, and performance views agree on server-owned facts.
- Desktop works at 1440px and mobile at 390px without hidden actions or horizontal page overflow.
- Keyboard, screen reader, focus, reduced motion, contrast, and 44px mobile targets pass.
