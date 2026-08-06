/* The edge panel must report the engine's answer, not compose its own.

   `/api/edge-stats` has always served `by_tf`, `confound`, `verdict` and
   `counts`. `edgeview.js` fetched all of it and rendered none of it, while
   writing its own verdict prose from `lo`/`hi`. Two problems in one file:

     · a second authority for the one number this panel exists to state
       carefully. The engine's verdict names the fee basis it was computed on;
       the local one did not. They agreed by luck, on separate code paths.
     · the per-timeframe split — the highest-value figure in the payload —
       discarded. The operator slices this book by timeframe from memory
       whether or not the UI helps, and unaided concludes "1H works, 4H is
       broken" from four means whose intervals all overlap each other and zero.

   These tests pin the REFUSALS, because the refusals are the design:
   rows never sort, the mean is never coloured, a slice under the sample floor
   prints the engine's own refusal and no mean, and a missing verdict refuses
   rather than falling back to locally-authored prose.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const APP = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(APP, 'static', 'edgeview.js'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

/* --- a DOM stub just large enough to run the module ------------------- */
function harness(payload) {
  const root = {innerHTML: '', id: 'edgeRoot'};
  const head = {appendChild() {}};
  global.document = {
    getElementById: id => (id === 'edgeRoot' ? root : (id === 'ev-css' ? null : {textContent: ''})),
    createElement: () => ({}),
    head,
  };
  global.window = {};
  global.fetch = async () => ({ok: true, json: async () => payload});
  // Module is an IIFE that calls load() itself; run it and let the microtask settle.
  new Function(SRC)();
  return new Promise(res => setImmediate(() => res(root.innerHTML)));
}

const BASE = {
  sufficient: true,
  algo_version: 'exec-v0.17-draft',
  counts: {exec_facts: 644, filled: 644, shadow_venue: 243, traded_venue: 401,
           unfilled_missed: 0, excluded_no_stop_distance: 0,
           excluded_no_fee_record: 0, filtered_out_strategy: 0},
  book: {n: 401, mean_r: 0.0745, win_rate: 0.33, max_consecutive_losses: 21,
         mean_r_gross: 0.198, mean_costs_r: 0.1237,
         avg_win_r: 2.627, avg_loss_r: -1.122,
         bootstrap: {ci_lo: -0.111, ci_hi: 0.258, p_gt_zero: 0.7988, resamples: 8000}},
  verdict: {code: 'INDISTINGUISHABLE',
            text: 'At venue-real fees the 95% CI [-0.111, +0.258] R INCLUDES ZERO.'},
  by_tf: {
    '15m': {n: 110, mean_r: 0.1038, bootstrap: {ci_lo: -0.2, ci_hi: 0.41, p_gt_zero: 0.8}},
    '1H':  {n: 179, mean_r: 0.2794, bootstrap: {ci_lo: 0.02, ci_hi: 0.54, p_gt_zero: 0.98}},
    '4H':  {n: 62,  mean_r: -0.3548, bootstrap: {ci_lo: -0.79, ci_hi: 0.08, p_gt_zero: 0.06}},
    '1D':  {n: 47,  mean_r: -0.1347, bootstrap: {ci_lo: -0.6, ci_hi: 0.33, p_gt_zero: 0.28}},
    '1W':  {n: 3, mean_r: null, bootstrap: null,
            refusal: 'below the 10-trade floor. No expectancy, CI or verdict is reported.'},
  },
  confound: {slices: {'15m': {confounded: false, note: 'single-generation book'},
                      '1H': {confounded: false, note: 'single-generation book'},
                      '4H': {confounded: false, note: 'single-generation book'},
                      '1D': {confounded: false, note: 'single-generation book'},
                      '1W': {confounded: false, note: 'single-generation book'}}},
  scenarios: [], caveats: [], warnings: [],
};

const clone = o => JSON.parse(JSON.stringify(o));

