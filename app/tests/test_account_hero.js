/* The overview answers "how is my account", and the two numbers that answer
   it were not on it.

   Equity lived only as a chip in the top bar. The day's result was one of four
   equal tiles — beside a market count and a setup count, wearing the same
   weight — and for months it rendered an em-dash, because a duplicate function
   name meant its renderer never ran (see shell.js, renderTodayTile). Three of
   those four tiles were technicals.

   These pin the replacement, and most of them exist to stop a regression that
   LOOKS fine: a tile that navigates nowhere, a zero painted as a result, a
   number re-derived beside one already computed. */
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

console.log('account hero');

ok('the account is the headline, not the funnel', () => {
  const hero = HTML.slice(HTML.indexOf('class="account-hero"'),
                          HTML.indexOf('class="funnel-strip"'));
  assert(hero.length > 0, 'the hero is gone or now sits below the funnel');
  assert(/id="mBalance"/.test(hero), 'balance is not in the hero');
  assert(/id="mToday"/.test(hero), "today's result is not in the hero");
});

ok("today's tile is a real control that goes to the journal", () => {
  /* A div with a click handler is not a button: it is not tabbable, Enter and
     Space do nothing on it, and a screen reader announces it as text. */
  const at = HTML.indexOf('id="mTodayTile"');
  const tag = HTML.slice(HTML.lastIndexOf('<', at), at + 400);
  assert(/^<button/.test(tag),
    "today's tile is not a button — a keyboard operator cannot reach it and " +
    'a screen reader announces it as plain text');
  assert(/data-goes="performance-ledger"/.test(tag),
    'the tile does not carry the journal route. #performance-ledger is the ' +
    'established address for Results/Journal — a second spelling of that ' +
    'destination is a second authority for it');
  assert(/aria-label=/.test(tag),
    'no accessible name: the visible content is a currency figure, which ' +
    'announces as a number with no idea what pressing it does');
});

