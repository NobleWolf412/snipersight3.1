"""What has to be true before this system may trade real money.

THE PROBLEM THIS SOLVES. `live_enabled` was a hardcoded `False` beside the
sentence "Forward paper evidence has not yet earned live execution." The UI
printed that faithfully on two surfaces — `Auto: Off`, `live execution
LOCKED` — and nothing anywhere in the system defined what "earned" meant.
No trade count, no expectancy bar, no drawdown ceiling, no progress. The
app's entire stated purpose sat behind a door with no handle, and neither an
experienced trader nor a newcomer could answer the only question that
matters: what do I have to do, and how close am I? (UX audit, 4 Aug 2026.)

A lock with no key is not caution. It is an unfinished thought.

THE BAR IS THE HOUSE BAR. Nothing here is invented for the occasion. This
project already refuses to ship a strategy whose confidence interval crosses
zero — `edgestats._verdict` calls that INDISTINGUISHABLE and it is the reason
`breakout` is measured-and-not-enabled. The same test, applied to the
operator's own forward record, is what earns real money.

SCOPE IS FORWARD, AND ONLY FORWARD. The recorded book holds 390 closed
trades across every baseline and every algo generation; the forward window
holds far fewer. Grading the lock on the big number would be the population
mixing this codebase has already had to fix once — the answer would be about
a strategy that no longer exists. Every criterion below is scoped to the
CURRENT baseline, which is exactly the record that would have been made with
today's rules.

WHAT THIS DELIBERATELY DOES NOT DO. It does not enable anything. Order
placement code now EXISTS — `execution.py` is a full outbox and
`phemex_private.py` a signed adapter — but only the TESTNET path may use it;
mainnet routing is build-locked (`automation.LIVE_ROUTER_BUILD_ENABLED` is
False and `broker_factory` raises rather than building a mainnet broker).
So passing every criterion here produces `ready` — evidence earned — and
never `enabled`. The two are reported separately because they fail for
different reasons and are fixed by different people: the operator moves the
evidence bar by trading the paper book, and only a deliberate build unlocks
the mainnet router (and the repo goes private first — see CLAUDE.md).
Collapsing them into one flag is how the button came to be permanently dead
in the first place. (This paragraph claimed "there is no order-placement
code in this system" until 2026-08-27, which stopped being true when the
outbox shipped — a stale claim of exactly the kind that sits beside the
lock it justifies.)
"""
from __future__ import annotations

from . import edgestats

LIVEGATE_VERSION = "livegate-v0.3-draft"
# v0.3: the gate grades the PAPER ACCOUNT, not the research replay. The caller
# passed `/api/portfolio`'s journal, built from `execsim.EXEC_VERSION` facts, so
# "Forward trades closed: N/100" counted simulated trades — 1030 replay execs
# against 3 paper orders ever, on the live store 2026-09-15. A v0.2 reader of a
# v0.3 payload is wrong about WHICH BOOK the number describes, which is the
# manual-v0.3 argument verbatim, so the payload now names its `population`.
# The count drops to the true one; that is the fix, not a regression.
# v0.2: build_note copy changed — it now names the build lock rather than
# claiming no order code exists (the outbox and signed testnet adapter shipped
# 2026-08-27). No criterion moved, but the note is API-visible on two operator
# surfaces, and a reader of a stored v0.1 payload was being told a different
# reason for the same lock. Copy that ships over the wire moves the tag — the
# opportunity-v0.5 precedent (trader-readable reasons were a version).

# ── the criteria ────────────────────────────────────────────────────────────
# Each is a number an operator can watch move. They are deliberately few: a
# gate with nine conditions is a gate nobody reads.

#: Closed forward trades required before the record is allowed to mean
#: anything. `edgestats.MIN_TRADES` (10) is the floor for computing a
#: bootstrap at all, which is a different and much weaker claim than "enough
#: evidence to risk money on". 100 is the house number for the latter.
MIN_FORWARD_TRADES = 100

