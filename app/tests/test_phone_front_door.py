"""What has to stay true for the cockpit to be safe on a phone.

The app became reachable from a second device on 4 Aug 2026 (`tailscale serve`
puts https://<host>.<tailnet>.ts.net in front of the loopback socket). Two
things had to hold before that was sensible, and both are the kind that fail
silently:

  1. A page the operator merely VISITS must not be able to drive the API.
  2. The phone must be able to install the cockpit as an app.

Neither shows up as an error when it regresses. The first just quietly stops
refusing; the second just quietly stops offering to install.
"""
import json
import os
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server

STATIC = Path(__file__).resolve().parents[1] / "static"


class CrossSiteGuardTests(unittest.TestCase):
    """`Sec-Fetch-Site` is set by the browser and page script cannot forge it."""

    def setUp(self):
        self.client = TestClient(server.app)

    def test_a_cross_site_request_to_the_api_is_refused(self):
        r = self.client.get("/api/status", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("refused", r.json()["detail"])

    def test_same_site_is_refused_too(self):
        """A sibling host on the tailnet is not this app."""
        r = self.client.get("/api/status", headers={"Sec-Fetch-Site": "same-site"})
        self.assertEqual(r.status_code, 403)

    def test_the_app_itself_still_reaches_its_own_api(self):
        r = self.client.get("/api/status", headers={"Sec-Fetch-Site": "same-origin"})
        self.assertEqual(r.status_code, 200)

    def test_a_typed_address_or_bookmark_still_works(self):
        r = self.client.get("/api/status", headers={"Sec-Fetch-Site": "none"})
        self.assertEqual(r.status_code, 200)

    def test_non_browser_callers_are_untouched(self):
        """curl, the watchdog's health poll and this suite send no such header,
        and none of them is the case CSRF describes."""
        r = self.client.get("/api/status")
        self.assertEqual(r.status_code, 200)

    def test_the_guard_does_not_cover_the_shell_or_its_assets(self):
        """Only /api/* is guarded. Following a link to the cockpit from
        anywhere must still load the page."""
        r = self.client.get("/", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status_code, 200)

    def test_every_writing_endpoint_sits_behind_the_guard(self):
        """The guard is path-prefix based, so this is really a check that no
        write endpoint has been mounted OUTSIDE /api/ where it would be
        unprotected. Two of these are GETs: /api/manual/open and
        /api/manual/live call manual.run() and record fills."""
        writing = [r for r in server.app.routes
                   if getattr(r, "path", "").startswith("/api/")
                   and {"POST", "PUT", "PATCH", "DELETE"} & set(getattr(r, "methods", []) or [])]
        self.assertTrue(writing, "no write endpoints found — the scan is wrong")
        for route in server.app.routes:
            path = getattr(route, "path", "")
            methods = set(getattr(route, "methods", []) or [])
            if {"POST", "PUT", "PATCH", "DELETE"} & methods:
                self.assertTrue(
                    path.startswith("/api/"),
                    f"{path} writes but sits outside /api/, so the cross-site "
                    f"guard does not cover it")


class TailnetIdentityTests(unittest.TestCase):
    """The login. There is no password, and that is the stronger choice.

    `tailscale serve` sets Tailscale-User-Login from the authenticated tailnet
    identity and OVERWRITES any the caller sent — measured 4 Aug 2026, a
    request carrying a forged `attacker@evil.example` arrived at the app with
    the real address substituted. So the header is Tailscale's assertion, not
    the caller's claim, and a second secret would only add something to phish,
    forget and leak.

    These tests spell the header out because the whole design rests on it: if
    a future proxy change stopped overwriting it, every one of these would
    still pass while the gate had become decorative. The forgery-resistance
    itself cannot be tested from in here — it is a property of the proxy, and
    it is recorded in the commit and in _gate's docstring.
    """

    def setUp(self):
        self.client = TestClient(server.app)
        self._env = os.environ.get("SNIPERSIGHT_ALLOWED_USERS")
        os.environ["SNIPERSIGHT_ALLOWED_USERS"] = "operator@example.com"

    def tearDown(self):
        if self._env is None:
            os.environ.pop("SNIPERSIGHT_ALLOWED_USERS", None)
        else:
            os.environ["SNIPERSIGHT_ALLOWED_USERS"] = self._env

    @staticmethod
    def _proxied(login=None):
        """What `tailscale serve` puts on a request it forwards."""
        h = {"X-Forwarded-For": "100.99.215.76", "X-Forwarded-Proto": "https"}
        if login:
            h["Tailscale-User-Login"] = login
        return h

    def test_this_machine_is_not_gated(self):
        """No proxy headers means nothing forwarded it, so it came from here.
        The desktop cockpit, the watchdog's health poll and these suites all
        arrive this way, and anything running here already has the database."""
        self.assertEqual(self.client.get("/api/status").status_code, 200)

    def test_a_permitted_tailnet_user_is_let_in(self):
        r = self.client.get("/api/status", headers=self._proxied("operator@example.com"))
        self.assertEqual(r.status_code, 200)

    def test_the_match_ignores_case(self):
        r = self.client.get("/api/status", headers=self._proxied("Operator@Example.COM"))
        self.assertEqual(r.status_code, 200)

    def test_an_unknown_tailnet_user_is_refused(self):
        r = self.client.get("/api/status", headers=self._proxied("someone@else.example"))
        self.assertEqual(r.status_code, 403)
        self.assertIn("not permitted", r.json()["detail"])

    def test_a_proxied_request_with_no_identity_is_refused(self):
        """This is what a Tailscale *Funnel* request looks like — the public
        internet. Enabling Funnel by accident must fail closed rather than
        publish the operator's book."""
        r = self.client.get("/api/status", headers=self._proxied())
        self.assertEqual(r.status_code, 403)
        self.assertIn("Funnel", r.json()["detail"])

    def test_an_empty_allowlist_refuses_every_remote_device(self):
        os.environ["SNIPERSIGHT_ALLOWED_USERS"] = ""
        r = self.client.get("/api/status", headers=self._proxied("operator@example.com"))
        self.assertEqual(r.status_code, 403)
        self.assertIn("No operator is configured", r.json()["detail"])

    def test_an_empty_allowlist_still_leaves_this_machine_working(self):
        """The failure mode has to be 'the phone stops', never 'the desk
        stops' — the desk is where it gets fixed."""
        os.environ["SNIPERSIGHT_ALLOWED_USERS"] = ""
        self.assertEqual(self.client.get("/api/status").status_code, 200)

    def test_the_gate_covers_the_page_not_only_the_api(self):
        """Letting an unlisted device load the shell and then 403 every panel
        renders an empty cockpit, which reads as 'broken app' rather than
        'you are not on the list'."""
        r = self.client.get("/", headers=self._proxied("someone@else.example"))
        self.assertEqual(r.status_code, 403)
        self.assertIn("NOT PERMITTED", r.text)
        self.assertIn("text/html", r.headers["content-type"])

    def test_a_refusal_to_the_api_stays_json(self):
        r = self.client.get("/api/status", headers=self._proxied("someone@else.example"))
        self.assertIn("application/json", r.headers["content-type"])

    def test_revoking_access_needs_no_restart(self):
        """Read per request, deliberately: access should end when the operator
        saves the file, not when they next remember to restart."""
        allow = self._proxied("operator@example.com")
        self.assertEqual(self.client.get("/api/status", headers=allow).status_code, 200)
        os.environ["SNIPERSIGHT_ALLOWED_USERS"] = "somebody@else.example"
        self.assertEqual(self.client.get("/api/status", headers=allow).status_code, 403)

    def test_whoami_reports_which_path_the_caller_came_in_on(self):
        """A gate whose output nobody can see is a gate nobody notices has
        stopped working."""
        local = self.client.get("/api/whoami").json()
        self.assertFalse(local["checked"])
        self.assertEqual(local["via"], "this machine")

        remote = self.client.get("/api/whoami",
                                 headers=self._proxied("operator@example.com")).json()
        self.assertTrue(remote["checked"])
        self.assertEqual(remote["via"], "tailnet")
        self.assertEqual(remote["identity"], "operator@example.com")


class BaselineResetTests(unittest.TestCase):
    """The one endpoint whose effect cannot be undone from the app.

    Nothing here ever sends confirm=true — these assert the REFUSALS. A test
    that actually reset the baseline would scope the operator's wallet,
    positions and performance to a new window.
    """

    def setUp(self):
        self.client = TestClient(server.app)

    def test_a_form_post_cannot_reach_the_handler(self):
        """The second lock, behind the guard: a plain HTML form cannot produce
        a body FastAPI will parse as JSON, so it dies at validation. This must
        hold even if the browser ever stops sending Sec-Fetch-Site."""
        r = self.client.post("/api/baseline/reset", data={"confirm": "true"})
        self.assertEqual(r.status_code, 422)

    def test_a_json_body_without_confirmation_is_refused(self):
        r = self.client.post("/api/baseline/reset", json={})
        self.assertEqual(r.status_code, 400)
        self.assertIn("confirm", r.json()["detail"])


class FactsWindowTests(unittest.TestCase):
    """/api/facts had no limit clause of any kind.

    It returned every fact ever written for a symbol and timeframe, forever,
    into a chart that draws 1500 bars and discards the rest. Measured 4 Aug
    2026 for BTCUSDT: a full 1H chart load moved 2.47MB, of which 1.59MB was
    for bars that were not on screen. On loopback that is invisible; on a phone
    it is most of the page weight, and it grows with the store.

    `bars` bounds the answer to a window of BARS, computed from the candle
    table — not to a count of facts, which would cut a different depth for
    every kind and leave the swings reaching further back than the moving
    averages beneath them.
    """

    def setUp(self):
        self.client = TestClient(server.app)

    def test_the_default_is_still_unbounded(self):
        """Changing the default would silently truncate every existing caller.
        The bound is opt-in and the header says so."""
        r = self.client.get("/api/facts?kind=swing&symbol=BTCUSDT&tf=1H")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("X-Facts-Window"), "unbounded")

    def test_a_windowed_request_says_what_it_dropped(self):
        """No silent caps. A caller that asked for a window it did not get has
        to be able to find out without counting rows and guessing."""
        r = self.client.get("/api/facts?kind=swing&symbol=BTCUSDT&tf=1H&bars=1500")
        self.assertEqual(r.status_code, 200)
        window = r.headers.get("X-Facts-Window", "")
        self.assertIn("bars=1500", window)
        self.assertIn("kept=", window)
        self.assertIn("older_dropped=", window)

    def test_the_window_never_returns_more_than_unbounded(self):
        full = self.client.get("/api/facts?kind=swing&symbol=BTCUSDT&tf=1H").json()
        win = self.client.get("/api/facts?kind=swing&symbol=BTCUSDT&tf=1H&bars=1500").json()
        self.assertLessEqual(len(win), len(full))

    def test_the_window_keeps_the_RECENT_end(self):
        """The end of the chart the operator is looking at, and the end that
        bears on the next decision."""
        full = self.client.get("/api/facts?kind=ma&symbol=BTCUSDT&tf=1H").json()
        win = self.client.get("/api/facts?kind=ma&symbol=BTCUSDT&tf=1H&bars=1500").json()
        if not full or not win or len(win) == len(full):
            self.skipTest("this store holds no history older than 1500 bars here")
        self.assertEqual(win[-1]["market_time"], full[-1]["market_time"],
                         "the newest fact was dropped — the window cut the "
                         "wrong end")
        self.assertGreater(win[0]["market_time"], full[0]["market_time"])

    def test_the_chart_asks_for_the_same_window_it_draws(self):
        """Two numbers for 'how much chart is there' would drift, and the
        symptom would be markers drawn from evidence off the left edge."""
        chart = (STATIC / "chart.js").read_text(encoding="utf-8")
        self.assertIn("const BARS = 1500", chart)
        self.assertIn("limit=${BARS}", chart)
        self.assertIn("bars=${BARS}", chart)


