"""Edge statistics — is per-trade expectancy distinguishable from zero, and does
it survive realistic fees?  READ-ONLY: this module writes no facts (§1).

Method ported from the prior project's `backend/diagnostics/edge_significance.py`.
The method is the same (deterministic-LCG bootstrap of the mean, breakeven fee,
verdict). The plumbing is not: that tool read a JSONL trade journal of dollar
PnL, this one reads the SQLite fact store and works in R.

THE CAVEAT THAT INVERTS ON THE PORT — read before touching the arithmetic.
In the old project the journal `pnl` was GROSS price-move PnL; the modelled fee
hit the paper executor's balance and never reached the journal row, so that tool
had to SUBTRACT fees itself. Here the opposite is true: `execsim` nets both fees
and market-exit slippage into `r_multiple` before the fact is written, and
records the difference as `costs_r`. Checked against the live store on
2026-07-29: `costs_r == r_gross - r_multiple` for all 142 filled
`exec-v0.7-draft` facts, no exceptions. Subtracting a fee again would
DOUBLE-COUNT it. So:
  * every statistic below is in R, not dollars — nothing is reconstructed into
    notional and nothing is re-netted;
  * the only fee arithmetic here is RE-PRICING: `fees_price_units` (recorded per
    fact) is added back to recover a fee-free R, and a different fee is then
    charged on the same two legs (`entry` + `effective_exit_price`).

Three more things the numbers here do not know:
  1. Slippage is modelled on SL/TIMEOUT exits only (0.05 ATR) — entry and TP are
     resting limits, so they slip by construction not at all. No scenario below
     touches slippage; every one of them holds it at what execsim charged.
  2. Funding IS modelled, as of v0.2 — but it is a modelled CONSTANT, not a
     measurement. `execsim` charges `FUNDING_RATE_PER_SETTLEMENT` per
     settlement and folds the result into `fees_price_units`; this module
     carries it as `funding_r` and re-charges it in the venue-real scenario.
     Until v0.2 it did not, so the scenario the verdict reads described a trade
     that paid no funding at all: +0.2262 R against +0.1545 R restored, a 46%
     overstatement across 639 trades. The remaining caveat is the constant
     itself — one rate for venues whose settlement schedules differ 8x
     (Phemex 3/day, Kraken 24/day), which is an assumption wearing a
     measurement's clothes and is tracked as such.
  3. MISSED rows are orders that never filled — 90 of the 232 exec-v0.7-draft
     facts. They are not trades. Including their `r_multiple` of "0" would drag
     any real expectancy toward zero with rows where no money moved, which is
     exactly the flattering-by-dilution error this tool exists to avoid.

Floats: prices, fees and stop distances are Decimal end to end (§3). The
conversion to float happens once, at the boundary where a price ratio becomes an
R-multiple — R is dimensionless and the bootstrap sums millions of them, so
float is the right type there and Decimal would be both slower and no more
correct. No float ever touches a price in this file.

Usage:  python -m engine.edgestats
        python -m engine.edgestats --tf 1D --strategy PULLBACK
        python -m engine.edgestats --algo exec-v0.6-draft --resamples 20000
"""
from __future__ import annotations

import json
from decimal import Decimal

from . import store, venues
from .execsim import EXEC_VERSION

EDGESTATS_VERSION = "edgestats-v0.2-draft"
# v0.2: funding restored to the venue-real scenario. It was being added back
# with the fees (execsim folds it into `fees_price_units`) and then not
# re-charged, so the scenario `_verdict` reads described a trade that paid no
# funding. A reported number moved, so the tag moves with it.

# 20,000 resamples, same as the source. At n=142 that is ~1s of pure Python;
# the cost buys a CI whose endpoints are stable in the 3rd decimal, which is
# finer than the 0.01 quantisation execsim applies to r_multiple anyway.
BOOTSTRAP_RESAMPLES = 20000

# Below this the answer is "we do not know", not a number. The source refused at
# n<10 for the summary and n<5 for the CI; we take the stricter of the two for
# everything, because a confident-looking CI on 6 trades is the single most
# misleading artefact this tool could emit (§4 loud-fallback).
MIN_TRADES = 10

_MASK64 = (1 << 64) - 1
_TFS_ORDER = ("15m", "1H", "4H", "1D", "1W")


# ---------------------------------------------------------------- bootstrap

