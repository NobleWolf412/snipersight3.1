from decimal import Decimal

from engine import opportunities
from engine.contracts import OpportunityState, OrderKind, TopDownState


def setup(**overrides):
    data = {
        "setup_id": "BTC|15m|PULLBACK|1", "symbol": "BTCUSDT", "tf": "15m",
        "strategy": "PULLBACK", "direction": "LONG", "state": "VALIDATED",
        "confirmed_at": 100, "expires_at_ts": 200, "entry": "50000.10",
        "sl": "49000.10", "tp": "52000.10", "rr": "2.0",
        "regime": "BULL_TREND", "zone_strength": 4,
        "confluence": {"sweep": True, "volume": None},
        "bias": {"alignment": "WITH", "composite": "UP",
                 "resolved": "ALLOW", "rungs": {"1H": "UP"}},
    }
    data.update(overrides)
    return data


def test_top_down_states_describe_the_ladder_and_only_policy_blocks():
    """One HTF authority: the playbook's recorded BIAS_POLICY verdict.

    v0.5 re-derived a policy here — WITH-only eligible, everything else held —
    which was a second, ungraded authority over the one number bias.py owns,
    and it scored a missing measurement as a bad one (the rule
    bias.validate_policy refuses at import time; measured cost 1.02 R/trade
    when setups.py made the same mistake). The four states stay as the honest
    display of the ladder; only `resolved == "BLOCK"` gates.
    """
    assert opportunities.top_down(setup()).state == TopDownState.ALIGNED

    # The ladder disagreeing is a counterargument, not a veto. The playbook's
    # policy said ALLOW, and dispatch must rehearse the book paper measures.
    conflict = setup(bias={"alignment": "MIXED", "composite": "MIXED",
                           "resolved": "ALLOW", "rungs": {}})
    conflict_candidate = opportunities.candidate(conflict)
    assert conflict_candidate.setup.top_down.state == TopDownState.CONFLICT
    assert conflict_candidate.state == OpportunityState.READY
    assert conflict_candidate.eligible is True
    assert conflict_candidate.entry_recommendation.order_kind == OrderKind.LIMIT
    assert conflict_candidate.strongest_counterargument == (
        "Higher-timeframe structure conflicts with this direction.")

    blocked = opportunities.candidate(setup(), risk_fact={
        "decision": "REJECTED", "reasons": ["DAILY_LOSS_HALT"]})
    assert blocked.setup.top_down.state == TopDownState.ALIGNED


def test_a_missing_ladder_reading_never_holds_dispatch():
    # UNKNOWN IS NOT A WEAK FORM OF AGAINST — engine/bias.py. A setup with no
    # bias block at all (or a FLAT/UNKNOWN composite) reads CONDITIONAL for
    # display and stays fully eligible.
    unmeasured = setup(bias=None)
    item = opportunities.candidate(unmeasured)
    assert item.setup.top_down.state == TopDownState.CONDITIONAL
    assert item.state == OpportunityState.READY
    assert item.eligible is True
    assert item.entry_recommendation.order_kind == OrderKind.LIMIT

    flat = setup(bias={"alignment": "FLAT", "composite": "FLAT",
                       "resolved": "ALLOW", "rungs": {"1H": "FLAT"}})
    item = opportunities.candidate(flat)
    assert item.setup.top_down.state == TopDownState.CONDITIONAL
    assert item.eligible is True


def test_the_playbooks_own_policy_block_is_the_one_ladder_gate():
    armed = setup(bias={"alignment": "AGAINST", "composite": "DOWN",
                        "resolved": "BLOCK", "rungs": {"1H": "DOWN"}})
    item = opportunities.candidate(armed)
    assert item.setup.top_down.state == TopDownState.BLOCKED
    assert item.state == OpportunityState.BLOCKED
    assert item.eligible is False
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert item.strongest_counterargument == (
        "This playbook's own higher-timeframe policy blocks this entry.")


def test_ready_pullback_recommends_limit_and_never_uses_legacy_rank_for_grade():
    item = opportunities.candidate(setup(rank=99))
    assert item.state == OpportunityState.READY
    assert item.entry_recommendation.order_kind == OrderKind.LIMIT
    assert item.entry_recommendation.limit_price == Decimal("50000.10")
    assert item.evidence.grade == "UNGRADED"
    assert item.evidence.sizing_allowed is False
    assert item.strongest_counterargument == (
        "No safety issue is currently blocking this setup.")


def test_legacy_setup_identity_is_hydrated_by_the_server_not_the_browser():
    item = opportunities.candidate(setup(symbol=None, tf=None))
    assert item.setup.symbol == "BTC"
    assert item.setup.timeframe == "15m"


