/* Tests for the order-ticket arithmetic.
   Run: node tests/test_ticket_math.js   (from app/)

   This is the code that decides how big a trade is, so it is tested for the
   cases that actually cost money: inverted stops, shorts, fee-dominated
   scalps, and sizing that quietly exceeds the account.
*/
const assert = require('assert');
const {ticketMath} = require('../static/ticket-math.js');

// mirrors GET /api/trade-config, which reads engine/risk.py + engine/costs.py
const CFG = {
  risk_pct: 0.02, max_leverage: 1, max_total_risk_pct: 0.04,
  max_concurrent: 2, daily_loss_pct: 0.06,
  cost: {maker_rate: 0.0040, taker_rate: 0.0060, slippage_atr: 0.05},
};
const EQ = 10000;
const near = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;

let pass = 0;
function t(name, fn){
  try{ fn(); console.log('  ok   ' + name); pass++; }
  catch(e){ console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('ticket math');

t('long: risk, reward and gross R:R', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG});
  assert.ok(m.ok);
  assert.ok(near(m.riskPerUnit, 10));
  assert.ok(near(m.rewardPerUnit, 30));
  assert.ok(near(m.rrGross, 3));
});

t('short: direction flips the arithmetic, not the sign convention', () => {
  const m = ticketMath({dir: 'SHORT', entry: 100, tp: 70, sl: 110, equity: EQ, cfg: CFG});
  assert.ok(m.ok);
  assert.ok(near(m.riskPerUnit, 10), 'risk must stay positive on a short');
  assert.ok(near(m.rewardPerUnit, 30));
  assert.ok(near(m.rrGross, 3));
});

t('sizing spends exactly the configured risk budget', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG});
  assert.ok(near(m.riskUsd, 200), 'risk = 2% of 10,000');
  assert.ok(near(m.size, 20), 'size = 200 / 10 per unit');
  assert.ok(near(m.notional, 2000));
  // the whole point: losing at the stop costs exactly the risk budget
  assert.ok(near(m.size * m.riskPerUnit, m.riskUsd));
});

t('stop on the wrong side is refused, not silently negated', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 110, equity: EQ, cfg: CFG});
  assert.ok(!m.ok);
  assert.ok(/BELOW entry/.test(m.errors.join(' ')));
  assert.strictEqual(m.size, null, 'must not size an invalid trade');
});

t('short with stop below entry is refused', () => {
  const m = ticketMath({dir: 'SHORT', entry: 100, tp: 70, sl: 90, equity: EQ, cfg: CFG});
  assert.ok(!m.ok);
  assert.ok(/ABOVE entry/.test(m.errors.join(' ')));
});

t('target on the wrong side is refused', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 95, sl: 90, equity: EQ, cfg: CFG});
  assert.ok(!m.ok);
  assert.ok(/ABOVE entry/.test(m.errors.join(' ')));
});

t('missing or zero prices produce an error, never a NaN', () => {
  for(const bad of [{entry: null}, {tp: 0}, {sl: NaN}, {entry: -5}]){
    const m = ticketMath(Object.assign(
      {dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG}, bad));
    assert.ok(!m.ok, JSON.stringify(bad));
    assert.strictEqual(m.size, null);
  }
});

t('fees are charged on notional, so a tight stop is fee-dominated', () => {
  // 0.1% stop on a 60k asset: structurally tight, but 1% round-trip fees
  // dwarf it. This is the case that sank the intraday book in backtest.
  const m = ticketMath({dir: 'LONG', entry: 60000, tp: 60180, sl: 59940,
                        equity: EQ, cfg: CFG});
  assert.ok(m.ok);
  assert.ok(near(m.rrGross, 3), 'gross ratio still looks like a 3R trade');
  assert.ok(m.rrNet < 0, 'after fees it is a guaranteed loser: ' + m.rrNet);
  assert.ok(m.notes.some(n => /risks more than it stands to make/.test(n)));
});

t('fee maths matches the engine cost profile exactly', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG});
  assert.ok(near(m.fees, m.notional * (CFG.cost.maker_rate + CFG.cost.taker_rate)));
  assert.ok(near(m.netUsd, m.rewardPerUnit * m.size - m.fees));
  assert.ok(near(m.rrNet, m.netUsd / m.riskUsd));
});

t('a wide stop keeps net R:R close to gross', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 140, sl: 80, equity: EQ, cfg: CFG});
  assert.ok(m.rrNet > 1.8 && m.rrNet < m.rrGross,
            'net ' + m.rrNet + ' vs gross ' + m.rrGross);
});

