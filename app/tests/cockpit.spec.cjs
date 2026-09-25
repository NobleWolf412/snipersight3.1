/* global document, window, localStorage */
const {test,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;

test('confirmation cards explain actual conditions and candle progress',async({page},info)=>{
  const now=Math.floor(Date.now()/1000);
  const guide={available:true,state:'CONFIRMING',direction:'SHORT',timeframe:'15m',as_of:now,
    intended_trade:'Short · Resistance rejection',market_context:'15m structure turning bearish; 4H bullish structure',
    zone_bottom:'3.1105',zone_top:'3.1780',confirmation_boundary:'3.1105',last_price:'3.12',last_closed_at:now-20,
    conditions:['High at or above 3.1105','Close strictly below 3.1105','Close in the bottom 34% of that candle’s range'],
    max_followup_bars:3,completed_followup_bars:1,next_close_at:now+800,confirmation_deadline:now+1700,
    steps:[{complete:true},{complete:false},{complete:false}],
    skip_if:'A completed candle closes above 3.1780 by more than the volatility/tick buffer.',
    expiry_action:'Cancel this setup if no candle confirms in time.',after_confirmation:'Account risk checks still apply.',
    mini_chart:{zone_y:'40',zone_height:'45',boundary_y:'85',last_y:'78',bars:Array.from({length:16},(_,i)=>({x:20+i*18,high:String(20+i*3),low:String(55+i*3),body_top:String(30+i*3),body_height:'15',rising:i%3===0}))}};
  const row={state:'WATCHING',eligible:false,actionable:false,evidence:{grade:'UNGRADED'},progress_label:'Waiting for confirmation',confirmation_guide:guide,
    setup:{setup_id:'guide-test',symbol:'TESTUSDT',timeframe:'15m',strategy:'REVERSAL',direction:'SHORT',entry:null,stop:null,targets:[],confirmed_at:now-900},primary_explanation:'Old vague message',strongest_counterargument:'Wait'};
  await page.route('**/api/ui/v1/opportunities?*',r=>r.fulfill({json:{items:[row],total:1,counts:{ready:0,watching:1}}}));
  await page.route('**/api/ui/v1/setup-guide?*',r=>r.fulfill({json:guide}));
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/#opportunities');
  await page.getByRole('tab',{name:/Watching/}).click();
  const card=page.locator('.setup-row');
  await expect(card).toContainText('Close strictly below 3.1105');
  await expect(card).toContainText('1 of 3 follow-up candles recorded');
  await expect(card).toContainText('Next candle closes in');
  await expect(card.locator('svg')).toBeVisible();
  await expect(card).not.toContainText('Not set');
  await card.getByText('What cancels it?',{exact:true}).click();
  await expect(card).toContainText('volatility/tick buffer');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations.map(v=>v.id)).toEqual([]);
  await page.screenshot({path:info.outputPath('confirmation-card.png'),fullPage:true});
  await openSetupChart(page);
  await expect(page.locator('#setup-evidence')).toContainText('Close strictly below 3.1105');
  await expect(page.locator('#setup-evidence')).not.toContainText('Old vague message');
  row.state='BLOCKED';row.strongest_counterargument='The potential reward is too small for the risk.';
  guide.state='REJECTED';delete guide.steps;delete guide.next_close_at;
  await page.goto('/#blocked');
  await openSetupChart(page);
  await expect(page.locator('#setup-evidence')).toContainText('The potential reward is too small for the risk.');
  await expect(page.locator('#confirmation-detail')).toContainText('This setup has left the confirmation stage.');
  await expect(page.locator('#confirmation-detail')).not.toContainText('countdown starts');
  expect(errors).toEqual([]);
});

test.beforeEach(async({page,request})=>{
  await page.route('**/api/command',route=>route.fulfill({json:{generated_at:Math.floor(Date.now()/1000),scanner:{state:'SCANNING',age_s:2,stage:'idle',cycles:3},automation:{mode:'PAPER',halted:false},opportunities:{counts:{}},data:{}}}));
  const response=await request.get('/api/ui/v1/context');
  expect((await response.json()).epoch.label).toBe('Isolated preview · synthetic');
  // Protected effects are blocked twice: in this browser and in the harness.
  await page.route('**/api/**',async route=>{
    if(route.request().method()==='POST')await route.fulfill({status:409,json:{detail:'Protected effect stubbed in browser test'}});
    else await route.continue();
  });
});

async function ticket(page){
  await page.goto('/#trade');
  await expect(page.locator('#ticket')).toBeVisible();
  await page.locator('#entry').fill('100');
  await page.locator('#sl').fill('98');
  await page.locator('#tp').fill('104');
}

async function openSetupChart(page){
  await page.getByRole('button',{name:/^(View chart|Review trade)$/}).first().click();
  const open=page.getByRole('button',{name:'Open in Trade',exact:true});
  try{await open.waitFor({state:'visible',timeout:2000});await open.click();}catch{ /* direct chart route */ }
}

function preview(){return {request:{workspace:'CRYPTO',symbol:'BTCUSDT',tf:'1H',direction:'LONG',entry:'100',sl:'98',tp:'104',risk_usd:'25',created_at:Math.floor(Date.now()/1000),expected_epoch:'fixture'},quantity:'12.5',risk_usd:'25',rr:'2',expires_at:Math.floor(Date.now()/1000)+120,note:'Preview fixture'};}

