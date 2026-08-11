/* Settings — configuration only, and the renames that got it there.

   This file guarded the Rules surface: an explainer essay, a playbook
   catalogue, five strategy toggles. Operator rulings, 3 Aug 2026: the essay
   is gone ("nobody reads a wall to flip a switch"), the catalogue is gone,
   the two dead toggles are gone ("no need to talk about dead anything"), and
   the surface is now Settings: exchanges, Claude, and the knobs that do
   something. These pins hold the new contract — and the renames' safety net:
   the old #rules address still lands here.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const SHELL = S('shell.js');
const CSS = S('ss.css');
/* Engine source, read as text like everything else here. The hide list is only
   correct RELATIVE to what the engine reads, so pinning it without reading the
   other side is what let two inert switches ship visible. */
const E = f => fs.readFileSync(path.join(__dirname, '..', 'engine', f), 'utf8');
const SETTINGS = E('settings.py');
const SETUPS = E('setups.py');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('settings surface');

ok('the surface is Settings, and the old addresses still arrive', () => {
  assert(/id="s-settings"/.test(HTML), 'no Settings section');
  assert(!/id="s-rules"/.test(HTML), 'the Rules section survived the rename');
  assert(/data-s="settings">Settings</.test(HTML), 'the nav does not say Settings');
  assert(/rules: 'settings'/.test(SHELL),
    'links and habits point at #rules — the alias must keep them working');
  assert(/setup: 'settings'/.test(SHELL), 'the older #setup alias broke');
});

ok('the essay and the catalogue are gone', () => {
  assert(!/id="howItWorks"/.test(HTML), 'the explainer essay came back');
  assert(!/id="playbookRoot"/.test(HTML), 'the playbook catalogue came back');
  assert(!/playbooks\.js/.test(HTML), 'playbooks.js is still shipped');
});

