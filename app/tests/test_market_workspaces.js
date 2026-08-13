const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const MARKETS = S('markets.js');
const STOCKS = S('stocks.js');
const SHELL = S('shell.js');
const SSDATA = S('ssdata.js');
const OPERATIONS = S('operations.js');
const OPPORTUNITIES = S('opportunities.js');
const TRADE_WORKSPACE = S('trade-workspace.js');
const COCKPIT = S('cockpit-workspaces.js');
const MODE = S('mode-control.js');
const CSS = S('ss.css');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('market workspaces');

ok('first-run chooser names two separate market workspaces', () => {
  assert(HTML.includes('id="marketGate"'));
  assert(HTML.includes('data-market-choice="crypto"'));
  assert(HTML.includes('data-market-choice="stocks"'));
  assert(HTML.includes('Each workspace keeps its own scanner, evidence, positions and results.'));
  assert(HTML.includes('id="cryptoApp"') && HTML.includes('id="stocksApp"'));
});

ok('choice persists while existing operators safely default to crypto', () => {
  assert(MARKETS.includes("const KEY = 'ss.market-workspace.v1'"));
  assert(/localStorage\.setItem\(KEY, value\)/.test(MARKETS));
  assert(MARKETS.includes("read('ss.seen-intro') === '1'"));
  assert(MARKETS.includes("remember('crypto')"));
  assert(MARKETS.includes("dispatchEvent(new CustomEvent('ss:market-change'"));
});

ok('all recurring crypto authorities stop while Stocks is selected', () => {
  const refresh = SHELL.slice(SHELL.indexOf('async function refresh()'),
    SHELL.indexOf('async function refresh()') + 500);
  assert(refresh.includes("SSMarkets.current() !== 'crypto'"));
  assert(SHELL.includes("event.detail.market === 'crypto'"));
  for(const [name, source] of Object.entries({OPERATIONS, OPPORTUNITIES,
      TRADE_WORKSPACE, COCKPIT, MODE})){
    assert(source.includes("SSMarkets.current() !== 'crypto'"),
      `${name} keeps reading the crypto book behind Stocks`);
    assert(source.includes("market === 'crypto'"),
      `${name} does not refresh when Crypto is restored`);
  }
  assert(SSDATA.includes('!marketAllows(e.path)'),
    'subscribed crypto feeds continue polling behind Stocks');
  assert(SSDATA.includes("path.startsWith('/api/stocks/')"),
    'the shared scheduler has no stock namespace boundary');
});

ok('stocks has its own focused jobs and never claims a scanner exists', () => {
  for(const view of ['overview', 'setups', 'trade', 'performance', 'system'])
    assert(HTML.includes(`data-stock-view="${view}"`), `${view} stock view missing`);
  assert(HTML.includes('No stock scanner is running yet.'));
  assert(HTML.includes('Live orders disabled'));
  assert(HTML.includes('Crypto outcomes, samples and strategy grades are intentionally excluded.'));
});

ok('stock UI reads server authority and only performs credential or verification writes', () => {
  assert(STOCKS.includes("SSData.get('/api/stocks/status'"));
  assert(STOCKS.includes("fetch('/api/credentials'"));
  assert(STOCKS.includes("fetch('/api/stocks/connections/test'"));
  for(const cryptoPath of ['/api/overview', '/api/operations', '/api/manual/arm', '/api/scan'])
    assert(!STOCKS.includes(cryptoPath), `stock workspace reaches crypto path ${cryptoPath}`);
});

ok('provider forms request only the credentials each stock authority needs', () => {
  assert(HTML.includes('data-stock-cred="alpaca-paper|api_key"'));
  assert(HTML.includes('data-stock-cred="alpaca-paper|api_secret"'));
  assert(HTML.includes('data-stock-cred="massive-stocks|api_key"'));
  assert(!HTML.includes('data-stock-cred="massive-stocks|api_secret"'));
});

ok('stock workspace and chooser have phone layouts', () => {
  assert(/@media \(max-width:640px\)\{[\s\S]*?\.market-choices\{grid-template-columns:1fr\}/.test(CSS));
  assert(/@media \(max-width:640px\)\{[\s\S]*?\.stock-summary\{grid-template-columns:1fr\}/.test(CSS));
  assert(/\.stock-nav\{[^}]*overflow-x:auto/.test(CSS));
});

console.log('\n  ' + passed + ' passed');
