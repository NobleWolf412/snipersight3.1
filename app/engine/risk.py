"""Risk Authority — §9: strategies request risk, this engine decides. Paper only.

Portfolio-scoped (one pass over ALL symbols/timeframes in strict time order —
risk is an account property, not a per-chart property). For every VALIDATED
setup intent, at its confirmed_at moment:
  1. settle any positions whose exits have occurred (equity moves),
  2. check the kill switch (daily realized loss beyond limit halts the day, §9/§13),
  3. check concurrent-position and total-open-risk limits (BTC and ETH count
     together — correlated crypto exposure),
  4. size the position: risk_usd = equity * RISK_PCT; units = risk_usd / stop
     distance; implied leverage capped by reducing size, never by widening
     stops (§9: stops are structure).
Decisions: APPROVED / REDUCED / REJECTED — each a fact with machine-readable
reasons (§8: rejections are as auditable as approvals).
"""
import json
from datetime import datetime, timezone
from decimal import Decimal

from . import store, venues
from .contracts import AutomationMode
from .setups import SETUP_VERSION
from .execsim import EXEC_VERSION, plan_versions as execsim_plan_versions
from .runlog import RunRecorder
from .universe import admitted_at

RISK_VERSION = "risk-v0.22-draft"
# v0.22: the envelope is restated in R — one R being one full stop-out at the
# per-trade risk — and only the R SIZE differs by mode. Paper is rehearsal for
# live: the gates (2R total open risk, 4R daily halt, one base position, 0R
# adds) are identical everywhere, so paper takes the same trades and halts at
# the same point in the same circumstances; only the dollar magnification
# changes. Paper/shadow size R at 2%, testnet/live at 0.25%. v0.21 had set one
# global 0.25% for every mode, which silently resized the research book and
# left 91 already-armed setup-v0.17 facts contradicting every number downstream.
# DECISION facts now record `risk_pct` and `pct_basis` so a fact explains
# itself without this module's constants. Known, deliberate: once mode reaches
# TESTNET the cockpit budgets show 0.25%-based numbers while the paper book
# continues enforcing 2% on itself — the paper replay is never mode-aware
# (a mode flip mid-baseline must not mint a second generation of DECISIONs).
# v0.21: first-live safety envelope — superseded by v0.22 before any facts
# were relied on; kept for the record. 0.25% per trade in all modes.
# v0.20: cascade from setup-v0.17 / exec-v0.21 / cooldown-v0.9 (the top-down
# bias block upstream). No sizing rule changed and this engine does not read
# `bias`; it replays the whole account from setup and exec facts, so a new
# generation of those is a new equity curve and a new set of decisions even
# when every rule is identical. Leaving the tag put is the S37/S40 defect.
# v0.19: cascade from setup-v0.16 / exec-v0.20 / cooldown-v0.8
# (magnitude-scaled WHY prices upstream).
# v0.18: cascade from setup-v0.15 / exec-v0.19 / cooldown-v0.7 (the same-bar
# pivot-pair fix upstream).
# v0.17: cascade from setup-v0.14 / exec-v0.18 / cooldown-v0.6 (swing-v0.9 at
# the root). risk replays the whole account from exec facts, so a new exec
# generation changes its decisions and equity curve even with no rule change.
# v0.16: cascade from exec-v0.17. risk replays the whole account from exec
# facts, so an exec version move changes this engine's inputs and therefore its
# decisions and equity curve — even though no rule here changed. Leaving the tag
# put is the S37/S40 defect: two generations under one label.
# v0.13: cascade from exec-v0.14. The account replay is built from exec facts,
# and exec-v0.14 corrects a crossing leg that booked market fills at a price the
# bar never traded. Every equity figure downstream of those fills changes, so
# this tag moves with them rather than covering two generations of the book.
# v0.12: reads setup-v0.11 / exec-v0.13.

# v0.11: reads exec-v0.12, which now charges funding. Net R per trade moves,
# so equity and every sizing decision downstream of it moves.

# v0.10: reads setup-v0.10 / exec-v0.11. Sizing rules unchanged, but the math
# now lives in the pure `size_order` helper this module still owns (plan
# Phase C ruling, option A) and setups.py calls it at arming time.

