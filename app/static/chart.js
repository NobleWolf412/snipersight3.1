/* SniperSight CHART surface — phase 2.

   The chart owns the screen and the ticket turns a setup into a decision.
   Three rules this file follows, each learned the hard way:

   1. The ResizeObserver applies `contentRect` and NEVER calls fitContent().
      Calling fitContent() on every resize made the renderer relayout forever
      and the chart came up blank (S9).
   2. Sizing and cost constants come from /api/trade-config. When a surface
      re-derived a number the engine already owned, the two disagreed and the
      operator chased a phantom (2026-07-26). One authority, read over the wire.
   3. Any level the operator drags is tagged `operator`, and the ticket says so
      on screen. Hand-tuned levels must never be counted as engine edge.
*/
window.SSChart = (() => {
  const $ = id => document.getElementById(id);

  let chart = null, series = null, booted = false, visible = false;
  let sym = null, tf = '4H';
  let candles = [], facts = {}, setup = null;
  // `base` is whatever this chart started from — the engine's setup, or levels
  // seeded from the recent range when there is no setup. Either way it is
  // restorable, so an operator who drags into a corner is never stranded.
  let base = null;                            // {entry,tp,sl,dir,kind}
  let modified = false;
  // Per-trade risk. Null means "use the engine default". Deliberately reset on
  // every setup load: an override is a decision about ONE trade, and carrying
  // it silently to the next chart is exactly what the operator ruled out.
  let riskOverride = null;
  let levels = {entry: null, tp: null, sl: null};
  let dir = 'LONG';
  let cfg = null, equity = null;
  let priceLines = {}, zoneLines = [], handles = {};
  let loadSeq = 0;                            // guards out-of-order responses

  const overlays = {swings: true, structure: true, zones: true,
                    liquidity: false, cycle: false};
  const VISIBLE_BARS = 120;                   // the opening window, not the limit

  /* Through SSData. /api/overview, /api/portfolio and /api/trade-config are all
     also read by the shell, so the ticket now sizes against exactly the equity
     and config the Results and Risk panels are displaying — previously they
     came from separate requests and could differ by a poll period.
     Candles and facts key on symbol and timeframe, so switching market is
     always a fresh read; only revisiting the same one inside the window is
     served from cache. */
  const api = p => window.SSData.get(p, 25000);

  /* ---------- price formatting: one token is $60,000 and another $0.00004 ---------- */
  const digits = p => { p = Math.abs(p);
    return p >= 1000 ? 2 : p >= 10 ? 3 : p >= 1 ? 4 : p >= 0.01 ? 5 : 8; };
  const pf = p => p == null || !isFinite(p) ? '—'
    : Number(p).toLocaleString(undefined, {minimumFractionDigits: digits(p),
                                           maximumFractionDigits: digits(p)});
  const usd = n => (n < 0 ? '-$' : '$') + Math.abs(n).toLocaleString(
    undefined, {maximumFractionDigits: Math.abs(n) >= 100 ? 0 : 2});

  /* ---------- boot ---------- */
  function boot(){
    if(booted) return;
    booted = true;
    chart = LightweightCharts.createChart($('chartBox'), {
      layout: {background: {color: 'transparent'}, textColor: '#7d8c83',
               fontFamily: "'JetBrains Mono',ui-monospace,monospace", fontSize: 10},
      grid: {vertLines: {color: 'rgba(255,255,255,.035)'},
             horzLines: {color: 'rgba(255,255,255,.035)'}},
      crosshair: {mode: 0},
      rightPriceScale: {borderColor: 'rgba(255,255,255,.10)'},
      timeScale: {borderColor: 'rgba(255,255,255,.10)',
                  timeVisible: true, secondsVisible: false},
    });
    series = chart.addCandlestickSeries({
      upColor: 'rgba(74,222,128,.75)', downColor: 'rgba(248,113,113,.75)',
      borderUpColor: '#4ade80', borderDownColor: '#f87171',
      wickUpColor: '#4ade80', wickDownColor: '#f87171'});

    // contentRect only — see rule 1 at the top of this file
    new ResizeObserver(es => {
      const {width, height} = es[0].contentRect;
      if(width > 0 && height > 0)
        chart.applyOptions({width: Math.floor(width), height: Math.floor(height)});
    }).observe($('chartBox'));

    for(const k of ['entry', 'tp', 'sl']){
      const el = document.createElement('div');
      el.className = 'lvl lvl-' + k;
      el.innerHTML = '<span></span>';
      el.style.display = 'none';
      el.addEventListener('mousedown', e => startDrag(k, e));
      $('chartHandles').appendChild(el);
      handles[k] = el;
    }
    requestAnimationFrame(syncHandles);
  }

  /* ---------- dragging levels ---------- */
  function startDrag(key, ev){
    if(levels[key] == null) return;
    ev.preventDefault();
    handles[key].classList.add('drag');
    // freeze the chart, or the drag pans the viewport underneath the cursor
    chart.applyOptions({handleScroll: false, handleScale: false});
    const box = $('chartBox').getBoundingClientRect();
    const move = e => {
      const p = series.coordinateToPrice(e.clientY - box.top);
      if(p == null || !isFinite(p) || p <= 0) return;
      levels[key] = p;
      modified = true;
      applyLevels(); recompute();
    };
    const up = () => {
      removeEventListener('mousemove', move);
      handles[key].classList.remove('drag');
      chart.applyOptions({handleScroll: true, handleScale: true});
    };
    addEventListener('mousemove', move);
    addEventListener('mouseup', up, {once: true});
  }

  /* Place the grab tags at their prices. Called directly whenever a level
     changes, and from the rAF loop so panning and zooming keep them glued.
     It must NOT live only in rAF: a backgrounded tab suspends rAF, and the
     tags would then be stale the instant the operator returned. */
  function placeHandles(){
    if(!series) return;
    for(const k of ['entry', 'tp', 'sl']){
      const el = handles[k], p = levels[k];
      const y = p == null ? null : series.priceToCoordinate(p);
      if(y == null){ el.style.display = 'none'; }
      else{
        el.style.display = '';
        el.style.top = y + 'px';
        el.firstChild.textContent = k.toUpperCase() + ' ' + pf(p);
      }
    }
  }
  function syncHandles(){
    if(visible) placeHandles();
    requestAnimationFrame(syncHandles);
  }

  function applyLevels(){
    const spec = {
      entry: {c: '#22d3ee', s: 0, t: 'ENTRY'},
      tp:    {c: '#4ade80', s: 2, t: 'TP'},
      sl:    {c: '#f87171', s: 2, t: 'SL'},
    };
    for(const k of ['entry', 'tp', 'sl']){
      const p = levels[k];
      if(p == null){
        if(priceLines[k]){ series.removePriceLine(priceLines[k]); delete priceLines[k]; }
        continue;
      }
      if(priceLines[k]) priceLines[k].applyOptions({price: p});
      else priceLines[k] = series.createPriceLine({
        price: p, color: spec[k].c, lineWidth: 1, lineStyle: spec[k].s,
        axisLabelVisible: true, title: spec[k].t});
    }
    $('tkEntry').value = levels.entry == null ? '' : pf(levels.entry);
    $('tkTp').value    = levels.tp    == null ? '' : pf(levels.tp);
    $('tkSl').value    = levels.sl    == null ? '' : pf(levels.sl);
    placeHandles();
  }

  /* ---------- the ticket maths ---------- */
  function recompute(){
    const out = $('tkOut'), warn = $('tkWarn');
    const e = levels.entry, tp = levels.tp, sl = levels.sl;
    const long = dir === 'LONG';

    // Say plainly whose numbers these are. Anything the operator touched is
    // excluded from the strategy record, so the label must never read "engine".
    const kind = base ? base.kind : 'none';
    $('tkSrc').textContent = kind === 'engine'
      ? (modified ? 'operator-modified' : 'engine')
      : kind === 'seeded' ? 'operator-seeded' : 'no setup';
    $('tkSrc').className = 'chip ' +
      (kind === 'engine' && !modified ? 'chip-accent' : 'chip-amber');
    $('tkReset').textContent = base && base.kind === 'engine' ? 'Reset to engine' : 'Reset';
    $('tkReset').disabled = !base || !modified;

    if(e == null || tp == null || sl == null){
      out.innerHTML = '<div><span class="k">status</span><span class="v">no levels</span></div>';
      warn.hidden = true;
      return;
    }

    const m = SSTicketMath.ticketMath(
      {dir, entry: e, tp, sl, equity, cfg, riskUsdOverride: riskOverride});

    if(!m.ok){
      out.innerHTML = '<div><span class="k">status</span><span class="v bad">invalid</span></div>';
      warn.hidden = false; warn.innerHTML = m.errors.join('<br>');
      $('tkArm').disabled = true;
      return;
    }

    const rrCls = m.rrNet == null ? '' : m.rrNet >= 2 ? 'good' : m.rrNet >= 1 ? 'warn' : 'bad';
    const row = (k, v, cls) => `<div><span class="k">${k}</span><span class="v ${cls || ''}">${v}</span></div>`;
    out.innerHTML =
      row('risk / unit', pf(m.riskPerUnit)) +
      row('R:R gross', m.rrGross.toFixed(2)) +
      row('R:R after fees', m.rrNet == null ? '—' : m.rrNet.toFixed(2), rrCls) +
      row('position size', m.size == null ? '—' : pf(m.size)) +
      row('notional', m.notional == null ? '—' : usd(m.notional)) +
      row('risk', m.riskUsd == null ? '—' : usd(m.riskUsd)) +
      row('round-trip fees', m.fees == null ? '—' : usd(m.fees),
          m.fees && m.riskUsd && m.fees > m.riskUsd * 0.3 ? 'warn' : '') +
      row('net if target hits', m.netUsd == null ? '—' : usd(m.netUsd),
          m.netUsd > 0 ? 'good' : 'bad');

    // reflect where the risk number came from, without touching the default
    $('tkRisk').value = m.riskUsd == null ? '' : Math.round(m.riskUsd);
    $('tkRiskPct').textContent = m.riskPctEffective == null ? ''
      : '· ' + (m.riskPctEffective * 100).toFixed(2) + '% of account' +
        (m.riskSource === 'operator' ? ' (yours)' : ' (engine default)');
    $('tkRiskReset').disabled = m.riskSource !== 'operator';

    // The maths returns codes for breaches so the wording lives with the UI and
    // the arithmetic stays testable without asserting on prose.
    const WORDING = {
      NOTIONAL_EXCEEDS_BUYING_POWER: () =>
        `Notional ${usd(m.notional)} exceeds buying power ` +
        `(${usd(equity * cfg.max_leverage)} at ${cfg.max_leverage}x). ` +
        'The risk authority would cut this size.',
      RISK_EXCEEDS_TOTAL_BUDGET: () =>
        `Risking ${usd(m.riskUsd)} on one trade is more than the whole ` +
        `open-risk budget (${usd(equity * cfg.max_total_risk_pct)}). ` +
        'That budget is what keeps two concurrent positions survivable.',
      RISK_EXCEEDS_DAILY_HALT: () =>
        `A single loss here (${(m.riskPctEffective * 100).toFixed(1)}%) would ` +
        `breach the ${(cfg.daily_loss_pct * 100).toFixed(0)}% daily halt on its own.`,
    };
    const notes = m.notes.map(n => WORDING[n] ? WORDING[n]() : n);
    warn.hidden = !notes.length;
    warn.innerHTML = notes.join('<br><br>');
    $('tkArm').disabled = true;                 // live stays locked; see setLock()
  }

  /* ---------- overlays + data ---------- */
  /* Blank everything that describes a market, then say why.

     Called on any load failure. An operator reads pixels before they read
     banners, so a populated chart of the WRONG market is more dangerous than
     an empty one — especially with an order ticket attached to it. Every
     figure here is market-specific and must go: series, overlays, bracket
     lines, both header chips, and the Arm button. */
  function clearChart(title, detail){
    candles = [];
    facts = {swing: [], struct: [], zone: [], liq: [], regime: [],
             setupF: [], cycle: [], riskF: []};
    levels = {entry: null, tp: null, sl: null};
    try{ series.setData([]); }catch(e){ /* chart may not be built yet */ }
    try{ drawOverlays(); }catch(e){ /* overlays follow the now-empty facts */ }
    $('cPrice').textContent = '—';
    $('cPrice').className = 'chip';
    $('cRegime').textContent = '—';
    $('tkArm').disabled = true;
    const el = $('chartEmpty');
    el.style.display = '';                    // the bug: only ever unset on success
    el.textContent = detail ? `${title} — ${detail}` : title;
  }

  async function load(){
    if(!sym) return;
    const seq = ++loadSeq;
    const q = k => api(`/api/facts?kind=${k}&symbol=${sym}&tf=${tf}`);
    let res;
    try{
      res = await Promise.all([
        api(`/api/candles?symbol=${sym}&tf=${tf}&limit=1500`),
        q('swing'), q('structure'), q('zone'), q('liquidity'),
        q('regime'), q('setup'), q('cycle'), q('risk')]);
    }catch(err){
      // The failure path used to write into #chartEmpty and return — but
      // #chartEmpty is only ever un-hidden on the SUCCESS path below, so after
      // one good load the message was written into a hidden element and the
      // previous symbol's candles, levels, price chip, regime chip, overlay
      // counts and LIVE ORDER TICKET all stayed on screen under the new
      // symbol's name. `sym`/`tf` were already reassigned by the handlers, so
      // the selector read the new market and every number on it was the old
      // one. That is the worst failure mode this file can produce.
      if(seq === loadSeq) clearChart('Could not load ' + sym + ' · ' + tf, err.message);
      return;
    }
    if(seq !== loadSeq) return;                 // a newer symbol/tf won the race
    // Costs are per VENUE, so the config must be re-read per symbol. Spot fees
    // on a perp chart would flip the sign of the net-R decision.
    try{
      cfg = await api('/api/trade-config?symbol=' + encodeURIComponent(sym));
      setLock();
    }catch(err){ /* keep whatever we had; the ticket labels its source */ }
    if(seq !== loadSeq) return;
    const [c, swing, struct, zone, liq, regime, setupF, cycle, riskF] = res;
    candles = c;
    facts = {swing, struct, zone, liq, regime, setupF, cycle, riskF};

    if(!candles.length){
      // "the venue served nothing here" is a different fact from "the request
      // failed", and the operator has to be able to tell them apart.
      clearChart(`No candles for ${sym} · ${tf}`,
                 'the store holds no bars for this timeframe yet');
      return;
    }
    $('chartEmpty').style.display = 'none';

    series.applyOptions({priceFormat: {type: 'price',
      precision: digits(candles[candles.length - 1].close),
      minMove: Math.pow(10, -digits(candles[candles.length - 1].close))}});
    series.setData(candles);
    // NOT fitContent(): 1500 bars squeezed into one screen is an unreadable
    // hairline. Open on a working window of recent bars — the operator can
    // still scroll back through the full history.
    const n = candles.length, span = Math.min(n, VISIBLE_BARS);
    chart.timeScale().setVisibleLogicalRange({from: n - span, to: n + 4});

    const last = candles[candles.length - 1].close;
    const prev = candles.length > 1 ? candles[candles.length - 2].close : last;
    const chg = ((last - prev) / prev) * 100;
    $('cPrice').textContent = pf(last) + '  ' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
    $('cPrice').className = 'chip ' + (chg >= 0 ? 'chip-green' : 'chip-red');
    const reg = regime.length ? regime[regime.length - 1].regime : null;
    $('cRegime').textContent = reg ? reg.replace('_', ' ') : 'no regime';

    drawOverlays();
    pickSetup();
  }

  /* Build every overlay and report how many objects each one actually drew.
     A toggle that silently draws nothing is indistinguishable from a broken
     button — COTI 4H has zero liquidity and zero cycle facts, and every
     structure fact there is a LABEL. The counts go on the buttons so "nothing
     to show here" never looks like "this control is dead". */
  function drawOverlays(){
    const markers = [];
    const first = candles.length ? candles[0].time : 0;
    const n = {swings: 0, structure: 0, zones: 0, liquidity: 0, cycle: 0};

    for(const s of facts.swing){
      // MICRO/LOCAL are the engine's noise tiers — thousands of them would
      // bury the chart, so the overlay shows the structural ones.
      if(s.tier === 'MICRO' || s.tier === 'LOCAL') continue;
      n.swings++;
      if(!overlays.swings) continue;
      const major = s.tier === 'MAJOR', high = s.type === 'HIGH';
      markers.push({time: s.bar_open_ts, position: high ? 'aboveBar' : 'belowBar',
        shape: high ? 'arrowDown' : 'arrowUp',
        color: major ? '#22d3ee' : (high ? '#f87171' : '#4ade80'),
        size: major ? 2 : 1,
        text: major ? `MAJOR ${high ? 'H' : 'L'}` : undefined});
    }

    for(const f of facts.struct){
      n.structure++;
      if(!overlays.structure) continue;
      if(f.event === 'LABEL'){
        // HH / HL / LH / LL — this IS the market structure the strategy reads.
        // Skipping these left the toggle dead on every 4H chart.
        const high = f.type === 'HIGH';
        markers.push({time: f.market_time, position: high ? 'aboveBar' : 'belowBar',
          shape: 'circle', color: 'rgba(0,0,0,0)', size: 0.1, text: f.label});
      }else{
        const bull = f.direction === 'BULL';
        markers.push({time: f.market_time, position: bull ? 'belowBar' : 'aboveBar',
          shape: bull ? 'arrowUp' : 'arrowDown',
          color: f.event === 'CHOCH' ? '#ffc266' : '#22d3ee', size: 1.5,
          text: f.event === 'CHOCH' ? 'CHoCH' : 'BOS'});
      }
    }

    /* POOL and BROKEN used to be fetched, parsed, and dropped by a `continue`
       — 87% of what the liquidity engine computes, discarded by its only
       consumer. The glossary defines "liquidity pool" as the POOL ("clusters
       of stop-loss orders resting above highs or below lows, price often
       reaches for them before reversing"), and the chart showed only the
       sweep, which is the event that definition does not describe.

       The pool is the FORWARD-looking object — stops are resting there. The
       sweep is retrospective — it already happened. Showing only sweeps meant
       the operator saw the tail of a story whose head was suppressed. */
    for(const f of facts.liq){
      if(f.event !== 'SWEEP') continue;
      n.liquidity++;
      if(!overlays.liquidity) continue;
      markers.push({time: f.market_time, position: f.side === 'HIGH' ? 'aboveBar' : 'belowBar',
        shape: 'circle', color: '#f87171', size: 1, text: 'SWEEP'});
    }

    for(const f of facts.cycle){
      const shown = f.event === 'DCL' || f.event === 'WCL' ||
                    (f.event === 'CYCLE' && f.cycle_kind === 'WEEKLY');
      if(!shown) continue;
      n.cycle++;
      if(!overlays.cycle) continue;
      if(f.event === 'DCL' || f.event === 'WCL'){
        const w = f.event === 'WCL';
        markers.push({time: f.market_time, position: 'belowBar',
          shape: w ? 'square' : 'circle', color: w ? '#22d3ee' : '#0e7490',
          size: w ? 1.5 : 0.8, text: f.event + (f.late ? '·late' : '')});
      }else{
        const col = f.translation === 'right' ? '#4ade80'
                  : f.translation === 'left' ? '#f87171' : '#ffc266';
        markers.push({time: f.market_time, position: 'aboveBar', shape: 'circle',
          color: col, size: 1,
          text: `${(f.translation || '?')[0].toUpperCase()}T${f.failed ? ' FAILED' : ''}`});
      }
    }

    zoneLines.forEach(l => series.removePriceLine(l));
    zoneLines = [];
    const zState = {};
    for(const z of facts.zone) zState[z.zone_id] = z;   // last fact per zone wins
    const active = Object.values(zState)
      .filter(z => z.state !== 'BROKEN' && z.market_time >= first)
      .sort((a, b) => b.anchor_swing_ts - a.anchor_swing_ts).slice(0, 8);
    n.zones = active.length;
    if(overlays.zones) for(const z of active){
      const demand = z.zone_type === 'DEMAND';
      const col = demand ? 'rgba(74,222,128,.45)' : 'rgba(248,113,113,.45)';
      for(const [edge, title] of [['top', demand ? '' : z.zone_type],
                                  ['bottom', demand ? z.zone_type : '']])
        zoneLines.push(series.createPriceLine({price: +z[edge], color: col,
          lineWidth: 1, lineStyle: 1, axisLabelVisible: false, title}));
    }

    /* Active liquidity pools, drawn on the SAME line primitive as zones and
       tracked with the same last-fact-wins map.

       The BROKEN filter is load-bearing and not a tidiness choice: a pool line
       left on the chart after the stops behind it are gone is the most
       confident possible lie this chart can tell — it marks a magnet that no
       longer exists. `state !== 'ACTIVE'` covers BROKEN and both SWEPT states.

       Amber, not red: red is the sweep-and-loss colour throughout this app,
       and a pool is neither. Measured density is a median of 1 active pool per
       symbol/timeframe and a maximum of 2, so the clutter objection does not
       survive contact with the data. */
    const pState = {};
    for(const f of facts.liq) if(f.pool_id) pState[f.pool_id] = f;
    const pools = Object.values(pState)
      .filter(p => p.state === 'ACTIVE' && p.market_time >= first);
    n.liquidity += pools.length;
    if(overlays.liquidity) for(const p of pools){
      zoneLines.push(series.createPriceLine({
        price: +p.level, color: 'rgba(245,158,11,.55)',
        lineWidth: 1, lineStyle: 2,             // dashed: inferred, not measured
        axisLabelVisible: true,
        title: p.side === 'HIGH' ? 'STOPS ABOVE' : 'STOPS BELOW'}));
    }

    markers.sort((a, b) => a.time - b.time);
    series.setMarkers(markers);
    labelOverlays(n);
  }

  /* the count is the honesty: 0 means "no facts on this timeframe", not "off" */
  function labelOverlays(n){
    document.querySelectorAll('#cOverlays button').forEach(b => {
      const k = b.dataset.o, c = n[k];
      b.textContent = b.dataset.label + (c ? ' ' + c : '');
      b.classList.toggle('empty', !c);
      b.title = c ? `${c} on this timeframe`
                  : `nothing recorded for ${k} on ${sym} ${tf}`;
    });
  }

  /* ---------- the setup this chart is about ---------- */
  function pickSetup(){
    const byId = {};
    for(const f of facts.setupF) byId[f.setup_id] = f;
    const all = Object.values(byId);
    const valid = all.filter(f => f.state === 'VALIDATED')
                     .sort((a, b) => b.market_time - a.market_time);
    setup = valid[0] || null;

    modified = false;
    if(setup){
      base = {entry: +setup.entry, tp: +setup.tp, sl: +setup.sl,
              dir: setup.direction, kind: 'engine'};
      // The risk authority has the last word. If it refused this setup, the
      // ticket says so above the rationale — otherwise the chart would invite
      // the operator to size a trade the engine already rejected.
      const d = (facts.riskF || []).filter(
        r => r.event === 'DECISION' && r.setup_id === setup.setup_id).pop();
      const verdict = !d ? '' :
        `<div class="tk-verdict ${d.decision === 'APPROVED' ? 'ok'
           : d.decision === 'REDUCED' ? 'warn' : 'bad'}">` +
        `<b>RISK AUTHORITY: ${d.decision}</b>` +
        (d.decision === 'REJECTED'
          ? `<br>${(d.reasons || []).join(', ').replaceAll('_', ' ').toLowerCase()}` +
            '<br>This setup would not be traded. Anything below is analysis only.'
          : `<br>sizes ${usd(+d.risk_usd)} of risk`) + '</div>';
      $('tkWhy').innerHTML = verdict +
        `<em>Why the engine took it</em>${setup.why || '—'}`;
    }else{
      // No engine setup here. Seed from the recent range so the operator has
      // something to drag — and SAY it is seeded, never dress it as engine output.
      const last = candles.length ? candles[candles.length - 1].close : null;
      if(last == null) base = null;
      else{
        const n = Math.min(14, candles.length);
        const tr = candles.slice(-n).reduce((s, k) => s + (k.high - k.low), 0) / n;
        base = {entry: last, sl: last - tr, tp: last + tr * 2,
                dir: 'LONG', kind: 'seeded'};
      }
      $('tkWhy').innerHTML = '<em>No engine setup on this timeframe</em>' +
        'These levels are seeded from the average 14-bar range so you have ' +
        'something to work from. They are yours, not the engine\'s, and nothing ' +
        'you do here counts toward the strategy record.';
    }
    restore();
  }

  /* put the ticket back to whatever this chart started from */
  function restore(){
    if(!base){ levels = {entry: null, tp: null, sl: null}; }
    else levels = {entry: base.entry, tp: base.tp, sl: base.sl};
    modified = false;
    riskOverride = null;              // an override belongs to one trade only
    setDir(base ? base.dir : 'LONG', true);
    applyLevels();
    recompute();
  }

  function setDir(d, quiet){
    dir = d;
    document.querySelectorAll('#tkDir button').forEach(b =>
      b.classList.toggle('on', b.dataset.d === d));
    if(!quiet){
      if(base && d !== base.dir) modified = true;
      recompute();
    }
  }

  function setLock(){
    const locked = !cfg || !cfg.live_enabled;
    $('tkArm').disabled = true;
    $('tkLock').textContent = locked
      ? (cfg ? cfg.live_locked_reason : 'trade config unavailable')
      : '';
  }

  /* ---------- wiring ---------- */
  function wire(){
    $('cSym').addEventListener('change', e => { sym = e.target.value; load(); });
    $('cTfs').addEventListener('click', e => {
      const b = e.target.closest('button'); if(!b) return;
      tf = b.dataset.tf;
      document.querySelectorAll('#cTfs button').forEach(x => x.classList.toggle('on', x === b));
      load();
    });
    $('cOverlays').addEventListener('click', e => {
      const b = e.target.closest('button'); if(!b) return;
      overlays[b.dataset.o] = !overlays[b.dataset.o];
      b.classList.toggle('on', overlays[b.dataset.o]);
      if(candles.length) drawOverlays();
    });
    $('tkDir').addEventListener('click', e => {
      const b = e.target.closest('button'); if(!b) return;
      setDir(b.dataset.d);
    });
    for(const [id, key] of [['tkEntry', 'entry'], ['tkTp', 'tp'], ['tkSl', 'sl']])
      $(id).addEventListener('change', e => {
        const v = parseFloat(e.target.value.replace(/,/g, ''));
        if(!isFinite(v) || v <= 0){ applyLevels(); return; }   // reject, redraw
        levels[key] = v;
        modified = true;
        applyLevels(); recompute();
      });
    $('tkRisk').addEventListener('change', e => {
      const v = parseFloat(String(e.target.value).replace(/[$,]/g, ''));
      // Sizing THIS trade differently changes nothing else: not the engine
      // default, not any other trade, not the recorded history.
      riskOverride = (isFinite(v) && v > 0) ? v : null;
      if(riskOverride != null) modified = true;
      recompute();
    });
    $('tkRiskReset').addEventListener('click', () => {
      riskOverride = null;
      recompute();
    });
    $('tkTrail').addEventListener('change', e => {
      $('tkTrailRow').hidden = !e.target.checked;
      modified = true;
      recompute();
    });
    $('tkReset').addEventListener('click', restore);
  }

  /* ---------- public ---------- */
  async function onShow(){
    visible = true;
    boot();
    if(!cfg){
      try{
        const p = await api('/api/portfolio');
        equity = p.equity;
      }catch(err){ /* the health chip owns API state; ticket shows dashes */ }
      setLock();
    }
    if(!sym) await populate();
    else recompute();
  }
  function onHide(){ visible = false; }

  async function populate(){
    let o;
    try{ o = await api('/api/overview'); }
    catch(err){ $('chartEmpty').textContent = 'symbol list unavailable'; return; }
    const list = o.symbols.filter(s => s.state !== 'WARMING');
    $('cSym').innerHTML = list.map(s =>
      `<option value="${s.symbol}">${s.symbol.replace('-USD', '')}</option>`).join('');
    if(!sym) sym = list.length ? list[0].symbol : null;
    if(sym){ $('cSym').value = sym; await load(); }
  }

  /* open(symbol, timeframe) — the deck's "Open chart" entry point */
  async function open(s, t){
    sym = s; if(t) tf = t;
    boot();
    document.querySelectorAll('#cTfs button').forEach(b =>
      b.classList.toggle('on', b.dataset.tf === tf));
    if(!$('cSym').options.length) await populate();
    else{ $('cSym').value = sym; await load(); }
  }

  wire();
  return {open, onShow, onHide};
})();
