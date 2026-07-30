"""Forward paper loop — the scanner running live.

Every POLL_SECONDS: import newly CLOSED candles (never developing ones, §5),
re-aggregate 4H/1W, re-run every engine (all idempotent/append-only — a cycle
with no new data writes zero facts), then notify on any NEW validated setup.
This is the start of the forward paper track record (§15: paper results are
their own category — nothing here was knowable to the calibration).

Usage:
  python live.py           # run forever, poll every 60s
  python live.py --once    # single cycle (testing / task scheduler)
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import notify
from engine import (store, importer, aggregator, swings, structure, zones,
                    liquidity, regime, setups, execsim, risk, scalein, cycles,
                    universe, ingest, quality, marketdata)
from engine.runlog import get_logger

NATIVE_TFS = ("15m", "1H", "1D")
_last_universe_refresh = 0.0
ALL_TFS = ("15m", "1H", "4H", "1D", "1W")
ENGINES = (swings, structure, zones, liquidity, regime, setups, execsim,
           scalein, execsim,  # execsim runs again after scalein to fill adds
           cycles)            # observational satellite — BTC 1D only, no consumers
POLL_SECONDS = 60

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
    if time.monotonic() - _last_universe_refresh < universe.REFRESH_SECONDS:
        return
    _last_universe_refresh = time.monotonic()
    # the ranking sweep is a ~40s blocking call — beat inside it, not around it
    prog = (lambda d, t: beat(f"universe {d}/{t}")) if beat else None
    r = universe.refresh(con, progress=prog)
    if r["source"] == "unavailable":
        log.warning("universe refresh: rank source unavailable — unchanged")
        return
    for sym in r["warming"]:
        try:
            res = ingest.onboard(con, sym)
            log.info(f"UNIVERSE onboarded {sym}: {res['candles'].get('1D',0)} daily candles")
            notify.toast("＋ New symbol added", f"{sym} joined the scan universe")
        except Exception as e:
            log.warning(f"onboard failed for {sym}: {e}")
    if r["warming"]:
        universe.refresh(con)          # re-classify: warmed symbols -> admitted


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
            if not notify.toast(title, msg):
                log.warning("TOAST DELIVERY FAILED for drift alert")
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
    scan = universe.current_symbols(con)
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
                    "AND source NOT LIKE 'agg:%'", (sym, tf)).fetchone()[0] or 0
                closed_until = now - now % gran
                if last + gran < closed_until:
                    r = importer.backfill(con, sym, tf, last + gran, now)
                    new_candles += r["candles"]
                    if r["gaps"]:
                        log.warning(f"live import {sym} {tf}: {r['gaps']} gaps")
        except Exception as exc:
            log.warning(f"import skipped {sym}: {type(exc).__name__} {exc}")
            continue
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
    for i, sym in enumerate(scan, 1):
        _beat(f"engines {sym} ({i}/{len(scan)})")
        quality.assert_market_ready(con, sym, now)
        for mod in ENGINES:
            for tf in ALL_TFS:
                mod.run(con, sym, tf, importer.TF_SECONDS[tf])

    _beat("risk")
    risk.run(con)
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
    fired, historical, stale = [], 0, 0
    for sym_, tf_, conf_, pl in con.execute(
            "SELECT symbol, tf, confirmed_at, payload FROM facts "
            "WHERE id>? AND kind='setup'", (before,)).fetchall():
        p = json.loads(pl)
        if p["state"] not in ANNOUNCE_STATES:
            continue
        if conf_ < baseline_start:
            historical += 1
            continue
        if now - conf_ > ANNOUNCE_MAX_BARS * importer.TF_SECONDS[tf_]:
            stale += 1
            continue
        fired.append((sym_, tf_, p))
    # Suppression is never silent: the operator must be able to tell "quiet
    # market" from "the notifier swallowed everything".
    if historical or stale:
        log.info(f"announce filter: {len(fired)} live, {historical} pre-baseline, "
                 f"{stale} too old to be actionable (all still recorded as facts)")
    return new_candles, fired


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
    if not notify.toast(title, msg):
        # loud-fallback rule: a degraded path must never degrade silently
        log.warning(f"TOAST DELIVERY FAILED for {title} — signal exists only "
                    f"in this log and the UI feed; check notification settings")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    log = get_logger()
    con = store.connect()
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
            n, fired = cycle(con, log, beat=write_hb)
            n_cycles += 1
            state.update(cycles=n_cycles, last_new_candles=n,
                         last_new_setups=len(fired))
            write_hb("idle")
            if n:
                stamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
                log.info(f"cycle {stamp}Z: {n} new candles, {len(fired)} new setups "
                         f"({time.monotonic()-t0:.1f}s)")
            for sym, tf, p in fired:
                announce(sym, tf, p, log)
        except Exception as e:
            log.error(f"live cycle failed: {e}")
        if args.once:
            break
        time.sleep(POLL_SECONDS)
    con.close()


if __name__ == "__main__":
    main()
