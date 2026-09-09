/* Execute the calendar renderer with an offline DOM/transport. No live writes. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../static/macro-calendar.js'), 'utf8');
class Element {
  constructor(){ this.textContent = ''; this.children = []; }
  appendChild(child){ this.children.push(child); }
  replaceChildren(){ this.textContent = ''; this.children = []; }
  text(){ return this.textContent + this.children.map(child => child.text()).join(' '); }
}
async function run(data, failure){
  const headline = new Element(), details = new Element(), requests = [];
  const context = {
    document: {hidden: false, getElementById: id => id === 'macroHeadline' ? headline : details,
      createElement: () => new Element(), addEventListener(){}},
    fetch: async (url, options) => {
      requests.push({url, options});
      if(failure) throw new Error('offline');
      return {ok: true, json: async () => data};
    },
    Date, AbortController: global.AbortController, setTimeout, clearTimeout, setInterval(){},
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return {headline, details, requests};
}
(async () => {
  const data = {status: 'PARTIAL', near_event: false,
    sources: [{source: 'FED', status: 'FRESH', observed_at: 1788566400},
      {source: 'BLS', status: 'UNAVAILABLE', observed_at: null, error: 'HTTP 403'}],
    events: [{title: 'FOMC meeting', precision: 'DATE_RANGE', date_label: '2026-09-15 to 2026-09-16',
      source_status: 'FRESH'}]};
  const partial = await run(data);
  assert(partial.headline.text().includes('Calendar incomplete'));
  assert(partial.headline.text().includes('ET dates only'));
  assert(partial.details.text().includes('release time not supplied'));
  assert(partial.details.text().includes('BLS: Unavailable'));
  assert(partial.details.text().includes('HTTP 403'));
  assert(partial.details.text().includes('risk limits are unchanged'));
  assert.equal(partial.requests[0].url, '/api/macro-calendar');
  assert.equal(partial.requests[0].options.method, undefined);
  const outage = await run({}, true);
  assert(outage.headline.text().includes('Calendar unavailable'));
  assert(outage.headline.text().includes('do not assume'));
  const empty = await run({status: 'UNAVAILABLE', events: []});
  assert(empty.headline.text().includes('No verified upcoming event'));
  const untrusted = await run({...data, events: [{...data.events[0], title: '<img onerror=alert(1)>'}]});
  assert(untrusted.headline.textContent.includes('<img onerror=alert(1)>'));
  assert(!source.includes('innerHTML'), 'external calendar text must not become markup');
  assert(!source.includes('POST'), 'calendar renderer must have no write action');
  console.log('macro calendar: rendering, degraded coverage, offline and text-safety checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
