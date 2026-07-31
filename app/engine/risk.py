"""Risk Authority — §9: strategies request risk, this engine decides. Paper only.

Portfolio-scoped (one pass over ALL symbols/timeframes in strict time order —
risk is an account property, not a per-chart property). For every VALIDATED
setup intent, at its confirmed_at moment:
  1. settle any positions whose exits have occurred (equity moves),
  2. check the kill switch (daily realized loss beyond limit halts the day, §9/§13),
  3. check concurrent-position and total-open-risk limits (BTC and ETH count
     together — correlated crypto exposure),
  4. size the position: risk_usd = equity * RISK_PCT; units = risk_usd / stop
     distance; implied leverage capped by reducing size, never by widening
     stops (§9: stops are structure).
Decisions: APPROVED / REDUCED / REJECTED — each a fact with machine-readable
reasons (§8: rejections are as auditable as approvals).
"""
import json
from datetime import datetime, timezone
from decimal import Decimal

from . import store, venues
from .setups import SETUP_VERSION
from .execsim import EXEC_VERSION
from .runlog import RunRecorder
from .universe import admitted_at

RISK_VERSION = "risk-v0.18-draft"
# v0.18: the exit join merged exits. `exits` was keyed on `setup_id` alone, but
# a plan is re-simulated whenever the cost/venue manifest moves and each re-run
# writes its own exec fact under the same tag — so `setup_id` is not unique
# inside ONE book, never mind across generations. Measured on the store:
# exec-v0.8 carries 112 of 452 setup_ids with more than one exec fact,
# exec-v0.16 carries 7. The account settled on whichever row the scan happened
# to reach last, and `get_facts` orders market_time-major, so that was scan
# order rather than the newest costing.
#
# TWO distinct populations hide under one symptom, and they need different
# fixes — worth stating because the obvious single fix only covers one:
#  * Manifest re-runs are genuinely ONE trade costed several ways. Collapsing
#    them is CORRECT; only the arbitrary winner was wrong. They share
#    `available_at`, so the composite key does not separate them at all — the
#    explicit fact-id tie-break is what resolves these.
#  * Re-touches are different intents that a bare `setup_id` merged. The
#    composite key separates these — exec-v0.7, 25 ids down to 12.
#
# Honest scope: exec-v0.17 currently carries ZERO collisions (644 setup_ids), so
# this restates no number in today's book — it stops the merge recurring the
# next time the cost manifest moves, which is the event that produced all 119.
# Exec facts predating `available_at` (v0.1-v0.6, 786 facts) keep setup_id-only
# keying, because a tighter key that silently matched NOTHING would be a worse
# failure than the merge it set out to fix.
#
# This is the S37/S40 defect's other half. Version-scoping `setup_id` stopped
# two ENGINE GENERATIONS colliding; it did nothing about two facts from the
# same generation. Equity can move, so the tag moves with it.
# v0.17: cascade from exec-v0.18 and setup-v0.14, both downstream of zone-v0.12.
# Same reasoning as v0.16 below: this engine replays the account from exec
# facts, so a new exec generation is a new equity curve.
# v0.16: cascade from exec-v0.17. risk replays the whole account from exec
# facts, so an exec version move changes this engine's inputs and therefore its
# decisions and equity curve — even though no rule here changed. Leaving the tag
# put is the S37/S40 defect: two generations under one label.
# v0.13: cascade from exec-v0.14. The account replay is built from exec facts,
# and exec-v0.14 corrects a crossing leg that booked market fills at a price the
# bar never traded. Every equity figure downstream of those fills changes, so
# this tag moves with them rather than covering two generations of the book.
# v0.12: reads setup-v0.11 / exec-v0.13.

# v0.11: reads exec-v0.12, which now charges funding. Net R per trade moves,
# so equity and every sizing decision downstream of it moves.

# v0.10: reads setup-v0.10 / exec-v0.11. Sizing rules unchanged, but the math
# now lives in the pure `size_order` helper this module still owns (plan
# Phase C ruling, option A) and setups.py calls it at arming time.

