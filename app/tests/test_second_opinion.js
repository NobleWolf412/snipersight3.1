/* THE SECOND OPINION, in words.

   Operator report, 7 Aug 2026: "when I place a trade normally and then it
   fills I'll click on manage on the open trade and it takes me to the chart.
   it will show me in yellow on the chart where I placed my trade, but there's
   also a planned entry exit and take profit in red and green so it's a bit
   confusing because there's six plotted data points on the chart... if the bot
   has a planned trade for that on the same time frame it should indicate that
   more clear not necessarily block it because the bot might have a better
   entry than what I chose."

   The engine disagreeing with the operator is the single most useful thing
   this chart can tell them, and it was legible only as three extra coloured
   lines and the gaps between them. #tkSecond says it: which level, which way,
   by how much.

   Four properties, all of them things a later session could quietly undo:

     · it compares only when there IS something to compare, on the same symbol
       and the same timeframe;
     · a SKETCH is never quoted back as the engine's opinion;
     · it never gates or disables Arm — the engine may have the better entry
       and that call is the operator's;
     · it goes quiet with the Engine plan layer.

   These are source-text assertions, like every JS suite here: they pin the
   contract, not the rendered page. Behaviour was confirmed in the running app.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const CHART = S('static/chart.js');
const HTML = S('static/shell.html');
const CSS = S('static/ss.css');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

/* A top-level function body out of chart.js. Every function in the IIFE is
   indented two spaces, so its close brace is the first "\n  }" after it. */
function body(name) {
  const at = CHART.indexOf(`function ${name}(`);
  assert(at > 0, `${name} is gone from chart.js`);
  const end = CHART.indexOf('\n  }', at);
  assert(end > at, `could not find the end of ${name}`);
  return CHART.slice(at, end);
}

console.log('second opinion');

