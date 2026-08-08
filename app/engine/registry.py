"""Strategy registry — one declaration of what each playbook IS.

## Why this is deliberately thin

`PROGRAM-PLAN.md` Wave 2.1 specifies a registry where "each strategy owns its
bracket, confirmation rule, horizon, timeframes". That is the right shape for a
system with several strategies whose MECHANICS differ. This one does not have
that yet, and building the full abstraction now would be architecture without a
consumer:

  · PULLBACK and REVERSAL share every mechanic — same confirmation predicate,
    same structural stop, same capped target, same entry model. They differ only
    in which regime admits them and what evidence that regime demands.
  · Range fade, the obvious third, was CLOSED BY EVIDENCE (of the RANGE-regime
    rejections, 3 had a live detected range; zero on structure-sound symbols).
  · So a bracket-owning registry would today hold two identical brackets behind
    an interface, which is the speculative generality this codebase argues
    against everywhere else.

What DOES exist is a real duplication with a real cost: strategy metadata —
names, horizons, prose, which settings switch governs which playbook — is
currently written out by hand in `server.py`'s playbook endpoint while the
behaviour lives in `setups.py`. Those two WILL drift; the "needs a liquidity
sweep" copy already survived a full session after the engine stopped requiring
one. This module is the single declaration both read.

When a strategy arrives that genuinely needs a different bracket, `evaluate`
and `bracket` hooks belong here and the full Wave 2.1 shape is correct. Not
before. That moment is the trigger, not a version number.
"""
from dataclasses import dataclass, field


STRATEGY_CONTRACT_VERSION = "strategy-contract-v0.1-draft"


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    #: The `settings.py` switch that enables it. Must exist there and be
    #: BEHAVIOURAL — turning a strategy on or off changes what the engine
    #: produces, so it restarts the forward record.
    setting: str
    #: Hold-time policy, not a timeframe. A horizon selects the exit and
    #: cooldown policy; the timeframe merely tends to correlate with it.
    horizon: str
    one_liner: str
    hunts: str
    #: Which regimes admit it, as the engine actually gates them.
    regimes: tuple
    #: Extra evidence the regime demands, or None when the regime alone suffices.
    requires: str | None = None
    status: str = "live"
    #: Populated only for planned strategies: the measured reason it matters.
    gap: str | None = None
    timeframes: tuple = field(default_factory=lambda: ("15m", "1H", "4H", "1D", "1W"))
    # Public promotion state. ``status`` remains for the legacy cockpit
    # (live/measured/planned); this vocabulary is used by automation and the
    # task-oriented opportunity read model.
    evidence_status: str = "RESEARCH"
    horizons: tuple = field(default_factory=tuple)
    trigger_timeframe: str | None = None
    structure_requires: tuple = field(default_factory=tuple)
    required_factors: tuple = field(default_factory=tuple)
    optional_factors: tuple = field(default_factory=tuple)
    entry_policy: str = "LIMIT"
    expiry_policy: str = "PLAYBOOK"
    invalidation_policy: str = "STRUCTURAL_STOP"
    exit_policy: str = "STRUCTURAL_TARGET_AND_TIME_STOP"
    contraindications: tuple = field(default_factory=lambda: (
        "STALE_DATA", "UNECONOMIC_AFTER_COSTS", "RISK_REJECTED"))
    directions: tuple = ("LONG", "SHORT")
    higher_timeframe_relationship: str = "CANONICAL_TOP_DOWN_DECISION"
    trigger_rule: str = "CLOSED_CANDLE_PLAYBOOK_TRIGGER"
    minimum_rr_after_costs: str = "ENGINE_MIN_RR"
    liquidity_rule: str = "UNIVERSE_ELIGIBLE"
    spread_rule: str = "WITHIN_PLAYBOOK_COST_BUDGET"
    volatility_rule: str = "REGIME_AND_PLAYBOOK_COMPATIBLE"
    freshness_rule: str = "ALL_REQUIRED_CANDLES_CLOSED_AND_FRESH"
    version: str = STRATEGY_CONTRACT_VERSION


