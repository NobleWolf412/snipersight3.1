/* The Bitcoin cycle backdrop must state only what the model actually claims.

   `/api/cycles` had ZERO callers in the whole of static/ while glossary.js
   already defined `dcl`, `wcl` and `translation` — the model was computed,
   served, and shown to nobody.

   Surfacing it is only an improvement if it carries its own limits. The engine
   is careful in its docstring: fractal detection and band arithmetic are
   MECHANICAL, while band widths, translation thresholds and the push-out rule
   are community heuristics fitted to two or three four-year samples. A panel
   that renders both at the same confidence launders the second into the first.

   These tests pin the honesty properties, not the wording:
     · the two four-year window estimates are shown SEPARATELY and never averaged
     · every claim carries an evidence class
     · counted claims are counted, not asserted
     · the observational boundary is stated where it is read
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const APP = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(APP, 'static', 'weather.js'), 'utf8');
const CSS = fs.readFileSync(path.join(APP, 'static', 'weather.css'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

/* Pull cycleLede() out of the module and run it standalone. */
function lede(payload) {
  const i = SRC.indexOf('function cycleLede(');
  assert(i >= 0, 'cycleLede() not found');
  let depth = 0, j = i, started = false;
  while (j < SRC.length) {
    if (SRC[j] === '{') { depth++; started = true; }
    else if (SRC[j] === '}') { depth--; if (started && depth === 0) { j++; break; } }
    j++;
  }
  const body = SRC.slice(i, j);
  const prelude = `
    const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
      c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const D = ts => new Date(ts*1000).toISOString().slice(0,10);
    const DSTR = s => String(s);
  `;
  return new Function(prelude + body + '; return cycleLede(arguments[0]);')(payload);
}

const PAYLOAD = {
  algo_version: 'cycles-v0.2-draft',
  source_symbol: 'PF_XBTUSD',
  candles: 1590,
  last_candle_ts: 1785283200,
  observational: true,
  accepted_4y_lows: ['2015-01-14', '2018-12-15', '2022-11-21'],
  weekly: {cycles: [
    {start_ts: 1669075200, end_ts: 1685016000, fraction: 0.778, translation: 'right', failed: false},
    {start_ts: 1685016000, end_ts: 1700611200, fraction: 0.928, translation: 'right', failed: true},
    {start_ts: 1700611200, end_ts: 1716422400, fraction: 0.617, translation: 'right', failed: false},
    {start_ts: 1716422400, end_ts: 1732579200, fraction: 0.979, translation: 'right', failed: true},
    {start_ts: 1732579200, end_ts: 1749081600, fraction: 0.927, translation: 'right', failed: false},
    {start_ts: 1749081600, end_ts: 1765756800, fraction: 0.637, translation: 'right', failed: false},
    {start_ts: 1765756800, end_ts: 1780617600, fraction: 0.174, translation: 'left', failed: true},
  ]},
  windows: {
    low_to_low: {start: '2026-07-21', end: '2027-03-21', basis: 'low-to-low'},
    halving_anchored: {start: '2026-10-15', end: '2027-04-15', basis: 'halving-anchored'},
  },
};

console.log('cycle backdrop');
const html = lede(PAYLOAD);

ok('renders at all', () => {
  assert(html && html.includes('Bitcoin backdrop'), 'no backdrop rendered');
});

ok('the two four-year estimates are shown separately, never averaged', () => {
  assert(html.includes('2026-07-21') && html.includes('2027-03-21'), 'low-to-low missing');
  assert(html.includes('2026-10-15') && html.includes('2027-04-15'), 'halving-anchored missing');
  assert(/neither is averaged/.test(html),
         'does not state that the two estimates are deliberately not merged');
  // a merged/mid-point date would be a fabricated claim
  assert(!html.includes('2026-08-'), 'looks like a blended window was computed');
});

ok('counts are counted from the data, not asserted', () => {
  // 1 of 7 left-translated, 3 of 7 failed. The build plan for this panel
  // claimed the latest cycle was the first to peak early AND the first to
  // break; it is the first to peak early but the THIRD to break.
  assert(/only one of 7 to peak early/.test(html),
         'left-translation count is wrong or hardcoded');
  assert(/3 of 7 have done/.test(html),
         'failure count is wrong — it must not be conflated with the peak count');
});

ok('every claim carries an evidence class', () => {
  assert(/mechanical/.test(html), 'the arithmetic claim is not labelled mechanical');
  assert(/heuristic/.test(html), 'the fitted claim is not labelled heuristic');
  assert(/fitted to 2\s*\n?\s*completed four-year cycles/.test(html.replace(/\s+/g, ' '))
         || /fitted to 2 completed/.test(html.replace(/\s+/g, ' ')),
         'the four-year sample size is not stated');
});

ok('the observational boundary is stated where it is read', () => {
  assert(/Never consumed by any trading engine/.test(html),
         'does not say the model controls nothing');
  assert(/nothing here\s+opens, sizes or blocks a trade/.test(html.replace(/\s+/g, ' '))
         || /opens, sizes or blocks a trade/.test(html),
         'the boundary is stated abstractly rather than concretely');
});

ok('the reading is attributed to one series, not to Bitcoin', () => {
  assert(html.includes('PF_XBTUSD'), 'source series not named');
  assert(/one series, not a fact about Bitcoin/.test(html),
         'implies the reading is a property of Bitcoin rather than of this feed');
});

ok('a missing or unavailable payload renders nothing, not an empty shell', () => {
  assert.strictEqual(lede(null), '', 'null payload rendered markup');
  assert.strictEqual(lede({unavailable: true}), '', 'unavailable payload rendered markup');
  assert.strictEqual(lede({}), '', 'empty payload rendered a headline with no content');
});

ok('a right-translated cycle is not described as peaking early', () => {
  const p = JSON.parse(JSON.stringify(PAYLOAD));
  p.weekly.cycles[6] = {start_ts: 1765756800, end_ts: 1780617600,
                        fraction: 0.81, translation: 'right', failed: false};
  const h = lede(p);
  assert(/Peaked late/.test(h), 'right-translated cycle mislabelled');
  assert(!/then broke/.test(h), 'a cycle that did not fail is described as broken');
});

ok('cycle styling never uses the loss colour', () => {
  const cy = CSS.slice(CSS.indexOf('.cy-head'));
  assert(!/--red/.test(cy),
         'the backdrop uses the loss colour — a cycle reading is not a loss');
  assert(/--amber/.test(cy), 'no attention colour defined for an early peak');
});

console.log('\n' + passed + ' passed');
