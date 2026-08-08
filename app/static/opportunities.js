/* Setup Radar: compact comparison first, one selected detail second. Capital
   cannot be committed here; the selected server record is handed to Trade. */
(() => {
  const root = document.getElementById('opGroups');
  const detail = document.getElementById('opDetail');
  if(!root || !detail || !window.SSOpportunityUI) return;
  const status = document.getElementById('opStatus');
  const filters = document.getElementById('opFilters');
  const api = path => window.SSData
    ? SSData.get(path, 0)
    : fetch(path).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  const esc = value => String(value == null ? '' : value)
    .replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
      '"':'&quot;',"'":'&#39;'}[c]));
  const label = window.SSOpportunityUI.label;
  const HISTORY = new Set(['BLOCKED','REJECTED','EXPIRED','CANCELLED','CLOSED']);
  const ORDER = ['POSITION_OPEN','ORDER_WORKING','READY','FORMING','WATCHING',
    'BLOCKED','REJECTED','EXPIRED','CANCELLED','CLOSED'];
  let payload = {items: [], summary: {narrative: 'No setup data yet.'}};
  let activeFilter = 'ACTIVE';
  let selectedId = null;
  let selectionMissing = false;
  let returnFocusId = null;
  const mobile = matchMedia('(max-width:900px)');

  function visible(row){
    if(activeFilter === 'ACTIVE') return !HISTORY.has(row.state);
    if(activeFilter === 'HISTORY') return HISTORY.has(row.state);
    return row.state === activeFilter;
  }

  function selected(){
    return payload.items.find(row => row.setup.setup_id === selectedId) || null;
  }

  function paintDetail(){
    const row = selected();
    const visible = !!row || selectionMissing;
    detail.hidden = !visible;
    detail.innerHTML = row ? window.SSOpportunityUI.detail(row) : selectionMissing
      ? window.SSOpportunityUI.missing(selectedId) : '';
    if(visible && mobile.matches) detail.setAttribute('aria-label','Setup detail drawer');
    else detail.removeAttribute('aria-label');
    detail.removeAttribute('role'); detail.removeAttribute('aria-modal');
    document.body.classList.toggle('op-detail-open', visible && mobile.matches);
  }

  function paintCounts(){
    const all = payload.items || [];
    const count = key => key === 'ACTIVE' ? all.filter(row => !HISTORY.has(row.state)).length
      : key === 'HISTORY' ? all.filter(row => HISTORY.has(row.state)).length
      : all.filter(row => row.state === key).length;
    filters.querySelectorAll('[data-op-count]').forEach(node => {
      node.textContent = count(node.dataset.opCount);
    });
  }

  function paint(){
    const rows = (payload.items || []).filter(visible);
    paintCounts();
    const narrative = payload.summary && payload.summary.narrative || 'Scanner state unavailable.';
    status.textContent = `${rows.length} shown · ${narrative}`;
    if(!rows.length){
      root.innerHTML = `<div class="panel op-empty"><span class="op-state">No action</span>
        <h2>No matching setups</h2><p>Scanner continues watching closed candles.</p></div>`;
      if(!selectionMissing) selectedId = null;
      paintDetail();
      return;
    }
    root.innerHTML = ORDER.map(state => {
      const group = rows.filter(row => row.state === state);
      return group.length ? `<section class="op-group"><h2>${esc(label(state))}
        <span>${group.length}</span></h2><div class="op-grid">${group.map(row =>
          window.SSOpportunityUI.card(row, row.setup.setup_id === selectedId)).join('')}</div></section>` : '';
    }).join('');
    if(selectedId && !payload.items.some(row => row.setup.setup_id === selectedId))
      selectionMissing = true;
    paintDetail();
  }

  function choose(id){
    returnFocusId = id;
    selectedId = id;
    selectionMissing = false;
    window.SSSelectedOpportunity = selected();
    paint();
    requestAnimationFrame(() => {
      const target = mobile.matches ? detail.querySelector('.op-detail-close') : detail;
      if(target && target.focus) target.focus({preventScroll:true});
    });
  }

  function closeDetail(){
    const id = returnFocusId || selectedId;
    selectedId = null;
    selectionMissing = false;
    window.SSSelectedOpportunity = null;
    paint();
    requestAnimationFrame(() => {
      const button = [...root.querySelectorAll('.op-review')]
        .find(candidate => candidate.dataset.id === id);
      if(button) button.focus({preventScroll:true});
    });
  }

  function openTrade(row){
    if(!row) return;
    window.SSSelectedOpportunity = row;
    dispatchEvent(new CustomEvent('ss:opportunity-selected', {detail: row}));
    location.hash = 'trade';
    requestAnimationFrame(() => {
      if(window.SSChart) SSChart.open(row.setup.symbol, row.setup.timeframe,
        {setup_id: row.setup.setup_id});
    });
  }

  filters.addEventListener('click', event => {
    const button = event.target.closest('[data-op-filter]');
    if(!button) return;
    activeFilter = button.dataset.opFilter;
    filters.querySelectorAll('button').forEach(candidate => {
      const on = candidate === button;
      candidate.classList.toggle('on', on);
      candidate.setAttribute('aria-pressed', String(on));
    });
    paint();
  });

  root.addEventListener('click', event => {
    const button = event.target.closest('.op-review');
    if(button) choose(button.dataset.id);
  });
  root.addEventListener('keydown', event => {
    const button = event.target.closest('.op-review');
    if(!button || !['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
    const buttons = [...root.querySelectorAll('.op-review')];
    const current = buttons.indexOf(button);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
      : Math.max(0, Math.min(buttons.length - 1,
        current + (event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 1)));
    event.preventDefault();
    buttons[next].focus();
  });
  detail.addEventListener('click', event => {
    if(event.target.closest('.op-detail-close')){
      closeDetail(); return;
    }
    const trace = event.target.closest('[data-op-trace]');
    if(trace && window.SSTracer){ SSTracer.open(trace.dataset.opTrace); return; }
    const button = event.target.closest('.op-open-trade');
    if(button) openTrade(selected());
  });
  detail.addEventListener('keydown', event => {
    if(event.key === 'Escape'){ event.preventDefault(); closeDetail(); return; }
  });
  mobile.addEventListener('change', paintDetail);

  async function refresh(){
    try{
      const wanted = selectedId;
      payload = await api('/api/opportunities?include_history=true');
      selectionMissing = !!wanted && !payload.items.some(item => item.setup.setup_id === wanted);
      if(wanted && !selectionMissing){
        window.SSSelectedOpportunity = selected();
        dispatchEvent(new CustomEvent('ss:opportunity-refreshed', {detail: selected()}));
      }
      paint();
    }
    catch(err){
      status.textContent = 'Setup Radar unavailable';
      root.innerHTML = `<div class="panel op-empty bad"><span class="op-state">Data degraded</span>
        <h2>Opportunity data unavailable</h2><p>No setup is actionable.</p></div>`;
      selectedId = null;
      paintDetail();
      console.warn('opportunities unavailable', err);
    }
  }
  refresh();
  setInterval(refresh, 30000);
})();
