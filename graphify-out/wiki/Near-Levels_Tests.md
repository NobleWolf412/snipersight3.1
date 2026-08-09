# Near-Levels Tests

> 29 nodes

## Key Concepts

- **Sweep** (11 connections) — `app/tests/test_nearlevels.py`
- **ReachIsTheEnginesOwnBound** (7 connections) — `app/tests/test_nearlevels.py`
- **._candles()** (6 connections) — `app/tests/test_nearlevels.py`
- **._zone()** (6 connections) — `app/tests/test_nearlevels.py`
- **test_nearlevels.py** (4 connections) — `app/tests/test_nearlevels.py`
- **.test_it_writes_nothing()** (4 connections) — `app/tests/test_nearlevels.py`
- **.test_shadow_symbols_are_excluded_and_counted()** (4 connections) — `app/tests/test_nearlevels.py`
- **.test_the_distance_is_the_one_the_chart_will_draw()** (4 connections) — `app/tests/test_nearlevels.py`
- **.test_a_market_that_cannot_be_read_is_named_never_dropped_silently()** (4 connections) — `app/tests/test_nearlevels.py`
- **.test_rows_come_back_nearest_first()** (3 connections) — `app/tests/test_nearlevels.py`
- **.test_the_engines_exact_bound_is_still_in_range()** (2 connections) — `app/tests/test_nearlevels.py`
- **.test_price_inside_the_zone_is_its_own_state_not_merely_closest()** (2 connections) — `app/tests/test_nearlevels.py`
- **.test_a_timeframe_the_engine_never_forms_on_says_so()** (2 connections) — `app/tests/test_nearlevels.py`
- **.test_out_of_range_wins_over_the_timeframe_rule()** (2 connections) — `app/tests/test_nearlevels.py`
- **.test_the_payload_carries_the_bounds_so_the_client_never_guesses()** (2 connections) — `app/tests/test_nearlevels.py`
- **.test_a_hair_past_the_bound_is_out_of_range()** (1 connections) — `app/tests/test_nearlevels.py`
- **.setUp()** (1 connections) — `app/tests/test_nearlevels.py`
- **.tearDown()** (1 connections) — `app/tests/test_nearlevels.py`
- **At a level" — the sweep that says where price is standing, and what the engine** (1 connections) — `app/tests/test_nearlevels.py`
- **`engine_reach` mirrors the gates in `setups.py`'s forming loop.      Read the** (1 connections) — `app/tests/test_nearlevels.py`
- **`setups.py` skips at `dist > PROX_ATR * atr`, so a distance EQUAL to         th** (1 connections) — `app/tests/test_nearlevels.py`
- **At `dist <= 0` setups.py BREAKS out of the forming loop and hands the         z** (1 connections) — `app/tests/test_nearlevels.py`
- **The trap this panel is for. 15m and 1H are outside FORMING_TFS, so a         ro** (1 connections) — `app/tests/test_nearlevels.py`
- **A 1H row 2 ATR out is out of range for the distance reason first.         Repor** (1 connections) — `app/tests/test_nearlevels.py`
- **Read-only (§1). A panel that mutated the store while rendering would         ma** (1 connections) — `app/tests/test_nearlevels.py`
- *... and 4 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)

## Source Files

- `app/tests/test_nearlevels.py`

## Audit Trail

- EXTRACTED: 77 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*