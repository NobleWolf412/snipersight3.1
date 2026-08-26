/* Source-level contracts for the task-oriented cockpit redesign. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const STATIC = path.join(__dirname, '..', 'static');
const HTML = fs.readFileSync(path.join(STATIC, 'shell.html'), 'utf8');
const CSS = fs.readFileSync(path.join(STATIC, 'ss.css'), 'utf8');
const OPPORTUNITIES = fs.readFileSync(path.join(STATIC, 'opportunities.js'), 'utf8');
const OP_UI = fs.readFileSync(path.join(STATIC, 'opportunity-ui.js'), 'utf8');
const OPERATIONS_UI = fs.readFileSync(path.join(STATIC, 'operations.js'), 'utf8');
const WORKSPACES = fs.readFileSync(path.join(STATIC, 'workspaces.js'), 'utf8');
const TRADE = fs.readFileSync(path.join(STATIC, 'trade-workspace.js'), 'utf8');
const COCKPIT = fs.readFileSync(path.join(STATIC, 'cockpit-workspaces.js'), 'utf8');
const FACTORS = fs.readFileSync(path.join(STATIC, 'factor-evidence.js'), 'utf8');
const CHART = fs.readFileSync(path.join(STATIC, 'chart.js'), 'utf8');
const EDGE = fs.readFileSync(path.join(STATIC, 'edgeview.js'), 'utf8');
const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (error) { console.log('  FAIL ' + name + '\n       ' + error.message); process.exitCode = 1; }
}

console.log('cockpit redesign');

ok('every custom property this stylesheet uses is one it defines', () => {
  /* A MISSPELLED TOKEN IS NOT A COSMETIC DEFECT, and this is the only thing
     that can see one. CSS has no error for it: an undefined var() with no
     fallback does not fall back, it makes the WHOLE declaration invalid at
     computed-value time. So `border:1px solid var(--line)` computes
     border-style:none and draws nothing, and `font:var(--fs-0)/1.4
     var(--mono)` drops the size and the family together and inherits body
     text. Nothing throws, nothing logs, node --check cannot look at CSS, and
     the JS suites assert on markup — the only symptom is a surface that
     looks slightly wrong to whoever is using it.

     Found 8 Aug 2026 from an operator report that the Performance screen's
     layout was "rough": --line, --mono, --fs-0 and --panel were all in use
     and none existed. The real names are --border, --f-mono, --fs-1 and
     --card. Between them they left the scope strip, both of its dropdowns,
     the promotion stage cards and the ticket's sticky commit bar with no
     borders, and the commit bar with no background over scrolling content.

     A fallback is still allowed — `var(--x, 12px)` is a deliberate default,
     not a typo — so only bare references count. */
  const rules = CSS.replace(/\/\*[\s\S]*?\*\//g, '');
  const defined = new Set([...rules.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)].map(m => m[1]));
  const missing = [...new Set([...rules.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)\s*\)/g)]
    .map(m => m[1]).filter(name => !defined.has(name)))];
  assert.deepStrictEqual(missing, [],
    'ss.css uses custom properties it never defines: ' + missing.join(', ') +
    '. Every declaration mentioning one of these is silently dropped');
});

ok('the View by control only appears where it changes something', () => {
  /* It filters #performanceDimensions and nothing else, and that panel is on
     the Strategies view. Sitting in the always-visible scope strip, it did
     nothing at all on Overview — which is the tab this surface opens on — so
     the operator's read was that the dropdown was broken. It was pointed four
     views away. workspaces.js hides every [data-performance-view] that is not
     the active one, so scoping it is an attribute, not new wiring. */
  const label = HTML.match(/<label[^>]*>\s*(?:<!--[\s\S]*?-->\s*)?<b>View by<\/b>/) ||
                HTML.match(/<label[^>]*data-performance-view[^>]*>\s*<b>View by<\/b>/);
  assert(label, 'the View by control is gone, or no longer wraps a <label>');
  assert(/data-performance-view="strategies"/.test(label[0]),
    'the View by dropdown is back in the always-on scope strip. It only ' +
    'drives the Strategies dimension tables — everywhere else it is a live ' +
    'control that changes nothing, which reads as a broken one');
  assert(WORKSPACES.includes('panel.hidden = panel.dataset[`${name}View`] !== view'),
    'the view switcher no longer hides panels by data-*-view, so the ' +
    'attribute above stopped scoping anything');
});

