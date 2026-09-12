"""The paper account: whose money the paper book's decisions are a share of.

THE NUMBER THIS OWNS is the paper account's state — equity, what is at risk
right now, what has been lost today and on which side. Nothing else owns it,
because until this module existed nothing owned it at all.

What was there instead: `risk.run()` walked `START_EQUITY` forward through the
RESEARCH replay's simulated exits and stamped that figure onto every decision
as `equity_at`, and `autotrader` recorded the provenance honestly as
`equity_basis_source="PAPER_REPLAY"`. So a live cycle sized real paper orders
against a balance that only existed inside a backtest, and refused them for
`CONCURRENT_LIMIT`, `SAME_SIDE_HALT` and `COOLDOWN` on positions, losses and
stop-outs that had happened only in replay. Measured on the live store
2026-09-11: 23 blocks for a slot occupied by a simulated position, 19 for
same-day losses nothing had actually taken, while `paper_positions` held zero
rows.

The boundary, stated once:

    execution.py owns the ORDER  — the outbox is the lifecycle authority
    paperbook.py owns the ACCOUNT — equity, exposure, realised P&L

Two authorities, two different numbers, no overlap. `paper_positions.state`
is deliberately not read here as a lifecycle; it is read for the trades it
holds.

DOLLARS ARE NOT RE-DERIVED. `paper_positions` stores `r_multiple` and costs in
price units and no dollar figure at all, so the money is reconstructed as
`r_multiple x risk_usd`, where `risk_usd` is read from the execution plan the
outbox stored at dispatch. That is the figure the sizing decision was actually
made with; recomputing it from prices here would be a second authority for a
number that already has one.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from .contracts import AutomationMode


PAPERBOOK_VERSION = "paperbook-v0.3-draft"
# v0.3: RE-ENTRY LOCKS ARE THIS BOOK'S OWN. The last input the domain
# separation missed: equity, concurrency and the same-side governor moved
# onto the ledger, cooldowns did not, and the paper risk pass kept reading
# locks derived from the replay's exits. Measured 2026-09-11, with the rest
# of the work already done and this still live: PF_PUMPUSD LONG locked for
# three more hours off a stop-out the paper book had never taken. Rules and
# evaluator stay shared (`cooldowns`); only the source differs.
# v0.2: the book decomposes its realised money by OUTCOME CLASS.
# "We lost $84 today" is not an answer anyone can act on; "$84 of
# market losses, nothing broken" and "$84 because two orders were
# rejected" call for completely different responses. The
# classification is telemetry's, not restated here.

#: What the paper book opens with.
#:
#: Deliberately the same figure the research replay starts from
#: (`risk.START_EQUITY`), and imported rather than restated so the two cannot
#: drift apart. Sharing the OPENING BALANCE is not the thing this module
#: exists to separate — sharing live account STATE was. Two books may start
#: from the same number and must never share what happens to it afterwards.
#:
#: Changing it is one edit here, but it is not free: `setups.py` reads
#: `risk.START_EQUITY` when arming, so a paper book opening at a different
#: balance would move the setup facts and cascade through exec/risk/scale/
#: cooldown. Decide that deliberately, not in passing.
def opening_equity() -> Decimal:
    from .risk import START_EQUITY
    return START_EQUITY


def _day(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def _plan_risk_usd(raw: str | None) -> Decimal:
    """The `risk_usd` the dispatcher sized this intent with, or zero.

    Zero is the honest answer for a legacy row whose payload predates the
    plan being stored: it contributes no exposure and no P&L rather than
    inventing a figure. It cannot be silent, so `snapshot` counts these and
    reports them — a book quietly missing half its risk is the failure this
    whole phase exists to stop.
    """
    if not raw:
        return Decimal(0)
    try:
        plan = json.loads(raw)
    except (TypeError, ValueError):
        return Decimal(0)
    risk = plan.get("risk") if isinstance(plan, dict) else None
    if not isinstance(risk, dict):
        return Decimal(0)
    try:
        return Decimal(str(risk.get("risk_usd") or 0))
    except (TypeError, ValueError):
        return Decimal(0)


#: Outbox states holding a RESERVATION: the intent exists and may still become
#: exposure, so its risk is committed even though no position is open. Sizing
#: that ignores these can approve a second trade against a budget the first
#: one has already claimed but not yet filled.
_RESERVED = ("PENDING", "SUBMITTING", "SUBMITTED", "PAPER_ROUTED",
             "SHADOW_RECORDED", "PARTIALLY_FILLED")


def _cooldowns(closed: list[dict]) -> list[dict]:
    """Re-entry locks earned by THIS book's own stop-outs.

    `cooldowns.run` derives the research replay's locks from its `exec` facts,
    and until this existed the paper risk pass read those — so a paper entry
    could be refused because the SIMULATOR had stopped out on that symbol.
    Measured 2026-09-11, three days after the domain separation and still
    live: PF_PUMPUSD LONG locked for another three hours off a trade the paper
    book had never taken.

    The RULES are not restated. Duration, the invalidating-outcome set and the
    key all come from `cooldowns`, and the payloads are shaped so
    `cooldowns.blocked_at` evaluates them unchanged — one evaluator, one rule
    table, two sources. Copying the duration table here is how the two books
    would start cooling for different lengths of time.

    Derived in memory rather than written as facts, like every other paper
    halt in this module: a lock is a pure function of closes that already
    exist, and state that is mutated as trades close cannot be replayed.
    """
    from . import cooldowns as rules
    out = []
    for trade in closed:
        outcome, tf = trade.get("outcome"), trade.get("tf")
        if not outcome or outcome == "MISSED" or not trade.get("direction"):
            continue                     # no position was taken; nothing to cool
        hours = rules.duration_hours(outcome, tf)
        exit_ts = int(trade["closed_at"])
        out.append({
            "key": rules.key(trade["symbol"], trade["direction"]),
            "symbol": trade["symbol"], "direction": trade["direction"],
            "tf": tf, "outcome": outcome, "hours": hours,
            # The EXIT time, not the moment this ran. A lock that began when
            # the snapshot was taken would refuse different trades on a replay
            # than it did live.
            "market_time": exit_ts,
            "expires_at": int(exit_ts + hours * rules.HOUR),
            "setup_id": trade.get("setup_id"),
            "invalidating": outcome in rules.INVALIDATING,
        })
    return out


def _by_outcome_class(closed: list[dict]) -> dict[str, dict]:
    """The book's realised money, split by WHAT KIND of thing happened.

    "We lost $84 today" is not an answer anyone can act on. "$84 of market
    losses, nothing broken" and "$84 because two orders were rejected" call
    for completely different responses, and the only way to tell them apart
    after the fact is to have recorded which it was.

    The classification is `telemetry`'s and is not restated here — one
    authority. This decomposes; it does not judge. Every closed trade lands in
    exactly one bucket, so the parts sum to the whole with no residual, and
    the test that matters asserts precisely that.
    """
    from . import telemetry
    out: dict[str, dict] = {}
    for trade in closed:
        life = telemetry.classify_failure(
            None, None, {"outcome": trade["outcome"],
                         "r_multiple": str(trade["r_multiple"])})
        bucket = out.setdefault(telemetry.outcome_class(life),
                                {"trades": 0, "pnl_usd": Decimal(0),
                                 "r": Decimal(0)})
        bucket["trades"] += 1
        bucket["pnl_usd"] += trade["pnl_usd"]
        bucket["r"] += trade["r_multiple"]
    return out


def snapshot(con, *, mode: AutomationMode = AutomationMode.PAPER,
             gates: dict | None = None,
             max_drawdown_pct: float | Decimal = 0) -> dict:
    """Everything a sizing decision needs to know about the paper account.

    Point-in-time by construction: it reads only what has already been
    recorded. The live cycle must therefore settle the paper book BEFORE
    asking for this, or a decision sizes against the equity of the previous
    cycle (`live.py` runs `monitor_paper` ahead of the paper risk pass for
    exactly this reason).

    `gates` and `max_drawdown_pct` are needed for the halts — which days the
    daily loss limit closed, and whether total drawdown has tripped. Omit them
    to read the raw book without a verdict on it.
    """
    from . import execution
    execution._ensure(con)
    opening = opening_equity()

    plans: dict[str, Decimal] = {}
    setup_of: dict[str, str] = {}
    reserved: dict[str, Decimal] = {}
    unpriced = 0
    for intent_id, setup_id, state, payload in con.execute(
            "SELECT intent_id,setup_id,state,payload FROM execution_outbox "
            "WHERE mode=?", (mode.value,)):
        risk_usd = _plan_risk_usd(payload)
        plans[intent_id] = risk_usd
        setup_of[intent_id] = setup_id
        if not risk_usd:
            unpriced += 1
        if str(state or "").upper() in _RESERVED:
            reserved[intent_id] = risk_usd

    open_positions: list[dict] = []
    closed: list[dict] = []
    for row in con.execute(
            "SELECT intent_id,symbol,tf,direction,state,filled_at,closed_at,"
            "outcome,r_multiple FROM paper_positions ORDER BY filled_at, rowid"):
        (intent_id, symbol, tf, direction, state, filled_at, closed_at,
         outcome, r) = row
        if intent_id not in plans:
            # A paper position whose intent is not in the PAPER outbox belongs
            # to another mode's book. Never silently pooled.
            continue
        risk_usd = plans[intent_id]
        setup_id = setup_of.get(intent_id, "")
        if str(state or "").upper() == "CLOSED" and r is not None:
            closed.append({"intent_id": intent_id, "setup_id": setup_id,
                           "symbol": symbol, "tf": tf, "outcome": outcome,
                           "direction": direction, "closed_at": int(closed_at or 0),
                           "r_multiple": Decimal(str(r)),
                           "pnl_usd": Decimal(str(r)) * risk_usd})
        else:
            open_positions.append({"intent_id": intent_id, "setup_id": setup_id,
                                   "symbol": symbol,
                                   "direction": direction,
                                   "filled_at": int(filled_at or 0),
                                   "risk_usd": risk_usd})
            # An open position's risk is exposure, not a reservation; counting
            # it in both would double it.
            reserved.pop(intent_id, None)

    closed.sort(key=lambda c: (c["closed_at"], c["intent_id"]))
    equity = opening
    peak = opening
    realised_by_day: dict[str, Decimal] = {}
    day_start_equity: dict[str, Decimal] = {}
    #: Named `side_losses` to match `risk.decide`'s account contract exactly.
    #: One name for one thing: a snapshot key that has to be translated on the
    #: way into the rules is a rename waiting to be got wrong.
    side_losses: dict[tuple, int] = {}
    halted_days: set[str] = set()
    drawdown: dict | None = None
    dd_limit = Decimal(str(max_drawdown_pct or 0)) / Decimal(100)
    daily_loss_pct = (gates or {}).get("daily_loss_limit_pct")
    for trade in closed:
        day = _day(trade["closed_at"])
        day_start_equity.setdefault(day, equity)
        equity += trade["pnl_usd"]
        peak = max(peak, equity)
        realised_by_day[day] = realised_by_day.get(day, Decimal(0)) + trade["pnl_usd"]
        # A loss is r < 0 — a TIMEOUT that closed under water counts, because
        # the side was wrong however it ended — and size-agnostic, so a
        # REDUCED entry counts once like any other. An |ADD is not a position
        # (CONCURRENT_LIMIT already says so), so a scale-in stopping at its
        # parent's entry is one idea being wrong once, not twice. Same rule as
        # the replay's `settle`, deliberately: two books, one rulebook.
        if trade["r_multiple"] < 0 and trade["direction"] and \
                "|ADD" not in trade["setup_id"]:
            key = (day, str(trade["direction"]).upper())
            side_losses[key] = side_losses.get(key, 0) + 1
        # Total-drawdown guardrail. The daily halt catches a bad DAY; this
        # catches a bad month that never trips it — a slow bleed of small
        # losses can drain the account without any single day breaching the
        # daily limit. Trips once and stays tripped, as the replay's does.
        if dd_limit > 0 and peak > 0 and drawdown is None:
            dd = (peak - equity) / peak
            if dd >= dd_limit:
                drawdown = {"at": trade["closed_at"], "peak": str(peak),
                            "equity": str(equity),
                            "drawdown_pct": str((dd * 100).quantize(Decimal("0.01")))}
        if daily_loss_pct is not None:
            if realised_by_day[day] <= -(daily_loss_pct * day_start_equity[day]):
                halted_days.add(day)

    open_risk = sum((p["risk_usd"] for p in open_positions), Decimal(0))
    reserved_risk = sum(reserved.values(), Decimal(0))
    return {
        "mode": mode.value,
        "halted_days": halted_days,
        "drawdown": drawdown,
        #: Re-entry locks this book earned itself, in the shape
        #: `cooldowns.blocked_at` evaluates.
        "cooldowns": _cooldowns(closed),
        "by_outcome_class": _by_outcome_class(closed),
        "opening_equity": opening,
        "equity": equity,
        "peak_equity": peak,
        "open_positions": open_positions,
        "open_risk_usd": open_risk,
        "reserved_risk_usd": reserved_risk,
        #: What a concurrency or budget gate must compare against: money in
        #: the market PLUS money an unfilled intent has already claimed.
        "committed_risk_usd": open_risk + reserved_risk,
        "concurrent": len(open_positions),
        "reservations": len(reserved),
        "realised_by_day": realised_by_day,
        "day_start_equity": day_start_equity,
        "side_losses": side_losses,
        "closed_count": len(closed),
        #: Loud, per the fallback rule: intents whose stored plan carried no
        #: `risk_usd` contribute nothing to exposure or P&L, and a reader that
        #: cannot see how many there are cannot tell a quiet book from a
        #: broken one.
        "unpriced_intents": unpriced,
        "version": PAPERBOOK_VERSION,
    }
