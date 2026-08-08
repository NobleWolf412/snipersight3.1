/* The panels the remodel added, and the class of defect each one shipped with.

   Every case here is a bug that reached the running app and was found by
   audit rather than by test: the risk meters, the trade journal, the
   approaching radar, open/pending trades and the ticket panes had no
   coverage at all, so each regression below landed green.

   These assert against the static files as text, matching this repo's other
   JS tests — the point is to pin the CONTRACT (which helper is used, which
   token, which field), not to re-render the DOM.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const CSS = S('ss.css');
const JS = S('shell.js');
const CHART = S('chart.js');
const FUNNEL = S('funnel.js');
const TRACER = S('tracer.js');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('trade surfaces');

/* ---------- money and prices are written one way ---------- */

ok('money() puts the sign outside the currency symbol', () => {
  // "$-19" vs "-$19" vs "−$19" — the same loss rendered three ways across
  // three surfaces because each site formatted it itself.
  const m = JS.match(/const money = n => \(Number\(n\) < 0 \? '-\$' : '\$'\)/);
  assert(m, 'money() must branch on sign before the $ symbol');
  assert(JS.includes('const signedMoney ='), 'signedMoney helper must exist');
});

ok('no site hand-rolls a currency sign', () => {
  assert(!JS.includes("'−'"), 'Unicode minus prefix means a site is formatting money itself');
  const own = JS.match(/=> *'\$' *\+ *Number/g) || [];
  assert.strictEqual(own.length, 0, 'a second $-prefixing helper has reappeared');
});

