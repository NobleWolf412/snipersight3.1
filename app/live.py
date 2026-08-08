"""Forward paper loop — the scanner running live.

Wakes are aligned to the candle grid: just past each 5m boundary (where every
tracked timeframe closes — see next_wake), capped by the POLL_SECONDS drift
heartbeat. Each pass: import newly CLOSED candles (never developing ones, §5),
re-aggregate 4H/1W, re-run every engine (all idempotent/append-only — a cycle
with no new data writes zero facts), then notify on any NEW validated setup.
This is the start of the forward paper track record (§15: paper results are
their own category — nothing here was knowable to the calibration).

Usage:
  python live.py           # run forever, poll every 60s
  python live.py --once    # single cycle (testing / task scheduler)
"""
import argparse
import atexit
import faulthandler
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import notify
from engine import (automation, autotrader, broker_factory, execution, positions, store,
                    importer, aggregator, risk, universe, ingest, quality,
                    marketdata, pipeline)
from engine.runlog import get_logger

# ---------------------------------------------------------------- exit forensics
#
# This process exited 191 times with rc=1 and nothing to show for it. The exit
# code alone cannot tell a crash from a terminate from a clean stop, and the one
# thing every theory needed — what the process was doing at the end — was never
# recorded. So it records itself now. Each channel writes a DIFFERENT line, and
# which line appears is the diagnosis:
#
#   FATAL   ...  the interpreter died in C (segfault / access violation);
#                faulthandler dumps every thread's Python stack
#   SIGNAL  ...  something asked it to stop and Python got to hear about it
#   EXIT    ...  ordinary interpreter shutdown, with the code
#   (nothing) .. TerminateProcess — the OS shot it and nothing can be caught,
#                which narrows the caller to something holding a handle
#
# Silence is now evidence too, which it was not before.
_EXIT_LOG = Path(__file__).resolve().parent / "data" / "live-exit.log"


def _exit_note(kind: str, detail: str = "") -> None:
    try:
        _EXIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_EXIT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid={os.getpid()} "
                    f"{kind} {detail}\n")
            f.flush()
            os.fsync(f.fileno())      # the process may be about to vanish
    except Exception:
        pass


def install_exit_forensics() -> None:
    try:
        _fh = open(_EXIT_LOG, "a", encoding="utf-8")
        faulthandler.enable(file=_fh, all_threads=True)
    except Exception:
        pass
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, lambda s, _f: (_exit_note("SIGNAL", f"sig={s}"),
                                              sys.exit(1)))
        except Exception:
            pass                      # not every signal is settable on Windows
    atexit.register(lambda: _exit_note("EXIT", "interpreter shutdown"))

NATIVE_TFS = tuple(importer.NATIVE_TFS)
# None, not 0.0, and the difference is not cosmetic. This is compared against
# time.monotonic(), whose zero is BOOT — so 0.0 does not mean "never refreshed",
# it means "refreshed at boot". On a machine that has been up for hours the
# subtraction is huge and the first refresh runs, which is why this looked
# correct for months on a desktop. On a freshly booted one — a CI runner, a
# reboot, exactly when start.bat launches the scanner — monotonic() is a few
# seconds, the throttle below sees less than REFRESH_SECONDS elapsed, and the
# first universe refresh of the session is silently skipped for up to an hour.
_last_universe_refresh = None
# Symbols already announced as newly onboarded. A symbol stays in `warming`
# forever when its venue has less history than the engines need, so without this
# it is announced on every refresh and every restart. See refresh_universe().
_announced_warming: set[str] = set()
# One tuple, owned by the pipeline beside the loop that walks it. This was a
# second copy, and a second copy of a tuple is a roster waiting to drift.
ALL_TFS = pipeline.ALL_TFS
# The roster lives in `engine/pipeline.py` and is imported by all three runners
# (live, ingest, backfill). It used to be maintained here and copied there, and
# the copies drifted — `cooldowns` was in none of them, so the re-entry lockout
# `risk.py` consumes has never fired once. See that module for the measurements.
ENGINES = pipeline.PER_SYMBOL
POLL_SECONDS = 60

