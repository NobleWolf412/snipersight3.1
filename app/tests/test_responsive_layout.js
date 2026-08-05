/* The cockpit is now a two-viewport product, and neither viewport has a test.

   The JS suites here assert against the TEXT of the static files, which is
   right for contracts but blind to layout: a grid can be pinned to five fixed
   columns and every existing suite still passes while the surface is unusable
   on a phone. That is exactly how .deck-row survived the responsive pass —
   .jnl-row, .pos-row, .radar-row and .budget-grid all collapse at 900 and the
   deck was simply missed, so its neighbours made it look done.

   So this suite does not check that particular selectors were fixed. It checks
   the CLASS: every rule that pins a layout to fixed pixel columns must have a
   narrow-viewport counterpart. A new panel added next month is covered without
   anybody remembering to add it here.

   What it cannot do is tell you the page LOOKS right — no browser runs here.
   Measurements in the comments were taken against a real 412x915 viewport
   driven through the browser, and they are the evidence; this file is the
   ratchet that stops them being undone. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const STATIC = path.join(__dirname, '..', 'static');
const read = f => fs.readFileSync(path.join(STATIC, f), 'utf8');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

/* The four breakpoints this file is allowed to have. ss.css's own header
   records being rescued from twelve ad-hoc thresholds; without a pin they grow
   back one convenient number at a time. */
const BREAKPOINTS = [640, 900, 1100, 1180];
/* A phone is below both of the low two. Anything above 900 is a laptop
   question, so a rule that only collapses at 1100 has not been made to fit a
   phone. */
const PHONE_COVERS = 900;

/* Rules with their media context. A real parser rather than a line scan,
   because a rule's nesting is the whole question being asked.

   Comments are stripped FIRST, and that is not tidiness. This file's comments
   sit immediately above the rule they explain and are frequently longer than
   it, so a parser that accumulates them into the selector reports
   `.chart-main` as uncovered while its collapse rule sits forty lines below —
   which is precisely what the first run of this suite did. Newlines are kept
   so reported line numbers still point at the real rule. */
function rules(srcRaw) {
  const src = srcRaw.replace(/\/\*[\s\S]*?\*\//g,
    m => m.replace(/[^\n]/g, ' '));
  const out = [];
  let i = 0, buf = '', line = 1;
  const stack = [];
  while (i < src.length) {
    const ch = src[i];
    if (ch === '{') {
      const head = buf.trim(); buf = '';
      if (head.startsWith('@')) { stack.push(head); i++; continue; }
      let j = i + 1, d = 1;
      while (j < src.length && d) { if (src[j] === '{') d++; else if (src[j] === '}') d--; j++; }
      out.push({sel: head, body: src.slice(i + 1, j - 1), line, media: stack.slice()});
      line += src.slice(i, j).split('\n').length - 1;
      i = j; continue;
    }
    if (ch === '}') { stack.pop(); buf = ''; }
    else buf += ch;
    if (ch === '\n') line++;
    i++;
  }
  return out;
}

const maxWidths = media =>
  media.flatMap(m => [...m.matchAll(/max-width:\s*(\d+)px/g)].map(x => +x[1]));

const coversPhone = media => maxWidths(media).some(w => w <= PHONE_COVERS);

/* A track that cannot shrink. minmax(0,1fr) and 1fr can; a bare 150px cannot,
   and a row of them has a hard floor no viewport can talk it out of. */
function fixedFloor(tracks) {
  const withoutMinmax = tracks.replace(/minmax\([^)]*\)/g, 'FLEX');
  return [...withoutMinmax.matchAll(/(\d+)px/g)].reduce((a, m) => a + +m[1], 0);
}

console.log('responsive layout');

