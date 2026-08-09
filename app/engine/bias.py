"""Top-down bias — what the timeframes ABOVE this one are doing. algo bias-v0.1-draft.

WHY THIS EXISTS, and it is a consistency problem before it is a strategy one.
Three engines currently answer "does the higher timeframe matter" three
different ways, and not one of those answers was chosen by measurement:

    scalein   HARD GATE   no add without an open 4H/1D parent in the direction
    setups    RECORDS IT  writes htf_regime/htf_state/htf_composite, gates on
                          nothing — the +10 rank term it fed was retired with
                          `rank` itself
    trend     BLIND       reads only its own timeframe, and does not even
                          record what the rungs above were doing, so the
                          question cannot be asked of its cohort afterwards

That is not a design, it is the order things got built in. `SPEC-confirmed-
entry.md` §1.4 already names it: "scalein.py already encodes the principle —
'the higher timeframe GATES the lower' — it simply was never applied to the
primary entry." This module is the one place that principle lives, so a
fourth playbook inherits it instead of re-inventing a fourth answer.

A LIBRARY, NOT AN ENGINE. It emits no facts and has no `run()`. Everything
here is derived from `regime` and `structure` facts that already exist, and a
`bias` fact series would restate them under a second name — two authorities
for one number, which is how `abtest` and `execsim` came to disagree about a
fill for a whole version. The reading is recomputable for any historical
moment, which is also what makes step 2 of the plan free: the grade can be
run over the existing book without re-simulating anything.

WHAT IT READS, and why regime rather than the ribbon. `ma.RIBBON` needs 210
bars before it says anything and the store holds ~194 weekly bars, so a
ribbon-based 1W rung would read UNKNOWN nearly everywhere — the exact blind
spot S53 closed for `htf_regime` by demoting TIER_BY_TF["1W"]. Measured on
the live store at regime-v0.12: 1W regime exists for 32 symbols, 1D for 37,
and every rung is populated. Regime is the reading that can actually answer.

THE WHOLE CHAIN, NOT ONE RUNG, and that is measured rather than assumed. Both
readings were built from the same regime facts under the same as-of rule and
scored on the outcome-edge axis (|r| against realised R vs the ±1.96/√n noise
floor). On the trend book — 2,824 trades, the only sample here large enough to
decide anything — the ladder clears its floor (r=+0.0417 vs ±0.0375) and the
one-rung reading does not (r=+0.0010 vs ±0.0386), separating its three buckets
by 0.0055 R, which is nothing. The ladder also fires more often (96.8% vs
91.3%): a missing rung no longer blanks the reading, because the rungs above
it are still there to consult. That is the 1W blind spot fixed by structure
instead of by backfilling weekly history.

They are NOT redundant, which is worth stating because the opposite was
expected: r=0.5575 on the live book, 0.5717 on trend, both under the 0.70
bar, agreeing on barely half the trades. Two different questions, and the
one-rung version is the one that does not answer.

THE FIVE STATES, and MIXED is the one that earns its place. A bearish daily
sitting over a bullish 4H is the case a trader actually asks about, and the
honest answer is that the rungs disagree — not whichever one a tie-break
happened to pick. Collapsing it would invent a consensus the market is
explicitly not showing, the same argument `ma.stack` makes for keeping MIXED
instead of rounding to the nearest of BULL/BEAR.

    UP / DOWN   every rung that is trending agrees on a side
    MIXED       trending rungs disagree
    FLAT        nothing above is trending (all RANGE / TRANSITION)
    UNKNOWN     nothing above is measurable

UNKNOWN IS NOT A WEAK FORM OF AGAINST, and this is enforced rather than
documented. `setups.py` scored a missing HTF reading identically to a
contrary one, and it cost 1.02 R/trade: unknown-HTF trades ran 38.9% win /
+0.404 R while genuinely opposed ones ran 17.2% / -0.616 R. It fell entirely
on the 1D book, the only profitable timeframe, which had no way to close the
gap. `validate_policy` therefore REFUSES a policy that maps UNKNOWN to
anything but ALLOW — a programming error, loud at write, the way an unknown
`pipeline.GATES` name is. A future playbook with evidence that UNKNOWN
should block changes the rule here once, with the reasoning, rather than
quietly in its own dict.

POLICY IS THE PLAYBOOK'S, THE READING IS SHARED. Each playbook declares a
`BIAS_POLICY` mapping the five alignments to ALLOW / REQUIRE_EVIDENCE /
BLOCK. That split is deliberate: the reading is a fact about the market and
must be identical everywhere, while what to DO about it is a strategy rule
that has to be graded per playbook. A trend-continuation engine and a
mean-reversion engine should not want the same answer, and on the current
book they demonstrably do not — trades whose higher timeframe AGREED are the
WORST bucket at -0.247 R, because both live playbooks fade moves.

RECORD FIRST, GATE SECOND. Nothing here blocks anything yet. Every playbook
records its block on the setup fact and the policies stay advisory until the
replay harness shows, per playbook, that the filtered book beats the
unfiltered one. That ordering is the whole lesson of the prior project's
5,985-line scorer: 26 factors that were five signals counted repeatedly,
every one of them shipped on plausibility. `docs/SPEC-confirmed-entry.md`
§1.4 holds the five-axis promotion criterion a factor must clear first.

MEASURED 2026-08-04, and it is the reason policy is per-playbook rather than
one house rule. Every trade in the recorded book and every trade in the trend
replay was re-read as-of through this module, then each candidate policy was
asked what it would have kept:

                        unfiltered   only-WITH    delta
    TREND_CONTINUATION    -0.1498     -0.0639    +0.086   n=2823 -> 822
    live book             +0.0196     -0.0892    -0.109   n= 498 -> 144
      REVERSAL            +0.0751     +0.0816    +0.007   n= 369 ->  90
      PULLBACK            -0.1391     -0.3737    -0.235   n= 129 ->  54

THE TWO KINDS OF STRATEGY WANT OPPOSITE POLICIES. Filtering to WITH is worth
+0.086 R/trade to the continuation playbook and -0.109 R/trade to the live
counter-move book, and the per-bucket split says why: trend's best bucket is
WITH (-0.0245) and its worst are AGAINST (-0.2191) and FLAT (-0.2172), while
the live book's BEST bucket is AGAINST (+0.2755, P(>0) 94.5%). A single
global top-down rule would have improved one playbook and damaged the other,
which is exactly what a shared reading with per-playbook policy exists to
prevent — and exactly what the prior project shipped.

NOTHING HERE CLEARS ZERO IN THE POSITIVE DIRECTION. The filter moves trend
from an interval ENTIRELY BELOW zero to one straddling it (CI [-0.182,
+0.058], P(>0) 15.3%) — from proven-losing to unproven, which is progress and
is not an edge. No policy makes any book provably profitable. Note also that
this pass tested 5 alignments x 5 policies x 4 books, so some cell somewhere
looking significant is expected by chance; the trend result is the one worth
weight, because it has the largest n and it was PREDICTED before it was run.

The one bucket that clears zero is negative and mechanically sensible:
PULLBACK trades taken WITH a trending ladder ran -0.7391 R over 35 trades,
P(>0) 0.3%. Buying a dip while the timeframes above are trending hard in your
direction means buying an extended market, and the book says so.

ENFORCEMENT: BUILT, TESTED, AND OFF EVERYWHERE. The gate is real — a BLOCK
skips the setup and writes a `setup_rejection` fact under `BLOCK_REASON`, so a
refusal is as auditable as an approval (§8) and the funnel has a sentence for
it. Proven end to end rather than asserted: armed with a test policy on one
symbol, trend emitted 48 setups and 41 refusals against 89 shipped, the run
counter matched the fact count, and no setup survived that the policy should
have refused. Shipped, every policy is ALLOW and it fires zero times.

Three different reasons for OFF, and the difference matters:

  setups    MEASURED, AND THE ANSWER IS NO. Every filter tried costs this
            book money (-0.109 R/trade to WITH-only). Its best bucket is
            AGAINST. Both playbooks fade moves; a ladder trending hard your
            way means the move is extended.
  trend     MEASURED, AND THE ANSWER IS NOT YET. Filtering to WITH is worth
            +0.086 R/trade — but this engine does not trade, so that gain is
            uncollected, and the gate would refuse 2,001 of 2,823 trades
            which ARE the only evidence that can grade a trend-following
            factor. Paying 71% of the sample to improve a number nobody banks
            is a bad trade. Arm it the day the engine is enabled.
  breakout  NOT MEASURED AT ALL. n=55, no sample to grade with. ALLOW is what
            "we have not looked" must resolve to, exactly as UNKNOWN is.

THE POLICY THAT LOOKS BEST IS THE ONE TO TRUST LEAST. Blocking only MIXED
improves every live slice (+0.040 R/trade overall, +0.050 on REVERSAL) and is
NOT armed, because it was invented after reading the table above. The MIXED
bucket's own interval is [-0.635, +0.185] and the improved book still does not
clear zero (P(>0) 75.0%). It is the best candidate for the next round and it
needs data it has not seen; promoting it now would be fitting the rule to the
sample, which is how the prior project got a 5,985-line scorer.

Usage (from app/):
    from . import bias
    src = bias.load(con, symbol, tf)
    block = src.check(direction, as_of, tf_seconds, MY_BIAS_POLICY)
"""
import json

