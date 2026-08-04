/* The copilot has a home, and a second job.

   It was a chart feature: a modal drawer, dimming the page it was asked
   about, reachable from two buttons on one surface. It is now an app
   feature with a chart mode — a right dock toggled from the topbar on any
   surface, context following what the operator is looking at, plus a
   DIAGNOSTICS mode that reads the fault table, the data gates, the quality
   audit and the log tail, so "why is this failing" is one click on a
   Failing-now row.

   The boundaries did not move and are pinned hardest: observer only, cannot
   arm, never recorded.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const CP = S('static/copilot.js');
const CHART = S('static/chart.js');
const FUNNEL = S('static/funnel.js');
const HTML = S('static/shell.html');
const SERVER = S('server.py');
const ENGINE = S('engine/copilot.py');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('copilot dock');

ok('one button, in the topbar, bound in one place', () => {
  assert(/id="btnCopilot"/.test(HTML), 'no topbar button');
  assert(/getElementById\('btnCopilot'\)/.test(CP), 'copilot.js does not own its button');
  assert(!/btnCopilot/.test(CHART),
    'chart.js still binds the button — the dock is an app feature, not a chart feature');
});

ok('a dock, not a modal', () => {
  assert(/cp-dock/.test(CP), 'no dock');
  assert(!/cp-scrim/.test(CP),
    'the scrim is back — asking a question must not dim the page it is about');
  assert(!/aria-modal/.test(CP), 'the dock must not trap the page');
});

ok('context follows the surface', () => {
  assert(/function surfaceCtx/.test(CP), 'nothing derives context from the surface');
  assert(/SSChartCtx/.test(CP), 'the chart context is never read');
  assert(/window\.SSChartCtx = \{symbol: sym, tf\}/.test(CHART),
    'chart.js no longer publishes what it is looking at');
  assert(/kind: 'diagnostics'/.test(CP),
    'every non-chart surface should get the machine as the subject');
});

ok('the diagnostics pack exists server-side and needs no symbol', () => {
  assert(/def build_diag_pack/.test(ENGINE), 'no diagnostic pack builder');
  for (const src of ['engine_faults', 'pipeline_gates', 'quality_runs', 'ENGINE LOG']) {
    assert(ENGINE.includes(src), `the pack never reads ${src}`);
  }
  assert(/context == "diagnostics"/.test(SERVER), 'the endpoint ignores context');
  assert(/build_diag_pack\(con\)/.test(SERVER), 'the endpoint never builds the pack');
});

ok('a failing row opens the dock pre-filled with its own fault', () => {
  assert(/fail-diag/.test(FUNNEL), 'no Diagnose button on fault rows');
  assert(/SSCopilot\.open\(\{kind: 'diagnostics', prefill/.test(FUNNEL),
    'the button does not carry the fault into the question');
  assert(/ctx\.prefill/.test(CP), 'the dock ignores the prefill');
});

ok('the transcript survives a toggle, keyed by context', () => {
  assert(/sessionStorage/.test(CP), 'no persistence at all');
  assert(/'diag'/.test(CP), 'the diagnostics conversation has no stable key');
});

ok('the boundaries did not move', () => {
  assert(/cannot arm/.test(CP), 'the dock stopped saying it cannot arm');
  assert(/never enters the record/.test(CP), 'the not-recorded promise is gone');
  assert(/'ss-cp-model'/.test(CP),
    'the model preference must stay the ONE key Settings also writes');
});

console.log('\n  ' + passed + ' passed');
