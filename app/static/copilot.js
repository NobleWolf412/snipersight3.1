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

   Public: window.SSCopilot.open({kind?, symbol?, tf?, setupId?, prefill?, ask?})
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
        ${suggestHtml()}
        <div class="cp-input">
          <textarea id="cpText" rows="2" placeholder="${ctx.kind === 'diagnostics'
            ? 'Why is…' : 'Ask about this setup'}"></textarea>
          <button class="btn btn-primary" id="cpSend"${busy ? ' disabled' : ''}>Send</button>
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
    /* SUGGESTIONS FILL THE BOX; THEY DO NOT SEND IT.

       Opening the dock from an open trade used to compose a long question and
       send it immediately. Operator ruling, 4 Aug 2026: the box should be the
       operator's, and the app's ideas should be offered rather than typed on
       their behalf. So a chip drops its text into the textarea, puts the caret
       at the end, and stops — the question can be edited, extended or thrown
       away before a single token is spent on it. */
    const sug = document.getElementById('cpSuggest');
    if(sug) sug.addEventListener('click', e => {
      const b = e.target.closest('[data-q]');
      if(!b) return;
      ta.value = b.dataset.q;
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
      // it has served its purpose; the row would otherwise cover the reply
      sug.hidden = true;
    });
    ta.focus();
  }

  /* What is worth asking here, offered as one-tap starters. Deliberately
     short: a chip is a prompt for the operator, not the prompt for the model —
     they are expected to be edited. The first slot is reserved for a caller's
     own question (a Failing-now row knows its exact fault; a held trade knows
     its own levels), because that is the one nobody could retype. */
  const STARTERS = {
    chart: ["Where does this setup stand right now?",
            "What would prove this thesis wrong?",
            "Is the stop in a sensible place?",
            "What does this cost to hold?"],
    diagnostics: ["What should I fix first?",
                  "Why did nothing fire today?",
                  "Is the data healthy enough to trade on?"],
  };

  function suggestHtml(){
    const list = (STARTERS[ctx.kind] || []).slice();
    if(ctx.suggest) list.unshift(ctx.suggest);
    if(!list.length || msgs.length) return '';   // starters are for a blank slate
    return `<div class="cp-suggest" id="cpSuggest">` +
      list.map(q => `<button class="cp-q" type="button" data-q="${esc(q)}">${
        esc(q.length > 46 ? q.slice(0, 44) + '…' : q)}</button>`).join('') +
      `</div>`;
  }

  /* `override` lets a caller ASK rather than merely prefill. The open-trades
     panel wants one click to produce an answer, not a typed-out question the
     operator still has to send — but prefill stays, because a question you are
     meant to edit before sending is a different affordance. */
  /* NO PARAMETER, DELIBERATELY. This took an `override` that shadowed the
     textarea, and #cpSend is bound straight to this function — so a click
     called send(PointerEvent), `override != null` was true, and the question
     sent to the model was the string "[object PointerEvent]". The textarea was
     never read. The Enter key worked, because that path calls send() with
     nothing, which is why the box appeared to work at all.

     The parameter was already dead. Suggestion chips used to call
     send(theirText); 5bf8038 changed them to drop the text into the textarea
     instead, on the principle that the input belongs to the operator — after
     which nothing filled `override` on purpose and only the click event did.

     A dead parameter on a function bound to an event handler is not inert. It
     is an open socket for whatever the browser passes first. */
  async function send(){
    const ta = document.getElementById('cpText');
    const text = String(ta.value || '').trim();
    if(!text || busy) return;
    ta.value = '';
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
         setupId: c.setupId || null, suggest: c.suggest || null}
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
