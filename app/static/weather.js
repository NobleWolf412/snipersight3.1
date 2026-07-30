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
  const TERMS = [
    [/\bliquidity sweeps?\b/i, 'sweep'],
    [/\bhigher[- ]timeframe\b/i, 'timeframe'],
    [/\btimeframes?\b/i, 'timeframe'],
    [/\bpullbacks?\b/i, 'pullback'],
    [/\breversals?\b/i, 'reversal'],
    [/\bplaybooks?\b/i, 'playbook'],
    [/\btransitions?\b/i, 'transition'],
    [/\branges?\b/i, 'range'],
    [/\bzones?\b/i, 'zone'],
    [/\bregimes?\b/i, 'regime'],
    [/\bsetups?\b/i, 'setup'],
  ];

  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* Underline the first occurrence of each known term so the sentence teaches
     its own vocabulary. First occurrence only: a paragraph with nine dotted
     underlines is decoration, not help. */
  function teach(text) {
    let out = esc(text);
    for (const [re, key] of TERMS) {
      if (!window.GLOSSARY[key]) continue;   // never underline what cannot explain itself
      out = out.replace(re, m => `<span class="term" data-t="${key}">${m}</span>`);
    }
    return out;
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

  function render(d) {
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
