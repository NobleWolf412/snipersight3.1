/* A count of ZERO OBSERVATIONS must never share a treatment with a count of
   zero problems.

   Green and "clean" are reserved for CHECKED, NOTHING FOUND. Grey plus a
   stated denominator is for NOTHING CHECKED. Four sites in shell.js collapsed
   the two, and every one of them failed in the flattering direction:

     · Results tiles — `up = p.return_pct >= 0` put 0.0 on the POSITIVE branch,
       so an empty forward window rendered `+0%` in green with `class="tile up"`
       while the file's own header promised it "never renders a
       confident-looking zero".
     · Telemetry chip — `defects ? ... : 'clean'` in green made an empty record
       set look identical to a clean one, while the panel body directly beneath
       said "no candidates recorded in this window yet".
     · Pipeline orb — `evaluation_allowed && !blockers` is TRUE while the audit
       is PENDING, so an audit that had not run was painted as one that passed,
       on the always-visible element that governs trust in every other number.
     · Deck empty state — the informative branch was gated on `total > 0`, so
       on a fresh baseline it was unreachable and the operator got four bare
       words at exactly the moment "quiet" is most likely to read as "broken".

   These tests read the SOURCE rather than a rendered DOM, because the property
   is about which branch exists at all. A renderer test can only prove the
   branch it happens to exercise.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const APP = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(APP, 'static', 'shell.js'), 'utf8');
const CSS = fs.readFileSync(path.join(APP, 'static', 'ss.css'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

/* Extract one function body so an assertion cannot be satisfied by an
   unrelated line elsewhere in a 900-line file. */
function body(name) {
  const i = SRC.indexOf('function ' + name + '(');
  assert(i >= 0, name + '() not found — renamed?');
  let depth = 0, j = i, started = false;
  while (j < SRC.length) {
    if (SRC[j] === '{') { depth++; started = true; }
    else if (SRC[j] === '}') { depth--; if (started && depth === 0) break; }
    j++;
  }
  return SRC.slice(i, j);
}

console.log('empty-state honesty');

ok('Results: an unruled window does not take the positive branch', () => {
  const b = body('loadPortfolio');
  assert(/ruled/.test(b), 'no guard on whether the risk authority ruled at all');
  assert(b.includes("$('rReturn').textContent = '—'"),
         'return still renders a number on an empty window');
  assert(b.includes("'tile'"),
         "the 'up' class is still applied unconditionally");
  assert(/no closed trades/.test(b),
         'the tiles carry no denominator saying why they are blank');
});

ok('Results: the empty window says so in words, not just dashes', () => {
  const b = body('loadPortfolio');
  // "This forward window is empty" became "window empty" in the word-budget
  // purge. Shorter, same honesty: emptiness is named, never implied by dashes.
  assert(/window empty/.test(b), 'no explanatory band');
});

ok('Telemetry: zero records is grey "no data", not green "clean"', () => {
  const b = body('loadTelemetry') || SRC;
  const seg = SRC.slice(SRC.indexOf('telChip') - 900, SRC.indexOf('telChip') + 900);
  assert(seg.includes("'no data'"), 'empty record set still reads as a verdict');
  assert(/clean · /.test(seg), 'a clean verdict carries no denominator');
  // the grey branch must NOT be chip-green
  const greyIdx = seg.indexOf("'no data'");
  const after = seg.slice(greyIdx, greyIdx + 200);
  assert(!/chip-green/.test(after), 'the no-data branch is painted green');
});

/* The colour behind the health word is no longer a literal at each call site —
   it comes from one ladder, healthTone(), so the header orb and the diagnostics
   verdict cannot disagree. Assert the ladder by RUNNING it: a source match
   would pass on a function that returns the right string for the wrong reason. */
function healthToneFn() {
  const b = body('healthTone') + '}';        // body() stops ON the closing brace
  const tones = SRC.slice(SRC.indexOf('const TONE_OF_STATUS'),
                          SRC.indexOf('const TONE_VAR'));
  return new Function(tones + '\n' + b + '\nreturn healthTone;')();
}

