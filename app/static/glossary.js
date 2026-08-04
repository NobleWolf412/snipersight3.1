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
  liquidity:  "Clusters of stop-loss orders resting above highs or below lows. Price often reaches for them before reversing. SniperSight infers these from the chart's own shape — repeated highs or lows at nearly the same price — so it is a LIKELY place for stops, not a measured one: nothing here can see the real order book. No playbook trades them, so treat a marked pool as context, not a target.",
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
  structuralStop:"A stop placed where the trade idea would be proven wrong, not at a round percentage. SniperSight puts it just past the low the confirming candle rejected — or the zone's far edge if that sits further — plus a small buffer, so the loss is defined by a price the market visibly refused.",
  rr:         "Risk:Reward — how much you stand to gain versus lose. 3.0 means the target is three times further away than the stop.",
  rMultiple:  "Result measured in units of what you risked. +2R means you made twice what you had at risk; −1R means you lost exactly your planned risk.",
  expectancy: "What one trade is worth on average, in units of what you risked. Add up every result in R and divide by the number of trades — positive means the edge pays, and the honest question is whether it sits far enough from zero to be told apart from luck.",
  trailing:   "A stop that follows price as the trade moves your way, locking in gains instead of sitting still.",
  setup:      "A trade opportunity the scanner found: a direction, an entry, a target, a stop, and the reasoning behind it.",
  shadow:     "A symbol the scanner watches, scores and simulates but NEVER sizes a real position on — usually because its venue is not one this system trades yet. Its record is evidence about whether to admit that venue, not part of your own record. Market Weather counts shadow symbols separately from tradeable ones for that reason.",
  /* Added after the UX audit walked the primary surface as a first-time
     trader and listed the words that appear there with no way to look them
     up. "1D agrees" was the costliest omission: it is the higher-timeframe
     confirmation that makes the trade, and it was unexplained on the card
     asking you to take it. */
  liquidity:  "Prices where a lot of stop orders are probably resting — under an obvious low, above an obvious high. Price is drawn to them, because triggering stops creates the volume a large order needs to fill. This is INFERRED from the shape of the chart, never measured: no exchange publishes where stops sit.",
  sized:      "Turned into an actual position with a dollar amount at risk. A setup can be found, scored and recorded without ever being sized — sizing is the moment the risk authority approves it and decides how much. Shadow and warming symbols are scanned and scored but never sized.",
  halt:       "A limit that stops NEW entries when the day or the account goes badly enough. Open positions still run to their own stop or target — a halt is not a liquidation. The daily one triggers on losses in a single day; the drawdown one on the fall from your account's high-water mark.",
  htfAgrees:  "The higher timeframe is pointing the same way as the trade. A 4H short with '1D agrees' means the daily structure is also falling, so the trade runs with the larger trend rather than against it. When they disagree, the smaller timeframe is fighting the bigger one — which is the trade most likely to be stopped out by ordinary noise.",
  warming:    "A symbol that is still downloading history. It needs 200 daily candles before the engines can map its structure honestly, so until then it is scanned and recorded but never sized. Warming is the system waiting on data, not the system finding nothing.",
  cooldown:   "A rest period after a trade closes, per symbol and direction. A stop-out rests far longer than a target: a stop means the level was proven wrong, and re-entering an idea that just failed is one of the easiest ways to turn one loss into three. A setup refused this way was VALID — it was refused on timing, not on quality. This rule is new and has never been checked against outcomes: it is a rule of thumb the engine applies, not a proven improvement.",
  universe:   "The symbols the scanner is allowed to trade right now. Shadow symbols are watched, scored and simulated but never sized — their record is evidence for whether to admit that venue, not part of yours. Warming ones are still backfilling history. Symbols we merely still hold candles for are not in the count at all.",
  playbook:   "A named set of rules for one kind of trade: the market condition it needs, what triggers it, where the stop goes, how long it's held. The scanner only produces a setup when a playbook covers what the market is doing — so a quiet day usually means the market is in a state nothing here has a play for, not that nothing is happening.",
  horizon:    "How long a trade is meant to be held. It comes from the timeframe that found it: a 15-minute setup is usually over within a day, a daily one can run for weeks. The horizon is a policy, not a label — it decides how much patience a trade is given before it's closed as going nowhere.",
  confirmation:"Proof that a level held, before the trade opens. Price touching a zone isn't enough; SniperSight waits for a candle to close back out of it, finishing near the far end of its own range. Costs a little of the move, avoids a lot of the losses.",
  rank:       "SniperSight's confidence score for a setup, 0–100. It is a ranking, deliberately NOT a probability — nothing here claims to know the odds.",
  confluence: "Separate reasons pointing the same way — the higher timeframe agreeing, a fresh zone, heavy volume at the touch. Counting them only means something if they are independent: five indicators computed from the same closing prices are one opinion counted five times, so a factor here is recorded first and only earns weight once it is shown to predict outcomes.",
  htfAlignment:"Checking that the bigger timeframe agrees before trusting a smaller one — 4H defers to 1D, 1D to 1W. A 15-minute reversal inside a daily uptrend is usually a pullback; SniperSight records whether the higher timeframe agreed and adds 10 to the rank when it does, but never requires it.",
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

  /* The two ERAS. Every trade count in this app belongs to one of them, and the
     two legitimately disagree: Results can read zero while Diagnostics reads
     several hundred. That is not a fault, but an operator who meets the two
     numbers without these labels concludes the app is broken — so both surfaces
     name their era in the same words, and both point at the other. */
  forwardWindow:"The stretch of trading since the current baseline opened. Results reports ONLY this window, so it reads empty until the risk authority rules on its first setup — however many trades came before. Changing a rule starts a new one.",
  recordedBook: "Every trade the simulator has ever closed, across all baselines and every engine version. Diagnostics measures the edge against this, because a confidence interval needs far more trades than one forward window usually holds.",
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

  /* KEYBOARD, not just hover. The glossary is the best thing in this app and it
     was reachable by exactly one input device. Someone tabbing through the page
     could not read a single definition, and a footnote saying "tap it on a
     phone" does not help them either.

     Every term becomes a real focus stop: focus shows it, blur and Escape hide
     it, Enter and Space toggle. `button` role rather than `definition`, because
     it does something when activated — announcing it as a definition would
     promise screen-reader users the text is already there, which it is not. */
  /* FIRST USE PER CARD. 152 triggers for 67 unique terms meant the same word
     was dotted and focusable five times in one panel — five tab stops and five
     identical tooltips for one definition, and a page so speckled that the
     underlining stopped signalling anything.

     The first occurrence inside each card keeps its trigger; later ones in the
     SAME card become plain text. A different card starts over, because a
     reader who scrolled past the first one still needs a way in. */
  function capTriggers(root){
    const cards = (root || document).querySelectorAll(
      '.panel, .tile, .deck-row, .jnl-row, .ev-verdict, .explainer, .lesson');
    cards.forEach(card => {
      const seen = new Set();
      card.querySelectorAll('.term[data-t]').forEach(t => {
        const k = t.dataset.t;
        if(!seen.has(k)){ seen.add(k); return; }
        // demote: keep the word, drop the affordance
        t.removeAttribute('data-t');
        t.classList.remove('term');
        t.classList.add('term-plain');
      });
    });
  }

  function markFocusable(root){
    capTriggers(root);
    (root || document).querySelectorAll('.term:not([data-gfocus])').forEach(t => {
      t.dataset.gfocus = '1';
      t.tabIndex = 0;
      t.setAttribute('role', 'button');
      const key = t.dataset.t;
      /* NO aria-label. An aria-label REPLACES an element's text in the
         accessibility tree, so labelling each inline term shredded the
         sentence around it — a screen reader read "The only play in a is a ,
         and it counts only with at least 1 of: a structural break, a , heavy
         ." Every term had swallowed its own word.

         The accessible name now comes from the element's own text, which is
         the word in the sentence, and the DEFINITION is attached as a
         description instead. The sentence survives; the extra information is
         still announced. */
      t.removeAttribute('aria-label');
      if(window.GLOSSARY[key]){
        t.setAttribute('title', window.GLOSSARY[key]);
        // announced after the word, not instead of it
        t.setAttribute('aria-description', window.GLOSSARY[key]);
      }
    });
  }
  document.addEventListener('focusin', e => {
    const t = e.target.closest && e.target.closest('.term');
    if(t) show(t);
  });
  document.addEventListener('focusout', e => {
    if(e.target.closest && e.target.closest('.term')) hide();
  });
  document.addEventListener('keydown', e => {
    if(e.key === 'Escape'){ hide(); return; }
    const t = e.target.closest && e.target.closest('.term');
    if(!t) return;
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); show(t); }
  });

  /* Content arrives long after load and keeps being replaced — the deck rebuilds
     on a diff, weather re-renders every 30s, edgeview repaints wholesale. A
     one-time pass would leave every later term unreachable again. */
  markFocusable();
  new MutationObserver(ms => {
    for(const m of ms) if(m.addedNodes.length){ markFocusable(); return; }
  }).observe(document.body, {childList: true, subtree: true});
  window.SSGlossaryFocus = markFocusable;      // for tests and late mounts

  /* Mark up engine-authored prose so its jargon explains itself.

     Lives HERE, next to the definitions, because it was written inside
     weather.js's closure and the setup deck needed the same thing — and a
     second copy of a term table is precisely the drift this codebase keeps
     paying for (three engine rosters, two sizing authorities, two verdict
     writers). One table, one matcher, loaded before every consumer.

     Each regex is non-global on purpose: the FIRST occurrence of a term is
     underlined and later ones are left alone. A paragraph where every instance
     of "zone" is dotted reads as noise and gets skipped wholesale. */
  const TERMS = [
    [/\bliquidity sweeps?\b/i, 'sweep'],
    /* "1D agrees" / "4H opposes" — the higher-timeframe verdict, printed on
       the deck card that asks you to take the trade and unexplained until the
       UX audit walked this surface cold. Placed above the bare /liquidity/
       and /timeframe/ patterns so the whole phrase is claimed as one term
       rather than half of it being underlined. */
    [/\b\d+[DWHM] (?:agrees|opposes)\b/i, 'htfAgrees'],
    [/\bhigher[- ]timeframe\b/i, 'timeframe'],
    [/\bliquidity\b/i, 'liquidity'],
    [/\btimeframes?\b/i, 'timeframe'],
    [/\bpullbacks?\b/i, 'pullback'],
    [/\breversals?\b/i, 'reversal'],
    [/\bplaybooks?\b/i, 'playbook'],
    [/\btransitions?\b/i, 'transition'],
    [/\branges?\b/i, 'range'],
    [/\bzones?\b/i, 'zone'],
    [/\bregimes?\b/i, 'regime'],
    [/\bsetups?\b/i, 'setup'],
    [/\bconfirmed\b/i, 'confirmation'],
    [/\bstops?\b/i, 'structuralStop'],
  ];

  const escHtml = s => String(s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

  window.SSTeach = function teach(text) {
    if (text == null) return '';
    let out = escHtml(text);
    for (const [re, key] of TERMS) {
      if (!window.GLOSSARY[key]) continue;   // never underline what cannot explain itself
      out = out.replace(re, m => `<span class="term" data-t="${key}">${m}</span>`);
    }
    return out;
  };
})();
