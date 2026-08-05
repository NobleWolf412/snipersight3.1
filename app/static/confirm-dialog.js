/* THE CONFIRMATION AT THE MONEY.

   Arm, Close, Cancel, Halt and Apply were all `window.confirm()`. The CONTENT
   was already the best thing in the product — direction, symbol, timeframe,
   entry with its distance from market, stop with its percentage, target, risk
   in dollars, leverage, the scale-out rung, a flung-level warning, and "PAPER —
   this writes to your paper book. No real order is sent." Every word earned.

   The container was a browser dialog. System font, plain \n layout, glyphs
   rendered at whatever the OS decides, no way to give the risk figure any more
   weight than the timeframe, unstylable, and on some mobile platforms a
   truncated body — which would cut the fling warning that chart.js deliberately
   puts LAST so it cannot be scrolled past. The most consequential four hundred
   milliseconds in the product was the only one that looked like it belonged to
   a different program.

   This is the same shape as the wizard's .dx-modal, deliberately, so the app
   has one dialog language. It does NOT reuse that stylesheet: diagnostics-ui.css
   is lazy-loaded by funnel.js, tracer.js and wizard.js when those mount, and a
   confirmation on the money path must not race a stylesheet fetch to render.
   Its styles live in ss.css, which is always loaded.

   Returns a promise for a boolean, so a call site changes from

       if(!confirm(text)) return;
   to
       if(!await SSConfirm({...})) return;

   and nothing else about the flow moves. */
window.SSConfirm = (() => {
  'use strict';

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  let openDialog = null;          // only ever one; a second call resolves false

  /* A row is either a spacer, a `key: value` pair, or a plain sentence. The
     callers already build their lines this way for the text dialog, so the
     structure is recovered rather than demanded — no call site has to be
     rewritten into a data shape to gain a designed dialog. */
  function rowHtml(line){
    if(!line) return '<div class="ssc-gap"></div>';
    const m = /^([^:]{1,28}):\s+(.+)$/.exec(line);
    if(!m) return `<div class="ssc-line">${esc(line)}</div>`;
    return `<div class="ssc-row"><span class="ssc-k">${esc(m[1])}</span>` +
           `<span class="ssc-v">${esc(m[2])}</span></div>`;
  }

  function build({title, lead, rows, emphasis, warn, note, confirmLabel, tone}){
    const wrap = document.createElement('div');
    wrap.className = 'ssc-wrap';
    wrap.innerHTML = `
      <div class="ssc-scrim" data-ssc="cancel"></div>
      <div class="ssc-box ${tone === 'danger' ? 'danger' : ''}"
           role="alertdialog" aria-modal="true"
           aria-labelledby="ssc-title" aria-describedby="ssc-body">
        <div class="ssc-head"><span class="ssc-title" id="ssc-title">${esc(title)}</span></div>
        <div class="ssc-body" id="ssc-body">
          ${lead ? `<div class="ssc-lead">${esc(lead)}</div>` : ''}
          ${emphasis ? `<div class="ssc-emph">${esc(emphasis)}</div>` : ''}
          ${(rows || []).map(rowHtml).join('')}
          ${warn ? `<div class="ssc-warn">${esc(warn)}</div>` : ''}
        </div>
        <div class="ssc-foot">
          ${note ? `<span class="ssc-note">${esc(note)}</span>` : ''}
          <button class="btn" data-ssc="cancel">Cancel</button>
          <button class="btn ${tone === 'danger' ? 'btn-red' : 'btn-primary'}"
                  data-ssc="ok">${esc(confirmLabel || 'Confirm')}</button>
        </div>
      </div>`;
    return wrap;
  }

  return function ssConfirm(opts){
    const o = opts || {};
    // Never stack. A second confirmation while one is open is a bug upstream,
    // and answering it "no" is the safe reading of an ambiguous moment.
    if(openDialog) return Promise.resolve(false);

    const wrap = build(o);
    const returnFocus = document.activeElement;
    document.body.appendChild(wrap);
    openDialog = wrap;

    const box = wrap.querySelector('.ssc-box');
    const focusables = () => [...box.querySelectorAll('button:not([disabled])')];

    /* Cancel is focused first, not Confirm. Enter is how a keyboard user
       dismisses a dialog they did not mean to open, and on the one screen where
       Enter could size a trade it must not be the thing under the finger. */
    (box.querySelector('[data-ssc="cancel"]') || box).focus();

    return new Promise(resolve => {
      const finish = answer => {
        document.removeEventListener('keydown', onKey, true);
        wrap.remove();
        openDialog = null;
        // give focus back to whatever opened this, or the keyboard is stranded
        if(returnFocus && document.contains(returnFocus)) {
          try { returnFocus.focus(); } catch(e) {}
        }
        resolve(answer);
      };

      function onKey(e){
        if(e.key === 'Escape'){ e.preventDefault(); finish(false); return; }
        if(e.key !== 'Tab') return;
        // focus trap: Tab must not walk out of a modal into the page behind it
        const f = focusables();
        if(!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
        else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
      }

      document.addEventListener('keydown', onKey, true);
      wrap.addEventListener('click', e => {
        const a = e.target.closest('[data-ssc]');
        if(!a) return;
        finish(a.dataset.ssc === 'ok');
      });
    });
  };
})();
