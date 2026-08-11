# QualityStoreCase

> 26 nodes

## Key Concepts

- **RunRecorder** (62 connections) — `app/engine/runlog.py`
- **runlog.py** (31 connections) — `app/engine/runlog.py`
- **regime.py** (12 connections) — `app/engine/regime.py`
- **volprofile.py** (11 connections) — `app/engine/volprofile.py`
- **walk_states()** (6 connections) — `app/engine/volprofile.py`
- **bin_step()** (5 connections) — `app/engine/volprofile.py`
- **run()** (5 connections) — `app/engine/volprofile.py`
- **basis.py** (4 connections) — `app/engine/basis.py`
- **run()** (3 connections) — `app/engine/basis.py`
- **run()** (3 connections) — `app/engine/regime.py`
- **._fingerprint()** (3 connections) — `app/engine/runlog.py`
- **.__exit__()** (3 connections) — `app/engine/runlog.py`
- **Decimal** (3 connections)
- **classify()** (3 connections) — `app/engine/volprofile.py`
- **_classify()** (2 connections) — `app/engine/regime.py`
- **.__enter__()** (2 connections) — `app/engine/runlog.py`
- **Cross-venue basis — the spread between where you trade and where depth is.  algo** (1 connections) — `app/engine/basis.py`
- **Record the close-to-close basis for one (symbol, tf) series.      Facts key on t** (1 connections) — `app/engine/basis.py`
- **Regime engine — market-state classification from structure facts. algo regime-v** (1 connections) — `app/engine/regime.py`
- **.__init__()** (1 connections) — `app/engine/runlog.py`
- **Run logging — every engine invocation is recorded (file log + engine_runs table)** (1 connections) — `app/engine/runlog.py`
- **Context manager: times an engine run and records it on exit.** (1 connections) — `app/engine/runlog.py`
- **Volume profile — is price sitting where volume lived? algo volprofile-v0.1-draft** (1 connections) — `app/engine/volprofile.py`
- **The series' permanent bin width: VP_BIN_PCT of its first close,     quantized sc** (1 connections) — `app/engine/volprofile.py`
- **Schmitt-triggered node state for one close's bin ratio.** (1 connections) — `app/engine/volprofile.py`
- *... and 1 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (24 shared connections)
- [Indicator Engines](Indicator_Engines.md) (18 shared connections)
- [TestMarketQuality](TestMarketQuality.md) (9 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (7 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (6 shared connections)
- [volume.py](volume.py.md) (6 shared connections)
- [_facts](_facts.md) (4 shared connections)
- [Cooldown Engine](Cooldown_Engine.md) (3 shared connections)
- [cycles.py](cycles.py.md) (3 shared connections)
- [cached_audit](cached_audit.md) (3 shared connections)
- [Bias Ladder Engine](Bias_Ladder_Engine.md) (1 shared connections)
- [execsim.py](execsim.py.md) (1 shared connections)

## Source Files

- `app/engine/basis.py`
- `app/engine/regime.py`
- `app/engine/runlog.py`
- `app/engine/volprofile.py`

## Audit Trail

- EXTRACTED: 158 (94%)
- INFERRED: 10 (6%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*