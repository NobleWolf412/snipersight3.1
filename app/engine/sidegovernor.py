"""Same-side session governor — what would N have refused? READ-ONLY.

`risk.py` v0.24 refuses an entry on a side once N entries on that side have
closed at a loss in the same UTC day (`settings.same_side_session_losses`).
This module replays that rule over the recorded book at several N so the
operator can see what the limit costs and saves BEFORE moving it. It writes
nothing and arms nothing; the live rule is `risk.run`, and this is the same
arithmetic run over the same exits.

WHY THE RULE EXISTS, measured 2026-09-03. Three REVERSAL shorts in one
afternoon into a +5% BTC day, each funded after the previous had stopped. The
daily loss halt sat 0.6R away. A governor keyed on the HTF ladder would have
refused nothing — the ladder read FLAT for the third short on a market up 7%
that day, the same lagging-label defect the direction-first rebuild exists to
fix — so this one is keyed on REALISED direction and nothing else: two losses
on a side in a session is the market saying which way it is going.

WHAT THIS CANNOT PROVE. The research book pools every symbol per day, so on
the research replay "two losing shorts today" is usually two DIFFERENT markets
— which is the intent (the tide, not the boat), but it means the count trips
far more often than the funded book, where one slot serialises the trades.
Both are reported. The split is in-sample by construction: the first
measurement was taken on the same book that motivated the rule. It is a
portfolio control shipped on the cooldown precedent ("a rule of thumb the
engine applies, not a proven improvement"), and the funnel sentence says so.

Usage (from app/):
  python -m engine.sidegovernor            # both books, N = 1..4
  python -m engine.sidegovernor --json
"""
import argparse
import datetime as _dt
import json
import sqlite3
from collections import defaultdict

from . import store
from .execsim import EXEC_VERSION


def _day(ts: int) -> str:
    return _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).strftime("%Y-%m-%d")


def refusals(rows: list[dict], n: int) -> list[dict]:
    """The rows the governor at `n` would have refused. Pure, SEQUENTIAL.

    `rows`: dicts with `entry_ts` (the setup's confirmed_at — the clock
    risk.run keys on), `exit_ts`, `direction`, `r` (float), sorted by
    entry_ts. Walked in order like the replay: a row is refused when, by its
    own entry time, `n` rows on the same side had already exited at a loss
    that UTC day; and a REFUSED row's loss never lands — it was never a
    position, so it cannot count toward the next refusal. The first version
    of this function counted every loss regardless and over-refused (audit
    2026-09-03, finding 1).
    """
    if n <= 0:
        return []
    losses: dict[tuple, list] = defaultdict(list)
    out = []
    for r in rows:
        k = (_day(r["entry_ts"]), r["direction"])
        if sum(1 for t in losses[k] if t <= r["entry_ts"]) >= n:
            out.append(r)
            continue
        if r["r"] < 0:
            losses[(_day(r["exit_ts"]), r["direction"])].append(r["exit_ts"])
    return out


def load(con, *, funded_only: bool = False) -> list[dict]:
    """Closed trades at the current exec version, oldest first.

    `entry_ts` is the SETUP's confirmed_at — what risk.run keys the intent's
    day and its point-in-time cut on — not the fill bar, which is at least one
    bar later and can cross midnight. `exit_ts` is the exec fact's
    confirmed_at, the moment the loss became knowable.
    """
    from . import factorstats
    baseline = store.get_active_baseline(con)
    approved = set()
    if funded_only:
        for (p,) in con.execute(
                "SELECT payload FROM facts WHERE kind='risk' AND confirmed_at>=?",
                (baseline["started_at"],)):
            d = json.loads(p)
            if d.get("event") == "DECISION" and d.get("decision") in ("APPROVED", "REDUCED"):
                approved.add(d["setup_id"])
    exit_at: dict = {}
    for ct, p in con.execute(
            "SELECT confirmed_at, payload FROM facts WHERE kind='exec' AND algo_version=?",
            (EXEC_VERSION,)):
        d = json.loads(p)
        if d.get("outcome") != "MISSED":
            exit_at[d["setup_id"]] = int(ct)
    candidates, _ = factorstats.load_candidates(con, exec_version=EXEC_VERSION)
    rows = []
    for c in candidates:
        if c.get("r") is None or c["setup_id"] not in exit_at:
            continue
        if funded_only and (c["setup_id"] not in approved
                            or c["confirmed_at"] < baseline["started_at"]):
            continue
        if "|ADD" in c["setup_id"]:
            continue                      # an add is not a position (risk.py)
        rows.append({"symbol": c["symbol"], "tf": c["tf"], "setup_id": c["setup_id"],
                     "entry_ts": int(c["confirmed_at"]), "exit_ts": exit_at[c["setup_id"]],
                     "direction": c["payload"]["direction"], "r": float(c["r"])})
    rows.sort(key=lambda r: (r["entry_ts"], r["setup_id"]))
    return rows


def grade(con, ns=(1, 2, 3, 4)) -> dict:
    out = {"exec_version": EXEC_VERSION, "books": {}}
    for name, rows in (("research", load(con)), ("funded", load(con, funded_only=True))):
        book = {"n": len(rows), "sum_r": round(sum(r["r"] for r in rows), 2), "at": {}}
        for n in ns:
            ref = refusals(rows, n)
            rs = [r["r"] for r in ref]
            book["at"][n] = {
                "refused": len(ref),
                "refused_pct": round(100 * len(ref) / len(rows), 1) if rows else None,
                "refused_sum_r": round(sum(rs), 2),
                "refused_mean_r": round(sum(rs) / len(rs), 3) if rs else None,
                "book_after_r": round(sum(r["r"] for r in rows) - sum(rs), 2),
                "refused": [{k: v for k, v in r.items()} for r in ref] if name == "funded" else len(ref),
            }
        out["books"][name] = book
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rep = grade(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    print(f"same-side session governor — replay at {rep['exec_version']} (writes nothing)")
    for name, book in rep["books"].items():
        print(f"\n{name} book: n={book['n']} sumR={book['sum_r']:+.1f}")
        for n, c in book["at"].items():
            refused = c["refused"] if isinstance(c["refused"], int) else len(c["refused"])
            print(f"  N={n}: refuses {refused:4d} ({c['refused_pct']}%)  their R sum={c['refused_sum_r']:+.1f}"
                  f" mean={c['refused_mean_r'] if c['refused_mean_r'] is not None else '—'}"
                  f"  book after={c['book_after_r']:+.1f}R")
            if name == "funded":
                for r in c["refused"]:
                    print(f"        {_day(r['entry_ts'])} {r['symbol']:10s} {r['tf']:3s} {r['direction']:5s} R={r['r']:+.2f}")
    print("\nNOT A VERDICT. In-sample, pooled across symbols on the research book; "
          "shipped as a portfolio control on the cooldown precedent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
