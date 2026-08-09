"""The per-symbol engine sequence — declared ONCE, imported by every runner.

Three runners walked the same pipeline from three separately-maintained lists:
`live.ENGINES`, `ingest.PER_SYMBOL_ENGINES` and `backfill.ENGINES`. They had
drifted, and the drift was silent because nothing compared them:

  · `cooldowns` was in NONE of them. It was built in S41, tested, documented,
    and consumed by `risk.py` — which read an empty list on every pass, so the
    re-entry lockout has never fired once. Measured 2026-07-30: 0 cooldown
    facts in the store, `cooldowns` absent from `engine_runs` entirely, and 86
    of 1,007 VALIDATED intents (8.5%) would have been blocked. The 53 that
    filled returned -5.19 R. A guardrail that is not in the roster is not a
    guardrail.
  · `ranges, ma, momentum, volatility, volume, breakout` were in `live` only,
    so a symbol onboarded today got full history for the older engines and
    forward-only for these six — two populations in one fact store, with
    nothing marking which was which.

The order is load-bearing and is the reason this is a sequence rather than a
set. Each engine reads the facts the ones before it wrote:

    swings -> structure -> zones/liquidity/regime -> setups -> execsim

`execsim` appears TWICE on purpose: `scalein` adds to positions the first pass
opened, and those adds need filling. `cooldowns` is LAST of the trading
engines because it derives purely from exec facts, so it must see the adds too.

`cycles` is observational (BTC 1D, no consumers) and sits at the end.
"""

from . import (basis, breakout, cooldowns, cycles, execsim, fvg, liquidity,
               ma, manual, momentum, ranges, regime, scalein, setups,
               structure, swings, trend, volatility, volprofile, volume,
               zones)

# Facts the market DESCRIPTION layer derives. No trading consumer reads the
# indicator engines yet and none may until `factorstats` grades them — they are
# here because an engine that is built, tested and never run emits nothing to
# grade, which is exactly how `ranges.py` and `cooldowns.py` both died.
DESCRIPTIVE = (swings, structure, zones, liquidity, regime, ranges,
               ma, momentum, volatility, volume, fvg, volprofile,
               # basis self-selects: it early-returns for every symbol without
               # a reference feed (venues.REFERENCE) and every tf but its own,
               # so its presence here costs the other 91 symbols nothing.
               basis)

# MEASURED AND NOT ENABLED. `breakout` emits setup facts so its sample keeps
# growing and can be re-graded, but neither `execsim` nor `risk` reads
# BREAKOUT_VERSION, so it trades nothing. Graded 2026-07-30: n=55, -0.076 R,
# CI [-0.545, +0.426], P(>0) 37.4% — indistinguishable from zero. REVERSAL
# cleared this bar; this did not, so it does not ship.
#
# `trend` joins on the same terms, and for a reason that is not about its P&L.
# Grading the MA against the book on 2026-08-04 found LONG x ABOVE = 0 and
# SHORT x BELOW = 0 across all 477 closed trades: both shipped playbooks enter
# counter-move, so every trend-following factor is a CONSTANT here and cannot
# be graded at all. This records trades that buy strength, which is the only
# thing that can populate that cohort. First sample on BTCUSDT 1H: 32 setups,
# 26 of them in the previously-empty AGREES bucket. Whether it MAKES money is
# a separate question its own sample will answer, on the same bar as everything
# else — an interval above zero.
MEASURED_NOT_ENABLED = (breakout, trend)

# The trading path, in dependency order. See the module docstring for why
# `execsim` is listed twice and why `cooldowns` is last.
TRADING = (setups, execsim, scalein, execsim, cooldowns)

OBSERVATIONAL = (cycles,)

# The OPERATOR's own paper book, and deliberately NOT part of TRADING. It
# resolves trades the operator armed by hand, under `manual-*` — a namespace no
# strategy consumer queries, so a discretionary trade cannot reach the record
# `edgestats`/`factorstats` grade. Named as a namespace rather than a version
# because the book reads every tag it has ever written (manual.MANUAL_VERSIONS)
# so that a bump cannot strand an order still open under the old one. It is in this roster for the reason given
# above for `cooldowns`: an engine that is built, tested and never run resolves
# nothing, and an unresolved intent is a trade the operator placed and can never
# see the outcome of.
OPERATOR = (manual,)

PER_SYMBOL = (DESCRIPTIVE + MEASURED_NOT_ENABLED + TRADING + OPERATOR
              + OBSERVATIONAL)


