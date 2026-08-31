"""Sessions engine — which trading session each bar printed in. algo sessions-v0.1-draft.

The last unbuilt indicator engine (PROGRAM-PLAN Wave 2.4). CONDITION already
has `volatility`, PARTICIPATION has `volume`; what neither can say is WHEN a
reading happened in the day's rhythm. The killzone literature's claim — loosely,
that volume and volatility concentrate in the London and New York windows and
that Asia builds the ranges those windows break — is a claim about THIS store's
own bars, and it has never been asked of them because nothing recorded the
session. This engine records it; `factorstats` decides later whether it means
anything here.

RECORDED, NOT FILTERED ON, UNTIL GRADED (house convention 7). Nothing consumes
these facts and nothing may. Crypto trades 24/7 — there is no closing bell that
makes a session a hard boundary, so a session is at most a SOFT PRIOR imported
from markets that do close, and a prior imported from another market is exactly
the kind of plausible-sounding rule this project refuses to gate on unmeasured.
The store will decide. `setups.py`, `risk.py`, `execsim.py` and `scalein.py`
do not import this module.

THE ONE READING. Each bar is labelled by the session containing its OPEN, in
UTC, and a fact is emitted only when the label CHANGES — the same emit-on-change
shape as `regime.py`, and for the same reason: the session of every bar is
derivable from the clock, so per-bar emission would write ~5 facts of content
into hundreds of rows of calendar. A session nobody traded (a venue-acknowledged
quiet stretch with no bars) emits nothing, which is honest: the label describes
bars that exist, not hours that passed.

TIMEFRAME REFUSAL. Only timeframes whose bars fit inside one session get a
label. The shortest session below is two hours, so 5m/15m/1H qualify and
4H/1D/1W do not — a 4H bucket spans up to three sessions and a label naming one
of them would be mostly false, while a daily bar contains every session by
construction. An unsupported timeframe emits nothing at all rather than a label
wearing more precision than the bar carries; the same absent-key honesty as
`volume.SESSION_ANCHOR` ("an absent key means 'this timeframe has no session',
not 'default to a day'").

CAUSALITY (house convention 3/4). The label is clock-derivable at the bar's
open, but the fact confirms at the bar's CLOSE (`confirmed_at = open_ts +
tf_seconds`) like every other fact in this store. The earlier claim would buy
nothing: whatever a grader will join the label to — the bar's own range, volume,
or a setup confirmed on it — only exists at the close anyway, and one
convention for "when was this knowable" is worth more than one bar of lead time
on a clock label.

APPEND-ONLY AND IDEMPOTENT. Pure function of stored candles: no wall clock, no
RNG. Re-running over identical candles writes zero facts.

KNOWN EXPOSURE, noted rather than fixed: the input series is not quite
immutable. A late gap-fill candle landing INSIDE an already-labelled stretch
changes which bar is the first of its session and how many bars the previous
state held, so the next run appends regenerated transition facts with a
different `from` / `bars_in_prev_state` beside the originals, under the same
version. This is the same accepted shape as every emit-on-change engine that
re-derives from a series late data can extend (`regime` re-derives from
structure facts the same way); a consumer reads the latest fact per
market_time, and the label itself — the field a grader joins on — is clock-
derived and cannot change.
"""
from . import store
from .runlog import RunRecorder

SESSIONS_VERSION = "sessions-v0.1-draft"

#: UTC session windows as (name, start_hour, end_hour), end exclusive; ASIA
#: wraps midnight. The boundaries are the conventional crypto reading of the
#: equity/FX session map — Asia hands to London at 07:00, the London/New York
#: overlap carries 12:00-16:00, and the 21:00-23:00 gap after the US close is
#: named QUIET rather than folded into a neighbour, because "the dead zone" is
#: the cohort the killzone framing predicts least volume for and folding it
#: away would make that prediction untestable. Crypto is 24/7: these are soft
#: priors to be graded against this store's own bars, never a hard gate.
SESSIONS = (
    ("ASIA", 23, 7),
    ("LONDON", 7, 12),
    ("NY_OVERLAP", 12, 16),
    ("NY", 16, 21),
    ("QUIET", 21, 23),
)

#: Timeframes whose bars sit wholly inside one session. The shortest session is
#: QUIET at two hours, so anything up to 1H fits; a 4H bucket (opening 00/04/
#: 08/12/16/20 UTC) crosses a boundary in every single slot. See the docstring
#: for why the unsupported timeframes emit nothing instead of a rounded label.
SESSION_TFS = ("5m", "15m", "1H")

_HOUR_SECONDS = 3600
_DAY_SECONDS = 86400

#: hour-of-day -> session name, built once from SESSIONS so the table and the
#: lookup cannot disagree.
_BY_HOUR = {}
for _name, _start, _end in SESSIONS:
    _h = _start
    while _h != _end:
        _BY_HOUR[_h] = _name
        _h = (_h + 1) % 24
assert len(_BY_HOUR) == 24, "the session map must cover every UTC hour"


def session_label(ts: int) -> str:
    """Session containing the UTC instant `ts`. Total: every hour has one."""
    return _BY_HOUR[(ts % _DAY_SECONDS) // _HOUR_SECONDS]


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "sessions", SESSIONS_VERSION, symbol, tf) as rec:
        if tf not in SESSION_TFS:
            # Not a warmup gap — a structural refusal. The run record still
            # exists so "sessions ran and wrote nothing here" is visible.
            rec.notes = "unsupported timeframe: bar spans sessions"
            return {"symbol": symbol, "tf": tf, "changes": 0,
                    "unsupported": True}
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)

        n_changes = 0
        current, since = None, None
        for i, c in enumerate(candles):
            label = session_label(c["open_ts"])
            if label == current:
                continue
            payload = {"event": "SESSION", "session": label,
                       "from": current,
                       "state": "ESTABLISHED" if current is None else "CHANGED",
                       "bars_in_prev_state": None if since is None else i - since,
                       "utc_hour": (c["open_ts"] % _DAY_SECONDS) // _HOUR_SECONDS}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="sessions",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=SESSIONS_VERSION, payload=payload):
                n_changes += 1
            current, since = label, i

        con.commit()
        rec.n_new_facts = n_changes
        return {"symbol": symbol, "tf": tf, "changes": n_changes,
                "unsupported": False}


def main(argv=None) -> int:
    import argparse
    import json
    from .importer import TF_SECONDS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("symbol")
    ap.add_argument("tf")
    args = ap.parse_args(argv)
    con = store.connect()
    try:
        print(json.dumps(run(con, args.symbol, args.tf,
                             TF_SECONDS[args.tf]), indent=2))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
