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

    def test_verdict_funnel_and_reasons_are_all_present(self):
        """The operator asked for the verdict and the rejection reasons in ONE
        place, and that has not changed.

        The telemetry TABLE is no longer one of them. Stage counts and failure
        points are engine self-checks - the panel's own chip called them
        developer detail - and Copy report still carries them. What has to
        survive on this surface is the failure state, which is why #telChip is
        still asserted here: a panel may leave, a way of finding out that
        something is broken may not.
        """
        for anchor in ('id="dVerdict"', 'id="dFunnel"', 'id="dIssues"',
                       'id="dNotes"',
                       'id="telChip"', 'id="lossAutopsyPanel"',
                       'id="lossAutopsyRoot"'):
            self.assertIn(anchor, self.html, anchor)
        self.assertNotIn('id="dTelemetry"', self.html)

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

    def test_trade_autopsy_is_server_owned_and_read_only(self):
        self.assertIn("renderLossAutopsy(t.loss_autopsy)", self.js)
        start = self.js.index("function renderLossAutopsy")
        end = self.js.index("/* ---------- actions ----------", start)
        renderer = self.js[start:end]
        self.assertNotIn("fetch(", renderer)
        self.assertIn("WATCHLIST, NOT BLOCKS", renderer)


if __name__ == "__main__":
    unittest.main()
