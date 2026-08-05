/* "At a level" must not read as the engine's plans.

   The panel exists because it was impossible to tell them apart. The ticket
   draws a bracket on EVERY chart — including markets the engine has never
   considered — so an operator checking LINK on the 1D saw an entry, a target
   and a stop, went to arm it, and reasonably assumed the engine had put them
   there. It had not: price was 2.46 ATR from that zone and the engine's own
   attention stops at 1.

   So the properties pinned here are about honesty, not layout:

     · the reach label comes off the PAYLOAD, never recomputed in the client
       from a bound the client holds its own copy of;
     · a market that could not be read is announced, because a missing row and
       "price is nowhere near a level there" look identical on screen;
     · the panel says what it excluded — the shadow half is 11 of 30 symbols;
     · an empty list hides the panel rather than rendering an empty promise.

   Source text rather than a rendered DOM, per the suite's convention: these
   are contracts about which branch exists at all, and a renderer test can only
   exercise the branch it happens to hit. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const APP = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(APP, 'static', 'shell.js'), 'utf8');
const HTML = fs.readFileSync(path.join(APP, 'static', 'shell.html'), 'utf8');
const PY = fs.readFileSync(path.join(APP, 'engine', 'nearlevels.py'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

function body(name) {
  const i = SRC.indexOf('function ' + name + '(');
  assert(i >= 0, name + '() not found — renamed?');
  let depth = 0, j = i, started = false;
  while (j < SRC.length) {
    if (SRC[j] === '{') { depth++; started = true; }
    else if (SRC[j] === '}') { depth--; if (started && depth === 0) break; }
    j++;
  }
  return SRC.slice(i, j + 1);
}

const RENDER = body('renderNear');

ok('the panel and its mount exist in the shell', () => {
  assert(/id="nearPanel"/.test(HTML), 'nearPanel missing from shell.html');
  assert(/id="near"/.test(HTML), 'the row mount is missing');
  assert(/id="nearLede"/.test(HTML), 'the lede that states scope is missing');
});

ok('an empty list hides the panel instead of promising an empty one', () => {
  assert(/if\(!rows\.length\)\{[^}]*display\s*=\s*'none'/.test(RENDER),
    'renderNear must hide the panel when there is nothing near a level');
});

ok('the reach label is read off the payload, never recomputed here', () => {
  assert(/r\.engine_reach/.test(RENDER),
    'the row must use the payload field');
  /* The bounds are the ENGINE's (setups.PROX_ATR, FORMING_TFS). A literal 1 or
     a FORMING_TFS list in the client is a second copy that drifts silently the
     day the engine moves its own bound — which is exactly how the Approaching
     meter ended up scaled against the wrong constant. */
  assert(!/PROX_ATR|FORMING_TFS/.test(RENDER),
    'the client must not restate the engine constants');
  assert(!/distance_atr\s*[<>]=?\s*1\b/.test(RENDER),
    'the client must not re-derive reach from a hard-coded bound');
});

ok('both bounds ride on the payload rather than being assumed', () => {
  assert(/d\.prox_atr/.test(RENDER) && /d\.max_distance_atr/.test(RENDER),
    'renderNear must take both bounds from the response');
  assert(/"prox_atr"/.test(PY) && /"max_distance_atr"/.test(PY),
    'the endpoint must send both bounds');
});

ok('a market that could not be read is announced, not dropped in silence', () => {
  assert(/d\.warnings/.test(RENDER),
    'renderNear must surface the sweep warnings');
  assert(/could not be read/.test(RENDER),
    'the warning must say what it means for the list');
  assert(/warnings\.append/.test(PY),
    'the sweep must record a warning when a market cannot be read');
});

ok('the panel states what it left out', () => {
  assert(/shadow_excluded/.test(RENDER),
    'the lede must report the shadow symbols this list does not cover');
});

ok('every row says how the engine regards that zone', () => {
  for (const state of ['AT_ZONE', 'IN_RANGE', 'NO_FORMING_ON_TF', 'OUT_OF_RANGE']) {
    assert(SRC.includes(state), 'no sentence for reach state ' + state);
    assert(PY.includes(state), state + ' is not a state the sweep can emit');
  }
});

ok('an out-of-range row disowns the bracket rather than implying one', () => {
  /* The whole failure this panel was built for. The far rows must not read as
     something the engine put there. */
  const say = SRC.slice(SRC.indexOf('OUT_OF_RANGE:'), SRC.indexOf('function renderNear'));
  assert(/not considering/.test(say) && /not the engine/.test(say),
    'the out-of-range sentence must say the engine is not behind it');
});

ok('the row shows the zone and the distance, never a tradeable bracket', () => {
  /* Descriptive, not prescriptive. The payload carries entry/sl/tp — it is the
     same draft.for_symbol() the ticket calls — and a Command-tab row laying
     those three out reads as advice regardless of the heading above it. */
  for (const field of ['r.entry', 'r.sl', 'r.tp']) {
    assert(!RENDER.includes(field),
      'renderNear renders ' + field + ' — a bracket on this surface reads as advice');
  }
  assert(/distance_atr/.test(RENDER), 'the distance is the row’s number');
});

ok('prices go through the shared formatter, not a local one', () => {
  assert(/px\(a\)|px\(b\)/.test(RENDER),
    'zone bounds must be formatted with px(), the formatter every panel shares');
});

ok('the sweep is scoped to Command only', () => {
  assert(/\['command',\s*\(\)\s*=>\s*loadNearLevels\(\)\]/.test(SRC),
    'loadNearLevels must be registered for the command surface');
  assert(!/\[null,\s*\(\)\s*=>\s*loadNearLevels\(\)\]/.test(SRC),
    'a ~1.7s sweep must not run on every surface');
});

console.log(`\n${passed} checks passed`);
