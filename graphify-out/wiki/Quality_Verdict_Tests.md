# Quality Verdict Tests

> 24 nodes

## Key Concepts

- **OneVerdictCase** (16 connections) — `app/tests/test_quality_one_verdict.py`
- **._record()** (7 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_reports_its_own_age()** (3 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_a_recorded_block_is_still_published()** (3 connections) — `app/tests/test_quality_one_verdict.py`
- **test_quality_one_verdict.py** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_the_full_report_is_persisted_not_just_its_counts()** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_serves_the_recorded_verdict_verbatim()** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_the_newest_recorded_verdict_wins()** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_rows_without_a_report_are_skipped()** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_the_endpoint_serves_the_scanner_not_its_own_audit()** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_the_endpoint_falls_back_only_when_nothing_is_recorded()** (2 connections) — `app/tests/test_quality_one_verdict.py`
- **.setUp()** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **.tearDown()** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_migration_is_recorded()** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_returns_none_before_the_scanner_has_recorded_one()** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_unreadable_report_json_is_not_a_verdict()** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **.test_pending_when_there_is_no_verdict_at_all()** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **One verdict, and it is the one the engine acted on.  `cached_audit` holds its re** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **Write a quality_runs row the way audit(persist=True) does.** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **`summary` held four numbers, so any surface wanting the issue list         had t** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **A scanner that has stopped must be visible as staleness, not hidden         behi** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **Rows written before migration 7 are valid summaries but cannot         answer fo** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **A fresh store still shows something, and says it is provisional.** (1 connections) — `app/tests/test_quality_one_verdict.py`
- **The fix must not swallow a real BLOCKED — only ones the engine         never act** (1 connections) — `app/tests/test_quality_one_verdict.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_quality_one_verdict.py`

## Audit Trail

- EXTRACTED: 56 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*