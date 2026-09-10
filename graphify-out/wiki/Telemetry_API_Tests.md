# Telemetry API Tests

> 8 nodes

## Key Concepts

- **Path** (8 connections)
- **TestSetupTelemetryAPI** (4 connections) — `app/tests/test_api_telemetry.py`
- **test_api_telemetry.py** (2 connections) — `app/tests/test_api_telemetry.py`
- **.test_active_baseline_hides_pre_reset_losses_everywhere()** (2 connections) — `app/tests/test_api_telemetry.py`
- **.test_lifecycle_funnel_and_failure_attribution()** (2 connections) — `app/tests/test_api_telemetry.py`
- **.setUp()** (2 connections) — `app/tests/test_edgestats.py`
- **.setUp()** (2 connections) — `app/tests/test_entrystats.py`
- **.test_loss_autopsy_uses_only_approved_trades_and_names_weak_slices()** (1 connections) — `app/tests/test_api_telemetry.py`

## Relationships

- [Entry Stats Engine](Entry_Stats_Engine.md) (2 shared connections)
- [Edge Stats Determinism Tests](Edge_Stats_Determinism_Tests.md) (2 shared connections)
- [Entry Stats Tests](Entry_Stats_Tests.md) (2 shared connections)
- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/tests/test_api_telemetry.py`
- `app/tests/test_edgestats.py`
- `app/tests/test_entrystats.py`

## Audit Trail

- EXTRACTED: 13 (57%)
- INFERRED: 10 (43%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*