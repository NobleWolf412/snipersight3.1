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

t('buying power follows the CHOSEN leverage, not the venue ceiling', () => {
  /* This test used to assert that raising `max_leverage` to 10 cleared the
     flag. That was the old model, and it was quietly optimistic: it sized
     against headroom the venue ALLOWS rather than margin the operator has
     actually chosen to post, so a trade needing 40,000 of margin on a 10,000
     account looked fine merely because the venue permits 10x somewhere.

     Now the operator picks. Raising the venue ceiling changes nothing on its
     own; raising the dial is what posts less margin and frees the headroom. */
  const args = {dir: 'LONG', entry: 100, tp: 130, sl: 99.5, equity: EQ};
  const spot = ticketMath(Object.assign({cfg: CFG}, args));
  assert.ok(near(spot.notional, 40000), 'notional ' + spot.notional);
  assert.ok(spot.notes.includes('NOTIONAL_EXCEEDS_BUYING_POWER'), 'flagged at 1x');

  const ceilingOnly = ticketMath(Object.assign(
    {cfg: Object.assign({}, CFG, {max_leverage: 10})}, args));
  assert.ok(ceilingOnly.notes.includes('NOTIONAL_EXCEEDS_BUYING_POWER'),
            'a higher venue cap alone must not clear it — nothing was posted');

  const dialled = ticketMath(Object.assign(
    {cfg: Object.assign({}, CFG, {max_leverage: 10}), leverage: 10}, args));
  assert.ok(!dialled.notes.includes('NOTIONAL_EXCEEDS_BUYING_POWER'),
            '4,000 of margin against 10,000 of equity is fine');
  assert.ok(near(dialled.size, spot.size), 'leverage changes margin, not size');
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

/* ---------- leverage and liquidation (perps) ----------

   Every liquidation figure asserted below came from the ENGINE, not from this
   file:

     python -c "from decimal import Decimal as D; from engine import venues;
                print(venues.liquidation_price(D('100'), D(10), 'LONG'))"
     -> 90.500

   Pinning them is the whole point. `ticket-math.js` re-implements
   `venues.liquidation_price` — normally forbidden — because the ticket must
   draw the line before any fact exists to read it from. A second
   implementation is only tolerable while something proves the two agree, and
   this is that something. Both constants it needs arrive over
   /api/trade-config, so they cannot drift independently either. */
const PERP = Object.assign({}, CFG, {
  max_leverage: 10,
  venue: {key: 'phemex-perp', kind: 'perp', allow_shorts: true,
          margin_mode: 'ISOLATED', maintenance_margin: 0.005},
  cost: {maker_rate: 0.0001, taker_rate: 0.0006, slippage_atr: 0.05},
});

t('leverage never changes size or risk — only the margin posted', () => {
  const base = {dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ, cfg: PERP};
  const at1  = ticketMath(Object.assign({}, base, {leverage: 1}));
  const at10 = ticketMath(Object.assign({}, base, {leverage: 10}));
  assert.ok(near(at1.size, at10.size), 'size must not move with leverage');
  assert.ok(near(at1.notional, at10.notional), 'nor notional');
  assert.ok(near(at1.riskUsd, at10.riskUsd), 'risk is an input, never an output');
  assert.ok(near(at1.margin, at1.notional), 'at 1x you post the whole notional');
  assert.ok(near(at10.margin, at1.notional / 10));
});

t('liquidation matches the engine formula exactly', () => {
  const L = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 95,
                        equity: EQ, cfg: PERP, leverage: 10});
  assert.ok(near(L.liquidation, 90.5), 'engine says 90.500, got ' + L.liquidation);
  const S = ticketMath({dir: 'SHORT', entry: 100, tp: 70, sl: 105,
                        equity: EQ, cfg: PERP, leverage: 10});
  assert.ok(near(S.liquidation, 109.5), 'engine says 109.500, got ' + S.liquidation);
  const two = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 95,
                          equity: EQ, cfg: PERP, leverage: 2});
  assert.ok(near(two.liquidation, 50.5), 'engine says 50.500, got ' + two.liquidation);
});

t('1x cannot be liquidated by price, so spot is inert by construction', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ,
                        cfg: PERP, leverage: 1});
  assert.strictEqual(m.liquidation, null);
  assert.strictEqual(m.blocks.length, 0);
  const spot = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90, equity: EQ,
                           cfg: CFG, leverage: 10});
  assert.strictEqual(spot.leverage, 1, 'spot must clamp to its 1x venue max');
  assert.strictEqual(spot.liquidation, null);
});

t('a stop beyond liquidation BLOCKS, it does not merely warn', () => {
  // at 10x liquidation sits at 90.5, so a stop at 85 would never be reached:
  // the exchange closes the position first and the stop is decorative.
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 85,
                        equity: EQ, cfg: PERP, leverage: 10});
  assert.ok(m.blocks.includes('STOP_BEYOND_LIQUIDATION'));
  assert.ok(!m.notes.includes('STOP_BEYOND_LIQUIDATION'),
            'a safety gate must not be filed among the advisory notes');
  const ok = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 85,
                         equity: EQ, cfg: PERP, leverage: 2});
  assert.strictEqual(ok.blocks.length, 0,
                     'liquidation at 50.5 is far below a stop at 85');
});

t('the short side blocks on the correct side of the price', () => {
  const m = ticketMath({dir: 'SHORT', entry: 100, tp: 70, sl: 115,
                        equity: EQ, cfg: PERP, leverage: 10});
  assert.ok(m.blocks.includes('STOP_BEYOND_LIQUIDATION'),
            'short liquidation is 109.5; a stop at 115 sits past it');
});

