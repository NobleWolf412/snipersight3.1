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

ok('a layer fetching its data says so', () => {
  assert(/classList\.add\('loading'\)/.test(CHART), 'no loading state');
  assert(/\.layers-pop button\.loading/.test(CSS), 'the loading state has no styling');
  assert(/prefers-reduced-motion/.test(CSS.slice(CSS.indexOf('.layers-pop button.loading'))),
    'the loading pulse ignores reduced-motion');
});

console.log('\n  ' + passed + ' passed');
