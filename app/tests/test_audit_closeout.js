/* The last mechanical audit items, pinned.

   B4 — one path to a halt. The big red button confirms and names its
   consequence; the `halted` checkbox in the settings list was a second,
   quieter route to the same destructive state, applied with everything else.

   B7 — the risk panel's nine-line justification became one line plus a
   disclosure. The reasoning is worth keeping; not worth reading every visit.

   C — /api/context wired to the chart (the timeframe ladder at the decision
   point), /api/swings and /api/track deleted as superseded, and the wizard's
   "restart the background scanner" prose became a button that calls the
   endpoint built for it.

   D3 — the perf and telemetry panels are real <table> elements.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const JS = S('shell.js');
const CHART = S('chart.js');
const WIZ = S('wizard.js');
const CSS = S('ss.css');
const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('audit closeout');

ok('halting has exactly one path', () => {
  assert(/BUTTON_OWNED/.test(JS), 'no button-owned filter');
  assert(/BUTTON_OWNED = new Set\(\['halted'\]\)/.test(JS),
         'halted is not the setting the filter owns');
  const i = JS.indexOf('function buildSettings');
  const body = JS.slice(i, i + 300);
  // The filter grew a second clause (HIDDEN_SETTINGS, the dead-toggle hide
  // list) in the Settings rebuild; the property is unchanged — halted never
  // renders as a checkbox.
  assert(/!BUTTON_OWNED\.has\(s\.name\)/.test(body),
         'the settings list still renders a second, unconfirmed route to a halt');
  // display is not a path: the guardrails panel must still SHOW the state
  assert(/operator halt/.test(JS), 'hiding the control also hid the state');
});

ok('the risk justification survives on the hover', () => {
  // The one-line + disclosure pair was purged with the rest of the prose;
  // the justification now rides the Risk chip's title. The property is the
  // same: read-only is never unexplained.
  const i = HTML.indexOf('id="riskNow"');
  const before = HTML.slice(Math.max(0, i - 900), i);
  assert(/re-size the entire forward record/.test(before),
         'read-only with no reachable reason teaches that the app is arbitrary');
});

ok('the per-timeframe context still reaches the chart', () => {
  // The ladder ELEMENT died in the header consolidation (it read as a second
  // timeframe picker). The FACT it carried — regime per timeframe from
  // /api/context — survives on the regime chip's hover, and this pin follows
  // the fact, not the furniture.
  const i = CHART.indexOf('async function loadContext');
  assert(i > 0, 'loadContext is gone — the wiring audit regressed');
  const fn = CHART.slice(i, i + 1200);
  assert(/\/api\/context/.test(fn), 'loadContext no longer calls /api/context');
  assert(/cRegime/.test(fn),
    'the context no longer lands anywhere the operator can find it');
});

ok('the superseded routes are gone, with the reasoning recorded', () => {
  assert(!/@app\.get\("\/api\/swings"\)/.test(SERVER),
         '/api/swings is back — it is a strict subset of /api/facts?kind=swing');
  assert(!/@app\.get\("\/api\/track"\)/.test(SERVER),
         '/api/track is back — redundant with /api/performance.by_symbol');
  assert(/retired 2026-07-31/.test(SERVER),
         'the routes were deleted without recording why, so someone will '
         + 'reinvent them');
  assert(/@app\.get\("\/api\/facts"\)/.test(SERVER), 'the superseding route vanished too');
});

ok('the wizard restart is a button, not an instruction to find a terminal', () => {
  assert(/system\/restart\?target=scanner/.test(WIZ),
         'the wizard still tells the operator to restart the scanner in prose');
  assert(/data-confirm/.test(WIZ) && /confirm\(act\.dataset\.confirm\)/.test(WIZ),
         'a process restart fires with no confirmation');
  const i = WIZ.indexOf("closest('[data-action]')");
  const h = WIZ.slice(i, i + 1200);
  assert(/toISOString/.test(h), 'the action reports no time');
  assert(/refused|HTTP/.test(h),
         'a refusal (no watchdog supervising) is not distinguished from success');
  assert(/setTimeout\(run/.test(h),
         'the wizard never re-diagnoses, so the verdicts describe the old state');
});

ok('the data tables are tables', () => {
  assert(/<table class="data-table/.test(JS),
         'perf/telemetry rows are still div grids a screen reader cannot navigate');
  assert(/scope="col"/.test(JS) && /scope="row"/.test(JS),
         'cells carry no scope, so columns are shapes rather than answers');
  assert(/\.data-table\{/.test(CSS),
         'tables have no styling — the semantics changed and the pixels broke');
  /* The weather grid USED to be the exemption here — a symbol x timeframe
     table whose rows were expanding buttons, so it announced as a disclosure
     list rather than as a table.

     That grid no longer exists. It listed the same markets the At-a-level
     sweep listed, one screen apart, and both halves are now one card per
     market in Market Watch. So the exemption is retired and replaced by the
     property that has to hold in its place: weather renders no grid at all,
     and the card that absorbed it keeps each regime label bound to the
     timeframe it belongs to. A bare "Bear weakening" with the "4H" lost is
     the accessibility failure this assertion exists to catch — it is the
     same claim the old table made with a column header. */
  const W = S('weather.js');
  assert(!/wx-row|wx-data/.test(W),
         'weather still renders its per-symbol grid — it moved into Market '
         + 'Watch, and two copies of one reading is how they drift');
  assert(/class="wl-reg/.test(JS) && /<b>\$\{esc\(t\.tf\)\}<\/b>/.test(JS),
         'the watch card prints a regime label without its timeframe beside '
         + 'it, so the reading cannot be attributed to a timeframe');
});

ok('the served shell is version-stamped by the server', () => {
  assert(/_asset_version/.test(SERVER), 'no version authority');
  assert(/re\.sub\(r"\\\?v=\\d\+"/.test(SERVER),
         'the route serves the hand-edited ?v numbers again — thirteen tags '
         + 'maintained by whoever remembers is how one stale module runs '
         + 'against twelve fresh ones');
  assert(/st_mtime/.test(SERVER),
         'the version is not derived from the files, so it either never '
         + 'changes or busts every cache on every restart');
});

console.log('\n' + passed + ' passed');
