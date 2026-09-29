# SniperSight 3.1

A deterministic market-structure platform for Coinbase spot, Phemex perpetuals
and Kraken perpetuals. Paper execution and guarded private Phemex integration
are implemented. **Mainnet routing is build-locked** in
`app/engine/automation.py`; source presence is not account activation.

Start with [AGENTS.md](AGENTS.md) and the
[authoritative architecture](docs/PRODUCTION-ARCHITECTURE.md). The
[cleanup audit](docs/REPOSITORY-AUDIT-2026-09-28.md) records classification,
removal evidence, verification and retained compatibility paths.

## Current system

- `app/live.py` runs the scanner under `app/watchdog.py` supervision.
- `app/engine/pipeline.py` owns the shared per-symbol engine roster and loop.
- `app/engine/setups.py` owns pullback/reversal evaluation, confirmation,
  setup generation and rejection; `registry.py` owns catalogue metadata.
- Research replay, actual bot paper orders and manual trades have distinct
  state. `riskpaper.py` owns actual paper-book risk; `risk.py` supplies shared
  sizing/admission math and the separate replay risk pass.
- `execution.py`, `positions.py`, `broker_factory.py` and `phemex_private.py`
  implement guarded account/private execution. Mainnet remains build-locked.
- `/` serves the static JavaScript cockpit, using `ui_api.py` read models and
  existing `server.py` action APIs. `/classic` retains the earlier shell as a
  supported UI rollback. There is no React runtime or frontend build step.
- Existing research collectors, forward studies, replay and grading tools
  remain in place. Collection does not promote a strategy into production.
- The scanner queues alerts; the watchdog delivers configured local toast,
  ntfy or generic JSON webhook notifications. Destinations are off until
  configured; direct Telegram Bot API support is not implemented here.

Facts are append-only, versioned and causal; prices use Decimal. Closed candles
and confirmation time determine what a decision could know. See
[sources/ss3_v0.1.txt](sources/ss3_v0.1.txt) for the product constitution and
[CLAUDE.md](CLAUDE.md) for durable conventions and operational traps.

## Run

From the supported Windows workspace:

```text
cd app
python -m pip install fastapi uvicorn feedparser tzdata
python backfill.py
start.bat
```

Backfill seeds history; the scanner onboards further eligible markets. Open
http://localhost:8422. For an isolated API check, run from `app/`:
`python -m uvicorn server:app --port 8422`. Do not point verification at an
operator's store or call live write/restart endpoints as tests.

`python reset_baseline.py` is an explicit operator action to begin a new
forward paper record without deleting candle history. It is not a setup or
verification step. Historical versions and unresolved orders may still have
legitimate consumers; do not delete them based on age.

## Verify

On Windows use `scripts/preflight.ps1` and `scripts/check.ps1`. Core checks in
an isolated Linux/macOS checkout, from `app/`:

```sh
python -m pip install fastapi uvicorn pytest httpx feedparser tzdata
python -m compileall -q .
python -m pytest tests -q
for f in tests/test_*.js; do node "$f" || exit 1; done
npm ci
npm run lint
```

Inspect protected-action stubs and use scratch stores before running suites.
Use pytest: unittest discovery omits bare pytest functions. JavaScript suites
check source contracts, not rendered behavior. `npm run test:browser` uses the
scratch-only preview harness; first verify port 8437 is not another server.
See `scripts/check.ps1` for the additional source encoding/control-byte gate.

## Navigation

- [Production architecture](docs/PRODUCTION-ARCHITECTURE.md): source ownership,
  execution order, lifecycle and research boundaries.
- [Repository inventory](docs/REPOSITORY-INVENTORY.md): every tracked baseline
  path classified with reference evidence.
- [Work state](docs/WORK-STATE.md): dated open outcomes and handoff status.
- [Hardening](docs/HARDENING.md) and
  [autonomy operations](docs/AUTONOMY-OPERATIONS.md): existing contracts.
- `app/tests/`: engine, API, UI and version-cascade verification.
- `app/BUILDLOG.md`: historical decisions, including corrections/retractions.
- `graphify-out/wiki/`: generated navigation; check its build commit before use.

Historical plans and past account measurements are not current implementation
or performance guarantees. Future research may test production playbooks but
must write candidate strategies and require explicit production promotion.
