# WAL Hygiene Tests

> 15 nodes

## Key Concepts

- **WalIsBounded** (8 connections) — `app/tests/test_wal_hygiene.py`
- **test_wal_hygiene.py** (3 connections) — `app/tests/test_wal_hygiene.py`
- **ScannerCheckpointsBetweenCycles** (3 connections) — `app/tests/test_wal_hygiene.py`
- **.test_an_open_reader_blocks_the_reset()** (2 connections) — `app/tests/test_wal_hygiene.py`
- **.test_checkpoint_never_raises()** (2 connections) — `app/tests/test_wal_hygiene.py`
- **.setUp()** (1 connections) — `app/tests/test_wal_hygiene.py`
- **.tearDown()** (1 connections) — `app/tests/test_wal_hygiene.py`
- **.test_wal_mode_is_on()** (1 connections) — `app/tests/test_wal_hygiene.py`
- **.test_journal_size_limit_is_set()** (1 connections) — `app/tests/test_wal_hygiene.py`
- **.test_checkpoint_reclaims_the_log()** (1 connections) — `app/tests/test_wal_hygiene.py`
- **.test_live_loop_checkpoints_outside_the_work()** (1 connections) — `app/tests/test_wal_hygiene.py`
- **The write-ahead log must not be able to eat the machine again.  On 2026-07-30 th** (1 connections) — `app/tests/test_wal_hygiene.py`
- **The mechanism itself. If this ever stops being true, the whole         between-c** (1 connections) — `app/tests/test_wal_hygiene.py`
- **Housekeeping must never be able to kill a scan cycle.** (1 connections) — `app/tests/test_wal_hygiene.py`
- **Placement matters as much as existence: the loop holds a read snapshot     for m** (1 connections) — `app/tests/test_wal_hygiene.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_wal_hygiene.py`

## Audit Trail

- EXTRACTED: 28 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*