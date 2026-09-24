import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine import (diagnostic_status, liquidity, open_interest, pipeline, research, researchsignals,
                    setups, store)


def fact(con, *, symbol="BTCUSDT", tf="1H", kind, at, version, payload):
    store.insert_fact(con, symbol=symbol, tf=tf, kind=kind,
                      market_time=at - 3600, confirmed_at=at,
                      algo_version=version, payload=payload)
    con.commit()


def test_stoch_rsi_is_decimal_rounded_and_keeps_warmup_unavailable():
    closes = [Decimal(100 + ((i * 7) % 19)) + Decimal(i) / Decimal(10)
              for i in range(60)]
    raw, k, d = research.compute_stoch_rsi(closes)
    assert all(value is None for value in k[:29])
    assert all(value is None for value in d[:31])
    assert all(value is None or isinstance(value, Decimal) for value in raw + k + d)
    assert str(k[-1]) == "38.709141"
    assert str(d[-1]) == "33.139189"


def test_stoch_exit_does_not_bridge_an_unavailable_window(tmp_path):
    con = store.connect(tmp_path / "stoch-gap.db")
    research.activate(con, 1)
    candles = [{"open_ts": index * 3600, "close": str(100 + index)}
               for index in range(3)]
    with patch.object(research, "compute_stoch_rsi",
                      return_value=([Decimal(10), None, Decimal(25)],
                                    [Decimal(10), None, Decimal(25)],
                                    [Decimal(9), None, Decimal(20)])):
        research._emit_stoch(con, "BTCUSDT", "1H", candles, 3600)
    rows = store.get_facts(con, "BTCUSDT", "1H", "stoch_rsi",
                           research.STOCH_RSI_VERSION)
    assert json.loads(rows[-1]["payload"])["event"] == "RISING"
    con.close()


