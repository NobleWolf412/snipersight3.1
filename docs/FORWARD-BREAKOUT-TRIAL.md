# Breakout–retest forward trial

Approved on 2026-09-15: gather new evidence on live incoming prices, with
simulated orders and a separate $10,000 balance. No broker calls, main-account
orders, risk facts or strategy grades are created by the trial.

## Scope and timing

The scanner activates the trial once, freezing the wall-clock start, maximum
existing fact ID, strategy/simulation/ATR versions and cost profiles. Only
later-inserted breakout facts with confirmations after activation qualify.
First observation must be within three strategy candles of confirmation;
the source entry deadline must still be beyond the prospective activation.
Old and malformed newly inserted candidates are recorded as skipped.

Breakout currently becomes observable after the candle following confirmation
has closed. Its backdated confirmation time is therefore never used as a
trial fill time. Entry starts on the next candle boundary strictly after
wall-clock observation. This is a **prospective entry variant**: two complete
future candles for the recorded maker limit, then a market cross on the third.
Simply preserving the old deadline would make the market fallback impossible.
The original deadline is retained in the placement record. The UI explains
this timing; results must not be presented as a replay of the old entry model.

Setup identity, rather than fact ID, deduplicates attempts. Updated payloads
cannot create another order for the same attempt. The scanner's observation
cadence affects which setups are fresh enough, and skipped cases remain visible.

## Money and execution

Target price risk is a fixed $100 per trade, without compounding, with at most
five pending/open trades and one per exact market symbol. Quantity is fixed
from the original entry-to-stop distance. Fees and a changed fill can make
actual losses exceed $100. This is a strategy experiment, not a recommendation
to adopt its risk settings. Main-account risk settings do not affect it.

Pending/open orders reserve planned notional plus 2%; total reservations must
fit the trial's realized cash balance. No borrowing is modeled. A fill whose
notional and entry fee exceed its reserved cash is declined. Unsupported spot
shorts are skipped. Limits are deliberately conservative and can exclude
otherwise valid signals; this is a constrained trial, not every setup's return.

Shared pure execution helpers model entries, stop/target/timeout exits, fees,
slippage and constant funding. Entry slippage uses ATR available before the
fill candle. Accepted candles are frozen in the trial ledger; imports cannot
rewrite a fill or completed result. Missing candles, including acknowledged
venue voids, block progress until evidence exists. An unresolved trade keeps
its market on the import list even after universe removal. Both stop and
target in one candle counts as stop; that limitation is visible in the UI.

Dollar settlement is quantity times exact net price movement less modeled
costs, never rounded R times risk. Balance contains completed trades only;
unrealized returns are not estimated. Funding and slippage are models, not
measured execution. The trial does not establish profitability.

## Operation

`engine/forwardtrial.py` owns three dedicated tables: immutable trial config,
append-only lifecycle/candle events, and append-only scanner checks. A
`BEGIN IMMEDIATE` transaction makes each update atomic across processes.
The scanner runs it on normal and idle passes; API GETs do not activate it.
Research shows balances, a completed-trade balance chart, counts and expandable
trade/skip details. Checks older than 30 minutes show an explicit delay.

Dependency changes pause the trial rather than reprice existing results.
There is intentionally no automatic reset, historical backfill, promotion to
the main account, or timer that declares success. A subsequent rule version
requires a deliberate continuation policy for unresolved trades.

Validation lives in `app/tests/test_forwardtrial.py`, the version cascade
lockfile and the scratch-only cockpit browser suite.
