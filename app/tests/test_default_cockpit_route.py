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
