/* Headings are headings, tables are tables, and the glossary has a keyboard.

   Two audit findings that share a cause: everything on screen was a styled
   <span>, so the page had no structure a non-mouse reader could use.

   D3 — each surface had exactly ONE real heading, its <h1>. "SETUP DECK",
   "MARKET WEATHER", "ORDER TICKET" were divs and spans wearing a class. For an
   app this dense, that leaves screen-reader and keyboard navigation with
   nothing to jump between.

   D2 — the glossary is the best thing in this product and it was reachable by
   exactly one input device. Hover, or a click, and a footnote suggesting you
   "tap it on a phone". Someone tabbing through the page could not read a single
   definition.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const GLOSS = S('glossary.js');
const CSS = S('ss.css');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('semantics and keyboard');

ok('panel labels are real headings', () => {
  const h2 = (HTML.match(/<h2\b/g) || []).length;
  assert(h2 >= 15, `only ${h2} real headings — panel labels are still spans`);
  assert(!/<span class="t-section">/.test(HTML),
         'a section label is still a span pretending to be a heading');
});

ok('the heading markup is well formed', () => {
  assert.strictEqual((HTML.match(/<h2\b/g) || []).length,
                     (HTML.match(/<\/h2>/g) || []).length,
                     'unbalanced h2 tags');
  assert.strictEqual((HTML.match(/<span\b/g) || []).length,
                     (HTML.match(/<\/span>/g) || []).length,
                     'unbalanced span tags');
  // the nested-term case: <h2>...<span class="term">X</span></h2>, never crossed
  assert(!/<\/h2><\/span>/.test(HTML),
         'a heading closes inside a span it contains — crossed tags');
});

ok('promoting them did not restyle them', () => {
  const i = CSS.indexOf('.t-section{');
  const rule = CSS.slice(i, CSS.indexOf('}', i));
  assert(/margin:\s*0/.test(rule),
         "an h2's default margin would move all seventeen panel labels");
  assert(/font-size:/.test(rule) && /font-weight:/.test(rule),
         'size and weight are inherited from the h2 default rather than set');
});

ok('every glossary term is a focus stop', () => {
  assert(/tabIndex = 0/.test(GLOSS), 'terms cannot be reached by keyboard');
  assert(/setAttribute\('role', 'button'\)/.test(GLOSS),
         'a term announces no role, so its behaviour is unannounced');
  assert(/aria-label/.test(GLOSS), 'the control has no accessible name');
});

ok('role is button, not definition', () => {
  // `definition` would promise a screen reader the text is already present.
  // It is not — activating fetches and shows it.
  assert(!/'role', 'definition'/.test(GLOSS),
         'announcing a definition role promises text that is not there');
});

ok('focus shows it and blur hides it', () => {
  assert(/addEventListener\('focusin'/.test(GLOSS), 'focus does not open the term');
  assert(/addEventListener\('focusout'/.test(GLOSS), 'blur leaves it open');
});

ok('Enter, Space and Escape all work', () => {
  const i = GLOSS.indexOf("addEventListener('keydown'");
  assert(i > 0, 'no keyboard handler');
  const h = GLOSS.slice(i, i + 420);
  assert(/'Enter'/.test(h) && /' '/.test(h), 'Enter/Space do not activate it');
  assert(/'Escape'/.test(h), 'there is no way to dismiss it from the keyboard');
  assert(/preventDefault/.test(h), 'Space scrolls the page instead of activating');
});

ok('terms added later are made reachable too', () => {
  // the deck diffs, weather re-renders every 30s, edgeview repaints wholesale —
  // a one-time pass would leave every later term unreachable
  assert(/MutationObserver/.test(GLOSS),
         'only the terms present at load are keyboard-reachable');
  const i = GLOSS.indexOf('new MutationObserver');
  const o = GLOSS.slice(i, i + 220);
  assert(/subtree:\s*true/.test(o), 'nested re-renders are not observed');
});

ok('a focus stop shows a focus ring', () => {
  assert(/\.term:focus-visible\{/.test(CSS),
         'terms take focus and show nothing — the reader cannot tell where '
         + 'they are or what Enter would do');
  const i = CSS.indexOf('.term:focus-visible{');
  const rule = CSS.slice(i, CSS.indexOf('}', i));
  assert(/outline:/.test(rule), 'no visible outline on focus');
});

console.log('\n' + passed + ' passed');
