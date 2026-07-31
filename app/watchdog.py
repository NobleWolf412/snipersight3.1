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
import os
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

# A restart must never be able to prevent the work it is restarting.
#
# On 2026-07-30 watchdog.log recorded 184 `live-scanner exited rc=1` events.
# None were crashes: every one was this process terminating the scanner because
# the audit saw QUARANTINE climb. A full scan cycle measures ~296s, the audit
# runs every 60s, and the scanner was being killed ~78s in — so it never once
# reached the end of a pass. The climb was STALE_SERIES, which means candles are
# behind; the cure for that is letting the import finish, and the response was
# to kill the importer. Restart, fall behind, restart.
#
# Two guards. A climb has to PERSIST before it counts, because the observed
# sequence recovered on its own (19 -> 19 -> 4 -> 0) and each of those ticks
# used to be a kill. And the scanner gets long enough on the clock to finish a
# cycle before anything may terminate it, because a process that is never
# allowed to complete its work cannot clear the condition being complained
# about.
QUARANTINE_CLIMB_TICKS = 3        # consecutive audits elevated-and-not-recovering
RESTART_GRACE_SEC = 420           # > the slowest cycle measured (347.1s)
SERVER_PROBE_TIMEOUT = 15         # > /api/status measured at 6.9s under load
SERVER_MISSES_BEFORE_TAKEOVER = 3 # one slow answer is not a disappearance


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
    """Is an API server answering?

    The timeout was 3s against an endpoint measured at 6.9s while the WAL was
    bloated. One slow answer therefore read as "the external server vanished",
    the watchdog took over supervision, and started a SECOND uvicorn on a port
    the first one still held — which cannot bind, exits, and restarts forever.
    A liveness probe must be slower than the thing it is probing.
    """
    try:
        urllib.request.urlopen(SERVER_URL, timeout=SERVER_PROBE_TIMEOUT)
        return True
    except Exception:
        return False


def _orphans(exclude: set[int] | None = None) -> list[tuple[int, str]]:
    """Scanner/server processes from a PREVIOUS supervisor, still running.

    watchdog.log records 8 starts and 1 clean stop: seven supervisors died
    without reaching the finally that terminates their children. Popen children
    outlive their parent on Windows, so each of those left a live.py behind, and
    the next supervisor started a SECOND one. Two scanners on one SQLite file is
    exactly the `database is locked` storm the log shows — 154 of them inside a
    single hour.

    Adopting is not possible (no handle), so the only safe move is to clear them
    before spawning, and to say plainly what was cleared.
    """
    out = []
    if sys.platform != "win32":
        return out
    # NEVER this process, and never a child this supervisor is currently
    # running: `exclude` carries those. Without it, calling this after startup
    # would kill the very scanner we are supervising — the exact failure this
    # function exists to prevent, caused by the fix for it.
    skip = {os.getpid()} | (exclude or set())
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name like '%python%'",
             "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=15)
        for line in (r.stdout or "").splitlines():
            if "live.py" not in line and "uvicorn" not in line:
                continue
            parts = [p for p in line.strip().split(",") if p]
            pid = next((int(p) for p in reversed(parts) if p.isdigit()), None)
            if pid and pid not in skip:
                out.append((pid, "live.py" if "live.py" in line else "api-server"))
    except Exception:
        pass
    return out


def clear_orphans(exclude: set[int] | None = None) -> None:
    for pid, what in _orphans(exclude):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=10)
            log(f"cleared orphaned {what} pid={pid} from a previous supervisor")
        except Exception as e:
            log(f"could not clear orphaned {what} pid={pid}: {e}")


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

    prior_q = prior.get("QUARANTINE", 0)
    # How long the quarantine reading has been elevated WITHOUT recovering. A
    # single tick means nothing: the count moves while an import catches up.
    streak = state.get("q_streak", 0)
    if warmup or quarantine_now == 0 or quarantine_now < prior_q:
        streak = 0                       # clean, or actively recovering
    elif quarantine_now > prior_q or streak:
        streak += 1                      # climbing, or stuck high after a climb

    reason = None
    if halt_now:
        reason = f"HALT ({halt_now} finding(s))"
    elif streak >= QUARANTINE_CLIMB_TICKS:
        reason = (f"QUARANTINE {quarantine_now} sustained over "
                  f"{streak} audits (was {prior_q})")

    if reason:
        codes = sorted({b["code"] for b in report.get("blockers", [])} |
                       {c["code"] for c in report.get("warnings", [])
                        if c.get("rung") == "QUARANTINE"})
        # Killing a scanner that has not yet had time to finish a pass is how
        # the restart loop sustained itself. Say so and wait rather than
        # silently doing nothing — a suppressed safety action must be visible.
        age = time.monotonic() - getattr(live_child, "started_at", 0.0)
        if live_child.alive() and age < RESTART_GRACE_SEC:
            log(f"audit: worst={worst} counts={counts} — {reason}, but "
                f"live-scanner is {age:.0f}s old and a cycle needs ~296s; "
                f"deferring restart (codes={codes[:6]})")
            return {"counts": counts, "at": now_mono, "q_streak": streak}
        log(f"audit: worst={worst} counts={counts} — restart live ({reason}, "
            f"codes={codes[:6]})")
        toast("⚠ SniperSight audit restart",
              f"{reason} — restarting live-scanner. "
              f"Codes: {', '.join(codes[:6]) or '(none)'}")
        if live_child.alive():
            live_child.kill(f"audit: {reason}")
        streak = 0                       # the restart is the response; re-arm
    elif warmup:
        log(f"audit: warmup seed counts={counts} worst={worst}")
    elif auto_disable_now:
        log(f"audit: worst={worst} counts={counts} — AUTO_DISABLE noted")
    elif serve_flag_now:
        log(f"audit: worst={worst} counts={counts} — SERVE_FLAG only")
    else:
        log(f"audit: worst={worst} — clean")

    return {"counts": counts, "at": now_mono, "q_streak": streak}


