/* Persistent command layer. Every number arrives from /api/operations; this
   module formats it but never recalculates risk, equity, mode or eligibility. */
(() => {
  const $ = id => document.getElementById(id);
  const api = path => window.SSData
    ? SSData.get(path, 0)
    : fetch(path).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  const usd = value => '$' + Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2, maximumFractionDigits: 2});

  const MODE_NOTE = {
    OFF: 'OFF — scans and recommends; dispatch is disabled',
    PAPER: 'PAPER — orders and positions are simulated',
    SHADOW: 'SHADOW — intended orders are recorded; none are submitted',
    TESTNET: 'TESTNET — orders use Phemex test funds',
    LIVE: 'LIVE — real funds; restricted by promotion and risk gates'
  };

  function paint(data){
    window.SSOperationsData = data;
    const mode = data.automation || {};
    const name = mode.mode || 'UNKNOWN';
    const modeChip = $('modeChip');
    modeChip.className = 'chip ' + (name === 'LIVE' ? 'chip-red' :
      name === 'TESTNET' || name === 'SHADOW' ? 'chip-amber' : 'chip-green');
    modeChip.innerHTML = `<span class="orb ${name === 'LIVE' ? 'bad' :
      name === 'TESTNET' || name === 'SHADOW' ? 'warn' : 'good'}"></span>` +
      `<span>${name}</span>`;
    modeChip.title = MODE_NOTE[name] || 'Execution mode unavailable';
    document.body.dataset.automationMode = name;
    const commandMode = $('commandMode');
    if(commandMode){
      commandMode.textContent = name;
      commandMode.className = 'command-mode ' + (name === 'LIVE' ? 'bad' :
        name === 'TESTNET' || name === 'SHADOW' ? 'warn' : 'good');
    }

    const a = data.account || {};
    $('riskChip').classList.remove('data-stale');
    $('exposureChip').classList.remove('data-stale');
    $('venueNote').textContent = data.venue === 'PHEMEX_USDT_PERPETUAL'
      ? 'Phemex · USDT perpetuals' : (data.venue || 'Venue unknown');
    $('riskChip').textContent = `Risk ${usd(a.total_risk_remaining_usd || 0)} free`;
    $('riskChip').title = `${a.risk_per_trade_pct || '—'}% per trade · ` +
      `${usd(a.daily_loss_remaining_usd || 0)} left before the UTC daily halt`;
    $('exposureChip').textContent = `Open ${a.open_positions || 0} · ` +
      `Working ${a.working_orders || 0}`;
    $('executionStatus').textContent = MODE_NOTE[name] || 'Execution mode unavailable';
    const scanner = data.scanner || {};
    const health = data.data || {};
    const opportunities = data.opportunities || {};
    const counts = opportunities.counts || {};
    const ready = Number(counts.READY || 0);
    const forming = Number(counts.FORMING || 0);
    if($('mSetups')) $('mSetups').textContent = ready;
    if($('mSetupsSub')) $('mSetupsSub').textContent = forming
      ? `${forming} still forming` : '';
    if($('nCommand')) $('nCommand').textContent = ready || '';
    if($('commandScanner')) $('commandScanner').textContent =
      `${scanner.state || 'UNKNOWN'} · ${scanner.eligible_markets == null ? '—' : scanner.eligible_markets} ELIGIBLE`;
    if($('commandData')){
      $('commandData').textContent = health.status || 'UNKNOWN';
      $('commandData').className = health.status === 'HEALTHY' ? 'good' :
        health.status === 'BLOCKED' ? 'bad' : 'warn';
    }
    if($('commandExposure')) $('commandExposure').textContent =
      `${a.open_positions || 0} POSITION${Number(a.open_positions) === 1 ? '' : 'S'} · ` +
      `${a.working_orders || 0} WORKING`;
    const auto = $('btnAuto');
    if(auto){
      auto.textContent = `Automation: ${name.toLowerCase()}`;
      auto.title = mode.reasons && mode.reasons.length
        ? mode.reasons.map(r => r.summary).join(' ') : MODE_NOTE[name];
    }
    announce();
  }

  /* THE DISPOSITION LINE IS NOT PAINTED HERE, and this event is why.

     It used to be, and it printed "Bot progress - IMPORT / BTCUSDT" — the raw
     scanner stage, on the one line whose entire job is to answer "what is the
     bot doing" in a sentence. Worse, shell.js held a second writer for the
     same node that reproduced the same expression, so the app had two
     authorities for one sentence and both were wrong.

     shell.js now owns it alone, because that sentence needs BOTH payloads:
     the server's narrative and halt state from here, and the binding
     guardrail clause from /api/portfolio, which this module never sees. It
     reads window.SSOperationsData, so all this has to do is say "there is
     new state" — at the 15s operations cadence rather than shell's 30s. */
  const announce = () => dispatchEvent(new CustomEvent('ss:operations'));

  function bindOverviewTabs(){
    const tabs = [...document.querySelectorAll('[data-overview-tab]')];
    const panels = [...document.querySelectorAll('[data-overview-panel]')];
    if(tabs.length < 2 || panels.length < 2) return;

    const activate = (key, moveFocus) => {
      let activePanel = null;
      for(const tab of tabs){
        const active = tab.dataset.overviewTab === key;
        tab.classList.toggle('on', active);
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if(active && moveFocus) tab.focus();
      }
      for(const panel of panels){
        const active = panel.dataset.overviewPanel === key;
        panel.hidden = !active;
        if(active) activePanel = panel;
      }
      /* A wheel first measured under `hidden` has no usable width. The shell
         owns carousel geometry, so tell it exactly which panel was revealed. */
      dispatchEvent(new CustomEvent('ss:overview-tab', {detail: {panel: activePanel}}));
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(tab.dataset.overviewTab, false));
      tab.addEventListener('keydown', event => {
        if(!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        activate(tabs[next].dataset.overviewTab, true);
      });
    });
  }

  async function refresh(){
    if(window.SSMarkets && window.SSMarkets.current() !== 'crypto') return;
    try{ paint(await api('/api/operations')); }
    catch(err){
      const mode = $('modeChip');
      if(mode){ mode.textContent = 'MODE UNKNOWN'; mode.className = 'chip chip-red'; }
      if($('commandMode')){
        $('commandMode').textContent = 'MODE UNKNOWN';
        $('commandMode').className = 'command-mode bad';
      }
      /* Publish the FAILURE, do not just stop publishing. Leaving the last
         good payload in place let the disposition line go on describing a
         healthy bot from data that had stopped arriving — a stale sentence
         reads exactly like a current one. The reader announces it loudly. */
      window.SSOperationsData = {unavailable: true};
      announce();
      if($('commandScanner')) $('commandScanner').textContent = 'UNAVAILABLE';
      if($('commandData')){
        $('commandData').textContent = 'UNAVAILABLE';
        $('commandData').className = 'bad';
      }
      if($('commandExposure')) $('commandExposure').textContent = 'UNKNOWN';
      if($('riskChip')){
        $('riskChip').textContent = 'Risk unavailable';
        $('riskChip').title = 'Server risk budget is stale or unavailable';
        $('riskChip').classList.add('data-stale');
      }
      if($('exposureChip')){
        $('exposureChip').textContent = 'Exposure unavailable';
        $('exposureChip').title = 'Server position and order counts are stale or unavailable';
        $('exposureChip').classList.add('data-stale');
      }
      if($('executionStatus')) $('executionStatus').textContent =
        'Execution state unavailable — do not assume orders are disabled';
      console.warn('operations read model unavailable', err);
    }
  }
  bindOverviewTabs();
  refresh();
  setInterval(refresh, 15000);
  addEventListener('focus', refresh);
  addEventListener('ss:market-change', event => {
    if(event.detail && event.detail.market === 'crypto') refresh();
  });
})();
