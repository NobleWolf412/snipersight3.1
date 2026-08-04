/* SniperSight copilot dock — chat over the fact pack, observer only.

   A DOCK, not a modal. The drawer version dimmed the page behind a scrim, so
   asking a question meant losing the chart the question was about. The dock
   sits on the right edge, the page stays live, and it survives surface
   switches — one topbar button toggles it from anywhere.

   Context follows the surface. On Chart it reads the chart pack (setup trace,
   draft, weather, costs — chart.js publishes the current symbol/tf on
   window.SSChartCtx). Everywhere else it reads the DIAGNOSTIC pack: engine
   faults, data gates, the latest quality verdict and the engine-log tail —
   "why is the machine failing" answered from the same tables Diagnostics
   leads with. The Failing-now rows open it pre-filled with their own fault.

   Boundaries mirrored from the server (engine/copilot.py), unchanged:
     · It analyses; it cannot arm. No path from a reply to the ticket.
     · Nothing said here is recorded as a fact.
     · Runs on the operator's Claude subscription through the local CLI.

   Sessions: one CLI session per context, resumed across messages, transcript
   and session id both held in sessionStorage against the context key — so
   toggling the dock, switching surfaces and reloading all return to the
   conversation where it was left.

   Public: window.SSCopilot.open({kind?, symbol?, tf?, setupId?, prefill?})
           / .toggle() / .close() / .clear() */
(() => {
  'use strict';
  const ROOT = document.getElementById('copilotRoot');
  if (!ROOT) return;

  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));

  let ctx = null;          // {kind:'chart'|'diagnostics', symbol?, tf?, setupId?}
  let busy = false;
  let msgs = [];
  let model = localStorage.getItem('ss-cp-model') || 'sonnet';

  const ctxKey = c => c.kind === 'diagnostics'
    ? 'diag' : `${c.symbol}|${c.tf}|${c.setupId || ''}`;
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
    try{ sessionStorage.setItem(mKey(ctx), JSON.stringify(msgs.slice(-MAX_KEPT))); }
    catch(e){}
  }

  /* What is the operator looking at right now? Chart publishes its symbol/tf;
     every other surface gets the machine itself as the subject. */
  function surfaceCtx(){
    const h = (location.hash || '').replace('#', '');
    if(h === 'chart' && window.SSChartCtx && window.SSChartCtx.symbol){
      return {kind: 'chart', symbol: SSChartCtx.symbol, tf: SSChartCtx.tf || '1H',
              setupId: SSChartCtx.setupId || null};
    }
    return {kind: 'diagnostics'};
  }

  function render(){
    if(!ctx){ ROOT.innerHTML = ''; document.body.classList.remove('cp-open'); return; }
    document.body.classList.add('cp-open');
    const chip = ctx.kind === 'diagnostics'
      ? 'diagnosing the machine — faults · gates · quality · log'
      : `${esc(ctx.symbol)} ${esc(ctx.tf)}${ctx.setupId ? ' · setup attached' : ''}`;
    ROOT.innerHTML = `
      <aside class="cp-dock" role="complementary" aria-label="Copilot">
        <div class="cp-head">
          <span class="cp-title">Copilot</span>
          <span class="cp-sub">observer — cannot arm</span>
          <select id="cpModel" class="btn" title="model for the next message">
            <option value="sonnet"${model==='sonnet'?' selected':''}>Sonnet</option>
            <option value="haiku"${model==='haiku'?' selected':''}>Haiku</option>
            <option value="opus"${model==='opus'?' selected':''}>Opus</option>
          </select>
          <button class="btn" id="cpClear" title="forget this conversation">New</button>
          <button class="btn" id="cpClose">Close</button>
        </div>
        <div class="cp-chips"><span class="chip">${chip}</span></div>
        <div class="cp-msgs" id="cpMsgs">
          ${msgs.length ? '' : `<div class="cp-hint">${ctx.kind === 'diagnostics'
            ? 'Ask why something is failing — it reads the fault table, the data gates, the quality audit and the log tail.'
            : 'Ask about this chart — it reads the same facts the engine decided on.'}</div>`}
          ${msgs.map(m => `<div class="cp-msg ${m.who}">${esc(m.text)}</div>`).join('')}
          ${busy ? '<div class="cp-msg cp busy">thinking…</div>' : ''}
        </div>
        <div class="cp-input">
          <textarea id="cpText" rows="2" placeholder="${ctx.kind === 'diagnostics'
            ? 'Why is…' : 'Ask about this setup'}"></textarea>
          <button class="btn btn-cyan" id="cpSend"${busy ? ' disabled' : ''}>Send</button>
        </div>
        <div class="cp-foot">never enters the record · runs on your Claude plan</div>
      </aside>`;
    const box = document.getElementById('cpMsgs');
    box.scrollTop = box.scrollHeight;
    wire();
  }

  function wire(){
    document.getElementById('cpClose').addEventListener('click', close);
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
    if(ctx.prefill){ ta.value = ctx.prefill; ctx.prefill = null; }
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
                    context: ctx.kind,
                    symbol: ctx.symbol || null, tf: ctx.tf || '1H',
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
    const next = c && (c.kind || c.symbol)
      ? {kind: c.kind || 'chart', symbol: c.symbol || null, tf: c.tf || '1H',
         setupId: c.setupId || null, prefill: c.prefill || null}
      : surfaceCtx();
    ctx = next;
    msgs = loadMsgs(next);
    render();
  }
  function toggle(){ ctx ? close() : open(); }
  function close(){ ctx = null; render(); }
  function clear(){
    if(!ctx) return;
    msgs = [];
    try{ sessionStorage.removeItem(mKey(ctx)); sessionStorage.removeItem(sKey(ctx)); }
    catch(e){}
    render();
  }

  /* THE button — one binding, here, whatever surface is showing. chart.js
     used to own it, which made the copilot a chart feature; it is an app
     feature with a chart mode. */
  const btn = document.getElementById('btnCopilot');
  if(btn) btn.addEventListener('click', toggle);

  window.SSCopilot = {open, toggle, close, clear};
})();
