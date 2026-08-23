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

/* The first-run card is measured SEPARATELY, not exempted.

   This budget exists to stop the surfaces a RETURNING operator reads from
   silently regrowing into the Learn tab. A card shown once per browser and
   dismissed forever is not that text: it is read once, by someone who has
   never seen the app, and the audit found there was no such thing anywhere —
   79 buttons and not one entry point.

   Exempting it outright would be a loophole big enough to drive the whole
   deleted Learn surface through, so it carries its own ceiling below. The
   ratchet still applies; it just applies to the right number. */
/* Bounded by the two things either side of it, not by exact whitespace: the
   card's own id, and the Scanner panel that always follows it. */
function firstRunSpan(html) {
  const at = html.indexOf('id="firstRun"');
  if (at < 0) return null;
  const open = html.lastIndexOf('<div', at);
  const end = html.indexOf('panel panel-accent', at);
  if (end < 0) return null;
  return [html.lastIndexOf('<div', end), open];   // [endOfCard, startOfCard]
}

function stripFirstRun(html) {
  const span = firstRunSpan(html);
  return span ? html.slice(0, span[1]) + html.slice(span[0]) : html;
}

function surfaceText(id) {
  const at = HTML.indexOf(`id="s-${id}"`);
  assert(at > 0, `surface ${id} missing`);
  const end = HTML.indexOf('</section>', at);
  return stripFirstRun(HTML.slice(at, end))
    .replace(/<!--[\s\S]*?-->/g, ' ')       // comments are for developers
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function firstRunWords() {
  const span = firstRunSpan(HTML);
  if (!span) return 0;
  return HTML.slice(span[1], span[0])
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ').trim()
    .split(' ').filter(Boolean).length;
}
const words = id => surfaceText(id).split(' ').filter(Boolean).length;

/* A TABBED SURFACE IS NOT ONE SCREEN, and counting it as one charges the
   reader for prose no reader can see. Results and System show exactly one
   [data-*-view] panel at a time, so what a reader actually meets is the
   surface chrome plus the heaviest single view — 31 + 75 on Results, 21 + 69
   on System when this was written.

   Summing them instead was wrong in both directions. It failed Results at 165
   the moment the three books moved in from the deleted #s-ledger husk, which
   put no extra word on any screen; and it would have passed a surface that hid
   400 words behind five tabs and 60 in front of them. */
function viewPanels(id, attr) {
  const at = HTML.indexOf(`id="s-${id}"`);
  const slice = stripFirstRun(HTML.slice(at, HTML.indexOf('</section>', at)));
  const count = h => h.replace(/<!--[\s\S]*?-->/g, ' ').replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ').trim().split(' ').filter(Boolean).length;
  const open = new RegExp(`<(\\w+)[^>]*\\b${attr}="([\\w-]+)"`, 'g');
  const seen = {};
  let m;
  while ((m = open.exec(slice))) {
    const tag = m[1];
    const scan = new RegExp(`<${tag}\\b|</${tag}>`, 'g');
    scan.lastIndex = m.index;
    let depth = 0, hit, end = slice.length;
    while ((hit = scan.exec(slice))) {
      depth += hit[0][1] === '/' ? -1 : 1;
      if (depth === 0) { end = scan.lastIndex; break; }
    }
    seen[m[2]] = (seen[m[2]] || 0) + count(slice.slice(m.index, end));
  }
  return seen;
}

/* The worst single screen the surface can put in front of a reader. A surface
   with no view panels is already one screen, so its own total is the answer. */
function screenWords(id) {
  const attr = {results: 'data-performance-view', settings: 'data-system-view'}[id];
  if (!attr) return words(id);
  const views = viewPanels(id, attr);
  const inViews = Object.values(views).reduce((a, b) => a + b, 0);
  const heaviest = Math.max(0, ...Object.values(views));
  return (words(id) - inViews) + heaviest;
}

ok('the deleted prose layer stays deleted', () => {
  assert(!/panel-sub/.test(HTML), 'a panel-sub paragraph came back');
  assert(!/deck-note/.test(HTML), 'the deck essay came back');
  assert(!/id="s-learn"/.test(HTML), 'the Learn surface came back');
  assert(!/lessons\.js/.test(HTML), 'lessons.js is referenced again');
});

/* Operator ruling, 17 Aug 2026: "my app is full of jargon. all screens. stuff
   I've never even read." Every screen carried its name twice — once in plain
   English and once as a callsign, in the nav sublabel and again in the surface
   heading. Both said the same thing and neither was the answer to anything.

   These two are the same ratchet as the block above, one layer up: that one
   stops paragraphs regrowing, these stop the SECOND NAME regrowing. A word the
   operator has to translate is worse than a word that is merely long. */
ok('a surface heading is the question, not a callsign', () => {
  for (const codename of ['Command Center', 'Setup Radar', 'Execution Bay',
                          'Debrief', 'Control Room']) {
    assert(!HTML.includes(codename),
      `"${codename}" is back — a surface heading is the question it answers, ` +
      `not a second name for the screen`);
  }
});

ok('each destination is named once', () => {
  /* The rail is five links plus Spotter. A <small> inside any of them is the
     sublabel habit returning: the visible word is already the whole label. */
  assert(!/<a href="#(?:overview|opportunities|trade|performance|system)"[^>]*>[\s\S]{0,240}?<small>/
    .test(HTML), 'a nav sublabel came back — one word per destination');
  assert(!/<button[^>]+id="btnSpotter"[\s\S]{0,240}?<small>/.test(HTML),
    'the Spotter sublabel came back');
  /* The address is the contract, not the label: these five hashes are in
     bookmarks and in the router's alias table, and renaming a screen must
     never move them. */
  for (const hash of ['#overview', '#opportunities', '#trade', '#performance',
                      '#system']) {
    assert(HTML.includes(`href="${hash}"`),
      `${hash} no longer exists — a label rename moved an address`);
  }
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
   ~20% headroom. JS-injected text is budgeted by the builder checks below,
   not here. Settings joined at its rebuilt weight (UI 4/7): 1,350 words of
   Rules became ~300 rendered. */
/* THIS MAP FAILS OPEN TOO: an unbudgeted surface can carry any amount of
   prose. Ledger left it when #s-ledger stopped being a surface: the three
   books are the Journal view of Results now, and they are charged to Results
   at the weight a reader who opens that tab actually meets. */
const CEILINGS = { command: 120, chart: 200, results: 130, diagnostics: 220,
                   settings: 260 };

for (const [id, cap] of Object.entries(CEILINGS)) {
  ok(`${id} stays under ${cap} static words on one screen`, () => {
    const n = screenWords(id);
    assert(n <= cap, `${id} shows ${n} words on its heaviest single screen ` +
      `against a ${cap} ceiling — move the explanation into a hover term or ` +
      `delete it`);
  });
}

ok('the first-run card is an invitation, not a chapter', () => {
  const n = firstRunWords();
  assert(n > 0, 'the entry point for a first-time reader is gone — the audit ' +
    'counted 79 buttons and not one of them was a place to start');
  assert(n <= 130, `the intro card carries ${n} words against a 130 ceiling. ` +
    `It is read once by someone who has never seen a trading app; four ` +
    `sentences and three steps is the whole budget. This is where the Learn ` +
    `tab would grow back.`);
});

ok('the era band is a line, not an essay', () => {
  const SHELL = S('shell.js');
  const i = SHELL.indexOf("$('resultsEra').innerHTML");
  const block = SHELL.slice(i, SHELL.indexOf(';', i));
  const w = block.replace(/<[^>]+>/g, ' ').replace(/[^a-zA-Z ]/g, ' ')
    .split(/\s+/).filter(x => x.length > 2).length;
  assert(w <= 20, `the era band builder carries ~${w} words — it was two paragraphs once`);
});

console.log('\n  ' + passed + ' passed');
