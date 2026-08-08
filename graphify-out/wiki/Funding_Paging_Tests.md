# Funding Paging Tests

> 7 nodes

## Key Concepts

- **Paging** (7 connections) — `app/tests/test_funding.py`
- **.setUp()** (1 connections) — `app/tests/test_funding.py`
- **.tearDown()** (1 connections) — `app/tests/test_funding.py`
- **.test_it_walks_back_until_the_window_is_covered()** (1 connections) — `app/tests/test_funding.py`
- **.test_it_never_sends_start()** (1 connections) — `app/tests/test_funding.py`
- **.test_it_stops_rather_than_paging_forever()** (1 connections) — `app/tests/test_funding.py`
- **Phemex answers 100 settlements per call whatever `limit` asks, so the     histo** (1 connections) — `app/tests/test_funding.py`

## Relationships

- [Funding Read-Only Tests](Funding_Read-Only_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_funding.py`

## Audit Trail

- EXTRACTED: 13 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*