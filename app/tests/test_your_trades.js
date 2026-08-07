/* Your book, on a surface.

   The bug: `Arm` writes to the operator's manual store, and Command, the risk
   budget, the journal and every figure on Results read the ENGINE's store. That
   separation is deliberate and must stay — a hand-picked trade counted as
   engine edge would corrupt the record that decides whether live execution is
   ever unlocked. What was wrong is that one of the two books had no surface at
   all: three orders sat armed on three markets, and the only place any of them
   could be seen was the Chart tab, for the one symbol AND timeframe currently
   loaded. An order that expired while you were looking at another chart expired
   silently.

   These tests hold the shape of the fix: a separate panel that is never merged
   with the engine's, an honest disclosure on the budget meters that do not
   count this risk, and a cancel path that confirms, records, and never quietly
   deletes.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const HTML = S('static/shell.html');
const SHELL = S('static/shell.js');
const CSS = S('static/ss.css');
const CHART = S('static/chart.js');
const SERVER = S('server.py');
const ENGINE = S('engine/manual.py');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('your trades');

/* ───────────────────────── the panel exists ───────────────────────── */

ok('Command has a panel for the operator\'s own orders', () => {
  assert(/id="minePanel"/.test(HTML), 'no panel for your own book');
  assert(/<div id="mine">/.test(HTML), 'nowhere to render the rows');
  assert(/renderMine\(\)/.test(SHELL), 'nothing renders it');
  assert(/renderMine\(\)\.then\(\(\) => renderMineAside\(\)\)/.test(SHELL),
    'the panel must refresh on the same cycle as the rest of Command');
});

ok('it reads the whole-book endpoint, not one chart', () => {
  assert(/api\('\/api\/manual\/live'\)/.test(SHELL),
    'reading /api/manual/open would show one symbol+timeframe — the original bug');
  assert(/@app\.get\("\/api\/manual\/live"\)/.test(SERVER), 'the endpoint is missing');
  assert(/def live\(con\)/.test(ENGINE), 'nothing sweeps every market');
  assert(/for \(symbol, tf\) in sorted\(unresolved\(con\)\)/.test(ENGINE),
    'live() must iterate the whole work list');
});

ok('it resolves before it reports', () => {
  assert(/run\(con, symbol, tf, tf_seconds\)/.test(ENGINE),
    'the stored state is ARMED forever — an expired order would read as waiting');
});

ok('one unreadable market cannot blank the panel', () => {
  const fn = ENGINE.slice(ENGINE.indexOf('def live(con)'), ENGINE.indexOf('def status('));
  assert(/except Exception:/.test(fn) && /continue/.test(fn),
    'the rows that CAN be resolved are still worth showing');
});

/* ─────────────────── the two books stay separate ─────────────────── */

