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
  // Set by Setup Radar.  The card, overlays and ticket must describe the same
  // server-owned record even when a newer setup for the symbol arrives.
  let preferredSetupId = null;
  let preferredInspectOnly = false;
  let preferredSetupMissing = false;
  /* `base` is whatever this chart started from, and it is now one of exactly
     three things: an ACTIVE TRADE, a plan the ENGINE is still waiting on, or
     the operator's own. Null when there is none of the three — an empty ticket
     is the honest answer and the chart says so in words.

     It used to have a fourth: `last close ± average 14-bar range`, always
     LONG, drawn on any chart with nothing else to show. Its own comment called
     it "not a signal, not analysis, and not the engine's opinion", and it was
     still three horizontal price lines. The operator's rule, 8 Aug 2026: the
     only things that display are a plan the bot generated, a plan of mine, and
     an active trade. A ruler is none of them.

     Whatever `base` holds is restorable, so an operator who drags into a
     corner is never stranded. */
  let base = null;                            // {entry,tp,sl,dir,kind}
  let symMeta = {};                           // symbol -> /api/overview row (venue, state)
  let allSymbols = [];                        // the full overview list, cached for the picker
  // scope state died with the scope toggle: the picker lists everything, grouped
  let draftPlan = null;                       // engine/draft.py bracket, or null
  let openPos = [];                           // open manual trades on this chart
  /* WHICH MARKET that book is for, echoed by the endpoint rather than assumed
     from the request. The second-opinion line refuses to compare an engine
     plan against a position from another symbol or another timeframe, and a
     guard that trusts the variable it was fetched with is not a guard. */
  let posKey = null;                          // 'SYM|TF' openPos belongs to
  let enginePos = null;                       // the ENGINE's open trade here, if any
  let posLines = [];                          // their price lines, redrawn per load
  let tradeLines = [];                        // a CLOSED trade, opened from Results
  let pendingTrade = null;                    // ...the one waiting to be drawn
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
  /* Whether the ticket bracket is switched off right now, and whose switch it
     answers to. A hidden line must take its DRAG HANDLE with it: a grab tag
     naming a price with no line under it is worse than the clutter it was
     hidden to fix. applyLevels owns both. */
  let lvlHidden = false, bracketMine = true;
  /* TWO bracket tallies, because one number cannot answer both questions.
     `bracketN` is the bracket after de-duplication against the operator's own
     order — what its switch draws while the gold lines are up. `bracketRaw` is
     before it — what it draws once those gold lines are gone and the shared
     prices are its to show. Neither depends on the bracket's OWN switch, which
     is the property that makes the Layers tally honest while a layer is off. */
  let bracketN = 0, bracketRaw = 0;
  let posN = 0;                  // level lines the operator's own position draws
  let lastCounts = null;         // the last per-layer tally drawOverlays made
  let drawnKind = null;          // 'engine' | 'draft' — see applyLevels()
  let refreshTimer = null, refreshing = false;   // see startAutoRefresh()
  let loadedAt = null, freshTimer = null;        // see showFreshness()
  let loadSeq = 0;                            // guards out-of-order responses
  /* THE FLOOR UNDER THE RACE GUARD. A load that bails because a newer one
     started is normal and silent — but it leaves "Loading X · Y…" on screen,
     and only the winner takes that down. If no winner arrives, the pane holds
     a loading message that will never resolve, which is indistinguishable
     from a hung request and was exactly the "no candles" report.

     So every bail schedules a check. If the message is still up a beat later
     and nothing has painted since, the chart says it gave up rather than
     pretending it is still trying. One timer, replaced each time, because a
     burst of superseded loads is one stall, not five. */
  let stallTimer = 0;
  function noteStalledLoad(){
    clearTimeout(stallTimer);
    const seqAtBail = loadSeq;
    stallTimer = setTimeout(() => {
      const box = $('chartEmpty');
      if(!box || box.style.display === 'none') return;   // something painted
      if(loadSeq !== seqAtBail) return;                  // a newer load is running
      if(!/^Loading /.test(box.textContent || '')) return;
      clearChart('Could not finish loading ' + sym + ' · ' + tf,
                 'the request was superseded and nothing replaced it — ' +
                 'pick the timeframe again to retry');
    }, 4000);
  }
  // Which market the screen currently DESCRIBES — set only when a load paints,
  // nulled whenever the screen is cleared. load() compares against it to tell
  // a switch (clear first, everything on screen is the old market) from a
  // refresh (repaint in place, never flash).
  let painted = null;                         // 'SYM|TF' of the painted market
  /* The market whose prices last established the right-axis range. Keep this
     separate from `painted`: prepare() deliberately clears painted when the
     selected setup changes on the SAME chart, but that must not throw away a
     scale the operator just adjusted. A real symbol/timeframe switch does
     need auto-scale restored, otherwise LINK can inherit BTC's 60k range and
     render far below the visible canvas. */
  let priceScaleMarket = null;                // 'SYM|TF' of the price-axis range

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
  /* LEVELS ARE A LAYER TOO, and they were the only thing on this chart with
     no switch. A filled manual trade puts six price lines on screen at once —
     three gold ones that are the operator's, three the ticket's — and the
     operator's report was simply that they could not read it.

     TWO keys, not one. A single "levels" toggle would hide both sets together
     and take away the one view that answers the question being asked: the
     engine's idea, alone, with yours out of the way. Both default ON, because
     the ask was a volume knob and not a mute — the engine may well have the
     better entry, and it cannot say so from behind a switch nobody found. */
  const overlays = {yours: true, engine: true,
                    swings: false, structure: false, zones: false,
                    liquidity: false, cycle: false,
                    gaps: false, shelf: false, ranges: false, signals: false};
  /* ...and they are drawn from the book and the ticket rather than from the
     fact cache, so drawOverlays() cannot redraw them. Toggling one of these
     goes through drawPosition()/applyLevels() instead — see the Layers
     handler. */
  const LEVEL_LAYERS = {yours: 1, engine: 1};

  /* ═══════════ FOUR PRESETS, AND THE TWO THEY MAY NEVER TOUCH ═══════════

     Eleven switches is not a control, it is homework: to read this chart you
     had to already know which nine of them to move, and the operator's
     standing complaint about this surface is clutter. These are the four ways
     the chart is actually read, one press each.

     `yours` and `engine` ARE NOT IN ANY PRESET, and nothing here writes them.
     Between them they own the operator's entry, stop and target: the gold
     lines of a filled trade (drawPosition reads `overlays.yours`) and the
     ticket bracket about to be armed (applyLevels reads whichever of the two
     `bracketMine` names). Hiding those takes the drag handles with them
     (placeHandles) while the ticket keeps showing the prices and Arm stays
     live — a chart with no entry, stop or target under a ticket that says
     there is one. That is not a quieter chart, it is a lie about what is
     planned. The two switches stay under the operator's own hand, default ON,
     exactly as they were.

     The liquidation price is not on this list because it is not a layer at
     all: it is a ticket line (`#tkLiq`, written by syncLeverage from the
     venue's own maths), so nothing here can reach it either.

     Clean is the default for the same reason the four lazy layers ship off —
     a first chart should be readable before it is informative. */
  const PRESET_KEYS = ['swings', 'structure', 'zones', 'liquidity', 'cycle',
                       'gaps', 'shelf', 'ranges', 'signals'];
  const PRESETS = {
    clean:      [],
    trade:      ['zones'],
    structure:  ['zones', 'swings', 'structure', 'liquidity'],
    everything: PRESET_KEYS,
  };
  const PRESET_LABEL = {clean: 'Clean', trade: 'Trade',
                        structure: 'Structure', everything: 'Everything'};
  const PRESET_FALLBACK = 'clean';
  /* localStorage, not sessionStorage: this is a standing preference about how
     the operator reads a chart, not a per-session position like the workspace
     view tabs. Same shape as markets.js's `ss.market-workspace.v1`. */
  const PRESET_STORE = 'ss.chart-preset.v1';
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
    /* CANVAS COLOURS ARE LITERALS, AND HAVE TO BE.
       Lightweight Charts parses colour strings itself and its parser predates
       oklch(), which is the form every surface token in ss.css is written in —
       hand it a resolved `var(--fg-4)` and the option is dropped without a
       word. So these are hex and rgba, chosen to sit in the stylesheet's
       family rather than read from it.

       WHAT CHANGED. The candles were `#4ade80` and `#f87171` at 75% — full
       signal colours, on the largest object on screen, in an app whose design
       rule is that saturated colour stays under ~10% of any screen. Every
       level line here is a signal colour too, so the three prices the decision
       is made on were competing with two hundred candles wearing the same
       paint. These are the same hues at roughly a third of the chroma:
       direction still reads at a glance, and nothing on the chart is now
       louder than the plan drawn over it. */
    chart = LightweightCharts.createChart($('chartBox'), {
      layout: {background: {color: 'transparent'}, textColor: '#7d8c83',
               fontFamily: "'JetBrains Mono',ui-monospace,monospace", fontSize: 10},
      /* NEARLY INVISIBLE, and vertical fainter than horizontal. A grid is a
         reading aid for PRICE, which is what the horizontal lines carry; the
         vertical ones only repeat what the time axis already says, and at .035
         they were the noisiest thing behind the candles. */
      grid: {vertLines: {color: 'rgba(255,255,255,.012)'},
             horzLines: {color: 'rgba(255,255,255,.022)'}},
      /* The crosshair's two axis tags are the only labels on this chart the
         operator did not ask for, so they are the quietest: a near-black
         tablet instead of the library default `#131722`, which is a blue-black
         belonging to somebody else's app and not to an olive one. */
      crosshair: {mode: 0,
                  vertLine: {color: 'rgba(255,255,255,.16)', style: 3,
                             labelBackgroundColor: 'rgba(18,22,18,.94)'},
                  horzLine: {color: 'rgba(255,255,255,.16)', style: 3,
                             labelBackgroundColor: 'rgba(18,22,18,.94)'}},
      rightPriceScale: {borderColor: 'rgba(255,255,255,.05)'},
      timeScale: {borderColor: 'rgba(255,255,255,.05)',
                  timeVisible: true, secondsVisible: false},
    });
    series = chart.addCandlestickSeries({
      upColor: 'rgba(126,180,146,.45)', downColor: 'rgba(196,124,124,.45)',
      borderUpColor: '#7eb492', borderDownColor: '#c47c7c',
      wickUpColor: 'rgba(126,180,146,.65)', wickDownColor: 'rgba(196,124,124,.65)',
      /* The dashed last-price line, and the tag the right axis draws for it.
         Left to itself the library paints both in the last bar's own colour,
         so the brightest pill on the axis changed hue every close; a fixed
         neutral makes it a reading of where price IS rather than a third
         opinion about direction. */
      priceLineColor: 'rgba(255,255,255,.22)', priceLineStyle: 2,
      priceLineWidth: 1});

    /* VOLUME, on a chart whose engine computes 231,946 volume facts and whose
       operator could not see a single bar of it. Its own price scale, pinned
       to the bottom fifth: an overlay scale means the candles and the
       histogram share a range and the price series collapses to a hairline.
       No axis labels — the QUESTION volume answers is "more or less than the
       bars around it", which is shape, not magnitude. */
    volSeries = chart.addHistogramSeries({
      priceScaleId: 'vol', priceFormat: {type: 'volume'},
      color: 'rgba(148,163,184,.28)'});
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
    // A hidden handle is display:none and cannot be pressed, but the guard is
    // stated rather than inherited: nothing may drag a level that is not drawn.
    if(lvlHidden || levels[key] == null) return;
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
      /* Throws if the capture is already gone — the pointer left the window,
         or the browser released it when the element was re-rendered under the
         drag. Both mean the job is done. Nothing is owed here; the empty block
         is a decision, not an oversight. */
      try{ el.releasePointerCapture(ev.pointerId); }catch(_){ /* already released */ }
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
      /* A LAYER SWITCHED OFF TAKES ITS HANDLES WITH IT. Hiding the line and
         leaving the grab tag would put a draggable pill, naming a price, over
         empty chart — which is the six-lines complaint with the lines removed
         and the confusion kept. Treated exactly like "no such level". */
      const el = handles[k], p = lvlHidden ? null : levels[k];
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
     in words and then dressed it anyway. That ruler is gone entirely now — see
     `base` — but the argument it produced is the one this whole function runs
     on, so it stays recorded here.

     Draft covers anything that is not EXACTLY what the engine said — a
     structure draft and dragged levels both. Solid and bright therefore
     carries one meaning: this is the engine's plan, untouched. */
  function applyLevels(){
    /* Three visual registers, because they mean three different things:
       LIVE (gold, solid) is money at stake right now; ENGINE (bright) is a
       plan the machine is still waiting on; DIM AND DOTTED is anything that
       is not a trade about to be taken. */
    const live = !!enginePos;
    const draft = !live && (!base || base.kind !== 'engine' || modified);
    /* WHOSE bracket is this? Every level on this chart already prints its
       owner — YOURS and PLAN are the operator's, ENGINE is the machine's — so
       the two Layers switches ask the same question the labels already answer,
       and key off the same fact rather than a second rule. A live engine
       position the operator has DRAGGED has passed into their custody, which
       is why `modified` decides it on that branch — and it is also why LIVE,
       the one label that names neither party, goes to `Engine plan` until it
       is dragged and to `Your levels` after. */
    bracketMine = live ? modified : draft;
    const shown = bracketMine ? overlays.yours : overlays.engine;
    lvlHidden = !shown;
    /* AN ENGINE SETUP IS NOT AUTOMATICALLY A LIVE PLAN. Two ways it stops
       being one, both of them facts the chart already holds and neither of
       them visible in the setup itself (see setupFate):

         · the risk authority REFUSED it — the ticket said NOT TRADED while
           three bright ENGINE lines invited the operator to take it anyway;
         · its entry has already FILLED, or its order MISSED and expired —
           setups.py has no terminal state for "acted on", so a setup the
           engine entered days ago stays VALIDATED until its zone breaks.

       The second one no longer reaches this function by default: `pickSetup`
       drops spent setups from the candidates entirely, because a finished
       trade is not a plan and the chart draws only plans and positions. It
       still reaches here when Setup Radar links to that exact setup_id, which
       is a review of a past trade and is the one time these labels are wanted.

       All three take the DIM DOTTED register the draft already uses,
       deliberately: it means "not a trade about to be taken", which is exactly
       what these are. A fourth style would be a fourth thing to learn for a
       distinction the operator does not need to make.

       WHOSE stays with the ENGINE regardless — `bracketMine` is untouched
       above, so a refused or spent engine setup still belongs to the `Engine
       plan` switch and does not migrate into `Your levels`.

       The label carries WHICH SORT, in the slot LIVE already uses for a state
       rather than a party. The vocabulary on this chart is now PLAN (yours,
       unarmed), ENGINE (its plan, still waiting), NOT TRADED / FILLED /
       MISSED (its plan, over), YOURS (armed and resting), LIVE (filled). */
    const fate = !live && !draft && base ? base.fate : null;
    const spent = !!fate && fate !== 'live';
    /* Written out, not assembled. These strings are what the operator reads,
       and a label built from fragments cannot be found by grepping for the
       phrase that is on the screen — which is how the suites pin them and how
       the next session will look for them. Every key here is reachable: this
       map is only read on the `draft || spent` branch below. */
    const dim = {
      draft:   {entry: 'PLAN · ENTRY',       tp: 'PLAN · TP',       sl: 'PLAN · SL'},
      refused: {entry: 'NOT TRADED · ENTRY', tp: 'NOT TRADED · TP', sl: 'NOT TRADED · SL'},
      filled:  {entry: 'FILLED · ENTRY',     tp: 'FILLED · TP',     sl: 'FILLED · SL'},
      missed:  {entry: 'MISSED · ENTRY',     tp: 'MISSED · TP',     sl: 'MISSED · SL'},
    }[draft ? 'draft' : fate];
    const spec = live ? {
      entry: {c: '#fbbf24', s: 0, t: 'LIVE · IN AT'},
      tp:    {c: '#fbbf24', s: 2, t: modified ? 'YOUR TARGET' : 'LIVE · TARGET'},
      sl:    {c: '#fbbf24', s: 2, t: modified ? 'YOUR STOP' : 'LIVE · STOP'},
    } : draft || spent ? {
      /* "DRAFT" was jargon and an operator asked what it meant, fairly: it is
         the app's word, not the market's. Every label reads STATE · WHICH, so
         the states on this chart answer "what am I looking at" without a
         legend. */
      entry: {c: 'rgba(34,211,238,.40)',  s: 1, t: dim.entry},
      tp:    {c: 'rgba(74,222,128,.40)',  s: 1, t: dim.tp},
      sl:    {c: 'rgba(248,113,113,.40)', s: 1, t: dim.sl},
    } : {
      entry: {c: '#22d3ee', s: 0, t: 'ENGINE · ENTRY'},
      tp:    {c: '#4ade80', s: 2, t: 'ENGINE · TP'},
      sl:    {c: '#f87171', s: 2, t: 'ENGINE · SL'},
    };
    // Price lines only take `price` on update, so a kind change has to redraw
    // them — otherwise dragging an engine plan would keep its solid styling and
    // the distinction would silently stop working after the first edit.
    const want = live ? ('live' + (modified ? '-edited' : ''))
               : draft ? 'draft' : spent ? 'spent-' + fate : 'engine';
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
    /* The same prices again, but WITHOUT the `Your levels` short-circuit —
       drawing and counting need different answers. Deduping the drawing
       against lines that are not on screen would blank the chart (see
       positionPrices), and counting against a list that empties when a switch
       moves would make the tally jump by three the moment it was hidden. */
    const held = bookPrices();
    const same = (a, b) => Math.abs(a - b) <= Math.abs(a) * 1e-9;

    bracketN = 0; bracketRaw = 0;
    for(const k of ['entry', 'tp', 'sl']){
      const p = levels[k];
      if(p == null){
        if(priceLines[k]){ series.removePriceLine(priceLines[k]); delete priceLines[k]; }
        continue;
      }
      /* Counted BEFORE either guard below, and against `held` rather than
         `taken`, so both tallies answer "what would this switch draw" and
         neither changes when the switch itself moves. */
      bracketRaw++;
      if(!held.some(v => same(v, p))) bracketN++;
      if(taken.some(v => same(v, p))){
        if(priceLines[k]){ series.removePriceLine(priceLines[k]); delete priceLines[k]; }
        continue;
      }
      if(!shown){
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
    paintLevelCounts();
    /* The comparison depends on WHOSE plan is on screen, so it is repainted
       wherever that can change. It writes one element and reads nothing the
       ticket owns — it can never gate or disable Arm. */
    paintSecondOpinion();
  }

  /* ---------- the ticket maths ---------- */
  function recompute(){
    const out = $('tkOut'), key = $('tkKey'), warn = $('tkWarn');
    const e = levels.entry, tp = levels.tp, sl = levels.sl;

    // Say plainly whose numbers these are. Anything the operator touched is
    // excluded from the strategy record, so the label must never read "engine".
    const kind = base ? base.kind : 'none';
    /* One word each. The long forms ("structure draft", "operator-modified")
       overflowed the 268px head and wrapped it to two rows; the Why pane
       already carries the full sentence for every one of these states. */
    /* THE CHIP AND THE LINES MUST AGREE. `chip-accent` is the ticket's bright
       register and it said "engine" in it for a setup risk had refused, or one
       whose entry filled days ago — the same over-claim applyLevels makes with
       colour, in miniature and directly above it. One authority: both read
       `base.fate`. */
    const spent = kind === 'engine' && !modified && base.fate &&
                  base.fate !== 'live';
    $('tkSrc').textContent = kind === 'position'
      ? (modified ? 'your exit — unsaved' : 'open position')
      : kind === 'engine'
      ? (modified ? 'edited'
         : base.fate === 'refused' ? 'not traded'
         : base.fate === 'filled' ? 'already entered'
         : base.fate === 'missed' ? 'entry missed' : 'engine')
      : kind === 'draft' ? (modified ? 'edited' : 'your plan')
      // `manual` went with the seeded ruler. With no base, anything in the
      // form was typed by the operator and belongs to them.
      : modified ? 'yours' : 'no setup';
    $('tkSrc').className = 'chip ' +
      (kind === 'engine' && !modified && !spent ? 'chip-accent' : 'chip-amber');
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
      row('reward/risk after fees', m.rrNet == null ? '—' : m.rrNet.toFixed(2), rrCls) +
      row('size', m.size == null ? '—' : pf(m.size)) +
      row('you risk', m.riskUsd == null ? '—' : usd(m.riskUsd));

    /* The Numbers pane holds only the WORKING — the three figures the decision
       rests on are pinned right beneath it, so repeating them here spent three
       rows saying what is already permanently on screen an inch lower. */
    out.innerHTML =
      row('risk / unit', pf(m.riskPerUnit)) +
      row('reward/risk before fees', m.rrGross.toFixed(2)) +
      row('position value', m.notional == null ? '—' : usd(m.notional)) +
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

  /* WHY EVERY removePriceLine IS WRAPPED, once, for the four places that do it.

     A price line belongs to the series it was drawn on. Change symbol or
     timeframe and `load()` builds a fresh series, which takes its lines with
     it — but the arrays here still hold the old handles, and lightweight-charts
     throws on a handle whose series is gone. Removing an already-removed line
     is not a degraded path, it is a teardown arriving second; the array is
     emptied on the next line either way, so there is nothing to report and
     nothing to fall back to.

     That is the whole reason these blocks are empty, and it is written here
     rather than three times below. What would NOT be acceptable is an empty
     catch around a draw — a line that failed to appear is a chart lying about
     where a trade sits, and none of these are that. */
  function drawScale(){
    if(scaleLine){ try{ series.removePriceLine(scaleLine); }catch(e){ /* line already gone with its series */ } scaleLine = null; }
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
      ? `Perpetual futures charge funding every ${(24 / cfg.cost.funding_per_day).toFixed(0)}` +
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

     It is a TITLE, not a strip. The visual ladder was retired for the reason
     loadContext() gives below, and the LADDER_TONE map that coloured its
     rungs outlived it here unread — along with fourteen `.ctx-ladder` rules
     in ss.css that had styled no element on any surface since. Both are gone;
     the linter found the map, and the map led to the CSS. */
  /* It also owns the chip's WORDING. /api/context reads the same regime row
     this load already fetched and adds `label`, the display noun the server
     owns — so Overwatch, Market Weather and this chip all say "Bull weakening"
     and none of them says WEAKENING_BULL. The chip used to de-underscore the
     enum here, which made one recording read in two registers on two surfaces.
     The reading is unchanged; only who spells it has. */
  async function loadContext(mySeq){
    /* The per-timeframe ladder read as a second timeframe picker — same
       shape, adjacent position, different meaning, hover-only explanation.
       The same facts now live on the regime chip's hover: context, priced
       at exactly the attention it deserves. */
    const el = $('cRegime');
    if(!el || !sym) return;
    /* This load's own reading, straight off the facts already on screen. It is
       the same row /api/context returns, and it is what the chip falls back to
       if the endpoint that carries the wording cannot be reached. */
    const own = facts.regime.length
      ? facts.regime[facts.regime.length - 1].regime : null;
    try{
      const c = await api('/api/context?symbol=' + encodeURIComponent(sym));
      /* Same guard the candles get. This writes the chip now, not just a
         hover, and a switch mid-fetch would otherwise land the old market's
         regime under the new market's name. */
      if(mySeq !== loadSeq) return;
      const rows = c.timeframes || [];
      const here = rows.find(t => t.tf === tf);
      el.textContent = own ? ((here && here.label) || own.replace('_', ' '))
                           : 'no regime';
      el.title = 'regime by timeframe' + String.fromCharCode(10) + rows.map(t => {
        const label = t.label || 'no reading';
        const extra = (t.active_zones ? ` · ${t.active_zones} zones` : '')
                    + (t.ready ? ` · ${t.ready} ready` : '');
        return `${t.tf === tf ? '▸' : ' '} ${t.tf}: ${label}${extra}`;
      }).join(String.fromCharCode(10));
    }catch(e){
      if(mySeq !== loadSeq) return;
      /* Degraded, and audible. The reading survives — it came from the facts —
         but the wording authority did not answer, so the chip prints the
         engine's own enum and the hover says why the ladder is missing.
         Blanking both would read as "this market has no context", which is a
         different and false claim. Absent context still beats stale context. */
      el.textContent = own ? own.replace('_', ' ') : 'no regime';
      el.title = 'regime by timeframe unavailable — this is the raw engine '
               + 'reading, not the wording the other surfaces use';
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
             setupF: [], cycle: [], riskF: [], orderF: []};
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
    // ...and the market it belonged to, or the second-opinion line would go on
    // comparing against a position the screen no longer describes.
    posKey = null;
    for(const l of posLines){ try{ series.removePriceLine(l); }catch(e){ /* line already gone with its series */ } }
    posLines = [];
    $('tkOpen').innerHTML = '';
    try{ paintSecondOpinion(); }catch(e){ /* ticket may not be built yet */ }
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
    if(preferredSetupId) window.SSChartCtx.setup_id = preferredSetupId;
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

    /* THE THREE BELOW ARE STARTED HERE AND AWAITED WHERE THEY ALWAYS WERE.
       They used to be issued one after another AFTER the ten-way Promise.all
       had already settled — the draft, then the open positions, then the fee
       config — so a symbol switch paid four sequential round trips instead of
       one. None of the three reads the others' answers, and none reads the
       ten; the only thing the old order bought was the order itself.

       Only the STARTS move. Every await, seq guard, catch and assignment stays
       exactly where it was, so the failure semantics are untouched: the draft
       and the positions stay non-fatal, the fee config still keeps its
       previous value rather than blanking, and a load that loses the race
       still returns before the config is applied.

       The bare `.catch(() => {})` on each is not error handling — the real
       handlers are below. It marks the promise as having a handler so a
       rejection that lands before its await does not surface as an unhandled
       rejection in the console. */
    const draftReq = api(`/api/draft?symbol=${encodeURIComponent(sym)}&tf=${tf}`);
    const openReq = api(`/api/manual/open?symbol=${encodeURIComponent(sym)}&tf=${tf}`);
    const cfgReq = api('/api/trade-config?symbol=' + encodeURIComponent(sym));
    draftReq.catch(() => {}); openReq.catch(() => {}); cfgReq.catch(() => {});

    let res;
    try{
      res = await Promise.all([
        api(`/api/candles?symbol=${sym}&tf=${tf}&limit=${BARS}`),
        q('swing'), q('structure'), q('zone'), q('liquidity'),
        q('regime'), q('setup'), q('cycle'), q('risk'),
        /* WHAT BECAME OF THE SETUP. `setups.py` has no terminal state meaning
           "already acted on" — it emits FORMING, CONFIRMING, VALIDATED,
           CANCELLED and EXPIRED, and EXPIRED fires when the ZONE breaks — so a
           setup whose entry filled days ago stays VALIDATED and the chart kept
           drawing it as a plan the engine is still waiting on. The order facts
           answer it and always did: execsim writes PLACED, then FILLED or
           MISSED, against the same setup_id and the same market_time, so this
           rides the same 1500-bar window as the setup it describes.

           In the SAME Promise.all as the rest on purpose. It decides whether
           the bracket is drawn as a live plan, so a silent failure here would
           re-create the exact lie it exists to end; failing with the other
           nine puts "Could not load" on screen instead. */
        q('order')]);
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
        const dr = await draftReq;
        if(seq === loadSeq) draftPlan = dr && dr.draft ? dr.draft : null;
      }catch(err){ if(seq === loadSeq) draftPlan = null; }
      // The operator's open trades here. Same seq guard, same reason.
      try{
        const op = await openReq;
        if(seq === loadSeq){
          openPos = (op && op.open) || [];
          enginePos = (op && op.engine) || null;
          // The market the SERVER answered for, not the one we asked about —
          // the second-opinion guard is only worth something if it reads what
          // came back.
          posKey = op && op.symbol && op.tf ? op.symbol + '|' + op.tf : null;
        }
      }catch(err){ if(seq === loadSeq){ openPos = []; enginePos = null; posKey = null; } }
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
    /* A newer symbol/tf won the race. Bailing is right — this response
       describes a market the header no longer names — but the "Loading …"
       message this load wrote is still on screen, and only the winner clears
       it. If the winner is gone (it bailed too, or never ran), the pane sits
       on that message forever. Say so instead: an unresolved load is a
       degraded path, and degraded paths in this app are audible. */
    if(seq !== loadSeq){ noteStalledLoad(); return; }
    // Costs are per VENUE, so the config must be re-read per symbol. Spot fees
    // on a perp chart would flip the sign of the net-R decision.
    try{
      cfg = await cfgReq;
      setLock();
    }catch(err){ /* keep whatever we had; the ticket labels its source */ }
    if(seq !== loadSeq){ noteStalledLoad(); return; }
    const [c, swing, struct, zone, liq, regime, setupF, cycle, riskF,
           orderF] = res;
    candles = c;
    facts = {swing, struct, zone, liq, regime, setupF, cycle, riskF, orderF};

    if(!candles.length){
      // "the venue served nothing here" is a different fact from "the request
      // failed", and the operator has to be able to tell them apart.
      clearChart(`No candles for ${sym} · ${tf}`,
                 'the store holds no bars for this timeframe yet');
      return;
    }
    $('chartEmpty').style.display = 'none';
    const marketKey = sym + '|' + tf;
    const resetPriceScale = priceScaleMarket !== marketKey;
    painted = marketKey;           // from here down, the screen describes THIS market
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
    if(resetPriceScale){
      // Vertical dragging disables Lightweight Charts' auto-scale. setData()
      // preserves that manual range, so explicitly release it for a new
      // market before setting the new time window.
      series.priceScale().applyOptions({autoScale: true});
      priceScaleMarket = marketKey;
    }
    /* Volume coloured by the bar it belongs to, so a spike reads as buying or
       selling at a glance instead of as a bare quantity. */
    if(volSeries) volSeries.setData(candles.map(c => ({
      time: c.time, value: c.volume || 0,
      // Same family as the candles above them, at half their weight — a volume
      // bar answers "more or less than its neighbours", which is shape, not
      // magnitude. Left at the old full-chroma greens and reds it became the
      // loudest thing on a chart whose candles had just been taken down.
      color: c.close >= c.open ? 'rgba(126,180,146,.26)' : 'rgba(196,124,124,.26)'})));
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
    /* Writes both the chip and its hover — one writer for one element. The
       regime it prints is `facts.regime`, which this load just fetched; what
       the call goes out for is the display noun the rest of the app uses. */
    loadContext(seq);

    drawOverlays();
    pickSetup(!!(opts && opts.keepTicket));
    drawPosition();
    drawClosedTrade();
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
  /* Every price the operator's own order HOLDS, whether or not it is drawn.
     Empty when nothing is armed. Two callers with two different questions —
     see positionPrices below for the drawing one. */
  function bookPrices(){
    if(!openPos.length) return [];
    const p = openPos[0];
    return [p.fill_price || p.entry, p.tp, p.current_stop || p.sl]
      // The armed order's rungs count too: the ticket's dashed "PLAN · 50% OFF"
      // line sitting on the same pixel as the order's own gold one is the
      // six-labels-for-three-prices defect with a fourth price added.
      .concat((p.partials_planned || []).map(r => r.price))
      .map(v => parseFloat(v)).filter(v => isFinite(v));
  }

  /* The prices the operator's own armed order is already drawing, so the
     ticket does not label them a second time. Empty when nothing is armed. */
  function positionPrices(){
    /* Nothing is taken by a line that is not drawn. With `Your levels` off the
       gold lines are gone, so deduping the ticket bracket against them would
       delete BOTH copies of every shared price and leave the chart with no
       entry, stop or target at all — hiding one layer silently emptying the
       other is the worst thing this toggle could do. */
    if(!overlays.yours) return [];
    return bookPrices();
  }

  /* ═══════════════ WHAT BECAME OF A SETUP ═══════════════

     ONE READING, used by three surfaces: the bracket's styling, the ticket's
     rationale and the second opinion. Each of them was asking its own version
     of "is the engine still waiting on this trade", and two of them were not
     asking at all.

     Two facts, both already on this chart:

     · the RISK AUTHORITY's decision. A REJECTED setup is not a trade the
       engine will take, and `pickSetup` set `base.kind = 'engine'` BEFORE it
       looked the decision up — so a refusal reached the reader as a chip while
       three full-brightness ENGINE lines said the opposite. This file's own
       argument, first made when the 14-bar ruler was given a dim register and
       later the reason that ruler was deleted outright: three horizontal price
       lines outweigh any caption.

     · the ORDER's last word. FILLED means the entry already happened; MISSED
       means the window expired without price coming back. Either way the
       moment is gone, and neither is visible in the setup fact, which is still
       VALIDATED and stays that way until the zone breaks.

     FILLED beats MISSED because execsim stops at a fill, and REFUSED beats
     both on the LINE — one label has room for one word, and "the book would
     not have taken this" is the one that decides whether to act. The prose
     under the ticket has room for both and says both.

     Nothing here is inferred: it reports the facts or it returns 'live', and
     'live' is the only state that keeps the bright register. */
  function setupFate(id){
    const d = (facts.riskF || []).filter(
      r => r.event === 'DECISION' && r.setup_id === id).pop() || null;
    let order = null, orderTs = null;
    for(const o of (facts.orderF || [])){
      if(o.setup_id !== id) continue;
      if(o.event === 'FILLED'){ order = 'FILLED'; orderTs = o.confirmed_at; break; }
      if(o.event === 'MISSED'){ order = 'MISSED'; orderTs = o.confirmed_at; }
    }
    const refused = !!d && d.decision === 'REJECTED';
    return {d, refused, order, orderTs,
            state: refused ? 'refused'
                 : order === 'FILLED' ? 'filled'
                 : order === 'MISSED' ? 'missed' : 'live'};
  }

  /* ═══════════════ THE SECOND OPINION ═══════════════

     WHAT THE ENGINE ACTUALLY HAS HERE — and the four things that phrase can
     mean are not interchangeable. `pickSetup` folds a structure draft, a
     14-bar ruler and an edited plan into one dotted look, and only two of the
     four are the machine saying "this trade, at these prices": a VALIDATED
     setup fact, and a position the engine has already taken. Everything else
     is a sketch, and quoting a sketch back as a second opinion would invent an
     authority that does not exist.

     Returns {kind:'sketch'} for the two that are not — the caller says so in
     one sentence rather than staying silent, because the operator's whole
     complaint is not knowing what the coloured lines mean. */
  function enginePlanHere(){
    if(enginePos && enginePos.symbol === sym && enginePos.tf === tf)
      return {kind: 'position', dir: enginePos.direction,
              entry: +enginePos.entry, tp: +enginePos.tp, sl: +enginePos.sl};
    if(setup)
      return {kind: 'setup', dir: setup.direction, id: setup.setup_id,
              entry: +setup.entry, tp: +setup.tp, sl: +setup.sl};
    /* The 14-bar ruler was the other sketch and no longer exists (see `base`),
       leaving the structure draft as the only one. It is still a sketch: the
       engine drew it from a live zone but has not judged the trade, and
       quoting it back as a second opinion would invent an authority. */
    if(base && base.kind === 'draft')
      return {kind: 'sketch'};
    return null;
  }

  /* Say the disagreement in words.

     The operator's report: "there's six plotted data points on the chart" —
     three gold ones that are their filled trade and three the engine drew, and
     the only thing distinguishing a genuine difference of opinion from a
     redraw of the same idea was the colour of the lines and the gap between
     them. This names it: which level, which way, by how much.

     Three properties this must keep:

     · It never gates anything. Not one line here touches #tkArm, #tkBlock or
       `armable`. The operator was explicit that the engine might simply have
       the better entry, and a control that refuses a legitimate intent is
       worse than one that informs it.
     · Every figure goes through window.SSFormat. A percentage rounded locally
       is the same defect as a locally rounded dollar, one surface later.
     · It goes quiet with the layer that owns the lines it is talking about —
       the Engine plan switch when it is quoting the engine's levels, Your
       levels when it is describing your own dotted bracket. The point of the
       two switches is that the operator sets how loud the second opinion is,
       and a sentence that answers the wrong one of them is noise. */
  function paintSecondOpinion(){
    const el = $('tkSecond');
    if(!el) return;
    el.innerHTML = ''; el.hidden = true;
    /* SAME SYMBOL, SAME TIMEFRAME, or nothing. `painted` is the market the
       facts on screen describe and `posKey` is the market the open book was
       answered for; comparing across either of them would put one market's
       entry beside another market's, which is the wrong-price-under-the-right-
       name failure this file has already been bitten by once. */
    const here = sym + '|' + tf;
    if(painted !== here || posKey !== here || !openPos.length) return;
    const eng = enginePlanHere();
    if(!eng) return;
    if(eng.kind === 'sketch'){
      /* ANSWER THE SWITCH THAT OWNS THE BRACKET. This sentence is not about
         the engine's plan — it says there ISN'T one, and then describes the
         dotted bracket, which on this branch is a DRAFT and therefore belongs
         to `Your levels` (bracketMine in applyLevels). Gating it on `Engine
         plan` answered the wrong switch both ways round: Your levels off left
         "the dotted bracket is yours to drag" over an empty chart, and Engine
         plan off took the sentence away while its bracket was still drawn.
         `lvlHidden` is exactly "the bracket applyLevels drew is not on the
         chart", whichever switch decided that, so it is the right question. */
      if(lvlHidden) return;
      el.innerHTML = '<b>No engine setup here</b> — the dotted bracket is ' +
        'yours to drag, not a second opinion.';
      el.hidden = false;
      return;
    }
    // Past here the line quotes the ENGINE's own levels, so it answers the
    // Engine plan switch.
    if(!overlays.engine) return;
    const F = window.SSFormat;
    if(!F){
      // Degraded, and audible: silence here would read as "the engine agrees".
      el.innerHTML = '<b>Second opinion</b> — the engine has its own plan ' +
        'here, but the shared number formatter did not load, so the ' +
        'difference cannot be stated.';
      el.hidden = false;
      return;
    }
    const p = openPos[0];
    const num = v => { const n = parseFloat(v); return isFinite(n) ? n : null; };
    const yours = {entry: num(p.fill_price != null ? p.fill_price : p.entry),
                   sl: num(p.current_stop != null ? p.current_stop : p.sl),
                   tp: num(p.tp)};
    /* Signed distance as a percentage of YOUR price, which is the reference
       the sentence names. Under 0.05% the formatter would print "0.0% above"
       beside two visibly different numbers, so that band is called level.
       Returns the sentence AND whether it was a difference at all, because the
       headline has to know before it calls this a disagreement. */
    const gap = (theirs, mine, label) => {
      if(theirs == null || mine == null || !isFinite(theirs) || mine === 0)
        return null;
      const d = (theirs - mine) / Math.abs(mine) * 100;
      const same = Math.abs(d) < 0.05;
      const word = same ? 'level with yours'
        : F.pct(Math.abs(d)) + (d > 0 ? ' above' : ' below');
      return {label, same, txt: `${label} ${F.px(theirs)}, ${word}`};
    };
    const rows = [gap(eng.entry, yours.entry, 'entry'),
                  gap(eng.sl, yours.sl, 'stop'),
                  gap(eng.tp, yours.tp, 'target')].filter(Boolean);
    if(!rows.length) return;
    /* "HAS a validated setup" is a claim about NOW, and it was made for every
       validated setup on the chart — including ones whose entry filled days
       ago. Same reading as the bracket and the ticket (setupFate), so the
       three cannot drift apart. */
    const f = eng.kind === 'setup' ? setupFate(eng.id)
                                   : {state: 'live', refused: false, d: null};
    const head = eng.kind === 'position'
      ? 'the engine is in its own trade on this chart'
      : f.state === 'filled' ? 'the engine already entered its setup here'
      : f.state === 'missed' ? 'the engine\'s setup here never filled'
      : 'the engine has a validated setup on this chart';
    /* PENDING is a limit resting on the book, not a trade. #tkOpen one row
       above says so in as many words — "fills if touched … else missed" — and
       this line calling the same order an open trade contradicted it on the
       surface where the operator decides whether to arm another. */
    const mineTxt = p.state === 'PENDING' ? 'your resting order'
                                          : 'your open trade';
    /* Opposite directions is the loudest thing this line can report and does
       not belong buried behind three prices. NORMALISED on both sides, the way
       the duplicate-arm guard and the book reconciliation already do it: the
       engine's LONG against a book that spells it Long is not agreement, and a
       raw !== would have called it one. */
    const engDir = String(eng.dir || '').toUpperCase();
    const myDir = String(p.direction || '').toUpperCase();
    const flip = engDir && myDir && engDir !== myDir
      ? ` It is ${engDir} where you are ${myDir}.` : '';
    /* A setup risk REFUSED is not a trade the engine is waiting to take, and
       neither is one it has already entered or already missed. Drawn at full
       brightness both looked exactly like one. Both are stated in the Why pane
       too; they are restated here because this is the sentence that calls the
       setup a second opinion, and an opinion the machine has already acted on
       is not one it is offering. */
    let caveat = '';
    if(f.refused){
      const plain = c => window.SSFunnel
        ? SSFunnel.plain(c) : String(c).replace(/_/g, ' ').toLowerCase();
      caveat = ' Risk would not trade it (' +
        ((f.d && f.d.reasons) || []).map(plain).join('; ') +
        '), so this is analysis, not a trade the engine is waiting to take.';
    }
    /* Same rule, same reason: the practice fill says nothing about a setup
       risk refused, and appending "its entry has already happened" to a
       refusal claims an event that did not occur. The refusal caveat above
       already says what this setup is. */
    if(f.refused){ /* the caveat above stands alone */ }
    else if(f.order === 'FILLED')
      caveat += ' Its entry has already happened, so these are the levels it ' +
        'went in on rather than a plan it is still waiting on.';
    else if(f.order === 'MISSED')
      caveat += ' Its entry window expired without a fill, so it is history ' +
        'rather than a plan the engine is still waiting on.';
    /* AGREEMENT IS NOT A DISAGREEMENT. Arm the engine's own setup at the
       engine's own prices and the headline used to say the machine was set
       AGAINST you, above three rows each reporting that a level was identical
       to yours — an argument announced, then three pieces of evidence that
       there wasn't one. When every level matches, one clause says so. A flip
       is never agreement, whatever the prices do. */
    const agreed = !flip && rows.every(r => r.same);
    if(agreed){
      const names = rows.map(r => r.label);
      const list = names.length > 1
        ? names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1]
        : names[0];
      el.innerHTML = `<b>Second opinion</b> — ${head}, and it agrees with ` +
        `${mineTxt}: same ${list}.` + caveat;
    }else{
      el.innerHTML = `<b>Second opinion</b> — ${head}, compared with ` +
        `${mineTxt}.${flip} ` + rows.map(r => r.txt).join(' · ') + '.' + caveat;
    }
    el.hidden = false;
  }

  /* A SETTLED TRADE, on the bars it happened on. Two lines and a jump to the
     right part of history — deliberately not the ticket: this trade is over,
     nothing about it can be armed, and dressing it as a plan would invite
     exactly that. Cleared on the next load, so it never haunts another chart. */
  function drawClosedTrade(){
    for(const l of tradeLines){ try{ series.removePriceLine(l); }catch(e){ /* line already gone with its series */ } }
    tradeLines = [];
    const t = pendingTrade;
    pendingTrade = null;
    if(!t || !candles.length) return;
    const entry = parseFloat(t.entry), exit = parseFloat(t.exit_price);
    const won = (t.r_multiple || 0) > 0;
    const outWord = String(t.outcome || '').toUpperCase() === 'TP' ? 'TARGET'
                  : String(t.outcome || '').toUpperCase() === 'SL' ? 'STOP'
                  : String(t.outcome || 'EXIT').toUpperCase();
    for(const [price, colour, title] of [
        [entry, '#94a3b8', 'CLOSED · IN AT'],
        [exit,  won ? '#4ade80' : '#f87171', 'CLOSED · OUT (' + outWord + ')']]){
      if(!isFinite(price)) continue;
      tradeLines.push(series.createPriceLine({
        price, color: colour, lineWidth: 1, lineStyle: 2,
        axisLabelVisible: true, axisLabelColor: 'rgba(18,22,18,.94)',
        axisLabelTextColor: colour, title}));
    }
    /* Move to WHEN it happened. Landing on the newest 120 bars would show the
       lines floating over price that has nothing to do with the trade — the
       exact misreading this is meant to prevent. */
    if(t.ts){
      const i = candle_index_at(t.ts);
      if(i != null){
        const span = Math.min(candles.length, VISIBLE_BARS);
        const from = Math.max(0, i - Math.floor(span * 0.6));
        chart.timeScale().setVisibleLogicalRange(
          {from, to: Math.min(candles.length + 4, from + span)});
      }
    }
  }

  /* Nearest bar at or before a timestamp, or null when the trade predates the
     candles we hold — in which case the view is left where it was rather than
     scrolled to a bar that is not the one. */
  function candle_index_at(ts){
    let lo = 0, hi = candles.length - 1, best = null;
    while(lo <= hi){
      const mid = (lo + hi) >> 1;
      if(candles[mid].time <= ts){ best = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    return best;
  }

  function drawPosition(){
    for(const l of posLines){ try{ series.removePriceLine(l); }catch(e){ /* line already gone with its series */ } }
    posLines = [];
    const el = $('tkOpen');
    posN = 0;
    if(!openPos.length){
      el.innerHTML = '';
      paintLevelCounts(); paintSecondOpinion();
      return;
    }
    const p = openPos[0];
    /* The switch governs the CHART, not the ticket. Every line below is still
       counted so the toggle can report what it holds, and the readout at the
       end of this function still speaks either way — hiding the gold lines is
       a request for a quieter chart, not for the app to stop telling the
       operator they are in a trade. */
    const drawn = overlays.yours;
    // A trailed trade's stop is wherever the ratchet has moved it — drawing
    // the original would misstate where the trade dies.
    const stopNow = p.current_stop || p.sl;
    for(const [k, price, label] of [['entry', p.fill_price || p.entry, 'YOURS · ENTRY'],
                                    ['tp', p.tp, 'YOURS · TP'],
                                    ['sl', stopNow,
                                     p.trailed ? 'YOURS · TRAIL' : 'YOURS · SL']]){
      const v = parseFloat(price);
      if(!isFinite(v)) continue;
      posN++;
      /* A SMALL PILL, NOT A BLOCK. Left alone the axis tag takes the LINE's
         colour as its background (`axisLabelColor || color`), so three solid
         amber slabs stack down the right edge — the loudest thing on the
         chart, restating what the gold line already says. Dark tablet, amber
         text: the tag reads as a label OF the line rather than as a fourth
         object. The line itself is untouched; `#fbbf24` is still what LIVE
         means everywhere in this app. */
      if(drawn) posLines.push(series.createPriceLine({
        price: v, color: '#fbbf24', lineWidth: 1, lineStyle: k === 'entry' ? 0 : 3,
        axisLabelVisible: true, axisLabelColor: 'rgba(18,22,18,.94)',
        axisLabelTextColor: '#fbbf24', title: label}));
    }
    /* The ladder, on the chart. A rung already taken is drawn as a fact — the
       size behind it is gone — and one still waiting as a dotted intention, so
       "what have I got left on" is answered by looking rather than by counting
       back from a percentage in a panel. */
    const done = (p.partials_filled || []).map(r => String(r.price));
    for(const r of (p.partials_planned || [])){
      const v = parseFloat(r.price);
      if(!isFinite(v)) continue;
      posN++;
      const filled = done.includes(String(r.price));
      if(drawn) posLines.push(series.createPriceLine({
        price: v, color: filled ? 'rgba(251,191,36,.55)' : '#fbbf24',
        lineWidth: 1, lineStyle: filled ? 3 : 2, axisLabelVisible: true,
        axisLabelColor: 'rgba(18,22,18,.94)',
        axisLabelTextColor: filled ? 'rgba(251,191,36,.7)' : '#fbbf24',
        title: `YOURS · ${Math.round(+r.fraction * 100)}% ${filled ? 'OFF' : 'AT'}`}));
    }
    paintLevelCounts();
    paintSecondOpinion();
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
    const n = Object.assign({swings: 0, structure: 0, zones: 0, liquidity: 0,
                             cycle: 0}, levelCounts());

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
        axisLabelVisible: true, axisLabelColor: 'rgba(18,22,18,.94)',
        axisLabelTextColor: 'rgba(245,158,11,.9)',
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
    lastCounts = n;
    labelOverlays(n);
  }

  /* WHAT EACH LEVEL SWITCH WOULD DRAW — not what is on the chart right now.
     The nine older layers count fact-store rows, which is a claim that stays
     true while the layer is off; these two count lines the switch offers, for
     the same reason. A tally that fell to zero the moment a layer was hidden
     would mark the switch `.empty` and read as "there is nothing here", which
     is the one thing it must not say about a layer you have just turned off.

     The operator's position is always theirs. The ticket bracket goes to
     whichever switch its own labels name — `bracketMine` in applyLevels — and
     it draws its DE-DUPLICATED count while the gold lines are up and its raw
     count once they are gone, which is why `engine` reads `overlays.yours`.
     That is a real dependency, not a leak: hide your own lines and the
     engine's coincident ones genuinely become its to draw. Neither figure
     depends on its OWN switch, so neither changes when you flick it. */
  function levelCounts(){
    return {yours:  posN + (bracketMine ? bracketN : 0),
            engine: bracketMine ? 0 : (overlays.yours ? bracketN : bracketRaw)};
  }

  /* The two level switches are drawn AFTER drawOverlays on every load — the
     bracket does not exist until pickSetup has run — so their tallies are
     folded back into the last one it made rather than recomputed from facts
     they do not come from. Silent until drawOverlays has run once. */
  function paintLevelCounts(){
    if(!lastCounts) return;
    const c = levelCounts();
    if(lastCounts.yours === c.yours && lastCounts.engine === c.engine) return;
    Object.assign(lastCounts, c);
    labelOverlays(lastCounts);
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

  /* The saved preset, or Clean. localStorage throws with storage disabled and
     in a private window that has denied it; an unreadable preference is not
     worth surfacing, because the fallback IS a good chart. */
  function savedPreset(){
    try{
      const v = localStorage.getItem(PRESET_STORE);
      return PRESETS[v] ? v : PRESET_FALLBACK;
    }catch(e){ return PRESET_FALLBACK; }
  }

  /* Which preset the nine switches currently spell, or null when they spell
     none. Every individual switch still moves — that was always the volume
     knob — so the button has to be able to say `Custom` rather than keep
     naming a preset the chart has stopped matching. */
  function presetNow(){
    for(const name of Object.keys(PRESETS)){
      const on = new Set(PRESETS[name]);
      if(PRESET_KEYS.every(k => overlays[k] === on.has(k))) return name;
    }
    return null;
  }

  /* Apply a preset to the nine layers it owns — never to `yours` or `engine`,
     see PRESETS. `defer` is boot: the switches are set before the first load,
     so load()'s own lazy tail fetches and draws once, instead of this painting
     a chart that has no candles yet. */
  async function applyPreset(name, opts){
    const pick = PRESETS[name] ? name : PRESET_FALLBACK;
    const on = new Set(PRESETS[pick]);
    for(const k of PRESET_KEYS) overlays[k] = on.has(k);
    if(!(opts && opts.quiet)){
      try{ localStorage.setItem(PRESET_STORE, pick); }
      catch(e){ console.warn('[chart] the layer preset will not survive a reload'); }
    }
    paintLayerButtons();
    if(opts && opts.defer) return;
    for(const k of Object.keys(LAZY)) if(overlays[k]) await ensureLayer(k);
    if(candles.length) drawOverlays();
  }

  /* Every switch and every preset chip repainted from `overlays` itself, so
     the menu cannot disagree with what is drawn. The `on` CLASS is
     authoritative — labelOverlays reads it back to set aria-pressed — which is
     why it is written here rather than inferred at paint time. */
  function paintLayerButtons(){
    document.querySelectorAll('#cLayersPop [data-o]').forEach(b => {
      const on = !!overlays[b.dataset.o];
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
    });
    const now = presetNow();
    document.querySelectorAll('#cLayersPop [data-preset]').forEach(b => {
      const on = b.dataset.preset === now;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
    });
    paintLayersBtn();
  }

  /* The button says WHAT YOU ARE LOOKING AT. `Layers 3/11` was a count nobody
     can act on — three of what, and is three right? The preset name answers
     the question the control is actually asking, and `Custom` is the honest
     answer once a switch has been moved by hand. The name replaces the visible
     word, so aria-label carries what the control opens. */
  function paintLayersBtn(){
    const name = PRESET_LABEL[presetNow()] || 'Custom';
    const btn = $('cLayersBtn');
    btn.textContent = name;
    btn.setAttribute('aria-label', 'Chart layers — ' + name);
  }

  /* the count is the honesty: 0 means "no facts on this timeframe", not "off" */
  function labelOverlays(n){
    /* [data-o], not `button` — the preset chips are buttons in this popup too,
       and they carry no data-label, so the old selector rewrote each of them
       to the string "undefined" and marked them .empty. Nothing throws. */
    document.querySelectorAll('#cLayersPop [data-o]').forEach(b => {
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
      /* "No data" is fact-store language and it is wrong for the two level
         switches: nothing is ever recorded for them. It says TO DRAW rather
         than "nothing here" for a reason found in the browser — edit the
         ticket and the bracket passes to `Your levels`, leaving `Engine plan`
         with no lines while the engine's setup plainly still exists and the
         second opinion is still quoting it. The switch may say it has nothing
         to draw; it may not say the engine has nothing. */
      if(!c) b.textContent = b.dataset.label +
        (LEVEL_LAYERS[k] ? ' — none to draw' : ' — no data');
      /* Composed, not replaced. Overwriting the title destroyed the authored
         notes on Liquidity and Cycle — the only place the chart says those
         overlays are INFERRED rather than measured — leaving a bare count in
         their place. The note lives in data-note now and the count joins it.

         WHAT THE COUNT CLAIMS. The nine say "recorded" — a fact-store claim,
         true whether the layer is drawn or not. The two level switches said
         "on this chart", which made it a claim about pixels, and a switched-
         OFF layer then reported lines nobody could see. Same claim as the
         nine now: what this switch holds, not what is painted. */
      const count = LEVEL_LAYERS[k]
        ? (c ? `${c} price line${c === 1 ? '' : 's'} while this switch is on`
             : `nothing of ${k === 'yours' ? 'yours' : 'the engine\'s'} to draw on ${sym} ${tf} right now`)
        : c ? `${c} recorded on this timeframe`
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
    /* VALIDATED IS STICKY, AND THE CHART USED TO INHERIT WHATEVER IT STUCK TO.
       setups.py retires a setup only when its ZONE breaks, so one whose entry
       filled — or whose entry window expired — stays VALIDATED indefinitely.
       Meanwhile every setup that DID reach a clean end drops out of this list.
       The survivor is therefore biased towards the oldest: on BTCUSDT 1D on
       8 Aug 2026 the newest VALIDATED setup was from 8 Sep 2024, filled four
       days later, and the chart drew its bracket — stop 18% below the live
       price — because the three setups since had all expired properly.

       A setup the engine has finished with is history, not a plan, and the
       operator's rule is that only a plan the bot generated, a plan of theirs,
       or an active trade may draw on this chart. Falling through to the draft
       (or to nothing) is the right answer here; `setupFate` already knows
       which setups are spent, so this asks it rather than inventing a second
       reading. Refused is NOT spent — risk may size it tomorrow once the
       concurrent slot frees, and it is still the engine's live opinion. */
    const open = valid.filter(f => {
      const s = setupFate(f.setup_id).state;
      return s !== 'filled' && s !== 'missed';
    });
    /* An EXPLICIT request survives the filter. Setup Radar links to one exact
       setup_id, and an operator who clicked a finished trade to review it
       asked for that record — the labels already read FILLED / MISSED and the
       ticket already prints ENTRY ALREADY HAPPENED. The rule above governs
       what this chart volunteers, not what it is told to show. */
    const preferred = preferredSetupId
      ? valid.find(f => f.setup_id === preferredSetupId) : null;
    preferredSetupMissing = !!preferredSetupId && !preferred;
    setup = preferredSetupId ? (preferred || null) : (open[0] || null);

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
      /* READ BEFORE DRESSED. `kind: 'engine'` is what earns the bright,
         solid bracket in applyLevels, and it used to be set here with the
         risk decision looked up four lines below it and the order never
         looked up at all — so a setup the risk authority had refused, and a
         setup whose entry filled two days ago, both drew the identical
         full-brightness ENGINE lines as one the engine is still waiting on.
         `fate` travels on `base` so the styling reads the same answer this
         rationale does. */
      const fate = setupFate(setup.setup_id);
      base = {entry: +setup.entry, tp: +setup.tp, sl: +setup.sl,
              dir: setup.direction, kind: 'engine', fate: fate.state};
      // The risk authority has the last word. If it refused this setup, the
      // ticket says so above the rationale — otherwise the chart would invite
      // the operator to size a trade the engine already rejected.
      const d = fate.d;
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
        // `fate.refused`, not a second comparison of the same field. The
        // bracket's brightness and this paragraph have to be answering one
        // question, or the chip can read NOT TRADED over lines that do not.
        (fate.refused
          ? `<br>${(d.reasons || []).map(plain).join('; ')}` +
            '<br>This setup would not be traded. Anything below is analysis only.'
          : `<br>sizes ${usd(+d.risk_usd)} of risk`) + '</div>';
      /* AND WHETHER THE MOMENT HAS PASSED. Printed alongside the verdict
         rather than instead of it: a refused setup whose entry has also
         already filled is two separate things worth knowing, and the line
         label can only carry one of them.
         `entered`, not "the engine bought" — execsim simulates EVERY
         validated setup for research and only the ones risk sized are
         exposure (server.py: "shadow orders for strategy research"), so a
         word implying a position on the book would be false on exactly the
         setups this note fires most often for. */
      const when = t => t != null && window.SSClock
        ? ' ' + SSClock.ago(SSClock.ageOf(t)) : '';
      /* A REFUSED SETUP WAS NEVER ENTERED. execsim places a practice order for
         EVERY validated setup, before the risk authority has ruled — server.py
         calls them "shadow orders for strategy research" and excludes them
         from positions on exactly that basis. Reading the fill without asking
         whether risk allowed it printed "The engine entered this setup 174
         hours ago" directly under this app's own "This setup would not be
         traded", on nine charts, while the line labels beside them read
         NOT TRADED. The refusal is the earlier and stronger fact; it wins. */
      const gone = fate.refused ? ''
        : fate.order === 'FILLED'
        ? '<div class="tk-verdict warn"><b>ENTRY ALREADY HAPPENED</b>' +
          `<br>The engine entered this setup${when(fate.orderTs)}. These are ` +
          'the levels it went in on — not a trade it is waiting to take.</div>'
        : fate.order === 'MISSED'
        ? '<div class="tk-verdict warn"><b>ENTRY WINDOW CLOSED</b>' +
          `<br>The order expired${when(fate.orderTs)} without price coming ` +
          'back, so the engine never took this setup. These levels are ' +
          'history, not a plan.</div>'
        : '';
      $('tkWhy').innerHTML = verdict + gone +
        `<em>Why the engine took it</em>${setup.why || '—'}`;
    }else if(preferredSetupMissing){
      base = null;
      $('tkWhy').innerHTML = preferredInspectOnly
        ? '<div class="tk-verdict"><b>TRIGGER NOT CONFIRMED</b><br>This exact setup is available for chart inspection only. No order plan or substitute setup was loaded.</div>'
        : '<div class="tk-verdict bad"><b>SELECTED SETUP UNAVAILABLE</b>' +
          '<br>The requested setup is no longer validated on this chart. SniperSight did not substitute another setup or draft a new plan.</div>';
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
      /* NOTHING TO DRAW, AND THE CHART SAYS SO RATHER THAN FILLING THE SPACE.
         This branch used to seed a bracket from `last close ± average 14-bar
         range`, always LONG, purely so the ticket had something in it. Dimmed
         and captioned "not a signal, not analysis" — and still three price
         lines on a chart whose whole vocabulary is that a line means someone
         has an opinion about that price. An empty chart is the true statement;
         a 2:1 drawn around the last close is a false one wearing a disclaimer.

         The ticket inputs stay live. An operator who wants to trade a market
         the engine has no opinion on types the three numbers in, and the
         `change` handler on #tkEntry/#tkTp/#tkSl builds the plan from there —
         so the capability the ruler existed to provide survives it. */
      base = null;
      $('tkWhy').innerHTML =
        '<em>Nothing here — the engine has no plan on this chart</em>' +
        'No setup it is waiting on, and price is not at a level it recognises ' +
        'well enough to draft against. Nothing is drawn because there is ' +
        'nothing to draw.<br><br>Type an entry, stop and target above if you ' +
        'want to trade this anyway — it goes to your paper book and never to ' +
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
     the operator cannot reach: mainnet order routing is build-locked (the
     testnet outbox exists, gated separately). Wiring a paper button to a live
     flag would have meant the button stayed dead until someone unlocked the
     mainnet router, which is why it was dead. The live reason is still printed underneath, so the
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
  const TF_S = {'5m': 300, '15m': 900, '1H': 3600, '4H': 14400,
                '1D': 86400, '1W': 604800};
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
    dispatchEvent(new CustomEvent('ss:trade-ticket-state', {detail: {
      state: holding ? 'POSITION_MANAGED' : 'PLANNING', symbol: sym, timeframe: tf
    }}));
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
      : preferredSetupMissing ? true
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
      if(preferredSetupMissing){
        why = 'The selected setup is no longer available. No substitute was loaded.';
      }else if(stale){
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
      const warnEl = $('tkWarn');
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
      // A preset chip is a button in this popup too. Branch before the toggle,
      // or `overlays[undefined]` gets set, the tally counts a key that draws
      // nothing, and the press appears to do nothing at all.
      if(b.dataset.preset){ await applyPreset(b.dataset.preset); return; }
      const key = b.dataset.o;
      overlays[key] = !overlays[key];
      // Repainted from `overlays`, not from this one button: moving a switch by
      // hand is what makes the chart stop matching a preset, and the chips have
      // to clear when it does.
      paintLayerButtons();
      // Lazy layers pay for themselves on first use only; the await is why
      // this handler is async, and drawOverlays runs after either way so
      // switching a layer OFF is instant.
      if(overlays[key] && LAZY[key]) await ensureLayer(key);
      if(candles.length) drawOverlays();
      /* Levels come from the book and the ticket, not the fact cache, so
         drawOverlays cannot redraw them. Both are called because the two
         switches are coupled: hiding YOUR lines frees the ticket bracket to
         draw prices its de-duplication had been suppressing. */
      if(LEVEL_LAYERS[key] && series){ drawPosition(); applyLevels(); }
    });
    /* THE SAVED PRESET, BEFORE THE FIRST LOAD. `defer` skips the fetch-and-draw
       — there are no candles yet — so load()'s own lazy tail does it once, and
       the switches on screen match what will be drawn from the first paint
       rather than flicking a beat later. `quiet` because writing back what we
       have just read is not a preference change. */
    applyPreset(savedPreset(), {quiet: true, defer: true});

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
    /* Arm -> the OPERATOR's paper book, never the strategy record. The version
       the write carries is engine/manual.py's MANUAL_VERSION and is deliberately
       not named here: this comment said `manual-v0.1-draft` for two bumps after
       the store had moved on, because a version copied into prose has no test
       and no reader to keep it honest.
       The reply is reported literally: if the server refuses
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
          /* A 400 IS NOW A REFUSAL AND NOTHING ELSE, so this says so and does
             not guess.

             It used to pattern-match "already have an unresolved" and answer
             "your earlier tap landed — this is the trade you already have",
             which was right for a retry of the SAME order and flatly wrong for
             a second, different plan on the same side: that one is refused,
             nothing is recorded, and telling the operator it landed reports
             success for a trade that does not exist. The retry case never
             reaches here any more — the server recognises the repeated
             intent_id and answers 200 with `already_armed` — so the only thing
             left behind a non-OK status is a plan that was NOT written. */
          const detail = d.detail || ('HTTP ' + r.status);
          out.textContent = 'refused, nothing armed — ' + detail;
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
        /* "Armed" and "already armed" are different events and the receipt has
           to name which one happened. A retry announced as a fresh arm is the
           same lie as a refusal announced for one that worked — it tells the
           operator they now hold two. The entry quoted on the already-armed
           line is the RECORDED one, not what the ticket currently shows, so a
           level nudged between the two taps cannot be read back as fact. */
        const armedIntent = d.intent || {};
        out.textContent = d.already_armed
          ? `already armed — this is the order you placed, not a second one · ` +
            `${armedDir} ${sym} ${tf} · entry ${armedIntent.entry} · ` +
            `your book: ${n} settled, ${openN} open`
          : `armed on paper · ${armedDir} ${sym} ${tf} · entry ${pf(armedEntry)} · ` +
            `your book: ${n} settled, ${openN} open`;
        // The resolver failing is not the arm failing, and the order is on the
        // book either way — but a silent degraded path is a bug here as
        // everywhere, so it rides the receipt.
        if(d.resolve_failed)
          out.textContent += ` · it has not been checked against the bars yet ` +
            `(${d.resolve_failed})`;
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

  /* ONE POPULATE AT A TIME, and one load out of it.

     Opening a chart from Command runs BOTH entry points: `go('chart')` fires
     onShow(), which populates when there is no symbol yet, and the click
     handler then calls open(), which populates when the symbol list is still
     empty. On a cold page both conditions are true at once, so two populates
     ran, each awaiting the same /api/overview and each calling load() when it
     came back.

     Two loads race. The loser bails at the `seq !== loadSeq` guard — which is
     correct, that guard is what stops one market's candles landing under
     another market's name — but it bails AFTER clearChart() has already
     written "Loading AAVEUSDT · 4H…" into the pane, and nothing else ever
     clears that. The chart sat on the loading message forever while the
     ticket beside it filled in from the same response. Reproduced live on
     AAVEUSDT · 4H opening from an Overwatch card.

     Sharing the in-flight promise collapses the two into one, the same way
     SSData dedupes a path. There is then exactly one load, and it is by
     definition the newest, so it always reaches the paint. */
  let populating = null;
  function populate(){
    if(populating) return populating;
    populating = (async () => {
      let o;
      try{ o = await api('/api/overview'); }
      catch(err){ $('chartEmpty').textContent = 'symbol list unavailable'; return; }
      allSymbols = o.symbols.filter(s => s.state !== 'WARMING');
      symMeta = {};
      for(const s of allSymbols) symMeta[s.symbol] = s;
      if(!sym) sym = allSymbols.length ? allSymbols[0].symbol : null;
      if(sym){ paintSymBtn(); await load(); }
    })().finally(() => { populating = null; });
    return populating;
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
    ['SHADOW', 'watch-only — never sized'],
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
    let html = '';
    for(const [state, label] of PICK_GROUPS){
      const rows = allSymbols.filter(s => s.state === state && hit(s));
      if(!rows.length) continue;
      html += `<div class="sym-group">${label} (${rows.length})</div>` +
        rows.map(s => `<button class="sym-row${s.symbol === sym ? ' on' : ''}"
          data-sym="${s.symbol}">
          <b>${s.symbol}</b><i>${s.venue ? venueName(s.venue) : ''}</i></button>`).join('');
    }
    const known = new Set(PICK_GROUPS.map(g => g[0]));
    const rest = allSymbols.filter(s => !known.has(s.state) && hit(s));
    if(rest.length)
      html += `<div class="sym-group">other (${rest.length})</div>` +
        rest.map(s => `<button class="sym-row" data-sym="${s.symbol}">
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
  /* opts.trade — a settled trade from the Results journal. Results could say
     a trade lost 1.11R and not show you the bars it lost them on; "where did
     price actually go" was a question the surface raised and could not answer.
     Held rather than drawn here, because load() clears the chart. */
  function prepare(s, t, opts){
    const previousSetupId = preferredSetupId;
    const previousInspectOnly = preferredInspectOnly;
    pendingTrade = (opts && opts.trade) || null;
    preferredSetupId = opts && opts.setup_id ? opts.setup_id : null;
    preferredInspectOnly = !!(opts && opts.inspect_only);
    sym = s; if(t) tf = t;
    boot();
    document.querySelectorAll('#cTfs button').forEach(b =>
      b.classList.toggle('on', b.dataset.tf === tf));
    paintSymBtn();
    window.SSChartCtx = {symbol: sym, tf};
    if(preferredSetupId) window.SSChartCtx.setup_id = preferredSetupId;
    // Run before the router exposes Trade: new evidence must never sit beside
    // the previous market while onShow() awaits equity or candles.
    if(painted !== sym + '|' + tf || previousSetupId !== preferredSetupId ||
        previousInspectOnly !== preferredInspectOnly)
      clearChart('Loading ' + sym + ' / ' + tf + '...');
  }

  async function open(s, t, opts){
    prepare(s, t, opts);
    /* `sym` is assigned above, so a populate already running for onShow()
       will load THIS symbol — awaiting it is the whole job. Starting a second
       one here is what produced the two racing loads. */
    if(populating) await populating;
    else if(!allSymbols.length) await populate();     // handles load itself
    else{ paintSymBtn(); await load(); }
  }

  wire();
  return {open, prepare, onShow, onHide,
    /* Introspection, for the suites and for answering "why can I not see that
       swing on my phone" without guessing. A cap nobody can observe is
       indistinguishable from a bug. The price-scale state is equally invisible
       behind Lightweight Charts' canvas and lets browser verification prove a
       market switch released a manually pinned range. */
    _markerDrop: () => lastMarkerDrop,
    _priceScaleAuto: () => series ? !!series.priceScale().options().autoScale : null};
})();
