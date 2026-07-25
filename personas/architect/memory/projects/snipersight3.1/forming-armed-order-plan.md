---
name: forming-armed-order-plan
type: decision
status: approved
project: snipersight3.1
next_owner: coder
---

## Rulings (2026-07-24)
- **Freeze exception: GRANTED** by user ("ok go for it"). This is the one
  trade-logic change permitted inside the 2026-07-21 → ~2026-08-20 freeze
  window. Forward-record clock is NOT reset — the change is additive with
  the same gates and same fill semantics; the armed order equals what
  VALIDATED would have computed today, so any equity diff on 4H/1D/1W
  replay must be explained (Phase J) before merge.
- **Sizing seam: A (extract pure `risk.size_order`)** — recommended
  option accepted by user in the same message. §9 authority preserved:
  risk.py owns the sizing code; setups.py imports the helper. Phase E
  proceeds on path A; path B (parallel PROVISIONAL_SIZE facts) shelved.

# Complete FORMING → armed order (War Room idea #5)

## Problem

War Room 2026-07-24 idea #5 (argued by Auditor, User Advocate) proposes:
extend FORMING emission to attach `entry, SL, TP, size, expiry_bar_count` at
zone-approach time so the live loop watches for touch and promotes to
VALIDATED with **no runtime decision at execution**. Sibling idea #4
(Brainstormer, Architect) says the same thing.

## Grounding — what the room got right, wrong, and stale

Verified against the actual code, not the pitch text.

**Right:**
- `setups.py:38` (pitch said `:39`) — `FORMING_TFS = ("4H", "1D", "1W")`.
- FORMING is emitted for 4H/1D/1W with the same R:R + fee gates as
  VALIDATED (`setups.py:193-264`).

**Already true (the pitch understates how much ships):**
- FORMING **already attaches** `entry`, `sl`, `tp`, `rr`, `strategy`,
  `direction`, `zone_id`, `regime`, `distance_atr`, `zone_strength`,
  `manifest_hash`, `cost_manifest_hash` (`setups.py:240-251`).
- Missed-limit accounting **already exists**:
  `execsim.py:96-116` emits `outcome: MISSED` + `order event: MISSED`;
  `validate.py:22-30, :101` counts and reports missed limits;
  `telemetry.py:23-51` codes `ENTRY_NOT_FILLED`;
  `server.py:132-386` surfaces it; `HARDENING.md:28-30` under exec-v0.7
  acknowledges "limit entries may be missed" and line 41 lists
  "missed-entry rate" as cockpit-exposed. **The pitch's "HARDENING.md
  explicitly flags missed-limit handling as an open gap" is not
  supported by the current file.**

**Actually missing (the real delta):**
1. `size` (risk-sized units + risk_usd + decision) is not on the FORMING
   payload — `risk.py` runs post-VALIDATED, not against FORMING.
2. `expiry_bar_count` / `expires_at_ts` is not on the FORMING or
   VALIDATED payload — `execsim.MAX_ENTRY_BARS = 4` lives only as a
   runtime constant.
3. **VALIDATED re-computes from scratch** at touch (`setups.py:266+`)
   rather than adopting the FORMING order. This means the "no runtime
   decision at execution" property the pitch claims **is not yet true**
   — it's the load-bearing change, not a payload rename.
4. MISSED exec facts do not carry a `forming_id` back-pointer.

**Estimate:** ~80 lines is optimistic if we honor §9 (risk owns sizing —
setups cannot size). Realistically 150–220 lines across
`setups.py`/`risk.py`/`execsim.py`/`telemetry.py`/tests.

## Load-bearing constraint — the freeze

`state.md` declares a FEATURE FREEZE from 2026-07-21 through ~2026-08-20:
"No new trade logic until forward record ~30 days … Allowed: Tauri
packaging, Telegram alerts, §30 session, Item I rulings, bugfixes." Today
is 2026-07-24. **This idea is new trade logic** (it changes how VALIDATED
is derived, which is a state-machine change). It is blocked pending an
explicit freeze exception from the user. Every phase below assumes that
ruling comes in as "yes, exception granted"; without it, this note stays
`pending-review` and nothing else moves.

## Load-bearing decision — sizing authority (§9)

`risk.py` owns sizing (constitution §9; `HARDENING.md` risk-v0.5). Three
ways to have `size` on FORMING without violating that:

- **A. Extract a pure sizing helper.** Pull the sizing math from
  `risk.py:150-188` (equity → risk_usd → units, gated by exposure/
  leverage/min-notional) into a pure function `risk.size_order(equity,
  entry, sl, ...) -> Decision`. `setups.py` calls it at FORMING time.
  Risk authority still owns the code; sizing is now callable from where
  it's needed. **Recommended** — smallest surface, cleanest lineage.
- **B. Parallel PROVISIONAL_SIZE fact.** `risk.py` gains a pre-pass that
  reads FORMING facts, emits `sizing` facts keyed on `setup_id`,
  consumed by the FORMING → VALIDATED promotion. Purest layering; more
  moving parts; two facts describe one intent.
- **C. `setups.py` sizes directly.** Rejected — violates §9.

User rules between A and B before Phase D starts. Plan below assumes A.

## A→Z phased plan

Numbered so each phase is one-seat-sized with a concrete acceptance
check. **All phases from D onward are blocked by Phase A (freeze
exception) and Phase C (sizing-seam ruling).**

### Phase A — Freeze exception ruling
- Owner: user.
- Deliverable: explicit yes/no (in chat is enough; recorded to `state.md`).
- Accept: `state.md` updated with the ruling.

### Phase B — Grounding memo (this note)
- Owner: Architect (done).
- Accept: this file + `MEMORY.md` pointer; War Room framing corrected.

### Phase C — Sizing-seam decision
- Owner: user (A vs B).
- Deliverable: one-line ruling; this note updated with it.
- Accept: ruling captured; downstream phases un-ambiguous.

### Phase D — Extend FORMING payload
- Owner: Coder.
- Changes: add `size_units`, `risk_usd`, `notional_usd`, `implied_leverage`,
  `risk_decision`, `risk_reasons`, `expiry_bar_count`, `expires_at_ts`,
  `armed_at` to the FORMING fact payload (and to CANCELLED, VALIDATED).
- Accept: schema-only diff, no behavior change until Phase F wires it —
  every field is populated, older-data replays still bit-identical
  because new fields default to prior semantics on missing.

### Phase E — Wire risk.py against FORMING
- Owner: Coder.
- Per Phase C: either (A) `setups.py` imports the extracted
  `risk.size_order(...)` and calls it at FORMING emission time, or (B)
  `risk.py` gains a `size_forming(con)` pass that runs before `setups`'
  VALIDATED pass and emits PROVISIONAL_SIZE facts.
- Accept: every FORMING fact carries a resolved risk decision
  (APPROVED / REDUCED / REJECTED) with the same reason codes risk.py
  already uses; REJECTED FORMING facts still emit but are marked
  `armed: false`.

### Phase F — VALIDATED inherits FORMING verbatim
- Owner: Coder.
- Change `setups.py`'s VALIDATED pass to look up the matching FORMING
  fact by `setup_id` and copy `entry/sl/tp/size_units/expires_at_ts`
  onto the VALIDATED payload rather than recomputing. Recompute only
  when no FORMING exists (LTF paths — 15m/1H — have none by design).
- Accept: for 4H/1D/1W, every VALIDATED payload's `entry/sl/tp/size` is
  byte-identical to the immediately-preceding FORMING for the same
  `setup_id`. Assert this in a test.

### Phase G — execsim consumes armed order
- Owner: Coder.
- `execsim.py` continues to fill against VALIDATED, but the order it
  places is the armed order verbatim. Propagate `forming_id` /
  `armed_at` / `expires_at_ts` onto the `order` and `exec` facts.
- Accept: for 4H/1D/1W, `order.event=PLACED` carries `forming_id ==
  <the FORMING fact's id>`; existing tests unchanged.

### Phase H — MISSED-limit lineage
- Owner: Coder.
- `execsim`'s MISSED path already exists — annotate the MISSED `exec`
  fact with `forming_id`, `armed_at`, `expires_at_observed`, and a
  boolean `bars_armed_exceeded`. `validate.py` cohort report gains a
  "missed-by-armed-window" column so we can see whether MAX_ENTRY_BARS
  is well-calibrated against actual FORMING lead times.
- Accept: `validate.py` cohort report has the new column; existing
  MISSED count unchanged.

### Phase I — Tests
- Owner: Coder.
- Cases: (1) FORMING → VALIDATED same-`setup_id` order equality;
  (2) FORMING → CANCELLED still fires as today;
  (3) LTF (no FORMING) VALIDATED path unchanged;
  (4) REJECTED-by-risk FORMING emits with `armed: false` and does not
      spawn an order;
  (5) MISSED exec carries populated `forming_id` for 4H/1D/1W.