def names() -> list[str]:
    """Engine names in run order, for logging and for the roster test.

    A module that appears twice (`execsim`) is suffixed on the repeat, so a log
    line can say WHICH pass it is without a hand-written label drifting from the
    module beside it.
    """
    out, seen = [], {}
    for m in PER_SYMBOL:
        n = m.__name__.rsplit(".", 1)[-1]
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}{seen[n]}")
    return out


# ---------------------------------------------------------------- the one loop
#
# The roster was unified above; the LOOP that walks it was still written twice.
# `live.cycle` had per-engine exception guards and a per-symbol quality gate;
# `ingest.run_engines` had neither and raised on the first blocked symbol. Two
# loops over one roster is the same disease as two rosters — whichever one
# grows a check, the other silently lacks it.
#
# The loop also now names WHY it did not run, before it spends anything.
# Ported in shape from the prior project's staged rejection funnel
# (`orchestrator._process_symbol`), where `no_data` / `missing_critical_tf`
# are buckets checked before any compute. What made that design earn its port
# is a failure this repo already had: `cooldowns` sat outside every runner's
# roster and "has never fired once" — and nothing showed a zero where its
# work should have been. A gate with a named bucket cannot fail silently,
# because its absence of rejections is itself a visible number.
#
# The vocabulary is closed ON PURPOSE (see GATES). The prior project guarded
# its buckets with a _KNOWN_REASONS set after new reason strings drifted in
# unlabelled; here an unknown gate name is a programming error, loud at write.

ALL_TFS = ("5m", "15m", "1H", "4H", "1D", "1W")

# The closed gate vocabulary. Adding a gate means adding it HERE, to the
# funnel's label map, and to the tests — in one commit. An unknown name
# raises rather than warns because, unlike setup rejection reasons (which
# strategy code mints at arm's length), gates are minted three lines below
# their declaration; drift here is not vocabulary growth, it is a typo.
GATES = frozenset({"NO_DATA", "SHORT_HISTORY", "QUALITY_BLOCKED"})


def _record_gate(con, symbol: str, tf: str, gate: str, detail: str,
                 now: int) -> None:
    if gate not in GATES:
        raise ValueError(f"unknown pipeline gate {gate!r} — add it to "
                         f"pipeline.GATES, the funnel labels, and the tests")
    # Preserve first-seen on re-trip: "NO_DATA since 26 Jul" is the useful
    # sentence, and a timestamp that resets every cycle can never say it.
    con.execute(
        "INSERT INTO pipeline_gates (symbol, tf, gate, detail, measured_at) "
        "VALUES (?,?,?,?,?) ON CONFLICT(symbol, tf, gate) "
        "DO UPDATE SET detail=excluded.detail",
        (symbol, tf, gate, detail[:300], now))


