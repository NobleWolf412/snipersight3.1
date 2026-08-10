/* The engines the operator could not see.

   Seven engines ran on every scan cycle from the beginning and wrote facts no
   surface could request. Measured 4 Aug 2026, before this shipped:

       momentum   194,753     volatility  83,771     volprofile  20,050
       volume     231,946     fvg         74,596     range       12,367
       ma         171,982

   ...against a chart that offered a Cycle layer over 116 facts and a Liquidity
   layer over 5,988. The two smallest tables in the store were the two with
   toggles; the six largest had none. An engine the operator cannot see cannot
   inform a decision, and the operator had said so directly — "highly
   beneficial to know about momentum when analyzing price against structure".

   These tests pin the wiring end to end: the API serves the kinds, the chart
   knows how to ask for them, the markup offers them, and the ONE field-name
   mismatch that silently emptied a layer during the build cannot come back. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const CHART = S('static/chart.js');
const HTML = S('static/shell.html');
const SERVER = S('server.py');
const CSS = S('static/ss.css');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('chart layers');

ok('the API serves every engine the chart can now draw', () => {
  for (const kind of ['momentum', 'volatility', 'volume', 'ma',
                      'fvg', 'volprofile', 'range']) {
    assert(new RegExp(`"${kind}":`).test(SERVER),
      `/api/facts still refuses kind=${kind} — KIND_VERSIONS gates the endpoint`);
  }
  assert(/from engine import momentum, volatility, volume, ma, fvg, volprofile, ranges/
    .test(SERVER), 'the version constants are referenced but never imported');
});

ok('every new layer has a toggle, a label and a plain-language note', () => {
  for (const key of ['gaps', 'shelf', 'ranges', 'signals']) {
    assert(new RegExp(`data-o="${key}"`).test(HTML), `no toggle for ${key}`);
    const row = HTML.match(new RegExp(`<button data-o="${key}"[^>]*>`))[0];
    assert(/data-label="/.test(row), `${key} has no data-label`);
    assert(/data-note="/.test(row),
      `${key} has no note — a toggle whose meaning is not stated is the ` +
      `"cycles and liquidity crossed out with no explanation" complaint again`);
  }
});

ok('the new layers default OFF', () => {
  const m = CHART.match(/const overlays = \{[\s\S]*?\};/);
  assert(m, 'overlays defaults not found');
  for (const key of ['gaps', 'shelf', 'ranges', 'signals']) {
    assert(new RegExp(`${key}: false`).test(m[0]),
      `${key} defaults ON — the standing complaint about this surface is ` +
      `clutter, and the fix for "I cannot see momentum" is not "here is ` +
      `everything at once"`);
  }
});

ok('layers are lazy: nothing is fetched until one is switched on', () => {
  assert(/const LAZY = \{/.test(CHART), 'no lazy-layer map');
  assert(/async function ensureLayer/.test(CHART), 'no lazy fetch');
  // the eager load must NOT have grown these kinds
  const load = CHART.match(/res = await Promise\.all\(\[[\s\S]*?\]\);/)[0];
  for (const kind of ['fvg', 'volprofile', 'momentum', 'volume', 'volatility']) {
    assert(!load.includes(`'${kind}'`),
      `${kind} joined the eager load — a chart nobody asked to decorate must ` +
      `cost what it did before`);
  }
});

ok('lazy fetching never delays or blanks the price chart', () => {
  // The first cut awaited the layer fetches BEFORE series.setData, so the
  // candles waited on four decorative queries and a refresh landing mid-await
  // returned past the paint and left the chart empty.
  const load = CHART.slice(CHART.indexOf('async function load(opts)'));
  const setData = load.indexOf('series.setData(candles)');
  const ensure = load.indexOf('await ensureLayer');
  assert(setData > 0 && ensure > 0, 'load() no longer has both calls');
  assert(ensure > setData,
    'a layer fetch is awaited before the candles are drawn — price must never ' +
    'wait on decoration');
});

ok('layer facts are dropped when the market changes', () => {
  assert(/if\(extraKey !== painted\)\{ extra = \{\}; extraKey = painted; \}/.test(CHART),
    'the lazy cache survives a symbol switch — the old market\'s gaps would ' +
    'be drawn under the new market\'s candles');
  assert(/if\(layerSeq === loadSeq && candles\.length\) drawOverlays\(\)/.test(CHART),
    'a layer fetch finishing late is drawn without checking it is still the ' +
    'current market');
});

ok('the volume shelf matches the states the engine actually writes', () => {
  /* THE BUG THIS FILE EXISTS FOR. The first cut filtered on state === 'HVN'
     and 'LVN'. engine/volprofile.py writes Schmitt-trigger states — AT_HVN,
     AT_LVN, MID — so the layer matched nothing, drew nothing, and reported
     "no data" over 81 real facts on SOLUSDT 4H. A layer that silently shows
     nothing is worse than no layer: it teaches the operator the engine is
     empty. */
  assert(/'AT_HVN'/.test(CHART) && /'AT_LVN'/.test(CHART),
    'the shelf no longer matches AT_HVN/AT_LVN — check engine/volprofile.py ' +
    'before "fixing" this, because bare HVN/LVN matches nothing');
  const vp = fs.readFileSync(
    path.join(__dirname, '..', 'engine', 'volprofile.py'), 'utf8');
  assert(vp.includes('AT_HVN'),
    'the engine no longer writes AT_HVN — the chart filter must follow it');
});

