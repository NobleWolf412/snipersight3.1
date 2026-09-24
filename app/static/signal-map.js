/* Shared, server-owned research observation map. It formats states but never
   counts agreement, derives direction, or grades evidence in the browser. */
(() => {
  const esc = value => String(value == null ? '' : value)
    .replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
      '"':'&quot;',"'":'&#39;'}[c]));
  const icons = {ALIGNED:'↑', OPPOSED:'↓', NEUTRAL:'•', MISSING:'!',
    STALE:'⌛', NOT_APPLICABLE:'—'};
  const labels = {ALIGNED:'Aligned', OPPOSED:'Opposed', NEUTRAL:'Neutral',
    MISSING:'Missing', STALE:'Stale', NOT_APPLICABLE:'Unavailable'};
  const when = value => value == null ? 'Not available' :
    new Date(Number(value) * 1000).toISOString().replace('T',' ').slice(0,16) + 'Z';

  function cell(cell, rowKey, idPrefix){
    const state = String(cell && cell.status || 'MISSING').toUpperCase();
    const word = labels[state] || state.replaceAll('_',' ');
    const raw = cell && cell.raw && cell.raw !== '—' ? cell.raw : word;
    const id = `signal-${idPrefix}-${rowKey}-${cell.timeframe}`.replace(/[^a-z0-9_-]/gi,'-');
    const values = Object.entries(cell.values || {}).map(([key,value]) =>
      `<div><dt>${esc(key.replaceAll('_',' '))}</dt><dd>${value == null ? 'Unavailable' : esc(value)}</dd></div>`).join('');
    return `<td data-state="${esc(state)}"><button type="button" class="signal-cell"
        aria-expanded="false" aria-controls="${esc(id)}">
        <span aria-hidden="true">${esc(icons[state] || '•')}</span>
        <b>${esc(raw)}</b><small>${esc(word)}</small></button>
      <div class="signal-cell-detail" id="${esc(id)}" hidden>
        <dl>${values || '<div><dt>Raw values</dt><dd>None reported</dd></div>'}
          <div><dt>Source timeframe</dt><dd>${esc(cell.source_timeframe || cell.timeframe)}</dd></div>
          <div><dt>Confirmed</dt><dd>${esc(when(cell.confirmed_at))}</dd></div>
          <div><dt>Detector</dt><dd>${esc(cell.detector_version || 'Not reported')}</dd></div>
          ${cell.missing_reason ? `<div><dt>Availability</dt><dd>${esc(cell.missing_reason)}</dd></div>` : ''}
        </dl></div></td>`;
  }

  function table(data, {heading='Signal map at decision time', idPrefix='decision', showNotice=true} = {}){
    if(!data || data.availability === 'UNAVAILABLE' || !(data.rows || []).length){
      return `<section class="signal-map signal-map-empty" aria-label="${esc(heading)}">
        <div class="signal-map-head"><h3>${esc(heading)}</h3><span>Research only</span></div>
        <p>${esc(data && data.missing_reason || 'Research observations are unavailable.')}</p>
        <strong>Research observation — did not affect this setup.</strong></section>`;
    }
    const frames = data.timeframes || ['15m','1H','4H','1D'];
    return `<section class="signal-map" aria-label="${esc(heading)}">
      <div class="signal-map-head"><h3>${esc(heading)}</h3><span>Research only</span></div>
      <div class="signal-map-scroll"><table><thead><tr><th scope="col">Evidence family</th>
        ${frames.map(tf => `<th scope="col">${esc(tf)}</th>`).join('')}</tr></thead><tbody>
        ${(data.rows || []).map(row => `<tr data-signal-row><th scope="row"><button type="button" class="signal-row-toggle" aria-expanded="false">${esc(row.label)}</button></th>
          ${frames.map(tf => cell((row.cells || []).find(c => c.timeframe === tf) ||
            {timeframe:tf,status:'MISSING',missing_reason:'No reading returned.'}, row.key, idPrefix)).join('')}</tr>`).join('')}
      </tbody></table></div>
      ${showNotice ? `<p class="signal-map-notice">${esc(data.notice || 'Research observation — did not affect this setup.')}</p>` : ''}
    </section>`;
  }

  function disclosure(data){
    return `<details class="signal-map-disclosure"><summary>Signal map at decision time</summary>
      ${table(data,{idPrefix:'setup-drawer',showNotice:false})}</details>
      <p class="signal-map-notice">${esc(data?.notice || 'Research observation — did not affect this setup.')}</p>`;
  }

  function trade(setupData, currentData){
    const setupId = 'signal-view-setup', nowId = 'signal-view-now';
    return `<section class="trade-signal-map" data-signal-tabs>
      <div class="signal-view-tabs" role="tablist" aria-label="Signal map time">
        <button role="tab" aria-selected="true" aria-controls="${setupId}" id="${setupId}-tab">At setup</button>
        <button role="tab" aria-selected="false" aria-controls="${nowId}" id="${nowId}-tab">Now</button>
      </div>
      <div role="tabpanel" id="${setupId}" aria-labelledby="${setupId}-tab">${table(setupData,{heading:'Signal map at setup',idPrefix:'trade-setup'})}</div>
      <div role="tabpanel" id="${nowId}" aria-labelledby="${nowId}-tab" hidden>${table(currentData,{heading:'Signal map now',idPrefix:'trade-now'})}</div>
    </section>`;
  }

  document.addEventListener('click', event => {
    const detail = event.target.closest('.signal-cell');
    if(detail){
      const panel = document.getElementById(detail.getAttribute('aria-controls'));
      const open = detail.getAttribute('aria-expanded') !== 'true';
      detail.setAttribute('aria-expanded', String(open));
      if(panel) panel.hidden = !open;
      return;
    }
    const rowToggle = event.target.closest('.signal-row-toggle');
    if(rowToggle){
      const row = rowToggle.closest('[data-signal-row]');
      const open = rowToggle.getAttribute('aria-expanded') !== 'true';
      rowToggle.setAttribute('aria-expanded', String(open));
      row.querySelectorAll('.signal-cell').forEach(button => button.setAttribute('aria-expanded', String(open)));
      row.querySelectorAll('.signal-cell-detail').forEach(panel => { panel.hidden = !open; });
      return;
    }
    const tab = event.target.closest('[data-signal-tabs] [role="tab"]');
    if(!tab) return;
    const root = tab.closest('[data-signal-tabs]');
    root.querySelectorAll('[role="tab"]').forEach(button =>
      button.setAttribute('aria-selected', String(button === tab)));
    root.querySelectorAll('[role="tabpanel"]').forEach(panel =>
      panel.hidden = panel.id !== tab.getAttribute('aria-controls'));
  });
  document.addEventListener('keydown', event => {
    const tab = event.target.closest('[data-signal-tabs] [role="tab"]');
    if(!tab || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
    const tabs = [...tab.parentNode.querySelectorAll('[role="tab"]')];
    event.preventDefault();
    tabs[(tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length].click();
    tabs.find(button => button.getAttribute('aria-selected') === 'true').focus();
  });

  window.SSSignalMap = {table, disclosure, trade};
})();
