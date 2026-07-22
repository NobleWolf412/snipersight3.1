"""Watchdog — keeps the scanner and server alive. The forward paper record
is the project's most valuable asset; this process insures it.

- Supervises live.py and the API server; restarts either on exit with
  exponential backoff (5s -> 300s), reset after 60s of clean uptime.
- Toasts on scanner restarts (loud-fallback rule: silent recovery hides
  problems — you should know it crashed even though it self-healed).
- Single-instance guard via a lock socket on 127.0.0.1:8423.
- If an API server is already running externally (dev sessions), it is
  left alone rather than fought over.

Run: python watchdog.py            (console mode — used by start.bat)
     pythonw watchdog.py           (headless — used by boot autostart)
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
import urllib.request

APP = Path(__file__).resolve().parent
LOG = APP / "data" / "watchdog.log"
LOCK_PORT = 8423
SERVER_URL = "http://127.0.0.1:8422/api/status"


def log(msg: str):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def toast(title: str, msg: str):
    try:
        sys.path.insert(0, str(APP))
        import notify
        notify.toast(title, msg)
    except Exception:
        pass


def server_up() -> bool:
    try:
        urllib.request.urlopen(SERVER_URL, timeout=3)
        return True
    except Exception:
        return False


class Child:
    def __init__(self, name, args, notify_restart=False):
        self.name, self.args = name, args
        self.notify_restart = notify_restart
        self.proc = None
        self.started_at = 0.0
        self.backoff = 5

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        self.proc = subprocess.Popen(self.args, cwd=APP)
        self.started_at = time.monotonic()
        log(f"{self.name} started pid={self.proc.pid}")

    def tick(self):
        if self.alive():
            if time.monotonic() - self.started_at > 60:
                self.backoff = 5          # clean uptime resets backoff
            return
        if self.proc is not None:         # it died
            rc = self.proc.returncode
            log(f"{self.name} exited rc={rc} — restart in {self.backoff}s")
            if self.notify_restart:
                toast("⚠ SniperSight scanner restarted",
                      f"{self.name} exited (rc={rc}) — auto-recovered, check watchdog.log")
            time.sleep(self.backoff)
            self.backoff = min(self.backoff * 2, 300)
        self.start()


def main():
    # single-instance lock
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
        lock.listen(1)
    except OSError:
        log("another watchdog is already running — exiting")
        return

    py = sys.executable.replace("pythonw.exe", "python.exe")
    log("watchdog start")
    live = Child("live-scanner", [py, "-X", "utf8", "live.py"], notify_restart=True)
    server = Child("api-server", [py, "-m", "uvicorn", "server:app",
                                  "--port", "8422", "--host", "127.0.0.1"])
    external_server = server_up()
    if external_server:
        log("api-server already running externally — not supervising it")

    try:
        while True:
            live.tick()
            if not external_server:
                server.tick()
            elif not server_up():
                log("external api-server disappeared — taking over supervision")
                external_server = False
            time.sleep(10)
    finally:
        for c in (live, server):
            if c.alive():
                c.proc.terminate()
        log("watchdog stopped")


if __name__ == "__main__":
    main()
