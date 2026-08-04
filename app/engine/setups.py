"""Setup detector — pullback playbook. algo setup-v0.1-draft.

The strategy layer consumes ONLY confirmed facts through the same as_of
semantics as the chart (§3: no layer skipping — this engine never looks at
candles to form an opinion, only to measure ATR/volume at the trigger bar).

Draft playbook (user's regime->strategy mapping; versioned):
- LONG:  regime BULL_TREND at touch time + price touches a DEMAND zone.
- SHORT: regime BEAR_TREND at touch time + price touches a SUPPLY zone.
- Entry = zone edge nearest price (top of demand / bottom of supply).
- SL    = structural invalidation: far edge of zone -/+ 0.25 ATR (§9: stops
  are structure, not percentages).
- TP    = nearest unbroken liquidity pool beyond entry; fallback: nearest
  INTERMEDIATE/MAJOR opposing swing. No target -> no setup.
- Gate  = R:R >= 1.5 or the setup is never emitted.
- Rank  = deterministic confluence score 0-100 (NOT a probability, §25):
  base 50 + sweep-nearby 20 + touch-bar volume 15 + R:R >= 2.5 15.
- Lifecycle: VALIDATED at zone touch; EXPIRED when the zone breaks.
Every setup carries a plain-language WHY assembled from the facts it used (§8).
"""
import json
from decimal import Decimal

from . import store
from .swings import compute_atr, quote_ticks, SWING_VERSION
from .zones import ZONE_VERSION
from .liquidity import LIQ_VERSION
from .regime import REGIME_VERSION
from .runlog import RunRecorder
from . import costs

SETUP_VERSION = "setup-v0.16-draft"
# v0.16: WHY text writes prices with magnitude-scaled decimals (`_fp`, chart.js
# `digits()` exactly) instead of a flat .2f, which rendered every sub-dollar
# zone as a degenerate range — ENA's journal read "supply zone 0.09-0.09", and
# its TP was the same two digits. No strategy rule changed, but the WHY lives
# inside the content-hashed fact: re-derived under v0.15 the new bytes would
# append a near-duplicate of every recorded candidate (the S53 shape).
# Different facts, so a different version; the recorded v0.15 book stays as
# written.
# v0.15: cascade from zone-v0.13 / liq-v0.11 / structure-v0.12 / regime-v0.12 —
# the S53 consumer collapse keyed pivots on market_time alone and a same-bar
# HIGH+LOW pair shadowed one twin out of zones, pools and labels. Five supply
# zones store-wide did not exist under v0.14's inputs; which setups exist
# changes with them.
# v0.14: cascade from swing-v0.9 — every upstream this engine reads moved with
# it (zone-v0.12, liq-v0.10, regime-v0.11, structure-v0.11). The load-bearing
# change: v0.8 swings re-emitted promoted pivots every cycle and zones counted
# the copies as cluster neighbours, so zone strength — a REVERSAL evidence
# component — inflated monotonically. Which setups exist changes.
# v0.12: cascade from zone-v0.11, which closed a lookahead in the zone cluster
# count. `zone_strength` is one of the four REVERSAL evidence components, so a
# zone quality computed from the future fed straight into playbook selection.
# v0.11: the economics gate now prices FUNDING, not just fees and slippage
# (costs.estimated_round_trip_cost gained symbol/tf_seconds). On the current
# book the outputs are byte-identical — confirmed-entry stops are already wide
# enough to clear the higher bar, and only one extra 15m candidate is screened
# out. The bump is still correct: the RULES changed, a tighter-stopped setup
# would now be judged differently, and a version tag identifies the rules that
# produced a fact rather than the bytes that came out.

# v0.10 — FORMING is now an ARMED ORDER (forming-armed-order-plan, Phases E/F).
# It carries a real size and risk decision computed by risk.size_order at the
# moment the zone is approached, and VALIDATED INHERITS that bracket verbatim
# instead of recomputing it at touch. The point is that what executes is
# provably what was decided; recomputation "the same way" is a weaker claim,
# because ATR, structure and equity all move in between.
#
# The bump is not optional: v0.9 had already written FORMING facts with every
# armed field None, and emitting sized ones under the same tag produced 107
# armed and 107 unarmed rows describing the same 1D zones. Caught by the plan
# Phase J replay — which is what that phase is for.

# v0.9: no strategy rule changed. structure-v0.10/regime-v0.10 give the 1D
# book a higher-timeframe regime for the first time, so `htf_state` stops
# reading UNKNOWN there — the only factor ever measured above the noise floor
# becomes available on the timeframe that carries the book. Different facts,
# so a different version; see tests/test_version_cascade.py for why.

# v0.8: NO strategy rule changed. Every input did. structure-v0.9 fixed a tick
# floor that suppressed breaks entirely on most sub-dollar symbols, so
# regime-v0.9 reclassifies them out of a permanent false RANGE. Measured on the
# 20 symbols carrying both generations of rejection facts: NO_ELIGIBLE_PLAYBOOK
# with regime=RANGE fell 877 -> 176, and u1000SHIBUSDT alone went 290 -> 6.
# zone-v0.10 and liq-v0.9 carry the same fix (see BUILDLOG S40).
# Identical code over different facts produces different setups, and the
# version has to say so: `setup_id` is version-scoped precisely so two
# generations cannot collide, and leaving the tag at v0.7 would have written a
# second, incompatible book under a label that already means something else.
# That is the S37 defect, and it is not allowed to happen twice.

# ── v0.7 — CONFIRMED ENTRY. The change this version exists for. ──────────────
# Measured on the v0.6 book (142 filled trades, 13% win, -102.8R):
#   · 73 of 124 stop-outs (59%) resolved on the BAR THAT FILLED THE ENTRY
#   · median bars_held = 0
#   · median MAE 1.65R — the typical trade traded straight through its stop
# Cause, and it is geometric rather than a matter of tuning: the zone is
# 0.25 ATR wide and the stop sat 0.25 ATR beyond its far edge, so total risk was
# ~0.5 ATR. The bar that touches an ATR-anchored zone has a range of roughly
# 1 ATR by construction. The stop was inside the noise of its own trigger bar,
# so the trigger bar and the killing bar were the same bar.
#
# Second-order consequence, equally damaging: with risk pinned near 0.5 ATR the
# ONLY way a setup could satisfy R:R >= 1.5 was a distant target. Median target
# ran 6.4R against a median favourable excursion of 1.53R. The gate meant to
# enforce quality was selecting for improbability.
#
# v0.7 waits for a CLOSE that proves the level held before calling it a trade:
#   TOUCH -> CONFIRMING -> (confirming close) -> VALIDATED
#                       -> (window elapses)   -> CANCELLED CONFIRMATION_TIMEOUT
#                       -> (zone breaks)      -> CANCELLED ZONE_BROKE_UNCONFIRMED
# The wick that would have stopped you has already printed, and the stop becomes
# a low the market visibly rejected instead of an ATR offset. It is wider on
# purpose: a wider, earned stop un-pins risk and lets targets come back to
# reachable distances.
FORMING_TFS = ("4H", "1D", "1W")
PROX_ATR = Decimal(1)
# The closed rejection vocabulary — every word `reject()` may write. It exists
# because these strings are the funnel's raw material: funnel.js keeps a plain
# sentence for each one, and a reason minted here without a sentence there
# reaches the operator as a bare enum. `reject()` warns (loudly, not fatally)
# on any word missing from this set, and the cross-boundary test holds
# funnel.js to covering it. Grow the vocabulary in one commit: here, the
# sentence, the test.
REJECTION_REASONS = frozenset({
    "NO_ELIGIBLE_PLAYBOOK", "RR_BELOW_MINIMUM", "UNECONOMIC_AFTER_COSTS",
    "ATR_UNAVAILABLE", "NO_CAUSAL_TARGET", "INVALID_BRACKET", "VETOED",
})
MIN_RR = Decimal("1.5")
GOOD_RR = Decimal("2.5")
SL_ATR = Decimal("0.25")            # v0.6 zone-offset stop; kept for FORMING previews
SWEEP_LOOKBACK_BARS = 10
Q2 = Decimal("0.01")
# Armed-order window: number of bars a limit stays live before it MISSES.
# MUST equal execsim.MAX_ENTRY_BARS — Phase G will collapse to one source.
ENTRY_MAX_BARS = 4