ok('prices go through px(), which scales to magnitude', () => {
  // toLocaleString() defaults to 3 fraction digits, which collapsed a sub-cent
  // token's entry, stop and target into the same displayed number.
  assert(/const px = v => \{/.test(JS), 'px() must exist at module scope');
  assert(!/\(\+s\.entry\)\.toLocaleString\(\)/.test(JS),
    'deck prices must not use bare toLocaleString()');
  for (const f of ['px(s.entry)', 'px(s.tp)', 'px(s.sl)'])
    assert(JS.includes(f), 'deck must format with ' + f);
});

/* ---------- the risk budget ---------- */

ok('risk budget meters exist and name the binding constraint', () => {
  assert(HTML.includes('id="budgetPanel"') && HTML.includes('id="budget"'));
  assert(JS.includes('function renderRiskBudget'));
  for (const s of ['no slots free', 'halted for today', 'risk budget spent',
                   'room for another trade'])
    assert(JS.includes(s), 'missing binding-constraint label: ' + s);
});

ok('open risk is metered as COMMITTED risk, not filled-only', () => {
  // risk.py adds a trade to open_pos when it is SIZED, not when it fills, so
  // metering open_risk_usd (filled only) advertises budget the engine refuses.
  const b = JS.slice(JS.indexOf('function renderRiskBudget'));
  assert(/active_positions \|\| \[\]\)\s*\.concat\(p\.pending_orders/.test(b.replace(/\n\s*/g, '')),
    'the meter must sum filled AND pending risk');
});

ok('a pending order consumes a position slot', () => {
  const b = JS.slice(JS.indexOf('function renderRiskBudget'));
  assert(/const slots = .*active_positions[\s\S]{0,120}pending_orders/.test(b),
    'slot count must include pending orders');
});

/* ---------- the trade journal ---------- */

ok('journal is not silently truncated', () => {
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  assert(!SERVER.includes('journal[:30]'), 'a slice presented as a total');
  assert(SERVER.includes('"journal_total"'), 'server must emit the untruncated count');
  assert(JS.includes('renderJournal(journal, p.journal_total)'));
  assert(JS.includes('showing '), 'the chip must say "showing N of M" when sliced');
});

ok('MISSED orders never enter the journal', () => {
  // execsim writes outcome=MISSED when an armed limit expires unfilled; the
  // scoreboard counts anything that is not a winner as a loss, so a phantom
  // row was reported as a losing trade.
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  const j = SERVER.slice(SERVER.indexOf('journal = []'), SERVER.indexOf('journal.sort'));
  assert(/outcome"\) == "MISSED"/.test(j), 'journal must skip MISSED exec facts');
});

ok('journal pnl_usd is Decimal, matching the equity curve', () => {
  // Scoped to the journal builder: /api/performance has its own unrelated
  // pnl_usd accumulator that this rule is not about.
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  const j = SERVER.slice(SERVER.indexOf('journal = []'), SERVER.indexOf('journal.sort'));
  assert(!/["']pnl_usd["']: round\(/.test(j),
    'float round() banks to even where the engine rounds half up');
  assert(/pnl_usd["']: float\(\(Decimal\(/.test(j));
});

ok('a journal sub-line with a missing field does not double its separator', () => {
  assert(/\.filter\(Boolean\)\.join\(' · '\)/.test(JS),
    'sub-line clauses must be joined, not concatenated');
});

/* ---------- the approaching radar ---------- */

ok('radar scales against the engine bound, not another feature constant', () => {
  // (1 - d/3) used draft.MAX_DISTANCE_ATR; the engine bound is setups.PROX_ATR
  // = 1, so the bar only ever occupied 67-96% of its track.
  assert(!/1 - d \/ 3/.test(JS), 'the 3-ATR draft radius must not scale this meter');
  assert(JS.includes('const bound = +prox || 1'));
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  assert(SERVER.includes('"prox_atr"'), 'server must publish its own bound');
});

ok('the radar dates its distance instead of asserting it', () => {
  // distance_atr is measured once, at the arming bar, and never refreshed.
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  assert(SERVER.includes('"measured_at"'));
  assert(JS.includes('when it armed'), 'the figure must be dated in the copy');
});

/* ---------- raw engine codes must not reach a trader surface ---------- */

ok('Results "By Strategy" runs keys through the label map', () => {
  assert(/function perfRows\(rows, fmtKey\)/.test(JS));
  assert(JS.includes('perfRows(p.by_strategy, playbookLabel)'));
  // every not-taken table too, or the enum leaks one block lower
  assert((JS.match(/notTakenBlock\(p\.\w+_by_strategy, playbookLabel/g) || []).length >= 2,
    'the untaken and shadow strategy tables leak the enum');
});

/* ---------- Results reports the account's book, not the engine's research ---------- */

ok('performance is partitioned by whether the account took the trade', () => {
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  for (const b of ['untaken_by_symbol', 'untaken_by_strategy', '"totals"'])
    assert(SERVER.includes(b), 'missing bucket: ' + b);
  // route on money first — shadow membership is read at request time, the
  // trade is not, so a demoted venue must not reclassify a funded trade
  const perf = SERVER.slice(SERVER.indexOf('def performance'));
  assert(/if ru is not None:\s*\n\s*tgt = \(by_sym, by_strat\)/.test(perf),
    'routing must test funding before venue');
});

ok('a row never mixes populations', () => {
  const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');
  const perf = SERVER.slice(SERVER.indexOf('def performance'));
  assert(!/"sized": a\["sized"\]/.test(perf), 'sized/n could never disagree');
  assert(/"population": population/.test(perf), 'every row must name its population');
});

ok('the traded table shows what it excluded, as a count only', () => {
  assert(JS.includes('more found, not taken'),
    'the exclusion must travel with the figure it changes the meaning of');
  assert(!/untaken_sum_r|untaken_r/.test(JS),
    'an R from the other population inside the traded table is the original bug');
});

ok('an unfunded table does not call its column "net"', () => {
  assert(JS.includes("'would have been'"),
    'net on unfunded rows lets a hypothetical read as a result');
});

ok('setting descriptions use bare nouns, not deck phrases', () => {
  // PLAYBOOK_LABELS values already carry the noun, so reusing them produced
  // "Allow scale-in add adds."
  assert(JS.includes('CODE_NOUNS'), 'humaniseCodes needs its own map');
  const m = JS.match(/CODE_NOUNS = \{[\s\S]*?\}/)[0];
  assert(/SCALE_IN: 'scale-in'/.test(m), 'SCALE_IN must map to the bare noun');
});

ok('the funnel dictionary covers every refusal the engine can emit', () => {
  for (const code of ['DRAWDOWN_HALT', 'PARTICIPATION_TOO_THIN', 'VETOED'])
    assert(new RegExp('\\b' + code + ':').test(FUNNEL), 'no plain sentence for ' + code);
});

ok('a parameterised code falls back on its BASE, keeping the argument', () => {
  // DRAWDOWN_HALT(12.5%) used to render "drawdown halt(12.5%)".
  assert(/baseCode\(s\)\.replace\(\/_\/g, ' '\)\.toLowerCase\(\) \+ arg/.test(FUNNEL));
});

ok('the trace drawer speaks plainly and does not re-expose rank', () => {
  assert(TRACER.includes('SSFunnel.plain(life.failure_code)'));
  assert(!/data-t="rank"/.test(TRACER),
    'rank is non-monotone against outcomes; the deck removed it deliberately');
});

/* ---------- reachability ---------- */

ok('trace rows are focusable and operable by keyboard', () => {
  /* Was pinned to tabindex="0" role="button" appearing twice — the exact
     pattern the position and pending rows have now DROPPED, because ARIA
     forbids focusable descendants inside a button role and each row nested
     Reasons, Copilot and (when filled) Close. A screen reader computed the
     row's whole contents as the button name and buried the close control in it.

     The property is unchanged and still asserted: both rows are reachable and
     operable by keyboard. They just do it with a real <button> on the symbol
     instead of a div wearing a role. */
  assert(JS.includes('function activatable'), 'one helper, not per-element retrofits');
  /* Re-pinned: one card renderer now serves BOTH a filled position and a
     resting order (missionCardInner takes `filled`), so one occurrence
     covers what two row builders used to. The property is unchanged — the
     symbol is a real <button>, reachable and operable by keyboard. */
  assert((JS.match(/class="mc-tok t-mono pos-sym pos-open"/g) || []).length >= 1,
    'the mission card must expose a real keyboard control on the symbol');
  assert(/missionCardInner\(t, filled/.test(JS),
    'one renderer must still serve both filled positions and resting orders');
  assert(!/tabindex="0" role="button"[\s\S]{0,900}?pos-acts/.test(JS),
    'a row with nested action buttons must not itself be role="button"');
  assert(/keydown/.test(JS) && /e\.key !== 'Enter' && e\.key !== ' '/.test(JS));
  assert(CSS.includes('.traceable:focus-visible'), 'focus must be visible');
});

ok('the ticket panes do not claim a tab pattern they do not implement', () => {
  assert(!/id="tkTabs"[^>]*role="tablist"/.test(HTML),
    'role=tablist without tabs/tabpanels promises behaviour that is absent');
  assert((HTML.match(/data-p="\w+" [^>]*aria-pressed=/g) || []).length >= 1 ||
         /aria-pressed/.test(HTML), 'the pressed state must be exposed');
  assert(CHART.includes("setAttribute('aria-pressed'"), 'and kept in sync');
});

/* ---------- layout invariants ---------- */

ok('hidden hides globally, not just inside the ticket', () => {
  assert(/\[hidden\]\{display:none !important\}/.test(CSS));
  assert(!CSS.includes('.ticket [hidden]{display:none}'),
    'the scoped version guarantees the bug returns outside its scope');
});

ok('overlay mounts do not occupy shell grid rows', () => {
  /* Was pinned to the literal selector `.shell > #tracerRoot, .shell >
     #wizardRoot{position:absolute}`. #copilotRoot was added to the markup later
     and never to that rule, and this test could not notice, because the string
     it asserted was still present and still correct — it just no longer covered
     every mount. The omission stayed invisible while two stray </div>s held all
     three mounts outside .shell, where none of them took a grid track. Closing
     the tree made #copilotRoot take row 3 and squeeze .statusbar to 16.5px.

     So: enumerate the mounts from the markup and require the rule to cover each
     one. A mount added tomorrow fails this the day it lands, which a hardcoded
     selector cannot do. */
  /* Only the mounts that are DIRECT children of .shell matter. #weatherRoot,
     #edgeRoot and the diagnostics roots live inside a surface and belong in
     normal flow. The drawer mounts are the ones between </main> and the status
     bar, which is the whole of .shell that is neither chrome nor stage. */
  const tail = HTML.slice(HTML.indexOf('</main>'), HTML.indexOf('<footer class="statusbar"'));
  const mounts = [...tail.matchAll(/<div id="(\w*Root)"/g)].map(m => m[1]);
  assert(mounts.length >= 3, `expected the drawer mounts in shell.html, found ${mounts}`);
  const rule = (CSS.match(/^\.shell > #\w+Root[^{]*\{position:absolute\}/m) || [''])[0];
  assert(rule, 'no position:absolute rule for the .shell drawer mounts');
  const missing = mounts.filter(id => !rule.includes('#' + id));
  assert(missing.length === 0,
    `${missing.join(', ')} mount(s) auto-place into the shell grid and push the ` +
    'status bar into an implicit fourth row');
});

ok('chrome heights are tokens, shared by the grid and the chart calc', () => {
  assert(/--topbar-h:56px; --statusbar-h:26px/.test(CSS));
  assert(/grid-template-rows:var\(--topbar-h\) 1fr var\(--statusbar-h\)/.test(CSS));
  assert(/calc\(100vh - var\(--topbar-h\) - var\(--statusbar-h\)/.test(CSS),
    'the chart calc must read the same tokens the grid declares');
});

ok('live trade data clears the contrast floor', () => {
  // --fg-4 is 2.2:1 on this ground. These rules carry prices and dollars.
  /* Re-pinned when the hand-picked panel stopped being rows. `.pos-ends` and
     `.pos-r .t-sub` were the row's price line and its dollars-at-risk line;
     `.mc.mine .mc-nums` and `.mc.mine .t-sub` are the same two numbers on the
     card that replaced it. The property is untouched: live money does not
     render at 2.2:1. */
  for (const sel of ['.mc.mine .mc-nums{', '.mc.mine .t-sub{']) {
    const i = CSS.indexOf(sel);
    assert(i > -1, 'missing rule ' + sel);
    const block = CSS.slice(i, CSS.indexOf('}', i));
    assert(!block.includes('var(--fg-4)'), sel + ' renders trade data at 2.2:1');
  }
});

ok('the ticket clears on a failed load', () => {
  // A blank chart labelled XRPUSDT sat above BTC's R:R, size and dollar risk.
  const c = CHART.slice(CHART.indexOf('function clearChart'));
  const body = c.slice(0, c.indexOf('\n  }'));
  for (const s of ['base = null', 'applyLevels()', 'recompute()', "$('tkWhy')"])
    assert(body.includes(s), 'clearChart must reset ' + s);
});

ok('the buying-power remedy names a leverage that actually clears it', () => {
  assert(CHART.includes('const need = Math.ceil(m.notional / equity)'),
    'advising more leverage when even the venue max cannot clear it is harmful');
  assert(CHART.includes('pulls liquidation toward your entry'),
    'the remedy must state its cost');
});

ok('authored overlay notes survive the count', () => {
  assert(HTML.includes('data-note='), 'notes moved out of title so they are not overwritten');
  assert(CHART.includes("[b.dataset.note, count].filter(Boolean).join"));
});


/* MANAGING vs PLANNING. An operator opened the chart on a live short, read the
   position editor as a new-trade form, and could not understand why it refused
   a profit-locking stop. The two modes were separated by one small chip and the
   wording of one button — not enough for a surface where the difference is
   "money at stake" versus "an idea". */
console.log('ticket mode: managing vs new');
ok('the heading names the mode', () => {
  assert.ok(HTML.includes('id="tkMode"'), 'ticket heading must be addressable');
  assert.ok(CHART.includes("'Managing open trade'"), 'holding must say so');
  assert.ok(CHART.includes("'New trade'"), 'not holding must say so');
});
ok('unsaved edits are named in the heading, not just the chip', () => {
  assert.ok(/Managing trade — unsaved/.test(CHART));
});
ok('the whole panel changes, not one chip', () => {
  assert.ok(/classList\.toggle\('managing', holding\)/.test(CHART));
  assert.ok(CSS.includes('.ticket.managing'), 'managing needs its own chrome');
});
ok('live levels are gold, distinct from engine plan and draft', () => {
  const m = CHART.match(/function applyLevels\(\)[\s\S]*?const want/);
  assert.ok(m, 'applyLevels not found');
  assert.ok(m[0].includes("'LIVE · IN AT'"), 'a filled entry is not an ENTRY');
  assert.ok(m[0].includes('#fbbf24'), 'live levels use the armed amber');
  assert.ok(m[0].includes("'PLAN · ENTRY'") && m[0].includes("'ENGINE · ENTRY'"),
            'draft and engine styles must both survive');
});
ok('a kind change forces a redraw so live styling cannot go stale', () => {
  assert.ok(/want = live \? \('live' \+ \(modified \? '-edited' : ''\)\)/.test(CHART),
            'drawnKind must distinguish live and edited-live');
});
ok('every level label says WHOSE it is — no bare "DRAFT"', () => {
  // An operator asked what DRAFT meant. Fair: it is the app's word. The four
  // states now read PLAN / ENGINE / YOURS / LIVE without needing a legend.
  // Label STRINGS, not prose — the comments still explain why DRAFT went.
  assert.ok(!/t: *'[^']*DRAFT/.test(CHART), 'no level is still labelled DRAFT');
  for(const t of ['PLAN · ENTRY', 'ENGINE · ENTRY', 'YOURS · ENTRY', 'LIVE · IN AT'])
    assert.ok(CHART.includes(t), 'missing label: ' + t);
});
ok('an armed order is not labelled twice', () => {
  // Arming drew the order's gold lines while the ticket kept drawing the same
  // levels underneath: six labels stacked on three prices.
  assert.ok(/function positionPrices\(\)/.test(CHART));
  assert.ok(/const taken = positionPrices\(\)/.test(CHART));
  assert.ok(/taken\.some\(v => same\(v, p\)\)/.test(CHART),
            'the ticket must yield to the armed order where they agree');
});
ok('reset names what it reverts to', () => {
  assert.ok(CHART.includes("'Back to live levels'"));
});


/* THE DECK CARD FOR A TRADE YOU ARE ALREADY IN. The card and the position are
   the same trade at two moments, and the deck said nothing — so a held symbol
   read as an untaken opportunity, and "Open chart" landed on a position editor
   the operator had no reason to expect. */
console.log('deck: what you already hold');
ok('the deck is told what the book holds', () => {
  assert.ok(/function indexHeld\(p\)/.test(JS), 'the held index must exist');
  assert.ok(/indexHeld\(p\);/.test(JS), 'and something must feed it');
  assert.ok(JS.includes('active_positions') && JS.includes('pending_orders'),
            'both books count as exposure');
});
ok('setup_id is the exact link, symbol only the fallback', () => {
  assert.ok(/heldSids\.has\(sid\)/.test(JS), 'exact match first');
  assert.ok(/heldSyms\.get\(s\.symbol\)/.test(JS), 'then the market');
  assert.ok(/in this trade/.test(JS) && /already \$\{h\.kind === 'open' \? 'in' : 'bidding'\}/.test(JS),
            'the two claims must read differently — they are different claims');
});
ok('a resting order is not a position', () => {
  assert.ok(/order resting on this — not filled yet/.test(JS));
  // /api/manual/open returns `engine` from active_positions ALONE, so a
  // pending order must not promise a position editor it will not get.
  assert.ok(/const mine = \(heldSyms\.get\(s\.symbol\) \|\| \{\}\)\.kind === 'open'/.test(JS));
  assert.ok(/mine \? 'Manage trade' : 'Review setup'/.test(JS));
});
ok('an opposite-direction card on a held symbol says so', () => {
  assert.ok(/this card is the other way/.test(JS));
});
ok('Manage trade opens the timeframe the POSITION is on', () => {
  assert.ok(/mine \? heldSyms\.get\(s\.symbol\)\.tf : s\.tf/.test(JS),
            'the deck card tf is not necessarily the trade tf');
});
ok('a filled position outranks a resting order on the same name', () => {
  assert.ok(/if\(!syms\.has\(t\.symbol\)\)/.test(JS),
            'iteration order must not decide which claim wins');
});
ok('the deck repaints when the book changes, not on the next poll', () => {
  assert.ok(/lastDeckArgs = \[setups, funnel\]/.test(JS), 'args must be cached');
  assert.ok(/if\(lastDeckArgs\) renderDeck\(lastDeckArgs\[0\], lastDeckArgs\[1\]\)/.test(JS));
  assert.ok(/if\(sig === indexHeld\.sig\) return/.test(JS), 'and only when it changed');
});
ok('the held row is marked, and wears the same amber as the chart', () => {
  assert.ok(CSS.includes('.deck-row.held'), 'held rows need chrome');
  assert.ok(CSS.includes('.deck-row.held-sym'), 'exposure-only is quieter');
  assert.ok(/\.deck-held\{grid-column:1\/-1/.test(CSS),
            'the banner spans the row — 120px would crush the sentence');
  assert.ok(CSS.includes('.btn-amber'), 'Manage trade is an amber action');
});


/* The refusal an operator meets right after closing a position. The deck card
   outlives the trade, so the same drag that was legal a moment ago is refused
   — and the bare geometry rule reads as the app contradicting itself. */
ok('the new-trade stop rule says which mode it is enforcing', () => {
  const TM = S('ticket-math.js');
  assert.ok(/planning a NEW trade/.test(TM));
  assert.ok(/only exists once you are actually in one/.test(TM));
  assert.ok(/inp\.holding === true \? ''/.test(TM),
            'a held position must NOT be told it is planning one');
});


ok('a setup you already closed says so, and says what it paid', () => {
  assert.ok(/operator_closed/.test(JS), 'the payload had this all along');
  assert.ok(/you closed this/.test(JS));
  assert.ok(/signedMoney\(usd\)/.test(JS), 'one currency formatter, not two');
  assert.ok(/you took custody of this/.test(JS), 'ADOPTED is a different exit');
  assert.ok(CSS.includes('.deck-row.done'), 'history is neither opportunity nor exposure');
});
ok('a finished setup never offers Manage trade', () => {
  assert.ok(/&& !doneSids\.has\(s\.setup_id \|\| ''\)/.test(JS),
            'the symbol fallback must not resurrect a closed trade');
});


/* ONE ARM PER SIDE PER CHART. Arm stayed live under a "New trade" heading with
   an order already resting, so a second press armed the same trade twice. */
console.log('arm: no double order');
ok('the ticket will not offer an arm the server would refuse', () => {
  assert.ok(/const dupe = !holding && openPos\.find\(/.test(CHART));
  assert.ok(/!armable \|\| !sym \|\| !!dupe/.test(CHART), 'Arm must be disabled');
  assert.ok(/dupe \? 'Already armed' : 'New trade'/.test(CHART),
            'the heading must stop claiming this is a new trade');
});
ok('the reason is ON the control, not in a hover title', () => {
  assert.ok(HTML.includes('id="tkDup"'), 'the reason needs its own slot');
  assert.ok(/dupEl\.textContent =/.test(CHART), 'and must actually be written');
  // Sharing #tkWarn with the ticket maths means last-writer-wins.
  assert.ok(!/tkWarn'\)\.textContent =[\s\S]{0,80}already have/.test(CHART));
});
ok('the guard is per SIDE, so a hedge is still armable', () => {
  assert.ok(/String\(p\.direction \|\| ''\)\.toUpperCase\(\) === String\(dir\)\.toUpperCase\(\)/
            .test(CHART), 'only the same side blocks');
});


/* OPEN TRADES: the row shows you the trade; the trace keeps its own button. */
console.log('open trades: click, ask, manage');
ok('the row opens the chart, not the trace drawer', () => {
  assert.ok(/data-manage="\$\{esc\(t\.symbol\)\}"/.test(JS), 'rows carry the symbol');
  assert.ok(!/pos-row traceable/.test(JS), 'the whole row is no longer a trace target');
  // go() FIRST: SSChart.open only loads data, it does not navigate. Without
  // it the ticket silently managed a trade on a surface not being looked at.
  /* Re-pinned: the Engaged-detail rows are gone and their delegated handler
     with them. `data-manage` now lives on the mission card and is bound
     per-element in wireCardActions. The PROPERTY is unchanged and is what
     this checks — go() must run BEFORE SSChart.open, because open() only
     loads data and does not navigate. */
  const h = JS.match(/\[data-manage\]'\)\.forEach[\s\S]{0,400}/);
  assert.ok(h && /go\('chart'\)/.test(h[0]), 'the click must navigate');
  assert.ok(h && h[0].indexOf("go('chart')") < h[0].indexOf('SSChart.open'),
    'go() must come first, or the ticket manages a trade off-screen');
});
ok('the trace is still reachable, as its own control', () => {
  // A <button data-trace> inside the row, so nothing was lost by taking the
  // whole-row click away from it.
  assert.ok(/<button class="btn" data-trace=/.test(JS));
  // "Why" did not say why WHAT, and read oddly beside Copilot and Close.
  assert.ok(/>Reasons<\/button>/.test(JS), 'the control names what it opens');
  assert.ok(!/gate-by-gate/.test(JS), 'and its tooltip is plain English');
});
ok('keyboard reaches what the mouse reaches', () => {
  /* Re-pinned, and the property is now satisfied by construction rather than
     by a hand-rolled keydown. The symbol on a mission card is a real
     <button>, so Enter and Space come from the platform and cannot be
     forgotten at the next call site — which is why the old #positions
     keydown listener no longer exists.

     What must hold: the control that opens the chart is a BUTTON carrying
     data-manage, not a div with a click handler. */
  assert.ok(/<button class="mc-tok t-mono pos-sym pos-open" data-manage=/.test(JS),
    'the symbol is not a real button — Enter and Space are lost');
  assert.ok(!/\$\('positions'\)/.test(JS),
    'the deleted positions panel is still referenced');
});
ok('the copilot is OFFERED a HOLDING question, not an entry one', () => {
  assert.ok(/const holdAsk = t =>/.test(JS), 'one composer, shared by both row types');
  assert.ok(/Do not evaluate whether to enter/.test(JS));
  assert.ok(/hold, tighten the stop/.test(JS), 'the three live options');
  /* Repinned 4 Aug 2026: the question is OFFERED, not sent. Operator ruling —
     the box belongs to the operator, so this arrives as the first suggestion
     chip. It must still be COMPOSED (it carries this trade's own levels) and
     it must still reach the dock; it must no longer fire on its own. */
  assert.ok(/suggest: holdAsk\(t\)/.test(JS), 'and it must reach the dock');
  assert.ok(!/ask: holdAsk/.test(JS), 'clicking must not spend a token by itself');
});
ok('the question is built from the payload, not re-copied onto the button', () => {
  assert.ok(/let lastPortfolio = \{\}/.test(JS));
  assert.ok(/lastPortfolio = p \|\| \{\}/.test(JS), 'kept in step with what was rendered');
});

/* THE ACTIVE-TRADE BAND. Managing a live position is a different job, and a
   heading plus a colour was still leaving operators to work that out. */
console.log('chart: active-trade band');
ok('the band exists and only while a position is open', () => {
  assert.ok(HTML.includes('id="tkManage"'));
  assert.ok(/if\(!enginePos\)\{ el\.hidden = true/.test(CHART));
});
ok('R on the band uses the risk TAKEN, not the current stop', () => {
  const f = CHART.match(/function renderManage\(\)[\s\S]*?function refreshArm/);
  assert.ok(f, 'renderManage not found');
  assert.ok(/riskU = Math\.abs\(entry - \+enginePos\.sl\)/.test(f[0]),
            'the denominator must not move when the stop does');
});
ok('a stop move is offered only when it actually improves the position', () => {
  const f = CHART.match(/function renderManage\(\)[\s\S]*?function refreshArm/)[0];
  assert.ok(/const better = v =>/.test(f), 'no move that loosens the stop');
  // "Lock +1R" at +0.3R would sit the wrong side of price and exit at once.
  assert.ok(/const safe = v =>/.test(f), 'no stop on the wrong side of price');
  assert.ok(/better\(be\) && safe\(be\)/.test(f));
  assert.ok(/better\(lock1\) && safe\(lock1\)/.test(f));
});
ok('the band sets levels but never commits', () => {
  const f = CHART.match(/function renderManage\(\)[\s\S]*?function refreshArm/)[0];
  assert.ok(/levels\.sl = parseFloat\(b\.dataset\.mv\)/.test(f));
  assert.ok(!/manual\/arm|positions\/adopt|fetch\(/.test(f), 'one button writes to the book');
});
ok('the band does not rebuild on every mousemove of a drag', () => {
  const f = CHART.match(/function renderManage\(\)[\s\S]*?function refreshArm/)[0];
  assert.ok(/if\(el\.dataset\.h === html\) return/.test(f));
});


/* THE TRACE DRAWER. It opened onto nine stages, each with its rule, its detail
   and up to eight fact chips — three thousand characters to answer "where did
   I fill and why". The ladder is the record and it stays; it is just no longer
   the first thing read. */
console.log('trace drawer: the answer before the audit');
ok('the drawer leads with fill, reason and levels', () => {
  assert.ok(/function summary\(t, verdictChip, life\)/.test(TRACER));
  assert.ok(/filled at/.test(TRACER) && /not filled/.test(TRACER)
            && /never entered/.test(TRACER), 'all three order outcomes');
  assert.ok(/entry \$\{esc\(entry\)\}/.test(TRACER) && /R if it works/.test(TRACER)
            && /at risk/.test(TRACER), 'the levels line');
});
ok('facts are found by key, not by stage label', () => {
  // Labels are prose the server may reword; a summary that silently empties
  // when a label changes is worse than no summary.
  assert.ok(/function factOf\(t, key\)/.test(TRACER));
  assert.ok(/factOf\(t, 'entry'\)/.test(TRACER));
});
ok('the full ladder is collapsed, never removed', () => {
  assert.ok(/<details class="dx-all">/.test(TRACER));
  assert.ok(/Every check \(\$\{all\.length\}\)/.test(TRACER));
  assert.ok(/\$\{stages \|\| '<div class="dx-empty">no stages recorded<\/div>'\}/.test(TRACER),
            'every rung still renders inside it');
});
ok('a failed or warned check stays outside the fold', () => {
  assert.ok(/const notable = all\.filter\(s => s\.status === 'fail' \|\| s\.status === 'warn'\)/
            .test(TRACER));
  assert.ok(/checks need reading/.test(TRACER));
  // and shows the finding, not its eight audit chips
  assert.ok(/stageHtml\(x, true\)/.test(TRACER));
  assert.ok(/\$\{compact \? '' : factRow\(s\.facts\)\}/.test(TRACER));
});
ok('the engine sentence does not repeat the levels line', () => {
  assert.ok(/\/\^\(TP\|SL\|R:R\)/.test(TRACER), 'TP and R:R are dropped from why');
});
ok('no control character survives where a regex escape was meant', () => {
  // /^(TP|SL|R:R)\b/ and humanProse's epoch bounds each held a literal 0x08
  // backspace instead of backslash-b, so neither could ever match. Two of the
  // three predated this change and had silently disabled epoch formatting.
  assert.ok(!/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(TRACER),
            'a stray control byte is an unmatchable regex, and invisible');
});


/* THE STATUS-BAR TOGGLE. It said "Developer mode" from when it gated the whole
   Diagnostics surface. Diagnostics is a nav tab now and one rule is left —
   body:not(.dev) #consolePanel — so pressing it from any other surface changed
   nothing visible, which reads as a broken control. */
console.log('backend console toggle');
// Slice, not a multi-line regex literal: a JS regex cannot span lines, and the
// two previous attempts in this file died on exactly that.
const setDevBody = (() => {
  const i = JS.indexOf('function setDev(on, jump)');
  if(i < 0) return '';
  // To the end of the function, not a fixed byte count: the body grew past a
  // 1800-char window when the toggle gained a second thing to gate, and the
  // assertions below started passing vacuously on a truncated slice.
  // Bound by the next declaration, not a byte count: the body grew past
  // an 1800-char window when the toggle gained a second thing to gate,
  // and these assertions started passing vacuously on a truncated slice.
  const end = JS.indexOf('function ', i + 10);
  return end < 0 ? JS.slice(i) : JS.slice(i, end);
})();
ok('it is named for the one thing it reveals', () => {
  // The label tracks the scope. One panel -> "Backend console"; that plus the
  // raw internals in a trace -> the category, not one of its members.
  assert.ok(/Developer detail/.test(HTML), 'the markup ships the honest label');
  assert.ok(!/>Developer mode</.test(HTML), 'the vague original is gone');
  assert.ok(JS.includes('Developer detail · on'), 'and it says when it is on');
});
ok('turning it on goes to the panel it just revealed', () => {
  assert.ok(setDevBody, 'setDev(on, jump) not found');
  assert.ok(setDevBody.includes("pendingJump = 'consolePanel'"), 'reuses the one jump path');
  assert.ok(setDevBody.includes("go('diagnostics')"));
});
ok('it never hijacks the route at boot, or on the way off', () => {
  assert.ok(setDevBody.includes('if(on && jump && !reading)'),
            'all three conditions, not any one of them');
  assert.ok(JS.includes('setDev(readDev());'), 'boot passes no jump');
  assert.ok(JS.includes("setDev(!document.body.classList.contains('dev'), true)"),
            'only the click asks to jump');
});
ok('the id and the storage key are unchanged', () => {
  // Renaming either would break references and silently reset the preference
  // for everyone who already has one. The label is the part that was wrong.
  assert.ok(/id="devToggle"/.test(HTML));
  assert.ok(JS.includes("DEV_KEY = 'ss.devMode'"));
});


ok('it gates the raw internals in a trace, not just the console', () => {
  const DXCSS = S('diagnostics-ui.css');
  for(const sel of ['.dx-copyid', '.dx-tfacts', '.dx-verdict-owner'])
    assert.ok(DXCSS.includes('body:not(.dev) ' + sel),
              sel + ' must be developer-gated');
  assert.ok(CSS.includes('body:not(.dev) #consolePanel'), 'and still the console');
});
ok('it does not route you away from a trace you are reading', () => {
  // The drawer is one of the things this toggle changes; pressing it there
  // asks for more of what is on screen, not for a different screen.
  assert.ok(setDevBody.includes("document.querySelector('.dx-drawer')"));
  assert.ok(setDevBody.includes('if(on && jump && !reading)'));
});
ok('every stage keeps its facts — map passes the INDEX', () => {
  // `all.map(stageHtml)` fed the array index into `compact`, so eight of nine
  // stages silently lost their fact chips. Only the first, at index 0, kept
  // them; nothing errored and the drawer looked plausible.
  // Strip comments first. The fix's own comment quotes the broken form, so a
  // naive search matches the explanation and fails on correct code.
  // String.fromCharCode(10) rather than a backslash-n literal: three separate
  // escapes written into this repo through patch scripts have landed as the
  // BYTE they denote instead of the characters that spell it.
  const NL = String.fromCharCode(10);
  const code = TRACER.split(NL).filter(l => {
    const t = l.trim();
    return t && !t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*');
  }).join(NL);
  assert.ok(!code.includes('all.map(stageHtml)'),
            'never pass a multi-arg function straight to map');
  assert.ok(TRACER.includes('all.map(s => stageHtml(s))'));
});


/* RESULTS: what a trade paid, and where price went. A stop-out read
   "risked $197 · -$219" and left the operator to work out which number was
   wrong. Neither is: a stop loses 1R of PRICE and the round trip is charged on
   top of it. r_gross and costs_r were in the payload and reached no surface. */
console.log('results: costs, and the bars it happened on');
ok('a row says what the costs were, not just the net', () => {
  assert.ok(JS.includes('const costR = Number(j.costs_r)'), 'costs_r must be read');
  assert.ok(/R costs/.test(JS), 'and named on the row');
  assert.ok(JS.includes('j.r_gross'), 'against the gross, which is the 1R part');
  // Hidden when immaterial rather than printing "+0.00R costs" on every row.
  assert.ok(/costR > 0\.004/.test(JS));
});
ok('a settled trade opens on the bars it happened on', () => {
  assert.ok(/data-jsid=/.test(JS), 'rows carry their setup id');
  assert.ok(/jnl-open/.test(JS) && CSS.includes('.jnl-row.jnl-open'),
            'and look clickable');
  assert.ok(JS.includes("SSChart.open(t.symbol, t.tf, {trade: t})"),
            'the whole trade goes to the chart, not just the symbol');
  assert.ok(JS.includes("go('chart')"), 'and it navigates');
});
ok('the chart draws it as CLOSED, never as a ticket', () => {
  assert.ok(/function drawClosedTrade\(\)/.test(CHART));
  assert.ok(CHART.includes("'CLOSED · IN AT'"));
  assert.ok(/CLOSED · OUT \(/.test(CHART));
  // A settled trade cannot be armed; dressing it as a plan would invite that.
  const f = CHART.slice(CHART.indexOf('function drawClosedTrade()'),
                        CHART.indexOf('function candle_index_at'));
  assert.ok(!/levels\.|pickSetup|armable/.test(f), 'it must not touch the ticket');
});
ok('it moves the view to WHEN, not just what', () => {
  assert.ok(/candle_index_at\(t\.ts\)/.test(CHART));
  assert.ok(/setVisibleLogicalRange/.test(CHART));
  // Landing on the newest bars would float the lines over unrelated price.
  assert.ok(/i - Math\.floor\(span \* 0\.6\)/.test(CHART));
});
ok('a trade older than the loaded candles leaves the view alone', () => {
  const f = CHART.slice(CHART.indexOf('function candle_index_at'),
                        CHART.indexOf('function candle_index_at') + 600);
  assert.ok(/best = null/.test(f), 'null rather than a bar that is not the one');
  assert.ok(/if\(i != null\)/.test(CHART), 'and the caller checks it');
});
ok('the overlay clears so it cannot haunt the next chart', () => {
  assert.ok(/for\(const l of tradeLines\)/.test(CHART));
  assert.ok(/pendingTrade = null/.test(CHART));
});


/* A LABEL THAT CANNOT SURVIVE ITS BOX. "BOTTLENECK" sits absolutely positioned
   inside a 14px overflow:hidden bar, and came apart two ways at once — 11px
   text inherited line-height 1.55 for a 17.05px line box (letters shaved top
   and bottom), and an unbreakable word anchored right with no width limit
   overflowed LEFT and was clipped to its tail. It read as "ECK": a fragment
   that looks like a different word, with nothing to say it was truncated. */
console.log('funnel: the bottleneck tag');
ok('the tag fits the bar it is painted on', () => {
  const DXCSS = S('diagnostics-ui.css');
  const rule = DXCSS.slice(DXCSS.indexOf('.dx-stage-tag {'),
                           DXCSS.indexOf('.dx-stage-foot'));
  assert.ok(rule, '.dx-stage-tag rule not found');
  // includes(), not a regex: three escapes written into this file through
  // patch scripts have landed as the byte they denote, and one of them was
  // here, in the guard for this very bug.
  assert.ok(rule.includes('line-height: 1;'),
            'without an explicit line-height it inherits 1.55 and is clipped');
  assert.ok(/white-space: *nowrap/.test(rule), 'one unbreakable word must not wrap');
  assert.ok(/max-width: *calc\(100% - 12px\)/.test(rule),
            'it must not be able to exceed the track it lives in');
  assert.ok(/text-overflow: *ellipsis/.test(rule),
            'if it ever shortens it has to say so');
});
ok('the track it sits in still clips, which is why the above matters', () => {
  const DXCSS = S('diagnostics-ui.css');
  const track = DXCSS.slice(DXCSS.indexOf('.dx-stage-track {'),
                            DXCSS.indexOf('.dx-stage-fill'));
  assert.ok(/overflow: *hidden/.test(track));
  assert.ok(/height: *14px/.test(track),
            'if this height changes, re-check the tag line-height against it');
});

/* The arm receipt says which of the three things happened.

   Reported: "an error saying I already had one waiting, but it still shows as
   a pending order." The server side of that is fixed and pinned in
   test_manual.py / test_arm_from_a_phone.py. This is the other half — the
   ticket used to READ A REFUSAL AND ANNOUNCE A SUCCESS, pattern-matching the
   engine's duplicate message and replying "your earlier tap landed". For a
   retry of the same order that was true; for a second, different plan on the
   same side it was the opposite of true, and the operator was told a trade
   existed that had just been refused. */
/* Comments stripped first, deliberately: the code below is documented with the
   wrong sentence it used to print, and a text assertion that cannot tell a
   quotation from a behaviour would read that history as the bug returning. */
const armSrc = () => {
  const i = CHART.indexOf("fetch('/api/manual/arm'");
  assert.ok(i > 0, 'chart.js no longer arms through /api/manual/arm');
  return CHART.slice(i, i + 6000).replace(/\/\*[\s\S]*?\*\//g, '');
};
ok('a non-OK arm is reported as a refusal, with nothing claimed for it', () => {
  const arm = armSrc();
  const bad = arm.slice(arm.indexOf('if(!r.ok)'), arm.indexOf('const n = d.book'));
  assert.ok(/refused/.test(bad), 'a refused arm no longer says it was refused');
  assert.ok(!/landed|already have an unresolved/.test(bad),
            'the ticket is guessing again that a refusal was really a success');
});
ok('a retry is announced as the order it repeats, not as a second one', () => {
  const arm = armSrc();
  assert.ok(/d\.already_armed/.test(arm),
            'the ticket does not read the flag that distinguishes a retry, so ' +
            'a repeated tap is announced as a fresh arm');
  assert.ok(/already armed/.test(arm), 'nothing on screen says it was a repeat');
  assert.ok(/d\.resolve_failed/.test(arm),
            'a first resolve pass that failed is silent — the order is on the ' +
            'book unchecked and the receipt does not say so');
});

console.log(`  ${passed} passed`);
