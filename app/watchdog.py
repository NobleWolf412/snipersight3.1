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
AUDIT_INTERVAL_SEC = 60           # kill-switch audit cadence (SQLite read)


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


def audit_tick(state: dict, live_child: "Child", warmup: bool = False) -> dict:
    """Call quality.audit() and dispatch by Kill-Switch rung.

    HALT present or QUARANTINE count climbing vs prior tick → toast + restart
    live-scanner (the process that ingests). SERVE_FLAG → log summary. SERVE →
    silent clean. If the DB is not ready yet (fresh install / migration in
    flight) the tick is skipped without raising — but the cadence stamp
    (``at``) is still advanced so we don't audit every 10s on skip.

    ``warmup=True`` seeds prior counts on the first tick after boot so a
    non-zero QUARANTINE reading at startup is not misread as a climb from 0
    (Auditor FIND-2). HALT at warmup is still dispatched — a broken pipeline
    at boot is still a broken pipeline."""
    now_mono = time.monotonic()
    sys.path.insert(0, str(APP))
    try:
        from engine import store, quality
    except Exception as e:
        log(f"audit: import skip ({e})")
        return {**state, "at": now_mono}
    try:
        con = store.connect()
    except Exception as e:
        log(f"audit: db skip ({e})")
        return {**state, "at": now_mono}
    try:
        report = quality.audit(con)
    except Exception as e:
        log(f"audit: failed ({e})")
        return {**state, "at": now_mono}
    finally:
        con.close()

    worst = report.get("worst_rung", "SERVE")
    counts = report.get("rung_counts", {}) or {}
    prior = state.get("counts") or {}

    halt_now = counts.get("HALT", 0)
    quarantine_now = counts.get("QUARANTINE", 0)
    auto_disable_now = counts.get("AUTO_DISABLE", 0)
    serve_flag_now = counts.get("SERVE_FLAG", 0)

    reason = None
    if halt_now:
        reason = f"HALT ({halt_now} finding(s))"
    elif not warmup and quarantine_now > prior.get("QUARANTINE", 0):
        reason = (f"QUARANTINE climb "
                  f"{prior.get('QUARANTINE', 0)}->{quarantine_now}")

    if reason:
        codes = sorted({b["code"] for b in report.get("blockers", [])} |
                       {c["code"] for c in report.get("warnings", [])
                        if c.get("rung") == "QUARANTINE"})
        log(f"audit: worst={worst} counts={counts} — restart live ({reason}, "
            f"codes={codes[:6]})")
        toast("⚠ SniperSight audit restart",
              f"{reason} — restarting live-scanner. "
              f"Codes: {', '.join(codes[:6]) or '(none)'}")
        if live_child.alive():
            try:
                live_child.proc.terminate()
            except Exception as e:
                log(f"audit: terminate failed ({e})")
    elif warmup:
        log(f"audit: warmup seed counts={counts} worst={worst}")
    elif auto_disable_now:
        log(f"audit: worst={worst} counts={counts} — AUTO_DISABLE noted")
    elif serve_flag_now:
        log(f"audit: worst={worst} counts={counts} — SERVE_FLAG only")
    else:
        log(f"audit: worst={worst} — clean")

    return {"counts": counts, "at": now_mono}


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

    # Warmup: seed prior counts so a first-tick QUARANTINE reading is not
    # misread as a climb-from-0 (Auditor FIND-2, 2026-07-26).
    audit_state: dict = audit_tick({"counts": {}, "at": 0.0}, live, warmup=True)
    try:
        while True:
            live.tick()
            if not external_server:
                server.tick()
            elif not server_up():
                log("external api-server disappeared — taking over supervision")
                external_server = False
            if time.monotonic() - audit_state.get("at", 0.0) >= AUDIT_INTERVAL_SEC:
                audit_state = audit_tick(audit_state, live)
            time.sleep(10)
    finally:
        for c in (live, server):
            if c.alive():
                c.proc.terminate()
        log("watchdog stopped")


if __name__ == "__main__":
    main()
