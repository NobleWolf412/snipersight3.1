"""Manual (operator) paper book — trades the operator arms by hand.

algo manual-v0.1-draft.

WHY THIS IS A SEPARATE BOOK, which is the whole design and not a filing
preference. The forward paper record on `setup-*`/`exec-*` is the evidence that
decides whether live execution is ever unlocked, and `edgestats`/`factorstats`
grade it. A discretionary trade in that record does not merely add a row — it
changes what the record MEANS, from "what the strategy did" to "what the
strategy did, plus what the operator felt like on the day". The order ticket
already says so in its own copy when it seeds levels by hand:

    "They are yours, not the engine's, and nothing you do here counts toward
     the strategy record."

This module is what makes that sentence true rather than aspirational.

The separation is STRUCTURAL, not a filter anyone has to remember. Facts here
carry `manual-v0.1-draft`, which is not a SETUP_VERSION and never will be, and
every strategy consumer queries by those version constants. So manual trades
cannot leak into the graded book by construction; there is no join that would
reach them and no flag anyone can forget to set. That is the same mechanism
`store.insert_fact` already relies on to keep two engine generations apart.

FILL MODEL — deliberately identical to `execsim`, imported rather than restated:
BAR_TOUCH_FULL_FILL, and a bar that reaches both stop and target counts as the
STOP. Two paper books that resolved the same bar differently would be two
answers to one question, and the honest comparison an operator wants ("did my
judgement beat the engine?") requires that only the PLAN differs between them.

CAUSALITY (§5), and this is the one that would otherwise make the whole book a
fiction. An intent is created at a wall-clock moment. It may only fill on a bar
that CLOSED AFTER that moment. Without that rule, arming a trade would
immediately resolve it against bars that had already printed — the operator
would be placing orders in the past and the book would show a skill that is
purely retrospective. `_first_eligible_bar` enforces it, and it is the property
`test_manual.py` spends the most assertions on.

WHAT THIS IS NOT: a live order router. No order-placement code exists anywhere
in this system (`execsim` line 3: "No live orders exist anywhere"), and this
module adds none. It simulates. `live_enabled` in `/api/trade-config` stays
false and is not reachable from here.
"""
import json
from bisect import bisect_left
from decimal import Decimal

from . import costs, store, venues
from .swings import compute_atr
from .runlog import RunRecorder
# Imported, never restated. If the house fill model changes, this book changes
# with it — that is the point of the two books differing only in the plan.
from .execsim import MAX_BARS, MAX_ENTRY_BARS, FUNDING_RATE_PER_SETTLEMENT

MANUAL_VERSION = "manual-v0.1-draft"
Q2 = Decimal("0.01")

#: Kinds. Kept distinct from `setup`/`order`/`exec` so that even a query which
#: forgets to filter on algo_version cannot pick these up by accident.
INTENT_KIND = "manual_intent"
EXEC_KIND = "manual_exec"
#: An operator closing an ENGINE position early. Its own kind, under the
#: manual version, for a reason worth stating: the engine's book is a
#: deterministic replay, not a stateful holding. `execsim` re-derives every
#: setup from the candles on every run and does not skip ones already
#: resolved, so an override written under EXEC_VERSION would (a) enter the
#: graded record that decides whether live execution unlocks, and (b) collide
#: with the simulator's own terminal fact for the same setup_id — the S37
#: two-generations-under-one-label defect in a new costume.
#:
#: So the override never touches the strategy record. The simulation carries
#: on and still records what holding to SL/TP would have produced, which is
#: the whole point: the pair of outcomes MEASURES whether the operator's early
#: exit beat the rule. That is the open question the rejected managed-exit
#: experiment (S44) left behind, and this answers it with real decisions.
OVERRIDE_KIND = "manual_override"

VALID_DIRECTIONS = ("LONG", "SHORT")


class IntentRejected(ValueError):
    """An intent that must not be recorded. Raised before anything is written."""


def validate(symbol: str, direction: str, entry: Decimal, tp: Decimal,
             sl: Decimal, leverage: Decimal = Decimal(1)) -> dict:
    """Reject a plan that cannot be traded, and say which rule refused it.

    These are the checks that are true of the VENUE or of the geometry, not of
    the strategy — this book deliberately has no opinion on whether a trade is
    good. A spot account cannot short (`venues.allow_shorts`), and a stop on the
    wrong side of the entry is not a wide stop, it is a plan whose risk is
    undefined and whose r_multiple would be a negative denominator.

    The liquidation gate is checked HERE as well as in the ticket, and that
    duplication is deliberate. The ticket refuses to arm an unsafe plan, but the
    ticket is a client; an endpoint that trusts its own UI to have validated the
    request is an endpoint with no validation. `risk.py` applies the same gate to
    the strategy book (`stop_survives_liquidation`), so both books refuse the
    same geometry for the same reason.
    """
    if direction not in VALID_DIRECTIONS:
        raise IntentRejected(f"direction must be one of {VALID_DIRECTIONS}")
    venue = venues.venue_for(symbol)
    if direction == "SHORT" and not venue.allow_shorts:
        raise IntentRejected(
            f"{venue.key} is {venue.kind} and cannot short — a spot account "
            f"cannot sell what it does not hold")
    for name, v in (("entry", entry), ("take profit", tp), ("stop loss", sl)):
        if v is None or v <= 0:
            raise IntentRejected(f"{name} must be a positive price")
    if direction == "LONG":
        if sl >= entry:
            raise IntentRejected("a LONG stop must sit BELOW the entry")
        if tp <= entry:
            raise IntentRejected("a LONG target must sit ABOVE the entry")
    else:
        if sl <= entry:
            raise IntentRejected("a SHORT stop must sit ABOVE the entry")
        if tp >= entry:
            raise IntentRejected("a SHORT target must sit BELOW the entry")
    if leverage < 1:
        raise IntentRejected("leverage cannot be below 1x")
    if leverage > venue.max_leverage:
        raise IntentRejected(
            f"{venue.key} allows at most {venue.max_leverage}x, asked {leverage}x")
    ok, liq = venues.stop_survives_liquidation(entry, sl, leverage, direction)
    if not ok:
        raise IntentRejected(
            f"at {leverage}x this liquidates at {liq}, before the stop at {sl} — "
            f"the exchange would close it at a loss larger than the one risked, "
            f"so the stop and every R figure built on it would be fiction")
    return {"venue": venue.key, "kind": venue.kind,
            "max_leverage": str(venue.max_leverage),
            "liquidation": None if liq is None else str(liq)}


