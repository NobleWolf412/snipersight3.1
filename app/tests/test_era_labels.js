/* Results and Diagnostics may disagree about how many trades exist. They must
   never disagree SILENTLY.

   Results is scoped to the active baseline. The edge panel measures the whole
   recorded book. Live, that reads as "no closed trades" on one surface and
   "401 closed trades" on the other — both correct, and together they look like
   a broken app. The two surfaces whose stated jobs are "Is this actually
   working?" and "Is the machine telling me the truth?" are the worst possible
   place to appear to be lying.

   The fix was never a data change. It is that every trade count names its ERA,
   both surfaces name it in the SAME words, and each points at the other. These
   tests pin that: one shared vocabulary, defined once, cross-linked both ways.

   The failure mode they exist to catch is drift — one surface renamed, or one
   band deleted, restoring the contradiction without anything else breaking. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const APP = path.resolve(__dirname, '..');
const read = f => fs.readFileSync(path.join(APP, 'static', f), 'utf8');
const SHELL = read('shell.js');
const HTML = read('shell.html');
const EDGE = read('edgeview.js');
const GLOSS = read('glossary.js');
const CSS = read('ss.css');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('era labels');

/* The two nouns. If either surface renames one without the other, the whole
   point is lost — the reader can no longer tell the labels describe one system. */
const ERAS = ['forward window', 'recorded book'];

