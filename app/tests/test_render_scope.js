/* A render function may only pass names that exist.

   `renderDeck` called `deckRowInner(s, now)` and never bound `now`. The first
   row threw `ReferenceError: now is not defined` and the forEach died there —
   so the Setup Deck, the top panel of the primary surface, rendered its
   "Looked at, not taken" divider (inserted BEFORE the loop) and then nothing
   underneath, while the tile beside it read "4 examined, not taken".

   It looked like an empty deck rather than a broken one, and the loop only runs
   when there is something to show, so it survived every test on a quiet market.
   It also rejected loadOverview() on every 30s cycle, which lit API DEGRADED in
   the top bar while all five Command endpoints answered 200 — a health chip
   blaming the server for a bug in the page.

   TEXT WOULD NOT HAVE CAUGHT IT, and neither would `node --check`: an
   unbound READ is legal JavaScript that throws only when the line runs. So
   this asserts the SHAPE, in the spirit of test_shell_structure.js — resolve
   every bare name a render function hands to a call, against the names that
   function can actually see.

   Deliberately narrow. It looks only at identifiers passed as arguments,
   because that is the slice this defect lives in and the slice a regex can
   read without a parser. It is not a linter and does not pretend to be. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const SRC = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'shell.js'), 'utf8');

let passed = 0, total = 0;
function ok(name, fn) {
  total++;
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

/* Strings and comments are blanked before any name is read: prose and HTML
   inside a template literal mention plenty of words that are not identifiers,
   and counting those would fail this suite over English. Newlines survive so
   offsets still line up with the file. */