class OnePollForOnePayloadTests(unittest.TestCase):
    def test_setup_telemetry_is_asked_for_one_way_only(self):
        """shell.js asked limit=200 and funnel.js limit=500. There are far
        fewer than 200 records, so both came back byte-identical — measured at
        128,073 bytes each — and SSData caches on the URL, so it could not tell
        they were the same answer. Two cache entries, two downloads, every
        poll."""
        import re
        limits = set()
        for name in ("shell.js", "funnel.js", "wizard.js", "diagnostics.js"):
            src = (STATIC / name).read_text(encoding="utf-8")
            limits.update(re.findall(r"setup-telemetry\?limit=(\d+)", src))
        self.assertEqual(len(limits), 1,
                         f"setup-telemetry is requested with differing limits "
                         f"{sorted(limits)}, so one payload is fetched and "
                         f"cached more than once")


class InstallableOnAPhoneTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_the_manifest_is_served_from_the_root_with_its_own_media_type(self):
        """Chrome will not treat it as a manifest under a generic type, and
        StaticFiles guesses from the extension — which Windows does not always
        register for .webmanifest."""
        r = self.client.get("/manifest.webmanifest")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"].split(";")[0],
                         "application/manifest+json")

    def test_the_manifest_declares_what_android_requires_to_install(self):
        m = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(m["display"], "standalone")
        self.assertEqual(m["start_url"], "/")
        self.assertEqual(m["scope"], "/")
        sizes = {i["sizes"] for i in m["icons"]}
        self.assertIn("192x192", sizes, "Android needs a 192px icon to install")
        self.assertIn("512x512", sizes, "Android needs a 512px icon to install")
        self.assertTrue(any(i.get("purpose") == "maskable" for i in m["icons"]),
                        "without a maskable icon the launcher crops the wordmark")

    def test_every_icon_the_manifest_promises_actually_exists(self):
        m = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
        for icon in m["icons"]:
            r = self.client.get(icon["src"])
            self.assertEqual(r.status_code, 200, f"{icon['src']} is missing")

    def test_the_shell_links_the_manifest(self):
        """Pinned against the text of the file, per the JS-suite convention:
        a manifest nothing links to is a manifest the phone never reads."""
        html = (STATIC / "shell.html").read_text(encoding="utf-8")
        self.assertIn('rel="manifest"', html)
        self.assertIn("/manifest.webmanifest", html)

    def test_the_favicon_is_not_the_full_wordmark(self):
        """It was the 1080x410 logo — 349KB, drawn 26px tall, the heaviest
        single asset on the page and pure cost on cellular."""
        html = (STATIC / "shell.html").read_text(encoding="utf-8")
        self.assertNotIn('rel="icon" href="/static/assets/snipersight-logo.png"', html)

    def test_no_service_worker_is_registered(self):
        """Deliberate, and this test is the record of the decision.

        The only thing a worker could usefully cache is /static/*, which is
        exactly what _NoCacheStatic exists to prevent — a cached cockpit.js
        against a fresh cockpit.html once bound a DOM id that no longer
        existed and silently killed a drawer. A worker would reintroduce that
        persistently, on a device with no devtools. Chrome has not required
        one to install since v108.

        If a worker is ever added, it must never intercept /api/: two GET
        handlers there call manual.run() and write fills.
        """
        for name in ("shell.html", "shell.js"):
            text = (STATIC / name).read_text(encoding="utf-8")
            self.assertNotIn("serviceWorker", text,
                             f"{name} registers a service worker — read this "
                             f"test's docstring before removing the assertion")


if __name__ == "__main__":
    unittest.main()
