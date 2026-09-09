/* global module */
/* Present existing closed-bar readings, never infer approval or calculate prices. */
function chartInsightMarkup(data){
  const esc = value => String(value ?? 'Not reported').replace(/[&<>"']/g,
    char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const labels = {UP:'Uptrend', DOWN:'Downtrend', CHOP:'Choppy', RANGE:'Range-bound',
    UNKNOWN:'Not enough evidence', NOT_RECORDED:'Not recorded',
    TREND_UP_ALIGNED:'Uptrend agrees with broader chart', TREND_DOWN_ALIGNED:'Downtrend agrees with broader chart',
    PULLBACK_IN_HTF_UP:'Pullback within a broader uptrend', PULLBACK_IN_HTF_DOWN:'Bounce within a broader downtrend',
    CONSOLIDATION_IN_HTF_UP:'Pausing within a broader uptrend', CONSOLIDATION_IN_HTF_DOWN:'Pausing within a broader downtrend',
    LTF_TREND_IN_HTF_RANGE:'Local trend; broader chart is sideways',
    TREND_UP_NO_HTF:'Uptrend; broader context unavailable', TREND_DOWN_NO_HTF:'Downtrend; broader context unavailable'};
  const words = value => labels[value] || (value ? String(value).toLowerCase().replaceAll('_', ' ') : 'Not reported');
  const dated = value => value == null ? 'Not available' : new Date(value * 1000).toLocaleString();
  const own = data.frames.find(frame => frame.timeframe === data.timeframe);
  const observation = data.usage.chart === 'OBSERVATION_ONLY';
  return `<div class="insight-heading"><span class="op-state">Current chart · ${esc(data.symbol)} · ${esc(data.timeframe)}</span>
    <h2>What the bot sees</h2><p>Closed candles only. Separate from a setup’s recorded decision.</p></div>
    <div class="insight-reading"><span>${own?.freshness === 'FRESH' ? 'Chart reading' : 'Current reading unavailable'}</span>
    <strong>${own?.freshness === 'FRESH' ? esc(words(own.read)) : esc(words(own?.freshness))}</strong>
    <small>${observation ? 'Observation only' : 'Policy dependent — review recorded setup'}</small></div>
    <details class="insight-frames" open><summary>Top-down context</summary>${data.frames.map(frame => `<div class="insight-frame">
      <b>${esc(frame.timeframe)}</b><span>${frame.freshness === 'FRESH' ? esc(words(frame.read)) : esc(words(frame.freshness))}</span>
      <small>${esc(frame.lookback_bars)} / ${esc(frame.target_bars)} bars · ${frame.freshness === 'FRESH' ? esc(words(frame.top_down_call)) : 'No current direction'}</small>
      </div>`).join('')}</details>
    <dl class="insight-facts"><div><dt>Last closed candle</dt><dd>${esc(dated(own?.last_closed_at))}</dd></div>
    <div><dt>Window begins</dt><dd>${esc(dated(own?.window_start))}</dd></div>
    <div><dt>Used by trading rules</dt><dd>Structural regime: ${own?.freshness === 'FRESH' ? esc(words(own.trading_regime)) : 'current reading unavailable'}</dd></div>
    <div><dt>Higher-timeframe alignment</dt><dd>${data.usage.higher_timeframes === 'OBSERVATION_ONLY' ? 'Observation only' : 'Policy dependent — review recorded setup'}</dd></div>
    <div><dt>Scanner data quality</dt><dd>${esc(words(data.scanner_quality.status))} · ${esc(dated(data.scanner_quality.observed_at))}</dd></div></dl>
    <p class="t-note">${esc(data.notice)} Quality is the scanner’s last recorded verdict; fresh candles alone do not mean clean data.</p>`;
}
if(typeof module !== 'undefined') module.exports = {chartInsightMarkup};
if(typeof window !== 'undefined') (() => {
  const root = document.getElementById('chartInsight');
  if(!root || !window.SSData) return;
  let unsubscribe = null, activeKey = null, generation = 0;
  function connect(){
    const context = window.SSChartCtx || {};
    const active = document.body.dataset.route === 'trade' &&
      (!window.SSMarkets || window.SSMarkets.current() === 'crypto');
    const key = active && context.symbol && context.tf ? `${context.symbol}|${context.tf}` : '';
    if(key === activeKey) return;
    activeKey = key;
    const request = ++generation;
    if(unsubscribe) unsubscribe();
    unsubscribe = null;
    root.innerHTML = '<div class="insight-heading"><h2>What the bot sees</h2><p>Select a chart to read its context.</p></div>';
    if(!key) return;
    root.innerHTML = '<div class="insight-heading"><h2>What the bot sees</h2><p>Reading this chart…</p></div>';
    unsubscribe = SSData.subscribe(`/api/chart-insight?symbol=${encodeURIComponent(context.symbol)}&tf=${encodeURIComponent(context.tf)}`, (data, err) => {
      // A response for a market we left must never label the new chart.
      if(request !== generation || key !== activeKey) return;
      if(err || !data){
        root.innerHTML = '<div class="insight-heading"><h2>Chart context unavailable</h2><p>Could not read the backend. Retrying automatically; no current direction is shown.</p></div>';
        return;
      }
      if(data.symbol !== context.symbol || data.timeframe !== context.tf) return;
      root.innerHTML = chartInsightMarkup(data);
    }, 60000);
  }
  ['ss:chart-context','ss:route-change','ss:market-change','hashchange'].forEach(name => addEventListener(name, connect));
  connect();
})();
