/* Tests for the Learn surface and first-run orientation.
   Run: node tests/test_lessons.js   (from app/)

   What is worth testing here is not that the copy is good — no test can tell
   you that. It is that the STRUCTURE holds and the widgets cannot lie:

     · every chapter has all four sections, because the identical skeleton is
       the whole reason the surface works as teaching;
     · every widget exposes a working step API and draws at every step, because
       a widget that throws mid-lesson is worse than no widget;
     · no widget emits NaN or undefined into its markup, which is how a
       geometry bug shows up on screen;
     · every glossary term a chapter marks up actually exists, because
       glossary.js stays SILENT on an unknown key (`if(!def) return;`) — an
       underlined word that explains nothing is the exact complaint this whole
       feature was built to answer;
     · the JavaScript ports of engine logic agree with the Python they were
       copied from, checked against truth tables written from the source.
*/
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const L = require('../static/lessons.js');

let pass = 0;
function t(name, fn) {
  try { fn(); console.log('  ok   ' + name); pass++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('lessons');

/* ─────────────────────────── chapters ─────────────────────────── */

t('eight chapters, numbered and uniquely identified', () => {
  assert.strictEqual(L.chapters.length, 8);
  const ids = new Set(), ns = [];
  for (const c of L.chapters) {
    assert.ok(c.id && typeof c.id === 'string', 'chapter needs an id');
    assert.ok(!ids.has(c.id), 'duplicate chapter id: ' + c.id);
    ids.add(c.id);
    ns.push(c.n);
  }
  assert.deepStrictEqual(ns, [1, 2, 3, 4, 5, 6, 7, 8], 'chapters must be 1..8 in order');
});

t('every chapter has all four sections', () => {
  for (const c of L.chapters) {
    // 1. CORE MECHANIC
    assert.ok(typeof c.mechanic === 'string' && c.mechanic.length > 200,
      c.id + ': mechanic missing or too thin');
    // 2. WHY IT WORKS — the differentiator, so it is held to a real length
    assert.ok(typeof c.why === 'string' && c.why.length > 400,
      c.id + ': "why it works" missing or too thin (' + (c.why || '').length + ' chars)');
    // 3. COMMON MISTAKES
    assert.ok(Array.isArray(c.mistakes) && c.mistakes.length >= 2,
      c.id + ': needs at least two mistakes');
    for (const m of c.mistakes) {
      assert.ok(m.wrong && m.right, c.id + ': a mistake needs both sides');
      assert.ok(m.right.length > 40, c.id + ': "' + m.wrong + '" has no real correction');
    }
    // 4. interactive widget
    assert.ok(c.widget && L.widgets[c.widget], c.id + ': widget "' + c.widget + '" not found');
  }
});

t('every chapter names the engine file and version it was written against', () => {
  for (const c of L.chapters) {
    assert.ok(/engine\/\w+\.py/.test(c.source), c.id + ': source must name an engine file');
    assert.ok(/-v\d+\.\d+/.test(c.source), c.id + ': source must name an algo version');
  }
});

t('every chapter asks a question in its header', () => {
  for (const c of L.chapters) {
    assert.ok(c.question && c.question.trim().endsWith('?'),
      c.id + ': the header question must be a question');
  }
});

t('the eight subjects the surface promised are all covered', () => {
  const ids = L.chapters.map(c => c.id);
  for (const want of ['swings', 'structure', 'zones', 'liquidity', 'regime', 'risk',
    'confluence', 'card']) {
    assert.ok(ids.includes(want), 'missing chapter: ' + want);
  }
});

/* ─────────────────────────── widgets ─────────────────────────── */

const WIDGET_IDS = Object.keys(L.widgets);

t('at least three interactive widgets exist', () => {
  assert.ok(WIDGET_IDS.length >= 3, 'only ' + WIDGET_IDS.length + ' widgets');
  for (const need of ['wickVsClose', 'sweepVsBreakout', 'zoneLifecycle']) {
    assert.ok(L.widgets[need], 'missing the named widget: ' + need);
  }
});

t('no orphan widgets — each is used by exactly one chapter', () => {
  const used = L.chapters.map(c => c.widget);
  for (const id of WIDGET_IDS) {
    const n = used.filter(u => u === id).length;
    assert.strictEqual(n, 1, id + ' is used by ' + n + ' chapters, expected 1');
  }
});

t('every widget exposes its step API', () => {
  for (const id of WIDGET_IDS) {
    const w = L.widgets[id];
    assert.strictEqual(w.id, id, id + ': id field must match its key');
    assert.ok(typeof w.title === 'string' && w.title, id + ': needs a title');
    assert.ok(Array.isArray(w.steps) && w.steps.length >= 2,
      id + ': a widget that teaches by manipulation needs at least two steps');
    w.steps.forEach((s, i) => {
      assert.ok(s.label && typeof s.label === 'string', id + ' step ' + i + ': needs a label');
      assert.ok(s.note && s.note.length > 40,
        id + ' step ' + i + ': needs a note that says something');
    });
    assert.strictEqual(typeof w.svg, 'function', id + ': needs svg(step)');
  }
});

t('every widget draws at every step', () => {
  for (const id of WIDGET_IDS) {
    const w = L.widgets[id];
    for (let i = 0; i < w.steps.length; i++) {
      const out = w.svg(i);
      assert.strictEqual(typeof out, 'string', id + ' step ' + i + ': svg must return a string');
      assert.ok(out.startsWith('<svg'), id + ' step ' + i + ': must start with <svg');
      const open = (out.match(/<svg/g) || []).length;
      const close = (out.match(/<\/svg>/g) || []).length;
      assert.strictEqual(open, close, id + ' step ' + i + ': unbalanced <svg> tags');
    }
  }
});

t('no widget emits NaN, undefined or null into its markup', () => {
  // a geometry bug reaches the screen as the literal text "NaN" in a
  // coordinate, which silently collapses an element rather than failing
  for (const id of WIDGET_IDS) {
    const w = L.widgets[id];
    for (let i = 0; i < w.steps.length; i++) {
      const out = w.svg(i);
      for (const bad of ['NaN', 'undefined', 'null']) {
        assert.ok(out.indexOf(bad) === -1,
          id + ' step ' + i + ': markup contains "' + bad + '"');
      }
    }
  }
});

t('out-of-range and junk steps clamp instead of throwing', () => {
  for (const id of WIDGET_IDS) {
    const w = L.widgets[id];
    const last = w.steps.length - 1;
    assert.strictEqual(w.svg(-5), w.svg(0), id + ': negative step must clamp to the first');
    assert.strictEqual(w.svg(999), w.svg(last), id + ': overshoot must clamp to the last');
    for (const junk of [undefined, null, NaN, 'x', {}]) {
      const out = w.svg(junk);
      assert.ok(out.startsWith('<svg'), id + ': junk step "' + String(junk) + '" broke it');
    }
  }
});

t('parameterised widgets redraw across their whole range', () => {
  const withParam = WIDGET_IDS.filter(id => L.widgets[id].param);
  assert.ok(withParam.length >= 2, 'expected at least two slider widgets');
  for (const id of withParam) {
    const w = L.widgets[id];
    const p = w.param;
    assert.ok(p.min < p.max && p.step > 0, id + ': nonsensical param range');
    assert.ok(p.value >= p.min && p.value <= p.max, id + ': default param outside its range');
    for (let v = p.min; v <= p.max; v += (p.max - p.min) / 12) {
      const out = w.svg(0, v);
      assert.ok(out.startsWith('<svg'), id + ': param ' + v + ' broke the drawing');
      assert.ok(out.indexOf('NaN') === -1, id + ': param ' + v + ' produced NaN');
    }
  }
});

t('wick-vs-close applies the engine break rule, not a hard-coded answer', () => {
  // engine/structure.py: broken when close > level + max(1 tick, 0.05*ATR).
  // The widget's level is 105 with ATR 4.00, so the threshold is 105.20 and the
  // "break" bar closes at 105 + wick*0.55. A wick of 0.3 puts that close at
  // 105.165 — beyond the level but INSIDE the tolerance, so the widget must
  // stop calling it a break.
  const w = L.widgets.wickVsClose;
  assert.ok(w.svg(2, 3).includes('BREAK'), 'a deep wick should close past tolerance');
  const shallow = w.svg(2, 0.3);
  assert.ok(shallow.includes('NOT YET') || shallow.includes('NO BREAK'),
    'a close inside the tolerance must not be reported as a break');
});

t('sweep-vs-breakout renders both panels side by side', () => {
  const w = L.widgets.sweepVsBreakout;
  assert.strictEqual(w.layout, 'twin');
  const out = w.svg(2);
  assert.strictEqual((out.match(/<svg/g) || []).length, 2, 'twin layout needs two drawings');
  assert.ok(out.includes('SWEEP') && out.includes('BREAKOUT'));
});

t('zone lifecycle walks FRESH to BROKEN', () => {
  const w = L.widgets.zoneLifecycle;
  const labels = w.steps.map(s => s.label);
  assert.deepStrictEqual(labels, ['FRESH', 'TOUCHED', 'TESTED', 'WEAKENED', 'BROKEN']);
  labels.forEach((state, i) => {
    assert.ok(w.svg(i).includes(state), 'step ' + i + ' should render the state ' + state);
  });
});

/* ────────────────── ported engine logic ──────────────────
   These check the JavaScript against the Python it was copied from. A widget
   that disagrees with the engine teaches the wrong thing with full confidence,
   which is the failure mode this whole file exists to prevent. */

t('regime classifier matches engine/regime.py', () => {
  const B = (event, direction) => ({ event: event, direction: direction });
  const cases = [
    // [lastBreak, lastHighLabel, lastLowLabel, expected]
    [null, null, null, 'RANGE'],
    [null, 'HH', 'HL', 'RANGE'],                       // no break -> no trend
    [B('CHOCH', 'BEAR'), 'HH', 'HL', 'TRANSITION'],    // CHoCH wins over labels
    [B('CHOCH', 'BULL'), 'LH', 'LL', 'TRANSITION'],
    [B('BOS', 'BULL'), 'HH', 'HL', 'BULL_TREND'],
    [B('BOS', 'BULL'), 'HH', null, 'WEAKENING_BULL'],
    [B('BOS', 'BULL'), 'LH', 'HL', 'WEAKENING_BULL'],
    [B('BOS', 'BULL'), 'LH', 'LL', 'RANGE'],           // break says bull, labels refuse
    [B('BOS', 'BEAR'), 'LH', 'LL', 'BEAR_TREND'],
    [B('BOS', 'BEAR'), 'HH', 'LL', 'WEAKENING_BEAR'],
    [B('BOS', 'BEAR'), 'LH', 'HL', 'WEAKENING_BEAR'],
    [B('BOS', 'BEAR'), 'HH', 'HL', 'RANGE']
  ];
  for (const [brk, hi, lo, want] of cases) {
    assert.strictEqual(L.classifyRegime(brk, hi, lo), want,
      JSON.stringify([brk, hi, lo]) + ' -> expected ' + want);
  }
});

t('the regime widget covers all six states', () => {
  const seen = new Set();
  for (let i = 0; i < L.widgets.regimeMap.steps.length; i++) {
    const note = L.widgets.regimeMap.steps[i].note;
    ['BULL TREND', 'BEAR TREND', 'WEAKENING BULL', 'WEAKENING BEAR', 'TRANSITION', 'RANGE']
      .forEach(s => { if (note.includes(s)) seen.add(s); });
  }
  assert.strictEqual(seen.size, 6, 'the walkthrough visits ' + seen.size + ' of 6 states');
});

t('zone strength arithmetic matches engine/zones.py', () => {
  // formation_quality = min(100, 50 + min(30, cluster*10) + TF_WEIGHT)
  assert.strictEqual(L.zoneQuality(0, '4H'), 60);
  assert.strictEqual(L.zoneQuality(1, '4H'), 70);
  assert.strictEqual(L.zoneQuality(9, '1W'), 100, 'cluster contribution caps at 30');
  assert.strictEqual(L.zoneQuality(0, '15m'), 55);
  // freshness = 100 - 25*episodes - min(25, age//100), floored at 0; 0 if broken
  assert.strictEqual(L.zoneFreshness(0, 0, false), 100);
  assert.strictEqual(L.zoneFreshness(1, 0, false), 75);
  assert.strictEqual(L.zoneFreshness(2, 350, false), 47);
  assert.strictEqual(L.zoneFreshness(9, 0, false), 0, 'never negative');
  assert.strictEqual(L.zoneFreshness(0, 0, true), 0, 'broken is zero regardless');
  // strength = (quality + freshness) // 2, so a broken zone keeps its quality
  assert.strictEqual(L.zoneStrength(70, 100), 85);
  assert.strictEqual(L.zoneStrength(70, 0), 35);
  assert.strictEqual(L.zoneStrength(75, 50), 62, 'floor division, not rounding');
});

/* ─────────────────────────── orientation ─────────────────────────── */

t('orientation is four steps, persisted under a versioned key', () => {
  const o = L.orientation;
  assert.strictEqual(o.steps.length, 4);
  assert.ok(/^ss\./.test(o.key) && /v\d+$/.test(o.key), 'key should be namespaced and versioned');
  for (const s of o.steps) {
    assert.ok(s.title && s.html, 'each step needs a title and body');
  }
  assert.strictEqual(typeof o.open, 'function', 'orientation must be reopenable');
  assert.strictEqual(typeof o.dismiss, 'function');
  assert.strictEqual(typeof o.isDismissed, 'function');
});

t('step 2 says quiet is normal, roughly one setup a day', () => {
  // this is the whole reason the card exists: right now, silence reads as a
  // fault, and the operator has no way to tell a working filter from a dead app
  const s = L.orientation.steps[1];
  assert.ok(/quiet is normal/i.test(s.html), 'step 2 must say quiet is normal');
  assert.ok(/one setup a day/i.test(s.html), 'step 2 must give the expected rate');
  assert.ok(s.quiet === true, 'step 2 should be flagged for its own treatment');
});

t('orientation closes on the hover instruction', () => {
  assert.ok(/underlined explains itself/i.test(L.orientation.closer));
  assert.ok(/hover it/i.test(L.orientation.closer));
});

/* ─────────────────── glossary integration ───────────────────
   glossary.js returns silently on an unknown key, so a typo in data-t produces
   an underlined word that does nothing when you hover it. That is worse than
   leaving the word plain, and it is invisible without this check. */

const GLOSSARY_KEYS = (function () {
  const src = fs.readFileSync(path.join(__dirname, '..', 'static', 'glossary.js'), 'utf8');
  const body = src.slice(src.indexOf('window.GLOSSARY'), src.indexOf('\n};'));
  const keys = new Set();
  const re = /^\s{2}([A-Za-z_$][\w$]*)\s*:/gm;
  let m;
  while ((m = re.exec(body))) keys.add(m[1]);
  return keys;
})();

t('the glossary parsed cleanly', () => {
  assert.ok(GLOSSARY_KEYS.size > 30, 'only found ' + GLOSSARY_KEYS.size + ' glossary keys');
});

t('the five new terms this surface depends on are defined', () => {
  for (const k of ['confluence', 'confirmation', 'structuralStop', 'htfAlignment', 'expectancy']) {
    assert.ok(GLOSSARY_KEYS.has(k), 'glossary is missing "' + k + '"');
  }
});

t('every term a chapter underlines exists in the glossary', () => {
  const re = /data-t="([^"]+)"/g;
  const missing = [];
  for (const c of L.chapters) {
    const blob = c.mechanic + c.why + c.mistakes.map(m => m.wrong + m.right).join('');
    let m;
    while ((m = re.exec(blob))) if (!GLOSSARY_KEYS.has(m[1])) missing.push(c.id + ' -> ' + m[1]);
  }
  assert.deepStrictEqual(missing, [], 'undefined glossary terms: ' + missing.join(', '));
});