# v0.9: sizing rules unchanged. Reads setup-v0.9 / exec-v0.10, plus the new
# participation cap (D4). Different intents and a new constraint -> different
# decisions.

# v0.8: no sizing rule changed. Its INPUTS did — this engine reads setup facts
# at SETUP_VERSION and exec facts at EXEC_VERSION, and S40 moved both
# (setup-v0.8, exec-v0.9) after the tick fix reclassified regimes on 35 of 59
# symbols. Different intents, different exits, different decisions. Leaving the
# tag at v0.7 would have written a second incompatible book under a label that
# already means something — the exact S37 defect, which this project has now
# committed twice and should stop committing.

# v0.7: shorting, leverage and the liquidation gate are venue-derived. Sizing
# rules (2%/4%/6%) are unchanged, but SHORT setups on a shorts-capable venue now
# reach sizing instead of being rejected outright, so decisions differ.
# v0.6: account accounting is scoped to the active non-destructive forward
# baseline. Strategy eligibility and sizing rules are unchanged.
# v0.4 (user directive 2026-07-21): per-trade risk 1% -> 2%. Coherently
# re-tuned the whole envelope so the concurrency and kill-switch don't silently
# break: total cap 2% -> 4% (keeps 2 concurrent at 2% each), daily halt 3% ->
# 6% (~3 stop-outs, not ~1.5), scale-in add 0.5% -> 1% (stays half a base).
# v0.2: governs SCALE_IN adds — exempt from the concurrency count (attach to a
# parent) but consume the total-open-risk budget; REJECTED with PARENT_CLOSED
# if the parent position already exited.
SCALE_RISK_PCT = Decimal("0.01")

START_EQUITY = Decimal("10000")
RISK_PCT = Decimal("0.02")            # 2% of current equity per trade
MAX_CONCURRENT = 2
MAX_TOTAL_OPEN_RISK_PCT = Decimal("0.04")   # 4% of equity at risk at once
# v0.7: shorting and leverage are VENUE capabilities, not process constants.
# As globals they rejected 31% of all validated setups (44 of 143) — every SHORT
# the playbook produced — because the only declared venue was Coinbase spot.
# `venues.venue_for(symbol)` now answers both, and a leveraged perp additionally
# has to prove its stop triggers before liquidation.
# The kept names below are the SPOT defaults, retained so any caller that has
# not been migrated still gets the conservative answer rather than a crash.
MAX_LEVERAGE = Decimal("1")              # spot default; see venues.max_leverage
ALLOW_SHORTS = False                     # spot default; see venues.allow_shorts
MIN_NOTIONAL_USD = Decimal("1")
# D4 — participation cap (SALVAGE §3.6). `universe.py` gates which SYMBOLS are
# liquid enough to trade; nothing gated whether a given POSITION is too large
# for the book it has to fill in. Those are different questions: a $3M/day pair
# clears the universe floor and still cannot absorb a position sized off a very
# tight stop without moving against you on both legs.
#
# Expressed as a share of the symbol's own 24h volume, which the universe fact
# already records — so this reads a number the system owns rather than inventing
# a second liquidity model. Inert in paper (no fills to move), which is exactly
# why it must exist BEFORE live: it is a constraint the simulator cannot teach.
MAX_PARTICIPATION = Decimal("0.005")          # 0.5% of 24h volume
DAILY_LOSS_LIMIT_PCT = Decimal("0.06")      # realized -6% in a UTC day -> halt
MIN_REDUCED_FRACTION = Decimal("0.25")      # reduce below 25% of intended -> reject
QC = Decimal("0.01")

TFS = ("15m", "1H", "4H", "1D", "1W")


def _venue_allows_shorts(symbol: str) -> bool:
    """Venue capability. An unrecognised symbol falls back to the SPOT answer —
    refusing the short — because assuming a market is shortable when it is not
    would record trades that could never have been placed."""
    try:
        return venues.allow_shorts(symbol)
    except ValueError:
        return ALLOW_SHORTS