t('leverage is clamped to the venue maximum, and junk never escapes', () => {
  for(const bad of [50, 1e9, NaN, Infinity, -3, 0, '10', null, undefined]){
    const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 95,
                          equity: EQ, cfg: PERP, leverage: bad});
    assert.ok(m.leverage >= 1 && m.leverage <= 10,
              'leverage escaped its bounds for input: ' + String(bad));
  }
});

/* ---------------------- the scale-out rung ----------------------
   R is what the operator types; PRICE is what gets armed, recorded and drawn.
   The conversion is the whole reason this lives in ticket-math rather than in
   an event handler — a browser that shipped the wrong price would arm a trade
   nobody planned, and the server would accept it because it IS a valid rung.
*/

t('a rung at N R lands N stop-widths from the entry', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                        equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 1}});
  assert.ok(near(m.partial.price, 110), '1R above a 10-wide stop is 110');
  assert.strictEqual(m.partial.blocked, null);
  const two = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                          equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 2}});
  assert.ok(near(two.partial.price, 120));
});

t('the rung price carries no float noise into the record', () => {
  // 191.8 + 1 * 41.8 is 233.60000000000002 in IEEE754. The engine records
  // whatever the browser sends, so the fact would carry a price the operator
  // never chose — in a book whose whole value is being a truthful account of
  // what they decided.
  const m = ticketMath({dir: 'LONG', entry: 191.8, tp: 250, sl: 150,
                        equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 1}});
  assert.strictEqual(m.partial.price, 233.6);
  assert.strictEqual(String(m.partial.price), '233.6');
  // ...and a sub-cent token keeps every digit that matters
  const tiny = ticketMath({dir: 'LONG', entry: 0.00004, tp: 0.00009, sl: 0.00003,
                           equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 2}});
  assert.ok(near(tiny.partial.price, 0.00006, 1e-12),
            'trimming must not round a sub-cent level away');
});

t('a short rung goes DOWN from the entry', () => {
  const m = ticketMath({dir: 'SHORT', entry: 100, tp: 70, sl: 110,
                        equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 1}});
  assert.ok(near(m.partial.price, 90),
            'a short in profit at 1R is 10 BELOW entry, not above');
  assert.strictEqual(m.partial.blocked, null);
});

t('a rung measures R from the risk actually TAKEN on a held position', () => {
  // stop dragged into profit; R must still mean the entry risk of 10
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 105, holding: true,
                        originalRisk: 10, equity: EQ, cfg: CFG,
                        partial: {fraction: 0.5, atR: 2}});
  assert.ok(near(m.partial.price, 120),
            'R must not be re-derived from a stop the operator has moved');
});

t('a rung outside the bracket is blocked, not silently sent', () => {
  // 4R above a 10-wide stop is 140, past the 130 target
  const past = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                           equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 4}});
  assert.strictEqual(past.partial.blocked, 'OUTSIDE_BRACKET',
    'the engine refuses this rung — offering it spends a click to be told no');
  // and on the loss side, past the stop
  const under = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                            equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: -2}});
  assert.strictEqual(under.partial.blocked, 'OUTSIDE_BRACKET');
});

t('a rung ON the target or the stop is blocked too', () => {
  for(const atR of [3, -1]){          // exactly 130 and exactly 90
    const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                          equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR}});
    assert.strictEqual(m.partial.blocked, 'OUTSIDE_BRACKET',
      'a rung at the bracket edge settles with the whole position, never before it');
  }
});

t('a rung on the LOSS side of entry is allowed', () => {
  // de-risking: half off at -0.5R, still inside the stop
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                        equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: -0.5}});
  assert.ok(near(m.partial.price, 95));
  assert.strictEqual(m.partial.blocked, null,
    'cutting size on the way down is a real decision, not a mistake to refuse');
});

t('a fraction that would close the whole position is blocked', () => {
  for(const fraction of [1, 1.5, 0, -0.5, NaN]){
    const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                          equity: EQ, cfg: CFG, partial: {fraction, atR: 1}});
    assert.strictEqual(m.partial.blocked, 'FRACTION_RANGE',
      'nothing would be left to settle at the stop or target: ' + String(fraction));
  }
  const dust = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                           equity: EQ, cfg: CFG,
                           partial: {fraction: 0.001, atR: 1}});
  assert.strictEqual(dust.partial.blocked, 'FRACTION_TOO_SMALL');
});

t('a half-typed rung blocks rather than guessing a price', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                        equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: NaN}});
  assert.strictEqual(m.partial.blocked, 'NO_PRICE');
  assert.strictEqual(m.partial.price, null);
});

t('no rung asked for means no rung reported', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                        equity: EQ, cfg: CFG});
  assert.strictEqual(m.partial, undefined,
    'an absent scale-out must not materialise as a blocked one');
});

t('a bad rung does not block the trade itself', () => {
  const m = ticketMath({dir: 'LONG', entry: 100, tp: 130, sl: 90,
                        equity: EQ, cfg: CFG, partial: {fraction: 0.5, atR: 9}});
  assert.ok(m.ok, 'the bracket is still valid');
  assert.strictEqual(m.blocks.length, 0,
    'blocks is the liquidation gate — a mistyped rung is not a plan that ' +
    'cannot be placed at all');
});

console.log(`\n${pass} passed`);