def _bootstrap_mean(vals: list[float], resamples: int) -> dict | None:
    """Deterministic LCG bootstrap of the sample mean — verbatim in method from
    the source module.

    NOT `random`, NOT `numpy.random`, NOT a seeded RNG: a seeded RNG is only as
    reproducible as the implementation behind it, and this project forbids
    nondeterminism in anything that produces a recorded result (§4). The LCG
    constants are fixed here, so two runs over identical data resample the
    identical indices in the identical order and sum them in the identical
    order — byte-identical output, on any machine, on any Python.
    """
    n = len(vals)
    if n < MIN_TRADES:
        return None
    s = 0x2545F4914F6CDD1D
    means = []
    for _ in range(resamples):
        tot = 0.0
        for _ in range(n):
            s = (s * 6364136223846793005 + 1442695040888963407) & _MASK64
            tot += vals[(s >> 33) % n]
        means.append(tot / n)
    means.sort()
    return {
        "resamples": resamples,
        "ci_lo": means[int(0.025 * resamples)],
        "ci_hi": means[int(0.975 * resamples)],
        "p_gt_zero": sum(1 for m in means if m > 0) / resamples,
    }


# ---------------------------------------------------------------- loading

def _risk_index(con, symbol: str | None, tf: str | None) -> dict:
    """(symbol, tf, setup_id, market_time) -> {stop distances} from setup facts.

    Stop distance is what an R is denominated in, and execsim does not copy it
    onto the exec fact. Reading it back from the setup fact keeps ONE authority
    for the number (§6) instead of re-deriving it from the quantised r_gross.
    A setup fact is confirmed strictly before the exec fact it produced, so this
    lookup can never read a fact from the future (§5).

    A set, not a value: setup_id is reused across setup algo versions, and if two
    versions disagree about the stop the trade is ambiguous and must be handled
    loudly rather than silently resolved to whichever row came back first.
    """
    q = ("SELECT symbol, tf, market_time, payload FROM facts WHERE kind='setup'")
    args: list = []
    if symbol:
        q += " AND symbol=?"
        args.append(symbol)
    if tf:
        q += " AND tf=?"
        args.append(tf)
    idx: dict = {}
    for sym, t, mt, payload in con.execute(q, args):
        p = json.loads(payload)
        if p.get("state") != "VALIDATED" or not p.get("sl") or not p.get("entry"):
            continue
        dist = abs(Decimal(p["entry"]) - Decimal(p["sl"]))
        if dist <= 0:
            continue
        idx.setdefault((sym, t, p["setup_id"], mt), set()).add(dist)
    return idx


def _venue_or_none(symbol: str):
    try:
        return venues.venue_for(symbol)
    except ValueError:
        return None


def _setup_version_of(setup_id: str | None) -> str:
    """The engine generation behind a trade, read off its version-scoped id.

    Ids minted before S37 have no version segment; they return "pre-versioned"
    rather than a guess, because guessing which generation an unlabelled fact
    came from is precisely the confound this exists to expose.
    """
    if not setup_id:
        return "unknown"
    tail = setup_id.rsplit("|", 1)[-1]
    return tail if tail.startswith(("setup-v", "scale-v")) else "pre-versioned"