#: Resamples for the forward CI. Matches the request-path default in
#: `/api/edge-stats` rather than the 20k offline number, and is reported, so
#: the figure on screen is never mistaken for the deeper one.
RESAMPLES = 5000

#: WHY LIVE IS LOCKED, in one place. Every surface that tells the operator why
#: real-money routing is unavailable reads this string.
#:
#: `ui_api.context_model` used to carry its own wording — "Required venue
#: safety drills are not complete" — which is a different claim from the true
#: one, and one that would go on being displayed after the drills passed. Both
#: fail closed, so the duplicate could only ever mislead about the reason, never
#: unlock anything; that is exactly the kind of second authority §6 rule 9 is
#: about, and a safety statement is the worst place to keep one.
BUILD_NOTE = ("Even with every criterion met, this system cannot send a "
              "real-money order: mainnet order routing is build-locked. "
              "Unlocking it is a deliberate build decision, not something "
              "the record earns.")


def _drawdown_limit(con) -> float:
    """The operator's own total-drawdown guardrail, not a second opinion.

    `risk.py` halts the book at this number; a gate that let live execution
    unlock past it would be promising money to a system its own risk
    authority is about to stop.
    """
    from . import settings
    try:
        return float(settings.all_settings(con)["max_drawdown_pct"])
    except Exception:
        return float(settings.defaults()["max_drawdown_pct"])


