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

ok('the command brief leads with narrative, instruments, and system pulse', () => {
  const brief = HTML.indexOf('class="panel panel-accent bracket command-hero"');
  const missions = HTML.indexOf('class="panel floating mb-panel"');
  const risk = HTML.indexOf('id="budgetPanel"');
  assert(brief > 0, 'command brief is missing');
  assert(missions > brief, 'mission carousel must follow the brief');
  assert(risk > missions, 'risk mechanics must support, not precede, the active book');
  for (const id of ['commandNarrative', 'commandMode', 'commandScanner',
    'commandData', 'commandExposure']) assert(HTML.includes(`id="${id}"`), id + ' is missing');
});

ok('command state is painted from the operations read model', () => {
  assert(OPS.includes("api('/api/operations')"));
  assert(OPS.includes('opportunities.narrative'));
  assert(OPS.includes('scanner.eligible_markets'));
  assert(OPS.includes('a.open_positions'));
  assert(OPS.includes("$('commandData').className"), 'data degradation has no visible tone');
});

ok('the carousel exposes position and a route to the comparison surface', () => {
  assert(HTML.includes('id="mbPosition"'));
  assert(/href="#opportunities">View all setups/.test(HTML));
  assert(/position: 'mbPosition'/.test(SHELL));
  assert(/position\.textContent = st\.cards\.length/.test(SHELL));
});

ok('active trade cards are semantic and have one dominant management action', () => {
  assert(SHELL.includes("document.createElement('article')"));
  assert(SHELL.includes('>Manage position</button>'));
  assert(/mc\.mission \.mc-acts \.btn-primary\{grid-column:1\/-1;order:-1/.test(CSS));
  assert(SHELL.includes('>Review setup</button>'));
});

ok('the command brief and pulse collapse for mobile', () => {
  assert(/@media\(max-width:900px\)[\s\S]*?\.command-pulse\{grid-template-columns:1fr\}/.test(CSS));
  assert(/@media\(max-width:640px\)[\s\S]*?\.command-hero>\.panel-head \.btn\{[^}]*min-height:44px/.test(CSS));
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
  assert(OPS.includes('MODE_SHORT'));
});

console.log('\n  ' + passed + ' passed');