def _fp(p) -> str:
    """Price for WHY text, decimals scaled to magnitude — chart.js `digits()`
    exactly, so the journal writes a number the way the chart draws it. At a
    flat .2f every sub-dollar zone was a degenerate range: ENA's journal read
    "supply zone 0.09-0.09"."""
    p = float(p)
    a = abs(p)
    d = 2 if a >= 1000 else 3 if a >= 10 else 4 if a >= 1 else 5 if a >= 0.01 else 8
    return f"{p:,.{d}f}"

# --- confirmation (v0.7) ---
# Bars after the touch in which a confirming close may appear. Three is a
# deliberate opening guess, not a calibrated value: long enough that a zone
# needing a retest still qualifies, short enough that "it eventually went up"
# is not mistaken for "the level held". The 2x2 replay grades it.
CONFIRM_MAX_BARS = 3
# The confirming bar must close in this fraction of its own range, measured
# from the far side — i.e. a LONG needs a close in the upper third. This is
# what separates a rejection wick from a bar that merely drifted back out.
REJECTION_FRACTION = Decimal("0.66")
# Structural buffer beyond the confirmation bar's own extreme. Small, because
# the extreme is ALREADY a tested level; this only clears the tick noise around
# it rather than inventing a second cushion.
SL_BUFFER_ATR = Decimal("0.15")
# Targets are capped in R. `target()` returns the nearest opposing structure,
# which on a daily chart can be a quarter away. Both the capped and uncapped
# values are recorded so a later version can measure whether the cap helped.
MAX_TARGET_R = Decimal(3)
# Entry model, chosen by measurement (abtest, perps, hold exit, n=228):
#   MARKET_NEXT_OPEN   -0.017 R   P(>0) 43.6%   0 missed
#   MAKER_PULLBACK     +0.074 R   P(>0) 70.8%   32 missed  <- adversely selected
#   MAKER_THEN_MARKET  +0.115 R   P(>0) 82.2%   0 missed
#
# Rest a limit MAKER_OFFSET_R better than the market; if it has not filled in
# MAKER_WAIT_BARS, cross and pay taker. Both halves are load-bearing:
#   · The passive leg matters because the break-even fee on this book is
#     0.033%/side against Phemex taker 0.06% — the fee alone spans losing and
#     winning.
#   · The crossing leg matters because the pure maker variant is ADVERSELY
#     SELECTED, exactly as v0.6's resting limits were: its 32 unfilled orders
#     would have made +0.365 R each at market against +0.074 R for the ones that
#     filled. Price walks away precisely when the trade is right, so declining
#     those trades pays for the saved fee with the edge.
# A limit AT the market is marketable and pays taker — the offset must be > 0 or
# this is a taker order wearing a maker label.
ENTRY_MODEL = "MAKER_THEN_MARKET"
MAKER_OFFSET_R = Decimal("0.10")
MAKER_WAIT_BARS = 2
# The higher timeframe each timeframe defers to, for the HTF-alignment factor.
# scalein.py already encodes the principle — "the higher timeframe GATES the
# lower" — it was simply never applied to the primary entry.
HTF_LADDER = {"15m": "1H", "1H": "4H", "4H": "1D", "1D": "1W", "1W": None}
# D1 — premium/discount. Where price sits between the most recent opposing
# INTERMEDIATE+ swings, 0 = at the low, 100 = at the high. Cheap, and genuinely
# ORTHOGONAL to everything else recorded here: buying a demand zone in the lower
# third of its range is a different trade from buying the same zone after price
# has already run to the top. Nothing else in the confluence block measures
# location-within-range; zone strength measures the quality of a level, not
# where that level sits.
PD_LOOKBACK_SWINGS = 6
# D2 — HTF composite. `factorstats` measured htf_regime_aligned,
# htf_align_strength and htf_regime_conviction as one cluster (r up to 0.93):
# three names for "what is the higher timeframe doing". They are collapsed to a
# single three-state reading so a future scorer cannot count one signal thrice —
# the precise failure that produced 26 factors worth 5 in the prior project.


# Cost model is an immutable profile resolved PER SYMBOL — see costs.profile_for.
# There is deliberately no module-level COST_PROFILE here any more: every
# consumer that imported that name silently inherited Coinbase spot rates, which
# is precisely how the perp book came to be priced at ~14x its real fees with
# nothing failing. A global default is what made the mistake invisible.
SLIP_ATR = costs.DEFAULT_COST_PROFILE.market_slippage_atr   # legacy consumers only

# v0.3 (validation-001 finding): tight stops make fees enormous in R terms —
# 15m round-trip costs ran 3-6R and the whole intraday book was net-negative.
# Fee-aware gate: a setup is only economic if risk >= K x estimated round-trip
# cost (2 fees on entry notional + one market-exit slippage).
# v0.4: K=2 (max ~0.5R cost drag). K=4 was unattainable with 0.5-ATR structural
# stops on BTC 1D (fees are % of notional; max achievable ratio ~2.9) and
# rejected 193/200 including the profitable 1D book — the user's named failure
# mode. Deterministic, pre-trade, evaluated at validation time.
MIN_RISK_COST_MULT = Decimal(2)

# v0.2 (CAL-5 diagnosis 2026-07-21): TRANSITION regimes ate most zone touches
# with no playbook to trade them — user's own mapping says exhaustion->reversal.
# Added REVERSAL playbook (TRANSITION + zone touch, lower base rank) and
# WEAKENING_* continuation entries. Draft pending §30 item 9 ratification.


