"""Chart read — the regime a trader SEES in the window a chart opens with.
A LIBRARY, not an engine: writes no facts, has no run(). READ-ONLY.

THE OPERATOR'S PICTURE, 2026-09-04, verbatim in substance: "I open the 4H
chart. It shows X candles. I can see all the highs and lows, draw the
support and resistance — that's sideways. If I can draw higher highs and
higher lows inside that window, that's a trend. Then I go up to the daily,
same window, further back, and if I'm in a bearish structure there and the
4H is trending up into daily resistance, that 4H trend is a pullback."

That is §26 of the constitution (multi-timeframe context as a trader reads
it), and it is not what `regime.py` computes. regime.py is the slow, audited
witness: a swing must HOLD for 90 bars before it counts, a trend needs break
+ HH + HL all confirmed, and the label is anchored to the last three
structural events whatever their age — so it lands 24-42 bars late and calls
a vertical rally TRANSITION for as long as no higher low prints. Right for a
fact store; wrong for "what is the chart doing now". This module is the fast
witness beside it: a FIXED window of closed bars, the swings visible inside
it, and the sequence they make. No memory of anything off-screen.

WHAT IT READS, per (symbol, timeframe, as_of), from closed candles only:

    read        UP / DOWN / RANGE / CHOP / UNKNOWN
                UP    the last two visible highs step up AND the last two
                      lows step up (HH + HL); DOWN mirrors (LH + LL)
                RANGE neither, and the last two highs sit within a level's
                      width of each other and the last two lows likewise —
                      equal highs over equal lows, two lines you could draw
                CHOP  neither a sequence nor two lines
    efficiency  Kaufman's ratio: net move / sum of moves over the window.
                Near 1 is a straight line, near 0 is noise. Evidence beside
                the read, never the read itself.
    levels      resistance = clustered visible swing highs (touch counts),
                support = clustered visible swing lows, plus the window's
                extreme high and low
    swings      the pivots the read was made from, so the call is auditable

And the top-down reconciliation the operator described, `call`:

    TREND_UP_ALIGNED / TREND_DOWN_ALIGNED   own read and the rung above agree
    PULLBACK_IN_HTF_DOWN / _UP              own trend AGAINST the rung above —
                                            expect it to end at the HTF level
    CONSOLIDATION_IN_HTF_UP / _DOWN         own RANGE/CHOP under an HTF trend —
                                            a break in the HTF direction wants
                                            the retest, not the breakout
    LTF_TREND_IN_HTF_RANGE                  own trend, rung above sideways
    RANGE / CHOP                            both sideways
    UNKNOWN                                 not enough bars

THE CONSTANTS ARE FIXED BEFORE THE FIRST GRADE and are the chart's own:
WINDOW_BARS is what chart.js opens with (pinned by a test), FRACTAL_WING is
the classic three-bar pivot, LEVEL_ATR is zones.ZONE_ATR so a "level" here is
a zone's width there. They are not tuned to this book; moving one is a
CHARTREAD_VERSION bump and a re-grade.

WHY THE WINDOW STOPS AT THE LAST CLOSED BAR AND WAITS FRACTAL_WING BARS. The
eye includes the forming candle and calls a high a high the moment it looks
like one; a fact store cannot. A pivot here is knowable only once
FRACTAL_WING bars have closed after it (rule 3), and the read at `as_of` is
the read a trader could have made at `as_of`, three bars slower than their
eye. That is the one place this picture and the constitution disagree.

NOTHING GATES ON THIS. It is stamped at analysis time by `annotate()` and
graded by `factorstats.outcome_split` (rule 7); the golden loop (§27) is how
the operator's own calls calibrate it before any playbook reads it.

Usage (from app/):
  python -m engine.chartread                       # grade against the book
  python -m engine.chartread --propose 20          # windows for you to label
  python -m engine.chartread --golden verification/golden-chart-reads.json
"""
import bisect
import json
import random
from decimal import Decimal

from . import store
from .swings import compute_atr
from .zones import ZONE_ATR

CHARTREAD_VERSION = "chartread-v0.1-draft"

