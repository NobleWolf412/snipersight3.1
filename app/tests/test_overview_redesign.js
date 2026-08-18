/* Overview hierarchy and carousel contracts. These are source-level ratchets;
   browser measurements still belong in the visual verification pass. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const STATIC = path.join(__dirname, '..', 'static');
const HTML = fs.readFileSync(path.join(STATIC, 'shell.html'), 'utf8');
const CSS = fs.readFileSync(path.join(STATIC, 'ss.css'), 'utf8');
const SHELL = fs.readFileSync(path.join(STATIC, 'shell.js'), 'utf8');
const OPS = fs.readFileSync(path.join(STATIC, 'operations.js'), 'utf8');
const WEATHER = fs.readFileSync(path.join(STATIC, 'weather.js'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('overview redesign');

ok('bot overview contains its directive, instruments, and guardrails', () => {
  const brief = HTML.indexOf('class="panel panel-accent bracket command-hero"');
  const missions = HTML.indexOf('class="panel floating mb-panel overview-intel"');
  const risk = HTML.indexOf('id="budgetPanel"');
  assert(brief > 0, 'command brief is missing');
  assert(risk > brief && risk < missions, 'guardrails must be inside the bot overview');
  assert(missions > brief, 'mission carousel must follow the brief');
  assert(HTML.includes('>Bot overview</span>'));
  assert(!HTML.includes('>Rules of engagement</h2>'));
});

ok('command state is painted from the operations read model', () => {
  assert(OPS.includes("api('/api/operations')"));
  assert(OPS.includes('scanner.eligible_markets') || SHELL.includes('scanner'),
    'nothing reads the scanner state from the read model');
  assert(OPS.includes('a.open_positions'));
});

/* ONE AUTHORITY PER FACT, AND IT IS THE TOPBAR.

   Mode, scanner state and exposure were each rendered THREE times on the
   Overview: the topbar chip, the command hero's pulse row inches below it,
   and the statusbar — all three from the same payload, so a disagreement
   between them could only ever be a bug. The eligible count managed three
   renderings too (topbar chip, Command tile, statusbar).

   The topbar won every one of them because it is outside .stage, so it is
   the only one of the three that survives on Chart, Results and System.

   These assert the count, not the absence of particular ids: a fourth
   rendering added later fails just as loudly as a restored third. */
ok('mode, scanner and exposure are each stated once', () => {
  for (const gone of ['commandMode', 'commandScanner', 'commandData',
                      'commandExposure', 'executionStatus', 'sbWatch']) {
    assert(!HTML.includes(`id="${gone}"`), gone + ' restates a topbar fact again');
    assert(!OPS.includes(`'${gone}'`), 'operations.js writes ' + gone + ' again');
  }
  for (const [id, what] of [['modeChip', 'execution mode'], ['scanTxt', 'scanner state'],
                            ['exposureChip', 'open exposure'], ['healthTxt', 'data health']]) {
    assert((HTML.match(new RegExp(`id="${id}"`, 'g')) || []).length === 1,
      `${what} has more than one display again`);
  }
  assert(!CSS.includes('.command-pulse'), 'the pulse row CSS outlived its markup');
  assert(!CSS.includes('.command-mode'), 'the hero mode chip CSS outlived its markup');
});

/* The statusbar sentence carried this warning and the statusbar sentence is
   gone. It may not go with it: the whole point of the mode display is that a
   dead feed must never read as "orders are safely disabled". */
ok('a dead operations feed still says do not trust the mode', () => {
  assert(/do not assume orders are disabled/i.test(OPS),
    'the surviving mode display lost the warning the statusbar used to carry');
  assert(/mode\.title =/.test(OPS) && /MODE UNKNOWN/.test(OPS),
    'the mode chip failure state no longer explains itself');
});

/* The disposition line had TWO writers producing one sentence from one
   payload, and both printed the scanner's raw stage: `Bot progress - IMPORT /
   BTCUSDT`. The server had already written the plain sentence that belonged
   there. These pin the arrangement that replaced them, not the prose. */
ok('one writer owns the disposition sentence', () => {
  assert(!/\$\('disposition'\)/.test(OPS),
    'operations.js writes the disposition again — two authorities for one sentence');
  /* Backtick-anchored so the comments recording WHY this was removed do not
     themselves trip the guard: what is banned is rendering the string, not
     naming it. */
  assert(!/`Bot progress/.test(OPS) && !/`Bot progress/.test(SHELL),
    'the raw scanner stage is back on the line that should carry a sentence');
  assert(!/scanner\.stage/.test(OPS) && !/scanner\.stage/.test(SHELL),
    'the scanner stage is being read into a surface again');
  assert(!HTML.includes('id="commandNarrative"'),
    'the hero restates the disposition line again');
  assert(SHELL.includes('opportunities') && /chances\.narrative/.test(SHELL),
    'the disposition no longer reads the server narrative — it is deriving its own');
});

