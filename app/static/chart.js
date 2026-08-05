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
  // How many markers the narrow-screen cap held back on the last paint. Zero
  // on desktop and whenever nothing was dropped. Read by the introspection
  // hook so a hidden marker is a question with an answer.
  let lastMarkerDrop = 0;
  let sym = null, tf = '4H';
  let candles = [], facts = {}, setup = null;
  // `base` is whatever this chart started from — the engine's setup, or levels
  // seeded from the recent range when there is no setup. Either way it is
  // restorable, so an operator who drags into a corner is never stranded.
  let base = null;                            // {entry,tp,sl,dir,kind}
  let symMeta = {};                           // symbol -> /api/overview row (venue, state)
  let allSymbols = [];                        // the full overview list, cached for the picker
  // scope state died with the scope toggle: the picker lists everything, grouped
  let draftPlan = null;                       // engine/draft.py bracket, or null
  let openPos = [];                           // open manual trades on this chart
  let enginePos = null;                       // the ENGINE's open trade here, if any
  let posLines = [];                          // their price lines, redrawn per load
  let modified = false;
  // Per-trade risk. Null means "use the engine default". Deliberately reset on
  // every setup load: an override is a decision about ONE trade, and carrying
  // it silently to the next chart is exactly what the operator ruled out.
  let riskOverride = null;
  let levels = {entry: null, tp: null, sl: null};
  let dir = 'LONG';
  /* The scale-out rung the ticket currently describes, or null. Read from the
     form by recompute() and kept here so drawScale(), the Arm payload and the
     block reason all quote ONE answer — three readers parsing the same two
     inputs is three chances to disagree about where the rung sits. */
  let scalePlan = null;                       // {fraction, atR, price, blocked}
  let scaleLine = null;                       // its dashed line on the chart
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
  // the last computed ticket maths, so the Arm button can state WHY it is
  // disabled instead of leaving the reason in footer prose
  let lastMetrics = null;
  let volSeries = null;                       // the volume histogram pane
  let priceLines = {}, zoneLines = [], handles = {};
  // what the grab tags say and whether they go gold — applyLevels owns these
  let lvlSpec = null, lvlLive = false;
  let drawnKind = null;          // 'engine' | 'draft' — see applyLevels()
  let refreshTimer = null, refreshing = false;   // see startAutoRefresh()
  let loadedAt = null, freshTimer = null;        // see showFreshness()
  let loadSeq = 0;                            // guards out-of-order responses
  // Which market the screen currently DESCRIBES — set only when a load paints,
  // nulled whenever the screen is cleared. load() compares against it to tell
  // a switch (clear first, everything on screen is the old market) from a
  // refresh (repaint in place, never flash).
  let painted = null;                         // 'SYM|TF' of the painted market

  /* The four layers below (gaps/shelf/ranges/signals) read engines that ran
     from the beginning and had nowhere to appear. They are LAZY: their facts
     are fetched the first time the layer is switched on for a symbol/timeframe
     and cached until the market changes, so a chart nobody asked to decorate
     costs exactly what it did before. Default OFF for the same reason — the
     operator's standing complaint about this surface is clutter, and the fix
     for "I can't see momentum" is not "here is everything at once". */
  let extra = {};                 // kind -> facts[], for extraKey's market only
  let extraKey = null;            // 'SYM|TF' the cache belongs to
  const LAZY = {gaps: 'fvg', shelf: 'volprofile', ranges: 'range',
                signals: 'momentum|volume|volatility'};
  const overlays = {swings: true, structure: true, zones: true,
                    liquidity: false, cycle: false,
                    gaps: false, shelf: false, ranges: false, signals: false};
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

    /* VOLUME, on a chart whose engine computes 231,946 volume facts and whose
       operator could not see a single bar of it. Its own price scale, pinned
       to the bottom fifth: an overlay scale means the candles and the
       histogram share a range and the price series collapses to a hairline.
       No axis labels — the QUESTION volume answers is "more or less than the
       bars around it", which is shape, not magnitude. */
    volSeries = chart.addHistogramSeries({
      priceScaleId: 'vol', priceFormat: {type: 'volume'},
      color: 'rgba(148,163,184,.35)'});
    chart.priceScale('vol').applyOptions({
      scaleMargins: {top: 0.86, bottom: 0}, visible: false});

    /* OHLC READOUT. Hovering a candle told the operator nothing — the single
       most basic thing a chart does. Reads from the crosshair, falls back to
       the last bar when the pointer leaves, so the strip is never blank. */
    chart.subscribeCrosshairMove(param => {
      const bar = param && param.seriesData && param.seriesData.get(series);
      paintOHLC(bar || (candles.length ? candles[candles.length - 1] : null));
    });

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
      el.addEventListener('pointerdown', e => startDrag(k, e));
      $('chartHandles').appendChild(el);
      handles[k] = el;
    }
    requestAnimationFrame(syncHandles);
  }

  /* ---------- dragging levels ----------

     POINTER, not mouse. These were the last mouse-only handlers in the file;
     every other listener is a click, which Android synthesises from a tap. A
     finger produced no mousedown at all, so the three levels that define the
     trade could be moved with a mouse and by nothing else — on the surface
     whose entire job is planning that trade.

     Three things a mouse never made us think about:

     · CAPTURE. A cursor stays under the button it pressed; a fingertip is a
       9mm contact patch that rolls and slides off a 3mm handle mid-gesture.
       Without setPointerCapture the drag simply stops partway, leaving the
       level wherever the finger happened to lose it — silently, and on a
       control that decides where money stops.

     · touch-action. The browser decides whether a gesture is yours or a
       scroll BEFORE your handler sees it, and it decides scroll. `.lvl` gets
       touch-action:none in ss.css; without it this code is correct and never
       runs.

     · pointercancel. A mouse-up always arrives. A touch can be taken away —
       the system claims it for a gesture, the palm lands, a call comes in —
       and then no pointerup is ever sent. The old `up` released the chart's
       pan/zoom, so on that path the chart would have stayed frozen with no
       way back short of reloading. Both endings release it now. */
  const FLING_FACTOR = 3;      // one gesture may not change risk by more than this
  function startDrag(key, ev){
    if(levels[key] == null) return;
    if(ev.button != null && ev.button > 0) return;      // right-click is not a drag
    ev.preventDefault();
    const el = handles[key];
    el.classList.add('drag');
    // freeze the chart, or the drag pans the viewport underneath the pointer
    chart.applyOptions({handleScroll: false, handleScale: false});
    const box = $('chartBox').getBoundingClientRect();
    const riskBefore = riskDistance();
    /* Route every later event for this finger to the handle, so sliding off
       it — or off the chart entirely — keeps dragging instead of dropping the
       level where contact was lost. */
    try{ el.setPointerCapture(ev.pointerId); }catch(_){ /* pre-capture browser */ }

    const move = e => {
      if(e.pointerId !== ev.pointerId) return;          // a second finger is not this drag
      const p = series.coordinateToPrice(e.clientY - box.top);
      if(p == null || !isFinite(p) || p <= 0) return;
      levels[key] = p;
      modified = true;
      applyLevels(); recompute();
    };
    const end = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', end);
      el.removeEventListener('pointercancel', end);
      try{ el.releasePointerCapture(ev.pointerId); }catch(_){}
      el.classList.remove('drag');
      chart.applyOptions({handleScroll: true, handleScale: true});
      flagFling(riskBefore);
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
  }

  /* The distance the trade risks per unit — |entry - stop|, the same quantity
     manual.risk_per_unit computes server-side. Read, not re-derived: it is
     only ever compared with itself here, never shown. */
  function riskDistance(){
    if(levels.entry == null || levels.sl == null) return null;
    return Math.abs(levels.entry - levels.sl);
  }

  /* A FLING IS ARITHMETICALLY VALID. The drag rejects impossible prices —
     non-finite, zero, negative — and nothing else, so a finger that skids
     across the chart and lands the stop 10% away produces a perfectly legal
     trade: wider risk, smaller size, no complaint anywhere. On a mouse that
     barely happens. On a phone, one pixel of finger travel is several ticks
     and the gesture is exactly the one a bumpy train produces.

     So it warns rather than blocks — the operator may genuinely want a much
     wider stop, and a control that refuses a legitimate intent is worse than
     one that asks. It says the factor, because "your risk tripled" is the
     sentence that makes someone look. */
  let flung = null;
  function flagFling(before){
    const after = riskDistance();
    flung = null;
    if(before && after && before > 0){
      const factor = after / before;
      if(factor > FLING_FACTOR || factor < 1 / FLING_FACTOR)
        flung = {factor, wider: factor > 1};
    }
    refreshArm();
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
        /* The one label a plan level gets: WHOSE · WHICH and the price, on
           the thing you drag. The state vocabulary (PLAN / ENGINE / LIVE)
           used to live only in the right-axis tags this replaced. */
        el.firstChild.textContent =
          (lvlSpec ? lvlSpec[k].t : k.toUpperCase()) + '  ' + pf(p);
        el.style.color = lvlLive ? '#fbbf24' : '';
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
    /* Three visual states, because they mean three different things:
       LIVE (gold, solid) is money at stake right now; ENGINE (bright) is the
       machine's untouched plan; DRAFT (dotted, dim) is a sketch. */
    const live = !!enginePos;
    const draft = !live && (!base || base.kind !== 'engine' || modified);
    const spec = live ? {
      entry: {c: '#fbbf24', s: 0, t: 'LIVE · IN AT'},
      tp:    {c: '#fbbf24', s: 2, t: modified ? 'YOUR TARGET' : 'LIVE · TARGET'},
      sl:    {c: '#fbbf24', s: 2, t: modified ? 'YOUR STOP' : 'LIVE · STOP'},
    } : draft ? {
      /* "DRAFT" was jargon and an operator asked what it meant, fairly: it is
         the app's word, not the market's. Every label now reads WHOSE · WHICH,
         so the four states on this chart answer "what am I looking at" without
         a legend — PLAN (yours, unarmed), ENGINE (its plan, unarmed), YOURS
         (armed and resting on the book), LIVE (filled, money at stake). */
      entry: {c: 'rgba(34,211,238,.40)',  s: 1, t: 'PLAN · ENTRY'},
      tp:    {c: 'rgba(74,222,128,.40)',  s: 1, t: 'PLAN · TP'},
      sl:    {c: 'rgba(248,113,113,.40)', s: 1, t: 'PLAN · SL'},
    } : {
      entry: {c: '#22d3ee', s: 0, t: 'ENGINE · ENTRY'},
      tp:    {c: '#4ade80', s: 2, t: 'ENGINE · TP'},
      sl:    {c: '#f87171', s: 2, t: 'ENGINE · SL'},
    };
    // Price lines only take `price` on update, so a kind change has to redraw
    // them — otherwise dragging an engine plan would keep its solid styling and
    // the distinction would silently stop working after the first edit.
    const want = live ? ('live' + (modified ? '-edited' : ''))
               : draft ? 'draft' : 'engine';
    if(drawnKind !== want){
      for(const k of Object.keys(priceLines)){
        series.removePriceLine(priceLines[k]);
        delete priceLines[k];
      }
      drawnKind = want;
    }
    /* SIX LABELS FOR THREE PRICES. Arming a plan draws the order's own gold
       lines while the ticket keeps drawing the identical levels underneath, so
       the chart stacked "PLAN · TP" and "YOURS · TP" on the same pixel — and
       the operator read it as the app having done something twice. The armed
       order is the authority wherever the two agree; drag a level and the plan
       line reappears, because then it is saying something different. */
    const taken = positionPrices();
    const same = (a, b) => Math.abs(a - b) <= Math.abs(a) * 1e-9;

    for(const k of ['entry', 'tp', 'sl']){
      const p = levels[k];
      if(p != null && taken.some(v => same(v, p))){
        if(priceLines[k]){ series.removePriceLine(priceLines[k]); delete priceLines[k]; }
        continue;
      }
      if(p == null){
        if(priceLines[k]){ series.removePriceLine(priceLines[k]); delete priceLines[k]; }
        continue;
      }
      if(priceLines[k]) priceLines[k].applyOptions({price: p});
      /* No axis label: the grab tag IS this level's one label (state, name,
         price — see placeHandles). Each plan price was printed twice, in the
         drag pill on the left and again as an axis tag on the right, and the
         operator read the pair as two different things. The split is now
         semantic: LEFT is your editable plan, the RIGHT axis carries only
         facts — the live price, armed orders, the zone shelf. */
      else priceLines[k] = series.createPriceLine({
        price: p, color: spec[k].c, lineWidth: 1, lineStyle: spec[k].s,
        axisLabelVisible: false});
    }
    // the grab tags render from these — set BEFORE placeHandles paints
    lvlSpec = spec; lvlLive = live;
    $('tkEntry').value = levels.entry == null ? '' : pf(levels.entry);
    $('tkTp').value    = levels.tp    == null ? '' : pf(levels.tp);
    $('tkSl').value    = levels.sl    == null ? '' : pf(levels.sl);
    placeHandles();
  }

  /* ---------- the ticket maths ---------- */
  function recompute(){
    const out = $('tkOut'), key = $('tkKey'), warn = $('tkWarn');
    const e = levels.entry, tp = levels.tp, sl = levels.sl;
    const long = dir === 'LONG';

    // Say plainly whose numbers these are. Anything the operator touched is
    // excluded from the strategy record, so the label must never read "engine".
    const kind = base ? base.kind : 'none';
    /* One word each. The long forms ("structure draft", "operator-modified")
       overflowed the 268px head and wrapped it to two rows; the Why pane
       already carries the full sentence for every one of these states. */
    $('tkSrc').textContent = kind === 'position'
      ? (modified ? 'your exit — unsaved' : 'open position')
      : kind === 'engine'
      ? (modified ? 'edited' : 'engine')
      : kind === 'draft' ? (modified ? 'edited' : 'your plan')
      : kind === 'seeded' ? 'manual' : 'no setup';
    $('tkSrc').className = 'chip ' +
      (kind === 'engine' && !modified ? 'chip-accent' : 'chip-amber');
    // Name what you are reverting TO. On a live position that is the levels
    // the trade is actually resting at, which is not the same promise as
    // "reset" on a plan that has never been committed to anything.
    $('tkReset').textContent = kind === 'position' ? 'Back to live levels'
      : base && base.kind === 'engine' ? 'Reset to engine' : 'Reset';
    /* Reset is live whenever the form DIFFERS from what it was given — it was
       gated on `modified`, which only tracks dragged levels, so a ticket with
       an operator risk override or a moved leverage dial showed a dead Reset
       beside values that plainly were not the defaults. */
    $('tkReset').disabled = !base ||
      !(modified || riskOverride != null || (leverage || 1) > 1);

    /* Both early returns skip syncLeverage(), which is the ONLY writer of the
       leverage row, the dial bounds and the liquidation line — so a symbol
       with no plan kept showing the previous symbol's "liquidation X · Y away"
       and the previous venue's "up to Nx". Cleared before either return, and
       the no-levels branch now disarms like its sibling does. */
    const clearSized = () => {
      try{ syncLeverage(null); }catch(err){ /* row may not exist yet */ }
      $('tkRiskPct').textContent = '';
      $('tkRisk').value = '';
      // A rung is priced off the entry and the stop. With no valid levels there
      // is no price to state, and leaving the last one on screen would put a
      // stale number beside a ticket that has none.
      paintScale(null);
    };

    if(e == null || tp == null || sl == null){
      out.innerHTML = key.innerHTML =
        '<div><span class="k">status</span><span class="v">no levels</span></div>';
      warn.hidden = true;
      clearSized();
      armable = false; refreshArm();
      return;
    }

    const m = SSTicketMath.ticketMath(
      {dir, entry: e, tp, sl, equity, cfg, riskUsdOverride: riskOverride,
       leverage,
       // Holding: R keeps the denominator the trade was ENTERED with, so the
       // stop can be dragged past entry to lock in a winner.
       holding: !!enginePos,
       originalRisk: enginePos
         ? Math.abs(+enginePos.entry - +enginePos.sl) : null,
       partial: readScale()});

    if(!m.ok){
      out.innerHTML = key.innerHTML =
        '<div><span class="k">status</span><span class="v bad">invalid</span></div>';
      warn.hidden = false; warn.innerHTML = m.errors.join('<br>');
      clearSized();
      armable = false; refreshArm();
      return;
    }

    const rrCls = m.rrNet == null ? '' : m.rrNet >= 2 ? 'good' : m.rrNet >= 1 ? 'warn' : 'bad';
    const row = (k, v, cls) => `<div><span class="k">${k}</span><span class="v ${cls || ''}">${v}</span></div>`;

    /* The three that decide it, pinned outside the panes: what the trade pays
       relative to what it risks, how big it is, and what it costs you if the
       stop hits. Everything else is the working, and lives in the Numbers
       pane — visible on request rather than occupying the panel by default. */
    key.innerHTML =
      row('R:R after fees', m.rrNet == null ? '—' : m.rrNet.toFixed(2), rrCls) +
      row('size', m.size == null ? '—' : pf(m.size)) +
      row('you risk', m.riskUsd == null ? '—' : usd(m.riskUsd));

    /* The Numbers pane holds only the WORKING — the three figures the decision
       rests on are pinned right beneath it, so repeating them here spent three
       rows saying what is already permanently on screen an inch lower. */
    out.innerHTML =
      row('risk / unit', pf(m.riskPerUnit)) +
      row('R:R gross', m.rrGross.toFixed(2)) +
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
          m.netUsd > 0 ? 'good' : 'bad') +
      // A stop past the entry cannot lose. Say what it guarantees, because
      // that is the entire reason for dragging it there.
      (m.lockedR == null ? ''
        : row('stop now locks in', '+' + m.lockedR.toFixed(2) + 'R', 'good'));

    // reflect where the risk number came from, without touching the default
    $('tkRisk').value = m.riskUsd == null ? '' : Math.round(m.riskUsd);
    /* "(engine default)" wrapped the label to a second line in the 268px
       column; the disabled Default button already says the value IS the
       default, so the suffix only flags the exceptional case. */
    $('tkRiskPct').textContent = m.riskPctEffective == null ? ''
      : '· ' + (m.riskPctEffective * 100).toFixed(2) + '% of account' +
        (m.riskSource === 'operator' ? ' — yours' : '');
    $('tkRiskReset').disabled = m.riskSource !== 'operator';

    // The maths returns codes for breaches so the wording lives with the UI and
    // the arithmetic stays testable without asserting on prose.
    const WORDING = {
      /* The check (ticket-math.js) compares margin at the CHOSEN leverage
         against equity; this sentence used to quote buying power at the venue
         MAXIMUM, so at 1x it claimed $30,699 exceeds $97,105 — a false
         statement about a true breach. It now names the numbers that were
         actually compared, and the fix that is in the operator's hands. */
      /* The remedy names the leverage that ACTUALLY clears the breach, not
         merely that headroom exists. Gating on `m.leverage < cfg.max_leverage`
         alone advised raising the dial in cases where even the venue maximum
         still leaves margin above equity — telling someone to take more
         leverage on a trade that will be cut anyway. It also stays silent
         about the cost: leverage clears this by posting less, and posting
         less is what pulls liquidation toward the entry. */
      NOTIONAL_EXCEEDS_BUYING_POWER: () => {
        const need = Math.ceil(m.notional / equity);
        return `A ${usd(m.notional)} position at ${m.leverage}x needs ` +
          `${usd(m.margin)} of margin — more than the ${usd(equity)} account. ` +
          'A tight stop sizes a big position for the same risk. ' +
          (need <= cfg.max_leverage && m.leverage < need
            ? `At ${need}x you would post ${usd(m.notional / need)} instead — ` +
              'but that pulls liquidation toward your entry.'
            : 'The risk authority will cut this size.');
      },
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
    /* Margin above equity BLOCKS. The maths reports it as a note, and a note
       left Arm enabled and primary while grey footer prose explained that a
       $32,158 position could not be posted from a $9,646 account — the
       operator's own money, described in the quietest text on the panel,
       beside a live button. The risk authority refuses these anyway; offering
       an action that will be refused is the defect. Kept OUT of ticket-math
       so no engine rule moves: this is the ticket declining to offer
       something, not a change to what is permitted. */
    lastMetrics = m;
    paintScale(m.partial || null);
    const overMargin = (m.notes || []).includes('NOTIONAL_EXCEEDS_BUYING_POWER');
    armable = m.blocks.length === 0 && !overMargin;
    refreshArm();
  }

  /* ---------- the scale-out rung ---------- */

  /* What the two inputs currently say, or null when the toggle is off.
     Percent in the form, fraction on the wire — the engine records fractions
     and a UI that shipped "50" as a fraction would take fifty times the
     position off. */
  function readScale(){
    if(!$('tkScale') || !$('tkScale').checked) return null;
    const pct = parseFloat(String($('tkScalePct').value).replace(/[%,]/g, ''));
    const atR = parseFloat(String($('tkScaleR').value).replace(/[R,]/gi, ''));
    return {fraction: isFinite(pct) ? pct / 100 : NaN,
            atR: isFinite(atR) ? atR : NaN};
  }

  /* State where the rung lands, in price, and draw it.

     R is what the operator types; PRICE is what gets recorded, what the
     resolver tests against a bar, and what the chart can show. Printing only
     the R would leave the one number the trade actually turns on unstated —
     the same reason the liquidation line prints a price beside the leverage
     dial rather than a multiple. */
  const SCALE_BLOCK = {
    FRACTION_RANGE: 'Take off between 1% and 99% — 100% is a target, not a ' +
      'scale-out, and the trade needs something left to settle at the stop.',
    FRACTION_TOO_SMALL: 'A slice under 1% pays more in fees than it can change ' +
      'the result.',
    NO_PRICE: 'Set how far in R to take it off.',
    OUTSIDE_BRACKET: 'That lands outside your stop and target, so the trade ' +
      'would already have ended before price got there. Move it inside, or ' +
      'move the target.',
  };

  function paintScale(p){
    scalePlan = (p && p.blocked == null) ? p : null;
    const note = $('tkScaleAt');
    if(note){
      note.textContent = !p ? ''
        : p.blocked ? (SCALE_BLOCK[p.blocked] || p.blocked)
        : `takes ${Math.round(p.fraction * 100)}% off at ${pf(p.price)} · ` +
          `${(1 - p.fraction) * 100 < 1 ? '' : Math.round((1 - p.fraction) * 100) + '% '}` +
          'rides to the target or the stop';
      note.className = 't-mono' + (p && p.blocked ? ' bad' : '');
    }
    drawScale();
  }

  function drawScale(){
    if(scaleLine){ try{ series.removePriceLine(scaleLine); }catch(e){} scaleLine = null; }
    if(!series || !scalePlan || !isFinite(scalePlan.price)) return;
    // Dashed and dim like every other unarmed plan level — this is a rung the
    // operator is drawing, not a level anything is resting at yet.
    scaleLine = series.createPriceLine({
      price: scalePlan.price, color: 'rgba(34,211,238,.40)', lineWidth: 1,
      lineStyle: 1, axisLabelVisible: false,
      title: `PLAN · ${Math.round(scalePlan.fraction * 100)}% OFF`});
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
    // "· phemex-perp allows up to 10x" wrapped the label to two lines in the
    // 268px column; the venue is already named on the chart's venue chip.
    $('tkLevMax').textContent = `· up to ${max}x`;
    /* Liquidation AND the cost of holding, on the same line, because they are
       the two things leverage changes that the R figures deliberately do not
       reflect. Funding has always been charged by the simulator and was shown
       nowhere: a perp held over a weekend pays every settlement, and on a
       tight target that can exceed the edge (UX audit, 4 Aug 2026).

       Stated per DAY rather than per settlement — "0.03%/day" is a number an
       operator can weigh against a target; "0.01% every 8 hours" is homework.
       Modelled, and labelled as modelled: this is the constant the cost model
       charges, not a live quote from the venue. */
    const liq = (m && m.liquidation != null)
      ? `liquidation ${pf(m.liquidation)} · ${pf(m.liqDistance)} away`
      : 'no liquidation at 1x';
    const perDay = cfg && cfg.cost && cfg.cost.funding_per_day
      ? cfg.cost.funding_rate * cfg.cost.funding_per_day * 100 : 0;
    $('tkLiq').textContent = perDay
      ? `${liq} · funding ≈${perDay.toFixed(3)}%/day to hold`
      : liq;
    $('tkLiq').title = perDay
      ? `Perps charge funding every ${(24 / cfg.cost.funding_per_day).toFixed(0)}` +
        ` hours while the position is open. This is the modelled rate the cost` +
        ` engine charges, not a live quote — a multi-day hold pays it` +
        ` repeatedly, and on a tight target that can cost more than the trade` +
        ` makes.`
      : 'Spot positions pay no funding — you own the asset outright.';
  }

  /* ---------- the context ladder ----------
     /api/context shipped with the docstring "compact synchronized context
     strip for the decision workspace" and had zero callers. Meanwhile the
     chart showed the regime of ONE timeframe, and the decision needs the
     ladder: a 4H long inside a 1D downtrend is a different trade from the same
     entry with the trend at its back. Market Weather already shows this per
     symbol on Command — this is the same fact repeated at the point where the
     trade is actually committed, which is where it earns its screen space.

     Colour only, one letter-group per timeframe, detail in the title: the
     ladder is context, and context must never be louder than the chart. */
  const LADDER_TONE = {
    BULL_TREND: 'lx-bull', WEAKENING_BULL: 'lx-bull-w',
    BEAR_TREND: 'lx-bear', WEAKENING_BEAR: 'lx-bear-w',
    TRANSITION: 'lx-trans', RANGE: 'lx-range',
  };
  async function loadContext(){
    /* The per-timeframe ladder read as a second timeframe picker — same
       shape, adjacent position, different meaning, hover-only explanation.
       The same facts now live on the regime chip's hover: context, priced
       at exactly the attention it deserves. */
    const el = $('cRegime');
    if(!el || !sym) return;
    try{
      const c = await api('/api/context?symbol=' + encodeURIComponent(sym));
      el.title = 'regime by timeframe' + String.fromCharCode(10) + (c.timeframes || []).map(t => {
        const label = t.regime ? t.regime.replace('_', ' ').toLowerCase() : 'no reading';
        const extra = (t.active_zones ? ` · ${t.active_zones} zones` : '')
                    + (t.ready ? ` · ${t.ready} ready` : '');
        return `${t.tf === tf ? '▸' : ' '} ${t.tf}: ${label}${extra}`;
      }).join(String.fromCharCode(10));
    }catch(e){
      el.title = '';                   // absent context beats stale context
    }
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
      const el = $('cLiveIn');
      if(!el) return;
      if(!t || t.price == null || t.status !== 'OK'){
        el.hidden = true;                      // never show a stale or absent tick
        return;
      }
      el.hidden = false;
      el.textContent = ' · live ' + pf(t.price);
    }catch(e){
      const el = $('cLiveIn');
      if(el) el.hidden = true;                 // a failed tick shows nothing
    }
  }

  /* The four numbers a candle is, plus its volume. Fixed-width and
     tabular so hovering across bars does not make the strip twitch. */
  function paintOHLC(bar){
    const el = $('cOHLC'); if(!el) return;
    if(!bar){ el.textContent = ''; return; }
    const up = bar.close >= bar.open;
    const v = bar.volume == null ? '' :
      `  V ${bar.volume >= 1e6 ? (bar.volume / 1e6).toFixed(1) + 'M'
           : bar.volume >= 1e3 ? (bar.volume / 1e3).toFixed(1) + 'K'
           : Math.round(bar.volume)}`;
    el.textContent = `O ${pf(bar.open)}  H ${pf(bar.high)}  ` +
                     `L ${pf(bar.low)}  C ${pf(bar.close)}${v}`;
    el.className = 't-mono c-ohlc ' + (up ? 'up' : 'down');
  }

  function startTicker(){
    stopTicker();
    tickOnce();
    tickTimer = setInterval(tickOnce, TICK_MS);
  }
  function stopTicker(){
    if(tickTimer){ clearInterval(tickTimer); tickTimer = null; }
    const el = $('cLiveIn');
    if(el) el.hidden = true;
  }

  /* ---------- overlays + data ---------- */
  /* Blank everything that describes a market, then say why.

     Called on any load failure. An operator reads pixels before they read
     banners, so a populated chart of the WRONG market is more dangerous than
     an empty one — especially with an order ticket attached to it. Every
     figure here is market-specific and must go: series, overlays, bracket
     lines, both header chips, the Arm button, and the whole order ticket —
     its pinned figures, its warning, its rationale and its source chip. */
  function clearChart(title, detail){
    painted = null;                 // the screen no longer describes any market
    candles = [];
    facts = {swing: [], struct: [], zone: [], liq: [], regime: [],
             setupF: [], cycle: [], riskF: []};
    levels = {entry: null, tp: null, sl: null};
    /* Nulling `levels` is not clearing them: applyLevels() is the only thing
       that removes the entry/tp/sl price lines from the series and blanks the
       three inputs, so without this call a cleared chart kept the previous
       market's bracket drawn on it and editable. `base`, `modified` and the
       per-trade risk override are market-specific for the same reason — a
       stale `base` would let Reset restore the WRONG symbol's plan. */
    base = null; modified = false; riskOverride = null;
    /* The ticket maths too: refreshArm() below rebuilds the blocking notice
       from `lastMetrics`, and stale metrics re-painted the OLD market's
       margin line — "posts $20,838" — under the NEW market's loading state
       (caught on camera, beta demo 4 Aug 2026). */
    lastMetrics = null;
    try{ applyLevels(); }catch(e){ /* chart may not be built yet */ }
    try{ series.setData([]); }catch(e){ /* chart may not be built yet */ }
    try{ drawOverlays(); }catch(e){ /* overlays follow the now-empty facts */ }
    $('cPx').textContent = '—'; $('cChg').textContent = '';
    $('cLiveIn').hidden = true; $('cPrice').className = 'chip';
    $('cRegime').textContent = '—'; $('cRegime').title = '';
    // market-specific like everything else here — a ladder for the WRONG
    // symbol is worse than none (see the rule at the top of clearChart)
    // A cleared chart describes no market, so there is no plan to arm.
    armable = false; refreshArm();
    /* The TICKET is market-specific too, and it was the one thing clearChart
       never touched: a blank chart labelled XRPUSDT sat directly above BTC's
       R:R, BTC's position size and BTC's dollar risk, in 17px display type on
       the strip whose whole job is to be the last thing read before arming.
       recompute()'s no-levels branch writes both #tkKey and #tkOut and hides
       #tkWarn, and with `base` nulled above it resets the source chip to
       "no setup". It runs AFTER refreshArm() so it cannot re-enable Arm. */
    try{ recompute(); }catch(e){ /* ticket may not be built yet */ }
    $('tkWhy').innerHTML = '';
    $('tkLiq').textContent = '';
    $('tkRiskPct').textContent = '';
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
    paintSymBtn();
    window.SSChartCtx = {symbol: sym, tf};
    // The live suffix is per-symbol and the ticker only corrects it every 5s —
    // long enough for BTC's tick to sit beside LINK's closed price, which is
    // the wrong-market-under-the-right-name failure with a $55k tell. Hide it
    // now; the next tick repaints it for the RIGHT symbol.
    if($('cLiveIn')) $('cLiveIn').hidden = true;
    /* A SWITCH is not a refresh. Until the new market's data lands, every
       pixel below the header — candles, both chips, the bracket, the ticket,
       the Arm button — still describes the OLD market under the NEW name.
       That window measured 3+ seconds on a cold symbol, and Arm stayed live
       through it: the confirm dialog quoted one market's levels over another
       market's symbol (beta pass, 4 Aug 2026). clearChart() is the one honest
       state for that interval. Same-market refreshes skip it, so the 60s
       repaint and the post-arm reload never flash. */
    if(painted !== sym + '|' + tf)
      clearChart('Loading ' + sym + ' · ' + tf + '…');
    const seq = ++loadSeq;
    /* ONE NUMBER FOR "how much chart is there". The candle request and every
       fact request quote the same window, so a marker can never be drawn from
       evidence outside the bars on screen — and, more to the point, evidence
       outside those bars is never sent. /api/facts had no limit clause at
       all: it returned every fact ever written for the symbol and timeframe,
       forever, and the chart discarded everything older than its oldest
       candle. Measured for BTCUSDT 4H: swing 134KB and ma 131KB alone, about
       half a megabyte across the kinds, to draw markers over 1500 bars.
       Invisible on loopback; most of the page weight on a phone. */
    const BARS = 1500;
    const q = k => api(`/api/facts?kind=${k}&symbol=${sym}&tf=${tf}&bars=${BARS}`);
    let res;
    try{
      res = await Promise.all([
        api(`/api/candles?symbol=${sym}&tf=${tf}&limit=${BARS}`),
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
        if(seq === loadSeq){
          openPos = (op && op.open) || [];
          enginePos = (op && op.engine) || null;
        }
      }catch(err){ if(seq === loadSeq){ openPos = []; enginePos = null; } }
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
    painted = sym + '|' + tf;      // from here down, the screen describes THIS market
    /* Lazy-layer facts are per market — drop them the moment the market
       changes, or the old symbol's gaps would be drawn under the new
       symbol's candles. The RE-FETCH is deliberately not here: awaiting it
       before setData meant the price chart waited on four decorative
       queries, and a refresh landing mid-await could return past the paint
       and leave the chart blank. Layers fill in after price is on screen. */
    if(extraKey !== painted){ extra = {}; extraKey = painted; }

    series.applyOptions({priceFormat: {type: 'price',
      precision: digits(candles[candles.length - 1].close),
      minMove: Math.pow(10, -digits(candles[candles.length - 1].close))}});
    series.setData(candles);
    /* Volume coloured by the bar it belongs to, so a spike reads as buying or
       selling at a glance instead of as a bare quantity. */
    if(volSeries) volSeries.setData(candles.map(c => ({
      time: c.time, value: c.volume || 0,
      color: c.close >= c.open ? 'rgba(74,222,128,.30)' : 'rgba(248,113,113,.30)'})));
    paintOHLC(candles[candles.length - 1]);
    // NOT fitContent(): 1500 bars squeezed into one screen is an unreadable
    // hairline. Open on a working window of recent bars — the operator can
    // still scroll back through the full history.
    const n = candles.length, span = Math.min(n, VISIBLE_BARS);
    chart.timeScale().setVisibleLogicalRange({from: n - span, to: n + 4});

    const last = candles[candles.length - 1].close;
    const prev = candles.length > 1 ? candles[candles.length - 2].close : last;
    const chg = ((last - prev) / prev) * 100;
    $('cPx').textContent = pf(last);
    $('cChg').textContent = ' ' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
    $('cPrice').className = 'chip ' + (chg >= 0 ? 'chip-green' : 'chip-red');
    $('cPrice').title = 'last CLOSED candle — what the engines see. The live suffix is for the eye only; the dot is data freshness.';
    startTicker();
    loadContext();
    const reg = regime.length ? regime[regime.length - 1].regime : null;
    $('cRegime').textContent = reg ? reg.replace('_', ' ') : 'no regime';

    drawOverlays();
    pickSetup(!!(opts && opts.keepTicket));
    drawPosition();
    loadedAt = Date.now();
    showFreshness();

    /* Lazy layers refill AFTER price is on screen, and deliberately without
       an await on the caller: the chart is complete without them, and a
       decorative query must never be able to delay or blank the candles.
       The seq guard means a switch mid-fetch drops the stale layer instead
       of drawing it over the new market. */
    const layerSeq = seq;
    (async () => {
      for(const key of Object.keys(LAZY)) if(overlays[key]) await ensureLayer(key);
      if(layerSeq === loadSeq && candles.length) drawOverlays();
    })();
  }

  /* The operator's live trade, on the chart and in words.

     Gold and solid, against the ticket's cyan/green/red — these are not plan
     levels to drag, they are the terms of a position already taken, and the
     resolver will settle them whether or not anyone is watching. The readout
     marks to the LAST CLOSED bar and says so; a fresher number here than
     everywhere else would read as precision and be inconsistency. */
  /* The prices the operator's own armed order is already drawing, so the
     ticket does not label them a second time. Empty when nothing is armed. */
  function positionPrices(){
    if(!openPos.length) return [];
    const p = openPos[0];
    return [p.fill_price || p.entry, p.tp, p.current_stop || p.sl]
      // The armed order's rungs count too: the ticket's dashed "PLAN · 50% OFF"
      // line sitting on the same pixel as the order's own gold one is the
      // six-labels-for-three-prices defect with a fourth price added.
      .concat((p.partials_planned || []).map(r => r.price))
      .map(v => parseFloat(v)).filter(v => isFinite(v));
  }

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
    /* The ladder, on the chart. A rung already taken is drawn as a fact — the
       size behind it is gone — and one still waiting as a dotted intention, so
       "what have I got left on" is answered by looking rather than by counting
       back from a percentage in a panel. */
    const done = (p.partials_filled || []).map(r => String(r.price));
    for(const r of (p.partials_planned || [])){
      const v = parseFloat(r.price);
      if(!isFinite(v)) continue;
      const filled = done.includes(String(r.price));
      posLines.push(series.createPriceLine({
        price: v, color: filled ? 'rgba(251,191,36,.55)' : '#fbbf24',
        lineWidth: 1, lineStyle: filled ? 3 : 2, axisLabelVisible: true,
        title: `YOURS · ${Math.round(+r.fraction * 100)}% ${filled ? 'OFF' : 'AT'}`}));
    }
    const more = openPos.length > 1 ? ` · +${openPos.length - 1} more` : '';
    if(p.state === 'PENDING'){
      el.innerHTML = `PENDING ${p.direction} · limit ${pf(+p.entry)} · ` +
        `fills if touched within ${p.bars_left} more bar${p.bars_left === 1 ? '' : 's'}, ` +
        `else missed${more}`;
      return;
    }
    /* The BLENDED figure headlines, because it is what the trade is worth: the
       rungs already banked plus what is still on. `unrealized_r` alone would
       quote the open remainder's per-unit R as if the whole position were
       still riding it — the same overstatement the Your-trades panel made. */
    const r = parseFloat(p.blended_r != null ? p.blended_r : p.unrealized_r);
    const cls = r >= 0 ? 'good' : 'bad';
    const usd = p.unrealized_usd != null
      ? ` (<span class="${cls}">${(r >= 0 ? '+' : '-')}$${Math.abs(+p.unrealized_usd).toFixed(0)}</span>)` : '';
    const off = Math.round((+p.closed_fraction || 0) * 100);
    el.innerHTML =
      `OPEN ${p.direction} · in at ${pf(+p.fill_price)} · ` +
      `<span class="${cls}">${r >= 0 ? '+' : ''}${r.toFixed(2)}R</span>${usd} ` +
      `at last close · held ${p.bars_held} bar${p.bars_held === 1 ? '' : 's'}` +
      (off > 0 ? ` · ${off}% taken off (${(+p.realized_r).toFixed(2)}R banked)` : '') +
      more;
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
    /* The dot on the price chip. The chip-sized "updated 30s ago" label was
       the widest reflow source on the surface and one more thing to read;
       a dot that goes amber past two minutes says the same thing in zero
       words, with the sentence on hover. */
    const el = $('cDot');
    if(!el) return;
    if(!loadedAt){ el.className = 'dot'; return; }
    const s = Math.round((Date.now() - loadedAt) / 1000);
    el.className = 'dot ' + (s > 120 ? 'stale' : 'ok');
    el.title = s > 120
      ? 'a refresh has been missed — these numbers may not be what the engine holds'
      : 'data fresh (' + (window.SSClock ? SSClock.ago(s) : s + 's') + ') — refreshes every 60s while visible';
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

    /* ── the engines that had nowhere to appear ──────────────────────────
       Everything below reads a lazily-fetched kind. `extra[k]` is undefined
       until the layer has been switched on once for this market, and an
       undefined kind contributes nothing and counts zero — so a layer that
       has never been opened is indistinguishable from one with no facts,
       which is exactly right: neither has anything to show. */
    const ex = k => extra[k] || [];

    /* GAPS. A fair-value gap is a hole in the tape: price moved so fast that
       a whole band went untraded. They tend to get revisited, which makes an
       unfilled one a magnet and a filled one history. Last fact per gap wins,
       and FILLED gaps are dropped — a gap line left up after it has been
       traded through marks a level that no longer exists, the same lie the
       liquidity-pool filter above exists to prevent. */
    const gapState = {};
    for(const g of ex('fvg')) gapState[g.gap_id] = g;
    const openGaps = Object.values(gapState)
      .filter(g => g.event !== 'FILLED' && g.market_time >= first)
      .sort((a, b) => b.market_time - a.market_time).slice(0, 6);
    n.gaps = openGaps.length;
    if(overlays.gaps) for(const g of openGaps){
      const bull = g.direction === 'BULL';
      const col = bull ? 'rgba(74,222,128,.34)' : 'rgba(248,113,113,.34)';
      for(const [edge, title] of [['top', bull ? '' : 'GAP'],
                                  ['bottom', bull ? 'GAP' : '']])
        zoneLines.push(series.createPriceLine({price: +g[edge], color: col,
          lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title}));
    }

    /* VOLUME SHELF. Where the market actually did its business. HVN is a price
       the market keeps agreeing on — it slows down there; LVN is a band it
       crossed in a hurry and tends to cross in a hurry again. Drawn as the
       shelf edges, deduped by bin so a state that reports every bar does not
       stack fifty identical lines on one price. */
    /* AT_HVN / AT_LVN / MID — the engine's Schmitt-trigger states, not bare
       HVN/LVN. Matching the wrong strings drew nothing and reported "no
       data" over 81 real facts, which is the exact failure this whole layer
       set exists to end. */
    const bins = {};
    for(const v of ex('volprofile'))
      if(v.state === 'AT_HVN' || v.state === 'AT_LVN') bins[v.bin_lo + '|' + v.state] = v;
    const shelves = Object.values(bins)
      .sort((a, b) => b.market_time - a.market_time).slice(0, 8);
    n.shelf = shelves.length;
    if(overlays.shelf) for(const v of shelves){
      const hvn = v.state === 'AT_HVN';
      zoneLines.push(series.createPriceLine({
        price: (+v.bin_lo + +v.bin_hi) / 2,
        color: hvn ? 'rgba(148,163,184,.55)' : 'rgba(217,119,6,.45)',
        lineWidth: hvn ? 2 : 1,
        lineStyle: hvn ? 0 : 2,          // solid = traded heavily, dashed = thin
        axisLabelVisible: false, title: hvn ? 'HVN' : 'LVN'}));
    }

    /* RANGES. The sideways boxes the market has been respecting. BROKEN ones
       go for the same reason broken zones do. */
    const rState = {};
    for(const r of ex('range')) rState[r.range_id] = r;
    const liveRanges = Object.values(rState)
      .filter(r => r.event !== 'BROKEN' && r.state !== 'BROKEN')
      .sort((a, b) => b.market_time - a.market_time).slice(0, 2);
    n.ranges = liveRanges.length;
    if(overlays.ranges) for(const r of liveRanges)
      for(const [edge, title] of [['top', 'RANGE'], ['bottom', '']])
        zoneLines.push(series.createPriceLine({price: +r[edge],
          color: 'rgba(56,189,248,.40)', lineWidth: 1, lineStyle: 3,
          axisLabelVisible: false, title}));

    /* MOMENTUM, VOLUME AND VOLATILITY — one layer, because they answer one
       question together: is price arriving at this structure with force
       behind it, or out of breath? That is the reading the operator asked
       for by name ("highly beneficial to know about momentum when analyzing
       price against structure"), and it is a property of a MOMENT, so it
       belongs on the bar it happened to rather than in a side panel.

       Only the events that change a decision are drawn. MACD_ZERO, VWAP
       crosses and ATR-regime changes fire constantly and would rebuild the
       clutter this layer exists to justify removing. */
    /* TEXT IS THE CLUTTER, not the markers. The first cut labelled every
       event and produced three overlapping "DIVERGENCE" tags and a stack of
       "2.1x VOL / 3.1x VOL" on adjacent bars — the exact look this surface
       was cleaned up to remove. Only divergence keeps a word, because it is
       the only one whose meaning is not carried by its own shape and colour;
       the rest are read positionally, against the structure they sit on. */
    const sig = [];
    for(const m of ex('momentum')){
      if(m.event === 'DIVERGENCE'){
        // price made the high; momentum did not follow. The one momentum
        // event that speaks directly about structure.
        const bear = m.side === 'HIGH' || m.direction === 'BEAR';
        sig.push({time: m.market_time, position: bear ? 'aboveBar' : 'belowBar',
          shape: bear ? 'arrowDown' : 'arrowUp', color: '#a78bfa', size: 1.3,
          text: 'DIV'});
      }else if(m.event === 'RSI_BAND' && m.state){
        const hot = /OVERBOUGHT/i.test(m.state);
        if(!hot && !/OVERSOLD/i.test(m.state)) continue;
        sig.push({time: m.market_time, position: hot ? 'aboveBar' : 'belowBar',
          shape: 'circle', color: hot ? '#f87171' : '#4ade80', size: 0.8});
      }
    }
    /* A 2x-of-baseline bar is common enough to be background. The threshold
       is raised here rather than in the engine because the ENGINE's job is to
       record every crossing for grading; the CHART's job is to show the ones
       worth looking at. */
    for(const v of ex('volume')){
      if(v.event !== 'RVOL' || v.rvol_state !== 'HOT') continue;
      if(!(+v.rvol >= 2.5)) continue;
      sig.push({time: v.market_time, position: 'belowBar', shape: 'square',
        color: '#fbbf24', size: 0.85});
    }
    for(const v of ex('volatility')){
      if(v.event !== 'SQUEEZE') continue;
      /* `squeeze` is the STRING 'ON'/'OFF' — volatility.py emits
         {"squeeze": new, "from": state, "state": "CHANGED"|"ESTABLISHED"}.
         The first cut tested `=== true` and `state === 'ON'`, neither of
         which can ever match: `state` is the event PHASE, not the squeeze.
         So this marker silently never drew, the same class of failure as the
         AT_HVN mismatch beside it. Caught 4 Aug 2026 by enumerating the real
         values in the store rather than reading the code. */
      if(v.squeeze !== 'ON') continue;      // the squeeze forming is the signal
      sig.push({time: v.market_time, position: 'belowBar', shape: 'circle',
        color: '#38bdf8', size: 0.75});
    }
    // Most recent first: an old signal off the left edge of the opening
    // window cannot inform the trade being considered now.
    sig.sort((a, b) => b.time - a.time);
    const shown = sig.slice(0, 40);
    n.signals = shown.length;
    if(overlays.signals) markers.push(...shown);

    markers.sort((a, b) => a.time - b.time);
    /* A PHONE CANNOT DRAW ALL OF THEM AND SHOULD NOT TRY.
       Every layer contributes markers and only the signals layer was ever
       bounded; swings, structure, sweeps and cycles are as many as the window
       holds. On a desktop that is dense but legible. On a 412px screen the
       glyphs overlap into a smear, and every one of them is re-laid-out on
       each frame of a pinch, which is where the judder comes from.

       The cap keeps the MOST RECENT, because that is the end of the chart the
       operator is looking at and the end that bears on the next decision.
       Dropping is never silent: the count goes to the console and the
       introspection hook below reports it, so "why can I not see that swing"
       has an answer other than a shrug. Desktop is unchanged. */
    const narrow = matchMedia('(max-width:640px)').matches;
    const MAX_MARKERS = 60;
    let drawn = markers;
    if(narrow && markers.length > MAX_MARKERS){
      drawn = markers.slice(-MAX_MARKERS);
      lastMarkerDrop = markers.length - drawn.length;
      console.info(`[chart] ${lastMarkerDrop} older markers hidden at this ` +
                   `width (showing the most recent ${MAX_MARKERS} of ` +
                   `${markers.length})`);
    } else {
      lastMarkerDrop = 0;
    }
    series.setMarkers(drawn);
    labelOverlays(n);
  }

  /* Fetch a lazy layer's facts once per market, then redraw.

     Every kind behind one toggle is fetched together, so switching "Momentum"
     on asks for momentum, volume and volatility in one go and never asks
     again until the symbol or timeframe changes. Failure is silent-but-honest:
     the kind stays an empty array, so the toggle reports "no data" rather than
     appearing to work. */
  async function ensureLayer(key){
    const kinds = (LAZY[key] || '').split('|').filter(Boolean);
    if(!kinds.length) return;
    const want = sym + '|' + tf;
    if(extraKey !== want){ extra = {}; extraKey = want; }
    const missing = kinds.filter(k => !extra[k]);
    if(!missing.length) return;
    const btn = document.querySelector(`#cLayersPop [data-o="${key}"]`);
    if(btn) btn.classList.add('loading');
    await Promise.all(missing.map(async k => {
      try{
        // Same window as the base load — an overlay drawn from deeper history
        // than the candles beneath it is evidence for bars that are not there.
        const rows = await api(
          `/api/facts?kind=${k}&symbol=${encodeURIComponent(sym)}&tf=${tf}&bars=1500`);
        // the market may have changed while this was in flight
        if(extraKey === want) extra[k] = Array.isArray(rows) ? rows : [];
      }catch(err){ if(extraKey === want) extra[k] = []; }
    }));
    if(btn) btn.classList.remove('loading');
  }

  function paintLayersBtn(){
    const on = Object.values(overlays).filter(Boolean).length;
    $('cLayersBtn').textContent = `Layers ${on}/${Object.keys(overlays).length}`;
  }

  /* the count is the honesty: 0 means "no facts on this timeframe", not "off" */
  function labelOverlays(n){
    document.querySelectorAll('#cLayersPop button').forEach(b => {
      const k = b.dataset.o, c = n[k];
      /* Name only. "Swings 42" put a fact-store row count on a toggle whose
         only question is on/off — 42 of what, and is 42 good? The count keeps
         living in the tooltip for whoever wants it. */
      b.textContent = b.dataset.label;
      b.classList.toggle('empty', !c);
      /* Nine toggles whose only question is on/off, and the state lived purely
         in a class. A screen-reader operator could not tell which layers were
         drawn on the chart they were being asked to trade from. */
      b.setAttribute('aria-pressed', String(b.classList.contains('on')));
      // in the menu, absence is said in words — a struck-through control
      // reads as broken every time
      if(!c) b.textContent = b.dataset.label + ' — no data';
      /* Composed, not replaced. Overwriting the title destroyed the authored
         notes on Liquidity and Cycle — the only place the chart says those
         overlays are INFERRED rather than measured — leaving a bare count in
         their place. The note lives in data-note now and the count joins it. */
      const count = c ? `${c} recorded on this timeframe`
                      : `nothing recorded for ${k} on ${sym} ${tf}`;
      b.title = [b.dataset.note, count].filter(Boolean).join(' — ');
    });
    paintLayersBtn();
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

    /* An OPEN ENGINE POSITION outranks everything else this ticket could
       show. You are already in the trade; the only decision left is where it
       ends, so the ticket loads its live levels and the commit button becomes
       "Update trade". Dragging a level then takes custody: the operator's
       stop and target settle on THEIR book while the engine keeps simulating
       the plan it entered on, which is what makes the two comparable. */
    if(enginePos){
      base = {entry: +enginePos.entry, tp: +enginePos.tp, sl: +enginePos.sl,
              dir: enginePos.direction, kind: 'position'};
      $('tkWhy').innerHTML =
        '<em>You are in this trade — the engine entered it</em>' +
        `Filled ${pf(+enginePos.entry)} · stop ${pf(+enginePos.sl)} · target ` +
        `${pf(+enginePos.tp)}. Drag a level and press <b>Update trade</b> to ` +
        'take it onto your book with your own exit — trailing included. The ' +
        'engine keeps simulating its original plan either way, so both ' +
        'outcomes get recorded and you can see which was better.';
      if(editing){ applyLevels(); recompute(); }
      else restore();
      return;
    }

    if(setup){
      base = {entry: +setup.entry, tp: +setup.tp, sl: +setup.sl,
              dir: setup.direction, kind: 'engine'};
      // The risk authority has the last word. If it refused this setup, the
      // ticket says so above the rationale — otherwise the chart would invite
      // the operator to size a trade the engine already rejected.
      const d = (facts.riskF || []).filter(
        r => r.event === 'DECISION' && r.setup_id === setup.setup_id).pop();
      /* The verdict names what happened to the TRADE, not which component ruled
         on it. "RISK AUTHORITY: REJECTED / concurrent limit(2)" told the reader
         the name of an internal module and then a raw enum; neither is a thing
         a trader can act on. The refusals come from the shared dictionary that
         funnel.js already owns. */
      const plain = c => window.SSFunnel
        ? SSFunnel.plain(c) : String(c).replace(/_/g, ' ').toLowerCase();
      const HEAD = {APPROVED: 'CLEARED TO TRADE',
                    REDUCED:  'CLEARED AT REDUCED SIZE',
                    REJECTED: 'NOT TRADED'};
      const verdict = !d ? '' :
        `<div class="tk-verdict ${d.decision === 'APPROVED' ? 'ok'
           : d.decision === 'REDUCED' ? 'warn' : 'bad'}">` +
        `<b>${HEAD[d.decision] || d.decision}</b>` +
        (d.decision === 'REJECTED'
          ? `<br>${(d.reasons || []).map(plain).join('; ')}` +
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
        '<br><br>The engine has not judged this trade. Arming it writes to ' +
        'your paper book, never the strategy record.';
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
    // ...and so does a scale-out. Carrying "half off at 1R" silently onto the
    // next chart would arm a plan on a market it was never decided for, which
    // is the same defect the risk override is reset for one line above.
    if($('tkScale')){
      $('tkScale').checked = false;
      $('tkScaleRow').hidden = true;
      paintScale(null);
    }
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
    document.querySelectorAll('#tkDir button').forEach(b => {
      const on = b.dataset.d === d;
      b.classList.toggle('on', on);
      /* Long vs Short is the single most consequential state in the ticket and
         a screen reader was told nothing about it: the only signal was a class
         that changes a background colour. Same pattern #tkTabs already uses. */
      b.setAttribute('aria-pressed', String(on));
    });
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
  /* ═══ THE ACTIVE-TRADE BAND ═══
     A live position is a different job from drawing a plan, and until now the
     only things saying so were a heading and the panel's colour. This states
     where the trade stands and offers the two moves an operator actually makes
     on a winner — stop to breakeven, stop to +1R — each shown ONLY when it
     would improve the position. Offering "lock +1R" at +0.3R would put the
     stop the wrong side of price and close the trade the moment it was armed.

     It sets the level and marks the ticket modified; it does NOT commit. The
     commit is still Update trade, deliberately: one button writes to the book,
     and these are ways of filling it in. */
  function renderManage(){
    const el = $('tkManage');
    if(!el) return;
    if(!enginePos){ el.hidden = true; el.innerHTML = ''; el.dataset.h = ''; return; }
    el.hidden = false;
    const long = enginePos.direction === 'LONG';
    const entry = +enginePos.entry;
    // The risk TAKEN, from the stop the trade was entered with — never the
    // current one, or every R on this band would move when the stop does.
    const riskU = Math.abs(entry - +enginePos.sl);
    const px = candles.length ? +candles[candles.length - 1].close : null;
    const nowR = (px == null || !riskU) ? null
      : (long ? px - entry : entry - px) / riskU;

    const be = entry;
    const lock1 = long ? entry + riskU : entry - riskU;
    // "Better" means further into profit than where the stop sits now.
    const better = v => long ? v > levels.sl : v < levels.sl;
    // A stop must not be placed the wrong side of the last close, or it is not
    // a stop, it is a market exit wearing one.
    const safe = v => px == null ? false : (long ? v < px : v > px);

    const acts = [];
    if(better(be) && safe(be))
      acts.push(`<button class="btn" data-mv="${be}">Stop to breakeven</button>`);
    if(better(lock1) && safe(lock1))
      acts.push(`<button class="btn" data-mv="${lock1}">Lock +1R</button>`);

    const rTxt = nowR == null ? 'price unavailable'
      : `${nowR >= 0 ? '+' : ''}${nowR.toFixed(2)}R right now`;
    const rCls = nowR == null ? '' : nowR >= 0 ? 'up' : 'down';
    const html =
      `<div class="tkm-head"><span class="tkm-dot"></span>You are in this trade
         <b>${long ? 'LONG' : 'SHORT'} ${sym}</b> ${tf}
         <span class="tkm-r ${rCls}">${rTxt}</span></div>` +
      (acts.length
        ? `<div class="tkm-acts">${acts.join('')}</div>`
        : `<div class="tkm-none">No stop move improves this yet — it needs to
             be in profit first. Drag a level to set your own.</div>`) +
      `<div class="tkm-foot">Nothing here commits. Set a level, then press
         <b>Update trade</b>.</div>`;
    /* refreshArm() runs on every mousemove of a drag, so rebuilding this
       unconditionally would replace the band's DOM sixty times a second and
       flicker the buttons under the cursor. */
    if(el.dataset.h === html) return;
    el.dataset.h = html;
    el.innerHTML = html;
    el.querySelectorAll('[data-mv]').forEach(b =>
      b.addEventListener('click', () => {
        levels.sl = parseFloat(b.dataset.mv);
        modified = true;
        applyLevels(); recompute();
      }));
  }

  /* Seconds in one bar, for each timeframe this app actually has. Only ever
     used to answer "how old is too old to commit" — never to compute a price
     or a time, where importer.TF_SECONDS stays the one authority.

     THE SPELLINGS ARE THE POINT. These are engine/importer.py's exact keys:
     '15m' is lower case and '1H', '4H', '1D', '1W' are upper. A first draft
     here wrote them all lower case and fell back to 60 seconds for every one
     that missed, so on a 4H chart the gate below fired at a minute of
     staleness instead of four hours — Arm switched itself off, blaming a bar
     length it had not actually used. It was caught by reading the sentence it
     produced: "15 min — longer than one 4H bar" is arithmetic nobody would
     write on purpose.

     An unknown timeframe therefore returns null rather than a default, and
     the caller says so out loud. A silent fallback here is a gate that is
     either uselessly strict or quietly absent, and no way to tell which. */
  const TF_S = {'15m': 900, '1H': 3600, '4H': 14400, '1D': 86400, '1W': 604800};
  const barSeconds = t => Object.prototype.hasOwnProperty.call(TF_S, t) ? TF_S[t] : null;

  /* The refusal sentence when the numbers are too old to size against, or ''
     when they are current. Returns the words rather than a boolean so the one
     caller that disables Arm and the one that explains why cannot disagree
     about which condition fired. */
  function staleForThisTimeframe(){
    const h = (window.SSData && window.SSData.health) ? window.SSData.health() : null;
    if(!h || h.state === 'ok') return '';
    if(h.neverLoaded)
      return 'Nothing has loaded yet, so there is no price to size this ' +
             'against. Arm is off until the cockpit has data.';
    if(h.staleMs == null) return '';
    const barS = barSeconds(tf);
    const mins = Math.round(h.staleMs / 60000);
    const age = mins < 1 ? `${Math.round(h.staleMs / 1000)}s` : `${mins} min`;
    if(barS == null)
      // Audible, not silent. Refusing on an unrecognised timeframe is the safe
      // side of the choice, and naming it is what gets it fixed.
      return `The last good data is ${age} old and this build does not know ` +
             `how long a ${tf} bar is, so it cannot judge whether that is ` +
             `stale. Arm is off.`;
    if(h.staleMs < barS * 1000) return '';
    return h.state === 'offline'
      ? `This device has not reached the PC for ${age} — longer than one ${tf} ` +
        `bar. These prices are old, so Arm is off until it reconnects.`
      : `The last good data is ${age} old — longer than one ${tf} bar. Arm is ` +
        `off until the cockpit refreshes.`;
  }

  function refreshArm(){
    const holding = !!enginePos;
    const btn = $('tkArm');
    // Say which job this ticket is doing, in the heading, where a heading is
    // read. `managing` recolours the whole panel so the two modes are never
    // mistaken at a glance.
    /* ONE ARM PER SIDE PER CHART. Arm stayed live under a "New trade"
       heading while an order was already resting, so pressing it again — or
       simply not noticing the first one — armed the same trade twice. Both
       fill on the same touch and the book carries double the risk the budget
       was told about. engine/manual.py refuses it; this stops the ticket
       offering an action that will be refused. The opposite side stays
       armable: a hedge is a different argument. */
    const dupe = !holding && openPos.find(p =>
      String(p.direction || '').toUpperCase() === String(dir).toUpperCase());
    const dupEl = $('tkDup');
    if(dupEl){
      dupEl.hidden = !dupe;
      // textContent, not innerHTML: chart.js has no esc() and this line is
      // assembled from server strings. Text needs no escaping and cannot grow
      // an injection later.
      if(dupe) dupEl.textContent =
        `You already have a ${dupe.state === 'PENDING' ? 'resting' : 'live'} ` +
        `${dupe.direction} on this chart at ${pf(+dupe.entry)}. Arming again ` +
        `would open a second one on the same side and double the risk. ` +
        `Let it resolve, close it, or arm the other way.`;
    }
    const mode = $('tkMode');
    if(mode) mode.textContent = holding
      ? (modified ? 'Managing trade — unsaved' : 'Managing open trade')
      : dupe ? 'Already armed' : 'New trade';
    $('ticket').classList.toggle('managing', holding);
    renderManage();
    // Holding a position: the only honest commit is changing where it ends,
    // and only once a level has actually moved.
    btn.textContent = holding ? 'Update trade' : 'Arm (paper)';
    /* A half-typed or impossible rung disables the commit in BOTH modes. The
       engine refuses it (manual.validate_partials) and nothing is armed, so
       leaving the button live would spend a click to be told no — and worse,
       a rung that silently failed validation while the rest of the plan armed
       would give the operator a trade they did not ask for. */
    const badScale = $('tkScale') && $('tkScale').checked && !scalePlan;
    // Holding: BOTH a moved level and valid geometry. `armable` alone was not
    // checked, so dragging a short's stop below its entry left Update live on
    // a ticket the maths had already called invalid — the server would refuse
    // it, but offering an impossible action is its own defect.
    /* STALE PRICES MUST NOT SIZE A TRADE.
       ssdata.js deliberately keeps the last good payload on screen when a
       fetch fails, which is right for reading and wrong for committing: this
       ticket sizes a position against a price, and on cellular that price can
       be minutes old while every number still renders with full confidence.
       One bar of the chosen timeframe is the threshold because it is the
       resolution the operator chose to trade at — anything older and the bar
       they are planning against may already have closed somewhere else. */
    const stale = staleForThisTimeframe();
    btn.disabled = badScale ? true
      : stale ? true
      : holding ? (!modified || !armable) : (!armable || !sym || !!dupe);

    /* The blocking reason, ON the control. Only ever set when Arm is actually
       off — a standing explanation beside a live button teaches the operator
       to read neither. */
    const blockEl = $('tkBlock'), whyEl = $('tkBlockWhy'), fixEl = $('tkBlockFix');
    if(blockEl && whyEl && fixEl){
      const m = lastMetrics;
      const over = m && (m.notes || []).includes('NOTIONAL_EXCEEDS_BUYING_POWER');
      const hardBlock = m && m.blocks && m.blocks.length;
      let why = '', fixLabel = '', fixLev = null;
      if(stale){
        /* FIRST, ahead of every other reason. The others are verdicts about
           the plan — margin, geometry, a resting duplicate — and every one of
           them was computed against numbers this branch has just established
           are out of date. Reporting a margin breach from stale prices sends
           the operator to fix the wrong thing. */
        why = stale;
      } else if(!holding && over && equity){
        // The leverage that actually clears it, not merely "raise leverage":
        // at or above the venue cap there IS no fix and saying so is kinder
        // than pointing at a dial that cannot help.
        const need = Math.ceil(m.notional / equity);
        why = `This posts ${usd(m.margin)} of margin against a ${usd(equity)} ` +
              `account. A tighter stop sizes a smaller position.`;
        if(cfg && need <= cfg.max_leverage && (m.leverage || 1) < need){
          fixLev = need;
          fixLabel = `Use ${need}x — posts ${usd(m.notional / need)}`;
        }
      } else if(!holding && hardBlock){
        why = 'The plan cannot be placed as drawn — see the warning above.';
      } else if(!holding && dupe){
        why = 'One order per side per chart.';
      } else if(badScale){
        // The engine refuses this rung (manual.validate_partials), so the
        // ticket must not offer to send it. The reason is already spelled out
        // under the field; here it only has to say what is blocking Arm.
        why = 'That scale-out cannot be placed — see the note under it.';
      }
      blockEl.hidden = !why;
      whyEl.textContent = why;
      fixEl.hidden = !fixLabel;
      fixEl.textContent = fixLabel;
      fixEl.dataset.lev = fixLev == null ? '' : String(fixLev);

      /* ONE notice at a time, in priority order. Three of them could be open
         together — the maths breach, the duplicate-order refusal and the
         reason Arm is off — saying overlapping things and stacking 198px into
         a bar that then squeezed the chart above it to 124px. The operator
         only ever acts on the most binding one; the rest are noise until it
         is cleared. */
      const warnEl = $('tkWarn'), dupWarnEl = $('tkDup');
      if(dupe){
        if(blockEl) blockEl.hidden = true;
        if(warnEl) warnEl.hidden = true;
      } else if(why){
        if(warnEl) warnEl.hidden = true;
      }

      /* The fling notice sits at the BOTTOM of that ladder. It is the only one
         here that is not a refusal, so it must never displace a notice that
         is: a stop the finger skidded is a worse trade, a plan that breaches
         the risk budget is no trade at all. Shown only when nothing more
         binding is already speaking. */
      const flingEl = $('tkFling');
      if(flingEl){
        const speak = flung && !why && !dupe && !holding;
        flingEl.hidden = !speak;
        flingEl.textContent = speak
          ? `That drag made the risk ${flung.factor.toFixed(1)}x ` +
            `${flung.wider ? 'wider' : 'tighter'}. Check the stop before arming.`
          : '';
      }
    }
    btn.title = holding
      ? (modified ? 'take this trade onto your book with these levels'
                  : 'drag the stop or target to change where this trade ends')
      : dupe ? 'one order per side per chart — see the reason above'
      : '';
    $('tkLock').textContent = (cfg && cfg.live_enabled)
      ? ''
      : (cfg ? 'Live orders: ' + cfg.live_locked_reason
             : 'trade config unavailable');
  }

  /* Venue truth reaches the TOGGLE, not just the endpoint. The server refuses
     a spot short at arm time (manual.validate: "cannot sell what it does not
     hold"), but refusing at the last click means the operator planned an
     impossible trade for as long as the ticket was open — the beta pass sat
     in SHORT on a Coinbase chart with the ticket earnestly critiquing the
     stop geometry of a trade the venue cannot take. Dead button, reason beside
     it, same sentence the server would use.

     The reason used to live ONLY in the button's title. A mouse reveals that;
     a finger has no hover, so on a phone the control was dead and silent —
     the operator gets a button that does nothing and no account of why. The
     text now goes on the surface, which is the pattern this ticket already
     follows for its live-orders lock. The title stays for the pointer. */
  function setLock(){
    const sb = document.querySelector('#tkDir [data-d="SHORT"]');
    const why = $('tkDirWhy');
    if(sb){
      const can = !cfg || !cfg.venue || cfg.venue.allow_shorts !== false;
      const reason = can ? ''
        : `${cfg.venue.key} is spot — cannot sell what it does not hold`;
      sb.disabled = !can;
      sb.title = reason;
      if(why){ why.textContent = reason; why.hidden = can; }
      if(!can && dir === 'SHORT') setDir('LONG');
    }
    refreshArm();
  }

  /* ---------- wiring ---------- */
  function wire(){
    $('cSymBtn').addEventListener('click', () =>
      $('cSymPop').hidden ? openPicker() : closePicker());
    $('cSymSearch').addEventListener('input',
      e => renderSymList(e.target.value));
    $('cSymList').addEventListener('click', e => {
      const b = e.target.closest('[data-sym]'); if(!b) return;
      // Leverage means nothing across instruments — 10x on a perp is not a
      // setting that survives a hop to spot. Back to the safe end on every
      // symbol change rather than silently carrying a dial the new venue may
      // not even permit.
      leverage = 1;
      pickSym(b.dataset.sym);
    });
    $('cSymPop').addEventListener('keydown', e => {
      const rows = [...$('cSymList').querySelectorAll('[data-sym]')];
      if(e.key === 'Escape'){ closePicker(); $('cSymBtn').focus(); return; }
      if(e.key === 'ArrowDown' || e.key === 'ArrowUp'){
        e.preventDefault();
        pickIdx = Math.max(0, Math.min(rows.length - 1,
          pickIdx + (e.key === 'ArrowDown' ? 1 : -1)));
        rows.forEach((r, k) => r.classList.toggle('hl', k === pickIdx));
        if(rows[pickIdx]) rows[pickIdx].scrollIntoView({block: 'nearest'});
      }
      if(e.key === 'Enter'){
        e.preventDefault();
        const r = rows[pickIdx >= 0 ? pickIdx : 0];
        if(r){ leverage = 1; pickSym(r.dataset.sym); }
      }
    });
    document.addEventListener('click', e => {
      if(!$('cSymPop').hidden && !e.target.closest('.sym-wrap')) closePicker();
      if(!$('cLayersPop').hidden && !e.target.closest('.layers-wrap')){
        $('cLayersPop').hidden = true;
        $('cLayersBtn').setAttribute('aria-expanded', 'false');
      }
    });
    $('cTfs').addEventListener('click', e => {
      const b = e.target.closest('button'); if(!b) return;
      tf = b.dataset.tf;
      document.querySelectorAll('#cTfs button').forEach(x => {
        x.classList.toggle('on', x === b);
        x.setAttribute('aria-pressed', String(x === b));
      });
      load();
    });
    $('cLayersBtn').addEventListener('click', () => {
      const pop = $('cLayersPop');
      pop.hidden = !pop.hidden;
      $('cLayersBtn').setAttribute('aria-expanded', String(!pop.hidden));
    });
    $('cLayersPop').addEventListener('click', async e => {
      const b = e.target.closest('button'); if(!b) return;
      const key = b.dataset.o;
      overlays[key] = !overlays[key];
      b.classList.toggle('on', overlays[key]);
      paintLayersBtn();
      // Lazy layers pay for themselves on first use only; the await is why
      // this handler is async, and drawOverlays runs after either way so
      // switching a layer OFF is instant.
      if(overlays[key] && LAZY[key]) await ensureLayer(key);
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
    /* Ticket panes. Grouping only helps if the group you are in is obvious, so
       the tab carries the state and the pane merely follows it. */
    $('tkTabs').addEventListener('click', e => {
      const b = e.target.closest('button[data-p]');
      if(!b) return;
      $('tkTabs').querySelectorAll('button').forEach(x => {
        x.classList.toggle('on', x === b);
        // the pressed state is the only thing a screen reader can read here
        x.setAttribute('aria-pressed', String(x === b));
      });
      $('ticket').querySelectorAll('.tk-pane').forEach(p =>
        p.classList.toggle('on', p.dataset.p === b.dataset.p));
      // A new pane starts at its top. Carrying the previous pane's offset
      // opened the next one mid-sentence, clipped at both ends.
      $('ticket').scrollTop = 0;
    });

    /* copilot binding lives in copilot.js now — the dock is an app feature
       with a chart mode, not a chart feature. This surface just publishes
       what it is looking at. */
    /* The BUTTON KEEPS ITS NAME. It used to become its own status line —
       "ANALYZING…" then "ALREADY CURRENT" — so the control the operator was
       reaching for changed identity underneath the cursor, and the outcome
       vanished four seconds later with no record that anything happened.
       Progress goes to the button's busy state, the outcome goes to a toast
       that says WHAT was recomputed. */
    $('cAnalyse').addEventListener('click', async () => {
      const b = $('cAnalyse');
      if(!sym || b.disabled) return;
      const t = window.SSToast || (() => {});
      b.disabled = true; b.setAttribute('aria-busy', 'true');
      try{
        const r = await fetch('/api/analyse?symbol=' + encodeURIComponent(sym),
                              {method: 'POST'});
        const d = await r.json().catch(() => ({}));
        if(r.status === 404){ t(`No price history stored for ${sym} yet.`, 'warn'); return; }
        if(!r.ok && r.status !== 207){
          t(`Could not analyse ${sym} — ${d.detail || r.status}`, 'bad'); return; }
        // The facts just changed underneath the cache, so a plain reload would
        // redraw the pre-analysis answer for up to 25 seconds.
        for(const p of ['/api/facts', '/api/candles', '/api/draft'])
          window.SSData.invalidate(p);
        await load();
        /* The button reports whether the CHART changed, not how many rows the
           analysis wrote. `+412 facts` is a true number about the fact store
           and an unanswerable one about the trade: nobody can tell whether 412
           is a lot, or which of them they are now looking at. */
        /* Names WHAT was recomputed rather than how many rows were written.
           "Already current" now carries the time it was checked, so a no-op
           is distinguishable from a click that never landed. */
        const nf = d.new_facts || {};
        const changed = Object.entries(nf).filter(([, v]) => v > 0)
          .map(([k]) => k).sort();
        const at = new Date().toISOString().slice(11, 16) + 'Z';
        if(d.errors && d.errors.length)
          t(`${sym}: partly updated — ${d.errors.length} step(s) failed.`, 'warn');
        else if(!changed.length)
          t(`${sym} was already current at ${at} — nothing had changed since ` +
            `the last pass.`);
        else
          t(`${sym} updated: ${changed.join(', ')} recomputed.`, 'good');
      }catch(err){
        t(`Could not reach the engine to analyse ${sym}.`, 'bad');
      }finally{
        b.disabled = false; b.removeAttribute('aria-busy');
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

      /* CONFIRM BEFORE COMMITTING. The ticket's numbers drift with live price
         between reading them and pressing this, so the dialog restates what is
         actually about to be recorded — side, symbol, all three levels, the
         dollars at risk, and that it is PAPER. The last word before an
         irreversible-feeling action should be the action's own terms, not the
         label on a button. */
      if(!enginePos){
        /* Say where the entry sits RELATIVE TO THE MARKET, not just its
           digits. "entry 63,847.12" reads as plausible on any chart; "15.2%
           below market" is a plan, and "94% below market" is another symbol's
           levels about to be armed under this one's name. The Your-trades
           panel words resting orders exactly this way, so the promise and the
           receipt match. */
        const lastClose = candles.length ? candles[candles.length - 1].close : null;
        const away = lastClose ? (armedEntry - lastClose) / lastClose * 100 : null;
        /* The stop's DISTANCE, not only its digits. The restatement already
           says how far entry sits from market, and said nothing at all about
           how far the stop sits from entry — which is the number a mis-drag
           actually corrupts, and the one that decides the size. "stop
           0.20063" reads as plausible at any distance; "1.8% away" is a plan
           and "14% away" is a slip. */
        const stopAway = armedEntry ? Math.abs(armedEntry - levels.sl) / armedEntry * 100 : null;
        /* `key: value`, so the dialog lays them out as a table and the deciding
           figure can be lifted out of the list entirely. Same strings, one
           separator changed. */
        const lines = [
          `entry: ${pf(armedEntry)}${away == null ? ''
            : Math.abs(away) < 0.05 ? ' · at market'
            : ` · ${Math.abs(away).toFixed(1)}% ${away > 0 ? 'above' : 'below'} market`}`,
          `stop: ${pf(levels.sl)}${stopAway == null ? ''
            : ` · ${stopAway.toFixed(2)}% from entry`}`,
          `target: ${pf(levels.tp)}`,
        ];
        // The rung belongs in the restatement for the same reason the levels
        // do: it changes what the trade settles for, and the last word before
        // committing should be the action's own terms.
        if(scalePlan)
          lines.push(`scale-out: ${Math.round(scalePlan.fraction * 100)}% off at ` +
                     `${pf(scalePlan.price)} (+${scalePlan.atR}R)`);
        // A flung level is restated where it cannot be scrolled past. The
        // ticket already says it, but the ticket is what the operator has
        // stopped reading by the time they reach for Arm.
        /* The flung-level warning was pushed LAST so it could not be scrolled
           past. In a native dialog that was the only lever available, and on a
           platform that truncates the body it failed anyway. It is now a
           bordered block above the buttons: it cannot be cut without cutting
           the buttons with it. */
        const flungWarn = flung
          ? `Your last drag made the risk ${flung.factor.toFixed(1)}x ` +
            `${flung.wider ? 'wider' : 'tighter'}.`
          : '';
        if(!await SSConfirm({
          title: 'Arm this trade?',
          lead: `${String(armedDir).toUpperCase()} ${sym} ${tf}`,
          // the figure a mis-drag corrupts, at the scale the decision deserves
          emphasis: `risking ${usd(riskUsd)}${cfg && cfg.max_leverage > 1 && leverage > 1
            ? ` at ${leverage}x` : ''}`,
          rows: lines,
          warn: flungWarn,
          note: 'PAPER — this writes to your paper book. No real order is sent.',
          confirmLabel: 'Arm (paper)'
        })) return;
      }
      btn.disabled = true;
      out.textContent = 'arming…';
      /* ONE MOMENT, GENERATED ONCE. manual.create_intent builds its intent_id
         as `symbol|tf|MANUAL|created_at`, and the endpoint already accepts a
         created_at from the caller — it just was not being sent, so the
         server stamped its own on every attempt and two taps became two
         different intents. The engine caught that with _same_side_open, which
         is why no duplicate was ever written, but "refused" is a poor answer
         to a tap that actually worked.

         Stamped here, before the request, and reused if it is ever retried:
         the same created_at yields the same intent_id and an identical
         payload, which the content-hashed store collapses to the one row it
         already holds. The server clamps it against its own clock, so a phone
         with a wrong time cannot stamp a false moment onto the record. */
      const armAt = Math.floor(Date.now() / 1000);
      try{
        const r = await fetch('/api/manual/arm', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            symbol: sym, tf: tf, direction: dir,
            created_at: armAt,
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
            // The rung as a PRICE, because that is what the resolver tests
            // against a bar and what the fact records. The R the operator typed
            // was only ever the way in — sending it would make the engine
            // re-derive a price from a risk figure it would have to trust the
            // browser for.
            partials: scalePlan
              ? [{fraction: scalePlan.fraction, price: scalePlan.price}] : null,
            risk_usd: isFinite(riskUsd) && riskUsd > 0 ? riskUsd : null})});
        const d = await r.json().catch(() => ({}));
        if(!r.ok){
          /* A REFUSAL THAT IS REALLY A RECEIPT. The engine rejects a second
             unresolved intent on the same market and side — correctly — but
             on a phone the commonest way to meet that rule is tapping Arm
             again because the first tap looked like it did nothing on a slow
             connection. Reporting the operator's own successful trade back to
             them as an error is how someone talks themselves into a third
             tap. Say what is true: it landed. */
          const detail = d.detail || ('HTTP ' + r.status);
          out.textContent = /already have an unresolved/i.test(detail)
            ? `your earlier tap landed — this is the trade you already have. ${detail}`
            : 'refused — ' + detail;
          return;
        }
        const n = d.book ? d.book.n : 0;
        const openN = d.book ? (d.book.open_intents || []).length : 0;
        // Put the position on screen NOW, not at the next refresh — arming
        // and then seeing nothing appear is the report this closes. The
        // receipt is written AFTER the reload because a clean reload runs
        // restore(), which clears the receipt line.
        window.SSData.invalidate('/api/manual/open');
        // ...and the whole-book view Command reads, or the order you just armed
        // would be missing from "Your trades" until the cache aged out.
        window.SSData.invalidate('/api/manual/live');
        await load({keepTicket: true});
        out.textContent =
          `armed on paper · ${armedDir} ${sym} ${tf} · entry ${pf(armedEntry)} · ` +
          `your book: ${n} settled, ${openN} open`;
      }catch(err){
        /* THIS USED TO CLAIM SOMETHING IT CANNOT KNOW. fetch() rejects both
           when the request never left and when it arrived, was recorded, and
           the REPLY was lost — and those are indistinguishable from here.
           "nothing was armed" is therefore a coin-flip stated as fact, on the
           one screen where being wrong means the operator arms a second
           position believing they have none. On loopback the ambiguous case
           essentially never happens; on cellular it is ordinary.

           So: do not assert. Go and look. /api/manual/book is a pure read —
           unlike /api/manual/open and /api/manual/live, which call
           manual.run() and record fills — so asking it costs the book
           nothing. */
        out.textContent = 'the reply never arrived — checking your book…';
        try{
          const book = await window.SSData.get('/api/manual/book', 0);
          const open = (book && (book.open_intents || book.open || [])) || [];
          const mine = open.filter(o =>
            o && String(o.symbol) === sym && String(o.tf) === tf &&
            String(o.direction).toUpperCase() === String(armedDir).toUpperCase());
          out.textContent = mine.length
            ? `it landed after all — ${armedDir} ${sym} ${tf} is on your book. ` +
              `Nothing was armed twice.`
            : 'the reply never arrived, and your book shows no such trade — ' +
              'nothing was armed. Safe to try again.';
        }catch(_){
          // Still cannot reach it. Say exactly that, and no more.
          out.textContent =
            'the reply never arrived and your book is unreachable, so whether ' +
            'this armed is UNKNOWN. Check Your trades before arming again.';
        }
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
        // A number typed on purpose answers the fling warning — the operator
        // has now stated the level deliberately, in digits.
        flung = null;
        applyLevels(); recompute(); refreshArm();
      });
    /* THE NUDGE EDITOR. Deliberately a first-class way to set a level, not a
       fallback for when dragging fails — dragging is imprecise on a phone even
       when it works perfectly, because the price axis is a few hundred pixels
       tall and a fingertip covers several ticks of it.

       Two units, because the operator thinks in both: a TICK is the smallest
       move the price format can express, and 0.1R is a tenth of the distance
       from entry to stop, which is the unit the risk is denominated in. R is
       measured from the CURRENT geometry each press, so stepping the stop
       makes later 0.1R presses smaller — that is correct, it is the same
       shrinking distance the position size is computed from.

       Delegated, so the three groups share one handler and a group added later
       works without wiring. */
    document.addEventListener('click', e => {
      const b = e.target.closest && e.target.closest('.tk-nudge button');
      if(!b) return;
      const key = b.parentElement.dataset.k;
      if(levels[key] == null) return;
      const step = b.dataset.step;
      const tick = Math.pow(10, -digits(levels[key]));
      const r = riskDistance();
      // No stop yet means no R to step by; the tick still works, and offering
      // a button that silently does nothing is worse than one that is off.
      const size = step.endsWith('r') ? (r ? r * 0.1 : 0) : tick;
      if(!size) return;
      const next = levels[key] + (step[0] === '-' ? -size : size);
      if(!isFinite(next) || next <= 0) return;
      // Land on the tick grid, or repeated 0.1R presses drift the level into
      // precision the price format cannot even display.
      levels[key] = Math.round(next / tick) * tick;
      modified = true;
      // A deliberate step answers the fling warning for the same reason a
      // typed number does: the operator has now stated the level on purpose.
      flung = null;
      applyLevels(); recompute(); refreshArm();
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
    $('tkScale').addEventListener('change', e => {
      $('tkScaleRow').hidden = !e.target.checked;
      modified = true;
      recompute();
    });
    // `input`, not `change`: the rung's price is the answer to what is being
    // typed, and a line that only moved on blur would leave the chart showing
    // a level the form no longer describes.
    for(const id of ['tkScalePct', 'tkScaleR'])
      $(id).addEventListener('input', () => { modified = true; recompute(); });
    $('tkReset').addEventListener('click', restore);

    /* The one-click fix. It moves the dial the block named and nothing else,
       so the operator can see the same numbers recompute rather than being
       handed a different trade. */
    $('tkBlockFix').addEventListener('click', e => {
      const lev = parseInt(e.currentTarget.dataset.lev, 10);
      if(!isFinite(lev)) return;
      leverage = lev;
      const slider = $('tkLev');
      if(slider) slider.value = String(lev);
      recompute();
    });
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
    if(!sym) sym = allSymbols.length ? allSymbols[0].symbol : null;
    if(sym){ paintSymBtn(); await load(); }
  }

  /* One searchable list replaces the <select> + scope toggle. The OS-native
     dropdown was the one element on this surface no stylesheet could reach —
     a white panel in a dark app — and the scope button existed only because a
     flat unsearchable list buried the 19 scanned symbols under 47 leftovers.
     Grouping plus search solves what the scope toggle solved, one control
     cheaper: scanned first, shadow next, unscanned last, and typing filters
     all of them. */
  const PICK_GROUPS = [
    ['ADMITTED', 'scanned'],
    ['SHADOW', 'shadow — never sized'],
    ['UNTRACKED', 'not scanned'],
  ];
  let pickIdx = -1;                    // keyboard highlight, -1 = none

  function venueName(v){
    const house = (v.key || '').split('-')[0];
    return `${house.charAt(0).toUpperCase()}${house.slice(1)} ${v.kind}`;
  }

  function paintSymBtn(){
    const m = symMeta[sym];
    $('cSymTok').textContent = sym || '—';
    const v = m && m.venue;
    $('cSymVenue').textContent = !v ? '' :
      `${venueName(v)}${v.max_leverage > 1 ? ' · ' + v.max_leverage + 'x' : ''}${
        v.allow_shorts ? '' : ' · long only'}`;
    $('cSymBtn').classList.toggle('shadow', !!m && m.state !== 'ADMITTED');
    $('cSymBtn').title = !m ? 'choose a symbol' : (m.state === 'ADMITTED'
      ? 'the engine scans this symbol'
      : `state ${m.state} — the engine is not scanning this, so it will have no setups`);
  }

  function renderSymList(filter){
    const q = (filter || '').trim().toUpperCase();
    const hit = s => !q || s.symbol.toUpperCase().includes(q);
    let html = '', n = 0;
    for(const [state, label] of PICK_GROUPS){
      const rows = allSymbols.filter(s => s.state === state && hit(s));
      if(!rows.length) continue;
      html += `<div class="sym-group">${label} (${rows.length})</div>` +
        rows.map(s => { n++; return `<button class="sym-row${s.symbol === sym ? ' on' : ''}"
          role="option" data-sym="${s.symbol}">
          <b>${s.symbol}</b><i>${s.venue ? venueName(s.venue) : ''}</i></button>`; }).join('');
    }
    const known = new Set(PICK_GROUPS.map(g => g[0]));
    const rest = allSymbols.filter(s => !known.has(s.state) && hit(s));
    if(rest.length)
      html += `<div class="sym-group">other (${rest.length})</div>` +
        rest.map(s => `<button class="sym-row" role="option" data-sym="${s.symbol}">
          <b>${s.symbol}</b><i>${s.venue ? venueName(s.venue) : ''}</i></button>`).join('');
    $('cSymList').innerHTML = html ||
      '<div class="sym-group">nothing matches</div>';
    pickIdx = -1;
  }

  function openPicker(){
    $('cSymPop').hidden = false;
    $('cSymBtn').setAttribute('aria-expanded', 'true');
    const inp = $('cSymSearch');
    inp.value = '';
    renderSymList('');
    inp.focus();
  }
  function closePicker(){
    $('cSymPop').hidden = true;
    $('cSymBtn').setAttribute('aria-expanded', 'false');
  }
  async function pickSym(next){
    closePicker();
    if(!next || next === sym) return;
    sym = next;
    paintSymBtn();
    await load();
  }

  /* Venue facts now live ON the symbol button — the chip repeated what the
     picker already had to say. `venues.py` still decides everything. */


  /* open(symbol, timeframe) — the deck's "Open chart" entry point */
  async function open(s, t){
    sym = s; if(t) tf = t;
    boot();
    document.querySelectorAll('#cTfs button').forEach(b =>
      b.classList.toggle('on', b.dataset.tf === tf));
    if(!allSymbols.length) await populate();          // handles load itself
    else{ paintSymBtn(); await load(); }
  }

  wire();
  return {open, onShow, onHide,
    /* Introspection, for the suites and for answering "why can I not see that
       swing on my phone" without guessing. A cap nobody can observe is
       indistinguishable from a bug. */
    _markerDrop: () => lastMarkerDrop};
})();
