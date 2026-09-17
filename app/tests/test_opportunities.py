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


def test_later_risk_rejection_cannot_hide_existing_position():
    # Subsequent risk runs can reject new entries because this order owns a
    # slot. That verdict must not erase the account's recorded custody.
    item = opportunities.candidate(
        setup(),
        risk_fact={"decision": "REJECTED",
                   "reasons": ["NOT_IN_POINT_IN_TIME_UNIVERSE"]},
        record=OpportunityState.POSITION_OPEN)
    assert item.state == OpportunityState.POSITION_OPEN
    assert item.eligible is False
    assert item.entry_recommendation.order_kind == OrderKind.NONE
    assert item.strongest_counterargument == (
        "The position is already open and is being managed.")
    assert item.reasons[-1].code == "NOT_IN_POINT_IN_TIME_UNIVERSE"


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
        "DAILY_LOSS_HALT", "SAME_SIDE_HALT(SHORT,2)", "NOT_IN_POINT_IN_TIME_UNIVERSE",
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


def test_every_outbox_state_a_writer_can_produce_is_mapped():
    """Derived from the WRITERS, not listed by hand.

    `_OUTBOX_LIFECYCLE` is the lifecycle authority for a dispatched intent, and
    an unmapped state hits the `continue` in `_outbox_records` — which returns
    NO RECORD. Under opportunity-v0.8's rule the absence of a record means the
    domain has not acted, so a setup whose venue entry had already FILLED read
    READY again and was eligible to be dispatched a second time.

    Six states were missing: the five `ENTRY_*` that `monitor_private` writes
    and the `"CANCELLED"` that `shared_account.sync_manual` writes. A hand-kept
    list is what let them drift apart in the first place, so this reads the
    string literals out of the writers' own source.
    """
    import inspect
    import re

    from engine import execution, shared_account

    written = set()
    for module in (execution, shared_account):
        src = inspect.getsource(module)
        # A literal handed to the outbox event writer. The lookbehind keeps
        # `_audit_event` out — that writes the audit trail, a different table
        # with its own vocabulary (EXPIRY_CANCELLED and friends).
        written |= set(re.findall(
            r'(?<![\w])_?event\s*\(\s*\w+\s*,\s*\w+\s*,\s*"([A-Z][A-Z_]{3,})"',
            src))
        written |= set(re.findall(r'next_state\s*=\s*"([A-Z][A-Z_]{3,})"', src))
        # Direct UPDATEs, scoped to the outbox — `account_epochs` has its own
        # `state` column whose values (OPEN/DRAINING/SEALED) are not lifecycle.
        for stmt in re.findall(r'UPDATE execution_outbox[^"\']*', src):
            written |= set(re.findall(r"state\s*=\s*'([A-Z][A-Z_]{3,})'", stmt))

    # `next_state = "ENTRY_" + status` builds its name at runtime; the five it
    # can produce are asserted by name below.
    written = {s for s in written if not s.endswith("_")}

    unmapped = {s for s in written if s not in opportunities._OUTBOX_LIFECYCLE}
    assert not unmapped, (
        f"these outbox states have no lifecycle mapping, so a setup carrying "
        f"one reads as 'this domain never acted' and returns to READY: "
        f"{sorted(unmapped)}")

    # The six that were actually missing, pinned by name so a future edit that
    # drops one fails here rather than in the dispatcher.
    for state in ("ENTRY_FILLED", "ENTRY_CANCELLED", "ENTRY_CANCELED",
                  "ENTRY_REJECTED", "ENTRY_EXPIRED", "CANCELLED"):
        assert state in opportunities._OUTBOX_LIFECYCLE, state
    assert (opportunities._OUTBOX_LIFECYCLE["ENTRY_FILLED"]
            is OpportunityState.POSITION_OPEN), (
        "a filled venue entry is an OPEN POSITION — reading it as anything "
        "dispatchable is how the same zone gets entered twice")