ok('traded-through gaps and broken ranges are not drawn', () => {
  assert(/g\.event !== 'FILLED'/.test(CHART),
    'a filled gap stays on the chart — it marks a level that no longer exists');
  assert(/r\.event !== 'BROKEN' && r\.state !== 'BROKEN'/.test(CHART),
    'a broken range stays drawn');
});

ok('signal markers stay thin enough to read', () => {
  assert(/sig\.slice\(0, 40\)/.test(CHART), 'signal markers are uncapped');
  assert(/\+v\.rvol >= 2\.5/.test(CHART),
    'every hot-volume bar is marked — 2x of baseline is background noise');
  // Only divergence keeps a word; the first cut labelled everything and
  // produced three overlapping DIVERGENCE tags on adjacent bars.
  const sigBlock = CHART.slice(CHART.indexOf('const sig = []'),
                               CHART.indexOf('sig.sort('));
  const texts = sigBlock.match(/text: '[^']+'/g) || [];
  assert(texts.length === 1 && texts[0] === "text: 'DIV'",
    `signal markers carry ${texts.length} text labels (${texts.join(', ')}) — ` +
    `text is the clutter, and only DIV needs a word`);
});

/* ─────────── LEVELS ARE A LAYER TOO ───────────

   The operator's report, 7 Aug 2026: a filled manual trade opened from Manage
   put six price lines on the chart — three gold ones that were theirs and
   three the ticket drew — and the nine-switch Layers control governed none of
   them. These pin the switches, and the one coupling that makes hiding a level
   safe: nothing may be left stranded by a line that is not drawn. */

