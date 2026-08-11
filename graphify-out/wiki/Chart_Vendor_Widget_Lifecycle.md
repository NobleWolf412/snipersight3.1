# Chart Vendor Widget Lifecycle

> 16 nodes

## Key Concepts

- **go()** (8 connections) — `app/static/shell.js`
- **renderLedger()** (6 connections) — `app/static/shell.js`
- **refresh()** (6 connections) — `app/static/shell.js`
- **pollConsole()** (5 connections) — `app/static/shell.js`
- **markDegraded()** (3 connections) — `app/static/shell.js`
- **closePosition()** (3 connections) — `app/static/shell.js`
- **paint()** (3 connections) — `app/static/shell.js`
- **setDev()** (3 connections) — `app/static/shell.js`
- **loadLedger()** (3 connections) — `app/static/shell.js`
- **ledgerRow()** (3 connections) — `app/static/shell.js`
- **renderLedgerMine()** (3 connections) — `app/static/shell.js`
- **renderLedgerExits()** (3 connections) — `app/static/shell.js`
- **storageFailed()** (2 connections) — `app/static/shell.js`
- **ageText()** (2 connections) — `app/static/shell.js`
- **scanResult()** (2 connections) — `app/static/shell.js`
- **bookCard()** (2 connections) — `app/static/shell.js`

## Relationships

- [Shell Health & Staleness](Shell_Health_%26_Staleness.md) (18 shared connections)
- [Mission Rail & Radar UI](Mission_Rail_%26_Radar_UI.md) (3 shared connections)
- [Chart Vendor Core](Chart_Vendor_Core.md) (1 shared connections)
- [Engine Fault Row Tests](Engine_Fault_Row_Tests.md) (1 shared connections)

## Source Files

- `app/static/shell.js`

## Audit Trail

- EXTRACTED: 56 (98%)
- INFERRED: 1 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*