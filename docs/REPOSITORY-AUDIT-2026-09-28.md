# SniperSight 3.1 repository audit and conservative cleanup

Audited baseline: `acc579f6e8e481839c98dc84d49659f767db2a96` on
`NobleWolf412/snipersight3.1/main`. Work is isolated on
`codex/repository-audit-cleanup`. This is a source/scratch-runtime audit, not
an inspection or activation of the operator's Windows installation.

## Result

The repository already has one shared scanner engine roster. Most apparently
duplicate systems are separate account/research domains or supported UI/API
interfaces. No complete module met the required deletion proof. The cleanup
removes six unreachable lines in one lifecycle projection function and fixes
misleading architecture documentation. It preserves playbooks, thresholds,
scoring, confirmation, rejection, risk, routing, alerts, API payloads and
algorithm versions. No new research system is implemented.

All **858 tracked baseline paths** are classified in
[REPOSITORY-INVENTORY.md](REPOSITORY-INVENTORY.md): **165 ACTIVE**, **690
SUPPORT**, **3 LEGACY / QUARANTINE historical documents**, and **0 DEAD whole
files**. File classification does not assert every contained function is
called, nor that a runtime mode is enabled. The local unreachable branches are
the only DEAD code approved for removal.

## Production architecture

The detailed [source-of-truth map](PRODUCTION-ARCHITECTURE.md) covers startup,
data, indicators, structure, BOS/CHoCH, liquidity, zones/order blocks, FVG,
HTF/BTC context, playbooks, confirmation, rejection, risk, APIs, frontend,
alerts, execution, workers and existing research.

The actual flow is:

1. `start.bat` launches `watchdog.py`, which supervises `live.py` and the
   FastAPI server. `live.main/cycle` owns scheduling and the scan cutoff.
2. Universe/feed-pin logic selects markets; importer/adapters fetch closed
   candles/funding; aggregator builds higher timeframes.
3. `pipeline.run_symbol` applies data gates and the shared priority roster.
   Confirmed swing/structure/zone/liquidity/regime facts feed `setups.py`.
4. `setups.py` owns pullback/reversal selection, confirmation and rejection.
   Registry metadata is not a competing evaluator. Candidate quality ordering
   is separately owned by `opportunities._quality/rank` and used by dispatch.
5. Account settlement precedes `riskpaper.run`. Private custody monitoring,
   reconciliation and protection run when required. `live.cycle` enforces the
   entry deadline before `autotrader.run` dispatches domain-specific READY
   candidates through `execution.Coordinator`.
6. Deferred roster work, research collection, pinned replay resolution, forward
   studies, replay risk, quality audit, retention and daily regrading follow.
7. API read models expose stored/derived authoritative values to the default
   cockpit and retained classic UI. Scanner alert decisions enter a durable
   queue; the watchdog performs configured delivery.

This checkout uses static JavaScript, not React. Market/exchange adapters are
bespoke Python, not CCXT. Research order blocks are distinct from production
supply/demand zones. BTC alignment research is not a hard BTC impulse scanner
gate. No direct Telegram Bot API adapter was found; generic webhooks are not
proof of native Telegram support. Private Phemex implementation exists, but
mainnet routing remains build-locked.

## Audit method and reference coverage

- Inventoried every tracked file, including dot-directory agent/CI tooling,
  build/configuration files, fixtures, tests, docs and generated navigation.
  Excluded ignored dependencies, runtime stores and other repositories from
  cleanup. No operator credentials or account data were required.
- Read repository instructions, current work ledger, canonical role contract,
  generated wiki index and relevant source. Wiki build `eb591d23adff` is older
  than the audited HEAD and was not treated as execution proof or regenerated
  by hand.
- Built an AST import-reference map across 122 non-test application Python
  files. The scanner/API/supervisor root closure reaches 102 modules, including
  conditional/support paths. Reviewed outside-closure modules as CLI/research
  support rather than calling them dead.
- Traced `PER_SYMBOL` and its phase partition, strategy/version registries,
  `prune.current_versions` string imports, engine-source version scanning,
  source-constant diagnostics, FastAPI decorators/router inclusion/static
  mounts, JavaScript endpoint strings, HTML/CSS asset references, CLI scripts,
  watchdog subprocesses, autostart, PowerShell tooling and CI/test discovery.
- Checked environment/configuration references: bridge token/mode, allowed
  users, Citadel endpoints, toast controls, settings defaults/coercion and
  alert configuration. Generic catalogue/settings enumeration and external
  callers prevent deletion of a key merely because a literal read is absent.
- Filename search found no tracked old/backup/copy/new/final/fixed/v2/v3
  candidates under delimiter-based matching. Byte hashes found no identical
  Python/JavaScript/HTML/CSS file pairs. Neither check proves semantic uniqueness.
- Independent read-only backend and frontend/API reviews challenged apparent
  duplicates. A final code/architecture review found no behavior regression;
  its deadline-ownership, ranking-authority and Unicode inventory corrections
  were applied.

