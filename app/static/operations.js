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
  let commandFreshAt = 0;

  async function runAction(action){
    if(!action) return;
    if(action.external_url){
      window.open(action.external_url, '_blank', 'noopener'); return;
    }
    if(action.command === 'scan'){
      const scan = $('btnScan'); if(scan) scan.click(); return;
    }
    if(action.command === 'reload'){ location.reload(); return; }
    if(action.view){
      try{ sessionStorage.setItem('ss:system-view', action.view); }catch(_){ /* optional */ }
      dispatchEvent(new CustomEvent('ss:workspace-request',
        {detail:{name:'system', view:action.view}}));
    }
    if(action.setup_id){
      try{
        const row = await api('/api/opportunities/' + encodeURIComponent(action.setup_id));
        if(action.route === 'trade'){
          if(window.SSOpenOpportunity) window.SSOpenOpportunity(row);
          else {
            window.SSSelectedOpportunity = row;
            dispatchEvent(new CustomEvent('ss:opportunity-selected', {detail:row}));
            location.hash = 'trade';
          }
          return;
        }
        location.hash = action.route || 'opportunities';
        if(window.SSSelectOpportunity) window.SSSelectOpportunity(action.setup_id);
        return;
      }catch(err){ console.warn('next action setup unavailable', err); }
    }
    if(action.route) location.hash = action.route;
  }

  function paintAction(data){
    const action = data.next_action || {};
    const state = $('nextActionState');
    if(state){
      state.textContent = action.state || 'UNKNOWN';
      state.className = 'chip next-action-state state-' +
        String(action.state || 'unknown').toLowerCase();
    }
    if($('nextActionTitle')) $('nextActionTitle').textContent = action.title || 'No directive available';
    if($('nextActionSummary')) $('nextActionSummary').textContent = action.summary || 'The server did not return a next action.';
    if($('nextActionBot')) $('nextActionBot').textContent = action.bot_handling || 'No bot activity reported.';
    for(const [id, key] of [['nextActionPrimary','primary'],['nextActionSecondary','secondary']]){
      const button = $(id), target = action[key];
      if(!button) continue;
      button.disabled = !target;
      button.textContent = target && target.label || 'Unavailable';
      button.onclick = target ? () => runAction(target) : null;
    }

    const citadel = data.citadel || {};
    if($('citadelState')){
      $('citadelState').textContent = citadel.reachable
        ? (citadel.server_healthy ? 'READY' : citadel.server_state || 'ATTENTION') : 'OFFLINE';
      $('citadelState').className = 'chip ' +
        (citadel.server_healthy ? 'chip-green' : 'chip-amber');
    }
    if($('citadelSummary')) $('citadelSummary').textContent =
      citadel.summary || 'Citadel status is unavailable.';
    if($('citadelOpen')){
      $('citadelOpen').href = citadel.control_url || '#';
      $('citadelOpen').setAttribute('aria-disabled', String(!citadel.control_url));
    }
  }

  function paintCommand(data){
    commandFreshAt = Date.now();
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
    const counts = (data.opportunities || {}).counts || {};
    const ready = Number(counts.READY || 0);
    if($('mSetups')) $('mSetups').textContent = ready;
    if($('mSetupsSub')) $('mSetupsSub').textContent = Number(counts.FORMING || 0)
      ? `${Number(counts.FORMING)} still forming` : '';
    if($('nCommand')) $('nCommand').textContent = ready || '';
    paintAction(data);
    announce();
  }

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

    const a = data.account || {};
    $('riskChip').classList.remove('data-stale');
    $('exposureChip').classList.remove('data-stale');
    $('venueNote').textContent = data.venue === 'PHEMEX_USDT_PERPETUAL'
      ? 'Phemex · perpetual futures' : (data.venue || 'Venue unknown');
    $('riskChip').textContent = `Risk ${usd(a.total_risk_remaining_usd || 0)} free`;
    $('riskChip').title = `${a.risk_per_trade_pct || '—'}% per trade · ` +
      `${usd(a.daily_loss_remaining_usd || 0)} left before the UTC daily halt`;
    $('exposureChip').textContent = `Positions ${a.open_positions || 0} · ` +
      `Orders ${a.working_orders || 0}`;
    const opportunities = data.opportunities || {};
    const counts = opportunities.counts || {};
    const ready = Number(counts.READY || 0);
    const forming = Number(counts.FORMING || 0);
    if($('mSetups')) $('mSetups').textContent = ready;
    if($('mSetupsSub')) $('mSetupsSub').textContent = forming
      ? `${forming} still forming` : '';
    if($('nCommand')) $('nCommand').textContent = ready || '';
    const auto = $('btnAuto');
    if(auto){
      auto.textContent = `Automation: ${name.toLowerCase()}`;
      auto.title = mode.reasons && mode.reasons.length
        ? mode.reasons.map(r => r.summary).join(' ') : MODE_NOTE[name];
    }
    paintAction(data);
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
      if(Date.now() - commandFreshAt < 30000){
        if($('riskChip')){
          $('riskChip').textContent = 'Risk unavailable';
          $('riskChip').classList.add('data-stale');
        }
        if($('exposureChip')){
          $('exposureChip').textContent = 'Exposure unavailable';
          $('exposureChip').classList.add('data-stale');
        }
        console.warn('operations detail unavailable; command state remains current', err);
        return;
      }
      /* THE MODE CHIP IS THE ONLY MODE DISPLAY LEFT, so its failure state
         carries what the deleted statusbar sentence used to say. It is in the
         topbar, which is outside .stage and therefore on every surface —
         which the disposition line is not. */
      const mode = $('modeChip');
      if(mode){
        mode.textContent = 'MODE UNKNOWN';
        mode.className = 'chip chip-red';
        mode.title = 'Execution state unavailable — do not assume orders are disabled';
      }
      /* Publish the FAILURE, do not just stop publishing. Leaving the last
         good payload in place let the disposition line go on describing a
         healthy bot from data that had stopped arriving — a stale sentence
         reads exactly like a current one. The reader announces it loudly, in
         the same sentence the statusbar used to carry. */
      window.SSOperationsData = {unavailable: true};
      paintAction({next_action:{state:'OFFLINE', title:'Cockpit state is unavailable',
        summary:'Reconnect before acting on a trade.',
        bot_handling:'No current backend state can be confirmed.',
        primary:{label:'Retry', command:'reload'}},
        citadel:{reachable:false, server_state:'OFFLINE',
          summary:'Citadel status is unavailable.'}});
      announce();
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
      console.warn('operations read model unavailable', err);
    }
  }
  async function refreshCommand(){
    if(window.SSMarkets && window.SSMarkets.current() !== 'crypto') return;
    try{ paintCommand(await api('/api/command')); }
    catch(err){
      if(Date.now() - commandFreshAt < 30000) return;
      const mode = $('modeChip');
      if(mode){
        mode.textContent = 'MODE UNKNOWN';
        mode.className = 'chip chip-red';
        mode.title = 'Execution state unavailable — do not assume orders are disabled';
      }
      window.SSOperationsData = {unavailable: true};
      paintAction({next_action:{state:'OFFLINE', title:'Cockpit state is unavailable',
        summary:'Reconnect before acting on a trade.',
        bot_handling:'No current backend state can be confirmed.',
        primary:{label:'Retry', command:'reload'}},
        citadel:{reachable:false, server_state:'OFFLINE',
          summary:'Citadel status is unavailable.'}});
      announce();
      console.warn('command read model unavailable', err);
    }
  }
  bindOverviewTabs();
  refreshCommand();
  refresh();
  setInterval(refreshCommand, 10000);
  setInterval(refresh, 15000);
  addEventListener('focus', () => { refreshCommand(); refresh(); });
  addEventListener('ss:market-change', event => {
    if(event.detail && event.detail.market === 'crypto'){
      refreshCommand(); refresh();
    }
  });
})();
