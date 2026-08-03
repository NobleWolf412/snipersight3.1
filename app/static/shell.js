/* SniperSight shell — navigation, live wiring, and honest failure.
   Phase 1: the five surfaces exist and COMMAND/RESULTS/DIAGNOSTICS carry real
   data. Chart and settings are stubs until phases 2 and 3.
   Loud-fallback rule: a failed fetch says so on screen; it never renders a
   confident-looking zero. */
(() => {
  const $ = id => document.getElementById(id);
  const fmt = n => Number(n).toLocaleString();
  /* The sign goes OUTSIDE the currency symbol. Naively prefixing '$' produced
     "$-19" for a loss, while chart.js's usd() produced "-$19" and the
     scoreboard hand-rolled "−$19" with a Unicode minus — the same −$19.46
     written three ways on three surfaces of one app. One helper, one form.
     `signedMoney` adds an explicit + for gains, for the places where the
     direction of a number is the point rather than its size. */
  const money = n => (Number(n) < 0 ? '-$' : '$') +
    Math.abs(Number(n)).toLocaleString(undefined, {maximumFractionDigits: 0});
  const signedMoney = n => (Number(n) > 0 ? '+' : '') + money(n);

  /* A PRICE, scaled to the magnitude it trades at. `toLocaleString()` defaults
     to three fraction digits, which on a sub-cent token collapses entry, stop
     and target into the same displayed number — u1000PEPEUSDT's 0.0041588 /
     0.0043328 / 0.0041008 all render "0.004", on the deck row where the
     operator decides whether the trade is worth opening. Module scope because
     the deck, the open-trades panel and the pending rows must all agree; it
     lived inside renderPositions and only that panel was correct. */
  const px = v => {
    const n = +v, a = Math.abs(n);
    const d = a >= 1000 ? 0 : a >= 100 ? 2 : a >= 1 ? 3 : 5;
    return n.toLocaleString(undefined,
      {minimumFractionDigits: d, maximumFractionDigits: d});
  };

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

  /* ═══════════════ ONE DERIVED STATE ═══════════════
     Four surfaces disagreed about whether a position was open. The trace said
     ORDER PLACED / FILLED with no terminal exit; Diagnostics said open=1;
     Command said "0 of 2 slots" and "$0 of $386"; and the Setup Deck still
     showed that same filled position as a pending card labelled EXPIRING NOW.

     The cause was one predicate. The deck filtered on `!f.result`, but
     `result` is the EXEC OUTCOME — it is null for a setup that has been armed
     and filled and simply has not closed yet. So "not finished" was being read
     as "not started".

     A setup has a lifecycle, and exactly one place computes it:

         PENDING  — validated, nothing committed
         ARMED    — an order is resting (portfolio.pending_orders)
         FILLED   — money is in the market (portfolio.active_positions)
         CLOSED   — an exec fact recorded an outcome

     Both payloads key on setup_id, so this is a client-side join and touches
     no engine math. Every surface reads the SAME object; none of them may
     re-derive membership from a payload of its own. */
  const SSState = {
    overview: null,
    portfolio: null,

    put(which, payload){ this[which] = payload; },

    /* setup_id -> the live order/position record, whichever stage it is at.
       Built fresh each call: a stale map here is the bug this replaces. */
    engaged(){
      const p = this.portfolio || {};
      const m = new Map();
      for(const t of (p.pending_orders || []))   m.set(t.setup_id, {stage: 'ARMED',  t});
      for(const t of (p.active_positions || [])) m.set(t.setup_id, {stage: 'FILLED', t});
      return m;
    },

    lifecycleOf(f, eng){
      if(f.result) return 'CLOSED';
      const hit = (eng || this.engaged()).get(f.setup_id);
      return hit ? hit.stage : 'PENDING';
    },

    /* The deck is PENDING setups only. A filled position is not an
       opportunity, and counting down its expiry is describing a decision that
       has already been made. */
    deck(){
      const o = this.overview;
      if(!o || !o.feed) return [];
      const eng = this.engaged();
      return o.feed.filter(f =>
        f.state === 'VALIDATED' && this.lifecycleOf(f, eng) === 'PENDING');
    },

    /* ── ONE SYMBOL VOCABULARY ──
       Five counts were on screen under four different names. These are the
       only words the app uses for a set of symbols, and each is a strict
       subset of the one above it except SHADOW, which is deliberately outside
       the chain: it is warmed and never sizeable.

       Only tiers the ENGINE can actually distinguish are defined here. There
       is no separate WATCHED tier because the engine does not emit one, and
       inventing a denominator it cannot back is how the five-count problem
       started. */
    symbolSets(){
      const o = this.overview || {};
      const uc = o.universe_counts || {};
      return {
        stored:    (o.symbols || []).length,      // every symbol with candles
        admitted:  uc.admitted ?? 0,              // in the tradeable universe
        tradeable: uc.admitted ?? 0,              // admitted and not warming
        warming:   uc.warming ?? 0,               // admitted, not yet sizeable
        shadow:    uc.shadow ?? 0,                // warmed, never sizeable
      };
    },
  };
  // exposed so tests and other modules read the same derivation, never a copy
  window.SSStateView = SSState;

  /* Three missed minutes is behind rather than merely late: a 60s cycle that
     has not reported in three of them is not going to catch up on its own. */
  const STALE_AFTER_S = 180;

  /* ═══════════════ ONE CLOCK ═══════════════
     Four components each wrote their own staleness grammar: the header said
     "last checked just now", the scanner banner showed a raw timestamp ten
     minutes old, the footer said "a minute ago", and the chart flipped between
     "JUST NOW" and "UPDATED 30S AGO" — four vocabularies for one fact, two of
     them contradicting each other on screen at the same moment.

     One function, one grammar, exported so chart.js uses it too. The buckets
     are deliberately coarse and never show seconds: a value that changes every
     second is a value that reflows a layout every second, which is the other
     half of this bug (see the fixed-width rule in ss.css). */
  const agoText = s =>
    s == null   ? 'a while ago' :
    s < 45      ? 'just now' :
    s < 90      ? 'a minute ago' :
    s < 3600    ? Math.round(s / 60) + ' minutes ago' :
                  Math.round(s / 3600) + ' hours ago';
  window.SSClock = {
    ago: agoText,
    STALE_AFTER_S,
    /* Age in seconds from an epoch-seconds stamp, floored at zero — a clock
       skew between server and browser must never render as "in 3 seconds". */
    ageOf: ts => ts == null ? null : Math.max(0, Date.now() / 1000 - ts),
  };

  /* ═══════════════ ONE ROUNDING POLICY PER UNIT ═══════════════
     Risk-per-trade appeared as $193, $195, 194.68 and $194 on four surfaces —
     the same number, formatted four ways, which reads as four numbers. One
     rule per unit, defined here and used everywhere:

         money  0dp        R  2dp        percent  1dp
         price  by magnitude (px, below — stands in for venue tick size)
         units  4sf        (stands in for venue lot size)

     px and money already live at module scope; these complete the set. R is
     2dp because the engine quantises r_multiple to 2dp and a third digit
     would be inventing precision the fact store does not carry. */
  const rr = v => v == null || isNaN(+v) ? '—'
    : (+v >= 0 ? '+' : '') + (+v).toFixed(2) + 'R';
  const pct = v => v == null || isNaN(+v) ? '—' : (+v).toFixed(1) + '%';
  /* Units are a venue lot size the browser does not know, so this uses
     significant figures rather than pretending to a tick: "908.979 units" was
     a raw float dump, and neither 908.979 nor 909 is knowably right. */
  const units = v => v == null || isNaN(+v) ? '—'
    : (+v).toLocaleString(undefined, {maximumSignificantDigits: 4});
  window.SSFormat = {money, signedMoney, px, rr, pct, units};

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
    SSState.put('overview', o);
    /* Every count names the SET it belongs to. "15 symbols" on its own was
       unanswerable: fifteen out of what, and fifteen that can do what? */
    const sets = SSState.symbolSets();
    $('mUniverse').textContent = sets.tradeable;
    const sub = [`of ${sets.stored} stored`];
    if (sets.warming) sub.push(`${sets.warming} warming`);
    if (sets.shadow)  sub.push(`${sets.shadow} shadow — never sized`);
    $('mUniverseSub').textContent = sub.join(' · ');

    /* The deck comes from the shared selector, so a filled position leaves it
       the moment the portfolio says the money is in the market — rather than
       sitting here counting down an expiry that no longer applies. */
    SSState.put('overview', o);
    const active = SSState.deck();
    $('mSetups').textContent = active.length;
    $('nCommand').textContent = active.length || '';

    /* Scanner state, said as what it means for a trade rather than as a
       progress report on a backend loop.

       `SCANNER · IMPORT BTCUSDT (3/19)` narrated the import stage in the one
       strip that is on screen whichever surface you are on, and it changed
       every few seconds — constant motion in the top bar reads as alarm from
       the corner of the eye, on a chip whose job is to be ignorable until
       something is actually wrong. Which symbol is being imported is not a
       fact a trader can act on; whether the engine is still watching, and
       whether what is on screen is current, are the only two that are. */
    const sc = o.scanner || {};
    const fresh = sc.alive && sc.age_s != null && sc.age_s < STALE_AFTER_S;
    const tone  = !sc.alive ? 'bad' : fresh ? 'good' : 'warn';
    $('scanOrb').className = 'orb ' + tone;
    $('scanTxt').textContent = sc.alive
      // names the SET, so the number is answerable without opening a tooltip
      ? (sets.tradeable ? `WATCHING ${sets.tradeable} TRADEABLE` : 'WATCHING')
      : 'NOT WATCHING';
    $('scanChip').title = !sc.alive
      ? 'The engine has stopped watching. No new setups will appear until it restarts.'
      : fresh
        ? `The engine is watching for setups. Last checked ${agoText(sc.age_s)}.`
        : `The engine is behind — last checked ${agoText(sc.age_s)}. ` +
          'Setups and prices on screen may be out of date.';

    // The same two facts restated along the bottom, so they are answerable
    // from Chart or Rules without looking up at the header.
    $('sbOrb').className = 'orb ' + tone;
    $('sbLive').textContent = !sc.alive ? 'Not watching'
      : fresh ? 'Watching the market' : 'Catching up';
    // names the set, like every other count on screen
    $('sbWatch').textContent = sc.alive && sets.tradeable
      ? `${sets.tradeable} tradeable · checked ${agoText(sc.age_s)}`
      : '';

    if(o.baseline){
      $('baselineChip').textContent = o.baseline.label || 'forward window';
    }
    renderDeck(active, o.rejection_funnel || {});
    renderRadar(o.approaching, o.prox_atr);
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

  /* When the engine found this — the question the deck could not answer.
     A card with an expiry but no birth time reads as timeless, and "is this
     fresh or have I been staring at it for a day?" decides whether the entry
     is still worth taking. armed_at is the moment the paper order went live;
     the confirming-bar close is the fallback for cards not yet armed. */
  function foundAgo(s, now){
    const ts = s.armed_at || s.confirmed_bar_ts || s.market_time;
    if(!ts) return '';
    const m = Math.round((now - ts) / 60);
    if(m < 1) return 'found just now';
    if(m < 60) return `found ${m}m ago`;
    const h = Math.round(m / 60);
    return h < 48 ? `found ${h}h ago` : `found ${Math.round(h / 24)}d ago`;
  }
  function foundTitle(s){
    const ts = s.armed_at || s.confirmed_bar_ts || s.market_time;
    return ts ? 'found ' + new Date(ts * 1000).toLocaleString() : '';
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
  /* The sentence for a refusal comes from the shared dictionary in funnel.js,
     which already carries one for every code the engine can emit.

     Three surfaces lowercased the raw code instead, so the deck said
     "stop beyond liquidation(0.4412" and the Command tile said "no eligible
     playbook" while Diagnostics — the surface a trader has least reason to
     open — said both of them in English. The translation existed; only its
     distribution was inverted.

     Guarded exactly the way wizard.js guards it: funnel.js is deferred, so a
     dictionary that has not loaded yet must degrade to the old text rather
     than throw on the surface that renders first. */
  const plainReason = c => window.SSFunnel
    ? SSFunnel.plain(c) : String(c).replace(/_/g, ' ').toLowerCase();

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
      return plainReason(s);
    }).join(', ');
  }

  function renderDeck(setups, funnel){
    lastDeckArgs = [setups, funnel];
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
        body = '<br><span style="color:var(--fg-3)">The engine looked at ' +
          fmt(total) + ' chances in this window and passed on every one. ' +
          'The most common reasons:</span><br>' +
          rows.map(([r, n]) => '<span style="color:var(--amber)">' + fmt(n) + '</span> ' +
            plainReason(r)).join('<br>');
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
      /* Keyed by TOKEN, not by symbol. The header promises "One per token"
         and the deck was showing PF_UNIUSD and UNIUSDT — the same coin on two
         venues — as two near-identical cards, because a venue prefix or a
         quote suffix made them different keys. The surviving card names its
         venue, so the split is stated rather than duplicated. */
      const key = tokenOf(s.symbol);
      const cur = best.get(key);
      if(!cur || expiry(s) < expiry(cur)) best.set(key, s);
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
      const held = heldSids.has(s.setup_id || '') || pendSids.has(s.setup_id || '');
      const done = doneSids.has(s.setup_id || '');
      const cls = 'deck-row' + (s.risk && s.risk.decision === 'REJECTED' ? ' dead' : '')
                + (held ? ' held' : done ? ' done'
                   : heldSyms.has(s.symbol) ? ' held-sym' : '');
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
        if(b.dataset.copilot){
          if(window.SSCopilot)
            SSCopilot.open({symbol: b.dataset.sym, tf: b.dataset.tf,
                            setupId: b.dataset.sid || null});
          return;
        }
        go('chart');
        if(window.SSChart) SSChart.open(b.dataset.sym, b.dataset.tf);
      });
    });
    /* The verdict is a claim; the trace is its evidence. SSTracer has existed
       since Wave 3.5 and NOTHING opened it — a drawer that answers "why did
       this trade / why was this refused" gate by gate, wired to no click.
       The verdict cell is now that click. */
    el.querySelectorAll('[data-trace]').forEach(d => {
      if(d.dataset.wired || !d.dataset.trace) return;
      d.dataset.wired = '1';
      activatable(d);
      d.addEventListener('click', () => {
        if(window.SSTracer) SSTracer.open(d.dataset.trace);
      });
    });
  }

  /* Makes a non-button element genuinely operable rather than merely
     clickable. Every trace opener was a bare <div> with a click handler, so
     the drawer that answers "why was this trade taken / why was it refused"
     — the most explanatory thing in the app — could not be reached at all
     without a mouse. One helper, so the next element that opens something
     cannot forget half of it. */
  function activatable(el){
    if(!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    if(!el.hasAttribute('role')) el.setAttribute('role', 'button');
    if(el.dataset.keyed) return;
    el.dataset.keyed = '1';
    el.addEventListener('keydown', e => {
      if(e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();                       // Space must not scroll
      el.click();
    });
  }

  const deckRows = new Map();          // token -> {el, html, cls}

  /* The COIN behind a venue's symbol. `PF_UNIUSD` (Kraken perp), `UNIUSDT`
     (Phemex perp) and `UNI-USD` (Coinbase spot) are three listings of one
     token, and the deck promises one card per token. Venue prefix, quote
     suffix and separator all come off; what is left is the thing being
     traded. Deliberately narrow — it strips only the forms this app actually
     admits, so an unfamiliar symbol keeps its own identity rather than being
     silently merged with something else. */
  const tokenOf = sym => String(sym || '')
    .replace(/^PF_/, '')                 // Kraken perp prefix
    .replace(/[-_/]/g, '')               // separators
    .replace(/(USDT|USDC|USD)$/, '')     // quote currency
    || String(sym || '');

  /* WHAT THE OPERATOR IS ALREADY IN, indexed for the deck.

     A setup card and an open position are the same trade seen at two moments:
     the plan the engine cleared, and the money that went in on it. The deck
     never said so, so UNIUSDT sat there reading like an untaken opportunity
     while the operator held it — and clicking "Open chart" landed on a
     position editor they had no reason to expect.

     Two different claims, deliberately kept apart:
       · by setup_id — THIS card is the trade you are in. Exact.
       · by symbol   — a DIFFERENT setup on a market you already hold. The deck
         keeps one card per symbol and picks the soonest to expire, so the card
         on screen is often not the one that was entered. Arming it would stack
         exposure on a name you are already exposed to, which is the thing the
         operator most needs told before they click, not after. */
  let heldSids = new Set();            // setup_id -> filled position
  let pendSids = new Set();            // setup_id -> order placed, not filled
  let heldSyms = new Map();            // symbol -> {direction, tf, kind}
  let doneSids = new Map();            // setup_id -> the operator's own exit
  let lastDeckArgs = null;             // so a change in the book can repaint

  function indexHeld(p){
    const sids = new Set(), pend = new Set(), syms = new Map();
    /* Setups the operator has already finished with. `operator_closed` has
       been in this payload all along and reached no surface: a trade you took
       and closed leaves its card sitting in the deck looking exactly like one
       you never touched, so the deck's answer to "should I take this" omitted
       the fact that you already did — and what it paid. */
    const done = new Map();
    for(const o of (p.operator_closed || []))
      if(o.setup_id) done.set(o.setup_id, o);
    for(const t of (p.active_positions || [])){
      if(t.setup_id) sids.add(t.setup_id);
      syms.set(t.symbol, {direction: t.direction, tf: t.tf, kind: 'open'});
    }
    for(const t of (p.pending_orders || [])){
      if(t.setup_id) pend.add(t.setup_id);
      // A filled position outranks a resting order on the same name: it is the
      // stronger claim and must not be overwritten by iteration order.
      if(!syms.has(t.symbol))
        syms.set(t.symbol, {direction: t.direction, tf: t.tf, kind: 'pending'});
    }
    const sig = JSON.stringify([[...sids].sort(), [...pend].sort(),
                                [...syms.keys()].sort(), [...done.keys()].sort()]);
    if(sig === indexHeld.sig) return;
    indexHeld.sig = sig;
    heldSids = sids; pendSids = pend; heldSyms = syms; doneSids = done;
    /* The deck and the portfolio arrive on separate payloads, so whichever
       lands second would otherwise paint a deck that disagrees with the book
       until the next poll — a full cycle of "you are not in this" on a trade
       that just opened. Repaint from the cached args instead. */
    if(lastDeckArgs) renderDeck(lastDeckArgs[0], lastDeckArgs[1]);
  }

  /* The banner a held card wears, or ''. */
  function heldBadge(s){
    const sid = s.setup_id || '';
    if(heldSids.has(sid))
      return '<div class="deck-held">in this trade — you are holding it now</div>';
    if(pendSids.has(sid))
      return '<div class="deck-held pend">order resting on this — not filled yet</div>';
    const d = doneSids.get(sid);
    if(d){
      if(d.event === 'ADOPTED')
        return '<div class="deck-held done">you took custody of this — your exit, ' +
               'not the engine’s</div>';
      // What it paid, on the card. "You closed this" without the number sends
      // the operator to Results to answer the obvious next question.
      // signedMoney/money are the ONE currency formatter on this surface; a
      // second one here is how two panels come to disagree about a minus sign.
      const r = d.r_at_close == null ? null : Number(d.r_at_close);
      const usd = d.usd_at_close == null ? null : Number(d.usd_at_close);
      return '<div class="deck-held done">you closed this' +
        (r == null ? '' : ' — ' + rr(r)) +
        (usd == null ? '' : ` (${signedMoney(usd)})`) +
        (d.exit_price ? ` at ${esc(d.exit_price)}` : '') + '</div>';
    }
    const h = heldSyms.get(s.symbol);
    if(h)
      return `<div class="deck-held other">already ${h.kind === 'open' ? 'in' : 'bidding'} ${
        esc(s.symbol.replace('-USD', ''))} — ${esc(h.direction || '')} on ${esc(h.tf || '')}${
        h.direction && s.direction && h.direction !== s.direction
          ? ' · this card is the other way' : ''}</div>`;
    return '';
  }

  /* The engine's enums, said the way a trader would say them. Both maps fall
     back to the de-underscored code, so a playbook or decision added to the
     engine can never render a blank cell here — it just reads plainer once
     someone adds a line. */
  const DECISION_LABELS = {
    APPROVED: 'CLEARED', REDUCED: 'REDUCED SIZE', REJECTED: 'NOT TRADED'
  };
  const PLAYBOOK_LABELS = {
    PULLBACK: 'pullback', REVERSAL: 'reversal', SCALE_IN: 'scale-in add',
    BREAKOUT_RETEST: 'breakout retest', RANGE_FADE: 'range fade'
  };
  const playbookLabel = k =>
    PLAYBOOK_LABELS[String(k).toUpperCase()] || String(k).replace(/_/g, ' ').toLowerCase();

  /* ---------- the trade story ----------
     The engine composes its rationale server-side into one ` · `-joined line:

       "TRANSITION regime · reversal off DEMAND zone 451.40-452.18 · confirmed
        by a close back above the zone on 3.78x volume · TP 479.21 · R:R 2.76"

     Every clause in that is a separate thing a trader weighs — what the market
     was doing, which level, what confirmed it, where it is aimed — and run
     together they read as one machine sentence that nobody finishes. The parts
     arrive already delimited, so they are split back apart and labelled with
     the question each one answers.

     A clause that matches no label keeps its place unlabelled rather than
     being dropped: a rationale that silently loses a line is worse than one
     that reads slightly flat. */
  /* Order is significant, and the specific patterns come first: the
     confirmation clause reads "confirmed by a close back above the ZONE", so
     a /zone/ test placed above /confirm/ swallows it and labels the trigger
     as the level it fired at. */
  const WHY_LABELS = [
    [/confirm/i,                             'Confirmation'],
    [/sweep|liquidity/i,                     'Trigger'],
    [/^TP\b/i,                               'Target'],
    [/^R:R\b/i,                              'Reward'],
    [/cost|fee|slippage/i,                   'Costs'],
    [/\bregime\b/i,                          'Trend'],
    [/\bagrees\b|\bopposes\b|^\d+[DWHM]\b/i, 'Higher timeframe'],
    [/\bzone\b/i,                            'Zone']
  ];
  const whyLabel = seg => (WHY_LABELS.find(([re]) => re.test(seg)) || [])[1] || '';

  function storyOf(s){
    if(!s.why) return '';
    const teach = t => window.SSTeach ? window.SSTeach(t) : esc(t);
    // The headline claims nothing the engine did not state outright.
    const regime = String(s.regime || '').replace(/_/g, ' ').toLowerCase();
    const head = `A ${playbookLabel(s.strategy)} ` +
      (s.direction === 'LONG' ? 'long' : 'short') +
      (regime ? ` in a ${regime} market` : '') + '.';
    const rows = String(s.why).split(' · ').map(x => x.trim()).filter(Boolean)
      .map(seg => `<div class="why-row"><span class="why-k">${whyLabel(seg)}</span>` +
                  `<span class="why-d">${teach(seg)}</span></div>`).join('');
    return `<div class="t-body deck-why">${esc(head)}</div>
      <details class="deck-story"><summary>Why this trade</summary>
        <div class="why-rows">${rows}</div></details>`;
  }

  function deckRowInner(s, now){
    {
      const long = s.direction === 'LONG';
      // The risk authority is the last word on whether a setup is tradeable.
      // Showing a rejected setup as if it were actionable is the worst thing
      // this deck can do — the operator would size a trade the engine refused.
      const r = s.risk;
      const dec = r ? r.decision : null;
      /* Only a FILLED position turns the chart into a position editor —
         /api/manual/open returns `engine` from active_positions alone. A
         resting order must not promise "Manage trade" and then hand back a
         planning ticket. */
      const mine = (heldSyms.get(s.symbol) || {}).kind === 'open'
                && !doneSids.has(s.setup_id || '');
      /* Delegates to the shared formatter rather than re-implementing it, so a
         negative can never render one way here and another way on Results.
         The null case stays local: an unsized setup must read "—", and the
         shared helper would turn null into "$0", which is a different claim. */
      const moneyOr = v => v == null ? null : money(v);
      const chip = dec === 'APPROVED' ? 'chip-green' : dec === 'REDUCED' ? 'chip-amber'
                 : dec === 'REJECTED' ? 'chip-red' : '';
      const verdict = dec
        ? `<span class="chip ${chip}">${DECISION_LABELS[dec] || dec}</span>` +
          (dec === 'REJECTED'
            ? `<div class="t-label" style="margin-top:4px;color:var(--red-2)">${
                reasonText(r.reasons)}</div>`
            : `<div class="t-label" style="margin-top:4px">risks ${moneyOr(r.risk_usd) || '—'}${
                r.units ? ' · ' + Number(r.units).toLocaleString() + ' units' : ''}</div>`)
        : '<span class="chip">awaiting decision</span>' +
          '<div class="t-label" style="margin-top:4px">the risk rules have not ruled on this one yet</div>';

      // wrapper element and its .dead class are owned by renderDeck's differ;
      // this returns the row's CONTENTS only
      return `
        ${heldBadge(s)}
        <div>
          <div class="t-mono" style="font-size:13px;color:var(--fg)">${s.symbol.replace('-USD','')}</div>
          <div class="t-label">${s.tf} · ${playbookLabel(s.strategy)}</div>
          <div class="t-label" title="${foundTitle(s)}">${foundAgo(s, now)}</div>
          <!-- The sort key, made visible. A deck ordered by something the
               operator cannot see is worse than one ordered by a bad score. -->
          <div class="t-label" style="color:var(--amber)" title="how long this setup stays live"><span class="term" data-t="horizon">${expiresIn(s.expires_at_ts, now)}</span></div>
        </div>
        <div>
          <span class="chip ${long ? 'chip-green' : 'chip-red'}">${s.direction}</span>
          <div class="t-label" style="margin-top:4px">${htfChip(s)}</div>
        </div>
        <div class="t-mono" style="color:var(--fg-3)">
          entry <b style="color:var(--fg)">${px(s.entry)}</b> ·
          tp <b style="color:var(--green)">${px(s.tp)}</b> ·
          sl <b style="color:var(--red-2)">${px(s.sl)}</b> ·
          <span class="term" data-t="rr">R:R</span> ${s.rr}
          ${storyOf(s)}
        </div>
        <div class="traceable" data-trace="${esc(s.setup_id || '')}"
             title="click for the gate-by-gate story: the zone, the confirmation, every rule it passed or failed">${verdict}</div>
        <button class="btn" data-copilot="1" data-sym="${s.symbol}" data-tf="${s.tf}"
                data-sid="${esc(s.setup_id || '')}"
                title="ask the copilot about this setup — it reads the trace and cannot arm">Ask copilot</button>
        <button class="btn${mine ? ' btn-amber' : ''}" data-sym="${s.symbol}" data-tf="${
          mine ? heldSyms.get(s.symbol).tf : s.tf}"
                title="${mine ? 'open the chart on the trade you are holding — the ticket manages it'
                              : 'open this plan on the chart'}">${
          mine ? 'Manage trade' : 'Open chart'}</button>`;
    }
  }

  function renderFunnel(funnel){
    const rows = Object.entries(funnel).sort((a, b) => b[1] - a[1]);
    $('dFunnel').innerHTML = rows.length
      ? rows.map(([r, n]) => `<div style="display:flex;justify-content:space-between;padding:3px 0"
            class="t-mono"><span style="color:var(--fg-3)" title="${esc(r)}">${plainReason(r)}</span>
            <b style="color:var(--amber)">${fmt(n)}</b></div>`).join('')
      : '<span class="t-mono" style="color:var(--fg-4)">no rejections recorded yet</span>';
  }

  /* Approaching: setups still FORMING — price closing on a zone, no verdict
     yet. The engine sends these to desktop notifications and the feed drops
     them (it is VALIDATED-only by construction), so the cockpit never showed
     the one signal that says what might happen NEXT.

     The sentence is composed from the payload's structured fields, not from
     its machine `why` line ("price 1.8 ATR from DEMAND zone … · prospective
     PULLBACK would pass all gates · watching") — the zone bounds are the only
     thing lifted out of it, because they exist nowhere else on the payload.

     The meter maps distance in ATR onto the zone-search radius (3 ATR): full
     means price is at the zone's edge. Watch-only: nothing here can be armed,
     so the only control is the chart. */
  function renderRadar(list, prox){
    const panel = $('radarPanel'), box = $('radar');
    list = list || [];
    if(!list.length){ panel.style.display = 'none'; box.innerHTML = ''; return; }
    panel.style.display = '';
    $('radarCount').textContent = list.length + ' near a zone';
    box.innerHTML = list.map(s => {
      const long = s.direction === 'LONG';
      const d = parseFloat(s.distance_atr);
      /* Scaled against the engine's OWN proximity bound (setups.PROX_ATR, sent
         on the payload), not against draft.py's 3-ATR search radius — a
         constant from a different feature that happened to be nearby. With
         the wrong divisor the bar only ever occupied 67–96% of its track, so
         the farthest setup the engine can report looked near-identical to one
         sitting on the zone, and the proportional encoding said nothing. */
      const bound = +prox || 1;
      const fill = isNaN(d) ? 10 : Math.max(8, Math.min(96, (1 - d / bound) * 100));
      /* The figure is a one-shot measurement taken when the setup armed and is
         never refreshed, so it is dated rather than asserted in the present
         tense — "0.5 ATR away when it armed, 3d ago" is true; "0.5 ATR away"
         about a 28-day-old fact is not. */
      const agoTxt = s.measured_at
        ? ' when it armed, ' + agoText(Math.max(0, Date.now() / 1000 - s.measured_at))
        : '';
      const zm = /\b(SUPPLY|DEMAND) zone ([\d.,]+-[\d.,]+)/.exec(s.why || '');
      const zone = zm ? `${zm[1].toLowerCase()} at ${zm[2]}` : 'a zone the engine is watching';
      const verb = long ? 'Pulling back toward' : 'Rising into';
      return `<div class="radar-row">
        <div>
          <div class="radar-sym">${esc(String(s.symbol).replace('-USD',''))}</div>
          <div class="t-label" style="margin-top:3px">${s.tf} · ${long ? 'long' : 'short'} · ${playbookLabel(s.strategy)}</div>
        </div>
        <div>
          <div class="radar-say">${verb} <b>${esc(zone)}</b>. Becomes a trade only if price
            gets there and a candle confirms.</div>
          <div class="radar-meter"><i style="width:${fill.toFixed(0)}%"></i></div>
        </div>
        <div class="radar-dist">${isNaN(d) ? '—' : d.toFixed(1)}<span class="t-sub">ATR away${esc(agoTxt)}</span>
          <button class="btn" style="margin-top:6px" data-rsym="${esc(s.symbol)}" data-rtf="${esc(s.tf)}">Chart</button></div>
      </div>`;
    }).join('');
    box.querySelectorAll('button[data-rsym]').forEach(b =>
      b.addEventListener('click', () => {
        go('chart');
        if(window.SSChart) SSChart.open(b.dataset.rsym, b.dataset.rtf);
      }));
  }

  /* Open trades, drawn on the surface that asks what to do next.

     `active_positions` has been in the portfolio payload the whole time and
     reached no surface at all: an open trade appeared only inside the chart's
     order ticket, and only while you happened to be looking at that symbol's
     chart. "What am I in right now" cost one navigation per position.

     One last close per open symbol is what turns a plan into a position — it
     says whether the trade is winning and how far it is from either end. A
     price that will not load costs that row its marker, never the row. */
  async function renderPositions(p){
    const panel = $('posPanel'), box = $('positions');
    const list = p.active_positions || [];
    /* Armed orders that have not filled yet. Same payload, same builder — the
       only difference is the order event (PLACED vs FILLED) — and they reached
       no surface either. An armed order is money committed to a price: it is
       holding a slot and it will become a position without asking again, so
       leaving it invisible meant the deck could look idle while two orders sat
       waiting to fire. */
    const pending = p.pending_orders || [];
    if(!list.length && !pending.length){
      panel.style.display = 'none'; box.innerHTML = ''; return;
    }
    panel.style.display = '';
    $('posRisk').textContent = money(p.open_risk_usd || 0) + ' at risk' +
      (pending.length ? ` · ${pending.length} waiting` : '');

    const priceOf = t =>
      api(`/api/candles?symbol=${encodeURIComponent(t.symbol)}&tf=${
            encodeURIComponent(t.tf)}&limit=1`)
        .then(rows => {
          const arr = Array.isArray(rows) ? rows : [];
          const last = arr[arr.length - 1];
          return last ? +last.close : null;
        })
        .catch(() => null);
    const prices = await Promise.all(list.map(priceOf));
    const pendPrices = await Promise.all(pending.map(priceOf));

    box.innerHTML = list.map((t, i) => {
      const long = t.direction === 'LONG';
      const entry = +t.entry, sl = +t.sl, tp = +t.tp, now = prices[i];
      const span = Math.abs(tp - sl);
      // where price stands between the two ends, as a percentage of the trade
      const at = (now == null || !span) ? null
        : Math.max(2, Math.min(98, ((long ? now - sl : sl - now) / span) * 100));
      const perR = Math.abs(entry - sl);
      const r = (now == null || !perR) ? null
        : (long ? now - entry : entry - now) / perR;
      const tone = r == null ? '' : r >= 0 ? 'up' : 'down';
      return `<div class="pos-row traceable" data-trace="${esc(t.setup_id || '')}"
        tabindex="0" role="button"
        title="click for why this trade was taken — the zone, the confirmation, every gate">
        <div>
          <div class="pos-sym">${esc(String(t.symbol).replace('-USD', ''))}</div>
          <div class="t-label" style="margin-top:3px">${long ? 'long' : 'short'} · ${
            esc(t.tf)} · ${playbookLabel(t.strategy)}</div>
        </div>
        <div>
          <div class="pos-track"><span class="end-sl"></span><span class="end-tp"></span>${(() => {
            // Entry tick + travelled segment. Without the entry the marker had
            // no origin: a 3:1 trade STARTS at 25% of this bar, so "near the
            // stop end" is where every fresh trade lives, win or lose. What is
            // honest to colour is the movement SINCE entry.
            const entAt = span ? Math.max(2, Math.min(98,
              ((long ? entry - sl : sl - entry) / span) * 100)) : null;
            if(at == null || entAt == null) return '';
            const a = Math.min(entAt, at), b = Math.max(entAt, at);
            return `<span class="pos-prog ${tone}" style="left:${a.toFixed(1)}%;width:${(b - a).toFixed(1)}%"></span>` +
                   `<span class="pos-entry" style="left:${entAt.toFixed(1)}%" title="entry ${px(entry)}"></span>` +
                   `<span class="pos-mark" style="left:${at.toFixed(1)}%"></span>`;
          })()}</div>
          <div class="pos-ends">
            <span>stop ${px(sl)}</span>
            <span class="now">${now == null ? 'price unavailable' : 'now ' + px(now)}</span>
            <span>target ${px(tp)}</span>
          </div>
        </div>
        <div class="pos-r ${tone}">${
          rr(r)}
          <span class="t-sub">${money(t.risk_usd)} at risk</span>
          <button class="btn pos-close" data-close-sid="${esc(t.setup_id || '')}"
            title="close this on YOUR book at the last closed price — the engine keeps simulating its own plan, so the two outcomes can be compared">Close</button></div>
      </div>`;
    }).join('') + pending.map((t, i) => {
      const long = t.direction === 'LONG';
      const entry = +t.entry, now = pendPrices[i];
      // How far price still has to travel to trigger this order. Percent, not
      // ATR: this is a distance to a resting limit, not a volatility judgement.
      const away = (now == null || !now) ? null
        : Math.abs(now - entry) / now * 100;
      return `<div class="pos-row pending traceable" data-trace="${esc(t.setup_id || '')}"
        tabindex="0" role="button"
        title="click for why this trade was taken — the zone, the confirmation, every gate">
        <div>
          <div class="pos-sym">${esc(String(t.symbol).replace('-USD', ''))}</div>
          <div class="t-label" style="margin-top:3px">${long ? 'long' : 'short'} · ${
            esc(t.tf)} · ${playbookLabel(t.strategy)}</div>
        </div>
        <div>
          <div class="pos-wait">Order resting at <b>${px(entry)}</b>${
            away == null ? '' : ` — price is ${away.toFixed(1)}% away`}.
            Nothing is at stake until it fills.</div>
          <div class="pos-ends">
            <span>stop ${px(+t.sl)}</span>
            <span class="now">${now == null ? 'price unavailable' : 'now ' + px(now)}</span>
            <span>target ${px(+t.tp)}</span>
          </div>
        </div>
        <div class="pos-r">
          <span class="chip chip-amber">waiting</span>
          <span class="t-sub">${money(t.risk_usd)} if it fills</span></div>
      </div>`;
    }).join('');
  }

  /* ---------- risk budget ----------
     The three limits the risk authority actually enforces, each drawn as a fill
     against its ceiling. Every one of them has been enforced since day one and
     shown nowhere: the ticket said "$195 at risk" without saying at risk
     AGAINST WHAT, so a REDUCED verdict or a refused setup arrived with no
     context and read as the engine being arbitrary rather than as a cap doing
     its job. The chip names the BINDING constraint, because "can I take another
     trade right now" is the question, and the answer is whichever limit runs
     out first. */
  function renderRiskBudget(p){
    const cfg = p.config || {};
    const eq = +p.equity || 0;
    /* COMMITTED risk, not just filled risk. `open_risk_usd` sums filled
       positions only, but risk.py budgets against `open_pos`, which a trade
       joins the moment it is sized (risk.py:491 — anything not MISSED) rather
       than when it fills. Metering the filled-only figure would show budget
       room that the risk authority will refuse to give, which is precisely the
       "the engine is being arbitrary" reading this panel exists to prevent. */
    const openRisk = (p.active_positions || []).concat(p.pending_orders || [])
      .reduce((s, t) => s + (+t.risk_usd || 0), 0);
    const openCap = eq * (+cfg.max_total_risk_pct || 0) / 100;
    const slots = (p.active_positions || []).length +
                  (p.pending_orders || []).length;
    const slotCap = +cfg.max_concurrent || 0;

    // Today's realised loss, read from the same journal the scoreboard reads so
    // the two can never disagree about what "today" means.
    const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
    const cut = midnight.getTime() / 1000;
    const todayPnl = (p.journal || [])
      .filter(j => j.ts >= cut).reduce((s, j) => s + j.pnl_usd, 0);
    const lost = Math.max(0, -todayPnl);
    const lossCap = eq * (+cfg.daily_loss_pct || 0) / 100;

    const cell = (label, used, cap, text) => {
      const pct = cap > 0 ? Math.max(0, Math.min(100, (used / cap) * 100)) : 0;
      const tone = cap > 0 && used >= cap ? 'bad' : pct >= 70 ? 'warn' : '';
      return `<div class="budget-cell">
        <span class="t-label">${label}</span>
        <div class="budget-bar"><i class="${tone}" style="width:${pct.toFixed(0)}%"></i></div>
        <span class="budget-txt">${text}</span>
      </div>`;
    };

    $('budget').innerHTML =
      cell('Open risk', openRisk, openCap,
           openCap > 0 ? `${money(openRisk)} of ${money(openCap)} used`
                       : 'no cap configured') +
      cell('Position slots', slots, slotCap,
           slotCap > 0
             ? (slots >= slotCap
                 ? `${slots} of ${slotCap} — full until one closes`
                 : `${slots} of ${slotCap} used`)
             : 'no cap configured') +
      cell("Today's losses", lost, lossCap,
           lossCap <= 0 ? 'no halt configured'
             : lost > 0 ? `${money(lost)} of ${money(lossCap)} before trading halts`
             : `nothing lost today · halts at ${money(lossCap)}`);

    // The binding constraint, named. Order matters: the hardest stop first.
    const chip = $('budgetChip');
    let label, tone;
    if(lossCap > 0 && lost >= lossCap){ label = 'halted for today'; tone = 'chip-red'; }
    else if(slotCap > 0 && slots >= slotCap){ label = 'no slots free'; tone = 'chip-amber'; }
    else if(openCap > 0 && openRisk >= openCap){ label = 'risk budget spent'; tone = 'chip-amber'; }
    else { label = 'room for another trade'; tone = 'chip-green'; }
    chip.textContent = label;
    chip.className = 'chip ' + tone;
  }

  /* ---------- the trade journal + daily scoreboard ----------
     Both read the same `journal` list: closed, risk-sized trades with their
     endings. The scoreboard is "today" in the OPERATOR'S clock, not UTC —
     a trade closed at 22:10 local belongs to the evening the trader watched
     it close, whatever day the exchange's clock had reached. */
  const OUTCOME_WORDS = {
    TP: 'hit target', SL: 'stopped out',
    TIMEOUT: 'closed on time — went nowhere', TIME: 'closed on time'
  };
  const outcomeWord = o => OUTCOME_WORDS[String(o).toUpperCase()] ||
    String(o).replace(/_/g, ' ').toLowerCase();
  const heldText = h => {
    const n = parseFloat(h);
    if(isNaN(n)) return '';
    if(n < 1) return 'held under an hour';
    if(n < 48) return `held ${Math.round(n)}h`;
    return `held ${Math.round(n / 24)}d`;
  };

  function renderJournal(journal, total){
    const el = $('journal');
    total = total == null ? journal.length : total;
    if(!journal.length){
      el.innerHTML = '<div class="empty">no closed trades in this window yet</div>';
      $('jnlCount').textContent = '0 closed';
      return;
    }
    /* Says "showing N of M" whenever the server sends a slice, so the chip can
       never read as a window total it is not. Today it always sends the whole
       list, and this stays correct if that ever changes. */
    $('jnlCount').textContent = total > journal.length
      ? `showing ${journal.length} of ${total} closed`
      : journal.length + ' closed';
    el.innerHTML = journal.map(j => {
      const up = j.pnl_usd > 0;
      const flat = j.pnl_usd === 0;
      const when = new Date(j.ts * 1000).toLocaleDateString(undefined,
        {month: 'short', day: 'numeric'});
      /* The one ending that deserves its own sentence: right direction, and
         costs still turned it into a loss. Says entry/target placement, not
         "bad pick" — a plain SL needs no extra prose. */
      const costsAte = j.r_gross > 0 && j.r_multiple <= 0;
      /* "hit target" beside a red −0.10R reads as a contradiction. It is not
         one — the target was simply too close to pay — but the row has to say
         that itself rather than leave the reader to reconcile it. */
      const outcomeText =
        String(j.outcome).toUpperCase() === 'TP' && j.r_multiple <= 0
          ? 'hit target — too close to pay'
          : outcomeWord(j.outcome);
      return `<div class="jnl-row${flat ? '' : up ? ' up' : ' down'}">
        <div>
          <div class="t-mono" style="font-size:13px;color:var(--fg)">${esc(String(j.symbol).replace('-USD',''))}</div>
          <div class="t-label" style="margin-top:3px">${esc(j.tf)} · ${
            j.direction === 'LONG' ? 'long' : 'short'} · ${playbookLabel(j.strategy)}</div>
        </div>
        <div class="jnl-say">
          ${outcomeText}${costsAte
            ? ' — <span class="warn">right direction, fees and slippage ate it</span>' : ''}
          <!-- joined rather than concatenated: heldText returns '' when the
               exec fact carries no holding_hours, which produced a doubled
               separator ("Jul 30 ·  · risked $195"). Any future absent field
               now degrades to one fewer clause instead of a visible gap. -->
          <div class="t-sub">${[when, heldText(j.holding_hours),
            'risked ' + money(j.risk_usd)].filter(Boolean).join(' · ')}</div>
        </div>
        <div class="jnl-r">${rr(j.r_multiple)}
          <span class="t-sub">${signedMoney(j.pnl_usd)}</span></div>
      </div>`;
    }).join('');
  }

  function renderScoreboard(journal){
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const cut = today.getTime() / 1000;
    const rows = journal.filter(j => j.ts >= cut);
    const tile = $('mTodayTile'), val = $('mToday'), sub = $('mTodaySub');
    if(!rows.length){
      tile.classList.remove('up', 'down');
      val.textContent = '—';
      sub.textContent = 'no trades closed yet today';
      return;
    }
    const pnl = rows.reduce((s, j) => s + j.pnl_usd, 0);
    const wins = rows.filter(j => j.pnl_usd > 0).length;
    const losses = rows.length - wins;
    tile.classList.toggle('up', pnl > 0);
    tile.classList.toggle('down', pnl < 0);
    val.textContent = signedMoney(pnl);
    const part = [];
    if(wins) part.push(wins + (wins === 1 ? ' winner' : ' winners'));
    if(losses) part.push(losses + (losses === 1 ? ' loss' : ' losses'));
    const netR = rows.reduce((s, j) => s + j.r_multiple, 0);
    sub.textContent = part.join(' · ') +
      ' · ' + rr(netR) + ' net';
  }

  /* ---------- RESULTS ---------- */
  async function loadPortfolio(){
    const p = await api('/api/portfolio');
    const d = p.decisions || {};
    /* Feeds the shared selector BEFORE anything renders. The deck's membership
       depends on this payload, so a render that runs between the two fetches
       would show a filled position as a pending card — the exact disagreement
       the selector exists to remove. */
    SSState.put('portfolio', p);

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
    $('rEquity').textContent = money(p.equity);

    const journal = p.journal || [];
    renderJournal(journal, p.journal_total);
    renderScoreboard(journal);

    if(!$('positions').dataset.traceWired){
      $('positions').dataset.traceWired = '1';
      $('positions').addEventListener('click', async e => {
        /* Close comes first: it lives INSIDE a traceable row, so letting the
           trace handler see the event would open the drawer instead. */
        const c = e.target.closest('[data-close-sid]');
        if(c){
          e.stopPropagation();
          if(c.disabled) return;
          const was = c.textContent;
          c.disabled = true; c.textContent = 'closing…';
          try{
            const r = await fetch('/api/positions/close', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({setup_id: c.dataset.closeSid})});
            const d = await r.json().catch(() => ({}));
            c.textContent = r.ok
              ? (d.closed ? `closed ${d.closed.r_at_close}R` : 'closed')
              : 'failed — ' + (d.detail || r.status);
            if(r.ok) refresh();
          }catch(err){ c.textContent = 'unreachable'; }
          setTimeout(() => { c.disabled = false; c.textContent = was; }, 3000);
          return;
        }
        const d = e.target.closest('[data-trace]');
        if(d && d.dataset.trace && window.SSTracer) SSTracer.open(d.dataset.trace);
      });
      // delegation covers the click; the rows still have to be reachable and
      // operable, which is per-element and has to run after each render
      $('positions').addEventListener('keydown', e => {
        if(e.key !== 'Enter' && e.key !== ' ') return;
        const d = e.target.closest('[data-trace]');
        if(!d || !d.dataset.trace) return;
        e.preventDefault();
        if(window.SSTracer) SSTracer.open(d.dataset.trace);
      });
    }
    // fire-and-forget: the positions panel fetches a price per open trade, and
    // a slow venue must not hold up the equity numbers above it
    indexHeld(p);
    renderRiskBudget(p);
    renderPositions(p).catch(() => {});

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
    /* Rewritten when the edge panel moved HERE from Diagnostics (audit B6).
       The two eras now share one page, which makes this band more important,
       not less: the tiles count the forward window and the panel below counts
       the whole book, so without the label the page contradicts itself at a
       glance. No in-page link on purpose — a bare href="#edgeRoot" would be
       read by the hash router as a surface name and blank every surface. */
    $('resultsEra').innerHTML =
      `The tiles and curve count the
       <span class="term" data-t="forwardWindow">forward window</span> that opened${
         started ? ' <b>' + started + '</b>' : ''} — not the whole history.
       The full <span class="term" data-t="recordedBook">recorded book</span>,
       across every <span class="term" data-t="baseline">baseline</span>, is measured
       just below, under the equity curve${
         ruled ? '' : ' — which is why that panel can report trades while these tiles report none'}.`;
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
  /* D3 — a REAL table, because this is real tabular data. These rows were CSS
     grids inside divs, which look identical and read as nothing: a screen
     reader in a div soup cannot answer "what column am I in" or jump between
     rows, and this app's whole pitch is dense numbers. The headers exist for
     the same reason — a sighted reader infers "42 trades" is a count from its
     shape; column semantics make that answerable rather than inferable. */
  /* The key formatter is passed in because perfRows cannot tell a SYMBOL key
     from a STRATEGY key, and they need opposite treatment: symbols get their
     venue suffix stripped, strategies are engine enums and must go through the
     same label map the deck uses. Without this the "By Strategy" table on
     Results printed BREAKOUT_RETEST — a raw constant on a trader surface, in
     the middle of a remodel whose whole point was removing them. */
  function perfRows(rows, fmtKey){
    fmtKey = fmtKey || (k => String(k).replace('-USD', ''));
    if(!rows || !rows.length) return '<div class="empty">no closed trades yet</div>';
    const body = rows.map(r => {
      const has = r.sum_r !== undefined && r.sum_r !== null;
      const pnl = +r.sum_r;
      const good = pnl >= 0;
      const wr = (r.win_pct ?? null) === null ? '—' : `${r.win_pct}%`;
      /* The exclusion travels WITH the number whose meaning it changes.
         "1 trade, -0.10R" reads very differently once you know a second was
         found on the same symbol and never funded — and that second trade is
         exactly what used to be summed into this cell. The COUNT only: an R
         from the other population inside this table is the defect being
         removed, so it stays in the block below where it is labelled. */
      const more = r.untaken_n
        ? `<div class="t-label" style="margin-top:2px;color:var(--fg-4)">${
            r.untaken_n} more found, not taken</div>` : '';
      return `<tr>
        <th scope="row">${esc(fmtKey(r.key ?? '—'))}${more}</th>
        <td>${r.n ?? 0}</td>
        <td>${wr}</td>
        <td><b style="color:${!has ? 'var(--fg-4)' : (good ? 'var(--green)' : 'var(--red-2)')}">${
          has ? rr(pnl) : 'n/a'}</b></td>
      </tr>`;
    }).join('');
    /* "net" on a taken table is money the account made or lost. On an untaken
       table it is what the trade WOULD have returned, and saying "net" there
       would let a hypothetical be read as a result. */
    const taken = (rows[0] || {}).population !== 'untaken' &&
                  (rows[0] || {}).population !== 'shadow';
    return `<table class="data-table t-mono">
      <thead><tr><th scope="col">name</th><th scope="col">trades</th>
        <th scope="col">win rate</th>
        <th scope="col">${taken ? 'net' : 'would have been'}</th></tr></thead>
      <tbody>${body}</tbody>
    </table>`;
  }

  /* A SHADOW venue is warmed but never tradeable — `risk.py` refuses every one
     of its intents. Its simulated record is evidence for admitting the venue,
     so it stays visible, but it is fenced off and labelled rather than added
     to the operator's track record. */
  /* Trades the engine found and the account did NOT take, kept off the record
     but not hidden. Two reasons a trade lands here, and the row says which:
     the risk authority refused to fund it, or its venue was never tradeable.

     This block exists because the table above it used to include these — the
     BTCUSDT row read "2 trades, 50% win, +1.77R" on the strength of a +1.87R
     trade the account was never allowed to take, three panels above a journal
     showing the same symbol at -0.10R. */
  function notTakenBlock(rows, fmtKey, what){
    if(!rows || !rows.length) return '';
    const n = rows.reduce((a, r) => a + (r.n || 0), 0);
    const why = [...new Set(rows.flatMap(r => Object.keys(r.reasons || {})))]
      .slice(0, 2).map(plainReason).join('; ');
    // "trade" is the only word that pluralises; the rest of the phrase is a
    // clause about the block, not a noun to be suffixed.
    return `<details style="border-top:1px solid var(--border-soft)">
      <summary style="padding:8px var(--lg);color:var(--fg-4);cursor:pointer" class="t-mono">
        + ${n} trade${n === 1 ? '' : 's'} ${what}${
          why ? ' — ' + esc(why) : ''}</summary>
      <!-- No R total in the summary. A headline R for trades that were never
           funded is the number that started this: it reads as performance. -->
      ${perfRows(rows, fmtKey)}</details>`;
  }

  async function loadPerformance(){
    const p = await api('/api/performance');
    const NOT_TAKEN = 'the account did not take';
    const NOT_TRADEABLE = 'on a venue the account cannot trade';
    $('perfSymbol').innerHTML =
      perfRows(p.by_symbol) +
      notTakenBlock(p.untaken_by_symbol, undefined, NOT_TAKEN) +
      notTakenBlock(p.shadow_by_symbol, undefined, NOT_TRADEABLE);
    $('perfStrategy').innerHTML =
      perfRows(p.by_strategy, playbookLabel) +
      notTakenBlock(p.untaken_by_strategy, playbookLabel, NOT_TAKEN) +
      notTakenBlock(p.shadow_by_strategy, playbookLabel, NOT_TRADEABLE);
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

  /* The engine writes its own setting descriptions, and they quote engine
     enums verbatim — "Allow SCALE_IN adds." The labels were humanised a while
     back; the sentence underneath each one still shouted a constant name. */
  /* Its own BARE-NOUN map rather than PLAYBOOK_LABELS: those values are deck
     display phrases that already carry the noun, so reusing them turned
     "Allow SCALE_IN adds." into "Allow scale-in add adds." The underscore
     requirement in the pattern is deliberate and stays — matching bare
     all-caps words would start rewriting BLOCKED inside
     halt_on_data_blocked's description, which is meant to read as it does. */
  const CODE_NOUNS = {
    SCALE_IN: 'scale-in', BREAKOUT_RETEST: 'breakout-retest',
    RANGE_FADE: 'range-fade', PULLBACK: 'pullback', REVERSAL: 'reversal'
  };
  const humaniseCodes = t => String(t).replace(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g,
    m => CODE_NOUNS[m] || m.replace(/_/g, ' ').toLowerCase());

  /* Full rebuild. Only ever called when the SHAPE of the spec changes — never
     on a keystroke and never on the refresh tick, both of which used to blow
     away the input under the operator's cursor. See patchSettingsState. */
  /* B4 — ONE path to a halt. `halted` is a real setting the server owns, but
     rendering it here made a second, quieter route to the same state as the
     big red HALT button: a checkbox in a list, applied with everything else,
     no confirmation. Two paths to a destructive action means one of them is
     the one nobody rehearsed. The button is the path — always visible, names
     its consequence, confirms — and the guardrails panel still DISPLAYS the
     halt state, so nothing is hidden, there is just one way to change it. */
  const BUTTON_OWNED = new Set(['halted']);

  function buildSettings(){
    $('setFields').innerHTML = setSpec.filter(s => !BUTTON_OWNED.has(s.name)).map(s => {
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
            letter-spacing:0;color:var(--fg-4)">${humaniseCodes(escHtml(s.description))}</span>
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
    // a real table for the same reason the perf panels are — see perfRows()
    $('dTelemetry').innerHTML = rows.length
      ? `<table class="data-table t-mono">
          <thead><tr><th scope="col">stage</th><th scope="col">count</th></tr></thead>
          <tbody>${rows.sort((a, b) => b[1] - a[1]).map(([k, n]) =>
            `<tr><th scope="row">${k.replaceAll('_', ' ').toLowerCase()}</th>
             <td><b style="color:var(--fg-2)">${fmt(n)}</b></td></tr>`).join('')}
          </tbody></table>`
      : '<div class="empty">no candidates recorded in this window yet</div>';
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

  /* ---------- developer mode ----------
     Diagnostics is the surface that asks whether the machine is telling the
     truth. That is a real question and a necessary surface — but it is a
     developer's question, and it was sitting in the rail between Rules and
     Learn where the first thing a new reader clicked showed them
     `ohlc invariant failure` and a log tail. It is opt-in now.

     The preference survives a reload, and turning it off while standing on
     Diagnostics moves you somewhere that still exists rather than leaving a
     blank stage. */
  const DEV_KEY = 'ss.devMode';
  const shellEl = document.querySelector('.shell');
  const readDev = () => { try{ return localStorage.getItem(DEV_KEY) === '1'; }
                          catch(e){ return false; } };
  function setDev(on){
    shellEl.classList.toggle('dev', on);
    const b = $('devToggle');
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.textContent = on ? 'Developer mode · on' : 'Developer mode';
    try{ localStorage.setItem(DEV_KEY, on ? '1' : '0'); }catch(e){}
    if(!on && location.hash === '#diagnostics') go('command');
  }
  setDev(readDev());
  $('devToggle').addEventListener('click',
    () => setDev(!shellEl.classList.contains('dev')));

  /* ---------- refresh loop ---------- */
  async function refresh(){
    /* The portfolio lands FIRST and alone. The deck's membership is a join
       against it, so running the two concurrently meant a first paint that
       rendered a filled position as a pending card whenever the overview won
       the race. Ordering costs one round trip and removes a whole class of
       "the screens disagree" bug. */
    const first = await Promise.allSettled([loadPortfolio()]);
    const jobs = [loadOverview(), loadHealth(),
                  loadRisk(), loadSettings(), loadCredentials(), loadPerformance(),
                  loadTelemetry()];
    const results = first.concat(await Promise.allSettled(jobs));
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
