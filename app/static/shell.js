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
  // guards the console poll below, which cannot run until its own state exists
  let consoleReady = false;
  /* `setup` was renamed to `rules` because a SETUP is a trade candidate
     everywhere else in this app. Old hashes are still honoured — a bookmark, a
     link in the wizard's prose, or anything the operator saved must not land on
     a blank screen because we improved a word. */
  const SURFACE_ALIASES = {setup: 'rules'};
  function go(name){
    name = SURFACE_ALIASES[name] || name;
    document.querySelectorAll('.surface').forEach(s => s.classList.toggle('on', s.id === 's' + '-' + name));
    document.querySelectorAll('.nav a').forEach(a => a.classList.toggle('on', a.dataset.s === name));
    if(location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
    // The chart cannot size itself while its surface is display:none, so it is
    // told when it becomes visible rather than measuring a 0x0 box at load.
    if(window.SSChart) name === 'chart' ? SSChart.onShow() : SSChart.onHide();
    // The console polls slowly while it is off screen; arriving on it should
    // not mean waiting out that slow tick for the first paint.
    if(name === 'diagnostics' && consoleReady) pollConsole();
  }
  document.querySelectorAll('.nav a').forEach(a =>
    a.addEventListener('click', e => { e.preventDefault(); go(a.dataset.s); }));
  addEventListener('hashchange', () => go(location.hash.slice(1) || 'command'));
  go(location.hash.slice(1) || 'command');

  /* ---------- clock ---------- */
  setInterval(() => { $('clock').textContent = new Date().toISOString().slice(11, 19) + 'Z'; }, 1000);

  /* ---------- fetch with visible failure ---------- */
  let degraded = false;
  /* Reads go through SSData so this file and funnel.js/chart.js/wizard.js share
     one response per endpoint instead of fetching the same thing on four
     unaligned clocks and then disagreeing about the answer.

     shell.js is the POLLER and defaults to maxAge 0 — always a real request.
     That is deliberate: refresh() is not only the 30s loop, it is also the
     repaint after a scan finishes, after Apply, and after a halt. Serving any
     of those from cache would show the operator the state they just changed
     away from. Everyone else reads with a window and gets these answers free.

     Costs nothing extra: SSData collapses concurrent requests for one path into
     one in-flight promise, which matters more than it sounds — /api/overview
     can take the better part of a minute while the scanner holds the store, and
     four modules asking separately used to mean four overlapping requests
     competing for it. The throw-on-failure contract is unchanged. */
  const api = (path, maxAge) => window.SSData.get(path, maxAge == null ? 0 : maxAge);
  /* ONE severity ladder, ONE colour. The engine already grades every check on
     PASS < DEGRADED < BLOCKED (engine/quality.py ORDER) and this file used to
     re-derive a colour at three call sites from three different predicates.
     That is how `DEGRADED` came to render GREEN in the diagnostics verdict and
     amber in the header at the same instant — the verdict coloured off
     `evaluation_allowed && !blockers`, which is true for the mildest non-clean
     rung, while the text printed `h.status`. Colour and word now share a
     source, and an unknown status can never resolve to green. */
  const TONE_OF_STATUS = {PASS: 'good', DEGRADED: 'warn', BLOCKED: 'bad'};
  const TONE_VAR = {good: 'var(--green)', warn: 'var(--amber)', bad: 'var(--red)'};
  function healthTone(h){
    if(h.pending) return 'warn';              // an audit that has not run is not a pass
    if(!h.evaluation_allowed) return 'bad';
    if((h.blockers || []).length) return 'bad';
    return TONE_OF_STATUS[h.status] || 'warn';
  }

  /* An exception string is not operator copy. `TypeError: Failed to fetch` was
     the ONLY explanation this chip ever offered, in a native tooltip. What an
     operator needs is how many surfaces are stale and how old the numbers still
     on screen are; the stack detail belongs in the console, where it already is.
     The chip carries the count and routes to Diagnostics for the rest. */
  let lastGoodAt = null;
  function ageText(ts){
    if(ts == null) return 'Nothing on this page has loaded successfully yet.';
    const s = Math.round((Date.now() - ts) / 1000);
    const age = s < 90 ? `${s} seconds` : `${Math.round(s / 60)} minutes`;
    return `The numbers still on screen are ${age} old.`;
  }
  function markDegraded(detail, failedCount){
    degraded = true;
    const n = failedCount || 1;
    $('healthOrb').className = 'orb bad';
    $('healthTxt').textContent = 'API DEGRADED';
    $('healthChip').title =
      `${n} ${n === 1 ? 'panel' : 'panels'} on this page could not refresh. ` +
      `${ageText(lastGoodAt)} Click for Diagnostics.`;
    $('healthChip').classList.add('clickable');
    console.warn('[shell] refresh failed:', detail);
  }
  $('healthChip').addEventListener('click', () => go('diagnostics'));

  /* ---------- COMMAND + status bar ---------- */
  /* The last overview payload, so `renderDeck` can tell an unexamined window
     from a quiet market. It needs `scanner.cycles` and the admitted count, and
     re-fetching them there would be a second request for data this function
     already holds — and could disagree with what is on screen. */
  let lastOverview = null;

  async function loadOverview(){
    const o = await api('/api/overview');
    lastOverview = o;
    /* READ the count, do not re-derive it. This filtered `state !== 'WARMING'`
       and rendered 75 while the engine held 19 admitted — because the server
       defaulted every symbol with candles but no universe row to "ADMITTED",
       and the UI's filter was a different definition again. Market Weather
       200px below reported 34 from the universe fact. Three universe sizes on
       one screen. The engine owns this number now (`universe_counts`).

       75 also made "no setups right now" read as a malfunction: 19 symbols
       producing nothing is the ordinary case, 75 producing nothing is not. */
    const uc = o.universe_counts || {};
    $('mUniverse').textContent = uc.admitted ?? '—';
    const sub = [];
    if (uc.shadow) sub.push(`${uc.shadow} shadow`);
    if (uc.warming) sub.push(`${uc.warming} warming`);
    $('mUniverseSub').textContent = sub.length
      ? sub.join(' · ') + ' — never sized'
      : '';

    const active = o.feed.filter(f => f.state === 'VALIDATED' && !f.result);
    $('mSetups').textContent = active.length;
    $('nCommand').textContent = active.length || '';

    // scanner liveness
    const sc = o.scanner || {};
    $('scanOrb').className = 'orb ' + (sc.alive ? 'good' : 'bad');
    // show WHAT it is doing, not just that it lives — the phase comes from the
    // live loop's per-stage heartbeat
    const phase = sc.phase && sc.phase !== 'idle' ? sc.phase.split(' (')[0] : null;
    $('scanTxt').textContent = sc.alive
      ? (phase ? 'SCANNER · ' + phase.toUpperCase() : 'SCANNER LIVE')
      : 'SCANNER DOWN';
    $('scanChip').title = sc.alive
      ? `${sc.phase || 'idle'} · ${sc.cycles || 0} cycles · heartbeat ${sc.age_s}s ago`
      : `no heartbeat for ${sc.age_s == null ? '?' : sc.age_s}s`;

    if(o.baseline){
      $('sbBaseline').textContent = new Date(o.baseline.started_at * 1000).toISOString().slice(0, 10);
      $('baselineChip').textContent = o.baseline.label || 'forward window';
    }
    renderDeck(active, o.rejection_funnel || {});
    renderFunnel(o.rejection_funnel || {});
  }

  /* Higher-timeframe context as a LABEL, never folded into a score.
     Three states, and UNKNOWN is its own — measured on 228 trades, unknown-HTF
     setups ran 38.9% win / +0.404 R against genuinely opposed ones at 17.2% /
     -0.616 R. Showing "not aligned" for a missing measurement would have
     libelled the entire 1D book, which cannot have a 1W regime at all: that
     needs MAJOR-tier weekly swings, and 194 weeks of perp history yields one or
     two per symbol. A gap in the data is not a fact about the trade. */
  function htfChip(s){
    const c = s.confluence || {};
    const state = c.htf_state ||
      (c.htf_regime == null ? 'UNKNOWN'
        : c.htf_regime_aligned == null ? 'UNKNOWN'
        : c.htf_regime_aligned ? 'TRENDING' : 'FLAT');
    const tf = c.htf_timeframe ? c.htf_timeframe + ' ' : '';
    if(state === 'UNKNOWN') return `<span style="color:var(--fg-4)">${tf}not measured</span>`;
    if(state === 'TRENDING') return `<span style="color:var(--green-soft)">${tf}trending</span>`;
    return `<span style="color:var(--fg-3)">${tf}flat</span>`;
  }

  function expiresIn(ts, now){
    if(!ts) return '';
    const m = Math.round((ts - now) / 60);
    if(m <= 0) return 'expiring now';
    if(m < 60) return `expires in ${m}m`;
    const h = Math.round(m / 60);
    return h < 48 ? `expires in ${h}h` : `expires in ${Math.round(h / 24)}d`;
  }

  /* One card per token, ordered by EXPIRY URGENCY — which decision dies first.

     The deck used to sort by `rank`. It no longer does, and the number is no
     longer shown, because `rank` was graded against 228 closed trades and does
     not survive:
       · rank as a whole      r = +0.210  (noise floor +/-0.130)
       · rank minus its HTF term  r = +0.111 — INSIDE the floor
       · that HTF term alone      r = +0.261 — clears it
     86% of the score's spread is its volume (+15) and R:R (+15) terms, neither
     of which clears its own floor. Worse, the composite is NON-MONOTONE: the
     modal bucket (rank 65, 51% of the deck) was the WORST at -0.643 R while
     rank 50 ran +0.027 R. A score that sorts the deck backwards at its own mode
     is not a confidence score, and presenting it as one invites the operator to
     trust an ordering the data contradicts.

     Expiry urgency makes no predictive claim. Setups die after ENTRY_MAX_BARS,
     so "which of these expires first" is operationally true and useful. */
  /* Rejection reasons, made explicable rather than merely lowercased.

     `COOLDOWN(SL,12.0h)` rendered as "cooldown(sl,12.0h)" — a refusal the
     operator had no way to understand, on a guardrail that silently removes
     tradeable setups from the deck. An unexplained refusal is the fastest
     route to someone overriding a rule they do not understand.

     The bracket carries real information (which exit started the rest, and how
     long), so it is kept and spelled out rather than stripped. The glossary
     entry does the rest. */
  function reasonText(reasons){
    if(!reasons || !reasons.length) return 'no reason given';
    return reasons.map(raw => {
      const s = String(raw);
      const m = /^COOLDOWN\(([^,]+),\s*([^)]+)\)$/i.exec(s);
      if(m){
        const exit = m[1].toUpperCase() === 'SL' ? 'a stop-out' :
                     m[1].toUpperCase() === 'TP' ? 'a target' : m[1].toLowerCase();
        return `<span class="term" data-t="cooldown">resting</span> after ${exit} — ${m[2]} left`;
      }
      return s.replaceAll('_', ' ').toLowerCase();
    }).join(', ');
  }

  function renderDeck(setups, funnel){
    const el = $('deck');
    if(!setups.length){
      /* THE EMPTY-WINDOW RULE, site 4 of 4.
         The informative branch was gated on `total > 0`, so on a FRESH
         BASELINE — when nothing has been rejected because nothing has been
         examined — it was unreachable, and the operator got four bare words.
         That is precisely the moment after every rule change, when "no setups
         right now" is most likely to be read as "the scanner is broken".

         Three distinct states, three different messages. Two of them are the
         OPPOSITE of each other and were collapsed into the same sentence:
         a quiet market and an unexamined one. */
      const rows = Object.entries(funnel).sort((a, b) => b[1] - a[1]).slice(0, 3);
      const total = Object.values(funnel).reduce((s, n) => s + n, 0);
      const cycles = (lastOverview && lastOverview.scanner && lastOverview.scanner.cycles) || 0;
      const nSyms = (lastOverview && (lastOverview.universe_counts || {}).admitted) || 0;
      let body;
      if(total){
        body = '<br><span style="color:var(--fg-3)">' + fmt(total) +
          ' candidates rejected since baseline</span><br>' +
          rows.map(([r, n]) => '<span style="color:var(--amber)">' + fmt(n) + '</span> ' +
            r.replaceAll('_', ' ').toLowerCase()).join('<br>');
      } else if(!cycles){
        body = '<br><span style="color:var(--fg-3)">Nothing has been rejected ' +
          'either, because nothing has been examined in this window yet.</span>';
      } else {
        body = '<br><span style="color:var(--fg-3)">' + nSyms + ' symbols scanned. ' +
          'None are in a state any ' +
          '<span class="term" data-t="playbook">playbook</span> has a play for — ' +
          'Market Weather below shows which regimes they are in.</span>';
      }
      el.innerHTML = '<div class="empty">no setups right now' + body + '</div>';
      deckRows.clear();          // the differ's nodes went with that innerHTML
      return;
    }
    const expiry = s => s.expires_at_ts || Infinity;   // no expiry -> sorts last
    const best = new Map();            // symbol -> the one expiring soonest
    for(const s of setups){
      const cur = best.get(s.symbol);
      if(!cur || expiry(s) < expiry(cur)) best.set(s.symbol, s);
    }
    const now = Date.now() / 1000;
    const ordered = [...best.values()].sort((a, b) => expiry(a) - expiry(b));

    /* Keyed diff, because the next click on this surface opens an order ticket.
       This deck used to be replaced wholesale via `innerHTML` every 30s: every
       row was destroyed and rebuilt, and when a setup expired the rows beneath
       it jumped up into the cursor. On the one screen where a misclick sizes
       the wrong trade, the list must not move under the pointer.

       Rows are keyed by symbol — `best` holds one per symbol, so the key is
       stable even when the chosen timeframe or strategy for that symbol
       changes. Survivors keep their node (and their position); a row that
       leaves the payload fades OUT IN PLACE, holding its slot open, so nothing
       below it shifts at the moment the operator is reaching for it. */
    /* The differ only ever APPENDS rows, so the placeholder the markup ships
       with (`loading…`) was never removed on the path where setups exist — it
       sat above the first card until the deck happened to empty out once. */
    el.querySelectorAll(':scope > .empty').forEach(n => n.remove());

    /* The differ APPENDS row nodes; anything else in the container survives
       every render. So the loading skeleton — and the empty state, when a quiet
       market wakes up — must be removed by hand, or they sit ABOVE the first
       real rows forever. This was live: a PF_ZECUSD setup rendered underneath
       the skeleton, and the same hole existed for the old "loading…" div. It
       went unseen because the deck was empty in every test until a real setup
       finally fired. */
    el.querySelectorAll(':scope > .skeleton, :scope > .empty').forEach(n => n.remove());

    const seen = new Set();
    ordered.forEach(s => {
      const key = s.symbol;
      seen.add(key);
      const cls = 'deck-row' + (s.risk && s.risk.decision === 'REJECTED' ? ' dead' : '');
      const html = deckRowInner(s, now);
      let rec = deckRows.get(key);
      if(!rec){
        const node = document.createElement('div');
        node.dataset.deckkey = key;
        node.className = cls;
        node.innerHTML = html;
        rec = {el: node, html, cls};
        deckRows.set(key, rec);
      }else{
        rec.el.classList.remove('expiring');
        if(rec.cls !== cls){ rec.el.className = cls; rec.cls = cls; }
        if(rec.html !== html){ rec.el.innerHTML = html; rec.html = html; }
      }
      el.appendChild(rec.el);          // appendChild MOVES an existing node
    });

    for(const [key, rec] of deckRows){
      if(seen.has(key)) continue;
      if(rec.el.classList.contains('expiring')) continue;   // already fading
      rec.el.classList.add('expiring');
      setTimeout(() => { rec.el.remove(); deckRows.delete(key); }, 900);
    }

    el.querySelectorAll('button[data-sym]').forEach(b => {
      if(b.dataset.wired) return;      // survivors keep their handler
      b.dataset.wired = '1';
      b.addEventListener('click', () => {
        go('chart');
        if(window.SSChart) SSChart.open(b.dataset.sym, b.dataset.tf);
      });
    });
  }

  const deckRows = new Map();          // symbol -> {el, html, cls}

  function deckRowInner(s, now){
    {
      const long = s.direction === 'LONG';
      // The risk authority is the last word on whether a setup is tradeable.
      // Showing a rejected setup as if it were actionable is the worst thing
      // this deck can do — the operator would size a trade the engine refused.
      const r = s.risk;
      const dec = r ? r.decision : null;
      const money = v => v == null ? null : '$' + Number(v).toLocaleString(undefined, {maximumFractionDigits: 0});
      const chip = dec === 'APPROVED' ? 'chip-green' : dec === 'REDUCED' ? 'chip-amber'
                 : dec === 'REJECTED' ? 'chip-red' : '';
      const verdict = dec
        ? `<span class="chip ${chip}">${dec}</span>` +
          (dec === 'REJECTED'
            ? `<div class="t-label" style="margin-top:4px;color:var(--red-2)">${
                reasonText(r.reasons)}</div>`
            : `<div class="t-label" style="margin-top:4px">risks ${money(r.risk_usd) || '—'}${
                r.units ? ' · ' + Number(r.units).toLocaleString() + ' units' : ''}</div>`)
        : '<span class="chip">unsized</span><div class="t-label" style="margin-top:4px">no risk decision</div>';

      // wrapper element and its .dead class are owned by renderDeck's differ;
      // this returns the row's CONTENTS only
      return `
        <div>
          <div class="t-mono" style="font-size:13px;color:var(--fg)">${s.symbol.replace('-USD','')}</div>
          <div class="t-label">${s.tf} · ${s.strategy.replace('_',' ')}</div>
          <!-- The sort key, made visible. A deck ordered by something the
               operator cannot see is worse than one ordered by a bad score. -->
          <div class="t-label" style="color:var(--amber)" title="how long this setup stays live"><span class="term" data-t="horizon">${expiresIn(s.expires_at_ts, now)}</span></div>
        </div>
        <div>
          <span class="chip ${long ? 'chip-green' : 'chip-red'}">${s.direction}</span>
          <div class="t-label" style="margin-top:4px">${htfChip(s)}</div>
        </div>
        <div class="t-mono" style="color:var(--fg-3)">
          entry <b style="color:var(--fg)">${(+s.entry).toLocaleString()}</b> ·
          tp <b style="color:var(--green)">${(+s.tp).toLocaleString()}</b> ·
          sl <b style="color:var(--red-2)">${(+s.sl).toLocaleString()}</b> ·
          <span class="term" data-t="rr">R:R</span> ${s.rr}
          ${s.why ? `<div class="t-body deck-why">${
            window.SSTeach ? window.SSTeach(s.why) : esc(s.why)}</div>` : ''}
        </div>
        <div>${verdict}</div>
        <button class="btn" data-sym="${s.symbol}" data-tf="${s.tf}">Open chart</button>`;
    }
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
    const d = p.decisions || {};

    /* THE EMPTY-WINDOW RULE, site 1 of 4.
       A count of ZERO OBSERVATIONS must never share a treatment with a count
       of zero problems. `up = p.return_pct >= 0` put 0.0 on the POSITIVE
       branch, so a forward window in which the risk authority has not ruled on
       a single setup rendered `+0%` in GREEN with `class="tile up"`. This
       file's own header promises it "never renders a confident-looking zero",
       and a baseline reset is exactly when the operator is most anxious and
       least able to tell a starting value from a result. */
    const ruled = (d.APPROVED || 0) + (d.REDUCED || 0) + (d.REJECTED || 0);
    const up = p.return_pct >= 0;

    $('equityTxt').textContent = money(p.equity);
    $('equityRet').textContent = ruled ? '  ' + (up ? '+' : '') + p.return_pct + '%' : '';
    $('equityChip').title = `account equity (paper) — start ${money(p.start_equity)}, ` +
      `open risk ${money(p.open_risk_usd || 0)}`;
    $('mEquity').textContent = money(p.equity);
    $('rEquity').textContent = money(p.equity);

    if(!ruled){
      // Em-dash, never 0% and never —%. The sub-line carries the denominator.
      $('rReturn').textContent = '—';
      $('rReturn').parentElement.className = 'tile';
      $('rDD').textContent = '—';
      setSub('rReturn', 'no closed trades');
      setSub('rDD', 'no closed trades');
      setSub('rEquity', 'starting balance');
    } else {
      $('rReturn').textContent = (up ? '+' : '') + p.return_pct + '%';
      $('rReturn').parentElement.className = 'tile ' + (up ? 'up' : 'down');
      $('rDD').textContent = (p.max_drawdown_pct ?? '—') + '%';
      setSub('rReturn', ''); setSub('rDD', ''); setSub('rEquity', '');
    }
    $('rHalt').textContent = p.kill_switch_days ?? 0;
    if(p.config) $('mRisk').textContent = money(p.config.next_risk_usd);
    drawCurve(p.curve, p.start_equity);

    const startedAt = (p.baseline || {}).started_at;
    const started = startedAt
      ? new Date(startedAt * 1000).toLocaleDateString(undefined, {day: 'numeric', month: 'short'})
      : null;

    /* THE ERA LABEL. This surface counts ONLY the current forward window;
       Diagnostics counts the whole recorded book. Both are correct and they
       disagree by hundreds of trades, which reads as a broken app unless each
       one says which era it covers and where the other number lives. Stated as
       a headline above the tiles, in the same words the edge panel uses. */
    $('resultsEra').innerHTML =
      `Everything on this page counts the
       <span class="term" data-t="forwardWindow">forward window</span> that opened${
         started ? ' <b>' + started + '</b>' : ''} — not the whole history.
       The full <span class="term" data-t="recordedBook">recorded book</span>,
       across every <span class="term" data-t="baseline">baseline</span>, is measured on
       <a href="#diagnostics" data-era-link="diagnostics">Diagnostics</a>${
         ruled ? '' : ', which is why it can report trades while this page reports none'}.`;
    $('resultsNote').innerHTML = ruled
      ? `Risk authority decisions: <b>${d.APPROVED || 0}</b> approved,
         <b>${d.REDUCED || 0}</b> reduced, <b>${d.REJECTED || 0}</b> rejected.
         Sizing runs at ${p.config ? p.config.risk_pct : '—'}% per trade with a
         ${p.config ? p.config.max_total_risk_pct : '—'}% total cap.
         Everything here is <span class="term" data-t="paper">paper</span>.`
      : `<b>This forward window is empty.</b> It opened${started ? ' ' + started : ''}
         and the risk authority has not ruled on a single setup, so every number
         above is a starting value, not a result.
         Everything here is <span class="term" data-t="paper">paper</span>.`;
  }

  /* Write a tile's sub-line, creating it on first use. The qualifier has to sit
     next to the number it qualifies — a caveat one surface away is not one. */
  function setSub(metricId, text){
    const metric = $(metricId);
    if(!metric) return;
    const tile = metric.parentElement;
    let sub = tile.querySelector('.t-sub');
    if(!sub){
      sub = document.createElement('span');
      sub.className = 't-sub';
      tile.appendChild(sub);
    }
    sub.textContent = text || '';
  }

  /* ---------- RESULTS: curve + per-symbol/strategy breakdown ---------- */
  function drawCurve(curve, start){
    const el = $('eqCurve');
    if(!curve || curve.length < 2){
      el.innerHTML = `<text x="400" y="84" text-anchor="middle" fill="var(--fg-4)"
        font-family="var(--f-mono)" font-size="11">no closed trades in this window yet</text>`;
      $('eqNote').textContent = curve && curve.length === 1
        ? '1 settlement — a curve needs at least two points' : '';
      return;
    }
    const ys = curve.map(p => +p.equity);
    const lo = Math.min(...ys, start), hi = Math.max(...ys, start);
    const pad = (hi - lo) * 0.1 || 1;
    const y = v => 150 - ((v - (lo - pad)) / ((hi + pad) - (lo - pad))) * 140;
    const x = i => (i / (curve.length - 1)) * 800;
    const pts = curve.map((p, i) => `${x(i).toFixed(1)},${y(+p.equity).toFixed(1)}`).join(' ');
    const up = ys[ys.length - 1] >= start;
    const col = up ? 'var(--green)' : 'var(--red-2)';
    el.innerHTML =
      `<line x1="0" y1="${y(start).toFixed(1)}" x2="800" y2="${y(start).toFixed(1)}"
             stroke="var(--fg-4)" stroke-dasharray="3 4" stroke-width="1" opacity=".6"/>
       <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"
                 vector-effect="non-scaling-stroke"/>`;
    $('eqNote').textContent =
      `${curve.length} settlements · start ${money(start)} · peak ${money(hi)} · now ${money(ys[ys.length-1])}`;
  }

  /* `/api/performance` keys every row `key` and reports R as `sum_r`. This read
     was `r[key]` / `r.net_r ?? r.total_r ?? 0` against fields the endpoint has
     never emitted, so every row rendered an em-dash and `+0.00R` in GREEN —
     a -3.91R book displayed as break-even, with `n` correct so the row looked
     alive. A missing number must never default to zero and read as flat. */
  function perfRows(rows){
    if(!rows || !rows.length) return '<div class="empty">no closed trades yet</div>';
    return rows.map(r => {
      const has = r.sum_r !== undefined && r.sum_r !== null;
      const pnl = +r.sum_r;
      const good = pnl >= 0;
      const wr = (r.win_pct ?? null) === null ? '' : `${r.win_pct}% win`;
      return `<div style="display:grid;grid-template-columns:1fr auto auto auto;gap:var(--md);
        align-items:center;padding:8px var(--lg);border-bottom:1px solid var(--border-soft)"
        class="t-mono">
        <span style="color:var(--fg-2)">${String(r.key ?? '—').replace('-USD','')}</span>
        <span style="color:var(--fg-4)">${r.n ?? 0} trades</span>
        <span style="color:var(--fg-4)">${wr}</span>
        <b style="color:${!has ? 'var(--fg-4)' : (good ? 'var(--green)' : 'var(--red-2)')}">${
          has ? `${good ? '+' : ''}${pnl.toFixed(2)}R` : 'n/a'}</b>
      </div>`;
    }).join('');
  }

  /* A SHADOW venue is warmed but never tradeable — `risk.py` refuses every one
     of its intents. Its simulated record is evidence for admitting the venue,
     so it stays visible, but it is fenced off and labelled rather than added
     to the operator's track record. */
  function shadowBlock(rows){
    if(!rows || !rows.length) return '';
    const sum = rows.reduce((a, r) => a + (+r.sum_r || 0), 0);
    const n = rows.reduce((a, r) => a + (r.n || 0), 0);
    return `<details style="border-top:1px solid var(--border-soft)">
      <summary style="padding:8px var(--lg);color:var(--fg-4);cursor:pointer" class="t-mono">
        + ${n} shadow trade${n === 1 ? '' : 's'} (${sum >= 0 ? '+' : ''}${sum.toFixed(2)}R) —
        warmed venue, never tradeable, excluded above</summary>
      ${perfRows(rows)}</details>`;
  }

  async function loadPerformance(){
    const p = await api('/api/performance');
    $('perfSymbol').innerHTML = perfRows(p.by_symbol) + shadowBlock(p.shadow_by_symbol);
    $('perfStrategy').innerHTML = perfRows(p.by_strategy) + shadowBlock(p.shadow_by_strategy);
  }

  /* ---------- DIAGNOSTICS ---------- */
  async function loadHealth(){
    const h = await api('/api/pipeline-health');
    const blockers = (h.blockers || []).length, warns = (h.warnings || []).length;

    /* THE EMPTY-WINDOW RULE, site 3 of 4 — and the most consequential, because
       this orb is always visible and governs trust in every other number.
       `good = h.evaluation_allowed && !blockers` is TRUE while the audit is
       PENDING, because the endpoint reports `evaluation_allowed: true` with
       empty arrays until the first (~72s) pass finishes. An audit that has not
       run was displayed as an audit that passed. The endpoint has always
       shipped `pending: true` and this file ignored it. */
    if(h.pending){
      $('healthOrb').className = 'orb ' + healthTone(h);
      $('healthTxt').textContent = 'AUDITING…';
      $('dVerdict').textContent = 'AUDITING…';
      $('dVerdict').style.color = TONE_VAR[healthTone(h)];
      $('dCounts').textContent = 'the audit has not produced a verdict yet — ' +
        'about a minute on this store. Nothing below has been checked.';
      $('nDiag').textContent = '';
      $('dIssues').innerHTML = '<div class="empty">waiting for the first audit pass</div>';
      return;
    }

    const tone = healthTone(h);
    $('healthOrb').className = 'orb ' + tone;
    $('healthTxt').textContent = h.status;
    $('dVerdict').textContent = h.status + (h.evaluation_allowed ? '' : ' · BLOCKED');
    $('dVerdict').style.color = TONE_VAR[tone];

    /* `DEGRADED · 0 blockers · 92 warnings` reads far worse than the state is.
       The engine already grades severity on a ladder and the UI dropped it:
       SERVE_FLAG is the mildest non-clean rung — data used, with a mark on it,
       nothing held back or switched off. The rung says HOW bad, which is a
       different question from whether it is acceptable, so the colour above
       stays amber and the warning count stays on screen. */
    const RUNG = {
      SERVE: 'served clean', SERVE_FLAG: 'flagged',
      QUARANTINE: 'held back', AUTO_DISABLE: 'switched off', HALT: 'halted',
    };
    const rc = h.rung_counts || {};
    const counted = Object.keys(rc).length
      ? Object.entries(rc).map(([k, v]) => `${RUNG[k] || k.toLowerCase()} ${v}`).join(' · ')
      : `${blockers} blockers · ${warns} warnings`;
    $('dCounts').textContent = h.worst_rung
      ? `worst severity: ${RUNG[h.worst_rung] || h.worst_rung} — ${counted}`
      : counted;
    $('nDiag').textContent = blockers || '';

    /* D5 — a count without a drill-in is an assertion, not diagnostics.
       This panel reported "known venue gaps ×91" and offered no way to see one
       of them, on the surface whose whole question is whether the machine is
       telling the truth. The payload has carried `symbol`, `tf` and `details`
       per finding the entire time; only the aggregate was rendered.

       Each code is now a disclosure holding its own findings. Collapsed by
       default — 93 rows expanded is the wall of numbers the grouping exists to
       avoid — and capped, because a count in the thousands should not try to
       paint thousands of nodes. The cap says how many it is not showing rather
       than silently truncating. */
    const ISSUE_SAMPLE = 40;
    const groups = {};
    for(const c of [...(h.blockers || []), ...(h.warnings || [])]){
      const k = c.code + '|' + c.status;
      (groups[k] = groups[k] || []).push(c);
    }
    const rows = Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
    $('dIssues').innerHTML = rows.length ? rows.map(([k, items]) => {
      const [code, status] = k.split('|');
      const blocked = status === 'BLOCKED';
      const n = items.length;
      const shown = items.slice(0, ISSUE_SAMPLE);
      const where = c => [c.symbol, c.tf].filter(Boolean).join(' ') || c.stage || '—';
      const detail = shown.map(c => `<div class="issue-item">
          <span class="t-mono issue-where">${esc(where(c))}</span>
          <span class="issue-detail">${esc(c.details || c.code || '')}</span></div>`).join('');
      return `<details class="issue">
        <summary class="issue-head">
          <span class="chip ${blocked ? 'chip-red' : 'chip-amber'}">${blocked ? 'blocker' : 'warning'}</span>
          <span class="t-mono" style="color:var(--fg-2)">${code.replaceAll('_', ' ').toLowerCase()}</span>
          <b class="t-mono issue-count">×${n}</b>
        </summary>
        <div class="issue-body">${detail}${
          n > shown.length
            ? `<div class="issue-item issue-more">…and ${n - shown.length} more not listed</div>`
            : ''}</div>
      </details>`;
    }).join('') : '<div class="empty">no open issues</div>';
  }

  /* ---------- SCANNER SETUP: show the real sizing rules, not prose ---------- */
  async function loadRisk(){
    const c = await api('/api/trade-config');
    const pct = v => (v * 100).toFixed(v * 100 % 1 ? 1 : 0) + '%';
    const row = (k, v, note) => `<div><span class="k">${k}</span>` +
      `<span class="v">${v}${note ? ' <span style="color:var(--fg-4)">' + note + '</span>' : ''}</span></div>`;
    $('riskNow').innerHTML =
      row('risk per trade', pct(c.risk_pct)) +
      row('total open risk', pct(c.max_total_risk_pct), `(${c.max_concurrent} × per-trade)`) +
      row('concurrent positions', c.max_concurrent) +
      row('daily loss halt', pct(c.daily_loss_pct)) +
      row('live execution', c.live_enabled ? 'ENABLED' : 'LOCKED') +
      // Per-venue, because the difference is decisive rather than cosmetic:
      // a 0.1%-stop trade nets -7.00R on spot and +2.30R on perps.
      (c.venues || []).map(v => row(
        v.key.replace('-', ' '),
        `${v.allow_shorts ? 'long+short' : 'long only'} · ${v.max_leverage}x`)).join('');
    $('riskVer').textContent = c.cost.version;
  }

  /* ---------- settings: editable, audited, honest about the cost ---------- */
  let setSpec = [], setValues = {}, setPending = {};

  /* An <input> hands back a STRING. The server hands back a typed value. The
     dirty test used to be `pending !== values` — strict — so `max_drawdown_pct`
     came back as "20" against the number 20.0 and never compared equal. The
     effect was not cosmetic: the row stayed lit UNSAVED for the life of the
     tab, `loadSettings` used the same test to retire satisfied edits so it
     never retired that one, and Apply appeared to do nothing. A dirty flag
     that lies is worse than no dirty flag. Coerce to the spec's own type, in
     one place, and compare the coerced values. */
  const specOf = name => setSpec.find(s => s.name === name);
  function coerceSetting(name, raw){
    const s = specOf(name);
    if(!s) return raw;
    if(s.type === 'bool')  return typeof raw === 'boolean' ? raw
      : ['1','true','yes','on'].includes(String(raw).trim().toLowerCase());
    if(s.type === 'int')   { const n = parseInt(raw, 10);   return Number.isNaN(n) ? raw : n; }
    if(s.type === 'float') { const n = parseFloat(raw);     return Number.isNaN(n) ? raw : n; }
    return String(raw);
  }
  const sameSetting = (name, a, b) => coerceSetting(name, a) === coerceSetting(name, b);
  const dirtyKeys = () =>
    Object.keys(setPending).filter(k => !sameSetting(k, setPending[k], setValues[k]));

  const escHtml = s => String(s).replace(/[<>&"]/g, c =>
    ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));

  /* B7 — this page mixes two voices. The prose above these controls is careful
     ("These are the live numbers the risk authority sizes with…") and the
     controls themselves were raw config keys with the underscores knocked out:
     "strategy scale in", "max drawdown pct", "halt on data blocked", "halted".
     A reader has to translate every one of them back into English, on the
     surface that was already the hardest to understand.

     The engine keeps owning the NAMES — these are display labels only, and an
     unmapped key still falls back to the de-underscored form rather than
     disappearing, so adding a setting can never produce a blank row. */
  const SETTING_LABELS = {
    enable_perps: 'Trade perpetual futures',
    top_n: 'How many symbols to admit',
    min_volume_usd: 'Minimum 24h volume',
    strategy_pullback: 'Pullback playbook',
    strategy_reversal: 'Reversal playbook',
    strategy_scale_in: 'Scale-in adds',
    strategy_breakout_retest: 'Breakout-retest playbook',
    strategy_range_fade: 'Range-fade playbook',
    max_drawdown_pct: 'Halt if equity falls this far below its peak',
    halt_on_data_blocked: 'Halt when the data audit is BLOCKED',
    halted: 'Operator halt',
  };
  const settingLabel = name => SETTING_LABELS[name] || name.replaceAll('_', ' ');

  /* Full rebuild. Only ever called when the SHAPE of the spec changes — never
     on a keystroke and never on the refresh tick, both of which used to blow
     away the input under the operator's cursor. See patchSettingsState. */
  function buildSettings(){
    $('setFields').innerHTML = setSpec.map(s => {
      const v = (s.name in setPending) ? setPending[s.name] : setValues[s.name];
      const ctl = s.type === 'bool'
        ? `<input type="checkbox" data-set="${s.name}" ${v ? 'checked' : ''}>`
        : `<input class="t-mono" data-set="${s.name}" value="${escHtml(v)}" style="width:110px">`;
      return `<label class="set-row" data-setrow="${s.name}">
        ${s.type === 'bool' ? ctl : ''}
        <span>
          <span class="t-mono" style="color:var(--fg-2)">${escHtml(settingLabel(s.name))}</span>
          ${s.class === 'BEHAVIOURAL' ? '<span class="chip chip-amber">rule</span>' : ''}
          <span class="t-label" style="display:block;margin-top:2px;text-transform:none;
            letter-spacing:0;color:var(--fg-4)">${escHtml(s.description)}</span>
        </span>
        ${s.type === 'bool' ? '' : ctl}
      </label>`;
    }).join('');
  }

  /* Everything that can change without the control itself changing: the dirty
     ring on a row, the Apply/Discard buttons, the new-forward-window warning.
     Touches attributes only, so a focused input keeps focus and its value. */
  function patchSettingsState(){
    const dirty = dirtyKeys();
    for(const s of setSpec){
      const row = document.querySelector(`[data-setrow="${s.name}"]`);
      if(row) row.classList.toggle('changed', dirty.includes(s.name));
    }
    $('setDirty').hidden = !dirty.length;
    $('setApply').disabled = $('setReset').disabled = !dirty.length;
    const rules = dirty.filter(k => (specOf(k) || {}).class === 'BEHAVIOURAL');
    $('setWarn').hidden = !rules.length;
    if(rules.length) $('setWarn').innerHTML =
      `Changing <b>${escHtml(rules.map(settingLabel).join(', '))}</b> starts a NEW forward window. ` +
      'Your existing record is kept but stops accumulating. Nothing is deleted.';
  }

  // adopt server values into inputs the operator is not editing
  function syncSettingInputs(){
    for(const s of setSpec){
      if(s.name in setPending) continue;              // operator owns this one
      const el = document.querySelector(`[data-set="${s.name}"]`);
      if(!el || el === document.activeElement) continue;
      if(s.type === 'bool') el.checked = !!setValues[s.name];
      else el.value = setValues[s.name];
    }
  }

  let setShape = null;
  async function loadSettings(){
    const d = await api('/api/settings');
    setSpec = d.spec; setValues = d.values;
    // drop pending edits that the server now agrees with — typed comparison,
    // or a float edit is never retired and Apply looks like it did nothing
    for(const k of Object.keys(setPending))
      if(sameSetting(k, setPending[k], setValues[k])) delete setPending[k];

    const shape = setSpec.map(s => s.name).join(',');
    if(shape !== setShape){ buildSettings(); setShape = shape; }
    syncSettingInputs();
    patchSettingsState();
    // guardrails: every gate that can stop new entries, and whether it is armed
    const gr = (k, v, cls) => `<div><span class="k">${k}</span>` +
      `<span class="v ${cls || ''}">${v}</span></div>`;
    const rc = setValues.risk_config || {};
    $('guardRows').innerHTML =
      gr('operator halt', setValues.halted ? 'ENGAGED' : 'armed',
         setValues.halted ? 'bad' : 'good') +
      gr('total drawdown halt', setValues.max_drawdown_pct + '% from peak', 'good') +
      gr('daily loss halt', (rc.daily_loss_pct != null ? rc.daily_loss_pct : 6) + '%', 'good') +
      gr('data-health halt', setValues.halt_on_data_blocked ? 'armed' : 'DISABLED',
         setValues.halt_on_data_blocked ? 'good' : 'warn') +
      gr('max concurrent', rc.max_concurrent != null ? rc.max_concurrent : 2) +
      gr('total open risk', (rc.max_total_risk_pct != null ? rc.max_total_risk_pct : 4) + '%') +
      gr('live execution', 'LOCKED', 'warn');
    $('guardChip').textContent = setValues.halted ? 'halted' : 'armed';
    $('guardChip').className = 'chip ' + (setValues.halted ? 'chip-red' : 'chip-green');

    const halted = !!setValues.halted;
    $('btnHalt').textContent = halted ? 'HALTED' : 'HALT';
    $('btnHalt').className = 'btn ' + (halted ? 'btn-cyan' : 'btn-red');
    $('btnHalt').title = halted
      ? 'new entries are blocked — click to resume'
      : 'stop sizing new entries (open positions still settle)';
    document.body.classList.toggle('is-halted', halted);
  }

  /* `input`, not `change`: the dirty flag should follow typing, not wait for
     blur. The handler patches state and never re-renders — calling the full
     rebuild from here is what used to destroy and recreate the very input the
     operator had just touched, losing focus and caret on every keystroke. */
  document.addEventListener('input', e => {
    const el = e.target.closest('[data-set]');
    if(!el) return;
    const name = el.dataset.set;
    const spec = specOf(name);
    if(!spec) return;
    setPending[name] = coerceSetting(name, spec.type === 'bool' ? el.checked : el.value);
    if(sameSetting(name, setPending[name], setValues[name])) delete setPending[name];
    patchSettingsState();
  });

  async function applySettings(changes, note){
    const r = await fetch('/api/settings', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({changes, note: note || ''})});
    const d = await r.json().catch(() => ({}));
    if(!r.ok) throw new Error(d.detail || ('settings → ' + r.status));
    /* This file reads with maxAge 0 and would repaint correctly on its own, but
       playbooks.js holds the same settings behind a window and would keep
       showing the pre-Apply switch positions. A write invalidates for everyone,
       not just for the writer. A BEHAVIOURAL change also opens a new forward
       window, so the overview and portfolio both stop describing the old one. */
    window.SSData.invalidate('/api/settings');
    window.SSData.invalidate('/api/playbooks');
    if(d.baseline){
      window.SSData.invalidate('/api/overview');
      window.SSData.invalidate('/api/portfolio');
    }
    return d;
  }

  $('setApply').addEventListener('click', async e => {
    const b = e.currentTarget;
    const changes = {};
    for(const k of dirtyKeys()) changes[k] = setPending[k];
    if(!Object.keys(changes).length) return;
    b.disabled = true; b.textContent = 'Applying…';
    try{
      const d = await applySettings(changes, 'scanner setup');
      setPending = {};
      await refresh();
      if(d.baseline) alert('New forward window started (baseline #' + d.baseline.id +
        ').\nYour previous record is retained, but stops accumulating.');
    }catch(err){ markDegraded(String(err)); }
    b.textContent = 'Apply';
    syncSettingInputs(); patchSettingsState();
  });

  $('setReset').addEventListener('click', () => {
    setPending = {}; syncSettingInputs(); patchSettingsState();
  });

  $('btnHalt').addEventListener('click', async e => {
    const b = e.currentTarget, halting = !setValues.halted;
    if(halting && !confirm('Halt the scanner?\n\nNo NEW entries will be sized. ' +
        'Open positions still settle — refusing to close a position is not safety.')) return;
    b.disabled = true;
    try{
      await applySettings({halted: halting}, halting ? 'operator halt' : 'operator resume');
      await loadSettings();
    }catch(err){ markDegraded(String(err)); }
    b.disabled = false;
  });

  /* ---------- credentials: write-only, never displayed ---------- */
  /* This container is rebuilt by a 30s timer. It used to be rebuilt with
     `innerHTML`, which destroyed every <input> inside it — including the one
     the operator was mid-way through typing an API key into. Credential values
     are deliberately never held in JS (write-only, and that is correct), so
     there was no state to restore from: the field simply emptied, silently,
     up to twice a minute while you typed.

     So the rows are built ONCE and thereafter patched. Nothing that owns a
     focused or partially-filled input may be re-rendered wholesale. */
  let credShape = null;                 // venue|field list currently in the DOM

  function buildCredRows(d){
    const venues = Object.keys(d.status);
    $('credFields').innerHTML = venues.map(v => `
      <div style="margin-bottom:var(--md)">
        <div class="t-label" style="margin-bottom:6px">${v.replace('-', ' ')}</div>
        ${d.fields.map(f => `
          <div class="fld-row" style="margin-bottom:6px" data-credrow="${v}|${f}">
            <input type="password" data-cred="${v}|${f}" autocomplete="off">
            <button class="btn" data-credsave="${v}|${f}">Save</button>
            <button class="btn btn-red" data-credclear="${v}|${f}" hidden>Clear</button>
          </div>`).join('')}
      </div>`).join('');
  }

  async function loadCredentials(){
    const d = await api('/api/credentials');
    $('credChip').textContent = d.available ? 'DPAPI' : 'unavailable';
    $('credChip').className = 'chip ' + (d.available ? 'chip-green' : 'chip-red');

    // rebuild only when the set of venues/fields itself changes
    const shape = Object.keys(d.status).sort().join(',') + '::' + d.fields.join(',');
    if(shape !== credShape){ buildCredRows(d); credShape = shape; }

    // patch state per row: placeholder carries "is a key stored", Clear follows it
    for(const v of Object.keys(d.status)){
      for(const f of d.fields){
        const set = d.status[v][f];
        const input = document.querySelector(`[data-cred="${v}|${f}"]`);
        const clear = document.querySelector(`[data-credclear="${v}|${f}"]`);
        if(input) input.placeholder = set ? '•••••••• stored' : f.replace('_', ' ');
        if(clear) clear.hidden = !set;
      }
    }
  }

  document.addEventListener('click', async e => {
    const save = e.target.closest('[data-credsave]');
    const clr = e.target.closest('[data-credclear]');
    if(!save && !clr) return;
    const key = (save || clr).dataset.credsave || (save || clr).dataset.credclear;
    const [venue, field] = key.split('|');
    const input = document.querySelector(`[data-cred="${key}"]`);
    try{
      const body = clr ? {venue, field, clear: true}
                       : {venue, field, value: input ? input.value : ''};
      const r = await fetch('/api/credentials', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const d = await r.json().catch(() => ({}));
      if(!r.ok) throw new Error(d.detail || ('credentials → ' + r.status));
      if(input) input.value = '';        // never leave a secret in the DOM
      window.SSData.invalidate('/api/credentials');
      await loadCredentials();
    }catch(err){ alert('Could not save credential: ' + err.message); }
  });

  /* where candidates die, stage by stage — the operator's debugging view */
  async function loadTelemetry(){
    const t = await api('/api/setup-telemetry?limit=200');
    const stages = t.stages || {}, fails = t.failure_points || {};
    const rows = Object.entries(stages).length ? Object.entries(stages)
      : Object.entries(fails);
    /* THE EMPTY-WINDOW RULE, site 2 of 4.
       `defects ? ... : 'clean'` in green made an EMPTY record set
       indistinguishable from a checked-and-clean one — while the panel body
       directly beneath it said "no candidates recorded in this window yet".
       Chip and body contradicted each other, and the chip is what gets read.
       The denominator IS the caveat: a verdict without one is not a verdict. */
    const n = (t.records || []).length;
    const defects = (t.records || []).reduce((s, r) => s + (r.defect_count || 0), 0);
    if(!n){
      $('telChip').textContent = 'no data';
      $('telChip').className = 'chip';                    // grey: nothing checked
    } else if(defects){
      $('telChip').textContent = defects + ' defects';
      $('telChip').className = 'chip chip-red';
    } else {
      $('telChip').textContent = 'clean · ' + n + ' checked';
      $('telChip').className = 'chip chip-green';
    }
    $('dTelemetry').innerHTML = rows.length
      ? rows.sort((a, b) => b[1] - a[1]).map(([k, n]) =>
          `<div style="display:flex;justify-content:space-between;padding:7px var(--lg);
            border-bottom:1px solid var(--border-soft)" class="t-mono">
            <span style="color:var(--fg-3)">${k.replaceAll('_', ' ').toLowerCase()}</span>
            <b style="color:var(--fg-2)">${fmt(n)}</b></div>`).join('')
      : '<div class="empty">no candidates recorded in this window yet</div>';
  }

  async function loadStatus(){
    const s = await api('/api/status');
    $('sbFacts').textContent = fmt(s.facts);
    $('sbAlgo').textContent = s.algo_version;
  }

  /* ---------- actions ---------- */
  /* ---------- backend console: tail the log both processes write ---------- */
  let logOffset = -1, follow = true, scanning = false;
  const consoleEl = $('console');

  function paint(lines){
    if(!lines.length) return;
    const html = lines.map(ln => {
      const m = ln.match(/^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+(\w+)?\s*(.*)$/);
      if(!m) return `<span class="l-info">${esc(ln)}</span>`;
      const [, ts, lvl, rest] = m;
      const cls = /ERROR/.test(lvl) ? 'l-err' : /WARNING/.test(lvl) ? 'l-warn'
                : /MANUAL SCAN|SETUP FIRED/.test(rest) ? 'l-mark' : 'l-info';
      return `<span class="l-time">${ts.slice(11)}</span> <span class="${cls}">${esc(rest)}</span>`;
    }).join('\n');
    consoleEl.insertAdjacentHTML('beforeend', (consoleEl.dataset.seeded ? '\n' : '') + html);
    consoleEl.dataset.seeded = '1';
    // keep the buffer bounded so a long session cannot eat the tab's memory
    const kids = consoleEl.childNodes;
    while(kids.length > 4000) consoleEl.removeChild(kids[0]);
    if(follow) consoleEl.scrollTop = consoleEl.scrollHeight;
  }
  const esc = s => s.replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));

  let polling = false;
  async function pollConsole(){
    // Two overlapping polls would both fetch from the same logOffset and paint
    // the same lines twice — the click handler's poll races the interval.
    if(polling) return;
    polling = true;
    try{
      /* NOT through SSData, deliberately. This is a cursored stream: the offset
         is different on every call, so every poll would mint a cache entry that
         can never be hit again — an unbounded map, growing twice a second, for
         responses nothing will ever re-read. A cache keyed by URL is the wrong
         shape for a cursor, and `polling` above already does the only
         de-duplication this call needs. */
      const r = await fetch('/api/console?offset=' + logOffset, {cache: 'no-store'});
      if(!r.ok) throw new Error('/api/console → ' + r.status);
      const d = await r.json();
      if(!consoleEl.dataset.seeded) consoleEl.textContent = '';
      logOffset = d.offset;
      paint(d.lines || []);
      const s = d.scan || {}, b = $('btnScan');
      $('consoleState').textContent = s.running ? 'scanning…' : (s.detail || 'idle');
      $('consoleState').className = 'chip ' + (s.running ? 'chip-accent' : '');
      // The backend owns the truth about whether a scan is running, so a page
      // reload mid-scan shows the same button state as the tab that started it.
      b.disabled = !!s.running;
      b.textContent = s.running ? 'Scanning…' : 'Run Scan';
      if(scanning && !s.running){
        // A finished scan changes what every one of these paths says. Drop the
        // cached copies so funnel.js and the chart repaint from the new pass
        // too, rather than waiting out their own windows.
        window.SSData.invalidate('/api/overview');
        window.SSData.invalidate('/api/setup-telemetry');
        window.SSData.invalidate('/api/pipeline-health');
        // AND SAY SO. Run Scan used to show "Scanning…", revert, and change
        // nothing an operator could see — no result, no timestamp, no way to
        // tell a finished scan from a click that missed. An action that reports
        // nothing teaches you to distrust it.
        scanResult(s.detail || 'finished');
        refresh();                                   // just finished — repaint deck
      }
      scanning = !!s.running;
    }catch(err){ /* console is best-effort; the health chip owns API state */ }
    finally{ polling = false; }
  }
  /* Decision Provenance — the second application, loaded on demand.
     diagnostics.html shipped with an ?embed=1 mode that hides its own chrome;
     someone designed it to be embedded here and stopped one step short of
     wiring it. The iframe is src-less in the markup and gets its URL on the
     FIRST open only, so the extra page and its fetches cost nothing until the
     operator actually asks for provenance. */
  const prov = $('provenance');
  if(prov) prov.addEventListener('toggle', () => {
    const f = $('provFrame');
    if(prov.open && f && !f.src) f.src = f.dataset.src;
  });

  $('btnFollow').addEventListener('click', e => {
    follow = !follow;
    e.currentTarget.textContent = follow ? 'Following' : 'Paused';
    e.currentTarget.style.color = follow ? '' : 'var(--fg-4)';
  });

  /* This poll ran every 2s forever — 30 of the ~57 requests a minute this page
     made at idle, most of them for a console that was not on screen. It cannot
     simply stop when the console is hidden, because it also owns Run Scan's
     state on COMMAND and the repaint when a scan finishes. So it adapts:

       · console on screen  — 2s, someone is reading the log
       · a scan is running  — 2s, wherever the operator is standing
       · otherwise          — 15s, just keeping the button honest
       · tab in background  — not at all

     Idle on Command now costs 4 requests a minute instead of 30, and every
     behaviour that depended on the fast tick still has it when it matters. */
  const FAST = 2000, SLOW = 15000;
  function consoleInterval(){
    if(document.hidden) return SLOW;
    if(scanning) return FAST;
    return $('s-diagnostics').classList.contains('on') ? FAST : SLOW;
  }
  (function tick(){
    const wait = consoleInterval();
    setTimeout(async () => {
      if(!document.hidden) await pollConsole();
      tick();
    }, wait);
  })();
  consoleReady = true;
  pollConsole();

  /* ---------- run a real scan ---------- */
  /* Every action reports a RESULT and a TIME. A control that changes nothing
     visible is indistinguishable from one that did not fire, and an operator
     who cannot tell those apart stops trusting the button. */
  function scanResult(text, bad){
    const el = $('scanResult');
    if(!el) return;
    el.textContent = `${text} · ${new Date().toISOString().slice(11, 19)}Z`;
    el.className = 't-mono scan-result' + (bad ? ' bad' : '');
    el.hidden = false;
  }

  $('btnScan').addEventListener('click', async e => {
    const b = e.currentTarget;
    b.disabled = true; b.textContent = 'Scanning…';
    follow = true;
    try{
      const r = await fetch('/api/scan', {method:'POST'});
      const d = await r.json().catch(() => ({}));
      if(r.status === 409){
        $('consoleState').textContent = 'already scanning';
        scanResult('a scan was already running', true);
      }
      else if(!r.ok){
        markDegraded(d.detail || ('scan → ' + r.status));
        scanResult(d.detail || ('scan failed → ' + r.status), true);
      }
      else scanResult('scanning…');
      await pollConsole();
    }catch(err){
      markDegraded(String(err));
      scanResult('could not start a scan', true);
      b.disabled = false; b.textContent = 'Run Scan';
    }
    // the poll loop re-enables the button when the backend reports it finished
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

  /* ---------- refresh loop ---------- */
  async function refresh(){
    const jobs = [loadOverview(), loadPortfolio(), loadHealth(), loadStatus(),
                  loadRisk(), loadSettings(), loadCredentials(), loadPerformance(),
                  loadTelemetry()];
    const results = await Promise.allSettled(jobs);
    const failed = results.filter(r => r.status === 'rejected');
    if(failed.length) markDegraded(failed.map(f => f.reason).join('; '), failed.length);
    else {
      lastGoodAt = Date.now();                    // the age the chip reports when it next fails
      if(degraded){ degraded = false; $('healthChip').classList.remove('clickable'); }
    }                                             // health orb is reset by loadHealth
  }
  refresh();
  setInterval(refresh, 30000);
})();