#: Bars in the window — chart.js VISIBLE_BARS, what a chart opens showing.
WINDOW_BARS = 120
#: Bars each side that must be lower (higher) for a high (low) to be a pivot.
FRACTAL_WING = 3
#: Two swing highs (lows) within this many ATR of each other are one level.
LEVEL_ATR = ZONE_ATR
#: Fewer visible pivots than this and the window cannot be read.
MIN_PIVOTS = 4
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


def _d(v):
    return Decimal(str(v))


def pivots(candles, wing=FRACTAL_WING):
    """Fractal pivots in a list of closed bars, ALTERNATING high/low.

    A bar is a HIGH when its high is strictly above the `wing` bars either
    side; LOW mirrors. Consecutive same-type pivots collapse to the extreme
    (the higher high, the lower low), so the result reads H, L, H, L — the
    sequence a trader connects. Each pivot carries the bar index and the
    index at which it became KNOWABLE (i + wing).
    """
    out = []
    n = len(candles)
    hs = [_d(c["high"]) for c in candles]
    ls = [_d(c["low"]) for c in candles]
    for i in range(wing, n - wing):
        if all(hs[i] > hs[j] for j in range(i - wing, i + wing + 1) if j != i):
            out.append({"type": "HIGH", "i": i, "price": hs[i], "known_i": i + wing})
        if all(ls[i] < ls[j] for j in range(i - wing, i + wing + 1) if j != i):
            out.append({"type": "LOW", "i": i, "price": ls[i], "known_i": i + wing})
    out.sort(key=lambda p: (p["i"], p["type"]))
    merged = []
    for p in out:
        if merged and merged[-1]["type"] == p["type"]:
            keep = ((p["price"] > merged[-1]["price"]) if p["type"] == "HIGH"
                    else (p["price"] < merged[-1]["price"]))
            if keep:
                merged[-1] = p
            continue
        merged.append(p)
    return merged


def efficiency(closes) -> Decimal | None:
    if len(closes) < 2:
        return None
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k - 1]) for k in range(1, len(closes)))
    return (net / path).quantize(Q4) if path > 0 else Decimal(0)


def cluster_levels(prices, atr):
    """Group prices within LEVEL_ATR of each other into levels with touch counts."""
    if not prices or not atr:
        return []
    tol = LEVEL_ATR * atr
    levels = []
    for p in sorted(prices):
        if levels and p - levels[-1]["hi"] <= tol:
            levels[-1]["hi"] = p
            levels[-1]["touches"] += 1
            levels[-1]["members"].append(p)
        else:
            levels.append({"lo": p, "hi": p, "touches": 1, "members": [p]})
    for lv in levels:
        lv["price"] = (sum(lv["members"]) / len(lv["members"])).quantize(Q4)
        del lv["members"]
    return levels


def read_window(candles, atr_at_end) -> dict:
    """The read of ONE window of closed bars. Pure."""
    pv = pivots(candles)
    closes = [_d(c["close"]) for c in candles]
    er = efficiency(closes)
    highs = [p for p in pv if p["type"] == "HIGH"]
    lows = [p for p in pv if p["type"] == "LOW"]
    out = {"read": "UNKNOWN", "efficiency": None if er is None else str(er),
           "n_pivots": len(pv), "swings": [{"type": p["type"], "i": p["i"],
                                             "price": str(p["price"])} for p in pv[-6:]],
           "window_high": str(max(_d(c["high"]) for c in candles)) if candles else None,
           "window_low": str(min(_d(c["low"]) for c in candles)) if candles else None,
           "resistance": [], "support": [], "version": CHARTREAD_VERSION}
    if len(pv) < MIN_PIVOTS or len(highs) < 2 or len(lows) < 2:
        return out
    atr = atr_at_end
    out["resistance"] = [{"price": str(l["price"]), "touches": l["touches"]}
                         for l in cluster_levels([p["price"] for p in highs], atr)]
    out["support"] = [{"price": str(l["price"]), "touches": l["touches"]}
                      for l in cluster_levels([p["price"] for p in lows], atr)]
    h1, h2 = highs[-2]["price"], highs[-1]["price"]
    l1, l2 = lows[-2]["price"], lows[-1]["price"]
    if h2 > h1 and l2 > l1:
        out["read"] = "UP"
    elif h2 < h1 and l2 < l1:
        out["read"] = "DOWN"
    else:
        # RANGE is two lines you could draw through the RECENT pivots: the
        # last two highs within a level's width of each other and the last
        # two lows likewise — equal highs over equal lows. The first draft
        # asked every pivot in the window to sit inside one band, which no
        # 120-bar window ever satisfied (RANGE fired 0 times in 811 reads on
        # the first grade, and every sideways window fell into CHOP). A
        # definition that cannot fire is not a definition.
        band = LEVEL_ATR * atr * 2 if atr else Decimal(0)
        hi_band = abs(h2 - h1) <= band
        lo_band = abs(l2 - l1) <= band
        out["read"] = "RANGE" if (hi_band and lo_band) else "CHOP"
    out["hh"] = h2 > h1
    out["hl"] = l2 > l1
    out["lh"] = h2 < h1
    out["ll"] = l2 < l1
    return out


