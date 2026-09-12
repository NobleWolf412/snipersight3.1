"""What KIND of thing happened, beside the outcome of what happened.

Two dimensions, never one. A trade is `SL` AND a `MARKET_LOSS`; a partial fill
that later wins is both a win and an execution event. Collapsing them is how
"we lost money today" stops being answerable as "and here is how much of that
was the market, and how much was us".

The distinction everybody gets wrong, stated once and tested here: **a limit
that expires unfilled is not a failure.** It is the strategy declining to
chase, working as designed. An EXECUTION_FAILURE means the machinery broke.
"""
from __future__ import annotations

import unittest

from engine import telemetry


def _lifecycle(risk=None, order=None, execution=None):
    return telemetry.classify_failure(risk, order, execution)


class TheSecondDimension(unittest.TestCase):
    def test_a_stop_out_is_a_market_loss_not_a_defect(self):
        """The market going the other way is the business, not a bug."""
        life = _lifecycle(execution={"outcome": "SL", "r_multiple": "-1.0"})
        self.assertEqual(telemetry.outcome_class(life), "MARKET_LOSS")

    def test_a_winner_is_its_own_class(self):
        life = _lifecycle(execution={"outcome": "TP", "r_multiple": "2.0"})
        self.assertEqual(telemetry.outcome_class(life), "MARKET_WIN")

    def test_an_unfilled_limit_is_never_an_execution_failure(self):
        """THE one that matters. A limit that expired unfilled is the strategy
        refusing to chase — the behaviour that protects the book from the
        worst entries. Filed as a machinery fault, it would read as something
        to go and fix, and the fix would be to chase."""
        life = _lifecycle(execution={"outcome": "MISSED"})
        self.assertEqual(telemetry.outcome_class(life), "NO_FILL")
        self.assertNotEqual(telemetry.outcome_class(life), "EXECUTION_FAILURE")

    def test_a_risk_refusal_is_the_strategy_working(self):
        life = _lifecycle(risk={"decision": "REJECTED",
                                "reasons": ["CONCURRENT_LIMIT(1)"]})
        self.assertEqual(
            telemetry.outcome_class(life, {"decision": "REJECTED",
                                           "reasons": ["CONCURRENT_LIMIT(1)"]}),
            "STRATEGY_REJECTION")

    def test_a_refusal_on_untrustworthy_data_is_a_system_failure(self):
        """A refusal because the data could not be trusted is a system fault
        wearing a risk reason. Counting it as a strategy rejection would
        credit the strategy with judgement it never exercised."""
        risk = {"decision": "REJECTED", "reasons": ["DATA_HEALTH_BLOCKED"]}
        self.assertEqual(telemetry.outcome_class(_lifecycle(risk=risk), risk),
                         "SYSTEM_FAILURE")

    def test_an_open_position_has_no_outcome_yet(self):
        life = _lifecycle(order={"event": "FILLED"})
        self.assertEqual(telemetry.outcome_class(life), "IN_FLIGHT")

    def test_costs_erasing_the_edge_is_a_market_loss_that_names_a_lever(self):
        life = _lifecycle(execution={"outcome": "TP", "r_multiple": "-0.1",
                                     "r_gross": "1.5"})
        self.assertEqual(life["failure_code"], "COSTS_ERASED_EDGE")
        self.assertEqual(telemetry.outcome_class(life), "MARKET_LOSS")


class TheMapIsComplete(unittest.TestCase):
    def test_every_lifecycle_code_has_a_class(self):
        """An unmapped code defaults to EXECUTION_FAILURE — deliberately the
        LOUD default, because a new lifecycle state nobody classified should
        surface as something to look at, not vanish into a normal bucket. This
        test is what stops that default ever being reached in practice."""
        import inspect
        src = inspect.getsource(telemetry.classify_failure)
        emitted = set()
        for line in src.splitlines():
            if '"failure_code":' in line:
                emitted.add(line.split('"failure_code":')[1]
                            .split('"')[1])
        missing = sorted(emitted - set(telemetry._CLASS_BY_CODE))
        self.assertEqual(missing, [],
                         f"classify_failure emits codes with no outcome class: {missing}")

    def test_every_class_in_the_map_is_a_declared_one(self):
        unknown = sorted(set(telemetry._CLASS_BY_CODE.values())
                         - set(telemetry.OUTCOME_CLASSES))
        self.assertEqual(unknown, [])

    def test_the_record_carries_both_dimensions(self):
        record = telemetry.build_record(
            {"setup_id": "s-1", "entry": "100", "sl": "99", "tp": "102"},
            execution={"outcome": "SL", "r_multiple": "-1.0"})
        self.assertEqual(record["outcome_class"], "MARKET_LOSS")
        self.assertEqual(record["classification"], "EXPECTED_ATTRITION",
                         "expected and market-loss are different questions")


if __name__ == "__main__":
    unittest.main()
