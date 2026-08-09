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
# HALT codes RESTARTING THE SCANNER CANNOT CLEAR, so a restart does nothing
# but interrupt the cycle. `UNKNOWN_TIMEFRAME` is the concrete case, and the
# reason is that THIS process reads the timeframe list, not the child it kills.
#
# `quality.audit()` runs here, in the supervisor, against
# `importer.TF_SECONDS` — imported once and held for the life of the process.
# The scanner restarts constantly and therefore always runs current code; the
# supervisor can be days old. Add a timeframe and the two disagree, and every
# series on the new timeframe reads as UNKNOWN to the only process that can
# act on it.
#
# Measured 2026-08-08. The supervisor had been up since 06 Aug 17:40, from a
# commit whose TF_SECONDS was {15m,1H,4H,1D,1W}; `5m` was added after. 27
# symbols carried 5m candles, the audit reported exactly 27 UNKNOWN_TIMEFRAME
# findings on every tick, and the scanner was killed every ~7 minutes while
# its own log ("22 new candles, 0 new setups") showed it working normally. The
# same audit run against the same database with current code found ZERO. On
# restarting the supervisor at 20:26 the count went 27 -> 0 with nothing in
# the store having changed.
#
# So the store was never damaged, and an earlier draft of this comment was
# wrong to say a bad row was stuck in it. The guard still stands, for a
# stronger reason than the one it was written for: the scanner is not the
# process holding the stale reading, so killing it is guaranteed not to help.
# Same shape as the QUARANTINE hysteresis below — a data verdict is not a
# process fault — narrowed to this one code because other HALT codes
# (NO_CANDLES, OHLC_INVARIANT_FAILURE) CAN be healed by the scanner's next
# import.
#
# What this does NOT do is fix the underlying condition. The toast is the only
# thing that will tell you, and the answer is almost always "restart the
# supervisor", which `/api/system/restart` cannot do — it restarts the
# children and refuses outright if the watchdog is down.
UNHEALABLE_HALT_CODES = frozenset({"UNKNOWN_TIMEFRAME"})
RESTART_GRACE_SEC = 420           # > the slowest cycle measured (347.1s)
SERVER_PROBE_TIMEOUT = 15         # > /api/status measured at 6.9s under load
SERVER_MISSES_BEFORE_TAKEOVER = 3 # one slow answer is not a disappearance
ERR_LOG_CAP_BYTES = 8 * 1024 * 1024   # a diagnostic must not fill the disk
ENGINE_LOG_CAP_BYTES = 64 * 1024 * 1024
ENGINE_LOG_GENERATIONS = 1  # live file plus one retained 64 MB generation
# Windows creation flags. Each child gets its own console and its own process
# group, so a console control event cannot travel between them — see start().
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


def log(msg: str):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def toast(title: str, msg: str, key: str | None = None):
    """Announce something, WITHOUT spawning anything.

    THE RESTART LOOP THIS ENDS. This function used to call notify.toast(),
    which spawns PowerShell. The supervisor's three call sites include one on
    every scanner restart, so the sequence was:

        scanner dies -> watchdog toasts about it -> PowerShell spawns ->
        the spawn reaches the supervisor's children and kills the new
        scanner -> watchdog toasts about it -> ...

    It feeds itself, which is why the log holds 356 scanner exits, all rc=1,
    all `NOT ended by this supervisor`, and 176 starts with ZERO exit notes in
    live-exit.log — no atexit, no signal handler, no faulthandler dump. That
    combination means the process was never allowed to run Python on the way
    out: an uncatchable console control event, exactly the mechanism notify.py
    documents for the original 191 deaths. The clustering fits too, and so do
    the quiet spells: with nothing to announce, nothing spawns, and it runs for
    hours.

    So the supervisor no longer spawns. It queues, and delivery happens through
    the sink system, where the toast sink is off by default and the phone is an
    HTTP POST that cannot do this.
    """
    try:
        sys.path.insert(0, str(APP))
        import notify
        # Keyed so a supervisor stuck in a bad patch reports it once rather
        # than once per tick. Falls back to a per-minute bucket.
        notify.enqueue(key or f"watchdog|{title}|{int(time.time()) // 60}",
                       title, msg, notify.LOUD)
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
    # PowerShell/CIM rather than wmic: wmic is REMOVED on current Windows 11
    # builds, and its absence is silent here — FileNotFoundError is swallowed by
    # the except below, _orphans() returns [], and the clearing this function
    # exists to do never happens. The first version of this shipped exactly that
    # way, and a unit test passed because it mocked subprocess.run: a mock of a
    # binary that does not exist proves the parser, never the plumbing.
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
          "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30)
        for line in (r.stdout or "").splitlines():
            pid_s, _, cmd = line.partition("\t")
            if not pid_s.strip().isdigit():
                continue
            if "live.py" not in cmd and "uvicorn" not in cmd:
                continue
            pid = int(pid_s.strip())
            if pid not in skip:
                out.append((pid, "live.py" if "live.py" in cmd else "api-server"))
    except Exception as e:
        log(f"orphan scan failed ({e}) — cannot tell leftovers from live children")
    return out


