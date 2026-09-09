"""Official event calendar, informational only; never a trading or macro bias gate.

Fixed public URLs, bounded reads and an in-memory six-hour cache. No fact/book
writes, credentials, model calls or background process. Failed sources retain
dated evidence but cannot establish that the calendar is clear. This is not a
historical-vintage store and must not be used in a backtest.
"""
from __future__ import annotations

import calendar
import copy
import html
import hashlib
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MACRO_CALENDAR_VERSION = "macro-calendar-v0.1-draft"
FED_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BLS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
REFRESH_SECONDS = 6 * 3600
STALE_SECONDS = 24 * 3600
HORIZON_SECONDS = 30 * 86400
MAX_BYTES = 2_000_000
ET = ZoneInfo("America/New_York")


def _utc(dt):
    return int(dt.timestamp())


def _clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value)).split())


def parse_fed(body: str) -> list[dict]:
    """Meeting DAYS from the Fed, not invented 2pm statement timestamps."""
    headings = list(re.finditer(r"(20\d{2}) FOMC Meetings", body))
    events = []
    months = {name.lower(): n for n in range(1, 13)
              for name in (calendar.month_name[n], calendar.month_abbr[n])}
    for i, heading in enumerate(headings):
        year = int(heading.group(1))
        section = body[heading.end():headings[i + 1].start() if i + 1 < len(headings) else len(body)]
        pairs = re.findall(
            r'<div[^>]*class="[^"]*\bfomc-meeting__month\b[^"]*"[^>]*>(.*?)</div>\s*'
            r'<div[^>]*class="[^"]*\bfomc-meeting__date\b[^"]*"[^>]*>(.*?)</div>',
            section, re.S)
        for month_text, days_text in pairs:
            names = _clean(month_text).lower().split("/")
            days = _clean(days_text).replace("*", "").strip()
            # Notation votes, emergency calls and unknown markup are not
            # silently converted into regularly scheduled decision meetings.
            if not re.fullmatch(r"\d{1,2}-\d{1,2}", days):
                continue
            if any(name not in months for name in names) or len(names) > 2:
                raise ValueError("unrecognized FOMC month")
            first, last = map(int, days.split("-"))
            start = datetime(year, months[names[0]], first, tzinfo=ET)
            finish = datetime(year, months[names[-1]], last, tzinfo=ET)
            if finish < start:
                raise ValueError("invalid FOMC date range")
            events.append({"id": f"fed-fomc-{finish.date()}", "title": "FOMC meeting",
                           "category": "MONETARY_POLICY", "start_at": _utc(start),
                           "end_at": _utc(finish + timedelta(days=1)),
                           "precision": "DATE_RANGE", "timezone": "America/New_York",
                           "date_label": f"{start.date()} to {finish.date()}",
                           "source": "FED", "source_url": FED_URL,
                           "note": "Meeting dates only; statement time not supplied. Schedule can change."})
    if not events:
        raise ValueError("no scheduled FOMC meetings parsed")
    return sorted({e["id"]: e for e in events}.values(), key=lambda e: e["start_at"])


def _ical_time(key, value):
    if "VALUE=DATE" in key or re.fullmatch(r"\d{8}", value):
        raise ValueError("a release needs a published time, not an all-day date")
    tz = re.search(r"TZID=([^;:]+)", key)
    zone = tz.group(1).strip('"') if tz else "America/New_York"
    aliases = {"US-Eastern": "America/New_York", "US/Eastern": "America/New_York",
               "Eastern Standard Time": "America/New_York"}
    # Floating BLS schedule times are Eastern, as documented on its calendar.
    fmt = "%Y%m%dT%H%M%S" if len(value.rstrip("Z")) == 15 else "%Y%m%dT%H%M"
    dt = datetime.strptime(value.rstrip("Z"), fmt)
    return _utc(dt.replace(tzinfo=timezone.utc if value.endswith("Z") else
                          ZoneInfo(aliases.get(zone, zone))))


