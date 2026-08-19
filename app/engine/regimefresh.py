"""Regime freshness — how stale was the label this trade was gated on? READ-ONLY.

PULLBACK's short leg loses money on this book: n=1,136, mean -0.546 R, and the
loss does not live in the geometry. The bracket is provably fair — under a
driftless walk the entry/sl/tp triple implies P(target) of 25.4% for PULLBACK
SHORT against 25.5% / 25.7% / 27.2% for the other three strategy-direction
groups, a spread of under two points where the realised win rates spread
nineteen. Widening the stop does not rescue it either: from the tightest to the
widest quartile on 1H the short only improves from -0.83 R to -0.28 R.

What differs is WHEN the trade fires relative to the label that let it fire.

A regime label cannot exist until the move that defines it has finished
printing. `regime.py`'s BEAR_TREND needs a confirmed break plus a confirmed LH
plus a confirmed LL, so the label lands 24-42 bars after its own trigger event
(measured: 28.3 bars on 15m, 41.9 on 1H, 23.7 on 4H, 29.7 on 1D). The setup
then fires a median 68 bars later again on WEAKENING_BEAR, 159 on BEAR_TREND.

PULLBACK is a counter-move entry by design: it buys a dip. On the long side the
dip is a discount. On the short side the same rule SELLS A RALLY — into a bear
call the market may already have undone. That is the hypothesis. It is NOT a
finding, and an earlier version of this docstring stated three cohort figures
as though it were; those came from a scratch analysis that this module never
reproduced, and they are withdrawn.

WHY A RECONSTRUCTION HERE CAN LIE, and what is done about it. The store holds
THIRTEEN regime versions. A later version re-runs over old candles and writes
its own label for dates a trade was already taken on, so "the regime at time T"
has more than one answer depending on which version is asked. Measured against
the engine's own recorded regime (the `details.regime` on every
NO_ELIGIBLE_PLAYBOOK rejection, which is the value the gate actually read):

    reconstruct with the CURRENT regime version only ... 68.4% match
    reconstruct with ALL versions, newest confirmed wins  84.6% match
    the same, restricted to the CURRENT setup version .. 99.8% match

Only the last is honest, and it is what `grade()` measures: load_candidates is
scoped to the current setup version, and `_regime_series` to the current regime
version, so engine and reconstruction were live together. `verify()` proves
that on the operator's own book rather than asserting it — run it first, and
distrust any split whose reconstruction does not clear its floor.

WHY THIS IS A MEASUREMENT AND NOT A FIX. Two things this codebase has already
auditioned came back INVERTED — btcalign graded OPPOSED at +0.536 R against
ALIGNED at -0.244 R, and BIAS_POLICY graded AGAINST at +0.2755 R against WITH
at -0.0736 R. Both were the obvious rule. Both were backwards. A third rule
that reads just as obviously ("do not trade a stale label") has not earned a
different standard, and §6 rule 7 is explicit: evidence is recorded, not
filtered on, until it has been graded.

WHAT MAKES IT A CANDIDATE RATHER THAN HINDSIGHT. Every field stamped here is
knowable BEFORE the entry. The label's own lateness is `confirmed_at` minus its
trigger event, both on the fact. Its age is the gap to the setup's own
confirmation. Supersession is whether a newer regime fact was confirmed first.
Nothing here reads a candle the trade had not seen, and nothing reads a fact
confirmed after the moment being described (§6 rule 3).

If a split one day clears the floor, gating is a SEPARATE, deliberate change:
a setups version bump, five tags moving together, and the forward record
restarting from its current 49 trades. A decision for the operator, never a
side effect of this file.

Usage (from app/):
  python -m engine.regimefresh            # grade against the current book
  python -m engine.regimefresh --json
"""
import json
import sqlite3

from . import store
from .regime import REGIME_VERSION

#: The floor `verify()` must clear before any split here is worth reading. Set
#: at the measured 99.8% rather than 100%: 13 of 5,940 genuinely disagree, and
#: a reconstruction that demanded perfection would fail on its own rounding.
VERIFY_FLOOR = 0.99