def clear_orphans(exclude: set[int] | None = None) -> None:
    for pid, what in _orphans(exclude):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=10)
            log(f"cleared orphaned {what} pid={pid} from a previous supervisor")
        except Exception as e:
            log(f"could not clear orphaned {what} pid={pid}: {e}")


def rotate_engine_log(cap: int = ENGINE_LOG_CAP_BYTES,
                      generations: int = ENGINE_LOG_GENERATIONS) -> bool:
    """Bound the duplicated/operational stream while both children are down.

    The scanner and API server both hold ``engine.log`` open, so rotating from
    either process is unsafe on Windows. The watchdog is the single owner and
    calls this only after clearing old children and before starting new ones.
    ``engine-audit.log`` is intentionally outside this policy.
    """
    path = APP / "data" / "engine.log"
    try:
        if generations < 1 or not path.exists() or path.stat().st_size <= cap:
            return False
        for candidate in path.parent.glob(f"{path.name}.*"):
            suffix = candidate.name.removeprefix(f"{path.name}.")
            if suffix.isdigit() and int(suffix) >= generations:
                candidate.unlink()
        for number in range(generations - 1, 0, -1):
            source = path.with_name(f"{path.name}.{number}")
            if source.exists():
                source.replace(path.with_name(f"{path.name}.{number + 1}"))
        path.replace(path.with_name(f"{path.name}.1"))
        log(f"engine.log rotated at {cap // (1024 * 1024)}MB; "
            f"keeping {generations} generations")
        return True
    except Exception as exc:
        # Retention must never prevent supervision from starting.
        log(f"engine.log rotation skipped ({type(exc).__name__}: {exc})")
        return False


