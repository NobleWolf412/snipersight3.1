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

ok('opportunities compare compact cards before opening one detail', () => {
  assert(HTML.includes('id="opGroups"'));
  assert(HTML.includes('id="opDetail"'));
  assert(OP_UI.includes('op-card-compact'));
  assert(OP_UI.includes('Review setup'));
  assert(OP_UI.includes('Open in Trade'));
  assert(!OPPORTUNITIES.includes('armSetup'), 'Setup Radar must not directly commit capital');
});

ok('trade synchronizes evidence, chart, and ticket as three explicit areas', () => {
  for (const id of ['tradeEvidence', 'chartPane', 'ticket']) assert(HTML.includes(`id="${id}"`));
  assert(CSS.includes('grid-template-areas:"evidence chart ticket"'));
  assert(HTML.includes('/static/trade-workspace.js'));
  assert(OPPORTUNITIES.includes("new CustomEvent('ss:opportunity-selected'"));
});

ok('performance exposes five focused views and owns factor evidence', () => {
  for (const view of ['overview', 'strategies', 'factors', 'journal', 'promotion']) {
    assert(HTML.includes(`data-view="${view}"`), view + ' tab is missing');
    assert(HTML.includes(`data-performance-view="${view}"`), view + ' panel is missing');
  }
  assert.strictEqual((HTML.match(/id="factorEvidenceRoot"/g) || []).length, 1,
    'Factor evidence must have one mount and one screen owner');
  assert(HTML.includes('id="performanceLedger"'));
  assert(WORKSPACES.includes('ledgerHost.append'), 'manual books must join the Journal view');
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
  assert(/@media\(max-width:640px\)[\s\S]*?:root\{--topbar-h:94px\}/.test(CSS));
  assert(/#equityChip,#riskChip,#exposureChip\{display:flex!important/.test(CSS));
  assert(/#healthChip\{display:inline-flex!important/.test(CSS));
  assert(/\.topbar-actions\{display:block!important/.test(CSS));
});

ok('opportunity disclosure includes full economics, calibration, trace and non-modal focus', () => {
  for(const field of ['fee_r', 'funding_r', 'slippage_r', 'total_cost_r', 'notional_usd'])
    assert(OP_UI.includes(field), field + ' is absent');
  for(const field of ['expected_edge_r', 'sample_size', 'grade.components'])
    assert(OP_UI.includes(field), field + ' FactorGrade field is absent');
  assert(OP_UI.includes('data-op-trace='));
  assert(!OPPORTUNITIES.includes("setAttribute('aria-modal'"));
  assert(!OPPORTUNITIES.includes("event.key !== 'Tab'"));
  assert(OPPORTUNITIES.includes("event.key === 'Escape'"));
  assert(OPPORTUNITIES.includes("['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End']"));
  assert(HTML.includes('data-op-count="ACTIVE"'));
});

ok('entry presentation never manufactures a limit price and FactorGrade uses uplift', () => {
  const context = {window:{}, Number, String, Object, Date};
  vm.runInNewContext(OP_UI, context);
  const ui = context.window.SSOpportunityUI;
  assert.strictEqual(ui.entryRecommendation({order_kind:'NONE', limit_price:'99'}), 'NO ORDER');
  assert.strictEqual(ui.entryRecommendation({order_kind:'MARKET', limit_price:'99'}), 'MARKET - confirmed trigger');
  assert.strictEqual(ui.entryRecommendation({order_kind:'LIMIT'}), 'LIMIT - price not reported');
  assert(ui.entryRecommendation({order_kind:'LIMIT',limit_price:'42'}).includes('42'));
  const exact = '0.123456789012345678901';
  assert.strictEqual(ui.px(exact), exact);
  assert(ui.entryRecommendation({order_kind:'LIMIT',limit_price:exact}).includes(exact));
  const body = ui.evidenceBody({setup:{}, evidence:{components:[{factor:'x',uplift_r:0.2,shrunk_uplift_r:0.1}]}});
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
  assert(COCKPIT.includes("data-performance-dimension"));
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