def validate_position(symbol: str, direction: str, entry: Decimal,
                      tp: Decimal, sl: Decimal) -> None:
    """Geometry rules for a trade ALREADY OPEN — deliberately not `validate`.

    `validate` refuses a stop on the profit side of the entry, and for a NEW
    trade that is right: you cannot enter with a stop already in profit, and
    the R denominator would be negative. Applied to an OPEN position it is
    exactly backwards. A short entered at 4.379 and now trading at 4.05 has a
    stop at 4.30 that guarantees a win — locking in profit is the defining act
    of trade management, and the first version of adoption refused it with
    "a SHORT stop must sit ABOVE the entry", advice meant for a trade that has
    not happened yet.

    R does not move when the stop does. It is fixed by the risk actually taken
    at entry, so a profit-side stop simply means every outcome is positive.
    What still has to hold is direction: the target stays on the profit side,
    or the trade has no thesis left.
    """
    for name, v in (("entry", entry), ("take profit", tp), ("stop loss", sl)):
        if v is None or v <= 0:
            raise IntentRejected(f"{name} must be a positive price")
    if direction == "LONG" and tp <= entry:
        raise IntentRejected("a LONG target must sit ABOVE the entry")
    if direction == "SHORT" and tp >= entry:
        raise IntentRejected("a SHORT target must sit BELOW the entry")
    if direction == "LONG" and sl >= tp:
        raise IntentRejected("the stop cannot sit at or beyond the target")
    if direction == "SHORT" and sl <= tp:
        raise IntentRejected("the stop cannot sit at or beyond the target")


def risk_per_unit(direction: str, entry: Decimal, sl: Decimal) -> Decimal:
    return (entry - sl) if direction == "LONG" else (sl - entry)


def _same_side_open(con, symbol: str, tf: str, direction: str):
    """An unresolved intent on the same market and side, or None.

    ONE ARM PER SIDE PER CHART. Nothing stopped a second identical order: the
    ticket stayed on "New trade" with Arm live after an order was already
    resting, so a double-click — or simply not noticing the first one — armed
    the same trade twice. Both would fill on the same touch and the book would
    carry double the risk the budget was told about.

    Deliberately keyed on DIRECTION, not on the prices: two shorts at different
    entries is the same mistake wearing a different number, and a rule that
    only caught byte-identical levels would miss every case that matters. The
    opposite side is left alone — that is a hedge, a different argument, and
    refusing it here would be this function inventing a position policy.

    Server-side because it is the authority. The ticket disables Arm for the
    same reason it shows the stop: so the operator is not offered an action
    that will be refused. That is courtesy; THIS is the guard.
    """
    for p in unresolved(con).get((symbol, tf), []):
        if str(p.get("direction", "")).upper() == str(direction).upper():
            return p
    return None


