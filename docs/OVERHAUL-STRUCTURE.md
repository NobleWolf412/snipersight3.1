# Trading Experience Overhaul — worked structure

Companion to the overhaul plan. The plan says *what*; this resolves *how*, and
corrects three places where it assumes something the code does not do.

Written against HEAD `9f67159`. Every claim below was checked in source, and
the ones that matter name their file. Nothing here is built.

---

## 0. Three corrections before anything is designed

**(a) There is no shared admission path to extend. One has to be built.**

The plan reads "*then* establish one account admission path", implying a
refinement of something existing. There is no gate to refine:

| path | who approves it | budget checked? | slot counted? |
|---|---|---|---|
| bot | `riskpaper.run` → `risk.decide` | yes | yes |
| manual | **nobody** | **no** | **no** |

`manual.create_intent` (`engine/manual.py:466`) takes `risk_usd` as a
*caller-supplied parameter*. It validates the bracket and the levels; it never
consults the risk authority, the ledger balance, the concurrency ceiling or
the cooldowns. Manual and bot already share the account's money and have never
shared its gate.

This is the single largest piece of work in the release, and it is Phase B's
whole reason for existing.

**(b) The concurrency boundary is two OS processes, not two devices.**

The plan says "including simultaneous requests from different devices".
Devices all funnel through one uvicorn worker. The real race is between **two
separate processes** the watchdog supervises — `live.py` (the scanner, which
runs `riskpaper` then `autotrader`) and `server.py` (the API, which handles
manual arming) — over one SQLite file.

That changes the mechanism entirely. An in-process lock, a module global or an
asyncio primitive cannot see the other process. See §2.

**(c) Moving paper to 0.25% is a decision, not a detail.**

§3 says the new shared account uses "the existing live sizing basis — 0.25%
per trade". Paper sizes at **2%** today (`risk.MODE_RISK_PCT`). Adopting
0.25% makes every paper dollar figure 8× smaller, is a behaviour change
requiring a version bump, and means the forward book and the research replay
are no longer comparable in dollars — only in R.

That is probably the right call (paper should rehearse the live envelope) but
it needs to be taken deliberately, and the R-versus-dollars consequence stated
on screen wherever both books appear.

---

## 1. Ownership map

One authority per number. Every value the cockpit renders resolves to exactly
one record; anything not on this list is not renderable yet.

| displayed value | authority | module |
|---|---|---|
| cash, equity, unrealised, today's P&L | paper ledger snapshot | `paperbook.snapshot` |
| open risk, reserved risk, committed risk | same | `paperbook.snapshot` |
| slots used / ceiling | same + `gates_for_mode` | `paperbook`, `risk` |
| halted today, drawdown | same | `paperbook.snapshot` |
| realised money by outcome class | same | `paperbook._by_outcome_class` |
| outcome class of one trade | `telemetry.outcome_class` | `telemetry` |
| order lifecycle (queued → routed → filled → closed) | the outbox | `execution` |
| position, entry, exit, R, costs | `paper_positions` | `execution` |
| routing state per domain | domain records only | `opportunities` |
| the replay's account of a setup | `research_story` — display, inert | `opportunities` |
| risk verdict (paper) | `risk_paper` facts | `riskpaper` |
| risk verdict (research) | `risk` facts | `risk` |
| mode, promotion, drills | automation state | `automation` |
| capabilities per symbol | venue contract | `venues` |

**The rule that makes this enforceable:** a UI field names its authority in
the API response. `/api/paper-book` already carries `authority`. Extend that
to every `/api/ui/v1` payload rather than trusting convention.

---

## 2. The admission gate

The plan's Phase B gate — *"simultaneous manual/bot requests cannot exceed the
budget; retries cannot duplicate orders"* — is the hardest requirement in the
release. It has a concrete answer.

### The mechanism

SQLite is in **WAL with `busy_timeout=60000`** (`engine/store.py:188,198`).
That gives one writer at a time and makes a second writer wait rather than
fail. What it does *not* give is atomicity across a read-then-write: two
processes can both read "budget free", then both write.

