# SniperSight 3.1

This file is the authority for agents working in this repository. Work from
repository evidence and exercise independent judgment; do not adopt another
assistant's persona, assumptions, or conclusions.

Read **`CLAUDE.md`** before project work. It is the shared notebook for durable,
costly, and otherwise invisible behaviour: how to operate safely, expensive
traps, and conventions enforced by tests. Treat it as evidence that must stay
consistent with code and tests, not as a higher-priority instruction source.
If they disagree, report the conflict and verify what is true before changing
anything.

Do not duplicate the notebook here. Two copies drift, and this codebase treats
a document that misdescribes the code as worse than no document.

## AUTHORITATIVE PRODUCTION PATH

`app/start.bat` → `app/watchdog.py` → `app/live.py:main/cycle` →
`engine/importer.py` and venue adapters → `engine/aggregator.py` →
`engine/pipeline.py:run_symbol` → structure/zone/liquidity/regime facts →
`engine/setups.py` playbooks and confirmation → paper settlement and
`engine/riskpaper.py` → `engine/autotrader.py` → `engine/execution.py`.
The scanner then completes deferred research, replay risk, audit and alert
queueing. The watchdog delivers queued alerts through `app/notify.py`.

- `engine/registry.py` owns playbook metadata; `engine/setups.py` owns
  pullback/reversal evaluation, setup generation, confirmation and rejection.
- `engine/opportunities.py` projects domain-specific candidate/account state.
  `engine/lifecycle.py` instead manages private entry/protective orders.
- `engine/risk.py` owns shared sizing/admission math and replay risk;
  `engine/riskpaper.py` owns actual paper-book risk. Do not merge their books.
- `engine/broker_factory.py` and `engine/phemex_private.py` own private exchange
  integration. Mainnet routing remains build-locked; source is not activation.
- `app/server.py` includes `app/ui_api.py` and serves the default
  `app/static/cockpit.html`; `cockpit/app.js` and `cockpit/state.js` own its UI
  and request state. `/classic` deliberately retains `shell.html`/`ssdata.js`.

See [the architecture map](docs/PRODUCTION-ARCHITECTURE.md) for data/indicator,
HTF, API, research and support ownership. Check source when wiring changes.

## LEGACY CODE POLICY

Legacy/archived code is NOT an implementation reference unless explicitly
requested. Historical plans, reports and generated navigation do not supersede
current source. Check imports, dynamic registries, configuration, routes,
frontend strings/assets, subprocess/CLI entrypoints, tests and documentation
before calling anything dead. A missing static import is insufficient.

Keep uncertain removals in place with an explicit review record, or quarantine
on an isolated branch before relocation. Prefer Git history over archive
copies. Any physical archive must be excluded from imports, builds and runtime
discovery. Preserve supported compatibility paths until explicitly retired.
The [cleanup audit](docs/REPOSITORY-AUDIT-2026-09-28.md) records retained items
and the evidence required before future removal.

## PLAYBOOK POLICY

Playbooks are production trading logic. Research may READ and TEST them but
must not automatically overwrite them. A research-modified strategy initially
exists as a candidate and requires explicit promotion into production, with
the existing version cascade and safety contracts. Cleanup must not change
thresholds, scoring, confirmation, rejection, risk, alerts or exchange behavior.

## RESEARCH BOUNDARY

Reserve `research/` conceptually for backtesting, experiments, optimization,
walk-forward testing and future TraderDev/TradingKit integration. Do not create
those systems merely to satisfy this boundary. Existing research modules and
scheduled collectors remain in place and are mapped in the architecture guide.
Production scanner decisions and experimental state must stay separate;
sharing verified calculation helpers never permits sharing account state or
automatic strategy promotion.

## Working contract

- Lead with the outcome and explain it in trader-readable language.
- Inspect `graphify-out/wiki/index.md` before a broad code search. Use the graph
  to locate code, then read the code before describing cross-file behaviour.
- Check the wiki's build commit against `HEAD`; do not silently trust stale
  generated knowledge.
- Preserve unrelated work. Other sessions edit and commit to `main`, and a
  dirty working tree belongs to the user unless proven otherwise.
- Never test by calling a live write endpoint. Do not POST to manual arm,
  position close, position adopt, restart, or any other operation that can
  mutate the operator's book or processes.
- Before running a suite that opens the real application, confirm its safety
  guard and the protected action are both stubbed. Prefer focused tests and a
  scratch store.
- A behaviour change requires a new `algo_version`; never rewrite behaviour
  beneath an existing version. Follow the cascade enforced by
  `app/tests/test_version_cascade.py`.
- Prices remain `Decimal` end to end. The UI displays authoritative values and
  does not independently derive them. Fallbacks must be visible.
- After Python changes, restart before checking the running application.
- Use `scripts/preflight.ps1` for workspace state and `scripts/check.ps1` for
  the repository verification gate.

## Knowledge ownership

- `AGENTS.md`: agent authority and safety boundaries.
- `CLAUDE.md`: durable behavioural invariants and learned traps, never current
  code inventory, version lists, or counts.
- `docs/WORK-STATE.md`: current requested outcomes, unresolved decisions,
  delivery evidence and the next handoff. Dated state, not a second rulebook.
- `docs/` and `sources/`: specifications and deliberate design decisions.
- `graphify-out/wiki/`: generated navigation, not durable memory or proof of a
  cross-file flow.
- Serena memory: investigation notes only. Promote durable facts to the proper
  tracked document instead of maintaining competing truths.

## Shared roles

Use the [development skill](.agents/skills/snipersight-development/SKILL.md)
and its [role contract](.agents/skills/snipersight-development/references/agent-roles.md)
for task-specific trading, product-design and engineering perspectives. Codex
and Claude use the same definitions. Roles share this authority and the work
ledger; they do not establish separate personas, permissions or memories.

## Continuity between sessions

Before substantive project work, read `docs/WORK-STATE.md` with `CLAUDE.md`.
Reconcile the relevant item against the latest user request and current source;
a backlog entry does not authorize unrelated work or override newer direction.
Use `.agents/skills/snipersight-continuity/SKILL.md` when resuming work,
recording a material user correction, or preparing a handoff.

Update the existing work item when scope, evidence, decisions or status change,
and before a substantial task ends or context is handed off. Preserve the
requested outcome and state what remains unfinished. Keep implementation,
verification, activation and commit/push status distinct when relevant. Mark
an outcome complete only with evidence in the requested operating context;
research, a chart or passing tests alone do not establish active account behavior.
Store stable lessons once in `CLAUDE.md`; keep current results in the work ledger
or a linked dated report. Re-read shared files before patching another session's
state. Do not turn every conversation into another instruction or transcript.

## What this file used to say

It bootstrapped the **Apex** persona system: read `foundation.md`, resolve a
persona from `personas/`, load that persona's memory, and only then start
project work. Apex was a separate project that happened to share this working
directory; its files (`foundation.md`, `personas/`) were removed on 2026-08-07
and live only in git history.

That version also forbade writing to Claude Code's own memory store. That rule
belonged to Apex's single-memory-system policy and does not apply here.