ok('levels have two switches, with notes, and both start ON', () => {
  for (const key of ['yours', 'engine']) {
    assert(new RegExp(`data-o="${key}"`).test(HTML), `no toggle for ${key}`);
    const row = HTML.match(new RegExp(`<button data-o="${key}"[^>]*>`))[0];
    assert(/data-label="/.test(row), `${key} has no data-label`);
    assert(/data-note="/.test(row),
      `${key} has no note — a toggle whose meaning is not stated is the same ` +
      `complaint the Liquidity and Cycle notes were written for`);
    assert(/class="on"/.test(row),
      `${key} starts switched off. The ask was a way to quiet a loud chart, ` +
      `not for the operator's own trade or the engine's opinion to disappear ` +
      `until someone finds a menu`);
  }
  const m = CHART.match(/const overlays = \{[\s\S]*?\};/)[0];
  for (const key of ['yours', 'engine'])
    assert(new RegExp(`${key}: true`).test(m),
      `${key} is not a live overlay key with a default of ON`);
});

ok('the two level switches stay separate', () => {
  /* Collapsing them into one "levels" toggle would remove the only view that
     answers the question being asked: the engine's idea, on its own, with the
     operator's own lines out of the way. Both keys must be read independently
     by the drawing code, not through a shared flag. */
  assert(/overlays\.yours/.test(CHART) && /overlays\.engine/.test(CHART),
    'one of the two level keys is never read — the switches have been merged');
  assert(/const LEVEL_LAYERS = \{yours: 1, engine: 1\}/.test(CHART),
    'the level-layer set is gone; the Layers handler needs it to know which ' +
    'switches redraw from the book rather than from the fact cache');
});

ok('a level switched off takes its drag handle with it', () => {
  /* A grab tag is a draggable pill that names a price. Left over a line that
     is not drawn it is worse than the clutter it was hidden to fix. */
  assert(/lvlHidden \? null : levels\[k\]/.test(CHART),
    'placeHandles still positions a grab tag from the raw level');
  assert(/if\(lvlHidden \|\| levels\[key\] == null\) return;/.test(CHART),
    'startDrag will still drag a level that is not on the chart');
});

ok('hiding YOUR levels does not empty the engine bracket too', () => {
  /* The ticket bracket de-duplicates against the operator's own order lines —
     that is what stopped "PLAN · TP" and "YOURS · TP" stacking on one pixel.
     With those lines switched off, deduping against them would suppress the
     shared prices on BOTH sides and leave the chart with no entry, stop or
     target at all: one switch silently emptying the other. */
  const at = CHART.indexOf('function positionPrices()');
  assert(at > 0, 'positionPrices is gone');
  assert(/if\(!overlays\.yours\) return \[\];/.test(CHART.slice(at, at + 900)),
    'positionPrices still claims prices for lines it is no longer drawing');
});

ok('toggling a level layer actually redraws the levels', () => {
  const h = CHART.slice(CHART.indexOf("$('cLayersPop').addEventListener"));
  assert(/LEVEL_LAYERS\[key\][\s\S]{0,80}drawPosition\(\); applyLevels\(\);/.test(h),
    'the Layers handler only calls drawOverlays, which draws from the fact ' +
    'cache — levels come from the book and the ticket, so the switch would ' +
    'report itself off and change nothing on screen');
});

ok('an empty level switch claims nothing bigger than "none to draw"', () => {
  /* Caught in the browser. Edit the ticket and the bracket passes from the
     Engine plan switch to Your levels, so Engine plan has no lines while the
     engine's validated setup plainly still exists — and the second opinion is
     still quoting it two rows below. The switch may say IT has nothing to
     draw; it may not say the engine has nothing. */
  assert(/LEVEL_LAYERS\[k\] \? ' — none to draw' : ' — no data'/.test(CHART),
    'the empty level switch reads as "the engine has no plan here", which is ' +
    'a claim about the world rather than about the switch, and it can be false ' +
    'while the second opinion is quoting the setup it denies');
  assert(/nothing of \$\{k === 'yours' \? 'yours' : 'the engine\\'s'\} to draw/.test(CHART),
    'the empty tooltip makes the same over-claim the label used to');
});

ok('a level switch that is OFF does not claim its lines are on the chart', () => {
  /* THE DEFECT THIS PINS. The tooltip read "N price lines on this chart" — a
     claim about pixels — while the count behind it was what the switch is
     RESPONSIBLE for, taken before every draw guard. Switch Your levels off and
     it went on reporting lines with none drawn; worse, positionPrices() empties
     when that switch is off, releasing the ticket bracket's de-duplication, so
     the total went UP. The nine older layers say "recorded", which stays true
     whether they are drawn or not. These two now make the same shape of claim
     about the same shape of fact. */
  assert(!/price line\$\{c === 1 \? '' : 's'\} on this chart/.test(CHART),
    'the level tooltip is a claim about what is on the chart, made from a ' +
    'count that ignores every draw guard — it is false whenever the switch ' +
    'is off');
  assert(/price line\$\{c === 1 \? '' : 's'\} while this switch is on/.test(CHART),
    'the level tooltip no longer says the count is conditional on the switch');
});

ok('a level tally never moves when its own switch moves', () => {
  /* `bracketN` de-duplicates against the operator's order lines, and
     positionPrices() returns [] when Your levels is off — so counting through
     it made the tally jump by three the moment the layer was hidden. The
     drawing keeps that short-circuit (it is what stops the chart emptying);
     the counting must not have it. */
  const fn = CHART.slice(CHART.indexOf('function applyLevels('),
                         CHART.indexOf('function recompute('));
  assert(/const held = bookPrices\(\);/.test(fn),
    'applyLevels counts the bracket through positionPrices(), whose answer ' +
    'depends on the very switch the count is describing');
  assert(/if\(!held\.some\(v => same\(v, p\)\)\) bracketN\+\+;/.test(fn),
    'the de-duplicated tally is no longer taken against the book itself');
  assert(/bracketRaw\+\+;/.test(fn),
    'the pre-de-duplication tally is gone — Engine plan needs it to say what ' +
    'it would draw once the gold lines are hidden');

  const counts = CHART.slice(CHART.indexOf('function levelCounts('),
                             CHART.indexOf('function paintLevelCounts('));
  assert(/yours:\s*posN \+ \(bracketMine \? bracketN : 0\)/.test(counts),
    'the Your-levels tally reads something other than its own de-duplicated ' +
    'bracket, so it can change when the switch is flicked');
  assert(/engine: bracketMine \? 0 : \(overlays\.yours \? bracketN : bracketRaw\)/
    .test(counts),
    'the Engine-plan tally ignores whether the gold lines are up — with them ' +
    'hidden it really does draw the shared prices, and the count must say so');
  assert(!/overlays\.engine/.test(counts),
    'a level tally reads its own switch, so it will fall to zero when the ' +
    'layer is hidden and mark the control .empty — which reads as "there is ' +
    'nothing here" about a layer you have just turned off');
});

ok('a layer fetching its data says so', () => {
  assert(/classList\.add\('loading'\)/.test(CHART), 'no loading state');
  assert(/\.layers-pop button\.loading/.test(CSS), 'the loading state has no styling');
  assert(/prefers-reduced-motion/.test(CSS.slice(CSS.indexOf('.layers-pop button.loading'))),
    'the loading pulse ignores reduced-motion');
});

ok('on a phone the popup anchors to the viewport, not the button', () => {
  /* `right:0` pins the panel to the Layers BUTTON's right edge; on a phone
     the chart-top row wraps, the button lands mid-row, and a 310px panel ran
     left past the screen edge (operator's phone, 2026-08-10). A width cap
     cannot fix a position. The pin: inside a phone media query, the popup is
     position:fixed with BOTH horizontal edges set — the only anchor that
     cannot leave the screen wherever the button wrapped to. */
  const at = CSS.indexOf('.layers-pop{position:fixed');
  assert(at > 0, 'the phone rule is gone — the popup anchors to the button again');
  const rule = CSS.slice(at, CSS.indexOf('}', at));
  assert(/left:10px/.test(rule) && /right:10px/.test(rule),
    'only one horizontal edge is set, so the other can still leave the screen');
  const before = CSS.slice(Math.max(0, at - 600), at);
  assert(/@media \(max-width:900px\)/.test(before),
    'the fixed anchoring is not scoped to phones — on a desktop the popup ' +
    'belongs beside the button that opened it');
  assert(/100dvh/.test(rule),
    'no dvh cap — Android vh includes retracted browser chrome, so a vh-sized ' +
    'popup runs past the real bottom of the screen');
});

console.log('\n  ' + passed + ' passed');
