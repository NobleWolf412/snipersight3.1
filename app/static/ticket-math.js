/* Order-ticket arithmetic — pure, and deliberately in its own file so it can be
   run under node without a DOM (see tests/test_ticket_math.js).

   This is the code that decides how big a trade is. It gets tested like it.

   Nothing in here invents a constant: risk_pct, leverage and the fee rates all
   arrive from /api/trade-config, which reads them off the engine. A UI that
   re-derives a number the engine already owns is how two surfaces came to
   disagree about equity on 2026-07-26.
*/
(function(root){
  'use strict';

  /* input:  {dir, entry, tp, sl, equity, cfg, riskUsdOverride}
     output: {ok, errors[], notes[], riskPerUnit, rewardPerUnit, rrGross,
              rrNet, riskUsd, size, notional, fees, netUsd, riskPctEffective,
              riskSource} */
  function ticketMath(inp){
    const {dir, entry, tp, sl, equity, cfg, riskUsdOverride} = inp;
    const long = dir === 'LONG';
    const out = {ok: false, errors: [], notes: [], riskPerUnit: null,
                 rewardPerUnit: null, rrGross: null, rrNet: null, riskUsd: null,
                 size: null, notional: null, fees: null, netUsd: null};

    const num = v => typeof v === 'number' && isFinite(v) && v > 0;
    if(!num(entry) || !num(tp) || !num(sl)){
      out.errors.push('Entry, target and stop all need a price.');
      return out;
    }

    const riskU = long ? entry - sl : sl - entry;
    const rewU  = long ? tp - entry : entry - tp;
    out.riskPerUnit = riskU;
    out.rewardPerUnit = rewU;

    if(riskU <= 0)
      out.errors.push(long ? 'Stop must sit BELOW entry for a long.'
                           : 'Stop must sit ABOVE entry for a short.');
    if(rewU <= 0)
      out.errors.push(long ? 'Target must sit ABOVE entry for a long.'
                           : 'Target must sit BELOW entry for a short.');
    if(out.errors.length) return out;

    out.ok = true;
    out.rrGross = rewU / riskU;

    // Sizing needs both the account and the engine's risk policy. Without
    // either we report the ratios and say nothing about size — a guessed
    // position size is worse than a blank one.
    if(!num(equity) || !cfg) return out;

    // Per-trade override: sizing THIS trade differently must not touch the
    // engine default, any other trade, or the recorded history. It is a local
    // substitution for one number, nothing more.
    const useOverride = typeof riskUsdOverride === 'number' &&
                        isFinite(riskUsdOverride) && riskUsdOverride > 0;
    const riskUsd = useOverride ? riskUsdOverride : equity * cfg.risk_pct;
    out.riskSource = useOverride ? 'operator' : 'engine';
    out.riskPctEffective = riskUsd / equity;

    const size = riskUsd / riskU;
    const notional = size * entry;
    out.riskUsd = riskUsd;
    out.size = size;
    out.notional = notional;

    if(useOverride){
      // The coupled envelope still applies. Risking more than the account's
      // whole open-risk budget on one trade would breach the limit that keeps
      // two concurrent positions survivable.
      const cap = equity * (cfg.max_total_risk_pct || cfg.risk_pct);
      if(riskUsd > cap) out.notes.push('RISK_EXCEEDS_TOTAL_BUDGET');
      if(out.riskPctEffective > (cfg.daily_loss_pct || 1))
        out.notes.push('RISK_EXCEEDS_DAILY_HALT');
    }

    // Fees are charged on NOTIONAL while the stop is measured in ticks, so a
    // tight structural stop can cost more in fees than it risks in price.
    // That asymmetry is what sank the intraday book in backtest; it is shown,
    // not buried.
    if(cfg.cost){
      const fees = notional * (cfg.cost.maker_rate + cfg.cost.taker_rate);
      out.fees = fees;
      out.netUsd = rewU * size - fees;
      out.rrNet = out.netUsd / riskUsd;
      if(out.rrNet < 1)
        out.notes.push('After fees this risks more than it stands to make. ' +
                       'The engine gate rejects trades like this for a reason.');
    }

    const buyingPower = equity * (cfg.max_leverage || 1);
    if(notional > buyingPower)
      out.notes.push('NOTIONAL_EXCEEDS_BUYING_POWER');

    return out;
  }

  if(typeof module !== 'undefined' && module.exports) module.exports = {ticketMath};
  else root.SSTicketMath = {ticketMath};
})(typeof globalThis !== 'undefined' ? globalThis : this);