def create_intent(con, symbol: str, tf: str, direction: str, entry, tp, sl,
                  created_at: int, risk_usd=None, size_units=None,
                  note: str = "", leverage=1, trail_r=None) -> dict:
    """Record one operator intent. Validated first; nothing is written on reject.

    `created_at` is the causal boundary and is stored as `confirmed_at` — the
    resolver will not fill this on any bar that closed at or before it.

    `leverage` sets the MARGIN posted and nothing else. Size below is derived
    from risk and the stop distance exactly as it would be at 1x — leverage
    never widens a stop, and the resolver never reads it, so a leveraged and an
    unleveraged plan with the same prices resolve to the same r_multiple. What
    it does change is where liquidation sits, which `validate` gates on.

    `trail_r` — the operator's CHOICE, never a default. The stop ratchets to
    trail this many R behind the best price seen since fill, which folds
    breakeven in for free (at +1R of progress a 1.0R trail sits at entry). It
    is recorded on the intent and on the exit, so the book can eventually
    grade trailing against holding — the engine's own managed exits measured
    WORSE than holding (S44), and this feature does not get to skip the same
    exam just because it feels prudent. None means hold to SL/TP, exactly as
    before; this field is ADDITIVE, and every previously-recorded intent
    resolves byte-identically, which is why MANUAL_VERSION does not bump — a
    bump would strand every open v0.1 intent the resolver queries by version.
    """
    entry, tp, sl = Decimal(str(entry)), Decimal(str(tp)), Decimal(str(sl))
    leverage = Decimal(str(leverage or 1))
    if trail_r is not None:
        trail_r = Decimal(str(trail_r))
        # A zero or negative trail is not a tight trail, it is a stop placed at
        # or beyond the best price itself — the first bar of noise closes it.
        if trail_r < Decimal("0.1"):
            raise IntentRejected(
                f"trail distance must be at least 0.1R, got {trail_r} — a "
                f"tighter trail than that is stopped by the same bar that "
                f"moves it")
    dup = _same_side_open(con, symbol, tf, direction)
    if dup is not None:
        raise IntentRejected(
            f"you already have an unresolved {direction} on {symbol} {tf} — "
            f"entry {dup['entry']}, stop {dup['sl']}. Arming again would open a "
            f"second position on the same side, doubling the risk the budget "
            f"thinks you took. Let it resolve, or close it first.")
    meta = validate(symbol, direction, entry, tp, sl, leverage)
    per_unit = risk_per_unit(direction, entry, sl)
    if size_units is None and risk_usd is not None:
        size_units = (Decimal(str(risk_usd)) / per_unit) if per_unit > 0 else Decimal(0)
    profile = costs.profile_for(symbol)
    intent_id = f"{symbol}|{tf}|MANUAL|{created_at}"
    payload = {
        "intent_id": intent_id,
        # Marks provenance on the fact itself, so a row read in isolation still
        # says who authored the plan. The version already guarantees isolation;
        # this makes it legible.
        "source": "OPERATOR",
        "state": "ARMED",
        "direction": direction,
        "entry": str(entry), "tp": str(tp), "sl": str(sl),
        "risk_per_unit": str(per_unit),
        "risk_usd": None if risk_usd is None else str(risk_usd),
        "size_units": None if size_units is None else str(size_units),
        # Financing, recorded so the trade can be reproduced. `margin_usd` is
        # notional / leverage; it is what the position COST to hold, which the
        # r_multiple deliberately does not reflect.
        "leverage": str(leverage),
        "liquidation": meta["liquidation"],
        "margin_usd": (None if size_units is None
                       else str((Decimal(str(size_units)) * entry) / leverage)),
        "venue": meta["venue"], "venue_kind": meta["kind"],
        "max_entry_bars": MAX_ENTRY_BARS,
        "max_holding_bars": MAX_BARS,
        "trail_r": None if trail_r is None else str(trail_r),
        "armed_at": created_at,
        "note": note[:280],
        "cost_manifest_hash": costs.record(con, profile),
    }
    written = store.insert_fact(
        con, symbol=symbol, tf=tf, kind=INTENT_KIND, market_time=created_at,
        confirmed_at=created_at, algo_version=MANUAL_VERSION, payload=payload)
    con.commit()
    return {"intent_id": intent_id, "written": bool(written), **payload}


def overridden_setups(con) -> dict:
    """setup_id -> the operator's early close, for the portfolio view."""
    import sqlite3
    con.row_factory = sqlite3.Row
    out = {}
    for r in con.execute(
            "SELECT confirmed_at, payload FROM facts WHERE kind=? AND algo_version=?",
            (OVERRIDE_KIND, MANUAL_VERSION)):
        p = json.loads(r["payload"])
        out[p["setup_id"]] = {**p, "closed_at": r["confirmed_at"]}
    return out


def adopt_position(con, setup_id: str, symbol: str, tf: str, direction: str,
                   entry, sl, tp, fill_ts: int, adopted_at: int,
                   risk_usd=None, trail_r=None, note: str = "",
                   original_sl=None) -> dict:
    """Take custody of an engine position with the operator's own levels.

    The engine entered this trade; the operator is changing where it ends. Two
    facts are written and the strategy record is touched by neither:

      · an OVERRIDE marking the engine position adopted, so the cockpit stops
        reporting it as engine exposure the operator no longer governs;
      · an INTENT carrying the ORIGINAL fill price as entry and the operator's
        new stop and target, flagged `adopted_fill_ts` so the resolver knows
        the entry already happened and must not hunt for one.

    From here it is an ordinary manual trade: it settles on the operator's
    book, it can trail, and the engine's simulation keeps running its own
    plan. That pairing is the point — the operator's exit and the rule's exit
    both get recorded, so which one was better stops being a matter of opinion.
    """
    entry = Decimal(str(entry))
    sl, tp = Decimal(str(sl)), Decimal(str(tp))
    validate_position(symbol, direction, entry, tp, sl)
    if trail_r is not None:
        trail_r = Decimal(str(trail_r))
        if trail_r < Decimal("0.1"):
            raise IntentRejected("trail distance must be at least 0.1R")
    # R is the risk actually TAKEN, measured to the stop this trade was entered
    # with — not to wherever the operator has since moved it. Recomputing it
    # from a profit-side stop would give a negative denominator and invert
    # every subsequent number.
    ref_sl = Decimal(str(original_sl if original_sl is not None else sl))
    per_unit = risk_per_unit(direction, entry, ref_sl)
    if per_unit <= 0:
        raise IntentRejected("this position has no measurable risk to price R against")
    size_units = ((Decimal(str(risk_usd)) / per_unit)
                  if risk_usd is not None else None)
    intent_id = f"{symbol}|{tf}|ADOPTED|{adopted_at}"
    payload = {
        "intent_id": intent_id, "source": "OPERATOR", "state": "ADOPTED",
        "direction": direction,
        "entry": str(entry), "tp": str(tp), "sl": str(sl),
        "risk_per_unit": str(per_unit),
        # The stop R is measured against, kept so the denominator survives the
        # operator moving the live stop anywhere they like.
        "risk_ref_sl": str(ref_sl),
        "risk_usd": None if risk_usd is None else str(risk_usd),
        "size_units": None if size_units is None else str(size_units),
        "trail_r": None if trail_r is None else str(trail_r),
        "armed_at": adopted_at,
        # The entry already happened. This is what tells the resolver to hold
        # rather than hunt for a fill it would never find.
        "adopted_fill_ts": fill_ts,
        "adopted_from": setup_id,
        "note": note[:280],
        "cost_manifest_hash": costs.record(con, costs.profile_for(symbol)),
    }
    store.insert_fact(con, symbol=symbol, tf=tf, kind=INTENT_KIND,
                      market_time=adopted_at, confirmed_at=adopted_at,
                      algo_version=MANUAL_VERSION, payload=payload)
    store.insert_fact(
        con, symbol=symbol, tf=tf, kind=OVERRIDE_KIND,
        market_time=adopted_at, confirmed_at=adopted_at,
        algo_version=MANUAL_VERSION,
        payload={"setup_id": setup_id, "source": "OPERATOR",
                 "event": "ADOPTED", "symbol": symbol, "tf": tf,
                 "direction": direction, "entry": str(entry),
                 "new_sl": str(sl), "new_tp": str(tp),
                 "intent_id": intent_id,
                 "not_the_strategy_record": True})
    con.commit()
    return {"intent_id": intent_id, **payload}