def run_symbol(con, symbol: str, now: int | None = None, log=None) -> dict:
    """Run every per-symbol engine, gates first. THE loop — both runners call it.

    Returns {"blocked": str | None, "gates": {(tf, gate): detail}} so the
    caller keeps its own policy: `live.cycle` aggregates blocked symbols into
    one warning and carries on; `ingest.run_engines` raises, because onboarding
    a symbol whose market data fails audit should fail the onboard.

    What each gate DOES is deliberately unequal, and the asymmetry is the
    design:

      QUALITY_BLOCKED  skips the symbol's engines (existing behaviour — the
                       audit gate doing its job, now counted where it can be
                       seen instead of only in a log line).
      NO_DATA          skips that timeframe's engines. Zero candles in, zero
                       facts out — every engine walks the candle list and
                       writes nothing on empty input, so the skip changes no
                       record; it only names the absence and saves the walk.
      SHORT_HISTORY    is OBSERVED AND NOT ENFORCED. Engines still run. A
                       series that starts later than its floor produces facts
                       from the history it has, and those facts are already in
                       the recorded book — blocking them now would change what
                       the book contains under the same algo versions, which
                       is the rewrite the versioning rule exists to forbid.
                       The gate makes the condition visible; whether it should
                       ever gate is a question for measurement, not a default.
    """
    import time as _time
    from . import importer, ingest, quality   # lazy: ingest imports this module

    now = int(_time.time()) if now is None else now
    tripped: dict = {}

    def trip(tf, gate, detail):
        tripped[(tf, gate)] = detail
        _record_gate(con, symbol, tf, gate, detail, now)

    blocked = None
    try:
        quality.assert_market_ready(con, symbol, now)
    except Exception as exc:
        blocked = f"{type(exc).__name__}: {exc}"
        trip("*", "QUALITY_BLOCKED", blocked)

    if blocked is None:
        # Observed, not enforced — see the docstring. `missing_history` is the
        # PF_XLMUSD detector: the series starts later than its floor and no
        # productive import ever closed the window, so this is a HOLE, not
        # merely a venue whose history starts where it starts.
        try:
            for tf in ingest.missing_history(con, symbol, now):
                trip(tf, "SHORT_HISTORY",
                     "stored history starts later than its floor and no "
                     "productive import has closed the window")
        except Exception as exc:            # the detector must never block the loop
            if log:
                log.warning(f"short-history check skipped {symbol}: "
                            f"{type(exc).__name__} {exc}")

        counts = {tf: n for tf, n in con.execute(
            "SELECT tf, COUNT(*) FROM candles WHERE symbol=? GROUP BY tf",
            (symbol,))}
        live_tfs = []
        for tf in ALL_TFS:
            if counts.get(tf):
                live_tfs.append(tf)
            else:
                trip(tf, "NO_DATA", "no candles stored for this timeframe")
        # MODULE-outer, timeframe-inner, exactly as both runners always were —
        # and it is load-bearing, not style: `scalein`'s 1H pass reads the HTF
        # positions `execsim` writes on 4H/1D. Timeframe-outer would run
        # scalein before this cycle's HTF execsim passes exist, landing every
        # add one cycle late — a silent lag, which is the drift disease this
        # function exists to end.
        #
        # The candle cache is scoped to exactly this walk, and the scoping IS
        # the correctness argument: engines write facts and never candles
        # (pinned by test_candle_cache's source scan), and imports/aggregation
        # both ran before this point, so the series is immutable for the
        # duration. Without it, every module re-parsed the same rows out of
        # SQLite — eighteen reads of an identical series per (symbol, tf).
        from . import store as _store
        faulted = set()
        with _store.candle_cache(con):
            for mod in PER_SYMBOL:
                name = mod.__name__.rsplit(".", 1)[-1]
                for tf in live_tfs:
                    try:
                        mod.run(con, symbol, tf, importer.TF_SECONDS[tf])
                    except Exception as exc:
                        # One engine's failure is a fault to surface, not a
                        # rejection reason to count — an exception that becomes
                        # a funnel statistic is an exception nobody fixes. It
                        # is RECORDED as current state (engine_faults): a
                        # fault living only in a log line is an archaeology
                        # dig, and Diagnostics now leads with what is failing.
                        faulted.add((tf, name))
                        con.execute(
                            "INSERT INTO engine_faults "
                            "(symbol, tf, engine, error, first_seen, last_seen, times) "
                            "VALUES (?,?,?,?,?,?,1) "
                            "ON CONFLICT(symbol, tf, engine) DO UPDATE SET "
                            "error=excluded.error, last_seen=excluded.last_seen, "
                            "times=times+1",
                            (symbol, tf, name,
                             f"{type(exc).__name__}: {exc}"[:300], now, now))
                        if log:
                            log.warning(f"engine {name} failed on "
                                        f"{symbol} {tf}: {type(exc).__name__} {exc}")
        # a fault that did not recur this walk has been fixed — current state,
        # exactly like the gates table below
        stale_faults = [(f_tf, f_eng) for (f_sym, f_tf, f_eng) in con.execute(
            "SELECT symbol, tf, engine FROM engine_faults WHERE symbol=?",
            (symbol,)) if (f_tf, f_eng) not in faulted]
        for f_tf, f_eng in stale_faults:
            con.execute("DELETE FROM engine_faults WHERE symbol=? AND tf=? "
                        "AND engine=?", (symbol, f_tf, f_eng))

    # A gate that no longer trips is DELETED: this table is current state, and
    # a stale row would keep reporting a hole the last cycle already closed.
    stale = [(s_tf, s_gate) for (s_sym, s_tf, s_gate) in con.execute(
        "SELECT symbol, tf, gate FROM pipeline_gates WHERE symbol=?", (symbol,))
        if (s_tf, s_gate) not in tripped]
    for s_tf, s_gate in stale:
        con.execute("DELETE FROM pipeline_gates WHERE symbol=? AND tf=? AND gate=?",
                    (symbol, s_tf, s_gate))
    con.commit()
    return {"blocked": blocked, "gates": tripped}
