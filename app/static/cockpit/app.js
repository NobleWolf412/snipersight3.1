import {Selection} from './state.js';



const selection = new Selection();

const $ = (selector) => document.querySelector(selector);

const esc = (value) => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const money = value => value == null ? '—' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(value);

const date = value => value == null ? 'Not available' : new Date(value*1000).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});

const displayLabels = {
  SETUP_REQUIRED:'Setup needed', CONNECTIONS_CONFIGURED:'Connection details saved', 'CONTEXT ONLY':'News and context',
  ZONE_BROKE_UNCONFIRMED:'The support or resistance area broke before confirmation.', CONFIRMATION_TIMEOUT:'No confirming candle arrived before the deadline.',
  PULLBACK:'Pullback', REVERSAL:'Reversal', EXECUTED_ACCOUNT:'Paper account',
  OPERATOR:'You', BOT:'Bot', MANUAL:'You', PAPER:'Paper trading', OFF:'Off',
  PAPER_ROUTED:'Waiting for entry', PENDING:'Pending', PAPER_FILLED:'Open',
  PAPER_CLOSED:'Closed', PAPER_EXPIRED:'Expired', CANCELLED:'Cancelled',
  RISK_REJECTED:'Risk limit reached', HELD_OFF:'Not placed', REJECTED:'Not eligible',
  OPEN:'Open', DRAINING:'Waiting for trades to finish', SEALED:'Previous account',
  READY:'Ready', FORMING:'Forming', WATCHING:'Watching', BLOCKED:'Not available',
  LONG:'Long', SHORT:'Short', TP:'Target reached', SL:'Stop-loss reached',
  BE:'Break-even', MISSED:'Entry not reached', TIMEOUT:'Time limit reached',
  EXACT_SETTLEMENT:'Recorded prices and costs', LEGACY_R_ESTIMATE:'Estimated from an older trade result',
  LEGACY_MANUAL_RECORD:'Older manually placed trade', CURRENT:'Current account', ARCHIVE:'Previous accounts',
  UNAVAILABLE:'Unavailable', DELAYED:'Update delayed', HISTORICAL:'Older news',
  FRESH:'Up to date', AVAILABLE:'Available', OK:'Available', FIXTURE:'Practice example',
  UNGRADED:'Not yet rated', UNVERIFIED:'Not yet checked', RESEARCH:'Research', LOCKED:'Not enabled',
};
const label = value => displayLabels[value] ?? String(value ?? '—').replaceAll('_',' ');
function plain(message) {
  return String(message ?? '')
    .replace('Synthetic training data. Not market evidence, not investment advice, and excluded from strategy grades.',
      'Practice examples use made-up prices. They are not trading advice and do not count toward strategy performance.')
    .replace('Store a Massive API key for the point-in-time universe.', 'Add a Massive API key to access stock listings and their history.')
    .replace('Verify both connections before importing a stock universe.', 'Check both connections before loading stock listings.')
    .replace('The isolated stock universe has not been imported.', 'The stock list has not been loaded yet.')
    .replace('The stock scanner and stock-native strategies are not enabled.', 'Stock scanning and trading strategies are not available yet.')
    .replace(/consolidated SIP data|SIP market data/g,'combined stock-price data')
    .replace('SIP returned no latest bar', 'the price service returned no recent candle')
    .replace('Counterfactual strategy replay. These are not orders in your account.',
    'Research includes simulated trades and setup decisions, including skipped or expired setups. It is not your account’s trade history.')
    .replace('Compare different risk profiles in R, not dollars. Cancelled orders are not trades.',
      'When trade sizes differ, compare results against the amount risked. 1R equals that amount. Cancelled orders are not completed trades.')
    .replace('Preview only. The shared account is checked again when you place the order.',
      'This is an order preview. Your balance and risk limits are checked again when you place it.')
    .replace('Selected official releases, not a complete news service. Missing coverage never means an all-clear.',
      'These are selected official announcements, not all market news. Missing updates do not mean there are no risks.')
    .replace(/ACCOUNT_CHANGED: ?/g,'Your account settings changed. ')
    .replace(/ACCOUNT_BUSY: ?/g,'Your account is busy. ')
    .replace(/RISK_LIMIT: ?/g,'Your risk limit was exceeded. ')
    .replace(/DRAINING: ?/g,'New orders are paused while you prepare a new account. ')
    .replace(/UNPRICED_EXPOSURE: ?/g,'An existing order has missing risk information. ')
    .replace(/CUTOVER_WAITING: ?/g,'Existing orders or trades still need to finish. ')
    .replace(/REQUEST_CONFLICT: ?/g,'This order was already submitted with different details. ')
    .replace(/PREVIEW_EXPIRED/g,'This order preview has expired. Review it again before placing the order.')
    .replace(/ATTEMPT_EXPIRED/g,'This setup has expired. Review a current setup.')
    .replace(/NO_FRESH_MARK: ?/g,'A recent price is not available. ')
    .replace(/ENTRY_PAUSED: ?/g,'New orders are paused. ');
}

const badge = (value, style='neutral') => `<span class="badge ${style}">${esc(label(value))}</span>`;

const empty = (title, detail) => `<div class="empty"><img src="/static/assets/ui/radar.svg" alt=""><h3>${esc(title)}</h3><p>${esc(detail)}</p></div>`;

const heading = (title, detail, actions='') => `<div class="page-heading"><div><div class="eyebrow">${workspace === 'CRYPTO' ? 'CRYPTO' : 'US STOCKS'} / PAPER WORKSPACE</div><h1>${title}</h1><p class="subheading">${detail}</p></div><div class="actions">${actions}</div></div>`;

let workspace = localStorage.getItem('ss-workspace-v1') === 'STOCKS' ? 'STOCKS' : 'CRYPTO';

let context = null, page = 'home', selectedSetup = null, chart = null, resize = null, noticeTimer;

$('#workspace').value = workspace;

function url(path, query={}) { return `/api/ui/v1/${path}?${new URLSearchParams({workspace,...query})}`; }

function read(resource,path,query={}) { const epoch=(context&&workspace==='CRYPTO'&&resource!=='context')?{epoch_id:context.epoch_id}:{};return selection.read(resource,url(path,{...epoch,...query})); }
function notify(message) { $('#notice').textContent=plain(message); clearTimeout(noticeTimer); noticeTimer=setTimeout(()=>{$('#notice').textContent='';},8000); }

function errorAt(node,error) { if(node) node.innerHTML=`<div class="error" role="alert">${esc(plain(error.message))}</div>`; }

async function post(path,payload,resource='action') {

  return selection.read(resource,path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});

}

async function confirmAction(title,detail,label) {

  const dialog=$('#confirm-dialog'); $('#confirm-title').textContent=title; $('#confirm-detail').textContent=detail; $('#confirm-go').textContent=label;

  dialog.returnValue='cancel'; dialog.showModal();

  return new Promise(resolve=>dialog.addEventListener('close',()=>resolve(dialog.returnValue==='confirm'),{once:true}));

}

