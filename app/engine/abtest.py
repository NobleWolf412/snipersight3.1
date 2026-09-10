"""2x2 replay harness — the gate on setup-v0.7. READ-ONLY, writes no facts.

`docs/SPEC-confirmed-entry.md` changes the ENTRY (touch -> confirmed close) and
the EXIT (hold-to-SL/TP -> partials + trail + breakeven + time stop) in the same
version. A single before/after therefore cannot attribute the result, and the
attribution is not academic: if the exit change carries the whole improvement,
the confirmation rule is optional complexity that should be DROPPED rather than
shipped. Median MFE 1.53R against a median 6.4R target makes that a live
possibility, not a hedge.

So: four variants over the same candles, same cost model, same code path.

                     hold to SL/TP        managed exit
    touch entry      v0.6 baseline        isolates the EXIT fix
    confirmed entry  isolates the ENTRY   proposed v0.7

IT NO LONGER HAS ITS OWN SIMULATION CORE, and the history of that is the point.
It was written with one, defended by the argument that all four variants share
it so the comparison between them stays internally valid, plus a runtime
`calibrate()` pass to catch any absolute offset from production. The offset
arrived anyway, four times, each time as a fix that landed in `execsim.py` and
never crossed over: the exit-fee convention, then funding, then the crossing
fill (+0.1207 R/trade on 76 of 497 trades, the v0.13 behaviour still running
here long after the engine had corrected it), then — once the crossing PRICE
was shared — the model around it, which still chose its own fill bar, its own
maker limit and its own risk denominator.

So the entry (`execsim.simulate_entry`, built on `execsim.cross_fill`), the
exit walk (`execsim.walk_exit`) and the costing (`execsim.settle`) are now the
engine's own, called from here. What remains local is the MANAGED exit —
partials, trail, breakeven, time stop — which execsim does not implement
because its 2x2 gate rejected it. Agreement on everything else is a property of
there being one implementation rather than a result calibration has to keep
re-establishing.

`calibrate()` still runs, and still refuses to present the 2x2 as comparable if
the replay cannot reproduce the recorded book — a measurement tool that cannot
reproduce a known result has not earned the right to describe an unknown one.
Its job is now catching the drift a shared core cannot prevent: a change in
what the STORE holds, rather than in what the code does.

Determinism: pure function of stored candles and setup facts. No RNG, no clock,
no network. Decimal throughout for prices.
"""
import json
from decimal import Decimal

from . import costs, execsim, store
from .importer import TF_SECONDS
from .swings import compute_atr

# v0.3: a missing `entry_model` is now read as the direct-limit model execsim
# actually ran, not silently replaced with MAKER_THEN_MARKET. Scale-in facts
# deliberately predate an explicit model field; substituting one changed a
# recorded +0.34R result to -0.04R in replay. Versions containing more than one
# model now refuse grading loudly rather than choosing a default.
# v0.2: `by_strategy` decides on a CLUSTER bootstrap over symbols instead of
# the IID one, and replays each version under the entry model its own facts
# recorded. The verdict this harness reports therefore changed meaning, and a
# stored result labelled v0.1 was produced by a different question — which is
# the whole reason a research harness carries a version at all.
# v0.6: CALIBRATION SCOPED TO THE BOOK THE RECORD CAN HOLD, and the strategy
#   grade scoped with it. `execsim` never re-settles a market that has left
#   the universe, so an exec bump strands it on the old version and the replay
#   — which walks any symbol with stored candles — reported it as a trade the
#   record was missing. 140 such trades across 47 pairs on 8 Sep 2026, and
#   calibration could not go green by waiting for a rebuild that would never
#   reach them. See `certified_pairs`.
#   THE REPLAY ARITHMETIC IS UNCHANGED: a v0.5 number and a v0.6 number over
#   the same trades are identical, and the corrected trail-minus-hold reading
#   of +0.0232 R does not move. The label moves because the VERDICT does.
#   `strategy_regrades` is append-only and stores `abtest_version` beside
#   `trustworthy`, and the store already held `abtest-v0.5 trustworthy=0`
#   (2026-09-07) for this same book; writing `abtest-v0.5 trustworthy=1` over
#   it would put two opposite verdicts under one label in the one table whose
#   whole reason for carrying the version is that a grade cannot be quoted
#   without knowing which generation produced it.
# v0.5: the gapped-stop fill v0.4 added HERE is now the engine's own rule
# (`execsim.stop_gap_fill`, exec-v0.26-draft), so both cells of every pair get
# it from the same place and the hold cell is once again the engine unmodified.
# v0.4 applied it to one side of its own comparison: a gapped stop was booked
# half a risk unit worse for managed than for hold at the identical level, and
# trailed stops gap through 15.6% of the time against 1.5% for an untouched
# one, so the convention outweighed the effect. Trail-minus-hold reads +0.0208
# R under v0.4, +0.0232 R now, and +0.0670 R if the fill were simply removed
# from both cells — which is why "make the two sides match" was not the fix.
# A v0.4 managed reading is not a v0.5 reading; rerun before quoting one.
# v0.4: existing protection resolves before a closed bar can ratchet the stop.
# Managed stop gaps fill at the adverse open, not an unreachable stop price.
# Research results using managed/trail exits under earlier tags need rerunning.
ABTEST_VERSION = "abtest-v0.7"
# v0.7: the swing-v0.11 ATR cascade — the replay computes its own ATR. Analysis-only,
# writes no facts, and locked for the reason `cycles` is.

# A cluster is a symbol, and eight is the floor for saying anything about the
# spread between them. Below that the resample keeps drawing the same two or
# three markets and the interval describes those, not the strategy. This is a
# floor on CLUSTERS and sits beside `edgestats.MIN_TRADES`, not instead of it:
# both must clear, because forty trades on three symbols is three observations
# and three trades on forty symbols is not a sample either.
MIN_CLUSTERS = 8

# Same 64-bit mask the source LCG uses. Named here rather than imported so the
# two bootstraps cannot drift into different arithmetic without somebody
# noticing they were ever supposed to match.
_MASK64 = (1 << 64) - 1

# The engine's own window, not a copy that "matches" it. A comment claiming
# equality is the roster disease — the number it describes drifts and the
# comment stays.
MAX_HOLD_BARS = execsim.MAX_BARS
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")

# --- managed-exit parameters (SPEC-confirmed-entry §1.6) ---
TP1_R = Decimal("1.5")            # first target, in R
PARTIAL_FRACTION = Decimal("0.5")  # fraction closed at TP1
TRAIL_ACTIVATE_R = Decimal("1.5")
TRAIL_DISTANCE_R = Decimal("0.5")
BE_TRIGGER_R = Decimal("1.0")
STAGNATION_FLOOR_RATIO = Decimal("0.7")
# Adaptive time stop, in BARS of the setup's own timeframe rather than hours —
# the same 48h means something different on 15m and 1D, and bar-counting keeps
# the harness free of wall-clock reasoning.
HOLD_BARS_BY_TF = {"5m": 24, "15m": 20, "1H": 14, "4H": 12,
                   "1D": 10, "1W": 8}