t('notional above buying power is flagged at 1x', () => {
  // a 0.1% stop needs a huge position to risk 2%, far past a spot account
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 99.9, equity: EQ, cfg: CFG});
  assert.ok(m.notional > EQ);
  assert.ok(m.notes.includes('NOTIONAL_EXCEEDS_BUYING_POWER'));
});

t('leverage raises buying power and clears the flag', () => {
  // 0.5 stop -> size 400 -> notional 40,000: over a 10,000 spot account,
  // comfortably inside a 100,000 buying power at 10x.
  const args = {dir: 'LONG', entry: 100, tp: 130, sl: 99.5, equity: EQ};
  const spot = ticketMath(Object.assign({cfg: CFG}, args));
  assert.ok(near(spot.notional, 40000), 'notional ' + spot.notional);
  assert.ok(spot.notes.includes('NOTIONAL_EXCEEDS_BUYING_POWER'), 'flagged at 1x');

  const lev = ticketMath(Object.assign(
    {cfg: Object.assign({}, CFG, {max_leverage: 10})}, args));
  assert.ok(!lev.notes.includes('NOTIONAL_EXCEEDS_BUYING_POWER'), 'clear at 10x');
  assert.ok(near(lev.size, spot.size), 'leverage changes the limit, not the size');
});

t('no equity means ratios but deliberately no position size', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: null, cfg: CFG});
  assert.ok(m.ok);
  assert.ok(near(m.rrGross, 3));
  assert.strictEqual(m.size, null, 'a guessed size is worse than a blank one');
  assert.strictEqual(m.notional, null);
});

/* ---- per-trade risk override ----
   Operator directive: "if I decide to risk more for one particular trade it
   shouldn't affect any others." These tests hold that line. */

t('default sizing is engine-owned and labelled as such', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG});
  assert.strictEqual(m.riskSource, 'engine');
  assert.ok(near(m.riskUsd, 200));
  assert.ok(near(m.riskPctEffective, 0.02));
});

t('override replaces the risk budget for this trade only', () => {
  const args = {dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG};
  const m = ticketMath(Object.assign({riskUsdOverride: 350}, args));
  assert.strictEqual(m.riskSource, 'operator');
  assert.ok(near(m.riskUsd, 350));
  assert.ok(near(m.size, 35), 'size follows the override: 350 / 10');
  assert.ok(near(m.riskPctEffective, 0.035));

  // the very next call, with no override, must be untouched
  const after = ticketMath(args);
  assert.strictEqual(after.riskSource, 'engine');
  assert.ok(near(after.riskUsd, 200), 'the override leaked into a later trade');
  assert.ok(near(after.size, 20));
});

t('override never mutates the shared config object', () => {
  const before = JSON.stringify(CFG);
  ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ,
              cfg: CFG, riskUsdOverride: 900});
  assert.strictEqual(JSON.stringify(CFG), before, 'cfg was mutated');
});

t('R:R is unchanged by how much you risk', () => {
  const args = {dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: CFG};
  const a = ticketMath(args);
  const b = ticketMath(Object.assign({riskUsdOverride: 700}, args));
  assert.ok(near(a.rrGross, b.rrGross), 'size must not change the ratio');
  assert.ok(near(a.rrNet, b.rrNet), 'fees scale with notional, so net R holds too');
});

t('override above the total open-risk budget is flagged', () => {
  // 4% total cap on 10,000 = 400
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ,
                        cfg: CFG, riskUsdOverride: 450});
  assert.ok(m.ok, 'still a valid trade, just a flagged one');
  assert.ok(m.notes.includes('RISK_EXCEEDS_TOTAL_BUDGET'));
});

t('override inside the budget is not flagged', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ,
                        cfg: CFG, riskUsdOverride: 350});
  assert.ok(!m.notes.includes('RISK_EXCEEDS_TOTAL_BUDGET'));
});

t('override past the daily halt is flagged too', () => {
  // 6% daily halt on 10,000 = 600: one trade that could trip the kill switch
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ,
                        cfg: CFG, riskUsdOverride: 700});
  assert.ok(m.notes.includes('RISK_EXCEEDS_DAILY_HALT'));
});

t('junk overrides fall back to the engine default, never to NaN', () => {
  for(const bad of [0, -50, NaN, Infinity, '300', null, undefined]){
    const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                          equity: EQ, cfg: CFG, riskUsdOverride: bad});
    assert.ok(near(m.riskUsd, 200), 'bad override: ' + String(bad));
    assert.strictEqual(m.riskSource, 'engine');
  }
});

console.log(`\n${pass} passed`);
