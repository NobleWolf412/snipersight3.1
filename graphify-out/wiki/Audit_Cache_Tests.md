# Audit Cache Tests

> 18 nodes

## Key Concepts

- **AuditCacheIsolation** (8 connections) — `app/tests/test_audit_cache.py`
- **RiskGateConsequence** (5 connections) — `app/tests/test_audit_cache.py`
- **test_audit_cache.py** (3 connections) — `app/tests/test_audit_cache.py`
- **.test_a_verdict_does_not_leak_between_stores()** (2 connections) — `app/tests/test_audit_cache.py`
- **.test_non_default_store_never_spawns_a_background_audit()** (2 connections) — `app/tests/test_audit_cache.py`
- **.test_pending_is_none_not_a_confident_verdict()** (2 connections) — `app/tests/test_audit_cache.py`
- **.setUp()** (1 connections) — `app/tests/test_audit_cache.py`
- **.tearDown()** (1 connections) — `app/tests/test_audit_cache.py`
- **.test_two_stores_get_two_cache_slots()** (1 connections) — `app/tests/test_audit_cache.py`
- **.test_force_audits_the_store_it_was_given()** (1 connections) — `app/tests/test_audit_cache.py`
- **.setUp()** (1 connections) — `app/tests/test_audit_cache.py`
- **.tearDown()** (1 connections) — `app/tests/test_audit_cache.py`
- **.test_foreign_blocked_verdict_does_not_block_this_store()** (1 connections) — `app/tests/test_audit_cache.py`
- **The audit cache must not answer questions about one store using another's verdic** (1 connections) — `app/tests/test_audit_cache.py`
- **The exact failure: poison one store's slot, read the other.** (1 connections) — `app/tests/test_audit_cache.py`
- **A daemon thread holding a temporary store open outlives its owner —         on W** (1 connections) — `app/tests/test_audit_cache.py`
- **Loud-fallback rule: 'we have not audited yet' must never render as         'audi** (1 connections) — `app/tests/test_audit_cache.py`
- **The behaviour the leak actually broke, pinned directly.** (1 connections) — `app/tests/test_audit_cache.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_audit_cache.py`

## Audit Trail

- EXTRACTED: 34 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*