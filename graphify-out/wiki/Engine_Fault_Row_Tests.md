# Engine Fault Row Tests

> 14 nodes

## Key Concepts

- **ringSvg()** (9 connections) — `app/static/shell.js`
- **.Vt()** (8 connections) — `app/static/lightweight-charts.js`
- **renderNear()** (8 connections) — `app/static/shell.js`
- **b()** (7 connections) — `app/static/lightweight-charts.js`
- **.m()** (6 connections) — `app/static/lightweight-charts.js`
- **ladderHtml()** (6 connections) — `app/static/shell.js`
- **mineCardInner()** (6 connections) — `app/static/shell.js`
- **missionCardInner()** (4 connections) — `app/static/shell.js`
- **ladderRing()** (4 connections) — `app/static/shell.js`
- **S()** (3 connections) — `app/static/lightweight-charts.js`
- **weatherIndex()** (2 connections) — `app/static/shell.js`
- **reachPlay()** (2 connections) — `app/static/shell.js`
- **loadNearLevels()** (2 connections) — `app/static/shell.js`
- **windowLeft()** (2 connections) — `app/static/shell.js`

## Relationships

- [Shell Health & Staleness](Shell_Health_%26_Staleness.md) (13 shared connections)
- [Mission Rail & Radar UI](Mission_Rail_%26_Radar_UI.md) (3 shared connections)
- [Chart Vendor API](Chart_Vendor_API.md) (2 shared connections)
- [Shell Navigation & Near Levels](Shell_Navigation_%26_Near_Levels.md) (2 shared connections)
- [Chart Vendor Hit Testing](Chart_Vendor_Hit_Testing.md) (2 shared connections)
- [Chart Vendor Core](Chart_Vendor_Core.md) (2 shared connections)
- [Chart Vendor Panes](Chart_Vendor_Panes.md) (2 shared connections)
- [makeRail](makeRail.md) (2 shared connections)
- [status](status.md) (1 shared connections)
- [Chart Vendor Internals](Chart_Vendor_Internals.md) (1 shared connections)
- [Fact Store Conventions](Fact_Store_Conventions.md) (1 shared connections)
- [Chart Vendor Coordinates](Chart_Vendor_Coordinates.md) (1 shared connections)

## Source Files

- `app/static/lightweight-charts.js`
- `app/static/shell.js`

## Audit Trail

- EXTRACTED: 61 (88%)
- INFERRED: 8 (12%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*