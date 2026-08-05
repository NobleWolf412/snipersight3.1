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

/* Newlines normalised on read. This repo is core.autocrlf=true with no
   .gitattributes, so git stores LF and materialises CRLF in the working tree on
   every checkout. Assertions here slice between multi-line anchors written with
   a bare \n, which match a file a previous tool wrote as LF and never match the
   same file after git checks it out — indexOf returns -1, String.slice(a, -1)
   silently runs to the end of the file, and the slice sweeps in code the
   assertion was written to prove absent. That failure looks like a real
   regression in copilot.js and is not one.

   Every other file this suite reads gets the same treatment, because the bug is
   in comparing bytes to a hardcoded newline, not in any one file. */
const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8')
                 .replace(/\r\n/g, '\n');
const CP = S('static/copilot.js');
const CHART = S('static/chart.js');
const FUNNEL = S('static/funnel.js');
const SHELL = S('static/shell.js');
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

/* Repinned 4 Aug 2026. Operator ruling: "maybe get rid of that and allow the
   user to type. but maybe clickable hints to fill in?" — so a caller's question
   is OFFERED as a chip rather than written into the box. The property is
   unchanged and slightly stronger: the fault still travels from the row to the
   dock, and it still cannot be lost, but the operator's input stays theirs. */
ok('a failing row carries its own fault into the dock as an offer', () => {
  assert(/fail-diag/.test(FUNNEL), 'no Diagnose button on fault rows');
  assert(/SSCopilot\.open\(\{kind: 'diagnostics', suggest/.test(FUNNEL),
    'the button does not carry the fault into the dock');
  assert(/ctx\.suggest/.test(CP), 'the dock ignores the caller\'s question');
});

ok('nothing types in the box, and nothing sends, on open', () => {
  // The open-trades panel used to compose a paragraph and fire it the instant
  // the button was clicked — the operator's first sight of the dock was their
  // own name above text they had not written.
  assert(!/ta\.value = ctx\./.test(CP),
    'the dock writes into the textarea on open again');
  assert(!/if\(c && c\.ask/.test(CP), 'a caller can auto-send again');
  assert(!/ask: holdAsk/.test(SHELL),
    'the open-trade button auto-asks again — it must suggest');
  assert(/suggest: holdAsk/.test(SHELL),
    'the composed hold question was dropped rather than offered — it carries ' +
    'the trade\'s own levels and is the one nobody wants to retype');
});

ok('a suggestion fills the box and stops there', () => {
  assert(/data-q/.test(CP), 'suggestions are not clickable');
  const h = CP.slice(CP.indexOf("const sug = document.getElementById('cpSuggest')"),
                     CP.indexOf('ta.focus();\n  }'));
  assert(/ta\.value = b\.dataset\.q/.test(h), 'a chip does not fill the box');
  assert(!/send\(/.test(h),
    'a chip SENDS — clicking a hint must never spend a token on its own');
});

ok('starters step aside once the conversation has started', () => {
  assert(/msgs\.length\) return ''/.test(CP.replace(/\s+/g, ' ')) ||
         /if\(!list\.length \|\| msgs\.length\)/.test(CP),
    'the starter row survives into a live conversation, covering the reply');
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
