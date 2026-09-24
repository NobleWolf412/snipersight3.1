/* Research preset renderer. The server returns every signal and Decimal value;
   this module only plots the supplied geometry and leaves missing OI as gaps. */
(() => {
  const svg = document.getElementById('researchPriceOverlay');
  const panes = document.getElementById('researchPanes');
  const stochPane = document.getElementById('stochResearchPane');
  const oiPane = document.getElementById('oiResearchPane');
  const chartPane = document.getElementById('chartPane');
  if(!svg || !panes || !stochPane || !oiPane || !chartPane) return;
  const api = path => window.SSData ? SSData.get(path, 0) :
    fetch(path, {cache:'no-store'}).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
  const activeKeys = ['orderblocks','sequences','divergence','stochrsi','openinterest'];
  const cache = new Map();
  let state = null, request = 0, stochChart, oiChart, stochK, stochD, oiSeries;
  let syncing = false;
  let paneSyncTimer;
  let countsSignature = '';
  let stochThresholdsAdded = false;

  const chartOptions = () => ({
    layout:{background:{color:'transparent'},textColor:'#7d8c83',
      fontFamily:"'JetBrains Mono',ui-monospace,monospace",fontSize:9},
    grid:{vertLines:{color:'rgba(255,255,255,.01)'},horzLines:{color:'rgba(255,255,255,.02)'}},
    rightPriceScale:{borderColor:'rgba(255,255,255,.05)'},
    timeScale:{borderColor:'rgba(255,255,255,.05)',timeVisible:true,secondsVisible:false},
    crosshair:{mode:0}, handleScale:false, handleScroll:false,
  });
  function bootPanes(){
    if(stochChart) return;
    stochChart = LightweightCharts.createChart(stochPane.querySelector('.research-pane-chart'), chartOptions());
    stochK = stochChart.addLineSeries({color:'#65d4a2',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
    stochD = stochChart.addLineSeries({color:'#d8b46b',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false});
    oiChart = LightweightCharts.createChart(oiPane.querySelector('.research-pane-chart'), chartOptions());
    oiSeries = oiChart.addLineSeries({color:'#7ab8dc',lineWidth:2,priceLineVisible:false,lastValueVisible:true});
    const main = window.SSChartResearchHost && window.SSChartResearchHost.chart();
    if(main) main.timeScale().subscribeVisibleTimeRangeChange(range => {
      if(syncing || !range) return;
      syncing = true;
      [stochChart,oiChart].forEach(target => {
        try{ target.timeScale().setVisibleRange(range); }catch(error){void error;}
      });
      syncing = false;
    });
    [stochPane,oiPane].forEach((pane, index) => new ResizeObserver(entries => {
      const box = entries[0].contentRect;
      const host = pane.querySelector('.research-pane-chart');
      const chart = index ? oiChart : stochChart;
      if(box.width > 0) chart.applyOptions({width:Math.floor(box.width),
        height:Math.max(50,Math.floor(host.clientHeight))});
    }).observe(pane));
  }
  function resizePane(pane, delta){
    const next = Math.max(90, Math.min(260, pane.getBoundingClientRect().height + delta));
    pane.style.height = `${next}px`;
    const handle=pane.querySelector('.pane-resizer');
    if(handle){handle.setAttribute('aria-valuenow',String(Math.round(next)));handle.setAttribute('aria-valuetext',`${Math.round(next)} pixels high`);}
  }
  panes.addEventListener('keydown', event => {
    const handle = event.target.closest('.pane-resizer');
    if(!handle || !['ArrowUp','ArrowDown'].includes(event.key)) return;
    event.preventDefault(); resizePane(handle.parentElement, event.key === 'ArrowUp' ? 12 : -12);
  });
  panes.addEventListener('pointerdown', event => {
    const handle = event.target.closest('.pane-resizer');
    if(!handle) return;
    const pane = handle.parentElement, start = event.clientY, height = pane.getBoundingClientRect().height;
    handle.setPointerCapture(event.pointerId);
    const move = e => { const next=Math.max(90,Math.min(260,height + e.clientY - start));pane.style.height = `${next}px`;handle.setAttribute('aria-valuenow',String(Math.round(next)));handle.setAttribute('aria-valuetext',`${Math.round(next)} pixels high`); };
    const up = e => { handle.releasePointerCapture(e.pointerId); handle.removeEventListener('pointermove',move); handle.removeEventListener('pointerup',up); };
    handle.addEventListener('pointermove',move); handle.addEventListener('pointerup',up);
  });

  function plotPrice(data){
    const host = window.SSChartResearchHost;
    const chart = host && host.chart(), series = host && host.series();
    if(!chart || !series){ svg.innerHTML = ''; return; }
    const width = svg.clientWidth || chartPane.clientWidth;
    const height = svg.clientHeight || chartPane.clientHeight;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    const x = t => chart.timeScale().timeToCoordinate(Number(t));
    const y = p => series.priceToCoordinate(Number(p));
    const shapes = [];
    if(state.overlays.orderblocks) (data.order_blocks || []).forEach(block => {
      const x1=x(block.source_candle_ts), x2=x(block.break_ts), yt=y(block.top), yb=y(block.bottom);
      if([x1,x2,yt,yb].some(v => v == null)) return;
      const bull = block.direction === 'BULL';
      const left=Math.min(x1,x2),right=Math.max(x1,x2),top=Math.min(yt,yb),bottom=Math.max(yt,yb);
      if(right<0||left>width||bottom<0||top>height) return;
      const midX=(left+right)/2,midY=(top+bottom)/2;
      shapes.push(`<rect class="research-ob ${bull?'bull':'bear'}" x="${left}" y="${top}" width="${Math.max(3,right-left)}" height="${Math.max(2,bottom-top)}"><title>Order block · ${block.direction} · ${block.bottom} to ${block.top} · ${block.version}</title></rect>`+
        `<text class="research-ob-label ${bull?'bull':'bear'}" x="${midX}" y="${midY}" text-anchor="middle" dominant-baseline="central"><title>Order block · ${block.direction}</title>OB ${bull?'↑':'↓'}</text>`);
    });
    if(state.overlays.sequences) (data.structure_sequences || []).forEach(seq => {
      const block=(data.order_blocks||[]).find(item=>item.block_id===seq.block_id);
      if(!block) return;
      const xb=x(seq.break_ts), xo=x(seq.block_ts), yy=y((Number(block.top)+Number(block.bottom))/2), complete=seq.sweep_ts!=null;
      const xs=complete?x(seq.sweep_ts):null;
      if([xb,xo,yy].some(v=>v==null)||(complete&&xs==null)) return;
      const points=complete?`${xs},${yy} ${xb},${yy-12} ${xo},${yy}`:`${xo},${yy} ${xb},${yy-12}`;
      const title=complete?`Sweep → break → linked block · ${seq.version}`:`Partial sequence · break linked to block · sweep unavailable · ${seq.version}`;
      const sweepLabel=complete?`<text class="research-label" x="${xs}" y="${yy-4}">S</text>`:'';
      const stateLabel=complete?'':`<text class="research-label research-sequence-state" x="${(xb+xo)/2}" y="${yy-6}" text-anchor="middle">B→OB · partial</text>`;
      shapes.push(`<polyline class="research-sequence ${complete?'complete':'partial'}" data-sequence-state="${complete?'COMPLETE':'PARTIAL'}" points="${points}"><title>${title}</title></polyline>`+
        `${sweepLabel}${complete?`<text class="research-label" x="${xb}" y="${yy-16}">B</text><text class="research-label" x="${xo}" y="${yy-4}">OB</text>`:''}${stateLabel}`);
    });
    if(state.overlays.divergence){
      const lines = [...(data.regular_divergence||[]).map(v=>({...v,hidden:false})),
        ...(data.hidden_divergence||[]).map(v=>({...v,hidden:true}))];
      lines.forEach(item => {
        const x1=x(item.prev_pivot_ts), x2=x(item.time), y1=y(item.price_prev), y2=y(item.price);
        if([x1,x2,y1,y2].some(v=>v==null)) return;
        shapes.push(`<line class="research-divergence ${item.hidden?'hidden':'regular'}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"><title>${item.hidden?'Hidden':'Regular'} ${item.divergence} divergence · ${item.version}</title></line>`);
      });
    }
    svg.innerHTML = shapes.join('');
  }

  function plotPanes(data){
    const showStoch=!!state.overlays.stochrsi, showOi=!!state.overlays.openinterest;
    panes.hidden = !(showStoch || showOi); stochPane.hidden=!showStoch; oiPane.hidden=!showOi;
    chartPane.classList.toggle('research-panes-on', showStoch || showOi);
    chartPane.classList.toggle('stoch-pane-on', showStoch);
    chartPane.classList.toggle('oi-pane-on', showOi);
    if(!(showStoch || showOi)) return;
    bootPanes();
    clearTimeout(paneSyncTimer);
    if(showStoch){
      const rows=(data.stoch_rsi||[]).filter(r=>r.k!=null&&r.d!=null);
      stochK.setData(rows.map(r=>({time:Number(r.time),value:Number(r.k)})));
      stochD.setData(rows.map(r=>({time:Number(r.time),value:Number(r.d)})));
      if(!stochThresholdsAdded){
        [20,80].forEach(level => stochK.createPriceLine({price:level,color:'rgba(255,255,255,.18)',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:String(level)}));
        stochThresholdsAdded = true;
      }
      const last=rows.at(-1); stochPane.querySelector('[data-last-time]').textContent=last ? `Last closed ${new Date(last.confirmed_at*1000).toISOString().slice(0,16)}Z` : 'Unavailable';
    }
    if(showOi){
      const rows=(data.open_interest||[]);
      oiSeries.setData(rows.map(r => r.value == null ? {time:Number(r.time)} : {time:Number(r.time),value:Number(r.value)}));
      const last=[...rows].reverse().find(r=>r.value!=null);
      oiPane.querySelector('[data-last-time]').textContent=last ? `Observed ${new Date(last.time*1000).toISOString().slice(0,16)}Z · Value ${last.value} · Δ1H ${last.change_1h ?? 'unavailable'}` : 'Unavailable';
    }
    const alignPanesToPrice = () => {
      const main=window.SSChartResearchHost&&window.SSChartResearchHost.chart();
      const range=main&&main.timeScale().getVisibleRange();if(!range)return;
      syncing=true;for(const target of [stochChart,oiChart])try{target.timeScale().setVisibleRange(range);}catch(error){void error;}syncing=false;
    };
    alignPanesToPrice();
    paneSyncTimer=setTimeout(alignPanesToPrice,0);
  }

  async function render(detail){
    state = detail;
    const active=activeKeys.some(key=>detail.overlays[key]);
    if(!active){ svg.innerHTML=''; plotPanes({}); return; }
    const key=`${detail.symbol}|${detail.timeframe}`;
    const seq=++request;
    try{
      let data=cache.get(key);
      if(!data){ data=await api(`/api/research-series?symbol=${encodeURIComponent(detail.symbol)}&tf=${encodeURIComponent(detail.timeframe)}`); cache.set(key,data); }
      if(seq!==request || !state || key!==`${state.symbol}|${state.timeframe}`) return;
      const counts={orderblocks:(data.order_blocks||[]).length,
        sequences:(data.structure_sequences||[]).length,
        divergence:(data.regular_divergence||[]).length+(data.hidden_divergence||[]).length,
        stochrsi:(data.stoch_rsi||[]).length,openinterest:(data.open_interest||[]).filter(r=>r.value!=null).length};
      window.SSResearchLayerCounts=counts;
      const signature=key+'|'+JSON.stringify(counts);
      if(signature!==countsSignature){ countsSignature=signature; dispatchEvent(new CustomEvent('ss:research-layer-counts')); }
      plotPrice(data); plotPanes(data);
    }catch(err){
      svg.innerHTML=''; window.SSResearchLayerCounts={orderblocks:0,sequences:0,divergence:0,stochrsi:0,openinterest:0};
      plotPanes({}); console.warn('research chart unavailable',err);
    }
  }
  addEventListener('ss:chart-research-state', event => render(event.detail));
})();