function pnlTone(value){
  if(value==null||value==='—')return 'pending';
  const raw=String(value).replace(/[$,\s]/g,'');
  if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw))return 'pending';
  if(!/[1-9]/.test(raw.split(/[eE]/)[0]))return 'flat';
  return raw.startsWith('-')?'loss':'gain';
}
function pnl(value,unit='USD'){
  const tone=pnlTone(value), word={gain:'Gain',loss:'Loss',flat:'Break-even',pending:'Not available'}[tone];
  const display=tone==='pending'?'—':unit==='USD'?money(value):`${esc(value)} R`;
  return `<span class="pnl-value pnl-${tone}"><span aria-hidden="true">${tone==='gain'?'↗':tone==='loss'?'↘':tone==='flat'?'＝':'·'}</span> ${display}<small>${word}</small></span>`;
}
function resultMeter(value){
  // Geometry only: authoritative result text is never recomputed from prices.
  const numeric=Number(value), width=value!=null&&Number.isFinite(numeric)?Math.min(Math.abs(numeric),3)/3*50:0;
  const tone=pnlTone(value);
  return `<div class="result-meter" aria-hidden="true"><i class="zero-mark"></i><span class="pnl-fill pnl-${tone}" style="width:${width}%;${tone==='loss'?'right':'left'}:50%"></span></div>`;
}
function resultChart(rows){
  const settled=rows.filter(row=>row.r_multiple!=null).slice(0,12);
  if(!settled.length)return '';
  return `<section class="card section-gap outcome-chart"><div class="card-head"><div><h2>Recent trade results</h2><p class="ticket-note">Each bar is one recorded trade. Losses extend left; gains extend right.</p></div></div><div class="result-axis"><span>Loss</span><span>0</span><span>Gain</span></div>${settled.map(row=>`<button class="result-chart-row" data-diagnosis="${esc(row.intent_id)}" aria-label="View ${esc(row.symbol)} result, ${esc(row.r_multiple)} R"><span>${esc(row.symbol)}<small>${esc(date(row.closed_at))}</small></span><span>${resultMeter(row.r_multiple)}</span><strong class="pnl-${pnlTone(row.r_multiple)}">${esc(row.r_multiple)} R</strong></button>`).join('')}<p class="source-detail">Shown in list order, up to 12 trades. Bar lengths stop at 3R; the written result is uncapped. This is not an account balance chart.</p></section>`;
}

function facts(entries) { return `<dl class="facts">${entries.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd class="${/profit|loss|realised/i.test(label)?'pnl-'+pnlTone(value):''}">${esc(value)}</dd></div>`).join('')}</dl>`; }

function disposeChart(){if(resize)resize.disconnect();resize=null;if(chart)chart.remove();chart=null;}

function goto(next){if(location.hash===`#${next}`)void render();else location.hash=next;}

function stockGate(){const c=context.capabilities;return `<div class="card"><div class="card-head"><h2>Stock trading is not enabled yet</h2>${badge(c.state,'warning')}</div><p>Stock prices and practice examples are kept separate from your crypto account.</p><ul>${c.blockers.map(x=>`<li>${esc(plain(x))}</li>`).join('')}</ul><div class="actions"><a href="#settings" class="text-link">Set up providers →</a><a href="#research" class="text-link">Try practice examples →</a></div></div>`;}

function accountBanner(){const estimates=context.account.estimated_settlement_ids||[];const note=estimates.length?`<div class="banner">Your balance includes estimates for ${estimates.length} older trades. New trades are calculated using recorded prices and costs.</div>`:'';return note+(context.state==='DRAINING'?`<div class="banner">Preparing a new paper account. New orders are paused; existing trades keep their stop-loss and target. ${esc(context.cutover_blockers.length)} order(s) or position(s) still need to finish. <a href="#settings" class="text-link">View account settings →</a></div>`:'');}

function metrics(){const a=context.account;return `<div class="metrics">${[

  ['Account value',money(a.marked_equity),a.marks_complete?'Cash plus profit or loss on open trades':'Some current prices are missing','accent-card'],

  ['Balance after closed trades',money(a.settled_balance),'Includes recorded trading costs',''],

  ['Open profit / loss',money(a.unrealised_pnl_usd),'Before the cost of closing these trades','pnl-'+pnlTone(a.unrealised_pnl_usd)],

  ['Risk in current orders',money(a.committed_risk_usd),`${a.concurrent} open trade(s) · ${a.reserved_slots} pending order(s) · limit ${context.slot_ceiling}`,'']

].map(([label,value,detail,cls])=>`<div class="card ${cls}"><div class="metric-label">${label}</div><div class="metric-value">${esc(value)}</div><div class="metric-detail">${esc(detail)}</div></div>`).join('')}</div>`;}

function setupTimes(row){return `<p class="source-detail">Setup recorded ${esc(date(row.setup.confirmed_at||null))} · ${row.confirmation_deadline&&!setupPrice(row.setup.entry)?'Confirmation deadline':'Entry deadline'} ${esc(date((row.confirmation_deadline&&!setupPrice(row.setup.entry)?row.confirmation_deadline:row.setup.expires_at)||null))}</p>`;}
function setupLevels(row){const s=row.setup;return `<div class="level-cards">${[['Entry',s.entry,'entry'],['Stop-loss',s.stop,'stop'],['Target',s.targets?.[0],'target']].map(([name,value,kind])=>`<div class="level-${kind}"><span>${name}</span><strong>${esc(setupPrice(value)||'Not set')}</strong></div>`).join('')}</div>`;}
function opportunitiesTable(rows){if(!rows.length)return empty('No matching setups','Ready trades appear once their prices and trading checks are confirmed. Use Watching to see setups still developing.');return `<div class="setup-list">${rows.map((r,i)=>`<article class="setup-row" data-state="${esc(r.state)}"><div class="card-head"><div><h3>${esc(r.setup.symbol)} · ${esc(label(r.setup.direction))}</h3><p class="source-detail">${esc(r.setup.timeframe)} · ${esc(label(r.setup.strategy))}</p></div>${badge(r.state)}</div>${setupLevels(r)}${setupTimes(r)}<button class="small" data-setup="${i}">${r.state==='READY'?'Review trade':'View chart'}</button></article>`).join('')}</div>`;}


function bindSetups(rows){document.querySelectorAll('[data-setup]').forEach(button=>button.onclick=()=>{selectedSetup=rows[Number(button.dataset.setup)];goto('trade');});}

// Preserve exact price text; zero is the older opportunity model's missing-value sentinel.
function setupPrice(value){
  const text=String(value??'');
  return /^\+?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text)&&/[1-9]/.test(text.split(/[eE]/)[0])?text:'';
}

function tradeTable(rows,details=true){if(!rows.length)return empty('No account orders yet','Orders placed by you and the bot will appear here.');return `<div class="trade-list">${rows.map(r=>`<article class="trade-row"><div>${details?`<button class="trade-select" data-diagnosis="${esc(r.intent_id)}" aria-label="View ${esc(r.symbol)} trade details">${esc(r.symbol)} <span aria-hidden="true">→</span></button>`:`<strong>${esc(r.symbol)}</strong>`}<p class="source-detail">${esc(label(r.direction))} · ${esc(r.timeframe)}</p></div><div>${badge(r.outcome||r.state)}<p class="source-detail">Placed by ${esc(label(r.origin))} · managed by ${esc(label(r.controller))}</p></div><div class="trade-result">${pnl(r.realised_usd)}<div class="pnl-${pnlTone(r.r_multiple)}">${esc(r.r_multiple??'—')} R</div>${resultMeter(r.r_multiple)}<p class="source-detail">After recorded costs</p></div></article>`).join('')}<p class="ticket-note">1R is the amount risked on a trade. Select a market name to view its trade details.</p></div>`;}


