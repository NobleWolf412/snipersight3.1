"""The optional exit rule is causal, pinned per intent, and restart-safe."""
import json
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from engine import execution, lifecycle, positions, profit_protection, store
from engine.contracts import (AutomationMode, BrokerOrder, DecisionReason,
                              ExecutionPlan, Fill, OrderIntent, OrderKind,
                              RiskDecision, to_wire)


HOUR = 3600


def _bar(ts, high="51100", low="50050", close="50900"):
    return {"open_ts": ts, "open": "50500", "high": high,
            "low": low, "close": close}


def _candidate(**changes):
    args = dict(policy=profit_protection.COST_COVER, symbol="BTCUSDT",
                direction="LONG", entry=Decimal("50000"),
                original_stop=Decimal("49000"),
                current_stop=Decimal("49000"),
                target=Decimal("52000"), bar=_bar(0), bars_survived=2,
                atr=Decimal("200"), entry_role="MAKER", tf_seconds=HOUR,
                tick=Decimal("0.1"))
    args.update(changes)
    return profit_protection.candidate(**args)


def test_candidate_requires_closed_survival_and_risk_move():
    assert _candidate(policy="OFF") is None
    assert _candidate(bars_survived=1) is None
    assert _candidate(atr=None) is None
    assert _candidate(bar=_bar(0, high="50999")) is None
    moved = _candidate()
    assert Decimal("50000") < moved < Decimal("52000")
    assert moved % Decimal("0.1") == 0
    assert _candidate(current_stop=moved) is None
    short = _candidate(direction="SHORT", original_stop=Decimal("51000"),
                       current_stop=Decimal("51000"),
                       bar={"open_ts": 0, "open": "49500", "high": "49950",
                            "low": "48900", "close": "49100"},
                       target=Decimal("48000"))
    assert Decimal("48000") < short < Decimal("50000")


def test_paper_stop_applies_only_to_next_candle_and_preserves_original_risk():
    bars = [_bar(0, high="50500", low="49900", close="50100"),
            _bar(HOUR, high="51100", low="50050", close="50900"),
            _bar(2*HOUR, high="50950", low="49900", close="50000")]
    kwargs = dict(symbol="BTCUSDT", direction="LONG", entry=Decimal("50000"),
                  original_stop=Decimal("49000"), target=Decimal("52000"),
                  entry_role="MAKER", tf_seconds=HOUR, max_bars=100)
    off = profit_protection.walk_paper(policy="OFF", bars=bars,
        atr=[Decimal("200")]*3, cutoff=3*HOUR, observed_at=3*HOUR, **kwargs)
    first = profit_protection.walk_paper(policy="COST_COVER", bars=bars[:2],
        atr=[Decimal("200")]*2, cutoff=2*HOUR, observed_at=2*HOUR, **kwargs)
    on = profit_protection.walk_paper(policy="COST_COVER", bars=bars,
        atr=[Decimal("200")]*3, cutoff=3*HOUR, observed_at=3*HOUR,
        scheduled_move=first["proposal"], **kwargs)
    assert off["exit"] is None and off["stop"] == Decimal("49000")
    assert first["exit"] is None and first["stop"] == Decimal("49000")
    assert first["proposal"]["effective_at"] == 2*HOUR
    assert on["exit"][0] == "SL" and on["exit"][2] == 2
    assert on["exit"][1] <= on["stop"]  # adverse gap convention


def test_confirmation_that_fades_does_not_claim_a_protected_profit():
    bars = [_bar(0, high="50500", low="49900", close="50100"),
            _bar(HOUR, high="51100", low="49900", close="50001"),
            _bar(2*HOUR, high="51100", low="50050", close="50900"),
            _bar(3*HOUR, high="50950", low="49900", close="50000")]
    kwargs = dict(
        policy="COST_COVER", symbol="BTCUSDT", direction="LONG",
        entry=Decimal("50000"), original_stop=Decimal("49000"),
        target=Decimal("52000"),
        entry_role="MAKER", tf_seconds=HOUR, max_bars=100)
    faded = profit_protection.walk_paper(bars=bars[:2],
        atr=[Decimal("200")]*2, cutoff=2*HOUR, observed_at=2*HOUR, **kwargs)
    assert faded["proposal"] is None
    recovered = profit_protection.walk_paper(bars=bars[:3],
        atr=[Decimal("200")]*3, cutoff=3*HOUR, observed_at=3*HOUR, **kwargs)
    assert recovered["proposal"]["effective_at"] == 3*HOUR
    managed = profit_protection.walk_paper(bars=bars,
        atr=[Decimal("200")]*4, cutoff=4*HOUR, observed_at=4*HOUR,
        scheduled_move=recovered["proposal"], **kwargs)
    assert managed["exit"][2] == 3


def test_adverse_gap_after_move_fills_at_open_not_the_protected_level():
    bars = [_bar(0, high="50500", low="49900", close="50100"),
            _bar(HOUR, high="51100", low="50050", close="50900"),
            {"open_ts": 2*HOUR, "open": "49800", "high": "50000",
             "low": "49700", "close": "49900"}]
    kwargs = dict(
        policy="COST_COVER", symbol="BTCUSDT", direction="LONG",
        entry=Decimal("50000"), original_stop=Decimal("49000"),
        target=Decimal("52000"),
        entry_role="MAKER", tf_seconds=HOUR, max_bars=100)
    first = profit_protection.walk_paper(bars=bars[:2],
        atr=[Decimal("200")]*2, cutoff=2*HOUR, observed_at=2*HOUR,
        **kwargs)
    managed = profit_protection.walk_paper(bars=bars,
        atr=[Decimal("200")]*3, cutoff=3*HOUR, observed_at=3*HOUR,
        scheduled_move=first["proposal"], **kwargs)
    assert managed["exit"][0] == "SL"
    assert managed["exit"][1] == Decimal("49800")


