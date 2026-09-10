# Engine Fault Row Tests

> 2 nodes

## Key Concepts

- **.test_the_retired_tags_are_read_and_never_written()** (2 connections) — `app/tests/test_manual.py`
- **The read set only ever grows. Dropping a tag strands every order         still** (1 connections) — `app/tests/test_manual.py`

## Relationships

- [Manual Book Tests](Manual_Book_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 3 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*