# Bot loss audit — 21 September 2026

The concern is supported by evidence. There is a real account-wide blocking defect, paper execution does not faithfully preserve the researched entry, and the strategy research itself is negative after costs. Fixing the first two does not establish profitability.

This is an investigation, not a strategy deployment. No trading settings, orders, production data, or application code were changed.

## What the actual account has done

Read-only snapshot: **2026-09-21 23:52:57 UTC**, code `ea02279`. The account has no separate account epoch; its paper ledger starts at $10,000. All seven bot orders were reversals: five filled and stopped out, two expired unfilled. The separate operator order also expired unfilled. No positions remained open at the snapshot.

| Filled trade | Direction / timeframe | Account result | Recorded result against initial risk | Signal-to-order delay |
|---|---|---:|---:|---:|
| ENAUSDT | Long / 15m | −$176.47* | −1.18R | 27.85 minutes |
| LINKUSDT | Long / 1H | −$218.08* | −1.11R | 78.93 minutes |
| BNBUSDT | Short / 15m | −$248.06 | −1.29R | 18.40 minutes |
| ADAUSDT | Short / 15m | −$205.26 | −1.10R | 11.73 minutes |
| ETHUSDT | Short / 1H | −$210.03 | −1.15R | 49.62 minutes |

**Balance: $8,942.10; loss: $1,057.90, or 10.58%.** R means the trade's price risk to its original stop. Five trades are too few to establish the future win rate, but they are real losses in this paper account.

\* Two older settlements use the existing rounded-R estimate. Reconstructing all five from recorded prices, quantities and costs gives −$1,058.45, a $0.56 difference; the audit did not rewrite those settlements.

The losses are approximately $908.32 of price risk to the stops, $102.73 fees, $12.87 modeled funding and $34.54 exit slippage. Slippage is already in the effective exit price and must not be subtracted twice. These were losing price moves even before costs. Costs made them worse: BNB alone paid about $55.95 beyond its $192.11 planned stop risk.

All five fills were recorded as maker fills at the dispatched limit. The potential crossed-entry risk and slippage defects described below did **not** cause these five losses.

## 1. A damaged market can still stop healthy markets

**Confirmed scope defect, currently active.** Latest recorded quality report `8073` has `evaluation_allowed=false`, caused by one unexplained 5m candle discontinuity on each of PENGU-USD and PEPE-USD. No account position was open.

The defect is the scope of the response, not proof those gaps should be ignored:

1. `quality.py:319–370` collects scan members plus unresolved research, manual and paper positions into a roster used to prevent unsafe data retirement.
2. `quality.py:1063–1068` also uses that roster to turn any relevant market's blocking finding into a global trading prohibition.
3. `risk.py:422–429` reads one global boolean; `risk.py:503–504` rejects every candidate with `DATA_HEALTH_BLOCKED`.
4. `shared_account.py:178–192` shares that policy with bot and manual admission.

This contradicts the isolation promised at `live.py:695–700`: a bad market should not stop other markets. The previous quality fix excluded irrelevant stored markets, but did not separate per-market admission from account-wide safety. Even a research-only unresolved position can keep a symbol in this global veto roster.

PEPE became a global blocker at **2026-09-19 18:38:19 UTC**. Apart from a roughly one-hour recorded recovery on September 21, it remained a blocker; PENGU joined at 18:53:07 UTC that day. Nine current-generation candidates across AVAX, LTC, SOL, BNB, TAO and XRP had data health as their first recorded rejection. AAVE also received a later data-health refusal after a universe rejection and is excluded from that nine-count. This is not evidence that all nine would otherwise have passed every later gate, nor that they would have won.

**Fix boundary:** preserve damaged-market restrictions and data-retention pins. Separate store/account-wide failures from per-symbol failures, and evaluate the latter against the proposed trade's market. An actual held exposure that cannot be priced needs an explicit account-risk policy; a simulated research position must not impersonate account exposure. Test healthy candidate/bad scan member, research-only bad market, bad candidate market, genuine store failure and unpriceable actual exposure through both admission paths.

## 2. Paper and research do not trade the same entry

**Confirmed in every one of the seven bot orders.** Setups record a passive limit 0.10R better than the reference entry (`setups.py:1374`). Research uses that recorded limit (`execsim.py:570`). The paper recommendation uses the reference `entry` instead (`opportunities.py:244,274`), which becomes the paper limit (`execution.py:643`).