The fix is one SQLite primitive the codebase does not currently use anywhere:

```
BEGIN IMMEDIATE              -- take the write lock BEFORE reading
  read the ledger snapshot   -- balance, open risk, reservations, slots
  decide                     -- risk.decide, unchanged
  insert the outbox row      -- the reservation IS the row
COMMIT
```

`BEGIN IMMEDIATE` acquires the write lock at the start of the transaction
rather than at the first write, so the budget a decision is made against
cannot move underneath it. The loser waits up to 60 s and then re-reads. No
new infrastructure, no lock table, no daemon.

### What this means for the existing code

- `riskpaper.run`'s intra-cycle claim tracking (added in `9f67159`) is
  bookkeeping *within* one process and remains correct, but it is **not** the
  cross-process guarantee. Both are needed; neither substitutes.
- `enqueue`'s `INSERT OR IGNORE` on a UNIQUE idempotency key already gives
  retry idempotency at the row level. That survives untouched — it answers
  "same request twice", while `BEGIN IMMEDIATE` answers "two different
  requests at once". Different questions, different mechanisms.
- The gate must wrap **both** callers. A gate the bot honours and the manual
  endpoint bypasses is not a gate.

### Recovery

A crash between the reservation and the dispatch leaves an outbox row in
`PENDING`. That is already the correct state: `paperbook` counts it as
reserved, so the budget stays claimed, and the existing retry path picks it
up. What is missing is a **release rule** — a `PENDING` row that has never
routed and whose setup has expired should be cancelled rather than holding
budget for ever. Today one such row from August holds $208.

**Acceptance evidence:** two real processes, not two threads. Spawn a second
Python process against a scratch store, have both attempt admission at the
same instant, assert exactly one reservation exists and the other received a
refusal naming the budget. A single-process test proves nothing about this.

---

## 3. Identity

The plan asks for account, attempt, intent and position identity to be
persisted. Three of the four exist. One does not.

| identity | today | needed |
|---|---|---|
| intent | `intent_id`, unique column | — |
| position | `paper_positions.intent_id` | — |
| attempt | **derived only**, inside the idempotency hash | **a column** |
| account epoch | does not exist | **a table** |

### Attempt

`attempt_id` = version-stripped zone + confirming bar
(`opportunities.attempt_id_for`). Since `9f67159` it feeds
`execution.intent_key`, so a retest no longer inherits the previous attempt's
row — but it is only recoverable by recomputation, and a test currently
forbids querying it because no column holds it.

The release needs it stored, for the reason that test names: **the moment
several intents can belong to one attempt** — partial fills, a resize, a
replacement order, and manual taking control of a bot position — time alone
can no longer say which attempt a record belongs to. The overhaul introduces
all four.

So: `execution_outbox.attempt_id`, written at enqueue, nullable for legacy
rows. Then relax the guard in `test_execution_domains.py` from "no query may
name it" to "no query may name it on a table that lacks it".

### Account epoch

Reuse the shape that already works. `research_baselines` (`store.py:170`) is
the existing epoch mechanism — `active=1`, a `started_at`, version stamps —
and every read scopes to it. An account epoch is the same idea for money:

```
account_epochs(id, workspace, mode, opened_at, opening_equity,
               profile_version, active, closed_at, label)
```

Every ledger read scopes to the active epoch. The cutover creates a new row
rather than mutating history, which is why "do not recalculate historical
outcomes" comes for free instead of needing discipline.

### Origin, controller, and grade eligibility are three fields

The plan says "preserve original trade origin separately from current control
owner". It needs a third:

| field | answers | changes? |
|---|---|---|
| `origin` | who created this — BOT or OPERATOR | never |
| `controller` | who manages it right now | on handoff |
| `grade_eligible` | may this score an autonomous strategy | **latches false** |

The third cannot be derived from the first two. A bot trade an operator took
control of and handed back has `origin=BOT`, `controller=BOT`, and must still
be excluded from strategy grades for ever — the operator's intervention
changed the outcome. Deriving eligibility from the current controller would
silently re-admit it. Latch it false on the first handoff and never clear it.

