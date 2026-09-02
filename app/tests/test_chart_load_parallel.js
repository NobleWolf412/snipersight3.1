/* Loading one chart cost four round trips when it needed one.

   A symbol switch fires ten requests together — the bars plus nine marker
   layers — and then used to issue three more one at a time, each waiting on
   the last to come back: the draft plan, the operator's open positions, and
   the venue fee config. None of the three reads either of the others, and
   none reads the ten. The serialisation bought nothing but its own latency,
   on the interaction the operator performs most.

   These pin the fix by SHAPE rather than by timing, because the suite reads
   source text and cannot observe the network. The shape is the whole claim:
   a request that is started before the ten-way Promise.all is in flight
   alongside it, and one started after it is not.

   The seq guards are pinned here too, and they are the reason this fix is
   only a re-ordering of the STARTS. `loadSeq` is what stops a slow response
   for the previous symbol painting itself under the new symbol's name — the
   worst failure this file can produce, per chart.js's own comment. Moving an
   await or an assignment across a guard would reintroduce it, so the tests
   below assert those stayed put. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const CHART = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'chart.js'), 'utf8');

let passed = 0;
function ok(name, fn) {
  fn();
  passed++;
  console.log('  ok  ' + name);
}

const startDraft = CHART.indexOf('const draftReq = api(');
const startOpen = CHART.indexOf('const openReq = api(');
const startCfg = CHART.indexOf('const cfgReq = api(');
const fanout = CHART.indexOf('res = await Promise.all([');
const awaitDraft = CHART.indexOf('await draftReq');
const awaitOpen = CHART.indexOf('await openReq');
const awaitCfg = CHART.indexOf('await cfgReq');

ok('all three trailing reads exist as named promises', () => {
  assert(startDraft > 0, 'the draft request is not started as a named promise');
  assert(startOpen > 0, 'the open-positions request is not started as a named promise');
  assert(startCfg > 0, 'the fee-config request is not started as a named promise');
});

ok('all three are started BEFORE the ten-way fan-out', () => {
  assert(fanout > 0, 'the ten-way Promise.all is gone — this test is measuring nothing');
  for (const [what, at] of [['draft', startDraft], ['open positions', startOpen],
                            ['fee config', startCfg]]) {
    assert(at < fanout,
      `the ${what} request is issued after the ten-way fan-out, so it waits ` +
      'for all ten to settle before it even leaves — the exact serialisation ' +
      'this fix removed');
  }
});

ok('none of the three awaits another before starting', () => {
  /* The failure this catches is subtle and reads as correct: keeping the
     starts up here but writing `const dr = await draftReq;` above the
     `openReq` start would put them back in series while every name still
     looks parallel. */
  const region = CHART.slice(startDraft, fanout);
  assert(!/\bawait\b/.test(region),
    'something is awaited between the three starts and the fan-out — they ' +
    'are back in series, whatever the variable names suggest');
});

ok('a rejection landing before its await cannot go unhandled', () => {
  /* Starting a request early means it can reject while the code is still
     inside the fan-out. Without a handler attached at creation that surfaces
     as an unhandledrejection, which is noise at best and a crashed handler
     at worst. This is NOT the error handling — the real catches are below. */
  const region = CHART.slice(startDraft, fanout);
  for (const name of ['draftReq', 'openReq', 'cfgReq']) {
    assert(new RegExp(name + '\\.catch\\(').test(region),
      `${name} has no handler attached where it is created — a rejection ` +
      'arriving before its await escapes as an unhandled rejection');
  }
});

ok('every await stayed on its own side of the guards', () => {
  assert(awaitDraft > fanout && awaitOpen > fanout,
    'the draft or positions await moved above the fan-out — those two are ' +
    'read inside the block the fan-out failure clears');
  const guardBeforeCfg = CHART.lastIndexOf('if(seq !== loadSeq)', awaitCfg);
  assert(guardBeforeCfg > awaitOpen,
    'the fee config is no longer awaited after a seq guard — a load that ' +
    'lost the race would apply the previous market\'s fees to this chart');
});

ok('the fee config still keeps its previous value on failure', () => {
  /* Blanking it would be worse than the stale value it replaces: spot fees
     on a perp chart flip the sign of the net-R decision, and chart.js says
     so where cfg is read. `cfg` must be assigned only by a resolved await,
     never reset in the catch. */
  const at = CHART.indexOf('cfg = await cfgReq');
  const tail = CHART.slice(at, at + 400);
  const catchAt = tail.indexOf('}catch');
  assert(catchAt > 0, 'the fee-config await lost its catch — a venue lookup ' +
    'failure now takes down the whole chart load');
  assert(!/cfg\s*=/.test(tail.slice(catchAt)),
    'the catch reassigns cfg — on a failed lookup the ticket must keep the ' +
    'value it had, not blank it');
});

console.log('\n  ' + passed + ' passed');
