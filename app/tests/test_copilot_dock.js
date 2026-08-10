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
const CSS = S('static/ss.css');
const SERVER = S('server.py');
const ENGINE = S('engine/copilot.py');


// Regexes built with chr(92) at authoring time so no tool between here and
// disk can eat an escape -- this file has been bitten by that before.
const SEND_SIG = new RegExp('async function send\\(([^)]*)\\)');
const READS_BOX = new RegExp('const text = String\\(ta\\.value');
const BLOCK_COMMENT = new RegExp('/\\*[\\s\\S]*?\\*/', 'g');
const LINE_COMMENT  = new RegExp('^\\s*//.*$', 'gm');
const SEND_CALL_WITH_ARG = new RegExp('[^\\w.]send\\(\\s*[^)\\s]', 'g');
let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('Spotter dock');

ok('Spotter has one launcher in the sidebar, bound in one place', () => {
  assert(/<nav class="nav">[\s\S]*id="btnSpotter"/.test(HTML), 'no Spotter sidebar button');
  assert(!/id="btnCopilot"/.test(HTML), 'the old topbar Copilot button still exists');
  assert(/getElementById\('btnSpotter'\)/.test(CP), 'copilot.js does not own the Spotter button');
  assert(!/btnSpotter/.test(CHART),
    'chart.js still binds the button — the dock is an app feature, not a chart feature');
});

ok('Spotter survives a phone as the sixth bottom-rail control', () => {
  const rules = CSS.replace(BLOCK_COMMENT, '');
  for (let at = rules.indexOf('#btnSpotter'); at !== -1;
       at = rules.indexOf('#btnSpotter', at + 1)) {
    const block = rules.slice(at, rules.indexOf('}', at));
    assert(!/display\s*:\s*none/.test(block),
      'a CSS rule hides #btnSpotter; phones need a non-keyboard way in');
  }
  assert(/grid-template-columns:repeat\(6,minmax\(0,1fr\)\)/.test(rules),
    'the mobile rail does not reserve a sixth slot for Spotter');
});

ok('a dock, not a modal', () => {
  assert(/cp-dock/.test(CP), 'no dock');
  assert(!/cp-scrim/.test(CP),
    'the scrim is back — asking a question must not dim the page it is about');
  assert(!/aria-modal/.test(CP), 'the dock must not trap the page');
});

