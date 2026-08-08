from engine import achievements


def test_progression_rewards_safety_and_evidence_not_profit_or_frequency():
    gate = {"criteria": [
        {"key": "sample", "have": 25, "need": 100, "pass": False},
        {"key": "edge", "pass": False},
    ]}
    status = {"promotion": {"shadow_ready": False, "testnet_ready": False}}
    rows = achievements.calculate(
        live_gate=gate, automation_status=status, journal_count=25,
        quality_status="PASS")
    by_key = {row["key"]: row for row in rows}
    assert by_key["FORWARD_RECORD"]["progress"] == "0.25"
    assert by_key["DATA_DRILL"]["completed"] is True
    text = " ".join(row["label"] + " " + row["description"] for row in rows).lower()
    assert "profit" not in text
    assert "leverage" not in text
    assert "winning streak" not in text


def test_blocked_data_never_awards_integrity_drill():
    rows = achievements.calculate(
        live_gate={"criteria": []}, automation_status={"promotion": {}},
        journal_count=0, quality_status="BLOCKED")
    row = next(item for item in rows if item["key"] == "DATA_DRILL")
    assert row["completed"] is False
    assert row["progress"] == "0"
