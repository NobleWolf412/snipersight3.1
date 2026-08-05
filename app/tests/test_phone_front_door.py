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