# ---------------------------------------------------- boundary-aligned wakeups
#
# The sleep used to be a blind 60-second tick, unaligned to anything. A candle
# is the unit of knowledge in this system — every engine is deliberately blind
# between closes (§5) — yet the moment a candle closed, the scanner was a
# uniformly random 0-60s into its nap, plus the cycle time, before it looked.
# Signal latency was jitter, not a number.
#
# Ported from the prior project's ohlcv_cache TTL fix, which is the same
# insight from the caching side: expiry anchored to elapsed time served
# readings up to ~59 minutes stale past a boundary, and 84 LONG rejections in
# one May 2026 session traced to one stale reading. Staleness must be anchored
# to the CANDLE BOUNDARY, because that is when the world can change.
#
# One grid covers every boundary, and that is a checked fact, not a hope:
# every tracked granularity is a multiple of 300s, and the 1D/1W boundaries
# (midnight / Monday 00:00 UTC) sit on the 300s grid too — pinned in
# test_boundary_wake. So a wake landing just after each 15m edge lands just
# after EVERY edge that matters.
#
# The drift heartbeat still caps the nap at POLL_SECONDS: the drift monitor
# is the one consumer that genuinely wants elapsed-time cadence (it watches
# the live price BETWEEN closes), and the scanner-health light declares the
# process stuck at SCANNER_STALE_S=90 — both constraints hold by construction
# because next_wake never exceeds the poll.
CANDLE_GRID_S = 300
# How long after the boundary the venue needs to finalize the bar before an
# import can land it. The prior project ran 5.0s in production
# (ohlcv_cache.is_expired buffer_seconds); kept. A candle that finalizes
# slower than this is not lost — the next heartbeat tick retries within 60s,
# exactly as before this change.
CANDLE_FINALIZATION_S = 5


def next_wake(now: float, poll: float = POLL_SECONDS,
              grid: float = CANDLE_GRID_S,
              buffer: float = CANDLE_FINALIZATION_S) -> float:
    """Seconds to sleep so the next wake serves both masters.

    Lands on whichever comes first: the drift heartbeat (poll) or the moment
    just past the next candle boundary (boundary + finalization buffer). The
    floor of 1s exists so a wake a hair before its target cannot degenerate
    into a hot loop; the cap at poll is the liveness contract.
    """
    floor = now - now % grid
    for target in (floor + buffer, floor + grid + buffer):
        if target > now:
            return max(1.0, min(poll, target - now))
    return poll                                    # unreachable; belt and braces

# Price-drift monitor (ported concept from user's prior project): between
# candle closes the engines are deliberately blind (§5). This watches the
# live price vs the last CLOSED 15m candle and ALERTS on violent intracandle
# moves — awareness only, never analysis on unclosed data. One alert per
# symbol per 15m bucket.
DRIFT_VERSION = "drift-v0.2-draft"
DRIFT_ALERT_PCT = 3.0
# v0.2: the reference close must be RECENT. Comparing a live price against a
# stale candle does not measure an intracandle move, it measures how long the
# importer has been behind — and since the dedupe only spaces alerts one per
# 15m bucket, a symbol whose imports have lagged alerts every 15 minutes
# forever. Measured 2026-07-26..29: 139 alerts, over half from two symbols
# (COTI-USD, EUL-USD) whose reference closes were 2.8 and 3.5 DAYS old.
DRIFT_MAX_REF_AGE_BARS = 2
DRIFT_BAR_SECONDS = 900
_drift_alerted: dict = {}
_drift_muted: dict = {}          # symbol -> bucket, so a mute is logged once

# --- Announce policy (see cycle()) ---------------------------------------
# How late a setup may be and still be announced, in bars of its OWN timeframe.
# 2 means "at most one bar behind": the signal became knowable at a bar close
# and the next scan pass should carry it. Older than that and it is history.
ANNOUNCE_MAX_BARS = 2
# Which setup states earn an interruption. FORMING means "price is APPROACHING
# a zone" — context, not a trade — and there are roughly as many FORMING facts
# as VALIDATED ones, so it is about half of all setup notifications. Kept on by
# default because that is an operator preference, not an engine decision;
# dropping "FORMING" here silences them without touching the fact stream.
ANNOUNCE_STATES = ("VALIDATED", "FORMING")