class Child:
    def __init__(self, name, args, notify_restart=False):
        self.name, self.args = name, args
        self.notify_restart = notify_restart
        self.proc = None
        self.started_at = 0.0
        self.backoff = 5
        self._err = None
        self._err_path = APP / "data" / f"{name}.err.log"
        # Did THIS supervisor end the child? The exit forensics in live.py can
        # prove a death was TerminateProcess but not who sent it, and rc=1 looks
        # identical either way. Recording our own hand is the only way to read
        # an exit as "we did that" rather than "something did that".
        self.killed_by_us = None

    def kill(self, why: str):
        self.killed_by_us = why
        try:
            self.proc.terminate()
        except Exception as e:
            log(f"{self.name}: terminate failed ({e})")

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        """Start the child with its stderr captured to a file.

        It used to inherit this process's stderr. Under start.bat that is a
        console window, so 184 exits were recorded as `rc=1` with the traceback
        printed to a window nobody was reading and nothing kept. The exit code
        alone cannot distinguish a crash from a deliberate terminate, which is
        most of why those events went a day without a diagnosis.
        """
        try:
            self._err_path.parent.mkdir(parents=True, exist_ok=True)
            self._err = open(self._err_path, "a", encoding="utf-8", errors="replace")
            self._err.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} start ===\n")
            self._err.flush()
        except Exception as e:                       # never block a start on logging
            log(f"{self.name}: could not open {self._err_path.name} ({e})")
            self._err = None
        self.proc = subprocess.Popen(self.args, cwd=APP, stderr=self._err or None)
        self.started_at = time.monotonic()
        log(f"{self.name} started pid={self.proc.pid}")

    def _last_error(self, max_lines: int = 12) -> str:
        """The tail of the child's stderr, so the exit explains itself."""
        try:
            lines = self._err_path.read_text(encoding="utf-8",
                                             errors="replace").splitlines()
            i = max(i for i, l in enumerate(lines) if l.startswith("=== "))
            tail = [l for l in lines[i + 1:] if l.strip()][-max_lines:]
            return " | ".join(tail)
        except Exception:
            return ""

    def tick(self):
        if self.alive():
            if time.monotonic() - self.started_at > 60:
                self.backoff = 5          # clean uptime resets backoff
            return
        if self.proc is not None:         # it died
            rc = self.proc.returncode
            if self._err:
                try: self._err.close()
                except Exception: pass
                self._err = None
            why = self._last_error()
            # The distinction that took 191 exits to become answerable.
            hand = (f" — ENDED BY THIS SUPERVISOR ({self.killed_by_us})"
                    if self.killed_by_us
                    else " — NOT ended by this supervisor")
            log(f"{self.name} exited rc={rc}{hand} — restart in {self.backoff}s"
                + (f" — last output: {why}" if why else ""))
            self.killed_by_us = None
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
    # Before spawning anything: clear children a previous supervisor left behind.
    # Holding the lock proves no OTHER watchdog is live, so anything still
    # running is an orphan, and starting beside it would put two scanners on one
    # database.
    clear_orphans()
    live = Child("live-scanner", [py, "-X", "utf8", "live.py"], notify_restart=True)
    server = Child("api-server", [py, "-m", "uvicorn", "server:app",
                                  "--port", "8422", "--host", "127.0.0.1"])
    external_server = server_up()
    if external_server:
        log("api-server already running externally — not supervising it")

    # Warmup: seed prior counts so a first-tick QUARANTINE reading is not
    # misread as a climb-from-0 (Auditor FIND-2, 2026-07-26).
    audit_state: dict = audit_tick({"counts": {}, "at": 0.0}, live, warmup=True)
    misses = 0
    try:
        while True:
            live.tick()
            if not external_server:
                server.tick()
            elif not server_up():
                # A slow answer is not a disappearance. Taking over on one miss
                # starts a second uvicorn on a port the first still holds, which
                # cannot bind and then restart-loops forever.
                misses += 1
                log(f"external api-server did not answer ({misses}/"
                    f"{SERVER_MISSES_BEFORE_TAKEOVER})")
                if misses >= SERVER_MISSES_BEFORE_TAKEOVER:
                    log("external api-server gone — taking over supervision")
                    external_server = False
                    # wedged rather than dead is possible; clear it, but never
                    # the scanner this supervisor is already running
                    clear_orphans(exclude={live.proc.pid} if live.alive() else set())
            else:
                misses = 0
            if time.monotonic() - audit_state.get("at", 0.0) >= AUDIT_INTERVAL_SEC:
                audit_state = audit_tick(audit_state, live)
            time.sleep(10)
    finally:
        # Reached only on an orderly stop. A hard kill of this process skips it
        # entirely, which is how seven previous supervisors left their children
        # running — see clear_orphans().
        for c in (live, server):
            if c.alive():
                c.kill("watchdog shutting down")
        log("watchdog stopped")


if __name__ == "__main__":
    main()