def load_trades(con, *, algo_version: str, symbol: str | None = None,
                tf: str | None = None, strategy: str | None = None,
                as_of: int | None = None) -> tuple[list[dict], dict, list[str]]:
    """Filled trades for one algo version, in the order the system learned them.

    Returns (trades, counts, warnings). Ordering is by confirmed_at then id —
    when the system could first know the outcome (§2), not when the bar printed.
    A losing streak measured in market_time would be a streak nobody ever lived
    through, and the bootstrap's resample order must be reproducible.
    """
    q = ("SELECT id, symbol, tf, market_time, confirmed_at, payload FROM facts "
         "WHERE kind='exec' AND algo_version=?")
    args: list = [algo_version]
    if symbol:
        q += " AND symbol=?"
        args.append(symbol)
    if tf:
        q += " AND tf=?"
        args.append(tf)
    if as_of is not None:
        q += " AND confirmed_at<=?"
        args.append(as_of)
    q += " ORDER BY confirmed_at, id"

    rows = con.execute(q, args).fetchall()
    idx = _risk_index(con, symbol, tf)
    warnings: list[str] = []
    counts = {"exec_facts": 0, "unfilled_missed": 0, "filtered_out_strategy": 0,
              "excluded_no_stop_distance": 0, "excluded_no_fee_record": 0,
              "filled": 0}
    trades: list[dict] = []
    ambiguous, unknown_venue = 0, set()

    for fid, sym, t, mt, confirmed_at, payload in rows:
        counts["exec_facts"] += 1
        p = json.loads(payload)
        if strategy and p.get("strategy") != strategy:
            counts["filtered_out_strategy"] += 1
            continue
        if p.get("outcome") == "MISSED" or p.get("exit_price") is None:
            counts["unfilled_missed"] += 1
            continue

        cands = idx.get((sym, t, p["setup_id"], mt))
        if not cands or len(cands) > 1:
            counts["excluded_no_stop_distance"] += 1
            if cands and len(cands) > 1:
                ambiguous += 1
            continue
        risk = next(iter(cands))

        fees = p.get("fees_price_units")
        eff_exit = p.get("effective_exit_price")
        if fees is None or eff_exit is None:
            # Pre-v0.2 exec facts have no cost record. They cannot be re-priced,
            # and silently treating their fee as zero would make an old book look
            # cheaper than a new one (§4).
            counts["excluded_no_fee_record"] += 1
            continue

        entry = Decimal(p["entry"])
        eff_exit = Decimal(eff_exit)
        fees = Decimal(fees)
        r_net = float(Decimal(p["r_multiple"]))
        r_gross = float(Decimal(p["r_gross"]))
        # The only float conversion in the module: price ratios becoming R.
        # `fees_price_units` CHANGED MEANING at exec-v0.17. Before it, execsim
        # folded funding into that field while ALSO reporting it separately as
        # `funding_price_units`; from v0.17 it is exchange fees only. Both
        # generations are in the store and both must read correctly, so the two
        # components are separated here and recombined explicitly below.
        #
        # Getting this wrong is a silent double-count in either direction: on a
        # v0.17 fact, treating `fees` as funding-inclusive under-adds the
        # cost-free baseline and then re-charges funding a second time in the
        # venue-real scenario. On Kraken, where funding is 58.8% of modelled
        # cost, that is not a rounding error.
        funding = Decimal(p.get("funding_price_units", "0"))
        fee_only = fees if _fees_exclude_funding(algo_version) else (fees - funding)
        fees_r = float(fee_only / risk)
        funding_r = float(funding / risk)
        legs_r = float((entry + eff_exit) / risk)

        v = _venue_or_none(sym)
        if v is None:
            unknown_venue.add(sym)

        counts["filled"] += 1
        trades.append({
            "id": fid, "symbol": sym, "tf": t, "strategy": p.get("strategy"),
            "direction": p.get("direction"), "outcome": p.get("outcome"),
            "confirmed_at": confirmed_at,
            "risk": risk, "entry": entry, "effective_exit_price": eff_exit,
            "fees_price_units": fees,
            "exit_fee_role": p.get("exit_fee_role", "TAKER"),
            "entry_fee_role": p.get("entry_fee_role", "MAKER"),
            # Funding, always separate from fees regardless of which generation
            # wrote the fact. Pre-v0.12 facts have no funding record and get 0,
            # which is correct: those trades were simulated without it.
            "funding_r": funding_r,
            "r_net": r_net, "r_gross": r_gross,
            "costs_r": float(Decimal(p.get("costs_r", "0"))),
            "fees_r": fees_r,
            # Slippage is whatever total cost is NOT fee and NOT funding. Held
            # constant by every scenario — re-pricing a fee must not quietly
            # re-price the market-exit slip too.
            "slip_r": float(Decimal(p.get("costs_r", "0"))) - fees_r - funding_r,
            # The cost-free baseline: BOTH fees and funding added back, so the
            # venue-real scenario can charge both without double-counting.
            "r_ex_fee": r_net + fees_r + funding_r,
            "legs_r": legs_r,
            "venue": v.key if v else None,
            # Carried so the confound guard can see which engine generation
            # produced each trade. `setup_id` is version-scoped since S37
            # (`SYMBOL|TF|STRATEGY|ZONE|setup-vX`), so the generation is already
            # in the identifier and needs no extra join.
            "setup_id": p.get("setup_id"),
            "setup_version": _setup_version_of(p.get("setup_id")),
        })

    if counts["excluded_no_stop_distance"]:
        warnings.append(
            f"{counts['excluded_no_stop_distance']} filled trade(s) excluded: no "
            f"unambiguous VALIDATED setup fact to read the stop distance from "
            f"({ambiguous} ambiguous across setup versions). Their R cannot be "
            f"re-priced, so they are omitted rather than guessed.")
    if counts["excluded_no_fee_record"]:
        warnings.append(
            f"{counts['excluded_no_fee_record']} filled trade(s) excluded: exec "
            f"fact predates cost modelling (no fees_price_units).")
    if unknown_venue:
        warnings.append(
            "venue undeterminable for " + ", ".join(sorted(unknown_venue)) +
            " — venue-real fee scenario falls back to the MODELLED fee for those "
            "trades, so that scenario is not a venue-real number for them.")
    return trades, counts, warnings


# ---------------------------------------------------------------- statistics

def _max_consecutive_losses(trades: list[dict]) -> int:
    """Longest run of non-winning trades in confirmed_at order. A flat trade
    (r_net == 0) extends the run rather than breaking it: it did not win, and
    the drawdown it sits in does not pause for it."""
    run = best = 0
    for t in trades:
        if t["r_net"] > 0:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


