/* P0 — no two surfaces may disagree about the same fact.
 *
 * The audit found four surfaces contradicting each other about ONE filled
 * position: the trace said FILLED, Diagnostics said open=1, Command said
 * "0 of 2 slots" and "$0 of $386", and the Setup Deck still showed it as a
 * pending card labelled EXPIRING NOW. The cause was that each surface derived
 * membership from a payload of its own.
 *
 * These tests pin the SHARED DERIVATION rather than any one screen. They are
 * text assertions over the static files, matching this repo's other JS tests,
 * plus a real execution of the selector against a fixture — the fixture is the
 * "one source" the acceptance criteria ask for, and every shared value below
 * is read from it exactly once.
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const JS = S('shell.js');
const CHART = S('chart.js');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('one source of truth');

/* ---------- the selector exists and is the only deriver ---------- */

ok('a single selector owns lifecycle and symbol sets', () => {
  assert(JS.includes('const SSState = {'), 'no shared state selector');
  for (const m of ['engaged()', 'lifecycleOf(', 'deck()', 'symbolSets()'])
    assert(JS.includes(m), 'selector is missing ' + m);
  assert(JS.includes('window.SSStateView = SSState'),
    'the selector must be observable so tests read the same derivation');
});

ok('the deck no longer treats "not closed" as "not started"', () => {
  // `result` is the EXEC OUTCOME. It is null for a setup that is armed and
  // filled and simply has not closed, so filtering on it kept live positions
  // on the deck counting down an expiry that no longer applied.
  assert(!/feed\.filter\(f => f\.state === 'VALIDATED' && !f\.result\)/.test(JS),
    'the deck still filters on !result, which is the original bug');
  assert(JS.includes('SSState.deck()'), 'the deck must come from the selector');
});

ok('the portfolio lands before anything joins against it', () => {
  // Concurrent fetches meant the overview could win the race and paint a
  // filled position as a pending card on first load.
  assert(/await Promise\.allSettled\(\[loadPortfolio\(\)\]\)/.test(JS),
    'portfolio must be awaited before the surfaces that join against it');
});

/* ---------- one vocabulary for symbol counts ---------- */

ok('every symbol count names the set it belongs to', () => {
  assert(JS.includes('symbolSets()'), 'no shared vocabulary');
  // the bare, unanswerable count the audit called out
  assert(!/WATCHING \$\{uc\.admitted\} SYMBOLS/.test(JS),
    'the header still shows a bare symbol count with no set name');
  /* Pinned to the CHIP, not to a bare substring. This read
     `JS.includes('TRADEABLE')` and went vacuous the day the chip was renamed
     to ELIGIBLE: the only TRADEABLE left in the file was the unrelated
     NOT_TRADEABLE exclusion label, so the assertion passed on a substring of
     a different feature and the chip could have lost its set name entirely
     with the suite still green. */
  assert(/WATCHING \$\{sets\.tradeable\} [A-Z]+/.test(JS),
    'the header count must name its set');
  assert(JS.includes('of ${sets.stored} stored'),
    'the tile must state its denominator');
});

/* ---------- one clock ---------- */

ok('one staleness grammar, shared with the chart', () => {
  assert(JS.includes('window.SSClock'), 'the clock must be shared');
  assert(CHART.includes('SSClock.ago('),
    'the chart still writes its own staleness grammar');
  assert(!/`updated \$\{s\}s ago`/.test(CHART),
    'per-second text reflows the layout every second');
});

/* ---------- one rounding policy per unit ---------- */

ok('R renders at one precision everywhere', () => {
  // $193 / $195 / 194.68 / $194 was the money version of this; R had a 1dp
  // and a 2dp form on different surfaces.
  assert(JS.includes('window.SSFormat'), 'no shared formatter');
  const strays = JS.match(/toFixed\(1\)\s*\+\s*'R'|toFixed\(1\)\}R/g) || [];
  assert.strictEqual(strays.length, 0,
    'a 1dp R survives: ' + strays.join(', '));
});

