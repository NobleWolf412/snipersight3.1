/* Your book, on a surface.

   The bug: `Arm` writes to the operator's manual store, and Command, the risk
   budget, the journal and every figure on Results read the ENGINE's store. That
   separation is deliberate and must stay — a hand-picked trade counted as
   engine edge would corrupt the record that decides whether live execution is
   ever unlocked. What was wrong is that one of the two books had no surface at
   all: three orders sat armed on three markets, and the only place any of them
   could be seen was the Chart tab, for the one symbol AND timeframe currently
   loaded. An order that expired while you were looking at another chart expired
   silently.

   These tests hold the shape of the fix: a separate panel that is never merged
   with the engine's, an honest disclosure on the budget meters that do not
   count this risk, and a cancel path that confirms, records, and never quietly
   deletes.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const HTML = S('static/shell.html');
const SHELL = S('static/shell.js');
const CSS = S('static/ss.css');
const CHART = S('static/chart.js');
const SERVER = S('server.py');
const ENGINE = S('engine/manual.py');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('your trades');

/* ───────────────────────── the panel exists ───────────────────────── */

ok('Command has a panel for the operator\'s own orders', () => {
  assert(/id="minePanel"/.test(HTML), 'no panel for your own book');
  assert(/<div id="mine">/.test(HTML), 'nowhere to render the rows');
  assert(/renderMine\(\)/.test(SHELL), 'nothing renders it');
  assert(/renderMine\(\)\.then\(\(\) => renderMineAside\(\)\)/.test(SHELL),
    'the panel must refresh on the same cycle as the rest of Command');
});

ok('it reads the whole-book endpoint, not one chart', () => {
  assert(/api\('\/api\/manual\/live'\)/.test(SHELL),
    'reading /api/manual/open would show one symbol+timeframe — the original bug');
  assert(/@app\.get\("\/api\/manual\/live"\)/.test(SERVER), 'the endpoint is missing');
  assert(/def live\(con\)/.test(ENGINE), 'nothing sweeps every market');
  assert(/for \(symbol, tf\) in sorted\(unresolved\(con\)\)/.test(ENGINE),
    'live() must iterate the whole work list');
});

ok('it resolves before it reports', () => {
  assert(/run\(con, symbol, tf, tf_seconds\)/.test(ENGINE),
    'the stored state is ARMED forever — an expired order would read as waiting');
});

ok('one unreadable market cannot blank the panel', () => {
  const fn = ENGINE.slice(ENGINE.indexOf('def live(con)'), ENGINE.indexOf('def status('));
  assert(/except Exception:/.test(fn) && /continue/.test(fn),
    'the rows that CAN be resolved are still worth showing');
});

/* ─────────────────── the two books stay separate ─────────────────── */

