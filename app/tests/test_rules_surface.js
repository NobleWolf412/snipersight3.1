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
  assert(/HIDDEN_SETTINGS/.test(SHELL), 'no hide list');
  for (const dead of ['strategy_breakout_retest', 'strategy_range_fade']) {
    assert(SHELL.includes(`'${dead}'`), `${dead} is not in the hide list`);
  }
  assert(/!HIDDEN_SETTINGS\.has\(s\.name\)/.test(SHELL),
    'the builder does not consult the hide list');
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

ok('the halt still has exactly one path', () => {
  assert(/BUTTON_OWNED = new Set\(\['halted'\]\)/.test(SHELL),
    'the halted checkbox is renderable again — two paths to a destructive action');
});

ok('the dirty banner still guards Apply', () => {
  assert(/id="dirtyBanner"/.test(HTML), 'unsaved changes have no banner');
  assert(/id="setApply"/.test(HTML) && /id="setReset"/.test(HTML),
    'Apply/Discard are gone');
});

console.log('\n  ' + passed + ' passed');