# Maker-leg parameters for the COUNTERFACTUAL cells only. A setup that records
# its own `maker_limit` and `maker_wait_bars` is replayed on those — setups.py
# is the authority for where its order rested and execsim honours that, so a
# replay that re-derived the number would be answering a different question.
# These fill in for the older generations the 2x2 tests this entry model over,
# which predate the fields.
#
# Bars a maker limit rests before it is abandoned. Short on purpose: the
# thesis is 'the level held and price is leaving', so a limit that has not
# filled in two bars is waiting for a move that already went without it.
MAKER_WAIT_BARS = 2
# How far better than the market the maker limit rests, in R of the
# PLANNED risk. Must be > 0 or the order is marketable and pays taker.
MAKER_OFFSET_R = Decimal("0.10")


class _Pos:
    """Open position state. Exists because a managed exit cannot be expressed
    as a single terminal outcome — partials mean realised R accrues in pieces."""

    __slots__ = ("entry", "sl", "tp", "long", "risk", "qty", "realised_r",
                 "be_moved", "trailing", "extreme", "partials")

    def __init__(self, entry, sl, tp, long, risk):
        self.entry, self.sl, self.tp, self.long, self.risk = entry, sl, tp, long, risk
        self.qty = Decimal(1)
        self.realised_r = Decimal(0)
        self.be_moved = False
        self.trailing = False
        self.extreme = entry
        self.partials = []

    def r_at(self, price):
        move = (price - self.entry) if self.long else (self.entry - price)
        return move / self.risk


def _leg_r(profile, symbol, entry, px, risk, long, taker_in, taker_out,
           atr_exit, bars_held, tf_seconds):
    """NET R of one closed leg, priced by execsim.settle — THE costing.

    This replaces a local `_cost_r` that had already drifted from the engine in
    the two ways copies drift: its exit fee was charged on the nominal price
    where the engine charges the slipped one, and it never charged funding —
    the cost execsim v0.12 added precisely because an unmodelled cost that only
    ever flatters is the kind that survives review. Every cell of the 2x2 was
    flattered by the funding its holds accrued; the managed cells, which hold
    longest, were flattered most, and the harness's whole job is comparing them.

    Per-leg funding is correct by distribution: settle charges funding on the
    FULL notional to this leg's close, and the caller multiplies the leg by its
    fraction — fraction x full == funding on the fraction. The entry fee sums
    the same way across legs to exactly one entry's fee.
    """
    st = execsim.settle(profile, symbol, entry, px, risk, long,
                        "SL" if taker_out else "TP",
                        bars_held, tf_seconds, atr_exit,
                        entry_role="TAKER" if taker_in else "MAKER")
    return st["r_mult"]


