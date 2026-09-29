# Repository inventory at the audit baseline

Baseline: `acc579f6e8e481839c98dc84d49659f767db2a96` (2026-09-28 audit).
Every path from `git ls-files` at that revision is included below. Newly added
architecture/audit/inventory documents are SUPPORT and are not counted in the
baseline. Runtime databases, credentials, ignored dependencies and other
checkouts are outside the tracked inventory and were not cleanup targets.

Classification applies to the file's retained role, not every function inside
it. ACTIVE includes conditional routes, compatibility UIs and scheduled
research, **not** a claim that a study may trade or that an operator enabled a
mode. SUPPORT includes CLI tools, tests and historical evidence. Import closure
is navigation evidence only; explicit runtime/string/registry/CLI checks and
retention decisions are described in the audit. DEAD is reserved for the
proven unreachable branches recorded there; no entire file earned that label.
LEGACY / QUARANTINE documents remain at their original paths to preserve links,
with policy quarantine against use as implementation authority.

Baseline counts: **165 ACTIVE**, **3 LEGACY / QUARANTINE**, **690 SUPPORT**; **858 total**.

| Path | Classification | Reference / retention evidence |
|---|---|---|
| ``.agents/skills/snipersight-continuity/SKILL.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.agents/skills/snipersight-continuity/agents/openai.yaml`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.agents/skills/snipersight-development/SKILL.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.agents/skills/snipersight-development/agents/openai.yaml`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.agents/skills/snipersight-development/references/agent-roles.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/agents/architect.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/agents/auditor.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/agents/contrarian.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/agents/implementer.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/agents/product-designer.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/agents/trading-analyst.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/codex-consult.enabled`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/hooks/consult-codex.ps1`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/skills/snipersight-continuity/SKILL.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.claude/skills/snipersight-development/SKILL.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.gitattributes`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.github/workflows/ci.yml`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.gitignore`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.impeccable/critique/2026-08-05T00-10-27Z__app-static-shell-html.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.impeccable/critique/2026-08-05T10-57-16Z__app-static-shell-html.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.impeccable/critique/2026-08-05T18-08-40Z__app-static-shell-html.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.impeccable/critique/2026-08-06T00-03-42Z__app-static-shell-html.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.serena/.gitignore`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.serena/memories/investigations/continuity-entrypoint.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``.serena/project.yml`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``AGENTS.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``CLAUDE.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``PRODUCT.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``README.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/BUILDLOG.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/backfill.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `README.md`, `app/BUILDLOG.md`, `app/engine/quality.py`, `app/tests/test_quality_one_verdict.py`. |
| ``app/calibrate.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/BUILDLOG.md`, `app/server.py`. |
| ``app/engine/abtest.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/regrade.py`, `app/engine/strategygrade.py`, `app/engine/trailexit.py`, `app/engine/trendslice.py`. |
| ``app/engine/achievements.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/aggregator.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/backfill.py`, `app/engine/ingest.py`, `app/engine/quality.py`, `app/engine/volume.py`, `app/live.py`. |
| ``app/engine/analysis_cache.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`. |
| ``app/engine/analyst_context.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/chart_insight.py`, `app/engine/copilot.py`, `app/server.py`. |
| ``app/engine/apexbridge.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/automation.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/autotrader.py`, `app/engine/broker_factory.py`, `app/engine/execution.py`, `app/engine/phemex_private.py`, `app/engine/positions.py`. |
| ``app/engine/autotrader.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`. |
| ``app/engine/basis.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/pipeline.py`. |
| ``app/engine/bias.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analyst_context.py`, `app/engine/breakout.py`, `app/engine/chartread.py`, `app/engine/htfcontext.py`, `app/engine/htfread.py`. |
| ``app/engine/binance.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/basis.py`, `app/engine/importer.py`. |
| ``app/engine/breakout.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/forwardtrial.py`, `app/engine/market_context.py`, `app/engine/pipeline.py`, `app/engine/regrade.py`, `app/engine/strategygrade.py`. |
| ``app/engine/broker_factory.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`, `app/server.py`. |
| ``app/engine/btcalign.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/engine/bias.py`, `app/engine/divstats.py`, `app/engine/factorgrade.py`, `app/engine/fvg.py`. |
| ``app/engine/chart_insight.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/chartread.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analyst_context.py`, `app/engine/chart_insight.py`, `app/engine/htfcontext.py`, `app/engine/setups.py`. |
| ``app/engine/contextgrade.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: module CLI/docstring and retained support role. |
| ``app/engine/contracts.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/achievements.py`, `app/engine/automation.py`, `app/engine/autotrader.py`, `app/engine/broker_factory.py`, `app/engine/diagnostics.py`. |
| ``app/engine/cooldowns.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/factorstats.py`, `app/engine/paperbook.py`, `app/engine/pipeline.py`, `app/engine/risk.py`, `app/engine/riskpaper.py`. |
| ``app/engine/copilot.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/costs.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/abtest.py`, `app/engine/breakout.py`, `app/engine/entrystats.py`, `app/engine/episodes.py`, `app/engine/execsim.py`. |
| ``app/engine/credentials.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/broker_factory.py`, `app/engine/stocks.py`, `app/server.py`. |
| ``app/engine/cycles.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/pipeline.py`, `app/server.py`. |
| ``app/engine/diagnostic_status.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/copilot.py`, `app/server.py`. |
| ``app/engine/diagnostics.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/telemetry.py`. |
| ``app/engine/divstats.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/factorgrade.py`. |
| ``app/engine/draft.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/copilot.py`, `app/engine/nearlevels.py`, `app/server.py`. |
| ``app/engine/driftfade.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Import consumers: `app/engine/htfread.py`. |
| ``app/engine/edgestats.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/abtest.py`, `app/engine/factorgrade.py`, `app/engine/funding.py`, `app/engine/livegate.py`, `app/engine/strategygrade.py`. |
| ``app/engine/entrystats.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Import consumers: `app/engine/htfread.py`. |
| ``app/engine/episodes.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/tests/test_episodes.py`. |
| ``app/engine/execsim.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/abtest.py`, `app/engine/cooldowns.py`, `app/engine/edgestats.py`, `app/engine/episodes.py`, `app/engine/execution.py`. |
| ``app/engine/execution.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/autotrader.py`, `app/engine/paperbook.py`, `app/engine/positions.py`, `app/engine/quality.py`, `app/engine/shared_account.py`. |
| ``app/engine/factorgrade.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/factorstats.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/btcalign.py`, `app/engine/chartread.py`, `app/engine/contextgrade.py`, `app/engine/divstats.py`, `app/engine/driftfade.py`. |
| ``app/engine/forwardtrial.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/stopstudy.py`, `app/engine/zonestudy.py`, `app/live.py`, `app/ui_api.py`. |
| ``app/engine/funding.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`. |
| ``app/engine/fvg.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/factorgrade.py`, `app/engine/pipeline.py`, `app/server.py`. |
| ``app/engine/htfcontext.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/setup_guide.py`. |
| ``app/engine/htfread.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/tests/test_htfread.py`, `docs/INTELLIGENCE-REVIEW-2026-09-05.md`. |
| ``app/engine/ignition.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Import consumers: `app/engine/contextgrade.py`, `app/engine/driftfade.py`, `app/engine/episodes.py`. |
| ``app/engine/importer.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/backfill.py`, `app/engine/abtest.py`, `app/engine/aggregator.py`, `app/engine/analyst_context.py`, `app/engine/chartread.py`. |
| ``app/engine/ingest.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/pipeline.py`, `app/live.py`. |
| ``app/engine/kraken.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/funding.py`, `app/engine/importer.py`, `app/engine/listings.py`, `app/engine/universe.py`. |
| ``app/engine/learning.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/lifecycle.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/positions.py`, `app/live.py`. |
| ``app/engine/liquidity.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/breakout.py`, `app/engine/draft.py`, `app/engine/episodes.py`, `app/engine/htfcontext.py`. |
| ``app/engine/listings.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/quality.py`, `app/live.py`. |
| ``app/engine/livegate.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`, `app/ui_api.py`. |
| ``app/engine/ma.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/analyst_context.py`, `app/engine/factorgrade.py`, `app/engine/fvg.py`, `app/engine/momentum.py`. |
| ``app/engine/macro_calendar.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/marketpulse.py`, `app/server.py`. |
| ``app/engine/manual.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/copilot.py`, `app/engine/opportunities.py`, `app/engine/paperbook.py`, `app/engine/pipeline.py`, `app/engine/quality.py`. |
| ``app/engine/market_context.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/contextgrade.py`, `app/engine/trendslice.py`, `app/server.py`. |
| ``app/engine/marketdata.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`, `app/server.py`. |
| ``app/engine/marketpulse.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/ui_api.py`. |
| ``app/engine/momentum.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/analyst_context.py`, `app/engine/divstats.py`, `app/engine/pipeline.py`, `app/engine/research.py`. |
| ``app/engine/nearlevels.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/engine/open_interest.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/diagnostic_status.py`, `app/live.py`, `app/server.py`, `app/ui_api.py`. |
| ``app/engine/opportunities.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/autotrader.py`, `app/server.py`, `app/ui_api.py`. |
| ``app/engine/paperbook.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/riskpaper.py`, `app/engine/shared_account.py`, `app/server.py`. |
| ``app/engine/phemex.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/funding.py`, `app/engine/importer.py`, `app/engine/listings.py`, `app/engine/marketdata.py`, `app/engine/open_interest.py`. |
| ``app/engine/phemex_private.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/broker_factory.py`, `app/engine/execution.py`. |
| ``app/engine/pipeline.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/backfill.py`, `app/engine/ingest.py`, `app/engine/regrade.py`, `app/live.py`, `app/server.py`. |
| ``app/engine/positions.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/execution.py`, `app/engine/lifecycle.py`, `app/live.py`, `app/server.py`, `app/watchdog.py`. |
| ``app/engine/profit_protection.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/autotrader.py`, `app/engine/execution.py`, `app/engine/positions.py`. |
| ``app/engine/quality.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/backfill.py`, `app/engine/apexbridge.py`, `app/engine/pipeline.py`, `app/engine/risk.py`, `app/live.py`. |
| ``app/engine/ranges.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/factorgrade.py`, `app/engine/htfread.py`, `app/engine/ma.py`, `app/engine/pipeline.py`. |
| ``app/engine/rebuild.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/regrade.py`, `app/server.py`. |
| ``app/engine/regime.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/bias.py`, `app/engine/breakout.py`, `app/engine/btcalign.py`, `app/engine/episodes.py`. |
| ``app/engine/regimefresh.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `CLAUDE.md`. |
| ``app/engine/regimeread.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analyst_context.py`, `app/engine/htfcontext.py`, `app/engine/htfread.py`, `app/engine/setups.py`. |
| ``app/engine/registry.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/breakout.py`, `app/engine/opportunities.py`, `app/engine/setups.py`, `app/server.py`. |
| ``app/engine/regrade.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`. |
| ``app/engine/research.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/chart_insight.py`, `app/engine/open_interest.py`, `app/engine/pipeline.py`, `app/engine/researchsignals.py`. |
| ``app/engine/researchsignals.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/pipeline.py`, `app/engine/research.py`, `app/server.py`, `app/ui_api.py`. |
| ``app/engine/risk.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/backfill.py`, `app/engine/apexbridge.py`, `app/engine/autotrader.py`, `app/engine/copilot.py`, `app/engine/diagnostics.py`. |
| ``app/engine/riskpaper.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/opportunities.py`, `app/live.py`, `app/server.py`. |
| ``app/engine/runlog.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/aggregator.py`, `app/engine/basis.py`, `app/engine/binance.py`, `app/engine/breakout.py`, `app/engine/cooldowns.py`. |
| ``app/engine/scalein.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/abtest.py`, `app/engine/apexbridge.py`, `app/engine/entrystats.py`, `app/engine/execsim.py`, `app/engine/pipeline.py`. |
| ``app/engine/sessions.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/pipeline.py`. |
| ``app/engine/settings.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/automation.py`, `app/engine/autotrader.py`, `app/engine/lifecycle.py`, `app/engine/livegate.py`, `app/engine/positions.py`. |
| ``app/engine/setups.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/abtest.py`, `app/engine/analysis_cache.py`, `app/engine/apexbridge.py`, `app/engine/breakout.py`, `app/engine/chart_insight.py`. |
| ``app/engine/shared_account.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/execution.py`, `app/engine/manual.py`, `app/engine/paperbook.py`, `app/engine/riskpaper.py`, `app/server.py`. |
| ``app/engine/sidegovernor.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/tests/test_sidegovernor.py`, `docs/INTELLIGENCE-REVIEW-2026-09-05.md`. |
| ``app/engine/simpletrial.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`, `app/ui_api.py`. |
| ``app/engine/snapshot.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/BUILDLOG.md`. |
| ``app/engine/stockcalendar.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/stockdemo.py`, `app/engine/stocks.py`. |
| ``app/engine/stockdemo.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/stocks.py`, `app/server.py`, `app/ui_api.py`. |
| ``app/engine/stocks.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`, `app/ui_api.py`. |
| ``app/engine/stockstore.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/stocks.py`. |
| ``app/engine/stopstudy.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`, `app/ui_api.py`. |
| ``app/engine/store.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/backfill.py`, `app/calibrate.py`, `app/engine/abtest.py`, `app/engine/analysis_cache.py`, `app/engine/analyst_context.py`. |
| ``app/engine/strategygrade.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/tests/test_strategy_grade.py`. |
| ``app/engine/structure.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/calibrate.py`, `app/engine/analysis_cache.py`, `app/engine/bias.py`, `app/engine/breakout.py`, `app/engine/ignition.py`. |
| ``app/engine/studycohort.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/forwardtrial.py`, `app/engine/stopstudy.py`, `app/engine/zonestudy.py`. |
| ``app/engine/swings.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/calibrate.py`, `app/engine/abtest.py`, `app/engine/analysis_cache.py`, `app/engine/breakout.py`, `app/engine/chartread.py`. |
| ``app/engine/telemetry.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/paperbook.py`, `app/server.py`. |
| ``app/engine/tradevisuals.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/ui_api.py`. |
| ``app/engine/trailexit.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `docs/INTELLIGENCE-REVIEW-2026-09-05.md`. |
| ``app/engine/trend.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/pipeline.py`, `app/engine/regrade.py`, `app/engine/simpletrial.py`, `app/engine/strategygrade.py`, `app/engine/trailexit.py`. |
| ``app/engine/trendslice.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Import consumers: `app/engine/trailexit.py`. |
| ``app/engine/universe.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/abtest.py`, `app/engine/apexbridge.py`, `app/engine/chartread.py`, `app/engine/cycles.py`, `app/engine/edgestats.py`. |
| ``app/engine/venues.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/basis.py`, `app/engine/chartread.py`, `app/engine/copilot.py`, `app/engine/costs.py`, `app/engine/credentials.py`. |
| ``app/engine/volatility.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/analyst_context.py`, `app/engine/execution.py`, `app/engine/factorgrade.py`, `app/engine/market_context.py`. |
| ``app/engine/volprofile.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/factorgrade.py`, `app/engine/pipeline.py`, `app/server.py`. |
| ``app/engine/volume.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/analyst_context.py`, `app/engine/factorgrade.py`, `app/engine/pipeline.py`, `app/server.py`. |
| ``app/engine/zones.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/analysis_cache.py`, `app/engine/chartread.py`, `app/engine/draft.py`, `app/engine/episodes.py`, `app/engine/htfread.py`. |
| ``app/engine/zonestudy.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`, `app/ui_api.py`. |
| ``app/eslint.config.mjs`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/fixtures/stocks/training_v1.json`` | ACTIVE | stockdemo.py bundled synthetic workspace dataset; never evidence of live market performance. |
| ``app/install_autostart.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/BUILDLOG.md`, `docs/MOBILE-PLAN.md`. |
| ``app/live.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/notify.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`, `app/watchdog.py`. |
| ``app/orphans.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: module CLI/docstring and retained support role. |
| ``app/package-lock.json`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/package.json`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/playwright.config.cjs`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/prune.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/live.py`. |
| ``app/reset_baseline.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `PRODUCT.md`, `README.md`. |
| ``app/server.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/engine/apexbridge.py`. |
| ``app/setup_guide.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/ui_api.py`. |
| ``app/start.bat`` | ACTIVE | Documented production launcher; invokes watchdog child supervision. |
| ``app/start_bridge.bat`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/static/app-mobile.css`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/assets/icon-192.png`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit.html`, `app/static/shell.html`. |
| ``app/static/assets/icon-512-maskable.png`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: static mount plus asset URLs/manifest; retain externally addressable asset. |
| ``app/static/assets/icon-512.png`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: static mount plus asset URLs/manifest; retain externally addressable asset. |
| ``app/static/assets/snipersight-logo.png`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/assets/strategies/README.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/static/assets/strategies/pullback.jpg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/strategies/README.md`. |
| ``app/static/assets/strategies/reversal.jpg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/strategies/README.md`, `app/static/cockpit/app.js`. |
| ``app/static/assets/ui/INTER-LICENSE.txt`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/static/assets/ui/LUCIDE-LICENSE.txt`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/static/assets/ui/README.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/static/assets/ui/book-open.svg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.html`. |
| ``app/static/assets/ui/chart-candlestick.svg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.html`. |
| ``app/static/assets/ui/flask-conical.svg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.html`. |
| ``app/static/assets/ui/house.svg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.html`. |
| ``app/static/assets/ui/inter-500.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.css`. |
| ``app/static/assets/ui/inter-600.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.css`. |
| ``app/static/assets/ui/radar.svg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.html`, `app/static/cockpit/app.js`. |
| ``app/static/assets/ui/settings-2.svg`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/assets/ui/README.md`, `app/static/cockpit.html`. |
| ``app/static/chart-insight.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/chart.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/server.py`, `app/static/confirm-dialog.js`, `app/static/copilot.js`, `app/static/shell.html`. |
| ``app/static/cockpit-workspaces.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/cockpit.css`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit.html`. |
| ``app/static/cockpit.html`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/server.py`. |
| ``app/static/cockpit/app.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit.html`. |
| ``app/static/cockpit/state.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit/app.js`. |
| ``app/static/confirm-dialog.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/copilot.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/chart.js`, `app/static/funnel.js`, `app/static/shell.html`, `app/static/ss.css`. |
| ``app/static/diagnostic-status.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/diagnostics-ui.css`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/confirm-dialog.js`, `app/static/funnel.js`, `app/static/ss.css`, `app/static/tracer.js`. |
| ``app/static/diagnostics.css`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/diagnostics.html`. |
| ``app/static/diagnostics.html`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/diagnostics.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/diagnostics.html`. |
| ``app/static/edgeview.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/glossary.js`, `app/static/shell.html`. |
| ``app/static/factor-evidence.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/fonts/inter-400.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit.css`, `app/static/ss.css`. |
| ``app/static/fonts/jetbrains-400.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/ss.css`. |
| ``app/static/fonts/jetbrains-600.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/ss.css`. |
| ``app/static/fonts/jetbrains-800.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/ss.css`. |
| ``app/static/fonts/share-tech-mono.woff2`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: static mount plus asset URLs/manifest; retain externally addressable asset. |
| ``app/static/funnel.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/chart.js`, `app/static/cockpit-workspaces.js`, `app/static/confirm-dialog.js`, `app/static/diagnostics-ui.css`. |
| ``app/static/glossary.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`, `app/static/shell.js`, `app/static/weather.js`. |
| ``app/static/lightweight-charts.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit.html`, `app/static/shell.html`. |
| ``app/static/macro-calendar.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/manifest.webmanifest`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/server.py`, `app/static/cockpit.html`, `app/static/shell.html`. |
| ``app/static/markets.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/chart.js`, `app/static/shell.html`. |
| ``app/static/mode-control.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/operations.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`, `app/static/shell.js`. |
| ``app/static/opportunities.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/opportunity-ui.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/research-chart.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/shell.html`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/server.py`, `app/static/funnel.js`, `app/static/shell.js`, `app/static/ss.css`. |
| ``app/static/shell.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/chart.js`, `app/static/diagnostics-ui.css`, `app/static/edgeview.js`, `app/static/funnel.js`. |
| ``app/static/signal-map.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/cockpit.html`, `app/static/shell.html`. |
| ``app/static/ss.css`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/app-mobile.css`, `app/static/chart.js`, `app/static/confirm-dialog.js`, `app/static/diagnostics-ui.css`. |
| ``app/static/ssdata.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/chart.js`, `app/static/shell.html`, `app/static/shell.js`, `app/static/ss.css`. |
| ``app/static/stocks.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/ticket-math.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/server.py`, `app/static/chart.js`, `app/static/edgeview.js`, `app/static/shell.html`. |
| ``app/static/tracer.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/confirm-dialog.js`, `app/static/diagnostics-ui.css`, `app/static/funnel.js`, `app/static/shell.html`. |
| ``app/static/trade-workspace.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`. |
| ``app/static/weather.css`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/weather.js`. |
| ``app/static/weather.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/glossary.js`, `app/static/shell.html`, `app/static/shell.js`, `app/static/ssdata.js`. |
| ``app/static/wheel.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`, `app/static/shell.js`. |
| ``app/static/wizard.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/confirm-dialog.js`, `app/static/diagnostics-ui.css`, `app/static/funnel.js`, `app/static/shell.html`. |
| ``app/static/workspaces.js`` | ACTIVE | Served static namespace; default/classic/diagnostics UI or its assets. Reference: `app/static/shell.html`, `app/static/shell.js`. |
| ``app/tests/__init__.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/cockpit.spec.cjs`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/cockpit_preview.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_abtest.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_account_gates_reach_every_surface.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_account_hero.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_achievements.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_action_feedback.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_alerts.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_analysis_cache.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_analyst_context.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_api_telemetry.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_app_mobile.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_arm_from_a_phone.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_armed_order.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_audit_cache.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_audit_closeout.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_audit_log.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_auto_prune.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_automation_execution.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_autonomy_contracts.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_autotrader.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_bias.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_boundary_wake.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_broker_factory.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_btcalign.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_candle_cache.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_chart_insight.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_chart_insight.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_chart_layers.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_chart_load_parallel.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_chartread.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cockpit_api.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cockpit_diagnostics.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cockpit_redesign.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cockpit_state.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cold_start.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_confirmation_lifecycle.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_context_policy.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_contextgrade.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_controlled_learning.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cooldowns.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_copilot.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_copilot_dock.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_core_hardening.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_credentials.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cross_fill_honesty.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_cycle_lede.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_default_cockpit_route.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_diagnostic_status.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_diagnostic_status.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_diagnostics.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_divstats.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_draft.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_driftfade.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_edgestats.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_edgeview_render.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_empty_state_honesty.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_engine_contracts.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_entrystats.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_episodes.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_era_labels.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_execution_domains.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_execution_parity.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_execution_rebuild.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_factor_evidence_contract.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_factorgrade.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_factorstats.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_forwardtrial.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_funding.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_fvg_volprofile.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_health_scope.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_home_trades.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_htfcontext.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_htfread.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ignition.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_kraken_walk.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ledger_field_contract.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_liquidation_contract.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_liquidity_causality.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_live_clock.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_livegate.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_loading_states.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ma.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_macro_calendar.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_macro_calendar.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_manual.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_market_context.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_market_workspaces.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_marketpulse.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_mode_sizing.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_momentum.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_nav_and_affordance.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_near_levels_panel.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_nearlevels.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_nested_cycles.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_next_action.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_next_action.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_notifications.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_onboard_announce.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_one_source_of_truth.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_one_walk.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_opportunities.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_orientation_and_axes.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_outcome_classes.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_overnight_sweep.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_override_survives_version_bump.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_overview_redesign.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_paper_account_surface.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_paper_attempt_end_to_end.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_paper_book.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_permitted.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_phemex.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_phemex_private.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_phone_front_door.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_pipeline_gates.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_pipeline_quality.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_pipeline_roster.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_playbooks.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_position_api.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_position_safety.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_profit_protection.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_prune_facts.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_prune_runs.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_quality_one_verdict.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_quality_plain.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ranges.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_rebuild_note.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_rebuild_status.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_reference_feed.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_regimefresh.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_regimeread.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_registry.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_regrade.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_render_scope.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_research_integration.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_responsive_layout.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_review_findings.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_rules_surface.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_same_side_governor.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_scan_scheduling.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_second_opinion.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_semantics_and_keyboard.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_sessions.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_settings.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_setup_guide.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_setup_trace.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_shadow_venue.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_shared_account.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_shell_structure.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_sidegovernor.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_signal_ui_contract.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_simpletrial.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_spotter_analysis.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ssdata.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_stock_training.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_stocks_foundation.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_stopstudy.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_store_schema.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_strategy_grade.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_studycohort.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_swing_promotion_stability.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_swing_zero_atr.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_system_restart.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_testnet_lifecycle.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_testnet_safety_fixes.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ticket_math.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_toast_isolation.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trade_evidence.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trade_surfaces.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trader_basics.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trader_translation.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_tradevisuals.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trailexit.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trend.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_trendslice.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ui_field_contract.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_ui_read_models.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_universe_coverage.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_venue_costs.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_venue_listings.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_venues.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_version_cascade.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_volatility.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_volume.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_wal_hygiene.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_watchdog_rung_dispatch.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_weather.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_weather_denominator.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_window_policy.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_word_budget.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_your_trades.js`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_zone_anchor_identity.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_zone_causality.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/tests/test_zonestudy.py`` | SUPPORT | Verification support: pytest/Node discovery or explicit Playwright/harness/fixture references; not production startup. |
| ``app/ui_api.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Import consumers: `app/server.py`. |
| ``app/validate.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/BUILDLOG.md`, `docs/WORK-STATE.md`. |
| ``app/verification/golden-btc-1d.json`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/golden-chart-reads-2.json`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/golden-chart-reads.json`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/major-inspection-btc-1d.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/pack-001-swings.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/validation-001-pregate.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/validation-001.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verification/validation-002.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``app/verify_pack.py`` | SUPPORT | CLI, diagnostic or research support outside scanner/API import closure. Entrypoint/reference evidence: `app/BUILDLOG.md`. |
| ``app/watchdog.py`` | ACTIVE | Runtime import/entry path (including conditional/research/API paths). Entrypoint/reference evidence: `AGENTS.md`, `CLAUDE.md`, `README.md`, `app/BUILDLOG.md`, `app/engine/diagnostic_status.py`. |
| ``docs/ADR-001-MARKET-WORKSPACES.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/AUDIT-setup-id-join-hazards.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/AUTONOMY-OPERATIONS.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/BOT-LOSS-AUDIT-2026-09-21.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/CONFIRMATION-LIFECYCLE-FIX.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/CONSISTENCY-PLAN.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/DEFENDED-ZONE-STOP-PLAN.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/DESIGN-QA-2026-08-23.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/DESIGN-SYSTEM.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/FORWARD-BREAKOUT-TRIAL.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/FORWARD-STOP-COMPARISON.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/HARDENING.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/INCIDENT-CAP-DATA-2026-09-15.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/INTELLIGENCE-REVIEW-2026-09-05.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/MOBILE-PLAN.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/OVERHAUL-DELIVERY.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/OVERHAUL-STRUCTURE.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/PRODUCT-REVIEW-2026-07-29.md`` | LEGACY / QUARANTINE | Historical design/reference document, retained in place; not a current implementation reference. |
| ``docs/PROGRAM-PLAN.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/README.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/REDESIGN-PLAN.md`` | LEGACY / QUARANTINE | Historical design/reference document, retained in place; not a current implementation reference. |
| ``docs/SALVAGE-from-snipersight-trading.md`` | LEGACY / QUARANTINE | Historical design/reference document, retained in place; not a current implementation reference. |
| ``docs/SCAN-SCHEDULING.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/SIMPLE-STRATEGY-TRIAL.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/SPEC-confirmed-entry.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/SPEC-log-retention.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/SPEC-persistence-retention.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/UI-REDESIGN-SCOPE.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/WORK-STATE.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``docs/alerts.example.json`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``graphify-out/.graphify_labels.json`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/GRAPH_REPORT.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/graph.json`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/manifest.json`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/refresh_wiki.py`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/A-B_Calibration_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/A-B_Test_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ADR-001-_Isolated_Market_Workspaces.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/API_Server_Endpoints.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Action_Feedback_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Agent_roles.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Alert_Idempotency_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Apex_Bridge.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/App_Icon_192.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/App_Icon_512.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Arm-From-Phone_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Audit_Cache_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Audit_Closeout_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/BTC_Alignment_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/BTC_Alignment_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Baseline_Reset_Guard_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Baseline_Reset_Script.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias,_Trend_&_Setups.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias_Alignment_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias_As-Of_Discipline_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias_Enforcement_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias_Ladder_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias_Policy_Validation_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Bias_Verdict_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Boundary_Wake_Grid_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Breakeven_Fee_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/BrokerOrder.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/CI_Workflow_&_Test_Conventions.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/CalibrationAgainstTheLiveStore.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Candle_Cache_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Bootstrap_Glue.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_UI_Layer.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_API.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Chart_API.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Coordinates.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Core.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Crosshair.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Data_Layer.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Grid_&_Axis.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Hit_Testing.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Internals.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Layout.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Line_Renderers.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Marker_Rendering.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Number_Formatting.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Pane_Views.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Panes.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Price_Scale_Formatting.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Primitives.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Renderer_Base.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Rendering.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Scales.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Series.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Series_Views.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Time_Scale_API.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Watermark.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Chart_Vendor_Widget_Lifecycle.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Child_Spawn_Isolation_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cockpit_Diagnostics_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cockpit_Hierarchy_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cockpit_Route_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cold_Start_Live_Loop_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Composite_Bias_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Confirm_Dialog_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Confluence_Extractor_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Confound_Guard_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cooldown_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cooldown_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Copilot_Chat_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Copilot_Dock_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Copilot_Pack_Builder.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Copilot_Pack_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/CostTest.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cost_Profiles.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Credential_Vault.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Credential_Vault_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cross-Fill_Honesty_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cross-Site_Guard_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/CustodyOverridesTheSimulatorsStory.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cycle_Detection_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Cycle_Lede_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/DPAPI_Credentials_Vault_(credentials.py).md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Data_Quality_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Default_Factor_Extractor_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Design_Health_Reviews.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Design_System_&_Consistency_Docs.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Diagnostics_&_Edge_View_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Diagnostics_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Diagnostics_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Divergence_&_Factor_Grading.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Divergence_Stats_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Draft_Bracket_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ESLint_Config.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Edge_Statistics_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Edge_Stats_Determinism_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Edge_View_Render_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Empty_State_Honesty_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Engine_Contract_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Engine_Fault_Row_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Engine_Pipeline_Runner.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Entry_Stats_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Entry_Stats_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Era_Label_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ExecutionPlan.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Execution_Realism_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Execution_Simulator_&_Risk.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/FVG_&_Volume_Profile_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Fact_Contract_&_Core_Engines.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Fact_Query_&_Scan_Endpoints.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Fact_Store_&_Migrations.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Factor_Grading_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Factor_Redundancy_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Factor_Statistics_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Factor_Stats_Determinism_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Facts_Window_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/FaultCase.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/FaultCase_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Filtered_Book_Refusal_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Forward_vs_Historical_Book_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_Accrual_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_In_Simulation_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_Magnitude_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_Paging_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_Rate_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_Read-Only_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Funding_Sign_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Glossary_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Golden_Data_Calibration.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Health_Scope_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Heartbeat_Assertion_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/History_Floor_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/History_Ingest_&_Repair.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/History_Repair_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Indicator_Engines.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Kraken_Adapter.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Kraken_Window_Walk_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Ledger_Field_Contract_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Live_Gate_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Live_Gate_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Live_Market_Data_Helpers.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Live_Scanner_Loop.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Loading_State_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manifest_&_Cost_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ManualCase.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Arm_Validation_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Book_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Fill_Timing_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Order_Idempotency_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Settlement_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Trading_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Manual_Version_Migration_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Market_Data_Importer.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Maskable_PWA_Icon.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Missing_History_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Mission_Rail_&_Radar_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Momentum_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Moving_Average_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Mt.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Multi-Venue_Universe_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/NPM_Package_Manifest.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Near-Levels_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Near_Levels_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Near_Levels_Panel_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Nested_Cycle_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/NextWakeMath.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/NextWakeMath_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Next_Wake_Math_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/No-Cache_Static_Serving.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Notification_Delivery.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Notification_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Onboarding_Announce_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Onboarding_Path_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/One_Source_of_Truth_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Order_Sizing_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Outcome_Edge_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Outcome_Split_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/PWA_Installability_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Per-Factor_Noise_Floor_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Performance_&_Playbook_Endpoints.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Phemex_Adapter.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Phemex_Adapter_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Pipeline_Gate_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Pipeline_Quality_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Pipeline_Roster_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Playbook_Policy_Roster_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Playbook_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Portfolio_&_Position_Endpoints.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Process_Restart_Endpoint.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Product_Charter_&_Build_Journal.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ProtectedBroker.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ProtectedBroker_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/QualityStoreCase.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Quality_Verdict_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Range_Engine_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Rank_Decomposition_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Rate_Limiter_&_Retry_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Refresh_Repair_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Regime_Wording_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Rejection_Fact_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Remote_Alert_Sink_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Render_Scope_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Responsive_Layout_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/RetiredSymbolStalenessTest.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Ri.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Rules_Surface_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/RunRecorder.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/SPEC_—_Log_Retention_(`data-engine.log`).md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``graphify-out/wiki/SSData_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Scale-Out_Settlement_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Scanner_Alert_Isolation_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Second_Opinion_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Semantics_&_Keyboard_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Server_Narrative_Phrasing.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Settings_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Settings_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Setup_ID_Version_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Setup_Lifecycle_Telemetry.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Setup_Telemetry_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Setup_Trace_Endpoint.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Setup_Trace_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Setup_Wizard_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shadow_Classification_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shadow_Venue_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shared_Data_Cache_(ssdata.js).md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shared_Pipeline_Loop_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shell_Disposition_&_Risk_Rendering.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shell_Health_&_Staleness.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Shell_Navigation_&_Near_Levels.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ShortCapabilityTest.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Simulator_Convention_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Single-Walk_Book_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/SiteBridgeTests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Small_Sample_Refusal_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/SniperSight_Logo.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/SniperSight_Phemex-style_foundation_—_design_QA.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``graphify-out/wiki/SniperSight_autonomy_operations.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/SniperSight_development.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Store_Snapshots.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Strategy_Guard_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Strategy_Registry.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Strategy_Registry_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Summary.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Supervisor_Announce_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Swing_Promotion_Stability_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Swings,_Zones_&_Draft_Bracket.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/System_Restart_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/T.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/T_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/T_3.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/T_4.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Tactical_Cockpit-_Remaining_Screen_Redesign_Scope.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Tailnet_Access_Gate.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Tailnet_Access_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Telemetry_API_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/TestEveryRowIsAccountedFor.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/TestMarketQuality.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/TestNoLookahead.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/TestPointInTimeUniverse.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Tests_Package_Init.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Ticket_Math_&_Liquidation.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Toast_Flag_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Toast_Isolation_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Toast_Sink_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Tracer_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Trade_Surface_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Trader_Basics_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Trailing_Stop_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Trend_Engine_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/UI_Field_Contract_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/UI_Structure_JS_Suites.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Universe_&_Rate_Limiting.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Universe_Coverage_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/VenueResolutionTest.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Venue_Cost_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Venue_Policy_&_Contract.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Venue_Resolution_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Venue_Seam_&_Order_Ticket.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Version_Cascade_Lockfile.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Volatility_Engine.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Volatility_Engine_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Volume,_Ranges_&_Aggregation.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Volume_Engine_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/WAL_Hygiene_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Watchdog_Audit_Cadence_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Watchdog_Child_Capture_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Watchdog_Orphan_Clearing_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Watchdog_Quarantine_Persistence_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Watchdog_Restart_Dispatch_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Watchdog_Supervisor.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Weather_Denominator_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Weather_Endpoint_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Weather_Row_Accounting_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Weather_UI.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Weather_UI_Restraint_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Wheel_Widget.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Windows_Autostart_Installer.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Word_Budget_JS_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Working_Notes_&_Risk_Authority.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ZeroAtrDoesNotCrash.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Zone_Anchor_Identity_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/Zone_Causality_Tests.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/_as_float.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/_asset_version.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/_facts.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/aggregator.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/apex_state.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/applyLevels.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/architect.md.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/as().md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/auditor.md.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/binance.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/c.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/check.ps1.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/cockpit-workspaces.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/contrarian.md.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/cs.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/cycles.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/deck.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/edgeview.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/execsim.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/execsim.py_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/f().md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/factor-evidence.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/factorstats.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/fs().md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/funding.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/funding.py_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/he.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/implementer.md.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/index.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ji.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/key.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/learning.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/loadHealth.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/loadPerformance.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/markets.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/mn.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/mode-control.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/momentum.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ni.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ni_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ol.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/on.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/operations.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/preflight.ps1.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ranges.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/re.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/rebuild.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/renderLedger.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/renderLedger_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/renderProgression.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/report.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/scan_symbols.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/sn().md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/ssdata.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/status.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/stocks.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/stocks.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/stocks_connection_test.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_abtest.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_account_hero.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_achievements.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_autonomy_contracts.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_chart_layers.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_controlled_learning.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_factor_evidence_contract.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_live_clock.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_loading_states.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_market_context.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_market_workspaces.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_next_action.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_opportunities.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_orientation_and_axes.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_orientation_and_axes.js_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_overview_redesign.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_phemex_private.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_pipeline_gates.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_pipeline_gates.py_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_semantics_and_keyboard.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_shell_structure.js.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_ui_read_models.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/test_venues.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/vn.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/volatility.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/volume.py.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/wire.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/yi.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/yn.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/yn_2.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``graphify-out/wiki/zt.md`` | SUPPORT | Generated navigation or its refresh support; wiki baseline eb591d23adff is older than audited HEAD. Not execution authority. |
| ``scripts/check.ps1`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``scripts/preflight.ps1`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``sources/ss3_v0.1.txt`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``tools/agent-loop/Invoke-AgentLoop.ps1`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``tools/agent-loop/README.md`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
| ``tools/agent-loop/Uninstall-AgentLoop.ps1`` | SUPPORT | Tracked documentation, tooling, configuration or provenance; not a trading implementation. |