def retention_tick(live_child, server_child, *, external_server: bool,
                   pending: bool = False,
                   cap: int = ENGINE_LOG_CAP_BYTES) -> bool:
    """Coordinate a safe hot-log rollover during a scanner idle boundary.

    Returns whether a rollover is still pending. Both writers must release the
    file before Windows can rename it. Exposure defers housekeeping: preserving
    custody is more important than enforcing the byte cap immediately.
    """
    path = APP / "data" / "engine.log"
    try:
        oversized = path.exists() and path.stat().st_size > cap
    except OSError:
        return pending
    if not (oversized or pending):
        return False
    if external_server:
        return False  # watchdog cannot safely stop a process it does not own
    try:
        heartbeat = json.loads(
            (APP / "data" / "heartbeat.json").read_text(encoding="utf-8"))
        scanner_idle = heartbeat.get("phase") == "idle"
    except (OSError, ValueError, TypeError):
        scanner_idle = False
    if not pending and not scanner_idle:
        return False
    if not pending:
        sys.path.insert(0, str(APP))
        try:
            from engine import positions, store
            con = store.connect()
            try:
                if positions.private_environments_with_exposure(con):
                    return False
            finally:
                con.close()
        except Exception as exc:
            log(f"engine.log rotation deferred; custody check failed ({exc})")
            return False
        for child in (live_child, server_child):
            if child.alive():
                child.kill("coordinated engine.log rotation")
        return True
    if live_child.alive() or server_child.alive():
        return True
    rotate_engine_log(cap=cap)
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

    prior_q = prior.get("QUARANTINE", 0)
    # How long the quarantine reading has been elevated WITHOUT recovering. A
    # single tick means nothing: the count moves while an import catches up.
    streak = state.get("q_streak", 0)
    if warmup or quarantine_now == 0 or quarantine_now < prior_q:
        streak = 0                       # clean, or actively recovering
    elif quarantine_now > prior_q or streak:
        streak += 1                      # climbing, or stuck high after a climb

    # QUARANTINE NO LONGER RESTARTS THE SCANNER. Measured, on 2026-07-31:
    #
    #   07:30:27  QUARANTINE 1   climb        streak 1
    #   07:31:35  QUARANTINE 1   stuck        streak 2
    #   07:32:44  QUARANTINE 1   stuck        streak 3  -> restart
    #   07:32:59  scanner restarted
    #   07:33:48  QUARANTINE 1   UNCHANGED
    #
    # The restart did not clear it. It cleared later, on its own, while the
    # scanner ran. So the response never achieved its goal: a quarantine is a
    # statement about DATA, and bouncing the process that ingests data cannot
    # repair data — it interrupts the cycle that would.
    #
    # Adding hysteresis (3 audits) only slowed this down; the run above already
    # had it. The right change is to stop treating a data verdict as a process
    # fault. HALT still restarts: that is a pipeline the engine says is broken,
    # and a fresh process is at least a plausible response to it.
    #
    # Nothing is silenced — a sustained quarantine still logs and toasts.
    reason = None
    halt_codes = sorted({b["code"] for b in report.get("blockers", [])})
    unhealable_only = bool(halt_codes) and set(halt_codes).issubset(
        UNHEALABLE_HALT_CODES)
    if halt_now and not unhealable_only:
        reason = f"HALT ({halt_now} finding(s))"
    elif halt_now and unhealable_only:
        # Same reasoning as sustained QUARANTINE (below): the process is not
        # the fault. Log and toast; do not restart. Fall through so QUARANTINE
        # hysteresis on the same tick still works.
        log(f"audit: worst={worst} counts={counts} — HALT ({halt_now} "
            f"finding(s)) codes={halt_codes[:6]}. NOT restarting: the scanner "
            f"has no code path that can heal these rows.")
        toast("⚠ SniperSight data HALT",
              f"{halt_now} finding(s) the scanner cannot heal: "
              f"{', '.join(halt_codes[:4]) or '(none)'}")
    if streak == QUARANTINE_CLIMB_TICKS and not reason:
        codes = sorted({c["code"] for c in report.get("warnings", [])
                        if c.get("rung") == "QUARANTINE"})
        log(f"audit: worst={worst} counts={counts} — QUARANTINE {quarantine_now} "
            f"sustained over {streak} audits, codes={codes[:6]}. NOT restarting: "
            f"a data verdict is not a process fault.")
        toast("⚠ SniperSight data quarantine",
              f"{quarantine_now} finding(s) held back for "
              f"{streak} audits: {', '.join(codes[:4]) or '(none)'}")

    if reason:
        codes = sorted({b["code"] for b in report.get("blockers", [])} |
                       {c["code"] for c in report.get("warnings", [])
                        if c.get("rung") == "QUARANTINE"})
        # Killing a scanner that has not yet had time to finish a pass is how
        # the restart loop sustained itself. Say so and wait rather than
        # silently doing nothing — a suppressed safety action must be visible.
        # Default None, never 0.0. `started_at` is monotonic, whose zero is
        # BOOT — so a missing value read as 0.0 means "started at boot", which
        # is ancient on a long-running desktop and newborn on a machine that
        # came up a minute ago. The same clock reading two opposite things is
        # not a default, and this one gates a SAFETY restart: unknown age must
        # not defer it. A child that never recorded a start is not young.
        started = getattr(live_child, "started_at", None)
        age = None if started is None else time.monotonic() - started
        if live_child.alive() and age is not None and age < RESTART_GRACE_SEC:
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
    def __init__(self, name, args, notify_restart=False, capture_stderr=False):
        self.name, self.args = name, args
        self.notify_restart = notify_restart
        # OFF by default, and deliberately. Capturing a child's stderr to a file
        # is what made the scanner's deaths diagnosable at all — but handing
        # uvicorn an inherited file handle broke its access logger outright:
        # `OSError: [Errno 22] Invalid argument` on every request it logged,
        # 8,461 of them and 48 MB in hours, and finally an api-server exit with
        # 0xC000013A (STATUS_CONTROL_C_EXIT). Neither an unbuffered binary
        # handle nor a non-append one fixed it.
        #
        # The scanner needs the capture and tolerates it; the server does not
        # need it and does not. A diagnostic that breaks the process it watches
        # has to be scoped to the process that benefits.
        self.capture_stderr = capture_stderr
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

        NOT an append handle. Python's "a"/"ab" ask Windows for FILE_APPEND_DATA
        only, and a child that inherits such a handle cannot flush it: every
        uvicorn log line raised `OSError: [Errno 22] Invalid argument` inside
        logging.flush(). Logging caught that and printed the traceback to the
        same broken stream — 8,461 of them and 48 MB in a few hours. Switching
        to binary was not enough; the append MODE is the problem, not the text
        wrapper. live.py escaped it only because the watchdog gives that child
        `-X utf8`; uvicorn gets no such flag.

        So: a plain write handle, seeked to the end by hand. A capture that
        corrupts the thing it captures is worse than no capture.
        """
        if self.capture_stderr:
            try:
                self._err_path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_err()
                fd = os.open(str(self._err_path),
                             os.O_WRONLY | os.O_CREAT | getattr(os, "O_BINARY", 0))
                os.lseek(fd, 0, os.SEEK_END)      # append by position, not by mode
                self._err = os.fdopen(fd, "wb", buffering=0)
                self._err.write(
                    f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} start ===\n"
                    .encode("utf-8"))
            except Exception as e:                   # never block a start on logging
                log(f"{self.name}: could not open {self._err_path.name} ({e})")
                self._err = None
        # Each child gets its OWN console and its OWN process group.
        #
        # Both children were dying together and unattributed while this
        # supervisor, which is pythonw and has no console, survived. A
        # console-less parent makes Windows hand its console children a console,
        # and a control event delivered there takes out everything sharing it
        # while leaving the console-less parent untouched. That is the exact
        # shape observed at 06:39 — scanner rc=1, api-server rc=0 forty-four
        # seconds later, neither ended by us.
        #
        # CREATE_NEW_PROCESS_GROUP scopes GenerateConsoleCtrlEvent, so neither
        # child can be reached by, or reach, anything outside itself.
        self.proc = subprocess.Popen(
            self.args, cwd=APP, stderr=self._err or None,
            creationflags=(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)
            if sys.platform == "win32" else 0,
            env=self._child_env())
        self.started_at = time.monotonic()
        log(f"{self.name} started pid={self.proc.pid}")

    def _child_env(self) -> dict:
        """The scanner does not spawn desktop notifications.

        Every toast spawns a PowerShell process, and the scanner's deaths land
        on toast call sites over and over — an onboard, then a drift alert at
        35 minutes, then another drift alert at 402 seconds — across console
        mode AND the detached autostart path, and through two rounds of
        isolation flags that each failed to stop it. The one intervention that
        has ever measurably worked is not spawning them: 1055s and 13 completed
        cycles with toasts off, against 254s and death with them on.

        The scan loop staying up is worth more than a balloon. The supervisor
        still toasts on restarts and audit events, so the operator is still
        told when something happens — from a process that is not the one
        holding the scan.

        SNIPERSIGHT_TOASTS=1 puts them back for anyone who wants to test it.
        """
        env = dict(os.environ)
        if self.name == "live-scanner" and env.get("SNIPERSIGHT_TOASTS") != "1":
            env["SNIPERSIGHT_NO_TOAST"] = "1"
        return env

    def _rotate_err(self, cap: int = ERR_LOG_CAP_BYTES) -> None:
        """Keep the capture file bounded. It reached 48 MB in hours once, and a
        diagnostic that fills the disk is a fault of its own. One generation is
        kept — the previous run's tail is occasionally what explains this run."""
        try:
            if self._err_path.exists() and self._err_path.stat().st_size > cap:
                self._err_path.replace(self._err_path.with_suffix(".old.log"))
                log(f"{self.name}: rotated {self._err_path.name} at "
                    f"{cap // (1024 * 1024)}MB")
        except Exception:
            pass

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
                # Keyed to the exiting pid: one announcement per death, not one
                # per tick. This is the call site that closed the loop — it
                # fires on every restart, and announcing a restart used to be
                # enough to cause the next one.
                toast("⚠ SniperSight scanner restarted",
                      f"{self.name} exited (rc={rc}) — auto-recovered, check watchdog.log",
                      key=f"restart|{self.name}|{self.proc.pid}")
            time.sleep(self.backoff)
            self.backoff = min(self.backoff * 2, 300)
        self.start()