ok('your book is never merged into the engine\'s', () => {
  assert(!/active_positions.*\.concat\(.*manual/i.test(SHELL),
    'a hand-picked trade must never join the engine position list');
  assert(/hand-picked · not engine record/.test(HTML),
    'the panel must say whose plan these are');
  /* Re-pinned: #posPanel is gone — the engine's open trades are the Mission
     Briefs rail (#deck) now, so the comparison re-points at that. The
     ordering property is UNCHANGED in direction: your hand-picked orders sit
     above the engine's book, because the panel that can mislead you about
     whose plan a trade was should be met first. The separation itself is
     carried by the two assertions above, which are untouched. */
  assert(HTML.indexOf('id="minePanel"') < HTML.indexOf('id="deck"'),
    'your orders belong above the engine book, not mixed into it');
  assert(!/id="posPanel"/.test(HTML),
    'the duplicate Engaged-detail panel is back');
});

ok('the row is visually attributed, not just captioned', () => {
  assert(/\.pos-row\.mine\{border-left:2px solid var\(--accent\)\}/.test(CSS),
    'two books rendered identically is how a number ends up read against the wrong one');
});

ok('a resting row is marked unfilled, with the stake on hover', () => {
  // The paragraph version was purged by operator ruling; the FACT it carried
  // ("nothing at stake until it fills") survives as a hover title on the
  // unfilled marker — words on demand, zero screen cost.
  assert(/title="Nothing is at stake until it fills"/.test(SHELL),
    'the at-stake fact must survive somewhere a hover can reach');
  assert(/>unfilled</.test(SHELL), 'the row no longer marks itself unfilled');
});

/* ────────────────────── states are distinguished ────────────────────── */

ok('waiting and filled are drawn differently', () => {
  assert(/t\.state === 'PENDING'/.test(SHELL), 'one rendering for both states');
  assert(/waits <b>/.test(SHELL), 'a resting order must read as waiting, tersely');
});

ok('an order about to expire says so louder', () => {
  assert(/soon \? 'chip-red' : 'chip-amber'/.test(SHELL), 'no escalation near expiry');
  assert(/bars <= 1/.test(SHELL), 'nothing detects the last bar of the window');
});

ok('the window is stated in time, not only in bars', () => {
  assert(/function windowLeft/.test(SHELL), '"4 bars" means an hour on 15m and a day on 4H');
  assert(/tf_seconds/.test(SHELL) && /"tf_seconds": tf_seconds/.test(ENGINE),
    'the timeframe length must reach the browser');
});

ok('unrealized R comes from the server, not a second calculation', () => {
  assert(/t\.unrealized_r == null \? null : \+t\.unrealized_r/.test(SHELL),
    'recomputing R in the browser is a second authority that drifts from the one that pays out');
});

/* ──────────────────── the budget tells the truth ──────────────────── */

ok('the risk meters disclose what they do not count', () => {
  assert(/id="budgetAside"/.test(HTML), 'no disclosure element');
  assert(/function renderMineAside/.test(SHELL), 'nothing writes it');
  assert(/Outside these limits/.test(SHELL),
    'the bars must say they EXCLUDE this money, not merely mention it');
});

ok('the disclosure hides itself at zero rather than printing $0', () => {
  const fn = SHELL.slice(SHELL.indexOf('function renderMineAside'),
                         SHELL.indexOf('/* ---------- risk budget'));
  assert(/if\(total <= 0\)\{ el\.hidden = true/.test(fn),
    'a permanent "$0 outside these limits" trains the eye to skip the line that will matter');
});

ok('the disclosure changes nothing about what the engine will size', () => {
  assert(!/manual/i.test(SHELL.slice(SHELL.indexOf('const openRisk ='),
                                     SHELL.indexOf("const openCap ="))),
    'the budget arithmetic must stay the engine\'s — this is a disclosure, not a rule change');
  const arm = SERVER.slice(SERVER.indexOf('def manual_arm'), SERVER.indexOf('def draft_bracket'));
  assert(!/risk\.(authorize|size|rule)/.test(arm),
    'arming still must not consult the risk authority — that separation is the design');
});

/* ─────────────────────────── cancelling ─────────────────────────── */

ok('cancel confirms, and says what it does and does not do', () => {
  /* Was pinned to the literal confirm(`Cancel ${what}?`) call. The five
     high-stakes commits moved off window.confirm onto SSConfirm, so a selector
     naming the native function failed while every property it guarded still
     held. Assert the properties: this action asks first, and it says what is
     and is not at stake. */
  assert(/data-cancel/.test(SHELL), 'no cancel control');
  const asks = /SSConfirm\(\{[\s\S]{0,400}?Cancel this order\?/.test(SHELL)
            || /confirm\(`Cancel /.test(SHELL);
  assert(asks, 'an irreversible-looking action with no confirmation');
  assert(/nothing has been risked/.test(SHELL),
    'the confirmation must say nothing is at stake on an unfilled order');
});

ok('a cancelled order is recorded, never deleted', () => {
  assert(/def cancel_intent/.test(ENGINE), 'no cancel path');
  assert(/"outcome": "CANCELLED"/.test(ENGINE), 'it must leave a fact behind');
  assert(!/DELETE FROM facts/.test(ENGINE), 'this store is append-only');
});

ok('a cancellation is not a trade', () => {
  const book = ENGINE.slice(ENGINE.indexOf('def book(con'));
  assert(/r\["outcome"\] in \("TP", "SL", "TRAIL_STOP", "TIMEOUT"\)/.test(book),
    'CANCELLED must stay out of n/wins/win_rate — otherwise a record improves by cancelling losers');
});

ok('a filled position cannot be cancelled', () => {
  const fn = ENGINE.slice(ENGINE.indexOf('def cancel_intent'), ENGINE.indexOf('def live(con)'));
  assert(/w\["phase"\] == "OPEN"/.test(fn) && /IntentRejected/.test(fn),
    'resolving a filled trade at zero R would erase a real result');
});

ok('arming refreshes the panel that shows the order', () => {
  assert(/invalidate\('\/api\/manual\/live'\)/.test(CHART),
    'the order you just armed would be missing until the cache aged out');
});

/* ─────────────────── failure is not an empty book ─────────────────── */

ok('a book that cannot be read does not render as an empty one', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/catch\(err\)\{/.test(fn), 'a failed fetch is swallowed');
  assert(/Could not read your book/.test(fn), 'it must say the read failed');
  assert(/are still there/.test(fn),
    'the operator must not conclude their orders vanished because a fetch did');
});

ok('an empty book hides the panel rather than showing an empty box', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/if\(!rows\.length\)\{ panel\.style\.display = 'none'/.test(fn),
    'no orders is the normal state and needs no furniture');
});

/* ─────────────── partial exits: a position that is half gone ───────────────

   The panel rendered a partly-closed position exactly like an untouched one.
   Two numbers were wrong at once, both in the flattering direction on a
   winner: the full original stake showed under "at risk" when only what is
   left can still be lost, and `unrealized_r` — the per-unit R of the REMAINING
   size — read as the whole trade's result while half of it had already been
   banked at a different price. */

ok('the row headlines the blended R, not the open remainder alone', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/const blended = t\.blended_r == null \? r : \+t\.blended_r/.test(fn),
    'blended_r is banked plus open — the trade. It equals unrealized_r when ' +
    'nothing was scaled out, so an ordinary row must be untouched by this');
  assert(/\$\{rr\(blended\)\}/.test(fn), 'the headline still quotes the open half only');
});

ok('only the size still on is described as at risk', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/const stillAtRisk = t\.risk_usd == null \? null : \+t\.risk_usd \* openFrac/.test(fn),
    'quoting the original stake on a half-closed position overstates what a ' +
    'stop would now cost — the money the operator is deciding with');
  assert(!/money\(t\.risk_usd\) \+ ' at risk'/.test(fn),
    'the full-stake wording survived somewhere in the open row');
});

ok('what was taken off is stated, with what it banked', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/% off · \$\{\s*rr\(\+t\.realized_r\)\} banked/.test(fn),
    'a closed fraction with no R beside it is a percentage nobody can act on');
  assert(/closed > 0/.test(fn), 'nothing distinguishes a scaled row from a whole one');
});

ok('a resting order shows the ladder it will run without you', () => {
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(/t\.partials_planned \|\| \[\]/.test(fn),
    'an order that will take half off at a level reads as an ordinary one until it does');
});

ok('the server owns every one of those figures', () => {
  // Same rule the unrealized R already lives under: one authority, which is
  // the walk that settles the trade.
  assert(/"realized_r"|realized_r=str/.test(ENGINE), 'the engine does not compute it');
  assert(/blended_r=str/.test(ENGINE), 'the blend is not computed server-side');
  assert(/closed_fraction=str/.test(ENGINE), 'nothing reports how much is gone');
  const fn = SHELL.slice(SHELL.indexOf('async function renderMine'),
                         SHELL.indexOf('/* Cancel is a real mutation'));
  assert(!/realized[A-Za-z]*\s*=\s*[^t].*\*\s*\+t\.(entry|sl|tp)/.test(fn),
    'the browser must not re-derive a banked R from prices');
});

/* ───────────── partial exits: setting one on the ticket ───────────── */

ok('the ticket has a way to take part off, and it is off by default', () => {
  assert(/id="tkScale"/.test(HTML), 'no scale-out control');
  assert(/id="tkScalePct"/.test(HTML) && /id="tkScaleR"/.test(HTML),
    'a scale-out needs both how much and how far');
  assert(/id="tkScaleRow" hidden/.test(HTML),
    'taking half off is a choice with a cost, not a prudence the app assumes');
});

ok('the rung is typed in R and armed as a price', () => {
  assert(/function partialPrice/.test(S('static/ticket-math.js')),
    'the R-to-price conversion belongs in the tested arithmetic file');
  assert(/partials: scalePlan/.test(CHART), 'the rung never reaches the server');
  assert(/\{fraction: scalePlan\.fraction, price: scalePlan\.price\}/.test(CHART),
    'the engine records a PRICE — sending R would make it re-derive one from ' +
    'a risk figure it had to trust the browser for');
});

ok('the price it lands on is shown, not just the R', () => {
  assert(/id="tkScaleAt"/.test(HTML), 'nowhere to state where the rung lands');
  assert(/takes \$\{Math\.round\(p\.fraction \* 100\)\}% off at \$\{pf\(p\.price\)\}/.test(CHART),
    'R is what you type; the price is what the trade turns on');
});

ok('a rung the engine would refuse disables Arm rather than being sent', () => {
  assert(/const badScale = \$\('tkScale'\) && \$\('tkScale'\)\.checked && !scalePlan/.test(CHART),
    'nothing detects an unplaceable rung');
  assert(/btn\.disabled = badScale \? true/.test(CHART),
    'a rung that silently failed validation while the rest armed would give ' +
    'the operator a trade they did not ask for');
  assert(/SCALE_BLOCK/.test(CHART), 'the refusal has no wording');
});

ok('the confirm restates the rung before it commits', () => {
  /* The label moved from "taking N% off at" to "scale-out: N% off at" when the
     dialog gained key/value rows. What matters is that the rung is restated at
     all, in the action's own terms, before it commits. */
  assert(/\$\{Math\.round\(scalePlan\.fraction \* 100\)\}% off at/.test(CHART),
    'the last word before an irreversible-feeling action should be its own terms');
});

ok('the scale-out does not survive onto the next chart', () => {
  const fn = CHART.slice(CHART.indexOf('function restore()'),
                         CHART.indexOf('function setDir('));
  assert(/\$\('tkScale'\)\.checked = false/.test(fn),
    'carrying "half off at 1R" to another market arms a plan never decided for it');
});

ok('the chart draws the rung, filled and unfilled differently', () => {
  assert(/PLAN · \$\{Math\.round\(scalePlan\.fraction \* 100\)\}% OFF/.test(CHART),
    'the planned rung is invisible on the chart');
  assert(/YOURS · \$\{Math\.round\(\+r\.fraction \* 100\)\}% \$\{filled \? 'OFF' : 'AT'\}/.test(CHART),
    'a rung already taken and one still waiting must not draw identically — ' +
    '"what have I got left on" should be answerable by looking');
});

/* ──────────────── partial exits: the accounting ──────────────── */

ok('the blend is derived from the recorded legs, by the replay function', () => {
  assert(/def blend_r\(legs/.test(ENGINE), 'no single definition of the blend');
  assert(/"r_multiple": str\(blend_r\(legs, "r_net"\)\)/.test(ENGINE),
    'settle code must BE replay code — a separately-computed headline number ' +
    'is one the record cannot vouch for');
  assert(/"legs": legs/.test(ENGINE),
    'without the legs on the fact the blend is unreproducible');
});

ok('every leg is costed by one function, with no cheaper path for a partial', () => {
  assert(/def settle_leg\(/.test(ENGINE), 'no shared costing');
  const run = ENGINE.slice(ENGINE.indexOf('def run(con, symbol'));
  assert((run.match(/settle_leg\(/g) || []).length === 2,
    'the rungs and the remainder must both go through settle_leg');
});

ok('the stop still takes the whole bar', () => {
  const fn = ENGINE.slice(ENGINE.indexOf('def _exit_walk'), ENGINE.indexOf('def run(con'));
  assert(fn.indexOf('if hit_stop:') < fn.indexOf('for r in touched:'),
    'a rung filling on the stop\'s own bar would bank a profit moments before ' +
    'the loss — plausible, flattering, and unprovable from OHLC');
});

/* Re-pinned when the override key moved off the engine version (manual-v0.3).
 * The old assertions named v0.2 and the exact two-element tuple, so the next
 * bump would have failed them for being a bump — which is not what they are
 * for. The PROPERTY is: the write tag is one version, the read set is every
 * version this book has ever written, and it only ever grows. Stated that way
 * a bump passes and a bump that STRANDS the old book fails, which is the
 * direction that matters. */
ok('the version moved, and every old one is still read', () => {
  const cur = ENGINE.match(/MANUAL_VERSION = "(manual-v[\d.]+-draft)"/);
  assert(cur, 'the write tag must be one named manual version');
  const set = ENGINE.match(/MANUAL_VERSIONS = \(([^)]*)\)/);
  assert(set, 'the read set must be a literal tuple, greppable from here');
  /* Every tag this book has SHIPPED. Append on a bump; never remove. Dropping
   * one strands every order still open under it: never settled, never expired,
   * absent from every surface. */
  for (const shipped of ['manual-v0.1-draft', 'manual-v0.2-draft',
                         'manual-v0.3-draft']) {
    assert(set[1].includes('"' + shipped + '"'),
      `the read set dropped ${shipped} — orders under it are stranded armed forever`);
  }
  assert(!set[1].includes('"' + cur[1] + '"') && /MANUAL_VERSION\s*\)?\s*$/.test(set[1].trim()),
    'the current tag belongs in the tuple as MANUAL_VERSION, last, not restated as a literal');
  assert(/algo_version IN \(\{marks\}\)/.test(ENGINE),
    'the read path must filter on the tuple, not on one version');
});

/* ─────────── an override outlives the engine version it was written under ───────────
 * The class of bug, not the one instance. Found live 2026-08-06: `setup_id`
 * embeds SETUP_VERSION, the portfolio suppressed on an exact id match, so the
 * bump from setup-v0.15 to v0.17 re-minted the id and a position the operator
 * had CLOSED for +$136.22 came back as $194.60 of live exposure. It was the
 * only position, so open_risk_usd was entirely a closed trade. */
ok('an operator override is keyed on the zone, not on the engine version', () => {
  assert(/def setup_zone_key\(/.test(ENGINE),
    'the version-stripping rule needs one named home, or it gets re-implemented');
  assert(/def overridden_zone_keys\(/.test(ENGINE),
    'the suppression set must come from the same map operator_closed is built from');
  assert(!/if sid in completed or sid in overrides/.test(SERVER),
    'an exact setup_id match expires every override the next time setups bumps');
  assert(/setup_zone_key\(sid\) in override_zones/.test(SERVER),
    'the portfolio must suppress on the version-stripped id');
  /* operator_closed keeps the FULL id, one row per fact. Collapsing it on the
   * stripped key would hide a second close of the same zone — real money. */
  assert(/out\[p\["setup_id"\]\] = /.test(ENGINE),
    'overridden_setups must stay keyed on the full id so no closed trade is lost');
});

/* ───────────────── the label that was written twice ───────────────── */

ok('the scan button label lives in one place', () => {
  assert(!/textContent = s\.running \? 'Scanning…' : 'Run Scan'/.test(SHELL),
    'this line rewrote the HTML label on every console poll — the rename to ' +
    '"Check now" survived exactly one poll');
  assert(/b\.dataset\.idleLabel = b\.textContent\.trim\(\)/.test(SHELL),
    'the idle label must be read from the DOM, not restated in JS');
  assert(/>Check now</.test(HTML), 'the HTML is the authority on the label');
});

console.log('\n  ' + passed + ' passed');