async function drawTradeHistory(dialog,trade){
  const host=dialog.querySelector('.trade-history-chart'),note=dialog.querySelector('.trade-history-note');
  const seconds={ '1m':60,'5m':300,'15m':900,'30m':1800,'1H':3600,'4H':14400,'1D':86400 }[trade.timeframe];
  const start=Number(trade.filled_at),end=Number(trade.closed_at)||Math.floor(Date.now()/1000);
  if(!seconds||!start){note.textContent='No entry time was recorded, so a trade journey cannot be plotted. Unfilled orders have no trade to replay.';return;}
  let historyChart,observer;
  const controller=new AbortController();
  const cleanup=()=>{controller.abort();observer?.disconnect();historyChart?.remove();historyChart=null;};
  dialog.addEventListener('close',cleanup,{once:true});
  const removal=new MutationObserver(()=>{if(!dialog.isConnected){cleanup();removal.disconnect();}});
  removal.observe(dialog.parentNode,{childList:true});
  try{
    const query=new URLSearchParams({symbol:trade.symbol,tf:trade.timeframe,end_ts:Math.min(end+seconds*12,Math.floor(Date.now()/1000)),limit:5000});
    const response=await fetch('/api/candles?'+query,{signal:controller.signal});
    if(!response.ok)throw new Error('Historical candles could not be loaded.');
    const raw=await response.json();if(!dialog.isConnected)return;
    const candles=raw.filter(c=>c.time>=start-seconds*12&&c.time+seconds<=Date.now()/1000);
    if(!candles.length){note.textContent='The candles from this trade are not available. Its recorded prices and result are still shown below.';return;}
    host.style.height=window.innerWidth<600?'440px':'520px';
    historyChart=window.LightweightCharts.createChart(host,{width:host.clientWidth,height:host.clientHeight,localization:{timeFormatter:ts=>date(ts)},layout:{background:{color:'#141c25'},textColor:'#a1b1c0'},grid:{vertLines:{color:'#202d38'},horzLines:{color:'#202d38'}},timeScale:{timeVisible:true,tickMarkFormatter:ts=>new Date(ts*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})},handleScroll:true,handleScale:true});
    const series=historyChart.addCandlestickSeries({upColor:'#78e2b6',downColor:'#ed929c',borderVisible:false,wickUpColor:'#78e2b6',wickDownColor:'#ed929c',lastValueVisible:false,priceLineVisible:false});
    series.setData(candles);
    // Numeric conversion is for canvas coordinates only. Recorded price text stays authoritative.
    [[trade.entry,'Filled entry','#a4baff'],[trade.planned_stop,'Original stop','#ff999e'],[trade.targets?.[0],'Planned target','#78e2b6'],[trade.exit_price,'Exit','#f0c37e']].forEach(([price,title,color])=>{if(setupPrice(price))series.createPriceLine({price:Number(price),title,color,lineWidth:1,lineStyle:2,axisLabelVisible:true});});
    const events=[];
    for(const [ts,price,title,color] of [[start,trade.entry,'Entry','#a4baff'],[Number(trade.closed_at),trade.exit_price,'Exit','#f0c37e']]){
      const candle=candles.find(c=>c.time<=ts&&ts<c.time+seconds);
      if(ts&&candle&&setupPrice(price)){
        const point=historyChart.addLineSeries({color,pointMarkersVisible:true,pointMarkersRadius:7,lastValueVisible:false,priceLineVisible:false,crosshairMarkerVisible:true});
        point.setData([{time:candle.time,value:Number(price)}]);
        point.setMarkers([{time:candle.time,position:title==='Entry'?'belowBar':'aboveBar',color,shape:'circle',size:0,text:title}]);
        events.push({time:candle.time,title});
      }
    }
    const shade=document.createElement('div');shade.className='trade-held-area';shade.setAttribute('aria-hidden','true');host.append(shade);
    const updateShade=()=>{
      const first=events.find(e=>e.title==='Entry'),last=events.find(e=>e.title==='Exit');
      const x1=first&&historyChart.timeScale().timeToCoordinate(first.time),x2=last&&historyChart.timeScale().timeToCoordinate(last.time);
      shade.style.display=x1!=null&&x2!=null?'block':'none';
      if(x1!=null&&x2!=null){shade.style.left=Math.max(0,x1)+'px';shade.style.width=Math.max(2,Math.min(host.clientWidth-70,x2)-Math.max(0,x1))+'px';}
    };
    historyChart.timeScale().subscribeVisibleTimeRangeChange(updateShade);
    historyChart.timeScale().setVisibleRange({from:Math.max(candles[0].time,start-seconds*4),to:Math.min(candles[candles.length-1].time,end+seconds*3)});
    updateShade();
    observer=new ResizeObserver(()=>{historyChart?.applyOptions({width:host.clientWidth});if(historyChart)updateShade();});observer.observe(host);
    note.insertAdjacentHTML('beforebegin',`<div class="journey-key"><span>● Entry ${esc(trade.entry)}</span><span>Shaded = trade open</span><span>● Exit ${esc(trade.exit_price||'Still open')}</span></div><p class="journey-outcome">${esc(label(trade.direction))} · ${esc(label(trade.outcome||trade.state))} · ${pnl(trade.realised_usd)}</p>`);
    note.textContent=`${trade.symbol} · ${trade.timeframe} candles. Entry ${date(start)}${trade.closed_at?' · Exit '+date(trade.closed_at):' · Still open'}. Dots mark recorded fill prices on their containing candles. All times use your local clock. Candles do not show the order of moves within each bar. Original stop and target are reference levels, not a history of later adjustments.${candles[0].time>start?' Earlier candles are missing; the entry is outside this chart.':''}`;
  }catch(error){if(error.name!=='AbortError')note.textContent='Historical chart unavailable. Your recorded trade details remain below.';}
}

function bindDiagnoses(){document.querySelectorAll('[data-diagnosis]').forEach(button=>button.onclick=async()=>{
  try{
    const data=await read('diagnosis',`trades/${encodeURIComponent(button.dataset.diagnosis)}/diagnosis`);if(!data)return;
    document.querySelector('.trade-dialog')?.remove();
    const trade=data.trade, dialog=document.createElement('dialog');dialog.className='trade-dialog';dialog.setAttribute('aria-labelledby','trade-dialog-title');
    dialog.innerHTML=`<form method="dialog" class="dialog-close"><button autofocus>Close details</button></form><div class="eyebrow">RECORDED PAPER TRADE</div><h2 id="trade-dialog-title">${esc(trade.symbol)} · Trade details</h2><section class="trade-history"><h3>How the trade played out</h3><div class="trade-history-chart" role="img" aria-label="Historical candlestick chart"></div><p class="trade-history-note ticket-note">Loading the candles around this trade…</p></section><div class="trade-result-hero">${pnl(trade.realised_usd)}<div>${pnl(trade.r_multiple,'R')}</div>${resultMeter(trade.r_multiple)}<p>After recorded trading costs · ${esc(label(trade.outcome||trade.state))}</p></div><div class="trade-path"><div><span>Entry</span><strong>${esc(trade.entry??trade.planned_entry)}</strong></div><span aria-hidden="true">→</span><div><span>Exit</span><strong>${esc(trade.exit_price??'No exit recorded')}</strong></div></div><p class="ticket-note">${esc(label(trade.direction))} · ${esc(trade.timeframe)} · Placed by ${esc(label(trade.origin))} · managed by ${esc(label(trade.controller))}</p>${facts([['Amount risked',money(trade.risk_usd)],['Closed',date(trade.closed_at)],['Fees',money(trade.fees_usd)],['Funding',money(trade.funding_usd)],['Slippage',money(trade.slippage_usd)],['Calculation',label(trade.pnl_basis)]])}<p class="ticket-note">Slippage is reflected in the recorded prices; do not subtract it again. 1R equals the amount risked.</p><p class="ticket-note">${trade.grade_eligible?'Counts toward the bot’s unassisted results.':'Excluded from unassisted bot results because it was placed or managed manually.'}</p><details class="source-detail"><summary>Technical details</summary><p class="code">Setup attempt ID: ${esc(trade.attempt_id)}<br>Order ID: ${esc(trade.intent_id)}</p></details>`;
    $('#content').append(dialog);button.focus();dialog.showModal();void drawTradeHistory(dialog,trade);dialog.addEventListener('close',()=>{dialog.remove();if(button.isConnected)button.focus();},{once:true});
  }catch(error){notify(error.message);}
});}


