"""Grade a PLAYBOOK against the recorded book, on the house bar.

WHAT THIS IS FOR. `pipeline.MEASURED_NOT_ENABLED` runs engines that record and
trade nothing, so their sample grows against the day somebody asks whether they
work. Until 2026-08-11 nobody could ask: `execsim` only simulates whitelisted
versions, so a record-only engine produces no closed trade, and `edgestats`
grades closed trades. The setups piled up in a bucket with no bottom — 108
under breakout, 4,767 under trend, and zero outcomes under either.

`abtest.by_strategy` was the missing rung and it was already built. This is the
surface for it: read-only, writes no fact, moves no `algo_version`, and enables
nothing. It answers one question — "would this playbook have made money" — and
the answer it is allowed to give is one of three: cleared the bar, measurably
negative, or cannot tell yet.

WHY THIS IS NOT THE PROMOTION BUTTON, and must not become one:

  1. A grade here is HISTORICAL. It replays setups the engine recorded against
     candles that already happened. That is evidence about a rule, not about a
     book — `livegate` grades the forward record and is deliberately separate.
  2. GRADING SEVERAL PLAYBOOKS AND PROMOTING THE FIRST ONE THAT CLEARS ZERO IS
     NOT EVIDENCE OF EDGE, it is evidence of having looked five times. That is
     what `_holm` below is for, and why the corrected verdict is the one
     printed while the raw one is kept beside it.
  3. RE-RUNNING THIS UNTIL A NUMBER TURNS is the same error spread over time.
     The sample grows every cycle, so the interval will wander across zero on
     its own eventually. Predeclare the bar and the date before looking, or the
     result means nothing whatever it says.

Read only through a trustworthy calibration. If the harness cannot reproduce
the book it already has, it cannot be trusted on a book it has never seen, and
this refuses to print a verdict at all in that case rather than printing one
with a warning nobody reads.

    python -m engine.strategygrade                 # the traded set
    python -m engine.strategygrade --include-research   # ...and the record-only ones
"""
from __future__ import annotations

import argparse
import json
import sys

from . import abtest, breakout, edgestats, scalein, store, trend, venues
from .setups import SETUP_VERSION
from .universe import all_tracked_symbols

TFS = ("15m", "1H", "4H", "1D", "1W")

# The record-only engines: emitted, never traded. Their versions are named here
# rather than derived from `pipeline.MEASURED_NOT_ENABLED` because that tuple
# holds MODULES and this needs the version each one writes under; deriving it
# would couple this surface to the shape of the run roster for no benefit.
RESEARCH_VERSIONS = (breakout.BREAKOUT_VERSION, trend.TREND_VERSION)


