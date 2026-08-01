"""S23: the cockpit wrapper was deleted — one page serves the app AND its
diagnostics drawer. These guard that consolidation from regressing."""
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


class ConsolidatedCockpitTests(unittest.TestCase):
    def test_no_wrapper_files_remain(self):
        for gone in ("cockpit_server.py", "static/cockpit.html", "static/cockpit.js"):
            self.assertFalse((APP / gone).exists(), f"{gone} should have been removed")

    def test_watchdog_and_launcher_target_the_single_app(self):
        watchdog = (APP / "watchdog.py").read_text(encoding="utf-8")
        start = (APP / "start.bat").read_text(encoding="utf-8")
        self.assertIn('"server:app"', watchdog)
        self.assertNotIn("cockpit_server", watchdog)
        self.assertIn("http://localhost:8422", start)

    def test_raw_route_redirects_instead_of_serving_a_second_view(self):
        src = (APP / "server.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/raw", include_in_schema=False)', src)
        self.assertIn("RedirectResponse", src)

    def test_no_iframe_embeds_the_app_in_itself(self):
        html = (APP / "static" / "shell.html").read_text(encoding="utf-8")
        self.assertNotIn('src="/raw"', html)
        self.assertNotIn('id="cockpit"', html)

    def test_legacy_ui_is_fully_retired(self):
        """A second UI over the same facts is a second place for them to
        disagree — which is how two equity numbers diverged on 2026-07-26."""
        self.assertFalse((APP / "static" / "index.html").exists())
        src = (APP / "server.py").read_text(encoding="utf-8")
        self.assertNotIn('@app.get("/legacy"', src)


if __name__ == "__main__":
    unittest.main()


class VersionStampedShellTests(unittest.TestCase):
    """The ?v=N cache busters in shell.html were HAND-MAINTAINED — thirteen
    tags bumped by whoever remembered. One stale module against twelve fresh
    ones does not error, it disagrees, which is the class of bug this codebase
    keeps paying to remove. The route is the authority now: every tag served
    from / carries one version derived from the newest static mtime."""

    def test_every_served_tag_carries_one_version(self):
        import re
        import server
        html = server.index().body.decode("utf-8")
        stamped = set(re.findall(r"\?v=(\d+)", html))
        self.assertEqual(len(stamped), 1,
                         f"served tags disagree: {sorted(stamped)} — the exact "
                         "stale-module hazard the stamping exists to remove")
        self.assertEqual(stamped, {server._asset_version()},
                         "the served version is not the asset version")

    def test_the_version_follows_the_files(self):
        import server
        v1 = server._asset_version()
        # The version is the MAX mtime, so nudging one file by a couple of
        # seconds proves nothing — another file is usually newer, and the first
        # draft of this test failed exactly that way. Push the file past
        # EVERYTHING by using wall-clock now plus a margin.
        target = next(p for p in (APP / "static").glob("*.js"))
        st = target.stat()
        try:
            import os
            import time
            os.utime(target, ns=(st.st_atime_ns,
                                 time.time_ns() + 10_000_000_000))
            self.assertNotEqual(server._asset_version(), v1,
                                "a changed file does not change the version, "
                                "so clients keep the stale module")
        finally:
            os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(server._asset_version(), v1,
                         "the version moved without a file changing")