from . import store
from .regime import REGIME_VERSION
from .structure import STRUCTURE_VERSION

BIAS_VERSION = "bias-v0.2-draft"
# v0.2: input cascade from agg-v0.2 via regime-v0.13/structure-v0.13 — the
# ladder is read off their facts, and those are a new generation. No rule
# change here.

#: The rung each timeframe defers to. Moved here from `setups.HTF_LADDER`,
#: which re-exports it so no consumer breaks; this module is now the one
#: authority for what "the higher timeframe" means.
LADDER = {"5m": "15m", "15m": "1H", "1H": "4H", "4H": "1D",
          "1D": "1W", "1W": None}

#: Regime states that count as a SIDE. WEAKENING_* is treated as its parent
#: trend, matching what `setups.py` has recorded since v0.7 — continuity
#: matters because the whole point of step 2 is grading this against the
#: existing htf_composite reading, and changing the mapping in the same
#: change would make the two incomparable.
#:
#: `btcalign.py` deliberately takes the OPPOSITE view for its own purpose
#: ("OPPOSED means the full opposing trend only — WEAKENING_* is a trend
#: losing force, and counting it would block exactly the turns the REVERSAL
#: playbook exists to catch"). Both are defensible; they are answering
#: different questions, and the disagreement is recorded here rather than
#: silently resolved. If the grade says the weakening states belong with
#: FLAT, that is a bias-v0.2 rule change with a measurement behind it.
_SIDE_BY_REGIME = {
    "BULL_TREND": "UP", "WEAKENING_BULL": "UP",
    "BEAR_TREND": "DOWN", "WEAKENING_BEAR": "DOWN",
    "RANGE": "FLAT", "TRANSITION": "FLAT",
}

