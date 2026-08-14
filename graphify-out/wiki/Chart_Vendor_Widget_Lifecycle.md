# Chart Vendor Widget Lifecycle

> 13 nodes

## Key Concepts

- **go()** (8 connections) — `app/static/shell.js`
- **wireCardActions()** (8 connections) — `app/static/shell.js`
- **refresh()** (6 connections) — `app/static/shell.js`
- **pollConsole()** (5 connections) — `app/static/shell.js`
- **markDegraded()** (3 connections) — `app/static/shell.js`
- **closePosition()** (3 connections) — `app/static/shell.js`
- **setDev()** (3 connections) — `app/static/shell.js`
- **storageFailed()** (2 connections) — `app/static/shell.js`
- **ageText()** (2 connections) — `app/static/shell.js`
- **explainRefusal()** (2 connections) — `app/static/shell.js`
- **activatable()** (2 connections) — `app/static/shell.js`
- **paint()** (2 connections) — `app/static/shell.js`
- **scanResult()** (2 connections) — `app/static/shell.js`

## Relationships

- [Shell Health & Staleness](Shell_Health_%26_Staleness.md) (13 shared connections)
- [Mission Rail & Radar UI](Mission_Rail_%26_Radar_UI.md) (3 shared connections)
- [Shell Navigation & Near Levels](Shell_Navigation_%26_Near_Levels.md) (2 shared connections)
- [market_context.py](market_context.py.md) (1 shared connections)
- [renderNear](renderNear.md) (1 shared connections)

## Source Files

- `app/static/shell.js`

## Audit Trail

- EXTRACTED: 48 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*