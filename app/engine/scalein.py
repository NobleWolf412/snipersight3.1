"""Scale-in playbook — LTF adds inside an active HTF setup. algo scale-v0.1-draft.

Draft answer to §30 item 9 (HTF influence): the higher timeframe GATES the
lower — a 1H trigger means nothing unless a 1D/4H setup is currently open in
the same direction.

Rules (versioned; pending user ratification):
- Parent: a VALIDATED 1D/4H setup, from its trigger bar until its exec exit.
- Trigger: a 1H BOS in the parent's direction, confirmed inside that window,
  whose close has already moved >= 1 parent-R beyond the parent entry (the
  add is bought with the market's progress, not with hope).
- Add bracket: entry = the 1H break close; SL = the PARENT ENTRY (breakeven
  line of the original position); TP = parent TP. Fee gate applies to the add
  itself (same K as setups). Max 2 adds per parent.
- SCALE-1 (honest caveat): the parent position keeps its ORIGINAL bracket in
  the exec sim — full trail-to-breakeven accounting for the parent needs a
  stateful position manager (exec v0.6+). Until then, adds are risk-governed
  as additional exposure by the risk authority (half-size, exposure-capped).
"""
import json
from decimal import Decimal

from . import store
from .swings import compute_atr
from .structure import STRUCTURE_VERSION
from .setups import SETUP_VERSION, MIN_RISK_COST_MULT, Q2, _fp
from . import costs
from .execsim import EXEC_VERSION
from .runlog import RunRecorder

SCALE_VERSION = "scale-v0.19-draft"
# v0.19: cascade from setup-v0.21/exec-v0.25/risk-v0.26 (the chart-eye read
# upstream). No rule change.
# v0.18: cascade from setup-v0.20/exec-v0.24/risk-v0.25 (the context reading
# upstream) — adds only join positions the simulator says are open. No rule
# change.
# v0.17: input cascade from agg-v0.2 via setup-v0.19/exec-v0.23/risk-v0.23 —
# adds only join positions the simulator says are open. No rule change.
# v0.16: cascade from setup-v0.18 / exec-v0.22 / risk-v0.22 (R-denominated
# envelope). Adds are 0R under the autonomous contract — risk.run REJECTS
# them with SCALE_IN_FORBIDDEN(0R) rather than approving them at zero size —
# but the parent generations moved, so this tag moves with them.
# v0.15: cascade from setup-v0.17 / exec-v0.21 (the top-down bias block
# upstream). Parents are SETUP_VERSION setups and an add is only placed against
# a position exec says is open, so both input generations moved under it.
#
# Its adds carry NO bias block of their own, deliberately, and it is named in
# `tests/test_bias.py` PENDING with this reason: an add inherits its parent's
# bracket and already answers to the strictest higher-timeframe rule in the
# system — no add exists without an open 4H/1D parent in the same direction. A
# second policy here would be a second authority over one question, which is
# the thing `engine/bias.py` was written to stop.
# v0.14: cascade from setup-v0.16 / exec-v0.20 (magnitude-scaled WHY prices
# upstream) — and the add's own WHY takes the same fix: the BOS price printed
# at a flat .2f, which on a sub-dollar symbol reads "BOS at 0.09".
# v0.13: cascade from setup-v0.15 / exec-v0.19 / structure-v0.12 (the same-bar
# pivot-pair fix upstream).
# v0.12: cascade from setup-v0.14 / exec-v0.18 / structure-v0.11 (swing-v0.9 at
# the root). An add is only placed against a position the simulator says is
# open, and its structure reads moved generation with the rest.
# v0.11: the add's economics gate is priced on the ADD'S OWN VENUE. It imported
# setups.COST_PROFILE — the process-wide Coinbase default — so every scale-in on
# a perp had to clear a gate built from fees ~14x higher than the venue charges.
# Decisions differ, hence the bump.
# v0.8: cascade from exec-v0.14. An add is only placed against a position the
# simulator says is open, so a corrected fill price changes which adds exist and
# what they are worth.
# v0.7: parents are setup-v0.11; windows close on exec-v0.13 exits.

# v0.6: parent windows close on exec-v0.12 exits.

# v0.5: parents are setup-v0.10; windows close on exec-v0.11 exits.

# v0.4: parents are setup-v0.9 setups; windows close on exec-v0.10 exits.

# v0.3: same reason as risk-v0.8. Parents are SETUP_VERSION setups and the
# window closes on EXEC_VERSION exits; S40 moved both, so the adds differ.

