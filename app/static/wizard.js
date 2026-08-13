/* Diagnose wizard — numbered checks that end in an instruction.

   Ported from snipersight-trading's DiagnoseWizard (docs/SALVAGE §4.4). Its
   value is stated in one line there: "Today that page reports state; this one
   tells you what to do about it." So every step here renders three things —
   the measured value, what it means in plain language, and the action that
   fixes it, with a link to the surface that owns that action.

   Orchestrates existing endpoints only; adds no backend.

   Loud fallback, applied per step rather than per page: an endpoint that could
   not be read produces an explicit `?` UNDETERMINED step naming the failure. It
   never produces a ✓, and it never produces a ✗ either — claiming a check
   failed when it simply could not run is its own kind of lie.

   Public: window.SSWizard.open() / .close() */
(() => {
  'use strict';

  const ROOT = document.getElementById('wizardRoot');
  if (!ROOT) return;

  // Idempotent by design. shell.html loads this file, and funnel.js also boots
  // it defensively (the shell did not always carry the tag). Whichever copy
  // runs first wins; a second execution would bind #btnDiagnose twice and fire
  // two playbook runs per click. Guarding here rather than at the injection
  // site is what makes it order-independent — a parser-inserted tag later in
  // the document is invisible to a querySelector run earlier in the parse.
  if (window.SSWizard) return;

  if (!document.getElementById('dx-css')) {
    const link = document.createElement('link');
    link.id = 'dx-css';
    link.rel = 'stylesheet';
    link.href = '/static/diagnostics-ui.css?v=3';
    document.head.appendChild(link);
  }

  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
  const fmt = n => Number(n).toLocaleString();
  const GLYPH = { pass: '✓', fail: '✗', warn: '!', unknown: '?' };

  // funnel.js owns the plain-English lexicon. Guarded so neither module can
  // take the other down: if it is missing, codes are shown de-underscored.
  const plain = c => (window.SSFunnel && SSFunnel.plain)
    ? SSFunnel.plain(c) : String(c).replace(/_/g, ' ').toLowerCase();
  const explain = c => (window.SSFunnel && SSFunnel.explain) ? SSFunnel.explain(c) : null;

  let open = false, lastFocus = null;

  /* ---------- data ---------- */

  /* The wizard reads five endpoints the shell is already polling. Reading them
     through SSData means opening it costs nothing when the shell has current
     answers, and — more to the point — the wizard's verdict is computed from
     the SAME payloads the surfaces behind it are showing. A diagnosis drawn
     from a different moment than the screen it is diagnosing is worse than no
     diagnosis. */
  const api = path => window.SSData.get(path, 25000);

  // Every step reads from this bag. A rejected entry carries its error string,
  // which is what turns the step into UNDETERMINED rather than a guess.
  async function gather() {
    const paths = ['/api/overview', '/api/health', '/api/pipeline-health',
                   '/api/setup-telemetry?limit=500', '/api/portfolio'];
    const settled = await Promise.allSettled(paths.map(api));
    const names = ['overview', 'health', 'pipeline', 'telemetry', 'portfolio'];
    const out = {};
    settled.forEach((s, i) => {
      out[names[i]] = s.status === 'fulfilled'
        ? { ok: true, d: s.value }
        : { ok: false, err: String(s.reason && s.reason.message || s.reason) };
    });
    return out;
  }

  /* ---------- steps ----------
     Each returns { title, result, value, means, doing, cta }. `value` is always
     the measured figure, so no step is ever just a tick. */

  const undetermined = (title, src, means) => ({
    title, result: 'unknown',
    value: 'could not read ' + src.err,
    means: means + ' This check could not run, so its state is unknown — not OK.',
    doing: 'Reload the page. If it persists, the API server is down or erroring; ' +
           'the backend console on Command shows what it is saying.',
    cta: { href: '#command', label: 'Command' }
  });

  function stepScanner(b) {
    const T = 'Is the scanner running?';
    const M = 'The scanner is the process that pulls market data, maps structure ' +
              'and looks for setups.';
    if (!b.overview.ok) return undetermined(T, b.overview, M);
    const sc = b.overview.d.scanner || {};
    if (sc.alive) return {
      title: T, result: 'pass',
      value: `heartbeat ${sc.age_s}s ago · ${fmt(sc.cycles || 0)} cycles · ${sc.phase || 'idle'}`,
      means: M + ' It is beating, so new data and new setups can appear.'
    };
    return {
      title: T, result: 'fail',
      value: sc.age_s == null ? 'no heartbeat ever recorded' : `silent for ${sc.age_s}s`,
      means: M + ' It is not running. Nothing new can appear no matter how ' +
             'everything else is configured — this is the first thing to fix.',
      /* The instruction used to end in prose: "…then restart the background
         scanner" — with no way to do it. /api/system/restart existed the whole
         time, purpose-built and wired to nothing, so the wizard diagnosed the
         fault and then told the operator to go find a terminal. The button IS
         the instruction now; the watchdog respawns what it stops, and the
         endpoint refuses outright when no watchdog is supervising, which the
         result line reports verbatim. */
      doing: 'Restart it. The watchdog stops the scanner and respawns it in a ' +
             'few seconds; if nothing is supervising, the restart is refused ' +
             'and says so.',
      action: { id: 'restart-scanner', label: 'Restart scanner',
                confirm: 'Restart the background scanner?\n\nThe current scan ' +
                         'pass is abandoned and restarts from the top in ~5s. ' +
                         'Recorded facts are append-only — nothing is lost.',
                url: '/api/system/restart?target=scanner' }
    };
  }

  function stepUniverse(b) {
    const T = 'Does it have anything to scan?';
    const M = 'The universe is the list of tokens the scanner is allowed to look at.';
    if (!b.overview.ok) return undetermined(T, b.overview, M);
    const syms = b.overview.d.symbols || [];
    const admitted = syms.filter(s => s.state !== 'WARMING');
    if (admitted.length) return {
      title: T, result: 'pass',
      value: `${fmt(admitted.length)} tokens admitted of ${fmt(syms.length)} tracked`,
      means: M + ' It has tokens to work on.'
    };
    if (syms.length) return {
      title: T, result: 'warn',
      value: `0 admitted · ${fmt(syms.length)} still warming up`,
      means: M + ' Every token is still building the price history the engines ' +
             'need before they are allowed to produce facts.',
      doing: 'Wait for the import to finish, or run a scan to pull more history.',
      cta: { href: '#command', label: 'Command' }
    };
    return {
      title: T, result: 'fail', value: 'the universe is empty',
      means: M + ' It is empty, so there is nothing to scan and nothing can ever fire.',
      doing: 'Open Rules and check the universe settings — a minimum volume ' +
             'or minimum history threshold may be excluding every token.',
      cta: { href: '#settings', label: 'Settings' }
    };
  }

  function stepCycles(b) {
    const T = 'Has it completed a full pass recently?';
    const M = 'A cycle is one complete sweep of the universe: import candles, ' +
              'map structure, look for setups, size them.';
    if (!b.overview.ok) return undetermined(T, b.overview, M);
    const sc = b.overview.d.scanner || {};
    if (!sc.alive) return {
      title: T, result: 'fail',
      value: sc.age_s == null ? 'no heartbeat' : `last beat ${sc.age_s}s ago`,
      means: M + ' No cycle can complete while the scanner is down.',
      doing: 'Fix check 1 first — the rest of this list is downstream of it.',
      cta: { href: '#command', label: 'Command' }
    };
    if (!sc.cycles) return {
      title: T, result: 'warn',
      value: `0 cycles finished · currently ${sc.phase || 'idle'}`,
      means: M + ' It is alive but has not finished its first pass yet, so the ' +
             'counts below will be empty or partial. That is expected right ' +
             'after a restart.',
      doing: 'Give it one full pass and re-run this check.',
      cta: { href: '#command', label: 'Command' }
    };
    return {
      title: T, result: 'pass',
      value: `${fmt(sc.cycles)} cycles · last beat ${sc.age_s}s ago · ` +
             `${fmt(sc.last_new_candles || 0)} new candles, ${fmt(sc.last_new_setups || 0)} new setups last pass`,
      means: M + ' It is completing them.'
    };
  }

  function stepData(b) {
    const T = 'Is the price data healthy?';
    const M = 'Setups are only as trustworthy as the candles behind them.';
    if (!b.health.ok) return undetermined(T, b.health, M);
    const h = b.health.d;
    /* `stale_series` counts only MAINTAINED series — the ones the scanner
       actually refreshes. Everything else in the store is history for symbols
       outside the scan universe, which ages by design and which no scan will
       ever bring current. This step used to count those too and then tell the
       operator to "run a scan to re-import", an instruction that could never
       succeed: 227 permanently stale series, a permanent DEGRADED, and a
       permanent piece of advice that did nothing (UX audit, 4 Aug 2026). */
    const stale = (h.stale_series || []).length;
    const stored = h.stored_stale_count || 0;
    // Said the same way whether the step passes or not, so the number never
    // reappears later as a surprise.
    const aside = stored
      ? ` ${fmt(stored)} more are history for tokens outside the scan list — ` +
        `those age by design and no scan changes them.`
      : '';
    if (h.status === 'OK') return {
      title: T, result: 'pass',
      value: `database ${h.database} · ${fmt(h.maintained_series || 0)} ` +
             `scanned series, all current`,
      means: M + ' Every series the scanner maintains is current and the store ' +
             'passes its integrity check.' + aside
    };
    return {
      title: T, result: stale ? 'warn' : 'fail',
      value: `${h.status} · database ${h.database} · ${fmt(stale)} stale of ` +
             `${fmt(h.maintained_series || 0)} scanned · ` +
             `${fmt(h.bad_candles_rejected || 0)} bad candles rejected`,
      means: M + (stale
        ? ' A token the scanner is supposed to keep current stopped updating, ' +
          'so any setup on it is being judged on old prices.'
        : ' The fact store failed its integrity check, which is more serious ' +
          'than stale data — numbers built on it cannot be trusted.') + aside,
      doing: stale
        ? 'Run a scan to re-import. If it stays stale, the venue is not ' +
          'returning candles for that token.'
        : 'Stop trading decisions on these numbers and rebuild the store.',
      cta: { href: '#command', label: 'Command' }
    };
  }

  function stepPipeline(b) {
    const T = 'Does the pipeline audit pass?';
    const M = 'The audit re-checks that every fact the engines produced obeys its ' +
              'contract, end to end.';
    if (!b.pipeline.ok) return undetermined(T, b.pipeline, M);
    const p = b.pipeline.d;
    if (p.pending) return {
      title: T, result: 'unknown', value: 'first audit still running',
      means: M + ' It has not produced a verdict yet.',
      doing: 'Wait for the scanner to finish, then press Refresh on Diagnostics.',
      cta: { href: '#diagnostics', label: 'Diagnostics' }
    };
    const blockers = (p.blockers || []).length, warns = (p.warnings || []).length;
    if (p.evaluation_allowed && !blockers) return {
      title: T, result: warns ? 'warn' : 'pass',
      value: `${p.status} · ${blockers} blockers · ${warns} warnings`,
      means: M + (warns
        ? ' Nothing is blocking, but there are open warnings worth reading.'
        : ' It passes, so the performance numbers are safe to read.'),
      doing: warns ? 'Open Diagnostics and read the Open Issues list.' : undefined,
      cta: warns ? { href: '#diagnostics', label: 'Diagnostics' } : undefined
    };
    return {
      title: T, result: 'fail',
      // status is already "BLOCKED" in the common case; do not say it twice
      value: `${p.status}${p.evaluation_allowed || p.status === 'BLOCKED' ? '' : ' · BLOCKED'} · ` +
             `${fmt(blockers)} blockers · ${fmt(warns)} warnings`,
      means: M + ' A blocker means a fact broke its contract, so every ' +
             'performance figure downstream of it is suspect until it is fixed.',
      doing: 'Open Diagnostics → Open Issues for the exact codes, then press ' +
             'Refresh once they are addressed.',
      cta: { href: '#diagnostics', label: 'Diagnostics' }
    };
  }

  /* The funnel question, condensed into one step. Numbers come from the API's
     own funnel object; the only arithmetic is subtraction between two of its
     fields to find the largest drop. */
  function stepWhereDying(b) {
    const T = 'Where are setups dying?';
    const M = 'Every candidate travels the same road: zone touched → validated ' +
              '→ risk approved → order → fill → close.';
    if (!b.telemetry.ok) return undetermined(T, b.telemetry, M);
    const f = b.telemetry.d.funnel || {};
    const rejected = f.rejected_candidates || 0;
    const chain = [
      ['candidates',    rejected + (f.validated || 0)],
      ['validated',     f.validated || 0],
      ['risk approved', f.risk_approved || 0],
      ['orders placed', f.order_placed || 0],
      ['fills',         f.filled || 0],
      ['closed',        f.closed || 0],
      ['winners',       f.winners || 0]
    ];
    const value = chain.map(([k, n]) => `${fmt(n)} ${k}`).join(' → ');
    if (!chain[0][1]) return {
      title: T, result: 'warn', value: 'no candidates recorded in this window',
      means: M + ' Nothing has been examined yet, so nothing has been rejected. ' +
             'An empty funnel is not a healthy funnel.',
      doing: 'Run a scan, or wait for the scanner to finish a cycle.',
      cta: { href: '#command', label: 'Command' }
    };

    let worst = null;
    for (let i = 1; i < chain.length; i++) {
      const drop = Math.max(0, chain[i - 1][1] - chain[i][1]);
      if (drop > 0 && (!worst || drop > worst.drop))
        worst = { drop, at: chain[i][0], from: chain[i - 1][1], i };
    }
    if (!worst) return {
      title: T, result: 'pass', value,
      means: M + ' Nothing is being lost between stages.'
    };

    // Name the dominant reason for the worst transition, using the same
    // authoritative maps the funnel reads.
    const fails = b.telemetry.d.failure_points || {};
    const cand = b.telemetry.d.candidate_rejections || {};
    const map = worst.i === 1 ? cand : fails;
    const top = Object.entries(map).sort((a, c) => c[1] - a[1])[0];
    const meta = top ? explain(top[0]) : null;
    return {
      title: T, result: 'warn', value,
      means: M + ` The biggest loss is into ${worst.at}: ` +
             `${fmt(worst.drop)} of ${fmt(worst.from)} ` +
             `(${Math.round(100 * worst.drop / worst.from)}%) stop there` +
             (top ? `, most often because ${plain(top[0])}.` : '.'),
      doing: meta && meta.means
        ? meta.means + ' The funnel on Diagnostics breaks this down stage by ' +
          'stage, and each setup can be traced individually.'
        : 'Open the funnel on Diagnostics and click that stage to see the reasons.',
      cta: meta && meta.cta ? meta.cta : { href: '#diagnostics', label: 'Diagnostics' }
    };
  }

  function stepRisk(b) {
    const T = "Are the bot's safety checks skipping trades, and why?";
    const M = 'These checks decide whether a valid setup can be given a safe ' +
              'position size. They can skip a good setup because of account limits.';
    if (!b.telemetry.ok) return undetermined(T, b.telemetry, M);
    const t = b.telemetry.d;
    const rejected = (t.failure_points || {}).RISK_REJECTED || 0;
    if (!rejected) return {
      title: T, result: 'pass',
      value: `0 setups refused · ${fmt((t.funnel || {}).risk_approved || 0)} approved`,
      means: M + ' They have skipped nothing in this window.'
    };
    // The COUNT comes from failure_points, which is computed over the whole
    // window. records[] is a recent slice, so it is used only to name which
    // reasons occur — never to count them.
    //
    // Only REJECTED records contribute: an approved setup also carries a
    // risk_reasons list (["WITHIN_LIMITS"]), and reading those here would
    // report "every risk rule passed" as the reason trades were refused.
    const seen = [];
    for (const r of (t.records || [])) {
      if (r.risk_decision !== 'REJECTED') continue;
      for (const reason of (r.risk_reasons || []))
        if (reason !== 'WITHIN_LIMITS' && !seen.includes(reason)) seen.push(reason);
    }
    const top = seen[0];
    const meta = top ? explain(top) : null;
    return {
      title: T, result: 'warn',
      value: `${fmt(rejected)} setups skipped by safety checks · reasons seen: ${
        seen.length ? seen.map(plain).join(', ') : 'none recorded'}`,
      means: M + (top ? ` The reasons recorded include ${plain(top)}.` :
             ' No reason was recorded on the recent skipped setups, which needs investigation.'),
      doing: meta && meta.means ? meta.means
        : 'Open a trace on any refused setup from the funnel to see the exact rule.',
      cta: meta && meta.cta ? meta.cta : { href: '#settings', label: 'Settings' }
    };
  }

  function stepForwardRecord(b) {
    const T = 'Does the forward record contain anything to judge?';
    const M = 'The forward record is the paper track accumulated since the ' +
              'current baseline. Results before it belong to an older engine.';
    if (!b.portfolio.ok) return undetermined(T, b.portfolio, M);
    const p = b.portfolio.d;
    const d = p.decisions || {};
    const total = (d.APPROVED || 0) + (d.REDUCED || 0) + (d.REJECTED || 0);
    // != null, not truthiness: an epoch of 0 is a real timestamp, and printing
    // "unknown" for it would invent a missing value that is not missing.
    const started = p.baseline && p.baseline.started_at != null
      ? new Date(p.baseline.started_at * 1000).toISOString().slice(0, 10) : 'an unknown date';
    if (total) return {
      title: T, result: 'pass',
      value: `${fmt(total)} decisions since ${started} · ${fmt(d.APPROVED || 0)} allowed, ` +
             `${fmt(d.REDUCED || 0)} allowed smaller, ${fmt(d.REJECTED || 0)} skipped`,
      means: M + ' It has decisions in it, so the numbers on Results mean something.'
    };
    return {
      title: T, result: 'fail',
      value: `0 decisions since ${started}`,
      means: M + ' It is empty. The account safety checks have not decided a single ' +
             'setup, so every figure on Results is a placeholder rather than a ' +
             'result. Nothing about the strategy can be concluded yet.',
      doing: 'This is normal immediately after a baseline reset or a rule change. ' +
             'Run a scan and let at least one full cycle complete.',
      cta: { href: '#command', label: 'Command' }
    };
  }

  const CHECKS = [stepScanner, stepUniverse, stepCycles, stepData, stepPipeline,
                  stepWhereDying, stepRisk, stepForwardRecord];

  /* ---------- render ---------- */

  function summary(steps) {
    const fails = steps.filter(s => s.result === 'fail');
    const unknown = steps.filter(s => s.result === 'unknown');
    const warns = steps.filter(s => s.result === 'warn');
    if (fails.length) return { cls: 'bad', html:
      `<b>${fails.length} of ${steps.length} checks failed.</b> Start with number
       ${steps.indexOf(fails[0]) + 1} — ${esc(fails[0].title.replace(/\?$/, ''))} —
       because the checks below it are downstream of it.` };
    if (unknown.length) return { cls: 'warn', html:
      `<b>${unknown.length} check${unknown.length > 1 ? 's' : ''} could not run.</b>
       Everything that did run passed, but an unread check is not a passed check.` };
    if (warns.length) return { cls: 'warn', html:
      `<b>Nothing is broken.</b> ${warns.length} check${warns.length > 1 ? 's' : ''}
       flagged something worth understanding — most often where candidates are
       being lost, which is normal attrition rather than a fault.` };
    return { cls: 'ok', html:
      '<b>All checks pass.</b> The scanner is running, the data is current, the ' +
      'audit is clean and the forward record is accumulating.' };
  }

  function paint(bodyHtml, footHtml) {
    ROOT.innerHTML = `<div class="dx-scrim" data-close="1"></div>
      <div class="dx-modal-wrap">
        <div class="dx-modal" role="dialog" aria-modal="true" aria-label="Diagnose">
          <div class="dx-modal-head">
            <span class="dx-modal-title">Diagnose</span>
            <button class="btn" data-rerun="1" style="margin-left:auto">Re-run</button>
            <button class="btn" data-close="1">Close</button>
          </div>
          <div class="dx-modal-body">${bodyHtml}</div>
          <div class="dx-modal-foot">${footHtml || ''}</div>
        </div>
      </div>`;
    open = true;
  }

  function render(steps) {
    const s = summary(steps);
    const body = `<div class="dx-summary ${s.cls}">${s.html}</div>
      <div class="dx-steps">` + steps.map((st, i) => `
        <div class="dx-step ${st.result}">
          <span class="dx-step-n">${i + 1}</span>
          <span class="dx-step-glyph">${GLYPH[st.result] || '?'}</span>
          <span>
            <span class="dx-step-title">${esc(st.title)}</span>
            <span class="dx-step-value">${esc(st.value)}</span>
            <span class="dx-step-means">${esc(st.means)}</span>
            ${st.doing ? `<span class="dx-step-do"><b>What to do</b>${esc(st.doing)}</span>` : ''}
            ${st.cta ? `<span class="dx-step-cta">
              <a class="btn" href="${st.cta.href}" data-close="1">Open ${esc(st.cta.label)} →</a>
            </span>` : ''}
            ${st.action ? `<span class="dx-step-cta">
              <button class="btn" data-action="${esc(st.action.id)}"
                data-url="${esc(st.action.url)}"
                data-confirm="${esc(st.action.confirm || '')}">${esc(st.action.label)}</button>
              <span class="t-mono dx-action-result" data-result-for="${esc(st.action.id)}"></span>
            </span>` : ''}
          </span>
        </div>`).join('') + '</div>';
    paint(body, 'Read-only · five endpoints · nothing here changes any setting');
  }

  /* ---------- lifecycle ---------- */

  function close() {
    ROOT.innerHTML = '';
    open = false;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
  }

  async function run() {
    paint('<div class="dx-load">running the checks…</div>', '');
    try {
      const bag = await gather();
      render(CHECKS.map(fn => fn(bag)));
    } catch (err) {
      // A throw here means the wizard itself broke, not an endpoint. Say that
      // rather than presenting a half-run playbook as a verdict.
      paint(`<div class="dx-fail"><b>the wizard could not run</b>
        <code>${esc(err && err.message || err)}</code>
        <span class="dx-fail-what">No conclusions are shown because none were
        reached. This is a fault in the page, not a report about the engine.</span>
      </div>`, '');
    }
  }

  function openWizard() {
    lastFocus = document.activeElement;
    run();
  }

  ROOT.addEventListener('click', async e => {
    /* A step's action button. The same rules as every other action in the app:
       it confirms before anything irreversible-feeling, it reports its RESULT
       and TIME beside the control, and a refusal (no watchdog supervising) is
       shown verbatim rather than dressed up as success. The wizard re-runs
       after a short wait so the step verdicts reflect what the restart did. */
    const act = e.target.closest('[data-action]');
    if (act) {
      if (act.dataset.confirm && !confirm(act.dataset.confirm)) return;
      const out = ROOT.querySelector(`[data-result-for="${act.dataset.action}"]`);
      const stamp = () => new Date().toISOString().slice(11, 19) + 'Z';
      act.disabled = true;
      if (out) out.textContent = 'asking…';
      try {
        const r = await fetch(act.dataset.url, { method: 'POST' });
        const d = await r.json().catch(() => ({}));
        if (out) out.textContent = (r.ok
          ? (d.detail || 'restarting — back in a few seconds')
          : (d.detail || 'refused → HTTP ' + r.status)) + ' · ' + stamp();
        if (r.ok) setTimeout(run, 8000);      // re-diagnose against the new state
      } catch (err) {
        if (out) out.textContent = 'could not reach the server · ' + stamp();
      }
      act.disabled = false;
      return;
    }
    if (e.target.closest('[data-rerun]')) { run(); return; }
    if (e.target.closest('[data-close]')) close();
  });
  document.addEventListener('keydown', e => { if (open && e.key === 'Escape') close(); });

  /* Two doors, one room. The Diagnostics one has always existed, buried in a
     panel called "Why nothing fired" on the surface that looks like it is for
     engineers; the audit found that a newcomer would never reach the single
     most useful thing in the app. The Command one is the fix. */
  for (const id of ['btnDiagnose', 'btnDiagnoseCmd']) {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', openWizard);
  }

  window.SSWizard = { open: openWizard, close };
})();
