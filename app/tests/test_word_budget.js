/* The word budget — the prose cannot grow back.

   Operator ruling, 3 Aug 2026: "clean and concise. less explaining and words.
   it's a trading app. no one wants to read." The purge that followed deleted
   the Learn surface (71% of all words), thirteen panel-sub paragraphs, the
   deck note, and the era essays. This test is the ratchet: every ceiling here
   is the measured post-purge weight with a little headroom, so a future
   session adding a helpful paragraph fails a test instead of starting the
   slide over.

   Explanation still exists — in the hover-tooltip terms, which cost zero
   screen words until asked. That is the budget's escape valve, on purpose. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('word budget');

function surfaceText(id) {
  const at = HTML.indexOf(`id="s-${id}"`);
  assert(at > 0, `surface ${id} missing`);
  const end = HTML.indexOf('</section>', at);
  return HTML.slice(at, end)
    .replace(/<!--[\s\S]*?-->/g, ' ')       // comments are for developers
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ').trim();
}
const words = id => surfaceText(id).split(' ').filter(Boolean).length;

ok('the deleted prose layer stays deleted', () => {
  assert(!/panel-sub/.test(HTML), 'a panel-sub paragraph came back');
  assert(!/deck-note/.test(HTML), 'the deck essay came back');
  assert(!/id="s-learn"/.test(HTML), 'the Learn surface came back');
  assert(!/lessons\.js/.test(HTML), 'lessons.js is referenced again');
});

ok('panel titles stay under four words', () => {
  const heads = [...HTML.matchAll(/<h2 class="t-section">([\s\S]*?)<\/h2>/g)]
    .map(m => m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
  assert(heads.length >= 10, 'the heading scan found nothing');
  for (const h of heads) {
    assert(h.split(' ').length <= 4, `"${h}" exceeds the four-word title budget`);
  }
});

/* Static-markup ceilings per surface: the measured post-purge weight plus
   ~20% headroom. Rules is exempt until its Settings rebuild lands (UI 4/7),
   then it gets a ceiling of its own. JS-injected text is budgeted by the
   builder checks below, not here. */
const CEILINGS = { command: 120, chart: 200, results: 130, diagnostics: 220 };

for (const [id, cap] of Object.entries(CEILINGS)) {
  ok(`${id} stays under ${cap} static words`, () => {
    const n = words(id);
    assert(n <= cap, `${id} carries ${n} words against a ${cap} ceiling — ` +
      `move the explanation into a hover term or delete it`);
  });
}

ok('the era band is a line, not an essay', () => {
  const SHELL = S('shell.js');
  const i = SHELL.indexOf("$('resultsEra').innerHTML");
  const block = SHELL.slice(i, SHELL.indexOf(';', i));
  const w = block.replace(/<[^>]+>/g, ' ').replace(/[^a-zA-Z ]/g, ' ')
    .split(/\s+/).filter(x => x.length > 2).length;
  assert(w <= 20, `the era band builder carries ~${w} words — it was two paragraphs once`);
});

console.log('\n  ' + passed + ' passed');
