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
  const MODE_SHORT = {
    OFF: 'Recommendations only.', PAPER: 'Simulation only.',
    SHADOW: 'Orders are recorded, not sent.', TESTNET: 'Using test funds.',
    LIVE: 'Real funds active.'
  };

  function paint(data){
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
    const narrative = $('commandNarrative');
    if(narrative){
      narrative.textContent = mode.halted
        ? 'New entries are halted. Existing positions remain under protective management.'
        : `${opportunities.narrative || 'No opportunity decision is available.'} ${MODE_SHORT[name] || ''}`;
    }
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
  }

  async function refresh(){
    try{ paint(await api('/api/operations')); }
    catch(err){
      const mode = $('modeChip');
      if(mode){ mode.textContent = 'MODE UNKNOWN'; mode.className = 'chip chip-red'; }
      if($('commandMode')){
        $('commandMode').textContent = 'MODE UNKNOWN';
        $('commandMode').className = 'command-mode bad';
      }
      if($('commandNarrative')) $('commandNarrative').textContent =
        'Execution state is unavailable. Do not assume order dispatch is disabled.';
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
  refresh();
  setInterval(refresh, 15000);
  addEventListener('focus', refresh);
})();
