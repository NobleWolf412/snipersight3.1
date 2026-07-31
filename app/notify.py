"""Windows toast notifications — no third-party modules, pure PowerShell WinRT.

Falls back to console output if the toast pipeline fails (e.g. non-Windows).
"""
import subprocess
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


def toast(title: str, msg: str) -> bool:
    """Show a Windows toast. Returns whether the toast pipeline reported success.

    SNIPERSIGHT_NO_TOAST=1 turns the whole path into a no-op. Every toast spawns
    a PowerShell process, and the scanner's two most frequent death sites sit
    directly on a toast call, so being able to take this path out of the picture
    without editing three call sites is what makes that testable at all. It is
    also the right switch for a headless run, where a desktop notification has
    nobody to notify.
    """
    import os
    if os.environ.get("SNIPERSIGHT_NO_TOAST") == "1":
        return False
    script = (PS_TEMPLATE
              .replace("__TITLE__", _xml_escape(title))
              .replace("__MSG__", _xml_escape(msg)))
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                         encoding="utf-8-sig") as f:
            f.write(script)
            path = f.name
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
            capture_output=True, timeout=15)
        Path(path).unlink(missing_ok=True)
        return r.returncode == 0
    except Exception:
        print(f"[TOAST-FALLBACK] {title}: {msg}")
        return False
