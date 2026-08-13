"""Diagnostics contract — now a first-class surface in the shell (phase 1/6).

Replaces the legacy drawer tests: /legacy was retired 2026-07-29 and its
diagnostics moved into the shell's DIAGNOSTICS surface. The properties being
guarded are the same — the operator can always reach the verdict, the funnel,
and the telemetry that explains why nothing fired.
"""
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1]
STATIC = APP / "static"


class DiagnosticsSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.html = (STATIC / "shell.html").read_text(encoding="utf-8")
        self.js = (STATIC / "shell.js").read_text(encoding="utf-8")

    def test_launcher_opens_the_app_origin(self):
        launcher = (APP / "start.bat").read_text(encoding="utf-8")
        self.assertIn("http://localhost:8422", launcher)
        self.assertIn("watchdog.py", launcher)

    def test_diagnostics_is_a_navigable_surface(self):
        self.assertIn('data-s="diagnostics"', self.html)
        self.assertIn('id="s-diagnostics"', self.html)

    def test_verdict_funnel_and_telemetry_are_all_present(self):
        """The operator asked for telemetry and rejection reasons in ONE place."""
        for anchor in ('id="dVerdict"', 'id="dFunnel"', 'id="dIssues"',
                       'id="dNotes"',
                       'id="dTelemetry"'):
            self.assertIn(anchor, self.html, anchor)

    def test_refresh_is_read_only_and_reachable(self):
        self.assertIn('id="btnAudit"', self.html)
        self.assertIn('id="btnAudit" style="margin-left:auto">Refresh', self.html)
        start = self.js.index("$('btnAudit').addEventListener")
        end = self.js.index("$('btnCopyDiag').addEventListener", start)
        handler = self.js[start:end]
        self.assertIn("loadHealth()", handler)
        self.assertNotIn("/api/action", handler,
                         "a Diagnostics refresh must not create a second "
                         "pipeline verdict in the API process")

    def test_blocker_count_is_surfaced_in_the_nav(self):
        self.assertIn('id="nDiag"', self.html)


if __name__ == "__main__":
    unittest.main()
