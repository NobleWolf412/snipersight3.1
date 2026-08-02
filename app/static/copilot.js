/* SniperSight copilot drawer — chat over the fact pack, observer only.

   Boundaries mirrored from the server (engine/copilot.py):
     · It analyses; it cannot arm. There is no path from a reply to the
       ticket, deliberately — even "apply suggestion" is refused as a
       feature, or the manual book stops meaning "the operator's judgement".
     · Nothing said here is recorded as a fact.
     · Runs on the operator's Claude subscription through the local CLI; the
       footer says so because a chat box that silently spends quota is rude.

   Sessions: one CLI session per context (symbol|tf|setup), resumed across
   messages so the fact pack is transmitted once per conversation. The session
   id AND the transcript are both held in sessionStorage against that context,
   so closing the drawer, switching symbol and back, or reloading the page all
   return to the conversation where it was left. A browser restart starts
   fresh, which is the right default for advice that goes stale with the
   chart; "New" discards a conversation on purpose.

   Public: window.SSCopilot.open({symbol, tf, setupId?}) / .close() / .clear() */
(() => {
  'use strict';
  const ROOT = document.getElementById('copilotRoot');
  if (!ROOT) return;

  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));

  let ctx = null;          // {symbol, tf, setupId}
  let busy = false;
  let msgs = [];           // {who:'op'|'cp'|'err', text}
  let model = localStorage.getItem('ss-cp-model') || 'sonnet';

  /* Context identity. The CLI session id AND the visible transcript are both
     stored against it, because losing either one alone is worse than losing
     both: the session survived a close while the transcript did not, so the
     model remembered an exchange the operator could no longer read, and a
     follow-up question got "as noted above" about text that was gone. */
  const ctxKey = c => `${c.symbol}|${c.tf}|${c.setupId || ''}`;
  const sKey = c => 'ss-cp-session|' + ctxKey(c);
  const mKey = c => 'ss-cp-msgs|' + ctxKey(c);
  const MAX_KEPT = 40;

  const getSession = () => { try { return sessionStorage.getItem(sKey(ctx)); }
                             catch(e){ return null; } };
  const setSession = id => { try { if(id) sessionStorage.setItem(sKey(ctx), id); }
                             catch(e){} };
  function loadMsgs(c){
    try{ return JSON.parse(sessionStorage.getItem(mKey(c)) || '[]'); }
    catch(e){ return []; }
  }
  function saveMsgs(){
    // Storage can be full or blocked; a failed save must never break the chat.
    try{ sessionStorage.setItem(mKey(ctx), JSON.stringify(msgs.slice(-MAX_KEPT))); }
    catch(e){}
  }

  function render(){
    if(!ctx){ ROOT.innerHTML = ''; return; }
    const chips = [`${esc(ctx.symbol)} ${esc(ctx.tf)}`,
                   ctx.setupId ? 'engine setup attached' : 'chart context',
                   'trace · draft · weather · book'];
    ROOT.innerHTML = `
      <div class="cp-scrim" data-close="1"></div>
      <aside class="cp-drawer" role="dialog" aria-modal="true" aria-label="Copilot">
        <div class="cp-head">
          <span class="cp-title">Copilot</span>
          <span class="cp-sub">observer only — cannot arm</span>
          <select id="cpModel" class="btn" title="model for the next message">
            <option value="sonnet"${model==='sonnet'?' selected':''}>Sonnet</option>
            <option value="haiku"${model==='haiku'?' selected':''}>Haiku</option>
            <option value="opus"${model==='opus'?' selected':''}>Opus</option>
          </select>
          <button class="btn" id="cpClear" title="forget this conversation and start a new one">New</button>
          <button class="btn" data-close="1">Close</button>
        </div>
        <div class="cp-chips">${chips.map(c => `<span class="chip">${c}</span>`).join('')}</div>
        <div class="cp-msgs" id="cpMsgs">
          ${msgs.length ? '' : `<div class="cp-hint">Ask about this chart — the
            copilot reads the same facts the engine decided on: the setup's
            trace, the draft and its basis, regime weather, venue costs, and
            the honest state of the book. It analyses; you decide.</div>`}
          ${msgs.map(m => `<div class="cp-msg ${m.who}">${esc(m.text)}</div>`).join('')}
          ${busy ? '<div class="cp-msg cp busy">thinking…</div>' : ''}
        </div>
        <div class="cp-input">
          <textarea id="cpText" rows="2" placeholder="Ask about this setup"></textarea>
          <button class="btn btn-cyan" id="cpSend"${busy ? ' disabled' : ''}>Send</button>
        </div>
        <div class="cp-foot">opinion layer — never enters the record · runs on your Claude plan</div>
      </aside>`;
    const box = document.getElementById('cpMsgs');
    box.scrollTop = box.scrollHeight;
    wire();
  }

  function wire(){
    ROOT.querySelectorAll('[data-close]').forEach(el =>
      el.addEventListener('click', close));
    const sel = document.getElementById('cpModel');
    sel.addEventListener('change', () => {
      model = sel.value;
      localStorage.setItem('ss-cp-model', model);
    });
    const ta = document.getElementById('cpText');
    ta.addEventListener('keydown', e => {
      if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
    });
    document.getElementById('cpSend').addEventListener('click', send);
    document.getElementById('cpClear').addEventListener('click', clear);
    ta.focus();
  }

  async function send(){
    const ta = document.getElementById('cpText');
    const text = (ta.value || '').trim();
    if(!text || busy) return;
    msgs.push({who: 'op', text});
    saveMsgs();
    busy = true; render();
    try{
      const body = {message: text, model,
                    symbol: ctx.symbol, tf: ctx.tf,
                    setup_id: ctx.setupId || null,
                    session_id: getSession()};
      const r = await fetch('/api/copilot', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)});
      const d = await r.json().catch(() => ({}));
      if(!r.ok){
        msgs.push({who: 'err', text: 'copilot error — ' + (d.detail || ('HTTP ' + r.status))});
      }else{
        setSession(d.session_id);
        msgs.push({who: 'cp', text: d.reply || '(empty reply)'});
      }
    }catch(err){
      msgs.push({who: 'err', text: 'could not reach the server — nothing was sent'});
    }finally{
      saveMsgs();
      busy = false; render();
    }
  }

  function open(c){
    const next = {symbol: c.symbol, tf: c.tf || '1H', setupId: c.setupId || null};
    /* Reopening restores the transcript. It did not: close() nulls `ctx`, so
       the guard `!ctx || ...` was true on EVERY reopen and wiped the history
       the comment claimed it kept. Reading it from storage keyed by context
       fixes both that and the page reload — the transcript now lives exactly
       as long as the CLI session it belongs to. */
    ctx = next;
    msgs = loadMsgs(next);
    render();
  }
  function close(){ ctx = null; render(); }

  /* A transcript is worth keeping until the operator says otherwise. */
  function clear(){
    if(!ctx) return;
    msgs = [];
    try{ sessionStorage.removeItem(mKey(ctx)); sessionStorage.removeItem(sKey(ctx)); }
    catch(e){}
    render();
  }

  window.SSCopilot = {open, close, clear};
})();