def close_engine_position(con, setup_id: str, symbol: str, tf: str,
                          direction: str, entry, sl, risk_usd=None,
                          note: str = "") -> dict:
    """Record an operator closing an engine position early, at the last close.

    Priced at the last CLOSED bar, like every other number on the screen — a
    live tick here would make the one number the operator acted on fresher
    than the chart it was read from.

    Writes ONE fact and changes nothing else. The engine's simulation of this
    setup continues untouched, so the strategy record still gets the outcome
    holding would have produced.
    """
    entry, sl = Decimal(str(entry)), Decimal(str(sl))
    long = direction == "LONG"
    risk = risk_per_unit(direction, entry, sl)
    if risk <= 0:
        raise IntentRejected("this position has no measurable risk to close against")
    candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
    if not candles:
        raise IntentRejected(f"no candles for {symbol} {tf} — nothing to price against")
    last = candles[-1]
    px = Decimal(last["close"])
    closed_at = last["open_ts"] + _tf_seconds_of(tf)
    profile = costs.profile_for(symbol)
    # A discretionary close is a MARKET order — the operator wants out now and
    # crosses the spread for it — so it pays exactly what execsim charges its
    # own market exits: taker fee AND slippage. Charging the fee alone (the
    # first cut of this function) priced operator exits better than engine
    # stops, which would have biased the one comparison this feature exists
    # for, in the operator's favour, invisibly.
    #
    # A LIMIT close is a different thing and already has a home: resting an
    # order at a price and waiting for it is what moving the take-profit is.
    slip = Decimal(0)
    atr_series = compute_atr(candles)
    if atr_series and atr_series[-1] is not None:
        slip = profile.market_slippage_atr * atr_series[-1]
    else:
        # loud-fallback rule: a degraded price must be audible, never silent
        from .runlog import get_logger
        get_logger().warning(
            f"operator close {symbol} {tf}: no ATR at the exit bar — slippage "
            f"NOT modelled, so this close is priced slightly flatteringly")
    eff_exit = (px - slip) if long else (px + slip)
    gross = (eff_exit - entry) if long else (entry - eff_exit)
    r_mult = (gross / risk).quantize(Q2)
    fees = profile.taker_rate * eff_exit
    payload = {
        "setup_id": setup_id, "source": "OPERATOR", "event": "CLOSED_EARLY",
        "symbol": symbol, "tf": tf, "direction": direction,
        "entry": str(entry), "sl": str(sl),
        "exit_price": str(px), "priced_at": "last closed bar",
        "effective_exit_price": str(eff_exit),
        "slippage_price_units": str(slip),
        "order_type": "MARKET",
        "r_at_close": str(r_mult),
        "usd_at_close": (None if risk_usd is None
                         else str((r_mult * Decimal(str(risk_usd))).quantize(Q2))),
        "fees_price_units": str(fees),
        "risk_usd": None if risk_usd is None else str(risk_usd),
        "note": note[:280],
        # Stated on the fact itself so a row read in isolation cannot be
        # mistaken for the strategy's own result.
        "not_the_strategy_record": True,
    }
    written = store.insert_fact(
        con, symbol=symbol, tf=tf, kind=OVERRIDE_KIND, market_time=last["open_ts"],
        confirmed_at=closed_at, algo_version=MANUAL_VERSION, payload=payload)
    con.commit()
    return {"written": bool(written), **payload}


def _tf_seconds_of(tf: str) -> int:
    from .importer import TF_SECONDS
    return TF_SECONDS[tf]


def unresolved(con) -> dict:
    """Every armed intent with no terminal fact, grouped by (symbol, tf).

    This is the resolver's WORK LIST, and it exists because the live loop runs
    engines over the scan universe only. An intent armed on any of the ~58
    chartable-but-unscanned symbols got exactly one resolution attempt — at arm
    time — and then sat ARMED forever: the trade the operator placed could
    never report a result. `live.cycle` now asks this function where manual
    work exists instead of assuming it lives inside the watchlist.
    """
    import sqlite3
    con.row_factory = sqlite3.Row
    intents: dict = {}
    for r in con.execute(
            "SELECT symbol, tf, payload FROM facts WHERE kind=? AND algo_version=?",
            (INTENT_KIND, MANUAL_VERSION)):
        p = json.loads(r["payload"])
        intents[p["intent_id"]] = (r["symbol"], r["tf"], p)
    done = {json.loads(r[0])["intent_id"] for r in con.execute(
        "SELECT payload FROM facts WHERE kind=? AND algo_version=?",
        (EXEC_KIND, MANUAL_VERSION))}
    out: dict = {}
    for iid, (sym, tf, p) in intents.items():
        if iid not in done:
            out.setdefault((sym, tf), []).append(p)
    return out


