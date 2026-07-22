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
                    universe, ingest)
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
# live spot vs the last CLOSED 15m candle and ALERTS on violent intracandle
# moves — awareness only, never analysis on unclosed data. One alert per
# symbol per 15m bucket.
DRIFT_VERSION = "drift-v0.1-draft"
DRIFT_ALERT_PCT = 3.0
_drift_alerted: dict = {}


def _spot(symbol: str):
    import urllib.request
    req = urllib.request.Request(
        f"https://api.exchange.coinbase.com/products/{symbol}/ticker",
        headers={"User-Agent": "snipersight/0.1"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return float(json.loads(r.read().decode())["price"])


def refresh_universe(con, log):
    """Hourly: re-rank live, onboard newly-admitted symbols (backfill+engines)."""
    global _last_universe_refresh
    if time.monotonic() - _last_universe_refresh < universe.REFRESH_SECONDS:
        return
    _last_universe_refresh = time.monotonic()
    r = universe.refresh(con)
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
    bucket = now - now % 900
    for sym in universe.current_symbols(con):
        try:
            spot = _spot(sym)
            row = con.execute(
                "SELECT close FROM candles WHERE symbol=? AND tf='15m' "
                "ORDER BY open_ts DESC LIMIT 1", (sym,)).fetchone()
            if not row:
                continue
            ref = float(row[0])
            drift = (spot - ref) / ref * 100
            if abs(drift) < threshold or _drift_alerted.get(sym) == bucket:
                continue
            _drift_alerted[sym] = bucket
            arrow = "▲" if drift > 0 else "▼"
            title = f"⚠ FAST MOVE — {sym} {arrow} {drift:+.2f}% intracandle"
            msg = (f"spot {spot:,.2f} vs last closed 15m {ref:,.2f} · engines "
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
                                       "drift_pct": f"{drift:.2f}"})
            con.commit()
            if not notify.toast(title, msg):
                log.warning("TOAST DELIVERY FAILED for drift alert")
        except Exception as e:
            log.warning(f"drift check failed for {sym}: {e}")


def cycle(con, log) -> tuple[int, list]:
    now = int(time.time())
    new_candles = 0
    scan = universe.current_symbols(con)
    for sym in scan:
        for tf in NATIVE_TFS:
            gran = importer.NATIVE_TFS[tf]
            last = con.execute(
                "SELECT MAX(open_ts) FROM candles WHERE symbol=? AND tf=? AND source='coinbase'",
                (sym, tf)).fetchone()[0] or 0
            closed_until = now - now % gran
            if last + gran < closed_until:
                r = importer.backfill(con, sym, tf, last + gran, now)
                new_candles += r["candles"]
                if r["gaps"]:
                    log.warning(f"live import {sym} {tf}: {r['gaps']} gaps")
    if not new_candles:
        return 0, []

    before = con.execute("SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0]
    for sym in scan:
        for tf in ("4H", "1W"):
            aggregator.aggregate(con, sym, tf)
        for mod in ENGINES:
            for tf in ALL_TFS:
                mod.run(con, sym, tf, importer.TF_SECONDS[tf])

    risk.run(con)

    fired = []
    for sym_, tf_, pl in con.execute(
            "SELECT symbol, tf, payload FROM facts WHERE id>? AND kind='setup'",
            (before,)).fetchall():
        p = json.loads(pl)
        if p["state"] in ("VALIDATED", "FORMING"):
            fired.append((sym_, tf_, p))
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
    while True:
        t0 = time.monotonic()
        try:
            refresh_universe(con, log)   # hourly (self-throttled)
            check_drift(con, log)        # runs every poll, even quiet ones
            n, fired = cycle(con, log)
            n_cycles += 1
            try:  # heartbeat EVERY poll, quiet or not — the UI light trusts this
                hb_path.write_text(json.dumps(
                    {"ts": int(time.time()), "pid": os.getpid(), "cycles": n_cycles,
                     "last_new_candles": n, "last_new_setups": len(fired)}))
            except Exception as hb_err:
                log.warning(f"heartbeat write failed: {hb_err}")
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
