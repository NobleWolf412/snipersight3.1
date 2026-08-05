/* A parser, for the one class of defect the suites cannot see.
 *
 * The JavaScript suites assert against the TEXT of the static files, and
 * `node --check` proves only that the file parses. Neither can catch a name
 * that is read but never bound: that is legal JavaScript which throws the
 * first time the line runs, and if the line lives inside a branch that only
 * executes when a panel has something to show, it ships.
 *
 * That is not hypothetical. `renderDeck` called `deckRowInner(s, now)` and
 * never bound `now`, so the Setup Deck printed its "Looked at, not taken"
 * heading and then dropped every row under it, while the tile beside it said
 * "4 examined, not taken". It also rejected the 30s refresh cycle, which put
 * API DEGRADED in the top bar while every endpoint answered 200. The whole JS
 * suite ran green through all of it. Checked against the revision that shipped
 * it (4cd5965): `no-undef` reports `'now' is not defined` at shell.js:836.
 *
 * THIS IS A BUG GATE, NOT A STYLE GATE. `js.configs.recommended` is entirely
 * rules about code that cannot do what it says — duplicate keys, unreachable
 * statements, assignment inside a condition. No formatting rule is enabled and
 * none should be: a lint run that argues about quotes trains everyone to skim
 * past it, and the one line that mattered here would be skimmed past with it.
 *
 * It is also the repo's FIRST npm dependency, which the CI file previously
 * noted the absence of twice. That is a real cost — a lockfile, an install
 * step, and third-party code in the build. It is worth it for a parser, and
 * for nothing else: eslint is the only entry in package.json, there are no
 * plugins or shared configs, and the browser globals below are written out by
 * hand rather than pulling in the `globals` package for them.
 */
import js from '@eslint/js';

/* The DOM surface these files actually touch. Hand-written, and deliberately
   not exhaustive — a name missing from here surfaces as a no-undef error on
   first use, which is a two-second fix and a far better failure than the
   `globals` package quietly blessing every API in every environment. */
const BROWSER = [
  'window', 'document', 'console', 'location', 'history', 'navigator', 'screen',
  'fetch', 'Request', 'Response', 'Headers', 'AbortController', 'WebSocket',
  'localStorage', 'sessionStorage', 'caches',
  'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval', 'queueMicrotask',
  'requestAnimationFrame', 'cancelAnimationFrame', 'requestIdleCallback',
  'addEventListener', 'removeEventListener', 'dispatchEvent',
  'innerWidth', 'innerHeight', 'scrollTo', 'scrollBy', 'getComputedStyle',
  'matchMedia', 'alert', 'confirm', 'prompt', 'open', 'close', 'print',
  'Event', 'CustomEvent', 'MutationObserver', 'IntersectionObserver',
  'ResizeObserver', 'performance', 'crypto', 'structuredClone',
  'Image', 'URL', 'URLSearchParams', 'FormData', 'Blob', 'File', 'FileReader',
  'DOMParser', 'XMLSerializer', 'Node', 'Element', 'HTMLElement', 'SVGElement',
  'atob', 'btoa', 'TextEncoder', 'TextDecoder', 'Intl', 'Notification',
  'getSelection', 'devicePixelRatio', 'self',
];

/* The app's OWN cross-file surface. Each of these is assigned as
   `window.SSFoo = {...}` by the module that owns it, and read bare by the
   others — a real global, so it is declared as one rather than silenced.
   Kept as an explicit list because it doubles as the inventory of what the
   surfaces are allowed to reach for across file boundaries; a new name here
   should be a deliberate decision, not a side effect of typing one. */
const APP = [
  'SSChart', 'SSChartCtx', 'SSClock', 'SSConfirm', 'SSCopilot', 'SSData',
  'SSEdgeView', 'SSFormat', 'SSFunnel', 'SSGlossaryFocus', 'SSStateView',
  'SSTeach', 'SSToast', 'SSTracer', 'SSWizard',
  // Assigned as `root.SSTicketMath`, not `window.SSTicketMath`, because that
  // file is also require()d by test_ticket_math.js and has to name its own
  // root either way.
  'SSTicketMath',
];

const readonly = names => Object.fromEntries(names.map(n => [n, 'readonly']));

