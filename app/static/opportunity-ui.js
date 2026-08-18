/* Shared presentation for server-owned OpportunityCandidate records.
   Formatting only: no eligibility, risk, ranking or economics are derived here. */
(() => {
  const esc = value => String(value == null ? '' : value)
    .replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
      '"':'&quot;',"'":'&#39;'}[c]));
  const label = value => String(value || 'UNKNOWN').replaceAll('_', ' ');
  // Prices arrive as Decimal strings. Converting through Number would round a
  // valid tick before the operator saw it, so preserve the server characters.
  const px = value => value == null || value === '' ? '—' : String(value);
  const money = value => value == null ? 'Not recorded' :
    '$' + Number(value).toLocaleString(undefined, {maximumFractionDigits:2});
  const when = value => value ? new Date(Number(value) * 1000)
    .toISOString().replace('T',' ').slice(0,16) + 'Z' : 'Not specified';
  const setup = row => row && row.setup || {};
  const hasGrade = grade => grade && grade.score != null &&
    grade.grade && String(grade.grade).toUpperCase() !== 'UNGRADED';
  const cautionLabel = state => ['BLOCKED','REJECTED','EXPIRED','CANCELLED'].includes(state)
    ? 'Why it was skipped' : ['ORDER_WORKING','POSITION_OPEN'].includes(state)
      ? 'Current status' : state === 'CLOSED' ? 'Outcome' : 'What could stop it';
  function entryRecommendation(entry, state){
    const kind = String(entry && entry.order_kind || 'NONE').toUpperCase();
    if(kind === 'LIMIT') return entry.limit_price == null
      ? 'Limit order — price unavailable' : `Limit order at ${px(entry.limit_price)}`;
    if(kind === 'MARKET') return 'Market entry on confirmed trigger';
    const copy = {
      FORMING: 'Watching — entry not confirmed', WATCHING: 'Watching — no entry yet',
      BLOCKED: 'Skipped', REJECTED: 'Skipped', EXPIRED: 'Entry window expired',
      CANCELLED: 'Cancelled', ORDER_WORKING: 'Order working',
      POSITION_OPEN: 'Position open', CLOSED: 'Trade finished'
    };
    return copy[String(state || '').toUpperCase()] || 'No trade';
  }

  function evidenceBody(row){
    const s = setup(row), grade = row.evidence || {}, td = s.top_down || {};
    const rungs = Object.entries(td.rungs || {})
      .map(([tf, value]) => `<li><span>${esc(tf)}</span><b>${esc(label(value))}</b></li>`).join('');
    const components = Object.entries(row.ranking_components || {})
      .map(([key, value]) => `<li><span>${esc(label(key))}</span><b>${esc(value)}</b></li>`).join('');
    const gradeComponents = hasGrade(grade) ? (grade.components || []).map(component => {
      const name = component.factor || component.name || component.key || 'component';
      const contribution = component.uplift_r;
      return `<li><span>${esc(label(name))}</span><b>${contribution == null ? 'Not recorded' : esc(contribution + 'R')}</b></li>`;
    }).join('') : '';
    const gradeFacts = hasGrade(grade) ? `<dl class="factor-grade-facts">
        <div><dt>Performance grade</dt><dd>${esc(grade.grade)}</dd></div>
        <div><dt>Score</dt><dd>${esc(grade.score)}</dd></div>
        <div><dt>Confidence</dt><dd>${esc(label(grade.confidence))}</dd></div>
        <div><dt>Coverage</dt><dd>${grade.coverage == null ? 'Not recorded' : esc(grade.coverage)}</dd></div>
        <div><dt>Expected edge</dt><dd>${grade.expected_edge_r == null ? 'Not established' : esc(grade.expected_edge_r + 'R')}</dd></div>
        <div><dt>Sample</dt><dd>${esc(grade.sample_size || 0)}</dd></div>
      </dl>` : '';
    return `${gradeFacts}<div class="op-evidence-grid"><div><h3>Higher-timeframe view</h3><ul>${rungs || '<li>No higher-timeframe readings recorded</li>'}</ul></div>
      <div><h3>How the score was built</h3><ul>${components || '<li>No score components recorded</li>'}</ul></div></div>
      ${gradeComponents ? `<div><h3>Proven factor contributions</h3><ul>${gradeComponents}</ul></div>` : ''}`;
  }

  function card(row, selected){
    const s = setup(row), entry = row.entry_recommendation || {};
    const grade = row.evidence || {}, econ = row.economics || {};
    const symbol = s.symbol || 'Unknown pair';
    const gradeScore = hasGrade(grade) ? `<span><b>${esc(grade.grade)}</b><small>${esc(label(grade.confidence))}</small></span>` : '';
    return `<article class="op-card op-card-compact${selected ? ' selected' : ''}"
        data-state="${esc(row.state)}" data-opportunity-id="${esc(s.setup_id)}">
      <header>
        <div><span class="op-state">${esc(label(row.state))}</span>
          <h3>${esc(symbol)} <small>${esc(s.direction)}</small></h3></div>
        <div class="op-score-pair" aria-label="Setup score ${esc(row.quality_score)} out of 100">
          <span><b>${esc(row.quality_score)}</b><small>Setup score</small></span>
          ${gradeScore}
        </div>
      </header>
      <div class="op-meta"><span>${esc(s.horizon)}</span><span>${esc(s.timeframe)}</span>
        <span>${esc(label(s.strategy))}</span><span>${esc(label(s.regime))}</span></div>
      <dl class="op-compact-levels">
        <div><dt>Entry</dt><dd>${esc(entryRecommendation(entry, row.state))}</dd></div>
        <div><dt>Reward/risk</dt><dd>${esc(s.rr)}R</dd></div>
        <div><dt>Risk</dt><dd>${esc(money(econ.risk_usd))}</dd></div>
        <div><dt>Expires</dt><dd>${esc(when(s.expires_at))}</dd></div>
      </dl>
      <button class="btn btn-primary op-review" data-id="${esc(s.setup_id)}"
        aria-pressed="${selected ? 'true' : 'false'}">Review setup</button>
    </article>`;
  }

  function detail(row, options){
    if(!row) return `<div class="op-detail-empty"><span class="op-state">No selection</span>
      <h2>Select a setup</h2><p>Choose one card to inspect its plan and evidence.</p></div>`;
    const s = setup(row), entry = row.entry_recommendation || {};
    const grade = row.evidence || {}, econ = row.economics || {};
    const td = s.top_down || {};
    const targets = (s.targets || []).map(px).join(' / ') || '—';
    const actionsEnabled = !(options && options.action === false);
    const canTrade = row.state === 'READY' && row.eligible &&
      String(entry.order_kind || 'NONE').toUpperCase() !== 'NONE';
    const canInspect = ['FORMING','WATCHING'].includes(row.state);
    const manageLabel = row.state === 'POSITION_OPEN' ? 'Manage position'
      : row.state === 'ORDER_WORKING' ? 'View working order' : null;
    const action = !actionsEnabled ? '' : canTrade
      ? `<button class="btn btn-primary op-open-trade" data-id="${esc(s.setup_id)}"
          data-symbol="${esc(s.symbol)}" data-tf="${esc(s.timeframe)}">Open in Trade</button>`
      : manageLabel
        ? `<button class="btn btn-primary op-open-trade" data-id="${esc(s.setup_id)}"
            data-symbol="${esc(s.symbol)}" data-tf="${esc(s.timeframe)}">${manageLabel}</button>`
      : canInspect
        ? `<button class="btn op-inspect-chart" data-id="${esc(s.setup_id)}"
            data-symbol="${esc(s.symbol)}" data-tf="${esc(s.timeframe)}">Inspect chart</button>`
        : '';
    return `<div class="op-detail-head">
        <div><span class="op-state">${esc(label(row.state))}</span>
          <h2>${esc(s.symbol || 'Unknown pair')} <small>${esc(s.direction)}</small></h2></div>
        <button class="btn op-detail-close" type="button" aria-label="Close setup details">Close</button>
      </div>
      <div class="op-detail-tags"><span>${esc(s.venue)}</span><span>${esc(s.horizon)}</span>
        <span>${esc(s.timeframe)}</span><span>${esc(label(s.strategy))}</span></div>
      <div class="op-decision-line"><span>${esc(label(s.regime))}</span>
        <span>Higher timeframes: ${esc(label(td.state))}</span>
        ${hasGrade(grade) ? `<span>Performance grade: ${esc(grade.grade)}</span>` : ''}</div>
      <div class="op-recommendation"><span class="op-kicker">Recommendation</span>
        <strong>${esc(entryRecommendation(entry, row.state))}</strong>
        <small>${esc((entry.reasons && entry.reasons[0] && entry.reasons[0].summary) || 'No entry reason recorded.')}</small></div>
      <dl class="op-detail-levels">
        <div><dt>Stop</dt><dd>${px(s.stop)}</dd></div><div><dt>Targets</dt><dd>${targets}</dd></div>
        <div><dt>Reward/risk</dt><dd>${esc(s.rr)}R</dd></div><div><dt>Risk amount</dt><dd>${esc(money(econ.risk_usd))}</dd></div>
        <div><dt>Fees</dt><dd>${econ.fee_r == null ? 'Not recorded' : esc(econ.fee_r + 'R')}</dd></div>
        <div><dt>Funding</dt><dd>${econ.funding_r == null ? 'Not recorded' : esc(econ.funding_r + 'R')}</dd></div>
        <div><dt>Slippage</dt><dd>${econ.slippage_r == null ? 'Not recorded' : esc(econ.slippage_r + 'R')}</dd></div>
        <div><dt>Total costs</dt><dd>${econ.total_cost_r == null ? 'Not recorded' : esc(econ.total_cost_r + 'R')}</dd></div>
        <div><dt>Position value</dt><dd>${esc(money(econ.notional_usd))}</dd></div>
        <div><dt>Distance</dt><dd>${econ.distance_atr == null ? 'Not recorded' : esc(econ.distance_atr + ' ATR')}</dd></div>
        <div><dt>Expires</dt><dd>${esc(when(s.expires_at))}</dd></div>
      </dl>
      <section class="op-callout"><span class="op-kicker">Why it exists</span><p>${esc(row.primary_explanation)}</p></section>
      <section class="op-callout caution"><span class="op-kicker">${cautionLabel(row.state)}</span><p>${esc(row.strongest_counterargument)}</p></section>
      <section class="op-callout"><span class="op-kicker">What kills this trade</span><p>${esc(s.invalidation)}</p></section>
      <details class="op-detail-evidence"><summary>How the bot scored it</summary>
        ${evidenceBody(row)}
      </details>
      <div class="op-detail-actions">
        <button class="btn op-trace" type="button" data-op-trace="${esc(s.setup_id)}">Open decision trace</button>
        ${action}</div>`;
  }

  function tradeEvidence(row){
    if(!row) return `<div class="trade-evidence-empty"><span class="op-state">No setup selected</span>
      <h2>Chart inspection</h2><p>Open a setup to see why the bot likes it, on the chart and in the ticket.</p>
      <a class="btn btn-primary" href="#opportunities">Open Setups</a></div>`;
    const s = setup(row), entry = row.entry_recommendation || {};
    const grade = row.evidence || {}, td = s.top_down || {};
    return `<div class="trade-evidence-head"><span class="op-state">${esc(label(row.state))}</span>
        <h2>${esc(s.symbol || 'Unknown pair')} <small>${esc(s.direction)}</small></h2>
        <div class="op-detail-tags"><span>${esc(s.horizon)}</span><span>${esc(s.timeframe)}</span>
          <span>${esc(label(s.strategy))}</span></div></div>
      <div class="trade-verdict"><span class="op-kicker">Recommendation</span>
        <strong>${esc(entryRecommendation(entry, row.state))}</strong></div>
      <dl class="trade-evidence-stats"><div><dt>Regime</dt><dd>${esc(label(s.regime))}</dd></div>
        <div><dt>Higher timeframes</dt><dd>${esc(label(td.state))}</dd></div>
        <div><dt>Setup score</dt><dd>${esc(row.quality_score)}/100</dd></div>
        ${hasGrade(grade) ? `<div><dt>Performance grade</dt><dd>${esc(grade.grade)} · ${esc(label(grade.confidence))}</dd></div>` : ''}</dl>
      <section class="trade-brief"><span class="op-kicker">Why it exists</span><p>${esc(row.primary_explanation)}</p></section>
      <section class="trade-brief caution"><span class="op-kicker">${cautionLabel(row.state)}</span><p>${esc(row.strongest_counterargument)}</p></section>
      <section class="trade-brief"><span class="op-kicker">What kills this trade</span><p>${esc(s.invalidation)}</p></section>
      <details class="trade-evidence-more"><summary>How the bot scored it</summary>
        ${evidenceBody(row)}</details>`;
  }

  function missing(setupId){
    return `<div class="trade-evidence-empty bad"><span class="op-state">Setup unavailable</span>
      <h2>This setup is no longer current — review a fresh setup</h2><p>${esc(setupId || 'Unknown setup')} was removed, expired, or superseded. No replacement was selected.</p>
      <a class="btn btn-primary" href="#opportunities">Back to Setups</a></div>`;
  }

  window.SSOpportunityUI = {card, detail, tradeEvidence, missing, entryRecommendation,
    evidenceBody, label, px, money, when};
})();