#: The staleness cut, in the label's own bars. Chosen as the measured median
#: wait rather than tuned: PULLBACK fires a median 68 bars after a
#: WEAKENING_BEAR label and 159 after BEAR_TREND. A threshold fitted to the
#: outcome would be the curve-fit this module exists to avoid, so the split
#: below reports the raw ages too and lets the grading argue about the cut.
STALE_AFTER_BARS = 68

#: Seconds per bar, for turning an age in seconds into an age in bars without
#: re-deriving a candle. Timeframes the scanner does not run are absent by
#: design: an unknown timeframe yields no age flag rather than a guessed one.
TF_SECONDS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400,
              "1D": 86400, "1W": 604800}


def trigger_at(payload: dict) -> int | None:
    """The market event that defined this label, or None when unrecorded.

    regime.py writes `evidence.trigger.at` — the swing or break that made the
    call. The gap between that and the fact's own confirmed_at is the label's
    lateness, and it is the only part of staleness that belongs to the label
    rather than to the setup that later read it.
    """
    trigger = ((payload or {}).get("evidence") or {}).get("trigger") or {}
    at = trigger.get("at")
    return int(at) if isinstance(at, (int, float)) else None


def _regime_series(con, symbol: str, tf: str) -> list[tuple[int, str, int | None]]:
    """(confirmed_at, regime, trigger_at) for one market, in confirmation order."""
    out = []
    for r in store.get_facts(con, symbol, tf, "regime", REGIME_VERSION):
        payload = json.loads(r["payload"])
        out.append((r["confirmed_at"], payload.get("regime"), trigger_at(payload)))
    out.sort()
    return out


def label_asof(series, ts: int):
    """The governing label at `ts`, and whether a newer one had already landed.

    Returns (regime, confirmed_at, trigger_at, superseded). `superseded` is
    True when a LATER regime fact was also confirmed at or before `ts` — the
    gate read one label while a newer one already existed. Both halves are
    knowable at `ts`; neither reads forward.
    """
    current = None
    seen = 0
    for confirmed_at, regime, trig in series:
        if confirmed_at > ts:
            break
        seen += 1
        current = (regime, confirmed_at, trig)
    if current is None:
        return None, None, None, None
    regime, confirmed_at, trig = current
    # Superseded means the label that GATED the trade is not this newest one.
    # We cannot know which fact the gate read, so the honest reading is: a
    # regime older than the newest is what a lagging playbook acts on, and the
    # count above tells us whether any newer one existed. Reported as a flag on
    # the newest label's own age instead — see `annotate`.
    return regime, confirmed_at, trig, seen


def annotate(con, candidates: list[dict]) -> int:
    """Stamp regime-freshness fields onto candidate payloads, in place.

    Mutates payloads the same way `factorstats.load_candidates` surfaces
    tf/symbol, and returns how many were annotated. Candidates confirmed before
    their market's first regime fact are left untouched and land in
    outcome_split's MISSING bucket, which exists so that "we did not look"
    cannot launder itself into "we looked and it was not there".
    """
    series: dict[tuple[str, str], list] = {}
    n = 0
    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or not tf:
            continue
        key = (symbol, tf)
        if key not in series:
            series[key] = _regime_series(con, symbol, tf)
        regime, confirmed_at, trig, _seen = label_asof(series[key], c["confirmed_at"])
        if regime is None:
            continue
        p["regime_asof"] = regime
        # How late the LABEL was: its own confirmation, minus the event it names.
        if trig is not None:
            p["regime_lag_s"] = max(0, confirmed_at - trig)
        # How long the SETUP then waited on it.
        age_s = max(0, c["confirmed_at"] - confirmed_at)
        p["regime_age_s"] = age_s
        secs = TF_SECONDS.get(tf)
        if secs:
            p["regime_age_bars"] = age_s / secs
        n += 1
    return n


