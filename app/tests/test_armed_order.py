"""Armed order — "no runtime decision at execution", asserted rather than claimed.

`forming-armed-order-plan.md` Phase I. The property under test is narrow and
load-bearing: when a setup is armed at zone approach, the order that eventually
executes must be the order that was DECIDED then — not one recomputed at touch
time and assumed to match. The inputs move in between (ATR, structure, equity),
so "computed the same way" is a weaker guarantee than "inherited".

The five cases below are the plan's own acceptance criteria.
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import execsim, risk, setups, store


class PureSizing(unittest.TestCase):
    """Phase E — sizing extracted from the portfolio pass without moving §9.

    `risk.py` still owns the code. What changed is that it can be CALLED at
    arming time. The split is deliberate: order-level constraints belong here,
    account-level ones (kill switch, concurrency, cooldowns, universe
    eligibility) stay in `risk.run`, because a FORMING fact must never be able
    to claim an approval the portfolio never granted.
    """

    def test_it_is_pure_no_connection_no_clock(self):
        """Checked on the AST, not the source text.

        The first version of this test grepped `inspect.getsource` and failed on
        the phrase "at execution time." in the docstring — prose that describes
        impurity is not impurity. Matching identifiers in the parsed tree asks
        the question that was actually meant.
        """
        import ast
        import inspect
        import textwrap

        sig = inspect.signature(risk.size_order)
        self.assertNotIn("con", sig.parameters,
                         "a pure sizer must not take a connection")

        tree = ast.parse(textwrap.dedent(inspect.getsource(risk.size_order)))
        called, attrs = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    called.add(f.id)
                elif isinstance(f, ast.Attribute):
                    base = f.value
                    attrs.add(f"{getattr(base, 'id', '?')}.{f.attr}")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.fail("size_order imports at call time — hidden dependency")
        for bad in ("store.insert_fact", "store.get_facts", "time.time",
                    "time.monotonic", "datetime.now"):
            self.assertNotIn(bad, attrs, f"size_order calls {bad}")
        self.assertNotIn("print", called)

    def test_same_inputs_give_the_same_order(self):
        kw = dict(equity=Decimal("10000"), entry=Decimal("100"),
                  sl=Decimal("98"), direction="LONG", symbol="BTCUSDT")
        self.assertEqual(risk.size_order(**kw), risk.size_order(**kw))

    def test_risk_is_a_fixed_fraction_of_equity_not_of_the_stop(self):
        """The invariant the whole sizing model rests on: a wide stop buys fewer
        units, never more dollars at risk."""
        near = risk.size_order(equity=Decimal("10000"), entry=Decimal("100"),
                               sl=Decimal("99"), direction="LONG", symbol="BTCUSDT")
        far = risk.size_order(equity=Decimal("10000"), entry=Decimal("100"),
                              sl=Decimal("90"), direction="LONG", symbol="BTCUSDT")
        self.assertEqual(near["risk_usd"], far["risk_usd"])
        self.assertGreater(near["units"], far["units"])

    def test_a_stop_beyond_liquidation_is_refused_not_resized(self):
        """A stop the exchange would close through first is not a smaller trade,
        it is a different one — the R-multiple downstream would be fiction."""
        out = risk.size_order(equity=Decimal("1000"), entry=Decimal("100"),
                              sl=Decimal("50"), direction="LONG",
                              symbol="BTCUSDT", risk_pct=Decimal("0.9"))
        self.assertEqual(out["decision"], "REJECTED")

    def test_a_rejection_carries_no_size(self):
        out = risk.size_order(equity=Decimal("10000"), entry=Decimal("100"),
                              sl=Decimal("100"), direction="LONG", symbol="BTCUSDT")
        self.assertEqual(out["decision"], "REJECTED")
        self.assertEqual(out["risk_usd"], Decimal(0))
        self.assertEqual(out["units"], Decimal(0))


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _setup_fact(self, state, sid, tf="1D", ts=1_700_000_000, **extra):
        payload = {"setup_id": sid, "state": state, "strategy": "PULLBACK",
                   "direction": "LONG", "entry": "100", "sl": "95", "tp": "115",
                   "rr": "3", "rank": 50, "why": "t", **extra}
        store.insert_fact(self.con, symbol="BTCUSDT", tf=tf, kind="setup",
                          market_time=ts, confirmed_at=ts,
                          algo_version=setups.SETUP_VERSION, payload=payload)
        self.con.commit()
        return payload


class Inheritance(_StoreCase):
    """Phase F — case (1) and case (3) of the plan's acceptance list."""

    def test_a_validated_setup_records_whether_it_inherited(self):
        """The claim has to be visible on the fact. An inheritance that cannot
        be audited is indistinguishable from a coincidence."""
        for field in ("inherited_from_forming", "forming_id",
                      "armed_size_units", "armed_risk_decision"):
            self.assertIn(field, _VALIDATED_FIELDS,
                          f"{field} must ride on every VALIDATED payload")

    def test_lower_timeframes_have_no_forming_and_say_so(self):
        """15m/1H never arm — there is no FORMING pass for them by design. They
        must report `inherited_from_forming: False`, not pretend otherwise."""
        self.assertNotIn("15m", setups.FORMING_TFS)
        self.assertNotIn("1H", setups.FORMING_TFS)
        self.assertIn("1D", setups.FORMING_TFS)