def _venue_max_leverage(symbol: str) -> Decimal:
    """Same conservative fallback: 1x when the venue is unknown."""
    try:
        return venues.max_leverage(symbol)
    except ValueError:
        return MAX_LEVERAGE


def size_order(*, equity, entry, sl, direction, symbol, risk_pct=None,
               open_risk=Decimal(0), vol24=None, is_add=False) -> dict:
    """PURE sizing. No I/O, no facts, no clock — equity and a bracket in, a
    decision out.

    Extracted per the `forming-armed-order-plan` Phase C ruling (option A):
    §9 says the risk authority owns sizing, and it still does — this module owns
    the code. What changes is that `setups.py` can now CALL it at the moment a
    setup is armed, instead of the size being computed later at execution time.
    That is the whole point of the armed order: the thing that gets executed is
    the thing that was decided, provably, rather than something recomputed under
    different conditions and hoped to match.

    Everything the portfolio pass knows that this cannot — the kill switch, the
    concurrency count, cooldowns, point-in-time universe eligibility — stays in
    `run()`. Those are properties of the ACCOUNT at a moment; this is a property
    of one order. Mixing them here would make sizing untestable and would let a
    FORMING fact claim an approval the portfolio never granted.
    """
    reasons: list = []
    decision = "APPROVED"
    pct = risk_pct if risk_pct is not None else (SCALE_RISK_PCT if is_add else RISK_PCT)
    intended = (equity * pct).quantize(QC)
    risk_usd = intended
    stop_dist = abs(entry - sl)
    if stop_dist <= 0:
        return {"decision": "REJECTED", "reasons": ["INVALID_STOP_DISTANCE"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": str(intended)}

    budget = (MAX_TOTAL_OPEN_RISK_PCT * equity - open_risk).quantize(QC)
    if budget < intended:
        if budget < intended * MIN_REDUCED_FRACTION:
            return {"decision": "REJECTED", "reasons": ["EXPOSURE_LIMIT"],
                    "risk_usd": Decimal(0), "units": Decimal(0),
                    "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                    "intended_risk_usd": str(intended)}
        decision, reasons = "REDUCED", ["EXPOSURE_LIMIT"]
        risk_usd = budget

    venue_lev = _venue_max_leverage(symbol)
    units = risk_usd / stop_dist
    notional = units * entry
    lev = notional / equity if equity > 0 else Decimal(0)
    if lev > venue_lev:
        risk_usd = (risk_usd * (venue_lev / lev)).quantize(QC)
        units = risk_usd / stop_dist
        notional = units * entry
        lev = venue_lev
        if decision == "APPROVED":
            decision = "REDUCED"
        reasons.append(f"LEVERAGE_CAP({venue_lev}x)")

    ok, liq = venues.stop_survives_liquidation(entry, sl, lev, direction)
    if not ok:
        return {"decision": "REJECTED",
                "reasons": [f"STOP_BEYOND_LIQUIDATION({liq.quantize(QC)}"
                            f"@{lev.quantize(QC)}x)"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": str(intended)}

    if units * entry < MIN_NOTIONAL_USD:
        return {"decision": "REJECTED", "reasons": ["BELOW_MIN_NOTIONAL"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": str(intended)}

    if vol24:
        cap = MAX_PARTICIPATION * Decimal(str(vol24))
        if notional > cap > 0:
            risk_usd = (risk_usd * cap / notional).quantize(QC)
            units = risk_usd / stop_dist
            notional = units * entry
            lev = notional / equity if equity > 0 else Decimal(0)
            if decision == "APPROVED":
                decision = "REDUCED"
            reasons.append(
                f"PARTICIPATION_CAP({float(MAX_PARTICIPATION)*100:.1f}%_of_24h)")
            if risk_usd < intended * MIN_REDUCED_FRACTION:
                return {"decision": "REJECTED", "reasons": ["PARTICIPATION_TOO_THIN"],
                        "risk_usd": Decimal(0), "units": Decimal(0),
                        "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                        "intended_risk_usd": str(intended)}

    return {"decision": decision, "reasons": reasons or ["WITHIN_LIMITS"],
            "risk_usd": risk_usd,
            "units": units.quantize(Decimal("0.00000001")),
            "notional_usd": notional.quantize(QC),
            "implied_leverage": lev.quantize(QC),
            "intended_risk_usd": str(intended)}


def _symbols(con):
    """Every symbol with stored candles — portfolio scope spans the universe."""
    from .universe import all_tracked_symbols
    return all_tracked_symbols(con)


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def run(con) -> dict:
    with RunRecorder(con, "risk", RISK_VERSION, "PORTFOLIO", "ALL") as rec:
        from .scalein import SCALE_VERSION   # lazy: avoids circular import
        baseline = store.get_active_baseline(con)
        baseline_start = baseline["started_at"]
        intents, exits, legacy_exits = [], {}, {}
        n_exit_collisions = 0
        for sym in _symbols(con):
            for tf in TFS:
                for ver in (SETUP_VERSION, SCALE_VERSION):
                    for r in store.get_facts(con, sym, tf, "setup", ver):
                        p = json.loads(r["payload"])
                        if (p["state"] == "VALIDATED" and
                                r["confirmed_at"] >= baseline_start):
                            intents.append({"symbol": sym, "tf": tf,
                                            "market_time": r["market_time"],
                                            "confirmed_at": r["confirmed_at"],
                                            "universe_eligible": admitted_at(
                                                con, sym, r["confirmed_at"]), **p})
                for r in store.get_facts(con, sym, tf, "exec", EXEC_VERSION):
                    p = json.loads(r["payload"])
                    # S37/S40, the join half. Version-scoping `setup_id` stopped
                    # two ENGINE GENERATIONS colliding; it does nothing about two
                    # facts from the SAME generation. A plan is re-simulated
                    # whenever the cost/venue manifest moves, and each re-run
                    # writes its own exec fact under the same tag, so `setup_id`
                    # is not unique inside one book: exec-v0.8 has 112 of 452 ids
                    # carrying more than one exec fact, exec-v0.16 has 7.
                    #
                    # Those really are ONE trade costed several ways, so
                    # collapsing them is right — the defect is that WHICH one
                    # survived was arbitrary. `get_facts` orders by market_time
                    # first, so plain overwrite kept whichever row the scan
                    # happened to reach last, not the newest costing, and the
                    # settled equity curve moved with scan order. Ties are now
                    # broken on fact id, explicitly.
                    #
                    # The key is also tightened to the plan AND the bar it became
                    # actionable on, which is the true identity of an intent
                    # (execsim writes `available_at` from the setup's own
                    # confirmed_at — what the lookup below holds). On today's
                    # data that separates the exec-v0.7 re-touches, 25 ids down
                    # to 12; the manifest re-runs share available_at and are
                    # resolved by the id tie-break above. Verified on the live
                    # store: the tighter key matches exactly as many intents as
                    # `setup_id` did (644 of 654), so it costs no exit.
                    row = {"exit_ts": r["confirmed_at"],
                           "r_net": Decimal(p["r_multiple"]),
                           "outcome": p["outcome"], "fact_id": r["id"]}
                    if p.get("available_at") is None:
                        # exec-v0.1 through v0.6 predate the field — 786 facts in
                        # the store, plus any fixture that writes a bare outcome.
                        # They cannot be keyed by the bar they became actionable
                        # on, so they keep the old setup_id-only behaviour. A
                        # tighter key that silently matched NOTHING would be a
                        # worse failure than the merge it set out to fix.
                        legacy_exits[p["setup_id"]] = row
                        continue
                    key = (p["setup_id"], p["available_at"])
                    prev = exits.get(key)
                    if prev is not None:
                        # Same plan, same bar, different manifest: one trade
                        # costed two ways. The newest fact is the current truth,
                        # and it is chosen by fact id — `get_facts` orders by
                        # market_time first, so scan order is NOT id-major and
                        # "last one wins" would be arbitrary rather than latest.
                        n_exit_collisions += 1
                        if r["id"] < prev["fact_id"]:
                            continue
                    exits[key] = row
        intents.sort(key=lambda i: (i["confirmed_at"], i["market_time"], i["setup_id"]))
        rec.n_inputs = len(intents)

        equity = START_EQUITY
        open_pos: list[dict] = []
        daily_pnl: dict[str, Decimal] = {}
        day_start_equity: dict[str, Decimal] = {}
        halted: set[str] = set()
        curve: list[dict] = []
        n = {"APPROVED": 0, "REDUCED": 0, "REJECTED": 0, "KILL": 0}
        n_new_facts = 0

        _peak_box = [START_EQUITY]
        _dd_box: list = [None]

        def _set_peak(v):
            _peak_box[0] = v

        def _dd_halted():
            return _dd_box[0] is not None

        def _trip_dd(info):
            _dd_box[0] = info

        def settle(up_to_ts):
            nonlocal equity, n_new_facts
            for p in sorted([p for p in open_pos if p["exit_ts"] and p["exit_ts"] <= up_to_ts],
                            key=lambda p: p["exit_ts"]):
                d = _day(p["exit_ts"])
                day_start_equity.setdefault(d, equity)
                pnl = (p["risk_usd"] * p["r_net"]).quantize(QC)
                equity = (equity + pnl).quantize(QC)
                daily_pnl[d] = daily_pnl.get(d, Decimal(0)) + pnl
                curve.append({"ts": p["exit_ts"], "equity": str(equity)})
                open_pos.remove(p)
                # Total-drawdown guardrail. The daily halt catches a bad DAY;
                # this catches a bad month that never trips it — a slow bleed of
                # small losses can drain the account without any single day
                # breaching -6%.
                if equity > _peak_box[0]:
                    _set_peak(equity)
                dd_limit = Decimal(str(opcfg["max_drawdown_pct"])) / Decimal(100)
                if dd_limit > 0 and _peak_box[0] > 0:
                    dd = (_peak_box[0] - equity) / _peak_box[0]
                    if dd >= dd_limit and not _dd_halted():
                        _trip_dd({"at": p["exit_ts"], "peak": str(_peak_box[0]),
                                  "equity": str(equity),
                                  "drawdown_pct": str((dd * 100).quantize(QC))})
                        if store.insert_fact(
                                con, symbol="PORTFOLIO", tf="ALL", kind="risk",
                                market_time=p["exit_ts"], confirmed_at=p["exit_ts"],
                                algo_version=RISK_VERSION,
                                payload={"event": "DRAWDOWN_HALT",
                                         "peak_equity": str(_peak_box[0]),
                                         "equity": str(equity),
                                         "drawdown_pct": str((dd * 100).quantize(QC)),
                                         "limit_pct": str(opcfg["max_drawdown_pct"]),
                                         "baseline_id": baseline["id"],
                                         "reason": "total drawdown limit reached "
                                                   "— no new entries this window"}):
                            n_new_facts += 1
                loss_limit = DAILY_LOSS_LIMIT_PCT * day_start_equity[d]
                if d not in halted and daily_pnl[d] <= -loss_limit:
                    halted.add(d)
                    n["KILL"] += 1
                    if store.insert_fact(
                            con, symbol="PORTFOLIO", tf="ALL", kind="risk",
                            market_time=p["exit_ts"], confirmed_at=p["exit_ts"],
                            algo_version=RISK_VERSION,
                            payload={"event": "KILL_SWITCH", "day": d,
                                     "daily_pnl": str(daily_pnl[d]),
                                     "day_start_equity": str(day_start_equity[d]),
                                     "loss_limit_usd": str(loss_limit),
                                     "equity": str(equity),
                                     "baseline_id": baseline["id"],
                                     "baseline_started_at": baseline_start,
                                     "reason": "daily loss limit reached — no new entries today"}):
                        n_new_facts += 1

        # Operator halt and strategy toggles. Read once per run so a mid-run
        # edit cannot approve half the intents under one policy and half under
        # another. A halt blocks NEW entries only — open positions still settle,
        # because refusing to close a position is not a safety feature.
        from . import settings as _settings
        opcfg = _settings.all_settings(con)
        # Cooldowns are loaded ONCE and evaluated in memory. `active_at` runs a
        # query; calling it per intent inside the loop below would issue two
        # round-trips per candidate across hundreds of intents, on the hot path
        # of every scan cycle.
        from . import cooldowns as _cooldowns
        _cd_facts = _cooldowns.load(con, baseline_start=baseline_start)
        # 24h volume per symbol, read from the latest universe fact. One
        # authority: `universe.py` already measures this to decide admission,
        # and re-deriving it here would give two numbers that drift.
        _vol24: dict = {}
        try:
            from .universe import UNIVERSE_VERSION
            _row = con.execute(
                "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
                "ORDER BY id DESC LIMIT 1", (UNIVERSE_VERSION,)).fetchone()
            if _row:
                for _m in json.loads(_row[0])["members"]:
                    if _m.get("vol_usd"):
                        _vol24[_m["symbol"]] = _m["vol_usd"]
        except Exception:
            _vol24 = {}          # no universe fact yet -> cap simply inert
        # Data-health gate. Trading on data the audit says is BROKEN produces a
        # forward record that proves nothing — the results would be attributable
        # to the corruption as much as to the strategy.
        data_blocked = False
        if opcfg["halt_on_data_blocked"]:
            try:
                from . import quality
                rep = quality.cached_audit(con)
                data_blocked = bool(rep) and not rep.get("evaluation_allowed", True)
            except Exception:
                data_blocked = False          # never block on the gate itself failing
        _strategy_on = {
            "PULLBACK": opcfg["strategy_pullback"],
            "REVERSAL": opcfg["strategy_reversal"],
            "SCALE_IN": opcfg["strategy_scale_in"],
        }

        for it in intents:
            ts = it["confirmed_at"]
            settle(ts)
            entry, sl = Decimal(it["entry"]), Decimal(it["sl"])
            stop_dist = abs(entry - sl)
            reasons, decision = [], "APPROVED"
            is_add = it["strategy"] == "SCALE_IN"
            intended = (equity * (SCALE_RISK_PCT if is_add else RISK_PCT)).quantize(QC)
            risk_usd = intended

            parents_open = {p["setup_id"] for p in open_pos}
            if opcfg["halted"]:
                decision, reasons = "REJECTED", ["OPERATOR_HALT"]
            elif data_blocked:
                decision, reasons = "REJECTED", ["DATA_HEALTH_BLOCKED"]
            elif _dd_halted():
                decision, reasons = "REJECTED", [
                    f"DRAWDOWN_HALT({_dd_box[0]['drawdown_pct']}%)"]
            elif not _strategy_on.get(it["strategy"], True):
                decision, reasons = "REJECTED", [f"STRATEGY_DISABLED({it['strategy']})"]
            elif _cooldowns.blocked_at(_cd_facts, ts, it["symbol"],
                                       it["direction"]) is not None:
                # Re-entry control. Nothing stopped this system from buying a
                # level again the bar after it stopped out — tolerable while
                # REVERSAL fired 5 times in four years, not once it fires 471.
                # The cooldown FACT is carried into the reason so the operator
                # sees which exit caused the lockout, not just that one exists.
                _cd = _cooldowns.blocked_at(_cd_facts, ts, it["symbol"],
                                            it["direction"])
                decision = "REJECTED"
                reasons = [f"COOLDOWN({_cd['outcome']},{_cd['hours']}h)"]
            elif _day(ts) in halted:
                decision, reasons = "REJECTED", ["DAILY_LOSS_HALT"]
            elif not it["universe_eligible"]:
                decision, reasons = "REJECTED", ["NOT_IN_POINT_IN_TIME_UNIVERSE"]
            elif stop_dist <= 0:
                decision, reasons = "REJECTED", ["INVALID_STOP_DISTANCE"]
            elif it["direction"] == "SHORT" and not _venue_allows_shorts(it["symbol"]):
                decision, reasons = "REJECTED", ["SHORT_UNSUPPORTED_COINBASE_SPOT"]
            elif is_add and it.get("parent_setup_id") not in parents_open:
                decision, reasons = "REJECTED", ["PARENT_CLOSED"]
            elif not is_add and sum(1 for p in open_pos if "|ADD" not in p["setup_id"]) >= MAX_CONCURRENT:
                decision, reasons = "REJECTED", [f"CONCURRENT_LIMIT({MAX_CONCURRENT})"]
            else:
                open_risk = sum(p["risk_usd"] for p in open_pos)
                budget = (MAX_TOTAL_OPEN_RISK_PCT * equity - open_risk).quantize(QC)
                if budget < intended:
                    if budget < intended * MIN_REDUCED_FRACTION:
                        decision, reasons = "REJECTED", ["EXPOSURE_LIMIT"]
                    else:
                        decision, reasons = "REDUCED", ["EXPOSURE_LIMIT"]
                        risk_usd = budget
                venue_lev = _venue_max_leverage(it["symbol"])
                if decision != "REJECTED" and stop_dist > 0:
                    units = risk_usd / stop_dist
                    notional = units * entry
                    lev = notional / equity
                    if lev > venue_lev:
                        scale = venue_lev / lev
                        risk_usd = (risk_usd * scale).quantize(QC)
                        units = risk_usd / stop_dist
                        notional = units * entry
                        lev = venue_lev
                        if decision == "APPROVED":
                            decision = "REDUCED"
                        reasons.append(f"LEVERAGE_CAP({venue_lev}x)")

                    # Liquidation gate. On a leveraged perp the exchange can
                    # close the position before the stop is reached, at a loss
                    # LARGER than the one that was risked — which makes the stop
                    # decorative and every R-multiple downstream fiction.
                    ok, liq = venues.stop_survives_liquidation(
                        entry, sl, lev, it["direction"])
                    if not ok:
                        decision = "REJECTED"
                        reasons = [f"STOP_BEYOND_LIQUIDATION({liq.quantize(QC)}"
                                   f"@{lev.quantize(QC)}x)"]

                if decision != "REJECTED" and risk_usd > 0:
                    units = risk_usd / stop_dist
                    if units * entry < MIN_NOTIONAL_USD:
                        decision, reasons = "REJECTED", ["BELOW_MIN_NOTIONAL"]

                # Participation cap. REDUCES rather than rejects: a position too
                # large for the book is not a bad trade, it is a bad SIZE, and
                # the correct answer to a bad size is a smaller one.
                vol24 = _vol24.get(it["symbol"])
                if decision != "REJECTED" and vol24 and risk_usd > 0:
                    units = risk_usd / stop_dist
                    notional = units * entry
                    cap = MAX_PARTICIPATION * Decimal(str(vol24))
                    if notional > cap > 0:
                        risk_usd = (risk_usd * cap / notional).quantize(QC)
                        if decision == "APPROVED":
                            decision = "REDUCED"
                        reasons.append(
                            f"PARTICIPATION_CAP({float(MAX_PARTICIPATION)*100:.1f}%_of_24h)")
                        if risk_usd < intended * MIN_REDUCED_FRACTION:
                            decision, reasons = "REJECTED", ["PARTICIPATION_TOO_THIN"]
                            risk_usd = Decimal(0)

            if decision == "REJECTED":
                risk_usd = Decimal(0)
            payload = {"event": "DECISION", "setup_id": it["setup_id"],
                       "decision": decision, "reasons": reasons or ["WITHIN_LIMITS"],
                       "intended_risk_usd": str(intended), "risk_usd": str(risk_usd),
                       "equity_at": str(equity), "baseline_id": baseline["id"],
                       "baseline_started_at": baseline_start}
            if decision != "REJECTED" and stop_dist > 0:
                units = (risk_usd / stop_dist)
                payload.update({"units": str(units.quantize(Decimal("0.00000001"))),
                                "notional_usd": str((units * entry).quantize(QC)),
                                "implied_leverage": str((units * entry / equity).quantize(QC))})
                # Composite key, matching how `exits` was built above. The setup
                # payload never carries `confirmed_at` of its own (checked across
                # all 5,058 current setup facts), so the explicit value set when
                # the intent was built survives the `**p` splat and is the same
                # timestamp execsim recorded as `available_at`.
                ex = exits.get((it["setup_id"], it["confirmed_at"]))
                if ex is None:
                    ex = legacy_exits.get(it["setup_id"])
                payload["fill_outcome"] = ex["outcome"] if ex else "PENDING"
                if ex is None or ex["outcome"] != "MISSED":
                    open_pos.append({"setup_id": it["setup_id"], "risk_usd": risk_usd,
                                     "exit_ts": ex["exit_ts"] if ex else None,
                                     "r_net": ex["r_net"] if ex else Decimal(0)})
            n[decision] += 1
            if store.insert_fact(con, symbol=it["symbol"], tf=it["tf"], kind="risk",
                                 market_time=it["market_time"], confirmed_at=ts,
                                 algo_version=RISK_VERSION, payload=payload):
                n_new_facts += 1

        settle(2**53)
        # authoritative account summary — the UI reads THIS, never re-derives
        # equity (a second reconstruction would drift from the compounding +
        # kill-switch accounting done here). §8: one source of truth.
        peak = float(START_EQUITY)
        maxdd = 0.0
        for pt in curve:
            e = float(pt["equity"])
            peak = max(peak, e)
            maxdd = max(maxdd, (peak - e) / peak * 100 if peak else 0)
        # deterministic anchor: last settlement (not wall-clock) so a re-run over
        # identical data produces a byte-identical summary fact (idempotent).
        summ_ts = int(curve[-1]["ts"]) if curve else baseline_start
        if store.insert_fact(
                con, symbol="PORTFOLIO", tf="ALL", kind="account",
                market_time=summ_ts, confirmed_at=summ_ts,
                algo_version=RISK_VERSION,
                payload={"event": "SUMMARY", "start_equity": str(START_EQUITY),
                         "final_equity": str(equity),
                         "baseline_id": baseline["id"],
                         "baseline_started_at": baseline_start,
                         "baseline_label": baseline["label"],
                         "return_pct": str(((equity / START_EQUITY - 1) * 100).quantize(QC)),
                         "max_drawdown_pct": round(maxdd, 2),
                         "decisions": n, "curve": curve,
                         # The account can now span venues, so the contract is a
                         # list of what each ALLOWS rather than one hard-coded
                         # claim about Coinbase.
                         "venue_contract": {
                             "venues_version": venues.VENUES_VERSION,
                             "venues": [{"venue": v.key, "kind": v.kind,
                                         "allow_shorts": v.allow_shorts,
                                         "max_leverage": str(v.max_leverage),
                                         "cost_profile": v.cost_profile}
                                        for v in venues.ALL]}}):
            n_new_facts += 1
        con.commit()
        rec.n_new_facts = n_new_facts
        rec.notes = f"baseline={baseline['id']} final_equity={equity}"
        # A merge that resolves silently is the defect this key exists to stop,
        # so say when one happened even though it resolved correctly.
        if n_exit_collisions:
            rec.notes += f" exit_manifest_collisions={n_exit_collisions}"
        return {"final_equity": str(equity), **n}