ok('the ticket has somewhere to put it, and it is not a warning', () => {
  assert(/id="tkSecond"/.test(HTML), 'no #tkSecond on the ticket');
  const row = HTML.match(/<div[^>]*id="tkSecond"[^>]*>/)[0];
  assert(/hidden/.test(row),
    '#tkSecond is not hidden by default — an empty bordered row would sit ' +
    'under every ticket that has nothing to compare');
  assert(!/tk-warn/.test(row),
    'the second opinion is styled as a warning. It is not one: red on this ' +
    'bar means Arm is off, and this line stops nothing');
  assert(/\.commit-bar \.tk-second\{/.test(CSS), 'tk-second has no styling');
  assert(/\.tk-second\[hidden\]\{display:none\}/.test(CSS),
    'the flex rules on .commit-bar rows can outvote [hidden]');
});

ok('it compares only when both plans are on the SAME symbol and timeframe', () => {
  const fn = body('paintSecondOpinion');
  assert(/const here = sym \+ '\|' \+ tf;/.test(fn),
    'the market being compared is not named in one place');
  assert(/if\(painted !== here \|\| posKey !== here \|\| !openPos\.length\) return;/.test(fn),
    'the guard is gone. `painted` is the market the facts on screen describe ' +
    'and `posKey` is the market the open book was answered for — comparing ' +
    'across either puts one market\'s entry beside another market\'s, which ' +
    'is the wrong-price-under-the-right-name failure this file has already ' +
    'been bitten by once');
});

ok('the market of the open book is read from the answer, not assumed', () => {
  /* A guard that trusts the variable the request was built from is not a
     guard: a response landing after a symbol switch would satisfy it. */
  assert(/posKey = op && op\.symbol && op\.tf \? op\.symbol \+ '\|' \+ op\.tf : null;/
    .test(CHART),
    'posKey no longer comes from the endpoint\'s own echo of symbol and tf');
  assert(/openPos = \[\];\s*\n(\s*\/\/[^\n]*\n)*\s*posKey = null;/.test(CHART),
    'clearChart empties openPos without clearing the market it belonged to');
});

ok('a sketch is never quoted back as the engine\'s opinion', () => {
  /* pickSetup folds several different things into two looks: only a VALIDATED
     setup fact and a position the engine has actually taken are the machine
     saying "this trade, at these prices". A structure draft is not — the
     engine drew it from a live zone but has not judged the trade. (The 14-bar
     ruler was the other sketch and is now deleted rather than dimmed; see
     "the chart draws only a plan, a position, or nothing" below.) */
  const fn = body('enginePlanHere');
  assert(/kind: 'position'/.test(fn) && /kind: 'setup'/.test(fn),
    'the two real engine plans are no longer distinguished');
  assert(/base\.kind === 'draft'/.test(fn),
    'the structure draft is no longer separated out — it would be reported ' +
    'as a second opinion the engine never gave');
  assert(/\{kind: 'sketch'\}/.test(fn), 'the sketch verdict is gone');

  const paint = body('paintSecondOpinion');
  assert(/if\(eng\.kind === 'sketch'\)\{/.test(paint),
    'the sketch case is no longer handled separately, so a ruler drawn around ' +
    'the last close would be compared against a real position as though the ' +
    'engine had an opinion about it');
  assert(/not a second opinion/.test(paint),
    'the sketch line no longer says what it is');
});

ok('a validated setup risk REFUSED says so', () => {
  /* base.kind was set to 'engine' BEFORE the risk decision was looked up, so a
     rejected setup drew the same full-brightness ENGINE lines as an approved
     one. This line is where the setup gets called a second opinion, so it is
     where the refusal has to be repeated. */
  const fn = body('paintSecondOpinion');
  assert(/if\(f\.refused\)\{/.test(fn),
    'a refused setup is presented as a trade the engine is waiting to take');
  assert(/SSFunnel/.test(fn),
    'the refusal reasons are not going through the shared plain-language ' +
    'dictionary — a raw enum is not a thing a trader can act on');
});

ok('a setup the engine has already acted on is not called a live plan', () => {
  /* setups.py emits FORMING, CONFIRMING, VALIDATED, CANCELLED and EXPIRED,
     and EXPIRED fires when the ZONE breaks — there is no terminal state for
     "already acted on". So a VALIDATED setup whose entry filled days ago kept
     being quoted as a trade the engine was waiting to take. The order facts
     already answer it; nothing new has to be invented in the engine. */
  const fate = body('setupFate');
  assert(/facts\.orderF/.test(fate),
    'setupFate no longer reads the order facts, so a filled or expired setup ' +
    'is indistinguishable from one the engine is still waiting on');
  assert(/o\.event === 'FILLED'/.test(fate) && /o\.event === 'MISSED'/.test(fate),
    'the two events that end a setup\'s entry window are no longer read');
  assert(fate.indexOf("o.event === 'FILLED'") < fate.indexOf("o.event === 'MISSED'") &&
         /break;/.test(fate),
    'FILLED must win — execsim stops at a fill, so a MISSED read afterwards ' +
    'would report an entry that happened as one that never did');
  assert(/d\.decision === 'REJECTED'/.test(fate),
    'the risk refusal no longer lives with the rest of the setup\'s fate, so ' +
    'the bracket, the ticket and this line can each answer it differently');

  const fn = body('paintSecondOpinion');
  assert(/setupFate\(eng\.id\)/.test(fn),
    'the second opinion no longer asks what became of the setup it is quoting');
  assert(/f\.order === 'FILLED'/.test(fn) && /f\.order === 'MISSED'/.test(fn),
    'an entry that has already happened, or a window that expired, is not ' +
    'said in words — the operator is told the engine is offering an opinion ' +
    'it has in fact already finished acting on');
});

ok('one reading of a setup\'s fate, shared by all three surfaces', () => {
  /* The bracket\'s styling, the ticket\'s rationale and this line were each
     free to answer "is the engine still waiting on this" differently. One
     authority per number: setupFate answers it, base.fate carries it. */
  assert(/function setupFate\(id\)\{/.test(CHART), 'setupFate is gone');
  assert((CHART.match(/decision === 'REJECTED'/g) || []).length === 1,
    'the REJECTED comparison is made in more than one place');
  const pick = body('pickSetup');
  assert(/const fate = setupFate\(setup\.setup_id\);/.test(pick),
    'pickSetup no longer reads the fate');
  assert(pick.indexOf('const fate = setupFate(') <
         pick.indexOf("dir: setup.direction, kind: 'engine'"),
    'the setup is dressed as an engine plan BEFORE anything checks whether it ' +
    'still is one — the exact ordering that produced this defect');
  assert(/fate: fate\.state/.test(pick),
    'the fate does not travel on `base`, so applyLevels cannot style from it');
  assert(/base\.fate/.test(body('applyLevels')),
    'applyLevels no longer reads the fate, so a refused or spent setup is ' +
    'drawn at full brightness again');
});

ok('a setup that is not a live plan is not DRAWN as one', () => {
  /* THE ARGUMENT THIS PINS, made by chart.js itself where the seeded ruler was
     given a dim register: three horizontal price lines outweigh any caption.
     It was not applied to a refused setup, or to one whose entry had already
     filled — both drew the bright solid ENGINE bracket while the chip above
     them said NOT TRADED. */
  const fn = body('applyLevels');
  const upto = fn.slice(0, fn.indexOf('const want'));
  for (const t of ['NOT TRADED · ENTRY', 'FILLED · ENTRY', 'MISSED · ENTRY'])
    assert(upto.includes(t), 'missing label: ' + t);
  assert(/draft \|\| spent \?/.test(upto),
    'the dim dotted register is no longer shared with the spent states, so ' +
    'they are either bright again or wearing a fourth style nobody asked for');
  assert(/'ENGINE · ENTRY'/.test(upto),
    'the bright register is gone — a plan the engine IS waiting on must still ' +
    'be told apart from one it is not');
  assert(/spent \? 'spent-' \+ fate/.test(fn),
    'drawnKind does not change with the fate, so a bracket that goes stale ' +
    'under a refresh keeps the styling it was first drawn with');
  assert(/bracketMine = live \? modified : draft;/.test(fn),
    'a refused or spent ENGINE setup has been moved into `Your levels`. It ' +
    'is still the machine\'s — only the register changes, never the owner');
});

ok('the chart draws only a plan, a position, or nothing', () => {
  /* THE OPERATOR'S RULE, 8 Aug 2026: "the only time something should display
     on the chart is if the bot generated a plan, my plan, or active trades."

     Two things violated it, and the second was found live on BTCUSDT 1D:

     · the 14-bar ruler — `last close ± average range`, always LONG, drawn on
       any chart with nothing else to show. Its own caption said "not a
       signal, not analysis, and not the engine's opinion" and it was still
       three horizontal price lines, which this file's other tests spend two
       hundred lines establishing outweigh any caption;
     · a SPENT setup. VALIDATED is sticky — setups.py retires a setup only
       when its zone breaks — so one whose entry filled in Sep 2024 was still
       the newest VALIDATED setup on BTC 1D in Aug 2026, purely because the
       three setups since had all expired cleanly and dropped out. The chart
       drew its bracket with the stop 18% below the live price. */
  const pick = body('pickSetup');
  assert(!/kind: 'seeded'/.test(CHART),
    'the 14-bar ruler is back. A bracket invented from the recent range is ' +
    'not a plan the bot generated, not the operator\'s, and not a position');
  assert(!/base\.kind === 'seeded'/.test(CHART),
    'something still branches on the seeded kind, so a caller can revive it');
  assert(/const open = valid\.filter\(/.test(pick) &&
         /setupFate\(f\.setup_id\)\.state/.test(pick),
    'pickSetup no longer asks what became of each candidate, so a setup the ' +
    'engine finished with two years ago can become the chart\'s subject again');
  assert(/s !== 'filled' && s !== 'missed'/.test(pick),
    'the spent states are no longer excluded by name');
  assert(!/'refused'/.test(pick.slice(pick.indexOf('const open = valid.filter('),
                                      pick.indexOf('const preferred'))),
    'a REFUSED setup is being dropped with the spent ones. It is not spent — ' +
    'risk may size it once the concurrent slot frees, and it is still the ' +
    'engine\'s live opinion. It stays, labelled NOT TRADED');
  assert(/setup = preferredSetupId \? \(preferred \|\| null\) : \(open\[0\] \|\| null\);/
    .test(pick),
    'the default pick no longer reads the filtered list, or the explicit ' +
    'Setup Radar link no longer reaches a finished setup for review');
  assert(/valid\.find\(f => f\.setup_id === preferredSetupId\)/.test(pick),
    'an explicitly requested setup_id is resolved against the FILTERED list, ' +
    'so clicking a finished trade in Setup Radar now reports it missing');
});

ok('an empty chart says so instead of filling the space', () => {
  const pick = body('pickSetup');
  const tail = pick.slice(pick.lastIndexOf('}else{'));
  assert(/base = null;/.test(tail),
    'the no-plan branch sets levels again rather than leaving them empty');
  assert(!/candles\.slice\(-n\)/.test(tail),
    'the average-range arithmetic is back in the empty branch');
  assert(/the engine has no plan on this chart/.test(tail),
    'the empty state no longer says what it is');
  assert(/Type an entry, stop and target/.test(tail),
    'the empty state does not say how to trade the market anyway. The ruler ' +
    'existed to be dragged; deleting it without naming the typed-entry path ' +
    'removes a capability instead of a false statement');
});

ok('it NEVER disables or gates the arm control', () => {
  /* The operator was explicit: "not necessarily block it because the bot
     might have a better entry than what I chose." */
  const fn = body('paintSecondOpinion');
  for (const forbidden of ['tkArm', 'tkBlock', 'armable', 'refreshArm',
                           'disabled']) {
    assert(!fn.includes(forbidden),
      `the second opinion touches ${forbidden}. It is information, not a ` +
      `gate — the engine disagreeing is a reason to look, never a refusal`);
  }
  assert((fn.match(/\$\('tkSecond'\)/g) || []).length === 1,
    'the second opinion writes to more than its own element');
});

ok('it goes quiet with the Engine plan layer', () => {
  const fn = body('paintSecondOpinion');
  assert(/if\(!overlays\.engine\) return;/.test(fn),
    'the comparison survives its own layer being switched off — the whole ' +
    'point of the two switches is that the operator sets how loud the second ' +
    'opinion is');
  // ...and it has to be repainted when that switch moves, or the guard above
  // only takes effect on the next full load.
  assert(/paintSecondOpinion\(\);/.test(body('applyLevels')),
    'applyLevels no longer repaints it, so toggling the layer leaves a stale ' +
    'line on screen');
});

ok('each sentence answers the switch that owns the lines it describes', () => {
  /* THE DEFECT THIS PINS. The sketch branch was behind `overlays.engine`, but
     on that branch there is no engine plan at all — `bracketMine` is true and
     the dotted bracket it describes belongs to Your levels. So Your levels off
     left "the dotted bracket is yours to drag" sitting over an empty chart,
     and Engine plan off took the sentence away while its bracket was still
     drawn. `lvlHidden` is applyLevels' own answer to "is that bracket on the
     chart", whichever switch decided it. */
  const fn = body('paintSecondOpinion');
  const sketch = fn.slice(fn.indexOf("if(eng.kind === 'sketch'){"));
  assert(/if\(lvlHidden\) return;/.test(sketch.slice(0, 1200)),
    'the sketch sentence describes a bracket without checking that the ' +
    'bracket is drawn');
  assert(fn.indexOf('if(!overlays.engine) return;') >
         fn.indexOf("if(eng.kind === 'sketch'){"),
    'the Engine plan gate still runs before the sketch branch, so a sentence ' +
    'about the operator\'s own dotted bracket answers the engine\'s switch');
});

ok('agreement is not announced as disagreement', () => {
  /* Arm the engine's own setup at the engine's own prices and this read
     "against your open trade … entry X, level with yours · stop Y, level with
     yours · target Z, level with yours" — three rows of nothing under a
     headline saying the machine was arguing with you. */
  const fn = body('paintSecondOpinion');
  assert(!/against your open/.test(fn),
    'the headline still calls every comparison an argument, including the ' +
    'ones where every level matches');
  assert(/const agreed = !flip && rows\.every\(r => r\.same\);/.test(fn),
    'nothing decides whether the two plans actually differ, so the wording ' +
    'cannot depend on it');
  assert(/it agrees with/.test(fn),
    'total agreement has no sentence of its own — it is still spelled out as ' +
    'a list of non-differences');
  assert(/same \$\{list\}/.test(fn),
    'the agreement clause names levels it did not compare, or does not name ' +
    'them at all');
});

ok('a resting limit is not called an open trade', () => {
  /* #tkOpen one row above says "PENDING … fills if touched, else missed". Two
     rows of the same commit bar contradicting each other about whether the
     operator is in a trade is the worst place in the app to do it. */
  const fn = body('paintSecondOpinion');
  assert(/p\.state === 'PENDING' \? 'your resting order'/.test(fn),
    'a PENDING limit is described as an open trade, contradicting the row ' +
    'directly above it');
});

ok('every figure goes through the shared formatters', () => {
  /* A percentage rounded locally here is the money-formatter bug in a new
     costume: the same number, formatted two ways, on two surfaces of one app. */
  const fn = body('paintSecondOpinion');
  assert(/const F = window\.SSFormat;/.test(fn), 'SSFormat is not read');
  assert(/F\.pct\(/.test(fn) && /F\.px\(/.test(fn),
    'the difference or the prices are formatted by hand');
  assert(!/toFixed\(/.test(fn),
    'a figure is rounded locally instead of by the shared formatter');
  assert(/toLocaleString/.test(fn) === false,
    'a figure is formatted locally instead of by the shared formatter');
});

ok('a missing formatter is audible, not silent', () => {
  /* Silence here reads as "the engine agrees", which is the one thing this
     line must never imply by accident. */
  const fn = body('paintSecondOpinion');
  assert(/if\(!F\)\{/.test(fn), 'no fallback when SSFormat has not loaded');
  const at = fn.indexOf('if(!F){');
  const branch = fn.slice(at, at + 400);
  assert(/el\.hidden = false;/.test(branch),
    'the degraded path hides itself — a fallback that is silent is a bug');
});

ok('the comparison names a direction as well as a distance', () => {
  const fn = body('paintSecondOpinion');
  assert(/' above'/.test(fn) && /' below'/.test(fn),
    'the difference is stated without saying which way it goes');
  assert(/level with yours/.test(fn),
    'a difference under the formatter\'s own resolution still prints a ' +
    'percentage — "0.0% above" beside two visibly different prices is a ' +
    'rounding lie');
  /* NORMALISED on both sides, the way the duplicate-arm guard at #tkDup and
     the book reconciliation after a lost reply already do it. A raw !== reads
     the engine's LONG against a book that spells it Long as a flip — or, worse
     on this line, misses a genuine one. */
  assert(/const engDir = String\(eng\.dir \|\| ''\)\.toUpperCase\(\);/.test(fn) &&
         /const myDir = String\(p\.direction \|\| ''\)\.toUpperCase\(\);/.test(fn),
    'the two directions are compared raw, so this file normalises the same ' +
    'value three ways');
  assert(/engDir && myDir && engDir !== myDir/.test(fn),
    'the engine being on the OTHER side is the loudest thing this line can ' +
    'report and it is no longer reported');
});

console.log('\n  ' + passed + ' passed');