ALERT_INTERVAL_SEC = 60           # how often the queue is drained
HEARTBEAT_INTERVAL_SEC = 300      # how often the outside world hears from us
SCANNER_DARK_AFTER_S = 300        # heartbeat age that means "it stopped"


def alert_tick(state: dict, live, warmup: bool = False) -> dict:
    """Find what the operator would want to know, queue it, and send the queue.

    This is the ONLY sender. The scanner queues; nothing else in the system
    opens a socket to announce anything, because notification work in the scan
    loop is what killed it — 254s to death against 1055s and 13 clean cycles
    with it off.

    Three sources, and the split is deliberate:

      · The kill switch and a resolved trade of the operator's own are read
        straight from the fact store, because they have no equivalent of the
        scanner's announce() gate and nothing else was ever going to notice
        them. The kill switch has fired 23 times and been silent every one.

      · The scanner going dark is read from its heartbeat file, which already
        existed and which nothing acted on.

      · Setups arrive already queued, from inside announce()'s baseline and
        staleness filter. Re-deriving that filter here would be a second
        authority on "is this worth announcing", and the first one is right.

    NEVER from `exec` or `order`: that is the shadow simulation, 100-400 events
    a day for trades nobody placed.
    """
    now = time.monotonic()
    if not warmup and now - state.get("at", 0.0) < ALERT_INTERVAL_SEC:
        return state
    state = dict(state)
    state["at"] = now

    try:
        sys.path.insert(0, str(APP))
        import notify
        from engine import store
    except Exception as e:
        log(f"alerts: import skip ({e})")
        return state

    try:
        con = store.connect()
    except Exception as e:
        log(f"alerts: store unreachable ({e})")
        return state
    try:
        # On the first tick, note where the store already is and announce
        # nothing before it. Without this a fresh supervisor introduces itself
        # by replaying the whole book — the same failure the audit warmup and
        # announce()'s baseline filter each exist to prevent.
        if state.get("last_id") is None:
            state["last_id"] = con.execute(
                "SELECT COALESCE(MAX(id), 0) FROM facts").fetchone()[0]
            return state

        rows = con.execute(
            "SELECT id, symbol, tf, kind, payload FROM facts "
            "WHERE id > ? AND kind IN ('risk', 'manual_exec') ORDER BY id",
            (state["last_id"],)).fetchall()
        for fid, sym, tf, kind, payload in rows:
            state["last_id"] = max(state["last_id"], fid)
            try:
                p = json.loads(payload)
            except Exception:
                continue

            if kind == "risk" and p.get("event") == "KILL_SWITCH":
                # KEYED WITHOUT THE MONEY, AND NOT RE-DERIVED.
                #
                # The risk engine replays the whole book on every run. Three
                # records for the halt of 2026-07-30 carry daily_pnl -675.66,
                # -678.13 and -678.85: same event, three numbers, because the
                # figure is recomputed. A key containing it turns every replay
                # into a fresh alarm.
                #
                # The payload already states its own `day`, so that is what is
                # used — reading the engine's answer rather than deriving a
                # second one from a timestamp. A first draft keyed off
                # baseline_started_at instead, which is constant across a whole
                # baseline: all 23 kill-switch facts collapsed to 2 alerts, so
                # a halt on Monday and another on Thursday would have shared
                # one. There are 15 distinct days in there.
                day = p.get("day") or "unknown-day"
                notify.enqueue(
                    f"killswitch|{p.get('baseline_id')}|{day}",
                    "⛔ Daily loss limit — trading halted",
                    f"{p.get('reason') or 'kill switch tripped'} · "
                    f"day {day} · equity {p.get('equity', '?')} · "
                    f"limit {p.get('loss_limit_usd', '?')}",
                    notify.LOUD)

            elif kind == "manual_exec":
                # The operator's OWN trade reaching its end. Their book, their
                # money-shaped decision — the one outcome in the store that is
                # about them rather than about the engine's simulation.
                outcome = str(p.get("outcome") or "")
                if outcome and outcome != "OPEN":
                    notify.enqueue(
                        f"mytrade|{p.get('intent_id')}|{outcome}",
                        f"◆ Your {p.get('direction', '')} {sym} {tf} — {outcome}",
                        f"{p.get('r_multiple', '?')}R"
                        f"{'' if p.get('exit_price') is None else ' at ' + str(p['exit_price'])}",
                        notify.LOUD)
    except Exception as e:
        log(f"alerts: scan failed ({e})")
    finally:
        con.close()

    # THE SCANNER GOING DARK. Its heartbeat file already existed and nothing
    # read it. Keyed to the minute it went quiet so a scanner that stays down
    # says so once rather than every tick.
    scanner_dark = False
    try:
        hb = json.loads((APP / "data" / "heartbeat.json").read_text(encoding="utf-8"))
        # The field is `ts`. A first draft read `at`, got None, and would have
        # announced "scanner has stopped" on every tick from a scanner that was
        # running perfectly — a false alarm at 3am being the exact opposite of
        # what this is for. An unrecognised shape therefore says so and alerts
        # nothing, because a monitor that cannot read its input must not be
        # trusted to declare a failure.
        beat = hb.get("ts")
        if beat is None:
            log("alerts: heartbeat.json has no 'ts' field — cannot judge "
                "whether the scanner is alive, so not alerting on it")
            raise KeyError("ts")
        age = int(time.time()) - int(beat)
        if age > SCANNER_DARK_AFTER_S:
            scanner_dark = True
            notify.enqueue(
                f"dark|{int(time.time()) // 600}",
                "⚠ Scanner has stopped",
                f"no heartbeat for {age // 60} minutes — the cockpit is "
                f"showing whatever it last knew",
                notify.LOUD)
    except FileNotFoundError:
        pass                      # never started; the restart alert covers it
    except KeyError:
        pass                      # already logged above
    except Exception as e:
        log(f"alerts: heartbeat read failed ({e})")

    try:
        sent = notify.deliver_pending(log=log)
        if sent.get("failed"):
            log(f"alerts: {sent['failed']} could not be delivered")
    except Exception as e:
        log(f"alerts: delivery failed ({e})")

    # A heartbeat this machine sends OUT, to something that alarms when it
    # stops. Nothing running here can report this machine's own death, and the
    # watchdog's log shows eight starts against one clean stop.
    #
    # IT ASSERTS THE STACK, NOT THIS PROCESS. Pinging merely because the
    # supervisor is executing would tell the outside world "all good" while the
    # scanner had been dark for an hour — the supervisor is the one part of the
    # system whose survival proves the least, since its whole job is to outlive
    # the others. Silence is the signal, so the ping is withheld whenever this
    # tick has just concluded the scanner is dark. The ntfy alert covers that
    # case too; this covers it when ntfy is down, the phone is off, or the
    # machine cannot reach anything at all.
    if time.monotonic() - state.get("hb_at", 0.0) >= HEARTBEAT_INTERVAL_SEC:
        state["hb_at"] = time.monotonic()
        if scanner_dark:
            log("heartbeat withheld: scanner is dark, so this machine is not "
                "healthy and must not tell an outside monitor that it is")
            state["hb_last"] = "withheld"
        else:
            try:
                result = notify.heartbeat(log=log)
            except Exception as exc:
                result = f"error({type(exc).__name__})"
            # A SUCCESSFUL PING USED TO LEAVE NO TRACE, which made the one
            # question worth asking about a dead-man's switch — is it actually
            # running? — unanswerable from this machine. Answering it every
            # five minutes forever would be noise, so it is logged on the first
            # ping and on every CHANGE after that: a failure, and the recovery
            # from one. A steady state says nothing, which is the point.
            if result != state.get("hb_last"):
                log(f"heartbeat: {result}")
                state["hb_last"] = result
    return state


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
    rotate_engine_log()
    # Only the scanner gets its stderr captured: it is the process whose exits
    # needed explaining, it runs under -X utf8 so the capture is clean, and
    # uvicorn demonstrably cannot tolerate the same treatment.
    # -u, and it is the difference between a diagnosable death and a guess.
    #
    # This child's stderr is redirected to a FILE, and Python block-buffers a
    # non-tty stderr. A process killed externally never flushes, so everything
    # since the last 4KB boundary dies with it — and `_last_error()` then
    # reports whatever happened to be flushed as "last output", which reads
    # exactly like the place it died.
    #
    # That artefact has cost real time: 39 exits appeared to end at
    # `UNIVERSE onboarded PF_SPCXXUSD`, and one run lived 331 seconds while
    # logging only two lines. Neither was a clue about the crash; both were the
    # buffer. Unbuffered, the last line in the file IS the last thing that
    # happened, and the next death can be read instead of inferred.
    live = Child("live-scanner", [py, "-X", "utf8", "-u", "live.py"],
                 notify_restart=True, capture_stderr=True)
    server = Child("api-server", [py, "-m", "uvicorn", "server:app",
                                  "--port", "8422", "--host", "127.0.0.1"])
    external_server = server_up()
    if external_server:
        log("api-server already running externally — not supervising it")

    # Warmup: seed prior counts so a first-tick QUARANTINE reading is not
    # misread as a climb-from-0 (Auditor FIND-2, 2026-07-26).
    audit_state: dict = audit_tick({"counts": {}, "at": 0.0}, live, warmup=True)
    # Seeded with the ids already in the store, so a fresh supervisor does not
    # announce the whole existing book on its first tick. Same reasoning as the
    # audit warmup above, and the same failure it prevents.
    alert_state: dict = alert_tick({"at": 0.0}, live, warmup=True)
    misses = 0
    retention_pending = False
    try:
        while True:
            retention_pending = retention_tick(
                live, server, external_server=external_server,
                pending=retention_pending)
            if retention_pending:
                time.sleep(1)
                continue
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
            # THE ONLY PLACE ALERTS ARE SENT. The scanner decides what is worth
            # announcing and queues it; this loop does the talking, because
            # notification work from the scan loop is what killed it — 254s to
            # death against 1055s and 13 clean cycles with it off.
            alert_state = alert_tick(alert_state, live)
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