# v0.9: sizing rules unchanged. Reads setup-v0.9 / exec-v0.10, plus the new
# participation cap (D4). Different intents and a new constraint -> different
# decisions.

# v0.8: no sizing rule changed. Its INPUTS did — this engine reads setup facts
# at SETUP_VERSION and exec facts at EXEC_VERSION, and S40 moved both
# (setup-v0.8, exec-v0.9) after the tick fix reclassified regimes on 35 of 59
# symbols. Different intents, different exits, different decisions. Leaving the
# tag at v0.7 would have written a second incompatible book under a label that
# already means something — the exact S37 defect, which this project has now
# committed twice and should stop committing.

# v0.7: shorting, leverage and the liquidation gate are venue-derived. Sizing
# rules (2%/4%/6%) are unchanged, but SHORT setups on a shorts-capable venue now
# reach sizing instead of being rejected outright, so decisions differ.
# v0.6: account accounting is scoped to the active non-destructive forward
# baseline. Strategy eligibility and sizing rules are unchanged.
# v0.4 (user directive 2026-07-21): per-trade risk 1% -> 2%. Coherently
# re-tuned the whole envelope so the concurrency and kill-switch don't silently
# break: total cap 2% -> 4% (keeps 2 concurrent at 2% each), daily halt 3% ->
# 6% (~3 stop-outs, not ~1.5), scale-in add 0.5% -> 1% (stays half a base).
# v0.2: governs SCALE_IN adds — exempt from the concurrency count (attach to a
# parent) but consume the total-open-risk budget; REJECTED with PARENT_CLOSED
# if the parent position already exited.
START_EQUITY = Decimal("10000")

# ---------------------------------------------------------------- the gates
#
# Stated in R, once, and identical in every mode. R-multiples are
# size-invariant, so two books running these gates at different R sizes take
# the SAME trades, halt at the SAME point, and produce the SAME R
# distribution — which is what makes paper a rehearsal rather than a
# different system. The only mode-dependent number is MODE_RISK_PCT.
MAX_OPEN_R = Decimal("2")            # total open risk: 2 full stop-outs
DAILY_LOSS_R = Decimal("4")          # realized -4R in a UTC day -> halt
MAX_CONCURRENT = 1                   # one base position; adds don't count
SCALE_ADD_R = Decimal("0")           # pyramiding forbidden by contract

# One R, by mode. OFF maps to paper because the research book keeps running
# when dispatch is off — OFF is "no orders leave", not "no research happens".
MODE_RISK_PCT = {
    AutomationMode.OFF:     Decimal("0.02"),
    AutomationMode.PAPER:   Decimal("0.02"),
    AutomationMode.SHADOW:  Decimal("0.02"),
    AutomationMode.TESTNET: Decimal("0.0025"),
    AutomationMode.LIVE:    Decimal("0.0025"),
}


def gates_for_mode(mode) -> dict:
    """THE authority on the envelope. Every reader — the replay, the sizer,
    the API, diagnostics — gets its numbers here or from a fact this wrote.
    A module-level pct constant is exactly the bug v0.21 shipped: a reader
    that never states its mode reports a number some book is not using.
    """
    pct = MODE_RISK_PCT[mode]        # KeyError on an unknown mode, on purpose
    return {
        "risk_pct": pct,
        "scale_risk_pct": (SCALE_ADD_R * pct),
        "max_total_open_risk_pct": (MAX_OPEN_R * pct),
        "daily_loss_limit_pct": (DAILY_LOSS_R * pct),
        "max_concurrent": MAX_CONCURRENT,
        "max_open_r": MAX_OPEN_R,
        "daily_loss_r": DAILY_LOSS_R,
    }


def dispatch_scale(mode) -> Decimal:
    """Quantity scale from the paper-sized risk fact to this mode's R.

    The replay sizes the research book at paper R unconditionally (see
    run()); a TESTNET/LIVE order built from that fact must be scaled down or
    the first real order goes out 8x oversize. Exact by construction:
    0.0025 / 0.02 == 0.125.
    """
    return MODE_RISK_PCT[mode] / MODE_RISK_PCT[AutomationMode.PAPER]
