# Swings, Zones & Draft Bracket

> 19 nodes

## Key Concepts

- **stockstore.py** (6 connections) — `app/engine/stockstore.py`
- **Connection** (4 connections)
- **_require_scope()** (4 connections) — `app/engine/stockstore.py`
- **StockTrainingWorkflowTest** (4 connections) — `app/tests/test_stock_training.py`
- **connect()** (3 connections) — `app/engine/stockstore.py`
- **insert_fact()** (3 connections) — `app/engine/stockstore.py`
- **insert_candle()** (3 connections) — `app/engine/stockstore.py`
- **insert_paper_event()** (3 connections) — `app/engine/stockstore.py`
- **test_stock_training.py** (3 connections) — `app/tests/test_stock_training.py`
- **StockCalendarTest** (3 connections) — `app/tests/test_stock_training.py`
- **Path** (2 connections)
- **StockStoreIsolationTest** (2 connections) — `app/tests/test_stock_training.py`
- **.test_store_is_append_only_and_rejects_unlabelled_scope()** (2 connections) — `app/tests/test_stock_training.py`
- **Isolated append-only US-equity research store.  This schema is deliberately inco** (1 connections) — `app/engine/stockstore.py`
- **.test_explicit_early_close_is_not_assumed_to_be_a_normal_session()** (1 connections) — `app/tests/test_stock_training.py`
- **.test_closed_session_is_not_tradable()** (1 connections) — `app/tests/test_stock_training.py`
- **.test_report_is_loudly_synthetic_and_never_gradeable()** (1 connections) — `app/tests/test_stock_training.py`
- **.test_scanner_explains_acceptance_and_stock_native_rejections()** (1 connections) — `app/tests/test_stock_training.py`
- **.test_simulator_uses_server_owned_decimal_strings()** (1 connections) — `app/tests/test_stock_training.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/engine/stockstore.py`
- `app/tests/test_stock_training.py`

## Audit Trail

- EXTRACTED: 46 (96%)
- INFERRED: 2 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*