def _core(trades: list[dict], resamples: int, warnings: list[str],
          label: str = "book") -> dict:
    n = len(trades)
    net = [t["r_net"] for t in trades]
    wins = [r for r in net if r > 0]
    losses = [r for r in net if r < 0]
    gross_loss = -sum(losses)
    out = {
        "n": n,
        "sufficient": n >= MIN_TRADES,
        "refusal": None,
        "sum_r": sum(net),
        "mean_r": sum(net) / n if n else None,
        "win_rate": len(wins) / n if n else None,
        "wins": len(wins),
        "losses": len(losses),
        "avg_win_r": sum(wins) / len(wins) if wins else None,
        "avg_loss_r": sum(losses) / len(losses) if losses else None,
        "mean_r_gross": sum(t["r_gross"] for t in trades) / n if n else None,
        "mean_costs_r": sum(t["costs_r"] for t in trades) / n if n else None,
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "profit_factor": None,
        "bootstrap": None,
    }
    if gross_loss > 0:
        out["profit_factor"] = sum(wins) / gross_loss
    elif n >= MIN_TRADES:
        # No losing trade at all. Profit factor is not "infinity, therefore
        # excellent" — it is undefined, and it usually means the sample is too
        # short to have met a loss yet (§4). Not worth saying about a book that
        # is already being refused for size; that refusal is the louder signal.
        warnings.append(
            f"{label}: profit factor undefined — no losing trade in this book.")
    if n < MIN_TRADES:
        # Said plainly because it is READ on a trader surface — edgeview.js
        # prints this string verbatim and deliberately does not paraphrase it.
        # The refusal itself is unchanged; only the words are.
        out["refusal"] = (f"fewer than {MIN_TRADES} trades. No average and no "
                          f"range is shown for a slice this short: the numbers "
                          f"would describe these few trades rather than the "
                          f"system that produced them.")
        for k in ("mean_r", "win_rate", "profit_factor", "avg_win_r",
                  "avg_loss_r", "mean_r_gross", "mean_costs_r"):
            out[k] = None
        return out
    out["bootstrap"] = _bootstrap_mean(net, resamples)
    return out


# ---------------------------------------------------------------- fee models

def _fees_exclude_funding(algo_version: str | None) -> bool:
    """Does this generation's `fees_price_units` mean exchange fees ONLY?

    exec-v0.17 split them; every earlier generation folded funding into the fee
    field while also reporting it separately. Keyed on the version string
    deliberately rather than inferred from the numbers — a heuristic that tries
    to detect which convention a fact used would be wrong exactly when funding
    happens to be zero, which is most 15m trades.

    Parsed as a TUPLE OF INTS, not a float. `float("0.2") == 0.2 >= 0.17` is
    True, which would have read every exec-v0.2 fact as the new convention —
    a version string is a sequence of integers, and 2 < 17.
    """
    if not algo_version:
        return False
    try:
        parts = algo_version.split("-v")[1].split("-")[0].split(".")
        n = tuple(int(x) for x in parts)
    except (IndexError, ValueError):
        return False
    return n >= (0, 17)


def _venue_fee_r(t: dict) -> float:
    """What this trade's COST would have been in R at the venue's real published
    rates: both fee legs, plus the funding it accrued while held.

    Rates come from venues.py and nowhere else (§6).

    Funding is included because `r_ex_fee` is built by adding back
    `fees_price_units`, and execsim folds funding into that figure. Charging
    only the two fee legs here therefore returned a trade that paid NO funding,
    in the one scenario `_verdict` reads. Measured on exec-v0.13, all 639
    trades: +0.2262 R shipped against +0.1545 R with funding restored — a
    +0.0717 R/trade overstatement (46%), and 84% on the Kraken half, whose
    24x-per-day settlement schedule makes funding the dominant cost term.

    That is S45's defect one layer up: a cost charged in the simulator and
    subtracted back out in the engine that grades it.
    """
    v = _venue_or_none(t["symbol"])
    if v is None:
        return t["fees_r"]                      # loud-flagged in load_trades
    entry_rate = v.maker_rate if t["entry_fee_role"] == "MAKER" else v.taker_rate
    exit_rate = v.maker_rate if t["exit_fee_role"] == "MAKER" else v.taker_rate
    fee = entry_rate * t["entry"] + exit_rate * t["effective_exit_price"]
    return float(fee / t["risk"]) + t.get("funding_r", 0.0)