ok('the disposition stays loud when it cannot answer', () => {
  assert(/unavailable[\s\S]{0,400}?Do not assume order dispatch is disabled/.test(SHELL),
    'an unreadable operations feed no longer says so on the line');
  assert(/window\.SSOperationsData = \{unavailable: true\}/.test(OPS),
    'a failed poll leaves the last good payload in place, so the line goes stale silently');
  assert(/The scanner is not running/.test(SHELL),
    'a dead scanner no longer reads differently from a quiet market');
  assert(/addEventListener\('ss:operations'/.test(SHELL) && /ss:operations/.test(OPS),
    'the sentence no longer repaints on the operations cadence');
});

ok('the carousel exposes position and a route to the comparison surface', () => {
  assert(HTML.includes('id="mbPosition"'));
  assert(/href="#opportunities">View all setups/.test(HTML));
  assert(/position: 'mbPosition'/.test(SHELL));
  assert(/position\.textContent = st\.cards\.length/.test(SHELL));
});

ok('mission briefs and Overwatch are accessible tabs with separate carousels', () => {
  assert(HTML.includes('class="overview-tabs" role="tablist"'));
  assert(/id="overviewMissionsTab"[\s\S]*?role="tab"[\s\S]*?aria-controls="overviewMissions"/.test(HTML));
  assert(/id="overviewOverwatchTab"[\s\S]*?role="tab"[\s\S]*?aria-controls="overviewOverwatch"/.test(HTML));
  assert(/id="overviewMissions" role="tabpanel"[\s\S]*?id="mbTrack"/.test(HTML));
  assert(/id="overviewOverwatch" role="tabpanel"[\s\S]*?id="near"/.test(HTML));
  assert(SHELL.includes("addEventListener('ss:overview-tab'"), 'revealed wheels are not re-synced');
});

ok('overview tabs support click and keyboard selection without losing wheel state', () => {
  assert(OPS.includes("document.querySelectorAll('[data-overview-tab]')"));
  assert(OPS.includes("['ArrowLeft', 'ArrowRight', 'Home', 'End']"));
  assert(OPS.includes("panel.hidden = !active"));
  assert(OPS.includes("new CustomEvent('ss:overview-tab'"));
});

ok('active trade cards are semantic and have one dominant management action', () => {
  assert(SHELL.includes("document.createElement('article')"));
  assert(SHELL.includes('>Manage position</button>'));
  assert(/mc\.mission \.mc-acts \.btn-primary\{grid-column:1\/-1;order:-1/.test(CSS));
  assert(SHELL.includes('>Review setup</button>'));
});

ok('the command brief collapses for mobile', () => {
  assert(/@media\(max-width:900px\)[\s\S]*?\.command-heading\{flex-basis:100%\}/.test(CSS),
    'the hero heading no longer takes the full row once the mode chip is gone');
  assert(/@media\(max-width:640px\)[\s\S]*?\.command-hero>\.panel-head \.btn\{[^}]*min-height:44px/.test(CSS));
  assert(/@media\(max-width:640px\)[\s\S]*?\.overview-tab\{[^}]*flex:1[^}]*min-width:0/.test(CSS));
});

ok('the top bar has four explicit jobs instead of a loose chip row', () => {
  for (const name of ['topbar-identity', 'topbar-system', 'topbar-account',
    'topbar-actions']) assert(HTML.includes(`class="${name}"`), name + ' is missing');
  assert(HTML.includes('id="modeChip"'));
  assert(HTML.includes('id="riskChip"'));
  assert(HTML.includes('id="btnHalt"'));
  assert(/\.topbar-account\{[^}]*border:1px solid var\(--border-soft\)/.test(CSS));
});

ok('long overview explanation is collapsed behind optional detail', () => {
  assert(WEATHER.includes('class="mission-detail"'));
  assert(WEATHER.includes('<summary>Universe details</summary>'));
  assert(!WEATHER.includes('so quiet days are normal'));
  assert(!SHELL.includes('Nothing is open right now, and nothing needs you'));
  /* MODE_SHORT existed to stop the hero's sentence carrying the long mode
     note. The hero has no sentence now, so the short form has no reader at
     all — a stronger version of the same property. The chip states the mode
     and its title carries the long note. */
  assert(!OPS.includes('MODE_SHORT'), 'the hero grew a mode sentence again');
  assert(OPS.includes('MODE_NOTE'), 'the mode chip lost its explanation');
});

console.log('\n  ' + passed + ' passed');
