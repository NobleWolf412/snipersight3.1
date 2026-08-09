# Watchdog Kill Attribution Tests

> 8 nodes

## Key Concepts

- **t()** (28 connections) — `app/tests/test_ticket_math.js`
- **engaged()** (4 connections) — `app/static/shell.js`
- **deck()** (4 connections) — `app/static/shell.js`
- **.M_()** (3 connections) — `app/static/lightweight-charts.js`
- **lifecycleOf()** (3 connections) — `app/static/shell.js`
- **storyOf()** (3 connections) — `app/static/shell.js`
- **buildSettings()** (3 connections) — `app/static/shell.js`
- **reachableTitles()** (2 connections) — `app/static/shell.js`

## Relationships

- [Shell Health & Staleness](Shell_Health_%26_Staleness.md) (7 shared connections)
- [Chart Vendor Core](Chart_Vendor_Core.md) (3 shared connections)
- [Chart Vendor Internals](Chart_Vendor_Internals.md) (2 shared connections)
- [Chart Vendor Panes](Chart_Vendor_Panes.md) (2 shared connections)
- [Chart Vendor Hit Testing](Chart_Vendor_Hit_Testing.md) (2 shared connections)
- [report](report.md) (1 shared connections)
- [Chart UI Layer](Chart_UI_Layer.md) (1 shared connections)
- [automation_drill_start](automation_drill_start.md) (1 shared connections)
- [A/B Position Simulation](A-B_Position_Simulation.md) (1 shared connections)
- [Manual Trading Engine](Manual_Trading_Engine.md) (1 shared connections)
- [Chart Vendor Rendering](Chart_Vendor_Rendering.md) (1 shared connections)
- [Setup Deck UI](Setup_Deck_UI.md) (1 shared connections)

## Source Files

- `app/static/lightweight-charts.js`
- `app/static/shell.js`
- `app/tests/test_ticket_math.js`

## Audit Trail

- EXTRACTED: 17 (34%)
- INFERRED: 33 (66%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*