This is not a claim that every branch, private venue or external consumer has
been exercised. Absence of evidence was handled by retention, not deletion.

## Removed code

| Item | What it did | Replacement / reachability proof | Verification |
|---|---|---|---|
| Three two-line terminal-state branches in `app/engine/opportunities.py:lifecycle` | Returned CANCELLED, EXPIRED or REJECTED | An earlier unconditional membership branch already returns `OpportunityState(state)` for exactly those values. `state` is not reassigned between them, so the removed branches cannot execute | Old/new function comparison over 715 combinations; focused opportunity/scanner/API/version tests; executable AST comparison; final repository checks |

No file, module, migration, configuration key, route, frontend asset, test or
historical fact was deleted. No replacement trading logic was introduced. No
version bump is needed because executable behavior is unchanged.

## Quarantined and retained code

No executable module was physically moved to an archive. Moving reachable
classic assets, API handlers or research helpers would itself change behavior.
The isolated cleanup branch and Git history are the recovery mechanism; no
duplicate archive tree was introduced into runtime discovery.

The following historical documents are policy-quarantined **in place**:

- `docs/REDESIGN-PLAN.md`
- `docs/PRODUCT-REVIEW-2026-07-29.md`
- `docs/SALVAGE-from-snipersight-trading.md`

Their provenance/links remain intact. `AGENTS.md` and the docs index state that
legacy/historical material is not an implementation reference unless explicitly
requested. Other dated reports remain SUPPORT evidence, not current authority.

| Suspicious item | Classification and reason retained | Requirement before removal |
|---|---|---|
| Classic shell and linked assets | ACTIVE: `/classic` explicitly serves the rollback UI | Retire that supported surface and review bookmarks/assets/contracts |
| Unversioned API beside `/api/ui/v1` | ACTIVE: classic consumers and default cockpit actions still use it | Trace each endpoint and external-client contract; migrate callers explicitly |
| Apex bridge / console / raw redirect / bridge launcher | ACTIVE conditional or SUPPORT entrypaths, not the removed persona project | Explicit retirement of those integrations/compatibility contracts |
| CLI research modules outside scanner import closure | SUPPORT: intentional CLI, tests, grading and shared-helper consumers | Establish experiment provenance and downstream helper consumers; absence from scanner imports is insufficient |
| `execsim`, replay risk, manual namespaces and historical versions | ACTIVE: distinct replay/account/manual domains and retained order ownership | Domain/version migration with open-order and record-integrity evidence; outside cleanup scope |
| Tests under `app/tests`, verification fixtures and scripts | SUPPORT: explicit discovery/harness/CLI contracts | Demonstrate replacement coverage and no workflow dependency |
| Generated wiki and old audits | SUPPORT navigation/provenance, with explicit freshness limits | Regenerate using supported tooling or retire links; do not hand-edit generated knowledge |

## Duplicate systems found

| Apparent duplicate | Actual authority / distinction | Action |
|---|---|---|
| Live scanner, backfill and ingest runners | One `pipeline.PER_SYMBOL/run_symbol`; wrappers have different orchestration duties | Documented, retained |
| Two `execsim` entries | Second pass resolves scale-ins emitted between passes | Documented, retained |
| `risk.py` and `riskpaper.py` | Shared sizing plus replay risk versus actual paper-account risk | Documented, retained |
| `execsim.py` and `execution.py` | Replay/shared math versus durable account routing/monitoring | Documented, retained |
| `zones.py` and research order blocks | Different detector definitions and evidence domains | Documented, retained |
| Regime, phase, chart-window and HTF readers | Different questions; playbook policy decides gate use | Documented, retained |
| Setup lifecycle and `lifecycle.py` | Candidate confirmation/projection versus private protective orders | Documented; only local unreachable branches removed |
| Setup confluence rank and opportunity quality | Legacy setup score versus current candidate ordering; neither is a probability/performance grade | Documented, unchanged |
| Default cockpit and classic shell | Two supported routes sharing server/account authorities | Documented, unchanged |
| Registry evaluator-looking metadata | Catalogue includes planned/measured entries; production mechanics stay in `setups.py` | Documented, unchanged |

One redundant `venues` import remains in `server.py`; it is harmless and not a
competing implementation. No broad import reformatting was mixed into cleanup.

## Changes made

- Added the architecture map and full baseline inventory.
- Updated `AGENTS.md` with AUTHORITATIVE PRODUCTION PATH, LEGACY CODE POLICY,
  PLAYBOOK POLICY and RESEARCH BOUNDARY, preserving existing safety/role rules.
- Replaced stale README startup/test/architecture claims and historical runtime
  counts with verified source navigation. Corrected the docs index's obsolete
  claims that retention was unimplemented.
- Corrected comments/docstrings describing validation at touch, a read-only
  server, default-enabled toast and unscheduled regrading. The old registry
  `gap` string is left byte-for-byte unchanged because it is API/UI output;
  a comment identifies its historical wording.
