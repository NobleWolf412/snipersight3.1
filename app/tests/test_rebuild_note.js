/* The rebuild is visible where the equity is read.

   A setups version bump makes the scanner re-derive the record over hours
   while the account is replayed from a book still filling in, so equity and
   return move with no trade closing. On 2026-09-05 the operator read that as
   a slow loss. These pin that the UI says so — from the server's one reading,
   never re-derived — on Results, in the equity chip's title, and on Command's
   balance line, and that it says nothing when no rebuild is underway. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const STATIC = path.join(__dirname, '..', 'static');
const HTML = fs.readFileSync(path.join(STATIC, 'shell.html'), 'utf8');
const SHELL = fs.readFileSync(path.join(STATIC, 'shell.js'), 'utf8');
const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

let passed = 0;
function ok(name, fn) { fn(); passed++; console.log('  ok   ' + name); }

ok('the note exists on Results, beside the equity tiles, hidden at rest', () => {
  assert(/id="rebuildNote"[^>]*hidden/.test(HTML), 'no hidden #rebuildNote in shell.html');
  const tiles = HTML.indexOf('id="rEquity"');
  const note = HTML.indexOf('id="rebuildNote"');
  assert(tiles > 0 && note > tiles && note - tiles < 2500,
    'the note is not next to the equity tiles it qualifies');
});

ok('the UI reads the server\'s one reading and re-derives nothing', () => {
  assert(/const rb = p\.rebuild \|\| \{\}/.test(SHELL), 'shell.js does not read p.rebuild');
  assert(!/api\/rebuild|engine_runs[^\n]*(SELECT|COUNT)/.test(SHELL),
    'shell.js must not compute rebuild progress itself or fetch it from a second place');
  // account_status, not status: status() only ever asks about SETUPS, so an
  // exec-only bump rebuilds every settlement with the screen saying complete.
  assert(/"rebuild": _rebuild\.account_status\(con\)/.test(SERVER),
    'the portfolio payload does not carry the rebuild reading');
  assert(!/"rebuild": _rebuild\.status\(con\)/.test(SERVER),
    'the payload is back on the setup-only reading');
});

ok('it says provisional in all three places the equity is read', () => {
  assert(/rebuildNote/.test(SHELL) && /note\.hidden = !rebuilding/.test(SHELL),
    'the Results note is not driven by the reading');
  assert(/PROVISIONAL: the book is being rebuilt/.test(SHELL), 'the equity chip title says nothing');
  assert(/provisional, record rebuilding/.test(SHELL), 'the Command balance line says nothing');
});

ok('progress is stated as done of total, in the reading\'s own words', () => {
  assert(/\$\{rb\.done\} of \$\{rb\.total\}/.test(SHELL), 'the count is not shown');
});

ok('the rebuild note says the loss governors are replayed from the same book', () => {
  // A rebuild makes the equity provisional AND the same-side / daily-loss
  // governors blind: risk.py counts today's losses by replaying exec facts,
  // and during a version rebuild that set is incomplete, so a governor can
  // fail to trip with nothing saying so. Loud-fallback rule — the notice that
  // already covers the numbers has to cover the guard too (2026-09-07).
  assert(/same-side governors are replayed/.test(SHELL),
         'the rebuild note does not mention the governors');
  assert(/may not have tripped/.test(SHELL),
         'the note does not say what the operator could actually miss');
});

console.log(`\n  ${passed} passed`);
