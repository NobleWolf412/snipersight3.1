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
import re
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

    def test_ntfy_sends_the_title_once_with_its_symbol(self):
        """The header form sends Title: in an HTTP header, and headers are
        ASCII — so the one glyph that distinguishes a kill switch from a setup
        at a glance was stripped, and putting the title in the body to
        compensate made the phone show it twice. JSON publish carries UTF-8 and
        keeps the fields apart."""
        sent = {}
        real = notify._post
        notify._post = lambda url, body, headers, timeout=8.0: (
            sent.update(url=url, body=json.loads(body), headers=headers), "http 200")[1]
        try:
            notify._send_remote({"type": "ntfy", "url": "https://ntfy.sh/mytopic"},
                                "⛔ Daily loss limit", "equity 9321.15", notify.LOUD)
        finally:
            notify._post = real
        self.assertEqual(sent["body"]["topic"], "mytopic")
        self.assertEqual(sent["body"]["title"], "⛔ Daily loss limit",
                         "the symbol was stripped from the title again")
        self.assertEqual(sent["body"]["message"], "equity 9321.15")
        self.assertNotIn(sent["body"]["title"], sent["body"]["message"],
                         "the title is repeated inside the body")
        self.assertIn("json", sent["headers"]["Content-Type"])

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


class TheToastSinkIsOffUntilAskedFor(QueueCase):
    """Measured 2026-08-05, on the first live run of this system.

    Moving delivery out of the scanner and into the watchdog was supposed to
    make toasts safe. The watchdog drained a backlog of 14 and spawned 14
    PowerShell processes in a few seconds; within 25 seconds the scanner exited
    rc=1 twice with no traceback — `NOT ended by this supervisor`, the same
    signature as the 191 deaths before it — and the api-server followed. The
    stack went quiet the moment the queue emptied.

    So the hazard was never "the SCANNER spawns PowerShell". It is that
    spawning PowerShell at all, from a process that supervises others, reaches
    those others. CREATE_NO_WINDOW and CREATE_NEW_PROCESS_GROUP were already in
    place for both rounds; they are not sufficient.

    Phone delivery is an HTTP POST and has none of this failure mode, so it is
    the path that carries the alerts and the toast is opt-in.
    """

    def test_no_toast_is_spawned_by_default(self):
        import subprocess
        calls = []
        real = subprocess.run
        subprocess.run = lambda *a, **k: calls.append("spawn")
        try:
            notify.enqueue("k", "t", "m")
            notify.deliver_pending()
        finally:
            subprocess.run = real
        self.assertEqual(calls, [],
                         "the watchdog spawned a process to deliver an alert — "
                         "that is what took the scanner and the server down")

    def test_it_can_be_turned_back_on_deliberately(self):
        notify.CONFIG.write_text(json.dumps({"toast": True}), encoding="utf-8")
        self.assertTrue(notify.toast_enabled())

    def test_an_undelivered_alert_is_not_reported_as_sent(self):
        """With the toast off and no remote sink, nobody was told. Saying
        otherwise would be the silent-degradation this codebase forbids."""
        notify.enqueue("k", "t", "m")
        out = notify.deliver_pending()
        self.assertEqual(out["sent"], 0)
        self.assertEqual(out["failed"], 1)

    def test_a_backlog_drains_over_several_ticks(self):
        """14 at once is what caused the kill. The queue is durable, so a small
        per-tick limit loses nothing and bounds the burst."""
        self.assertLessEqual(notify.DELIVER_PER_TICK, 5)
        for i in range(10):
            notify.enqueue(f"k{i}", "t", "m")
        first = notify.deliver_pending()
        self.assertEqual(first["sent"] + first["failed"], notify.DELIVER_PER_TICK)


class TheSupervisorNeverSpawnsToAnnounce(unittest.TestCase):
    """The restart loop, and why it ran for 356 exits.

    watchdog.toast() called notify.toast(), which spawns PowerShell. One of its
    three call sites fires on EVERY scanner restart, so:

        scanner dies -> watchdog announces it -> PowerShell spawns -> the spawn
        reaches the supervisor's children and kills the new scanner -> watchdog
        announces it -> ...

    Self-sustaining. The evidence it left: 356 scanner exits, every one rc=1 and
    `NOT ended by this supervisor`, against 176 starts in live-exit.log with
    ZERO exit notes — no atexit, no signal handler, no faulthandler dump. The
    process never ran Python on the way out, which is an uncatchable console
    control event, the same mechanism notify.py documents for the original 191
    deaths. It also explains the quiet spells: nothing to announce, nothing
    spawns, and it runs for hours.

    The supervisor queues now. Delivery is somebody else's tick, and the sink
    that spawns is off by default.
    """

    def test_the_watchdog_does_not_call_the_spawning_sink(self):
        src = (Path(__file__).resolve().parents[1] / "watchdog.py").read_text(
            encoding="utf-8")
        # Mentions inside comments and docstrings are the record of WHY; a call
        # is the defect. Strip both, then look for the call.
        code = re.sub(r'"""[\s\S]*?"""', "", src)
        code = "\n".join(l for l in code.splitlines()
                         if not l.strip().startswith("#"))
        offenders = [i + 1 for i, l in enumerate(code.splitlines())
                     if "notify.toast(" in l]
        # a bare boolean, not assertNotIn: the container here is the whole
        # supervisor and dumping it buries the one line that matters
        self.assertFalse(
            offenders,
            f"watchdog.py calls notify.toast() at line(s) {offenders} — the "
            f"supervisor is spawning PowerShell to announce something again, "
            f"which is the restart loop this test exists to keep closed")

    def test_the_restart_announcement_is_keyed_per_death(self):
        """Not per tick. A supervisor in a bad patch must report a restart
        once, or the announcement becomes its own source of restarts."""
        src = (Path(__file__).resolve().parents[1] / "watchdog.py").read_text(
            encoding="utf-8")
        self.assertIn('key=f"restart|{self.name}|{self.proc.pid}"', src)


class TheHeartbeatAssertsTheStack(unittest.TestCase):
    """Silence is the signal, so the ping must mean more than "I am running".

    The supervisor is the one component whose survival proves the least — its
    entire job is to outlive the others. A heartbeat sent merely because the
    watchdog loop is executing would tell an outside monitor "all good" while
    the scanner had been dark for an hour, which is the exact hour the operator
    needed to hear about.
    """

    def test_the_ping_is_withheld_when_the_scanner_is_dark(self):
        src = (Path(__file__).resolve().parents[1] / "watchdog.py").read_text(
            encoding="utf-8")
        body = src.split("def alert_tick")[1].split("\ndef main")[0]
        self.assertIn("if scanner_dark:", body,
                      "the heartbeat no longer checks whether the scanner is alive")
        # and the check has to come BEFORE the send, not decorate it afterwards
        self.assertLess(body.index("if scanner_dark:"), body.index("notify.heartbeat("),
                        "the heartbeat fires before the dark check is consulted")

    def test_an_unreadable_heartbeat_file_does_not_claim_health(self):
        """A monitor that cannot read its input must not declare either
        verdict — and specifically must not tell the outside world it is fine.
        `scanner_dark` starts False, so this pins that the unreadable path is
        reached only after the flag exists."""
        src = (Path(__file__).resolve().parents[1] / "watchdog.py").read_text(
            encoding="utf-8")
        body = src.split("def alert_tick")[1].split("\ndef main")[0]
        self.assertLess(body.index("scanner_dark = False"),
                        body.index("heartbeat.json"),
                        "scanner_dark is not initialised before the file is read")


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
