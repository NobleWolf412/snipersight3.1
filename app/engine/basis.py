"""Cross-venue basis — the spread between where you trade and where depth is.

algo basis-v0.1-draft. MEASURED, NOT ENABLED, and not even MEASURED_NOT_ENABLED
in the pipeline's sense — this engine has no setup to withhold. It records one
number per closed bar: the difference between the execution venue's close and
the reference venue's close, for every symbol that has a reference feed
(venues.REFERENCE). Nothing reads it, nothing gates on it, nothing may until
the grading layer has judged whether it predicts anything against the book —
constitution rule 7, the same posture breakout and trend ride.

Why record it at all: the operator's arbitrage question (2026-08-09). The
tradeable version of cross-venue arb is a different machine — order books,
sub-second execution, capital on both legs — and this platform is closed
candles on a minutes cadence by design. But whether a stretched basis
PREDICTS anything a setup can use (entry filter, confluence, exit accelerant)
is exactly the kind of question the fact store exists to answer cheaply, and
it can only answer it about basis readings that were recorded before anyone
knew.

Two honesty notes, both recorded on the fact rather than corrected away:

· QUOTE BLEND. The execution series may be USD-quoted (Coinbase spot,
  Kraken perps) while the reference is USDT-quoted, so the basis blends venue
  spread with USD/USDT. `ref_quote` is on every fact; whether to normalise is
  an operator decision deferred until grading, because a normalisation baked
  in here would be unrecoverable from the recorded number.

· SAMPLE BIAS. A bucket either venue served nothing for produces NO fact —
  absence is recorded as absence, never as zero. On a thin market the stream
  therefore over-represents liquid hours. That is the truth about the data,
  and the liquid control symbol in venues.REFERENCE exists so grading can see
  the bias by comparison rather than guess at it.
"""
from decimal import Decimal

from . import binance, store, venues
from .runlog import RunRecorder

BASIS_VERSION = "basis-v0.1-draft"

#: One timeframe, to start. The basis is a per-bar reading, so every tf it
#: runs on multiplies the fact volume for a stream nothing consumes yet; 1H is
#: fine enough to see intraday stretch and coarse enough to stay cheap
#: (operator default, 2026-08-09). Widening this is a rule change — new
#: version, per the constitution.
BASIS_TF = "1H"


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    """Record the close-to-close basis for one (symbol, tf) series.

    Facts key on the TRADING symbol — the reading is about that market, the
    reference key is plumbing and appears only inside the payload. market_time
    is the bar's open (like every per-bar engine here); confirmed_at is the
    bar's close, the first moment both closes were knowable. Idempotent via
    content hash, like everything else: re-running over the same bars is a
    no-op, and a reference bar arriving LATE simply lets the fact be written
    on a later pass with the same content it would always have had.
    """
    ref = venues.reference_for(symbol)
    if ref is None or tf != BASIS_TF:
        return {"symbol": symbol, "tf": tf, "facts": 0}
    venue_key, _native = ref
    rkey = venues.ref_key(symbol)
    with RunRecorder(con, "basis", BASIS_VERSION, symbol, tf) as rec:
        exec_rows = store.get_candles(con, symbol, tf)
        ref_close = {r["open_ts"]: r["close"]
                     for r in store.get_candles(con, rkey, tf)}
        rec.n_inputs = len(exec_rows)
        n_facts = 0
        for c in exec_rows:
            rc = ref_close.get(c["open_ts"])
            if rc is None:
                continue                    # absence stays absence, never zero
            ec_d, rc_d = Decimal(c["close"]), Decimal(rc)
            if rc_d == 0:
                continue                    # a zero close is venue garbage, not a spread
            basis = ec_d - rc_d
            payload = {
                "event": "BASIS",
                "exec_close": str(ec_d),
                "ref_close": str(rc_d),
                "basis": str(basis),
                # of the REFERENCE close: the deep venue is the yardstick the
                # thin one is being measured against, not the reverse.
                "basis_pct": str((basis / rc_d * 100).quantize(Decimal("0.000001"))),
                "ref_source": venue_key,
                "ref_quote": binance.QUOTE,
                # From the venue authority, not re-derived from symbol
                # spelling — a spelling heuristic here was a second authority
                # for a number (rule 9), written into append-only facts, on
                # exactly the field that exists so grading can un-blend
                # USD/USDT later. Auditor catch, 2026-08-09.
                "exec_quote": venues.venue_for(symbol).quote,
            }
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="basis",
                                 market_time=c["open_ts"],
                                 confirmed_at=c["open_ts"] + tf_seconds,
                                 algo_version=BASIS_VERSION, payload=payload):
                n_facts += 1
        con.commit()
        rec.n_new_facts = n_facts
        rec.notes = f"basis_bars={n_facts} ref={rkey}"
        return {"symbol": symbol, "tf": tf, "facts": n_facts}
