/* Per-setup trace drawer — "why didn't THIS one fire?".

   Ported from snipersight-trading's PipelineTracer (docs/SALVAGE §4.3). The
   funnel answers the aggregate question; this answers the one an operator
   actually asks, about the single setup in front of them.

   The discipline worth copying from the source is in its docstring: when a
   trace cannot be produced it renders an explicit amber state rather than
   degrading silently. An empty drawer reads as "this setup sailed through",
   which is the exact opposite of "we have no idea what happened to it". So:

     · An unknown setup id is a 404 from the API and an amber panel here.
     · A failed fetch prints the endpoint and the status.
     · Every stage carries the ACTUAL value the gate compared — the R:R against
       the minimum, the regime the playbook was chosen for, the equity the risk
       authority sized against. A ladder of bare ticks would tell the operator
       the gates ran, not what they decided.

   Public: window.SSTracer.open(setupId) / .close() */
(() => {
  'use strict';

  const ROOT = document.getElementById('tracerRoot');
  if (!ROOT) return;

  if (!document.getElementById('dx-css')) {
    const link = document.createElement('link');
    link.id = 'dx-css';
    link.rel = 'stylesheet';
    link.href = '/static/diagnostics-ui.css?v=1';
    document.head.appendChild(link);
  }

  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));

  /* Numbers said the way a person reads them, raw values one hover away.
     The drawer printed epochs (`confirmed at 1785470400`) and venue-precision
     decimals (`stop distance 0.2140863565`) — true, and unreadable. Analysts
     keep the exact value in the tooltip; everyone else gets a clock time and
     a sane number of digits. */
  const looksEpoch = s => /^1[5-9]\d{8}$/.test(s);   // seconds, ~2017-2033
  const fmtEpoch = s => new Date(+s * 1000).toLocaleString(undefined,
    { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  const fmtNum = s => {
    const n = +s, a = Math.abs(n);
    const dp = a >= 1000 ? 2 : a >= 1 ? 4 : 6;
    return n.toLocaleString(undefined, { maximumFractionDigits: dp });
  };
  // one fact value -> {txt, raw}; raw non-null only when we changed something
  function human(v) {
    const s = String(v);
    if (looksEpoch(s)) return { txt: fmtEpoch(s), raw: s };
    if (/^-?\d+\.\d{5,}$/.test(s)) return { txt: fmtNum(s), raw: s };
    return { txt: s, raw: null };
  }
  // prose with long decimals or epochs embedded in it
  const humanProse = s => String(s)
    .replace(/-?\d+\.\d{5,}/g, m => fmtNum(m))
    .replace(/1[5-9]\d{8}/g, m => fmtEpoch(m));

  // Pass / fail / warn / pending / skip, straight from the API. `skip` is
  // deliberately an em-dash and not a cross: a stage with no fact means the
  // pipeline stopped upstream, and marking it failed would blame execution for
  // a decision the risk authority made.
  const GLYPH = { pass: '✓', fail: '✗', warn: '!', pending: '◌', skip: '—' };

  let open = false;
  let lastFocus = null;

  /* ---------- chrome ---------- */

  function shell(title, sub, body) {
    return `<div class="dx-scrim" data-close="1"></div>
      <aside class="dx-drawer" role="dialog" aria-modal="true" aria-label="Setup trace">
        <div class="dx-drawer-head">
          <span class="dx-drawer-title">${title}</span>
          <button class="btn dx-drawer-x" data-close="1">Close</button>
          <span class="dx-drawer-sub">${sub}</span>
        </div>
        <div class="dx-drawer-body">${body}</div>
      </aside>`;
  }

  function paint(html) { ROOT.innerHTML = html; open = true; }

  function close() {
    ROOT.innerHTML = '';
    open = false;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
  }

  /* ---------- states that are not a trace ---------- */

  function notFound(setupId, detail) {
    paint(shell('Trace unavailable', esc(setupId),
      `<div class="dx-note">◌ no trace recorded for this setup
        <span class="dx-note-what">${esc(detail || 'The store has no setup fact with this id.')}
        This is not a setup that passed silently — it is a setup the fact store
        cannot find. Nothing below it can be shown, so nothing is shown.</span>
      </div>`));
  }

  function failed(setupId, msg) {
    paint(shell('Trace unavailable', esc(setupId),
      `<div class="dx-fail"><b>request failed</b>
        <code>${esc(msg)}</code>
        <span class="dx-fail-what">The trace could not be loaded. This drawer is
        empty because the request failed, <em>not</em> because the setup passed
        every gate.</span></div>`));
  }

  /* ---------- the trace ---------- */

  function factRow(facts) {
    const keys = Object.keys(facts || {}).filter(k => facts[k] !== null && facts[k] !== undefined);
    if (!keys.length) return '';
    return '<span class="dx-tfacts">' + keys.map(k => {
      const v = Array.isArray(facts[k]) ? facts[k].join(', ') : facts[k];
      const h = human(v);
      return `<span class="dx-tfact"${h.raw ? ` title="raw: ${esc(h.raw)}"` : ''}><b>${
        esc(k.replace(/_/g, ' '))}</b> ${esc(h.txt)}</span>`;
    }).join('') + '</span>';
  }

  function render(t) {
    const life = t.lifecycle || {};
    const dirChip = t.direction === 'SHORT' ? 'chip-red' : 'chip-green';
    const verdictChip = life.failure_code === 'WINNER' ? 'chip-green'
      : (life.classification === 'DECISION' ? 'chip-red' : 'chip-amber');

    // Conditions worth saying out loud before the ladder, because they change
    // how every number below should be read.
    let notes = '';
    if (!t.in_baseline) {
      notes += `<div class="dx-note">◌ outside the active forward window
        <span class="dx-note-what">This setup was recorded before the current
        <span class="term" data-t="baseline">baseline</span> started, so it is
        history rather than part of the record being accumulated now. It is
        shown in full — it is just not counted in the funnel above.</span></div>`;
    }
    if ((t.stale_versions || []).length) {
      notes += `<div class="dx-note">◌ recorded by an older engine
        <span class="dx-note-what">${t.stale_versions.map(v =>
          `The ${esc(v.kind)} fact came from <b>${esc(v.recorded)}</b>; the engine now runs
           <b>${esc(v.current)}</b>.`).join(' ')}
        The thresholds it was judged against may not be the ones running today.
        See <span class="term" data-t="algoVersion">engine version</span>.</span></div>`;
    }

    const stages = (t.stages || []).map(s => {
      const st = GLYPH[s.status] ? s.status : 'skip';
      return `<div class="dx-tstage ${st}">
        <span class="dx-tglyph">${GLYPH[st]}</span>
        <span>
          <span class="dx-tlabel">${esc(s.label)}</span>
          <span class="dx-tvalue">${s.value === null || s.value === undefined
            ? 'not recorded' : esc(humanProse(s.value))}</span>
          ${s.expected ? `<span class="dx-texpect">rule: ${esc(humanProse(s.expected))}</span>` : ''}
          ${s.detail ? `<span class="dx-tdetail">${esc(humanProse(s.detail))}</span>` : ''}
          ${factRow(s.facts)}
        </span>
      </div>`;
    }).join('');

    paint(shell(
      esc(String(t.symbol || '').replace('-USD', '')) + ' · ' + esc(t.tf || ''),
      esc(t.setup_id),
      `${notes}
      <div class="dx-verdict">
        <span class="chip ${dirChip}">${esc(t.direction || '—')}</span>
        <span class="chip">${esc(String(t.strategy || 'unknown').replace('_', ' '))}</span>
        <span class="chip ${verdictChip}">${esc(life.failure_code || 'unknown')}</span>
        ${t.rank != null ? `<span class="chip"><span class="term" data-t="rank">rank</span> ${esc(t.rank)}</span>` : ''}
        <span class="dx-verdict-line">${esc(life.detail || 'no lifecycle verdict recorded')}</span>
        ${t.why ? `<span class="dx-why"><b>why this trade</b>${esc(t.why)}</span>` : ''}
        <span class="dx-verdict-owner">${life.failure_owner
          ? 'attributed to ' + esc(String(life.failure_owner).replace(/_/g, ' ').toLowerCase())
          : 'no failure to attribute'}${life.classification
          ? ' · ' + esc(life.classification.replace(/_/g, ' ').toLowerCase()) : ''}</span>
      </div>
      <div class="dx-trace">${stages || '<div class="dx-empty">no stages recorded</div>'}</div>
      ${(t.missing_evidence || []).length ? `<div class="dx-note" style="margin-top:var(--md)">
        ◌ some evidence was never captured
        <span class="dx-note-what">These inputs were not retained by the facts
        this trace is built from, so they are shown as missing rather than
        guessed: <b>${esc(t.missing_evidence.join(', '))}</b>.</span></div>` : ''}`));
  }

  /* ---------- api ---------- */

  async function openTrace(setupId) {
    if (!setupId) return;
    lastFocus = document.activeElement;
    paint(shell('Trace', esc(setupId), '<div class="dx-load">reading the trace…</div>'));
    // setup ids contain '|' and the symbol, so they must be encoded rather
    // than pasted into the path.
    const path = '/api/setup-trace/' + encodeURIComponent(setupId);
    let r;
    try {
      r = await fetch(path);
    } catch (err) {
      failed(setupId, path + ' → ' + err);
      return;
    }
    if (r.status === 404) {
      const d = await r.json().catch(() => ({}));
      notFound(setupId, d.detail);
      return;
    }
    if (!r.ok) { failed(setupId, path + ' → HTTP ' + r.status); return; }
    try {
      render(await r.json());
    } catch (err) {
      failed(setupId, 'malformed response — ' + err);
    }
  }

  /* ---------- events ---------- */

  ROOT.addEventListener('click', e => { if (e.target.closest('[data-close]')) close(); });
  document.addEventListener('keydown', e => { if (open && e.key === 'Escape') close(); });

  window.SSTracer = { open: openTrace, close };
})();
