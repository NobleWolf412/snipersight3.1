"""The plain-language layer over the quality verdict is complete and honest.

Two properties, both invisible to the runtime: every code the audit can emit
has a real translation (the fallback exists for codes newer than the build,
not as a place to hide), and the serve-time annotation never touches the
recorded verdict's own findings beyond adding to them.
"""
import server
from engine import quality


def test_every_audit_code_has_a_real_plain_entry():
    for code in quality.CODE_RUNG:
        base = code.removeprefix("REFERENCE_")
        assert base in server.QUALITY_PLAIN, (
            f"{code} would fall back to the 'no plain-language entry yet' "
            "sentence — add its translation to QUALITY_PLAIN in the same "
            "change that adds the code")


def test_plain_entries_carry_a_meaning_and_an_action():
    for code, (what, action) in server.QUALITY_PLAIN.items():
        assert what and action, code
        assert code.replace("_", " ").lower() not in what.lower(), (
            f"{code}: restating the code is not a translation")


def test_reference_findings_say_they_cannot_block_trading():
    plain = server._quality_plain("REFERENCE_STALE_SERIES")
    assert "cannot block trading" in plain["what"]
    assert "cannot stop a trade" in plain["action"]


def test_annotation_adds_but_never_rewrites():
    report = {"status": "BLOCKED",
              "blockers": [{"code": "SEQUENCE_GAPS", "symbol": "BTCUSDT",
                            "tf": "15m", "details": "3 unexplained"}],
              "warnings": [], "notes": []}
    out = server._annotate_quality(report)
    finding = out["blockers"][0]
    assert finding["plain"]["what"]
    assert finding["code"] == "SEQUENCE_GAPS"
    assert finding["details"] == "3 unexplained"
    assert "stopped" in out["headline"]
    assert "BTCUSDT" in out["headline"]


def test_cause_groups_by_dominant_code_and_counts_the_rest():
    findings = [
        {"code": "SEQUENCE_GAPS", "symbol": "AUSDT"},
        {"code": "SEQUENCE_GAPS", "symbol": "BUSDT"},
        {"code": "SEQUENCE_GAPS", "symbol": "CUSDT"},
        {"code": "SEQUENCE_GAPS", "symbol": "DUSDT"},
        {"code": "OHLC_INVARIANT_FAILURE", "symbol": "EUSDT"},
    ]
    cause = server._quality_cause(findings)
    assert cause["code"] == "SEQUENCE_GAPS"
    # Three named, the remainder counted — a list nobody reads is not an answer.
    # Only the dominant group's markets are named: blaming a malformed-bar
    # market for "holes" would be a wrong specific, worse than a vague card.
    assert "and 1 more" in cause["sentence"]
    assert "EUSDT" not in cause["sentence"]
    assert cause["total_markets"] == 5
    assert "1 other issue type is also open" in cause["sentence"]


def test_pass_headline_calls_notes_records_not_work():
    report = {"status": "PASS", "blockers": [], "warnings": [],
              "notes": [{"code": "KNOWN_VENUE_GAPS", "symbol": "XUSDT"}]}
    headline = server._quality_headline(report)
    assert "passed" in headline
    assert "not work" in headline
