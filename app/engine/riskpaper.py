"""The paper book's own risk authority — same rules, its own account.

`risk.py` is the RESEARCH replay: it walks a simulated account from the first
bar of the baseline and rules on every setup in it. That is the right shape for
measuring a strategy and the wrong shape for running one, because the account
it sizes against never held an order.

This is the forward book. It rules only on setups that are still live, against
the balance, exposure, cooldowns and halts in `paperbook`, and writes its
verdict under its own kind so nothing can confuse the two populations again.

    risk.py      kind "risk"       the replay's account, every setup ever
    riskpaper.py kind "risk_paper" the paper ledger, the setups live now

Both call `risk.decide`. That is deliberate and load-bearing: sharing the rules
was never the problem — sharing STATE was, and it cost the paper book every
trade it might have taken between August and 2026-09-11.

WHY THE DECISION IS NOT REWRITTEN EVERY CYCLE. A paper decision depends on the
account as it stands, so its `confirmed_at` is the moment it was made, not the
setup's. Stamping wall-clock on an unchanged verdict every scan would append
roughly six thousand identical facts a day and drown the store, so a fact is
written only when the verdict actually MOVES. The history then reads as what it
is: the moments this book changed its mind.
"""
from __future__ import annotations

import time
from decimal import Decimal

from . import paperbook, risk, store
from .contracts import AutomationMode
from .execsim import EXEC_VERSION
from .runlog import RunRecorder
from .setups import SETUP_VERSION


PAPER_RISK_VERSION = "riskpaper-v0.2-draft"
# v0.2: three corrections found by review, all of which let the book
# approve more than it could fund.
#  - RESERVATIONS COUNT. Budget and slots now include money an unfilled
#    order has already claimed. Without it a second trade was approved
#    against a budget the first was holding.
#  - EACH CANDIDATE SEES THE ONES BEFORE IT. The snapshot is taken once,
#    so every candidate in a scan was sized against the same untouched
#    balance — with MAX_CONCURRENT=1 that is a deck of orders for one slot.
#  - THE CLOCK IS NOW, not the setup's confirmation. Cooldowns, the daily
#    halt and the same-side governor were read at the moment the setup
#    confirmed, so a stop-out since would not block the next entry.

#: The fact kind. Separate from "risk" rather than a field on it, because
#: `_latest_by_setup` selects on (kind, algo_version) and nothing in the store
#: carries a domain column — so the domain has to live in the kind. Putting it
#: in `algo_version` instead would make one field answer two questions ("which
#: rules" and "whose account"), which is how the two populations became
#: indistinguishable in the first place.
PAPER_RISK_KIND = "risk_paper"

#: Fields that decide whether the verdict MOVED. Deliberately not the whole
#: payload: `equity_at` drifts by pennies as costs settle, and re-writing a
#: fact because the account moved $0.03 under an unchanged decision is noise,
#: not evidence.
_MATERIAL = ("decision", "reasons", "risk_usd", "units")


def _latest(con) -> dict[str, dict]:
    """The most recent paper verdict per setup_id."""
    import json
    out: dict[str, dict] = {}
    for (raw,) in con.execute(
            "SELECT payload FROM facts WHERE kind=? AND algo_version=? "
            "ORDER BY confirmed_at, id", (PAPER_RISK_KIND, PAPER_RISK_VERSION)):
        payload = json.loads(raw)
        if payload.get("event") == "DECISION" and payload.get("setup_id"):
            out[payload["setup_id"]] = payload
    return out


def _moved(previous: dict | None, payload: dict) -> bool:
    if previous is None:
        return True
    return any(previous.get(k) != payload.get(k) for k in _MATERIAL)


def live_intents(con, baseline_start: int, now: int) -> list[dict]:
    """Setups this book could still act on: validated, and not yet expired.

    The replay rules on everything since the baseline because it is measuring
    history. A forward book ruling on a setup whose entry window shut days ago
    would be sizing a trade nobody can take against an account that has moved
    since — a number with no meaning and a slot it would wrongly consume.
    """
    out = []
    for intent in risk.load_intents(con, baseline_start):
        expires = intent.get("expires_at_ts") or intent.get("expires_at")
        try:
            if expires is not None and int(expires) <= now:
                continue
        except (TypeError, ValueError):
            # An unreadable expiry is unsafe for an entry decision, exactly as
            # the read model treats it. Skip rather than guess.
            continue
        out.append(intent)
    return out


