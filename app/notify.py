"""Windows toast notifications — no third-party modules, pure PowerShell WinRT.

Falls back to console output if the toast pipeline fails (e.g. non-Windows).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

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

    SNIPERSIGHT_NO_TOAST=1 turns the whole path into a no-op — correct for a
    headless run, where a desktop notification has nobody to notify, and the
    switch that made the failure above bisectable in the first place.
    """
    import os
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
