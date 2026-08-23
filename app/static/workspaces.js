/* Focused sub-views for dense cockpit surfaces. This module changes only
   presentation; each panel's existing module remains the authority for data. */
(() => {
  const getSaved = (name, fallback) => {
    try { return sessionStorage.getItem(`ss:${name}-view`) || fallback; }
    catch (_) { return fallback; }
  };
  const save = (name, view) => {
    try { sessionStorage.setItem(`ss:${name}-view`, view); }
    catch (_) { /* private browsing can deny storage; the view still works */ }
  };

  function bind(name, surfaceId, fallback){
    const tabs = document.querySelector(`[data-workspace-tabs="${name}"]`);
    const surface = document.getElementById(surfaceId);
    if(!tabs || !surface) return;
    const buttons = [...tabs.querySelectorAll('button[data-view]')];
    const panels = [...surface.querySelectorAll(`[data-${name}-view]`)];
    const allowed = new Set(buttons.map(button => button.dataset.view));

    const show = requested => {
      const view = allowed.has(requested) ? requested : fallback;
      buttons.forEach(button => {
        const active = button.dataset.view === view;
        button.classList.toggle('on', active);
        button.setAttribute('aria-pressed', String(active));
      });
      panels.forEach(panel => { panel.hidden = panel.dataset[`${name}View`] !== view; });
      surface.dataset.activeView = view;
      save(name, view);
      requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
      dispatchEvent(new CustomEvent('ss:workspace-view', {detail: {name, view}}));
    };

    buttons.forEach(button => button.addEventListener('click', () => show(button.dataset.view)));
    /* THE ROUTER CANNOT REACH THIS VIEW BY WRITING STORAGE. #performance-ledger
       is a real address — a bookmark, the rail's Trade journal link, the 6 key
       — and go() honoured it by setting ss:performance-view and nothing else.
       That is read exactly once, by show(getSaved(...)) below, at load. So the
       route worked from a cold start and was inert every time after: the
       surface switched to Results and the visible view stayed where it was,
       with the requested one arriving on the NEXT page load instead. This is
       the live half of the same instruction. */
    addEventListener('ss:workspace-request', event => {
      const request = event.detail || {};
      if(request.name === name) show(request.view);
    });
    tabs.addEventListener('keydown', event => {
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      const current = buttons.indexOf(document.activeElement);
      if(current < 0) return;
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
        : (current + (event.key === 'ArrowLeft' ? -1 : 1) + buttons.length) % buttons.length;
      event.preventDefault();
      buttons[next].focus();
      show(buttons[next].dataset.view);
    });
    show(getSaved(name, fallback));
  }

  bind('performance', 's-results', 'overview');
  bind('system', 's-settings', 'automation');

  document.querySelectorAll('[data-system-target]').forEach(link => {
    link.addEventListener('click', () => {
      const view = link.dataset.systemTarget;
      save('system', view);
      const button = document.querySelector(`[data-workspace-tabs="system"] button[data-view="${view}"]`);
      if(button) button.click();
    });
  });
})();
