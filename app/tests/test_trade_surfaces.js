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
  assert(JS.includes('function activatable'), 'one helper, not per-element retrofits');
  assert((JS.match(/tabindex="0" role="button"/g) || []).length >= 2,
    'position and pending rows must be focusable');
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
  assert(/\.shell > #tracerRoot, \.shell > #wizardRoot\{position:absolute\}/.test(CSS),
    'auto-placed mounts pushed the status bar into an implicit fourth row');
});

ok('chrome heights are tokens, shared by the grid and the chart calc', () => {
  assert(/--topbar-h:56px; --statusbar-h:26px/.test(CSS));
  assert(/grid-template-rows:var\(--topbar-h\) 1fr var\(--statusbar-h\)/.test(CSS));
  assert(/calc\(100vh - var\(--topbar-h\) - var\(--statusbar-h\)/.test(CSS),
    'the chart calc must read the same tokens the grid declares');
});

ok('live trade data clears the contrast floor', () => {
  // --fg-4 is 2.2:1 on this ground. These rules carry prices and dollars.
  for (const sel of ['.pos-ends{', '.pos-r .t-sub{']) {
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
  assert.ok(m[0].includes("'ENTRY · DRAFT'") && m[0].includes("t: 'ENTRY'"),
            'draft and engine styles must both survive');
});
ok('a kind change forces a redraw so live styling cannot go stale', () => {
  assert.ok(/want = live \? \('live' \+ \(modified \? '-edited' : ''\)\)/.test(CHART),
            'drawnKind must distinguish live and edited-live');
});
ok('reset names what it reverts to', () => {
  assert.ok(CHART.includes("'Back to live levels'"));
});

console.log(`  ${passed} passed`);