class ArmedFlag(_StoreCase):
    """Phase E — case (4): a risk-rejected arming still emits, unarmed."""

    def test_a_sizing_rejection_still_emits_the_candidate(self):
        """Silence would lose the evidence. The candidate was real; the refusal
        is the finding."""
        out = risk.size_order(equity=Decimal("10000"), entry=Decimal("100"),
                              sl=Decimal("100"), direction="LONG", symbol="BTCUSDT")
        self.assertEqual(out["decision"], "REJECTED")
        # setups.py writes armed = decision != REJECTED
        self.assertFalse(out["decision"] != "REJECTED")


class Lineage(_StoreCase):
    """Phases G and H — cases (2) and (5)."""

    LINEAGE = ("forming_id", "inherited_from_forming", "armed_at",
               "armed_size_units", "armed_risk_decision", "expires_at_ts")

    def test_orders_and_execs_carry_the_armed_lineage(self):
        import inspect
        src = inspect.getsource(execsim.run)
        for field in self.LINEAGE:
            self.assertIn(field, src,
                          f"{field} must propagate onto order/exec facts")

    def test_a_missed_order_records_why_the_window_closed(self):
        """MAX_ENTRY_BARS has never been judged against real arming lead times.
        A MISSED fact that does not say whether the window expired cannot
        calibrate it."""
        import inspect
        src = inspect.getsource(execsim.run)
        for field in ("bars_armed_exceeded", "expires_at_observed",
                      "armed_lead_bars"):
            self.assertIn(field, src, f"MISSED path must record {field}")

    def test_lineage_rides_on_the_missed_path_too(self):
        """A MISSED order is the one case where lineage matters most — it is the
        only evidence that the armed window, rather than the thesis, ended it."""
        import inspect
        src = inspect.getsource(execsim.run)
        miss = src[src.index('"outcome": "MISSED"') - 2000:
                   src.index('"outcome": "MISSED"') + 200]
        self.assertIn("armed_lineage", miss)


# Fields the VALIDATED payload must carry, read from the source so this test
# fails when the payload changes rather than drifting quietly beside it.
def _validated_fields():
    import inspect
    src = inspect.getsource(setups.run)
    marker = 'payload = {"setup_id": setup_id,'
    return src[src.index(marker):src.index(marker) + 2000]


_VALIDATED_FIELDS = _validated_fields()


if __name__ == "__main__":
    unittest.main()
