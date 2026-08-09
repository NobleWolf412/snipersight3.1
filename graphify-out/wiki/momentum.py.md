# momentum.py

> 6 nodes

## Key Concepts

- **OneFillModel** (4 connections) — `app/tests/test_abtest.py`
- **.test_a_crossed_order_is_priced_on_the_bar_it_crossed_on()** (3 connections) — `app/tests/test_abtest.py`
- **.test_a_missing_atr_on_the_cross_degrades_audibly()** (3 connections) — `app/tests/test_abtest.py`
- **The whole fill model is the engine's, not just the crossing price.** (1 connections) — `app/tests/test_abtest.py`
- **The passive limit rests below every low so it can never fill; the         engin** (1 connections) — `app/tests/test_abtest.py`
- **`cross_fill` returns a `slipped` flag and abtest discarded it         (`entry_p** (1 connections) — `app/tests/test_abtest.py`

## Relationships

- [Simulator Convention Tests](Simulator_Convention_Tests.md) (2 shared connections)
- [Retired Symbol Staleness Tests](Retired_Symbol_Staleness_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_abtest.py`

## Audit Trail

- EXTRACTED: 13 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*