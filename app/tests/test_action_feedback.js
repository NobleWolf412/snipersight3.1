/* Every action reports a RESULT and a TIME, and every disabled control says why.

   Observed: Run Scan showed "SCANNING…", reverted, and changed nothing an
   operator could see — no result, no timestamp, no visible tile change. There
   was no way to tell a completed scan from a click that missed, and a control
   you cannot verify is one you learn to distrust.

   `AUTO: OFF` was disabled but styled like a live button, with its reason
   ("locked until the forward record earns it") reachable only by hovering. An
   explanation nobody can find may as well not exist, and an unexplained dead
   button reads as an app that is arbitrary rather than one that is careful.

   And the header would not hold still: the scanner chip cycles between
   `SCANNER · ENGINES PF_ADAUSD`, `SCANNER · AUDIT` and `SCANNER LIVE` at
   different widths, shoving its neighbours sideways every few seconds. Motion
   in the corner of the eye reads as alarm, on the one bar whose job is to be
   ignorable until something is wrong.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const JS = S('shell.js');
const CSS = S('ss.css');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('action feedback');

ok('there is somewhere for a result to appear', () => {
  assert(/id="scanResult"/.test(HTML), 'no result element on Command');
  assert(/scanResult'\)/.test(JS), 'nothing ever writes to it');
});

ok('the result carries a timestamp', () => {
  const i = JS.indexOf('function scanResult(');
  assert(i > 0, 'no scanResult()');
  const body = JS.slice(i, i + 420);
  assert(/toISOString\(\)/.test(body),
         'the result never says WHEN — "scanning…" with no time cannot be told '
         + 'apart from the same message five minutes ago');
});

ok('a finished scan reports its outcome', () => {
  // the poll loop owns completion; the click handler cannot know the result
  const i = JS.indexOf('scanning && !s.running');
  assert(i > 0, 'the scan-finished branch was renamed');
  // to the end of the branch, not a guessed character count — the comment
  // inside it is long enough that a fixed window silently missed the call
  const branch = JS.slice(i, JS.indexOf('scanning = !!s.running', i));
  assert(branch.length > 0, 'the branch could not be delimited');
  assert(/scanResult\(/.test(branch),
         'a scan completes and tells the operator nothing');
});

ok('every failure path reports too', () => {
  const i = JS.indexOf("$('btnScan').addEventListener");
  const h = JS.slice(i, i + 1200);
  assert(/409/.test(h) && /already/.test(h), 'a busy scanner is silent');
  assert((h.match(/scanResult\(/g) || []).length >= 3,
         'some failure paths still change nothing on screen');
  assert(/true\)/.test(h), 'failures are not distinguished from successes');
});

ok('a failed result is visually distinct', () => {
  assert(/\.scan-result\.bad\{/.test(CSS),
         'a failure and a success render identically');
});

ok('the disabled Auto button still carries its reason', () => {
  // Post-purge the reason moved from a visible caption to a hover title —
  // words on demand. The property that matters survives: the control is
  // never disabled WITHOUT a stated reason.
  // through the CLOSING tag: the label is text content, not an attribute
  const m2 = HTML.match(/<button[^>]*id="btnAuto"[\s\S]*?<\/button>/);
  assert(m2, 'the Auto control is gone');
  assert(/title="[^"]*locked until/.test(m2[0]),
         'a disabled control with no stated reason teaches that the app is arbitrary');
  /* Repinned 4 Aug 2026. The reason no longer OPENS with "locked until": the
     UX audit found "Auto: Off" under a heading reading Scanner was taken to
     mean the scanner was off, while it was running 213 cycles. The title now
     leads by saying the scanner IS running and names what is actually off,
     then gives the reason. Both properties are pinned — the label distinguishes
     itself from the scanner, and the reason is still stated. */
  assert(/Auto-trade/.test(m2[0]),
         'the label reads "Auto" alone again — under a Scanner heading that ' +
         'says the scanner is off, which it is not');
  assert(/scanner is running/.test(m2[0]),
         'the title no longer distinguishes auto-trading from scanning');
});

ok('the scanner chip cannot shove the header around', () => {
  const i = CSS.indexOf('#scanChip{');
  assert(i >= 0, 'the scanner chip has no width reservation');
  const rule = CSS.slice(i, CSS.indexOf('}', i));
  assert(/width:/.test(rule), 'the chip still sizes to its content');
  assert(/flex:none/.test(rule), 'the chip can still be stretched by its siblings');
  const t = CSS.slice(CSS.indexOf('#scanTxt{'), CSS.indexOf('}', CSS.indexOf('#scanTxt{')));
  assert(/text-overflow:\s*ellipsis/.test(t), 'a long phase reflows instead of truncating');
  assert(/white-space:\s*nowrap/.test(t), 'the phase can wrap and change the bar height');
});

ok('the clock does not shuffle its own digits', () => {
  const i = CSS.indexOf('#clock{');
  assert(i >= 0, 'the clock has no rule');
  const rule = CSS.slice(i, CSS.indexOf('}', i));
  assert(/tabular-nums/.test(rule),
         'proportional digits make the clock twitch once a second');
});

console.log('\n' + passed + ' passed');
