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
  let allSymbols = [];                        // the full overview list, cached for the picker
  let pickerScope = 'scanned';                // 'scanned' | 'all' — see renderPicker()
  let draftPlan = null;                       // engine/draft.py bracket, or null
  let openPos = [];                           // open manual trades on this chart
  let posLines = [];                          // their price lines, redrawn per load
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
  let refreshTimer = null, refreshing = false;   // see startAutoRefresh()
  let loadedAt = null, freshTimer = null;        // see showFreshness()
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
      : 'at 1x there is no liquidation — slide right to add leverage';
  }

  /* ---------- live price ----------
     /api/ticker has existed since S-whenever with this docstring: "this exists
     purely so the human sees the market move between candle closes". It had
     ZERO callers in the whole of static/ — the liveness feature was built,
     documented, and never connected.

     It goes BESIDE the closed-candle price, never replacing it, and the two are
     visibly different things. §5 is closed-candle-only: every engine, every
     fact, every setup is computed on closed candles, and a live tick must never
     be mistakeable for something the system acted on. So the closed price keeps
     its colour and its chip, and this is a quieter neighbour that says LIVE.

     Stops when the surface is hidden — this is the only poll in the app that
     exists for the eye, so it has no business running when nobody is looking. */
  let tickTimer = null;
  const TICK_MS = 5000;

  async function tickOnce(){
    if(!sym || !visible) return;
    try{
      // short window: a stale live price is worse than none, and this is the
      // one number on screen whose entire value is being current
      const all = await window.SSData.get('/api/ticker', 4000);
      const t = all && all[sym];
      const el = $('cLive');
      if(!el) return;
      if(!t || t.price == null || t.status !== 'OK'){
        el.hidden = true;                      // never show a stale or absent tick
        return;
      }
      el.hidden = false;
      el.textContent = 'LIVE ' + pf(t.price);
      el.title = 'live ticker price, display only — no engine reads this (§5: '
               + 'analysis is closed-candle only)';
    }catch(e){
      const el = $('cLive');
      if(el) el.hidden = true;                 // a failed tick shows nothing
    }
  }

  function startTicker(){
    stopTicker();
    tickOnce();
    tickTimer = setInterval(tickOnce, TICK_MS);
  }
  function stopTicker(){
    if(tickTimer){ clearInterval(tickTimer); tickTimer = null; }
    const el = $('cLive');
    if(el) el.hidden = true;
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
    openPos = [];
    for(const l of posLines){ try{ series.removePriceLine(l); }catch(e){} }
    posLines = [];
    $('tkOpen').innerHTML = '';
    const el = $('chartEmpty');
    el.style.display = '';                    // the bug: only ever unset on success
    el.textContent = detail ? `${title} — ${detail}` : title;
  }

  async function load(opts){
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
      //
      // The seq guard on the ASSIGNMENT matters as much as the one below:
      // `draftPlan` is module state, and a stale load finishing late would
      // otherwise overwrite the new symbol's draft with the old symbol's —
      // the same wrong-market-under-the-right-name failure the catch block
      // below exists to prevent.
      try{
        const dr = await api(`/api/draft?symbol=${encodeURIComponent(sym)}&tf=${tf}`);
        if(seq === loadSeq) draftPlan = dr && dr.draft ? dr.draft : null;
      }catch(err){ if(seq === loadSeq) draftPlan = null; }
      // The operator's open trades here. Same seq guard, same reason.
      try{
        const op = await api(`/api/manual/open?symbol=${encodeURIComponent(sym)}&tf=${tf}`);
        if(seq === loadSeq) openPos = (op && op.open) || [];
      }catch(err){ if(seq === loadSeq) openPos = []; }
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
    $('cPrice').title = 'last CLOSED candle on this timeframe — what the engines see';
    startTicker();
    const reg = regime.length ? regime[regime.length - 1].regime : null;
    $('cRegime').textContent = reg ? reg.replace('_', ' ') : 'no regime';

    drawOverlays();
    pickSetup(!!(opts && opts.keepTicket));
    drawPosition();
    loadedAt = Date.now();
    showFreshness();
  }

  /* The operator's live trade, on the chart and in words.

     Gold and solid, against the ticket's cyan/green/red — these are not plan
     levels to drag, they are the terms of a position already taken, and the
     resolver will settle them whether or not anyone is watching. The readout
     marks to the LAST CLOSED bar and says so; a fresher number here than
     everywhere else would read as precision and be inconsistency. */
  function drawPosition(){
    for(const l of posLines){ try{ series.removePriceLine(l); }catch(e){} }
    posLines = [];
    const el = $('tkOpen');
    if(!openPos.length){ el.innerHTML = ''; return; }
    const p = openPos[0];
    // A trailed trade's stop is wherever the ratchet has moved it — drawing
    // the original would misstate where the trade dies.
    const stopNow = p.current_stop || p.sl;
    for(const [k, price, label] of [['entry', p.fill_price || p.entry, 'YOURS · ENTRY'],
                                    ['tp', p.tp, 'YOURS · TP'],
                                    ['sl', stopNow,
                                     p.trailed ? 'YOURS · TRAIL' : 'YOURS · SL']]){
      const v = parseFloat(price);
      if(isFinite(v)) posLines.push(series.createPriceLine({
        price: v, color: '#fbbf24', lineWidth: 1, lineStyle: k === 'entry' ? 0 : 3,
        axisLabelVisible: true, title: label}));
    }
    const more = openPos.length > 1 ? ` · +${openPos.length - 1} more` : '';
    if(p.state === 'PENDING'){
      el.innerHTML = `PENDING ${p.direction} · limit ${pf(+p.entry)} · ` +
        `fills if touched within ${p.bars_left} more bar${p.bars_left === 1 ? '' : 's'}, ` +
        `else missed${more}`;
      return;
    }
    const r = parseFloat(p.unrealized_r);
    const cls = r >= 0 ? 'good' : 'bad';
    const usd = p.unrealized_usd != null
      ? ` (<span class="${cls}">${(r >= 0 ? '+' : '-')}$${Math.abs(+p.unrealized_usd).toFixed(0)}</span>)` : '';
    el.innerHTML =
      `OPEN ${p.direction} · in at ${pf(+p.fill_price)} · ` +
      `<span class="${cls}">${r >= 0 ? '+' : ''}${r.toFixed(2)}R</span>${usd} ` +
      `at last close · held ${p.bars_held} bar${p.bars_held === 1 ? '' : 's'}${more}`;
  }

  /* State the age of what is on screen, and keep stating it.

     The chart updates once a minute, so "is this current?" is a question the
     operator would otherwise answer by guessing. The ticker runs on its own 5s
     timer rather than the refresh's, because the whole point is to keep
     counting UP when a refresh has NOT happened — a freshness label that only
     moved when the data did would be permanently reassuring and useless.
     Past two minutes it says so: a refresh has been missed and the numbers are
     not what the engine currently holds. */
  function showFreshness(){
    const el = $('cFresh');
    if(!el) return;
    if(!loadedAt){ el.textContent = '—'; el.className = 'chip'; return; }
    const s = Math.round((Date.now() - loadedAt) / 1000);
    el.textContent = s < 5 ? 'just now'
      : s < 90 ? `updated ${s}s ago`
      : `updated ${Math.round(s / 60)}m ago`;
    el.className = 'chip' + (s > 120 ? ' chip-amber' : '');
    el.title = s > 120
      ? 'a refresh has been missed — these numbers may not be what the engine holds'
      : 'age of the data on screen; the chart refreshes every 60s while visible';
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
  function pickSetup(keepTicket){
    const byId = {};
    for(const f of facts.setupF) byId[f.setup_id] = f;
    const all = Object.values(byId);
    const valid = all.filter(f => f.state === 'VALIDATED')
                     .sort((a, b) => b.market_time - a.market_time);
    setup = valid[0] || null;

    /* An operator who has dragged a level or overridden risk owns those
       numbers, and a background refresh must not take them away mid-thought.
       `base` and the rationale below still update — so the Reset button snaps
       to the CURRENT engine plan and the "why" text stays true — but the
       levels on screen are left exactly as they were typed or dragged.
       Without this, auto-refresh would silently delete a half-built trade
       every 60 seconds, which is worse than the staleness it fixes. */
    const editing = keepTicket && (modified || riskOverride != null);
    if(!editing) modified = false;
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
    // Redraw against the refreshed facts without touching the operator's
    // numbers; otherwise put the ticket back to whatever the chart now says.
    if(editing){ applyLevels(); recompute(); }
    else restore();
  }

  /* put the ticket back to whatever this chart started from */
  function restore(){
    if(!base){ levels = {entry: null, tp: null, sl: null}; }
    else levels = {entry: base.entry, tp: base.tp, sl: base.sl};
    modified = false;
    riskOverride = null;              // an override belongs to one trade only
    // The arm confirmation belongs to the trade that was armed. Left in place
    // it would sit under the NEXT symbol's ticket reading "armed on paper ·
    // LONG BTCUSDT ..." while the chart shows ETHUSDT — a stale receipt
    // dressed as a current one.
    $('tkArmed').textContent = '';
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
    /* Ask the engine to look at THIS symbol. Runs the same description-layer
       roster the live loop runs, so a per-symbol analysis can never disagree
       with the scanner. Slow by nature (~10-20s for five timeframes), so the
       button states what it is doing rather than appearing to hang.

       "+0 facts" read as "it did nothing" — but on an already-scanned symbol,
       zero new facts IS the result: facts are content-hashed, so a re-run over
       data the engine has already described inserts nothing. That outcome now
       says so in words, because a number the operator must interpret as
       reassurance is not reassurance. */
    $('cScope').addEventListener('click', () => {
      pickerScope = pickerScope === 'scanned' ? 'all' : 'scanned';
      renderPicker();
    });
    $('cAnalyse').addEventListener('click', async () => {
      const b = $('cAnalyse'), was = b.textContent;
      if(!sym || b.disabled) return;
      b.disabled = true; b.textContent = 'analyzing…';
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
        b.textContent = (d.errors && d.errors.length) ? `partial · ${n} facts`
          : n === 0 ? 'already current'
          : `+${n} facts`;
      }catch(err){
        b.textContent = 'unreachable';
      }finally{
        setTimeout(() => { b.disabled = false; b.textContent = was; }, 4000);
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
      // Captured at click: the reload below may restore() the ticket, and the
      // receipt must quote the price that was ARMED, not the one drawn after.
      const armedEntry = levels.entry, armedDir = dir;
      btn.disabled = true;
      out.textContent = 'arming…';
      try{
        const r = await fetch('/api/manual/arm', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            symbol: sym, tf: tf, direction: dir,
            entry: levels.entry, tp: levels.tp, sl: levels.sl,
            leverage: leverage,
            // The trailing toggle was DECORATIVE — it showed an input and the
            // value went nowhere, an armed promise the resolver never kept.
            // Now it rides the intent, and the resolver honors it.
            trail_r: (() => {
              if(!$('tkTrail').checked) return null;
              const v = parseFloat($('tkTrailR').value);
              return isFinite(v) && v > 0 ? v : null;
            })(),
            risk_usd: isFinite(riskUsd) && riskUsd > 0 ? riskUsd : null})});
        const d = await r.json().catch(() => ({}));
        if(!r.ok){
          out.textContent = 'refused — ' + (d.detail || ('HTTP ' + r.status));
          return;
        }
        const n = d.book ? d.book.n : 0;
        const openN = d.book ? (d.book.open_intents || []).length : 0;
        // Put the position on screen NOW, not at the next refresh — arming
        // and then seeing nothing appear is the report this closes. The
        // receipt is written AFTER the reload because a clean reload runs
        // restore(), which clears the receipt line.
        window.SSData.invalidate('/api/manual/open');
        await load({keepTicket: true});
        out.textContent =
          `armed on paper · ${armedDir} ${sym} ${tf} · entry ${pf(armedEntry)} · ` +
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

  /* Equity, re-read every time rather than once per page load.

     This was guarded by `if(!cfg)`, and `cfg` is assigned by load() — so after
     the first symbol rendered, the branch never ran again and equity was
     FROZEN for the lifetime of the page while `shell.js` refreshed its own
     copy every 30s. The ticket sizes every trade against this number, so a
     stale one silently mis-sizes: position size is `riskUsd / stop distance`
     and `riskUsd` is `equity * risk_pct`. Two surfaces disagreeing about
     equity is the exact defect of 2026-07-26 that /api/trade-config exists to
     prevent, reintroduced one variable over.

     The guard also conflated two unrelated things: whether the trade CONFIG
     had loaded, and whether the ACCOUNT had. They are refreshed separately
     now because they go stale for different reasons. */
  async function loadEquity(){
    try{
      const p = await api('/api/portfolio');
      equity = p.equity;
    }catch(err){ /* the health chip owns API state; ticket shows dashes */ }
  }

  /* ---------- public ---------- */
  async function onShow(){
    visible = true;
    boot();
    await loadEquity();
    setLock();
    if(!sym) await populate();
    // Re-entering the tab used to call recompute() only, which re-does the
    // ticket ARITHMETIC on data already in memory — so the chart showed
    // whatever it had when you last left it, with nothing saying so.
    else await load({keepTicket: true});
    startAutoRefresh();
  }
  function onHide(){
    visible = false;
    // the live tick exists for the eye; it has no business polling when the
    // surface is off screen
    stopTicker();
  }

  /* Keep the chart current while it is on screen.

     There was no refresh of any kind: no timer, no subscription. The chart
     fetched on a symbol or timeframe change and never again, so a bar could
     close, the scanner could write new facts, and the screen would keep
     showing the previous state indefinitely with no indication it was old.

     60s matches the scanner's own poll. It cannot usefully be faster: the
     engines act only on CLOSED candles, so nothing downstream changes until a
     bar closes anyway.

     `keepTicket` is the load-bearing part — see pickSetup(). A refresh that
     reset the ticket would delete levels the operator was in the middle of
     dragging, which is a far worse failure than showing a stale chart. */
  function startAutoRefresh(){
    if(!freshTimer) freshTimer = setInterval(showFreshness, 5000);
    if(refreshTimer) return;
    refreshTimer = setInterval(async () => {
      if(!visible || !sym || refreshing) return;
      refreshing = true;
      try{
        await loadEquity();
        await load({keepTicket: true});
      }catch(err){ /* transient; the health chip reports API state */ }
      finally{ refreshing = false; }
    }, 60000);
  }

  async function populate(){
    let o;
    try{ o = await api('/api/overview'); }
    catch(err){ $('chartEmpty').textContent = 'symbol list unavailable'; return; }
    allSymbols = o.symbols.filter(s => s.state !== 'WARMING');
    symMeta = {};
    for(const s of allSymbols) symMeta[s.symbol] = s;
    ensureInScope();          // a deck-opened symbol may sit outside 'scanned'
    renderPicker();
    if(!sym) sym = allSymbols.length ? allSymbols[0].symbol : null;
    if(sym){ $('cSym').value = sym; await load(); }
  }

  /* Two scopes, because one flat list of 78 was measured to be mostly noise:
     47 entries are former universe members nothing scans, and they buried the
     19 the engine actually watches. Default is the watchlist; "all pairs" is
     one click away and keeps every stored symbol reachable — a symbol the
     picker hides entirely is one the operator cannot inspect to find out why
     it was dropped. Grouping survives in the full view: whether the engine is
     even LOOKING at a symbol is the first thing to know about it. */
  function renderPicker(){
    const scoped = pickerScope === 'scanned'
      ? allSymbols.filter(s => s.state === 'ADMITTED')
      : allSymbols;
    const GROUPS = [
      ['ADMITTED', 'Scanned — the engine watches these'],
      ['SHADOW',   'Shadow — measured, never sized'],
      ['UNTRACKED', 'Not scanned — history only, no engine opinion'],
    ];
    const seen = new Set();
    let html = '';
    for(const [state, label] of GROUPS){
      const rows = scoped.filter(s => s.state === state);
      if(!rows.length) continue;
      rows.forEach(s => seen.add(s.symbol));
      html += `<optgroup label="${label} (${rows.length})">` +
        rows.map(s => `<option value="${s.symbol}">${optLabel(s)}</option>`).join('') +
        '</optgroup>';
    }
    const rest = scoped.filter(s => !seen.has(s.symbol));
    if(rest.length)
      html += `<optgroup label="Other (${rest.length})">` +
        rest.map(s => `<option value="${s.symbol}">${optLabel(s)}</option>`).join('') +
        '</optgroup>';
    // Narrowing the scope must never orphan the chart on screen. A <select>
    // whose value is not among its options silently displays the first entry
    // while `sym` says otherwise — the wrong-market-under-the-right-name
    // failure again. The current symbol rides along as its own group instead.
    if(sym && symMeta[sym] && !scoped.some(s => s.symbol === sym))
      html += '<optgroup label="Current — not on the watchlist">' +
        `<option value="${sym}">${optLabel(symMeta[sym])}</option></optgroup>`;
    $('cSym').innerHTML = html;
    if(sym && symMeta[sym]) $('cSym').value = sym;
    const btn = $('cScope');
    if(btn){
      btn.textContent = pickerScope === 'scanned'
        ? `all pairs (${allSymbols.length})`
        : 'watchlist only';
      btn.title = pickerScope === 'scanned'
        ? 'show every stored symbol, including shadow and unscanned ones'
        : 'back to just the symbols the engine scans';
    }
  }

  /* A symbol outside the current scope must widen the scope, not vanish.
     The deck's "Open chart", a shadow pair, or a hand-typed URL can land on a
     symbol the scanned view does not contain; a <select> whose value is not
     among its options silently shows the first entry while `sym` says
     otherwise — the wrong-market-under-the-right-name failure again. */
  function ensureInScope(){
    if(pickerScope === 'scanned' && sym && symMeta[sym]
       && symMeta[sym].state !== 'ADMITTED'){
      pickerScope = 'all';
      renderPicker();
    }
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
    el.title = (m.state === 'ADMITTED'
      ? 'the exchange these candles came from — the engine scans this symbol'
      : `the exchange these candles came from — state ${m.state}, the engine is `
        + 'not scanning this symbol, so it will have no setups')
      + (v.max_leverage > 1
         ? '. Leverage is set per trade with the dial at the top of the order ticket.'
         : '');
  }

  /* open(symbol, timeframe) — the deck's "Open chart" entry point */
  async function open(s, t){
    sym = s; if(t) tf = t;
    boot();
    document.querySelectorAll('#cTfs button').forEach(b =>
      b.classList.toggle('on', b.dataset.tf === tf));
    if(!$('cSym').options.length) await populate();   // handles scope + load itself
    else{ ensureInScope(); $('cSym').value = sym; await load(); }
  }

  wire();
  return {open, onShow, onHide};
})();
