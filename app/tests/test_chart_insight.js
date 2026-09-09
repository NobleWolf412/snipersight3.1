const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {chartInsightMarkup} = require('../static/chart-insight.js');
const source = fs.readFileSync(path.join(__dirname,'../static/chart-insight.js'),'utf8');
const sample = (symbol='BTCUSDT', freshness='FRESH') => ({symbol, timeframe:'1H',
  frames:[{timeframe:'1H',freshness,read:'UP',lookback_bars:120,target_bars:120,
    last_closed_at:7200,window_start:0,trading_regime:'TREND_UP',top_down_call:'ALIGNED'}],
  usage:{chart:'OBSERVATION_ONLY',higher_timeframes:'OBSERVATION_ONLY'},
  scanner_quality:{status:'NOT_RECORDED'},notice:'Current context is not trade approval.'});
assert.match(chartInsightMarkup(sample()), /What the bot sees/);
assert.match(chartInsightMarkup(sample()), /120 \/ 120 bars/);
assert.match(chartInsightMarkup(sample()), /Observation only/);
assert.match(chartInsightMarkup(sample('BTCUSDT','STALE')), /Current reading unavailable/);
assert.doesNotMatch(chartInsightMarkup(sample('BTCUSDT','STALE')), /<strong>up<\/strong>/);
assert.match(chartInsightMarkup(sample('<script>')), /&lt;script&gt;/);
// Exercise a late response, a market switch and route exit with a small DOM fake.
const root = {innerHTML:''}, listeners = {}, subscriptions = [];
let market = 'crypto', stopped = 0;
const ctx = {symbol:'BTCUSDT',tf:'1H'};
const shared = {subscribe(url, callback){subscriptions.push({url,callback}); return () => stopped++;}};
const window = {SSChartCtx:ctx,SSData:shared,SSMarkets:{current:()=>market}};
const document = {body:{dataset:{route:'trade'}},getElementById:()=>root};
vm.runInNewContext(source, {window,document,SSData:shared,addEventListener:(name,fn)=>listeners[name]=fn});
assert.equal(subscriptions.length,1);
window.SSChartCtx = {symbol:'ETHUSDT',tf:'1H'};
listeners['ss:chart-context']();
subscriptions[0].callback(sample());
assert.doesNotMatch(root.innerHTML,/BTCUSDT/);
subscriptions[1].callback(sample('ETHUSDT'));
assert.match(root.innerHTML,/ETHUSDT/);
subscriptions[1].callback(sample('ETHUSDT'),new Error('offline'));
assert.match(root.innerHTML,/context unavailable/);
market = 'stocks'; listeners['ss:market-change']();
subscriptions[1].callback(sample('ETHUSDT'));
assert.doesNotMatch(root.innerHTML,/ETHUSDT/);
assert.equal(stopped,2);
console.log('Chart insight: rendering, stale data, escaping, late response and market isolation passed');
