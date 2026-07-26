(() => {
  const button = document.getElementById('diagButton');
  const close = document.getElementById('diagClose');
  const drawer = document.getElementById('diagDrawer');
  const scrim = document.getElementById('scrim');
  const badge = document.getElementById('diagBadge');
  const status = document.getElementById('status');
  const diagnostics = document.getElementById('diagnostics');

  function setOpen(open) {
    drawer.classList.toggle('open', open);
    scrim.classList.toggle('open', open);
    button.setAttribute('aria-expanded', String(open));
    if (open) diagnostics.contentWindow?.postMessage({type: 'snipersight:refresh'}, location.origin);
  }

  button.addEventListener('click', () => setOpen(!drawer.classList.contains('open')));
  close.addEventListener('click', () => setOpen(false));
  scrim.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setOpen(false);
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'd') {
      event.preventDefault();
      setOpen(!drawer.classList.contains('open'));
    }
  });

  async function refreshBadge() {
    try {
      const [telemetryResponse, healthResponse] = await Promise.all([
        fetch('/api/setup-telemetry?limit=500'),
        fetch('/api/pipeline-health')
      ]);
      if (!telemetryResponse.ok || !healthResponse.ok) throw new Error('diagnostics unavailable');
      const telemetry = await telemetryResponse.json();
      const health = await healthResponse.json();
      const diagnosticDefects = (telemetry.records || []).reduce((sum, record) => sum + Number(record.defect_count || 0), 0);
      const blockers = (health.blockers || []).length;
      const actionable = diagnosticDefects + blockers;
      badge.textContent = actionable > 99 ? '99+' : String(actionable);
      badge.classList.toggle('show', actionable > 0);
      button.classList.toggle('alert', actionable > 0);
      status.textContent = actionable > 0
        ? `${actionable} ACTIONABLE DIAGNOSTIC${actionable === 1 ? '' : 'S'}`
        : 'DECISION PROVENANCE · NO ACTIONABLE DEFECTS';
    } catch (error) {
      status.textContent = 'DIAGNOSTICS DEGRADED';
      button.classList.add('alert');
    }
  }

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'snipersight:open-diagnostics') return;
    setOpen(true);
  });

  refreshBadge();
  setInterval(refreshBadge, 60000);
})();