ok('your book is never merged into the engine\'s', () => {
  assert(!/active_positions.*\.concat\(.*manual/i.test(SHELL),
    'a hand-picked trade must never join the engine position list');
  assert(/hand-picked · not engine record/.test(HTML),
    'the panel must say whose plan these are');
  assert(HTML.indexOf('id="minePanel"') < HTML.indexOf('id="posPanel"'),
    'your orders belong above the engine positions, not mixed into them');
});

ok('the row is visually attributed, not just captioned', () => {
  assert(/\.pos-row\.mine\{border-left:2px solid var\(--accent\)\}/.test(CSS),
    'two books rendered identically is how a number ends up read against the wrong one');
});

ok('the panel says a resting order is not a position', () => {
  const sub = HTML.slice(HTML.indexOf('id="minePanel"'), HTML.indexOf('<div id="mine">'));
  assert(/resting order is not a\s+position/.test(sub),
    'the reported symptom was calling a pending order an open trade');
  assert(/expires/.test(sub), 'an order with a window that closes must say so');
  assert(/does not? count|not count/.test(sub) || /None of this counts/.test(sub),
    'it must say this is outside the strategy record');
});

/* ────────────────────── states are distinguished ────────────────────── */

ok('waiting and filled are drawn differently', () => {
  assert(/t\.state === 'PENDING'/.test(SHELL), 'one rendering for both states');
  assert(/Waiting for price to reach/.test(SHELL), 'no plain words for a resting order');
  assert(/Nothing is at stake until it fills/.test(SHELL),
    'a pending order must not read as money already committed');
});

ok('an order about to expire says so louder', () => {
  assert(/soon \? 'chip-red' : 'chip-amber'/.test(SHELL), 'no escalation near expiry');
  assert(/bars <= 1/.test(SHELL), 'nothing detects the last bar of the window');
});

ok('the window is stated in time, not only in bars', () => {
  assert(/function windowLeft/.test(SHELL), '"4 bars" means an hour on 15m and a day on 4H');
  assert(/tf_seconds/.test(SHELL) && /"tf_seconds": tf_seconds/.test(ENGINE),
    'the timeframe length must reach the browser');
});

ok('unrealized R comes from the server, not a second calculation', () => {
  assert(/t\.unrealized_r == null \? null : \+t\.unrealized_r/.test(SHELL),
    'recomputing R in the browser is a second authority that drifts from the one that pays out');
});

/* ──────────────────── the budget tells the truth ──────────────────── */

ok('the risk meters disclose what they do not count', () => {
  assert(/id="budgetAside"/.test(HTML), 'no disclosure element');
  assert(/function renderMineAside/.test(SHELL), 'nothing writes it');
  assert(/Outside these limits/.test(SHELL), 'the disclosure does not say it is outside');
  assert(/not sized by the risk authority/.test(SHELL),
    'it must say WHY these bars do not count it');
});

ok('the disclosure hides itself at zero rather than printing $0', () => {
  const fn = SHELL.slice(SHELL.indexOf('function renderMineAside'),
                         SHELL.indexOf('/* ---------- risk budget'));
  assert(/if\(total <= 0\)\{ el\.hidden = true/.test(fn),
    'a permanent "$0 outside these limits" trains the eye to skip the line that will matter');
});

ok('the disclosure changes nothing about what the engine will size', () => {
  assert(!/manual/i.test(SHELL.slice(SHELL.indexOf('const openRisk ='),
                                     SHELL.indexOf("const openCap ="))),
    'the budget arithmetic must stay the engine\'s — this is a disclosure, not a rule change');
  const arm = SERVER.slice(SERVER.indexOf('def manual_arm'), SERVER.indexOf('def draft_bracket'));
  assert(!/risk\.(authorize|size|rule)/.test(arm),
    'arming still must not consult the risk authority — that separation is the design');
});

/* ─────────────────────────── cancelling ─────────────────────────── */

ok('cancel confirms, and says what it does and does not do', () => {
  assert(/data-cancel/.test(SHELL), 'no cancel control');
  assert(/confirm\(`Cancel \$\{what\}\?/.test(SHELL), 'an irreversible-looking action with no confirm');
  assert(/nothing has been ` \+\s*`risked/.test(SHELL),
    'the confirm must say nothing is at stake on an unfilled order');
});

ok('a cancelled order is recorded, never deleted', () => {
  assert(/def cancel_intent/.test(ENGINE), 'no cancel path');
  assert(/"outcome": "CANCELLED"/.test(ENGINE), 'it must leave a fact behind');
  assert(!/DELETE FROM facts/.test(ENGINE), 'this store is append-only');
});

ok('a cancellation is not a trade', () => {
  const book = ENGINE.slice(ENGINE.indexOf('def book(con'));
  assert(/r\["outcome"\] in \("TP", "SL", "TRAIL_STOP", "TIMEOUT"\)/.test(book),
    'CANCELLED must stay out of n/wins/win_rate — otherwise a record improves by cancelling losers');
});

ok('a filled position cannot be cancelled', () => {
  const fn = ENGINE.slice(ENGINE.indexOf('def cancel_intent'), ENGINE.indexOf('def live(con)'));
  assert(/w\["phase"\] == "OPEN"/.test(fn) && /IntentRejected/.test(fn),
    'resolving a filled trade at zero R would erase a real result');
});

ok('arming refreshes the panel that shows the order', () => {
  assert(/invalidate\('\/api\/manual\/live'\)/.test(CHART),
    'the order you just armed would be missing until the cache aged out');
});

/* ─────────────────── failure is not an empty book ─────────────────── */

ok('a book that cannot be read does not render as an empty one', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/catch\(err\)\{/.test(fn), 'a failed fetch is swallowed');
  assert(/Could not read your book/.test(fn), 'it must say the read failed');
  assert(/are still there/.test(fn),
    'the operator must not conclude their orders vanished because a fetch did');
});

ok('an empty book hides the panel rather than showing an empty box', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/if\(!rows\.length\)\{ panel\.style\.display = 'none'/.test(fn),
    'no orders is the normal state and needs no furniture');
});

/* ───────────────── the label that was written twice ───────────────── */

ok('the scan button label lives in one place', () => {
  assert(!/textContent = s\.running \? 'Scanning…' : 'Run Scan'/.test(SHELL),
    'this line rewrote the HTML label on every console poll — the rename to ' +
    '"Check now" survived exactly one poll');
  assert(/b\.dataset\.idleLabel = b\.textContent\.trim\(\)/.test(SHELL),
    'the idle label must be read from the DOM, not restated in JS');
  assert(/>Check now</.test(HTML), 'the HTML is the authority on the label');
});

console.log('\n  ' + passed + ' passed');