function blank(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length))
    .replace(/`(?:\\[\s\S]|\$\{[^}]*\}|[^`\\])*`/g, m => m.replace(/[^\n]/g, ' '))
    .replace(/'(?:\\.|[^'\\])*'/g, m => m.replace(/[^\n]/g, ' '))
    .replace(/"(?:\\.|[^"\\])*"/g, m => m.replace(/[^\n]/g, ' '));
}

const CODE = blank(SRC);

function bodyOf(name) {
  const i = CODE.indexOf('function ' + name + '(');
  if (i < 0) return null;
  let depth = 0, j = i, started = false;
  while (j < CODE.length) {
    if (CODE[j] === '{') { depth++; started = true; }
    else if (CODE[j] === '}') { depth--; if (started && depth === 0) break; }
    j++;
  }
  return {start: i, end: j, text: CODE.slice(i, j + 1)};
}

/* What the whole module can see — and ONLY that.

   Anchored to the two-space indentation of the IIFE body, because the file's
   entire content lives inside one. Scanning every `const` in the file instead
   was this test's own first bug: `now` is declared inside three OTHER functions
   (renderPositions, renderPending, and one more), so a file-wide sweep reported
   it as bound and the check sailed straight past the very defect it was written
   for. A name declared inside a sibling function is not in scope here, and
   pretending otherwise makes the whole test decorative. */
const MODULE_NAMES = new Set();
for (const re of [/^ {2}(?:const|let|var)\s+([A-Za-z_$][\w$]*)/gm,
                  /^ {2}function\s+([A-Za-z_$][\w$]*)/gm,
                  /^ {2}(?:const|let|var)\s*\{([^}]*)\}/gm,
                  /^ {2}(?:const|let|var)\s[^;\n]*?,\s*([A-Za-z_$][\w$]*)\s*=/gm]) {
  let m;
  while ((m = re.exec(CODE))) {
    m[1].split(',').forEach(part => {
      const n = part.split(':').pop().trim().replace(/\s*=[\s\S]*$/, '');
      if (/^[A-Za-z_$][\w$]*$/.test(n)) MODULE_NAMES.add(n);
    });
  }
}

const GLOBALS = new Set([
  'window', 'document', 'location', 'console', 'Math', 'Date', 'JSON', 'Object',
  'Array', 'Set', 'Map', 'Number', 'String', 'Boolean', 'Promise', 'RegExp',
  'Error', 'parseInt', 'parseFloat', 'isNaN', 'setTimeout', 'setInterval',
  'clearTimeout', 'clearInterval', 'fetch', 'navigator', 'localStorage', 'e',
  'undefined', 'null', 'true', 'false', 'this', 'arguments', 'event',
]);

/* Bare identifiers handed to a call inside this function body. Anything with a
   dot, a bracket, an operator or a literal is skipped — only a lone name can be
   the unbound-read this test is for. */
function argNamesIn(text) {
  const out = new Map();
  const call = /\b([A-Za-z_$][\w$]*)\s*\(([^()]*)\)/g;
  let m;
  while ((m = call.exec(text))) {
    if (/^(if|for|while|switch|catch|return|function|typeof)$/.test(m[1])) continue;
    m[2].split(',').forEach(raw => {
      const a = raw.trim();
      if (/^[A-Za-z_$][\w$]*$/.test(a)) {
        if (!out.has(a)) out.set(a, m[1]);
      }
    });
  }
  return out;
}

function localNamesIn(fnText) {
  const names = new Set();
  const params = /^function\s+[\w$]*\s*\(([^)]*)\)/.exec(fnText);
  if (params) params[1].split(',').forEach(p => {
    const n = p.trim().split('=')[0].trim();
    if (/^[A-Za-z_$][\w$]*$/.test(n)) names.add(n);
  });
  /* Declarations, destructuring, arrow/callback params, catch bindings — and
     the second and later declarators of a list (`const prox = a, max = b`),
     which the first pattern alone misses. Over-collecting is the safe
     direction: a name wrongly counted as bound only makes this test quieter,
     while a name wrongly counted as free accuses working code. */
  for (const re of [/\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g,
                    /,\s*([A-Za-z_$][\w$]*)\s*=[^=]/g,
                    /\b(?:const|let|var)\s*\{([^}]*)\}/g,
                    /\b(?:const|let|var)\s*\[([^\]]*)\]/g,
                    /\(([^()]*)\)\s*=>/g,
                    /(?:^|[\s(,])([A-Za-z_$][\w$]*)\s*=>/g,
                    /\bcatch\s*\(([^)]*)\)/g,
                    /\bfunction\s*\(([^)]*)\)/g]) {
    let m;
    while ((m = re.exec(fnText))) {
      m[1].split(',').forEach(part => {
        const n = part.split(':').pop().trim().replace(/\s*=[\s\S]*$/, '');
        if (/^[A-Za-z_$][\w$]*$/.test(n)) names.add(n);
      });
    }
  }
  return names;
}

const RENDERERS = [...SRC.matchAll(/\bfunction\s+(render[A-Z][\w$]*)\s*\(/g)]
  .map(m => m[1]);

ok('there are render functions to check', () => {
  assert.ok(RENDERERS.length >= 5,
    `only found ${RENDERERS.length} render functions — did the naming change?`);
});

ok('every name a render function passes to a call is bound', () => {
  const problems = [];
  for (const name of RENDERERS) {
    const fn = bodyOf(name);
    if (!fn) continue;
    const local = localNamesIn(fn.text);
    for (const [ident, callee] of argNamesIn(fn.text)) {
      if (local.has(ident) || MODULE_NAMES.has(ident) || GLOBALS.has(ident)) continue;
      problems.push(`${name}() passes '${ident}' to ${callee}() — bound nowhere ` +
                    `it can see, so this throws ReferenceError the first time ` +
                    `that line runs`);
    }
  }
  assert.deepStrictEqual(problems, [], '\n       ' + problems.join('\n       '));
});

ok('the deck dates its rows in SECONDS, from one instant', () => {
  /* Both clocks on a deck row subtract an epoch-seconds field off the fact —
     foundAgo() from market_time, expiresIn() from expires_at_ts. In
     milliseconds every setup reads as found decades ago and long expired. */
  const fn = bodyOf('renderDeck');
  assert.ok(fn, 'renderDeck() not found — renamed?');
  const decl = /\bconst\s+now\s*=\s*Date\.now\(\)\s*\/\s*1000\b/.exec(fn.text);
  assert.ok(decl, "renderDeck must bind `now` as Date.now() / 1000 (seconds)");
  const use = fn.text.indexOf('deckRowInner(s, now)');
  assert.ok(use > -1, 'the deckRowInner call moved — check this test still applies');
  assert.ok(decl.index < use,
    '`now` is bound after the row loop that reads it');
  /* Once, outside the ROW loop — not merely before the first .forEach in the
     function, which is the node cleanup further up. Two rows painted a
     millisecond apart must not print different minute counts from one render. */
  const rowLoop = fn.text.indexOf('ordered.concat(passed).forEach(');
  assert.ok(rowLoop > -1, 'the row loop moved — check this test still applies');
  assert.ok(decl.index < rowLoop,
    '`now` must be read once before the row loop, not per row');
});

console.log(`\n  ${passed}/${total} passed`);