# v0.7: shorting and leverage are VENUE capabilities, not process constants.
# As globals they rejected 31% of all validated setups (44 of 143) — every SHORT
# the playbook produced — because the only declared venue was Coinbase spot.
# `venues.venue_for(symbol)` now answers both, and a leveraged perp additionally
# has to prove its stop triggers before liquidation.
# The kept names below are the SPOT defaults, retained so any caller that has
# not been migrated still gets the conservative answer rather than a crash.
MAX_LEVERAGE = Decimal("1")              # spot default; see venues.max_leverage
ALLOW_SHORTS = False                     # spot default; see venues.allow_shorts
MIN_NOTIONAL_USD = Decimal("1")
# D4 — participation cap (SALVAGE §3.6). `universe.py` gates which SYMBOLS are
# liquid enough to trade; nothing gated whether a given POSITION is too large
# for the book it has to fill in. Those are different questions: a $3M/day pair
# clears the universe floor and still cannot absorb a position sized off a very
# tight stop without moving against you on both legs.
#
# Expressed as a share of the symbol's own 24h volume, which the universe fact
# already records — so this reads a number the system owns rather than inventing
# a second liquidity model. Inert in paper (no fills to move), which is exactly
# why it must exist BEFORE live: it is a constraint the simulator cannot teach.
MAX_PARTICIPATION = Decimal("0.005")          # 0.5% of 24h volume
# The daily halt is DAILY_LOSS_R x one R — see gates_for_mode(). It has no
# module constant on purpose: as a bare pct it silently stopped meaning "four
# losers" when the R size moved (at 2% R a 1% cap halted on the FIRST loss).
MIN_REDUCED_FRACTION = Decimal("0.25")      # reduce below 25% of intended -> reject
QC = Decimal("0.01")

TFS = ("5m", "15m", "1H", "4H", "1D", "1W")


def _venue_allows_shorts(symbol: str) -> bool:
    """Venue capability. An unrecognised symbol falls back to the SPOT answer —
    refusing the short — because assuming a market is shortable when it is not
    would record trades that could never have been placed."""
    try:
        return venues.allow_shorts(symbol)
    except ValueError:
        return ALLOW_SHORTS


def _venue_max_leverage(symbol: str) -> Decimal:
    """Same conservative fallback: 1x when the venue is unknown."""
    try:
        return venues.max_leverage(symbol)
    except ValueError:
        return MAX_LEVERAGE


