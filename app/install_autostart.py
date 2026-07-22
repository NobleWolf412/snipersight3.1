"""Install/remove SniperSight autostart at Windows logon.

Writes a silent launcher (.vbs) into the user's Startup folder that runs the
watchdog headless (pythonw). No admin rights required; fully reversible.

  python install_autostart.py            install
  python install_autostart.py --remove   uninstall
  python install_autostart.py --status   check
"""
import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
STARTUP = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
LAUNCHER = STARTUP / "SniperSight.vbs"


def pythonw() -> Path:
    pw = Path(sys.executable).with_name("pythonw.exe")
    return pw if pw.exists() else Path(sys.executable)


def install():
    watchdog = APP / "watchdog.py"
    vbs = (f'CreateObject("Wscript.Shell").Run '
           f'"""{pythonw()}"" ""{watchdog}""", 0, False\n')
    LAUNCHER.write_text(vbs, encoding="utf-8")
    print(f"installed: {LAUNCHER}")
    print("SniperSight watchdog will start silently at every logon.")
    print("Remove anytime with: python install_autostart.py --remove")


def remove():
    if LAUNCHER.exists():
        LAUNCHER.unlink()
        print(f"removed: {LAUNCHER}")
    else:
        print("not installed")


def status():
    print(f"{'INSTALLED' if LAUNCHER.exists() else 'not installed'}: {LAUNCHER}")


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove()
    elif "--status" in sys.argv:
        status()
    else:
        install()
