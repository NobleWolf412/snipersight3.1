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

  /* Liquidation, mirroring `venues.liquidation_price` — ISOLATED margin.

     `(1/leverage) - maintenance` is the price move that exhausts the margin
     posted to THIS position. This is a second implementation of an engine
     formula, which the house rules normally forbid, and it is justified only
     because the ticket must draw the line before any fact exists to read it
     from. Both of its inputs are served by /api/trade-config so the CONSTANTS
     cannot drift; `test_ticket_math.js` pins the output against values computed
     from the Python.

     Returns null at 1x: an unleveraged position cannot be liquidated by price,
     which is also why this is inert on spot. */
  function liquidationPrice(entry, leverage, long, maintenance){
    if(!(leverage > 1)) return null;
    const move = (1 / leverage) - maintenance;
    if(move <= 0) return entry;              // margin allowance exceeds the buffer
    return long ? entry * (1 - move) : entry * (1 + move);
  }

  /* input:  {dir, entry, tp, sl, equity, cfg, riskUsdOverride, leverage}
     output: {ok, errors[], notes[], blocks[], riskPerUnit, rewardPerUnit,
              rrGross, rrNet, riskUsd, size, notional, fees, netUsd,
              riskPctEffective, riskSource, leverage, margin, liquidation,
              liqDistance} */
  function ticketMath(inp){
    const {dir, entry, tp, sl, equity, cfg, riskUsdOverride, leverage} = inp;
    const long = dir === 'LONG';
    /* `notes` are shown; `blocks` PREVENT the trade. They were one list, and
       merging them would mean a liquidation-safety failure rendered in the same
       grey as "fees are high" — the engine already refuses these outright
       (risk.py calls stop_survives_liquidation), so the ticket must not present
       one as advice. */
    const out = {ok: false, errors: [], notes: [], blocks: [], riskPerUnit: null,
                 rewardPerUnit: null, rrGross: null, rrNet: null, riskUsd: null,
                 size: null, notional: null, fees: null, netUsd: null,
                 leverage: null, margin: null, liquidation: null,
                 liqDistance: null};

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

    /* LEVERAGE IS A CAP ON MARGIN, NEVER A MULTIPLIER ON RISK.

       Size is already fixed above by `riskUsd / riskU` and nothing here may
       touch it. Raising leverage posts LESS margin for the same position and
       moves liquidation closer to entry; it does not buy a bigger trade. That
       is the spec's rule verbatim — "risk stays distance to stop; margin =
       notional / leverage. Leverage never widens a stop" — and it is what makes
       the dial safe to expose: the worst it can do is move a line the ticket
       draws, and the gate below refuses the trade when that line crosses the
       stop.

       Clamped to the venue's own maximum, so spot (1x) silently pins to 1 and
       the whole mechanism is inert there by construction rather than by a
       branch. */
    const venueMax = cfg.max_leverage || 1;
    const lev = Math.min(Math.max(
      (typeof leverage === 'number' && isFinite(leverage) && leverage >= 1)
        ? leverage : 1, 1), venueMax);
    out.leverage = lev;
    out.margin = notional / lev;

    const maint = (cfg.venue && typeof cfg.venue.maintenance_margin === 'number')
      ? cfg.venue.maintenance_margin : 0;
    const liq = liquidationPrice(entry, lev, long, maint);
    out.liquidation = liq;
    if(liq != null){
      out.liqDistance = Math.abs(entry - liq);
      /* The stop must trigger BEFORE liquidation. If the exchange closes the
         position first, the stop is decorative and every R-multiple built on it
         is fiction — which is why this blocks rather than warns. */
      const survives = long ? sl > liq : sl < liq;
      if(!survives) out.blocks.push('STOP_BEYOND_LIQUIDATION');
    }

    /* Buying power is now measured against the CHOSEN leverage, not the venue
       maximum. Sizing against a 10x cap while posting 1x of margin would report
       headroom the account does not have. */
    if(out.margin > equity)
      out.notes.push('NOTIONAL_EXCEEDS_BUYING_POWER');

    return out;
  }

  if(typeof module !== 'undefined' && module.exports) module.exports = {ticketMath};
  else root.SSTicketMath = {ticketMath};
})(typeof globalThis !== 'undefined' ? globalThis : this);
