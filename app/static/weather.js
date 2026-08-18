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

  /* Second mount, on CHART. The Bitcoin backdrop is the only thing this module
     still draws, and it does not draw it here — see the comment above
     cycleLede(). Optional by design: if the chart surface is absent the module
     still renders its lede and its fallback, it just has nowhere to put the
     backdrop. Never injected, same rule as above. */
  const cycleMount = document.getElementById('cycleRoot');

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

  /* The per-symbol grid that used to live here — the regime cells, their
     bias colouring, the expand-a-row-for-the-reason behaviour — is gone, and
     with it TONE, bias(), shortName(), rowHtml() and the expanded-row set.

     It was not deleted, it MOVED. It listed exactly the markets the
     At-a-level sweep listed, a screen apart, so "what condition is DOGE in
     and is price anywhere near a level in it" took two panels and a
     scroll. Both halves are one card per market in Overwatch now
     (shell.js renderNear), which reads THIS payload out of the shared SSData
     cache — same response, same instant, same words.

     What this module still owns: the sentence that says whether a quiet rail
     is correct, and the Bitcoin backdrop — the first on Command beside the
     rail, the second on Chart beside the decision. */
  let backdropOpen = false;

  /* ---------- Bitcoin cycle backdrop ----------
     The nested-cycle model has been computed and served since S31 and rendered
     nowhere: `/api/cycles` had zero callers in the whole of static/, while
     glossary.js already defined `dcl`, `wcl` and `translation` — someone
     intended this and stopped.

     It renders ONCE, on CHART, and it is BITCOIN ONLY.

     It was on Command, which is the wrong surface for it. Command asks "what
     should I do right now?", and this block cannot answer that by its own
     admission — the footer below says nothing here opens, sizes or blocks a
     trade. Chart asks "is this setup worth taking?", and long-horizon context
     is precisely what that question takes. So it moved to a mount of its own at
     the foot of the chart surface rather than being demoted a second time on a
     surface it never belonged on. Still collapsed, still last, still
     remembering its state.

     The alt basket correlates ~0.65 to BTC at lag 0, which licenses a shared
     BACKDROP and specifically forbids the alternative: a per-symbol cycle stage
     fanned across 33 deck rows would be 33 copies of one reading, each looking
     like independent confirmation. That is the confluence trap the glossary
     already warns about, rebuilt in the UI.

     Every row carries its own evidence class. `mechanical` means arithmetic on
     detected swings; `heuristic` means a community rule of thumb fitted to two
     or three samples. The engine labels these in its own docstring and the
     labels travel with the numbers rather than sitting in a footnote. */
  /* The last /api/cycles payload. `lastWeather` used to sit beside it so the
     backdrop could be redrawn out of render() when cycles arrived second; the
     backdrop no longer renders out of render() at all, so it went. */
  let cyc = null;

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
    /* CLOSED, deliberately. This block is explicitly observational — its own
       footer says nothing here opens, sizes or blocks a trade — and it once
       rendered open, at full height, above the thing it was context FOR.
       Context outranking instruction is exactly backwards. It now starts closed
       wherever it mounts. Nothing is removed: the reader who wants the longer
       rhythm opens it, and it remembers that choice. */
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
    /* "Eligible", the same word Command's tile uses, because the comment above
       is right that this is the same population — and one population under two
       names on two panels of one screen is the exact defect ssdata.js records
       having already cost an investigation once. */
    const footer = d.n_live === 0
      ? 'No eligible market matches an enabled playbook regime. Watching continues.'
      : `${d.n_live} of ${d.n_total} eligible markets match an enabled regime. ` +
        'Entry still requires zone confirmation.';
    /* Said plainly rather than folded into the count above. A watched symbol
       that can never be sized is evidence about a venue, not an opportunity.

       ONE CLAUSE PER STATE, and each one ends. Joining shadow and warming with
       a semicolon read as one fact about one group — "12 more are shadow
       symbols, watched and scored, never sized, and 10 of those are live; 1
       still warming" says, to anyone reading it, that the warming symbol is
       the twelfth shadow. It is not: all twelve shadows are Kraken perps being
       warmed for a venue switch, and the warming one is a separate symbol
       still short of history. Read as a subset, that sentence also loses a
       symbol — 11 of 12 accounted for, and no clue which was missing.

       `other` closes the last hole. The universe holds states beyond these
       three and one of them (REJECTED, below the liquidity floor) appeared in
       no count at all: 18 + 12 + 1 against 32 rows. It is deliberately not
       named "rejected" here — the server counts it as the remainder, so a
       state invented later is reported as unexplained rather than vanishing,
       which is the failure this whole comment exists about. */
    const other = d.n_other || 0;
    const parts = [];
    if (shadow) {
      parts.push(`${shadow} <span class="term" data-t="shadow">shadow</span>`
        + `, measured but never sized${shadowLive ? ` (${shadowLive} live)` : ''}`);
    }
    if (warming) {
      parts.push(`${warming} <span class="term" data-t="warming">warming</span>`);
    }
    if (other) {
      parts.push(`${other} unclassified`);
    }
    const aside = parts.length
      ? `<details class="mission-detail"><summary>Universe details</summary>` +
        `<div>${parts.join(' · ')}</div></details>`
      : '';

    /* THE ANSWER GOES WHERE THE QUESTION IS ASKED.
       This sentence is the only thing on the surface that says whether an
       empty rail is correct or broken, and it used to sit two thousand
       pixels below the empty rail it was explaining. It now renders into
       #missionLede, directly under Trades on now — the operator reads
       "nothing is in a tradeable condition" in the same glance as the
       nothing. Owned here still: one authority, new address. */
    const lede = document.getElementById('missionLede');
    if (lede) {
      lede.innerHTML = `<span class="mission-summary">${teach(footer)}</span>${aside}`;
      lede.className = 'mb-lede' + (d.n_live === 0 ? ' quiet' : '');
    }

    /* NOTHING renders here on a healthy scan, and that is the finished state,
       not an oversight.

       The per-symbol grid became one card per market in Overwatch (shell.js
       renderNear), reading this very payload from the shared cache. The lede
       moved to #missionLede above. The backdrop moved to Chart. What was left
       was a panel head, a subtitle describing a block that is no longer under
       it, and a "N of M tradeable" chip restating the lede's own first clause
       — chrome around an absence, and a second copy of a count that already
       has an authority forty pixels higher up.

       The mount stays because fail() below needs it: a failed request has to
       announce itself on the surface whose quiet it would otherwise be
       mistaken for. Empty on success, loud on failure. */
    root.innerHTML = '';
  }

  /* The backdrop repaints on the CHART mount and on its own data.

     It used to be drawn inside render(), which meant a failed /api/weather
     took the backdrop down with it — the subscription below already declares
     that these two must not be able to fail together, and drawing one from
     the other's handler quietly broke that. Now /api/cycles calls this and
     /api/weather never touches it. Two mounts, two payloads, two failures. */
  function renderBackdrop() {
    if (!cycleMount) return;
    cycleMount.innerHTML = cycleLede(cyc, backdropOpen);
    const cyd = cycleMount.querySelector('.cy-details');
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
        <div>No market condition is being reported. Do not read an empty
        Trades on now above as &ldquo;nothing to trade&rdquo; until this is
        fixed &mdash; this is a failed request, not a quiet market.</div>
      </div>
    </div>`;
  }

  /* The expand-a-row handler went with the rows it operated on. Nothing this
     module renders is expandable any more except the backdrop, which is a
     native <details> and needs no handler.

     The cadence is SSData's now, not this module's. It was the only file
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
     reason: its failure must never take the strip down with it, and — now that
     the two live on different surfaces — the strip's failure must not take the
     backdrop down either. The strip answers "why is my screen empty?", which is
     the load-bearing question. On error `c` is undefined, cycleLede() returns
     the empty string, and each side stands on its own. */
  window.SSData.subscribe('/api/cycles', (c) => {
    cyc = c || null;
    renderBackdrop();
  }, 30000);
})();
