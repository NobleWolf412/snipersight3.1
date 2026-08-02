/* SniperSight copilot drawer — chat over the fact pack, observer only.

   Boundaries mirrored from the server (engine/copilot.py):
     · It analyses; it cannot arm. There is no path from a reply to the
       ticket, deliberately — even "apply suggestion" is refused as a
       feature, or the manual book stops meaning "the operator's judgement".
     · Nothing said here is recorded as a fact.
     · Runs on the operator's Claude subscription through the local CLI; the
       footer says so because a chat box that silently spends quota is rude.

   Sessions: one CLI session per context (symbol|tf|setup), resumed across
   messages so the fact pack is transmitted once per conversation. Held in
   sessionStorage — a browser restart starts fresh conversations, which is
   the right default for advice that goes stale with the chart.

   Public: window.SSCopilot.open({symbol, tf, setupId?}) / .close() */
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

  const key = c => `ss-cp-session|${c.symbol}|${c.tf}|${c.setupId || ''}`;
  const getSession = () => sessionStorage.getItem(key(ctx));
  const setSession = id => id && sessionStorage.setItem(key(ctx), id);

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
    ta.focus();
  }

  async function send(){
    const ta = document.getElementById('cpText');
    const text = (ta.value || '').trim();
    if(!text || busy) return;
    msgs.push({who: 'op', text});
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
      busy = false; render();
    }
  }

  function open(c){
    const next = {symbol: c.symbol, tf: c.tf || '1H', setupId: c.setupId || null};
    // switching context starts a fresh transcript; same context re-opens it
    if(!ctx || key(ctx) !== key(next)) msgs = [];
    ctx = next;
    render();
  }
  function close(){ ctx = null; render(); }

  window.SSCopilot = {open, close};
})();