ok('Pipeline: a PENDING audit is not painted as a pass', () => {
  const b = body('loadHealth');
  assert(/h\.pending/.test(b), 'the endpoint ships `pending` and the UI ignores it');
  const p = b.indexOf('h.pending');
  const branch = b.slice(p, p + 700);
  assert(/healthTone\(h\)/.test(branch),
         'pending branch picks its own colour instead of using the shared ladder');
  assert(/AUDITING/.test(branch), 'pending state is not named on screen');
  assert(/Nothing below has been checked/.test(branch),
         'does not say the verdict is absent rather than clean');
  assert(branch.indexOf('return') > 0,
         'pending branch falls through into the pass/fail rendering');

  const tone = healthToneFn();
  assert.strictEqual(tone({pending: true, evaluation_allowed: true, status: 'PASS'}),
                     'warn', 'an audit that has not run is painted as a pass');
});

ok('Pipeline: DEGRADED never renders green', () => {
  const tone = healthToneFn();
  // the exact live state that rendered green: mildest non-clean rung, nothing
  // blocked, evaluation still allowed. The old good-predicate was true here, so
  // the verdict went green while the word beside it said DEGRADED.
  assert.strictEqual(
    tone({status: 'DEGRADED', evaluation_allowed: true, blockers: [], warnings: [1, 2]}),
    'warn', 'DEGRADED with zero blockers is painted as a pass');
  assert.strictEqual(
    tone({status: 'BLOCKED', evaluation_allowed: false, blockers: [1]}), 'bad');
  assert.strictEqual(
    tone({status: 'PASS', evaluation_allowed: true, blockers: []}), 'good');
  // a status this file has never seen must not default to reassurance
  assert.notStrictEqual(
    tone({status: 'SOMETHING_NEW', evaluation_allowed: true, blockers: []}), 'good',
    'an unrecognised status falls through to green');
});

ok('Pipeline: header and verdict cannot disagree about colour', () => {
  const b = body('loadHealth');
  // both consumers must read the same computed tone, not re-derive one
  assert(/const tone = healthTone\(h\)/.test(b), 'no single tone is computed');
  assert(/healthOrb'\)\.className = 'orb ' \+ tone/.test(b),
         'the orb re-derives its own colour');
  assert(/dVerdict'\)\.style\.color = TONE_VAR\[tone\]/.test(b),
         'the verdict re-derives its own colour');
  // the file's comments still narrate the old predicate, deliberately — it is
  // the bug history. What must not come back is the binding that APPLIED it.
  assert(!/const\s+good\s*=/.test(b),
         'the old good-predicate is still deciding a colour');
});

ok('Pipeline: severity rungs are translated, not dropped', () => {
  const b = body('loadHealth');
  assert(/worst_rung/.test(b), 'worst_rung is served and still ignored');
  for (const rung of ['SERVE_FLAG', 'QUARANTINE', 'AUTO_DISABLE', 'HALT']) {
    assert(b.includes(rung), 'no plain-English translation for ' + rung);
  }
  assert(/flagged/.test(b) && /held back/.test(b) && /switched off/.test(b),
         'rung names are shown raw rather than translated');
});

ok('Deck: a fresh window is distinguished from a quiet market', () => {
  const b = body('renderDeck');
  assert(/cycles/.test(b), 'no check for whether anything was scanned at all');
  assert(/nothing has been examined in this window yet/i.test(b),
         'the unexamined-window message is missing');
  assert(/None are in a state any/.test(b),
         'the scanned-but-quiet message is missing');
  // and the two must be different branches, not one string
  assert(b.indexOf('nothing has been examined') !== b.indexOf('None are in a state'),
         'the two opposite states share one message');
});

ok('the sub-line style hides itself when empty', () => {
  assert(/\.t-sub/.test(CSS), 'no .t-sub style');
  assert(/\.t-sub:empty\{display:none\}/.test(CSS.replace(/\s/g, '')),
         'an empty sub-line would leave a gap under every tile');
});

console.log('\n' + passed + ' passed');