ok('opportunities compare compact cards before opening one detail', () => {
  assert(HTML.includes('id="opGroups"'));
  assert(HTML.includes('id="opDetail"'));
  assert(OP_UI.includes('op-card-compact'));
  assert(OP_UI.includes('Review setup'));
  assert(OP_UI.includes('Open in Trade'));
  assert(OP_UI.includes("row.state === 'READY' && row.eligible"),
    'Open in Trade must be driven by server entry eligibility');
  assert(OP_UI.includes('Inspect chart'),
    'forming setups need an inspection action, not a trade action');
  assert(OP_UI.includes('Manage position') && OP_UI.includes('View working order'),
    'active lifecycle states need an exact-setup management action');
  assert(!OPPORTUNITIES.includes('armSetup'), 'Setup Radar must not directly commit capital');
});

ok('trade synchronizes evidence, chart, and ticket as three explicit areas', () => {
  for (const id of ['tradeEvidence', 'chartPane', 'ticket']) assert(HTML.includes(`id="${id}"`));
  assert(CSS.includes('grid-template-areas:"evidence chart ticket"'));
  assert(HTML.includes('/static/trade-workspace.js'));
  assert(OPPORTUNITIES.includes("new CustomEvent('ss:opportunity-selected'"));
  assert(OPPORTUNITIES.indexOf('SSChart.prepare') < OPPORTUNITIES.indexOf("location.hash = 'trade'"),
    'the next chart context must be prepared before the Trade route paints');
  assert(OPPORTUNITIES.includes('setup_id: row.setup.setup_id, inspect_only: inspectOnly'),
    'chart inspection must preserve exact setup identity');
  const prepare = CHART.slice(CHART.indexOf('function prepare'), CHART.indexOf('async function open'));
  assert(prepare.includes('clearChart('),
    'preparing a route must synchronously mask the old chart and ticket');
  assert(prepare.includes('previousSetupId !== preferredSetupId') &&
    prepare.includes('previousInspectOnly !== preferredInspectOnly'),
    'same-market setup and inspection changes must mask the old ticket too');
});

ok('a new chart market releases the previous market price range', () => {
  const load = CHART.slice(CHART.indexOf('async function load(opts)'),
    CHART.indexOf('/* The operator\'s live trade'));
  assert(CHART.includes('let priceScaleMarket = null'),
    'the price-axis market identity must not depend on painted, which setup changes clear');
  assert(load.includes('const resetPriceScale = priceScaleMarket !== marketKey'),
    'symbol/timeframe changes must be distinguished from same-market refreshes');
  const setData = load.indexOf('series.setData(candles)');
  const autoScale = load.indexOf('series.priceScale().applyOptions({autoScale: true})');
  assert(setData >= 0 && autoScale > setData,
    'the new candles must release the old manual vertical range before the viewport paints');
  assert(load.indexOf('priceScaleMarket = marketKey') > autoScale,
    'the axis identity must advance only after its reset succeeds');
  assert(CHART.includes('_priceScaleAuto: () => series ?'),
    'canvas-only price-scale state must stay observable to the browser regression');
});

ok('overview setup count and bot phase use the operational read model', () => {
  assert(OPERATIONS_UI.includes("$('mSetups').textContent = ready"));
  assert(!/\$\('mSetups'\)\.textContent = split\.ordered\.length/.test(
    fs.readFileSync(path.join(STATIC, 'shell.js'), 'utf8')),
    'legacy deck selector still overwrites the server READY count');
  assert(SERVER.includes('"stage": hb.get("phase")'),
    'operations still reads a heartbeat key the scanner never writes');
});

