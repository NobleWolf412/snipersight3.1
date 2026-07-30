"""Factor statistics — read-only grading of confluence factors. "Does this factor
deserve to exist?"

Ported from the prior project's `diagnostics/factor_contribution.py`. That project
shipped 26 named confluence factors and believed it was stacking 26 confirmations.
It was not: pairwise correlation showed the 26 collapsed into roughly 5 independent
signals, each counted three to six times under different names. Every "strong
confluence" reading was one opinion shouted repeatedly. The method below is the
guard against repeating that, applied to this project's SQLite fact store rather
than to JSONL signal logs.

Five axes, all of them required before a factor is worth its name:

  1. FIRE RATE     — fraction of candidates where the factor is present at all.
                     A factor that is absent 95% of the time cannot be carrying
                     the decision, whatever the backtest says.
  2. DISPERSION    — mean +/- std of the value WHEN present, plus the spread across
                     ALL candidates as a fraction of the observed range. Near-zero
                     spread means the factor says the same thing every time, which is
                     the same as saying nothing: it cannot separate one candidate from
                     another. Both readings are needed because a 0/1 flag is constant
                     "when present" by construction — its power lives entirely in how
                     often it fires — while a continuous score can vary and still be
                     flat relative to its own range.
  3. CONTRIBUTION  — share of composite variance, cov(factor, composite)/var(composite).
                     The source measured `score x renormalised weight`; this store
                     carries no per-factor weights, so the scale-free equivalent is
                     used. The shares sum to exactly 1.0 when the composite is the
                     unweighted sum of the listed factors, which gives the axis a
                     second use: a sum far ABOVE 1.0 means the set is attributing the
                     same variance more than once — the 26-factor failure mode
                     expressed as a number.
  4. REDUNDANCY    — pairwise Pearson correlation between factors. |r| >= 0.70 is
                     overlapping signal. Reported as clusters plus an EFFECTIVE
                     INDEPENDENT FACTOR COUNT. This is the axis that matters most:
                     it is the only one that can catch five correlated inputs being
                     counted as five confirmations.
  5. OUTCOME EDGE  — Pearson correlation between factor value and realised net R on
                     closed trades, judged against the noise floor +/-1.96/sqrt(n).
                     Inside the floor the factor is indistinguishable from random and
                     is NOT credited. NEGATIVE r is a finding, not an error: it means
                     the factor scores HIGH on losers and is actively misleading.

This tool GRADES factors. It must never gate a trade, size a position, or filter a
setup. Evidence is recorded, not filtered on (house convention 3) — nothing here is
imported by `setups.py`, `risk.py`, `execsim.py` or `scalein.py`, and nothing here
writes a fact. It is READ-ONLY on the store, in service of a separate, human,
versioned decision about which factors to keep.

Causality (house convention 2): a candidate is read at its `confirmed_at`, and its
outcome is only attached from an exec fact confirmed at or after that moment. No
factor value is ever computed from something the system could not have known.

Loud fallback (house convention 4): below MIN_TRADES matched trades the outcome axis
reports "sample too small" and refuses to publish a correlation. A confident-looking
0.00 from nine trades is worse than an honest blank.

Usage (from app/):
  python -m engine.factorstats
  python -m engine.factorstats --setup-version setup-v0.6-draft --json
  python -m engine.factorstats --factors confluence-v07 \
      --setup-version setup-v0.7-draft --exec-version exec-v0.8-draft
  python -m engine.factorstats --factors rank-components   # rank variance decomposition
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path

from . import store
from .execsim import EXEC_VERSION
from .setups import SETUP_VERSION

FACTORSTATS_VERSION = "factorstats-v0.1-draft"

# |Pearson| at or above this between two factors = overlapping signal. 0.70 is the
# source project's threshold and is deliberately generous: at r=0.70 the two factors
# already share half their variance (r^2 = 0.49), so calling them two confirmations
# overstates the evidence by roughly a factor of two.
REDUNDANT_R = 0.70
# Below this fire rate the factor is absent from 9 of 10 candidates and cannot be
# what is driving the book, whatever its outcome correlation looks like on the few
# candidates where it does appear.
DEAD_FIRE_RATE = 0.10
# Dispersion has to be scale-free here (this store's factors run from 0/1 flags to
# R:R in the tens), so flatness is std as a fraction of the factor's own observed
# range rather than an absolute std. A uniform spread scores 0.29 and a normal one
# 0.16-0.25, so 0.10 is comfortably below "actually varies". For a 0/1 flag this
# reduces to sqrt(p(1-p)), which drops under 0.10 only when the flag is on (or off)
# for more than 99% of candidates — the case where a flag has stopped separating
# anything. In the current book that is exactly `strategy_pullback`: 229 of 231.
FLAT_RATIO = 0.10
# Outcome-edge sample floor. At n=30 the noise floor is +/-0.36, which is already
# most of the correlation range; below that the honest answer is "unknown", and the
# source project's worst calls all came from trusting r on 8-15 trades.
MIN_TRADES = 30
# Below this many candidates even fire rate and dispersion are anecdote.
MIN_CANDIDATES = 20

_REGIME_ORDINAL = {
    "BEAR_TREND": -2.0,
    "WEAKENING_BEAR": -1.0,
    "TRANSITION": 0.0,
    "WEAKENING_BULL": 1.0,
    "BULL_TREND": 2.0,
}
_TF_ORDINAL = {"15m": 1.0, "1H": 2.0, "4H": 3.0, "1D": 4.0, "1W": 5.0}
# The HTF regime carried inside a v0.7 `confluence` block is read off a HIGHER
# timeframe than the setup, and that read is unfiltered by the playbook — so it can
# come back RANGE, a label the setup's own `regime` field never carries (the playbook
# has no RANGE play). RANGE and TRANSITION both mean "no directional conviction", so
# both map to 0.0. Kept as a separate table rather than widened into _REGIME_ORDINAL
# so that grading v0.6's `regime` field keeps behaving exactly as it did.
_HTF_REGIME_ORDINAL = dict(_REGIME_ORDINAL, RANGE=0.0)
# The two thresholds `setups.py` bakes into the rank integer: +15 when the
# confirmation bar's volume beats its trailing 20-bar average by more than
# VOLUME_HOT_RATIO, +15 when R:R clears GOOD_RR. Mirrored as floats rather than
# imported so that a later change to the LIVE formula cannot silently rewrite the
# history this module is grading — a decomposition of the book as it was ranked has
# to use the thresholds that were in force when those ranks were written. If the two
# ever diverge, RANK_POINTS below stops reproducing `rank` and says so out loud.
VOLUME_HOT_RATIO = 1.5
GOOD_RR = 2.5
# Points each term of the v0.7 rank formula is worth, from setups.py:
#   rank = min(100, base + 20*sweep + 15*volume + 15*rr_good + 10*htf_aligned)
# where base is 50 (PULLBACK) or 40 (REVERSAL).
RANK_POINTS = {"sweep": 20.0, "volume": 15.0, "rr_good": 15.0, "htf_aligned": 10.0}
RANK_BASE = {"PULLBACK": 50.0, "REVERSAL": 40.0}
RANK_CAP = 100.0


# --------------------------------------------------------------------------- math

def pearson(xs, ys) -> tuple[float | None, int]:
    """Pearson r over paired samples. Returns (r, n); r is None when undefined —
    fewer than three pairs, or either side constant. A constant vector has no
    correlation with anything, and returning 0.0 there would read as "measured and
    found unrelated" rather than "not measurable"."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None, n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return sxy / math.sqrt(sxx * syy), n


