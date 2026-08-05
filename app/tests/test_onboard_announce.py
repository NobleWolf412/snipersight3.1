"""A symbol is announced as new ONCE, not once per refresh.

`universe.refresh()` returns every symbol short of the 200 daily candles the
engines need, under the key `warming`. That is not the same as "newly added":
a symbol whose venue simply has no more history stays there permanently.
CAP-USD has 35 daily candles and always will.

So `refresh_universe` re-onboarded it and toasted "New symbol added" on every
hourly refresh, and on every restart — because `_last_universe_refresh` is a
module global reset to 0, which forces a full refresh immediately on start.

Wrong, and not free. Each toast spawns a PowerShell process, and the scanner's
remaining deaths all sit in that startup burst:

    run 1   60s   died, last log line at an onboard/toast site
    run 2   30s   died
    run 3  119s   died, last log line at a drift/toast site
    run 4  1936s  still running once the burst was over
"""
import logging
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import live      # noqa: E402
import notify    # noqa: E402


class AnnounceOnce(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._toast = notify.toast
        self._ingest = live.ingest
        self._refresh = live.universe.refresh
        self._repair = live.repair_short_history
        notify.toast = lambda t, m: (self.calls.append(t), True)[1]

        class FakeIngest:
            @staticmethod
            def onboard(con, sym):
                return {"candles": {"1D": 35}}       # never reaches 200

        live.ingest = FakeIngest
        live.universe.refresh = lambda con, progress=None: {
            "source": "ok", "warming": ["CAP-USD"]}
        live.repair_short_history = lambda *a, **k: None
        live._announced_warming.clear()
        self.log = logging.getLogger("test-onboard")

    def tearDown(self):
        notify.toast = self._toast
        live.ingest = self._ingest
        live.universe.refresh = self._refresh
        live.repair_short_history = self._repair
        live._announced_warming.clear()

    def _refresh_n(self, n):
        for _ in range(n):
            live._last_universe_refresh = None       # what a restart looks like
            live.refresh_universe(None, self.log)

    def test_a_permanently_warming_symbol_is_announced_once(self):
        self._refresh_n(4)
        self.assertEqual(len(self.calls), 1,
                         "a symbol that can never warm is announced on every "
                         "refresh and every restart")

    def test_it_is_still_onboarded_every_time(self):
        """Suppressing the ANNOUNCEMENT must not suppress the work — the symbol
        still needs its candles pulled on each pass."""
        seen = []
        class Counting:
            @staticmethod
            def onboard(con, sym):
                seen.append(sym)
                return {"candles": {"1D": 35}}
        live.ingest = Counting
        self._refresh_n(3)
        self.assertEqual(len(seen), 3, "onboarding itself was skipped")
        self.assertEqual(len(self.calls), 1)

    def test_a_genuinely_new_symbol_is_announced(self):
        self._refresh_n(1)
        live.universe.refresh = lambda con, progress=None: {
            "source": "ok", "warming": ["CAP-USD", "NEW-USD"]}
        self._refresh_n(1)
        self.assertEqual(len(self.calls), 2,
                         "a symbol appearing for the first time was silenced too")

    def test_an_unavailable_rank_source_announces_nothing(self):
        live.universe.refresh = lambda con, progress=None: {
            "source": "unavailable", "warming": []}
        self._refresh_n(2)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