(async () => {
  console.log('edgeview render');

  const html = await harness(clone(BASE));

  ok('renders the ENGINE verdict text, not locally-composed prose', () => {
    assert(html.includes('INDISTINGUISHABLE'), 'verdict code missing');
    assert(html.includes('At venue-real fees'), 'engine verdict text missing');
    assert(!html.includes('Indistinguishable from break even. The interval crosses'),
           'the old locally-authored verdict string is still being rendered');
  });

  ok('every timeframe appears', () => {
    for (const tf of ['15m', '1H', '4H', '1D', '1W']) {
      assert(html.includes('>' + tf + '<'), 'missing timeframe ' + tf);
    }
  });

  ok('rows are in ladder order, never sorted by expectancy', () => {
    const order = ['15m', '1H', '4H', '1D', '1W'].map(tf => html.indexOf('>' + tf + '<'));
    for (let i = 1; i < order.length; i++) {
      assert(order[i] > order[i - 1],
             'timeframe rows are out of ladder order — did they get sorted?');
    }
    // 1H has the best mean; if sorted by expectancy it would lead.
    assert(html.indexOf('>15m<') < html.indexOf('>1H<'),
           'best-performing timeframe floated to the top');
  });

  ok('a slice under the sample floor prints the refusal and NO mean', () => {
    assert(html.includes('below the 10-trade floor'), 'refusal not rendered verbatim');
    assert(!html.includes('n=3</span>\n        <span style="color:var(--fg-2)">'),
           'a mean was rendered for the refused slice');
  });

  ok('the mean is never coloured green or red', () => {
    // means render in fg-2; colour belongs to the interval band only.
    assert(!/ev-tf-mean" style="[^"]*background:var\(--green\)/.test(html),
           'mean marker coloured green');
    assert(html.includes('color:var(--fg-2)">0.104 R'),
           'a positive mean should still render in the neutral token');
    assert(html.includes('color:var(--fg-2)">-0.355 R'),
           'a negative mean should still render in the neutral token');
  });

  ok('a non-confounded slice shows no reassurance note', () => {
    assert(!html.includes('single-generation book'),
           'confound note rendered when confounded=false — that trains the eye '
           + 'to skip the row that will eventually matter');
  });

  ok('the denominator names what was excluded and why', () => {
    assert(html.includes('401 of 644 simulated'), 'denominator missing');
    assert(html.includes('warmed venue, never tradeable'),
           'shadow exclusion not explained in the operator-facing phrase');
  });

  ok('cost decomposition explains the interval without promising a fee cut', () => {
    assert(html.includes('Where the edge goes'), 'cost split missing');
    assert(html.includes('0.198 R'), 'gross missing');
    assert(!/cut fees/i.test(html), 'implies profitability if fees were removed');
  });

  /* --- refusals ------------------------------------------------------- */
  const noVerdict = clone(BASE); delete noVerdict.verdict;
  const html2 = await harness(noVerdict);
  ok('a missing engine verdict REFUSES rather than falling back', () => {
    assert(html2.includes('does not write one'),
           'panel composed its own verdict when the engine gave none');
    assert(!html2.includes('Indistinguishable from break even. The interval'),
           'fell back to the old local prose');
  });

  const noTf = clone(BASE); delete noTf.by_tf;
  const html3 = await harness(noTf);
  ok('no by_tf renders no section rather than an empty shell', () => {
    assert(!html3.includes('By timeframe'), 'empty timeframe section rendered');
    assert(html3.includes('INDISTINGUISHABLE'), 'rest of the panel should still render');
  });

  const confounded = clone(BASE);
  confounded.confound.slices['4H'] = {confounded: true, note: 'spans exec-v0.15 and exec-v0.16'};
  const html4 = await harness(confounded);
  ok('a genuinely confounded slice IS flagged', () => {
    assert(html4.includes('spans exec-v0.15 and exec-v0.16'),
           'confound note suppressed when confounded=true');
  });

  console.log('\n' + passed + ' passed');
})();