def run(con, *, now: int | None = None) -> dict:
    """Rule on every live setup against the paper account as it stands now."""
    now = int(time.time()) if now is None else int(now)
    with RunRecorder(con, "risk_paper", PAPER_RISK_VERSION,
                     "PORTFOLIO", "ALL") as rec:
        baseline = store.get_active_baseline(con)
        baseline_start = int(baseline["started_at"])
        # PAPER unconditionally. The gates are identical in every mode and
        # only the R SIZE differs, so this book rehearses the live one; and
        # reading the operating mode here would let a mode flip mint a second
        # generation of verdicts under one version label.
        gates = risk.gates_for_mode(AutomationMode.PAPER)
        policy = risk.policy_for(con, gates, baseline_start)
        account = paperbook.snapshot(
            con, mode=AutomationMode.PAPER, gates=gates,
            max_drawdown_pct=policy["max_drawdown_pct"])
        # THE COOLDOWNS ARE THIS BOOK'S, not the replay's. `policy_for` loads
        # the research locks — derived from `exec` facts — and reading those
        # here would refuse a paper entry because the SIMULATOR stopped out on
        # that symbol. Measured 2026-09-11, with the rest of the separation
        # already done and this input still missed: PF_PUMPUSD LONG locked for
        # three more hours off a trade the paper book had never taken.
        #
        # The evaluator stays shared. `cooldowns.blocked_at` owns what
        # "blocking at this instant" means — overlapping locks, the
        # point-in-time rule, later-expiry-wins — and only the SOURCE differs.
        from . import cooldowns as _cooldowns
        policy = dict(
            policy,
            cooldown=lambda ts, sym, side: _cooldowns.blocked_at(
                account["cooldowns"], ts, sym, side),
            # THIS BOOK RULES NOW. The replay's clock is each setup's own
            # `confirmed_at`, which is right for history and wrong here: a
            # stop-out an hour ago would not count against today for a setup
            # that confirmed yesterday, and a cooldown started since would not
            # block. The loss controls have to be read at the moment of the
            # decision, which is this instant.
            decision_at=now)
        intents = live_intents(con, baseline_start, now)
        rec.n_inputs = len(intents)
        previous = _latest(con)
        counts = {"APPROVED": 0, "REDUCED": 0, "REJECTED": 0}
        written = 0

        # EVERY CANDIDATE IN A SCAN SEES WHAT THE ONES BEFORE IT CLAIMED.
        # The snapshot is taken once, so without this each candidate is sized
        # against the same untouched balance and a scan can approve the whole
        # deck against one budget — with MAX_CONCURRENT=1 that is several
        # orders for a single slot. The claims are intra-cycle bookkeeping
        # only: nothing is dispatched until `autotrader.run`, and next cycle
        # the snapshot rebuilds from what the outbox and the book actually
        # hold. So an approval that never routes releases itself.
        book = dict(account)
        for intent in intents:
            verdict = risk.decide(intent, book, policy)
            if verdict["decision"] != "REJECTED":
                book = dict(book,
                            reserved_risk_usd=(book.get("reserved_risk_usd", Decimal(0))
                                               + verdict["risk_usd"]),
                            reserved_slots=(book.get("reserved_slots", 0)
                                            + (0 if intent["strategy"] == "SCALE_IN" else 1)))
            payload = {
                "event": "DECISION", "setup_id": intent["setup_id"],
                "decision": verdict["decision"], "reasons": verdict["reasons"],
                "intended_risk_usd": str(verdict["intended_risk_usd"]),
                "risk_usd": str(verdict["risk_usd"]),
                "risk_pct": str(gates["risk_pct"]),
                # Not "PAPER", which the replay already uses to mean its own
                # simulated book. This one names the ledger.
                "pct_basis": "PAPER_LEDGER",
                "equity_at": str(account["equity"]),
                "committed_risk_usd": str(account["committed_risk_usd"]),
                "open_positions": account["concurrent"],
                "baseline_id": baseline["id"],
                "baseline_started_at": baseline_start,
                # WHICH GENERATION THIS VERDICT IS ABOUT. The setups ruled on
                # come from `risk.load_intents` and the ledger's P&L from exec
                # settlement, so this book is coupled to both even though it
                # imports neither reader directly — and a coupling the cascade
                # map claims but the source never names is one nobody can
                # check. Stamped rather than asserted: a fact that carries its
                # own provenance can be placed when the tags move on.
                "setup_version": SETUP_VERSION,
                "exec_version": EXEC_VERSION,
            }
            if verdict["units"] is not None:
                payload.update({
                    "units": str(verdict["units"].quantize(Decimal("0.00000001"))),
                    "notional_usd": str(verdict["notional_usd"]),
                    "implied_leverage": str(verdict["implied_leverage"])})
            counts[verdict["decision"]] += 1
            if not _moved(previous.get(intent["setup_id"]), payload):
                continue
            if store.insert_fact(
                    con, symbol=intent["symbol"], tf=intent["tf"],
                    kind=PAPER_RISK_KIND, market_time=intent["market_time"],
                    # When it could first be known: this verdict depends on the
                    # account as it stands, not on the bar that confirmed the
                    # setup. Convention 3, applied to a forward decision.
                    confirmed_at=now, algo_version=PAPER_RISK_VERSION,
                    payload=payload):
                written += 1

        return {"equity": str(account["equity"]),
                "committed_risk_usd": str(account["committed_risk_usd"]),
                "open_positions": account["concurrent"],
                "reserved_slots": account["reserved_slots"],
                "unpriced_intents": account["unpriced_intents"],
                "live_intents": len(intents), "written": written,
                "version": PAPER_RISK_VERSION, **counts}
