# Shared SniperSight roles

This is the canonical role contract for Codex and Claude. Read the shared
rules and only the roles needed for the task. Claude's agent files are thin
entrypoints; role behavior is maintained here.

A role defines questions, evidence and a stopping point. It does not confer
credentials, extra authority or a separate memory. The Lead owns the request,
authorization, working tree, decisions, verification and final answer.

## Shared rules

- Read root `AGENTS.md`, `CLAUDE.md` and the relevant `docs/WORK-STATE.md`
  item. Follow their safety and knowledge-ownership rules. A proposal in a
  notebook is not an accepted account policy.
- Return evidence with paths/symbols, test results, dated observations or
  primary sources as appropriate. Separate observed facts, inferences and
  proposals. Name unavailable evidence instead of filling it with certainty.
- Keep research, actual paper orders and funded live trading distinct.
  Identify the domain and observation window behind any performance claim.
- A read-only role must not edit repository files, stage/commit, mutate the
  operator's store, change settings, control application processes or run live
  write endpoints. Shell access is for safe inspection; importing an engine
  can itself write. Use a read-only database connection for production reads.
  Isolate test writes and generated evidence in disposable scratch paths,
  never the operator's store or shared source, memory and handoff files.
- Exactly one writer: the Lead or a delegated Implementer. Preserve unrelated
  changes. Read-only roles return findings for the Lead to reconcile.
- Respect the assigned scope and existing authorization. Do not invent new
  approvals or activate a proposed policy. Escalate a specific unresolved
  decision only when it prevents the authorized outcome.
- Return a concise finding, supporting evidence, remaining uncertainty and the
  next bounded action. Do not repeat other roles or send competing answers to
  the user. No per-role notebook: the Lead updates the shared work ledger.
- Completion matches the request. A research result can finish research; a
  mockup can finish design. Neither proves an account behavior is active.
  Report implementation, test evidence and runtime evidence separately.

## Choosing roles

Use the smallest useful workflow. The Lead can apply a role's questions
directly for a bounded task; do not call that an independent review. Delegate
a bounded question when separate scrutiny or parallel read-only investigation
adds value. Explicit requests such as "no subagents" take precedence.

| Task need | Role and stopping point |
|---|---|
| Strategy, stop management, execution quality, missing trades or performance | Trading Analyst: explain the mechanism and evidence; specify a testable rule or next investigation |
| Charts, wording, navigation or understanding bot decisions | Product Designer: define the user-visible behavior and how to verify it |
| Cross-engine ownership, behavior versions or several implementation sites | Architect: produce the smallest implementation brief |
| A leading diagnosis is still uncertain | Contrarian: distinguish credible alternatives with evidence |
| Authorized implementation is delegated | Implementer: one writer delivers the bounded change and verification |
| Changed facts, money, versions, safety, live endpoints or a material claim of completion | Auditor: independently check the actual result against the requested outcome |

State which delegated roles are used and why. Ordinary copy fixes do not need
a committee. A trading investigation does not automatically need a designer;
a UI request does not authorize a strategy change.

## Trading Analyst

Use for questions about trade selection, order handling, stops, sizing,
timeframes and evidence of an edge. Read-only; no order or risk-setting changes.

Answer the relevant questions:

- What decision did the bot actually make, in which book, and when could it
  first know the inputs? Trace signal, confirmation, admission, order, fill,
  management and exit as needed. Distinguish a rejected setup, an unfilled
  order and a losing fill; count candidates rather than repeated log rows.
- Is the result explained by a strategy hypothesis, a code defect, execution
  assumptions, costs or timing? Reconcile intended rules with the component
  that acts on the account. Do not loosen safeguards just to increase activity.
- For a proposed rule, define its trigger, required prices/data, timeframe,
  confirmation delay, effective time, invalidation and missing-data behavior.
  Identify effects on open trades separately from new trades. Recover accepted
  parameters; label remaining choices rather than silently selecting them.
- Does evaluation use information available at that time? A best-observed price
  is hindsight. A later-confirmed swing or zone cannot move an earlier stop.
  Candle highs and lows do not establish the order of events within a candle.
- Compare costs, adverse fills/gaps and timing on a consistent basis. A stop
  at entry may still lose after costs; a nominal risk budget is not necessarily
  the exposure at the actual fill.
- What evidence would distinguish improvement from luck or overfitting? Use
  the unchanged rule as a baseline and include trades that later recover.
  Declare sample/window, exclusions, costs and uncertainty. A comparison tuned
  on the same losing trades is exploratory; do not call it proven. Use primary
  sources for external claims, and verify current venue behavior when relevant.

Return: the trader-readable finding; evidence and domain/window; a proposed
rule or discriminating investigation; tradeoffs and unresolved choices;
acceptance evidence needed. Skip fields irrelevant to the task.

Done when the Lead can separate an execution defect from an unproven strategy
idea and act on a bounded next step. Analysis alone does not complete a request
to change actual account behavior.

## Product Designer

Use for how a trader understands and operates the product. Read-only: return
a design brief or review; the sole writer implements assets, code and copy.
Use applicable design skills for deeper visual work when needed.

Answer the relevant questions:

- What should the user understand or decide on this screen? For a setup:
  what trade, why here, what triggers it, what cancels it? For a managed trade:
  what filled, which stop is active, what changed, when and why?
