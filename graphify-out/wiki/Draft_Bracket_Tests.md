# Draft Bracket Tests

> 26 nodes

## Key Concepts

- **zone()** (15 connections) — `app/tests/test_draft.py`
- **DraftBracket** (15 connections) — `app/tests/test_draft.py`
- **pool()** (5 connections) — `app/tests/test_draft.py`
- **test_draft.py** (4 connections) — `app/tests/test_draft.py`
- **.test_every_draft_says_what_it_stands_on()** (4 connections) — `app/tests/test_draft.py`
- **.test_the_draft_is_a_valid_ticket()** (4 connections) — `app/tests/test_draft.py`
- **.test_anchors_the_entry_to_the_zone_edge_not_to_price()** (3 connections) — `app/tests/test_draft.py`
- **.test_target_is_the_nearest_unbroken_pool_it_would_run_into()** (3 connections) — `app/tests/test_draft.py`
- **.test_a_broken_pool_is_never_a_target()** (3 connections) — `app/tests/test_draft.py`
- **.test_price_standing_inside_a_zone_is_the_nearest_thing_there_is()** (3 connections) — `app/tests/test_draft.py`
- **.test_price_below_a_demand_zone_is_not_an_anchor()** (3 connections) — `app/tests/test_draft.py`
- **.test_returns_None_when_nothing_is_near_price()** (3 connections) — `app/tests/test_draft.py`
- **.test_a_spot_venue_is_never_drafted_a_short()** (3 connections) — `app/tests/test_draft.py`
- **.test_stop_sits_beyond_the_far_edge_by_the_declared_buffer()** (2 connections) — `app/tests/test_draft.py`
- **.test_broken_zones_are_not_anchors()** (2 connections) — `app/tests/test_draft.py`
- **.test_the_nearest_zone_wins_when_several_are_live()** (2 connections) — `app/tests/test_draft.py`
- **.test_supply_above_price_drafts_a_short()** (2 connections) — `app/tests/test_draft.py`
- **.test_missing_atr_or_price_yields_nothing_rather_than_a_guess()** (2 connections) — `app/tests/test_draft.py`
- **Draft bracket tests — the properties that keep it honest.  The draft exists beca** (1 connections) — `app/tests/test_draft.py`
- **The whole point. The ruler put entry AT the last close; this puts it         at** (1 connections) — `app/tests/test_draft.py`
- **Distance zero, and the case the draft most needs to handle: price in         a d** (1 connections) — `app/tests/test_draft.py`
- **It did not hold. Entering at its top would be chasing a broken level         rat** (1 connections) — `app/tests/test_draft.py`
- **Price is not near anything this system recognises' is a real answer         and** (1 connections) — `app/tests/test_draft.py`
- **`venues.allow_shorts` is a venue capability, not a preference. A         draft t** (1 connections) — `app/tests/test_draft.py`
- **`basis` is the thing the ruler could never provide — it had no         reasoning** (1 connections) — `app/tests/test_draft.py`
- *... and 1 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_draft.py`

## Audit Trail

- EXTRACTED: 86 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*