def noise_floor(n: int) -> float | None:
    """Two-sided 95% floor for a correlation at sample size n. |r| inside this is
    indistinguishable from random and must not be credited as edge."""
    return (1.96 / math.sqrt(n)) if n and n > 0 else None


def _covariance(xs, ys) -> tuple[float, int]:
    """Pairwise-complete covariance: pairs where either side is missing are dropped
    rather than imputed. Imputing a missing continuous score as 0.0 would invent an
    observation ("this zone had zero strength") that the store never recorded."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return 0.0, n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    return sum((p[0] - mx) * (p[1] - my) for p in pairs) / n, n


def _std(xs) -> float:
    vals = [v for v in xs if v is not None]
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _round(v, dp=6):
    """Fixed-precision rounding on the way out. Identical input already produces
    identical floats; rounding keeps the JSON stable to read and immune to the last
    binary digit wobbling between platforms."""
    return None if v is None else round(v, dp)


# ---------------------------------------------------------------- feature extractor

def default_factors(payload: dict) -> dict[str, float]:
    """The default extractor: today's ranking inputs, and nothing invented.

    Every value below is read from a field that `setup-v0.6-draft` actually emits
    (see `setups.py`). There is no `confluence` block in this store yet; when a later
    setup version adds one, pass a different extractor to `analyze`/`report` — the
    tool takes `factors(setup_payload) -> dict[str, float]` and nothing else, so no
    part of this module needs rewriting to grade it.

    Omitting a key is meaningful and is NOT the same as returning 0.0. An omitted key
    means the store never recorded that quantity for this candidate; it is dropped
    pairwise from every correlation rather than imputed, because imputing zero
    invents an observation ("this zone had zero strength") that was never made. A
    returned 0.0 is a real observation of the factor not firing — that is what the
    fire-rate axis counts, matching the source's `score > 0` presence convention.
    """
    out: dict[str, float] = {}

    rr = _as_float(payload.get("rr"))
    if rr is not None:
        out["rr"] = rr
        # The rank formula awards +15 for rr >= 2.5 (setups.py GOOD_RR). Extracting
        # the threshold separately from the raw value is deliberate: if the binary is
        # redundant with the continuous one, the rank formula is paying twice for the
        # same information, and that is precisely the finding this tool exists for.
        out["rr_good"] = 1.0 if rr >= 2.5 else 0.0

    rank = _as_float(payload.get("rank"))
    if rank is not None:
        out["rank"] = rank

    zs = _as_float(payload.get("zone_strength"))
    if zs is not None:
        out["zone_strength"] = zs

    reg = payload.get("regime")
    if reg in _REGIME_ORDINAL:
        # Signed trend ordinal: which way, and how hard. Kept alongside the unsigned
        # conviction because they answer different questions and their correlation is
        # itself a result worth seeing.
        out["regime_ordinal"] = _REGIME_ORDINAL[reg]
        out["regime_conviction"] = abs(_REGIME_ORDINAL[reg])

    tf = payload.get("tf")
    if tf in _TF_ORDINAL:
        out["tf_ordinal"] = _TF_ORDINAL[tf]

    d = payload.get("direction")
    if d in ("LONG", "SHORT"):
        out["direction_long"] = 1.0 if d == "LONG" else 0.0

    strat = payload.get("strategy")
    if strat:
        out["strategy_pullback"] = 1.0 if strat == "PULLBACK" else 0.0

    # The two boolean rank inputs are not stored as fields — `setups.py` folds them
    # into the rank integer and records them in the WHY sentence. Reading the WHY is
    # not string-parsing for its own sake: the WHY is the audited evidence record
    # (§8), and these two exact phrases are emitted by one line of setups.py each.
    why = payload.get("why") or ""
    out["why_sweep"] = 1.0 if "liquidity sweep nearby" in why else 0.0
    out["why_volume"] = 1.0 if "high volume at touch" in why else 0.0
    return out


def confluence_v07_factors(payload: dict) -> dict[str, float]:
    """Extractor for `setup-v0.7-draft`, which is the first version to emit a
    `confluence` block (`setups.py::confluence_block`).

    Same contract as `default_factors`: read what the store actually wrote, invent
    nothing, and OMIT a key rather than impute 0.0 when the field is absent. The
    omission rule does real work here — `htf_regime` is None on roughly a third of
    the book (the higher timeframe had no regime fact at that moment), and scoring
    those as "not aligned" would silently merge "we looked and the HTF disagreed"
    with "we never looked", which are different claims with different consequences.

    Three fields are deliberately extracted TWICE, once raw and once as the binary
    the rank formula actually consumes:

      * `volume_expansion` / `volume_hot`  — rank pays +15 for ratio > 1.5
      * `rr` / `rr_good`                   — rank pays +15 for R:R >= 2.5
      * `htf_align_strength` / `htf_regime_aligned` — rank pays +10 for the flag

    If a pair turns out redundant (|r| >= 0.70) the threshold is throwing away the
    only information the raw number carried; if it does NOT, the formula is reading a
    continuous quantity through a one-bit window and the axis will show which side of
    that window holds the edge. Either answer is a finding.

    `confluence.score` is not extracted: `setups.py` emits it as a hard-coded 0
    placeholder for a future version, so it is constant by construction and would
    only occupy a row saying ZERO_DISPERSION about a field that holds no data yet.
    """
    out: dict[str, float] = {}
    conf = payload.get("confluence")
    if not isinstance(conf, dict):
        conf = {}

    # ---- top-level setup fields (present on every v0.7 payload) ----------------
    rr = _as_float(payload.get("rr"))
    if rr is not None:
        out["rr"] = rr
        out["rr_good"] = 1.0 if rr >= GOOD_RR else 0.0

    rank = _as_float(payload.get("rank"))
    if rank is not None:
        out["rank"] = rank

    # Bars the setup waited for a confirming close. v0.7's entry model waits for
    # proof the level held; how LONG it waited is the cost of that proof, and
    # whether patience is paid for is exactly the sort of thing rank never asks.
    cbw = _as_float(payload.get("confirm_bars_waited"))
    if cbw is not None:
        out["confirm_bars_waited"] = cbw

    tf = payload.get("tf")
    if tf in _TF_ORDINAL:
        out["tf_ordinal"] = _TF_ORDINAL[tf]

    direction = payload.get("direction")
    if direction in ("LONG", "SHORT"):
        out["direction_long"] = 1.0 if direction == "LONG" else 0.0

    strat = payload.get("strategy")
    if strat:
        out["strategy_pullback"] = 1.0 if strat == "PULLBACK" else 0.0

    # ---- the confluence block --------------------------------------------------
    hr = conf.get("htf_regime")
    if hr in _HTF_REGIME_ORDINAL:
        ordinal = _HTF_REGIME_ORDINAL[hr]
        # Signed: which way the higher timeframe is leaning, and how hard.
        out["htf_regime_ordinal"] = ordinal
        # Unsigned: how TRENDING the higher timeframe is, ignoring the side. A
        # strong trend against the trade and a strong trend with it are the same
        # number here and opposite numbers in htf_align_strength; their outcome
        # correlations therefore answer two different questions.
        out["htf_regime_conviction"] = abs(ordinal)
        if direction in ("LONG", "SHORT"):
            # Signed TOWARD the trade: +2 = strong HTF trend agreeing, -2 = strong
            # HTF trend opposing. The graded version of the +10 flag, which cannot
            # tell "mildly against" from "hard against".
            out["htf_align_strength"] = ordinal * (1.0 if direction == "LONG" else -1.0)

    aligned = conf.get("htf_regime_aligned")
    if aligned is not None:
        out["htf_regime_aligned"] = 1.0 if aligned else 0.0

    for key in ("zone_strength", "zone_quality", "zone_cluster", "bars_since_break"):
        v = _as_float(conf.get(key))
        if v is not None:
            out[key] = v

    ve = _as_float(conf.get("volume_expansion"))
    if ve is not None:
        out["volume_expansion"] = ve
        out["volume_hot"] = 1.0 if ve > VOLUME_HOT_RATIO else 0.0

    sweep = conf.get("sweep_nearby")
    if sweep is not None:
        out["sweep_nearby"] = 1.0 if sweep else 0.0

    # Distance to the UNCAPPED structural target, in R. `rr` is this value after
    # MAX_TARGET_R clamps it, so the two are the same number until the cap bites and
    # diverge afterwards — the pair measures how often the cap is doing the deciding.
    tdr = _as_float(conf.get("target_distance_r"))
    if tdr is not None:
        out["target_distance_r"] = tdr
    return out


def rank_components(payload: dict) -> dict[str, float]:
    """The rank formula decomposed into its own terms, IN POINTS.

    Not a rival extractor — a decomposition. Graded against `default_composite`
    (which is `rank`), the contribution axis becomes exactly the variance
    decomposition the source project ran: `cov(term, rank) / var(rank)`, i.e. what
    fraction of the spread in rank each term is responsible for. Because rank is the
    unweighted SUM of these terms, the shares sum to 1.00 — and that sum is the
    decomposition's own self-check. If it drifts off 1.00 the terms below have stopped
    reproducing the formula in `setups.py` and the decomposition is not to be trusted.

    Points, not flags: `cov(20*sweep, rank)` is 20x `cov(sweep, rank)`, so emitting
    bare 0/1 flags would give every term a share proportional to its correlation but
    blind to its weight, and the whole question here is whether the WEIGHTS are
    earned. `rank_reproduction_error` is emitted alongside and must be 0.0 on every
    candidate; it is a factor row rather than an assertion so that a mismatch shows up
    as a visible non-zero line in the table instead of an exception nobody ran.
    """
    conf = payload.get("confluence")
    if not isinstance(conf, dict):
        conf = {}
    out: dict[str, float] = {}

    strat = payload.get("strategy")
    if strat not in RANK_BASE:
        return out                     # not a v0.7-shaped payload: decompose nothing
    base = RANK_BASE[strat]
    out["pts_base"] = base

    swept = bool(conf.get("sweep_nearby"))
    out["pts_sweep"] = RANK_POINTS["sweep"] if swept else 0.0

    ve = _as_float(conf.get("volume_expansion"))
    out["pts_volume"] = (RANK_POINTS["volume"]
                         if (ve is not None and ve > VOLUME_HOT_RATIO) else 0.0)

    rr = _as_float(payload.get("rr"))
    out["pts_rr_good"] = (RANK_POINTS["rr_good"]
                          if (rr is not None and rr >= GOOD_RR) else 0.0)

    # `setups.py` writes `if conf.get("htf_regime_aligned"):` — an UNKNOWN htf regime
    # is therefore scored identically to a DISAGREEING one. That collapse is part of
    # the formula and so it is part of the decomposition; the honest three-way version
    # lives in `confluence_v07_factors`, which omits the key when the regime is None.
    out["pts_htf_aligned"] = (RANK_POINTS["htf_aligned"]
                              if conf.get("htf_regime_aligned") else 0.0)

    rank = _as_float(payload.get("rank"))
    if rank is not None:
        rebuilt = min(RANK_CAP, sum(out.values()))
        out["rank_reproduction_error"] = rebuilt - rank
    return out


def default_composite(payload: dict) -> float | None:
    """The composite the contribution axis measures against: the system's own
    ranking score. Grading factors against anything else would grade a composite the
    system does not actually use."""
    return _as_float(payload.get("rank"))


def _as_float(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# Named extractors, for the CLI and for callers that want one by name rather than by
# import. The interface never changes: factors(setup_payload) -> dict[str, float].
EXTRACTORS = {
    "default": default_factors,
    "confluence-v07": confluence_v07_factors,
    "rank-components": rank_components,
}


# ------------------------------------------------------------------------- loading

def load_candidates(con, *, setup_version: str = SETUP_VERSION,
                    exec_version: str = EXEC_VERSION,
                    state: str = "VALIDATED",
                    inherit_forming_fields: bool = True) -> tuple[list[dict], list[str]]:
    """Read every candidate of `setup_version` in `state`, joined to its outcome.

    READ-ONLY: this issues SELECTs only. Returns (candidates, warnings).

    Two store realities are handled explicitly rather than silently:

    * The same `setup_id` can appear more than once at the same `confirmed_at`, from
      re-runs under different upstream versions (in the current book 72 of 231
      validated ids do, differing only in the regime label after a regime version
      bump). Taking them all would weight those setups twice. The rule is earliest
      `confirmed_at`, then highest fact id — earliest keeps causality honest, highest
      id takes the reading produced by the most recent upstream run.
    * `zone_strength` is only written on the FORMING payload, never on VALIDATED.
      With `inherit_forming_fields` it is back-filled from that setup's own FORMING
      fact, which is confirmed strictly earlier, so no lookahead is introduced. The
      back-fill is partial by nature (not every validated setup had a FORMING pass),
      and the resulting fire rate is the honest measure of that coverage.
    """
    warnings: list[str] = []
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, symbol, tf, market_time, confirmed_at, payload FROM facts "
        "WHERE kind='setup' AND algo_version=? ORDER BY confirmed_at, id",
        (setup_version,)).fetchall()

    chosen: dict[str, dict] = {}
    forming: dict[str, dict] = {}
    n_dupes = 0
    for r in rows:
        p = json.loads(r["payload"])
        sid = p.get("setup_id")
        if not sid:
            continue
        rec = {"fact_id": r["id"], "symbol": r["symbol"], "tf": r["tf"],
               "market_time": r["market_time"], "confirmed_at": r["confirmed_at"],
               "payload": p}
        if p.get("state") == "FORMING":
            prev = forming.get(sid)
            if prev is None or (r["confirmed_at"], r["id"]) < (prev["confirmed_at"],
                                                               prev["fact_id"]):
                forming[sid] = rec
            continue
        if p.get("state") != state:
            continue
        prev = chosen.get(sid)
        if prev is None:
            chosen[sid] = rec
        else:
            n_dupes += 1
            if (r["confirmed_at"], -r["id"]) < (prev["confirmed_at"], -prev["fact_id"]):
                chosen[sid] = rec
    if n_dupes:
        warnings.append(
            f"{n_dupes} duplicate {state} facts collapsed by setup_id "
            "(earliest confirmed_at, then latest fact id)")

    n_inherited = 0
    for sid, rec in chosen.items():
        # tf is a column, not a payload field; the extractor only ever sees the
        # payload, so surface it there rather than widening the extractor interface.
        rec["payload"].setdefault("tf", rec["tf"])
        rec["payload"].setdefault("symbol", rec["symbol"])
        if not inherit_forming_fields:
            continue
        f = forming.get(sid)
        if f is None or f["confirmed_at"] > rec["confirmed_at"]:
            continue                       # never read a fact before its confirmed_at
        for key in ("zone_strength", "distance_atr"):
            if key not in rec["payload"] and key in f["payload"]:
                rec["payload"][key] = f["payload"][key]
                n_inherited += 1
    if n_inherited:
        warnings.append(
            f"{n_inherited} field values back-filled from earlier FORMING facts "
            "(zone_strength/distance_atr are not written on VALIDATED payloads)")

    ex_rows = con.execute(
        "SELECT id, confirmed_at, payload FROM facts "
        "WHERE kind='exec' AND algo_version=? ORDER BY confirmed_at, id",
        (exec_version,)).fetchall()
    outcomes: dict[str, dict] = {}
    for r in ex_rows:
        p = json.loads(r["payload"])
        sid = p.get("setup_id")
        if not sid or sid in outcomes:
            continue                       # first (earliest) resolution wins
        outcomes[sid] = {"confirmed_at": r["confirmed_at"],
                         "outcome": p.get("outcome"),
                         "r_multiple": _as_float(p.get("r_multiple"))}

    if not chosen:
        # A version bump can leave the CURRENT algo version with no facts yet (it did
        # on 2026-07-29, when setup-v0.6 was superseded mid-session). Naming the
        # versions that do have candidates turns a silent empty report into an
        # actionable one.
        have = [r[0] for r in con.execute(
            "SELECT DISTINCT algo_version FROM facts WHERE kind='setup' "
            "ORDER BY algo_version").fetchall()]
        warnings.append(
            f"no '{state}' setup facts at algo_version {setup_version!r}. "
            f"versions present in this store: {', '.join(have) or 'none'}")

    n_missed = n_lookahead = 0
    candidates = []
    for sid in sorted(chosen):
        rec = chosen[sid]
        rec["setup_id"] = sid
        rec["outcome"] = None
        rec["r"] = None
        ex = outcomes.get(sid)
        if ex is not None:
            rec["outcome"] = ex["outcome"]
            if ex["confirmed_at"] < rec["confirmed_at"]:
                # Would mean an outcome known before the setup existed. Impossible by
                # construction; if it ever happens the join is wrong and the whole
                # outcome axis is fiction, so refuse the row loudly.
                n_lookahead += 1
            elif ex["outcome"] == "MISSED":
                n_missed += 1              # the limit never filled: no realised R
            else:
                rec["r"] = ex["r_multiple"]
        candidates.append(rec)
    if n_lookahead:
        warnings.append(
            f"{n_lookahead} exec facts confirmed BEFORE their setup — dropped from "
            "the outcome axis (a join this wrong invalidates the correlation)")
    if n_missed:
        warnings.append(
            f"{n_missed} candidates were MISSED (limit never filled) — excluded from "
            "the outcome axis, they have no realised R")
    return candidates, warnings


# ------------------------------------------------------------------------- analysis

def _clusters(names: list[str], pairs: list[tuple[str, str, float]]) -> list[list[str]]:
    """Connected components over the |r| >= REDUNDANT_R graph. Transitivity is the
    point: A~B and B~C means all three are reading one underlying thing even if A and
    C never correlate directly, and that chain is how 26 names became 5 signals."""
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _r in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups: dict[str, list[str]] = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)
    return sorted((sorted(v) for v in groups.values()), key=lambda g: (-len(g), g[0]))


def analyze(candidates: list[dict], *, factors=default_factors,
            composite=default_composite, warnings: list[str] | None = None) -> dict:
    """Grade every factor the extractor produces. Pure computation, no I/O, no RNG,
    no writes. Identical candidates in -> identical dict out."""
    warn = list(warnings or [])
    n = len(candidates)
    extracted = [factors(c["payload"]) for c in candidates]
    names = sorted({k for d in extracted for k in d})

    if n == 0:
        # Loud fallback: the empty case returns the FULL result shape, so a caller
        # that renders it cannot crash and cannot mistake it for a measurement. An
        # earlier version returned a short dict here and blew up the formatter the
        # first time a version bump left the requested version with no facts.
        return {"version": FACTORSTATS_VERSION, "n_candidates": 0, "n_trades": 0,
                "sample_ok": False, "outcome_sample_ok": False,
                "min_trades": MIN_TRADES, "noise_floor": None,
                "redundant_r": REDUNDANT_R, "factors": [], "stats": {},
                "contribution_share_sum": None, "redundant_pairs": [],
                "clusters": [], "redundant": [], "raw_factor_count": 0,
                "effective_independent_factors": 0,
                "warnings": warn + ["no candidates matched — nothing to grade"]}
    if n < MIN_CANDIDATES:
        warn.append(f"only {n} candidates (< {MIN_CANDIDATES}) — fire rate and "
                    "dispersion are anecdote at this size")

    # None = the store recorded nothing for this candidate (dropped pairwise).
    # 0.0 = a real observation that the factor did not fire.
    vectors = {name: [d.get(name) for d in extracted] for name in names}

    comp = [composite(c["payload"]) for c in candidates]
    comp_ok = [v for v in comp if v is not None]
    comp_var, _ = _covariance(comp, comp)
    if len(comp_ok) < n:
        warn.append(f"composite unavailable on {n - len(comp_ok)}/{n} candidates — "
                    "contribution shares computed on the covered subset only")
    if comp_var <= 0:
        warn.append("composite is constant across candidates — contribution share "
                    "not computed (nothing to attribute variance to)")

    # ---- outcome vectors: closed trades only, in candidate order
    idx_out = [i for i, c in enumerate(candidates) if c["r"] is not None]
    r_vec = [candidates[i]["r"] for i in idx_out]
    n_trades = len(idx_out)
    outcome_sample_ok = n_trades >= MIN_TRADES
    floor = noise_floor(n_trades) if outcome_sample_ok else None
    if not outcome_sample_ok:
        warn.append(
            f"outcome edge NOT reported: {n_trades} closed trades is below the "
            f"{MIN_TRADES}-trade floor. A correlation here would look like a "
            "measurement and would be noise.")

    stats: dict[str, dict] = {}
    for name in names:
        vec = vectors[name]
        observed = [v for v in vec if v is not None]
        present = [v for v in observed if v != 0.0]
        n_present = len(present)
        fire = n_present / n
        mean_p = (sum(present) / n_present) if n_present else 0.0
        std_p = (math.sqrt(sum((v - mean_p) ** 2 for v in present) / n_present)
                 if n_present else 0.0)

        # Discrimination across ALL candidates, normalised by the factor's own range
        # so flags and R:R are judged on one scale.
        spread = (max(observed) - min(observed)) if observed else 0.0
        std_all = _std(vec)
        ratio = (std_all / spread) if spread > 0 else 0.0

        share = None
        if comp_var > 0:
            cov, n_cov = _covariance(vec, comp)
            if n_cov >= 2:
                share = cov / comp_var

        r_out = None
        n_pairs = 0
        f_floor = None
        if outcome_sample_ok:
            r_out, n_pairs = pearson([vec[i] for i in idx_out], r_vec)
            # Each factor is judged against ITS OWN floor, from the pairs that
            # actually entered ITS correlation — not the book-wide trade count. A
            # factor the store only recorded on two thirds of the book (v0.7's
            # `htf_regime` is None on ~32%) is measured on a smaller sample and has a
            # correspondingly wider floor; borrowing the full book's floor would
            # credit it with a confidence its own coverage never earned.
            f_floor = noise_floor(n_pairs)
            if n_pairs < MIN_TRADES:
                # Full-book sample is fine, THIS factor's is not. Refuse the r
                # outright rather than publish one judged against a floor so wide it
                # is meaningless.
                r_out, f_floor = None, None
                warn.append(
                    f"{name}: recorded on only {n_pairs} of {n_trades} closed trades "
                    f"(< {MIN_TRADES}) — outcome edge withheld for this factor")

        stats[name] = {
            "fire_rate": _round(fire),
            "n_present": n_present,
            "n_observed": len(observed),
            "coverage": _round(len(observed) / n),
            "mean_when_present": _round(mean_p),
            "std_when_present": _round(std_p),
            "std_all": _round(std_all),
            "dispersion_ratio": _round(ratio),
            "contribution_share": _round(share),
            "r_outcome": _round(r_out),
            "n_outcome": n_pairs if outcome_sample_ok else 0,
            "noise_floor": _round(f_floor),
            "clears_noise_floor": (bool(r_out is not None and f_floor is not None
                                        and abs(r_out) >= f_floor)),
            "structural": None, "verdict": None, "cluster": None,
            "notes": [],
        }
        # A continuous score whose VALUE barely moves among the candidates it covers
        # is really a presence flag wearing a number. Not fatal — presence still
        # separates candidates — but the number itself is decoration.
        if (n_present > 2 and 0 < fire < 1 and mean_p
                and (std_p / abs(mean_p)) < FLAT_RATIO and len(set(present)) > 1):
            stats[name]["notes"].append(
                "value is near-constant when present — behaves as a presence flag")

    # ---- axis 1-2 structural verdicts, decided before redundancy so a factor that
    # never fires is not also reported as "redundant with" something.
    for name in names:
        s = stats[name]
        if s["n_observed"] == 0 or s["n_present"] == 0:
            s["structural"] = "ABSENT"
        elif s["fire_rate"] < DEAD_FIRE_RATE:
            s["structural"] = "RARE"
        elif s["std_all"] == 0.0:
            s["structural"] = "ZERO_DISPERSION"
        elif s["dispersion_ratio"] < FLAT_RATIO:
            s["structural"] = "FLAT"

    live = [nm for nm in names if stats[nm]["structural"] is None]

    # ---- axis 4: redundancy
    pairs: list[tuple[str, str, float]] = []
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            a, b = live[i], live[j]
            r, _ = pearson(vectors[a], vectors[b])
            if r is not None and abs(r) >= REDUNDANT_R:
                pairs.append((a, b, r))
    pairs.sort(key=lambda p: (-abs(p[2]), p[0], p[1]))

    groups = _clusters(live, pairs)
    redundant: set[str] = set()
    for gi, g in enumerate(groups):
        for nm in g:
            stats[nm]["cluster"] = gi
        if len(g) < 2:
            continue
        # Within a cluster only one member is evidence; the rest are echoes. Keep the
        # one with the strongest outcome correlation — that is the member actually
        # tracking money — falling back to the widest dispersion, then to the name,
        # so the choice is deterministic even with no outcome data at all.
        def _keep_key(nm):
            s = stats[nm]
            r = abs(s["r_outcome"]) if s["r_outcome"] is not None else -1.0
            return (-r, -(s["dispersion_ratio"] or 0.0), nm)
        keep = sorted(g, key=_keep_key)[0]
        for nm in g:
            if nm != keep:
                redundant.add(nm)

    # ---- final verdicts
    for name in names:
        s = stats[name]
        if s["structural"] is not None:
            s["verdict"] = {
                "ABSENT": "ABSENT (never fires — not a factor here)",
                "RARE": f"RARE (fires <{int(DEAD_FIRE_RATE * 100)}% of candidates)",
                "ZERO_DISPERSION": "ZERO_DISPERSION (identical on every candidate — "
                                   "no discriminating power)",
                "FLAT": "FLAT (spread below "
                        f"{int(FLAT_RATIO * 100)}% of its own range — barely separates "
                        "candidates)",
            }[s["structural"]]
        elif name in redundant:
            s["verdict"] = "REDUNDANT (overlaps a stronger factor in its cluster)"
        elif not outcome_sample_ok:
            s["verdict"] = (f"UNPROVEN (only {n_trades} closed trades; "
                            f"need {MIN_TRADES} before an outcome edge is credited)")
        elif s["r_outcome"] is None and s["n_outcome"] < MIN_TRADES:
            s["verdict"] = (f"UNPROVEN (recorded on only {s['n_outcome']} of "
                            f"{n_trades} closed trades; need {MIN_TRADES})")
        elif s["r_outcome"] is None:
            s["verdict"] = "UNPROVEN (no variance among closed trades — r undefined)"
        elif not s["clears_noise_floor"]:
            s["verdict"] = (f"NOISE (|r|={abs(s['r_outcome']):.2f} inside the "
                            f"±{s['noise_floor']:.2f} floor at n={s['n_outcome']} — "
                            "not credited)")
        elif s["r_outcome"] < 0:
            s["verdict"] = (f"ANTI (r={s['r_outcome']:+.2f} on n={s['n_outcome']} — "
                            "scores HIGH on LOSERS)")
        else:
            s["verdict"] = (f"EDGE (r={s['r_outcome']:+.2f}, clears ±"
                            f"{s['noise_floor']:.2f} at n={s['n_outcome']})")

    # A factor that IS the composite (rank graded against rank) trivially owns 100%
    # of its variance. Leaving it in the sum would hide the double-counting signal
    # the sum exists to expose, so it is flagged and excluded.
    for name in names:
        r_c, _ = pearson(vectors[name], comp)
        stats[name]["is_composite"] = bool(r_c is not None and abs(r_c) >= 0.999)
    shares = [stats[nm]["contribution_share"] for nm in names
              if stats[nm]["contribution_share"] is not None
              and not stats[nm]["is_composite"]]
    share_sum = _round(sum(shares)) if shares else None
    if share_sum is not None and share_sum > 1.5:
        warn.append(
            f"contribution shares sum to {share_sum:.2f} (>1.0) — the factor set is "
            "attributing the same composite variance more than once, i.e. it is "
            "double-counting")

    live_clusters = [g for g in groups if g]
    return {
        "version": FACTORSTATS_VERSION,
        "n_candidates": n,
        "n_trades": n_trades,
        "sample_ok": n >= MIN_CANDIDATES,
        "outcome_sample_ok": outcome_sample_ok,
        "min_trades": MIN_TRADES,
        "noise_floor": _round(floor),
        "redundant_r": REDUNDANT_R,
        "factors": names,
        "stats": stats,
        "contribution_share_sum": share_sum,
        "redundant_pairs": [{"a": a, "b": b, "r": _round(r)} for a, b, r in pairs],
        "clusters": live_clusters,
        "redundant": sorted(redundant),
        "raw_factor_count": len(names),
        "effective_independent_factors": len(live_clusters),
        "warnings": warn,
    }


def outcome_split(candidates: list[dict], name: str, *,
                  factors=confluence_v07_factors, threshold: float = 0.5) -> dict:
    """Split closed trades on one factor and report what each side actually earned.

    A Pearson r answers "does this move with R", which for a 0/1 flag is the same
    question as "which side wins" wearing a coat. The split is the readable form, and
    it is the only form that can show a rank term paying points to the LOSING side —
    the v0.6 finding that R:R >= 2.5 won 9% while R:R < 2.5 won 32%.

    Three groups, never two: at-or-above the threshold, below it, and MISSING (the
    extractor omitted the key, i.e. the store never recorded the quantity). Folding
    MISSING into "below" is how "we didn't look" gets laundered into "we looked and
    it wasn't there"; it is reported separately or not at all.

    Loud fallback (house convention 4): a group under MIN_TRADES keeps its counts —
    they are facts — but its `win_rate` and `mean_r` are None and `sample_ok` is
    False. `delta_mean_r` is only computed when BOTH compared groups clear the floor.
    """
    groups: dict[str, list[float]] = {"at_or_above": [], "below": [], "missing": []}
    for c in candidates:
        if c.get("r") is None:
            continue                    # no realised R: MISSED, or still open
        v = factors(c["payload"]).get(name)
        key = ("missing" if v is None
               else "at_or_above" if v >= threshold else "below")
        groups[key].append(c["r"])

    out: dict = {"factor": name, "threshold": threshold,
                 "n_trades": sum(len(v) for v in groups.values()),
                 "min_trades": MIN_TRADES, "groups": {}, "delta_mean_r": None,
                 "warnings": []}
    for key, rs in groups.items():
        n = len(rs)
        ok = n >= MIN_TRADES
        wins = sum(1 for r in rs if r > 0)
        out["groups"][key] = {
            "n": n, "n_wins": wins, "sample_ok": ok,
            "win_rate": _round(wins / n) if ok else None,
            "mean_r": _round(sum(rs) / n) if ok else None,
            "total_r": _round(sum(rs)) if rs else 0.0,
        }
        if n and not ok:
            out["warnings"].append(
                f"{name} [{key}]: {n} trades is below the {MIN_TRADES}-trade floor — "
                "win rate and mean R withheld (they would read as measurement)")
    hi, lo = out["groups"]["at_or_above"], out["groups"]["below"]
    if hi["mean_r"] is not None and lo["mean_r"] is not None:
        out["delta_mean_r"] = _round(hi["mean_r"] - lo["mean_r"])
    return out


def report(con=None, *, db_path: Path | None = None,
           setup_version: str = SETUP_VERSION, exec_version: str = EXEC_VERSION,
           state: str = "VALIDATED", factors=default_factors,
           composite=default_composite,
           inherit_forming_fields: bool = True) -> dict:
    """Full grading over the store, as a plain JSON-serialisable dict. READ-ONLY:
    this writes no facts and issues no INSERT. (Opening a connection for you goes
    through `store.connect`, which applies any pending schema migration — pass your
    own connection if even that is unwanted.)

    Pass an open connection, or a `db_path`, or neither (the default store)."""
    own = False
    if con is None:
        con = store.connect(db_path or store.DB_PATH)
        own = True
    try:
        candidates, warns = load_candidates(
            con, setup_version=setup_version, exec_version=exec_version,
            state=state, inherit_forming_fields=inherit_forming_fields)
        result = analyze(candidates, factors=factors, composite=composite,
                         warnings=warns)
    finally:
        if own:
            con.close()
    result["setup_version"] = setup_version
    result["exec_version"] = exec_version
    result["state"] = state
    return result


# ------------------------------------------------------------------------------ CLI

def format_report(res: dict) -> str:
    """Paste-friendly rendering: headline first, per-factor table second, clusters
    last — the order in which the question is actually asked."""
    out: list[str] = []
    a = out.append
    a("=== FACTOR STATISTICS (read-only; grades factors, never gates a trade) ===")
    a(f"setups {res.get('setup_version')} [{res.get('state')}] "
      f"x exec {res.get('exec_version')}")
    a(f"candidates: {res['n_candidates']}   closed trades: {res['n_trades']}   "
      f"factors: {res['raw_factor_count']}")
    if res["outcome_sample_ok"]:
        a(f"noise floor at n={res['n_trades']}: ±{res['noise_floor']:.2f} "
          "(|r| inside this is indistinguishable from random)")
    else:
        a(f"outcome edge SUPPRESSED — under the {res['min_trades']}-trade floor")
    a("")
    a(f"HEADLINE: {res['raw_factor_count']} factors declared → "
      f"{res['effective_independent_factors']} effective independent "
      f"({len(res['redundant'])} redundant, "
      f"{sum(1 for s in res['stats'].values() if s['structural'])} structurally dead)")
    if res["contribution_share_sum"] is not None:
        a(f"contribution shares sum to {res['contribution_share_sum']:.2f} "
          "(1.00 when the composite is exactly these factors; >>1.00 = double-counted)")
    a("")
    a("  mean/±std are measured WHEN PRESENT (a 0/1 flag is 1.00±0.00 by definition);")
    a("  disp = std across ALL candidates as a fraction of the factor's own range;")
    a("  cov% = share of candidates the store recorded this field on at all, and each")
    a("  factor's r is judged against ITS OWN floor from ITS OWN pair count.")
    a("")
    a(f"  {'factor':20}{'fire%':>7}{'cov%':>7}{'mean':>10}{'±std':>9}{'disp':>7}"
      f"{'share':>8}{'r_out':>8}  verdict")
    order = sorted(res["factors"],
                   key=lambda nm: (-(abs(res["stats"][nm]["r_outcome"])
                                     if res["stats"][nm]["r_outcome"] is not None
                                     else -1.0), nm))
    for nm in order:
        s = res["stats"][nm]
        share = f"{s['contribution_share']:+.2f}" if s["contribution_share"] is not None else "   -"
        rr = f"{s['r_outcome']:+.2f}" if s["r_outcome"] is not None else "   -"
        a(f"  {nm[:19]:20}{100 * s['fire_rate']:6.1f}%{100 * s['coverage']:6.1f}%"
          f"{s['mean_when_present']:10.2f}{s['std_when_present']:9.2f}"
          f"{s['dispersion_ratio']:7.2f}{share:>8}{rr:>8}  {s['verdict']}")
        for note in s["notes"]:
            a(f"  {'':20}└─ {note}")
    a("")
    a(f"--- redundancy (|Pearson| >= {res['redundant_r']}) ---")
    if not res["redundant_pairs"]:
        a("  no pair above threshold")
    for p in res["redundant_pairs"]:
        a(f"  r={p['r']:+.2f}  {p['a']}  <->  {p['b']}")
    a("")
    a("--- clusters (each cluster is ONE signal, however many names it has) ---")
    for i, g in enumerate(res["clusters"]):
        mark = "  (1 signal, %d names)" % len(g) if len(g) > 1 else ""
        a(f"  [{i}] {', '.join(g)}{mark}")
    if res["warnings"]:
        a("")
        a("--- warnings (loud fallback: these are NOT confident zeros) ---")
        for w in res["warnings"]:
            a(f"  ! {w}")
    return "\n".join(out)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        prog="python -m engine.factorstats",
        description="Grade confluence factors (read-only). Five axes: fire rate, "
                    "dispersion, contribution, redundancy, outcome edge.")
    ap.add_argument("--db", default=None, help="path to the fact store")
    ap.add_argument("--setup-version", default=SETUP_VERSION)
    ap.add_argument("--exec-version", default=EXEC_VERSION)
    ap.add_argument("--state", default="VALIDATED")
    ap.add_argument("--no-inherit", action="store_true",
                    help="do not back-fill zone_strength from earlier FORMING facts")
    ap.add_argument("--factors", default="default", choices=sorted(EXTRACTORS),
                    help="which extractor to grade with: 'default' (v0.6 ranking "
                         "inputs), 'confluence-v07' (the v0.7 confluence block), or "
                         "'rank-components' (rank's own terms, in points — the "
                         "variance decomposition of the ranking formula)")
    ap.add_argument("--json", action="store_true", help="emit the raw report dict")
    args = ap.parse_args(argv)

    res = report(db_path=Path(args.db) if args.db else None,
                 setup_version=args.setup_version, exec_version=args.exec_version,
                 state=args.state, factors=EXTRACTORS[args.factors],
                 inherit_forming_fields=not args.no_inherit)
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(format_report(res))
    return 0 if res["n_candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