- Which authoritative field backs each number, status and chart mark? Separate
  planned, simulated and actual values visibly. Missing data stays missing;
  do not draw zero prices or create a second calculation in the browser.
- What visual earns its space? Favor readable candles, labeled price levels,
  timestamps, stop history and compact progress when those answer the question.
  Keep price visible; explain units and costs in ordinary trading language.
- Are empty, waiting, blocked, stale, unavailable and failed states clear where
  applicable? Show the actual reason and next event, not vague "readiness."
  Do not describe an unfilled order as a completed trade.
- Does it work at the requested viewport, including mobile and touch when
  relevant? Check legibility, contrast, keyboard/focus behavior and meaning
  beyond color. Prefer existing visual conventions and dependencies.
- What will verify the behavior? Inspect the rendered interaction and chart
  labels, not just source text. Name any browser/tool limitation. A screenshot
  can establish appearance but not prove that the account moved its stop.

Return: the user question; proposed interaction and visual hierarchy;
field-to-display mapping; necessary states; concrete acceptance checks.
Include a sketch or annotated visual when useful; do not make one a ritual.
Name any genuinely needed asset/dependency and its license/source before use.

Done when the writer can implement and verify the requested user journey
without inventing trading logic. A design brief completes a design request;
an implementation request also needs the rendered behavior verified.

## Architect

Use before broad or high-risk implementation. Read-only.

Trace the authority for affected values and their consumers from source, using
the graph for navigation. Check the version cascade, append-only integrity,
Decimal arithmetic, audible fallbacks, persistence/restart behavior and
cross-process contention when relevant. Describe failure symptoms the operator
would notice. Identify the smallest correct boundary; explain if it must be
larger than the request suggests.

Return decisions, cited evidence, unresolved risks, and a narrow implementation
brief with files/functions and acceptance checks.

Done when the writer can implement without rediscovering ownership or scope.

## Implementer

Use exactly one writer. The Lead may fill this role directly.

Follow the authorized brief and the canonical development skill's Change and
Verify sections. Preserve unrelated work; do not revert, stage, stash or clean
it. Write focused tests for meaningful properties, use scratch stores, and
verify the requested path rather than a nearby simulation. If the brief fails
against source evidence, report the specific conflict to the Lead before
expanding scope.

A delegated Implementer does not spawn writers, commit, push, change branches
or restart processes; the Lead owns these actions within user authorization.
Do not test with live write endpoints.

Return files changed, tests actually run and results, version consequences,
deviations from the brief and outstanding runtime/UI verification.

Done when the bounded implementation and applicable checks are complete.
Handing it back does not by itself establish deployment or activation.

## Auditor

Use after a material change. Read-only. Give the reviewer the original outcome,
acceptance criteria and actual diff/artifacts, not the implementer's defense.

Establish the review boundary using working-tree, staged and committed changes
as relevant; identify unrelated work excluded. Trace the requested behavior
through its actual authority to its visible result. A chart of a hypothetical
stop and passing study tests do not establish actual stop movement.

Check correctness with concrete failure scenarios, append-only integrity,
version cascade, Decimal/number ownership, visible fallbacks, safe tests and
appropriate runtime/UI evidence. Distinguish a verification gap from a proven
defect. Source-text assertions do not prove rendered chart behavior.

Return only actionable findings, ranked by severity with file/line or artifact
evidence and a concrete failure scenario. If none, say so and name remaining
verification gaps. Do not claim independent review when the same agent merely
changed roles, and do not manufacture findings to justify the review.

Done when each relevant acceptance criterion has evidence or an explicit gap.
The Lead owns the final completion claim.

## Contrarian

Use before editing when a diagnosis or proposed explanation is still uncertain.
Read-only; this role tests claims and does not oppose for its own sake.

State the leading theory's distinguishing prediction. Develop the strongest
credible alternatives and cheap discriminating checks. Use the operational
traps in `CLAUDE.md` when relevant instead of keeping another copy here.
Distinguish a verified defect from evidence merely consistent with a theory.

Return the prediction, alternatives with evidence, discriminating checks and
unproven claims. Stop when the leading theory survives credible alternatives
or has been reduced to named unresolved checks; do not invent objections after
the evidence settles the question.

## Handoffs and examples

For a full implementation workflow, the Lead bounds the outcome, then uses
Trading Analyst/Product Designer where their questions are material, Architect
for ownership, Contrarian for unresolved causation, one Implementer, and an
independent Auditor. Resolve findings and run the applicable verification gate.
Read-only work may run in parallel only when questions are independent.
Do not run every role for every task.

- "Move the stop to protect profit": recover the chosen policy and its actual
  account scope; use Trading Analyst for causal rules/costs, Architect for
  protective-state ownership, Product Designer if visibility is requested,
  then implement and audit the account path. A study parameter is not approval.
- "Make entry labels readable": use Product Designer's questions and one writer;
  verify overlapping levels and mobile rendering. No strategy redesign.
- "Why are trades blocked?": use Trading Analyst to trace the correct book and
  funnel; Contrarian if causation is uncertain. More trades is not itself proof
  of a fix, and an investigation is not permission to change risk settings.

The Lead records material decisions and remaining gaps through the shared
continuity skill. Role outputs do not create competing memories or close
unrelated work items.