// Patch existing nodes during polling so focus, scroll and loaded feeds survive.
function updateContent(node, html, preservePulse=false) {
  const template=document.createElement('template');template.innerHTML=html;
  function patch(parent, next) {
    const old=[...parent.childNodes], fresh=[...next.childNodes];
    fresh.forEach((child,index)=>{
      const current=old[index];
      if(!current){parent.append(child.cloneNode(true));return;}
      if(current.nodeType!==child.nodeType||current.nodeName!==child.nodeName){current.replaceWith(child.cloneNode(true));return;}
      if(current.nodeType===3){if(current.nodeValue!==child.nodeValue)current.nodeValue=child.nodeValue;return;}
      if(current.nodeType!==1)return;
      if(preservePulse&&current.id==='pulse'&&child.id==='pulse')return;
      for(const attr of [...current.attributes])if(!child.hasAttribute(attr.name))current.removeAttribute(attr.name);
      for(const attr of [...child.attributes])if(current.getAttribute(attr.name)!==attr.value)current.setAttribute(attr.name,attr.value);
      patch(current,child);
    });
    old.slice(fresh.length).forEach(child=>child.remove());
  }
  patch(node,template.content);
}
let refreshingHome=false;
async function refreshHome(){
  if(refreshingHome||page!=='home'||document.hidden||document.querySelector('dialog[open]'))return;
  refreshingHome=true;
  try{await home(true);}catch(e){notify(`Refresh unavailable: ${e.message}. Showing the last loaded account.`);}
  finally{refreshingHome=false;}
}

async function home(background=false){const data=await read('home','home');if(!data)return;context=data.context;if(workspace==='STOCKS'){$('#content').innerHTML=heading('Your stock workspace','A separate account. A clear path to readiness.')+stockGate();return;}

  const html=heading('A clear view of your account.','One balance. Every trade accounted for.',`<button id="pause">${context.automation.halted?'Resume entries':'Pause entries'}</button><button class="primary" id="open-trade">New paper trade</button>`)+accountBanner()+metrics()+`<div class="grid two"><div class="stack"><section class="card"><div class="card-head"><h2>Opportunities</h2><a href="#opportunities" class="text-link">View all →</a></div>${opportunitiesTable(data.opportunities)}<p class="source-detail section-gap">Closest to being ready first, then closest to the entry price.</p></section><section class="card"><div class="card-head"><h2>Open trades & pending orders</h2>${badge(context.automation.halted?'ENTRIES PAUSED':context.automation.mode)}</div>${tradeTable(data.positions)}</section></div><div class="stack"><section class="card"><div class="card-head"><h2>Account limits</h2>${badge(context.state)}</div>${facts([['Risk per trade',context.risk_percent_label],['Maximum open trades',context.slot_ceiling],['Cash',money(context.account.cash)],['Closed profit / loss today (UTC)',money(context.today_realised_usd)],['Oldest price update',date(context.account.oldest_mark_at)]])}<p class="ticket-note">You and the bot share one open-trade limit. Pausing new orders leaves existing stop-losses and targets in place.</p></section><section class="card" id="pulse"><h2>Market Pulse</h2><p class="loading">Checking news updates…</p></section></div></div><section class="card section-gap"><div class="card-head"><h2>Recent closes</h2><a href="#journal" class="text-link">Open journal →</a></div>${tradeTable(data.recent)}</section>`;

  if(background)updateContent($('#content'),html,true);else $('#content').innerHTML=html;
  bindSetups(data.opportunities);bindDiagnoses();$('#open-trade').onclick=()=>{selectedSetup=null;goto('trade');};$('#pause').onclick=async()=>{try{const result=await post('/api/settings',{changes:{halted:!context.automation.halted},note:'Cockpit account entry control'});if(result){notify('Account entry control updated.');await render();}}catch(e){notify(e.message);}};void loadPulse();

}

async function loadPulse(){try{const data=await read('pulse','market-pulse');const node=$('#pulse');if(!data||!node)return;updateContent(node,`<div class="card-head"><h2>Market Pulse</h2>${badge('CONTEXT ONLY')}</div>${data.sources.map(s=>`<div class="source-detail">${esc(s.source)} · ${esc(label(s.status))} · checked ${esc(date(s.observed_at))}</div>`).join('')}${data.items.slice(0,4).map(i=>`<article class="feed-item"><div class="feed-meta">${esc(i.source)} · ${esc(date(i.published_at))}${i.historical?' · Older news':i.status==='DELAYED'?' · Update delayed':''}</div><a href="${esc(i.url)}" target="_blank" rel="noopener noreferrer">${esc(i.title)} ↗</a></article>`).join('')||'<p class="ticket-note">Headlines unavailable. Check the original sources.</p>'}<hr><h3>Upcoming scheduled events</h3><p class="source-detail">Calendar coverage: ${esc(label(data.calendar.status))}</p>${data.calendar.events.slice(0,3).map(e=>`<div class="feed-item"><h3>${esc(e.title)}</h3><div class="source-detail">${esc(e.date_label||date(e.start_at))} · ${esc(label(e.source_status))}</div></div>`).join('')||'<p class="ticket-note">No upcoming events are listed by these sources. Other events may still affect the market.</p>'}<p class="ticket-note">${esc(plain(data.note))}</p>`);}catch(e){errorAt($('#pulse'),e);}}

async function opportunitiesPage(){if(workspace==='STOCKS'){$('#content').innerHTML=heading('Opportunities','Ready trades have prices and pass the recorded checks. Watching setups are not ready for an order.')+stockGate();return;}

  $('#content').innerHTML=heading('Opportunities','Ready setups have recorded prices and passed the recorded checks. Use Watching for setups still developing. Risk is checked again when placing an order.')+`<form id="filters" class="filters"><label>Show setups<select name="group"><option value="ready">Ready to trade</option><option value="watching">Watching</option></select></label><label>Market<input name="search" placeholder="Search BTC, ETH…"></label><label>Readiness<select name="state"><option value="">All states</option>${['READY','FORMING','WATCHING','BLOCKED','REJECTED'].map(s=>`<option value="${s}">${esc(label(s))}</option>`).join('')}</select></label><label>Show<select name="limit"><option>10</option><option>25</option><option>50</option></select></label><button type="submit">Apply</button></form><section class="card"><div id="opportunity-list" class="loading">Reading opportunities…</div></section>`;

  const load=async()=>{try{const query=Object.fromEntries(new FormData($('#filters')));const data=await read('opportunities','opportunities',query);if(!data)return;const items=data.items.filter(row=>query.group==='ready'?row.state==='READY'&&row.eligible!==false&&[row.setup.entry,row.setup.stop,row.setup.targets?.[0]].every(value=>setupPrice(value))&&Number(row.setup.expires_at)>Date.now()/1000:['FORMING','WATCHING','BLOCKED'].includes(row.state));$('#opportunity-list').className='';$('#opportunity-list').innerHTML=(items.length?opportunitiesTable(items):empty(query.group==='ready'?'No confirmed trades ready right now':'No setups to watch right now',query.group==='ready'?'Nothing returned has a complete, current trade plan. Choose Watching to inspect developing setups.':'Developing setups will appear after a scan.'))+`<p class="source-detail section-gap">${items.length} shown · Sorted by readiness, then distance to entry</p>`;bindSetups(items);}catch(e){errorAt($('#opportunity-list'),e);}};

  $('#filters').onsubmit=e=>{e.preventDefault();void load();};$('#filters select[name=group]').onchange=()=>void load();await load();

}

async function journalPage(archive=false){if(workspace==='STOCKS'){$('#content').innerHTML=heading('Journal','See the orders and trades in this account.')+stockGate();return;}

  const data=await read('journal','journal',{archive});if(!data)return;$('#content').innerHTML=heading('Every trade has a record.','Manual and bot together. Research stays in Research.')+`<details class="account-history" ${archive?'open':''}><summary>Older account history</summary><p class="ticket-note">Use this only if you want to review an account you previously finished.</p><div class="tabs"><button id="current-book" aria-pressed="${!archive}">Current account</button><button id="archive-book" aria-pressed="${archive}">View older accounts</button></div></details><div class="banner info">${esc(plain(data.note))}</div><section class="card"><div class="card-head"><h2>${archive?'Previous account history':'Account orders & trades'}</h2>${badge(data.scope)}</div>${tradeTable(data.items)}</section>${resultChart(data.items)}<section id="diagnosis" class="card section-gap"><p class="ticket-note">Tap a market name above to see the entry, exit, costs, and who managed the trade.</p></section>`;$('#current-book').onclick=()=>void journalPage(false);$('#archive-book').onclick=()=>void journalPage(true);bindDiagnoses();}

