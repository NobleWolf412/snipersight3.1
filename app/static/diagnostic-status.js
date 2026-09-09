/* global module */
/* One dated read model for the screen and its copied handover. No actions. */
(function (global) {
  'use strict';
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g,
    c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const date = ts => typeof ts === 'number' && Number.isFinite(ts)
    ? new Date(ts * 1000).toLocaleString(undefined, {timeZoneName: 'short'}) : 'unavailable';
  function lines(s) {
    if (!s) return ['Current health has not been verified.'];
    const a = s.audit, h = s.scanner;
    const result = [s.headline, `Evidence assembled: ${date(s.generated_at)}`,
      `Scanner: ${h.meaning} Last heartbeat: ${date(h.observed_at)}`,
      `Scanner audit: ${a.status} · ${date(a.observed_at)}${a.fresh ? '' : ' · stale or incomplete evidence'}`];
    if (a.accepted_notes.length) result.push(`${a.accepted_notes.length} accepted data notes. No repair is required by these notes alone.`);
    if (a.blockers.length) result.push(`Recorded blockers: ${a.blockers.map(b => b.code || 'unknown').join(', ')}. Review these before considering a restart.`);
    if (a.warnings?.length) result.push(`${a.warnings.length} audit warnings. Review Open issues below for affected markets.`);
    if (s.supervisor) result.push(`Supervisor: ${s.supervisor.verdict || 'UNKNOWN'} · ${date(s.supervisor.observed_at)}. This separate check is not the scanner verdict.`);
    return result;
  }
  function historyText(s) {
    if (!s) return [];
    return [s.history_source.meaning, ...(s.supervisor ? [s.supervisor.detail] : []), ...s.history.flatMap(e => [
      `${e.state === 'recovered' ? 'RECOVERED (scanner progress only)' : 'HISTORICAL'} · ${date(e.observed_at)}`,
      e.detail, e.meaning, e.recovered_at ? `Recovery evidence: ${date(e.recovered_at)}` : '', e.action
    ].filter(Boolean))];
  }
  function render(s) {
    const root = document.getElementById('diagEvidence');
    const history = document.getElementById('diagHistory');
    if (root) root.innerHTML = lines(s).map((line, i) =>
      `<p class="diag-evidence-line${i ? ' dim' : ''}">${esc(line)}</p>`).join('');
    if (!history) return;
    if (!s) { history.textContent = 'History unavailable.'; return; }
    const entries = s.history.map(e => `<article class="diag-history-event">
      <h3>${e.state === 'recovered' ? 'Recovered · scanner resumed' : 'Historical · not a current alert'}</h3>
      <p>${esc(date(e.observed_at))}</p><p>${esc(e.detail)}</p>
      <p>${esc(e.meaning)}</p>${e.recovered_at ? `<p>Recovery evidence: ${esc(date(e.recovered_at))}</p>` : ''}
      <p>${esc(e.action)}</p></article>`).join('');
    history.innerHTML = `<details><summary>Recovered &amp; historical events (${s.history.length})</summary>
      <p>${esc(s.history_source.meaning)}</p>${entries || '<p>No restart events found in this log window.</p>'}
      ${s.history_source.available ? '' : '<p>Supervisor log unavailable; history is incomplete.</p>'}</details>`;
  }
  global.SSDiagnosticStatus = {render, lines, historyText, date};
  if (typeof module !== 'undefined') module.exports = global.SSDiagnosticStatus;
})(typeof window === 'undefined' ? globalThis : window);