Example: BNB's researched short limit was **738.747775158550**, but the actual paper order/fill used **738.54**. This changes fill selection, price and sometimes maker-versus-taker costs. It is not enough to say both paths call the same simulator when they pass different plans to it.

A pure reproduction with reference entry 100, stop 90 and recorded limit 99 produces a paper maker fill at 100 on the first bar, whereas research waits and crosses at 106.10 on the third bar. This demonstrates divergence; it does not demonstrate that repairing the mismatch makes this or every trade profitable.

Two additional defects affect crossed entries:

- Paper supplies no ATR to the entry simulator (`execution.py:640`), so modeled crossing slippage is omitted, with a warning. This makes results optimistic.
- Quantity remains the admission quantity after a worse fill (`execution.py:676`), while open exposure continues to use original plan risk (`paperbook.py:222–255`). Crossing from 100 to 106 with a stop at 90 increases price exposure by 60% at unchanged quantity. Recorded net dollars eventually reflect the loss; the reserved risk understates it meanwhile.

**Fix boundary:** preserve the recorded entry model, maker limit and wait; carry reference and executable prices explicitly; size the executable plan consistently; enforce bounded crossing/revalidation before increased exposure, and record actual fill risk. Supply causal ATR consistently. Use one immutable plan through replay, prospective study and paper execution, with explicit actual-dispatch delay. Require parity fixtures for every entry model, expiry, gap and cost path. These are behavior changes requiring the repository's version cascade.

## 3. Late orders change the experiment

Research can act after the confirming candle. Paper waits for actual dispatch and considers only complete candles whose opening time is at or after that dispatch (`execution.py:565–578`). It therefore discards the remainder of the current candle. This is deliberate conservatism with OHLC data, but late scanning makes the difference material.

The two expired bot orders were ZEC, dispatched 30.83 minutes after a 15m signal, and LINK, dispatched 18.22 minutes after a 15m signal. Their remaining eligible windows were too short to complete the planned two-bar passive wait and then cross. Research's near-automatic eventual fill is not the actual bot's capture rate.

Today's 76 logged scans had a median core duration of **14.12 minutes**, range 13.22–25.04; median account decision occurred 4.61 minutes after scan start. These core durations exclude some outer-loop work. Moving account admission earlier helped, but deferred research still delays the next cycle. Signal-to-order delay includes scan timing and, for some orders, waiting for account availability; it must not all be attributed to calculation time.

**Fix boundary:** establish a measured decision deadline after each tradable candle close, remove research/regrading from the critical schedule, and keep settlement/admission fresh. Do not recover apparent speed by permitting pre-order fills or extending expired entries silently. Compare ideal signal-time replay with measured dispatch-time replay and real paper fills separately.

## 4. The researched strategies have not earned a positive-edge claim

Latest stored grade: `strategy_regrades.id=19`, **2026-09-21 03:18:13 UTC**.

| Strategy | Completed research trades | Average net result per trade | Profit factor |
|---|---:|---:|---:|
| Pullback | 282 | −0.1545R | 0.82 |
| Reversal | 888 | −0.1494R | 0.82 |
| Breakout retest | 305 | −0.3541R | 0.61 |
| Trend continuation | 11,489 | −0.3026R | 0.66 |

A profit factor below 1 means losses exceed gains in that sample. None clears the implemented positive-edge criterion. Reversal's symbol-clustered interval is −0.2789 to −0.0150R; pullback's spans zero. These are retrospective research results, not independent prospective proof or the actual account's dollars.

The report's `trustworthy=true` means its replay matched recorded **research** settlements. It does not certify paper fills, future performance or a profitable strategy. The shared certificate does not independently certify each alternate playbook's forward execution. The report also sets aside 3,464 uncertified simulated fills across its strategy runs.

Its 100% fill figures refer to resolved simulated outcomes under a model that crosses to market. Pending entries and still-open trades are excluded. They cannot be presented as the percentage of live opportunities captured. Stored grade reports also lack a complete frozen input manifest: exact strategy versions, markets, timeframes, cutoff and included identities should be persisted.

Paper enables pullback and reversal without a profitability prerequisite (`settings.py:43–44`); daily regrading records evidence but does not promote/demote them (`regrade.py:33`). That is suitable for an explicitly labeled experiment, not evidence that an enabled strategy is validated.

### What the actual reversals were betting on

The recorded chart context said UP for the BNB, ADA and ETH shorts, and DOWN for the LINK long. ENA was CHOP. Three of the five reversal records carried VOLUME/STRENGTH without CHOCH or SWEEP; ADA included CHOCH and volume; ETH included CHOCH. These are reversal bets, not confirmed trend-following entries.

