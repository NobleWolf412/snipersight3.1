/* Home's trades card: live orders own it; recent closes only fold out when
   nothing is open. Runs the real homeTrades() source against stub helpers,
   because the question is behaviour (which list shows when), not wording. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const APP = fs.readFileSync(path.join(__dirname, '..', 'static', 'cockpit', 'app.js'), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (error) { console.log('  FAIL ' + name + '\n       ' + error.message); process.exitCode = 1; }
}

function load(open) {
  const start = APP.indexOf('function homeTrades(');
  assert(start >= 0, 'homeTrades() is missing from cockpit/app.js');
  const end = APP.indexOf('\n}\n', start) + 2;
  const sandbox = {
    recentClosesOpen: open,
    empty: (title) => `<empty>${title}</empty>`,
    tradeTable: (rows) => `<table>${rows.map((r) => r.symbol).join(',')}</table>`,
  };
  vm.createContext(sandbox);
  vm.runInContext(APP.slice(start, end) + '\nthis.homeTrades = homeTrades;', sandbox);
  return sandbox.homeTrades;
}

const open = [{ symbol: 'BTCUSDT' }];
const closed = [{ symbol: 'ETHUSDT' }, { symbol: 'SOLUSDT' }];

console.log('home trades card');

ok('open trades are the whole card; recent closes are not shown', () => {
  const html = load(false)(open, closed);
  assert.strictEqual(html, '<table>BTCUSDT</table>');
});

ok('with nothing open, recent closes fold out of the same card', () => {
  const html = load(false)([], closed);
  assert(html.includes('Nothing open right now'));
  assert(/<details class="recent-closes" id="recent-closes">/.test(html));
  assert(html.includes('Recent closes (2)'));
  assert(html.includes('<table>ETHUSDT,SOLUSDT</table>'));
  assert(html.includes('href="#journal"'));
});

ok('an opened list stays open across the background refresh', () => {
  assert(/<details class="recent-closes" id="recent-closes" open>/.test(load(true)([], closed)));
});

ok('no closes yet: just the empty state, no empty fold-out', () => {
  const html = load(false)([], []);
  assert(html.includes('Nothing open right now'));
  assert(!html.includes('<details'));
});

ok('the separate Recent closes card is gone from Home', () => {
  const home = APP.slice(APP.indexOf('async function home('), APP.indexOf('function botActivity('));
  assert(!home.includes('<h2>Recent closes</h2>'));
  assert(home.includes('homeTrades(data.positions,data.recent)'));
});

console.log('\n  ' + passed + ' passed');
