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

    const verdict = !hasCI ? 'Not enough sample for an interval.'
      : hi < 0 ? 'This book is losing, and the sample is large enough to say so. '
               + 'The interval sits entirely below break even — this is not bad luck.'
      : lo > 0 ? 'This book is profitable and the interval clears break even. '
               + 'Check concentration before trusting it: a handful of trades can carry a mean.'
      : 'Indistinguishable from break even. The interval crosses zero, so the '
        + 'honest answer is "not yet known" — neither a win nor a proven loss.';

    panel(`
      <div class="ev-grid">
        <div class="tile"><span class="t-label">Closed trades</span>
          <span class="t-metric">${b.n ?? '—'}</span></div>
        <div class="tile"><span class="t-label">Expectancy per trade</span>
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