ok('the dead toggles are hidden, not deleted from the server', () => {
  /* DERIVED, not listed. This pinned two names and went half-blind: two more
     inert strategy switches (liquidity-sweep, compression-release) shipped as
     ordinary working checkboxes and the suite had no opinion, because the
     property was written down as a pair of strings instead of as a rule.

     The rule is: a strategy switch the ENGINE does not read must not render.
     Both halves are read out of the source here, so the day someone wires one
     of these into `setups.enabled_strategies` this test fails until they also
     unhide it — and the day someone adds a new inert one, it fails then too.
     Neither direction depends on anyone remembering to edit this list.

     Why it matters more than tidiness: every one of these is BEHAVIOURAL in
     settings.py, so flipping it calls start_baseline and resets the forward
     trade count the live gate needs 100 of. An inert switch is not a dead
     control, it is a live control wired to the wrong thing. */
  assert(/HIDDEN_SETTINGS/.test(SHELL), 'no hide list');
  assert(/!HIDDEN_SETTINGS\.has\(s\.name\)/.test(SHELL),
    'the builder does not consult the hide list');

  const declared = new Set(
    [...SETTINGS.matchAll(/"(strategy_[a-z_]+)"\s*:\s*\(/g)].map(m => m[1]));
  assert(declared.size >= 4,
    `only ${declared.size} strategy settings found — the SPEC shape changed ` +
    'and this test is no longer reading it');

  const readBlock = SETUPS.slice(SETUPS.indexOf('def enabled_strategies'));
  const wired = new Set(
    [...readBlock.slice(0, 900).matchAll(/\("(strategy_[a-z_]+)",\s*"/g)].map(m => m[1]));
  assert(wired.size > 0,
    'enabled_strategies no longer names its settings keys in a readable form — ' +
    'this test cannot tell a wired switch from an inert one any more');

  const hidden = new Set(
    [...SHELL.slice(SHELL.indexOf('const HIDDEN_SETTINGS'),
                    SHELL.indexOf('function buildSettings'))
       .matchAll(/'(strategy_[a-z_]+)'/g)].map(m => m[1]));

  const inertButVisible = [...declared].filter(k => !wired.has(k) && !hidden.has(k));
  assert.deepStrictEqual(inertButVisible, [],
    'these strategy switches are read by no engine yet render as working ' +
    'checkboxes, and each one resets the forward baseline when flipped: ' +
    inertButVisible.join(', '));

  const wiredButHidden = [...wired].filter(k => hidden.has(k));
  assert.deepStrictEqual(wiredButHidden, [],
    'these switches DO drive the engine but are hidden from the operator, ' +
    'so a real rule change has no visible control: ' + wiredButHidden.join(', '));
});

ok('Exchanges keeps its one security line, on the chip', () => {
  assert(/>Exchanges</.test(HTML), 'the credentials panel lost its name');
  assert(/read-only keys only/.test(HTML), 'the security posture went silent');
  assert(/DPAPI/.test(HTML), 'where keys live must stay discoverable on hover');
});

ok('Claude has a panel: model and CLI check', () => {
  assert(/id="setCpModel"/.test(HTML), 'no model select');
  assert(/id="btnCpTest"/.test(HTML), 'no CLI test button');
  assert(/'ss-cp-model'/.test(SHELL),
    'the select must write the SAME key the copilot drawer reads — one preference, not two');
  assert(/\/api\/copilot\/health/.test(SHELL), 'the test button calls nothing');
});

ok('Risk is read-only and says why on hover', () => {
  assert(/id="riskNow"/.test(HTML), 'the live risk rows are gone');
  assert(/re-size the entire forward record/.test(HTML),
    'the why-not-editable reason vanished entirely — it belongs on the hover');
  assert(!/fine-print/.test(HTML), 'the essay disclosure came back');
});

ok('Guardrails keeps its rows and moves its sentence to hover', () => {
  assert(/id="guardRows"/.test(HTML), 'the guardrail rows are gone');
  assert(/blocks NEW entries only/.test(HTML),
    'the new-entries-only fact must survive on the chip hover');
});

/* WAS: Risk and Guardrails as two panels, each printing the daily loss halt,
   the maximum concurrent positions and the total open risk — one from
   /api/trade-config in fractions, one from /api/settings.values.risk_config in
   percentages, the second inventing 6, 2 and 4 when a key was absent. Three
   caps the engine owns, six readings on one surface, three of them a guess.

   The property this now pins is the one that was always meant: ONE authority
   per cap, and no UI-invented default standing in for a number the engine
   owns. Both output blocks are in one panel; #riskNow is the caps and nothing
   else prints them. */
ok('a cap is read from one authority, and never invented', () => {
  const ri = SHELL.indexOf("$('riskNow').innerHTML");
  const gi = SHELL.indexOf("$('guardRows').innerHTML");
  assert(ri > 0 && gi > 0, 'one of the two settings blocks was renamed');
  const guards = SHELL.slice(gi, SHELL.indexOf(';', gi));
  for (const cap of ['daily loss halt', 'max concurrent', 'total open risk']) {
    assert(!guards.includes(cap),
      `"${cap}" is printed by the guardrail block as well as by #riskNow — ` +
      `two readings of one cap, and they were in different units`);
  }
  assert(!/setValues\.risk_config|values\.risk_config\b(?![\s\S]{0,3}in perc)/
    .test(SHELL.replace(/\/\*[\s\S]*?\*\//g, ' ')),
    'the settings copy of the risk caps is being read again — /api/trade-config ' +
    'is the authority, and the two disagreed about units');
  assert(!/!=\s*null\s*\?\s*rc\./.test(SHELL),
    'a client-side fallback for an engine-owned cap came back');
  // one panel, one heading
  assert(/Risk &amp; guardrails|Risk & guardrails/.test(HTML),
    'the merged panel lost its heading');
  assert(!/<h2 class="t-section">Guardrails<\/h2>/.test(HTML),
    'Guardrails is a second panel again');
});

ok('the halt still has exactly one path', () => {
  assert(/BUTTON_OWNED = new Set\(\['halted'\]\)/.test(SHELL),
    'the halted checkbox is renderable again — two paths to a destructive action');
});

ok('the dirty banner still guards Apply', () => {
  assert(/id="dirtyBanner"/.test(HTML), 'unsaved changes have no banner');
  assert(/id="setApply"/.test(HTML) && /id="setReset"/.test(HTML),
    'Apply/Discard are gone');
});

/* The lock that had no key. "live execution LOCKED" was printed here and the
   condition it named was defined nowhere in the system, so the app's stated
   purpose sat behind a door with no handle (UX audit, 4 Aug 2026). */
/* WAS: `id="gateRoot"` on Settings. The criteria moved to Results' Progression
   track — they were a wheel of met/not-met cards with a ring and a note,
   thirty lines from a wheel of met/not-met cards with a ring and a note that
   measured the same forward record and shared two criteria outright.

   The property is unchanged and is what this pins: the lock must not be a dead
   end. It has to say what it scores, and the criteria have to be reachable
   from it in one click. WHERE they render is a layout decision; that they
   exist, are measured by the engine, and are one link away is not. */
ok('going live is not a dead end', () => {
  assert(/Going live/.test(HTML), 'the panel lost its heading');
  assert(/id="gateChip"/.test(HTML), 'the lock no longer says where the record stands');
  assert(/id="gateFoot"/.test(HTML), 'the build caveat has nowhere to render');
  assert(/href="#results"/.test(HTML.slice(HTML.indexOf('id="gateChip"'))),
    'the Going live panel does not link to the criteria — a lock whose ' +
    'conditions are one surface away and unlinked is the dead end this ' +
    'panel was built to end');
  assert(/loadLiveGate/.test(SHELL), 'nothing reads the criteria');
  assert(/\/api\/live-gate/.test(SHELL), 'the criteria are not read from the engine');
  assert(/id="progTrack"/.test(HTML), 'the track the criteria render into is gone');
});

ok('the criteria and the milestones share one verdict word', () => {
  /* LOCKED used to mean two things thirty lines apart: a milestone the record
     had not reached (Progression) and live execution being off (Settings).
     One track, one MET / NOT MET vocabulary; LOCKED survives on Settings
     meaning exactly one thing. */
  const i = SHELL.indexOf('function renderProgression()');
  assert(i > 0, 'renderProgression was renamed');
  /* LINE-ENDING AGNOSTIC. This anchored on '\n  }\n', and shell.js in a
     Windows checkout is 100% CRLF — so indexOf returned -1, slice(i, -1)
     yielded the entire rest of the file, and the two assertions below were
     satisfied by ANY occurrence of those strings anywhere beneath, including
     inside the Ledger. A fail-open slice, in the test whose stated purpose
     was to pin this precisely. */
  const endM = /\r?\n {2}\}\r?\n/.exec(SHELL.slice(i + 200));
  assert(endM, 'could not find the end of renderProgression');
  const block = SHELL.slice(i, i + 200 + endM.index);
  assert(/'MET'/.test(block) && /'NOT MET'/.test(block),
    'the progression track no longer stamps MET / NOT MET');
  assert(!/EARNED/.test(block),
    'EARNED is back on the progression track — two verdict vocabularies for ' +
    'one idea, on one rail');
});

ok('LOCKED points at where the condition is written down', () => {
  assert(/LOCKED — see Going live/.test(SHELL),
    'the guardrail row says LOCKED and nothing else again — a lock whose ' +
    'condition is stated nowhere is an unfinished thought, not caution');
});

ok('every criterion shows how close it is, proportionally', () => {
  /* The bar became a ring when the gates moved onto the app's shared card.
     The PROPERTY is unchanged and is what this pins: a lock must show its
     distance, not just its state, because "how close am I" is the only
     question worth asking of one. Either shape satisfies it; a bare
     MET/NOT MET does not. */
  assert(/gate-card/.test(SHELL) && /gate-card/.test(CSS),
    'the criteria no longer render as cards — check this test still ' +
    'describes the code');
  /* The criteria moved onto the shared Progression rail, so the ring is drawn
     from the row's `frac` rather than inline from `c.progress`. Pin the two
     halves of the property separately: the engine's measured progress reaches
     the row, and the row draws it. */
  assert(/c\.progress/.test(SHELL), 'the indicator is not driven by measured progress');
  const gi = SHELL.indexOf('function gateRows()');
  assert(gi > 0, 'gateRows was renamed — this test no longer reads the criteria');
  assert(/frac:[^\n]*c\.progress/.test(SHELL.slice(gi, gi + 900)),
    'the engine\'s measured progress no longer reaches the card');
  const pi = SHELL.indexOf('function renderProgression()');
  assert(/ringSvg\(r\.frac/.test(SHELL.slice(pi, pi + 3000)) || /gate-bar/.test(SHELL),
    'progress is not drawn — a lock that shows only its state tells the ' +
    'operator nothing about how far off it is');
});

ok('the build gate is stated apart from the evidence gate', () => {
  assert(/build_note/.test(SHELL),
    'the order-router caveat is dropped — a passing evidence bar would read ' +
    'as permission to trade, which is how Arm stayed dead for months');
  assert(/gate-foot/.test(CSS), 'the build note has no styling of its own');
});

console.log('\n  ' + passed + ' passed');