ok('#performance-ledger opens the Journal after boot, not on the next boot', () => {
  /* THE ADDRESS WORKED EXACTLY ONCE PER PAGE LOAD. go() honoured
     #performance-ledger by writing ss:performance-view and nothing else, and
     that key is read once, by show(getSaved(...)) when workspaces.js binds. So
     a cold start on the hash landed on the Journal and every later arrival —
     the rail's Trade journal link, a hashchange, the 6 key — switched to
     Results and left the visible view where it was, with the request taking
     effect the NEXT time the app booted. A UI audit read that as the ledger
     being unreachable, which is what it was.

     Both halves are required: storage covers boot, because shell.js runs
     before workspaces.js and there is nothing listening yet; the event covers
     every arrival after it, because by then storage is nobody's input. */
  const SHELL = fs.readFileSync(path.join(STATIC, 'shell.js'), 'utf8');
  const at = SHELL.indexOf("route === 'performance-ledger'");
  assert(at > 0, 'the ledger route is gone — re-anchor this test');
  const block = SHELL.slice(at, at + 500);
  assert(/sessionStorage\.setItem\('ss:performance-view', 'journal'\)/.test(block),
    'the cold-start half is gone: a bookmarked #performance-ledger opens Overview');
  assert(/ss:workspace-request/.test(block),
    'the live half is gone: the route only takes effect on the next page load');
  assert(/addEventListener\('ss:workspace-request'/.test(WORKSPACES) &&
         /request\.name === name/.test(WORKSPACES),
    'nothing acts on a view request, so the router writes storage into a void');
});

ok('performance exposes five focused views and owns factor evidence', () => {
  for (const view of ['overview', 'strategies', 'factors', 'journal', 'promotion']) {
    assert(HTML.includes(`data-view="${view}"`), view + ' tab is missing');
    assert(HTML.includes(`data-performance-view="${view}"`), view + ' panel is missing');
  }
  assert.strictEqual((HTML.match(/id="factorEvidenceRoot"/g) || []).length, 1,
    'Factor evidence must have one mount and one screen owner');
  assert(HTML.includes('id="performanceLedger"'));
  assert(/<div class="panel floating" hidden>\s*<div class="mb-shell">/.test(HTML),
    'the duplicate statistic carousel is visible again');
  /* The books are AUTHORED in the Journal view now. They used to be markup in
     a separate #s-ledger surface that workspaces.js emptied into this host on
     every load, which left the husk behind: an unroutable section, a second
     <h1>Results</h1>, and two tab links nothing could ever show. Moving them at
     runtime is the thing that must not come back — a panel that renders in a
     different place from where it is written is a panel nobody finds. */
  assert(!WORKSPACES.includes('ledgerHost.append') && !HTML.includes('id="ledgerContent"'),
    'the books are being relocated at runtime again instead of authored in place');
  const host = HTML.indexOf('id="performanceLedger"');
  for (const mount of ['id="ledgerBooks"', 'id="ledgerMine"', 'id="ledgerExits"']) {
    const at = HTML.indexOf(mount);
    assert(at > host && at < HTML.indexOf('</section>', host),
      `${mount} is not inside the Journal view`);
  }
});

ok('system separates automation, risk, venues, strategies, and diagnostics', () => {
  for (const view of ['automation', 'risk', 'venues', 'strategies']) {
    assert(HTML.includes(`data-system-view="${view}"`), view + ' system panel is missing');
  }
  assert(HTML.includes('href="#system-diagnostics"'));
  assert(WORKSPACES.includes("bind('system', 's-settings', 'automation')"));
});

ok('focused views retain keyboard-sized controls and responsive trade order', () => {
  assert(/\.workspace-tabs button,.workspace-tabs a\{[^}]*min-height:44px/.test(CSS));
  assert(/@media \(max-width:900px\)[\s\S]*?grid-template-areas:"evidence" "chart" "ticket"/.test(CSS));
  assert(/\.topbar-actions #btnHalt\{display:inline-flex/.test(CSS));
});

ok('390px command layer keeps every safety fact and HALT visible', () => {
  /* The two safety rows remain; tighter 40px + 36px tracks remove twelve pixels
     of dead chrome without deleting health, equity, risk, exposure, or HALT. */
  assert(/@media\(max-width:640px\)[\s\S]*?:root\{--topbar-h:82px\}/.test(CSS));
  assert(/#equityChip,#riskChip,#exposureChip\{display:flex!important/.test(CSS));
  assert(/#healthChip\{display:inline-flex!important/.test(CSS));
  /* `flex`, not `block`. The actions track carries TWO buttons on a phone now
     — Copilot was hidden here on 8 Aug 2026 and the operator reported the
     copilot unreachable on mobile the same day, so it came back. What this
     line is really asserting is that the track lays out as one row and stays
     on screen; the display value is how, not what. test_copilot_dock.js pins
     the other half: no rule anywhere may hide #btnCopilot at any width. */
  assert(/\.topbar-actions\{display:flex!important/.test(CSS));
});

ok('opportunity disclosure keeps economics and hides unavailable grading', () => {
  for(const field of ['fee_r', 'funding_r', 'slippage_r', 'total_cost_r', 'notional_usd'])
    assert(OP_UI.includes(field), field + ' is absent');
  for(const field of ['expected_edge_r', 'sample_size', 'grade.components'])
    assert(OP_UI.includes(field), field + ' FactorGrade field is absent');
  assert(OP_UI.includes("String(grade.grade).toUpperCase() !== 'UNGRADED'"),
    'unavailable setup grades are visible again');
  assert(!OP_UI.includes("grade.grade || 'UNGRADED'"));
  assert(!OP_UI.includes('INSUFFICIENT_EVIDENCE'));
  assert(OP_UI.includes('Why it was skipped'));
  assert(OP_UI.includes('data-op-trace='));
  assert(!OPPORTUNITIES.includes("setAttribute('aria-modal'"));
  assert(!OPPORTUNITIES.includes("event.key !== 'Tab'"));
  assert(OPPORTUNITIES.includes("event.key === 'Escape'"));
  assert(OPPORTUNITIES.includes("['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End']"));
  assert(HTML.includes('data-op-count="ACTIVE"'));
  assert(HTML.includes('data-op-filter="ACTIVE" aria-pressed="true">Live'),
    'the active-order bucket must not imply it includes forming setups');
  assert(OPPORTUNITIES.includes("const ACTIVE = new Set(['POSITION_OPEN','ORDER_WORKING'])"),
    'Live, Ready, Forming, Watching, and History must be disjoint buckets');
  assert(OPPORTUNITIES.includes("['ACTIVE','READY','FORMING','WATCHING','HISTORY']"),
    'the first non-empty bucket should open instead of an empty Live view');
});

ok('entry presentation is plain, exact, and only shows real grades', () => {
  const context = {window:{}, Number, String, Object, Date};
  vm.runInNewContext(OP_UI, context);
  const ui = context.window.SSOpportunityUI;
  assert.strictEqual(ui.entryRecommendation({order_kind:'NONE', limit_price:'99'}, 'FORMING'),
    'Watching — entry not confirmed');
  assert.strictEqual(ui.entryRecommendation({order_kind:'NONE'}, 'BLOCKED'), 'Skipped');
  assert.strictEqual(ui.entryRecommendation({order_kind:'MARKET', limit_price:'99'}),
    'Market entry on confirmed trigger');
  assert.strictEqual(ui.entryRecommendation({order_kind:'LIMIT'}),
    'Limit order — price unavailable');
  assert(ui.entryRecommendation({order_kind:'LIMIT',limit_price:'42'}).includes('42'));
  const exact = '0.123456789012345678901';
  assert.strictEqual(ui.px(exact), exact);
  assert(ui.entryRecommendation({order_kind:'LIMIT',limit_price:exact}).includes(exact));
  const hidden = ui.evidenceBody({setup:{}, evidence:{grade:'UNGRADED',
    confidence:'INSUFFICIENT_EVIDENCE', components:[]}});
  assert(!hidden.includes('UNGRADED')); assert(!hidden.includes('INSUFFICIENT'));
  const body = ui.evidenceBody({setup:{}, evidence:{grade:'A', score:82,
    confidence:'HIGH', components:[{factor:'x',uplift_r:0.2,shrunk_uplift_r:0.1}]}});
  assert(body.includes('0.2R')); assert(!body.includes('0.1R'));
});

ok('halt banner never changes exact managed or manual custody state', () => {
  const context = {window:{}};
  vm.runInNewContext(TRADE.slice(0, TRADE.indexOf('(() => {')), context);
  const project = context.window.SSTradeWorkspaceProjection;
  assert.deepStrictEqual(JSON.parse(JSON.stringify(project({halted:true,
    position:{owner:'BOT'}, rowState:'POSITION_OPEN'}))),
    {bannerState:'HALTED',custodyState:'POSITION_MANAGED'});
  assert.deepStrictEqual(JSON.parse(JSON.stringify(project({halted:true,
    position:{owner:'MANUAL_OVERRIDE'}}))),
    {bannerState:'HALTED',custodyState:'MANUAL_OVERRIDE'});
});

ok('selected setup and custody contracts use exact setup identity', () => {
  assert(CHART.includes('setup = preferredSetupId ? (preferred || null)'));
  assert(CHART.includes('preferredSetupMissing ? true'));
  assert(TRADE.includes('position.setup_id === selectedSetupId'));
  assert(TRADE.includes("api('/api/opportunities/' + encodeURIComponent(selectedSetupId))"));
  assert(!TRADE.includes('position.symbol ==='));
});

ok('trade uses explicit state vocabulary, grouped layers and mobile sheets', () => {
  for(const state of ['PLANNING','ORDER_WORKING','POSITION_MANAGED','MANUAL_OVERRIDE','HALTED'])
    assert(TRADE.includes(state), state + ' is absent');
  assert.strictEqual((HTML.match(/class="layer-group"/g) || []).length, 3);
  assert(HTML.includes('id="tradeMobileBar"'));
  assert(TRADE.includes("api('/api/automation/status')"));
  assert(TRADE.includes("api('/api/positions/managed')"));
  assert(CHART.includes("new CustomEvent('ss:trade-ticket-state'"));
  assert(CSS.includes('body.trade-sheet-evidence .trade-evidence'));
  assert(CSS.includes('body.trade-sheet-action .ticket'));
  assert(!TRADE.includes("setAttribute('aria-modal'"));
  assert(!TRADE.includes("event.key !== 'Tab'"));
  assert(TRADE.includes('sheetReturnFocus'));
});

ok('performance reads its scoreboard and dimensions from server contracts', () => {
  assert(SERVER.includes('"performance_summary": _journal_performance_summary'));
  assert(SERVER.includes('@app.get("/api/performance/dimensions")'));
  assert(COCKPIT.includes("api('/api/performance/dimensions')"));
  assert(HTML.includes('id="performanceTrust"'));
  assert(HTML.includes('id="journalSearch"'));
  assert(HTML.includes('id="performanceBreakdown"'));
  assert(!HTML.includes('All dimensions'),
    'one trade must not be repeated through every breakdown by default');
  assert(HTML.includes('<b>View by</b><select id="performanceBreakdown">'));
  assert(HTML.includes('<option value="symbol">Symbol</option>'));
  assert(COCKPIT.includes("data-performance-dimension"));
  assert(COCKPIT.includes('panel.hidden = panel.dataset.performanceDimension !== select.value'));
  assert(COCKPIT.includes("['strategy','symbol','regime','horizon','direction','order_type']"));
  assert(/<div class="grid cols-2" hidden>/.test(HTML),
    'the legacy By Symbol / By Strategy pair is visible below the dimension selector');
  assert(COCKPIT.includes('data-label="Avg R"') && COCKPIT.includes('data-label="P&amp;L"'),
    'mobile performance cells need visible labels without a table header');
  assert(/@media\(max-width:640px\)[\s\S]*?\.dimension-table thead\{display:none\}/.test(CSS));
  assert(HTML.includes('id="journalSource"'));
  for(const id of ['performancePopulation','performanceWindow']) assert(HTML.includes(`id="${id}"`));
  assert(SERVER.includes('"confidence_interval_r": confidence'));
  assert(SERVER.includes('CUMULATIVE_CURRENT_FACTORSTATS_VERSION'));
  assert(SERVER.includes('CUMULATIVE_CURRENT_AUTOMATION_VERSION'));
  for(const stage of ['PAPER','SHADOW','TESTNET','LIVE']) assert(COCKPIT.includes(`['${stage}'`));
  assert(FACTORS.includes('Factor Stats cohorts'));
  for(const field of ['shrunk_uplift_r', 'ci_lo', 'q_value', 'high_samples'])
    assert(FACTORS.includes(field), field + ' factor evidence is absent');
});

ok('journal filtering cannot observe its own status announcement', () => {
  assert(COCKPIT.includes("const journal = $('journal'), status = $('journalMatch')"));
  assert(COCKPIT.includes('observe(journal, {childList:true,subtree:true})'));
  assert(COCKPIT.includes('if(status.textContent !== message) status.textContent = message'));
  assert(!COCKPIT.includes('observe(surface, {childList:true,subtree:true})'));
});

ok('mixed evidence views never claim one uniform scope', () => {
  const context = {window:{}};
  vm.runInNewContext(COCKPIT.slice(0, COCKPIT.indexOf('(() => {')), context);
  const scopes = context.window.SSPerformanceScopeMapping({
    summary:{population:'FUNDED_PAPER_TRADES',window:'ACTIVE_BASELINE'},
    dimensions:{population:'FUNDED_PAPER_TRADES',window:'ACTIVE_BASELINE'}});
  for(const view of ['overview','factors','journal','promotion']){
    assert.strictEqual(scopes[view].population, 'MIXED EVIDENCE WINDOWS');
    assert.strictEqual(scopes[view].window, 'EACH PANEL LABELS ITS SCOPE');
  }
  assert.strictEqual(scopes.strategies.window, 'ACTIVE_BASELINE');
  assert(EDGE.includes('whole recorded book'));
  assert(FACTORS.includes('Factor Stats scope'));
  assert(FACTORS.includes('FactorGrade scope'));
  assert(COCKPIT.includes("stage === 'PAPER' ? summary : mode.evidence_scope"));
});

ok('system names consequences and keeps one global apply bar', () => {
  for(const id of ['automationFacts','riskUsage','venueFacts','strategyCatalogue',
    'reconciliationRoot']) assert(HTML.includes(`id="${id}"`), id + ' is absent');
  assert.strictEqual((HTML.match(/id="dirtyBanner"/g) || []).length, 1);
  assert(/<section class="surface" id="s-settings"[\s\S]*id="dirtyBanner"[\s\S]*<\/section>/.test(HTML));
  assert(COCKPIT.includes("api('/api/playbooks')"));
  assert(COCKPIT.includes('No qualifying run reported'));
  assert(COCKPIT.includes('Not reported by credential status'));
  assert(COCKPIT.includes('STALE / UNAVAILABLE'));
  assert(fs.readFileSync(path.join(STATIC, 'operations.js'), 'utf8').includes('Risk unavailable'));
  assert(/#s-settings>\.dirty-banner\{position:fixed/.test(CSS));
});

console.log('\n  ' + passed + ' passed');
