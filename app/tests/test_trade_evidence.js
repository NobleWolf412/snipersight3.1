/* Trade evidence panel: RENDERS the real functions from cockpit/app.js in a
   sandbox, rather than only matching their text. No browser, no endpoint.

   The property that matters most is a negative one: nothing on this surface
   may add up, count or rank the factors. None of them has earned a weight —
   an early grading found one related to results and another not — and a panel
   that turned them into "4 of 6 supportive" would present a guess as a
   measurement (setup_guide.confluence_rows). */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(path.join(__dirname, '../static/cockpit/app.js'), 'utf8');
const start = source.indexOf('/* TRADE EVIDENCE');
const end = source.indexOf('function opportunitiesTable(rows)');
assert(start > 0 && end > start, 'the trade evidence block moved; update this test');
const block = source.slice(start, end);

const scope = {
  esc: v => String(v ?? ''),
  label: v => String(v ?? '—').replaceAll('_', ' '),
  date: v => `date(${v})`,
  empty: (title) => `<empty>${title}</empty>`,
  setupTimes: () => '<times/>',
};
scope.badge = (v, style = 'neutral') => `<b class="${style}">${scope.label(v)}</b>`;
vm.createContext(scope);
vm.runInContext(block + '\nthis.api={evidenceView,compareTable,COMPARE_SORTS,nearestAgainst,STANCE_TONE};', scope);
const {evidenceView, compareTable, COMPARE_SORTS, nearestAgainst, STANCE_TONE} = scope.api;

const evidence = {
  direction: 'SHORT', note: 'Recorded evidence, not predictions.',
  factors: [
    {key: 'htf', factor: '1H trend at confirmation', state: 'SUPPORTS', value: 'with this trade', detail: 'd'},
    {key: 'volume', factor: 'Volume on the confirming candle', state: 'CONFLICTS', value: '0.8x', detail: 'd'},
    {key: 'zone_strength', factor: 'Zone strength', state: 'INFO', value: '77', detail: 'd'},
  ],
  required: [{check: 'A completed candle confirmed the rejection', passed: true, value: 1000},
             {check: 'Risk at least 2× the estimated costs', passed: true, value: '7.05'}],
  economics: {rr_gross: '3.00', rr_net: '2.86', cost_r: '0.14', basis: 'Estimated.'},
  higher_timeframe: {
    as_of: 5000, price: '100', price_timeframe: '5m', price_at: 4800, price_stale: false,
    stance: {label: 'COUNTER_INTO_RUNNING_MOVE', sentence: 'Counter-trend into a move that is still running.'},
    ladder: [{tf: '1H', words: 'running up hard'}, {tf: '1D', words: 'trending down'}],
    pools: {against: [{tf: '1D', level: '120', distance_pct: '20.00',
                       status: 'no sweep recorded by the last closed 1D candle'}],
            toward: [], measured: ['1D']},
    levels: [{tf: '1D', resistance: {price: '105', distance_pct: '5.00', touches: 2}, support: null}],
  },
};

const html = evidenceView(evidence);

// Danger first: the higher-timeframe reading leads the panel.
assert(html.indexOf('still running') < html.indexOf('Confluence when it confirmed'),
  'the higher-timeframe warning must come before the confluence');
assert(html.includes('class="evidence-block htf-bad"'), 'a running move against the trade is drawn as the alarm');
assert(html.includes('Above you (against a short)'), 'a short names the pool ABOVE as the one against it');
assert(html.includes('Daily</strong> 120 · 20.00% away · no sweep recorded by the last closed 1D candle'), 'pool line');
assert(!html.includes('untouched'), 'the record cannot support "untouched" (cold audit)');
assert(html.includes('last closed 5m candle at date(4800)'), 'the price carries its own close time, not page-open time');
assert(!html.includes('out of date'), 'a fresh price carries no staleness warning');
assert(evidenceView({...evidence, higher_timeframe: {...evidence.higher_timeframe, price_stale: true}}).includes('out of date'),
  'a stale price says so');
assert(html.includes('None found'), 'a measured market with nothing in the way says none found');
assert(evidenceView({...evidence, higher_timeframe: {...evidence.higher_timeframe,
  pools: {against: [], toward: [], measured: []}}}).includes('No liquidity records up to daily'),
  'a market with no liquidity records must not read as "none found"');