- Removed the six unreachable lifecycle lines above.
- Recorded this outcome in the shared work ledger without closing or activating
  unrelated trading work.

## Verification

Performed in a fresh isolated Linux checkout with no operator store, credentials
or supervised application attached. Core test dependencies were installed in a
separate Python 3.12 virtual environment; npm dependencies came from the lockfile.
The existing restart test stubs the protected process effect when opening its
guard, and manual-arm/API fixtures redirect connections to scratch databases.

| Check | Result |
|---|---|
| Baseline full Python suite | 2,149 passed; 20 skipped; 230 subtests passed |
| Baseline JavaScript / lint | All 40 Node contract suites passed; ESLint passed |
| Cleanup group 1: lifecycle equivalence | 715 combinations of setup/risk/custody inputs match baseline |
| Cleanup group 1: focused verification | 58 passed; 11 subtests passed (opportunities, live clock, roster, default route, cockpit API, version cascade) |
| Final full Python suite | 2,149 passed; 20 skipped; 230 subtests passed (271.55 seconds) |
| Final JavaScript / lint | All 40 Node contract suites passed; ESLint passed |
| Backend/scanner imports and registry wiring | Server/live/backfill imported; live and ingest use the same roster; backfill resolves the same ordered modules |
| Configuration loading | All 15 declared settings defaults load; mainnet routing flag remains false; operator secrets/configuration were not loaded |
| API contract | Full OpenAPI document equals baseline; 96 paths unchanged |
| Actual backend startup | Uvicorn scratch harness completed startup; HTTP 200 for `/`, `/classic`, `/api/ui/v1/context`, `/openapi.json` |
| Frontend assets | All 42 linked default/classic static resources returned HTTP 200 |
| Frontend build | Not applicable: static frontend explicitly has no build script/runtime npm dependencies |
| Executable source comparison | All changed Python ASTs unchanged after excluding docstrings and exactly the three proven-dead branches |
| Syntax / source hygiene | Python compilation, 359-file UTF-8/control-byte scan and `git diff --check` passed |

PowerShell is unavailable here, so Windows-specific `preflight.ps1` and
`check.ps1` were inspected and equivalent available checks run directly.
No claim is made that Windows task supervision, DPAPI, toast delivery, real
exchange connectivity, private account routing or a full live market scan ran.
Scanner startup/import and mocked-cycle contracts were verified; the actual
account was not started or restarted. Rendered Playwright interactions were
not rerun because no frontend assets or wire payloads changed. Source-contract
and HTTP checks do not claim rendered-browser coverage.

An initial HTTP attempt across separate tool sessions could not reach the
scratch listener. Launching and checking the harness within one process tree
resolved that environment limitation; the successful checks above use that
isolated server, which was then terminated. The test dependency stack emits
one Starlette/httpx deprecation warning; it is not a test failure.
The 20 skips are 8 Windows-only checks (DPAPI/process inspection) and 12
checks requiring recorded market/account facts absent from the scratch store.
They are verification gaps, not evidence that related code is unused.

## Remaining technical debt

1. Research lives under `app/engine` and still shares scanner scheduling.
   Physical separation needs a deliberate migration, not filename cleanup.
2. The supported classic UI and unversioned API increase maintenance surface.
   They need an explicit retirement/migration decision before deletion.
3. The generated graph/wiki is stale and some article titles are misleading.
   Regenerate with the real graph tool; the new source map is the audit guide.
4. Historical headers, dated design proposals and registry display copy retain
   old claims. The guide identifies precedence; API copy edits remain outside
   this unchanged-output cleanup.
5. Some GET handlers (`/api/manual/open`, `/api/manual/live`) can settle manual
   paper orders. Do not treat HTTP GET alone as proof that a test is read-only.
6. CLI experiments contain helpers shared by later studies. Isolating them
   requires helper ownership review, not deleting old-looking filenames.
7. No full external-client inventory, Windows runtime validation or private
   exchange smoke test was available. These gaps constrain future retirement.

## Strategy-Lab readiness

The source boundaries are now explicit. Future `research/` adapters can read
closed candles, immutable/versioned facts, playbook contracts and setup-time
snapshots, reuse established execution/cost math, and write isolated candidate
and study results. Existing forward studies/regrade/read models are integration
references. Production playbooks must never be overwritten automatically;
candidate strategies require explicit promotion. No TraderDev, TradingKit,
optimizer, worker migration or new backtester was implemented.

## Delivery

Cleanup committed locally as `3969b6e` on the isolated branch. Automatic
approval review initially blocked publication pending explicit authorization.
The user authorized publishing this branch and opening a draft PR on
2026-09-28. Publication uses the connected GitHub integration because the
command-line checkout has no GitHub push credentials. See the review branch
and task handoff for remote commit/PR identity; connector publication preserves
the reviewed file tree but may use a different commit identity. No merge,
deployment, strategy promotion or operator process restart is part of this audit.
