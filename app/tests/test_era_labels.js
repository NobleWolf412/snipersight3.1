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

ok('each era resolves in the glossary', () => {
  for (const key of ['forwardWindow', 'recordedBook', 'baseline']) {
    assert(new RegExp('\\b' + key + '\\s*:').test(GLOSS),
           `no glossary entry for ${key} — the term is shown and never defined`);
  }
  // and both surfaces mark them up, or the definitions are unreachable
  for (const src of [['Results', SHELL], ['edge panel', EDGE]]) {
    for (const key of ['forwardWindow', 'recordedBook']) {
      assert(src[1].includes(`data-t="${key}"`),
             `${src[0]} shows the term without linking it to its definition`);
    }
  }
});

ok('the two eras share one page and each band locates the other', () => {
  /* GEOMETRY CHANGED 2026-07-31 (audit B6): the edge panel moved from
     Diagnostics to Results, under the equity curve. The original assertions
     pinned cross-surface links; the property they protected — a reader of
     either number can find the other — is now positional. The band above the
     tiles must say the whole book is measured BELOW, and the panel's band must
     name the tiles ABOVE. And neither may use an in-page href: a bare
     "#edgeRoot" would be read by the hash router as a surface name and blank
     every surface, which is why this asserts the ABSENCE of the old links. */
  const html = fs.readFileSync(path.join(__dirname, '..', 'static', 'shell.html'), 'utf8');
  const results = html.slice(html.indexOf('id="s-results"'),
                             html.indexOf('</section>', html.indexOf('id="s-results"')));
  assert(/id="edgeRoot"/.test(results),
         'the edge panel left Results — the honesty check is a surface away '
         + 'from the numbers it disciplines again');
  const curve = results.indexOf('id="eqCurve"');
  assert(curve > 0 && curve < results.indexOf('id="edgeRoot"'),
         'the panel is on Results but not under the equity curve');
  assert(/measured\s+just below/.test(SHELL),
         'the Results band no longer says where the whole book lives');
  assert(/tiles\s+above/.test(EDGE),
         'the edge band no longer distinguishes itself from the window above it');
  // an actual anchor tag, not any mention — the comment in shell.js that
  // EXPLAINS this hazard names the literal string, and the first draft of this
  // assertion failed on its own documentation
  assert(!/<a href="#edgeRoot"/.test(SHELL) && !/<a href="#edgeRoot"/.test(EDGE),
         'an in-page surface-hash link — the router reads it as a surface name '
         + 'and blanks the app');
});

ok('an empty forward window explains the non-empty panel below it', () => {
  // the reconciliation matters most in exactly the state that produced the bug
  const i = SHELL.indexOf("resultsEra')");
  const band = SHELL.slice(i, i + 1100);
  assert(/ruled \?/.test(band),
         'the band reads the same whether or not the window has trades');
  assert(/report trades while these tiles report none/.test(band),
         'an empty window never explains why the panel below still shows a count');
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

console.log('\n' + passed + ' passed');
