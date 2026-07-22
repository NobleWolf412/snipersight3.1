"""M4 validation harness — §15 performance report over exec facts (net of costs).

Honest-scope note: our rules were drafted with knowledge of this whole window
(user golden data spans 2022-2026), so nothing here is true out-of-sample.
This report measures ROBUSTNESS (cohort stability, tail dependence, drawdown),
not proof of edge. True OOS = forward paper trading from today.
Usage: python validate.py  -> verification/validation-002.md + console summary
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from engine import store, execsim

OUT = Path(__file__).resolve().parent / "verification" / "validation-002.md"
SYMBOLS = ("BTC-USD", "ETH-USD")
TFS = ("15m", "1H", "4H", "1D")


def load(con):
    trades = []
    for sym in SYMBOLS:
        for tf in TFS:
            for r in store.get_facts(con, sym, tf, "exec", execsim.EXEC_VERSION):
                p = json.loads(r["payload"])
                trades.append({"symbol": sym, "tf": tf, "ts": r["market_time"],
                               "year": datetime.fromtimestamp(r["market_time"], tz=timezone.utc).year,
                               "net": float(p["r_multiple"]), "gross": float(p["r_gross"]),
                               "strategy": p["strategy"], "outcome": p["outcome"]})
    trades.sort(key=lambda t: t["ts"])
    return trades


def stats(rows):
    if not rows:
        return None
    rs = [t["net"] for t in rows]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    pf = round(sum(wins) / abs(sum(losses)), 2) if losses and wins else None
    # equity curve in R, max drawdown, longest underwater run (in trades)
    eq = peak = 0.0
    maxdd = 0.0
    under = longest_under = 0
    for r in rs:
        eq += r
        if eq >= peak:
            peak = eq
            under = 0
        else:
            under += 1
            longest_under = max(longest_under, under)
            maxdd = max(maxdd, peak - eq)
    return {"n": len(rs), "win%": round(100 * len(wins) / len(rs)),
            "pf": pf, "sumR": round(sum(rs), 1),
            "avgR": round(sum(rs) / len(rs), 2),
            "maxDD_R": round(maxdd, 1), "underwater": longest_under}


def fmt(label, s):
    if s is None:
        return f"| {label} | — | — | — | — | — | — | — |"
    return (f"| {label} | {s['n']} | {s['win%']}% | {s['pf'] if s['pf'] is not None else '—'} | "
            f"{s['sumR']:+} | {s['avgR']:+} | {s['maxDD_R']} | {s['underwater']} |")


HDR = ("| Cohort | n | Win% | PF | ΣR | avg R | maxDD (R) | underwater |\n"
       "|---|---|---|---|---|---|---|---|")


def main():
    con = store.connect()
    trades = load(con)
    lines = [f"# Validation Report 001 — {execsim.EXEC_VERSION}, net of costs",
             "", f"Trades: {len(trades)} · fees 0.25%/side · slippage 0.05 ATR on market exits",
             "", "**Scope caveat: rules were calibrated with hindsight over this window — "
             "this measures robustness, not out-of-sample edge. True OOS starts with "
             "forward paper trading.**", ""]

    for strat in ("REVERSAL", "PULLBACK"):
        sub = [t for t in trades if t["strategy"] == strat]
        lines += [f"## {strat}", "", HDR, fmt("ALL (net)", stats(sub))]
        gross_stats = stats([{**t, "net": t["gross"]} for t in sub])
        lines.append(fmt("ALL (gross)", gross_stats))
        for sym in SYMBOLS:
            lines.append(fmt(sym, stats([t for t in sub if t["symbol"] == sym])))
        for tf in TFS:
            lines.append(fmt(tf, stats([t for t in sub if t["tf"] == tf])))
        years = sorted({t["year"] for t in sub})
        for y in years:
            lines.append(fmt(str(y), stats([t for t in sub if t["year"] == y])))
        # tail dependence: strip top winners
        srt = sorted(sub, key=lambda t: t["net"], reverse=True)
        for k in (1, 3, 5):
            lines.append(fmt(f"minus top {k}", stats(srt[k:])))
        lines.append("")

    txt = "\n".join(lines) + "\n"
    OUT.write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