def refresh_universe(con, log, beat=None):
    """Hourly: re-rank live, onboard newly-admitted symbols (backfill+engines)."""
    global _last_universe_refresh
    if (_last_universe_refresh is not None
            and time.monotonic() - _last_universe_refresh
                < universe.REFRESH_SECONDS):
        return
    _last_universe_refresh = time.monotonic()
    # the ranking sweep is a ~40s blocking call — beat inside it, not around it
    prog = (lambda d, t: beat(f"universe {d}/{t}")) if beat else None
    r = universe.refresh(con, progress=prog)
    if r["source"] == "unavailable":
        log.warning("universe refresh: rank source unavailable — unchanged")
    else:
        for sym in r["warming"]:
            try:
                res = ingest.onboard(con, sym)
                n_daily = res["candles"].get("1D", 0)
                log.info(f"UNIVERSE onboarded {sym}: {n_daily} daily candles")
                # ANNOUNCE ONCE. `warming` lists every symbol short of the 200
                # daily candles the engines need, so a symbol whose venue simply
                # has no more history — CAP-USD has 35 and always will — is
                # re-onboarded and announced as "New symbol added" on every
                # hourly refresh AND every restart. It is not new, and saying so
                # repeatedly is both wrong and expensive: each toast spawns a
                # PowerShell process, and the scanner's remaining deaths all sit
                # in the startup burst where that fires once per warming symbol.
                if sym not in _announced_warming:
                    _announced_warming.add(sym)
                    # QUIET, and queued rather than spawned. Onboarding is
                    # awareness, not something to act on, and it fires once per
                    # warming symbol in the startup burst — which is exactly
                    # where the scanner's remaining deaths sat.
                    notify.enqueue(f"onboard|{sym}",
                                   "＋ New symbol added",
                                   f"{sym} joined the scan universe",
                                   notify.QUIET)
            except Exception as e:
                log.warning(f"onboard failed for {sym}: {e}")
        if r["warming"]:
            universe.refresh(con)      # re-classify: warmed symbols -> admitted
    # Runs whether or not the ranking answered. A hole in the candle store is
    # not a fact about whether the rank endpoint was up this hour, and the
    # symbols needing repair are already-tracked ones — the scan set survives a
    # failed refresh untouched.
    repair_short_history(con, log, beat)


def repair_short_history(con, log, beat=None):
    """Hourly: re-import timeframes a PARTIAL onboard left short.

    The onboarding retry above is keyed on `r["warming"]`, and membership of
    that list is decided by the DAILY candle count alone. A symbol whose 1D
    series is warm is therefore never re-onboarded no matter what its 1H and
    15m hold — which is how PF_XLMUSD ran 24 cycles with 1D warm and both
    intraday timeframes at zero, in `warming` on no refresh.

    `ingest.history_floor` stopped the live loop asking for 1970, and it does
    repair a timeframe that is entirely EMPTY, because the watermark is NULL and
    `cycle` falls through to the floor. What it cannot repair is a series that
    is merely SHORT: a partial onboard leaves a non-NULL watermark and the loop
    only ever walks FORWARD from it, so the history behind it stays missing for
    as long as the symbol is tracked.

    Deliberately outside the `source == "unavailable"` early return above: a
    hole in the candle store is not a fact about whether the ranking endpoint
    answered this hour.
    """
    for sym in universe.scan_symbols(con):
        try:
            short = ingest.missing_history(con, sym)
            if not short:
                continue
            if beat:
                beat(f"repair {sym}")
            gained = {tf: n for tf, n in
                      ingest.repair_history(con, sym, short).items() if n}
            if not gained:
                # Not a failure: the venue's history simply starts where it
                # starts. `missing_history` records the productive attempt and
                # will not ask again, so this line appears once per symbol.
                log.info(f"history probe {sym} {short}: venue served nothing "
                         f"older — series starts where the venue's does")
                continue
            log.warning(f"REPAIRED short history for {sym}: {gained} — "
                        f"onboarding had left these timeframes incomplete")
            ingest.run_engines(con, sym)
        except Exception as exc:
            log.warning(f"history repair skipped {sym}: "
                        f"{type(exc).__name__} {exc}")