def cancel_intent(con, intent_id: str, at: int | None = None) -> dict:
    """Withdraw an armed intent that has not filled.

    Recorded as a terminal fact, never a delete: this store is append-only and
    an intent that vanished would leave the operator unable to answer "what
    happened to that order?". CANCELLED carries r_multiple 0 and is excluded
    from `n`/`wins`/`win_rate` for the same reason MISSED is — declining to
    take a trade is not a trade, and letting it count would let anyone improve
    their record by cancelling the ones that look like losers.

    Refuses once the intent has FILLED. A filled position is closed, not
    cancelled, and quietly resolving one at zero R would erase a real result.
    """
    import time
    open_here = unresolved(con)
    for (symbol, tf), plans in open_here.items():
        for p in plans:
            if p["intent_id"] != intent_id:
                continue
            tf_seconds = _tf_seconds_of(tf)
            candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
            if candles:
                w = _walk(p, candles, [c["open_ts"] for c in candles], tf_seconds)
                if w["phase"] == "OPEN":
                    raise IntentRejected(
                        f"{symbol} {tf} has already filled at {p['entry']} — "
                        f"that is an open position, not a resting order. Close "
                        f"it from the chart instead.")
            written = store.insert_fact(
                con, symbol=symbol, tf=tf, kind=EXEC_KIND,
                market_time=p["armed_at"], confirmed_at=int(at or time.time()),
                algo_version=MANUAL_VERSION,
                payload={"intent_id": intent_id, "source": "OPERATOR",
                         "direction": p["direction"], "outcome": "CANCELLED",
                         "entry": str(p["entry"]), "exit_price": None,
                         "r_multiple": "0", "r_gross": "0",
                         "bars_held": 0, "fill_ts": None,
                         "ambiguous_bar": False,
                         "cost_manifest_hash": p.get("cost_manifest_hash")})
            con.commit()
            return {"intent_id": intent_id, "symbol": symbol, "tf": tf,
                    "written": bool(written)}
    raise IntentRejected(
        f"no unresolved intent {intent_id} — it has already settled, or was "
        f"never armed")


def live(con) -> list[dict]:
    """Every open intent across every market, resolved and ready to render.

    `status()` answers for ONE chart because that is all the chart needed. The
    operator's book is not a per-chart thing: three orders armed on three
    markets were invisible on all but the one symbol/timeframe that happened to
    be loaded, and an order that expires while you are looking at another chart
    expires silently. This walks the whole work list.

    Resolves before it reports, exactly as `/api/manual/open` does — an intent
    whose window closed two bars ago must not be described as waiting.
    """
    out = []
    for (symbol, tf) in sorted(unresolved(con)):
        tf_seconds = _tf_seconds_of(tf)
        try:
            run(con, symbol, tf, tf_seconds)
        except Exception:
            # One unreadable market must not blank the whole panel. The rows
            # that CAN be resolved are still worth showing.
            continue
        for row in status(con, symbol, tf, tf_seconds):
            out.append({"symbol": symbol, "tf": tf,
                        "tf_seconds": tf_seconds, **row})
    # Newest first: the order you just placed is the one you are looking for.
    out.sort(key=lambda r: r.get("armed_at") or 0, reverse=True)
    return out


def status(con, symbol: str, tf: str, tf_seconds: int) -> list[dict]:
    """Non-terminal state of each open intent: PENDING, OPEN, or EXPIRING.

    The resolver only writes facts at terminal outcomes, so between arm and
    exit the book says nothing — and the operator watching the chart needs the
    in-between: has it filled, at what price, and what is it worth right now.
    Computed HERE, not in the browser: the fill test is the same bar-touch walk
    `run()` performs, and a JS re-implementation would be a second authority
    that drifts from the one that settles the trade.

    Unrealized R is marked against the LAST CLOSED bar, and says so. A closed
    candle is the only price this system trusts anywhere else; quoting a live
    tick here would make this one number fresher than every other number on
    the screen, which reads as precision and is actually inconsistency.
    """
    open_here = unresolved(con).get((symbol, tf), [])
    if not open_here:
        return []
    candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
    if not candles:
        return []
    candle_times = [c["open_ts"] for c in candles]
    last_close = Decimal(candles[-1]["close"])
    out = []
    for p in open_here:
        direction, long = p["direction"], p["direction"] == "LONG"
        entry, sl = Decimal(p["entry"]), Decimal(p["sl"])
        # Same denominator the settlement uses, for the same reason: a
        # profit-side stop would otherwise flip the sign of the unrealized R
        # shown on the chart while the book settled it correctly.
        risk = _risk_of(p, direction, entry, sl)
        # The SAME walk that settles the trade — see _walk. status() only
        # reports its live phases, so screen and settlement cannot disagree.
        w = _walk(p, candles, candle_times, tf_seconds)
        row = {"intent_id": p["intent_id"], "direction": direction,
               "entry": str(entry), "sl": str(sl), "tp": p["tp"],
               "trail_r": p.get("trail_r"),
               "risk_usd": p.get("risk_usd"), "leverage": p.get("leverage"),
               "liquidation": p.get("liquidation"),
               "last_close": str(last_close), "armed_at": p["armed_at"]}
        if w["phase"] == "PENDING":
            row.update(state="PENDING", bars_left=w["bars_left"])
            out.append(row)
            continue
        if w["phase"] != "OPEN":
            # MISSED and EXIT are run()'s to record; the endpoint resolves
            # before it asks, so by the time we are here they are facts.
            continue
        move = (last_close - entry) if long else (entry - last_close)
        r_unreal = (move / risk).quantize(Q2) if risk > 0 else Decimal(0)
        usd = p.get("risk_usd")
        row.update(state="OPEN",
                   bars_held=len(candles) - 1 - w["fill_i"],
                   fill_price=str(entry),
                   # The stop as it stands NOW, ratchet included — this is the
                   # number the gold SL line must draw. Showing the original
                   # stop on a trailed trade would misstate where it dies.
                   current_stop=str(w["current_stop"]),
                   trailed=w["trailed"],
                   unrealized_r=str(r_unreal),
                   unrealized_usd=(None if usd is None
                                   else str((r_unreal * Decimal(str(usd)))
                                            .quantize(Q2))))
        out.append(row)
    return out


