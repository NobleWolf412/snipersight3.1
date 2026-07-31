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

VALID_DIRECTIONS = ("LONG", "SHORT")


class IntentRejected(ValueError):
    """An intent that must not be recorded. Raised before anything is written."""


def validate(symbol: str, direction: str, entry: Decimal, tp: Decimal,
             sl: Decimal) -> dict:
    """Reject a plan that cannot be traded, and say which rule refused it.

    These are the checks that are true of the VENUE or of the geometry, not of
    the strategy — this book deliberately has no opinion on whether a trade is
    good. A spot account cannot short (`venues.allow_shorts`), and a stop on the
    wrong side of the entry is not a wide stop, it is a plan whose risk is
    undefined and whose r_multiple would be a negative denominator.
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
    return {"venue": venue.key, "kind": venue.kind,
            "max_leverage": str(venue.max_leverage)}


def risk_per_unit(direction: str, entry: Decimal, sl: Decimal) -> Decimal:
    return (entry - sl) if direction == "LONG" else (sl - entry)


def create_intent(con, symbol: str, tf: str, direction: str, entry, tp, sl,
                  created_at: int, risk_usd=None, size_units=None,
                  note: str = "") -> dict:
    """Record one operator intent. Validated first; nothing is written on reject.

    `created_at` is the causal boundary and is stored as `confirmed_at` — the
    resolver will not fill this on any bar that closed at or before it.
    """
    entry, tp, sl = Decimal(str(entry)), Decimal(str(tp)), Decimal(str(sl))
    meta = validate(symbol, direction, entry, tp, sl)
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
        "venue": meta["venue"], "venue_kind": meta["kind"],
        "max_entry_bars": MAX_ENTRY_BARS,
        "max_holding_bars": MAX_BARS,
        "armed_at": created_at,
        "note": note[:280],
        "cost_manifest_hash": costs.record(con, profile),
    }
    written = store.insert_fact(
        con, symbol=symbol, tf=tf, kind=INTENT_KIND, market_time=created_at,
        confirmed_at=created_at, algo_version=MANUAL_VERSION, payload=payload)
    con.commit()
    return {"intent_id": intent_id, "written": bool(written), **payload}


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

        counts = {"TP": 0, "SL": 0, "TIMEOUT": 0, "OPEN": 0, "MISSED": 0}
        n_out = 0
        for iid, s in intents.items():
            if iid in done:
                continue
            direction = s["direction"]
            long = direction == "LONG"
            entry = Decimal(s["entry"])
            tp, sl = Decimal(s["tp"]), Decimal(s["sl"])
            risk = risk_per_unit(direction, entry, sl)
            if risk <= 0:                     # validated at creation; belt and braces
                continue

            order_i = _first_eligible_bar(candle_times, tf_seconds, s["armed_at"])
            if order_i >= len(candles):
                counts["OPEN"] += 1           # armed, no bar has closed since
                continue

            # --- entry: a resting limit at the operator's own price ---
            fill_i = None
            for k in range(order_i, min(order_i + MAX_ENTRY_BARS, len(candles))):
                lo, hi = Decimal(candles[k]["low"]), Decimal(candles[k]["high"])
                if lo <= entry <= hi:
                    fill_i = k
                    break
            if fill_i is None:
                if order_i + MAX_ENTRY_BARS > len(candles):
                    counts["OPEN"] += 1       # window still open, not yet missed
                    continue
                miss_ts = (candles[order_i + MAX_ENTRY_BARS - 1]["open_ts"]
                           + tf_seconds)
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

            # --- exit: same walk execsim performs, same STOP_FIRST rule ---
            i = fill_i
            outcome = exit_price = exit_ts = None
            ambiguous = False
            j = i
            for j in range(i, min(i + MAX_BARS, len(candles))):
                c = candles[j]
                hi, lo = Decimal(c["high"]), Decimal(c["low"])
                hit_sl = lo <= sl if long else hi >= sl
                hit_tp = hi >= tp if long else lo <= tp
                if hit_sl or hit_tp:
                    ambiguous = hit_sl and hit_tp
                    outcome = "SL" if hit_sl else "TP"
                    exit_price = sl if hit_sl else tp
                    exit_ts = c["open_ts"] + tf_seconds
                    break
            else:
                if i + MAX_BARS <= len(candles):
                    j = i + MAX_BARS - 1
                    outcome = "TIMEOUT"
                    exit_price = Decimal(candles[j]["close"])
                    exit_ts = candles[j]["open_ts"] + tf_seconds
            if outcome is None:
                counts["OPEN"] += 1
                continue

            slip = Decimal(0)
            if outcome in ("SL", "TIMEOUT") and atr[j] is not None:
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
                             "bars_to_fill": i - order_i,
                             "fill_ts": candles[i]["open_ts"] + tf_seconds,
                             "ambiguous_bar": ambiguous,
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
    wins = [r for r in rows if r["outcome"] == "TP"]
    settled = [r for r in rows if r["outcome"] in ("TP", "SL", "TIMEOUT")]
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