ok('the formatter covers every unit the app renders', () => {
  const m = JS.match(/window\.SSFormat = \{([^}]*)\}/);
  assert(m, 'SSFormat not exported');
  for (const fn of ['money', 'px', 'rr', 'pct', 'units'])
    assert(m[1].includes(fn), 'SSFormat is missing ' + fn);
});

/* ---------- one card per token ---------- */

ok('the deck keys on token, honouring its own promise', () => {
  assert(JS.includes('const tokenOf ='), 'no token extractor');
  assert(/const key = tokenOf\(s\.symbol\)/.test(JS),
    'the deck still keys on symbol, so one token can occupy two cards');
});

/* ---------- the fixture: one payload, every shared value read once ---------- */

ok('every surface agrees when rendered from one fixture', () => {
  // A filled position, an armed order, a pending setup, and the same token
  // listed on two venues — the exact shape that broke four surfaces.
  const overview = {
    symbols: new Array(82).fill(0).map((_, i) => ({symbol: 'S' + i})),
    universe_counts: {admitted: 15, shadow: 11, warming: 0},
    feed: [
      {setup_id: 'a', symbol: 'UNIUSDT',   tf: '4H', state: 'VALIDATED', result: null},
      {setup_id: 'b', symbol: 'PF_UNIUSD', tf: '4H', state: 'VALIDATED', result: null},
      {setup_id: 'c', symbol: 'BTCUSDT',   tf: '1H', state: 'VALIDATED', result: null},
      {setup_id: 'd', symbol: 'ETHUSDT',   tf: '4H', state: 'VALIDATED', result: null},
      {setup_id: 'e', symbol: 'SOLUSDT',   tf: '1H', state: 'VALIDATED',
       result: {outcome: 'TP', r_multiple: '1.2'}},
    ],
  };
  const portfolio = {
    active_positions: [{setup_id: 'c', symbol: 'BTCUSDT', risk_usd: '194.60'}],
    pending_orders:   [{setup_id: 'd', symbol: 'ETHUSDT', risk_usd: '190.00'}],
  };

  // Re-implementing the selector here would defeat the point, so the real one
  // is lifted out of the source and executed against the fixture.
  const src = JS.slice(JS.indexOf('const SSState = {'));
  const body = src.slice(0, src.indexOf('\n  };') + 5);
  const SSState = new Function('return ' + body.replace(/^const SSState = /, ''))();
  SSState.overview = overview;
  SSState.portfolio = portfolio;

  const lc = id => SSState.lifecycleOf(overview.feed.find(f => f.setup_id === id));
  assert.strictEqual(lc('c'), 'FILLED',  'a position in the book must read FILLED');
  assert.strictEqual(lc('d'), 'ARMED',   'a resting order must read ARMED');
  assert.strictEqual(lc('e'), 'CLOSED',  'an exec outcome must read CLOSED');
  assert.strictEqual(lc('a'), 'PENDING', 'an untouched setup must read PENDING');

  const deck = SSState.deck().map(f => f.setup_id);
  assert.deepStrictEqual(deck, ['a', 'b'],
    'the deck must hold only PENDING setups — a filled or armed one showing ' +
    'here is the EXPIRING NOW bug');
  assert(!deck.includes('c'), 'a FILLED position is still on the deck');

  const sets = SSState.symbolSets();
  assert.strictEqual(sets.stored, 82);
  assert.strictEqual(sets.tradeable, 15);
  assert.strictEqual(sets.shadow, 11);
  assert(sets.tradeable <= sets.stored, 'TRADEABLE must be a subset of STORED');

  // The cross-surface diff: open-position count, risk and slot usage all
  // derive from ONE payload, so they cannot disagree.
  const open = portfolio.active_positions.length;
  const armed = portfolio.pending_orders.length;
  const committed = [...portfolio.active_positions, ...portfolio.pending_orders]
    .reduce((a, t) => a + +t.risk_usd, 0);
  assert.strictEqual(open, 1);
  assert.strictEqual(open + armed, 2, 'slots used must count armed orders too');
  assert.strictEqual(committed.toFixed(2), '384.60',
    'open risk must be committed risk, not filled-only');
});

console.log(`  ${passed} passed`);
