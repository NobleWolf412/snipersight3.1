"""Official-feed parsing and fail-visible caching, entirely offline."""
import inspect
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from engine import macro_calendar as mc

FED = '''<h4>2026 FOMC Meetings</h4>
<div class="fomc-meeting__month col-xs-5"><strong>January</strong></div>
<div class="fomc-meeting__date col-xs-4">27-28</div>
<div class="fomc-meeting--shaded fomc-meeting__month">September</div>
<div class="fomc-meeting__date">15-16*</div>
<h4>2027 FOMC Meetings</h4>
<div class="fomc-meeting__month">Jan/Feb</div><div class="fomc-meeting__date">31-1</div>'''


def ics(start="20260911T083000", title="Consumer Price Index", extra=""):
    return ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:" + title +
            "\r\nDTSTART;TZID=America/New_York:" + start + "\r\n" + extra +
            "END:VEVENT\r\nEND:VCALENDAR")


NOW = int(datetime(2026, 9, 5, tzinfo=timezone.utc).timestamp())


class CalendarParsing(unittest.TestCase):
    def test_fed_years_ranges_and_dst_not_guessed_release_times(self):
        events = mc.parse_fed(FED)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["date_label"], "2026-01-27 to 2026-01-28")
        self.assertEqual(events[2]["date_label"], "2027-01-31 to 2027-02-01")
        self.assertEqual(datetime.fromtimestamp(events[0]["start_at"], timezone.utc).hour, 5)
        self.assertEqual(datetime.fromtimestamp(events[1]["start_at"], timezone.utc).hour, 4)
        self.assertEqual(events[1]["precision"], "DATE_RANGE")
        self.assertIn("time not supplied", events[1]["note"])

    def test_bls_daylight_saving_and_standard_time(self):
        for stamp, hour in [("20260714T083000", 12), ("20260113T083000", 13)]:
            with self.subTest(stamp=stamp):
                event = mc.parse_bls(ics(stamp))[0]
                self.assertEqual(datetime.fromtimestamp(event["start_at"], timezone.utc).hour, hour)
                self.assertEqual(event["precision"], "TIME")

    def test_utc_and_floating_times(self):
        self.assertEqual(mc._ical_time("DTSTART", "20260911T123000Z"),
                         mc._ical_time("DTSTART", "20260911T083000"))

    def test_folded_lines_cancelled_events_and_unsupported_recurrence(self):
        event = mc.parse_bls(ics(title="Consumer Price \r\n Index for August"))[0]
        self.assertEqual(event["category"], "INFLATION")
        for extra in ("STATUS:CANCELLED\r\n", "RRULE:FREQ=MONTHLY\r\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                mc.parse_bls(ics(extra=extra))

    def test_all_day_release_is_not_assigned_an_invented_clock_time(self):
        with self.assertRaises(ValueError):
            mc.parse_bls(ics("20260911"))

    def test_bad_or_changed_pages_fail_loudly(self):
        for parse in (mc.parse_fed, mc.parse_bls):
            with self.subTest(parse=parse), self.assertRaises(ValueError):
                parse("<html>Access Denied</html>")
        with self.assertRaises(ValueError):
            mc.parse_fed(FED.replace("September", "Unknownmonth"))


class CalendarCache(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.calls = []
        self.fail = set()

        def fetch(url):
            self.calls.append(url)
            if url in self.fail:
                raise RuntimeError("source unavailable")
            return FED if url == mc.FED_URL else ics()
        self.client = mc.CalendarClient(fetch=fetch, clock=lambda: self.now)

    def test_fixed_sources_cached_without_exposing_mutable_cache(self):
        report = self.client.current()
        self.assertEqual(report["status"], "AVAILABLE")
        self.assertEqual(report["version"], "macro-calendar-v0.1-draft")
        self.assertEqual(set(self.calls), {mc.FED_URL, mc.BLS_URL})
        report["events"][0]["title"] = "tampered"
        self.assertNotIn("tampered", str(self.client.current()))
        self.assertEqual(len(self.calls), 2)

    def test_bls_failure_is_partial_not_a_clear_calendar(self):
        self.fail.add(mc.BLS_URL)
        report = self.client.current()
        self.assertEqual(report["status"], "PARTIAL")
        bls = next(s for s in report["sources"] if s["source"] == "BLS")
        self.assertEqual(bls["status"], "UNAVAILABLE")
        self.assertIsNone(bls["observed_at"])
        self.assertTrue(bls["error"])
        self.assertTrue(report["informational_only"])
        self.assertIn("not mean a quiet calendar", report["caveat"])

    def test_failed_refresh_retains_original_age_then_becomes_stale(self):
        self.client.current()
        self.fail.update((mc.BLS_URL, mc.FED_URL))
        self.now += mc.REFRESH_SECONDS + 1
        report = self.client.current()
        self.assertTrue(all(s["status"] == "DEGRADED" for s in report["sources"]))
        self.assertTrue(all(s["observed_at"] == NOW for s in report["sources"]))
        self.now += mc.STALE_SECONDS
        report = self.client.current()
        self.assertTrue(all(s["status"] == "STALE" for s in report["sources"]))
        self.assertFalse(report["near_event"])

    def test_upcoming_and_active_meeting_dates_are_event_awareness_not_permissions(self):
        self.now = int(datetime(2026, 9, 15, 16, tzinfo=timezone.utc).timestamp())
        report = self.client.current()
        self.assertTrue(report["near_event"])
        self.assertIn("historical vintages", report["missing"])
        self.assertNotIn("evaluation_allowed", report)

    def test_exhausted_calendar_has_no_upcoming_coverage(self):
        self.now = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
        report = self.client.current()
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertTrue(all(s["status"] == "NO_UPCOMING_COVERAGE" for s in report["sources"]))

    def test_route_only_reads_the_calendar_not_the_book(self):
        import server
        with patch.object(mc, "current", return_value={"status": "PARTIAL"}) as current, \
             patch.object(server.store, "connect", side_effect=AssertionError("no book access")):
            self.assertEqual(server.macro_calendar_snapshot(), {"status": "PARTIAL"})
        current.assert_called_once_with()

    def test_trading_path_does_not_consume_the_calendar(self):
        from engine import setups, risk, execsim, autotrader
        for module in (setups, risk, execsim, autotrader):
            self.assertNotIn("macro_calendar", inspect.getsource(module))


if __name__ == "__main__":
    unittest.main()