ok('a tile that navigates is delegated, not bound once', () => {
  /* The budget cells are rebuilt from a template string on every portfolio
     poll. A handler attached at load is discarded on the first refresh, and
     the control then LOOKS as clickable as ever and does nothing. */
  const at = SHELL.indexOf("ev.target.closest('[data-goes]')");
  assert(at > 0, 'no delegated handler for data-goes');
  const before = SHELL.slice(Math.max(0, at - 400), at);
  assert(/document\.addEventListener\('click'/.test(before),
    'the data-goes handler is not delegated from the document — re-rendered ' +
    'controls lose it silently');
});

ok('a sub-view request writes storage AND fires the live event', () => {
  /* go() already carries this scar at #performance-ledger: the storage key is
     read exactly once, by workspaces.js at load, so writing it alone works
     from a cold start and is inert on a page that is already up. */
  const at = SHELL.indexOf("ev.target.closest('[data-goes]')");
  const region = SHELL.slice(at, at + 900);
  assert(/sessionStorage\.setItem/.test(region),
    'no storage write — a bookmark or a reload lands on the wrong sub-view');
  assert(/ss:workspace-request/.test(region),
    'no live event — the jump does nothing on a page that is already open, ' +
    'and only takes effect the next time the app boots');
  assert(/catch/.test(region),
    'the storage write is unguarded; private browsing denies it and takes ' +
    'the navigation down with it');
});

ok('position slots goes to the read-only limits, not an editor', () => {
  /* Slots, risk per trade and the daily halt are fixed in R-multiples so that
     paper and live take the same trades and stop at the same point. A control
     that opened an editor would promise something the risk authority does not
     offer. */
  const at = SHELL.indexOf("cell('Position slots'");
  assert(at > 0, 'the slots cell is gone');
  const call = SHELL.slice(at, SHELL.indexOf('+', SHELL.indexOf('no cap configured', at)));
  assert(/'system:risk'/.test(call),
    'the slots cell does not point at System/Risk');
  const cellFn = SHELL.slice(SHELL.indexOf('const cell = ('), at);
  assert(/data-goes-view=/.test(cellFn) && /button type="button"/.test(cellFn),
    'a navigating budget cell is not rendered as a button');
  assert(/const tag = goes \?/.test(cellFn) || /goes \?/.test(cellFn),
    'every budget cell is now a button — open risk and today\'s losses are ' +
    'readings with nothing to open, and a control that goes nowhere is the ' +
    'affordance lying');
});

ok('nothing closed today is a result, not a broken tile', () => {
  /* The empty-window rule this file states four times over. An em-dash reads
     as "this is not working" — which is precisely what the tile WAS while its
     renderer never ran — and a green $0.00 is the confident-looking zero the
     portfolio loader refuses everywhere else. */
  const at = SHELL.indexOf('function renderTodayTile');
  const fn = SHELL.slice(at, SHELL.indexOf('\n  }', at));
  const empty = fn.slice(fn.indexOf('if(!rows.length)'), fn.indexOf('return;'));
  assert(!/textContent = '—'/.test(empty),
    'the empty state is an em-dash again — indistinguishable from the ' +
    'renderer having never run, which is the bug that hid here for months');
  assert(/is-flat/.test(empty),
    'no neutral treatment for a flat day: zero is neither a win nor a loss ' +
    'and must not take the colour of either');
});

ok('the flat state has a colour of its own in CSS', () => {
  assert(/#mTodayTile \.hero-metric\.is-flat\{color:/.test(CSS),
    'is-flat is set in JS but styled nowhere, so a $0.00 day inherits ' +
    'whatever colour was last applied');
  assert(/#mTodayTile\.up \.hero-metric\{color:var\(--green\)/.test(CSS)
    && /#mTodayTile\.down \.hero-metric\{color:var\(--red\)/.test(CSS),
    'the day figure lost its win/loss colours');
});

ok('balance is read from the payload, never re-derived', () => {
  /* §6 rule 9, and this file carries the scar: `p.return_pct + '%'` printed
     -5.84% forty pixels above a card rendering the same field as -5.8%. */
  const at = SHELL.indexOf("$('mBalance').textContent");
  assert(at > 0, 'balance is not rendered');
  const region = SHELL.slice(at, at + 700);
  assert(/money\(p\.equity\)/.test(region),
    'balance is not money(p.equity) — the top bar renders exactly that, and ' +
    'two spellings of one number is how two surfaces come to disagree');
  assert(/pct\(p\.return_pct\)/.test(region),
    'the return is not passed through pct(), the shared helper every other ' +
    'reader of that field uses');
  assert(!/toFixed\(/.test(region),
    'the hero formats a figure itself instead of using the shared helpers');
});

ok('a window with no ruled decisions does not show a confident return', () => {
  const at = SHELL.indexOf("const balSub = $('mBalanceSub')");
  const region = SHELL.slice(at, at + 600);
  assert(/ruled\s*\?/.test(region),
    'the sub-line does not branch on `ruled` — a forward window where the ' +
    'risk authority has ruled on nothing would render +0% as a result');
});

ok('the funnel keeps its three distinct stage names', () => {
  /* Abbreviating these to "eligible" and "ready" in the strip is the 2026-08-09
     ambiguity coming back in a smaller font: "ready" alone does not say ready
     for what, which is the whole reason the three stages were named. */
  const strip = HTML.slice(HTML.indexOf('class="funnel-strip"'),
                           HTML.indexOf('</div>', HTML.indexOf('class="funnel-strip"')));
  assert(/Eligible markets/.test(strip) && /Setups ready/.test(strip),
    'the funnel strip abbreviated its stage names');
  assert(/data-t="universe"/.test(strip) && /data-t="setup"/.test(strip),
    'the glossary hooks were dropped in the demotion — the terms still need ' +
    'to be explainable where they are shown');
});

ok('the hero stacks on a phone at a sanctioned breakpoint', () => {
  const at = CSS.indexOf('.account-hero{grid-template-columns:1fr}');
  assert(at > 0, 'the hero never stacks — two figures side by side on a ' +
    'phone shrink below their own labels');
  const media = CSS.lastIndexOf('@media', at);
  const width = /max-width:(\d+)px/.exec(CSS.slice(media, at));
  assert(width && [640, 900, 1100, 1180].includes(+width[1]),
    `the hero stacks at an ad-hoc ${width && width[1]}px — this file was ` +
    'rescued from twelve of those once');
});

console.log('\n  ' + passed + ' passed');