That is allowed by current policy. Bias, pullback-context and chart-window policies are ALLOW; BTC alignment is measurement-only; the stored rank does not admit or reject trades. Turning off this supposed stack of filters cannot recover trades because it is not blocking them now. Conversely, the descriptive chart's disagreement does not currently protect the account. Whether imposing such a filter helps must be measured on unseen observations, not selected from five losses.

## 5. What the blocked count actually means

For **2026-09-14 23:52:57 through 2026-09-21 23:52:57 UTC**, the paper risk ledger contains 72 decision changes over 60 candidate identities. Identity here removes the algorithm-version suffix and combines setup identity with its source market time; distinct zones remain distinct candidates, even on the same market and candle.

Five candidates were approved at least once and became actual orders: three filled and two expired. Of the 55 never approved, their first recorded reason was:

| First paper-account rejection | Candidates |
|---|---:|
| Data-health block | 30 |
| Outside the universe at signal confirmation | 14 |
| Account's one slot occupied/reserved | 6 |
| Two earlier short losses that UTC day | 3 |
| Shorting unsupported on spot venue | 2 |

Reasons are evaluated in priority order, not an exhaustive list of everything wrong. Removing the first reason can expose another. These 30 health refusals span older and current generations and are not all attributable to today's two blockers.

This does **not** support the earlier explanation that the current bottleneck was primarily the one-position setting or 179 actual-account cooldowns. No first rejection in this window was an actual-account cooldown. Point-in-time universe eligibility is checked at **signal confirmation**, not simply at today's membership.

Also, latest-only risk counts would misleadingly say all 60 were rejected: five previously approved candidates later acquired another verdict, including rejection because their own order occupied the slot. Order custody and verdict history must be retained when counting the funnel.

Current-generation setup history contains 474 distinct setup IDs with an update in the window, including 155 latest cancellations because the zone broke, 68 confirmation timeouts and 120 rejections for inadequate reward versus risk. They are not 474 ready, independent trades. There were 84 validated records, but 57 were first materialized after their historical entry deadlines, often during replay/rebuild or renewed market coverage. Do not count these automatically as live missed opportunities or as scanner-delay failures without checking point-in-time coverage.

The last five paper-risk runs passed with zero still-timely input candidates. No new fact is needed when no verdict changes. Live evaluation is happening; the store does not erase actual paper orders when an algorithm version changes. No recent engine fault was recorded in the seven-day window; today's inspected engine log had no ERROR/CRITICAL lines. That does not negate the logical blocking defect.

## 6. Follow-up: profits were observed, but actual stops never moved

The operator's follow-up about the chart's "Best observed price" exposes an important omission in the initial audit: actual paper execution has no active profit-protection rule. `execution.py:712–715` passes the original `intent.stop` to `execsim.walk_exit`; that walk checks fixed stop, fixed target and holding timeout. It does not ratchet the stop after a profitable move.

The marker is a read-only retrospective measurement from `tradevisuals.excursion` (`tradevisuals.py:38–83`), rendered at `static/cockpit/app.js:283–285`. It is not an order, target or stop-update trigger. Complete interior candles, excluding entry/exit candle extremes, establish the following lower bounds before costs:

| Paper trade | Best observed price profit | Initial price-risk multiples | Final account result |
|---|---:|---:|---:|
| ENAUSDT | $386.38 | +2.58R | −$176.47 (estimated) |
| LINKUSDT | $341.85 | +1.74R | −$218.08 (estimated) |
| ADAUSDT | $238.58 | +1.27R | −$205.26 |
| ETHUSDT | $497.47 | +2.72R | −$210.03 |

BNB has no complete interior candle from which this measurement can be made; absence of a reading does not establish zero favorable movement.

Both the three-rule stop study and smaller-timeframe defended-zone study explicitly operate separate simulated ledgers and never adjust the account's stop. Their latest persisted checks at `1790034706` both say the comparison is paused because simulation rules changed. Their frozen configurations still reference older execution versions. Therefore neither provides active account protection, and their current state must not be described as a running test that is collecting new comparisons.

This is observed profit giveback, not proof that the exact peaks could have been captured. A deployable rule needs a trigger known at the time, causal update timing, fees/slippage, and a recorded change to the actual protective stop. Prior work implemented measurement and comparison, not that final behavior. Include this missing account behavior and the paused comparisons in the repair scope, while testing the effect on eventual winners as well as these four losers. Do not tune a rule to their retrospectively identified peaks.