class Chart:
    """One symbol/timeframe's candle series, read as-of any moment."""

    def __init__(self, tf, tf_seconds, candles):
        self.tf, self.tf_seconds = tf, tf_seconds
        self.candles = candles
        self.opens = [c["open_ts"] for c in candles]
        self.atr = compute_atr(candles) if candles else []

    def window(self, as_of):
        """The last WINDOW_BARS bars CLOSED at as_of, minus the FRACTAL_WING
        newest whose pivots could not yet be known — no, keep them: a pivot
        inside the wing is simply not emitted, and the bars still carry
        closes for the efficiency ratio."""
        end = bisect.bisect_right(self.opens, as_of - self.tf_seconds)
        start = max(0, end - WINDOW_BARS)
        return start, end

    def at(self, as_of) -> dict:
        start, end = self.window(as_of)
        win = self.candles[start:end]
        atr = self.atr[end - 1] if end and end - 1 < len(self.atr) else None
        r = read_window(win, atr)
        r["window_start_ts"] = win[0]["open_ts"] if win else None
        r["window_end_ts"] = win[-1]["open_ts"] if win else None
        r["atr"] = None if atr is None else str(atr)
        r["close"] = str(_d(win[-1]["close"])) if win else None
        return r


def load(con, symbol, tf, tf_seconds, candles=None) -> Chart:
    if candles is None:
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
    return Chart(tf, tf_seconds, candles)


def reconcile(own: str, htf: str | None) -> str:
    """The operator's top-down call from two reads. Pure."""
    if own == "UNKNOWN":
        return "UNKNOWN"
    trend = own in ("UP", "DOWN")
    if htf in ("UP", "DOWN"):
        if trend:
            return f"TREND_{own}_ALIGNED" if own == htf else f"PULLBACK_IN_HTF_{htf}"
        return f"CONSOLIDATION_IN_HTF_{htf}"
    if trend:
        return "LTF_TREND_IN_HTF_RANGE" if htf in ("RANGE", "CHOP") else f"TREND_{own}_NO_HTF"
    return own            # RANGE or CHOP, both sideways (or HTF unknown)


def nearest_htf_levels(htf_read: dict, price: Decimal, own_atr) -> dict:
    """Nearest HTF resistance above and support below the price, in own-ATR."""
    out = {"resistance_above": None, "support_below": None}
    if not htf_read or own_atr in (None, 0):
        return out
    above = [_d(l["price"]) for l in htf_read.get("resistance", []) if _d(l["price"]) > price]
    below = [_d(l["price"]) for l in htf_read.get("support", []) if _d(l["price"]) < price]
    if above:
        out["resistance_above"] = str(((min(above) - price) / own_atr).quantize(Q2))
    if below:
        out["support_below"] = str(((price - max(below)) / own_atr).quantize(Q2))
    return out


