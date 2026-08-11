# Chart Vendor Widget Lifecycle

> 9 nodes

## Key Concepts

- **test_ssdata.js** (7 connections) — `app/tests/test_ssdata.js`
- **ms()** (5 connections) — `app/static/lightweight-charts.js`
- **sleep()** (3 connections) — `app/tests/test_ssdata.js`
- **load()** (3 connections) — `app/tests/test_ssdata.js`
- **fs** (1 connections) — `app/tests/test_ssdata.js`
- **path** (1 connections) — `app/tests/test_ssdata.js`
- **assert** (1 connections) — `app/tests/test_ssdata.js`
- **SRC** (1 connections) — `app/tests/test_ssdata.js`
- **ok()** (1 connections) — `app/tests/test_ssdata.js`

## Relationships

- [Chart Vendor API](Chart_Vendor_API.md) (1 shared connections)
- [Chart Vendor Layout](Chart_Vendor_Layout.md) (1 shared connections)
- [Chart Vendor Internals](Chart_Vendor_Internals.md) (1 shared connections)
- [Chart Vendor Number Formatting](Chart_Vendor_Number_Formatting.md) (1 shared connections)
- [Simulator Convention Tests](Simulator_Convention_Tests.md) (1 shared connections)

## Source Files

- `app/static/lightweight-charts.js`
- `app/tests/test_ssdata.js`

## Audit Trail

- EXTRACTED: 20 (87%)
- INFERRED: 3 (13%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*