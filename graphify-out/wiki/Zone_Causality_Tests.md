# Zone Causality Tests

> 11 nodes

## Key Concepts

- **RecordedZonesAreCausal** (5 connections) — `app/tests/test_zone_causality.py`
- **test_zone_causality.py** (4 connections) — `app/tests/test_zone_causality.py`
- **ZoneClusterIsCausal** (3 connections) — `app/tests/test_zone_causality.py`
- **.test_cluster_ignores_swings_confirmed_after_the_zone()** (2 connections) — `app/tests/test_zone_causality.py`
- **.test_no_zone_counts_a_swing_it_could_not_see()** (2 connections) — `app/tests/test_zone_causality.py`
- **.test_source_applies_the_confirmed_at_filter()** (1 connections) — `app/tests/test_zone_causality.py`
- **.setUpClass()** (1 connections) — `app/tests/test_zone_causality.py`
- **.tearDownClass()** (1 connections) — `app/tests/test_zone_causality.py`
- **A fact stamped `confirmed_at = T` may not depend on anything after T.  `zones.** (1 connections) — `app/tests/test_zone_causality.py`
- **Constructed: three lows in one band, the third confirmed LATER.          The b** (1 connections) — `app/tests/test_zone_causality.py`
- **Store-level: recompute each zone's cluster causally and require a match.** (1 connections) — `app/tests/test_zone_causality.py`

## Relationships

- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (2 shared connections)

## Source Files

- `app/tests/test_zone_causality.py`

## Audit Trail

- EXTRACTED: 21 (95%)
- INFERRED: 1 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*