for (const file of ['ss.css', 'diagnostics-ui.css']) {
  const src = read(file);
  const rs = rules(src);

  ok(`${file}: every fixed-column layout collapses for a phone`, () => {
    // selectors that get ANY grid-template-columns inside a phone-width block
    const covered = new Set();
    for (const r of rs) {
      if (!coversPhone(r.media)) continue;
      if (!/grid-template-columns|display:\s*block/.test(r.body)) continue;
      r.sel.split(',').forEach(s => covered.add(s.trim()));
    }
    const offenders = [];
    for (const r of rs) {
      if (coversPhone(r.media)) continue;
      const m = r.body.match(/grid-template-columns:\s*([^;}]+)/);
      if (!m) continue;
      const floor = fixedFloor(m[1]);
      if (floor < 300) continue;              // fits a phone with room to spare
      const parts = r.sel.split(',').map(s => s.trim());
      if (parts.some(s => covered.has(s))) continue;
      offenders.push(`${file}:${r.line}  ${r.sel.trim()}  floor≈${floor}px  {${m[1].trim()}}`);
    }
    assert.strictEqual(offenders.length, 0,
      'these pin a layout wider than a phone and never collapse:\n       ' +
      offenders.join('\n       '));
  });
}

ok('ss.css keeps to its four breakpoints', () => {
  const found = [...new Set(maxWidths(rules(read('ss.css')).flatMap(r => r.media)))].sort((a, b) => a - b);
  const extra = found.filter(w => !BREAKPOINTS.includes(w));
  assert.strictEqual(extra.length, 0,
    'new ad-hoc breakpoints: ' + extra.join(', ') + '. The file was rescued ' +
    'from twelve of these once; add to an existing one or change BREAKPOINTS ' +
    'deliberately.');
});

ok('the controls that WRITE are thumb-sized on a phone', () => {
  /* 24px is the WCAG floor for a pointer; Android asks 48dp, and the gap is
     not pedantry — one of these three is CLOSE on a live position, sitting in
     a dense list where the neighbouring target is what you actually hit. */
  const css = read('ss.css');
  const narrow = rules(css).filter(r => coversPhone(r.media) && /\.pos-acts/.test(r.sel));
  const sized = narrow.some(r => /min-height:\s*4[8-9]px|min-height:\s*[5-9]\dpx/.test(r.body));
  assert(sized, '.pos-acts buttons are not raised to a 48px target below 900px');
});

ok('a wide table scrolls rather than being clipped away', () => {
  /* Measured at 412px: the table wanted 440px inside a 345px panel, and
     .panel is overflow-x:hidden — the right-hand columns were not cramped,
     they were unreachable. */
  const css = read('ss.css');
  const hit = rules(css).some(r =>
    coversPhone(r.media) && /\.data-table/.test(r.sel + r.body) && /overflow-x:\s*auto/.test(r.body));
  assert(hit, 'no phone-width scroll container for .data-table');
});

ok('the nav hint appears only when the strip really has more', () => {
  /* A fade that is always on lies on the wider screens where everything fits.
     shell.js measures and sets the class; the mask hangs off that class, so
     the hint cannot appear on a strip with nothing hidden. */
  const css = read('ss.css');
  const js = read('shell.js');
  assert(/\.nav\.scrollable\s*\{[^}]*mask-image/.test(css.replace(/\s+/g, ' ')),
    'the fade is not bound to .scrollable');
  assert(/scrollWidth\s*-\s*\w*\.?clientWidth/.test(js) && /classList\.toggle\('scrollable'/.test(js),
    'shell.js no longer measures the strip before claiming it scrolls');
});

ok('a refusal the finger cannot hover is written on the surface', () => {
  /* The venue's reason for a dead SHORT button lived only in a title. A mouse
     reveals that; a finger does not, so on a phone the control was dead and
     silent. */
  const html = read('shell.html');
  const chart = read('chart.js');
  assert(/id="tkDirWhy"/.test(html), 'the visible slot for the reason is gone');
  assert(/\$\('tkDirWhy'\)/.test(chart) && /why\.textContent\s*=\s*reason/.test(chart),
    'chart.js stopped writing the venue reason into the visible slot');
  assert(/sb\.title\s*=\s*reason/.test(chart),
    'the pointer tooltip was dropped; it should stay alongside the text');
});

console.log('\n' + passed + ' passed');
process.exit(process.exitCode || 0);
