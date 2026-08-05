"""Alerts: one entry point, several destinations, and a queue between them.

WHY A QUEUE AND NOT A FUNCTION CALL.

Two constraints pull in opposite directions.

The scanner is the only place that knows a setup is worth announcing. Its gate
in `live.py` filters on the active baseline and on how late the setup is, and
without it a notifier fires years of backfilled history — that is not
hypothetical, it toasted 87 historical setups in one cycle on 2026-07-29, the
most recent of them dated 2025-01.

And the scanner is the one place that must not do the sending. Notification
work from the scan loop killed it, repeatedly and measurably: 254s to death
with toasts on, against 1055s and 13 clean cycles with them off. The cause is
recorded below — a shared console delivering an uncatchable kill — and two
rounds of process-isolation flags did not fully settle it.

So the scanner DECIDES and the watchdog SENDS. `enqueue()` writes a row and
returns; `deliver_pending()` runs on the watchdog's own tick and does the
network I/O. The scan loop never waits on a socket, and the alert still
inherits the gate that makes it trustworthy.

DEDUPLICATION IS THE PRIMARY KEY. The risk engine replays the whole book on
every run, so one halted day in July produced eight kill-switch records with
differing P&L. The event key must therefore be built from what IDENTIFIES the
event — symbol, day, baseline — and never from a figure that varies across
re-derivation. Insert-or-ignore then does the rest: a replayed fact meets a row
that already exists and nothing is sent.

THE QUEUE IS NOT IN THE FACT STORE, deliberately. "I told the operator about
this" is bookkeeping about a notification, not a fact about the market, and the
fact store is append-only, content-hashed and versioned for evidence. Its own
file keeps a delivery retry from ever looking like a research record.

REMOTE DELIVERY IS OFF UNTIL CONFIGURED. Sending trade alerts anywhere off this
machine publishes the operator's positions to a third party; that is their
decision to make, not a default to inherit. With no config file the only sink
is the local toast, and everything else is recorded and waits.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent
QUEUE_DB = APP / "data" / "notifications.db"
CONFIG = APP / "data" / "alerts.json"

#: Priorities. `loud` is what the operator acts on — a setup fired, the kill
#: switch tripped, their own trade closed: about three a day. `quiet` is
#: awareness — drift, onboarding, restarts — which runs 13-44 a day and lands
#: in every hour including overnight. Burying three actionable alerts under
#: thirty unactionable ones is the failure this exists to avoid, so a sink can
#: subscribe to loud only.
LOUD = "loud"
QUIET = "quiet"

PS_TEMPLATE = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xmlText = @'
<toast scenario="reminder"><visual><binding template="ToastText02">
<text id="1">__TITLE__</text><text id="2">__MSG__</text>
</binding></visual></toast>
'@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($xmlText)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("SniperSight").Show($toast)
"""


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("'", "&apos;").replace('"', "&quot;"))


# A notification must never be able to take down the thing it is notifying about.
#
# It could, and it did. The live scanner exited 191 times with rc=1 and no
# traceback, and the cause was this function. Measured, with only this variable
# changed and every other fix already in place:
#
#   toasts on  — 254s, dead, last log line sitting on a toast call site
#   toasts off — 1055s and 13 completed cycles, still running
#
# The exit forensics in live.py showed TerminateProcess, and the supervisor's
# own attribution said NOT ended by this supervisor. Something else was killing
# it, and the something else was the console.
#
# subprocess spawned PowerShell into the CALLER'S console, because that is what
# Windows does by default. Every process sharing a console also shares its
# control events, so a Ctrl-C, a Ctrl-Break, or a console teardown reaching that
# short-lived PowerShell reached the scanner sitting in the same console — and
# a console control event is delivered as an uncatchable kill, which is exactly
# the signature the forensics recorded.
#
# CREATE_NO_WINDOW gives the child its own hidden console instead of borrowing
# ours. The toast still appears; the blast radius does not include the caller.
#
# CREATE_NEW_PROCESS_GROUP added after that was not sufficient. With the console
# fix in place the scanner still died at toast sites — a drift alert at 05:47:45
# after 35 minutes, an onboard before that — so the deaths track TOASTS rather
# than startup, and CREATE_NO_WINDOW alone had not severed whatever reaches back.
# A new process group is what actually stops console control events being
# delivered across the boundary: GenerateConsoleCtrlEvent is scoped to a group,
# so a child in its own group cannot pass one back to us and we cannot send one
# to it. Belt and braces, on a path where the failure is an uncatchable kill and
# the cost of over-isolating a notification is nil.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