async function drawChart(symbol,tf){disposeChart();try{const data=await read('candles','candles',{symbol,tf});if(!data||!$('#chart'))return;$('#chart-title').textContent=`${symbol} / ${tf}`;$('#chart-caption').textContent=`Latest completed candle ${data.mark??'unavailable'} · ${date(data.observed_at)}`;if(!data.candles.length){$('#chart').className='chart-empty';$('#chart').textContent='No completed candles are available for this market yet. Try another market or wait for the next scan.';return;}$('#chart').className='chart';$('#chart').textContent='';

    if(!window.LightweightCharts)throw new Error('The chart could not load. You can still see prices in the order form.');

    chart=window.LightweightCharts.createChart($('#chart'),{width:$('#chart').clientWidth,height:$('#chart').clientHeight,layout:{background:{color:'#141c25'},textColor:'#a1b1c0'},grid:{vertLines:{color:'#202d38'},horzLines:{color:'#202d38'}},rightPriceScale:{borderColor:'#334352'},timeScale:{borderColor:'#334352',timeVisible:true},handleScroll:true,handleScale:true});

    const series=chart.addCandlestickSeries({upColor:'#78e2b6',downColor:'#ed929c',borderVisible:false,wickUpColor:'#78e2b6',wickDownColor:'#ed929c'});

    // Float conversion is confined to the chart vendor's canvas coordinates.

    series.setData(data.candles.map(c=>({time:c.time,open:Number(c.open),high:Number(c.high),low:Number(c.low),close:Number(c.close)})));

    if(selectedSetup&&selectedSetup.setup.symbol===symbol){const s=selectedSetup.setup;[[s.entry,'Entry','#a4baff'],[s.stop,'Stop','#ff999e'],[s.targets?.[0],'Target','#78e2b6']].forEach(([price,title,color])=>{if(setupPrice(price)&&Number.isFinite(Number(price))&&Number(price)>0)series.createPriceLine({price:Number(price),color,lineWidth:1,lineStyle:2,axisLabelVisible:true,title});});}

    if(selectedSetup){
      const chartForGuide=chart;
      let guide;try{guide=await read('setup-guide','setup-guide',{setup_id:selectedSetup.setup.setup_id});}catch(error){notify(`Chart levels unavailable: ${plain(error.message)}`);}
      if(!chart||chart!==chartForGuide||!$('#chart'))return;
      if(guide){
      const node=$('#setup-evidence');
      if(node)node.insertAdjacentHTML('beforeend',`<h3>Levels being watched</h3>${facts([['Area lower edge',guide.zone_bottom||'Not recorded'],['Area upper edge',guide.zone_top||'Not recorded'],['Confirmation deadline',date(guide.confirmation_deadline)],['Entry deadline',date(guide.entry_deadline)]])}<p>${esc(guide.confirmation)}</p><h3>When the bot skips it</h3><p>${esc(guide.cancel_reason?label(guide.cancel_reason):guide.skip_if)}</p><p class="source-detail">Area edges are shown on the chart. They are not entry or stop-loss orders.</p>`);
      [[guide.zone_bottom,'Area lower edge'],[guide.zone_top,'Area upper edge']].forEach(([price,title])=>{if(setupPrice(price)&&Number.isFinite(Number(price)))series.createPriceLine({price:Number(price),color:'#f0c37e',lineWidth:2,lineStyle:2,axisLabelVisible:true,title});});
      }
    }
    chart.timeScale().fitContent();resize=new ResizeObserver(()=>{if(chart&&$('#chart'))chart.applyOptions({width:$('#chart').clientWidth,height:$('#chart').clientHeight});});resize.observe($('#chart'));

  }catch(e){errorAt($('#chart'),e);}}

function savedRequest(){try{return JSON.parse(localStorage.getItem('ss-pending-ticket-v1'));}catch{return null;}}

async function submitTicket(request){const node=$('#ticket-result');try{localStorage.setItem('ss-pending-ticket-v1',JSON.stringify(request));node.innerHTML='<p>Sending your order…</p>';const data=await post('/api/ui/v1/ticket/arm',request,'arm');if(!data)return;localStorage.removeItem('ss-pending-ticket-v1');const receipt=data.receipt;node.innerHTML=`<div class="ticket-review">${request.expected_epoch!==context.epoch_id?'<p>This order belongs to a previous account.</p>':''}<h3>${receipt.already_armed?'Existing order recovered':'Paper order recorded'}</h3><details class="source-detail"><summary>Order reference</summary><p class="receipt">${esc(receipt.intent_id)}</p></details><p class="ticket-note">Your order has been saved. The next scan checks whether a completed candle reached your entry price.</p><a href="#journal" class="text-link">View the account journal →</a></div>`;notify('Paper order saved.');}catch(e){if(e.status===400||e.status===409){localStorage.removeItem('ss-pending-ticket-v1');node.innerHTML=`<div class="error">${esc(plain(e.message))}</div><p class="ticket-note">No new order was accepted. Update the ticket and review again.</p>`;return;}node.innerHTML=`<div class="error">${esc(plain(e.message))}</div><p class="ticket-note">We could not confirm whether your order was saved. Retry below to check or send the same order safely. Do not place a separate order.</p><button id="retry-saved">Retry this order</button>`;$('#retry-saved').onclick=()=>void submitTicket(request);}}