def check_drift(con, log, threshold=DRIFT_ALERT_PCT, dry=False):
    now = int(time.time())
    bucket = now - now % DRIFT_BAR_SECONDS
    symbols = universe.current_symbols(con)
    # One batched call for the whole scan set. Per-symbol fetching was also
    # hard-wired to Coinbase, so once the universe became Phemex perps every
    # single request 404'd — twenty warnings a minute and zero drift coverage.
    try:
        prices = marketdata.last_prices(symbols)
    except Exception as exc:
        log.warning(f"drift check skipped this poll: price source unavailable "
                    f"({type(exc).__name__} {exc})")
        return
    unpriced = [s for s in symbols if s not in prices]
    if unpriced and _drift_muted.get("__unpriced__") != bucket:
        _drift_muted["__unpriced__"] = bucket
        log.warning(f"drift monitor blind for {len(unpriced)}/{len(symbols)} "
                    f"symbols — no live price: {', '.join(unpriced[:6])}")
    for sym in symbols:
        spot = prices.get(sym)
        if spot is None:
            continue
        try:
            row = con.execute(
                "SELECT open_ts, close FROM candles WHERE symbol=? AND tf='15m' "
                "ORDER BY open_ts DESC LIMIT 1", (sym,)).fetchone()
            if not row:
                continue
            ref_open, ref = int(row[0]), float(row[1])
            # Age of the reference measured from when that bar CLOSED.
            ref_age = now - (ref_open + DRIFT_BAR_SECONDS)
            if ref_age > DRIFT_MAX_REF_AGE_BARS * DRIFT_BAR_SECONDS:
                # Suppressing must be audible (loud-fallback rule) — but once
                # per bucket, not once per poll, or the fix trades an alert
                # flood for a log flood.
                if _drift_muted.get(sym) != bucket:
                    _drift_muted[sym] = bucket
                    log.warning(
                        f"drift check muted for {sym}: reference 15m close is "
                        f"{ref_age // 60}m old (limit "
                        f"{DRIFT_MAX_REF_AGE_BARS * DRIFT_BAR_SECONDS // 60}m) — "
                        f"this is an IMPORT lag, not an intracandle move")
                continue
            drift = (spot - ref) / ref * 100
            if abs(drift) < threshold or _drift_alerted.get(sym) == bucket:
                continue
            _drift_alerted[sym] = bucket
            arrow = "▲" if drift > 0 else "▼"
            title = f"⚠ FAST MOVE — {sym} {arrow} {drift:+.2f}% intracandle"
            msg = (f"last {spot:,.2f} vs last closed 15m {ref:,.2f} · engines "
                   f"see it at next candle close")
            log.warning(f"DRIFT ALERT {title}")
            if dry:
                print(f"[DRY] {title} | {msg}")
                continue
            store.insert_fact(con, symbol=sym, tf="15m", kind="alert",
                              market_time=now, confirmed_at=now,
                              algo_version=DRIFT_VERSION,
                              payload={"event": "PRICE_DRIFT", "spot": str(spot),
                                       "ref_close": str(ref),
                                       "ref_age_s": ref_age,
                                       "drift_pct": f"{drift:.2f}"})
            con.commit()
            # QUIET. Drift runs 13-44 a day against 2-8 setup announcements,
            # lands in every hour including overnight, and the code around it
            # describes it as awareness rather than something to act on. Same
            # channel as a fired setup and the three that matter are buried
            # under thirty that do not. Keyed per symbol per day so a repeated
            # reading of the same drift does not re-buzz.
            notify.enqueue(
                f"drift|{sym}|{time.strftime('%Y-%m-%d', time.gmtime(now))}",
                title, msg, notify.QUIET)
        except Exception as e:
            log.warning(f"drift check failed for {sym}: {e}")


