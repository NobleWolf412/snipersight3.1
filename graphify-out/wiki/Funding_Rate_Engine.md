# Funding Rate Engine

> 16 nodes

## Key Concepts

- **funding.py** (10 connections) — `app/engine/funding.py`
- **history()** (7 connections) — `app/engine/funding.py`
- **Decimal** (6 connections)
- **phemex_history()** (6 connections) — `app/engine/funding.py`
- **kraken_history()** (5 connections) — `app/engine/funding.py`
- **report()** (5 connections) — `app/engine/funding.py`
- **charge()** (4 connections) — `app/engine/funding.py`
- **_now()** (3 connections) — `app/engine/funding.py`
- **_get()** (3 connections) — `app/engine/funding.py`
- **What funding ACTUALLY cost, against the constant the simulator charges. READ-ON** (1 connections) — `app/engine/funding.py`
- **Wall clock, in one place so a test can pin it.** (1 connections) — `app/engine/funding.py`
- **(settlement unix seconds, rate) hourly, oldest first.      `relativeFundingRat** (1 connections) — `app/engine/funding.py`
- **(settlement unix seconds, rate) 8-hourly, oldest first.      Keyed on the INDE** (1 connections) — `app/engine/funding.py`
- **Real settlements for one symbol, or [] where the venue charges none.      Spot** (1 connections) — `app/engine/funding.py`
- **What this hold really paid — signed, in price units on entry notional.      SI** (1 connections) — `app/engine/funding.py`
- **Re-price the recorded book on real funding. Writes nothing.      The R denomin** (1 connections) — `app/engine/funding.py`

## Relationships

- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)
- [Venue Policy & Contract](Venue_Policy_%26_Contract.md) (1 shared connections)

## Source Files

- `app/engine/funding.py`

## Audit Trail

- EXTRACTED: 55 (98%)
- INFERRED: 1 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*