# Version Cascade Lockfile

> 16 nodes

## Key Concepts

- **VersionLockfile** (8 connections) — `app/tests/test_version_cascade.py`
- **test_version_cascade.py** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_pipeline_versions_are_what_we_think_they_are()** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_downstream_engines_actually_import_what_they_claim_to_consume()** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_function_level_dependents_import_what_the_map_claims()** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_a_retired_manual_version_is_still_read_and_still_isolated()** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_no_two_engines_share_a_version_string()** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_every_version_is_namespaced_to_its_engine()** (2 connections) — `app/tests/test_version_cascade.py`
- **.test_every_consumer_relationship_names_a_real_engine()** (1 connections) — `app/tests/test_version_cascade.py`
- **Version lockfile — the guard against a defect this project has committed twice.** (1 connections) — `app/tests/test_version_cascade.py`
- **Fails on ANY version move. That failure is the feature — it is the         mome** (1 connections) — `app/tests/test_version_cascade.py`
- **The consumer map must describe the code, not an intention. If an         engine** (1 connections) — `app/tests/test_version_cascade.py`
- **`ma` is consumed by importing its primitives, not its version. The         gene** (1 connections) — `app/tests/test_version_cascade.py`
- **The migration, held in place.          `manual` is the one engine whose old fa** (1 connections) — `app/tests/test_version_cascade.py`
- **Two engines under one label is the collision itself, in its purest         form** (1 connections) — `app/tests/test_version_cascade.py`
- **`exec-v0.9-draft` must not be readable as a swing version. The prefix         i** (1 connections) — `app/tests/test_version_cascade.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_version_cascade.py`

## Audit Trail

- EXTRACTED: 30 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*