async function tradePage(){if(workspace==='STOCKS'){$('#content').innerHTML=heading('Trade','Trading options depend on the market you select.')+stockGate();return;}

  const s=selectedSetup?.setup;$('#content').innerHTML=heading('Plan the trade. See the risk.','Orders you place use the same paper balance and risk limits as the bot.')+accountBanner()+`<div class="grid two trade-layout"><div class="stack"><section class="card chart-panel"><div class="chart-toolbar"><h2 id="chart-title">${esc(s?.symbol||'BTCUSDT')} / ${esc(s?.timeframe||'1H')}</h2>${badge('CLOSED CANDLES')}</div><div id="chart" class="chart"></div><div id="chart-caption" class="chart-caption">Loading price chart…</div></section>${selectedSetup?`<section class="card" id="setup-evidence"><h2>Setup evidence</h2>${badge(selectedSetup.state)}<p class="section-gap">${esc(setupSentence(selectedSetup.primary_explanation))}</p><h3>Main reason to wait</h3><p>${esc(setupSentence(selectedSetup.strongest_counterargument))}</p><p class="source-detail">${esc(s.invalidation)} · Research rating: ${esc(label(selectedSetup.evidence.grade))}. This rating does not guarantee a profitable trade.</p></section>`:''}<section class="card" id="spotter-panel"><h2>Spotter</h2><p>Ask Spotter to explain a setup or point out its risks. It cannot place trades or change your strategy.</p><form id="spotter-form"><label for="spotter-question">Question about this market</label><textarea id="spotter-question" required rows="2" placeholder="What would invalidate this setup?"></textarea><button class="section-gap" type="submit">Ask Spotter</button></form><div id="spotter-answer" class="spotter-response section-gap"></div></section></div><div class="stack"><section class="card ticket"><div class="card-head"><h2>Order ticket</h2>${badge('MANUAL · PAPER')}</div>${s&&[s.entry,s.stop,s.targets?.[0]].some(value=>!setupPrice(value))?'<div class="banner info" id="setup-prices-pending">This setup does not have a complete entry, stop-loss and target yet. You can view its chart while it develops. To place a manual order, enter your own prices and review the risk.</div>':''}<form id="ticket"><div class="form-grid"><div class="field"><label for="symbol">Market</label><input id="symbol" name="symbol" required value="${esc(s?.symbol||'BTCUSDT')}" autocomplete="off"></div><div class="field"><label for="tf">Timeframe</label><select id="tf" name="tf">${['5m','15m','1H','4H','1D'].map(tf=>`<option ${tf===(s?.timeframe||'1H')?'selected':''}>${tf}</option>`).join('')}</select></div><div class="field wide"><label for="direction">Direction</label><select id="direction" name="direction"><option ${s?.direction!=='SHORT'?'selected':''}>LONG</option><option ${s?.direction==='SHORT'?'selected':''}>SHORT</option></select></div>${[['entry','Limit entry',s?.entry],['sl','Protective stop',s?.stop],['tp','Target',s?.targets?.[0]]].map(([name,label,value])=>`<div class="field ${name==='tp'?'wide':''}"><label for="${name}">${label}</label><input id="${name}" name="${name}" inputmode="decimal" required value="${esc(setupPrice(value))}" placeholder="${s&&!setupPrice(value)?'Not available yet':'Price'}"></div>`).join('')}<div class="field wide"><label for="risk_usd">Risk in USD · optional lower amount</label><input id="risk_usd" name="risk_usd" inputmode="decimal" placeholder="Use account limit (${esc(context.risk_percent_label)})"></div></div><button type="submit" class="primary">Review paper order</button></form><p class="ticket-note">Order size is calculated using your account balance and risk limit. You can hold one trade at a time and cannot add to an open trade.</p><div id="ticket-result"></div></section><section id="trade-active" class="card"><h2>Open trades & orders</h2><p>Loading pending orders…</p></section></div></div>`;

  void drawChart($('#symbol').value,$('#tf').value);const reloadChart=()=>{selectedSetup=null;selection.invalidate('preview');$('#setup-evidence')?.remove();$('#setup-prices-pending')?.remove();for(const name of ['entry','sl','tp']){const field=$('#'+name);field.value='';field.placeholder='Price';}$('#ticket-result').innerHTML='';void drawChart($('#symbol').value.trim(),$('#tf').value);};$('#symbol').onchange=reloadChart;$('#tf').onchange=reloadChart;

  $('#ticket').addEventListener('input',()=>{selection.invalidate('preview');$('#ticket-result').innerHTML='';});

  $('#ticket').onsubmit=async e=>{e.preventDefault();try{const pending=savedRequest();if(pending){$('#ticket-result').innerHTML='<div class="banner">Your previous order has not been confirmed. Retry it below before placing another.</div><button id="retry-saved">Retry this order</button>';$('#retry-saved').onclick=()=>void submitTicket(pending);return;}const data=await post('/api/ui/v1/ticket/preview',{workspace,...Object.fromEntries(new FormData($('#ticket')))},'preview');if(!data)return;$('#ticket-result').innerHTML=`<div class="ticket-review"><h3>Review before placing</h3>${facts([['Market',data.request.symbol+' '+data.request.direction],['Entry',data.request.entry],['Stop',data.request.sl],['Target',data.request.tp],['Risk',money(data.risk_usd)],['Quantity',data.quantity],['Potential reward / amount risked',data.rr+' R'],['Valid until',date(data.expires_at)]])}<p class="ticket-note">${esc(plain(data.note))}</p><button class="primary" id="place-order">Place paper order</button></div>`;$('#place-order').onclick=()=>void submitTicket(data.request);}catch(err){errorAt($('#ticket-result'),err);}};

  const pending=savedRequest();if(pending){$('#ticket-result').innerHTML=`<div class="banner">An order for ${esc(pending.symbol)} still needs confirmation. Retry it below before placing another.</div><button id="retry-saved">Retry this order</button>`;$('#retry-saved').onclick=()=>void submitTicket(pending);}

  $('#spotter-form').onsubmit=async e=>{e.preventDefault();$('#spotter-answer').textContent='Reading the current evidence…';try{const data=await post('/api/copilot',{message:$('#spotter-question').value,symbol:$('#symbol').value,tf:$('#tf').value,setup_id:selectedSetup?.setup.setup_id,context:'chart'},'spotter');if(data)$('#spotter-answer').textContent=data.reply||data.text||data.response||data.answer||'Spotter returned no explanation.';}catch(err){errorAt($('#spotter-answer'),err);}};

  await activeControls();

}

async function activeControls(){try{const data=await read('positions','positions');if(!data||!$('#trade-active'))return;$('#trade-active').innerHTML='<h2>Open trades & orders</h2>'+ (data.items.length?data.items.map(r=>`<div class="provider"><h3>${esc(r.symbol)} ${esc(r.direction)}</h3>${badge(r.state)}<p class="ticket-note">Placed by ${esc(label(r.origin))} · managed by ${esc(label(r.controller))}</p>${facts([['Entry',r.entry||r.planned_entry],['Stop',r.stop],['Risk',money(r.risk_usd)],['Counts toward bot performance',r.grade_eligible?'Yes':'No']])}<div class="actions section-gap">${r.state==='PAPER_FILLED'?`<button class="small danger" data-close="${esc(r.intent_id)}">Close paper position</button>${r.origin==='BOT'?`<button class="small" data-control="${esc(r.intent_id)}" data-owner="${r.controller==='BOT'?'OPERATOR':'BOT'}">${r.controller==='BOT'?'Take control':'Return to bot'}</button>`:''}`:r.origin==='OPERATOR'?`<button class="small" data-cancel="${esc(r.intent_id)}">Cancel resting order</button>`:'<span class="source-detail">The bot order is waiting for its entry price. It will expire if the price is not reached in time.</span>'}</div></div>`).join(''):empty('No open trades or pending orders','Review a new paper order. Your account limits will be checked when you place it.'));

  document.querySelectorAll('[data-close],[data-control],[data-cancel]').forEach(button=>button.onclick=async()=>{const close=button.dataset.close,control=button.dataset.control;const iid=close||control||button.dataset.cancel;const title=close?'Close this paper position?':control?'Change who manages this trade?':'Cancel this resting order?';const detail=close?'The remaining position will close at the latest recorded candle price, with trading costs included.':control?'The original stop-loss and target stay in place. Once you take over, this trade no longer counts toward the bot’s unassisted results, even if you return control later.':'Only orders that have not filled can be cancelled.';if(!await confirmAction(title,detail,close?'Close position':control?'Change manager':'Cancel order'))return;try{const data=await post(close?'/api/account/close':control?'/api/account/control':'/api/manual/cancel',{intent_id:iid,...(control?{controller:button.dataset.owner}:{})});if(data){notify('Account action recorded.');await activeControls();}}catch(e){notify(e.message);}});

  }catch(e){errorAt($('#trade-active'),e);}}

