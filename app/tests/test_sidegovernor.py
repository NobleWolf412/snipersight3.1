"""The governor replay (engine/sidegovernor.py) must apply risk.run's predicate,
not a flattering cousin of it. Two properties the audit of 2026-09-03 found the
first version violating, pinned so the numbers the operator picks N from are
the numbers the engine will produce."""
import unittest

from engine import sidegovernor as sg

D = 86400


def _row(sid, entry, exit_, side, r):
    return {"setup_id": sid, "symbol": "X", "tf": "1H", "entry_ts": entry,
            "exit_ts": exit_, "direction": side, "r": r}


class SequentialReplay(unittest.TestCase):
    def test_a_refused_trade_never_contributes_a_loss(self):
        """s1, s2 lose on day D -> s3 (day D) refused. s3 would ALSO have lost,
        landing on D+1 — but it was never a position, so on D+1 only s4's loss
        exists and s5 must be APPROVED. Counting s3's loss over-refuses."""
        rows = [_row("s1", 1000, 1500, "SHORT", -1.0),
                _row("s2", 2000, 2500, "SHORT", -1.0),
                _row("s3", 3000, D + 3600, "SHORT", -1.0),    # refused; its loss is fiction
                _row("s4", D + 5000, D + 5500, "SHORT", -1.0),
                _row("s5", D + 6000, D + 6500, "SHORT", -1.0)]
        refused = [r["setup_id"] for r in sg.refusals(rows, 2)]
        self.assertEqual(refused, ["s3"])

    def test_the_other_side_and_the_next_day_are_untouched(self):
        rows = [_row("s1", 1000, 1500, "SHORT", -1.0),
                _row("s2", 2000, 2500, "SHORT", -1.0),
                _row("l1", 3000, 3500, "LONG", -1.0),
                _row("s3", D + 100, D + 600, "SHORT", -1.0)]
        self.assertEqual(sg.refusals(rows, 2), [])

    def test_a_loss_landing_after_the_entry_does_not_count(self):
        rows = [_row("s1", 1000, 1500, "SHORT", -1.0),
                _row("s2", 2000, 9000, "SHORT", -1.0),     # exits AFTER s3 enters
                _row("s3", 3000, 3500, "SHORT", -1.0)]
        self.assertEqual(sg.refusals(rows, 2), [])

    def test_zero_refuses_nothing(self):
        rows = [_row("s1", 1000, 1500, "SHORT", -1.0), _row("s2", 2000, 2500, "SHORT", -1.0),
                _row("s3", 3000, 3500, "SHORT", -1.0)]
        self.assertEqual(sg.refusals(rows, 0), [])
        self.assertEqual([r["setup_id"] for r in sg.refusals(rows, 1)], ["s2", "s3"])


if __name__ == "__main__":
    unittest.main()
