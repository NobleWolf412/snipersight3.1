"""Regime reading — what the market is doing NOW, not what label it last earned.
A LIBRARY, not an engine: writes no facts, has no run().

WHY THIS EXISTS. `regime.py` classifies from the last break and the last two
labels. That is a true statement about structure and a poor statement about
the present: BULL_TREND lands 24-42 bars after its trigger (regimefresh), and
TRANSITION means only "the last break was a CHoCH" — with no direction, no
distance travelled since, no volatility state and no age. A market that rips
25% in three days without a pullback never confirms a higher low, so it reads
TRANSITION the whole way up, and TRANSITION plus a supply touch is the
REVERSAL short. Measured 2026-09-03: 76% of REVERSAL shorts were placed into a
symbol already up >=2%/24h, at -0.15R against +0.14R for the rest, and the
funded book had shorted a +5% BTC day three times in one afternoon.

WHAT IT READS, all as-of, all from facts and candles the store already holds:

    regime            the structural label (regime.py), unchanged
    label_age_bars    bars since the label's own trigger — how stale it is
    last_break        event, direction, bars since, and DISPLACEMENT: how far
                      price has travelled from the break level, in ATR, signed
                      so that positive means "kept going the break's way"
    vol               ATR percentile regime and squeeze state (volatility.py)
    phase             ONE word for the above, defined below

THE PHASE VOCABULARY, fixed before the first grade so the grade cannot name
its own teacher. Direction is carried on every phase that has one, which is
the whole point — TRANSITION had none.

    TREND_UP / TREND_DOWN          a confirmed trend, price within EXTENDED_ATR
                                   of its last break
    TREND_UP_EXTENDED / _DOWN_..   the same trend, price >= EXTENDED_ATR beyond
                                   its last break — the dip you buy here is late
    TURN_UP / TURN_DOWN            a fresh CHoCH (<= FRESH_BARS old) in that
                                   direction, price still near the break
    IMPULSE_UP / IMPULSE_DOWN      a CHoCH that price has since RUN from by
                                   >= IMPULSE_ATR — the vertical move regime.py
                                   calls TRANSITION forever. This is the label
                                   the 2026-08-19..21 rally and 2026-09-03
                                   should have carried.
    DRIFT_UP / DRIFT_DOWN          an aged CHoCH (> FRESH_BARS) that never
                                   became an impulse — direction known, energy
                                   gone
    RANGE                          regime.py's RANGE
    UNKNOWN                        no regime fact yet

A phase never gates anything here. It is stamped at analysis time by
`annotate()` and graded by `factorstats.outcome_split`; recording it on setup
facts is a versioned setups change, and reading it in a playbook is a further
one. Rule 7.

WHAT THE CONSTANTS ARE NOT. FRESH_BARS, IMPULSE_ATR and EXTENDED_ATR were
chosen from the desk definitions ("a fresh break is a few bars old"; "three
ATR is a move, not a wobble") before any cell was read. They are not tuned to
this book. If a later version moves one, it is a REGIMEREAD_VERSION bump and
the annotate grade is re-run, not quietly re-fit.
"""
import bisect
import json
from decimal import Decimal

from . import store
from .regime import REGIME_VERSION
from .structure import STRUCTURE_VERSION
from .swings import compute_atr
from .volatility import VOLATILITY_VERSION

REGIMEREAD_VERSION = "regimeread-v0.1-draft"

#: A CHoCH this many bars old or younger is FRESH — the turn just printed.
FRESH_BARS = 12
#: Price this many ATR beyond a CHoCH level is an IMPULSE: the turn ran.
IMPULSE_ATR = Decimal(3)
#: Price this many ATR beyond a trend's last break is EXTENDED: the dip is late.
EXTENDED_ATR = Decimal(3)

_TREND = {"BULL_TREND": "UP", "WEAKENING_BULL": "UP",
          "BEAR_TREND": "DOWN", "WEAKENING_BEAR": "DOWN"}
_DIR = {"BULL": "UP", "BEAR": "DOWN"}
Q2 = Decimal("0.01")


def _as_of(series, ts):
    """Last (confirmed_at, ...) row confirmed at or before ts, or None.
    The lookahead guard: confirmed_at is when the engine could have known."""
    i = bisect.bisect_right([s[0] for s in series], ts)
    return series[i - 1] if i else None