function setupSentence(value){
  const text=String(value||'No explanation is available yet.');
  const match=text.match(/^price reached the (DEMAND|SUPPLY) zone (.+?) in ([A-Z_]+) · waiting for a close that proves it held \((\d+) bars\)$/);
  if(match){const area=match[1]==='DEMAND'?'support area':'resistance area';const trend={BULL_TREND:'an uptrend',BEAR_TREND:'a downtrend',WEAKENING_BULL:'a weakening uptrend',WEAKENING_BEAR:'a weakening downtrend',TRANSITION:'a changing trend'}[match[3]]||'the current market conditions';return `Price reached the ${area} at ${match[2]} during ${trend}. The bot is waiting for a completed candle to confirm that price is holding this area. It allows up to ${match[4]} candles for confirmation.`;}
  return plain(text).replace('The setup has no expiry, so the entry window cannot be verified.','No entry deadline is recorded for this setup. The app cannot confirm whether it is still eligible for a new order.').replace('The setup expiry is unreadable, so the entry window cannot be verified.','The entry deadline could not be read. The app cannot confirm whether a new order is still allowed.').replaceAll('DEMAND','support').replaceAll('SUPPLY','resistance').replaceAll('BULL_TREND','uptrend').replaceAll('BEAR_TREND','downtrend');
}
function setupExplanation(row){return `<h2>${esc(row.setup.symbol)} · ${esc(label(row.setup.strategy))}</h2><h3>What happened</h3><p>${esc(setupSentence(row.primary_explanation))}</p><h3>What to check before trading</h3><p>${esc(row.cancel_reason?label(row.cancel_reason):setupSentence(row.strongest_counterargument))}</p><a href="#strategies" class="text-link">How this strategy works →</a>`;}
function strategyImage(kind){
  const pullback=kind==='pullback';
  const file=pullback?'EUR-USD-bear-trend.jpg':'EUR-USD-outside-bar-in-trend-reversal.jpg';
  const alt=pullback?'EUR/USD candlestick chart: short upward bounces interrupt a larger downward trend.':'EUR/USD candlestick chart: an upward move turns downward near the red arrow.';
  return `<figure class="strategy-figure"><button class="strategy-image-button" data-chart-image="${kind}" aria-label="Enlarge ${kind} chart"><img src="/static/assets/strategies/${kind}.jpg" alt="${alt}" width="${pullback?929:201}" height="${pullback?585:415}" loading="lazy"><span>View larger chart ↗</span></button><figcaption><strong>What to notice</strong><p>${pullback?'Follow the chart from left to right. Price keeps moving lower, but briefly bounces upward along the way. Those temporary bounces are pullbacks within the downtrend.':'Price rises on the left, then turns lower near the red arrow. The candles on the right show the downward move continuing. This is a reversal, rather than a brief pause in the same direction.'}</p><p class="source-detail">Historical EUR/USD example, not a SniperSight trade. The image illustrates the price pattern, not every condition the bot checks. <a href="https://commons.wikimedia.org/wiki/File:${file}" target="_blank" rel="noopener noreferrer">Chart: Ahardy42 / Wikimedia Commons</a> · <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener noreferrer">CC0</a></p></figcaption></figure>`;
}

async function strategiesPage(){
  $('#content').innerHTML=heading('How the bot trades','A guide to its setup types and the checks before an order.')+`<div class="banner info">These descriptions explain the crypto bot’s approach. A setup appearing in Research does not mean the bot is enabled, has placed an order, or has a proven profitable edge.</div><div class="grid equal"><section class="card"><h2>Pullback</h2>${strategyImage('pullback')}<p>The bot looks for price to return to a support area during an uptrend, or a resistance area during a downtrend. It waits for a completed candle to confirm a reaction before considering an entry.</p><p>The idea is to join a move after a temporary retracement. A return to the area alone is not a buy or sell signal.</p></section><section class="card"><h2>Reversal</h2>${strategyImage('reversal')}<p>When the market is changing direction, the bot looks for a possible turn at support or resistance. It checks additional evidence, such as a change in price structure, a sweep beyond recent highs or lows, or stronger trading volume.</p><p>A possible turning point still needs confirmation and must pass the entry and risk checks.</p></section></div><section class="card section-gap"><h2>Before any order</h2><ul><li>The setup must have valid entry, stop-loss and target prices, and an entry deadline that has not passed.</li><li>The wider market context, expected trading costs and account risk checks must allow the trade.</li><li>You and the bot share the same balance and one open-trade limit. Paused entries and trading cooldowns can prevent an order.</li><li>Research results are simulations. Your Journal shows orders actually recorded in your paper account.</li></ul><p>Support is an area where buyers may react; resistance is an area where sellers may react. Neither guarantees a price will hold.</p><a href="#research" class="text-link">Review research setups →</a></section>`;
  const dialog=document.createElement('dialog');dialog.className='strategy-lightbox';dialog.setAttribute('aria-label','Historical chart example');dialog.innerHTML='<form method="dialog"><button autofocus>Close chart</button></form><p>Historical example. On a small screen, scroll across to see the full chart.</p><div class="strategy-zoom"></div>';$('#content').append(dialog);
  document.querySelectorAll('[data-chart-image]').forEach(button=>button.onclick=()=>{const original=button.querySelector('img');const img=original.cloneNode();img.loading='eager';dialog.querySelector('.strategy-zoom').replaceChildren(img);button.focus();dialog.showModal();});

}

function researchCards(rows){if(!rows.length)return empty('No research records yet','Simulations and setup decisions will appear after a scan.');return `<div class="research-list">${rows.map((r,i)=>`<article class="research-row"><div class="card-head"><h3>${esc(r.setup.symbol)} · ${esc(label(r.setup.strategy))}</h3>${badge(r.simulation?.outcome?'Simulation completed':r.state==='CANCELLED'||r.state==='EXPIRED'||r.state==='REJECTED'?'Setup not taken':'Research record')}</div><p class="source-detail">${esc(r.setup.timeframe)} · ${esc(label(r.setup.direction))} · ${esc(label(r.state))}</p>${r.simulation?.outcome?`<p>Simulated result: ${esc(label(r.simulation.outcome))} · ${pnl(r.simulation.r_multiple,'R')}</p>`:`<p>${esc(r.cancel_reason?label(r.cancel_reason):setupSentence(r.strongest_counterargument))}</p>`}${setupLevels(r)}${setupTimes(r)}${r.simulation_updated_at?`<p class="source-detail">Simulation updated ${esc(date(r.simulation_updated_at))}</p>`:''}<button data-setup="${i}" class="small">Inspect</button></article>`).join('')}</div>`;}

async function researchPage(){const data=await read('research','research');if(!data)return;if(workspace==='STOCKS'){const t=data.training;$('#content').innerHTML=heading('Learn the stock workflow.','Practice with made-up prices. These examples do not affect your account.')+`<div class="banner">${esc(plain(t.disclaimer))}</div><section class="card"><h2>Training scenarios</h2><div class="table-wrap"><table><thead><tr><th>Scenario</th><th>Readiness</th><th>Evidence</th></tr></thead><tbody>${t.setups.map(s=>`<tr><td>${esc(s.name)}</td><td>${badge(s.state)}</td><td>${esc(plain((s.rejections||[]).map(x=>x.detail).join(' ')||'This practice setup meets the example rules.'))}</td></tr>`).join('')}</tbody></table></div></section><section class="card section-gap"><h2>Practice trade result</h2>${facts([['Outcome',label(t.simulation?.outcome)],['Result',t.simulation?.r_multiple+' R'],['Data','Practice data · trading fees not included'],['Counts toward bot performance','Never']])}</section>`;return;}

  $('#content').innerHTML=heading('Research is evidence.','See how the strategy would have performed on past prices. These are simulated results.')+`<div class="banner info">${esc(plain(data.note))} Compare results in R when trade sizes differ. 1R is the amount risked on a trade; 2R is twice that amount.</div><section class="card"><div class="card-head"><h2>Simulation results & setup decisions</h2>${badge('RESEARCH')}</div>${researchCards(data.items.slice(0,50))}</section><section class="card section-gap"><h2>How the bot trades</h2><p>Learn about pullbacks, reversals, and the checks a setup must pass before the bot can place an order.</p><a class="text-link" href="#strategies">Explore the strategies →</a></section><section id="research-detail" class="card section-gap" hidden></section>`;document.querySelectorAll('[data-setup]').forEach(button=>{button.textContent='Inspect';button.onclick=()=>{const r=data.items[Number(button.dataset.setup)];const node=$('#research-detail');node.hidden=false;node.innerHTML=setupExplanation(r);node.scrollIntoView({block:'nearest'});};});}

