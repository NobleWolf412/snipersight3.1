/* Edge statistics — "is this working, or have I just not seen enough yet?"

   An equity curve cannot answer that question. A losing strategy and an unlucky
   one draw the same shape, and the difference decides whether you change the
   rules or wait for sample. This panel puts the confidence interval on screen
   next to the curve so the distinction is unavoidable.

   Loud-fallback rule applies with unusual force here: a statistics panel that
   silently renders zeros is worse than no panel, because a zero looks like an
   answer. Every failure path below says what failed. */
(() => {
  const root = document.getElementById('edgeRoot');
  if (!root) return;

  const CSS = `
  .ev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:var(--md)}
  .ev-ci{position:relative;height:44px;margin:var(--md) 0 var(--xs)}
  .ev-ci-track{position:absolute;inset:18px 0 auto 0;height:6px;border-radius:var(--r-pill);
    background:var(--card-2)}
  .ev-ci-band{position:absolute;top:18px;height:6px;border-radius:var(--r-pill)}
  .ev-ci-mean{position:absolute;top:11px;width:2px;height:20px;background:var(--fg)}
  .ev-ci-zero{position:absolute;top:6px;width:1px;height:30px;background:var(--fg-4)}
  .ev-ci-zerolab{position:absolute;top:36px;transform:translateX(-50%);color:var(--fg-4)}
  .ev-verdict{padding:var(--md) var(--lg);border-radius:var(--r-md);
    border:1px solid var(--border);background:var(--card);margin-top:var(--md)}
  .ev-scn{width:100%;border-collapse:collapse;margin-top:var(--sm)}
  .ev-scn td,.ev-scn th{padding:6px 10px;border-bottom:1px solid var(--border-soft);text-align:right}
  .ev-scn th:first-child,.ev-scn td:first-child{text-align:left}
  .ev-warn{color:var(--amber);margin-top:var(--sm)}
  /* Per-timeframe rows. One shared scale across all five — a per-row scale
     would make a wide interval and a narrow one look the same width, which is
     the one thing this panel exists to prevent. */
  .ev-tf{display:grid;grid-template-columns:44px 62px 76px 1fr;gap:var(--sm);
    align-items:center;padding:5px 0;border-bottom:1px solid var(--border-soft)}
  .ev-tf-bar{position:relative;height:14px}
  .ev-tf-track{position:absolute;inset:6px 0 auto 0;height:3px;border-radius:var(--r-pill);
    background:var(--card-2)}
  .ev-tf-band{position:absolute;top:6px;height:3px;border-radius:var(--r-pill)}
  .ev-tf-mean{position:absolute;top:2px;width:2px;height:11px;background:var(--fg-2)}
  .ev-tf-zero{position:absolute;top:0;width:1px;height:14px;background:var(--fg-4)}
  .ev-tf-none{color:var(--fg-4);grid-column:2 / -1}
  .ev-flow{margin-top:var(--sm);color:var(--fg-3)}
  `;
  if (!document.getElementById('ev-css')) {
    const st = document.createElement('style');
    st.id = 'ev-css'; st.textContent = CSS; document.head.appendChild(st);
  }

  const esc = s => String(s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const sign = v => v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--fg-3)';
  const num = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v))
    ? '—' : Number(v).toFixed(d);

  function panel(inner) {
    root.innerHTML =
      `<div class="panel"><div class="panel-head">
         <span class="t-section">Is the edge real?</span>
         <span class="chip" style="margin-left:auto" id="evVer">—</span>
       </div><div class="panel-body">${inner}</div></div>`;
  }

  /* The CI bar. Zero is drawn as a fixed landmark, because the ONLY thing that
     matters visually is which side of it the interval sits on — an interval
     that crosses zero has not established a direction, however good the mean. */
  function ciBar(lo, hi, mean) {
    const pad = Math.max(0.15, (hi - lo) * 0.35);
    const min = Math.min(lo, 0) - pad, max = Math.max(hi, 0) + pad;
    const pct = v => ((v - min) / (max - min)) * 100;
    const crosses = lo <= 0 && hi >= 0;
    const col = crosses ? 'var(--amber)' : (hi < 0 ? 'var(--red)' : 'var(--green)');
    return `<div class="ev-ci">
      <div class="ev-ci-track"></div>
      <div class="ev-ci-band" style="left:${pct(lo)}%;width:${pct(hi) - pct(lo)}%;background:${col}"></div>
      <div class="ev-ci-mean" style="left:${pct(mean)}%"></div>
      <div class="ev-ci-zero" style="left:${pct(0)}%"></div>
      <div class="ev-ci-zerolab t-label" style="left:${pct(0)}%">break even</div>
    </div>`;
  }

  /* Timeframe order is FIXED — shortest to longest, the ladder the operator
     already thinks in. Never sorted by expectancy: a table that reorders itself
     so the best number is on top is an argument, not a report. */
  const TF_ORDER = ['15m', '1H', '4H', '1D', '1W'];

  /* The same book cut five ways. This is the single highest-value figure the
     API serves and `edgeview.js` used to throw it away.

     Three deliberate refusals, each preventing a specific misreading:
       · rows never sort — see TF_ORDER
       · the MEAN is never coloured. Colour goes on the interval, and only when
         it clears zero. A green -0.35 that happens to have a wide interval
         reads as a result; it is not one.
       · a slice below the sample floor prints the engine's own refusal string
         verbatim and NO mean. Printing a mean for n=3 beside four real ones
         invites exactly the comparison the floor exists to forbid. */
  function byTimeframe(byTf, confound) {
    const rows = TF_ORDER.filter(tf => byTf && byTf[tf]).map(tf => [tf, byTf[tf]]);
    if (!rows.length) return '';

    // One shared scale across every row, so widths are comparable.
    let min = 0, max = 0;
    rows.forEach(([, s]) => {
      const b = s.bootstrap;
      if (!b) return;
      min = Math.min(min, b.ci_lo); max = Math.max(max, b.ci_hi);
    });
    const pad = Math.max(0.1, (max - min) * 0.12);
    min -= pad; max += pad;
    const pct = v => ((v - min) / (max - min)) * 100;

    let cleared = 0, measured = 0;
    const body = rows.map(([tf, s]) => {
      const b = s.bootstrap;
      if (!b || s.mean_r == null) {
        // Verbatim. The engine wrote a sentence explaining the refusal; this
        // panel does not paraphrase it and does not blank it.
        return `<div class="ev-tf t-mono">
          <b>${esc(tf)}</b><span style="color:var(--fg-4)">n=${s.n ?? 0}</span>
          <span class="ev-tf-none t-label">${esc(s.refusal || 'no verdict reported')}</span>
        </div>`;
      }
      measured++;
      const crosses = b.ci_lo <= 0 && b.ci_hi >= 0;
      if (!crosses) cleared++;
      const col = crosses ? 'var(--amber)' : (b.ci_hi < 0 ? 'var(--red)' : 'var(--green)');
      const cf = (confound && confound.slices && confound.slices[tf]) || {};
      // Only when actually confounded. A reassuring note on every row trains
      // the eye to skip the one row that will eventually matter.
      const note = cf.confounded
        ? `<div class="t-label" style="grid-column:2 / -1;color:var(--amber)">⚠ ${esc(cf.note || 'version-confounded slice')}</div>`
        : '';
      return `<div class="ev-tf t-mono">
        <b>${esc(tf)}</b>
        <span style="color:var(--fg-4)">n=${s.n}</span>
        <span style="color:var(--fg-2)">${num(s.mean_r, 3)} R</span>
        <div class="ev-tf-bar">
          <div class="ev-tf-track"></div>
          <div class="ev-tf-band" style="left:${pct(b.ci_lo)}%;width:${pct(b.ci_hi) - pct(b.ci_lo)}%;background:${col}"></div>
          <div class="ev-tf-mean" style="left:${pct(s.mean_r)}%"></div>
          <div class="ev-tf-zero" style="left:${pct(0)}%"></div>
        </div>
        ${note}
      </div>`;
    }).join('');

    const lede = cleared === 0
      ? `Not one of these ${measured} has cleared break even, and their intervals overlap each other heavily.`
      : `${cleared} of ${measured} clear break even on their own interval.`;

    return `<div style="margin-top:var(--lg)">
      <div class="t-section">By timeframe</div>
      <div class="t-label" style="color:var(--fg-4);margin-bottom:var(--xs)">
        the same book cut five ways, against the same break-even line</div>
      ${body}
      <div class="t-body ev-flow">${lede}
        This is one book cut five ways after the fact — with five slices, one will
        look best by chance. Read the spread as a place to look, not a result.</div>
    </div>`;
  }

  function render(d) {
    if (!(d.sufficient ?? (d.book || {}).sufficient)) {
      panel(`<div class="empty">Not enough closed trades to say anything honest yet.
        <br><span class="t-label" style="color:var(--fg-3)">${esc(d.refusal || 'sample too small')}</span></div>`);
      return;
    }
    const b = d.book || {};
    const ci = b.bootstrap || {};
    const lo = ci.ci_lo, hi = ci.ci_hi, p = ci.p_gt_zero;
    const exp = b.mean_r;
    const hasCI = typeof lo === 'number' && typeof hi === 'number';
    const crosses = hasCI && lo <= 0 && hi >= 0;

    /* The verdict is the ENGINE's, not this file's.
       `edgestats._verdict` names the fee basis it was computed on; the prose
       that used to live here did not, and rebuilding an interpretation from
       `lo`/`hi` in the browser is a second authority for the one number this
       panel exists to state carefully — the same breach as ticket-math.js, in
       the one place that can least afford it. They agreed by luck.

       If the engine did not return a verdict, REFUSE. Falling back to
       locally-written prose is how the second authority came back. */
    const ev = d.verdict || {};
    const verdict = ev.text
      ? `<b>${esc(ev.code || '')}</b> ${esc(ev.text)}`
      : '<span style="color:var(--amber)">The engine did not return a verdict for '
        + 'this book. The figures above are shown; the sentence that interprets '
        + 'them is not, because this panel does not write one.</span>';

    /* The denominator. "Closed trades 401" invites the reading that 401 is
       everything the simulator produced. 243 of 644 ran on a warmed venue the
       risk authority will not size — excluded by VENUE, not by outcome, and an
       operator who does not know that cannot reconcile this panel with
       Results. Phrase reused verbatim from shell.js shadowBlock(). */
    const ct = d.counts || {};
    const excl = [];
    if (ct.shadow_venue) excl.push(`${ct.shadow_venue} on a warmed venue, never tradeable`);
    if (ct.unfilled_missed) excl.push(`${ct.unfilled_missed} never filled`);
    if (ct.excluded_no_stop_distance) excl.push(`${ct.excluded_no_stop_distance} with no stop distance`);
    if (ct.excluded_no_fee_record) excl.push(`${ct.excluded_no_fee_record} with no cost record`);
    if (ct.filtered_out_strategy) excl.push(`${ct.filtered_out_strategy} filtered by strategy`);
    const denom = ct.exec_facts
      ? `${b.n ?? '—'} of ${ct.exec_facts} simulated${excl.length ? ' · ' + excl.join(' · ') : ''}`
      : '';

    /* Where the edge goes. The interval is computed on NET; showing gross
       beside it explains the width instead of leaving costs as an unexplained
       subtraction. Deliberately not framed as "cut fees and you profit" —
       mean_r_gross has no interval of its own and is not a demonstrated edge. */
    const g = b.mean_r_gross, cst = b.mean_costs_r;
    const costLine = (typeof g === 'number' && typeof cst === 'number' && g !== 0)
      ? `<div class="t-body ev-flow"><b>Where the edge goes</b> — gross
         ${num(g)} R → costs ${num(-Math.abs(cst))} R → net ${num(b.mean_r)} R.
         Costs are consuming ${Math.round(100 * Math.abs(cst) / Math.abs(g))}% of the gross figure.
         ${(typeof b.avg_win_r === 'number' && typeof b.avg_loss_r === 'number')
            ? `Average win ${num(b.avg_win_r, 2)} R against average loss ${num(b.avg_loss_r, 2)} R —
               a low-hit-rate, high-payoff book, so long losing runs are normal in that
               shape rather than a sign something broke.` : ''}</div>`
      : '';

    /* THE ERA LABEL, matching Results verbatim in its nouns. This panel counts
       the whole recorded book; Results counts only the current forward window.
       Left unlabelled, the two contradict each other on the two surfaces whose
       stated jobs are "is this actually working" and "is the machine telling me
       the truth" — the worst possible place to look like you are lying. */
    const eraBand = `<div class="era-band">
      These figures cover the whole
      <span class="term" data-t="recordedBook">recorded book</span> — every trade
      the simulator has closed, across every
      <span class="term" data-t="baseline">baseline</span>. The current
      <span class="term" data-t="forwardWindow">forward window</span> on its own is
      on <a href="#results" data-era-link="results">Results</a>, and will show far
      fewer trades, often none.</div>`;

    panel(`
      ${eraBand}
      <div class="ev-grid">
        <div class="tile"><span class="t-label">Closed trades</span>
          <span class="t-metric">${b.n ?? '—'}</span>
          <span class="t-sub">${esc(denom)}</span></div>
        <div class="tile"><span class="t-label"><span class="term" data-t="expectancy">Expectancy</span> per trade</span>
          <span class="t-metric" style="color:${sign(exp)}">${num(exp)} R</span></div>
        <div class="tile"><span class="t-label">Win rate</span>
          <span class="t-metric">${b.win_rate == null ? '—' : (b.win_rate * 100).toFixed(1) + '%'}</span></div>
        <div class="tile"><span class="t-label">Worst losing streak</span>
          <span class="t-metric">${b.max_consecutive_losses ?? '—'}</span></div>
      </div>

      ${hasCI ? ciBar(lo, hi, exp) : ''}
      ${hasCI ? `<div class="t-label" style="color:var(--fg-3)">
          95% confidence interval ${num(lo)} R to ${num(hi)} R ·
          probability the edge is positive <b style="color:${crosses ? 'var(--amber)' : sign(exp)}">
          ${p == null ? '—' : (p * 100).toFixed(1) + '%'}</b>
          · ${ci.resamples ? Number(ci.resamples).toLocaleString() : '—'} resamples</div>` : ''}

      <div class="ev-verdict t-body">${verdict}</div>
      ${costLine}
      ${byTimeframe(d.by_tf, d.confound)}

      ${(d.scenarios || []).length ? `<table class="ev-scn t-mono">
        <tr><th>fee scenario</th><th>expectancy</th><th>P(&gt;0)</th></tr>
        ${d.scenarios.map(s => `<tr><td>${esc(s.scenario || '')}</td>
          <td style="color:${sign(s.mean_r)}">${num(s.mean_r)} R</td>
          <td>${(s.bootstrap||{}).p_gt_zero == null ? '—' : (s.bootstrap.p_gt_zero * 100).toFixed(1) + '%'}</td></tr>`).join('')}
      </table>` : ''}

      ${d.breakeven_fee && d.breakeven_fee.computable ? `
        <div class="t-label" style="margin-top:var(--sm);color:var(--fg-3)">
          Break-even fee: ${num(d.breakeven_fee.per_side * 100, 4)}% per side
          (the book is ${Number(d.breakeven_fee.mean_r_ex_fee) > 0 ? 'profitable' : 'unprofitable'}
           before costs at ${num(d.breakeven_fee.mean_r_ex_fee)} R).
          ${Number(d.breakeven_fee.per_side) < 0
            ? '<b style="color:var(--red)">Negative — this book loses before a single fee is charged, so fees are not the cause.</b>'
            : ''}</div>` : ''}

      ${(d.warnings || []).length ? `<div class="ev-warn t-label">${
        d.warnings.map(w => '⚠ ' + esc(w)).join('<br>')}</div>` : ''}
      ${(d.caveats || []).length ? `<div class="t-label" style="margin-top:var(--xs);color:var(--fg-4)">${
        d.caveats.map(esc).join('<br>')}</div>` : ''}
    `);
    const v = document.getElementById('evVer');
    if (v) v.textContent = d.algo_version || '—';
  }

  async function load() {
    panel('<div class="empty">measuring…</div>');
    try {
      const r = await fetch('/api/edge-stats');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      render(await r.json());
    } catch (e) {
      // Never a zero. A statistics panel that fails quietly is a lie.
      panel(`<div class="empty" style="color:var(--red-2)">
        Edge statistics could not be loaded — <span class="t-mono">${esc(e.message)}</span>.
        <br><span class="t-label">This is a failed request, not a book with no edge.</span></div>`);
    }
  }

  load();
  window.SSEdgeView = {reload: load};
})();