def _holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values, strongest evidence first.

    Holm rather than plain Bonferroni because it is uniformly more powerful at
    the same guarantee, and rather than Benjamini-Hochberg because BH controls
    the false DISCOVERY rate — the expected proportion of promoted duds among
    promotions — which is the right target when you are screening a thousand
    candidates and can afford some. Here a false promotion puts real money
    behind a rule that does not work, so the family-wise error rate is what
    matters: the chance of ANY false promotion in the batch.

    `factorstats` uses BH for exactly the opposite and correct reason — it
    screens hundreds of factor cohorts to decide what is worth a second look,
    and nothing it flags reaches an order.
    """
    if not pvalues:
        return {}
    ordered = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(ordered)
    out, running = {}, 0.0
    for i, (name, p) in enumerate(ordered):
        adj = min(1.0, (m - i) * p)
        running = max(running, adj)      # enforce monotonicity
        out[name] = round(running, 4)
    return out


def grade(con, *, include_research: bool = False, resamples: int = 10000) -> dict:
    """Every playbook with a sample, on one bar, corrected for the multiplicity."""
    symbols = [s for s in all_tracked_symbols(con)
               if not venues.is_reference_key(s)]
    versions = (SETUP_VERSION, scalein.SCALE_VERSION)
    if include_research:
        versions = versions + RESEARCH_VERSIONS

    res = abtest.by_strategy(con, symbols, TFS, versions=versions,
                             resamples=resamples)
    strategies = res["strategies"]

    # Two-sided, from the clustered draw — the same distribution the verdict
    # reads. `p_gt_zero` is the mass above zero, so the two-sided p is twice
    # the smaller tail, and a playbook is "tested" only if it had enough
    # clusters to produce a distribution at all.
    raw = {name: min(1.0, 2 * min(s["cluster_p_gt_zero"],
                                  1 - s["cluster_p_gt_zero"]))
           for name, s in strategies.items()
           if s.get("cluster_p_gt_zero") is not None}
    adjusted = _holm(raw)

    for name, s in strategies.items():
        s["p_two_sided"] = raw.get(name)
        s["p_adjusted"] = adjusted.get(name)
        if not s["sample_ok"]:
            s["verdict"] = "INSUFFICIENT"
        elif s["cluster_ci_lo"] is not None and s["cluster_ci_lo"] > 0:
            s["verdict"] = "POSITIVE_EDGE"
        elif s["cluster_ci_hi"] is not None and s["cluster_ci_hi"] < 0:
            s["verdict"] = "NEGATIVE_EDGE"
        else:
            s["verdict"] = "INDISTINGUISHABLE"
        # The corrected column is the one that decides. A raw interval clear of
        # zero that does not survive the correction is a candidate worth
        # another look, never a promotion.
        s["survives_correction"] = bool(
            s.get("p_adjusted") is not None and s["p_adjusted"] < 0.05
            and s["verdict"] in ("POSITIVE_EDGE", "NEGATIVE_EDGE"))

    res["strategies_tested"] = len(raw)
    res["bar"] = ("clustered 95% interval clear of zero, Holm-corrected across "
                  "every playbook graded in this run")
    return res


def _render(res: dict) -> str:
    L = []
    cal = res.get("calibration") or {}
    conflicts = res.get("entry_model_conflicts") or {}
    L.append(f"STRATEGY GRADE - {res.get('version')}")
    L.append("")
    if conflicts:
        L.append("NO VERDICT. A setup generation records more than one entry "
                 "model:")
        for version, detail in sorted(conflicts.items()):
            L.append(f"  {version}: {detail}")
        L.append("")
        L.append("One generation cannot be replayed as two different order "
                 "types. Split or repair that evidence before grading it.")
        return "\n".join(L)
    if not res.get("trustworthy"):
        L.append("NO VERDICT. The harness could not reproduce the book it "
                 "already has:")
        L.append(f"  {cal.get('detail') or cal.get('status') or 'no detail'}")
        L.append("")
        L.append("A replay that cannot rebuild a known result is not evidence "
                 "about an unknown one. Nothing below would mean anything, so "
                 "nothing below is printed.")
        return "\n".join(L)

    L.append(f"calibration OK - {cal.get('detail') or cal.get('status')}")
    degradations = res.get("replay_degradations") or []
    if degradations:
        L.append(f"WARNING: {len(degradations)} replay fill(s) used a degraded "
                 "entry estimate:")
        for item in degradations[:5]:
            L.append(f"  {item['symbol']} {item['tf']} - {item['note']}")
        if len(degradations) > 5:
            L.append(f"  ...and {len(degradations) - 5} more")
    L.append(f"bar: {res['bar']}")
    L.append(f"playbooks graded in this run: {res.get('strategies_tested')}")
    L.append("")
    head = (f"{'playbook':<22} {'n':>5} {'sym':>4} {'fill%':>6} {'mean R':>8} "
            f"{'clustered 95%':>22} {'p adj':>7}  verdict")
    L.append(head)
    L.append("-" * len(head))
    for name, s in res["strategies"].items():
        if s["sample_ok"]:
            iv = f"[{s['cluster_ci_lo']:+.3f}, {s['cluster_ci_hi']:+.3f}]"
            padj = "-" if s["p_adjusted"] is None else f"{s['p_adjusted']:.3f}"
        else:
            iv, padj = "not computed", "-"
        L.append(f"{name:<22} {s['n']:>5} {str(s['clusters'] or '-'):>4} "
                 f"{str(s['fill_pct'] if s['fill_pct'] is not None else '-'):>6} "
                 f"{s['expectancy_r']:>8.4f} {iv:>22} {padj:>7}  {s['verdict']}"
                 # ONLY where the correction is what killed it. Printed on an
                 # already-indistinguishable row it blames the multiplicity for
                 # a verdict the interval reached on its own, which reads as
                 # "there was something here and the statistics took it away".
                 + ("  (interval clears zero, but not after correcting for "
                    "grading %d playbooks)" % res["strategies_tested"]
                    if s["verdict"] in ("POSITIVE_EDGE", "NEGATIVE_EDGE")
                    and not s["survives_correction"] else ""))
    L.append("")

    # The IID pair is shown ONLY where it disagrees, and labelled as the wrong
    # one. Printing it everywhere invites reading whichever is more flattering.
    dis = [(n, s) for n, s in res["strategies"].items()
           if s["sample_ok"] and s["ci_lo"] is not None
           and ((s["ci_lo"] > 0) != (s["cluster_ci_lo"] > 0)
                or (s["ci_hi"] < 0) != (s["cluster_ci_hi"] < 0))]
    if dis:
        L.append("Where the naive interval would have said something else - it "
                 "treats correlated signals as independent draws and is too "
                 "tight; the clustered pair above is the honest one:")
        for n, s in dis:
            L.append(f"  {n:<20} naive [{s['ci_lo']:+.3f}, {s['ci_hi']:+.3f}]"
                     f"  vs clustered [{s['cluster_ci_lo']:+.3f}, "
                     f"{s['cluster_ci_hi']:+.3f}]")
        L.append("")
    L.append("A grade here is historical. It is not the forward record, and it "
             "promotes nothing: enabling a playbook is a source change in "
             "execsim.plan_versions() and a version cascade.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--include-research", action="store_true",
                    help="also grade the record-only engines (breakout, trend)")
    ap.add_argument("--resamples", type=int, default=10000)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    a = ap.parse_args(argv)
    # UTF-8 at the boundary. This repo has paid for Windows console encoding
    # twice — a cp1252 stdout turns any prose punctuation into mojibake, and
    # the text flowing through here is not all ours: `calibration.detail` comes
    # from abtest and carries an em dash today. Our own rendered lines are kept
    # ASCII as well, so the two defences are independent.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):        # already wrapped, or a pipe
            pass
    con = store.connect()
    try:
        res = grade(con, include_research=a.include_research,
                    resamples=a.resamples)
    finally:
        con.close()
    print(json.dumps(res, indent=2, default=str) if a.json else _render(res))
    # Non-zero when no verdict could be given, so a scheduled caller cannot
    # mistake "could not grade" for "graded, nothing found".
    return 0 if res.get("trustworthy") else 2


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(main())