def _risk_of(p: dict, direction: str, entry: Decimal, sl: Decimal) -> Decimal:
    """R's denominator: the risk taken at entry, never the current stop.

    Stored on every intent at creation, so this is identical to
    `risk_per_unit(entry, sl)` for an ordinary trade and stays correct for an
    adopted one whose stop has since been moved into profit.
    """
    stored = p.get("risk_per_unit")
    if stored:
        try:
            v = Decimal(str(stored))
            if v > 0:
                return v
        except Exception:
            pass
    return risk_per_unit(direction, entry, sl)


def _first_eligible_bar(candle_times: list, tf_seconds: int,
                        armed_at: int) -> int:
    """Index of the first bar that OPENS at or after `armed_at`.

    The open, not the close, and the distinction is the whole guarantee. A bar
    still in progress when the operator armed has already printed part of its
    range, and OHLC alone cannot say whether the touch came before or after the
    order existed. Admitting that bar would let a fill land on a price that
    traded BEFORE the plan was made — lookahead of exactly the kind this book
    would otherwise be full of, and invisible in the results because it looks
    like a good entry.

    So the in-progress bar is discarded whole. It costs at most one bar of
    latency and buys a book whose every fill is provably after its own order.
    """
    return bisect_left(candle_times, armed_at)


def _walk(p: dict, candles: list, candle_times: list, tf_seconds: int) -> dict:
    """ONE simulation of an intent against the bars, used by run() AND status().

    This function exists so the trade that settles and the trade on screen are
    the same trade. The fill test, the exit test and the trailing ratchet live
    here once; run() writes facts off the terminal phases and status() reports
    the live ones, and neither can drift from the other because neither owns a
    copy.

    Trailing, at bar granularity, honestly:
      · Exits are tested against the stop AS IT STOOD ENTERING THE BAR. A bar
        that makes a new high and then falls back through the stop that high
        implies cannot exit on that stop THIS bar — OHLC does not reveal
        whether the high or the fall came first, so the ratchet only arms for
        the next bar. Conservative by one bar, never clairvoyant.
      · The stop only ever tightens: max() for longs, min() for shorts. An
        adverse bar moves nothing.
      · Breakeven falls out for free — with a 1.0R trail, +1R of progress puts
        the stop at entry.
    A stop exit fills at the stop and pays taker + slippage, like any stop.

    Phases: PENDING (fill window still open) · MISSED (window closed untouched)
    · OPEN (filled, no exit yet) · EXIT (outcome TP / SL / TRAIL_STOP / TIMEOUT).
    TRAIL_STOP is a distinct outcome, not an SL flavour, so the book can grade
    the trailing rule against holding without parsing free text.
    """
    direction = p["direction"]
    long = direction == "LONG"
    entry, sl, tp = Decimal(p["entry"]), Decimal(p["sl"]), Decimal(p["tp"])
    trail = p.get("trail_r")
    trail = Decimal(str(trail)) if trail else None
    risk = _risk_of(p, direction, entry, sl)
    if risk <= 0:
        return {"phase": "INVALID"}

    # An ADOPTED position is already filled — the operator took custody of a
    # trade the engine had entered — so the entry search is skipped entirely.
    # Hunting for a limit fill would be wrong twice: the fill already happened
    # at a price the engine recorded, and a failed search would mark a live
    # position as never entered.
    if p.get("adopted_fill_ts") is not None:
        fi = bisect_left(candle_times, p["adopted_fill_ts"])
        if fi >= len(candles):
            return {"phase": "PENDING", "bars_left": 0}
        # The operator's levels apply from when they were SET, not from the
        # fill. Testing a stop moved today against bars that closed days ago
        # would stop the trade out retroactively — the position is provably
        # still open, so those bars did not hit anything, and re-judging them
        # against new levels would fabricate an exit that never happened.
        start = max(fi, bisect_left(candle_times, p["armed_at"]))
        if start >= len(candles):
            return {"phase": "OPEN", "fill_i": fi, "order_i": fi,
                    "current_stop": Decimal(p["sl"]), "best": entry,
                    "trailed": False}
        return _exit_walk(p, candles, start, fi, fi)

    order_i = _first_eligible_bar(candle_times, tf_seconds, p["armed_at"])
    if order_i >= len(candles):
        return {"phase": "PENDING", "bars_left": MAX_ENTRY_BARS}
    fill_i = None
    for k in range(order_i, min(order_i + MAX_ENTRY_BARS, len(candles))):
        lo, hi = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
        if lo <= entry <= hi:
            fill_i = k
            break
    if fill_i is None:
        if order_i + MAX_ENTRY_BARS > len(candles):
            return {"phase": "PENDING",
                    "bars_left": order_i + MAX_ENTRY_BARS - len(candles)}
        return {"phase": "MISSED", "miss_i": order_i + MAX_ENTRY_BARS - 1,
                "order_i": order_i}

    return _exit_walk(p, candles, fill_i, fill_i, order_i)