#: The closed action vocabulary. Unknown names raise rather than warn, for the
#: reason `pipeline.GATES` does: these are minted a few lines from their
#: declaration, so drift here is a typo, not vocabulary growth.
ACTIONS = frozenset({"ALLOW", "REQUIRE_EVIDENCE", "BLOCK"})

#: Every alignment a policy must answer for. A policy missing one is rejected
#: — a playbook that has not thought about MIXED has not declared a policy,
#: it has declared three quarters of one.
ALIGNMENTS = ("WITH", "AGAINST", "MIXED", "FLAT", "UNKNOWN")

#: How recently a break must have confirmed to count as evidence. Bars, on the
#: TRADE's timeframe. Deliberately short: the permission slip is "the market
#: just changed its mind in my favour", and a break twenty bars ago is the
#: prevailing structure rather than a change in it.
#:
#: **AT 5 BARS THIS PREDICATE IS VERY NEARLY A NO-OP, and that is measured
#: rather than suspected.** Over the 2026-08-04 grading pass it fired on 0 of
#: 126 counter-ladder trades in the recorded book and 5 of 744 in the trend
#: replay. So REQUIRE_EVIDENCE currently resolves to BLOCK almost every time
#: and is indistinguishable from a flat BLOCK — the `evidence` and
#: `no_against` policies scored within 0.003 R/trade of each other on trend
#: and identically on the live book.
#:
#: That is a finding about the RULE, not about the idea. Structure breaks are
#: confirmed on the trade's own timeframe and a zone-touch entry rarely sits
#: within five bars of one. Before this window can gate anything it has to be
#: re-tuned and re-graded — a wider window, or the break read off the rung
#: above rather than the trade's own timeframe, are the two obvious candidates
#: and each is a bias-v0.2 rule change with its own measurement. Shipping the
#: gate on the current number would ship a BLOCK wearing a subtler name.
EVIDENCE_MAX_BARS = 5

