"""The restart endpoint must be a restart, never a kill switch."""
import os
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
        """target=scanner must not schedule an exit of the API server.

        THIS TEST USED TO KILL THE OPERATOR'S LIVE SCANNER, and it did it every
        time the suite ran. It forced `_watchdog_alive` to True — which is the
        one guard stopping the endpoint proceeding — and then POSTed for real.
        The endpoint read the live heartbeat, found the running scanner's pid,
        and taskkilled it.

        That is the whole story behind 356 exits, all rc=1, all "NOT ended by
        this supervisor": rc=1 is what taskkill produces, TerminateProcess
        never runs atexit, and the supervisor was telling the exact truth —
        it had not ended them, the API server had, on this test's instruction.
        It explains the clustering during development, the erratic intervals,
        and the four-hour-forty-seven-minute quiet spell when nobody happened
        to run the suite. CLAUDE.md's rule — do not POST to write endpoints to
        test them — was written about arming trades; this is the same rule and
        the same cost.

        `_stop_pid` is stubbed now, which also makes the assertion stronger.
        Instead of reading the prose in the response and hoping "api-server"
        never appears in it for some other reason, it asserts on the pids the
        endpoint actually ASKED to stop: the scanner's, and nothing else.
        """
        original_alive, original_stop = server._watchdog_alive, server._stop_pid
        asked = []
        server._watchdog_alive = lambda: True
        server._stop_pid = lambda pid: (asked.append(pid), (True, f"stubbed {pid}"))[1]
        try:
            r = self.client.post("/api/system/restart?target=scanner")
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertNotIn("api-server", " ".join(body["actions"]),
                             "target=scanner scheduled an exit of this process")
            self.assertNotIn(os.getpid(), asked,
                             "target=scanner asked to stop the API server itself")
            self.assertLessEqual(len(asked), 1,
                                 f"target=scanner tried to stop {len(asked)} "
                                 f"processes: {asked}")
        finally:
            server._watchdog_alive = original_alive
            server._stop_pid = original_stop

    def test_no_test_in_this_file_can_reach_a_real_process(self):
        """The guarantee, not just this one call site.

        A future test that forces the watchdog probe true and forgets to stub
        the killer would silently start ending the operator's scanner again,
        and the symptom — a supervisor reporting deaths it did not cause —
        looks nothing like a test bug.
        """
        src = Path(__file__).read_text(encoding="utf-8")
        forced = src.count("_watchdog_alive = lambda: True")
        stubbed = src.count("_stop_pid = lambda")
        self.assertLessEqual(
            forced, stubbed,
            f"{forced} test(s) force the watchdog probe true but only "
            f"{stubbed} stub _stop_pid — the difference reaches taskkill and "
            f"a live process")

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
