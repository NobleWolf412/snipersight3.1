"""ONE walk settles and replays — and the pin that let it be extracted.

`abtest.py` opens by admitting the risk it runs: "execsim.py is the production
simulator and a second one risks the two disagreeing", defended by a runtime
calibration pass. The defense was real and it was also already needed — the
harness's `_cost_r` charged exit fees on the nominal price where execsim
charges them on the slipped price, and it never charged funding at all: the
exact "unmodelled cost that only ever flatters" that execsim v0.12 exists to
prevent, alive in the tool whose verdicts decide what ships.

This session paid the tuition twice on the neighbouring repo before touching
this one: a bar-replay of the old book validated at 47.7% against its own
recorded exits because it modelled a fixed bracket for a managed-exit system.
The lesson is structural, not procedural — the code that settles must BE the
code that replays, so agreement is a property, not a calibration result.

PinCase is the contract that made the extraction safe: the expected values
below were generated from execsim.run BEFORE the walk was extracted, and the
refactored engine must reproduce every field to the digit. AgreementCase is
the prize: the harness's hold cell now matches execsim's settlements
identically, because they are the same walk.
"""
import json
import unittest
import tempfile
from decimal import Decimal
from pathlib import Path

from engine import abtest, costs, execsim, store
from engine.setups import SETUP_VERSION

TF, TFS = "1H", 3600
T0 = 1_700_000_000

BANDS = {
    "A_tp": 100, "B_sl": 200, "C_ambig": 300, "D_timeout": 400,
    "E_missed": 500, "G_cross": 700, "H_short": 800,
}
N = 130

# Generated from execsim.run BEFORE the walk was extracted (scratchpad
# pin_execsim.py, 2026-08-04). Every figure is the CURRENT engine's own
# answer; the refactor is only a refactor while all of them still hold.
EXPECTED = json.loads("""
{
 "A_tp": {"counts": {"TP": 1},"facts": [{"outcome": "TP","entry": "101","exit_price": "104","effective_exit_price": "104","fees_price_units": "0.0205","funding_price_units": "0.002525","r_multiple": "0.99","r_gross": "1.00","costs_r": "0.01","bars_held": 2,"bars_to_fill": 0,"ambiguous_bar": false,"entry_fee_role": "MAKER","exit_fee_role": "MAKER","mae_r": "0.50","mfe_r": "1.07","holding_hours": "2"}]},
 "B_sl": {"counts": {"SL": 1},"facts": [{"outcome": "SL","entry": "201","exit_price": "197","effective_exit_price": "197","fees_price_units": "0.1383","funding_price_units": "0.0075375","r_multiple": "-1.04","r_gross": "-1.00","costs_r": "0.04","bars_held": 3,"bars_to_fill": 0,"ambiguous_bar": false,"entry_fee_role": "MAKER","exit_fee_role": "TAKER","mae_r": "1.12","mfe_r": "0.05","holding_hours": "3"}]},
 "C_ambig": {"counts": {"SL": 1},"facts": [{"outcome": "SL","entry": "301","exit_price": "297","effective_exit_price": "297","fees_price_units": "0.2083","funding_price_units": "0.0037625","r_multiple": "-1.05","r_gross": "-1.00","costs_r": "0.05","bars_held": 1,"bars_to_fill": 0,"ambiguous_bar": true,"entry_fee_role": "MAKER","exit_fee_role": "TAKER","mae_r": "1.75","mfe_r": "1.25","holding_hours": "1"}]},
 "D_timeout": {"counts": {"TIMEOUT": 1},"facts": [{"outcome": "TIMEOUT","entry": "401","exit_price": "400","effective_exit_price": "399.9749926860","fees_price_units": "0.28008499561160","funding_price_units": "0.4962375","r_multiple": "-0.18","r_gross": "-0.10","costs_r": "0.08","bars_held": 99,"bars_to_fill": 0,"ambiguous_bar": false,"entry_fee_role": "MAKER","exit_fee_role": "TAKER","mae_r": "0.15","mfe_r": "0.02","holding_hours": "99"}]},
 "E_missed": {"counts": {"MISSED": 1},"facts": [{"outcome": "MISSED","entry": "505","exit_price": null,"effective_exit_price": null,"fees_price_units": null,"funding_price_units": null,"r_multiple": "0","r_gross": "0","costs_r": "0","bars_held": 0,"bars_to_fill": null,"ambiguous_bar": false,"entry_fee_role": null,"exit_fee_role": null,"mae_r": null,"mfe_r": null,"holding_hours": null}]},
 "G_cross": {"counts": {"TIMEOUT": 1},"facts": [{"outcome": "TIMEOUT","entry": "700","exit_price": "700","effective_exit_price": "699.9749989490","fees_price_units": "0.83998499936940","funding_price_units": "0.8662500","r_multiple": "-0.29","r_gross": "0.00","costs_r": "0.29","bars_held": 99,"bars_to_fill": 2,"ambiguous_bar": false,"entry_fee_role": "TAKER","exit_fee_role": "TAKER","mae_r": "0.08","mfe_r": "0.00","holding_hours": "99"}]},
 "H_short": {"counts": {"TP": 1},"facts": [{"outcome": "TP","entry": "799","exit_price": "796","effective_exit_price": "796","fees_price_units": "0.1595","funding_price_units": "0.019975","r_multiple": "0.94","r_gross": "1.00","costs_r": "0.06","bars_held": 2,"bars_to_fill": 0,"ambiguous_bar": false,"entry_fee_role": "MAKER","exit_fee_role": "MAKER","mae_r": "0.33","mfe_r": "1.07","holding_hours": "2"}]}}
""")