#: Which structure events count. A BOS continues the existing swing sequence;
#: a CHOCH is the first break AGAINST it. Both are admitted because the
#: counter-trend case this gates is exactly where a CHOCH appears first, and
#: requiring the sequence to have already flipped would refuse the earliest
#: honest evidence there is.
EVIDENCE_EVENTS = ("BOS", "CHOCH")

#: The rejection reason a blocked setup is recorded under. One name, shared,
#: because the funnel has to be able to say WHICH gate refused a trade — and
#: `setups.REJECTION_REASONS` refuses any reason it does not know.
BLOCK_REASON = "BIAS_BLOCKED"

_DIR_SIDE = {"BULL": "UP", "BEAR": "DOWN"}
_WANT_SIDE = {"LONG": "UP", "SHORT": "DOWN"}


def blocked(block: dict) -> bool:
    """Did this check refuse the trade? The one place that question is asked.

    Trivial by design. It exists so no engine writes `== "BLOCK"` inline: the
    day REQUIRE_EVIDENCE grows a third outcome, or a policy learns to defer,
    every call site follows automatically instead of four of them agreeing
    until one does not.
    """
    return block["resolved"] == "BLOCK"


def rungs_above(tf: str) -> tuple:
    """Every timeframe above `tf`, nearest first. ("1H","4H","1D","1W") for 15m.

    The whole chain rather than one step, because MIXED cannot exist with a
    single rung and MIXED is the state a trader actually asks about. Walking
    the chain is also what makes this top-down rather than one-up: a 15m trade
    under a bearish daily should be able to know that, and under the one-step
    map it could only ever see the 1H.
    """
    out, cur, seen = [], LADDER.get(tf), {tf}
    while cur and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = LADDER.get(cur)
    return tuple(out)


def _as_of(series, ts):
    """The last reading CONFIRMED at or before `ts`, or None.

    The as-of discipline is the lookahead guard and it is not optional: a 4H
    trade may only know the 1D regime that had already confirmed when it was
    taken. `confirmed_at` is when the engine could have known; reading by
    `market_time` here would let a trade see a regime label derived from its
    own future.
    """
    cur = None
    for conf, val in series:
        if conf > ts:
            break
        cur = val
    return cur


