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
    link.href = '/static/diagnostics-ui.css?v=2';
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
    /* A ROW PER GATE, with the name and the value in their own columns. These
       ran together as one inline paragraph — "rr 2.41 costs r 0.08 zone type
       SUPPLY bars since break 2" — so the reader had to parse where each
       label ended and its value began, on the panel whose entire job is
       showing what each gate compared. */
    return '<span class="dx-tfacts">' + keys.map(k => {
      const v = Array.isArray(facts[k]) ? facts[k].join(', ') : facts[k];
      const h = human(v);
      return `<span class="dx-tfact"${h.raw ? ` title="raw: ${esc(h.raw)}"` : ''}>` +
        `<b class="dx-tfact-k">${esc(k.replace(/_/g, ' '))}</b>` +
        `<span class="dx-tfact-v">${esc(h.txt)}</span></span>`;
    }).join('') + '</span>';
  }

  /* ── THE ANSWER, BEFORE THE AUDIT ──
     This drawer opened onto nine stages, each with its rule, its detail and up
     to eight fact chips — three thousand characters to answer "why am I in
     this and where did I fill". The ladder is the right record and it stays,
     but it is the WORKING. What an operator wants first is the fill, the
     reason, and the levels; everything else is available one click down.

     Facts are looked up BY KEY across the stages rather than by stage label:
     labels are prose the server may reword, and a summary that silently
     empties when a label changes is worse than no summary. */
  function factOf(t, key) {
    for (const st of (t.stages || [])) {
      const f = st.facts || {};
      if (f[key] !== null && f[key] !== undefined) return f[key];
    }
    return null;
  }

  function summary(t, verdictChip, life) {
    life = life || t.lifecycle || {};
    const num = v => v === null || v === undefined ? null : human(v).txt;
    const order = t.order || {};
    const risk = t.risk || {};

    const fill = order.fill_price != null ? num(order.fill_price)
               : factOf(t, 'fill_price') != null ? num(factOf(t, 'fill_price')) : null;
    const limit = order.limit_price != null ? num(order.limit_price) : null;
    /* What actually happened to this order, in the operator's words. The
       lifecycle code is the authority; the fill price is only a number. */
    const head = fill ? `filled at <b>${esc(fill)}</b>`
      : life.stage === 'ARMED' || order.event === 'PLACED'
        ? `order resting${limit ? ` at <b>${esc(limit)}</b>` : ''} — not filled`
        : 'never entered';

    const entry = num(factOf(t, 'entry'));
    const sl = num(factOf(t, 'sl'));
    const tp = num(factOf(t, 'tp'));
    const rr = num(factOf(t, 'computed_rr') ?? factOf(t, 'recorded_rr'));
    const usd = risk.risk_usd != null ? risk.risk_usd : factOf(t, 'risk_usd');

    /* The engine's sentence ends "· TP 0.17692 · R:R 3.00", which is exactly
       what the numbers line below prints. Two copies of a price on a panel
       being cut for length is the easiest one to drop. */
    const why = String(t.why || '').split(' · ')
      .filter(part => !/^(TP|SL|R:R)/i.test(part.trim())).join(' · ');

    const nums = [
      entry ? `entry ${esc(entry)}` : null,
      sl ? `stop ${esc(sl)}` : null,
      tp ? `target ${esc(tp)}` : null,
      rr ? `${esc(rr)}R if it works` : null,
      usd != null ? `$${esc(Math.round(Number(usd)))} at risk` : null,
    ].filter(Boolean).join(' · ');

    /* The header already says which market and which way. Repeating it here
       cost a line and taught nothing; what this line owes the reader is what
       HAPPENED to the order and how it stands now. */
    const outcome = window.SSFunnel && life.failure_code
      ? SSFunnel.plain(life.failure_code) : (life.failure_code || null);
    return `<div class="dx-sum">
      <div class="dx-sum-head">${head}${outcome
        ? ` <span class="chip ${verdictChip || ''}" title="${
            esc(life.failure_code || '')}">${esc(outcome)}</span>` : ''}</div>
      ${why ? `<div class="dx-sum-why">${esc(humanProse(why))}</div>` : ''}
      ${nums ? `<div class="dx-sum-nums">${nums}</div>` : ''}
    </div>`;
  }

  function render(t) {
    const life = t.lifecycle || {};
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

    /* A stage that FAILED or WARNED is the reason this trade is what it is —
       it stays open. A passing stage is a box ticked, and nine ticked boxes
       are the audit trail, not the answer. */
    const stageHtml = (s, compact) => {
      const st = GLYPH[s.status] ? s.status : 'skip';
      return `<div class="dx-tstage ${st}">
        <span class="dx-tglyph">${GLYPH[st]}</span>
        <span>
          <span class="dx-tlabel">${esc(s.label)}</span>
          <span class="dx-tvalue">${s.value === null || s.value === undefined
            ? 'not recorded' : esc(humanProse(s.value))}</span>
          ${s.expected ? `<span class="dx-texpect">rule: ${esc(humanProse(s.expected))}</span>` : ''}
          ${s.detail ? `<span class="dx-tdetail">${esc(humanProse(s.detail))}</span>` : ''}
          ${compact ? '' : factRow(s.facts)}
        </span>
      </div>`;
    };
    const all = t.stages || [];
    const notable = all.filter(s => s.status === 'fail' || s.status === 'warn');
    const stages = all.map(stageHtml).join('');

    paint(shell(
      esc(String(t.symbol || '').replace('-USD', '')) + ' · ' + esc(t.tf || ''),
      /* The subtitle was the raw composite key —
         "UNIUSDT|4H|REVERSAL|UNIUSDT|4H|SUPPLY|1770811200|setup-v0.15-draft" —
         which is a database identifier printed where a human summary belongs,
         on a drawer now reachable from Command. The summary says what the
         trade WAS; the id stays available as something to copy, because a
         developer chasing a fact still needs it. */
      `${esc(String(t.strategy || '').replace(/_/g, ' ').toLowerCase())} ` +
      `${esc(String(t.direction || '').toLowerCase())}` +
      (t.why ? ' · ' + esc(String(t.why).split(' · ')[0]) : '') +
      `<button class="dx-copyid" type="button" data-copyid="${esc(t.setup_id)}"
               title="copy the internal id for this setup">copy id</button>`,
      `${notes}
      ${summary(t, verdictChip, life)}
      <!-- A check that failed or warned is the reason this trade is what it
           is, so it stays out here. Nine ticked boxes are the audit trail. -->
      ${notable.length ? `<div class="dx-flagged">
        <div class="dx-flagged-t">${notable.length === 1 ? 'One check needs reading'
          : notable.length + ' checks need reading'}</div>
        <div class="dx-trace">${notable.map(x => stageHtml(x, true)).join('')}</div>
      </div>` : ''}
      <!-- Collapsed, not removed. The ladder is the record this app is built
           on and a developer chasing a fact still needs every rung; it just
           should not be the first three thousand characters an operator reads
           to find out where they filled and why.

           The verdict block came in here with it. It used to open the drawer
           with a direction chip, a strategy chip and three sentences that all
           said "it is still open", above a header already reading
           "ADAUSDT · 4H · reversal short". Its one irreducible fact — the
           outcome — is now a chip on the summary line; who a failure is
           attributed to is developer detail and belongs with the ladder. -->
      <details class="dx-all">
        <summary>Every check (${all.length})</summary>
        <div class="dx-verdict">
          <span class="dx-verdict-line">${esc(life.detail || 'no lifecycle verdict recorded')}</span>
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
          guessed: <b>${esc(t.missing_evidence.join(', '))}</b>.</span></div>` : ''}
      </details>`));
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
  /* The id is still one click away for anyone who needs it — it just is not
     the headline any more. Reports success in place rather than a toast: the
     drawer is modal, so a message behind it would be unread. */
  ROOT.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('[data-copyid]');
    if (!b) return;
    const id = b.dataset.copyid;
    const done = () => { const was = b.textContent; b.textContent = 'copied';
                         setTimeout(() => { b.textContent = was; }, 1500); };
    if (navigator.clipboard) navigator.clipboard.writeText(id).then(done, () => {});
    else done();
  });
  document.addEventListener('keydown', e => { if (open && e.key === 'Escape') close(); });

  window.SSTracer = { open: openTrace, close };
})();
