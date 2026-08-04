/* "Setup" means ONE thing: a trade candidate.

   The configuration surface was called "Scanner Setup", so the word meant a
   trade opportunity on Command, in the Setup Deck, in "active setups", in "a
   setup only appears once price returns to a zone" — and a settings page in the
   left rail. An operator asked, in as many words, what the toggles were for,
   "because i dont even know how the scanner works".

   Two fixes, both pinned here. The surface is Rules. And it opens with the
   pipeline described in plain language, because a control cannot be judged
   without the step it controls.

   The failure mode these guard is a half-revert: one reference renamed back, or
   the old hash dropped, either of which strands a bookmark on a blank screen.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const SHELL = S('shell.js');
const CSS = S('ss.css');
const GLOSS = S('glossary.js');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('rules surface');

ok('the surface is Rules, not Scanner Setup', () => {
  assert(/data-s="rules"/.test(HTML), 'the nav still points at the old surface');
  assert(/id="s-rules"/.test(HTML), 'the section was not renamed');
  // the comment explaining WHY may name the old label; the markup may not
  const markup = HTML.replace(/<!--[\s\S]*?-->/g, '');
  assert(!/Scanner Setup/.test(markup),
         'the old two-meaning label is still on screen');
  assert(!/id="s-setup"/.test(markup), 'the old section id survives');
});

ok('an old #setup link still lands somewhere', () => {
  // bookmarks, and wizard prose written before the rename
  assert(/SURFACE_ALIASES/.test(SHELL), 'no alias table');
  assert(/setup:\s*'rules'/.test(SHELL), 'the old hash maps nowhere');
  const i = SHELL.indexOf('function go(');
  const body = SHELL.slice(i, i + 400);
  assert(/SURFACE_ALIASES\[name\]/.test(body),
         'go() never consults the alias, so an old hash still blanks the screen');
});

ok('every surface that links to it uses the new hash', () => {
  for (const f of ['funnel.js', 'wizard.js']) {
    const src = S(f);
    assert(!/href: '#setup'/.test(src), `${f} still links to the old hash`);
    assert(/#rules/.test(src), `${f} never links to the surface at all`);
  }
});

ok('the catalogue still refreshes under both names', () => {
  // playbooks.js reloads on arrival; keyed on the hash, so a rename that missed
  // it would leave the catalogue silently stale
  const p = S('playbooks.js');
  assert(/'rules'/.test(p), 'playbooks.js does not know the new name');
  assert(/'setup'/.test(p), 'playbooks.js stopped answering to the old one');
});

ok('the explainer exists and is closed by default', () => {
  assert(/id="howItWorks"/.test(HTML), 'no explainer on the Rules surface');
  const i = HTML.indexOf('id="howItWorks"');
  const tag = HTML.slice(HTML.lastIndexOf('<details', i), i + 40);
  assert(!/\bopen\b/.test(tag),
         'a settings page that opens with an essay is its own problem');
});

ok('it answers the questions that were actually asked', () => {
  const i = HTML.indexOf('id="howItWorks"');
  const body = HTML.slice(i, HTML.indexOf('</details>', i));
  // "is it always scanning? what does run scan do then?"
  assert(/always running/i.test(body), 'never says the scanner runs continuously');
  // substance, not my original phrasing — another session rewrote this prose
  // (for the better) and the old assertion pinned exact words instead of the
  // claim. What must survive any rewrite: Run Scan is the same work, now.
  assert(/Run Scan/.test(body) && /same (pass|check|work)/i.test(body),
         'never explains that Run Scan is the same work, just now');
  // "market weather looks like potential setups?"
  assert(/empty Setup Deck/i.test(body) && /normal state/i.test(body),
         'never says an empty deck beside a busy weather is correct');
  // "im seeing not scanned yet still warming up. whats that"
  assert(/200 daily candles|enough history/i.test(body),
         'never says what warming is waiting for');
  // "arm scanner should take the trade"
  assert(/paper/i.test(body) && /locked/i.test(body),
         'never says Arm does not place a real order');
});

ok('each step names the settings it controls', () => {
  const i = HTML.indexOf('id="howItWorks"');
  const body = HTML.slice(i, HTML.indexOf('</details>', i));
  assert(/Controlled by:/.test(body),
         'the pipeline is described but never tied to the toggles below it, '
         + 'which is the whole reason it is on this surface');
  // accepts either the raw keys or the B7 display labels the page now uses
  assert(/top n|min volume|how many symbols to admit|minimum 24h volume/i.test(body),
         'no setting is named');
});

ok('every term it underlines is defined', () => {
  const i = HTML.indexOf('id="howItWorks"');
  const body = HTML.slice(i, HTML.indexOf('</details>', i));
  const keys = [...body.matchAll(/data-t="([a-zA-Z]+)"/g)].map(m => m[1]);
  assert(keys.length, 'the explainer underlines nothing');
  for (const k of keys) {
    assert(new RegExp('\\b' + k + '\\s*:').test(GLOSS),
           `"${k}" is underlined as a defined term and has no glossary entry — `
           + 'it silently explains nothing on hover');
  }
});


ok('both are readable prose, not chrome', () => {
  for (const sel of ['.explainer-body{']) {
    const i = CSS.indexOf(sel);
    assert(i >= 0, sel + ' has no styling');
    const rule = CSS.slice(i, CSS.indexOf('}', i));
    assert(!/--f-mono/.test(rule), sel + ' sets paragraphs in the label face');
    assert(!/text-transform:\s*uppercase/.test(rule),
           sel + ' is all-caps, which destroys word shape at sentence length');
  }
});

console.log('\n' + passed + ' passed');