# --- REVERSAL evidence (v0.7) ---------------------------------------------
# The TRANSITION regime is the single largest bucket of discarded opportunity:
# 2,959 of 7,149 NO_ELIGIBLE_PLAYBOOK rejections, 41%. A REVERSAL playbook for
# it already existed — and had fired FIVE TIMES in the entire history, because
# it demanded a liquidity sweep within 10 bars and the whole store contains only
# 98 SWEEP facts across every symbol and timeframe. That is not a confluence
# requirement, it is a lottery ticket.
#
# Replaced with a composition, ported in shape from the prior project's reversal
# detector (SALVAGE §3.5), which required 3 of 4 independent components rather
# than one rare one. Adapted to the evidence THIS engine actually produces, and
# to the rule that confluence must come from different information types rather
# than several readings of the same one:
#   CHOCH      structure  — the trend has actually broken, not merely paused
#   SWEEP      liquidity  — stops were taken before the turn (rare; still counts)
#   VOLUME     participation — someone showed up at the level
#   STRENGTH   location   — RECORDED, NOT COUNTED. See below.
#
# S50 — STRENGTH WAS NEVER EVIDENCE. It cannot be false:
#
#     strength   = (quality + freshness) // 2          [zones.strength]
#     freshness  = 100 at creation, and the setup reads the CREATION value
#     quality   >= 55 for the weakest zone the engine can build (cluster 0, 15m)
#     => strength >= 77,  against REVERSAL_MIN_ZONE_STRENGTH = 60
#
# Every timeframe, every cluster count, including zero. Which is why STRENGTH
# appeared in 985 of 985 VALIDATED REVERSAL setups — cardinality 1, the exact
# stuck-value signature that means a field is dead, defaulted or broken.
#
# So "2 of 4" was really "1 of 3 plus a free point", and 81.3% of REVERSAL
# setups were admitted on ONE real component. This is the honest statement of
# what the engine has always done: three real components, one required.
#
# Operator ruling 2026-07-30, on the measurement below: state it honestly and
# keep trading the same book. The alternative — demanding genuine 2-of-3 — was
# measured on the traded book and is WORSE, not better:
#
#     2+ real components   n= 63   +0.020 R   CI [-0.388, +0.444]   P(>0) 51.9%
#     1  real component    n=214   +0.191 R   CI [-0.053, +0.451]   P(>0) 93.4%
#
# More confluence performed worse. That is the confluence-stacking trap this
# project was built to avoid, found in this project's own gate — so the
# threshold is NOT tightened on the strength of an intuition the data refutes.
#
# STRENGTH is still COMPUTED and still RECORDED on every fact (house rule:
# evidence is recorded, not filtered on — a factor must be graded before it can
# gate). It simply no longer counts toward the bar it could never fail to clear.
# If `zones.strength` is ever retuned so it CAN fail, it earns its place back
# here — by measurement, in the same commit.
REVERSAL_MIN_EVIDENCE = 1
# What the gate COUNTS. STRENGTH is deliberately absent; see above.
REVERSAL_COMPONENTS = ("CHOCH", "SWEEP", "VOLUME")
# What is RECORDED on the fact, so a grader can still measure STRENGTH later.
REVERSAL_RECORDED_COMPONENTS = ("CHOCH", "SWEEP", "VOLUME", "STRENGTH")
REVERSAL_CHOCH_LOOKBACK_BARS = 20
REVERSAL_VOL_RATIO = Decimal("1.3")
REVERSAL_MIN_ZONE_STRENGTH = 60


def reversal_evidence(*, choch_recent: bool, swept: bool,
                      vol_ratio, zone_strength) -> list:
    """Which reversal components are present. Returns the NAMES, not a count —
    the setup fact records them so a rejection is as auditable as an approval."""
    out = []
    if choch_recent:
        out.append("CHOCH")
    if swept:
        out.append("SWEEP")
    try:
        if vol_ratio is not None and Decimal(str(vol_ratio)) >= REVERSAL_VOL_RATIO:
            out.append("VOLUME")
    except Exception:
        pass
    if zone_strength is not None and zone_strength >= REVERSAL_MIN_ZONE_STRENGTH:
        out.append("STRENGTH")
    return out


# --- D3: VETO conditions ---------------------------------------------------
# Some conditions are GATES, not weights. The distinction is the single most
# useful structural idea carried over from the prior project (SALVAGE §3.1):
# there, a high confluence score could buy its way past a disqualifying
# condition because everything was additive, and a comment in that codebase
# admits setups were "inflating past the confluence threshold via unearned
# synergy points".
#
# A veto cannot be outscored. It is checked before any score exists, it records
# WHY, and no amount of supporting evidence overrides it. Kept deliberately
# short — a long veto list is a scoring system wearing a disguise.
VETO_MIN_CONFIRM_BAR_RANGE_ATR = Decimal("0.15")


def vetoes(*, confirm_bar, atr_at_confirm, entry, sl, tick) -> list:
    """Disqualifying conditions. Returns the NAMES of every veto that fired.

    Each one describes a trade that cannot be executed as planned, rather than
    one that is merely unattractive — which is what separates a veto from a
    negative score.
    """
    out = []
    if atr_at_confirm is not None and atr_at_confirm > 0:
        rng = Decimal(confirm_bar["high"]) - Decimal(confirm_bar["low"])
        if rng < VETO_MIN_CONFIRM_BAR_RANGE_ATR * atr_at_confirm:
            # A confirmation bar with almost no range has not demonstrated a
            # rejection; it has demonstrated that nothing happened. The close
            # position test (REJECTION_FRACTION) is trivially satisfied inside a
            # doji, so without this a flat bar can "confirm" anything.
            out.append("CONFIRM_BAR_TOO_NARROW")
    risk = abs(entry - sl)
    if tick and risk < 2 * tick:
        # A stop closer than two ticks cannot be placed distinctly from the
        # entry. Any R computed against it is arithmetic, not a trade.
        out.append("STOP_INSIDE_TICK_RESOLUTION")
    return out


def playbook(zone_type: str, reg: str | None, swept: bool = False,
             enabled: set | None = None, rev_evidence: list | None = None):
    """Returns (strategy, direction, base_rank) or None if no play.

    `enabled` is the operator's strategy selection. `settings.py` has defined
    `strategy_pullback` / `strategy_reversal` / `strategy_scale_in` as
    BEHAVIOURAL settings since S34 and `/api/settings` has been wired the whole
    time, but nothing ever READ them — the switches were inert and turning one
    off changed nothing. Honouring them here is what makes the setting real;
    the active set is recorded in the strategy manifest so any fact can be
    traced to the configuration that produced it.
    """
    def allow(strategy):
        return enabled is None or strategy in enabled

    # A caller that supplies only `swept` (the Market Weather strip probes this
    # function that way) is treated as having exactly one component, which now
    # clears the bar — and that is a CORRECTION, not a loosening. The probe used
    # to report "a sweep alone is not enough" while the real engine, on the same
    # zone, always also had the structurally-true STRENGTH component and
    # therefore always passed. The probe was describing a rule the engine did
    # not follow. It now describes the one it does.
    ev = rev_evidence if rev_evidence is not None else (["SWEEP"] if swept else [])
    # Count only the components that can actually be absent. STRENGTH is
    # recorded on the fact but excluded here — it was structurally true on
    # 985 of 985 setups, so counting it was counting a constant. See the
    # REVERSAL_COMPONENTS block for the measurement and the ruling.
    counted = [c for c in ev if c in REVERSAL_COMPONENTS]
    reversal_ok = len(counted) >= REVERSAL_MIN_EVIDENCE

    if zone_type == "DEMAND":
        if reg in ("BULL_TREND", "WEAKENING_BULL") and allow("PULLBACK"):
            return "PULLBACK", "LONG", 50
        if reg == "TRANSITION" and reversal_ok and allow("REVERSAL"):
            return "REVERSAL", "LONG", 40
    else:
        if reg in ("BEAR_TREND", "WEAKENING_BEAR") and allow("PULLBACK"):
            return "PULLBACK", "SHORT", 50
        if reg == "TRANSITION" and reversal_ok and allow("REVERSAL"):
            return "REVERSAL", "SHORT", 40
    return None


