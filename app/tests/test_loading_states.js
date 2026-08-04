/* A loading state holds the space its content will take, and the second
   application is reachable.

   A10 — every pending panel said "loading…" in one line of text, then resolved
   into rows, tables and bands several hundred pixels tall. Every fetch was a
   layout jump, and anything the operator was about to click moved.

   E — static/diagnostics.html was a complete second application with a
   searchable decision-provenance view this surface lacked, reachable only by
   typing the path. It shipped with an ?embed=1 mode that hides its own chrome:
   someone designed it to be embedded and stopped one step short of wiring it.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const CSS = S('ss.css');
const JS = S('shell.js');
const FUNNEL = S('funnel.js');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('loading states and provenance');

ok('no text loading placeholder remains', () => {
  assert(!/loading…/.test(HTML),
         'a one-line "loading…" still resolves into content of a different size');
  assert(!/reading the funnel…/.test(FUNNEL),
         'the funnel still grows on arrival');
});

ok('every skeleton names itself to assistive tech', () => {
  const skeletons = (HTML.match(/class="skeleton"/g) || []).length;
  const labelled = (HTML.match(/class="skeleton" role="status" aria-label="loading"/g) || []).length;
  assert(skeletons >= 8, `only ${skeletons} skeletons — sites were missed`);
  assert.strictEqual(labelled, skeletons,
    'a silent skeleton reads as finished-and-empty to a screen reader');
});

ok('skeleton blocks reserve real heights', () => {
  // the entire point is dimension: a skeleton with no height is the old
  // text placeholder wearing a different class
  for (const id of ['deck', 'dIssues', 'dTelemetry', 'perfSymbol', 'perfStrategy']) {
    const i = HTML.indexOf(`id="${id}"`);
    assert(i > 0, `${id} missing`);
    const block = HTML.slice(i, i + 600);
    assert(/height:\d+px/.test(block),
           `${id}'s skeleton reserves no height — arrival still reflows`);
  }
});

ok('the shimmer exists and is motion-guarded', () => {
  assert(/\.skel::after\{/.test(CSS), 'no shimmer');
  assert(/@keyframes skelSweep/.test(CSS), 'no sweep animation');
  // guarded by the GLOBAL reduced-motion rule. The file also carries older
  // local guards, so check every occurrence rather than the first — indexOf
  // found a local one and this assertion cried wolf on a rule that exists.
  const guards = [...CSS.matchAll(/prefers-reduced-motion/g)].map(m =>
    CSS.slice(m.index, m.index + 400));
  assert(guards.length > 0, 'reduced motion is not honoured at all');
  assert(guards.some(g => /animation-duration:\s*\.01ms/.test(g)),
         'no global rule flattens animations, so the shimmer runs for people '
         + 'who asked their machine to stop moving things');
});

ok('the provenance app is embedded on Diagnostics', () => {
  assert(/id="provenance"/.test(HTML), 'no provenance disclosure');
  assert(/id="provFrame"/.test(HTML), 'no iframe');
  assert(/diagnostics\.html\?embed=1/.test(HTML),
         'the embed mode its author built is still unused');
});

ok('the iframe is lazy', () => {
  const i = HTML.indexOf('id="provFrame"');
  const tag = HTML.slice(HTML.lastIndexOf('<iframe', i), HTML.indexOf('>', i) + 1);
  assert(/data-src=/.test(tag), 'no deferred URL');
  assert(!/\ssrc=/.test(tag),
         'the second application loads for every Diagnostics visit whether or '
         + 'not anyone opens it');
  // and something actually promotes data-src to src on open
  assert(/provFrame/.test(JS) && /f\.src = f\.dataset\.src/.test(JS),
         'nothing ever loads the frame, so the panel opens onto a blank void');
});

ok('the standalone page is linked, not orphaned', () => {
  assert(/href="\/static\/diagnostics\.html"/.test(HTML),
         'the full page is once again reachable only by typing the path');
});

ok('the deck differ clears placeholders before appending rows', () => {
  /* Found live, not by reading: the keyed differ APPENDS row nodes, so
     anything already in the container survives every render. A real PF_ZECUSD
     setup rendered UNDERNEATH the loading skeleton — and the same hole existed
     for the old "loading…" div and for the empty state when a quiet market
     wakes up. It went unseen because the deck was empty in every prior test. */
  // delimited on the next top-level declaration, not a guessed length — a
  // fixed window already silently missed one assertion tonight
  const i = JS.indexOf('function renderDeck');
  const end = JS.indexOf('const deckRows = new Map', i);
  const body = JS.slice(i, end > i ? end : i + 8000);
  assert(/:scope > \.skeleton, :scope > \.empty/.test(body),
         'placeholders survive the differ and sit above the first real rows');
  // and the removal must come BEFORE the append loop
  assert(body.indexOf(':scope > .skeleton') < body.indexOf('appendChild'),
         'the placeholder is removed after rows are appended, not before');
});

ok('genuine empty states are still text', () => {
  // A10 is about LOADING states. "no setups right now" is an answer, not a
  // wait — turning answers into grey boxes would be its own regression.
  assert(/no setups right now/.test(JS), 'the deck empty state was lost');
  assert(/no open issues/.test(JS), 'the issues empty state was lost');
});

console.log('\n' + passed + ' passed');