def size_order(*, equity, entry, sl, direction, symbol, risk_pct=None,
               base_risk_pct=None, open_risk=Decimal(0), vol24=None,
               is_add=False) -> dict:
    """PURE sizing. No I/O, no facts, no clock — equity and a bracket in, a
    decision out.

    Defaults are PAPER's R deliberately: the callers that omit `risk_pct` are
    the arming pass and the replay, both of which walk historical bars and
    must stay deterministic — they must never consult the operating mode.
    Mode-aware callers pass `risk_pct` explicitly from gates_for_mode().
    `base_risk_pct` denominates the open-risk budget (2R of the BASE trade
    even when `risk_pct` itself is an override or an add).

    Extracted per the `forming-armed-order-plan` Phase C ruling (option A):
    §9 says the risk authority owns sizing, and it still does — this module owns
    the code. What changes is that `setups.py` can now CALL it at the moment a
    setup is armed, instead of the size being computed later at execution time.
    That is the whole point of the armed order: the thing that gets executed is
    the thing that was decided, provably, rather than something recomputed under
    different conditions and hoped to match.

    Everything the portfolio pass knows that this cannot — the kill switch, the
    concurrency count, cooldowns, point-in-time universe eligibility — stays in
    `run()`. Those are properties of the ACCOUNT at a moment; this is a property
    of one order. Mixing them here would make sizing untestable and would let a
    FORMING fact claim an approval the portfolio never granted.
    """
    reasons: list = []
    decision = "APPROVED"
    paper = gates_for_mode(AutomationMode.PAPER)
    pct = risk_pct if risk_pct is not None else (
        paper["scale_risk_pct"] if is_add else paper["risk_pct"])
    base_pct = base_risk_pct if base_risk_pct is not None else paper["risk_pct"]
    if pct <= 0:
        # 0R is the contract saying this order type does not exist (adds,
        # today). Falling through here used to produce a misleading
        # BELOW_MIN_NOTIONAL — or, in run(), a silent APPROVED at zero size.
        # The reason names the actual condition: an add hit the 0R contract,
        # anything else was handed a non-positive pct explicitly.
        return {"decision": "REJECTED",
                "reasons": ["SCALE_IN_FORBIDDEN" if is_add else "ZERO_RISK_SIZE"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": "0.00"}
    intended = (equity * pct).quantize(QC)
    risk_usd = intended
    stop_dist = abs(entry - sl)
    if stop_dist <= 0:
        return {"decision": "REJECTED", "reasons": ["INVALID_STOP_DISTANCE"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": str(intended)}

    budget = (MAX_OPEN_R * base_pct * equity - open_risk).quantize(QC)
    if budget < intended:
        if budget < intended * MIN_REDUCED_FRACTION:
            return {"decision": "REJECTED", "reasons": ["EXPOSURE_LIMIT"],
                    "risk_usd": Decimal(0), "units": Decimal(0),
                    "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                    "intended_risk_usd": str(intended)}
        decision, reasons = "REDUCED", ["EXPOSURE_LIMIT"]
        risk_usd = budget

    venue_lev = _venue_max_leverage(symbol)
    units = risk_usd / stop_dist
    notional = units * entry
    lev = notional / equity if equity > 0 else Decimal(0)
    if lev > venue_lev:
        risk_usd = (risk_usd * (venue_lev / lev)).quantize(QC)
        units = risk_usd / stop_dist
        notional = units * entry
        lev = venue_lev
        if decision == "APPROVED":
            decision = "REDUCED"
        reasons.append(f"LEVERAGE_CAP({venue_lev}x)")

    ok, liq = venues.stop_survives_liquidation(entry, sl, lev, direction)
    if not ok:
        return {"decision": "REJECTED",
                "reasons": [f"STOP_BEYOND_LIQUIDATION({liq.quantize(QC)}"
                            f"@{lev.quantize(QC)}x)"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": str(intended)}

    if units * entry < MIN_NOTIONAL_USD:
        return {"decision": "REJECTED", "reasons": ["BELOW_MIN_NOTIONAL"],
                "risk_usd": Decimal(0), "units": Decimal(0),
                "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                "intended_risk_usd": str(intended)}

    if vol24:
        cap = MAX_PARTICIPATION * Decimal(str(vol24))
        if notional > cap > 0:
            risk_usd = (risk_usd * cap / notional).quantize(QC)
            units = risk_usd / stop_dist
            notional = units * entry
            lev = notional / equity if equity > 0 else Decimal(0)
            if decision == "APPROVED":
                decision = "REDUCED"
            reasons.append(
                f"PARTICIPATION_CAP({float(MAX_PARTICIPATION)*100:.1f}%_of_24h)")
            if risk_usd < intended * MIN_REDUCED_FRACTION:
                return {"decision": "REJECTED", "reasons": ["PARTICIPATION_TOO_THIN"],
                        "risk_usd": Decimal(0), "units": Decimal(0),
                        "notional_usd": Decimal(0), "implied_leverage": Decimal(0),
                        "intended_risk_usd": str(intended)}

    return {"decision": decision, "reasons": reasons or ["WITHIN_LIMITS"],
            "risk_usd": risk_usd,
            "units": units.quantize(Decimal("0.00000001")),
            "notional_usd": notional.quantize(QC),
            "implied_leverage": lev.quantize(QC),
            "intended_risk_usd": str(intended)}


def _symbols(con):
    """Every symbol with stored candles — portfolio scope spans the universe."""
    from .universe import all_tracked_symbols
    return all_tracked_symbols(con)


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def run(con) -> dict:
    with RunRecorder(con, "risk", RISK_VERSION, "PORTFOLIO", "ALL") as rec:
        baseline = store.get_active_baseline(con)
        baseline_start = baseline["started_at"]
        # PAPER unconditionally, never the operating mode. The replay
        # re-derives every DECISION from the first bar of the baseline each
        # cycle, and facts are content-hashed: a mode flip mid-baseline would
        # append a second full generation of DECISIONs under this one version
        # label. Mode is operational state; it never rewrites research.
        gates = gates_for_mode(AutomationMode.PAPER)
        intents, exits = [], {}
        for sym in _symbols(con):
            for tf in TFS:
                # execsim owns the definition of what the book trades; risk
                # sizes exactly that set and never a wider one.
                for ver in execsim_plan_versions():
                    for r in store.get_facts(con, sym, tf, "setup", ver):
                        p = json.loads(r["payload"])
                        if (p["state"] == "VALIDATED" and
                                r["confirmed_at"] >= baseline_start):
                            intents.append({"symbol": sym, "tf": tf,
                                            "market_time": r["market_time"],
                                            "confirmed_at": r["confirmed_at"],
                                            "universe_eligible": admitted_at(
                                                con, sym, r["confirmed_at"]), **p})
                for r in store.get_facts(con, sym, tf, "exec", EXEC_VERSION):
                    p = json.loads(r["payload"])
                    exits[p["setup_id"]] = {"exit_ts": r["confirmed_at"],
                                            "r_net": Decimal(p["r_multiple"]),
                                            "outcome": p["outcome"]}
        intents.sort(key=lambda i: (i["confirmed_at"], i["market_time"], i["setup_id"]))
        rec.n_inputs = len(intents)

        equity = START_EQUITY
        open_pos: list[dict] = []
        daily_pnl: dict[str, Decimal] = {}
        day_start_equity: dict[str, Decimal] = {}
        halted: set[str] = set()
        curve: list[dict] = []
        n = {"APPROVED": 0, "REDUCED": 0, "REJECTED": 0, "KILL": 0}
        n_new_facts = 0

        _peak_box = [START_EQUITY]
        _dd_box: list = [None]

        def _set_peak(v):
            _peak_box[0] = v

        def _dd_halted():
            return _dd_box[0] is not None

        def _trip_dd(info):
            _dd_box[0] = info

        def settle(up_to_ts):
            nonlocal equity, n_new_facts
            for p in sorted([p for p in open_pos if p["exit_ts"] and p["exit_ts"] <= up_to_ts],
                            key=lambda p: p["exit_ts"]):
                d = _day(p["exit_ts"])
                day_start_equity.setdefault(d, equity)
                pnl = (p["risk_usd"] * p["r_net"]).quantize(QC)
                equity = (equity + pnl).quantize(QC)
                daily_pnl[d] = daily_pnl.get(d, Decimal(0)) + pnl
                curve.append({"ts": p["exit_ts"], "equity": str(equity)})
                open_pos.remove(p)
                # Total-drawdown guardrail. The daily halt catches a bad DAY;
                # this catches a bad month that never trips it — a slow bleed of
                # small losses can drain the account without any single day
                # breaching -6%.
                if equity > _peak_box[0]:
                    _set_peak(equity)
                dd_limit = Decimal(str(opcfg["max_drawdown_pct"])) / Decimal(100)
                if dd_limit > 0 and _peak_box[0] > 0:
                    dd = (_peak_box[0] - equity) / _peak_box[0]
                    if dd >= dd_limit and not _dd_halted():
                        _trip_dd({"at": p["exit_ts"], "peak": str(_peak_box[0]),
                                  "equity": str(equity),
                                  "drawdown_pct": str((dd * 100).quantize(QC))})
                        if store.insert_fact(
                                con, symbol="PORTFOLIO", tf="ALL", kind="risk",
                                market_time=p["exit_ts"], confirmed_at=p["exit_ts"],
                                algo_version=RISK_VERSION,
                                payload={"event": "DRAWDOWN_HALT",
                                         "peak_equity": str(_peak_box[0]),
                                         "equity": str(equity),
                                         "drawdown_pct": str((dd * 100).quantize(QC)),
                                         "limit_pct": str(opcfg["max_drawdown_pct"]),
                                         "baseline_id": baseline["id"],
                                         "reason": "total drawdown limit reached "
                                                   "— no new entries this window"}):
                            n_new_facts += 1
                loss_limit = gates["daily_loss_limit_pct"] * day_start_equity[d]
                if d not in halted and daily_pnl[d] <= -loss_limit:
                    halted.add(d)
                    n["KILL"] += 1
                    if store.insert_fact(
                            con, symbol="PORTFOLIO", tf="ALL", kind="risk",
                            market_time=p["exit_ts"], confirmed_at=p["exit_ts"],
                            algo_version=RISK_VERSION,
                            payload={"event": "KILL_SWITCH", "day": d,
                                     "daily_pnl": str(daily_pnl[d]),
                                     "day_start_equity": str(day_start_equity[d]),
                                     "loss_limit_usd": str(loss_limit),
                                     "loss_limit_r": str(gates["daily_loss_r"]),
                                     "risk_pct": str(gates["risk_pct"]),
                                     "pct_basis": "PAPER",
                                     "equity": str(equity),
                                     "baseline_id": baseline["id"],
                                     "baseline_started_at": baseline_start,
                                     "reason": "daily loss limit reached — no new entries today"}):
                        n_new_facts += 1

        # Operator halt and strategy toggles. Read once per run so a mid-run
        # edit cannot approve half the intents under one policy and half under
        # another. A halt blocks NEW entries only — open positions still settle,
        # because refusing to close a position is not a safety feature.
        from . import settings as _settings
        opcfg = _settings.all_settings(con)
        # Cooldowns are loaded ONCE and evaluated in memory. `active_at` runs a
        # query; calling it per intent inside the loop below would issue two
        # round-trips per candidate across hundreds of intents, on the hot path
        # of every scan cycle.
        from . import cooldowns as _cooldowns
        _cd_facts = _cooldowns.load(con, baseline_start=baseline_start)
        # 24h volume per symbol, read from the latest universe fact. One
        # authority: `universe.py` already measures this to decide admission,
        # and re-deriving it here would give two numbers that drift.
        _vol24: dict = {}
        try:
            from .universe import UNIVERSE_VERSION
            _row = con.execute(
                "SELECT payload FROM facts WHERE kind='universe' AND algo_version=? "
                "ORDER BY id DESC LIMIT 1", (UNIVERSE_VERSION,)).fetchone()
            if _row:
                for _m in json.loads(_row[0])["members"]:
                    if _m.get("vol_usd"):
                        _vol24[_m["symbol"]] = _m["vol_usd"]
        except Exception:
            _vol24 = {}          # no universe fact yet -> cap simply inert
        # Data-health gate. Trading on data the audit says is BROKEN produces a
        # forward record that proves nothing — the results would be attributable
        # to the corruption as much as to the strategy.
        data_blocked = False
        if opcfg["halt_on_data_blocked"]:
            try:
                from . import quality
                rep = quality.cached_audit(con)
                data_blocked = bool(rep) and not rep.get("evaluation_allowed", True)
            except Exception:
                data_blocked = False          # never block on the gate itself failing
        _strategy_on = {
            "PULLBACK": opcfg["strategy_pullback"],
            "REVERSAL": opcfg["strategy_reversal"],
            "SCALE_IN": opcfg["strategy_scale_in"],
        }

        for it in intents:
            ts = it["confirmed_at"]
            settle(ts)
            entry, sl = Decimal(it["entry"]), Decimal(it["sl"])
            stop_dist = abs(entry - sl)
            reasons, decision = [], "APPROVED"
            is_add = it["strategy"] == "SCALE_IN"
            intended = (equity * (gates["scale_risk_pct"] if is_add
                                  else gates["risk_pct"])).quantize(QC)
            risk_usd = intended

            parents_open = {p["setup_id"] for p in open_pos}
            if opcfg["halted"]:
                decision, reasons = "REJECTED", ["OPERATOR_HALT"]
            elif data_blocked:
                decision, reasons = "REJECTED", ["DATA_HEALTH_BLOCKED"]
            elif _dd_halted():
                decision, reasons = "REJECTED", [
                    f"DRAWDOWN_HALT({_dd_box[0]['drawdown_pct']}%)"]
            elif not _strategy_on.get(it["strategy"], True):
                decision, reasons = "REJECTED", [f"STRATEGY_DISABLED({it['strategy']})"]
            elif _cooldowns.blocked_at(_cd_facts, ts, it["symbol"],
                                       it["direction"]) is not None:
                # Re-entry control. Nothing stopped this system from buying a
                # level again the bar after it stopped out — tolerable while
                # REVERSAL fired 5 times in four years, not once it fires 471.
                # The cooldown FACT is carried into the reason so the operator
                # sees which exit caused the lockout, not just that one exists.
                _cd = _cooldowns.blocked_at(_cd_facts, ts, it["symbol"],
                                            it["direction"])
                decision = "REJECTED"
                reasons = [f"COOLDOWN({_cd['outcome']},{_cd['hours']}h)"]
            elif _day(ts) in halted:
                decision, reasons = "REJECTED", ["DAILY_LOSS_HALT"]
            elif not it["universe_eligible"]:
                decision, reasons = "REJECTED", ["NOT_IN_POINT_IN_TIME_UNIVERSE"]
            elif stop_dist <= 0:
                decision, reasons = "REJECTED", ["INVALID_STOP_DISTANCE"]
            elif it["direction"] == "SHORT" and not _venue_allows_shorts(it["symbol"]):
                decision, reasons = "REJECTED", ["SHORT_UNSUPPORTED_COINBASE_SPOT"]
            elif is_add and gates["scale_risk_pct"] <= 0:
                # The 0R gate, stated. Without this branch a permitted add
                # fell through to intended = equity * 0 and booked APPROVED
                # at zero size — the arithmetic enforced the contract and
                # nothing said so (audit 2026-08-08, finding 4).
                decision, reasons = "REJECTED", ["SCALE_IN_FORBIDDEN(0R)"]
            elif is_add and it.get("parent_setup_id") not in parents_open:
                decision, reasons = "REJECTED", ["PARENT_CLOSED"]
            elif not is_add and sum(1 for p in open_pos if "|ADD" not in p["setup_id"]) >= gates["max_concurrent"]:
                decision, reasons = "REJECTED", [f"CONCURRENT_LIMIT({gates['max_concurrent']})"]
            else:
                open_risk = sum(p["risk_usd"] for p in open_pos)
                budget = (gates["max_total_open_risk_pct"] * equity - open_risk).quantize(QC)
                if budget < intended:
                    if budget < intended * MIN_REDUCED_FRACTION:
                        decision, reasons = "REJECTED", ["EXPOSURE_LIMIT"]
                    else:
                        decision, reasons = "REDUCED", ["EXPOSURE_LIMIT"]
                        risk_usd = budget
                venue_lev = _venue_max_leverage(it["symbol"])
                if decision != "REJECTED" and stop_dist > 0:
                    units = risk_usd / stop_dist
                    notional = units * entry
                    lev = notional / equity
                    if lev > venue_lev:
                        scale = venue_lev / lev
                        risk_usd = (risk_usd * scale).quantize(QC)
                        units = risk_usd / stop_dist
                        notional = units * entry
                        lev = venue_lev
                        if decision == "APPROVED":
                            decision = "REDUCED"
                        reasons.append(f"LEVERAGE_CAP({venue_lev}x)")

                    # Liquidation gate. On a leveraged perp the exchange can
                    # close the position before the stop is reached, at a loss
                    # LARGER than the one that was risked — which makes the stop
                    # decorative and every R-multiple downstream fiction.
                    ok, liq = venues.stop_survives_liquidation(
                        entry, sl, lev, it["direction"])
                    if not ok:
                        decision = "REJECTED"
                        reasons = [f"STOP_BEYOND_LIQUIDATION({liq.quantize(QC)}"
                                   f"@{lev.quantize(QC)}x)"]

                if decision != "REJECTED" and risk_usd > 0:
                    units = risk_usd / stop_dist
                    if units * entry < MIN_NOTIONAL_USD:
                        decision, reasons = "REJECTED", ["BELOW_MIN_NOTIONAL"]

                # Participation cap. REDUCES rather than rejects: a position too
                # large for the book is not a bad trade, it is a bad SIZE, and
                # the correct answer to a bad size is a smaller one.
                vol24 = _vol24.get(it["symbol"])
                if decision != "REJECTED" and vol24 and risk_usd > 0:
                    units = risk_usd / stop_dist
                    notional = units * entry
                    cap = MAX_PARTICIPATION * Decimal(str(vol24))
                    if notional > cap > 0:
                        risk_usd = (risk_usd * cap / notional).quantize(QC)
                        if decision == "APPROVED":
                            decision = "REDUCED"
                        reasons.append(
                            f"PARTICIPATION_CAP({float(MAX_PARTICIPATION)*100:.1f}%_of_24h)")
                        if risk_usd < intended * MIN_REDUCED_FRACTION:
                            decision, reasons = "REJECTED", ["PARTICIPATION_TOO_THIN"]
                            risk_usd = Decimal(0)

            if decision != "REJECTED" and risk_usd <= 0:
                # Belt and braces: no zero-size position may ever book as
                # APPROVED. Every legitimate zero already carries a REJECTED
                # above; reaching here means a new code path leaked one.
                decision, reasons = "REJECTED", ["ZERO_RISK_SIZE"]
            if decision == "REJECTED":
                risk_usd = Decimal(0)
            payload = {"event": "DECISION", "setup_id": it["setup_id"],
                       "decision": decision, "reasons": reasons or ["WITHIN_LIMITS"],
                       "intended_risk_usd": str(intended), "risk_usd": str(risk_usd),
                       "risk_pct": str(gates["risk_pct"]), "pct_basis": "PAPER",
                       "equity_at": str(equity), "baseline_id": baseline["id"],
                       "baseline_started_at": baseline_start}
            if decision != "REJECTED" and stop_dist > 0:
                units = (risk_usd / stop_dist)
                payload.update({"units": str(units.quantize(Decimal("0.00000001"))),
                                "notional_usd": str((units * entry).quantize(QC)),
                                "implied_leverage": str((units * entry / equity).quantize(QC))})
                ex = exits.get(it["setup_id"])
                payload["fill_outcome"] = ex["outcome"] if ex else "PENDING"
                if ex is None or ex["outcome"] != "MISSED":
                    open_pos.append({"setup_id": it["setup_id"], "risk_usd": risk_usd,
                                     "exit_ts": ex["exit_ts"] if ex else None,
                                     "r_net": ex["r_net"] if ex else Decimal(0)})
            n[decision] += 1
            if store.insert_fact(con, symbol=it["symbol"], tf=it["tf"], kind="risk",
                                 market_time=it["market_time"], confirmed_at=ts,
                                 algo_version=RISK_VERSION, payload=payload):
                n_new_facts += 1

        settle(2**53)
        # authoritative account summary — the UI reads THIS, never re-derives
        # equity (a second reconstruction would drift from the compounding +
        # kill-switch accounting done here). §8: one source of truth.
        peak = float(START_EQUITY)
        maxdd = 0.0
        for pt in curve:
            e = float(pt["equity"])
            peak = max(peak, e)
            maxdd = max(maxdd, (peak - e) / peak * 100 if peak else 0)
        # deterministic anchor: last settlement (not wall-clock) so a re-run over
        # identical data produces a byte-identical summary fact (idempotent).
        summ_ts = int(curve[-1]["ts"]) if curve else baseline_start
        if store.insert_fact(
                con, symbol="PORTFOLIO", tf="ALL", kind="account",
                market_time=summ_ts, confirmed_at=summ_ts,
                algo_version=RISK_VERSION,
                payload={"event": "SUMMARY", "start_equity": str(START_EQUITY),
                         "final_equity": str(equity),
                         "risk_pct": str(gates["risk_pct"]), "pct_basis": "PAPER",
                         "baseline_id": baseline["id"],
                         "baseline_started_at": baseline_start,
                         "baseline_label": baseline["label"],
                         "return_pct": str(((equity / START_EQUITY - 1) * 100).quantize(QC)),
                         "max_drawdown_pct": round(maxdd, 2),
                         "decisions": n, "curve": curve,
                         # The account can now span venues, so the contract is a
                         # list of what each ALLOWS rather than one hard-coded
                         # claim about Coinbase.
                         "venue_contract": {
                             "venues_version": venues.VENUES_VERSION,
                             "venues": [{"venue": v.key, "kind": v.kind,
                                         "allow_shorts": v.allow_shorts,
                                         "max_leverage": str(v.max_leverage),
                                         "cost_profile": v.cost_profile}
                                        for v in venues.ALL]}}):
            n_new_facts += 1
        con.commit()
        rec.n_new_facts = n_new_facts
        rec.notes = f"baseline={baseline['id']} final_equity={equity}"
        return {"final_equity": str(equity), **n}
