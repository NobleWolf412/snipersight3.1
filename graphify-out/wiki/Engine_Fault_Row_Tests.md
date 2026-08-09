# Engine Fault Row Tests

> 7 nodes

## Key Concepts

- **renderMissions()** (8 connections) — `app/static/shell.js`
- **ladderHtml()** (6 connections) — `app/static/shell.js`
- **mineCardInner()** (6 connections) — `app/static/shell.js`
- **missionCardInner()** (4 connections) — `app/static/shell.js`
- **ladderRing()** (4 connections) — `app/static/shell.js`
- **renderPositions()** (3 connections) — `app/static/shell.js`
- **windowLeft()** (2 connections) — `app/static/shell.js`

## Relationships

- [Shell Health & Staleness](Shell_Health_%26_Staleness.md) (10 shared connections)
- [Mission Rail & Radar UI](Mission_Rail_%26_Radar_UI.md) (2 shared connections)
- [Chart Bootstrap Glue](Chart_Bootstrap_Glue.md) (2 shared connections)
- [Chart UI Layer](Chart_UI_Layer.md) (1 shared connections)
- [Shell Navigation & Near Levels](Shell_Navigation_%26_Near_Levels.md) (1 shared connections)
- [Watchdog Kill Attribution Tests](Watchdog_Kill_Attribution_Tests.md) (1 shared connections)
- [automation_drill_start](automation_drill_start.md) (1 shared connections)
- [Chart Vendor Panes](Chart_Vendor_Panes.md) (1 shared connections)

## Source Files

- `app/static/shell.js`

## Audit Trail

- EXTRACTED: 29 (88%)
- INFERRED: 4 (12%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*