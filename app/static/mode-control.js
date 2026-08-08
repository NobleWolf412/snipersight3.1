/* Revision-checked operating-mode control. Promotion remains server-owned;
   disabled buttons display the lock instead of inviting a doomed request. */
(() => {
  const controls = document.getElementById('modeControls');
  if(!controls) return;
  const explanation = document.getElementById('modeExplanation');
  const lock = document.getElementById('modeLock');
  const revision = document.getElementById('modeRevision');
  const ACK = {
    SHADOW: 'I UNDERSTAND SHADOW SENDS NO ORDERS',
    TESTNET: 'I UNDERSTAND TESTNET USES TEST FUNDS',
    LIVE: 'ENABLE LIVE TRADING WITH REAL FUNDS'
  };
  let current = null;

  async function read(){
    const response = await fetch('/api/automation/status', {cache:'no-store'});
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    current = await response.json(); paint();
  }
  function paint(){
    revision.textContent = `revision ${current.revision}`;
    explanation.textContent = (current.reasons || []).map(r => r.summary).join(' ');
    const p = current.promotion || {};
    lock.textContent = p.live_router_build_enabled
      ? 'Promotion gates still apply independently.'
      : 'LIVE remains build-locked even if evidence passes.';
    controls.querySelectorAll('[data-mode]').forEach(button => {
      const mode = button.dataset.mode;
      button.classList.toggle('btn-primary', mode === current.mode);
      button.setAttribute('aria-pressed', String(mode === current.mode));
      const gated = (mode === 'TESTNET' && !p.shadow_ready) ||
                    (mode === 'LIVE' && (!p.live_ready || !p.live_router_build_enabled));
      button.disabled = gated || mode === current.mode;
      button.title = gated ? (mode === 'TESTNET'
        ? 'Locked until 14 shadow days and 100 matching intents pass.'
        : 'Locked until evidence, testnet, safety drills, and a reviewed live build pass.')
        : `Switch to ${mode}`;
    });
  }
  controls.addEventListener('click', async event => {
    const button = event.target.closest('[data-mode]');
    if(!button || button.disabled || !current) return;
    const target = button.dataset.mode;
    const accepted = await SSConfirm({
      title: `Switch to ${target}`,
      lead: target === 'LIVE' ? 'This mode uses real funds.' :
            target === 'TESTNET' ? 'This mode submits orders using test funds.' :
            target === 'SHADOW' ? 'This reads live state and records intent, but submits nothing.' :
            target === 'PAPER' ? 'Orders and positions will be simulated.' :
            'Scanning and recommendations continue; order dispatch stops.',
      rows: [`Current mode: ${current.mode}`, `New mode: ${target}`,
             `Expected revision: ${current.revision}`],
      warn: target === 'LIVE' ? 'LIVE cannot be enabled by this build.' : '',
      confirmLabel: `Use ${target}`, tone: target === 'LIVE' ? 'danger' : 'normal'
    });
    if(!accepted) return;
    button.disabled = true;
    try{
      const response = await fetch('/api/automation/mode', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({mode:target, expected_revision:current.revision,
          acknowledgement:ACK[target] || '', note:'Tactical Cockpit operator change'})});
      const body = await response.json();
      if(!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
      current = body; paint();
      if(window.SSData) SSData.invalidate('/api/operations');
    }catch(err){
      lock.textContent = `Mode change refused: ${err.message}`;
      await read().catch(() => {});
    }
  });
  read().catch(err => {
    explanation.textContent = `Operating mode unavailable: ${err.message}`;
    controls.querySelectorAll('button').forEach(button => button.disabled = true);
  });
})();