def _simulate(candles, atr, i_fill, entry, sl, tp, long, tf, profile, managed,
              taker_in, *, symbol, tf_seconds, partials=None, trail=None,
              timestop=None):
    """Walk bars from the fill and return one outcome dict, or None if the data
    runs out before the position resolves (OPEN — never counted as a result).

    Conservative rule kept from execsim: a bar that touches BOTH stop and target
    counts as the STOP. Sub-bar sequencing needs lower-timeframe data we do not
    have, and flattering an ambiguous bar is how a backtest lies.
    """
    # The managed exit was rejected as a BUNDLE (partials + breakeven + trail +
    # time stop), and a bundle verdict is not a component verdict. Each piece is
    # now switchable so it can earn or lose on its own merits; `managed` remains
    # the shorthand for "all of them", which is what the 2x2 measured.
    use_partials = managed if partials is None else partials
    use_trail = managed if trail is None else trail
    use_timestop = managed if timestop is None else timestop
    risk = (entry - sl) if long else (sl - entry)
    if risk <= 0:
        return None

    if not (use_partials or use_trail or use_timestop):
        # The hold cell IS the engine. No re-implementation, however faithful:
        # the walk that settles the record walks the counterfactual, so the
        # baseline cell of every 2x2 agrees with execsim by construction —
        # which is what the calibrate() pass used to have to establish
        # empirically, and what the drift it tolerated used to erode.
        w = execsim.walk_exit(candles, i_fill, sl, tp, long,
                              max_bars=MAX_HOLD_BARS)
        if w is None:
            return None                       # OPEN — never counted as a result
        outcome, px, j, _ambiguous = w
        st = execsim.settle(profile, symbol, entry, px, risk, long, outcome,
                            j - i_fill, tf_seconds, atr[j],
                            entry_role="TAKER" if taker_in else "MAKER")
        held = candles[i_fill:j + 1]
        if long:
            mfe = max(Decimal(c["high"]) - entry for c in held) / risk
            mae = max(entry - Decimal(c["low"]) for c in held) / risk
        else:
            mfe = max(entry - Decimal(c["low"]) for c in held) / risk
            mae = max(Decimal(c["high"]) - entry for c in held) / risk
        return {"outcome": outcome, "r": st["r_mult"],
                "bars_held": j - i_fill,
                "same_bar": j == i_fill and outcome in ("SL", "TP"),
                "mfe_r": max(mfe, Decimal(0)), "mae_r": max(mae, Decimal(0)),
                "partials": [], "r_if_held": None}

    pos = _Pos(entry, sl, tp, long, risk)
    max_hold = HOLD_BARS_BY_TF.get(tf, 12) if use_timestop else MAX_HOLD_BARS
    limit = min(i_fill + MAX_HOLD_BARS, len(candles))
    same_bar = False
    mfe = mae = Decimal(0)

    for j in range(i_fill, limit):
        c = candles[j]
        hi, lo = Decimal(c["high"]), Decimal(c["low"])
        fav = (hi - entry) if long else (entry - lo)
        adv = (entry - lo) if long else (hi - entry)
        mfe = max(mfe, fav / risk)
        mae = max(mae, adv / risk)
        bars_held = j - i_fill

        if use_partials:
            # TP1 partial. Checked before the stop on the same bar ONLY when the
            # bar's own extreme reached it before the stop could have — which we
            # cannot know from OHLC. So: if both are touched on one bar, the stop
            # wins and no partial is booked. Conservative, and it keeps the
            # partial from manufacturing profit out of an ambiguous bar.
            tp1 = entry + TP1_R * risk if long else entry - TP1_R * risk
            hit_tp1 = (hi >= tp1) if long else (lo <= tp1)
            hit_sl_now = (lo <= pos.sl) if long else (hi >= pos.sl)
            # A partial moves the stop to breakeven. If THIS SAME BAR also
            # trades through breakeven, we would be claiming the high came
            # before the low — intrabar ordering OHLC cannot tell us. execsim's
            # convention for that ambiguity is "stop first", and it must apply
            # here or the managed-exit cells get to bank a profit out of a bar
            # that may have gone the other way first. Skipping the partial on
            # such a bar is the conservative reading, and it matters most
            # exactly where the bars are largest relative to risk — which is
            # the touch-entry cell this comparison is judging.
            # Strict: a bar whose low merely TOUCHES entry has not traded
            # through breakeven, and the fill sits at that price anyway.
            be_touched_same_bar = (lo < entry) if long else (hi > entry)
            if hit_tp1 and not hit_sl_now and not be_touched_same_bar \
                    and not pos.partials:
                booked = PARTIAL_FRACTION * _leg_r(
                    profile, symbol, entry, tp1, risk, long, taker_in, False,
                    None, bars_held, tf_seconds)
                pos.realised_r += booked
                pos.qty -= PARTIAL_FRACTION
                pos.partials.append({"r": str(TP1_R.quantize(Q2)),
                                     "fraction": str(PARTIAL_FRACTION),
                                     "bar": bars_held})
                # breakeven follows the first partial: the remainder is now
                # riding on money already banked
                pos.sl = entry
                pos.be_moved = True

        hit_sl = (lo <= pos.sl) if long else (hi >= pos.sl)
        hit_tp = (hi >= pos.tp) if long else (lo <= pos.tp)
        if hit_sl or hit_tp:
            if bars_held == 0:
                same_bar = True
            outcome = "SL" if hit_sl else "TP"
            px = pos.sl if hit_sl else pos.tp
            if hit_sl and j > i_fill:
                # A new closed-bar trail may already be crossed at the next
                # open. The fill candle's own open precedes the entry and must
                # not be used as a post-entry gap price. Shared with the hold
                # cell above, which is the point: see `execsim.stop_gap_fill`.
                px = execsim.stop_gap_fill(px, Decimal(c["open"]), long)
            taker_out = hit_sl
            leg_r = _leg_r(profile, symbol, entry, px, risk, long, taker_in,
                           taker_out, atr[j], bars_held, tf_seconds)
            total = pos.realised_r + pos.qty * leg_r
            return {"outcome": outcome, "r": total, "bars_held": bars_held,
                    "same_bar": same_bar, "mfe_r": mfe, "mae_r": mae,
                    "partials": pos.partials,
                    "r_if_held": None}

        if use_trail:
            # Only a surviving bar may update protection for the NEXT bar.
            # Updating before the hit test assumes its favourable extreme
            # preceded its low/high, and can turn an original stop-out into
            # a winner. This is closed-bar management, not intrabar trailing.
            if not pos.be_moved and pos.r_at(hi if long else lo) >= BE_TRIGGER_R:
                pos.sl = entry
                pos.be_moved = True
            pos.extreme = max(pos.extreme, hi) if long else min(pos.extreme, lo)
            if pos.r_at(pos.extreme) >= TRAIL_ACTIVATE_R:
                pos.trailing = True
            if pos.trailing:
                next_stop = (pos.extreme - TRAIL_DISTANCE_R * risk) if long \
                    else (pos.extreme + TRAIL_DISTANCE_R * risk)
                pos.sl = max(pos.sl, next_stop) if long else min(pos.sl, next_stop)

        if use_timestop and bars_held >= max_hold:
            # Adaptive time stop, with the floor guard: never time-stop a trade
            # already most of the way to its stop — defer to the stop, which is
            # the exit that was actually planned for that outcome.
            px = Decimal(c["close"])
            if pos.r_at(px) <= -STAGNATION_FLOOR_RATIO:
                continue
            leg_r = _leg_r(profile, symbol, entry, px, risk, long, taker_in,
                           True, atr[j], bars_held, tf_seconds)
            total = pos.realised_r + pos.qty * leg_r
            return {"outcome": "TIME", "r": total, "bars_held": bars_held,
                    "same_bar": False, "mfe_r": mfe, "mae_r": mae,
                    "partials": pos.partials, "r_if_held": None}

    if not use_timestop and i_fill + MAX_HOLD_BARS <= len(candles):
        j = i_fill + MAX_HOLD_BARS - 1
        c = candles[j]
        px = Decimal(c["close"])
        leg_r = _leg_r(profile, symbol, entry, px, risk, long, taker_in, True,
                       atr[j], j - i_fill, tf_seconds)
        return {"outcome": "TIMEOUT", "r": pos.realised_r + pos.qty * leg_r,
                "bars_held": MAX_HOLD_BARS - 1, "same_bar": False,
                "mfe_r": mfe, "mae_r": mae, "partials": [], "r_if_held": None}
    return None                                    # still open at end of data


def _load_setups(con, symbol, tf, version):
    out = {}
    for r in store.get_facts(con, symbol, tf, "setup", version):
        p = json.loads(r["payload"])
        if p.get("state") != "VALIDATED" or not p.get("entry"):
            continue
        out[p["setup_id"]] = {"confirmed_at": r["confirmed_at"],
                              "market_time": r["market_time"], **p}
    return out


def _bisect_fill(candle_times, available_at):
    lo, hi = 0, len(candle_times)
    while lo < hi:
        mid = (lo + hi) // 2
        if candle_times[mid] < available_at:
            lo = mid + 1
        else:
            hi = mid
    return lo


def recorded_entry_model(con, symbols, tfs, setup_version):
    """Return the one entry model a setup generation recorded.

    ``None`` is meaningful: it is execsim's direct-limit path, not permission
    for a research caller to substitute the current setup engine's model. Read
    the same VALIDATED, entry-bearing population ``run_variant`` replays;
    FORMING and terminal lifecycle rows are not orders and may predate fields
    that only a final plan needs.
    """
    models = set()
    for symbol in symbols:
        for tf in tfs:
            models.update(
                s.get("entry_model")
                for s in _load_setups(con, symbol, tf, setup_version).values())
    if len(models) > 1:
        readable = sorted("DIRECT_LIMIT" if m is None else m for m in models)
        raise ValueError(
            f"{setup_version} records multiple entry models: {', '.join(readable)}")
    return next(iter(models)) if models else None