def toast(title: str, msg: str) -> bool:
    """Show a Windows toast. Returns whether the toast pipeline reported success.

    SNIPERSIGHT_NO_TOAST=1 turns THIS SINK into a no-op — correct for a
    headless run, where a desktop notification has nobody to notify, and the
    switch that made the failure above bisectable in the first place.

    The flag is checked here and nowhere higher up, and that placement is the
    whole point. Moved into the shared entry point it would silence every
    destination in the scanner — which runs with the flag set — and ship an
    alert system that is mute on day one and looks like a delivery bug.
    """
    if os.environ.get("SNIPERSIGHT_NO_TOAST") == "1":
        return False
    script = (PS_TEMPLATE
              .replace("__TITLE__", _xml_escape(title))
              .replace("__MSG__", _xml_escape(msg)))
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                         encoding="utf-8-sig") as f:
            f.write(script)
            path = f.name
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
            capture_output=True, timeout=15, **kwargs)
        return r.returncode == 0
    except Exception:
        # NOT print(): under pythonw sys.stdout is None, and a notification
        # failing is not a reason for the caller to hear about it twice.
        return False
    finally:
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass          # a leftover temp file is not worth an exception


# ─────────────────────────────────────────────────────────── the queue ──

def _queue():
    QUEUE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(QUEUE_DB, timeout=5)
    con.execute("""CREATE TABLE IF NOT EXISTS notifications(
        event_key TEXT PRIMARY KEY,
        queued_at INTEGER NOT NULL,
        priority  TEXT NOT NULL,
        title     TEXT NOT NULL,
        msg       TEXT NOT NULL,
        sent_at   INTEGER,
        outcome   TEXT)""")
    con.commit()
    return con


def enqueue(event_key: str, title: str, msg: str, priority: str = LOUD) -> bool:
    """Record that something happened. Returns True if this is the first time.

    Cheap and local: one INSERT OR IGNORE against a small SQLite file. Safe to
    call from the scan loop precisely because it touches no socket and spawns
    no process — the two things that have killed the scanner.

    `event_key` must identify the EVENT and nothing else. Include the symbol,
    the day and the baseline; never a P&L figure or anything else the engines
    re-derive, or a replay will look like a new event and buzz again.
    """
    try:
        con = _queue()
        try:
            cur = con.execute(
                "INSERT OR IGNORE INTO notifications"
                "(event_key, queued_at, priority, title, msg) VALUES (?,?,?,?,?)",
                (event_key, int(time.time()), priority, title, msg))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()
    except Exception:
        # A notification must never be able to take down its caller. That is
        # the founding rule of this module and it applies to its own storage.
        return False


