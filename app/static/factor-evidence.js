/* Factor calibration belongs in Debrief. Quality and evidence confidence are
   separate, and UNGRADED is a valid answer rather than a score-shaped guess. */
(() => {
  const root = document.getElementById('factorEvidenceRoot');
  if(!root) return;
  const esc = value => String(value == null ? '' : value)
    .replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
      '"':'&quot;',"'":'&#39;'}[c]));
  const api = path => window.SSData ? SSData.get(path, 30000) :
    fetch(path).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  let loaded = false;

  async function load(){
    if(loaded) return; loaded = true;
    try{
      const [grade, evidence] = await Promise.all([
        api('/api/factor-grade'), api('/api/factor-evidence')]);
      const passing = (evidence.rows || []).filter(r => r.passes_evidence);
      const rows = evidence.rows || [];
      root.innerHTML = `<section class="panel factor-panel">
        <div class="panel-head"><h2 class="t-section">Factor calibration</h2>
          <span class="chip">${esc(grade.grade || 'UNGRADED')}</span></div>
        <div class="panel-body">
          <p class="population-note">Factor Stats scope Â· Population: ${esc(evidence.population || 'not reported')} Â·
            Window: ${esc(evidence.window || 'not reported')}</p>
          <p class="population-note">FactorGrade scope Â· Population: ${esc(grade.population || 'not reported')} Â·
            Window: ${esc(grade.window || 'not reported')}</p>
          <div class="factor-summary">
            <div><span>Setup quality score</span><b>${esc(grade.score == null ? 'not calibrated' : grade.score)}</b></div>
            <div><span>Evidence confidence</span><b>${esc(grade.confidence || 'INSUFFICIENT EVIDENCE')}</b></div>
            <div><span>Coverage</span><b>${esc(grade.coverage == null ? '—' : grade.coverage)}</b></div>
            <div><span>Forward samples</span><b>${esc(grade.sample_size || 0)}</b></div>
          </div>
          <p class="t-note">${esc(grade.permission || 'RANK_AND_EXPLAIN_ONLY')}. A grade cannot override
            regime conflict, stale data, cost, reward/risk, or a risk rejection.</p>
          <p class="t-note">${passing.length} factor cohort${passing.length === 1 ? '' : 's'}
            survived chronological validation, forward stability, confidence,
            shrinkage, and multiple-testing correction.</p>
          ${(grade.warnings || []).map(w => `<p class="op-warning">${esc(w)}</p>`).join('')}
          <details class="factor-record"><summary>Factor Stats cohorts (${rows.length})</summary>
            <p class="t-note">${esc(evidence.closed_trades || 0)} closed trades · chronological
              ${esc(Math.round((evidence.split || {}).train * 100 || 0))}% train,
              ${esc(Math.round((evidence.split || {}).validation * 100 || 0))}% validation,
              ${esc(Math.round((evidence.split || {}).forward * 100 || 0))}% forward ·
              ${evidence.point_in_time ? 'point-in-time joins' : 'point-in-time status not reported'}</p>
            <div class="dimension-scroll"><table class="factor-table"><thead><tr>
              <th>Factor / cohort</th><th>Status</th><th>Forward sample</th><th>Coverage</th>
              <th>Uplift</th><th>95% interval</th><th>Stable</th><th>Adjusted q</th></tr></thead><tbody>
              ${rows.length ? rows.map(row => `<tr><td><b>${esc(row.factor)}</b><small>${esc(row.cohort_key)}</small></td>
                <td>${row.passes_evidence ? 'PASSED' : esc(row.status)}</td>
                <td>${esc((row.high_samples || {}).forward || 0)} high / ${esc((row.control_samples || {}).forward || 0)} control</td>
                <td>${row.coverage == null ? 'Not reported' : esc((Number(row.coverage) * 100).toFixed(0) + '%')}</td>
                <td>${row.shrunk_uplift_r == null ? 'Not established' : esc(Number(row.shrunk_uplift_r).toFixed(3) + 'R shrunk')}</td>
                <td>${row.ci_lo == null || row.ci_hi == null ? 'Not computed' : esc(`[${Number(row.ci_lo).toFixed(3)}, ${Number(row.ci_hi).toFixed(3)}]R`)}</td>
                <td>${row.stable ? 'YES' : 'NO'}</td><td>${row.q_value == null ? 'Not computed' : esc(Number(row.q_value).toFixed(3))}</td></tr>`).join('')
                : '<tr><td colspan="8">No factor cohorts were reported.</td></tr>'}
            </tbody></table></div>
          </details>
          ${(evidence.warnings || []).map(w => `<p class="op-warning">${esc(w)}</p>`).join('')}
        </div></section>`;
    }catch(err){
      root.innerHTML = `<section class="panel op-empty bad"><h2>Factor evidence unavailable</h2>
        <p>No grade may be inferred while the evidence read model is unavailable.</p></section>`;
    }
  }
  if('IntersectionObserver' in window){
    const observer = new IntersectionObserver(entries => {
      if(entries.some(e => e.isIntersecting)){ observer.disconnect(); load(); }
    }, {rootMargin:'200px'});
    observer.observe(root);
  }else load();
})();
