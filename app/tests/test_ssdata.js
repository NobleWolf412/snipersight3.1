/* SSData is the answer to a bug that had already been fixed once and came back.

   Five modules fetched /api/overview on five unaligned clocks, so two panels on
   one screen could legitimately show two different moments — and did: Command
   reporting one universe size beside Market Weather reporting another. shell.js
   still carries the comment from the FIRST time that was fixed, at one call
   site. A per-site fix cannot retire a per-site bug, so the guarantee has to
   live somewhere every reader passes through.

   These tests pin the guarantees the panels now depend on:
     · concurrent readers of one path share ONE request and ONE payload object
     · a write invalidates for every reader, not just the writer
     · a failure keeps the last good payload rather than blanking the screen
     · nobody polls a hidden tab
     · the cache cannot grow without bound

   The last one is not hypothetical. Routing the cursored /api/console poll
   through this layer minted a fresh entry twice a second, every one of them
   unreachable forever, and it took a live _stats() read to notice. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const SRC = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'ssdata.js'), 'utf8');

let passed = 0;
function ok(name, fn) {
  return fn().then(
    () => { console.log('  ok   ' + name); passed++; },
    e => { console.log('  FAIL ' + name + '\n       ' + (e && e.message)); process.exitCode = 1; });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* A fresh module instance per test: SSData holds process-wide cache state, and
   tests that share it would pass or fail depending on their order. */
function load() {
  const calls = [];
  let hidden = false;
  const handlers = {};
  const fakeWindow = {};
  const sandbox = {
    window: fakeWindow,
    document: {
      get hidden() { return hidden; },
      addEventListener: (k, fn) => { handlers[k] = fn; },
    },
    fetch: async (url, opts) => {
      const c = {url, opts, at: Date.now()};
      calls.push(c);
      const plan = sandbox.plan[url];
      await sleep(plan && plan.delay ? plan.delay : 5);
      if (plan && plan.fail) throw new Error('boom');
      return {ok: plan && plan.status ? plan.status < 400 : true,
              status: (plan && plan.status) || 200,
              json: async () => (plan && plan.body !== undefined
                ? plan.body : {v: (plan ? ++plan.n : ++sandbox.n)})};
    },
    console,
    setInterval, clearInterval, setTimeout, clearTimeout, Date,
    plan: {}, n: 0,
  };
  new Function('window', 'document', 'fetch', 'console', 'setInterval',
               'clearInterval', 'setTimeout', 'clearTimeout', 'sandbox', SRC)
    (sandbox.window, sandbox.document, sandbox.fetch, sandbox.console,
     sandbox.setInterval, sandbox.clearInterval, sandbox.setTimeout,
     sandbox.clearTimeout, sandbox);
  return {D: fakeWindow.SSData, calls, sandbox,
          setHidden: v => { hidden = v; }, handlers};
}

