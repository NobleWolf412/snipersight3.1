from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
STATIC = APP / "static"


class CockpitDiagnosticsIntegrationTests(unittest.TestCase):
    def test_launcher_opens_integrated_cockpit(self):
        launcher = (APP / "start.bat").read_text(encoding="utf-8")
        self.assertIn("/static/cockpit.html", launcher)

    def test_cockpit_contains_accessible_why_drawer(self):
        html = (STATIC / "cockpit.html").read_text(encoding="utf-8")
        self.assertIn('id="whyButton"', html)
        self.assertIn('aria-controls="whyDrawer"', html)
        self.assertIn('id="whyDrawer"', html)
        self.assertIn('/static/diagnostics.html?embed=1', html)
        self.assertIn('id="cockpit" src="/"', html)

    def test_drawer_reports_actionable_diagnostics(self):
        script = (STATIC / "cockpit.js").read_text(encoding="utf-8")
        self.assertIn("/api/setup-telemetry?limit=500", script)
        self.assertIn("/api/pipeline-health", script)
        self.assertIn("diagnosticDefects + blockers", script)
        self.assertIn("Ctrl+Shift+D", (STATIC / "cockpit.html").read_text(encoding="utf-8"))

    def test_embedded_diagnostics_remove_duplicate_header(self):
        html = (STATIC / "diagnostics.html").read_text(encoding="utf-8")
        css = (STATIC / "diagnostics.css").read_text(encoding="utf-8")
        self.assertIn("get('embed')==='1'", html)
        self.assertIn(".embed header{display:none}", css)


if __name__ == "__main__":
    unittest.main()