def _scenarios(trades: list[dict], resamples: int) -> list[dict]:
    """Expectancy under each fee model, slippage held at what execsim charged."""
    rows = [
        ("the costs recorded at the time",
         [t["r_net"] for t in trades],
         "r_multiple exactly as execsim wrote it — fees already netted."),
        ("no fees at all — the best case",
         [t["r_ex_fee"] for t in trades],
         "fees added back; market-exit slippage untouched. The ceiling."),
        # Rendered as a row label in the fee table on Results; the module it
        # reads from is provenance, not something the reader chooses between.
        ("today's venue rates, re-priced",
         [t["r_ex_fee"] - _venue_fee_r(t) for t in trades],
         "re-priced at each symbol's own venue maker/taker rate."),
    ]
    # Parallel to `rows`, in the same order. Consumers match on the KEY; the
    # label above is free to be reworded for readers without breaking them.
    keys = ("as_recorded", "fee_free", "venue_real")
    out = []
    for (label, vals, note), key in zip(rows, keys):
        n = len(vals)
        boot = _bootstrap_mean(vals, resamples) if n >= MIN_TRADES else None
        out.append({"key": key, "scenario": label, "note": note, "n": n,
                    "mean_r": sum(vals) / n if n else None,
                    "bootstrap": boot})
    return out


def _breakeven_fee(trades: list[dict]) -> dict:
    """Per-side fee rate at which mean net expectancy reaches zero.

    Solve mean(r_ex_fee) - f * mean(legs_r) = 0 for f, where legs_r is
    (entry + effective_exit) / stop_distance — the two notional legs a per-side
    fee is charged on, expressed in R. Same identity as the source's
    mean_gross / mean_legs, only the units are R instead of dollars.

    When mean(r_ex_fee) <= 0 the solution is <= 0: the book loses before any fee
    is charged, and there is no fee rate that rescues it. That is reported as a
    fact, not smoothed into a small positive number.
    """
    n = len(trades)
    mean_ex_fee = sum(t["r_ex_fee"] for t in trades) / n
    mean_legs = sum(t["legs_r"] for t in trades) / n
    if mean_legs <= 0:
        return {"computable": False,
                "reason": "mean fee base (entry + exit legs, in R) is not positive",
                "mean_r_ex_fee": mean_ex_fee, "mean_legs_r": mean_legs,
                "per_side": None, "round_trip": None, "venues": []}
    per_side = mean_ex_fee / mean_legs
    rows = []
    seen: dict = {}
    example: dict = {}
    for t in trades:
        seen[t["venue"]] = seen.get(t["venue"], 0) + 1
        example.setdefault(t["venue"], t["symbol"])
    for v in venues.ALL:
        if v.key not in seen:
            continue
        # Round trip via venues.round_trip_cost_rate, not maker+taker restated
        # here — the venue module owns what a round trip costs (§6), including
        # any future change to which side is charged what.
        rt = float(venues.round_trip_cost_rate(example[v.key]))
        rows.append({
            "venue": v.key, "n_trades": seen[v.key],
            "maker_rate": float(v.maker_rate), "taker_rate": float(v.taker_rate),
            "round_trip_rate": rt,
            "survives": per_side * 2 > rt,
        })
    if None in seen:
        rows.append({"venue": None, "n_trades": seen[None], "maker_rate": None,
                     "taker_rate": None, "round_trip_rate": None,
                     "survives": None})
    return {"computable": True,
            "mean_r_ex_fee": mean_ex_fee, "mean_legs_r": mean_legs,
            "per_side": per_side, "round_trip": per_side * 2,
            "no_fee_rescues_it": per_side <= 0,
            "venues": rows}


# ---------------------------------------------------------------- report