def context(charts, symbol, tf, as_of, tfs, ladder) -> dict:
    """Own read + rung-above read + reconciliation. `charts` caches Chart
    objects by (symbol, tf); `tfs` is importer.TF_SECONDS; `ladder` bias.LADDER."""
    own = charts[(symbol, tf)].at(as_of)
    rung = ladder.get(tf)
    htf = charts[(symbol, rung)].at(as_of) if rung in tfs and (symbol, rung) in charts else None
    price = _d(own["close"]) if own.get("close") else None
    atr = _d(own["atr"]) if own.get("atr") else None
    return {"read": own["read"], "efficiency": own["efficiency"],
            "htf_tf": rung, "htf_read": htf["read"] if htf else None,
            "call": reconcile(own["read"], htf["read"] if htf else None),
            "htf_levels": nearest_htf_levels(htf, price, atr) if (htf and price) else
                          {"resistance_above": None, "support_below": None},
            "own": own, "version": CHARTREAD_VERSION}


# ------------------------------------------------------------- analysis time

def annotate(con, candidates) -> int:
    """Stamp chart_read / chart_htf_read / chart_call as-of each setup's
    confirmation. In place, MISSING left alone — the driftfade convention."""
    from .bias import LADDER
    from .importer import TF_SECONDS
    charts: dict = {}
    n = 0

    def chart(symbol, tf):
        key = (symbol, tf)
        if key not in charts:
            charts[key] = load(con, symbol, tf, TF_SECONDS[tf])
        return charts[key]

    for c in candidates:
        p = c["payload"]
        symbol, tf = p.get("symbol"), p.get("tf")
        if not symbol or tf not in TF_SECONDS:
            continue
        chart(symbol, tf)
        rung = LADDER.get(tf)
        if rung in TF_SECONDS:
            chart(symbol, rung)
        ctx = context(charts, symbol, tf, c["confirmed_at"], TF_SECONDS, LADDER)
        if ctx["read"] == "UNKNOWN":
            continue
        p["chart_read"] = ctx["read"]
        p["chart_htf_read"] = ctx["htf_read"]
        p["chart_call"] = ctx["call"]
        p["chart_efficiency"] = ctx["efficiency"]
        p["chart_htf_resistance_atr"] = ctx["htf_levels"]["resistance_above"]
        p["chart_htf_support_atr"] = ctx["htf_levels"]["support_below"]
        n += 1
    return n


def factor_extractors(payload) -> dict:
    """0/1 flags for outcome_split — the operator's two rules, and the read's
    disagreement with regime.py, which is the claim this module tests."""
    if "chart_read" not in payload:
        return {}
    call, d = payload["chart_call"], payload.get("direction")
    # PULLBACK_IN_HTF_DOWN = own window UP under an HTF that reads DOWN. A
    # LONG there rides the pullback against the bigger picture (the trade the
    # operator says to avoid); a SHORT there sells it at the HTF level (the
    # trade they would take).
    rides = ((call == "PULLBACK_IN_HTF_DOWN" and d == "LONG")
             or (call == "PULLBACK_IN_HTF_UP" and d == "SHORT"))
    fades = ((call == "PULLBACK_IN_HTF_DOWN" and d == "SHORT")
             or (call == "PULLBACK_IN_HTF_UP" and d == "LONG"))
    out = {
        "rides_pullback_against_htf": 1.0 if rides else 0.0,
        "fades_pullback_with_htf": 1.0 if fades else 0.0,
        "in_chop": 1.0 if payload["chart_read"] == "CHOP" else 0.0,
        "in_range": 1.0 if payload["chart_read"] == "RANGE" else 0.0,
        "aligned_trend": 1.0 if call in ("TREND_UP_ALIGNED", "TREND_DOWN_ALIGNED")
        and ((call == "TREND_UP_ALIGNED") == (d == "LONG")) else 0.0,
    }
    reg = payload.get("regime")
    if reg is not None:
        # regime.py says trend and the chart says sideways, or vice versa
        reg_trend = reg in ("BULL_TREND", "BEAR_TREND", "WEAKENING_BULL", "WEAKENING_BEAR")
        chart_trend = payload["chart_read"] in ("UP", "DOWN")
        out["disagrees_with_regime"] = 1.0 if reg_trend != chart_trend else 0.0
    return out


