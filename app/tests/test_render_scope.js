/* The Deck's row loop must be able to see the clock it dates rows from.

   `renderDeck` called `deckRowInner(s, now)` and never bound `now`. The first
   row threw `ReferenceError: now is not defined` and the forEach died there —
   so the Setup Deck, top panel of the surface that asks "What should I do right
   now?", rendered ZERO rows while the tile beside it read "4 examined, not
   taken".

   It read as an empty deck rather than a broken one, which is why it lived for
   as long as it did. The "Looked at, not taken" divider is inserted BEFORE the
   loop, so the heading appeared and nothing followed it; and the loop only runs
   when there is something to show, so every quiet market passed over it. It
   also rejected loadOverview() on every 30s cycle, putting API DEGRADED in the
   top bar while all five Command endpoints answered 200.

   Neither text nor `node --check` could have caught it: an unbound READ is
   legal JavaScript that throws only when the line runs.

   ─────────────────────────────────────────────────────────────────────────
   WHAT WAS TRIED AND DELIBERATELY ABANDONED, so nobody spends the evening on
   it again: a general check that resolved every bare name each render function
   passes to a call against the names that function can see. It cannot be done
   reliably with regexes over this file. Finding where a function ENDS needs a
   parser — shell.js is 3,600 lines of dense template literals, nested `${}`
   and regex literals, and blanking them by pattern desynced the brace counter
   every time. Three separate attempts each ended the same way: the counter ran
   past the end of `renderNear` and the check confidently accused it of 37
   identifiers belonging to nine other functions. A checker that accuses working
   code is worse than none — the next person deletes it, and the real defect it
   was guarding goes with it.

   The right tool for the general case is a linter's `no-undef`, which has a
   real parser. That is worth adding to this repo; it is not worth
   approximating here. What survives is the narrow contract below, which is
   verified in both directions: it fails on the source that shipped the bug and
   passes on the fix.
   ───────────────────────────────────────────────────────────────────────── */
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

/* Bounded by the next module-level declaration of ANY kind — `function`,
   `async function`, or a `const` arrow. Module level is exactly two spaces:
   the whole file is one IIFE. Bounding on `function` alone reaches 2,240 lines
   past renderNear, because almost everything after it is declared the other
   two ways. */
function bodyOf(name) {
  const i = SRC.indexOf('  function ' + name + '(');
  if (i < 0) return null;
  const next = /\n {2}(?:async\s+function|function|const|let|var)\s/g;
  next.lastIndex = i + 1;
  const hit = next.exec(SRC);
  /* Comments blanked to spaces — length preserved, so every index below still
     points at the same character of the real source. This test caught itself
     with this one: the comment explaining the bug quotes `deckRowInner(s, now)`
     verbatim, so indexOf found the PROSE above the declaration and reported a
     correctly-ordered file as binding `now` too late. Code positions have to be
     read from code. */
  return SRC.slice(i, hit ? hit.index : SRC.length)
    .replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length));
}

ok('renderDeck binds the clock its rows are dated from', () => {
  const fn = bodyOf('renderDeck');
  assert.ok(fn, 'renderDeck() not found — renamed?');
  const call = fn.indexOf('deckRowInner(s, now)');
  assert.ok(call > -1,
    'the deckRowInner(s, now) call moved — check this test still describes the code');
  const decl = /\bconst\s+now\s*=/.exec(fn);
  assert.ok(decl,
    'renderDeck passes `now` to deckRowInner and never binds it — this is a ' +
    'ReferenceError on the first row, and the deck renders its heading with ' +
    'nothing under it');
  assert.ok(decl.index < call, '`now` is bound after the row loop that reads it');
});

ok('it is SECONDS, and read once above the loop', () => {
  /* Both clocks on a row subtract an epoch-SECONDS field off the fact:
     foundAgo() from market_time, expiresIn() from expires_at_ts. In
     milliseconds every setup reads as found decades ago and long expired.

     Once, above the loop — two rows painted a millisecond apart must not print
     different minute counts from one render. */
  const fn = bodyOf('renderDeck');
  const decl = /\bconst\s+now\s*=\s*Date\.now\(\)\s*\/\s*1000\b/.exec(fn);
  assert.ok(decl, 'renderDeck must bind `now` as Date.now() / 1000 (seconds)');
  const rowLoop = fn.indexOf('ordered.concat(passed).forEach(');
  assert.ok(rowLoop > -1, 'the row loop moved — check this test still applies');
  assert.ok(decl.index < rowLoop, '`now` must be read once before the row loop');
});

console.log(`\n  ${passed}/${total} passed`);