def composite(sides) -> str:
    """Fold per-rung sides into one state. See the module docstring.

    `sides` is an iterable of "UP" / "DOWN" / "FLAT" / None, one per rung.
    None means that rung had no reading and is skipped — it must not drag the
    composite toward FLAT, because "we did not look" and "we looked and it was
    quiet" are different findings and the whole UNKNOWN rule exists to keep
    them apart.
    """
    measured = [s for s in sides if s is not None]
    if not measured:
        return "UNKNOWN"
    trending = {s for s in measured if s in ("UP", "DOWN")}
    if not trending:
        return "FLAT"
    if len(trending) > 1:
        return "MIXED"
    return trending.pop()


def alignment(comp: str, direction: str) -> str:
    """Where a trade in `direction` stands against the composite.

    WITH / AGAINST only exist when the ladder has actually taken a side.
    MIXED, FLAT and UNKNOWN pass through as themselves rather than collapsing
    into AGAINST, so a policy can treat "the rungs disagree" differently from
    "the rungs are against me" — they are different market conditions and
    folding them together is the same mistake as folding UNKNOWN into AGAINST.
    """
    if comp in ("MIXED", "FLAT", "UNKNOWN"):
        return comp
    want = _WANT_SIDE.get(direction)
    if want is None:
        raise ValueError(f"unknown direction {direction!r} — LONG or SHORT")
    return "WITH" if comp == want else "AGAINST"


def validate_policy(policy: dict, who: str = "policy") -> dict:
    """Reject a malformed policy at import time rather than at trade time.

    Three rules, each of which has a measurement or a defect behind it:
      * every alignment answered — a playbook silent on MIXED has not decided
      * every action in the closed vocabulary — see ACTIONS
      * UNKNOWN maps to ALLOW — see the module docstring; scoring a missing
        measurement as a bad one cost 1.02 R/trade and fell entirely on the
        only profitable timeframe
    """
    missing = [a for a in ALIGNMENTS if a not in policy]
    if missing:
        raise ValueError(f"{who}: no action declared for {missing} — every "
                         f"alignment in bias.ALIGNMENTS must be answered")
    unknown = {k for k in policy if k not in ALIGNMENTS}
    if unknown:
        raise ValueError(f"{who}: unknown alignment(s) {sorted(unknown)} — "
                         f"add them to bias.ALIGNMENTS and the tests, or fix "
                         f"the typo")
    for k, v in policy.items():
        if v not in ACTIONS:
            raise ValueError(f"{who}: {k} -> {v!r} is not one of "
                             f"{sorted(ACTIONS)}")
    if policy["UNKNOWN"] != "ALLOW":
        raise ValueError(
            f"{who}: UNKNOWN -> {policy['UNKNOWN']!r}. A missing measurement "
            f"must never be scored as a bad one — see engine/bias.py. If you "
            f"have evidence that changes, change it there once, with the "
            f"measurement, not here.")
    return policy


def verdict(read: dict, direction: str, policy: dict,
            evidence_ok=None) -> dict:
    """Pure: the reading plus a policy plus the evidence flag -> what to do.

    Pure on purpose. The 2x2 harness has to be able to ask "what would this
    policy have done" for a historical moment without a store connection, and
    a rule that can only run inside an engine cannot be counterfactualled —
    which is how a filter ships ungraded.

    `resolved` is the action after REQUIRE_EVIDENCE is settled; `action` keeps
    the policy's own word so a fact records what the rule SAID as well as what
    happened to it. `evidence_ok=None` with a REQUIRE_EVIDENCE action means
    the caller never looked, which resolves to BLOCK — refusing to treat an
    unasked question as a satisfied one.
    """
    align = alignment(read["composite"], direction)
    action = policy[align]
    if action == "REQUIRE_EVIDENCE":
        resolved = "ALLOW" if evidence_ok else "BLOCK"
    else:
        resolved = action
    return {"alignment": align, "action": action, "resolved": resolved,
            "evidence_ok": evidence_ok, "composite": read["composite"],
            "rungs": read["rungs"], "version": BIAS_VERSION}