def enabled_strategies(con) -> set:
    """Operator-selected strategies, defaulting to all when unset/unavailable.

    Fails OPEN deliberately. A settings-table read failure that silently
    disabled every strategy would look identical to a quiet market, and this
    system's whole complaint about itself is that silence must never be
    ambiguous.
    """
    try:
        from . import settings
        values = settings.all_settings(con)
    except Exception:
        return {"PULLBACK", "REVERSAL", "SCALE_IN"}
    out = set()
    for key, name in (("strategy_pullback", "PULLBACK"),
                      ("strategy_reversal", "REVERSAL"),
                      ("strategy_scale_in", "SCALE_IN")):
        if values.get(key, True):
            out.add(name)
    return out


def confirms(candle: dict, direction: str, top: Decimal, bottom: Decimal) -> bool:
    """Did this CLOSED bar prove the zone held?

    Three conditions, all required (LONG shown; SHORT mirrors):
      1. the bar engaged the zone            low  <= zone top
      2. and closed back out of it           close > zone top
      3. with the close in the upper third   close >= low + 0.66 * (high - low)

    (3) is what distinguishes a rejection from a drift. A bar that closes
    fractionally above the zone after spending its session inside it has not
    demonstrated anything; a bar that spikes down into it and closes near its
    high has. Without this the rule would admit most touches and change nothing.
    """
    hi, lo = Decimal(candle["high"]), Decimal(candle["low"])
    close = Decimal(candle["close"])
    rng = hi - lo
    if direction == "LONG":
        if not (lo <= top and close > top):
            return False
        return rng <= 0 or close >= lo + REJECTION_FRACTION * rng
    if not (hi >= bottom and close < bottom):
        return False
    return rng <= 0 or close <= hi - REJECTION_FRACTION * rng


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    with RunRecorder(con, "setup", SETUP_VERSION, symbol, tf) as rec:
        enabled = enabled_strategies(con)
        # v0.7: the cost profile is VENUE-derived, not a module constant. It was
        # Coinbase spot for every symbol while the traded universe was entirely
        # Phemex perps — a 14x over-charge that made the economics gate demand a
        # ~14x wider stop before a setup counted as economic. See costs.profile_for.
        profile = costs.profile_for(symbol)
        strategy_manifest = {
            "version": SETUP_VERSION, "min_rr": str(MIN_RR),
            "good_rr": str(GOOD_RR), "sl_atr": str(SL_ATR),
            "sweep_lookback_bars": SWEEP_LOOKBACK_BARS,
            "min_risk_cost_multiple": str(MIN_RISK_COST_MULT),
            "reversal_min_evidence": REVERSAL_MIN_EVIDENCE,
            "reversal_components": ["CHOCH", "SWEEP", "VOLUME", "STRENGTH"],
            # v0.7 — the confirmed-entry parameters are part of the manifest
            # because they change which facts exist, not merely how they look.
            "confirm_max_bars": CONFIRM_MAX_BARS,
            "rejection_fraction": str(REJECTION_FRACTION),
            "sl_buffer_atr": str(SL_BUFFER_ATR),
            "max_target_r": str(MAX_TARGET_R),
            "entry_model": ENTRY_MODEL,
            "maker_offset_r": str(MAKER_OFFSET_R),
            "maker_wait_bars": MAKER_WAIT_BARS,
            "enabled_strategies": sorted(enabled),
            "cost_profile": profile.payload(),
            "inputs": {"swing": SWING_VERSION, "zone": ZONE_VERSION,
                       "liquidity": LIQ_VERSION, "regime": REGIME_VERSION},
        }
        manifest_hash = store.record_manifest(con, "strategy", strategy_manifest)
        cost_manifest_hash = costs.record(con, profile)
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
        atr = compute_atr(candles)
        ticks = quote_ticks(candles)

        regimes = []
        for r in store.get_facts(con, symbol, tf, "regime", REGIME_VERSION):
            regimes.append((r["confirmed_at"], json.loads(r["payload"])["regime"]))
        regimes.sort()

        def regime_at(ts):
            cur = None
            for conf, reg in regimes:
                if conf <= ts:
                    cur = reg
                else:
                    break
            return cur

        # Higher-timeframe regime, read with the SAME as_of discipline: a 4H
        # trade may only know the 1D regime that had already confirmed by then.
        htf = HTF_LADDER.get(tf)
        htf_regimes = []
        if htf:
            for r in store.get_facts(con, symbol, htf, "regime", REGIME_VERSION):
                htf_regimes.append((r["confirmed_at"],
                                    json.loads(r["payload"])["regime"]))
            htf_regimes.sort()

        def htf_regime_at(ts):
            cur = None
            for conf, reg in htf_regimes:
                if conf <= ts:
                    cur = reg
                else:
                    break
            return cur

        # PHASE F — the armed orders already emitted, by setup_id. VALIDATED
        # will INHERIT from these rather than recomputing, which is the entire
        # point of the armed order: what gets executed must provably be what was
        # decided when the setup was armed, not something recalculated later
        # under different conditions and assumed to match.
        # Populated BY the FORMING pass below, and seeded from facts an earlier
        # invocation already wrote. Reading the store alone was wrong: a zone
        # arms and validates inside ONE run, so on a fresh store nothing would
        # ever inherit — which is exactly what the Phase J replay showed (0% on
        # every timeframe, including the three that arm).
        armed_by_id: dict = {}
        for r in store.get_facts(con, symbol, tf, "setup", SETUP_VERSION):
            p_ = json.loads(r["payload"])
            if p_.get("state") == "FORMING" and p_.get("size_units") is not None:
                prev = armed_by_id.get(p_["setup_id"])
                # earliest arming wins — a later re-arm of the same id is a
                # different decision wearing the same name
                if prev is None or r["confirmed_at"] < prev["_armed_confirmed_at"]:
                    armed_by_id[p_["setup_id"]] = {**p_,
                                                   "_armed_confirmed_at": r["confirmed_at"]}

        zones: dict = {}
        for r in store.get_facts(con, symbol, tf, "zone", ZONE_VERSION):
            p = json.loads(r["payload"])
            z = zones.setdefault(p["zone_id"], {})
            rec_p = {"market_time": r["market_time"],
                     "confirmed_at": r["confirmed_at"], **p}
            if p["event"] == "TOUCH":
                if p.get("episode") == 1:
                    z["TOUCHED"] = rec_p       # first episode is the trigger
            else:
                z[p["event"]] = rec_p

        pools, pool_broken, sweeps = [], {}, []
        for r in store.get_facts(con, symbol, tf, "liquidity", LIQ_VERSION):
            p = json.loads(r["payload"])
            if p["event"] == "POOL":
                pools.append({"confirmed_at": r["confirmed_at"], "side": p["side"],
                              "level": Decimal(p["level"]), "pool_id": p["pool_id"]})
            elif p["event"] == "BROKEN":
                pool_broken[p["pool_id"]] = r["confirmed_at"]
            elif p["event"] == "SWEEP":
                sweeps.append({"market_time": r["market_time"],
                               "confirmed_at": r["confirmed_at"], "side": p["side"]})

        # Structure breaks, for the "bars since the last break" confluence
        # factor only. Recorded as evidence; nothing gates on it.
        from .structure import STRUCTURE_VERSION
        breaks_by_conf = []
        for r in store.get_facts(con, symbol, tf, "structure", STRUCTURE_VERSION):
            p = json.loads(r["payload"])
            if p["event"] in ("BOS", "CHOCH"):
                breaks_by_conf.append({"market_time": r["market_time"],
                                       "confirmed_at": r["confirmed_at"],
                                       "event": p["event"]})
        breaks_by_conf.sort(key=lambda b: b["confirmed_at"])

        tier_swings = {"HIGH": [], "LOW": []}
        for r in store.get_facts(con, symbol, tf, "swing", SWING_VERSION):
            p = json.loads(r["payload"])
            if p["tier"] in ("INTERMEDIATE", "MAJOR"):
                tier_swings[p["type"]].append(
                    {"confirmed_at": r["confirmed_at"], "price": Decimal(p["price"])})

        def target(direction, entry, as_of):
            side = "HIGH" if direction == "LONG" else "LOW"
            beyond = [p["level"] for p in pools
                      if p["side"] == side and p["confirmed_at"] <= as_of
                      and pool_broken.get(p["pool_id"], 2**53) > as_of
                      and (p["level"] > entry if direction == "LONG" else p["level"] < entry)]
            if not beyond:
                beyond = [s["price"] for s in tier_swings[side]
                          if s["confirmed_at"] <= as_of
                          and (s["price"] > entry if direction == "LONG" else s["price"] < entry)]
            if not beyond:
                return None
            return min(beyond) if direction == "LONG" else max(beyond)

        def recent_choch(market_time, confirmed_at):
            """Has a CHoCH confirmed within the lookback, at or before now?

            CHoCH is the structural statement that the prevailing trend has
            actually broken. TRANSITION regime is *derived from* the last break
            being a CHoCH, so this is not a second independent reading of the
            same thing — it answers WHEN, and a break twenty bars stale is a
            different trade from one that just printed.
            """
            window = REVERSAL_CHOCH_LOOKBACK_BARS * tf_seconds
            return any(b["event"] == "CHOCH"
                       and b["confirmed_at"] <= confirmed_at
                       and 0 <= market_time - b["market_time"] <= window
                       for b in breaks_by_conf)

        def recent_sweep(direction, market_time, confirmed_at):
            side = "LOW" if direction == "LONG" else "HIGH"
            lookback = SWEEP_LOOKBACK_BARS * tf_seconds
            return any(s["side"] == side
                       and 0 <= market_time - s["market_time"] <= lookback
                       and s["confirmed_at"] <= confirmed_at for s in sweeps)

        rec.n_inputs = len(zones)
        n_setups = n_expired = n_cost_rejected = n_forming = n_cancelled = n_rejected = 0
        n_confirming = n_unconfirmed = 0

        def volume_ratio(i):
            """Confirmation-bar volume against its trailing 20-bar average."""
            if i < 20:
                return None
            avg = sum(Decimal(candles[j]["volume"]) for j in range(i - 20, i)) / 20
            if avg <= 0:
                return None
            return (Decimal(candles[i]["volume"]) / avg).quantize(Q2)

        def premium_discount(price, as_of):
            """Where `price` sits between the last opposing INTERMEDIATE+ swings.

            0 = at the low of the range, 100 = at the high. None when there is
            no bracketing pair yet — a partial range would put price at "50% of
            nothing", which reads like a measurement and is not one.
            """
            highs = [s["price"] for s in tier_swings["HIGH"]
                     if s["confirmed_at"] <= as_of][-PD_LOOKBACK_SWINGS:]
            lows = [s["price"] for s in tier_swings["LOW"]
                    if s["confirmed_at"] <= as_of][-PD_LOOKBACK_SWINGS:]
            if not highs or not lows:
                return None
            hi, lo = max(highs), min(lows)
            if hi <= lo:
                return None
            pct = (price - lo) / (hi - lo) * 100
            return int(max(0, min(100, pct)))

        def confluence_block(direction, i, created, bct, swept, target_r):
            """Evidence RECORDED, never filtered on (§22 discipline).

            `score` is deliberately emitted as 0 and consumed by nothing. The
            field exists so the schema is stable from day one and a later
            version can populate it without a migration — but a factor only
            earns a gate after `engine/factorstats.py` shows it clears fire
            rate, dispersion, redundancy against already-promoted factors, and
            an outcome correlation beyond the ±1.96/√n noise floor.

            The previous project shipped 26 factors that were really about five
            independent signals, each counted several times. Recording first and
            grading second is the whole defence against repeating that.
            """
            hr = htf_regime_at(bct)
            aligned = None
            if hr is not None:
                aligned = ((direction == "LONG" and hr in ("BULL_TREND", "WEAKENING_BULL"))
                           or (direction == "SHORT" and hr in ("BEAR_TREND", "WEAKENING_BEAR")))
            # Three states, never two. UNKNOWN is not a weak form of OPPOSED:
            # measured on the v0.7 book, unknown-HTF trades ran 38.9% win /
            # +0.404 R while genuinely opposed ones ran 17.2% / -0.616 R. Folding
            # them together docked the entire 1D book — the only profitable
            # timeframe — for a data gap it cannot close: 1W regime needs
            # MAJOR-tier swings, and 194 weeks of perp history yields 1-2 MAJOR
            # swings per symbol, far too few to form an alternating sequence.
            # A missing measurement must never be scored as a bad measurement.
            if hr is None:
                htf_state = "UNKNOWN"
            elif hr in ("BULL_TREND", "WEAKENING_BULL", "BEAR_TREND", "WEAKENING_BEAR"):
                htf_state = "TRENDING"
            else:
                htf_state = "FLAT"
            vr = volume_ratio(i)
            last_break_bars = None
            for b in reversed(breaks_by_conf):
                if b["confirmed_at"] <= bct:
                    last_break_bars = max(0, (candles[i]["open_ts"] - b["market_time"])
                                          // tf_seconds)
                    break
            return {
                "htf_timeframe": htf,
                "htf_regime": hr,
                # D2 — ONE composite reading of the higher timeframe, not three
                # correlated ones. `htf_regime_aligned` is kept because it is
                # what the +10 term measured, but `htf_state` is the reading a
                # future scorer should use; recording both lets factorstats show
                # they are the same signal rather than assuming it.
                "htf_regime_aligned": aligned,
                "htf_state": htf_state,
                "htf_composite": (None if htf_state == "UNKNOWN" else
                                  "WITH" if aligned else
                                  "FLAT" if htf_state == "FLAT" else "AGAINST"),
                "zone_strength": created.get("strength"),
                "zone_quality": created.get("formation_quality"),
                "zone_cluster": created.get("cluster_members"),
                "volume_expansion": None if vr is None else str(vr),
                "sweep_nearby": swept,
                "bars_since_break": last_break_bars,
                "target_distance_r": None if target_r is None else str(target_r),
                # D1 — orthogonal to every other field here.
                "premium_discount": premium_discount(Decimal(candles[i]["close"]), bct),
                "score": 0,
            }

        def reject(zone_id, touched, reason, details=None):
            nonlocal n_rejected
            # The drift guard (ported in shape from the prior project's
            # _KNOWN_REASONS). Every reason written here is a word the funnel
            # must have a sentence for; a NEW reason that skips the canonical
            # set reaches the operator as a raw enum with no explanation, and
            # nobody files a bug against a word they assume is theirs to not
            # understand. Loud, not fatal: the rejection itself is a fact and
            # must be recorded — it is the LABEL that is late, not the event.
            if reason.split("(")[0] not in REJECTION_REASONS:
                from .runlog import get_logger
                get_logger().warning(
                    f"setups {symbol} {tf}: rejection reason {reason!r} is not "
                    f"in setups.REJECTION_REASONS — add it there and give it a "
                    f"sentence in funnel.js, or the funnel shows a raw enum")
            payload = {"event": "REJECTED", "zone_id": zone_id,
                       "reason": reason, "details": details or {},
                       "manifest_hash": manifest_hash}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup_rejection",
                                 market_time=touched["market_time"],
                                 confirmed_at=touched["confirmed_at"],
                                 algo_version=SETUP_VERSION, payload=payload):
                n_rejected += 1

        def gates(direction, entry, sl, tp, a):
            """Shared R:R + fee gates. Returns rr or None."""
            risk = (entry - sl) if direction == "LONG" else (sl - entry)
            reward = (tp - entry) if direction == "LONG" else (entry - tp)
            if risk <= 0 or reward <= 0:
                return None
            rr = (reward / risk).quantize(Q2)
            if rr < MIN_RR:
                return None
            if risk < MIN_RISK_COST_MULT * costs.estimated_round_trip_cost(
                    entry, a, profile, symbol=symbol, tf_seconds=tf_seconds):
                return None
            return rr

        # --- FORMING pass: price approaching an untouched active zone ---
        if tf in FORMING_TFS:
            for zone_id, z in zones.items():
                created = z.get("CREATED")
                if not created:
                    continue
                touched, broken = z.get("TOUCHED"), z.get("BROKEN")
                i0 = ts_index.get(created["market_time"])
                if i0 is None:
                    continue
                end_ts = min(touched["market_time"] if touched else 2**53,
                             broken["market_time"] if broken else 2**53)
                top, bottom = Decimal(created["top"]), Decimal(created["bottom"])
                emitted = None
                for j in range(i0 + 1, len(candles)):
                    c = candles[j]
                    bct = c["open_ts"] + tf_seconds
                    if bct <= created["confirmed_at"]:
                        continue
                    if c["open_ts"] >= end_ts:
                        break
                    if atr[j] is None:
                        continue
                    lo, hi = Decimal(c["low"]), Decimal(c["high"])
                    dist = (lo - top) if created["zone_type"] == "DEMAND" else (bottom - hi)
                    if dist <= 0:
                        break                    # reached the zone; TOUCH path owns it
                    if dist > PROX_ATR * atr[j]:
                        continue
                    reg_f = regime_at(bct)
                    dir_hint = "LONG" if created["zone_type"] == "DEMAND" else "SHORT"
                    swept_f = recent_sweep(dir_hint, c["open_ts"], bct)
                    play_f = playbook(created["zone_type"], reg_f, swept_f)
                    if play_f is None:
                        continue
                    strat_f, dir_f, _ = play_f
                    if dir_f == "LONG":
                        entry_f, sl_f = top, bottom - SL_ATR * atr[j]
                    else:
                        entry_f, sl_f = bottom, top + SL_ATR * atr[j]
                    tp_f = target(dir_f, entry_f, bct)
                    if tp_f is None:
                        continue
                    rr_f = gates(dir_f, entry_f, sl_f, tp_f, atr[j])
                    if rr_f is None:
                        continue
                    dist_atr = (dist / atr[j]).quantize(Q2)
                    # Same version-scoped form as the VALIDATED path — a FORMING
                    # fact that upgrades must carry the id its successor will use.
                    # PHASE E — the order is SIZED HERE, when it is armed, not
                    # later at execution. §9 authority is preserved: risk.py owns
                    # the code and this calls it (plan Phase C ruling, option A).
                    # Only the ORDER-level constraints are knowable now; the
                    # account-level ones (kill switch, concurrency, cooldowns,
                    # point-in-time eligibility) stay in risk.run and are applied
                    # when the trade is actually taken. So a FORMING fact says
                    # "this is the order", never "you are cleared to take it".
                    from . import risk as _risk
                    _sz = _risk.size_order(
                        equity=_risk.START_EQUITY, entry=entry_f, sl=sl_f,
                        direction=dir_f, symbol=symbol)
                    payload = {"setup_id": f"{symbol}|{tf}|{strat_f}|{zone_id}|{SETUP_VERSION}",
                               "strategy": strat_f, "direction": dir_f,
                               "entry": str(entry_f), "sl": str(sl_f), "tp": str(tp_f),
                               "rr": str(rr_f), "rank": 0,
                               "why": (f"price {dist_atr} ATR from {created['zone_type']} zone "
                                       f"{_fp(bottom)}-{_fp(top)} in {reg_f} · "
                                       f"prospective {strat_f} would pass all gates · watching"),
                               "zone_id": zone_id, "regime": reg_f, "state": "FORMING",
                               "distance_atr": str(dist_atr),
                               "zone_strength": created.get("strength"),
                               "manifest_hash": manifest_hash,
                               "cost_manifest_hash": cost_manifest_hash,
                               # Armed-order fields (Phase D scaffolding; sizing
                               # wired in Phase E, inheritance in Phase F).
                               "size_units": str(_sz["units"]),
                               "risk_usd": str(_sz["risk_usd"]),
                               "notional_usd": str(_sz["notional_usd"]),
                               "implied_leverage": str(_sz["implied_leverage"]),
                               "risk_decision": _sz["decision"],
                               "risk_reasons": _sz["reasons"],
                               # A sizing REJECTION still emits the fact — the
                               # candidate is real and the refusal is evidence.
                               # It is simply not armed.
                               "armed": _sz["decision"] != "REJECTED",
                               "armed_at": bct,
                               "expiry_bar_count": ENTRY_MAX_BARS,
                               "expires_at_ts": bct + ENTRY_MAX_BARS * tf_seconds}
                    if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                         market_time=c["open_ts"], confirmed_at=bct,
                                         algo_version=SETUP_VERSION, payload=payload):
                        n_forming += 1
                    # Available to the VALIDATED pass in THIS run, not only the
                    # next one. Idempotency means the insert may be a no-op on a
                    # re-run; the arming is still the arming either way.
                    if payload["setup_id"] not in armed_by_id:
                        armed_by_id[payload["setup_id"]] = {
                            **payload, "_armed_confirmed_at": bct}
                    emitted = payload
                    break
                if emitted and broken and not touched:
                    if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                         market_time=broken["market_time"],
                                         confirmed_at=broken["confirmed_at"],
                                         algo_version=SETUP_VERSION,
                                         payload={**emitted, "state": "CANCELLED"}):
                        n_cancelled += 1

        for zone_id, z in zones.items():
            created, touched = z.get("CREATED"), z.get("TOUCHED")
            if not created or not touched:
                continue
            reg = regime_at(touched["confirmed_at"])
            dir_hint = "LONG" if created["zone_type"] == "DEMAND" else "SHORT"
            swept = recent_sweep(dir_hint, touched["market_time"], touched["confirmed_at"])
            i_touch = ts_index.get(touched["market_time"])
            rev_ev = reversal_evidence(
                choch_recent=recent_choch(touched["market_time"], touched["confirmed_at"]),
                swept=swept,
                vol_ratio=volume_ratio(i_touch) if i_touch is not None else None,
                zone_strength=created.get("strength"))
            play = playbook(created["zone_type"], reg, swept, enabled, rev_ev)
            if play is None:
                # The rejection records WHICH components were present, not just
                # that the count fell short — a funnel that says "no playbook"
                # cannot tell you whether you were one component away.
                reject(zone_id, touched, "NO_ELIGIBLE_PLAYBOOK",
                       {"zone_type": created["zone_type"], "regime": reg,
                        "recent_sweep": swept,
                        "reversal_evidence": rev_ev,
                        "reversal_needed": REVERSAL_MIN_EVIDENCE})
                continue
            strategy, direction, base_rank = play
            i0 = ts_index.get(touched["market_time"])
            if i0 is None or atr[i0] is None:
                reject(zone_id, touched, "ATR_UNAVAILABLE")
                continue
            top, bottom = Decimal(created["top"]), Decimal(created["bottom"])
            # Version-scoped. `setup_id` was {symbol}|{tf}|{strategy}|{zone_id} with
            # no version component, so two engine generations minted the SAME
            # id for the same zone. Measured on the live store the moment v0.7
            # started running beside v0.6: 136 ids present in BOTH books, and
            # 130 of 346 exec facts joined to a setup that existed twice. Every
            # downstream join — execsim, risk, telemetry, the trace endpoint —
            # merges them silently, because a join on a colliding key cannot
            # tell it is merging. An id must identify one fact from one engine.
            setup_id = f"{symbol}|{tf}|{strategy}|{zone_id}|{SETUP_VERSION}"
            broken = z.get("BROKEN")
            break_ts = broken["market_time"] if broken else 2**53

            # ── CONFIRMING: price is in the zone, nothing is proven yet ──────
            # This is the state that used to be VALIDATED. Emitting it keeps the
            # candidate visible on the deck (and countable in the funnel) while
            # it is still deciding, so a user is never left wondering whether
            # the scanner noticed.
            confirming = {"setup_id": setup_id, "strategy": strategy,
                          "direction": direction, "zone_id": zone_id,
                          "regime": reg, "state": "CONFIRMING",
                          "entry": None, "sl": None, "tp": None,
                          "rr": None, "rank": 0,
                          "why": (f"price reached the {created['zone_type']} zone "
                                  f"{_fp(bottom)}-{_fp(top)} in {reg} · "
                                  f"waiting for a close that proves it held "
                                  f"({CONFIRM_MAX_BARS} bars)"),
                          "confirm_deadline_ts": (touched["confirmed_at"]
                                                  + CONFIRM_MAX_BARS * tf_seconds),
                          "manifest_hash": manifest_hash,
                          "cost_manifest_hash": cost_manifest_hash}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=touched["market_time"],
                                 confirmed_at=touched["confirmed_at"],
                                 algo_version=SETUP_VERSION, payload=confirming):
                n_confirming += 1

            # ── walk forward for a confirming close ─────────────────────────
            ci = None
            for j in range(i0, min(i0 + 1 + CONFIRM_MAX_BARS, len(candles))):
                c = candles[j]
                if c["open_ts"] >= break_ts:
                    break                      # the zone failed before it proved
                if c["open_ts"] + tf_seconds <= touched["confirmed_at"] and j != i0:
                    continue
                if confirms(c, direction, top, bottom):
                    ci = j
                    break

            if ci is None:
                cancel_at = min(i0 + CONFIRM_MAX_BARS, len(candles) - 1)
                reason = ("ZONE_BROKE_UNCONFIRMED"
                          if broken and broken["market_time"] <= candles[cancel_at]["open_ts"]
                          else "CONFIRMATION_TIMEOUT")
                # A zone that broke before confirming is a LOSS AVOIDED, not
                # attrition. The UI must present it that way or the filter that
                # is helping the operator will read as the thing failing them.
                if store.insert_fact(
                        con, symbol=symbol, tf=tf, kind="setup",
                        market_time=candles[cancel_at]["open_ts"],
                        confirmed_at=candles[cancel_at]["open_ts"] + tf_seconds,
                        algo_version=SETUP_VERSION,
                        payload={**confirming, "state": "CANCELLED",
                                 "cancel_reason": reason}):
                    n_unconfirmed += 1
                continue

            # ── VALIDATED: the level held, on the evidence of a closed bar ───
            cb = candles[ci]
            bct = cb["open_ts"] + tf_seconds          # when this became knowable
            if atr[ci] is None:
                reject(zone_id, touched, "ATR_UNAVAILABLE")
                continue
            # Entry is the NEXT bar's open — a price that demonstrably traded,
            # so no fill assumption is required. v0.6 rested a limit at the zone
            # edge and MISSED 90 of 232 orders (39%); a miss is not a neutral
            # outcome, it is a signal the book never got to express.
            if ci + 1 >= len(candles):
                continue                              # next bar has not closed yet
            entry = Decimal(candles[ci + 1]["open"])
            # Stop sits beyond the confirmation bar's own extreme: a level the
            # market has just visibly rejected, not an ATR offset from a zone.
            if direction == "LONG":
                sl = min(Decimal(cb["low"]), bottom) - SL_BUFFER_ATR * atr[ci]
            else:
                sl = max(Decimal(cb["high"]), top) + SL_BUFFER_ATR * atr[ci]
            risk = (entry - sl) if direction == "LONG" else (sl - entry)
            if risk <= 0:
                reject(zone_id, touched, "INVALID_BRACKET")
                continue
            # VETO before any scoring. A veto is not a low score that something
            # else can offset — it is a trade that cannot be taken as planned.
            fired = vetoes(confirm_bar=cb, atr_at_confirm=atr[ci],
                           entry=entry, sl=sl, tick=ticks[ci])
            if fired:
                reject(zone_id, touched, "VETOED", {"vetoes": fired})
                continue

            tp_uncapped = target(direction, entry, bct)
            if tp_uncapped is None:
                reject(zone_id, touched, "NO_CAUSAL_TARGET")
                continue
            # Cap the target in R. Uncapped, `target()` returns the nearest
            # opposing structure — which on a daily chart is routinely a quarter
            # away, and produced a 6.4R median against a 1.53R median favourable
            # excursion. Both values are recorded so the cap can be graded.
            cap = (entry + MAX_TARGET_R * risk) if direction == "LONG" \
                else (entry - MAX_TARGET_R * risk)
            tp = min(tp_uncapped, cap) if direction == "LONG" else max(tp_uncapped, cap)

            rr = ((tp - entry) if direction == "LONG" else (entry - tp)) / risk
            rr = rr.quantize(Q2)
            if rr < MIN_RR:
                reject(zone_id, touched, "RR_BELOW_MINIMUM",
                       {"rr": str(rr), "minimum": str(MIN_RR)})
                continue
            est_cost = costs.estimated_round_trip_cost(entry, atr[ci], profile,
                                            symbol=symbol, tf_seconds=tf_seconds)
            if risk < MIN_RISK_COST_MULT * est_cost:
                n_cost_rejected += 1
                reject(zone_id, touched, "UNECONOMIC_AFTER_COSTS",
                       {"risk_price_units": str(risk),
                        "estimated_cost_price_units": str(est_cost),
                        "required_multiple": str(MIN_RISK_COST_MULT)})
                continue

            vr = volume_ratio(ci)
            vol_hot = vr is not None and vr > Decimal("1.5")
            rank = (base_rank + (20 if swept else 0) + (15 if vol_hot else 0)
                    + (15 if rr >= GOOD_RR else 0))
            conf = confluence_block(direction, ci, created, bct, swept,
                                    ((tp_uncapped - entry) if direction == "LONG"
                                     else (entry - tp_uncapped)) / risk)
            # RANK IS RETAINED FOR HISTORY, NOT USED TO DECIDE ANYTHING.
            # Graded on 228 closed v0.7 trades (engine/factorstats.py):
            #   · rank as a whole:            r = +0.210  (floor +/-0.130)
            #   · rank MINUS this htf term:   r = +0.111  — inside the floor
            #   · this htf term alone:        r = +0.261  — clears it
            # 86% of the score's variance is the volume (+15) and rr_good (+15)
            # terms, neither of which clears its own floor, and the composite is
            # NON-MONOTONE: the modal bucket (rank 65, 51% of the deck) is the
            # WORST at -0.643 R while rank 50 is +0.027 R. A number that sorts
            # the deck backwards at its own mode is not a confidence score.
            # The UI no longer displays or sorts on it; the deck orders by
            # expiry urgency, which makes no claim it cannot support.
            if conf.get("htf_regime_aligned") is True:
                rank = min(100, rank + 10)

            verb = "pullback into" if strategy == "PULLBACK" else "reversal off"
            side_word = "above" if direction == "LONG" else "below"
            why = (f"{reg} regime · {verb} {created['zone_type']} zone "
                   f"{_fp(bottom)}-{_fp(top)}"
                   + (" · liquidity sweep nearby" if swept else "")
                   + f" · confirmed by a close back {side_word} the zone"
                   + (f" on {vr}x volume" if vol_hot else "")
                   + (f" · {htf} agrees" if conf.get("htf_regime_aligned") else "")
                   + f" · TP {_fp(tp)} · R:R {rr}")
            # Where the passive leg rests. Recorded on the fact so execsim
            # never re-derives it — one authority per number.
            maker_limit = ((entry - MAKER_OFFSET_R * risk) if direction == "LONG"
                           else (entry + MAKER_OFFSET_R * risk))
            # PHASE F — inherit the armed order verbatim when one exists.
            # 4H/1D/1W arm at zone approach; 15m/1H have no FORMING pass by
            # design and still compute here. Inheritance is byte-for-byte on the
            # bracket AND the size: recomputing "the same way" is not the same
            # guarantee, because the inputs (ATR, structure, equity) have moved
            # between arming and touch.
            _armed = armed_by_id.get(setup_id)
            _inherited = False
            if _armed and _armed.get("size_units") is not None:
                entry = Decimal(_armed["entry"])
                sl = Decimal(_armed["sl"])
                tp = Decimal(_armed["tp"])
                risk = (entry - sl) if direction == "LONG" else (sl - entry)
                if risk > 0:
                    rr = (((tp - entry) if direction == "LONG" else (entry - tp))
                          / risk).quantize(Q2)
                    maker_limit = ((entry - MAKER_OFFSET_R * risk)
                                   if direction == "LONG"
                                   else (entry + MAKER_OFFSET_R * risk))
                    _inherited = True
            payload = {"setup_id": setup_id,
                       "strategy": strategy, "direction": direction,
                       "entry": str(entry), "sl": str(sl), "tp": str(tp),
                       "inherited_from_forming": _inherited,
                       "forming_id": (_armed.get("setup_id") if _inherited else None),
                       "armed_size_units": (_armed.get("size_units") if _inherited else None),
                       "armed_risk_decision": (_armed.get("risk_decision") if _inherited else None),
                       "maker_limit": str(maker_limit),
                       "maker_wait_bars": MAKER_WAIT_BARS,
                       "tp_uncapped": str(tp_uncapped),
                       "rr": str(rr), "rank": rank, "why": why,
                       "zone_id": zone_id, "regime": reg, "state": "VALIDATED",
                       "entry_model": ENTRY_MODEL,
                       "confirmed_bar_ts": cb["open_ts"],
                       "confirm_bars_waited": ci - i0,
                       "confluence": conf,
                       "reversal_evidence": rev_ev,
                       "manifest_hash": manifest_hash,
                       "cost_manifest_hash": cost_manifest_hash,
                       "size_units": None, "risk_usd": None,
                       "notional_usd": None, "implied_leverage": None,
                       "risk_decision": None, "risk_reasons": [],
                       "armed": False,
                       "armed_at": bct,
                       "expiry_bar_count": ENTRY_MAX_BARS,
                       "expires_at_ts": bct + ENTRY_MAX_BARS * tf_seconds}
            if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                 market_time=cb["open_ts"], confirmed_at=bct,
                                 algo_version=SETUP_VERSION, payload=payload):
                n_setups += 1
            if broken and broken["confirmed_at"] > bct:
                if store.insert_fact(con, symbol=symbol, tf=tf, kind="setup",
                                     market_time=broken["market_time"],
                                     confirmed_at=broken["confirmed_at"],
                                     algo_version=SETUP_VERSION,
                                     payload={**payload, "state": "EXPIRED"}):
                    n_expired += 1

        con.commit()
        rec.n_new_facts = (n_setups + n_expired + n_forming + n_cancelled
                           + n_rejected + n_confirming + n_unconfirmed)
        # Confirmation yield is THE diagnostic for this version: too low and the
        # rule has choked throughput, too high and it is not filtering anything.
        # Recording it per run means the answer is in the run log, not inferred.
        yield_den = n_setups + n_unconfirmed
        rec.notes = (f"cost_rejected={n_cost_rejected} confirming={n_confirming} "
                     f"confirmed={n_setups} unconfirmed={n_unconfirmed} "
                     f"yield={(n_setups / yield_den):.0%}" if yield_den else
                     f"cost_rejected={n_cost_rejected} no_candidates")
        return {"symbol": symbol, "tf": tf, "setups": n_setups,
                "expired": n_expired, "cost_rejected": n_cost_rejected,
                "forming": n_forming, "cancelled": n_cancelled,
                "rejected": n_rejected, "confirming": n_confirming,
                "unconfirmed": n_unconfirmed}