def _exit_walk(p: dict, candles: list, start_i: int, fill_i: int,
               order_i: int) -> dict:
    """The hold: stop, target, trail and timeout, from the fill bar onward.

    Shared by the ordinary path and the adopted one so a position taken over
    from the engine is held to exactly the rules a hand-armed trade is.
    """
    direction = p["direction"]
    long = direction == "LONG"
    entry, sl, tp = Decimal(p["entry"]), Decimal(p["sl"]), Decimal(p["tp"])
    trail = p.get("trail_r")
    trail = Decimal(str(trail)) if trail else None
    risk = _risk_of(p, direction, entry, sl)
    stop, best, trailed = sl, entry, False
    for j in range(start_i, min(fill_i + MAX_BARS, len(candles))):
        hi, lo = Decimal(candles[j]["high"]), Decimal(candles[j]["low"])
        hit_stop = lo <= stop if long else hi >= stop
        hit_tp = hi >= tp if long else lo <= tp
        if hit_stop:                          # stop wins ties, house rule
            return {"phase": "EXIT",
                    "outcome": "TRAIL_STOP" if trailed else "SL",
                    "exit_price": stop, "exit_i": j, "fill_i": fill_i,
                    "order_i": order_i,
                    "ambiguous": hit_stop and hit_tp, "final_stop": stop}
        if hit_tp:
            return {"phase": "EXIT", "outcome": "TP", "exit_price": tp,
                    "exit_i": j, "fill_i": fill_i, "order_i": order_i,
                    "ambiguous": False, "final_stop": stop}
        if trail is not None:
            best = max(best, hi) if long else min(best, lo)
            cand = (best - trail * risk) if long else (best + trail * risk)
            if (cand > stop) if long else (cand < stop):
                stop, trailed = cand, True
    if fill_i + MAX_BARS <= len(candles):
        j = fill_i + MAX_BARS - 1
        return {"phase": "EXIT", "outcome": "TIMEOUT",
                "exit_price": Decimal(candles[j]["close"]), "exit_i": j,
                "fill_i": fill_i, "order_i": order_i,
                "ambiguous": False, "final_stop": stop}
    return {"phase": "OPEN", "fill_i": fill_i, "order_i": order_i,
            "current_stop": stop, "best": best, "trailed": trailed}


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    """Resolve every unresolved manual intent for this symbol/tf.

    Append-only and idempotent: an intent that cannot resolve yet simply emits
    nothing and is retried on the next pass, exactly as `execsim` treats OPEN.
    """
    with RunRecorder(con, "manual", MANUAL_VERSION, symbol, tf) as rec:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        candle_times = [c["open_ts"] for c in candles]
        atr = compute_atr(candles)
        profile = costs.profile_for(symbol)
        cost_manifest_hash = costs.record(con, profile)

        intents = {}
        for r in store.get_facts(con, symbol, tf, INTENT_KIND, MANUAL_VERSION):
            p = json.loads(r["payload"])
            intents[p["intent_id"]] = {**p, "confirmed_at": r["confirmed_at"],
                                       "market_time": r["market_time"]}
        # Already-resolved intents are skipped rather than re-emitted. The
        # content hash would dedupe a byte-identical repeat anyway, but a
        # re-run after more candles arrive could otherwise resolve the SAME
        # intent a second way (OPEN -> TP) and write both.
        done = set()
        for r in store.get_facts(con, symbol, tf, EXEC_KIND, MANUAL_VERSION):
            done.add(json.loads(r["payload"])["intent_id"])
        rec.n_inputs = len(intents)

        counts = {"TP": 0, "SL": 0, "TRAIL_STOP": 0, "TIMEOUT": 0,
                  "OPEN": 0, "MISSED": 0}
        n_out = 0
        for iid, s in intents.items():
            if iid in done:
                continue
            direction = s["direction"]
            long = direction == "LONG"
            entry = Decimal(s["entry"])
            # The denominator is the risk TAKEN, not the distance to wherever
            # the stop now sits. Deriving it from a profit-side stop gives a
            # negative risk and inverts the sign of the whole trade — a
            # locked-in winner settled as r_gross -1.00.
            risk = _risk_of(s, direction, entry, Decimal(s["sl"]))

            # ONE walk settles and displays — see _walk. run() only turns its
            # terminal phases into facts.
            w = _walk(s, candles, candle_times, tf_seconds)
            if w["phase"] in ("PENDING", "INVALID"):
                if w["phase"] == "PENDING":
                    counts["OPEN"] += 1
                continue
            if w["phase"] == "OPEN":
                counts["OPEN"] += 1
                continue
            if w["phase"] == "MISSED":
                miss_ts = candles[w["miss_i"]]["open_ts"] + tf_seconds
                if store.insert_fact(
                        con, symbol=symbol, tf=tf, kind=EXEC_KIND,
                        market_time=s["market_time"], confirmed_at=miss_ts,
                        algo_version=MANUAL_VERSION,
                        payload={"intent_id": iid, "source": "OPERATOR",
                                 "direction": direction, "outcome": "MISSED",
                                 "entry": str(entry), "exit_price": None,
                                 "r_multiple": "0", "r_gross": "0",
                                 "bars_held": 0, "fill_ts": None,
                                 "ambiguous_bar": False,
                                 "cost_manifest_hash": cost_manifest_hash}):
                    n_out += 1
                counts["MISSED"] += 1
                continue

            i, j = w["fill_i"], w["exit_i"]
            outcome, exit_price = w["outcome"], w["exit_price"]
            ambiguous = w["ambiguous"]
            exit_ts = candles[j]["open_ts"] + tf_seconds

            slip = Decimal(0)
            # Every stop is a market order when it fires — the initial one and
            # the trailed one alike — so both pay taker and slippage below.
            if outcome in ("SL", "TRAIL_STOP", "TIMEOUT") and atr[j] is not None:
                slip = profile.market_slippage_atr * atr[j]
            holding_hours = Decimal((j - i) * tf_seconds) / Decimal(3600)
            funding_cost = venues.funding_cost_rate(
                symbol, FUNDING_RATE_PER_SETTLEMENT, holding_hours) * entry
            eff_exit = (exit_price - slip) if long else (exit_price + slip)
            # The operator's entry is a resting limit they chose, so it earns
            # maker. The exit follows execsim: a target is passive, a stop is a
            # market order and pays taker plus slippage.
            exit_rate = profile.maker_rate if outcome == "TP" else profile.taker_rate
            fees = profile.maker_rate * entry + exit_rate * eff_exit
            gross = (exit_price - entry) if long else (entry - exit_price)
            net = (((eff_exit - entry) if long else (entry - eff_exit))
                   - fees - funding_cost)
            counts[outcome] += 1
            if store.insert_fact(
                    con, symbol=symbol, tf=tf, kind=EXEC_KIND,
                    market_time=s["market_time"], confirmed_at=exit_ts,
                    algo_version=MANUAL_VERSION,
                    payload={"intent_id": iid, "source": "OPERATOR",
                             "direction": direction, "outcome": outcome,
                             "entry": str(entry), "exit_price": str(exit_price),
                             "effective_exit_price": str(eff_exit),
                             "r_multiple": str((net / risk).quantize(Q2)),
                             "r_gross": str((gross / risk).quantize(Q2)),
                             "fees_price_units": str(fees),
                             "funding_price_units": str(funding_cost),
                             "slippage_price_units": str(slip),
                             "bars_held": j - i,
                             "bars_to_fill": i - w["order_i"],
                             "fill_ts": candles[i]["open_ts"] + tf_seconds,
                             "ambiguous_bar": ambiguous,
                             # Which exit RULE settled this — recorded so the
                             # book can grade trailing against holding, which
                             # is the only way this feature earns permanence.
                             "exit_rule": ("TRAIL" if s.get("trail_r")
                                           else "HOLD"),
                             "trail_r": s.get("trail_r"),
                             "final_stop": str(w["final_stop"]),
                             "size_units": s.get("size_units"),
                             "risk_usd": s.get("risk_usd"),
                             "venue": s.get("venue"),
                             "cost_manifest_hash": cost_manifest_hash}):
                n_out += 1

        con.commit()
        rec.n_new_facts = n_out
        rec.notes = " ".join(f"{k}={v}" for k, v in counts.items() if v)
        return {"symbol": symbol, "tf": tf, **counts}


