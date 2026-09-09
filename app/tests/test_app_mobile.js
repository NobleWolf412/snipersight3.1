/* Presentation contracts complement the rendered phone checks. No live writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = file => fs.readFileSync(path.join(__dirname,'../static',file),'utf8');
const html = read('shell.html'), css = read('app-mobile.css');
const base = read('ss.css'), workspace = read('workspaces.js');
const declarations = new Set([...(base + css).matchAll(/(--[\w-]+)\s*:/g)].map(m=>m[1]));
for(const match of css.matchAll(/var\((--[\w-]+)/g)) assert(declarations.has(match[1]),`Undefined ${match[1]}`);
assert(html.indexOf('app-mobile.css') > html.indexOf('ss.css'));
assert.match(css,/grid-template-columns:repeat\(5,minmax\(0,1fr\)\)/);
assert.match(css,/min-width:0; min-height:100px/);
assert.match(css,/body\[data-market="crypto"\]/);
assert.match(workspace,/split\(' '\).includes\(view\)/);
assert.match(workspace,/fromTabs && !from.getClientRects\(\).length/);
for(const id of ['modeControls','guardFields','setFields','setApply','setReset','setCpModel','citadelOpen','tradeSetupEvidence','chartInsight']){
  assert.equal(html.split(`id="${id}"`).length - 1,1,`${id} must keep a single handler target`);
}
for(const view of ['home','venues','automation','risk','assistant','help']) assert(html.includes(`data-view="${view}"`));
assert(html.includes('data-system-view="automation strategies"'));
assert(!workspace.includes('fetch('),'Changing categories must not save settings');
assert(read('shell.js').includes("new CustomEvent('ss:route-change'"));
for(const file of ['mode-control.js','cockpit-workspaces.js','chart-insight.js','trade-workspace.js'])
  assert(read(file).includes('ss:route-change'),`${file} must handle replaceState navigation`);
assert(read('mode-control.js').includes("controls.querySelectorAll('button').forEach(button => button.disabled = true)"));
assert(read('trade-workspace.js').includes("getElementById('tradeSetupEvidence').innerHTML"));
assert.equal((html.match(/data-trade-close/g)||[]).length,2);
console.log('App mobile: tokens, five tabs, settings ownership, route refresh and sheet mounts passed');
