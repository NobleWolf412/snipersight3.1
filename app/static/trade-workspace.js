/* Trade workspace state is a projection of server-owned opportunity,
   automation and custody records. It labels state; it never decides risk. */
function tradeWorkspaceProjection({halted=false, position=null, ticketState=null, rowState=null} = {}){
  const custodyState = position && position.owner === 'MANUAL_OVERRIDE' ? 'MANUAL_OVERRIDE'
    : position || ticketState === 'POSITION_MANAGED' || rowState === 'POSITION_OPEN'
      ? 'POSITION_MANAGED' : rowState === 'ORDER_WORKING' ? 'ORDER_WORKING' : 'PLANNING';
  return {bannerState: halted ? 'HALTED' : custodyState, custodyState};
}
if(typeof window !== 'undefined') window.SSTradeWorkspaceProjection = tradeWorkspaceProjection;
(() => {
  const evidence = document.getElementById('tradeEvidence');
  const ticket = document.getElementById('ticket');
  const stateRoot = document.getElementById('tradeState');
  const mobileBar = document.getElementById('tradeMobileBar');
  const scrim = document.getElementById('tradeSheetScrim');
  if(!evidence || !ticket || !stateRoot || !mobileBar || !window.SSOpportunityUI) return;
  const api = path => window.SSData ? SSData.get(path, 0) :
    fetch(path, {cache:'no-store'}).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  const mobile = matchMedia('(max-width:900px)');
  let row = window.SSSelectedOpportunity || null;
  let automation = null;
  let managed = [];
  let ticketState = null;
  let sheet = null;
  let sheetReturnFocus = null;
  let selectedSetupId = row && row.setup && row.setup.setup_id || null;
  let selectionError = null;

  const custodyPanel = document.createElement('section');
  custodyPanel.className = 'managed-custody'; custodyPanel.hidden = true;
  custodyPanel.setAttribute('aria-live','polite');
  ticket.querySelector('.panel-head').after(custodyPanel);

  const matchingPosition = () => managed.find(position =>
    selectedSetupId && position.setup_id === selectedSetupId && position.state !== 'CLOSED');

  function projection(){
    const position = matchingPosition();
    const states = tradeWorkspaceProjection({halted: !!(automation && automation.halted),
      position, ticketState, rowState: row && row.state});
    const note = states.bannerState === 'HALTED'
      ? `New entries are halted. ${states.custodyState === 'MANUAL_OVERRIDE'
        ? 'Manual custody and protective status remain in force.'
        : states.custodyState === 'POSITION_MANAGED' ? 'Existing protection remains active.' : ''}`
      : states.custodyState === 'MANUAL_OVERRIDE'
        ? 'Bot discretionary changes are paused; the server reports manual custody.'
        : states.custodyState === 'POSITION_MANAGED'
          ? 'A filled position is under protective management.'
          : states.custodyState === 'ORDER_WORKING' ? 'The selected setup has a working order.'
            : row ? 'Review evidence, levels, cost, and risk before acting.'
              : 'Select a setup or inspect the chart.';
    return [states.bannerState, states.custodyState, note];
  }

  function renderState(){
    const [state, custodyState, note] = projection();
    stateRoot.dataset.state = state;
    stateRoot.innerHTML = `<span>Workspace state</span><b>${state.replaceAll('_',' ')}</b>` +
      `<small>${automation ? note : `${note} Automation state is not confirmed.`}</small>`;
    evidence.dataset.state = row && row.state || 'NONE';
    const action = mobileBar.querySelector('[data-trade-sheet="action"]');
    action.textContent = ['POSITION_MANAGED','MANUAL_OVERRIDE'].includes(custodyState) ? 'Position' : 'Order';
    const position = matchingPosition();
    const managedState = ['POSITION_MANAGED','MANUAL_OVERRIDE'].includes(custodyState) && !!position;
    ticket.dataset.workspaceState = custodyState;
    ticket.classList.toggle('private-managed', managedState);
    custodyPanel.hidden = !managedState;
    if(managedState) custodyPanel.innerHTML = `<span class="op-kicker">Who controls this trade?</span>
      <strong>${position.owner === 'MANUAL_OVERRIDE' ? 'Manual override - bot changes paused' : 'Position managed'}</strong>
      <dl><div><dt>Entry</dt><dd>${window.SSOpportunityUI.px(position.entry)}</dd></div>
      <div><dt>Protective stop</dt><dd>${window.SSOpportunityUI.px(position.stop)}</dd></div>
      <div><dt>Protection</dt><dd>${String(position.protection_status || 'NOT REPORTED').replaceAll('_',' ')}</dd></div></dl>
      <small>Planning and commit controls are unavailable while this exact setup is in custody.</small>`;
  }

  function renderEvidence(){
    evidence.innerHTML = selectionError ? window.SSOpportunityUI.missing(selectedSetupId)
      : window.SSOpportunityUI.tradeEvidence(row);
    renderState();
  }

  function closeSheet(){
    if(!sheet) return;
    sheet = null; syncSheet();
    if(sheetReturnFocus) sheetReturnFocus.focus({preventScroll:true});
  }

  function syncSheet(){
    const active = mobile.matches ? sheet : null;
    document.body.classList.toggle('trade-sheet-evidence', active === 'evidence');
    document.body.classList.toggle('trade-sheet-action', active === 'action');
    if(scrim) scrim.hidden = !active;
    mobileBar.querySelectorAll('[data-trade-sheet]').forEach(button => {
      const on = button.dataset.tradeSheet === active;
      button.setAttribute('aria-expanded', String(on));
      button.classList.toggle('on', on);
    });
    [[evidence,'evidence'],[ticket,'action']].forEach(([panel, name]) => {
      if(!mobile.matches){
        panel.removeAttribute('role'); panel.removeAttribute('aria-modal');
        panel.removeAttribute('aria-hidden'); panel.removeAttribute('inert'); panel.removeAttribute('tabindex');
        panel.removeAttribute('aria-label'); return;
      }
      const open = active === name;
      panel.removeAttribute('role'); panel.removeAttribute('aria-modal');
      panel.setAttribute('aria-label', name === 'evidence' ? 'Trade evidence sheet' : 'Order and position sheet');
      panel.setAttribute('aria-hidden', String(!open));
      panel.toggleAttribute('inert', !open);
      panel.tabIndex = -1;
    });
  }

  mobileBar.addEventListener('click', event => {
    const button = event.target.closest('[data-trade-sheet]');
    if(!button) return;
    sheetReturnFocus = button;
    sheet = sheet === button.dataset.tradeSheet ? null : button.dataset.tradeSheet;
    syncSheet();
    if(sheet) requestAnimationFrame(() =>
      (sheet === 'evidence' ? evidence : ticket).focus({preventScroll:true}));
  });
  document.addEventListener('keydown', event => {
    if(event.key === 'Escape' && sheet){ closeSheet(); return; }
  });
  if(scrim) scrim.addEventListener('click', closeSheet);
  addEventListener('hashchange', () => { if(location.hash !== '#trade'){ sheet = null; syncSheet(); } });
  mobile.addEventListener('change', () => { if(!mobile.matches) sheet = null; syncSheet(); });

  addEventListener('ss:opportunity-selected', event => {
    row = event.detail; selectedSetupId = row && row.setup && row.setup.setup_id || null;
    selectionError = null; renderEvidence(); refreshAuthority();
  });
  addEventListener('ss:opportunity-refreshed', event => {
    const refreshed = event.detail;
    if(refreshed && refreshed.setup && refreshed.setup.setup_id === selectedSetupId){
      row = refreshed; selectionError = null; renderEvidence();
    }
  });
  addEventListener('ss:trade-ticket-state', event => {
    ticketState = event.detail && event.detail.state || null;
    renderState();
  });

  async function refreshAuthority(){
    if(window.SSMarkets && window.SSMarkets.current() !== 'crypto') return;
    try{
      const requests = [api('/api/automation/status'), api('/api/positions/managed')];
      if(selectedSetupId) requests.push(api('/api/opportunities/' + encodeURIComponent(selectedSetupId)));
      const [mode, custody, fresh] = await Promise.all(requests);
      automation = mode;
      managed = custody.items || [];
      if(selectedSetupId){ row = fresh; selectionError = null; }
    }catch(err){
      if(selectedSetupId){ row = null; selectionError = String(err.message || err); }
      else { automation = null; managed = []; }
      console.warn('trade workspace authority unavailable', err);
    }
    renderEvidence();
  }

  renderEvidence();
  syncSheet();
  refreshAuthority();
  setInterval(refreshAuthority, 15000);
  addEventListener('ss:market-change', event => {
    if(event.detail && event.detail.market === 'crypto') refreshAuthority();
  });
})();