test('forward trial separates new evidence and expands trade reasons',async({page},info)=>{
  const now=Math.floor(Date.now()/1000);
  await page.route('**/api/ui/v1/simple-strategy-trial*',route=>route.fulfill({json:{state:'COLLECTING',affects_trading:false,started_at:now-86400,ends_at:now+86400,checked_at:now,arms:{CURRENT:{closed:1,symbols:1,net_usd:'-5',return_pct:'-0.05',max_drawdown_pct:'0.05',mean_r:'-0.05',unresolved:0,by_direction:{LONG:{closed:1,net_usd:'-5'},SHORT:{closed:0,net_usd:'0'}}},CHANNEL:{closed:1,symbols:1,net_usd:'10',return_pct:'0.1',max_drawdown_pct:'0',mean_r:'0.1',unresolved:0,by_direction:{LONG:{closed:1,net_usd:'10'},SHORT:{closed:0,net_usd:'0'}}}},primary:{verdict:'UNKNOWN',minimum_trades_each:30,minimum_symbols_each:8,interval:null}}}));
  await page.route('**/api/ui/v1/forward-trial*',route=>route.fulfill({json:{state:'COLLECTING',started_at:now-86400,checked_at:now,starting_balance:'10000',balance:'10123.45',pnl_usd:'123.45',risk_usd:'100',max_slots:5,counts:{PLACED:1,FILLED:1,CLOSED:1,SKIPPED:1,EXPIRED:0},curve:[{time:now-86400,value:'10000'},{time:now,value:'10123.45'}],items:[{symbol:'BTCUSDT',tf:'15m',observed_at:now,state:'SKIPPED',entry:'100',sl:'98',tp:'104',direction:'LONG',reason:'The trial is already watching a trade in this market.'}]}}));
  await page.goto('/#research');
  await expect(page.getByRole('heading',{name:'Does a simpler strategy work better?'})).toBeVisible();
  await expect(page.getByText('Too few completed trades')).toBeVisible();
  await expect(page.locator('.trial-balance')).toHaveText('$10,123.45');
  await expect(page.locator('.trial-curve')).toBeVisible();
  await page.locator('.trial-trade summary').click();
  await expect(page.getByText('The trial is already watching a trade in this market.')).toBeVisible();
  await expect(page.getByRole('heading',{name:'Simulation results & setup decisions'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations.map(v=>v.id)).toEqual([]);
  await page.screenshot({path:info.outputPath('forward-trial.png'),fullPage:true});
});

test('six screens, chart, keyboard navigation and accessibility',async({page},info)=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  for(const route of ['home','opportunities','trade','journal','research','settings']){
    await page.goto('/#'+route);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('#content .error')).toHaveCount(0);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
    if(route==='trade')await expect(page.locator('#chart canvas').first()).toBeVisible();
    const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
    expect(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
    if(route==='home'||route==='trade')await page.screenshot({path:info.outputPath(route+'.png'),fullPage:true});
  }
  if(info.project.name==='phone-webkit'){
    await page.locator('#more').click();
    await expect(page.locator('#more-menu')).toBeVisible();
    await page.locator('#more-menu a[href="#research"]').click();
    await expect(page.locator('h1')).toHaveText('Research is evidence.');
    await expect(page.locator('#more-menu')).toBeHidden();
  }
  expect(errors).toEqual([]);
});

test('research panes cannot replace the price chart opening range',async({page})=>{
  const now=Math.floor(Date.now()/3600000)*3600;
  await page.route('**/api/research-series?*',route=>route.fulfill({json:{
    order_blocks:[{block_id:'visible-ob',direction:'BULL',source_candle_ts:now-6*3600,break_ts:now-5*3600,bottom:'100.4',top:'101.2',version:'order-block-fixture'}],
    structure_sequences:[{block_id:'visible-ob',direction:'BULL',block_ts:now-6*3600,break_ts:now-5*3600,sweep_ts:null,state:'PARTIAL',version:'sequence-fixture'}],
    regular_divergence:[{prev_pivot_ts:now-8*3600,time:now-7*3600,price_prev:'100.3',price:'100.9',divergence:'BULLISH',version:'regular-fixture'}],
    hidden_divergence:[{prev_pivot_ts:now-4*3600,time:now-3*3600,price_prev:'101.1',price:'100.6',divergence:'BEARISH_HIDDEN',version:'hidden-fixture'}],
    stoch_rsi:Array.from({length:120},(_,i)=>({time:now-(119-i)*3600,confirmed_at:now-(118-i)*3600,k:'45',d:'50'})),
    // A fresh collector often has only a few OI readings. Those timestamps
    // used to auto-fit the main chart down to two giant candles.
    open_interest:[{time:now-600,value:'1000',change_1h:null},{time:now-300,value:null,status:'MISSING'},{time:now,value:'1001',change_1h:'1'}],
  }}));
  await page.goto('/#trade');
  await expect(page.locator('#chart canvas').first()).toBeVisible();
  const before=await page.evaluate(()=>window.SSCockpitChartHost?.chart()?.timeScale().getVisibleLogicalRange());
  expect(before).toBeTruthy();
  await page.locator('[data-chart-preset="research"]').click();
  await expect(page.locator('#research-indicator-panes')).toBeVisible();
  await expect(page.locator('.research-ob-label')).toHaveText('OB ↑');
  await expect(page.locator('.research-ob-label')).toBeVisible();
  await expect(page.locator('.research-sequence.partial')).toBeVisible();
  await expect(page.locator('.research-sequence-state')).toHaveText('B→OB · partial');
  await expect(page.locator('.research-layer-summary')).toContainText('1 structure sequences (0 complete · 1 partial; partial means no sweep recorded)');
  await expect(page.locator('.research-layer-summary')).toHaveAttribute('data-sequence-markers','1');
  await expect(page.locator('.research-layer-summary')).toHaveAttribute('data-regular-divergence-series','1');
  await expect(page.locator('.research-layer-summary')).toHaveAttribute('data-hidden-divergence-series','1');
  await expect(page.locator('[data-research-pane="stoch"]')).toHaveAttribute('data-point-count','120');
  await expect(page.locator('[data-research-pane="oi"]')).toHaveAttribute('data-point-count','2');
  await expect(page.locator('[data-research-pane="oi"]')).toHaveAttribute('data-gap-count','1');
  await page.waitForTimeout(50);
  const after=await page.evaluate(()=>window.SSCockpitChartHost?.chart()?.timeScale().getVisibleLogicalRange());
  expect(after).toBeTruthy();
  expect(after.to-after.from).toBeGreaterThanOrEqual((before.to-before.from)*0.8);
});

test('stock selection never renders crypto money or calls a crypto chart',async({page})=>{
  await page.goto('/#trade');await expect(page.locator('#ticket')).toBeVisible();
  const calls=[];page.on('request',r=>calls.push(r.url()));
  await page.locator('#workspace').selectOption('STOCKS');
  await expect(page.getByRole('heading',{name:'Stock trading is not enabled yet'})).toBeVisible();
  await expect(page.locator('#ticket')).toHaveCount(0);
  expect(await page.locator('#content').innerText()).not.toContain('$10,000');
  expect(calls.filter(url=>url.includes('workspace=CRYPTO'))).toEqual([]);
});

test('editing while preview is pending removes authority to place old terms',async({page})=>{
  let release;
  const ready=new Promise(resolve=>{release=resolve;});
  let entered;
  const pending=new Promise(resolve=>{entered=resolve;});
  await page.route('**/api/ui/v1/ticket/preview',async route=>{entered();await ready;await route.fulfill({json:preview()});});
  await ticket(page);await page.getByRole('button',{name:'Review paper order'}).click();await pending;
  await page.locator('#entry').fill('101');release();
  await expect(page.getByRole('button',{name:'Place paper order'})).toHaveCount(0);
  await page.getByRole('button',{name:'Review paper order'}).click();
  await expect(page.getByRole('heading',{name:'Review before placing'})).toBeVisible();
  await expect(page.locator('#ticket-result')).toContainText('BTCUSDT LONG');
});

test('proven rejection releases saved request; uncertain delivery survives reload',async({page})=>{
  await page.route('**/api/ui/v1/ticket/preview',route=>route.fulfill({json:preview()}));
  let behavior='reject';const sent=[];
  await page.route('**/api/ui/v1/ticket/arm',async route=>{
    sent.push(route.request().postDataJSON());
    if(behavior==='reject')await route.fulfill({status:400,json:{detail:'PREVIEW_EXPIRED'}});
    else if(behavior==='lost')await route.abort('failed');
    else await route.fulfill({json:{ok:true,receipt:{intent_id:'fixture-receipt',already_armed:true}}});
  });
  await ticket(page);await page.getByRole('button',{name:'Review paper order'}).click();
  await page.getByRole('button',{name:'Place paper order'}).click();
  await expect(page.locator('#ticket-result')).toContainText('No new order was accepted');
  expect(await page.evaluate(()=>localStorage.getItem('ss-pending-ticket-v1'))).toBeNull();
  behavior='lost';await page.getByRole('button',{name:'Review paper order'}).click();await page.getByRole('button',{name:'Place paper order'}).click();
  await expect(page.getByRole('button',{name:'Retry this order'})).toBeVisible();
  await page.reload();await expect(page.getByRole('button',{name:'Retry this order'})).toBeVisible();
  behavior='receipt';await page.getByRole('button',{name:'Retry this order'}).click();
  await expect(page.getByRole('heading',{name:'Existing order recovered'})).toBeVisible();
  expect(sent[2]).toEqual(sent[1]);
  expect(await page.evaluate(()=>localStorage.getItem('ss-pending-ticket-v1'))).toBeNull();
});


test('background refresh keeps the page and focused control mounted',async({page})=>{
  await page.clock.install();
  await page.goto('/#home');
  await expect(page.locator('#pause')).toBeVisible();
  await expect(page.locator('#pulse .loading')).toHaveCount(0);
  await page.locator('#pause').focus();
  await page.evaluate(()=>{window.savedHeading=document.querySelector('h1');window.savedPause=document.querySelector('#pause');window.savedPulse=document.querySelector('#pulse');});
  const refreshed=page.waitForResponse(response=>response.url().includes('/api/ui/v1/home'));
  await page.clock.fastForward(15000);
  await refreshed;
  await expect(page.locator('#pause')).toBeFocused();
  expect(await page.evaluate(()=>window.savedHeading===document.querySelector('h1')&&window.savedPause===document.querySelector('#pause')&&window.savedPulse===document.querySelector('#pulse'))).toBeTruthy();
  await expect(page.locator('#content > .loading')).toHaveCount(0);
  await expect(page.locator('#pulse .loading')).toHaveCount(0);
});


test('paper risk setting sends the user percentage and current account guard',async({page})=>{
  await page.goto('/#settings');
  await expect(page.locator('#account-risk')).toBeVisible();
  await page.route('**/api/account/risk',route=>route.fulfill({status:409,json:{detail:'Fixture save rejected'}}));
  await page.locator('#account-risk').fill('0.75');
  const sent=page.waitForRequest(request=>request.url().includes('/api/account/risk'));
  await page.getByRole('button',{name:'Save paper risk'}).click();
  const payload=(await sent).postDataJSON();
  expect(payload.risk_percent).toBe('0.75');
  expect(payload.workspace).toBe('CRYPTO');
  expect(payload.expected_epoch).toBeTruthy();
  expect(payload.expected_risk_pct).toBeTruthy();
  await expect(page.locator('#notice')).toContainText('Fixture save rejected');
  await expect(page.locator('#account-risk')).toHaveValue('0.75');
});

test('profit protection is an explicit new-trade toggle at desktop and phone sizes',async({page})=>{
  await page.route('**/api/settings',route=>route.fulfill({json:{values:{profit_protection_cost_cover:false},spec:[],history:[]}}));
  await page.goto('/#settings');
  const toggle=page.getByRole('checkbox',{name:/Move the stop to cover estimated costs/});
  await expect(toggle).toBeVisible();
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await page.getByRole('button',{name:'Save profit protection'}).click();
  await expect(page.getByRole('dialog')).toContainText('Open trades keep their recorded choice');
  await expect(page.getByRole('dialog')).toContainText('new forward results window');
  await page.getByRole('button',{name:'Keep as is'}).click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});


test('journal details are directly reachable and older history is tucked away',async({page})=>{
  const trade={intent_id:'test-order',symbol:'LINKUSDT',direction:'LONG',timeframe:'1H',origin:'BOT',controller:'BOT',outcome:'SL',r_multiple:'-1',grade_eligible:true,planned_stop:'98',stop:'100.2',profit_protection:'COST_COVER',stop_history:[{effective_at:1789401600,stop:'100.2',reason:'COST_COVER_AFTER_1R'}]};
  await page.route('**/api/ui/v1/journal?*',route=>route.fulfill({json:{items:[trade],scope:'EXECUTED_ACCOUNT',note:'Recorded paper trades.'}}));
  await page.route('**/api/ui/v1/trades/test-order/diagnosis?*',route=>route.fulfill({json:{trade,facts:[],limits:''}}));
  await page.goto('/#journal');
  const button=page.getByRole('button',{name:'View LINKUSDT trade details'});
  await expect(button).toBeInViewport();
  await expect(page.getByRole('button',{name:'View older accounts'})).toBeHidden();
  await button.click();
  await expect(page.getByRole('heading',{name:'LINKUSDT · Trade details'})).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('Actual protective stop');
  await expect(page.getByRole('dialog')).toContainText('stop tightened to 100.2');
  expect(await page.locator('.trade-list').evaluate(node=>node.scrollWidth<=node.clientWidth)).toBeTruthy();
});

test('research explanation and strategy guide stay in the current app',async({page})=>{
  const row={setup:{symbol:'BCHUSDT',timeframe:'15m',strategy:'PULLBACK',direction:'LONG',entry:null},state:'BLOCKED',primary_explanation:'price reached the DEMAND zone 214.270-214.371 in BULL_TREND · waiting for a close that proves it held (3 bars)',strongest_counterargument:'The setup has no expiry, so the entry window cannot be verified.'};
  await page.route('**/api/ui/v1/research?*',route=>route.fulfill({json:{items:[row],note:'Research only.'}}));
  await page.goto('/#research');
  await page.getByRole('button',{name:'Inspect',exact:true}).click();
  await expect(page.locator('#research-detail')).toContainText('support area at 214.270-214.371 during an uptrend');
  await expect(page.locator('#research-detail')).toContainText('No entry deadline is recorded');
  await expect(page.locator('a[href^="/classic"]')).toHaveCount(0);
  await page.locator('#research-detail a').click();
  await expect(page.getByRole('heading',{name:'How the bot trades',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Pullback',exact:true})).toBeVisible();
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations).toEqual([]);
});


test('strategy examples load locally and enlarge without leaving the guide',async({page})=>{
  await page.goto('/#strategies');
  for(const kind of ['pullback','reversal']){
    const button=page.getByRole('button',{name:`Enlarge ${kind} chart`});
    await button.scrollIntoViewIfNeeded();
    await expect(button.locator('img')).toBeVisible();
    await expect.poll(()=>button.locator('img').evaluate(img=>img.complete&&img.naturalWidth>0)).toBeTruthy();
    await button.click();
    await expect(page.getByRole('dialog',{name:'Historical chart example'})).toBeVisible();
    await expect(page.locator('.strategy-zoom img')).toHaveAttribute('src',`/static/assets/strategies/${kind}.jpg`);
    await page.getByRole('button',{name:'Close chart',exact:true}).click();
    await expect(page.getByRole('dialog')).toBeHidden();
    await expect(button).toBeFocused();
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});


test('opportunities preserve confirmed prices and leave missing setup prices blank',async({page})=>{
  let ready=false;
  await page.route('**/api/ui/v1/opportunities?*',route=>route.fulfill({json:{total:1,items:[{setup:{setup_id:'prices-test',symbol:'BTCUSDT',timeframe:'1H',strategy:'PULLBACK',direction:'LONG',entry:ready?'100.125':'0',stop:ready?'98.250':'0.00',targets:[ready?'104.875':'0'],invalidation:'Stop-loss',expires_at:Math.floor(Date.now()/1000)+3600},state:ready?'READY':'FORMING',evidence:{grade:'UNGRADED'},primary_explanation:'Waiting for confirmation.',strongest_counterargument:'No entry deadline is recorded.'}]}}));
  await page.goto('/#opportunities');
  await expect(page.getByText('No confirmed trades ready right now')).toBeVisible();
  await page.getByRole('tab',{name:/Watching/}).click();
  await openSetupChart(page);
  for(const name of ['entry','sl','tp']){
    await expect(page.locator('#'+name)).toHaveValue('');
    await expect(page.locator('#'+name)).toHaveAttribute('placeholder','Not available yet');
  }
  await expect(page.locator('#setup-prices-pending')).toBeVisible();
  ready=true;
  await page.goto('/#opportunities');
  await openSetupChart(page);
  await expect(page.locator('#entry')).toHaveValue('100.125');
  await expect(page.locator('#sl')).toHaveValue('98.250');
  await expect(page.locator('#tp')).toHaveValue('104.875');
  await expect(page.locator('#setup-prices-pending')).toHaveCount(0);
});


test('watching shows recorded timing, prices and chart conditions',async({page})=>{
  const row={setup:{setup_id:'guide-test',symbol:'BTCUSDT',timeframe:'1H',strategy:'PULLBACK',direction:'LONG',entry:'0',stop:'0',targets:[],confirmed_at:1700000000,expires_at:null,invalidation:'Not set'},state:'FORMING',evidence:{grade:'UNGRADED'},primary_explanation:'Waiting for confirmation.',strongest_counterargument:'No entry deadline is recorded.'};
  await page.route('**/api/ui/v1/opportunities?*',route=>route.fulfill({json:{total:1,items:[row]}}));
  await page.route('**/api/ui/v1/setup-guide?*',route=>route.fulfill({json:{zone_bottom:'98.125',zone_top:'99.875',confirmation_deadline:1700007200,entry_deadline:null,confirmation:'A completed candle must close above the upper edge.',skip_if:'Skip if the zone breaks before confirmation.'}}));
  await page.goto('/#opportunities');
  await page.getByRole('tab',{name:/Watching/}).click();
  await expect(page.locator('.setup-row')).toContainText('Setup recorded');
  await expect(page.locator('.setup-row')).toContainText('Stop-loss');
  await expect(page.locator('.setup-row')).toContainText('Not set');
  await openSetupChart(page);
  await expect(page.locator('#setup-evidence')).toContainText('98.125');
  await expect(page.locator('#setup-evidence')).toContainText('99.875');
  await expect(page.locator('#setup-evidence')).toContainText('Skip if the zone breaks');
  await expect(page.locator('#chart canvas').first()).toBeVisible();
  await expect(page.locator('#opportunity-level-key')).toContainText('Area lower edge: 98.125');
  await expect(page.locator('#opportunity-level-key')).toContainText('Area upper edge: 99.875');
  await page.locator('#symbol').fill('ETHUSDT');
  await page.locator('#symbol').press('Tab');
  await expect(page.locator('#setup-evidence')).toHaveCount(0);
  await expect(page.locator('#entry')).toHaveValue('');
});

test('entry remains distinct when it shares the watched zone edge',async({page})=>{
  const row={setup:{setup_id:'overlap-test',symbol:'BTCUSDT',timeframe:'1H',strategy:'PULLBACK',direction:'LONG',entry:'99.8750',stop:'98',targets:['104']},state:'FORMING',evidence:{grade:'UNGRADED'}};
  await page.route('**/api/ui/v1/opportunities?*',route=>route.fulfill({json:{total:1,items:[row]}}));
  await page.route('**/api/ui/v1/setup-guide?*',route=>route.fulfill({json:{zone_bottom:'99',zone_top:'99.875',confirmation:'Waiting for confirmation.',skip_if:'Skip if the zone breaks.'}}));
  await page.goto('/#opportunities');
  await page.getByRole('tab',{name:/Watching/}).click();
  await openSetupChart(page);
  await expect(page.locator('#opportunity-level-key .entry-level')).toHaveText('Entry: 99.8750 · area upper edge at the same price');
  await expect(page.locator('#opportunity-level-key span')).toHaveCount(4);
  await expect(page.locator('#chart canvas').first()).toBeVisible();
});

test('profit colours, recorded result bars and accessible trade pop-out',async({page},info)=>{
  const base={direction:'LONG',timeframe:'1H',origin:'BOT',controller:'BOT',grade_eligible:true,entry:'100',exit_price:'102',risk_usd:'25',closed_at:1789416000,fees_usd:'0.5',funding_usd:'0',slippage_usd:'0',pnl_basis:'EXACT'};
  const items=[['BTCUSDT','50','2'],['ETHUSDT','-25','-1'],['LINKUSDT','0','0'],['SOLUSDT',null,null]].map(([symbol,realised_usd,r_multiple],i)=>({...base,intent_id:'visual-'+i,symbol,realised_usd,r_multiple,outcome:i===3?'PENDING':'TP'}));
  await page.route('**/api/ui/v1/journal?*',route=>route.fulfill({json:{items,scope:'EXECUTED_ACCOUNT',note:'Recorded paper trades.'}}));
  await page.route('**/api/ui/v1/trades/visual-0/diagnosis?*',route=>route.fulfill({json:{trade:items[0],facts:[],limits:''}}));
  await page.goto('/#journal');
  for(const tone of ['gain','loss','flat','pending'])await expect(page.locator('.trade-list .pnl-value.pnl-'+tone)).toHaveCount(1);
  await expect(page.locator('.result-chart-row')).toHaveCount(3);
  await expect(page.locator('.trade-list')).toContainText('Not available');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath('journal-visual.png'),fullPage:true});
  const opener=page.getByRole('button',{name:'View BTCUSDT trade details'});
  await opener.click();
  await expect(page.getByRole('dialog')).toContainText('$50.00');
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
  await page.screenshot({path:info.outputPath('trade-popout.png')});
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test('trade journey loads historical candles around the recorded fill',async({page},info)=>{
  const start=1789000000;
  const trade={intent_id:'history',symbol:'LINKUSDT',timeframe:'1H',direction:'LONG',origin:'BOT',controller:'BOT',filled_at:start,closed_at:start+7200,entry:'100',exit_price:'98',planned_stop:'98',targets:['104'],realised_usd:'-25',r_multiple:'-1',outcome:'SL'};
  await page.route('**/api/ui/v1/journal?*',route=>route.fulfill({json:{items:[trade],scope:'EXECUTED_ACCOUNT',note:'Recorded trades'}}));
  await page.route('**/api/ui/v1/trades/history/diagnosis?*',route=>route.fulfill({json:{trade}}));
  await page.route('**/api/candles?*',route=>{
    const url=new URL(route.request().url());expect(url.searchParams.get('symbol')).toBe('LINKUSDT');expect(Number(url.searchParams.get('end_ts'))).toBe(start+7200+43200);
    return route.fulfill({json:Array.from({length:20},(_,i)=>({time:start+(i-8)*3600,open:100,high:103,low:97,close:99+i%3,volume:10}))});
  });
  await page.goto('/#journal');await page.getByRole('button',{name:'View LINKUSDT trade details'}).click();
  await expect(page.locator('.trade-history-chart canvas').first()).toBeVisible();
  await expect(page.locator('.trade-history-note')).toContainText('Dots mark recorded fill prices');
  expect(await page.locator('.trade-dialog').evaluate(n=>n.scrollWidth<=n.clientWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath('trade-history.png')});
  await page.getByRole('button',{name:'Close details'}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('journal shows profit given back and distinct sub-dollar chart labels',async({page},info)=>{
  const start=1789000200;
  const trade={intent_id:'precise',symbol:'ENAUSDT',timeframe:'15m',direction:'LONG',origin:'BOT',controller:'BOT',grade_eligible:true,filled_at:start,closed_at:start+3600,entry:'0.13910',exit_price:'0.13851',planned_stop:'0.13852',targets:['0.14100'],realised_usd:'-176.47',r_multiple:'-1.18',outcome:'SL',price_format:{type:'price',precision:6,minMove:'0.000001'},excursion:{state:'LOWER_BOUND',peak_at:start+1800,peak_price:'0.1406',peak_gain_usd:'386.375',peak_gain_r:'2.58',given_back_usd:'386.375',note:'Entry and exit candle extremes are excluded. Before fees and funding.'}};
  await page.route('**/api/ui/v1/journal?*',r=>r.fulfill({json:{items:[trade],scope:'EXECUTED_ACCOUNT',note:'Recorded trades'}}));
  await page.route('**/api/ui/v1/trades/precise/diagnosis?*',r=>r.fulfill({json:{trade,stop_comparison:{state:'COLLECTING',started_at:start+86400,items:[]}}}));
  await page.route('**/api/candles?*',r=>r.fulfill({json:Array.from({length:22},(_,i)=>({time:start+(i-6)*900,open:.139,high:.1406,low:.1385,close:.1395,volume:10}))}));
  await page.goto('/#journal');
  await page.evaluate(()=>{
    const lib=window.LightweightCharts;
    window.LightweightCharts={...lib,createChart(...args){
      const chart=lib.createChart(...args),add=chart.addCandlestickSeries.bind(chart);
      chart.addCandlestickSeries=(options)=>{
        const series=add(options);
        window.__journalPriceLabels=['0.13910','0.13852','0.14100','0.13851'].map(p=>series.priceFormatter().format(Number(p)));
        return series;
      };
      return chart;
    }};
  });
  await page.getByRole('button',{name:'View ENAUSDT trade details'}).click();
  await expect(page.locator('.trade-history-chart canvas').first()).toBeVisible();
  await expect(page.locator('.excursion-panel')).toContainText('At least $386.38');
  await expect(page.locator('.excursion-panel')).toContainText('Profit given back');
  const labels=await page.evaluate(()=>window.__journalPriceLabels);
  expect(labels).toEqual(['0.139100','0.138520','0.141000','0.138510']);
  expect(await page.locator('.trade-dialog').evaluate(n=>n.scrollWidth<=n.clientWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath('precise-journal.png')});
});

test('stop comparison counts only completed triplets and explains pending arms',async({page},info)=>{
  const now=Math.floor(Date.now()/1000);
  const rules={HOLD:'Original stop',COST_COVER:'Cover costs after +1R',STRUCTURE:'Follow confirmed swings'};
  await page.route('**/api/ui/v1/stop-comparison*',r=>r.fulfill({json:{state:'COLLECTING',started_at:now-86400,checked_at:now,rules,paired_count:2,pending_count:3,excluded_count:1,totals:{HOLD:{pnl_usd:'-200',difference_usd:'0'},COST_COVER:{pnl_usd:'50',difference_usd:'250',better:1,worse:0},STRUCTURE:{pnl_usd:'-25',difference_usd:'175',better:1,worse:1}},items:[]}}));
  await page.goto('/#research');
  await expect(page.locator('.study-panel:not(.zone-study)')).toContainText('3 still being followed');
  await expect(page.locator('.study-cost')).toContainText('$250.00 versus the original stop');
  await page.getByText('What each rule does',{exact:true}).click();
  await expect(page.locator('.study-panel:not(.zone-study)')).toContainText('Changes take effect on the next candle');
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations.map(v=>v.id)).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath('stop-study.png'),fullPage:true});
});

test('open simulated stop paths extend beyond the recorded exit',async({page})=>{
  const now=Math.floor(Date.now()/1000),start=Math.floor((now-86400)/900)*900;
  const trade={intent_id:'still-following',symbol:'ENAUSDT',timeframe:'15m',direction:'LONG',origin:'BOT',controller:'BOT',filled_at:start,closed_at:start+900,entry:'100',exit_price:'98',planned_stop:'98',targets:['110'],price_format:{type:'price',precision:2,minMove:'.01'}};
  const comparison={state:'COLLECTING',rules:{HOLD:'Original stop',COST_COVER:'Cover costs after +1R',STRUCTURE:'Follow confirmed swings'},items:[{state:'OPEN',results:{HOLD:{at:start+900,outcome:'SL',pnl_usd:'-20'},COST_COVER:null,STRUCTURE:null},moves:{COST_COVER:[{at:start+36000,price:'100.2'}],STRUCTURE:[]}}]};
  await page.route('**/api/ui/v1/journal?*',r=>r.fulfill({json:{items:[trade],scope:'EXECUTED_ACCOUNT',note:''}}));
  await page.route('**/api/ui/v1/trades/still-following/diagnosis?*',r=>r.fulfill({json:{trade,stop_comparison:comparison}}));
  await page.route('**/api/candles?*',r=>{
    const end=Number(new URL(r.request().url()).searchParams.get('end_ts'));
    expect(end).toBeGreaterThanOrEqual(now-5);
    return r.fulfill({json:Array.from({length:96},(_,i)=>({time:start+i*900,open:101,high:105,low:99,close:102,volume:1}))});
  });
  await page.goto('/#journal');
  await page.evaluate(()=>{
    const lib=window.LightweightCharts;
    window.__studyTraces=[];
    window.LightweightCharts={...lib,createChart(...args){const chart=lib.createChart(...args),add=chart.addLineSeries.bind(chart);chart.addLineSeries=options=>{const series=add(options),set=series.setData.bind(series);series.setData=data=>{if(options.title?.includes('simulated'))window.__studyTraces.push(data);return set(data);};return series;};return chart;}};
  });
  await page.getByRole('button',{name:'View ENAUSDT trade details'}).click();
  await expect(page.locator('.trade-history-chart canvas').first()).toBeVisible();
  await expect(page.locator('.study-timeline')).toContainText('100.2');
  expect(await page.evaluate(()=>window.__studyTraces[0].some(p=>p.value===100.2))).toBeTruthy();
});


test('bot view separates fresh scanning, paused entries and delayed updates',async({page},info)=>{
  await page.clock.install();
  // A poll also waits for positions after rendering status. Advancing the
  // clock while that request is pending may legitimately skip one tick.
  const nextStatus=async text=>expect.poll(async()=>{
    await page.clock.fastForward(15000);
    return page.locator('#bot-status').innerText();
  }).toContain(text);
  let status={generated_at:Math.floor(Date.now()/1000),scanner:{state:'SCANNING',age_s:3,stage:'engines LINKUSDT (12/40)',cycles:7},automation:{mode:'PAPER',halted:true},opportunities:{counts:{WATCHING:2,READY:1,BLOCKED:4}},data:{headline:'Affected market: CAP-USD has missing price data.',observed_at:1789401600}};
  await page.route('**/api/command',route=>route.fulfill({json:status}));
  await page.goto('/#home');
  await expect(page.locator('#bot-status')).toContainText('Checking strategies');
  await page.getByRole('link',{name:'Open Bot view'}).click();
  await expect(page.locator('#bot-status')).toContainText('New entries paused');
  await expect(page.locator('progress')).toHaveAttribute('value','12');
  await expect(page.locator('#bot-status')).toContainText('CAP-USD');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();expect(audit.violations.map(v=>v.id)).toEqual([]);
  await page.screenshot({path:info.outputPath('bot-view.png'),fullPage:true});
  status={...status,scanner:{...status.scanner,stage:'research ETHUSDT (4/36)'}};
  await nextStatus('Updating research');
  await expect(page.locator('#bot-status')).toContainText('Current market: ETHUSDT');
  await expect(page.locator('progress')).toHaveAttribute('value','4');
  status={...status,scanner:{...status.scanner,stage:'paper risk'}};
  await nextStatus('Checking account risk');
  status={...status,scanner:{...status.scanner,state:'STALE',age_s:240}};
  await nextStatus('Scanner update overdue');
  await expect(page.locator('progress')).toHaveCount(0);
  await expect(page.locator('.bot-signal.reporting')).toHaveCount(0);
  await page.route('**/api/command',route=>route.fulfill({status:503,json:{detail:'Unavailable'}}));
  await nextStatus('Bot status unavailable');
});

test('blocked count opens searchable reasons and links to the setup chart',async({page},info)=>{
  await page.route('**/api/ui/v1/opportunities?*',route=>{
    const query=new URL(route.request().url()).searchParams;expect(query.get('state')).toBe('BLOCKED');
    return route.fulfill({json:{total:query.get('search')?0:345,items:query.get('search')?[]:[{state:'BLOCKED',setup:{setup_id:'blocked-fixture',symbol:'BCHUSDT',timeframe:'15m',strategy:'PULLBACK',direction:'LONG',entry:'0',stop:'0',targets:[],confirmed_at:1789401600},strongest_counterargument:'The setup has no expiry, so the entry window cannot be verified.',primary_explanation:'Waiting for confirmation.',reasons:[]}]}});
  });
  await page.goto('/#bot');await page.getByRole('link',{name:'View blocked setups and reasons'}).click();
  await expect(page.getByRole('heading',{name:'Why setups are blocked.'})).toBeVisible();
  await expect(page.locator('#blocked-list')).toContainText('No entry deadline is recorded');
  await expect(page.locator('#blocked-list')).toContainText('1 of 345');
  await expect(page.getByRole('button',{name:'View chart'})).toBeVisible();
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();expect(audit.violations.map(v=>v.id)).toEqual([]);
  await page.screenshot({path:info.outputPath('blocked-reasons.png'),fullPage:true});
  await page.getByRole('textbox',{name:'Market'}).fill('XYZ');await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.getByRole('heading',{name:'No blocked setups found'})).toBeVisible();
});

test('defended zone comparison shows timing, reasons, and chart timeframe toggle',async({page},info)=>{
  const start=Math.floor((Date.now()/1000-86400)/900)*900;
  const rules={HOLD:'Original stop',SWING_IDEAL:'Swing trail - candle close',SWING_OBSERVED:'Swing trail - scanner timing',ZONE_IDEAL:'Defended zone - candle close',ZONE_OBSERVED:'Defended zone - scanner timing'};
  const item={key:'paper:zone',state:'OPEN',source:'PAPER',tf:'15m',management_tf:'5m',symbol:'ENAUSDT',note:'Following the remaining simulated stops.',results:{},moves:{ZONE_IDEAL:[{at:start+1800,price:'99.5',confirmed_at:start+1800,observed_at:start+1850}]},zones:[{kind:'FORMED',at:start+900,detected_at:start+900,observed_at:start+950,low:'99',high:'100'},{kind:'DEFENDED',at:start+1800,detected_at:start+900,observed_at:start+1850,low:'99',high:'100'}],diagnostics:[{rule:'ZONE_OBSERVED',reason:'Price had already crossed the proposed stop.'}]};
  const comparison={state:'COLLECTING',rules,items:[item],paired_count:0,pending_count:1,excluded_count:0,started_at:start,checked_at:start+3000};
  const trade={intent_id:'zone',symbol:'ENAUSDT',timeframe:'15m',direction:'LONG',origin:'BOT',controller:'BOT',filled_at:start,closed_at:start+2700,entry:'100',exit_price:'98',planned_stop:'98',targets:['110'],price_format:{type:'price',precision:2,minMove:'.01'}};
  await page.route('**/api/ui/v1/zone-comparison*',r=>r.fulfill({json:comparison}));
  await page.route('**/api/ui/v1/journal?*',r=>r.fulfill({json:{items:[trade],scope:'EXECUTED_ACCOUNT',note:''}}));
  await page.route('**/api/ui/v1/trades/zone/diagnosis?*',r=>r.fulfill({json:{trade,zone_comparison:comparison}}));
  await page.route('**/api/candles?*',r=>{const step=new URL(r.request().url()).searchParams.get('tf')==='5m'?300:900;return r.fulfill({json:Array.from({length:40},(_,i)=>({time:start+(i-5)*step,open:100+Math.sin(i*.6)*.8,high:101.2+Math.sin(i*.6)*.8,low:99.4+Math.sin(i*.6)*.8,close:100+Math.sin(i*.6)*.8+(i%3===0?-.35:.45),volume:1}))});});
  await page.goto('/#research');
  await expect(page.locator('.zone-study .study-arm')).toHaveCount(5);
  await page.getByText('Individual trades and reasons',{exact:true}).click();
  await expect(page.locator('.zone-study')).toContainText('Price had already crossed');
  await page.goto('/#journal');
  await page.getByRole('button',{name:'View ENAUSDT trade details'}).click();
  await expect(page.locator('.trade-history-note')).toContainText('15m candles');
  await expect(page.getByRole('button',{name:'Recorded trade chart',exact:true})).toHaveAttribute('aria-pressed','true');
  await page.getByRole('button',{name:'Smaller-timeframe comparison',exact:true}).click();
  await expect(page.locator('.trade-history-note')).toContainText('5m candles');
  await page.getByLabel('Simulated stop',{exact:true}).selectOption('ZONE_IDEAL');
  await expect(page.locator('.trade-zone-area.defended')).toHaveCount(1);
  await expect(page.locator('.zone-study')).toContainText('observed');
  await page.getByRole('button',{name:'Recorded trade chart',exact:true}).click();
  await expect(page.locator('.trade-history-note')).toContainText('15m candles');
  await expect(page.locator('.journey-key')).toHaveCount(1);
  await page.getByRole('button',{name:'Smaller-timeframe comparison',exact:true}).click();
  await expect(page.locator('.trade-history-note')).toContainText('5m candles');
  expect(await page.locator('.trade-dialog').evaluate(n=>n.scrollWidth<=n.clientWidth)).toBeTruthy();
  await page.getByLabel('Simulated stop',{exact:true}).selectOption('SWING_OBSERVED');
  await expect(page.locator('.trade-zone-area')).toHaveCount(0);
  await page.getByLabel('Simulated stop',{exact:true}).selectOption('ZONE_IDEAL');
  await expect(page.locator('.trade-zone-area.defended')).toHaveCount(1);
  await page.locator('.trade-dialog .eyebrow').first().evaluate(n=>{n.textContent='SYNTHETIC TEST EXAMPLE - NOT A REAL TRADE';});
  await page.screenshot({path:info.outputPath('zone-comparison.png')});
});


test('opportunity tabs prioritize actionable plans and filter instantly',async({page},info)=>{
  const queries=[];
  await page.route('**/api/ui/v1/opportunities/tabs-*?*',route=>{
    const setupId=new URL(route.request().url()).pathname.split('/').at(-1);
    return route.fulfill({json:{state:'READY',eligible:true,actionable:true,evidence:{grade:'UNGRADED'},primary_explanation:'Recorded fixture',strongest_counterargument:'Account risk is checked again.',research_observations:{availability:'UNAVAILABLE',rows:[],missing_reason:'Research collection had not started when this setup was confirmed.'},setup:{setup_id:setupId,symbol:'BTC0USDT',timeframe:'1H',strategy:'PULLBACK',direction:'LONG',entry:'100',stop:'98',targets:['104'],expires_at:Math.floor(Date.now()/1000)+3600,confirmed_at:Math.floor(Date.now()/1000)}}});
  });
  await page.route('**/api/ui/v1/opportunities?*',route=>{
    const q=new URL(route.request().url()).searchParams;queries.push(Object.fromEntries(q));
    const watching=q.get('group')==='watching';
    const count=Number(q.get('limit')||10);
    const rows=Array.from({length:Math.min(count,12)},(_,i)=>({state:watching?'FORMING':'READY',eligible:!watching,actionable:!watching,evidence:{grade:'UNGRADED'},primary_explanation:'Recorded fixture',strongest_counterargument:'Account risk is checked again.',progress_label:watching?'Waiting for confirmation':'Ready to trade',setup:{setup_id:'tabs-'+i,symbol:(q.get('search')||'BTC')+i+'USDT',timeframe:'1H',strategy:'PULLBACK',direction:'LONG',entry:'100',stop:'98',targets:['104'],expires_at:Math.floor(Date.now()/1000)+3600,confirmed_at:Math.floor(Date.now()/1000)}}));
    return route.fulfill({json:{items:rows,total:12,counts:{ready:12,watching:8},ordering:'Confirmation stage first, then recorded proximity to the zone.'}});
  });
  await page.goto('/#opportunities');
  await expect(page.getByRole('tab',{name:/Ready to trade/})).toHaveAttribute('aria-selected','true');
  await expect(page.locator('.setup-row')).toHaveCount(10);
  await expect(page.getByText('Readiness',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Apply',exact:true})).toHaveCount(0);
  await page.getByRole('tab',{name:/Watching/}).click();
  await expect(page.locator('.setup-row').first()).toContainText('Waiting for confirmation');
  await page.getByLabel('Sort by',{exact:true}).selectOption('newest');
  await expect.poll(()=>queries.at(-1)?.sort).toBe('newest');
  await page.getByRole('button',{name:'Show 10 more',exact:true}).click();
  await expect(page.locator('.setup-row')).toHaveCount(12);
  await page.getByRole('searchbox',{name:'Market',exact:true}).fill('ETH');
  await expect(page.locator('.setup-row').first()).toContainText('ETH0USDT');
  await expect(page.locator('.setup-row')).toHaveCount(10);
  await page.getByRole('tab',{name:/Watching/}).focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('tab',{name:/Ready to trade/})).toHaveAttribute('aria-selected','true');
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations.map(v=>v.id)).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath('opportunity-tabs.png')});
  await page.getByRole('button',{name:'Review trade',exact:true}).first().click();
  await expect(page.locator('#opportunity-detail')).toContainText('Why it exists');
  await expect(page.locator('#opportunity-detail > .signal-map-notice')).toBeVisible();
  await expect(page.locator('#opportunity-detail > .signal-map-notice')).toHaveText('Research observation — did not affect this setup.');
  await page.locator('#opportunity-detail summary').filter({hasText:'Signal map at decision time'}).click();
  await expect(page.locator('#opportunity-detail')).toContainText('Research collection had not started');
  await page.getByRole('button',{name:'Open in Trade',exact:true}).click();
  await page.getByRole('button',{name:'Short',exact:true}).click();
  await expect(page.locator('#direction')).toHaveValue('SHORT');
  await expect(page.getByRole('button',{name:'Short',exact:true})).toHaveAttribute('aria-pressed','true');
});

test('signal map keeps every state explicit and expands by evidence row',async({page})=>{
  const now=Math.floor(Date.now()/1000);
  const states=['ALIGNED','OPPOSED','NEUTRAL','MISSING','STALE','NOT_APPLICABLE','ALIGNED','NEUTRAL'];
  const frames=['15m','1H','4H','1D'];
  const observations={availability:'PARTIAL',timeframes:frames,notice:'Research observation — did not affect this setup.',rows:['trend','structure'].map((key,row)=>({key,label:key==='trend'?'Trend':'Structure',cells:frames.map((timeframe,column)=>({family:key,timeframe,status:states[row*4+column],raw:states[row*4+column].replace('_',' '),source_timeframe:timeframe,confirmed_at:now-60,detector_version:'fixture-v1',values:{raw:'1.2500'},missing_reason:states[row*4+column]==='MISSING'?'No causal reading.':null}))}))};
  const item={state:'READY',eligible:true,actionable:true,evidence:{grade:'UNGRADED'},primary_explanation:'Recorded fixture',strongest_counterargument:'Wait.',research_observations:observations,setup:{setup_id:'signal-map-fixture',symbol:'MAPUSDT',timeframe:'1H',strategy:'PULLBACK',direction:'LONG',entry:'100',stop:'98',targets:['104'],expires_at:now+3600,confirmed_at:now}};
  await page.route('**/api/ui/v1/opportunities?*',route=>route.fulfill({json:{items:[item],total:1,counts:{ready:1,watching:0}}}));
  await page.route('**/api/ui/v1/opportunities/signal-map-fixture?*',route=>route.fulfill({json:item}));
  await page.goto('/#opportunities');
  await page.getByRole('button',{name:'Review trade',exact:true}).click();
  await expect(page.locator('#opportunity-detail > .signal-map-notice')).toBeVisible();
  await page.locator('#opportunity-detail summary').filter({hasText:'Signal map at decision time'}).click();
  for(const state of new Set(states))await expect(page.locator(`#opportunity-detail td[data-state="${state}"]`).first()).toBeVisible();
  const toggle=page.locator('#opportunity-detail .signal-row-toggle').first();
  await toggle.focus();await page.keyboard.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded','true');
  await expect(page.locator('#opportunity-detail tr[data-signal-row]').first().locator('.signal-cell-detail:visible')).toHaveCount(4);
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(audit.violations.map(v=>v.id)).toEqual([]);
});

test('home shows open trades alone, and folds recent closes out only when nothing is open',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const real=await (await page.request.get('/api/ui/v1/home')).json();
  const trade=(id,symbol,extra)=>({intent_id:id,symbol,direction:'LONG',timeframe:'1H',state:'OPEN',active:true,closed_at:null,...extra});
  const closes=[trade('c1','ETHUSDT',{state:'CLOSED',outcome:'TARGET',active:false,closed_at:1}),trade('c2','SOLUSDT',{state:'CLOSED',outcome:'STOP',active:false,closed_at:2})];
  let positions=[trade('o1','BTCUSDT')];
  await page.route('**/api/ui/v1/home*',route=>route.fulfill({json:{...real,positions,recent:closes}}));
  await page.goto('/#home');
  const card=page.locator('section.card',{has:page.getByRole('heading',{name:'Open trades & pending orders'})});
  await expect(card).toContainText('BTCUSDT');
  await expect(card).not.toContainText('ETHUSDT');
  await expect(page.getByRole('heading',{name:'Recent closes'})).toHaveCount(0);
  positions=[];
  await page.goto('/#opportunities');await page.goto('/#home');
  await expect(card).toContainText('Nothing open right now');
  const fold=card.locator('details.recent-closes');
  await expect(fold.locator('summary')).toHaveText('Recent closes (2)');
  await expect(fold.getByText('ETHUSDT')).toBeHidden();
  await fold.locator('summary').click();
  await expect(fold.getByText('ETHUSDT')).toBeVisible();
  await expect(fold.getByRole('link',{name:/Open journal/})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});
