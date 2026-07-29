/* SniperSight shell — navigation, live wiring, and honest failure.
   Phase 1: the five surfaces exist and COMMAND/RESULTS/DIAGNOSTICS carry real
   data. Chart and settings are stubs until phases 2 and 3.
   Loud-fallback rule: a failed fetch says so on screen; it never renders a
   confident-looking zero. */
(() => {
  const $ = id => document.getElementById(id);
  const fmt = n => Number(n).toLocaleString();
  const money = n => '$' + Number(n).toLocaleString(undefined, {maximumFractionDigits: 0});

  /* ---------- navigation ---------- */
  function go(name){
    document.querySelectorAll('.surface').forEach(s => s.classList.toggle('on', s.id === 's' + '-' + name));
    document.querySelectorAll('.nav a').forEach(a => a.classList.toggle('on', a.dataset.s === name));
    if(location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
  }
  document.querySelectorAll('.nav a').forEach(a =>
    a.addEventListener('click', e => { e.preventDefault(); go(a.dataset.s); }));
  addEventListener('hashchange', () => go(location.hash.slice(1) || 'command'));
  go(location.hash.slice(1) || 'command');

  /* ---------- clock ---------- */
  setInterval(() => { $('clock').textContent = new Date().toISOString().slice(11, 19) + 'Z'; }, 1000);

  /* ---------- fetch with visible failure ---------- */
  let degraded = false;
  async function api(path){
    const r = await fetch(path);
    if(!r.ok) throw new Error(path + ' → ' + r.status);
    return r.json();
  }
  function markDegraded(msg){
    degraded = true;
    $('healthOrb').className = 'orb bad';
    $('healthTxt').textContent = 'API DEGRADED';
    $('healthChip').title = msg;
  }

  /* ---------- COMMAND + status bar ---------- */
  async function loadOverview(){
    const o = await api('/api/overview');
    const admitted = o.symbols.filter(s => s.state !== 'WARMING');
    $('mUniverse').textContent = admitted.length;

    const active = o.feed.filter(f => f.state === 'VALIDATED' && !f.result);
    $('mSetups').textContent = active.length;
    $('nCommand').textContent = active.length || '';

    // scanner liveness
    const sc = o.scanner || {};
    $('scanOrb').className = 'orb ' + (sc.alive ? 'good' : 'bad');
    $('scanTxt').textContent = sc.alive ? 'SCANNER LIVE' : 'SCANNER DOWN';

    if(o.baseline){
      $('sbBaseline').textContent = new Date(o.baseline.started_at * 1000).toISOString().slice(0, 10);
      $('baselineChip').textContent = o.baseline.label || 'forward window';
    }
    renderDeck(active, o.rejection_funnel || {});
    renderFunnel(o.rejection_funnel || {});
  }

  /* one card per token; a token already showing keeps its slot (best rank wins) */
  function renderDeck(setups, funnel){
    const el = $('deck');
    if(!setups.length){
      const rows = Object.entries(funnel).sort((a, b) => b[1] - a[1]).slice(0, 3);
      const total = Object.values(funnel).reduce((s, n) => s + n, 0);
      el.innerHTML = '<div class="empty">no setups right now' +
        (total ? '<br><span style="color:var(--fg-3)">' + fmt(total) +
          ' candidates rejected since baseline</span><br>' +
          rows.map(([r, n]) => '<span style="color:var(--amber)">' + fmt(n) + '</span> ' +
            r.replaceAll('_', ' ').toLowerCase()).join('<br>') : '') + '</div>';
      return;
    }
    const best = new Map();                       // symbol -> highest-ranked setup
    for(const s of setups){
      const cur = best.get(s.symbol);
      if(!cur || (s.rank || 0) > (cur.rank || 0)) best.set(s.symbol, s);
    }
    el.innerHTML = [...best.values()].sort((a, b) => (b.rank || 0) - (a.rank || 0)).map(s => {
      const long = s.direction === 'LONG';
      return `<div class="deck-row" style="display:grid;grid-template-columns:120px 96px 1fr auto;
        gap:var(--md);align-items:center;padding:var(--md) var(--lg);border-bottom:1px solid var(--border-soft)">
        <div>
          <div class="t-mono" style="font-size:13px;color:var(--fg)">${s.symbol.replace('-USD','')}</div>
          <div class="t-label">${s.tf} · ${s.strategy.replace('_',' ')}</div>
        </div>
        <div>
          <span class="chip ${long ? 'chip-green' : 'chip-red'}">${s.direction}</span>
          <div class="t-label" style="margin-top:4px">rank ${s.rank}</div>
        </div>
        <div class="t-mono" style="color:var(--fg-3)">
          entry <b style="color:var(--fg)">${(+s.entry).toLocaleString()}</b> ·
          tp <b style="color:var(--green)">${(+s.tp).toLocaleString()}</b> ·
          sl <b style="color:var(--red-2)">${(+s.sl).toLocaleString()}</b> ·
          <span class="term" data-t="rr">R:R</span> ${s.rr}
        </div>
        <button class="btn" data-sym="${s.symbol}" data-tf="${s.tf}">Open chart</button>
      </div>`;
    }).join('');
    el.querySelectorAll('button[data-sym]').forEach(b =>
      b.addEventListener('click', () => go('chart')));
  }

  function renderFunnel(funnel){
    const rows = Object.entries(funnel).sort((a, b) => b[1] - a[1]);
    $('dFunnel').innerHTML = rows.length
      ? rows.map(([r, n]) => `<div style="display:flex;justify-content:space-between;padding:3px 0"
            class="t-mono"><span style="color:var(--fg-3)">${r.replaceAll('_', ' ').toLowerCase()}</span>
            <b style="color:var(--amber)">${fmt(n)}</b></div>`).join('')
      : '<span class="t-mono" style="color:var(--fg-4)">no rejections recorded yet</span>';
  }

  /* ---------- RESULTS ---------- */
  async function loadPortfolio(){
    const p = await api('/api/portfolio');
    const up = p.return_pct >= 0;
    $('mEquity').textContent = money(p.equity);
    $('rEquity').textContent = money(p.equity);
    $('rReturn').textContent = (up ? '+' : '') + p.return_pct + '%';
    $('rReturn').parentElement.className = 'tile ' + (up ? 'up' : 'down');
    $('rDD').textContent = (p.max_drawdown_pct ?? '—') + '%';
    $('rHalt').textContent = p.kill_switch_days ?? 0;
    if(p.config) $('mRisk').textContent = money(p.config.next_risk_usd);
    const d = p.decisions || {};
    $('resultsNote').innerHTML =
      `Risk authority decisions: <b>${d.APPROVED || 0}</b> approved,
       <b>${d.REDUCED || 0}</b> reduced, <b>${d.REJECTED || 0}</b> rejected.
       Sizing runs at ${p.config ? p.config.risk_pct : '—'}% per trade with a
       ${p.config ? p.config.max_total_risk_pct : '—'}% total cap.
       Everything here is <span class="term" data-t="paper">paper</span>.`;
  }

  /* ---------- DIAGNOSTICS ---------- */
  async function loadHealth(){
    const h = await api('/api/pipeline-health');
    const blockers = (h.blockers || []).length, warns = (h.warnings || []).length;
    const good = h.evaluation_allowed && !blockers;
    $('healthOrb').className = 'orb ' + (blockers ? 'bad' : (warns ? 'warn' : 'good'));
    $('healthTxt').textContent = h.status;
    $('dVerdict').textContent = h.status + (h.evaluation_allowed ? '' : ' · BLOCKED');
    $('dVerdict').style.color = good ? 'var(--green)' : (blockers ? 'var(--red)' : 'var(--amber)');
    $('dCounts').textContent = `${blockers} blockers · ${warns} warnings`;
    $('nDiag').textContent = blockers || '';

    const groups = {};
    for(const c of [...(h.blockers || []), ...(h.warnings || [])]){
      const k = c.code + '|' + c.status;
      groups[k] = (groups[k] || 0) + 1;
    }
    const rows = Object.entries(groups).sort((a, b) => b[1] - a[1]);
    $('dIssues').innerHTML = rows.length ? rows.map(([k, n]) => {
      const [code, status] = k.split('|');
      const blocked = status === 'BLOCKED';
      return `<div style="display:flex;align-items:center;gap:var(--md);padding:9px var(--lg);
        border-bottom:1px solid var(--border-soft)">
        <span class="chip ${blocked ? 'chip-red' : 'chip-amber'}">${blocked ? 'blocker' : 'warning'}</span>
        <span class="t-mono" style="color:var(--fg-2)">${code.replaceAll('_', ' ').toLowerCase()}</span>
        <b class="t-mono" style="margin-left:auto;color:var(--fg-3)">×${n}</b></div>`;
    }).join('') : '<div class="empty">no open issues</div>';
  }

  async function loadStatus(){
    const s = await api('/api/status');
    $('sbFacts').textContent = fmt(s.facts);
    $('sbAlgo').textContent = s.algo_version;
  }

  /* ---------- actions ---------- */
  $('btnScan').addEventListener('click', async e => {
    const b = e.currentTarget, was = b.textContent;
    b.disabled = true; b.textContent = 'Scanning…';
    try{
      // Phase 1 wires the existing audit/refresh path; a true on-demand scan
      // trigger lands with the scanner control work in phase 2.
      await fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({paneId:'snipersight', actionId:'audit'})});
      await refresh();
    }catch(err){ markDegraded(String(err)); }
    b.disabled = false; b.textContent = was;
  });

  $('btnAudit').addEventListener('click', async e => {
    const b = e.currentTarget, was = b.textContent;
    b.disabled = true; b.textContent = 'Auditing…';
    try{
      await fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({paneId:'snipersight', actionId:'audit'})});
      await loadHealth();
    }catch(err){ markDegraded(String(err)); }
    b.disabled = false; b.textContent = was;
  });

  $('venue').addEventListener('change', e => {
    // Phase 3 makes this switch adapters. Until then it must not pretend.
    if(e.target.value === 'phemex'){
      alert('Phemex adapter lands in phase 4 (perps: shorts, leverage, liquidation, funding).\n' +
            'All current data is Coinbase spot.');
      e.target.value = 'coinbase';
    }
  });

  /* ---------- refresh loop ---------- */
  async function refresh(){
    const jobs = [loadOverview(), loadPortfolio(), loadHealth(), loadStatus()];
    const results = await Promise.allSettled(jobs);
    const failed = results.filter(r => r.status === 'rejected');
    if(failed.length) markDegraded(failed.map(f => f.reason).join('; '));
    else if(degraded){ degraded = false; }        // health orb is reset by loadHealth
  }
  refresh();
  setInterval(refresh, 30000);
})();
