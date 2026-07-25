import unittest
from pathlib import Path


APP = Path(__file__).resolve().parents[1]


class DefaultCockpitRouteTests(unittest.TestCase):
    def test_integrated_cockpit_is_default_server_entry(self):
        wrapper = (APP / "cockpit_server.py").read_text(encoding="utf-8")
        watchdog = (APP / "watchdog.py").read_text(encoding="utf-8")
        start = (APP / "start.bat").read_text(encoding="utf-8")

        self.assertIn('@app.get("/", include_in_schema=False)', wrapper)
        self.assertIn('@app.get("/raw", include_in_schema=False)', wrapper)
        self.assertIn('app.mount("/", core_app)', wrapper)
        self.assertIn('"cockpit_server:app"', watchdog)
        self.assertIn('http://localhost:8422', start)

    def test_integrated_shell_embeds_raw_route_without_recursion(self):
        html = (APP / "static" / "cockpit.html").read_text(encoding="utf-8")

        self.assertIn('id="whyButton"', html)
        self.assertIn('src="/raw"', html)
        self.assertIn('href="/raw"', html)
        self.assertNotIn('id="cockpit" src="/"', html)


if __name__ == "__main__":
    unittest.main()
