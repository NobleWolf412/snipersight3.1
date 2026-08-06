/* The table stakes an experienced trader checks in the first minute.

   The UX audit walked the app as someone with a decade of screen time and
   listed what was missing before anything else was noticed: hovering a candle
   told you nothing, there was no volume under the price on an app computing
   231,946 volume facts, funding was charged by the simulator and shown
   nowhere, the book could be read but not extracted, and there was not one
   keyboard shortcut in the whole application.

   None of these are clever. That is the point — they are the floor. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const CHART = S('static/chart.js');
const SHELL = S('static/shell.js');
const HTML = S('static/shell.html');
const CSS = S('static/ss.css');
const SERVER = S('server.py');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('trader basics');

ok('volume is drawn, on its own scale', () => {
  assert(/addHistogramSeries/.test(CHART), 'no volume series');
  assert(/priceScaleId: 'vol'/.test(CHART),
    'volume shares the price scale — the candles collapse to a hairline');
  assert(/scaleMargins/.test(CHART), 'the histogram is not pinned to the bottom');
  assert(/c\.close >= c\.open/.test(CHART),
    'volume bars are not coloured by direction — a spike should read as ' +
    'buying or selling, not as a bare quantity');
});

ok('hovering a candle says what it is', () => {
  assert(/subscribeCrosshairMove/.test(CHART), 'nothing reads the crosshair');
  assert(/function paintOHLC/.test(CHART), 'no OHLC readout');
  assert(/id="cOHLC"/.test(HTML), 'the readout has nowhere to render');
  // It must fall back to the last bar, or the strip blanks whenever the
  // pointer leaves the chart.
  assert(/candles\[candles\.length - 1\] : null/.test(CHART),
    'the readout has no fallback when the pointer leaves');
});

ok('the readout cannot push the chart controls around', () => {
  /* It lived in the control strip for one build and wrapped Analyse onto a
     second row at 1400px. It is chart context; it belongs over the chart. */
  const at = HTML.indexOf('id="cOHLC"');
  const box = HTML.indexOf('id="chartBox"');
  assert(at > box && at > 0, 'the readout is back in the control strip');
  assert(/\.c-ohlc\{position:absolute/.test(CSS.replace(/\s+/g, '')) ||
         /position:absolute/.test(CSS.slice(CSS.indexOf('.c-ohlc'), CSS.indexOf('.c-ohlc') + 200)),
    'the readout is not positioned over the chart');
});

ok('funding is shown, not just charged', () => {
  /* The simulator has always charged it — a perp held over a weekend pays
     every settlement, and on a tight target that can exceed the edge. No
     surface ever displayed the rate. */
  assert(/"funding_rate": float\(costs\.DEFAULT_FUNDING_RATE\)/.test(SERVER),
    'trade-config does not publish the funding rate');
  assert(/funding_per_day/.test(SERVER) && /funding_per_day/.test(CHART),
    'the ticket cannot read the settlement count');
  assert(/%\/day to hold/.test(CHART),
    'funding is not stated per DAY — "0.01% every 8 hours" is homework, ' +
    'not a number you can weigh against a target');
});