async function settingsPage(){const creds=await selection.read('credentials','/api/credentials');if(!creds)return;const stock=workspace==='STOCKS';const targets=Object.keys(creds.target_fields).filter(t=>stock?['alpaca-paper','massive-stocks'].includes(t):!['alpaca-paper','massive-stocks'].includes(t));

  $('#content').innerHTML=heading('Manage your account.','Choose a market, connect supported providers, and start in paper.')+`<div class="grid equal"><section class="card"><h2>1 / Market & account</h2><p>${stock?'Stock trading and scanning are not available yet. Practice examples are available in Research.':'Paper trading uses public prices. You do not need exchange keys to place simulated orders.'}</p>${stock?stockGate():facts([['Current account','Paper trading'],['Risk per trade',context.risk_percent_label],['Maximum positions',context.slot_ceiling],['Account status',label(context.state)]])}<hr><h2>2 / Provider connections</h2><p class="ticket-note">Saved connection details still need to be checked. Your keys are stored securely on this computer.</p>${targets.map(target=>`<details class="provider"><summary>${esc(target)} · ${Object.values(creds.status[target]||{}).some(Boolean)?'Details saved':'Not connected'}</summary><form data-provider="${esc(target)}">${creds.target_fields[target].map(field=>`<div class="field"><label for="${target}-${field}">${esc(field.replaceAll('_',' '))} ${creds.status[target]?.[field]?'· stored':''}</label><input type="password" id="${target}-${field}" name="${field}" autocomplete="new-password" placeholder="Leave blank to keep existing"></div>`).join('')}<button type="submit" ${!creds.available?'disabled':''}>Save connection details</button></form>${stock?`<button data-verify="${target}">Check data access</button>`:'<p class="source-detail">Paper trading uses public prices and does not need exchange keys. Real-money trading is not enabled.</p>'}<div id="verify-${target}" class="source-detail section-gap"></div></details>`).join('')}</section><div class="stack"><section class="card"><h2>3 / Risk & paper</h2>${stock?'<p>Stock paper trading is not available yet.</p>':`<form id="risk-settings"><label for="account-risk">Risk per trade (%)</label><input id="account-risk" name="risk_percent" type="number" min="0.000001" max="100" step="any" required value="${esc(context.risk_percent_label.replace('%',''))}"><p class="ticket-note">The share of your account balance you can risk on each new trade, whether placed by you or the bot. Existing orders keep their size. New orders pause if daily losses reach four times this percentage. You can hold one trade at a time.</p><button type="submit">Save paper risk</button></form>${facts([['Bot mode',label(context.automation.mode)],['Entry pause',context.automation.halted?'Paused':'Not paused']])}<div class="actions section-gap"><button id="mode-paper" ${context.automation.mode==='PAPER'?'disabled':''}>Enable paper bot</button><button id="mode-off" ${context.automation.mode==='OFF'?'disabled':''}>Turn bot off</button></div><p class="ticket-note">Turning the bot off stops it from placing new orders. Existing stop-losses and targets stay active. Orders you place still follow your account limits.</p><hr><h3>Start a new paper account</h3><p class="ticket-note">Pause new orders and wait for current trades and orders to finish. Then start a new $10,000 paper account with your saved risk setting. Your history is kept, and trades are never closed automatically to make this happen.</p><div class="actions"><button data-cutover="drain" ${context.state==='DRAINING'?'disabled':''}>Pause orders to prepare</button><button data-cutover="resume" ${context.state!=='DRAINING'?'disabled':''}>Keep using this account</button><button data-cutover="complete" class="primary" ${context.state!=='DRAINING'||context.cutover_blockers.length?'disabled':''}>Start new paper account</button></div>${context.cutover_blockers.length?`<p class="source-detail section-gap">${context.cutover_blockers.length} order(s) or position(s) still need to finish. <a href="#trade">View open trades and orders →</a></p>`:''}`}</section><section class="card"><div class="card-head"><h2>Live execution</h2>${badge('LOCKED','warning')}</div><p>Real-money trading is not available. Exchange safety checks still need to be completed.</p><a class="text-link" href="#strategies">Read how the bot trades →</a></section><section class="card"><h2>Display & recovery</h2><p>Learn how the bot identifies setups and decides whether an order is allowed.</p><a href="#strategies" class="text-link">Explore the strategies →</a><p class="ticket-note">Research explains possible trades. Your Journal shows what was actually placed.</p></section></div></div>`;

  document.querySelectorAll('[data-provider]').forEach(form=>form.onsubmit=async e=>{e.preventDefault();try{for(const [field,value] of new FormData(form)){if(value){const result=await post('/api/credentials',{venue:form.dataset.provider,field,value});if(!result)return;}}form.reset();notify('Credential fields saved. Verify access separately.');}catch(err){notify(err.message);}});

  document.querySelectorAll('[data-verify]').forEach(button=>button.onclick=async()=>{const target=button.dataset.verify;try{const result=await post('/api/stocks/connections/test',{target});if(result)$(`#verify-${target}`).textContent=plain(result.detail||(result.ok?'Connection check passed.':'Connection check did not pass.'));}catch(e){errorAt($(`#verify-${target}`),e);}});

  if(stock)return;
  $('#risk-settings').onsubmit=async e=>{e.preventDefault();try{const result=await post('/api/account/risk',{workspace,risk_percent:$('#account-risk').value,expected_epoch:context.epoch_id,expected_risk_pct:context.risk_pct});if(result){notify('Paper risk saved. Existing orders keep their size.');await render();}}catch(err){notify(err.message);}};


  for(const [id,mode] of [['mode-paper','PAPER'],['mode-off','OFF']])$(`#${id}`).onclick=async()=>{try{const result=await post('/api/automation/mode',{mode,expected_revision:context.automation.revision,note:'Cockpit paper setup'});if(result){notify(`Bot mode is ${mode}.`);await render();}}catch(e){notify(e.message);}};

  document.querySelectorAll('[data-cutover]').forEach(button=>button.onclick=async()=>{const action=button.dataset.cutover;if(action==='complete'&&!await confirmAction('Start a new paper account?',`This archives the completed account and starts $10,000 at ${context.risk_percent_label} risk. Old dollar results remain in Previous accounts.`,'Start new paper account'))return;try{const result=await post('/api/account/cutover',{action,expected_epoch:context.epoch_id});if(result){notify('Account updated.');await render();}}catch(e){notify(e.message);}});

}

async function render(){selection.change();$('#more-menu').hidden=true;$('#more').setAttribute('aria-expanded','false');disposeChart();page=location.hash.slice(1).split('?')[0]||'home';if(!['home','opportunities','trade','journal','research','settings','strategies'].includes(page))page='home';document.querySelectorAll('[data-page]').forEach(a=>{if(a.dataset.page===page)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});$('#content').innerHTML='<div class="loading">Loading your account…</div>';try{const data=await read('context','context');if(!data)return;context=data;$('#scope').textContent=workspace==='STOCKS'?'Stocks · setup required':`Current paper account · ${context.risk_percent_label} risk`;await ({home,opportunities:opportunitiesPage,trade:tradePage,journal:journalPage,research:researchPage,settings:settingsPage,strategies:strategiesPage}[page])();}catch(e){errorAt($('#content'),e);}}

$('#workspace').onchange=()=>{workspace=$('#workspace').value;localStorage.setItem('ss-workspace-v1',workspace);selectedSetup=null;context=null;void render();};

window.addEventListener('hashchange',()=>void render());

document.addEventListener('visibilitychange',()=>{if(!document.hidden&&page==='home')void refreshHome();});
// Refresh the live account view without ever rebuilding an in-progress ticket.
setInterval(()=>{void refreshHome();},15000);
$('#more').onclick=()=>{const menu=$('#more-menu');menu.hidden=!menu.hidden;$('#more').setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)menu.querySelector('a').focus();};

document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('#more-menu').hidden){$('#more-menu').hidden=true;$('#more').setAttribute('aria-expanded','false');$('#more').focus();}});

void render();