def sym_of(k):
    return k.replace("_", "").upper() + "USDT"     # -> phemex-perp economics


def entry_model_of(k):
    """What the PLAN declares — the only thing execsim consults, so the only
    thing a replay reproducing execsim may consult."""
    return "MAKER_THEN_MARKET" if k == "G_cross" else None


def bars(k, base):
    out = []
    for i in range(N):
        o = h = c = base
        lo = base - 0.5
        if k == "A_tp":
            if i == 1: h = base + 1.2
            if i == 3: h = base + 4.2
        if k == "B_sl":
            if i == 1: h = base + 1.2
            if i == 4: lo = base - 3.5
        if k == "C_ambig":
            if i == 1: h = base + 1.2
            if i == 2: h, lo = base + 6, base - 6
        if k == "D_timeout":
            if i == 1: h = base + 1.2
        if k == "G_cross":
            if i == 1: h = base + 0.2
        if k == "H_short":
            if i == 1: lo = base - 1.2
            if i == 3: lo = base - 4.2
        out.append((o, h, lo, c))
    return out


def brackets(k, base):
    long = k != "H_short"
    if k == "A_tp":      e, sl, tp = base + 1, base - 2, base + 4
    elif k == "B_sl":    e, sl, tp = base + 1, base - 3, base + 9
    elif k == "C_ambig": e, sl, tp = base + 1, base - 3, base + 5
    elif k == "D_timeout": e, sl, tp = base + 1, base - 9, base + 9
    elif k == "E_missed":  e, sl, tp = base + 5, base - 2, base + 9
    elif k == "G_cross":   e, sl, tp = base + 1, base - 6, base + 9
    else:                  e, sl, tp = base - 1, base + 2, base - 4
    return long, e, sl, tp


def build_book(con):
    for k, base in BANDS.items():
        sym = sym_of(k)
        for i, (o, h, lo, c) in enumerate(bars(k, base)):
            con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (sym, TF, T0 + i * TFS, str(o), str(h), str(lo), str(c),
                         "1", "test", T0 + i * TFS))
        long, e, sl, tp = brackets(k, base)
        payload = {"setup_id": f"{sym}|{TF}|TEST|{T0}", "state": "VALIDATED",
                   "strategy": "PULLBACK",
                   "direction": "LONG" if long else "SHORT",
                   "entry": str(e), "sl": str(sl), "tp": str(tp)}
        if k == "G_cross":
            payload["entry_model"] = "MAKER_THEN_MARKET"
            payload["maker_limit"] = str(base - 2)
            payload["maker_wait_bars"] = 2
        store.insert_fact(con, symbol=sym, tf=TF, kind="setup",
                          market_time=T0, confirmed_at=T0 + TFS,
                          algo_version=SETUP_VERSION, payload=payload)
    con.commit()