PULLBACK = Strategy(
    key="pullback", name="Pullback", setting="strategy_pullback",
    horizon="swing",
    one_liner="Buy the dip in an uptrend, sell the bounce in a downtrend.",
    hunts="Trending markets — the trend is intact and price has come back.",
    regimes=("BULL_TREND", "WEAKENING_BULL", "BEAR_TREND", "WEAKENING_BEAR"),
    evidence_status="PAPER", horizons=("intraday", "swing"),
    structure_requires=("intact trend", "tested demand or supply"),
    optional_factors=("sweep", "volume", "higher-timeframe ladder"),
    trigger_timeframe="SETUP_TIMEFRAME",
    trigger_rule="ZONE_RETEST_CONFIRMED_ON_CLOSED_CANDLE",
    higher_timeframe_relationship="ALIGNED_OR_PLAYBOOK_CONDITIONAL",
    entry_policy="LIMIT_THEN_MARKET_IF_STILL_VALID",
)

REVERSAL = Strategy(
    key="reversal", name="Reversal", setting="strategy_reversal",
    horizon="swing",
    one_liner="Fade a move that has just run out of buyers, or sellers.",
    hunts="Markets in transition — the old trend has broken and a new one has "
          "not formed.",
    regimes=("TRANSITION",),
    requires="composed evidence",
    evidence_status="PAPER", horizons=("intraday", "swing"),
    structure_requires=("transition regime", "confirmed rejection"),
    required_factors=("composed reversal evidence",),
    optional_factors=("sweep", "volume", "higher-timeframe ladder"),
    trigger_timeframe="SETUP_TIMEFRAME",
    trigger_rule="TRANSITION_REJECTION_CONFIRMED_ON_CLOSED_CANDLE",
    higher_timeframe_relationship="TRANSITION_WITHOUT_DIRECTIONAL_CONFLICT",
    entry_policy="LIMIT_THEN_MARKET_IF_STILL_VALID",
)

SCALE_IN = Strategy(
    key="scale_in", name="Scale In", setting="strategy_scale_in",
    horizon="intraday",
    one_liner="Add to a position that is already working.",
    hunts="An open higher-timeframe position that has moved at least 1R your way.",
    regimes=(),
    requires="an open parent position",
    evidence_status="DISABLED", horizons=("intraday",),
    trigger_timeframe="15m",
    contraindications=("FIRST_LIVE_SAFETY_CONTRACT",),
)

# Planned entries carry the MEASURED reason they matter, so the catalogue shows
# a roadmap grounded in the rejection funnel rather than a wish list. `gap` is
# prose only — the percentages themselves are computed live from rejection
# facts, never written down (see server._rejection_regime_share).
RANGE_FADE = Strategy(
    key="range_fade", name="Range Fade", setting="strategy_range_fade",
    horizon="intraday", status="planned",
    one_liner="Buy the low of a range, sell the high.",
    hunts="Markets going sideways between two levels that keep holding.",
    regimes=("RANGE",),
    evidence_status="RESEARCH", horizons=("scalp", "intraday"),
    timeframes=("5m", "15m", "1H"), trigger_timeframe="5m",
    structure_requires=("confirmed range", "tested boundary"),
    trigger_rule="BOUNDARY_REJECTION_CONFIRMED_ON_CLOSED_CANDLE",
    higher_timeframe_relationship="NO_DIRECTIONAL_TREND_CONFLICT",
    entry_policy="LIMIT",
    gap="Ranging markets are a large share of rejected candidates — but "
        "`ranges.py` measured that almost none of them have a detected range "
        "at the moment of rejection, and none at all on symbols whose "
        "structure engine can see a break. Blocked on a longer-lived range "
        "definition, not on the strategy.",
)