def run_variant(con, symbols, tfs, setup_version, *, managed, entry_model,
                profile_override=None, partials=None, trail=None,
                timestop=None, beat=None):
    """One cell of the 2x2. Returns per-trade results, never aggregates alone.

    `profile_override` exists for calibration only. Reproducing a historical
    result requires the cost model that PRODUCED it, and execsim wrote every
    recorded fact under the venue-blind Coinbase default (fixed 2026-07-30, see
    costs.profile_for). Replaying that book with the corrected 14x-cheaper perp
    fees is not a reproduction — it is a different experiment that happens to
    share inputs. The 2x2 cells all use the CORRECTED model, so the comparison
    between them stays internally valid.

    `beat` is an optional per-symbol progress callback, for callers running
    inside a supervised process: a full-universe replay runs minutes against
    the watchdog's dark-scanner threshold, and the retention sweep set the
    precedent — beat inside the work, "so a sweep is never mistaken for a
    hang". Default None; nothing else changes.
    """
    results = []
    for symbol in symbols:
        if beat:
            beat(symbol)
        profile = profile_override or costs.profile_for(symbol)
        for tf in tfs:
            candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
            if not candles:
                continue
            atr = compute_atr(candles)
            times = [c["open_ts"] for c in candles]
            for sid, s in _load_setups(con, symbol, tf, setup_version).items():
                entry, sl, tp = (Decimal(s["entry"]), Decimal(s["sl"]),
                                 Decimal(s["tp"]))
                long = s["direction"] == "LONG"
                # The order is available on the bar execsim would place it on
                # — a bisect on `confirmed_at`, exactly as run() does. This was
                # `confirmed_bar_ts + 1` for the maker and market cells and a
                # bisect only for the resting-limit one; the two agree on all
                # 497 facts of the current book, which is a coincidence this
                # harness has already been burned for relying on.
                order_i = _bisect_fill(times, s["confirmed_at"])
                if order_i >= len(candles):
                    continue
                base_risk = (entry - sl) if long else (sl - entry)
                if base_risk <= 0:
                    continue
                # `maker_limit` is READ from the plan when the plan recorded one
                # — setups.py calls itself the authority for that number ("so
                # execsim never re-derives it — one authority per number") and
                # execsim honours it, so the replay must too. Re-deriving it
                # here reproduced the same value on this book and would have
                # stopped the day MAKER_OFFSET_R moved on one side only.
                #
                # The counterfactual cells run this entry model over OLDER setup
                # generations that predate the field; only there is it derived,
                # and the constants below are the ones the model is being tested
                # with.
                if s.get("maker_limit"):
                    maker_limit = Decimal(s["maker_limit"])
                    maker_wait = int(s.get("maker_wait_bars") or MAKER_WAIT_BARS)
                else:
                    # A limit AT the next open is marketable — it crosses the
                    # spread and pays TAKER. Claiming maker for it would be a
                    # free lunch invented by the model, so the limit must rest
                    # at a BETTER price than the market and genuinely wait.
                    maker_limit = ((entry - MAKER_OFFSET_R * base_risk) if long
                                   else (entry + MAKER_OFFSET_R * base_risk))
                    maker_wait = MAKER_WAIT_BARS
                # THE fill model — execsim's, not a second one. Sharing
                # `cross_fill` fixed the crossing PRICE; this shares the model
                # around it, which is where the harness was still deciding for
                # itself which bar to cross on, whether the passive leg had
                # filled, and what the risk denominator was.
                fill = execsim.simulate_entry(
                    candles, atr, order_i, entry, sl, long,
                    entry_model=entry_model, maker_limit=maker_limit,
                    maker_wait=maker_wait, profile=profile)
                if fill["status"] == "PENDING":
                    continue
                if fill["status"] == "MISSED":
                    # A MISS is a real outcome, never a zero — 90 of 232 in the
                    # v0.6 book, and the pure-maker cell exists to price exactly
                    # this: price walks away precisely when the trade was right.
                    results.append({"setup_id": sid, "symbol": symbol,
                                    "tf": tf, "outcome": "MISSED",
                                    "r": Decimal(0), "same_bar": False,
                                    "bars_held": 0, "filled": False})
                    continue
                i_fill = fill["fill_i"]
                entry = fill["entry"]          # the price PAID, not the plan's
                taker_in = fill["entry_role"] == "TAKER"
                out = _simulate(candles, atr, i_fill, entry, sl, tp, long, tf,
                                profile, managed, taker_in,
                                symbol=symbol, tf_seconds=TF_SECONDS[tf],
                                partials=partials, trail=trail,
                                timestop=timestop)
                if out is None:
                    continue
                if fill["note"]:
                    out["warnings"] = [fill["note"]]
                results.append({"setup_id": sid, "symbol": symbol, "tf": tf,
                                 "filled": True, **out})
    return results


def _cluster_bootstrap(rows, resamples: int) -> dict | None:
    """Bootstrap the mean by resampling SYMBOLS, not trades.

    The IID bootstrap in `edgestats` asks "if I drew these trades again one at
    a time, how much would the mean move". That question has the wrong shape
    for a playbook. A strategy fires on every symbol that meets its conditions,
    and when BTC turns, forty alt-coins turn with it — so the same market move
    is counted forty times as forty independent draws, and the interval comes
    out far tighter than the evidence supports. TREND_CONTINUATION has 3,567
    trades across 43 symbols; treating those as 3,567 independent facts is the
    single easiest way to manufacture a confident verdict here.

    Resampling whole symbols keeps the within-symbol correlation intact: a
    symbol is either in a resample with all its trades or out of it entirely.
    That is the standard cluster bootstrap, and it is deliberately the
    CONSERVATIVE choice — it widens intervals, so its failure mode is refusing
    to promote something that works, not promoting something that does not.

    Same deterministic LCG as `edgestats._bootstrap_mean`, and for the same
    reason (§4): two runs over identical data must resample identical clusters
    in identical order. Constants are the source module's.

    Returns None when there are too few CLUSTERS to say anything — four
    symbols' worth of trades is four observations however many rows it holds.
    """
    from . import edgestats
    clusters: dict[str, list[float]] = {}
    for r in rows:
        clusters.setdefault(r["symbol"], []).append(float(r["r"]))
    keys = sorted(clusters)
    k = len(keys)
    n_total = sum(len(clusters[c]) for c in keys)
    if k < MIN_CLUSTERS or n_total < edgestats.MIN_TRADES:
        return None
    s = 0x2545F4914F6CDD1D
    means = []
    for _ in range(resamples):
        tot, cnt = 0.0, 0
        for _ in range(k):
            s = (s * 6364136223846793005 + 1442695040888963407) & _MASK64
            for v in clusters[keys[(s >> 33) % k]]:
                tot += v
                cnt += 1
        means.append(tot / cnt if cnt else 0.0)
    means.sort()
    return {"resamples": resamples, "clusters": k,
            "ci_lo": means[int(0.025 * resamples)],
            "ci_hi": means[int(0.975 * resamples)],
            "p_gt_zero": sum(1 for m in means if m > 0) / resamples}


