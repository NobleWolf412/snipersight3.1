/* Results → Signals. All cohorts, grades, and verdicts are server-owned. */
(() => {
  const root = document.getElementById('factorEvidenceRoot');
  if(!root) return;
  const esc = value => String(value == null ? '' : value)
    .replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
      '"':'&quot;',"'":'&#39;'}[c]));
  const pct = value => value == null ? 'Unavailable' : `${(Number(value) * 100).toFixed(0)}%`;
  const metric = (v, suffix='') => v == null ? 'Not gradeable' : `${Number(v).toFixed(3)}${suffix}`;
  const api = path => window.SSData ? SSData.get(path, 30000) :
    fetch(path).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  let loaded = false;

  function card(row){
    const p = row.progress || {};
    const interval = row.ci_lo == null || row.ci_hi == null ? 'Not gradeable' :
      `[${Number(row.ci_lo).toFixed(3)}, ${Number(row.ci_hi).toFixed(3)}]R`;
    return `<article class="panel signal-evidence-card">
      <header><div><span class="op-state">${esc(row.verdict || 'Collecting evidence')}</span>
        <h3>${esc(row.label)}</h3></div><strong>Used in trading: No</strong></header>
      <p>${esc(row.hypothesis)}</p>
      <dl class="signal-evidence-stats">
        <div><dt>Exposed</dt><dd>${esc(row.exposed_count)} trades · ${esc(row.exposed_symbol_clusters)} symbols</dd></div>
        <div><dt>Control</dt><dd>${esc(row.control_count)} trades · ${esc(row.control_symbol_clusters)} symbols</dd></div>
        <div><dt>Progress</dt><dd>Exposed ${esc(p.exposed_trades)}/${esc(p.trades_required_each)} trades, ${esc(p.exposed_symbols)}/${esc(p.symbols_required_each)} symbols<br>
          Control ${esc(p.control_trades)}/${esc(p.trades_required_each)} trades, ${esc(p.control_symbols)}/${esc(p.symbols_required_each)} symbols</dd></div>
        <div><dt>Coverage</dt><dd>${esc(pct(row.coverage))} · missing ${esc(pct(row.missing_rate))}</dd></div>
        <div><dt>Net-R uplift after costs</dt><dd>${esc(metric(row.uplift_r,'R'))}</dd></div>
        <div><dt>95% interval</dt><dd>${esc(interval)}</dd></div>
        <div><dt>Stability</dt><dd>${row.sample_ok ? (row.stable ? 'Stable across time split' : 'Not stable') : 'Not gradeable'}</dd></div>
        <div><dt>Corrected significance</dt><dd>${row.q_value == null ? 'Not gradeable' : esc(Number(row.q_value).toFixed(3))}</dd></div>
        <div><dt>Collection start</dt><dd>${row.collection_start ? esc(new Date(row.collection_start * 1000).toISOString().slice(0,10)) : 'Not started'}</dd></div>
        <div><dt>Detector version</dt><dd>${esc(row.detector_version)}</dd></div>
      </dl>
      <details><summary>Other patterns observed</summary><ul>
        ${(row.other_patterns_observed || []).map(item => `<li>${esc(item.label)} <small>${item.status === 'EXPLORATORY_UNCOLLECTED' ? 'Planned exploratory pattern — no observations collected.' : 'Exploratory — cannot be Proven useful'}</small></li>`).join('') || '<li>None reported</li>'}
      </ul></details>
    </article>`;
  }

  async function load(){
    if(loaded) return; loaded = true;
    try{
      const report = await api('/api/factor-evidence');
      root.innerHTML = `<section class="signal-research-head">
        <span class="op-state">Research only · does not affect trading</span>
        <h2>Signal research — which readings have earned trust?</h2>
        <p class="signal-research-verdict">${esc(report.verdict || 'Data unavailable')}</p>
        <small>Each side needs ${esc(report.minimums && report.minimums.closed_trades_each || 30)} closed trades and ${esc(report.minimums && report.minimums.symbol_clusters_each || 8)} symbol clusters.</small>
      </section><div class="signal-evidence-grid">${(report.rows || []).map(card).join('')}</div>`;
    }catch(err){
      root.innerHTML = `<section class="panel op-empty bad"><span class="op-state">Data unavailable</span>
        <h2>Signal research unavailable</h2><p>No missing sample is shown as zero, neutral, or proven.</p></section>`;
    }
  }
  if('IntersectionObserver' in window){
    const observer = new IntersectionObserver(entries => {
      if(entries.some(e => e.isIntersecting)){ observer.disconnect(); load(); }
    }, {rootMargin:'200px'});
    observer.observe(root);
  }else load();
})();