def parse_bls(body: str) -> list[dict]:
    if "BEGIN:VCALENDAR" not in body or "END:VCALENDAR" not in body:
        raise ValueError("BLS did not return a complete calendar")
    unfolded = re.sub(r"\r?\n[ \t]", "", body)
    events = []
    for block in re.findall(r"BEGIN:VEVENT\s*(.*?)END:VEVENT", unfolded, re.S):
        props = {}
        for line in block.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                props[key.split(";", 1)[0]] = (key, value.strip())
        title = props.get("SUMMARY", ("", ""))[1]
        category = next((cat for text, cat in (
            ("Consumer Price Index", "INFLATION"), ("Producer Price Index", "INFLATION"),
            ("Employment Situation", "JOBS"), ("Job Openings and Labor Turnover", "JOBS"),
            ("Employment Cost Index", "WAGES")) if text.lower() in title.lower()), None)
        if not category or props.get("STATUS", ("", ""))[1] == "CANCELLED":
            continue
        if "RRULE" in props or "DTSTART" not in props:
            raise ValueError("unsupported recurrence or missing BLS release time")
        start = _ical_time(*props["DTSTART"])
        title = title.replace(r"\,", ",").replace(r"\n", " ").replace(r"\;", ";")[:240]
        tag = hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]
        events.append({"id": f"bls-{category}-{start}-{tag}", "title": title,
                       "category": category, "start_at": start, "end_at": start,
                       "precision": "TIME", "timezone": "America/New_York",
                       "source": "BLS", "source_url": BLS_URL,
                       "note": "Scheduled release only; actual, consensus and surprise are not supplied."})
    if not events:
        raise ValueError("no relevant BLS releases parsed")
    return sorted({e["id"]: e for e in events}.values(), key=lambda e: e["start_at"])


def _fetch(url):
    # No operator data is sent. URLs are constants, never request parameters.
    req = urllib.request.Request(url, headers={"User-Agent": "SniperSight-calendar/0.1"})
    with urllib.request.urlopen(req, timeout=5) as response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("calendar response exceeded size limit")
        return raw.decode("utf-8-sig")


class CalendarClient:
    def __init__(self, fetch=_fetch, clock=time.time):
        self.fetch, self.clock = fetch, clock
        self.records = {}
        self.next_refresh = 0
        self.lock = threading.Lock()

    def _load(self, source, url, parse):
        try:
            events = parse(self.fetch(url))
            return source, {"source": source, "source_url": url, "events": events,
                            "observed_at": int(self.clock()), "error": None}
        except Exception as exc:
            # Exceptions are visible, never a fabricated empty calendar.
            return source, {"source": source, "source_url": url,
                            "error": f"{type(exc).__name__}: {exc}"[:180]}

    def current(self):
        with self.lock:
            now = int(self.clock())
            if now >= self.next_refresh:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(self._load, *args) for args in
                               (("FED", FED_URL, parse_fed), ("BLS", BLS_URL, parse_bls))]
                    for future in futures:
                        source, result = future.result()
                        if result["error"] and source in self.records:
                            result = {**self.records[source], "error": result["error"]}
                        self.records[source] = result
                now = int(self.clock())
                self.next_refresh = now + REFRESH_SECONDS
            sources, events = [], []
            for source, record in self.records.items():
                observed = record.get("observed_at")
                age = now - observed if observed is not None else None
                relevant = [e for e in record.get("events", []) if e["end_at"] >= now]
                status = ("UNAVAILABLE" if age is None else "STALE" if age < 0 or age > STALE_SECONDS
                          else "DEGRADED" if record.get("error") else
                          "NO_UPCOMING_COVERAGE" if not relevant else "FRESH")
                sources.append({"source": source, "source_url": record["source_url"],
                                "status": status, "observed_at": observed,
                                "age_seconds": age, "error": record.get("error"),
                                "coverage_end_at": max((e["end_at"] for e in record.get("events", [])),
                                                       default=None)})
                events.extend({**e, "source_status": status, "observed_at": observed}
                              for e in relevant if e["start_at"] <= now + HORIZON_SECONDS)
            events.sort(key=lambda e: e["start_at"])
            fresh = sum(s["status"] == "FRESH" for s in sources)
            return copy.deepcopy({
                "version": MACRO_CALENDAR_VERSION, "as_of": now,
                "status": "AVAILABLE" if fresh == 2 else "PARTIAL" if fresh else "UNAVAILABLE",
                "scope": "US_SCHEDULED_EVENTS_ONLY", "informational_only": True,
                "sources": sources, "events": events, "next_refresh_at": self.next_refresh,
                "horizon_days": 30,
                "near_event": any(e["source_status"] == "FRESH" and
                                  e["start_at"] <= now + 86400 for e in events),
                "detail": "Scheduled events are not a directional macro model or trading permission.",
                "missing": ["release actuals and consensus", "rates and dollar context",
                            "cross-asset breadth", "unscheduled news", "historical vintages"],
                "caveat": "No listed event does not mean a quiet calendar. Check source coverage and freshness."})


CLIENT = CalendarClient()


def current():
    return CLIENT.current()
