/* The translation layer: what the system stores vs what the trader decides.

   A UI audit (2026-08-09) walked the cockpit and reached one verdict — the
   screens are operationally honest and speak the wrong language. Too much of
   the interface says how evidence is stored and validated; too little says
   what it means for the next decision. These pins hold the corrections that
   came out of it.

   Each pin is a PROPERTY, not a wording. Copy on these surfaces is rewritten
   often and a test that pins a sentence is a test that gets deleted the first
   time someone improves it. What must not come back is the defect: a scope
   that is silently wrong, a verdict the client invented, two words for one
   idea, or a screen that leads with provenance instead of the answer.
*/
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const S = f => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const HTML = S('shell.html');
const SHELL = S('shell.js');
const CSS = S('ss.css');
const FUNNEL = S('funnel.js');
const FACTOR = S('factor-evidence.js');
const COCKPIT = S('cockpit-workspaces.js');

let passed = 0;
function ok(name, fn) {
  try { fn(); console.log('  ok   ' + name); passed++; }
  catch (e) { console.log('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('trader translation');

/* ---------------------------------------------------------------- encoding */

ok('no double-encoded separator survives in any served file', () => {
  /* `Â·` is UTF-8 `·` decoded as latin-1 and re-encoded. It painted a stray Â
     on Factors, Journal and Promotion for as long as those lines existed,
     because it reads correctly in an editor that guesses the wrong codec and
     nothing else complains. It came in by paste, so it can come back the same
     way — and only a text assertion will notice.

     Checked across every served script, not the two files it happened to be
     in: pinning the files would pass while a third acquired it. */
  const dir = path.join(__dirname, '..', 'static');
  const offenders = fs.readdirSync(dir)
    .filter(f => /\.(js|css|html)$/.test(f) && f !== 'lightweight-charts.js')
    .filter(f => /Â/.test(fs.readFileSync(path.join(dir, f), 'utf8')));
  assert.deepStrictEqual(offenders, [],
    'double-encoded characters are back in: ' + offenders.join(', '));
});

/* ------------------------------------------------------- funnel vocabulary */

ok('the three funnel words are distinct', () => {
  /* "Tradeable now 14" sat directly above "Nothing to take right now" and the
     audit read it as a contradiction. It is not one — 14 markets the risk
     authority MAY size is a different quantity from 0 setups that cleared
     entry — but the interface used one word for the first and a denial for
     the third, so the operator had to be told the difference rather than
     seeing it. Three stages, three names. */
  assert(/Eligible markets/.test(HTML),
    'the eligible-markets tile lost its name');
  assert(/Setups ready/.test(HTML), 'the setups-ready tile lost its name');
  assert(!/>Tradeable now</.test(HTML),
    '"Tradeable now" is back on a tile — it reads as "available to trade now" ' +
    'directly above a line saying no trade is available');
  assert(!/'Nothing to take right now\.'/.test(SHELL),
    'the disposition says "nothing to take" again — it denies the tile beside ' +
    'it instead of naming a different stage of the same funnel');
});

ok('the scanner chip and the status bar name the same set as the tile', () => {
  /* One vocabulary or none. The header said TRADEABLE while the tile said
     something else, which is how a reader concludes they are two measurements. */
  assert(!/WATCHING \$\{sets\.tradeable\} TRADEABLE/.test(SHELL),
    'the header chip says TRADEABLE while the tile it summarises says eligible');
  assert(/ELIGIBLE/.test(SHELL), 'the header chip no longer names the set');
});

/* --------------------------------------------------- degraded consequences */

ok('a data gate states its scope, and the scopes are not averaged', () => {
  /* The three gates have genuinely different blast radii — QUALITY_BLOCKED
     drops a whole symbol, NO_DATA drops one timeframe of it, SHORT_HISTORY
     drops nothing. One sentence covering all three would be wrong for two of
     them, and "wrong about whether a market is still trading" is the exact
     class of error this surface exists to prevent. */
  /* Pinned as CODE, not as prose. Two earlier drafts of this file asserted on
     a substring that also appeared in the comment explaining the rule, so the
     rationale kept the test green while the branch it described was gone. */
  assert(/kinds\.has\('QUALITY_BLOCKED'\)/.test(SHELL) &&
         /kinds\.has\('NO_DATA'\)/.test(SHELL),
    'the diagnostics headline no longer branches on gate kind — one ' +
    'consequence sentence cannot be true for all three gates');
  const qi = FUNNEL.indexOf('QUALITY_BLOCKED:');
  const ni = FUNNEL.indexOf('NO_DATA:');
  assert(qi > 0 && ni > 0, 'the gate label table was renamed or removed');
  assert(/every engine on this|whole market|all engines/i.test(FUNNEL.slice(qi, qi + 200)),
    'the blocked-audit label no longer says it costs the whole market');
  /* Not a bare /rest/ — that matched "restart", "restore" and "interest", so a
     rewrite that dropped the scope clause could stay green on an unrelated
     word in the next label. */
  assert(/other timeframe/i.test(FUNNEL.slice(ni, ni + 280)),
    'the missing-candles label no longer scopes itself to one timeframe — ' +
    'without it the row reads as a dead market');
  /* The label must NOT claim the other timeframes are still scanning: that is
     false for a symbol whose candles are missing in all of them. It may only
     say they are unaffected by THIS gate. */
  assert(!/keeps scanning|still scanning/i.test(FUNNEL.slice(ni, ni + 280)),
    'the missing-candles label promises the market is still scanning ' +
    'elsewhere — untrue when every timeframe on it is empty');
});

ok('the pipeline verdict says it is whole-book', () => {
  /* The count above it is per-symbol/per-timeframe; this verdict is fetched
     with no symbol. Unqualified, the pair reads as one statement about the
     one failing market, which inverts its meaning. */
  /* Read the EMITTED strings only. An earlier draft of this pin searched a
     window of surrounding source and passed on the strength of the comment
     explaining the rule — the assertion was satisfied by its own rationale
     sitting two lines above the bug. Backticks cannot span a comment, so
     matching whole template literals reads what the operator will see. */
  const sentences = SHELL.match(/`[^`]*the pipeline is[^`]*`/g) || [];
  assert(sentences.length >= 2,
    'the sizing verdict was reworded past recognition — expected both the ' +
    'allowed and the stopped branch');
  sentences.forEach(s => assert(/book as a whole|whole book|every market/i.test(s),
    'a sizing verdict states no scope, so it reads as a claim about the ' +
    'failing market named directly above it: ' + s.slice(0, 70)));
});

/* ----------------------------------------------------- one authority again */

ok('the promotion verdict is the server\'s, not a count of cards', () => {
  /* The audit asked for one page-level answer instead of a carousel that
     shows one gate and blurs three. livegate.py already computes met/total
     and names the first unmet criterion, so the answer is READ. Counting the
     rendered cards instead would put a second authority on the number that
     decides live promotion (§6 rule 9). */
  assert(/id="gateVerdict"/.test(HTML), 'the promotion verdict line is gone');
  const i = SHELL.indexOf("$('gateVerdict')");
  assert(i > 0, 'nothing paints the promotion verdict');
  const block = SHELL.slice(i, i + 700);
  assert(/lastGate\.headline/.test(block),
    'the verdict no longer quotes the server headline — if it derives the ' +
    'count locally the card rail and the verdict can disagree');
  assert(!/filter\([^)]*\)\.length/.test(block),
    'the verdict counts something itself instead of reading met/total');
});

ok('the verdict scopes itself to evidence without restating the other locks', () => {
  /* Two failures are possible here and both matter. A bare "promotion met"
     over four EVIDENCE criteria overclaims. But naming the remaining locks in
     this string duplicates #promotionSummary, which renders the server's own
     MET/NOT MET for those same locks a few elements below — an audit caught
     that draft, where the two could state opposite things on one panel. */
  const i = SHELL.indexOf("$('gateVerdict')");
  const block = SHELL.slice(i, i + 800);
  assert(/evidence/i.test(block),
    'the verdict no longer says its four are the evidence gate, so it reads ' +
    'as a verdict on live promotion as a whole');
  const met = (block.match(/'Evidence gate met[^']*'/) || [''])[0];
  assert(met, 'the met branch was reworded past recognition');
  assert(!/shadow|testnet|router/i.test(met),
    'the met branch lists the remaining locks itself instead of pointing at ' +
    'the strip that reads them from the server — the two can disagree');
});

/* ------------------------------------------------------- provenance, plain */

ok('store enums are given sentences, and unmapped ones stay shouting', () => {
  /* "POPULATION FUNDED PAPER TRADES WINDOW ACTIVE BASELINE" is provenance a
     database can read. The map fixes the ones we ship; the FALLBACK is the
     part that matters — an enum added engine-side must keep its raw shape so
     it is visibly missing a sentence rather than quietly dressed as English
     (§6 rule 6, loud fallback). */
  assert(/SCOPE_SENTENCES/.test(COCKPIT), 'the scope vocabulary is gone');
  assert(/FUNDED_PAPER_TRADES:/.test(COCKPIT),
    'the shipped populations lost their sentences');
  const i = COCKPIT.indexOf('const scopeLabel');
  assert(i > 0, 'scopeLabel was renamed — the scope strip has no translator');
  assert(/\|\|\s*label\(value\)/.test(COCKPIT.slice(i, i + 400)),
    'an unmapped enum no longer falls back to its raw form — new vocabulary ' +
    'would be silently prettified instead of visibly untranslated');
  assert(/window\.SSScopeLabel/.test(COCKPIT) && /SSScopeLabel/.test(FACTOR),
    'Factors keeps its own scope table — two tables for one vocabulary is ' +
    'how two screens come to name one scope differently');
});

ok('the readable scope values are not uppercased back into enums', () => {
  /* scopeLabel turned FUNDED_PAPER_TRADES into "Funded paper trades" and the
     strip's own `text-transform:uppercase` painted FUNDED PAPER TRADES —
     byte-identical to the string the audit complained about. The translation
     was invisible on the one surface it was written for, and every text
     assertion about the source passed while the screen did not change. */
  const i = CSS.indexOf('#performancePopulation');
  assert(i > 0, 'the scope values lost their case override');
  assert(/text-transform:\s*none/.test(CSS.slice(i, i + 260)),
    'the scope strip uppercases its values again, which undoes the mapping ' +
    'without changing any of the source these tests read');
});

ok('both gate kinds speak when both are present', () => {
  /* An `else if` let one quality-blocked symbol silence the sentence covering
     twenty missing-candle rows, leaving a whole-market consequence sitting
     under a count of twenty-one. */
  const i = SHELL.indexOf("kinds.has('QUALITY_BLOCKED')");
  assert(i > 0, 'the gate-kind branch is gone');
  assert(!/\belse\s+if\s*\(\s*kinds\.has/.test(SHELL),
    'the second gate kind is an else-if again — one kind of gate silences ' +
    'the consequence sentence belonging to the other');
});

ok('Factors leads with its conclusion, not its population', () => {
  /* The screen had a real answer — no factor is calibrated, do not size on
     grades — under two lines of enum provenance and a paragraph of policy
     language. The conclusion goes first. */
  assert(/factor-verdict/.test(FACTOR) && /factor-verdict/.test(CSS),
    'the Factors verdict line is gone, or is unstyled');
  const v = FACTOR.indexOf('factor-verdict');
  const p = FACTOR.indexOf('population-note');
  assert(v > 0 && p > 0 && v < p,
    'the population strip is back above the verdict — the screen leads with ' +
    'where the numbers came from instead of what they mean');
  /* Rule 7 — evidence is recorded, not filtered on, until it has been graded
     — has to reach the operator in words, in BOTH branches, and it has to
     stay above the disclosure. The one conclusion nobody may draw from this
     panel is that a grade let a trade through. Pinned by meaning rather than
     by the old sentence: the wording moved to plain English on purpose, and
     an assertion on the phrasing would have blocked exactly that. */
  const consequence = FACTOR.slice(FACTOR.indexOf('const consequence'),
                                   FACTOR.indexOf('root.innerHTML'));
  assert(consequence.length > 0, 'the consequence line is gone entirely');
  assert(/cannot approve a trade|cannot approve/.test(consequence),
    'the graded branch stopped saying a passing factor still cannot approve ' +
    'or size a trade');
  assert(/not picking or sizing|is picking or sizing/.test(consequence),
    'the ungraded branch no longer tells the operator what not to do with it');
  assert(FACTOR.indexOf('factor-consequence') < FACTOR.indexOf('factor-why'),
    'the consequence moved inside the disclosure — the one thing that must ' +
    'never be optional reading on this panel');
});

ok('a warning carried by two payloads prints once', () => {
  /* grade and evidence both carry the back-fill warning, and rendering each
     list where it arrived printed the same amber line twice on one screen.
     Deduped by text — and still rendered, because a warning in only one
     payload is the only place it appears. */
  assert(/new Set\(\[\.\.\.\(grade\.warnings/.test(FACTOR),
    'the two warning lists are no longer merged and deduped');
  assert(!/\(evidence\.warnings \|\| \[\]\)\.map/.test(FACTOR),
    'the second warning list renders again on its own — the same sentence ' +
    'appears twice and reads as two defects');
});

/* ------------------------------------------------------------- readability */

ok('the verdict lines are body type, not tracked mono', () => {
  /* The audit\'s structural note: near-everything is uppercase tracked mono,
     so nothing is differentiated and the operator must read all of it. The
     lines meant to be READ as sentences say so in their type. */
  const i = CSS.indexOf('.factor-verdict');
  assert(i > 0, 'the verdict styling is gone');
  const block = CSS.slice(i, i + 420);
  assert(/--f-body/.test(block),
    'the verdict lines render in the chrome typeface — a sentence set as a ' +
    'label is scanned and skipped, not read');
  assert(!/text-transform:uppercase/.test(block),
    'the verdict lines are uppercased again');
});

console.log('\n  ' + passed + ' passed');