PARENT_TFS = ("4H", "1D")
TRIGGER_TF = "1H"
TRIGGER_MIN_R = Decimal(1)
MIN_ADD_RR = Decimal(1)
MAX_ADDS = 2


def run(con, symbol: str, tf: str = TRIGGER_TF, tf_seconds: int = 3600) -> dict:
    # pipeline-compatible signature; this engine only acts on the trigger TF
    if tf != TRIGGER_TF:
        return {"symbol": symbol, "parents": 0, "adds": 0}
    with RunRecorder(con, "scalein", SCALE_VERSION, symbol, TRIGGER_TF) as rec:
        candles_1h = [dict(r) for r in store.get_candles(con, symbol, TRIGGER_TF)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles_1h)}
        atr_1h = compute_atr(candles_1h)

        breaks = []
        for r in store.get_facts(con, symbol, TRIGGER_TF, "structure", STRUCTURE_VERSION):
            p = json.loads(r["payload"])
            if p["event"] in ("BOS", "CHOCH"):
                breaks.append({"market_time": r["market_time"],
                               "confirmed_at": r["confirmed_at"],
                               "direction": p["direction"],
                               "close": Decimal(p["close"])})
        breaks.sort(key=lambda b: b["confirmed_at"])

        exits = {}
        for tf in PARENT_TFS:
            for r in store.get_facts(con, symbol, tf, "exec", EXEC_VERSION):
                p = json.loads(r["payload"])
                exits[p["setup_id"]] = r["confirmed_at"]

        n_adds = 0
        n_parents = 0
        for tf in PARENT_TFS:
            for r in store.get_facts(con, symbol, tf, "setup", SETUP_VERSION):
                parent = json.loads(r["payload"])
                if parent["state"] != "VALIDATED":
                    continue
                n_parents += 1
                entry = Decimal(parent["entry"])
                sl, tp = Decimal(parent["sl"]), Decimal(parent["tp"])
                p_risk = abs(entry - sl)
                long = parent["direction"] == "LONG"
                w_start = r["confirmed_at"]
                w_end = exits.get(parent["setup_id"], 2**53)
                want_dir = "BULL" if long else "BEAR"
                adds = 0
                for b in breaks:
                    if adds >= MAX_ADDS:
                        break
                    if not (w_start < b["confirmed_at"] < w_end):
                        continue
                    if b["direction"] != want_dir:
                        continue
                    px = b["close"]
                    progressed = (px - entry) if long else (entry - px)
                    if progressed < TRIGGER_MIN_R * p_risk:
                        continue
                    risk_dist = abs(px - entry)          # SL sits at parent entry
                    i = ts_index.get(b["market_time"])
                    if i is None or atr_1h[i] is None or risk_dist <= 0:
                        continue
                    # the ADD trades on the same venue as its parent, so it is
                    # priced there — not on the process-wide spot default
                    est_cost = costs.estimated_round_trip_cost(
                        px, atr_1h[i], costs.profile_for(symbol))
                    if risk_dist < MIN_RISK_COST_MULT * est_cost:
                        continue
                    reward = (tp - px) if long else (px - tp)
                    if reward <= 0:
                        continue
                    rr = (reward / risk_dist).quantize(Q2)
                    if rr < MIN_ADD_RR:
                        continue
                    adds += 1
                    payload = {"setup_id": f"{parent['setup_id']}|ADD{adds}",
                               "strategy": "SCALE_IN", "direction": parent["direction"],
                               "parent_setup_id": parent["setup_id"],
                               "entry": str(px), "sl": str(entry), "tp": str(tp),
                               "rr": str(rr), "rank": 50,
                               "why": (f"add #{adds} on 1H {b['direction']} BOS at "
                                       f"{_fp(px)} inside active {tf} "
                                       f"{parent['strategy']} · stop at parent entry "
                                       f"(breakeven) · shared TP · R:R {rr}"),
                               "zone_id": parent.get("zone_id"), "regime": parent.get("regime"),
                               "state": "VALIDATED",
                               "manifest_hash": parent.get("manifest_hash"),
                               "cost_manifest_hash": parent.get("cost_manifest_hash")}
                    if store.insert_fact(con, symbol=symbol, tf=TRIGGER_TF, kind="setup",
                                         market_time=b["market_time"],
                                         confirmed_at=b["confirmed_at"],
                                         algo_version=SCALE_VERSION, payload=payload):
                        n_adds += 1

        con.commit()
        rec.n_inputs = n_parents
        rec.n_new_facts = n_adds
        return {"symbol": symbol, "parents": n_parents, "adds": n_adds}