BREAKOUT_RETEST = Strategy(
    key="breakout_retest", name="Breakout Retest", setting="strategy_breakout_retest",
    horizon="intraday", status="measured",
    one_liner="Trade the level that just broke, once it holds from the other side.",
    hunts="A structural break that price comes back to test.",
    regimes=(),
    requires="a confirmed close back off the broken level",
    evidence_status="RESEARCH", horizons=("scalp", "intraday"),
    timeframes=("5m", "15m", "1H"), trigger_timeframe="5m",
    structure_requires=("confirmed break", "successful retest"),
    required_factors=("close back off broken level",),
    trigger_rule="BREAK_RETEST_AND_REJECTION_CLOSE",
    higher_timeframe_relationship="ALIGNED_OR_NON_CONFLICTING_TRANSITION",
    entry_policy="MARKET_ON_CONFIRMED_RETEST",
    gap="Built and MEASURED, deliberately not enabled: n=55, -0.076 R, "
        "CI [-0.545, +0.426], P(>0) 37.4% — indistinguishable from zero on the "
        "same harness REVERSAL cleared. It keeps emitting facts so the sample "
        "grows and it can be re-graded; it trades nothing meanwhile.",
)

LIQUIDITY_SWEEP_REVERSAL = Strategy(
    key="liquidity_sweep_reversal", name="Liquidity Sweep Reversal",
    setting="strategy_liquidity_sweep_reversal", horizon="scalp",
    status="planned", evidence_status="RESEARCH", horizons=("scalp",),
    timeframes=("5m",), trigger_timeframe="5m",
    one_liner="Fade a confirmed sweep that closes back through the taken level.",
    hunts="Fast stop-runs at established liquidity followed by immediate rejection.",
    regimes=("RANGE", "TRANSITION", "WEAKENING_BULL", "WEAKENING_BEAR"),
    requires="a confirmed sweep and rejection close",
    structure_requires=("liquidity pool", "sweep", "rejection close"),
    required_factors=("sweep",), optional_factors=("relative volume", "divergence"),
    trigger_rule="SWEEP_AND_CLOSE_BACK_THROUGH_LIQUIDITY",
    higher_timeframe_relationship="NO_HARD_DIRECTIONAL_CONFLICT",
    entry_policy="MARKET_ON_CONFIRMED_SWEEP",
    gap="Research contract only. It must earn point-in-time forward evidence "
        "before it may create an executable setup.",
)

COMPRESSION_RELEASE = Strategy(
    key="compression_release", name="Compression Release",
    setting="strategy_compression_release", horizon="intraday",
    status="planned", evidence_status="RESEARCH", horizons=("intraday",),
    timeframes=("15m", "1H"), trigger_timeframe="15m",
    one_liner="Trade a confirmed expansion out of a mature compression.",
    hunts="Volatility contractions that break with structure and executable cost.",
    regimes=("RANGE", "TRANSITION"),
    requires="a mature squeeze and confirmed structural release",
    structure_requires=("compression", "break of structure"),
    required_factors=("squeeze",), optional_factors=("relative volume", "VWAP"),
    trigger_rule="MATURE_COMPRESSION_AND_STRUCTURE_RELEASE_CLOSE",
    higher_timeframe_relationship="RELEASE_DIRECTION_NOT_IN_CONFLICT",
    entry_policy="MARKET_ON_CONFIRMED_RELEASE",
    gap="Research contract only. The volatility engine supplies the measurement, "
        "but no promoted entry engine exists yet.",
)

ALL = (PULLBACK, REVERSAL, SCALE_IN, BREAKOUT_RETEST, RANGE_FADE,
       LIQUIDITY_SWEEP_REVERSAL, COMPRESSION_RELEASE)
#: "measured" is a third status, distinct from planned: the engine EXISTS and
#: runs, it simply has not earned a place in the book. Collapsing it into
#: "planned" would hide a strategy that is already producing gradeable evidence.
LIVE = tuple(s for s in ALL if s.status == "live")
MEASURED = tuple(s for s in ALL if s.status == "measured")
BY_KEY = {s.key: s for s in ALL}
#: setups.py speaks in upper-case strategy names; the registry keys are slugs.
BY_ENGINE_NAME = {s.key.upper(): s for s in ALL}


def for_engine_name(name: str) -> Strategy | None:
    """The registry entry for a name as `setups.playbook()` returns it."""
    return BY_ENGINE_NAME.get((name or "").upper())


def enabled_settings() -> dict:
    """key -> settings switch, for every LIVE strategy."""
    return {s.key: s.setting for s in LIVE}