def test_setup_snapshot_starts_at_activation_and_never_reconstructs(tmp_path):
    con = store.connect(tmp_path / "research.db")
    research.activate(con, 1_000)
    old = {"setup_id": "old", "state": "VALIDATED", "direction": "LONG",
           "zone_id": "z-old"}
    fact(con, kind="setup", at=900, version=setups.SETUP_VERSION, payload=old)
    researchsignals.run(con, "BTCUSDT", "1H", 3600, fact_floor=0)
    assert researchsignals.for_setup(con, "old") is None

    floor = con.execute("SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0]
    current = {"setup_id": "current", "state": "VALIDATED", "direction": "LONG",
               "zone_id": "z-current"}
    fact(con, kind="setup", at=1_100, version=setups.SETUP_VERSION, payload=current)
    fact(con, kind="stoch_rsi", at=1_050, version=research.STOCH_RSI_VERSION,
         payload={"event": "OVERSOLD_EXIT", "direction": "BULL", "k": "24", "d": "18"})
    researchsignals.run(con, "BTCUSDT", "1H", 3600, fact_floor=floor)
    captured = researchsignals.for_setup(con, "current")
    assert captured and captured["as_of"] == 1_100

    fact(con, kind="stoch_rsi", at=1_200, version=research.STOCH_RSI_VERSION,
         payload={"event": "OVERBOUGHT_EXIT", "direction": "BEAR", "k": "76", "d": "82"})
    later_floor = con.execute("SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0]
    researchsignals.run(con, "BTCUSDT", "1H", 3600,
                        fact_floor=later_floor)
    assert researchsignals.for_setup(con, "current") == captured
    con.close()


def test_setup_missed_in_its_live_cycle_is_never_reconstructed(tmp_path):
    con = store.connect(tmp_path / "missed-snapshot.db")
    research.activate(con, 1_000)
    missed = {"setup_id": "missed", "state": "VALIDATED", "direction": "LONG"}
    fact(con, kind="setup", at=1_100, version=setups.SETUP_VERSION,
         payload=missed)
    # A later live cycle starts after this setup fact already exists.
    later_floor = con.execute("SELECT MAX(id) FROM facts").fetchone()[0]
    researchsignals.run(con, "BTCUSDT", "1H", 3600,
                        fact_floor=later_floor)
    assert researchsignals.for_setup(con, "missed") is None
    con.close()


def test_research_fact_generation_refuses_to_run_before_activation(tmp_path):
    con = store.connect(tmp_path / "inactive.db")
    result = research.run(con, "BTCUSDT", "1H", 3600)
    assert result["availability"] == "INACTIVE"
    assert con.execute("SELECT COUNT(*) FROM facts WHERE kind IN "
                       "('order_block','structure_sequence','stoch_rsi',"
                       "'hidden_divergence')").fetchone()[0] == 0
    con.close()


def test_open_interest_uses_fixed_observed_at_and_exact_strings(tmp_path):
    con = store.connect(tmp_path / "oi.db")
    research.activate(con, 10_000)
    with patch.object(open_interest.phemex, "open_interest_snapshot",
                      return_value=open_interest.phemex.OpenInterestSnapshot(
                          {"BTCUSDT": {"open_interest": "1000.1250",
                                       "price": "50000.0100", "source_ts": 99}},
                          supported_contract_count=137)):
        open_interest.collect(con, ["BTCUSDT"], 10_000)
    with patch.object(open_interest.phemex, "open_interest_snapshot",
                      return_value=open_interest.phemex.OpenInterestSnapshot(
                          {"BTCUSDT": {"open_interest": "1100.1250",
                                       "price": "51000.0100", "source_ts": 100}},
                          supported_contract_count=138)):
        open_interest.collect(con, ["BTCUSDT"], 13_600)
    rows = con.execute("SELECT observed_at,value,price FROM open_interest ORDER BY observed_at").fetchall()
    assert rows == [(10_000, "1000.1250", "50000.0100"),
                    (13_600, "1100.1250", "51000.0100")]
    signal = store.get_facts(con, "BTCUSDT", "1H", "open_interest_signal",
                             research.OPEN_INTEREST_SIGNAL_VERSION)[-1]
    payload = json.loads(signal["payload"])
    assert signal["confirmed_at"] == 13_600
    assert payload["direction"] == "BULL"
    assert payload["value"] == "1100.1250"
    assert open_interest.status(con, 13_601)["supported_contract_count"] == 138
    con.close()


def test_open_interest_failure_is_explicit_and_never_zero(tmp_path):
    con = store.connect(tmp_path / "oi-failure.db")
    research.activate(con, 20_000)
    with patch.object(open_interest.phemex, "open_interest_snapshot",
                      side_effect=TimeoutError("feed late")):
        result = open_interest.collect(con, ["BTCUSDT"], 20_000)
    assert result["failed"] == 1 and "error" in result
    status = open_interest.status(con, 20_001)
    assert status["freshness"] == "MISSING"
    assert status["last_successful_observation"] is None
    assert status["failed_requests"] == 1
    assert status["failed_collection_attempts"] == 1
    assert status["missing_contract_observations"] == 1
    assert status["supported_contract_count"] is None
    diagnostics = diagnostic_status.snapshot(con, now=20_001,
                                               data_dir=tmp_path)
    assert diagnostics["research_feeds"]["open_interest"]["last_error"]
    con.close()


def test_open_interest_support_is_unknown_before_first_collection(tmp_path):
    con = store.connect(tmp_path / "oi-unknown.db")
    assert open_interest.status(con, 1)["supported_contract_count"] is None
    con.close()


def test_open_interest_does_not_call_a_gap_recovery_one_hour_change(tmp_path):
    con = store.connect(tmp_path / "oi-gap.db")
    research.activate(con, 10_000)
    for observed_at, value in ((10_000, "1000"), (17_200, "1200")):
        with patch.object(open_interest.phemex, "open_interest_snapshot",
                          return_value={"BTCUSDT": {"open_interest": value,
                                                    "price": value,
                                                    "source_ts": observed_at}}):
            open_interest.collect(con, ["BTCUSDT"], observed_at)
    assert store.get_facts(con, "BTCUSDT", "1H", "open_interest_signal",
                           research.OPEN_INTEREST_SIGNAL_VERSION) == []
    con.close()


def test_research_grade_requires_both_locked_floors():
    assert not research.sample_ready(29, 30, 8, 8)
    assert not research.sample_ready(30, 30, 7, 8)
    assert research.sample_ready(30, 30, 8, 8)


def test_gradeable_evidence_applies_detector_level_multiple_test_correction(tmp_path):
    con = store.connect(tmp_path / "gradeable.db")
    research.activate(con, 900)
    candidates = []
    snapshots = {}
    for index in range(60):
        exposed = index % 2 == 0
        setup_id = f"setup-{index}"
        candidates.append({"setup_id": setup_id, "tf": "1H",
                           "symbol": f"SYM{(index // 2) % 8}",
                           "confirmed_at": 1_000 + index,
                           "r": 2.0 if exposed else -1.0})
        snapshots[setup_id] = {
            "rows": [{"key": family,
                       "cells": [{"family": family, "timeframe": "1H",
                                    "status": "ALIGNED" if exposed else "OPPOSED",
                                    "raw": ("Complete" if exposed else "Unordered")
                                    if family == "structure_sequence" else "Observed"}]}
                     for family in research.HYPOTHESES]
        }
    with patch.object(research.factorstats, "load_candidates",
                      return_value=(candidates, [])), patch(
            "engine.researchsignals.for_setup",
            side_effect=lambda _con, setup_id: snapshots[setup_id]):
        report = research.evidence_report(con)
    assert all(row["sample_ok"] for row in report["rows"])
    assert all(row["q_value"] is not None for row in report["rows"])
    assert all(row["verdict"] == "Proven useful" for row in report["rows"])
    con.close()


def test_research_modules_are_not_in_the_priority_trading_phase():
    assert research not in pipeline._PRIORITY
    assert researchsignals not in pipeline._PRIORITY


def test_open_interest_network_collection_is_after_routing_phase():
    source = (Path(__file__).resolve().parents[1] / "live.py").read_text(
        encoding="utf-8")
    normal_path = source[source.index('routed = autotrader.run'):
                         source.index('for i, sym in enumerate(scan, 1):',
                                      source.index('research_started ='))]
    assert normal_path.index('routed = autotrader.run') < normal_path.index(
        'open_interest.collect')


def test_research_snapshot_does_not_rewrite_setup_plan_or_routing_fields(tmp_path):
    con = store.connect(tmp_path / "isolation.db")
    research.activate(con, 1_000)
    setup_payload = {"setup_id": "isolated", "state": "VALIDATED",
                     "direction": "LONG", "score": "7", "eligible": True,
                     "entry": "100", "stop": "98", "targets": ["104"],
                     "risk_usd": "20", "routing": "PAPER"}
    floor = con.execute("SELECT COALESCE(MAX(id),0) FROM facts").fetchone()[0]
    fact(con, kind="setup", at=1_100, version=setups.SETUP_VERSION,
         payload=setup_payload)
    before = [row["payload"] for row in store.get_facts(
        con, "BTCUSDT", "1H", "setup", setups.SETUP_VERSION)]
    researchsignals.run(con, "BTCUSDT", "1H", 3600, fact_floor=floor)
    after = [row["payload"] for row in store.get_facts(
        con, "BTCUSDT", "1H", "setup", setups.SETUP_VERSION)]
    assert after == before
    assert con.execute("SELECT COUNT(*) FROM facts WHERE kind IN "
                       "('risk','risk_paper','order','exec')").fetchone()[0] == 0
    con.close()


def test_results_verdict_distinguishes_unavailable_from_collecting(tmp_path):
    con = store.connect(tmp_path / "verdicts.db")
    with patch.object(research.factorstats, "load_candidates",
                      return_value=([], [])):
        assert research.evidence_report(con)["verdict"] == "Data unavailable"
        research.activate(con, 1_000)
        report = research.evidence_report(con)
    assert report["verdict"] == "Collecting evidence"
    assert all(item["status"] == "EXPLORATORY_UNCOLLECTED"
               for row in report["rows"]
               for item in row["other_patterns_observed"])
    con.close()


def test_matrix_distinguishes_missing_stale_and_not_applicable(tmp_path):
    con = store.connect(tmp_path / "states.db")
    research.activate(con, 1_000)
    fact(con, kind="open_interest_signal", at=1_000,
         version=research.OPEN_INTEREST_SIGNAL_VERSION,
         payload={"event": "ONE_HOUR_CHANGE", "direction": "BULL",
                  "label": "Expanding", "value": "12", "change_1h": "2"})
    result = research.matrix(con, "BTCUSDT", as_of=1_000,
                             direction="LONG", now=10_000)
    cells = {(row["key"], cell["timeframe"]): cell["status"]
             for row in result["rows"] for cell in row["cells"]}
    assert cells[("trend", "15m")] == "MISSING"
    assert cells[("open_interest", "1H")] == "STALE"
    assert cells[("open_interest", "4H")] == "NOT_APPLICABLE"
    assert research._status("BULL", "LONG") == "ALIGNED"
    assert research._status("BEAR", "LONG") == "OPPOSED"
    con.close()


def test_later_opposed_block_does_not_mask_qualifying_primary_block(tmp_path):
    con = store.connect(tmp_path / "competing-blocks.db")
    research.activate(con, 900)
    for at, direction, bottom, top in (
            (1_000, "BULL", "95", "105"),
            (1_100, "BEAR", "200", "210")):
        fact(con, kind="order_block", at=at,
             version=research.ORDER_BLOCK_VERSION,
             payload={"event": "CREATED",
                      "variant": "LAST_OPPOSITE_BEFORE_BREAK",
                      "direction": direction, "bottom": bottom, "top": top,
                      "block_id": f"block-{at}", "break_ts": at})
    result = research.matrix(
        con, "BTCUSDT", as_of=1_200, direction="LONG",
        setup_payload={"tf": "1H", "zone_bottom": "90", "zone_top": "110"},
        now=1_200)
    order_block = next(row for row in result["rows"]
                       if row["key"] == "order_block")["cells"][1]
    assert order_block["status"] == "ALIGNED"
    assert order_block["confirmed_at"] == 1_000
    con.close()


def test_order_block_uses_last_opposite_before_break_without_swing_floor(tmp_path):
    con = store.connect(tmp_path / "order-block-contract.db")
    research.activate(con, 1)
    candles = [
        {"open_ts": 100, "open": "10", "high": "11", "low": "8", "close": "9"},
        {"open_ts": 200, "open": "9", "high": "11", "low": "9", "close": "10"},
        {"open_ts": 300, "open": "10", "high": "12", "low": "10", "close": "11"},
        {"open_ts": 400, "open": "11", "high": "14", "low": "11", "close": "13"},
    ]
    store.insert_fact(con, symbol="BTCUSDT", tf="1H", kind="structure",
                      market_time=400, confirmed_at=500,
                      algo_version=research.structure.STRUCTURE_VERSION,
                      payload={"event": "BOS", "direction": "BULL",
                               "level_swing_ts": 250, "level": "12"})
    count, blocks = research._emit_order_blocks(con, "BTCUSDT", "1H", candles)
    assert count == 1
    assert blocks[0]["source_candle_ts"] == 100
    con.close()


def test_structure_sequence_same_candle_is_unordered_control(tmp_path):
    con = store.connect(tmp_path / "sequence-contract.db")
    research.activate(con, 1)
    store.insert_fact(con, symbol="BTCUSDT", tf="1H", kind="liquidity",
                      market_time=400, confirmed_at=500,
                      algo_version=liquidity.LIQ_VERSION,
                      payload={"event": "SWEEP", "side": "LOW", "pool_id": "p"})
    block = {"direction": "BULL", "block_id": "b", "source_candle_ts": 300,
             "break_ts": 400, "confirmed_at": 500}
    assert research._emit_sequences(con, "BTCUSDT", "1H", [block], 3600) == 1
    result = research.matrix(con, "BTCUSDT", as_of=600, direction="LONG", now=600)
    sequence = next(row for row in result["rows"]
                    if row["key"] == "structure_sequence")["cells"][1]
    assert sequence["raw"] == "Unordered"
    assert research.primary_exposure(result, "1H")["structure_sequence"] == "CONTROL"
    sequence["raw"] = "Partial"
    assert research.primary_exposure(result, "1H")["structure_sequence"] == "MISSING"
    con.close()


def test_later_partial_sequence_does_not_mask_complete_primary(tmp_path):
    con = store.connect(tmp_path / "sequence-competing.db")
    research.activate(con, 1)
    for at, state in ((500, "COMPLETE"), (600, "PARTIAL")):
        fact(con, kind="structure_sequence", at=at,
             version=research.STRUCTURE_SEQUENCE_VERSION,
             payload={"event": "SEQUENCE", "state": state,
                      "direction": "BULL", "block_id": f"b-{at}",
                      "ordered": state == "COMPLETE", "linked": True})
    result = research.matrix(con, "BTCUSDT", as_of=700,
                             direction="LONG", now=700)
    sequence = next(row for row in result["rows"]
                    if row["key"] == "structure_sequence")["cells"][1]
    assert sequence["raw"] == "Complete"
    assert sequence["confirmed_at"] == 500
    assert research.primary_exposure(result, "1H")["structure_sequence"] == "EXPOSED"
    con.close()


def test_future_sweep_unordered_control_is_not_backdated(tmp_path):
    con = store.connect(tmp_path / "sequence-future-sweep.db")
    research.activate(con, 1)
    store.insert_fact(con, symbol="BTCUSDT", tf="1H", kind="liquidity",
                      market_time=500, confirmed_at=700,
                      algo_version=liquidity.LIQ_VERSION,
                      payload={"event": "SWEEP", "side": "LOW", "pool_id": "future"})
    block = {"direction": "BULL", "block_id": "b", "source_candle_ts": 300,
             "break_ts": 400, "confirmed_at": 450}
    research._emit_sequences(con, "BTCUSDT", "1H", [block], 3600)
    row = store.get_facts(con, "BTCUSDT", "1H", "structure_sequence",
                          research.STRUCTURE_SEQUENCE_VERSION)[0]
    assert row["confirmed_at"] == 700
    assert json.loads(row["payload"])["state"] == "UNORDERED"
    con.close()


def test_matrix_has_explicit_top_level_availability(tmp_path):
    con = store.connect(tmp_path / "availability.db")
    research.activate(con, 1)
    result = research.matrix(con, "BTCUSDT", as_of=2, direction="LONG", now=2)
    assert result["availability"] in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}
    con.close()
