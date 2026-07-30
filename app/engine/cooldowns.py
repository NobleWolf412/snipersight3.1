"""Re-entry control — how long a symbol+direction is locked out after an exit.

Nothing in this system currently prevents re-entering a level that has just
stopped you out. That was tolerable while REVERSAL fired five times in four
years; it stopped being tolerable at S38, when the reworked TRANSITION gate took
it to 471 setups. A zone that breaks does not become untouchable — price sits
right against it and the next bar can produce another touch, another
confirmation, and another trade into the level that just proved it would not
hold.

The durations are DELIBERATELY ASYMMETRIC, and that asymmetry is the whole idea
(ported in shape from the prior project's cooldown manager, SALVAGE §2.2):

  · **Stop-out -> long lockout.** The level was INVALIDATED. Re-entering is
    re-buying a thesis the market has just refuted.
  · **Target / trail / time exit -> short lockout.** The level was not
    invalidated, it merely RESOLVED. Locking it out for a day would discard the
    setups that follow a level doing exactly what it was supposed to do.

Most bots get this backwards, or use one number for both, which necessarily gets
one of the two cases wrong.

Scope: per (symbol, direction). Not per zone — a stopped-out demand zone usually
sits inside a cluster, and re-entering the neighbour thirty seconds later is the
same trade wearing a different `zone_id`. Not per symbol alone either: being
stopped out of a long says nothing about a short.

Cooldowns are FACTS, not hidden state. A rejection has to be as auditable as an
approval, so the lockout that caused it is queryable, versioned and replayable.
Nothing here reads the clock: every decision is made against an `as_of` the
caller supplies, so a replay reaches the same verdict as the live pass did.
"""
from . import store
from .runlog import RunRecorder

COOLDOWN_VERSION = "cooldown-v0.5-draft"
# v0.5: cascade from exec-v0.17. Cooldowns are derived purely from recorded
# exits, so a new exec generation produces a new cooldown series.
# v0.2: cascade from exec-v0.14. Cooldowns are derived purely from recorded
# exits, so a corrected fill price moves the exits they are derived from.

HOUR = 3600

# Hours locked out after a stop-out. The level was proven wrong; give the market
# time to build a different one. Scaled by horizon so a 15m scalp is not silenced
# for a day over a stop that a scalper expects several of.
STOP_OUT_HOURS = {"scalp": 4.0, "intraday": 12.0, "swing": 24.0}

# Hours locked out after the trade RESOLVED — target, trail or time stop. Short
# on purpose: nothing was invalidated. Long enough only to stop the same bar
# producing a second identical entry.
RESOLVED_HOURS = {"scalp": 0.25, "intraday": 0.5, "swing": 1.0}

# Which timeframes count as which horizon. A horizon is a hold-time policy, not
# a timeframe — but the timeframe is what the setup carries, so this is the map.
HORIZON_BY_TF = {"15m": "scalp", "1H": "intraday", "4H": "intraday",
                 "1D": "swing", "1W": "swing"}

# Outcomes that mean the level FAILED, as opposed to merely finished.
INVALIDATING = {"SL"}


def horizon_for(tf: str) -> str:
    return HORIZON_BY_TF.get(tf, "intraday")


def duration_hours(outcome: str, tf: str) -> float:
    table = STOP_OUT_HOURS if outcome in INVALIDATING else RESOLVED_HOURS
    return table[horizon_for(tf)]


def key(symbol: str, direction: str) -> str:
    return f"{symbol}|{direction}"


def record(con, *, symbol: str, tf: str, direction: str, outcome: str,
           exit_ts: int, setup_id: str) -> dict | None:
    """Emit a cooldown fact for one closed trade. Idempotent by content hash.

    `confirmed_at` is the EXIT time, not the moment this ran. A cooldown that
    began when the report was generated would lock out different trades on a
    replay than it did live, which would make the forward record unreproducible.
    """
    if outcome == "MISSED":
        return None                     # no position was taken; nothing to cool
    hours = duration_hours(outcome, tf)
    payload = {"event": "COOLDOWN", "key": key(symbol, direction),
               "symbol": symbol, "direction": direction, "tf": tf,
               "horizon": horizon_for(tf), "outcome": outcome,
               "invalidating": outcome in INVALIDATING,
               "hours": hours, "expires_at": int(exit_ts + hours * HOUR),
               "setup_id": setup_id, "market_time": int(exit_ts),
               "reason": ("the level was invalidated — a stop-out is the market "
                          "refusing the thesis" if outcome in INVALIDATING else
                          "the level resolved rather than failed — a short pause "
                          "only, so a working level is not discarded")}
    # Returns the payload only when a NEW fact was written. `insert_fact` is
    # content-hash idempotent, so a re-run inserts nothing — and a caller that
    # counted the return value regardless would report fresh cooldowns on every
    # pass over unchanged history, which is exactly the signal that is supposed
    # to prove determinism.
    if not store.insert_fact(con, symbol=symbol, tf=tf, kind="cooldown",
                             market_time=exit_ts, confirmed_at=exit_ts,
                             algo_version=COOLDOWN_VERSION, payload=payload):
        return None
    return payload