def by_strategy(con, symbols, tfs, versions=None, *, resamples=10000,
                beat=None) -> dict:
    """Replay the live book and split it by PLAYBOOK, with intervals.

    The aggregate hides the disagreement. Measured 4 Aug 2026 on 495 trades:
    REVERSAL +0.0792 R and PULLBACK -0.1511 R net to +0.0201 R, a number that
    describes neither and would have both playbooks judged by the average of a
    thing that works and a thing that does not.

    The bar is the house bar — an interval clear of zero, not a mean above it.
    Groups under `edgestats.MIN_TRADES` report their counts (those are facts)
    and no verdict, because the alternative is a confident number computed from
    nothing.

    THE CLUSTERED INTERVAL IS THE ONE THAT DECIDES. `ci_lo`/`ci_hi` are kept as
    the IID pair because they are what `edgestats` reports elsewhere and
    dropping them would make two surfaces disagree silently — but they are too
    tight for a playbook (see `_cluster_bootstrap`), and `clears_zero` is
    computed from the clustered pair alone.

    Measured on BREAKOUT_RETEST, 2026-08-11, n=79 over 32 symbols: IID
    [-0.7191, -0.0013] at 2,000 resamples and [-0.7149, +0.0001] at 4,000,
    against clustered [-0.750, +0.012] and [-0.7503, +0.0123]. Two things to
    read there. The clustered interval covers zero at both resample counts,
    while the IID upper bound FLICKERS ACROSS IT with nothing but the resample
    draw — a verdict of "measurably negative" that survives only at one
    setting of a knob is not a verdict. And the widening is modest here (32
    clusters, trades spread fairly evenly) which is worth knowing: clustering
    is not a large correction on this book, it is the correction that decides
    the one strategy sitting on the line.

    ENTRY MODEL IS READ, NOT ASSUMED. Each setup version is replayed under the
    `entry_model` its own facts recorded. Missing is a recorded answer too:
    execsim routes it through the direct-limit path, as the scale-in book did.
    A generation that records more than one answer is refused rather than
    squeezed through a model that describes neither.

    Read only through a TRUSTWORTHY calibration: the caller is responsible for
    checking `calibrate()` first, and this returns its verdict alongside so a
    result can never be quoted without it.
    """
    from . import edgestats, scalein
    from .setups import SETUP_VERSION
    versions = versions or (SETUP_VERSION, scalein.SCALE_VERSION)

    strategies = {}
    for symbol in symbols:
        for tf in tfs:
            for version in versions:
                for r in store.get_facts(con, symbol, tf, "setup", version):
                    p = json.loads(r["payload"])
                    strategies[(version, p["setup_id"])] = p.get("strategy")

    # THE GRADE AND ITS CERTIFICATE MUST COVER THE SAME BOOK. `calibrate()`
    # sets aside markets the record cannot hold a settlement for; graded here
    # anyway, those trades would ride into a published verdict under a
    # `trustworthy` flag that never checked them. Before the calibration was
    # scoped this was invisible, because the flag was permanently False and
    # nothing published at all — fixing one without the other is what turns a
    # stuck red light into a confident wrong one. Measured 8 Sep 2026: 140 of
    # 939 filled trades came from pairs calibration had declined to check.
    certified = certified_pairs(con, tfs)
    uncertified = 0

    groups: dict[str, list[dict]] = {}
    missed: dict[str, int] = {}
    model_conflicts = {}
    replay_degradations = []
    for version in versions:
        try:
            model = recorded_entry_model(con, symbols, tfs, version)
        except ValueError as exc:
            model_conflicts[version] = str(exc)
            continue
        # The per-symbol heartbeat carries the version so a supervisor log can
        # say WHICH generation's replay is running, not merely that one is.
        for r in run_variant(con, symbols, tfs, version, managed=False,
                             entry_model=model,
                             beat=None if beat is None else
                             (lambda s, v=version: beat(f"{v} {s}"))):
            for note in r.get("warnings") or ():
                replay_degradations.append({
                    "version": version, "setup_id": r["setup_id"],
                    "symbol": r["symbol"], "tf": r["tf"], "note": note})
            if (r["symbol"], r["tf"]) not in certified:
                # `filled` only, because that is what calibration counts. Two
                # published remainders for one set-aside that disagree about
                # its size is the kind of near-miss nobody reconciles.
                uncertified += 1 if r.get("filled") else 0
                continue
            name = strategies.get((version, r["setup_id"])) or "UNATTRIBUTED"
            if not r.get("filled"):
                missed[name] = missed.get(name, 0) + 1
                continue
            groups.setdefault(name, []).append(
                {"symbol": r["symbol"], "r": float(r["r"])})

    out = {}
    for name, rows in sorted(groups.items()):
        rs = [x["r"] for x in rows]
        wins = [x for x in rs if x > 0]
        losses = [x for x in rs if x < 0]
        b = (edgestats._bootstrap_mean(rs, resamples)
             if len(rs) >= edgestats.MIN_TRADES else None)
        cb = _cluster_bootstrap(rows, resamples)
        n_miss = missed.get(name, 0)
        out[name] = {
            "n": len(rs), "sum_r": round(sum(rs), 2),
            "expectancy_r": round(sum(rs) / len(rs), 4),
            "win_pct": round(100 * len(wins) / len(rs), 1),
            "profit_factor": (round(sum(wins) / abs(sum(losses)), 2)
                              if wins and losses else None),
            "ci_lo": None if b is None else round(b["ci_lo"], 4),
            "ci_hi": None if b is None else round(b["ci_hi"], 4),
            "p_gt_zero": None if b is None else b["p_gt_zero"],
            # Expectancy is PER FILLED TRADE. A miss is a real outcome and is
            # not a zero, so it is reported beside the number rather than
            # folded into it — a playbook that only fills when it is wrong
            # would otherwise read as merely unprofitable.
            "missed": n_miss,
            "fill_pct": (round(100 * len(rs) / (len(rs) + n_miss), 1)
                         if len(rs) + n_miss else None),
            "clusters": None if cb is None else cb["clusters"],
            "cluster_ci_lo": None if cb is None else round(cb["ci_lo"], 4),
            "cluster_ci_hi": None if cb is None else round(cb["ci_hi"], 4),
            "cluster_p_gt_zero": None if cb is None else cb["p_gt_zero"],
            "clears_zero": bool(cb and cb["ci_lo"] > 0),
            "sample_ok": cb is not None,
        }
    cal = calibrate(con, symbols, tfs, beat=beat, certified=certified)
    return {"version": ABTEST_VERSION,
            "calibration": cal,
            # Named next to the grades it is absent from, so a reader can see
            # how much of the replay this verdict declines to speak for.
            "uncertified_trades": uncertified,
            "trustworthy": (cal.get("trustworthy", False)
                            and not model_conflicts),
            "entry_model_conflicts": model_conflicts,
            "replay_degradations": replay_degradations,
            "strategies": out}