class Bias:
    """One symbol/timeframe's view up the ladder, loaded once, read many times.

    Built as an object rather than a function because the callers are bar
    loops over thousands of candles: `trend.run` would otherwise re-query the
    store per candidate. The series are plain lists of (confirmed_at, value)
    so a test can construct one directly with no database at all — which is
    how the policy rules below get tested without fixtures.
    """

    def __init__(self, tf: str, rungs: dict, breaks: list):
        self.tf = tf
        self.rungs = rungs           # {rung_tf: [(confirmed_at, side|None)]}
        self.breaks = breaks         # [(confirmed_at, side)] on THIS tf

    def reading(self, as_of: int) -> dict:
        """What every rung above was showing at `as_of`, and the composite."""
        per = {r: _as_of(s, as_of) for r, s in self.rungs.items()}
        return {"rungs": per, "composite": composite(per.values()),
                "version": BIAS_VERSION}

    def evidence(self, direction: str, as_of: int, tf_seconds: int,
                 max_bars: int = EVIDENCE_MAX_BARS) -> dict:
        """Did structure just break in this trade's favour, and how recently?

        The counter-trend permission slip, and deliberately ONE predicate. The
        prior project's version of this grew a sweep test, a divergence test
        and a pullback-quality proxy, each with its own threshold, and the
        combination is what made its counter-HTF rule untunable — the code's
        own comment records that its ranging check "always returns 'normal'",
        so the block fired more often than designed for an unknown period.
        One predicate can be graded; four cannot be told apart.
        """
        want = _WANT_SIDE.get(direction)
        if want is None:
            raise ValueError(f"unknown direction {direction!r} — LONG or SHORT")
        window = max_bars * tf_seconds
        best = None
        for conf, side in self.breaks:
            if conf > as_of:
                break
            if side == want and as_of - conf <= window:
                best = conf
        return {"ok": best is not None, "at": best,
                "bars_ago": None if best is None else (as_of - best) // tf_seconds,
                "max_bars": max_bars}

    def check(self, direction: str, as_of: int, tf_seconds: int,
              policy: dict) -> dict:
        """The whole block a setup fact should carry. The one call an engine makes.

        Evidence is only looked up when the policy actually asks for it —
        `evidence_ok` stays None otherwise, so a fact never claims a test was
        run that was not.
        """
        read = self.reading(as_of)
        align = alignment(read["composite"], direction)
        ev = None
        if policy[align] == "REQUIRE_EVIDENCE":
            ev = self.evidence(direction, as_of, tf_seconds)
        out = verdict(read, direction, policy,
                      evidence_ok=None if ev is None else ev["ok"])
        out["evidence"] = ev
        return out


def load(con, symbol: str, tf: str) -> Bias:
    """Read every rung's regime series and this timeframe's breaks, once."""
    rungs = {}
    for rung in rungs_above(tf):
        series = []
        for r in store.get_facts(con, symbol, rung, "regime", REGIME_VERSION):
            reg = json.loads(r["payload"]).get("regime")
            series.append((r["confirmed_at"], _SIDE_BY_REGIME.get(reg)))
        # Key on the timestamp alone. An unmapped regime yields None, and two
        # readings confirmed on the same second would put None beside a string
        # in the tuple comparison — a TypeError at scan time, on data rather
        # than on code, which is the kind that only shows in production.
        series.sort(key=lambda x: x[0])
        rungs[rung] = series
    breaks = []
    for r in store.get_facts(con, symbol, tf, "structure", STRUCTURE_VERSION):
        p = json.loads(r["payload"])
        if p.get("event") in EVIDENCE_EVENTS:
            side = _DIR_SIDE.get(p.get("direction"))
            if side:
                breaks.append((r["confirmed_at"], side))
    breaks.sort(key=lambda x: x[0])
    return Bias(tf, rungs, breaks)


def inputs() -> dict:
    """What a strategy manifest should record about this layer's own inputs."""
    return {"bias": BIAS_VERSION, "regime": REGIME_VERSION,
            "structure": STRUCTURE_VERSION}
