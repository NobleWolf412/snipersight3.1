/* SniperSight shell — navigation, live wiring, and honest failure.
   Phase 1: the five surfaces exist and COMMAND/RESULTS/DIAGNOSTICS carry real
   data. Chart and settings are stubs until phases 2 and 3.
   Loud-fallback rule: a failed fetch says so on screen; it never renders a
   confident-looking zero. */
(() => {
  const $ = id => document.getElementById(id);
  const fmt = n => Number(n).toLocaleString();

  /* A PREFERENCE THAT FAILS TO PERSIST SAYS SO — ONCE.

     localStorage throws with storage disabled, in a private window that has
     exhausted its allowance, and on quota. The reads in this file all fall
     back deliberately; the writes used to swallow the error, so a setting the
     operator changed simply reverted on the next load with nothing anywhere
     saying why. §4 — a degraded path has to be audible.

     Once per load, because the alternative is a warning per toggle burying the
     first and truest one. The message names the BEHAVIOUR that was lost rather
     than only the exception: "QuotaExceededError" does not tell a reader that
     their intro card is coming back. */
  let storageWarned = false;
  function storageFailed(lost, e){
    if(storageWarned) return;
    storageWarned = true;
    console.warn(`shell: browser storage is unavailable — ${lost} will not ` +
                 `survive a reload (${(e && e.message) || e})`);
  }
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
  // `rules` lived at this address for the whole redesign; links and habits
  // survive the rename to Settings.
  const SURFACE_ALIASES = {setup: 'settings', rules: 'settings'};
  let pendingJump = null;
  /* Set once the first full refresh has been kicked off. go() runs during
     boot — from the initial hash — and refreshing from inside it then would
     race the boot refresh for no gain. */
  let booted = false;
  function go(name){
    name = SURFACE_ALIASES[name] || name;
    /* THE SKIP LINK POINTED AT A SECTION ID AND EMPTIED THE APP.

       shell.html's skip link is href="#s-command" — the id of the <section>,
       which is what an in-page link must target to move focus. The router
       reads the same hash as a surface NAME, so go('s-command') looked for
       '#s-s-command', matched nothing, and turned every surface and every rail
       item off: stage text 10,734 characters to 0, with no message and no way
       back except clicking the rail.

       It was the FIRST tab stop on the page. The one control an
       accessibility-dependent reader reaches before anything else destroyed
       the view, and the same held for any bookmarked or mistyped hash.

       Two guards, because they fix different halves. Stripping the prefix lets
       the section id and the surface name be the same link. Refusing to land
       nowhere means no hash can ever empty the stage again, whatever it says. */
    if(name.startsWith('s-')) name = name.slice(2);
    if(!document.getElementById('s-' + name)) name = 'command';
    document.querySelectorAll('.surface').forEach(s => s.classList.toggle('on', s.id === 's' + '-' + name));
    document.querySelectorAll('.nav a').forEach(a => {
      const here = a.dataset.s === name;
      a.classList.toggle('on', here);
      /* The rail showed the current surface with a colour and nothing else.
         aria-current is how that fact reaches anyone not reading the colour. */
      if(here) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    if(location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
    // The chart cannot size itself while its surface is display:none, so it is
    // told when it becomes visible rather than measuring a 0x0 box at load.
    if(window.SSChart) name === 'chart' ? SSChart.onShow() : SSChart.onHide();
    // The console polls slowly while it is off screen; arriving on it should
    // not mean waiting out that slow tick for the first paint.
    if(name === 'diagnostics' && consoleReady) pollConsole();
    /* ...and the same courtesy for the rest. The 30s tick now only refreshes
       the surface you are looking at, so ARRIVING somewhere is the moment its
       data has to be fetched — otherwise Settings would show whatever was
       true when you last left it. Concurrent requests for one path collapse
       inside SSData, so this costs nothing when it races the periodic tick. */
    if(booted) refresh();
    /* A dead-end number becomes a door. Anything with data-jump routes to the
       surface AND scrolls the panel that answers it into view, because landing
       at the top of Diagnostics is not the same as being shown the funnel. */
    if(pendingJump){
      const target = pendingJump; pendingJump = null;
      requestAnimationFrame(() => {
        const el = document.getElementById(target + 'Root') || document.getElementById(target);
        if(el) el.scrollIntoView({block: 'center',
          behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
      });
    }
    /* A new surface starts at its top. The stage kept the previous route's
       offset, so arriving on Learn from halfway down Results dropped the
       reader into the middle of a chapter with no way to tell they had
       missed the beginning. */
    const stage = document.querySelector('.stage');
    if(stage) stage.scrollTop = 0;
  }
  document.querySelectorAll('.nav a').forEach(a =>
    a.addEventListener('click', e => { e.preventDefault(); go(a.dataset.s); }));

  /* THE STRIP SAYS WHEN IT HAS MORE. Measured at 412px, Diagnostics sits at
     370-504px — off the edge, with two of the five surfaces undiscoverable.
     ss.css answers that with a slim always-visible scrollbar and argues,
     rightly, against a fade: a fade would dim the last item on the wider
     screens where everything already fits, which is a hint that lies half the
     time.

     But a ::-webkit-scrollbar does not render at rest on a touch device — it
     is an overlay that appears while scrolling and then goes away, so on the
     one device that needed the hint there is none. The class below is the
     version that cannot lie: it is set only when the strip genuinely has more
     than it can show, so the fade never appears on a screen where everything
     fits. Measured, not guessed at, and re-measured on resize and rotate. */
  const navEl = document.querySelector('.nav');
  if(navEl){
    const markScrollable = () => {
      const more = navEl.scrollWidth - navEl.clientWidth;
      navEl.classList.toggle('scrollable', more > 2);
      // and drop the hint once they have actually reached the end
      navEl.classList.toggle('scrolled-end',
        more > 2 && navEl.scrollLeft >= more - 2);
    };
    markScrollable();
    navEl.addEventListener('scroll', markScrollable, {passive: true});
    addEventListener('resize', markScrollable);
    // fonts land after first paint and change the measurement
    if(document.fonts && document.fonts.ready) document.fonts.ready.then(markScrollable);
  }
  // delegated: a figure rendered later still becomes a door
  document.addEventListener('click', e => {
    const j = e.target.closest && e.target.closest('[data-jump]');
    if(!j) return;
    e.preventDefault();
    pendingJump = j.dataset.jump;
    go((j.getAttribute('href') || '#command').slice(1));
  });
  /* SKIP TO CONTENT, to the content you are actually looking at.

     The anchor's href is hard-coded to #s-command and cannot know which surface
     is open, so on its own it navigated away from four surfaces out of five and
     left document.activeElement on <body>. Both halves were measured from every
     surface. This handler cancels the navigation entirely and moves focus into
     whichever surface is on, which is what the control has always claimed to
     do. The href stays as the no-JS fallback. */
  const skip = document.querySelector('.skip-link');
  if(skip) skip.addEventListener('click', e => {
    const target = document.querySelector('.surface.on') || $('s-command');
    if(!target) return;
    e.preventDefault();
    target.focus({preventScroll: true});
    target.scrollIntoView({block: 'start'});
  });

  addEventListener('hashchange', () => go(location.hash.slice(1) || 'command'));
  go(location.hash.slice(1) || 'command');

  /* ---------- keyboard ----------
     There were no shortcuts of any kind. Five surfaces on the number keys and
     one letter for the copilot — the whole nav, reachable without the mouse.

     Deliberately NOT bound: anything that arms, halts or cancels. A hotkey
     that sizes a trade is one fat finger away from a position nobody meant to
     take, and this app's own rule is that irreversible-feeling actions get a
     confirm dialog, not an accelerator. */
  /* First run. Shown once per browser, and the dismissal is remembered even
     if storage throws — a card that reappears every load is worse than no
     card. "Something looks wrong" goes to the wizard, because the honest
     first question a newcomer has about an empty deck is whether it is
     broken, and that is precisely what the eight checks answer. */
  const FR_KEY = 'ss.seen-intro';
  const frEl = document.getElementById('firstRun');
  if(frEl){
    /* Read: HIDE on failure, deliberately. "Shown once, dismissed forever" is
       the promise; a storage error that re-showed the intro would break it on
       every load, and an operator who has never seen the card loses nothing by
       not seeing it once. */
    let seen;
    try{ seen = localStorage.getItem(FR_KEY) === '1'; }catch(e){ seen = true; }
    frEl.hidden = seen;
    const dismiss = () => {
      frEl.hidden = true;
      /* Write: SAY so. The card goes away for this session either way, but if
         this throws it comes back on the next load, and "dismissed forever"
         quietly became "dismissed until you reload" with nothing anywhere
         explaining it. Once per load — this runs on a click, not a loop. */
      try{ localStorage.setItem(FR_KEY, '1'); }
      catch(e){ storageFailed('the dismissal of the intro card', e); }
    };
    document.getElementById('frGo').addEventListener('click', dismiss);
    document.getElementById('frDiag').addEventListener('click', () => {
      dismiss();
      if(window.SSWizard) SSWizard.open();
    });
  }

  const expBtn = document.getElementById('btnExport');
  if(expBtn) expBtn.addEventListener('click', () => exportJournal(lastJournal));

  /* Ledger takes 6, not 4. It sits beside Results in the rail because that is
     where it belongs by subject, but 4 and 5 have meant Settings and
     Diagnostics for the life of the app and renumbering a habit is a worse
     cost than a rail whose order and whose keys are not the same list. The
     keys are accelerators; nothing on screen numbers the rail. */
  const KEYS = {'1': 'command', '2': 'chart', '3': 'results',
                '4': 'settings', '5': 'diagnostics', '6': 'ledger'};
  addEventListener('keydown', e => {
    // never steal a keystroke from a field, and never from a chord the OS or
    // the browser owns
    if(e.ctrlKey || e.metaKey || e.altKey) return;
    // e.target is document/window for a keystroke with nothing focused, and
    // those have no .matches — guard on the method, not on truthiness.
    const t = e.target;
    if(t && typeof t.matches === 'function' &&
       (t.matches('input, textarea, select') || t.isContentEditable)) return;
    if(KEYS[e.key]){ e.preventDefault(); go(KEYS[e.key]); return; }
    if(e.key === 'c' && window.SSCopilot){ e.preventDefault(); SSCopilot.toggle(); }
    if(e.key === '?'){ e.preventDefault(); toast(
      'Keys: 1–6 switch surfaces · c toggles the copilot · Esc closes ' +
      'popovers. Arming is deliberately not on a key.', 'good'); }
  });

  /* ---------- clock ---------- */
  /* ONE NODE TICKS. This called $('clock') — a document.getElementById — every
     second, so a 1Hz timer was doing a document-wide lookup forever and any
     element reference held across it was invalidated on the next frame. The
     node is resolved once and only its text is written; nothing else in the
     app is touched by the clock. Writing only on CHANGE also means a
     background tab with a throttled timer does no work at all. */
  const clockEl = $('clock');
  let lastClock = '';
  setInterval(() => {
    const t = new Date().toISOString().slice(11, 19) + 'Z';
    if(t !== lastClock){ lastClock = t; clockEl.textContent = t; }
  }, 1000);

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
  /* The age comes from ssdata.js, which owns it. This file used to stamp its
     own lastGoodAt in its own refresh loop — a second authority for a number
     the data layer already had, and one that went stale the moment anything
     else on the page fetched. §8: the UI reads, it never re-derives. */
  function ageText(ms){
    if(ms == null) return 'Nothing on this page has loaded successfully yet.';
    const s = Math.round(ms / 1000);
    const age = s < 90 ? `${s} seconds` : `${Math.round(s / 60)} minutes`;
    return `The numbers still on screen are ${age} old.`;
  }
  /* WHICH FAILURE, in words. "API DEGRADED" covered two situations the
     operator answers differently: the phone cannot reach the PC at all
     (nothing is wrong at the desk — walk out of the lift), and the PC
     answered badly (the desk needs attention). On loopback only the second
     could ever happen, which is why one word was enough until the app was
     reachable from a phone. Colour cannot carry this distinction; the words
     have to. */
  const FAILURE_WORDS = {
    offline: {chip: 'NO CONNECTION',
              say: n => `This device cannot reach the PC — ${n} ` +
                        `${n === 1 ? 'panel has' : 'panels have'} stopped refreshing.`},
    server:  {chip: 'API DEGRADED',
              say: n => `The PC answered, badly: ${n} ` +
                        `${n === 1 ? 'panel' : 'panels'} could not refresh.`},
  };
  function markDegraded(detail, failedCount){
    degraded = true;
    const h = (window.SSData.health && window.SSData.health()) || {};
    const n = h.failing || failedCount || 1;
    const words = FAILURE_WORDS[h.state] || FAILURE_WORDS.server;
    $('healthOrb').className = 'orb bad';
    $('healthTxt').textContent = words.chip;
    $('healthChip').title =
      `${words.say(n)} ` +
      `${ageText(h.neverLoaded ? null : h.staleMs)} Click for Diagnostics.`;
    $('healthChip').classList.add('clickable');
    /* The chip is shed below 900px to make room in the top bar, which is fine
       while it reads OK and wrong the moment it reports a failure. ssdata.js
       deliberately keeps the last good numbers on screen when a fetch fails,
       and its comment justifies that by saying THIS chip reports the staleness
       in words — so hiding it turns a stated contract into stale prices with a
       confident face. On loopback the fetch never fails and this never showed;
       over a tunnel or cellular it fails constantly. The class overrides the
       shed rule, so the chip disappears only while there is nothing wrong. */
    $('healthChip').classList.add('degraded');
    console.warn('[shell] refresh failed:', detail);
  }
  $('healthChip').addEventListener('click', () => go('diagnostics'));

  /* ---------- COMMAND + status bar ---------- */
  /* The last overview payload, so `renderDeck` can tell an unexamined window
     from a quiet market. It needs `scanner.cycles` and the admitted count, and
     re-fetching them there would be a second request for data this function
     already holds — and could disagree with what is on screen. */
  let lastOverview = null;
  // The budget's binding stop, so the disposition line can quote it rather than
  // recompute it. Written by renderRiskBudget, read by renderDisposition.
  let lastConstraint = null;
  /* The deck split the tile computed, so the disposition quotes the SAME object
     rather than recomputing from a variable that is populated later in the
     cycle. See renderDisposition for what that cost. */
  let lastSplit = null;
  /* What the shell's accent is FOR. See setAccentMode. */
  let liveEnabled = false;
  let engineExposed = false;
  /* The portfolio payload the Open Trades rows were built from. The copilot
     button needs the whole trade — direction, entry, stop, target — to compose
     its question, and putting six values on the button as data attributes
     would be a second copy of the trade that can disagree with the first. */
  let lastPortfolio = {};

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
       producing nothing is the ordinary case, 75 producing nothing is not.

       The read itself lives in SSState.symbolSets(), called below — this
       function held a second `universe_counts` lookup that nothing consumed,
       which is the shape the original defect took: two places deriving one
       number. One place does now. */
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
    /* Actionable only. A nav badge reading 3 that leads to "nothing to take" is
       a false alarm, and it was firing on every refused setup in the window. */
    const split = lastSplit = deckSplit(active);
    $('mSetups').textContent = split.ordered.length;
    $('mSetupsSub').textContent = split.passed.length
      ? `${split.passed.length} examined, not taken` : '';
    $('nCommand').textContent = split.ordered.length || '';
    renderDisposition();

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
    /* The rail needs BOTH payloads: the book from the portfolio and the live
       price from here. Whichever lands second has to repaint, or the ring and
       the ladder marker sit at "no price" until the next 30s poll. */
    renderMissions();
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
    if(m <= 0) return 'Expiring now';
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

  /* Two or three words for a table cell, with the full sentence on hover.
     The sentences are right for a card that has room to explain; repeated
     down a column they stop being read at all. */
  const SHORT_REASON = {
    NOT_IN_POINT_IN_TIME_UNIVERSE: 'not on watchlist',
    CONCURRENT_LIMIT: 'slots full',
    EXPOSURE_LIMIT: 'risk budget',
    DAILY_LOSS_HALT: 'daily halt',
    DRAWDOWN_HALT: 'drawdown halt',
    COOLDOWN: 'cooling off',
    LEVERAGE_CAP: 'leverage cap',
    STOP_BEYOND_LIQUIDATION: 'stop past liquidation',
    BELOW_MIN_NOTIONAL: 'too small',
    PARTICIPATION_TOO_THIN: 'book too thin',
    SHORT_UNSUPPORTED_COINBASE_SPOT: 'no shorts on spot',
    STRATEGY_DISABLED: 'playbook off',
    OPERATOR_HALT: 'halted',
    DATA_HEALTH_BLOCKED: 'data blocked',
  };
  const shortReason = c => SHORT_REASON[String(c).split('(')[0]] ||
    String(c).split('(')[0].replace(/_/g, ' ').toLowerCase();

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

  /* THE EMPTY-WINDOW RULE, site 4 of 4.
     The informative branch was gated on `total > 0`, so on a FRESH BASELINE —
     when nothing has been rejected because nothing has been examined — it was
     unreachable, and the operator got four bare words. That is precisely the
     moment after every rule change, when "no setups right now" is most likely
     to be read as "the scanner is broken".

     Three distinct states, three different messages. Two of them are the
     OPPOSITE of each other and were collapsed into the same sentence: a quiet
     market and an unexamined one.

     Extracted from renderDeck so the "nothing ACTIONABLE" path can lead with
     the same sentence rather than inventing a fourth wording for what is the
     same fact. */
  function deckEmptyHtml(funnel){
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
    return '<div class="empty">No setups right now.' + body + '</div>';
  }

  /* ONE AUTHORITY FOR "HOW MANY SETUPS".

     This split used to live inside renderDeck, so the deck was the only reader
     that knew a REJECTED or expired setup is not something you can act on. The
     Active-setups tile counted the raw payload and read 3 directly above a deck
     headline that read "no setups right now" — both true under different
     definitions of the word, on one screen, which is the definition of a UI
     that cannot be trusted on a number.

     Every reader of that count now calls this: the tile, the nav badge, the
     disposition line, and the deck itself. The convention is one authority per
     number, and this is that authority. */
  function deckSplit(setups){
    const expiry = s => s.expires_at_ts || Infinity;   // no expiry -> sorts last
    const best = new Map();            // token -> the one expiring soonest
    for(const s of setups || []){
      /* Keyed by TOKEN, not by symbol. The header promises one card per coin
         and the deck was showing PF_UNIUSD and UNIUSDT — the same coin on two
         venues — as two near-identical cards, because a venue prefix or a
         quote suffix made them different keys. The surviving card names its
         venue, so the split is stated rather than duplicated. */
      const key = tokenOf(s.symbol);
      const cur = best.get(key);
      if(!cur || expiry(s) < expiry(cur)) best.set(key, s);
    }
    const now = Date.now() / 1000;
    const all = [...best.values()].sort((a, b) => expiry(a) - expiry(b));
    const spent = s => (s.risk && s.risk.decision === 'REJECTED')
                    || (s.expires_at_ts && s.expires_at_ts <= now);
    return { all, ordered: all.filter(s => !spent(s)), passed: all.filter(spent) };
  }

  /* THE ONE LINE THAT ANSWERS THE SURFACE'S OWN QUESTION.

     Reads only, and re-derives nothing: deckSplit() owns the counts,
     bindingConstraint() owns the stop, and the scanner's own liveness flag owns
     whether any of it is current. If this line is ever wrong, one of those
     three is wrong and every panel below it is wrong in the same way, which is
     the point. A summary with its own arithmetic is a second opinion.

     Not an aria-live region on purpose. It repaints on a 30s poll, and a live
     region that re-announces "Nothing to take right now" twice a minute is a
     screen-reader user's definition of hostile. It sits first in the document,
     so it is read on arrival, which is when the answer is wanted. */
  /* THE DYNAMIC ACCENT RULE, FINALLY CONNECTED.

     ss.css declares three accents — idle green, paper amber, live red — and
     shell.html wrote data-mode="idle" as a literal that nothing ever changed.
     One hit across every .js, .py, .html and .css in the repo. The design
     system was documented around a mechanism that had never fired, and a
     comment in ss.css claimed "the primary button is amber while the book is
     paper", describing behaviour the app did not have.

     Wired to exposure, because that is what amber already means everywhere
     else in this stylesheet: .deck-row.held, .ticket.managing, .tk-open and
     .tkm-dot all use it for "your money is on this", and four independently
     owned modules agree on it without a shared component. The shell now agrees
     with them. Green is flat, amber is committed, and the accent answers one
     question at a glance from any surface: is my money on the line.

     Both books count. The engine's positions and the operator's hand-armed
     orders are kept rigorously apart in the RECORD — a hand-picked trade must
     never be read as engine edge — but they are not apart in the money, and
     this rule is about the money. renderMineAside already makes the same
     judgement in words: "Outside these limits: 79 hand-picked".

     Red is a tripwire, not a state we expect. live_enabled is a hardcoded
     False in server.py and there is no order-routing code behind it, so this
     branch should never fire. It is wired anyway: if that constant ever flips,
     every accent in the app turns red before a single order is sent, and
     nobody has to remember to add the warning. */
  /* DO NOT CLAIM A MODE BEFORE THE BOOK HAS ANSWERED.

     shell.html used to ship `data-mode="idle"` as a literal, so every launch
     painted the whole shell GREEN — the accent that means "nothing of yours
     is in the market" — and then flipped to amber a second or two later when
     the portfolio arrived and said otherwise. Green first, on a trader's home
     screen, is not a neutral placeholder: it is the app asserting the SAFE
     state before it has any facts, and asserting it in the one channel whose
     entire job is answering "is my money on the line".

     `unknown` is the honest opening state and renders a muted accent that
     claims nothing. It resolves once, the moment /api/portfolio lands, and
     never appears again. */
  let bookKnown = false;
  function setAccentMode(){
    if(!bookKnown) return;             // stay `unknown`; say nothing yet
    const manualExposed =
      (+MINE.open_risk_usd || 0) > 0 || (+MINE.pending_risk_usd || 0) > 0 ||
      (MINE.open || []).length > 0;
    const mode = liveEnabled ? 'live'
               : (engineExposed || manualExposed) ? 'paper'
               : 'idle';
    if(document.body.dataset.mode !== mode) document.body.dataset.mode = mode;
  }

  function renderDisposition(){
    const el = $('disposition');
    if(!el) return;
    if(!lastOverview) return;              // still loading: keep the skeleton
    /* Wait for the split rather than guessing at it. This read
       deckSplit(lastDeckArgs ? lastDeckArgs[0] : []), and lastDeckArgs is set
       by renderDeck, which the overview handler calls AFTER this function — so
       on first paint the split was empty, refused counted 0, and the line
       omitted its refusal clause while the tile forty pixels below already read
       "3 examined, not taken". It corrected on the next poll, which means it
       was wrong for the first thirty seconds and right after: wrong during the
       twenty-second check, which is one of the three session shapes this
       surface exists to serve, and right for the two that would have caught it.

       Now it quotes the very object the tile rendered from, and holds the
       skeleton until there is one. A shared authority is only shared if every
       reader reads the same instance. */
    if(!lastSplit) return;
    const sc = lastOverview.scanner || {};
    const split = lastSplit;
    const stop = lastConstraint && lastConstraint.blocked ? lastConstraint : null;
    const n = split.ordered.length, refused = split.passed.length;

    let tone = '', text;
    if(sc.alive === false){
      /* Degraded paths are audible. Saying "nothing to take" in the same voice
         whether the market is quiet or the scanner is dead uses one sentence
         for two opposite situations, and the operator cannot tell them apart. */
      tone = 'bad';
      text = 'The scanner is not running, so nothing is being watched. Diagnostics names the failing check.';
    } else if(n && stop){
      tone = 'warn';
      text = `${n} ${n === 1 ? 'setup is' : 'setups are'} ready, but ${stop.clause}.`;
    } else if(n){
      tone = 'go';
      text = `${n} ${n === 1 ? 'setup' : 'setups'} ready to review, in the deck below.`;
    } else {
      text = 'Nothing to take right now.';
      if(refused) text += ` ${refused} ${refused === 1 ? 'was' : 'were'} examined and refused.`;
      if(stop) text += ` Also, ${stop.clause}.`;
    }
    el.className = 'disposition' + (tone ? ' ' + tone : '');
    el.textContent = text;
  }

  /* ═══════════════ THE MISSION RAIL IS THE BOOK, NOT THE PLAN ═══════════════

     This rail used to render `SSState.deck()` — VALIDATED setups still
     PENDING — and it was empty every single time anyone looked at it. Not
     usually. Structurally.

     `engine/pipeline.py` runs `setups -> execsim` back to back inside ONE
     cycle, and execsim paper-fills every VALIDATED setup at entry on its
     trigger bar. So PENDING exists for the microseconds between two engines
     in the same pass and is never observable between cycles. Measured on the
     live store while this was written: 36 setups, 18 VALIDATED, 18 EXPIRED,
     30 already carrying an exec result, 0 pending orders, 0 PENDING.

     The operator's question is different when the engine trades for itself.
     Not "what should I take" — it has been taken. "What am I IN, and what
     did it just do." So the rail carries the book: filled positions first,
     resting orders behind them. Those are on screen every day there is
     exposure, which is the point.

     The refused setups still render, through renderDeck below, into
     Overwatch's own tab. They are the record of what did NOT happen, and
     that is a different question from what is happening. */
  function renderMissions(){
    const el = $('deck');
    if(!el) return;
    const p = lastPortfolio || {};
    const open = p.active_positions || [], resting = p.pending_orders || [];
    const rows = open.concat(resting);
    if(!rows.length){
      missionRows.forEach(r => r.el.remove());
      missionRows.clear();
      if(!el.querySelector('.empty'))
        el.innerHTML = '<div class="empty">No position open.<br>' +
          '<span style="color:var(--fg-3)">The engine enters on its own as ' +
          'setups confirm. Nothing is open right now, and nothing needs you.</span></div>';
      missionRailSync();
      return;
    }
    el.querySelectorAll(':scope > .empty, :scope > .skeleton').forEach(n => n.remove());
    /* Current price per symbol, off the overview the tiles already read. Used
       only to POSITION the live marker between stop and target — the same
       geometry the ladder draws — never to compute an R or a P&L. Those have
       an authority and it is not this file. */
    const px_ = new Map();
    for(const s of ((lastOverview || {}).symbols) || [])
      if(s.price != null) px_.set(s.symbol, +s.price);

    const now = Date.now() / 1000;
    const seen = new Set();
    rows.forEach(t => {
      const key = t.setup_id || (t.symbol + '|' + t.tf);
      seen.add(key);
      const filled = open.includes(t);
      const html = missionCardInner(t, filled, px_.get(t.symbol), now);
      const cls = 'deck-row mc mission' + (filled ? ' filled' : ' resting');
      let rec = missionRows.get(key);
      if(!rec){
        const node = document.createElement('div');
        node.className = cls;
        node.innerHTML = html;
        rec = {el: node, html, cls};
        missionRows.set(key, rec);
      }else{
        if(rec.cls !== cls){ rec.el.className = cls; rec.cls = cls; }
        if(rec.html !== html){ rec.el.innerHTML = html; rec.html = html; }
      }
      el.appendChild(rec.el);
    });
    for(const [key, rec] of missionRows){
      if(seen.has(key)) continue;
      rec.el.remove(); missionRows.delete(key);
    }
    wireCardActions(el);
    missionRailSync();
  }
  const missionRows = new Map();

  /* A live trade, in the dossier card's own anatomy. The ladder is the hero
     here in a way it never was for a plan: stop, entry and target to scale
     with a marker showing where price actually stands between them. */
  function missionCardInner(t, filled, price, now){
    const long = t.direction === 'LONG';
    const held = Math.max(0, now - (t.updated_at || now));
    const d = Number(t.decision) === 0 ? null : t.decision;
    return `
      <div class="mc-top">
        <span class="mc-stamp ${filled ? 'st-live' : 'st-rest'}">${
          filled ? 'IN TRADE' : 'ORDER RESTING'}</span>
        <span class="mc-id t-mono">${filled ? 'Held ' + agoText(held) : 'Not filled yet'}</span>
      </div>
      <div class="mc-hero">
        <div class="mc-idy">
          <!-- A REAL BUTTON, not a div with a click handler. This carries the
               keyboard affordance the deleted Engaged-detail rows owned: the
               symbol opens the chart on this trade, and a native <button>
               gets Enter and Space from the platform rather than from a
               hand-rolled keydown that has to be remembered at every new
               call site. Both a filled position and a resting order render
               through here, so one control covers both. -->
          <button class="mc-tok t-mono pos-sym pos-open" data-manage="${esc(t.symbol)}"
                  data-managetf="${esc(t.tf)}"
                  title="open the chart on this trade">${esc(tokenOf(t.symbol))}</button>
          <div class="mc-sub t-label" title="${esc(t.symbol)}">${
            esc(String(t.symbol).replace('-USD',''))} · ${esc(t.tf)} · ${playbookLabel(t.strategy)}</div>
          <div class="mc-dirline">
            <span class="chip ${long ? 'chip-green' : 'chip-red'}">${esc(t.direction)}</span>
            ${d ? `<span class="chip ${d === 'REDUCED' ? 'chip-amber' : 'chip-green'}">${
              esc(DECISION_LABELS[d] || d)}</span>` : ''}
          </div>
        </div>
        <div class="mc-ringcol">
          ${ladderRing(t, price)}
          <div class="t-label mc-exp">${price != null ? 'Toward target' : 'No live price'}</div>
        </div>
      </div>
      ${ladderHtml(t, price)}
      <div class="mc-nums t-mono">Risk <b style="color:var(--fg)">${
        t.risk_usd == null ? '—' : money(t.risk_usd)}</b>${
        t.notional_usd == null ? '' : ` · Size <b style="color:var(--fg)">${money(t.notional_usd)}</b>`}</div>
      <div class="mc-acts">
        <button class="btn" data-trace="${esc(t.setup_id || '')}"
                title="what this trade passed, gate by gate">Reasons</button>
        <!-- The composed hold question, carried over from the deleted rows.
             It OFFERS the wording and never sends it — the dock fills its own
             input and the operator presses send. -->
        <button class="btn" data-ask="${esc(t.setup_id || '')}"
                data-asksym="${esc(t.symbol)}" data-asktf="${esc(t.tf)}"
                title="ask the copilot whether to hold this — it reads the trace and cannot arm">Ask</button>
        <button class="btn btn-amber" data-manage="${esc(t.symbol)}"
                data-managetf="${esc(t.tf)}"
                title="open the chart — the ticket manages this position">Manage</button>
        <!-- CLOSE, carried over with the rest. It is the one WRITE control on
             this card and it only exists for a filled position: a resting
             order has nothing to close. Leaving it behind with the deleted
             rows would have removed the operator's ability to close from
             Command at all, which is a capability loss, not a declutter. -->
        ${filled ? `<button class="btn pos-close" data-close-sid="${esc(t.setup_id || '')}"
                title="close this on YOUR book at the last closed price — the engine keeps simulating its own plan, so the two outcomes can be compared">Close</button>` : ''}
      </div>`;
  }

  /* Where price stands between stop and target, as a ring. Pure geometry on
     four known prices — the same thing the ladder draws — and labelled as
     position, never as profit. */
  function ladderRing(t, price){
    const e = parseFloat(t.entry), tp = parseFloat(t.tp), sl = parseFloat(t.sl);
    if(price == null || !isFinite(e) || !isFinite(tp) || !isFinite(sl) || tp === sl)
      return ringSvg(0, 'ring-form', '—', 'no price');
    const f = Math.max(0, Math.min(1, (price - sl) / (tp - sl)));
    const cls = f > 0.66 ? 'ring-ok' : f > 0.33 ? 'ring-mid' : 'ring-low';
    return ringSvg(f, cls, Math.round(f * 100) + '%', 'stop→target');
  }

  function renderDeck(setups, funnel){
    lastDeckArgs = [setups, funnel];
    const el = $('deck');
    /* The refused cards live in Overwatch now, under its "Not taken" tab.
       They are evidence about why nothing fired, which belongs with the other
       things being watched — not in the panel that answers "what should I do
       right now", where a four-day-dead card was sitting in the slot where
       advice goes. */
    const strip = $('refused'), panel = $('refusedPanel');
    if(!setups.length){
      deckRows.clear();
      if(strip) strip.innerHTML = deckEmptyHtml(funnel);
      if(panel) panel.style.display = '';
      return;
    }

    /* ACTIONABLE FIRST, AND NEVER A DEAD CARD ALONE.

       This panel answers "What should I do right now?" and the audit found it
       answering with a single setup that was four days old, expiring, refused
       by the risk authority, and carrying `dead` in its own class list. The
       experienced reader treats a stale signal as noise and stops trusting
       the deck; the newcomer cannot tell whether a card marked NOT TRADED is
       advice or a rejection, because it sits in the slot where advice goes.

       Nothing is hidden — a refused setup is still the best available answer
       to "why did nothing fire", which is why the funnel exists. It is
       demoted, and when it is ALL there is, the honest empty state leads and
       the refusals follow it under a heading that says what they are. */
    const { ordered, passed } = deckSplit(setups);

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
    /* The differ APPENDS row nodes; anything else in the container survives
       every render, so the placeholder and the empty state must be removed by
       hand or they sit ABOVE the first real card forever. This was live: a
       PF_ZECUSD setup rendered underneath the skeleton, and it went unseen
       because the deck was empty in every test until a real setup fired. */
    if(strip) strip.querySelectorAll(':scope > .skeleton, :scope > .empty')
      .forEach(n => n.remove());

    /* EVERY card this function makes is a card that did NOT become a
       position. `ordered` is PENDING setups, which execsim makes unreachable
       (see renderMissions), so in practice this is `passed` — refused and
       expired. Both go to the same tab: the question they answer is "why did
       nothing fire", and that is not the question the rail answers. */

    /* SECONDS, because that is what the row's two clocks compare against.
       `foundAgo` subtracts `market_time` and `expiresIn` subtracts
       `expires_at_ts`, both epoch seconds off the fact — in milliseconds every
       setup would read as found 56 years ago and long expired.

       It was missing entirely. `deckRowInner(s, now)` was extracted into its
       own function without a binding for `now` in this scope, so the first row
       threw `ReferenceError: now is not defined` and the forEach died there.
       Read ONCE outside the loop rather than per row: every row on one render
       should date itself from the same instant, or two rows a millisecond apart
       can print different minute counts from the same paint.

       What it looked like is why it survived: the divider above is inserted
       BEFORE this loop, so the deck printed "Looked at, not taken" and then
       nothing under it, while the tile beside it said "4 examined, not taken".
       An empty deck, not a broken one — and the loop only runs when there is
       something to show, so every test with an empty deck passed. It also
       rejected loadOverview() on every cycle, which is what put API DEGRADED in
       the top bar with all five Command endpoints answering 200. */
    const now = Date.now() / 1000;
    const seen = new Set();
    ordered.concat(passed).forEach(s => {
      const key = s.symbol;
      seen.add(key);
      const held = heldSids.has(s.setup_id || '') || pendSids.has(s.setup_id || '');
      const done = doneSids.has(s.setup_id || '');
      const spent = s.risk && s.risk.decision === 'REJECTED';
      const cls = 'deck-row mc' + (spent ? ' dead' : '')
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
      // every card here is a card that did not become a position
      (strip || el).appendChild(rec.el);   // appendChild MOVES an existing node
    });

    for(const [key, rec] of deckRows){
      if(seen.has(key)) continue;
      if(rec.el.classList.contains('expiring')) continue;   // already fading
      rec.el.classList.add('expiring');
      setTimeout(() => { rec.el.remove(); deckRows.delete(key); }, 900);
    }

    /* The panel hides itself when there is nothing refused — an empty
       "Refused setups" heading is a promise of an explanation that is not
       there. The count and the lede both name the window so the number is
       answerable. */
    if(panel){
      const n = ordered.length + passed.length;
      panel.style.display = n ? '' : 'none';
      const cnt = $('refusedCount');
      if(cnt) cnt.textContent = n + (n === 1 ? ' setup' : ' setups');
      const lede = $('refusedLede');
      if(lede) lede.textContent = n
        ? 'Setups the risk authority refused, or that expired before price ' +
          'came back. Each card carries the reason it was not taken.'
        : '';
    }
    wireCardActions(strip || el);
    mountRails(strip || el);
  }

  /* CLOSING A POSITION, carried out of the deleted Engaged-detail rows.

     This is the one WRITE control on a mission card and the irreversible
     half of the pair: an arm can be left to expire, a close is recorded
     and the engine's own simulation carries on without it. The
     confirmation restates the trade from the payload the card was built
     from, so the dialog quotes the position the operator can see rather
     than a second fetch that could name a different one. */
  async function closePosition(c){
    if(c.disabled) return;
    const sid = c.dataset.closeSid;

    /* SAY WHAT IS ABOUT TO END. The ticket restates side, symbol, levels
       and dollars before arming; closing had no equivalent, on the
       reasoning that it is small and quiet. That reasoning was written
       for a 55x19 button under a cursor. On a phone this control is now
       48px and full width, sitting in a list the operator is scrolling
       with the same thumb — and closing is the irreversible half of the
       pair: an arm can be left to expire, a close is recorded and the
       engine's own simulation carries on without it.

       Restated from the payload the row was built from, so the dialog
       quotes the position the operator can see rather than a second
       fetch that could name a different one. */
    const pos = (lastPortfolio.active_positions || [])
      .concat(lastPortfolio.pending_orders || [])
      .find(x => x.setup_id === sid);
    if(pos){
      const r0 = pos.r_multiple != null ? Number(pos.r_multiple) : null;
      const lines = [
        `${String(pos.direction || '').toUpperCase()} ${pos.symbol || ''} ${pos.tf || ''}`,
        `entry ${pos.entry}`,
        r0 == null ? 'result so far unknown'
                   : `closing at ${r0 >= 0 ? '+' : ''}${r0}R`,
      ];
      if(!await SSConfirm({
        title: 'Close this position?',
        rows: lines,
        note: 'This ends the trade on your paper book now, at the last ' +
              "closed bar. The engine's own simulation of the setup " +
              'carries on.',
        confirmLabel: 'Close it',
        tone: 'danger'
      })) return;
    }

    const was = c.textContent;
    c.disabled = true; c.textContent = 'closing…';
    try{
      const r = await fetch('/api/positions/close', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({setup_id: sid})});
      const d = await r.json().catch(() => ({}));
      c.textContent = r.ok
        ? (d.closed ? `closed ${d.closed.r_at_close}R` : 'closed')
        : 'failed — ' + (d.detail || r.status);
      if(r.ok) refresh();
    }catch(err){
      /* 'unreachable' claimed the close did not happen. fetch() rejects
         both when the request never left AND when it arrived, was
         recorded, and the reply was lost — indistinguishable from here,
         and the second is ordinary on cellular. Refreshing is the answer
         that cannot be wrong: the row either disappears because it
         closed, or it is still there because it did not. */
      c.textContent = 'no reply — checking…';
      try{
        await refresh();
        c.textContent = 'no reply; see the list';
      }catch(_){
        c.textContent = 'no reply, and the list will not load — unknown';
      }
    }
    // give the outcome a beat to be read, then hand the button back
    setTimeout(() => { c.disabled = false; c.textContent = was; }, 3000);
  }

  /* One wiring pass for every card in the app, whichever container it lives
     in. `dataset.wired` survives a node being moved between containers, so a
     card the differ relocates keeps its handlers instead of losing them or
     collecting a second copy. */
  function wireCardActions(box){
    if(!box) return;
    box.querySelectorAll('button[data-sym]').forEach(b => {
      if(b.dataset.wired) return;
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
       this trade / why was this refused" gate by gate, wired to no click. */
    box.querySelectorAll('[data-trace],button[data-why]').forEach(d => {
      const id = d.dataset.trace || d.dataset.why;
      if(d.dataset.wired || !id) return;
      d.dataset.wired = '1';
      if(!d.matches('button')) activatable(d);
      d.addEventListener('click', () => {
        if(window.SSTracer) SSTracer.open(id);
      });
    });
    // the plain-English refusal, in a dialog, for the card that was refused
    box.querySelectorAll('button[data-reasons]').forEach(b => {
      if(b.dataset.wired) return;
      b.dataset.wired = '1';
      b.addEventListener('click', () => explainRefusal(b.dataset.reasons, b.dataset.rsym));
    });
    /* CARRIED FROM THE DELETED ENGAGED-DETAIL ROWS.

       `data-manage` opens the chart on that trade — go() FIRST, because
       SSChart.open only loads the data and navigating is the caller's job;
       without it the ticket silently switched to managing a trade on a
       surface the operator was not looking at.

       These are real <button>s, so Enter and Space come from the platform and
       the hand-rolled keydown handler that used to live on #positions is not
       needed. */
    box.querySelectorAll('[data-manage]').forEach(m => {
      if(m.dataset.wired) return;
      m.dataset.wired = '1';
      m.addEventListener('click', e => {
        e.stopPropagation();
        go('chart');
        if(window.SSChart) SSChart.open(m.dataset.manage, m.dataset.managetf);
      });
    });
    /* The composed hold question. It reaches the dock as a SUGGESTION and is
       never auto-sent — the operator's input is theirs, which is the ruling
       test_copilot_dock.js pins in both directions. */
    box.querySelectorAll('[data-close-sid]').forEach(b => {
      if(b.dataset.wired) return;
      b.dataset.wired = '1';
      b.addEventListener('click', e => { e.stopPropagation(); closePosition(b); });
    });
    box.querySelectorAll('[data-ask]').forEach(a => {
      if(a.dataset.wired) return;
      a.dataset.wired = '1';
      a.addEventListener('click', e => {
        e.stopPropagation();
        if(!window.SSCopilot) return;
        const t = (lastPortfolio.active_positions || [])
          .concat(lastPortfolio.pending_orders || [])
          .find(x => x.setup_id === a.dataset.ask);
        if(!t) return;
        SSCopilot.open({kind: 'chart', symbol: a.dataset.asksym,
                        tf: a.dataset.asktf, setupId: a.dataset.ask,
                        suggest: holdAsk(t)});
      });
    });
  }

  /* WHY IT DID NOT TAKE, IN WORDS.
     funnel.js already carries a `means` sentence and a "go here to fix it"
     link for every refusal code the engine can emit — written for someone who
     has never traded, and until now readable only on Diagnostics, the surface
     a trader has least reason to open. This puts it one button from the card
     it explains. No jargon reaches the dialog: an unknown code degrades to its
     own de-underscored text rather than being guessed at. */
  function explainRefusal(codesCsv, sym){
    const codes = String(codesCsv || '').split('|').filter(Boolean);
    if(!codes.length || !window.SSConfirm) return;
    /* One block per reason: the short sentence, then the paragraph that says
       what it actually means. `explain()` returns null for a code funnel.js
       has no entry for, and that degrades to the de-underscored code rather
       than to a guess — describing a refusal we do not understand would be
       worse than showing the raw one. */
    const rows = [];
    codes.forEach((c, i) => {
      if(i) rows.push('');                       // a spacer between reasons
      const e = SSFunnel.explain ? SSFunnel.explain(c) : null;
      rows.push(SSFunnel.plain(c).replace(/^./, m => m.toUpperCase()));
      if(e && e.means) rows.push(e.means);
    });
    SSConfirm({
      title: `Why ${sym || 'this setup'} was not taken`,
      lead: codes.length > 1 ? `${codes.length} things stopped it.` : '',
      rows,
      note: 'Nothing was risked on this.',
      confirmLabel: 'Close',
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

  /* ---------- the mission rail ----------
     A rotating wheel, not a slider. SSWheel (static/wheel.js) owns the
     physics and one number: `pos`, a continuous position in card-units. This
     file owns what that number LOOKS like, and nothing else. The two do not
     know about each other beyond that number, which is what makes the engine
     reusable for the next carousel this app grows.

     Every frame, every card is placed as a function of its distance from the
     wheel's current position — never as a function of which card is
     "selected". So nothing is ever assigned a state and nothing jumps: the
     whole rail interpolates because there is only ever one input.

     Per-frame writes are transform, opacity, filter and z-index only. No
     layout property is touched and no layout property is READ; the two
     measurements the placement needs (card width, track width) are taken in
     measureRail() when the DOM actually changes, and cached. That is what
     keeps this at frame rate with a dozen cards on screen. */
  const RAIL = {
    gap: 0.62,        // horizontal travel per card-unit, as a fraction of pitch
    depth: 210,       // px pushed back per card-unit away
    turn: 27,         // degrees of Y rotation per card-unit
    shrink: 0.11,     // scale lost per card-unit, to 1 unit
    dim: 0.34,        // brightness lost per card-unit, to 1 unit
    blur: 1.5,        // px of blur per card-unit, to 2 units
    fade: 0.30,       // opacity lost per card-unit, from unit 1 outward
    visible: 3.4,     // beyond this many units a card is not rendered at all
  };
  /* ONE RAIL IMPLEMENTATION, MANY RAILS.
     wheel.js owns the physics and knows nothing about cards; this owns what
     the physics LOOK like and knows nothing about which rail it is driving.
     Every carousel on the surface — the mission wheel and all four Overwatch
     groups — is an instance of this, so they cannot drift into behaving
     differently, and the next one costs a single call. */
  const rails = new Map();          // track element -> instance

  function makeRail(track, opts){
    opts = opts || {};
    const st = {track, cards: [], pitch: 320, wheel: null, tilt: {x: 0, y: 0}};

    /* The only place that reads layout. Called when cards arrive or the
       viewport changes — never from the frame loop. */
    function measure(){
      st.cards = [...track.querySelectorAll('.mc')];
      const w = st.cards.length ? st.cards[0].getBoundingClientRect().width : 0;
      st.pitch = Math.max(120, w || Math.min(340, track.clientWidth * 0.86));
      let h = 0;
      for(const c of st.cards) h = Math.max(h, c.offsetHeight);
      const flat = track.querySelector(':scope > .empty, :scope > .mb-seg > .empty, ' +
                                       ':scope > .mb-seg > .skeleton');
      if(flat) h = Math.max(h, flat.offsetHeight);
      /* Padding has to be added on: `* { box-sizing: border-box }` is global,
         so a bare height makes the CONTENT box that tall and the card hangs
         out of a track whose overflow:hidden then cuts it — losing exactly
         the shadow the lift exists to show. */
      if(h){
        const cs = getComputedStyle(track);
        track.style.height =
          (h + parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)) + 'px';
      }
      track.classList.toggle('has-wheel', st.cards.length > 0);
    }

    function place(c, d){
      const ad = Math.abs(d);
      if(ad > RAIL.visible){
        if(c.style.display !== 'none') c.style.display = 'none';
        return;
      }
      if(c.style.display === 'none') c.style.display = '';
      const near = Math.min(ad, 1);
      const tw = opts.tilt ? Math.max(0, 1 - ad * 2) : 0;
      const tx = st.tilt.x * tw, ty = st.tilt.y * tw;
      c.style.transform =
        `translate3d(${(d * st.pitch * RAIL.gap).toFixed(2)}px,0,${
          (-ad * RAIL.depth + (tw ? tw * 14 : 0)).toFixed(2)}px) rotateY(${
          (-d * RAIL.turn + ty).toFixed(3)}deg) rotateX(${
          tx.toFixed(3)}deg) scale(${(1 - near * RAIL.shrink).toFixed(4)})`;
      c.style.opacity = (1 - Math.min(Math.max(ad - 1, 0), 2) * RAIL.fade).toFixed(3);
      const blur = Math.round(Math.min(ad, 2) * RAIL.blur * 10) / 10;
      const bright = (1 - near * RAIL.dim).toFixed(3);
      const f = blur > 0.05 ? `blur(${blur}px) brightness(${bright})`
                            : `brightness(${bright})`;
      if(c.style.filter !== f) c.style.filter = f;
      c.style.zIndex = String(Math.max(1, 100 - Math.round(ad * 30)));
      c.classList.toggle('flip-r', d > 0);
      const centered = ad < 0.5;
      c.classList.toggle('is-center', centered);
      c.style.pointerEvents = centered ? '' : 'none';
      c.setAttribute('aria-hidden', centered ? 'false' : 'true');
    }

    function navState(){
      if(!st.wheel) return;
      const i = st.wheel.nearest();
      const prev = opts.prev && $(opts.prev), next = opts.next && $(opts.next);
      if(prev){ prev.hidden = st.cards.length < 2; prev.disabled = i <= 0; }
      if(next){ next.hidden = st.cards.length < 2; next.disabled = i >= st.cards.length - 1; }
      const live = opts.status && $(opts.status);
      if(live && st.cards[i]){
        /* THE POSITION IS ANNOUNCED EVEN WHEN THE CARD HAS NO SYMBOL. This
           read `.mc-tok` only and wrote an empty string when it found none —
           so on every rail whose cards are not trades (the stat wheel, the
           progression track) a screen reader was told nothing at all as the
           wheel turned, which is the exact hint a sighted reader gets from
           the cards moving. Title first if the card has one, then its verdict,
           then where it sits. */
        const tok = st.cards[i].querySelector('.mc-tok, .prog-title, .stat-big');
        const stamp = st.cards[i].querySelector('.mc-stamp');
        live.textContent = [
          tok && tok.textContent.trim(),
          stamp && stamp.textContent.trim().toLowerCase(),
          `${i + 1} of ${st.cards.length}`,
        ].filter(Boolean).join(', ');
      }
    }

    st.sync = function(){
      /* A hidden track measures as zero and would place every card at the
         same spot. Skip, and let whoever reveals it sync then. */
      if(!track.offsetParent && track.style.display !== '') return;
      measure();
      if(st.wheel) st.wheel.resync();
      else st.cards.forEach((c, i) => place(c, i));
      navState();
    };

    st.wheel = window.SSWheel.create(track, {
      count: () => st.cards.length,
      pitch: () => st.pitch * RAIL.gap,
      onFrame: pos => {
        for(let i = 0; i < st.cards.length; i++) place(st.cards[i], i - pos);
      },
      onRest: navState,
    });

    const prev = opts.prev && $(opts.prev), next = opts.next && $(opts.next);
    if(prev) prev.addEventListener('click', () => st.wheel.goTo(st.wheel.nearest() - 1));
    if(next) next.addEventListener('click', () => st.wheel.goTo(st.wheel.nearest() + 1));

    /* Click a card that is not in front and it comes to the front. Its own
       controls are pointer-inert while it is behind, so that is the only
       thing a click on a side card can mean. */
    track.addEventListener('click', e => {
      const card = e.target.closest('.mc');
      if(!card) return;
      const i = st.cards.indexOf(card);
      if(i < 0 || i === st.wheel.nearest()) return;
      e.preventDefault(); e.stopPropagation();
      st.wheel.goTo(i);
    });

    track.addEventListener('keydown', e => {
      const k = e.key;
      if(k !== 'ArrowLeft' && k !== 'ArrowRight' && k !== 'Home' && k !== 'End') return;
      e.preventDefault();
      const n = st.cards.length - 1;
      st.wheel.goTo(k === 'ArrowLeft' ? st.wheel.nearest() - 1
                  : k === 'ArrowRight' ? st.wheel.nearest() + 1
                  : k === 'Home' ? 0 : n);
    });

    // tabbing into a card behind the front one must bring it forward
    track.addEventListener('focusin', e => {
      const card = e.target.closest('.mc');
      if(!card) return;
      const i = st.cards.indexOf(card);
      if(i >= 0 && i !== st.wheel.nearest()) st.wheel.goTo(i);
    });

    if(opts.tilt && matchMedia('(hover: hover) and (pointer: fine)').matches &&
       !matchMedia('(prefers-reduced-motion: reduce)').matches){
      track.addEventListener('pointermove', e => {
        if(st.wheel.isDragging()) return;
        const card = st.cards[st.wheel.nearest()];
        if(!card) return;
        const r = card.getBoundingClientRect();
        const nx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
        const ny = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
        st.tilt.y = Math.max(-1, Math.min(1, nx)) * 3.2;
        st.tilt.x = Math.max(-1, Math.min(1, -ny)) * 2.2;
        st.wheel.resync();
      });
      track.addEventListener('pointerleave', () => {
        if(!st.tilt.x && !st.tilt.y) return;
        st.tilt.x = st.tilt.y = 0;
        st.wheel.resync();
      });
    }

    rails.set(track, st);
    return st;
  }

  /* Attach a wheel to any track that does not have one yet, and re-sync the
     ones that do. renderNear replaces its rails wholesale on every poll, so
     the map is swept of tracks the document no longer holds — otherwise each
     30s cycle would leak an engine and its listeners. */
  function mountRails(root){
    for(const [el, st] of rails){
      if(!el.isConnected){ st.wheel.destroy(); rails.delete(el); }
    }
    const seen = [];
    if(root && root.classList && root.classList.contains('wheel-rail')) seen.push(root);
    (root || document).querySelectorAll('.wheel-rail').forEach(el => seen.push(el));
    seen.forEach(el => {
      const st = rails.get(el) || makeRail(el, {});
      st.sync();
    });
  }

  /* The mission wheel is just an instance of the shared rail, with the extras
     only the hero earns: nav buttons, a live region, and the cursor tilt. */
  let missionRail = null;
  function missionRailSync(){
    const track = $('mbTrack');
    if(!track || !window.SSWheel) return;
    if(!missionRail)
      missionRail = makeRail(track, {prev: 'mbPrev', next: 'mbNext',
                                     status: 'mbStatus', tilt: true});
    missionRail.sync();
  }

  /* The operator's own book rides the same rail, with the same extras. It is
     the third instance of makeRail on this surface and it cost one call, which
     is the point of the shared implementation. */
  let mineRail = null;
  function mineRailSync(){
    const track = $('mine');
    if(!track || !window.SSWheel) return;
    if(!mineRail){
      /* A bare mountRails() sweep — the resize handler runs one — walks every
         .wheel-rail in the document and attaches a CHROME-LESS instance to any
         it does not know. #mine starts inside a display:none panel, so it can
         be claimed that way before this panel has ever painted, and a second
         makeRail on the same element would leave two wheels fighting over one
         drag. Take the track back rather than doubling up. */
      const stale = rails.get(track);
      if(stale){ stale.wheel.destroy(); rails.delete(track); }
      mineRail = makeRail(track, {prev: 'minePrev', next: 'mineNext',
                                  status: 'mineStatus'});
    }
    mineRail.sync();
  }

  let railResizeT = 0;
  addEventListener('resize', () => {
    clearTimeout(railResizeT);
    railResizeT = setTimeout(() => {
      missionRailSync(); mineRailSync(); mountRails();
    }, 120);
  });

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
  let lastJournal = [];                // the closed book, for Export
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

  /* ---------- the mission ring ----------
     One SVG ring, two real numbers, zero scores. A ready card's ring is the
     fraction of its life remaining (expiry minus now, over expiry minus
     found); a forming card's ring is how close price stands to the zone,
     scaled against the engine's own proximity bound. Both are live facts the
     engine already publishes — this app records no confidence percentage and
     the ring must never be mistaken for one, which is why the label inside it
     names the unit every time. */
  function ringSvg(frac, cls, big, small){
    const f = Math.max(0, Math.min(1, frac));
    const C = 2 * Math.PI * 26;               // r=26 viewBox circle
    return `<div class="mc-ring ${cls}" aria-hidden="true">
      <svg viewBox="0 0 64 64">
        <circle class="mc-ring-track" cx="32" cy="32" r="26"/>
        <circle class="mc-ring-fill" cx="32" cy="32" r="26"
          stroke-dasharray="${C.toFixed(2)}" stroke-dashoffset="${(C * (1 - f)).toFixed(2)}"/>
      </svg>
      <div class="mc-ring-label"><b>${big}</b><span>${small}</span></div>
    </div>`;
  }

  /* ---------- the trade ladder ----------
     Stop, entry and target drawn where they actually sit, to scale. This is
     the card's picture and it is deliberately NOT a price chart: the payload
     carries no candles, and a decorative squiggle would be the one dishonest
     pixel on the surface. The three numbers are the engine's own strings
     through px(); the floats below position them and are never displayed —
     presentation geometry, not a second authority on price. */
  function ladderHtml(s, price){
    const e = parseFloat(s.entry), t = parseFloat(s.tp), l = parseFloat(s.sl);
    if(!isFinite(e) || !isFinite(t) || !isFinite(l) || t === l) return '';
    /* On a live trade the ladder gains a marker for where price actually is.
       The scale stretches to include it, so a trade that has run past its
       target still draws honestly instead of pinning the marker to an edge
       and implying it stopped there. */
    const live = price != null && isFinite(price) ? +price : null;
    const hi = Math.max(e, t, l, live == null ? -Infinity : live);
    const lo = Math.min(e, t, l, live == null ? Infinity : live);
    // map price -> 10%..90% of the column so edge labels keep their room
    const y = p => 10 + (1 - (p - lo) / (hi - lo)) * 80;
    const band = (a, b, cls) => {
      const top = Math.min(y(a), y(b));
      return `<div class="lad-band ${cls}" style="top:${top.toFixed(1)}%;height:${
        Math.abs(y(a) - y(b)).toFixed(1)}%"></div>`;
    };
    const lv = (p, cls, name, val) =>
      `<div class="lad-lv ${cls}" style="top:${y(p).toFixed(1)}%">
        <span class="lad-name">${name}</span><b class="t-mono">${val}</b></div>`;
    return `<div class="mc-ladder">
      ${band(e, t, 'reward')}${band(e, l, 'risk')}
      ${lv(t, 'tp', 'target', px(s.tp))}
      ${lv(e, 'en', 'entry', px(s.entry))}
      ${lv(l, 'sl', 'stop', px(s.sl))}
      ${live == null ? '' :
        `<div class="lad-now" style="top:${y(live).toFixed(1)}%"><b class="t-mono">${
          px(String(live))}</b></div>`}
    </div>`;
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
            ? `<div class="t-label cap" style="margin-top:4px;color:var(--red-2)">${
                reasonText(r.reasons)}</div>`
            : `<div class="t-label" style="margin-top:4px">risks ${moneyOr(r.risk_usd) || '—'}${
                r.units ? ' · ' + Number(r.units).toLocaleString() + ' units' : ''}</div>`)
        : '<span class="chip">awaiting decision</span>' +
          '<div class="t-label" style="margin-top:4px">the risk rules have not ruled on this one yet</div>';

      /* The banner states what the card IS before a single number is read:
         the risk verdict, in the deck's own established words. A card with no
         verdict yet says so. The stamp is the differentiation the rail runs
         on — READY draws the accent, REDUCED is amber, NOT TRADED is grey-red
         and only ever appears in the refused strip below the rail. */
      const stamp = dec === 'APPROVED' ? ['st-go', 'READY']
                  : dec === 'REDUCED'  ? ['st-warn', 'REDUCED SIZE']
                  : dec === 'REJECTED' ? ['st-dead', 'NOT TRADED']
                  : ['st-wait', 'AWAITING VERDICT'];

      /* Life remaining, as a fraction of this setup's own window. Both ends
         come off the fact (found + expiry, epoch seconds); a card with no
         expiry renders a full quiet ring rather than inventing an urgency. */
      const born = s.armed_at || s.confirmed_bar_ts || s.market_time;
      const exp = s.expires_at_ts;
      const lifeFrac = (exp && born && exp > born)
        ? (exp - now) / (exp - born) : 1;
      const expTxt = expiresIn(exp, now);                 // "expires in 4h"
      const expBig = exp ? expTxt.replace(/^expires in /, '').replace(/^expiring now$/, 'now') : '—';
      const urgency = lifeFrac <= 0.25 ? 'ring-low' : lifeFrac <= 0.5 ? 'ring-mid' : 'ring-ok';

      // wrapper element and its .dead class are owned by renderDeck's differ;
      // this returns the card's CONTENTS only
      return `
        <div class="mc-top">
          <span class="mc-stamp ${stamp[0]}">${stamp[1]}</span>
          <span class="mc-id t-mono" title="${foundTitle(s)}">${foundAgo(s, now)}</span>
        </div>
        ${heldBadge(s)}
        <div class="mc-hero">
          <div class="mc-idy">
            <div class="mc-tok t-mono">${esc(tokenOf(s.symbol))}</div>
            <div class="mc-sub t-label" title="${esc(s.symbol)}">${s.symbol.replace('-USD','')} · ${s.tf} · ${playbookLabel(s.strategy)}</div>
            <div class="mc-dirline">
              <span class="chip ${long ? 'chip-green' : 'chip-red'}">${s.direction}</span>
              <span class="t-label">${htfChip(s)}</span>
            </div>
          </div>
          <div class="mc-ringcol">
            ${ringSvg(lifeFrac, urgency, esc(expBig), exp ? 'left' : 'no expiry')}
            <!-- The sort key, made visible. A rail ordered by something the
                 operator cannot see is worse than one ordered by a bad score. -->
            <div class="t-label mc-exp" title="how long this setup stays live"><span class="term" data-t="horizon">${expTxt}</span></div>
          </div>
        </div>
        ${ladderHtml(s) || `<div class="mc-nums t-mono">
          entry <b style="color:var(--fg)">${px(s.entry)}</b> ·
          tp <b style="color:var(--green)">${px(s.tp)}</b> ·
          sl <b style="color:var(--red-2)">${px(s.sl)}</b>
        </div>`}
        <div class="mc-nums t-mono"><span class="term" data-t="rr">R:R</span>
          <b style="color:var(--fg)">${s.rr}</b></div>
        <div class="mc-story">${storyOf(s)}</div>
        <div class="traceable" data-trace="${esc(s.setup_id || '')}"
             title="click to see what this setup passed and what it failed — the zone, the confirmation, and every check">${verdict}</div>
        <div class="mc-acts">
          ${dec === 'REJECTED' && r && (r.reasons || []).length
            ? `<button class="btn btn-why" data-reasons="${esc((r.reasons || []).join('|'))}"
                       data-rsym="${esc(tokenOf(s.symbol))}"
                       title="the plain-English reason this was refused">Reasons</button>`
            : `<button class="btn" data-copilot="1" data-sym="${s.symbol}" data-tf="${s.tf}"
                       data-sid="${esc(s.setup_id || '')}"
                       title="ask the copilot about this setup — it reads the trace and cannot arm">Ask copilot</button>`}
          <button class="btn${mine ? ' btn-amber' : ''}" data-sym="${s.symbol}" data-tf="${
            mine ? heldSyms.get(s.symbol).tf : s.tf}"
                  title="${mine ? 'open the chart on the trade you are holding — the ticket manages it'
                                : 'open this plan on the chart'}">${
            mine ? 'Manage trade' : 'Open chart'}</button>
        </div>`;
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
    const box = $('radar'), chip = $('radarCount');
    list = list || [];
    if(chip){
      chip.hidden = !list.length;
      chip.textContent = list.length + ' forming';
    }
    if(!list.length){
      box.innerHTML = ''; radarRows.clear(); missionRailSync(); return;
    }
    /* Keyed diff, same discipline as the deck differ above and for the same
       reason: this rail repaints on a 30s poll, and a wholesale innerHTML
       rebuilt every forming card — destroying the button under a pointer
       already on its way down, on the rail whose CSS promises a repaint
       never moves a card. Survivors keep their node; only a card whose
       content actually changed is patched. */
    const seenR = new Set();
    list.forEach(s => {
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
      /* A forming card wears the same dossier silhouette as a ready one and
         earns none of its controls: no verdict, no arm, nothing to trace.
         The amber stamp and the watch-only tag are the differentiation, and
         the ring is the radar meter promoted — same fill, same bound, drawn
         where the ready card draws its countdown so the two reads sit in the
         same place on every card. */
      const html = `
        <div class="mc-top">
          <span class="mc-stamp st-form">FORMING</span>
          <span class="mc-id t-mono">watch-only</span>
        </div>
        <div class="mc-hero">
          <div class="mc-idy">
            <div class="mc-tok t-mono">${esc(tokenOf(s.symbol))}</div>
            <div class="mc-sub t-label" title="${esc(s.symbol)}">${esc(String(s.symbol).replace('-USD',''))} · ${s.tf} · ${playbookLabel(s.strategy)}</div>
            <div class="mc-dirline">
              <span class="chip ${long ? 'chip-green' : 'chip-red'}">${long ? 'LONG' : 'SHORT'}</span>
            </div>
          </div>
          <div class="mc-ringcol">
            ${ringSvg(fill / 100, 'ring-form', isNaN(d) ? '—' : d.toFixed(1),
              /* "at arm", not "away": the reading is a one-shot measurement
                 taken when the setup armed, and the ring must not restate a
                 dated fact in the present tense. The caption below carries
                 the full dated sentence. */
              'ATR at arm')}
            <div class="t-label mc-exp">${isNaN(d) ? '' : d.toFixed(1) + ' ATR away' + esc(agoTxt)}</div>
          </div>
        </div>
        <div class="radar-say mc-say">${verb} <b>${esc(zone)}</b>. Becomes a trade only if price
          gets there and a candle confirms.</div>
        <div class="mc-acts">
          <button class="btn" data-rsym="${esc(s.symbol)}" data-rtf="${esc(s.tf)}">Open chart</button>
        </div>`;
      const key = s.symbol + '|' + s.tf;
      seenR.add(key);
      let rec = radarRows.get(key);
      if(!rec){
        const node = document.createElement('article');
        node.className = 'mc forming radar-card';
        node.innerHTML = html;
        rec = {el: node, html};
        radarRows.set(key, rec);
      }else if(rec.html !== html){
        rec.el.innerHTML = html; rec.html = html;
      }
      box.appendChild(rec.el);         // appendChild MOVES an existing node
    });
    for(const [key, rec] of radarRows){
      if(seenR.has(key)) continue;
      rec.el.remove(); radarRows.delete(key);
    }
    box.querySelectorAll('button[data-rsym]').forEach(b => {
      if(b.dataset.wired) return;      // survivors keep their handler
      b.dataset.wired = '1';
      b.addEventListener('click', () => {
        go('chart');
        if(window.SSChart) SSChart.open(b.dataset.rsym, b.dataset.rtf);
      });
    });
    missionRailSync();
  }
  const radarRows = new Map();         // symbol|tf -> {el, html}

  /* At a level: where price is standing near structure, across every tradeable
     market at once.

     DESCRIPTIVE, NOT PRESCRIPTIVE, and the row shape enforces it. The endpoint
     returns a full bracket per row — it is the same draft.for_symbol() the
     ticket calls — and this deliberately renders only the zone and the
     distance. An entry, a stop and a target laid out in a Command-tab row read
     as advice no matter what the heading says, which is the exact misreading
     that made this panel necessary: a bracket drawn on a chart the engine had
     never looked at was taken for the engine's own plan. The numbers are one
     click away on the chart, where the ticket says whose plan they are.

     `engine_reach` comes from the payload rather than being recomputed from
     distance here. The bounds it is derived from (setups.PROX_ATR,
     FORMING_TFS) are the engine's, and a second copy in the client is a second
     answer waiting to drift. */
  /* The label is the threat step; the sentence under it is what that step
     MEANS. Both are needed and neither substitutes for the other — a
     newcomer cannot decode "CONTACT" alone, and "Price is inside the zone"
     alone does not rank against the card beside it. Labels are short because
     they are labels; sentences are one line because the old ones ran to
     three and nobody read the third.

     Only the SENTENCE (index 2) is read. The label and the chip class in
     indices 0 and 1 are leftovers from the tabbed rail: the card takes its
     word and its colour from the one Reach & Play scale now, and the
     `chip-t*` rules those strings named have been deleted from ss.css. */
  const NEAR_SAY = {
    AT_ZONE: () =>
      ['CONTACT', 'chip-t3',
       'Price is in the zone. If the engine takes it, it appears in Mission Briefs.'],
    IN_RANGE: () =>
      ['TRACKING', 'chip-t2',
       'Close enough that the engine is considering this zone. Most never become setups.'],
    NO_FORMING_ON_TF: (r) =>
      ['HOLDING', 'chip-t1',
       `The engine does not plan ahead on ${r.tf}. It acts only once price arrives.`],
    OUT_OF_RANGE: (r, prox) =>
      ['OUT OF REACH', 'chip-t0',
       `Past the ${prox} ATR the engine looks, so it is not considering this ` +
       'zone. Anything the chart draws here is the chart\'s, not the engine\'s.'],
  };

  /* ---------- Overwatch: the two halves of "what is this market doing" ----
     Market Weather answered "what condition is this market in"; At-a-level
     answered "is price anywhere near a level in it". They listed the SAME
     symbols in two tables a screen apart, so answering the obvious combined
     question meant holding one in your head while scrolling to the other.

     One card per market now. Neither number is re-derived here — the regime
     and its bias are quoted from /api/weather exactly as weather.js quotes
     them, the distance and the reach chip from /api/near-levels, which stays
     the only authority on whether the engine is even looking at that zone.
     This function decides layout and nothing else. */
  function weatherIndex(w){
    const by = new Map();
    for(const s of (w && w.symbols) || []) by.set(s.symbol, s);
    return by;
  }

  /* ═══════════ ONE SCALE FOR "COULD I TRADE THIS?" — REACH & PLAY ═══════════

     There were THREE badge vocabularies for one question, and a letter grade
     restating all of them. The same market rendered CONTACT (green) under one
     tab and NO PLAY (grey) under the next, carrying the identical letter B on
     both, because the tabs were never a partition — the all-markets list was a
     superset of the near-level list, and the badge slot silently changed its
     question depending on which one you were looking at. Counted live: 12
     cards showing CONTACT/TRACKING/HOLDING beside grades B and C, 21 showing
     OUT OF REACH beside grade D every single time, and 31 showing
     PLAYABLE/NO PLAY beside B, C and D.

     One badge now, in one slot, on every card on every surface. It states two
     facts and fuses neither:

       REACH — 1:1 with the engine's own `engine_reach` (nearlevels.py). Four
               values in, four words out, no fifth invented.
       PLAY  — from weather's `live`: does any playbook trade this market's
               condition. Only ever printed when it is NOT favourable, because
               the good case is the quiet case.

     The two are deliberately NOT merged into a single tier word. nearlevels
     refuses to model playbook coverage and the weather engine knows nothing of
     distance; a word ordering both would be a claim neither engine makes, and
     the off-diagonal cases (in the zone with no playbook; far out with one)
     would misread under any total order. So the words stay separate and only
     the COLOUR carries the combined rank — which is enough to sort by, and
     honest, because every card prints the sentence that produced it. */
  const REACH_WORD = {
    AT_ZONE:          'IN THE ZONE',
    IN_RANGE:         'NEARBY',
    NO_FORMING_ON_TF: 'NOT PLANNED HERE',
    OUT_OF_RANGE:     'OUT OF REACH',
  };
  /* Rank 3..0. The lattice is the one the old grade already computed — it was
     never wrong, it was just printed as an uninterpretable letter beside a
     word that contradicted it. */
  function reachPlay(reach, live){
    const r = REACH_WORD[reach] ? reach : 'OUT_OF_RANGE';
    const word = REACH_WORD[r];
    /* THREE play states, not two. A symbol the weather payload does not carry
       has no reading, and an absent reading must never be drawn as a flat one
       — that is the same rule the regime strip already follows. */
    const play = live === true ? 'yes' : live === false ? 'no' : 'unknown';
    const suffix = play === 'no' ? ' · NO PLAY'
                 : play === 'unknown' ? ' · NO READ' : '';
    let rank;
    if(r === 'AT_ZONE')               rank = play === 'yes' ? 3 : 2;
    else if(r === 'IN_RANGE')         rank = play === 'yes' ? 2 : 1;
    else if(r === 'NO_FORMING_ON_TF') rank = 1;
    else                              rank = 0;
    /* The basis, in one sentence, on the card. A badge whose reasoning is not
       on screen is the uncalibrated score this product exists to refuse. */
    const why =
      r === 'AT_ZONE' && play === 'yes'
        ? 'Price is in the zone and a playbook trades this condition.'
      : r === 'AT_ZONE'
        ? 'Price is in the zone, but no playbook covers this condition.'
      : r === 'IN_RANGE' && play === 'yes'
        ? 'Close to the zone and a playbook trades this condition.'
      : r === 'IN_RANGE'
        ? 'Close to the zone; no playbook covers this condition.'
      : r === 'NO_FORMING_ON_TF'
        ? 'Near, but the engine does not plan ahead on this timeframe.'
        : 'Further out than the engine looks. It is not considering this.';
    return {word, suffix, label: word + suffix, rank,
            stamp: 'st-t' + rank, cls: 't' + rank,
            ring: ['ring-dim', 'ring-cy', 'ring-mid', 'ring-ok'][rank], why};
  }

  /* The engine's universe state, in words. It was printed as a raw enum. */
  const UNIVERSE_LABEL = {
    ADMITTED: 'Tradeable', SHADOW: 'Shadow — never sized',
    WARMING: 'Warming up', UNTRACKED: 'Not in the universe',
  };

  /* ONE RANKED DECK. Four tabs became one rail.

     The tabs were never a partition — "All markets" iterated the whole
     weather universe while "Manual setups" iterated near-level rows, so the
     same symbol appeared on both wearing two different badges. And "Out of
     reach" was pure redundancy: every card on it was the bottom rank, 21
     times out of 21.

     So: one card per MARKET over the watched universe, each carrying its
     nearest zone row, sorted by rank and then by distance. The engine's own
     bound is no longer a tab — it is the grey bottom of one ordering, which
     is what it always was.

     What is lost is a second card for a symbol at AT_ZONE on 15m and
     IN_RANGE on 4H; the nearest row wins. The per-timeframe regime strip
     still prints every timeframe with its label bound to it, so nothing about
     the market's condition is hidden — only the duplicate card is. */
  function renderNear(d, weather){
    const panel = $('nearPanel'), box = $('near');
    const rows = (d && d.rows) || [];
    if(!rows.length){ panel.style.display = 'none'; box.innerHTML = ''; return; }
    panel.style.display = '';
    const c = d.counts || {};
    const prox = d.prox_atr, max = d.max_distance_atr;
    const wx = weatherIndex(weather);

    /* ONE DENOMINATOR. Three rings drew the same ATR figure at three
       different lengths — one divided by prox_atr, one by max_distance_atr,
       one by a hard-coded 3 — so a card could show 0.6 ATR fuller than a card
       showing 0.4. Both bounds ride on the payload for exactly this reason;
       the rail uses the sweep's own outer bound throughout. */
    const bound = parseFloat(max) || 3;
    const fillOf = dist => isNaN(dist) || !isFinite(dist) ? 6
      : Math.max(6, Math.min(96, (1 - dist / bound) * 100));

    /* Nearest row per SYMBOL. The sweep is per symbol AND timeframe, and a
       market can be at a zone on one timeframe and nowhere on another; the
       closest is the honest one-line summary. */
    const nearestBySym = new Map();
    for(const r of rows){
      const dv = parseFloat(r.distance_atr);
      const cur = nearestBySym.get(r.symbol);
      if(!cur || (!isNaN(dv) && dv < cur.d))
        nearestBySym.set(r.symbol, {d: isNaN(dv) ? 99 : dv, r});
    }

    /* The deck covers the union: every market the weather engine reports,
       plus any swept symbol weather does not carry. A market missing from one
       source is shown with that half marked unknown rather than dropped. */
    const symbols = new Set([...wx.keys(), ...nearestBySym.keys()]);
    const cards = [...symbols].map(sym => {
      const w = wx.get(sym) || null;
      const hit = nearestBySym.get(sym) || null;
      const reach = hit ? hit.r.engine_reach : 'OUT_OF_RANGE';
      const rp = reachPlay(reach, w ? !!w.live : null);
      const sayFn = NEAR_SAY[reach] || NEAR_SAY.OUT_OF_RANGE;
      return {sym, w, hit, rp,
              dist: hit ? hit.d : Infinity,
              say: sayFn(hit ? hit.r : {tf: ''}, prox)};
    }).sort((a, b) => b.rp.rank - a.rp.rank || a.dist - b.dist);

    $('nearCount').textContent = `${c.in_engine_range || 0} in reach`;
    /* Says what was swept and what was left out — a list that cannot name its
       exclusions reads as a complete one — then states the ranking rule,
       because a sorted deck whose basis is unstated is a ranking nobody can
       check. */
    $('nearLede').textContent =
      `${c.symbols} markets swept, ${rows.length} standing within ${max} ATR of a zone. ` +
      `${c.shadow_excluded} shadow markets are excluded — the risk authority never sizes them. ` +
      `Ranked on both halves of the badge together — how close price is to a zone ` +
      `the engine watches, and whether a playbook trades this market's condition. ` +
      `A market sitting in its zone with no playbook ranks level with one nearby ` +
      `that has one; distance breaks the tie.`;

    /* Degraded loudly: a market whose structure could not be read is MISSING
       from this list, and silence would read as "price is not near a level
       there" — the strongest possible wrong answer. */
    const warn = (d.warnings || []).length
      ? `<div class="deck-divider" style="color:var(--amber)">${esc(d.warnings.length +
          ' market(s) could not be read and are missing from this list')}</div>`
      : '';

    const cardHtml = k => {
      const w = k.w, hit = k.hit, rp = k.rp, say = k.say;
      /* draft.py's own sentence for the zone, lead-in trimmed and first
         letter raised. The engine's words stay the engine's. */
      const zone = hit
        ? ((hit.r.basis || [])[0] || 'A live zone')
            .replace(/([\d.]+)–([\d.]+)/, (m, a, b) => `${px(a)}–${px(b)}`)
            .replace(/^nearest live /, '').replace(/^./, ch => ch.toUpperCase())
        : 'No live zone within the swept range.';
      const regimes = w && (w.timeframes || []).length
        ? `<div class="wl-wx">
            <div class="wl-regs">${w.timeframes.map(t =>
              `<span class="wl-reg${t.bias === 'LONG' ? ' up' : t.bias === 'SHORT' ? ' dn' : ''}">
                <b>${esc(t.tf)}</b>${esc(t.label || '—')}</span>`).join('')}</div>
            <div class="wl-mean${w.live ? ' live' : ''}">${esc(w.meaning || '')}</div>
          </div>`
        : '';
      const chartTf = hit ? hit.r.tf
        : (w && w.timeframes && w.timeframes[0] && w.timeframes[0].tf) || '4H';
      return `<div class="mc wl-card ${rp.cls}">
        <div class="mc-top">
          <span class="mc-stamp ${rp.stamp}">${esc(rp.label)}</span>
          <span class="mc-id t-mono">${hit ? esc(hit.r.tf) + ' · ' +
            (hit.r.direction === 'LONG' ? 'Long' : 'Short') : 'no zone'}</span>
        </div>
        <div class="mc-hero">
          <div class="mc-idy">
            <div class="mc-tok t-mono">${esc(tokenOf(k.sym))}</div>
            <div class="mc-sub t-label" title="${esc(k.sym)}">${
              esc(String(k.sym).replace('-USD', ''))}${
              w && w.state ? ' · ' + esc(UNIVERSE_LABEL[w.state] || w.state) : ''}</div>
            <div class="t-label wl-why">${esc(rp.why)}</div>
          </div>
          <div class="mc-ringcol">
            ${ringSvg(fillOf(k.dist) / 100, rp.ring,
                      isFinite(k.dist) ? k.dist.toFixed(2) : '—', 'ATR away')}
            <div class="t-label mc-exp">To the zone</div>
          </div>
        </div>
        ${regimes}
        <div class="mc-nums t-mono">${esc(zone)}</div>
        <div class="mc-story radar-say">${esc(say[2])}</div>
        <div class="mc-acts">
          <button class="btn" data-nsym="${esc(k.sym)}" data-ntf="${esc(chartTf)}">Open chart</button>
        </div>
      </div>`;
    };

    box.innerHTML = warn + (cards.length
      ? `<div class="wl-rail wheel-rail" tabindex="0" role="group"
              aria-label="markets — use left and right arrow keys">${
           cards.map(cardHtml).join('')}</div>`
      : '<div class="empty mw-empty">No market condition has been reported yet.</div>');

    box.querySelectorAll('button[data-nsym]').forEach(b =>
      b.addEventListener('click', () => {
        go('chart');
        if(window.SSChart) SSChart.open(b.dataset.nsym, b.dataset.ntf);
      }));
    mountRails(box);
  }


  /* The four Overwatch tabs are gone. They were never a partition — the
     all-markets list was a superset of the near-level list — so the same
     symbol appeared twice wearing two different badges. One ranked deck
     replaces them (renderNear above); the refused setups moved to their own
     home. MW_GROUPS, mwShow, mwCounts and wireMarketWatch went with the
     tab strip they drove. */
  async function loadNearLevels(){
    /* Weather comes from the SHARED cache, never a second fetch. weather.js
       already subscribes to this path on a 30s cadence, so SSData hands back
       the very payload that module is rendering from — which is the whole
       point of that layer. Two fetches would also mean two moments, and the
       merged card would show a regime from one instant beside a distance
       from another. maxAge is generous for the same reason: this rail wants
       the payload on screen, not a fresher one. */
    const [levels, weather] = await Promise.all([
      api('/api/near-levels'),
      window.SSData ? window.SSData.get('/api/weather', 60000).catch(() => null)
                    : Promise.resolve(null),
    ]);
    renderNear(levels, weather);
  }

  /* Open trades, drawn on the surface that asks what to do next.

     `active_positions` has been in the portfolio payload the whole time and
     reached no surface at all: an open trade appeared only inside the chart's
     order ticket, and only while you happened to be looking at that symbol's
     chart. "What am I in right now" cost one navigation per position.

     One last close per open symbol is what turns a plan into a position — it
     says whether the trade is winning and how far it is from either end. A
     price that will not load costs that row its marker, never the row. */
  /* The question the Open Trades panel asks on the operator's behalf. Written
     for a trade ALREADY TAKEN: the copilot's default instinct is to weigh an
     entry, which is the one question that is settled by the time a row exists
     in this panel. Concise because it is read between bars. */
  /* OFFERED, NOT SENT. This used to be composed and fired the instant the
     button was clicked, so the operator's first sight of the dock was their
     own name above a paragraph they had not written. Operator ruling,
     4 Aug 2026: the box is theirs. It is now the first suggestion chip —
     one tap to fill, then edit or discard. Still composed rather than typed,
     because it is long and carries this trade's own levels, which is exactly
     the question nobody wants to retype between bars. */
  const holdAsk = t => `I am already in this trade: ${t.direction} ${
    tokenOf(t.symbol)} on ${t.tf}, entry ${t.entry}, stop ${t.sl}, target ${
    t.tp}. Do not evaluate whether to enter — that is done. Give me, in a few
short paragraphs: where this trade actually stands right now against the
facts in the pack; what would have to happen for the thesis to be wrong;
and a concrete recommendation — hold, tighten the stop (to what price and
why), or close — with the round-trip cost and the recorded edge state
weighed in. Name the facts you used.`;

  /* THE BOOK IS THE MISSION RAIL. This used to render a second, row-shaped
     copy of active_positions and pending_orders into an "Engaged — detail"
     panel on Command — the same two arrays renderMissions builds, on the same
     surface, under a different shape. The operator called it what it was: a
     duplicate.

     Everything it owned travelled onto the mission card first: the symbol is
     a real <button> carrying data-manage (so Enter and Space come from the
     platform rather than a hand-rolled keydown), the Reasons control keeps
     data-trace, the composed hold question keeps data-ask, and Close keeps
     data-close-sid with its confirmation. All four are bound per-element in
     wireCardActions.

     What is left here is the state assignment, which is load-bearing:
     renderMissions reads lastPortfolio, so deleting this outright would
     silently blank the rail. */
  async function renderPositions(p){
    lastPortfolio = p || {};
    renderMissions();
  }

  /* ---------- YOUR book ----------
     The operator's own orders, which reached no surface. `/api/manual/live`
     resolves every one of them across every market before reporting — the
     stored state is `ARMED` forever, because the resolver only writes facts at
     terminal outcomes, so reading the raw book would describe an order that
     expired yesterday as still waiting.

     Deliberately NOT merged into "Open trades": that panel is the engine's
     book, and the whole point of the manual store is that hand-picked trades
     never enter the record that grades the strategy. Same visual language,
     separate panel, labelled on the header. */

  /* ═══ SAME ANATOMY AS A MISSION CARD, DELIBERATELY NOT THE SAME MATERIAL ═══

     These were rows while every other live-trade surface on Command had become
     a card rail, so they get the rail: `.mc`, makeRail(), ringSvg(),
     ladderHtml(), window.SSFormat. That is the anatomy, and sharing it is
     right — an open trade is an open trade, and a second hand-rolled money
     formatter on this panel is the bug this repo has already fixed twice.

     What is NOT shared is the plate. `.mc.mission` wears brushed platinum and
     it means exactly one thing: the engine's book, your money in it. A
     hand-picked trade is a different book by construction — `manual.arm` never
     consults the risk authority, the risk budget does not count this money,
     and none of it may ever be read as engine edge. So this card stays on the
     app's matte ground and wears an accent spine (the property `.pos-row.mine`
     carried, brought forward) plus an off-record hatch. Material is the
     distinction because material survives the rail: at three cards out a card
     is turned, dimmed and blurred, and a chip is unreadable while a plate
     versus a black card with a lit edge still is not. The chip is kept anyway,
     on the card as well as the panel head, so the same thing is said in words
     to anyone reading one card close up or with a screen reader. */
  let MINE = {open: [], pending_risk_usd: '0', open_risk_usd: '0'};

  /* Bars left, said in time. "4 bars" is the engine's unit and means nothing
     to someone deciding whether to sit and watch: on 15m it is an hour, on 4H
     it is most of a day. */
  function windowLeft(bars, tfSeconds){
    if(bars == null || !tfSeconds) return '';
    const s = bars * tfSeconds;
    if(s < 5400) return `${Math.round(s / 60)} min left`;
    if(s < 172800) return `${Math.round(s / 3600)}h left`;
    return `${Math.round(s / 86400)}d left`;
  }

  async function renderMine(){
    const panel = $('minePanel'), box = $('mine');
    let d;
    try { d = await api('/api/manual/live'); }
    catch(err){
      // A book that cannot be read is not an empty book, and must not render
      // as one — this panel exists because invisible orders are the bug.
      panel.style.display = '';
      $('mineRisk').textContent = 'unavailable';
      box.innerHTML = `<div class="empty">Could not read your book — ${
        esc(err.message || 'the server did not answer')}. Any orders you armed
        are still there; this panel just cannot show them right now.</div>`;
      mineRows.clear();
      mineRailSync();
      return;
    }
    MINE = d || MINE;
    setAccentMode();          // the operator's own orders are money too
    const rows = (d && d.open) || [];
    if(!rows.length){ panel.style.display = 'none'; box.innerHTML = ''; mineRows.clear(); return; }
    panel.style.display = '';
    box.querySelectorAll(':scope > .empty').forEach(n => n.remove());

    const risk = (+d.open_risk_usd || 0) + (+d.pending_risk_usd || 0);
    $('mineRisk').textContent =
      `${money(risk)} committed · ${d.n_open} open, ${d.n_pending} waiting`;

    /* The server's own measuring moment, not the browser's clock — every
       `bars_left` on this payload was counted against it. */
    const now = +d.measured_at || Date.now() / 1000;
    /* Keyed diff, the same discipline every other rail on this surface holds
       and for the same reason: this repaints on a 30s poll, and a wholesale
       innerHTML would destroy Cancel under a pointer already on its way down —
       on the one control here that mutates the operator's book. Keyed on
       intent_id, which is the order's identity for its whole life. */
    const seen = new Set();
    rows.forEach(t => {
      const key = t.intent_id || (t.symbol + '|' + t.tf);
      seen.add(key);
      const html = mineCardInner(t, now);
      const cls = 'mc mine' + (t.state === 'PENDING' ? ' resting' : ' filled');
      let rec = mineRows.get(key);
      if(!rec){
        const node = document.createElement('div');
        node.className = cls;
        node.innerHTML = html;
        rec = {el: node, html, cls};
        mineRows.set(key, rec);
      }else{
        if(rec.cls !== cls){ rec.el.className = cls; rec.cls = cls; }
        if(rec.html !== html){ rec.el.innerHTML = html; rec.html = html; }
      }
      box.appendChild(rec.el);
    });
    for(const [key, rec] of mineRows){
      if(seen.has(key)) continue;
      rec.el.remove(); mineRows.delete(key);
    }
    wireCardActions(box);     // data-manage; Cancel is delegated on document
    mineRailSync();
  }
  const mineRows = new Map();          // intent_id -> {el, html, cls}

  function mineCardInner(t, now){
    const long = t.direction === 'LONG';
    const pending = t.state === 'PENDING';
    const entry = +t.entry;
    /* ONE PRICE ON THIS CARD, AND IT IS THE SERVER'S. This panel used to fetch
       /api/candles per row on the CHART timeframe and mark the live price from
       that, while the R beside it was marked by the book against `last_close`
       on the RESOLVING timeframe — two different bars, forty pixels apart. The
       payload already carries the bar the book used, so the picture and the
       number now come off the same close. */
    const live = t.last_close == null ? null : +t.last_close;
    /* The plan, as the shared ladder wants it. The stop is the stop as it
       stands NOW, ratchet included: that is where this trade dies today, and
       drawing the original one would misstate it. */
    const lad = {entry: t.entry, tp: t.tp, sl: t.current_stop || t.sl};

    const bars = t.bars_left;
    const soon = bars != null && bars <= 1;
    /* A resting order's ring is the fraction of its OWN fill window still to
       run — the same measurement the mission ready-card's ring carries, and
       computed from two facts on the row rather than from a denominator this
       file would have to invent: when it was armed, and how many bars are
       left. A filled trade's ring is where price stands between stop and
       target, which is ladderRing's whole job. */
    const elapsed = t.tf_seconds
      ? Math.max(0, (now - (t.armed_at || now)) / t.tf_seconds) : 0;
    const span = (bars == null ? 0 : bars) + elapsed;
    const lifeFrac = (bars == null || span <= 0) ? 1 : bars / span;
    const ring = pending
      ? ringSvg(lifeFrac,
                soon ? 'ring-low' : lifeFrac <= 0.5 ? 'ring-mid' : 'ring-ok',
                bars == null ? '—' : String(bars),
                bars === 1 ? 'bar left' : 'bars left')
      : ladderRing(lad, live);

    /* ARMED AND WAITING IS NOT OPEN AND FILLED, and the stamp is where that is
       said first. A resting order wears the dashed mark this app already uses
       for "not cleared yet"; a filled one wears solid ink. */
    const stamp = pending ? ['st-mine-rest', 'YOURS · ARMED']
                          : ['st-mine', 'YOURS · FILLED'];
    const held = t.bars_held == null ? ''
      : `Held ${t.bars_held} ${esc(t.tf)} bar${t.bars_held === 1 ? '' : 's'}`;

    /* AUDIBLE DEGRADATION. `resolution_tf` is the grid this row's fill and mark
       were resolved on, and `resolution_degraded` is the plain-English reason
       when it is not the finest one stored. A fill that landed four hours late
       for a reason nobody can read is the same bug in a quieter costume, so
       the reason is printed on the card rather than left in a run log. Null is
       the ordinary case and prints nothing. */
    const degraded = t.resolution_degraded
      ? `<div class="mc-degraded">Resolved on ${esc(t.resolution_tf || '')} bars — ${
           esc(t.resolution_degraded)}. The fill moment and the mark are
           coarser than usual.</div>`
      : '';

    /* A planned rung belongs on a RESTING order too. It is part of the plan
       that will run without anyone watching, and an order that will take half
       off at a level reads as an ordinary one until it does. */
    const plan = (t.partials_planned || []).map(
      r => `${Math.round(+r.fraction * 100)}% off at ${px(+r.price)}`).join(' · ');

    let body;
    if(pending){
      const away = (live == null || !live) ? null : Math.abs(live - entry) / live * 100;
      body = `<div class="mc-nums t-mono">waits <b>${px(entry)}</b>${
          away == null ? '' : ` · ${away.toFixed(1)}% away`}${
          bars == null ? '' : ` · ${bars} bar${bars === 1 ? '' : 's'} left`}
          <span class="t-sub" title="Nothing is at stake until it fills">unfilled</span></div>
        <div class="mc-nums t-mono">${money(t.risk_usd)} if it fills · ${
          esc(windowLeft(bars, t.tf_seconds))}</div>`;
    }else{
      // OPEN — filled, and worth something right now. The R comes from the
      // server, which marks it against the last CLOSED bar with the same walk
      // that will settle the trade; recomputing it here would be a second
      // authority that drifts from the one that pays out.
      const r = t.unrealized_r == null ? null : +t.unrealized_r;
      /* PARTLY CLOSED IS NOT OPEN, and this used to say it was. A position with
         half taken off rendered exactly like an untouched one: the full stake
         under "at risk", and `unrealized_r` — which is the per-unit R of what
         is STILL on — read as the whole trade's result. Both numbers were
         wrong in the flattering direction on a winner.
         `blended_r` is the trade: banked plus open. It equals `unrealized_r`
         when nothing has been scaled out, so an ordinary card is unchanged. */
      const closed = +t.closed_fraction || 0;
      const openFrac = t.open_fraction == null ? 1 : +t.open_fraction;
      const blended = t.blended_r == null ? r : +t.blended_r;
      const tone = blended == null ? '' : blended >= 0 ? 'up' : 'down';
      /* Only the REMAINING size is still exposed. Quoting the original stake
         beside a half-closed position overstates what a stop would now cost —
         the money the operator is deciding with. */
      const stillAtRisk = t.risk_usd == null ? null : +t.risk_usd * openFrac;
      const scaled = closed > 0
        ? `<span class="t-sub">${Math.round(closed * 100)}% off · ${
             rr(+t.realized_r)} banked${
             openFrac > 0 ? ' · ' + rr(r) + ' on the rest' : ''}</span>`
        : '';
      /* The ladder draws the stop where it stands, which on a ratcheted trade
         is not where it started. Saying so is the difference between "the plan
         moved" and "I misread the plan". */
      body = `<div class="mc-nums t-mono mine-money">
          <b class="mine-r ${tone}">${rr(blended)}</b>
          <span class="t-sub">${
            t.unrealized_usd == null ? money(stillAtRisk) + ' at risk'
              : signedMoney(t.unrealized_usd) + ' · ' + money(stillAtRisk) + ' at risk'}</span>
          ${scaled}
          ${t.trailed ? '<span class="t-sub">stop trailed — the ladder shows where it stands now</span>' : ''}
        </div>`;
    }

    return `
      <div class="mc-top">
        <span class="mc-stamp ${stamp[0]}">${stamp[1]}</span>
        <span class="mc-id t-mono">${pending ? 'Not filled yet' : held}</span>
      </div>
      <div class="mc-hero">
        <div class="mc-idy">
          <button class="mc-tok t-mono pos-sym pos-open" data-manage="${esc(t.symbol)}"
                  data-managetf="${esc(t.tf)}"
                  title="open the chart on this trade">${esc(tokenOf(t.symbol))}</button>
          <div class="mc-sub t-label" title="${esc(t.symbol)}">${
            esc(String(t.symbol).replace('-USD',''))} · ${esc(t.tf)} · yours${
            +t.leverage > 1 ? ' · ' + esc(t.leverage) + 'x' : ''}</div>
          <div class="mc-dirline">
            <span class="chip ${long ? 'chip-green' : 'chip-red'}">${esc(t.direction)}</span>
            ${pending ? `<span class="chip ${soon ? 'chip-red' : 'chip-amber'}">${
              soon ? 'expiring' : 'waiting'}</span>` : ''}
            <!-- Said on the card, not only on the panel head: one card seen
                 alone, or read out by a screen reader, must still say which
                 book it belongs to. -->
            <span class="chip chip-mine"
                  title="you armed this by hand — it is outside the risk budget and never counts as engine edge">not engine record</span>
          </div>
        </div>
        <div class="mc-ringcol">
          ${ring}
          <!-- "4h left" alone renders uppercase as 4H LEFT, which on a card
               whose timeframe IS 4H reads as the timeframe. The clause says
               what the time is until. -->
          <div class="t-label mc-exp">${pending
            ? (esc(windowLeft(bars, t.tf_seconds)) + ' to fill').trim()
            : (live == null ? 'No live price' : 'Toward target')}</div>
        </div>
      </div>
      <!-- ladderHtml returns nothing when the three prices cannot be scaled
           against each other, and this card must never lose its prices to
           that. Same flat fallback the setup card carries. -->
      ${ladderHtml(lad, live) || `<div class="mc-nums t-mono">
        entry <b>${px(lad.entry)}</b> ·
        tp <b style="color:var(--green)">${px(lad.tp)}</b> ·
        stop <b style="color:var(--red-2)">${px(lad.sl)}</b>
      </div>`}
      ${body}
      ${plan ? `<div class="mc-nums t-mono"><span class="t-sub">${esc(plan)}</span></div>` : ''}
      ${degraded}
      <div class="mc-acts">
        <button class="btn" data-manage="${esc(t.symbol)}" data-managetf="${esc(t.tf)}"
                title="open the chart on this trade — the ticket manages it">Manage</button>
        ${pending ? `<button class="btn mine-cancel" data-cancel="${esc(t.intent_id)}"
                title="withdraw this resting order — nothing has been risked yet">Cancel</button>` : ''}
      </div>`;
  }

  /* Cancel is a real mutation on the operator's book, so it confirms first and
     says what it will and will not do. A cancelled order is recorded, never
     deleted — the store is append-only, and "what happened to that order?" has
     to stay answerable. */
  document.addEventListener('click', async ev => {
    const btn = ev.target.closest && ev.target.closest('[data-cancel]');
    if(!btn) return;
    const id = btn.getAttribute('data-cancel');
    const row = (MINE.open || []).find(r => r.intent_id === id);
    const what = row ? `${tokenOf(row.symbol)} ${row.tf} ${row.direction.toLowerCase()} at ${px(+row.entry)}` : 'this order';
    if(!await SSConfirm({
      title: 'Cancel this order?',
      lead: what,
      rows: ['It has not filled, so nothing has been risked and nothing is ' +
             'recorded as a loss.',
             'The cancellation itself is kept, so your book still says what ' +
             'happened to it.'],
      confirmLabel: 'Cancel the order'
    })) return;
    btn.disabled = true;
    try{
      const r = await fetch('/api/manual/cancel', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({intent_id: id})});
      const d = await r.json().catch(() => ({}));
      if(!r.ok){ toast(d.detail || `could not cancel — HTTP ${r.status}`, 'bad'); btn.disabled = false; return; }
      toast(`cancelled ${what}`, 'ok');
      window.SSData.invalidate('/api/manual/live');
      window.SSData.invalidate('/api/manual/open');
      await renderMine();
    }catch(err){
      toast('could not reach the server — nothing was cancelled', 'bad');
      btn.disabled = false;
    }
  });

  /* The exposure the three meters above do NOT include. `manual.arm` does not
     consult the risk authority — hand-picked trades are structurally outside
     the engine's budget, by the same design that keeps them out of the record —
     so the bars can read "room for another trade" while $579 of your own orders
     are already committed. Stating it is a disclosure, not a rule change:
     nothing here alters what the engine will or will not size. */
  function renderMineAside(){
    const el = $('budgetAside');
    if(!el) return;
    const pend = +MINE.pending_risk_usd || 0, open = +MINE.open_risk_usd || 0;
    const total = pend + open;
    if(total <= 0){ el.hidden = true; el.textContent = ''; return; }
    el.hidden = false;
    const parts = [];
    if(open > 0) parts.push(`${money(open)} in your open trades`);
    if(pend > 0) parts.push(`${money(pend)} in orders you armed that have not filled`);
    // ≤ 8 words. "Outside these limits" is load-bearing (test-pinned): the
    // bars must say they exclude this money, not merely mention it.
    el.innerHTML = `Outside these limits: <b>${money(total)}</b> hand-picked
      <span class="term" data-t="paper">(not risk-sized)</span>`;
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

    renderMineAside();

    // The binding constraint, named. Order matters: the hardest stop first.
    const chip = $('budgetChip');
    const c = lastConstraint = bindingConstraint(
      { lost, lossCap, slots, slotCap, openRisk, openCap });
    chip.textContent = c.label;
    chip.className = 'chip ' + c.tone;
    renderDisposition();
  }

  /* ONE AUTHORITY FOR "CAN I TAKE A TRADE".

     Extracted from the budget chip so the disposition line at the top of
     Command states the same stop, in the same words, as the panel four hundred
     pixels below it. Order matters: the hardest stop first, because an operator
     who is halted for the day does not care that slots are also full. */
  function bindingConstraint({ lost, lossCap, slots, slotCap, openRisk, openCap }){
    /* `label` is the chip's two or three words. `clause` is the same fact in a
       form that can be read inside a sentence, because "there is no slots free"
       is what you get when a chip label is pasted into prose. */
    if(lossCap > 0 && lost >= lossCap)
      return { label: 'halted for today', clause: 'trading is halted for today',
               tone: 'chip-red', blocked: true };
    if(slotCap > 0 && slots >= slotCap)
      return { label: 'no slots free', clause: 'every position slot is full',
               tone: 'chip-amber', blocked: true };
    if(openCap > 0 && openRisk >= openCap)
      return { label: 'risk budget spent', clause: 'the open-risk budget is spent',
               tone: 'chip-amber', blocked: true };
    return { label: 'room for another trade', clause: 'there is room for another trade',
             tone: 'chip-green', blocked: false };
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
      /* The row is read left to right as: what · why · how it went · what it
         paid. The bar is the visual verdict — signed R against a zero line,
         capped at 3R so one runner cannot flatten every other bar — because
         a column of green and red bars says in one glance what a column of
         numbers says in thirty seconds. */
      const barR = Math.max(-3, Math.min(3, j.r_multiple || 0));
      const barW = Math.abs(barR) / 3 * 50;
      // The setup's `why` sentence already opens with its regime ("TRANSITION
      // regime · reversal off..."), so prefixing the regime again printed
      // "transition · transition..." on every row. The why alone when it
      // exists; the bare regime only as the fallback.
      const reason = j.why ? plainReason(j.why)
        : (j.regime ? String(j.regime).replace('_', ' ').toLowerCase() : '');
      /* WHAT IT PAID, not just what it lost. `r_gross` and `costs_r` have been
         in this payload all along and reached no surface, so a stop-out read
         "risked $197 · -$219" and left the operator to wonder which number was
         wrong. Neither is: a stop loses 1R of PRICE, and the round trip is
         charged on top. Shown whenever costs are material. */
      const costR = Number(j.costs_r);
      const costTxt = isFinite(costR) && costR > 0.004
        ? `${Math.abs(Number(j.r_gross)).toFixed(2)}R ${
            Number(j.r_gross) < 0 ? 'loss' : 'gain'} + ${costR.toFixed(2)}R costs`
        : '';
      return `<div class="jnl-row jnl-open${flat ? '' : up ? ' up' : ' down'}"
        data-jsid="${esc(j.setup_id || '')}" tabindex="0" role="button"
        title="open this trade on the chart — the bars it happened on, with entry and exit marked">
        <div>
          <div class="t-mono" style="font-size:13px;color:var(--fg)">${
            j.direction === 'LONG' ? '<span class="dir-up">▲</span>' : '<span class="dir-dn">▼</span>'} ${
            esc(tokenOf(j.symbol))}</div>
          <div class="t-label" style="margin-top:3px">${esc(j.tf)} · ${playbookLabel(j.strategy)}</div>
          ${reason ? `<div class="jnl-why" title="why the engine took it">${esc(reason)}</div>` : ''}
        </div>
        <div class="jnl-say">
          ${outcomeText}${costsAte
            ? ' — <span class="warn">right direction, fees and slippage ate it</span>' : ''}
          <!-- joined rather than concatenated: heldText returns '' when the
               exec fact carries no holding_hours, which produced a doubled
               separator ("Jul 30 ·  · risked $195"). Any future absent field
               now degrades to one fewer clause instead of a visible gap. -->
          <div class="t-sub">${[when, heldText(j.holding_hours),
            'risked ' + money(j.risk_usd), costTxt].filter(Boolean).join(' · ')}</div>
        </div>
        <div class="jnl-r">${rr(j.r_multiple)}
          <span class="t-sub">${signedMoney(j.pnl_usd)}</span>
          <span class="jnl-bar"><i class="${barR >= 0 ? 'pos' : 'neg'}"
            style="width:${barW.toFixed(1)}%;${barR >= 0 ? 'left:50%' : 'right:50%'}"></i></span></div>
      </div>`;
    }).join('');
  }

  /* A settled trade opens on the bars it happened on. Results could tell you a
     trade lost 1.11R and not show you where price went — the obvious next
     question, and the surface had no answer to it. Delegated once, because the
     rows are rebuilt on every refresh. */
  if(!$('journal').dataset.openWired){
    $('journal').dataset.openWired = '1';
    const openTrade = row => {
      const t = lastJournal.find(x => x.setup_id === row.dataset.jsid);
      if(!t || !window.SSChart) return;
      go('chart');
      SSChart.open(t.symbol, t.tf, {trade: t});
    };
    $('journal').addEventListener('click', e => {
      const r = e.target.closest('[data-jsid]');
      if(r && r.dataset.jsid) openTrade(r);
    });
    $('journal').addEventListener('keydown', e => {
      if(e.key !== 'Enter' && e.key !== ' ') return;
      const r = e.target.closest('[data-jsid]');
      if(!r || !r.dataset.jsid) return;
      e.preventDefault();
      openTrade(r);
    });
  }

  /* Renamed from renderScoreboard, which is what a SECOND function 900 lines
     below is also called. Function declarations hoist, so the later one won
     and this one never ran — for as long as both have existed. Nothing errored
     and nothing looked broken from the code: the two callers resolved to the
     Results scoreboard, which fills its own elements perfectly well.

     What it cost is the "Closed today" tile on Command. This is the only code
     that writes #mTodayTile / #mToday / #mTodaySub, so that tile has been
     showing an em-dash forever, beside a Results panel reporting 7 trades and
     a 29% win rate from the same journal.

     Found by eslint's no-redeclare, which is the case CLAUDE.md describes: a
     defect no text assertion and no `node --check` can see, because the file
     is valid JavaScript and every suite that reads it still finds what it
     expects. */
  function renderTodayTile(journal){
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const cut = today.getTime() / 1000;
    const rows = journal.filter(j => j.ts >= cut);
    const tile = $('mTodayTile'), val = $('mToday'), sub = $('mTodaySub');
    if(!rows.length){
      tile.classList.remove('up', 'down');
      val.textContent = '—';
      sub.textContent = 'No trades closed yet today';
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
    /* THROUGH pct(), not concatenated. This printed `p.return_pct + '%'` raw
       while every other reader formats the same field through the shared
       helper, so the top bar said -5.84% with the Ledger card saying -5.8%
       forty pixels below it — one number, two renderings, on one screen.
       That is the defect test_one_source_of_truth.js exists for, and its own
       comment names the ancestor: "$193 / $195 / 194.68 / $194". */
    $('equityRet').textContent = ruled
      ? '  ' + (up ? '+' : '') + pct(p.return_pct) : '';
    $('equityChip').title = `account equity (paper) — start ${money(p.start_equity)}, ` +
      `open risk ${money(p.open_risk_usd || 0)}`;
    $('rEquity').textContent = money(p.equity);

    const journal = p.journal || [];
    renderJournal(journal, p.journal_total);
    // Both, deliberately: this loader feeds Command's today tile AND the
    // Results scoreboard, and the name collision meant only the second ever
    // ran from here.
    renderTodayTile(journal);
    renderScoreboard(journal);


    // fire-and-forget: the positions panel fetches a price per open trade, and
    // a slow venue must not hold up the equity numbers above it
    indexHeld(p);
    engineExposed = (p.active_positions || []).length > 0 ||
                    (p.pending_orders   || []).length > 0;
    /* The engine's book is the authority on exposure, so this is the moment
       the accent is allowed to speak. The operator's own orders adjust it
       afterwards; they cannot be the thing that unlocks it, because a reader
       with no hand-armed orders would then never leave `unknown`. */
    bookKnown = true;
    setAccentMode();
    renderRiskBudget(p);
    renderPositions(p).catch(() => {});
    // Your own book, on its own request — it resolves intents server-side and
    // must not hold up the engine numbers above it.
    renderMine().then(() => renderMineAside()).catch(() => {});

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
    renderScoreboard(p.journal || []);
    lastJournal = p.journal || [];
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
    /* One chip-sized line each. The paragraph versions explained the era
       split in full sentences; the operator ruled "no one wants to read", and
       the numbers carry the fact: the tiles count THIS window, the full book
       lives on Diagnostics. */
    $('resultsEra').innerHTML =
      `<span class="term" data-t="forwardWindow">window</span>${
         started ? ' · since <b>' + started + '</b>' : ''} · full book in
       <a href="#diagnostics">Diagnostics</a>`;
    $('resultsNote').innerHTML = ruled
      ? `<b>${d.APPROVED || 0}</b> approved · <b>${d.REDUCED || 0}</b> reduced ·
         <a href="#diagnostics" class="num-link" data-jump="funnel"
            title="every refusal, grouped by reason"><b>${d.REJECTED || 0}</b> rejected</a>
         · ${p.config ? p.config.risk_pct : '—'}%/trade ·
         <span class="term" data-t="paper">paper</span>`
      : `window empty — opened${started ? ' ' + started : ''}, nothing ruled yet ·
         <span class="term" data-t="paper">paper</span>`;
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
  /* This was a bare polyline on a 0-800 viewBox with preserveAspectRatio="none"
     and no axis of any kind: a shape that rose or fell without ever saying by
     how much, over what period, or where one trade ended and the next began.
     It is the headline picture of the operator's record, so it now carries a
     dollar scale, a dated x axis, a dot per settlement, and a hover/arrow-key
     readout naming the trade under the cursor. The viewBox is measured in CSS
     pixels rather than stretched, because a stretched viewBox distorts every
     glyph in it — which is exactly why the old one could not afford labels. */
  const EQ = {curve: null, start: 0, geo: null, idx: -1};
  const dayFmt = ts => new Date(ts * 1000)
    .toLocaleDateString(undefined, {day: 'numeric', month: 'short'});

  function drawCurve(curve, start){
    EQ.curve = curve; EQ.start = start; EQ.idx = -1;
    const el = $('eqCurve');
    if(!el) return;
    const W = Math.max(320, Math.round(el.clientWidth || el.parentElement.clientWidth || 800));
    const H = 200;
    el.setAttribute('viewBox', `0 0 ${W} ${H}`);

    const note = $('eqNote'), hov = $('eqHover');
    if(hov) hov.textContent = '';

    if(!curve || curve.length < 2){
      EQ.geo = null;
      el.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="var(--fg-3)"
        font-family="var(--f-mono)" font-size="11">no closed trades in this window yet</text>`;
      el.setAttribute('aria-label', 'Equity curve: no closed trades in this window yet');
      note.textContent = curve && curve.length === 1
        ? '1 settlement — a curve needs at least two points' : '';
      return;
    }

    const ys = curve.map(p => +p.equity);
    const last = ys[ys.length - 1];
    const lo = Math.min(...ys, start), hi = Math.max(...ys, start);
    const pad = (hi - lo) * 0.12 || Math.max(1, Math.abs(start) * 0.001);
    const dLo = lo - pad, dHi = hi + pad;
    const L = 62, R = 12, T = 14, B = 30;         // gutters: $ labels left, dates below
    const y = v => T + (1 - (v - dLo) / (dHi - dLo)) * (H - T - B);
    const x = i => L + (i / (curve.length - 1)) * (W - L - R);
    EQ.geo = {x, y, L, R, T, B, W, H};

    const up = last >= start;
    const col = up ? 'var(--green)' : 'var(--red-2)';
    const pts = curve.map((p, i) => `${x(i).toFixed(1)},${y(+p.equity).toFixed(1)}`).join(' ');

    // Four horizontal rules with the dollars they stand for. Without these the
    // same rise reads as a fortune or as noise depending only on the crop.
    let grid = '';
    for(let k = 0; k <= 3; k++){
      const v = dLo + (dHi - dLo) * (k / 3), gy = y(v).toFixed(1);
      grid += `<line x1="${L}" y1="${gy}" x2="${W - R}" y2="${gy}"
                     stroke="var(--border-soft)" stroke-width="1"/>
               <text x="${L - 8}" y="${(+gy + 3.5).toFixed(1)}" text-anchor="end"
                     fill="var(--fg-4)" font-family="var(--f-mono)" font-size="10"
                     >${money(v)}</text>`;
    }

    // Dates under the plot — first, last, and the middle if there is room.
    const stamps = [0];
    if(curve.length > 3 && (W - L - R) > 300) stamps.push(Math.floor((curve.length - 1) / 2));
    stamps.push(curve.length - 1);
    const dates = [...new Set(stamps)].map(i => {
      const anchor = i === 0 ? 'start' : (i === curve.length - 1 ? 'end' : 'middle');
      return `<text x="${x(i).toFixed(1)}" y="${H - 10}" text-anchor="${anchor}"
                    fill="var(--fg-4)" font-family="var(--f-mono)" font-size="10"
                    >${dayFmt(curve[i].ts)}</text>`;
    }).join('');

    // One dot per settlement, so the operator can count trades in the shape.
    // Above ~90 closes the dots merge into a band and are dropped.
    const dots = curve.length <= 90
      ? curve.map((p, i) =>
          `<circle cx="${x(i).toFixed(1)}" cy="${y(+p.equity).toFixed(1)}" r="2.4"
                   fill="var(--bg-1)" stroke="${col}" stroke-width="1.4"/>`).join('')
      : '';

    el.innerHTML =
      `${grid}
       <line x1="${L}" y1="${y(start).toFixed(1)}" x2="${W - R}" y2="${y(start).toFixed(1)}"
             stroke="var(--fg-3)" stroke-dasharray="3 4" stroke-width="1"/>
       <text x="${W - R - 3}" y="${(y(start) - 5).toFixed(1)}" text-anchor="end"
             fill="var(--fg-3)" font-family="var(--f-mono)" font-size="9.5"
             >break even ${money(start)}</text>
       <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"
                 stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
       ${dots}
       ${dates}
       <g id="eqCursor" opacity="0">
         <line y1="${T}" y2="${H - B}" stroke="var(--accent)" stroke-width="1" opacity=".7"/>
         <circle r="4" fill="var(--accent)"/>
       </g>`;

    el.setAttribute('aria-label',
      `Equity curve, ${curve.length} settlements from ${dayFmt(curve[0].ts)} to ` +
      `${dayFmt(curve[curve.length - 1].ts)}. Started ${money(start)}, now ${money(last)}, ` +
      `peak ${money(hi)}, low ${money(lo)}.`);
    note.textContent =
      `${curve.length} settlements · start ${money(start)} · peak ${money(hi)} · now ${money(last)}`;
  }

  /* Point the cursor at settlement i and say what it was. Shared by the mouse
     and the arrow keys — the readout is the only way to get an exact number off
     this picture, so it cannot be mouse-only. */
  function eqPoint(i){
    const g = EQ.geo, el = $('eqCurve'), hov = $('eqHover');
    if(!g || !EQ.curve) return;
    i = Math.max(0, Math.min(EQ.curve.length - 1, i));
    EQ.idx = i;
    const p = EQ.curve[i], v = +p.equity;
    const prev = i > 0 ? +EQ.curve[i - 1].equity : EQ.start;
    const step = v - prev;
    const cur = el.querySelector('#eqCursor');
    if(cur){
      cur.setAttribute('opacity', '1');
      cur.querySelector('line').setAttribute('x1', g.x(i));
      cur.querySelector('line').setAttribute('x2', g.x(i));
      cur.querySelector('circle').setAttribute('cx', g.x(i));
      cur.querySelector('circle').setAttribute('cy', g.y(v));
    }
    if(hov) hov.innerHTML =
      `settlement <b>${i + 1}</b>/${EQ.curve.length} · ${dayFmt(p.ts)} ·
       equity <b>${money(v)}</b> ·
       <span class="${step >= 0 ? 'up' : 'down'}">${step >= 0 ? '+' : ''}${money(step)}</span>
       this trade · ${signedMoney(v - EQ.start)} since the window opened`;
  }
  function eqClear(){
    const cur = $('eqCurve') && $('eqCurve').querySelector('#eqCursor');
    if(cur) cur.setAttribute('opacity', '0');
    if($('eqHover')) $('eqHover').textContent = '';
    EQ.idx = -1;
  }

  (function wireCurve(){
    const el = $('eqCurve');
    if(!el) return;
    const nearest = ev => {
      const g = EQ.geo;
      if(!g || !EQ.curve) return -1;
      const box = el.getBoundingClientRect();
      const px = (ev.clientX - box.left) * (g.W / box.width);
      const frac = (px - g.L) / (g.W - g.L - g.R);
      return Math.round(frac * (EQ.curve.length - 1));
    };
    el.addEventListener('pointermove', ev => { const i = nearest(ev); if(i >= 0) eqPoint(i); });
    el.addEventListener('pointerleave', eqClear);
    el.addEventListener('blur', eqClear);
    el.addEventListener('focus', () => { if(EQ.curve && EQ.idx < 0) eqPoint(EQ.curve.length - 1); });
    el.addEventListener('keydown', ev => {
      if(!EQ.curve) return;
      const jump = {ArrowLeft: -1, ArrowRight: 1, Home: -1e9, End: 1e9}[ev.key];
      if(jump === undefined) return;
      ev.preventDefault();
      eqPoint(EQ.idx < 0 ? EQ.curve.length - 1 : EQ.idx + jump);
    });
    // The viewBox is measured in pixels, so a width change needs a redraw or
    // the labels land in the wrong places. Cheap: only fires on real resizes.
    if(window.ResizeObserver){
      let w = 0;
      new ResizeObserver(() => {
        const now = Math.round(el.clientWidth);
        if(now && Math.abs(now - w) > 4){ w = now; if(EQ.curve) drawCurve(EQ.curve, EQ.start); }
      }).observe(el);
    }
  })();

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
      /* SAY IT ONCE, BADGE THE REST. The same 90-character refusal — "the
         token was not on the traded watchlist when the setup confirmed" —
         appeared on four rows of one table, which is 360 characters spent
         saying one thing and a table nobody scans. The block heading above
         carries the sentence; a row only needs to name WHICH refusal it was,
         and only when it differs from its neighbours. */
      const rk = Object.keys(r.reasons || {});
      const badge = rk.length === 1
        ? `<span class="chip" title="${esc(plainReason(rk[0]))}">${
            esc(shortReason(rk[0]))}</span>`
        : rk.length > 1 ? `<span class="chip">${rk.length} reasons</span>` : '';
      return `<tr>
        <th scope="row">${esc(fmtKey(r.key ?? '—'))}${more}${
          badge ? '<div style="margin-top:3px">' + badge + '</div>' : ''}</th>
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
    /* Kept for the handover report, which must quote what the panels were
       painted from rather than fetch its own copy — two reads of a moving
       audit could disagree, and a report that disagrees with the screen is
       worse than no report. Same reason for lastDiagTelemetry below. */
    lastDiagHealth = h;
    renderDiagState();
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
    /* Keyed off the STATE, not off one branch that happens to set a class.
       ss.css sheds this chip below 900px unless it carries .degraded, and only
       markDegraded() — the fetch-failure path — was adding it. The pipeline
       audit's own verdict lands here, so DEGRADED and BLOCKED were shed on
       every phone and tablet while the chip's text said DEGRADED and its rect
       measured 0x0. The comment beside that CSS rule said "shell.js adds
       .degraded when a refresh fails", which was true and was the tell: one
       path of two had been considered. A clean audit still sheds. */
    $('healthChip').classList.toggle('degraded', tone !== 'good');
    /* A STATUS WITH NO CONSEQUENCE IS NOT A STATUS. This chip read DEGRADED on
       every surface with nothing to say whether that meant "do not trade
       today" or "a background check is noisy". The newcomer freezes; the
       experienced reader learns it never changes and stops seeing it — and
       then misses the day it says BLOCKED. The consequence, in one sentence,
       on the hover that was previously a bare label. */
    $('healthChip').title =
      !h.evaluation_allowed
        ? 'BLOCKED — the engine is refusing to size new entries on this data. ' +
          'Fix the data before trading. Diagnostics lists what failed.'
      : h.status === 'PASS'
        ? 'Every data check passed. Nothing is being held back.'
        : 'Trading continues — the data is being used with a mark on it, not ' +
          'held back. Only BLOCKED stops new entries. Diagnostics lists what ' +
          'is flagged.';
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
    /* The one place the UI learns whether real orders are possible. server.py
       says outright: "The UI reads this rather than deciding for itself." */
    liveEnabled = !!c.live_enabled;
    setAccentMode();
    const pct = v => (v * 100).toFixed(v * 100 % 1 ? 1 : 0) + '%';
    const row = (k, v, note) => `<div><span class="k">${k}</span>` +
      `<span class="v">${v}${note ? ' <span style="color:var(--fg-4)">' + note + '</span>' : ''}</span></div>`;
    /* THE ONE AUTHORITY ON THE CAPS. Guardrails printed the daily loss halt,
       the maximum concurrent positions and the total open risk a second time,
       off /api/settings.values.risk_config, in percentages where these are
       fractions — and invented client-side fallbacks of 6, 2 and 4 when the
       key was missing. Three caps the engine owns, six readings on one panel,
       three of them a UI guess. The duplicates are deleted; what is left in
       #guardRows is halt STATE, which lives nowhere else.

       `live execution` says where the condition is written down rather than
       just LOCKED — the lock spent months here with no definition anywhere. */
    $('riskNow').innerHTML =
      row('risk per trade', pct(c.risk_pct)) +
      row('total open risk', pct(c.max_total_risk_pct), `(${c.max_concurrent} × per-trade)`) +
      row('concurrent positions', c.max_concurrent) +
      row('daily loss halt', pct(c.daily_loss_pct)) +
      row('live execution', c.live_enabled ? 'ENABLED' : 'LOCKED — see Going live') +
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
  /* Operator ruling: "no need to talk about dead anything." Range-fade has no
     engine behind it and breakout-retest was measured and left off — a toggle
     wired to nothing and a toggle nobody should flip are both noise on a
     settings page. The SERVER still knows both settings; hiding is a UI act. */
  const HIDDEN_SETTINGS = new Set(['strategy_breakout_retest', 'strategy_range_fade']);

  function buildSettings(){
    $('setFields').innerHTML = setSpec.filter(s => !BUTTON_OWNED.has(s.name) && !HIDDEN_SETTINGS.has(s.name)).map(s => {
      const v = (s.name in setPending) ? setPending[s.name] : setValues[s.name];
      const ctl = s.type === 'bool'
        ? `<input type="checkbox" data-set="${s.name}" ${v ? 'checked' : ''}>`
        : `<input class="t-mono" data-set="${s.name}" value="${escHtml(v)}" style="width:110px">`;
      /* The description is dropped when it merely restates the label —
         "Pullback playbook · Trade PULLBACK setups." taught nothing and cost a
         line on every row. Compared on words, not characters, so a genuinely
         informative sentence that happens to share a noun survives. */
      const label = settingLabel(s.name);
      const desc = humaniseCodes(String(s.description || ''));
      const words = t => new Set(String(t).toLowerCase().match(/[a-z]+/g) || []);
      const dw = words(desc), lw = words(label);
      const novel = [...dw].filter(w => !lw.has(w) && w.length > 3);
      const tautological = dw.size > 0 && novel.length <= 1;

      /* The "rule" badge was on nearly every row, which is the definition of
         a badge that means nothing. Behavioural settings are the MAJORITY
         here; what is worth marking is the exception, so the badge is gone
         and the consequence is carried by the confirm dialog and the banner —
         where it is read at the moment it applies. */
      return `<label class="set-row" data-setrow="${s.name}">
        ${s.type === 'bool' ? ctl : ''}
        <span>
          <span class="t-mono" style="color:var(--fg-2)">${escHtml(label)}</span>
          ${tautological ? '' : `<span class="t-label" style="display:block;margin-top:2px;
            text-transform:none;letter-spacing:0;color:var(--fg-3)">${escHtml(desc)}</span>`}
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
    /* The banner appears only when there IS something to apply. Two buttons
       sitting permanently disabled taught the reader to stop looking at them,
       so the one moment they mattered looked like every other moment. */
    const banner = $('dirtyBanner'), what = $('dirtyWhat');
    if(banner){
      banner.hidden = !dirty.length;
      if(dirty.length && what)
        what.textContent = dirty.length === 1
          ? `Unsaved change to ${settingLabel(dirty[0])}.`
          : `${dirty.length} unsaved rule changes.`;
    }
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
    /* THE HALT STATE, and only that. Three caps (daily loss, max concurrent,
       total open risk) used to be printed here as well as in #riskNow — from
       a different endpoint, in percentages against #riskNow's fractions, with
       invented fallbacks of 6, 2 and 4 standing in for whatever the engine
       failed to send. They are gone; #riskNow is the one authority on a cap,
       and a cap the engine does not send now reads as absent rather than as
       somebody's guess.

       These three rows survive because nothing else prints them: whether the
       operator has pulled the halt, the drawdown ceiling, and whether a
       blocked data audit stops trading. All three are settings, not caps. */
    const gr = (k, v, cls) => `<div><span class="k">${k}</span>` +
      `<span class="v ${cls || ''}">${v}</span></div>`;
    const ddPct = setValues.max_drawdown_pct;
    $('guardRows').innerHTML =
      gr('operator halt', setValues.halted ? 'ENGAGED' : 'armed',
         setValues.halted ? 'bad' : 'good') +
      // No fallback. An absent ceiling is not a 20% ceiling.
      gr('total drawdown halt', ddPct == null ? 'not set' : ddPct + '% from peak',
         ddPct == null ? 'warn' : 'good') +
      gr('data-health halt', setValues.halt_on_data_blocked ? 'armed' : 'DISABLED',
         setValues.halt_on_data_blocked ? 'good' : 'warn');
    $('guardChip').textContent = setValues.halted ? 'halted' : 'armed';
    $('guardChip').className = 'chip ' + (setValues.halted ? 'chip-red' : 'chip-green');

    const halted = !!setValues.halted;
    $('btnHalt').textContent = halted ? 'HALTED' : 'HALT';
    $('btnHalt').className = 'btn ' + (halted ? 'btn-primary' : 'btn-red');
    $('btnHalt').title = halted
      ? 'new entries are blocked — click to resume'
      : 'stop sizing new entries (open positions still settle)';
    document.body.classList.toggle('is-halted', halted);
  }

  /* ---------- export ----------
     The book was readable and not extractable: anyone wanting to check this
     record in a spreadsheet had to retype it. Client-side on the journal
     already fetched — no endpoint, no second authority for what a trade was.
     Every field the journal row shows, plus the identifiers needed to trace
     a row back to the fact store. */
  const CSV_COLS = ['ts', 'symbol', 'tf', 'strategy', 'direction', 'regime',
                    'entry', 'exit_price', 'outcome', 'r_multiple', 'r_gross',
                    'costs_r', 'pnl_usd', 'risk_usd', 'holding_hours',
                    'setup_id', 'why'];
  function exportJournal(journal){
    if(!journal || !journal.length){ toast('No closed trades to export.', 'warn'); return; }
    // RFC 4180 quoting: `why` carries commas and the odd quote, and a CSV that
    // breaks on its own reason column is worse than no export.
    const cell = v => {
      const s = v == null ? '' : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const rows = [CSV_COLS.join(',')].concat(journal.map(t => CSV_COLS.map(c =>
      cell(c === 'ts' && t.ts ? new Date(t.ts * 1000).toISOString() : t[c])
    ).join(',')));
    const blob = new Blob([rows.join('\r\n')], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `snipersight-journal-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(`Exported ${journal.length} trade${journal.length === 1 ? '' : 's'}.`, 'good');
  }

  /* ---------- the scoreboard ----------

     "Is this actually working?" is the question printed at the top of this
     surface, and equity and drawdown do not answer it — they say what
     happened to the money, not whether the method works. Win rate, average R
     and the sample lived on Diagnostics, framed as engineering detail.

     Computed from the FORWARD journal, never from the edge panel's whole
     recorded book: those two populations differ by hundreds of trades, and
     mixing them on one page is a bug this project has already had to fix
     once. The era band above these tiles is their scope statement. */
  function renderScoreboard(journal){
    const rs = journal.map(t => t.r_multiple)
                      .filter(r => r != null).map(Number);
    const n = rs.length;
    if(!n){
      for(const id of ['rTrades', 'rWin', 'rAvgR', 'rPF']) $(id).textContent = '—';
      $('rSample').textContent = '';
      return;
    }
    const wins = rs.filter(r => r > 0);
    const gross = wins.reduce((s, r) => s + r, 0);
    const loss = rs.filter(r => r < 0).reduce((s, r) => s - r, 0);
    const avg = rs.reduce((s, r) => s + r, 0) / n;

    $('rTrades').textContent = n;
    $('rWin').textContent = Math.round(wins.length / n * 100) + '%';
    $('rAvgR').textContent = (avg >= 0 ? '+' : '') + avg.toFixed(2) + 'R';
    $('rAvgR').parentElement.className = 'tile ' + (avg > 0 ? 'up' : avg < 0 ? 'down' : '');
    // A book with no losses has no profit factor — it has no denominator.
    // Printing ∞ or 999 there would read as a result rather than an absence.
    $('rPF').textContent = loss > 0 ? (gross / loss).toFixed(2)
                         : gross > 0 ? 'no losses yet' : '—';

    /* THE SAMPLE CAVEAT, sized to the sample. A win rate off seven trades is
       a number, not evidence. The thresholds match the ones the rest of the
       app already uses: edgestats needs 10 trades to compute an interval at
       all, and livegate wants 100 before it will unlock real money. */
    $('rSample').textContent = n >= 100
      ? ''
      : n < 10
        ? `${n} trade${n === 1 ? '' : 's'} — far too few to read anything into. ` +
          `A confidence interval needs at least 10.`
        : `${n} trades — enough to compute, not enough to trust. Settings ` +
          `wants 100 before the record argues for real money.`;

    lastScore = {n, win: wins.length / n, avg,
                 pf: loss > 0 ? gross / loss : null,
                 best: Math.max(...rs), worst: Math.min(...rs)};
    renderStatWheel();
    renderProgression();
  }
  let lastScore = null;

  /* ---------- the stat wheel ----------
     Eight figures, each DRAWN as well as printed. The ring is the same
     component the Mission Briefs use, so a reader who has learned to read one
     ring on Command can read these without being taught twice.

     Every `frac` below is a stated proportion of a stated bound, and the bound
     is on the card — a ring filled against an invented denominator is a
     progress bar pretending to be a measurement. Where a figure has no honest
     bound (equity, profit factor) the ring is omitted rather than faked. */
  function statCards(){
    const s = lastScore, p = lastPortfolio || {};
    if(!s) return [];
    const pct = v => (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
    const ret = p.return_pct == null ? null : Number(p.return_pct);
    const dd  = p.max_drawdown_pct == null ? null : Number(p.max_drawdown_pct);
    const halts = p.kill_switch_days ?? 0;
    return [
      {k: 'trades', label: 'Trades closed', big: String(s.n),
       sub: s.n < 10 ? `${10 - s.n} more to a confidence interval`
                     : s.n < 100 ? `${100 - s.n} more before the record argues for real money`
                                 : 'a sample worth reading',
       frac: Math.min(s.n / 100, 1), ringLabel: 'of 100', tone: 'ring-mid',
       note: 'The forward window only. Diagnostics measures the whole book.'},
      {k: 'win', label: 'Win rate', big: Math.round(s.win * 100) + '%',
       sub: 'of closed trades ended positive',
       frac: s.win, ringLabel: 'won', tone: s.win >= 0.5 ? 'ring-ok' : 'ring-low',
       note: 'A high win rate is not an edge on its own — size of win against ' +
             'size of loss is what decides it. That is average R, next.'},
      {k: 'avgr', label: 'Average R', big: (s.avg >= 0 ? '+' : '') + s.avg.toFixed(2) + 'R',
       sub: s.avg > 0 ? 'each trade returned more than it risked, on average'
                      : 'each trade lost a fraction of what it risked, on average',
       frac: null, tone: s.avg > 0 ? 'ring-ok' : 'ring-low',
       note: 'R is the multiple of the money put at risk. −0.27R means about a ' +
             'quarter of the risk was lost per trade on average.'},
      {k: 'pf', label: 'Profit factor', big: s.pf == null ? '—' : s.pf.toFixed(2),
       sub: s.pf == null ? 'no losing trades to divide by'
          : s.pf >= 1 ? 'won more than it lost' : 'lost more than it won',
       frac: null, tone: (s.pf != null && s.pf >= 1) ? 'ring-ok' : 'ring-low',
       note: 'Gross winnings divided by gross losses. Above 1.00 is profitable ' +
             'before costs of being wrong about the sample.'},
      {k: 'best', label: 'Best trade', big: (s.best >= 0 ? '+' : '') + s.best.toFixed(2) + 'R',
       sub: 'the most any single trade returned', frac: null, tone: 'ring-ok',
       note: 'One trade. It is the ceiling of the record, not evidence about it.'},
      {k: 'worst', label: 'Worst trade', big: s.worst.toFixed(2) + 'R',
       sub: 'the most any single trade lost', frac: null, tone: 'ring-low',
       note: 'A stop doing its job looks like this. Worse than −1R means the ' +
             'stop was jumped, not respected.'},
      {k: 'dd', label: 'Max drawdown', big: dd == null ? '—' : dd + '%',
       sub: 'the deepest fall from a high-water mark',
       frac: dd == null ? null : Math.min(dd / 20, 1), ringLabel: 'of 20%',
       tone: dd != null && dd > 10 ? 'ring-low' : 'ring-mid',
       note: 'Scaled against 20%, the depth at which a strategy is usually ' +
             'considered to have failed rather than dipped.'},
      {k: 'halt', label: 'Halt days', big: String(halts),
       sub: halts ? 'days the automatic loss limit stopped new entries'
                  : 'the daily loss limit has never had to fire',
       frac: null, tone: halts ? 'ring-low' : 'ring-ok',
       note: 'The kill switch stopping you is the system working. It is listed ' +
             'because it should be rare, not because it is bad.'},
      ...(ret == null ? [] : [{k: 'ret', label: 'Return', big: pct(ret),
       sub: 'against the starting equity of this window', frac: null,
       tone: ret >= 0 ? 'ring-ok' : 'ring-low',
       note: 'Money, not method. Average R is the one that says whether the ' +
             'rules work; this says what happened to the account.'}]),
    ];
  }

  function renderStatWheel(){
    const el = $('statTrack');
    if(!el) return;
    const cards = statCards();
    if(!cards.length){
      el.innerHTML = '<div class="empty">No closed trades in this window yet.</div>';
      return;
    }
    el.innerHTML = cards.map(c => `<div class="mc stat-card">
      <div class="mc-top">
        <span class="mc-stamp ${c.tone === 'ring-ok' ? 'st-go'
                              : c.tone === 'ring-low' ? 'st-dead' : 'st-wait'}">${esc(c.label)}</span>
      </div>
      <div class="mc-hero">
        <div class="mc-idy">
          <div class="stat-big t-mono">${esc(c.big)}</div>
          <div class="mc-sub t-label">${esc(c.sub)}</div>
        </div>
        ${c.frac == null ? '' : `<div class="mc-ringcol">
          ${ringSvg(c.frac, c.tone, Math.round(c.frac * 100) + '%', esc(c.ringLabel || ''))}
        </div>`}
      </div>
      <div class="mc-story stat-note">${esc(c.note)}</div>
    </div>`).join('');
    if(!statRail) statRail = makeRail(el, {prev: 'statPrev', next: 'statNext',
                                           status: 'statStatus', tilt: true});
    statRail.sync();
  }
  let statRail = null, progRail = null;
  /* Declared here, above their first reader. renderProgression is reached from
     the ungated portfolio loader on every surface, and `let` in a temporal
     dead zone throws rather than reading undefined. */
  let lastGate = null, gateErr = null;

  /* ---------- progression ----------
     Real thresholds only. Each row is a gate this system already enforces or
     already needs, so "locked" means something concrete rather than a game
     designer's pacing. Nothing here is awarded for winning: the forward record
     does not say the method works, and a badge claiming otherwise would be the
     one thing this product must never print. */
  function progressionRows(){
    const s = lastScore, p = lastPortfolio || {};
    if(!s) return [];
    const halts = p.kill_switch_days ?? 0;
    const rows = [
      {t: 'First blood', done: s.n >= 1, have: Math.min(s.n, 1), need: 1,
       d: 'One trade closed and recorded.',
       locked: 'Closes when the engine finishes its first trade.'},
      {t: 'Readable sample', done: s.n >= 10, have: Math.min(s.n, 10), need: 10,
       d: 'Ten closed trades — the minimum a confidence interval can be computed from.',
       locked: 'The maths cannot bound an edge on fewer than ten.'},
      /* "Arguable record" (100 trades) and "Shallow water" (drawdown) used to
         live here as well as on the going-live gate — the same two thresholds,
         measured twice, on two surfaces, in two vocabularies. The gate's
         versions win: they are the engine's own measurement, they carry its
         note, and the drawdown one reads the operator's CONFIGURED ceiling
         instead of a hardcoded 10. Both are appended below from /api/live-gate.
         Do not add a local copy back. */
      {t: 'Discipline held', done: halts === 0 && s.n > 0, have: halts === 0 ? 1 : 0, need: 1,
       d: 'The daily loss limit has never had to stop you.',
       locked: 'The kill switch has fired. It working is good; needing it is the note.'},
    ];
    return rows;
  }

  /* ---------- progression: one track, one vocabulary ----------

     The going-live criteria used to be a second wheel of the same card, on
     Settings, thirty lines from a "Guardrails" panel — met/not-met stamp, ring,
     note, measuring the same forward record, sharing two criteria outright
     with the rows above. Two tracks meant two verdict words for one idea:
     Progression said EARNED / LOCKED and the gate said MET / NOT MET, while
     LOCKED ALSO meant "live execution is off" on the panel beside it.

     One track now, and MET / NOT MET everywhere on it. LOCKED survives on
     Settings meaning exactly one thing.

     The four gate cards keep the `gate-card` class and their engine-supplied
     note; the local milestones keep `prog-card`. They are told apart on screen
     by one line — the gate ones say what they unlock. */
  function gateRows(){
    if(!lastGate) return [];
    return (lastGate.criteria || []).map(c => ({
      gate: true,
      t: c.label,
      done: !!c.pass,
      frac: Math.max(0, Math.min(1, c.progress || 0)),
      id: c.have == null ? 'not yet measurable'
        : c.key === 'sample' ? `${fmt(c.have)} of ${fmt(c.need)}`
        : c.key === 'edge' ? `${c.have > 0 ? '+' : ''}${c.have}R lower bound`
        : c.key === 'drawdown' ? `${c.have}% of ${c.need}%`
        : String(c.have),
      d: 'One of the four that unlock live execution.',
      story: c.note,
    }));
  }

  function renderProgression(){
    const el = $('progTrack');
    if(!el) return;
    const local = progressionRows().map(r => ({
      gate: false,
      t: r.t,
      done: r.done,
      frac: Math.max(0, Math.min(1, r.have / r.need)),
      id: r.need > 1 ? r.have + ' / ' + r.need : '',
      d: r.d,
      story: r.done ? r.d : r.locked,
    }));
    const rows = local.concat(gateRows());
    const done = rows.filter(r => r.done).length;
    const chip = $('progCount');
    /* The chip counts what it can measure and says so when that is not
       everything. "2 of 3 met" beside a rail of four cards is the kind of
       small disagreement that makes a reader stop trusting both numbers. */
    if(chip) chip.textContent = !rows.length ? '—'
      : lastGate ? `${done} of ${rows.length} met`
      : `${done} of ${rows.length} met · 4 not read`;
    const lede = $('progLede');
    if(lede) lede.textContent =
      'Milestones for the record itself, not for winning, and the four criteria ' +
      'that unlock live execution. None of these say the method works — that is ' +
      'what average R and the confidence interval are for.';
    if(!rows.length){
      el.innerHTML = '<div class="empty">Nothing recorded yet.</div>';
      return;
    }
    /* THE GATE'S ABSENCE IS AUDIBLE. /api/live-gate is fetched by the Results
       and Settings loaders; renderProgression also runs from the portfolio
       loader, which is ungated. Rendering the three local milestones with no
       word about the missing four would read as a complete track. */
    const missing = !lastGate
      ? `<div class="mc stat-card prog-card">
          <div class="mc-top"><span class="mc-stamp st-wait">NOT READ</span></div>
          <div class="mc-hero"><div class="mc-idy">
            <div class="prog-title t-mono">Going-live criteria</div>
            <div class="mc-sub t-label">four more, not loaded</div>
          </div></div>
          <div class="mc-story stat-note">${esc(gateErr
            ? 'Could not read the criteria — ' + gateErr
            : 'The four criteria that unlock live execution have not been read yet.')}</div>
        </div>`
      : '';
    el.innerHTML = rows.map(r =>
      `<div class="mc stat-card ${r.gate ? 'gate-card' : 'prog-card'}${
          r.done ? ' earned' : ''}">
        <div class="mc-top">
          <span class="mc-stamp ${r.done ? 'st-go' : 'st-wait'}">${r.done ? 'MET' : 'NOT MET'}</span>
          <span class="mc-id t-mono">${esc(r.id)}</span>
        </div>
        <div class="mc-hero">
          <div class="mc-idy">
            <div class="prog-title t-mono">${esc(r.t)}</div>
            <div class="mc-sub t-label">${esc(r.d)}</div>
          </div>
          <div class="mc-ringcol">
            ${ringSvg(r.frac, r.done ? 'ring-ok' : 'ring-mid',
                      Math.round(r.frac * 100) + '%', r.done ? 'met' : 'to go')}
          </div>
        </div>
        <div class="mc-story stat-note">${esc(r.story)}</div>
      </div>`).join('') + missing;
    if(!progRail) progRail = makeRail(el, {prev: 'progPrev', next: 'progNext',
                                           status: 'progStatus', tilt: true});
    progRail.sync();
  }

  /* ---------- going live: the lock, and where the record stands ----------

     The audit found the app's whole purpose behind a lock with no key —
     "Auto: Off", "live execution LOCKED", and no definition anywhere of what
     would unlock it. engine/livegate.py measures four criteria.

     THE CRITERIA RENDER ON RESULTS now, in the Progression track, because they
     are the same shape and the same measurement as the milestones already
     there. What stays on Settings is the lock itself: the score against the
     gate (#gateChip) and the build fact (#gateFoot).

     Two verdicts, never merged: the EVIDENCE gate is what the operator moves
     by trading the paper book; the ORDER ROUTER is a build task nobody earns
     by trading well. Collapsing them is how the Arm button stayed dead for
     months, and #gateFoot is the half that is not on Results. */
  async function loadLiveGate(){
    try{ lastGate = await api('/api/live-gate'); gateErr = null; }
    catch(err){
      /* Keep no stale criteria. A gate that cannot be read is not a gate the
         record has failed, and last tick's four cards would say it had. */
      lastGate = null;
      gateErr = err.message || 'the server did not answer';
    }
    const chip = $('gateChip');
    if(chip){
      chip.textContent = !lastGate ? 'unreadable'
        : lastGate.ready ? 'evidence met' : `${lastGate.met}/${lastGate.total} met`;
      chip.className = 'chip ' + (!lastGate ? 'chip-red'
        : lastGate.ready ? 'chip-green' : 'chip-amber');
    }
    const foot = $('gateFoot');
    if(foot) foot.textContent = lastGate
      ? (lastGate.build_note || '')
      : `Could not read the criteria — ${gateErr}`;
    renderProgression();
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
    /* The consequence is stated BEFORE the action, not in 10px grey below the
       button that causes it. Only for behavioural rules — a cosmetic setting
       does not open a new window and should not be dressed as if it might. */
    const behavioural = Object.keys(changes)
      .filter(k => (specOf(k) || {}).class === 'BEHAVIOURAL');
    if(behavioural.length){
      const names = behavioural.map(settingLabel).join(', ');
      if(!await SSConfirm({
        title: 'Apply these rule changes?',
        lead: names,
        rows: ['This starts a NEW forward window: your existing record is kept ' +
               'but stops accumulating, because a record spanning two ' +
               'configurations cannot tell you which one produced which result.'],
        note: 'Nothing is deleted.',
        confirmLabel: 'Apply and start a new window'
      })) return;
    }
    b.disabled = true; b.textContent = 'Applying…';
    try{
      const d = await applySettings(changes, 'scanner setup');
      setPending = {};
      await refresh();
      /* A result, not a decision. alert() blocked the page for a fact the
         operator can do nothing about; toast is where every other outcome in
         this app reports, and it is the aria-live region a screen reader is
         already listening to. */
      if(d.baseline) toast('New forward window started (baseline #' + d.baseline.id +
        '). Your previous record is retained, but stops accumulating.', 'ok');
    }catch(err){ markDegraded(String(err)); }
    b.textContent = 'Apply';
    syncSettingInputs(); patchSettingsState();
  });

  $('setReset').addEventListener('click', () => {
    setPending = {}; syncSettingInputs(); patchSettingsState();
  });

  $('btnHalt').addEventListener('click', async e => {
    const b = e.currentTarget, halting = !setValues.halted;
    if(halting && !await SSConfirm({
      title: 'Halt the scanner?',
      rows: ['No NEW entries will be sized.',
             'Open positions still settle — refusing to close a position is ' +
             'not safety.'],
      confirmLabel: 'Halt',
      tone: 'danger'
    })) return;
    b.disabled = true;
    try{
      await applySettings({halted: halting}, halting ? 'operator halt' : 'operator resume');
      await loadSettings();
      toast(halting
        ? 'Halted — no new entries will be sized. Open positions still settle.'
        : 'Resumed — the scanner may size new entries again.',
        halting ? 'warn' : 'good');
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

  /* ONE CARD PER VENUE. Nine bright browser-default boxes sat against the dark
     theme, each with its own Save button, each labelled only by a placeholder —
     which disappears the moment you type, and which a screen reader is not
     required to announce as a name at all. Twelve of the app's unlabelled
     controls were these.

     Now: real <label for>, a masked input with a reveal, ONE Save per venue,
     and a connection state that says whether the venue is usable rather than
     leaving the operator to infer it from an empty box. Values are never
     echoed back by the server and are never logged here. */
  const CRED_LABELS = {
    api_key:    'API key',
    api_secret: 'API secret',
    passphrase: 'Passphrase',
  };
  const CRED_SCOPES = {
    'coinbase-spot': 'Needs READ on accounts and products. No trade or ' +
                     'withdraw permission is required — this app never sends ' +
                     'a real order.',
    'phemex-perp':   'Needs READ only. Do not grant withdrawal rights.',
    'kraken-perp':   'Needs READ only. Do not grant withdrawal rights.',
  };
  function buildCredRows(d){
    const venues = Object.keys(d.status);
    $('credFields').innerHTML = venues.map(v => {
      const nice = v.replace(/-/g, ' ');
      const scope = CRED_SCOPES[v] || 'Read-only access is enough; this app ' +
                                      'never places a real order.';
      return `
      <section class="cred-card" data-credcard="${esc(v)}">
        <header class="cred-head">
          <h3 class="t-label" style="font-size:11px">${esc(nice)}</h3>
          <span class="chip" data-credstate="${esc(v)}">—</span>
        </header>
        ${d.fields.map(f => {
          const id = `cred-${v}-${f}`.replace(/[^a-zA-Z0-9-]/g, '-');
          return `
          <div class="cred-field" data-credrow="${esc(v)}|${esc(f)}">
            <label class="t-label" for="${id}">${esc(CRED_LABELS[f] || f.replace(/_/g, ' '))}</label>
            <div class="fld-row">
              <input id="${id}" type="password" class="t-mono"
                     data-cred="${esc(v)}|${esc(f)}" autocomplete="off"
                     spellcheck="false">
              <button class="btn cred-eye" type="button"
                      data-credreveal="${esc(v)}|${esc(f)}"
                      aria-label="Show ${esc(CRED_LABELS[f] || f)}"
                      aria-pressed="false">Show</button>
              <button class="btn btn-red" type="button"
                      data-credclear="${esc(v)}|${esc(f)}" hidden>Clear</button>
            </div>
          </div>`;
        }).join('')}
        <p class="cred-scope t-body">${esc(scope)}</p>
        <div class="cred-actions">
          <button class="btn btn-primary" type="button" data-credsaveall="${esc(v)}">Save ${esc(nice)}</button>
          <button class="btn" type="button" data-credtest="${esc(v)}">Test connection</button>
          <span class="t-mono cred-result" data-credresult="${esc(v)}"></span>
        </div>
      </section>`;
    }).join('');
  }

  async function loadCredentials(){
    const d = await api('/api/credentials');
    $('credChip').textContent = d.available ? 'DPAPI' : 'unavailable';
    $('credChip').className = 'chip ' + (d.available ? 'chip-green' : 'chip-red');

    // rebuild only when the set of venues/fields itself changes
    const shape = Object.keys(d.status).sort().join(',') + '::' + d.fields.join(',');
    if(shape !== credShape){ buildCredRows(d); credShape = shape; }

    for(const v of Object.keys(d.status)){
      let stored = 0;
      for(const f of d.fields){
        const set = d.status[v][f];
        if(set) stored++;
        const input = document.querySelector(`[data-cred="${v}|${f}"]`);
        const clear = document.querySelector(`[data-credclear="${v}|${f}"]`);
        // The label carries the name now, so the placeholder is free to carry
        // STATE — whether something is already stored under this field.
        if(input) input.placeholder = set ? '•••••••• stored' : 'not set';
        if(clear) clear.hidden = !set;
      }
      /* Connected / Partly set / Not connected, stated rather than inferred
         from whether a box looks empty. "Partly" is its own state because a
         venue with a key and no secret is not usable and not untouched. */
      const chip = document.querySelector(`[data-credstate="${v}"]`);
      if(chip){
        const n = d.fields.length;
        chip.textContent = stored === 0 ? 'not connected'
          : stored < n ? `partly set — ${stored} of ${n}` : 'connected';
        chip.className = 'chip ' + (stored === 0 ? '' : stored < n ? 'chip-amber' : 'chip-green');
      }
    }
  }

  /* Reveal. A masked field the operator cannot check is a field they paste
     into twice. Toggles type only — the value is never copied anywhere. */
  document.addEventListener('click', e => {
    const eye = e.target.closest('[data-credreveal]');
    if(!eye) return;
    const input = document.querySelector(`[data-cred="${eye.dataset.credreveal}"]`);
    if(!input) return;
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    eye.textContent = show ? 'Hide' : 'Show';
    eye.setAttribute('aria-pressed', String(show));
  });

  /* ONE Save per venue. Nine Save buttons meant nine chances to fill a key,
     press the wrong one and believe you were connected. Sends only the fields
     that were actually typed into — an empty box must not clear a stored key. */
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-credsaveall]');
    if(!b) return;
    const venue = b.dataset.credsaveall;
    const out = document.querySelector(`[data-credresult="${venue}"]`);
    const inputs = [...document.querySelectorAll(`[data-cred^="${venue}|"]`)]
      .filter(i => i.value.trim() !== '');
    if(!inputs.length){
      if(out) out.textContent = 'nothing typed to save';
      return;
    }
    b.disabled = true;
    if(out) out.textContent = 'saving…';
    try{
      for(const input of inputs){
        const [v, field] = input.dataset.cred.split('|');
        const r = await fetch('/api/credentials', {method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({venue: v, field, value: input.value})});
        const j = await r.json().catch(() => ({}));
        if(!r.ok) throw new Error(j.detail || ('credentials → ' + r.status));
        input.value = '';                 // never leave a secret in the DOM
        input.type = 'password';
      }
      window.SSData.invalidate('/api/credentials');
      await loadCredentials();
      if(out) out.textContent = '';
      toast(`Saved ${inputs.length} field${inputs.length === 1 ? '' : 's'} for ` +
            `${venue.replace(/-/g, ' ')}.`, 'good');
    }catch(err){
      if(out) out.textContent = '';
      // the message, never the value
      toast('Could not save: ' + err.message, 'bad');
    }
    b.disabled = false;
  });

  /* Test connection. Read-only: it asks the venue whether the stored key is
     accepted, and reports the answer. Nothing is echoed back. */
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-credtest]');
    if(!b) return;
    const venue = b.dataset.credtest;
    const out = document.querySelector(`[data-credresult="${venue}"]`);
    b.disabled = true;
    if(out) out.textContent = 'testing…';
    try{
      const r = await fetch('/api/credentials/test', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({venue})});
      const j = await r.json().catch(() => ({}));
      if(r.status === 404){
        // The endpoint is not built yet. Say so rather than implying a pass.
        if(out) out.textContent = 'not available in this build';
      } else if(r.ok && j.ok){
        if(out) out.textContent = '';
        toast(`${venue.replace(/-/g, ' ')} accepted the key.`, 'good');
      } else {
        if(out) out.textContent = '';
        toast(`${venue.replace(/-/g, ' ')} refused the key — ` +
              `${j.detail || 'no reason given'}`, 'bad');
      }
    }catch(err){
      if(out) out.textContent = '';
      toast('Could not reach the venue to test.', 'bad');
    }
    b.disabled = false;
  });

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
    }catch(err){ toast('Could not save credential: ' + err.message, 'bad'); }
  });

  /* where candidates die, stage by stage — the operator's debugging view */
  /* ---------- Diagnostics: the answer, and the handover ------------------
     The surface's own question is "what is failing, and why". Eight panels
     answered it across 3,722px, and the operator's real use of them is to
     copy what is wrong and hand it over. These two functions are that: one
     sentence at the top, and one button that puts the whole surface on the
     clipboard as text a person can read before they send it.

     Both read ONLY the payloads the panels were painted from. No second
     fetch, no re-derived count (§6) — a handover that disagrees with the
     screen it was copied from is worse than no handover at all. */
  let lastDiagHealth = null, lastDiagTelemetry = null;

  const diagFaults = t => ((t && t.engine_faults) || []).length;
  const diagGates = t => ((t && t.data_gates) || []).length;

  function renderDiagState(){
    const el = $('diagState');
    if(!el) return;
    const h = lastDiagHealth, t = lastDiagTelemetry;
    if(!h && !t) return;                  // keep the skeleton; say nothing yet
    const said = [];
    if(h && h.pending){
      said.push('The audit has not finished its first pass, so nothing below has been checked yet.');
    } else if(h){
      const faults = diagFaults(t), gates = diagGates(t);
      const broken = faults + gates;
      /* The count and the consequence in the same breath. "DEGRADED" alone
         taught the operator nothing about whether to trade today — the whole
         reason the chip on every surface carries its consequence too. */
      said.push(broken
        ? `${broken} thing${broken === 1 ? '' : 's'} failing.`
        : 'Nothing is failing.');
      said.push(h.evaluation_allowed
        ? `The pipeline is ${String(h.status || '').toLowerCase()} and still sizing trades.`
        : `The pipeline is ${String(h.status || '').toLowerCase()} and has stopped sizing trades.`);
    }
    /* The bottleneck belongs in the answer: on a surface about why nothing
       fired, the stage that ate the candidates IS the answer, and it was
       1,000px down the page. */
    const f = t && t.funnel;
    if(f && f.rejected_candidates != null && f.validated != null){
      const seen = f.rejected_candidates + f.validated;
      if(seen) said.push(`${f.rejected_candidates} of ${seen} candidates never became a setup.`);
    }
    el.textContent = said.join(' ');

    const stamp = $('diagStamp');
    if(stamp){
      const v = (t && t.versions) || {};
      const tags = Object.values(v).filter(Boolean).slice(0, 3).join(' · ');
      stamp.textContent = tags ? `${tags} — the report carries all of it` : '';
    }
  }

  /* Plain text, not JSON, and that is a decision. The operator reads this
     before sending it; JSON would paste smaller and cost them the ability to
     check what they are handing over, which is the one thing this surface
     exists to give them. */
  function diagReport(){
    const h = lastDiagHealth || {}, t = lastDiagTelemetry || {};
    const L = [];
    /* Column width is measured, not guessed. A fixed padEnd(16) ran
       NO_ELIGIBLE_PLAYBOOK straight into its own count — "NO_ELIGIBLE_PLAYBOOK142"
       — in the one artifact whose entire job is being read by someone else. */
    const rows = pairs => {
      const w = Math.max(0, ...pairs.map(([k]) => String(k).length)) + 2;
      return pairs.map(([k, v]) => `  ${String(k).padEnd(w)}${v}`);
    };
    const pad = (k, v) => rows([[k, v]])[0];
    L.push('SNIPERSIGHT DIAGNOSTICS');
    L.push(new Date().toString());
    const v = t.versions || {};
    if(Object.keys(v).length) L.push(Object.entries(v).map(([k, s]) => `${k}=${s}`).join(' · '));
    const b = t.baseline;
    if(b) L.push(`baseline ${b.id}${b.label ? ' "' + b.label + '"' : ''}`);

    L.push('', 'STATE');
    L.push(pad('pipeline', (h.status || '—') +
      (h.pending ? ' · audit still running' : '') +
      (h.evaluation_allowed === false ? ' · NOT sizing trades' : ' · sizing trades')));
    const rc = h.rung_counts || {};
    if(Object.keys(rc).length)
      L.push(pad('rungs', Object.entries(rc).map(([k, n]) => `${k.toLowerCase()} ${n}`).join(' · ')));
    (h.blockers || []).forEach(x => L.push(pad('BLOCKER', x.code || x)));

    const faults = (t.engine_faults || []), gates = (t.data_gates || []);
    L.push('', `FAILING NOW (${faults.length + gates.length})`);
    if(!faults.length && !gates.length) L.push('  nothing');
    faults.forEach(x => L.push(`  ${x.symbol} ${x.tf} ${x.engine}: ${x.error}`));
    gates.forEach(x => L.push(`  ${x.symbol} ${x.tf} ${x.gate}: ${x.detail}`));

    const f = t.funnel || {};
    if(Object.keys(f).length){
      L.push('', 'WHY NOTHING FIRED');
      L.push(...rows(Object.entries(f).map(([k, n]) => [k.replace(/_/g, ' '), n])));
    }
    const cr = t.candidate_rejections || {};
    if(Object.keys(cr).length){
      L.push('', 'REJECTED BEFORE VALIDATION');
      L.push(...rows(Object.entries(cr).sort((a, b) => b[1] - a[1]).slice(0, 8)));
    }

    const st = t.stages || {};
    if(Object.keys(st).length){
      L.push('', 'SETUP TELEMETRY');
      L.push(...rows(Object.entries(st).sort((a, b) => b[1] - a[1])
        .map(([k, n]) => [k.replace(/_/g, ' ').toLowerCase(), n])));
    }
    /* GROUPED AND COUNTED, the way the panel on screen shows them. Listed one
       per line this was twelve identical "KNOWN_VENUE_GAPS" and then "…and 87
       more" — 12 lines carrying one fact, and the one number that mattered
       (97) nowhere in them. */
    const warns = h.warnings || [];
    if(warns.length){
      const by = {};
      warns.forEach(w => {
        const k = (w.code || w.rung || 'UNLABELLED').toString();
        by[k] = (by[k] || 0) + 1;
      });
      L.push('', `OPEN ISSUES (${warns.length})`);
      L.push(...rows(Object.entries(by).sort((a, b) => b[1] - a[1])
        .map(([k, n]) => [k.replace(/_/g, ' ').toLowerCase(), '×' + n])));
    }
    return L.join('\n');
  }

  async function loadTelemetry(){
    const t = await api('/api/setup-telemetry?limit=500');
    lastDiagTelemetry = t;
    renderDiagState();
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
      /* The idle label is read from the DOM, not restated here. This line said
         'Run Scan' literally, so the rename to "Check now" — the whole point of
         which was that this button does nothing extra, it just runs the same
         pass immediately — survived exactly one console poll before being
         written back. A label that lives in two places is a label that has
         already diverged. */
      if(!b.dataset.idleLabel) b.dataset.idleLabel = b.textContent.trim();
      b.textContent = s.running ? 'Scanning…' : b.dataset.idleLabel;
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
  /* ═══════════════ EVERY ACTION REPORTS ═══════════════
     A mutating action that changes nothing visible is indistinguishable from a
     click that missed. One toast host, polite to screen readers, auto-clearing
     but never mid-read. Deliberately quiet per the house rule that nothing
     celebrates: it states an outcome and leaves. */
  let toastSeq = 0;
  function toast(text, kind){
    const host = $('toasts');
    if(!host) return;
    const el = document.createElement('div');
    el.className = 't-mono toast' + (kind ? ' toast-' + kind : '');
    el.textContent = text;
    const id = ++toastSeq;
    el.dataset.id = String(id);
    host.appendChild(el);
    // long enough to read a sentence, short enough not to stack up
    setTimeout(() => { if(el.parentNode) el.remove(); }, 6000);
    while(host.children.length > 3) host.firstChild.remove();
  }
  window.SSToast = toast;

  /* ---------- Settings · Claude panel ----------
     The model select writes the SAME localStorage key the copilot drawer
     reads, so there is one preference, not two. Test runs `claude --version`
     server-side — the copilot cannot work without the CLI on PATH, and a
     button that proves it beats a first failure mid-question. */
  (function wireClaudePanel(){
    const sel = $('setCpModel'), test = $('btnCpTest'), chip = $('cpHealth');
    if(!sel) return;
    sel.value = localStorage.getItem('ss-cp-model') || 'sonnet';
    sel.addEventListener('change', () =>
      localStorage.setItem('ss-cp-model', sel.value));
    test.addEventListener('click', async () => {
      test.disabled = true; chip.textContent = 'testing…'; chip.className = 'chip';
      try{
        const d = await api('/api/copilot/health');
        chip.textContent = d.ok ? ('CLI ok · ' + (d.version || '')) : 'CLI missing';
        chip.className = 'chip ' + (d.ok ? 'chip-green' : 'chip-red');
        chip.title = d.ok ? '' : (d.error || 'the `claude` CLI is not on PATH');
      }catch(err){
        chip.textContent = 'check failed'; chip.className = 'chip chip-red';
      }finally{ test.disabled = false; }
    });
  })();

  function scanResult(text, bad){
    const el = $('scanResult');
    if(!el) return;
    el.textContent = `${text} · ${new Date().toISOString().slice(11, 19)}Z`;
    el.className = 't-mono scan-result' + (bad ? ' bad' : '');
    el.hidden = false;
  }

  $('btnScan').addEventListener('click', async e => {
    const b = e.currentTarget;
    b.disabled = true; b.textContent = 'Checking…';
    follow = true;
    try{
      const r = await fetch('/api/scan', {method:'POST'});
      const d = await r.json().catch(() => ({}));
      if(r.status === 409){
        $('consoleState').textContent = 'already scanning';
        scanResult('a scan was already running', true);
        toast('Already checking — the scanner was mid-pass', 'warn');
      }
      else if(!r.ok){
        markDegraded(d.detail || ('scan → ' + r.status));
        scanResult(d.detail || ('scan failed → ' + r.status), true);
        toast('Check failed — ' + (d.detail || r.status), 'bad');
      }
      else { scanResult('checking…'); toast('Checking every watched symbol now'); }
      await pollConsole();
    }catch(err){
      markDegraded(String(err));
      scanResult('could not start a scan', true);
      b.disabled = false; b.textContent = 'Check now';
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

  /* The handover. Refuses rather than copying half a report: before the first
     audit lands there is nothing to hand over, and a clipboard quietly holding
     "pipeline: —" is worse than a button that says wait. */
  $('btnCopyDiag').addEventListener('click', async e => {
    const b = e.currentTarget, was = b.textContent;
    if(!lastDiagHealth && !lastDiagTelemetry){
      toast('Nothing to copy yet — the first audit has not landed.', 'warn');
      return;
    }
    const text = diagReport();
    try{
      await navigator.clipboard.writeText(text);
      b.textContent = 'Copied';
      toast(`${text.split('\n').length} lines copied.`, 'ok');
    }catch(err){
      /* Clipboard access can be refused, and a button that appears to work and
         silently does not is the failure this app keeps writing tests about.
         Select the text instead so the operator can still copy it by hand. */
      b.textContent = 'Select and copy';
      const pre = document.createElement('pre');
      pre.className = 't-mono';
      pre.style.cssText = 'white-space:pre-wrap;max-height:40vh;overflow:auto;' +
        'margin-top:var(--sm);padding:var(--md);border:1px solid var(--border);' +
        'border-radius:var(--r-sm);background:var(--bg)';
      pre.textContent = text;
      const host = document.querySelector('.diag-handover');
      if(host && !host.nextElementSibling?.matches?.('pre')) host.after(pre);
      const r = document.createRange();
      r.selectNodeContents(pre);
      const sel = getSelection();
      sel.removeAllRanges(); sel.addRange(r);
      toast('The browser refused clipboard access — the report is selected below.', 'warn');
    }
    setTimeout(() => { b.textContent = was; }, 2000);
  });

  /* ---------- developer detail ----------
     What this gates: the live server log at the foot of Diagnostics, AND the
     raw internals inside a setup trace — the composite id behind `copy id`,
     the per-stage fact chips, and the failure-attribution line. The CSS lives
     with each of them (ss.css, diagnostics-ui.css) and keys off `body.dev`;
     this function only owns the class, the label and the preference.

     It began as one panel. It used to gate that whole surface — Diagnostics sat in the
     rail between Rules and Learn, so the first thing a new reader clicked
     showed them `ohlc invariant failure` and a log tail — but the surface is a
     public tab now and only the console stayed behind the switch. The name and
     the comment kept the old scope for a while after the behaviour shrank,
     which is how an operator came to press it and find nothing changed.

     The id (`devToggle`) and the storage key (`ss.devMode`) are deliberately
     NOT renamed: the id is referenced elsewhere and the key holds a preference
     that would silently reset for everyone who has one.

     The preference survives a reload, and turning it off while standing on
     Diagnostics moves you somewhere that still exists rather than leaving a
     blank stage. */
  const DEV_KEY = 'ss.devMode';
  const readDev = () => { try{ return localStorage.getItem(DEV_KEY) === '1'; }
                          catch(e){ return false; } };
  function setDev(on, jump){
    // On BODY: the console panel sits on the stage, outside .shell, so a
    // .shell-scoped class could never reach it and the gate was decorative.
    document.body.classList.toggle('dev', on);
    const b = $('devToggle');
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    /* "Developer mode" is a promise this control stopped keeping. It once
       gated the whole Diagnostics surface; Diagnostics is a nav tab now and
       the single rule left is `body:not(.dev) #consolePanel{display:none}`.
       One panel is not a mode, and a label that overstates its scope leaves
       the operator hunting for changes that were never going to happen. */
    b.textContent = on ? 'Developer detail · on' : 'Developer detail';
    b.title = on
      ? 'raw internals are showing: backend console, and fact-level detail in a trace'
      : 'show raw internals: the backend console, and the fact-level detail in a trace';
    try{ localStorage.setItem(DEV_KEY, on ? '1' : '0'); }
    catch(e){ storageFailed('the developer-detail setting', e); }
    /* Turning it ON goes to the thing that was just turned on. This button
       lives in the status bar, on every surface; the panel it reveals is the
       last one on Diagnostics. Pressing it from anywhere else changed nothing
       visible, which is indistinguishable from a control that does not work.
       Reuses the existing pendingJump path rather than scrolling here, so
       there stays one implementation of "go there and show me".

       Only on the way ON, and never at boot — a preference restored on load
       must not hijack the route the operator actually asked for. */
    /* ...but not out from under an open trace drawer. That drawer is one of
       the things this toggle now changes, so someone pressing it while reading
       one is asking to see MORE OF WHAT IS IN FRONT OF THEM — routing them to
       Diagnostics would throw away the thing they were looking at to show them
       a different thing they were not. */
    const reading = document.querySelector('.dx-drawer');
    if(on && jump && !reading){
      pendingJump = 'consolePanel';
      go('diagnostics');
    }
    /* This used to bounce #diagnostics to Command, from the era when the
       WHOLE surface was dev-gated. The surface is a public nav tab now and
       this only gates the console panel — but setDev runs at boot, so the
       leftover bounce was silently eating every #diagnostics deep link and
       reload for anyone with dev mode off (beta pass, 4 Aug 2026). */
  }
  setDev(readDev());
  $('devToggle').addEventListener('click',
    () => setDev(!document.body.classList.contains('dev'), true));

  /* ---------- refresh loop ---------- */
  /* WHICH SURFACE EACH LOADER IS FOR.

     The 30s tick fired all eight regardless of what was on screen, so sitting
     on Command re-fetched the settings, the credentials, the performance
     tables and the telemetry — every half minute, forever. On loopback that
     is free. On a phone it is the difference between leaving the app open and
     watching the data allowance, and /api/setup-telemetry alone is 128KB a
     poll. The console poller in this file already gates itself on visibility;
     this is the same rule applied to the rest.

     `null` means always, and the entries that carry it are not a shortcut:
     the equity figure and the health chip live in the top bar, which is on
     screen no matter which surface is selected, so gating them would freeze
     the two numbers most likely to be glanced at. */
  /* The refused-setup feed, for Diagnostics. Reads the same overview payload
     Command reads — SSData collapses it to one request — and renders through
     the same renderDeck, so the two surfaces can never disagree about which
     setups were refused or why. */
  async function loadRefused(){
    const o = await api('/api/overview', 15000);
    SSState.put('overview', o);
    renderDeck(SSState.deck(), o.rejection_funnel || {});
  }

  /* ═══════════════ LEDGER: three books, never summed ═══════════════

     THE RULE THIS SURFACE ENFORCES. Nothing here adds two books together, and
     nothing may be added later. `manual.arm` never consults the risk
     authority, so a hand-armed position's size was never drawn from the
     engine's $10,000 — the two dollar figures are denominated in different
     capital, over different windows, under different versions. A combined
     "main wallet" total would be an invented number wearing the authority of a
     measured one, which is precisely what the version separation exists to
     prevent.

     Every figure on this surface goes through window.SSFormat. A money surface
     with its own formatter is how "$193 / $195 / 194.68 / $194" happened — one
     number, four renderings, four surfaces, read as four numbers.

     The field names read here are the ones tests/test_ledger_field_contract.py
     holds against the live endpoints. Adding a read means adding it there, or
     a renamed server field silently becomes a confident $0. */
  let lastBook = null, bookErr = null;

  async function loadLedger(){
    try{ lastBook = await api('/api/manual/book'); bookErr = null; }
    catch(err){
      lastBook = null;
      bookErr = err.message || 'the server did not answer';
    }
    renderLedger();
  }

  /* One key/value row, in the shape #riskNow already uses. */
  const lgRow = (k, v, cls) => `<div><span class="k">${esc(k)}</span>` +
    `<span class="v ${cls || ''}">${v}</span></div>`;
  /* One percentage rule, the app's own: 1dp, explicit sign. */
  const pctOf = v => (Number(v) >= 0 ? '+' : '') + pct(v);

  /* A book card. `era` is one of the two nouns the app uses for a window and
     they are NOT interchangeable — the engine's account is scoped to the
     active baseline, the operator's own book is all of history by design. */
  function bookCard(o){
    return `<div class="mc stat-card book-card">
      <div class="mc-top">
        <span class="mc-stamp ${o.stamp}">${esc(o.era)}</span>
        <span class="mc-id t-mono">${esc(o.id)}</span>
      </div>
      <div class="mc-hero">
        <div class="mc-idy">
          <div class="prog-title t-mono">${esc(o.title)}</div>
          <div class="book-money ${o.tone || ''}">${o.money}</div>
          <div class="mc-sub t-label">${esc(o.sub)}</div>
        </div>
        ${o.ring || ''}
      </div>
      <div class="tk-out">${o.rows}</div>
      <div class="book-caveat ${o.caveatTone || ''}">${esc(o.caveat)}</div>
    </div>`;
  }

  function renderLedger(){
    const box = $('ledgerBooks');
    if(!box) return;
    const p = lastPortfolio || {};
    const s = lastScore;
    const cards = [];

    /* ── A. the engine's paper account ──
       Every figure is read, none re-derived. equity/return/drawdown come off
       the payload; the four method numbers come off `lastScore`, which
       renderScoreboard computes once for the Results tiles. Computing them a
       second time here is how two surfaces start disagreeing about one book. */
    const ret = p.return_pct == null ? null : Number(p.return_pct);
    const ruled = s ? s.n : 0;
    cards.push(bookCard({
      era: 'forward window',
      stamp: 'st-t1',
      id: p.baseline && p.baseline.started_at
        ? 'since ' + new Date(p.baseline.started_at * 1000)
            .toLocaleDateString(undefined, {day: 'numeric', month: 'short'})
        : '—',
      title: 'Engine, paper',
      // The account's own headline is its equity, not a P&L: this book is the
      // only one of the three that has a balance.
      money: p.equity == null ? '—' : money(p.equity),
      tone: ret == null || !ruled ? '' : ret >= 0 ? 'up' : 'down',
      sub: p.start_equity == null ? 'paper account'
         : `started ${money(p.start_equity)} · paper`,
      ring: s && s.n ? `<div class="mc-ringcol">${
        ringSvg(s.win, s.win >= 0.5 ? 'ring-ok' : 'ring-low',
                Math.round(s.win * 100) + '%', `of ${s.n}`)}</div>` : '',
      rows:
        lgRow('return', ret == null || !ruled ? '—' : pctOf(ret),
              !ruled ? '' : ret >= 0 ? 'good' : 'bad') +
        lgRow('max drawdown', p.max_drawdown_pct == null ? '—'
              : p.max_drawdown_pct + '%') +
        lgRow('trades closed', s ? fmt(s.n) : '—') +
        lgRow('average R', s ? rr(s.avg) : '—', !s ? '' : s.avg >= 0 ? 'good' : 'bad') +
        lgRow('profit factor', !s ? '—' : s.pf == null ? 'no losses yet' : s.pf.toFixed(2)) +
        lgRow('open risk', p.open_risk_usd == null ? '—' : money(p.open_risk_usd)),
      caveat: 'The engine chose and sized these. Every trade is in the Trade ' +
              'Journal on Results.',
    }));

    /* ── B. the operator's own hand-armed trades ── */
    if(bookErr){
      cards.push(bookCard({
        era: 'recorded book', stamp: 'st-t0', id: 'unreadable',
        title: 'Your trades', money: '—', sub: 'not read',
        rows: '', caveatTone: 'warn',
        caveat: `Could not read your book — ${bookErr}. Any trades you armed ` +
                `are still there; this column just cannot show them.`,
      }));
    } else if(lastBook){
      const b = lastBook;
      const wr = b.win_rate == null ? null : Number(b.win_rate);
      const total = b.total_pnl_usd;
      const priced = b.n - (b.n_no_risk_usd || 0);
      cards.push(bookCard({
        era: 'recorded book',
        stamp: 'st-t1',
        id: `${fmt(b.n)} settled`,
        title: 'Your trades',
        /* NULL IS NOT ZERO. `total_pnl_usd` is null, never "0.00", when no
           settled trade carried a risk figure — six losses with no dollars on
           any of them would otherwise total $0.00 and read as break-even. */
        money: total == null ? '—' : signedMoney(total),
        tone: total == null ? '' : Number(total) >= 0 ? 'up' : 'down',
        sub: 'armed by hand · not risk-sized',
        /* TWO UNITS, ONE SCREEN. `lastScore.win` is a FRACTION (wins/n) and
           manual.book()'s `win_rate` is a PERCENTAGE (0-100). Both rings sat
           side by side reading the same kind of number, and this one fed a
           percentage to ringSvg — which clamps to [0,1], so any win at all
           drew a full green ring labelled 6000%. It read correctly only
           because the live value is 0.0. Normalised here, at the one call
           site that consumes the server's unit. */
        ring: b.n && wr != null ? `<div class="mc-ringcol">${
          ringSvg(wr / 100, wr >= 50 ? 'ring-ok' : 'ring-low',
                  Math.round(wr) + '%', `of ${fmt(b.n)}`)}</div>` : '',
        rows:
          lgRow('settled trades', fmt(b.n)) +
          lgRow('wins', fmt(b.wins)) +
          lgRow('total R', b.total_r == null ? '—' : rr(b.total_r),
                b.total_r == null ? '' : Number(b.total_r) >= 0 ? 'good' : 'bad') +
          lgRow('expectancy', b.expectancy_r == null ? '—' : rr(b.expectancy_r) + '/trade',
                b.expectancy_r == null ? '' : Number(b.expectancy_r) >= 0 ? 'good' : 'bad'),
        /* PRINTED EVERY TIME, including when the count is zero. A ticket armed
           without a valid risk figure stores none, so that trade has an R and
           no dollars, permanently. A caveat that appears only when something
           is missing gives the reader no way to know it is absent. */
        caveatTone: (b.n_no_risk_usd || 0) > 0 ? 'warn' : '',
        caveat: b.n === 0
          ? 'Nothing settled yet. Never added to the account above.'
          : total == null
            ? `No settled trade carried a risk figure, so this book has R and ` +
              `no dollars. Never added to the account above.`
            : `Dollars across ${fmt(priced)} of ${fmt(b.n)} settled trades. ` +
              `Never added to the account above.`,
      }));
    } else {
      cards.push(bookCard({
        era: 'recorded book', stamp: 'st-t0', id: '—',
        title: 'Your trades', money: '—', sub: 'not read yet',
        rows: '', caveat: 'Your book has not been read yet.',
      }));
    }

    /* ── C. the operator's exits on engine trades ──
       The engine picked the setup and the operator picked the exit. This money
       is in NO other total in the store: risk.py never mentions manual or
       override, and manual.book() reads exec facts only. No win rate here on
       purpose — the entry is the engine's and the exit is the operator's, so a
       rate over these rows would be attributing one author's result to two. */
    const oc = p.operator_closed || [];
    const ocUsd = p.operator_closed_usd;
    const ocNo = p.operator_closed_no_usd || 0;
    cards.push(bookCard({
      era: 'forward window',
      stamp: 'st-t1',
      id: `${fmt(oc.length)} closed`,
      title: 'Your exits',
      money: !oc.length ? '—' : ocUsd == null ? '—' : signedMoney(ocUsd),
      tone: !oc.length || ocUsd == null ? '' : Number(ocUsd) >= 0 ? 'up' : 'down',
      sub: 'engine picked · you closed',
      rows:
        lgRow('closes recorded', fmt(oc.length)) +
        lgRow('priced', fmt(Math.max(0, oc.length - ocNo))) +
        lgRow('counted elsewhere', 'nowhere', 'warn'),
      caveatTone: ocNo > 0 ? 'warn' : '',
      caveat: !oc.length
        ? 'You have not closed an engine trade by hand yet.'
        : ocNo > 0
          ? `${fmt(ocNo)} of these carries no dollar figure and is not in the ` +
            `total. This money is in no other total in the app.`
          : 'This money is in no other total in the app — not the equity ' +
            'curve above, not your own book.',
    }));

    box.innerHTML = cards.join('');
    renderLedgerMine();
    renderLedgerExits();
  }

  /* The outcomes that mean a trade actually happened. Same four the manual
     engine settles on and the same four tests/test_ledger_field_contract.py
     calls SETTLED — anything else (CANCELLED, MISSED) never took size. */
  const SETTLED_OUTCOMES = ['TP', 'SL', 'TRAIL_STOP', 'TIMEOUT'];
  const plural = (n, word) => `${fmt(n)} ${word}${n === 1 ? '' : 's'}`;

  /* A trade row, in the shape the Trade Journal already uses so the three
     books read the same way. Not clickable: a hand-armed trade has no engine
     setup_id to open a chart on. */
  function ledgerRow(o){
    const flat = o.r == null || Number(o.r) === 0;
    return `<div class="jnl-row${flat ? '' : Number(o.r) > 0 ? ' up' : ' down'}">
      <div>
        <div class="t-mono" style="font-size:13px;color:var(--fg)">${
          o.dir === 'SHORT' ? '<span class="dir-dn">▼</span>'
          : o.dir === 'LONG' ? '<span class="dir-up">▲</span>' : ''} ${
          esc(tokenOf(o.symbol))}</div>
        <div class="t-label" style="margin-top:3px">${esc(o.tf || '')}</div>
      </div>
      <div class="jnl-say">${esc(o.say)}
        <div class="t-sub">${esc(o.when)}</div>
      </div>
      <div class="jnl-r">${o.r == null ? '—' : rr(o.r)}
        <span class="t-sub">${o.usd == null ? esc(o.noUsd || 'no dollars')
                                            : signedMoney(o.usd)}</span></div>
    </div>`;
  }

  const dayOf = ts => ts == null ? 'no date'
    : new Date(ts * 1000).toLocaleDateString(undefined,
        {day: 'numeric', month: 'short'});

  function renderLedgerMine(){
    const box = $('ledgerMine'), chip = $('ledgerMineChip');
    if(!box) return;
    if(bookErr || !lastBook){
      if(chip) chip.textContent = 'unavailable';
      box.innerHTML = `<div class="empty">Could not read your book${
        bookErr ? ' — ' + esc(bookErr) : ''}.</div>`;
      return;
    }
    const rows = lastBook.trades || [];
    if(chip) chip.textContent = rows.length
      ? `${plural(rows.length, 'row')} · ${fmt(lastBook.n)} settled`
      : 'none';
    if(!rows.length){
      box.innerHTML = '<div class="empty">You have not armed a trade by hand yet.</div>';
      return;
    }
    /* `pnl_usd` is on EVERY row, holding null where there is no dollar figure —
       cancelled and missed orders never took size, and a settled trade whose
       ticket carried no risk figure never will. `risk_usd` is NOT on every row,
       which is why nothing here reads it: money(undefined) renders "$NaN".

       AND AN UNSETTLED ROW HAS NO R. The engine writes `r_multiple: "0"` on a
       cancelled order and on an entry window that expired, because nothing
       happened — but +0.00R on a money surface reads as a trade that broke
       even, which is the same confident-zero bug in a different unit. Those
       rows print an em-dash and say they were never sized. */
    box.innerHTML = rows.map(t => {
      const settled = SETTLED_OUTCOMES.includes(t.outcome);
      return ledgerRow({
        symbol: t.symbol, tf: t.tf, dir: t.direction,
        say: String(t.outcome || '').replace(/_/g, ' ').toLowerCase(),
        when: dayOf(t.resolved_at),
        r: settled ? t.r_multiple : null,
        usd: t.pnl_usd,
        noUsd: settled ? 'no dollars' : 'never sized',
      });
    }).join('');
  }

  function renderLedgerExits(){
    const box = $('ledgerExits'), chip = $('ledgerExitChip');
    if(!box) return;
    const rows = (lastPortfolio || {}).operator_closed || [];
    if(chip) chip.textContent = rows.length ? plural(rows.length, 'row') : 'none';
    if(!rows.length){
      box.innerHTML =
        '<div class="empty">You have not closed an engine trade by hand yet.</div>';
      return;
    }
    box.innerHTML = rows.map(o => ledgerRow({
      symbol: o.symbol, tf: o.tf, dir: o.direction,
      say: 'closed by you',
      when: dayOf(o.closed_at),
      r: o.r_at_close, usd: o.usd_at_close,
    })).join('');
  }

  const LOADER_SURFACE = [
    [null,          () => loadPortfolio()],     // top-bar equity, and Command
    [null,          () => loadHealth()],        // top-bar health chip
    ['command',     () => loadOverview()],
    /* NOT Command-tagged. Its only DOM output is #riskNow, which is on
       SETTINGS — so a reload or a POST /api/system/restart while on Settings
       left that panel literally blank, with no empty-state rule on .tk-out to
       say so. `null` rather than 'settings' because loadRisk also sets
       `liveEnabled` and the accent mode, which are global. */
    [null,          () => loadRisk()],
    // Command-only, deliberately: the sweep costs ~1.7s across 95 symbol/tf
    // pairs and there is no reason to pay it while the operator is reading
    // Results.
    ['command',     () => loadNearLevels()],
    ['settings',    () => loadSettings()],
    ['settings',    () => loadCredentials()],
    ['results',     () => loadPerformance()],
    ['diagnostics', () => loadTelemetry()],
    /* The refused cards live on Diagnostics now, and renderDeck is fed only by
       loadOverview, which is Command-gated. Without an entry here, arriving on
       Diagnostics by hash, bookmark or the 5 key shows whatever was painted
       last — or nothing at all on a cold load — with nothing saying so.
       loadOverview stays Command-gated; this asks for the same payload through
       SSData, which dedupes it to one request. */
    ['diagnostics', () => loadRefused()],
    /* Twice, deliberately. The gate's criteria render in Results' Progression
       track and its chip and build note render on Settings, so both surfaces
       need the payload and neither should pay for the other's. SSData collapses
       concurrent reads of one path to a single request. */
    ['results',     () => loadLiveGate()],
    ['settings',    () => loadLiveGate()],
    /* Its own loader, or arriving on Ledger by hash, bookmark or the 6 key
       shows three skeletons until the next 30s tick. The portfolio half of the
       surface rides the ungated loadPortfolio above; this fetches the manual
       book and paints all three columns. */
    ['ledger',      () => loadLedger()],
  ];
  const currentSurface = () => {
    const on = document.querySelector('.surface.on');
    return on ? on.id.replace(/^s-/, '') : 'command';
  };

  async function refresh(){
    /* The portfolio lands FIRST and alone. The deck's membership is a join
       against it, so running the two concurrently meant a first paint that
       rendered a filled position as a pending card whenever the overview won
       the race. Ordering costs one round trip and removes a whole class of
       "the screens disagree" bug. */
    const first = await Promise.allSettled([loadPortfolio()]);
    const here = currentSurface();
    const jobs = LOADER_SURFACE
      .filter(([surface, run], i) => i !== 0 && (surface === null || surface === here))
      .map(([, run]) => run());
    const results = first.concat(await Promise.allSettled(jobs));
    const failed = results.filter(r => r.status === 'rejected');
    if(failed.length) markDegraded(failed.map(f => f.reason).join('; '), failed.length);
    else {
      if(degraded){
        degraded = false;
        $('healthChip').classList.remove('clickable', 'degraded');
      }
    }                                             // health orb is reset by loadHealth
  }
  /* HOVER IS NOT A DELIVERY MECHANISM.

     Nine elements carried an explanation over 60 characters in a title and
     nothing else: no role, no tabindex, no aria. A title is revealed by a mouse
     pointer and by nothing else — not a finger, not the Tab key, not a screen
     reader — and this app now ships a phone manifest and standalone icons, so
     the pointer is no longer the assumed input.

     The two longest were prose and are now visible text in Settings. The rest
     are status chips in bars with no room to spare, so they keep the tooltip
     and gain the two attributes that make it reachable: a tab stop, and a
     description the assistive layer can read. Same pattern glossary.js already
     applies to .term, generalised — so a future chip earns it by carrying a
     long title, not by someone remembering.

     aria-description, not aria-label: a label REPLACES the accessible name,
     which on a chip reading "DEGRADED" would swallow the word the operator
     needs. glossary.js:170 records that bug being found the hard way. */
  function reachableTitles(root){
    (root || document).querySelectorAll('[title]:not([data-titlefix])').forEach(el => {
      const t = el.getAttribute('title') || '';
      if(t.length <= 60) return;
      if(!el.matches('a[href],button,input,select,textarea,[tabindex]')) el.tabIndex = 0;
      if(!el.hasAttribute('aria-description') && !el.hasAttribute('aria-label'))
        el.setAttribute('aria-description', t);
      el.dataset.titlefix = '1';
    });
  }
  reachableTitles();
  /* Observed, not polled. Titles are written by eight renderers across five
     files at times this module does not control — a position row appears the
     moment the portfolio poll lands, and on a timer it would sit unreachable
     until the next sweep. The observer is debounced and only ever adds two
     attributes, and it skips anything already stamped, so it cannot loop. */
  {
    let pending = 0;
    const obs = new MutationObserver(() => {
      clearTimeout(pending);
      pending = setTimeout(() => reachableTitles(), 250);
    });
    obs.observe(document.body, {
      subtree: true, childList: true,
      attributes: true, attributeFilter: ['title']
    });
  }

  refresh();
  booted = true;
  setInterval(refresh, 30000);
})();