t('every term the orientation underlines exists in the glossary', () => {
  const re = /data-t="([^"]+)"/g;
  const missing = [];
  for (const s of L.orientation.steps) {
    let m;
    while ((m = re.exec(s.html))) if (!GLOSSARY_KEYS.has(m[1])) missing.push(s.title + ' -> ' + m[1]);
  }
  assert.deepStrictEqual(missing, [], 'undefined glossary terms: ' + missing.join(', '));
});

t('glossary.js has no duplicate keys', () => {
  // a duplicate is legal JavaScript and silently keeps the last definition,
  // which is how two agents editing the same file lose one of the entries
  const src = fs.readFileSync(path.join(__dirname, '..', 'static', 'glossary.js'), 'utf8');
  const body = src.slice(src.indexOf('window.GLOSSARY'), src.indexOf('\n};'));
  const seen = new Set(), dupes = [];
  const re = /^\s{2}([A-Za-z_$][\w$]*)\s*:/gm;
  let m;
  while ((m = re.exec(body))) {
    if (seen.has(m[1])) dupes.push(m[1]);
    seen.add(m[1]);
  }
  assert.deepStrictEqual(dupes, [], 'duplicate glossary keys: ' + dupes.join(', '));
});

/* ─────────────────── house rules ─────────────────── */

t('the module loads without a DOM and mounts nothing on its own', () => {
  // it is required above with no document present; reaching here proves the
  // boot path is guarded. mountWidget is still exported for the browser.
  assert.strictEqual(typeof L.mountWidget, 'function');
  assert.strictEqual(typeof document, 'undefined');
});

t('no colour is hard-coded outside the token set', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'static', 'lessons.js'), 'utf8');
  const hex = src.match(/#[0-9a-fA-F]{3,8}\b/g) || [];
  assert.deepStrictEqual(hex, [], 'hard-coded hex colours: ' + hex.join(', '));
});

t('the stylesheet adds no colours the design system does not define', () => {
  const css = fs.readFileSync(path.join(__dirname, '..', 'static', 'lessons.css'), 'utf8');
  const hex = css.match(/#[0-9a-fA-F]{3,8}\b/g) || [];
  assert.deepStrictEqual(hex, [], 'hard-coded hex colours in lessons.css: ' + hex.join(', '));
  // glow is the operating state's signature and is reserved for live signals
  assert.ok(!/box-shadow[^;]*var\(--accent/.test(css),
    'lessons.css must not glow with the operating accent');
});

console.log('\n' + pass + ' passed');