def evaluate(con, *, journal: list[dict], max_drawdown_pct: float,
             quality_status: str | None, baseline: dict | None = None,
             strategy_version: str | None = None,
             population: str = "PAPER_ACCOUNT") -> dict:
    """Grade the forward record against the four criteria. Read-only.

    `journal` is the PAPER ACCOUNT's closed trades. The caller passes it in
    rather than re-deriving it — §8, never re-derive equity — but WHICH BOOK it
    comes from is this module's business, because the whole claim of the
    docstring above is that "the operator moves the evidence bar by trading the
    paper book".

    It did not. The caller passed `/api/portfolio`'s journal, which is built
    from `execsim.EXEC_VERSION` facts — the research replay. The bar counted
    simulated trades. Measured on the live store 2026-09-15: 1030 replay exec
    facts at the current version against 3 paper orders ever placed, so the
    population this gate graded could climb toward 100 without the operator's
    book doing anything at all. It read 1/100 at the time only because a risk
    version bump had reset the join, which is luck, not a guard.

    That matters beyond display: `automation.promotion_summary` turns `ready`
    into `live_ready` -> `live_enabled` -> `dispatch_allowed`. It is inert
    solely because `LIVE_ROUTER_BUILD_ENABLED` is False. This is the number
    that decides when real money is at risk, so it grades the book that would
    be risking it.

    `population` is stamped on the payload for the same reason the criteria
    are: a stored verdict must say which book it is about.
    """
    rs = [float(t["r_multiple"]) for t in journal
          if t.get("r_multiple") is not None]
    n = len(rs)

    # --- 1. sample ---------------------------------------------------------
    # A STRATEGY BUMP RESTARTS THE CLOCK, and the operator must be told so in
    # the same breath as the zero. Watched live on 4 Aug 2026: a parallel
    # session shipped setup-v0.16 and this count fell from 7 to 0 within the
    # hour. That is correct — the forward record is evidence about the rules
    # that made it, and those rules no longer exist — but a counter that
    # silently resets reads as a bug or a betrayal.
    base_ver = (baseline or {}).get("strategy_version")
    stale = bool(base_ver and strategy_version and base_ver != strategy_version)
    sample = {
        "key": "sample",
        "label": "Forward trades closed",
        "have": n,
        "need": MIN_FORWARD_TRADES,
        "progress": min(1.0, n / MIN_FORWARD_TRADES) if MIN_FORWARD_TRADES else 1.0,
        "pass": n >= MIN_FORWARD_TRADES,
        "note": (
            f"The strategy changed to {strategy_version} — this baseline "
            f"records {base_ver}, so the count starts again from zero. That "
            f"is the point of it: a record made by rules that no longer exist "
            f"is not evidence about the rules that do."
            if stale else
            "Trades closed since the current baseline started. Only these "
            "count: the older book was made by rules that have since "
            "changed."),
        "baseline_restarted": stale,
    }

    # --- 2. edge ----------------------------------------------------------
    boot = edgestats._bootstrap_mean(rs, RESAMPLES) if n >= edgestats.MIN_TRADES else None
    if boot is None:
        edge_txt = (f"Not measurable yet — a confidence interval needs at "
                    f"least {edgestats.MIN_TRADES} closed trades and there "
                    f"are {n}.")
        edge_pass, ci_lo, ci_hi = False, None, None
    else:
        ci_lo, ci_hi = boot["ci_lo"], boot["ci_hi"]
        edge_pass = ci_lo > 0
        if edge_pass:
            edge_txt = (f"The honest range for the average trade runs "
                        f"{ci_lo:+.3f}R to {ci_hi:+.3f}R — all of it above "
                        f"break even.")
        elif ci_hi < 0:
            edge_txt = (f"The honest range runs {ci_lo:+.3f}R to {ci_hi:+.3f}R "
                        f"— all of it below break even. This is not bad luck.")
        else:
            edge_txt = (f"The honest range runs {ci_lo:+.3f}R to {ci_hi:+.3f}R "
                        f"— it still crosses break even, so this record has "
                        f"not shown it makes money.")
    edge = {
        "key": "edge",
        "label": "Edge clears zero",
        "have": None if boot is None else round(ci_lo, 3),
        "need": 0.0,
        # Progress on a confidence bound is not a fraction of anything
        # meaningful — it is pass or not — so it reports as a step rather
        # than pretending to a percentage.
        "progress": 1.0 if edge_pass else 0.0,
        "pass": edge_pass,
        "ci_lo": ci_lo, "ci_hi": ci_hi, "resamples": RESAMPLES,
        "note": edge_txt,
    }

    # --- 3. drawdown -------------------------------------------------------
    dd_limit = _drawdown_limit(con)
    dd = float(max_drawdown_pct or 0.0)
    drawdown = {
        "key": "drawdown",
        "label": "Drawdown inside its limit",
        "have": round(dd, 2),
        "need": dd_limit,
        "progress": 1.0 if dd <= dd_limit else 0.0,
        "pass": dd <= dd_limit,
        "note": (f"Worst peak-to-trough fall on the forward record is "
                 f"{dd:.2f}%, against your own {dd_limit:.0f}% guardrail. "
                 f"Past it, the risk authority halts the book anyway."),
    }

    # --- 4. data integrity -------------------------------------------------
    q = (quality_status or "UNKNOWN").upper()
    q_pass = q in ("PASS", "DEGRADED")
    quality = {
        "key": "quality",
        "label": "Data integrity holds",
        "have": q,
        "need": "not BLOCKED",
        "progress": 1.0 if q_pass else 0.0,
        "pass": q_pass,
        "note": ("The pipeline audit is not blocking. A book built on candles "
                 "the audit rejects is not evidence of anything."
                 if q_pass else
                 "The pipeline audit is BLOCKING. Fix the data before the "
                 "record made from it is allowed to argue for real money."),
    }

    criteria = [sample, edge, drawdown, quality]
    met = sum(1 for c in criteria if c["pass"])
    ready = met == len(criteria)

    return {
        "version": LIVEGATE_VERSION,
        # WHOSE BOOK this verdict is about. A stored payload that does not say
        # is a payload nobody can check, and the reason v0.3 exists is that the
        # answer used to be the wrong one silently.
        "population": population,
        "criteria": criteria,
        "met": met,
        "total": len(criteria),
        # Evidence earned. NOT permission to send an order — see the module
        # docstring for why these are two answers and not one.
        "ready": ready,
        "enabled": False,
        "blocked_by_build": True,
        "build_note": BUILD_NOTE,
        "headline": (
            "Evidence bar met — live execution still needs an order router"
            if ready else
            f"{met} of {len(criteria)} met — "
            + next(c["label"].lower() for c in criteria if not c["pass"])
            + " is what is missing"),
    }