def cycle(con, log, beat=None) -> tuple[int, list]:
    """Run one scan pass.

    `beat` is an optional progress callback invoked at each stage. A heartbeat
    written only after the cycle RETURNS cannot distinguish "busy" from "hung"
    for the whole duration of the cycle — and a full pass measures ~250s
    against a 150s liveness threshold, so healthy runs reported SCANNER DOWN.
    Beating during the work lets the threshold stay short enough to mean
    something.
    """
    def _beat(phase):
        if beat:
            beat(phase)

    now = int(time.time())
    new_candles = 0
    # SCAN covers traded + shadow symbols; only the traded ones can reach the
    # risk authority. `admitted_at` gates every sizing decision on ADMITTED
    # membership, so a SHADOW venue accumulates candles, facts and even setups
    # without a dollar of paper risk touching it. Using `current_symbols` here
    # would leave Kraken cold and defeat the whole point of warming it.
    scan = universe.scan_symbols(con)
    for i, sym in enumerate(scan, 1):
        _beat(f"import {sym} ({i}/{len(scan)})")
        # One symbol's transient venue error must not abort the scan. A single
        # HTTP 429 killed an entire cycle on 2026-07-29 — every other symbol
        # went unscanned because one call failed. Skip it and carry on; the next
        # cycle retries it, and any resulting gap is recorded honestly.
        try:
            for tf, gran in importer.native_tfs(sym).items():
                last = con.execute(
                    "SELECT MAX(open_ts) FROM candles WHERE symbol=? AND tf=? "
                    "AND source NOT LIKE 'agg:%'", (sym, tf)).fetchone()[0]
                closed_until = now - now % gran
                # A cold symbol has no MAX(open_ts). Falling back to 0 asked the
                # venue for history from 1970 and imported nothing while logging
                # ~2M fabricated gaps per cycle — see ingest.history_floor.
                start = (last + gran) if last else ingest.history_floor(tf, now)
                if start < closed_until:
                    r = importer.backfill(con, sym, tf, start, now)
                    new_candles += r["candles"]
                    if r["gaps"]:
                        log.warning(f"live import {sym} {tf}: {r['gaps']} gaps")
        except Exception as exc:
            log.warning(f"import skipped {sym}: {type(exc).__name__} {exc}")
            continue

    # ── The operator's open trades, WHEREVER they are ─────────────────────
    # Everything above is scoped to the scan universe, and so was every
    # resolution pass — which meant an intent armed on any of the ~58
    # chartable-but-unscanned symbols was checked exactly once, at arm time,
    # and then sat ARMED forever: a trade the operator placed and could never
    # see settle. Manual work is now discovered from the intents themselves,
    # and for an off-watchlist symbol this block does the lifecycle the scan
    # loop does for its own — fresh candles, higher-timeframe roll-up, resolve.
    # It sits BEFORE the no-new-candles early return, which only knows whether
    # the WATCHLIST had new candles.
    try:
        from engine import manual
        for (m_sym, m_tf), _intents in sorted(manual.unresolved(con).items()):
            _beat(f"manual {m_sym}")
            try:
                if m_sym not in scan:
                    for tf, gran in importer.native_tfs(m_sym).items():
                        last = con.execute(
                            "SELECT MAX(open_ts) FROM candles WHERE symbol=? "
                            "AND tf=? AND source NOT LIKE 'agg:%'",
                            (m_sym, tf)).fetchone()[0]
                        closed_until = now - now % gran
                        # No history floor here: an intent can only exist on a
                        # symbol that already has candles, so `last` is real.
                        start = (last + gran) if last else None
                        if start and start < closed_until:
                            importer.backfill(con, m_sym, tf, start, now)
                    for tf in ("4H", "1W"):
                        aggregator.aggregate(con, m_sym, tf)
                manual.run(con, m_sym, m_tf, importer.TF_SECONDS[m_tf])
            except Exception as exc:
                # One symbol's venue hiccup must not strand the others' trades.
                log.warning(f"manual resolve skipped {m_sym} {m_tf}: "
                            f"{type(exc).__name__} {exc}")
    except Exception as exc:
        log.warning(f"manual resolve pass failed: {type(exc).__name__} {exc}")

    if not new_candles:
        return 0, []

    before = con.execute("SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0]
    # Aggregate EVERY tracked symbol, not just the admitted scan set. When a
    # symbol drops out of the universe mid-session its final higher-timeframe
    # buckets would otherwise never be rolled up — leaving complete 1H data with
    # no 4H candle, which the audit correctly reports as a permanent blocker
    # (ONDO-USD, 2026-07-26). Aggregation is a cheap roll-up of candles we
    # already hold; engines and scanning stay scoped to the admitted set.
    tracked = universe.all_tracked_symbols(con)
    for i, sym in enumerate(tracked, 1):
        _beat(f"aggregate {sym} ({i}/{len(tracked)})")
        for tf in ("4H", "1W"):
            aggregator.aggregate(con, sym, tf)
    # The engine loop lives in `pipeline.run_symbol` — ONE loop, shared with
    # `ingest.run_engines`, exactly as the roster already is. This block used
    # to carry its own copy with two behaviours the other loop lacked (the
    # per-engine guard and the per-symbol quality gate), which is the same
    # silent-drift disease the shared roster was built to end. What stays HERE
    # is policy: a blocked symbol must still be skipped — that is the audit
    # gate doing its job, and it stays loud — it just cannot take the other 74
    # symbols and the risk authority down with it, as it did for 364 of 948
    # cycles (EUL-USD: SEQUENCE_GAPS).
    blocked_syms = []
    for i, sym in enumerate(scan, 1):
        _beat(f"engines {sym} ({i}/{len(scan)})")
        r = pipeline.run_symbol(con, sym, now=now, log=log)
        if r["blocked"]:
            blocked_syms.append(f"{sym} ({r['blocked']})")
    if blocked_syms:
        log.warning(f"market-data quality blocked {len(blocked_syms)}/{len(scan)} "
                    f"symbols this cycle (engines skipped, rest of the scan "
                    f"continued): {'; '.join(blocked_syms[:4])}")

    _beat("risk")
    risk.run(con)
    _beat("autonomous intents")
    try:
        execution.monitor_paper(con)
        private_broker = None
        active_mode = automation.current(con)[0]
        custody_environments = positions.private_environments_with_exposure(con)
        if len(custody_environments) > 1:
            raise RuntimeError("simultaneous testnet and mainnet custody is forbidden")
        custody_mode = (automation.AutomationMode.TESTNET
                        if custody_environments == {"testnet"} else
                        automation.AutomationMode.LIVE
                        if custody_environments == {"mainnet"} else active_mode)
        if custody_mode in (automation.AutomationMode.TESTNET,
                            automation.AutomationMode.LIVE):
            private_broker = broker_factory.phemex_for_mode(custody_mode)
            private_broker.sync_time()
            # These returns were discarded, which made every refusal in the
            # private path silent — the one property a degraded path is not
            # allowed to have. Non-empty counts get one aggregate line here;
            # the per-intent detail is logged inside each monitor.
            _mon = execution.monitor_private(con, private_broker)
            from engine import lifecycle
            _lc = lifecycle.monitor(con, private_broker)
            _cl = positions.monitor_closures(con, private_broker)
            _stuck = {"unresolved": len(_mon.get("refused") or ()),
                      "blocked": len(_lc.get("blocked") or ()),
                      "pending_confirmation": len(_cl.get("pending_confirmation") or ())}
            if any(_stuck.values()):
                log.warning(f"private path degraded this cycle: {_stuck}")
            reconciliation = positions.reconcile(
                con, private_broker, symbols=universe.all_tracked_symbols(con))
            if not reconciliation["matched"]:
                log.error("private custody reconciliation blocked new entries: "
                          + json.dumps(reconciliation, sort_keys=True))
        routed = autotrader.run(con, broker=private_broker)
        if routed["routed"] or routed["refused"]:
            # AUTOTRADER is an evidence prefix (runlog.AUDIT_PREFIXES): this
            # line is the system's own record of sending orders to a venue,
            # and for a while it was the ONLY trace at any level — INFO,
            # unmatched by any prefix, discarded on the first log rotation.
            log.info(f"AUTOTRADER {routed['mode']}: {len(routed['routed'])} routed, "
                     f"{len(routed['refused'])} refused")
    except Exception as exc:
        # Fail closed without taking the data and paper research loop down.
        # A private execution fault is operational state to fix, never a reason
        # to stop recording the market.
        log.error(f"autotrader failed closed: {type(exc).__name__}: {exc}")
    _beat("audit")
    quality.audit(con, now=now, persist=True)

    # A notification claims something is actionable NOW. A new fact ROW is not
    # that claim: onboarding a symbol backfills years of candles, the engines
    # re-derive the setups those years contained, and every one arrives as a
    # brand-new row. Announcing on row-newness toasted 87 historical setups in
    # a single cycle (2026-07-29), the most recent of them dated 2025-01.
    # Two gates, both already the house rule elsewhere:
    #   · inside the active forward window — the same baseline filter every
    #     /api surface uses to decide what is visible
    #   · at most ANNOUNCE_MAX_BARS late for its OWN timeframe — a 1D setup
    #     confirmed three months ago is history no matter which window it is in
    baseline_start = store.get_active_baseline(con)["started_at"]
    fired = announceable(con, before, now, baseline_start, log)
    return new_candles, fired


def announceable(con, before: int, now: int, baseline_start: int, log=None):
    """Which new setup facts deserve to interrupt the operator. THE filter.

    Extracted from `cycle()` because its only test re-implemented it inline,
    which is how the defect below survived: a test that mirrors the code cannot
    fail when the code needs a rule the mirror does not have. `test_
    notifications.py` now drives this function, so the copy is gone.

    FOUR GATES, and the first one was missing entirely until 2026-08-05:

      · WHICH ENGINE. Only versions in `execsim.plan_versions()` — the setups
        the book actually trades. The query is `kind='setup'` and every engine
        that writes one landed in it, including the two that are MEASURED AND
        NOT ENABLED. The operator was toasted 17 times to take
        TREND_CONTINUATION trades: a playbook whose own grade is -0.1500 R over
        2,816 trades with the interval ENTIRELY below zero. `trend.py` says in
        its first line that it trades nothing; the alert path had never been
        told. An engine can be worth running and not worth trading, and the
        notifier is the one surface where that distinction is the whole point.
      · STATE — FORMING or VALIDATED, not every lifecycle row.
      · INSIDE THE BASELINE — onboarding a symbol backfills years of candles
        and the engines re-derive every setup those years contained; 87 of them
        toasted in one cycle on 2026-07-29, newest dated 2025-01.
      · NOT TOO LATE for its own timeframe.

    Suppression is never silent: every drop is counted and logged, so the
    operator can tell a quiet market from a notifier that swallowed everything.
    """
    from engine.execsim import plan_versions
    traded = set(plan_versions())
    fired, historical, stale, not_traded = [], 0, 0, 0
    for sym_, tf_, conf_, ver_, pl in con.execute(
            "SELECT symbol, tf, confirmed_at, algo_version, payload FROM facts "
            "WHERE id>? AND kind='setup'", (before,)).fetchall():
        p = json.loads(pl)
        if p["state"] not in ANNOUNCE_STATES:
            continue
        if ver_ not in traded:
            not_traded += 1
            continue
        if conf_ < baseline_start:
            historical += 1
            continue
        if now - conf_ > ANNOUNCE_MAX_BARS * importer.TF_SECONDS[tf_]:
            stale += 1
            continue
        fired.append((sym_, tf_, p))
    if log and (historical or stale or not_traded):
        log.info(f"announce filter: {len(fired)} live, {not_traded} from "
                 f"not-enabled engines, {historical} pre-baseline, {stale} too "
                 f"old to be actionable (all still recorded as facts)")
    return fired


def announce(sym: str, tf: str, p: dict, log):
    if p["state"] == "FORMING":
        title = f"👁 FORMING — {sym} {tf} {p['strategy']} {p['direction']}"
        msg = (f"price {p.get('distance_atr', '?')} ATR from zone · would be "
               f"entry {float(p['entry']):,.2f} / R:R {p['rr']} · watching")
    else:
        title = f"◉ {p['strategy']} {p['direction']} — {sym} {tf} · R {p['rank']}"
        msg = (f"entry {float(p['entry']):,.2f} · TP {float(p['tp']):,.2f} · "
               f"SL {float(p['sl']):,.2f} · R:R {p['rr']}")
    log.info(f"SETUP FIRED {title} | {msg}")
    # ENQUEUED, NOT SENT. The filtering above is what makes this alert worth
    # trusting — the baseline window and the how-late-is-too-late gate — so the
    # decision has to be made here, in the scanner. The DELIVERY must not be:
    # notification work from this loop is what killed the scanner, 254s to
    # death against 1055s and 13 clean cycles with it off, and that is why the
    # supervisor still starts this process with toasts disabled.
    #
    # enqueue() writes one row to a small local SQLite file and returns. No
    # socket, no subprocess — neither of the two things that have ever taken
    # this loop down. The watchdog drains the queue on its own tick.
    #
    # The key is the setup's own id plus its state, so the same setup moving
    # FORMING -> VALIDATED still announces once for each, and a re-derivation
    # of either announces neither.
    if not notify.enqueue(f"setup|{p.get('setup_id') or (sym + '|' + tf)}|{p['state']}",
                          title, msg, notify.LOUD):
        log.info(f"already announced, not re-queued: {title}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    log = get_logger()
    install_exit_forensics()
    con = store.connect()
    _exit_note("START", f"once={args.once}")
    log.info(f"live loop start (once={args.once}) poll={POLL_SECONDS}s")
    hb_path = Path(__file__).resolve().parent / "data" / "heartbeat.json"
    n_cycles = 0
    state = {"cycles": 0, "last_new_candles": 0, "last_new_setups": 0}

    def write_hb(phase):
        """Heartbeat EVERY step, not just every poll — the UI light trusts this."""
        try:
            hb_path.write_text(json.dumps(
                {"ts": int(time.time()), "pid": os.getpid(), "phase": phase, **state}))
        except Exception as hb_err:
            log.warning(f"heartbeat write failed: {hb_err}")

    while True:
        t0 = time.monotonic()
        try:
            write_hb("universe")
            refresh_universe(con, log, beat=write_hb)   # hourly (self-throttled)
            write_hb("drift")
            check_drift(con, log)        # runs every poll, even quiet ones
            # How far past the candle boundary this pass BEGAN. With aligned
            # wakeups this should read ~{CANDLE_FINALIZATION_S}s on the passes
            # that import; a persistently larger figure means the venue
            # finalizes slower than the buffer and the number to tune is
            # CANDLE_FINALIZATION_S — measured from production logs, the same
            # way the prior project arrived at its 5s.
            boundary_lag = time.time() % CANDLE_GRID_S
            n, fired = cycle(con, log, beat=write_hb)
            n_cycles += 1
            state.update(cycles=n_cycles, last_new_candles=n,
                         last_new_setups=len(fired))
            write_hb("idle")
            if n:
                stamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
                log.info(f"cycle {stamp}Z: {n} new candles, {len(fired)} new setups "
                         f"({time.monotonic()-t0:.1f}s, began boundary+{boundary_lag:.0f}s)")
            for sym, tf, p in fired:
                announce(sym, tf, p, log)
            # Housekeeping at the ONE moment this process is not mid-read. A
            # checkpoint cannot reset the log while a reader holds a snapshot,
            # and this loop holds one for most of a ~300s cycle; here, between
            # cycles, is the only place it can land cleanly.
            # BREADCRUMBS ACROSS THE GAP BETWEEN CYCLES.
            #
            # 356 exits, rc=1, never through Python — no atexit, no signal, no
            # faulthandler dump across 178 starts. Until stderr was unbuffered
            # the last line was whatever happened to be flushed, so every run
            # looked as though it stopped at startup. Unbuffered, the picture
            # changed: the scanner completes its cycles and dies in the quiet
            # afterwards.
            #
            # This is the only stretch of that quiet with any work in it — a
            # WAL checkpoint against a 2.6GB store — and it was invisible
            # unless it moved frames. Each step now says it happened, so the
            # next exit lands between two known points instead of somewhere in
            # a five-minute silence.
            log.info("cycle done — checkpointing WAL")
            ck = store.checkpoint_wal(con, log)
            log.info(f"WAL checkpoint returned busy={ck.get('busy')} "
                     f"{ck.get('checkpointed')}/{ck.get('frames')} frames")
        except Exception as e:
            log.error(f"live cycle failed: {e}")
        if args.once:
            break
        # Aligned, not blind: the nap ends at the drift heartbeat or just past
        # the next candle boundary, whichever is sooner — see next_wake.
        nap = next_wake(time.time())
        log.info(f"sleeping {nap:.1f}s until the next wake")
        time.sleep(nap)
        log.info("awake")
    con.close()


if __name__ == "__main__":
    main()
