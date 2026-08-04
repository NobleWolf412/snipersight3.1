/* The last four audit items: a picture with a scale, a page without a hole in
   it, a sentence above every wall of numbers, and a tour instead of a wall.

   #19 — the equity curve was a polyline on a stretched viewBox. It rose or
   fell without ever saying by how much, over what period, or where one trade
   ended and the next began. The by-timeframe CI bars had the same problem in
   miniature: a shared scale that was never drawn, and a zero line with no label
   on it.

   #25 — Rules was a 2-up grid, so every cell took the height of its tallest
   sibling. Credentials became three venue cards tall and Risk stretched to
   match it, leaving ~800px of empty bordered box.

   (#28's summaries were later ruled over-explaining and purged — see
   test_word_budget.js, which now enforces the opposite direction.)

   (#31, the guided tour, died with the Learn surface — 2026-08-03.)
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const SHELL = S('shell.js');
const CSS = S('ss.css');
const EDGE = S('edgeview.js');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('orientation, axes and summaries');

/* ─────────────────────── #19 the equity curve ─────────────────────── */

ok('the curve is measured in pixels, not stretched', () => {
  assert(!/id="eqCurve"[^>]*preserveAspectRatio="none"/.test(HTML),
    'preserveAspectRatio="none" distorts every glyph in the viewBox — that is why ' +
    'this chart could carry no labels');
  assert(/el\.setAttribute\('viewBox', `0 0 \$\{W\} \$\{H\}`\)/.test(SHELL),
    'the viewBox must be set from the measured width');
  assert(/el\.clientWidth/.test(SHELL), 'nothing measures the element');
});

ok('the curve carries a dollar scale and dated ticks', () => {
  const fn = SHELL.slice(SHELL.indexOf('function drawCurve'), SHELL.indexOf('function eqPoint'));
  assert(/money\(v\)/.test(fn), 'gridlines carry no dollar labels');
  assert(/dayFmt\(curve\[i\]\.ts\)/.test(fn), 'the x axis is undated');
  assert(/\$\{dates\}/.test(fn), 'the date labels are built but never rendered');
  assert(/break even \$\{money\(start\)\}/.test(fn),
    'the baseline is drawn but not named');
});

ok('every settlement is marked, until the dots would merge', () => {
  const fn = SHELL.slice(SHELL.indexOf('function drawCurve'), SHELL.indexOf('function eqPoint'));
  assert(/curve\.length <= 90/.test(fn),
    'dots must be dropped once they stop being countable, not drawn on top of each other');
  assert(/<circle/.test(fn), 'no settlement markers');
});

ok('the readout is reachable without a mouse', () => {
  assert(/id="eqCurve"[^>]*tabindex="0"/.test(HTML), 'the chart is not focusable');
  assert(/ArrowLeft: -1, ArrowRight: 1/.test(SHELL), 'no arrow-key navigation');
  assert(/function eqPoint/.test(SHELL) && /pointermove/.test(SHELL),
    'the mouse and the keyboard must drive the same readout');
  assert(/id="eqHover"[^>]*aria-live="polite"/.test(HTML),
    'the readout changes without announcing itself');
});

ok('the readout line reserves its space', () => {
  assert(/\.eq-hover\{[^}]*min-height/.test(CSS),
    'the panel would jump every time the cursor entered the chart');
});

ok('an empty window still says so', () => {
  const fn = SHELL.slice(SHELL.indexOf('function drawCurve'), SHELL.indexOf('function eqPoint'));
  assert(/no closed trades in this window yet/.test(fn), 'the empty state was dropped');
  assert(/a curve needs at least two points/.test(fn),
    'one settlement is not a broken chart and must not read as one');
});

/* ─────────────────── #19 the by-timeframe CI bars ─────────────────── */

ok('the shared CI scale is drawn, with break even named on it', () => {
  assert(/ev-tf-axis/.test(EDGE), 'the bars still have no axis');
  assert(/tick\(0, 'break even', 'on'\)/.test(EDGE), 'zero is drawn but not labelled');
  assert(/R per trade/.test(EDGE), 'the unit is never stated');
  assert(/ev-tf-ticklab \$\{kind\}/.test(EDGE) && /\.ev-tf-ticklab\.hi\{transform:translateX\(-100%\)\}/.test(EDGE),
    'end labels centred on 0% and 100% hang half outside the track');
});

/* ─────────────────────────── #25 Rules ─────────────────────────── */

ok('Rules packs its panels instead of stretching them', () => {
  assert(/<div class="pack-cols">/.test(HTML), 'Rules is still a stretched 2-up grid');
  assert(/\.pack-cols\{column-count:2/.test(CSS), 'no packing rule');
  assert(/\.pack-cols > \.panel\{break-inside:avoid/.test(CSS),
    'a panel split across a column boundary is worse than the hole it replaced');
  assert(/@media\(max-width:900px\)\{\.pack-cols\{column-count:1\}\}/.test(CSS),
    'two columns at phone width is unreadable');
});

console.log('\n  ' + passed + ' passed');
