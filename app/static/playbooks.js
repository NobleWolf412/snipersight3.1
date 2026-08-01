/* Playbook catalogue — the answer to "what strategies exist, how do they work,
   and are they actually working?" for someone who has never traded.

   Three house rules shape everything below.

   1. LOUD FALLBACK. A failed fetch says so, in the space the catalogue would
      have occupied. It must never look like "no strategies exist" — that is a
      different and much worse claim than "the catalogue could not be read".

   2. ONE AUTHORITY PER NUMBER. Every figure on a card comes from
      /api/playbooks, which takes the records straight from /api/performance.
      This file computes no win rate, sums no R, and derives no percentage. When
      the cockpit last re-derived a number the engine already owned, the two
      disagreed and the operator chased a phantom (2026-07-26).

   3. NOTHING SILENTLY RESETS A TRACK RECORD. The enable toggle writes to
      /api/settings, where the strategy switches are BEHAVIOURAL: applying one
      starts a new forward window. The warning is shown BEFORE the write, in the
      same words the settings panel uses, and the new baseline is reported back.

   Mounts into #playbookRoot, which is this module's only contract with the
   shell. It edits no other module's markup and no other module's stylesheet. */
(() => {
  const ROOT = document.getElementById('playbookRoot');
  if (!ROOT) return;                    // shell without the mount point: stay out

  // The <link> is injected from here rather than added to shell.html so this
  // module owns every file it needs and can be removed in one piece.
  if (!document.querySelector('link[data-pb]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/playbooks.css?v=1';
    link.dataset.pb = '1';
    document.head.appendChild(link);
  }

  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'}[c]));

  /* ---------- glossary linking ----------
     The API returns plain prose; the dotted-underline markup is applied here so
     the server never has to know how the UI explains itself. Longest phrases
     first, because alternation matches leftmost-first and "demand zone" has to
     win over "zone". One link per term per block: a paragraph where every other
     word is underlined is noise, not help. */
  const TERMS = [
    ['liquidity sweep', 'sweep'], ['stop hunt', 'sweep'],
    ['break of structure', 'bos'],
    ['demand zone', 'demand'], ['supply zone', 'supply'],
    ['entry price', 'entry'],
    ['zones', 'zone'], ['zone', 'zone'],
    ['liquidity', 'liquidity'],
    ['setups', 'setup'], ['setup', 'setup'],
    ['playbooks', 'playbook'], ['playbook', 'playbook'],
    ['rank', 'rank'], ['target', 'tp'],
  ];
  const TERM_RE = new RegExp('\\b(' + TERMS.map(t => t[0]).join('|') + ')\\b', 'gi');
  function gloss(text) {
    const used = new Set();
    return esc(text).replace(TERM_RE, m => {
      const hit = TERMS.find(t => t[0] === m.toLowerCase());
      if (!hit || used.has(hit[1])) return m;
      used.add(hit[1]);
      return `<span class="term" data-t="${hit[1]}">${m}</span>`;
    });
  }

  /* ---------- state ---------- */
  let data = null;          // /api/playbooks
  let specByName = {};      // setting name -> /api/settings spec entry
  let error = null;         // last load failure, shown rather than swallowed
  const pending = {};       // key -> the value the operator is about to apply
  const busy = {};          // key -> a POST is in flight
  const notice = {};        // key -> what happened after the last apply

  /* Through SSData, which sends no-store on every request for the reason this
     module originally set it: the endpoint reports a LIVE record, and a
     heuristically cached response would keep showing a stale win rate on a page
     whose whole claim is that its numbers are current. Freshness is now an
     explicit window rather than the browser's guess. /api/settings is shared
     with the shell, so the strategy toggles here and the settings panel there
     can no longer be a poll period apart. */
  const api = path => window.SSData.get(path, 25000);

  const day = ts => ts ? new Date(ts * 1000).toISOString().slice(0, 10) : 'unknown';
  const num = n => Number(n).toLocaleString();
  const money = v => (v < 0 ? '-' : '+') + '$' +
    Math.abs(Number(v)).toLocaleString(undefined, {maximumFractionDigits: 0});

  /* ---------- the record line ----------
     The reason this surface is not a brochure. A losing playbook prints its
     loss, in red, on its own card. */
  function recordLine(p) {
    const r = p.record;
    if (!r) return '';
    if (!r.n) {
      // A "0% win rate" is a claim about trades that happened. None have, so
      // the card says which window is empty and when it opened instead.
      return `<div class="pb-record empty"><span class="pb-k">Record</span><br>
        No closed trades since ${day(data.baseline && data.baseline.started_at)} —
        this <span class="term" data-t="baseline">baseline</span> has not
        produced one yet.</div>`;
    }
    const sr = Number(r.sum_r);
    const cls = sr > 0 ? 'up' : sr < 0 ? 'down' : 'flat';
    const sized = r.sized
      ? `<span class="pb-sep">·</span>
         <span class="pb-r"><span class="term" data-t="paper">${money(r.pnl_usd)}</span></span>
         <span style="color:var(--fg-4)">across ${num(r.sized)} sized</span>`
      : `<span class="pb-sep">·</span>
         <span style="color:var(--fg-4)">none sized yet</span>`;
    return `<div class="pb-record ${cls}">
      <span class="pb-k">Record</span>
      <b>${num(r.n)}</b> trades
      <span class="pb-sep">·</span>
      ${r.win_pct == null ? '' : `<b>${r.win_pct}%</b> win <span class="pb-sep">·</span>`}
      <b class="pb-r"><span class="term" data-t="rMultiple">${sr > 0 ? '+' : ''}${sr.toFixed(1)}R</span></b>
      ${sized}
    </div>`;
  }

  function toggleMarkup(p) {
    if (p.status !== 'live') return '';
    const on = p.enabled !== false;
    const label = on ? 'On' : 'Off';
    return `<button class="pb-toggle${on ? ' on' : ''}" data-toggle="${p.key}"
      aria-pressed="${on}" ${busy[p.key] ? 'disabled' : ''}
      title="${on ? 'Stop' : 'Start'} trading ${esc(p.name)} setups">${
      busy[p.key] ? 'Saving' : label}</button>`;
  }

  /* The confirmation step. Deliberately not a native confirm(): the operator
     has to be able to read what a new forward window costs, and a browser
     dialog is the wrong place for a sentence that matters. */
  function confirmMarkup(p) {
    if (!(p.key in pending)) return '';
    const want = pending[p.key];
    const spec = specByName[p.setting] || {};
    const behavioural = spec.class === 'BEHAVIOURAL';
    return `<div class="tk-warn">
      Turning <b>${esc(p.name)}</b> ${want ? 'ON' : 'OFF'} changes what the
      scanner is allowed to trade.
      ${behavioural ? `<br><br>This starts a <b>NEW forward window</b>. Your
        existing record is kept but stops accumulating, so the numbers on this
        page restart. Nothing is deleted.` : ''}
      <div class="pb-actions" style="margin-top:var(--md)">
        <button class="btn" data-cancel="${p.key}">Cancel</button>
        <button class="btn btn-cyan" data-apply="${p.key}">Apply</button>
      </div>
    </div>`;
  }

  function noticeMarkup(p) {
    const n = notice[p.key];
    if (!n) return '';
    return `<div class="tk-verdict ${n.kind}">${n.html}</div>`;
  }

  function rule(label, term, body, extra) {
    if (!body) return '';
    const dt = term ? `<span class="term" data-t="${term}">${label}</span>` : label;
    return `<div class="pb-rule"><dt>${dt}</dt><dd>${gloss(body)}${extra || ''}</dd></div>`;
  }

  function card(p) {
    const planned = p.status === 'planned';
    const tfs = (p.timeframes || []).length
      ? `<div class="pb-tfs">${p.timeframes.map(t =>
          `<span class="chip">${esc(t)}</span>`).join('')}</div>`
      : '';
    return `<article class="panel pb-card${planned ? ' planned' : ''}" data-key="${p.key}">
      <div class="panel-head">
        <span class="pb-name">${esc(p.name)}</span>
        ${planned ? '<span class="chip chip-amber">planned</span>'
                  : '<span class="chip">live</span>'}
        ${toggleMarkup(p)}
      </div>
      <div class="panel-body">
        <p class="pb-lede">${gloss(p.one_liner)}</p>
        ${noticeMarkup(p)}
        ${confirmMarkup(p)}
        <dl class="pb-rules">
          ${rule('Hunts', 'regime', p.hunts)}
          ${rule('Triggers', null, p.triggers)}
          ${rule('Confirms', 'confirmation', p.confirms)}
          ${rule('Stop goes', 'sl', p.stop_goes)}
          ${rule('Holds for', 'horizon', p.holds_for, tfs)}
        </dl>
        ${p.notes ? `<div class="pb-note">${gloss(p.notes)}</div>` : ''}
        ${planned
          ? `<div class="pb-gap"><em>Why it matters</em>${gloss(p.gap)}</div>`
          : recordLine(p)}
      </div>
    </article>`;
  }

  function head(counts) {
    return `<div class="pb-head">
      <span class="t-section"><span class="term" data-t="playbook">Playbook</span>
        Catalogue</span>
      <div class="pb-counts">${counts}</div>
    </div>`;
  }

  function render() {
    if (error) {
      // Loud fallback. An empty grid here would read as "this bot has no
      // strategies", which is a lie the operator has no way to detect.
      ROOT.innerHTML = head('') + `<div class="tk-warn">
        <b>The playbook catalogue could not be loaded.</b><br>${esc(error)}<br><br>
        This is a failed request, not an empty catalogue: the strategies could
        not be read, which is not the same as there being none.
        <div class="pb-actions" style="margin-top:var(--md)">
          <button class="btn" data-retry="1">Retry</button>
        </div></div>`;
      return;
    }
    if (!data) {
      ROOT.innerHTML = head('') +
        '<div class="pb-sub">Reading the strategy catalogue…</div>';
      return;
    }
    const live = data.playbooks.filter(p => p.status === 'live');
    const planned = data.playbooks.filter(p => p.status === 'planned');
    const counts = `<span class="chip">${live.length} live</span>` +
      `<span class="chip chip-amber">${planned.length} planned</span>`;
    const s = data.rejection_sample || {};
    ROOT.innerHTML = head(counts) + `
      <p class="pb-sub">Every strategy the scanner can run, what each one looks
        for, and what it has actually done. The records include the losing ones:
        a catalogue that hid them would be advertising, and there would be no
        honest way to choose between these.</p>
      <div class="pb-grid">${data.playbooks.map(card).join('')}</div>
      <div class="pb-foot">
        Records cover the active forward window
        (<b>${esc((data.baseline || {}).label || 'unnamed')}</b>, started
        ${day((data.baseline || {}).started_at)}) and are the same numbers the
        Results page reports — they are not recalculated here.<br>
        Planned-playbook percentages are counted from
        <b>${num(s.total || 0)}</b> recorded
        <span class="term" data-t="rejection">rejections</span>
        , not written down.
      </div>`;
  }

  /* ---------- the write path ---------- */
  async function apply(key) {
    const p = data.playbooks.find(x => x.key === key);
    if (!p || !p.setting) return;
    const want = pending[key];
    busy[key] = true; delete pending[key]; delete notice[key];
    render();
    try {
      const r = await fetch('/api/settings', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({changes: {[p.setting]: want},
                              note: 'playbook catalogue'})});
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || ('settings → ' + r.status));
      notice[key] = d.baseline
        // Say it plainly and immediately. A user who discovers on their own
        // that the track record restarted stops trusting every other number.
        ? {kind: 'warn', html: `<b>New forward window started</b> (baseline #${
            d.baseline.id}). Your previous record is retained but stops
            accumulating; the record below now starts from here.`}
        : {kind: 'ok', html: '<b>Saved.</b> No forward window was reset.'};
    } catch (err) {
      notice[key] = {kind: 'bad', html:
        '<b>Not saved.</b> ' + esc(String(err && err.message || err)) +
        ' — the switch is unchanged.'};
    }
    busy[key] = false;
    /* The write just changed what every cached read of these paths says. Drop
       them before reloading, or the catalogue repaints from the answer it got
       BEFORE the toggle and silently shows the operator the state they just
       changed away from. */
    window.SSData.invalidate('/api/settings');
    window.SSData.invalidate('/api/playbooks');
    await load();
  }

  ROOT.addEventListener('click', e => {
    const t = e.target.closest('[data-toggle]');
    const c = e.target.closest('[data-cancel]');
    const a = e.target.closest('[data-apply]');
    const r = e.target.closest('[data-retry]');
    if (t) {
      const p = data.playbooks.find(x => x.key === t.dataset.toggle);
      // never write on the click itself — the warning has to be readable first
      pending[t.dataset.toggle] = !(p.enabled !== false);
      delete notice[t.dataset.toggle];
      render();
    } else if (c) {
      delete pending[c.dataset.cancel];
      render();
    } else if (a) {
      apply(a.dataset.apply);
    } else if (r) {
      error = null; render(); load();
    }
  });

  async function load() {
    try {
      const [pb, st] = await Promise.all([
        api('/api/playbooks'),
        // read only for the setting CLASS: whether a switch resets the forward
        // window is settings.py's call, and asking it beats assuming it here
        api('/api/settings').catch(() => ({spec: []})),
      ]);
      data = pb;
      specByName = {};
      for (const s of (st.spec || [])) specByName[s.name] = s;
      error = null;
    } catch (err) {
      error = String(err && err.message || err);
    }
    render();
  }

  render();
  load();
  setInterval(load, 60000);
  // shell.js owns navigation and emits no event, so the hash is the cheapest
  // honest signal that this surface just became visible.
  addEventListener('hashchange', () => {
    // `setup` still accepted: the surface was renamed to `rules` and old
    // bookmarks keep working, so this has to answer to both names or the
    // catalogue silently stops refreshing for anyone using an old link.
    const s = location.hash.slice(1);
    if (s === 'rules' || s === 'setup') load();
  });
})();