ok('Spotter combines observer chat and local capture', () => {
  assert(/>Spotter</.test(CP), 'the dock still presents itself as Copilot');
  assert(/>Observe</.test(CP) && />Capture</.test(CP), 'the two Spotter modes are missing');
  assert(/getDisplayMedia/.test(CP), 'Capture never asks the browser for a screen or tab');
  assert(/new window\.MediaRecorder/.test(CP), 'Capture never records the selected stream');
  assert(/URL\.createObjectURL/.test(CP), 'the finished recording has no local replay');
  assert(/download="snipersight-spotter-/.test(CP), 'the local recording cannot be downloaded');
  assert(/Analyze recording/.test(CP), 'the completed capture has no AI review action');
  assert(/sampleCaptureFrames/.test(CP), 'analysis sends the full video instead of sampled frames');
  assert(/original video is not uploaded/.test(CP), 'the sampled-frame disclosure is missing');
  assert(/fetch\('\/api\/spotter\/analyze'/.test(CP), 'sampled frames never reach the reviewer');
  assert(/spotter_analyze/.test(SERVER), 'the observer-only review endpoint is missing');
  assert(!/captureBlob[^\n]*fetch/.test(CP), 'Capture uploads the original video blob');
});

ok('Capture offers the SniperSight tab itself', () => {
  assert(/preferCurrentTab:\s*true/.test(CP),
    'the browser is not asked to promote the tab the operator is using');
  assert(/selfBrowserSurface:\s*'include'/.test(CP),
    'the browser is allowed to hide the current SniperSight tab again');
  assert(/displaySurface:\s*'browser'/.test(CP),
    'the chooser is not told that a browser tab is the preferred surface');
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

/* MINIMIZE IS NOT CLOSE — operator request 2026-08-10, after the floating
   beacon in the old snipersight-trading cockpit. Close stops a recording;
   minimize folds the dock into a draggable beacon while the recording, the
   elapsed clock, the transcript and a thinking reply all keep running. The
   pins below are the properties a later session could quietly undo. */
ok('minimize folds to a beacon without touching the recording', () => {
  assert(/id="cpMin"/.test(CP), 'the dock has no Minimize control');
  const h = CP.slice(CP.indexOf("getElementById('cpMin')"),
                     CP.indexOf("getElementById('cpMin')") + 300);
  assert(/minimized = true/.test(h), 'Minimize does not set the minimized state');
  assert(!/stopCapture|close\(\)/.test(h),
    'Minimize travels close\'s path — folding the dock away mid-capture is ' +
    'exactly when the recording must keep running');
  const cl = CP.slice(CP.indexOf('function close()'),
                      CP.indexOf('function close()') + 220);
  assert(/stopCapture\(\)/.test(cl),
    'close() no longer stops an active recording — minimize exists so that ' +
    'CLOSE can keep meaning stop');
});

ok('the head wraps and its buttons never shrink — Close stays whole', () => {
  /* Adding Minimize made six items share one non-wrapping flex row; on a
     phone-width dock the flex algorithm pushed the LAST item — Close — past
     the dock's edge, clipping the word (reported 2026-08-10). Geometry can't
     be proven from source, but the two properties that make the clip
     impossible can: the row may wrap, and no button may shrink. */
  const at = CSS.indexOf('.cp-dock .cp-head{');
  const rule = CSS.slice(at, CSS.indexOf('}', at));
  assert(/flex-wrap:wrap/.test(rule),
    'the head row cannot wrap, so a squeeze clips its last control');
  assert(/\.cp-dock \.cp-head \.btn\{flex:none\}/.test(CSS),
    'head buttons can shrink below their label again');
  assert(/\.cp-dock \.cp-sub\{display:none\}/.test(CSS),
    'the subtitle no longer gives way on phones — it duplicates the tabs ' +
    'directly beneath it, and it was the space Close needed');
});

ok('the beacon is a real button and a minimized recording stays loud', () => {
  assert(/class="cp-beacon/.test(CP) && /<button type="button" class="cp-beacon/.test(CP.replace(/\s+/g, ' ')),
    'the beacon is not a <button> — the keyboard cannot restore what the ' +
    'mouse minimized');
  assert(/aria-label="Restore Spotter/.test(CP), 'the beacon does not say what it does');
  assert(/REC <span id="cpElapsed"/.test(CP),
    'a minimized recording loses its clock — the capture timer looks up ' +
    '#cpElapsed by id each tick, so the beacon must carry it');
  assert(/\.cp-beacon\.rec/.test(CSS) && /--red/.test(CSS.slice(CSS.indexOf('.cp-beacon.rec'), CSS.indexOf('.cp-beacon.rec') + 300)),
    'the recording state has no red register on the beacon');
});

ok('a drag is not a click, measured from the press point', () => {
  assert(/if\(moved\)\{ moved = false; return; \}/.test(CP),
    'the click that ends a drag also restores the dock');
  assert(/drag\.x0/.test(CP) && /drag\.y0/.test(CP),
    'drag slop is not measured from where the pointer went down — measured ' +
    'against the stored position it skips itself on first use, and every ' +
    'phone tap becomes a micro-drag that swallows the restore');
  assert(/setPointerCapture/.test(CP), 'the drag loses the pointer at the viewport edge');
});

ok('the beacon position survives, clamped to the screen that loads it', () => {
  assert((CP.match(/ss-cp-beacon-pos/g) || []).length >= 2,
    'the dragged position is not both read and written');
  assert(/function clampBeacon/.test(CP),
    'no clamp — a position saved on a desktop strands the beacon off-screen ' +
    'on a phone');
  assert(/addEventListener\('resize'/.test(CP.replace(/window\./g, '')) || /addEventListener\("resize"/.test(CP),
    'nothing re-clamps on resize or rotation');
  assert(/touch-action:none/.test(CSS.slice(CSS.indexOf('.cp-beacon{'), CSS.indexOf('.cp-beacon{') + 400)),
    'without touch-action:none the browser claims the drag gesture for scroll');
  assert(/min-height:44px/.test(CSS.slice(CSS.indexOf('.cp-beacon{'), CSS.indexOf('.cp-beacon{') + 400)),
    'the beacon is under the 44px thumb floor every other control holds');
});

ok('explicit opens unfold; the sidebar button restores before it closes', () => {
  const op = CP.slice(CP.indexOf('function open('), CP.indexOf('function open(') + 300);
  assert(/minimized = false/.test(op),
    'a Diagnose row or Ask button calling open() leaves the dock folded, ' +
    'with the question trapped behind a beacon');
  assert(/if\(ctx && minimized\)\{ minimized = false; render\(\); return; \}/.test(CP),
    'the sidebar button closes a minimized Spotter instead of restoring it — ' +
    'killing a session the operator only folded away');
});

ok('the boundaries did not move', () => {
  assert(/cannot arm/.test(CP), 'the dock stopped saying it cannot arm');
  assert(/never enters the trading record/.test(CP), 'the capture boundary is gone');
  assert(/Nothing is uploaded/.test(CP), 'local-only capture is no longer stated');
  assert(/'ss-cp-model'/.test(CP),
    'the model preference must stay the ONE key Settings also writes');
});

/* THE QUESTION THE OPERATOR TYPED, NOT THE EVENT THAT SENT IT.

   send() took an `override` that shadowed the textarea, and #cpSend is bound
   straight to it, so a click called send(PointerEvent), the override was
   non-null, and the message posted to the model was the literal string
   "[object PointerEvent]". Every click asked that; the box was never read.

   It only ever half-broke, which is why it survived: Enter calls send() with
   no argument and works perfectly, so the dock looked functional and only the
   button was wrong.

   The parameter was already dead when it broke. Suggestion chips used to call
   send(theirText); 5bf8038 changed them to fill the textarea instead, on the
   principle that the input belongs to the operator. After that nothing filled
   `override` deliberately, and only the browser did.

   The lesson is the assertion: a function bound directly to an event handler
   must not take a first parameter it would trust. */
ok('the send button asks what is in the box, not what clicked it', () => {
  const sig = CP.match(SEND_SIG);
  assert(sig, 'send() is gone or renamed');
  assert(sig[1].trim() === '',
    'send() takes a parameter again (' + sig[1].trim() + ') while #cpSend is ' +
    'bound directly to it, so a click passes the PointerEvent as the question');
  assert(READS_BOX.test(CP),
    'send() no longer reads the textarea as the question');
});

ok('nothing calls send with an argument', () => {
  // Comments stripped first. copilot.js explains this bug by NAMING the shape
  // that caused it -- send(PointerEvent), send(theirText) -- and a scan that
  // reads prose as code reports the explanation as the defect. The first run
  // of this test did exactly that.
  const code = CP.replace(BLOCK_COMMENT, ' ').replace(LINE_COMMENT, ' ');
  const bad = code.match(SEND_CALL_WITH_ARG) || [];
  assert(bad.length === 0,
    'send() is called with an argument, which reintroduces the parameter ' +
    'this test exists to keep absent: ' + bad.join(', '));
});
console.log('\n  ' + passed + ' passed');