export default [
  {
    // lightweight-charts.js is vendored third-party code. Linting someone
    // else's minified bundle reports their decisions, not ours.
    ignores: ['static/lightweight-charts.js', 'node_modules/**', 'data/**'],
  },
  {
    files: ['static/**/*.js'],
    languageOptions: {
      ecmaVersion: 2024,
      // `script`, not `module`: these are <script> tags wrapping IIFEs, and
      // calling them modules would hide top-level `this` and let import
      // syntax through that the browser would then reject at runtime.
      sourceType: 'script',
      globals: {
        ...readonly(BROWSER),
        ...readonly(APP),
        LightweightCharts: 'readonly',   // the vendored charting bundle
      },
    },
    ...js.configs.recommended,
    rules: {
      ...js.configs.recommended.rules,
      /* Reported, not fatal. An unused name is usually dead code worth
         deleting, but it is not a defect the way an unbound READ is, and
         making it fail the build is how a bug gate turns into a chore that
         gets disabled. Args are ignored entirely: a handler that takes
         (err, data) and uses only one of them is idiomatic, not a mistake. */
      'no-unused-vars': ['warn', {args: 'none', varsIgnorePattern: '^_'}],

      /* ── The three below are DOWNGRADED, NOT SILENCED ──────────────────
         Nothing here is switched off. Each one currently fires on code that
         predates this config, so gating the build on it would mean either a
         red CI from the first commit or a cleanup smuggled in beside the tool
         that found it. They report; they do not block; and every outstanding
         instance is named here so "warn" cannot quietly become "ignored".

         no-redeclare — ONE instance, and it is a real defect, not noise:
         `renderScoreboard` is declared twice in shell.js, at 2041 and 2948.
         The second silently wins, so the first is dead code — and the two do
         different jobs. The dead one fills the "Closed today" tile
         (#mTodayTile / #mToday / #mTodaySub), which is why that tile renders
         an em-dash with no sub-line on Command. Fixing it means deciding
         whether that tile should live, which is a change with a visible
         outcome and belongs in its own commit rather than in the one that
         installs the linter. Raise this to "error" the moment it lands.

         no-empty — 11 instances, all `catch(e){}`. §4 of the constitution
         says a silent fallback IS a bug, so these are worth working through;
         they are also spread across surfaces owned by other work in flight.

         no-useless-assignment — 1 instance, shell.js:166. Defensive
         `let seen = true` before a try/catch that assigns on both paths.
         Harmless, and arguably clearer than the alternative. */
      'no-redeclare': 'warn',
      'no-empty': 'warn',
      'no-useless-assignment': 'warn',
    },
  },
  {
    /* ticket-math.js carries a CommonJS export shim so test_ticket_math.js can
       require it. It is the one file that runs in both a browser and node —
       which is the point: it decides how big a trade is and re-implements
       venues.liquidation_price, and the test is the only thing proving the
       ticket and the engine agree about where a position dies. */
    files: ['static/ticket-math.js'],
    languageOptions: {globals: readonly(['module', 'exports', 'require'])},
  },
  {
    files: ['tests/**/*.js'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'commonjs',
      globals: readonly([
        'require', 'module', 'exports', '__dirname', '__filename',
        'console', 'process', 'Buffer', 'setTimeout', 'setInterval',
        'clearTimeout', 'clearInterval', 'setImmediate', 'global',
        'structuredClone', 'URL', 'queueMicrotask',
      ]),
    },
    ...js.configs.recommended,
    rules: {
      ...js.configs.recommended.rules,
      'no-unused-vars': ['warn', {args: 'none', varsIgnorePattern: '^_'}],

      /* Two rules are off for the SUITES ONLY, because in a test harness the
         thing each one guards against is the thing the harness is doing on
         purpose. Neither is relaxed for `static/`, where they still hold.

         no-control-regex — test_trade_surfaces.js scans served files for
         stray control bytes. CLAUDE.md records why: a scripted edit can land
         the byte an escape denotes instead of the characters that spell it,
         `\b` becomes 0x08, and a CSS `\25B8` becomes 0x15 followed by "B8".
         Searching for control characters is the entire point of that test.

         no-unexpected-multiline — test_ssdata.js builds a sandbox with
         `new Function(...)` and invokes it on the next line. The rule exists
         because that shape is usually an accidental call created by automatic
         semicolon insertion; here it is the deliberate one, and wrapping it
         to satisfy the rule would make the argument list unreadable. */
      'no-control-regex': 'off',
      'no-unexpected-multiline': 'off',
    },
  },
];