def phase_of(regime, brk, displacement_atr, bars_since_break) -> str:
    """The one word. Pure, so a test can pin every branch without a store."""
    if regime is None:
        return "UNKNOWN"
    side = _TREND.get(regime)
    if side:
        if displacement_atr is not None and displacement_atr >= EXTENDED_ATR:
            return f"TREND_{side}_EXTENDED"
        return f"TREND_{side}"
    if regime == "TRANSITION" and brk is not None:
        d = _DIR.get(brk.get("direction"))
        if d is None:
            return "RANGE"
        if displacement_atr is not None and displacement_atr >= IMPULSE_ATR:
            return f"IMPULSE_{d}"
        if bars_since_break is not None and bars_since_break <= FRESH_BARS:
            return f"TURN_{d}"
        return f"DRIFT_{d}"
    return "RANGE"


def phase_side(phase: str):
    """UP / DOWN carried by a phase, or None (RANGE, UNKNOWN)."""
    for s in ("UP", "DOWN"):
        if f"_{s}" in phase:
            return s
    return None


class Reading:
    """One symbol/timeframe, loaded once, read many times as-of any moment."""

    def __init__(self, tf: str, tf_seconds: int, regimes, breaks, atr_regimes,
                 squeezes, candles=None):
        self.tf, self.tf_seconds = tf, tf_seconds
        self.regimes = regimes          # [(confirmed_at, market_time, regime)]
        self.breaks = breaks            # [(confirmed_at, market_time, {event,direction,level})]
        self.atr_regimes = atr_regimes  # [(confirmed_at, regime)]
        self.squeezes = squeezes        # [(confirmed_at, squeeze)]
        self._candles = candles or []
        self._opens = [c["open_ts"] for c in self._candles]
        self._atr = compute_atr(self._candles) if self._candles else []

    def _bar_closed_by(self, as_of):
        """Index of the last candle CLOSED at as_of, or None."""
        i = bisect.bisect_right(self._opens, as_of - self.tf_seconds)
        return i - 1 if i else None

    def at(self, as_of: int) -> dict:
        reg = _as_of(self.regimes, as_of)
        brk = _as_of(self.breaks, as_of)
        i = self._bar_closed_by(as_of)
        bar_ts = self._candles[i]["open_ts"] if i is not None else as_of
        atr = self._atr[i] if i is not None and i < len(self._atr) else None
        close = Decimal(self._candles[i]["close"]) if i is not None else None

        label_age = None
        if reg is not None:
            label_age = max(0, (bar_ts - reg[1]) // self.tf_seconds)

        last_break = None
        displacement = None
        bars_since = None
        if brk is not None:
            bars_since = max(0, (bar_ts - brk[1]) // self.tf_seconds)
            if atr and close is not None:
                level = Decimal(brk[2]["level"])
                raw = (close - level) / atr
                # signed: positive = price kept going the break's way
                displacement = (raw if brk[2]["direction"] == "BULL" else -raw).quantize(Q2)
            last_break = {"event": brk[2]["event"], "direction": brk[2]["direction"],
                          "bars_since": bars_since,
                          "displacement_atr": None if displacement is None else str(displacement)}

        a = _as_of(self.atr_regimes, as_of)
        s = _as_of(self.squeezes, as_of)
        regime = reg[2] if reg else None
        return {"regime": regime, "label_age_bars": label_age,
                "last_break": last_break,
                "vol": {"atr_regime": a[1] if a else None,
                        "squeeze": s[1] if s else None},
                "phase": phase_of(regime, brk[2] if brk else None, displacement, bars_since),
                "version": REGIMEREAD_VERSION}


def load(con, symbol: str, tf: str, tf_seconds: int, candles=None) -> Reading:
    """Read the four series once. `candles` may be passed by a caller that
    already holds them (setups.run does); otherwise they are read here."""
    regimes, breaks, atr_regimes, squeezes = [], [], [], []
    for r in store.get_facts(con, symbol, tf, "regime", REGIME_VERSION):
        p = json.loads(r["payload"])
        regimes.append((r["confirmed_at"], r["market_time"], p.get("regime")))
    for r in store.get_facts(con, symbol, tf, "structure", STRUCTURE_VERSION):
        p = json.loads(r["payload"])
        if p.get("event") in ("BOS", "CHOCH"):
            breaks.append((r["confirmed_at"], r["market_time"],
                           {"event": p["event"], "direction": p.get("direction"),
                            "level": p.get("level")}))
    for r in store.get_facts(con, symbol, tf, "volatility", VOLATILITY_VERSION):
        p = json.loads(r["payload"])
        if p.get("event") == "ATR_REGIME":
            atr_regimes.append((r["confirmed_at"], p.get("regime")))
        elif p.get("event") == "SQUEEZE":
            squeezes.append((r["confirmed_at"], p.get("squeeze")))
    for s in (regimes, breaks, atr_regimes, squeezes):
        s.sort(key=lambda x: x[0])
    if candles is None:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
    return Reading(tf, tf_seconds, regimes, breaks, atr_regimes, squeezes, candles)


# ------------------------------------------------------------- analysis time

def _tf_seconds():
    from .importer import TF_SECONDS
    return TF_SECONDS


def annotate(con, candidates) -> int:
    """Stamp the reading as-of each setup's confirmed_at onto its payload.

    driftfade's convention: in place, as-of confirmation (rule 3), the setup's
    own symbol/timeframe, and a candidate the reading cannot describe is left
    untouched so it lands in outcome_split's MISSING bucket rather than in a
    guessed one.
    """
    from . import bias
    tfs = _tf_seconds()
    readings: dict = {}
    n = 0

    def reading(symbol, tf):
        key = (symbol, tf)
        if key not in readings:
            readings[key] = load(con, symbol, tf, tfs[tf])
        return readings[key]

    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or tf not in tfs:
            continue
        r = reading(symbol, tf).at(c["confirmed_at"])
        if r["regime"] is None:
            continue
        p["phase"] = r["phase"]
        p["phase_side"] = phase_side(r["phase"])
        p["label_age_bars"] = r["label_age_bars"]
        p["break_bars_since"] = (r["last_break"] or {}).get("bars_since")
        p["displacement_atr"] = (r["last_break"] or {}).get("displacement_atr")
        p["vol_atr_regime"] = r["vol"]["atr_regime"]
        p["squeeze"] = r["vol"]["squeeze"]
        # The rung above, read the same way, and the direction it permits
        # (bias.permitted — the ladder composite the setup already recorded,
        # plus the rung-above phase, which is the term the ladder lacked).
        rung = bias.LADDER.get(tf)
        htf = reading(symbol, rung).at(c["confirmed_at"]) if rung in tfs else None
        p["htf_phase"] = htf["phase"] if htf and htf["regime"] is not None else None
        comp = (p.get("bias") or {}).get("composite")
        if comp is not None or p["htf_phase"] is not None:
            p["permitted"] = bias.permitted(comp, p["htf_phase"])
            p["agrees"] = bias.agrees(p["direction"], p["permitted"]) if p.get("direction") else None
        n += 1
    return n


def factor_extractors(payload) -> dict:
    """0/1 flags for outcome_split. Absent when unannotated (MISSING stays honest).

    fades_impulse   the trade is AGAINST an IMPULSE phase — the 2026-09-03 trade
    fades_trend     AGAINST a TREND phase (extended or not)
    with_turn       WITH a fresh TURN — the "enter when the trend is born" idea
    with_extended   WITH an EXTENDED trend — the late dip
    """
    if "phase" not in payload:
        return {}
    ph, side, d = payload["phase"], payload.get("phase_side"), payload.get("direction")
    want = {"LONG": "UP", "SHORT": "DOWN"}.get(d)
    against = side is not None and want is not None and side != want
    with_ = side is not None and want is not None and side == want
    out = {"fades_impulse": 1.0 if against and ph.startswith("IMPULSE") else 0.0,
           "fades_trend": 1.0 if against and ph.startswith("TREND") else 0.0,
           "with_turn": 1.0 if with_ and ph.startswith("TURN") else 0.0,
           "with_extended": 1.0 if with_ and ph.endswith("EXTENDED") else 0.0}
    # disagrees = the trade sits OUTSIDE the permitted direction (Phase 2's
    # reading). Absent when the reading itself is absent, so MISSING is honest.
    if payload.get("agrees") is not None:
        out["disagrees"] = 0.0 if payload["agrees"] else 1.0
        out["permitted_none"] = 1.0 if payload.get("permitted") == "NONE" else 0.0
    return out


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    """Load, annotate, split. Every cell is a fact; no cell is a verdict."""
    from . import factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    n_annotated = annotate(con, candidates)
    closed = [c for c in candidates if c.get("r") is not None and "phase" in c["payload"]]
    cells: dict = {}
    for c in closed:
        p = c["payload"]
        k = f"{p['phase']} x {p.get('strategy')} {p.get('direction')}"
        cell = cells.setdefault(k, {"n": 0, "sum_r": 0.0, "wins": 0})
        cell["n"] += 1
        cell["sum_r"] += float(c["r"])
        cell["wins"] += float(c["r"]) > 0
    for cell in cells.values():
        cell["mean_r"] = round(cell["sum_r"] / cell["n"], 3)
        cell["win_rate"] = round(cell["wins"] / cell["n"], 3)
        cell["sum_r"] = round(cell["sum_r"], 2)
    splits = {name: factorstats.outcome_split(candidates, name, factors=factor_extractors)
              for name in ("fades_impulse", "fades_trend", "with_turn", "with_extended",
                           "disagrees", "permitted_none")}
    # The permitted-direction cells: what a direction-first playbook would
    # have kept (agrees) and refused (disagrees), by playbook.
    perm: dict = {}
    for c in closed:
        p = c["payload"]
        if p.get("agrees") is None:
            continue
        k = f"{p.get('strategy')} {'agrees' if p['agrees'] else 'DISAGREES'} (permitted {p.get('permitted')})"
        cell = perm.setdefault(k, {"n": 0, "sum_r": 0.0, "wins": 0})
        cell["n"] += 1
        cell["sum_r"] += float(c["r"])
        cell["wins"] += float(c["r"]) > 0
    for cell in perm.values():
        cell["mean_r"] = round(cell["sum_r"] / cell["n"], 3)
        cell["win_rate"] = round(cell["wins"] / cell["n"], 3)
        cell["sum_r"] = round(cell["sum_r"], 2)
    return {"version": REGIMEREAD_VERSION, "derived_at_analysis_time": True,
            "constants": {"FRESH_BARS": FRESH_BARS, "IMPULSE_ATR": str(IMPULSE_ATR),
                          "EXTENDED_ATR": str(EXTENDED_ATR)},
            "candidates": len(candidates), "annotated": n_annotated,
            "closed": len(closed), "cells": cells, "permitted_cells": perm,
            "splits": splits, "warnings": warnings}


def main(argv=None):
    import argparse
    import sqlite3
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--setup-version", default=None)
    ap.add_argument("--exec-version", default=None)
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rep = grade(con, setup_version=args.setup_version, exec_version=args.exec_version)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
        return 0
    print(f"regime reading {rep['version']} — {rep['annotated']}/{rep['candidates']} "
          f"annotated, {rep['closed']} closed; constants {rep['constants']}")
    print(f"\n{'phase x playbook direction':44s} {'n':>5} {'mean R':>8} {'sum R':>8} {'win':>5}")
    for k, c in sorted(rep["cells"].items(), key=lambda kv: -kv[1]["n"]):
        if c["n"] >= 10:
            print(f"  {k:42s} {c['n']:5d} {c['mean_r']:+8.3f} {c['sum_r']:+8.1f} {c['win_rate']:5.0%}")
    print(f"\n{'permitted direction x playbook':44s} {'n':>5} {'mean R':>8} {'sum R':>8} {'win':>5}")
    for k, c in sorted(rep["permitted_cells"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {k:42s} {c['n']:5d} {c['mean_r']:+8.3f} {c['sum_r']:+8.1f} {c['win_rate']:5.0%}")
    print("\nflags (outcome_split, house floors):")
    for name, s in rep["splits"].items():
        g = s["groups"]
        a, b = g["at_or_above"], g["below"]
        fmt = lambda x: (f"n={x['n']:4d} mean={x['mean_r']:+.3f}R win={x['win_rate']:.0%}"
                         if x.get("sample_ok") else f"n={x['n']:4d} SAMPLE TOO SMALL")
        print(f"  {name:14s}  flagged: {fmt(a)}   |  rest: {fmt(b)}"
              + (f"   delta={s['delta_mean_r']:+.3f}R" if s.get("delta_mean_r") is not None else ""))
    print("\nNOT A GATE. Recorded, not filtered on, until graded (rule 7); a phase reaches "
          "a setup fact only through a versioned setups change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