def load(con, *, baseline_start: int = 0) -> list:
    """Every cooldown fact once, ordered. The caller then evaluates any number of
    `as_of` cursors against it in memory — `risk.run` asks this question once per
    trade intent, and a query per question would put hundreds of round-trips on
    the hot path of every scan cycle."""
    import json
    return [json.loads(raw) for (raw,) in con.execute(
        "SELECT payload FROM facts WHERE kind='cooldown' AND algo_version=? "
        "AND confirmed_at>=? ORDER BY confirmed_at",
        (COOLDOWN_VERSION, baseline_start)).fetchall()]


def blocked_at(facts: list, as_of: int, symbol: str, direction: str):
    """The cooldown blocking this entry at `as_of`, or None.

    Point-in-time by construction: a fact only counts once its own start has
    passed, so a replay at any cursor reaches the verdict the live pass did.
    Where several overlap the one expiring LAST wins — a later stop-out must
    never be shortened by an earlier take-profit that happened to fire after it.
    """
    k = key(symbol, direction)
    best = None
    for p in facts:
        if p["key"] != k:
            continue
        if not (p["market_time"] <= as_of < p["expires_at"]):
            continue
        if best is None or p["expires_at"] > best["expires_at"]:
            best = p
    return best


def active_at(con, as_of: int, *, baseline_start: int = 0) -> dict:
    """Cooldowns in force at `as_of`, keyed by symbol|direction.

    Point-in-time by construction: only facts whose `confirmed_at` has already
    passed are considered, so this can be called from a replay at any cursor and
    from the live loop with the same meaning. Where several overlap, the one
    expiring LAST wins — a later stop-out must never be shortened by an earlier
    take-profit that happened to fire after it.
    """
    out: dict = {}
    rows = con.execute(
        "SELECT payload FROM facts WHERE kind='cooldown' AND algo_version=? "
        "AND confirmed_at<=? AND confirmed_at>=? ORDER BY confirmed_at",
        (COOLDOWN_VERSION, as_of, baseline_start)).fetchall()
    import json
    for (raw,) in rows:
        p = json.loads(raw)
        if p["expires_at"] <= as_of:
            continue
        cur = out.get(p["key"])
        if cur is None or p["expires_at"] > cur["expires_at"]:
            out[p["key"]] = p
    return out


def blocked(active: dict, symbol: str, direction: str):
    """The cooldown blocking this entry, or None. Returns the FACT so a caller
    can put the reason in front of the operator rather than a bare refusal."""
    return active.get(key(symbol, direction))


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    """Engine-contract entry point: derive cooldowns from recorded exits.

    Deliberately DERIVED rather than maintained as live state. State that is
    mutated as trades close cannot be replayed, and a cooldown that cannot be
    replayed silently changes which trades a historical run would have taken.
    Every fact here is a pure function of exec facts that already exist.
    """
    import json

    from .execsim import EXEC_VERSION
    with RunRecorder(con, "cooldowns", COOLDOWN_VERSION, symbol, tf) as rec:
        n = 0
        rows = store.get_facts(con, symbol, tf, "exec", EXEC_VERSION)
        rec.n_inputs = len(rows)
        for r in rows:
            p = json.loads(r["payload"])
            direction = p.get("direction")
            if not direction:
                continue
            if record(con, symbol=symbol, tf=tf, direction=direction,
                      outcome=p["outcome"], exit_ts=r["confirmed_at"],
                      setup_id=p["setup_id"]) is not None:
                n += 1
        con.commit()
        rec.n_new_facts = n
        return {"symbol": symbol, "tf": tf, "cooldowns": n}
