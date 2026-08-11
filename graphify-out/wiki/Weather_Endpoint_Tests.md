# Weather Endpoint Tests

> 27 nodes

## Key Concepts

- **.one()** (15 connections) — `app/tests/test_weather.py`
- **TempStore** (12 connections) — `app/tests/test_weather.py`
- **.reset()** (11 connections) — `app/tests/test_weather.py`
- **TestWhatTheStripSays** (11 connections) — `app/tests/test_weather.py`
- **test_weather.py** (9 connections) — `app/tests/test_weather.py`
- **TestEligibilityIsDerivedNotDuplicated** (8 connections) — `app/tests/test_weather.py`
- **play_for()** (7 connections) — `app/tests/test_weather.py`
- **.test_live_flag_matches_playbook_for_every_regime()** (5 connections) — `app/tests/test_weather.py`
- **.test_conditional_regimes_say_what_they_need_and_are_not_called_tradeable()** (5 connections) — `app/tests/test_weather.py`
- **.test_direction_words_follow_the_playbook_direction()** (5 connections) — `app/tests/test_weather.py`
- **.test_reported_plays_are_exactly_what_the_engine_returns()** (4 connections) — `app/tests/test_weather.py`
- **.test_regimes_with_no_play_at_all_say_no_playbook_covers_them()** (4 connections) — `app/tests/test_weather.py`
- **.test_operator_switching_a_strategy_off_changes_the_verdict()** (3 connections) — `app/tests/test_weather.py`
- **.test_every_regime_has_a_display_label_and_a_sentence()** (3 connections) — `app/tests/test_weather.py`
- **.tearDown()** (2 connections) — `app/tests/test_weather.py`
- **.test_agreeing_timeframes_are_marked_aligned()** (2 connections) — `app/tests/test_weather.py`
- **.test_disagreeing_timeframes_say_so()** (2 connections) — `app/tests/test_weather.py`
- **.test_one_live_timeframe_names_which_one()** (2 connections) — `app/tests/test_weather.py`
- **.setUp()** (1 connections) — `app/tests/test_weather.py`
- **Market Weather — the strip that tells the operator why the screen is empty.  T** (1 connections) — `app/tests/test_weather.py`
- **Call the engine exactly as the server does, signature and all.      `swept` no** (1 connections) — `app/tests/test_weather.py`
- **Fresh store between sub-cases, without leaking the previous temp dir.** (1 connections) — `app/tests/test_weather.py`
- **A one-symbol universe with the given 1D / 4H regimes.** (1 connections) — `app/tests/test_weather.py`
- **`live` must mean exactly: playbook() returns a play with NO sweep.          Th** (1 connections) — `app/tests/test_weather.py`
- **A regime that CAN be traded but needs supporting evidence must not be         r** (1 connections) — `app/tests/test_weather.py`
- *... and 2 more nodes in this community*

## Relationships

- [Weather Row Accounting Tests](Weather_Row_Accounting_Tests.md) (9 shared connections)
- [Universe Coverage Tests](Universe_Coverage_Tests.md) (4 shared connections)
- [Regime Wording Tests](Regime_Wording_Tests.md) (3 shared connections)
- [Weather UI Restraint Tests](Weather_UI_Restraint_Tests.md) (2 shared connections)
- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/tests/test_weather.py`

## Audit Trail

- EXTRACTED: 119 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*