def test_late_observation_cannot_backdate_a_paper_stop():
    bars = [_bar(0, high="50500", low="49900", close="50100"),
            _bar(HOUR, high="51100", low="50050", close="50900")]
    kwargs = dict(policy="COST_COVER", symbol="BTCUSDT", direction="LONG",
                  entry=Decimal("50000"), original_stop=Decimal("49000"),
                  target=Decimal("52000"), bars=bars,
                  atr=[Decimal("200")]*2, entry_role="MAKER",
                  tf_seconds=HOUR, max_bars=100, cutoff=2*HOUR)
    late = profit_protection.walk_paper(observed_at=2*HOUR+300, **kwargs)
    assert late["stop"] == Decimal("49000")
    assert late["proposal"]["confirmed_at"] == 2*HOUR
    assert late["proposal"]["observed_at"] == 2*HOUR+300
    assert late["proposal"]["effective_at"] == 3*HOUR
    stale = profit_protection.walk_paper(observed_at=3*HOUR+1, **kwargs)
    assert stale["proposal"] is None


class StopBroker:
    environment = "testnet"

    def __init__(self):
        self.stop = Decimal("49000")
        self.replacements = []

    def price_tick(self, symbol):
        return Decimal("0.1")

    def order_status(self, symbol, client_order_id, broker_order_id=None):
        return BrokerOrder("venue-stop", client_order_id, symbol, "New",
                           OrderKind.LIMIT, Decimal("0.01"), Decimal(0),
                           None, True, 0, stop_price=self.stop)

    def replace(self, symbol, client_order_id, *, quantity, stop,
                timeout_seconds=None):
        self.replacements.append(stop)
        self.stop = stop
        return self.order_status(symbol, client_order_id)


def test_private_stop_uses_same_rule_and_confirms_venue_price():
    with tempfile.TemporaryDirectory() as tmp:
        con = store.connect(Path(tmp) / "paper.db")
        try:
            execution._ensure(con)
            positions._ensure(con)
            lifecycle._ensure(con)
            now = int(time.time()) // HOUR * HOUR
            intent = OrderIntent(
                "private-1", "setup-1", AutomationMode.TESTNET, "BTCUSDT", "LONG",
                OrderKind.LIMIT, Decimal("0.01"), Decimal("50000"),
                Decimal("49000"), (Decimal("52000"),), False,
                now-2*HOUR, "playbook-v1", "private-key",
                timeframe="1H", profit_protection="COST_COVER")
            risk = RiskDecision(True, "APPROVED", Decimal("10"),
                Decimal("0.01"), Decimal("500"), Decimal("0.05"),
                (DecisionReason("OK", "approved"),))
            plan = ExecutionPlan(intent, risk, "phemex-perp", "ISOLATED", "ONE_WAY")
            execution.enqueue(con, intent, plan=plan)
            con.execute("INSERT INTO managed_positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (intent.intent_id, intent.intent_id, "BTCUSDT", "LONG",
                         "0.01", "50000", "49000", "BOT", "private-1-sl",
                         "CONFIRMED", "OPEN", now-2*HOUR))
            con.execute("INSERT INTO lifecycle_orders(position_id,role,client_order_id,"
                        "broker_order_id,quantity,price,state,updated_at) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (intent.intent_id, "STOP", "private-1-sl", "venue-stop",
                         "0.01", "49000", "NEW", now-2*HOUR))
            positions._event(con, intent.intent_id, "FILL", to_wire(Fill(
                "fill-1", "venue-entry", "BTCUSDT", Decimal("0.01"),
                Decimal("50000"), Decimal("0"), now-2*HOUR+100)))
            for i in range(22):
                ts = now-(22-i)*HOUR
                bar = _bar(ts) if i == 21 else {
                    "open_ts": ts, "open": "50000", "high": "50100",
                    "low": "49900", "close": "50000"}
                con.execute("INSERT INTO candles(symbol,tf,open_ts,open,high,low,"
                            "close,volume,source,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("BTCUSDT", "1H", ts, bar["open"], bar["high"],
                             bar["low"], bar["close"], "10", "fixture", ts))
            con.commit()
            broker = StopBroker()
            first = positions.protect_profit(con, broker, cutoff=now)
            assert first["moved"] == [intent.intent_id], first
            assert not first["refused"]
            assert len(broker.replacements) == 1
            assert Decimal(con.execute("SELECT stop FROM managed_positions").fetchone()[0]) == broker.stop
            assert positions.protect_profit(con, broker, cutoff=now)["moved"] == []
            assert len(broker.replacements) == 1
            history = con.execute("SELECT payload FROM position_events WHERE event='PROFIT_STOP_MOVED'").fetchall()
            assert len(history) == 1
            assert json.loads(history[0][0])["old_stop"] == "49000"
        finally:
            con.close()
