"""Diagnostics drawer contract — now hosted directly in the trading page (S23)."""
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1]
STATIC = APP / "static"


class DiagnosticsDrawerTests(unittest.TestCase):
    def setUp(self):
        self.html = (STATIC / "index.html").read_text(encoding="utf-8")

    def test_launcher_opens_the_app_origin(self):
        launcher = (APP / "start.bat").read_text(encoding="utf-8")
        self.assertIn("http://localhost:8422", launcher)
        self.assertIn("watchdog.py", launcher)

    def test_drawer_is_accessible_and_named(self):
        self.assertIn('id="diagButton"', self.html)
        self.assertIn('aria-controls="diagDrawer"', self.html)
        self.assertIn('id="diagDrawer"', self.html)
        # the control names what it opens; ">WHY?<" was a question with no object
        self.assertIn(">DIAGNOSTICS<", self.html)
        self.assertNotIn(">WHY?<", self.html)

    def test_panel_is_lazy_loaded_on_first_open(self):
        """The trading view must not pay for the diagnostics panel at startup."""
        self.assertIn('data-src="/static/diagnostics.html?embed=1', self.html)
        self.assertIn("frame.src=frame.dataset.src", self.html)

    def test_keyboard_affordances_present(self):
        self.assertIn("Ctrl+Shift+D", self.html)
        self.assertIn("'Escape'", self.html)

    def test_badge_counts_actionable_defects(self):
        self.assertIn("/api/setup-telemetry?limit=500", self.html)
        self.assertIn("/api/pipeline-health", self.html)
        self.assertIn("defect_count", self.html)

    def test_embedded_diagnostics_remove_duplicate_header(self):
        html = (STATIC / "diagnostics.html").read_text(encoding="utf-8")
        css = (STATIC / "diagnostics.css").read_text(encoding="utf-8")
        self.assertIn("get('embed')==='1'", html)
        self.assertIn(".embed header{display:none}", css)

    def test_diagnostics_link_home_does_not_nest(self):
        html = (STATIC / "diagnostics.html").read_text(encoding="utf-8")
        self.assertIn('href="/" target="_top"', html)
        self.assertNotIn('href="/static/cockpit.html"', html)


if __name__ == "__main__":
    unittest.main()
