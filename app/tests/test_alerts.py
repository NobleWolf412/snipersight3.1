"""Alerts, and the two ways they have historically gone wrong.

They killed the scanner. Notification work in the scan loop took it down 191
times: 254s to death with toasts on, against 1055s and 13 clean cycles with them
off. So the scanner decides and the watchdog sends, and `enqueue` is the seam —
it must touch no socket and spawn no process.

And they fired at history. Announcing on row-newness toasted 87 backfilled
setups in a single cycle, the most recent dated 2025-01. The risk engine replays
the whole book on every run, and one halted day produced eight kill-switch
records whose P&L differed between them — so an event key built from a number
the engines re-derive turns every replay into a fresh alarm.

Everything here runs against a scratch queue. Nothing sends.
"""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import notify


class QueueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._db, self._cfg = notify.QUEUE_DB, notify.CONFIG
        notify.QUEUE_DB = Path(self.tmp.name) / "notifications.db"
        notify.CONFIG = Path(self.tmp.name) / "alerts.json"

    def tearDown(self):
        notify.QUEUE_DB, notify.CONFIG = self._db, self._cfg
        try:
            self.tmp.cleanup()
        except OSError:
            pass          # windows holds the sqlite file briefly; harmless


class EnqueueIsCheapAndIdempotent(QueueCase):
    def test_the_same_event_queues_once(self):
        self.assertTrue(notify.enqueue("k", "t", "m"))
        self.assertFalse(notify.enqueue("k", "t", "m"),
                         "a replayed fact queued a second notification")

    def test_a_replayed_kill_switch_does_not_re_alarm(self):
        """The real shape of the bug: same day, same baseline, different P&L
        because the engine re-derived it. The key must not carry the money."""
        for pnl in ("-412.10", "-398.77", "-401.02"):
            notify.enqueue("killswitch|6|2026-07-31",
                           "⛔ Daily loss limit — trading halted",
                           f"equity {pnl}")
        self.assertEqual(self._pending(), 1,
                         "the kill switch alarmed once per replay")

    def test_distinct_days_are_distinct_events(self):
        notify.enqueue("killswitch|6|2026-07-31", "t", "m")
        notify.enqueue("killswitch|6|2026-08-01", "t", "m")
        self.assertEqual(self._pending(), 2)

    def test_enqueue_never_raises_at_the_caller(self):
        """It is called from the scan loop. A notification must never be able
        to take down the thing it is notifying about — the founding rule of
        this module, and the one it has actually broken before."""
        notify.QUEUE_DB = Path("Z:/nonexistent/cannot/write/notifications.db")
        self.assertFalse(notify.enqueue("k", "t", "m"))

    def _pending(self):
        con = notify._queue()
        try:
            return con.execute(
                "SELECT COUNT(*) FROM notifications WHERE sent_at IS NULL").fetchone()[0]
        finally:
            con.close()


class TheScannerMustNotSend(QueueCase):
    def test_enqueue_opens_no_socket_and_spawns_nothing(self):
        """Pinned by substitution rather than by reading the source: anything
        that reaches urlopen or subprocess from this path fails here."""
        import subprocess
        import urllib.request
        calls = []

        real_run, real_popen = subprocess.run, subprocess.Popen
        real_open = urllib.request.urlopen
        subprocess.run = lambda *a, **k: calls.append("subprocess.run")
        subprocess.Popen = lambda *a, **k: calls.append("subprocess.Popen")
        urllib.request.urlopen = lambda *a, **k: calls.append("urlopen")
        try:
            notify.enqueue("k", "t", "m")
        finally:
            subprocess.run, subprocess.Popen = real_run, real_popen
            urllib.request.urlopen = real_open
        self.assertEqual(calls, [],
                         f"enqueue reached {calls} — that is the path that "
                         f"killed the scanner")


class TheToastFlagGatesOnlyTheToast(QueueCase):
    """SNIPERSIGHT_NO_TOAST=1 is set on the scanner by the supervisor.

    Hoisted into the shared entry point it would silence every destination in
    the process that generates most of the alerts, and ship an alert system
    that is mute on day one while looking like a delivery bug.
    """

    def test_the_flag_does_not_stop_an_event_being_recorded(self):
        old = os.environ.get("SNIPERSIGHT_NO_TOAST")
        os.environ["SNIPERSIGHT_NO_TOAST"] = "1"
        try:
            self.assertTrue(notify.enqueue("k", "t", "m"),
                            "the no-toast flag swallowed the event itself")
        finally:
            if old is None:
                os.environ.pop("SNIPERSIGHT_NO_TOAST", None)
            else:
                os.environ["SNIPERSIGHT_NO_TOAST"] = old

    def test_the_flag_is_checked_in_the_toast_sink_only(self):
        src = Path(notify.__file__).read_text(encoding="utf-8")
        head, _, tail = src.partition("def toast(")
        self.assertNotIn("SNIPERSIGHT_NO_TOAST", head,
                         "the flag moved above the toast sink, which mutes "
                         "every destination in the scanner")


class RemoteDeliveryIsOffUntilAskedFor(QueueCase):
    """An alert carries the operator's symbol, direction and P&L. Sending that
    anywhere off this machine hands it to a third party, which is their
    decision and not a default to inherit."""

    def test_no_config_means_no_remote_sinks(self):
        self.assertEqual(notify.config(), {})
        self.assertEqual(notify.deliver_pending()["sinks"], 0)

    def test_a_configured_sink_is_used(self):
        notify.CONFIG.write_text(json.dumps(
            {"sinks": [{"type": "ntfy", "url": "https://example.invalid/t"}]}),
            encoding="utf-8")
        self.assertEqual(notify.deliver_pending()["sinks"], 1)

    def test_quiet_events_can_be_withheld_from_a_sink(self):
        """Drift runs 13-44 a day against 2-8 setups and is awareness-only.
        Three actionable alerts buried under thirty is the failure mode."""
        sink = {"type": "ntfy", "url": "https://example.invalid/t", "loud_only": True}
        self.assertEqual(notify._send_remote(sink, "t", "m", notify.QUIET),
                         "skipped (quiet)")

    def test_delivery_records_the_outcome_rather_than_raising(self):
        """An unreachable phone must not stop the local toast, and neither
        must stop the supervisor."""
        notify.CONFIG.write_text(json.dumps(
            {"sinks": [{"name": "phone", "type": "ntfy",
                        "url": "http://127.0.0.1:9/never"}]}), encoding="utf-8")
        notify.enqueue("k", "t", "m")
        out = notify.deliver_pending()
        self.assertEqual(out["sent"] + out["failed"], 1)
        con = notify._queue()
        try:
            row = con.execute(
                "SELECT sent_at, outcome FROM notifications WHERE event_key='k'").fetchone()
        finally:
            con.close()
        self.assertIsNotNone(row[0], "a failed send left the row to retry forever")
        self.assertIn("phone=", row[1])


class TheShadowBookIsNeverAnnounced(unittest.TestCase):
    def test_the_watchdog_reads_only_risk_and_the_operators_own_trades(self):
        """`exec` and `order` are the engine's simulation — 100-400 events a
        day for trades nobody placed. Alerting on those is a phone buzzing all
        day about a book that does not exist."""
        src = (Path(__file__).resolve().parents[1] / "watchdog.py").read_text(
            encoding="utf-8")
        self.assertIn("kind IN ('risk', 'manual_exec')", src)
        self.assertNotIn("'exec'", src.split("def alert_tick")[1].split("def main")[0])


if __name__ == "__main__":
    unittest.main()
