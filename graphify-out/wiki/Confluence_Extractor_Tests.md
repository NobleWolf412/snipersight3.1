# Confluence Extractor Tests

> 16 nodes

## Key Concepts

- **v07_payload()** (13 connections) — `app/tests/test_factorstats.py`
- **TestConfluenceV07Extractor** (10 connections) — `app/tests/test_factorstats.py`
- **.test_unknown_htf_regime_is_omitted_not_scored_as_disagreeing()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_range_regime_is_read_as_zero_conviction_not_dropped()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_align_strength_is_signed_toward_the_trade()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_placeholder_score_field_is_not_extracted()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_reads_every_field_the_v07_confluence_block_emits()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_binary_rank_inputs_are_extracted_beside_their_raw_values()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_a_payload_without_a_confluence_block_yields_only_top_level_factors()** (1 connections) — `app/tests/test_factorstats.py`
- **.test_registered_under_a_name_for_the_cli()** (1 connections) — `app/tests/test_factorstats.py`
- **A `setup-v0.7-draft` VALIDATED payload, in the shape `setups.py` writes it:** (1 connections) — `app/tests/test_factorstats.py`
- **The v0.7 extractor is the first thing in this project to read a `confluence`** (1 connections) — `app/tests/test_factorstats.py`
- **`rank` treats a missing HTF regime exactly like a disagreeing one. The         e** (1 connections) — `app/tests/test_factorstats.py`
- **`RANGE` never appears in a setup's OWN regime (no playbook trades it) but** (1 connections) — `app/tests/test_factorstats.py`
- **The graded version of the +10 flag: a hard bear HTF is +2 for a SHORT and** (1 connections) — `app/tests/test_factorstats.py`
- **`setups.py` emits `score: 0` as a reserved slot consumed by nothing. It is** (1 connections) — `app/tests/test_factorstats.py`

## Relationships

- [Rank Decomposition Tests](Rank_Decomposition_Tests.md) (5 shared connections)
- [Factor Stats Determinism Tests](Factor_Stats_Determinism_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_factorstats.py`

## Audit Trail

- EXTRACTED: 47 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*