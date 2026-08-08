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
  function entryRecommendation(entry){
    const kind = String(entry && entry.order_kind || 'NONE').toUpperCase();
    if(kind === 'LIMIT') return entry.limit_price == null
      ? 'LIMIT - price not reported' : `LIMIT - ${px(entry.limit_price)}`;
    if(kind === 'MARKET') return 'MARKET - confirmed trigger';
    return 'NO ORDER';
  }

  function evidenceBody(row){
    const s = setup(row), grade = row.evidence || {}, td = s.top_down || {};
    const rungs = Object.entries(td.rungs || {})
      .map(([tf, value]) => `<li><span>${esc(tf)}</span><b>${esc(label(value))}</b></li>`).join('');
    const components = Object.entries(row.ranking_components || {})
      .map(([key, value]) => `<li><span>${esc(label(key))}</span><b>${esc(value)}</b></li>`).join('');
    const warnings = (grade.warnings || [])
      .map(w => `<li>${esc(w)}</li>`).join('');
    const gradeComponents = (grade.components || []).map(component => {
      const name = component.factor || component.name || component.key || 'component';
      const contribution = component.uplift_r;
      return `<li><span>${esc(label(name))}</span><b>${contribution == null ? 'Not recorded' : esc(contribution + 'R')}</b></li>`;
    }).join('');
    return `<dl class="factor-grade-facts">
        <div><dt>FactorGrade</dt><dd>${esc(grade.grade || 'UNGRADED')}</dd></div>
        <div><dt>Score</dt><dd>${grade.score == null ? 'Not calibrated' : esc(grade.score)}</dd></div>
        <div><dt>Confidence</dt><dd>${esc(label(grade.confidence || 'INSUFFICIENT_EVIDENCE'))}</dd></div>
        <div><dt>Coverage</dt><dd>${grade.coverage == null ? 'Not recorded' : esc(grade.coverage)}</dd></div>
        <div><dt>Expected edge</dt><dd>${grade.expected_edge_r == null ? 'Not established' : esc(grade.expected_edge_r + 'R')}</dd></div>
        <div><dt>Sample</dt><dd>${esc(grade.sample_size || 0)}</dd></div>
      </dl>
      <div class="op-evidence-grid"><div><h3>Top-down ladder</h3><ul>${rungs || '<li>No rungs recorded</li>'}</ul></div>
      <div><h3>Ranking components</h3><ul>${components || '<li>No components recorded</li>'}</ul></div></div>
      ${gradeComponents ? `<div><h3>Factor contributions</h3><ul>${gradeComponents}</ul></div>` : ''}
      ${warnings ? `<h3>Warnings</h3><ul class="op-warning-list">${warnings}</ul>` : ''}`;
  }

  function card(row, selected){
    const s = setup(row), entry = row.entry_recommendation || {};
    const grade = row.evidence || {}, econ = row.economics || {};
    const symbol = s.symbol || 'Unknown pair';
    const confidence = label(grade.confidence || 'INSUFFICIENT_EVIDENCE');
    return `<article class="op-card op-card-compact${selected ? ' selected' : ''}"
        data-state="${esc(row.state)}" data-opportunity-id="${esc(s.setup_id)}">
      <header>
        <div><span class="op-state">${esc(label(row.state))}</span>
          <h3>${esc(symbol)} <small>${esc(s.direction)}</small></h3></div>
        <div class="op-score-pair" aria-label="Quality ${esc(row.quality_score)}, evidence ${esc(confidence)}">
          <span><b>${esc(row.quality_score)}</b><small>Quality</small></span>
          <span><b>${esc(grade.grade || 'UNGRADED')}</b><small>${esc(confidence)}</small></span>
        </div>
      </header>
      <div class="op-meta"><span>${esc(s.horizon)}</span><span>${esc(s.timeframe)}</span>
        <span>${esc(label(s.strategy))}</span><span>${esc(label(s.regime))}</span></div>
      <dl class="op-compact-levels">
        <div><dt>Entry</dt><dd>${esc(entryRecommendation(entry))}</dd></div>
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
    const action = options && options.action === false ? '' :
      `<button class="btn btn-primary op-open-trade" data-id="${esc(s.setup_id)}"
        data-symbol="${esc(s.symbol)}" data-tf="${esc(s.timeframe)}">Open in Trade</button>`;
    return `<div class="op-detail-head">
        <div><span class="op-state">${esc(label(row.state))}</span>
          <h2>${esc(s.symbol || 'Unknown pair')} <small>${esc(s.direction)}</small></h2></div>
        <button class="btn op-detail-close" type="button" aria-label="Close setup details">Close</button>
      </div>
      <div class="op-detail-tags"><span>${esc(s.venue)}</span><span>${esc(s.horizon)}</span>
        <span>${esc(s.timeframe)}</span><span>${esc(label(s.strategy))}</span></div>
      <div class="op-decision-line"><span>${esc(label(s.regime))}</span>
        <span>Top-down ${esc(label(td.state))}</span>
        <span>Evidence ${esc(label(grade.confidence))}</span></div>
      <div class="op-recommendation"><span class="op-kicker">Recommendation</span>
        <strong>${esc(entryRecommendation(entry))}</strong>
        <small>${esc((entry.reasons && entry.reasons[0] && entry.reasons[0].summary) || 'No entry reason recorded.')}</small></div>
      <dl class="op-detail-levels">
        <div><dt>Stop</dt><dd>${px(s.stop)}</dd></div><div><dt>Targets</dt><dd>${targets}</dd></div>
        <div><dt>Reward/risk</dt><dd>${esc(s.rr)}R</dd></div><div><dt>Risk amount</dt><dd>${esc(money(econ.risk_usd))}</dd></div>
        <div><dt>Fees</dt><dd>${econ.fee_r == null ? 'Not recorded' : esc(econ.fee_r + 'R')}</dd></div>
        <div><dt>Funding</dt><dd>${econ.funding_r == null ? 'Not recorded' : esc(econ.funding_r + 'R')}</dd></div>
        <div><dt>Slippage</dt><dd>${econ.slippage_r == null ? 'Not recorded' : esc(econ.slippage_r + 'R')}</dd></div>
        <div><dt>Total costs</dt><dd>${econ.total_cost_r == null ? 'Not recorded' : esc(econ.total_cost_r + 'R')}</dd></div>
        <div><dt>Notional</dt><dd>${esc(money(econ.notional_usd))}</dd></div>
        <div><dt>Distance</dt><dd>${econ.distance_atr == null ? 'Not recorded' : esc(econ.distance_atr + ' ATR')}</dd></div>
        <div><dt>Expires</dt><dd>${esc(when(s.expires_at))}</dd></div>
      </dl>
      <section class="op-callout"><span class="op-kicker">Why it exists</span><p>${esc(row.primary_explanation)}</p></section>
      <section class="op-callout caution"><span class="op-kicker">Reason to pass</span><p>${esc(row.strongest_counterargument)}</p></section>
      <section class="op-callout"><span class="op-kicker">Invalidation</span><p>${esc(s.invalidation)}</p></section>
      <details class="op-detail-evidence"><summary>Evidence and scoring</summary>
        ${evidenceBody(row)}
      </details>
      <div class="op-detail-actions">
        <button class="btn op-trace" type="button" data-op-trace="${esc(s.setup_id)}">Open decision trace</button>
        ${action}</div>`;
  }

  function tradeEvidence(row){
    if(!row) return `<div class="trade-evidence-empty"><span class="op-state">No setup selected</span>
      <h2>Chart inspection</h2><p>Open a Setup Radar candidate to synchronize evidence, chart, and ticket.</p>
      <a class="btn btn-primary" href="#opportunities">Open Setup Radar</a></div>`;
    const s = setup(row), entry = row.entry_recommendation || {};
    const grade = row.evidence || {}, td = s.top_down || {};
    return `<div class="trade-evidence-head"><span class="op-state">${esc(label(row.state))}</span>
        <h2>${esc(s.symbol || 'Unknown pair')} <small>${esc(s.direction)}</small></h2>
        <div class="op-detail-tags"><span>${esc(s.horizon)}</span><span>${esc(s.timeframe)}</span>
          <span>${esc(label(s.strategy))}</span></div></div>
      <div class="trade-verdict"><span class="op-kicker">Recommendation</span>
        <strong>${esc(entryRecommendation(entry))}</strong></div>
      <dl class="trade-evidence-stats"><div><dt>Regime</dt><dd>${esc(label(s.regime))}</dd></div>
        <div><dt>Top-down</dt><dd>${esc(label(td.state))}</dd></div>
        <div><dt>Quality</dt><dd>${esc(row.quality_score)}/100</dd></div>
        <div><dt>Evidence</dt><dd>${esc(grade.grade || 'UNGRADED')} · ${esc(label(grade.confidence))}</dd></div></dl>
      <section class="trade-brief"><span class="op-kicker">Why it exists</span><p>${esc(row.primary_explanation)}</p></section>
      <section class="trade-brief caution"><span class="op-kicker">Reason to pass</span><p>${esc(row.strongest_counterargument)}</p></section>
      <section class="trade-brief"><span class="op-kicker">Invalidation</span><p>${esc(s.invalidation)}</p></section>
      <details class="trade-evidence-more"><summary>Show full evidence</summary>
        ${evidenceBody(row)}</details>`;
  }

  function missing(setupId){
    return `<div class="trade-evidence-empty bad"><span class="op-state">Setup unavailable</span>
      <h2>Selected setup is no longer in the current baseline</h2><p>${esc(setupId || 'Unknown setup')} was removed, expired, or superseded. No replacement was selected.</p>
      <a class="btn btn-primary" href="#opportunities">Return to Setup Radar</a></div>`;
  }

  window.SSOpportunityUI = {card, detail, tradeEvidence, missing, entryRecommendation,
    evidenceBody, label, px, money, when};
})();
