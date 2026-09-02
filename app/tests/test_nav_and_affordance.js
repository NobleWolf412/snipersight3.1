/* The rail's marks, and the one rule that makes a control admit it is one.

   Two complaints from the operator, one root: the app read as a web page, and
   you could not tell what was clickable. The rail was six text labels — 9px
   type in a 64px strip on a phone, closer to texture than to reading — and
   panels that navigate were styled identically to panels that do not.

   These pin the parts that go quiet when they break. An icon that stops
   rendering leaves a blank cell, not an error; an affordance applied to the
   wrong control is invisible until someone presses it and nothing happens. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const STATIC = path.join(__dirname, '..', 'static');
const HTML = fs.readFileSync(path.join(STATIC, 'shell.html'), 'utf8');
const CSS = fs.readFileSync(path.join(STATIC, 'ss.css'), 'utf8');
const SHELL = fs.readFileSync(path.join(STATIC, 'shell.js'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('nav marks and affordance');

const NAV = HTML.slice(HTML.indexOf('<nav class="nav"'), HTML.indexOf('</nav>'));

ok('every destination carries a mark', () => {
  /* Five routes plus Spotter. A count is the only thing that catches the
     failure where one anchor is edited and its neighbours are not. */
  const marks = NAV.match(/class="nav-ico"/g) || [];
  assert.strictEqual(marks.length, 6,
    `expected 6 marks in the rail, found ${marks.length} — a destination is ` +
    'wearing a blank cell, which renders as nothing rather than as an error');
});

ok('the marks are drawn, not fetched', () => {
  /* An <img> in the rail is a request that can 404 into an empty tab bar,
     and it cannot take the active or focus colour. */
  assert(!/<img[^>]*nav-ico|nav-ico[^>]*<img/.test(NAV),
    'a rail mark is an image — it cannot inherit the active colour and it ' +
    'can fail to load into a blank cell');
  assert(/stroke="currentColor"/.test(NAV),
    'the marks do not take currentColor, so the active, hover and focus ' +
    'colours reach the label but not the mark beside it');
});

ok('the marks are hidden from screen readers', () => {
  /* The label beside each one already names the destination. Announcing both
     reads every tab twice. */
  const icons = NAV.match(/<svg class="nav-ico"[^>]*>/g) || [];
  assert(icons.length > 0, 'no marks to check');
  for (const tag of icons) {
    assert(/aria-hidden="true"/.test(tag),
      'a rail mark is exposed to assistive tech — the visible label beside ' +
      'it already names the destination, so this reads every tab twice');
  }
});

ok('the crosshair belongs to Setups alone', () => {
  /* It is the product's own mark. A second circle-with-ticks anywhere in the
     set stops it meaning "a setup", which is the one thing it is for. */
  const cells = NAV.split('<svg').slice(1);
  const withTicks = cells.filter(c =>
    /M12 1\.8v3\.3/.test(c.slice(0, c.indexOf('</svg>'))));
  assert.strictEqual(withTicks.length, 1,
    'the crosshair appears on more than one destination — it is the ' +
    'product mark and it has to name exactly one thing');
  assert(/Setups/.test(withTicks[0]),
    'the crosshair is not on Setups');
});

ok('labels survive beside the marks', () => {
  /* An icon-only bar trades "what is this word" for "what is this picture".
     The mark carries recognition; the word carries the meaning. */
  for (const word of ['Overview', 'Setups', 'Trade', 'Results', 'System', 'Spotter']) {
    assert(new RegExp('<span>' + word + '</span>').test(NAV),
      `${word} lost its text label — the mark alone is a guessing game`);
  }
});

ok('the phone rail stacks the mark over the label', () => {
  /* A cell one sixth of a phone wide cannot hold a row. Laid out sideways it
     either clips the word or shrinks the mark to nothing. */
  const at = CSS.indexOf('.nav a,.nav .nav-spotter{min-width:0;min-height:64px');
  assert(at > 0, 'the phone rail rule is gone');
  const rule = CSS.slice(at, CSS.indexOf('}', at));
  assert(/flex-direction:column/.test(rule),
    'the phone tab cell is still a row — at one sixth of a phone wide that ' +
    'clips the label or crushes the mark');
});

ok('the affordance is one class, not a dialect per surface', () => {
  assert(/\.tappable\{[^}]*cursor:pointer/.test(CSS),
    '.tappable does not set a pointer cursor — the cheapest signal there is');
  assert(/\.tappable:hover\{/.test(CSS), 'no hover state');
  assert(/\.tappable:active\{/.test(CSS),
    'no press state — a touch device never sees hover, so without this a ' +
    'phone gets no feedback at all');
  assert(/\.tappable:focus-visible\{/.test(CSS),
    'no focus state — a keyboard operator cannot see which control is armed');
});

ok('the press lands at rest, not at a third position', () => {
  const at = CSS.indexOf('.tappable:active{');
  const rule = CSS.slice(at, CSS.indexOf('}', at));
  assert(/transform:translateY\(0\)/.test(rule),
    'the pressed state does not return to rest — a control that hovers up ' +
    'and presses to somewhere other than its resting position reads as sprung');
});

ok('the chevron is reserved for controls that navigate', () => {
  /* A lift says "I respond". It does not say "I go somewhere", and the
     difference is the whole reason the mark exists. Applied to a toggle it
     stops being a promise. */
  assert(/\.tappable\[data-goes\]::after\{/.test(CSS),
    'the chevron is not gated on data-goes — every tappable thing now claims ' +
    'to navigate, including the ones that expand in place');
  assert(!/\.tappable::after\{content/.test(CSS),
    'the chevron is on bare .tappable, so a toggle wears a promise it does ' +
    'not keep');
});

ok('reduced motion keeps the meaning and drops only the travel', () => {
  const at = CSS.indexOf('@media (prefers-reduced-motion:reduce){');
  assert(at > 0, 'no reduced-motion block covering the affordance');
  const block = CSS.slice(at, CSS.indexOf('\n}', at));
  assert(/\.tappable:hover[^{]*\{[^}]*transform:none/.test(block),
    'reduced motion does not stop the lift');
  assert(/border-color/.test(block),
    'reduced motion drops the border change too — that leaves a viewer who ' +
    'switched off animation with no hover feedback whatsoever');
});

ok('shell.js still only toggles nav state, never rewrites it', () => {
  /* The marks live in the markup. A route change that wrote innerHTML would
     erase them on the first navigation — and the rail would look correct
     until you pressed something. */
  const at = SHELL.indexOf("document.querySelectorAll('.nav a').forEach");
  assert(at > 0, 'the nav update loop is gone');
  const region = SHELL.slice(at, at + 700);
  assert(!/innerHTML|textContent\s*=/.test(region),
    'the nav loop writes content — the marks are markup, so this erases them ' +
    'on the first route change');
});

console.log('\n  ' + passed + ' passed');