def verify(con, *, setup_version: str | None = None) -> dict:
    """Prove the reconstruction against the engine's own recorded regime.

    The gate writes the label it read onto every NO_ELIGIBLE_PLAYBOOK
    rejection, under `details.regime`. That is ground truth: not a later
    re-derivation, but the value the decision was made on. This replays
    `label_asof` at the same confirmed_at and reports how often it agrees.

    It exists because the first version of this module did NOT agree — 68.4%
    over the whole book — and reported a result anyway. A reconstruction that
    silently reads a different label than the engine did is not a weaker
    measurement, it is a measurement of something else.
    """
    from .setups import SETUP_VERSION
    version = setup_version or SETUP_VERSION
    cache: dict[tuple[str, str], list] = {}
    agree = wrong = absent = 0
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT symbol, tf, confirmed_at, payload FROM facts "
        "WHERE kind='setup_rejection' AND algo_version=?", (version,))
    for r in rows:
        payload = json.loads(r["payload"])
        if payload.get("reason") != "NO_ELIGIBLE_PLAYBOOK":
            continue
        truth = (payload.get("details") or {}).get("regime")
        if truth is None:
            continue
        key = (r["symbol"], r["tf"])
        if key not in cache:
            cache[key] = _regime_series(con, r["symbol"], r["tf"])
        mine, _, _, _ = label_asof(cache[key], r["confirmed_at"])
        if mine is None:
            absent += 1
        elif mine == truth:
            agree += 1
        else:
            wrong += 1
    n = agree + wrong + absent
    rate = (agree / n) if n else None
    return {"setup_version": version, "n": n, "agree": agree, "wrong": wrong,
            "no_label": absent, "match_rate": rate,
            "trustworthy": bool(rate is not None and rate >= VERIFY_FLOOR)}


def factor_extractors(payload: dict) -> dict[str, float]:
    """0/1 flags for outcome_split. Absent when unannotated, so MISSING stays
    honest — an unreadable regime history is not a fresh one."""
    if "regime_asof" not in payload:
        return {}
    out: dict[str, float] = {}
    bars = payload.get("regime_age_bars")
    if bars is not None:
        out["regime_stale"] = 1.0 if bars >= STALE_AFTER_BARS else 0.0
        out["regime_fresh"] = 1.0 if bars < STALE_AFTER_BARS else 0.0
    lag = payload.get("regime_lag_s")
    if lag is not None and payload.get("tf") in TF_SECONDS:
        late_bars = lag / TF_SECONDS[payload["tf"]]
        # The label's OWN lateness, separate from how long the setup waited.
        # Split at 24 bars: the fastest measured mean confirmation lag across
        # timeframes was 23.7, so below it is "as prompt as this classifier
        # gets" rather than a fitted threshold.
        out["label_late"] = 1.0 if late_bars >= 24 else 0.0
    return out


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    """The whole audition: load, annotate, split, and say what held."""
    from . import factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    # THE RECONSTRUCTION IS CHECKED BEFORE IT IS USED. The first version of
    # this module reported a split built on a 68% match and called the sign
    # meaningful; the split was real, the labels underneath it were not.
    proof = verify(con, setup_version=setup_version)
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    annotated = annotate(con, candidates)
    splits = {name: factorstats.outcome_split(candidates, name,
                                              factors=factor_extractors)
              for name in ("regime_stale", "regime_fresh", "label_late")}
    return {"derived_at_analysis_time": True,   # no fact written, no gate armed
            "reconstruction": proof,
            "annotated": annotated, "candidates": len(candidates),
            "warnings": warnings, "splits": splits}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    con = sqlite3.connect(store.DB_PATH)
    try:
        result = grade(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    proof = result["reconstruction"]
    rate = proof["match_rate"]
    shown = f"{rate:.1%}" if rate is not None else "no ground truth"
    print(f"reconstruction vs the engine's own recorded regime: {shown} "
          f"of {proof['n']:,} gated decisions")
    if not proof["trustworthy"]:
        print("  *** BELOW THE FLOOR. The labels under the split below are not "
              "the ones the engine read. Do not quote these numbers. ***")
    print(f"regime freshness — {result['annotated']} of {result['candidates']} "
          f"candidates annotated")
    for name, split in result["splits"].items():
        print(f"\n  {name}")
        for group, stats in (split.get("groups") or {}).items():
            n = stats.get("n", 0)
            mean = stats.get("mean_r")
            shown = f"{mean:+.3f} R" if isinstance(mean, (int, float)) else "—"
            print(f"    {group:<10} n={n:<6} {shown}")
    print("\nNOT A GATE. Evidence is recorded, not filtered on, until it has "
          "been graded (rule 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