def book(con, limit: int = 200) -> dict:
    """The manual record: intents, resolutions, and a cumulative R curve.

    Reads ONLY manual facts. It cannot accidentally report a strategy trade,
    because it never queries a strategy version.
    """
    import sqlite3
    con.row_factory = sqlite3.Row      # `get_facts` sets this too; do not rely on it
    rows = []
    for r in con.execute(
            "SELECT symbol, tf, market_time, confirmed_at, payload FROM facts "
            "WHERE kind=? AND algo_version=? ORDER BY confirmed_at",
            (EXEC_KIND, MANUAL_VERSION)):
        p = json.loads(r["payload"])
        rows.append({"symbol": r["symbol"], "tf": r["tf"],
                     "resolved_at": r["confirmed_at"], **p})
    curve, cum = [], Decimal(0)
    for row in rows:
        cum += Decimal(row.get("r_multiple") or 0)
        curve.append({"ts": row["resolved_at"], "r": str(cum)})
    open_intents = []
    resolved = {row["intent_id"] for row in rows}
    for r in con.execute(
            "SELECT symbol, tf, confirmed_at, payload FROM facts "
            "WHERE kind=? AND algo_version=? ORDER BY confirmed_at DESC",
            (INTENT_KIND, MANUAL_VERSION)):
        p = json.loads(r["payload"])
        if p["intent_id"] not in resolved:
            open_intents.append({"symbol": r["symbol"], "tf": r["tf"], **p})
    settled = [r for r in rows
               if r["outcome"] in ("TP", "SL", "TRAIL_STOP", "TIMEOUT")]
    # A win is a settled trade that MADE money, not one that exited at the
    # target. A trailed stop at +1.4R is a win in anyone's language, and
    # outcome==TP was already wrong for a profitable TIMEOUT. Counted on net R,
    # the same number the expectancy uses.
    wins = [r for r in settled if Decimal(r.get("r_multiple") or 0) > 0]
    return {
        "version": MANUAL_VERSION,
        "trades": rows[-limit:],
        "open_intents": open_intents[:limit],
        "curve": curve[-limit:],
        "n": len(settled),
        "wins": len(wins),
        "win_rate": round(len(wins) / len(settled) * 100, 1) if settled else None,
        "total_r": str(cum.quantize(Q2)),
        "expectancy_r": str((cum / len(settled)).quantize(Q2)) if settled else None,
    }