ok('the book can be taken out of the app', () => {
  assert(/function exportJournal/.test(SHELL), 'no export');
  assert(/id="btnExport"/.test(HTML), 'export has no control');
  // RFC 4180: `why` carries commas, and a CSV that breaks on its own reason
  // column is worse than no export at all.
  assert(/replace\(\/"\/g, '""'\)/.test(SHELL), 'quotes are not escaped');
  assert(/\/\[",\\n\]\//.test(SHELL) || /[",\\n]/.test(SHELL),
    'fields with commas are not quoted');
  assert(/setup_id/.test(SHELL.slice(SHELL.indexOf('CSV_COLS'), SHELL.indexOf('CSV_COLS') + 400)),
    'the export drops setup_id — a row that cannot be traced back to the ' +
    'fact store is not a record');
});

ok('the nav is reachable from the keyboard', () => {
  assert(/const KEYS = \{'1': 'command'/.test(SHELL), 'no surface shortcuts');
  /* Read the surfaces out of the MARKUP rather than listing them: this used to
     be a hardcoded '2'..'5' and a sixth surface could ship with no accelerator
     without anything noticing. Every section with class="surface" needs a key,
     and every key has to name a surface that exists. */
  const map = SHELL.slice(SHELL.indexOf('const KEYS = '),
                          SHELL.indexOf('};', SHELL.indexOf('const KEYS = ')));
  const bound = [...map.matchAll(/'(\w)': '(\w+)'/g)].map(m => m[2]);
  const surfaces = [...HTML.matchAll(/<section class="surface[^"]*" id="s-(\w+)"/g)]
    .map(m => m[1]);
  assert(surfaces.length >= 5, `the section scan found ${surfaces.length} surfaces`);
  for (const s of surfaces) {
    assert(bound.includes(s), `surface ${s} has no key`);
  }
  for (const b of bound) {
    assert(surfaces.includes(b), `key for '${b}' names a surface that does not exist`);
  }
});

ok('shortcuts never steal a keystroke from a field', () => {
  assert(/isContentEditable/.test(SHELL), 'contenteditable is not excluded');
  assert(/input, textarea, select/.test(SHELL), 'form fields are not excluded');
  // e.target is document/window when nothing is focused, and those have no
  // .matches — this threw on every keystroke for one build.
  assert(/typeof t\.matches === 'function'/.test(SHELL),
    'the field guard assumes an Element — it throws when nothing is focused');
  assert(/e\.ctrlKey \|\| e\.metaKey \|\| e\.altKey/.test(SHELL),
    'browser and OS chords are hijacked');
});

ok('nothing that commits money is on a hotkey', () => {
  /* An accelerator that sizes a trade is one fat finger from a position
     nobody meant to take. This app's own rule is that irreversible-feeling
     actions get a confirm dialog, not a shortcut. */
  /* Bounded by the handler, not by a byte count. This sliced a FIXED 1400
     characters after `const KEYS = ` — a window that a sixth surface pushed
     twenty characters along, and which would pass vacuously the moment
     anything above it grew enough to shorten it past the handler's end. Now
     it runs from the map to the clock block that follows the listener, so it
     covers exactly the keydown handler however long that is. */
  const from = SHELL.indexOf('const KEYS = ');
  const to = SHELL.indexOf('/* ---------- clock ----------', from);
  assert(from > 0 && to > from,
    'the keydown handler is no longer bounded by the KEYS map and the clock ' +
    'block — re-anchor this slice before trusting it');
  const block = SHELL.slice(from, to);
  assert(/addEventListener\('keydown'/.test(block),
    'the slice no longer contains the keydown listener it is checking');
  for (const bad of ['tkArm', 'btnHalt', 'arm(', 'cancel']) {
    assert(!block.includes(bad),
      `the keyboard handler reaches ${bad} — arming, halting and cancelling ` +
      `must stay off the keyboard`);
  }
});

ok('a first-time reader has somewhere to start', () => {
  assert(/id="firstRun"/.test(HTML), 'no entry point — the audit counted 79 ' +
    'buttons and not one of them was a place to begin');
  assert(/ss\.seen-intro/.test(SHELL), 'the card is not dismissible');
  assert(/localStorage\.setItem\(FR_KEY/.test(SHELL), 'dismissal is not remembered');
  // A card that reappears every load is worse than no card, so a storage
  // failure must fail CLOSED (stay hidden), never open.
  assert(/catch\(e\)\{ seen = true; \}/.test(SHELL),
    'a storage failure re-shows the intro forever');
});

ok('the words the audit caught unexplained are in the glossary', () => {
  const G = S('static/glossary.js');
  for (const term of ['liquidity', 'sized', 'halt', 'htfAgrees']) {
    assert(new RegExp(`\\b${term}:`).test(G), `no glossary entry for ${term}`);
  }
  // "1D agrees" is the higher-timeframe confirmation printed on the very card
  // asking you to take the trade, and it was the costliest omission.
  assert(/\\d\+\[DWHM\] \(\?:agrees\|opposes\)/.test(G),
    'the "1D agrees" phrase is not matched as one term');
});

console.log('\n  ' + passed + ' passed');