class PinCase(unittest.TestCase):
    """The engine after the extraction is the engine before it, to the digit."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "pin.db")
        build_book(self.con)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_every_settlement_field_is_unchanged(self):
        for k in BANDS:
            sym = sym_of(k)
            r = execsim.run(self.con, sym, TF, TFS)
            with self.subTest(case=k):
                for outcome, n in EXPECTED[k]["counts"].items():
                    self.assertEqual(r[outcome], n, f"{k}: {outcome} count moved")
                facts = [json.loads(row["payload"]) for row in store.get_facts(
                    self.con, sym, TF, "exec", execsim.EXEC_VERSION)]
                self.assertEqual(len(facts), len(EXPECTED[k]["facts"]))
                for got, want in zip(facts, EXPECTED[k]["facts"]):
                    for field, val in want.items():
                        self.assertEqual(got.get(field), val,
                                         f"{k}.{field}: {got.get(field)!r} != {val!r}")


class WalkCase(unittest.TestCase):
    """The extracted walk, held to the conventions the inline code enforced."""

    def test_ambiguous_bar_is_the_stop(self):
        c = [{"open_ts": i, "high": Decimal(130), "low": Decimal(70),
              "close": Decimal(100)} for i in range(3)]
        out = execsim.walk_exit(c, 0, Decimal(90), Decimal(120), True)
        self.assertEqual((out[0], out[3]), ("SL", True),
                         "a bar reaching both levels must settle as the stop")

    def test_open_is_none_never_zero(self):
        c = [{"open_ts": i, "high": Decimal(101), "low": Decimal(99),
              "close": Decimal(100)} for i in range(3)]
        self.assertIsNone(execsim.walk_exit(c, 0, Decimal(90), Decimal(120), True),
                          "running out of data is OPEN, not a result")

    def test_timeout_exits_at_the_window_close(self):
        c = [{"open_ts": i, "high": Decimal(101), "low": Decimal(99),
              "close": Decimal("100.5")} for i in range(execsim.MAX_BARS + 5)]
        out = execsim.walk_exit(c, 0, Decimal(90), Decimal(120), True)
        self.assertEqual(out[0], "TIMEOUT")
        self.assertEqual(out[2], execsim.MAX_BARS - 1)
        self.assertEqual(out[1], Decimal("100.5"))

    def test_settle_funding_is_zero_on_spot_and_real_on_perps(self):
        """The drift this unification closes: the harness never charged
        funding. The one costing function now does, keyed on the venue."""
        prof = costs.profile_for("BTCUSDT")
        kw = dict(entry=Decimal(100), exit_price=Decimal(104), risk=Decimal(2),
                  long=True, outcome="TP", bars_held=24, tf_seconds=3600,
                  atr_exit=Decimal(1), entry_role="MAKER")
        perp = execsim.settle(prof, "BTCUSDT", **kw)
        spot = execsim.settle(costs.profile_for("BTC-USD"), "BTC-USD", **kw)
        self.assertGreater(perp["funding"], 0, "a perp held 24h pays funding")
        self.assertEqual(spot["funding"], 0, "spot pays no funding, by venue")


class AgreementCase(unittest.TestCase):
    """The prize: the harness's hold cell and execsim agree because they ARE
    the same walk — every outcome and every R, not within tolerance, equal.

    G_cross used to be EXCLUDED here, on the reasoning that "the cross entry leg
    is execsim's own model; the harness's entry variants are deliberately
    different experiments and are not asked to reproduce it." True of a variant
    cell, false of the CALIBRATION cell, which replays the engine's own declared
    entry model and is asked for exactly that. So the one case that would have
    caught a +0.1207 R/trade divergence on every crossed order was the one case
    the test skipped, and it was found by a red calibration instead.

    The entry model is now taken from the PLAN, as execsim takes it, and every
    band including the cross must agree.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "agree.db")
        build_book(self.con)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_hold_cell_reproduces_execsim_exactly(self):
        for k in BANDS:
            sym = sym_of(k)
            execsim.run(self.con, sym, TF, TFS)
            exec_by_id = {}
            for row in store.get_facts(self.con, sym, TF, "exec",
                                       execsim.EXEC_VERSION):
                p = json.loads(row["payload"])
                exec_by_id[p["setup_id"]] = p
            got = abtest.run_variant(self.con, [sym], [TF], SETUP_VERSION,
                                     managed=False,
                                     entry_model=entry_model_of(k))
            with self.subTest(case=k):
                self.assertEqual(len(got), 1)
                g = got[0]
                e = exec_by_id[g["setup_id"]]
                if e["outcome"] == "MISSED":
                    self.assertFalse(g["filled"])
                    self.assertEqual(g["outcome"], "MISSED")
                    continue
                self.assertEqual(g["outcome"], e["outcome"])
                self.assertEqual(str(g["r"]), e["r_multiple"],
                                 f"{k}: the harness and the engine settled the "
                                 f"same trade for different money")
                self.assertEqual(g["bars_held"], e["bars_held"])

    def test_the_crossing_leg_is_where_they_used_to_disagree(self):
        """Name the specific defect, so a re-introduction fails HERE with a
        readable message rather than as one row of a 499-trade join.

        Asserted against literals, not against the other caller — once both go
        through `simulate_entry`, an agreement test cannot detect a bug INSIDE
        it, only a fork away from it. These numbers are the engine's own.

        The old harness crossed at bar `ci+1` and paid the PLAN's entry price
        against the PLAN's risk denominator. The engine crosses once the passive
        window has closed — `order_i + maker_wait_bars`, here ci+3 — at that
        bar's own open. On this band the plan entry is 701 against a stop at
        694, so the plan risk is 7 and the fill's is 6: a replay reading the
        plan reports every crossed trade against a denominator 17% too large.
        """
        sym = sym_of("G_cross")
        execsim.run(self.con, sym, TF, TFS)
        e = next(json.loads(r["payload"])
                 for r in store.get_facts(self.con, sym, TF, "exec",
                                          execsim.EXEC_VERSION))
        g = abtest.run_variant(self.con, [sym], [TF], SETUP_VERSION,
                               managed=False,
                               entry_model="MAKER_THEN_MARKET")[0]
        self.assertEqual(e["entry"], "700",
                         "the engine fills the cross at the crossing bar's open")
        self.assertNotEqual(e["entry"], "701", "...not at the plan's entry")
        self.assertEqual(e["bars_to_fill"], 2,
                         "the cross fires after the passive window, not on the "
                         "bar the order was placed")
        self.assertEqual(str(g["r"]), e["r_multiple"],
                         "the replay must price the crossing leg the engine's "
                         "way — same bar, same price, same risk denominator")


if __name__ == "__main__":
    unittest.main()