ok('both surfaces carry an era band', () => {
  assert(/id="resultsEra"/.test(HTML), 'Results has no era band element');
  assert(/resultsEra'\)\.innerHTML/.test(SHELL), 'nothing ever fills the Results era band');
  assert(/class="era-band"/.test(EDGE), 'the edge panel renders no era band');
});

ok('the simulator tile does not call its count trades', () => {
  /* THE BAND WAS NOT ENOUGH, and that is the lesson this pins.

     This panel already carried a correct era band saying the figures were
     simulator closes across every baseline. The tile beside it was still
     labelled "Closed trades", and on 2026-08-11 the operator read the number
     in it — in the hundreds — and concluded that many trades had been placed
     on their account. Their funded record at that moment was ONE trade. The
     misreading survived being checked by an assistant, which quoted the same
     figure back as if it were the operator's record.

     A label is read; the caption under it is not, and a band above it is not.
     So the noun in the LABEL is the load-bearing part: it may not be a word
     that can be mistaken for money the operator committed. The era band stays
     — it is still true and still useful — but it is no longer the only thing
     standing between a research number and a wrong conclusion. */
  const i = EDGE.indexOf('class="ev-grid"');
  assert(i > 0, 'the edge tile grid was renamed — this test reads nothing');
  /* Wide enough to clear the comment that explains the rename and still reach
     the tile. The "trades" check is safe over this span: the expectancy tile
     reads `t-label"><span class="term"...>Average result per trade`, and the
     pattern requires the word with no tag between it and the label, so that
     legitimate use of the word cannot trip it. */
  const firstTile = EDGE.slice(i, i + 1600);
  assert(!/t-label">[^<]*\btrades?\b/i.test(firstTile),
    'the simulator-count tile calls its number "trades" again. It counts ' +
    'replays of setups against history — no order, no money, no decision — ' +
    'and the operator has already once read it as their own record');
  assert(/not trades you placed/i.test(firstTile),
    'the tile no longer says what its number is NOT, which is the only part ' +
    'that survived being misread last time');
});

ok('the band is a headline, not a footnote', () => {
  // it must precede the tiles it qualifies — a caveat under the number is not one
  const band = HTML.indexOf('id="resultsEra"');
  const tiles = HTML.indexOf('id="rReturn"');
  assert(band > 0 && tiles > 0, 'markup not found');
  assert(band < tiles, 'the Results era band renders below the metric it qualifies');
  // match the MARKUP, not the stylesheet block at the top of edgeview.js
  const eband = EDGE.indexOf('${eraBand}');
  const egrid = EDGE.indexOf('<div class="ev-grid">');
  assert(eband > 0, 'the edge era band is built but never placed in the panel');
  assert(egrid > 0, 'the edge tile grid markup was renamed');
  assert(eband < egrid, 'the edge era band renders below the closed-trade count');
});

ok('both surfaces use the SAME two nouns', () => {
  for (const era of ERAS) {
    assert(SHELL.includes(era), `Results never says "${era}"`);
    assert(EDGE.includes(era), `the edge panel never says "${era}"`);
  }
});

ok('the window term resolves in the glossary', () => {
  // Post-purge the band is one line and carries ONE term. recordedBook still
  // resolves for the Diagnostics-side band; Results carries forwardWindow.
  assert(/data-t="forwardWindow"/.test(SHELL),
         'the band must still anchor its one term to a definition');
});

ok('the band still says where the full book lives', () => {
  const i = SHELL.indexOf("$('resultsEra').innerHTML");
  const block = SHELL.slice(i, i + 500);
  assert(/#diagnostics/.test(block),
         'the Results band no longer says where the whole book lives');
});

ok('an empty forward window still says so', () => {
  assert(/window empty/.test(SHELL),
         'the empty branch must name the emptiness, however briefly');
});

ok('the band is readable prose, not a label', () => {
  const i = CSS.indexOf('.era-band{');
  assert(i >= 0, '.era-band has no styling');
  const rule = CSS.slice(i, CSS.indexOf('}', i));
  assert(/--f-body/.test(rule), 'the era band is not set in the body face');
  assert(!/--f-mono/.test(rule), 'multi-sentence prose set in the mono label face');
  assert(!/text-transform:\s*uppercase/.test(rule),
         'all-caps destroys word shape at sentence length');
  assert(!/var\(--fg-[34]\)/.test(rule),
         'the reconciliation is set in the dimmest greys the palette has');
});

/* A duplicate key is invisible: JS keeps the last one and the earlier
   definition simply stops existing. It happened on 4 Aug 2026 — an audit
   scanned the data-t attributes present in the DOM rather than GLOSSARY
   itself, reported `liquidity` as undefined, and the "fix" overwrote a
   longer entry that carried the part an operator most needs. Nothing failed,
   nothing warned, and the term still explained itself on hover — with less
   in it than before. */
ok('no term is defined twice', () => {
  const body = GLOSS.slice(GLOSS.indexOf('window.GLOSSARY'));
  const keys = [...body.matchAll(/^\s{2}([a-zA-Z][a-zA-Z0-9]*):\s*"/gm)]
    .map(m => m[1]);
  assert(keys.length > 30, 'the key scan found almost nothing — check the shape');
  const dupes = keys.filter((k, i) => keys.indexOf(k) !== i);
  assert(dupes.length === 0,
    `defined more than once: ${[...new Set(dupes)].join(', ')} — the later ` +
    `definition silently replaces the earlier one`);
});

/* ── LEDGER ──
   The surface that puts the two eras next to each other on purpose. The engine
   book is scoped to the active baseline; the operator's own book is all of
   history by design (manual.py's `book()` reads every manual version). Those
   are different windows over different capital, so the nouns are not decoration
   here — they are the whole reason the columns may not be added. */
ok('the Ledger names an era on every book', () => {
  assert(/id="s-ledger"/.test(HTML), 'no Ledger surface');
  const i = SHELL.indexOf('function renderLedger(');
  assert(i > 0, 'renderLedger was renamed — this test no longer reads it');
  const block = SHELL.slice(i, SHELL.indexOf('function renderLedgerMine', i));
  assert(block.length > 400, 'the renderLedger slice is empty — re-anchor it');
  /* Every bookCard() call must carry one, including the "could not read" and
     "not read yet" branches — a book whose window is unstated is a number the
     reader has to guess the scope of, and those branches are exactly when a
     reader is most likely to misread one. */
  const calls = (block.match(/bookCard\(\{/g) || []).length;
  const eras = [...block.matchAll(/era:\s*'([^']+)'/g)].map(m => m[1]);
  assert(calls >= 3, `only ${calls} book cards are built; the surface has three`);
  assert.strictEqual(eras.length, calls,
    `${calls} book cards are built and ${eras.length} carry an era label. An ` +
    `unlabelled book is a number whose window the reader has to guess.`);
  for (const e of eras) {
    assert(ERAS.includes(e),
      `the Ledger says "${e}" — the app has exactly two era nouns, ` +
      `"${ERAS.join('" and "')}", and a third invents a window`);
  }
  assert(eras.includes('recorded book') && eras.includes('forward window'),
    'both eras must appear — the point of the surface is that they differ');
});

ok('no figure on the Ledger adds two books', () => {
  /* The one rule the whole surface exists to enforce. `manual.arm` never
     consults the risk authority, so hand-armed size was never drawn from the
     engine's $10,000; a combined total would be an invented number wearing a
     measured one's authority. */
  const i = SHELL.indexOf('function renderLedger(');
  const block = SHELL.slice(i, SHELL.indexOf('const LOADER_SURFACE', i));
  assert(block.length > 400, 'the renderLedger slice is empty — re-anchor it');
  assert(!/total_pnl_usd\s*[+]|[+]\s*(?:b\.)?total_pnl_usd/.test(block),
    'the manual book total is being added to something');
  assert(!/operator_closed_usd\s*[+]|[+]\s*(?:p\.)?operator_closed_usd/.test(block),
    'the operator-exit total is being added to something');
  assert(/never added|not added/i.test(block) || /never added/i.test(HTML),
    'nothing on screen says the books are not summed');
});

console.log('\n' + passed + ' passed');