## Comparison with the pasted proposal

The attachment is a summary based on a July audit. The named 5,000-word, 26-source blueprint was not attached, so its complete source claims and proposed implementation could not be checked.

| Proposal | Current code and decision |
|---|---|
| Fix fills before signals existed | Current research and paper enforce signal/order availability; focused tests pass. The July claim is outdated. |
| Make execution realistic and shared | Necessary. Shared helpers already exist, but paper passes a different entry and lacks crossing ATR. OHLC still cannot determine whether a target was hit before a same-candle entry. |
| Test a simple 4H channel breakout | Reasonable independent baseline, not the existing structural breakout/retest strategy. No profitability claim follows from its simplicity. |
| Test trend pullback/reclaim | Some mechanics exist. The current reversal-dominated paper selection and permissive direction policy differ from the proposed trend requirement. |
| Add range rejection | Range detection exists; a frozen-range rejection playbook with execution does not. Keep it a separate experiment. |
| Require confluence factors to earn inclusion | Correct objective. Existing chronological factor reports start with validated, closed trades; they cannot price pre-validation exclusions or prove incremental combined-filter improvements. |
| Use another public bot as a reference | Useful for reproducible comparisons, not evidence its headline return transfers to this account. The attachment's NFI numbers were not independently verified here. |

External evidence supports testing, not adopting a winning recipe. The [NBER cryptocurrency study](https://www.nber.org/papers/w24877) reports momentum findings; it does not validate SniperSight's intraday reversal rules. [Freqtrade's lookahead analysis documentation](https://docs.freqtrade.io/en/stable/lookahead-analysis/) describes a useful method for detecting future-data leakage; framework tooling itself supplies no edge.

## Order of work

1. Repair market-specific versus account-wide data admission. Preserve actual safety restrictions and prove both admission paths with scratch-store tests.
2. Repair entry-plan, costs and risk parity; separately measure dispatch delay and expiry. Preserve historical orders and publish version boundaries.
3. Freeze the evaluation contract: immutable candidate identities, pre-filter reasons, terminal/unresolved counts, actual dispatch times, input manifests and a fixed future test window. Do not confuse retrospective internal consistency with prospective evidence.
4. Compare the repaired existing playbooks with one simple 4H breakout baseline; then test the trend pullback/reclaim alternative. Use the same executable costs and entry rules, separate long/short and timeframe results, and measure net return/drawdown as well as per-trade outcomes.
5. Test frozen-range rejection independently and add one confluence requirement at a time. Keep an untouched future sample; account for overlapping trade outcomes and shared market conditions. Do not optimize filters against these five losses.

Increasing risk, increasing available slots, disabling quality checks globally or forcing a daily quota is not supported by this investigation. The useful simplification is fewer independently testable strategy hypotheses and one accountable execution contract.

## Evidence and verification

- Local diagnostic: `artifacts/loss_audit_20260921.py`; captured output: `artifacts/loss-audit-2026-09-21.json`. Both are ignored local artifacts. The script opens SQLite with `mode=ro`, reads orders/positions, bounded fact history, stored grades, quality history and telemetry, and writes only its diagnostic output. Reads occurred across a live scanner session, not a frozen whole-database backup.
- Source checked at `ea02279`; generated wiki was stale at `eb591d23adff` and used only for navigation. Pre-existing generated Graphify edits were preserved.
- Read-only execution review ran 13 focused tests successfully: execution availability, shared exit settlement, maker/cross behavior, expiry and missing-history protection. No application-opening or live-write tests were used.
- Command: `python -m pytest app/tests/test_core_hardening.py::TestExecutionRealism app/tests/test_execution_parity.py app/tests/test_automation_execution.py::test_paper_entry_uses_shared_maker_then_market_fill_authority app/tests/test_automation_execution.py::test_expired_partial_maker_window_resolves_without_losing_valid_fills app/tests/test_automation_execution.py::test_missing_first_candle_cannot_be_hidden_by_later_touch -q`.
- `scripts/check.ps1 -SkipPython -SkipJavaScript -SkipLint` passed the source encoding/control-byte gate; `git diff --check` passed. Full application suites were not repeated for this documentation-only change. An independent read-only review checked the audit's arithmetic and causal qualifications.
- The investigation ran no full-book replay, new strategy backtest, live write or server restart. No application code changed. Identified defects remain open; the documented remediation is not presented as implemented.
