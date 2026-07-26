"""The restart endpoint must be a restart, never a kill switch."""
import socket
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server

APP = Path(__file__).resolve().parents[1]


class SystemRestartTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def test_refuses_when_no_supervisor_is_running(self):
        """Without the watchdog, stopping processes would leave the app down —
        so the endpoint must refuse rather than become a kill switch."""
        original = server._watchdog_alive
        server._watchdog_alive = lambda: False
        try:
            r = self.client.post("/api/system/restart?target=both")
            self.assertEqual(r.status_code, 409)
            self.assertIn("watchdog is not running", r.json()["detail"])
        finally:
            server._watchdog_alive = original

    def test_rejects_unknown_target(self):
        r = self.client.post("/api/system/restart?target=rm-rf")
        self.assertEqual(r.status_code, 422)

    def test_scanner_only_target_never_exits_this_process(self):
        """target=scanner must not schedule an exit of the API server."""
        original = server._watchdog_alive
        server._watchdog_alive = lambda: True
        try:
            r = self.client.post("/api/system/restart?target=scanner")
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertNotIn("api-server", " ".join(body["actions"]))
        finally:
            server._watchdog_alive = original

    def test_watchdog_liveness_probe_matches_lock_port(self):
        """The probe must key on the same lock port watchdog.py binds."""
        watchdog_src = (APP / "watchdog.py").read_text(encoding="utf-8")
        self.assertIn(f"LOCK_PORT = {server.WATCHDOG_LOCK_PORT}", watchdog_src)

    def test_probe_detects_a_held_lock(self):
        held = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            held.bind(("127.0.0.1", server.WATCHDOG_LOCK_PORT))
            held.listen(1)
        except OSError:
            self.skipTest("a real watchdog already holds the lock port")
        try:
            self.assertTrue(server._watchdog_alive())
        finally:
            held.close()


if __name__ == "__main__":
    unittest.main()
