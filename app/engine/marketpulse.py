"""Public, dated headlines. Advisory context, never an input to admission."""
import calendar
import copy
import html
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import feedparser

from . import macro_calendar

SOURCES = {"Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
           "SEC": "https://www.sec.gov/news/pressreleases.rss"}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "SniperSight market-context reader"})
    with urllib.request.urlopen(request, timeout=6) as response:
        data = response.read(1_000_001)
    if len(data) > 1_000_000:
        raise ValueError("Feed exceeds size limit")
    return data


class PulseClient:
    def __init__(self, fetcher=fetch, clock=time.time):
        self.fetcher, self.clock = fetcher, clock
        self.records, self.next_refresh = {}, 0
        self.lock = threading.Lock()

    def _load(self, source, url):
        try:
            parsed = feedparser.parse(self.fetcher(url))
            if not parsed.entries:
                raise ValueError("No readable feed entries")
            items = []
            for entry in parsed.entries[:20]:
                link = entry.get('link', '')
                if urlparse(link).scheme not in ('https', 'http'):
                    continue
                stamp = entry.get('published_parsed') or entry.get('updated_parsed')
                items.append({"title": html.unescape(re.sub('<[^>]+>', '', entry.get('title', 'Untitled')))[:300],
                              "url": link, "published_at": calendar.timegm(stamp) if stamp else None,
                              "source": source})
            return source, {"items": items, "observed_at": int(self.clock()), "error": None}
        except Exception as exc:
            return source, {"error": str(exc)[:180]}

    def current(self):
        with self.lock:
            now = int(self.clock())
            if now >= self.next_refresh:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(self._load, name, url) for name, url in SOURCES.items()]
                    for future in futures:
                        source, result = future.result()
                        self.records[source] = {**self.records.get(source, {}), **result}
                now = int(self.clock())
                self.next_refresh = now + 900
            sources, items = [], []
            for source, row in self.records.items():
                observed = row.get('observed_at')
                status = ('UNAVAILABLE' if observed is None or not 0 <= now-observed <= 86400 else
                          'DELAYED' if row.get('error') else 'FRESH')
                sources.append(dict(source=source, url=SOURCES[source], status=status,
                                    observed_at=observed, error=row.get('error')))
                items.extend({**i, "status": status, "historical": status == 'UNAVAILABLE'} for i in row.get('items', []))
            items.sort(key=lambda i: i['published_at'] or 0, reverse=True)
            return copy.deepcopy({"sources": sources, "items": items[:12], "as_of": now,
                "next_refresh_at": self.next_refresh, "advisory_only": True,
                "note": "Selected official releases, not a complete news service. Missing coverage never means an all-clear."})


CLIENT = PulseClient()


def current():
    result = CLIENT.current()
    result['calendar'] = macro_calendar.current()
    return result
