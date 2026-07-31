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
  let symMeta = {};                           // symbol -> /api/overview row (venue, state)
  let draftPlan = null;                       // engine/draft.py bracket, or null
  let modified = false;
  // Per-trade risk. Null means "use the engine default". Deliberately reset on
  // every setup load: an override is a decision about ONE trade, and carrying
  // it silently to the next chart is exactly what the operator ruled out.
  let riskOverride = null;
  let levels = {entry: null, tp: null, sl: null};
  let dir = 'LONG';
  /* Whether the ticket currently on screen is a plan that could be armed on
     PAPER. Deliberately separate from the live gate: "is this plan valid" and
     "may this system send real orders" are different questions, and folding
     them into one flag is what left the button permanently dead — `setLock()`
     computed a live verdict and then disabled the button unconditionally, so a
     valid paper plan and a missing trade config looked identical. */
  let armable = false;
  /* Operator leverage for THIS trade. A cap on posted margin, never a
     multiplier on risk — see ticket-math.js. Defaults to 1x deliberately: at
     1x you post the full notional and cannot be liquidated by price, so the
     safe end is the one you get without touching anything. Reset per symbol,
     because it means nothing across venues. */
  let leverage = 1;
  let cfg = null, equity = null;
  let priceLines = {}, zoneLines = [], handles = {};
  let drawnKind = null;          // 'engine' | 'draft' — see applyLevels()
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

  /* A DRAFT and an engine plan must not be drawn alike.

     They were. `spec` was one fixed style map, so levels invented from
     `last close ± average 14-bar range` — no zone, no structure, no regime,
     always LONG — got the identical cyan ENTRY, green TP and red SL as a real
     setup. `base.kind` was consulted only for a text chip and a button label,
     and three horizontal price lines outweigh any caption. The code that seeds
     them says "SAY it is seeded, never dress it as engine output"; it said so
     in words and then dressed it anyway.

     Draft covers anything that is not EXACTLY what the engine said — seeded
     levels and dragged ones both. Solid and bright therefore carries one
     meaning: this is the engine's plan, untouched. */
  function applyLevels(){
    const draft = !base || base.kind !== 'engine' || modified;
    const spec = draft ? {
      entry: {c: 'rgba(34,211,238,.40)',  s: 1, t: 'ENTRY · DRAFT'},
      tp:    {c: 'rgba(74,222,128,.40)',  s: 1, t: 'TP · DRAFT'},
      sl:    {c: 'rgba(248,113,113,.40)', s: 1, t: 'SL · DRAFT'},
    } : {
      entry: {c: '#22d3ee', s: 0, t: 'ENTRY'},
      tp:    {c: '#4ade80', s: 2, t: 'TP'},
      sl:    {c: '#f87171', s: 2, t: 'SL'},
    };
    // Price lines only take `price` on update, so a kind change has to redraw
    // them — otherwise dragging an engine plan would keep its solid styling and
    // the distinction would silently stop working after the first edit.
    const want = draft ? 'draft' : 'engine';
    if(drawnKind !== want){
      for(const k of Object.keys(priceLines)){
        series.removePriceLine(priceLines[k]);
        delete priceLines[k];
      }
      drawnKind = want;
    }
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
      : kind === 'draft' ? (modified ? 'operator-modified' : 'structure draft')
      : kind === 'seeded' ? 'not analysis' : 'no setup';
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
      {dir, entry: e, tp, sl, equity, cfg, riskUsdOverride: riskOverride,
       leverage});

    if(!m.ok){
      out.innerHTML = '<div><span class="k">status</span><span class="v bad">invalid</span></div>';
      warn.hidden = false; warn.innerHTML = m.errors.join('<br>');
      armable = false; refreshArm();
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
      // Margin is what leverage actually moves. Shown next to notional so the
      // difference between "the position" and "what it costs to hold" is
      // visible rather than inferred.
      (m.margin == null ? '' : row('margin posted', usd(m.margin) +
          (m.leverage > 1 ? ` at ${m.leverage}x` : ''))) +
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
      // The only BLOCKING wording. It says what to change, because both fixes
      // are in the operator's hands: lower the dial or tighten the stop.
      STOP_BEYOND_LIQUIDATION: () =>
        `At ${m.leverage}x you are liquidated at ${pf(m.liquidation)}, which is ` +
        `before your stop at ${pf(sl)}. The exchange would close this at a loss ` +
        `bigger than the one you set, so the stop — and every R figure built on ` +
        `it — would be fiction. Lower the leverage or move the stop closer.`,
    };
    const notes = m.notes.map(n => WORDING[n] ? WORDING[n]() : n);
    const blocks = m.blocks.map(n => WORDING[n] ? WORDING[n]() : n);
    warn.hidden = !(notes.length || blocks.length);
    warn.innerHTML = blocks.map(b => `<strong class="bad">${b}</strong>`)
                           .concat(notes).join('<br><br>');
    syncLeverage(m);
    /* Breaches in `notes` are shown, not used to block. They are the risk
       authority's warnings about SIZE, and the operator's paper book is where
       they are allowed to disagree with it — that is the point of keeping this
       record separate. The engine's own book still refuses them.

       `blocks` are different in kind and do stop the trade. A stop sitting
       beyond liquidation is not an opinion about sizing: the position would be
       closed by the exchange before the stop was ever reached, so the plan does
       not describe what would happen. `risk.py` refuses these outright; the
       ticket must not offer to record one. */
    armable = m.blocks.length === 0;
    refreshArm();
  }

  /* Keep the dial, its ceiling and the liquidation line in step with the venue.

     Everything here is driven off `cfg.max_leverage`, which arrives per-symbol
     from /api/trade-config. On spot that is 1, so the whole control hides
     itself — the instrument answers the question rather than a mode switch
     somewhere else deciding it. */
  function syncLeverage(m){
    const row = $('tkLevRow'), max = (cfg && cfg.max_leverage) || 1;
    row.hidden = !(max > 1);
    if(row.hidden) return;
    const slider = $('tkLev');
    slider.max = String(max);
    slider.value = String(m && m.leverage ? m.leverage : leverage);
    $('tkLevVal').textContent = slider.value + 'x';
    $('tkLevMax').textContent = `· ${cfg.venue ? cfg.venue.key : ''} allows up to ${max}x`;
    $('tkLiq').textContent = (m && m.liquidation != null)
      ? `liquidation ${pf(m.liquidation)} · ${pf(m.liqDistance)} away`
      : 'no liquidation at 1x — the full notional is posted as margin';
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
    // A cleared chart describes no market, so there is no plan to arm.
    armable = false; refreshArm();
    $('tkArmed').textContent = '';
    const el = $('chartEmpty');
    el.style.display = '';                    // the bug: only ever unset on success
    el.textContent = detail ? `${title} — ${detail}` : title;
  }

  async function load(){
    if(!sym) return;
    // Before the fetch, not after: which instrument this is stays true even
    // when the candles fail to arrive, and it is the thing that says whether
    // the empty chart in front of you is a failure or simply unscanned.
    showVenue();
    const seq = ++loadSeq;
    const q = k => api(`/api/facts?kind=${k}&symbol=${sym}&tf=${tf}`);
    let res;
    try{
      res = await Promise.all([
        api(`/api/candles?symbol=${sym}&tf=${tf}&limit=1500`),
        q('swing'), q('structure'), q('zone'), q('liquidity'),
        q('regime'), q('setup'), q('cycle'), q('risk')]);
      // The draft is fetched, never computed here. Composing a bracket out of
      // zones and pools in the browser would be a second authority for what a
      // level is; `engine/draft.py` owns it and this only displays the answer.
      // Failure is non-fatal — the ticket falls back and says it did.
      try{
        const dr = await api(`/api/draft?symbol=${encodeURIComponent(sym)}&tf=${tf}`);
        draftPlan = dr && dr.draft ? dr.draft : null;
      }catch(err){ draftPlan = null; }
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
    }else if(draftPlan){
      /* No engine setup, but price IS at a level the engine recognises. Draft
         a bracket from it — entry at the zone edge, stop beyond its far edge,
         target at the nearest unbroken pool. Anchored to the market instead of
         to arithmetic, and it says what it stood on. */
      base = {entry: +draftPlan.entry, tp: +draftPlan.tp, sl: +draftPlan.sl,
              dir: draftPlan.direction, kind: 'draft'};
      $('tkWhy').innerHTML =
        '<em>No engine setup — drafted from live structure</em>' +
        draftPlan.basis.map(b => '· ' + b).join('<br>') +
        '<br><br>A starting point anchored to real levels, not an engine ' +
        'setup — the engine has not judged this trade. Yours to change, and ' +
        'nothing you do here counts toward the strategy record.';
    }else{
      /* Nothing near price. The ruler stays ONLY as something to drag, and it
         now says outright that it is not analysis — previously it read as a
         plan because it was drawn like one and described in the same breath as
         the engine's own. `applyLevels` renders it dotted and dimmed. */
      const last = candles.length ? candles[candles.length - 1].close : null;
      if(last == null) base = null;
      else{
        const n = Math.min(14, candles.length);
        const tr = candles.slice(-n).reduce((s, k) => s + (k.high - k.low), 0) / n;
        base = {entry: last, sl: last - tr, tp: last + tr * 2,
                dir: 'LONG', kind: 'seeded'};
      }
      $('tkWhy').innerHTML =
        '<em>Nothing here — price is not at a level the engine recognises</em>' +
        'No setup, and no live zone within 3 ATR to draft against. These ' +
        'numbers are a plain 2:1 drawn around the current price: not a signal, ' +
        'not analysis, and not the engine\'s opinion — just something to drag ' +
        'if you want to trade this anyway. Nothing you do here counts toward ' +
        'the strategy record.';
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

  /* The Arm button commits to the OPERATOR's paper book and nothing else.

     It is not gated on `live_enabled`, because that flag gates a capability
     that does not exist: there is no order-placement code anywhere in this
     system (`execsim` line 3). Wiring a paper button to a live flag would have
     meant the button stayed dead until someone shipped an order router, which
     is why it was dead. The live reason is still printed underneath, so the
     distinction between "your paper trade was recorded" and "this system can
     send real orders" is on screen rather than assumed. */
  function refreshArm(){
    $('tkArm').disabled = !armable || !sym;
    $('tkLock').textContent = (cfg && cfg.live_enabled)
      ? ''
      : (cfg ? 'Live orders: ' + cfg.live_locked_reason
             : 'trade config unavailable');
  }

  function setLock(){ refreshArm(); }

  /* ---------- wiring ---------- */
  function wire(){
    $('cSym').addEventListener('change', e => {
      sym = e.target.value;
      // Leverage means nothing across instruments — 10x on a perp is not a
      // setting that survives a hop to spot. Back to the safe end on every
      // symbol change rather than silently carrying a dial the new venue may
      // not even permit.
      leverage = 1;
      load();
    });
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
    /* Ask the engine to look at THIS symbol. Runs the same pipeline roster the
       live loop runs, so a per-symbol analysis can never disagree with the
       scanner. Slow by nature (~10-20s for five timeframes), so the button
       states what it is doing rather than appearing to hang. */
    $('cAnalyse').addEventListener('click', async () => {
      const b = $('cAnalyse'), was = b.textContent;
      if(!sym || b.disabled) return;
      b.disabled = true; b.textContent = 'analysing…';
      try{
        const r = await fetch('/api/analyse?symbol=' + encodeURIComponent(sym),
                              {method: 'POST'});
        const d = await r.json().catch(() => ({}));
        if(r.status === 404){ b.textContent = 'no candles'; return; }
        if(!r.ok && r.status !== 207){ b.textContent = 'failed'; return; }
        // The facts just changed underneath the cache, so a plain reload would
        // redraw the pre-analysis answer for up to 25 seconds.
        for(const p of ['/api/facts', '/api/candles', '/api/draft'])
          window.SSData.invalidate(p);
        await load();
        const n = Object.values(d.new_facts || {}).reduce((s, v) => s + v, 0);
        b.textContent = (d.errors && d.errors.length)
          ? `partial · ${n} facts` : `+${n} facts`;
      }catch(err){
        b.textContent = 'unreachable';
      }finally{
        setTimeout(() => { b.disabled = false; b.textContent = was; }, 2500);
      }
    });
    /* Arm -> the OPERATOR's paper book (`manual-v0.1-draft`), never the
       strategy record. The reply is reported literally: if the server refuses
       the plan it names the rule that refused it, because "failed" tells an
       operator nothing about what to change. */
    $('tkArm').addEventListener('click', async () => {
      const btn = $('tkArm'), out = $('tkArmed');
      if(btn.disabled) return;
      const riskUsd = parseFloat(String($('tkRisk').value).replace(/[$,]/g, ''));
      btn.disabled = true;
      out.textContent = 'arming…';
      try{
        const r = await fetch('/api/manual/arm', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            symbol: sym, tf: tf, direction: dir,
            entry: levels.entry, tp: levels.tp, sl: levels.sl,
            leverage: leverage,
            risk_usd: isFinite(riskUsd) && riskUsd > 0 ? riskUsd : null})});
        const d = await r.json().catch(() => ({}));
        if(!r.ok){
          out.textContent = 'refused — ' + (d.detail || ('HTTP ' + r.status));
          return;
        }
        const n = d.book ? d.book.n : 0;
        const openN = d.book ? (d.book.open_intents || []).length : 0;
        out.textContent =
          `armed on paper · ${dir} ${sym} ${tf} · entry ${pf(levels.entry)} · ` +
          `your book: ${n} settled, ${openN} open`;
      }catch(err){
        // Never imply an order exists when the request never landed.
        out.textContent = 'could not reach the server — nothing was armed';
      }finally{
        refreshArm();
      }
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
    $('tkLev').addEventListener('input', e => {
      const v = parseInt(e.target.value, 10);
      leverage = isFinite(v) && v >= 1 ? v : 1;
      // Not `modified`: leverage changes how the position is FINANCED, not the
      // engine's plan. Marking it operator-modified would wrongly suggest the
      // entry, target or stop had been touched.
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
    symMeta = {};
    for(const s of list) symMeta[s.symbol] = s;

    /* GROUPED, because 19 of these are scanned and 47 are leftovers nothing
       watches. The picker used to present a 41-day-old symbol the scanner
       dropped months ago with exactly the same standing as BTCUSDT, and the
       ticket would then draw it a full-looking plan. Whether the engine is
       even LOOKING at a symbol is the first thing to know about it. */
    const GROUPS = [
      ['ADMITTED', 'Scanned — the engine watches these'],
      ['SHADOW',   'Shadow — measured, never sized'],
      ['UNTRACKED', 'Not scanned — history only, no engine opinion'],
    ];
    const seen = new Set();
    let html = '';
    for(const [state, label] of GROUPS){
      const rows = list.filter(s => s.state === state);
      if(!rows.length) continue;
      rows.forEach(s => seen.add(s.symbol));
      html += `<optgroup label="${label} (${rows.length})">` +
        rows.map(s => `<option value="${s.symbol}">${optLabel(s)}</option>`).join('') +
        '</optgroup>';
    }
    // Anything in an unexpected state still has to be reachable — a symbol the
    // picker silently omits is one the operator cannot look at to find out why.
    const rest = list.filter(s => !seen.has(s.symbol));
    if(rest.length)
      html += `<optgroup label="Other (${rest.length})">` +
        rest.map(s => `<option value="${s.symbol}">${optLabel(s)}</option>`).join('') +
        '</optgroup>';
    $('cSym').innerHTML = html;

    if(!sym) sym = list.length ? list[0].symbol : null;
    if(sym){ $('cSym').value = sym; await load(); }
  }

  /* The full symbol, never prettified. `.replace('-USD','')` rendered BTC-USD
     as "BTC" while BTCUSDT stayed "BTCUSDT" — so the one string that tells you
     spot from perp was stripped from exactly the symbols where it mattered. */
  function optLabel(s){
    const v = s.venue;
    return v ? `${s.symbol}  ·  ${venueName(v)}` : s.symbol;
  }
  function venueName(v){
    const house = (v.key || '').split('-')[0];
    return `${house.charAt(0).toUpperCase()}${house.slice(1)} ${v.kind}`;
  }

  /* The header chip. Presentation only — every fact in it was decided by
     `venues.py` and served over /api/overview; nothing here re-derives a venue
     from a symbol string. */
  function showVenue(){
    const el = $('cVenue'), m = symMeta[sym];
    if(!m || !m.venue){ el.textContent = '—'; el.className = 'chip'; return; }
    const v = m.venue;
    const lev = v.max_leverage > 1 ? ` · up to ${v.max_leverage}x` : ' · 1x';
    el.textContent = venueName(v) + lev + (v.allow_shorts ? '' : ' · long only');
    el.className = 'chip ' + (m.state === 'ADMITTED' ? 'chip-accent' : 'chip-amber');
    el.title = m.state === 'ADMITTED'
      ? 'the exchange these candles came from — the engine scans this symbol'
      : `the exchange these candles came from — state ${m.state}, the engine is `
        + 'not scanning this symbol, so it will have no setups';
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
