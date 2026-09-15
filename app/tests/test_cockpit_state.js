/* Executable request-ordering contract: no browser or live endpoint involved. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

async function main() {
  const pending = [];
  const scope = {AbortController, fetch: () => new Promise(resolve => pending.push(resolve))};
  vm.createContext(scope);
  const source = fs.readFileSync(path.join(__dirname, '../static/cockpit/state.js'), 'utf8');
  vm.runInContext(source.replace('export class Selection', 'class Selection') + '\nthis.Selection=Selection;', scope);
  const selection = new scope.Selection();
  const result = value => ({ok:true,json:async()=>({value})});
  const old = selection.read('account','/old');
  const fresh = selection.read('account','/fresh');
  pending[1](result('fresh'));pending[0](result('old'));
  assert.equal((await fresh).value,'fresh');assert.equal(await old,null);
  const crypto = selection.read('journal','/crypto');
  selection.change();
  pending[2](result('crypto'));assert.equal(await crypto,null);
  const preview = selection.read('preview','/ticket');
  selection.invalidate('preview');
  pending[3](result('stale terms'));assert.equal(await preview,null);
  const rejected = selection.read('arm','/arm');
  pending[4]({ok:false,status:400,json:async()=>({detail:'PREVIEW_EXPIRED'})});
  await assert.rejects(rejected,e=>e.status===400&&e.message==='PREVIEW_EXPIRED');
  console.log('Cockpit request ordering: passed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