def test_ranking_uses_lifecycle_and_quality_not_legacy_rank():
    weak = opportunities.candidate(setup(setup_id="weak", rr="1.5", rank=100))
    strong = opportunities.candidate(setup(setup_id="strong", rr="3", rank=1))
    forming = opportunities.candidate(setup(setup_id="forming", state="FORMING", rr="3"))
    assert [x.setup.setup_id for x in opportunities.rank([weak, forming, strong])] == [
        "strong", "weak", "forming"]


def test_blocked_candidate_recommends_no_trade():
    item = opportunities.candidate(setup(), risk_fact={
        "decision": "REJECTED", "reasons": ["DATA_HEALTH_BLOCKED"]})
    assert item.state == OpportunityState.BLOCKED
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert item.eligible is False


def test_rejected_risk_outranks_shadow_fill_and_explains_the_real_reason():
    item = opportunities.candidate(
        setup(),
        risk_fact={"decision": "REJECTED",
                   "reasons": ["NOT_IN_POINT_IN_TIME_UNIVERSE"]},
        order={"event": "FILLED"})
    assert item.state == OpportunityState.BLOCKED
    assert item.eligible is False
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert item.strongest_counterargument == (
        "Trade skipped — BTCUSDT did not meet the bot's market-selection rules "
        "when the setup confirmed.")
    assert item.reasons[-1].code == "NOT_IN_POINT_IN_TIME_UNIVERSE"
    assert item.reasons[-1].summary == item.strongest_counterargument


def test_shadow_market_rejection_says_research_only_in_plain_language():
    item = opportunities.candidate(
        setup(symbol="PF_DOGEUSD"),
        risk_fact={"decision": "REJECTED",
                   "reasons": ["NOT_IN_POINT_IN_TIME_UNIVERSE"]})
    assert item.strongest_counterargument == (
        "Trade skipped — this is a research-only market, so the bot records "
        "setups but does not fund them.")


def test_every_current_risk_refusal_has_trader_readable_copy():
    reasons = [
        "OPERATOR_HALT", "DATA_HEALTH_BLOCKED", "DRAWDOWN_HALT(8.0%)",
        "STRATEGY_DISABLED(PULLBACK)", "COOLDOWN(STOP,12h)",
        "DAILY_LOSS_HALT", "NOT_IN_POINT_IN_TIME_UNIVERSE",
        "INVALID_STOP_DISTANCE", "SHORT_UNSUPPORTED_COINBASE_SPOT",
        "SCALE_IN_FORBIDDEN(0R)", "PARENT_CLOSED", "CONCURRENT_LIMIT(2)",
        "EXPOSURE_LIMIT", "STOP_BEYOND_LIQUIDATION(99@10x)",
        "BELOW_MIN_NOTIONAL", "PARTICIPATION_TOO_THIN", "ZERO_RISK_SIZE",
    ]
    for reason in reasons:
        item = opportunities.candidate(
            setup(), risk_fact={"decision": "REJECTED", "reasons": [reason]})
        assert item.strongest_counterargument.startswith("Trade skipped —")
        assert reason.replace("_", " ").lower() not in \
            item.strongest_counterargument.lower()


def test_forming_setup_is_progress_not_an_entry_recommendation():
    item = opportunities.candidate(setup(state="FORMING"))
    assert item.state == OpportunityState.FORMING
    assert item.eligible is False
    assert item.entry_recommendation.order_kind == OrderKind.NONE


def test_expired_candidate_is_never_actionable_even_if_setup_still_says_validated():
    item = opportunities.candidate(setup(expires_at_ts=200), now=201)
    assert item.state == OpportunityState.EXPIRED
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert item.eligible is False


def test_unreadable_expiry_fails_closed():
    item = opportunities.candidate(setup(expires_at_ts="not-a-timestamp"), now=201)
    assert item.state == OpportunityState.BLOCKED
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert "expiry is unreadable" in item.strongest_counterargument


def test_missing_expiry_fails_closed_in_operational_read_model():
    item = opportunities.candidate(setup(expires_at_ts=None), now=150)
    assert item.state == OpportunityState.BLOCKED
    assert item.eligible is False
    assert "no expiry" in item.strongest_counterargument


def test_empty_summary_treats_no_trade_as_a_successful_state():
    assert opportunities.summary([])["narrative"] == (
        "No setup currently meets entry rules. Scanning continues.")


def test_summary_uses_plain_singular_and_plural_copy():
    one = [{"state": "POSITION_OPEN"}]
    two = one * 2
    assert opportunities.summary(one)["narrative"] == "Managing 1 open position."
    assert opportunities.summary(two)["narrative"] == "Managing 2 open positions."


def test_summary_separates_ready_entries_from_forming_progress():
    result = opportunities.summary([{"state": "FORMING"}])
    assert result["actionable"] == 0
    assert result["narrative"] == "1 setup is forming; no entry is ready."
