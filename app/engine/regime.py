"""Regime engine — market-state classification from structure facts.
algo regime-v0.1-draft.

Draft methodology (spec §25 subset; versioned):
- Inputs: structure facts (LABELs and BOS/CHOCH breaks) in confirmed_at order.
- Classification after each new fact, with evidence attached (§25: a primary
  regime plus supporting evidence, never a mystery score):
    BULL_TREND    last break BOS/BULL and last high-label HH and low-label HL
    BEAR_TREND    last break BOS/BEAR and last high-label LH and low-label LL
    WEAKENING_*   trend break pattern intact but latest label disagrees
    TRANSITION    last break is CHOCH
    RANGE         anything else (mixed labels, no directional break)
  COMPRESSION/EXPANSION/DISORDERED deferred (need volatility-state facts).
- A regime fact is emitted only when the classification CHANGES.
"""
import json

from . import store
from .structure import STRUCTURE_VERSION
from .runlog import RunRecorder

REGIME_VERSION = "regime-v0.8-draft"


def _classify(last_break, last_hi, last_lo):
    if last_break is None:
        return "RANGE"
    if last_break["event"] == "CHOCH":
        return "TRANSITION"
    d = last_break["direction"]
    if d == "BULL":
        if last_hi == "HH" and last_lo == "HL":
            return "BULL_TREND"
        if last_hi == "HH" or last_lo == "HL":
            return "WEAKENING_BULL"
    if d == "BEAR":
        if last_hi == "LH" and last_lo == "LL":
            return "BEAR_TREND"
        if last_hi == "LH" or last_lo == "LL":
            return "WEAKENING_BEAR"
    return "RANGE"


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "regime", REGIME_VERSION, symbol, tf) as rec:
        facts = []
        for r in store.get_facts(con, symbol, tf, "structure", STRUCTURE_VERSION):
            p = json.loads(r["payload"])
            facts.append({"market_time": r["market_time"],
                          "confirmed_at": r["confirmed_at"], **p})
        facts.sort(key=lambda f: (f["confirmed_at"], f["market_time"]))
        rec.n_inputs = len(facts)

        n_changes = 0
        last_break = None
        last_hi = last_lo = None
        current = None
        for f in facts:
            if f["event"] == "LABEL":
                if f["type"] == "HIGH":
                    last_hi = f["label"]
                else:
                    last_lo = f["label"]
            else:
                last_break = f
            regime = _classify(last_break, last_hi, last_lo)
            if regime == current:
                continue
            current = regime
            payload = {"regime": regime,
                       "evidence": {
                           "last_break": None if last_break is None else
                           {"event": last_break["event"],
                            "direction": last_break.get("direction"),
                            "at": last_break["market_time"]},
                           "last_high_label": last_hi,
                           "last_low_label": last_lo,
                           "trigger": {"event": f["event"], "at": f["market_time"]}}}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="regime",
                                 market_time=f["market_time"],
                                 confirmed_at=f["confirmed_at"],
                                 algo_version=REGIME_VERSION, payload=payload):
                n_changes += 1

        con.commit()
        rec.n_new_facts = n_changes
        return {"symbol": symbol, "tf": tf, "changes": n_changes}
