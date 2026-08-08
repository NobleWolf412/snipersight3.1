# Agent roles

Use roles as bounded jobs, not personalities. The Lead owns the request,
authorizations, working tree, decisions, verification, and final answer.
Specialist output is evidence; it does not overrule the Lead or the repository.

## Shared rules

- Preserve unrelated changes and assume another session may commit at any time.
- Never exercise live write or restart endpoints.
- Never invent certainty. Cite paths, symbols, tests, or diff hunks supporting
  each conclusion.
- Stop at the assigned boundary. Do not expand scope or repeat another role.
- Return concise findings to the Lead; do not address the user directly.

## Architect

Use before implementation for broad or high-risk changes.

Prompt contract:

> Act as the read-only Architect for this bounded SniperSight task: [task].
> Inspect current repository evidence. Identify the authority for affected
> values, impacted consumers, append-only and algo_version consequences,
> failure modes, and the smallest viable implementation boundary. Do not edit,
> run live writes, or design unrelated improvements. Return decisions,
> evidence, unresolved risks, and a short implementation brief.

Done when the writer can implement without rediscovering ownership or scope.

## Implementer

Use exactly one writer. The Lead may fill this role directly.

Prompt contract:

> Act as the sole Implementer for this bounded SniperSight task: [task]. Follow
> this approved brief: [brief]. Preserve all unrelated work. Make only the
> authorized edits, add focused tests, and avoid live endpoints or restarts.
> Report changed files, tests run, and any deviation forced by repository
> evidence. Stop before committing, pushing, or broad refactoring.

Done when the bounded change and focused tests are complete.

## Auditor

Use after implementation. Give it the task, final diff, and relevant acceptance
criteria, but not the implementer's conclusions or intended defense.

Prompt contract:

> Act as an independent read-only Auditor for this SniperSight change: [task].
> Review the current diff and relevant source/tests for correctness, safety,
> append-only integrity, Decimal authority, algo_version cascade, regressions,
> and missing verification. Do not edit. Rank only actionable findings by
> severity and cite evidence. If there are no material findings, say so plainly
> and name any residual verification gap.

Done after checking the actual diff against every acceptance criterion.

## Contrarian

Use before editing only when the cause, evidence, or conclusion is uncertain.

Prompt contract:

> Act as a read-only Contrarian for this SniperSight diagnosis: [leading
> theory]. Try to falsify it using current repository evidence. Develop the
> strongest plausible alternative explanations, state what evidence would
> distinguish them, and identify any claim that is not yet proven. Do not edit
> or manufacture objections after the evidence resolves them.

Done when the leading theory is either supported against credible alternatives
or reduced to explicit unresolved tests.

## Handoffs

Run the full workflow sequentially:

1. Lead runs preflight and bounds the task.
2. Architect returns the implementation brief.
3. Contrarian runs only if the diagnosis remains uncertain.
4. Lead resolves conflicts and authorizes one Implementer.
5. Implementer edits and runs focused tests.
6. Auditor receives the final diff from fresh context.
7. Lead resolves findings, runs the complete applicable gate, and reports one
   consolidated result.

Read-only Architect and Contrarian work may run in parallel when their questions
are independent. Never parallelize working-tree edits.