def report(con, *, algo_version: str | None = None, symbol: str | None = None,
           tf: str | None = None, strategy: str | None = None,
           as_of: int | None = None, venue_state: str | None = None,
           resamples: int = BOOTSTRAP_RESAMPLES) -> dict:
    """Plain-dict edge report. Read-only: writes no facts, mutates nothing.

    `venue_state` selects which half of the book to grade:
      · "TRADED" — symbols the risk authority will actually size. This is what
        an operator-facing surface must show.
      · "SHADOW" — a warmed venue's simulated record. Real evidence, and the
        basis for admitting the venue, but not a track record.
      · None (default) — everything, which is what offline research wants.

    The split exists because the two were being added together. Measured
    2026-07-30: 276 of 639 trades (43.2%) were Kraken SHADOW, and
    `/api/edge-stats` sat beside the equity curve implying it described the
    same book. It described neither the traded universe nor the forward
    baseline. `counts` always reports both halves, so a filtered report still
    says out loud what it left out.
    """
    algo_version = algo_version or EXEC_VERSION
    trades, counts, warnings = load_trades(
        con, algo_version=algo_version, symbol=symbol, tf=tf,
        strategy=strategy, as_of=as_of)

    from . import universe
    shadow = set(universe.shadow_symbols(con))
    counts["shadow_venue"] = sum(1 for t in trades if t["symbol"] in shadow)
    counts["traded_venue"] = len(trades) - counts["shadow_venue"]
    if venue_state == "TRADED":
        trades = [t for t in trades if t["symbol"] not in shadow]
    elif venue_state == "SHADOW":
        trades = [t for t in trades if t["symbol"] in shadow]
    elif counts["shadow_venue"]:
        warnings.append(
            f"{counts['shadow_venue']} of {counts['shadow_venue'] + counts['traded_venue']} "
            f"trades are on SHADOW symbols the risk authority refuses to size. "
            f"This is the COMBINED book — pass venue_state='TRADED' for the "
            f"tradeable one.")

    out = {
        "edgestats_version": EDGESTATS_VERSION,
        "venues_version": venues.VENUES_VERSION,
        "algo_version": algo_version,
        "filters": {"symbol": symbol, "tf": tf, "strategy": strategy,
                    "as_of": as_of, "venue_state": venue_state},
        "resamples": resamples,
        "counts": counts,
        "warnings": warnings,
        # These are printed under the panel on the Results surface, so they are
        # written for the person deciding whether to trust the number above
        # them — not for the person maintaining the module. Each one names a
        # way the figures could be wrong; the field names and module paths that
        # used to carry that meaning live in this file's header instead.
        "caveats": [
            "Every figure here is already after costs. Fees and the slippage "
            "on stop and timeout exits are taken out before a trade is "
            "counted, so nothing below is a gross number dressed as a net one.",
            "Funding is charged, but from a single assumed rate applied to "
            "every venue — and real venues settle up to eight times more often "
            "than each other. Treat the funding part as an estimate, not a "
            "measurement.",
            "Orders that never filled are not counted. They are not trades, "
            "and counting them would drag the average toward zero with rows "
            "where no money ever moved.",
            "The 'if fees were' rows re-price the same trades under a "
            "different fee schedule. They do not re-run the strategy, so they "
            "cannot tell you how it would have behaved at those costs.",
        ],
        "sufficient": False,
        "refusal": None,
        "book": None,
        "scenarios": None,
        "breakeven_fee": None,
        "by_tf": {},
        "verdict": None,
    }

    if counts["filled"] < MIN_TRADES:
        out["refusal"] = (
            f"{counts['filled']} filled trade(s) for {algo_version} under these "
            f"filters — below the {MIN_TRADES}-trade floor. No expectancy, no "
            f"confidence interval, no breakeven fee and no verdict are reported. "
            f"This is a refusal, not a result of zero.")
        return out

    out["sufficient"] = True
    out["book"] = _core(trades, resamples, warnings)
    out["scenarios"] = _scenarios(trades, resamples)
    out["breakeven_fee"] = _breakeven_fee(trades)

    by_tf: dict = {}
    present = {t["tf"] for t in trades}
    for t_key in [x for x in _TFS_ORDER if x in present] + \
                 sorted(present - set(_TFS_ORDER)):
        sub = [t for t in trades if t["tf"] == t_key]
        by_tf[t_key] = _core(sub, resamples, warnings, label=f"tf {t_key}")
    out["by_tf"] = by_tf
    # Every by-timeframe slice is tagged with the engine generations behind it.
    # Without this, a timeframe that only exists under one setup version reads
    # as a market fact when it may be an engine fact.
    out["confound"] = confound_report(
        trades, {t_key: [t for t in trades if t["tf"] == t_key] for t_key in by_tf})
    out["verdict"] = _verdict(out)
    return out


# --- confound guard (SALVAGE 1.3) -----------------------------------------
# A slice is only comparable to another slice if both were produced by the same
# code. Ported from the prior project's `edge_by_regime`, which existed because
# a naive read said "up_compressed bleeds, down is fine" when the real cause was
# a wide-stop bug fixed partway through the sample — the regimes were entangled
# with a code change, not with each other.
#
# This project is unusually exposed to that. S40 moved SIX versions in one pass
# (structure, zone, liquidity, regime, setup, exec) and the re-measurement was
# done by hand. A slice living entirely on one side of a version boundary
# describes the engine as much as the market, and saying so is the whole job.
# A generation below this share of the book is residue, not a split.
MATERIAL_GENERATION_SHARE = 0.05


def _version_spans(trades: list[dict]) -> dict:
    """setup_version -> (first_exit_ts, last_exit_ts, n) across the trades."""
    spans: dict = {}
    for t in trades:
        v = t.get("setup_version") or t.get("setup_algo_version") or "unknown"
        ts = t.get("exit_ts") or t.get("confirmed_at") or 0
        cur = spans.get(v)
        if cur is None:
            spans[v] = [ts, ts, 1]
        else:
            cur[0] = min(cur[0], ts)
            cur[1] = max(cur[1], ts)
            cur[2] += 1
    return {k: {"first": v[0], "last": v[1], "n": v[2]} for k, v in spans.items()}