def config() -> dict:
    """Remote destinations, or {} when the operator has not set any up.

    Absent file means local toast only. That default is deliberate: an alert
    carries the operator's symbol, direction and P&L, and sending it anywhere
    off this machine hands that to a third party. Opting in is their call.
    """
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _post(url: str, body: str, headers: dict, timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, data=body.encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return f"http {r.status}"


def _send_remote(sink: dict, title: str, msg: str, priority: str) -> str:
    """One remote destination. Returns a short outcome string for the record.

    Two shapes cover what a solo operator actually reaches for: `ntfy` (POST
    the text, topic in the URL) and `webhook` (POST JSON). Telegram is a
    webhook with a URL that already carries the token, so it needs no case of
    its own.
    """
    kind = str(sink.get("type") or "webhook").lower()
    url = str(sink.get("url") or "")
    if not url:
        return "no url"
    if sink.get("loud_only") and priority != LOUD:
        return "skipped (quiet)"
    if kind == "ntfy":
        return _post(url, f"{title}\n{msg}",
                     {"Title": title.encode("ascii", "ignore").decode() or "SniperSight",
                      "Priority": "high" if priority == LOUD else "low",
                      "Content-Type": "text/plain; charset=utf-8"})
    return _post(url, json.dumps({"title": title, "message": msg,
                                  "priority": priority}),
                 {"Content-Type": "application/json"})


#: How many alerts one tick may deliver. Small on purpose — see the burst
#: described on `toast_enabled` below. A backlog drains over several ticks
#: instead of all at once, and the queue is durable, so nothing is lost.
DELIVER_PER_TICK = 3


def toast_enabled() -> bool:
    """Whether the Windows toast sink runs. OFF unless explicitly turned on.

    MEASURED, 2026-08-05, and the reason this default is what it is.

    Moving delivery out of the scanner and into the watchdog was supposed to
    make toasts safe: the scanner had died 191 times at toast call sites, and
    the supervisor is not doing delicate work. On the first live run the
    watchdog drained a backlog of 14 and spawned 14 PowerShell processes in a
    few seconds. Within 25 seconds the scanner exited rc=1 twice with no
    traceback — `NOT ended by this supervisor`, the same signature as before —
    and the api-server followed. The stack went quiet again the moment the
    queue emptied.

    So the hazard was never "the scanner spawns PowerShell". It is that
    spawning PowerShell at all, from a process supervising others, reaches
    those others. CREATE_NO_WINDOW and CREATE_NEW_PROCESS_GROUP were already
    in place for both rounds of this; they are not sufficient.

    That is survivable for a desktop nicety and unacceptable for the thing it
    was built for. Phone delivery is an HTTP POST — no console, no child
    process, none of this failure mode — so the remote sink is the path that
    actually carries the alerts, and the toast is opt-in for anyone who wants
    it back and has read this.
    """
    return bool(config().get("toast", False))


def deliver_pending(limit: int = DELIVER_PER_TICK, log=None) -> dict:
    """Send what is queued. Call this from the WATCHDOG tick, never the scanner.

    Every send is attempted independently and a failure marks the row rather
    than raising — an unreachable phone must not stop the other sinks, and
    none of them must stop the supervisor. Rows are marked sent even when every
    sink failed, with the reason recorded: retrying forever means a phone that
    comes back online after a night buzzes for a night of events, which is
    worse than missing them.
    """
    out = {"sent": 0, "failed": 0, "sinks": len(config().get("sinks") or [])}
    try:
        con = _queue()
    except Exception:
        return out
    try:
        rows = con.execute(
            "SELECT event_key, priority, title, msg FROM notifications "
            "WHERE sent_at IS NULL ORDER BY queued_at LIMIT ?", (limit,)).fetchall()
        for key, priority, title, msg in rows:
            outcomes = []
            if toast_enabled():
                try:
                    outcomes.append("toast=" + ("ok" if toast(title, msg) else "no"))
                except Exception as exc:
                    outcomes.append(f"toast=error({type(exc).__name__})")
            else:
                outcomes.append("toast=off")
            for sink in (config().get("sinks") or []):
                name = sink.get("name") or sink.get("type") or "remote"
                try:
                    outcomes.append(f"{name}=" + _send_remote(sink, title, msg, priority))
                except Exception as exc:
                    outcomes.append(f"{name}=error({type(exc).__name__})")
            verdict = ", ".join(outcomes)
            # "off" is not a delivery. With no sink configured every alert is
            # correctly reported as undelivered, which is the honest reading:
            # it was recorded and nobody was told.
            ok = any("=ok" in o or "=http 2" in o for o in outcomes)
            out["sent" if ok else "failed"] += 1
            con.execute("UPDATE notifications SET sent_at=?, outcome=? "
                        "WHERE event_key=?", (int(time.time()), verdict, key))
            # A degraded path must never degrade silently.
            if log and not ok:
                log(f"alert not delivered: {title} | {verdict}")
        con.commit()
    except Exception:
        pass
    finally:
        con.close()
    return out


def heartbeat(log=None) -> str:
    """Tell an OUTSIDE service this machine is still alive.

    A heartbeat emitted by the watchdog cannot report the watchdog's own death,
    and its log records eight starts against one clean stop. The check that
    matters is therefore one the operator's phone hears about when it STOPS —
    a scheduled ping to a service that alarms on absence. Configured or
    skipped; there is no local fallback, because a local fallback would be the
    same machine vouching for itself again.
    """
    url = str(config().get("heartbeat_url") or "")
    if not url:
        return "not configured"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return f"http {r.status}"
    except Exception as exc:
        if log:
            log(f"heartbeat failed: {type(exc).__name__}")
        return f"error({type(exc).__name__})"


def event(event_key: str, title: str, msg: str, priority: str = LOUD,
          deliver: bool = False, log=None) -> bool:
    """Queue an alert, and optionally send it now.

    `deliver=False` is the default and is what the scanner uses: record it and
    let the watchdog do the talking. `deliver=True` is for callers that already
    ARE the watchdog.
    """
    fresh = enqueue(event_key, title, msg, priority)
    if fresh and deliver:
        deliver_pending(log=log)
    return fresh