def grade(con, *, setup_version=None, exec_version=None) -> dict:
    from . import factorstats
    kwargs = {}
    if setup_version:
        kwargs["setup_version"] = setup_version
    if exec_version:
        kwargs["exec_version"] = exec_version
    candidates, warnings = factorstats.load_candidates(con, **kwargs)
    n = annotate(con, candidates)
    closed = [c for c in candidates if c.get("r") is not None and "chart_read" in c["payload"]]

    def cells(keyf):
        out: dict = {}
        for c in closed:
            k = keyf(c["payload"])
            cell = out.setdefault(k, {"n": 0, "sum_r": 0.0, "wins": 0})
            cell["n"] += 1
            cell["sum_r"] += float(c["r"])
            cell["wins"] += float(c["r"]) > 0
        for cell in out.values():
            cell["mean_r"] = round(cell["sum_r"] / cell["n"], 3)
            cell["win_rate"] = round(cell["wins"] / cell["n"], 3)
            cell["sum_r"] = round(cell["sum_r"], 2)
        return out

    by_call = cells(lambda p: f"{p['chart_call']} x {p.get('strategy')} {p.get('direction')}")
    by_read = cells(lambda p: f"{p['chart_read']} x {p.get('strategy')} {p.get('direction')}")
    # The agreement matrix: what regime.py called it vs what the chart shows.
    agree: dict = {}
    for c in candidates:
        p = c["payload"]
        if "chart_read" in p and p.get("regime"):
            k = f"{p['regime']} -> {p['chart_read']}"
            agree[k] = agree.get(k, 0) + 1
    splits = {name: factorstats.outcome_split(candidates, name, factors=factor_extractors)
              for name in ("in_chop", "in_range", "aligned_trend", "rides_pullback_against_htf",
                           "fades_pullback_with_htf", "disagrees_with_regime")}
    return {"version": CHARTREAD_VERSION, "derived_at_analysis_time": True,
            "constants": {"WINDOW_BARS": WINDOW_BARS, "FRACTAL_WING": FRACTAL_WING,
                          "LEVEL_ATR": str(LEVEL_ATR), "MIN_PIVOTS": MIN_PIVOTS},
            "candidates": len(candidates), "annotated": n, "closed": len(closed),
            "by_call": by_call, "by_read": by_read, "regime_vs_chart": agree,
            "splits": splits, "warnings": warnings}


# ------------------------------------------------------------- golden loop

def golden_score(con, labels: list[dict]) -> dict:
    """Score the reader against operator labels — §27 of the constitution.

    Each label: {"symbol", "tf", "as_of" (epoch seconds or ISO date),
    "expected": UP|DOWN|RANGE|CHOP, "note"?}. The read is taken as-of the
    label's moment from closed bars, exactly as annotate() would. Reported
    per label so a disagreement names the chart to look at.
    """
    from .importer import TF_SECONDS
    import datetime as _dt
    charts: dict = {}
    rows, hits = [], 0
    for lab in labels:
        as_of = lab["as_of"]
        if isinstance(as_of, str):
            as_of = int(_dt.datetime.fromisoformat(as_of.replace("Z", "+00:00"))
                        .replace(tzinfo=_dt.timezone.utc).timestamp())
        key = (lab["symbol"], lab["tf"])
        if key not in charts:
            charts[key] = load(con, lab["symbol"], lab["tf"], TF_SECONDS[lab["tf"]])
        got = charts[key].at(as_of)
        hit = got["read"] == lab["expected"]
        hits += hit
        rows.append({**{k: lab.get(k) for k in ("symbol", "tf", "as_of", "expected", "note")},
                     "got": got["read"], "efficiency": got["efficiency"],
                     "n_pivots": got["n_pivots"], "hit": hit})
    return {"version": CHARTREAD_VERSION, "n": len(rows), "hits": hits,
            "agreement": round(hits / len(rows), 3) if rows else None, "rows": rows}


