/* Bottleneck funnel — "why is nothing firing?", answered in one sentence.

   Ported from snipersight-trading's GauntletBreakdown (docs/SALVAGE §4.2). The
   thing worth porting was never the three-column chrome; it was the insight
   pill. A flat list of rejection counts is a wall of numbers that an operator
   has to rank in their head. This surface does the ranking, names the single
   largest drop-off in plain English, and links to the surface that addresses
   it. With 88% of rejections at one stage, a bottleneck pill would have
   surfaced that on day one.

   House rules honoured here:
     · Loud fallback. A failed fetch prints the endpoint and the status. It
       never renders a confident-looking zero, and it never renders an empty
       state that could be misread as "all clear".
     · One authority per number. Every count is read from an API field. The
       only arithmetic performed in this file is subtraction between two API
       numbers to get a drop-off, and the definitional identity
       candidates = validated + rejected_candidates, which is stated on screen
       rather than hidden.
     · Vanilla, no build, no framework, no CDN. */
(() => {
  'use strict';

  const ROOT = document.getElementById('funnelRoot');
  if (!ROOT) return;                       // not the shell — nothing to mount into

  /* ---------- boot ---------- */

  // Each module injects the shared diagnostics stylesheet itself so it can be
  // cached and broken independently of ss.css, which another surface owns.
  if (!document.getElementById('dx-css')) {
    const link = document.createElement('link');
    link.id = 'dx-css';
    link.rel = 'stylesheet';
    link.href = '/static/diagnostics-ui.css?v=3';
    document.head.appendChild(link);
  }

  // Defensive boot for the wizard. shell.html now carries its own <script> tag
  // for it, but it did not always, and the shell is owned elsewhere. wizard.js
  // early-returns if it has already registered, so loading it twice is a
  // no-op rather than a double-bound Diagnose button.
  /* The check must find the SHELL'S tag, not only a previous injection of our
     own. Since every script in shell.html gained `defer`, execution order puts
     funnel.js before wizard.js — so `window.SSWizard` is undefined here and the
     old test (which only looked for `data-dx-wizard`) injected a second copy on
     every load. wizard.js guards its own re-execution, so nothing broke; it was
     simply a wasted request that nothing reported. */
  if (!window.SSWizard && !document.querySelector('script[src*="wizard.js"]')) {
    const s = document.createElement('script');
    s.src = '/static/wizard.js?v=1';
    s.dataset.dxWizard = '1';
    document.head.appendChild(s);
  }

  /* ---------- plain language ----------
     Every machine reason the operator can see gets a sentence a non-expert can
     act on, plus the surface that addresses it. A code with no entry falls back
     to a de-underscored version of itself and no CTA — guessing at a meaning we
     do not have would be worse than showing the raw code. */

  const SETUP_SURFACE  = { href: '#settings',    label: 'Settings' };
  const CHART_SURFACE  = { href: '#chart',       label: 'Chart' };
  const RESULTS_SURF   = { href: '#results',     label: 'Results' };
  const COMMAND_SURF   = { href: '#command',     label: 'Command' };
  const DIAG_SURFACE   = { href: '#diagnostics', label: 'Diagnostics' };

  const REASONS = {
    /* --- the scanner's own candidate gates (engine/setups.py) --- */
    NO_ELIGIBLE_PLAYBOOK: {
      plain: 'no strategy covers that market condition',
      means: 'The zone was real and price reached it, but none of the enabled ' +
             'strategies trades that kind of zone in that market regime, so no ' +
             'trade idea was ever built.',
      cta: SETUP_SURFACE },
    RR_BELOW_MINIMUM: {
      plain: 'the target was not far enough away to justify the stop',
      means: 'The trade idea was built, but the reward was small relative to ' +
             'the risk, so it was dropped before it became a setup.',
      cta: SETUP_SURFACE },
    UNECONOMIC_AFTER_COSTS: {
      plain: 'the move was too small to survive fees and slippage',
      means: 'The distance to the stop was so tight that trading costs would ' +
             'have eaten the edge. The engine refuses these rather than book ' +
             'a trade it expects to lose to friction.',
      cta: SETUP_SURFACE },
    ATR_UNAVAILABLE: {
      plain: 'there was not enough price history to measure volatility',
      means: 'The stop is placed using recent volatility. Without it the ' +
             'engine cannot size a stop honestly, so it declines.',
      cta: DIAG_SURFACE },
    NO_CAUSAL_TARGET: {
      plain: 'there was no structure ahead to aim the target at',
      means: 'Targets are placed at levels the market has actually respected. ' +
             'With nothing ahead, any target would have been invented.',
      cta: CHART_SURFACE },
    INVALID_BRACKET: {
      plain: 'the stop came out on the wrong side of the entry',
      means: 'The entry, stop and target did not form a valid trade. This is a ' +
             'geometry fault, not a market condition.',
      cta: DIAG_SURFACE },

    /* --- the risk authority (engine/risk.py) --- */
    OPERATOR_HALT: {
      plain: 'you halted the scanner, so nothing was sized',
      means: 'The halt blocks new entries only; open positions still settle.',
      cta: SETUP_SURFACE },
    DATA_HEALTH_BLOCKED: {
      plain: 'the data audit found a fault, so sizing was blocked',
      means: 'The engine will not size trades on data it cannot vouch for.',
      cta: DIAG_SURFACE },
    STRATEGY_DISABLED: {
      plain: 'that strategy is switched off',
      means: 'The setup was valid, but the strategy that produced it is ' +
             'disabled in Rules.',
      cta: SETUP_SURFACE },
    DAILY_LOSS_HALT: {
      plain: "the day's loss limit had already been hit",
      means: 'No new entries open until the next day. This is the automatic ' +
             'halt working, not a fault.',
      cta: SETUP_SURFACE },

    /* Three refusals the engine emits that had no entry here, so they reached
       the deck as raw codes on the one surface this dictionary exists to keep
       clean. DRAWDOWN_HALT arrives parameterised with the percentage. */
    DRAWDOWN_HALT: {
      plain: 'the account is too far below its high-water mark to keep trading',
      means: 'A drawdown halt is deeper than the daily one: it stops new ' +
             'entries until the account recovers, rather than until tomorrow. ' +
             'The bracket carries how far down it is.',
      cta: RESULTS_SURF },
    PARTICIPATION_TOO_THIN: {
      plain: 'the position would have been too large a share of what actually trades here',
      means: 'Size is capped against real traded volume, not just against the ' +
             'account. A position that is a big fraction of a thin book moves ' +
             'the price it is trying to get, so the fill you model is not the ' +
             'fill you would get.',
      cta: SETUP_SURFACE },
    VETOED: {
      plain: 'a safety check on the trade itself refused it',
      means: 'The setup passed its playbook but failed a structural check — ' +
             'the confirming candle was too narrow to trust, or the stop sat ' +
             'inside the venue tick resolution. The trace names which.',
      cta: DIAG_SURFACE },
    BIAS_BLOCKED: {
      plain: 'the bigger timeframes said no',
      means: 'The trade was sound on its own chart, but this playbook has a ' +
             'rule about what the timeframes above it were doing — and they ' +
             'were doing the wrong thing. The trace names the reading on each ' +
             'one. Every playbook carries its own rule here, because the ' +
             'record says trend-following and counter-move strategies want ' +
             'opposite answers.',
      cta: DIAG_SURFACE },

    /* `cooldown(sl,12.0h)` has been rendering raw and lowercased on the deck
       and in the order ticket with no glossary entry and no card here, while
       DAILY_LOSS_HALT and RISK_REJECTED both had hand-written ones. `baseCode`
       already strips the bracket, so this entry needs no parser work.

       Explaining it is not cosmetic. An operator who reads an unexplained
       refusal as arbitrary goes to the chart and sizes the trade by hand —
       which is precisely the failure a guardrail creates when it does not say
       why. The setup was VALID; it was refused on TIMING. */
    COOLDOWN: {
      plain: 'this symbol and direction were still resting after a recent exit',
      means: 'The last trade on this symbol in this direction closed recently, ' +
             'and the engine sits out a fixed window rather than re-entering ' +
             'the same idea straight away. The brackets name the exit that ' +
             'started the rest and how long it lasts — a stop-out rests much ' +
             'longer than a target, because a stop means the level was proven ' +
             'wrong rather than simply finished. ' +
             'This rule is NEW and has never been checked against outcomes: ' +
             'it is a rule of thumb the engine applies, not a proven improvement.',
      cta: RESULTS_SURF },
    NOT_IN_POINT_IN_TIME_UNIVERSE: {
      plain: "the market did not meet the bot's trading requirements at that time",
      means: 'The bot funds only markets that pass its selection rules when the ' +
             'setup forms. A market may be outside the selected group or fail ' +
             'liquidity or history requirements. PF_ markets are research-only: ' +
             'their setups are recorded, but no money is assigned to them.',
      cta: SETUP_SURFACE },
    INVALID_STOP_DISTANCE: {
      plain: 'the stop sat on top of the entry, so no size could be computed',
      means: 'Position size comes from the distance to the stop. A zero ' +
             'distance would mean an infinite position.',
      cta: DIAG_SURFACE },
    SHORT_UNSUPPORTED_COINBASE_SPOT: {
      plain: 'the venue cannot short — it is a spot market',
      means: 'Short setups need a venue that supports them. On spot you can ' +
             'only buy, so short ideas are recorded and refused.',
      cta: SETUP_SURFACE },
    PARENT_CLOSED: {
      plain: 'the position it was adding to had already closed',
      means: 'This was a scale-in. With the original trade gone there was ' +
             'nothing to add to.',
      cta: RESULTS_SURF },
    CONCURRENT_LIMIT: {
      plain: 'the account was already at its maximum number of open trades',
      means: 'A cap on simultaneous positions. Good setups are refused while ' +
             'it is full — that is the cap doing its job.',
      cta: SETUP_SURFACE },
    EXPOSURE_LIMIT: {
      plain: 'taking it would have pushed total open risk past the cap',
      means: 'Each trade risks a fixed slice of the account and the total is ' +
             'capped. This setup did not fit in the remaining budget.',
      cta: SETUP_SURFACE },
    LEVERAGE_CAP: {
      plain: 'the position needed more leverage than the venue allows',
      means: 'The stop was far enough away that a correctly sized position ' +
             'would have exceeded the leverage limit.',
      cta: SETUP_SURFACE },
    SPOT_CASH_CAP: {
      plain: 'buying it outright needed more cash than the account holds',
      means: 'On a spot venue there is no borrowing, so a position cannot ' +
             'exceed the cash available.',
      cta: SETUP_SURFACE },
    STOP_BEYOND_LIQUIDATION: {
      plain: 'the stop sat past the point where the exchange would force-close it',
      means: 'The stop has to sit safely inside the liquidation price or the ' +
             'exchange closes the position first.',
      cta: SETUP_SURFACE },
    BELOW_MIN_NOTIONAL: {
      plain: "the position came out smaller than the exchange's minimum order",
      means: 'Correct sizing produced an order too small to place.',
      cta: SETUP_SURFACE },
    WITHIN_LIMITS: {
      plain: 'every account safety check passed',
      means: 'The bot allowed the full position size.',
      cta: null },

    /* --- lifecycle outcomes (engine/telemetry.py) --- */
    RISK_REJECTED: {
      plain: 'the account safety checks blocked it',
      means: 'The setup was valid but an account rule blocked it. Open the ' +
             'trace on any one of them to see which rule.',
      cta: SETUP_SURFACE },
    ENTRY_NOT_FILLED: {
      plain: 'price never came back to the entry before the order expired',
      means: 'The order rested at the entry and price walked away instead of ' +
             'returning. The idea may have been right and still paid nothing.',
      cta: CHART_SURFACE },
    STOP_LOSS: {
      plain: 'price hit the stop before the target',
      means: 'A normal losing trade. This is expected attrition, not a fault — ' +
             'what matters is the rate, which Results tracks.',
      cta: RESULTS_SURF },
    TIMEOUT_EXIT: {
      plain: 'neither target nor stop was reached inside the holding limit',
      means: 'The trade went nowhere and was closed on time. Frequent timeouts ' +
             'usually mean targets are too far away.',
      cta: RESULTS_SURF },
    LOSING_EXIT: {
      plain: 'it closed at a loss',
      means: 'Closed below breakeven for a reason other than the stop.',
      cta: RESULTS_SURF },
    COSTS_ERASED_EDGE: {
      plain: 'it was profitable before fees and slippage, and not after',
      means: 'The direction was right and the move was too small to pay for ' +
             'itself. This points at entry and target placement, not at ' +
             'picking the wrong side.',
      cta: RESULTS_SURF },
    OPEN_POSITION: {
      plain: 'it is still open, so there is no result yet',
      means: 'Not a failure. It simply has not finished.',
      cta: COMMAND_SURF },
    WAITING_FOR_FILL: {
      plain: 'the order is live and waiting for price',
      means: 'Not a failure. The entry window is still open.',
      cta: COMMAND_SURF },
    AWAITING_RISK: {
      plain: 'the account safety checks have not finished yet',
      means: 'The setup validated but no position-size decision has been recorded. ' +
             'On a live scanner this clears within a cycle.',
      cta: DIAG_SURFACE },
    WINNER: {
      plain: 'closed with a profit after costs',
      means: 'Survived every gate and paid.',
      cta: RESULTS_SURF }
  };

  // Reason codes arrive parameterised, e.g. CONCURRENT_LIMIT(2). Strip the
  // argument to look the sentence up, but keep the original on screen.
  const baseCode = c => String(c).split('(')[0];
  const lookup = c => REASONS[baseCode(c)] || null;
  /* The fallback lowercases the BASE code, not the original. Left on the whole
     string, `DRAWDOWN_HALT(12.5%)` came out as "drawdown halt(12.5%)" — the
     parenthetical is stripped for the lookup and must be stripped for the
     fallback too, then re-appended so the number survives. */
  const plainOf = c => {
    const hit = (lookup(c) || {}).plain;
    if(hit) return hit;
    const s = String(c), arg = s.slice(baseCode(s).length);
    return baseCode(s).replace(/_/g, ' ').toLowerCase() + arg;
  };

  // Shared with wizard.js, which needs the same sentences. Exposed rather than
  // duplicated; wizard.js still guards for its absence so neither module can
  // take the other down.
  window.SSFunnel = { explain: c => lookup(c), plain: plainOf };

  /* ---------- the funnel model ----------
     Ordered exactly as a candidate travels. Each stage names the API field it
     reads, so there is one authority per number and it is visible in the source
     rather than buried in a formula. */
  const STAGES = [
    { key: 'candidates',    label: 'Candidates',
      blurb: 'zones price actually reached' },
    { key: 'validated',     label: 'Validated', term: 'setup',
      blurb: 'became a real trade idea' },
    { key: 'risk_approved', label: 'Safety approved', term: 'riskPerTrade',
      blurb: 'account checks allowed a position size' },
    { key: 'order_placed',  label: 'Order placed',
      blurb: 'an entry order was simulated' },
    { key: 'filled',        label: 'Filled',
      blurb: 'price came back and the order filled' },
    { key: 'closed',        label: 'Closed',
      blurb: 'reached a final result' },
    { key: 'winners',       label: 'Winners', term: 'rMultiple',
      blurb: 'closed positive after costs' }
  ];

  // What the drop into each stage means, as a sentence. `n` and `prev` are
  // filled in by the caller.
  const DROP_COPY = {
    validated:     (n, p) => `${n} of ${p} candidates never became a setup`,
    risk_approved: (n, p) => `${n} of ${p} setups were skipped by account safety checks`,
    order_placed:  (n, p) => `${n} of ${p} approved setups never became an order`,
    filled:        (n, p) => `${n} of ${p} orders never filled`,
    closed:        (n, p) => `${n} of ${p} filled trades have not finished yet`,
    winners:       (n, p) => `${n} of ${p} closed trades lost or broke even`
  };

  /* ---------- helpers ---------- */
  const esc = s => String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
  const fmt = n => Number(n).toLocaleString();
  const pct = (n, d) => d > 0 ? Math.round(100 * n / d) : 0;

  /* Through SSData: this module and shell.js both read /api/overview and
     /api/setup-telemetry on 30s clocks that were never aligned, so the same
     data was fetched twice per cycle and the two panels could show two
     different moments. The window is just under the poll period, so whichever
     module wakes first pays for the request and the other reads its answer. */
  const api = path => window.SSData.get(path, 25000);

  /* ---------- state ---------- */
  let selected = null;         // stage key the operator clicked, null = follow bottleneck
  let model = null;

  /* ---------- build ---------- */

  function build(tel, ovErr, ov) {
    const f = tel.funnel || {};
    const stageCounts = tel.stages || {};
    const failures = tel.failure_points || {};
    const records = tel.records || [];

    // candidates is the only figure not returned directly. It is a definitional
    // identity, not a re-derivation of a metric — and it is spelled out on
    // screen in the top stage's footer so the arithmetic is never hidden.
    const rejected = f.rejected_candidates || 0;
    const counts = {
      candidates:    rejected + (f.validated || 0),
      validated:     f.validated || 0,
      risk_approved: f.risk_approved || 0,
      order_placed:  f.order_placed || 0,
      filled:        f.filled || 0,
      closed:        f.closed || 0,
      winners:       f.winners || 0
    };

    /* Reason attribution per transition. Candidate rejections come from
       /api/overview's rejection_funnel, which is produced by the same query as
       rejected_candidates and therefore sums to it exactly. The downstream maps
       count every setup in the window, so they are a superset of any one
       transition — the UI says so rather than implying a clean decomposition. */
    const pick = (src, keys) => {
      const out = {};
      for (const k of keys) if (src[k]) out[k] = src[k];
      return out;
    };
    const reasons = {
      candidates:    {},
      validated:     ovErr ? null : (ov.rejection_funnel || {}),
      risk_approved: pick(failures, ['RISK_REJECTED']),
      order_placed:  stageCounts['VALIDATED'] ? { AWAITING_RISK: stageCounts['VALIDATED'] } : {},
      filled:        pick(failures, ['ENTRY_NOT_FILLED']),
      closed:        Object.assign({},
                       stageCounts['OPEN'] ? { OPEN_POSITION: stageCounts['OPEN'] } : {},
                       stageCounts['ORDER PENDING'] ? { WAITING_FOR_FILL: stageCounts['ORDER PENDING'] } : {}),
      winners:       pick(failures, ['STOP_LOSS', 'LOSING_EXIT', 'TIMEOUT_EXIT', 'COSTS_ERASED_EDGE'])
    };
    // Only the candidate transition is an exact decomposition of its drop.
    const exact = { validated: true };

    /* Individual setups that stalled at each stage — the bridge into the
       per-setup tracer. records[] is the most recent slice, never the whole
       window, so it is labelled as a sample and never counted from. */
    const inSample = k => records.filter(r => {
      const code = r.failure_code;
      if (k === 'risk_approved') return r.risk_decision === 'REJECTED';
      if (k === 'order_placed')  return code === 'AWAITING_RISK';
      if (k === 'filled')        return code === 'ENTRY_NOT_FILLED';
      if (k === 'closed')        return code === 'OPEN_POSITION' || code === 'WAITING_FOR_FILL';
      if (k === 'winners')       return ['STOP_LOSS', 'LOSING_EXIT', 'TIMEOUT_EXIT',
                                         'COSTS_ERASED_EDGE'].includes(code);
      return false;
    });

    // Drop-offs, and the largest of them.
    const rows = STAGES.map((s, i) => {
      const prev = i === 0 ? null : counts[STAGES[i - 1].key];
      const n = counts[s.key];
      const drop = prev == null ? 0 : Math.max(0, prev - n);
      return { ...s, n, prev, drop, dropPct: prev ? pct(drop, prev) : 0 };
    });
    let bottleneck = null;
    for (const r of rows) if (r.drop > 0 && (!bottleneck || r.drop > bottleneck.drop)) bottleneck = r;

    return { counts, rows, reasons, exact, bottleneck, inSample,
             ovErr, baseline: tel.baseline, total: counts.candidates,
             gates: tel.data_gates || [],
             faults: tel.engine_faults || [],
             unlabelled: tel.unlabelled_rejections || [] };
  }

  /* The stage before the first stage. The funnel begins at "candidates" —
     zones price actually reached — so a symbol whose DATA never arrived
     produces no candidates and used to be absent from this panel entirely,
     which is a hole exactly where "why is nothing firing" needs its answer.
     One closed vocabulary, shared with engine/pipeline.GATES; the roster test
     holds the two sides together. */
  /* Each sentence carries the CONSEQUENCE, and the consequence is a scope.
     A UI audit (2026-08-09) read "1 thing failing" beside "the pipeline is
     degraded and still sizing trades" and could not tell whether the failing
     market was still being traded off broken data. It is not: `pipeline.run_symbol`
     skips only the timeframe NO_DATA names and keeps the symbol's other
     timeframes, while QUALITY_BLOCKED is the one that drops the whole symbol.
     Naming which of the two a row is costs a clause and answers the question.

     NO_DATA says its neighbours are "unaffected by this", NOT that they are
     still scanning. A draft claimed the market keeps scanning on every other
     timeframe, which is false for a symbol whose candles are missing in ALL
     of them — a cold store, or an importer that threw and was logged past in
     live.py. That symbol trips one row per timeframe, so the honest form is
     per-gate scope: this row costs this timeframe, and the others speak for
     themselves by being listed or not. */
  const GATE_LABELS = {
    NO_DATA: 'no candles stored for this timeframe — the engines were not run ' +
             'on it, and no other timeframe on this market is affected by it',
    SHORT_HISTORY: 'history starts later than its floor — engines run, but on ' +
                   'less past than they were designed to see',
    QUALITY_BLOCKED: 'the market-data audit failed — every engine on this ' +
                     'market is skipped until it clears'
  };

  /* "Failing now" — the panel Diagnostics leads with. Engine exceptions,
     data gates and vocabulary drift in one list, newest first, each row one
     line: what · where · error · how long. Painted from the same payload the
     funnel already fetches, into its own panel above the funnel. */
  function paintFailing(m) {
    const root = document.getElementById('failingRoot');
    const chip = document.getElementById('failingChip');
    if (!root) return;
    const since = ts => new Date(ts * 1000)
      .toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
    const rows = [];
    for (const f of (m.faults || [])) {
      rows.push(`<div class="fail-row">
        <span class="fail-kind">engine</span>
        <span class="fail-what"><b>${esc(f.engine)}</b> ${esc(String(f.symbol).replace('-USD',''))} ${esc(f.tf)}</span>
        <span class="fail-err" title="${esc(f.error)}">${esc(f.error)}</span>
        <span class="fail-meta">${f.times}× · since ${since(f.since)}</span>
        <button class="btn fail-diag" data-diag="${esc(
          `Why is the ${f.engine} engine failing on ${f.symbol} ${f.tf}? Error: ${f.error}`
        )}">Diagnose</button>
      </div>`);
    }
    for (const g of (m.gates || [])) {
      rows.push(`<div class="fail-row dim">
        <span class="fail-kind">data</span>
        <span class="fail-what"><b>${esc(String(g.symbol).replace('-USD',''))}</b> ${esc(g.tf === '*' ? 'all TFs' : g.tf)}</span>
        <span class="fail-err">${esc(GATE_LABELS[g.gate] || g.gate)}</span>
        <span class="fail-meta">since ${since(g.since)}</span>
      </div>`);
    }
    for (const u of (m.unlabelled || [])) {
      rows.push(`<div class="fail-row dim">
        <span class="fail-kind">drift</span>
        <span class="fail-what"><b>${esc(u)}</b></span>
        <span class="fail-err">a rejection reason with no written sentence</span>
        <span class="fail-meta"></span>
      </div>`);
    }
    chip.textContent = rows.length ? rows.length + ' failing' : 'all clear';
    chip.className = 'chip ' + (rows.length ? 'chip-amber' : 'chip-green');
    root.innerHTML = rows.join('') ||
      '<div class="empty">nothing failing — engines clean, data flowing</div>';
  }

  function renderGates(m) {
    if (!m.gates.length) return '';
    const since = ts => new Date(ts * 1000)
      .toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
    return `<div class="dx-gates">
      <div class="dx-detail-head"><span>Before any candidate existed</span></div>
      ${m.gates.map(g => `<div class="dx-gate${GATE_LABELS[g.gate] ? '' : ' dx-drift'}">
        <span class="dx-gate-sym">${esc(String(g.symbol).replace('-USD', ''))}
          <i>${esc(g.tf === '*' ? 'all TFs' : g.tf)}</i></span>
        <span class="dx-gate-what">${esc(GATE_LABELS[g.gate] ||
          g.gate + ' — a gate this panel has no sentence for (vocabulary drift)')}
        </span>
        <span class="dx-gate-since">since ${since(g.since)}</span>
      </div>`).join('')}
      <div class="dx-sample-note">These symbols produced no candidates for the
        stages below — not because a gate refused their trades, but because the
        data to look for one never arrived.</div>
    </div>`;
  }

  /* ---------- render ---------- */

  function renderPill(m) {
    const b = m.bottleneck;
    if (!b) {
      // Genuinely nothing is being lost — say so in the same slot, so the
      // operator learns where the answer always appears.
      const none = m.total === 0;
      return `<div class="dx-bottleneck ${none ? '' : 'ok'}">
        <span class="dx-bn-mark">${none ? '—' : '✓'}</span>
        <span class="dx-bn-copy">
          <span class="dx-bn-kicker">Biggest bottleneck</span>
          <span class="dx-bn-line">${none
            ? 'No candidates recorded in this forward window yet. Nothing has been rejected because nothing has been examined.'
            : 'Nothing is being lost between stages in this window.'}</span>
          <span class="dx-bn-sub">${none
            ? 'run a scan, or wait for the scanner to complete a cycle'
            : fmt(m.total) + ' candidates · no stage is dropping any'}</span>
        </span>
      </div>`;
    }

    const map = m.reasons[b.key] || {};
    const top = Object.entries(map).sort((x, y) => y[1] - x[1])[0] || null;
    const meta = top ? lookup(top[0]) : null;
    const copy = (DROP_COPY[b.key] || ((n, p) => `${n} of ${p} were lost here`))(fmt(b.drop), fmt(b.prev));
    // Amber is attrition; red is reserved for a bottleneck the engine itself
    // owns, which is a different kind of problem from the market saying no.
    const isDefect = top && ['INVALID_BRACKET', 'INVALID_STOP_DISTANCE',
                             'ATR_UNAVAILABLE', 'DATA_HEALTH_BLOCKED'].includes(baseCode(top[0]));
    const cta = meta && meta.cta;

    return `<div class="dx-bottleneck ${isDefect ? 'bad' : ''}">
      <span class="dx-bn-mark">${b.dropPct}%</span>
      <span class="dx-bn-copy">
        <span class="dx-bn-kicker">Biggest bottleneck · ${esc(b.label)}</span>
        <span class="dx-bn-line">${esc(copy)}${top ? ' — ' + esc(plainOf(top[0])) : ''}.</span>
        <span class="dx-bn-sub">${top
          ? esc(top[0]) + ' · ' + fmt(top[1]) + ' of ' +
            fmt(Object.values(map).reduce((s, n) => s + n, 0)) + ' recorded at this stage'
          : 'no reason recorded for this drop'}</span>
      </span>
      ${cta ? `<a class="btn btn-primary dx-bn-cta" href="${cta.href}">Open ${esc(cta.label)} →</a>` : ''}
    </div>`;
  }

  function renderStages(m) {
    const active = selected || (m.bottleneck && m.bottleneck.key);
    return '<div class="dx-stages">' + m.rows.map(r => {
      // The track is the previous stage's count; the fill is what survived into
      // this one. The visible gap IS the drop-off — that is the whole point.
      // When nothing arrived at all, 100% of nothing survived: a 0%-wide bar
      // over a hatched track would read as total loss, which is a lie about an
      // empty window.
      const width = r.prev == null ? 100 : (r.prev > 0 ? (r.n / r.prev) * 100 : 100);
      const isBn = m.bottleneck && m.bottleneck.key === r.key;
      const name = r.term
        ? `<span class="term" data-t="${r.term}">${esc(r.label)}</span>`
        : esc(r.label);
      return `<button class="dx-stage${active === r.key ? ' on' : ''}${isBn ? ' bottleneck' : ''}${
                r.key === 'winners' ? ' terminal' : ''}" data-stage="${r.key}"
              aria-pressed="${active === r.key}">
        <span class="dx-stage-top">
          <span class="dx-stage-name">${name}</span>
          <span class="dx-stage-drop${r.drop ? '' : ' none'}">${
            r.prev == null ? '' : (r.drop ? '−' + fmt(r.drop) + ' (' + r.dropPct + '%)' : 'no loss')}</span>
          <span class="dx-stage-count">${fmt(r.n)}</span>
        </span>
        <span class="dx-stage-track">
          <!-- A survival of 2 out of 3,000 is 0.07% — mathematically right
               and a sub-pixel sliver on screen, so every heavy-loss stage
               looked identical to every other. The fill keeps its true
               proportion and gains a visible floor when ANY candidate
               survived, so "a few got through" is distinguishable from
               "none did". Zero stays genuinely zero. -->
          <span class="dx-stage-fill" style="width:${width.toFixed(2)}%${
            r.n > 0 ? ';min-width:4px' : ''}"></span>
          ${isBn ? '<span class="dx-stage-tag">bottleneck</span>' : ''}
        </span>
        <span class="dx-stage-foot">
          <span>${esc(r.blurb)}</span>
          <span style="margin-left:auto">${
            r.key === 'candidates'
              ? fmt(m.counts.validated) + ' validated + ' + fmt(m.counts.candidates - m.counts.validated) +
                ' rejected'
              : pct(r.n, m.total) + '% of all candidates'}</span>
        </span>
      </button>`;
    }).join('') + '</div>';
  }

  function renderDetail(m) {
    const key = selected || (m.bottleneck && m.bottleneck.key) || 'validated';
    const row = m.rows.find(r => r.key === key);
    const map = m.reasons[key];
    let html = `<div class="dx-detail"><div class="dx-detail-head">
      <span>Why they died at ${esc(row ? row.label : key)}</span></div>`;

    if (map === null) {
      // /api/overview failed: this stage's reasons are genuinely unknown. Say
      // which call failed instead of printing an empty list.
      html += `<div class="dx-fail"><b>reason breakdown unavailable</b>
        <code>${esc(m.ovErr)}</code>
        <span class="dx-fail-what">The stage counts above are still live. Only the
        per-reason split for this stage could not be loaded.</span></div>`;
    } else {
      const rows = Object.entries(map).sort((a, b) => b[1] - a[1]);
      if (!rows.length) {
        html += `<div class="dx-empty">Nothing recorded at this stage in this
          window${row && row.drop ? ' — the ' + fmt(row.drop) +
          ' lost here carry no recorded reason code' : ''}.</div>`;
      } else {
        html += rows.map(([code, n]) => {
          const meta = lookup(code);
          /* An unlabelled reason is VOCABULARY DRIFT, and it must look like
             drift, not like content. The lowercased fallback reads exactly
             like a written sentence — which trained everyone, including the
             person who minted the new reason, to assume someone else labelled
             it. Ported lesson: the prior project's _KNOWN_REASONS guard,
             surfaced at the pane where a human actually looks. */
          return `<div class="dx-reason${meta ? '' : ' dx-drift'}">
            <span class="dx-reason-code">${esc(code)}</span>
            <span class="dx-reason-n">${fmt(n)}</span>
            <span class="dx-reason-plain">${esc(meta ? meta.means : plainOf(code))}${
              meta ? '' : ' <i class="dx-drift-tag">unlabelled — this reason has no' +
                          ' written sentence yet</i>'}</span>
          </div>`;
        }).join('');
        const sum = rows.reduce((s, [, n]) => s + n, 0);
        if (!m.exact[key] && row && row.drop && sum !== row.drop) {
          html += `<div class="dx-sample-note">These counts cover every setup
            recorded in this window, so they need not sum to the ${fmt(row.drop)}
            lost at this stage.</div>`;
        }
      }
    }

    // Individual setups → the per-setup trace. This is the hand-off from
    // "why is nothing firing?" to "why didn't THIS one fire?".
    const sample = m.inSample(key).slice(0, 10);
    if (sample.length) {
      html += '<div class="dx-samples"><div class="dx-detail-head"><span>Open a trace</span></div>' +
        sample.map(r => `<button class="dx-sample" data-trace="${esc(r.setup_id)}">
          <b>${esc(String(r.symbol || '').replace('-USD', ''))}</b>
          <span>${esc(r.tf || '')}</span>
          <span>${esc(String(r.strategy || '').replace('_', ' ').toLowerCase())}</span>
          <span>${esc(String(r.direction || '').toLowerCase())}</span>
          <span class="dx-sample-go">trace →</span>
        </button>`).join('') +
        `<div class="dx-sample-note">Most recent setups recorded at this stage.
          Click one to see every gate it passed and the value it was judged on.</div></div>`;
    }
    return html + '</div>';
  }

  function render(m) {
    model = m;
    paintFailing(m);
    ROOT.innerHTML = '<div class="dx-funnel">' +
      renderPill(m) + renderGates(m) + renderStages(m) + renderDetail(m) + '</div>';
    // Only now is the flat list in #dFunnel superseded. If this module had
    // thrown, the shell's original list would still be on screen.
    document.body.classList.add('dx-funnel-live');
  }

  function fail(msgs) {
    // Loud fallback. Do not touch dx-funnel-live: if a refresh fails after a
    // good render, the shell's flat list is the right thing to fall back to,
    // and it is restored by removing the class.
    document.body.classList.remove('dx-funnel-live');
    ROOT.innerHTML = `<div class="dx-funnel"><div class="dx-fail">
      <b>funnel unavailable</b>
      ${msgs.map(m => '<code>' + esc(m) + '</code>').join('<br>')}
      <span class="dx-fail-what">No stage counts are shown because they could not
      be read. This is a failed request, <em>not</em> a report that nothing was
      rejected.</span></div></div>`;
  }

  /* ---------- events ---------- */

  document.addEventListener('click', e => {
    const d = e.target.closest('.fail-diag');
    if (d) {
      // offered as a chip, not typed into the box — see copilot.js suggestHtml
      if (window.SSCopilot) SSCopilot.open({kind: 'diagnostics', suggest: d.dataset.diag});
      else alert('Spotter could not be loaded (static/copilot.js).');
      return;
    }
  });

  ROOT.addEventListener('click', e => {
    const stage = e.target.closest('[data-stage]');
    if (stage && model) {
      selected = stage.dataset.stage;
      render(model);
      return;
    }
    const trace = e.target.closest('[data-trace]');
    // The tracer is a separate module; if it failed to load, say so rather
    // than silently doing nothing on a click.
    if (trace) {
      if (window.SSTracer) SSTracer.open(trace.dataset.trace);
      else alert('The trace drawer could not be loaded (static/tracer.js).');
    }
  });

  /* ---------- load ---------- */

  async function load() {
    // limit=500 is the endpoint's ceiling: the aggregate counts are computed
    // before the limit is applied, so only the clickable sample is truncated.
    const [tel, ov] = await Promise.allSettled([
      api('/api/setup-telemetry?limit=500'),
      api('/api/overview')
    ]);
    if (tel.status === 'rejected') {
      const msgs = [String(tel.reason && tel.reason.message || tel.reason)];
      if (ov.status === 'rejected') msgs.push(String(ov.reason && ov.reason.message || ov.reason));
      fail(msgs);
      return;
    }
    render(build(tel.value,
                 ov.status === 'rejected'
                   ? String(ov.reason && ov.reason.message || ov.reason) : null,
                 ov.status === 'fulfilled' ? ov.value : {}));
  }

  // Skeleton, not text: the funnel arrives as several stage bars, and a
  // one-line placeholder meant the panel grew on arrival and shoved everything
  // below it. ss.css owns .skel; this module renders inside the shell page.
  ROOT.innerHTML = '<div class="dx-funnel"><div class="skeleton" role="status" ' +
    'aria-label="loading"><div class="skel" style="height:28px"></div>' +
    '<div class="skel" style="height:28px"></div>' +
    '<div class="skel" style="height:28px"></div></div></div>';

  /* Driven by SSData's scheduler rather than a timer of this module's own, so
     the cadence, the in-flight de-duplication and the don't-poll-a-hidden-tab
     rule are decided in one place for every consumer.

     Subscribed on the telemetry path because that is the one only this file
     reads; /api/overview is then pulled from cache inside load(), which is what
     stops this panel and the shell describing two different scans. The
     operator's stage selection is held in `selected` and survives the repaint. */
  window.SSData.subscribe('/api/setup-telemetry?limit=500', () => { load(); }, 30000);
})();
