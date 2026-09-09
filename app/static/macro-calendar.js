/* Official event awareness. No price arithmetic, permissions or trade actions. */
(() => {
  'use strict';
  const sources = {
    FED: 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',
    BLS: 'https://www.bls.gov/help/hlpical.htm',
  };
  const headline = document.getElementById('macroHeadline');
  const detail = document.getElementById('macroDetails');
  if(!headline || !detail) return;
  let busy = false, lastRead = 0;
  const stamp = ts => new Date(ts * 1000).toLocaleString([], {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  });
  const calendarDates = value => String(value || '').split(' to ').map(day =>
    new Date(day + 'T12:00:00Z').toLocaleDateString([], {
      month: 'short', day: 'numeric', timeZone: 'UTC',
    })).join(' – ');
  function row(text, className){
    const el = document.createElement('p');
    el.textContent = text;
    if(className) el.className = className;
    detail.appendChild(el);
    return el;
  }
  function eventText(event){
    return event.precision === 'DATE_RANGE'
      ? `${event.title}: ${event.date_label} (New York dates; release time not supplied)`
      : `${event.title}: ${stamp(event.start_at)}`;
  }
  function render(data){
    detail.replaceChildren();
    const events = data.events || [];
    const next = events.find(event => event.source_status === 'FRESH');
    const coverage = data.status === 'AVAILABLE' ? 'Scheduled events only' : 'Calendar incomplete';
    const nextText = next && (next.precision === 'DATE_RANGE'
      ? `${next.title}: ${calendarDates(next.date_label)} (ET dates only)` : eventText(next));
    headline.textContent = `${data.near_event ? 'Event window nearby · ' : ''}${coverage}${next ? ' · ' + nextText : ' · No verified upcoming event in this view'}`;
    row('Informational only. Trade permissions and risk limits are unchanged.', 'macro-note');
    for(const source of data.sources || []){
      const labels = {FRESH: 'Current', UNAVAILABLE: 'Unavailable', STALE: 'Out of date',
        DEGRADED: 'Refresh failed', NO_UPCOMING_COVERAGE: 'No upcoming coverage'};
      const p = row(`${source.source === 'FED' ? 'Federal Reserve' : source.source}: ${labels[source.status] || source.status}${source.observed_at == null ? '' : ' · checked ' + stamp(source.observed_at)}`);
      if(sources[source.source]){
        const link = document.createElement('a');
        link.href = sources[source.source];
        link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.textContent = ' Official source'; p.appendChild(link);
      }
      if(source.error) row(source.error.includes('403')
        ? 'Source refused the calendar download (HTTP 403).' : source.error, 'macro-note');
    }
    for(const event of events.slice(0, 6)){
      row(`${eventText(event)}${event.source_status === 'FRESH' ? '' : ' · ' + event.source_status}`);
    }
    row(data.caveat || 'A missing event does not establish a quiet calendar.', 'macro-note');
  }
  async function refresh(){
    if(busy || document.hidden || Date.now() - lastRead < 300000) return;
    busy = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try{
      const response = await fetch('/api/macro-calendar', {signal: controller.signal});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
    }catch(err){
      headline.textContent = 'Calendar unavailable · do not assume there are no events';
      detail.replaceChildren();
      row(`Could not check the calendar: ${err.message}`, 'macro-note');
    }finally{
      clearTimeout(timer); busy = false; lastRead = Date.now();
    }
  }
  // Independent of the account/scanner polling: a slow provider cannot hold
  // the trading cockpit's first paint or health/exposure reads hostage.
  refresh();
  setInterval(refresh, 300000);
  document.addEventListener('visibilitychange', refresh);
})();
