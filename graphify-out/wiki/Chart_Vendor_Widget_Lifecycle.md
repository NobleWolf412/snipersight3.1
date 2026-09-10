# Chart Vendor Widget Lifecycle

> 11 nodes

## Key Concepts

- **wireCardActions()** (8 connections) — `app/static/shell.js`
- **go()** (7 connections) — `app/static/shell.js`
- **refresh()** (6 connections) — `app/static/shell.js`
- **pollScanState()** (4 connections) — `app/static/shell.js`
- **markDegraded()** (3 connections) — `app/static/shell.js`
- **closePosition()** (3 connections) — `app/static/shell.js`
- **loadLedger()** (3 connections) — `app/static/shell.js`
- **ageText()** (2 connections) — `app/static/shell.js`
- **explainRefusal()** (2 connections) — `app/static/shell.js`
- **activatable()** (2 connections) — `app/static/shell.js`
- **scanResult()** (2 connections) — `app/static/shell.js`

## Relationships

- [Shell Health & Staleness](Shell_Health_%26_Staleness.md) (11 shared connections)
- [BTC Alignment Engine](BTC_Alignment_Engine.md) (3 shared connections)
- [Shell Navigation & Near Levels](Shell_Navigation_%26_Near_Levels.md) (2 shared connections)
- [NextWakeMath](NextWakeMath.md) (1 shared connections)
- [renderLedger](renderLedger.md) (1 shared connections)

## Source Files

- `app/static/shell.js`

## Audit Trail

- EXTRACTED: 42 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*