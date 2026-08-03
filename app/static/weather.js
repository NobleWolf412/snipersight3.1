/* Market Weather — the strip that answers "why is my screen empty?".
   Mounts into #weatherRoot on Command. Nothing else in the shell is touched:
   the mount point is the whole contract between this module and the page.

   The problem it exists for: the scanner produces roughly one setup a day, and
   the operator's own complaint was that the quiet reads as broken. Regime was
   already recorded, but it lived as a chip on the chart with no stated purpose.
   Here the regime sits next to the consequence — whether any playbook can
   trade this condition — so an empty Setup Deck explains itself.

   One authority per claim: every word in the right-hand column comes from
   /api/weather, which derives it by asking engine/setups.py's own playbook()
   what it would do. This file decides how that reads on screen and nothing
   more. If it ever starts deciding what is tradeable, the UI and the engine
   will disagree, and the UI will be the one lying. */
(() => {
  const root = document.getElementById('weatherRoot');
  if (!root) return;                 // no mount point, no module. Never inject one.

  /* The module carries its own stylesheet so a mistake in here cannot take out
     the sheet the other four surfaces depend on. */
  if (!document.getElementById('wxCss')) {
    const link = document.createElement('link');
    link.id = 'wxCss';
    link.rel = 'stylesheet';
    link.href = '/static/weather.css?v=2';
    document.head.appendChild(link);
  }

  /* ---------- glossary ----------
     Terms this strip puts on screen that glossary.js may not carry yet. `??=`
     only fills gaps: glossary.js loads first, so wherever it defines a term
     ITS wording wins and this is a no-op. Written for someone who has never
     traded — plain sentence first, the precise one second. */
  const G = window.GLOSSARY || (window.GLOSSARY = {});
  G.playbook ??= "A named set of rules for one kind of trade: what market it hunts, what triggers it, where the stop goes. SniperSight only takes a trade when one of its playbooks covers the conditions in front of it — which is why most days are quiet.";
  G.pullback ??= "A temporary move back against the trend. The pullback playbook buys those dips in an uptrend and sells the bounces in a downtrend.";
  G.reversal ??= "A trade betting the current move is finished and the market is about to turn. A harder call than following a trend, so SniperSight ranks it lower and demands a liquidity sweep first.";
  G.transition ??= "The old trend has broken but a new one has not formed yet. The market is between states — the most common reading on this screen, and the one with the fewest trades in it.";
  G.range ??= "Price moving sideways between a floor and a ceiling with no trend to follow. No playbook covers one yet, so a ranging market produces nothing.";
  G.timeframe ??= "The candle size a chart is read at. The same market can be trending on the daily and going nowhere on the 4-hour — which is why this strip shows both.";

  /* Phrases worth explaining, longest first so "liquidity sweep" is claimed
     before "sweep" can take half of it. */

  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* Underline the first occurrence of each known term so the sentence teaches
     its own vocabulary. First occurrence only: a paragraph with nine dotted
     underlines is decoration, not help. */
  /* Delegates to the single term table in glossary.js. This used to own its own
     copy; the setup deck then needed the same markup, and two tables of the
     same terms is how they drift. Falls back to plain escaped text if glossary
     has not loaded — losing an underline is acceptable, rendering raw HTML is
     not. */
  function teach(text) {
    return window.SSTeach ? window.SSTeach(text) : esc(text);
  }

  /* ---------- presentation lookups ----------
     Both map an engine constant to a class name. Neither decides anything. */
  const TONE = {
    BULL_TREND: 'r-bull', WEAKENING_BULL: 'r-bull-w',
    BEAR_TREND: 'r-bear', WEAKENING_BEAR: 'r-bear-w',
    TRANSITION: 'r-trans', RANGE: 'r-range',
  };
  function bias(tf) {
    if (!tf.regime) return 'b-unknown';        // absent data, not a flat market
    if (tf.bias === 'LONG') return 'b-long';
    if (tf.bias === 'SHORT') return 'b-short';
    return tf.requires_sweep ? 'b-gated' : 'b-flat';
  }
  /* BTCUSDT -> BTC, BTC-USD -> BTC. The full symbol stays in the title. */
  const shortName = s => String(s).replace(/-USD$/, '').replace(/USDT$/, '');

  const COLLAPSED = 8;                 // above the fold beats complete-but-buried
  let showAll = false;
  /* Both start CLOSED on Command, and survive the 30s re-render — a panel that
     folded itself back up under the reader every half minute would be worse
     than one that never folded at all. */
  let tableOpen = false, backdropOpen = false;
  const open = new Set();              // rows the operator expanded, kept across refreshes

  function rowHtml(s) {
    const cells = s.timeframes.map((t, i) => {
      const b = bias(t);
      // A colour change between adjacent cells IS the disagreement, so the
      // break in the rule is drawn from the same two classes — no second
      // opinion about whether the timeframes agree.
      const split = i > 0 && bias(s.timeframes[i - 1]) !== b ? ' split' : '';
      return `<div class="wx-tf ${b}${split}">` +
        `<span class="tfk">${esc(t.tf)}</span>` +
        `<span class="reg ${TONE[t.regime] || 'r-none'}">${esc(t.label)}</span></div>`;
    }).join('');
    return `<div class="wx-row wx-data tier-${s.tier}${s.live ? ' live' : ''}` +
      `${open.has(s.symbol) ? ' open' : ''}" data-sym="${esc(s.symbol)}"` +
      ` role="button" tabindex="0" aria-expanded="${open.has(s.symbol)}">` +
      `<div class="wx-sym" title="${esc(s.symbol)}"><span>${esc(shortName(s.symbol))}</span></div>` +
      cells +
      `<div class="wx-mean"><span class="wx-arrow" aria-hidden="true">&rarr;</span>` +
      `<span>${teach(s.meaning)}</span></div>` +
      `<div class="wx-why">${teach(s.why)}</div></div>`;
  }

  /* ---------- Bitcoin cycle backdrop ----------
     The nested-cycle model has been computed and served since S31 and rendered
     nowhere: `/api/cycles` had zero callers in the whole of static/, while
     glossary.js already defined `dcl`, `wcl` and `translation` — someone
     intended this and stopped.

     It goes HERE, once, at the top of Market Weather, and it is BITCOIN ONLY.
     The alt basket correlates ~0.65 to BTC at lag 0, which licenses a shared
     BACKDROP and specifically forbids the alternative: a per-symbol cycle stage
     fanned across 33 deck rows would be 33 copies of one reading, each looking
     like independent confirmation. That is the confluence trap the glossary
     already warns about, rebuilt in the UI.

     Every row carries its own evidence class. `mechanical` means arithmetic on
     detected swings; `heuristic` means a community rule of thumb fitted to two
     or three samples. The engine labels these in its own docstring and the
     labels travel with the numbers rather than sitting in a footnote. */
  let cyc = null;
  let lastWeather = null;   // so the backdrop can re-render without a refetch

  const D = ts => new Date(ts * 1000).toLocaleDateString(undefined,
    {day: 'numeric', month: 'short', year: 'numeric'});
  const DSTR = s => {
    const [y, m, dd] = String(s).split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, dd)).toLocaleDateString(undefined,
      {day: 'numeric', month: 'short', year: 'numeric'});
  };

  /* `isOpen` is a PARAMETER rather than a read of module state so this stays a
     pure function of its inputs — test_cycle_lede evaluates it in isolation,
     and a hidden dependency on a `let` outside it is a function that only works
     in one place. */
  function cycleLede(c, isOpen) {
    if (!c || c.unavailable) return '';
    const wk = (c.weekly && c.weekly.cycles) || [];
    const last = wk[wk.length - 1];
    const w = c.windows || {};
    const rows = [];

    if (last) {
      // Counted from the data, never asserted. The plan for this panel claimed
      // the latest cycle was the first to peak early AND the first to break;
      // it is the first to peak EARLY (1 of 7 left-translated) but the third
      // to break (3 of 7 failed, two of them right-translated). Conflating the
      // two would have been a false claim in the first sentence on screen.
      const nLeft = wk.filter(x => x.translation === 'left').length;
      const nFail = wk.filter(x => x.failed).length;
      const pct = Math.round(last.fraction * 1000) / 10;
      const early = last.translation === 'left';
      rows.push(`<div class="cy-row">
        <div class="cy-k">Weekly <span class="term" data-t="translation">cycle</span></div>
        <div class="cy-v">
          <b class="${early ? 'cy-warn' : ''}">${early ? 'Peaked early' : 'Peaked late'}${last.failed ? ', then broke' : ''}</b>
          <div class="cy-note">The weekly cycle that ran ${D(last.start_ts)} → ${D(last.end_ts)}
            put its high <b>${pct}%</b> of the way through itself
            ${early ? `— the ${nLeft === 1 ? 'only one of' : `${nLeft} of`} ${wk.length} to peak early.`
                    : `, which is late — ${wk.length - nLeft} of ${wk.length} have.`}
            ${last.failed ? `It also closed below the low it started from, which
              ${nFail} of ${wk.length} have done.` : ''}</div>
          <div class="cy-tag">mechanical · ${wk.length} weekly cycles observed</div>
        </div></div>`);
    }

    if (w.low_to_low && w.halving_anchored) {
      const now = Date.now() / 1000;
      const openState = s => {
        const t = Date.parse(s + 'T00:00:00Z') / 1000;
        const days = Math.round((now - t) / 86400);
        return days >= 0 ? `open now, day ${days}` : `opens in ${-days} days`;
      };
      rows.push(`<div class="cy-row">
        <div class="cy-k"><span class="term" data-t="fourYear">Four-year</span> low window</div>
        <div class="cy-v">
          <div class="cy-win"><span>Low-to-low</span>
            <b>${DSTR(w.low_to_low.start)} → ${DSTR(w.low_to_low.end)}</b>
            <em>${openState(w.low_to_low.start)}</em></div>
          <div class="cy-win"><span>Halving-anchored</span>
            <b>${DSTR(w.halving_anchored.start)} → ${DSTR(w.halving_anchored.end)}</b>
            <em>${openState(w.halving_anchored.start)}</em></div>
          <div class="cy-note">Two ways of estimating when Bitcoin's four-year low is
            due, from different anchors. They disagree by about three months. Both are
            shown and neither is averaged — the gap between them is the honest width of
            the estimate.</div>
          <div class="cy-tag">heuristic · fitted to ${(c.accepted_4y_lows || []).length - 1}
            completed four-year cycles · the halving date is itself an estimate</div>
        </div></div>`);
    }

    if (!rows.length) return '';
    /* DEMOTED, deliberately. This block is explicitly observational — its own
       footer says nothing here opens, sizes or blocks a trade — and it was
       sitting ABOVE the weather table on the surface that answers "what should
       I do right now?". Context outranking instruction is exactly backwards, so
       it now sits last and starts closed. Nothing is removed: the reader who
       wants the longer rhythm opens it, and it remembers that choice. */
    return `<details class="wx-lede cy-details"${isOpen ? ' open' : ''}>
      <summary class="cy-head">
        <span class="t-section">Bitcoin backdrop</span>
        <span class="wx-sub">where the market sits in its own longer rhythm</span>
        <span class="chip">observational</span>
      </summary>
      ${rows.join('')}
      <!-- The caveat is the point of this line and it stays. How many candles
           were read, and which build read them, are not part of it: they told
           the reader nothing about how much to trust the reading, which is the
           only question the sentence exists to answer. Which SERIES it came
           from does bear on that, so that stays too. -->
      <div class="cy-foot">Never consumed by any trading engine — nothing here
        opens, sizes or blocks a trade. Read from
        <b>${esc(c.source_symbol || '—')}</b>${
          c.last_candle_ts ? ', current to ' + D(c.last_candle_ts) : ''}.
        A different Bitcoin series gives a slightly
        different reading; this is one series, not a fact about Bitcoin.</div>
    </details>`;
  }

  /* The engine build stamps (regime and strategy versions) used to sit under
     the weather grid, on the surface a trader opens first. They are provenance
     for whoever is debugging a reading, not for whoever is reading it. */
  function render(d) {
    lastWeather = d;
    const rows = showAll ? d.symbols : d.symbols.slice(0, COLLAPSED);
    const hidden = d.symbols.length - rows.length;
    // The GRID lists every row — tradeable, shadow and warming. Its own
    // counts must say so, or "top 8 of 19" would sit above a 29-row table.
    const rowTotal = d.n_rows != null ? d.n_rows : d.symbols.length;
    // The sentence that does the actual explaining. Regime eligibility is
    // necessary, not sufficient — price still has to arrive at a zone — and
    // saying so is the difference between "quiet" and "broken".
    /* Counts are scoped to the TRADEABLE universe — the same population
       Command counts — because this panel used to fold shadow symbols into a
       headline that reads as opportunity. It said "20 of 29 tradeable" while
       only 11 could be sized; the other nine were shadow, which the risk
       authority never sizes. Two panels on one screen therefore disagreed about
       the universe AND about what "tradeable" meant. */
    const shadow = d.n_shadow || 0, warming = d.n_warming || 0;
    const shadowLive = d.n_shadow_live || 0;
    const footer = d.n_live === 0
      ? 'No symbol is in a condition any playbook trades right now. An empty ' +
        'Setup Deck is the correct answer to that, not a fault.'
      : `${d.n_live} of ${d.n_total} tradeable symbols are in a condition a ` +
        `playbook trades. Even then a setup only appears once price returns to ` +
        `one of that symbol's zones and confirms there, so quiet days are normal.`;
    // Said plainly rather than folded into the count above. A watched symbol
    // that can never be sized is evidence about a venue, not an opportunity.
    const aside = (shadow || warming)
      ? ` <span style="color:var(--fg-4)">${
          shadow ? `${shadow} more are <span class="term" data-t="shadow">shadow</span>`
                 + ` symbols — watched and scored, never sized${
                     shadowLive ? `, and ${shadowLive} of those are live` : ''}` : ''}${
          shadow && warming ? '; ' : ''}${
          warming ? `${warming} still <span class="term" data-t="warming">warming</span>` : ''}.</span>`
      : '';

    /* Command asks "what should I do right now?" and this panel's ANSWER is one
       sentence — whether anything is in a tradeable condition, and that a quiet
       deck is the correct result rather than a fault. The 8-row grid is the
       evidence for that sentence, not the sentence itself, and on the surface
       whose job is instruction it was outweighing the Setup Deck.

       So the sentence stays on screen and the grid goes behind a disclosure.
       The reader who wants to know WHY still gets everything, one click away
       and with its state remembered. */
    root.innerHTML = `<div class="panel wx">
      <div class="panel-head">
        <span class="t-section">Market Weather</span>
        <span class="wx-sub">what the market is doing &middot; and whether anything can be traded</span>
        <span class="chip">${d.n_live} of ${d.n_total} tradeable</span>
      </div>
      <div class="wx-lead">${teach(footer)}${aside}</div>
      <details class="wx-details"${tableOpen ? ' open' : ''}>
        <summary class="wx-summary">Per-symbol breakdown${
          showAll ? '' : ` &middot; top ${Math.min(COLLAPSED, rowTotal)} of ${rowTotal}`}</summary>
        <div class="wx-body">
          <div class="wx-row wx-head">
            <span class="t-label">Symbol</span>
            ${d.timeframes.map(tf => `<span class="t-label">${esc(tf)}</span>`).join('')}
            <span class="t-label mean">what this means</span>
          </div>
          ${rows.map(rowHtml).join('')}
        </div>
        <div class="wx-foot">
          <p><span style="color:var(--fg-4)">Click a row for the full reason.</span></p>
          ${hidden > 0 || showAll
            ? `<button class="btn" id="wxMore">${showAll ? 'Show fewer' : 'Show all ' + rowTotal}</button>`
            : ''}

        </div>
      </details>
      ${cycleLede(cyc, backdropOpen)}
    </div>`;

    const more = document.getElementById('wxMore');
    if (more) more.addEventListener('click', () => { showAll = !showAll; render(d); });
    const det = root.querySelector('.wx-details');
    if (det) det.addEventListener('toggle', () => { tableOpen = det.open; });
    const cyd = root.querySelector('.cy-details');
    if (cyd) cyd.addEventListener('toggle', () => { backdropOpen = cyd.open; });
  }

  function fail(msg) {
    // Loud fallback. Rendering nothing here would be indistinguishable from a
    // calm market, and this strip is the thing that tells calm from broken.
    root.innerHTML = `<div class="panel wx wx-fail">
      <div class="panel-head">
        <span class="t-section">Market Weather</span>
        <span class="chip chip-red">unavailable</span>
      </div>
      <div class="wx-failbody">
        <b>Market Weather could not load.</b>
        <code>${esc(msg)}</code>
        <div>No market condition is being reported. Do not read the empty Setup
        Deck above as &ldquo;nothing to trade&rdquo; until this is fixed &mdash;
        this is a failed request, not a quiet market.</div>
      </div>
    </div>`;
  }

  /* Rows expand on click and on Enter/Space, so the reason is reachable
     without a mouse and without a hover-only tooltip. */
  root.addEventListener('click', e => {
    const r = e.target.closest('.wx-data');
    if (!r || e.target.closest('.term')) return;   // let the glossary have its own taps
    const sym = r.dataset.sym;
    const now = !open.has(sym);
    if (now) open.add(sym); else open.delete(sym);
    r.classList.toggle('open', now);
    r.setAttribute('aria-expanded', String(now));
  });
  root.addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const r = e.target.closest('.wx-data');
    if (!r) return;
    e.preventDefault();
    r.click();
  });


  /* The cadence is SSData's now, not this module's. It was the only file
     checking document.hidden; that check is in the layer, so every consumer
     gets it rather than only the one that remembered. Subscribing also means
     this strip repaints from the same /api/weather response any other reader
     saw, instead of one it fetched on a clock of its own. */
  window.SSData.subscribe('/api/weather', (d, err) => {
    if (err) { fail(String(err.message || err)); return; }
    if (!d || !Array.isArray(d.symbols)) return;
    if (!d.symbols.length) {
      fail('the scan universe is empty — no symbol has been admitted yet');
      return;
    }
    render(d);
  }, 30000);
  /* The cycle backdrop is SUPPLEMENTARY, and subscribed SEPARATELY for that
     reason: its failure must never take the strip down with it. The strip
     answers "why is my screen empty?", which is the load-bearing question here.
     A missing backdrop drops one block; a backdrop that could throw into the
     weather's own path would drop the answer. On error `c` is undefined, the
     lede renders nothing, and the strip stands on its own. */
  window.SSData.subscribe('/api/cycles', (c) => {
    cyc = c || null;
    if (lastWeather) render(lastWeather);
  }, 30000);
})();