assert(html.includes('Plan checks — all cleared') && !html.includes('all passed'),
  '"passed" beside "Bot declined" read as its opposite');
assert(html.includes('2 touches'), 'support/resistance shows how often a level held');
assert(html.includes('2.86 R') && html.includes('0.14 R'), 'net reward and cost in R, from the server');
assert(html.includes('date(1000)'), 'the confirming candle is shown as a time, not a raw number');

// THE NEGATIVE PROPERTY. No tally of supporting factors, anywhere.
assert(!/\d+\s*(of|\/)\s*\d+\s*(factors|supportive|supporting)/i.test(html),
  'the panel must never summarise factors as a count');
assert(!/state\s*===?\s*'SUPPORTS'\)?\s*\)?\s*\.length/.test(block) &&
       !/filter\([^)]*SUPPORTS[^)]*\)\.length/.test(block),
  'no code in the evidence block may count supporting factors');
assert(!/score/i.test(block.replace(/no overall score/gi, '').replace(/confluence_rows/g, '')),
  'nothing in the evidence block may compute or show a score');

// A waiting setup says when confluence arrives, and still shows the live HTF read.
const waiting = evidenceView({...evidence, factors: undefined, required: undefined,
  confluence_reason: 'Recorded when this setup confirms.'});
assert(waiting.includes('Recorded when this setup confirms.'));
assert(waiting.includes('still running'), 'the higher-timeframe reading does not wait for confirmation');

// Plain counter-trend is a caution, not the alarm.
assert.equal(STANCE_TONE.COUNTER_TREND, 'warning');
assert.equal(STANCE_TONE.COUNTER_INTO_RUNNING_MOVE, 'bad');

// Compare: sorts read server values only, and there is no ranking key.
assert.deepStrictEqual(Object.keys(COMPARE_SORTS).sort(), ['net_rr', 'newest', 'pool_against']);
const row = (id, rr, pools, at, measured = ['1D'], byHand = true) => ({setup: {symbol: id, direction: 'SHORT', timeframe: '15m', strategy: 'REVERSAL', confirmed_at: at},
  state: 'BLOCKED', tradeable_by_hand: byHand, trade_evidence: {...evidence, economics: {rr_net: rr}, higher_timeframe: {...evidence.higher_timeframe,
  pools: {against: pools, toward: [], measured}}}});
const rows = [row('A', '1.2', [{distance_pct: '3.00'}], 3), row('B', '2.5', [], 1), row('C', '0.9', [{distance_pct: '9.00'}, {distance_pct: '1.00'}], 2)];
assert.equal(nearestAgainst(rows[2]), 1, 'the nearest pool against is the closest on any timeframe');
assert.equal(nearestAgainst(rows[1]), 1e9, 'a measured market with no pool against has the most room');
assert.equal(nearestAgainst(row('D', '1', [], 0, [])), -1,
  'an UNMEASURED market sorts last on room, never first (cold audit)');
assert.deepStrictEqual([...rows].sort(COMPARE_SORTS.net_rr).map(r => r.setup.symbol), ['B', 'A', 'C']);
assert.deepStrictEqual([...rows].sort(COMPARE_SORTS.pool_against).map(r => r.setup.symbol), ['B', 'A', 'C']);
assert.deepStrictEqual([...rows].sort(COMPARE_SORTS.newest).map(r => r.setup.symbol), ['A', 'C', 'B']);

const table = compareTable(rows);
assert.equal((table.match(/data-setup="/g) || []).length, 3, 'every open plan can be opened');
assert(table.includes('Bot declined') && !table.includes('Bot passed'),
  'a plan the bot refused says "declined" — "passed" read as "cleared the checks"');
assert(compareTable([row('E', '1', [], 0, ['1D'], false)]).includes('Not tradeable here'), 'venue cannot place it');
assert(compareTable([row('F', '1', [], 0, ['1D'], null)]).includes('Venue unknown'),
  'an unknown venue is shown as unknown, never as tradeable');
assert(compareTable([]).includes('No open trade plans'), 'an empty compare tab says why');

console.log('trade evidence: ok');