def confound_report(trades: list[dict], slices: dict) -> dict:
    """Tag every slice with the engine generations that produced it.

    A slice drawn from ONE generation while the book spans several is
    CONFOUNDED: its difference from the others may be the engine, not the
    market. It is still reported — suppressing it would hide data — but it is
    labelled, and a comparison ACROSS two confounded slices is refused outright.
    """
    spans = _version_spans(trades)
    # Materiality floor. A generation holding a handful of orphan rows is
    # residue, not a split book — flagging every slice as CONFOUNDED because
    # three pre-versioned facts survive would train the reader to ignore the
    # label, which costs more than the label is worth. A generation only counts
    # toward a confound once it holds a real share of the book.
    total = sum(v["n"] for v in spans.values()) or 1
    material = {k: v for k, v in spans.items()
                if v["n"] / total >= MATERIAL_GENERATION_SHARE}
    immaterial = {k: v for k, v in spans.items() if k not in material}
    multi = len(material) > 1
    out = {"book_versions": spans, "material_versions": sorted(material),
           "immaterial_versions": {k: v["n"] for k, v in immaterial.items()},
           "book_spans_versions": multi, "slices": {}}
    for name, members in slices.items():
        vs = _version_spans(members)
        vs_material = [k for k in vs if k in material]
        single = len(vs_material) == 1
        confounded = bool(multi and single)
        out["slices"][name] = {
            "n": len(members),
            "versions": vs,
            "confounded": confounded,
            "note": (
                f"CONFOUNDED — every trade in this slice came from "
                f"{(vs_material or list(vs))[0]}, while the book spans {len(material)} engine "
                f"generations. Its difference from other slices may be the "
                f"ENGINE rather than the market, and it must not be compared "
                f"against a slice from a different generation."
                if confounded else
                "spans the same generations as the book — comparable"
                if multi else
                "single-generation book; no version confound possible"),
        }
    comparable = [n for n, v in out["slices"].items() if not v["confounded"]]
    out["comparable_slices"] = comparable
    out["detail"] = (
        f"{len(comparable)} of {len(out['slices'])} slices are comparable"
        if out["slices"] else "no slices")
    return out


def _verdict(rep: dict) -> dict:
    """The one-line answer, phrased so a null result cannot read as a win."""
    real = next(s for s in rep["scenarios"] if s.get("key") == "venue_real")
    boot = real["bootstrap"]
    be = rep["breakeven_fee"]
    if boot is None:
        return {"code": "INSUFFICIENT",
                "headline": "Not measured yet",
                "text": "There are too few closed trades to say anything about "
                        "the edge at the fees these venues really charge. This "
                        "is not a bad result — it is the absence of one."}
    lo, hi, p = boot["ci_lo"], boot["ci_hi"], boot["p_gt_zero"]
    if hi < 0:
        code = "NEGATIVE_EDGE"
        text = (f"At the fees these venues really charge, the honest range for "
                f"the average trade runs from {lo:+.3f} R to {hi:+.3f} R — all "
                f"of it below break even. This is not bad luck: the system "
                f"loses money per trade, and no fee schedule fixes it.")
    elif lo > 0:
        code = "POSITIVE_EDGE"
        text = (f"At the fees these venues really charge, the honest range for "
                f"the average trade runs from {lo:+.3f} R to {hi:+.3f} R — all "
                f"of it above break even. That is a real, if modest, edge. "
                f"Funding costs are still not modelled, so check it again on "
                f"more trades before trusting the size of it.")
    else:
        code = "INDISTINGUISHABLE"
        text = (f"At the fees these venues really charge, the honest range for "
                f"the average trade runs from {lo:+.3f} R to {hi:+.3f} R — it "
                f"still crosses break even. This book has not shown it makes "
                f"money, and it has not shown it loses money either. There is "
                f"not enough evidence yet to say which.")
    if be["computable"] and be["no_fee_rescues_it"]:
        text += (f" Even with ZERO fees this book still loses, on slippage "
                 f"alone. Fees are not what is holding it back.")
    headline = {"NEGATIVE_EDGE": "It loses money",
                "POSITIVE_EDGE": "It makes money, modestly",
                "INDISTINGUISHABLE": "Too close to call"}[code]
    return {"code": code, "headline": headline, "text": text,
            "ci_lo": lo, "ci_hi": hi, "p_gt_zero": p}


# ---------------------------------------------------------------- CLI

def _fmt(x, spec="+.4f", dash="n/a"):
    return dash if x is None else format(x, spec)


