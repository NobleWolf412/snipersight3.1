const fs = require('fs');
const path = require('path');
const assert = require('assert');

const STATIC = path.join(__dirname, '..', 'static');
const HTML = fs.readFileSync(path.join(STATIC, 'shell.html'), 'utf8');
const OPS = fs.readFileSync(path.join(STATIC, 'operations.js'), 'utf8');
const OPPS = fs.readFileSync(path.join(STATIC, 'opportunities.js'), 'utf8');
const CSS = fs.readFileSync(path.join(STATIC, 'ss.css'), 'utf8');

assert(HTML.includes('id="nextActionPrimary"'));
assert(HTML.includes('id="nextActionBot"'));
assert(HTML.includes('id="citadelState"'));
assert(/data\.next_action/.test(OPS));
assert(/data\.citadel/.test(OPS));
assert(/api\('\/api\/command'\)/.test(OPS));
assert(/routeLoad/.test(fs.readFileSync(path.join(STATIC, 'cockpit-workspaces.js'), 'utf8')));
assert(/SSOpenOpportunity/.test(OPS) && /window\.SSOpenOpportunity = openTrade/.test(OPPS));
assert(/height:100vh;height:100dvh/.test(CSS));
assert(/env\(safe-area-inset-bottom/.test(CSS));

console.log('next action: 10/10 passed');
