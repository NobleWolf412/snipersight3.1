/* Stock-native workspace foundation.  It renders only server-owned readiness
   and connection results.  No counts, prices, sessions or setups are invented
   while their stock authorities do not exist. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  let lastStatus = null;
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
    if(route === 'system') load();
  }

  function render(status){
    lastStatus = status;
    const configured = status.state === 'CONNECTIONS_CONFIGURED';
    $('stockStateChip').textContent = configured ? 'Connections configured' : 'Setup required';
    $('stockStateChip').className = 'chip ' + (configured ? 'chip-amber' : 'chip-red');
    $('stockNarrative').textContent = configured
      ? 'Both authorities are configured. Verify them before the first stock universe is imported.'
      : 'The stock scout is isolated and waiting for its market authorities. Crypto keeps running independently.';
    $('stockFooterState').textContent = configured ? 'Ready to verify connections' : 'Stock setup required';

    const ready = status.progress.filter(row => row.state !== 'BLOCKED' && row.state !== 'ACTION_REQUIRED').length;
    $('stockProgressChip').textContent = `${ready} of ${status.progress.length} ready`;
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
      : '<p class="stock-muted">Nothing is blocking the stock scout.</p>';

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

  async function load(){
    if(loading) return loading;
    loading = window.SSData.get('/api/stocks/status', 0)
      .then(render)
      .catch(error => {
        $('stockStateChip').textContent = 'Status unavailable';
        $('stockStateChip').className = 'chip chip-red';
        $('stockNarrative').textContent = 'Stock readiness could not be read. Do not treat this as ready.';
        $('stockBlockers').innerHTML = `<p class="stock-error">${esc(error.message || error)}</p>`;
      })
      .finally(() => { loading = null; });
    return loading;
  }

  async function save(target, button){
    const inputs = [...document.querySelectorAll(`[data-stock-cred^="${target}|"]`)]
      .filter(input => input.value.trim());
    const out = document.querySelector(`[data-stock-result="${target}"]`);
    if(!inputs.length){ out.textContent = 'Nothing typed to save.'; return; }
    button.disabled = true;
    out.textContent = 'Saving encrypted credentials…';
    try{
      for(const input of inputs){
        const [venue, field] = input.dataset.stockCred.split('|');
        const response = await fetch('/api/credentials', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({venue, field, value: input.value}),
        });
        const body = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(body.detail || `save returned ${response.status}`);
        input.value = '';
      }
      window.SSData.invalidate('/api/stocks/status');
      window.SSData.invalidate('/api/credentials');
      await load();
      out.textContent = 'Saved on this machine. Verification has not run yet.';
    }catch(error){ out.textContent = `Could not save: ${error.message}`; }
    button.disabled = false;
  }

  async function test(target, button){
    const out = document.querySelector(`[data-stock-result="${target}"]`);
    button.disabled = true;
    out.textContent = 'Running read-only verification…';
    try{
      const response = await fetch('/api/stocks/connections/test', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({target}),
      });
      const body = await response.json().catch(() => ({}));
      if(!response.ok) throw new Error(body.detail || `verification returned ${response.status}`);
      out.textContent = body.detail || (body.ok ? 'Connected.' : 'Connection incomplete.');
      out.classList.toggle('good', !!body.ok);
      out.classList.toggle('bad', !body.ok);
    }catch(error){
      out.textContent = `Verification failed: ${error.message}`;
      out.classList.remove('good'); out.classList.add('bad');
    }
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
  addEventListener('ss:market-change', event => {
    if(event.detail && event.detail.market === 'stocks') load();
  });

  window.SSStocks = {onShow: load, show, status: () => lastStatus};
  if(window.SSMarkets && window.SSMarkets.current() === 'stocks') load();
})();
