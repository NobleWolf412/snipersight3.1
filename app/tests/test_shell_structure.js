/* The shell's element tree has to close, and no text assertion can prove it.

   Two closing divs were left behind by an unfinished panel move in Results.
   They terminated .shell forty lines early, so #s-settings, #s-diagnostics and
   footer.statusbar parsed as children of <body> — below a height:100vh shell
   inside overflow:hidden. Settings and Diagnostics rendered blank. The nav
   highlighted the destination and the stage stayed empty: no error, no message,
   no route back. Dead with them: the number-key shortcuts for those two
   surfaces, the permanent "Sim only — no live orders" statement in the status
   bar, the Backend console toggle, Decision Provenance, and every cross-surface
   pointer the UI writes ("Settings → Going live", "full book in Diagnostics").

   The whole JS suite ran green through all of it, because these suites assert
   against the TEXT of the static files. Every string they look for was present
   and correctly spelled. Text was never the thing that broke.

   This is the second instance — the comment above #edgeRoot records an earlier
   one, where two closers went missing and the panels after them were parsed as
   edgeRoot's children and wiped on mount. A defect that recurs is a defect the
   suite is not testing, so this file tests the shape rather than the spelling:
   strip comments, walk the tags, and assert the tree closes and every surface
   sits at the same depth. It needs no DOM library and no browser.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');

/* Comments are stripped first and newlines preserved, so reported line numbers
   still match the file. Prose inside a comment mentions closing tags more than
   once in this file, and counting those would fail the suite over English. */
const CODE = HTML.replace(/<!--[\s\S]*?-->/g, m => '\n'.repeat((m.match(/\n/g) || []).length));

/* Depth after each line, tracking <div> only. Void and self-closing elements
   never appear as <div>, so open-minus-close is the whole rule here. */
function depths(src) {
  const out = [];
  let d = 0;
  src.split('\n').forEach((line, i) => {
    d += (line.match(/<div\b/g) || []).length;
    d -= (line.match(/<\/div>/g) || []).length;
    out.push({ line: i + 1, depth: d, text: line.trim() });
  });
  return out;
}

const ROWS = depths(CODE);
/* THIS LIST FAILS OPEN. A surface that is not named here is not depth-checked
   at all, and a section that parses outside .shell renders blank with nothing
   saying so — which is the entire reason this file exists. Anything with
   `class="surface"` belongs in it, on the commit that adds it. */
const SURFACES = ['s-command', 's-chart', 's-results', 's-ledger', 's-settings',
                  's-diagnostics'];

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('shell.html structure');

ok('every <div> in shell.html is closed', () => {
  const final = ROWS[ROWS.length - 1].depth;
  assert.strictEqual(final, 0,
    `div depth ends at ${final}, not 0. ` +
    (final < 0 ? `${-final} stray </div>` : `${final} unclosed <div>`) +
    '. First line where depth goes negative: ' +
    ((ROWS.find(r => r.depth < 0) || {}).line || 'none'));
});

ok('div depth never goes negative', () => {
  const bad = ROWS.find(r => r.depth < 0);
  assert.ok(!bad, bad && `depth ${bad.depth} at line ${bad.line}: ${bad.text}`);
});

ok('every surface sits at the same div depth', () => {
  const found = SURFACES.map(id => {
    const row = ROWS.find(r => r.text.includes(`id="${id}"`));
    assert.ok(row, `surface ${id} not found in shell.html`);
    return { id, depth: row.depth, line: row.line };
  });
  const base = found[0].depth;
  const off = found.filter(f => f.depth !== base);
  assert.strictEqual(off.length, 0,
    'surfaces at a different depth than ' + found[0].id + ` (${base}): ` +
    off.map(f => `${f.id}=${f.depth} (line ${f.line})`).join(', ') +
    ' — a section outside .shell renders blank.');
});

ok('the list above covers every surface in the markup', () => {
  /* Closes the fail-open hole. SURFACES used to be five hand-written ids, and
     a sixth section could be added — and be broken — without this file ever
     looking at it. Read the markup instead and require the list to match. */
  const inMarkup = [...CODE.matchAll(/<section class="surface[^"]*" id="([\w-]+)"/g)]
    .map(m => m[1]);
  assert(inMarkup.length >= 5, `the section scan found ${inMarkup.length} surfaces`);
  const unchecked = inMarkup.filter(id => !SURFACES.includes(id));
  assert.strictEqual(unchecked.length, 0,
    `${unchecked.join(', ')} carries class="surface" and is not in SURFACES, ` +
    'so nothing in this file checks that it closes inside .shell.');
});

ok('the status bar closes inside the shell, not after it', () => {
  const footer = ROWS.find(r => r.text.includes('<footer class="statusbar"'));
  const command = ROWS.find(r => r.text.includes('id="s-command"'));
  assert.ok(footer, 'footer.statusbar not found');
  assert.strictEqual(footer.depth, command.depth,
    `footer.statusbar is at depth ${footer.depth} but #s-command is at ${command.depth}. ` +
    'The "Sim only — no live orders" statement is unreachable when these differ.');
});

ok('Results has no orphan skeleton bars left in it', () => {
  /* The bars the unfinished move left behind had no panel and no JS owner, so
     they shimmered for the life of the page on the surface that answers "is
     this actually working?". A skeleton is a promise that content is coming. */
  const start = ROWS.find(r => r.text.includes('id="s-results"')).line;
  const end = ROWS.find(r => r.text.includes('id="s-settings"')).line;
  const base = ROWS.find(r => r.text.includes('id="s-results"')).depth;
  /* <div>-based, specifically. The panels legitimately nest <span
     class="skel skel-line"> inside a <span class="skeleton"> live region; those
     have an owner and get replaced on render. The orphans were divs sitting
     bare in the section. */
  const orphans = ROWS.filter(r =>
    r.line > start && r.line < end &&
    /<div class="skel skel-line"/.test(r.text) &&
    r.depth <= base + 1);
  assert.strictEqual(orphans.length, 0,
    'skeleton bars directly inside #s-results with no panel wrapper, line(s): ' +
    orphans.map(o => o.line).join(', '));
});

ok('#edgeRoot is documented where it actually lives', () => {
  /* CLAUDE.md: documenting something that does not exist costs the reader more
     than documenting nothing.

     This panel has crossed between the two surfaces twice, and BOTH times the
     comment describing the move outlived the move. The last round left two
     contradicting comments in Diagnostics — one saying it had gone to Results,
     one saying it had come back — with no way for a reader to tell which was
     true. That is what this test is for; it is not really about an offset.

     It lives in Results now: Diagnostics is faults, Results is the record, and
     at 1,488px it was 40% of a Diagnostics surface that had grown to four and
     a half screens. If it moves again, the comment beside it moves too. */
  const results = HTML.indexOf('id="s-results"');
  const diag = HTML.indexOf('id="s-diagnostics"');
  const edge = HTML.indexOf('id="edgeRoot"');
  assert.ok(edge > -1, '#edgeRoot not found in shell.html');
  assert.ok(edge > results && edge < diag,
    '#edgeRoot moved out of Results — move the comment that explains why it ' +
    'lives there along with it, or this file is now the stale one.');
  /* And the account of the move travels with the panel: a bare div would pass
     the offsets above while telling the next reader nothing. */
  const near = HTML.slice(Math.max(0, edge - 1400), edge);
  assert.ok(/Diagnostics is faults\. Results is the record\./.test(near),
    'the comment explaining why #edgeRoot sits in Results is gone or moved ' +
    'away from it — it is the whole point of this check');
});

console.log(`  ${passed}/7 passed`);
