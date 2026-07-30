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
    link.href = '/static/weather.css?v=1';
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

  function cycleLede(c) {
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
    return `<div class="wx-lede">
      <div class="cy-head">
        <span class="t-section">Bitcoin backdrop</span>
        <span class="wx-sub">where the market sits in its own longer rhythm</span>
        <span class="chip">observational</span>
      </div>
      ${rows.join('')}
      <div class="cy-foot">Never consumed by any trading engine — nothing here
        opens, sizes or blocks a trade. Read from
        <b>${esc(c.source_symbol || '—')}</b>, ${esc(String(c.candles || '—'))} daily
        candles${c.last_candle_ts ? ' to ' + D(c.last_candle_ts) : ''} ·
        ${esc(c.algo_version || '')}. A different Bitcoin series gives a slightly
        different reading; this is one series, not a fact about Bitcoin.</div>
    </div>`;
  }

  function render(d) {
    lastWeather = d;
    const rows = showAll ? d.symbols : d.symbols.slice(0, COLLAPSED);
    const hidden = d.symbols.length - rows.length;
    // The sentence that does the actual explaining. Regime eligibility is
    // necessary, not sufficient — price still has to arrive at a zone — and
    // saying so is the difference between "quiet" and "broken".
    const footer = d.n_live === 0
      ? 'No symbol is in a condition any playbook trades right now. An empty ' +
        'Setup Deck is the correct answer to that, not a fault.'
      : `${d.n_live} of ${d.n_total} symbols are in a condition a playbook ` +
        `trades. Even then a setup only appears once price returns to one of ` +
        `that symbol's zones and confirms there, so quiet days are normal.`;

    root.innerHTML = `<div class="panel wx">
      ${cycleLede(cyc)}
      <div class="panel-head">
        <span class="t-section">Market Weather</span>
        <span class="wx-sub">what the market is doing &middot; and whether anything can be traded</span>
        <span class="chip">${d.n_live} of ${d.n_total} tradeable</span>
      </div>
      <div class="wx-body">
        <div class="wx-row wx-head">
          <span class="t-label">Symbol</span>
          ${d.timeframes.map(tf => `<span class="t-label">${esc(tf)}</span>`).join('')}
          <span class="t-label mean">what this means</span>
        </div>
        ${rows.map(rowHtml).join('')}
      </div>
      <div class="wx-foot">
        <p>${teach(footer)} <span style="color:var(--fg-4)">Click a row for the full reason.</span></p>
        ${hidden > 0 || showAll
          ? `<button class="btn" id="wxMore">${showAll ? 'Show fewer' : 'Show all ' + d.n_total}</button>`
          : ''}
        <span class="wx-ver" title="the engine versions that produced these readings">${
          esc(d.regime_version)} &middot; ${esc(d.strategy_version)}</span>
      </div>
    </div>`;

    const more = document.getElementById('wxMore');
    if (more) more.addEventListener('click', () => { showAll = !showAll; render(d); });
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

  async function load() {
    try {
      /* The cycle backdrop is SUPPLEMENTARY. It is fetched alongside the
         weather but its failure must never take the strip down with it — the
         strip answers "why is my screen empty?", which is the load-bearing
         question here. A missing backdrop drops one block; a thrown backdrop
         would drop the answer. */
      fetch('/api/cycles')
        .then(r => (r.ok ? r.json() : null))
        .then(c => { cyc = c; if (lastWeather) render(lastWeather); })
        .catch(() => { /* backdrop absent; the strip stands on its own */ });

      const res = await fetch('/api/weather');
      if (!res.ok) throw new Error('/api/weather → ' + res.status);
      const data = await res.json();
      if (!data || !Array.isArray(data.symbols)) throw new Error('/api/weather returned no symbols');
      if (!data.symbols.length) {
        // An empty universe is a real state, but it is a PIPELINE state, and it
        // must not be dressed up as a calm one.
        fail('the scan universe is empty — no symbol has been admitted yet');
        return;
      }
      render(data);
    } catch (err) {
      fail(String(err && err.message ? err.message : err));
    }
  }

  load();
  // Same cadence as the shell's own refresh loop; skipped while the tab is
  // hidden because a background tab polling a 1GB store buys nothing.
  setInterval(() => { if (!document.hidden) load(); }, 30000);
})();
