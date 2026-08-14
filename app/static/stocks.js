/* US-stock workspace. Real readiness and synthetic training evidence remain
   separate server-owned tracks; this client formats but never derives prices,
   quantities, decisions, rejection reasons, or results. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  let lastStatus = null;
  let lastTraining = null;
  let loading = null;

  function show(route){
    document.querySelectorAll('[data-stock-view]').forEach(view =>
      view.classList.toggle('on', view.dataset.stockView === route));
    document.querySelectorAll('[data-stock-route]').forEach(button => {
      const here = button.dataset.stockRoute === route;
      button.classList.toggle('on', here);
      button.setAttribute('aria-current', here ? 'page' : 'false');
    });
    const stage = document.querySelector('.stock-stage');
    if(stage) stage.scrollTop = 0;
    load();
  }

  function renderStatus(status){
    lastStatus = status;
    const configured = status.state === 'CONNECTIONS_CONFIGURED';
    $('stockStateChip').textContent = 'Training ready';
    $('stockStateChip').className = 'chip chip-green';
    $('stockNarrative').textContent = configured
      ? 'The synthetic workflow is ready, and both real-data authorities are configured for read-only verification.'
      : 'The synthetic workflow is ready now. Real-market scanning stays locked until Alpaca SIP and Massive are connected.';
    $('stockFooterState').textContent = 'Training workflow ready';

    const ready = status.progress.filter(row => row.state !== 'BLOCKED' && row.state !== 'ACTION_REQUIRED').length;
    $('stockProgressChip').textContent = `${ready} of ${status.progress.length} real steps ready`;
    $('stockProgress').innerHTML = status.progress.map((row, index) => {
      const good = row.state === 'READY_TO_VERIFY' || row.state === 'READY';
      const action = row.state === 'ACTION_REQUIRED';
      return `<div class="stock-progress-row ${good ? 'ready' : action ? 'action' : 'blocked'}">
        <span class="stock-progress-number">${index + 1}</span>
        <div><strong>${esc(row.label)}</strong><small>${esc(row.detail)}</small></div>
        <span class="stock-progress-state">${esc(row.state.replace(/_/g, ' '))}</span>
      </div>`;
    }).join('');
    $('stockBlockers').innerHTML = status.blockers.length
      ? `<ol>${status.blockers.map(reason => `<li>${esc(reason)}</li>`).join('')}</ol>`
      : '<p class="stock-muted">Nothing is blocking real stock scanning.</p>';

    Object.entries(status.providers).forEach(([target, provider]) => {
      const chip = document.querySelector(`[data-stock-provider-state="${target}"]`);
      if(chip){
        chip.textContent = provider.configured ? 'Configured · not verified' : 'Not configured';
        chip.className = 'chip ' + (provider.configured ? 'chip-amber' : '');
      }
      provider.required_fields.forEach(field => {
        const input = document.querySelector(`[data-stock-cred="${target}|${field}"]`);
        if(input) input.placeholder = provider.configured ? '•••••••• stored' : 'not set';
      });
    });
  }

  function setupCard(setup){
    const accepted = setup.state === 'READY';
    const evidence = setup.evidence.map(row =>
      `<li><span>${esc(row.label)}</span><strong>${esc(row.value)}</strong><small>${esc(row.why)}</small></li>`).join('');
    const rejections = setup.rejections.length
      ? `<div class="stock-rejections"><h3>Why the bot rejected it</h3>${setup.rejections.map(reason =>
          `<article><strong>${esc(reason.code.replace(/_/g, ' '))}</strong><p>${esc(reason.detail)}</p></article>`).join('')}</div>`
      : `<div class="stock-accept"><strong>Setup accepted</strong><p>The sample passes every training rule. Open the plan to see exactly what the simulator received.</p></div>`;
    return `<article class="stock-setup-card ${accepted ? 'accepted' : 'rejected'}">
      <header><div><span class="market-eyebrow">${esc(setup.strategy)} · ${esc(setup.timeframe)}</span>
        <h2>${esc(setup.symbol)}</h2><p>${esc(setup.name)}</p></div>
        <span class="chip ${accepted ? 'chip-green' : 'chip-red'}">${esc(setup.state)}</span></header>
      <ul class="stock-evidence">${evidence}</ul>${rejections}
      ${accepted ? `<button class="btn btn-primary" data-stock-open="trade">Inspect simulated trade</button>` : ''}
    </article>`;
  }

  function renderTraining(training){
    lastTraining = training;
    $('stockTrainingDiagnostics').innerHTML = training.diagnostics.map(row =>
      `<div class="stock-diag"><span class="orb ok"></span><div><strong>${esc(row.label)}</strong><small>${esc(row.detail)}</small></div></div>`).join('');
    $('stockSetupList').innerHTML = training.setups.map(setupCard).join('');
    const selected = training.setups.find(row => row.setup_id === training.selected_setup_id);
    const plan = selected && selected.plan;
    const simulation = training.simulation;
    $('stockTrade').innerHTML = plan ? `<div class="stock-trade-layout">
      <section class="panel"><div class="panel-head"><div><span class="market-eyebrow">Selected sample</span><h2 class="t-section">${esc(selected.symbol)} plan</h2></div><span class="chip chip-green">READY</span></div>
        <div class="panel-body"><p class="stock-trade-reason">A 2%+ opening gap held a pullback on elevated relative volume. No earnings or halt exclusion is present in this fixture.</p>
        <div class="stock-plan-grid"><article><span>Side</span><strong>${esc(plan.side)}</strong></article><article><span>Entry</span><strong>$${esc(plan.entry)}</strong></article><article><span>Stop</span><strong>$${esc(plan.stop)}</strong></article><article><span>Target</span><strong>$${esc(plan.target)}</strong></article><article><span>Risk budget</span><strong>$${esc(plan.risk_budget_usd)}</strong></article><article><span>Sample qty</span><strong>${esc(plan.quantity)}</strong></article></div></div></section>
      <section class="panel"><div class="panel-head"><h2 class="t-section">Paper replay</h2><span class="chip">${esc(simulation.state)}</span></div>
        <div class="panel-body stock-replay"><p>Limit filled at <strong>$${esc(simulation.fill.price)}</strong>.</p><p>Target exited at <strong>$${esc(simulation.exit.price)}</strong>.</p><div class="stock-result-metric"><strong>${esc(simulation.r_multiple)}R</strong><span>$${esc(simulation.pnl_usd)} sample P&amp;L</span></div><small>${esc(simulation.cost_model.replace(/_/g, ' '))}</small></div></section>
      </div>` : '<div class="stock-empty"><h2>No accepted fixture setup.</h2></div>';
    $('stockReview').innerHTML = simulation ? `<div class="stock-review-card"><span class="market-eyebrow">Training replay result</span><strong>${esc(simulation.r_multiple)}R</strong><p>${esc(simulation.outcome)} · $${esc(simulation.pnl_usd)} synthetic P&amp;L</p><div class="stock-review-exclusion"><b>Excluded from grading</b><span>${esc(training.disclaimer)}</span></div></div>` : '';
  }

  async function load(){
    if(loading) return loading;
    loading = Promise.all([
      window.SSData.get('/api/stocks/status', 0),
      window.SSData.get('/api/stocks/training', 0),
    ]).then(([status, training]) => { renderStatus(status); renderTraining(training); })
      .catch(error => {
        $('stockStateChip').textContent = 'Stock workspace unavailable';
        $('stockStateChip').className = 'chip chip-red';
        $('stockNarrative').textContent = 'Stock readiness could not be read. Do not treat this as ready.';
        $('stockBlockers').innerHTML = `<p class="stock-error">${esc(error.message || error)}</p>`;
      }).finally(() => { loading = null; });
    return loading;
  }

  async function save(target, button){
    const inputs = [...document.querySelectorAll(`[data-stock-cred^="${target}|"]`)].filter(input => input.value.trim());
    const out = document.querySelector(`[data-stock-result="${target}"]`);
    if(!inputs.length){ out.textContent = 'Nothing typed to save.'; return; }
    button.disabled = true; out.textContent = 'Saving encrypted credentials…';
    try{
      for(const input of inputs){
        const [venue, field] = input.dataset.stockCred.split('|');
        const response = await fetch('/api/credentials', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({venue, field, value: input.value})});
        const body = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(body.detail || `save returned ${response.status}`);
        input.value = '';
      }
      window.SSData.invalidate('/api/stocks/status'); await load();
      out.textContent = 'Saved on this machine. Verification has not run yet.';
    }catch(error){ out.textContent = `Could not save: ${error.message}`; }
    button.disabled = false;
  }

  async function test(target, button){
    const out = document.querySelector(`[data-stock-result="${target}"]`);
    button.disabled = true; out.textContent = 'Running read-only verification…';
    try{
      const response = await fetch('/api/stocks/connections/test', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({target})});
      const body = await response.json().catch(() => ({}));
      if(!response.ok) throw new Error(body.detail || `verification returned ${response.status}`);
      out.textContent = body.detail || (body.ok ? 'Connected.' : 'Connection incomplete.');
      out.classList.toggle('good', !!body.ok); out.classList.toggle('bad', !body.ok);
    }catch(error){ out.textContent = `Verification failed: ${error.message}`; out.classList.remove('good'); out.classList.add('bad'); }
    button.disabled = false;
  }

  document.addEventListener('click', event => {
    const route = event.target.closest('[data-stock-route],[data-stock-open]');
    if(route){ show(route.dataset.stockRoute || route.dataset.stockOpen); return; }
    const saveButton = event.target.closest('[data-stock-save]');
    if(saveButton){ save(saveButton.dataset.stockSave, saveButton); return; }
    const testButton = event.target.closest('[data-stock-test]');
    if(testButton) test(testButton.dataset.stockTest, testButton);
  });
  addEventListener('ss:market-change', event => { if(event.detail && event.detail.market === 'stocks') load(); });
  window.SSStocks = {onShow: load, show, status: () => lastStatus, training: () => lastTraining};
  if(window.SSMarkets && window.SSMarkets.current() === 'stocks') load();
})();
