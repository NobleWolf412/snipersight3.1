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


def test_top_down_is_a_real_four_state_decision_not_allow_everywhere():
    assert opportunities.top_down(setup()).state == TopDownState.ALIGNED
    conflict = setup(bias={"alignment": "MIXED", "composite": "MIXED",
                           "resolved": "ALLOW", "rungs": {}})
    conflict_candidate = opportunities.candidate(conflict)
    assert conflict_candidate.setup.top_down.state == TopDownState.CONFLICT
    assert conflict_candidate.state == OpportunityState.BLOCKED
    assert conflict_candidate.entry_recommendation.order_kind == OrderKind.NONE
    blocked = opportunities.candidate(setup(), risk_fact={
        "decision": "REJECTED", "reasons": ["DAILY_LOSS_HALT"]})
    assert blocked.setup.top_down.state == TopDownState.BLOCKED


def test_ready_pullback_recommends_limit_and_never_uses_legacy_rank_for_grade():
    item = opportunities.candidate(setup(rank=99))
    assert item.state == OpportunityState.READY
    assert item.entry_recommendation.order_kind == OrderKind.LIMIT
    assert item.entry_recommendation.limit_price == Decimal("50000.10")
    assert item.evidence.grade == "UNGRADED"
    assert item.evidence.sizing_allowed is False


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


def test_expired_candidate_is_never_actionable_even_if_setup_still_says_validated():
    item = opportunities.candidate(setup(expires_at_ts=200), now=201)
    assert item.state == OpportunityState.EXPIRED
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert item.eligible is False


def test_unreadable_expiry_fails_closed():
    item = opportunities.candidate(setup(expires_at_ts="not-a-timestamp"), now=201)
    assert item.state == OpportunityState.BLOCKED
    assert item.entry_recommendation.order_kind == OrderKind.NONE


def test_missing_expiry_fails_closed_in_operational_read_model():
    item = opportunities.candidate(setup(expires_at_ts=None), now=150)
    assert item.state == OpportunityState.BLOCKED
    assert item.eligible is False


def test_empty_summary_treats_no_trade_as_a_successful_state():
    assert opportunities.summary([])["narrative"] == (
        "No setup currently meets entry rules. Scanning continues.")


def test_summary_uses_plain_singular_and_plural_copy():
    one = [{"state": "POSITION_OPEN"}]
    two = one * 2
    assert opportunities.summary(one)["narrative"] == "Managing 1 open position."
    assert opportunities.summary(two)["narrative"] == "Managing 2 open positions."
