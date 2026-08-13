/* Asset-class workspace boundary.

   The choice is intentionally browser-local.  It changes which independent
   book is visible; it never changes automation mode, venue, or server state.
   New operators choose once.  Existing SniperSight operators keep Crypto on
   upgrade and can switch from the permanent header control. */
(() => {
  const KEY = 'ss.market-workspace.v1';
  const VALID = new Set(['crypto', 'stocks']);
  const gate = document.getElementById('marketGate');
  const cancel = document.getElementById('marketCancel');
  const crypto = document.getElementById('cryptoApp');
  const stocks = document.getElementById('stocksApp');
  let selected = null;
  let returnTo = null;

  function read(key){
    try{ return localStorage.getItem(key); }
    catch(e){ return null; }
  }
  function remember(value){
    try{ localStorage.setItem(KEY, value); }
    catch(e){ console.warn('market workspace will not survive a reload'); }
  }
  function paint(value){
    selected = value;
    document.body.dataset.market = value;
    crypto.hidden = value !== 'crypto';
    stocks.hidden = value !== 'stocks';
    gate.hidden = true;
    cancel.hidden = true;
    document.querySelectorAll('[data-market-switch]').forEach(button => {
      button.setAttribute('aria-label', `Switch market workspace. Current: ${value}`);
    });
    dispatchEvent(new CustomEvent('ss:market-change', {detail: {market: value}}));
    if(value === 'stocks' && window.SSStocks) window.SSStocks.onShow();
  }
  function choose(value){
    if(!VALID.has(value)) return;
    remember(value);
    paint(value);
  }
  function openChooser(){
    returnTo = selected;
    gate.hidden = false;
    cancel.hidden = !returnTo;
    const active = gate.querySelector(`[data-market-choice="${selected || 'crypto'}"]`);
    if(active) requestAnimationFrame(() => active.focus());
  }

  document.querySelectorAll('[data-market-choice]').forEach(button =>
    button.addEventListener('click', () => choose(button.dataset.marketChoice)));
  document.querySelectorAll('[data-market-switch]').forEach(button =>
    button.addEventListener('click', openChooser));
  cancel.addEventListener('click', () => returnTo ? paint(returnTo) : openChooser());
  gate.addEventListener('keydown', event => {
    if(event.key === 'Escape' && returnTo){ event.preventDefault(); paint(returnTo); }
  });

  const saved = read(KEY);
  if(VALID.has(saved)) paint(saved);
  else if(read('ss.seen-intro') === '1'){
    // Preserve the current product for operators upgrading into this build.
    remember('crypto');
    paint('crypto');
  } else {
    document.body.dataset.market = 'choose';
    crypto.hidden = true;
    stocks.hidden = true;
    openChooser();
  }

  window.SSMarkets = {
    current: () => selected,
    choose,
    open: openChooser,
  };
})();