- Accept: `python -m unittest discover -s tests -v` green;
  `python -m compileall -q .` green.

### Phase J — Determinism + replay diff
- Owner: Coder + Architect review.
- Run full pipeline; equity/facts diff vs pre-change baseline.
  Because Phase F changes the VALIDATED payload shape and Phase E adds
  a risk decision to FORMING, the replay WILL diff. That diff must be
  intentional and documented in `BUILDLOG.md` (which fields changed,
  which counts moved, why). If any 4H/1D/1W trade equity outcome
  changes, the reason must be traced to an armed-order property
  difference and explained.
- Accept: BUILDLOG entry recorded; `state.md` updated; Auditor review
  (Phase K).

### Phase K — Auditor review
- Owner: Auditor.
- Reviews the Coder's Phase D–J work against this packet's
  acceptance criteria and the "no runtime decision at execution"
  property specifically: is the VALIDATED order provably inherited?
  Is `forming_id` present everywhere it should be? Does the replay diff
  match the intent?
- Accept: APPROVE / APPROVE WITH NOTES / CHANGES REQUIRED per
  foundation review-convergence rules.

## Next step + owner

**Coder** — begin Phase D (extend FORMING payload; schema-only, no
behavior change) then Phase E (import extracted `risk.size_order` into
`setups.py` at FORMING emission). Work Phases D → K in order; each
phase has its own acceptance check above. Do not skip Phase J's replay
diff. Auditor reviews at Phase K.

## Handoff packet (for the Coder seat)

- **Files in play (read-only survey shows current state):**
  - `app/engine/setups.py` — FORMING pass at lines 193-264; VALIDATED
    pass at lines 266+. FORMING payload built at lines 240-251.
  - `app/engine/risk.py` — sizing math at lines 150-188 (equity →
    risk_usd → units, gated by exposure / leverage / min-notional).
    Extract this into `risk.size_order(equity, entry, sl, ...) ->
    Decision` (Phase E prerequisite).
  - `app/engine/execsim.py` — order placement at lines 74-83, MISSED
    path at lines 96-116, fill loop at 118-146. Phase G/H changes here.
  - `app/engine/telemetry.py` — ENTRY_NOT_FILLED taxonomy already in
    place; Phase H just adds `forming_id`/`armed_at`/`expires_at`
    fields, no new stage.
  - `app/validate.py` — cohort report at lines 100-101; Phase H adds
    one column.
  - `app/live.py` — no changes expected (armed-order property is a
    fact-store contract, not a live-loop change).
  - `app/tests/` — Phase I lives here. `test_core_hardening.py:150`
    already has `test_unrevisited_limit_becomes_missed` — extend or
    mirror pattern.
- **Contracts to preserve:**
  - Determinism: append-only facts, idempotent re-runs (§4.1).
  - §9: `risk.py` remains the sole author of sizing logic (helper is
    still owned by risk.py; setups.py only calls it).
  - Loud-fallback rule: any FORMING that cannot be sized (missing ATR,
    equity gate, etc.) logs at WARNING and emits with `armed: false`
    rather than silently dropping.
  - Fact schema: new fields are additive; older facts remain readable
    (server.py and validate.py must tolerate missing `size_units` on
    pre-change FORMING facts).
- **Bit-identity assertion (Phase F acceptance):** for 4H/1D/1W, if
  a FORMING fact exists for a `setup_id`, the subsequent VALIDATED
  fact's `entry/sl/tp/size_units/expires_at_ts` must equal the
  FORMING's byte-for-byte. Assert in a new test.
- **Expected replay diff (Phase J):** counts of VALIDATED-without-
  FORMING on 4H/1D/1W should approach zero (FORMING coverage is
  already high per S16 — 31 historical FORMING / 7 CANCELLED).
  Equity outcomes for 4H/1D/1W trades should NOT change materially —
  same entry, sl, tp — but new fields on the payload will change fact
  content hashes. Document this in BUILDLOG.
- **Non-scope (do not do):** no sizing-authority relocation; no
  LTF (15m/1H) FORMING emission; no new state names; no changes to
  `PROX_ATR`, `MIN_RR`, `SL_ATR`, or cost profile; no live-loop or UI
  work beyond tolerating the new fields.
