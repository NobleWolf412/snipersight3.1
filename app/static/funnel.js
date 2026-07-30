/* Bottleneck funnel — "why is nothing firing?", answered in one sentence.

   Ported from snipersight-trading's GauntletBreakdown (docs/SALVAGE §4.2). The
   thing worth porting was never the three-column chrome; it was the insight
   pill. A flat list of rejection counts is a wall of numbers that an operator
   has to rank in their head. This surface does the ranking, names the single
   largest drop-off in plain English, and links to the surface that addresses
   it. With 88% of rejections at one stage, a bottleneck pill would have
   surfaced that on day one.

   House rules honoured here:
     · Loud fallback. A failed fetch prints the endpoint and the status. It
       never renders a confident-looking zero, and it never renders an empty
       state that could be misread as "all clear".
     · One authority per number. Every count is read from an API field. The
       only arithmetic performed in this file is subtraction between two API
       numbers to get a drop-off, and the definitional identity
       candidates = validated + rejected_candidates, which is stated on screen
       rather than hidden.
     · Vanilla, no build, no framework, no CDN. */
(() => {
  'use strict';

  const ROOT = document.getElementById('funnelRoot');
  if (!ROOT) return;                       // not the shell — nothing to mount into

  /* ---------- boot ---------- */

  // Each module injects the shared diagnostics stylesheet itself so it can be
  // cached and broken independently of ss.css, which another surface owns.
  if (!document.getElementById('dx-css')) {
    const link = document.createElement('link');
    link.id = 'dx-css';
    link.rel = 'stylesheet';
    link.href = '/static/diagnostics-ui.css?v=1';
    document.head.appendChild(link);
  }

  // Defensive boot for the wizard. shell.html now carries its own <script> tag
  // for it, but it did not always, and the shell is owned elsewhere. wizard.js
  // early-returns if it has already registered, so loading it twice is a
  // no-op rather than a double-bound Diagnose button.
  if (!window.SSWizard && !document.querySelector('script[data-dx-wizard]')) {
    const s = document.createElement('script');
    s.src = '/static/wizard.js?v=1';
    s.dataset.dxWizard = '1';
    document.head.appendChild(s);
  }

  /* ---------- plain language ----------
     Every machine reason the operator can see gets a sentence a non-expert can
     act on, plus the surface that addresses it. A code with no entry falls back
     to a de-underscored version of itself and no CTA — guessing at a meaning we
     do not have would be worse than showing the raw code. */

  const SETUP_SURFACE  = { href: '#setup',       label: 'Scanner Setup' };
  const CHART_SURFACE  = { href: '#chart',       label: 'Chart' };
  const RESULTS_SURF   = { href: '#results',     label: 'Results' };
  const COMMAND_SURF   = { href: '#command',     label: 'Command' };
  const DIAG_SURFACE   = { href: '#diagnostics', label: 'Diagnostics' };

  const REASONS = {
    /* --- the scanner's own candidate gates (engine/setups.py) --- */
    NO_ELIGIBLE_PLAYBOOK: {
      plain: 'no strategy covers that market condition',
      means: 'The zone was real and price reached it, but none of the enabled ' +
             'strategies trades that kind of zone in that market regime, so no ' +
             'trade idea was ever built.',
      cta: SETUP_SURFACE },
    RR_BELOW_MINIMUM: {
      plain: 'the target was not far enough away to justify the stop',
      means: 'The trade idea was built, but the reward was small relative to ' +
             'the risk, so it was dropped before it became a setup.',
      cta: SETUP_SURFACE },
    UNECONOMIC_AFTER_COSTS: {
      plain: 'the move was too small to survive fees and slippage',
      means: 'The distance to the stop was so tight that trading costs would ' +
             'have eaten the edge. The engine refuses these rather than book ' +
             'a trade it expects to lose to friction.',
      cta: SETUP_SURFACE },
    ATR_UNAVAILABLE: {
      plain: 'there was not enough price history to measure volatility',
      means: 'The stop is placed using recent volatility. Without it the ' +
             'engine cannot size a stop honestly, so it declines.',
      cta: DIAG_SURFACE },
    NO_CAUSAL_TARGET: {
      plain: 'there was no structure ahead to aim the target at',
      means: 'Targets are placed at levels the market has actually respected. ' +
             'With nothing ahead, any target would have been invented.',
      cta: CHART_SURFACE },
    INVALID_BRACKET: {
      plain: 'the stop came out on the wrong side of the entry',
      means: 'The entry, stop and target did not form a valid trade. This is a ' +
             'geometry fault, not a market condition.',
      cta: DIAG_SURFACE },

    /* --- the risk authority (engine/risk.py) --- */
    OPERATOR_HALT: {
      plain: 'you halted the scanner, so nothing was sized',
      means: 'The halt blocks new entries only; open positions still settle.',
      cta: SETUP_SURFACE },
    DATA_HEALTH_BLOCKED: {
      plain: 'the data audit found a fault, so sizing was blocked',
      means: 'The engine will not size trades on data it cannot vouch for.',
      cta: DIAG_SURFACE },
    STRATEGY_DISABLED: {
      plain: 'that strategy is switched off',
      means: 'The setup was valid, but the strategy that produced it is ' +
             'disabled in Scanner Setup.',
      cta: SETUP_SURFACE },
    DAILY_LOSS_HALT: {
      plain: "the day's loss limit had already been hit",
      means: 'No new entries open until the next day. This is the automatic ' +
             'halt working, not a fault.',
      cta: SETUP_SURFACE },
    NOT_IN_POINT_IN_TIME_UNIVERSE: {
      plain: 'the token was not in the tradeable list when the setup confirmed',
      means: 'Membership is judged at the moment the setup confirmed, not now. ' +
             'A token that qualifies today does not retroactively qualify.',
      cta: SETUP_SURFACE },
    INVALID_STOP_DISTANCE: {
      plain: 'the stop sat on top of the entry, so no size could be computed',
      means: 'Position size comes from the distance to the stop. A zero ' +
             'distance would mean an infinite position.',
      cta: DIAG_SURFACE },
    SHORT_UNSUPPORTED_COINBASE_SPOT: {
      plain: 'the venue cannot short — it is a spot market',
      means: 'Short setups need a venue that supports them. On spot you can ' +
             'only buy, so short ideas are recorded and refused.',
      cta: SETUP_SURFACE },
    PARENT_CLOSED: {
      plain: 'the position it was adding to had already closed',
      means: 'This was a scale-in. With the original trade gone there was ' +
             'nothing to add to.',
      cta: RESULTS_SURF },
    CONCURRENT_LIMIT: {
      plain: 'the account was already at its maximum number of open trades',
      means: 'A cap on simultaneous positions. Good setups are refused while ' +
             'it is full — that is the cap doing its job.',
      cta: SETUP_SURFACE },
    EXPOSURE_LIMIT: {
      plain: 'taking it would have pushed total open risk past the cap',
      means: 'Each trade risks a fixed slice of the account and the total is ' +
             'capped. This setup did not fit in the remaining budget.',
      cta: SETUP_SURFACE },
    LEVERAGE_CAP: {
      plain: 'the position needed more leverage than the venue allows',
      means: 'The stop was far enough away that a correctly sized position ' +
             'would have exceeded the leverage limit.',
      cta: SETUP_SURFACE },
    SPOT_CASH_CAP: {
      plain: 'buying it outright needed more cash than the account holds',
      means: 'On a spot venue there is no borrowing, so a position cannot ' +
             'exceed the cash available.',
      cta: SETUP_SURFACE },
    STOP_BEYOND_LIQUIDATION: {
      plain: 'the stop sat past the point where the exchange would force-close it',
      means: 'The stop has to sit safely inside the liquidation price or the ' +
             'exchange closes the position first.',
      cta: SETUP_SURFACE },
    BELOW_MIN_NOTIONAL: {
      plain: "the position came out smaller than the exchange's minimum order",
      means: 'Correct sizing produced an order too small to place.',
      cta: SETUP_SURFACE },
    WITHIN_LIMITS: {
      plain: 'every risk rule passed',
      means: 'The risk authority approved this one in full.',
      cta: null },

    /* --- lifecycle outcomes (engine/telemetry.py) --- */
    RISK_REJECTED: {
      plain: 'the risk authority refused to size it',
      means: 'The setup was valid but a portfolio rule blocked it. Open the ' +
             'trace on any one of them to see which rule.',
      cta: SETUP_SURFACE },
    ENTRY_NOT_FILLED: {
      plain: 'price never came back to the entry before the order expired',
      means: 'The order rested at the entry and price walked away instead of ' +
             'returning. The idea may have been right and still paid nothing.',
      cta: CHART_SURFACE },
    STOP_LOSS: {
      plain: 'price hit the stop before the target',
      means: 'A normal losing trade. This is expected attrition, not a fault — ' +
             'what matters is the rate, which Results tracks.',
      cta: RESULTS_SURF },
    TIMEOUT_EXIT: {
      plain: 'neither target nor stop was reached inside the holding limit',
      means: 'The trade went nowhere and was closed on time. Frequent timeouts ' +
             'usually mean targets are too far away.',
      cta: RESULTS_SURF },
    LOSING_EXIT: {
      plain: 'it closed at a loss',
      means: 'Closed below breakeven for a reason other than the stop.',
      cta: RESULTS_SURF },
    COSTS_ERASED_EDGE: {
      plain: 'it was profitable before fees and slippage, and not after',
      means: 'The direction was right and the move was too small to pay for ' +
             'itself. This points at entry and target placement, not at ' +
             'picking the wrong side.',
      cta: RESULTS_SURF },
    OPEN_POSITION: {
      plain: 'it is still open, so there is no result yet',
      means: 'Not a failure. It simply has not finished.',
      cta: COMMAND_SURF },
    WAITING_FOR_FILL: {
      plain: 'the order is live and waiting for price',
      means: 'Not a failure. The entry window is still open.',
      cta: COMMAND_SURF },
    AWAITING_RISK: {
      plain: 'the risk authority has not ruled on it yet',
      means: 'The setup validated but no sizing decision has been recorded. ' +
             'On a live scanner this clears within a cycle.',
      cta: DIAG_SURFACE },
    WINNER: {
      plain: 'closed with a profit after costs',
      means: 'Survived every gate and paid.',
      cta: RESULTS_SURF }
  };

  // Reason codes arrive parameterised, e.g. CONCURRENT_LIMIT(2). Strip the
  // argument to look the sentence up, but keep the original on screen.
  const baseCode = c => String(c).split('(')[0];
  const lookup = c => REASONS[baseCode(c)] || null;
  const plainOf = c => (lookup(c) || {}).plain ||
    String(c).replace(/_/g, ' ').toLowerCase();

  // Shared with wizard.js, which needs the same sentences. Exposed rather than
  // duplicated; wizard.js still guards for its absence so neither module can
  // take the other down.
  window.SSFunnel = { explain: c => lookup(c), plain: plainOf };

  /* ---------- the funnel model ----------
     Ordered exactly as a candidate travels. Each stage names the API field it
     reads, so there is one authority per number and it is visible in the source
     rather than buried in a formula. */
  const STAGES = [
    { key: 'candidates',    label: 'Candidates',
      blurb: 'zones price actually reached' },
    { key: 'validated',     label: 'Validated', term: 'setup',
      blurb: 'became a real trade idea' },
    { key: 'risk_approved', label: 'Risk approved', term: 'riskPerTrade',
      blurb: 'the risk authority agreed to size' },
    { key: 'order_placed',  label: 'Order placed',
      blurb: 'an entry order was simulated' },
    { key: 'filled',        label: 'Filled',
      blurb: 'price came back and the order filled' },
    { key: 'closed',        label: 'Closed',
      blurb: 'reached a final result' },
    { key: 'winners',       label: 'Winners', term: 'rMultiple',
      blurb: 'closed positive after costs' }
  ];

  // What the drop into each stage means, as a sentence. `n` and `prev` are
  // filled in by the caller.
  const DROP_COPY = {
    validated:     (n, p) => `${n} of ${p} candidates never became a setup`,
    risk_approved: (n, p) => `${n} of ${p} setups were refused by the risk authority`,
    order_placed:  (n, p) => `${n} of ${p} approved setups never became an order`,
    filled:        (n, p) => `${n} of ${p} orders never filled`,
    closed:        (n, p) => `${n} of ${p} filled trades have not finished yet`,
    winners:       (n, p) => `${n} of ${p} closed trades lost or broke even`
  };

  /* ---------- helpers ---------- */
  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
  const fmt = n => Number(n).toLocaleString();
  const pct = (n, d) => d > 0 ? Math.round(100 * n / d) : 0;

  async function api(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(path + ' → HTTP ' + r.status);
    return r.json();
  }

  /* ---------- state ---------- */
  let selected = null;         // stage key the operator clicked, null = follow bottleneck
  let model = null;

  /* ---------- build ---------- */

  function build(tel, ovErr, ov) {
    const f = tel.funnel || {};
    const stageCounts = tel.stages || {};
    const failures = tel.failure_points || {};
    const records = tel.records || [];

    // candidates is the only figure not returned directly. It is a definitional
    // identity, not a re-derivation of a metric — and it is spelled out on
    // screen in the top stage's footer so the arithmetic is never hidden.
    const rejected = f.rejected_candidates || 0;
    const counts = {
      candidates:    rejected + (f.validated || 0),
      validated:     f.validated || 0,
      risk_approved: f.risk_approved || 0,
      order_placed:  f.order_placed || 0,
      filled:        f.filled || 0,
      closed:        f.closed || 0,
      winners:       f.winners || 0
    };

    /* Reason attribution per transition. Candidate rejections come from
       /api/overview's rejection_funnel, which is produced by the same query as
       rejected_candidates and therefore sums to it exactly. The downstream maps
       count every setup in the window, so they are a superset of any one
       transition — the UI says so rather than implying a clean decomposition. */
    const pick = (src, keys) => {
      const out = {};
      for (const k of keys) if (src[k]) out[k] = src[k];
      return out;
    };
    const reasons = {
      candidates:    {},
      validated:     ovErr ? null : (ov.rejection_funnel || {}),
      risk_approved: pick(failures, ['RISK_REJECTED']),
      order_placed:  stageCounts['VALIDATED'] ? { AWAITING_RISK: stageCounts['VALIDATED'] } : {},
      filled:        pick(failures, ['ENTRY_NOT_FILLED']),
      closed:        Object.assign({},
                       stageCounts['OPEN'] ? { OPEN_POSITION: stageCounts['OPEN'] } : {},
                       stageCounts['ORDER PENDING'] ? { WAITING_FOR_FILL: stageCounts['ORDER PENDING'] } : {}),
      winners:       pick(failures, ['STOP_LOSS', 'LOSING_EXIT', 'TIMEOUT_EXIT', 'COSTS_ERASED_EDGE'])
    };
    // Only the candidate transition is an exact decomposition of its drop.
    const exact = { validated: true };

    /* Individual setups that stalled at each stage — the bridge into the
       per-setup tracer. records[] is the most recent slice, never the whole
       window, so it is labelled as a sample and never counted from. */
    const inSample = k => records.filter(r => {
      const code = r.failure_code;
      if (k === 'risk_approved') return r.risk_decision === 'REJECTED';
      if (k === 'order_placed')  return code === 'AWAITING_RISK';
      if (k === 'filled')        return code === 'ENTRY_NOT_FILLED';
      if (k === 'closed')        return code === 'OPEN_POSITION' || code === 'WAITING_FOR_FILL';
      if (k === 'winners')       return ['STOP_LOSS', 'LOSING_EXIT', 'TIMEOUT_EXIT',
                                         'COSTS_ERASED_EDGE'].includes(code);
      return false;
    });

    // Drop-offs, and the largest of them.
    const rows = STAGES.map((s, i) => {
      const prev = i === 0 ? null : counts[STAGES[i - 1].key];
      const n = counts[s.key];
      const drop = prev == null ? 0 : Math.max(0, prev - n);
      return { ...s, n, prev, drop, dropPct: prev ? pct(drop, prev) : 0 };
    });
    let bottleneck = null;
    for (const r of rows) if (r.drop > 0 && (!bottleneck || r.drop > bottleneck.drop)) bottleneck = r;

    return { counts, rows, reasons, exact, bottleneck, inSample,
             ovErr, baseline: tel.baseline, total: counts.candidates };
  }

  /* ---------- render ---------- */

  function renderPill(m) {
    const b = m.bottleneck;
    if (!b) {
      // Genuinely nothing is being lost — say so in the same slot, so the
      // operator learns where the answer always appears.
      const none = m.total === 0;
      return `<div class="dx-bottleneck ${none ? '' : 'ok'}">
        <span class="dx-bn-mark">${none ? '—' : '✓'}</span>
        <span class="dx-bn-copy">
          <span class="dx-bn-kicker">Biggest bottleneck</span>
          <span class="dx-bn-line">${none
            ? 'No candidates recorded in this forward window yet. Nothing has been rejected because nothing has been examined.'
            : 'Nothing is being lost between stages in this window.'}</span>
          <span class="dx-bn-sub">${none
            ? 'run a scan, or wait for the scanner to complete a cycle'
            : fmt(m.total) + ' candidates · no stage is dropping any'}</span>
        </span>
      </div>`;
    }

    const map = m.reasons[b.key] || {};
    const top = Object.entries(map).sort((x, y) => y[1] - x[1])[0] || null;
    const meta = top ? lookup(top[0]) : null;
    const copy = (DROP_COPY[b.key] || ((n, p) => `${n} of ${p} were lost here`))(fmt(b.drop), fmt(b.prev));
    // Amber is attrition; red is reserved for a bottleneck the engine itself
    // owns, which is a different kind of problem from the market saying no.
    const isDefect = top && ['INVALID_BRACKET', 'INVALID_STOP_DISTANCE',
                             'ATR_UNAVAILABLE', 'DATA_HEALTH_BLOCKED'].includes(baseCode(top[0]));
    const cta = meta && meta.cta;

    return `<div class="dx-bottleneck ${isDefect ? 'bad' : ''}">
      <span class="dx-bn-mark">${b.dropPct}%</span>
      <span class="dx-bn-copy">
        <span class="dx-bn-kicker">Biggest bottleneck · ${esc(b.label)}</span>
        <span class="dx-bn-line">${esc(copy)}${top ? ' — ' + esc(plainOf(top[0])) : ''}.</span>
        <span class="dx-bn-sub">${top
          ? esc(top[0]) + ' · ' + fmt(top[1]) + ' of ' +
            fmt(Object.values(map).reduce((s, n) => s + n, 0)) + ' recorded at this stage'
          : 'no reason recorded for this drop'}</span>
      </span>
      ${cta ? `<a class="btn btn-cyan dx-bn-cta" href="${cta.href}">Open ${esc(cta.label)} →</a>` : ''}
    </div>`;
  }

  function renderStages(m) {
    const active = selected || (m.bottleneck && m.bottleneck.key);
    return '<div class="dx-stages">' + m.rows.map(r => {
      // The track is the previous stage's count; the fill is what survived into
      // this one. The visible gap IS the drop-off — that is the whole point.
      // When nothing arrived at all, 100% of nothing survived: a 0%-wide bar
      // over a hatched track would read as total loss, which is a lie about an
      // empty window.
      const width = r.prev == null ? 100 : (r.prev > 0 ? (r.n / r.prev) * 100 : 100);
      const isBn = m.bottleneck && m.bottleneck.key === r.key;
      const name = r.term
        ? `<span class="term" data-t="${r.term}">${esc(r.label)}</span>`
        : esc(r.label);
      return `<button class="dx-stage${active === r.key ? ' on' : ''}${isBn ? ' bottleneck' : ''}${
                r.key === 'winners' ? ' terminal' : ''}" data-stage="${r.key}"
              aria-pressed="${active === r.key}">
        <span class="dx-stage-top">
          <span class="dx-stage-name">${name}</span>
          <span class="dx-stage-drop${r.drop ? '' : ' none'}">${
            r.prev == null ? '' : (r.drop ? '−' + fmt(r.drop) + ' (' + r.dropPct + '%)' : 'no loss')}</span>
          <span class="dx-stage-count">${fmt(r.n)}</span>
        </span>
        <span class="dx-stage-track">
          <span class="dx-stage-fill" style="width:${width.toFixed(2)}%"></span>
          ${isBn ? '<span class="dx-stage-tag">bottleneck</span>' : ''}
        </span>
        <span class="dx-stage-foot">
          <span>${esc(r.blurb)}</span>
          <span style="margin-left:auto">${
            r.key === 'candidates'
              ? fmt(m.counts.validated) + ' validated + ' + fmt(m.counts.candidates - m.counts.validated) +
                ' rejected'
              : pct(r.n, m.total) + '% of all candidates'}</span>
        </span>
      </button>`;
    }).join('') + '</div>';
  }

  function renderDetail(m) {
    const key = selected || (m.bottleneck && m.bottleneck.key) || 'validated';
    const row = m.rows.find(r => r.key === key);
    const map = m.reasons[key];
    let html = `<div class="dx-detail"><div class="dx-detail-head">
      <span>Why they died at ${esc(row ? row.label : key)}</span></div>`;

    if (map === null) {
      // /api/overview failed: this stage's reasons are genuinely unknown. Say
      // which call failed instead of printing an empty list.
      html += `<div class="dx-fail"><b>reason breakdown unavailable</b>
        <code>${esc(m.ovErr)}</code>
        <span class="dx-fail-what">The stage counts above are still live. Only the
        per-reason split for this stage could not be loaded.</span></div>`;
    } else {
      const rows = Object.entries(map).sort((a, b) => b[1] - a[1]);
      if (!rows.length) {
        html += `<div class="dx-empty">Nothing recorded at this stage in this
          window${row && row.drop ? ' — the ' + fmt(row.drop) +
          ' lost here carry no recorded reason code' : ''}.</div>`;
      } else {
        html += rows.map(([code, n]) => {
          const meta = lookup(code);
          return `<div class="dx-reason">
            <span class="dx-reason-code">${esc(code)}</span>
            <span class="dx-reason-n">${fmt(n)}</span>
            <span class="dx-reason-plain">${esc(meta ? meta.means : plainOf(code))}</span>
          </div>`;
        }).join('');
        const sum = rows.reduce((s, [, n]) => s + n, 0);
        if (!m.exact[key] && row && row.drop && sum !== row.drop) {
          html += `<div class="dx-sample-note">These counts cover every setup
            recorded in this window, so they need not sum to the ${fmt(row.drop)}
            lost at this stage.</div>`;
        }
      }
    }

    // Individual setups → the per-setup trace. This is the hand-off from
    // "why is nothing firing?" to "why didn't THIS one fire?".
    const sample = m.inSample(key).slice(0, 10);
    if (sample.length) {
      html += '<div class="dx-samples"><div class="dx-detail-head"><span>Open a trace</span></div>' +
        sample.map(r => `<button class="dx-sample" data-trace="${esc(r.setup_id)}">
          <b>${esc(String(r.symbol || '').replace('-USD', ''))}</b>
          <span>${esc(r.tf || '')}</span>
          <span>${esc(String(r.strategy || '').replace('_', ' ').toLowerCase())}</span>
          <span>${esc(String(r.direction || '').toLowerCase())}</span>
          <span class="dx-sample-go">trace →</span>
        </button>`).join('') +
        `<div class="dx-sample-note">Most recent setups recorded at this stage.
          Click one to see every gate it passed and the value it was judged on.</div></div>`;
    }
    return html + '</div>';
  }

  function render(m) {
    model = m;
    ROOT.innerHTML = '<div class="dx-funnel">' +
      renderPill(m) + renderStages(m) + renderDetail(m) + '</div>';
    // Only now is the flat list in #dFunnel superseded. If this module had
    // thrown, the shell's original list would still be on screen.
    document.body.classList.add('dx-funnel-live');
  }

  function fail(msgs) {
    // Loud fallback. Do not touch dx-funnel-live: if a refresh fails after a
    // good render, the shell's flat list is the right thing to fall back to,
    // and it is restored by removing the class.
    document.body.classList.remove('dx-funnel-live');
    ROOT.innerHTML = `<div class="dx-funnel"><div class="dx-fail">
      <b>funnel unavailable</b>
      ${msgs.map(m => '<code>' + esc(m) + '</code>').join('<br>')}
      <span class="dx-fail-what">No stage counts are shown because they could not
      be read. This is a failed request, <em>not</em> a report that nothing was
      rejected.</span></div></div>`;
  }

  /* ---------- events ---------- */

  ROOT.addEventListener('click', e => {
    const stage = e.target.closest('[data-stage]');
    if (stage && model) {
      selected = stage.dataset.stage;
      render(model);
      return;
    }
    const trace = e.target.closest('[data-trace]');
    // The tracer is a separate module; if it failed to load, say so rather
    // than silently doing nothing on a click.
    if (trace) {
      if (window.SSTracer) SSTracer.open(trace.dataset.trace);
      else alert('The trace drawer could not be loaded (static/tracer.js).');
    }
  });

  /* ---------- load ---------- */

  async function load() {
    // limit=500 is the endpoint's ceiling: the aggregate counts are computed
    // before the limit is applied, so only the clickable sample is truncated.
    const [tel, ov] = await Promise.allSettled([
      api('/api/setup-telemetry?limit=500'),
      api('/api/overview')
    ]);
    if (tel.status === 'rejected') {
      const msgs = [String(tel.reason && tel.reason.message || tel.reason)];
      if (ov.status === 'rejected') msgs.push(String(ov.reason && ov.reason.message || ov.reason));
      fail(msgs);
      return;
    }
    render(build(tel.value,
                 ov.status === 'rejected'
                   ? String(ov.reason && ov.reason.message || ov.reason) : null,
                 ov.status === 'fulfilled' ? ov.value : {}));
  }

  ROOT.innerHTML = '<div class="dx-funnel"><div class="dx-load">reading the funnel…</div></div>';
  load();
  // Matches the shell's own 30s cadence. The operator's stage selection is held
  // in `selected` and survives the repaint.
  setInterval(load, 30000);
})();
