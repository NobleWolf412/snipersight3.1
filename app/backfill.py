"""One-command backfill + aggregate + swing run for BTC-USD and ETH-USD.

Usage: python backfill.py [--days-5m 30] [--days-15m 30] [--days-1h 180] [--since-1d 2022-01-01]
Idempotent: safe to re-run; facts are append-only, candles keyed by open_ts.
"""
import argparse
import time
from datetime import datetime, timezone

from engine import store, importer, aggregator, risk, quality, pipeline

# One roster, declared in `engine/pipeline.py`. Names are derived from the
# modules rather than typed beside them, so a label can no longer disagree with
# the engine it labels.
ENGINES = list(zip(pipeline.names(), pipeline.PER_SYMBOL))

SYMBOLS = ["BTC-USD", "ETH-USD"]
TF_SECONDS = importer.TF_SECONDS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-5m", type=int, default=30)
    ap.add_argument("--days-15m", type=int, default=30)
    ap.add_argument("--days-1h", type=int, default=180)
    ap.add_argument("--since-1d", default="2022-01-01")
    args = ap.parse_args()

    now = int(time.time())
    since_1d = int(datetime.strptime(args.since_1d, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp())
    plan = [("1D", since_1d), ("1H", now - args.days_1h * 86400),
            ("5m", now - args.days_5m * 86400),
            ("15m", now - args.days_15m * 86400)]

    con = store.connect()
    for symbol in SYMBOLS:
        for tf, start in plan:
            r = importer.backfill(con, symbol, tf, start, now)
            print(f"import  {r['symbol']:8s} {r['tf']:3s} candles={r['candles']:6d} gaps={r['gaps']}")
        for tf in ("4H", "1W"):
            r = aggregator.aggregate(con, symbol, tf)
            print(f"agg     {r['symbol']:8s} {r['tf']:3s} candles={r['candles']:6d} skipped={r['skipped_incomplete']}")
        quality.assert_market_ready(con, symbol, now)
        for name, mod in ENGINES:
            for tf in pipeline.ALL_TFS:
                r = mod.run(con, symbol, tf, TF_SECONDS[tf])
                counts = " ".join(f"{k}+{v}" for k, v in r.items()
                                  if k not in ("symbol", "tf"))
                print(f"{name:9s} {r['symbol']:8s} {r['tf']:3s} {counts}")
    risk.run(con)
    # This command is an offline repair/analysis tool, not the live scanner.
    # Its local report must not replace the durable verdict shown to operators.
    report = quality.audit(con, now=now)
    print(f"quality   {report['status']} blockers={len(report['blockers'])} "
          f"warnings={len(report['warnings'])} evaluation_allowed={report['evaluation_allowed']}")
    con.close()


if __name__ == "__main__":
    main()
