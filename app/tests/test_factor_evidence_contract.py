from engine import factorgrade, factorstats


def book(n=360):
    rows = []
    for i in range(n):
        fired = 1.0 if i % 2 else 0.0
        # Chronologically stable positive uplift: high factor earns +0.4R,
        # baseline alternates +0.4/-0.2 and is therefore lower.
        result = 0.4 if fired else -0.2
        rows.append({
            "fact_id": i, "setup_id": f"s-{i}", "symbol": "BTCUSDT",
            "tf": "15m", "confirmed_at": i, "r": result,
            "setup_version": "setup-test", "exec_version": "exec-test",
            "payload": {"symbol": "BTCUSDT", "tf": "15m",
                        "strategy": "PULLBACK", "direction": "LONG",
                        "regime": "BULL_TREND", "test_factor": fired},
        })
    return rows


def extract(payload):
    return {"test_factor": payload["test_factor"]}


def test_evidence_is_chronological_cohort_scoped_and_adjusted():
    report = factorstats.evidence_report(
        book(), factors=extract, dimensions=("strategy", "horizon", "direction"))
    assert report["point_in_time"] is True
    row = report["rows"][0]
    assert row["splits"] == {"train": 216, "validation": 72, "forward": 72}
    assert row["cohort"]["strategy"] == "PULLBACK"
    assert row["q_value"] is not None
    assert row["stable"] is True


def test_small_forward_sample_is_ungraded_not_a_confident_zero():
    report = factorstats.evidence_report(
        book(60), factors=extract, dimensions=("strategy",))
    row = report["rows"][0]
    assert row["status"] == "INSUFFICIENT_EVIDENCE"
    grade = factorgrade.calibrated_grade(report)
    assert grade["grade"] == "UNGRADED"
    assert grade["score"] is None
    assert grade["sizing_allowed"] is False


def test_even_a_letter_grade_cannot_change_position_size():
    report = factorstats.evidence_report(
        book(600), factors=extract, dimensions=("strategy",))
    grade = factorgrade.calibrated_grade(report)
    assert grade["grade"] in {"A", "B", "C", "D", "UNGRADED"}
    assert grade["sizing_allowed"] is False