(async () => {
  console.log('ssdata');

  await ok('concurrent readers share one request and one payload', async () => {
    const {D, calls} = load();
    const all = await Promise.all([D.get('/a', 0), D.get('/a', 0),
                                   D.get('/a', 0), D.get('/a', 0)]);
    assert.strictEqual(calls.length, 1, 'four readers made ' + calls.length + ' requests');
    // identity, not equality: two panels holding one object cannot disagree
    assert(all.every(x => x === all[0]), 'readers got different payload objects');
  });

  await ok('a read inside the window is served from cache', async () => {
    const {D, calls} = load();
    await D.get('/a', 1000);
    await D.get('/a', 1000);
    assert.strictEqual(calls.length, 1, 'the cached read still hit the network');
  });

  await ok('maxAge 0 always hits the network', async () => {
    // shell.js relies on this: refresh() is also the repaint after Apply and
    // after a scan, and must never show the state just changed away from.
    const {D, calls} = load();
    await D.get('/a', 0);
    await D.get('/a', 0);
    assert.strictEqual(calls.length, 2, 'a forced read was served from cache');
  });

  await ok('a write invalidates for every reader, not just the writer', async () => {
    const {D, calls} = load();
    await D.get('/a', 60000);
    D.invalidate('/a');
    await D.get('/a', 60000);
    assert.strictEqual(calls.length, 2, 'invalidate did not drop the cached copy');
  });

  await ok('invalidate covers a path and its query variants', async () => {
    const {D, calls} = load();
    await D.get('/a?limit=200', 60000);
    await D.get('/a?limit=500', 60000);
    D.invalidate('/a');
    await D.get('/a?limit=200', 60000);
    await D.get('/a?limit=500', 60000);
    assert.strictEqual(calls.length, 4, 'query variants survived invalidation');
  });

  await ok('every request is no-store', async () => {
    // the endpoints all report a live record; freshness is this layer's call
    const {D, calls} = load();
    await D.get('/a', 0);
    assert.strictEqual(calls[0].opts && calls[0].opts.cache, 'no-store');
  });

  await ok('a failure keeps the last good payload and reports the error', async () => {
    const {D, sandbox} = load();
    const first = await D.get('/a', 0);
    const seen = [];
    D.subscribe('/a', (d, e) => seen.push({d, e}), 0);
    sandbox.plan['/a'] = {fail: true};
    await D.get('/a', 0).catch(() => {});
    const last = seen[seen.length - 1];
    assert(last.e, 'subscriber was not told about the failure');
    assert.strictEqual(last.d, first,
      'the last good payload was dropped — the panel blanks instead of going stale');
  });

  await ok('subscribers are pushed the same object the reader got', async () => {
    const {D} = load();
    const got = [];
    D.subscribe('/a', d => { if (d) got.push(d); }, 0);
    const direct = await D.get('/a', 0);
    assert(got.length, 'subscriber never fired');
    assert.strictEqual(got[got.length - 1], direct,
      'a subscriber and a direct reader hold different objects');
  });

  await ok('a late subscriber paints from the payload already on screen', async () => {
    const {D, calls} = load();
    const early = await D.get('/a', 60000);
    let late = null;
    D.subscribe('/a', d => { late = d; }, 0);
    await sleep(1);
    assert.strictEqual(late, early, 'the late panel fetched its own different answer');
    assert.strictEqual(calls.length, 1, 'subscribing re-fetched a path already cached');
  });

  await ok('nothing polls a hidden tab', async () => {
    const {D, calls, setHidden} = load();
    D.subscribe('/a', () => {}, 20);
    await sleep(40);
    const whileVisible = calls.length;
    assert(whileVisible >= 1, 'the scheduler never ran while visible');
    setHidden(true);
    const mark = calls.length;
    await sleep(1200);
    assert.strictEqual(calls.length, mark, 'a hidden tab kept polling');
  });

  await ok('the last unsubscribe stops the polling', async () => {
    const {D, calls} = load();
    const off = D.subscribe('/a', () => {}, 20);
    await sleep(40);
    off();
    const mark = calls.length;
    await sleep(1200);
    assert.strictEqual(calls.length, mark, 'polling continued with no subscribers left');
  });

  await ok('the cache does not grow without bound for one endpoint', async () => {
    /* The /api/console regression: a cursored URL is a NEW key every call, so
       each poll left an entry nothing could ever hit again. Cursored streams
       must not be routed through here — asserted at the call site in shell.js
       by test_no_cursor_paths below; here we only pin that distinct paths are
       distinct entries, which is what makes that mistake unbounded. */
    const {D} = load();
    for (let i = 0; i < 5; i++) await D.get('/c?offset=' + i, 0);
    assert.strictEqual(D._stats().length, 5);
  });

  await ok('cold entries are evicted, subscribed ones never are', async () => {
    /* Chart data keys on symbol AND timeframe, so browsing the universe walks
       hundreds of distinct keys holding thousands of candles each. Cap them —
       but never drop a path something on screen is still subscribed to. */
    const {D} = load();
    D.subscribe('/pinned', () => {}, 0);
    await D.get('/pinned', 0);
    for (let i = 0; i < 90; i++) await D.get('/candles?s=' + i, 0);
    const stats = D._stats();
    assert(stats.length <= 60, 'cache grew past the cap: ' + stats.length);
    assert(stats.some(e => e.path === '/pinned'),
           'an entry with a live subscriber was evicted from under it');
  });

  await ok('the scan-state poll does NOT go through the cache', async () => {
    /* This pinned `/api/console?offset=` until 2026-08-13, when the backend
       console left the cockpit as developer detail. The console was a CURSORED
       stream and caching it minted an entry per call that could never be hit —
       an unbounded map growing twice a second.

       The poll that replaced it must stay uncached for a different reason, and
       the reason is worth stating because it is the one that survives: this is
       a CONTROL'S OWN LIVENESS. `/api/scan/state` says whether Check-now may be
       pressed, and a cached answer is a button that lies about whether a scan
       is already running. Two different faults, one rule. */
    const shell = fs.readFileSync(
      path.join(__dirname, '..', 'static', 'shell.js'), 'utf8');
    // Anchored on the CALL, not the path: the path also appears in the comment
    // above explaining why this poll exists, and slicing around that window
    // read the prose instead of the code.
    const i = shell.indexOf("fetch('/api/scan/state'");
    assert(i > 0, 'the scan-state poll was renamed');
    const around = shell.slice(i - 400, i + 200);
    assert(!/api\('\/api\/scan\/state/.test(around)
           && !/SSData\.get\('\/api\/scan\/state/.test(around),
      'the scan-state poll is routed through the cache — the Check-now button ' +
      'would report a scan that already finished, or refuse one that has not started');
    assert(/cache: *'no-store'/.test(around), 'the scan-state fetch lost no-store');
  });

  /* ── How old is what I am looking at? ──────────────────────────────────
     This layer keeps the last good payload on screen when a fetch fails,
     which is right, and it justified that by pointing at the shell's health
     chip to report the staleness. For that to be honest the age has to be
     the age of the DATA, and `at` used to be stamped in the failure branch
     too — so it advanced while every request failed. On loopback the failure
     branch is unreachable; over a tunnel or on cellular it is the common
     case, and the app would have shown hour-old prices with a confident
     face. */

  await ok('a failure does not make the data on screen look younger', async () => {
    const {D, sandbox} = load();
    await D.get('/a', 0);
    const fresh = D._stats().find(e => e.path === '/a').ageMs;
    await sleep(30);
    sandbox.plan['/a'] = {fail: true};
    await D.get('/a', 0).catch(() => {});
    const after = D._stats().find(e => e.path === '/a').ageMs;
    assert(after >= fresh + 25,
      'the age reset on a FAILED fetch (' + fresh + ' -> ' + after + '), so a ' +
      'stale panel would report itself as current');
  });

  await ok('unreachable reads as offline, not as a bad answer', async () => {
    /* The operator answers these two differently: one means walk out of the
       lift, the other means the desk needs attention. */
    const {D, sandbox} = load();
    D.subscribe('/a', () => {}, 5000);
    await sleep(20);
    sandbox.plan['/a'] = {fail: true};       // fetch() itself rejects
    await D.get('/a', 0).catch(() => {});
    assert.strictEqual(D.health().state, 'offline', 'a dead tunnel read as a server fault');
  });

  await ok('a bad answer reads as a server fault, not as offline', async () => {
    const {D, sandbox} = load();
    D.subscribe('/a', () => {}, 5000);
    await sleep(20);
    sandbox.plan['/a'] = {status: 500};      // something answered, badly
    await D.get('/a', 0).catch(() => {});
    assert.strictEqual(D.health().state, 'server', 'a 500 read as "no connection"');
  });

  await ok('everything current reads as ok', async () => {
    const {D} = load();
    D.subscribe('/a', () => {}, 5000);
    await sleep(20);
    assert.strictEqual(D.health().state, 'ok');
    assert.strictEqual(D.health().failing, 0);
  });

  await ok('health ignores paths nothing on screen depends on', async () => {
    /* A chart the operator browsed away from must not be able to put the
       whole cockpit into a failure state. */
    const {D, sandbox} = load();
    sandbox.plan['/gone'] = {fail: true};
    await D.get('/gone', 0).catch(() => {});
    assert.strictEqual(D.health().state, 'ok', 'an unsubscribed path raised an alarm');
  });

  await ok('staleness reports the OLDEST failing panel, not the newest', async () => {
    /* The worst number on screen is the one that can mislead. */
    const {D, sandbox} = load();
    D.subscribe('/old', () => {}, 5000);
    await sleep(60);
    D.subscribe('/new', () => {}, 5000);
    await sleep(20);
    sandbox.plan['/old'] = {fail: true};
    sandbox.plan['/new'] = {fail: true};
    await Promise.all([D.get('/old', 0).catch(() => {}), D.get('/new', 0).catch(() => {})]);
    const h = D.health();
    assert.strictEqual(h.failing, 2);
    const newest = D._stats().find(e => e.path === '/new').ageMs;
    assert(h.staleMs > newest,
      'staleMs followed the freshest panel (' + h.staleMs + ' vs ' + newest + ')');
  });

  await ok('the shell does not keep its own copy of the age', async () => {
    /* §8, one authority per number. shell.js stamped its own lastGoodAt in
       its own refresh loop, which drifted the moment anything else fetched —
       the exact class of bug this file exists to retire. */
    const shell = fs.readFileSync(
      path.join(__dirname, '..', 'static', 'shell.js'), 'utf8');
    const code = shell.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    assert(!/lastGoodAt\s*=/.test(code),
      'shell.js is stamping its own lastGoodAt again instead of reading ' +
      'SSData.health()');
    assert(/SSData\.health\(\)/.test(code),
      'shell.js stopped reading the age from the layer that owns it');
  });

  console.log('\n' + passed + ' passed');
  /* SSData starts a scheduler on load and a browser module has no reason to
     offer a teardown, so the interval holds the event loop open and node would
     never exit. Leave explicitly, after letting stdout drain. */
  await new Promise(r => setTimeout(r, 20));
  process.exit(process.exitCode || 0);
})();
