/* Glossary — one definition source for every term the UI shows.
   Operator complaint that produced this file: "there's lingo I have no idea
   what it means, features I don't know what they are, zero explanation."
   Rule: if a domain term appears on screen, it has an entry here. Mark it up as
   <span class="term" data-t="bos">BOS</span> and it explains itself on hover.
   Plain-English first sentence; the precise version second. */
window.GLOSSARY = {
  /* ---- market structure ---- */
  swing:      "A turning point on the chart — a high where price stopped rising, or a low where it stopped falling. SniperSight ranks them minor / intermediate / major by how much they actually mattered.",
  major:      "A turning point big enough to matter months later. Scored on how far price reversed, how long the level held, volume at the turn, and how many later breaks it caused.",
  bos:        "Break of Structure — price closed beyond a previous major high or low, confirming the trend is continuing in that direction.",
  choch:      "Change of Character — the first break AGAINST the prevailing trend. A warning that the trend may be ending, not proof that it has.",
  zone:       "A price band where buyers or sellers previously stepped in hard. Demand zones sit under price, supply zones above.",
  demand:     "A zone below price where buying previously overwhelmed selling — a candidate area to go long from.",
  supply:     "A zone above price where selling previously overwhelmed buying — a candidate area to go short from.",
  liquidity:  "Clusters of stop-loss orders resting above highs or below lows. Price often reaches for them before reversing.",
  sweep:      "Price pushed past a high or low, triggered the stops there, then came straight back. Often a reversal signal rather than a real break.",
  regime:     "The market's current weather: trending up, trending down, ranging, or transitioning. Different regimes call for different playbooks.",

  /* ---- cycles ---- */
  dcl:        "Daily Cycle Low — the bottom of a roughly 60-day rhythm in price. Cycle traders count from one to the next.",
  wcl:        "Weekly Cycle Low — the bottom of a longer rhythm, roughly 24 weeks, usually containing about three daily cycles.",
  translation:"Where a cycle's high lands within it. Peaks late (right-translated) = strength. Peaks early (left-translated) = weakness.",
  fourYear:   "The four-year rhythm many traders track in Bitcoin, historically anchored near halvings. SniperSight shows the projected low window but treats it as observation, not fact — the sample size is tiny.",

  /* ---- trade mechanics ---- */
  entry:      "The price where the trade opens.",
  tp:         "Take Profit — the price where the trade closes in profit, set automatically when the trade is placed.",
  sl:         "Stop Loss — the price where the trade closes at a loss. Placed where the trade idea would be proven wrong, not at an arbitrary percentage.",
  rr:         "Risk:Reward — how much you stand to gain versus lose. 3.0 means the target is three times further away than the stop.",
  rMultiple:  "Result measured in units of what you risked. +2R means you made twice what you had at risk; −1R means you lost exactly your planned risk.",
  trailing:   "A stop that follows price as the trade moves your way, locking in gains instead of sitting still.",
  setup:      "A trade opportunity the scanner found: a direction, an entry, a target, a stop, and the reasoning behind it.",
  rank:       "SniperSight's confidence score for a setup, 0–100. It is a ranking, deliberately NOT a probability — nothing here claims to know the odds.",
  forming:    "Price is approaching a zone but hasn't reached it. A heads-up, not yet a trade.",
  challenger: "A better setup found for a token that already has one pending. It waits beside the current one until you choose to switch — it never swaps itself.",

  /* ---- risk ---- */
  riskPerTrade:"How much of the account you're willing to lose on one trade. Position size is calculated from this and the stop distance, so the loss is the same whether the stop is near or far.",
  drawdown:   "How far the account has fallen from its highest point. The limit that stops the bot trading.",
  leverage:   "Borrowing to hold a bigger position than your cash. It multiplies gains AND losses, and introduces liquidation.",
  liquidation:"On leveraged trades, the price where the exchange force-closes you and takes the margin. Your stop must sit safely inside it.",
  funding:    "A recurring fee paid between long and short holders on perpetual contracts. It accrues while a position is held, so it matters on multi-day swings.",
  perps:      "Perpetual futures — contracts with no expiry that track the spot price. They allow shorting and leverage; spot markets do not.",
  killSwitch: "An automatic halt. When the day's loss limit is hit, no new trades open until the next day.",

  /* ---- system ---- */
  paper:      "Simulated trading with fake money. Same code, same decisions, no real orders — used to prove the strategy before risking anything.",
  live:       "Real orders on a real exchange with real money.",
  scanner:    "The process that pulls market data, maps structure, and looks for setups.",
  baseline:   "The start date of the current forward test. Results before it belong to an older engine and are not mixed in.",
  fact:       "One recorded observation, stamped with when it happened, when the system could first know it, and which algorithm version produced it. Facts are never edited — only added.",
  algoVersion:"Which version of an engine produced a result. Changing a rule creates a NEW version rather than editing the old one, so past results stay reproducible.",
  rejection:  "A candidate the scanner looked at and turned down, with the reason recorded. Rejections are kept because knowing why nothing fired is as useful as knowing why something did.",
  telemetry:  "The debug trail: what each engine did, on what inputs, producing what. Used to prove the CODE is right before judging whether the STRATEGY is right.",
  blocker:    "A data or pipeline fault serious enough that performance numbers can't be trusted until it's fixed."
};

(function(){
  let box;
  function ensure(){
    if(box) return box;
    box = document.createElement('div');
    box.id = 'gloss';
    box.innerHTML = '<div class="g-term"></div><div class="g-def"></div>';
    document.body.appendChild(box);
    return box;
  }
  function show(el){
    const key = el.dataset.t;
    const def = window.GLOSSARY[key];
    if(!def) return;                       // unknown key: stay silent, never guess
    const b = ensure();
    b.querySelector('.g-term').textContent = el.textContent.trim();
    b.querySelector('.g-def').textContent = def;
    b.style.display = 'block';
    const r = el.getBoundingClientRect();
    const w = b.offsetWidth, h = b.offsetHeight;
    b.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left)) + 'px';
    b.style.top  = (r.top > h + 12 ? r.top - h - 8 : r.bottom + 8) + 'px';
  }
  const hide = () => { if(box) box.style.display = 'none'; };
  // delegated: works for content rendered after load
  document.addEventListener('mouseover', e => {
    const t = e.target.closest('.term'); if(t) show(t);
  });
  document.addEventListener('mouseout', e => {
    if(e.target.closest('.term')) hide();
  });
  document.addEventListener('click', e => {
    const t = e.target.closest('.term');       // tap-friendly
    if(t){ show(t); e.stopPropagation(); } else hide();
  });
  window.addEventListener('scroll', hide, true);
})();