def summarise(results) -> dict:
    filled = [r for r in results if r.get("filled")]
    rs = [float(r["r"]) for r in filled]
    warnings = [note for r in results for note in (r.get("warnings") or ())]
    if not rs:
        return {"n": 0, "missed": sum(1 for r in results if not r.get("filled")),
                "note": "no filled trades — nothing to report",
                "warnings": warnings}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    same_bar_losers = [r for r in filled
                       if r.get("same_bar") and float(r["r"]) <= 0]
    n_loss = sum(1 for r in rs if r <= 0)
    return {
        "n": len(rs),
        "missed": sum(1 for r in results if not r.get("filled")),
        "win_pct": round(100 * len(wins) / len(rs), 1),
        "sum_r": round(sum(rs), 1),
        "expectancy_r": round(sum(rs) / len(rs), 4),
        "profit_factor": (round(sum(wins) / abs(sum(losses)), 2)
                          if losses and wins else None),
        # THE metric this whole version exists to move: 59% on the v0.6 book.
        "same_bar_stopout_pct": (round(100 * len(same_bar_losers) / n_loss, 1)
                                 if n_loss else None),
        "median_bars_held": sorted(r["bars_held"] for r in filled)[len(filled) // 2],
        "partial_rate_pct": round(
            100 * sum(1 for r in filled if r.get("partials")) / len(filled), 1),
        "warnings": warnings,
    }


def certified_pairs(con, tfs) -> set:
    """The (symbol, tf) pairs whose settlements the record can be expected to
    hold under the current EXEC_VERSION — everything else the replay
    produces is a market nobody has been asked about.

    `execsim` only runs for pairs the scanner still visits, so a version bump
    re-derives the live scan set and leaves every market that has since left
    the universe on the OLD version forever. The replay has no such boundary:
    it walks any symbol with stored candles. Measured 8 Sep 2026 at
    exec-v0.26-draft, that was 140 trades across 47 pairs last scanned 20-72
    hours earlier, and it kept calibration red against a rebuild that was
    never going to reach them.

    A pair qualifies on EITHER half:
      · it already holds a fact under this version — the engine has run here
        and produced output, so a trade missing from it is a real gap; or
      · its symbol is still in the scan set — the engine will reach it, so
        silence is a defect and not a market nobody is watching.

    NEITHER half is `engine_runs`. That is the obvious discriminator and it
    separates the same 140 exactly, but it is telemetry under a retention
    sweep, and `regrade.py` refuses it in the same words for the same reason:
    a grade must outlive a sweep. Scoped that way, a pair the engine ran and
    wrote NOTHING for reads as a defect until the sweep takes its run rows and
    is silently excused afterwards — the pin would lose its grip on exactly
    the interesting failure, on a timer, with nothing to connect the two. Both
    halves here are durable: facts are append-only, and the scan set is read
    from the universe fact rather than from telemetry.

    Coverage cannot shrink under this rule. A matched trade's pair holds its
    own fact, so the first half admits every trade the join could ever certify
    — verified on the store the day this was written: 140 set aside, 0 of 799
    matched excused, 0 unmatched left owed.
    """
    from . import universe
    from .execsim import EXEC_VERSION
    have = {(r[0], r[1]) for r in con.execute(
        "SELECT DISTINCT symbol, tf FROM facts "
        "WHERE kind='exec' AND algo_version=?", (EXEC_VERSION,))}
    return have | {(sym, tf) for sym in universe.scan_symbols(con) for tf in tfs}


def calibrate(con, symbols, tfs, tolerance=0.15, per_trade_r=0.01, *,
              beat=None, certified=None) -> dict:
    """Reproduce the RECORDED book TRADE BY TRADE, and say plainly whether we
    managed it.

    This is the harness's licence to be believed. It replays the generation the
    recorded book actually came from, under the conditions that produced it, and
    joins the result to the exec facts on disk BY setup_id.

    THE JOIN IS THE POINT. Comparing sum_r to sum_r asks "do these two books
    total the same", which 499 trades can answer yes to while disagreeing about
    every one of them. It also divides by a total that is near zero on any
    honest book — this one sums to 9.9 R — so a systematic +0.1207 R/trade bias
    across 76 trades showed as 0.716 and two structurally unreproducible trades
    showed as 0.256: two numbers of the same magnitude for a simulation defect
    and a population mismatch, which have nothing in common and different fixes.
    The ratio could say something was wrong. It could never say what.

    Matching per trade answers the question that was actually being asked:
      · `diverged` — trades both books have and price differently. Any at all
        means the replay is not the engine, and no tolerance makes that
        acceptable, because a difference in code is not a difference in degree.
      · `unmatched` — trades one book has and the other cannot see. A
        POPULATION difference, invisible to any per-trade comparison because
        there is nothing to compare, and invisible to any aggregate because it
        arrives as a magnitude rather than as a name.
      · `not_resimulated` — trades on pairs the current EXEC_VERSION has never
        run, which the record CANNOT hold and which therefore say nothing
        about the simulator. Set aside with a count rather than counted as a
        failure; `certified_pairs` explains why this does not blunt the
        pin.
    `drift_n` and `drift_sum_r` are still reported, as context rather than as
    the verdict.
    """
    import re
    from collections import Counter
    from .execsim import EXEC_VERSION
    recorded, generations, set_aside = {}, Counter(), 0
    for symbol in symbols:
        for tf in tfs:
            for r in store.get_facts(con, symbol, tf, "exec", EXEC_VERSION):
                p = json.loads(r["payload"])
                # LIKE FOR LIKE. A scale-in leg reuses its PARENT's setup_id
                # (scalein.py), so these facts carry `setup-v0.16-draft` in the
                # id while being produced by scale-v0.14 — and `run_variant` is
                # given one setup version, so it can never produce them. Counted
                # here, they were 2 trades and -2.07 R the replay was structurally
                # unable to reproduce, which on a book totalling 7.9 R showed as
                # 26% drift and kept calibration red after everything real had
                # been fixed. Grade the adds by replaying SCALE_VERSION, not by
                # folding them into a setup-version comparison.
                # Counted as `set_aside` rather than dropped in silence: a
                # calibration that certifies less than the whole book must say
                # how much less, or "OK" quietly stops meaning what it did.
                if p.get("strategy") == "SCALE_IN":
                    if p["outcome"] != "MISSED":
                        set_aside += 1
                    continue
                if p["outcome"] != "MISSED":
                    recorded[p["setup_id"]] = p
                m = re.search(r"setup-v[\d.]+-draft", p.get("setup_id") or "")
                if m:
                    generations[m.group(0)] += 1
    if not generations:
        return {"status": "UNAVAILABLE", "trustworthy": False,
                "detail": "no recorded book to calibrate against"}

    # WHICH GENERATION THE RECORDED BOOK ACTUALLY IS, derived rather than
    # assumed. This replayed a hardcoded "setup-v0.6-draft" — correct when the
    # harness was written as the gate on v0.7, and meaningless ten versions
    # later. Measured 4 Aug 2026: every one of the 499 recorded exec facts came
    # from setup-v0.16, so the harness was replaying one book and comparing it
    # against a different one, drifting 71.6% BY CONSTRUCTION and reporting its
    # own core as untrustworthy when the core was fine and the comparison was
    # wrong. A calibration that cannot go green is worse than none: it retires
    # the tool silently.
    version = generations.most_common(1)[0][0]

    # The conditions that PRODUCED that book, which are version-dependent.
    # v0.6/v0.7 were simulated touch-entry under the venue-blind Coinbase
    # default; everything since is the entry model the setup declares, exits
    # held to SL/TP (the managed exit was rejected by its own 2x2 gate — see
    # execsim line 105), and venue-derived costs.
    legacy = version in ("setup-v0.6-draft", "setup-v0.7-draft")

    # Scoped to what the record could possibly hold; see `certified_pairs`
    # for why neither half of that rule is the run log. A caller that grades
    # off the same replay passes ITS set in, so the certificate and the grade
    # cannot describe two different universe refreshes — recomputing here
    # after a minutes-long replay is a real window, and a symbol admitted or
    # dropped inside it would put the two out of step.
    certified = certified_pairs(con, tfs) if certified is None else certified

    replayed = run_variant(
        con, symbols, tfs, version, managed=False,
        entry_model="LIMIT_AT_EDGE" if legacy else "MAKER_THEN_MARKET",
        profile_override=costs.DEFAULT_COST_PROFILE if legacy else None,
        # Calibration replays the whole recorded book — the same minutes-long
        # dark window as the version replays, so it beats the same heartbeat.
        beat=None if beat is None else (lambda s: beat(f"calibrate {s}")))

    # Set aside rather than dropped in silence, the same contract `set_aside`
    # keeps for the scale-in adds: a calibration that certifies less than the
    # whole book must say how much less, or "OK" quietly stops meaning what it
    # did. Filtered BEFORE `summarise`, because `drift_n` and `drift_sum_r`
    # divide by the recorded book and a replay carrying trades that book
    # cannot contain reports a drift that is pure population.
    stranded = [r for r in replayed
                if (r["symbol"], r["tf"]) not in certified]
    replayed = [r for r in replayed
                if (r["symbol"], r["tf"]) in certified]
    not_resimulated = sum(1 for r in stranded if r.get("filled"))
    not_resimulated_pairs = len({(r["symbol"], r["tf"]) for r in stranded
                                 if r.get("filled")})

    rep = summarise(replayed)
    if not recorded or not rep.get("n"):
        return {"status": "UNAVAILABLE", "trustworthy": False,
                "detail": "no recorded book to calibrate against"}
    by_id = {r["setup_id"]: r for r in replayed if r.get("filled")}
    diverged, worst, matched = [], 0.0, 0
    for sid, p in recorded.items():
        got = by_id.get(sid)
        if got is None:
            continue
        matched += 1
        d = float(got["r"]) - float(p["r_multiple"])
        if abs(d) > abs(worst):
            worst = d
        if abs(d) > per_trade_r:
            diverged.append({"setup_id": sid, "recorded_r": p["r_multiple"],
                             "replayed_r": str(got["r"]),
                             "diff_r": round(d, 4)})
    only_recorded = [k for k in recorded if k not in by_id]
    only_replayed = [k for k in by_id if k not in recorded]

    rec_sum = sum(float(p["r_multiple"]) for p in recorded.values())
    rec_n = len(recorded)
    drift_n = abs(rep["n"] - rec_n) / rec_n
    denom = abs(rec_sum) or 1.0
    drift_r = abs(rep["sum_r"] - rec_sum) / denom
    ok = not diverged and not only_recorded and not only_replayed
    if ok:
        detail = (f"core reproduces the recorded book trade by trade — "
                  f"{matched} of {rec_n} matched, none differing by more than "
                  f"{per_trade_r} R"
                  + (f"; {set_aside} scale-in adds set aside, graded by "
                     f"replaying SCALE_VERSION" if set_aside else "")
                  + (f"; {not_resimulated} trades across "
                     f"{not_resimulated_pairs} pairs NOT CERTIFIED — "
                     f"{EXEC_VERSION} has not run for them, so the record "
                     f"holds no settlement to compare"
                     if not_resimulated else ""))
    elif diverged:
        d0 = diverged[0]
        detail = (f"REPLAY DISAGREES WITH THE RECORDED BOOK on {len(diverged)} "
                  f"of {matched} matched trades (worst {worst:+.4f} R, e.g. "
                  f"{d0['setup_id']} replayed {d0['replayed_r']} vs recorded "
                  f"{d0['recorded_r']}) — the 2x2 numbers below are NOT "
                  f"comparable to production and must not be used to accept or "
                  f"reject the change"
                  + (f"; a further {not_resimulated} trades across "
                     f"{not_resimulated_pairs} pairs were set aside as not "
                     f"re-settled under {EXEC_VERSION}"
                     if not_resimulated else ""))
    else:
        detail = (f"THE REPLAY AND THE RECORD ARE NOT LOOKING AT THE SAME "
                  f"TRADES: {len(only_recorded)} recorded trades the replay "
                  f"never produced, {len(only_replayed)} replayed trades the "
                  f"record does not contain. Every matched trade agrees, so "
                  f"this is a population difference, not a simulation one — "
                  f"the 2x2 numbers below still must not be used"
                  + (f" (a further {not_resimulated} trades across "
                     f"{not_resimulated_pairs} pairs were set aside as not "
                     f"re-settled under {EXEC_VERSION}, and are not part of "
                     f"this count)" if not_resimulated else ""))
    return {
        "status": "OK" if ok else "DRIFT",
        "trustworthy": ok,
        "recorded": {"n": rec_n, "sum_r": round(rec_sum, 1)},
        "replayed": {"n": rep["n"], "sum_r": rep["sum_r"]},
        "matched": matched,
        "diverged_n": len(diverged),
        "worst_trade_diff_r": round(worst, 4),
        "unmatched_recorded": len(only_recorded),
        "unmatched_replayed": len(only_replayed),
        "scale_in_set_aside": set_aside,
        # Trades the replay produced for pairs the current EXEC_VERSION has
        # never run. NOT a failure and NOT a pass: an uncertified remainder,
        # reported so "OK" says how much of the book it speaks for.
        "not_resimulated": not_resimulated,
        "not_resimulated_pairs": not_resimulated_pairs,
        "replay_degradations": rep.get("warnings") or [],
        "examples": diverged[:5] or (only_recorded + only_replayed)[:5],
        "per_trade_tolerance_r": per_trade_r,
        # Reported for continuity with what this pass used to return, and
        # because the aggregate is still worth seeing. It is no longer what
        # decides `trustworthy` — see the docstring.
        "drift_n": round(drift_n, 3), "drift_sum_r": round(drift_r, 3),
        "tolerance": tolerance,
        "detail": detail,
    }


CELLS = (
    ("touch_hold", "setup-v0.6-draft", False, "LIMIT_AT_EDGE",
     "v0.6 baseline"),
    ("touch_managed", "setup-v0.6-draft", True, "LIMIT_AT_EDGE",
     "isolates the EXIT fix"),
    ("confirmed_hold", "setup-v0.7-draft", False, "MARKET_NEXT_OPEN",
     "isolates the ENTRY fix"),
    ("confirmed_managed", "setup-v0.7-draft", True, "MARKET_NEXT_OPEN",
     "proposed v0.7"),
)


def report(con, symbols=None, tfs=("5m", "15m", "1H", "4H", "1D", "1W")) -> dict:
    from .universe import all_tracked_symbols
    symbols = symbols or all_tracked_symbols(con)
    # THE CELLS AND THE CERTIFICATE COVER THE SAME BOOK. `_verdict` returns
    # INDETERMINATE on an untrustworthy calibration and nothing else, so the
    # day scoping let that flag go green this surface would have started
    # publishing a real verdict over cells that still carried the markets
    # calibration had declined to check. Same hazard as the grade, one
    # function over; fixing one without the other is what turns a stuck red
    # light into a confident wrong one.
    certified = certified_pairs(con, tfs)
    cal = calibrate(con, symbols, tfs, certified=certified)
    cells = {}
    uncertified = 0
    for key, version, managed, entry_model, label in CELLS:
        res = run_variant(con, symbols, tfs, version, managed=managed,
                          entry_model=entry_model)
        uncertified += sum(1 for r in res if r.get("filled")
                           and (r["symbol"], r["tf"]) not in certified)
        res = [r for r in res if (r["symbol"], r["tf"]) in certified]
        cells[key] = {"label": label, "setup_version": version,
                      "managed_exit": managed, "entry_model": entry_model,
                      **summarise(res)}
    replay_degradations = [
        {"cell": key, "note": note}
        for key, cell in cells.items() for note in cell.get("warnings") or ()]
    return {"version": ABTEST_VERSION, "calibration": cal,
            "trustworthy": cal.get("trustworthy", False), "cells": cells,
            "uncertified_trades": uncertified,
            "replay_degradations": replay_degradations,
            "verdict": _verdict(cells, cal)}


def _verdict(cells, cal) -> dict:
    """State which change earned the result — including 'neither'."""
    if not cal.get("trustworthy"):
        return {"call": "INDETERMINATE",
                "detail": "calibration failed; no conclusion may be drawn"}
    base = cells.get("touch_hold", {})
    exit_only = cells.get("touch_managed", {})
    entry_only = cells.get("confirmed_hold", {})
    both = cells.get("confirmed_managed", {})
    if not base.get("n"):
        return {"call": "INDETERMINATE", "detail": "no baseline trades"}

    def exp(c):
        return c.get("expectancy_r")

    b = exp(base)
    improves = {k: (exp(c) is not None and b is not None and exp(c) > b)
                for k, c in (("exit", exit_only), ("entry", entry_only),
                             ("both", both))}
    small = [k for k, c in (("exit", exit_only), ("entry", entry_only),
                            ("both", both)) if (c.get("n") or 0) < 30]
    # "Both beat the baseline" is a shallow reading and would have shipped the
    # wrong thing here. What decides the change is whether the COMBINATION beats
    # the best single change — two fixes that each help alone can interact
    # badly, and that interaction is the entire reason this is a 2x2 rather than
    # two A/Bs.
    singles = {k: exp(c) for k, c in (("exit", exit_only), ("entry", entry_only))
               if exp(c) is not None}
    best_single = max(singles.values()) if singles else None
    combo = exp(both)
    # Precedence matters. "Nothing helped" must be decided BEFORE antagonism,
    # or a uniformly losing 2x2 gets reported as an interesting interaction —
    # and antagonism is only a meaningful call when both changes helped alone,
    # because that is the case where a naive reading would ship both.
    if not any(improves.values()):
        return {"call": "NEITHER_HELPS",
                "detail": ("neither change improves expectancy — the pullback "
                           "premise itself is the thing to re-open, and no "
                           "further strategies should be built on it"),
                "baseline_expectancy_r": b,
                "underpowered_cells": small,
                "caveat": ("cells with n<30 are reported but must not decide "
                           "anything" if small else None)}
    antagonistic = (improves["exit"] and improves["entry"]
                    and best_single is not None and combo is not None
                    and combo < best_single)
    if antagonistic:
        winner = max(singles, key=singles.get)
        call = "ANTAGONISTIC"
        detail = (f"both changes beat the baseline alone, but COMBINED they are "
                  f"worse than the '{winner}' change on its own "
                  f"({combo:+.4f}R vs {best_single:+.4f}R). Ship the single "
                  f"change that wins and re-test the other against it — "
                  f"shipping both would knowingly pick the weaker system.")
    elif improves["exit"] and not improves["entry"]:
        call = "EXIT_CARRIES_IT"
        detail = ("the managed exit improves expectancy and the confirmation "
                  "rule does not — per the spec, confirmation is optional "
                  "complexity and should be dropped, not shipped")
    elif improves["entry"] and not improves["exit"]:
        call = "ENTRY_CARRIES_IT"
        detail = "confirmation improves expectancy; the exit change is neutral here"
    elif improves["entry"] and improves["exit"]:
        call = "BOTH_HELP"
        detail = "both changes improve expectancy, and together beat either alone"
    else:
        call = "NEITHER_HELPS"
        detail = ("neither change improves expectancy — the pullback premise "
                  "itself is the thing to re-open, and no further strategies "
                  "should be built on it")
    return {"call": call, "detail": detail,
            "baseline_expectancy_r": b,
            "underpowered_cells": small,
            "caveat": ("cells with n<30 are reported but must not decide "
                       "anything" if small else None)}


def main():
    import sys
    con = store.connect()
    try:
        rep = report(con)
    finally:
        con.close()
    cal = rep["calibration"]
    print(f"\ncalibration: {cal['status']} — {cal['detail']}")
    if cal.get("recorded"):
        print(f"  recorded n={cal['recorded']['n']} sumR={cal['recorded']['sum_r']}"
              f"   replayed n={cal['replayed']['n']} sumR={cal['replayed']['sum_r']}")
    print(f"\n{'cell':22} {'n':>5} {'win%':>6} {'sumR':>8} {'exp R':>8} "
          f"{'sameBar%':>9} {'missed':>7}")
    for key, _, _, _, _ in CELLS:
        c = rep["cells"][key]
        print(f"{key:22} {c.get('n',0):>5} {c.get('win_pct','—'):>6} "
              f"{c.get('sum_r','—'):>8} {c.get('expectancy_r','—'):>8} "
              f"{c.get('same_bar_stopout_pct','—'):>9} {c.get('missed',0):>7}")
    v = rep["verdict"]
    print(f"\nVERDICT: {v['call']} — {v['detail']}")
    if v.get("caveat"):
        print(f"CAVEAT: {v['caveat']} ({', '.join(v['underpowered_cells'])})")
    if not rep["trustworthy"]:
        print("\nTHESE NUMBERS ARE NOT TRUSTWORTHY — calibration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