---

## 4. Cutover

The plan's five steps need to survive a crash halfway through, and need an
answer for "what if exposure never resolves".

### State machine, persisted on the epoch row

```
OPEN ──pause requested──▶ DRAINING ──all terminal──▶ SEALED ──▶ (new epoch OPEN)
                              │
                              └──operator abandons──▶ OPEN (resume, no cutover)
```

- **DRAINING** blocks new admissions at the shared gate — one place, both
  callers — and leaves management, protection and settlement running.
- **SEALED** is only reached when every intent in the epoch is terminal and
  every position closed. Proved by query, not by elapsed time.
- Resumable by construction: the state is a column, so a restart mid-cutover
  re-reads it rather than starting over.

### If exposure never resolves

Name it rather than hoping. A 4H position that never reaches its stop or
target sits until its 100-bar timeout — that can be days. `DRAINING` has no
deadline and **must not force-close**: closing a position to tidy a migration
is a real trade taken for an administrative reason.

The honest answer is that DRAINING is a state the operator can sit in
indefinitely, sees on screen, and can abandon. The new epoch waits.

### Rollback is two things, not one

The plan says rollback restores the previous UI. Split it:

- **UI rollback** — safe, and the old screens keep working over compatibility
  adapters.
- **Execution rollback** — *not* available once the shared gate is live,
  because the old manual endpoint does not check the budget. Rolling back the
  UI must not roll back the gate, or manual arming silently regains its
  bypass.

Never restore an older database over newly recorded trades. That is already
in the plan and is right.

---

## 5. Delivery — one change to the sequence

The plan's Phase A (prototype) and Phase B (account) are independent, and
Phase C builds all six destinations. That last part is where it can go wrong.

**Prove one complete shared-account journey before building six screens.**

Concretely, insert between B and C:

> **Phase B2 — one journey, both origins.** A manual arm and a bot dispatch,
> against one account, through one gate, both appearing in one journal with
> correct origin and controller. Gate: the second of the two is refused for
> the slot, by name, and the refusal reads the same whichever came first.

The reason is empirical. This project has just spent a week discovering that
every engine was individually correct while the system was not, and that six
screens rendering a wrong number all render it convincingly. One journey
proves the seam; six screens prove the layout.

Everything else in §5 of the plan stands, including releasing the UI
independently of execution graduation.

---

## 6. Open questions for the review

1. **0.25% paper sizing** — confirm, and decide what the screens say where
   the two books' dollars are no longer comparable. (§0c)
2. **Setup score** — the previous composite rank sorted the deck *backwards
   at its own mode*: rank 65 held 51% of the deck at −0.643 R while rank 50
   was +0.027 R (`setups.py`). Any replacement needs grading before it is
   displayed, or it is the confidence number again with a new label.
3. **Hard envelope** — the plan says expanding it is out of scope, but a
   shared manual+bot account with `MAX_CONCURRENT=1` means a manual trade
   locks the bot out entirely. Intended?
4. **Stale-response rejection** (§3) — needs a monotonic request sequence per
   workspace, not timestamps. Client clocks are not ordered.
5. **`pytest`/`httpx` "missing locally"** — that is the reviewer's
   environment, not the repository's. CI runs the suite; nothing in the repo
   needs fixing for it, and a dependency manifest should not be written to
   solve it.

---

## 7. What this does not resolve

Named so nobody reads silence as completion.

- **The two venue-dependent drills.** No executing sandbox exists anywhere
  (`docs/AUTONOMY-OPERATIONS.md`). Unchanged by this release.
- **Whether the Coinbase sandbox can rehearse orders.** It cannot — static
  mocked responses — so the adapter question is still open.
- **Stocks.** The plan keeps it behind explicit blockers, which is right, but
  a second workspace sharing the shared gate multiplies §2's test matrix.
- **Market Pulse freshness under failure.** The plan says show source and
  refresh status; it does not say what the screen does when a feed is stale
  for a day. Needs an answer before build, not after.