def propose(con, n=20, seed=17) -> list[dict]:
    """Windows for the operator to label: random (symbol, tf, moment) with the
    reader's own call beside them, so a label is a confirmation or a
    correction rather than a blank."""
    from .importer import TF_SECONDS
    from .universe import all_tracked_symbols
    from .venues import is_reference_key
    rng = random.Random(seed)
    syms = [s for s in all_tracked_symbols(con) if not is_reference_key(s)]
    out = []
    tries = 0
    while len(out) < n and tries < n * 20:
        tries += 1
        sym = rng.choice(syms)
        tf = rng.choice(["1H", "4H", "1D"])
        rows = con.execute("SELECT open_ts FROM candles WHERE symbol=? AND tf=? ORDER BY open_ts",
                           (sym, tf)).fetchall()
        if len(rows) < WINDOW_BARS + 20:
            continue
        i = rng.randrange(WINDOW_BARS, len(rows))
        as_of = rows[i][0] + TF_SECONDS[tf]
        got = load(con, sym, tf, TF_SECONDS[tf]).at(as_of)
        if got["read"] == "UNKNOWN":
            continue
        out.append({"symbol": sym, "tf": tf, "as_of": as_of,
                    "window_start_ts": got["window_start_ts"], "reader_says": got["read"],
                    "efficiency": got["efficiency"], "expected": None,
                    "note": "fill `expected` with UP / DOWN / RANGE / CHOP from the chart at this moment"})
    return out


def main(argv=None):
    import argparse
    import sqlite3
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--propose", type=int, default=0, metavar="N")
    ap.add_argument("--golden", default=None, metavar="PATH")
    args = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        if args.propose:
            print(json.dumps(propose(con, args.propose), indent=1))
            return 0
        if args.golden:
            labels = json.load(open(args.golden, encoding="utf-8"))
            labels = [l for l in (labels.get("labels") if isinstance(labels, dict) else labels)
                      if l.get("expected")]
            rep = golden_score(con, labels)
            if args.json:
                print(json.dumps(rep, indent=1, default=str))
                return 0
            print(f"golden chart reads {rep['version']}: {rep['hits']}/{rep['n']} agree "
                  f"({rep['agreement']})")
            for r in rep["rows"]:
                mark = "ok  " if r["hit"] else "MISS"
                print(f"  {mark} {r['symbol']:10s} {r['tf']:3s} {r['as_of']}  you: {r['expected']:5s}"
                      f"  reader: {r['got']:5s}  er={r['efficiency']}  pivots={r['n_pivots']}"
                      + (f"  — {r['note']}" if r.get("note") else ""))
            return 0
        rep = grade(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
        return 0
    print(f"chart read {rep['version']} — {rep['annotated']}/{rep['candidates']} annotated, "
          f"{rep['closed']} closed; constants {rep['constants']}")
    print("\nregime.py label -> what the chart window showed (all annotated setups):")
    for k, v in sorted(rep["regime_vs_chart"].items(), key=lambda kv: -kv[1])[:14]:
        print(f"  {k:32s} {v:5d}")
    for title, key in (("top-down call x playbook direction", "by_call"),
                       ("own read x playbook direction", "by_read")):
        print(f"\n{title:44s} {'n':>5} {'mean R':>8} {'sum R':>8} {'win':>5}")
        for k, c in sorted(rep[key].items(), key=lambda kv: -kv[1]["n"]):
            if c["n"] >= 10:
                print(f"  {k:42s} {c['n']:5d} {c['mean_r']:+8.3f} {c['sum_r']:+8.1f} {c['win_rate']:5.0%}")
    print("\nflags (outcome_split, house floors):")
    for name, s in rep["splits"].items():
        g = s["groups"]
        fmt = lambda x: (f"n={x['n']:4d} mean={x['mean_r']:+.3f}R win={x['win_rate']:.0%}"
                         if x.get("sample_ok") else f"n={x['n']:4d} SAMPLE TOO SMALL")
        print(f"  {name:22s} flagged: {fmt(g['at_or_above'])}   |  rest: {fmt(g['below'])}"
              + (f"   delta={s['delta_mean_r']:+.3f}R" if s.get("delta_mean_r") is not None else ""))
    print("\nNOT A GATE. Label windows with --propose and score with --golden before any "
          "playbook reads this (constitution §27).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
