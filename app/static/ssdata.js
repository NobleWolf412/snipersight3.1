/* SSData — one fetch, one cache, one number on screen.

   THE BUG THIS EXISTS TO KILL. shell.js, funnel.js, chart.js, weather.js,
   playbooks.js and wizard.js each fetched what they needed on their own timer.
   Five consumers for /api/overview, three for /api/portfolio, three for
   /api/setup-telemetry. Two panels on one screen were therefore reading two
   different moments, and that is not a theoretical hazard — it shipped:

     · Command reported "TRADEABLE NOW 18" and "18 symbols scanned" while
       Market Weather, on the same screen, reported "23 of 33 tradeable".
     · The risk panel listed KRAKEN PERP while the venue picker offered only
       Coinbase and Phemex.

   The universe-count bug had already been fixed ONCE — shell.js still carries
   the comment about three universe sizes on one screen and the rule that the
   engine owns the number. That fix corrected one call site. weather.js kept its
   own clock and derived its own count, so the CLASS survived. A per-site fix
   cannot retire a per-site bug.

   So: subscribe to a path and every subscriber is handed the SAME payload from
   the SAME response. Panels can still disagree about what a number MEANS; they
   can no longer disagree about what it IS.

   Also retires the idle request load. One scheduler, one timer, deduped
   in-flight requests, and nothing at all while the tab is in the background. */
(() => {
  'use strict';

  const entries = new Map();          // path -> Entry
  const TICK = 1000;                  // scheduler granularity

  function entry(path) {
    let e = entries.get(path);
    if (!e) {
      e = {path, data: undefined, err: null, at: 0, inflight: null,
           subs: new Set(), everyMs: 0, nextAt: 0};
      entries.set(path, e);
    }
    return e;
  }

  function emit(e) {
    // A subscriber that throws must not stop the others from being told.
    for (const fn of e.subs) {
      try { fn(e.data, e.err); }
      catch (err) { console.error('[ssdata] subscriber threw for ' + e.path, err); }
    }
  }

  /* One request per path in flight, ever. Concurrent callers share the promise
     rather than racing — which is what makes "five consumers" cost one GET. */
  function fetchNow(path) {
    const e = entry(path);
    if (e.inflight) return e.inflight;
    e.inflight = (async () => {
      try {
        /* no-store, always. Every endpoint behind this layer reports a LIVE
           record, and a heuristically cached response would keep showing a
           stale win rate on a page whose entire claim is that its numbers are
           current. Freshness is this layer's decision to make, explicitly and
           per path — never the browser's to guess at. */
        const r = await fetch(path, {cache: 'no-store'});
        if (!r.ok) throw new Error(path + ' → ' + r.status);
        const d = await r.json();
        e.data = d; e.err = null; e.at = Date.now();
        return d;
      } catch (err) {
        /* Keep the last good payload. A panel showing data it can label as
           stale is more use than a panel that blanks itself — and the shell's
           health chip already reports staleness in words. */
        e.err = err; e.at = Date.now();
        throw err;
      } finally {
        e.inflight = null;
        e.nextAt = e.everyMs ? Date.now() + e.everyMs : 0;
        emit(e);
      }
    })();
    return e.inflight;
  }

  /* Read a path. Serves the cached payload when it is younger than maxAge, so
     several panels waking on the same tick share one response instead of
     issuing one request each and then disagreeing about the answer. */
  function get(path, maxAge) {
    const e = entry(path);
    const age = maxAge == null ? 2000 : maxAge;
    if (e.data !== undefined && !e.err && (Date.now() - e.at) < age) {
      return Promise.resolve(e.data);
    }
    return fetchNow(path);
  }

  /* Subscribe to a path, optionally asking that it be kept fresh every
     everyMs. The strictest interval any subscriber asks for wins, so a panel
     wanting 5s does not get starved by one that only needs 60s.

     Fires immediately with cached data when there is some, so a late-arriving
     subscriber paints from the same payload its neighbours are showing rather
     than triggering a fetch that would give it a different one. */
  function subscribe(path, fn, everyMs) {
    const e = entry(path);
    e.subs.add(fn);
    if (everyMs) {
      e.everyMs = e.everyMs ? Math.min(e.everyMs, everyMs) : everyMs;
      if (!e.nextAt) e.nextAt = Date.now() + e.everyMs;
    }
    if (e.data !== undefined || e.err) {
      try { fn(e.data, e.err); } catch (err) { console.error('[ssdata]', err); }
    } else {
      get(path).catch(() => { /* the emit in fetchNow already told the subscriber */ });
    }
    return () => {
      e.subs.delete(fn);
      if (!e.subs.size) { e.everyMs = 0; e.nextAt = 0; }   // stop polling for nobody
    };
  }

  // Force the next read to hit the network — for after a POST changes state.
  function invalidate(path) {
    if (path == null) { for (const e of entries.values()) e.at = 0; return; }
    for (const [k, e] of entries) if (k === path || k.startsWith(path + '?')) e.at = 0;
  }

  // Refetch now and push to subscribers. Used by Apply/Run Scan/Halt.
  function refresh(path) {
    invalidate(path);
    if (path != null) return fetchNow(path);
    return Promise.allSettled([...entries.keys()]
      .filter(k => entries.get(k).subs.size)
      .map(fetchNow));
  }

  /* ONE timer for the whole page. Nothing polls in a background tab: a hidden
     tab hitting a 1GB store on five separate clocks buys precisely nothing. */
  setInterval(() => {
    if (document.hidden) return;
    const now = Date.now();
    for (const e of entries.values()) {
      if (!e.everyMs || !e.subs.size || e.inflight) continue;
      if (e.nextAt && now >= e.nextAt) fetchNow(e.path).catch(() => {});
    }
  }, TICK);

  // Returning to a foregrounded tab should repaint from fresh data, not from
  // whatever was on screen when it was hidden.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    for (const e of entries.values()) if (e.everyMs && e.subs.size) fetchNow(e.path).catch(() => {});
  });

  window.SSData = {
    get, subscribe, invalidate, refresh,
    // introspection, for tests and for the request-rate work in the audit
    _stats: () => [...entries.values()].map(e =>
      ({path: e.path, subs: e.subs.size, everyMs: e.everyMs, ageMs: e.at ? Date.now() - e.at : null})),
  };
})();
