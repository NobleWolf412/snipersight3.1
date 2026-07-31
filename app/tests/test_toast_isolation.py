"""A notification must not be able to kill the process that emits it.

The live scanner exited 191 times with rc=1 and no traceback. The exit forensics
in live.py showed TerminateProcess and the supervisor's own attribution said it
was not the one doing it, so something else held a handle. Measured in console
mode, with only this variable moved:

    toasts on   254s, dead, last log line on a toast call site
    toasts off  1055s and 13 completed cycles, still running

Every toast spawns PowerShell, and by default Windows puts that child in the
CALLER'S console. Processes sharing a console share its control events, and a
console control event is delivered as an uncatchable kill.

Two flags, added in that order and both needed:

  CREATE_NO_WINDOW          own console rather than borrowing ours
  CREATE_NEW_PROCESS_GROUP  GenerateConsoleCtrlEvent is scoped to a group, so a
                            control event cannot cross the boundary either way

The second was added because the first was not sufficient: with it in place the
scanner still died at toast sites — a drift alert after 35 minutes, an onboard
before that.

These tests pin the isolation and the kill-switch. They deliberately do NOT
claim to reproduce the original failure: it never reproduced outside a long
running scanner, and a test that pretends otherwise would be worse than none.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP = Path(__file__).resolve().parent.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import notify  # noqa: E402


class ToastIsSpawnedIsolated(unittest.TestCase):
    def _spawn_kwargs(self):
        with patch.object(notify.subprocess, "run",
                          return_value=MagicMock(returncode=0)) as run, \
             patch.object(notify.sys, "platform", "win32"):
            notify.toast("t", "m")
        self.assertTrue(run.called, "toast never spawned anything")
        return run.call_args.kwargs

    def test_the_child_does_not_borrow_our_console(self):
        flags = self._spawn_kwargs().get("creationflags", 0)
        self.assertTrue(flags & notify.CREATE_NO_WINDOW,
                        "PowerShell is spawned into the caller's console again — "
                        "a control event there is an uncatchable kill for us")

    def test_the_child_is_in_its_own_process_group(self):
        flags = self._spawn_kwargs().get("creationflags", 0)
        self.assertTrue(flags & notify.CREATE_NEW_PROCESS_GROUP,
                        "a console control event can cross back into the caller")

    def test_a_toast_failure_is_never_raised_at_the_caller(self):
        """check_drift and refresh_universe call this mid-cycle. A notification
        that raises would take a scan pass with it."""
        with patch.object(notify.subprocess, "run", side_effect=OSError("boom")):
            self.assertFalse(notify.toast("t", "m"))

    def test_the_temp_script_is_always_cleaned_up(self):
        seen = {}
        real = notify.tempfile.NamedTemporaryFile

        def spy(*a, **k):
            f = real(*a, **k)
            seen["path"] = f.name
            return f

        with patch.object(notify.tempfile, "NamedTemporaryFile", spy), \
             patch.object(notify.subprocess, "run", side_effect=OSError("boom")):
            notify.toast("t", "m")
        self.assertIn("path", seen)
        self.assertFalse(os.path.exists(seen["path"]),
                         "the failure path leaks one .ps1 per toast")

    def test_the_kill_switch_spawns_nothing(self):
        """SNIPERSIGHT_NO_TOAST is what made the failure bisectable, and is the
        right setting for a headless run."""
        with patch.dict(os.environ, {"SNIPERSIGHT_NO_TOAST": "1"}), \
             patch.object(notify.subprocess, "run") as run:
            self.assertFalse(notify.toast("t", "m"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
