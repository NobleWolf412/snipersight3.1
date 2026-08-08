# SniperSight autonomy operations

## What happens to a trade idea

Every automated idea follows one server-owned chain:

OFF and SHADOW end at a durable route. PAPER resolves fills and stop-first
exits deterministically from closed candles. In TESTNET, an accepted route can
continue through broker submission, fills, and protected-position custody;
the entry carries an atomic attached stop so a fill is protected before a poll
can observe it. After the fill, SniperSight also maintains a deterministic
standalone reduce-only stop and first target whose venue identities can be
audited. The overlap is deliberate: reduce-only prevents either stop from
reversing a flat position, while the attached stop covers the handoff to the
independently traceable child order.
Trailing stops, discretionary early exits, and target ladders are not
implemented.

A flat custody snapshot is not promotion evidence by itself. TESTNET lifecycle
credit requires exact venue execution IDs, entry and exit quantities, VWAP
prices, fees, a bot-owned exit cause, terminal entry/stop/target cleanup, and
two spaced flat observations. Missing or conflicting evidence closes custody
when safe but earns no promotion credit.

Safety drills are staged one at a time in TESTNET with the exact acknowledgement
`RUN TESTNET SAFETY DRILL: <name>`. Staging does not inject a fault or award a
pass. A pass is written only when the corresponding real code path observes the
disconnect, restart recovery, stale-state block, rejection, partial fill,
protective stop, or kill-switch block — and each drill names the evidence its
pass requires (`automation._DRILL_EVIDENCE`), failing closed when a field is
missing. Restart specifically requires the process boot id recorded at
submission to differ from the one observed at recovery: resolving a lost
response inside one process is disconnect recovery, not a restart, and until
automation-v0.5 it wrongly passed this drill.

`closed candles → market context → playbook → opportunity → risk decision → execution plan → broker → fill → protected position → exit → reconciliation`

A rejection or `NO_TRADE` result is recorded as a valid decision. The browser
shows these records; it does not calculate eligibility, risk, grades, or account
state itself.

## Operating modes

- **OFF** continues scanning and recommendations but holds every new intent.
- **PAPER** never contacts a broker. It simulates limit-touch or next-open
  fills, then stop, first-target, or timeout exits from closed candles. Results
  use the venue's versioned fee/funding/slippage cost profile; missing ATR is
  recorded explicitly rather than silently treated as measured slippage.
- **SHADOW** reads live context and records intended orders without submitting.
- **TESTNET** may use only the separately stored `phemex-testnet` credentials.
- **LIVE** is mainnet. This build is deliberately incapable of constructing a
  mainnet broker, even if credentials exist.

Changing mode requires the latest server revision. SHADOW, TESTNET, and LIVE
also require their exact acknowledgement. TESTNET and LIVE remain locked until
their promotion evidence passes.

## Initial risk contract

- 0.25% account equity risked per trade
- one position at a time
- 0.5% maximum total open risk
- 1% deterministic UTC-day loss halt
- isolated margin and one-way position mode
- no averaging down, martingale, automatic leverage escalation, or withdrawal
  permission

HALT blocks new entries. Existing exposure remains under protective management.

## Evidence and grades

Factor Stats uses chronological train, validation, and forward windows. It
reports coverage, sample size, uplift against a non-overlapping control,
confidence intervals, stability, shrinkage, and multiple-testing-adjusted
significance. Version changes isolate old evidence.

FactorGrade explains and orders opportunities. `UNGRADED` means the setup may
look technically clean but has not earned stable statistical confidence. A
grade never overrides market conflict, stale data, costs, expiry, or risk.

## Promotion sequence

1. PAPER establishes deterministic, point-in-time behavior.
2. SHADOW must run for at least 14 calendar days and record 100 intents whose
   paired PAPER simulations reach a terminal result with no durable-pair
   integrity failures. This proves routing and simulation coverage; it does
   not claim an independent second decision engine or decision parity.
3. TESTNET must run for at least 30 calendar days and complete 100 order
   qualified, distinct bot-owned order lifecycles, with at least 99.9%
   TESTNET reconciliation and all safety drills passing. Duplicate or legacy
   flat-only events do not count.
4. LIVE additionally requires the forward evidence gate and an independently
   tradeable verdict for each enabled playbook.

These are observations, not checkboxes. Time and sample gates cannot be waived
by UI state or a stored API key.

## Manual custody

“Manual override” stops discretionary bot changes but leaves the confirmed
server-side protective stop active. Automation resumes only after the explicit
“Return control to bot” action succeeds. Unknown orders, orphan positions,
stale private state, or reconciliation disagreement block all new private
entries. Phemex reconciliation enumerates active orders across the loaded
product catalogue, so an open order on a symbol SniperSight has never tracked
still blocks new exposure.
