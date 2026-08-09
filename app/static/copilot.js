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
  let mode = 'observe';
  let recorder = null;
  let captureStream = null;
  let captureChunks = [];
  let captureUrl = '';
  let captureBlob = null;
  let captureStarted = 0;
  let captureDurationMs = 0;
  let captureTimer = 0;
  let captureNote = '';
  let analysisBusy = false;
  let analysisText = '';

  const ctxKey = c => c.kind === 'diagnostics'
    ? 'diag' : `${c.symbol}|${c.tf}|${c.setupId || ''}`;
  const sKey = c => 'ss-cp-session|' + ctxKey(c);
  const mKey = c => 'ss-cp-msgs|' + ctxKey(c);
  const MAX_KEPT = 40;

  /* A WRITE THAT FAILS SAYS SO — ONCE.

     sessionStorage throws when the browser has storage disabled, when a
     private window has exhausted its allowance, or when the transcript grows
     past quota. The READS below already fall back honestly (no session, no
     messages). The WRITES used to swallow it in silence, and the operator's
     only clue was a copilot conversation that quietly failed to survive a
     reload — a stated behaviour not happening, with nothing anywhere saying
     why. §4: a degraded path has to be audible.

     Once, though, not per call. saveMsgs() runs on every message, so warning
     each time would bury the first and truest report under a hundred copies of
     itself. The consequence is named in the message because "QuotaExceeded"
     alone does not tell the reader which behaviour they just lost. */
  let storageWarned = false;
  function storageFailed(lost, e){
    if(storageWarned) return;
    storageWarned = true;
    console.warn(`copilot: browser storage is unavailable — ${lost} will not ` +
                 `survive a reload (${(e && e.message) || e})`);
  }

  const getSession = () => { try { return sessionStorage.getItem(sKey(ctx)); }
                             catch(e){ return null; } };
  const setSession = id => { try { if(id) sessionStorage.setItem(sKey(ctx), id); }
                             catch(e){ storageFailed('this conversation', e); } };
  function loadMsgs(c){
    try{ return JSON.parse(sessionStorage.getItem(mKey(c)) || '[]'); }
    catch(e){ return []; }
  }
  function saveMsgs(){
    try{ sessionStorage.setItem(mKey(ctx), JSON.stringify(msgs.slice(-MAX_KEPT))); }
    catch(e){ storageFailed('the messages in this conversation', e); }
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

  const captureActive = () => recorder && recorder.state === 'recording';
  function elapsed(){
    const seconds = captureStarted ? Math.floor((Date.now() - captureStarted) / 1000) : 0;
    return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }
  function captureHtml(){
    if(captureActive()) return `
      <div class="cp-capture cp-recording">
        <span class="cp-rec-dot" aria-hidden="true"></span>
        <p class="cp-capture-kicker">Recording locally</p>
        <strong id="cpElapsed">${elapsed()}</strong>
        <p>Your selected screen or tab is being captured. Nothing is uploaded.</p>
        <button type="button" class="btn btn-red" id="cpStopCapture">Stop recording</button>
      </div>
      <div class="cp-foot">local only · closing Spotter stops the recording</div>`;
    if(captureBlob && captureUrl) return `
      <div class="cp-capture cp-capture-ready">
        <p class="cp-capture-kicker">Capture ready</p>
        <video controls src="${captureUrl}" aria-label="Recorded session preview"></video>
        <p>${captureNote || 'The recording is held in this browser tab until you download or discard it.'}</p>
        <p class="cp-capture-note">Analyze sends up to 12 sampled still frames to Codex. The original video is not uploaded.</p>
        <div class="cp-capture-actions">
          <button type="button" class="btn btn-primary" id="cpAnalyzeCapture"${analysisBusy ? ' disabled' : ''}>${
            analysisBusy ? 'Analyzing…' : 'Analyze recording'}</button>
          <a class="btn btn-primary" id="cpDownloadCapture" href="${captureUrl}"
             download="snipersight-spotter-${new Date().toISOString().replace(/[:.]/g, '-')}.webm">Download</a>
          <button type="button" class="btn" id="cpDiscardCapture"${analysisBusy ? ' disabled' : ''}>Discard</button>
        </div>
        ${analysisBusy ? '<p class="cp-analysis-state" role="status">Sampling timestamped frames and asking Codex to review them…</p>' : ''}
        ${analysisText ? `<div class="cp-analysis"><p class="cp-capture-kicker">Spotter diagnosis</p><pre>${esc(analysisText)}</pre></div>` : ''}
      </div>
      <div class="cp-foot">video stays local · analysis shares sampled frames only · never enters the trading record</div>`;
    return `
      <div class="cp-capture cp-capture-idle">
        <div class="cp-capture-mark" aria-hidden="true">◎</div>
        <p class="cp-capture-kicker">Record a screen or tab</p>
        <p>Capture a session for replay or debrief. Your browser will ask exactly what to share.</p>
        <label class="cp-mic"><input type="checkbox" id="cpCaptureMic"> Include microphone</label>
        <button type="button" class="btn btn-primary" id="cpStartCapture">Choose screen or tab</button>
        <p class="cp-capture-note">The video stays on this device. Spotter cannot trade, restart, deploy, or apply changes.</p>
        ${captureNote ? `<p class="cp-capture-error" role="status">${esc(captureNote)}</p>` : ''}
      </div>
      <div class="cp-foot">local only · nothing is sent until you choose to share it</div>`;
  }

  function render(){
    if(!ctx){ ROOT.innerHTML = ''; document.body.classList.remove('cp-open'); return; }
    document.body.classList.add('cp-open');
    const chip = ctx.kind === 'diagnostics'
      ? 'diagnosing the machine — faults · gates · quality · log'
      : `${esc(ctx.symbol)} ${esc(ctx.tf)}${ctx.setupId ? ' · setup attached' : ''}`;
    ROOT.innerHTML = `
      <aside class="cp-dock" role="complementary" aria-label="Spotter">
        <div class="cp-head">
          <span class="cp-title">Spotter</span>
          <span class="cp-sub">observe · capture</span>
          ${mode === 'observe' ? `<select id="cpModel" class="btn" title="model for the next message">
            <option value="sonnet"${model==='sonnet'?' selected':''}>Sonnet</option>
            <option value="haiku"${model==='haiku'?' selected':''}>Haiku</option>
            <option value="opus"${model==='opus'?' selected':''}>Opus</option>
          </select>
          <button class="btn" id="cpClear" title="forget this conversation">New</button>` : ''}
          <button class="btn" id="cpClose">Close</button>
        </div>
        <div class="cp-tabs" role="tablist" aria-label="Spotter mode">
          <button type="button" role="tab" id="cpObserve" aria-selected="${mode === 'observe'}">Observe</button>
          <button type="button" role="tab" id="cpCapture" aria-selected="${mode === 'capture'}">Capture</button>
        </div>
        ${mode === 'capture' ? captureHtml() : `
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
        <div class="cp-foot">observer only · cannot arm · runs on your Claude plan</div>`}
      </aside>`;
    const box = document.getElementById('cpMsgs');
    if(box) box.scrollTop = box.scrollHeight;
    wire();
  }

  function wire(){
    document.getElementById('cpClose').addEventListener('click', close);
    document.getElementById('cpObserve').addEventListener('click', () => {
      mode = 'observe'; render();
    });
    document.getElementById('cpCapture').addEventListener('click', () => {
      mode = 'capture'; render();
    });
    if(mode === 'capture'){
      const start = document.getElementById('cpStartCapture');
      const stop = document.getElementById('cpStopCapture');
      const discard = document.getElementById('cpDiscardCapture');
      const analyze = document.getElementById('cpAnalyzeCapture');
      if(start) start.addEventListener('click', startCapture);
      if(stop) stop.addEventListener('click', stopCapture);
      if(discard) discard.addEventListener('click', discardCapture);
      if(analyze) analyze.addEventListener('click', analyzeCapture);
      return;
    }
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

  async function startCapture(){
    captureNote = '';
    if(!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia ||
       typeof window.MediaRecorder === 'undefined'){
      captureNote = 'Screen recording is not supported by this browser.';
      render();
      return;
    }
    const withMic = !!(document.getElementById('cpCaptureMic') || {}).checked;
    let display = null;
    let mic = null;
    try{
      /* Spotter is often recording SniperSight itself. With only video/audio,
         Chromium is free to omit the calling tab to avoid a hall-of-mirrors
         preview, which made the screen the operator was auditing impossible
         to choose. These are chooser hints, not a bypass: the browser still
         presents every allowed source and the operator still grants access. */
      display = await navigator.mediaDevices.getDisplayMedia({
        video: {displaySurface: 'browser'},
        audio: true,
        preferCurrentTab: true,
        selfBrowserSurface: 'include',
        surfaceSwitching: 'include',
        systemAudio: 'include',
      });
      if(withMic){
        try{
          mic = await navigator.mediaDevices.getUserMedia({audio: true});
        }catch(err){
          captureNote = 'Microphone access was unavailable; screen recording continued without it.';
        }
      }
      const tracks = display.getTracks().concat(mic ? mic.getAudioTracks() : []);
      captureStream = new window.MediaStream(tracks);
      captureChunks = [];
      recorder = new window.MediaRecorder(captureStream);
      recorder.addEventListener('dataavailable', e => {
        if(e.data && e.data.size) captureChunks.push(e.data);
      });
      recorder.addEventListener('stop', finishCapture, {once: true});
      const videoTrack = display.getVideoTracks()[0];
      if(videoTrack) videoTrack.addEventListener('ended', stopCapture, {once: true});
      recorder.start(1000);
      captureStarted = Date.now();
      captureTimer = window.setInterval(() => {
        const label = document.getElementById('cpElapsed');
        if(label) label.textContent = elapsed();
      }, 1000);
      render();
    }catch(err){
      if(display) display.getTracks().forEach(track => track.stop());
      if(mic) mic.getTracks().forEach(track => track.stop());
      captureStream = null;
      recorder = null;
      captureNote = err && err.name === 'NotAllowedError'
        ? 'Capture was cancelled. Nothing was recorded.'
        : 'Spotter could not start the recording.';
      render();
    }
  }

  function stopCapture(){
    if(recorder && recorder.state === 'recording') recorder.stop();
    if(captureStream) captureStream.getTracks().forEach(track => track.stop());
  }

  function finishCapture(){
    window.clearInterval(captureTimer);
    captureTimer = 0;
    if(captureUrl) URL.revokeObjectURL(captureUrl);
    const type = (recorder && recorder.mimeType) || 'video/webm';
    captureDurationMs = captureStarted ? Date.now() - captureStarted : 0;
    captureBlob = new Blob(captureChunks, {type});
    captureUrl = captureBlob.size ? URL.createObjectURL(captureBlob) : '';
    if(!captureUrl) captureNote = 'The browser stopped capture without producing a video.';
    captureStream = null;
    recorder = null;
    captureStarted = 0;
    if(ctx) render();
  }

  function discardCapture(){
    if(captureUrl) URL.revokeObjectURL(captureUrl);
    captureUrl = '';
    captureBlob = null;
    captureChunks = [];
    captureDurationMs = 0;
    captureNote = '';
    analysisText = '';
    render();
  }

  function waitMedia(video, event){
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => reject(new Error(`video ${event} timed out`)), 10000);
      const done = () => { window.clearTimeout(timer); cleanup(); resolve(); };
      const failed = () => { window.clearTimeout(timer); cleanup(); reject(new Error('video could not be read')); };
      const cleanup = () => {
        video.removeEventListener(event, done);
        video.removeEventListener('error', failed);
      };
      video.addEventListener(event, done, {once: true});
      video.addEventListener('error', failed, {once: true});
    });
  }

  async function sampleCaptureFrames(){
    const video = document.createElement('video');
    video.muted = true;
    video.preload = 'auto';
    video.src = captureUrl;
    await waitMedia(video, 'loadedmetadata');
    if(video.readyState < 2) await waitMedia(video, 'loadeddata');
    const duration = Number.isFinite(video.duration) && video.duration > 0
      ? video.duration : captureDurationMs / 1000;
    if(!duration) throw new Error('the recording duration could not be read');
    const count = Math.min(12, Math.max(4, Math.ceil(duration / 15)));
    const canvas = document.createElement('canvas');
    const width = Math.min(1280, video.videoWidth || 1280);
    const scale = width / (video.videoWidth || width);
    canvas.width = Math.round(width);
    canvas.height = Math.max(1, Math.round((video.videoHeight || 720) * scale));
    const draw = canvas.getContext('2d', {alpha: false});
    const frames = [];
    for(let i = 0; i < count; i++){
      const second = count === 1 ? 0 : (duration * i / (count - 1));
      const target = Math.min(Math.max(0.01, second), Math.max(0.01, duration - 0.05));
      if(Math.abs(video.currentTime - target) > 0.01){
        video.currentTime = target;
        await waitMedia(video, 'seeked');
      }
      draw.drawImage(video, 0, 0, canvas.width, canvas.height);
      frames.push({timestamp_ms: Math.round(second * 1000),
                   image: canvas.toDataURL('image/jpeg', 0.78)});
    }
    video.removeAttribute('src');
    video.load();
    return frames;
  }

  async function analyzeCapture(){
    if(!captureBlob || !captureUrl || analysisBusy) return;
    analysisBusy = true;
    analysisText = '';
    captureNote = '';
    render();
    try{
      const frames = await sampleCaptureFrames();
      const response = await fetch('/api/spotter/analyze', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({frames})});
      const data = await response.json().catch(() => ({}));
      if(!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      analysisText = data.reply || 'Spotter returned no diagnosis.';
      captureNote = `${data.frames_analyzed || frames.length} timestamped frames analyzed by Codex.`;
    }catch(err){
      captureNote = `Analysis failed — ${(err && err.message) || err}`;
    }finally{
      analysisBusy = false;
      render();
    }
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
        msgs.push({who: 'err', text: 'Spotter error — ' + (d.detail || ('HTTP ' + r.status))});
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
    if(c && (c.kind || c.symbol)) mode = 'observe';
    const next = c && (c.kind || c.symbol)
      ? {kind: c.kind || 'chart', symbol: c.symbol || null, tf: c.tf || '1H',
         setupId: c.setupId || null, suggest: c.suggest || null}
      : surfaceCtx();
    ctx = next;
    msgs = loadMsgs(next);
    render();
  }
  function toggle(){ ctx ? close() : open(); }
  function close(){
    if(captureActive()) stopCapture();
    ctx = null;
    render();
  }
  function clear(){
    if(!ctx) return;
    msgs = [];
    /* `msgs = []` above already cleared what is on screen, so Clear does what
       it says either way. What can still fail is the erasure from storage —
       and a transcript the operator asked to be rid of coming back on the next
       reload is the one failure here worth hearing about. */
    try{ sessionStorage.removeItem(mKey(ctx)); sessionStorage.removeItem(sKey(ctx)); }
    catch(e){ storageFailed('the cleared conversation, which may come back', e); }
    render();
  }

  /* THE button — one binding, here, whatever surface is showing. Spotter is
     an app feature; observer context still follows the active surface. */
  const btn = document.getElementById('btnSpotter');
  if(btn) btn.addEventListener('click', toggle);

  window.SSCopilot = {open, toggle, close, clear};
})();
