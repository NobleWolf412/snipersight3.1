/* Read-only detail for Debrief and Control Room. Every figure is copied from
   a server read model; missing fields are named instead of reconstructed. */
function performanceScopeMapping({summary={},dimensions={}} = {}){
  const mixed = {population:'MIXED EVIDENCE WINDOWS',
    window:'EACH PANEL LABELS ITS SCOPE'};
  return {
    overview: {...mixed}, factors: {...mixed}, journal: {...mixed}, promotion: {...mixed},
    strategies: {population:dimensions.population || 'NOT_REPORTED',
      window:dimensions.window || 'NOT_REPORTED'},
    overviewPanel: {population:summary.population || 'NOT_REPORTED',
      window:summary.window || 'NOT_REPORTED'}
  };
}
if(typeof window !== 'undefined') window.SSPerformanceScopeMapping = performanceScopeMapping;
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = path => window.SSData ? SSData.get(path, 0) :
    fetch(path, {cache:'no-store'}).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  const label = value => String(value || 'NOT_REPORTED').replaceAll('_',' ');
  const money = value => value == null ? 'Not reported' : '$' + Number(value).toLocaleString(undefined,
    {minimumFractionDigits:2,maximumFractionDigits:2});
  const performanceScopes = {};
  function showPerformanceScope(view){
    const scope = performanceScopes[view] || {population:'NOT_REPORTED',window:'NOT_REPORTED'};
    if($('performancePopulation')) $('performancePopulation').textContent = label(scope.population);
    if($('performanceWindow')) $('performanceWindow').textContent = label(scope.window);
  }

  function dimensionTable(name, rows){
    return `<section class="panel" data-performance-dimension="${esc(name)}"><div class="panel-head"><h2 class="t-section">By ${esc(label(name).toLowerCase())}</h2></div>
      <div class="dimension-scroll"><table class="dimension-table"><thead><tr><th>Group</th><th>Trades</th>
        <th>Win</th><th>Avg R</th><th>Total R</th><th>P&amp;L</th></tr></thead><tbody>${
        rows.length ? rows.map(row => `<tr><td>${esc(label(row.key))}</td><td>${esc(row.n)}</td>
          <td>${esc(row.win_pct)}%</td><td>${Number(row.average_r).toFixed(2)}R</td>
          <td>${Number(row.sum_r).toFixed(2)}R</td><td>${esc(money(row.pnl_usd))}</td></tr>`).join('')
          : '<tr><td colspan="6">No funded trades in this dimension.</td></tr>'}</tbody></table></div></section>`;
  }

  async function loadPerformanceWorkspace(){
    if(!$('performanceTrust')) return;
    try{
      const [portfolio, dimensions, mode] = await Promise.all([
        api('/api/portfolio'), api('/api/performance/dimensions'), api('/api/automation/status')]);
      const summary = portfolio.performance_summary;
      if(!summary || !summary.verdict) throw new Error('performance summary not reported by this server build');
      $('performanceTrust').dataset.verdict = summary.verdict.code === 'REVIEW_CONFIDENCE_INTERVAL'
        ? 'TRUST_BUILDING' : 'NOT_PROVEN';
      $('performanceTrust').innerHTML = `<span class="op-state">Trust verdict</span>
        <b>${esc(summary.verdict.text)}</b><small>${esc(label(summary.population))} · ${esc(label(summary.window))} · ` +
        `since ${summary.started_at ? new Date(summary.started_at * 1000).toISOString().slice(0,10) : 'date not reported'} Â· ` +
        `${summary.confidence_interval_r && summary.confidence_interval_r.status === 'MEASURED'
          ? `95% mean-R interval [${summary.confidence_interval_r.lo}, ${summary.confidence_interval_r.hi}]R`
          : `confidence interval unavailable: insufficient evidence (${summary.trades}/${summary.confidence_interval_r && summary.confidence_interval_r.minimum_trades || 10})`}</small>`;
      const groups = dimensions.dimensions || {};
      $('performanceDimensions').innerHTML = `<p class="population-note">Funded paper trades · active baseline. ` +
        `Unknown metadata remains “not reported.”</p><div class="dimension-grid">${
          ['strategy','regime','horizon','direction','order_type'].map(key =>
            dimensionTable(key, groups[key] || [])).join('')}</div>`;
      const p = mode.promotion || {}, op = mode.operational || {};
      Object.assign(performanceScopes, performanceScopeMapping({summary,dimensions}));
      showPerformanceScope($('s-results').dataset.activeView || 'overview');
      if($('promotionScopeNote')) $('promotionScopeNote').textContent =
        `Mixed evidence windows. PAPER uses ${label(summary.population)} / ${label(summary.window)}; ` +
        `later stages use ${label(mode.evidence_scope && mode.evidence_scope.population)} / ` +
        `${label(mode.evidence_scope && mode.evidence_scope.window)}.`;
      $('promotionSummary').innerHTML = [
        ['Evidence', p.evidence_ready ? 'MET' : 'NOT MET'],
        ['Shadow', p.shadow_ready ? 'MET' : `${op.shadow_days || 0}d · ${op.shadow_intents || 0} intents`],
        ['Testnet', p.testnet_ready ? 'MET' : `${op.testnet_days || 0}d · ${op.testnet_lifecycles || 0} lifecycles`],
        ['Live router', p.live_router_build_enabled ? 'BUILT' : 'BUILD LOCKED']
      ].map(([key,value]) => `<div><span>${key}</span><b>${esc(value)}</b></div>`).join('');
      if($('promotionStages')) $('promotionStages').innerHTML = [
        ['PAPER', summary.trades > 0 ? `${summary.trades} funded outcomes recorded` : 'BLOCKED - no funded outcomes recorded'],
        ['SHADOW', p.shadow_ready ? 'READY - server gate met' : `BLOCKED - ${op.shadow_days || 0} days and ${op.shadow_intents || 0} intents recorded`],
        ['TESTNET', p.testnet_ready ? 'READY - server gate met' : `BLOCKED - ${op.testnet_days || 0} days, ${op.testnet_lifecycles || 0} lifecycles; reconciliation and drills must pass`],
        ['LIVE', p.live_router_build_enabled ? 'BUILD PRESENT - all live gates still apply' : 'BLOCKED - live router build lock is active']
      ].map(([stage,detail]) => {
        const scope = stage === 'PAPER' ? summary : mode.evidence_scope || {};
        return `<article><b>${stage}</b><span>${esc(detail)}</span><small>Population: ${esc(label(scope.population))} Â· Window: ${esc(label(scope.window))}</small></article>`;
      }).join('');
    }catch(err){
      $('performanceTrust').dataset.verdict = 'DEGRADED';
      $('performanceTrust').innerHTML = `<span class="op-state">Data degraded</span><b>Trust summary unavailable.</b>
        <small>${esc(err.message)}. No result is inferred.</small>`;
      if($('performanceDimensions')) $('performanceDimensions').innerHTML =
        '<div class="panel op-empty bad"><h2>Dimension record unavailable</h2><p>No comparison is inferred.</p></div>';
    }
  }

  function wireJournalSearch(){
    const input = $('journalSearch'), source = $('journalSource'), surface = $('s-results');
    const journal = $('journal'), status = $('journalMatch');
    if(!input || !source || !surface || !journal || !status) return;
    const apply = () => {
      const query = input.value.trim().toLowerCase();
      const wanted = source.value;
      const rows = [...surface.querySelectorAll('[data-performance-view="journal"] .jnl-row')];
      let shown = 0;
      rows.forEach(row => { const visible = (!query || row.textContent.toLowerCase().includes(query)) &&
          (wanted === 'ALL' || row.dataset.journalSource === wanted);
        row.hidden = !visible; shown += visible ? 1 : 0; });
      /* The observer watches only the journal mount. Watching the whole
         Performance surface made this status write observe itself forever,
         pinning Chrome's main thread before the operator could interact. */
      const message = `${shown} of ${rows.length} journal rows`;
      if(status.textContent !== message) status.textContent = message;
    };
    input.addEventListener('input', apply);
    source.addEventListener('change', apply);
    new MutationObserver(apply).observe(journal, {childList:true,subtree:true});
    apply();
  }

  function wirePerformanceBreakdown(){
    const select = $('performanceBreakdown'), root = $('performanceDimensions');
    if(!select || !root) return;
    const apply = () => root.querySelectorAll('[data-performance-dimension]').forEach(panel => {
      panel.hidden = select.value !== 'ALL' && panel.dataset.performanceDimension !== select.value;
    });
    select.addEventListener('change', apply);
    new MutationObserver(apply).observe(root, {childList:true});
  }

  addEventListener('ss:workspace-view', event => {
    if(event.detail && event.detail.name === 'performance') showPerformanceScope(event.detail.view);
  });

  function facts(items){
    return `<div class="system-fact-grid">${items.map(([key,value]) =>
      `<div><span>${esc(key)}</span><b>${esc(value)}</b></div>`).join('')}</div>`;
  }

  async function loadSystemWorkspace(){
    if(!$('automationFacts')) return;
    try{
      const [mode, operations, config, credentials, playbooks] = await Promise.all([
        api('/api/automation/status'), api('/api/operations'), api('/api/trade-config'),
        api('/api/credentials'), api('/api/playbooks')]);
      const promotion = mode.promotion || {};
      $('automationFacts').innerHTML = [
        ['Halt state', mode.halted ? 'HALTED' : 'CLEAR'],
        ['Dispatch', mode.dispatch_allowed ? 'ALLOWED BY CURRENT MODE' : 'NOT ALLOWED'],
        ['Promotion lock', promotion.live_router_build_enabled ? 'GATES APPLY' : 'LIVE BUILD LOCKED'],
        ['Custody', mode.mode === 'SHADOW' ? 'RECORD ONLY' : mode.mode]
      ].map(([key,value]) => `<div><span>${key}</span><b>${esc(value)}</b></div>`).join('');

      const account = operations.account || {}, venue = config.venue || {};
      $('riskUsage').innerHTML = [
        ['Open risk', money(account.open_risk_usd)],
        ['Free total risk', money(account.total_risk_remaining_usd)],
        ['Daily loss room', money(account.daily_loss_remaining_usd)],
        ['Exposure', `${account.open_positions || 0} positions · ${account.working_orders || 0} orders`],
        ['Margin mode', label(venue.margin_mode)], ['Position mode', label(venue.position_mode)]
      ].map(([key,value]) => `<div><span>${key}</span><b>${esc(value)}</b></div>`).join('');

      const phemex = Object.entries(credentials.status || {})
        .filter(([name]) => name.startsWith('phemex'));
      const stored = phemex.reduce((total, [, fields]) =>
        total + Object.values(fields || {}).filter(Boolean).length, 0);
      $('venueFacts').innerHTML = facts([
        ['Environment', operations.venue || 'Not reported'],
        ['Credential health', stored ? `${stored} fields stored across ${phemex.length} environments; acceptance not tested` : 'Not connected'],
        ['Permission scope', 'Not reported by credential status'],
        ['Instrument metadata age', 'Not reported by current adapter'],
        ['Connectivity', 'Not tested in this session'],
        ['Withdrawal authority', 'Never required; do not grant it']
      ]);

      $('strategyCatalogue').innerHTML = (playbooks.playbooks || []).map(card =>
        `<article class="strategy-contract"><header><h3>${esc(card.name)}</h3>
          <span class="chip">${esc(label(card.evidence_status))}</span>
          <span class="chip">${card.enabled == null ? esc(label(card.status)) : card.enabled ? 'ENABLED' : 'DISABLED'}</span></header>
          <dl><div><dt>Horizons</dt><dd>${esc((card.horizons || []).join(', ') || 'Not reported')}</dd></div>
          <div><dt>Trigger</dt><dd>${esc(card.trigger_timeframe || (card.timeframes || []).join(', ') || 'Not reported')}</dd></div>
          <div><dt>Directions</dt><dd>${esc((card.directions || []).join(', ') || 'Not reported')}</dd></div>
          <div><dt>Higher timeframe</dt><dd>${esc(label(card.higher_timeframe_relationship))}</dd></div>
          <div><dt>Entry</dt><dd>${esc(label(card.entry_policy))}</dd></div>
          <div><dt>Minimum after costs</dt><dd>${card.minimum_rr_after_costs == null ? 'Not reported' : esc(card.minimum_rr_after_costs + 'R')}</dd></div></dl>
        </article>`).join('') || '<div class="empty">No playbook contracts reported.</div>';

      renderReconciliation(mode);
    }catch(err){
      $('automationFacts').innerHTML = '<div><span>System read model</span><b>UNAVAILABLE</b></div>';
      if($('riskUsage')) $('riskUsage').innerHTML =
        '<div><span>Risk and exposure</span><b>STALE / UNAVAILABLE</b></div>';
      $('venueFacts').textContent = `Venue state unavailable: ${err.message}`;
      $('strategyCatalogue').innerHTML = '<div class="empty">Playbook contracts unavailable.</div>';
      renderReconciliation(null);
    }
  }

  function renderReconciliation(mode){
    const root = $('reconciliationRoot'), chip = $('reconciliationChip');
    if(!root || !chip) return;
    if(!mode){ chip.textContent = 'unavailable'; chip.className = 'chip chip-red';
      root.innerHTML = '<p class="op-warning">Custody evidence could not be read. Do not assume reconciliation passed.</p>'; return; }
    const op = mode.operational || {}, promotion = mode.promotion || {};
    const observed = Number(op.testnet_lifecycles || 0) > 0 || Number(op.reconciliation_rate || 0) > 0;
    const passed = observed && promotion.testnet_ready === true;
    chip.textContent = passed ? 'promotion ready' : !observed ? 'not observed' : 'gate blocked';
    chip.className = 'chip ' + (passed ? 'chip-green' : 'chip-red');
    root.closest('.reconciliation-panel').dataset.state = passed ? 'PROMOTION_READY' : 'BLOCKED';
    root.innerHTML = `<div class="reconciliation-grid">
      <div><span>Success rate</span><b>${observed ? (Number(op.reconciliation_rate) * 100).toFixed(1) + '%' : 'No qualifying run reported'}</b></div>
      <div><span>Duplicate orders</span><b>${esc(op.duplicate_orders ?? 'Not reported')}</b></div>
      <div><span>Orphan positions</span><b>${esc(op.orphan_positions ?? 'Not reported')}</b></div>
      <div><span>Safety drills</span><b>${op.safety_drills_passed ? 'PASSED' : 'NOT PASSED'}</b></div></div>`;
    if(!passed) root.insertAdjacentHTML('beforeend',
      '<p class="op-warning">The server promotion verdict is not ready. A recorded reconciliation run alone is not a pass.</p>');
  }

  wireJournalSearch();
  wirePerformanceBreakdown();
  loadPerformanceWorkspace();
  loadSystemWorkspace();
  setInterval(loadSystemWorkspace, 30000);
})();
