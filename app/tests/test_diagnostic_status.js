const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const status = require('../static/diagnostic-status.js');
const source = name => fs.readFileSync(path.join(__dirname, '..', name), 'utf8');
const mounts = {diagEvidence: {innerHTML: ''}, diagHistory: {innerHTML: ''}};
global.document = {getElementById: id => mounts[id]};
const sample = {
  headline: 'Scanner is reporting.', generated_at: 1788730000,
  scanner: {meaning: 'Progress verified.', observed_at: 1788730000},
  audit: {status: 'PASS', observed_at: 1788730000, fresh: true, accepted_notes: [{}], blockers: []},
  supervisor: {observed_at: 1788730000, detail: 'QUARANTINE <script>alert(1)</script>'},
  history_source: {meaning: 'Bounded history.', available: true},
  history: [{state: 'recovered', observed_at: 1788700000, recovered_at: 1788730000,
    detail: '<img src=x onerror=alert(1)>', meaning: 'Progress only.', action: 'No restart needed.'}]
};
status.render(sample);
assert.match(mounts.diagEvidence.innerHTML, /No repair is required/);
assert.match(mounts.diagEvidence.innerHTML, /not the scanner verdict/);
assert(!mounts.diagEvidence.innerHTML.includes('<script>'));
assert(!mounts.diagHistory.innerHTML.includes('<img'));
assert.match(mounts.diagHistory.innerHTML, /Recovery evidence/);
assert.match(status.historyText(sample).join('\n'), /RECOVERED \(scanner progress only\)/);
assert.match(status.lines(null).join(''), /not been verified/);
status.render(null);
assert.equal(mounts.diagHistory.textContent, 'History unavailable.');
assert.match(source('static/funnel.js'), /SSDiagnosticStatus\?\.render\(m.diagnosticStatus\)/);
assert.match(source('static/shell.js'), /SSDiagnosticStatus.lines\(t.diagnostic_status\)/);
assert.match(source('server.py'), /"diagnostic_status": diagnostic_status.snapshot\(con\)/);
console.log('PASS: dated diagnostics, escaped history, shared report evidence');
