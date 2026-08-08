# Phemex Adapter Tests

> 32 nodes

## Key Concepts

- **test_phemex.py** (7 connections) — `app/tests/test_phemex.py`
- **CandleTest** (7 connections) — `app/tests/test_phemex.py`
- **RankTest** (5 connections) — `app/tests/test_phemex.py`
- **_rows()** (4 connections) — `app/tests/test_phemex.py`
- **._patched()** (4 connections) — `app/tests/test_phemex.py`
- **SafetyTest** (4 connections) — `app/tests/test_phemex.py`
- **ListingGapTest** (4 connections) — `app/tests/test_phemex.py`
- **.test_unlisted_ticker_symbols_are_ignored()** (3 connections) — `app/tests/test_phemex.py`
- **.test_forming_candle_is_never_returned()** (3 connections) — `app/tests/test_phemex.py`
- **ProductsTest** (2 connections) — `app/tests/test_phemex.py`
- **.test_ranked_descending_by_turnover()** (2 connections) — `app/tests/test_phemex.py`
- **.test_malformed_turnover_is_counted_not_crashed()** (2 connections) — `app/tests/test_phemex.py`
- **.test_rows_are_deduped_and_ascending()** (2 connections) — `app/tests/test_phemex.py`
- **.test_field_mapping_matches_the_row_layout()** (2 connections) — `app/tests/test_phemex.py`
- **.test_no_forward_progress_terminates()** (2 connections) — `app/tests/test_phemex.py`
- **.test_serves_4h_natively()** (2 connections) — `app/tests/test_phemex.py`
- **.test_module_holds_no_credentials_and_cannot_trade()** (2 connections) — `app/tests/test_phemex.py`
- **.test_only_usdt_settled_perps_are_listed()** (1 connections) — `app/tests/test_phemex.py`
- **.test_unknown_timeframe_is_refused()** (1 connections) — `app/tests/test_phemex.py`
- **.test_retry_gives_up_rather_than_looping()** (1 connections) — `app/tests/test_phemex.py`
- **.test_client_error_is_not_retried()** (1 connections) — `app/tests/test_phemex.py`
- **.test_empty_leading_windows_are_skipped_not_fatal()** (1 connections) — `app/tests/test_phemex.py`
- **.test_all_empty_still_terminates()** (1 connections) — `app/tests/test_phemex.py`
- **Phemex perp adapter — contract and safety tests. No network.  The endpoint sha** (1 connections) — `app/tests/test_phemex.py`
- **[ts, resolution, lastClose, open, high, low, close, volume]** (1 connections) — `app/tests/test_phemex.py`
- *... and 7 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_phemex.py`

## Audit Trail

- EXTRACTED: 72 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*