def _print_core(label: str, c: dict) -> None:
    if not c["sufficient"]:
        print(f"  {label:<8} n={c['n']:<4} REFUSED — {c['refusal']}")
        return
    b = c["bootstrap"]
    ci = (f"[{b['ci_lo']:+.3f}, {b['ci_hi']:+.3f}]" if b else "n/a")
    pf = _fmt(c["profit_factor"], ".2f", "undef")
    print(f"  {label:<8} n={c['n']:<4} exp={c['mean_r']:+.3f}R  "
          f"win={c['win_rate']:.1%}  PF={pf:<6} "
          f"CI95={ci:<20} P(>0)={b['p_gt_zero']:.1%}  "
          f"maxLoseStreak={c['max_consecutive_losses']}")


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    def opt(name, cast=str, default=None):
        if name in argv:
            return cast(argv[argv.index(name) + 1])
        return default

    rep = report(store.connect(),
                 algo_version=opt("--algo"), symbol=opt("--symbol"),
                 tf=opt("--tf"), strategy=opt("--strategy"),
                 as_of=opt("--as-of", int),
                 resamples=opt("--resamples", int, BOOTSTRAP_RESAMPLES))

    print("=== EDGE SIGNIFICANCE + EDGE AFTER REAL FEES ===")
    f = rep["filters"]
    print(f"algo={rep['algo_version']}  filters: symbol={f['symbol'] or 'ALL'} "
          f"tf={f['tf'] or 'ALL'} strategy={f['strategy'] or 'ALL'} "
          f"as_of={f['as_of'] or 'ALL'}")
    c = rep["counts"]
    print(f"exec facts={c['exec_facts']}  filled={c['filled']}  "
          f"unfilled(MISSED)={c['unfilled_missed']}  "
          f"excluded={c['excluded_no_stop_distance'] + c['excluded_no_fee_record']}")

    for w in rep["warnings"]:
        print(f"  ! {w}")

    if not rep["sufficient"]:
        print(f"\nREFUSED: {rep['refusal']}")
        return 1

    b = rep["book"]
    print("\n--- book ---")
    print(f"  expectancy {b['mean_r']:+.4f} R/trade over n={b['n']}  "
          f"(total {b['sum_r']:+.2f} R)")
    print(f"  win rate {b['win_rate']:.1%} ({b['wins']}W / {b['losses']}L)  "
          f"avgW {_fmt(b['avg_win_r'], '+.2f')}R  "
          f"avgL {_fmt(b['avg_loss_r'], '+.2f')}R  "
          f"profit factor {_fmt(b['profit_factor'], '.3f', 'undefined')}")
    print(f"  gross expectancy {b['mean_r_gross']:+.4f} R  "
          f"modelled cost drag {b['mean_costs_r']:+.4f} R/trade")
    print(f"  max consecutive losses {b['max_consecutive_losses']}")

    print(f"\n--- expectancy per fee model "
          f"(95% CI, {rep['resamples']:,}-resample deterministic bootstrap) ---")
    print(f"  {'scenario':<36}{'exp/trade':>11}{'95% CI':>22}{'P(>0)':>8}")
    for s in rep["scenarios"]:
        bs = s["bootstrap"]
        ci = f"[{bs['ci_lo']:+.3f}, {bs['ci_hi']:+.3f}]" if bs else "n/a"
        p = f"{bs['p_gt_zero']:.1%}" if bs else "n/a"
        print(f"  {s['scenario']:<36}{s['mean_r']:>+11.4f}{ci:>22}{p:>8}")
    for s in rep["scenarios"]:
        print(f"    - {s['scenario']}: {s['note']}")

    be = rep["breakeven_fee"]
    print("\n--- breakeven fee ---")
    if not be["computable"]:
        print(f"  NOT COMPUTABLE: {be['reason']}")
    else:
        print(f"  fee-free expectancy {be['mean_r_ex_fee']:+.4f} R on a mean fee "
              f"base of {be['mean_legs_r']:.2f} R")
        print(f"  -> breaks even at a per-side fee of "
              f"{100*be['per_side']:+.4f}% ({100*be['round_trip']:+.4f}% round trip)")
        for v in be["venues"]:
            if v["venue"] is None:
                print(f"  {'(venue unknown)':<16} n={v['n_trades']}")
                continue
            print(f"  {v['venue']:<16} n={v['n_trades']:<4} "
                  f"maker {100*v['maker_rate']:.4f}% / taker "
                  f"{100*v['taker_rate']:.4f}% -> round trip "
                  f"{100*v['round_trip_rate']:.4f}%  "
                  f"{'SURVIVES' if v['survives'] else 'DOES NOT SURVIVE'}")

    print("\n--- per timeframe ---")
    for tf_key, core in rep["by_tf"].items():
        _print_core(tf_key, core)

    print("\n=== VERDICT ===")
    print(f"  [{rep['verdict']['code']}] {rep['verdict']['text']}")
    for cav in rep["caveats"]:
        print(f"  * {cav}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
